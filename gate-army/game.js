(() => {
'use strict';
const $ = id => document.getElementById(id);
const canvas = $('game'), ctx = canvas.getContext('2d');
const levels = [
  {name:'Emerald Landing', biome:'THE OUTER ISLANDS', sky:'#cfefe5', water:'#53b7b8', land:'#70b89a', road:'#eceddb', enemy:100, speed:98, goal:65, story:'Commander, the Crimson Legion has taken our islands. Rescue the scouts on Emerald Bridge and reclaim our first beacon.', end:'The first beacon is lit. Our scouts spotted a Legion convoy heading into the canyon.'},
  {name:'Amber Canyon', biome:'THE SUNKEN CANYON', sky:'#ffe3b5', water:'#df9c70', land:'#c68053', road:'#f7e0b8', enemy:160, speed:108, goal:100, story:'The canyon is full of moving blades. Recover a shield, protect your recruits, and break the convoy at the far bridge.', end:'The canyon is ours. A radio signal is coming from the frozen relay station.'},
  {name:'Frost Relay', biome:'THE NORTHERN PASS', sky:'#d9eafa', water:'#82aeca', land:'#c7deea', road:'#f2f7ff', enemy:210, speed:116, goal:130, story:'Our engineers are trapped beyond the frozen pass. Rescue them and push through the Legion patrols to restore the relay.', end:'The relay is online. We have coordinates for the enemy’s night harbor.'},
  {name:'Neon Harbor', biome:'BEHIND ENEMY LINES', sky:'#8a9fca', water:'#394e88', land:'#63719c', road:'#c8d6e8', enemy:270, speed:122, goal:160, story:'The harbor never sleeps. Moving traps and patrols guard the last supply route. Build a huge squad before the final push.', end:'Their supply route is cut. Only the Crimson Citadel remains.'},
  {name:'Crimson Citadel', biome:'THE FINAL ASSAULT', sky:'#f1b8b2', water:'#945f7f', land:'#ac7988', road:'#e8d5cd', enemy:340, speed:128, goal:200, story:'Every rescued soldier brought us here. Cross the citadel bridge, time your rally strike, and free the islands for good.', end:'All five beacons shine again. The islands are free. Replay any mission to earn every medal.'}
];
const art=window.EmpireArt, sound=window.EmpireAudio, ads=window.GateAds;
let adState={native:false,ready:false,eligible:false,busy:false}, rewardClaimed=false;
function adUI(){const allowed=phase==='won'||phase==='lost';$('reward-ad').hidden=!adState.native||!adState.eligible||!allowed;$('reward-ad').disabled=!adState.ready||adState.busy||rewardClaimed||ads.bonus()>0;$('reward-ad').textContent=ads.bonus()?'15 REINFORCEMENTS READY':adState.busy?'AD PLAYING…':'WATCH AD · +15 NEXT RUN';$('ad-message').textContent=allowed&&adState.native?adState.message||'':'';$('play').disabled=adState.busy;$('secondary').disabled=adState.busy;}
levels.forEach((l,i)=>{const c=art.cultures[i];Object.assign(l,{name:c.island,biome:c.biome,sky:c.sky,water:c.water,land:c.land,road:c.road,story:[
 'Emperor Aurelius guards the laurel island. Lead your legionaries through his marble causeway, gather allies, and claim the first imperial banner.',
 'King Leandros holds the Aegean acropolis. Take up bronze armor and round shields, dodge the moving traps, and march on his hilltop temple.',
 'Shah Ardeshir awaits at Saffron Palace. Your Immortals march in patterned armor beneath purple standards. Rescue allies before crossing his palace gates.',
 'Pharaoh Neferu rules the Temple of Dawn. Lead the Sun Guard along the river, gather your scattered warriors, and rally beneath the pyramids.',
 'High King Eirik commands Frosthold. Your shieldbearers must cross the fjord and break the last guard. Unite the five islands beneath your banner.'
 ][i],end:i===4?'The five banners are united. Your warriors have become legends. Replay the islands to perfect your campaign.':c.ruler+' yields the island. Your next army and its homeland await across the sea.'});});
let outfit=-1;try{const v=localStorage.getItem('gate-army-outfit');if(v!==null&&Number.isInteger(Number(v)))outfit=Math.max(-1,Math.min(4,Number(v)));}catch{}
const outfitIndex=()=>outfit<0?stage:outfit;
let saved={medals:[0,0,0,0,0],unlocked:0,best:0};
try { const data=JSON.parse(localStorage.getItem('gate-army-campaign-v2')); if(data) saved={medals:Array.from({length:5},(_,i)=>Math.max(0,Math.min(3,Number(data.medals?.[i])||0))),unlocked:Math.max(0,Math.min(4,Number(data.unlocked)||0)),best:Math.max(0,Number(data.best)||0)}; } catch {}
let w=380,h=680,phase='ready',stage=saved.unlocked,count=12,x=0,target=0,distance=0,last=0,time=0;
let events=[],particles=[],enemy=0,shield=0,rescued=0,hits=0,combo=0,peak=12,toast='',toastTime=0,shake=0;
let battleTime=0,battleTick=0,battleStart=1,rallyUsed=false,resumePhase='running',muted=true,audio,keys={};
const FINISH=2500, SEE=850;
const running=()=>phase==='running'||phase==='battle';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function persist(){try{localStorage.setItem('gate-army-campaign-v2',JSON.stringify(saved));}catch{}}
function resize(){const r=canvas.getBoundingClientRect();w=r.width;h=r.height;const d=Math.min(devicePixelRatio||1,2);canvas.width=w*d;canvas.height=h*d;ctx.setTransform(d,0,0,d,0,0);}
new ResizeObserver(resize).observe(canvas);
function tone(freq=600){sound.fx(freq>=850?'win':freq<200?'hit':'grow');}
function wardrobe(){
 const selected=outfitIndex();$('uniform-name').textContent=art.cultures[selected].name.toUpperCase()+' '+art.cultures[selected].unit.toUpperCase();
 $('outfit-auto').setAttribute('aria-pressed',String(outfit===-1));
 document.querySelectorAll('[data-outfit]').forEach(b=>{const i=Number(b.dataset.outfit);b.setAttribute('aria-pressed',String(outfit===i));const c=b.querySelector('canvas'),p=c.getContext('2d');p.clearRect(0,0,c.width,c.height);art.warrior(p,70,105,3.4,i,0,false,0);});
}
function ui(){
 wardrobe();adUI();
 $('level').textContent=`${String(stage+1).padStart(2,'0')} · ${levels[stage].name.toUpperCase()}`;
 $('best').textContent='BEST '+saved.best;
 $('stages').innerHTML=levels.map((l,i)=>`<button class="mission ${i===stage?'active':''}" data-stage="${i}" ${i>saved.unlocked?'disabled':''} title="${l.name}"><b>${i>saved.unlocked?'⌑':i+1}</b><span>${l.name}<small>${'★'.repeat(saved.medals[i])+'☆'.repeat(3-saved.medals[i])}</small></span></button>`).join('');
 $('stages').querySelectorAll('button').forEach(b=>b.onclick=()=>{if(adState.busy)return;stage=Number(b.dataset.stage);brief();});
 $('shield').textContent=shield?'◆ SHIELD READY':'◇ NO SHIELD';
 $('rescues').textContent=`${rescued}/2 RESCUED`;
 $('mission-goal').textContent=`BONUS MEDALS: RESCUE BOTH • FINISH WITH ${levels[stage].goal}+`;
}
function overlay(badge,title,message,button,hint){$('overlay').classList.remove('hidden');$('badge').textContent=badge;$('title').innerHTML=title;$('message').textContent=message;$('play').innerHTML=button+' <span>↗</span>';$('hint').textContent=hint;}
function brief(){if(adState.busy)return;phase='ready';distance=0;count=12+ads.bonus();enemy=levels[stage].enemy;x=target=0;events=makeEvents(stage);shield=rescued=hits=0;particles=[];toastTime=0;$('progress').style.width='0%';$('rally').hidden=true;$('secondary').hidden=true;$('report').innerHTML='';$('status').textContent=levels[stage].biome;ui();overlay('MISSION '+String(stage+1).padStart(2,'0'),levels[stage].name.replace(' ','<br>'),levels[stage].story,'DEPLOY SQUAD','3 MEDALS: WIN · RESCUE BOTH · '+levels[stage].goal+'+ SURVIVORS');}
function makeEvents(s){
 const gate=(z,a,b)=>({z,type:'gate',ops:[a,b]});
 const saw=(z,x,moving=false)=>({z,type:'saw',x,moving,loss:14+s*5});
 const pickup=(z,type,x)=>({z,type,x});
 return [gate(190,['+',18+s*3],['×',2]),pickup(335,'rescue',.53),saw(490,-.5,s>0),
 gate(670,s%2?['+',18]:['×',3],s%2?['×',3]:['+',18]),pickup(820,'shield',-.53),
 ...(s>=2?[{z:970,type:'patrol',x:.5,loss:20+s*5}]:[saw(970,.48)]),
 gate(1140,['−',15],['+',35+s*5]),saw(1330,0,s>0),pickup(1500,'rescue',-.53),
 gate(1680,s%2?['×',2]:['÷',2],s%2?['÷',2]:['×',2]),
 ...(s>=3?[{z:1860,type:'patrol',x:-.5,loss:35+s*5}]:[saw(1860,-.5,s>0)]),
 pickup(2020,'shield',.53),gate(2200,['+',45],['×',2]),...(s===4?[saw(2340,.5,true)]:[])
 ];
}
function start(){if(adState.busy)return;rewardClaimed=false;count=12+ads.consumeBonus();x=target=distance=0;events=makeEvents(stage);particles=[];enemy=levels[stage].enemy;shield=rescued=hits=combo=0;peak=count;toastTime=shake=0;phase='running';$('overlay').classList.add('hidden');$('rally').hidden=true;$('pause').textContent='Ⅱ';$('pause').setAttribute('aria-label','Pause game');$('status').textContent='RECLAIM THE BEACON';$('progress').style.width='0%';ui();sound.fx('start');}
function burst(px,py,color,n=20){for(let i=0;i<n;i++)particles.push({x:px,y:py,vx:(Math.random()-.5)*220,vy:-40-Math.random()*180,life:.8+Math.random()*.6,color});}
function announce(text,color='#287ce1'){toast=text;toastTime=1.2;burst(w/2+x*w*.34,h*.77,color);sound.fx(text.includes('RESCUED')?'rescue':text.includes('SHIELD')?'shield':text.includes('RALLY')?'rally':color==='#e85369'?'hit':'grow');}
function damage(amount){combo=0;if(shield){shield=0;announce('SHIELD BLOCK!','#18a8a9');}else{const loss=Math.min(count,amount);count-=loss;hits++;shake=.25;announce('−'+loss,'#e85369');}ui();}
function eventX(e){return e.moving?Math.sin((distance-e.z)*.008+e.z)*.62:e.x;}
function resolve(e){if(e.type==='gate'){const [op,v]=e.ops[x<0?0:1],old=count;count=op==='+'?count+v:op==='−'?Math.max(0,count-v):op==='×'?count*v:Math.floor(count/v);if(count>old){combo++;const bonus=combo>=3?5:0;count+=bonus;announce('+'+(count-old)+(bonus?' · STREAK!':''));}else{combo=0;announce('−'+(old-count),'#e85369');}}
 else if(Math.abs(x-eventX(e))<.3){if(e.type==='rescue'){rescued++;count+=15;announce('+15 RESCUED','#299c81');}else if(e.type==='shield'){shield=1;announce('SHIELD READY','#18a8a9');}else damage(e.loss);}
 peak=Math.max(peak,count);ui();if(count<=0)result(false);
}
function result(win){phase=win?'won':'lost';ads.refresh();$('rally').hidden=true;const medals=win?1+(rescued===2?1:0)+(count>=levels[stage].goal?1:0):0;
 if(win){saved.medals[stage]=Math.max(saved.medals[stage],medals);saved.unlocked=Math.max(saved.unlocked,Math.min(4,stage+1));burst(w/2,h*.4,'#c2f86d',65);}
 saved.best=Math.max(saved.best,peak);persist();ui();$('secondary').hidden=false;$('secondary').textContent=win?'REPLAY FOR MORE MEDALS':'MISSION BRIEFING';
 $('report').innerHTML=`<div class="medals">${'★'.repeat(medals)}<span>${'☆'.repeat(3-medals)}</span></div><div class="report-grid"><span><b>${count}</b>SURVIVORS</span><span><b>${rescued}/2</b>RESCUES</span><span><b>${peak}</b>PEAK SQUAD</span></div>`;
 overlay(win?'BEACON RECLAIMED':'THE SQUAD NEEDS YOU',win?(stage===4?'Islands<br>liberated!':'Outpost<br>reclaimed.'):'Regroup.<br>Come back bigger.',win?levels[stage].end:'Pick stronger gates, collect shields, and save your rally strike for the green zone.',win?(stage===4?'REPLAY CAMPAIGN':'NEXT MISSION'):'RETRY MISSION',`MEDALS: WIN · RESCUE BOTH · ${levels[stage].goal}+ SURVIVORS`);
 $('status').textContent=win?'MISSION COMPLETE':'MISSION FAILED';sound.fx(win?'win':'lose');
}
function rally(){if(phase!=='battle'||rallyUsed)return;rallyUsed=true;const timing=(Math.sin(battleTime*2.5)+1)/2;const perfect=timing>.68&&timing<.9;const loss=Math.min(enemy,perfect?Math.ceil(levels[stage].enemy*.32):Math.ceil(levels[stage].enemy*.12));enemy-=loss;announce(perfect?'PERFECT RALLY!':'RALLY STRIKE',perfect?'#299c81':'#287ce1');$('rally').hidden=true;if(enemy<=0)result(count>0);}
function update(dt){if(running()){time+=dt;toastTime-=dt;shake=Math.max(0,shake-dt);}
 if(phase==='running'){
 if(keys.ArrowLeft||keys.a)target-=dt*1.8;if(keys.ArrowRight||keys.d)target+=dt*1.8;target=clamp(target,-.8,.8);x+=(target-x)*Math.min(1,dt*13);distance+=dt*levels[stage].speed;
 $('progress').style.width=Math.min(100,distance/FINISH*100)+'%';
 for(const e of events){if(!e.done&&distance>=e.z){e.done=true;resolve(e);if(phase!=='running')break;}}
 if(phase==='running'&&distance>=FINISH){distance=FINISH;phase='battle';battleTime=battleTick=0;battleStart=count;rallyUsed=false;$('rally').hidden=false;$('status').textContent='TAP RALLY IN THE GREEN ZONE';}
 }else if(phase==='battle'){
 battleTime+=dt;battleTick+=dt;x+=(0-x)*Math.min(1,dt*5);
 // The opening beat gives the player time to read the rally action.
 if(battleTime>1.6&&battleTick>.08){battleTick=0;const amount=Math.min(enemy,count,Math.max(1,Math.ceil(levels[stage].enemy/65)));enemy-=amount;count-=amount;burst(w/2+(Math.random()-.5)*70,h*.71,'#ffce74',3);if(count<=0||enemy<=0)result(count>0);}
 }
 if(phase!=='paused'){particles.forEach(p=>{p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=220*dt;p.life-=dt;});particles=particles.filter(p=>p.life>0);}
}
function rr(px,py,width,height,r,fill){ctx.fillStyle=fill;ctx.beginPath();ctx.roundRect(px,py,Math.max(0,width),Math.max(0,height),r);ctx.fill();}
function text(t,px,py,size=16,color='#193a50'){ctx.font=`800 ${size}px "DM Sans",sans-serif`;ctx.textAlign='center';ctx.fillStyle=color;ctx.fillText(t,px,py);}
function poly(points,color){ctx.beginPath();points.forEach(([a,b],i)=>i?ctx.lineTo(a,b):ctx.moveTo(a,b));ctx.closePath();ctx.fillStyle=color;ctx.fill();}
function project(z){const t=1-clamp(z/SEE,0,1);return {y:h*.23+Math.pow(t,1.7)*h*.56,scale:.15+t*.85};}
function soldier(px,py,s,color,t=0,role=1){const foe=color==='#e25770';art.warrior(ctx,px,py,s,foe?stage:outfitIndex(),t,foe,role);}
function crowd(n,cx,cy,scale,color,t){const visible=Math.min(88,Math.max(0,n)),arr=[];for(let i=0;i<visible;i++){const a=i*2.39996,r=Math.sqrt(i)*7.7*scale;arr.push({x:cx+Math.cos(a)*r,y:cy+Math.sin(a)*r*.57,i});}arr.sort((a,b)=>a.y-b.y).forEach(p=>soldier(p.x,p.y,scale*(p.i===0?1.22:1),color,t+p.i,p.i===0?0:1));}
function scenery(){const l=levels[stage],g=ctx.createLinearGradient(0,0,0,h);g.addColorStop(0,l.sky);g.addColorStop(1,l.water);ctx.fillStyle=g;ctx.fillRect(0,0,w,h);
 ctx.fillStyle='#ffffff70';ctx.beginPath();ctx.arc(w*.78,h*.19,26,0,Math.PI*2);ctx.fill();
 for(let i=0;i<6;i++){const xx=(i*97+Math.sin(i)*25)%w,yy=h*.19+(i%3)*20;poly([[xx-70,yy+35],[xx,yy-20],[xx+60,yy+35]],l.land);}
 art.building(ctx,w*.16,h*.285,.43,stage);art.building(ctx,w*.88,h*.29,.33,stage);
 // Layered shoreline, softly lit water and drifting highlights.
 for(let i=0;i<22;i++){const yy=h*.3+((i*47+distance*.22)%(h*.68));const xx=(Math.sin(i*2.7)*.5+.5)*w;ctx.fillStyle='#ffffff24';ctx.beginPath();ctx.ellipse(xx,yy,7+i%4*4,1.2,0,0,Math.PI*2);ctx.fill();}
 for(let i=0;i<14;i++){const z=(i*91-distance*.6)%1100;const p=project((z+1100)%1100),side=i%2?1:-1,xx=w/2+side*(w*.48*p.scale+25);ctx.fillStyle='#ffffff25';ctx.beginPath();ctx.ellipse(xx,p.y,22*p.scale,5*p.scale,0,0,Math.PI*2);ctx.fill();if(i%3===0){poly([[xx-18*p.scale,p.y],[xx-10*p.scale,p.y-22*p.scale],[xx+13*p.scale,p.y-12*p.scale],[xx+22*p.scale,p.y+2]],l.land);}}
 const hy=h*.23;poly([[w*.438,hy],[w*.562,hy],[w*1.02,h],[w*-.02,h]],'#354e6660');poly([[w*.442,hy],[w*.558,hy],[w*.97,h],[w*.03,h]],l.road);
 for(let i=0;i<12;i++){const p=project(i*90-distance%90);ctx.strokeStyle='#ffffff6a';ctx.lineWidth=Math.max(1,p.scale*2);ctx.beginPath();ctx.moveTo(w/2-w*.4*p.scale,p.y);ctx.lineTo(w/2+w*.4*p.scale,p.y);ctx.stroke();}
 for(let i=0;i<9;i++){const p=project(i*110-distance%110);for(const side of [-1,1]){const px=w/2+side*w*.44*p.scale;ctx.fillStyle=art.cultures[stage].gold;ctx.fillRect(px,p.y-32*p.scale,2*p.scale,33*p.scale);poly([[px+2*p.scale,p.y-31*p.scale],[px+18*p.scale,p.y-28*p.scale],[px+15*p.scale,p.y-15*p.scale],[px+2*p.scale,p.y-18*p.scale]],art.cultures[stage].cloth);}}
 for(const side of [-1,1]){ctx.strokeStyle='#ffffffbb';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(w/2+side*w*.058,hy);ctx.lineTo(w/2+side*w*.46,h);ctx.stroke();for(let i=0;i<8;i++){const p=project(i*120-distance%120),xx=w/2+side*w*.415*p.scale;rr(xx-3*p.scale,p.y-18*p.scale,6*p.scale,22*p.scale,2,'#759da5');rr(xx-4*p.scale,p.y-20*p.scale,8*p.scale,4*p.scale,1,'#d9ffda');}}
}
function drawEvent(e){const p=project(e.z-distance),s=p.scale;if(e.type==='gate'){
 e.ops.forEach((op,i)=>{const gx=w/2+(i?1:-1)*w*.2*s,gw=w*.37*s,gh=90*s,good=op[0]==='+'||op[0]==='×',color=good?'#258fe7':'#e65970';rr(gx-gw/2+4*s,p.y-gh+5*s,gw,gh,5*s,'#183b6220');const glass=ctx.createLinearGradient(0,p.y-gh,0,p.y);glass.addColorStop(0,good?'#50c8ffba':'#ff9aafb0');glass.addColorStop(1,good?'#50c8ff18':'#ff9aaf18');rr(gx-gw/2,p.y-gh,gw,gh,5*s,glass);rr(gx-gw/2,p.y-gh,gw,7*s,2,color);rr(gx-gw/2,p.y-gh,5*s,gh,2,color);rr(gx+gw/2-5*s,p.y-gh,5*s,gh,2,color);text(op.join(''),gx,p.y-gh*.35,34*s,good?'#1262b5':'#bb294b');text(good?'GROW':'CAUTION',gx,p.y-gh*.76,7*s,good?'#1262b5':'#bb294b');});
 }else {const px=w/2+eventX(e)*w*.34*s;
 if(e.type==='saw'){if(e.moving){ctx.strokeStyle='#dc69796b';ctx.lineWidth=3*s;ctx.beginPath();ctx.moveTo(w/2-w*.24*s,p.y);ctx.lineTo(w/2+w*.24*s,p.y);ctx.stroke();}ctx.fillStyle='#183b6230';ctx.beginPath();ctx.ellipse(px,p.y+4*s,26*s,8*s,0,0,Math.PI*2);ctx.fill();ctx.save();ctx.translate(px,p.y-10*s);ctx.rotate(time*8);const pts=[];for(let j=0;j<32;j++){const a=j*Math.PI/16,r=(j%2?18:26)*s;pts.push([Math.cos(a)*r,Math.sin(a)*r]);}poly(pts,'#db5069');ctx.fillStyle='#e4edf1';ctx.beginPath();ctx.arc(0,0,15*s,0,Math.PI*2);ctx.fill();ctx.fillStyle='#576b81';ctx.beginPath();ctx.arc(0,0,6*s,0,Math.PI*2);ctx.fill();ctx.restore();
 }else if(e.type==='patrol'){crowd(12,px,p.y-5*s,s,'#e25770',time*10);rr(px-23*s,p.y-52*s,46*s,20*s,6*s,'#b72d52');text('−'+e.loss,px,p.y-37*s,12*s,'white');
 }else {const bob=Math.sin(time*4+e.z)*4*s;ctx.fillStyle=e.type==='shield'?'#46d7e339':'#66c99740';ctx.beginPath();ctx.ellipse(px,p.y,25*s,9*s,0,0,Math.PI*2);ctx.fill();if(e.type==='shield'){poly([[px-16*s,p.y-37*s+bob],[px+16*s,p.y-37*s+bob],[px+13*s,p.y-16*s+bob],[px,p.y-5*s+bob],[px-13*s,p.y-16*s+bob]],'#25b1be');text('◆',px,p.y-17*s+bob,19*s,'#d5ffff');}else{crowd(5,px,p.y-8*s+bob,s,'#30aa8b',time*8);text('+15',px,p.y-38*s+bob,15*s,'#08745f');}}
 }}
function fortress(){if(FINISH-distance>SEE)return;const p=project(FINISH-distance),s=p.scale,yy=p.y;art.building(ctx,w/2,yy-24*s,1.65*s,stage);const by=phase==='battle'?h*.72:yy-10*s;crowd(enemy,w/2,by,s,'#e25770',time*11);rr(w/2-38*s,yy-131*s,76*s,24*s,8*s,'#902b45');text(enemy,w/2,yy-113*s,15*s,'white');text(art.cultures[stage].ruler.toUpperCase(),w/2,yy-145*s,10*s,'#60303f');}
function draw(){ctx.clearRect(0,0,w,h);ctx.save();if(shake>0)ctx.translate(Math.sin(time*110)*shake*15,0);scenery();fortress();events.filter(e=>!e.done&&e.z-distance<SEE&&e.z-distance>-30).sort((a,b)=>b.z-a.z).forEach(drawEvent);
 const cx=w/2+x*w*.34,cy=phase==='battle'?h*.8:h*.79;
 if(shield){ctx.strokeStyle='#35c5d7bb';ctx.lineWidth=3;ctx.fillStyle='#67e4ee20';ctx.beginPath();ctx.ellipse(cx,cy-8,70,44,0,0,Math.PI*2);ctx.fill();ctx.stroke();}
 crowd(count,cx,cy,1.12,'#2788e7',time*14);rr(cx-28,cy-78,56,29,11,'#ffffff');text(count,cx,cy-57,18,'#1468bc');
 if(phase==='running'&&combo>=2)text('GATE STREAK '+combo,cx,cy+48,9,'#156ea5');
 if(toastTime>0){ctx.globalAlpha=Math.min(1,toastTime*3);text(toast,w/2,h*.52-(1.2-toastTime)*16,22,toast.startsWith('−')?'#c83354':'#126b93');ctx.globalAlpha=1;}
 ctx.restore();
 if(phase==='battle'){const bx=w*.15,by=h*.39,bw=w*.7;rr(bx-12,by-28,bw+24,72,12,'#132b48e8');text(rallyUsed?'RALLY USED · HOLD THE LINE':'TIME YOUR RALLY',w/2,by-8,11,'#fff');rr(bx,by,bw,10,5,'#586a84');rr(bx+bw*.68,by,bw*.22,10,2,'#c2f86d');if(!rallyUsed){const t=(Math.sin(battleTime*2.5)+1)/2;rr(bx+bw*t-3,by-4,6,18,3,'white');}text('ENEMY '+enemy+'    /    SQUAD '+count,w/2,by+31,10,'#d1dfeb');}
 particles.forEach(p=>{ctx.globalAlpha=clamp(p.life,0,1);rr(p.x,p.y,5,8,2,p.color);});ctx.globalAlpha=1;
}
function frame(t){sound.update(stage,phase);const dt=Math.min(.04,(t-last)/1000||0);last=t;update(dt);draw();requestAnimationFrame(frame);}
function steer(e){if(phase!=='running')return;const r=canvas.getBoundingClientRect();target=clamp(((e.clientX-r.left)/w-.5)/.34,-.8,.8);}
canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);steer(e);});canvas.addEventListener('pointermove',e=>{if(e.pointerType==='mouse'||e.buttons)steer(e);});
function pause(){if(running()){resumePhase=phase;phase='paused';$('rally').hidden=true;$('secondary').hidden=false;$('secondary').textContent='RESTART MISSION';$('report').innerHTML='';overlay('TAKE A BREATHER','Run paused.','Your squad is waiting. Resume the mission or make a fresh start.','RESUME','SPACE TO RESUME');$('pause').textContent='▶';$('pause').setAttribute('aria-label','Resume game');}else if(phase==='paused'){phase=resumePhase;$('overlay').classList.add('hidden');$('rally').hidden=phase!=='battle'||rallyUsed;$('pause').textContent='Ⅱ';$('pause').setAttribute('aria-label','Pause game');}}
$('play').onclick=()=>{if(phase==='paused')return pause();if(phase==='won'){if(stage<4){stage++;brief();}else{stage=0;brief();}return;}start();};
$('secondary').onclick=()=>phase==='lost'?brief():start();$('pause').onclick=pause;$('rally').onclick=rally;
$('sound').onclick=()=>{muted=!sound.setEnabled(muted);$('sound').innerHTML='♫ <span>'+(muted?'OFF':'ON')+'</span>';$('sound').setAttribute('aria-label',muted?'Enable sound':'Mute sound');tone();};
window.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight',' '].includes(e.key))e.preventDefault();keys[e.key]=true;if(e.key===' '&&!e.repeat)pause();if(e.key.toLowerCase()==='r'&&!e.repeat)rally();});window.addEventListener('keyup',e=>keys[e.key]=false);window.addEventListener('blur',()=>{keys={};if(running())pause();});document.addEventListener('visibilitychange',()=>{if(document.hidden&&running())pause();});
document.querySelectorAll('[data-outfit]').forEach(b=>b.onclick=()=>{outfit=Number(b.dataset.outfit);try{localStorage.setItem('gate-army-outfit',String(outfit));}catch{}wardrobe();sound.fx('shield');});
$('outfit-auto').onclick=()=>{outfit=-1;try{localStorage.setItem('gate-army-outfit','-1');}catch{}wardrobe();};
ads.subscribe(state=>{adState=state;adUI();});
$('reward-ad').onclick=async()=>{if(rewardClaimed||!(phase==='won'||phase==='lost'))return;rewardClaimed=await ads.reward();adUI();};
$('ad-privacy').hidden=!ads.isNative;$('ad-privacy').onclick=()=>ads.privacy();
$('privacy-link').onclick=e=>{if(ads.policy())e.preventDefault();};
window.GateNativeLifecycle={pause(){if(running())pause();sound.update(stage,'paused');}};
brief();ads.refresh();requestAnimationFrame(frame);
})();


