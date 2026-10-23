# Signalas · Vercel ir Neon

## Dabartinis veikimo būdas

Pagrindinė aplikacija: https://signalas-ecru.vercel.app/. Python API (`api/index.py`, `cloud_api.py`) veikia Vercel; visi nuolatiniai įrašai, komentarai, medijos metaduomenys, pratybų kontekstas, datos, analizės rezultatai ir surinkimo būsena saugomi Neon Postgres. Naršyklėje nenaudojamas localStorage ar IndexedDB; prisijungimui naudojamas tik Secure / HttpOnly / SameSite sesijos slapukas.

„Atnaujinti duomenis“ surenka visą autorizuotai paskyrai matomą srautą ir jos profilį, ne visą Diasporos serverį. Pasikartojantys paspaudimai neleidžia paleisti lygiagrečių rinkimų (duomenų bazės lease). Rinkimas vykdomas tik rankiniu būdu; ankstesnė vietinė kasvalandinė automatika sustabdyta. Filtrų ir stebėjimo būsenos užklausos tik skaito duomenų bazę. Po sėkmingo rankinio surinkimo automatiškai sudaroma analizės eilė; ją tęsia autentifikuota aplikacija.

Vercel **Production** paslaptys: `OPENAI_API_KEY`, `OPENAI_MODEL` (nenustačius naudojamas `openai_analysis.DEFAULT_ANALYSIS_MODEL`), `DATABASE_URL` (valdo Neon integracija), `SIGNALAS_ACCESS_PASSWORD` (bent 16 ženklų, atskiras aplikacijos prieigos slaptažodis), `DIASPORA_BASE_URL`, `DIASPORA_USERNAME`, `DIASPORA_PASSWORD`. Nieko nevadinkite NEXT_PUBLIC_ ar VITE_. Kiekvienas API turinio ir medijos skaitymas tikrina prisijungimą; keičiantiems veiksmams papildomai reikia tos pačios kilmės ir CSRF. Be prieigos slaptažodžio API užsidaro, o demonstraciniai duomenys neįjungiami automatiškai.

Duomenų bazėje `signalas_fetches` saugo surinkimų kopijas, `signalas_content` – naujausius turinio vienetus, `signalas_state` – kontekstą, datas ir analizės/būsenos duomenis; `signalas_jobs` valdo rinkimo blokavimą. Kontekstas išsaugomas vieną kartą, ir lygiagretūs bandymai jo neperrašo. Originalūs medijos adresai saugomi kaip metaduomenys; prieigos reikalaujančios nuotraukos perduodamos tik prisijungus, jų failai diske nekaupiami.

Vercel funkcijos trukmė – iki 300 s. Viršijus šią vykdymo ribą ankstesnė sėkminga kopija lieka duomenų bazėje; blokavimas baigia galioti po 6 min. Bendras įrašų skaičiaus limitas netaikomas. Ilgalaikiams dideliems rinkimams vėliau gali reikėti užduočių eilės; atskiras mokamas worker ar planas dabar nekuriamas.

## Autorių reitingas

80 balų už skirtingus autorinius įrašus, 15 už kitų paskyrų komentarus ir 5 už persidalijimus. Kiekviena dalis normalizuojama pagal didžiausią tinkamų autorių kiekį pasirinktame laikotarpyje; reikia bent trijų skirtingų autorinių įrašų. Organizacinės paskyros atmetamos pagal patvirtintus metaduomenis arba išplėstus pavadinimo požymius (žiniasklaida, verslai, institucijos, politinės, ne pelno, bendruomeninės ir kitos įstaigos). Tai euristika, ne tapatybės patvirtinimas. Vien vietovardis nėra organizacijos įrodymas. Formulė ir apribojimai aprašyti `docs/METRICS.md`. Duomenų bazės schema nekeičiama.

## Standartizuotas naratyvų registras (vietiniai pakeitimai, 2026-10-23)

Įtrauktas naudotojo Excel registras: 35 tipai, 15 nekintamų temų, priskyrimo / atmetimo kriterijai ir formuluočių atitikmenys. Live žemėlapis rodo patvirtintus tipus, jų pratybų atmainas ir atskiras įrašų / komentarų pozicijas; kandidatai rodomi atskirai, tik pasiekę bandomuosius sklaidos slenksčius. Senieji `N-…` ID automatiškai neperrašomi. Bendri kiekiai yra unikalių šaltinio vienetų aibė; nežinomos pozicijos iš procentų vardiklio išimtos.

[Vertinimo sutartis, kandidatų ribos, administratoriaus sprendimai ir testai](docs/NARRATIVE_REGISTRY.md). Sprendimų saugojimas paruoštas esamai Neon bazei; šios užduoties metu produkciniai duomenys nekeisti, AI užklausos nevykdytos. Automatinė teksto analizė po surinkimo prijungta, kaip aprašyta žemiau. Medijos supratimas dar neprijungtas.

## Analizė po duomenų surinkimo

Paspaudus „Atnaujinti duomenis“, sėkmingai surinkti įrašai ir komentarai išsaugomi Neon, o naujas arba pasikeitęs turinys patenka į teksto analizės eilę. Viena užklausa vertina vieną turinio vienetą ir iškart išsaugo naratyvų bei termometro rezultatą. Bendro kiekio limito nėra. Galiojantys rezultatai pakartotinai neskaičiuojami; pakeitus tekstą / diskusijos kontekstą, pratybas, taisykles, registrą arba modelį reikia naujo vertinimo. Pirmas surinkimas po šio atnaujinimo gali pervertinti ankstesnį rinkinį ir naudoti API kreditus.

Eilę tęsia atidaryta, prisijungusi aplikacija. Ją uždarius, naujos užduotys nebepaleidžiamos; grįžus nebaigta eilė tęsiama iš Neon. Tai nėra nepriklausomas nuolat veikiantis worker. Datos keitimas nieko nerenka ir nepradeda naujos eilės. Pasibaigus kreditams, nutrūkus ryšiui ar negavus tinkamo rezultato, eilė sustoja, lemputė tampa oranžinė. Ištaisius priežastį, mygtukas „Atnaujinti duomenis“ leidžia bandyti iš naujo. Neužbaigtos HTTP užklausos rezultatas gali būti nežinomas: pakartojimas po proceso nutrūkimo gali turėti papildomą API kainą; sėkmingai Neon įrašyti vertinimai nekartojami.

Naudojamas esamas Responses API su `store:false`, tik tekstas. Nuotraukos, garsas ir vaizdo įrašai automatiškai neinterpretuojami; toks termometro turinys lieka peržiūrai. Visos eilės, vertinimų ir paslaugų būsenos laikomos esamoje Neon `signalas_state` lentelėje, schema nekeičiama. API tęsimui reikia prisijungimo, leistinos kilmės ir CSRF.

## Ankstesnės vietinės versijos dokumentacija

Žemiau pateiktos vietinės komandos išsaugotos ankstesnės versijos priežiūrai. Jos nėra dabartinės Vercel aplikacijos vykdymo ar saugojimo mechanizmas. Ankstesnės vietinės kopijos automatiškai netrinamos.

# Signalas · vietinė Python versija

## Vercel peržiūra

`vercel.json` publikuoja tik `dist/` kaip statinę demonstracinę peržiūrą (Framework: Other, Output Directory: dist, be build komandos). Du perrašymo adresai aiškiai įjungia demonstracinį režimą ir sustabdyto srauto indikatorių. Tai nėra tikrų Diasporos duomenų serveris. Vietinis Python serveris ir jo API lieka nepakeisti.

Į Vercel nekelkite `.env`, `var/`, privačių įrašų ar prisijungimo duomenų. Tikro srauto talpinimui reikėtų atskiros autorizuotos serverio integracijos ir privataus duomenų saugojimo; ši peržiūra jų neįjungia.

## Tikri duomenys ir visos platformos aprėptis

Sąsaja dabar gali veikti tikrų duomenų režimu (`var/dashboard-mode.json`, `mode: live`). Demonstraciniai kiekiai ir ryšiai šiame režime nerodomi. Laikotarpis „Nuo–Iki“ pasirenkamas kalendoriuje ir abi datos išsaugomos atskirai nuo rinkinio; turima imtis ar naujas importas jos nekeičia. AI rezultatai susieti su konkrečiu turiniu ir pradiniu kontekstu; pakeitus vieną jų, senas rezultatas nenaudojamas.

**Dabartinė asmeninio srauto imtis nėra visa Diasporos platforma.** Pilnam pasirinkto intervalo turiniui paruoštas administratoriaus eksportas ir jo importas, be dalyvių / kontaktų filtro:

```sh
python3 integrations.py collect --export /secure/signalas-export.json
```

Tikslūs prieigos patikros rezultatai, administratoriaus paleidimo komanda, aprėptis ir likusios ribos: [docs/COLLECTION.md](docs/COLLECTION.md). Eksportuotojas dar nepaleistas tikroje serverio Rails aplinkoje. Iki administratoriaus suteikto eksporto sąsaja aiškiai rodo nepilną aprėptį.

Laikotarpio filtras: **kalendoriaus intervalas „Nuo–Iki“**, be fiksuotų trukmių tikrų duomenų režime. Abi dienos įtraukiamos Lietuvos laiku. Visos skiltys naudoja tą patį intervalą, kuris išlieka po atnaujinimo (`var/dashboard-period.json`). Keičiant datas tik filtruojamas jau surinktas vietinis rinkinys: rinkimas iš Diasporos ir AI analizė nepaleidžiami. Naujas turinys gaunamas atskiru kasvalandiniu procesu. Jei pasirinktas intervalas neturi surinktų duomenų, rodoma tuščia būsena. Ankstesnis trukmės ir pabaigos pasirinkimas perkeliamas vieną kartą; demonstracinių failų senieji trukmės API palikti suderinamumui.

Tikro turinio užklausos: `GET /api/platform/overview?start_date=2026-10-12&end_date=2026-10-21` ir `GET /api/thermometer?start_date=2026-10-12&end_date=2026-10-21`. `POST /api/dashboard/period` su abiem datomis išsaugo tik pasirinkimą; nepakeičia surinktos imties, pratybų konteksto ar vertinimų. Laikotarpis apriboja paskelbimo datą, o sąveikų skaitikliai ir toliau yra bendri įrašo skaitikliai.

## Atnaujinimas kas valandą

Aktyvi „Codex“ užduotis „Kas valandą atnaujinti Signalo duomenis“ kas valandą vykdo `python3 integrations.py collect-sample`, be papildomos AI analizės. Kompiuteris ir „Codex“ turi veikti, užduotis turi turėti tinklo prieigą. Antra lygiagreti rinkimo užduotis nepaleidžiama. Nesėkmė nepakeičia paskutinės sėkmingos imties. Naršyklė kas minutę bei grįžus į skirtuką patikrina vietinę kopiją ir parodo pasikeitimus; laikotarpis ir filtrai išlieka.

2026-10-21 atnaujinimas: 9 unikalūs įrašai (įskaitant 3 savo profilio), 104 komentarai, 3 medijos metaduomenų elementai. Spalio 15–21 intervale yra 7 įrašai; 2 įrašai paskelbti spalio 14 d.

## Srauto būsenos lemputė

Šoniniame meniu palikta tik kompaktiška indikacija. Žalia „Stebimas srautas“ reiškia, kad yra ne senesnė nei 90 min. vietinė kolekcija ir nėra užfiksuoto neišspręsto rinkimo ar AI API sutrikimo. Oranžinė „Srauto stebėjimas sustabdytas“ rodoma po rinkimo klaidos, viršijus kasvalandinio rinkimo 30 min. toleranciją, negalint pasiekti vietinio serverio / naršyklei netekus ryšio, arba gavus AI API prieigos, ryšio, kvotos ar dažnio klaidą. Priežastis pateikiama tik užvedus pelę; atskiro informacinio bloko nėra. Siaurame ekrane lieka lemputė su prieinama būsenos žyma.

`monitoring.py` saugo tik dabartinę atskirą rinkimo ir OpenAI būseną, laiko žymą bei iš anksto apibrėžtą priežasties kodą privačiuose `var/*-status.json`. Neįrašomi raktai, žinutės ar neapdoroti API atsakymai. `GET /api/monitoring/status` ir naršyklės patikra kas minutę nesiunčia užklausų į Diasporą ar OpenAI. Senas turinys, pasirinktos datos ir pratybų kontekstas nepakeičiami. `already_running` nėra klaida.

Kreditų / naudojimo limito trūkumas nustatomas tik gavus tikrą atitinkamą OpenAI klaidą, pagal [oficialų klaidų aprašą](https://developers.openai.com/api/docs/guides/error-codes). Likęs kredito balansas automatiškai netikrinamas; AI analizė ir toliau vykdoma tik aiškiai paleista. Sėkmingas Diasporos rinkimas arba modelių sąrašo GET nepanaikina nustatyto AI kvotos sutrikimo. Jį patvirtintai atstato sėkminga analizės API užklausa. Testai naudoja tik dirbtinius API atsakymus, be mokamų užklausų.

## OpenAI API ryšio patikra

Jau paruoštos aiškiai paleidžiamos jungtys:

```sh
python3 configure_secrets.py diaspora --web
python3 integrations.py check-openai
python3 integrations.py ai-test
python3 integrations.py collect-sample
python3 integrations.py analyze --limit 1 --context var/exercise-context.json
```

`configure_secrets.py diaspora --web` išveda vienkartinį vietinės formos adresą. Atverkite jį, įrašykite slaptažodį ir išsaugokite. Forma klausosi tik 127.0.0.1, turi vienkartinį slaptą kelią ir CSRF formos žymą, neišveda slaptažodžio ir po sėkmingo išsaugojimo arba 15 minučių sustoja. Alternatyva: `python3 configure_secrets.py diaspora` terminale paslėptai įveda tą pačią reikšmę.

`collect-sample` vieną kartą prisijungia su atskirais `DIASPORA_BASE_URL`, `DIASPORA_USERNAME`, `DIASPORA_PASSWORD` nustatymais. Slapukai lieka tik proceso atmintyje. Nuskaitomi visi prisijungusiai paskyrai matomo srauto ir jos profilio puslapiai be bendro įrašų limito. Dublikatai sujungiami pagal šaltinio GUID, paimami visi detalėse pateikti komentarai. Tai nėra visas serveris. Pilnos įrašo detalės skaitomos atskirai, nes sraute yra tik paskutiniai trys komentarai. Originalo nuoroda imama iš šaltinio HTML canonical / og:url metaduomenų; jei jos nėra, nuoroda nekuriama iš ID. Komentarai neperima pirminio įrašo nuotraukų.

Rezultatai laikomi privačiame `var/diaspora-latest.json`, importuojami į esamą SQLite ir tampa prieinami per `/api/posts`. Pakartotinis importas ankstesnių įrašų neperrašo. JSON momentinė kopija turi naujausius gautus skaitiklius; ji nėra pilna istorija. Esamas importuoto turinio indikatorius atsinaujina perkrovus puslapį. Be patvirtinto pratybų susiejimo `exercise_id` ir auditorija lieka nežinomi. Vien paskyrai matomų įrašų negalima pateikti kaip visos platformos turinio.

`ai-test` per OpenAI Responses API pateikia tik sintetinį sakinį ir tikrina struktūruotą atsakymą. `OPENAI_MODEL` numatyta `gpt-6.1-sol` su vidutiniu mąstymo lygiu: tai kokybės ir kainos santykio pradinis pasirinkimas bendrai tekstinei naratyvų ir termometro analizei, ne empiriškai patvirtintas geriausias modelis. Dabartinis vienas AI kvietimas vertina abi sritis, todėl modelio nustatymas joms bendras. `analyze` aiškiai paleidžiamas ir apsiriboja 1–5 gautais turinio vienetais. API užklausos mokamos pagal paskyros sąlygas, AI analizė automatiškai nevykdoma.

Pradinio konteksto failo formatas sutampa su naršyklėje išsaugotu objektu: `initialSituation`, `confirmedFacts`, neprivalomas `nameMappings`. CLI pats naršyklės localStorage neskaito ir jo neperrašo. Nepateikus konteksto arba esant neperžiūrėtai medijai, termometro kategorija lieka `needs_review`. Bandymas analizuoja tik tekstą ir ankstesnę diskusiją; paveikslėlių URL nėra paveikslėlių analizė, o vaizdo ir garso atpažinimas šiame etape neprijungti.

AI pasiūlymai validuojami pagal fiksuotą temų ir naratyvų katalogą. Naujas naratyvas lieka pasiūlymu, automatiškai nekuriamas registre. Pradiniai pavadinimai ir šaltinio nuoroda išlaikomi. `var/openai-analysis-pilot.json` bei `var/openai-test.json` nėra automatiškai pritaikomi demonstraciniams vaizdams. `store:false` nurodomas API užklausoje; tai savaime nekeičia visų OpenAI paskyros duomenų saugojimo politikų.

Oficialios integracijos nuorodos: [Responses API](https://developers.openai.com/api/reference/responses/overview), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [patikrinto Diasporos leidimo srautas](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/controllers/streams_controller.rb).

Projekto šaknyje esančiame vietiniame `.env` faile įrašykite `OPENAI_API_KEY=jusu_raktas` ir išsaugokite. Python pirmiausia naudoja aplinkos kintamąjį, o kai jo nėra – šį failą. `.env` ignoruojamas Git ir laikomas už serverio teikiamo `dist/` katalogo. Rakto į pokalbį, pavyzdžius ar naršyklės kodą nekelkite.

Paleiskite `python3 openai_check.py`. Patikra kreipiasi tik į `GET https://api.openai.com/v1/models` ir neišveda rakto ar API atsakymo kūno. Ji nesukuria modelio atsakymo, nesiunčia pratybų turinio ir nekeičia rodiklių. Sėkmė reiškia prieigą prie modelių sąrašo; konkretaus modelio analizė ir apmokėjimas dar nepatikrinti. Ribotų teisių raktui gali reikėti leisti skaityti modelių sąrašą.

OpenAI raktas skirtas būsimai AI analizei. Diasporos duomenų gavimas ir autorizacija prijungiami atskirai. Analitiniai vaizdai tebėra demonstraciniai.

Oficiali autentifikavimo dokumentacija: https://developers.openai.com/api/reference/overview

Gyva patikra 2026-10-21: OpenAI modelių prieiga, sintetinio sakinio struktūruota analizė ir vieno tikro įrašo teksto bandymas pavyko. Autentifikuotai gauti 5 paskyrai matomi įrašai, 2 nuotraukų metaduomenų elementai, 5 originalo nuorodos; šioje imtyje komentarų nebuvo. Visi 5 įrašai importuoti ir patikrinti per vietinį API. Tikro įrašo bandymui pradinis pratybų kontekstas nepateiktas, todėl termometro kategorija palikta peržiūrai; tai nėra pratybų analizės kokybės patvirtinimas. 52 Python testai ir visi 5 JS testų rinkiniai praėjo.

Vietinė „Naratyvų observatorijos“ kopija tolesniam plėtojimui „Codex“. Reikia Python 3.9 arba naujesnio. Papildomų paketų diegti nereikia.

## Paleidimas

Terminale pereikite į šį projekto katalogą ir paleiskite:

```sh
python3 app.py serve
```

Atverkite http://127.0.0.1:8000/. Sustabdyti: `Ctrl+C`. Jei 8000 prievadas užimtas: `python3 app.py serve --port 8001`.

„Codex“ šį katalogą galima pasirinkti kaip projektą. Pagrindinė kūrimo instrukcija yra `AGENTS.md`. Ši kopija yra atskiras vietinis projektas; pradinis Desktop katalogas nepakeistas.

## Kas veikia

- Originali lietuviška sąsaja: temų apžvalga, naratyvų žemėlapis ir raida laike.
- Vartotojo patvirtintas 15 temų katalogas nurodyta tvarka, 8 prioritetai, išsaugoti 21 naratyvo ID ir originalūs apibrėžimai.
- Python serveris, vietinė SQLite duomenų bazė, JSON ir CSV importas.
- Datos normalizuojamos į UTC; reikalaujama šaltinio, išorinio ID, teksto, datos su laiko juosta ir demonstracinių duomenų žymos.
- Pasikartojantys `(source, external_id)` praleidžiami. Esamo įrašo turinys pakartotiniu importu nekeičiamas.
- Klaidingas paketas atmetamas visas. Neaiškūs priskyrimai saugomi su tuščiu `narrative_id`; nauji naratyvai automatiškai nekuriami.

**Analitiniai vaizdai kol kas rodo originalų demonstracinį rinkinį. Importuoti įrašai prie šių rodiklių nepridedami.** Viršutinėje juostoje kompiuteryje atskirai matomas importuotų įrašų skaičius; jis atsinaujina perkrovus puslapį arba grįžus į jo langą. Importuotus įrašus galima skaityti per API. Vienkartinis autentifikuotas Diasporos srauto gavimas ir ribotas OpenAI teksto analizės bandymas paleidžiami atskirai per `integrations.py`; jų rezultatai demonstracinių rodiklių nekeičia.

## Importas

Pateikti du sintetiniai pavyzdžiai:

```sh
python3 app.py import examples/posts.json
python3 app.py summary
```

Importui tinka JSON objektų masyvas arba CSV su šiais stulpeliais:

| Laukas | Turinys |
| --- | --- |
| `source` | Šaltinio pavadinimas |
| `external_id` | Unikalus įrašo ID tame šaltinyje |
| `published_at` | ISO 8601 data su laiko juosta, pvz. `2026-10-19T12:00:00+03:00` |
| `text` | Įrašo tekstas |
| `narrative_id` | Esamas ID, pvz. `N-005`, arba tuščia reikšmė |
| `stance` | `support`, `oppose`, `quote`, `unknown`; numatyta `unknown` |
| `is_demo` | Privaloma `true` arba `false` |
| `kind` | Neprivaloma `post`, `comment`, `reshare`; senų įrašų numatyta `post` |
| `sourceUrl` | Šaltinio pateikta konkretaus įrašo / komentaro originalo nuoroda arba tuščia |
| `parentSourceUrl` | Komentarui žinoma pirminio įrašo nuoroda, jei tiesioginės komentaro nuorodos nėra |
| `media` | Neprivalomas medijos masyvas; CSV langelyje – JSON. Pavyzdys pateiktas žemiau |

Nepriskirtas įrašas ir naujas nepatvirtintas naratyvas yra skirtingi dalykai: šiame etape importas saugo nepriskirtus įrašus, bet nekuria naujų naratyvų kandidatų.

Numatyta bazė: `var/signalas.sqlite3`. Galima pasirinkti kitą bazę, globalų argumentą rašant prieš komandą:

```sh
python3 app.py --db var/eksperimentas.sqlite3 import examples/posts.json
python3 app.py --db var/eksperimentas.sqlite3 serve --port 8001
```

## Vietinis API

| GET kelias | Rezultatas |
| --- | --- |
| `/api/health` | Serverio būklė ir sąsajos demonstracinis režimas |
| `/api/platform/overview?period=7` (1 / 3 / 7 d.) | Visos platformos demonstracinės kategorijos ir autorių reitingas |
| `/api/metrics/context` | Konkrečių pratybų auditorijos duomenų būsena ir bendri augimo slenksčiai; kol šaltinis neprijungtas, auditorija nežinoma |
| `/api/catalog` | Fiksuotos temos ir naratyvų apibrėžimai |
| `/api/summary` | Importuotų įrašų kiekis, demo žyma, nepriskirti įrašai |
| `/api/posts?limit=100&offset=0` | Importuoti įrašai, naujausi pirmi; daugiausia 500 viename puslapyje |

Serveris klausosi tik `127.0.0.1`. API yra skirtas šiam vietiniam darbui ir nereikalauja prisijungimo. Rašymas atliekamas per Python importo komandą. Duomenų bazė ir Python šaltiniai per statinių failų serverį neteikiami.

## Projekto struktūra

- `app.py` — vietinis serveris, validavimas, importas ir SQLite saugykla.
- `dist/` — esama sąsaja; `local.js` rodo Python importo būklę.
- `data/catalog.json` — Python naudojama esamo temų ir naratyvų katalogo kopija. Administratorius keisdamas katalogą turi suderinti ją su `dist/app.js`.
- `examples/posts.json` — tik sintetiniai importo pavyzdžiai.
- `tests/test_app.py` — importo ir API testai, naudojantys atskirą laikiną bazę.
- `var/` — vietiniai duomenys; neįtraukiama į Git.
- `README-original.md` — pradinio eksporto aprašas ir kilmė.

## Patikra

```sh
python3 -m unittest discover -s tests -v
node --check dist/app.js
node --check dist/local.js
```

Python vykdymui Node nereikia; jis naudojamas tik JavaScript sintaksės patikrai.

## Tolesnis plėtojimas

Diaspora pasirinkta pirmajam autentifikuoto srauto gavimo bandymui. Periodinis rinkimas dar neįjungtas. Toliau reikės patvirtinto konkrečių pratybų turinio ir narių susiejimo, analizės kokybės vertinimo bei analitiko peržiūros. Sąsajos laikotarpius, suvestines ir įrodymus reikės atskirai prijungti prie realių įrašų API, aiškiai atskiriant demo ir tikrus duomenis. Dabartinių sintetinių ryšių negalima pateikti kaip išmatuotų ryšių iš tikro srauto.

Vietinė versija neturi publikavimo konfigūracijos. Pirminio eksporto privataus Site tapatybė nekopijuota; vietiniai pakeitimai jo neatnaujina.

## Nuotaikų termometras

Atverkite `http://127.0.0.1:8000/#thermometer` arba pasirinkite naują navigacijos sekciją. Ji rodo 34 sintetinių vienetų atskiro demonstracinio rinkinio pasirinkto laikotarpio proporcijas, aprėptį, dienų raidą ir pagrindžiančius įrašus. AI analizė nevykdoma. Naratyvų filtrai šio bendro srauto neriboja.

- `thermometer.py` — gavimo adapteris, konteksto parinkimas, demonstracinės žymos ir statistika.
- `data/thermometer-demo.json` — sintetiniai vienetai, konteksto versijos ir žymos.
- `dist/thermometer.js`, `dist/thermometer.css` — demonstracinės sekcijos vaizdavimas.
- `GET /api/thermometer?period=1|3|7` — demonstracinis API.
- `python3 thermometer.py` — atnaujinti statines atsargines 1, 3 ir 7 dienų išvestis pakeitus demo duomenis.
- `docs/THERMOMETER.md` — bendras įvesties kontraktas, modelio kandidatas, kritinė peržiūra ir vertinimo planas prieš realų naudojimą.

Pakeitus `app.py` arba `thermometer.py`, vietinį serverį reikia paleisti iš naujo. Papildoma JS patikra: `node --check dist/thermometer.js`.

## Pratybų kontekstas

Atverkite `http://127.0.0.1:8000/#context`. Sekcijoje yra tik du tekstiniai laukai: „Pradinė situacija“ ir „Patvirtinti scenarijaus faktai“. Abu užpildomi ir išsaugomi vieną kartą pratybų pradžioje. Po sėkmingo išsaugojimo laukai lieka tik skaitomi. Redagavimo, įvykių pildymo ir konteksto versijų valdymo funkcijų nėra.

Vienas aktyvus pradinis kontekstas saugomas šios naršyklės `localStorage` raktu `signalas.exerciseContext`. Jis atkuriamas atnaujinus puslapį tuo pačiu adresu ir tame pačiame prievade. Saugyklos klaida rodoma aiškiai, neskelbiant, kad duomenys išsaugoti; esami duomenys automatiškai neperrašomi.

`dist/exercise-context.js` teikia bendrą `window.SignalExerciseContext.get()` prieigą. Integracijos vietos:

- `window.SignalDemo.prepareAnalysisInput(unit)` — naratyvų analizės įvestis su tuo pačiu pradiniu kontekstu ir galimybe aptikti naujus naratyvus esamame 15 temų kataloge.
- `window.SignalThermometer.prepareAnalysisInput(unit)` — termometro įvestis su tuo pačiu kontekstu, visu srautu ir neprivalomu naratyvo priskyrimu.

Abu metodai parengia įvestį; AI analizės nevykdo. Jie atskiria nekintamą `exercise_context` nuo įrašo teksto, pirminio įrašo, jo medijos ir reikalingos ankstesnės diskusijos. Vėlesni teiginiai nepridedami prie patvirtintų faktų. Trūkstamas būtinas faktas turi lemti „Reikia peržiūros“ su paaiškinimu; aprašyme nenumatytas įvykis savaime nelaikomas klaidingu ar destabilizuojančiu.

Pradinis kontekstas nenaudojamas kaip atrankos filtras. Iš anksto parengti naratyvų ir termometro demonstraciniai rezultatai jo pagrindu neperskaičiuojami. Termometro vidinis sintetinių pavyzdžių pagrindas nėra naudotojo pratybų konteksto istorija ir nėra keičiamas šioje sekcijoje.

Patikra: `node --check dist/exercise-context.js` ir `node tests/test_exercise_context.cjs`. Pastaroji programiškai tikrina saugojimą, naują modulio įkėlimą su išlikusia saugykla, prieigą abiem moduliams ir saugyklos klaidas. Interaktyvus naršyklės valdymas nenaudojamas pagal vartotojo pageidavimą.

Termometro žinutės pagal nutylėjimą paslėptos po mygtuku „Termometro turinys“. Išskleidus rodomi visi pasirinkto laikotarpio turinio vienetai su kategorijų žymomis. Vidinei analizei galima pasirinkti stabilizuojantį, neutralų, destabilizuojantį arba peržiūros laukiantį turinį.


## Naratyvų augimo ženkliukai

Atskiras „Kas keičiasi“ blokas pašalintas. Temų katalogas užima visą apžvalgos plotį. „↗ Sparčiai auga“ rodomas prie naratyvų pavadinimų apžvalgos lentelėje ir po žemėlapiu. Paaiškinimas pasiekiamas užvedus pelę, paspaudus arba gavus klaviatūros fokusą; uždaromas „Escape“. Ženkliukas yra atskiras mygtukas ir nekeičia naratyvo išskleidimo.

Bandomieji slenksčiai laikomi vienoje vietoje: `dist/metrics-context.json`, `growth_policy`. Ankstesnis kiekis > 0, procentinis prieaugis ≥ 50 %, absoliutus prieaugis ≥ `max(3, ceil(0.01 × faktinė pratybų auditorija))`. Visi kriterijai turi būti tenkinami kartu. Tai produkto bandymo nustatymai, ne statistiškai patvirtintos ribos. 1 % didesnėms auditorijoms pakelia minimalaus kiekio ribą; 3 vienetų minimumas sumažina ženkliukų dėl pavienių veiksmų skaičių mažose auditorijose. Nėra fiksuotos 200–300 narių prielaidos.

Kai patvirtinta auditorija yra 100 ar 250 narių: 2 → 5 rodo ženkliuką, 1 → 2 nerodo, 10 → 15 rodo. Kai auditorija 500, reikia bent +5 vienetų. Jei konkrečių pratybų auditorija nežinoma, tuščia arba neatitinka turinio pratybų ID, ženkliukas nevertinamas. Grynas turinio kiekio pokytis gali būti apskaičiuotas be narių skaičiaus ir nėra įsitraukusių žmonių dalies pokytis. Dabartiniai sintetiniai naratyvai nesusieti su realių pratybų narių sąrašu, todėl jų augimo ženkliukai paslėpti ir rodoma trūkstamų auditorijos duomenų būsena.

Nulinė bazė arba trūkstami palyginimo duomenys procento ir ženkliuko nerodo. Skaičiuojama iškart prieš pasirinktas 1 / 3 / 7 dienas buvusi tokios pačios trukmės atkarpa. `dist/demo/narrative-history.js` pateikia aiškiai sintetinius ankstesnių septynių dienų kiekius; ankstesni kiekiai nebeskaičiuojami iš saugomo augimo procento.

Patikra: `node tests/test_growth.cjs`, `node --check dist/growth.js`, `node --check dist/app.js`. Populiarumo ir pirmojo pastebėjimo datos rikiavimas nuo augimo kriterijų nepriklauso.


## Pavadinimų atitikmenys

„Pratybų kontekste“ prie dviejų esamų situacijos ir faktų laukų pridėta neprivaloma lentelė su dviem duomenų stulpeliais: „Tikras pavadinimas“ ir „Pavadinimas pratybose“. „Pridėti atitikmenį“ sukuria eilutę; „Pašalinti“ ją pašalina. Siaurame ekrane abu poros laukai pateikiami vienas po kitu.

Naudojamas tas pats „Išsaugoti kontekstą“ veiksmas ir tas pats localStorage įrašas. Išsaugoma `nameMappings: [{id, realName, exerciseName}]`. ID suteikiamas pridedant eilutę ir išlaikomas redaguojant, pašalinant kitas eilutes, išsaugant ir atnaujinant puslapį. Po išsaugojimo kontekstas ir atitikmenys lieka tik skaitomi. Senas įrašas be `nameMappings` skaitomas kaip turintis tuščią sąrašą, jo esamų duomenų automatiškai neperrašant.

Visiškai tuščios eilutės neįtraukiamos. Nepilnos, vienodos pasikartojančios ir prieštaringos poros pažymimos prie konkrečių eilučių; prieš išsaugant jas reikia pataisyti. Tikrinant pasikartojimą suvienodinamas raidžių dydis, Unicode forma ir tarpai, tačiau įvesti pavadinimai išsaugomi jų originaliu pavidalu, pašalinus tik kraštinius tarpus. Vieno tikro pavadinimo susiejimas su skirtingais pratybų pavadinimais arba vieno pratybų pavadinimo susiejimas su skirtingais tikrais pavadinimais laikomas prieštaravimu; programa nesirenka vieno varianto.

Abu `prepareAnalysisInput(unit)` metodai gauna tą patį atitikmenų sąrašą `exercise_context.nameMappings`. Originalus tekstas automatiškai neperrašomas. `content.source_reference` išlaiko šaltinį, turinio ID ir originalią nuorodą (`unit.url` arba `unit.original_url`, jei pateikta). Bendra rezultatų politika nurodo išlaikyti pratybų pavadinimus bei originalaus įrašo nuorodą. Susiejimai nenustato turinio kategorijos, nekeičia temų katalogo ir neriboja naujų naratyvų aptikimo.

AI analizė ir automatinis atpažinimas neprijungti. Tai duomenų perdavimo vieta. `node tests/test_exercise_context.cjs` tikrina neprivalomą lentelę, nepilnas / pasikartojančias / prieštaringas poras, ID ir duomenų išlikimą, seną kontekstą bei bendrą analizės įvestį. Naršyklės bandymai atliekami atskirame vietiniame prievade su testiniais duomenimis.

## Rodikliai ir auditorija

Audito rezultatai, formulės, paruoštas Python duomenų kontraktas ir konkretūs „diaspora*“ šaltinio apribojimai aprašyti `docs/METRICS.md`.

- `metrics.py` atskiria unikalių įsitraukusių paskyrų dalį, absoliučius turinio / sąveikų kiekius ir neprivalomą aktyvumą 100 narių. Narystė tikrinama pagal pratybų ID ir galiojimo laiką; autorius pašalinamas iš kitų narių įsitraukimo skaitiklio bei vardiklio. Tai paruošti skaičiavimo metodai, dar neprijungti prie tiesioginio „diaspora*“ srauto.
- `dist/metrics-context.js` gauna auditorijos būseną bei slenksčius iš vietinio API (statinė atsarginė kopija skaitoma iš to paties JSON). Auditorija neatspėjama iš aktyvumo, kontaktų ar bendro serverio registracijų skaičiaus.
- `dist/counts.js` parenka mažiems kiekiams tinkamą grafiko skalę ir demonstracines pozicijas paskirsto sveikais vienetais, išlaikydamas dienos sumą. Pozicijų procentai skaičiuojami iš pasirinkto laikotarpio įvertintų demonstracinių vienetų. Termometro procentų vardiklis lieka įvertintas turinys.
- Pagal vėlesnę užduotį pridėta „Platformos apžvalga“ ir autorių reitingas, aprašyti žemiau. Bendras medianos metodas dabar gauna visus laikotarpio autorinius įrašus, įskaitant įrašus be sąveikų.

Papildoma patikra: `node tests/test_counts.cjs`, `node tests/test_growth.cjs`, `node tests/test_exercise_context.cjs`. Python rinkinyje yra auditorijos, matomumo, deduplikavimo ir istorinių pratybų testai. Prisijungimo duomenys į projektą nesaugomi.

## Platformos apžvalga

Atverkite `http://127.0.0.1:8000/#platform`. Trys lygiavertės kategorijos rodo iki trijų įrašų pagal komentarus (su atsakymais), patiktukus ir pasidalijimus. Kompiuteryje jos pateikiamos trimis stulpeliais, siaurame ekrane viena po kitos. Kortelėse išlaikomas originalus tekstas, autorius, Lietuvos laikas ir prieinama medija; ilgas tekstas išskleidžiamas. Naratyvų, temos, būsenos ir paieškos filtrai šios sekcijos neriboja. Bendras 10 / 7 / 3 / 1 dienų filtras išlieka.

Visur taikoma viena laiko logika: laikotarpiu **paskelbti įrašai** ir jų **bendri skaitikliai bei sąveikos**, o ne tik tuo laikotarpiu atlikti veiksmai. Ilga šios logikos paaiškinimo pastraipa iš apžvalgos antraštės pašalinta naudotojo prašymu; išlieka laikotarpio ir aprėpties žymos. Trūkstami skaitikliai nerikiuojami kaip nuliai; nepilna atranka pažymima. Patvirtintas nulinis kiekis ir nežinomas kiekis atskirti.

Po kategorijomis rodomi iki penkių autorių. `platform_overview.py`, `AUTHOR_POLICY`, yra viena bandomųjų kriterijų vieta: bent 3 aktyvūs originalūs įrašai ir teigiama auditorijos dalies mediana; balas = mediana × log₂(1 + aktyvių originalių įrašų skaičius). Į medianą įtraukiami **visi** autoriaus laikotarpio originalūs įrašai, taip pat be sąveikų. Komentarai ir paprasti persidalijimai neįeina. Aktyvumui reikia bent vieno kito tinkamo pratybų nario sąveikos. Sąveikų paskyros deduplikuojamos; autorius pašalinamas ir iš skaitiklio, ir iš konkretaus įrašo matomumo auditorijos. Nežinomas bent vieno originalaus įrašo įsitraukimas neleidžia to autoriaus vertinti. Reitingo balas nėra auditorijos procentas. Tai produkto bandymo kriterijus, ne patvirtintas statistinis modelis.

`data/platform-demo.json` yra aiškiai sintetinis 18 įrašų rinkinys, turintis savo **demonstracinį**, nuo realių pratybų nepriklausomą narių sąrašą. `python3 platform_overview.py` atnaujina statines atsargines 1 / 3 / 7 dienų išvestis. Tikras platformos srautas dar neprijungtas. `adapt_diaspora_post` ir `adapt_diaspora_comment` paruošia būsimą integraciją: reikia API pateiktų originalo nuorodų, pratybų ID, istorinių narių sąrašų, įrašų matomumo / gavėjų ir pilnų sąveikų paskyrų duomenų. Riboto pradinių sąveikų rinkinio negalima pažymėti pilnu. Medijos adapteriui perduodami patikimame šaltinyje pateikti medijos URL. Nė vienas turinio ar komentaro URL nėra konstruojamas iš ID. Prisijungimai ir tiesioginis rinkimas šiame etape nekuriami.

`content.py` ir `dist/source-content.js` suvienodina `sourceUrl`, `parentSourceUrl` ir originalo nuorodų vaizdavimą. Senos `url` / `original_url` įvestys tebepalaikomos. SQLite papildoma neprarandant senų duomenų; senos eilutės be nuorodų lieka su `null`. Šaltinio teksto tarpai ir eilutės importuojant išlaikomi. Nuorodos rodomos platformos kortelėse, autorių įrašuose, naratyvų pavyzdžiuose, termometro vienetuose ir jo diskusijos kontekste; perduodamos abiem analizės įvestims. Komentarui rodoma „Komentaro nuoroda“ arba „Atverti pirminį įrašą“. Visos tikros nuorodos atveriamos naujame skirtuke. Demonstraciniam turiniui tikrų originalų nėra; vietoj fiktyvaus mygtuko rodoma aiški trūkstamos nuorodos žyma.

Patikra: Python `unittest` rinkinys, `node tests/test_platform_ui.cjs` ir esami JS testai. Naršyklėje fone tikrinti kompiuterio / 390 px išdėstymai, originalaus teksto ir autoriaus įrašų išskleidimas bei laikotarpio keitimas. Naršyklės konteksto duomenys nebuvo keičiami.

## Nuotraukų miniatiūros

Tikro srauto pataisa (2026-10-21): Diasporos serveris WEBP failus grąžina kaip `text/plain` su `nosniff`, todėl tiesioginis miniatiūros įkėlimas gali nepavykti. Tik šio konfigūruoto podo HTTP medijos adresai keliami į HTTPS, išlaikant šaltinio kelią. Nepavykus tiesioginiam įkėlimui, bendras komponentas naudoja `GET /api/media/image` su `X-Signalas-CSRF` antrašte. Kelias tikrina tikslų loopback Host, aktyvų tikro turinio režimą ir leidžia tik konkretaus gauto įrašo ar komentaro nuosavos medijos indeksą. Savavališko URL parametro nėra.

`private_media.py` naudoja esamą Diasporos sesijos autorizaciją; slapukai ir iki 16 MiB ribota medijos kopija lieka tik proceso atmintyje, atnaujinus rinkinį išvaloma. Paveikslėlio tipas patikrinamas iš rastrinio failo signatūros, HTML ir SVG neperduodami. Atsakymas neturi CORS leidimo, turi `no-store` ir `Cross-Origin-Resource-Policy: same-origin`; žyma neperduodama URL. Nei nuotraukos, nei slapukai nekeliami į `dist/` ar viešą failų saugyklą. Neveikiant miniatiūrai dar bandoma šaltinio originali nuotrauka, o nepavykus išlieka tekstas ir originalo nuoroda. Patikrintos visos 3 tikros nuotraukos.


Vienas bendras `SignalSourceContent.thumbnail` / `body` komponentas naudojamas platformos kortelėse, išskleistuose autorių įrašuose, naratyvų pavyzdžiuose, termometro vienetuose ir jo atskirų komentarų kontekste. Miniatiūra rodoma šalia originalaus teksto: 96 × 72 px, siaurame ekrane iki 80 × 60 px. Kelios nuotraukos rodomos kaip pirmoji ir „+N“; galerijos nėra.

Bendra medijos forma:

```json
{
  "kind": "image",
  "thumbnailUrl": "https://pod.example/source-provided-thumbnail.jpg",
  "originalUrl": "https://pod.example/source-provided-original.jpg",
  "alt": "Šaltinio pateiktas alternatyvus tekstas"
}
```

Šie URL tik formato pavyzdžiai, demonstracinė sąsaja jų nenaudoja. `sourceUrl` lieka atskiras įrašo / komentaro laukas. Tušti arba nesaugūs medijos URL nepaverčiami veikiančiomis nuorodomis. Jei `thumbnailUrl` nėra, sumažintai rodoma `originalUrl`. Senas medijos `url` ir termometro nuosavi `attachments[].asset` tebepalaikomi, pateikiant juos tuo pačiu komponentu; analizės priedai ir jų vertinimai nepakeisti.

Paspaudimas ir klaviatūros „Enter“ atveria šaltinio pateiktą originalo nuorodą naujame skirtuke; kortelės / naratyvo išskleidimas nesuveikia. Atskira originalo nuoroda išlieka. Be originalo URL miniatiūra nėra tariama nuoroda. Komentarui naudojama jo tiesioginė nuoroda arba aiškiai pažymėtas pirminis įrašas. Komentaras niekada neperima pirminio įrašo ar persidalijimo šakninio įrašo nuotraukų.

Paveikslėliai įkeliami atidėtai (`loading="lazy"`). Iki sėkmingo įkėlimo pats paveikslėlis nematomas, todėl nerodoma sugadinto paveikslėlio ikona. Įkėlimo klaida pašalina visą miniatiūros elementą, palikdama tekstą ir originalo nuorodą. Tuščiam medijos sąrašui vieta nerezervuojama.

Python adapteris perskaito tik nuosavą `photos` masyvą. [Diasporos PhotoPresenter](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/presenters/photo_presenter.rb) pateikia `sizes.medium` / `sizes.small` ir `sizes.raw` / `sizes.large`; naudojamos šios pateiktos reikšmės. API pateiktas santykinis medijos kelias gali būti išspręstas pagal aiškiai perduotą `source_base_url`; kelias iš nuotraukos ar įrašo ID negeneruojamas. `media` išsaugoma ir grąžinama per vietinio importo API, senoms SQLite eilutėms išlaikant tuščią sąrašą.

Tikras Diasporos duomenų gavimas tebėra neprijungtas. Reikia realių įrašų medijos URL, originalo nuorodų ir, jei nuotraukos apsaugotos, veikiančios autorizuotos šaltinio prieigos. Pateikti URL naudojami tiesiogiai su įprastais naršyklės prieigos apribojimais; neįdiegta vieša nuotraukų kopija, proxy ar privatumo apribojimų apėjimas. Neprieinama autorizuota nuotrauka tiesiog paslepiama. Demonstraciniai SVG aiškiai pažymėti kaip iliustracijos, ne tikros Diasporos nuotraukos, ir neturi fiktyvių originalo nuorodų.

Patikra: `node tests/test_thumbnails.cjs`, esami JS rinkiniai ir Python `unittest`. Atskira vietinė bandomoji peržiūra patikrino be nuotraukos / vieną / kelias nuotraukas, originalo URL sumažinimą, 404 paveikslėlį, komentaro medijos atskyrimą, paspaudimą ir klaviatūros „Enter“ su nauju skirtuku bei nepakeistu kortelės išskleidimų skaičiumi. Aplikacijoje naršyklėje patikrintos visos keturios vietos ir 1280 / 390 px išdėstymai. Autorių reitingo, naratyvų analizės ir termometro skaičiavimo formulės nepakeistos.

## Privati debesijos duomenų bazė

Vercel projektui prijungta Neon Postgres `signalas-data` (Free, Frankfurt). Vietinis Python rinkiklis po sėkmingo `collect-sample` automatiškai įrašo imtį, kai serverio `.env` nustatytas `SIGNALAS_DATABASE_URL`. Prisijungimas laikomas tik ignoruojamame `.env`, niekada `dist/` ar Git. Vercel integracija projekto aplinkoje valdo `DATABASE_URL`.

`signalas_fetches` saugo surinkimų JSON kopijas, `signalas_content` – naujausius įrašus ir komentarus su medijos metaduomenimis bei sąveikomis. Nuotraukų failai nekopijuojami. Šaltinio/paskyros sritis atskirta; pakartotinis siuntimas nedubliuoja turinio. Debesijos klaida nepašalina vietinės kopijos ir grąžinama atskirai `cloud_storage` rezultate. Pakartoti paskutinės kopijos siuntimą: `python3 cloud_storage.py`.

Duomenų bazė nėra viešas API. Vercel sąsaja lieka demonstracinė iki atskiros autentifikuotos skaitymo integracijos. Automatinis rinkimas vis dar vyksta vietiniame kompiuteryje per esamą kasvalandinę užduotį. Duomenų kopijų kaupimą riboja pasirinkto nemokamo plano talpa; automatinio privataus turinio trynimo ar mokamo plano įjungimo nėra.
