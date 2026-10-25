"""Inclusive publication cutoff. Original archive rows are never deleted."""
from datetime import datetime

STATE = 'collection-cutoff.json'


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Laiko ribai būtina laiko juosta.')
    return parsed


def current(repo):
    value = repo.read(STATE,{}) or {}
    cutoff = value.get('published_until')
    if cutoff is not None:
        instant(cutoff)
    return cutoff


def allows(record, cutoff, *, field='published_at'):
    return cutoff is None or instant(record[field]) <= instant(cutoff)


def cursor(cutoff):
    # Diaspora max_time is exclusive; include the boundary second, then apply
    # the exact inclusive comparison (including fractional seconds) locally.
    import math
    return math.floor(instant(cutoff).timestamp())+1 if cutoff else None


def records(items, cutoff):
    if not cutoff:
        return list(items)
    result = []
    for record in items:
        if not allows(record,cutoff):
            continue
        row = record
        if isinstance(record.get('interactions'),list) and isinstance(record.get('counters'),dict):
            actions=record['interactions']
            kept=[a for a in actions if a.get('published_at') and allows(a,cutoff)]
            counters={};completeness={}
            for key,kind in (('comments','comment'),('likes','like'),('shares','share')):
                if key not in record['counters']:
                    continue
                group=[a for a in actions if a.get('kind')==kind]
                complete=(record.get('interaction_completeness') or {}).get(key,record.get('interactions_complete',False))
                complete=bool(complete and all(a.get('published_at') for a in group))
                completeness[key]=complete
                counters[key]=sum(a.get('kind')==kind for a in kept) if complete else None
            row={**record,'interactions':kept,'counters':counters,
                 'interaction_completeness':completeness,'interactions_complete':all(completeness.values()),
                 'counter_scope':'published_until','published_until':cutoff}
        result.append(row)
    return result


def packet(value, cutoff):
    if not cutoff:
        return value
    selected=records(value['records'],cutoff)
    return {**value,'records':selected,'published_until':cutoff,
            'record_keys':[{'source':r['source'],'id':r['id']} for r in selected],
            'post_count':sum(r.get('kind')!='comment' for r in selected),
            'comment_count':sum(r.get('kind')=='comment' for r in selected)}


def retained(repo, cutoff):
    if not cutoff:
        return []
    rows = repo.sql("""WITH latest AS (SELECT packet FROM signalas_fetches
        WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1)
        SELECT COALESCE(jsonb_agg(jsonb_build_object('source',c.source,'id',c.content_id,
            'kind',c.payload->'kind') ORDER BY ref.n),'[]'::jsonb)
        FROM latest,LATERAL jsonb_array_elements(packet->'record_keys') WITH ORDINALITY ref(k,n)
        JOIN signalas_content c ON c.scope=$1 AND c.source=ref.k->>'source' AND c.content_id=ref.k->>'id'
        WHERE (c.payload->>'published_at')::timestamptz <= $2::timestamptz""",[repo.scope,cutoff])['rows']
    import json
    return json.loads(rows[0][0]) if rows else []
