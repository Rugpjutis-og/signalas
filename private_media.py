"""Header-protected loopback delivery of known, authorized source photos.

No arbitrary URL parameter, disk cache, public media route or cross-pod cookie
forwarding. Cached bytes and the source session exist only in process memory.
"""
import json
import threading
from collections import OrderedDict
from urllib.parse import urlsplit

from content import normalize_media
from diaspora_client import DiasporaClient
from integration_config import ROOT, settings


class MediaDelivery:
    def __init__(self, root=ROOT, config=settings, client_factory=DiasporaClient):
        self.root, self.config, self.client_factory = root, config, client_factory
        self.lock = threading.Lock()
        self.client, self.generation = None, None
        self.cache = OrderedDict()
        self.cache_size = 0

    def image(self, source, identity, index):
        packet = json.loads((self.root / 'var/diaspora-latest.json').read_text(encoding='utf-8'))
        config = self.config()
        base = config.get('DIASPORA_BASE_URL', 'https://diaspora.sauliai.lt')
        if source != urlsplit(base).hostname or not isinstance(index, int) or index < 0:
            raise ValueError('Nuotraukos šaltinis neatpažintas.')
        record = next((r for r in packet['records'] if r.get('source') == source and r.get('id') == identity
                       and not r.get('is_demo')), None)
        media = normalize_media(record.get('media'), source_base_url=base) if record else []
        if index >= len(media) or media[index]['kind'] != 'image':
            raise ValueError('Šis turinio vienetas neturi nurodytos nuotraukos.')
        addresses = list(dict.fromkeys(m for m in (media[index]['thumbnailUrl'], media[index]['originalUrl']) if m))
        # Only a source-provided URL on this configured origin can be fetched.
        addresses = [a for a in addresses if urlsplit(a)[:2] == urlsplit(base)[:2]]
        if not addresses:
            raise ValueError('Nuotraukai nėra leistino platformos adreso.')
        generation = (packet['collected_at'], base, config.get('DIASPORA_USERNAME'), config.get('DIASPORA_PASSWORD'))
        key = (source, identity, index, tuple(addresses))
        with self.lock:
            if generation != self.generation:
                self.client, self.generation = None, generation
                self.cache.clear()
                self.cache_size = 0
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            if self.client is None:
                self.client = self.client_factory(base, config.get('DIASPORA_USERNAME'), config.get('DIASPORA_PASSWORD'))
                try:
                    self.client.login()
                except ValueError:
                    self.client = None
                    raise
            for address in addresses:
                try:
                    result = self.client.image(address)
                    break
                except ValueError:
                    result = None
            if result is None:
                raise ValueError('Nuotraukos nepavyko įkelti; tekstas ir įrašo nuoroda išlieka.')
            self.cache[key] = result
            self.cache_size += len(result[0])
            while self.cache_size > 16 * 1024 * 1024:
                _, previous = self.cache.popitem(last=False)
                self.cache_size -= len(previous[0])
            return result


delivery = MediaDelivery()
