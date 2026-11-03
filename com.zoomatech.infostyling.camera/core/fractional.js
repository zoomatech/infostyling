"use strict";
// Web-only addition: finds and reads an ISB3 carrier whose cell size is no longer a whole number of pixels
// (e.g. after the image was resized to 2048 px). Reuses the plugin's blindPattern, clusterBits and decodeGrid.
const {blindPattern,clusterBits,decodeGrid}=require("./carrier.js"),{luminance}=require("./math.js");
function corr(src,w,h,n,c,x0,y0,N){let k=0,sy=0,sp=0,sxx=0,szz=0,syx=0,spx=0,syz=0,spz=0;const Y=[],P=[],X=[],Z=[];
 for(let j=0;j<N;j++)for(let i=0;i<N;i++){const x=Math.round(x0+(i+.5)*c/N-.5),y=Math.round(y0+(j+.5)*c/N-.5);if(x<0||y<0||x>=w||y>=h)continue;const q=(y*w+x)*n;if(n>3&&src[q+3]<20)continue;
  const v=luminance(src[q],src[q+1]??src[q],src[q+2]??src[q]),p=blindPattern(x-x0,y-y0,c),a=(i-(N-1)/2)/N,b=(j-(N-1)/2)/N;Y.push(v);P.push(p);X.push(a);Z.push(b);sy+=v;sp+=p;sxx+=a*a;szz+=b*b;syx+=v*a;spx+=p*a;syz+=v*b;spz+=p*b;k++}
 if(!k)return 0;const my=sy/k,mp=sp/k,by=sxx?syx/sxx:0,bp=sxx?spx/sxx:0,cy=szz?syz/szz:0,cp=szz?spz/szz:0;let num=0,den=0;
 for(let t=0;t<k;t++){const yy=Y[t]-my-by*X[t]-cy*Z[t],pp=P[t]-mp-bp*X[t]-cp*Z[t];num+=yy*pp;den+=pp*pp}return den?num/den:0}
function score(src,w,h,n,c,ox,oy,kmax){const cols=Math.floor((w-ox)/c),rows=Math.floor((h-oy)/c),kx=Math.min(cols,kmax),ky=Math.min(rows,kmax);if(kx<8||ky<8)return 0;let s=0,m=0;const G=6;
 for(let j=0;j<G;j++)for(let i=0;i<G;i++){const cx=Math.round((i+.5)*kx/G-.5),cy=Math.round((j+.5)*ky/G-.5);s+=Math.abs(corr(src,w,h,n,c,ox+cx*c,oy+cy*c,5));m++}return s/m}
function grid(src,w,h,n,c,ox=0,oy=0){const cols=Math.floor((w-ox)/c),rows=Math.floor((h-oy)/c);if(cols<1||rows<1)return null;const values=new Float32Array(cols*rows);let k=0;
 for(let y=0;y<rows;y++)for(let x=0;x<cols;x++)values[k++]=corr(src,w,h,n,c,ox+x*c,oy+y*c,7);return{...clusterBits(values),values,cols,rows,cell:c,ox,oy}}
function refine(src,w,h,n,c,step,span,kmax){let best=c,bs=-1;for(let f=-span;f<=span;f+=step){const t=c*(1+f),s=score(src,w,h,n,t,0,0,kmax);if(s>bs){bs=s;best=t}}return{c:best,s:bs}}
// Coarse-to-fine search over cell size, assuming the carrier grid still starts at the image's top-left corner.
function estimateCells(src,w,h,n,o={}){const lo=o.minCell||4.5,hi=o.maxCell||48,r=1.012,list=[];for(let c=lo;c<=hi;c*=r)list.push({c,s:score(src,w,h,n,c,0,0,10)});
 const peaks=list.filter((q,i)=>(i===0||q.s>=list[i-1].s)&&(i===list.length-1||q.s>=list[i+1].s)).sort((a,b)=>b.s-a.s).slice(0,o.peaks||4);
 return peaks.map(p=>{let q=refine(src,w,h,n,p.c,.002,.014,40);q=refine(src,w,h,n,q.c,.0003,.0025,1e9);return q}).sort((a,b)=>b.s-a.s)}
function decodeFractional(src,w,h,n,o={}){const cands=estimateCells(src,w,h,n,o);for(const q of cands){const g=grid(src,w,h,n,q.c);if(!g)continue;const r=decodeGrid(g,o);if(r)return{...r,cell:+q.c.toFixed(3),offX:0,offY:0,separation:g.separation,scaleScore:q.s}}return null}
module.exports={estimateCells,decodeFractional,grid};
