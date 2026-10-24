# Organizatoriaus fiktyvių pratybų turinio taisyklė v2

`organizer-exercise-content-v2` yra atskirai aktyvuojama organizatoriaus vertinimo taisyklė tik jau patvirtintoms pratybų paskyroms. Paskyrų sąrašas ir GUID lieka privačiame Neon įraše `exercise-account-context.json`; jų nėra kode. Tai nėra realių žmonių politinių pažiūrų ar pavojingumo nustatymas.

Organizatoriaus susitarimu turiniui skiriama destabilizuojanti kryptis D5, išskyrus aiškiai nesusijusius kasdienius poreikius ir neutralų laisvalaikį be sąsajos su įvykiais, institucijomis ar politika. Mišrus turinys, pranešimas, klausimas ar citata viešosios situacijos tema išimties neatitinka. Nepriklausoma modelio nustatyta kryptis išsaugoma `exercise_rule_application.content_direction`, o pakeitimo kilmė – `exercise_organizer`. Kodas nėra rankinio patvirtinimo reikalavimas.

Taisyklės versija nekeičia senų rezultatų vien dėl kodo diegimo. Aktyvavimas Neon `scoring_rule` įraše naudoja naują ID, aktyvavimo laiką ir aiškų `historical_review_enabled` leidimą. Vienkartinis `scoring_review_request` sukuria idempotentinę baigtinę jau vertintų vienetų peržiūrą. Ji perima tų pačių vienetų laukiančias ankstesnio leidimo užduotis, išsaugo kitus eilės darbus ir jau atliktų rezultatų istoriją. Aktyvavimas vykdomas tik turint bendrą lease, neužbaigtas vykdymo žymas pirmiausia sutvarko esamas Vercel vykdytojas.

Nauji / dar nevertinti vienetai lieka pagrindinėje Luna eilėje; ankstesnių vertinimų tikslinę peržiūrą vykdo SOL. Išlaikomas esamas santykis 3 pagrindiniai vertinimai : 1 peržiūra. Tikslinės peržiūros viduje pirmiausia tikrinami naujesni tekstiniai vienetai, po jų – vienetai su medija. Turinys renkamas kas valandą kaip iki šiol. Rankiniai sprendimai turi pirmenybę tiek atrenkant tikslus, tiek prieš mokamą vertinimą ir rodant statistiką.

Sena AI kategorija išlieka iki naujo tinkamo klasifikuoto rezultato. Neaiškus išimties taikymas, trūkstama būtina medija, svetima ištrauka ar vertinimo klaida nepriverčia priskirti D5 ir nepakeičia senos kategorijos. Galiojantys rankiniai sprendimai neperrašomi. Naratyvų rezultatai per termometro peržiūrą išsaugomi nepakeisti.
