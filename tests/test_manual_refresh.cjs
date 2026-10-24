const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('dist/manual-refresh.js','utf8');
(async()=>{
 let click,mode='ok',calls=[],redraws=0,release;
 const button={disabled:false,addEventListener:(event,fn)=>click=fn,setAttribute(){},removeAttribute(){}};
 const message={textContent:''};
 const runtime={document:{getElementById:id=>id==='fetch-data'?button:message},window:{SignalSession:{ready:Promise.resolve()},SignalLiveData:{refresh:async()=>redraws++},SignalMonitoring:{refresh:async()=>{}}},fetch:async(url,options)=>{
  calls.push([url,options]);if(url.endsWith('/status'))return {ok:true,json:async()=>({available:true,csrf:'token'})};
  if(mode==='pending')await new Promise(r=>release=r);
  if(mode==='failure')throw Error('Network failed');
  return {ok:true,json:async()=>mode==='running'?{status:'already_running'}:mode==='checkpoint'?{status:'pending',processed_posts:4,discovered_posts:20}:{status:'ok',posts:15,comments:115}};
 }};
 vm.runInNewContext(source,runtime);
 assert.equal(calls.length,0,'mount must never collect');
 await click();assert.equal(redraws,1);assert(message.textContent.includes('15'));
 assert.equal(calls[1][1].method,'POST');assert.equal(calls[1][1].headers['X-Signalas-CSRF'],'token');
 mode='pending';const first=click();await new Promise(r=>setImmediate(r));const before=calls.length;
 await click();assert.equal(calls.length,before);assert(button.disabled);release();await first;assert(!button.disabled);
 mode='running';await click();assert(message.textContent.includes('jau vyksta'));
 mode='checkpoint';const redrawBefore=redraws;await click();assert(message.textContent.includes('4 iš 20'));assert.equal(redraws,redrawBefore);
 mode='failure';await click();assert(message.textContent.includes('Network failed'));assert(!button.disabled);
 for(const file of fs.readdirSync('dist').filter(x=>x.endsWith('.js'))){assert(!/localStorage|sessionStorage|indexedDB/.test(fs.readFileSync('dist/'+file,'utf8')),file+' may not persist browser data');}
 console.log('Manual fetch only, duplicate-click protection, CSRF, errors and no browser persistence: OK');
})().catch(e=>{console.error(e);process.exitCode=1});
