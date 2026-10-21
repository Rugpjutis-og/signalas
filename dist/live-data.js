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
    if(latest.collected_at!==data.collected_at||latest.start!==data.start||latest.end!==data.end){
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
    return data.units.filter(u=>inPeriod(u,state.period)&&(!unassigned||!u.narrative_id)&&
      (state.theme==='all'||(u.analysis?.theme_id||'unassigned')===state.theme)&&
      (state.themeScope!=='priority'||window.SignalDemo.themes.some(t=>t.id===u.analysis?.theme_id&&t.priority))&&
      (state.status==='all'||(state.status==='candidate'?Boolean(u.analysis?.candidate_title):Boolean(u.analysis?.narrative_id)))&&
      (!state.query||[u.text,u.author_name,u.analysis?.candidate_title].join(' ').toLocaleLowerCase('lt-LT').includes(state.query.toLocaleLowerCase('lt-LT'))));
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
    const content=state.tab==='evidence'?`<div class="evidence-grid">${selected.length?selected.map(window.SignalDemo.evidenceCard).join(''):'<p class="detail-description">Šiai dienai turinio nėra.</p>'}</div><p class="detail-caution">AI teksto analizės pasiūlymas. Pozicija vertinama turinio, o ne žmogaus lygiu. Medija neperžiūrėta.</p>`:
      state.tab==='relations'?'<p class="detail-description">Patikrintų šio naratyvo ryšių dar nėra.</p>':
      '<p class="detail-description">Šio tikro turinio bandymo apibrėžimo pakeitimų istorijos nėra. Demonstraciniai įvykiai nerodomi.</p>';
    const body=`<div class="detail-tabs" role="tablist" aria-label="Naratyvo informacija">${tabs.map(([key,label])=>`<button role="tab" id="narrative-tab-${n.id}-${key}" aria-selected="${state.tab===key}" aria-controls="narrative-tabpanel-${n.id}" tabindex="${state.tab===key?0:-1}" class="${state.tab===key?'active':''}" data-tab="${key}">${label}</button>`).join('')}</div><div class="detail-body" id="narrative-tabpanel-${n.id}" role="tabpanel" aria-labelledby="narrative-tab-${n.id}-${state.tab}">${content}</div>`;
    if(inline)return `<div class="narrative-expanded" id="narrative-content-${n.id}" role="region" aria-labelledby="narrative-title-${n.id}"><div class="inline-narrative-overview"><div class="inline-definition"><span>AI TEKSTO ANALIZĖS PASIŪLYMAS</span><p>${esc(n.description)}</p></div><button class="button" data-view="time">Tirti laiko eigą</button></div>${body}</div>`;
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
    return `<div class="time-layout"><div class="time-left"><section class="panel"><div class="panel-heading"><div><h2>Naratyvo dinamika</h2><p>Tikri gauti įrašai ir komentarai · pasirinkite dieną</p></div></div><div class="time-chart"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Gauto naratyvo turinio kiekis pagal dieną">${bars}</svg></div><p class="chart-note">Rodomas gautos imties turinio kiekis. Trūkstama istorija nelaikoma patvirtintu ankstesnio laikotarpio nuliu.</p></section><section class="panel"><div class="panel-heading"><h2>Pakeisti tiriamą naratyvą</h2>${ui.sortControl()}</div><div class="topic-list">${ui.sort(ns).filter(x=>x.id!==n.id).map(x=>`<button class="topic-row" data-narrative="${x.id}" style="grid-template-columns:1fr auto"><span class="topic-name">${esc(x.title)}</span><span class="topic-count">${ui.count(x)}</span></button>`).join('')||'<p class="detail-description">Kitų naratyvų šiame pjūvyje nėra.</p>'}</div></section></div>${detail(n,false,state,ui)}</div>`;
  }
  function decorate(){
    if(!active())return;
    document.body.classList.add('live-view');
    const full=data.collection_scope?.full_platform_export;
    const indicator=document.querySelector('.demo-indicator');indicator.innerHTML=`<span></span>Tikri duomenys · ${full?'administratoriaus eksportas':'nepilna aprėptis'}`;
    document.querySelector('.page-footer').innerHTML=`<span><span class="footer-dot"></span>Nuskaityta: ${source.date(data.collected_at)}</span><span>${full?'Aprėptis pagal administratoriaus eksporto laikotarpį':'Paskyrai prieinamas turinys · ne visa platforma'}</span>`;
    document.getElementById('local-status').title='Duomenys saugomi vietinėje SQLite bazėje. Rodoma tikra gauta imtis.';
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
  return Object.freeze({ready,active,get:()=>data,syncContext,setPeriod,range,refresh,image,units,note,empty,detail,time,decorate,periodControl,inPeriod,periodBounds});
})();
