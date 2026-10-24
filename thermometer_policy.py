"""Versioned content-direction contract. These are product rules, not validated accuracy claims."""

VERSION = "1.0"
CATEGORIES = ("stabilizing", "neutral", "destabilizing")
STATUSES = ("classified", "needs_review", "waiting_data", "error")
REASONS = {
    "N0": "Kasdienis arba su scenarijumi nesusijęs turinys",
    "N1": "Nuomonė, kritika ar taikus pilietinis veiksmas be žalingo mechanizmo",
    "N2": "Nepakanka požymių kitai krypčiai, tačiau reikšmė suprantama",
    "S1": "Patikimais duomenimis pagrįstas paaiškinimas ar paneigimas",
    "S2": "Praktiška ir patikima pagalba arba saugaus elgesio nurodymas",
    "S3": "Įtampos mažinimas ir pagarba žmonių orumui",
    "S4": "Demokratinis dalyvavimas, teisės ir solidarumas",
    "D1": "Patvirtintai klaidingas ar iškreiptas žalingas teiginys",
    "D2": "Smurto, diskriminacijos ir neapykantos kurstymas",
    "D3": "Kolektyvinis kaltinimas ar grupės pavertimas priešu",
    "D4": "Demokratinio dalyvavimo ar saugumo griovimas, visuotinio apleistumo ar bejėgiškumo formavimas",
    "D5": "Antisisteminis naratyvas",
}

# Prompt guidance revision is recorded without invalidating saved human decisions
# or silently creating a paid full-dataset reanalysis.
GUIDANCE_REVISION = "2026-10-24.3"
COMMUNICATION_GUIDANCE = (
    "D5 – Antisisteminis naratyvas: taikyk tik kai pats turinys ir pratybų kontekstas pagrindžia raginimą griauti demokratinius procesus, teises ar viešąjį saugumą (pvz., panaikinti rinkimus ar jėga užgniaužti pilietinį dalyvavimą). Pateik konkrečią turinio ištrauką ir paaiškink žalingą mechanizmą. Vien opozicija, nepasitikėjimas, antielitinė retorika, sistemos reformos siūlymas, taikus protestas ar autoriaus pratybų vaidmuo nėra D5 pagrindas; citavimo, pranešimo ir paneigimo neprilygink palaikymui.",
    "Viešai veikiančių institucijų, valdžios, savivaldybės, kariuomenės, žiniasklaidos, žurnalistų ir kitų organizacijų komunikaciją vertink gyventojų saugumo, informavimo, paaiškinimų bei tiesos lūkesčio kontekste. Sąrašas nėra baigtinis.",
    "Destabilizuojančiai krypčiai nebūtinas raginimas agresyviai veikti: D3 gali pagrįsti apibendrinantis kolektyvinės kaltės ar bendros piktybiškos veiklos primetimas; D4 gali pagrįsti visuotinio apleistumo, bejėgiškumo ar saugios išeities nebuvimo formavimas, kai tai aiškiai parodo turinys ir kontekstas.",
    "Atskirk konkretaus neveikimo, tylos ar neinformavimo kritiką bei reikalavimą atsiskaityti nuo visuotinio kaltinimo, kad visos institucijos sąmoningai paliko gyventojus be saugumo, pagalbos ir patikimos informacijos, o jokie paaiškinimai ar veiksmai nebeturi prasmės. Antrajam mechanizmui vertinti neapsiribok vien smurto, neapykantos ar susidorojimo požymiais.",
    "Kritikos aštrumas, emocingumas ar didelis nepasitikėjimas savaime nėra D3 ar D4. N1 nereikalauja pasitikėjimo valdžia: konkreti taiki kritika, informacijos ar atsakomybės reikalavimas gali likti N1 ir be institucijų palaikymo. Neigiama nuomonė apie Lietuvą, valdžią ar kariuomenę savaime nenulemia krypties.",
    "Institucijų palaikymas ar pasitikėjimas savaime nėra stabilizuojantis: suprantamas sprendimas ar taiki palaikymo nuomonė gali būti N1. S kategorijai būtinas konkretus S1–S4 mechanizmas.",
    "Vertink visą pasakymą: klausimas, citata, ironija, pasipiktinimas ar pateiktu kontekstu pagrįstas perspėjimas nėra automatiškai kolektyvinis kaltinimas. Nenaudok vien raktažodžių ar teigiamo / neigiamo tono. Nepriskirk autoriaus ketinimų ir neteigk, kad realus poveikis gyventojams buvo išmatuotas.",
    "Pratybų, Lietuvos šaulių sąjungos, valdžios veiklos ar viešųjų lėšų naudojimo pašaipą ir smerkimą vertink pagal konkretų teiginį, o ne institucijos pavadinimą. Apibendrinantis kaltinimas, kad visa grupė yra vagys ar sąmoningai kenkia, gali pagrįsti D3; pasakojimas, kad visi saugumo ir informavimo kanalai sąmoningai apleido žmones, jokiais sprendimais negalima pasikliauti ir pagalbos nėra, gali pagrįsti D4 net be raginimo smurtauti.",
    "Žodžiai korupcija, neveiksnumas, mokesčių mokėtojų pinigai, nutylėti faktai, informacijos trūkumas ar nepasitikėjimas nėra automatiniai D požymiai. Konkretaus sprendimo ar išlaidų kritika, pašaipa, įtarimo įvardijimas ir prašymas pateikti įrodymus ar paaiškinimus gali būti N1. Kaltinimo korupcija nelaikyk nei patvirtintu faktu, nei melu vien pagal jo toną. Nepaversk visos institucinės kritikos destabilizuojančia ir nenustatyk pageidaujamo D procento.",
    "D3 ar D4 paaiškinime įvardyk konkretų kolektyvinės kaltės, apleistumo ar bejėgiškumo mechanizmą ir pateik jo ištrauką. Nežinomų faktų nepaversk įrodyta melagyste; trūkstant būtino konteksto palik needs_review.",
)
COMMUNICATION_EXAMPLES = (
    {"text": "Kariuomenė nepaaiškino ribojimų, reikia informacijos.", "direction": "neutral", "reason_code": "N1", "basis": "Konkreti taiki kritika ir paaiškinimo reikalavimas; vien nepasitikėjimo nepakanka destabilizuojančiai krypčiai."},
    {"text": "Visos institucijos mus paliko, niekam mūsų saugumas nerūpi, jokiais paaiškinimais negalima tikėti.", "direction": "destabilizing", "reason_code": "D4", "basis": "Jei kontekstas patvirtina tokį komunikacinį mechanizmą, visuotinio apleistumo ir patikimos išeities nebuvimo formavimas galimas ir be raginimo agresyviai veikti; tai nėra automatinė raktažodžių taisyklė."},
    {"text": "Visi žurnalistai yra mūsų priešai ir sąmoningai kenkia gyventojams.", "direction": "destabilizing", "reason_code": "D3", "basis": "Visai grupei primetama kolektyvinė piktybiška veikla ir kuriamas priešo įvaizdis."},
    {"text": "Pasitikiu institucijomis, suprantu jų sprendimą.", "direction": "neutral", "reason_code": "N1", "basis": "Taiki nuomonė; vien palaikymo nepakanka S mechanizmui."},
    {"text": "Šaulių sąjungoje visi vagys: kiekvienos pratybos tik priedanga susižerti mokesčių mokėtojų pinigus.", "direction": "destabilizing", "reason_code": "D3", "basis": "Visiems organizacijos nariams apibendrintai primetama nusikalstama veikla; tai kolektyvinio kaltinimo pavyzdys, o ne faktinis korupcijos patvirtinimas."},
    {"text": "Valdžia ir visos saugumo institucijos sąmoningai mus paliko. Viską nutyli, niekas niekada nepadės, jokiais sprendimais pasikliauti negalima.", "direction": "destabilizing", "reason_code": "D4", "basis": "Formuojamas visuotinis apleistumas ir saugios išeities nebuvimas, o ne vien kritikuojamas konkretus informavimo trūkumas."},
    {"text": "Pratybų organizatoriai nepaaiškino išlaidų. Įtariu korupciją ir nepasitikiu šiuo sprendimu; prašau paskelbti sutartis.", "direction": "neutral", "reason_code": "N1", "basis": "Konkreti atskaitomybės ir informacijos užklausa; nepasitikėjimas ir įtarimas savaime nėra D, o korupcija čia nepatvirtinta."},
    {"text": "Puikios pratybos – informacijos gyventojams nulis! Už ką mokame mokesčius? Paskelbkite aiškų pranešimą.", "direction": "neutral", "reason_code": "N1", "basis": "Pašaipa ir aštri konkretaus neinformavimo kritika su reikalavimu paaiškinti; nėra kolektyvinės piktybiškos veiklos ar visuotinio bejėgiškumo teiginio."},
)

BY_CATEGORY = {
    "neutral": frozenset(("N0", "N1", "N2")),
    "stabilizing": frozenset(("S1", "S2", "S3", "S4")),
    "destabilizing": frozenset(("D1", "D2", "D3", "D4", "D5")),
}


def validate_assessment(value, *, require_evidence=True):
    """Reject unsupported classifications before they reach category denominators."""
    if not isinstance(value, dict) or value.get("status") not in STATUSES:
        raise ValueError("Netinkama termometro vertinimo būsena.")
    category = value.get("category")
    codes = value.get("reason_codes")
    if not isinstance(codes, list) or not all(code in REASONS for code in codes):
        raise ValueError("Netinkami termometro priežasties kodai.")
    if value["status"] != "classified":
        if category is not None:
            raise ValueError("Neįvertintas turinys negali turėti galutinės kategorijos.")
        return value
    if category not in CATEGORIES or not codes or any(code not in BY_CATEGORY[category] for code in codes):
        raise ValueError("Termometro kategorija ir priežastis nesutampa.")
    if not str(value.get("reason") or "").strip():
        raise ValueError("Trūksta termometro vertinimo pagrindo.")
    if require_evidence and category in ("stabilizing", "destabilizing") and not str(value.get("evidence") or "").strip():
        raise ValueError("Kryptingam vertinimui trūksta turinio įrodymo.")
    return value
