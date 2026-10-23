// In-memory DOM render checks; headless visual QA is separately in browser/.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=spawnSync('python3',['tests/narrative_preview_fixture.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'});
 assert.equal(fixture.status,0,fixture.stderr);let snapshot=JSON.parse(fixture.stdout);
 const nodes=new Map(),events={},requests=[];
 function node(id){if(!nodes.has(id))nodes.set(id,{id,innerHTML:'',textContent:'',value:'',style:{},dataset:{},classList:{toggle(){},add(){},remove(){}},addEventListener(){},setAttribute(){},removeAttribute(){},focus(){},closest(){return node(id+'parent')},querySelector(s){return node(id+s)},querySelectorAll(){return []}});return nodes.get(id);}
 const window={localStorage:new Proxy({},{get(){throw Error('Browser persistence forbidden')}}),SignalSession:{ready:Promise.resolve(),csrf:()=> 'csrf'},addEventListener(name,fn){(events[name]??=[]).push(fn)},dispatchEvent(e){for(const f of events[e.type]||[])f(e)}};
 const document={getElementById:node,querySelector:node,querySelectorAll:()=>[],addEventListener(){},body:node('body'),activeElement:{tagName:'BODY'}};
 const context={window,document,location:{hash:'#map'},history:{replaceState(){}},Intl,Date,URL,URLSearchParams,setTimeout,clearTimeout,setInterval(){},console,Event:class{constructor(type){this.type=type}},fetch:async(url,options={})=>{
  requests.push([url,options]);
  if(url==='/api/dashboard/context')return {ok:true,json:async()=>({context:null})};
  if(url==='/api/dashboard/bootstrap')return {ok:true,json:async()=>structuredClone(snapshot)};
  return {ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'dist/metrics-context.json')))};
 }};
 vm.createContext(context);
 for(const file of ['source-content.js','exercise-context.js','thermometer.js','demo/narrative-history.js','metrics-context.js','counts.js','growth.js','platform-overview.js','live-data.js','app.js'])vm.runInContext(fs.readFileSync(path.join(root,'dist',file),'utf8'),context);
 await window.SignalLiveData.ready;await new Promise(resolve=>setImmediate(resolve));
 const ui=window.SignalDemo;
 assert(!node('view').innerHTML.includes('Duomenų įkelti nepavyko'),node('view').innerHTML);
 ui.selectTheme('security','map');
 assert(!node('theme').innerHTML.includes('value="all"'));
 assert.equal(ui.visibleNarratives().length,2);
 ui.selectNarrative('N001','map');
 const html=node('view').innerHTML;
 assert(html.includes('neaišku: 1'));assert(html.includes('Perteikia'));
 assert.equal((html.match(/class="registry-variant"/g)||[]).length,2);
 assert(html.includes('N004'));assert(html.includes('https://example.test/source/a'));
 assert(html.includes('target="_blank"'));assert(html.includes('narrative-excerpt'));
 ui.state.sort='newest';ui.render();assert.equal(ui.state.expanded,'N001');
 assert.equal((node('view').innerHTML.match(/class="registry-type"/g)||[]).length,14);
 ui.selectTheme('identity','map');
 assert(node('view').innerHTML.includes('Naujas kandidatas'));assert(node('view').innerHTML.includes('Auditorija nežinoma'));
 assert(!node('view').innerHTML.includes('class="graph-node'));
 assert.equal((node('view').innerHTML.match(/class="registry-type"/g)||[]).length,4); // 1 candidate and 3 fixed types, collapsed parents
 ui.selectTheme('health','map');
 assert(node('view').innerHTML.includes('Patvirtintų tipų registras'));
 assert(!node('view').innerHTML.includes('Turinys be naratyvo'));
 ui.setView('overview');ui.resetFilters();
 assert.equal(vm.runInContext('total(visibleNarratives())',context),4,'global union, not 5 assignments');
 const state={period:1,theme:'economy',themeScope:'all',status:'all',query:''};
 assert.equal(window.SignalLiveData.units(state).length,1,'secondary match included in its primary topic');
 const prepared=ui.prepareAnalysisInput(snapshot.units[0]);assert.equal(prepared.narrative_registry.types.length,35);
 // Same collection date but new analysis must refresh. Selection remains intact.
 ui.selectNarrative('N001','map');
 snapshot={...snapshot,analysis_revision:'test-2'};await window.SignalLiveData.refresh();
 assert.equal(window.SignalLiveData.get().analysis_revision,'test-2');assert.equal(ui.state.expanded,'N001');
 assert(requests.every(([url,options])=>!options.method||options.method==='GET'),'reading the map never writes or runs AI');
 // Model/source strings are escaped in all new markup.
 snapshot.registry.types[0].title='<script>alert(1)</script>';
 await window.SignalLiveData.syncContext();
 assert(!window.SignalLiveData.registryPanel({theme:'all',query:''}).includes('<script>'));
 console.log('Narrative render checks passed: 35 types, fixed topics, multi-claim union, variants, unknown coverage, candidate separation, source links, escaping, analysis refresh and preserved expansion.');
})().catch(e=>{console.error(e);process.exitCode=1});
