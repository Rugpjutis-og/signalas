"""Administrator-approved thematic branches. No inference of stance or parent claim."""
import copy
import json
from datetime import datetime, timezone

STATE = 'narrative-subnarratives.json'


def approve(repo, candidates, assignments, *, actor):
    """Explicit finite approval. The parent relation is organizational, not claim equivalence."""
    import narrative_registry as registry_api
    if not isinstance(actor,str) or not actor.strip(): raise ValueError('Reikia administratoriaus.')
    registry=registry_api.load(repo)
    types={t['id']:t for t in registry['types']}
    known={c['id']:c for c in candidates}
    old=repo.read(STATE)
    value=copy.deepcopy(old or {'definitions':{}})
    for identity,parent_id in assignments.items():
        candidate=known.get(identity)
        parent=types.get(parent_id)
        from narrative_projection import candidate_id
        if (not candidate or candidate.get('status')!='candidate' or candidate_id(candidate.get('exercise_id'),candidate)!=identity
                or not parent or candidate['topic_id']!=parent['topic_id']):
            raise ValueError('Reikia galiojančio kandidato ir tos pačios temos pagrindinio naratyvo.')
        previous=value['definitions'].get(identity)
        if previous:
            if previous['parent_type_id']!=parent_id:raise ValueError('Subnaratyvas jau priskirtas kitam naratyvui.')
            continue
        definition={k:candidate[k] for k in ('id','title','claim_template','topic_id','exercise_id')}
        definition.update(parent_type_id=parent_id,relationship='thematic_branch',
                          counts_as_parent_match=False,status='confirmed',approved_by=actor,
                          approved_at=datetime.now(timezone.utc).isoformat())
        value['definitions'][identity]=definition
    if value==old:return value
    rows=repo.sql('''INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,$3::jsonb)
        ON CONFLICT(scope,name) DO UPDATE SET value=EXCLUDED.value
        WHERE signalas_state.value=$4::jsonb RETURNING name''',
        [repo.scope,STATE,json.dumps(value,ensure_ascii=False),json.dumps(old)])['rows']
    if not rows:raise ValueError('Subnaratyvų sąrašas pasikeitė. Reikia pakartotinės peržiūros.')
    repo.values[STATE]=value
    return value


def project(records, analyses, registry):
    from narrative_projection import key,valid_analysis,candidate_id
    definitions={d['id']:d for d in registry.get('subnarratives',[])}
    groups={}
    for record in records:
        assessment=valid_analysis(record,analyses.get(key(record)),registry)
        for proposal in assessment['proposals'] if assessment else []:
            identity=candidate_id(record.get('exercise_id'),proposal)
            definition=definitions.get(identity)
            if not definition or definition.get('exercise_id')!=record.get('exercise_id'):continue
            group=groups.setdefault(identity,{**definition,'evidence':{}})
            group['evidence'][key(record)]={**record,'narrative_evidence':proposal['evidence'],'stance':'unknown'}
    rows=[]
    for group in groups.values():
        evidence=sorted(group.pop('evidence').values(),key=lambda r:r['published_at'])
        group.update(evidence=evidence,unit_count=len(evidence),first_seen=evidence[0]['published_at'],last_seen=evidence[-1]['published_at'])
        rows.append(group)
    return rows


def attach(parents, branches, registry, days, exercise_id):
    types={t['id']:t for t in registry['types']}
    topics={t['id']:t['app_id'] for t in registry['topics']}
    by_id={n['id']:n for n in parents}
    for branch in branches:
        identity=branch['parent_type_id']; t=types[identity]
        if identity not in by_id:
            by_id[identity]={'id':identity,'title':t['title'],'lines':[t['title'][:27],t['title'][27:54]],
                'description':t['claim_template'],'include_when':t['include_when'],'exclude_when':t['exclude_when'],
                'broader_type':t['broader_type'],'theme':topics[t['topic_id']],'source':'user_list',
                'status':'confirmed','fixed':False,'is_live':True,'history_complete':False,'exercise_id':exercise_id,
                'days':[0]*len(days),'dailyStances':[[0,0,0] for _ in days],'evidence':[],'variants':[],
                'firstSeenAt':branch['first_seen'],'first':'','actors':[],'places':[],
                'secondaryThemes':[topics[v] for v in t['secondary_topics']],'registry_version':registry['version'],
                'stance_coverage':{'known':0,'unknown':0,'percent':None}}
        by_id[identity].setdefault('subnarratives',[]).append(branch)
    return list(by_id.values())


def compact(branches):
    # The bootstrap already contains source units. Do not resend their bodies/media per branch.
    return [{**b,'evidence':[{k:u.get(k) for k in ('source','id','published_at','narrative_evidence','stance')}
                            for u in b['evidence']]} for b in branches]
