"""Shared original-content links. URLs are supplied by the source, never inferred from IDs."""
import re
from urllib.parse import urljoin, urlsplit, urlunsplit


def source_url(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Originalo nuoroda turi būti pilnas HTTP arba HTTPS URL')
    try:
        url = urlsplit(value)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.path in ('', '/'):
            raise ValueError('Reikia konkretaus turinio originalo URL, ne platformos pradžios')
        _ = url.port
    except ValueError:
        raise ValueError('Netinkama konkretaus turinio originalo nuoroda')
    return value


def source_reference(unit):
    return {'id': unit.get('id', unit.get('external_id')), 'source': unit.get('source'),
            'sourceUrl': source_url(unit.get('sourceUrl') or unit.get('original_url') or unit.get('url')),
            'parentSourceUrl': source_url(unit.get('parentSourceUrl')), 'kind': unit.get('kind', 'post')}


def media_url(value, *, source_base_url=None, is_demo=False):
    """Accept only an address supplied by the source, never manufacture an image path."""
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    if is_demo and re.fullmatch(r'demo/[\w.-]+\.(?:svg|png|jpe?g|webp)', value):
        return value
    if source_base_url:
        base = urlsplit(source_base_url)
        if base.scheme not in ('http', 'https') or not base.hostname or base.username or base.password:
            return None
        value = urljoin(source_base_url, value)
        try:
            supplied = urlsplit(value)
            # Upgrade only this configured pod, preserving supplied paths/query.
            if (base.scheme == 'https' and supplied.scheme == 'http' and supplied.hostname == base.hostname
                    and not supplied.username and not supplied.password and supplied.port in (None, 80)):
                value = urlunsplit(('https', base.netloc, supplied.path, supplied.query, supplied.fragment))
        except ValueError:
            return None
    try:
        url = urlsplit(value)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            return None
        _ = url.port
    except ValueError:
        return None
    return value


def normalize_media(items, *, source_base_url=None, is_demo=False):
    """Shared own-attachment schema; no parent/root media is consulted."""
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError('media turi būti medijos elementų sąrašas')
    result = []
    for item in items:
        if not isinstance(item, dict) or item.get('kind', item.get('type')) not in ('image', 'video'):
            continue
        kind = item.get('kind', item.get('type'))
        address = lambda value: media_url(value, source_base_url=source_base_url, is_demo=is_demo)
        result.append({'kind': kind,
                       'thumbnailUrl': address(item.get('thumbnailUrl')),
                       'originalUrl': address(item.get('originalUrl') or item.get('url') or item.get('asset')),
                       'alt': item.get('alt') or item.get('description') or '',
                       **({'caption': item['caption']} if item.get('caption') else {}),
                       **({'posterUrl': address(item.get('posterUrl'))} if kind == 'video' else {})})
    return result


def diaspora_photos(photos, *, source_base_url=None):
    """PhotoPresenter supplies sizes. Use those exact values, not photo GUIDs."""
    items = []
    for photo in photos if isinstance(photos, list) else []:
        if not isinstance(photo, dict):
            continue
        sizes = photo.get('sizes') or {}
        items.append({'kind': 'image', 'thumbnailUrl': sizes.get('medium') or sizes.get('small'),
                      'originalUrl': sizes.get('raw') or sizes.get('large'),
                      'alt': photo.get('alt') or photo.get('description') or ''})
    return normalize_media(items, source_base_url=source_base_url)
