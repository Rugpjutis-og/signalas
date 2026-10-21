// Isolated Web Storage and UI integration checks. No browser automation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const scripts=['source-content.js','exercise-context.js','thermometer.js','demo/narrative-history.js','metrics-context.js','counts.js','growth.js','platform-overview.js','app.js'].map(file=>fs.readFileSync(path.join(root,'dist',file),'utf8'));
const contents=new Map();
const storage={getItem:key=>contents.get(key)??null,setItem:(key,value)=>contents.set(key,String(value))};
function runtime(localStorage=storage,hash='#context'){
  const nodes=new Map(),events={};
  function node(id){if(!nodes.has(id))nodes.set(id,{id,innerHTML:'',textContent:'',value:'',isConnected:true,dataset:{},classList:{toggle(){},add(){},remove(){}},addEventListener(){},focus(){},querySelector(s){return node(id+s)},querySelectorAll(){return []}});return nodes.get(id);}
  const document={getElementById:node,querySelector:node,querySelectorAll:()=>[],addEventListener(){},body:node('body'),activeElement:{tagName:'BODY'}};
  const window={localStorage,addEventListener(name,fn){(events[name]??=[]).push(fn)},dispatchEvent(event){for(const fn of events[event.type]||[])fn(event)}};
  const context={window,document,location:{hash},history:{replaceState(){}},Intl,Date,URL,setTimeout,clearTimeout,console,Event:class{constructor(type){this.type=type}},fetch:async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,url.includes('metrics')?'dist/metrics-context.json':url.includes('platform')?'dist/demo/platform-'+(url.match(/period=(\d+)/)?.[1]||7)+'.json':'dist/demo/thermometer-7.json')))})};
  vm.createContext(context);for(const source of scripts)vm.runInContext(source,context);
  return {context,window,node};
}
const toPlain=value=>JSON.parse(JSON.stringify(value));
const first=runtime();
assert.equal(first.window.SignalExerciseContext.get(),null);
assert(first.node('navigation').innerHTML.includes('Pratybų kontekstas'));
const formRoot=first.node('exercise-context-root');
assert.equal((formRoot.innerHTML.match(/<textarea /g)||[]).length,2);
assert(formRoot.innerHTML.includes('Pradinė situacija'));
assert(formRoot.innerHTML.includes('Patvirtinti scenarijaus faktai'));
assert(!formRoot.innerHTML.includes('readonly'));
// Whitespace fails validation and never writes to storage.
formRoot.querySelector('#exercise-initial-situation').value='  ';
formRoot.querySelector('#exercise-confirmed-facts').value='Faktas';
formRoot.querySelector('form').onsubmit({preventDefault(){}});
assert.equal(contents.size,0);
assert(formRoot.querySelector('#exercise-save-error').textContent.includes('Užpildykite'));
// Submit from the actual form handler; save only the two allowed fields.
const initial={initialSituation:'Fiktyvus miestas. Vyksta pratybos. <script>test</script>',confirmedFacts:'Tiekimas sutrikęs. Tyrimų rezultatai dar nežinomi.',nameMappings:[]};
formRoot.querySelector('#exercise-initial-situation').value=initial.initialSituation;
formRoot.querySelector('#exercise-confirmed-facts').value=initial.confirmedFacts;
formRoot.querySelector('form').onsubmit({preventDefault(){}});
assert.deepEqual(toPlain(first.window.SignalExerciseContext.get()),initial);
assert.equal((formRoot.innerHTML.match(/readonly/g)||[]).length,2);
assert(formRoot.innerHTML.includes('Kontekstas ir atitikmenys išsaugoti'));
assert(!formRoot.innerHTML.includes('<script>test</script>'));
assert(formRoot.innerHTML.includes('&lt;script&gt;test&lt;/script&gt;'));
assert(first.node('analysis-context-note').innerHTML.includes('AI analizė dar neprijungta'));
const rawBefore=[...contents.values()][0];
assert.throws(()=>first.window.SignalExerciseContext.save({initialSituation:'Kita',confirmedFacts:'Kiti'}),/jau išsaugotas/);
assert.equal([...contents.values()][0],rawBefore);
// New page runtime, same persisted storage: equivalent to module reload after refresh.
const refreshed=runtime();
assert.deepEqual(toPlain(refreshed.window.SignalExerciseContext.get()),initial);
assert(refreshed.node('exercise-context-root').innerHTML.includes('readonly'));
assert(Object.isFrozen(refreshed.window.SignalExerciseContext.get()));
const unit={id:'NEW-1',source:'exercise',published_at:'2026-10-19T12:00:00+03:00',text:'Naujas, pradžioje nenumatytas įvykis.',attachments:[],author_role:'unknown',stance:'oppose',
  parent_post:{id:'parent',published_at:'2026-10-19T10:00:00+03:00',text:'Pirminis įrašas',attachments:[{kind:'image',asset:'original-image'}]},
  conversation_context:[{published_at:'2026-10-19T11:00:00+03:00',text:'Ankstesnis komentaras'},
                        {published_at:'2026-10-19T13:00:00+03:00',text:'Vėlesnis komentaras'}]};
const narrative=refreshed.window.SignalDemo.prepareAnalysisInput(unit);
const thermometer=refreshed.window.SignalThermometer.prepareAnalysisInput(unit);
assert.deepEqual(toPlain(narrative.exercise_context),toPlain(thermometer.exercise_context));
assert.deepEqual(toPlain(thermometer.exercise_context),initial);
assert(narrative.allow_new_narratives);assert.equal(narrative.theme_catalog.length,15);
assert.equal(thermometer.requires_narrative_assignment,false);
assert.equal(thermometer.stream_scope,'all_content');assert.equal(thermometer.review_policy.category,null);
assert.equal(narrative.analysis_executed,false);assert.equal(thermometer.analysis_executed,false);
assert.equal(narrative.content.conversation_context.length,1);
assert.equal(narrative.content.parent_post.attachments.length,1);
assert(!Object.hasOwn(narrative.content,'author_role'));assert(!Object.hasOwn(narrative.content,'stance'));
assert.equal([...contents.values()][0],rawBefore); // Preparing discussion never changes initial facts.
const snapshot=JSON.stringify(thermometer.exercise_context);
thermometer.content.parent_post.text='changed';
assert.equal(JSON.stringify(refreshed.window.SignalExerciseContext.get()),snapshot);
// Existing global filters cannot change the shared context or whole-stream scope.
refreshed.window.SignalDemo.state.theme='health';refreshed.window.SignalDemo.state.query='nothing-matches';
assert.deepEqual(toPlain(refreshed.window.SignalDemo.prepareAnalysisInput(unit).exercise_context),initial);
assert.equal(refreshed.window.SignalThermometer.prepareAnalysisInput(unit).stream_scope,'all_content');
// Read failures and corrupted storage fail closed; never overwrite stored content.
const blocked=runtime({getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}});
assert(blocked.node('exercise-context-root').innerHTML.includes('disabled'));
assert(!blocked.node('exercise-context-root').innerHTML.includes('Kontekstas išsaugotas šioje naršyklėje'));
const corrupt=runtime({getItem:()=>'{bad-json',setItem(){throw Error('must not write')}});
assert.throws(()=>corrupt.window.SignalExerciseContext.save(initial),/nepavyko perskaityti/);
const full=runtime({getItem:()=>null,setItem(){throw Error('quota')}});
assert.throws(()=>full.window.SignalExerciseContext.save(initial),/išsaugoti nepavyko/);
assert.equal(full.window.SignalExerciseContext.get(),null);
const noContext=runtime({getItem:()=>null,setItem(){}},'#overview');
assert.equal(noContext.window.SignalDemo.prepareAnalysisInput(unit).exercise_context,null);
assert.throws(()=>noContext.window.SignalDemo.prepareAnalysisInput({...unit,published_at:'2026-10-19T12:00:00'}),/laiko juostą/);
// Optional mappings: preserve IDs and text, and never silently pick a conflicting alias.
const mappingsAPI=first.window.SignalExerciseContext;
const row=(id,realName,exerciseName)=>({id,realName,exerciseName});
assert.deepEqual(toPlain(mappingsAPI.validateMappings(undefined)),{nameMappings:[],issues:[]});
assert.equal(mappingsAPI.validateMappings([row('empty','  ','\n')]).nameMappings.length,0);
assert.equal(mappingsAPI.validateMappings([row('half','Lietuva','')]).issues.length,1);
assert.equal(mappingsAPI.validateMappings([row('half','','Šilija')]).issues.length,1);
const duplicate=mappingsAPI.validateMappings([row('a','Lietuva','Šilija'),row('b',' lietuva ',' šilija ')]);
assert.equal(duplicate.issues.length,2);
for(const pair of [[row('a','Lietuva','Šilija'),row('b','Lietuva','Rytija')],
                   [row('a','Lietuva','Šilija'),row('b','Latvija','Šilija')]]){
 const checked=mappingsAPI.validateMappings(pair);
 assert.equal(checked.issues.length,2);
 assert(checked.issues.every(issue=>issue.message.includes('Prieštaringas')));
}
assert.throws(()=>mappingsAPI.validateMappings([row('same','A','B'),row('same','C','D')]),/unikalų pastovų ID/);
const isolated=new Map();const isolatedStorage={getItem:key=>isolated.get(key)??null,setItem:(key,value)=>isolated.set(key,value)};
const mappingPage=runtime(isolatedStorage);
const withNames={...initial,nameMappings:[row('stable-country-id','Lietuva','Šilija'),row('stable-org-id','Organizacija A','Iniciatyva B'),row('blank','','')]};
assert.throws(()=>mappingPage.window.SignalExerciseContext.save({...initial,nameMappings:[row('half','Lietuva','')]}),/Patikrinkite/);
assert.equal(isolated.size,0);
assert.throws(()=>mappingPage.window.SignalExerciseContext.save({...initial,nameMappings:[row('a','Lietuva','Šilija'),row('b','Lietuva','Rytija')]}),/Patikrinkite/);
assert.equal(isolated.size,0);
mappingPage.window.SignalExerciseContext.save(withNames);
const mappingReload=runtime(isolatedStorage);
const restored=mappingReload.window.SignalExerciseContext.get();
assert.equal(restored.nameMappings.length,2);assert.equal(restored.nameMappings[0].id,'stable-country-id');
assert(Object.isFrozen(restored.nameMappings));assert(Object.isFrozen(restored.nameMappings[0]));
const mappedUnit={...unit,text:'Šilijoje naujas pasakojimas apie Iniciatyvą B.',url:'https://exercise.invalid/posts/NEW-1'};
const left=mappingReload.window.SignalDemo.prepareAnalysisInput(mappedUnit),right=mappingReload.window.SignalThermometer.prepareAnalysisInput(mappedUnit);
assert.deepEqual(toPlain(left.exercise_context.nameMappings),toPlain(right.exercise_context.nameMappings));
assert.equal(left.content.text,mappedUnit.text);
assert.equal(left.content.source_reference.url,mappedUnit.url);
assert(left.output_policy.preserve_exercise_names);assert(left.output_policy.preserve_source_reference);
assert(left.allow_new_narratives);assert.equal(right.requires_narrative_assignment,false);assert.equal(right.analysis_executed,false);
assert(!mappingReload.node('exercise-context-root').innerHTML.includes('id="exercise-add-mapping"'));
assert(!mappingReload.node('exercise-context-root#exercise-mapping-rows').innerHTML.includes('data-remove-mapping'));
// Legacy context has no mappings; loading must preserve its exact stored bytes and both existing fields.
const legacy={initialSituation:'Ankstesnė situacija',confirmedFacts:'Ankstesni faktai'},legacyRaw=JSON.stringify(legacy);
let legacyWrites=0;
const legacyPage=runtime({getItem:()=>legacyRaw,setItem(){legacyWrites++}});
assert.deepEqual(toPlain(legacyPage.window.SignalExerciseContext.get()),{...legacy,nameMappings:[]});
assert.equal(legacyWrites,0);assert.equal(legacyPage.node('exercise-context-root').innerHTML.includes('Ankstesnė situacija'),true);
assert.equal(legacyPage.node('exercise-context-root#exercise-mapping-rows').innerHTML.includes('Atitikmenų nėra'),true);
assert.throws(()=>legacyPage.window.SignalExerciseContext.save(initial),/jau išsaugotas/);
assert.equal(legacyWrites,0);
console.log('Context checks passed: save/reload, optional name mappings, stable IDs, empty/partial/duplicate/conflicting rows, legacy compatibility, original source/text preservation and shared analysis inputs.');

// Selected-period categories are whole assessed content units; audience size never rescales them.
const demo=noContext.window.SignalDemo, counts=noContext.window.SignalCounts;
for(const period of [10,7,3,1]){
 demo.state.period=period;
 for(const n of demo.narratives)assert.equal(demo.stanceCounts(n).reduce((a,b)=>a+b,0),demo.count(n));
}
demo.state.period=1;
const tiny={days:[0,0,0,0,0,0,1],stance:[50,50,0]};
assert.equal(demo.stanceCounts(tiny).reduce((a,b)=>a+b,0),1);
assert.deepEqual(toPlain(demo.stancePercentages(tiny)),[100,0,0]);
assert.deepEqual(toPlain(demo.stancePercentages({...tiny,days:[0,0,0,0,0,0,0]})),[null,null,null]);
const before=JSON.stringify(demo.stanceCounts(demo.narratives[0]));
const policy=JSON.parse(fs.readFileSync(path.join(root,'dist/metrics-context.json'))).growth_policy;
for(const size of [100,250,500]){
 noContext.window.SignalMetricsContext.apply({exercise_id:'A',audience:{exercise_id:'A',status:'known',count:size},growth_policy:policy});
 assert.equal(JSON.stringify(demo.stanceCounts(demo.narratives[0])),before);
}
noContext.window.SignalMetricsContext.apply({exercise_id:'B',audience:{exercise_id:'A',status:'known',count:250},growth_policy:policy});
assert.equal(noContext.window.SignalMetricsContext.get().audience.status,'missing');
assert(noContext.node('analysis-context-note').innerHTML.includes('Trūksta'));
noContext.window.SignalMetricsContext.apply({exercise_id:'A',audience:{exercise_id:'A',status:'known',count:0},growth_policy:policy});
assert.equal(noContext.window.SignalMetricsContext.get().audience.status,'zero');
assert(noContext.node('analysis-context-note').innerHTML.includes('tuščia'));
assert.throws(()=>noContext.window.SignalMetricsContext.apply({growth_policy:{...policy,minAudienceFraction:2}}));
assert.equal(demo.state.period,1);
console.log('Metrics UI checks passed: assessed-content denominators, missing/zero audiences and exercise isolation.');

// Context refreshes and period changes must preserve narrative selection and expansion.
Object.assign(demo.state,{view:'map',theme:'environment',selected:'N-002',expanded:'N-002',sort:'oldest'});
for(const period of [10,7,3,1]){
 demo.state.period=period;
 noContext.window.SignalMetricsContext.apply({exercise_id:'A',audience:{exercise_id:'A',status:'known',count:500},growth_policy:policy});
 assert.equal(demo.state.selected,'N-002');assert.equal(demo.state.expanded,'N-002');
 assert.equal(demo.state.sort,'oldest');assert.equal(demo.state.theme,'environment');
 assert(noContext.node('view').innerHTML.includes('id="narrative-content-N-002"'));
}
const savedDays=demo.narratives.map(n=>n.days);
try{
 demo.narratives.forEach(n=>n.days=[0,0,0,0,0,0,0]);
 for(const view of ['map','time','overview']){
  demo.state.view=view;demo.render();
  assert(!/NaN|Infinity|undefined/.test(noContext.node('view').innerHTML));
 }
}finally{demo.narratives.forEach((n,i)=>n.days=savedDays[i]);}
console.log('Selection, expansion, sorting and zero-volume rendering checks passed.');

const linked={id:'real-1',source:'pod',kind:'comment',is_demo:false,published_at:'2026-10-19T12:00:00Z',
 text:'Originalus šaltinio tekstas',sourceUrl:'https://pod.test/p/from-api#comment-from-api',parentSourceUrl:'https://pod.test/p/from-api'};
const rendered=demo.evidenceCard(linked,0);
assert(rendered.includes('href="'+linked.sourceUrl+'"'));assert(rendered.includes('Komentaro nuoroda'));
for(const input of [noContext.window.SignalDemo.prepareAnalysisInput(linked),noContext.window.SignalThermometer.prepareAnalysisInput(linked)]){
 assert.equal(input.content.sourceUrl,linked.sourceUrl);
 assert.equal(input.content.source_reference.sourceUrl,linked.sourceUrl);
 assert.equal(input.content.parentSourceUrl,linked.parentSourceUrl);
}
console.log('Narrative and shared analysis original-link checks passed.');

const pictured={...linked,media:[{kind:'image',thumbnailUrl:'https://pod.test/photo/small.jpg',originalUrl:'https://pod.test/photo/full.jpg',alt:'Prisegta nuotrauka'}]};
assert(demo.evidenceCard(pictured,0).includes('data-source-thumbnail'));
for(const input of [demo.prepareAnalysisInput(pictured),noContext.window.SignalThermometer.prepareAnalysisInput(pictured)]){
 assert.equal(input.content.media[0].thumbnailUrl,pictured.media[0].thumbnailUrl);
}
assert.equal(noContext.window.SignalSourceContent.thumbnail({...linked,parent_post:pictured}), '');
console.log('Narrative thumbnails and shared own-media analysis payload checks passed.');
