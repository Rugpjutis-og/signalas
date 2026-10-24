"""One explicitly authorized, finite Sol review pass; execution stays on Vercel."""
import copy
import json
import uuid
import time
from datetime import datetime, timezone

from live_data import load, thermometer, fingerprint
from thermometer_review import saved, applicable
from thermometer_policy import VERSION, CATEGORIES, GUIDANCE_REVISION
from narrative_registry import load as registry
from openai_analysis import analyze, AnalysisServiceError
from cloud_repository import analysis_result_name
from cloud_storage import CloudStorageError
from vision_input import REVISION as VISION_REVISION

STATE = 'thermometer-recheck-job.json'
MODEL = 'gpt-6.1-sol'
ELIGIBLE = ('needs_review', 'error')


def now():
    return datetime.now(timezone.utc).isoformat()


def active(repo):
    state = repo.read(STATE, {}) or {}
    return state.get('status') in ('pending', 'running', 'category_pending', 'category_running')


def status(repo):
    value = {k: v for k, v in (repo.read(STATE, {}) or {}).items()
             if k not in ('targets', 'exercise_context', 'inflight', 'inflight_analysis')}
    value['status'] = {'category_pending':'pending', 'category_running':'running'}.get(value.get('status'), value.get('status'))
    return value


def start(repo, *, category=None, request_id=None):
    """Administrative start, never a paid local call. Repeat starts are idempotent."""
    old = repo.read(STATE, {}) or {}
    if category is not None and category not in CATEGORIES:
        raise ValueError('Invalid review category')
    if old and (not request_id or old.get('request_id') == request_id):
        return status(repo)
    if old and old.get('status') != 'complete':
        return dict(status(repo), reason='another_review_not_complete')
    report = thermometer(root=repo)
    records, context, _ = load(repo)
    by_id = {(r['source'], r['id']): r for r in records['records']}
    targets = []
    for unit in report['units']:
        assessment = unit['assessment']
        eligible = (assessment['status'] == 'assessed' and assessment.get('category') == category
                    and assessment.get('method') != 'manual_review') if category else assessment['status'] in ELIGIBLE
        if not eligible:
            continue
        original = repo.expand_unit(by_id[unit['source'], unit['id']])
        targets.append({'source': unit['source'], 'id': unit['id'],
                        'content_fingerprint': fingerprint(original),
                        'exercise_id': original.get('exercise_id')})
    job = {'status': ('category_pending' if category else 'pending') if targets else 'complete', 'run_id': uuid.uuid4().hex,
           'processing_model': MODEL, 'kind': 'thermometer_recheck',
           'selection_category': category, 'request_id': request_id, 'guidance_revision': GUIDANCE_REVISION,
           'reassigned': 0, 'retained': 0,
           'targets': targets, 'exercise_context': context, 'rules_version': VERSION,
           'registry_version': registry(repo)['version'], 'cursor': 0,
           'total': len(targets), 'remaining': len(targets), 'completed': 0,
           'classified': 0, 'review_required': 0, 'failed': 0, 'skipped': 0,
           'started_at': now(), 'updated_at': now(),
           'start': report['start'], 'end': report['end']}
    # Freeze the snapshot without interrupting an in-flight primary assessment.
    # Atomic insert makes competing starts idempotent; per-unit execution still
    # uses the shared six-minute lease and revalidates every frozen fingerprint.
    if old:
        repo.sql("""WITH previous AS (
            SELECT value FROM signalas_state WHERE scope=$1 AND name=$2
              AND value->>'run_id'=$4 AND value->>'status'='complete' FOR UPDATE
        ), archived AS (
            INSERT INTO signalas_state(scope,name,value)
            SELECT $1,'thermometer-recheck-history/'||$4,value FROM previous
            ON CONFLICT(scope,name) DO NOTHING
        ) UPDATE signalas_state SET value=$3::jsonb WHERE scope=$1 AND name=$2
            AND EXISTS(SELECT 1 FROM previous)""", [repo.scope, STATE, json.dumps(job), old['run_id']])
    else:
        repo.sql("""INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,$3::jsonb)
            ON CONFLICT(scope,name) DO NOTHING""", [repo.scope, STATE, json.dumps(job)])
    repo.values.pop(STATE, None)
    return status(repo)

def primary_marker(repo):
    primary = repo.read('analysis-job.json', {}) or {}
    return {k: primary.get(k) for k in ('updated_at', 'completed', 'remaining')}


def advance(repo, state, outcome, result=None):
    state[outcome] = state.get(outcome, 0) + 1
    if outcome == 'classified' and state.get('selection_category') and result:
        changed = result['result'].get('thermometer_category') != state['selection_category']
        counter = 'reassigned' if changed else 'retained'
        state[counter] = state.get(counter, 0) + 1
    state['cursor'] += 1
    state['remaining'] = len(state['targets']) - state['cursor']
    state['completed'] = state['cursor']
    state['status'] = ('category_pending' if state.get('selection_category') else 'pending') if state['remaining'] else 'complete'
    state['updated_at'] = now()
    state['after_primary'] = primary_marker(repo)
    state.pop('inflight', None)
    state.pop('inflight_analysis', None)
    repo.write(STATE, state)
    from optimized_analysis import enabled
    if enabled(repo):
        repo.sql("UPDATE signalas_state SET value=jsonb_set(value,'{primary_since_review}','0'::jsonb) WHERE scope=$1 AND name='analysis-job.json'",[repo.scope])
        repo.values.pop('analysis-job.json',None)
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
        if state.get('status') not in ('pending', 'running', 'category_pending', 'category_running'):
            return status(repo)
        waiting = (repo.read('background-schedule.json', {}) or {}).get('collection_waiting_until')
        if waiting and datetime.fromisoformat(waiting.replace('Z', '+00:00')) > datetime.now(timezone.utc):
            return dict(status(repo), status='already_running', reason='collection_pending')
        if state.get('inflight'):
            # A result saved just before interruption must not be paid for again.
            result = repo.read(state['inflight'])
            if not result and state.get('inflight_analysis'):
                result = repo.read(state['inflight_analysis'])
            outcome = ('failed' if result.get('processing_disposition') == 'needs_review'
                       else 'classified' if result['result']['thermometer_status'] == 'classified'
                       else 'review_required') if result else 'failed'
            return advance(repo, state, outcome, result)
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
        account_revision = target.get('account_context_revision')
        from exercise_accounts import for_unit as actor_context
        actor = actor_context(repo, unit)
        if account_revision:
            if not actor or actor['revision'] != account_revision:
                return advance(repo, state, 'skipped')
        selected = None if account_revision else state.get('selection_category')
        still_eligible = original and ((original['result'].get('thermometer_status') == 'classified' and
            original['result'].get('thermometer_category') == selected) if selected else
            original['result'].get('thermometer_status') in ELIGIBLE)
        if account_revision:
            still_eligible = bool(original and original.get('result'))
        if not still_eligible:
            return advance(repo, state, 'skipped')
        timeout = min(180, deadline - (monotonic or time.monotonic)() - 30) if deadline else 180
        if timeout < 30:
            return status(repo)
        binding = {'source_reference': original['source_reference'],
                   'content_fingerprint': target['content_fingerprint'],
                   'exercise_id': unit.get('exercise_id'), 'exercise_context': state['exercise_context'],
                   'registry_version': state['registry_version'], 'thermometer_rules_version': VERSION,
                   'requested_model': MODEL, 'review_run_id': state['run_id'], 'vision_revision': VISION_REVISION}
        if actor:binding['exercise_actor_context_revision']=actor['revision']
        scoring_review = target.get('scoring_rule_id')
        if scoring_review:
            from exercise_rule import for_unit as scoring_for_unit
            if not account_revision or not scoring_for_unit(repo, unit, thermometer_only=True, review_rule_id=scoring_review):
                return advance(repo, state, 'skipped')
            binding['exercise_scoring_rule_review'] = scoring_review
        result_name = analysis_result_name(binding)
        audit_name = 'account-recheck-result/'+state['run_id']+'/'+result_name.split('/')[-1] if account_revision else None
        state.update(status='category_running' if selected else 'running', inflight=audit_name or result_name, updated_at=now())
        if audit_name:state['inflight_analysis']=result_name
        repo.write(STATE, state)
        try:
            result = analyze(unit, state['exercise_context'], root=repo, timeout=timeout,
                             model_override=MODEL, thermometer_only=True, **({"scoring_rule_review": scoring_review} if scoring_review else {}))
        except CloudStorageError:
            raise
        except AnalysisServiceError as error:
            state.update(status='error', reason=error.reason, updated_at=now())
            state.pop('inflight', None)
            state.pop('inflight_analysis', None)
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
            if audit_name:
                repo.write(audit_name, {'processing_disposition':'needs_review', 'processing_reason':reason,
                    'source_reference':original['source_reference'],'account_context_revision':account_revision,
                    'kept_previous':True,'recorded_at':now(),'result':{'thermometer_status':'error','thermometer_category':None}})
            if selected:
                fallback = {**binding, 'model': MODEL, 'analysis_executed': False,
                    'processing_disposition': 'needs_review', 'processing_reason': reason,
                    'method': 'openai_validation_failed', 'recorded_at': now(),
                    'result': {'narrative_analysis': copy.deepcopy(original['result']['narrative_analysis']),
                        'direction': 'needs_review', 'thermometer_status': 'error', 'thermometer_category': None,
                        'reason': 'Pakartotinis vertinimas nepraėjo patikros; reikia analitiko peržiūros.',
                        'missing_context': 'Pakartotinis vertinimas nepraėjo patikros.',
                        'reason_codes': [], 'evidence': ''}}
                for field in ('candidate_cluster_id', 'candidate_cluster_ids'):
                    if field in original:
                        fallback[field] = copy.deepcopy(original[field])
                repo.append_analysis(fallback)
            return advance(repo, state, 'failed')
        result.update(binding)
        result['method'] = 'openai_thermometer_recheck'
        for field in ('candidate_cluster_id', 'candidate_cluster_ids'):
            if field in original:
                result[field] = copy.deepcopy(original[field])
        result['result']['narrative_analysis'] = copy.deepcopy(original['result']['narrative_analysis'])
        classified = result['result']['thermometer_status'] == 'classified'
        if not account_revision or classified:
            repo.append_analysis(result)
        if audit_name:
            repo.write(audit_name, {'source_reference':result['source_reference'],
                'account_context_revision':account_revision,'recorded_at':now(),
                'kept_previous':not classified, 'reason':result['result'].get('reason'),
                'result':{k:result['result'].get(k) for k in ('thermometer_status','thermometer_category')}})
        outcome = 'classified' if result['result']['thermometer_status'] == 'classified' else 'review_required'
        return advance(repo, state, outcome, result)
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [repo.scope, owner])
