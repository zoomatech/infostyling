import math
def clamp(v,a,b):return a if v<a else b if v>b else v
def lerp(a,b,t):return a+(b-a)*t
def smooth(t):return t*t*(3-2*t)
def fract(x):return x-math.floor(x)
def hash2(x,y,seed):
 n=((int(x)*374761393)+(int(y)*668265263)+(int(seed)*1442695041))&0xffffffff;n^=n>>13;n=n*1274126177&0xffffffff;n^=n>>16;return(n&0xffffffff)/4294967295.
def noise(x,y,seed):
 xi=math.floor(x);yi=math.floor(y);tx=smooth(x-xi);ty=smooth(y-yi);a=hash2(xi,yi,seed);b=hash2(xi+1,yi,seed);c=hash2(xi,yi+1,seed);d=hash2(xi+1,yi+1,seed);return lerp(lerp(a,b,tx),lerp(c,d,tx),ty)*2-1
def fbm(x,y,seed,octaves,persistence,lacunarity):
 amp=freq=1.;total=norm=0.
 for i in range(int(octaves)):total+=noise(x*freq,y*freq,seed+i*1013)*amp;norm+=amp;amp*=persistence;freq*=lacunarity
 return total/norm if norm else 0.
def lum(r,g,b):return .2126*r+.7152*g+.0722*b
def hue(r,g,b,a):
 if abs(a)<1e-8:return r,g,b
 ca=math.cos(a);sa=math.sin(a);y=.299*r+.587*g+.114*b;i=.596*r-.274*g-.322*b;q=.211*r-.523*g+.312*b;ii=i*ca-q*sa;qq=i*sa+q*ca;return clamp(y+.956*ii+.621*qq,0,255),clamp(y-.272*ii-.647*qq,0,255),clamp(y-1.106*ii+1.703*qq,0,255)
def sample(src,w,h,x,y):
 x=int(clamp(round(x),0,w-1));y=int(clamp(round(y),0,h-1));i=(y*w+x)*4;return src[i],src[i+1],src[i+2],src[i+3]
