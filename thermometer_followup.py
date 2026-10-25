"""One approved, deferred direction audit after primary and prior review drain.

No source collection, AI calls, whole snapshot reads or historical result bodies.
"""
import json
import uuid
from datetime import datetime, timezone

from cloud_repository import ASSESSMENTS
from scenario_supplement import context_digest, current as supplement
from thermometer_review import saved, key
from thermometer_policy import VERSION
from narrative_registry import load as registry

STATE = 'thermometer-followup.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def candidates(repo, context, version):
    # Filter after selecting the newest applicable assessment, never resurrect an
    # old neutral result beneath a newer destabilizing/error result.
    rows = repo.sql(ASSESSMENTS + """, latest AS (
        SELECT DISTINCT ON(a->'source_reference'->>'source',a->'source_reference'->>'id') a
        FROM assessments WHERE a->>'registry_version'=$2 AND a->>'thermometer_rules_version'=$3
          AND COALESCE(a->'exercise_context','null'::jsonb)=$4::jsonb
        ORDER BY a->'source_reference'->>'source',a->'source_reference'->>'id',
                 stage DESC,n DESC,COALESCE(a->>'recorded_at',a->>'classified_at',a->>'analyzed_at','') DESC
    ), snapshot AS (
        SELECT packet FROM signalas_fetches WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1
    ) SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'source',c.source,'id',c.content_id,'content_fingerprint',a->'content_fingerprint',
        'exercise_id',a->'exercise_id','previous_category',a->'result'->'thermometer_category',
        'published_at',c.payload->'published_at','author_id',c.payload->'author_id',
        'author_handle',c.payload->'author_handle')
        ORDER BY (c.payload->>'published_at')::timestamptz DESC,c.source,c.content_id),'[]'::jsonb)
    FROM latest JOIN signalas_content c ON c.scope=$1
      AND c.source=a->'source_reference'->>'source' AND c.content_id=a->'source_reference'->>'id'
    CROSS JOIN snapshot
    WHERE a->'result'->>'thermometer_status'='classified'
      AND a->'result'->>'thermometer_category' IN('neutral','stabilizing')
      AND EXISTS(SELECT 1 FROM jsonb_array_elements(packet->'record_keys') ref
                 WHERE ref->>'source'=c.source AND ref->>'id'=c.content_id)""",
        [repo.scope, version, VERSION, json.dumps(context)])['rows']
    return json.loads(rows[0][0]) if rows else []


def maybe_start(repo):
    import thermometer_recheck as review
    request = repo.read(STATE, {}) or {}
    if request.get('status') not in ('waiting_primary', 'waiting_existing_review'):
        return request
    if (repo.read('analysis-job.json', {}) or {}).get('status') != 'complete':
        return request
    if (repo.read(review.STATE, {}) or {}).get('status') not in (None, 'complete'):
        return request
    owner = uuid.uuid4().hex
    acquired = repo.sql("""INSERT INTO signalas_jobs(scope,owner,expires_at)
        VALUES($1,$2,now()+interval '6 minutes') ON CONFLICT(scope) DO UPDATE
        SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
        WHERE signalas_jobs.expires_at<now() RETURNING owner""", [repo.scope,owner])['rows']
    if not acquired:
        return request
    try:
        repo.values.clear()
        request = repo.read(STATE, {}) or {}
        if request.get('status') not in ('waiting_primary','waiting_existing_review'):
            return request
        primary = repo.read('analysis-job.json', {}) or {}
        old = repo.read(review.STATE, {}) or {}
        if primary.get('status') != 'complete' or old.get('status') not in (None,'complete'):
            return request
        # Crash recovery: the job was committed before the small request receipt.
        if old.get('request_id') == request['request_id']:
            request.update(status='scheduled',run_id=old['run_id'],total=old['total'],updated_at=now())
            repo.write(STATE,request)
            return request
        from openai_analysis import context_data
        context = context_data(repo.read('live-context.json'))
        detail = supplement(repo)
        from exercise_accounts import current, matches
        actors = current(repo)
        scoring = actors.get('scoring_rule',{}) if actors else {}
        if (context_digest(context) != request.get('base_context_digest') or not detail
                or detail['id'] != request.get('supplement_id')
                or scoring.get('id') != request.get('scoring_rule_id')
                or scoring.get('historical_review_enabled') is not True):
            request.update(status='paused',reason='context_or_rule_changed',updated_at=now())
            repo.write(STATE,request)
            return request
        version = registry(repo)['version']
        manuals = saved(repo)
        targets = []
        manual_skips = 0
        for unit in candidates(repo,context,version):
            manual = manuals.get(key(unit['source'],unit['id']))
            if manual and (manual.get('content_fingerprint')==unit['content_fingerprint']
                    and manual.get('exercise_id')==unit.get('exercise_id')
                    and manual.get('exercise_context')==context and manual.get('rules_version')==VERSION):
                manual_skips += 1
                continue
            target = {k:unit[k] for k in ('source','id','content_fingerprint','exercise_id','previous_category')}
            if matches(actors,unit):
                target.update(account_context_revision=actors['revision'],scoring_rule_id=scoring['id'])
            targets.append(target)
        stamp = now()
        job = {'status':'pending' if targets else 'complete','kind':'thermometer_recheck',
               'run_id':uuid.uuid4().hex,'processing_model':review.MODEL,
               'request_id':request['request_id'],'targets':targets,'cursor':0,'total':len(targets),
               'remaining':len(targets),'completed':0,'classified':0,'review_required':0,
               'failed':0,'skipped':0,'reassigned':0,'retained':0,
               'selection_categories':['neutral','stabilizing'],'preserve_previous':True,
               'scenario_supplement_review':detail['id'],'exercise_context':context,
               'rules_version':VERSION,'registry_version':version,
               'started_at':stamp,'updated_at':stamp,'ordering_policy':'published_at_desc',
               'manual_skips':manual_skips}
        if old:
            repo.write('thermometer-recheck-history/'+old['run_id'],old)
        repo.write(review.STATE,job)
        request.update(status='scheduled',run_id=job['run_id'],total=len(targets),
                       manual_skips=manual_skips,updated_at=stamp)
        repo.write(STATE,request)
        return request
    finally:
        repo.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2',[repo.scope,owner])
