const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = {};
const noop = () => {};
const gradient = { addColorStop: noop };
const context = new Proxy({}, { get: (_, key) => {
  if (key === 'createLinearGradient') return () => gradient;
  if (key === 'ellipse') return (...args) => assert.ok(args.length >= 7, 'Canvas ellipse needs seven arguments');
  return noop;
}, set: () => true });
const element = id => elements[id] ??= {
  textContent: '', innerHTML: '', hidden: false, style: {},
  classList: { add: noop, remove: noop }, setAttribute: noop,
  addEventListener: noop, querySelectorAll: () => [],
  getBoundingClientRect: () => ({ width: 390, height: 700 }), getContext: () => context,
};
const storage = new Map();
const sandbox = {
  document: { getElementById: element, addEventListener: noop, querySelectorAll: () => [] },
  window: { addEventListener: noop }, ResizeObserver: class { observe() {} },
  localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
  requestAnimationFrame: noop, devicePixelRatio: 1, Math,
};
// Instrument only the test copy; the browser build exposes no mutable test hooks.
const source = fs.readFileSync(__dirname + '/game.js', 'utf8').replace(/\}\)\(\);\s*$/, `
globalThis.test = {start, update, draw, pause, rally, resolve, damage, brief, levels,
 get(){return {phase,count,enemy,shield,rescued,distance,combo,stage,saved,rallyUsed,events}},
 set(v){if(v.stage!==undefined)stage=v.stage;if(v.count!==undefined)count=v.count;
 if(v.x!==undefined)x=target=v.x;if(v.distance!==undefined)distance=v.distance;
 if(v.battleTime!==undefined)battleTime=v.battleTime;}};
})();`);
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(__dirname + '/empires.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(__dirname + '/audio.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(__dirname + '/ads.js', 'utf8'), sandbox);
vm.runInContext(source, sandbox);
const game = sandbox.test;
game.start();
game.set({ x: -.5 });
game.resolve({ type: 'gate', ops: [['+',18],['×',2]] });
assert.equal(game.get().count, 30);
game.resolve({ type: 'gate', ops: [['×',3],['+',18]] });
assert.equal(game.get().count, 90);
game.resolve({ type: 'gate', ops: [['+',10],['+',18]] });
assert.equal(game.get().count, 105, 'third growth gate grants five bonus soldiers');
game.resolve({ type: 'gate', ops: [['÷',2],['+',18]] });
assert.equal(game.get().count, 52);
assert.equal(game.get().combo, 0);
game.resolve({ type:'shield', x:-.5 });
game.damage(20);
assert.equal(game.get().count, 52, 'shield blocks one hit');
assert.equal(game.get().shield, 0);
game.damage(20);
assert.equal(game.get().count, 32, 'next hit removes soldiers');
game.pause();
const frozen = game.get().distance;
game.update(2);
assert.equal(game.get().distance, frozen);
game.pause();
assert.equal(game.get().phase, 'running');
for (let stage = 0; stage < 5; stage++) {
  game.set({ stage }); game.start();
  for (const e of game.get().events) {
    let x;
    if (e.type === 'gate') {
      const n = game.get().count;
      const value = ([op,v]) => op === '+' ? n+v : op === '×' ? n*v : op === '÷' ? Math.floor(n/v) : n-v;
      x = value(e.ops[0]) > value(e.ops[1]) ? -.53 : .53;
    } else if (e.type === 'shield' || e.type === 'rescue') x=e.x;
    else x=(e.moving ? Math.sin(e.z)*.62 : e.x) > 0 ? -.8 : .8;
    game.set({ x, distance: e.z }); game.update(.001); game.draw();
  }
  assert.equal(game.get().rescued, 2);
  game.set({ distance:2500 }); game.update(.001);
  assert.equal(game.get().phase, 'battle');
  game.set({ battleTime: Math.asin(.6)/2.5 });
  const enemyBefore = game.get().enemy;
  game.rally();
  assert.ok(game.get().enemy < enemyBefore);
  const afterRally = game.get().enemy; game.rally();
  assert.equal(game.get().enemy, afterRally, 'rally is available once per battle');
  for(let i=0;i<1000 && game.get().phase==='battle';i++) game.update(.04);
  assert.equal(game.get().phase,'won','winning route on stage '+stage);
  assert.equal(game.get().saved.medals[stage],3,'all medals are achievable on stage '+stage);
  game.draw();
}
assert.equal(JSON.parse(storage.get('gate-army-campaign-v2')).unlocked,4);
game.start();game.set({count:1});game.damage(50);
// The event resolver ends a run when its damage eliminates the squad.
game.resolve({type:'gate',ops:[['+',0],['+',0]]});
assert.equal(game.get().phase,'lost');
game.start();assert.equal(game.get().count,12);assert.equal(game.get().shield,0);
storage.set('gate-army-reinforcements','15');game.start();assert.equal(game.get().count,27,'earned ad reward adds fifteen soldiers');game.start();assert.equal(game.get().count,12,'bonus is consumed once');
console.log('PASS: arithmetic, streaks, shield consumption, damage, pause, five three-medal routes, single-use rally, saved campaign, defeat and restart.');

