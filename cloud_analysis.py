"""Resumable, authenticated analysis after collection; all state lives in Neon."""
from datetime import datetime, timezone
import uuid

from live_data import fingerprint
from content import source_reference
from openai_analysis import analyze, context_data, DEFAULT_ANALYSIS_MODEL, ANALYSIS_SERVICE_TIER
from narrative_registry import load as registry
from thermometer_policy import VERSION

STATE = 'analysis-job.json'
RESULTS = 'openai-analysis-pilot.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def pending(repo):
    context = context_data(repo.read('live-context.json'))
    version = registry(repo)['version']
    model = repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL
    results = repo.read(RESULTS, []) or []
    good = {(a.get('source_reference', {}).get('source'), a.get('source_reference', {}).get('id')): a
            for a in results if (a.get('analysis_executed') or a.get('processing_disposition') == 'needs_review')
            and a.get('registry_version') == version
            and a.get('thermometer_rules_version') == VERSION and a.get('exercise_context') == context
            and a.get('requested_model', a.get('model')) == model}
    units = {(r['source'], r['id']): r for r in repo.latest()['records']}
    return sorted((r for k, r in units.items() if k not in good or
                   good[k].get('content_fingerprint') != fingerprint(r) or
                   good[k].get('exercise_id') != r.get('exercise_id')),
                  key=lambda r: (r['published_at'], r['id'])), context


def enqueue(repo, *, reset_error=True):
    units, _ = pending(repo)
    old = repo.read(STATE, {}) or {}
    if old.get('status') == 'error' and not reset_error:
        state = dict(old, remaining=len(units), updated_at=now())
    else:
        state = {'status': 'pending' if units else 'complete', 'remaining': len(units),
                 'completed': 0, 'updated_at': now()}
    repo.write(STATE, state)
    return state


def review_required(repo, state, units, context):
    """Preserve a failed unit for human review, without claiming AI classified it."""
    if not units:
        state.update(status='complete', remaining=0, updated_at=now())
        repo.write(STATE, state)
        return state
    unit = units[0]
    model = repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL
    reason = 'Automatinis vertinimas neatitiko tikrinimo taisyklių; reikia analitiko peržiūros.'
    recorded = now()
    result = {
        'analysis_executed': False, 'processing_disposition': 'needs_review',
        'method': 'openai_validation_failed', 'model': model, 'requested_model': model,
        'registry_version': registry(repo)['version'], 'thermometer_rules_version': VERSION,
        'exercise_id': unit.get('exercise_id'), 'exercise_context': context,
        'source_reference': source_reference(unit), 'sourceUrl': unit.get('sourceUrl'),
        'content_fingerprint': fingerprint(unit), 'recorded_at': recorded,
        'result': {'narrative_analysis': {'match_status': 'uncertain', 'matches': [],
                                          'proposals': [], 'uncertainty_reason': reason},
                   'direction': 'needs_review', 'reason': reason, 'missing_context': reason,
                   'evidence': '', 'reason_codes': [], 'verified_claim_source': None,
                   'thermometer_status': 'needs_review', 'thermometer_category': None},
    }
    repo.write(RESULTS, (repo.read(RESULTS, []) or []) + [result])
    state.update(status='pending' if len(units) > 1 else 'complete',
                 remaining=len(units)-1, review_required=state.get('review_required', 0)+1,
                 updated_at=recorded)
    state.pop('reason', None)
    repo.write(STATE, state)
    return state


def recover_validation_failure(repo):
    """Advance an already failed validation item without paying for another call."""
    state = repo.read(STATE, {}) or {}
    if state.get('status') != 'error' or state.get('reason') != 'analysis_validation':
        return state
    owner = uuid.uuid4().hex
    acquired = repo.sql('''INSERT INTO signalas_jobs(scope,owner,expires_at)
        VALUES($1,$2,now()+interval '6 minutes')
        ON CONFLICT(scope) DO UPDATE SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
        WHERE signalas_jobs.expires_at<now() RETURNING owner''', [repo.scope, owner])['rows']
    if not acquired:
        return dict(state, status='already_running')
    try:
        repo.values.clear()
        repo.packet = None
        state = repo.read(STATE, {}) or {}
        if state.get('status') != 'error' or state.get('reason') != 'analysis_validation':
            return state
        units, context = pending(repo)
        return review_required(repo, state, units, context)
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])


def step(repo):
    """At most one paid call per request, no hidden retries after provider failure."""
    state = repo.read(STATE, {}) or {}
    if state.get('status') not in ('pending', 'running'):
        return state or {'status': 'idle', 'remaining': 0}
    owner = uuid.uuid4().hex
    acquired = repo.sql('''INSERT INTO signalas_jobs(scope,owner,expires_at)
        VALUES($1,$2,now()+interval '6 minutes')
        ON CONFLICT(scope) DO UPDATE SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
        WHERE signalas_jobs.expires_at<now() RETURNING owner''', [repo.scope, owner])['rows']
    if not acquired:
        return dict(state, status='already_running')
    try:
        # Invalidate cached state after acquiring the shared collection/analysis lease.
        repo.values.clear()
        repo.packet = None
        state = repo.read(STATE, {}) or {}
        if state.get('status') not in ('pending', 'running'):
            return state
        units, context = pending(repo)
        if not units:
            state.update(status='complete', remaining=0, updated_at=now())
            repo.write(STATE, state)
            return state
        unit = units[0]
        if not repo.config.get('OPENAI_API_KEY'):
            from monitoring import record
            record('openai', 'api_access', repo)
            state.update(status='error', reason='api_access', remaining=len(units), updated_at=now())
            repo.write(STATE, state)
            return state
        state.update(status='running', remaining=len(units), updated_at=now(),
                     processing_tier=ANALYSIS_SERVICE_TIER)
        repo.write(STATE, state)
        try:
            result = analyze(unit, context, root=repo)
        except ValueError:
            # No private provider message or source content in status responses.
            health = repo.read('openai-status.json', {}) or {}
            if health.get('status') != 'error':
                return review_required(repo, state, units, context)
            state.update(status='error', reason=health.get('reason') or 'api_error', updated_at=now())
            repo.write(STATE, state)
            return state
        result['content_fingerprint'] = fingerprint(unit)
        result['requested_model'] = repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL
        prior = repo.read(RESULTS, []) or []
        # Keep historical versions. Latest compatible result is selected by projections.
        repo.write(RESULTS, prior + [result])
        state.update(status='pending' if len(units) > 1 else 'complete', remaining=len(units)-1,
                     completed=state.get('completed', 0)+1, updated_at=now())
        state.pop('reason', None)
        repo.write(STATE, state)
        return state
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])
