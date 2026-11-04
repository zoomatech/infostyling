#!/usr/bin/env node
"use strict";
// InfoStyling for ImageMagick: the Photoshop plugin v0.13.0 as a command-line tool.
// ImageMagick opens and saves the pictures; the hiding, reading, compression and signed seal are the
// Photoshop plugin's own core files (core/, lib/, config.js, engine.js), copied unchanged, so pictures made
// here read in the Photoshop plugin and the Chrome plugin 0.13.0, and theirs read here.
const fs=require("fs"),path=require("path"),os=require("os"),{spawnSync}=require("child_process");
const codec=require("./core/codec.js"),engine=require("./engine.js"),dense=require("./core/dense.js"),glyph=require("./core/glyph.js"),colorpop=require("./core/chroma.js"),tract=require("./core/tract.js"),fractional=require("./core/fractional.js"),effects=require("./core/effects.js"),looks=require("./core/looks.js"),epub=require("./core/epub.js"),brightq=require("./core/brightq.js"),pack=require("./core/pack.js"),seal=require("./core/seal.js");
const VERSION="0.13.0",DEFAULT_SEED=24681357,JPEG_QUALITY=95;

const HELP=`InfoStyling for ImageMagick ${VERSION}

Hide text in a picture:
  infostyling hide PICTURE --look LOOK --text "your text" [options]
  infostyling hide PICTURE --look LOOK --file book.txt     (or a DRM-free .epub)

Read hidden text from a picture:
  infostyling read PICTURE [--save decoded.txt]

See how much text each look can hold:
  infostyling space PICTURE [--text "your text" | --file book.txt] [--size full]

Looks (use the name or the short word):
  ${looks.LOOKS.map(l=>`${l.id.padEnd(14)}${l.label} (${l.note})`).join("\n  ")}

Options for hide:
  --size share     Shareable (JPEG). Survives social media. The default.
  --size full      Full resolution (PNG). Holds book-length text. Share the PNG itself.
  --sign "NAME"    Add a signed seal with your name (date is automatic).
  --out FILE       Where to save. Default: next to the picture, named PICTURE_LOOK.jpg or .png
  --seed NUMBER    Default ${DEFAULT_SEED} (same as the Photoshop panel).
  --effect NAME=AMOUNT   Cover effect, amount 1 to 100. Can be repeated.
                   Names: ${effects.EFFECTS.map(e=>e[0]).join(", ")}

Options for read:
  --save FILE      Save the recovered text to a file.
  --quick          Skip the deep search (faster).
  --angle-search   Automatic angle search (much slower).
  --rotation DEGREES        Rotation correction, -30 to 30 degrees.
  --corners "TLx,TLy;TRx,TRy;BRx,BRy;BLx,BLy"  Artwork corners in % of the picture
                   (camera photo of a print; turns on camera reading).
`;

// ---------- ImageMagick ----------
let IM=null;
function im(){if(IM)return IM;for(const c of [["magick"],["convert"]]){const r=spawnSync(c[0],["-version"],{encoding:"utf8"});if(!r.error&&r.status===0&&/ImageMagick/.test(r.stdout))return IM=c}
 throw new Error("ImageMagick was not found. Install it with:  brew install imagemagick")}
function run(args,input){const r=spawnSync(im()[0],args,{input,maxBuffer:1<<30});if(r.error)throw r.error;if(r.status!==0)throw new Error("ImageMagick: "+String(r.stderr||"failed").trim());return r.stdout}
const MAC_SRGB="/System/Library/ColorSync/Profiles/sRGB Profile.icc";
// Opens any picture ImageMagick reads, turned upright, flattened on white, as 8-bit sRGB red/green/blue pixels.
function readPixels(file){if(!fs.existsSync(file))throw new Error("Picture not found: "+file);
 const prof=fs.existsSync(MAC_SRGB)?["-profile",MAC_SRGB]:[];
 const ppm=run([file+"[0]","-auto-orient",...prof,"-colorspace","sRGB","-background","white","-alpha","remove","-alpha","off","-depth","8","ppm:-"]);
 let i=0;const tok=()=>{while(/\s/.test(String.fromCharCode(ppm[i])))i++;if(ppm[i]===35){while(ppm[i]!==10)i++;return tok()}let s="";while(!/\s/.test(String.fromCharCode(ppm[i])))s+=String.fromCharCode(ppm[i++]);return s};
 if(tok()!=="P6")throw new Error("Could not read "+file);const width=+tok(),height=+tok(),max=+tok();i++;if(max!==255)throw new Error("Could not read "+file+" as 8-bit");
 return{data:new Uint8Array(ppm.buffer,ppm.byteOffset+i,width*height*3).slice(),width,height,components:3}}
// Saves pixels exactly: PNG is lossless; JPEG at quality 95 with full color detail (no color subsampling).
function writePixels(file,px,w,h,format){const head=Buffer.from(`P6\n${w} ${h}\n255\n`),buf=Buffer.concat([head,Buffer.from(px.buffer,px.byteOffset,px.length)]);
 const out=format==="png"?["-strip","-define","png:compression-level=6","PNG24:"+file]:["-strip","-quality",String(JPEG_QUALITY),"-sampling-factor","1x1","JPG:"+file];
 run(["ppm:-",...out],buf)}

// ---------- the plugin's steps (same order as the Photoshop panel) ----------
function anyDecode(r){try{const hc=dense.extract(r.data,r.width,r.height,r.components);if(hc)return hc}catch(e){}try{const bq=brightq.extract(r.data,r.width,r.height,r.components);if(bq)return bq}catch(e){}
 let d=fractionalD(r)||glyphD(r)||colorpopD(r);if(!d)try{d=engine.decodeBlind(r.data,r.width,r.height,r.components,{deep:false,camera:false})}catch(e){}return d}
const colorpopD=r=>{try{return colorpop.decodeColorPop(r.data,r.width,r.height,r.components,{})}catch(e){return null}};
const glyphD=r=>{try{return glyph.decodeGlyphs(r.data,r.width,r.height,r.components,{})}catch(e){return null}};
const fractionalD=r=>{try{return fractional.decodeFractional(r.data,r.width,r.height,r.components,{maxPilotErrors:10})}catch(e){return null}};
function carrierArt(data,r,frame,p){return p.style==="tract"?tract.renderTract(data,r.width,r.height,r.components,frame,{tractCell:p.blindCell,seed:p.seed}).pixels:p.style==="glyph"?glyph.renderGlyphs(data,r.width,r.height,r.components,frame,{glyphCell:p.blindCell,seed:p.seed}).pixels:colorpop.renderColorPop(data,r.width,r.height,r.components,frame,{colorCell:p.blindCell,seed:p.seed}).pixels}
function drawLook(text,plain,p,r){let data=r.data;
 if(p.style==="glyph"||p.style==="colorpop"||p.style==="tract"){if(p.mode==="dense")data=carrierArt(data,r,codec.v3FrameBits(plain.slice(0,64),{style:"none",blindCell:p.blindCell,seed:p.seed}),p)}
 else if(p.style!=="none")data=engine.render({src:r.data,width:r.width,height:r.height,components:r.components,bits:codec.frameBits(p.mode==="dense"?plain.slice(0,64):text),profile:p}).pixels;
 return effects.apply(data,r.width,r.height,r.components,p.fx,p.seed)}
function hide(data,text,p,r){if(p.mode==="dense")return dense.embed(data,r.width,r.height,r.components,text,p.bpc);if(p.style==="none")return brightq.embed(data,r.width,r.height,r.components,text);
 const frame=engine.v3FrameBits(text,{style:p.style,blindCell:p.blindCell,seed:p.seed});return{pixels:p.style==="glyph"||p.style==="colorpop"||p.style==="tract"?carrierArt(data,r,frame,p):engine.applyBlindCarrier(data,r.width,r.height,r.components,frame,p).pixels}}

// ---------- signing key (made once, kept in your home folder) ----------
const KEY_FILE=path.join(os.homedir(),".infostyling","sealkey");
let KEYS=null;
function keys(){if(KEYS)return KEYS;try{KEYS=seal.keysFromSecret(fs.readFileSync(KEY_FILE,"utf8").trim())}catch(e){}
 if(!KEYS){KEYS=seal.newKeys();fs.mkdirSync(path.dirname(KEY_FILE),{recursive:true,mode:0o700});fs.writeFileSync(KEY_FILE,seal.secretText(KEYS),{mode:0o600})}return KEYS}
const sized=(text,name)=>name&&text?seal.placeholder(text,name,keys()):text;

// ---------- commands ----------
function readText(o){if(o.text!=null)return{text:String(o.text)};if(!o.file)return{text:""};if(!fs.existsSync(o.file))throw new Error("Text file not found: "+o.file);
 if(/\.epub$/i.test(o.file)){const b=epub.epubText(new Uint8Array(fs.readFileSync(o.file)));return{text:b.text,book:b}}return{text:fs.readFileSync(o.file,"utf8")}}
function lookId(v){if(!v)throw new Error("Choose a look with --look (for example: --look invisible). Run with --help to see all looks.");const s=String(v).toLowerCase().replace(/[\s_-]/g,"");
 const l=looks.LOOKS.find(l=>l.id===s||l.label.toLowerCase().replace(/[\s_-]/g,"")===s)||(s==="invisible"?looks.byId("none"):null);if(!l)throw new Error(`Unknown look "${v}". Looks: ${looks.LOOKS.map(l=>l.label).join(", ")}`);return l.id}
function route(v){const s=String(v||"share").toLowerCase();if(/^(share|shareable|jpe?g)$/.test(s))return"share";if(/^(full|fullresolution|png)$/.test(s))return"full";throw new Error('--size must be "share" or "full"')}
function fxOpts(list){const fx={};for(const e of list){const m=/^(\w+)=(\d+(?:\.\d+)?)$/.exec(e);if(!m||!effects.EFFECTS.some(x=>x[0]===m[1]))throw new Error(`Bad --effect "${e}". Use NAME=AMOUNT, names: ${effects.EFFECTS.map(x=>x[0]).join(", ")}`);fx[m[1]]={on:true,amount:Math.max(0,Math.min(100,+m[2]))}}return fx}
const num=v=>v.toLocaleString("en-US"),kb=n=>n<10240?n+" bytes":(n/1024).toFixed(n<1048576?0:1)+" KB";

async function cmdSpace(file,o){const r=readPixels(file),{text}=readText(o),name=o.sign||"",rt=route(o.size),s=sized(text,name),bytes=text?codec.utf8Encode(s).length:0;
 if(bytes>pack.BIG){process.stdout.write("Measuring how small your text packs…\n");await pack.prepare(s,codec.utf8Encode(s))}
 console.log(`${path.basename(file)}: ${r.width} x ${r.height} px. ${rt==="share"?"Shareable (JPEG)":"Full resolution (PNG)"}.`);if(text)console.log(`Your text: ${num(text.length)} characters.`);
 const memo={bytes};for(const l of looks.LOOKS){const q=bytes?looks.plan(l.id,r.width,r.height,s,memo,rt):null,f=looks.footprint(l.id,r.width,r.height,q?q.stored:0,rt);
  console.log(`  ${l.label.padEnd(14)} Bytes available: ${num(f.avail).padStart(11)}${q?`   Your text takes: ${num(f.takes)} bytes   ${f.over?`TOO LONG by ${num(f.short)} bytes`:`Bytes left: ${num(f.left)}`}`:""}`)}}

async function cmdHide(file,o){const id=lookId(o.look),rt=route(o.size),png=rt==="full",look=looks.byId(id),{text:plain,book}=readText(o),name=o.sign?String(o.sign):"";
 if(!plain)throw new Error('Give the text to hide with --text "..." or --file book.txt');if(book)console.log(`Loaded ${path.basename(o.file)}: ${book.title||"EPUB"}, ${book.chapters} chapter(s) as plain text.`);
 const r=readPixels(file),s=sized(plain,name);if(!pack.ready(s)){console.log("Compressing your text…");await pack.prepare(s,codec.utf8Encode(s))}
 const q=looks.plan(id,r.width,r.height,s,{},rt);if(!q.fits){const f=looks.footprint(id,r.width,r.height,q.stored,rt);throw new Error(`Too long: your text takes ${num(f.takes)} bytes and ${look.label} has ${num(f.avail)} bytes available at ${png?"Full resolution (PNG)":"Shareable (JPEG)"}.${png?" Use a larger picture.":" Shorten it, or use --size full."}`)}
 const seed=o.seed!=null?Math.trunc(Number(o.seed)||0):DEFAULT_SEED,p={...looks.profile(id,q.cell,seed),mode:png?"dense":"robust",bpc:q.bpc||2,fx:fxOpts(o.effect)};
 console.log(`${look.label}: hiding ${kb(q.bytes)} of text${png?` as a lossless PNG at ${q.bpc} bit/ch`:` as a sharing-safe JPEG (${id==="none"?"8×8 brightness patterns":q.cell+" px marks"})`}…`);
 let text=plain;if(name){const k=keys();let fp;if(p.mode==="dense"||p.style==="none")fp=seal.fingerprint(drawLook(plain,plain,p,r),r.width,r.height,r.components);else{const ph=seal.placeholder(plain,name,k);fp=seal.fingerprint(hide(drawLook(ph,plain,p,r),ph,p,r).pixels,r.width,r.height,r.components)}text=seal.sign(plain,name,k,fp)}
 const e=hide(drawLook(text,plain,p,r),text,p,r),d=anyDecode({...r,data:e.pixels});if(!d||d.text!==text)throw new Error("Verification read-back did not match. Nothing was saved.");
 const out=o.out||path.join(path.dirname(file),path.basename(file).replace(/\.[^.]+$/,"")+`_${id}${png?".png":".jpg"}`);writePixels(out,e.pixels,r.width,r.height,png?"png":"jpg");
 // Re-open the saved file and read it back, as the Photoshop panel does.
 let ok=false,sealLine="";try{const b=readPixels(out),bd=anyDecode(b);ok=!!bd&&bd.text===text;if(ok&&name){const c=seal.check(bd.text,b.data,b.width,b.height,b.components);sealLine=c.line;ok=c.status==="ok"}}catch(err){}
 console.log(`${ok?"✓ APPLIED":"⚠ APPLIED, BUT CHECK FAILED:"} ${look.label}: saved ${out}`);console.log(ok?"Verified: re-opened the saved file and decoded the message (CRC valid).":"WARNING: the saved file did not decode. Try a larger picture.");
 if(sealLine)console.log("Seal on the saved file: "+sealLine);if(name)console.log("Your key ID: "+seal.keyId(keys().publicKey));
 console.log(png?"Share the PNG file itself. JPEG conversion or resizing destroys book-size text.":"Survives JPEG and resizing by social media.");if(!ok)process.exitCode=2}

function cmdRead(file,o){const r=readPixels(file);let d=null,label="",cam=!!o.corners;
 if(!cam){const hc=dense.extract(r.data,r.width,r.height,r.components);if(hc){d=hc;label=`High-capacity decode OK • ${kb(hc.rawBytes)} of text • ${hc.bpc} bit/ch • CRC valid.`}
  if(!d){const bq=brightq.extract(r.data,r.width,r.height,r.components);if(bq){d=bq;label=`Invisible (brightness) decode OK • ${kb(bq.rawBytes)} of text • CRC valid.`}}}
 if(!d){const opts={deep:!o.quick,camera:!!o["angle-search"],rotationHint:Number(o.rotation)||0};
  if(cam){const W=r.width-1,H=r.height-1,qd=String(o.corners).split(";").map(s=>s.trim()).filter(Boolean).map(s=>s.split(",").map(Number));if(qd.length!==4||qd.some(p=>p.length!==2||!p.every(Number.isFinite)))throw new Error("Corners must be TLx,TLy;TRx,TRy;BRx,BRy;BLx,BLy");Object.assign(opts,{quad:qd.map(p=>[p[0]*W/100,p[1]*H/100]),rectWidth:0,rectHeight:0,lensK1:0,lensK2:0})}
  try{d=(!cam&&fractionalD(r))||(!cam&&glyphD(r))||(!cam&&colorpopD(r))||engine.decodeBlind(r.data,r.width,r.height,r.components,opts)}catch(e){throw new Error("No hidden text found ("+e.message+")")}
  label=`${d.carrier==="glyph"?"Glyph hatch":d.carrier==="colorpop"?"Color Pop":"ISB3 "+(cam?"camera":"robust")} decode OK • ${codec.utf8Encode(d.text).length} bytes • style ${d.meta.style} • carrier ${d.cell} px • offset ${d.offX},${d.offY} • ${d.copies||1} tile source(s) • rotation correction ${d.deskewAngle||0}° • CRC valid.`}
 const c=cam?seal.check(d.text,null):seal.check(d.text,r.data,r.width,r.height,r.components);
 console.log(label);console.log(c.line);console.log("----- hidden text -----");console.log(c.text);
 if(o.save){fs.writeFileSync(o.save,c.text,"utf8");console.log("-----------------------");console.log(`Saved ${num(c.text.length)} characters to ${o.save}`)}}

function parse(argv){const o={_:[],effect:[]},flags=new Set(["quick","angle-search","help","version"]);for(let i=0;i<argv.length;i++){const a=argv[i];if(a==="-h")o.help=true;else if(a.startsWith("--")){const k=a.slice(2);if(flags.has(k))o[k]=true;else{const v=argv[++i];if(v==null)throw new Error(`${a} needs a value`);if(k==="effect")o.effect.push(v);else o[k]=v}}else o._.push(a)}return o}
(async()=>{try{const o=parse(process.argv.slice(2)),[cmd,file]=o._;if(o.version){console.log(VERSION);return}if(o.help||!cmd){console.log(HELP);return}
 if(!file)throw new Error("Give the picture file after the command. Run with --help for examples.");
 if(cmd==="hide")await cmdHide(file,o);else if(cmd==="read")cmdRead(file,o);else if(cmd==="space")await cmdSpace(file,o);else throw new Error(`Unknown command "${cmd}". Use hide, read or space.`)}
 catch(e){console.error("✗ "+(e&&e.message||e));process.exitCode=1}})();
