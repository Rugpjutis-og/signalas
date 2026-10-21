"""Trial author score: content creation 80%, received comments 15%, reshares 5%."""
import hashlib
import json
import re
import unicodedata
from collections import defaultdict

from content import normalize_media
from metrics import timestamp
from name_indicators import MULTILINGUAL_INDICATORS

# One source of product criteria. Not a quality/originality or audience-share model.
AUTHOR_POLICY = {
    'version': 'creation_80_15_5', 'min_original_posts': 3,
    'weights': {'originals': 80, 'comments': 15, 'shares': 5},
    'normalization': 'maximum_among_eligible_authors',
    'account_requirement': 'person_by_verified_metadata_or_name_heuristic',
    'counter_scope': 'lifetime_for_posts_published_in_period',
}
ORGANIZATION_TYPES = {'organization', 'business', 'institution', 'media', 'nonprofit', 'government', 'brand'}


# Transparent language rules, not identity verification. Place names alone do not classify an account.
# These are extensible contextual indicators, not an exhaustive registry of organizations.
ORGANIZATION_INDICATORS = {
    'media': [r'naujien\w*', r'agent[uū]r\w*', r'kronik\w*', r'\bzinios\b', r'dienrast\w*',
              r'laikrast\w*', r'redakcij\w*', r'televizij\w*', r'radij\w*', r'portal\w*',
              r'\b(?:tv|lrt|lnk|tv3|bns|elta|news|press|media)\b', r'informacijos\s+centras'],
    'business': [r'\b(?:uab|mb|vsi|llc|ltd|inc|corp)\b', r'^ab\s', r'\bimon\w*', r'bendrov\w*',
                 r'\b(?:group|holding|company|corporation)\b', r'prekyb\w*', r'parduotuv\w*',
                 r'bank(?:as|o|ai|u|ams)\b', r'vaistin\w*', r'klinik\w*', r'restoran\w*', r'viesbut\w*'],
    'institution': [r'ministerij\w*', r'savivaldyb\w*', r'seniunij\w*', r'departament\w*',
                    r'inspekcij\w*', r'tarnyb\w*', r'komisij\w*', r'agent[uū]r\w*', r'ambasad\w*',
                    r'konsulat\w*', r'\bseim(?:as|o)\b', r'vyriausyb\w*', r'prezidentur\w*',
                    r'policij\w*', r'kariuomen\w*', r'pajeg\w*', r'prokuratur\w*', r'teism(?:as|o|ai|u)\b'],
    'political_organization': [r'partij\w*', r'frakcij\w*', r'politinis\s+komitetas', r'rinkimu\s+komitetas'],
    'nonprofit': [r'asociacij\w*', r'organizacij\w*', r'fond(?:as|o|ai|u)\b', r'labdar\w*',
                  r'paramos\s+(?:fondas|centras)', r'\b(?:ngo|nvo|nonprofit|foundation|association)\b',
                  r'profesin\w*\s+sajung\w*', r'sajung\w*', r'federacij\w*'],
    'education_health_culture': [r'universitet\w*', r'kolegij\w*', r'mokykl\w*', r'gimnazij\w*',
                                r'licej\w*', r'institut\w*', r'akademij\w*', r'ligonin\w*',
                                r'poliklinik\w*', r'bibliotek\w*', r'muziej\w*', r'teatr\w*',
                                r'kulturos\s+(?:centras|namai)', r'sporto\s+(?:klubas|centras)'],
    'community_religion': [r'bendruomen\w*', r'parapij\w*', r'baznyci\w*', r'vyskupij\w*',
                           r'vienuolyn\w*', r'religin\w*\s+bendrij\w*', r'\bcentras\b', r'\bklubas\b'],
}
for _group, _patterns in MULTILINGUAL_INDICATORS.items():
    ORGANIZATION_INDICATORS.setdefault(_group, []).extend(_patterns)

INDICATOR_PATTERNS = {group: re.compile(r'(?<!\w)(?:'+'|'.join(values)+r')(?!\w)')
                      for group, values in ORGANIZATION_INDICATORS.items()}
DOMAIN = re.compile(r'(?:https?://|www\.)|(?:[a-z0-9-]+\.)+(?:lt|com|org|net|eu|info|tv|biz|edu|gov|io|co)\b', re.I)


def name_type(name):
    if not isinstance(name, str) or not name.strip():
        return 'unknown', 'Paskyros pavadinimas nepateiktas.'
    name = name.strip()
    if re.fullmatch(r'@?[^@\s]+@[^@\s]+', name):
        return 'unknown', 'Pateiktas tik paskyros adresas, o ne profilio pavadinimas.'
    words = ''.join(c for c in unicodedata.normalize('NFKD', name.casefold()) if not unicodedata.combining(c))
    if DOMAIN.search(name):
        return 'organization', 'Profilio pavadinime nurodytas interneto domenas.'
    for group, pattern in INDICATOR_PATTERNS.items():
        if pattern.search(words):
            return 'organization', 'Organizacinis pavadinimo požymis: ' + group + '.'
    if not any(c.isalpha() for c in name) or words in {'admin','administratorius','test','testas','bot','narys'}:
        return 'unknown', 'Iš pavadinimo nepakanka požymių asmeniniam profiliui.'
    if any(c.isalpha() and not any(script in unicodedata.name(c, '') for script in ('LATIN', 'CYRILLIC')) for c in name):
        return 'unknown', 'Šio rašto pavadinimui nepakanka patikimų taisyklių; reikia peržiūros.'
    return 'person', 'Vardas, pavardė arba slapyvardis be organizacinio pavadinimo požymių.'


def account_classification(posts):
    types = set()
    for post in posts:
        classification = post.get('author_classification') or {}
        if (classification.get('verified') is True and classification.get('provenance') in
                ('platform_metadata', 'exercise_administrator')):
            kind = classification.get('type')
            if kind in {'person'} | ORGANIZATION_TYPES:
                types.add(kind)
    if len(types) > 1:
        return {'type':'unknown','method':'conflicting_metadata'}
    if len(types) == 1:
        return {'type':next(iter(types)),'method':'verified_metadata'}
    # Different reported names must agree; never choose a convenient variant.
    guesses = [name_type(p.get('author_name'))[0] for p in posts]
    kind = guesses[0] if guesses and len(set(guesses)) == 1 else 'unknown'
    return {'type':kind,'method':'name_heuristic'}


def content_key(post):
    text = ' '.join(unicodedata.normalize('NFC', post.get('text') or '').split())
    media = sorted(set((m.get('kind'), m.get('originalUrl') or m.get('thumbnailUrl') or '')
                       for m in normalize_media(post.get('media'), is_demo=bool(post.get('is_demo')))))
    if not text and not media:
        return None  # An unavailable/empty body does not demonstrate unique creation.
    body = json.dumps([text, media], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def received(post, key):
    value = (post.get('counters') or {}).get(key)
    if (post.get('counter_scope') != 'lifetime' or not isinstance(value, int) or isinstance(value, bool)
            or value < 0 or key == 'comments' and post.get('comments_include_replies') is not True):
        return None
    if value == 0:
        return 0
    complete = post.get('interaction_completeness', {}).get(key, post.get('interactions_complete') is True)
    if complete is not True:
        return None
    kind = {'comments': 'comment', 'shares': 'share'}[key]
    events = {}
    for action in post.get('interactions') or []:
        if action.get('kind') != kind:
            continue
        identity, actor = action.get('id'), action.get('account_id')
        if not isinstance(identity, (str, int)) or isinstance(identity, bool) or not str(identity) or not isinstance(actor, str) or not actor:
            return None
        identity = str(identity)
        if identity in events and events[identity] != actor:
            return None
        events[identity] = actor
    if len(events) != value:
        return None
    # These are action counts, not unique people, reach, or audience percentages.
    return sum(actor != post['author_id'] for actor in events.values())


def rank_authors(posts, public_content):
    grouped = defaultdict(list)
    unidentified = 0
    for post in posts:
        if post.get('kind') != 'post':
            continue
        if not isinstance(post.get('author_id'), str) or not post['author_id']:
            unidentified += 1
            continue
        grouped[(post['source'], post['author_id'])].append(post)
    eligible, incomplete, unknown, excluded, below_minimum = [], 0, 0, 0, 0
    for (source, author_id), authored in grouped.items():
        classification = account_classification(authored)
        account_type = classification['type']
        if account_type == 'unknown':
            unknown += 1
            continue
        if account_type != 'person':
            excluded += 1
            continue
        selected, seen, missing_content = [], set(), False
        for post in sorted(authored, key=lambda p: (timestamp(p['published_at']), p['id'])):
            key = content_key(post)
            if key is None:
                missing_content = True
                continue
            if key not in seen:
                selected.append(post)
                seen.add(key)
        if missing_content:
            incomplete += 1
            continue
        if len(selected) < AUTHOR_POLICY['min_original_posts']:
            below_minimum += 1
            continue
        comments, shares = [received(p, 'comments') for p in selected], [received(p, 'shares') for p in selected]
        if None in comments or None in shares:
            incomplete += 1
            continue
        eligible.append({'author_id': author_id, 'source': source,
                         'author_name': authored[0].get('author_name') or author_id,
                         'authored_posts': len(authored), 'unique_original_posts': len(selected),
                         'duplicate_posts': len(authored) - len(selected), 'account_classification': classification,
                         'received_comments': sum(comments), 'received_shares': sum(shares),
                         'posts': [public_content(p) for p in sorted(selected, key=lambda p: timestamp(p['published_at']), reverse=True)]})
    fields = {'originals': 'unique_original_posts', 'comments': 'received_comments', 'shares': 'received_shares'}
    maxima = {key: max((a[field] for a in eligible), default=0) for key, field in fields.items()}
    for author in eligible:
        author['score_components'] = {key: AUTHOR_POLICY['weights'][key] * author[field] / maxima[key]
                                      if maxima[key] else 0.0 for key, field in fields.items()}
        author['score'] = sum(author['score_components'].values())
    eligible.sort(key=lambda a: (-a['score'], -a['unique_original_posts'], -a['received_comments'], -a['received_shares'], a['source'], a['author_id']))
    missing = incomplete or unknown or unidentified
    return {'items': eligible[:5], 'policy': AUTHOR_POLICY, 'normalization_maxima': maxima,
            'incomplete_authors': incomplete, 'unknown_account_types': unknown,
            'excluded_organizations': excluded, 'below_minimum_authors': below_minimum,
            'missing_identity_posts': unidentified,
            'status': 'partial' if missing and eligible else 'missing_data' if missing else 'ok' if eligible else 'empty'}
