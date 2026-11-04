"use strict";
// Color Pop carrier: a saturated, posterized look whose large tiles are shaded warmer (1 bit) or cooler (0 bit).
// The data rides on the blue-yellow (Cb) axis only, as a smooth bump per tile; brightness is left to the art.
// Uses the same ISB3 frame and tile layout as the brightness carrier, so decodeGrid reads it unchanged.
const {clamp}=require("./math.js"),{tilePeriod,cellBit}=require("./layout.js"),{clusterBits,decodeGrid}=require("./carrier.js");
const cb=(r,g,b)=>-.168736*r-.331264*g+.5*b;
function bump(u,v){return Math.sin(Math.PI*u)*Math.sin(Math.PI*v)}
// Bold mosaic: each tile is filled with its average colour, saturated and posterized, then shaded by the warm/cool bump.
// Flat tiles keep the photo's own colour detail out of the data channel; the tile's colour is pulled into gamut once,
// for the whole tile, so the bump is never clipped.
function toRGB(Y,Cb,Cr){return[Y+1.402*Cr,Y-.344136*Cb-.714136*Cr,Y+1.772*Cb]}
const inGamut=q=>q.every(v=>v>=0&&v<=255);
function renderColorPop(src,w,h,n,bits,p={}){const c=Math.max(8,Math.round(p.colorCell||20)),period=tilePeriod(bits.length),out=new Uint8Array(src.length),sat=1+1.6*clamp((p.colorSaturation==null?70:p.colorSaturation)/100,0,1),levels=Math.round(p.colorLevels||6),amp=10+22*clamp((p.colorStrength==null?60:p.colorStrength)/100,0,1);
 for(let cy=0;cy*c<h;cy++)for(let cx=0;cx*c<w;cx++){const x0=cx*c,y0=cy*c,x1=Math.min(w,x0+c),y1=Math.min(h,y0+c);let r=0,g=0,b=0,k=0;
  for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){const i=(y*w+x)*n;r+=src[i];g+=src[i+1]??src[i];b+=src[i+2]??src[i];k++}r/=k;g/=k;b/=k;
  const Y=.299*r+.587*g+.114*b;let Yp=Math.round(Y/255*(levels-1))/(levels-1)*255;Yp=28+(.65*Yp+.35*Y)*200/255;
  const s=cellBit(cx,cy,bits,period,p.seed)?1:-1;let Cb=cb(r,g,b)*sat,Cr=(.5*r-.418688*g-.081312*b)*sat;
  for(let t=1;t>=0;t-=.0625){if(inGamut(toRGB(Yp,Cb*t,Cr*t))&&inGamut(toRGB(Yp,Cb*t+s*amp,Cr*t))){Cb*=t;Cr*=t;break}if(t<.07){Cb=0;Cr=0}}
  for(let y=y0;y<y1;y++){const v=(y-y0+.5)/c;for(let x=x0;x<x1;x++){const i=(y*w+x)*n,q=toRGB(Yp,Cb+s*amp*bump((x-x0+.5)/c,v),Cr);out[i]=clamp(Math.round(q[0]),0,255);out[i+1]=clamp(Math.round(q[1]),0,255);out[i+2]=clamp(Math.round(q[2]),0,255);if(n>3)out[i+3]=src[i+3]}}}
 return{pixels:out,cell:c,period}}
function cbAt(src,w,h,n,x,y){const xi=clamp(Math.round(x),0,w-1),yi=clamp(Math.round(y),0,h-1),i=(yi*w+xi)*n;return cb(src[i],src[i+1]??src[i],src[i+2]??src[i])}
// Correlates the tile's Cb with the bump after removing the tile's own colour slope (norm: correlation coefficient, for the grid search).
function tileValue(src,w,h,n,c,x0,y0,N,norm){let k=0,sy=0,sp=0,sxx=0,szz=0,syx=0,spx=0,syz=0,spz=0;const Y=[],P=[],X=[],Z=[];
 for(let j=0;j<N;j++)for(let i=0;i<N;i++){const u=(i+.5)/N,v=(j+.5)/N,val=cbAt(src,w,h,n,x0+u*c-.5,y0+v*c-.5),p=bump(u,v),a=u-.5,b=v-.5;Y.push(val);P.push(p);X.push(a);Z.push(b);sy+=val;sp+=p;sxx+=a*a;szz+=b*b;syx+=val*a;spx+=p*a;syz+=val*b;spz+=p*b;k++}
 const my=sy/k,mp=sp/k,by=syx/sxx,bp=spx/sxx,cy=syz/szz,cp=spz/szz;let num=0,den=0,ey=0;for(let t=0;t<k;t++){const yy=Y[t]-my-by*X[t]-cy*Z[t],pp=P[t]-mp-bp*X[t]-cp*Z[t];num+=yy*pp;den+=pp*pp;ey+=yy*yy}if(norm)return den&&ey?num/Math.sqrt(den*ey):0;return den?num/den:0}
function score(src,w,h,n,c,ox,oy,kmax=1e9){const cols=Math.floor((w-ox)/c),rows=Math.floor((h-oy)/c);if(cols<12||rows<12)return 0;const kx=Math.min(cols,kmax),ky=Math.min(rows,kmax),G=Math.min(10,kx);let s=0;for(let j=0;j<G;j++)for(let i=0;i<G;i++){const cx=Math.round((i+.5)*kx/G-.5),cy=Math.round((j+.5)*ky/G-.5);s+=Math.abs(tileValue(src,w,h,n,c,ox+cx*c,oy+cy*c,5,true))}return s/(G*G)}
function grid(src,w,h,n,c,ox=0,oy=0){const cols=Math.floor((w-ox)/c),rows=Math.floor((h-oy)/c);if(cols<12||rows<12)return null;const values=new Float32Array(cols*rows);let k=0;for(let y=0;y<rows;y++)for(let x=0;x<cols;x++)values[k++]=tileValue(src,w,h,n,c,ox+x*c,oy+y*c,6);return{...clusterBits(values),values,cols,rows,cell:c,ox,oy}}
function bestOffset(src,w,h,n,c,kmax,st){let b={s:-1,x:0,y:0},sum=0,m=0;for(let y=0;y<c-.01;y+=st)for(let x=0;x<c-.01;x+=st){const v=score(src,w,h,n,c,x,y,kmax);sum+=v;m++;if(v>b.s)b={s:v,x,y}}b.peak=b.s-sum/m;return b}
function nudge(src,w,h,n,q,kmax){let b={...q,s:score(src,w,h,n,q.c,q.x,q.y,kmax)};const st=Math.max(.5,q.c/16);for(let dy=-3*st;dy<=3*st;dy+=st)for(let dx=-3*st;dx<=3*st;dx+=st){const x=q.x+dx,y=q.y+dy;if(x<0||y<0)continue;const v=score(src,w,h,n,q.c,x,y,kmax);if(v>b.s)b={...q,x,y,s:v}}return b}
function refine(src,w,h,n,q,step,span,kmax){let best=null;for(let f=-span;f<=span+1e-9;f+=step){const t=q.c*(1+f),v=score(src,w,h,n,t,q.x,q.y,kmax);if(!best||v>best.s)best={c:t,s:v,x:q.x,y:q.y}}return best}
// Coarse-to-fine search over tile size and offset, so resized and cropped images decode. Candidates are ranked by how
// sharply the score peaks at one offset, which separates the real grid from busy image content.
function estimateCells(src,w,h,n,o={}){const list=[];for(let c=o.minCell||5;c<=(o.maxCell||64);c*=1.01){const b=bestOffset(src,w,h,n,c,10,Math.max(1,c/5));list.push({c,...b})}
 const peaks=list.filter((q,i)=>(i===0||q.peak>=list[i-1].peak)&&(i===list.length-1||q.peak>=list[i+1].peak)).sort((a,b)=>b.peak-a.peak).slice(0,o.peaks||5);
 return peaks.map(p=>{let q={...p,...bestOffset(src,w,h,n,p.c,12,Math.max(.5,p.c/12))};for(const[k,st,sp]of[[40,.002,.014],[200,.0005,.003],[1e9,.0002,.001]]){q=refine(src,w,h,n,q,st,sp,k);q=nudge(src,w,h,n,q,k)}return q}).sort((a,b)=>b.s-a.s)}
function decodeColorPop(src,w,h,n,o={}){const cands=o.cell?[{c:o.cell,x:0,y:0}]:estimateCells(src,w,h,n,o);for(const q of cands){const g=grid(src,w,h,n,q.c,q.x,q.y);if(!g)continue;const d=decodeGrid(g,{maxPilotErrors:10,...o});if(d)return{...d,cell:+q.c.toFixed(3),offX:+q.x.toFixed(2),offY:+q.y.toFixed(2),carrier:"colorpop"}}return null}
module.exports={renderColorPop,decodeColorPop};
