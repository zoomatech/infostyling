"use strict";
// One-click shortcut settings. Pure functions so they can be tested outside Photoshop.
const layout=require("./layout.js"),dense=require("./dense.js"),codec=require("./codec.js");
const SOCIAL={style:"none",blindStrength:74,fx:{}},SOCIAL_CELLS=[16,20,24,28,32,40],SMALL_CELL=12,SHARE_SIDE=2048,MIN_SHARED_CELL=8;
// Smallest carrier cell that still spans ~8 px after a platform resizes the long side to 2048.
// Images already at or under 2048 px are not downscaled, so they can use a finer 12 px cell.
function socialCell(w,h){const L=Math.max(w,h);if(L<=SHARE_SIDE)return SMALL_CELL;for(const c of SOCIAL_CELLS)if(c*SHARE_SIDE/L>=MIN_SHARED_CELL)return c;return SOCIAL_CELLS[SOCIAL_CELLS.length-1]}
function socialPlan(w,h,text){const cell=socialCell(w,h),cap=layout.blindCapacityBytes(w,h,cell),raw=codec.utf8Encode(text||"").length,bytes=raw?codec.robustStoredBytes(text):0;return{cell,cap,bytes,raw,fits:bytes>0&&bytes<=cap}}
// Fewest bits per channel (start at 1, invisible) that hold the compressed text.
function bookPlan(w,h,n,text,slotCount){const slots=slotCount==null?w*h*Math.min(3,n):slotCount,{raw,data}=dense.pack(text);for(let bpc=1;bpc<=4;bpc++){const cap=dense.capacityBytes(slots,bpc);if(data.length<=cap)return{bpc,cap,stored:data.length,raw:raw.length}}return{bpc:0,cap:dense.capacityBytes(slots,4),stored:data.length,raw:raw.length}}
module.exports={SOCIAL,socialCell,socialPlan,bookPlan};
