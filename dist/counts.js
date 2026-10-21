"use strict";
window.SignalCounts=Object.freeze({
  categoryShares(counts){
    const assessed=counts.reduce((a,b)=>a+b,0);
    return counts.map(count=>assessed>0?count/assessed*100:null);
  },
  axisCeiling(value){
    if(!Number.isFinite(value)||value<=0)return 1;
    const unit=10**Math.floor(Math.log10(value)),scaled=value/unit;
    return [1,2,5,10].find(step=>step>=scaled)*unit;
  },
  axisTicks(ceiling){
    const step=Math.max(1,window.SignalCounts.axisCeiling(ceiling/5));
    return Array.from({length:Math.floor(ceiling/step)+1},(_,i)=>i*step);
  },
  apportion(total,weights){
    if(!Number.isInteger(total)||total<0||!weights.length||weights.some(w=>!Number.isFinite(w)||w<0))return weights.map(()=>0);
    const denominator=weights.reduce((a,b)=>a+b,0);if(!denominator)return weights.map(()=>0);
    const exact=weights.map(w=>total*w/denominator),result=exact.map(Math.floor);
    const order=exact.map((v,i)=>({i,remainder:v-result[i]})).sort((a,b)=>b.remainder-a.remainder||a.i-b.i);
    for(let remaining=total-result.reduce((a,b)=>a+b,0),i=0;i<remaining;i++)result[order[i].i]++;
    return result;
  }
});
