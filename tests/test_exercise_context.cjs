// Context persists through the authenticated database API, never Web Storage.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
let stored=null,fail=false,supplements=[];
async function runtime(){
 const nodes=new Map(),events={};
 function node(id){if(!nodes.has(id))nodes.set(id,{id,innerHTML:'',textContent:'',value:'',dataset:{},classList:{toggle(){},add(){},remove(){}},addEventListener(){},focus(){},querySelector(s){return node(id+s)},querySelectorAll(){return []}});return nodes.get(id);}
 const window={localStorage:new Proxy({},{get(){throw Error('Local persistence forbidden')}}),SignalSession:{ready:Promise.resolve(),csrf:()=> 'csrf'},addEventListener(name,fn){(events[name]??=[]).push(fn)},dispatchEvent(e){for(const f of events[e.type]||[])f(e)}};
 const document={getElementById:node,querySelector:node,querySelectorAll:()=>[],addEventListener(){},body:node('body'),activeElement:{tagName:'BODY'}};
 const context={window,document,location:{hash:'#context'},history:{replaceState(){}},Intl,Date,URL,setTimeout,clearTimeout,console,Event:class{constructor(type){this.type=type}},fetch:async(url,options={})=>{
  if(url==='/api/dashboard/context'){
   if(fail)return {ok:false,json:async()=>({error:'Database unavailable'})};
   if(options.method==='POST'){
    assert.equal(options.headers['X-Signalas-CSRF'],'csrf');
    if(stored)return {ok:false,json:async()=>({error:'Kontekstas jau išsaugotas'})};
    stored=JSON.parse(options.body).context;
   }
   return {ok:true,json:async()=>({context:structuredClone(stored),supplements:structuredClone(supplements)})};
  }
  return {ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,url.includes('metrics')?'dist/metrics-context.json':url.includes('platform')?'dist/demo/platform-7.json':'dist/demo/thermometer-7.json')))};
 }};
 vm.createContext(context);
 for(const file of ['source-content.js','exercise-context.js','thermometer.js','demo/narrative-history.js','metrics-context.js','counts.js','growth.js','platform-overview.js'])vm.runInContext(fs.readFileSync(path.join(root,'dist',file),'utf8'),context);
 await window.SignalExerciseContext.ready;
 vm.runInContext(fs.readFileSync(path.join(root,'dist/app.js'),'utf8'),context);
 return {window,node};
}
const plain=x=>JSON.parse(JSON.stringify(x));
(async()=>{
 const first=await runtime(),api=first.window.SignalExerciseContext,form=first.node('exercise-context-root');
 const demo=first.window.SignalDemo;
 demo.setView('map');
 assert.equal((first.node('theme').innerHTML.match(/<option /g)||[]).length,demo.themes.length);
 assert(!first.node('theme').innerHTML.includes('value="all"'));
 assert(!first.node('theme').innerHTML.includes('unassigned'));
 assert(!first.node('theme-scope').innerHTML.includes('Visos temos'));
 assert(demo.themes.some(t=>t.id===demo.state.theme));
 assert(demo.visibleNarratives().every(n=>n.theme===demo.state.theme));
 const emptyTopic=demo.themes.find(t=>!demo.narratives.some(n=>n.theme===t.id));
 if(emptyTopic){demo.selectTheme(emptyTopic.id);assert(!first.node('view').innerHTML.includes('Rodyti visas temas'));}
 demo.state.sort='oldest';demo.resetFilters();assert.notEqual(demo.state.theme,'all');
 demo.selectTheme(demo.themes.at(-1).id);assert.equal(demo.state.theme,demo.themes.at(-1).id);
 assert(demo.visibleNarratives().every(n=>n.theme===demo.state.theme));
 const evidenceNarrative=demo.narratives.find(n=>demo.themes.some(t=>t.id===n.theme));
 demo.selectNarrative(evidenceNarrative.id,'map');
 assert.equal(demo.state.theme,evidenceNarrative.theme);assert.equal(demo.state.expanded,evidenceNarrative.id);
 demo.selectThemeScope('priority');assert.equal(demo.state.themeScope,'all');
 assert.equal((first.node('theme').innerHTML.match(/<option /g)||[]).length,demo.themes.length);
 demo.setView('overview');demo.resetFilters();assert(first.node('theme').innerHTML.includes('value="all"'));
 demo.setView('context');
 assert.equal(api.get(),null);assert.equal((form.innerHTML.match(/<textarea /g)||[]).length,2);
 await assert.rejects(api.save({initialSituation:' ',confirmedFacts:'Fact'}));assert.equal(stored,null);
 const input={initialSituation:'Pratybos <script>test</script>',confirmedFacts:'Patvirtinti faktai',nameMappings:[{id:'stable',realName:'Lietuva',exerciseName:'Litanija'}]};
 await api.save(input);assert.deepEqual(plain(api.get()),input);
 await assert.rejects(api.save(input),/jau išsaugotas/);
 const fresh=await runtime();assert.deepEqual(plain(fresh.window.SignalExerciseContext.get()),input);
 assert(fresh.node('exercise-context-root').innerHTML.includes('readonly'));
 assert(!fresh.node('exercise-context-root').innerHTML.includes('<script>test</script>'));
 const invalid=[{id:'a',realName:'A',exerciseName:'B'},{id:'b',realName:'a',exerciseName:'b'}];
 assert(api.validateMappings(invalid).issues.length>0);
 assert(api.validateMappings([{id:'a',realName:'A',exerciseName:''}]).issues.length>0);
 assert.equal(api.validateMappings([{id:'a',realName:'',exerciseName:''}]).nameMappings.length,0);
 const unit={id:'1',source:'pod',kind:'comment',published_at:'2026-10-21T12:00:00Z',text:'Naujas įvykis',sourceUrl:'https://pod.test/real-source',media:[],conversation_context:[{published_at:'2026-10-21T11:00:00Z',text:'Prieš'},{published_at:'2026-10-21T13:00:00Z',text:'Po'}]};
 const narrative=fresh.window.SignalDemo.prepareAnalysisInput(unit),thermometer=fresh.window.SignalThermometer.prepareAnalysisInput(unit);
 assert.deepEqual(plain(narrative.exercise_context),plain(thermometer.exercise_context));assert.equal(narrative.theme_catalog.length,15);
 assert(narrative.allow_new_narratives);assert.equal(thermometer.requires_narrative_assignment,false);
 assert.equal(narrative.content.conversation_context.length,1);assert.equal(narrative.content.sourceUrl,unit.sourceUrl);
 stored={initialSituation:'Legacy',confirmedFacts:'Facts'};
 const legacy=await runtime();assert.deepEqual(plain(legacy.window.SignalExerciseContext.get().nameMappings),[]);
 supplements=[{id:'test-valare',text:'VALARE <script>test</script>',effective_at:'2026-10-24T12:00:00Z'}];
 const clarified=await runtime();
 const clarifiedHTML=clarified.node('exercise-context-root').innerHTML;
 assert(clarifiedHTML.includes('Papildomas analizės kontekstas'));
 assert(clarifiedHTML.includes('Taikomas tik dar nevertintam ir naujam turiniui'));
 assert(!clarifiedHTML.includes('<script>test</script>'));
 assert.deepEqual(plain(clarified.window.SignalExerciseContext.get()),{...stored,nameMappings:[]});
 supplements=[];
 stored=null;fail=true;const broken=await runtime();assert.throws(()=>broken.window.SignalExerciseContext.get());
 await assert.rejects(broken.window.SignalExerciseContext.save(input));assert.equal(stored,null);
 console.log('Database context save/reload, immutability, mappings, fail-closed reads and shared analysis: OK');
})().catch(e=>{console.error(e);process.exitCode=1});
