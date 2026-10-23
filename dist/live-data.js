"use strict";
window.SignalLiveData=(()=>{
  const source=window.SignalSourceContent,esc=source.escape;
  let data=null,token=null,selectionRevision=0;
  const dateKey=value=>new Date(value).toLocaleDateString('sv-SE',{timeZone:'Europe/Vilnius'});
  const active=()=>data?.mode==='live';
  async function image(source,id,index){
    await ready;
    if(!active())throw Error('Tikro turinio režimas neįjungtas.');
    const query=new URLSearchParams({source,id,index:String(index)});
    const request=()=>fetch('/api/media/image?'+query,{headers:{'X-Signalas-CSRF':token},cache:'no-store'});
    let response=await request();
    // An open tab may outlive a local server restart. Refresh its in-memory
    // request token once, without changing content, filters or saved context.
    if(response.status===403){
      const bootstrap=await fetch('/api/dashboard/bootstrap',{cache:'no-store'});
      if(bootstrap.ok){const latest=await bootstrap.json();if(latest.mode==='live'&&typeof latest.csrf==='string'){token=latest.csrf;response=await request();}}
    }
    if(!response.ok)throw Error('Nuotraukos įkelti nepavyko.');
    if(!/^image\/(webp|png|jpeg|gif)$/.test(response.headers.get('Content-Type')||''))throw Error('Netinkamas nuotraukos tipas.');
    return response.blob();
  }
  const accountDescription=()=>data?.collection_scope?.account_scope?'Paskyrai matomas srautas ir tavo profilio įrašai; dublikatai sujungti.':'Paskyrai prieinama turinio imtis.';
  async function refresh(){
    if(!active())return;
    const revision=selectionRevision;
    const response=await fetch('/api/dashboard/bootstrap',{cache:'no-store'});
    if(!response.ok)throw Error('Duomenų atnaujinti nepavyko. Rodoma paskutinė sėkmingai gauta imtis.');
    const latest=await response.json();
    if(latest.mode!=='live'||revision!==selectionRevision)return;
    token=latest.csrf;
    if(latest.collected_at!==data.collected_at||latest.start!==data.start||latest.end!==data.end||latest.analysis_revision!==data.analysis_revision){
      data=latest;window.SignalDemo?.refreshLive(data,{preserveDay:true});
    }
  }
  function periodBounds(period){return {start:data.days[data.days.length-period],end:dateKey(new Date(Date.parse(data.end)-1))};}
  function range(){
    const {start,end}=periodBounds(data.days.length);
    return {start_date:start,end_date:end,period:data.days.length,key:start+'/'+end,
      query:new URLSearchParams({start_date:start,end_date:end}).toString()};
  }
  function inPeriod(unit,period){const day=dateKey(unit.published_at),range=periodBounds(period);return day>=range.start&&day<=range.end;}
  async function syncContext(){
    if(!active())return data;
    const response=await fetch('/api/dashboard/bootstrap',{cache:'no-store'});
    if(!response.ok)throw Error('Konteksto būsenos įkelti nepavyko.');
    data=await response.json();token=data.csrf;return data;
  }
  async function setPeriod(start,end){
    ++selectionRevision;
    const request=()=>fetch('/api/dashboard/period',{method:'POST',headers:{'Content-Type':'application/json','X-Signalas-CSRF':token},
      body:JSON.stringify({start_date:start,end_date:end})});
    let response=await request();
    if(response.status===403){
      const bootstrap=await fetch('/api/dashboard/bootstrap',{cache:'no-store'});
      if(bootstrap.ok){const latest=await bootstrap.json();token=latest.csrf;response=await request();}
    }
    if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.error||'Nepavyko išsaugoti pasirinkto laikotarpio.');}
    data=await response.json();return data;
  }
  async function initialize(){
    await window.SignalSession?.ready;
    await window.SignalExerciseContext?.ready;
    const response=await fetch('/api/dashboard/bootstrap',{cache:'no-store'});
    if(!response.ok)throw Error('Nepavyko patikrinti pasirinkto duomenų šaltinio. Demonstraciniai duomenys neįjungiami automatiškai.');
    data=await response.json();token=data.csrf;
    if(active())await syncContext();
    return data;
  }
  const ready=initialize();
  function units(state,{unassigned=false}={}){
    const types=new Map((data.registry?.types||[]).map(t=>[t.id,t]));
    const topics=new Map((data.registry?.topics||[]).map(t=>[t.id,t.app_id]));
    return data.units.filter(u=>{
      const matched=u.narrative_analysis?.matches||[];
      const selected=matched.filter(m=>state.theme==='all'||topics.get(types.get(m.type_id)?.topic_id)===state.theme);
      return inPeriod(u,state.period)&&(!unassigned||!matched.length)&&
        (state.theme==='all'||selected.length>0)&&
        (state.themeScope!=='priority'||selected.some(m=>window.SignalDemo.themes.some(t=>t.id===topics.get(types.get(m.type_id)?.topic_id)&&t.priority)))&&
        (state.status==='all'||(state.status==='confirmed'&&selected.length>0))&&
        (!state.query||[u.text,u.author_name,...matched.map(m=>types.get(m.type_id)?.title)].join(' ').toLocaleLowerCase('lt-LT').includes(state.query.toLocaleLowerCase('lt-LT')));
    });
  }
  function stanceCoverage(n){
    const c=n.stance_coverage;
    return c?`<span class="narrative-coverage">Pozicija nustatyta ${c.known}/${c.known+c.unknown} · neaišku: ${c.unknown}</span>`:'';
  }
  function criteria(t){
    return `<dl class="registry-criteria"><dt>Teiginio branduolys</dt><dd>${esc(t.claim_template||t.description)}</dd><dt>Priskirti</dt><dd>${esc(t.include_when)}</dd><dt>Nepriskirti</dt><dd>${esc(t.exclude_when)}</dd>${t.broader_type?`<dt>Bendresnis tipas</dt><dd>${esc(t.broader_type)} · bendras kiekis su konkretesniais tipais: ${data.type_rollups?.[t.broader_type]??0} unikalių vienetų</dd>`:''}</dl>`;
  }
  function registryPanel(state){
    if(!data.registry)return '';
    const topics=new Map(data.registry.topics.map(t=>[t.id,t]));
    const types=data.registry.types.filter(t=>(state.theme==='all'||topics.get(t.topic_id)?.app_id===state.theme)&&(!state.query||[t.id,t.title,t.claim_template].join(' ').toLocaleLowerCase('lt-LT').includes(state.query.toLocaleLowerCase('lt-LT'))));
    return `<section class="panel registry-panel"><details><summary>Patvirtintų tipų registras <span class="compact-count">${types.length}</span></summary><p class="detail-description">Tema → naratyvo tipas → pratybų atmaina → įrašai ir komentarai. Registras apibrėžia teiginius, o ne patvirtintus faktus.</p>${types.map(t=>`<details class="registry-type"><summary>${esc(t.id)} · ${esc(t.title)}</summary><p class="detail-description">${esc(topics.get(t.topic_id)?.name)}</p>${criteria(t)}</details>`).join('')||'<p>Šiai temai tipų dar nėra.</p>'}</details>${data.requires_reanalysis_count?`<p class="detail-description">${data.requires_reanalysis_count} ankstesnių vertinimų reikia pakartotinai patikrinti pagal šį registrą.</p>`:''}</section>`;
  }
  function candidatePanel(state){
    if(state.status==='confirmed')return '';
    const topics=new Map((data.registry?.topics||[]).map(t=>[t.id,t]));
    const rows=(data.candidates||[]).filter(c=>(state.theme==='all'||topics.get(c.topic_id)?.app_id===state.theme)&&(!state.query||[c.title,c.claim_template].join(' ').toLocaleLowerCase('lt-LT').includes(state.query.toLocaleLowerCase('lt-LT'))));
    if(!rows.length)return state.status==='candidate'?'<section class="panel empty-state"><h2>Naujų kandidatų nėra</h2><p>Vienas nepriskirtas įrašas savaime nėra naujo tipo kandidatas.</p></section>':'';
    return `<section class="panel registry-panel"><h2>Nauji kandidatai <span class="compact-count">${rows.length}</span></h2><p class="detail-description">Laukia administratoriaus sprendimo. Į patvirtintą žemėlapį dar neįtraukti.</p>${rows.map(c=>`<details class="registry-type"><summary><span class="tag candidate">Naujas kandidatas</span> ${esc(c.title)}</summary><p>${esc(c.claim_template)}</p><p>${esc(topics.get(c.topic_id)?.name)} · ${c.unit_count} savarankiški vienetai · ${c.author_count} autoriai · ${c.thread_count} gijos</p><p class="detail-description">${c.audience===null?'Auditorija nežinoma':`Auditorija: ${c.audience}`} · reikia bent ${c.required_authors} autorių. Bandomieji kriterijai, ne statistinis reikšmingumas.</p><p class="detail-description">Langas: ${source.date(c.window_start)} – ${source.date(c.window_end)}. Pirmas: ${source.date(c.first_seen)} · paskutinis: ${source.date(c.last_seen)}</p><p>Skirtumas nuo ${esc(c.nearest_type_ids.join(', '))}: ${esc(c.novelty_reason)}</p><div class="evidence-grid">${c.evidence.slice(0,3).map(window.SignalDemo.evidenceCard).join('')}</div><p class="detail-description">${esc(c.id)}${c.exercise_known?'':' · pratybų ID nepateiktas'}</p></details>`).join('')}</section>`;
  }
  function note(){
    return `<p><strong>Tikri „Diasporos“ duomenys · ${data.collection_scope?.full_platform_export?'administratoriaus eksportas':'nepilna platformos aprėptis'}.</strong> Nuskaityta ${source.date(data.collected_at)}.
      ${data.collection_scope?.full_platform_export?'Naudojamas administratoriaus pateiktas platformos eksportas; jo datos nekeičiamos pagal pasirinktą laikotarpį.':accountDescription()+' Tai nėra visa platforma.'}
      AI tekstu išanalizuota ${data.analysis_count} iš ${data.units.length} gautų vienetų.
      ${data.context_available?'Naudojamas tas pats išsaugotas pradinis pratybų kontekstas.':'Pradinis pratybų kontekstas nepateiktas; termometro vertinimai paliekami peržiūrai.'}
      Pratybų narių ir matomumo auditorijos duomenų trūksta; autorių reitingas ir augimo ženkliukai nevertinami.
      Nuotraukų ir vaizdo turinys automatiškai neanalizuotas.</p>`;
  }
  function empty(){
    return `<section class="panel empty-state"><h2>Šiame pjūvyje naratyvų dar nėra</h2><p>Tikras turinys gali likti be naratyvo arba laukti analizės. Demonstraciniai naratyvai nerodomi.</p><button class="button" data-view="platform">Atverti platformos apžvalgą</button></section>`;
  }
  function evidence(n,state){return n.evidence.filter(u=>inPeriod(u,state.period)&&(!state.day||dateKey(u.published_at)===state.day));}
  function detail(n,inline,state,ui){
    if(!n)return '';
    const selected=evidence(n,state),t=ui.themeOf(n.theme),tabs=[['evidence','Reprezentatyvūs įrašai'],['relations','Ryšiai'],['history','Istorija']];
    const groups=(n.variants||[]).map(v=>({...v,evidence:v.evidence.filter(u=>selected.some(s=>s.source===u.source&&s.id===u.id))})).filter(v=>v.evidence.length);
    const labels={subject:'Subjektas',object:'Objektas',place:'Vieta',event:'Įvykis',time:'Laikas'};
    const content=state.tab==='evidence'?`${stanceCoverage(n)}${groups.map(v=>`<details class="registry-variant" open><summary>${esc(Object.entries(v.entities).filter(([,value])=>value).map(([k,value])=>labels[k]+': '+value).join(' · ')||'Atmaina be patikslintų parametrų')} <span class="compact-count">${v.evidence.length}</span></summary><div class="evidence-grid">${v.evidence.map(u=>`<div><blockquote class="narrative-excerpt">${esc(u.narrative_evidence)}</blockquote>${window.SignalDemo.evidenceCard(u)}</div>`).join('')}</div></details>`).join('')||'<p class="detail-description">Šiai dienai turinio nėra.</p>'}<p class="detail-caution">Pozicija vertinama teiginio, ne žmogaus lygiu. Ši analizė apima tekstą; medija neperžiūrėta.</p>`:
      state.tab==='relations'?`${criteria(n)}${(data.registry?.types||[]).filter(t=>t.broader_type===n.id).map(t=>`<p>Konkretesnis tipas: ${esc(t.id)} · ${esc(t.title)}</p>`).join('')}<p class="detail-description">Registro hierarchija neįrodo koordinavimo. Patikrintų ryšių tarp šaltinio įrašų nėra.</p>`:
      `<p class="detail-description">Registro versija: ${esc(n.registry_version)}. Senieji N-… priskyrimai automatiškai neperkelti. Tipo patvirtinimas nepatvirtina jo teiginio teisingumo.</p>`;
    const body=`<div class="detail-tabs" role="tablist" aria-label="Naratyvo informacija">${tabs.map(([key,label])=>`<button role="tab" id="narrative-tab-${n.id}-${key}" aria-selected="${state.tab===key}" aria-controls="narrative-tabpanel-${n.id}" tabindex="${state.tab===key?0:-1}" class="${state.tab===key?'active':''}" data-tab="${key}">${label}</button>`).join('')}</div><div class="detail-body" id="narrative-tabpanel-${n.id}" role="tabpanel" aria-labelledby="narrative-tab-${n.id}-${state.tab}">${content}</div>`;
    if(inline)return `<div class="narrative-expanded" id="narrative-content-${n.id}" role="region" aria-labelledby="narrative-title-${n.id}"><div class="inline-narrative-overview"><div class="inline-definition"><span>PATVIRTINTAS TIPAS · AI PRISKYRIMAI</span><p>${esc(n.description)}</p></div><button class="button" data-view="time">Tirti laiko eigą</button></div>${body}</div>`;
    return `<aside class="panel detail-panel"><div class="detail-top"><div class="detail-theme"><span class="theme-dot" style="background:${t.color}"></span>${esc(t.name)}</div><h2 class="detail-title">${esc(n.title)}</h2>${ui.statusTag(n)}<p class="detail-description">${esc(n.description)}</p></div>${body}</aside>`;
  }
  function time(n,ns,state,ui){
    if(!n)return empty(state);
    const days=data.days.slice(-state.period),counts=n.days.slice(-state.period),maximum=window.SignalCounts.axisCeiling(Math.max(...counts));
    const width=660,height=245,left=42,bottom=205,step=600/days.length;
    const bars=days.map((day,i)=>{
      const x=left+i*step+step*.2,h=counts[i]/maximum*160;
      return `<g class="chart-day ${state.day===day?'selected':''}" data-day="${day}" role="button" tabindex="0" aria-label="${day}: ${counts[i]} turinio vienetų"><rect x="${x}" y="${bottom-h}" width="${step*.6}" height="${Math.max(h,1)}" fill="#7e8ee4"/><text x="${x+step*.3}" y="${bottom-h-8}" text-anchor="middle">${counts[i]}</text><text class="axis-label" x="${x+step*.3}" y="${bottom+23}" text-anchor="middle">${day.slice(5)}</text></g>`;
    }).join('');
    return `<div class="time-layout"><div class="time-left"><section class="panel"><div class="panel-heading"><div><h2>Naratyvo dinamika</h2><p>Tikri gauti įrašai ir komentarai · pasirinkite dieną</p></div></div><div class="time-chart"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Gauto naratyvo turinio kiekis pagal dieną">${bars}</svg></div><p class="chart-note">Rodomas gautos imties turinio kiekis. Trūkstama istorija nelaikoma patvirtintu ankstesnio laikotarpio nuliu.</p></section><section class="panel"><div class="panel-heading"><h2>Pakeisti tiriamą naratyvą</h2>${ui.sortControl()}</div><div class="topic-list">${ui.sort(ns).filter(x=>x.id!==n.id).map(x=>`<button class="topic-row" data-narrative="${x.id}" style="grid-template-columns:1fr auto"><span class="topic-name">${esc(x.title)}</span><span class="topic-count">${ui.count(x)}</span></button>`).join('')||'<p class="detail-description">Kitų naratyvų šiame pjūvyje nėra.</p>'}</div></section></div></div>`;
  }
  function decorate(){
    if(!active())return;
    document.body.classList.add('live-view');
    const full=data.collection_scope?.full_platform_export;
    const indicator=document.querySelector('.demo-indicator');indicator.innerHTML=`<span></span>Tikri duomenys · ${full?'administratoriaus eksportas':'nepilna aprėptis'}`;
    document.querySelector('.page-footer').innerHTML=`<span><span class="footer-dot"></span>Nuskaityta: ${source.date(data.collected_at)}</span><span>${full?'Aprėptis pagal administratoriaus eksporto laikotarpį':'Paskyrai prieinamas turinys · ne visa platforma'}</span>`;
    document.getElementById('local-status').title='Duomenys saugomi privačioje Neon bazėje. Rodoma gauta imtis.';
    const help=document.querySelector('#help-dialog .help-note');
    help.textContent='Rodomi tikri gauti duomenys. Asmeninis srautas nėra visa platforma. Naratyvai ir ryšiai nepapildomi demonstraciniais pavyzdžiais. Be auditorijos duomenų narių procentai neskaičiuojami.';
    document.querySelectorAll('#help-dialog p').forEach(p=>{
      if(p.textContent.includes('demonstracin')||p.textContent.includes('AI analizė dar neprijungta'))p.textContent='Tikro turinio bandymas: datos ir kiekiai imami iš gauto šaltinio, AI teksto pasiūlymai pažymėti, o trūkstami vertinimai palikti peržiūrai. Fiksuotas temų katalogas ir išsaugotas pradinis kontekstas išlieka.';
    });
  }
  function periodControl(){
    const button=document.getElementById('period-picker'),dialog=document.getElementById('period-dialog');
    const start=document.getElementById('period-from'),end=document.getElementById('period-to');
    const error=document.getElementById('period-error'),submit=document.getElementById('period-apply');
    const selected=range();button.hidden=false;
    document.getElementById('period').closest('.select-wrap').style.display='none';
    button.querySelector('span').textContent=`Laikotarpis: ${selected.start_date} – ${selected.end_date}`;
    if(button.dataset.ready)return;
    button.dataset.ready='true';
    button.onclick=()=>{const selected=range();start.value=selected.start_date;end.value=selected.end_date;error.textContent='';dialog.showModal();};
    document.getElementById('period-cancel').onclick=()=>dialog.close();
    document.getElementById('period-form').onsubmit=async event=>{
      event.preventDefault();if(submit.disabled)return;error.textContent='';
      if(!start.value||!end.value||start.value>end.value){error.textContent='Pasirinkite abi datas. Data „Nuo“ negali būti vėlesnė už datą „Iki“.';return;}
      submit.disabled=true;
      try{const latest=await setPeriod(start.value,end.value);dialog.close();window.SignalDemo.refreshLive(latest);}
      catch(problem){error.textContent=problem.message;}
      finally{submit.disabled=false;}
    };
  }
  // This reads the database snapshot; collection only runs on a button click.
  // No source login or paid AI analysis is triggered by these reads.
  let refreshing=false;
  async function checkSnapshot(){
    if(refreshing||document.visibilityState==='hidden')return;
    refreshing=true;try{await ready;await refresh();}catch(_){}finally{refreshing=false;}
  }
  setInterval(checkSnapshot,60000);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')checkSnapshot();});
  return Object.freeze({ready,active,get:()=>data,syncContext,setPeriod,range,refresh,image,units,note,empty,detail,time,decorate,registryPanel,candidatePanel,stanceCoverage,periodControl,inPeriod,periodBounds});
})();
