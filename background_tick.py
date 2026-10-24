"""GitHub-scheduled Vercel worker. Source and results stay in Neon."""
import time
from datetime import datetime, timedelta, timezone

from cloud_analysis import enqueue, recover_validation_failure, step
from openai_analysis import ANALYSIS_SERVICE_TIER
from thermometer import instant

COLLECTION_INTERVAL = timedelta(hours=1)
MAX_ANALYSIS_SECONDS = 235  # Room inside the Vercel 300 s invocation limit.
RETRYABLE_ANALYSIS_REASONS = frozenset({'api_access', 'api_quota', 'api_connection'})
TRANSIENT_API_RETRY_INTERVAL = timedelta(minutes=15)
RATE_LIMIT_RETRY_INTERVAL = timedelta(hours=1)


def collection_due(schedule, current):
    next_due = schedule.get('next_collection_at')
    # Extend older short deadlines to the hourly cadence; preserve immediate busy-lock retries.
    anchors = [instant(schedule[k]) for k in ('last_attempt_at', 'last_success_at') if schedule.get(k)]
    if next_due and anchors and instant(next_due) > instant(schedule.get('last_attempt_at') or max(anchors).isoformat()):
        next_due = max(instant(next_due), max(anchors) + COLLECTION_INTERVAL).isoformat()
    return not next_due or instant(next_due) <= current


def tick(repo, *, clock=None, monotonic=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    monotonic = monotonic or time.monotonic
    started = monotonic()
    repo._queue_cache_enabled = True
    current = clock()
    previous_analysis = repo.read('analysis-job.json', {}) or {}
    schedule = repo.read('background-schedule.json', {}) or {}
    due = collection_due(schedule, current)
    collection = 'not_due'
    if due:
        # Persist a retry/backoff deadline before network I/O. Failed collection must not
        # be retried every five minutes. The current snapshot remains readable.
        repo.write('background-schedule.json', {
            'next_collection_at': (current + COLLECTION_INTERVAL).isoformat(),
            'last_attempt_at': current.isoformat(),
            'collection_waiting_until': (current + timedelta(minutes=6)).isoformat()})
        try:
            outcome = repo.collect(reset_analysis_error=False)
            collection = outcome['status']
            if collection == 'already_running':
                # Another invocation owns the lease; retry when next scheduled tick fires.
                repo.write('background-schedule.json', {
                    'next_collection_at': current.isoformat(),
                    'last_attempt_at': current.isoformat(),
                    'collection_waiting_until': (current + timedelta(minutes=6)).isoformat()})
            if collection == 'ok':
                repo.write('background-schedule.json', {
                    'next_collection_at': (clock() + COLLECTION_INTERVAL).isoformat(),
                    'last_attempt_at': current.isoformat(),
                    'last_success_at': outcome['collected_at']})
        except ValueError:
            collection = 'error'
            repo.write('background-schedule.json', {
                'next_collection_at': (current + COLLECTION_INTERVAL).isoformat(),
                'last_attempt_at': current.isoformat()})
    state = repo.read('analysis-job.json', {}) or {}
    retried = False
    if state.get('status') == 'error' and state.get('reason') == 'analysis_validation':
        # Legacy failed jobs can be advanced without another paid model call.
        state = recover_validation_failure(repo)
    if state.get('status') == 'error' and state.get('reason') in ('api_capacity', 'api_rate_limit'):
        last_attempt = state.get('updated_at')
        interval = RATE_LIMIT_RETRY_INTERVAL if state['reason'] == 'api_rate_limit' else TRANSIENT_API_RETRY_INTERVAL
        if (state.get('processing_tier') != ANALYSIS_SERVICE_TIER or
                not last_attempt or instant(last_attempt) + interval <= current):
            # A newly selected tier can resume immediately; repeated limits on
            # the same tier retain their cooldown.
            state = enqueue(repo)
            retried = True
    if collection == 'ok' and state.get('status') == 'error' and state.get('reason') in RETRYABLE_ANALYSIS_REASONS:
        # Retry provider failures only after the next scheduled collection. This also
        # resumes analysis after the key or provider service has been restored.
        state = enqueue(repo)
        retried = True
    import thermometer_recheck
    if thermometer_recheck.active(repo):
        state = thermometer_recheck.status(repo)
    progressed = 0
    if collection != 'already_running':
        while state.get('status') in ('pending', 'running') and monotonic() - started < MAX_ANALYSIS_SECONDS:
            before = (state.get('kind'), state.get('remaining'))
            state = step(repo, deadline=started + MAX_ANALYSIS_SECONDS, monotonic=monotonic)
            if state.get('status') == 'already_running' or (state.get('kind'), state.get('remaining')) == before:
                break
            progressed += 1
    fresh_failure = state.get('status') == 'error' and (
        previous_analysis.get('status') != 'error' or
        (retried and previous_analysis.get('reason') != state.get('reason')))
    status = 'error' if collection == 'error' or fresh_failure else 'paused' if state.get('status') == 'error' else 'ok'
    return {'status': status, 'collection': collection,
            'analysis': state.get('status', 'idle'), 'processed': progressed,
            'remaining': state.get('remaining', 0)}
