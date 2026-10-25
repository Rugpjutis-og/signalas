# Atidėta neutralaus ir stabilizuojančio turinio peržiūra

Vienkartinė organizatoriaus užklausa saugoma Neon `thermometer-followup.json`. Esamas Vercel foninis vykdytojas pradeda ją tik kai pagrindinės analizės `analysis-job.json` būsena yra `complete` ir ankstesnė termometro peržiūra taip pat užbaigta. Klaida, sustabdymas ar vien nulinis nepatikimas skaitiklis nelaikomas užbaigimu. Nauja automatika ar vietinis procesas nekuriamas.

Po bendro DB užrakto gavimo pasirengimas patikrinamas dar kartą. Atranka apima visą dabartinį surinktą manifestą, nepriklauso nuo ekrano datų filtro. Iš naujausio taikomo AI rezultato atrenkami tik `classified` neutralūs ir stabilizuojantys vienetai, išrikiuoti pagal paskelbimą mažėjančia tvarka. SQL grąžina tik ID, kontrolinį atspaudą ir reikalingus metaduomenis, ne visus tekstus ar analizės istoriją. Jei naujesnis rezultatas destabilizuojantis arba neklasifikuotas, senas neutralus rezultatas neatgaivinamas. Galiojantys rankiniai patvirtinimai praleidžiami.

Prieš mokamą SOL vertinimą dar kartą tikrinamas turinio ir pratybų atitikimas, rankinis sprendimas ir dabartinė kategorija. Naratyvų rezultatai išlaikomi. Nuo naujausių einantis eiliškumas nekeičiamas į tekstinių / medijos pakopas. Toliau atvykę nauji įrašai gauna esamą pagrindinės analizės prioritetą 3:1.

Užklausa aiškiai leidžia šiai baigtinei termometro peržiūrai naudoti užfiksuotą naują scenarijaus papildymo ID ir aktyvią organizatoriaus paskyrų taisyklę. Tai nekeičia bendro scenarijaus papildymo taikymo tik naujiems įrašams. Pakeitus pradinį kontekstą, papildymo ID ar paskyrų taisyklę prieš startą, užklausa sustoja peržiūrai. Pasikeitęs papildymas vykdymo metu taip pat sustabdo šią peržiūrą.

Ankstesnis vertinimas lieka iki tinkamo naujo klasifikuoto rezultato. Neaiškus atsakymas, modelio ar medijos klaida ir nutrūkęs darbas fiksuojami atskirai, neperrašant ankstesnės kategorijos. Vykdymo žymos leidžia atkurti nutrūkusį procesą nekartojant jau išsaugotų mokamų vertinimų. Rankiniai sprendimai lieka aukščiausio prioriteto. Duomenų bazės lentelės nekeičiamos.
