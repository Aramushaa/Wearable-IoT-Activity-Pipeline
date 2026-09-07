/* Stylized, empire-inspired fantasy art; intentionally not historical reconstructions. */
window.EmpireArt = (() => {
 const cultures = [
  {id:'roman',name:'Roman',unit:'Legionary',ruler:'Emperor Aurelius',island:'Laurel Imperium',biome:'THE ROMAN EMPEROR’S ISLAND',cloth:'#b73743',metal:'#b8c5cf',gold:'#e8b954',stone:'#eee1c8',dark:'#755541',symbol:'✦',sky:'#e4e9cb',water:'#4daba2',land:'#679e75',road:'#eee5cf',notes:[0,3,7,10,7,3,5,7]},
  {id:'greek',name:'Greek',unit:'Hoplite',ruler:'King Leandros',island:'Aegean Acropolis',biome:'THE GREEK KING’S ISLAND',cloth:'#216cab',metal:'#d9af5d',gold:'#f8d77a',stone:'#fff4dc',dark:'#8d866e',symbol:'Ω',sky:'#d4effa',water:'#278daf',land:'#6fab91',road:'#f6eedc',notes:[0,4,7,11,7,4,2,7]},
  {id:'persian',name:'Persian',unit:'Immortal',ruler:'Shah Ardeshir',island:'Saffron Palace',biome:'THE PERSIAN SHAH’S ISLAND',cloth:'#764391',metal:'#d0a35d',gold:'#f6d483',stone:'#edc89f',dark:'#9f6850',symbol:'✧',sky:'#f9d4bb',water:'#489f9f',land:'#c2916f',road:'#ecd4b2',notes:[0,1,4,5,7,8,11,7]},
  {id:'egyptian',name:'Egyptian',unit:'Sun Guard',ruler:'Pharaoh Neferu',island:'Temple of Dawn',biome:'THE PHARAOH’S ISLAND',cloth:'#1c9d9f',metal:'#e1b544',gold:'#ffe390',stone:'#e8c281',dark:'#ae7e45',symbol:'☀',sky:'#ffe1a4',water:'#389b9c',land:'#d6ac68',road:'#f3ddb3',notes:[0,2,5,7,10,7,5,2]},
  {id:'norse',name:'Norse',unit:'Shieldbearer',ruler:'High King Eirik',island:'Frosthold Fjord',biome:'THE HIGH KING’S ISLAND',cloth:'#356a68',metal:'#96a9b7',gold:'#d6b780',stone:'#8c9b9e',dark:'#465b68',symbol:'ᛟ',sky:'#d3deef',water:'#507b99',land:'#879ca5',road:'#dce3df',notes:[0,3,5,7,10,7,5,3]}
 ];
 function warrior(c,px,py,s,culture,t=0,enemy=false,role=0){
  const a=cultures[culture],cloth=enemy?'#902b45':a.cloth;
  const rr=(x,y,w,h,r,color)=>{c.fillStyle=color;c.beginPath();c.roundRect(x,y,w,h,r);c.fill();};
  const poly=(p,color)=>{c.fillStyle=color;c.beginPath();p.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.fill();};
  const disk=(x,y,r,color)=>{c.fillStyle=color;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill();};
  c.save();c.translate(px,py);c.scale(s,s);
  c.fillStyle='#132a3540';c.beginPath();c.ellipse(1,4,7,2.5,0,0,Math.PI*2);c.fill();
  const k=Math.sin(t)*1.2;
  poly([[-5,-14],[5,-14],[7,1],[-6,0]],cloth);
  rr(-3,0,2.5,5+k,1,'#624b40');rr(1,0,2.5,5-k,1,'#624b40');
  rr(-5,-14,10,12,2,a.metal);rr(-4,-13,3,10,1,'#ffffff42');rr(1,-13,3,10,1,'#17273b25');
  if(culture===0){for(let j=0;j<3;j++)rr(-4,-11+j*2,8,.6,0,'#556472');}
  if(culture===2){for(let y=-12;y<-3;y+=2)for(let x=-3;x<4;x+=2)rr(x,y,1,1,0,a.gold);}
  if(culture===3){rr(-4,-12,8,3,1,a.gold);for(let j=0;j<4;j++)rr(-3+j*2,-12,1,3,0,cloth);}
  rr(-5,-3,10,2,.5,a.gold);
  rr(-3.5,-20,7,7,2,'#cf9b72');rr(-3,-19,2,4,1,'#edbc8c');
  if(culture===0||culture===1){rr(-4.5,-22,9,5,2,a.metal);rr(-4.5,-18,2,5,.5,a.metal);rr(2.5,-18,2,5,.5,a.metal);rr(-1,-27,3,6,1,cloth);rr(-2,-27,5,2,.5,cloth);if(culture===1)rr(-.5,-18,1,4,.2,a.gold);}
  if(culture===2){poly([[-5,-18],[-4,-23],[0,-25],[4,-23],[5,-18]],cloth);rr(-4,-20,8,2,.5,a.gold);rr(-4,-16,8,3,1,'#473551');disk(0,-20,1,'#78d9d1');}
  if(culture===3){poly([[-4,-22],[4,-22],[6,-13],[3,-14],[3,-19],[-3,-19],[-3,-14],[-6,-13]],a.gold);rr(-3,-21,6,2,0,cloth);rr(-5,-18,2,1,0,cloth);rr(3,-18,2,1,0,cloth);}
  if(culture===4){rr(-5,-15,10,4,2,'#b3a797');poly([[-5,-18],[-4,-22],[0,-25],[4,-22],[5,-18]],a.metal);rr(-.7,-23,1.4,7,.4,a.gold);rr(-3,-15,6,3,1,'#735646');}
  // Small faces, readable silhouettes and different weapons, even at crowd scale.
  rr(-2,-17,.8,.7,0,'#302b32');rr(1.2,-17,.8,.7,0,'#302b32');
  c.strokeStyle='#7d6447';c.lineWidth=.9;c.beginPath();c.moveTo(7,2);c.lineTo(7,-24);c.stroke();
  if(culture===4)poly([[7,-23],[12,-23],[12,-17],[7,-19]],a.metal);else poly([[7,-28],[4.8,-22],[9.2,-22]],a.metal);
  if(culture===0){rr(-10,-13,7,12,2,a.gold);rr(-9,-12,5,10,1,cloth);poly([[-6.5,-11],[-7.5,-6],[-5,-8],[-6.5,-3]],a.gold);}
  else if(culture===2){poly([[-10,-13],[-4,-13],[-3,-7],[-7,-1],[-11,-7]],a.gold);poly([[-9,-12],[-5,-12],[-4,-7],[-7,-3],[-10,-7]],cloth);}
  else{disk(-7,-7,5.2,a.gold);disk(-7,-7,4.1,culture===4?'#70584a':cloth);disk(-7,-7,1.5,a.metal);if(culture===4){rr(-11,-7.5,8,1,0,a.metal);}}
  if(role===0){c.strokeStyle=a.gold;c.lineWidth=.8;c.beginPath();c.moveTo(10,1);c.lineTo(10,-35);c.stroke();poly([[10,-35],[20,-33],[18,-24],[10,-26]],cloth);disk(14,-30,1.7,a.gold);}
  c.restore();
 }
 function building(c,px,py,s,culture){const a=cultures[culture];c.save();c.translate(px,py);c.scale(s,s);
 const rect=(x,y,w,h,color)=>{c.fillStyle=color;c.fillRect(x,y,w,h);};
 const poly=(pts,color)=>{c.fillStyle=color;c.beginPath();pts.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.fill();};
 c.fillStyle='#172f4530';c.beginPath();c.ellipse(8,4,70,11,0,0,Math.PI*2);c.fill();
 if(culture===0){rect(-57,-57,114,57,a.stone);rect(-57,-57,114,7,a.gold);for(let i=-45;i<=45;i+=30){c.fillStyle=a.dark;c.beginPath();c.roundRect(i-8,-38,16,38,[8,8,0,0]);c.fill();}rect(-61,-5,122,5,'#d5c5a6');for(let i=-55;i<56;i+=12)rect(i,-66,8,10,a.stone);}
 if(culture===1){rect(-59,-5,118,6,a.stone);rect(-54,-12,108,7,'#d7cfb7');for(let i=-43;i<44;i+=21){rect(i-5,-65,10,53,a.stone);rect(i-5,-65,3,53,'#c9c8b3');rect(i-8,-67,16,5,a.gold);}poly([[-62,-67],[0,-98],[62,-67]],a.stone);poly([[-42,-72],[0,-91],[42,-72]],'#99bbbd');}
 if(culture===2){rect(-49,-50,98,50,a.stone);rect(-58,-12,116,12,a.gold);for(const x of [-45,45]){rect(x-6,-75,12,72,a.stone);rect(x-9,-78,18,6,a.gold);}poly([[-36,-50],[-29,-72],[0,-92],[29,-72],[36,-50]],'#3caaad');poly([[-27,-50],[-20,-70],[0,-87],[0,-50]],'#83d4c5');rect(-34,-52,68,5,a.gold);rect(-12,-33,24,33,a.dark);}
 if(culture===3){poly([[-66,0],[-43,-67],[-7,0]],a.stone);poly([[-7,0],[-43,-67],[-27,-6]],a.dark);poly([[-17,0],[29,-103],[78,0]],a.stone);poly([[29,-103],[78,0],[39,0]],'#b98b52');poly([[20,-81],[29,-103],[40,-81]],a.gold);}
 if(culture===4){rect(-48,-43,96,43,'#735c4d');for(let i=-45;i<48;i+=9)rect(i,-43,2,43,'#564739');poly([[-65,-41],[0,-94],[65,-41]],'#465e6c');poly([[-65,-41],[0,-94],[65,-41],[54,-41],[0,-82],[-54,-41]],'#e9eff0');rect(-13,-30,26,30,'#344b59');rect(-35,-30,12,12,'#edbf78');rect(24,-30,12,12,'#edbf78');}
 rect(49,-90,2,48,a.dark);poly([[51,-89],[73,-85],[69,-69],[51,-74]],a.cloth);c.restore();}
 return {cultures,warrior,building};
})();
