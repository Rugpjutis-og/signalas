"""Explicit administrator decisions in Neon. No public viewer can approve a type.
Run with server DATABASE_URL credentials; --help is safe and does not connect.
"""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import narrative_registry as registry_api


def decide(saved, candidate, action, actor, *, definition=None, target_id=None):
    if action not in ('approve', 'merge', 'reject') or not actor.strip():
        raise ValueError('Reikia administratoriaus ir galiojančio sprendimo.')
    if candidate.get('status') != 'candidate' or not candidate['id'].startswith('C'):
        raise ValueError('Sprendimas galimas tik kandidatui.')
    policy = registry_api.CANDIDATE_POLICY
    if (candidate.get('unit_count',0) < policy['independent_units'] or
            candidate.get('thread_count',0) < policy['threads'] or
            candidate.get('author_count',0) < candidate.get('required_authors',policy['unknown_audience_authors'])):
        raise ValueError('Kandidatas neatitinka pasikartojimo ir sklaidos kriterijų.')
    value = copy.deepcopy(saved or {})
    if candidate['id'] in value.get('decisions', {}): raise ValueError('Kandidatas jau peržiūrėtas.')
    registry = registry_api.load()
    types = registry['types'] + value.get('approved_types', [])
    if candidate['registry_version'] != registry['version'].rsplit('+',1)[0]+'+'+str(value.get('revision',0)):
        raise ValueError('Registras pasikeitė. Kandidatą reikia pervertinti.')
    ids = {t['id'] for t in types}
    if action == 'approve':
        if not isinstance(definition, dict): raise ValueError('Patvirtinimui reikia apibrėžties JSON.')
        required = ('title','claim_template','include_when','exclude_when','topic_id')
        if not all(isinstance(definition.get(k),str) and definition[k].strip() for k in required):
            raise ValueError('Užpildykite pavadinimą, teiginį, temą ir abu priskyrimo kriterijus.')
        topics = {t['id']:t['name'] for t in registry['topics']}
        secondary = definition.get('secondary_topics', [])
        if definition['topic_id'] not in topics or not isinstance(secondary,list) or any(t not in topics for t in secondary):
            raise ValueError('AI ir administratorius šiame veiksme nekeičia 15 temų katalogo.')
        broader = definition.get('broader_type')
        if broader is not None and broader not in ids: raise ValueError('Nežinomas bendresnis tipas.')
        if registry_api.normalized(definition['claim_template']) in {registry_api.normalized(t['claim_template']) for t in types}:
            raise ValueError('Toks teiginys jau registre; rinkitės prijungimą.')
        target_id = 'N%03d' % (max(int(t[1:]) for t in ids)+1)
        entry = {k:definition[k].strip() for k in required}
        entry.update(id=target_id,topic_name=topics[entry['topic_id']],secondary_topics=secondary,
                     broader_type=broader,source_locations='Administratorius: '+candidate['id'])
        value.setdefault('approved_types', []).append(entry)
    elif action == 'merge' and target_id not in ids: raise ValueError('Nežinomas prijungimo tipas.')
    elif action == 'reject': target_id = None
    decision = {'action':action,'actor':actor,'at':datetime.now(timezone.utc).isoformat(),
                'candidate':copy.deepcopy(candidate),'replaced_by':target_id,
                'reclassification_required':action in ('approve','merge')}
    value.setdefault('decisions', {})[candidate['id']] = decision
    value.setdefault('history', []).append({'candidate_id':candidate['id'],**{k:v for k,v in decision.items() if k!='candidate'}})
    if target_id: value.setdefault('aliases', {})[candidate['id']] = target_id
    value['revision'] = value.get('revision',0)+1
    return value


def save_decision(repository, candidate, action, actor, **kwargs):
    old = repository.read(registry_api.STATE_NAME)
    new = decide(old, candidate, action, actor, **kwargs)
    rows = repository.sql('''INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,$3::jsonb)
        ON CONFLICT(scope,name) DO UPDATE SET value=EXCLUDED.value
        WHERE signalas_state.value=$4::jsonb RETURNING name''',
        [repository.scope,registry_api.STATE_NAME,json.dumps(new),json.dumps(old)])['rows']
    if not rows: raise ValueError('Kitas administratorius pakeitė registrą. Atnaujinkite ir peržiūrėkite sprendimą.')
    repository.values[registry_api.STATE_NAME] = new
    return new


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['list','approve','merge','reject'])
    parser.add_argument('--candidate');parser.add_argument('--actor');parser.add_argument('--definition')
    parser.add_argument('--target')
    args=parser.parse_args()
    from cloud_repository import Repository
    from integration_config import settings
    from live_data import load
    from narrative_projection import candidates
    repo=Repository(settings())
    packet,_,assessments=load(repo)
    rows=candidates(packet,assessments,registry_api.load(repo),decisions=registry_api.state(repo).get('decisions',{}))
    if args.action=='list': print(json.dumps(rows,ensure_ascii=False,indent=2));return
    candidate=next((c for c in rows if c['id']==args.candidate),None)
    if candidate is None or not args.actor: parser.error('Reikia galiojančio kandidato ID ir --actor.')
    definition=json.loads(Path(args.definition).read_text()) if args.definition else None
    result=save_decision(repo,candidate,args.action,args.actor,definition=definition,target_id=args.target)
    print(json.dumps({'status':'saved','revision':result['revision']},ensure_ascii=False))

if __name__=='__main__': main()
