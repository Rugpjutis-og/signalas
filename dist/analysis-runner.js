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
    try{
      while(['pending','running','already_running'].includes(state.status)){
        message.textContent=`Analizuojamas turinys… Liko ${state.remaining ?? '…'} vnt. Galite naudotis skiltimis arba uždaryti aplikaciją: foninis vykdymas tęsis.`;
        if(state.status==='already_running')await sleep(3000);
        state=await request('continue','POST');
        if(state.status!=='already_running')await window.SignalLiveData?.refresh();
      }
      if(state.status==='error'){
        const reason=state.reason==='api_quota'?'Patikrinkite AI API kreditus.':state.reason==='api_access'?'Patikrinkite AI API rakto ir modelio prieigą.':'Patikrinkite ryšį, modelio nustatymus ar vertinimo klaidą.';
        message.textContent=`Duomenys išsaugoti. Analizė sustabdyta; liko ${state.remaining} vnt. ${reason} Pakartoti galima mygtuku „Atnaujinti duomenis“.`;
      }else if(state.status==='complete')message.textContent='Duomenys atnaujinti. Teksto analizė baigta; neaiškius ir medijos vertinimus reikia peržiūrėti.';
    }catch(error){message.textContent=(error.message||'Ryšys nutrūko.')+' Išsaugota analizė neprarasta. Atverkite aplikaciją iš naujo, kad tęstumėte eilę.';}
    finally{button.disabled=false;button.removeAttribute('aria-busy');await window.SignalMonitoring?.refresh();}
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
