"""Project validated multi-claim assessments into types, variants and candidate queues."""
import math
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import narrative_registry as registry_api
from metrics import audience_ids
from thermometer import instant


def key(unit): return (unit['source'], unit['id'])

def candidate_id(exercise_id, proposal):
    return 'C' + registry_api.digest([exercise_id, proposal['topic_id'], registry_api.normalized(proposal['claim_template'])])[:24]


def valid_analysis(record, analysis, registry):
    if (not analysis or analysis.get('registry_version') != registry['version'] or
            analysis.get('exercise_id') != record.get('exercise_id')): return None
    try:
        return registry_api.validate(analysis['result']['narrative_analysis'], registry, record.get('text', ''))
    except (KeyError, TypeError, ValueError): return None


def canonical_entities(entities, context):
    aliases = {registry_api.normalized(p['realName']): registry_api.normalized(p['exerciseName'])
               for p in (context or {}).get('nameMappings', [])}
    return {k: aliases.get(registry_api.normalized(v), registry_api.normalized(v)) for k,v in entities.items()}


def project(records, analyses, registry, days, zone, context, exercise_id):
    definitions = {t['id']: t for t in registry['types']}
    topics = {t['id']:t['app_id'] for t in registry['topics']}
    narratives, units, reanalysis = {}, [], 0
    seen = set()
    for record in records:
        if key(record) in seen: continue
        seen.add(key(record))
        analysis = analyses.get(key(record))
        result = valid_analysis(record, analysis, registry)
        reanalysis += bool(analysis and result is None)
        unit = {**record, 'analysis': analysis['result'] if analysis else None,
                'analysis_executed': bool(analysis), 'narrative_analysis': result,
                'match_status': result['match_status'] if result else 'requires_reanalysis' if analysis else 'not_analyzed',
                'narrative_ids': [], 'stance': 'unknown'}
        units.append(unit)
        for match in result['matches'] if result else []:
            t = definitions[match['type_id']]
            unit['narrative_ids'].append(t['id'])
            if t['id'] not in narratives:
                narratives[t['id']] = {'id':t['id'], 'title':t['title'], 'lines':[t['title'][:27],t['title'][27:54]],
                    'description':t['claim_template'], 'include_when':t['include_when'], 'exclude_when':t['exclude_when'],
                    'broader_type':t['broader_type'], 'theme':topics[t['topic_id']], 'source':'user_list',
                    'status':'confirmed','fixed':False,'is_live':True,'history_complete':False,
                    'exercise_id':exercise_id,'days':[0]*len(days),'dailyStances':[[0,0,0] for _ in days],
                    'evidence':[],'variants':{},'firstSeenAt':record['published_at'], 'first':'', 'actors':[], 'places':[],
                    'secondaryThemes':[topics[v] for v in t['secondary_topics']], 'registry_version':registry['version']}
            n = narratives[t['id']]
            variant_id = 'V' + registry_api.digest([record.get('exercise_id',exercise_id),t['id'],canonical_entities(match['instance_entities'],context)])[:20]
            evidence = {**record,'stance':match['stance'],'narrative_evidence':match['evidence'],
                        'variant_id':variant_id,'instance_entities':match['instance_entities']}
            n['evidence'].append(evidence)
            n['variants'].setdefault(variant_id, {'id':variant_id,'entities':match['instance_entities'],'evidence':[]})['evidence'].append(evidence)
            index = days.index(instant(record['published_at']).astimezone(zone).date().isoformat())
            n['days'][index] += 1
            if match['stance'] in registry_api.STANCES[:3]: n['dailyStances'][index][registry_api.STANCES.index(match['stance'])] += 1
            if instant(record['published_at']) < instant(n['firstSeenAt']): n['firstSeenAt'] = record['published_at']
    for n in narratives.values():
        n['variants'] = list(n['variants'].values())
        known = sum(sum(day) for day in n['dailyStances'])
        n['stance_coverage'] = {'known':known,'unknown':len(n['evidence'])-known,'percent':100*known/len(n['evidence'])}
        n['actors'] = sorted({v['entities']['subject'] for v in n['variants'] if v['entities']['subject']})
        n['places'] = sorted({v['entities']['place'] for v in n['variants'] if v['entities']['place']})
    # Rollup is explicit and deduplicated. It never adds a second direct assignment.
    rollups = {}
    for identity in definitions:
        descendants = {identity}
        while True:
            enlarged = descendants | {t['id'] for t in definitions.values() if t['broader_type'] in descendants}
            if enlarged == descendants: break
            descendants = enlarged
        rollups[identity] = len({key(u) for child in descendants if child in narratives for u in narratives[child]['evidence']})
    relations = [{'id':'registry-'+t['id'], 'a':t['broader_type'], 'b':t['id'], 'type':'branch',
                  'label':'Registro potipis', 'explanation':'Patvirtinto registro bendresnio ir konkretesnio tipo ryšys; tai nėra koordinavimo įrodymas.'}
                 for t in definitions.values() if t['broader_type'] in narratives and t['id'] in narratives]
    return {'units':units,'narratives':list(narratives.values()),'relations':relations, 'type_rollups':rollups,
            'requires_reanalysis_count':reanalysis,
            'assigned_unit_count':len({key(u) for n in narratives.values() for u in n['evidence']})}


def candidates(packet, analyses, registry, *, now=None, decisions=None):
    """No promotion to a registered type. Unproven identities/threads never invent diversity."""
    policy = registry_api.CANDIDATE_POLICY
    until = now or datetime.now(timezone.utc)
    start = until - timedelta(hours=policy['window_hours'])
    if packet.get('exercise_started_at'): start = max(start, instant(packet['exercise_started_at']))
    exercise_id = packet.get('exercise_id')
    # A single complete snapshot must cover the whole candidate window.
    membership = [s for s in packet.get('membership_snapshots', [])
                  if audience_ids(s,exercise_id,start.isoformat()) is not None
                  and audience_ids(s,exercise_id,(until-timedelta(microseconds=1)).isoformat()) is not None]
    sets = [audience_ids(s,exercise_id,start.isoformat()) for s in membership]
    audience = len(sets[0]) if sets and all(s == sets[0] for s in sets) else None
    threshold = max(policy['minimum_authors'],math.ceil(policy['author_fraction']*audience)) if audience is not None else policy['unknown_audience_authors']
    clusters = {}
    seen = set()
    for record in sorted(packet['records'],key=lambda u:(instant(u['published_at']),u['source'],u['id'])):
        if key(record) in seen: continue
        seen.add(key(record))
        if not start <= instant(record['published_at']) < until: continue
        if record.get('exercise_id') != exercise_id or record.get('kind') == 'reshare': continue
        analysis = valid_analysis(record,analyses.get(key(record)),registry)
        if not analysis: continue
        for proposal in analysis['proposals']:
            identity = candidate_id(exercise_id,proposal)
            if identity in (decisions or {}): continue
            c = clusters.setdefault(identity, {'id':identity,'status':'candidate','exercise_id':exercise_id,
                **proposal,'evidence':[], 'first_seen':record['published_at'], 'last_seen':record['published_at']})
            # Each independent wording contributes once, irrespective of reshares/likes.
            wording = registry_api.normalized(record.get('text',''))
            if not wording or any(SequenceMatcher(None,wording,registry_api.normalized(u['text']),autojunk=False).ratio() >= policy['near_duplicate_similarity'] for u in c['evidence']): continue
            c['evidence'].append({**record,'narrative_evidence':proposal['evidence'],'stance':'unknown'})
            c['last_seen'] = record['published_at']
    eligible=[]
    for c in clusters.values():
        independent = c['evidence']
        authors={u['author_id'] for u in independent if u.get('author_id')}
        threads={(u['source'],u.get('thread_id') or u.get('parent_id') or (u.get('parent_post') or {}).get('id') or (u['id'] if u.get('kind')=='post' else None)) for u in independent}
        threads={t for t in threads if t[1]}
        if audience == 0 or len(independent)<policy['independent_units'] or len(authors)<threshold or len(threads)<policy['threads']: continue
        c.update(unit_count=len({key(u) for u in independent}),author_count=len(authors),thread_count=len(threads),
                 audience=audience,required_authors=threshold,window_start=start.isoformat(),window_end=until.isoformat(),
                 exercise_known=bool(exercise_id),registry_version=registry['version'])
        eligible.append(c)
    return eligible
