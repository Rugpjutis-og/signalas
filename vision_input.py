"""Bounded, authorized photo input. Bytes stay in memory, never in Neon/history."""
import base64
import re
import time
from collections import OrderedDict
from urllib.parse import urlsplit
from content import normalize_media
from diaspora_client import DiasporaClient
from integration_config import settings

REVISION = 'photos-2026-10-24.1'
MAX_IMAGES = 4
MAX_BYTES = 12 * 1024 * 1024
FETCH_SECONDS = 35


def has_images(unit):
    return any(m.get('kind') == 'image' for r in (unit, unit.get('parent_post') or {}) for m in r.get('media') or [])


def visual_evidence(value, refs):
    if not isinstance(value, str): return False
    match = re.fullmatch(r'VAIZDAS\[([^\]]+)\]\s+(.{5,2000})', value, re.S)
    return bool(match and match[1] in refs)


def prepare(unit, root):
    """Only the unit's own photos and its parent; earlier comment media is optional context."""
    config = settings(root)
    base = config.get('DIASPORA_BASE_URL', 'https://diaspora.sauliai.lt')
    origin = urlsplit(base)[:2]
    client = getattr(root, '_vision_client', None)
    cache = getattr(root, '_vision_cache', OrderedDict())
    parts, refs, own_refs, missing = [], [], [], []
    used = 0
    deadline = time.monotonic() + FETCH_SECONDS
    for record in (unit, unit.get('parent_post') or {}):
        for index, media in enumerate(normalize_media(record.get('media'), source_base_url=base)):
            ref = str(record.get('id')) + ':' + str(index)
            if media['kind'] != 'image':
                missing.append({'ref': ref, 'reason': 'unsupported_audio_video'})
                continue
            if ref in refs: continue
            if len(refs) >= MAX_IMAGES or time.monotonic() >= deadline:
                missing.append({'ref': ref, 'reason': 'image_budget'})
                continue
            addresses = list(dict.fromkeys(a for a in (media.get('originalUrl'),media.get('thumbnailUrl')) if a))
            addresses = [a for a in addresses if urlsplit(a)[:2] == origin and not urlsplit(a).username and not urlsplit(a).password]
            result = None
            for address in addresses:
                if time.monotonic() >= deadline: break
                try:
                    result = cache.get(address)
                    if result is None:
                        if client is None:
                            client = DiasporaClient(base, config.get('DIASPORA_USERNAME'),config.get('DIASPORA_PASSWORD'))
                            client.login()
                        result = client.image(address, timeout=min(10, max(1, deadline-time.monotonic())))
                        if result[1] == 'image/gif':
                            result = None  # Animation completeness cannot be established here.
                            continue
                        cache[address] = result
                        while sum(len(v[0]) for v in cache.values()) > MAX_BYTES:
                            cache.popitem(last=False)
                    break
                except (ValueError, OSError):
                    result = None
            if not result or used + len(result[0]) > MAX_BYTES:
                missing.append({'ref': ref, 'reason': 'image_unavailable'})
                continue
            used += len(result[0]); refs.append(ref)
            if record is unit: own_refs.append(ref)
            parts.extend([{'type':'input_text','text':'Nuotrauka VAIZDAS['+ref+'] ('+('vertinamas vienetas' if record is unit else 'pirminio įrašo kontekstas')+').'},
                          {'type':'input_image','image_url':'data:'+result[1]+';base64,'+base64.b64encode(result[0]).decode(),'detail':'high'}])
    if hasattr(root,'config'):
        root._vision_client, root._vision_cache = client, cache
    return parts, {'revision':REVISION,'reviewed_image_refs':refs,'own_image_refs':own_refs,'missing':missing}
