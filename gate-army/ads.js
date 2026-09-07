/* No simulated rewards or live ads in browsers. Rewards come only from the native SDK callback. */
window.GateAds = (() => {
  const native = window.AndroidAds;
  let ready=false, eligible=false, busy=false, sequence=0, pending=null;
  let message='Optional rewarded ads are available in the Android app.';
  const listeners=[];
  const notify=()=>listeners.forEach(fn=>fn({native:!!native,ready,eligible,busy,message}));
  const bonus=()=>{try{return Number(localStorage.getItem('gate-army-reinforcements'))===15?15:0;}catch{return 0;}};
  window.GateAdsNative={receive(event){
    if(!native||!event)return;
    if(event.type==='status'){ready=event.ready===true;eligible=event.eligible===true;message=String(event.message||'');notify();}
    if(event.type==='reward'&&pending&&event.id===pending.id){
      const resolve=pending.resolve;clearTimeout(pending.timer);pending=null;busy=false;
      const earned=event.earned===true;
      if(earned){try{localStorage.setItem('gate-army-reinforcements','15');}catch{message='Reward could not be saved on this device.';notify();resolve(false);return;}}
      message=String(event.message||'');notify();resolve(earned);
    }
  }};
  return {
    isNative:!!native, bonus,
    subscribe(fn){listeners.push(fn);fn({native:!!native,ready,eligible,busy,message});},
    refresh(){try{native?.refresh();}catch{ready=false;notify();}},
    consumeBonus(){const value=bonus();try{localStorage.removeItem('gate-army-reinforcements');}catch{return 0;}return value;},
    reward(){
      if(!native||!ready||!eligible||busy||bonus())return Promise.resolve(false);
      busy=true;notify();
      return new Promise(resolve=>{
        const id='reward-'+(++sequence);
        pending={id,resolve,timer:setTimeout(()=>{pending=null;busy=false;message='Ad response timed out. You can keep playing.';notify();resolve(false);},300000)};
        try{native.reward(id);}catch{clearTimeout(pending.timer);pending=null;busy=false;notify();resolve(false);}
      });
    },
    privacy(){try{native?.privacy();}catch{}},
    policy(){if(native){native.policy();return true;}return false;}
  };
})();
