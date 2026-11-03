import math
from .mathutil import clamp,lerp,fract,hash2,noise,fbm,lum,hue,sample
def gate(style,x,y,cx,cy,p,n,sign):
 a=math.radians(p['orientation']);ca=math.cos(a);sa=math.sin(a);u=x*ca+y*sa;v=-x*sa+y*ca;density=clamp(p['density']/100.,.02,1);width=max(.6,p['line_width']);spacing=max(width+1,p['cell_size']*(.12+(1-density)*.35))
 if style=='engraving':return 1. if fract((v+n*p['roughness']*.15)/spacing)<width/spacing else .12
 if style=='impressionist':return clamp(.35+.45*abs(math.sin(u/max(2,p['cell_size']*.22)+n*4.5+sign*.35))+.35*max(0,noise(x/max(3,p['cell_size']*.35),y/max(3,p['cell_size']*.35),p['seed']+77)),.1,1)
 if style=='cubist':
  lx=(x%p['cell_size'])/p['cell_size'];ly=(y%p['cell_size'])/p['cell_size'];return 1. if fract((lx+ly+n*.12+sign*.04)*2)<.22 or abs(lx-ly)<.045 else .35
 if style=='surreal':return clamp(.45+.4*math.sin((u+.6*p['cell_size']*n)/max(2,p['cell_size']*.18)),.08,1)
 if style=='penskip':return 1. if fract((u+n*p['roughness']*.35)/max(2,spacing*.75))<.06+.28*density else .16
 if style=='stipple':return 1. if hash2(int(x/max(1,width)),int(y/max(1,width)),p['seed']+cx*17+cy*31)<density*.42 else .1
 return clamp(.3+.7*abs(n),.08,1) if style=='fractal' else .5
def render(src,w,h,bits,p):
 out=bytearray(len(src));cell=max(4,round(p['cell_size']));cols=math.ceil(w/cell);strength=clamp(p['strength']/100,0,1);contrast=clamp(p['contrast']/100,0,1);luma=clamp(p['luminance']/100,0,1);huev=clamp(p['hue']/100,0,1);inv=clamp(p['inversion']/100,0,1);carrier=clamp(p['carrier']/100,0,1);wamp=max(0,p['wobble'])*strength;wscale=max(2,p['wobble_scale']);pbias=clamp(p['payload_wobble']/100,0,1);octaves=max(1,min(7,round(p['octaves'])));pers=clamp(p['persistence'],.1,.95);lac=clamp(p['lacunarity'],1.1,4);ang=math.radians(p['orientation']);nx=-math.sin(ang);ny=math.cos(ang)
 for y in range(h):
  for x in range(w):
   cx=x//cell;cy=y//cell;i0=cy*cols+cx;bit=bits[i0%len(bits)];sign=1 if bit else -1;n=fbm(x/wscale,y/wscale,p['seed']+i0*3,octaves,pers,lac);wb=n*wamp*(1+sign*.45*pbias);sx=x+nx*wb;sy=y+ny*wb
   if p['style']=='surreal':
    n2=fbm(x/(wscale*1.7),y/(wscale*1.7),p['seed']+991,octaves,pers,lac);sx+=math.cos(ang)*n2*wamp*.65;sy+=math.sin(ang)*n2*wamp*.65
   elif p['style']=='cubist':
    q=max(2,cell*.18*strength)
    if q>2.1:sx=round(sx/q)*q;sy=round(sy/q)*q
   r,g,b,a=sample(src,w,h,sx,sy);i=(y*w+x)*4
   if a==0:out[i:i+4]=bytes((r,g,b,a));continue
   gt=gate(p['style'],x,y,cx,cy,p,n,sign);st=strength*gt;y0=lum(r,g,b);cg=1+sign*contrast*st*.42;r=y0+(r-y0)*cg;g=y0+(g-y0)*cg;b=y0+(b-y0)*cg;bias=sign*(2+18*carrier)*strength*(.45+.55*gt)+sign*10*luma*st;r+=bias;g+=bias;b+=bias
   if inv:
    t=inv*st*(.42 if bit else .13);r=lerp(r,255-r,t);g=lerp(g,255-g,t);b=lerp(b,255-b,t)
   r,g,b=hue(r,g,b,sign*huev*st*.55+n*huev*strength*.22)
   if p['style']=='stipple' and gt>.7:
    m=14+48*strength
    if bit:r-=m;g-=m;b-=m
    else:r+=m*.72;g+=m*.72;b+=m*.72
   elif p['style']=='penskip' and gt>.7:
    target=238 if bit else 25;m=.08+.34*strength;r=lerp(r,target,m);g=lerp(g,target,m);b=lerp(b,target,m)
   elif p['style']=='engraving' and gt>.7:r-=12+42*strength;g-=12+42*strength;b-=12+42*strength
   out[i]=int(clamp(round(r),0,255));out[i+1]=int(clamp(round(g),0,255));out[i+2]=int(clamp(round(b),0,255));out[i+3]=a
 return bytes(out)
