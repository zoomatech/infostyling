"use strict";
function clamp(v,a,b){return v<a?a:v>b?b:v}
function lerp(a,b,t){return a+(b-a)*t}
function smooth(t){return t*t*(3-2*t)}
function fract(x){return x-Math.floor(x)}
function hash2(x,y,seed){let n=(Math.imul(x|0,374761393)+Math.imul(y|0,668265263)+Math.imul(seed|0,1442695041))|0;n=(n^(n>>>13))|0;n=Math.imul(n,1274126177);n^=n>>>16;return(n>>>0)/4294967295}
function valueNoise(x,y,seed){const xi=Math.floor(x),yi=Math.floor(y),tx=smooth(x-xi),ty=smooth(y-yi),a=hash2(xi,yi,seed),b=hash2(xi+1,yi,seed),c=hash2(xi,yi+1,seed),d=hash2(xi+1,yi+1,seed);return lerp(lerp(a,b,tx),lerp(c,d,tx),ty)*2-1}
function fbm(x,y,seed,oct,pers,lac){let amp=1,freq=1,total=0,norm=0;for(let i=0;i<oct;i++){total+=valueNoise(x*freq,y*freq,seed+i*1013)*amp;norm+=amp;amp*=pers;freq*=lac}return norm?total/norm:0}
function luminance(r,g,b){return .2126*r+.7152*g+.0722*b}
function hueRotate(r,g,b,a){if(Math.abs(a)<1e-8)return[r,g,b];const ca=Math.cos(a),sa=Math.sin(a),y=.299*r+.587*g+.114*b,i=.596*r-.274*g-.322*b,q=.211*r-.523*g+.312*b,ii=i*ca-q*sa,qq=i*sa+q*ca;return[clamp(y+.956*ii+.621*qq,0,255),clamp(y-.272*ii-.647*qq,0,255),clamp(y-1.106*ii+1.703*qq,0,255)]}
function sampleNearest(src,w,h,c,x,y){x=clamp(Math.round(x),0,w-1);y=clamp(Math.round(y),0,h-1);const i=(y*w+x)*c;return[src[i],src[i+1]??src[i],src[i+2]??src[i],c>3?src[i+3]:255]}
module.exports={clamp,lerp,fract,hash2,valueNoise,fbm,luminance,hueRotate,sampleNearest};
