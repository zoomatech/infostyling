"use strict";
// EPUB reader: an EPUB is a zip of XHTML chapters. Unzips it, follows the OPF spine for reading order,
// and returns the chapters as plain text with paragraph breaks, so a whole book can be embedded.
const pako=require("../lib/pako.min.js"),{utf8Decode}=require("./codec.js");
function u16(b,i){return b[i]|b[i+1]<<8}
function u32(b,i){return(b[i]|b[i+1]<<8|b[i+2]<<16|b[i+3]<<24)>>>0}
function isZip(b){return b.length>4&&b[0]===0x50&&b[1]===0x4b&&b[2]===3&&b[3]===4}
// Reads the central directory at the end of the zip and returns {name: () => bytes}.
function unzip(b){let e=-1;for(let i=b.length-22;i>=Math.max(0,b.length-65557);i--)if(u32(b,i)===0x06054b50){e=i;break}if(e<0)throw new Error("Not a zip file.");
 const files={};let p=u32(b,e+16);for(let k=0,n=u16(b,e+10);k<n;k++){if(u32(b,p)!==0x02014b50)throw new Error("Broken zip directory.");const method=u16(b,p+10),size=u32(b,p+20),nl=u16(b,p+28),xl=u16(b,p+30),cl=u16(b,p+32),off=u32(b,p+42),name=utf8Decode(b.subarray(p+46,p+46+nl));
  files[name]=()=>{const s=off+30+u16(b,off+26)+u16(b,off+28),raw=b.subarray(s,s+size);if(method===0)return raw;if(method===8)return pako.inflateRaw(raw);throw new Error(`Unsupported zip method ${method} in ${name}.`)};p+=46+nl+xl+cl}
 return files}
const ENT={amp:"&",lt:"<",gt:">",quot:'"',apos:"'",nbsp:" ",mdash:"—",ndash:"–",hellip:"…",lsquo:"‘",rsquo:"’",ldquo:"“",rdquo:"”",copy:"©",shy:""};
function entities(s){return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi,(m,e)=>e[0]==="#"?String.fromCodePoint(e[1]==="x"||e[1]==="X"?parseInt(e.slice(2),16):parseInt(e.slice(1),10)):ENT[e.toLowerCase()]??m)}
function attr(tag,name){const m=new RegExp(`\\s${name}\\s*=\\s*("([^"]*)"|'([^']*)')`,"i").exec(tag);return m?(m[2]??m[3]):null}
function htmlText(h){return entities(h.replace(/<head[\s\S]*?<\/head>/gi,"").replace(/<(script|style)[\s\S]*?<\/\1>/gi,"").replace(/<br\s*\/?>/gi,"\n")
  .replace(/<\/(p|div|h[1-6]|li|blockquote|tr|section|title)>/gi,"\n\n").replace(/<[^>]+>/g,"")).replace(/[ \t\r\f\v]+/g," ").replace(/ *\n */g,"\n").replace(/\n{3,}/g,"\n\n").trim()}
function resolve(base,href){const parts=(base+decodeURIComponent(href.split("#")[0])).split("/"),out=[];for(const s of parts){if(s===".."){out.pop()}else if(s!=="."&&s!=="")out.push(s)}return out.join("/")}
function epubText(bytes){const b=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes),z=unzip(b),get=n=>{const f=z[n]||z[Object.keys(z).find(k=>k.toLowerCase()===n.toLowerCase())];return f?utf8Decode(f()):null};
 const container=get("META-INF/container.xml");if(!container)throw new Error("Not an EPUB: META-INF/container.xml is missing.");
 const enc=get("META-INF/encryption.xml");if(enc&&/<(?:\w+:)?EncryptedData\b/i.test(enc)&&!/idpf\.org\/2008\/embedding|ns\.adobe\.com\/pdf\/enc#RC/i.test(enc))throw new Error("This EPUB is DRM-protected, so its text can't be read. Use a DRM-free copy.");
 const opfPath=attr(/<rootfile\b[^>]*>/i.exec(container)?.[0]||"","full-path");if(!opfPath)throw new Error("EPUB has no package file.");const opf=get(opfPath);if(!opf)throw new Error(`EPUB package ${opfPath} is missing.`);
 const base=opfPath.includes("/")?opfPath.slice(0,opfPath.lastIndexOf("/")+1):"",items={};for(const t of opf.match(/<(?:\w+:)?item\b[^>]*>/gi)||[]){const id=attr(t,"id"),href=attr(t,"href");if(id&&href)items[id]={href,type:attr(t,"media-type")||""}}
 const title=entities((/<dc:title[^>]*>([\s\S]*?)<\/dc:title>/i.exec(opf)||[])[1]||"").trim(),author=entities((/<dc:creator[^>]*>([\s\S]*?)<\/dc:creator>/i.exec(opf)||[])[1]||"").trim();
 const chapters=[];for(const t of opf.match(/<(?:\w+:)?itemref\b[^>]*>/gi)||[]){const it=items[attr(t,"idref")];if(!it||!/html|xml/i.test(it.type))continue;const h=get(resolve(base,it.href));if(h){const s=htmlText(h);if(s)chapters.push(s)}}
 if(!chapters.length)throw new Error("EPUB has no readable chapters (it may be DRM-protected).");
 const head=[title,author&&`by ${author}`].filter(Boolean).join("\n");return{title,author,chapters:chapters.length,text:(head?head+"\n\n":"")+chapters.join("\n\n")}}
module.exports={epubText,isZip,unzip,htmlText};
