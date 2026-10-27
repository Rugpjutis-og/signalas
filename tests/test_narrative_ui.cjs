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
 assert(node('view').innerHTML.includes('Siūlomas subnaratyvas'));assert(node('view').innerHTML.includes('Auditorija nežinoma'));
 assert(!node('view').innerHTML.includes('class="graph-node'));
 assert.equal((node('view').innerHTML.match(/class="registry-type"/g)||[]).length,4); // 1 candidate and 3 fixed types, collapsed parents
 ui.selectTheme('health','map');
 assert(node('view').innerHTML.includes('Patvirtintų tipų registras'));
 assert(!node('view').innerHTML.includes('Turinys be naratyvo'));
 ui.setView('overview');ui.resetFilters();
 assert.equal(vm.runInContext('total(visibleNarratives())',context),4,'global union, not 5 assignments');
 // Parent count includes branches, deduplicates overlaps, and respects source/period.
 const latest=snapshot.days[snapshot.days.length-1],earlier=new Date(Date.parse(latest+'T12:00:00Z')-86400000).toISOString().slice(0,10);
 const direct={source:'pod.test',id:'shared',kind:'post',published_at:latest+'T09:00:00Z'};
 const child={source:'pod.test',id:'child-comment',kind:'comment',published_at:latest+'T10:00:00Z'};
 const otherSource={...direct,source:'other.test'};
 const outside={...child,id:'outside',published_at:'2000-01-01T10:00:00Z'};
 const combined={days:[99],evidence:[direct,direct],subnarratives:[{evidence:[direct,child,outside]},{evidence:[child,otherSource]}]};
 ui.state.period=1;
 assert.equal(ui.count(combined),3,'same unit across parent/branches counts once; distinct source remains distinct');
 assert.equal(ui.count({...combined,evidence:[]}),3,'branch-only parent has its branch union, not zero');
 assert.equal(vm.runInContext('count({days:[99],evidence:[],subnarratives:[]})',context),0,'no fallback to unrelated daily counts in live mode');
 const oldDays=snapshot.days;
 snapshot.days=[earlier,latest];await window.SignalLiveData.syncContext();
 combined.subnarratives[0].evidence.push({...child,id:'previous-day',published_at:earlier+'T09:00:00Z'});
 assert.equal(ui.count(combined),3,'one-day window excludes older branch content');
 ui.state.period=2;assert.equal(ui.count(combined),4,'changing period includes older branch content once');
 snapshot.days=oldDays;await window.SignalLiveData.syncContext();ui.state.period=1;
 const state={period:1,theme:'economy',themeScope:'all',status:'all',query:''};
 assert.equal(window.SignalLiveData.units(state).length,1,'secondary match included in its primary topic');
 const prepared=ui.prepareAnalysisInput(snapshot.units[0]);assert.equal(prepared.narrative_registry.types.length,35);
 // Same collection date but new analysis must refresh. Selection remains intact.
 ui.selectNarrative('N001','map');
 snapshot={...snapshot,analysis_revision:'test-2'};await window.SignalLiveData.refresh();
 assert.equal(window.SignalLiveData.get().analysis_revision,'test-2');assert.equal(ui.state.expanded,'N001');
 assert(requests.every(([url,options])=>!options.method||options.method==='GET'),'reading the map never writes or runs AI');
 // Official thematic branches retain their parent and original source URL without claiming parent support.
 const branch={id:'Cofficial',title:'Informacijos per mažai',claim_template:'Pateikiama mažai informacijos.',
   topic_id:'T09',parent_type_id:'N007',unit_count:1,evidence:[snapshot.units[0]],status:'confirmed'};
 snapshot.subnarratives=[branch];snapshot.analysis_revision='official-branches';
 await window.SignalLiveData.syncContext();
 const branches=window.SignalLiveData.candidatePanel({theme:'all',status:'all',query:''});
 assert(branches.includes('Subnaratyvai'));assert(branches.includes('Pagrindinis naratyvas: N007'));
 assert(branches.includes('Patvirtinta teminė atšaka'));assert(branches.includes('https://example.test/source/'));
 assert(!branches.includes('Naujas kandidatas'));
 assert(!window.SignalLiveData.candidatePanel({theme:'health',status:'all',query:''}).includes('Informacijos per mažai'));
 // Selecting a parent exposes only its approved, in-period subnarratives as graph nodes.
 const graphBranch={...branch,id:'Cgraph',parent_type_id:'N001',topic_id:'T03',title:'Pasirengimo pratyboms trūkumas'};
 const otherBranch={...graphBranch,id:'Cother',parent_type_id:'N004',title:'Kita atšaka'};
 snapshot.subnarratives=[graphBranch,otherBranch];
 snapshot.narratives.find(n=>n.id==='N001').subnarratives=[graphBranch,{...graphBranch,id:'Cunapproved',status:'candidate'}];
 snapshot.narratives.find(n=>n.id==='N004').subnarratives=[otherBranch];
 await window.SignalLiveData.syncContext();
 window.SignalDemo.refreshLive(window.SignalLiveData.get());
 ui.selectTheme('security','map');ui.selectNarrative('N001','map');
 let graphMarkup=node('view').innerHTML;
 assert(graphMarkup.includes('data-subnarrative="Cgraph"'));
 assert(graphMarkup.includes('graph-subnarrative-edge'));
 assert(!graphMarkup.includes('data-subnarrative="Cother"'));
 assert(!graphMarkup.includes('data-subnarrative="Cunapproved"'));
 const before=ui.count(ui.narratives.find(n=>n.id==='N001'));
 ui.selectSubnarrative('N001','Cgraph');
 assert.equal(ui.state.selected,'N001');assert.equal(ui.state.expanded,'N001');
 assert.equal(ui.state.subnarrative,'Cgraph');
 graphMarkup=node('view').innerHTML;
 assert(graphMarkup.includes('id="subnarrative-Cgraph-detail-N001" open'));
 assert(graphMarkup.includes('aria-controls="subnarrative-Cgraph-detail-N001"'));
 assert(graphMarkup.includes('role="button" tabindex="0" data-subnarrative="Cgraph"'));
 assert.equal(ui.count(ui.narratives.find(n=>n.id==='N001')),before,'graph expansion never changes statistics');
 ui.selectNarrative('N004','map');graphMarkup=node('view').innerHTML;
 assert(graphMarkup.includes('data-subnarrative="Cother"'));
 assert(!graphMarkup.includes('data-subnarrative="Cgraph"'));
 ui.selectTheme('health','map');assert(!node('view').innerHTML.includes('data-subnarrative='));
 // Model/source strings are escaped in all new markup.
 snapshot.registry.types[0].title='<script>alert(1)</script>';
 await window.SignalLiveData.syncContext();
 assert(!window.SignalLiveData.registryPanel({theme:'all',query:''}).includes('<script>'));
 console.log('Narrative render checks passed: 35 types, fixed topics, multi-claim union, variants, unknown coverage, candidate separation, source links, escaping, analysis refresh and preserved expansion.');
})().catch(e=>{console.error(e);process.exitCode=1});
