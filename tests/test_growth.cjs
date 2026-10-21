const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const handlers={};
const tip={hidden:true,textContent:'',style:{},getBoundingClientRect:()=>({width:320,height:90}),contains:target=>target===tip};
const policy=JSON.parse(fs.readFileSync(path.join(root,'dist/metrics-context.json'))).growth_policy;
let metrics={exercise_id:'A',audience:{exercise_id:'A',status:'known',count:250},growth_policy:policy};
const context={window:{SignalMetricsContext:{get:()=>metrics},innerHeight:844,addEventListener(){}},document:{documentElement:{clientWidth:375},getElementById:()=>tip,addEventListener(name,fn){handlers[name]=fn}}};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,'dist/growth.js'),'utf8'),context);
const g=context.window.SignalGrowth;
const fixture=(previous,current)=>({exercise_id:'A',days:[current],previousDays:[previous]});
assert.equal(g.compare(fixture(2,5),1).significant,true,'2 → 5: +3 and +150%');
assert.equal(g.compare(fixture(1,2),1).significant,false,'1 → 2: +100% but only +1');
assert.equal(g.compare(fixture(10,15),1).significant,true,'10 → 15: +5 and +50%');
assert.equal(g.compare(fixture(0,500),1).percent,null,'zero base');
assert.equal(g.badge(fixture(0,500),1),'');
assert.equal(g.compare({days:[200]},1).percent,null,'missing comparison');
assert.equal(g.compare({days:[200],previousDays:[null]},1).percent,null,'incomplete comparison');
assert.equal(g.compare(fixture(10,5),1).percent,-50,'decrease');
assert.equal(g.badge(fixture(10,5),1),'');
assert.equal(g.percentLabel(-25),'−25 %');assert.equal(g.percentLabel(null),'—');
assert.equal(g.compare(fixture(2,4),1).significant,false,'absolute increase is only 2');
assert.equal(g.compare(fixture(10,14),1).significant,false,'percentage is only 40');
assert.equal(g.compare(fixture(6,9),1).significant,true,'exact +3 and +50% boundary');
assert.equal(g.compare(fixture(101,151),1).significant,false,'rounding must not grant badge below 50%');
assert(g.explanation(fixture(2,5),1).includes('+150 % · nuo 2 iki 5 turinio vienetų'));
assert(g.explanation(fixture(2,5),1).includes('Demonstracinis'));
const series={days:[10,20,30,40,50,60,70],previousDays:[5,5,5,5,5,5,5]};
for(const [period,previous,current] of [[1,60,70],[3,90,180],[7,35,280]]){
 const c=g.compare(series,period);assert.equal(c.previous,previous);assert.equal(c.current,current);
 assert(Math.abs(c.percent-(current-previous)/previous*100)<1e-9);
}
const changing={exercise_id:'A',days:[100,100,100,100,100,100,150],previousDays:[90,90,90,90,90,90,90]};
assert.equal(g.compare(changing,1).significant,true);assert.equal(g.compare(changing,7).significant,false);
assert.notEqual(g.explanation(changing,1),g.explanation(changing,7));
assert.equal(g.aggregate([fixture(0,100)],1),null);
assert.equal(g.aggregate([fixture(100,150),fixture(100,100)],1),25);
assert.equal(g.aggregate([fixture(100,150),{days:[100]}],1),null);
const trigger={dataset:{growthExplanation:'Demonstracinis +50 %: 10 → 15'},attributes:{},setAttribute(key,value){this.attributes[key]=value},getBoundingClientRect:()=>({left:300,top:600,bottom:620}),contains:target=>target===trigger,closest:()=>trigger};
handlers.mouseover({target:trigger,relatedTarget:null});assert.equal(tip.hidden,false,'mouse hover opens');
handlers.mouseout({target:trigger,relatedTarget:null});assert.equal(tip.hidden,true,'mouse leave closes');
handlers.focusin({target:trigger});assert.equal(tip.hidden,false,'keyboard focus opens');
handlers.focusout({target:trigger});assert.equal(tip.hidden,true,'focus leave closes');
let propagationStopped=false;
handlers.click({target:trigger,stopImmediatePropagation(){propagationStopped=true}});
assert(propagationStopped,'badge click must not reach narrative accordion handler');
assert.equal(tip.hidden,false);assert.equal(trigger.attributes['aria-expanded'],'true');
handlers.mouseout({target:trigger,relatedTarget:null});assert.equal(tip.hidden,false,'clicked explanation stays open');
handlers.keydown({key:'Escape',preventDefault(){}});assert.equal(tip.hidden,true,'Escape closes');
assert(parseFloat(tip.style.left)+320<=375-12,'tooltip stays inside narrow viewport');
// Trial growth minimum adapts to actual assigned exercise membership.
for(const [audience,required] of [[100,3],[250,3],[500,5],[1000,10]]){
 metrics={exercise_id:'A',audience:{exercise_id:'A',status:'known',count:audience},growth_policy:policy};
 assert.equal(g.compare(fixture(2,5),1).requiredIncrease,required);
 assert.equal(g.compare(fixture(2,5),1).significant,required<=3);
 assert.equal(g.compare(fixture(10,15),1).significant,required<=5);
}
for(const audience of [{exercise_id:'A',status:'missing',count:null},{exercise_id:'A',status:'known',count:0},{exercise_id:'B',status:'known',count:100}]){
 metrics={exercise_id:'A',audience,growth_policy:policy};
 assert.equal(g.compare(fixture(2,5),1).significant,false);
 assert.equal(g.compare(fixture(2,5),1).percent,150,'count growth is independent of audience share');
 assert.equal(g.badge(fixture(2,5),1),'');
}
metrics={exercise_id:'B',audience:{exercise_id:'B',status:'known',count:100},growth_policy:policy};
assert.equal(g.compare(fixture(2,5),1).significant,false,'old exercise cannot use new membership');
assert.equal(g.compare({...fixture(2,5),exercise_id:'B'},1).significant,true);
metrics={exercise_id:'A',audience:{exercise_id:'A',status:'known',count:250},growth_policy:policy};
assert.equal(g.compare(fixture(2,5),1).significant,true,'switching back restores proper context');
console.log('Growth checks passed: audience scaling and exercise isolation; all three thresholds, small/zero/missing bases, declines, exact boundaries, equal immediately preceding periods and period changes.');
