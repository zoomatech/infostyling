"use strict";
const {DEFAULT_SEED,STORAGE_KEY}=require("../config.js"),{EFFECTS}=require("../core/effects.js"),{LOOKS}=require("../core/looks.js");
const $=id=>document.getElementById(id),PREVIEW=20000,DECODED_MAX=5*1024*1024;
class Panel{
 constructor(){this.state={seed:DEFAULT_SEED,fx:{}};this.picked=LOOKS[0].id;this.route="share";this.wired=false;this.fileText=null;this.lastDecoded=""}
 load(){try{const q=JSON.parse(localStorage.getItem(STORAGE_KEY)||"null");if(q)this.state={...this.state,seed:Number.isFinite(q.seed)?q.seed:DEFAULT_SEED,fx:q.fx||{},signName:typeof q.signName==="string"?q.signName:""}}catch(e){}return this}
 save(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(this.state))}catch(e){}}
 status(text){$("status").textContent=text}
 // Apply filter result, under the button: "working" blue, "ok" green, "bad" red.
 result(text,kind){const e=$("lookStatus");e.textContent=text;e.className="lookStatus "+(kind||"")}
 decoded(text){this.lastDecoded=text;$("decoded").value=text.length>DECODED_MAX?text.slice(0,DECODED_MAX)+`\n\n… ${text.length-DECODED_MAX} more characters. Use "Save decoded text…" for the full text.`:text}
 message(){return this.fileText!=null?this.fileText:$("message").value}
 setFile(name,text){this.fileText=text;$("message").value=text.length>PREVIEW?text.slice(0,PREVIEW)+"\n…":text;this.fileName=name}
 seed(){return Math.trunc(Number($("seed").value)||0)}
 // Name to sign with; blank means no seal.
 signName(){const e=$("signName");return e?e.value.trim():""}
 setKeyId(id){const e=$("keyId");if(e)e.textContent=`Your key ID: ${id}. Publish it so people can tell your seal from a counterfeit.`}
 effects(){const fx={};for(const[k]of EFFECTS)fx[k]={on:$("fx_"+k).checked,amount:Number($("fxa_"+k).value)};return fx}
 options(){return{respectSelection:$("respectSelection").checked,keepSource:true,deep:$("deepSearch").checked,camera:$("cameraSearch").checked,rotationHint:Number($("rotationHint").value)||0}}
 camera(){return{quad:$("quad").value,rectWidth:Number($("rectWidth").value)||0,rectHeight:Number($("rectHeight").value)||0,lensK1:Number($("lensK1").value)||0,lensK2:Number($("lensK2").value)||0}}
 buildEffects(){const root=$("effects");root.innerHTML="";for(const[k,label]of EFFECTS){const s=this.state.fx[k]||{on:false,amount:40},d=document.createElement("div");d.className="fx";d.innerHTML=`<label><input id="fx_${k}" type="checkbox"> ${label}</label><input id="fxa_${k}" type="range" min="0" max="100" step="1"><span id="fxv_${k}"></span>`;root.appendChild(d);const c=$("fx_"+k),a=$("fxa_"+k);c.checked=!!s.on;a.value=s.amount;$("fxv_"+k).textContent=String(s.amount);const upd=()=>{this.state.fx[k]={on:c.checked,amount:Number(a.value)};$("fxv_"+k).textContent=a.value;this.save()};c.addEventListener("change",upd);a.addEventListener("input",upd)}}
 // One tile per look: preview, name and note. Clicking a tile picks it; the one Apply filter button applies it.
 buildLooks(onPick){const root=$("looks");root.innerHTML="";for(const l of LOOKS){const d=document.createElement("div");d.className="tile";d.id="tile_"+l.id;d.innerHTML=`<div class="ph" id="ph_${l.id}"></div><sp-radio class="name" id="name_${l.id}" value="${l.id}">${l.label}</sp-radio><div class="route" id="route_${l.id}">${l.note}</div><div class="route" id="space_${l.id}"></div>`;root.appendChild(d);d.addEventListener("click",()=>onPick(l.id))}}
 // Shows which look and which size are picked, and names both on the Apply filter button.
 pick(id,route){if(id)this.picked=id;if(route)this.route=route;for(const l of LOOKS){const t=$("tile_"+l.id),n=$("name_"+l.id),on=l.id===this.picked;if(t)t.className=on?"tile picked":"tile";if(n){if(on)n.setAttribute("checked","");else n.removeAttribute("checked")}}
  const sh=this.route==="share";for(const[e,on]of[[$("outShare"),sh],[$("outFull"),!sh]]){if(on)e.setAttribute("checked","");else e.removeAttribute("checked")}
  if(!this.busy)$("applyFilter").textContent=`Apply filter: ${LOOKS.find(l=>l.id===this.picked).label}, ${sh?"Shareable (JPEG)":"Full resolution (PNG)"}`}
 setTileSpace(id,text,over){const e=$("space_"+id);if(!e)return;e.textContent=text;e.className=over?"route over":"route"}
 setSpace(text,over){const e=$("space");e.textContent=text;e.className=over?"space over":"space"}
 setPreview(id,dataUrl){const ph=$("ph_"+id);if(!ph)return;let img=ph.tagName==="IMG"?ph:null;if(!img){img=document.createElement("img");img.id="ph_"+id;ph.parentNode.replaceChild(img,ph)}img.src=dataUrl}
 clearPreviews(){for(const l of LOOKS){const e=$("ph_"+l.id);if(e&&e.tagName==="IMG"){const d=document.createElement("div");d.className="ph";d.id="ph_"+l.id;e.parentNode.replaceChild(d,e)}}}
 // Apply filter shows "Working… please wait" and is disabled while it runs.
 setBusy(on){this.busy=on;const b=$("applyFilter");if(on){b.setAttribute("disabled","");b.textContent="Working… please wait"}else{b.removeAttribute("disabled");this.pick()}}
 setSize(text,over){const e=$("payloadSize");e.textContent=text;e.className=over?"small over":"small"}
 bind(actions){if(this.wired)return;this.wired=true;this.load();$("seed").value=this.state.seed;$("signName").value=this.state.signName||"";this.buildEffects();
  const run=(fn,label)=>(...args)=>Promise.resolve().then(()=>{if(typeof fn!=="function")throw new Error("button is not wired");return fn(...args)}).catch(e=>this.status(label+" failed: "+e.message));
  this.buildLooks(id=>{this.pick(id);actions.capacity(true)});this.pick();
  $("outShare").addEventListener("click",()=>{this.pick(null,"share");actions.capacity(true)});$("outFull").addEventListener("click",()=>{this.pick(null,"full");actions.capacity(true)});
  $("applyFilter").addEventListener("click",()=>{if(this.busy)return;this.setBusy(true);this.result(`Applying ${LOOKS.find(l=>l.id===this.picked).label}…`,"working");Promise.resolve().then(()=>actions.oneClick(this.picked,this.route)).catch(e=>this.result("✗ NOT APPLIED. "+e.message,"bad")).then(()=>this.setBusy(false))});
  $("seed").addEventListener("change",()=>{this.state.seed=this.seed();this.save();actions.previews(true)});
  $("message").addEventListener("input",()=>{if(this.fileText!=null){this.fileText=null;this.fileName=null}actions.capacity()});
  $("signName").addEventListener("input",()=>{this.state.signName=$("signName").value;this.save();actions.capacity(true)});
  $("clearText").addEventListener("click",()=>{this.fileText=null;this.fileName=null;$("message").value="";actions.capacity()});
  const btn=(id,fn,label)=>$(id).addEventListener("click",run(fn,label));
  btn("decodeBlind",()=>actions.decode(false),"Read");btn("decodeCamera",()=>actions.decode(true),"Camera read");btn("decodePaired",actions.paired,"Paired read");btn("loadFile",actions.loadFile,"Load file");btn("saveFile",actions.saveFile,"Save file");btn("refreshPreviews",()=>actions.previews(true),"Preview");
  $("advToggle").addEventListener("click",()=>{const a=$("advanced"),open=a.className==="hidden";a.className=open?"":"hidden";$("advToggle").textContent=(open?"Hide":"Show")+" advanced settings "+(open?"▾":"▸")});
  setInterval(()=>{actions.capacity();actions.previews(false)},1800);actions.capacity();actions.previews(false)}
}
module.exports={Panel};
