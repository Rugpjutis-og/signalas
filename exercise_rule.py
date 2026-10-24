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


def for_unit(repo, unit, *, thermometer_only=False, review_rule_id=None):
    state = current(repo)
    rule = state.get('scoring_rule') if state else None
    historical = bool(rule and review_rule_id == ID and rule.get("historical_review_enabled") is True)
    if ((thermometer_only and not historical) or not matches(state, unit) or not isinstance(rule, dict)
            or rule.get('id') != ID or rule.get('enabled') is not True
            or not rule.get('effective_at') or not hasattr(repo, 'supplement_eligible')):
        return None
    if not historical and not repo.supplement_eligible(unit, rule['effective_at']):
        return None
    return {'id': ID, 'provenance': 'exercise_organizer',
            'scope': 'fictional_exercise_only', 'category': 'destabilizing', 'reason_code': 'D5'}


def apply(result, rule, trigger, unit, *, visual_refs=()):
    """Only a supported, complete unit can acquire an explicitly attributed scenario label."""
    if not rule or trigger == 'none' or result.get('direction') == 'needs_review':
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
