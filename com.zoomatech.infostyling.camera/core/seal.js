"use strict";
// Signed seal: proves who hid the text, and that neither the text nor the picture was changed afterwards.
// The seal rides at the end of the hidden text, after a 0 character, so every look and both sizes carry it.
// It holds the signer's name, the time, a coarse 8×8 brightness fingerprint of the finished picture, the
// signer's public key and an Ed25519 signature over all of that plus the text. Only the holder of the private
// key can make a seal that checks out; anyone can strip it, and a stripped image simply reads as "Not signed".
const nacl=require("../lib/nacl-fast.js"),codec=require("./codec.js");
const MARK="\u0000SEAL1:",VERSION=1,GRID=8,FP=GRID*GRID*5/8,PK=32,SIG=64,NAME_MAX=40,DOMAIN=codec.utf8Encode("InfoStyling seal 1\u0000");
// Picture check limits, in brightness levels (0-255): average and worst 1/64th of the picture.
const AVG_MAX=10,CELL_MAX=40;
const B64="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
function b64(a){let s="";for(let i=0;i<a.length;i+=3){const v=a[i]<<16|(a[i+1]||0)<<8|(a[i+2]||0);s+=B64[v>>18&63]+B64[v>>12&63]+(i+1<a.length?B64[v>>6&63]:"=")+(i+2<a.length?B64[v&63]:"=")}return s}
function unb64(s){s=s.replace(/=+$/,"");const out=new Uint8Array(Math.floor(s.length*3/4));let v=0,k=0,o=0;for(const c of s){const d=B64.indexOf(c);if(d<0)throw new Error("bad seal");v=v<<6|d;k+=6;if(k>=8){k-=8;out[o++]=v>>k&255}}return out.slice(0,o)}
const cat=(...a)=>{const out=new Uint8Array(a.reduce((n,x)=>n+x.length,0));let o=0;for(const x of a){out.set(x,o);o+=x.length}return out};
const hex=a=>Array.from(a,v=>v.toString(16).padStart(2,"0")).join("").toUpperCase();
const keyId=pk=>{const h=hex(nacl.hash(pk).slice(0,4));return h.slice(0,4)+"-"+h.slice(4)};
function cleanName(name){let s=String(name||"").trim();while(codec.utf8Encode(s).length>NAME_MAX)s=s.slice(0,-1);return s}
// Average brightness of each of 8×8 equal parts of the picture.
function means(px,w,h,n){const m=new Float64Array(GRID*GRID);for(let gy=0;gy<GRID;gy++){const y0=Math.floor(gy*h/GRID),y1=Math.max(y0+1,Math.floor((gy+1)*h/GRID));for(let gx=0;gx<GRID;gx++){const x0=Math.floor(gx*w/GRID),x1=Math.max(x0+1,Math.floor((gx+1)*w/GRID));let s=0,c=0;
 for(let y=y0;y<y1;y+=2)for(let x=x0;x<x1;x+=2){const i=(y*w+x)*n;s+=n>2?.299*px[i]+.587*px[i+1]+.114*px[i+2]:px[i];c++}m[gy*GRID+gx]=s/c}}return m}
// 40-byte fingerprint: each part's brightness in 32 steps.
function fingerprint(px,w,h,n){const m=means(px,w,h,n),out=new Uint8Array(FP);for(let i=0;i<m.length;i++){const q=Math.max(0,Math.min(31,Math.round(m[i]*31/255)));for(let b=0;b<5;b++)if(q>>(4-b)&1){const k=i*5+b;out[k>>3]|=128>>(k&7)}}return out}
function unfingerprint(fp){const q=new Float64Array(GRID*GRID);for(let i=0;i<q.length;i++){let v=0;for(let b=0;b<5;b++){const k=i*5+b;v=v<<1|(fp[k>>3]>>(7-(k&7))&1)}q[i]=v*255/31}return q}
function pictureMatches(fp,px,w,h,n){const a=unfingerprint(fp),m=means(px,w,h,n);let sum=0,worst=0;for(let i=0;i<m.length;i++){const d=Math.abs(m[i]-a[i]);sum+=d;if(d>worst)worst=d}const avg=sum/m.length;return{ok:avg<=AVG_MAX&&worst<=CELL_MAX,avg,worst}}
// A new key pair from as much randomness as the host offers. Ed25519 signing itself needs no randomness.
function newKeys(){const parts=[];try{const c=typeof crypto!=="undefined"?crypto:typeof self!=="undefined"?self.crypto:null;if(c&&c.getRandomValues){const r=new Uint8Array(64);c.getRandomValues(r);parts.push(r)}}catch(e){}
 const x=new Float64Array(64);for(let i=0;i<x.length;i++)x[i]=Math.random()*Date.now()+(typeof performance!=="undefined"&&performance.now?performance.now():i);parts.push(new Uint8Array(x.buffer));
 return nacl.sign.keyPair.fromSeed(nacl.hash(cat(...parts)).slice(0,32))}
const keysFromSecret=s=>nacl.sign.keyPair.fromSecretKey(unb64(s)),secretText=k=>b64(k.secretKey);
function body(name,time,fp,pk){const nm=codec.utf8Encode(cleanName(name)),t=time>>>0;return cat(Uint8Array.of(VERSION,nm.length),nm,Uint8Array.of(t>>>24&255,t>>>16&255,t>>>8&255,t&255),fp,pk)}
const attach=(text,seal)=>text+MARK+b64(seal);
// The text with a seal of the right length but no real signature, for measuring space before the picture exists.
function placeholder(text,name,keys){const h=nacl.hash(codec.utf8Encode(text.slice(0,200)+name)),fill=n=>{const a=new Uint8Array(n);for(let i=0;i<n;i++)a[i]=h[i%64]^(i*151&255);return a};return attach(text,cat(body(name,Date.now()/1000,fill(FP),keys.publicKey),fill(SIG)))}
// The finished text: original text plus a seal signed with the private key.
function sign(text,name,keys,fp,time){const b=body(name,time==null?Date.now()/1000:time,fp,keys.publicKey),sig=nacl.sign.detached(cat(DOMAIN,codec.utf8Encode(text),b),keys.secretKey);return attach(text,cat(b,sig))}
// Splits a decoded text into the original text and its seal, checks the signature, and checks the seal against the picture.
function check(full,px,w,h,n){const at=full.lastIndexOf(MARK);if(at<0)return{text:full,status:"none",line:"Not signed."};const text=full.slice(0,at);
 try{const s=unb64(full.slice(at+MARK.length)),nl=s[1];if(s[0]!==VERSION||s.length!==2+nl+4+FP+PK+SIG)throw new Error("bad seal");
  const name=codec.utf8Decode(s.slice(2,2+nl)),o=2+nl,time=((s[o]<<24)>>>0)+(s[o+1]<<16)+(s[o+2]<<8)+s[o+3],fp=s.slice(o+4,o+4+FP),pk=s.slice(o+4+FP,o+4+FP+PK),sig=s.slice(o+4+FP+PK),b=s.slice(0,o+4+FP+PK);
  const date=new Date(time*1000).toISOString().slice(0,10),id=keyId(pk),who=`"${name}" (key ID ${id})`;
  if(!nacl.sign.detached.verify(cat(DOMAIN,codec.utf8Encode(text),b),sig,pk))return{text,status:"tampered",name,date,keyId:id,short:"✗ Tampered or counterfeit",line:`✗ TAMPERED: the hidden text or its seal was changed after it was signed. The seal claims ${who}.`};
  if(px){const m=pictureMatches(fp,px,w,h,n);if(!m.ok)return{text,status:"picture",name,date,keyId:id,short:"✗ Picture changed",line:`✗ PICTURE CHANGED: the text is genuine, signed by ${who} on ${date}, but this picture is not the one it was signed in (edited, cropped or swapped).`}}
  return{text,status:"ok",name,date,keyId:id,short:`✔ Signed by ${name} · key ${id}`,line:`✔ SIGNED by ${who} on ${date}. Text and picture unchanged.`}}
 catch(e){return{text,status:"tampered",short:"✗ Tampered or counterfeit",line:"✗ TAMPERED: the seal is damaged and cannot be checked."}}}
module.exports={MARK,fingerprint,pictureMatches,newKeys,keysFromSecret,secretText,keyId,cleanName,placeholder,sign,check};
