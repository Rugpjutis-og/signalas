"use strict";
// Presentation only. Acquisition, authored classifications and statistics live in Python.
window.SignalThermometer = (() => {
  const labels = {stabilizing:'Stabilizuojantis turinys',neutral:'Neutralus arba nesusijęs turinys',destabilizing:'Destabilizuojantis turinys'};
  const pendingLabels={waiting_data:'Laukiama duomenų',needs_review:'Reikia peržiūros',error:'Vertinimo klaida',not_analyzed:'Dar neanalizuota'};
  const colors = {stabilizing:'#4bd600',neutral:'#c3c1d2',destabilizing:'#ff2f62'};
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct = value => value === null ? '—' : value.toLocaleString('lt-LT',{maximumFractionDigits:1})+' %';
  const date = value => new Intl.DateTimeFormat('lt-LT',{timeZone:'Europe/Vilnius',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
  let generation=0, active='all', expanded=false, current=null, currentPeriod=null;
  const reasonCodes={neutral:[['N0','Kasdienis arba nesusijęs turinys'],['N1','Taiki nuomonė ar kritika'],['N2','Krypties požymių nepakanka']],stabilizing:[['S1','Patikimais duomenimis pagrįstas paaiškinimas'],['S2','Praktiška ir patikima pagalba'],['S3','Įtampos mažinimas'],['S4','Teisės ir solidarumas']],destabilizing:[['D1','Patvirtintai klaidingas žalingas teiginys'],['D2','Smurto, diskriminacijos ir neapykantos kurstymas'],['D3','Kolektyvinis kaltinimas'],['D4','Saugumo ar dalyvavimo griovimas, visuotinis apleistumas ar bejėgiškumas']]};
  const cache=new Map();
  const partLabel=part=>({text:'įrašo tekstas',conversation_context:'ankstesnė diskusija','image-1:illustration':'paveikslėlio iliustracija','image-1:ocr_text':'paveikslėlio tekstas','clip-1:transcript:10-18s':'transkripcija 10–18 s','clip-1:subtitles:10-18s':'subtitrai 10–18 s','clip-1:frames:10s,18s':'atrinkti kadrai: 10 ir 18 s'}[part]||part);
  async function acquire(period) {
    const key=period.key||period,query=period.query||`period=${period}`;
    if(cache.has(key)) return cache.get(key);
    let response;
    try {
      response=await fetch(`/api/thermometer?${query}`,{cache:'no-store'});
      if(!response.ok) throw Error('API unavailable');
      const report=await response.json();
      if(!['demo','live'].includes(report.mode)||!Array.isArray(report.units)) throw Error('Unexpected response');
      cache.set(key,report);return report;
    } catch (_) {
      if(window.SignalLiveData?.active())throw Error('Tikro turinio duomenų įkelti nepavyko. Demonstraciniai pavyzdžiai nerodomi.');
      response=await fetch(`demo/thermometer-${period}.json?v=1`,{cache:'no-store'});
      if(!response.ok) throw Error('Nepavyko įkelti demonstracinių duomenų.');
      const report=await response.json();
      if(report.mode!=='demo'||!Array.isArray(report.units)) throw Error('Netinkamas demonstracinių duomenų formatas.');
      cache.set(key,report);return report;
    }
  }
  function chart(report) {
    const height=242, top=24, bottom=180, left=50, width=760;
    const cell=(width-left-20)/report.days.length;
    const grid=[0,50,100].map(v=>{const y=bottom-(bottom-top)*v/100;return `<line x1="${left}" y1="${y}" x2="${width-15}" y2="${y}" stroke="#e6eaf0"/><text x="${left-9}" y="${y+4}" text-anchor="end">${v}%</text>`;}).join('');
    const bars=report.days.map((day,i)=>{
      const x=left+i*cell+cell*.23,w=cell*.54;
      let y=bottom;
      const segments=day.assessed?day.categories.map(c=>{
        const h=c.count/day.assessed*(bottom-top);y-=h;
        return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${colors[c.id]}"><title>${escape(day.date)} · ${escape(c.label)}: ${c.count} (${pct(c.percent)})</title></rect>`;
      }).join(''):`<rect x="${x}" y="${top}" width="${w}" height="${bottom-top}" fill="url(#thermo-gap)" stroke="#d8dfe9" stroke-dasharray="3 4"/><text x="${x+w/2}" y="${top+78}" text-anchor="middle">—</text>`;
      return segments+`<text x="${x+w/2}" y="${bottom+20}" text-anchor="middle">${escape(day.date.slice(5))}</text><text x="${x+w/2}" y="${bottom+38}" text-anchor="middle">${day.assessed}/${day.total}</text>`;
    }).join('');
    const table=`<table class="thermo-sr"><caption>Dienos kategorijų proporcijos ir įvertinimo aprėptis</caption><thead><tr><th>Diena</th><th>Įvertinta iš visų</th>${Object.values(labels).map(s=>`<th>${s}</th>`).join('')}</tr></thead><tbody>${report.days.map(d=>`<tr><th>${d.date}</th><td>${d.assessed} iš ${d.total}</td>${d.categories.map(c=>`<td>${c.count}; ${d.assessed?pct(c.percent):'Nėra įvertintų duomenų'}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    return `<div class="thermo-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Kategorijų proporcijų raida laike. Kiekvienas stulpelis rodo vienos dienos įvertintus vienetus. Brūkšniuoti stulpeliai – nėra įvertintų duomenų."><defs><pattern id="thermo-gap" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 8L8 0" stroke="#e6eaf0"/></pattern></defs>${grid}${bars}</svg></div>${table}`;
  }
  function discussionMarkup(unit,report){
    if(report.mode==='live'&&report.context_records&&unit.kind==='comment'&&unit.parent_id){
      return `<details class="thermo-context" data-discussion-source="${escape(unit.source)}" data-discussion-id="${escape(unit.id)}"><summary>Diskusijos kontekstas</summary><div data-discussion-body></div></details>`;
    }
    return (unit.conversation_context||[]).length?`<div class="thermo-note">Diskusijos kontekstas:${unit.conversation_context.map(c=>`<div>${window.SignalSourceContent.body({...c,is_demo:unit.is_demo})}${window.SignalSourceContent.link({...c,kind:'comment',is_demo:unit.is_demo,parentSourceUrl:c.parentSourceUrl||unit.parentSourceUrl||unit.sourceUrl})}</div>`).join('')}</div>`:'';
  }
  function bindDiscussions(root,report){
    root.querySelectorAll('[data-discussion-id]').forEach(details=>details.addEventListener('toggle',()=>{
      if(!details.open||details.dataset.loaded)return;
      const pool=report.context_records||[],source=details.dataset.discussionSource,id=details.dataset.discussionId;
      const unit=pool.find(u=>u.source===source&&u.id===id);if(!unit)return;
      const parent=pool.find(u=>u.source===source&&u.id===unit.parent_id);
      const thread=pool.filter(u=>u.source===source&&u.kind==='comment'&&u.parent_id===unit.parent_id)
        .sort((a,b)=>Date.parse(a.published_at)-Date.parse(b.published_at));
      const preceding=thread.slice(0,Math.max(0,thread.findIndex(u=>u.id===id)));
      const items=[...(parent?[parent]:[]),...preceding];
      details.querySelector('[data-discussion-body]').innerHTML=items.map(c=>`<div>${window.SignalSourceContent.body(c)}${window.SignalSourceContent.link(c)}</div>`).join('')||'<p>Ankstesnių komentarų nėra.</p>';
      details.dataset.loaded='true';
    }));
  }
  function evidenceCard(unit, report) {
    const a=unit.assessment, context=report.contexts.find(c=>c.version===a.context_version);
    const kind={post:'Įrašas',comment:'Komentaras',message:'Žinutė'}[unit.kind]||'Turinio vienetas';
    const evidence=a.evidence.map(e=>`<p class="thermo-evidence"><strong>Pagrindžianti ištrauka${e.kind==='video'?` · ${e.start_seconds}–${e.end_seconds} s`:e.kind==='image'?' · paveikslėlio tekstas':''}:</strong> „${escape(e.quote)}“</p>`).join('');
    const media=unit.attachments.map(m=>{
      if(m.kind==='image') return m.asset?`<p class="thermo-note">${escape(m.description)}${m.ocr_text?` · OCR: ${escape(m.ocr_text)}`:''}</p>`:'<p class="thermo-note">Paveikslėlis neperskaitomas · reikia peržiūros.</p>';
      if(m.kind==='video') return `<div class="thermo-media"><p>${escape(m.description)}</p><p><strong>Įvertinta tik:</strong> transkripcija ir subtitrai 10–18 s, iliustraciniai kadrai ties 10 ir 18 s. Visas 60 s klipas nevertintas.</p><img src="demo/help-frame.svg" alt="Sintetinis pagalbos punkto kadras" width="480" height="220" loading="lazy"><blockquote>${escape(m.transcript.map(t=>t.text).join(' '))}</blockquote></div>`;
      return '';
    }).join('');
    return `<article class="thermo-item"><div class="thermo-item-meta"><span>${kind} ${escape(unit.id)}${report.mode==='demo'?' · sintetinis':''}</span><time datetime="${escape(unit.published_at)}">${date(unit.published_at)}</time></div>${window.SignalSourceContent.body(unit,{quote:true})}${discussionMarkup(unit,report)}${media}<div class="source-actions">${window.SignalSourceContent.link(unit)}</div><p><strong>${a.status==='assessed'?'Vertinimo paaiškinimas':pendingLabels[a.status]||'Neįvertinta'}:</strong> ${escape(a.reason)}</p>${a.reason_codes?.length?`<p class="thermo-note">Pagrindo kodai: ${escape(a.reason_codes.join(', '))}</p>`:''}${a.method==='manual_review'?'<p class="thermo-manual-confirmed">✓ Kryptis patvirtinta rankiniu būdu</p>':''}${evidence}<details class="thermo-context"><summary>${report.mode==='demo'?'Demonstracinio pavyzdžio pagrindas':'Vertinimo pagrindas'} · peržiūrėtos dalys</summary><p>${escape(report.mode==='live'?(report.exercise_context?.confirmedFacts||'Pradinis pratybų kontekstas nepateiktas.'):(context?.facts||'Nėra paskelbimo metu galiojusio konteksto.'))}</p><p>Peržiūrėta: ${escape(a.reviewed_parts.map(partLabel).join(', ')||'neįvertinta')}.</p><p>${report.mode==='demo'?'Iš anksto parengta demonstracinė žyma. Naratyvo pozicija nebuvo naudojama kategorijai išvesti.':a.method==='manual_review'?'Analitiko patvirtinta kryptis pagal peržiūrėtą turinį ir nurodytą pagrindą.':'Vertintas tik tekstas. Medijos turinys neperžiūrėtas; kategorija nenustatoma pagal autoriaus tapatybę ar naratyvo poziciją.'}</p></details></article>`;
  }
  function codeOptions(category,selected=''){
    return `<option value="">Pasirinkite pagrindą</option>${(reasonCodes[category]||[]).map(([id,label])=>`<option value="${id}"${id===selected?' selected':''}>${id} · ${escape(label)}</option>`).join('')}`;
  }
  function reviewForm(unit,report){
    if(report.mode!=='live'||!['assessed','needs_review','error'].includes(unit.assessment.status))return '';
    const editing=unit.assessment.status==='assessed',category=editing?unit.assessment.category:'';
    const code=editing?(unit.assessment.reason_codes||[])[0]:'';
    const form=`<form class="thermo-review" data-thermo-review data-source="${escape(unit.source)}" data-id="${escape(unit.id)}"><h3>${editing?'Pakeisti komunikacinę kryptį':'Rankinis krypties patvirtinimas'}</h3><p>Patikrinkite turinį ir jo originalą. Išsaugotas sprendimas bus įskaitytas į termometro statistiką.</p><div class="thermo-review-grid"><label>Kryptis<select name="category" required><option value="">Pasirinkite</option>${Object.entries(labels).map(([id,label])=>`<option value="${id}"${id===category?' selected':''}>${escape({stabilizing:"Stabilizuojantis",neutral:"Neutralus",destabilizing:"Destabilizuojantis"}[id])}</option>`).join('')}</select></label><label>Pagrindo kodas<select name="reason_code" required${category?'':' disabled'}>${category?codeOptions(category,code):'<option value="">Pirmiausia pasirinkite kryptį</option>'}</select></label></div><label>Trumpas vertinimo pagrindas<textarea name="reason" required minlength="5" maxlength="2000" rows="2">${editing?escape(unit.assessment.reason):''}</textarea></label><p class="thermo-review-error" role="alert" aria-live="polite"></p><button type="submit" class="button">${editing?'Išsaugoti pakeitimą':'Išsaugoti vertinimą'}</button></form>`;
    return editing?`<details class="thermo-review-edit" data-thermo-edit><summary>Keisti kryptį</summary>${form}</details>`:form;
  }
  function reviewFields(form){
    const category=form.elements.category.value,code=form.elements.reason_code;
    code.innerHTML=codeOptions(category);
    code.disabled=!category;
  }
  function updateEvidence(root, report) {
    const list=root.querySelector('#thermo-evidence');
    const toggle=root.querySelector('#thermo-content-toggle');
    list.hidden=!expanded;
    toggle.setAttribute('aria-expanded',String(expanded));
    root.querySelectorAll('[data-thermo-category]').forEach(button=>button.setAttribute('aria-pressed',String(expanded&&button.dataset.thermoCategory===active)));
    if(!expanded){list.innerHTML='';return;}
    const items=report.units.filter(u=>active==='all'||(active==='manual_review'?['needs_review','error'].includes(u.assessment.status):active==='needs_review'?u.assessment.status!=='assessed':u.assessment.status==='assessed'&&u.assessment.category===active));
    const title=active==='all'?'Visas termometro turinys':active==='manual_review'?'Laukia rankinio patvirtinimo':active==='needs_review'?'Neįvertinta / reikia peržiūros':labels[active];
    const filters=[['all','Visas turinys',report.total],...report.categories.map(c=>[c.id,c.label,c.count]),['needs_review','Neįvertinta',report.unassessed],['manual_review','Laukia rankinio patvirtinimo',report.units.filter(u=>['needs_review','error'].includes(u.assessment.status)).length]];
    list.innerHTML=`<div class="thermo-content-filters" role="group" aria-label="Termometro turinio kategorijos">${filters.map(([id,label,count])=>`<button type="button" class="thermo-content-filter" data-thermo-category="${id}" aria-pressed="${active===id}">${escape(label)} <span>${count}</span></button>`).join('')}</div><div class="panel-heading"><div><h2>${escape(title)} <span class="compact-count">${items.length}</span></h2><p>Pasirinkto laikotarpio ${report.mode==='demo'?'sintetiniai ':''}turinio vienetai vidinei analizei</p></div></div><div class="thermo-items">${items.length?items.map(u=>{
      const category=u.assessment.status==='assessed'?u.assessment.category:'needs_review';
      const label=labels[category]||pendingLabels[u.assessment.status]||'Neįvertinta';
      return `<div class="thermo-classified-item"><span class="thermo-content-badge ${category}">${escape(label)}</span>${evidenceCard(u,report)}${reviewForm(u,report)}</div>`;
    }).join(''):'<p class="thermo-note">Šios kategorijos vienetų pasirinktu laikotarpiu nėra.</p>'}</div>`;
    root.querySelectorAll('[data-thermo-category]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.thermoCategory===active)));
    bindDiscussions(list,report);
    list.querySelectorAll('[data-thermo-edit]').forEach(details=>details.addEventListener('toggle',()=>{
      root.reviewEditing=Boolean(root.reviewDirty)||Array.from(list.querySelectorAll('[data-thermo-edit]')).some(d=>d.open);
    }));
  }
  function paint(root,report) {
    root.reviewEditing=false;root.reviewDirty=false;
    const parts=report.categories.map(c=>`<button class="thermo-segment ${c.id}" style="flex-grow:${c.count};${c.count?'':'display:none'}" data-thermo-category="${c.id}" aria-label="${escape(c.label)}: ${c.count}, ${pct(c.percent)}" aria-controls="thermo-evidence" aria-pressed="${active===c.id}"></button>`).join('');
    root.innerHTML=`<p class="thermo-review-confirmation" data-thermo-review-confirmation role="status" tabindex="-1"></p><section class="panel thermo-summary" aria-labelledby="thermo-title"><div class="panel-heading"><div><h2 id="thermo-title">Turinio komunikacinė kryptis</h2><p class="thermo-period-label">Laikotarpis: ${escape(report.start.slice(0,10))}–${escape(new Date(Date.parse(report.end)-1).toLocaleDateString("sv-SE",{timeZone:"Europe/Vilnius"}))} · ${report.period} d.</p></div></div><div class="thermo-body">${report.assessed?`<div class="thermo-bar" role="group" aria-label="Turinio kategorijų proporcijos">${parts}</div>`:'<p class="thermo-empty">Nėra įvertintų duomenų</p>'}<div class="thermo-legend">${report.categories.map(c=>`<button class="thermo-category ${c.id}" data-thermo-category="${c.id}" aria-controls="thermo-evidence" aria-pressed="${active===c.id}"><span class="thermo-dot"></span><span>${escape(c.label)}<strong>${pct(c.percent)}</strong></span></button>`).join('')}</div><div class="thermo-coverage"><p><strong>Aprėptis: ${report.assessed} iš ${report.total}</strong> turinio vienetų įvertinta${report.coverage_percent===null||report.coverage_percent===undefined?'':` (${pct(report.coverage_percent)})`}.</p><button class="text-button" data-thermo-category="needs_review" aria-controls="thermo-evidence" aria-pressed="${active==='needs_review'}">Neįvertinta: ${report.unassessed}</button>${report.mode==='live'?`<button type="button" class="text-button" data-thermo-category="manual_review" aria-controls="thermo-evidence" aria-pressed="${active==='manual_review'}">Peržiūrėti ir priskirti kryptį (${report.units.filter(u=>['needs_review','error'].includes(u.assessment.status)).length})</button>`:''}${report.mode==='live'&&report.unassessed?`<p class="thermo-note">${Object.entries(report.pending||{}).filter(([,count])=>count).map(([status,count])=>`${pendingLabels[status]||status}: ${count}`).join(' · ')}</p>`:''}${report.assessed>0&&report.assessed<20?'<p class="thermo-note">Maža įvertinimo imtis.</p>':''}${report.total&&report.assessed/report.total<.8?'<p class="thermo-note">Dalis turinio dar neįvertinta; procentai apima tik įvertintus vienetus.</p>':''}</div></div></section><section class="panel thermo-trend" aria-labelledby="thermo-trend-title"><div class="panel-heading"><div><h2 id="thermo-trend-title">Proporcijų raida laike</h2><p>Kiekviena diena – 100 % tos dienos įvertinto turinio. Brūkšniuota – nėra įvertintų duomenų. Po data: įvertinta / gauta.</p></div></div>${chart(report)}</section><section class="panel thermo-content-panel"><button type="button" id="thermo-content-toggle" class="thermo-content-toggle" aria-expanded="false" aria-controls="thermo-evidence"><span>Termometro turinys</span><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></button><div id="thermo-evidence" hidden role="region" aria-label="Termometro turinys vidinei analizei" aria-live="polite"></div></section>`;
    updateEvidence(root,report);
    root.onclick=event=>{
      if(event.target.closest('#thermo-content-toggle')){expanded=!expanded;if(expanded)active='all';updateEvidence(root,report);return;}
      const button=event.target.closest('[data-thermo-category]');if(!button)return;
      const wasFilter=Boolean(button.closest?.('.thermo-content-filters'));
      active=button.dataset.thermoCategory;expanded=true;updateEvidence(root,report);
      if(!wasFilter){const list=root.querySelector('#thermo-evidence');list.setAttribute('tabindex','-1');list.focus({preventScroll:true});list.scrollIntoView({block:'start'});}
      if(wasFilter)root.querySelector('#thermo-evidence').querySelector(`[data-thermo-category="${active}"]`)?.focus({preventScroll:true});
    };
    root.oninput=event=>{if(event.target.closest?.('[data-thermo-review]'))root.reviewEditing=root.reviewDirty=true;};
    root.onchange=event=>{
      const form=event.target.closest?.('[data-thermo-review]');if(!form)return;
      root.reviewEditing=root.reviewDirty=true;
      if(event.target.name==='category')reviewFields(form);
    };
    root.onsubmit=async event=>{
      const form=event.target.closest?.('[data-thermo-review]');if(!form)return;
      event.preventDefault();const submit=form.querySelector('[type=submit]');if(submit.disabled)return;
      if(!form.reportValidity())return;
      const savedPeriod=currentPeriod,savedGeneration=generation;
      const values=Object.fromEntries(new FormData(form));
      const payload={source:form.dataset.source,id:form.dataset.id,...values};
      submit.disabled=true;form.querySelector('.thermo-review-error').textContent='';
      try{
        await window.SignalLiveData.saveThermometerReview(payload);
        cache.clear();
        if(savedGeneration!==generation||current!==root||!root.isConnected)return;
        const updated=await acquire(savedPeriod);
        if(savedGeneration!==generation||current!==root||!root.isConnected)return;
        expanded=true;paint(root,updated);
        const confirmation=root.querySelector('[data-thermo-review-confirmation]');
        confirmation.textContent='Vertinimas išsaugotas. Kryptis įskaityta į termometro statistiką.';
        confirmation.focus({preventScroll:true});
        root.querySelector('#thermo-evidence')?.scrollIntoView?.({block:'nearest'});
      }catch(error){form.querySelector('.thermo-review-error').textContent=error.message;submit.disabled=false;}
    };
  }
  async function mount(root,period) {
    const request=++generation;current=root;currentPeriod=period;expanded=false;active='all';
    root.innerHTML='<section class="panel thermo-body" role="status">Įkeliami turinio duomenys…</section>';
    try {
      const report=await acquire(period);
      if(request!==generation||!root.isConnected||current!==root)return;
      paint(root,report);
    } catch(error) {
      if(request!==generation||!root.isConnected)return;
      root.innerHTML=`<section class="panel thermo-body" role="alert"><h2>Duomenų įkelti nepavyko</h2><p>${escape(error.message)}</p><button class="button" id="thermo-retry">Bandyti dar kartą</button></section>`;
      root.querySelector('#thermo-retry').onclick=()=>mount(root,period);
    }
  }
  async function refresh(root,period){
    if(current!==root||(currentPeriod.key||currentPeriod)!==(period.key||period))return mount(root,period);
    // Keep the open list and typed review in place while background results arrive.
    if(root.reviewEditing)return;
    const request=++generation;
    try{
      const report=await acquire(period);
      if(request!==generation||current!==root||!root.isConnected||root.reviewEditing)return;
      paint(root,report);
    }catch(_){/* Keep the last successful report and review controls available. */}
  }
  function prepareAnalysisInput(unit){
    return {...window.SignalExerciseContext.analysisInput(unit),analysis_kind:'content_direction',
      categories:{stabilizing:'Stabilizuojantis turinys',neutral:'Neutralus arba nesusijęs turinys',destabilizing:'Destabilizuojantis turinys'},
      stream_scope:'all_content',requires_narrative_assignment:false,
      review_policy:{status:'needs_review',category:null,reason_required:true},
      direction_policy:'Vertink turinio komunikacinę kryptį, ne emocinį toną ar naratyvo stance. Nežinomas būtinas faktas reikalauja peržiūros; jo nebuvimas pradiniame kontekste neįrodo klaidingumo.'};
  }
  return {mount,refresh,prepareAnalysisInput,invalidate:()=>cache.clear()};
})();
