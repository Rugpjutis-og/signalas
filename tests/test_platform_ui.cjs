const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const read=name=>JSON.parse(fs.readFileSync(path.join(root,'dist/demo',name)));
const sources=['source-content.js','thermometer.js','platform-overview.js'].map(f=>fs.readFileSync(path.join(root,'dist',f),'utf8'));
function runtime(fetch){const context={window:{},URL,Intl,Date,fetch};vm.createContext(context);for(const code of sources)vm.runInContext(code,context);return context.window;}
function node(){const children=new Map();return {innerHTML:'',isConnected:true,attributes:{},setAttribute(k,v){this.attributes[k]=v},querySelector(key){if(!children.has(key))children.set(key,node());return children.get(key)},querySelectorAll(){return []}};}
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
