const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const read=name=>JSON.parse(fs.readFileSync(path.join(root,'dist/demo',name)));
const sources=['source-content.js','thermometer.js','platform-overview.js'].map(f=>fs.readFileSync(path.join(root,'dist',f),'utf8'));
function runtime(fetch){const context={window:{},URL,Intl,Date,fetch,FormData:class {constructor(form){return Object.entries(form.values)}}};vm.createContext(context);for(const code of sources)vm.runInContext(code,context);return context.window;}
function node(){const children=new Map();return {innerHTML:'',isConnected:true,attributes:{},focus(){},scrollIntoView(){},setAttribute(k,v){this.attributes[k]=v},querySelector(key){if(!children.has(key))children.set(key,node());return children.get(key)},querySelectorAll(){return []}};}
(async()=>{
 const thermo=read('thermometer-7.json');
 thermo.units[0].is_demo=false;thermo.units[0].sourceUrl='https://pod.test/p/from-api';thermo.units[0].media=[{kind:'image',thumbnailUrl:'https://pod.test/photo/small.jpg',originalUrl:'https://pod.test/photo/full.jpg',alt:'Įrašo nuotrauka'}];
 const w=runtime(async()=>({ok:true,json:async()=>thermo})),c=w.SignalSourceContent;
 const real={id:'1',kind:'post',is_demo:false,sourceUrl:'https://pod.test/p/exact',text:'Originalus <script>tekstą</script> & turinys',published_at:'2026-10-19T12:00:00Z',author_name:'Vardas'};
 assert(c.link(real).includes('href="https://pod.test/p/exact"'));
 assert(c.link(real).includes('target="_blank"'));assert(c.link(real).includes('noopener noreferrer'));
 assert(!c.link({...real,is_demo:true}).includes('href='));
 assert(!c.link({...real,is_demo:1}).includes('href='));
 assert(!c.link({...real,sourceUrl:'javascript:alert(1)'}).includes('href='));
 assert(!c.link({...real,sourceUrl:'https://pod.test/'}).includes('href='));
 assert(c.link({...real,kind:'comment',sourceUrl:null,parentSourceUrl:real.sourceUrl}).includes('Atverti pirminį įrašą'));
 assert(c.link({...real,kind:'comment'}).includes('Komentaro nuoroda'));
 assert(c.link({id:'123',source:'https://pod.test'}).includes('Originalo nuoroda nepateikta'));
 const long='Ilgas originalus tekstas\n'.repeat(30);
 assert(c.text(long).includes('<details'));assert(c.text(long).includes(long));
 assert(!c.text(real.text).includes('<script>'));assert(c.text(real.text).includes('&lt;script&gt;'));
 assert(c.date(real.published_at).includes('15:00'),'timestamps use Lithuania, not host timezone');
 assert(c.media({is_demo:false,media:[{kind:'video',url:'https://pod.test/uploads/exact.mp4'}]}).includes('controls preload="none"'));
 const platform=node(),report=read('platform-7.json');w.SignalPlatformOverview.paint(platform,report);
 for(const label of ['Labiausiai diskutuojami','Daugiausia patiktukų','Daugiausia dalinamasi','Populiariausi įrašų autoriai','Demonstraciniai duomenys'])assert(platform.innerHTML.includes(label));
 assert.equal((platform.innerHTML.match(/class="platform-category-body"/g)||[]).length,3);
 assert(!platform.innerHTML.includes('už pasirinkto laikotarpio ribų gautas sąveikas'));
 assert(platform.innerHTML.includes('Balas nėra auditorijos procentas'));
 for(const label of ['80 %','15 %','5 %','/ 100 balų','Originalūs įrašai','Kaip skaičiuojama?'])assert(platform.innerHTML.includes(label));
 assert(!platform.innerHTML.includes('Tipinis vieno įrašo įsitraukimas'));
 assert(!platform.innerHTML.includes('undefined'));
 assert(platform.innerHTML.indexOf('platform-totals')<platform.innerHTML.indexOf('platform-categories'));
 assert(platform.innerHTML.includes('Iš viso įrašų'));assert(platform.innerHTML.includes('Iš viso komentarų'));
 const noTotals=structuredClone(report);delete noTotals.totals;w.SignalPlatformOverview.paint(platform,noTotals);
 assert(platform.innerHTML.includes('Duomenų nėra'));
 w.SignalPlatformOverview.paint(platform,report);
 assert(!platform.innerHTML.includes('href="https://diaspora.sauliai.lt/'));
 const missing=structuredClone(report);
 missing.categories.forEach(c=>{c.items=[];c.status='missing_data';c.missing_posts=1});
 missing.authors={...missing.authors,items:[],status:'missing_data'};
 w.SignalPlatformOverview.paint(platform,missing);
 assert(platform.innerHTML.includes('Autorių reitingui duomenų nepakanka'));
 assert(platform.innerHTML.includes('Šios kategorijos duomenų nepakanka'));
 missing.categories.forEach(c=>{c.status='empty';c.missing_posts=0});missing.authors.status='empty';
 w.SignalPlatformOverview.paint(platform,missing);
 assert(platform.innerHTML.includes('nėra įrašų su komentarais'));
 assert(platform.innerHTML.includes('nėra autorių, atitinkančių'));
 const liveCard=w.SignalPlatformOverview.postCard(real,'likes');
 assert(liveCard.includes(real.sourceUrl));assert(liveCard.includes('Duomenų nėra'));
 // Thermometer's real content and nested discussion use the same original-link renderer.
 const thermometer=node();await w.SignalThermometer.mount(thermometer,7);
 thermometer.onclick({target:{closest:selector=>selector==='#thermo-content-toggle'?{}:null}});
 assert(thermometer.querySelector('#thermo-evidence').innerHTML.includes('href="https://pod.test/p/from-api"'));
 assert(thermometer.querySelector('#thermo-evidence').innerHTML.includes('data-source-thumbnail'));
 assert(!thermometer.querySelector('#thermo-evidence').innerHTML.includes('data-thermo-review'));
 const liveThermo=structuredClone(thermo);liveThermo.mode='live';
 const liveWindow=runtime(async()=>({ok:true,json:async()=>liveThermo}));
 const liveRoot=node();await liveWindow.SignalThermometer.mount(liveRoot,7);
 liveRoot.onclick({target:{closest:selector=>selector==='#thermo-content-toggle'?{}:null}});
 const reviewMarkup=liveRoot.querySelector('#thermo-evidence').innerHTML;
 assert(reviewMarkup.includes('data-thermo-review'));
 assert(reviewMarkup.includes('Išsaugoti vertinimą'));
 assert(!reviewMarkup.includes('name="verified_claim_source"'));
 assert(!reviewMarkup.includes('name="evidence"'));
 assert(!reviewMarkup.includes('Turinio ištrauka arba peržiūrėtos medijos aprašymas'));
 assert(reviewMarkup.includes('Rankinis krypties patvirtinimas'));
 for(const category of ['stabilizing','neutral','destabilizing'])assert(reviewMarkup.includes(`value="${category}"`));
 assert(liveRoot.innerHTML.includes('Peržiūrėti ir priskirti kryptį'));
 const manualButton={dataset:{thermoCategory:'manual_review'},closest:()=>null};
 liveRoot.onclick({target:{closest:selector=>selector==='[data-thermo-category]'?manualButton:null}});
 const manualList=liveRoot.querySelector('#thermo-evidence');
 assert(manualList.innerHTML.includes('Laukia rankinio patvirtinimo'));
 assert(!manualList.innerHTML.includes('AI analizė šiam turiniui dar neatlikta.'));
 const openedList=manualList.innerHTML;
 liveWindow.SignalThermometer.invalidate();await liveWindow.SignalThermometer.refresh(liveRoot,7);
 assert.equal(manualList.innerHTML,openedList,'background refresh preserves the selected review filter');
 liveRoot.reviewEditing=true;
 liveRoot.querySelector('#thermo-evidence').innerHTML='draft remains';
 liveWindow.SignalThermometer.invalidate();await liveWindow.SignalThermometer.refresh(liveRoot,7);
 assert.equal(manualList.innerHTML,'draft remains','background refresh must not discard an edited review');

 // Saving one decision refetches the report immediately and confirms the persisted category.
 let shown=structuredClone(liveThermo),savedPayload=null;
 const savingWindow=runtime(async()=>({ok:true,json:async()=>shown}));
 savingWindow.SignalLiveData={saveThermometerReview:async payload=>{
   savedPayload=payload;
   shown=structuredClone(shown);
   const unit=shown.units.find(u=>u.assessment.status!=='assessed');
   unit.assessment={...unit.assessment,status:'assessed',category:payload.category,method:'manual_review'};
   shown.assessed+=1;shown.unassessed-=1;
 }};
 const savingRoot=node();await savingWindow.SignalThermometer.mount(savingRoot,7);
 const pendingUnit=shown.units.find(u=>u.assessment.status!=='assessed');
 const form=node();form.dataset={source:pendingUnit.source,id:pendingUnit.id};
 form.reportValidity=()=>true;form.values={category:'neutral',reason_code:'N1',reason:'Taiki nuomonė.'};
 await savingRoot.onsubmit({preventDefault(){},target:{closest:()=>form}});
 assert.equal(savedPayload.category,'neutral');
 assert(savingRoot.innerHTML.includes(`Aprėptis: ${shown.assessed} iš ${shown.total}`));
 assert(savingRoot.querySelector('[data-thermo-review-confirmation]').textContent.includes('įskaityta'));
 assert(savingRoot.querySelector('#thermo-evidence').innerHTML.includes('Kryptis patvirtinta rankiniu būdu'));
 // A failed save keeps the form available and does not show a successful classification.
 savingWindow.SignalLiveData.saveThermometerReview=async()=>{throw Error('Išsaugoti nepavyko');};
 const retryForm=node();retryForm.dataset=form.dataset;retryForm.values=form.values;retryForm.reportValidity=()=>true;
 await savingRoot.onsubmit({preventDefault(){},target:{closest:()=>retryForm}});
 assert.equal(retryForm.querySelector('[type=submit]').disabled,false);
 assert.equal(retryForm.querySelector('.thermo-review-error').textContent,'Išsaugoti nepavyko');

 // Only review-required and failed assessments allow a manual direction.
 for(const status of ['needs_review','error','waiting_data','not_analyzed','assessed']){
   const scoped=structuredClone(liveThermo);
   scoped.units.forEach(unit=>{unit.assessment.status=status;});
   const scopedWindow=runtime(async()=>({ok:true,json:async()=>scoped}));
   const scopedRoot=node();await scopedWindow.SignalThermometer.mount(scopedRoot,7);
   scopedRoot.onclick({target:{closest:selector=>selector==='#thermo-content-toggle'?{}:null}});
   assert.equal(scopedRoot.querySelector('#thermo-evidence').innerHTML.includes('data-thermo-review'),
     ['needs_review','error'].includes(status),status);
 }
 const notAnalyzed=structuredClone(liveThermo);
 notAnalyzed.units.forEach(unit=>{unit.assessment.status='not_analyzed';});
 const pendingWindow=runtime(async()=>({ok:true,json:async()=>notAnalyzed}));
 const pendingRoot=node();await pendingWindow.SignalThermometer.mount(pendingRoot,7);
 pendingRoot.onclick({target:{closest:selector=>selector==='#thermo-content-toggle'?{}:null}});
 assert(!pendingRoot.querySelector('#thermo-evidence').innerHTML.includes('data-thermo-review'));
 // Out-of-order period responses cannot replace the latest period's report.
 const pending=new Map();
 const racing=runtime(url=>new Promise(resolve=>pending.set(url,resolve)));
 const raceRoot=node(),one=racing.SignalPlatformOverview.mount(raceRoot,1),three=racing.SignalPlatformOverview.mount(raceRoot,3);
 pending.get('/api/platform/overview?period=3')({ok:true,json:async()=>read('platform-3.json')});await three;
 const latest=raceRoot.innerHTML;
 pending.get('/api/platform/overview?period=1')({ok:true,json:async()=>read('platform-1.json')});await one;
 assert.equal(raceRoot.innerHTML,latest);assert(latest.includes('3 d.'));
 // Equal-duration ranges must not share a cache entry. Both modules receive the exact same date query.
 const dateCalls=[],dated=runtime(async url=>{
   dateCalls.push(url);
   const report=structuredClone(url.includes('thermometer')?read('thermometer-3.json'):read('platform-3.json'));
   report.mode='live';
   if(url.includes('platform'))report.posts=[];
   return {ok:true,json:async()=>report};
 });
 dated.SignalLiveData={active:()=>true};
 const firstRange={period:3,key:'2026-10-01/2026-10-03',query:'start_date=2026-10-01&end_date=2026-10-03'},
       nextRange={period:3,key:'2026-10-04/2026-10-06',query:'start_date=2026-10-04&end_date=2026-10-06'};
 // Rendering the fixture as live needs the source-post collection, independent of its categories.
 const dateRoot=node();
 await dated.SignalThermometer.mount(dateRoot,firstRange);
 await dated.SignalThermometer.mount(dateRoot,nextRange);
 await dated.SignalThermometer.mount(dateRoot,nextRange);
 await dated.SignalPlatformOverview.mount(dateRoot,firstRange);
 await dated.SignalPlatformOverview.mount(dateRoot,nextRange);
 await dated.SignalPlatformOverview.mount(dateRoot,nextRange);
 assert.equal(dateCalls.filter(url=>url.startsWith('/api/thermometer')).length,2);
 assert.equal(dateCalls.filter(url=>url.startsWith('/api/platform')).length,2);
 assert(!dateRoot.innerHTML.includes('Bandyti dar kartą'));
 assert(dateCalls.includes('/api/thermometer?'+nextRange.query));
 assert(dateCalls.includes('/api/platform/overview?'+nextRange.query));
 console.log('Platform UI checks passed: categories, full text, original URLs, Lithuanian time, empty/missing states, thermometer links and period races.');
})().catch(error=>{console.error(error);process.exitCode=1});
