"use strict";
// Tract ink carrier: pure black ink on white paper, in the style of small-press comic tracts.
// Each cell holds one diagonal stroke, as in Glyph hatch: "/" is a 1 bit and "\" is a 0 bit.
// Dark cells become solid ink with a white scratch on the opposite diagonal, which leans the same way to the decoder.
// The source's own ink lines are laid over the strokes, and the error-correcting code absorbs what they cover.
const {clamp,luminance}=require("./math.js"),{tilePeriod,cellBit}=require("./layout.js"),{decodeGlyphs}=require("./glyph.js");
const PAPER=255,INK=0;
function lumAt(src,n,i){return luminance(src[i],src[i+1]??src[i],src[i+2]??src[i])}
function renderTract(src,w,h,n,bits,p={}){const c=Math.max(6,Math.round(p.tractCell||10)),period=tilePeriod(bits.length),out=new Uint8Array(src.length),half=c/2,inset=.12*c,
  night=(p.tractNight==null?24:p.tractNight)/100,lineThr=p.tractLine==null?118:p.tractLine,scratch=Math.max(.75,.11*c);
 for(let cy=0;cy*c<h;cy++)for(let cx=0;cx*c<w;cx++){const x0=cx*c,y0=cy*c,x1=Math.min(w,x0+c),y1=Math.min(h,y0+c);let s=0,k=0;
  for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){s+=lumAt(src,n,(y*w+x)*n);k++}
  const L=s/k/255,bit=cellBit(cx,cy,bits,period,p.seed),dark=L<night,diag=dark?1-bit:bit,t=dark?scratch:c*(.04+.10*(1-L)),len=dark?1:.5+.5*(1-L);
  for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){const u=x-x0+.5-half,v=y-y0+.5-half,along=diag?(u-v)/Math.SQRT2:(u+v)/Math.SQRT2,across=diag?(u+v)/Math.SQRT2:(u-v)/Math.SQRT2,lim=(half*Math.SQRT2-inset)*len,
   d=Math.max(Math.abs(across)-t,Math.abs(along)-lim),a=clamp(.5-d,0,1),i=(y*w+x)*n;let g=dark?INK*(1-a)+PAPER*a:PAPER*(1-a)+INK*a;
   if(!dark&&lineThr>0){const l=lumAt(src,n,i);g=Math.min(g,clamp((l-lineThr+24)/48,0,1)*255)}
   g=Math.round(g);for(let q=0;q<Math.min(3,n);q++)out[i+q]=g;if(n>3)out[i+3]=src[i+3]}}
 return{pixels:out,cell:c,period}}
function decodeTract(src,w,h,n,o={}){const d=decodeGlyphs(src,w,h,n,o);return d?{...d,carrier:"tract"}:null}
module.exports={renderTract,decodeTract};
