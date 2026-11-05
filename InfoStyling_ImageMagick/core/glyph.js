"use strict";
// Glyph hatch carrier, after Xerox DataGlyphs: the image is redrawn as one diagonal ink stroke per cell.
// A stroke leaning "/" is a 1 bit and "\" is a 0 bit; stroke weight and ink colour follow the photo.
// Uses the same ISB3 frame and tile layout as the brightness carrier, so decodeGrid reads it unchanged.
const {clamp,luminance}=require("./math.js"),{tilePeriod,cellBit}=require("./layout.js"),{clusterBits,decodeGrid}=require("./carrier.js");
const PAPER=[246,241,229];
function cellStats(src,w,h,n,x0,y0,c){let r=0,g=0,b=0,k=0;for(let y=y0;y<Math.min(h,y0+c);y++)for(let x=x0;x<Math.min(w,x0+c);x++){const i=(y*w+x)*n;r+=src[i];g+=src[i+1]??src[i];b+=src[i+2]??src[i];k++}return k?[r/k,g/k,b/k]:[255,255,255]}
function glyphCapacityCells(w,h,cell){return Math.min(Math.floor(w/cell),Math.floor(h/cell))}
function renderGlyphs(src,w,h,n,bits,p={}){const c=Math.max(6,Math.round(p.glyphCell||12)),period=tilePeriod(bits.length),out=new Uint8Array(src.length),inset=.14*c,half=c/2,weight=clamp((p.glyphWeight==null?60:p.glyphWeight)/100,0,1);
 for(let cy=0;cy*c<h;cy++)for(let cx=0;cx*c<w;cx++){const x0=cx*c,y0=cy*c,col=cellStats(src,w,h,n,x0,y0,c),L=luminance(col[0],col[1],col[2])/255,bit=cellBit(cx,cy,bits,period,p.seed),
  t=c*(.055+(.06+.22*weight)*(1-L)),ink=col.map(v=>v*.42*(1-.5*L));
  for(let y=y0;y<Math.min(h,y0+c);y++)for(let x=x0;x<Math.min(w,x0+c);x++){const u=x-x0+.5-half,v=y-y0+.5-half,along=bit?(u-v)/Math.SQRT2:(u+v)/Math.SQRT2,across=bit?(u+v)/Math.SQRT2:(u-v)/Math.SQRT2,lim=half*Math.SQRT2-inset,
   d=Math.max(Math.abs(across)-t,Math.abs(along)-lim),a=clamp(.5-d,0,1),i=(y*w+x)*n;
   for(let k=0;k<Math.min(3,n);k++)out[i+k]=Math.round(PAPER[k]*(1-a)+ink[k]*a);if(n>3)out[i+3]=src[i+3]}}
 return{pixels:out,cell:c,period}}
function lumAt(src,w,h,n,x,y){const xi=clamp(Math.round(x),0,w-1),yi=clamp(Math.round(y),0,h-1),i=(yi*w+xi)*n;return luminance(src[i],src[i+1]??src[i],src[i+2]??src[i])}
// Positive when the "/" diagonal is darker than the "\" diagonal.
function lean(src,w,h,n,c,x0,y0){let s=0,b=0;for(const f of[.22,.3,.38,.62,.7,.78]){s+=lumAt(src,w,h,n,x0+f*c-.5,y0+(1-f)*c-.5);b+=lumAt(src,w,h,n,x0+f*c-.5,y0+f*c-.5)}return(b-s)/6}
function score(src,w,h,n,c,ox,oy,kmax=1e9){const cols=Math.floor((w-ox)/c),rows=Math.floor((h-oy)/c);if(cols<12||rows<12)return 0;const kx=Math.min(cols,kmax),ky=Math.min(rows,kmax);let s=0;const G=Math.min(12,kx);for(let j=0;j<G;j++)for(let i=0;i<G;i++){const cx=Math.round((i+.5)*kx/G-.5),cy=Math.round((j+.5)*ky/G-.5);s+=Math.abs(lean(src,w,h,n,c,ox+cx*c,oy+cy*c))}return s/(G*G)}
function grid(src,w,h,n,c,ox=0,oy=0){const cols=Math.floor((w-ox)/c),rows=Math.floor((h-oy)/c);if(cols<12||rows<12)return null;const values=new Float32Array(cols*rows);let k=0;for(let y=0;y<rows;y++)for(let x=0;x<cols;x++)values[k++]=lean(src,w,h,n,c,ox+x*c,oy+y*c);return{...clusterBits(values),values,cols,rows,cell:c,ox,oy}}
function bestOffset(src,w,h,n,c,kmax,st){let b={s:-1,x:0,y:0};for(let y=0;y<c-.01;y+=st)for(let x=0;x<c-.01;x+=st){const v=score(src,w,h,n,c,x,y,kmax);if(v>b.s)b={s:v,x,y}}return b}
function nudge(src,w,h,n,q,kmax){let b={...q,s:score(src,w,h,n,q.c,q.x,q.y,kmax)};for(let dy=-1.5;dy<=1.5;dy+=.5)for(let dx=-1.5;dx<=1.5;dx+=.5){const x=q.x+dx,y=q.y+dy;if(x<0||y<0)continue;const v=score(src,w,h,n,q.c,x,y,kmax);if(v>b.s)b={...q,x,y,s:v}}return b}
function refine(src,w,h,n,q,step,span,kmax){let best=q;for(let f=-span;f<=span+1e-9;f+=step){const t=q.c*(1+f),v=score(src,w,h,n,t,q.x,q.y,kmax);if(v>best.s||best===q&&f===-span)best={c:t,s:v,x:q.x,y:q.y}}return best}
// Coarse-to-fine search over cell size and grid offset, so resized and cropped images both decode.
function estimateCells(src,w,h,n,o={}){const list=[];for(let c=o.minCell||3.6;c<=(o.maxCell||48);c*=1.006){const b=bestOffset(src,w,h,n,c,10,Math.max(1,c/6));list.push({c,...b})}
 const peaks=list.filter((q,i)=>(i===0||q.s>=list[i-1].s)&&(i===list.length-1||q.s>=list[i+1].s)).sort((a,b)=>b.s-a.s).slice(0,o.peaks||6);
 return peaks.map(p=>{let q={...p,...bestOffset(src,w,h,n,p.c,12,1)};for(const[k,st,sp]of[[40,.002,.014],[200,.0005,.003],[1e9,.0002,.001]]){q=refine(src,w,h,n,q,st,sp,k);q=nudge(src,w,h,n,q,k)}return q}).sort((a,b)=>b.s-a.s)}
function decodeGlyphs(src,w,h,n,o={}){const cands=o.cell?[{c:o.cell,x:0,y:0}]:estimateCells(src,w,h,n,o);for(const q of cands){const g=grid(src,w,h,n,q.c,q.x,q.y);if(!g)continue;const d=decodeGrid(g,{maxPilotErrors:10,...o});if(d)return{...d,cell:+q.c.toFixed(3),offX:+q.x.toFixed(2),offY:+q.y.toFixed(2),carrier:"glyph"}}return null}
module.exports={renderGlyphs,decodeGlyphs,glyphCapacityCells,lean};
