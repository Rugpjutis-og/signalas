"use strict";
window.SignalAnalysis=(()=>{
  let active=null;
  const button=document.getElementById('fetch-data'),message=document.getElementById('fetch-result');
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  async function request(path,method='GET'){
    const response=await fetch('/api/analysis/'+path,{method,cache:'no-store',headers:method==='POST'?{'X-Signalas-CSRF':window.SignalSession.csrf()}: {}});
    const value=await response.json();
    if(!response.ok)throw Error(value.error||'Analizės tęsti nepavyko.');
    return value;
  }
  async function drain(state){
    button.disabled=true;
    button.setAttribute('aria-busy','true');
    let stopped=false,polling=false;
    const progress=(value=state)=>{if(value.kind==='collection'){message.textContent=`Surinkimas tęsiamas: patikrinta ${value.processed_posts??0} iš ${value.discovered_posts??0} aptiktų įrašų. Paskutinė sėkminga imtis išlieka.`;return;}message.textContent=`${value.remaining_kind==='candidate_checks'?'Tikrinama analizės eilė…':'Analizuojamas turinys…'} Liko ${value.remaining ?? '…'} ${value.remaining_kind==='candidate_checks'?'patikrinti kandidatų':'vnt.'}. Neaiškūs vertinimai paliekami peržiūrai, eilė tęsiama.`;};
    const timer=setInterval(async()=>{
      if(polling||stopped)return;polling=true;
      try{const latest=await request('status');if(!stopped&&['pending','running'].includes(latest.status)){progress(latest);}}
      catch(_){/* The active batch reports persistent failures. */}finally{polling=false;}
    },30000);
    try{
      while(['pending','running','already_running'].includes(state.status)){
        progress();
        if(state.status==='already_running')await sleep(10000);
        state=await request('continue','POST');
        if(state.status!=='already_running')await window.SignalLiveData?.refresh();
      }
      if(state.status==='error'){
        const reason=state.reason==='api_quota'?'Patikrinkite AI API kreditus.':state.reason==='api_access'?'Patikrinkite AI API rakto ir modelio prieigą.':'Patikrinkite ryšį, modelio nustatymus ar vertinimo klaidą.';
        message.textContent=`Duomenys išsaugoti. Analizė sustabdyta; liko ${state.remaining} ${state.remaining_kind==='candidate_checks'?'patikrinti kandidatų':'vnt.'}. ${reason} Pakartoti galima mygtuku „Atnaujinti duomenis“.`;
      }else if(state.status==='complete')message.textContent='Duomenys atnaujinti. Teksto analizė baigta; neaiškius ir medijos vertinimus reikia peržiūrėti.';
    }catch(error){message.textContent=(error.message||'Ryšys nutrūko.')+' Išsaugota analizė neprarasta. Atverkite aplikaciją iš naujo, kad tęstumėte eilę.';}
    finally{stopped=true;clearInterval(timer);button.disabled=false;button.removeAttribute('aria-busy');await window.SignalMonitoring?.refresh();}
  }
  function run(state){
    if(active)return active;
    active=drain(state).finally(()=>{active=null;});
    return active;
  }
  window.SignalSession.ready.then(async()=>{
    try{
      const state=await request('status');
      if(['pending','running'].includes(state.status))await run(state);
    }catch(_){/* Normal API status displays connection/auth errors; never start collection here. */}
  });
  return Object.freeze({run});
})();
