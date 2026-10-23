const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../dist/live-data.js'),'utf8');
(async()=>{
  let snapshot={mode:'live',csrf:'test',collected_at:'first',
    days:Array.from({length:10},(_,i)=>`2026-10-${String(12+i).padStart(2,'0')}`),
    start:'2026-10-12T00:00:00+03:00',end:'2026-10-22T00:00:00+03:00',range_saved:true,units:[]},fail=false,denyImageOnce=false;
  const calls=[],renders=[],timers=[],listeners={},dateInput={value:''};
  const context={window:{SignalSourceContent:{escape:x=>x},SignalExerciseContext:{get:()=>null},
    SignalDemo:{refreshLive:(data,options)=>renders.push([data.collected_at,options.preserveDay])}},
    document:{visibilityState:'visible',getElementById:()=>dateInput,addEventListener:(event,callback)=>listeners[event]=callback},
    Date,URLSearchParams,setInterval:(callback,ms)=>timers.push({callback,ms}),fetch:async(url,options)=>{
      calls.push([url,options]);
      if(url==='/api/dashboard/period'&&!fail){
        const dates=JSON.parse(options.body),start=Date.parse(dates.start_date),end=Date.parse(dates.end_date);
        snapshot={...snapshot,start:dates.start_date+'T00:00:00+03:00',end:new Date(end+86400000).toISOString(),
          days:Array.from({length:(end-start)/86400000+1},(_,i)=>new Date(start+i*86400000).toISOString().slice(0,10))};
      }
      const denied=url.startsWith('/api/media/image')&&denyImageOnce;if(denied)denyImageOnce=false;
      return {ok:!fail&&!denied,status:denied?403:fail?500:200,json:async()=>structuredClone(snapshot),
        headers:{get:()=> 'image/webp'},blob:async()=>({type:'image/webp'})};
    }};
  vm.createContext(context);vm.runInContext(code,context);
  const live=context.window.SignalLiveData;await live.ready;
  for(const [period,start] of [[10,'2026-10-12'],[7,'2026-10-15'],[3,'2026-10-19'],[1,'2026-10-21']]){
    assert.equal(live.periodBounds(period).start,start);
    assert.equal(live.periodBounds(period).end,'2026-10-21');
  }
  assert(live.inPeriod({published_at:'2026-10-14T10:00:00Z'},10));
  assert(!live.inPeriod({published_at:'2026-10-14T10:00:00Z'},7));
  assert.equal(live.range().key,'2026-10-12/2026-10-21');
  assert.equal(live.range().query,'start_date=2026-10-12&end_date=2026-10-21');
  assert.equal(timers.length,1);assert.equal(timers[0].ms,60000);
  await live.refresh();assert.equal(renders.length,0,'unchanged data must not collapse rendered content');
  snapshot={...snapshot,collected_at:'second'};await timers[0].callback();
  assert.deepEqual(renders,[['second',true]]);
  assert.equal(live.get().collected_at,'second');
  assert(!calls.some(([url])=>url.includes('/period')),'background refresh must not write the chosen dates');
  assert(calls.every(([url])=>url.startsWith('/api/dashboard/')),'snapshot checks only read the local server');
  assert.equal((await live.image('pod.test','post',0)).type,'image/webp');
  const [mediaUrl,mediaRequest]=calls.at(-1);
  assert(mediaUrl.startsWith('/api/media/image?'));
  assert.deepEqual([...new URLSearchParams(mediaUrl.split('?')[1]).keys()],['source','id','index'],'access token must never be placed in the URL');
  assert.equal(mediaRequest.headers['X-Signalas-CSRF'],'test');
  denyImageOnce=true;snapshot={...snapshot,csrf:'refreshed-after-server-restart'};
  await live.image('pod.test','post',0);
  assert.equal(calls.at(-1)[1].headers['X-Signalas-CSRF'],'refreshed-after-server-restart');
  assert.equal(renders.length,1,'token refresh must not reset the rendered view');
  const originalCollection=live.get().collected_at;
  await live.setPeriod('2026-09-29','2026-10-21');
  assert.equal(live.range().period,23);
  assert.equal(live.get().collected_at,originalCollection,'filtering must reuse the original collection');
  assert.equal(live.range().start_date,'2026-09-29');
  assert(live.inPeriod({published_at:'2026-09-29T10:00:00Z'},23));
  const writes=calls.filter(([url])=>url==='/api/dashboard/period');
  assert.equal(writes.length,1);
  assert.deepEqual(JSON.parse(writes[0][1].body),{start_date:'2026-09-29',end_date:'2026-10-21'});
  assert(calls.every(([url])=>url.startsWith('/api/dashboard/')||url.startsWith('/api/media/image')),'no source collector or AI request');
  snapshot={...snapshot,data_revision:'r1'};await live.refresh();
  const beforeCheck=calls.length;
  await live.refresh();
  assert.equal(calls.length,beforeCheck+1,'unchanged revision needs only one small request');
  assert.equal(calls.at(-1)[0],'/api/dashboard/revision','do not download full content on an unchanged poll');
  snapshot={...snapshot,data_revision:'r2'};await live.refresh();
  assert.equal(live.get().data_revision,'r2','changed revision reloads actual content');
  fail=true;await assert.rejects(live.refresh(),/paskutinė/);
  assert.equal(live.get().collected_at,'second','failed refresh preserves the last snapshot');
  fail=false;snapshot={...snapshot,collected_at:'third'};context.document.visibilityState='hidden';
  await timers[0].callback();assert.equal(live.get().collected_at,'second');
  console.log('Live snapshot refresh, unchanged selection and failure preservation: OK');
})().catch(error=>{console.error(error);process.exitCode=1});
