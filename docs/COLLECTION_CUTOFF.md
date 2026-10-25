# Įrašų ir komentarų paskelbimo riba

Neon `collection-cutoff.json` saugo įtraukiamąją `published_until` ribą su laiko juosta. Organizatoriaus patvirtinta riba: 2026-10-25 12:00 Europe/Vilnius = 2026-10-25 10:00 UTC. Tai vidurdienis, ne vidurnaktis. Dėl tą dieną pasibaigusio vasaros laiko poslinkis yra +02:00. Tiksli ribos akimirka įtraukiama; net vėlesnė sekundės dalis neįtraukiama.

Abiejų Diasporos srautų puslapiavimas prasideda ribos sekunde, naudojant išskirtinį `max_time` ir atskirą tikslų laiko patikrinimą. Įrašo detalės gali pateikti ir vėlesnius komentarus; jie pašalinami prieš išsaugojimą į surinkimo etapą. Ribojami ir komentarai po iki ribos paskelbtais įrašais. Bendras istorinių įrašų limitas nepridedamas.

Naujo rinkimo manifestas pradžioje išlaiko ankstesniame aktyviame manifeste esančius tinkamus vienetus, todėl vien srauto puslapių pasikeitimas jų neišmeta. Pasikeitus ribai, nebaigtas ankstesnės apimties rinkimas nepratęsiamas kaip naujas. Ankstesnė paskelbta imtis ir kanoniniai duomenys netrinami. Pradinis ribos aktyvavimas paskelbia siauresnį manifestą; po ribos jau surinkti duomenys lieka tik esamame archyve, be naujo analizavimo ar rodymo.

Rodinių ir ribotų analizės vienetų skaitymas taiko tą pačią ribą. Todėl jau sudarytų senesnių eilių vėlesni vienetai praleidžiami be mokamo kvietimo. Rankiniai patvirtinimai ir ankstesnės analizės lentelės nekeičiami. Filtrų pasirinktos datos automatiškai nekeičiamos.

Sąveikų sąrašuose lieka tik veiksmai, kurių data žinoma ir neviršija ribos. Istorinis skaitiklis apskaičiuojamas tik esant patvirtintai pilnam atitinkamų veiksmų sąrašui ir jų laiko žymoms. Trūkstami duomenys yra nežinomi, ne nulis. Originalių įrašų tekstų ar medijos istorinių redagavimo versijų Diasporos API neatkuria: riba taikoma paskelbimo laikui, ne pažadui atkurti tikslią serverio būseną praeityje.
