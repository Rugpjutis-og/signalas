const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
function node(){const children=new Map();return {innerHTML:'',isConnected:true,focus(){},scrollIntoView(){},setAttribute(){},
 querySelector(k){if(!children.has(k))children.set(k,node());return children.get(k)},querySelectorAll(){return []}};}
function runtime(fetch){const context={window:{},URL,Intl,Date,fetch,FormData:class{constructor(form){return Object.entries(form.values)}}};
 vm.createContext(context);for(const file of ['source-content.js','thermometer.js'])vm.runInContext(fs.readFileSync(path.join(root,'dist',file),'utf8'),context);return context.window;}
(async()=>{
 const initial=JSON.parse(fs.readFileSync(path.join(root,'dist/demo/thermometer-7.json'),'utf8'));initial.mode='live';
 const target=initial.units.find(u=>['needs_review','error'].includes(u.assessment.status));assert(target);
 const oldCoverage=initial.assessed;
 let calls=0,resolveBackground;
 const w=runtime(async()=>{calls++;if(calls===1)return {ok:true,json:async()=>structuredClone(initial)};
   if(calls===2)return new Promise(resolve=>{resolveBackground=resolve;});
   throw Error('No full fetch is needed for manual confirmation');});
 const response=category=>({status:'saved',source:target.source,id:target.id,assessment:{...target.assessment,
   status:'assessed',category,method:'manual_review',reason:'Rankiniu būdu patvirtinta.',reason_codes:[]}});
 w.SignalLiveData={saveThermometerReview:async p=>response(p.category)};
 const page=node();await w.SignalThermometer.mount(page,7);
 page.onclick({target:{closest:s=>s==='#thermo-content-toggle'?{}:null}});
 w.SignalThermometer.invalidate();const background=w.SignalThermometer.refresh(page,7);
 assert(resolveBackground);
 const submit=async category=>{const form=node();form.dataset={source:target.source,id:target.id};
   form.values={category};form.reportValidity=()=>true;
   await page.onsubmit({preventDefault(){},target:{closest:()=>form}});};
 await submit('neutral');
 assert.equal(calls,2,'save does not start or wait for another full request');
 assert(page.innerHTML.includes(`Aprėptis: ${oldCoverage+1} iš ${initial.total}`));
 const neutralBefore=initial.categories.find(c=>c.id==='neutral').count;
 const redBefore=initial.categories.find(c=>c.id==='destabilizing').count;
 assert(page.innerHTML.includes(`class="thermo-segment neutral" style="flex-grow:${neutralBefore+1};`));
 const dayKey=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Vilnius',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(target.published_at));
 const day=initial.days.find(d=>d.date===dayKey);assert(day);
 assert(page.innerHTML.includes(`<tr><th>${day.date}</th><td>${day.assessed+1} iš ${day.total}</td>`));
 assert(page.querySelector('[data-thermo-review-confirmation]').textContent.includes('įskaityta'));
 const afterFirst=page.innerHTML;
 resolveBackground({ok:true,json:async()=>structuredClone(initial)});await background;
 assert.equal(page.innerHTML,afterFirst,'an older background response cannot undo a committed decision');
 await submit('destabilizing');
 assert.equal(calls,2);
 assert(page.innerHTML.includes(`Aprėptis: ${oldCoverage+1} iš ${initial.total}`),'correction does not count the same unit twice');
 assert(page.innerHTML.includes(`class="thermo-segment destabilizing" style="flex-grow:${redBefore+1};`));
 assert(page.innerHTML.includes(`class="thermo-segment neutral" style="flex-grow:${neutralBefore};`));
 assert(page.querySelector('#thermo-evidence').innerHTML.includes('Kryptis patvirtinta rankiniu būdu'));
 // A failed save leaves the successfully displayed data unchanged.
 w.SignalLiveData.saveThermometerReview=async()=>{throw Error('Nepavyko išsaugoti');};
 const beforeFailure=page.innerHTML;await submit('stabilizing');assert.equal(page.innerHTML,beforeFailure);
 console.log('Fast manual review: immediate committed update, corrections, no refetch, failed save and stale background protection: OK');
})().catch(e=>{console.error(e);process.exit(1)});
