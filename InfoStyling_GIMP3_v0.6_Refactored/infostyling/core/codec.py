import zlib
MAGIC=b'IS01';HEADER_BYTES=14;BLIND_MAGIC=b'ISB1';BLIND_HEADER_BYTES=20;SYNC=bytes([0xD3,0x91,0x5A,0xC7,0x2E,0x84,0xF1,0x6B]);G0=0x79;G1=0x5B;MEMORY=6
STYLE={'engraving':1,'impressionist':2,'cubist':3,'surreal':4,'penskip':5,'stipple':6,'fractal':7};STYLE_NAME={v:k for k,v in STYLE.items()}
def bytes_to_bits(a):return[(v>>b)&1 for v in a for b in range(7,-1,-1)]
def bits_to_bytes(bits,n=None):
 n=len(bits)//8 if n is None else n;out=bytearray(n)
 for i in range(n):
  v=0
  for b in range(8):v=v<<1|(1 if bits[i*8+b] else 0)
  out[i]=v
 return bytes(out)
SYNC_BITS=bytes_to_bits(SYNC)
def frame_bits(text):
 p=text.encode();a=MAGIC+bytes([1,0])+len(p).to_bytes(4,'big')+(zlib.crc32(p)&0xffffffff).to_bytes(4,'big')+p;return bytes_to_bits(a)
def packet(text,style='engraving',cell=16,seed=0):
 p=text.encode();return BLIND_MAGIC+bytes([3,STYLE.get(style,0),int(cell)&255,0])+len(p).to_bytes(4,'big')+(zlib.crc32(p)&0xffffffff).to_bytes(4,'big')+(int(seed)&0xffffffff).to_bytes(4,'big')+p
def header(a):
 if len(a)<BLIND_HEADER_BYTES or a[:4]!=BLIND_MAGIC or a[4]!=3:raise ValueError('Not ISB3')
 return{'version':3,'style':STYLE_NAME.get(a[5],'unknown'),'style_id':a[5],'blind_cell':a[6],'flags':a[7],'payload_length':int.from_bytes(a[8:12],'big'),'crc':int.from_bytes(a[12:16],'big'),'seed':int.from_bytes(a[16:20],'big')}
def parity(v):v^=v>>4;v^=v>>2;v^=v>>1;return v&1
def step(state,bit):
 r=((state<<1)|(1 if bit else 0))&127;return r&63,parity(r&G0),parity(r&G1)
def encode(bits):
 out=[];state=0
 for i in range(len(bits)+MEMORY):
  state,a,b=step(state,bits[i] if i<len(bits) else 0);out.extend((a,b))
 return out
def decode(coded,count,conf=None,end_zero=True):
 steps=min(count,len(coded)//2);inf=1e30;prev=[inf]*64;prev[0]=0.;back=[[0]*64 for _ in range(steps)];choice=[[0]*64 for _ in range(steps)]
 for t in range(steps):
  nxt=[inf]*64;r0=1 if coded[t*2] else 0;r1=1 if coded[t*2+1] else 0;w0=max(0,float(conf[t*2] if conf else 1));w1=max(0,float(conf[t*2+1] if conf else 1))
  for s in range(64):
   if prev[s]>=inf/2:continue
   for bit in(0,1):
    ns,a,b=step(s,bit);cost=prev[s]+(0 if a==r0 else w0)+(0 if b==r1 else w1)
    if cost<nxt[ns]:nxt[ns]=cost;back[t][ns]=s;choice[t][ns]=bit
  prev=nxt
 state=0 if end_zero else min(range(64),key=lambda s:prev[s]);out=[0]*steps
 for t in range(steps-1,-1,-1):out[t]=choice[t][state];state=back[t][state]
 return out
def v3_frame_bits(text,style='engraving',blind_cell=16,seed=0):return SYNC_BITS+encode(bytes_to_bits(packet(text,style,blind_cell,seed)))
def v3_frame_bit_length(n):return len(SYNC_BITS)+2*((BLIND_HEADER_BYTES+n)*8+MEMORY)
def sync(bits,pos=0):
 d=sum(bits[pos+i]!=SYNC_BITS[i] for i in range(len(SYNC_BITS)));di=sum(bits[pos+i]==SYNC_BITS[i] for i in range(len(SYNC_BITS)));return(min(d,di),di<d)
def block(bits,conf,start,nbytes,tail,end_zero,inv):
 count=nbytes*8+tail;n=count*2;c=[bits[start+i]^(1 if inv else 0) for i in range(n)];w=[conf[start+i] if conf else 1 for i in range(n)];return bits_to_bytes(decode(c,count,w,end_zero)[:count-tail],nbytes)
def decode_header(bits,conf=None,max_errors=14):
 d,inv=sync(bits)
 if d>max_errors:raise ValueError('ISB3 sync mismatch')
 return header(block(bits,conf,len(SYNC_BITS),BLIND_HEADER_BYTES,0,False,inv)),d,inv
def decode_bits(bits,conf=None,max_errors=14):
 cand=[]
 for pos in range(max(0,len(bits)-(len(SYNC_BITS)+BLIND_HEADER_BYTES*16)+1)):
  d,inv=sync(bits,pos)
  if d<=max_errors:cand.append((d,pos,inv))
 cand.sort();last=None
 for d,pos,inv in cand:
  try:
   start=pos+len(SYNC_BITS);h=header(block(bits,conf,start,BLIND_HEADER_BYTES,0,False,inv));n=h['payload_length']
   if n>1048576:continue
   total=BLIND_HEADER_BYTES+n;need=(total*8+MEMORY)*2
   if start+need>len(bits):continue
   raw=block(bits,conf,start,total,MEMORY,True,inv);meta=header(raw[:BLIND_HEADER_BYTES]);p=raw[BLIND_HEADER_BYTES:]
   if(zlib.crc32(p)&0xffffffff)!=meta['crc']:raise ValueError('ISB3 CRC mismatch')
   return{'text':p.decode(),'meta':meta,'sync_errors':d}
  except Exception as e:last=e
 raise ValueError(str(last) if last else 'No ISB3 synchronization found')
