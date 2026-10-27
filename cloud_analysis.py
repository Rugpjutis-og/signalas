"""Resumable, authenticated analysis after collection; all state lives in Neon."""
from datetime import datetime, timezone
import uuid
import time

from live_data import fingerprint
from content import source_reference
from vision_input import has_images, REVISION as VISION_REVISION
from openai_analysis import (analyze, context_data, DEFAULT_ANALYSIS_MODEL, ANALYSIS_SERVICE_TIER,
                             ANALYSIS_TIMEOUT_SECONDS, AnalysisItemError, AnalysisServiceError, item_failure_reason)
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
    records = repo.latest()['records']
    units = {(r['source'], r['id']): r for r in records}
    if not getattr(repo, '_queue_cache_enabled', False) or getattr(repo, '_queue_record_pool', None) is not records:
        repo._queue_record_pool = records
        repo._queue_bindings = {}
    bindings = repo._queue_bindings
    from thermometer_review import saved, applicable, key
    manual = saved(repo)
    selected = []
    for k, unit in units.items():
        previous = good.get(k)
        manual_decision = manual.get(key(*k))
        if manual_decision and applicable(manual_decision, repo.expand_unit(unit), context):
            continue
        if not previous:
            selected.append(unit)
            continue  # No prior assessment: do not hash a full discussion merely to queue it.
        if k not in bindings:
            expanded = repo.expand_unit(unit)
            bindings[k] = (fingerprint(expanded), has_images(expanded))
        content_hash, images = bindings[k]
        previous = good.get(k)
        if previous and previous.get('content_fingerprint') == content_hash and manual.get(key(*k)) and applicable(manual[key(*k)], repo.expand_unit(unit), context):
            continue
        needs_photo = (images and previous and
                       previous.get('thermometer_status') == 'waiting_data' and
                       previous.get('vision_revision') != VISION_REVISION)
        recover_rollout = (previous and previous.get('vision_revision') == 'photos-2026-10-24.1' and
                           previous.get('processing_reason') in ('analysis_validation','analysis_valueerror'))
        if (not previous or previous.get('content_fingerprint') != content_hash or recover_rollout or
                previous.get('exercise_id') != unit.get('exercise_id') or needs_photo):
            selected.append(unit)
    # Unprocessed/changed content first; bounded photo backfill cannot starve new units.
    return sorted(selected, key=lambda r: (
        bool(good.get((r['source'],r['id']), {}).get('thermometer_status') == 'waiting_data'),
        r['published_at'], r['id'])), context



def enqueue(repo, *, reset_error=True):
    old = repo.read(STATE, {}) or {}
    if old.get('inflight_batch'):
        return old  # Collection cannot discard receipts for interrupted parallel work.
    from optimized_analysis import enabled, candidates
    optimized = enabled(repo)
    units = candidates(repo) if optimized else pending(repo)[0]
    if old.get('status') == 'error' and not reset_error:
        state = dict(old, remaining=len(units), updated_at=now())
    else:
        state = {'status': 'pending' if units else 'complete', 'remaining': len(units),
                 'completed': 0, 'updated_at': now()}
        if units and old.get('inflight'):
            state.update(status='running', inflight=old['inflight'])
    from optimized_analysis import enabled, build_plan
    if enabled(repo) and not state.get('inflight'):
        build_plan(repo, state, units)
        state['remaining_kind']='candidate_checks'
    repo.write(STATE, state)
    return state


def review_required(repo, state, units, context, *, unit=None, reason_code='analysis_validation'):
    """Preserve a failed unit for human review, without claiming AI classified it."""
    if not units:
        state.update(status='complete', remaining=0, updated_at=now())
        repo.write(STATE, state)
        return state
    unit = repo.expand_unit(unit or units[0])
    recorded = now()
    repo.append_analysis(failure_result(repo, unit, context, reason_code, recorded=recorded))
    state.update(status='pending' if len(units) > 1 else 'complete',
                 remaining=len(units)-1, review_required=state.get('review_required', 0)+1,
                 updated_at=recorded)
    state.pop('reason', None)
    state.pop('inflight', None)
    repo.write(STATE, state)
    return state


def failure_result(repo, unit, context, reason_code, *, recorded=None):
    model = repo.config.get('OPENAI_MODEL') or DEFAULT_ANALYSIS_MODEL
    reason = {
        'analysis_timeout': 'Automatinis vertinimas viršijo laukimo laiką; reikia analitiko peržiūros.',
        'analysis_interrupted': 'Vertinimo vykdymas nutrūko neišsaugojus rezultato; reikia analitiko peržiūros.',
    }.get(reason_code, 'Automatinis vertinimas neatitiko tikrinimo taisyklių; reikia analitiko peržiūros.')
    recorded = recorded or now()
    result = {
        'analysis_executed': False, 'processing_disposition': 'needs_review',
        'method': 'openai_validation_failed', 'processing_reason': reason_code,
        'vision_revision': VISION_REVISION,
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
    return result

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
            'registry_version': registry(repo)['version'], 'thermometer_rules_version': VERSION, 'vision_revision': VISION_REVISION if has_images(unit) else None}


def step(repo, *, deadline=None, monotonic=None):
    """Bounded paid work; optimized primary batches have at most two calls and no hidden retry."""
    import thermometer_recheck
    from optimized_analysis import enabled, ensure_plan, PRIMARY_PER_REVIEW
    if enabled(repo):
        ensure_plan(repo)
        primary = repo.read(STATE, {}) or {}
        if thermometer_recheck.active(repo) and (primary.get('status') not in ('pending','running') or primary.get('primary_since_review',0) >= PRIMARY_PER_REVIEW):
            return thermometer_recheck.step(repo, deadline=deadline, monotonic=monotonic)
        return _primary_step(repo, deadline=deadline, monotonic=monotonic)
    if thermometer_recheck.active(repo):
        trial = repo.read(thermometer_recheck.STATE, {}) or {}
        primary = repo.read(STATE, {}) or {}
        # A category audit alternates with the normal queue instead of pausing it.
        if (primary.get('status') not in ('pending', 'running') or
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
        from optimized_analysis import enabled, run_locked
        if (enabled(repo) or state.get('inflight_batch')) and state.get('queue_generation'):
            return run_locked(repo, state, deadline=deadline, monotonic=monotonic)
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
                                   reason_code=item_failure_reason(error))
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
    repo._queue_cache_enabled = True
    deadline = clock() + seconds
    import thermometer_recheck
    from background_tick import collection_due, tick
    schedule = repo.read('background-schedule.json', {}) or {}
    from cloud_collection import status as collection_status
    collection_job = collection_status(repo)
    from exercise_accounts import needs_service as account_setup_pending
    from narrative_mapping import needs_service as narrative_setup_pending
    if account_setup_pending(repo) or narrative_setup_pending(repo) or collection_job.get('status') == 'running' or (schedule and collection_due(schedule, datetime.now(timezone.utc))):
        # An open authenticated app can service overdue collection before more paid calls.
        # The same shared lease and persisted retry deadline still protect all workers.
        outcome = tick(repo, monotonic=clock)
        if collection_status(repo).get('status') == 'running':
            current = collection_status(repo)
            if outcome and outcome.get('collection') == 'already_running':
                current['status']='already_running'
            return current
        return (thermometer_recheck.status(repo) if thermometer_recheck.active(repo) else
                repo.read(STATE, {}) or {'status':'idle','remaining':0})
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
