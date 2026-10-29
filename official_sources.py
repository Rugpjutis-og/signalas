"""Deferred organizer scoring for exact official exercise-source identities.

The independent AI result is retained. No content, AI history or manual review is
rewritten, and display-name guesses never establish an official source.
"""
import uuid
from datetime import datetime, timezone
from scenario_supplement import context_digest
from thermometer_policy import VERSION

STATE = 'official-exercise-sources.json'
REVISION = 'official-exercise-sources-2026-10-29'
_UNSET = object()


def configuration(repo):
    if not hasattr(repo, 'read'):
        return None
    value = repo.read(STATE)
    if (not isinstance(value, dict) or value.get('revision') != REVISION
            or value.get('base_context_digest') != context_digest(repo.read('live-context.json'))):
        return None
    return value


def current(repo):
    value = configuration(repo)
    return value if value and value.get('status') == 'active' else None


def assessment(repo, unit, independent, *, rule=_UNSET):
    value = current(repo) if rule is _UNSET else rule
    if (not value or unit.get('kind') != 'post' or unit.get('source') != value.get('source')
            or unit.get('exercise_id') != value.get('exercise_id')):
        return independent
    author = next((a for a in value.get('accounts', [])
                   if a.get('author_id') and a['author_id'] == unit.get('author_id')), None)
    if not author:
        return independent
    handle = unit.get('author_handle')
    if handle and handle.casefold() != author['handle'].casefold():
        return independent  # Conflicting source identity is never resolved by display name.
    return {'category': 'stabilizing', 'status': 'assessed', 'method': 'exercise_organizer_rule',
        'reason': 'Organizatoriaus pratybų taisyklė: šaltinis „' + author['label'] +
                  '“ pratybose laikomas oficialiu stabilizuojančiu šaltiniu. Tai scenarijaus '
                  'priskyrimas; nepriklausoma turinio analizė neperrašoma.',
        'rules_version': VERSION, 'reason_codes': ['S4'], 'context_version': None,
        'reviewed_parts': ['organizatoriaus pratybų taisyklė'], 'evidence': [],
        'organizer_rule': {'revision': REVISION, 'scope': 'fictional_exercise_only',
                           'provenance': 'exercise_organizer', 'activated_at': value['activated_at']},
        'independent_content_assessment': independent}


def completed(repo, value):
    run = value.get('after_review_run_id')
    if not run or (repo.read('analysis-job.json', {}) or {}).get('status') != 'complete':
        return False
    review = repo.read('thermometer-recheck-job.json', {}) or {}
    if review.get('run_id') != run:
        review = repo.read('thermometer-recheck-history/' + run, {}) or {}
    return review.get('run_id') == run and review.get('status') == 'complete'


def maybe_activate(repo):
    value = configuration(repo)
    if not value or value.get('status') != 'waiting_for_current_checks' or not completed(repo, value):
        return value
    owner = uuid.uuid4().hex
    locked = repo.sql("""INSERT INTO signalas_jobs(scope,owner,expires_at)
        VALUES($1,$2,now()+interval '6 minutes') ON CONFLICT(scope) DO UPDATE
        SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
        WHERE signalas_jobs.expires_at<now() RETURNING owner""", [repo.scope, owner])['rows']
    if not locked:
        return value
    try:
        repo.values.clear()
        value = configuration(repo)
        if value and value.get('status') == 'waiting_for_current_checks' and completed(repo, value):
            value.update(status='active', activated_at=datetime.now(timezone.utc).isoformat())
            repo.write(STATE, value)
        return value
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])
