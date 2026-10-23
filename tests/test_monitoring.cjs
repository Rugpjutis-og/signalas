const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../dist/monitoring.js'),'utf8');
(async()=>{
  let fail=false,status={state:'watching',description:'Atnaujinta'},classes=new Set(),calls=0;
  const label={textContent:''},indicator={title:'',attributes:{},setAttribute(k,v){this.attributes[k]=v},classList:{toggle(k,on){on?classes.add(k):classes.delete(k)}}};
  const events={},documentEvents={},intervals=[],timeouts=new Map();let next=0;
  const context={window:{addEventListener:(k,fn)=>events[k]=fn},document:{visibilityState:'visible',
    getElementById:id=>id==='stream-status'?indicator:label,addEventListener:(k,fn)=>documentEvents[k]=fn},navigator:{onLine:true},AbortController,
    setTimeout:fn=>{timeouts.set(++next,fn);return next},clearTimeout:id=>timeouts.delete(id),setInterval:(fn,ms)=>intervals.push([fn,ms]),
    fetch:async(url,options)=>{calls++;assert.equal(url,'/api/monitoring/status');assert.equal(options.cache,'no-store');if(fail)throw Error('network');return {ok:true,json:async()=>status}}};
  vm.createContext(context);vm.runInContext(code,context);await new Promise(setImmediate);
  assert.equal(label.textContent,'Stebimas srautas');assert(!classes.has('stopped'));
  assert.equal(intervals[0][1],60000);assert.equal(timeouts.size,0);
  status={state:'stopped',description:'AI API kreditų trūksta'};await context.window.SignalMonitoring.refresh();
  assert.equal(label.textContent,'Srauto stebėjimas sustabdytas');assert(classes.has('stopped'));
  assert.equal(indicator.title,status.description);
  fail=true;await context.window.SignalMonitoring.refresh();assert(classes.has('stopped'));
  assert(indicator.title.includes('serveriu'));
  fail=false;status={state:'watching'};await context.window.SignalMonitoring.refresh();assert(!classes.has('stopped'));
  context.navigator.onLine=false;events.offline();assert(classes.has('stopped'));
  const before=calls;await context.window.SignalMonitoring.refresh();assert.equal(calls,before);
  context.navigator.onLine=true;await events.online();assert(!classes.has('stopped'));
  context.document.visibilityState='hidden';await intervals[0][0]();assert.equal(calls,before+1);
  context.document.visibilityState='visible';await documentEvents.visibilitychange();assert.equal(calls,before+2);
  console.log('Monitoring UI: green/orange, quota, network failure/recovery, offline and background polling: OK');
})().catch(error=>{console.error(error);process.exitCode=1});
