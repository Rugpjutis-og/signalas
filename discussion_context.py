"""Store each source unit once; reconstruct preceding discussion only when needed."""
from collections import defaultdict
from datetime import datetime

PART = ('id', 'published_at', 'text', 'media', 'sourceUrl')
COMMENT_PART = PART + ('parentSourceUrl',)


def identity(unit):
    return unit.get('source'), unit.get('id')


class DiscussionIndex:
    def __init__(self, records):
        self.units = {identity(r): r for r in records}
        self.threads = defaultdict(list)
        for r in self.units.values():
            if r.get('kind') == 'comment' and r.get('parent_id'):
                self.threads[(r['source'], r['parent_id'])].append(r)
        self.positions = {}
        for comments in self.threads.values():
            comments.sort(key=lambda r: datetime.fromisoformat(r['published_at'].replace('Z', '+00:00')))
            for i, r in enumerate(comments):
                self.positions[identity(r)] = i

    def expand(self, unit):
        if 'conversation_context' in unit or 'parent_post' in unit:
            return unit  # Preserve legacy/imported context that is not reconstructible.
        parent_key = (unit.get('source'), unit.get('parent_id'))
        parent = self.units.get(parent_key)
        if unit.get('kind') != 'comment' or not parent:
            return unit
        comments = self.threads[parent_key]
        position = self.positions[identity(unit)]
        return {**unit, 'parent_post': {k: parent.get(k) for k in PART},
                'conversation_context': [{k: c.get(k) for k in COMMENT_PART} for c in comments[:position]]}


def compact_records(records):
    """Only remove embedded context when all referenced units remain available."""
    unique = {identity(r): dict(r) for r in records}
    for r in unique.values():
        parent_key = (r.get('source'), r.get('parent_id'))
        if r.get('kind') == 'comment' and parent_key in unique:
            previous = r.get('conversation_context', [])
            if all((r['source'], c.get('id')) in unique for c in previous):
                r.pop('parent_post', None)
                r.pop('conversation_context', None)
    return list(unique.values())
