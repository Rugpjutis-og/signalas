const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
(async()=>{
 let calls=[],redraws=0,resolveReady;
 const button={disabled:false,setAttribute(){},removeAttribute(){}};
 const message={textContent:''};
 const queue=[{status:'pending',remaining:2},{status:'pending',remaining:1},{status:'complete',remaining:0}];
 const window={SignalSession:{ready:new Promise(r=>resolveReady=r),csrf:()=> 'csrf-test'},SignalLiveData:{refresh:async()=>redraws++},SignalMonitoring:{refresh:async()=>{}}};
 const runtime={window,document:{getElementById:id=>id==='fetch-data'?button:message},setTimeout,setInterval:()=>1,clearInterval:()=>{},fetch:async(url,options)=>{
  calls.push({url,options});return {ok:true,json:async()=>queue.shift()};
 }};
 vm.runInNewContext(fs.readFileSync('dist/analysis-runner.js','utf8'),runtime);
 assert.equal(calls.length,0,'no request before authentication');resolveReady();
 await new Promise(r=>setImmediate(r));
 assert.equal(calls.length,3);assert.equal(redraws,2);assert(!button.disabled);
 assert(calls.every(c=>c.url.startsWith('/api/analysis/')),'resuming must not collect');
 assert.equal(calls[1].options.headers['X-Signalas-CSRF'],'csrf-test');
 queue.push({status:'error',reason:'api_quota',remaining:1});
 await window.SignalAnalysis.run({status:'pending',remaining:1});
 assert(message.textContent.includes('kreditus'));assert.equal(calls.length,4,'do not retry failure');
 console.log('Analysis queue: authenticated resume, sequential steps, CSRF, progress, no collection and quota stop: OK');
})().catch(e=>{console.error(e);process.exitCode=1});
