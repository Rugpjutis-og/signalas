"""Resumable, authenticated analysis after collection; all state lives in Neon."""
from datetime import datetime, timezone
import uuid
import time

from live_data import fingerprint
from content import source_reference
from openai_analysis import (analyze, context_data, DEFAULT_ANALYSIS_MODEL, ANALYSIS_SERVICE_TIER,
                             ANALYSIS_TIMEOUT_SECONDS, AnalysisItemError, AnalysisServiceError)
from cloud_storage import CloudStorageError
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
    results = repo.analysis_for_queue(context, version, model)
    good = {(a.get('source_reference', {}).get('source'), a.get('source_reference', {}).get('id')): a
            for a in results}
    units = {(r['source'], r['id']): r for r in repo.latest()['records']}
    return sorted((r for k, r in units.items() if k not in good or
                   good[k].get('content_fingerprint') != fingerprint(repo.expand_unit(r)) or
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
        if units and old.get('inflight'):
            state.update(status='running', inflight=old['inflight'])
    repo.write(STATE, state)
    return state


def review_required(repo, state, units, context, *, unit=None, reason_code='analysis_validation'):
    """Preserve a failed unit for human review, without claiming AI classified it."""
    if not units:
        state.update(status='complete', remaining=0, updated_at=now())
        repo.write(STATE, state)
        return state
    unit = repo.expand_unit(unit or units[0])
    model = repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL
    reason = {
        'analysis_timeout': 'Automatinis vertinimas viršijo laukimo laiką; reikia analitiko peržiūros.',
        'analysis_interrupted': 'Vertinimo vykdymas nutrūko neišsaugojus rezultato; reikia analitiko peržiūros.',
    }.get(reason_code, 'Automatinis vertinimas neatitiko tikrinimo taisyklių; reikia analitiko peržiūros.')
    recorded = now()
    result = {
        'analysis_executed': False, 'processing_disposition': 'needs_review',
        'method': 'openai_validation_failed', 'processing_reason': reason_code,
        'model': model, 'requested_model': model,
        'registry_version': registry(repo)['version'], 'thermometer_rules_version': VERSION,
        'exercise_id': unit.get('exercise_id'), 'exercise_context': context,
        'source_reference': source_reference(unit), 'sourceUrl': unit.get('sourceUrl'),
        'content_fingerprint': fingerprint(unit), 'recorded_at': recorded,
        'result': {'narrative_analysis': {'match_status': 'uncertain', 'matches': [],
                                          'proposals': [], 'uncertainty_reason': reason},
                   'direction': 'needs_review', 'reason': reason, 'missing_context': reason,
                   'evidence': '', 'reason_codes': [],
                   'thermometer_status': 'needs_review', 'thermometer_category': None},
    }
    repo.append_analysis(result)
    state.update(status='pending' if len(units) > 1 else 'complete',
                 remaining=len(units)-1, review_required=state.get('review_required', 0)+1,
                 updated_at=recorded)
    state.pop('reason', None)
    state.pop('inflight', None)
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
        repo.refresh_snapshot()
        state = repo.read(STATE, {}) or {}
        if state.get('status') != 'error' or state.get('reason') != 'analysis_validation':
            return state
        units, context = pending(repo)
        return review_required(repo, state, units, context)
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])


def receipt(unit, context, repo):
    unit = repo.expand_unit(unit)
    return {'source_reference': source_reference(unit), 'content_fingerprint': fingerprint(unit),
            'exercise_id': unit.get('exercise_id'), 'exercise_context': context,
            'model': repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL,
            'registry_version': registry(repo)['version'], 'thermometer_rules_version': VERSION}


def step(repo, *, deadline=None, monotonic=None):
    """At most one paid call per request, no hidden retries after provider failure."""
    import thermometer_recheck
    if thermometer_recheck.active(repo):
        trial = repo.read(thermometer_recheck.STATE, {}) or {}
        primary = repo.read(STATE, {}) or {}
        # A category audit alternates with the normal queue instead of pausing it.
        if (not trial.get('selection_category') or primary.get('status') not in ('pending', 'running') or
                trial.get('after_primary') != thermometer_recheck.primary_marker(repo)):
            return thermometer_recheck.step(repo, deadline=deadline, monotonic=monotonic)
    return _primary_step(repo, deadline=deadline, monotonic=monotonic)


def _primary_step(repo, *, deadline=None, monotonic=None):
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
        repo.refresh_snapshot()
        state = repo.read(STATE, {}) or {}
        if state.get('status') not in ('pending', 'running'):
            return state
        waiting = (repo.read('background-schedule.json', {}) or {}).get('collection_waiting_until')
        if waiting and datetime.fromisoformat(waiting.replace('Z', '+00:00')) > datetime.now(timezone.utc):
            # A continuously open browser must yield between items so the
            # hourly collector can obtain the shared lease instead of starving.
            return dict(state, status='already_running', reason='collection_pending')
        units, context = pending(repo)
        if not units:
            state.update(status='complete', remaining=0, updated_at=now())
            state.pop('inflight', None)
            repo.write(STATE, state)
            return state
        if state.get('status') == 'running':
            # Acquiring the lease proves there is no active owner. A persisted
            # receipt identifies an interrupted paid request precisely. Do not
            # repeat it, or mark the next item if its result was already saved.
            inflight = state.get('inflight')
            interrupted = next((u for u in units if receipt(u, context, repo) == inflight), None) if inflight else units[0]
            if interrupted:
                return review_required(repo, state, units, context, unit=interrupted,
                                       reason_code='analysis_interrupted')
            state.pop('inflight', None)
        unit = repo.expand_unit(units[0])
        if not repo.config.get('OPENAI_API_KEY'):
            from monitoring import record
            record('openai', 'api_access', repo)
            state.update(status='error', reason='api_access', remaining=len(units), updated_at=now())
            repo.write(STATE, state)
            return state
        timeout = ANALYSIS_TIMEOUT_SECONDS
        if deadline is not None:
            timeout = min(timeout, deadline - (monotonic or time.monotonic)() - 30)
            if timeout < 30:
                state.update(status='pending', remaining=len(units), updated_at=now())
                repo.write(STATE, state)
                return state
        state.update(status='running', remaining=len(units), updated_at=now(),
                     processing_tier=ANALYSIS_SERVICE_TIER,
                     processing_model=repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL,
                     inflight=receipt(unit, context, repo))
        repo.write(STATE, state)
        try:
            result = analyze(unit, context, root=repo, timeout=timeout)
        except CloudStorageError:
            # A database failure is never an item-validation failure.
            raise
        except AnalysisServiceError as error:
            state.update(status='error', reason=error.reason, updated_at=now())
            state.pop('inflight', None)
            repo.write(STATE, state)
            return state
        except (ValueError, TypeError, KeyError) as error:
            return review_required(repo, state, units, context,
                                   reason_code=error.reason if isinstance(error, AnalysisItemError) else 'analysis_validation')
        result['content_fingerprint'] = fingerprint(unit)
        result['requested_model'] = repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL
        # Keep historical versions. Latest compatible result is selected by projections.
        repo.append_analysis(result)
        state.update(status='pending' if len(units) > 1 else 'complete', remaining=len(units)-1,
                     completed=state.get('completed', 0)+1, updated_at=now())
        state.pop('reason', None)
        state.pop('inflight', None)
        repo.write(STATE, state)
        return state
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])


def drain(repo, *, seconds=235, monotonic=None):
    """Reuse one private snapshot across a bounded Vercel batch."""
    clock = monotonic or time.monotonic
    deadline = clock() + seconds
    import thermometer_recheck
    state = (thermometer_recheck.status(repo) if thermometer_recheck.active(repo) else
             repo.read(STATE, {}) or {'status': 'idle', 'remaining': 0})
    if state.get('status') == 'error' and state.get('reason') == 'analysis_validation':
        state = recover_validation_failure(repo)
    while state.get('status') in ('pending', 'running') and clock() + 60 < deadline:
        before = (state.get('kind'), state.get('remaining'))
        state = step(repo, deadline=deadline, monotonic=clock)
        if state.get('status') == 'already_running' or (state.get('kind'), state.get('remaining')) == before:
            break
    if thermometer_recheck.active(repo):
        return thermometer_recheck.status(repo)
    return state
