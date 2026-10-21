"""Platform-wide content ranking. Offline demo adapter; no live collection or AI."""
import json
import math
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from periods import PERIODS

from content import diaspora_photos, normalize_media, source_reference
from metrics import audience_ids, author_statistics, post_engagement, timestamp

ROOT = Path(__file__).resolve().parent
# Product trial criteria, not statistically validated thresholds. One source for ranking policy.
AUTHOR_POLICY = {'min_active_posts': 3, 'positive_median_required': True, 'activity_weight': 'log2(1 + active_posts)'}
CATEGORIES = [('comments', 'Labiausiai diskutuojami'), ('likes', 'Daugiausia patiktukų'), ('shares', 'Daugiausia dalinamasi')]


def adapt_diaspora_post(raw, *, source, exercise_id, sourceUrl=None, parentSourceUrl=None,
                        visibility=None, visible_account_ids=None, interactions_complete=False, media=None, source_base_url=None):
    """Normalize trusted API JSON without guessing URLs, recipients or completeness.
    Caller supplies source-provided links and authoritative exercise/visibility metadata.
    Raw counters are lifetime totals. Diaspora's post comments collection includes replies.
    Initial HTML's limited interaction arrays must NOT be marked complete.
    """
    author = raw.get('author') or {}
    data = raw.get('interactions') or {}
    interactions = []
    complete = interactions_complete and all(isinstance(data.get(key), list) for key in ('likes', 'comments', 'reshares'))
    for key, kind in [('likes', 'like'), ('comments', 'comment'), ('reshares', 'share')]:
        if data.get(key + '_count') is not None and len(data.get(key) or []) != data[key + '_count']:
            complete = False
        for action in data.get(key) or []:
            actor = action.get('author') or {}
            interactions.append({'id': action.get('guid', action.get('id')), 'kind': kind,
                                 'account_id': actor.get('guid'), 'published_at': action.get('created_at')})
    return {'id': raw.get('guid'), 'source': source, 'exercise_id': exercise_id,
            'kind': 'reshare' if raw.get('post_type') == 'Reshare' else 'post' if raw.get('post_type') == 'StatusMessage' else 'unknown',
            'author_id': author.get('guid'), 'author_name': author.get('name') or author.get('diaspora_id'),
            'published_at': raw.get('created_at'), 'text': raw.get('text', ''), 'is_demo': False,
            'sourceUrl': source_reference({'sourceUrl': sourceUrl or raw.get('sourceUrl') or raw.get('url')})['sourceUrl'],
            'parentSourceUrl': source_reference({'parentSourceUrl': parentSourceUrl or raw.get('parentSourceUrl')})['parentSourceUrl'],
            'visibility': visibility, 'visible_account_ids': visible_account_ids,
            'interactions_complete': complete, 'interactions': interactions,
            'counter_scope': 'lifetime', 'comments_include_replies': True,
            'counters': {'comments': data.get('comments_count'), 'likes': data.get('likes_count'), 'shares': data.get('reshares_count')},
            'media': normalize_media(media, source_base_url=source_base_url) if media is not None else diaspora_photos(raw.get('photos'), source_base_url=source_base_url)}


def adapt_diaspora_comment(raw, *, source, exercise_id, sourceUrl=None, parentSourceUrl=None, media=None, source_base_url=None):
    """Preserve a supplied direct comment URL, otherwise only a known parent URL."""
    author = raw.get('author') or {}
    data = raw.get('interactions') or {}
    likes = data.get('likes')
    return {'id': raw.get('guid'), 'source': source, 'exercise_id': exercise_id, 'kind': 'comment',
            'author_id': author.get('guid'), 'author_name': author.get('name') or author.get('diaspora_id'),
            'published_at': raw.get('created_at'), 'text': raw.get('text', ''), 'is_demo': False,
            'sourceUrl': source_reference({'sourceUrl': sourceUrl or raw.get('sourceUrl') or raw.get('url')})['sourceUrl'],
            'parentSourceUrl': source_reference({'parentSourceUrl': parentSourceUrl or raw.get('parentSourceUrl')})['parentSourceUrl'],
            'media': normalize_media(media, source_base_url=source_base_url) if media is not None else diaspora_photos(raw.get('photos'), source_base_url=source_base_url),
            'counter_scope': 'lifetime', 'counters': {'likes': data.get('likes_count')},
            'interactions': [{'id': action.get('guid', action.get('id')), 'kind': 'like',
                              'account_id': (action.get('author') or {}).get('guid'), 'published_at': action.get('created_at')}
                             for action in likes or []],
            'interactions_complete': isinstance(likes, list) and len(likes) == data.get('likes_count')}


def public_content(post):
    """Keep full original text and references; don't expose membership lists to the UI."""
    return {**{key: post.get(key) for key in ('id', 'source', 'kind', 'author_name', 'published_at', 'text', 'is_demo')},
            'media': normalize_media(post.get('media'), is_demo=bool(post.get('is_demo'))),
            **source_reference(post)}


def scoped_posts(records, start, end, exercise_id):
    unique = {}
    for post in records:
        if post.get('exercise_id') != exercise_id or post.get('kind') not in ('post', 'reshare'):
            continue
        if not isinstance(post.get('id'), str) or not post['id'] or not isinstance(post.get('source'), str) or not post['source']:
            raise ValueError('Trūksta patikimo šaltinio turinio ID arba šaltinio')
        try:
            published_at = timestamp(post.get('published_at'))
        except (AttributeError, TypeError, ValueError):
            raise ValueError('Trūksta tinkamos turinio paskelbimo datos su laiko juosta')
        if start <= published_at < end:
            key = (post['exercise_id'], post['source'], post['id'])
            unique.setdefault(key, post)
    return list(unique.values())


def engagement(post, snapshots):
    matches = [s for s in snapshots if audience_ids(s, post.get('exercise_id'), post.get('published_at')) is not None]
    return post_engagement(post, matches[0] if len(matches) == 1 else None)


def author_ranking(posts, snapshots):
    by_author = defaultdict(list)
    unidentified = 0
    for post in posts:
        if post['kind'] != 'post':
            continue
        if not post.get('author_id'):
            unidentified += 1
            continue
        by_author[post['author_id']].append(post)
    ranked, incomplete = [], 0
    for author_id, authored in by_author.items():
        stats = author_statistics(authored, lambda p: engagement(p, snapshots))
        if stats['median_engagement_percent'] is None:
            incomplete += 1
            continue
        # Include every original post, also those with zero interactions, in the median.
        typical = stats['median_engagement_percent']
        active = stats['active_authored_posts']
        if active < AUTHOR_POLICY['min_active_posts'] or typical <= 0:
            continue
        ranked.append({'author_id': author_id, 'author_name': authored[0].get('author_name') or author_id,
                       'authored_posts': len(authored), 'active_authored_posts': active,
                       'median_engagement_percent': typical, 'score': typical * math.log2(1 + active),
                       'posts': [public_content(p) for p in sorted(authored, key=lambda p: timestamp(p['published_at']), reverse=True)]})
    ranked.sort(key=lambda a: (-a['score'], -a['median_engagement_percent'], -a['active_authored_posts'], a['author_id']))
    missing = incomplete or unidentified
    return {'items': ranked[:5], 'incomplete_authors': incomplete, 'missing_identity_posts': unidentified,
            'status': 'partial' if missing and ranked else 'missing_data' if missing else 'ok' if ranked else 'empty',
            'policy': AUTHOR_POLICY}


def report(records, snapshots, *, exercise_id, start, end, mode):
    selected = scoped_posts(records, start, end, exercise_id)
    categories = []
    for key, label in CATEGORIES:
        known = []
        missing = 0
        for post in selected:
            value = (post.get('counters') or {}).get(key)
            if post.get('counter_scope') != 'lifetime' or not isinstance(value, int) or isinstance(value, bool) or value < 0 or (key == 'comments' and post.get('comments_include_replies') is not True):
                missing += 1
                continue
            if value > 0:
                known.append({**public_content(post), 'count': value})
        known.sort(key=lambda p: (-p['count'], -timestamp(p['published_at']).timestamp(), p['id']))
        categories.append({'id': key, 'label': label, 'items': known[:3], 'missing_posts': missing,
                           'status': 'partial' if missing and known else 'missing_data' if missing else 'ok' if known else 'empty'})
    return {'mode': mode, 'exercise_id': exercise_id, 'start': start.isoformat(), 'end': end.isoformat(),
            'counter_scope': 'lifetime_for_posts_published_in_period',
            'categories': categories, 'authors': author_ranking(selected, snapshots)}


def demo_report(period=7):
    if period not in PERIODS:
        raise ValueError('Laikotarpis turi būti 10, 7, 3 arba 1 diena')
    data = json.loads((ROOT / 'data/platform-demo.json').read_text(encoding='utf-8'))
    end = timestamp(data['end'])
    result = report(data['posts'], data['membership_snapshots'], exercise_id=data['exercise_id'],
                    start=end - timedelta(days=period), end=end, mode='demo')
    return dict(result, period=period)


if __name__ == '__main__':
    for period in PERIODS:
        (ROOT / ('dist/demo/platform-%s.json' % period)).write_text(json.dumps(demo_report(period), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
