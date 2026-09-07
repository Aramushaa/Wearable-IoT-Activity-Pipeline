const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/ads.js','utf8');
function setup(native){const data=new Map();const env={window:{AndroidAds:native},localStorage:{getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)},setTimeout:()=>1,clearTimeout:()=>{},Promise};vm.createContext(env);vm.runInContext(source,env);return{ads:env.window.GateAds,receive:env.window.GateAdsNative.receive,data};}
(async()=>{
 const browser=setup();assert.equal(await browser.ads.reward(),false);assert.equal(browser.ads.bonus(),0);
 let id,requests=0;const native=setup({reward:v=>{id=v;requests++;},refresh(){}});
 native.receive({type:'status',ready:true,eligible:false});assert.equal(await native.ads.reward(),false);
 native.receive({type:'status',ready:true,eligible:true});
 let p=native.ads.reward();assert.equal(await native.ads.reward(),false,'duplicate click cannot open another ad');
 native.receive({type:'reward',id:'invalid',earned:true});assert.equal(native.ads.bonus(),0,'ignore unpaired callback');
 native.receive({type:'reward',id,earned:false});assert.equal(await p,false);assert.equal(native.ads.bonus(),0);
 p=native.ads.reward();native.receive({type:'reward',id,earned:true});assert.equal(await p,true);assert.equal(native.ads.bonus(),15);
 assert.equal(await native.ads.reward(),false,'no stacking rewards');assert.equal(native.ads.consumeBonus(),15);assert.equal(native.ads.consumeBonus(),0);
 native.receive({type:'reward',id,earned:true});assert.equal(native.ads.bonus(),0,'ignore replayed reward callback');
 assert.equal(requests,2);console.log('PASS: browser fallback, age restriction, duplicate protection, skipped ads, earned reward, one-time consumption and stale callbacks.');
})();
