import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from diaspora_client import DiasporaClient
from private_media import MediaDelivery

WEBP = b'RIFF\x04\x00\x00\x00WEBPtest'


class PrivateMediaTests(unittest.TestCase):
    def test_image_type_is_recognized_from_bytes_and_html_is_rejected(self):
        client = DiasporaClient('https://pod.test', 'test', 'not-a-secret')
        client.opener = Mock()
        client.opener.open.return_value = io.BytesIO(WEBP)
        self.assertEqual(client.image('https://pod.test/provided.webp'), (WEBP, 'image/webp'))
        client.opener.open.return_value = io.BytesIO(b'<html>sign in</html>')
        with self.assertRaises(ValueError):
            client.image('https://pod.test/provided.webp')
        calls = client.opener.open.call_count
        with self.assertRaises(ValueError):
            client.image('https://other.test/provided.webp')
        self.assertEqual(client.opener.open.call_count, calls)

    def test_known_attachment_original_fallback_and_private_memory_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'var').mkdir()
            packet = {'collected_at':'first', 'records':[
                {'id':'p', 'source':'pod.test', 'is_demo':False, 'media':[
                    {'kind':'image', 'thumbnailUrl':'http://pod.test/provided-thumb.webp',
                     'originalUrl':'http://pod.test/provided-original.webp'}]},
                {'id':'c', 'source':'pod.test', 'kind':'comment', 'media':[], 'parent_id':'p'}]}
            path = root/'var/diaspora-latest.json'
            path.write_text(json.dumps(packet))
            client = Mock()
            client.image.side_effect = [ValueError('missing thumbnail'), (WEBP,'image/webp')]
            factory = Mock(return_value=client)
            delivery = MediaDelivery(root, lambda:{'DIASPORA_BASE_URL':'https://pod.test',
                                                  'DIASPORA_USERNAME':'test','DIASPORA_PASSWORD':'test'}, factory)
            self.assertEqual(delivery.image('pod.test','p',0),(WEBP,'image/webp'))
            self.assertEqual(delivery.image('pod.test','p',0),(WEBP,'image/webp'))
            self.assertEqual(client.login.call_count,1)
            self.assertEqual(client.image.call_count,2)
            self.assertEqual(client.image.call_args_list[0].args[0],'https://pod.test/provided-thumb.webp')
            for source, identity, index in [('pod.test','c',0),('pod.test','missing',0),('other.test','p',0),('pod.test','p',-1)]:
                with self.assertRaises(ValueError):delivery.image(source, identity, index)
            packet['records'][0]['media'][0]['thumbnailUrl']='https://other.test/private.webp'
            packet['records'][0]['media'][0]['originalUrl']=None
            path.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):delivery.image('pod.test','p',0)
            self.assertEqual(client.image.call_count,2,'unknown origins must not receive session cookies')
            self.assertEqual(sorted(p.name for p in (root/'var').iterdir()),['diaspora-latest.json'])
