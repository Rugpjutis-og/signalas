"use strict";

const icons = {
  overview:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  map:'<circle cx="5" cy="7" r="2.5"/><circle cx="18" cy="4" r="2.5"/><circle cx="12" cy="17" r="3"/><circle cx="21" cy="18" r="1.5"/><path d="m7 8 3.5 6.5M7.5 6.5 15.5 4.5M17 6.5l-3.5 8M15 17.5l4.5.5"/>',
  time:'<path d="M3 3v17h18M6 14l4-5 4 3 6-8"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 11h18"/>',
  download:'<path d="M12 3v12m-4-4 4 4 4-4M4 15v5h16v-5"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.6 2.6 0 0 1 5 .8c0 1.9-2.5 2-2.5 3.7M12 17h.01"/>',
  reset:'<path d="M3 10a9 9 0 1 1 1 7M3 4v6h6"/>',
  arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
  arrowup:'<path d="M5 16 16 5M6 5h10v10"/>',
  trend:'<path d="m3 17 6-6 4 3 8-10M15 4h6v6"/>',
  bolt:'<path d="m13 2-9 12h7l-1 8 10-12h-8z"/>',
  trust:'<path d="m12 3 8 4v5c0 5-8 9-8 9s-8-4-8-9V7z"/><path d="m8 12 3 3 5-6"/>',
  economy:'<path d="M3 20h18M6 16v-4m6 4V7m6 9V3"/>',
  safety:'<path d="M3 10 12 3l9 7v10H3zM9 20v-7h6v7"/>',
  info:'<path d="M21 11a8 8 0 0 1-8 8H7l-4 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4zM7 8h10M7 12h7"/>',
  health:'<path d="M20.5 4.5a5 5 0 0 0-7 0L12 6l-1.5-1.5a5 5 0 0 0-7 7L12 20l8.5-8.5a5 5 0 0 0 0-7z"/>',
  posts:'<rect x="5" y="3" width="15" height="18" rx="2"/><path d="M9 8h7M9 12h7M9 16h4M2 7v11"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  minus:'<path d="M5 12h14"/>',
  fit:'<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6"/>',
  link:'<path d="m10 13 4-4m-6 7-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 2 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  check:'<path d="m5 12 4 4 10-10"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>'
};
const icon=(name,size=16)=>`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.overview}</svg>`;
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>Math.round(n).toLocaleString('lt-LT');
// Administrator-managed catalog. AI may assign narratives only to these IDs.
const themes=Object.freeze([
  {
    "id": "institutions",
    "name": "Politika ir valdžia",
    "color": "#a38cc9",
    "soft": "#f5f0fb",
    "icon": "trust",
    "priority": true
  },
  {
    "id": "foreign",
    "name": "Tarptautiniai santykiai ir suverenitetas",
    "color": "#687bd4",
    "soft": "#eff2ff",
    "icon": "link",
    "priority": true
  },
  {
    "id": "security",
    "name": "Saugumas ir gynyba",
    "color": "#65a999",
    "soft": "#eef8f4",
    "icon": "safety",
    "priority": true
  },
  {
    "id": "economy",
    "name": "Ekonomika ir finansai",
    "color": "#c3a266",
    "soft": "#faf5ea",
    "icon": "economy",
    "priority": true
  },
  {
    "id": "work",
    "name": "Darbas ir socialinė apsauga",
    "color": "#b89970",
    "soft": "#faf5ed",
    "icon": "economy",
    "priority": false
  },
  {
    "id": "health",
    "name": "Sveikata",
    "color": "#72aaa0",
    "soft": "#eff8f5",
    "icon": "health",
    "priority": false
  },
  {
    "id": "education",
    "name": "Švietimas ir mokslas",
    "color": "#9b9acb",
    "soft": "#f3f2fb",
    "icon": "posts",
    "priority": false
  },
  {
    "id": "science",
    "name": "Technologijos ir skaitmeninė erdvė",
    "color": "#7b9cbf",
    "soft": "#eef4fa",
    "icon": "spark",
    "priority": false
  },
  {
    "id": "information",
    "name": "Žiniasklaida ir informacinė aplinka",
    "color": "#8b91c1",
    "soft": "#f1f2fa",
    "icon": "info",
    "priority": true
  },
  {
    "id": "identity",
    "name": "Visuomenė, tapatybė ir migracija",
    "color": "#c68e9f",
    "soft": "#fcf0f4",
    "icon": "info",
    "priority": true
  },
  {
    "id": "rights",
    "name": "Teisės ir teisėsauga",
    "color": "#76a9b8",
    "soft": "#edf6f9",
    "icon": "eye",
    "priority": true
  },
  {
    "id": "environment",
    "name": "Aplinka, klimatas ir energetika",
    "color": "#90ad7d",
    "soft": "#f2f7ed",
    "icon": "safety",
    "priority": false
  },
  {
    "id": "infrastructure",
    "name": "Transportas, būstas ir infrastruktūra",
    "color": "#b69c84",
    "soft": "#f8f3ef",
    "icon": "safety",
    "priority": false
  },
  {
    "id": "culture",
    "name": "Kultūra, istorija ir sportas",
    "color": "#b48ead",
    "soft": "#f8f0f7",
    "icon": "spark",
    "priority": false
  },
  {
    "id": "emergencies",
    "name": "Kasdienis gyvenimas ir krizės",
    "color": "#c39680",
    "soft": "#fcf2ed",
    "icon": "bolt",
    "priority": true
  }
].map(t=>Object.freeze(t)));
const unassignedTheme=Object.freeze({id:'unassigned',name:'Nepriskirti naratyvai',color:'#929cad',soft:'#f1f3f7',icon:'spark'});
const narratives=[
  {id:'N-001',firstSeenAt:'2026-10-13T08:10:00+03:00',theme:'environment',subtopic:'Energetika',title:'Kainos keliamos įmonių naudai',lines:['Kainos keliamos','įmonių naudai'],description:'Kainų kilimas aiškinamas sąmoningu sprendimu privilegijuotoms įmonėms uždirbti gyventojų sąskaita.',status:'confirmed',fixed:true,days:[120,145,170,230,310,395,470],growth:46,stance:[62,24,14],first:'Spalio 13 d.',evidence:[['IR-001','Spalio 19 · 14:32','Vėl didesnė sąskaita. Man atrodo, šis pakeitimas pirmiausia naudingas didžiosioms įmonėms.','Palaiko'],['IR-002','Spalio 19 · 13:18','Vien kainų padidėjimas neįrodo, kad kažkam sąmoningai suteikiama privilegija. Reikia patikrinti sąnaudų duomenis.','Prieštarauja'],['IR-003','Spalio 18 · 17:05','Diskusijoje kartojamas teiginys, kad kainos keliamos įmonių naudai. Kokiais skaičiais jis pagrįstas?','Cituoja / klausia']]},
  {id:'N-002',firstSeenAt:'2026-10-13T09:35:00+03:00',theme:'environment',subtopic:'Energetika',title:'Kainas lemia rinkos svyravimai',lines:['Kainas lemia','rinkos svyravimai'],description:'Kainų pokyčiai aiškinami rinkos pasiūlos, paklausos ir gamybos sąnaudų svyravimais.',status:'confirmed',fixed:true,days:[110,115,150,160,230,255,300],growth:31,stance:[55,27,18],first:'Spalio 13 d.',evidence:[['IR-004','Spalio 19 · 12:10','Tarifą verta lyginti su didmeninės rinkos kaina ir tiekimo sąnaudomis.','Palaiko'],['IR-005','Spalio 18 · 18:40','Vien rinkos svyravimų argumentas nepaaiškina visų sąskaitos dedamųjų.','Prieštarauja']]},
  {id:'N-003',firstSeenAt:'2026-10-13T10:20:00+03:00',theme:'economy',title:'Parama nepasiekia gyventojų',lines:['Parama nepasiekia','gyventojų'],description:'Pagalbos priemonės vaizduojamos kaip neprieinamos daliai tų gyventojų, kuriems jos skirtos.',status:'confirmed',fixed:false,days:[80,90,100,135,180,225,270],growth:24,stance:[58,18,24],first:'Spalio 13 d.',evidence:[['IR-006','Spalio 19 · 10:20','Prašymo sąlygos tokios sudėtingos, kad pagalba nepasiekia žmonių, kuriems jos labiausiai reikia.','Palaiko'],['IR-007','Spalio 18 · 09:10','Šioje bendruomenėje dalis šeimų jau gavo paramą. Negalima teigti, kad ji nieko nepasiekia.','Prieštarauja']]},
  {id:'N-004',firstSeenAt:'2026-10-13T07:45:00+03:00',theme:'institutions',title:'Sprendimai priimami be paaiškinimų',lines:['Sprendimai priimami','be paaiškinimų'],description:'Neaiškus sprendimų pagrindimas siejamas su pasitikėjimo institucijomis mažėjimu.',status:'confirmed',fixed:true,days:[140,155,180,190,210,255,290],growth:28,stance:[49,21,30],first:'Spalio 13 d.',evidence:[['IR-008','Spalio 19 · 16:15','Sprendimą paskelbė, bet jo motyvų gyventojams suprantamai nepaaiškino.','Palaiko'],['IR-009','Spalio 18 · 15:50','Paaiškinimas paskelbtas kartu su sprendimu. Klausimas, ar jis pakankamai aiškus.','Prieštarauja']]},
  {id:'N-005',firstSeenAt:'2026-10-13T11:05:00+03:00',theme:'institutions',title:'Vieši duomenys leidžia tikrinti',lines:['Vieši duomenys','leidžia tikrinti'],description:'Prieinami šaltiniai ir skaidrus sprendimų paaiškinimas pristatomi kaip galimybė savarankiškai tikrinti teiginius.',status:'confirmed',fixed:true,days:[85,95,105,115,150,190,230],growth:34,stance:[72,10,18],first:'Spalio 13 d.',evidence:[['IR-010','Spalio 19 · 15:00','Sudėkime pirminius duomenis vienoje vietoje – tada kiekvienas galės pasitikrinti teiginius.','Palaiko'],['IR-011','Spalio 18 · 12:11','Vien paskelbti lentelę neužtenka, jei be specialių žinių jos neįmanoma suprasti.','Prieštarauja']]},
  {id:'N-006',firstSeenAt:'2026-10-13T12:30:00+03:00',theme:'emergencies',title:'Bendruomenės gali pasiruošti krizėms',lines:['Bendruomenės gali','pasiruošti krizėms'],description:'Bendras pasirengimas, konkretūs veiksmai ir savitarpio pagalba siejami su didesniu bendruomenių atsparumu.',status:'confirmed',fixed:true,days:[70,80,90,110,135,165,210],growth:37,stance:[76,8,16],first:'Spalio 13 d.',evidence:[['IR-012','Spalio 19 · 11:23','Susitarkime, kaip susisieksime sutrikus ryšiui, ir patikrinkime, kam reikėtų pagalbos.','Palaiko'],['IR-013','Spalio 18 · 08:10','Dalijamės bendruomenės pasirengimo plano projektu diskusijai.','Cituoja / klausia']]},
  {id:'N-007',firstSeenAt:'2026-10-13T17:40:00+03:00',theme:'security',title:'Grėsmės sąmoningai nutylimos',lines:['Grėsmės sąmoningai','nutylimos'],description:'Informacijos trūkumas aiškinamas sąmoningu grėsmių slėpimu. Sąmoningumo priskyrimas yra pagrindinis šio kandidato požymis.',status:'candidate',fixed:false,days:[20,30,45,70,105,160,210],growth:86,stance:[42,35,23],first:'Spalio 13 d.',evidence:[['IR-014','Spalio 19 · 09:32','Jei niekas nepaaiškina situacijos, gal apie tikrąją grėsmę sąmoningai nekalbama?','Palaiko'],['IR-015','Spalio 19 · 10:17','Informacijos stoka pati savaime neįrodo, kad grėsmė slepiama.','Prieštarauja']]},
  {id:'N-008',firstSeenAt:'2026-10-13T16:15:00+03:00',theme:'economy',title:'Pokyčiai didina regionų atskirtį',lines:['Pokyčiai didina','regionų atskirtį'],description:'Naujos sąlygos aiškinamos kaip nevienodai veikiančios didmiesčių ir regionų gyventojus.',status:'candidate',fixed:false,days:[55,65,70,85,110,140,185],growth:53,stance:[57,16,27],first:'Spalio 13 d.',evidence:[['IR-016','Spalio 19 · 08:48','Vienodos sąlygos neturi vienodo poveikio: regione alternatyvų gerokai mažiau.','Palaiko'],['IR-017','Spalio 18 · 13:20','Ar yra palyginimas, rodantis skirtingą pakeitimo poveikį regionams?','Cituoja / klausia']]},
  {id:'N-009',firstSeenAt:'2026-10-13T18:50:00+03:00',theme:'information',title:'Klaidinantys teiginiai kuria paniką',lines:['Klaidinantys teiginiai','kuria paniką'],description:'Nepatikrintų teiginių sklaida siejama su nerimo augimu; siūloma tikrinti jų šaltinius prieš dalijantis.',status:'candidate',fixed:false,days:[30,40,45,65,85,110,135],growth:41,stance:[65,12,23],first:'Spalio 13 d.',evidence:[['IR-018','Spalio 19 · 07:50','Prieš dalindamiesi grėsmingu pranešimu patikrinkime, iš kur jis ir kada paskelbtas.','Palaiko'],['IR-019','Spalio 18 · 20:41','Diskusijoje keliamas klausimas, ar nepatikrinti pranešimai didina nerimą.','Cituoja / klausia']]},
  {id:'N-010',firstSeenAt:'2026-10-13T13:25:00+03:00',theme:'health',title:'Prevencija padeda mažinti rizikas',lines:['Prevencija padeda','mažinti rizikas'],description:'Ankstyvi prevenciniai veiksmai pristatomi kaip būdas mažinti būsimų sveikatos problemų tikimybę.',status:'confirmed',fixed:false,days:[35,40,45,55,65,80,110],growth:12,stance:[74,9,17],first:'Spalio 13 d.',evidence:[['IR-020','Spalio 19 · 11:00','Bendruomenės renginyje aptarkime kasdienius prevencijos įpročius.','Palaiko'],['IR-021','Spalio 18 · 16:42','Dalijamės diskusijos apie prevenciją santrauka.','Cituoja / klausia']]}
];
narratives.push(...[
  {
    "id": "N-011",
    "firstSeenAt": "2026-10-13T06:20:00+03:00",
    "theme": "security",
    "title": "Lietuva yra silpna, viena ir nepasiruošusi gintis",
    "lines": [
      "Lietuva nepasiruošusi",
      "gintis"
    ],
    "description": "Pasakojimas apie tariamą Lietuvos gynybinį silpnumą, sąjungininkų stoką ir nepasirengimą gynybai.",
    "subtopic": "Gynybinis pasirengimas",
    "secondaryThemes": [
      "foreign"
    ],
    "actors": [
      "Lietuva"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      70,
      90,
      125,
      170,
      225,
      290,
      360
    ],
    "growth": 53,
    "stance": [
      48,
      32,
      20
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-011-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Lietuva yra silpna, viena ir nepasiruošusi gintis“.",
        "Palaiko"
      ],
      [
        "IR-011-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-011-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Lietuva yra silpna, viena ir nepasiruošusi gintis“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-012",
    "firstSeenAt": "2026-10-13T08:55:00+03:00",
    "theme": "institutions",
    "title": "Institucijos ir žiniasklaida veikia prieš piliečius bei slepia tiesą",
    "lines": [
      "Institucijos ir medijos",
      "slepia tiesą"
    ],
    "description": "Institucijoms ir žiniasklaidai priskiriamas sąmoningas veikimas prieš piliečius ir informacijos slėpimas.",
    "subtopic": "Skaidrumas ir informacijos patikimumas",
    "secondaryThemes": [
      "rights"
    ],
    "actors": [
      "Institucijos",
      "Žiniasklaida"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      180,
      210,
      255,
      290,
      340,
      395,
      450
    ],
    "growth": 60,
    "stance": [
      51,
      28,
      21
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-012-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Institucijos ir žiniasklaida veikia prieš piliečius bei slepia tiesą“.",
        "Palaiko"
      ],
      [
        "IR-012-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-012-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Institucijos ir žiniasklaida veikia prieš piliečius bei slepia tiesą“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-013",
    "firstSeenAt": "2026-10-13T09:15:00+03:00",
    "theme": "foreign",
    "title": "Lietuva nėra suvereni, ją valdo JAV ir Europos Sąjunga, o NATO kursto karą",
    "lines": [
      "Lietuva valdoma",
      "iš išorės"
    ],
    "description": "Lietuvos savarankiškumas neigiamas, o sprendimų kontrolė ir karo kurstymas priskiriami išorės veikėjams.",
    "subtopic": "Suverenitetas ir sąjungininkai",
    "secondaryThemes": [
      "security"
    ],
    "actors": [
      "JAV",
      "Europos Sąjunga",
      "NATO"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      95,
      110,
      145,
      175,
      225,
      280,
      330
    ],
    "growth": 67,
    "stance": [
      43,
      36,
      21
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-013-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Lietuva nėra suvereni, ją valdo JAV ir Europos Sąjunga, o NATO kursto karą“.",
        "Palaiko"
      ],
      [
        "IR-013-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-013-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Lietuva nėra suvereni, ją valdo JAV ir Europos Sąjunga, o NATO kursto karą“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-014",
    "firstSeenAt": "2026-10-13T10:45:00+03:00",
    "theme": "identity",
    "title": "Lietuvos nepriklausomybė buvo klaida, o Klaipėdos krašto savitumas slopinamas",
    "lines": [
      "Nepriklausomybė ir",
      "Klaipėdos savitumas"
    ],
    "description": "Neigiamas Lietuvos nepriklausomybės vertinimas siejamas su teiginiu apie slopinamą Klaipėdos krašto savitumą.",
    "subtopic": "Istorinė atmintis ir regioninė tapatybė",
    "secondaryThemes": [
      "foreign"
    ],
    "actors": [
      "Lietuva"
    ],
    "places": [
      "Klaipėda",
      "Klaipėdos kraštas"
    ],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      40,
      55,
      70,
      95,
      125,
      155,
      200
    ],
    "growth": 25,
    "stance": [
      39,
      40,
      21
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-014-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Lietuvos nepriklausomybė buvo klaida, o Klaipėdos krašto savitumas slopinamas“.",
        "Palaiko"
      ],
      [
        "IR-014-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-014-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Lietuvos nepriklausomybė buvo klaida, o Klaipėdos krašto savitumas slopinamas“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-015",
    "firstSeenAt": "2026-10-13T11:40:00+03:00",
    "theme": "economy",
    "title": "Valdžia ir privilegijuotieji apsirūpinę, o paprasti žmonės palikti be vandens, kuro ir maisto",
    "lines": [
      "Ištekliai tik",
      "privilegijuotiesiems"
    ],
    "description": "Gyventojų aprūpinimas būtiniausiais ištekliais aiškinamas per privilegijuotos valdžios ir likusių gyventojų nelygybę.",
    "subtopic": "Gyventojų aprūpinimas",
    "secondaryThemes": [
      "institutions"
    ],
    "actors": [
      "Valdžia"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      110,
      125,
      160,
      210,
      270,
      340,
      410
    ],
    "growth": 32,
    "stance": [
      57,
      24,
      19
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-015-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Valdžia ir privilegijuotieji apsirūpinę, o paprasti žmonės palikti be vandens, kuro ir maisto“.",
        "Palaiko"
      ],
      [
        "IR-015-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-015-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Valdžia ir privilegijuotieji apsirūpinę, o paprasti žmonės palikti be vandens, kuro ir maisto“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-016",
    "firstSeenAt": "2026-10-13T14:10:00+03:00",
    "theme": "rights",
    "title": "Lietuvos šaulių sąjunga turi nelojalių piliečių sąrašus ir karo metu gaudys žmones",
    "lines": [
      "LŠS sąrašai ir",
      "piliečių gaudymas"
    ],
    "description": "Organizacijai priskiriamas tariamas piliečių skirstymas pagal lojalumą ir žmonių gaudymas karo metu.",
    "subtopic": "Piliečių sekimas ir valstybės galios ribos",
    "secondaryThemes": [
      "security"
    ],
    "actors": [
      "Lietuvos šaulių sąjunga",
      "LŠS"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      45,
      65,
      95,
      130,
      170,
      230,
      290
    ],
    "growth": 39,
    "stance": [
      41,
      38,
      21
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-016-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Lietuvos šaulių sąjunga turi nelojalių piliečių sąrašus ir karo metu gaudys žmones“.",
        "Palaiko"
      ],
      [
        "IR-016-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-016-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Lietuvos šaulių sąjunga turi nelojalių piliečių sąrašus ir karo metu gaudys žmones“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-017",
    "firstSeenAt": "2026-10-13T19:05:00+03:00",
    "theme": "rights",
    "title": "Lietuvos šaulių sąjunga vykdys prievartinės mobilizacijos funkcijas",
    "lines": [
      "Prievartinė",
      "mobilizacija"
    ],
    "description": "Pasakojimas apie tariamą Lietuvos šaulių sąjungos vaidmenį prievarta mobilizuojant gyventojus.",
    "subtopic": "Mobilizacija",
    "secondaryThemes": [
      "security"
    ],
    "actors": [
      "Lietuvos šaulių sąjunga",
      "LŠS"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      60,
      80,
      105,
      145,
      190,
      245,
      310
    ],
    "growth": 46,
    "stance": [
      46,
      33,
      21
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-017-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Lietuvos šaulių sąjunga vykdys prievartinės mobilizacijos funkcijas“.",
        "Palaiko"
      ],
      [
        "IR-017-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-017-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Lietuvos šaulių sąjunga vykdys prievartinės mobilizacijos funkcijas“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-018",
    "firstSeenAt": "2026-10-13T15:20:00+03:00",
    "theme": "security",
    "title": "Lietuvos šaulių sąjunga yra naciai, karo kurstytojai, o jos nariai ruošiami būti patrankų mėsa",
    "lines": [
      "LŠS demonizavimas ir",
      "narių panaudojimas"
    ],
    "description": "Organizacija demonizuojama, jai priskiriamas karo kurstymas, o narių pasirengimas vaizduojamas kaip jų paaukojimas.",
    "subtopic": "Gynybos organizacijų demonizavimas",
    "secondaryThemes": [
      "institutions"
    ],
    "actors": [
      "Lietuvos šaulių sąjunga",
      "LŠS"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      50,
      70,
      90,
      120,
      165,
      215,
      270
    ],
    "growth": 53,
    "stance": [
      36,
      44,
      20
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-018-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Lietuvos šaulių sąjunga yra naciai, karo kurstytojai, o jos nariai ruošiami būti patrankų mėsa“.",
        "Palaiko"
      ],
      [
        "IR-018-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-018-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Lietuvos šaulių sąjunga yra naciai, karo kurstytojai, o jos nariai ruošiami būti patrankų mėsa“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-019",
    "firstSeenAt": "2026-10-13T16:45:00+03:00",
    "theme": "institutions",
    "title": "Lietuvos šaulių sąjunga yra silpna, korumpuota, politiškai valdoma ir pilna priešo šnipų",
    "lines": [
      "LŠS silpnumas ir",
      "nepatikimumas"
    ],
    "description": "Organizacijos patikimumas ir pajėgumas menkinami jungiant silpnumo, korupcijos, politinės kontrolės bei infiltracijos teiginius.",
    "subtopic": "Institucijų pajėgumas ir patikimumas",
    "secondaryThemes": [
      "security"
    ],
    "actors": [
      "Lietuvos šaulių sąjunga",
      "LŠS"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      55,
      75,
      100,
      135,
      185,
      240,
      305
    ],
    "growth": 60,
    "stance": [
      40,
      37,
      23
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-019-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Lietuvos šaulių sąjunga yra silpna, korumpuota, politiškai valdoma ir pilna priešo šnipų“.",
        "Palaiko"
      ],
      [
        "IR-019-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-019-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Lietuvos šaulių sąjunga yra silpna, korumpuota, politiškai valdoma ir pilna priešo šnipų“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-020",
    "firstSeenAt": "2026-10-13T17:15:00+03:00",
    "theme": "economy",
    "title": "Europos Sąjunga, NATO ir parama Ukrainai išsekino Lietuvą, todėl Klaipėdos žmonėms trūksta išteklių",
    "lines": [
      "Išteklių stoka dėl",
      "sąjungininkų ir paramos"
    ],
    "description": "Išteklių trūkumas Klaipėdoje priežastiniu ryšiu siejamas su Lietuvos tarptautiniais įsipareigojimais ir parama Ukrainai.",
    "subtopic": "Gyventojų aprūpinimas",
    "secondaryThemes": [
      "foreign"
    ],
    "actors": [
      "Europos Sąjunga",
      "NATO",
      "Ukraina"
    ],
    "places": [
      "Klaipėda"
    ],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      85,
      110,
      140,
      185,
      240,
      305,
      375
    ],
    "growth": 67,
    "stance": [
      49,
      30,
      21
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-020-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „Europos Sąjunga, NATO ir parama Ukrainai išsekino Lietuvą, todėl Klaipėdos žmonėms trūksta išteklių“.",
        "Palaiko"
      ],
      [
        "IR-020-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-020-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „Europos Sąjunga, NATO ir parama Ukrainai išsekino Lietuvą, todėl Klaipėdos žmonėms trūksta išteklių“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  },
  {
    "id": "N-021",
    "firstSeenAt": "2026-10-13T20:30:00+03:00",
    "theme": "institutions",
    "title": "„Velarės liaudies respublika“ yra vienintelė vietos jėga, galinti atkurti tvarką ir pasirūpinti savo gyventojais",
    "lines": [
      "Alternatyvi vietinė",
      "valdžia ir tvarka"
    ],
    "description": "Alternatyvi vietinė jėga legitimizuojama teigiant, kad tik ji gali atkurti tvarką ir aprūpinti gyventojus.",
    "subtopic": "Alternatyvios valdžios legitimizavimas",
    "secondaryThemes": [
      "identity",
      "economy"
    ],
    "actors": [
      "Velarės liaudies respublika"
    ],
    "places": [],
    "source": "user_list",
    "status": "confirmed",
    "fixed": true,
    "days": [
      25,
      40,
      65,
      100,
      150,
      210,
      285
    ],
    "growth": 25,
    "stance": [
      37,
      41,
      22
    ],
    "first": "Spalio 13 d.",
    "evidence": [
      [
        "IR-021-1",
        "Spalio 19 · 14:20",
        "Demonstracinis palaikymo pavyzdys: kartojamas ir palaikomas teiginys „„Velarės liaudies respublika“ yra vienintelė vietos jėga, galinti atkurti tvarką ir pasirūpinti savo gyventojais“.",
        "Palaiko"
      ],
      [
        "IR-021-2",
        "Spalio 19 · 12:10",
        "Šiam teiginiui pagrįsti reikėtų patikrinamų šaltinių. Vien jo kartojimas nėra pagrindimas.",
        "Prieštarauja"
      ],
      [
        "IR-021-3",
        "Spalio 18 · 17:05",
        "Diskusijoje cituojamas teiginys „„Velarės liaudies respublika“ yra vienintelė vietos jėga, galinti atkurti tvarką ir pasirūpinti savo gyventojais“. Kokie šaltiniai pateikiami?",
        "Cituoja / klausia"
      ]
    ]
  }
]);

narratives.filter(n=>n.source!=='user_list').forEach(n=>{n.fixed=false;});

const relations=[
  {id:'r1',a:'N-001',b:'N-002',type:'competing',label:'Konkuruoja',x:197,y:281,explanation:'Tas pats kainų pokytis aiškinamas skirtingai: sąmoninga privilegija arba rinkos svyravimais. Tai konkuruojantys priežasčių aiškinimai.',evidence:'„Ar sąskaitas kelia rinkos kaina, ar sprendimas palankus tiekėjams? Palyginkime argumentus.“'},
  {id:'r2',a:'N-001',b:'N-004',type:'related',label:'Giminingi',x:366,y:225,explanation:'Abiejuose pasakojimuose vertinami sprendimai ir jų pagrindimas. Teminis giminingumas nereiškia vienodo priežasties aiškinimo.',evidence:'„Neaišku, kodėl tarifas keičiasi ir kam šis pakeitimas naudingas.“'},
  {id:'r3',a:'N-004',b:'N-005',type:'competing',label:'Konkuruoja',x:565,y:333,explanation:'Pasakojimas apie nepaaiškintus sprendimus gretinamas su argumentu, kad paskelbti duomenys leidžia juos patikrinti.',evidence:'„Sprendimas nepaaiškintas.“ / „Pagrindimas yra paskelbtuose dokumentuose – pažiūrėkime kartu.“'},
  {id:'r4',a:'N-003',b:'N-008',type:'branch',label:'Atšaka',x:518,y:99,explanation:'Bendras pagalbos prieinamumo klausimas susiaurinamas iki regioninių skirtumų. Tai preliminari naratyvo atšaka, kurią dar turi peržiūrėti analitikas.',evidence:'„Parama sunkiai pasiekiama, o regionuose jos prieinamumą dar riboja atstumas iki paslaugų.“'},
  {id:'r5',a:'N-003',b:'N-004',type:'related',label:'Giminingi',x:537,y:211,explanation:'Abu naratyvai remiasi sprendimų ir gyventojų lūkesčių neatitikimu. Ryšys pagrįstas teiginių turiniu, ne bendrais autoriais.',evidence:'„Sąlygų nepavyksta suprasti, todėl nežinome, ar parama mums priklauso.“'},
  {id:'r6',a:'N-004',b:'N-007',type:'branch',label:'Galima atšaka',x:643,y:178,explanation:'Teiginys apie nepakankamą paaiškinimą papildomas nauju motyvu – sąmoningu slėpimu. Šis priežasties pokytis yra kandidato atskyrimo pagrindas.',evidence:'„Informacijos mažai – gal ji sąmoningai nutylima?“'},
  {id:'r7',a:'N-005',b:'N-009',type:'related',label:'Giminingi',x:515,y:433,explanation:'Abu pasakojimai akcentuoja šaltinių tikrinimą ir pagrindžiančių duomenų prieinamumą.',evidence:'„Nuoroda į pirminius duomenis padėtų patikrinti šį nerimą keliantį pranešimą.“'},
  {id:'r8',a:'N-006',b:'N-007',type:'competing',label:'Konkuruoja',x:819,y:168,explanation:'Neapibrėžtumas aiškinamas per skirtingus atsakus: konkrečius pasirengimo veiksmus arba prielaidą apie grėsmės slėpimą.',evidence:'„Užuot spėlioję apie slėpimą, aptarkime, kokius pasirengimo veiksmus galime patikrinti.“'},
  {id:'r9',a:'N-006',b:'N-010',type:'related',label:'Giminingi',x:809,y:374,explanation:'Naratyvus sieja išankstinio pasirengimo ir prevencinių veiksmų idėja skirtingose temose.',evidence:'„Tiek sveikatos, tiek krizių atveju padeda išankstinis planas ir aiškūs veiksmai.“'}
];
relations.push(...[
  {
    "id": "r10",
    "a": "N-011",
    "b": "N-019",
    "type": "related",
    "label": "Giminingi",
    "explanation": "Teiginius sieja gynybinio pajėgumo ir organizacijos patikimumo menkinimas. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r11",
    "a": "N-012",
    "b": "N-016",
    "type": "branch",
    "label": "Galima atšaka",
    "explanation": "Bendras teiginys apie institucijų veikimą prieš piliečius susiaurinamas iki tariamų sąrašų ir žmonių gaudymo. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r12",
    "a": "N-013",
    "b": "N-020",
    "type": "related",
    "label": "Giminingi",
    "explanation": "Abu teiginiai neigiamas pasekmes sieja su išorės veikėjais ir tarptautiniais įsipareigojimais. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r13",
    "a": "N-014",
    "b": "N-021",
    "type": "related",
    "label": "Giminingi",
    "explanation": "Valstybingumo vertinimas gretinamas su alternatyvios vietinės valdžios legitimizavimu. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r14",
    "a": "N-015",
    "b": "N-020",
    "type": "branch",
    "label": "Galima atšaka",
    "explanation": "Bendras aprūpinimo nelygybės pasakojimas papildomas konkrečiu tarptautinių įsipareigojimų kaltinimu. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r15",
    "a": "N-016",
    "b": "N-017",
    "type": "related",
    "label": "Giminingi",
    "explanation": "Teiginius sieja Lietuvos šaulių sąjungai priskiriama prievarta piliečių atžvilgiu. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r16",
    "a": "N-018",
    "b": "N-019",
    "type": "related",
    "label": "Giminingi",
    "explanation": "Skirtingais argumentais menkinamas tos pačios organizacijos legitimumas ir patikimumas. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r17",
    "a": "N-012",
    "b": "N-019",
    "type": "related",
    "label": "Giminingi",
    "explanation": "Bendras institucijų nepatikimumo aiškinimas siejamas su konkrečios organizacijos kritika. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  },
  {
    "id": "r18",
    "a": "N-021",
    "b": "N-015",
    "type": "related",
    "label": "Giminingi",
    "explanation": "Alternatyvios valdžios pažadas pasirūpinti gyventojais gretinamas su pasakojimu apie aprūpinimo nelygybę. Ryšys šiame prototipe yra analitinė hipotezė.",
    "evidence": "Demonstracinis dviejų registre pateiktų teiginių sugretinimas; tiesioginio persidalijimo duomenų nėra."
  }
]);

const viewMeta={overview:{title:'Temų apžvalga',description:'Kas svarbu šiandien. Kas keičiasi. Kokie pasakojimai iškyla.'},map:{title:'Naratyvų žemėlapis',description:'Atraskite pasakojimų ryšius. Atskirai matykite, kas juos palaiko ir kas jiems prieštarauja.'},time:{title:'Raida laike',description:'Sekite naratyvo raidą, įvykių kontekstą ir įrašų pozicijų pokyčius bendrame sraute.'}};
viewMeta.thermometer={title:'Nuotaikų termometras',description:'Turinio komunikacinė kryptis pratybų kontekste. Visas pasirinkto laikotarpio srautas.'};
viewMeta.context={title:'Pratybų kontekstas',description:'Pradinė situacija ir patvirtinti faktai, išsaugomi vieną kartą pratybų pradžioje.'};
icons.context='<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>';
icons.thermometer='<path d="M10 14.5V5a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0Z"/><path d="M12 9v8"/>' ;
viewMeta.platform={title:'Platformos apžvalga',description:'Visos platformos įrašai ir auditoriją įtraukiantys autoriai.'};
icons.platform='<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 9v12M15 9v12"/>';
const navigationOrder=['thermometer','platform','overview','map','time','context'];
const state={view:['overview','map','time','thermometer','context','platform'].includes(location.hash.slice(1))?location.hash.slice(1):'overview',theme:'all',themeScope:'all',period:7,status:'all',sort:'popular',query:'',selected:'N-001',tab:'evidence',relation:null,zoom:1,mapMode:'all',day:null,expanded:null,quickTag:''};
const $=id=>document.getElementById(id);
const live=()=>window.SignalLiveData?.active()===true;
let liveDataInitialized=!window.SignalLiveData;
const themeOf=id=>id==='unassigned'?unassignedTheme:themes.find(t=>t.id===id);
const nar=id=>narratives.find(n=>n.id===id);
const periodDays=n=>Array.from({length:Math.min(state.period,n.days.length)},(_,i)=>Math.max(0,n.days.length-state.period)+i);
const count=n=>n.days.slice(-state.period).reduce((a,b)=>a+b,0);
const sortOptions=Object.freeze({popular:'Populiariausi',least:'Mažiausiai įrašų',newest:'Naujausi',oldest:'Seniausi'});
const firstSeenTime=n=>Date.parse(n.firstSeenAt);
const firstSeenFormatter=new Intl.DateTimeFormat('lt-LT',{timeZone:'Europe/Vilnius',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const firstSeenLabel=n=>Number.isFinite(firstSeenTime(n))?firstSeenFormatter.format(firstSeenTime(n)):'Data nenurodyta';
function sortNarratives(ns){
  return [...ns].sort((a,b)=>{
    let order=0;
    if(state.sort==='newest'||state.sort==='oldest'){
      const aTime=firstSeenTime(a),bTime=firstSeenTime(b);
      if(Number.isFinite(aTime)!==Number.isFinite(bTime))return Number.isFinite(aTime)?-1:1;
      if(Number.isFinite(aTime))order=state.sort==='newest'?bTime-aTime:aTime-bTime;
    }else order=state.sort==='least'?count(a)-count(b):count(b)-count(a);
    return order||count(b)-count(a)||a.id.localeCompare(b.id);
  });
}
const narrativeSortControl=()=>`<label class="narrative-sort"><span>Rikiuoti</span><select data-narrative-sort aria-label="Rikiuoti naratyvus">${Object.entries(sortOptions).map(([value,label])=>`<option value="${value}" ${state.sort===value?'selected':''}>${label}</option>`).join('')}</select></label>`;
const narrativeSortHint=()=>state.sort==='newest'?'Nuo naujausiai iki seniausiai pastebėto':state.sort==='oldest'?'Nuo seniausiai iki naujausiai pastebėto':state.sort==='least'?'Nuo mažiausiai iki daugiausia įrašų':'Nuo daugiausia iki mažiausiai įrašų';
const firstSeenTag=n=>`<time class="narrative-first-seen" ${Number.isFinite(firstSeenTime(n))?`datetime="${esc(n.firstSeenAt)}"`:''} title="${n.is_live?'Ankstyviausias gautas šio naratyvo turinys; visa istorija nežinoma':'Pirmąkart pastebėtas stebimame sraute · demonstracinė data'} · Lietuvos laiku">${n.is_live?'Gautoje imtyje nuo':'Pirmąkart'}: ${esc(firstSeenLabel(n))}</time>`;
// Authored demo media; no original Diaspora photo is implied.
const demoPhotoEvidence=narratives.flatMap(n=>n.evidence).find(e=>Array.isArray(e)&&e[0]==='IR-001');
if(demoPhotoEvidence)demoPhotoEvidence[4]={media:[{kind:'image',thumbnailUrl:'demo/demo-invoice.svg',originalUrl:'demo/demo-invoice.svg',alt:'Demonstracinė sąskaitos iliustracija'}]};
// Explicit synthetic preceding-day counts are supplied by demo/narrative-history.js.
narratives.forEach(n=>{
  const history=window.SignalDemoPreviousDays?.[n.id];
  // Reuse already-authored demo history for the new 10-day window.
  // Keep the concatenated comparison history intact; do not invent older days.
  if(Array.isArray(history)&&history.length>=3){n.days=[...history.slice(-3),...n.days];n.previousDays=history.slice(0,-3);}
  else n.previousDays=history;
});
const previousCount=n=>window.SignalGrowth.compare(n,state.period).previous;
const growthFor=ns=>window.SignalGrowth.aggregate(ns,state.period);
const growthLabel=ns=>window.SignalGrowth.percentLabel(growthFor(ns));
const growthBadge=n=>window.SignalGrowth.badge(n,state.period);
const narrativeTags=n=>[n.subtopic,...(n.actors||[]),...(n.places||[])].filter(Boolean);
const catalogThemes=()=>themes.filter(t=>state.view==='map'||state.themeScope!=='priority'||t.priority);
function ensureMapTheme(){
  if(state.view!=='map')return;
  state.themeScope='all';
  if(!themes.some(t=>t.id===state.theme))state.theme=themes[0].id;
}
const subCount=n=>new Set((n.subnarratives||[]).flatMap(c=>c.evidence.filter(u=>window.SignalLiveData.inPeriod(u,state.period))).map(u=>JSON.stringify([u.source,u.id]))).size;
const visibleNarratives=()=>narratives.filter(n=>(!live()||count(n)>0||subCount(n)>0)&&(state.themeScope!=='priority'||themeOf(n.theme).priority)&&(state.theme==='all'||n.theme===state.theme)&&(state.status==='all'||n.status===state.status||(state.status==='candidate'&&subCount(n)>0))&&(!state.quickTag||narrativeTags(n).includes(state.quickTag))&&(!state.query||`${n.title} ${n.description} ${(n.subnarratives||[]).map(c=>c.title+' '+c.claim_template).join(' ')} ${themeOf(n.theme).name} ${narrativeTags(n).join(' ')} ${(n.secondaryThemes||[]).map(id=>themeOf(id).name).join(' ')}`.toLocaleLowerCase('lt').includes(state.query.toLocaleLowerCase('lt'))));
const total=ns=>live()?new Set(ns.flatMap(n=>[...(n.evidence||[]),...(n.subnarratives||[]).flatMap(c=>c.evidence)].filter(u=>window.SignalLiveData.inPeriod(u,state.period)).map(u=>JSON.stringify([u.source,u.id])))).size:ns.reduce((a,n)=>a+count(n),0);
const statusTag=n=>`<span class="tag ${n.status}">${n.status==='candidate'?'Subnaratyvas':`${icon('check',10)} Registre`}</span>${n.subnarratives?.length?` <span class="tag confirmed">${n.subnarratives.length} subnaratyv. · ${subCount(n)} vnt.</span>`:''}`;
const insightThemeTag=n=>{const t=themeOf(n.theme);return `<span class="insight-theme" style="--theme-color:${t.color};--theme-soft:${t.soft}" aria-label="Bendra tema: ${esc(t.name)}"><span class="theme-dot" aria-hidden="true"></span>${esc(t.name)}</span>`;};
const spark=(values,color='#8393d8',width=60,height=24)=>{const max=Math.max(...values),min=Math.min(...values);const pts=values.map((v,i)=>`${i*width/(values.length-1||1)},${height-((v-min)/(max-min||1))*(height-4)-2}`).join(' ');return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;};

function ensureSelection(){const ns=visibleNarratives();if(ns.length&&!ns.some(n=>n.id===state.selected)){state.selected=[...ns].sort((a,b)=>count(b)-count(a))[0].id;state.relation=null;}if(!ns.some(n=>n.id===state.expanded))state.expanded=null;return ns;}
function setView(view){state.view=view;history.replaceState(null,'',`#${view}`);render();}
function selectNarrative(id,view=state.view,subnarrative=null){if(!nar(id))return;state.subnarrative=subnarrative;if(view==='map'&&themes.some(t=>t.id===nar(id).theme))state.theme=nar(id).theme;state.selected=id;state.expanded=id;state.tab='evidence';state.relation=null;state.day=null;setView(view);if(view==='map')revealNarrative(id);}
function selectTheme(id,view=state.view){if(id!=='all'&&!themeOf(id))return;if(state.themeScope==='priority'&&!themeOf(id)?.priority&&id!=='all')state.themeScope='all';state.theme=id;state.day=null;state.relation=null;state.expanded=null;state.quickTag='';setView(view);}
function selectThemeScope(scope){if(!['all','priority'].includes(scope))return;state.themeScope=scope;if(state.theme!=='all'&&!catalogThemes().some(t=>t.id===state.theme))state.theme='all';state.expanded=null;state.relation=null;state.day=null;render();}
function resetFilters(){Object.assign(state,{theme:'all',themeScope:'all',period:live()?state.period:7,status:'all',sort:'popular',query:'',day:null,expanded:null,mapMode:'all',zoom:1,quickTag:''});render();}
function notify(message){$('toast').textContent=message;$('toast').classList.add('visible');clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('toast').classList.remove('visible'),3800);}

function renderNavigation(){
  $('navigation').innerHTML=navigationOrder.map(key=>[key,viewMeta[key]]).map(([key,v])=>`<button class="nav-link ${state.view===key?'active':''}" data-view="${key}" ${state.view===key?'aria-current="page"':''} title="${v.title}">${icon(key,18)}<span>${v.title}</span>${key==='map'?`<span class="nav-count">${narratives.length}</span>`:''}</button>`).join('');
}
function renderFilters(){
  $('search').value=state.query;$('period').value=String(state.period);$('status').value=state.status;
  $('theme').innerHTML=(state.view==='map'?'':'<option value="all">Visos temos</option>')+catalogThemes().map(t=>`<option value="${t.id}">${t.name}</option>`).join('')+(state.view!=='map'&&state.themeScope==='all'?'<option value="unassigned">Nepriskirti naratyvai</option>':'');$('theme').value=state.theme;
  const chips=[];
  if(state.themeScope==='priority')chips.push('Prioritetinės temos');
  const queueButton=`<button class="shortcut-button queue-shortcut ${state.theme==='unassigned'?'active':''}" data-topic="unassigned" data-target="map">${icon('spark',11)} Nepriskirti naratyvai <span>${narratives.filter(n=>n.theme==='unassigned').length}</span></button>`;
  $('theme-scope').innerHTML=`<div class="theme-scope-toggle" role="group" aria-label="Temų aprėptis">${[['all','Visos temos',themes.length],['priority','Prioritetinės temos',themes.filter(t=>t.priority).length]].map(([scope,label,amount])=>`<button data-theme-scope="${scope}" class="${state.themeScope===scope?'active':''}" aria-pressed="${state.themeScope===scope}">${label}<span>${amount}</span></button>`).join('')}</div><div class="catalog-tools"><span class="catalog-note">${icon('trust',12)} Fiksuotas temų katalogas</span>${queueButton}</div>`;
  if(state.view==='map')$('theme-scope').innerHTML='<div class="catalog-tools"><span class="catalog-note">'+icon('trust',12)+' Fiksuotas temų katalogas</span></div>';
  if(state.theme!=='all')chips.push(themeOf(state.theme).name);
  if(state.status!=='all')chips.push(state.status==='candidate'?'Subnaratyvai':'Naratyvai registre');
  if(state.quickTag)chips.push(`Žyma: ${state.quickTag}`);
  if(state.query)chips.push(`Paieška: ${state.query}`);
  $('active-filter').innerHTML=chips.length?`<span>Analizės pjūvis:</span>${chips.map(s=>`<span class="filter-chip">${esc(s)}</span>`).join('')}<button class="text-button" data-action="clear">Išvalyti ${icon('close',11)}</button>`:'';

}
function renderAnalyzedCount(ns){
  if(live()){
    const items=window.SignalLiveData.units(state);
    $('kpis').innerHTML=`<p class="analyzed-count"><span>Analizuoti įrašai ir komentarai</span><strong>${items.filter(u=>u.analysis_executed).length}</strong><small>iš ${items.length} gautų · per pasirinktą laikotarpį</small></p>`;
    return;
  }
  $('kpis').innerHTML=`<p class="analyzed-count"><span>Analizuojami įrašai</span><strong>${fmt(total(ns))}</strong><small>per pasirinktą laikotarpį</small></p>`;
}
function emptyState(){
  if(live())return window.SignalLiveData.empty(state);
  const t=themeOf(state.theme),unused=t&&t.id!=='unassigned'&&!narratives.some(n=>n.theme===t.id);
  const queue=state.theme==='unassigned';
  const title=unused?'Šioje temoje dar nėra naratyvų':queue?'Nepriskirtų naratyvų nėra':'Šiame pjūvyje naratyvų nerasta';
  const description=unused?'Tema yra fiksuotame kataloge. Jai priskirti naratyvai bus rodomi čia.':queue?'Visi dabartinio registro naratyvai priskirti esamoms bendrinėms temoms. Neaiškaus priskyrimo naratyvai čia lauks analitiko peržiūros.':'Pakeiskite temos ar būsenos filtrą arba įveskite platesnį paieškos žodį.';
  return `<section class="panel empty-state">${icon(unused?t.icon:queue?'check':'search',28)}${t?`<span class="empty-theme-name">${esc(t.name)}</span>`:''}<h2>${title}</h2><p>${description}</p>${state.view==='map'?'':'<button class="button" data-action="clear">Rodyti visas temas</button>'}<small>Tuščias rezultatas nereiškia, kad tokio naratyvo nėra už stebimo srauto ribų.</small></section>`;
}
function renderThemeQueue(ns){
  const pending=ns.filter(n=>n.theme==='unassigned');if(!pending.length)return '';
  return `<section class="panel theme-queue-panel" aria-labelledby="theme-queue-title"><div class="panel-heading"><div><h2 id="theme-queue-title">Nepriskirti naratyvai <span class="compact-count">${pending.length}</span></h2><p>Laukia priskyrimo vienai iš ${themes.length} esamų temų · katalogas nekeičiamas</p></div><button class="text-button" data-topic="unassigned" data-target="map">Atverti eilę ${icon('arrow',12)}</button></div><div class="theme-queue-grid">${pending.map(n=>`<button class="theme-queue-item" data-narrative="${n.id}" data-topic-switch="unassigned" data-target="map"><span class="queue-item-icon">${icon('spark',16)}</span><span><strong>${esc(n.title)}</strong><span>Teminį priskyrimą turi peržiūrėti analitikas.</span><small>${fmt(count(n))} įrašų · demonstracinis pavyzdys</small></span><span class="queue-status">Laukia peržiūros</span></button>`).join('')}</div></section>`;
}
function renderOverview(ns){
  const allCount=total(ns);
  const topicRows=catalogThemes().map(t=>({t,ns:ns.filter(n=>n.theme===t.id)}));
  const activeCount=topicRows.filter(o=>o.ns.length).length;
  const rows=topicRows.map(({t,ns:tn})=>{
    const c=total(tn),pct=allCount?c/allCount*100:0;
    return `<button class="topic-row ${tn.length?'':'topic-row-empty'}" data-topic="${t.id}" data-target="map" aria-label="${esc(t.name)}${t.priority?', prioritetinė tema':''}: ${fmt(c)} įrašų. Atverti žemėlapį."><span class="topic-symbol" style="background:${t.soft};color:${t.color}">${icon(t.icon,16)}</span><span><span class="topic-name">${esc(t.name)}${t.priority?'<span class="topic-priority" title="Prioritetinė stebėsenos tema" aria-hidden="true">◆</span>':''}</span><span class="topic-sub">${tn.length?`Naratyvų: ${tn.length}${tn.some(n=>n.status==='candidate')?' · yra naujų':''}`:'Šiame pjūvyje naratyvų nėra'}</span></span><span><span class="topic-track"><span style="width:${pct}%;background:${t.color}"></span></span><span class="topic-share">${pct.toFixed(1).replace('.',',')} % ${live()?'priskirto turinio':'srauto'}</span></span><span class="topic-count">${fmt(c)}</span><span class="topic-growth">${tn.length?growthLabel(tn):'—'}</span></button>`;
  }).join('');
  return `<div class="overview-layout"><section class="panel"><div class="panel-heading"><div><h2>Temų pulsas <span class="compact-count">${topicRows.length}</span></h2><p>Fiksuotas katalogas · ${activeCount} aktyvios iš ${topicRows.length} temų</p></div><span class="selection-summary">${icon('clock',12)} ${state.period} d.</span></div><div class="topic-list topic-catalog" tabindex="0" role="region" aria-label="Bendrinių temų sąrašas, slinkite norėdami matyti visas temas">${rows||'<p class="topic-empty">Šiame pjūvyje nėra pagrindinėms temoms priskirtų naratyvų.</p>'}</div><div class="panel-foot"><span>◆ Prioritetinė tema · slinkite, kad matytumėte visas</span><button class="text-button view-switch-link" data-view="map">Atverti žemėlapį ${icon('arrow',12)}</button></div></section></div>${renderThemeQueue(ns)}<section class="panel table-panel"><div class="panel-heading"><div><h2>Stebimi naratyvai <span class="compact-count">${ns.length}</span></h2><p>Pasirinkite pasakojimą jo ryšiams ir įrašams tyrinėti</p></div><div class="narrative-list-tools">${narrativeSortControl()}<button class="text-button" data-action="candidates">Tik subnaratyvai ${icon('arrow',12)}</button></div></div>${narrativeTable(ns)}<div class="panel-foot"><span>Palaikymas ir prieštaravimas matuojami įrašų, o ne žmonių lygiu.</span><span>${fmt(allCount)} įrašų</span></div></section>`;
}
function narrativeTable(ns){return `<div class="table-scroll"><table class="narrative-table"><thead><tr><th>NARATYVAS</th><th>TEMA</th><th>BŪSENA</th><th>ĮRAŠAI</th><th>POZICIJŲ SANTYKIS</th><th title="Turinio vienetų kiekio pokytis, ne įsitraukusių narių dalies pokytis">TURINIO POKYTIS</th></tr></thead><tbody>${sortNarratives(ns).map(n=>{const t=themeOf(n.theme);return `<tr><td><button class="narrative-link" data-narrative="${n.id}" data-target="map">${esc(n.title)}</button>${growthBadge(n)}<span class="row-id">${n.id}${n.fixed?' · PRIORITETINIS':''}</span>${firstSeenTag(n)}</td><td><span class="theme-dot" style="background:${t.color}"></span>${t.name}</td><td>${statusTag(n)}</td><td><span class="count-number">${fmt(count(n))}</span></td><td><div class="mini-stack" role="img" aria-label="Palaiko ${stanceLabel(n,0)} procentai, prieštarauja ${stanceLabel(n,1)}, cituoja ${stanceLabel(n,2)}"><span class="support" style="width:${stancePercentages(n)[0]??0}%"></span><span class="oppose" style="width:${stancePercentages(n)[1]??0}%"></span><span class="quote" style="width:${stancePercentages(n)[2]??0}%"></span></div>${n.is_live?window.SignalLiveData.stanceCoverage(n):''}</td><td><span class="table-growth">${growthLabel([n])}</span></td></tr>`;}).join('')}</tbody></table></div>`;}

function graphSubnarratives(ns){
  const parent=ns.find(n=>n.id===state.selected);
  return (parent?.subnarratives||[]).filter(c=>c.status==='confirmed'&&c.evidence.some(u=>window.SignalLiveData.inPeriod(u,state.period)));
}
function graphTitleLines(title,limit=29){
  const lines=[];let line='';
  for(const word of String(title).split(/\s+/)){if(line&&line.length+word.length>limit){lines.push(line);line=word;}else line+=(line?' ':'')+word;}
  if(line)lines.push(line);
  return lines.length>3?[...lines.slice(0,2),lines[2].slice(0,26)+'…']:lines;
}
function selectSubnarrative(parentId,identity){
  if(!nar(parentId)?.subnarratives?.some(c=>c.id===identity))return;
  selectNarrative(parentId,'map',identity);
  const reveal=()=>{const detail=document.getElementById(`subnarrative-${identity}-detail-${parentId}`);if(!detail)return;detail.open=true;detail.querySelector('summary')?.focus({preventScroll:true});detail.scrollIntoView?.({block:'nearest'});};
  if(window.requestAnimationFrame)window.requestAnimationFrame(reveal);else reveal();
}
function graphSVG(ns){
  const branches=graphSubnarratives(ns),hasBranches=branches.length>0;
  const many=ns.length>8,width=hasBranches?1000:many?1320:920,height=hasBranches?Math.max(540,branches.length*118+70,(ns.length-1)*100+100):many?Math.max(700,Math.ceil(ns.length/5)*150+90):540;
  const ordered=[...ns].sort((a,b)=>a.theme.localeCompare(b.theme)||a.id.localeCompare(b.id));
  let otherIndex=0;
  const positions=new Map(ordered.map((n,i)=>{
    if(hasBranches)return [n.id,n.id===state.selected?{x:340,y:height/2}:{x:100,y:80+otherIndex++*100}];
    if(many){const row=Math.floor(i/5),rowSize=Math.min(5,ns.length-row*5),offset=(5-rowSize)*125;return [n.id,{x:160+(i%5)*250+offset,y:90+row*150}];}
    if(ns.length===1)return [n.id,{x:460,y:270}];
    if(ns.length===2)return [n.id,{x:i?650:270,y:270}];
    const angle=-Math.PI/2+i*2*Math.PI/ns.length;
    return [n.id,{x:460+270*Math.cos(angle),y:270+165*Math.sin(angle)}];
  }));
  const ids=new Set(ns.map(n=>n.id));
  const near=state.mapMode==='selected'?new Set([state.selected,...relations.filter(r=>r.a===state.selected||r.b===state.selected).flatMap(r=>[r.a,r.b])]):ids;
  const links=relations.filter(r=>ids.has(r.a)&&ids.has(r.b));
  const edges=links.map((r,i)=>{const a=positions.get(r.a),b=positions.get(r.b),dim=!near.has(r.a)||!near.has(r.b),x=(a.x+b.x)/2,y=(a.y+b.y)/2+(i%3-1)*9,w=r.label.length*5.6+14;return `<g style="${dim?'opacity:.12':''}"><path class="graph-edge ${r.type}" d="M${a.x} ${a.y} L${b.x} ${b.y}"/><g class="edge-label" role="button" tabindex="0" aria-label="${esc(r.label)}: ${esc(nar(r.a).title)} ir ${esc(nar(r.b).title)}. Atverti ryšio pagrindą." data-relation="${r.id}" transform="translate(${x} ${y})"><rect x="${-w/2}" y="-10" width="${w}" height="20" rx="5"/><text text-anchor="middle" y="3">${r.label}</text></g></g>`;}).join('');
  const max=Math.max(...ns.map(count));
  const nodes=ns.map(n=>{const t=themeOf(n.theme),p=positions.get(n.id),r=(many?30:40)+(many?24:25)*Math.sqrt(max>0?count(n)/max:0),selected=n.id===state.selected,dim=!near.has(n.id);return `<g class="graph-node ${selected?'selected':''} ${dim?'dimmed':''}" data-narrative="${n.id}" role="button" tabindex="0" aria-label="${esc(n.title)}. ${fmt(count(n))} įrašų. ${n.status==='candidate'?'Subnaratyvas.':'Registre.'}" transform="translate(${p.x} ${p.y})"><title>${esc(n.title)} · ${esc(t.name)}</title><circle class="outer-ring" r="${r+14}" fill="${t.color}" stroke="${t.color}"/><circle class="node-core" r="${r}" fill="${t.color}" stroke="${t.color}"/>${selected?`<circle class="selection-ring" r="${r+7}" fill="none" stroke="${t.color}"/>`:''}${n.status==='candidate'?`<circle class="graph-candidate" cx="${r*.72}" cy="${-r*.72}" r="5"/>`:''}<text class="node-label" text-anchor="middle" y="${hasBranches?-17:-4}">${(hasBranches?graphTitleLines(n.title,22):n.lines).map((line,i)=>`<tspan x="0" dy="${i?15:0}">${esc(line)}</tspan>`).join('')}</text><text class="node-count" text-anchor="middle" y="${hasBranches?41:29}">${fmt(count(n))} įrašų</text></g>`;}).join('');
  const parent=ns.find(n=>n.id===state.selected),parentPoint=positions.get(state.selected);
  const branchNodes=branches.map((c,i)=>{
    const t=themeOf(parent.theme),x=735,y=(height-branches.length*118)/2+59+i*118;
    const units=c.evidence.filter(u=>window.SignalLiveData.inPeriod(u,state.period));
    const active=state.subnarrative===c.id;
    return `<g class="graph-subnarrative-link"><title>Patvirtinta teminė atšaka; ne tikslaus pagrindinio teiginio atitiktis</title><path class="graph-subnarrative-edge" stroke="${t.color}" d="M${parentPoint.x+65} ${parentPoint.y} C${parentPoint.x+170} ${parentPoint.y},${x-245} ${y},${x-155} ${y}"/></g><g class="graph-subnarrative ${active?'selected':''}" role="button" tabindex="0" data-subnarrative="${esc(c.id)}" data-parent-narrative="${esc(parent.id)}" aria-label="Subnaratyvas: ${esc(c.title)}. ${units.length} turinio vienetų. Atverti įrašus." aria-controls="subnarrative-${esc(c.id)}-detail-${esc(parent.id)}" aria-expanded="${active}" transform="translate(${x} ${y})" style="--sub-color:${t.color};--sub-soft:${t.soft}"><title>${esc(c.title)} · pagrindinis naratyvas: ${esc(parent.title)}</title><rect x="-155" y="-45" width="310" height="90" rx="14"/><text class="subnarrative-label" text-anchor="middle" y="-17">${graphTitleLines(c.title).map((line,j)=>`<tspan x="0" dy="${j?15:0}">${esc(line)}</tspan>`).join('')}</text><text class="subnarrative-count" text-anchor="middle" y="33">Subnaratyvas · ${fmt(units.length)} vnt.</text></g>`;
  }).join('');
  const z=state.zoom;
  return `<svg class="graph-svg ${hasBranches?'graph-svg-subnarratives':''}" ${hasBranches?`style="height:${height}px"`:''} viewBox="0 0 ${width} ${height}" role="group" aria-label="Interaktyvus naratyvų ryšių žemėlapis"><g transform="translate(${width/2*(1-z)} ${height/2*(1-z)}) scale(${z})">${edges}${branchNodes}${nodes}</g></svg>`;
}

function renderMap(ns){return `<div class="map-stack"><section class="panel map-panel"><div class="panel-heading"><div><h2>Pasakojimų ryšiai <span class="compact-count">${ns.length} naratyvų</span></h2><p>Pasirinkus naratyvą, žemėlapyje rodomi jo subnaratyvai. Pasirinkite subnaratyvą jo įrašams atverti.</p></div><div class="segmented" aria-label="Žemėlapio rodinys"><button data-map-mode="all" class="${state.mapMode==='all'?'active':''}" aria-pressed="${state.mapMode==='all'}">Visi ryšiai</button><button data-map-mode="selected" class="${state.mapMode==='selected'?'active':''}" aria-pressed="${state.mapMode==='selected'}">Pasirinkto ryšiai</button></div></div><div class="graph-wrap ${ns.length>8?'graph-wrap-many':''} ${graphSubnarratives(ns).length?'graph-wrap-subnarratives':''}">${graphSVG(ns)}<div class="map-hint">${icon('eye',11)} Apskritimo dydis – įrašų kiekis · kortelė – subnaratyvas</div><div class="graph-controls"><button class="icon-button" data-zoom="out" aria-label="Atitolinti žemėlapį" ${state.zoom<=.75?'disabled':''}>${icon('minus',14)}</button><button class="icon-button" data-zoom="in" aria-label="Priartinti žemėlapį" ${state.zoom>=1.5?'disabled':''}>${icon('plus',14)}</button><button class="icon-button" data-zoom="fit" aria-label="Atkurti žemėlapio mastelį">${icon('fit',14)}</button></div></div><div class="map-legend">${live()?'<span>Patvirtinti naratyvai · brūkšninės linijos – teminės subnaratyvų atšakos</span>':'<div class="legend-group"><span><i class="legend-line"></i>Giminingi</span><span><i class="legend-line competing"></i>Konkuruoja</span><span><i class="legend-line branch"></i>Atšaka</span></div><span><i class="legend-dot" style="background:#d3a657"></i>Subnaratyvas</span>'}</div><div class="graph-topic-legend">${[...themes,unassignedTheme].filter(t=>ns.some(n=>n.theme===t.id)).map(t=>`<button data-topic="${t.id}" class="${state.theme===t.id?'active':''}"><i class="legend-dot" style="background:${t.color}"></i>${t.name}</button>`).join('')}</div><div class="map-caption">Mazgų padėtys scheminės. Linijos žymi teiginių ryšius; jos neįrodo bendro autoriaus ar koordinavimo.</div></section>${renderNarrativeList(ns)}</div>`;}


function revealNarrative(id){
  window.requestAnimationFrame?.(()=>document.getElementById(`narrative-trigger-${id}`)?.scrollIntoView({behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'}));
}
function positionSummary(n){
  return `<span class="narrative-row-positions"><span class="positions-label">Įrašų pozicijos · pasirinktame laikotarpyje</span><span class="row-stance-bar" aria-hidden="true"><span class="support" style="width:${stancePercentages(n)[0]??0}%"></span><span class="oppose" style="width:${stancePercentages(n)[1]??0}%"></span><span class="quote" style="width:${stancePercentages(n)[2]??0}%"></span></span><span class="row-stance-values"><span><i class="support" aria-hidden="true"></i>Palaiko <strong>${stanceLabel(n,0)} %</strong></span><span><i class="oppose" aria-hidden="true"></i>Prieštarauja <strong>${stanceLabel(n,1)} %</strong></span><span><i class="quote" aria-hidden="true"></i>${n.is_live?'Perteikia':'Cituoja'} <strong>${stanceLabel(n,2)} %</strong></span></span>${n.is_live?window.SignalLiveData.stanceCoverage(n):''}</span>`;
}
function renderNarrativeList(ns){
  const sorted=sortNarratives(ns);
  return `<section class="panel narrative-list-panel" aria-labelledby="narrative-list-title"><div class="panel-heading"><div><h2 id="narrative-list-title">${state.theme==='all'?'Stebimi naratyvai':'Temos naratyvai'} <span class="compact-count">${ns.length}</span>${state.theme==='all'?'':insightThemeTag(sorted[0])}</h2><p>${narrativeSortHint()} · pasirinkite naratyvą jo turiniui išskleisti</p></div>${narrativeSortControl()}</div><div class="narrative-list">${sorted.map((n,index)=>{
    const open=state.expanded===n.id;
    return `<article class="narrative-item ${open?'expanded':''} ${state.selected===n.id?'selected':''}" id="narrative-${n.id}"><div class="narrative-summary" data-accordion="${n.id}" role="group" aria-labelledby="narrative-title-${n.id}"><span class="narrative-rank">${String(index+1).padStart(2,'0')}</span><span class="narrative-row-main"><span class="narrative-title-line"><button class="narrative-title-button narrative-row-title" id="narrative-trigger-${n.id}" data-accordion="${n.id}" aria-expanded="${open}" aria-controls="narrative-content-${n.id}"><span id="narrative-title-${n.id}">${esc(n.title)}</span></button>${growthBadge(n)}</span><span class="narrative-row-meta"><span class="narrative-row-id">${n.id}</span>${state.theme==='all'?insightThemeTag(n):''}${statusTag(n)}${n.fixed?'<span class="tag fixed">Prioritetinis</span>':''}</span>${firstSeenTag(n)}</span><span class="narrative-row-count"><strong>${fmt(count(n))}</strong><span>įrašų · ${state.period} d.</span></span>${positionSummary(n)}<button type="button" class="narrative-chevron" data-accordion="${n.id}" aria-expanded="${open}" aria-controls="narrative-content-${n.id}" aria-label="${open?'Suskleisti':'Išskleisti'} naratyvą ${esc(n.title)}">${icon('arrow',16)}</button></div>${open?detailPanel(n,true):`<div id="narrative-content-${n.id}" hidden></div>`}</article>`;
  }).join('')}</div><div class="panel-foot"><span>Įrašų skaičius apima palaikymą, prieštaravimą ir citavimą.</span><span>${fmt(total(ns))} įrašų</span></div></section>`;
}

function stanceStack(n){return `<div class="stance-stack" role="img" aria-label="Palaiko ${stanceLabel(n,0)} %, prieštarauja ${stanceLabel(n,1)} %, cituoja arba klausia ${stanceLabel(n,2)} %"><span class="support" style="width:${stancePercentages(n)[0]??0}%"></span><span class="oppose" style="width:${stancePercentages(n)[1]??0}%"></span><span class="quote" style="width:${stancePercentages(n)[2]??0}%"></span></div><div class="stance-legend"><span><i class="support"></i>Palaiko <b>${stanceLabel(n,0)} %</b></span><span><i class="oppose"></i>Prieštarauja <b>${stanceLabel(n,1)} %</b></span><span><i class="quote"></i>Cituoja <b>${stanceLabel(n,2)} %</b></span></div>`;}
function evidenceUnit(e){return Array.isArray(e)?{id:e[0],dateLabel:e[1],text:e[2],stance:e[3],is_demo:true,kind:'post',sourceUrl:null,media:e[4]?.media||[]}:e;}
function evidenceCard(e,index){
  const unit=evidenceUnit(e),source=window.SignalSourceContent;
  const stance=({support:'Palaiko',oppose:'Prieštarauja',quote:'Cituoja / klausia',unknown:'Pozicija neįvertinta'})[unit.stance]||unit.stance||'Pozicija neįvertinta',stanceClass=stance==='Prieštarauja'?'against':stance==='Palaiko'?'':'quoted';
  return `<article class="evidence-card"><div class="evidence-meta"><span>${unit.kind==='comment'?'Komentaras':'Įrašas'} ${esc(unit.id)}</span><span>${esc(unit.dateLabel||source.date(unit.published_at))}</span></div>${source.body(unit)}<div class="evidence-bottom"><span class="stance-badge ${stanceClass}">${esc(stance)}</span>${unit.is_demo?`<span>Sintetinis įrašas · ${index+1}</span>`:''}</div><div class="source-actions">${source.link(unit)}</div></article>`;
}
function narrativeMetadata(n){
  const secondary=(n.secondaryThemes||[]).map(id=>`<span class="metadata-chip secondary-theme">Papildoma tema: ${esc(themeOf(id).name)}</span>`).join('');
  const subject=n.subtopic?`<button class="metadata-chip" data-quicktag="${esc(n.subtopic)}">Potemė: ${esc(n.subtopic)}</button>`:'';
  const entities=[...(n.actors||[]),...(n.places||[])].filter(value=>value!=='LŠS').map(value=>`<button class="metadata-chip" data-quicktag="${esc(value)}">${esc(value)}</button>`).join('');
  const pending=n.theme==='unassigned'?'<span class="metadata-chip pending-theme">Laukia priskyrimo esamai temai</span>':'';
  return `<div class="narrative-metadata">${subject}${secondary}${entities}${pending}</div>${n.source==='user_list'?'<div class="definition-source">Apibrėžimas iš jūsų pateikto naratyvų sąrašo · registro būsena nėra teiginio faktinis patvirtinimas.</div>':''}`;
}
function detailPanel(n,inline=false){
  if(live())return window.SignalLiveData.detail(n,inline,state,{themeOf,statusTag});
  if(!n)return '';
  const t=themeOf(n.theme);
  const rels=relations.filter(r=>r.a===n.id||r.b===n.id);
  const es=n.evidence.filter(e=>{
    const unit=evidenceUnit(e);
    if(unit.published_at){const date=Date.parse(unit.published_at),end=Date.parse('2026-10-20T00:00:00+03:00');if(!Number.isFinite(date)||date<end-state.period*86400000||date>=end)return false;const day=Number(new Intl.DateTimeFormat('en',{timeZone:'Europe/Vilnius',day:'2-digit'}).format(new Date(date)));return !state.day||day===state.day;}
    const match=unit.dateLabel?.match(/Spalio (\d+)/);return match&&Number(match[1])>=20-state.period&&(!state.day||Number(match[1])===state.day);
  });
  let body='';
  if(state.tab==='evidence'){
    body=`${inline?'':`<h3>Įrašų pozicijos · pasirinktame laikotarpyje</h3>${stanceStack(n)}`}<h3>Reprezentatyvūs įrašai · demo ${state.day?`· spalio ${state.day} d.`:''}</h3><div class="evidence-grid">${es.length?es.map(evidenceCard).join(''):`<div class="evidence-card"><blockquote>Šiam pjūviui išsamaus demonstracinio įrašo nėra. Agreguoti kiekiai rodomi grafike.</blockquote></div>`}</div>${state.day?'<button class="text-button" data-action="clear-detail">Rodyti visus pavyzdžius</button>':''}<div class="detail-caution">Paminėjimas nėra palaikymas. Įrašų pozicijos nepriskiriamos žmonių profiliams. Kandidato apibrėžimas dar gali keistis.</div>`;
  }else if(state.tab==='relations'){
    body=`<h3>Ryšiai su kitais naratyvais</h3><div class="inline-relations-grid">${rels.length?rels.map(r=>{const other=nar(r.a===n.id?r.b:r.a);return `<article class="relation-card ${state.relation===r.id?'selected':''}"><span>${r.label}${r.type==='branch'?' · preliminaru':''}</span><strong>${esc(other.title)}</strong><p>${esc(r.explanation)}</p><blockquote>„${esc(r.evidence)}“</blockquote><small>Sintetinis teiginių sugretinimas · ${r.id.toUpperCase()}</small><br><button class="text-button" data-narrative="${other.id}" data-topic-switch="${other.theme}">Atverti naratyvą ${icon('arrow',11)}</button></article>`;}).join(''):'<p class="detail-description">Šiame prototipe ryšių dar nepažymėta.</p>'}</div><div class="detail-caution">Ryšys aprašo turinio panašumą, skirtumą arba raidą. Tai nėra įrodymas, kad šaltiniai koordinuoja veiksmus.</div>`;
  }else{
    body=`<h3>Apibrėžimo istorija</h3><div class="history-list"><div class="history-item"><small>SPALIO 19 · 16:40</small>${n.status==='candidate'?'Kandidatas paliktas analitiko peržiūrai.':'Patikrinti priskyrimo pavyzdžiai.'}<br>Apibrėžimas v1.0 išlaikytas.</div><div class="history-item"><small>SPALIO 16 · 10:20</small>Papildyti alternatyvių formuluočių ir paneigimų pavyzdžiai.</div><div class="history-item"><small>SPALIO 13 · 08:00</small>${n.id} sukurtas demonstraciniame registre.<br>${n.fixed?'Pažymėtas kaip prioritetinis.':'Pirmasis stebėjimas šiame duomenų rinkinyje.'}</div></div><div class="detail-caution">Pastovus ID išsaugo palyginamumą. Šiame prototipe istoriniai kiekiai neperrašomi keičiant pavadinimą.</div>`;
  }
  const tabs=[['evidence',inline?'Reprezentatyvūs įrašai':'Įrašai',es.length],['relations','Ryšiai',rels.length],['history','Istorija',null]];
  const tabBar=`<div class="detail-tabs" role="tablist" aria-label="Naratyvo informacija">${tabs.map(([key,label,amount])=>`<button role="tab" id="narrative-tab-${n.id}-${key}" aria-selected="${state.tab===key}" aria-controls="narrative-tabpanel-${n.id}" tabindex="${state.tab===key?0:-1}" class="${state.tab===key?'active':''}" data-tab="${key}">${label}${amount===null?'':` <span>${amount}</span>`}</button>`).join('')}</div>`;
  const content=`${tabBar}<div class="detail-body" id="narrative-tabpanel-${n.id}" role="tabpanel" aria-labelledby="narrative-tab-${n.id}-${state.tab}">${body}</div>`;
  if(inline)return `<div class="narrative-expanded" id="narrative-content-${n.id}" role="region" aria-labelledby="narrative-title-${n.id}"><div class="inline-narrative-overview"><div class="inline-definition"><span>NARATYVO APRAŠYMAS <span>· v1.0</span></span><p>${esc(n.description)}</p>${narrativeMetadata(n)}</div><button class="button" data-view="time">${icon('time',13)} Tirti laiko eigą</button></div>${content}</div>`;
  return `<aside class="panel detail-panel" aria-label="Pasirinkto naratyvo detalės"><div class="detail-top"><div class="detail-eyebrow"><span>PASIRINKTAS NARATYVAS</span><span>${n.id}</span></div><div class="detail-theme"><span class="theme-dot" style="background:${t.color}"></span>${t.name}</div><h2 class="detail-title">${esc(n.title)}</h2><div class="detail-tags">${statusTag(n)}${n.fixed?'<span class="tag fixed">Prioritetinis</span>':''}</div><p class="detail-description">${esc(n.description)}</p>${narrativeMetadata(n)}<div class="detail-stats"><div class="detail-stat"><strong>${fmt(count(n))}</strong>įrašų · ${state.period} d.</div><div class="detail-stat"><strong>${rels.length}</strong>turinio ryšiai</div><div class="detail-stat"><strong>v1.0</strong>apibrėžimas</div></div>${firstSeenTag(n)}<div class="detail-actions"><button class="button ${state.view==='time'?'':'primary'}" data-view="${state.view==='time'?'map':'time'}">${icon(state.view==='time'?'map':'time',12)}${state.view==='time'?'Ryšių žemėlapis':'Tirti laiko eigą'}</button></div></div>${content}</aside>`;
}

// Demo fixture weights are apportioned into whole assessed units for each day.
// Real classification must provide counts directly; these are not inferred labels.
function dayStances(n,i){return n.is_live?n.dailyStances[i]:window.SignalCounts.apportion(n.days[i],n.stance);}
function stanceCounts(n){return periodDays(n).reduce((counts,i)=>dayStances(n,i).map((value,k)=>value+counts[k]),[0,0,0]);}
function stancePercentages(n){return window.SignalCounts.categoryShares(stanceCounts(n)).map(p=>p===null?null:Number(p.toFixed(1)));}
const stanceLabel=(n,i)=>stancePercentages(n)[i]===null?'—':stancePercentages(n)[i].toLocaleString('lt-LT');
function timeChart(n){
  const ids=periodDays(n),width=660,height=250,left=38,right=15,top=25,bottom=34,plotW=width-left-right,plotH=height-top-bottom;
  const maxV=Math.max(...ids.map(i=>n.days[i]));const max=window.SignalCounts.axisCeiling(maxV);
  const x=k=>left+(k+.5)*plotW/ids.length;const y=v=>height-bottom-v/max*plotH;
  const series=[0,1,2].map(s=>ids.map((i,k)=>[x(k),y(dayStances(n,i)[s])])) ;
  const grid=window.SignalCounts.axisTicks(max).map(value=>`<line class="chart-grid" x1="${left}" x2="${width-right}" y1="${y(value)}" y2="${y(value)}"/><text class="axis-label" x="${left-9}" y="${y(value)+3}" text-anchor="end">${fmt(value)}</text>`).join('');
  const areas=series.map((points,s)=>{const color=['#697bdf','#d89d83','#c0c8d9'][s];return `<path d="M${points[0][0]} ${height-bottom} ${points.map(p=>`L${p[0]} ${p[1]}`).join(' ')} L${points[points.length-1][0]} ${height-bottom} Z" fill="${color}" opacity="${s===0?.09:.04}"/><polyline fill="none" stroke="${color}" stroke-width="${s===0?2.4:1.8}" stroke-linejoin="round" stroke-linecap="round" points="${points.map(p=>p.join(',')).join(' ')}"/>${points.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="2.7" fill="#fff" stroke="${color}" stroke-width="1.4"/>`).join('')}`;}).join('');
  const firstDay=20-n.days.length,eventIndex=ids.indexOf(16-firstDay);const event=eventIndex>=0?`<line x1="${x(eventIndex)}" x2="${x(eventIndex)}" y1="${top}" y2="${height-bottom}" stroke="#bbc5da" stroke-dasharray="3 4"/><rect x="${x(eventIndex)-61}" y="5" width="122" height="17" rx="4" fill="#f0f3fa"/><text class="chart-event-label" x="${x(eventIndex)}" y="17" text-anchor="middle">Paskelbtas paaiškinimas</text>`:'';
  const days=ids.map((i,k)=>{const day=firstDay+i;return `<g class="chart-day ${state.day===day?'selected':''}" data-day="${day}" role="button" tabindex="0" aria-label="Spalio ${day}: ${n.days[i]} įrašų. Palaiko ${dayStances(n,i)[0]}, prieštarauja ${dayStances(n,i)[1]}, cituoja ${dayStances(n,i)[2]}."><rect x="${left+k*plotW/ids.length}" y="${top}" width="${plotW/ids.length}" height="${plotH+29}" rx="4"/><text class="axis-label" x="${x(k)}" y="${height-10}" text-anchor="middle">Spal. ${day}</text><title>Spalio ${day}: ${n.days[i]} įrašų</title></g>`;}).join('');
  return `<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Naratyvo įrašų pozicijų dinamika">${grid}${event}${areas}${days}</svg>`;
}
function renderTime(ns){
  if(live())return window.SignalLiveData.time(nar(state.selected),ns,state,{themeOf,statusTag,count,sort:sortNarratives,sortControl:narrativeSortControl});
  const n=nar(state.selected),t=themeOf(n.theme);
  return `<div class="time-layout"><div class="time-left">
    <section class="panel">
      <div class="panel-heading"><div><h2>Naratyvo dinamika</h2><p>Įrašų skaičius per dieną bendrame sraute · pasirinkite dieną</p></div><span class="tag fixed">${n.id}</span></div>
      <div class="chart-legend"><span><i class="support"></i>Palaiko</span><span><i class="oppose"></i>Prieštarauja</span><span><i class="quote"></i>Cituoja / klausia</span></div>
      <div class="time-chart">${timeChart(n)}</div>
      <div class="chart-note">${icon('eye',12)}${state.day?`Spalio ${state.day} d. · ${fmt(n.days[state.day-(20-n.days.length)])} įrašų.`:'Įvykio žyma suteikia kontekstą; sutapimas laike neįrodo priežasties.'}</div>
      <div class="timeline-event"><span class="event-date">SPAL. 16</span><span class="event-dot"></span><div><strong>Paskelbtas viešas paaiškinimas</strong><span>Sintetinis kontekstinis įvykis, pažymėtas analitiko.</span></div></div>
      <div class="timeline-event"><span class="event-date">SPAL. 19</span><span class="event-dot" style="background:${t.color}"></span><div><strong>${fmt(n.days[n.days.length-1])} naratyvo paminėjimų per dieną</strong><span>Bendras stebimas srautas · demonstraciniai duomenys.</span></div></div>
    </section>
    <section class="panel"><div class="panel-heading"><div><h2>Pakeisti tiriamą naratyvą</h2><p>${narrativeSortHint()} · temos ir laikotarpio filtrai išliks</p></div>${narrativeSortControl()}</div><div class="topic-list">${sortNarratives(ns).filter(o=>o.id!==n.id).slice(0,4).map(o=>`<button class="topic-row" data-narrative="${o.id}" style="grid-template-columns:25px 1fr auto"><span class="theme-dot" style="background:${themeOf(o.theme).color};height:7px;width:7px"></span><span class="topic-name">${esc(o.title)}</span><span class="topic-count">${fmt(count(o))} ${icon('arrow',12)}</span></button>`).join('')||'<p class="detail-description" style="padding-bottom:15px">Šiame pjūvyje yra tik vienas naratyvas. Pasirinkite kitą temą viršuje.</p>'}</div></section>
  </div></div>`;
}

function render(){
  if(!liveDataInitialized)return;
  window.SignalGrowth.hide();
  ensureMapTheme();
  const ns=ensureSelection();renderNavigation();renderFilters();renderAnalyzedCount(ns);
  const meta=viewMeta[state.view];$('page-title').textContent=meta.title;$('page-description').textContent=meta.description;$('breadcrumb').textContent=meta.title;
  if(live()&&state.view==='platform')$('page-description').textContent='Gauto turinio ir sąveikų apžvalga · duomenų aprėptis nurodyta žemiau.';
  const thermometer=state.view==='thermometer',contextView=state.view==='context',platformView=state.view==='platform';
  document.body.classList.toggle('platform-view',platformView);
  document.body.classList.toggle('thermometer-view',thermometer);
  document.body.classList.toggle('context-view',contextView);
  $('analysis-context-note').innerHTML=live()?window.SignalLiveData.note():window.SignalExerciseContext.statusMarkup();
  const metrics=window.SignalMetricsContext.get();
  const hasAudience=metrics.audience.status==='known'&&ns.every(n=>n.exercise_id===metrics.exercise_id);
  if(!live()&&['overview','map','time'].includes(state.view)&&!hasAudience)$('analysis-context-note').innerHTML+=`<p>${metrics.audience.status==='zero'?'Pratybų auditorija tuščia.':'Trūksta šio srauto konkrečių pratybų auditorijos duomenų.'} Auditorijos procentai ir augimo ženkliukai nevertinami; turinio kiekiai ir jų pokytis rodomi atskirai.</p>`;
  $('view').innerHTML=platformView?'<div id="platform-overview-root"></div>':contextView?'<div id="exercise-context-root"></div>':thermometer?'<div id="thermometer-root"></div>':live()&&state.view==='overview'?renderOverview(ns):!ns.length?emptyState():state.view==='overview'?renderOverview(ns):state.view==='map'?renderMap(ns):renderTime(ns);
  if(live()&&['overview','map'].includes(state.view))$('view').innerHTML+=window.SignalLiveData.candidatePanel(state)+window.SignalLiveData.registryPanel(state);
  const period=live()?window.SignalLiveData.range():state.period;
  if(platformView)window.SignalPlatformOverview.mount($('platform-overview-root'),period);
  if(contextView)window.SignalExerciseContext.mount($('exercise-context-root'));
  if(thermometer)window.SignalThermometer.mount($('thermometer-root'),period);
  if(live())window.SignalLiveData.decorate();
  document.title=`${meta.title} · Signalas`;
}
function selectRelation(id,target){
  const r=relations.find(v=>v.id===id);if(!r)return;
  if(![r.a,r.b].includes(state.selected))state.selected=r.a;
  state.tab='relations';state.relation=id;state.expanded=state.selected;
  if(target)state.view=target;
  history.replaceState(null,'',`#${state.view}`);render();if(state.view==='map')revealNarrative(state.selected);
}
function exportData(){
  if(live()){
    const rows=[['Tikri duomenys · paskyrai matoma imtis'],['ID','Tipas','Data','Tekstas','Originalo nuoroda','Naratyvas','Pozicija'],...window.SignalLiveData.units(state).map(u=>[u.id,u.kind,u.published_at,u.text,u.sourceUrl||u.parentSourceUrl||'',(u.narrative_ids||[]).join(' | '),(u.narrative_analysis?.matches||[]).map(m=>m.type_id+': '+m.stance).join(' | ')])];
    const csv='\uFEFF'+rows.map(row=>row.map(value=>'"'+String(value).replace(/"/g,'""')+'"').join(';')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download='signalas-diaspora.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;
  }
  const ns=visibleNarratives();const rows=[['Demonstraciniai duomenys – Signalas'],['Laikotarpis',`2026-10-${20-state.period}–2026-10-19`],['ID','Naratyvas','Pirmąkart pastebėtas (ISO 8601)','Pagrindinė tema','Potemė','Papildomos temos','Minimi veikėjai','Vietovės','Apibrėžimo šaltinis','Būsena','Įrašai','Palaiko %','Prieštarauja %','Cituoja %'],...sortNarratives(ns).map(n=>[n.id,n.title,n.firstSeenAt||'',themeOf(n.theme).name,n.subtopic||'',(n.secondaryThemes||[]).map(id=>themeOf(id).name).join(' | '),(n.actors||[]).join(' | '),(n.places||[]).join(' | '),n.source==='user_list'?'Naudotojo sąrašas':'Demonstracinis pavyzdys',n.status==='candidate'?'Kandidatas':'Registre',count(n),...stancePercentages(n)])];
  const csv='\uFEFF'+rows.map(row=>row.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(';')).join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='signalas-demo.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('Pasirinkto pjūvio demonstraciniai duomenys eksportuoti į CSV.');
}

document.addEventListener('click',event=>{
  const target=event.target.closest('[data-theme-scope],[data-view],[data-topic],[data-subnarrative],[data-narrative],[data-accordion],[data-quicktag],[data-tab],[data-relation],[data-zoom],[data-map-mode],[data-action],[data-day]');
  if(!target||target.disabled)return;
  const d=target.dataset;
  if(d.themeScope){selectThemeScope(d.themeScope);document.querySelector(`[data-theme-scope="${d.themeScope}"]`)?.focus({preventScroll:true});}
  else if(d.view)setView(d.view);
  else if(d.topic)selectTheme(d.topic,d.target||state.view);
  else if(d.subnarrative)selectSubnarrative(d.parentNarrative,d.subnarrative);
  else if(d.narrative){if(d.topicSwitch){if(state.themeScope==='priority'&&!themeOf(d.topicSwitch)?.priority)state.themeScope='all';state.theme=d.topicSwitch;state.status='all';state.query='';state.quickTag='';}selectNarrative(d.narrative,d.target||state.view);}
  else if(d.quicktag){state.quickTag=state.quickTag===d.quicktag?'':d.quicktag;if(state.view!=='map')state.theme='all';state.expanded=null;state.day=null;render();}
  else if(d.accordion){if(state.expanded===d.accordion){state.expanded=null;render();}else selectNarrative(d.accordion,'map');document.getElementById(`narrative-trigger-${d.accordion}`)?.focus({preventScroll:true});}
  else if(d.tab){state.tab=d.tab;render();document.querySelector(`[data-tab="${state.tab}"]`)?.focus({preventScroll:true});}
  else if(d.relation)selectRelation(d.relation,d.target);
  else if(d.zoom){state.zoom=d.zoom==='fit'?1:Math.max(.75,Math.min(1.5,state.zoom+(d.zoom==='in'?.15:-.15)));render();}
  else if(d.mapMode){state.mapMode=d.mapMode;render();}
  else if(d.day){state.day=live()?d.day:Number(d.day);state.tab='evidence';render();}
  else if(d.action==='clear')resetFilters();
  else if(d.action==='clear-detail'){state.day=null;render();}
  else if(d.action==='candidates'){state.status=state.status==='candidate'?'all':'candidate';render();}
});
document.addEventListener('change',event=>{
  if(!event.target.matches('[data-narrative-sort]')||!Object.hasOwn(sortOptions,event.target.value))return;
  state.sort=event.target.value;render();document.querySelector('[data-narrative-sort]')?.focus({preventScroll:true});
});
document.addEventListener('keydown',event=>{
  if(event.target.matches('[role="tab"]')&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
    event.preventDefault();const tabs=['evidence','relations','history'],i=tabs.indexOf(state.tab);
    state.tab=event.key==='Home'?tabs[0]:event.key==='End'?tabs[2]:tabs[(i+(event.key==='ArrowRight'?1:2))%3];
    render();document.querySelector(`[data-tab="${state.tab}"]`)?.focus({preventScroll:true});return;
  }
  if((event.key==='Enter'||event.key===' ')&&event.target.matches('g[role="button"]')){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
  if(!['thermometer','context','platform'].includes(state.view)&&event.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){event.preventDefault();$('search').focus();}
});
$('search').addEventListener('input',event=>{state.query=event.target.value;render();});
$('period').addEventListener('change',event=>{state.period=Number(event.target.value);state.day=null;render();});
$('theme').addEventListener('change',event=>selectTheme(event.target.value));
$('status').addEventListener('change',event=>{state.status=event.target.value;state.day=null;render();});
$('reset-button').addEventListener('click',resetFilters);
$('export-button').addEventListener('click',exportData);
$('help-button').addEventListener('click',()=>$('help-dialog').showModal());
$('close-help').addEventListener('click',()=>$('help-dialog').close());
$('start-demo').addEventListener('click',()=>$('help-dialog').close());
document.querySelector('.brand').addEventListener('click',event=>{event.preventDefault();resetFilters();setView('overview');});
window.addEventListener('hashchange',()=>{const v=location.hash.slice(1);if(viewMeta[v]){state.view=v;render();}});
$('search-icon').innerHTML=icon('search',14);$('calendar-icon').innerHTML=icon('calendar',13);$('reset-button').innerHTML=icon('reset',14);$('help-button').innerHTML=icon('help',17);$('export-button').innerHTML=icon('download',14)+'Eksportuoti';
function prepareNarrativeAnalysisInput(unit){
  return {...window.SignalExerciseContext.analysisInput(unit),analysis_kind:'narratives',allow_new_narratives:true,
    theme_catalog:themes.map(t=>({id:t.id,name:t.name})),
    narrative_registry:live()?window.SignalLiveData.get().registry:null,
    candidate_policy:live()?window.SignalLiveData.get().candidate_policy:null,
    narrative_policy:'Aptikti galima ir pradiniame aprašyme nenumatytus naratyvus. Naują tipą tvirtina administratorius; kiekvienam teiginiui reikia atskiros ištraukos ir pozicijos. Temų katalogas nekeičiamas. Naratyvo tipas nenulemia termometro krypties.'};
}
window.addEventListener('signalas:context-saved',async()=>{
  if(live()){try{applyLiveData(await window.SignalLiveData.syncContext());window.SignalPlatformOverview.invalidate?.();window.SignalThermometer.invalidate?.();render();}catch(error){notify(error.message);}return;}
  const note=$('analysis-context-note');if(note)note.innerHTML=window.SignalExerciseContext.statusMarkup();
});
window.addEventListener('signalas:metrics-context',()=>{if(state.view!=='context')render();});
window.SignalDemo={prepareAnalysisInput:prepareNarrativeAnalysisInput,state,themes,narratives,relations,visibleNarratives,narrativeTags,count,sortNarratives,firstSeenTime,previousCount,growthFor,dayStances,stanceCounts,stancePercentages,evidenceCard,setView,selectTheme,selectThemeScope,selectNarrative,selectSubnarrative,selectRelation,resetFilters,render};
window.SignalDemo.refreshLive=(data,{preserveDay=false}={})=>{applyLiveData(data);window.SignalPlatformOverview.invalidate();window.SignalThermometer.invalidate();if(!preserveDay)state.day=null;if(state.view==='thermometer'&&$('thermometer-root')){window.SignalThermometer.refresh($('thermometer-root'),window.SignalLiveData.range());return;}if(state.view!=='context')render();};
function applyLiveData(data){
  narratives.splice(0,narratives.length,...data.narratives);
  relations.splice(0,relations.length,...data.relations);
  state.period=data.days.length;
  window.SignalLiveData.periodControl();
}
if(window.SignalLiveData){
  $('view').innerHTML='<section class="panel platform-loading" role="status">Įkeliami duomenys…</section>';
  window.SignalLiveData.ready.then(data=>{if(data.mode==='live')applyLiveData(data);liveDataInitialized=true;render();}).catch(error=>{
    renderNavigation();$('view').innerHTML=`<section class="panel empty-state" role="alert"><h2>Duomenų įkelti nepavyko</h2><p>${esc(error.message)}</p></section>`;
  });
}else render();
