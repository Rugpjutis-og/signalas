"""One explicitly authorized, finite Sol review pass; execution stays on Vercel."""
import copy
import json
import uuid
import time
from datetime import datetime, timezone

from live_data import load, thermometer, fingerprint
from thermometer_review import saved, applicable
from thermometer_policy import VERSION
from narrative_registry import load as registry
from openai_analysis import analyze, AnalysisServiceError
from cloud_repository import analysis_result_name
from cloud_storage import CloudStorageError

STATE = 'thermometer-recheck-job.json'
MODEL = 'gpt-6.1-sol'
ELIGIBLE = ('needs_review', 'error')


def now():
    return datetime.now(timezone.utc).isoformat()


def active(repo):
    state = repo.read(STATE, {}) or {}
    return state.get('status') in ('pending', 'running')


def status(repo):
    return {k: v for k, v in (repo.read(STATE, {}) or {}).items()
            if k not in ('targets', 'exercise_context', 'inflight')}


def start(repo):
    """Administrative start, never a paid local call. Repeat starts are idempotent."""
    old = repo.read(STATE, {}) or {}
    if old:
        return status(repo)
    report = thermometer(root=repo)
    records, context, _ = load(repo)
    by_id = {(r['source'], r['id']): r for r in records['records']}
    targets = []
    for unit in report['units']:
        if unit['assessment']['status'] not in ELIGIBLE:
            continue
        original = repo.expand_unit(by_id[unit['source'], unit['id']])
        targets.append({'source': unit['source'], 'id': unit['id'],
                        'content_fingerprint': fingerprint(original),
                        'exercise_id': original.get('exercise_id')})
    job = {'status': 'pending' if targets else 'complete', 'run_id': uuid.uuid4().hex,
           'processing_model': MODEL, 'kind': 'thermometer_recheck',
           'targets': targets, 'exercise_context': context, 'rules_version': VERSION,
           'registry_version': registry(repo)['version'], 'cursor': 0,
           'total': len(targets), 'remaining': len(targets), 'completed': 0,
           'classified': 0, 'review_required': 0, 'failed': 0, 'skipped': 0,
           'started_at': now(), 'updated_at': now(),
           'start': report['start'], 'end': report['end']}
    # Freeze the snapshot without interrupting an in-flight primary assessment.
    # Atomic insert makes competing starts idempotent; per-unit execution still
    # uses the shared six-minute lease and revalidates every frozen fingerprint.
    repo.sql("""INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,$3::jsonb)
        ON CONFLICT(scope,name) DO NOTHING""", [repo.scope, STATE, json.dumps(job)])
    repo.values.pop(STATE, None)
    return status(repo)

def advance(repo, state, outcome):
    state[outcome] = state.get(outcome, 0) + 1
    state['cursor'] += 1
    state['remaining'] = len(state['targets']) - state['cursor']
    state['completed'] = state['cursor']
    state['status'] = 'pending' if state['remaining'] else 'complete'
    state['updated_at'] = now()
    state.pop('inflight', None)
    repo.write(STATE, state)
    return status(repo)


def step(repo, *, deadline=None, monotonic=None):
    owner = uuid.uuid4().hex
    acquired = repo.sql('''INSERT INTO signalas_jobs(scope,owner,expires_at)
        VALUES($1,$2,now()+interval '6 minutes') ON CONFLICT(scope) DO UPDATE
        SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
        WHERE signalas_jobs.expires_at<now() RETURNING owner''', [repo.scope, owner])['rows']
    if not acquired:
        return dict(status(repo), status='already_running')
    try:
        repo.values.clear()
        repo.refresh_snapshot()
        state = repo.read(STATE, {}) or {}
        if state.get('status') not in ('pending', 'running'):
            return status(repo)
        waiting = (repo.read('background-schedule.json', {}) or {}).get('collection_waiting_until')
        if waiting and datetime.fromisoformat(waiting.replace('Z', '+00:00')) > datetime.now(timezone.utc):
            return dict(status(repo), status='already_running', reason='collection_pending')
        if state.get('inflight'):
            # A result saved just before interruption must not be paid for again.
            result = repo.read(state['inflight'])
            outcome = ('classified' if result['result']['thermometer_status'] == 'classified'
                       else 'review_required') if result else 'failed'
            return advance(repo, state, outcome)
        from openai_analysis import context_data
        if (state['exercise_context'] != context_data(repo.read('live-context.json')) or
                state['rules_version'] != VERSION or state['registry_version'] != registry(repo)['version']):
            state.update(status='paused', reason='context_changed', updated_at=now())
            repo.write(STATE, state)
            return status(repo)
        target = state['targets'][state['cursor']]
        unit = next((r for r in repo.latest()['records']
                     if (r['source'], r['id']) == (target['source'], target['id'])), None)
        if not unit:
            return advance(repo, state, 'skipped')
        unit = repo.expand_unit(unit)
        from thermometer_review import key
        manual = saved(repo).get(key(unit['source'], unit['id']))
        if (fingerprint(unit) != target['content_fingerprint'] or
                unit.get('exercise_id') != target['exercise_id'] or
                applicable(manual, unit, state['exercise_context'])):
            return advance(repo, state, 'skipped')
        # Preserve the original narrative result; this pass only revisits direction.
        original = repo.analysis_for_unit(unit['source'], unit['id'], target['content_fingerprint'], state['exercise_context'])
        if not original or original['result'].get('thermometer_status') not in ELIGIBLE:
            return advance(repo, state, 'skipped')
        timeout = min(180, deadline - (monotonic or time.monotonic)() - 30) if deadline else 180
        if timeout < 30:
            return status(repo)
        binding = {'source_reference': original['source_reference'],
                   'content_fingerprint': target['content_fingerprint'],
                   'exercise_id': unit.get('exercise_id'), 'exercise_context': state['exercise_context'],
                   'registry_version': state['registry_version'], 'thermometer_rules_version': VERSION,
                   'requested_model': MODEL, 'review_run_id': state['run_id']}
        state.update(status='running', inflight=analysis_result_name(binding), updated_at=now())
        repo.write(STATE, state)
        try:
            result = analyze(unit, state['exercise_context'], root=repo, timeout=timeout,
                             model_override=MODEL, thermometer_only=True)
        except CloudStorageError:
            raise
        except AnalysisServiceError as error:
            state.update(status='error', reason=error.reason, updated_at=now())
            state.pop('inflight', None)
            repo.write(STATE, state)
            return status(repo)
        except (ValueError, TypeError, KeyError) as error:
            message = str(error).lower()
            reason = next((code for fragment, code in (
                ('atsisak', 'model_refusal'), ('neužbaigt', 'incomplete_output'),
                ('json', 'invalid_json'), ('unexpected thermometer', 'response_schema'),
                ('strukt', 'response_schema'), ('neįvertintam', 'pending_reason_codes'),
                ('priežast', 'reason_codes'), ('kategorija', 'category_codes'),
                ('įrodymo', 'missing_evidence'), ('paaiškinimo', 'missing_reason'),
                ('laukas', 'field_type'), ('tipo', 'field_type')) if fragment in message),
                'analysis_validation')
            failures = state.setdefault('failure_reasons', {})
            failures[reason] = failures.get(reason, 0) + 1
            return advance(repo, state, 'failed')
        result.update(binding)
        result['method'] = 'openai_thermometer_recheck'
        for field in ('candidate_cluster_id', 'candidate_cluster_ids'):
            if field in original:
                result[field] = copy.deepcopy(original[field])
        result['result']['narrative_analysis'] = copy.deepcopy(original['result']['narrative_analysis'])
        repo.append_analysis(result)
        outcome = 'classified' if result['result']['thermometer_status'] == 'classified' else 'review_required'
        return advance(repo, state, outcome)
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])
