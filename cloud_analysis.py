"""Resumable, authenticated analysis after collection; all state lives in Neon."""
from datetime import datetime, timezone
import uuid

from live_data import fingerprint
from openai_analysis import analyze, context_data, DEFAULT_ANALYSIS_MODEL
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
            for a in results if a.get('analysis_executed') and a.get('registry_version') == version
            and a.get('thermometer_rules_version') == VERSION and a.get('exercise_context') == context
            and a.get('requested_model', a.get('model')) == model}
    units = {(r['source'], r['id']): r for r in repo.latest()['records']}
    return sorted((r for k, r in units.items() if k not in good or
                   good[k].get('content_fingerprint') != fingerprint(r) or
                   good[k].get('exercise_id') != r.get('exercise_id')),
                  key=lambda r: (r['published_at'], r['id'])), context


def enqueue(repo):
    units, _ = pending(repo)
    state = {'status': 'pending' if units else 'complete', 'remaining': len(units),
             'completed': 0, 'updated_at': now()}
    repo.write(STATE, state)
    return state


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
        state.update(status='running', remaining=len(units), updated_at=now())
        repo.write(STATE, state)
        try:
            result = analyze(unit, context, root=repo)
        except ValueError:
            # No private provider message or source content in status responses.
            health = repo.read('openai-status.json', {}) or {}
            reason = health.get('reason') if health.get('status') == 'error' else 'analysis_validation'
            state.update(status='error', reason=reason, updated_at=now())
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
