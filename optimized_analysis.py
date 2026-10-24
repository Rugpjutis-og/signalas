"""Bounded primary queue and two in-memory AI workers under the existing shared lease.

Only compact identities are persisted; source bodies/photos are never replicated here.
"""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from scenario_supplement import context_digest
from cloud_storage import CloudStorageError

POLICY = 'analysis-runtime.json'
PLAN = 'analysis-queue.json'
PRIMARY_PER_REVIEW = 3
MAX_WORKERS = 2
PAGE_SIZE = 16


def enabled(repo):
    return (repo.read(POLICY,{}) or {}).get('enabled') is True


def bindings(repo, context):
    import cloud_analysis as ca
    return {'context':context_digest(context),'registry':ca.registry(repo)['version'],'rules':ca.VERSION,
            'model':repo.config.get('OPENAI_MODEL') or ca.DEFAULT_ANALYSIS_MODEL,
            'snapshot':repo.latest().get('collected_at')}


def candidates(repo):
    """Queue compact candidates without expanding/hash-checking the entire discussion corpus."""
    import cloud_analysis as ca
    context=ca.context_data(repo.read('live-context.json'))
    binding=bindings(repo,context)
    prior=repo.analysis_for_queue(context,binding['registry'],binding['model'])
    known={(a['source_reference']['source'],a['source_reference']['id']) for a in prior}
    repo._known_queue_keys=known
    unique={(u['source'],u['id']):u for u in repo.latest()['records']}
    return sorted(unique.values(),key=lambda u:((u['source'],u['id']) in known,u['published_at'],u['id']))


def build_plan(repo, state, units):
    import cloud_analysis as ca
    generation=uuid.uuid4().hex
    old_plan=repo.read(PLAN,{}) or {}
    old_state=repo.read(ca.STATE,{}) or {}
    backlog={tuple(k) for k in old_plan.get('units',[])[old_state.get('queue_cursor',0):]}
    known=getattr(repo,'_known_queue_keys',set())
    units=sorted(units,key=lambda u:((u['source'],u['id']) in known,(u['source'],u['id']) in backlog))
    binding=bindings(repo,ca.context_data(repo.read('live-context.json')))
    repo.write(PLAN,{'generation':generation,'units':[[u['source'],u['id']] for u in units]})
    state.update(queue_generation=generation,queue_bindings=binding,queue_cursor=0,
                 queue_total=len(units),primary_since_review=0)


def ensure_plan(repo):
    import cloud_analysis as ca
    state=repo.read(ca.STATE,{}) or {}
    if state.get('status') not in ('pending','running') or (state.get('queue_generation') and state.get('reason')!='queue_refresh_required'):
        return
    if state.get('inflight_batch'):return # Existing parallel receipts are recovered by run_locked.
    owner=uuid.uuid4().hex
    got=repo.sql("""INSERT INTO signalas_jobs(scope,owner,expires_at) VALUES($1,$2,now()+interval '6 minutes')
        ON CONFLICT(scope) DO UPDATE SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
        WHERE signalas_jobs.expires_at<now() RETURNING owner""",[repo.scope,owner])['rows']
    if not got:return
    try:
        repo.values.clear();repo.refresh_snapshot()
        waiting=(repo.read('background-schedule.json',{}) or {}).get('collection_waiting_until')
        if waiting and datetime.fromisoformat(waiting.replace('Z','+00:00'))>datetime.now(timezone.utc):return
        state=repo.read(ca.STATE,{}) or {}
        if state.get('inflight'):
            receipt=state['inflight'];ref=receipt.get('source_reference',{})
            record=next((u for u in repo.latest()['records'] if (u['source'],u['id'])==(ref.get('source'),ref.get('id'))),None)
            context=ca.context_data(repo.read('live-context.json'))
            if record:
                unit=repo.expand_unit(record)
                prior=repo.analysis_queue_results([unit],context,ca.registry(repo)['version'],repo.config.get('OPENAI_MODEL') or ca.DEFAULT_ANALYSIS_MODEL)
                previous=prior[-1] if prior else None
                if ca.receipt(unit,context,repo)==receipt and eligible(repo,unit,previous,context):
                    repo.append_analysis(ca.failure_result(repo,unit,context,'analysis_interrupted'))
            state.pop('inflight',None);state.update(status='pending')
            repo.write(ca.STATE,state)
        if not state.get('queue_generation') or state.get('reason')=='queue_refresh_required':
            ca.enqueue(repo)
    finally:repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2',[repo.scope,owner])


def eligible(repo, unit, previous, context):
    import cloud_analysis as ca
    from thermometer_review import saved,key,applicable
    if applicable(saved(repo).get(key(unit['source'],unit['id'])),unit,context):return False
    if not previous:return True
    return (previous.get('content_fingerprint')!=ca.fingerprint(unit) or
            previous.get('exercise_id')!=unit.get('exercise_id') or
            (ca.has_images(unit) and previous.get('thermometer_status')=='waiting_data' and previous.get('vision_revision')!=ca.VISION_REVISION) or
            (previous.get('vision_revision')=='photos-2026-10-24.1' and previous.get('processing_reason') in ('analysis_validation','analysis_valueerror')))


def run_locked(repo,state,*,deadline=None,monotonic=None):
    """Caller owns collection/analysis lease for the entire bounded batch."""
    import cloud_analysis as ca
    clock=monotonic or time.monotonic
    context=ca.context_data(repo.read('live-context.json'))
    current=bindings(repo,context)
    records=repo.latest()['records']
    if getattr(repo,'_optimized_record_pool',None) is not records:
        repo._optimized_record_pool=records
        repo._optimized_units={(u['source'],u['id']):u for u in records}
    pool=repo._optimized_units
    model=current['model'];version=current['registry']
    def prior(units):
        return {(a['source_reference']['source'],a['source_reference']['id']):a
                for a in repo.analysis_queue_results(units,context,version,model)}
    def persist():
        state['updated_at']=ca.now();repo.write(ca.STATE,state)
    # Recover precisely the unfinished receipts; saved successes are never repaid.
    if state.get('status')=='running' and state.get('inflight_batch'):
        receipts=state['inflight_batch'];raw=[pool[(t['source_reference']['source'],t['source_reference']['id'])] for t in receipts
            if (t['source_reference']['source'],t['source_reference']['id']) in pool]
        previous=prior(raw)
        for record in raw:
            unit=repo.expand_unit(record);k=(record['source'],record['id'])
            frozen=next(t for t in receipts if t['source_reference']['source']==k[0] and t['source_reference']['id']==k[1])
            if frozen.get('content_fingerprint')==ca.fingerprint(unit) and eligible(repo,unit,previous.get(k),context):
                repo.append_analysis(ca.failure_result(repo,unit,context,'analysis_interrupted'))
                state['review_required']=state.get('review_required',0)+1
                state['primary_since_review']=state.get('primary_since_review',0)+1
        state['queue_cursor']=state.pop('batch_end',state['queue_cursor'])
        state.pop('inflight_batch',None)
        state['remaining']=state['queue_total']-state['queue_cursor']
        state['status']='pending' if state['remaining'] else 'complete'
        if current!=state.get('queue_bindings'):
            state.update(status='pending',reason='queue_refresh_required')
        persist();return state
    if current!=state.get('queue_bindings'):
        state.update(status='pending',reason='queue_refresh_required',updated_at=ca.now())
        repo.write(ca.STATE,state);return state
    offset=state['queue_cursor']
    page=repo.analysis_queue_page(state['queue_generation'],offset,PAGE_SIZE)
    if page is None or (not page and offset<state['queue_total']):
        state.update(reason='queue_refresh_required',status='pending');persist();return state
    raw=[pool[tuple(k)] for k in page if tuple(k) in pool]
    previous=prior(raw) if raw else {}
    import thermometer_recheck
    count=(min(MAX_WORKERS,max(1,PRIMARY_PER_REVIEW-state.get('primary_since_review',0)))
           if thermometer_recheck.active(repo) else MAX_WORKERS)
    selected=[];end=offset
    for index,key in enumerate(page):
        end=offset+index+1
        record=pool.get(tuple(key))
        if record:
            unit=repo.expand_unit(record)
            if eligible(repo,unit,previous.get(tuple(key)),context):selected.append((end-1,unit))
        if len(selected)==count:break
    if not selected:
        state.update(queue_cursor=end,remaining=state['queue_total']-end,
                     status='pending' if end<state['queue_total'] else 'complete')
        persist();return state
    timeout=min(ca.ANALYSIS_TIMEOUT_SECONDS,deadline-clock()-30) if deadline else ca.ANALYSIS_TIMEOUT_SECONDS
    if timeout<30:return state # No timestamp/credit progress for merely running out of time.
    if not repo.config.get('OPENAI_API_KEY'):
        state.update(status='error',reason='api_access');persist();return state
    state.update(status='running',batch_end=end,inflight_batch=[ca.receipt(u,context,repo) for i,u in selected],
                 processing_model=model,processing_tier=ca.ANALYSIS_SERVICE_TIER)
    state.pop('inflight',None);persist()
    service_error=None;failed_positions=[]
    with ThreadPoolExecutor(max_workers=len(selected)) as executor:
        pending={executor.submit(ca.analyze,u,context,root=repo.analysis_worker(n),timeout=timeout):(i,u)
                 for n,(i,u) in enumerate(selected)}
        for future in as_completed(pending):
            index,unit=pending[future]
            terminal=False
            try:
                result=future.result()
                result['content_fingerprint']=ca.fingerprint(unit);result['requested_model']=model
                repo.append_analysis(result)
                state['completed']=state.get('completed',0)+1;terminal=True
            except CloudStorageError:raise
            except ca.AnalysisServiceError as error:
                service_error=error.reason;failed_positions.append(index)
            except (ValueError,TypeError,KeyError,RuntimeError) as error:
                repo.append_analysis(ca.failure_result(repo,unit,context,ca.item_failure_reason(error)))
                state['review_required']=state.get('review_required',0)+1;terminal=True
            if terminal:
                receipt=ca.receipt(unit,context,repo)
                state['inflight_batch']=[t for t in state['inflight_batch'] if t!=receipt]
                state['primary_since_review']=state.get('primary_since_review',0)+1
                state['remaining']=max(0,state.get('remaining',state['queue_total']-offset)-1)
                persist() # Statistics see each result before the other worker finishes.
    state['queue_cursor']=min(failed_positions) if failed_positions else end
    state['remaining']=state['queue_total']-state['queue_cursor']
    state.pop('inflight_batch',None);state.pop('batch_end',None)
    state['status']='error' if service_error else 'pending' if state['remaining'] else 'complete'
    if service_error:state['reason']=service_error
    else:state.pop('reason',None)
    persist();return state
