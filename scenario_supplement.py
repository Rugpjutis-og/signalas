"""One explicitly approved, prospective scenario clarification in Neon.

The original context remains the validity binding for saved AI/manual results.
This clarification never enqueues work or invalidates a previous assessment.
"""
import hashlib
import json

STATE = 'analysis-context-supplement.json'


def context_digest(context):
    return hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def current(repo):
    if not hasattr(repo, 'read'):
        return None
    value = repo.read(STATE)
    if not value or value.get('base_context_digest') != context_digest(repo.read('live-context.json')):
        return None
    return value


def public(repo):
    value = current(repo)
    return [{key: value[key] for key in ('id', 'text', 'effective_at')}] if value else []


def for_unit(repo, unit, context):
    value = current(repo)
    if not value or value['base_context_digest'] != context_digest(context):
        return []
    if not repo.supplement_eligible(unit, value['effective_at']):
        return []
    return [{'id': value['id'], 'text': value['text']}]
