"""Audience-aware content metrics. Input records must belong to one exercise.
No audience is inferred from activity, global registrations or demonstration counts.
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent


def metrics_context():
    return json.loads((ROOT / 'dist/metrics-context.json').read_text(encoding='utf-8'))


def timestamp(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('A timezone is required')
    return date


def audience_ids(snapshot, exercise_id, published_at=None):
    """Complete assigned membership snapshot, including inactive accounts."""
    if not isinstance(exercise_id, str) or not exercise_id or not isinstance(snapshot, dict) or snapshot.get('exercise_id') != exercise_id or snapshot.get('complete') is not True:
        return None
    ids = snapshot.get('assigned_account_ids')
    if not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids):
        return None
    if published_at is not None:
        # An undated membership snapshot cannot establish historical audience.
        if not snapshot.get('valid_from') or not snapshot.get('valid_until'):
            return None
        try:
            covered = timestamp(snapshot['valid_from']) <= timestamp(published_at) < timestamp(snapshot['valid_until'])
        except (AttributeError, TypeError, ValueError):
            return None
        if not covered:
            return None
    return set(ids)


def share(engaged_ids, eligible_ids):
    if eligible_ids is None or engaged_ids is None:
        return {'status': 'missing_data', 'audience': None if eligible_ids is None else len(eligible_ids),
                'unique_engaged': None, 'percent': None}
    eligible = set(eligible_ids)
    engaged = set(engaged_ids) & eligible
    return {'status': 'ok' if eligible else 'zero_audience', 'audience': len(eligible),
            'unique_engaged': len(engaged), 'percent': len(engaged) / len(eligible) * 100 if eligible else None}


def visible_audience(post, snapshot):
    if not post.get('published_at'):
        return None
    eligible = audience_ids(snapshot, post.get('exercise_id'), post.get('published_at'))
    if eligible is None:
        return None
    visibility = post.get('visibility')
    if visibility == 'all_assigned':
        return eligible
    if visibility == 'restricted' and isinstance(post.get('visible_account_ids'), list) and all(isinstance(i, str) and i for i in post['visible_account_ids']):
        return eligible & set(post['visible_account_ids'])
    return None


def engagement_sets(post, snapshot):
    eligible = visible_audience(post, snapshot)
    author = post.get('author_id')
    interactions = post.get('interactions')
    if eligible is None or not isinstance(author, str) or not author:
        return None, None
    eligible.discard(author)
    if post.get('interactions_complete') is not True or not isinstance(interactions, list) or any(not isinstance(a, dict) or not isinstance(a.get('account_id'), str) or not a['account_id'] or a.get('kind') not in ('like', 'comment', 'share') for a in interactions):
        return eligible, None
    engaged = {a['account_id'] for a in interactions if a.get('kind') in ('like', 'comment', 'share')}
    return eligible, (engaged - {author}) & eligible


def post_engagement(post, snapshot):
    eligible, engaged = engagement_sets(post, snapshot)
    return share(engaged, eligible)


def aggregate_engagement(posts, snapshot):
    """Union across all included posts, for one narrative or author. Never sum uniques."""
    if not posts:
        return share(None, None)
    eligible_union, engaged_union = set(), set()
    for post in posts:
        eligible, engaged = engagement_sets(post, snapshot)
        if eligible is None or engaged is None:
            return share(None, None)
        eligible_union.update(eligible)
        engaged_union.update(engaged)
    return share(engaged_union, eligible_union)


def content_activity(posts, snapshot, exercise_id):
    """Absolute distinct published posts/comments, not counts of people."""
    units = {}
    for post in posts:
        if post.get('exercise_id') != exercise_id or post.get('kind', 'post') not in ('post', 'comment'):
            continue
        key = (post['exercise_id'], post['source'], post.get('kind', 'post'), post['id'])
        units.setdefault(key, post)
    counts = Counter(p.get('kind', 'post') for p in units.values())
    members = audience_ids(snapshot, exercise_id)
    per100 = None
    covered = all(p.get('published_at') and audience_ids(snapshot, exercise_id, p['published_at']) is not None for p in units.values())
    if members and covered:
        # Mixed historical membership periods cannot use a new snapshot's count.
        per100 = len(units) / len(members) * 100
    return {'posts': counts['post'], 'comments': counts['comment'], 'total_content': len(units),
            'content_units_per_100_members': per100,
            'audience_status': 'missing' if members is None or not covered else 'known' if members else 'zero'}


def interaction_counts(posts, exercise_id):
    """Keep absolute comments/likes/shares separate from unique account engagement.
    Each action needs a source-scoped ID; incomplete data must not become zero.
    """
    actions = {}
    for post in posts:
        if post.get('exercise_id') != exercise_id:
            continue
        if not isinstance(exercise_id, str) or not exercise_id or not post.get('source'):
            return {'status': 'missing_data', 'comments': None, 'likes': None, 'shares': None}
        interactions = post.get('interactions')
        if post.get('interactions_complete') is not True or not isinstance(interactions, list):
            return {'status': 'missing_data', 'comments': None, 'likes': None, 'shares': None}
        for action in interactions:
            if not isinstance(action, dict) or action.get('kind') not in ('like', 'comment', 'share') or not action.get('id'):
                return {'status': 'missing_data', 'comments': None, 'likes': None, 'shares': None}
            key = (post.get('exercise_id'), post.get('source'), action['kind'], action['id'])
            actions.setdefault(key, action)
    counts = Counter(a['kind'] for a in actions.values())
    return {'status': 'ok', 'comments': counts['comment'], 'likes': counts['like'], 'shares': counts['share']}


def author_statistics(authored_posts, resolve_engagement):
    """All period originals, including zero-engagement originals, enter the median."""
    selected_by_id = {(p['exercise_id'], p['source'], p['id']): p for p in authored_posts
                      if p.get('kind', 'post') == 'post'}
    selected = list(selected_by_id.values())
    results = [resolve_engagement(p) for p in selected]
    complete = bool(results) and all(r['percent'] is not None for r in results)
    return {'authored_posts': len(selected),
            'active_authored_posts': sum(r['unique_engaged'] > 0 for r in results) if complete else None,
            'posts_with_audience': sum(r['percent'] is not None for r in results),
            'median_engagement_percent': median(r['percent'] for r in results) if complete else None}


def author_median(authored_posts, snapshot, author_id):
    """Compatibility entry point; caller selects the period, never drops unengaged posts."""
    return author_statistics([p for p in authored_posts if p.get('author_id') == author_id],
                             lambda p: post_engagement(p, snapshot))
