"""GitHub-scheduled Vercel worker. Source and results stay in Neon."""
import time
from datetime import datetime, timedelta, timezone

from cloud_analysis import step
from thermometer import instant

COLLECTION_INTERVAL = timedelta(hours=1)
MAX_ANALYSIS_SECONDS = 235  # Room inside the Vercel 300 s invocation limit.


def tick(repo, *, clock=None, monotonic=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    monotonic = monotonic or time.monotonic
    started = monotonic()
    current = clock()
    schedule = repo.read('background-schedule.json', {}) or {}
    next_due = schedule.get('next_collection_at')
    due = not next_due or instant(next_due) <= current
    collection = 'not_due'
    if due:
        # Persist a retry/backoff deadline before network I/O. Failed collection must not
        # be retried every five minutes. The current snapshot remains readable.
        repo.write('background-schedule.json', {
            'next_collection_at': (current + COLLECTION_INTERVAL).isoformat(),
            'last_attempt_at': current.isoformat()})
        try:
            outcome = repo.collect(reset_analysis_error=False)
            collection = outcome['status']
            if collection == 'already_running':
                # Another invocation owns the lease; retry when next scheduled tick fires.
                repo.write('background-schedule.json', {
                    'next_collection_at': (current + timedelta(minutes=5)).isoformat(),
                    'last_attempt_at': current.isoformat()})
            if collection == 'ok':
                repo.write('background-schedule.json', {
                    'next_collection_at': (clock() + COLLECTION_INTERVAL).isoformat(),
                    'last_attempt_at': current.isoformat(),
                    'last_success_at': outcome['collected_at']})
        except ValueError:
            collection = 'error'
    state = repo.read('analysis-job.json', {}) or {}
    progressed = 0
    if collection != 'already_running':
        while state.get('status') in ('pending', 'running') and monotonic() - started < MAX_ANALYSIS_SECONDS:
            before = state.get('remaining')
            state = step(repo)
            if state.get('status') == 'already_running' or state.get('remaining') == before:
                break
            progressed += 1
    failed = collection == 'error' or state.get('status') == 'error'
    return {'status': 'error' if failed else 'ok', 'collection': collection,
            'analysis': state.get('status', 'idle'), 'processed': progressed,
            'remaining': state.get('remaining', 0)}
