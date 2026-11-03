"use strict";
// Packs text for hiding, using whichever is smallest: the built-in-lexicon compressor (cm.js), deflate, or plain bytes.
// Method codes stored in each header: 0 plain, 1 deflate, 2 lexicon compressor. The last packing is kept, so the
// panel's space figures and the encoder use the same result; long text is packed in the background first.
const pako=require("../lib/pako.min.js"),cm=require("./cm.js"),LEX=require("./lexicon.js");
const PLAIN=0,DEFLATE=1,LEXICON=2,BIG=262144;
let primed=null,last=null,pending=null;
function base(){if(!primed){const b=new Uint8Array(LEX.length);for(let i=0;i<LEX.length;i++)b[i]=LEX.charCodeAt(i);primed=new cm.Model();primed.prime(b)}return primed.clone()}
function pick(raw,c){let z=null;try{z=pako.deflateRaw(raw,{level:9})}catch(e){}let r={method:PLAIN,data:raw};if(z&&z.length<r.data.length)r={method:DEFLATE,data:z};if(c&&c.length<r.data.length)r={method:LEXICON,data:c};return r}
// Packs raw (the UTF-8 bytes of text). Synchronous; slow for book-length text unless prepare() ran first.
function pack(text,raw){if(last&&last.text===text)return last.r;const r=pick(raw,cm.encode(raw,base()));last={text,r};return r}
const ready=text=>!!last&&last.text===text;
// Packs long text in slices so the panel stays responsive; resolves when pack(text) is instant.
function prepare(text,raw){if(ready(text))return Promise.resolve(last.r);if(pending&&pending.text===text)return pending.p;
 const p=cm.encodeAsync(raw,base()).then(c=>{const r=pick(raw,c);last={text,r};if(pending&&pending.text===text)pending=null;return r});pending={text,p};return p}
function unpack(method,data){return method===LEXICON?cm.decode(data,base()):method===DEFLATE?pako.inflateRaw(data):data}
module.exports={pack,prepare,ready,unpack,PLAIN,DEFLATE,LEXICON,BIG};
