# Visos pratybų platformos surinkimas

## Patikros rezultatas · 2026-10-21

Dabartinė gyva jungtis **neapima visos platformos**. Patikrinta:

| Kelias / mechanizmas | Tikroji aprėptis |
| --- | --- |
| `GET /users/sign_in` ir prisijungimo formos POST | Įprasta paskyros sesija, ne administratoriaus eksporto teisė. OpenAI raktas šiai prieigai nenaudojamas. |
| `GET /stream.json` | Prisijungusio vartotojo asmeninis srautas pagal kontaktus, sekamas žymas ir serverio srauto taisykles. |
| `GET /posts/:id.json` | Vieno paskyrai prieinamo įrašo detalės ir sąveikos. |
| `GET /admins/dashboard` | Dabartinė paskyra nukreipiama į `/stream`; administracinė prieiga nepatvirtinta. |
| `GET /local_public.json` | Šiame serveryje grąžina 404. Net veikiantis viešas srautas neapimtų viso privataus turinio. |
| `/.well-known/openid-configuration` | Autentifikavimo aprašas pasiekiamas. Pats jo buvimas nesuteikia teisės skaityti visos duomenų bazės. |

`python3 integrations.py collect-sample` dabar skaito visus `/stream.json` puslapius ir savo profilio srautą: paskyra gaunama iš `/u/:username`, patvirtinamas `is_own_profile`, tada naudojamas serverio pateiktas GUID `/people/:guid/stream.json`. Bendro įrašų ar komentarų limito nėra. Dublikatai sujungiami pagal GUID; kiekvienam įrašui skaitomos pilnos detalės, nes srauto kortelėje būna tik paskutiniai trys komentarai. Puslapiai po 15 įrašų tęsiami su `max_time`, perdengiant ribinę sekundę, kad neprarastume milisekundžių tikslumo įrašų. Jei pilno puslapio neįmanoma tęsti vien laiko žyma, rinkimas baigiamas klaida ir paskutinė sėkminga kopija išlieka. Vieno HTTP atsakymo 8 MiB atminties apsauga taip pat reiškia aiškią klaidą, ne sutrumpintą sėkmingą kolekciją.

Produkcijoje turinį renka Vercel vykdymas kas valandą, o „GitHub Actions“ kas 5 minutes numato jo pažadinimą. Tai geriausių pastangų grafikas: vėluojantis planuoklis arba užimtas bendras rinkimo ir analizės užraktas gali atidėti surinkimą. Ankstesni 15 minučių terminai pritaikomi valandiniam intervalui, išlaikant pakartotinį bandymą atsilaisvinus užraktui. Surinktas turinys ir analizė saugomi Neon; vietinis „Codex“ rinkimas nebevykdomas. Po rinkimo tęsiama esama AI eilė; nepakeisto turinio analizės rezultatai naudojami pakartotinai. Laikotarpio filtras nekeičiamas.

Gyva patikra: srautas grąžino 9 įrašus, savo profilis – 3 iš tų pačių įrašų; po sujungimo 9 įrašai ir 104 komentarai. Gautos 113 originalo arba pirminio įrašo nuorodų ir 3 medijos metaduomenų elementai. Du įrašai yra spalio 14 d., todėl spalio 15–21 filtre rodomi 7 įrašai; tai laiko filtras, ne rinkimo limitas.

Patikrintame Diasporos leidime API `/api/v1/streams/main` taip pat remiasi vartotojo srautu. OAuth `private:read` reiškia prieigą prie tam vartotojui leistino privataus turinio, o ne visų podo privačių įrašų skaitymą. API puslapiavimas ir platesnės to paties asmeninio srauto ribos šio skirtumo neišsprendžia.

Šaltiniai: [oficialus srautų aprašas](https://diaspora.github.io/api-documentation/routes/streams.html), [naudojamo leidimo StreamsController](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/controllers/streams_controller.rb), [API srautų valdiklis](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/controllers/api/v1/streams_controller.rb).

## Paruoštas administratoriaus kelias

`server/signalas_export.rb` turi paleisti serverio administratorius Diasporos Rails aplinkoje, naudodamas **SELECT-only PostgreSQL rolę arba skaitymo repliką**. Papildomai pats skriptas atidaro vieną `REPEATABLE READ` transakciją ir nustato `SET TRANSACTION READ ONLY`. Jis nekuria HTTP maršruto, nekeičia paskyros teisių ir neatidaro turinio viešai.

Eksportas apima bazėje esančius `StatusMessage` ir `Reshare` srauto įrašus, įskaitant privačius, bei pasirinktu laikotarpiu paskelbtus jų komentarus. Nei kontaktų, nei sekamų žymų, nei dalyvių GUID filtras netaikomas. Įrašai skaitomi duomenų bazės ID paketais po 500 iki pabaigos, be 5 / 20 įrašų ar 100 komentarų bendro limito.

Komentarai atrenkami savarankiškai pagal paskelbimo laiką: jei atsakymo pirminis įrašas senesnis už pasirinktą laikotarpį, jis eksportuojamas kaip kontekstas, o ne papildomas to laikotarpio analizės vienetas. Ankstesnė diskusija išlaikoma. Įrašo nuotraukos neperduodamos komentarui kaip jo paties medija.

Originalo adresą pateikia paties serverio Rails maršrutizatorius. Komentarui, kai tiesioginio adreso nėra, perduodamas pirminio įrašo URL. Surenkami priedų URL ir jų tipai bei originalios sąveikų paskyros, ID, datos ir skaitikliai. Komentarų patiktukai skaitomi atskirai, nes standartinis komentaro pateikimas grąžina tik žiūrovo patiktukus.

Administratoriaus paleidimo pavyzdys: `FROM_ISO` ir `UNTIL_ISO` turi atitikti naudotojo pasirinktą intervalą; pabaiga neįtraukiama.

```sh
SIGNALAS_FROM="$FROM_ISO" \
SIGNALAS_UNTIL="$UNTIL_ISO" \
SIGNALAS_BASE_URL="https://diaspora.sauliai.lt" \
SIGNALAS_OUTPUT="/secure/signalas-export.json" \
RAILS_ENV=production \
bundle exec rails runner /secure/signalas_export.rb
```

Išvesties failas sukuriamas su 0600 teisėmis. Tik baigtas eksportas pervardijamas iš laikino failo; jau esamas eksportas neperrašomas. Administratorius saugiu kanalu perduoda JSON failą „Signalo“ operatoriui.

Vietiniame „Signalo“ projekto kataloge:

```sh
python3 integrations.py collect --export /secure/signalas-export.json
```

Importuojamas visas failas; autorius, kurio nėra dalyvių sąraše, neprarandamas. Pilnumas tikrinamas pagal administratoriaus aprėpties deklaraciją ir faktinius įrašų / komentarų kiekius. Jei kiekiai ar deklaracija nesutampa, turinys išsaugomas, bet aprėptis pažymima nepilna. Vien kliento pusėje negalima nepriklausomai patvirtinti serverio administratoriaus deklaracijos, todėl būtina gauti eksportą iš patikimo administratoriaus.

## Laikotarpis, auditorija ir ribos

Sąsajos kalendoriaus datos „Nuo“ ir „Iki“ išsaugomos atskirai nuo rinkinio. Abi dienos įtraukiamos Lietuvos laiku. Keičiant intervalą naudojama tik vietinė surinkta kopija; naujas rinkimas ar AI analizė nepaleidžiami. Rinkimo ar eksporto data, naujausias įrašas ir turimos imties dydis neperstumia pasirinkto intervalo. Tuščiam intervalui rodomos tuščios būsenos. Eksporto pilnumas visam pasirinktam intervalui patvirtinamas tik tada, kai eksportas jį iš tiesų apima.

Dalyvių sąrašas naudojamas tik auditorijos skaičiavimams. Nepilnas ar nežinomas sąrašas nėra surinkimo filtras; procentai lieka neapskaičiuoti. Patikimiems auditorijos rodikliams papildomai reikalingi konkrečių pratybų paskyrų sąrašai su neaktyviais nariais, jų galiojimo laikas ir įrašų matomumo / gavėjų duomenys.

**Dar trūksta:** administratoriaus paleisto eksporto arba jo suteikto SELECT-only priėjimo prie serverio / skaitymo replikos. Šiame kompiuteryje nėra serverio SSH ar duomenų bazės prieigos; eksportuotojas tikrintas Ruby sintaksės ir sintetinio importo lygmeniu, ne paleistas tikroje Rails / PostgreSQL aplinkoje. Paskyros sesija ir OpenAI raktas šios teisės nepakeičia.

Eksportas apima serverio bazėje esančius, ne iš kitų podų dar negautus ar pašalintus įrašus. Į jį neįtraukiami privatūs tarpasmeniniai pokalbiai. Jei vienu metu vyksta kelios pratybos, jų atribojimui reikia serverio patvirtinto turinio priskyrimo, ne autorių sąrašo filtro.

Eksportuojami medijos adresai, ne vieša failų kopija. Jei originalus serveris neleidžia jos gauti, reikia administratoriaus autorizuoto medijos perdavimo; prieiga neapeinama. AI teksto bandymai taip pat netampa paveikslėlių ar vaizdo įrašų analize.


## Tikrų miniatiūrų pateikimas · 2026-10-21

Patikrinus 3 šaltinio nuotraukas nustatyta: HTTPS atsakymuose yra tikri WEBP duomenys, bet `Content-Type: text/plain` ir `X-Content-Type-Options: nosniff`. Signale pridėtas apsaugotas vietinis atvaizdavimo kelias (`private_media.py`): jis naudoja esamą autorizuotą sesiją, patikrina rastrinio failo signatūrą ir pateikia teisingą `image/webp` tipą tik tikslų loopback Host ir antraštės žymą turinčiai užklausai. Kitos užklausos gauna 403. Leidžiami tik dabartinėje autorizuotai gautoje kopijoje esantys medijos adresai iš konfigūruoto podo. Nežinomas šaltinis, įrašas, indeksas ar kitas domenas nesuteikia priėjimo. Vieša medijos kopija nekuriama; turinys lieka ribotoje proceso atmintyje. Originalo nuorodos nepakeičiamos. Tai pateikimo pataisa, ne medijos AI analizė ar platesnė platformos prieiga.


## Nuotraukų analizė ir eilių paskirstymas (2026-10-24)

Įrašas su nuotraukomis lieka vienu analizės vienetu. Luna „medium“ vertina tekstą ir prieinamas nuotraukas kartu; SOL „medium“ papildomai peržiūri atrinktą neaiškų turinį. Eilės gauna pakaitinius vykdymus. Nauji ir pasikeitę vienetai aptarnaujami prieš senesnį nuotraukų laukimą. Analizė saugoma po kiekvieno vieneto, o rankinis sprendimas turi pirmenybę.

Originalios nuotraukos gaunamos su esama Diasporos autorizacija ir perduodamos OpenAI kaip privatūs `input_image` duomenys. Pirmenybė originalui, miniatiūra – atsarginė. Ribos vienam vertinimui: 4 nuotraukos, 12 MiB, 35 sekundžių gavimo biudžetas. Nei nuotraukų baitai, nei base64 neįrašomi į istoriją ar Neon. Trūkstami, per dideli, animuoti GIF ir vaizdo klipai neapsimetami peržiūrėtais. Garsas ir išorinės vaizdo nuorodos neanalizuojami. Vizualinis įrodymas turi patikrintą `VAIZDAS[id:indeksas]` nuorodą ir matomo požymio aprašymą; tai ne teksto citata.

Atidaryta autorizuota aplikacija gali inicijuoti jau vėluojantį valandinį rinkimą prieš kitą analizės paketą. Uždarius aplikaciją lieka GitHub Actions pažadinimas, kurio tikslus laikas negarantuojamas.
