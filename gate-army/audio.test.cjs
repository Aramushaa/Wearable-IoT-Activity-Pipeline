const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let instance;
const starts = [], gains = [];
class Param {
  setValueAtTime(value) { this.value = value; }
  linearRampToValueAtTime(value) { this.value = value; }
  exponentialRampToValueAtTime(value) { this.value = value; }
  setTargetAtTime(value) { this.value = value; }
  cancelScheduledValues() {}
}
class AudioContext {
  constructor() { this.currentTime = 0; this.destination = {}; instance = this; }
  resume() {}
  createGain() {
    const gain = { gain: new Param(), connect() {}, disconnect() {} };
    gains.push(gain); return gain;
  }
  createOscillator() {
    return { frequency: new Param(), connect() {}, disconnect() {},
      start(at) { starts.push(at); }, stop() {} };
  }
}
const sandbox = { window: { AudioContext } };
vm.createContext(sandbox);
for(const file of ['empires.js','audio.js']) vm.runInContext(fs.readFileSync(__dirname+'/'+file,'utf8'),sandbox);
const sound = sandbox.window.EmpireAudio;
sound.update(0,'running');
assert.equal(starts.length,0,'no audio before user enables it');
assert.equal(sound.setEnabled(true),true);
for(let stage=0;stage<5;stage++){
  instance.currentTime+=2;
  const before=starts.length;
  sound.update(stage,'running');
  assert.ok(starts.length>before,'island '+stage+' schedules a score');
}
const beforePause=starts.length;
sound.update(4,'paused');
assert.equal(starts.length,beforePause);
assert.equal(gains[1].gain.value,0,'pause fades music out');
for(const kind of ['grow','rescue','shield','hit','rally','win','lose','start']){
  const before=starts.length;sound.fx(kind);assert.ok(starts.length>before,kind+' effect plays');
}
sound.setEnabled(false);
assert.equal(gains[0].gain.value,0,'mute silences both score and effects');
const beforeMute=starts.length;
sound.fx('win');sound.update(4,'battle');assert.equal(starts.length,beforeMute);
sound.setEnabled(true);instance.currentTime+=2;sound.update(4,'battle');
assert.ok(starts.length>beforeMute,'sound resumes after re-enabling');
console.log('PASS: user activation, five scores, pause, eight effects, master mute, and re-enable.');
