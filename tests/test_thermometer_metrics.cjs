const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const path=require('node:path'),root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'dist/thermometer.js'),'utf8');
const block=source.slice(source.indexOf('  function percent('),source.indexOf('  function applySavedReview('));
const percent=vm.runInNewContext(block+'\npercent;');
const pairs=[];
for(let total=0;total<=100;total++)for(let count=0;count<=total;count++)pairs.push([count,total]);
for(const total of [2000,10003])for(let count=0;count<=total;count+=137)pairs.push([count,total]);
pairs.push([1,16],[19,2000],[1,40]);
const expected=spawnSync('python3',['-c','import json,sys; print(json.dumps([round(n/d*100,1) if d else None for n,d in json.load(sys.stdin)]))'],
 {cwd:root,input:JSON.stringify(pairs),encoding:'utf8'});
assert.equal(expected.status,0,expected.stderr);
assert.deepEqual(pairs.map(([n,d])=>percent(n,d)),JSON.parse(expected.stdout));
console.log('Immediate thermometer percentages match Python, including floating-point ties and zero denominators: OK');
