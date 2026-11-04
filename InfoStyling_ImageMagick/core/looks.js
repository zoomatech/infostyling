"use strict";
// One-click looks: what each tile does, how much text it holds, and its preview. Pure functions so they can be tested outside Photoshop.
const {PRESETS}=require("../config.js"),brightq=require("./brightq.js"),codec=require("./codec.js"),layout=require("./layout.js"),style=require("./style.js"),carrier=require("./carrier.js"),glyph=require("./glyph.js"),chroma=require("./chroma.js"),tract=require("./tract.js"),presets=require("./presets.js");
const LOOKS=[
 {id:"none",label:"Invisible",note:"Photo stays as it is"},
 {id:"glyph",label:"Glyph hatch",note:"Diagonal strokes",cell:12},
 {id:"colorpop",label:"Color Pop",note:"Bold color tiles",cell:20},
 {id:"tract",label:"Tract ink",note:"Black ink comic",cell:8},
 {id:"engraving",label:"Engraving",note:"Banknote lines"},
 {id:"impressionist",label:"Impressionist",note:"Painterly strokes"},
 {id:"cubist",label:"Cubist",note:"Faceted blocks"},
 {id:"surreal",label:"Surreal",note:"Melting waves"},
 {id:"penskip",label:"Pen sketch",note:"Skipping pen lines"},
 {id:"stipple",label:"Stipple",note:"Ink dots"},
 {id:"fractal",label:"Fractal",note:"Swirling noise"}
];
const byId=id=>LOOKS.find(l=>l.id===id);
const artLook=id=>id==="glyph"||id==="colorpop"||id==="tract";
// Carrier cell for the JPEG-safe route: art looks use their own mark size, the others the cell that survives a resize to 2048 px.
function robustCell(look,w,h){return look.cell||presets.socialCell(w,h)}
// Shareable space in bytes. The Invisible look uses the 8×8 brightness channel; the others the ISB3 carrier.
function shareSpace(id,w,h){return id==="none"?brightq.capacityBytes(w,h):layout.blindCapacityBytes(w,h,robustCell(byId(id),w,h))}
// Two outputs per look: "share" is the JPEG-safe carrier (short text, survives social media); "full" is the lossless PNG channel (book size, full resolution only).
function plan(id,w,h,text,memo={},route){const look=byId(id),bytes=memo.bytes!=null?memo.bytes:(memo.bytes=codec.utf8Encode(text||"").length);if(!look||!bytes)return{look,bytes,route:null};const cell=robustCell(look,w,h);
 if(route==="share"){const cap=shareSpace(id,w,h);
  if(memo.stored==null)memo.stored=codec.robustStoredBytes(text);return{look,bytes,route,cell,cap,stored:memo.stored,fits:memo.stored<=cap}}
 const b=memo.dense||(memo.dense=presets.bookPlan(w,h,3,text));return{look,bytes,route:"full",cell,bpc:b.bpc,cap:b.cap,stored:b.stored,fits:!!b.bpc}}
// Rough room in characters, for the counters. Short text barely compresses (about 1 byte per character);
// book-length English deflates to roughly 2.5 characters per stored byte. Once real text is long enough, its own ratio is used.
const dense=require("./dense.js");
function room(id,w,h,chars,memo={}){const look=byId(id),shareCap=shareSpace(id,w,h),fullCap=dense.capacityBytes(w*h*3,2);
 const sr=chars>=200&&memo.stored>0&&Number.isFinite(memo.stored)?chars/memo.stored:1,fr=chars>=2000&&memo.dense&&memo.dense.stored>0?chars/memo.dense.stored:2.5;
 return{share:Math.floor(shareCap*sr),full:Math.floor(fullCap*fr)}}
function profile(id,cell,seed){const p={...PRESETS[id]||PRESETS.engraving,style:id,seed,blindCell:cell,fx:{}};if(id==="glyph")p.glyphCell=cell;if(id==="colorpop")p.colorCell=cell;if(id==="tract")p.tractCell=cell;return p}
// Renders a look onto pixels at full scale. Used for the tile previews (a crop at 100%) and shares code with the real encode.
function renderLook(id,src,w,h,n,bits,cell,seed){const p=profile(id,cell,seed);if(id==="glyph")return glyph.renderGlyphs(src,w,h,n,bits,{glyphCell:cell,seed}).pixels;if(id==="colorpop")return chroma.renderColorPop(src,w,h,n,bits,{colorCell:cell,seed}).pixels;if(id==="tract")return tract.renderTract(src,w,h,n,bits,{tractCell:cell,seed}).pixels;if(id==="none")return new Uint8Array(src);return style.render({src,width:w,height:h,components:n,bits:codec.frameBits("InfoStyling preview"),profile:p}).pixels}
function preview(id,src,w,h,n,fullW,fullH,seed){if(id==="none")try{return brightq.embed(src,w,h,n,"InfoStyling preview").pixels}catch(e){return new Uint8Array(src)}
 const look=byId(id),cell=robustCell(look,fullW,fullH),bits=codec.v3FrameBits("InfoStyling preview",{style:artLook(id)?"none":id,blindCell:cell,seed});const art=renderLook(id,src,w,h,n,bits,cell,seed);return artLook(id)?art:carrier.applyBlindCarrier(art,w,h,n,bits,profile(id,cell,seed)).pixels}
// What the panel shows per look: bytes the image has for this look and size, and bytes the text takes once encoded
// by it (compressed text plus that look's header, error correction and repeats). Both come from the encoder's own sizes.
function footprint(id,w,h,stored,route){let avail,takes;
 if(route==="full"){avail=(dense.HEADER+dense.capacityBytes(w*h*3,4))*8;takes=(dense.HEADER+stored)*8}
 else if(id==="none"){avail=brightq.slotCount(w,h);takes=brightq.codedBits(stored)}
 else{avail=codec.v3FrameBitLength(shareSpace(id,w,h));takes=codec.v3FrameBitLength(stored)}
 return{avail:Math.ceil(avail/8),takes:Math.ceil(takes/8),over:takes>avail,short:Math.ceil(Math.max(0,takes-avail)/8),left:Math.floor(Math.max(0,avail-takes)/8)}}
module.exports={footprint,shareSpace,room,LOOKS,byId,artLook,robustCell,plan,profile,renderLook,preview};
