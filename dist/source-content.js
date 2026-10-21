"use strict";
window.SignalSourceContent=(()=>{
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function url(value){
    if(typeof value!=='string'||/[\s\x00-\x1f]/u.test(value))return null;
    try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&u.pathname!=='/'?value:null;}catch(_){return null;}
  }
  function reference(unit){
    return {id:unit.id??unit.external_id??null,source:unit.source??null,kind:unit.kind??'post',
      sourceUrl:url(unit.sourceUrl??unit.original_url??unit.url),parentSourceUrl:url(unit.parentSourceUrl)};
  }
  function link(unit){
    if(unit.is_demo===true||unit.is_demo===1)return '<span class="source-unavailable">Demonstracinis turinys · originalo nuorodos nėra.</span>';
    const r=reference(unit),href=r.sourceUrl||(r.kind==='comment'?r.parentSourceUrl:null);
    if(!href)return '<span class="source-unavailable">Originalo nuoroda nepateikta.</span>';
    const label=r.kind==='comment'?(r.sourceUrl?'Komentaro nuoroda':'Atverti pirminį įrašą'):'Įrašo nuoroda';
    return `<a class="source-link" href="${escape(href)}" target="_blank" rel="noopener noreferrer">${label}<span aria-hidden="true"> ↗</span><span class="source-sr"> (naujame skirtuke)</span></a>`;
  }
  const date=value=>{try{return new Intl.DateTimeFormat('lt-LT',{timeZone:'Europe/Vilnius',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value));}catch(_){return 'Data nepateikta';}};
  function text(value,limit=360){
    const original=String(value??'');
    if(original.length<=limit)return `<p class="source-text">${escape(original||'Įrašo tekstas nepateiktas.')}</p>`;
    return `<div class="source-copy"><p class="source-text source-excerpt">${escape(original.slice(0,limit))}…</p><details class="source-full"><summary>Rodyti visą tekstą</summary><p class="source-text">${escape(original)}</p></details></div>`;
  }
  function mediaItems(unit){
    const own=Array.isArray(unit.media)?unit.media:Array.isArray(unit.attachments)?unit.attachments:[];
    const asset=value=>(unit.is_demo===true||unit.is_demo===1)&&typeof value==='string'&&/^demo\/[\w.-]+\.(svg|png|jpe?g|webp)$/.test(value)?value:url(value);
    return own.map((m,index)=>m&&['image','video'].includes(m.kind??m.type)?({kind:m.kind??m.type,index,
      thumbnailUrl:asset(m.thumbnailUrl),originalUrl:asset(m.originalUrl||m.url||m.asset),
      alt:m.alt||m.description||'',caption:m.caption??'',posterUrl:asset(m.posterUrl)}):null).filter(Boolean);
  }
  function thumbnail(unit){
    const photos=mediaItems(unit).filter(m=>m.kind==='image'),first=photos[0];
    const src=first?.thumbnailUrl||first?.originalUrl;if(!src)return '';
    const demo=unit.is_demo===true||unit.is_demo===1,r=reference(unit);
    const href=demo?null:r.sourceUrl||(r.kind==='comment'?r.parentSourceUrl:null);
    const label=r.kind==='comment'?(r.sourceUrl?'Atverti komentarą naujame skirtuke':'Atverti pirminį įrašą naujame skirtuke'):'Atverti originalų įrašą naujame skirtuke';
    const source=r.source||window.SignalLiveData?.get()?.source;
    const mediaRef=!demo&&r.id&&source?{source,id:r.id,index:first.index}:null;
    const image=`<img class="source-thumb-image" data-source-thumbnail ${mediaRef?`data-source-media-ref="${escape(JSON.stringify(mediaRef))}"`:''} ${first.originalUrl&&first.originalUrl!==src?`data-source-fallback="${escape(first.originalUrl)}"`:''} src="${escape(src)}" alt="${escape(first.alt||'Prisegta įrašo nuotrauka')}" width="96" height="72" loading="lazy" decoding="async" referrerpolicy="no-referrer">${photos.length>1?`<span class="source-photo-count" aria-hidden="true">+${photos.length-1}</span><span class="source-sr">Papildomų nuotraukų: ${photos.length-1}</span>`:''}`;
    const preview=href?`<a class="source-thumbnail-preview" data-source-thumbnail-link href="${escape(href)}" target="_blank" rel="noopener noreferrer" aria-label="${escape(label)}">${image}</a>`:`<span class="source-thumbnail-preview">${image}</span>`;
    return `<figure class="source-thumbnail" data-source-thumbnail-wrap>${preview}${demo?'<figcaption>Demonstracinė iliustracija</figcaption>':''}</figure>`;
  }
  function videos(unit){
    return mediaItems(unit).filter(m=>m.kind==='video'&&m.originalUrl).map(m=>`<figure class="source-media"><video src="${escape(m.originalUrl)}" ${m.posterUrl?`poster="${escape(m.posterUrl)}"`:''} controls preload="none" aria-label="${escape(m.alt||'Įrašo vaizdo įrašas')}"></video>${m.caption?`<figcaption>${escape(m.caption)}</figcaption>`:''}</figure>`).join('');
  }
  function media(unit){return thumbnail(unit)+videos(unit);}
  function body(unit,{quote=false}={}){
    return `<div class="source-content-body">${thumbnail(unit)}${quote?`<blockquote>${escape(unit.text)}</blockquote>`:text(unit.text)}</div>${videos(unit)}`;
  }
  if(typeof document!=='undefined'){
    function originalOrHide(img){
      const fallback=url(img.getAttribute('data-source-fallback'));
      if(fallback){img.removeAttribute('data-source-fallback');img.src=fallback;return;}
      img.closest('[data-source-thumbnail-wrap]')?.remove();
    }
    document.addEventListener('load',event=>{if(event.target.matches?.('[data-source-thumbnail]'))event.target.setAttribute('data-source-loaded','true');},true);
    document.addEventListener('error',event=>{
      const img=event.target;if(!img.matches?.('[data-source-thumbnail]'))return;
      const value=img.getAttribute('data-source-media-ref');
      if(value&&window.SignalLiveData?.active()&&window.SignalLiveData.image){
        img.removeAttribute('data-source-media-ref');
        let ref;try{ref=JSON.parse(value);}catch(_){originalOrHide(img);return;}
        window.SignalLiveData.image(ref.source,ref.id,ref.index).then(blob=>{
          if(!img.isConnected)return;
          const address=URL.createObjectURL(blob),release=()=>URL.revokeObjectURL(address);
          img.addEventListener('load',release,{once:true});img.addEventListener('error',release,{once:true});
          img.src=address;
        }).catch(()=>originalOrHide(img));
        return;
      }
      originalOrHide(img);
    },true);
    // Keep the native link action, including keyboard Enter, without triggering an accordion.
    document.addEventListener('click',event=>{if(event.target.closest?.('[data-source-thumbnail-link]'))event.stopImmediatePropagation();},true);
  }
  return Object.freeze({escape,url,reference,link,date,text,mediaItems,thumbnail,media,body});
})();
