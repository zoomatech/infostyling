"use strict";
const codec=require("./codec.js"),{hash2}=require("./math.js");
const PILOT_SIZE=7,PILOT_RADIUS=3,DATA_OFFSET=5,PILOT=Uint8Array.from([1,1,0,0,1,0,1,0,0,1,1,0,1,1,1,0,1,0,1,1,0,0,1,1,0,0,0,1,1,1,1,0,1,0,0,0,1,0,1,1,1,0,1,0,0,1,0,1,1]);
function mortonDecode(n){let x=0,y=0,b=0;while(n>0){x|=(n&1)<<b;n>>>=1;y|=(n&1)<<b;n>>>=1;b++}return[x,y]}
function mortonEncode(x,y){let n=0,s=0;x>>>=0;y>>>=0;while(x||y){n|=(x&1)<<s++;n|=(y&1)<<s++;x>>>=1;y>>>=1}return n>>>0}
function dataRel(k){const block=Math.floor(k/256),i=k&255,perm=(Math.imul(i,73)+19)&255,q=mortonDecode(block*256+perm);return[DATA_OFFSET+q[0],DATA_OFFSET+q[1]]}
function tilePeriod(n){let max=0;for(let k=0;k<n;k++){const q=dataRel(k);max=Math.max(max,q[0],q[1])}return Math.max(12,5+max)}
function blindCapacityBytes(w,h,cell){const c=Math.max(8,Math.round(cell||16)),limit=Math.min(Math.floor(w/c),Math.floor(h/c));if(limit<12)return 0;let lo=0,hi=65535;while(lo<hi){const m=Math.ceil((lo+hi+1)/2);if(tilePeriod(codec.v3FrameBitLength(m))<=limit)lo=m;else hi=m-1}return lo}
function cellBit(cx,cy,bits,period,seed){const x=((cx%period)+period)%period,y=((cy%period)+period)%period;if(x<=6&&y<=6)return PILOT[y*7+x];if(x>=8&&y>=8){const raw=mortonEncode(x-8,y-8),block=Math.floor(raw/256),perm=raw&255,i=(Math.imul((perm-19)&255,249))&255,k=block*256+i;if(k<bits.length)return bits[k]}return hash2(cx,cy,(seed||0)^0x33c0ffee)>=.5?1:0}
module.exports={PILOT_SIZE,PILOT_RADIUS,PILOT,dataRel,tilePeriod,blindCapacityBytes,cellBit};
