# Greitas rankinis termometro patvirtinimas

`thermometer_review.save` konkretaus šaltinio vienetą, jo pirminį įrašą ir reikalingus ankstesnius komentarus gauna per `Repository.analysis_units`. Visas surinktas srautas nebeskaitomas. Išlieka tie patys turinio atspaudo, konteksto, laiko ribos ir originalo nuorodos patikrinimai. Sprendimas atominiu būdu išsaugomas toje pačioje Neon vietoje; ankstesni sprendimai ir jų pagrindimai neperkeliami ir netrinami.

Tik sėkmingai užbaigus DB įrašymą, API grąžina `saved` bei kompaktišką išsaugoto vieneto `assessment`. Sąsaja šį serverio patvirtintą sprendimą pritaiko atmintyje laikomam rodiniui, iškart perskaičiuoja kategorijų dalis, aprėptį, laukiančiųjų kiekius bei dienos proporcijas ir parodo išsaugojimo patvirtinimą. Pakartotinis jau įvertinto vieneto koregavimas aprėpties nepadidina. Procentų apvalinimas atitinka serverio Python `round(..., 1)`.

Paspaudus išsaugoti nebekviečiamas visas `/api/thermometer` rodinys. Bendras serverio rodinys toliau sinchronizuojamas esamu periodiniu foniniu atnaujinimu. Iki patvirtinimo pradėtas pavėlavęs skaitymas negali perrašyti naujo sprendimo ar jo talpyklos. Išlaikomas pasirinktas turinio filtras ir laikotarpis. Nesėkmingas išsaugojimas nepakeičia rodomos kategorijos ir palieka formą pakartotiniam bandymui.

Tai nekeičia AI klasifikavimo taisyklių, paskyrų rolių, retrospektyvių eilių, duomenų bazės schemos ar istorinių vertinimų. Nauja reali turinio klasifikacija testavimo metu nesukuriama; DB rašymo ir nesėkmių patikros vykdomos su sintetinėmis saugyklomis.
