"""Prospective organizer rule for explicitly fictional exercise accounts.

This is scenario scoring, not an inference about real people's political beliefs.
No roster, source content or extra analysis queue is persisted by this module.
"""
from exercise_accounts import current, matches

ID = 'organizer-exercise-activity-v1'
TRIGGERS = ('none', 'protest_organized_or_supported', 'scenario_institution_criticized')
INSTRUCTIONS = (
    'exercise_scoring_rule yra aiškiai organizatoriaus nustatyta fiktyvių pratybų vertinimo taisyklė, '
    'o ne objektyvus politinės veiklos pavojingumo ar realaus asmens pažiūrų vertinimas. '
    'exercise_rule_trigger nustatyk pagal paties vertinamo įrašo ar komentaro autoriaus išreikštą poziciją: '
    'protest_organized_or_supported – organizuoja arba palaiko protestą ar mitingą; '
    'scenario_institution_criticized – kritikuoja oficialią scenarijaus valdžią arba šaulius. '
    'Taisyklė neapima kitų institucijų savaime. Pranešimas apie įvykį, kito žmogaus citata, klausimas '
    'ar kritikos paneigimas nėra automatinis autoriaus palaikymas; neradus aiškaus požymio rinkis none. '
    'Nespręsk iš paskyros vardo, numanomų ketinimų ar vien temos. Kasdienis, šeimos ir laisvalaikio '
    'turinys lieka vertinamas įprastai. Kai požymis aiškus, evidence pateik tikslią jo ištrauką '
    'iš paties įrašo arba peržiūrėtos jo nuotraukos; ne pirminio įrašo ar kito autoriaus komentarą. '
    'Kryptį pirmiausia įvertink pagal bendrąsias gaires. Serveris atskirai pritaikys organizatoriaus '
    'D5 taisyklę tik patvirtintam scenarijaus požymiui, išsaugodamas priskyrimo kilmę.'
)


CONTENT_RULE_ID = 'organizer-exercise-content-v2'
CONTENT_TRIGGERS = ('not_unrelated_daily_life', 'unrelated_daily_life', 'unclear')
CONTENT_INSTRUCTIONS = (
    'exercise_scoring_rule yra tik fiktyvių pratybų organizatoriaus vertinimo susitarimas, '
    'ne realaus asmens politinių pažiūrų ar pavojingumo nustatymas. Ši taisyklė taikoma tik '
    'serverio tiksliai susietoms organizatoriaus pateiktoms pratybų paskyroms. '
    'Pirmiausia įvertink nepriklausomą turinio kryptį pagal bendrąsias gaires. '
    'Atskirai exercise_rule_trigger nustatyk iš viso vieneto teksto, jo peržiūrėtų nuotraukų '
    'ir reikalingo ankstesnio diskusijos konteksto. unrelated_daily_life galima tik tada, '
    'kai visas turinys yra aiškiai nesusiję kasdieniai poreikiai ar neutralus laisvalaikis '
    'ir nėra jokios prasminės sąsajos su pratybų įvykiais, institucijomis, politika ar '
    'kitomis viešosios situacijos aplinkybėmis. Vien kasdienybės žodžių nepakanka: '
    'šeimos, buities ar laisvalaikio tekstas su politine užuomina, institucijų paminėjimu '
    'ar nuoroda į vykstančius įvykius šios išimties neatitinka. Vertink prasmę originalo '
    'kalba, įskaitant ironiją, mišrią kalbą ir trumpus komentarus. '
    'not_unrelated_daily_life reiškia, kad ši siaura išimtis netaikoma: serveris priskirs '
    'destabilizuojančią kryptį pagal organizatoriaus taisyklę net jei nepriklausomas '
    'turinio vertinimas neutralus ar stabilizuojantis. Tai apima ir faktinį pranešimą, '
    'klausimą, citavimą, paneigimą ar palaikymą, susijusį su viešąja situacija; '
    'šio organizatoriaus susitarimo nepristatyk kaip nepriklausomo žalingumo įrodymo. '
    'Pateik tikslią paties vertinamo vieneto ištrauką arba jo peržiūrėto vaizdo požymį; '
    'pirminio įrašo ar kito autoriaus tekstas gali tik paaiškinti sąsają. '
    'Jei negali patikimai nustatyti, ar išimtis tinka, rinkis unclear; nežinomų faktų '
    'ir neperskaitytos medijos nespėk. unrelated_daily_life atveju lieka įprastas '
    'turinio vertinimas; pavojingas ar smurtą kurstantis buitinis turinys netampa '
    'neutraliu vien dėl kasdienės temos. Rankiniai sprendimai visada viršesni.'
)


def triggers(scoring_rule):
    return CONTENT_TRIGGERS if scoring_rule.get('id') == CONTENT_RULE_ID else TRIGGERS


def instructions(scoring_rule):
    return CONTENT_INSTRUCTIONS if scoring_rule.get('id') == CONTENT_RULE_ID else INSTRUCTIONS


def for_unit(repo, unit, *, thermometer_only=False, review_rule_id=None):
    state = current(repo)
    rule = state.get('scoring_rule') if state else None
    historical = bool(rule and review_rule_id == rule.get('id') and rule.get("historical_review_enabled") is True)
    if ((thermometer_only and not historical) or not matches(state, unit) or not isinstance(rule, dict)
            or rule.get('id') not in (ID, CONTENT_RULE_ID) or rule.get('enabled') is not True
            or not rule.get('effective_at') or not hasattr(repo, 'supplement_eligible')):
        return None
    if not historical and not repo.supplement_eligible(unit, rule['effective_at']):
        return None
    return {'id': rule['id'], 'provenance': 'exercise_organizer',
            'scope': 'fictional_exercise_only', 'category': 'destabilizing', 'reason_code': 'D5'}


def apply(result, rule, trigger, unit, *, visual_refs=()):
    """Only a supported, complete unit can acquire an explicitly attributed scenario label."""
    if not rule or result.get('direction') == 'needs_review':
        return None
    if trigger not in triggers(rule):
        result.update(direction='needs_review', reason_codes=[], missing_context=
                      'Nežinomas organizatoriaus taisyklės požymis.')
        return None
    if rule.get('id') == CONTENT_RULE_ID:
        if trigger == 'unclear':
            result.update(direction='needs_review', reason_codes=[], missing_context=
                          'Neaišku, ar turinys atitinka nesusijusios kasdienybės išimtį.')
            return None
        if trigger == 'unrelated_daily_life':
            return None
    elif trigger == 'none':
        return None
    from vision_input import visual_evidence
    evidence = result.get('evidence', '').strip()
    own_refs = visual_refs
    if not evidence or (evidence not in (unit.get('text') or '') and not visual_evidence(evidence, own_refs)):
        result.update(direction='needs_review', reason_codes=[], missing_context=
                      'Pratybų taisyklės požymiui trūksta paties turinio ištraukos arba peržiūrėto vaizdo.')
        return None
    original_direction = result['direction']
    result.update(direction='destabilizing', reason_codes=['D5'], missing_context='',
                  reason='Priskirta pagal organizatoriaus pratybų taisyklę (D5), o ne nepriklausomą politinės veiklos vertinimą. ' + result['reason'])
    return {**rule, 'trigger': trigger, 'applied': True, 'content_direction': original_direction}
