"use strict";
window.SignalMonitoring=(()=>{
  const indicator=document.getElementById('stream-status'),label=document.getElementById('stream-status-label');
  let busy=false;
  function paint(watching,description){
    const text=watching?'Stebimas srautas':'Srauto stebėjimas sustabdytas';
    indicator.classList.toggle('stopped',!watching);
    label.textContent=text;indicator.title=description||text;
    indicator.setAttribute('aria-label',text);
  }
  async function refresh(){
    if(busy||document.visibilityState==='hidden')return;
    await window.SignalSession?.ready;
    if(navigator.onLine===false){paint(false,'Nėra interneto ryšio.');return;}
    busy=true;
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
    try{
      const response=await fetch('/api/monitoring/status',{cache:'no-store',signal:controller.signal});
      if(!response.ok){const detail=await response.json().catch(()=>({}));paint(false,detail.description||detail.error||'Nepavyko patikrinti ryšio su serveriu.');return;}
      const status=await response.json();
      paint(status.state==='watching'&&navigator.onLine!==false,status.description);
    }catch(_){paint(false,'Nepavyko patikrinti ryšio su serveriu.');}
    finally{clearTimeout(timeout);busy=false;}
  }
  paint(false,'Tikrinama srauto būsena.');
  window.addEventListener('offline',()=>paint(false,'Nėra interneto ryšio.'));
  window.addEventListener('online',refresh);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refresh();});
  setInterval(refresh,60000);
  refresh();
  return Object.freeze({refresh});
})();
