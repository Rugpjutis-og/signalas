# Rodinių skaitymas be visos analizės istorijos

Rodinio klaida HTTP 507 kilo, kai vienu Neon HTTP atsakymu buvo agreguojama visa analizės istorija ir viršyta 64 MB perdavimo riba. Istorija netrinama ir analizės duomenų schema nekeičiama.

Debesijos `live_data.load` pateikia dabartinių šaltinio vienetų ID ir tikslius diskusijos kontrolinius atspaudus `Repository.dashboard_analyses`. Metaduomenų puslapiuose iki 1 000 ID Postgres atrenka tik naujausio tinkamo įvertinimo vietą: atskiros eilutės vardą arba seno masyvo indeksą. Atranka tikrina turinį, pradinį kontekstą ir leistiną vykdymo būseną. Patys rezultatai po ne daugiau kaip 100 skaitomi tiesiogiai pagal bazės indeksą, nekartojant visos istorijos skenavimo kiekvienam rezultatų puslapiui. Galiojimo ir eiliškumo kriterijai lieka tokie patys kaip anksčiau: naujo atskiro rezultato pirmenybė prieš senąjį masyvą, vėliau išsaugoto rezultato pirmenybė vienodam atspaudui. Kitos turinio versijos ar pratybų kontekstas nerodomi kaip aktualūs.

Pasikartojantis pradinis kontekstas nesiunčiamas su kiekvienu rezultatu: SQL patvirtina jo atitikimą, o Python atkuria tą pačią reikšmę atmintyje. Rankiniai sprendimai ir toliau taikomi projekcijos pabaigoje, virš AI rezultatų. Naujo vertinimo neprašoma ir jokie ankstesni įrašai nekeičiami.

Platformos apžvalgai naudojama `include_analyses=False`, nes įrašų, komentarų, patiktukų ir pasidalijimų skaičiavimams AI istorija nereikalinga. Vietinės sintetinės failų patikros išlaiko ankstesnį formatą.
