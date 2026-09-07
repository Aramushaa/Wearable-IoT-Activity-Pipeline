const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {createCanvas,GlobalFonts}=require('@napi-rs/canvas');
const root=path.resolve(__dirname,'..'),out=path.join(root,'release');
GlobalFonts.registerFromPath(path.join(root,'fonts/barlow-condensed-latin-800-normal.woff2'),'Barlow Condensed');
GlobalFonts.registerFromPath(path.join(root,'fonts/dm-sans-latin-700-normal.woff2'),'DM Sans');
const env={window:{}};vm.createContext(env);vm.runInContext(fs.readFileSync(path.join(root,'empires.js'),'utf8'),env);const art=env.window.EmpireArt;
function background(c,w,h){const g=c.createLinearGradient(0,0,w,h);g.addColorStop(0,'#263f52');g.addColorStop(1,'#101727');c.fillStyle=g;c.fillRect(0,0,w,h);}
function label(c,t,x,y,size,color='#fff',font='Barlow Condensed'){c.fillStyle=color;c.font=`800 ${size}px "${font}",sans-serif`;c.fillText(t,x,y);}
const icon=createCanvas(512,512),i=icon.getContext('2d');background(i,512,512);i.fillStyle='#c2f86d';i.fillRect(70,70,372,26);i.fillRect(70,70,26,372);i.fillRect(416,70,26,372);art.warrior(i,245,412,8.7,0,0,false,0);fs.writeFileSync(path.join(out,'store-icon.png'),icon.toBuffer('image/png'));
const feature=createCanvas(1024,500),c=feature.getContext('2d');background(c,1024,500);
label(c,'SLEEPY PANDA GAMES',44,57,14,'#a9c2c9','DM Sans');label(c,'GATE ARMY',42,177,87,'#f4f0d9');label(c,'FIVE EMPIRES',45,227,33,'#c2f86d');label(c,'Choose your gates.',45,317,27);label(c,'Build your legend.',45,353,27);label(c,'ROMAN · GREEK · PERSIAN · EGYPTIAN · NORSE',45,445,12,'#afc3cc','DM Sans');
c.fillStyle='#4c6d6940';c.beginPath();c.ellipse(765,392,205,46,0,0,Math.PI*2);c.fill();
art.building(c,817,203,1.55,1);art.warrior(c,638,379,5.3,1,0,false,1);art.warrior(c,854,375,5.7,2,0,false,0);art.warrior(c,742,416,7,0,0,false,0);
fs.writeFileSync(path.join(out,'feature-graphic.png'),feature.toBuffer('image/png'));
const gallery=createCanvas(1200,440),g=gallery.getContext('2d');background(g,1200,440);label(g,'FIVE EMPIRES — OUTFIT ART',36,49,28,'#c2f86d');
art.cultures.forEach((a,n)=>{const x=100+n*240;art.warrior(g,x,325,6,n,0,false,0);label(g,a.name.toUpperCase(),x-45,383,23,a.gold);label(g,a.unit,x-45,413,14,'#c4d1dd','DM Sans');});fs.writeFileSync(path.join(out,'outfit-art-review.png'),gallery.toBuffer('image/png'));
console.log('Created 512×512 store icon, 1024×500 feature graphic, and outfit art review. Actual device screenshots remain a release requirement.');
