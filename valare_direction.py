"""Scenario-bound stabilization guidance and one authorized historical review."""
import copy
import json
import uuid
from itertools import zip_longest

from narrative_mapping import for_unit as mapping_for_unit, SOURCE, now
from scenario_supplement import context_digest

REVISION = 'valare-stabilizing-2026-10-27'
STATE = 'valare-direction-review.json'
TRIGGERS = ('none', 'separatist_legitimacy_rejected', 'territorial_unity_supported',
            'lithuanian_riflemen_supported', 'unclear')
GUIDANCE = (
    'Patikslinta tik šių fiktyvių pratybų termometro interpretacija: pagal pateiktą VALARE '
    'scenarijų aiškus paties autoriaus separatistinio darinio legitimumo paneigimas, jo '
    'propagandos ar dezinformacijos atmetimas, raginimas netikėti VALARE / Valarės respublika '
    'ar Valarės šauliais, Lietuvos teritorinio vientisumo ir Lietuvos šaulių sąjungos '
    'palaikymas prieš separatistinio darinio primetamą valdžią yra stabilizuojanti komunikacija. '
    'Tai konkretus scenarijaus paaiškinimo / paneigimo (S1) arba solidarumo ir teisėtos '
    'visuomenės sanglaudos (S4) mechanizmas, ne vien bendras institucijos pagyrimas. '
    'Lietuvos šaulių sąjunga nėra tas pats kaip separatistinio darinio Valarės šauliai. '
    'Šių pratybų kontekste „Palaikau Lietuvos šaulių sąjungą“ gali pagrįsti S4 net be '
    'pažodinio VALARE pavadinimo; „Lietuva vientisa, Valarės respublikos nepripažįstu“ '
    'yra aiškus S4 pavyzdys. Vien „Valarėje lyja“ tokio požymio neturi. '
    'Kontekstas leidžia suprasti trumpą komentarą, bet evidence turi būti tiksli paties '
    'vertinamo vieneto ištrauka ar jo peržiūrėtas vaizdas. Ištraukas kopijuok originalo '
    'kalba, neversk ir neperfrazuok. Nemanyk, kad autorius palaiko vien todėl, kad cituoja. '
    'valare_stabilizing_trigger: separatist_legitimacy_rejected – aiškiai atmeta darinio '
    'legitimumą, jo idėjas ar propagandą; territorial_unity_supported – aiškiai palaiko '
    'vientisą Lietuvą šiame separatizmo kontekste; lithuanian_riflemen_supported – aiškiai '
    'palaiko Lietuvos šaulių sąjungą šiame kontekste; none – požymio nėra; unclear – pozicija '
    'neaiški. Nurodyk tik paties autoriaus išreikštą poziciją ir atitinkamą S1 / S4 kryptį. '
    'Vien tylėjimas, neprisidėjimas, neminimas palaikymas, neutralus klausimas ar citata '
    'nėra stabilizuojantis požymis. Neutrali buitis lieka vertinama įprastai. Neperrašyk '
    'smurto, neapykantos kurstymo ar kitų aiškių žalingų mechanizmų į S vien dėl Lietuvos '
    'palaikymo. Jei trūksta būtino konteksto ar neperžiūrėta reikalinga medija, palik peržiūrai. '
    'Šis konkretus stabilizuojantis požymis turi pirmenybę prieš ankstesnį bendrą '
    'organizatoriaus paskyrų D5 susitarimą; nurodytai paskyrai vien dėl jos vaidmens S nekeisk '
    'į D. Rankiniai patvirtinimai lieka viršesni. Naratyvo ID ir pozicija savaime nekeičia '
    'termometro krypties.'
)


def for_unit(repo, unit, context):
    mapping = mapping_for_unit(repo, unit, context)
    if not mapping:
        return None
    return {'revision': REVISION, 'scenario': mapping['scenario'], 'aliases': mapping['aliases'],
            'interpretation': GUIDANCE}


def exception(result, guidance, trigger, unit, *, visual_refs=()):
    """Only consistent content+scenario evidence can bypass the older account D5."""
    from vision_input import visual_evidence
    if (not guidance or guidance.get('revision') != REVISION or trigger not in TRIGGERS[1:-1]
            or result.get('direction') != 'stabilizing' or not result.get('reason_codes')
            or not set(result['reason_codes']).intersection({'S1', 'S4'})):
        return None
    evidence = result.get('evidence', '')
    if not evidence or (evidence not in (unit.get('text') or '') and not visual_evidence(evidence, visual_refs)):
        return None
    return {'revision': REVISION, 'provenance': 'exercise_organizer_context',
            'trigger': trigger, 'category': 'stabilizing', 'scope': 'fictional_exercise_only'}


def needs_service(repo):
    request = repo.read(STATE, {}) or {}
    return request.get('status') == 'requested' and request.get('revision') == REVISION


def candidates(repo, context):
    from cloud_repository import ASSESSMENTS
    rows = repo.sql(ASSESSMENTS + """, latest AS (
      SELECT DISTINCT ON(a->'source_reference'->>'source',a->'source_reference'->>'id') a
      FROM assessments WHERE COALESCE(a->'exercise_context','null'::jsonb)=$2::jsonb
      ORDER BY a->'source_reference'->>'source',a->'source_reference'->>'id',stage DESC,n DESC,
        COALESCE(a->>'recorded_at',a->>'classified_at',a->>'analyzed_at','') DESC
    ), snapshot AS (SELECT packet FROM signalas_fetches WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1)
    SELECT COALESCE(jsonb_agg(jsonb_build_object('source',c.source,'id',c.content_id,
      'content_fingerprint',a->'content_fingerprint','exercise_id',a->'exercise_id',
      'previous_category',a->'result'->'thermometer_category',
      'author_id',c.payload->'author_id','author_handle',c.payload->'author_handle')
      ORDER BY c.payload->>'published_at' DESC,c.content_id),'[]'::jsonb)
    FROM latest JOIN signalas_content c ON c.scope=$1 AND c.source=a->'source_reference'->>'source'
      AND c.content_id=a->'source_reference'->>'id'
    LEFT JOIN signalas_content p ON p.scope=c.scope AND p.source=c.source
      AND p.content_id=c.payload->>'parent_id'
    CROSS JOIN snapshot
    WHERE c.source=$3 AND (c.payload->>'text' ~* '\\mvalar[eė][[:alpha:]]*\\M'
      OR (a->'result'->'narrative_analysis')::text ~* '\\mvalar[eė][[:alpha:]]*\\M'
      OR p.payload->>'text' ~* '\\mvalar[eė][[:alpha:]]*\\M')
      AND a->'result' IS NOT NULL AND a->>'content_fingerprint' IS NOT NULL
      AND COALESCE(a->>'valare_direction_revision','')<>$4
      AND EXISTS(SELECT 1 FROM jsonb_array_elements(packet->'record_keys') ref
        WHERE ref->>'source'=c.source AND ref->>'id'=c.content_id)""",
        [repo.scope, json.dumps(context), SOURCE, REVISION])['rows']
    return json.loads(rows[0][0]) if rows else []


def interleave(old, new):
    return [item for pair in zip_longest(old, new) for item in pair if item is not None]


def maybe_start(repo):
    """Add typed targets under the shared lease, retaining existing paid work."""
    import thermometer_recheck as review
    from openai_analysis import context_data
    from thermometer_review import saved, key
    from thermometer_policy import VERSION
    from narrative_registry import load as registry
    request = repo.read(STATE, {}) or {}
    if not needs_service(repo):
        return request
    owner = uuid.uuid4().hex
    locked = repo.sql("""INSERT INTO signalas_jobs(scope,owner,expires_at)
      VALUES($1,$2,now()+interval '6 minutes') ON CONFLICT(scope) DO UPDATE
      SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
      WHERE signalas_jobs.expires_at<now() RETURNING owner""", [repo.scope, owner])['rows']
    if not locked:
        return request
    try:
        repo.values.clear()
        request = repo.read(STATE, {}) or {}
        if not needs_service(repo):
            return request
        old = repo.read(review.STATE, {}) or {}
        if request['request_id'] in old.get('direction_review_requests', []):
            request.update(old.get('direction_review_counts', {}).get(request['request_id'], {}))
            request.update(status='scheduled', run_id=old['run_id'], updated_at=now())
            repo.write(STATE, request)
            return request
        if old.get('status') not in (None, 'complete', 'pending', 'running', 'category_pending', 'category_running'):
            return request
        context = context_data(repo.read('live-context.json'))
        if (context_digest(context) != request.get('base_context_digest') or
                not for_unit(repo, {'source': SOURCE}, context)):
            request.update(status='paused', reason='scenario_changed', updated_at=now())
            repo.write(STATE, request)
            return request
        version = registry(repo)['version']
        if old and (old.get('exercise_context') != context or old.get('registry_version') != version):
            return request
        from exercise_accounts import current, matches
        actors = current(repo)
        scoring = (actors or {}).get('scoring_rule', {})
        manuals = saved(repo)
        targets, manual_skips = [], 0
        for unit in candidates(repo, context):
            manual = manuals.get(key(unit['source'], unit['id']))
            if manual and (manual.get('content_fingerprint') == unit['content_fingerprint']
                    and manual.get('exercise_id') == unit.get('exercise_id')
                    and manual.get('exercise_context') == context and manual.get('rules_version') == VERSION):
                manual_skips += 1
                continue
            target = {k: unit[k] for k in ('source', 'id', 'content_fingerprint', 'exercise_id', 'previous_category')}
            target['valare_direction_revision'] = REVISION
            if (actors and matches(actors, unit) and scoring.get('enabled') is True
                    and scoring.get('historical_review_enabled') is True):
                target.update(account_context_revision=actors['revision'], scoring_rule_id=scoring['id'])
            targets.append(target)
        if not old:
            old = {'run_id': uuid.uuid4().hex, 'kind': 'thermometer_recheck', 'processing_model': review.MODEL,
                'cursor': 0, 'completed': 0, 'classified': 0, 'review_required': 0, 'failed': 0, 'skipped': 0,
                'targets': [], 'exercise_context': context, 'rules_version': VERSION,
                'registry_version': version, 'started_at': now()}
        job = copy.deepcopy(old)
        boundary = job['cursor'] + bool(job.get('inflight'))
        job['targets'] = job['targets'][:boundary] + interleave(job['targets'][boundary:], targets)
        job.setdefault('direction_review_requests', []).append(request['request_id'])
        job.setdefault('direction_review_counts', {})[request['request_id']] = {'total': len(targets), 'manual_skips': manual_skips}
        job.update(total=len(job['targets']), remaining=len(job['targets'])-job['cursor'], updated_at=now())
        job['status'] = 'running' if job.get('inflight') else 'pending' if job['remaining'] else 'complete'
        repo.write(review.STATE, job)
        request.update(status='scheduled', run_id=job['run_id'], total=len(targets), manual_skips=manual_skips, updated_at=now())
        repo.write(STATE, request)
        return request
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])
