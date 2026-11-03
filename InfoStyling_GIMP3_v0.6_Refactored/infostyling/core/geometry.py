import math
from .mathutil import clamp,lerp
def solve(A,b):
 n=len(b);M=[r[:]+[b[i]] for i,r in enumerate(A)]
 for c in range(n):
  p=max(range(c,n),key=lambda r:abs(M[r][c]))
  if abs(M[p][c])<1e-12:raise ValueError('Degenerate quadrilateral')
  M[c],M[p]=M[p],M[c];d=M[c][c];M[c]=[v/d for v in M[c]]
  for r in range(n):
   if r==c:continue
   f=M[r][c];M[r]=[M[r][j]-f*M[c][j] for j in range(n+1)]
 return[r[n] for r in M]
def homography(w,h,q):
 src=((0,0),(w-1,0),(w-1,h-1),(0,h-1));A=[];b=[]
 for(x,y),(X,Y) in zip(src,q):A+=[[x,y,1,0,0,0,-x*X,-y*X],[0,0,0,x,y,1,-x*Y,-y*Y]];b+=[X,Y]
 z=solve(A,b);return z+[1]
def bilinear(src,w,h,x,y,ch):
 if x<0 or y<0 or x>w-1 or y>h-1:return 0 if ch==3 else 127
 x0=math.floor(x);y0=math.floor(y);x1=min(w-1,x0+1);y1=min(h-1,y0+1);tx=x-x0;ty=y-y0;a=src[(y0*w+x0)*4+ch];b=src[(y0*w+x1)*4+ch];d=src[(y1*w+x0)*4+ch];e=src[(y1*w+x1)*4+ch];return lerp(lerp(a,b,tx),lerp(d,e,tx),ty)
def warp(src,w,h,nw,nh,mapfn):
 out=bytearray(nw*nh*4)
 for y in range(nh):
  for x in range(nw):
   sx,sy=mapfn(x,y);i=(y*nw+x)*4
   for ch in range(4):out[i+ch]=int(clamp(round(bilinear(src,w,h,sx,sy,ch)),0,255))
 return bytes(out),nw,nh
def rectify(src,w,h,q,target_w=0,target_h=0):
 dist=lambda a,b:math.hypot(a[0]-b[0],a[1]-b[1]);nw=max(64,round(target_w or(dist(q[0],q[1])+dist(q[3],q[2]))/2));nh=max(64,round(target_h or(dist(q[0],q[3])+dist(q[1],q[2]))/2));H=homography(nw,nh,q)
 return warp(src,w,h,nw,nh,lambda x,y:((H[0]*x+H[1]*y+H[2])/(H[6]*x+H[7]*y+1),(H[3]*x+H[4]*y+H[5])/(H[6]*x+H[7]*y+1)))
def rotate(src,w,h,deg):
 a=math.radians(deg);ca=math.cos(a);sa=math.sin(a);nw=max(1,math.ceil(abs(w*ca)+abs(h*sa)));nh=max(1,math.ceil(abs(w*sa)+abs(h*ca)));cx=(w-1)/2;cy=(h-1)/2;ox=(nw-1)/2;oy=(nh-1)/2
 return warp(src,w,h,nw,nh,lambda x,y:(ca*(x-ox)+sa*(y-oy)+cx,-sa*(x-ox)+ca*(y-oy)+cy))
def undistort(src,w,h,k1=0.,k2=0.):
 if abs(k1)<1e-10 and abs(k2)<1e-10:return src,w,h
 cx=(w-1)/2;cy=(h-1)/2;s=max(cx,cy)
 return warp(src,w,h,w,h,lambda x,y:_radial(x,y,cx,cy,s,k1,k2))
def _radial(x,y,cx,cy,s,k1,k2):
 nx=(x-cx)/s;ny=(y-cy)/s;r2=nx*nx+ny*ny;f=1+k1*r2+k2*r2*r2;return cx+nx*f*s,cy+ny*f*s
