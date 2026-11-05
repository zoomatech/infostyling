"use strict";
const M=require("./math.js"),{clamp,lerp,fract,hash2,valueNoise,fbm,luminance,hueRotate,sampleNearest}=M;
function styleGate(style,x,y,cx,cy,p,n,sign){
 const a=p.orientation*Math.PI/180,ca=Math.cos(a),sa=Math.sin(a),u=x*ca+y*sa,v=-x*sa+y*ca,density=clamp(p.density/100,.02,1),width=Math.max(.6,p.lineWidth),spacing=Math.max(width+1,p.cellSize*(.12+(1-density)*.35));
 if(style==="engraving")return fract((v+n*p.roughness*.15)/spacing)<width/spacing?1:.12;
 if(style==="impressionist"){const stroke=Math.sin(u/Math.max(2,p.cellSize*.22)+n*4.5+sign*.35),blob=valueNoise(x/Math.max(3,p.cellSize*.35),y/Math.max(3,p.cellSize*.35),p.seed+77);return clamp(.35+.45*Math.abs(stroke)+.35*Math.max(0,blob),.1,1)}
 if(style==="cubist"){const lx=(x%p.cellSize)/p.cellSize,ly=(y%p.cellSize)/p.cellSize,diag=lx+ly+n*.12+sign*.04;return fract(diag*2)<.22||Math.abs(lx-ly)<.045?1:.35}
 if(style==="surreal")return clamp(.45+.4*Math.sin((u+.6*p.cellSize*n)/Math.max(2,p.cellSize*.18)),.08,1);
 if(style==="penskip")return fract((u+n*p.roughness*.35)/Math.max(2,spacing*.75))<.06+.28*density?1:.16;
 if(style==="stipple")return hash2(Math.floor(x/Math.max(1,width)),Math.floor(y/Math.max(1,width)),p.seed+cx*17+cy*31)<density*.42?1:.1;
 return style==="fractal"?clamp(.3+.7*Math.abs(n),.08,1):.5;
}
function render({src,width,height,components,bits,profile:p}){
 const out=new Uint8Array(src.length),cell=Math.max(4,Math.round(p.cellSize)),cols=Math.ceil(width/cell),strength=clamp(p.strength/100,0,1),contrast=clamp(p.contrast/100,0,1),luma=clamp(p.luminance/100,0,1),hue=clamp(p.hue/100,0,1),inv=clamp(p.inversion/100,0,1),carrier=clamp(p.carrier/100,0,1),wamp=Math.max(0,p.wobble)*strength,wscale=Math.max(2,p.wobbleScale),pbias=clamp(p.payloadWobble/100,0,1),oct=clamp(Math.round(p.octaves),1,7),pers=clamp(p.persistence,.1,.95),lac=clamp(p.lacunarity,1.1,4),angle=p.orientation*Math.PI/180,nx=-Math.sin(angle),ny=Math.cos(angle);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const cx=Math.floor(x/cell),cy=Math.floor(y/cell),ci=cy*cols+cx,bit=bits[ci%bits.length]?1:0,sign=bit?1:-1,n=fbm(x/wscale,y/wscale,p.seed+ci*3,oct,pers,lac),wobble=n*wamp*(1+sign*.45*pbias);let sx=x+nx*wobble,sy=y+ny*wobble;
  if(p.style==="surreal"){const w2=fbm(x/(wscale*1.7),y/(wscale*1.7),p.seed+991,oct,pers,lac);sx+=Math.cos(angle)*w2*wamp*.65;sy+=Math.sin(angle)*w2*wamp*.65}else if(p.style==="cubist"){const q=Math.max(2,cell*.18*strength);if(q>2.1){sx=Math.round(sx/q)*q;sy=Math.round(sy/q)*q}}
  let[r,g,b,a]=sampleNearest(src,width,height,components,sx,sy),i=(y*width+x)*components;if(a===0){out[i]=r;if(components>1)out[i+1]=g;if(components>2)out[i+2]=b;if(components>3)out[i+3]=a;continue}
  const gate=styleGate(p.style,x,y,cx,cy,p,n,sign),st=strength*gate,y0=luminance(r,g,b),cg=1+sign*contrast*st*.42;r=y0+(r-y0)*cg;g=y0+(g-y0)*cg;b=y0+(b-y0)*cg;
  const bias=sign*(2+18*carrier)*strength*(.45+.55*gate)+sign*10*luma*st;r+=bias;g+=bias;b+=bias;
  if(inv>0){const t=inv*st*(bit?.42:.13);r=lerp(r,255-r,t);g=lerp(g,255-g,t);b=lerp(b,255-b,t)}
  [r,g,b]=hueRotate(r,g,b,sign*hue*st*.55+n*hue*strength*.22);
  if(p.style==="stipple"&&gate>.7){const m=14+48*strength;if(bit){r-=m;g-=m;b-=m}else{r+=m*.72;g+=m*.72;b+=m*.72}}else if(p.style==="penskip"&&gate>.7){const t=bit?238:25,m=.08+.34*strength;r=lerp(r,t,m);g=lerp(g,t,m);b=lerp(b,t,m)}else if(p.style==="engraving"&&gate>.7){const k=12+42*strength;r-=k;g-=k;b-=k}
  out[i]=clamp(Math.round(r),0,255);if(components>1)out[i+1]=clamp(Math.round(g),0,255);if(components>2)out[i+2]=clamp(Math.round(b),0,255);if(components>3)out[i+3]=a;
 }
 return{pixels:out};
}
module.exports={render};
