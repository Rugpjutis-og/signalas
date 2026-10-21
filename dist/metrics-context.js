"use strict";
window.SignalMetricsContext=(()=>{
  let current={exercise_id:null,audience:{exercise_id:null,status:'missing',count:null},growth_policy:null};
  function apply(value){
    const p=value?.growth_policy;
    if(!p||!['minPrevious','minAbsoluteIncrease','minPercent','minAudienceFraction'].every(key=>typeof p[key]==='number'&&Number.isFinite(p[key])&&p[key]>0)||!Number.isSafeInteger(p.minPrevious)||!Number.isSafeInteger(p.minAbsoluteIncrease)||p.minAudienceFraction>1)throw Error('Invalid metrics policy');
    const exercise_id=typeof value.exercise_id==='string'&&value.exercise_id?value.exercise_id:null;
    const a=value.audience;
    const known=exercise_id!==null&&a?.exercise_id===exercise_id&&a.status==='known'&&Number.isSafeInteger(a.count)&&a.count>=0;
    current={exercise_id,audience:{exercise_id,status:known?(a.count>0?'known':'zero'):'missing',count:known?a.count:null},growth_policy:{...p}};
    window.dispatchEvent(new Event('signalas:metrics-context'));
  }
  const ready=(async()=>{
    await window.SignalSession?.ready;
    for(const url of ['/api/metrics/context','metrics-context.json']){
      try{const response=await fetch(url,{cache:'no-store'});if(!response.ok)continue;apply(await response.json());return;}catch(_){}
    }
  })();
  return Object.freeze({get:()=>JSON.parse(JSON.stringify(current)),apply,ready});
})();
