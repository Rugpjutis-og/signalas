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
    "D4": "Aiškus demokratinio dalyvavimo ar saugumo griovimas",
}
BY_CATEGORY = {
    "neutral": frozenset(("N0", "N1", "N2")),
    "stabilizing": frozenset(("S1", "S2", "S3", "S4")),
    "destabilizing": frozenset(("D1", "D2", "D3", "D4")),
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
