"use strict";
window.SignalPlatformOverview=(()=>{
  const content=window.SignalSourceContent,esc=content.escape;
  const count=n=>Number.isSafeInteger(n)?n.toLocaleString('lt-LT'):'Duomenų nėra';
  const percent=n=>n>0&&n<0.1?'&lt; 0,1':n.toLocaleString('lt-LT',{maximumFractionDigits:1});
  const cache=new Map();let generation=0;
  async function acquire(period){
    const key=period.key||period,query=period.query||`period=${period}`,duration=period.period||period;
    if(cache.has(key))return cache.get(key);
    for(const url of [`/api/platform/overview?${query}`,...(!window.SignalLiveData?.active()?[`demo/platform-${period}.json?v=thumbnails-12`]:[])]){
      try{
        const response=await fetch(url,{cache:'no-store'});if(!response.ok)continue;
        const report=await response.json();
        if(!['demo','live'].includes(report.mode)||!Array.isArray(report.categories)||!Array.isArray(report.authors?.items)||report.period!==duration||report.counter_scope!=='lifetime_for_posts_published_in_period')continue;
        cache.set(key,report);return report;
      }catch(_){}
    }
    throw Error('Platformos apžvalgos duomenų įkelti nepavyko.');
  }
  const glyphs={comments:'<path d="M21 11a8 8 0 0 1-8 8H5l-4 3V11a10 10 0 0 1 20 0Z"/>',likes:'<path d="M8 21H3V10h5m0 11h9a2 2 0 0 0 2-1.5L22 11a2 2 0 0 0-2-2h-6l1-5a2 2 0 0 0-4-1L8 10v11Z"/>',shares:'<path d="M4 20v-5a7 7 0 0 1 7-7h8m-5-5 5 5-5 5"/>'};
  function postCard(post,category=null){
    return `<article class="platform-post"><div class="platform-post-meta"><strong>${esc(post.author_name||'Autorius nepateiktas')}</strong><time datetime="${esc(post.published_at)}">${content.date(post.published_at)}</time></div>${category?`<div class="platform-counter"><span>${({comments:'Komentarų su atsakymais',likes:'Patiktukų',shares:'Pasidalijimų'})[category]}</span><strong>${count(post.count)}</strong></div>`:''}${content.body(post)}<div class="source-actions">${content.link(post)}</div></article>`;
  }
  function categoryMarkup(category){
    const missing=category.status==='missing_data';
    const warning=category.missing_posts?`<p class="platform-data-note" role="status">${count(category.missing_posts)} įrašų skaitiklių trūksta. ${category.items.length?'Pateikta turimų duomenų atranka.':''}</p>`:'';
    return `<section class="panel platform-category ${esc(category.id)}" aria-labelledby="platform-${esc(category.id)}"><div class="platform-category-heading"><h2 id="platform-${esc(category.id)}">${esc(category.label)}</h2><svg viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">${glyphs[category.id]||''}</svg></div><div class="platform-category-body">${warning}${category.items.length?category.items.map(p=>postCard(p,category.id)).join(''):`<p class="platform-empty">${missing?'Šios kategorijos duomenų nepakanka.':`Pasirinktu laikotarpiu nėra įrašų ${({comments:'su komentarais',likes:'su patiktukais',shares:'su pasidalijimais'})[category.id]}.`}</p>`}</div></section>`;
  }
  function authorsMarkup(authors){
    const policy=authors.policy,weights=policy.weights;
    const note=`Reikia bent ${policy.min_original_posts} skirtingų originalių įrašų. Kiekvienos dalies kiekis dalijamas iš didžiausio tos dalies kiekio tarp kriterijus atitinkančių asmeninių paskyrų ir dauginamas iš jos svorio. Gauti komentarai (su atsakymais) ir persidalijimai skaičiuojami prie šių įrašų; paties autoriaus sąveikos neįtraukiamos. Vienodo teksto ir tos pačios medijos pakartojimai tam pačiam autoriui skaičiuojami vieną kartą. Tai nėra AI kokybės ar autorystės patikra. Balas nėra auditorijos procentas.`;
    const notices=[];
    if(authors.unknown_account_types)notices.push(`${count(authors.unknown_account_types)} paskyrų tipas nepatvirtintas — jos nereitinguojamos.`);
    if(authors.incomplete_authors||authors.missing_identity_posts)notices.push('Autorių reitingui duomenų nepakanka: daliai autorių trūksta turinio arba pilnų komentarų / persidalijimų duomenų.');
    if(authors.status==='missing_data'&&!notices.length)notices.push('Autorių reitingui duomenų nepakanka.');
    const warning=notices.length?`<p class="platform-data-note" role="status">${notices.map(esc).join(' ')}</p>`:'';
    const rows=authors.items.map((a,i)=>`<li class="platform-author"><div class="platform-author-row"><span class="platform-rank" aria-label="${i+1} vieta">${String(i+1).padStart(2,'0')}</span><div class="platform-author-info"><h3>${esc(a.author_name)}</h3>${a.account_classification?.method==='name_heuristic'?'<span class="author-type-note">Asmeninis profilis pagal pavadinimą</span>':''}<p>Originalių įrašų: <b>${count(a.unique_original_posts)}</b> · gautų komentarų: <b>${count(a.received_comments)}</b> · persidalijimų: <b>${count(a.received_shares)}</b></p>${a.duplicate_posts?`<p>Pasikartojantys įrašai neįtraukti: ${count(a.duplicate_posts)}.</p>`:''}</div><strong class="author-score">${percent(a.score)}<small>/ 100 balų</small></strong></div><div class="author-score-parts" aria-label="Balo sudėtis"><span>Originalūs įrašai <strong>${percent(a.score_components.originals)} / ${weights.originals}</strong></span><span>Komentarai <strong>${percent(a.score_components.comments)} / ${weights.comments}</strong></span><span>Persidalijimai <strong>${percent(a.score_components.shares)} / ${weights.shares}</strong></span></div><details class="platform-author-posts"><summary>Autoriaus originalūs įrašai (${count(a.unique_original_posts)})</summary><div>${a.posts.map(p=>postCard(p)).join('')}</div></details></li>`).join('');
    return `<section class="panel platform-authors" aria-labelledby="platform-authors-title"><div class="panel-heading"><div><h2 id="platform-authors-title">Populiariausi įrašų autoriai</h2><p>Turinio kūrimas ir auditorijos įsitraukimas · asmeniniai profiliai pagal pateiktus duomenis ir pavadinimą</p></div></div><div class="author-weights" aria-label="Reitingo svoriai"><span><b>${weights.originals} %</b> originalūs įrašai</span><span><b>${weights.comments} %</b> komentarai</span><span><b>${weights.shares} %</b> persidalijimai</span></div><details class="author-method"><summary>Kaip skaičiuojama?</summary><p>${esc(note)}</p><p>Organizacijos, verslai, institucijos, žiniasklaida ir ne pelno organizacijos neįtraukiamos. Pirmiausia naudojami patvirtinti paskyros tipo duomenys. Kai jų nėra, vertinamas pavadinimas: domenai bei organizacijų žymenys. Vien vietovardžio neužtenka. Slapyvardis be organizacinių požymių laikomas asmeninio profilio požymiu; tai euristika, ne tapatybės patvirtinimas, todėl gali likti klaidų.</p></details>${warning}${rows?`<ol class="platform-author-list">${rows}</ol>`:authors.status!=='missing_data'?'<p class="platform-empty">Pasirinktu laikotarpiu nėra autorių, atitinkančių reitingo kriterijus.</p>':''}</section>`;
  }
  function totalsMarkup(report){
    const totals=report.totals,known=totals?.basis==='collected_records_by_own_publication_date';
    const scope=report.mode==='demo'?'Demonstraciniai duomenys':report.collection_scope?.selected_period_complete?'Visos platformos turinys':'Surinkta imtis · ne visa platforma';
    return `<div class="platform-totals" aria-label="Turinio kiekis pasirinktu laikotarpiu">${[['posts','Iš viso įrašų','Įrašai ir persidalijimai pagal jų paskelbimo datą.'],['comments','Iš viso komentarų','Komentarai ir atsakymai pagal jų paskelbimo datą, įskaitant komentarus prie senesnių įrašų.']].map(([key,label,help])=>`<section class="panel platform-total" aria-label="${label}"><h2>${label}</h2><strong title="${help}">${count(known&&Number.isSafeInteger(totals[key])&&totals[key]>=0?totals[key]:null)}</strong><small>${scope} · pasirinktu laikotarpiu</small></section>`).join('')}</div>`;
  }
  function paint(root,report){
    const scopeLabel=report.mode==='demo'?'Demonstraciniai duomenys':report.collection_scope?.selected_period_complete?'Administratoriaus eksportas · pasirinktas laikotarpis aprėptas':'Tikri duomenys · nepilna platformos aprėptis';
    const end=new Date(Date.parse(report.end)-1).toLocaleDateString('sv-SE',{timeZone:'Europe/Vilnius'});
    const start=new Date(report.start).toLocaleDateString('sv-SE',{timeZone:'Europe/Vilnius'});
    root.innerHTML=`${totalsMarkup(report)}<div class="platform-scope"><span class="platform-mode">${scopeLabel}</span><span>${esc(start)}–${esc(end)} · ${report.period} d. · Lietuvos laiku</span></div><div class="platform-categories">${report.categories.map(categoryMarkup).join('')}</div>${authorsMarkup(report.authors)}${report.mode==='live'?`<section class="panel live-source-posts"><div class="panel-heading"><div><h2>Gauti įrašai <span class="compact-count">${report.posts.length}</span></h2><p>Taip pat rodomi įrašai, kurie dar neturi sąveikų arba naratyvo.</p></div></div><div class="platform-source-grid">${report.posts.map(p=>postCard(p)).join('')||'<p class="platform-empty">Pasirinktu laikotarpiu gautų įrašų nėra.</p>'}</div></section>`:''}`;
  }
  async function mount(root,period){
    const request=++generation;
    root.innerHTML='<section class="panel platform-loading" role="status">Įkeliama platformos apžvalga…</section>';
    try{const report=await acquire(period);if(request===generation&&root.isConnected)paint(root,report);}
    catch(error){if(request!==generation||!root.isConnected)return;root.innerHTML=`<section class="panel platform-loading" role="alert"><p>${esc(error.message)}</p><button type="button" class="button" id="platform-retry">Bandyti dar kartą</button></section>`;root.querySelector('#platform-retry').onclick=()=>mount(root,period);}
  }
  return Object.freeze({mount,paint,postCard,invalidate:()=>cache.clear()});
})();
