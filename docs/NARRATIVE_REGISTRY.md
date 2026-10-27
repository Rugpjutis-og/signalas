# Naratyvų registras ir vertinimo sutartis

## Šaltinis ir ID

`data/narrative-registry.json` tiksliai perkelti keturi `Signalas_naratyvu_registras.xlsx` lapai: 35 tipai, 15 temų, 41 originalių formuluočių atitikmuo ir 30 taisyklių. Failo SHA-256 saugomas kartu su versija `2026-10-23.1`. Registro tipų apibrėžtys nėra patvirtinti scenarijaus faktai.

T01–T15 turi aiškų ryšį su esamais aplikacijos temų ID; jų pavadinimai ir eilė sutampa. Senieji `N-001`…`N-021` lieka istoriniame/demo kataloge. Jie nėra tie patys kaip `N001`…`N035`. `legacy_crosswalk` nurodo peržiūros kryptį, bet niekada automatiškai neperrašo istorinių priskyrimų. Live žemėlapis priima tik dabartinės registro versijos, nepakeisto turinio ir to paties pradinio konteksto vertinimus; kiti pažymimi kaip reikalaujantys pakartotinio vertinimo.

## Vertinimas

Bendras AI atsakymas turi atskirus `narrative_analysis` ir termometro laukus. Registras perduodamas tekstinės analizės funkcijai, įskaitant įtraukimo / atmetimo kriterijus ir konkrečius formuluočių atitikmenis. Pratybų tikslai bei RED / BLUE instrukcijos iš atitikmenų lapo modeliui neperduodami kaip instrukcijos ar faktai. Visas šaltinio turinys laikomas nepatikimais analizuojamais duomenimis.

`narrative_analysis`:

- `match_status`: `matched`, `no_narrative`, `unmatched`, `uncertain`;
- `matches`: vieneto ir tipo poros `{type_id, stance, evidence, instance_entities}`;
- `stance`: `support`, `oppose`, `quote` (perteikia be aiškios pozicijos), `unknown`;
- `instance_entities`: subjektas, objektas, vieta, įvykis, laikas; nežinomos reikšmės tuščios;
- `proposals`: nepriskirti savarankiški teiginiai su pavadinimu, šablonu, esama tema, ištrauka, artimiausių tipų ID ir naujumo paaiškinimu;
- `uncertainty_reason`: būtino trūkstamo konteksto paaiškinimas.

Rezultato apvalkalas išlaiko šaltinio nuorodą, unit_id, exercise_id, content_version / content_fingerprint, registry_version, modelį ir analyzed_at. `narrative_projection` sukuria stabilius kandidatų ir atmainų ID. Priskyrimai vienareikšmiškai susieti su šaltinio vienetu; keliems tipams reikia atskirų tikslių jo paties teksto ištraukų. Tėvinis įrašas ir ankstesni komentarai yra kontekstas, o ne komentarui priskirtas turinys. Naujas vietovardis sukuria kitą atmainą, o ne tipą. Tikro ir pratybų pavadinimo aliasai suvienodina atmainos raktą, bet rodomi originalūs pavadinimai.

Tam pačiam teiginiui siauresnis tipas turi pirmenybę; vienodi ar vienas kitą apimantys kelių tipų įrodymai atmetami. Atskiros savarankiškos frazės gali pagrįsti kelis tipus. Pavyzdžiui, N030 tiesiogiai neprideda N010 priskyrimo. `type_rollups` pateikia aiškiai atskirą unikalių vienetų agregatą per registro hierarchiją. Kiekvieno tipo tiesioginiai kiekiai ir bendras visų tipų kiekis deduplikuojami pagal `(source,id)`. Pirmo pastebėjimo data naudojama iš visos turimos patikimai įvertintos imties, ne tik pasirinkto laikotarpio.

Pozicijų procentų vardiklis – konkrečiam tipui įvertinti turinio vienetai. `unknown` neįtraukiamas į šiuos procentus; sąraše ir detalėse rodoma aprėptis ir neaiškių pozicijų kiekis. Termometro kategorijos iš naratyvų ar pozicijų neišvedamos.

AI struktūrinė schema atitinka [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) reikalavimus: objektams naudojami visi privalomi laukai ir `additionalProperties: false`. Schema pati nepatvirtina semantinio sprendimo teisingumo; papildoma Python validacija tikrina ID, būsenas ir originalias ištraukas.

## Kandidatai

Visi bandomieji slenksčiai vienoje vietoje: `narrative_registry.CANDIDATE_POLICY`.

- Paskutinės 24 valandos, apribotos žinoma pratybų pradžia; UI rodo langą.
- Bent 3 savarankiški vienetai ir 2 gijos.
- Žinomas N: bent `max(2, ceil(0.01 × N))` autorių. Nežinomas N: 3 autoriai ir aiški nežinomos auditorijos žyma. N=0 kandidatų nėra.
- N imamas tik iš pilno konkrečių pratybų narių sąrašo, galiojančio visame lange. Nepilnas, prieštaringas ar nedatuotas sąrašas nenaudojamas vardikliui.
- Paprasti persidalijimai neįtraukiami; kartotiniai vienetai ir beveik vienodas tekstas nelaikomi nepriklausomomis formuluotėmis. Pradinis teksto panašumo kriterijus – 0,85 (`SequenceMatcher`), tai euristika.
- Būtinas AI pateiktas semantinio naujumo pagrindas, palyginimas su artimiausiais tipais ir tikslūs įrodymai. Laukiančių teiginių šablonai perduodami tolesnei analizei, kad modelis sinonimus sietų su tuo pačiu šablonu. Programos grupavimo raktas – normalizuotas šablonas ir tema konkrečiose pratybose. Jis nėra atskira semantinė paieškos sistema; modelio nevienodai suformuluoti šablonai gali likti atskirose grupėse ir reikalauti peržiūros.

Kandidatai rodomi atskirai nuo patvirtinto žemėlapio. Pateikiamas naujumo pagrindas, autoriai / gijos / vienetai, datos, trys reprezentatyvūs šaltiniai ir jų originalo nuorodos (kai pateiktos). Filtravimas neišgalvoja nuorodų ar pratybų ID. Nežinomas pratybų ID žymimas. Kandidatų slenksčiai nekeičia augimo ženkliuko ar termometro kriterijų.

## Administratoriaus sprendimas ir Neon

Aplikacijos bendras prisijungimas nesuteikia naujos administratoriaus teisės. `narrative_admin.py` vykdomas tik patikimoje serverio aplinkoje su esamais Neon prisijungimo duomenimis. Naršyklės viešo tvirtinimo endpointo nėra.

```sh
python3 narrative_admin.py list
python3 narrative_admin.py approve --candidate C... --actor administratorius --definition patvirtintas-tipas.json
python3 narrative_admin.py merge --candidate C... --actor administratorius --target N031
python3 narrative_admin.py reject --candidate C... --actor administratorius
```

Patvirtinimo JSON reikia `title`, `claim_template`, `topic_id`, `include_when`, `exclude_when`; pasirinktinai `secondary_topics` ir `broader_type`. Administratorius turi patikrinti teiginio naujumą ir kriterijus, ne vien paspausti patvirtinimą. `--actor` yra audito žyma, ne autentifikavimo mechanizmas; prieigą riboja serverio DB kredencialai.

Sprendimai, patvirtinti papildomi tipai, alias / replaced_by ir istorija saugomi tik esamos Neon `signalas_state` lentelės `narrative-registry-state.json` įraše. Konkurentiniai sprendimai apsaugoti palyginimo ir įrašymo SQL sąlyga. Naujų DB lentelių nereikia. Numeris skiriamas monotoniškai nuo N036, ne pagal rikiavimą. Patvirtinimas ar prijungimas neperrašo šaltinio turinio ir istorinių vertinimų: naujai registro versijai reikia aiškiai paleisto pakartotinio vertinimo. Vietiniai duomenų failai ir browser storage nenaudojami.

Šios užduoties metu sprendimų į gyvą Neon bazę nerašyta, mokamos API užklausos nevykdytos, kodas nepublikuotas.

## Patikra ir ribos

`tests/test_narrative_registry.py` tikrina katalogą, ID migracijos ribas, kelių teiginių sutartį, pirmenybę siauresniam tipui, originalias daugiakalbes ištraukas, atmainas / vardų aliasus, deduplikuotus kiekius, nežinomų pozicijų aprėptį, kandidatų sklaidą, senus ir kitos pratybos duomenis bei administratoriaus sprendimus. `tests/test_narrative_ui.cjs` atvaizdavimo testuoja fiksuotas temas, registrą, atmainas, kandidatų atskyrimą, filtrus, išskleidimo išsaugojimą, originalo nuorodas, HTML escaping ir naujų analizių atnaujinimą be rinkimo.

Tai sintetiniais atsakymais paremti programos testai, ne AI tikslumo įvertinimas. Bendras teksto analizės adapteris paruoštas, bet Vercel automatinio AI apdorojimo paleidimas nėra prijungtas. Vaizdo / garso turinio supratimas, OCR ir vaizdo kadrų analizė neįgyvendinti: jų URL nėra peržiūrėta medija. Originalaus teksto analizės rezultatai žymi šią aprėpties ribą. Tikrų naujų modelio rezultatų ir gyvų Neon sprendimų integracinis testas dar neatliktas.

Pasirenkama headless vizualinė patikra: `NODE_PATH=<playwright paketų katalogas> node tests/browser/narrative-ui.cjs`; galima nurodyti `SIGNALAS_QA_BROWSER` arba `SIGNALAS_QA_CHROME=1`. Naudojama atskira naršyklė, tik sintetiniai API atsakymai, 1440 ir 390 px vaizdai, be DB. Šioje sesijoje naršyklės procesą užblokavo macOS MachPort leidimai, todėl vizualinė patikra liko nepatvirtinta.


2026-10-23 papildymas: po rankinio Vercel surinkimo prijungta Neon teksto analizės eilė (`cloud_analysis.py`). Ją tęsia atidaryta autentifikuota aplikacija; media tebėra nevertinama. Žr. aktualų README skyrių „Analizė po duomenų surinkimo“. Ankstesnės pastabos apie neprijungtą automatinį paleidimą aprašo būseną iki šio papildymo.


## Patvirtinti subnaratyvai (2026-10-24)

Vartotojo patvirtintas ryšys „pagrindinis naratyvas → subnaratyvas“ saugomas atskirai nuo 35 tipų registro Neon bazėje. N007 pavadinimas atnaujintas į „Sąmoningai slepiama ir nutylima tiesa“. Informacijos trūkumo teiginys gali būti teminė N007 atšaka, bet savaime neįrodo sąmoningo slėpimo. Pagrindinio teiginio tiesioginė atitiktis ir teminis grupavimas neskaičiuojami kaip tas pats rodiklis; palaikymas ir termometro kryptis nepaveldimi. Nauji vėliau pasiūlyti subnaratyvai vis tiek laukia administratoriaus patvirtinimo. Duomenų rinkimo ar pakartotinės mokamos analizės vien priskyrimui nereikia.
# VALARE scenarijaus N031 interpretacija · 2026-10-27

Organizatoriaus patvirtintas VALARE judėjimo, jo respublikos, alternatyvios valdžios
ar Valarės šaulių palaikymas yra N031 „Alternatyvi jėga yra vienintelė išgelbėtoja“
scenarijaus atmaina. Pažodinių žodžių „vienintelė“ ar „išgelbėtoja“ nereikia.
Vien paminėjimas, citata, klausimas, žinia ar paneigimas nėra palaikymas.
`narrative_mapping.py` saugo atitikmenis ir interpretaciją; ji galioja tik
`diaspora.sauliai.lt` ir su išsaugotu pradiniu kontekstu susietam VALARE patikslinimui.
Temų, tipų ID ir bendro registro versija nekeičiami.

Nauja įprasta analizė gauna šią interpretaciją. Atskirai autorizuota Neon
`narrative-mapping-review.json` užklausa sudaro vienkartinę jau analizuotų,
aktyviame manifeste esančių VALARE minimų vienetų eilę (naujausi pirmiausia).
Atrankai naudojamas tekstas ir ankstesni naratyvo įrodymai; tai nėra automatinis
priskyrimas ir ne pažadas aptikti dar neperskaitytus pavadinimus vien vaizduose.
Tikslinė peržiūra naudoja esamą Sol „medium“ juostą ir bendrą vykdymo blokavimą;
įprasta analizė tęsiama pagal esamą 3:1 planavimą.

Mokamas atsakymas turi tik naratyvų schemą. Sėkmingai patikrinus atnaujinamas tik
`result.narrative_analysis` ir jo kilmės metaduomenys. Termometro rezultatas,
ankstesni jo paaiškinimai ir rankiniai sprendimai nekeičiami. Neaiškus, netinkamas
ar nutrūkęs vertinimas palieka ankstesnį priskyrimą ir atskirą mažą audito įrašą;
sėkmingai įrašytas rezultatas po nutrūkimo pakartotinai neapmokestinamas.

