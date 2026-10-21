# Rodiklių ir auditorijos auditas · 2026-10-20

## Kas patikrinta ir kas veikia

Šis dokumentas pradžioje aprašė auditą iki „Platformos apžvalgos“ sukūrimo. Pagal vėlesnę vartotojo užduotį pridėta ši skiltis ir demonstracinis autorių reitingas; dabartinis įgyvendinimas aprašytas README skyriuje „Platformos apžvalga“. Tiesioginis platformos srautas vis dar neprijungtas.

SQLite `/api/posts` turi tik šaltinį, išorinį ID, datą, tekstą, naratyvą, poziciją ir demo žymą. Jame nėra pratybų ID, narių, autorių, matomumo ar sąveikų paskyrų duomenų. Vėliau pridėti neprivalomi sourceUrl, parentSourceUrl ir kind laukai. Importuotų įrašų statistika ir sąsajos sintetiniai agregatai tebėra atskiri. Sintetinių agregatų negalima naudoti tikrų įrašų dubliams ar realiai unikaliai auditorijai nustatyti.

Pataisyti veikiančios sąsajos skaičiavimai:

- Dienos pozicijų sintetiniai kiekiai paskirstomi sveikais vienetais didžiausios liekanos metodu. Nebelieka neigiamos paskutinės kategorijos, kai mažiems kiekiams nepriklausomai apvalinamos pirmos kategorijos. Suma lygi dienos turinio kiekiui.
- Naratyvo pozicijų dalys sąrašuose, detalėse ir CSV gaunamos iš pasirinkto laikotarpio įvertintų sintetinių vienetų. Pradinės `stance` reikšmės lieka tik demo paskirstymo svoriais, ne automatine klasifikacija. Jei įvertintų vienetų nėra, procentas nežinomas; grafiko juosta tuščia.
- Grafiko skalė prisitaiko ir prie 1–5 vienetų, nebeapvalinama tik šimtais. Nuliniai naratyvų kiekiai žemėlapyje nebesukuria `NaN` spindulio.
- Augimas tebėra `(dabartinis − ankstesnis) / ankstesnis × 100`, lyginant iškart gretimus vienodos trukmės langus. Nulinė ar nežinoma bazė neturi procento ir ženkliuko. Procentas nerodo įsitraukusių žmonių dalies augimo.
- Termometro procentai patikrinti: kategorijos kiekis / įvertintų turinio vienetų kiekis × 100. „Reikia peržiūros“ neįtraukiama į kategorijų vardiklį. Kasdienis ir su naratyvais nesusijęs turinys įtraukiamas.

## Bendros formulės paruoštame Python modulyje

`metrics.py` yra būsimos integracijos skaičiavimo vieta; tiesioginės prieigos prie socialinės erdvės nevykdo.

1. Įrašo kitų narių įsitraukimas: unikalios sąveikų paskyros, priklausančios tinkamai pratybų auditorijai ir galėjusios matyti įrašą, išskyrus autorių / ta pati auditorija be autoriaus × 100. Kartojami komentarai, patiktukai ir pasidalijimai iš vienos paskyros skaitiklio nedidina. Išorinės / neįtrauktos paskyros nepridedamos. Rodiklis matuoja galėjusią matyti auditoriją, ne faktines peržiūras.
2. Naratyvo / autoriaus bendra unikali auditorija: tinkamų auditorijų sąjunga ir įsitraukusių paskyrų sąjunga per visus pasirinktus įrašus. Per įrašus pasikartojantys žmonės pašalinami. Autorius pašalinamas konkretaus įrašo lygiu; kito autoriaus įraše jis gali būti kitas narys.
3. Absoliutūs įrašų ir komentarų kiekiai deduplikuojami pagal `(exercise_id, source, kind, id)`. Sąveikų kiekiai pagal `(exercise_id, source, kind, action_id)` išlaiko atskirus komentarus, patiktukus ir pasidalijimus. To paties žmogaus 100 skirtingų komentarų lieka 100 komentarų. Tie patys pakartotinai gauti veiksmai neskaičiuojami dar kartą.
4. Neprivalomas aktyvumas 100 narių: turinio vienetai / priskirti pratybų nariai × 100. Gali viršyti 100; tai nėra žmonių procentas. Tinkamas palyginimui tik esant suderintiems laikotarpiams ir pilnam turinio rinkiniui.
5. `author_median` / `author_statistics` pagal naujausią reikalavimą skaičiuoja medianą iš VISŲ atrinktų laikotarpio originalių autorinių įrašų auditorijos procentų, įskaitant nulio sąveikų įrašus; aktyvus įrašas turi bent vieną kito nario sąveiką. Komentarai ir paprasti persidalijimai nelaikomi originaliais autoriniais įrašais. Kai bent vieno atrinkto įrašo procentui trūksta duomenų, bendros medianos nepateikia — neišmeta tokio įrašo tyliai.

Kiekvienas skaičiavimas gauna konkrečių pratybų duomenis. `snapshot.complete` turi būti `true`; `assigned_account_ids` apima ir neaktyvias paskyras. `valid_from ≤ published_at < valid_until` privalo galioti. Be datos, tinkamo istorinio sąrašo ar matomumo duomenų auditorija nežinoma. Skirtingų narystės intervalų turinį būsimas adapteris turi susieti su atitinkamais momentiniais sąrašais; vienas netinkamas sąrašas nesuteikia procento visam rinkiniui.

Tuščia patvirtinta auditorija atskiriama nuo nežinomos. Abiem atvejais procentas `null`, ne 0 % ir ne spėjamas narių skaičius. Įsitraukimo skaičiavimui reikalingas pilnas sąveikų paskyrų sąrašas, ne vien skaitikliai. Įvesties įrašus bei sąveikas pagal pasirinktą laikotarpį atrenka būsimas adapteris; šie pagalbiniai metodai laiko lango nepasirenka.

Minimalus paruoštas kontraktas:

```json
{
  "membership": {
    "exercise_id": "exercise-A", "complete": true,
    "valid_from": "2026-10-13T00:00:00Z", "valid_until": "2026-10-20T00:00:00Z",
    "assigned_account_ids": ["person-guid-1", "person-guid-2"]
  },
  "post": {
    "exercise_id": "exercise-A", "source": "diaspora.sauliai.lt", "id": "post-guid",
    "kind": "post", "author_id": "person-guid-1", "published_at": "2026-10-19T10:00:00Z",
    "visibility": "restricted", "visible_account_ids": ["person-guid-1", "person-guid-2"],
    "url": "https://diaspora.sauliai.lt/posts/post-guid",
    "interactions_complete": true,
    "interactions": [{"id": "comment-guid", "kind": "comment", "account_id": "person-guid-2"}]
  }
}
```

`all_assigned` galima naudoti tik patvirtinus, kad galėjo matyti visos konkrečių pratybų paskyros. `interactions_complete` taikoma tik gavus visus reikiamus sąrašus; pradinių 30 patiktukų ar vien skaitiklių neužtenka.

## Augimo bandomieji slenksčiai

Vienintelis nustatymų šaltinis — `dist/metrics-context.json`. API `/api/metrics/context` skaito tą patį failą. Nėra atskiro nustatymų ekrano.

- Ankstesnis kiekis bent 1.
- Absoliutus prieaugis bent `max(3, ceil(auditorija × 0.01))`.
- Procentinis prieaugis bent 50 %.

Visi kriterijai taikomi kartu. 3 vienetų minimumas mažina pavienių veiksmų įtaką, 1 % pritaiko minimalų kiekį didesnei pratybų erdvei. Tai produkto bandymo pasirinkimas, ne statistinio reikšmingumo įrodymas; 50 % neleidžia žymėti vien didelės absoliučios bazės menko santykinio pokyčio.

| Pratybų auditorija | Minimalus prieaugis | 2 → 5 | 10 → 15 |
| --- | --- | --- | --- |
| 100 | 3 | rodyti | rodyti |
| 250 | 3 | rodyti | rodyti |
| 500 | 5 | nerodyti | rodyti |
| 1000 | 10 | nerodyti | nerodyti |

Jeigu auditorija nežinoma, 0 arba netinka turinio `exercise_id`, ženkliukas nevertinamas. Skaičiavimo modulis perskaičiuoja pagal įvestą pratybų kontekstą ir laikotarpį; nenaudoja ankstesnio persijungimo vardiklio. Paaiškinimas išlaiko tikruosius palyginimo kiekius, procentą ir demonstracinę žymą. Dabartiniai demo naratyvai neturi tikro pratybų auditorijos susiejimo; jo neįvedėme išgalvotai, todėl sąsajoje jų ženkliukai paslėpti, o duomenų trūkumas nurodomas.

## „diaspora*“ patikra

2026-10-20 prisijungta vartotojo pateikta paskyra ir perskaitytas vienas prieinamas įrašo JSON. Įraše yra `guid`, `created_at`, `author.guid`, `public` ir `interactions` su komentarų, patiktukų bei pasidalijimų sąrašais / skaitikliais. Konkrečiame atsakyme nėra pratybų ID, pilno pratybų narių sąrašo ar privataus įrašo visų gavėjų sąrašo. Platformoje matomas ankstesnis / testinis turinys savaime nepriskiriamas būsimoms pratyboms. Jo tekstai, slaptažodžiai, sesijos ir paskyrų sąrašai projekte nesaugoti.

Puslapio nurodyto leidimo kodas — [ea6c79a](https://github.com/diaspora/diaspora/tree/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8). Tai patikros metu puslapyje nurodyta kilmė, ne serverio vidinių pakeitimų nebuvimo garantija.

- [PostPresenter](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/presenters/post_presenter.rb) pradinis HTML gali pateikti iki 30 patiktukų / pasidalijimų; vien šio rinkinio nepakanka unikaliai auditorijai. `public: false` nepasako, kiek ar kurios paskyros galėjo matyti įrašą.
- [PostInteractionPresenter](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/presenters/post_interaction_presenter.rb) pateikia sąveikas ir atskirus absoliučius skaitiklius. Jie nėra unikalių žmonių skaičius. [Post JSON](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/controllers/posts_controller.rb) naudoja `with_interactions`; ši prieiga ribojama prisijungusio vartotojo matomumu.
- [AspectsController](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/controllers/aspects_controller.rb) aspektai priklauso `current_user`. Vieno stebėtojo aspektas ar kontaktų sąrašas nėra patvirtintas visų pratybų narių registras ir neatskleidžia kitų autorių pasirinktų gavėjų.
- [AdminsController](https://github.com/diaspora/diaspora/blob/ea6c79a94cb2e3d73e3fe28cd81fa09c5c437cb8/app/controllers/admins_controller.rb) bendras `User.count` yra serverio paskyrų skaičius, ne konkrečių pratybų auditorija. Jo nepanaudojome vardikliu.

Prieš patikimą tiesioginę integraciją dar reikia: autoritetingo pratybų ID ir priskirtų paskyrų sąrašo su neaktyviais nariais, narystės galiojimo intervalų, privačių įrašų gavėjų / matomumo informacijos ir pilnų sąveikų ID, autorių bei datų. Paskyrų GUID turi būti vienodai naudojami narystėje ir sąveikose. Kol šių duomenų nėra, API išlaiko `missing`, o ne nustato auditoriją pagal srauto aktyvumą. Tiesioginis rinkimas, autentifikavimo raktų saugojimas ir automatinė AI analizė neprijungti.

## Patikrinimas

`python3 -m unittest discover -s tests -v` tikrina API ir Python skaičiavimus; JS rinkiniai `test_growth.cjs`, `test_counts.cjs`, `test_exercise_context.cjs` tikrina naratyvų statistiką bei bendrą sąsajos prieigą. Įtraukti 5/100 = 5 %, 5/250 = 2 %, 5/500 = 1 %, 100 komentarų iš 5 paskyrų, neaktyvūs nariai, autorius, ribotas matomumas, dublių pašalinimas tarp įrašų, nulinė / nežinoma auditorija, istoriniai sąrašai, persijungimas tarp pratybų, medianos pilnumas, maži kiekiai bei laikotarpio keitimas. Interaktyvus lokalaus prototipo valdymas šiame audite neatliekamas pagal ankstesnį vartotojo pageidavimą; programinės patikros to nepakeičia.
