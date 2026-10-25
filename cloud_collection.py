"""Resumable Vercel collection. Private checkpoints/changed bodies live only in Neon."""
import hashlib
import json
import math
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import quote, urlencode, urlsplit

from cloud_storage import query
from diaspora_client import DiasporaRequestError
import collection_cutoff as cutoff_policy

STATE = 'collection-job.json'
BATCH_SIZE = 4
STEP_SECONDS = 205
RESERVE_SECONDS = 105  # One source detail + canonical request + Neon commit, all bounded.


def now():
    return datetime.now(timezone.utc).isoformat()


def status(repo):
    method=getattr(repo,'collection_progress',None)
    if callable(method):
        result=method()
        if isinstance(result,dict):return result
    state=repo.read(STATE,{}) or {}
    return {'kind':'collection','status':state.get('status','idle'),
        'phase':state.get('phase'),'processed_posts':state.get('detail_cursor',0),
        'discovered_posts':len(state.get('entries',[])),
        'remaining':max(0,len(state.get('entries',[]))-state.get('detail_cursor',0))}


def previous(repo, entries, source):
    ids = [str(e['guid']) for e in entries]
    rows = repo.sql('''SELECT payload FROM signalas_content WHERE scope=$1 AND source=$2
        AND (content_id=ANY($3::text[]) OR payload->>'parent_id'=ANY($3::text[]))''',
        [repo.scope, source, ids])['rows']
    return {'records': [json.loads(r[0]) for r in rows]}


def checkpoint(repo, state, changed=()):
    # Changed compact units are staged once. The last published snapshot is untouched.
    staged = [{'name': 'collection-stage/'+state['run_id']+'/'+hashlib.sha256(
        json.dumps([u['source'],u['id']]).encode()).hexdigest(), 'value': u} for u in changed]
    query(repo.connection, [
        {'query': '''INSERT INTO signalas_state(scope,name,value)
            SELECT $1,r->>'name',r->'value' FROM jsonb_array_elements($2::jsonb) r
            ON CONFLICT(scope,name) DO UPDATE SET value=EXCLUDED.value''',
         'params': [repo.scope, json.dumps(staged, ensure_ascii=False)]},
        {'query': '''INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,$3::jsonb)
            ON CONFLICT(scope,name) DO UPDATE SET value=EXCLUDED.value''',
         'params': [repo.scope,STATE,json.dumps(state,ensure_ascii=False)]}])
    repo.values[STATE] = state


def finish(repo, state):
    if state['entries'] and not state['record_keys']:
        raise DiasporaRequestError('source_details_unavailable', 404)
    stamp = now()
    manifest = {'storage_version': 2, 'collected_at': stamp, 'source': state['source'],
        'mode':'live_sample','coverage':'account_stream_and_own_profile','stream_complete':False,
        'exercise_id':None,'membership':None,'record_keys':state['record_keys'],
        'post_count':state['post_count'],'comment_count':state['comment_count'],
        'published_until':state.get('published_until'),
        'limits':{'post_limit':None,'pages_read':sum(state['pages'].values()),'comments_truncated':False},
        'account_scope':{'feed_posts':state['counts']['feed'],'own_profile_posts':state['counts']['profile'],
            'feed_pages':state['pages']['feed'],'profile_pages':state['pages']['profile'],'pagination_complete':True},
        'collection_stats':{'detail_requests':len(state['entries']),'not_modified':state['not_modified'],
            'detail_bodies':len(state['entries'])-state['not_modified'],'workers':BATCH_SIZE,
            'unavailable_details':state['unavailable_details'],'resumed':True}}
    body=json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    snapshot=hashlib.sha256(body.encode()).hexdigest()
    complete={'status':'complete','run_id':state['run_id'],'updated_at':stamp,
              'collected_at':stamp,'processed_posts':len(state['entries'])}
    prefix='collection-stage/'+state['run_id']+'/%'
    # Publish bodies and manifest together, then remove only this run's transient staging.
    query(repo.connection,[
        {'query':'''INSERT INTO signalas_content(scope,source,content_id,collected_at,payload)
            SELECT $1,value->>'source',value->>'id',$2::timestamptz,value
            FROM signalas_state WHERE scope=$1 AND name LIKE $3
            ON CONFLICT(scope,source,content_id) DO UPDATE
            SET collected_at=EXCLUDED.collected_at,payload=EXCLUDED.payload
            WHERE EXCLUDED.collected_at>=signalas_content.collected_at
              AND signalas_content.payload IS DISTINCT FROM EXCLUDED.payload''',
         'params':[repo.scope,stamp,prefix]},
        {'query':'''INSERT INTO signalas_fetches(scope,snapshot_id,collected_at,packet)
            VALUES($1,$2,$3::timestamptz,$4::jsonb) ON CONFLICT DO NOTHING''',
         'params':[repo.scope,snapshot,stamp,body]},
        {'query':'DELETE FROM signalas_state WHERE scope=$1 AND name LIKE $2','params':[repo.scope,prefix]},
        {'query':'''INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,$3::jsonb)
            ON CONFLICT(scope,name) DO UPDATE SET value=EXCLUDED.value''',
         'params':[repo.scope,STATE,json.dumps(complete)]}])
    repo.values[STATE]=complete
    repo.packet=None
    return {'status':'ok','posts':state['post_count'],'comments':state['comment_count'],'collected_at':stamp}


def run_step(repo, client, *, seconds=STEP_SECONDS, monotonic=None):
    clock=monotonic or time.monotonic
    deadline=clock()+seconds
    state=repo.read(STATE,{}) or {}
    cutoff=cutoff_policy.current(repo)
    if state.get('status') not in ('running','error') or state.get('published_until') != cutoff:
        state={'status':'running','run_id':uuid.uuid4().hex,'source':urlsplit(client.base).hostname,
            'phase':'feed','cursor':None,'entries':[],'seen':[], 'record_keys':[], 'detail_cursor':0,
            'pages':{'feed':0,'profile':0},'counts':{'feed':0,'profile':0},'phase_seen':{'feed':[],'profile':[]},
            'post_count':0,'comment_count':0,'not_modified':0,'unavailable_details':0,'started_at':now()}
        kept=cutoff_policy.retained(repo,cutoff)
        state.update(published_until=cutoff,cursor=cutoff_policy.cursor(cutoff),
            record_keys=[{'source':r['source'],'id':r['id']} for r in kept],
            post_count=sum(r['kind']!='comment' for r in kept),
            comment_count=sum(r['kind']=='comment' for r in kept))
        checkpoint(repo,state)
    state['status']='running'
    client.login()  # Private session recreated per invocation; cookies are never persisted.
    while clock()+RESERVE_SECONDS < deadline:
        phase=state['phase']
        if phase in ('feed','profile'):
            if phase=='profile' and not state.get('profile_guid'):
                profile=client.json('/u/'+quote(client.username,safe=''))
                if not isinstance(profile,dict) or profile.get('is_own_profile') is not True or not profile.get('guid'):
                    raise ValueError('Nepavyko patvirtinti savo profilio.')
                state['profile_guid']=profile['guid']
            path='/stream.json' if phase=='feed' else '/people/'+quote(state['profile_guid'],safe='')+'/stream.json'
            cursor=state['cursor']
            page=client.json(path+('?' + urlencode({'max_time':cursor}) if cursor is not None else ''))
            if not isinstance(page,list):raise ValueError('Neatpažintas srauto puslapis.')
            seen=set(state['seen'])
            for entry in page:
                if not isinstance(entry,dict) or entry.get('id') is None or not entry.get('guid'):
                    raise ValueError('Srauto įrašui trūksta pastovaus ID.')
                if not cutoff_policy.allows(entry,cutoff,field='created_at'):
                    continue
                if entry['guid'] not in seen:
                    seen.add(entry['guid']);state['entries'].append({k:entry.get(k) for k in ('id','guid','created_at')})
            state['phase_seen'][phase]=list(set(state['phase_seen'][phase]) | {e['guid'] for e in page if cutoff_policy.allows(e,cutoff,field='created_at')})
            state['counts'][phase]=len(state['phase_seen'][phase])
            state['seen']=list(seen);state['pages'][phase]+=1
            if len(page)<15:
                state['phase']='profile' if phase=='feed' else 'details';state['cursor']=cutoff_policy.cursor(cutoff)
            else:
                oldest=min(datetime.fromisoformat(e['created_at'].replace('Z','+00:00')).timestamp() for e in page)
                following=math.floor(oldest)+1
                if cursor is not None and following>=cursor:
                    raise ValueError('Srauto laiko žymos neleidžia tęsti neprarandant įrašų.')
                state['cursor']=following
            state['updated_at']=now();checkpoint(repo,state)
        elif phase=='details':
            batch=state['entries'][state['detail_cursor']:state['detail_cursor']+BATCH_SIZE]
            if not batch:return finish(repo,state)
            prior=previous(repo,batch,state['source'])
            packet=client.collect_entries(batch,previous=prior,compact=True,workers=BATCH_SIZE,conditional=True,allow_empty=True)
            packet['records']=cutoff_policy.records(packet['records'],cutoff)
            known={(r['source'],r['id']):r for r in prior['records']}
            changed=[r for r in packet['records'] if known.get((r['source'],r['id']))!=r]
            keys={(r['source'],r['id']) for r in state['record_keys']}
            for r in packet['records']:
                if (r['source'],r['id']) not in keys:
                    state['record_keys'].append({'source':r['source'],'id':r['id']});keys.add((r['source'],r['id']))
                    state['comment_count' if r['kind']=='comment' else 'post_count']+=1
            state['not_modified']+=packet['collection_stats']['not_modified']
            state['unavailable_details']+=packet['collection_stats']['unavailable_details']
            state['detail_cursor']+=len(batch);state['updated_at']=now()
            checkpoint(repo,state,changed)
        else:raise ValueError('Neatpažintas surinkimo etapas.')
    return {'status':'pending','phase':state['phase'],'processed_posts':state['detail_cursor'],
            'discovered_posts':len(state['entries'])}
