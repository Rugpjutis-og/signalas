"use strict";
window.SignalGrowth = (() => {
  // Policy is loaded from metrics-context.json, the single source of trial thresholds.
  // Membership is supplied by an exercise-scoped authoritative API, never inferred from activity.
  const sum=values=>values.reduce((a,b)=>a+b,0);
  const valid=values=>values.every(v=>Number.isInteger(v)&&v>=0);
  function compare(n,period,context=window.SignalMetricsContext?.get()){
    const unavailable={current:null,previous:null,increase:null,percent:null,significant:false};
    if(!Number.isInteger(period)||period<=0||!Array.isArray(n.days)||n.days.length<period)return unavailable;
    const currentDays=n.days.slice(-period);
    if(!valid(currentDays))return unavailable;
    const history=[...(Array.isArray(n.previousDays)?n.previousDays:[]),...n.days];
    const previousDays=history.slice(Math.max(0,history.length-2*period),history.length-period);
    const current=sum(currentDays);
    if(n.is_live&&n.history_complete!==true)return {...unavailable,current};
    if(previousDays.length!==period||!valid(previousDays))return {...unavailable,current};
    const previous=sum(previousDays),increase=current-previous;
    const thresholds=context?.growth_policy;
    const a=context?.audience;
    const audience=a?.status==='known'&&typeof n.exercise_id==='string'&&n.exercise_id===context.exercise_id&&a.exercise_id===context.exercise_id&&Number.isSafeInteger(a.count)&&a.count>0?a.count:null;
    const requiredIncrease=thresholds&&audience!==null?Math.max(thresholds.minAbsoluteIncrease,Math.ceil(audience*thresholds.minAudienceFraction)):null;
    const percent=previous>0?increase/previous*100:null;
    return {current,previous,increase,percent,audience,requiredIncrease,significant:percent!==null&&requiredIncrease!==null&&previous>=thresholds.minPrevious&&increase>=requiredIncrease&&percent>=thresholds.minPercent};
  }
  function aggregate(ns,period){
    const comparisons=ns.map(n=>compare(n,period));
    if(!comparisons.length||comparisons.some(c=>c.previous===null||c.current===null))return null;
    const previous=sum(comparisons.map(c=>c.previous));
    return previous>0?(sum(comparisons.map(c=>c.current))-previous)/previous*100:null;
  }
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=value=>value.toLocaleString('lt-LT',{maximumFractionDigits:0});
  function percentLabel(percent){return percent===null?'—':`${percent>0?'+':percent<0?'−':''}${number(Math.abs(percent))} %`;}
  function explanation(n,period){
    const c=compare(n,period);
    return c.percent===null?'':`Demonstracinis palyginimas: ${percentLabel(c.percent)} · nuo ${number(c.previous)} iki ${number(c.current)} turinio vienetų, palyginti su ankstesniu tokios pačios trukmės laikotarpiu (${period} d.).`;
  }
  function badge(n,period){
    if(!compare(n,period).significant)return '';
    return `<button type="button" class="growth-badge" data-growth-info data-growth-explanation="${escape(explanation(n,period))}" aria-expanded="false" aria-describedby="growth-explanation">↗ Sparčiai auga</button>`;
  }
  let trigger=null,pinned=false;
  const tooltip=()=>document.getElementById('growth-explanation');
  function hide(){
    if(trigger)trigger.setAttribute('aria-expanded','false');
    trigger=null;pinned=false;
    const tip=tooltip();if(tip)tip.hidden=true;
  }
  function show(button,pin=false){
    const tip=tooltip();if(!tip)return;
    if(trigger&&trigger!==button)trigger.setAttribute('aria-expanded','false');
    trigger=button;pinned=pin;
    tip.textContent=button.dataset.growthExplanation;tip.hidden=false;
    button.setAttribute('aria-expanded','true');
    const r=button.getBoundingClientRect(),box=tip.getBoundingClientRect();
    const width=document.documentElement.clientWidth,height=window.innerHeight;
    tip.style.left=`${Math.max(12,Math.min(r.left,width-box.width-12))}px`;
    tip.style.top=`${Math.max(12,r.bottom+8+box.height<=height-12?r.bottom+8:r.top-box.height-8)}px`;
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-growth-info]');
    if(button){event.stopImmediatePropagation();if(trigger===button&&pinned)hide();else show(button,true);return;}
    if(!tooltip()?.contains(event.target))hide();
  });
  document.addEventListener('mouseover',event=>{
    const button=event.target.closest('[data-growth-info]');
    if(button&&!button.contains(event.relatedTarget)&&!pinned)show(button);
  });
  document.addEventListener('mouseout',event=>{
    if(pinned||!trigger)return;
    const next=event.relatedTarget;
    if(trigger.contains(next)||tooltip()?.contains(next))return;
    if(trigger.contains(event.target)||tooltip()?.contains(event.target))hide();
  });
  document.addEventListener('focusin',event=>{
    const button=event.target.closest('[data-growth-info]');if(button)show(button);
  });
  document.addEventListener('focusout',event=>{if(!pinned&&trigger===event.target)hide();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&trigger){hide();event.preventDefault();}});
  window.addEventListener('resize',hide);
  window.addEventListener('scroll',hide,true);
  return Object.freeze({get thresholds(){return window.SignalMetricsContext?.get().growth_policy??null},compare,aggregate,percentLabel,explanation,badge,hide});
})();
