"""Human content-direction decisions, stored only in the exercise's Neon scope."""
import hashlib
import json
from datetime import datetime, timezone

from content import source_reference
from live_data import fingerprint
from openai_analysis import context_data
from thermometer_policy import BY_CATEGORY, VERSION, REASONS

NAME = 'thermometer-reviews.json'


def key(source, unit_id):
    return hashlib.sha256(json.dumps([source, unit_id], ensure_ascii=False).encode()).hexdigest()


def saved(root):
    if hasattr(root, 'read'):
        return root.read(NAME, {}) or {}
    path = root / 'var' / NAME
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def applicable(review, unit, context):
    return (isinstance(review, dict) and review.get('content_fingerprint') == fingerprint(unit)
            and review.get('exercise_id') == unit.get('exercise_id')
            and review.get('exercise_context') == context
            and review.get('rules_version') == VERSION)


def save(repo, payload):
    source, unit_id = payload.get('source'), payload.get('id')
    category, code = payload.get('category'), payload.get('reason_code')
    reason, evidence = payload.get('reason', ''), payload.get('evidence', '')
    if not all(isinstance(s, str) and 0 < len(s) <= 256 for s in (source, unit_id)):
        raise ValueError('Nenurodytas turinio vienetas.')
    if not isinstance(category, str) or category not in BY_CATEGORY:
        raise ValueError('Netinkama komunikacinė kryptis.')
    # Older clients may still supply a code; new manual decisions need only direction.
    if code is not None and (not isinstance(code, str) or code not in BY_CATEGORY[category]):
        raise ValueError('Kategorija ir pagrindo kodas nesutampa.')
    if not isinstance(reason, str) or len(reason.strip()) > 2000:
        raise ValueError('Netinkamas vertinimo pagrindas.')
    label = REASONS[code] if code else {'stabilizing': 'stabilizuojantis turinys',
            'neutral': 'neutralus turinys', 'destabilizing': 'destabilizuojantis turinys'}[category]
    reason = reason.strip() or 'Rankiniu būdu patvirtinta kryptis: ' + label + '.'
    if not isinstance(evidence, str) or len(evidence) > 2000:
        raise ValueError('Netinkama pagrindžianti ištrauka.')
    unit = repo.analysis_units([[source, unit_id]]).get((source, unit_id))
    if unit is None:
        raise ValueError('Turinio vieneto nėra surinktoje imtyje.')
    context = context_data(repo.read('live-context.json'))
    review = {'source_reference': source_reference(unit), 'content_fingerprint': fingerprint(unit),
              'exercise_id': unit.get('exercise_id'), 'exercise_context': context,
              'rules_version': VERSION, 'category': category, 'reason_code': code,
              'reason': reason.strip(), 'evidence': evidence.strip(),
              'reviewed_at': datetime.now(timezone.utc).isoformat(),
              'method': 'manual_review'}
    review_key = key(source, unit_id)
    repo.sql('''INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,jsonb_build_object($3::text,$4::jsonb))
        ON CONFLICT(scope,name) DO UPDATE SET value=signalas_state.value ||
        jsonb_build_object($3::text,$4::jsonb || jsonb_build_object('previous_reasons',
          COALESCE(signalas_state.value->$3->'previous_reasons','[]'::jsonb) ||
          CASE WHEN COALESCE(signalas_state.value->$3->>'reason','')<>''
            AND signalas_state.value->$3->>'reason'<>$4::jsonb->>'reason'
            AND NOT COALESCE(signalas_state.value->$3->'previous_reasons','[]'::jsonb)
                    @> jsonb_build_array(signalas_state.value->$3->>'reason')
          THEN jsonb_build_array(signalas_state.value->$3->>'reason') ELSE '[]'::jsonb END))''',
             [repo.scope, NAME, review_key, json.dumps(review, ensure_ascii=False)])
    repo.values.pop(NAME, None)
    return {'status': 'saved', 'category': category, 'reviewed_at': review['reviewed_at'],
            'source': source, 'id': unit_id, 'published_at': unit['published_at'],
            'assessment': {'category': category, 'status': 'assessed', 'method': 'manual_review',
                'reason': review['reason'], 'context_version': None,
                'reviewed_parts': ['analitiko peržiūra'],
                'reason_codes': [code] if code else [], 'rules_version': VERSION,
                'evidence': [{'kind': 'text', 'quote': review['evidence']}] if review['evidence'] else []}}
