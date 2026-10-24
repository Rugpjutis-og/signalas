"""Explicit organizer-supplied roles in a fictional exercise; never identity-only labels."""
import json
import time
import uuid
from datetime import datetime,timezone
from urllib.parse import quote

from scenario_supplement import context_digest
from diaspora_client import DiasporaClient,DiasporaRequestError
from cloud_repository import ASSESSMENTS

STATE='exercise-account-context.json'


def current(repo):
    if not hasattr(repo,'read'):return None
    state=repo.read(STATE)
    if not isinstance(state,dict) or state.get('base_context_digest')!=context_digest(repo.read('live-context.json')):
        return None
    return state


def matches(state,unit):
    if not state or unit.get('source')!=state.get('source') or unit.get('exercise_id')!=state.get('exercise_id'):
        return False
    if unit.get('author_id') in set(state.get('account_ids',{}).values()):return True
    handle=unit.get('author_handle')
    if not isinstance(handle,str):return False
    return handle.casefold() in {name+'@'+state['source'] for name in state.get('usernames',[])}


def for_unit(repo,unit):
    state=current(repo)
    if not matches(state,unit):return None
    return {'revision':state['revision'],'provenance':'exercise_organizer',
        'scenario_role':'organizer_identified_adversarial_exercise_account',
        'interpretation':'Tai fiktyvių pratybų organizatoriaus pateiktas vaidmuo. Tai nėra šio įrašo krypties ar autoriaus tikrųjų politinių pažiūrų įrodymas.'}


def needs_service(repo):
    state=current(repo)
    return bool(state and state.get('status') in ('pending','resolving','queue_pending'))


def append_review(repo,state):
    """Called under the shared lease; append finite targets without replacing an active pass."""
    import thermometer_recheck as review
    from live_data import fingerprint
    from thermometer_review import saved,applicable,key
    from narrative_registry import load as registry
    context=repo.read('live-context.json')
    job=repo.read(review.STATE,{}) or {}
    if state['revision'] in job.get('account_context_requests',[]):return
    records=repo.latest()['records'];manuals=saved(repo)
    version=registry(repo)['version']
    rows=repo.sql(ASSESSMENTS+'''SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'source',a->'source_reference'->'source','id',a->'source_reference'->'id',
        'fingerprint',a->'content_fingerprint')),'[]'::jsonb) FROM assessments
        WHERE (a->>'analysis_executed'='true' OR a->>'processing_disposition'='needs_review')
          AND a->>'registry_version'=$2 AND a->>'thermometer_rules_version'=$3
          AND COALESCE(a->'exercise_context','null'::jsonb)=$4::jsonb
          AND COALESCE(a->'exercise_id','null'::jsonb)=$5::jsonb''',
          [repo.scope,version,review.VERSION,json.dumps(context),json.dumps(state.get('exercise_id'))])['rows']
    bindings={(v['source'],v['id'],v['fingerprint']) for v in json.loads(rows[0][0])} if rows else set()
    targets=[];manual_skips=0
    for record in records:
        if not matches(state,record):continue
        unit=repo.expand_unit(record)
        if applicable(manuals.get(key(unit['source'],unit['id'])),unit,context):
            manual_skips+=1;continue
        digest=fingerprint(unit)
        if (unit['source'],unit['id'],digest) not in bindings:continue # Main queue handles new units.
        targets.append({'source':unit['source'],'id':unit['id'],'content_fingerprint':digest,
            'exercise_id':unit.get('exercise_id'),'account_context_revision':state['revision']})
    # An existing pending target for this same unit can perform the requested new pass.
    pending={(t['source'],t['id'],t['content_fingerprint']):t
             for t in job.get('targets',[])[job.get('cursor',0)+bool(job.get('inflight')):]}
    extra=[]
    for target in targets:
        existing=pending.get((target['source'],target['id'],target['content_fingerprint']))
        if existing is not None:existing['account_context_revision']=state['revision']
        else:extra.append(target)
    if not job or job.get('status')=='complete':
        # Keep completed pass metadata as the existing review subsystem already does.
        if job:repo.write('thermometer-recheck-history/'+job['run_id'],job)
        job={'status':'pending','run_id':uuid.uuid4().hex,'processing_model':review.MODEL,
            'kind':'thermometer_recheck','targets':targets,'exercise_context':context,
            'rules_version':review.VERSION,'registry_version':version,'cursor':0,
            'completed':0,'classified':0,'review_required':0,'failed':0,'skipped':0,
            'started_at':datetime.now(timezone.utc).isoformat()}
    else:
        job['targets'].extend(extra)
    job.setdefault('account_context_requests',[]).append(state['revision'])
    job['total']=len(job['targets']);job['remaining']=job['total']-job.get('cursor',0)
    job['updated_at']=datetime.now(timezone.utc).isoformat()
    if not job['remaining']:job['status']='complete'
    repo.write(review.STATE,job)
    state.update(status='complete',review_targets=len(targets),manual_skips=manual_skips,
        matched_accounts=len(state.get('account_ids',{})),updated_at=job['updated_at'])
    repo.write(STATE,state)


def service(repo,*,deadline=None,monotonic=None):
    """Vercel-only directory lookup. No cookies or source profile bodies are persisted."""
    clock=monotonic or time.monotonic
    stop=min(deadline or clock()+100,clock()+100)
    state=current(repo)
    if not state or not needs_service(repo):return {'status':'idle'}
    owner=uuid.uuid4().hex
    acquired=repo.sql('''INSERT INTO signalas_jobs(scope,owner,expires_at)
        VALUES($1,$2,now()+interval '6 minutes') ON CONFLICT(scope) DO UPDATE
        SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
        WHERE signalas_jobs.expires_at<now() RETURNING owner''',[repo.scope,owner])['rows']
    if not acquired:return {'status':'already_running'}
    try:
        repo.values.pop(STATE,None);state=current(repo)
        if not state or state.get('status')=='complete':return {'status':'complete'}
        if state.get('cursor',0)<len(state['usernames']):
            client=DiasporaClient(repo.config.get('DIASPORA_BASE_URL','https://'+state['source']),
                repo.config.get('DIASPORA_USERNAME'),repo.config.get('DIASPORA_PASSWORD'))
            client.login()
            while state.get('cursor',0)<len(state['usernames']) and clock()+30<stop:
                name=state['usernames'][state.get('cursor',0)]
                try:
                    profile=client.json('/u/'+quote(name,safe=''))
                    handle=profile.get('diaspora_id') if isinstance(profile,dict) else None
                    if isinstance(handle,str) and handle.casefold()==name+'@'+state['source'] and isinstance(profile.get('guid'),str) and profile['guid']:
                        state.setdefault('account_ids',{})[name]=profile['guid']
                    else:state.setdefault('unresolved',{})[name]='source_identity_unconfirmed'
                except DiasporaRequestError as e:
                    if e.http_status!=404:raise
                    state.setdefault('unresolved',{})[name]='source_profile_404'
                state.update(status='resolving',cursor=state.get('cursor',0)+1)
                repo.write(STATE,state)
        if state.get('cursor',0)==len(state['usernames']):
            state['status']='queue_pending';repo.write(STATE,state)
            if clock()+35<stop:append_review(repo,state)
        return {'status':state['status'],'resolved':len(state.get('account_ids',{})),'total':len(state['usernames'])}
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2',[repo.scope,owner])
