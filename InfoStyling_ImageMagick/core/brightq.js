"use strict";
// Shareable brightness channel for the Invisible look. Bits are stored as faint brightness patterns lined up
// with JPEG's own 8×8 blocks, so a JPEG save or a Facebook recompress keeps them. Each 8×8 block carries
// K bits, one per low-frequency pattern: the pattern's strength is nudged to an even or odd step (dithered
// quantization). Red, green and blue move together, so colour is unchanged. Bits are error-corrected,
// scattered in a fixed scrambled order and repeated. Images longer than 2048 px are coded on a 2048 px grid,
// because Facebook resizes them to that.
const pako=require("../lib/pako.min.js"),codec=require("./codec.js"),P=require("./pack.js");
const MAGIC=[0x49,0x53,0x51,0x31],HEADER=17,SIDE=2048,K=6,SEED=0x51b7c3a5,TAIL=6,LO=2,HI=253;
const ZZ=[[0,1],[1,0],[2,0],[1,1],[0,2],[0,3]];
// Strength steps tried by the decoder; the encoder uses MODE.
const MODES=[{step:24,rep:2},{step:20,rep:1},{step:30,rep:3}],MODE=MODES[0];
const BASIS=ZZ.map(([u,v])=>{const b=new Float64Array(64),cu=u?.5:Math.SQRT1_2*.5,cv=v?.5:Math.SQRT1_2*.5;for(let y=0;y<8;y++)for(let x=0;x<8;x++)b[y*8+x]=cu*cv*Math.cos(Math.PI*(2*y+1)*u/16)*Math.cos(Math.PI*(2*x+1)*v/16);return b});
function rng(seed){let a=seed>>>0;return()=>{a=(a+0x6D2B79F5)>>>0;let t=a;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return((t^t>>>14)>>>0)/4294967296}}
function grid(w,h){const L=Math.max(w,h);if(L<=SIDE)return{gw:w,gh:h,scaled:false};const s=SIDE/L;return{gw:Math.max(8,Math.round(w*s)),gh:Math.max(8,Math.round(h*s)),scaled:true}}
function slotCount(w,h){const g=grid(w,h);return Math.floor(g.gw/8)*Math.floor(g.gh/8)*K}
function capacityBytes(w,h,mode=MODE){const coded=Math.floor(slotCount(w,h)/mode.rep);return Math.max(0,Math.floor((Math.floor(coded/2)-TAIL)/8)-HEADER)}
// Fixed scrambled slot order and per-slot dither, the same for encoder and decoder.
const cache={};function layout(n){if(cache.n===n)return cache;const r=rng(SEED),perm=new Uint32Array(n),dith=new Float32Array(n);for(let i=0;i<n;i++)perm[i]=i;for(let i=n-1;i>0;i--){const j=Math.floor(r()*(i+1)),t=perm[i];perm[i]=perm[j];perm[j]=t}for(let i=0;i<n;i++)dith[i]=r();cache.n=n;cache.perm=perm;cache.dith=dith;return cache}
// Brightness (Rec. 601 luma) of the working grid; box-averaged when the image is scaled to 2048.
function luma(src,w,h,n,g){const Y=new Float64Array(w*h);for(let p=0,i=0;p<w*h;p++,i+=n)Y[p]=n>2?.299*src[i]+.587*src[i+1]+.114*src[i+2]:src[i];if(!g.scaled)return Y;const out=new Float64Array(g.gw*g.gh);for(let y=0;y<g.gh;y++){const y0=Math.floor(y*h/g.gh),y1=Math.max(y0+1,Math.floor((y+1)*h/g.gh));for(let x=0;x<g.gw;x++){const x0=Math.floor(x*w/g.gw),x1=Math.max(x0+1,Math.floor((x+1)*w/g.gw));let s=0,c=0;for(let yy=y0;yy<y1;yy++)for(let xx=x0;xx<x1;xx++){s+=Y[yy*w+xx];c++}out[y*g.gw+x]=s/c}}return out}
function coeffs(Y,gw,bw,bh){const C=new Float64Array(bw*bh*K);for(let by=0;by<bh;by++)for(let bx=0;bx<bw;bx++){const o=(by*bw+bx)*K;for(let k=0;k<K;k++){const b=BASIS[k];let s=0;for(let y=0;y<8;y++){const row=(by*8+y)*gw+bx*8;for(let x=0;x<8;x++)s+=b[y*8+x]*Y[row+x]}C[o+k]=s}}return C}
function header(method,rawLen,data){const h=new Uint8Array(HEADER);h.set(MAGIC);h[4]=method;const put=(v,o)=>{h[o]=v>>>24&255;h[o+1]=v>>>16&255;h[o+2]=v>>>8&255;h[o+3]=v&255};put(rawLen,5);put(data.length,9);put(codec.crc32(data),13);return h}
const r32=(a,o)=>((a[o]<<24)>>>0)+(a[o+1]<<16)+(a[o+2]<<8)+a[o+3];
function bits(bytes){const out=new Uint8Array(bytes.length*8);for(let i=0;i<out.length;i++)out[i]=bytes[i>>3]>>(7-(i&7))&1;return out}
// Hides text; returns new pixels. Throws when the text does not fit.
function embed(src,w,h,n,text,mode=MODE){const g=grid(w,h),bw=Math.floor(g.gw/8),bh=Math.floor(g.gh/8),N=bw*bh*K,cap=capacityBytes(w,h,mode),q=codec.robustPayload(text);
 if(q.bytes.length>cap)throw new Error(`The text packs to ${q.bytes.length} bytes; this image holds ${cap} bytes when shared.`);
 const frame=new Uint8Array(HEADER+q.bytes.length);frame.set(header(q.method,q.rawLength,q.bytes));frame.set(q.bytes,HEADER);const coded=codec.convEncode(bits(frame)),L=layout(N),M=coded.length;
 const target=new Float64Array(N).fill(NaN),out=new Uint8Array(src),{step}=mode;let C=coeffs(luma(out,w,h,n,g),g.gw,bw,bh);
 for(let r=0;r<mode.rep;r++)for(let j=0;j<M;j++){const s=L.perm[j*mode.rep+r],d=L.dith[s]*2*step,b=coded[j],v=C[s]-d-b*step;target[s]=Math.round(v/(2*step))*2*step+d+b*step}
 // A few passes: push each pattern to its target, keep blocks inside 2..253 by shifting their average, re-measure.
 for(let pass=0;pass<4;pass++){const Y=luma(out,w,h,n,g),D=new Float64Array(g.gw*g.gh);C=coeffs(Y,g.gw,bw,bh);let moved=0;
  for(let by=0;by<bh;by++)for(let bx=0;bx<bw;bx++){const o=(by*bw+bx)*K,blk=new Float64Array(64);let any=false;for(let k=0;k<K;k++){const t=target[o+k];if(t!==t)continue;const dc=t-C[o+k];if(Math.abs(dc)<.25)continue;any=true;moved++;const b=BASIS[k];for(let i=0;i<64;i++)blk[i]+=dc*b[i]}if(!any)continue;
   let mx=-1e9,mn=1e9;for(let y=0;y<8;y++)for(let x=0;x<8;x++){const v=Y[(by*8+y)*g.gw+bx*8+x]+blk[y*8+x];if(v>mx)mx=v;if(v<mn)mn=v}const shift=mx>HI&&mn-(mx-HI)>=LO?HI-mx:mn<LO&&mx+(LO-mn)<=HI?LO-mn:0;
   for(let y=0;y<8;y++)for(let x=0;x<8;x++)D[(by*8+y)*g.gw+bx*8+x]=blk[y*8+x]+shift}
  if(!moved)break;apply(out,w,h,n,g,D)}
 return{pixels:out,storedBytes:q.bytes.length,rawBytes:q.rawLength,capacity:cap,mode}}
// Adds a brightness change to R, G and B; bilinear upscale from the 2048 grid when scaled.
function apply(out,w,h,n,g,D){for(let y=0;y<h;y++){let fy,y0,y1;if(g.scaled){fy=Math.min(g.gh-1,Math.max(0,(y+.5)*g.gh/h-.5));y0=Math.floor(fy);y1=Math.min(g.gh-1,y0+1);fy-=y0}for(let x=0;x<w;x++){let d;if(!g.scaled)d=D[y*w+x];else{let fx=Math.min(g.gw-1,Math.max(0,(x+.5)*g.gw/w-.5));const x0=Math.floor(fx),x1=Math.min(g.gw-1,x0+1);fx-=x0;d=(D[y0*g.gw+x0]*(1-fx)+D[y0*g.gw+x1]*fx)*(1-fy)+(D[y1*g.gw+x0]*(1-fx)+D[y1*g.gw+x1]*fx)*fy}if(!d)continue;const i=(y*w+x)*n;for(let c=0;c<Math.min(3,n);c++){const v=Math.round(out[i+c]+d);out[i+c]=v<0?0:v>255?255:v}}}}
function soft(C,L,step,N){const s=new Float32Array(N);for(let i=0;i<N;i++){const r=(C[i]-L.dith[i]*2*step)/step,k=Math.round(r);s[i]=((k&1)?1:-1)*(.5-Math.abs(r-k))}return s}
function readCoded(sv,L,M,rep){const b=new Uint8Array(M),c=new Float32Array(M);for(let j=0;j<M;j++){let t=0;for(let r=0;r<rep;r++)t+=sv[L.perm[j*rep+r]];b[j]=t>=0?1:0;c[j]=Math.abs(t)}return{b,c}}
// Reads the text back, or returns null when no channel is found.
function extract(src,w,h,n){const g=grid(w,h),bw=Math.floor(g.gw/8),bh=Math.floor(g.gh/8),N=bw*bh*K;if(bw<4||bh<4)return null;const L=layout(N),C=coeffs(luma(src,w,h,n,g),g.gw,bw,bh);
 for(const mode of MODES){const sv=soft(C,L,mode.step,N),slots=Math.floor(N/mode.rep),hb=HEADER*8;if(slots<2*(hb+TAIL))continue;
  let r=readCoded(sv,L,(hb+TAIL)*2,mode.rep);const hd=bitsToBytes(codec.convDecode(r.b,hb+TAIL,r.c,false).slice(0,hb),HEADER);if(MAGIC.some((v,i)=>hd[i]!==v))continue;
  const len=r32(hd,9),rawLen=r32(hd,5),crc=r32(hd,13),count=(HEADER+len)*8+TAIL,M=count*2;if(len>capacityBytes(w,h,mode)||M*mode.rep>N)continue;
  // Slots were filled with the whole frame's code length, so re-read with the real length.
  r=readCoded(sv,L,M,mode.rep);const all=bitsToBytes(codec.convDecode(r.b,count,r.c,true).slice(0,count-TAIL),HEADER+len),data=all.slice(HEADER);if(codec.crc32(data)!==crc)continue;
  const raw=P.unpack(all[4]&3,data);if(raw.length!==rawLen)continue;return{text:codec.utf8Decode(raw),rawBytes:raw.length,storedBytes:len,mode,carrier:"brightness"}}
 return null}
function bitsToBytes(b,n){const out=new Uint8Array(n);for(let i=0;i<n*8&&i<b.length;i++)if(b[i])out[i>>3]|=1<<(7-(i&7));return out}
// Bits a stored payload of len bytes occupies: header, error-correction code and repeats.
const codedBits=len=>((HEADER+len)*8+TAIL)*2*MODE.rep;
module.exports={embed,extract,capacityBytes,slotCount,codedBits,MODE,MODES};
