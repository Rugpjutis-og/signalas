/* Headless QA. All API responses are synthetic; never contacts Neon/Diaspora/OpenAI. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const {chromium}=require('playwright');
(async()=>{
  const root=path.resolve(__dirname,'../..');
  const fixture=spawnSync('python3',['tests/narrative_preview_fixture.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'});
  assert.equal(fixture.status,0,fixture.stderr);
  let snapshot=JSON.parse(fixture.stdout);
  const metrics=JSON.parse(fs.readFileSync(path.join(root,'dist/metrics-context.json'),'utf8'));
  const server=http.createServer((req,res)=>{
    const pathname=new URL(req.url,'http://localhost').pathname;
    const filename=path.resolve(root,'dist','.'+(pathname==='/'?'/index.html':pathname));
    if(!filename.startsWith(path.join(root,'dist')+path.sep)){res.writeHead(404);res.end();return;}
    try{const body=fs.readFileSync(filename);res.setHeader('Content-Type',filename.endsWith('.js')?'application/javascript':filename.endsWith('.css')?'text/css':'text/html');res.end(body);}catch{res.writeHead(404);res.end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try{
    browser=await chromium.launch({headless:true,channel:process.env.SIGNALAS_QA_CHROME?'chrome':undefined,executablePath:process.env.SIGNALAS_QA_BROWSER});
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const origin='http://127.0.0.1:'+server.address().port;
    await page.route('**/*',async route=>{
      const url=new URL(route.request().url());
      if(url.origin!==origin)return route.abort();
      if(!url.pathname.startsWith('/api/'))return route.continue();
      let body;
      if(url.pathname==='/api/auth/session')body={authenticated:true,csrf:'synthetic-test'};
      else if(url.pathname==='/api/dashboard/context')body={context:null};
      else if(url.pathname==='/api/dashboard/bootstrap')body=snapshot;
      else if(url.pathname==='/api/metrics/context')body=metrics;
      else if(url.pathname==='/api/monitoring/status')body={state:'watching'};
      else throw Error('Unexpected test API '+url.pathname);
      return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
    });
    await page.goto(origin+'/#map');
    await page.locator('#theme').selectOption('security');
    await page.locator('#narrative-trigger-N001').waitFor();
    assert.equal(await page.locator('#theme option[value="all"]').count(),0);
    assert.equal(await page.locator('.graph-node').count(),2);
    await page.locator('#narrative-trigger-N001').click();
    assert.equal(await page.locator('#narrative-content-N001 .registry-variant').count(),2);
    assert((await page.locator('#narrative-content-N001').innerText()).includes('neaišku: 1'));
    assert.equal(await page.locator('#narrative-content-N001 a[target="_blank"]').count(),3);
    await page.selectOption('[data-narrative-sort]','newest');
    assert.equal(await page.locator('#narrative-trigger-N001').getAttribute('aria-expanded'),'true');
    // Registry is available to keyboard users and contains only selected fixed-topic types.
    const summary=page.locator('.registry-panel > details > summary');
    await summary.focus();await page.keyboard.press('Enter');
    assert.equal(await page.locator('.registry-type').count(),14);
    await page.locator('.registry-type > summary').first().click();
    assert((await page.locator('.registry-panel').innerText()).includes('Nepriskirti'));
    // Add a clearly visible testing label to screenshots only.
    await page.evaluate(()=>{const b=document.createElement('div');b.textContent='VIETINĖ PATIKRA · SINTETINIAI DUOMENYS';b.style='position:fixed;top:0;right:0;z-index:9999;background:#fff3c4;padding:8px 14px;font:12px sans-serif';document.body.append(b);});
    if(process.env.SIGNALAS_QA_SCREENSHOT)await page.screenshot({path:process.env.SIGNALAS_QA_SCREENSHOT,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'narrow page overflow');
    assert(await page.locator('#narrative-trigger-N001').isVisible());
    await page.locator('#theme').selectOption('identity');
    assert.equal(await page.locator('.registry-type').count(),4,'one candidate and three registry types');
    assert((await page.locator('#view').innerText()).includes('Auditorija nežinoma')===false,'candidate starts collapsed');
    await page.locator('.registry-type > summary').first().click();
    assert((await page.locator('#view').innerText()).includes('Auditorija nežinoma'));
    assert.equal(await page.locator('.graph-node').count(),0,'candidate not in confirmed graph');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'candidate narrow overflow');
    // Empty topic still has catalog without raw unassigned posts.
    await page.locator('#theme').selectOption('health');
    assert((await page.locator('#view').innerText()).includes('Patvirtintų tipų registras'));
    assert(!(await page.locator('#view').innerText()).includes('Turinys be naratyvo'));
    assert.equal(await page.evaluate(()=>localStorage.length),0);
    assert.deepEqual(errors,[]);
    console.log('Narrative browser checks passed: fixed topics, map, variants, unknown stance, source links, keyboard registry, separate candidate, empty topic, 1440/390px and no browser storage.');
  }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
