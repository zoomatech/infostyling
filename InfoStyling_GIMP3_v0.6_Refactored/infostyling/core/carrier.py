from . import codec,layout
from .mathutil import clamp,lum
def pattern(x,y,c):
 import math;u=(x+.5)/c;v=(y+.5)/c;t=math.pi*2;return(math.sin(t*(u+2*v+.137))+.72*math.sin(t*(2*u-v+.371))+.48*math.cos(t*(u-v+.719)))/2.2
def apply(src,w,h,bits,p):
 out=bytearray(src);cell=max(8,round(p['blind_cell']));amp=3+19*clamp(p['blind_strength']/100.,0,1);period=layout.tile_period(len(bits))
 for y in range(h):
  for x in range(w):
   cx=x//cell;cy=y//cell;s=1 if layout.cell_bit(cx,cy,bits,period,p['seed']) else -1;i=(y*w+x)*4
   if out[i+3]<20:continue
   d=s*amp*pattern(x-cx*cell,y-cy*cell,cell);out[i]=int(clamp(round(out[i]+d),0,255));out[i+1]=int(clamp(round(out[i+1]+d),0,255));out[i+2]=int(clamp(round(out[i+2]+d),0,255))
 return bytes(out),period
def cluster(v):
 if not v:return[],0,0
 a=min(v);b=max(v)
 for _ in range(10):
  x=[];y=[]
  for q in v:(x if abs(q-a)<=abs(q-b) else y).append(q)
  if x:a=sum(x)/len(x)
  if y:b=sum(y)/len(y)
 lo=min(a,b);hi=max(a,b);t=(lo+hi)/2;return[1 if q>=t else 0 for q in v],hi-lo,t
def detrend(s):
 if not s:return 0
 sy=sum(q[0] for q in s);sp=sum(q[1] for q in s);xx=sum(q[2]*q[2] for q in s);zz=sum(q[3]*q[3] for q in s);yx=sum(q[0]*q[2] for q in s);px=sum(q[1]*q[2] for q in s);yz=sum(q[0]*q[3] for q in s);pz=sum(q[1]*q[3] for q in s);n=len(s);my=sy/n;mp=sp/n;by=yx/xx if xx else 0;bp=px/xx if xx else 0;cy=yz/zz if zz else 0;cp=pz/zz if zz else 0;num=den=0
 for y,p,x,z in s:
  yr=y-my-by*x-cy*z;pr=p-mp-bp*x-cp*z;num+=yr*pr;den+=pr*pr
 return num/den if den else 0
def cell_corr(src,w,h,cell,x0,y0,N):
 s=[]
 for sy in range(N):
  for sx in range(N):
   lx=min(cell-1,max(0,round((sx+.5)*cell/N-.5)));ly=min(cell-1,max(0,round((sy+.5)*cell/N-.5)));x=x0+lx;y=y0+ly
   if x>=w or y>=h:continue
   i=(y*w+x)*4
   if src[i+3]<20:continue
   s.append((lum(src[i],src[i+1],src[i+2]),pattern(lx,ly,cell),(sx-(N-1)/2)/N,(sy-(N-1)/2)/N))
 return detrend(s)
def extract(src,w,h,cell,ox=0,oy=0):
 cell=max(8,round(cell));ox=max(0,round(ox));oy=max(0,round(oy));cols=(w-ox)//cell;rows=(h-oy)//cell
 if cols<1 or rows<1:return{'bits':[],'values':[],'separation':0,'threshold':0,'cols':cols,'rows':rows}
 v=[cell_corr(src,w,h,cell,ox+x*cell,oy+y*cell,7) for y in range(rows) for x in range(cols)];bits,sep,t=cluster(v);return{'bits':bits,'values':v,'separation':sep,'threshold':t,'cols':cols,'rows':rows,'cell':cell,'ox':ox,'oy':oy}
def bit(g,x,y):return g['bits'][y*g['cols']+x] if 0<=x<g['cols'] and 0<=y<g['rows'] else None
def conf(g,x,y):return abs(g['values'][y*g['cols']+x]-g['threshold']) if 0<=x<g['cols'] and 0<=y<g['rows'] else 0
def roff(x,y,o):return(-y,x) if o%4==1 else(-x,-y) if o%4==2 else(y,-x) if o%4==3 else(x,y)
def pdist(g,ax,ay,o):
 d=0
 for y in range(-3,4):
  for x in range(-3,4):
   rx,ry=roff(x,y,o);b=bit(g,ax+rx,ay+ry)
   if b is None:return 999
   d+=b!=layout.PILOT[(y+3)*7+x+3]
 return d
def pilots(g,maxerr=10):
 out=[]
 for y in range(3,g['rows']-3):
  for x in range(3,g['cols']-3):
   for o in range(4):
    d=pdist(g,x,y,o)
    if d<=maxerr:out.append((d,x,y,o))
 return sorted(out)
def read(g,a,count,partial=False):
 d,ax,ay,o=a;bits=[0]*count;cf=[0.]*count
 for k in range(count):
  x,y=layout.data_rel(k);x,y=roff(x,y,o);b=bit(g,ax+x,ay+y)
  if b is None:
   if not partial:return None
   continue
  bits[k]=b;cf[k]=conf(g,ax+x,ay+y)
 return bits,cf
def combine(copies,count):
 bits=[0]*count;cf=[0.]*count
 for i in range(count):
  score=total=0.
  for b,c,q in copies:
   w=max(0,c[i] if i<len(c) else 0)*q
   if not w:continue
   score+=(1 if b[i] else -1)*w;total+=w
  bits[i]=1 if score>=0 else 0;cf[i]=total
 for i in range(min(len(codec.SYNC_BITS),count)):
  bits[i]=codec.SYNC_BITS[i]
  if not cf[i]:cf[i]=.001
 return bits,cf
def decode_grid(g):
 pp=pilots(g)
 if not pp:return None
 cand=[]
 for a in pp[:72]:
  r=read(g,a,len(codec.SYNC_BITS)+codec.BLIND_HEADER_BYTES*16)
  if not r:continue
  try:h,_,_=codec.decode_header(*r)
  except ValueError:continue
  if h['payload_length']>65535:continue
  total=codec.v3_frame_bit_length(h['payload_length']);r=read(g,a,total)
  if not r:continue
  try:return{**codec.decode_bits(*r),'anchor':a,'copies':1,'pilot_errors':a[0]}
  except ValueError:cand.append((a,h,r,total,max(.2,(11-a[0])/11)))
 groups={}
 for a,h,r,total,q in cand:groups.setdefault((h['payload_length'],h['crc'],h['style_id'],h['seed']),[]).append((a,r,total,q))
 for group in groups.values():
  if len(group)<2:continue
  n=group[0][2]
  if any(x[2]!=n for x in group):continue
  z=combine([(x[1][0],x[1][1],x[3]) for x in group],n)
  try:return{**codec.decode_bits(*z,max_errors=18),'anchor':group[0][0],'copies':len(group),'pilot_errors':group[0][0][0]}
  except ValueError:pass
 hn=len(codec.SYNC_BITS)+codec.BLIND_HEADER_BYTES*16
 for o in range(4):
  a=[x for x in pp if x[3]==o and x[0]<=7][:24]
  if not a:continue
  hp=[]
  for x in a:
   r=read(g,x,hn,True);hp.append((r[0],r[1],max(.15,(8-x[0])/8)))
  hz=combine(hp,hn)
  try:h,_,_=codec.decode_header(*hz,max_errors=0)
  except ValueError:continue
  total=codec.v3_frame_bit_length(h['payload_length']);fp=[]
  for x in a:
   r=read(g,x,total,True);fp.append((r[0],r[1],max(.15,(8-x[0])/8)))
  try:return{**codec.decode_bits(*combine(fp,total),max_errors=0),'anchor':a[0],'copies':len(a),'pilot_errors':a[0][0],'partial_combined':True}
  except ValueError:pass
 return None
def cells(hint):
 out=[]
 for v in[hint,8,10,12,14,16,18,20,22,24,28,32,36,40,48]:
  v=max(6,min(64,round(v)))
  if v not in out:out.append(v)
 return out
def score(src,w,h,cell,ox,oy):
 cell=max(8,round(cell));cols=(w-ox)//cell;rows=(h-oy)//cell
 if cols<8 or rows<8:return 0
 total=0
 for y in range(5):
  for x in range(5):
   cx=min(cols-1,max(0,round((x+.5)*cols/5-.5)));cy=min(rows-1,max(0,round((y+.5)*rows/5-.5)));total+=abs(cell_corr(src,w,h,cell,ox+cx*cell,oy+cy*cell,5))
 return total/25
def decode(src,w,h,hint=16,deep=False):
 cc=cells(hint)
 for cell in cc:
  g=extract(src,w,h,cell);r=decode_grid(g)
  if r:r.update(cell=cell,offx=0,offy=0);return r
 if not deep:raise ValueError('No valid ISB3 tile recovered')
 ordered=[max(6,round(hint))]+[x for x in cc if x!=max(6,round(hint))]
 for cell in ordered:
  st=max(1,cell//4);coarse=sorted(((score(src,w,h,cell,x,y),x,y) for y in range(0,cell,st) for x in range(0,cell,st) if x or y),reverse=True);fine={};rad=max(1,cell//4)
  for _,qx,qy in coarse[:5]:
   for y in range(max(0,qy-rad),min(cell,qy+rad+1)):
    for x in range(max(0,qx-rad),min(cell,qx+rad+1)):fine.setdefault((x,y),score(src,w,h,cell,x,y))
  for(x,y),_ in sorted(fine.items(),key=lambda z:z[1],reverse=True)[:14]:
   g=extract(src,w,h,cell,x,y);r=decode_grid(g)
   if r:r.update(cell=cell,offx=x,offy=y);return r
 raise ValueError('No valid ISB3 tile recovered')
