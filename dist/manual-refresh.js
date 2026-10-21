"use strict";
(()=>{
  const button=document.getElementById('fetch-data'),message=document.getElementById('fetch-result');
  let busy=false;
  button.addEventListener('click',async()=>{
    if(busy)return;
    busy=true;button.disabled=true;button.setAttribute('aria-busy','true');
    message.textContent='Renkami duomenys…';
    try{
      await window.SignalSession?.ready;
      const status=await fetch('/api/collection/status',{cache:'no-store'});
      if(!status.ok)throw Error('Šiame serveryje duomenų surinkimas dar neprijungtas.');
      const capability=await status.json();
      if(!capability.available)throw Error(capability.message||'Duomenų surinkimas dar neprijungtas.');
      const response=await fetch('/api/collection/refresh',{method:'POST',headers:{'X-Signalas-CSRF':capability.csrf||''}});
      const result=await response.json();
      if(!response.ok)throw Error(result.error||'Duomenų surinkti nepavyko.');
      if(result.status==='already_running')message.textContent='Duomenų surinkimas jau vyksta.';
      else{
        message.textContent=`Atnaujinta: ${result.posts} įrašų, ${result.comments} komentarų.${result.cloud_storage?.status==='error'?' Debesijos kopijos išsaugoti nepavyko; vietinė kopija išsaugota.':''}`;
        await window.SignalLiveData?.refresh();

      }
    }catch(error){message.textContent=error.message||'Ryšys nutrūko. Paskutinė sėkminga kopija išsaugota.';}
    finally{busy=false;button.disabled=false;button.removeAttribute('aria-busy');await window.SignalMonitoring?.refresh();}
  });
})();
