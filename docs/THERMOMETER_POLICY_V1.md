# Termometro klasifikavimo taisyklės (v1.0)

Šiame etape „Nuotaikų termometras“ vertina paskelbto turinio komunikacinę kryptį, ne autoriaus ketinimus, nuotaiką ar auditorijos pažiūras. Vienas įrašas su savo medija yra vienas vienetas, komentaras – atskiras vienetas. Naratyvo priskyrimas, autoriaus vardas, sekėjai ir sąveikų kiekis kategorijos nenulemia. Išplėstiniai naratyvai, kai bus pateikti, gali būti perduodami tik kaip papildomas kontekstas, o ne kaip patvirtinti faktai.

`thermometer_policy.py` laiko vienoje vietoje taisyklių versiją ir pagrindo kodus. Neutralus turinys apima kasdienius įrašus, klausimus ir taikią kritiką. Stabilizuojančiai krypčiai būtinas S1–S4 mechanizmas, destabilizuojančiai – D1–D5. S1 ir D1 vertinami pagal turinį bei pateiktą kontekstą: atskira išorinio šaltinio nuoroda nereikalinga, vien šie kodai neperkelia įrašo peržiūrai. Trūkstant būtino fakto paliekama peržiūra; kontekste nepaminėtas teiginys savaime nėra klaidingas. Citata ar paneigimas nėra autoriaus palaikymas.

Galutinės kategorijos turi tik `classified` rezultatai. `waiting_data`, `needs_review` ir `error` neturi kategorijos. Seno taisyklių formato rezultatai į naujus termometro procentus neįtraukiami. Procentų vardiklis – tik klasifikuoti vienetai; aprėptis rodoma atskirai. Kai klasifikuotų vienetų nėra, procentai nežinomi. Maža imtis ir maža aprėptis žymimos sąsajoje.

AI jungtis vis dar yra **tik tekstinis, rankiniu būdu paleidžiamas bandymas**. Ji neanalizuoja prisegtų paveikslėlių, garso ar vaizdo, automatiškai nerengia OCR, transkripcijų ar faktų patikros. Neperskaityta susijusi medija siunčiama į `waiting_data`. Automatinio tikslaus pakartotinio bandymo, žmogaus peržiūros darbo eigos ir sužymėtos kokybės imties kol kas nėra. Tikrų pratybų tikslumo ir v1.0 ribų patvirtinti negalima. Joks automatinis API kvietimas ar DB migracija šiomis taisyklėmis nepridėta.

## Komunikacinio mechanizmo patikslinimas (2026-10-24)

D3 apima ir viešai veikiančioms institucijoms / organizacijoms primetamą kolektyvinę piktybišką veiklą. D4 gali apimti visuotinio apleistumo, bejėgiškumo ir saugios išeities nebuvimo formavimą. Agresyvių veiksmų raginimas šioms kryptims nebūtinas. Informacijos, paaiškinimų ir saugumo lūkestis taikomas valdžiai, savivaldybei, kariuomenei, žiniasklaidai, žurnalistams ir kitoms viešai veikiančioms organizacijoms; tai nėra uždaras sąrašas.

Vien aštrumas, didelis nepasitikėjimas, neigiamas tonas ar neigiama nuomonė apie šalį nenulemia kategorijos. Konkretus reikalavimas paaiškinti veiksmus ar atsiskaityti gali likti N1, net jei valdžia nepasitikima. Palaikymas ir pasitikėjimas taip pat savaime nesuteikia stabilizuojančios kategorijos. Vertinama visa komunikacinė reikšmė, citavimas, ironija ir pateiktas kontekstas, o ne raktažodžiai ar autoriaus ketinimai. Modelis turi įvardyti konkretų mechanizmą ir jį pagrindžiančią originalią ištrauką.

Bendros gairės bei iliustraciniai, o ne mechaniškai taikomi pavyzdžiai yra `thermometer_policy.py`. `GUIDANCE_REVISION` įrašoma naujame AI rezultate ir pateikiama tiek įprastai analizei, tiek Sol pakartotinei termometro peržiūrai. Išsaugoti rankiniai sprendimai ir ankstesni rezultatai neperrašomi, automatinė masinė mokama analizė nesukuriama.

## D5 papildymas (2026-10-24)

„D5 – Antisisteminis naratyvas“ pasirenkamas destabilizuojančios krypties rankinio patvirtinimo ir koregavimo formose; serveris išsaugo jį tuo pačiu Neon mechanizmu. Naujo turinio AI schemoje kodas taip pat leidžiamas, tačiau jam reikia konkretaus turinio ir konteksto pagrindo: demokratinių procesų, teisių ar viešojo saugumo griovimo mechanizmo. Taikus protestas, opozicija, kritika ar autoriaus vaidmuo savaime nėra D5.

Priedas nekeičia `VERSION`, turinio ar konteksto susiejimo ir nekuria istorinių įrašų pakartotinės analizės eilės. Ankstesni AI bei rankiniai sprendimai lieka galiojantys. Nauji rezultatai žymimi gairių revizija `2026-10-24.3`; atskiros anksčiau autorizuotos baigtinės peržiūros nėra paleidžiamos iš naujo.

## Organizatoriaus fiktyvių pratybų taisyklė

Tik privačiame `exercise-account-context.json` esančioms, tiksliais šaltinio GUID susietoms paskyroms organizatorius patvirtino atskirą scenarijaus taisyklę: protesto / mitingo organizavimas ar palaikymas arba oficialios scenarijaus valdžios / šaulių kritika priskiriami D5. Tai pratybų vertinimo susitarimas, o ne realių asmenų politinių pažiūrų ar taikaus protesto pavojingumo nustatymas.

`exercise_rule.py` taikomas tik įprastai naujo / iki aktyvavimo neįvertinto turinio analizei. Tikslinio seno turinio Sol peržiūros režime jis išjungtas. Ankstesnius AI / rankinius sprendimus nuo pakeitimo saugo aktyvavimo laikas ir esamas `supplement_eligible` patikrinimas; jokia nauja analizės eilė nekuriama. Taisyklė saugoma toje pačioje Neon būsenoje lauke `scoring_rule`; visos 50 paskyrų lieka privačioje bazėje.

AI nustato aiškų paties autoriaus turinio požymį ir pateikia tikslią ištrauką, o serveris taiko organizatoriaus D5 priskyrimą. `none`, neaiškus turinys, trūkstama medija ir svetimos ištraukos priverstinio priskyrimo nesukuria. Rezultato `exercise_rule_application` išsaugo taisyklės ID, kilmę, požymį ir nepriklausomo turinio vertinimo kryptį; vartotojui paaiškinime rodoma, kad kategorija skirta pagal organizatoriaus pratybų taisyklę. Rankinis sprendimas išlieka viršesnis. Naratyvų atpažinimas nekeičiamas.
