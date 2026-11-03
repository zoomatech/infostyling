"use strict";
// Text compressor for hidden text. It predicts each bit from the text before it: contexts of the last 1 to 6
// characters, the current and previous word, and a long-match model that finds the last time the recent text
// appeared. The predictions are mixed and arithmetic-coded. The model is primed with a built-in English lexicon,
// so common words and phrases cost almost nothing even in short text. Encoder and decoder run the identical model.
const TBITS=21,TSIZE=1<<TBITS,TMASK=TSIZE-1,N=7,NI=N+2,MBITS=20;
// Lookup tables are rounded so that every JavaScript engine builds exactly the same values.
const ST=new Float32Array(4096);for(let i=0;i<4096;i++){const p=(i+.5)/4096;ST[i]=Math.round(Math.log(p/(1-p))*1024)/1024}
const SQ=new Float32Array(4096);for(let i=0;i<4096;i++)SQ[i]=Math.round(65536/(1+Math.exp(-((i-2048)/128))))/65536;
const squash=x=>{let i=Math.round(x*128)+2048;return SQ[i<0?0:i>4095?4095:i]};
const H=(a,b)=>(Math.imul(a^Math.imul(b,0x9E3779B1),0x2545F491)^(a>>>15))>>>0;
function Model(){this.t=new Uint16Array(TSIZE*N).fill(32768);this.n=new Uint8Array(TSIZE*N);this.w=new Float32Array(256*NI).fill(.25);
 this.apm=new Uint16Array(65536*33);for(let c=0;c<65536;c++)for(let j=0;j<33;j++)this.apm[c*33+j]=Math.round(1/(1+Math.exp(-(j-16)/2))*65535);
 this.mt=new Int32Array(1<<MBITS);this.mm=new Uint16Array(64*2).fill(49152);this.buf=new Uint8Array(1<<16);this.pos=0;this.mp=0;this.ml=0;this.mexp=0;this.mi=0;
 this.h=new Uint32Array(N);this.idx=new Int32Array(N);this.x=new Float32Array(NI);this.c0=1;this.c4=0;this.c8=0;this.word=0;this.b2=0;this.bit=0;this.pr=.5;this.pm=.5;this.ai=0;this.aw=0;this.ctx()}
Model.prototype.ctx=function(){const c=this.c4,h=this.h;h[0]=0;h[1]=H(1,c&0xff);h[2]=H(2,c&0xffff);h[3]=H(3,c&0xffffff);h[4]=H(4,c);h[5]=H(5,H(c,this.c8));h[6]=H(H(6,this.word),this.b2)}
Model.prototype.p=function(){const c0=this.c0,x=this.x,w=this.w,wo=c0*NI;let dot=0;
 for(let i=0;i<N;i++){const j=i*TSIZE+((this.h[i]+Math.imul(c0,0x6F4F2A35))&TMASK);this.idx[i]=j;const s=ST[this.t[j]>>>4];x[i]=s;dot+=w[wo+i]*s}
 if(this.ml>0){const e=(this.buf[this.mp]>>(7-this.bit))&1;if(((this.buf[this.mp]|256)>>(8-this.bit))!==c0){this.ml=0;x[N]=0}else{this.mexp=e;this.mi=Math.min(this.ml,63)*2+e;const s=ST[this.mm[this.mi]>>>4];x[N]=e?s:-s}}else x[N]=0;
 x[N+1]=.25;dot+=w[wo+N]*x[N]+w[wo+N+1]*.25;this.pm=squash(dot);
 const s=Math.max(-7.999,Math.min(7.999,dot))*2+16,lo=Math.floor(s),fr=s-lo,a=((this.c4&0xff)<<8|c0)*33;this.ai=a+lo;this.aw=fr;
 const pa=(this.apm[a+lo]*(1-fr)+this.apm[a+lo+1]*fr)/65536;this.pr=Math.min(.9999,Math.max(.0001,(this.pm+3*pa)/4));return this.pr}
Model.prototype.update=function(bit){const t=this.t,n=this.n;for(let i=0;i<N;i++){const j=this.idx[i],k=n[j];t[j]+=((bit?65535:0)-t[j])/(k+1.6);if(k<60)n[j]=k+1}
 if(this.ml>0&&this.x[N]!==0){const m=this.mm,i=this.mi;m[i]+=(((bit===this.mexp)?65535:0)-m[i])/32}
 const err=bit-this.pm,w=this.w,wo=this.c0*NI,lr=.012;for(let i=0;i<NI;i++)w[wo+i]+=lr*err*this.x[i];
 const ap=this.apm,g=bit?65535:0;ap[this.ai]+=(g-ap[this.ai])*(1-this.aw)/40;ap[this.ai+1]+=(g-ap[this.ai+1])*this.aw/40;
 this.c0=this.c0<<1|bit;this.bit++;
 if(this.c0>=256){const c=this.c0&255;this.c8=((this.c8<<8)|(this.c4>>>24))>>>0;this.c4=(this.c4<<8|c)>>>0;this.c0=1;this.bit=0;
  if(this.pos>=this.buf.length){const nb=new Uint8Array(this.buf.length*2);nb.set(this.buf);this.buf=nb}this.buf[this.pos++]=c;
  if(this.ml>0){this.ml++;this.mp++}
  const hk=H(this.c4,this.c8&0xffff)>>>(32-MBITS);if(this.ml===0&&this.pos>=6){const p=this.mt[hk];if(p>0){let l=0;while(l<32&&p-1-l>=0&&this.buf[p-1-l]===this.buf[this.pos-1-l])l++;if(l>=6){this.ml=l;this.mp=p}}}
  this.mt[hk]=this.pos;
  const lc=c>=65&&c<=90?c+32:c;if((lc>=97&&lc<=122)||c===39||c>=128)this.word=H(this.word,lc);else if(this.word){this.b2=this.word;this.word=0}this.ctx()}}
Model.prototype.prime=function(bytes){for(const c of bytes)for(let b=7;b>=0;b--){this.p();this.update(c>>b&1)}}
Model.prototype.clone=function(){const m=Object.create(Model.prototype);for(const k in this){if(!Object.prototype.hasOwnProperty.call(this,k))continue;const v=this[k];m[k]=ArrayBuffer.isView(v)?v.slice():v}return m}
function encode(bytes,model){const out=[];let x1=0,x2=0xffffffff;let n=bytes.length;do{let b=n&127;n=Math.floor(n/128);out.push(n?b|128:b)}while(n);
 for(let i=0;i<bytes.length;i++){const c=bytes[i];for(let b=7;b>=0;b--){const bit=c>>b&1,p=model.p(),xm=x1+Math.floor((x2-x1)*(1-p));if(bit)x1=xm+1;else x2=xm;model.update(bit);
  while(((x1^x2)&0xff000000)===0){out.push(x2>>>24);x1=(x1<<8)>>>0;x2=((x2<<8)|255)>>>0}}}
 out.push(x1>>>24,(x1>>>16)&255,(x1>>>8)&255,x1&255);return Uint8Array.from(out)}
// Same as encode, but pauses every 64 KB so a panel can keep responding while a book is packed.
async function encodeAsync(bytes,model){const out=[];let x1=0,x2=0xffffffff;let n=bytes.length;do{let b=n&127;n=Math.floor(n/128);out.push(n?b|128:b)}while(n);
 for(let i=0;i<bytes.length;i++){if(i&&!(i&65535))await new Promise(r=>setTimeout(r,0));const c=bytes[i];for(let b=7;b>=0;b--){const bit=c>>b&1,p=model.p(),xm=x1+Math.floor((x2-x1)*(1-p));if(bit)x1=xm+1;else x2=xm;model.update(bit);
  while(((x1^x2)&0xff000000)===0){out.push(x2>>>24);x1=(x1<<8)>>>0;x2=((x2<<8)|255)>>>0}}}
 out.push(x1>>>24,(x1>>>16)&255,(x1>>>8)&255,x1&255);return Uint8Array.from(out)}
function decode(data,model){let pos=0,len=0,mul=1;for(;;){const b=data[pos++];len+=(b&127)*mul;mul*=128;if(!(b&128))break}
 const out=new Uint8Array(len);let x1=0,x2=0xffffffff,x=0;for(let i=0;i<4;i++)x=((x<<8)|(data[pos++]||0))>>>0;
 for(let i=0;i<len;i++){let c=0;for(let b=0;b<8;b++){const p=model.p(),xm=x1+Math.floor((x2-x1)*(1-p)),bit=x>xm?1:0;if(bit)x1=xm+1;else x2=xm;model.update(bit);c=c<<1|bit;
   while(((x1^x2)&0xff000000)===0){x1=(x1<<8)>>>0;x2=((x2<<8)|255)>>>0;x=((x<<8)|(data[pos++]||0))>>>0}}out[i]=c}return out}
module.exports={Model,encode,encodeAsync,decode};
