from . import codec
from .mathutil import hash2
PILOT=[1,1,0,0,1,0,1,0,0,1,1,0,1,1,1,0,1,0,1,1,0,0,1,1,0,0,0,1,1,1,1,0,1,0,0,0,1,0,1,1,1,0,1,0,0,1,0,1,1]
def morton_decode(n):
 x=y=b=0
 while n:x|=(n&1)<<b;n>>=1;y|=(n&1)<<b;n>>=1;b+=1
 return x,y
def morton_encode(x,y):
 n=s=0
 while x or y:n|=(x&1)<<s;s+=1;n|=(y&1)<<s;s+=1;x>>=1;y>>=1
 return n
def data_rel(k):
 block=k//256;i=k&255;perm=(i*73+19)&255;x,y=morton_decode(block*256+perm);return 5+x,5+y
def tile_period(n):
 m=0
 for k in range(n):x,y=data_rel(k);m=max(m,x,y)
 return max(12,5+m)
def capacity(w,h,cell):
 c=max(8,round(cell or 16));limit=min(w//c,h//c)
 if limit<12:return 0
 lo=0;hi=65535
 while lo<hi:
  m=(lo+hi+1)//2
  if tile_period(codec.v3_frame_bit_length(m))<=limit:lo=m
  else:hi=m-1
 return lo
def cell_bit(cx,cy,bits,period,seed):
 x=cx%period;y=cy%period
 if x<=6 and y<=6:return PILOT[y*7+x]
 if x>=8 and y>=8:
  raw=morton_encode(x-8,y-8);block=raw//256;perm=raw&255;i=((perm-19)*249)&255;k=block*256+i
  if k<len(bits):return bits[k]
 return 1 if hash2(cx,cy,int(seed)^0x33c0ffee)>=.5 else 0
