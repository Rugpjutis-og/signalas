# Nuotaikų termometras: įgyvendinimas ir kritinė peržiūra

## Išvada

Turinio komunikacinės krypties modelis tinka pratybų prototipui. Jis dar nėra empiriškai patikrintas automatinis klasifikatorius. „Nuotaikų termometras“ yra vartotojo pasirinktas sekcijos pavadinimas; matuojama paskelbto turinio kryptis scenarijaus kontekste, o ne emocinė ar psichologinė dalyvių būsena, visuomenės nuomonė arba įrodytas elgesio pokytis.

## Kas įgyvendinta

Ketvirtas navigacijos vaizdas, bendra 1 / 3 / 7 dienų laikotarpio parinktis, trijų kategorijų juosta, kiekiai ir procentai, aprėptis, dienos proporcijų diagrama bei kategorijų vienetai su paaiškinimais. Neįvertintų įrašų sąrašą galima atverti iš aprėpties eilutės. Prie kiekvienos dienos pateikiama „įvertinta / gauta“. Dienos be įvertintų vienetų rodomos brūkšniuotos, be tariamų nulinių procentų.

Katalogas lieka vartotojo patvirtintų 15 temų. Termometro srauto neriboja paieška, tema, prioritetas ar naratyvo būsena. Šie filtrai termometre paslepiami, jų pasirinkimai išlaikomi grįžtant į kitus vaizdus.

Demo yra 34 sintetiniai vienetai. Tai atskiras demonstracinis rinkinys: senosios apžvalgos agreguoti demonstraciniai skaitikliai ir SQLite importuoti įrašai nėra šio termometro šaltinis. Būsimai integracijai reikės suvienodinti realių vienetų šaltinį abiem analizėms.

## Duomenų kelias

1. `thermometer.load_demo()` gauna vienetus, konteksto versijas ir iš anksto parengtas žymas iš `data/thermometer-demo.json`.
2. `context_at()` parenka naujausią kontekstą, kurio įsigaliojimas ir žinojimo momentas ne vėlesni už įrašą.
3. `demo_assessment()` tik nuskaito parengtą žymą. Joje nėra raktažodžių klasifikatoriaus ar modelio iškvietimo.
4. `aggregate()` pašalina pakartotinius `(source, id)`, filtruoja laiką ir suskaičiuoja nesvertus rodiklius.
5. `/api/thermometer?period=7` pateikia demonstracinį rezultatą. `dist/thermometer.js` jį tik atvaizduoja.

`python3 thermometer.py` sukuria 1, 3 ir 7 dienų statinius atsarginius JSON, skirtus statinei peržiūrai. Tai tų pačių Python skaičiavimų išvestis, ne antra skaičiavimo realizacija. Juos reikia atnaujinti pakeitus demo duomenis ar logiką. Statinis atsarginis rinkinys leidžiamas tik demonstracijoje; realios integracijos klaidos neturi tyliai rodyti senų demonstracinių duomenų.

## Rodikliai

Kategorijos procentas = kategorijos įvertintų vienetų skaičius / visų įvertintų vienetų skaičius × 100.

Trijų kategorijų suma lygi 100 %, išskyrus apvalinimą iki vieno skaitmens. Neįvertinti vienetai į šį vardiklį nepatenka. Kai nėra įvertintų vienetų, procentai yra `null`, sąsaja rodo „Nėra įvertintų duomenų“. Aprėptis = įvertinta / visi gauti vienetai. Laikotarpis turi įskaitytiną pradžią ir neįskaitytiną pabaigą; dienos grupuojamos Lietuvos laiku.

Vienas įrašas, komentaras ar žinutė yra vienas vienetas. Vaizdas, jo tekstas, transkripcija ir kadrai – priedai. Atskirai paskelbti vienodi tekstai su skirtingais ID skaičiuojami atskirai. Autoriai, organizacijos, patiktukai ir formatas svorio nesuteikia.

## Bendras įvesties ir rezultato kontraktas

Vienetas turi `id`, `source`, `kind`, `published_at` su laiko juosta, `text`, `conversation_context`, `attachments`, `is_demo`; neprivalomi analitiniai požymiai yra `narrative_id` ir atskiras `stance`.

Paveikslėlio priedas turi aprašą, vaizdo nuorodą, OCR tekstą ir perskaitomumo būseną. Vaizdo klipas turi trukmę, transkripcijos ir subtitrų intervalus, kadrų laiko žymas, vaizdų nuorodas ir `full_video_reviewed`. Demo video sudaro sintetinė transkripcija bei iliustraciniai kadrai, o ne tikras įkeltas klipas. Parodyta tik 10–18 s teksto atkarpa ir du kadrai; likusi 60 s klipo dalis nelaikoma įvertinta.

Vertinimas saugo `status` (`assessed` arba `needs_review`), `category` (viena iš trijų arba `null`), `reason`, `evidence`, `context_version`, `reviewed_parts`, `method` ir `content_fingerprint`. Piršto atspaudas sieja vertinimą su konkrečiu tekstu, data, diskusija ir priedais. Turinį pakeitus, sena žyma nebetaikoma. Patvirtinant naują demo žymą atspaudas apskaičiuojamas `content_fingerprint(unit)`; jo negalima tyliai atnaujinti neperžiūrėjus vertinimo.

`model_input()` parengia kontraktą būsimam modeliui: turinį, tik ne vėlesnę diskusiją, tuo metu galiojusį kontekstą, kategorijų apibrėžimus, taisykles ir pažymėtus pavyzdžius. Autoriaus pratybų pusė ir naratyvo palaikymo žyma neperduodamos kaip kategorijos nustatymo kriterijai.

## Kritinės pastabos ir pataisos

- **Pavadinimo interpretacija.** „Nuotaikos“ gali sudaryti psichologinio matavimo įspūdį. Sąsajoje pagrindinis paaiškinimas aiškiai nurodo turinio komunikacinę kryptį.
- **Vėlesnės žinios.** Filtruojami ir konteksto versijų laikai, ir vėlesnės diskusijos žinutės. Konteksto versijos prieš realų naudojimą turi būti nekintamos ir saugomos su audito istorija.
- **Pasenęs vertinimas.** Turinio atspaudo neatitikimas grąžina „reikia peržiūros“. Esamas bendras JSON/CSV importas pakartotinį ID praleidžia; turinio redagavimų versijavimas dar nėra įdiegtas.
- **Maža arba šališka aprėptis.** Procentai apibūdina tik įvertintą dalį. Pridėta ir kiekvienos dienos aprėptis. Daug neįvertintų ar sudėtingų įrašų gali iškreipti matomą pasiskirstymą; viso srauto proporcijos tokiu atveju nėra žinomos.
- **Mišri kryptis.** Viename įraše gali būti ir pagalba, ir žalingas raginimas. Kol nėra aiškios organizatorių taisyklės tokiems atvejams, neaiškus vienetas paliekamas peržiūrai; kryptys nesudedamos į nulį ir nevadinamos neutraliomis.
- **Konteksto kaita.** Raidos pokytį gali lemti pasikeitę scenarijaus faktai, klasifikavimo taisyklės ar modelio versija. Proporcijų skirtumas savaime neįrodo komunikacijos poveikio. Prieš realų naudojimą reikia fiksuoti vertinimo ir scenarijaus versijas.
- **Neutralus ir nesusijęs.** Pagal užduotį jie sujungti vienoje kategorijoje. Iš šios pilkos dalies negalima atskirai spręsti, kiek buvo neutralių reakcijų į scenarijų ir kiek visai nesusijusių įrašų.
- **Medijos ribos.** Sintetiniai OCR ir transkripcijos tekstai nėra realiai veikiančių OCR ar kalbos atpažinimo kokybės įrodymas. Dalinė vaizdo peržiūra neįrodo, kad likusiame klipe nėra prasmę keičiančių scenų.
- **Demo ir kokybės testas.** Šie pavyzdžiai skirti sąsajai bei skaičiavimams. Išankstinių žymų grąžinimo testai nepatvirtina semantinio klasifikatoriaus tikslumo.
- **Ankstesni naratyvų rodikliai.** Esamo prototipo palaikymo / prieštaravimo procentai yra fiksuoti demonstraciniai dydžiai; ankstesnio laikotarpio kiekiai išvedami iš sintetinio augimo. Jų negalima laikyti išmatuota realių įrašų dinamika. Jie nenaudojami termometro kategorijoms.

## Vienas modelio kandidatas būsimam bandymui

Pradiniam ribotam kokybės bandymui siūlomas **GPT-6 Astra** su teksto ir paveikslėlių įvestimi bei struktūruotu rezultatu. Tai kandidatas įvertinimui, ne nustatytas geriausias algoritmas. Pagal oficialią dokumentaciją jis palaiko vaizdų įvestį ir Structured Outputs; tiesioginė audio/video įvestis nepalaikoma. Todėl klipui paruošiama transkripcija, subtitrai ir atrinkti kadrai, tiksliai pažymint aprėptį. [OpenAI Docs, patikrinta 2026-10-20](https://developers.openai.com/api/docs/models/gpt-6-astra).

Joks modelis šioje demonstracijoje neprijungtas. Prieš integraciją reikia patikrinti prieinamumą paskyroje, kaštus su reprezentatyviais pavyzdžiais, saugų medijos gavimą, rezultato schemos validavimą ir versijų saugojimą. Modelio pasitikėjimo skaičius nėra patikrinta tikimybė, todėl dabartinėje schemoje jis nenaudojamas.

## Vertinimo planas prieš realų naudojimą

Parengti 200–300 realistiškų pratybų pavyzdžių. Du žmonės juos žymi nepriklausomai; trečiame žingsnyje suderinami nesutarimai ir tikslinamos taisyklės. Šis žmonių darbas dar neatliktas. AI sugeneruoti pavyzdžiai negali pakeisti nepriklausomos validacijos.

Atskirti taisyklių derinimo ir galutinio testavimo dalis pagal diskusijos grupę bei beveik identiško turinio grupę. Tos pačios diskusijos, perskelbimai ir artimos variacijos negali būti abiejose dalyse. Galutinio testo pavyzdžiai negali būti prompto pavyzdžiai.

Skaičiuoti trijų kategorijų macro-F1, klaidų matricą, raudonos kategorijos precision ir recall. Atskirai rodyti abstencijas / „reikia peržiūros“ ir aprėptį; vien geras F1 mažai lengvų įrašų daliai nėra gero viso srauto veikimo įrodymas. Pateikti klaidas ir imties dydį konstruktyvios kritikos, citavimo, paneigimo, sarkazmo, tikrų perspėjimų bei medijos pogrupiuose. Slenksčius ir priimtinus klaidų kompromisus nustatyti tik pagal derinimo duomenis; galutinio testo nenaudoti taisyklėms koreguoti.

## Patikros apimtis

Python testai tikrina deduplikaciją, proporcijų vardiklį, tuščią / neįvertintą srautą, laikotarpių ribas, UTC ir Lietuvos dienų ribas, paskelbimo momento kontekstą, turinio pokyčius, vėlesnių diskusijos žinučių atmetimą ir demonstracinius API atsakymus. Programinis JS atvaizdavimo patikrinimas tikrina atskirą sekciją, kategorijų sąrašus, laikotarpį, nepriklausomumą nuo naratyvų filtrų bei pavėluotų atsakymų atmetimą.

Interaktyvi naršyklės ir vizualinio maketo patikra neatlikta, nes vartotojas paprašė sustabdyti naršyklės valdymą. CSS numato mažo ekrano išdėstymą, bet jo vaizdas nepatvirtintas realioje naršyklėje.

## Naujesnis sprendimas: nekintamas pradinis kontekstas

Pagal naujesnę vartotojo užduotį aktyvių pratybų pradinis kontekstas suvedamas tik vieną kartą dviem laukais ir saugomas naršyklėje. Jis nekeičiamas pratybų eigoje; konteksto versijų ir įvykių papildymo valdymo nereikia. Ankstesnės šiame dokumente pateiktos rekomendacijos dėl kintančio organizatorių konteksto versijų taikomos tik ankstesnės demonstracijos paaiškinimui ir nėra dabartinis aktyvaus konteksto reikalavimas.

Nauja integracijos vieta yra `SignalThermometer.prepareAnalysisInput(unit)`, kuri gauna tokį pat `exercise_context` kaip `SignalDemo.prepareAnalysisInput(unit)`. Susijusio pirminio įrašo medija ir ankstesni komentarai perduodami atskirai. Vėlesni teiginiai nepatvirtinami vien dėl jų pasirodymo sraute. Naujų įvykių nebuvimas pradiniame aprašyme neįrodo klaidingumo ar destabilizuojančios krypties; kai vertinimui būtinas nežinomas faktas, reikalinga peržiūra ir trūkstamo konteksto paaiškinimas.

Tai parengtas įvesties kontraktas. Esama Python demonstracinių žymų statistika nenaudoja naudotojo lokaliai įvesto konteksto ir nerodo perskaičiavimo pagal jį. Tą ribą aiškiai nurodo sąsaja.
