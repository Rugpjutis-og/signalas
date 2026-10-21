const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const sandbox={window:{}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/counts.js'),'utf8'),sandbox);
const c=sandbox.window.SignalCounts;
for(const [value,expected] of [[0,1],[1,1],[2,2],[3,5],[5,5],[9,10],[11,20],[81,100],[101,200]])assert.equal(c.axisCeiling(value),expected);
for(const max of [1,2,5,10,20,50,100]){
 const ticks=Array.from(c.axisTicks(max));
 assert(ticks.every(Number.isInteger));assert.equal(new Set(ticks).size,ticks.length);
 assert.equal(ticks[0],0);assert.equal(ticks.at(-1),max);
}
for(const weights of [[50,50,0],[62,24,14],[1,1,1],[72,10,18]]){
 for(let total=0;total<=500;total++){
  const amounts=c.apportion(total,weights);
  assert.equal(amounts.reduce((a,b)=>a+b,0),total);
  assert(amounts.every(v=>Number.isInteger(v)&&v>=0));
  const shares=c.categoryShares(amounts);
  if(total)assert(Math.abs(shares.reduce((a,b)=>a+b,0)-100)<1e-10);
  else assert(shares.every(v=>v===null));
 }
}
assert.deepEqual(Array.from(c.apportion(1,[50,50,0])),[1,0,0]);
console.log('Count checks passed: adaptive axes, tiny/zero volumes, whole units and assessed-content proportions.');
