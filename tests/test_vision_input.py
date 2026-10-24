import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from collections import OrderedDict

import vision_input as vision
import openai_analysis as ai
from cloud_repository import Repository, analysis_result_name


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.root = SimpleNamespace(config={'DIASPORA_BASE_URL':'https://pod.test',
            'DIASPORA_USERNAME':'test','DIASPORA_PASSWORD':'private-password','OPENAI_API_KEY':'test'})
        self.unit = {'id':'one','source':'pod.test','kind':'post','text':'',
                     'published_at':'2026-10-24T10:00:00Z','media':[
                         {'kind':'image','originalUrl':'https://pod.test/original.png','thumbnailUrl':'https://pod.test/thumb.png'}]}
        self.client = Mock()
        self.client.image.return_value = (b'\x89PNG\r\n\x1a\nimage', 'image/png')

    def test_private_original_bytes_and_cache_without_public_urls_or_secrets(self):
        with patch.object(vision,'DiasporaClient',return_value=self.client):
            parts, metadata = vision.prepare(self.unit, self.root)
            vision.prepare(self.unit, self.root)
        self.client.login.assert_called_once()
        self.client.image.assert_called_once()
        self.assertEqual(self.client.image.call_args.args[0],'https://pod.test/original.png')
        self.assertTrue(parts[1]['image_url'].startswith('data:image/png;base64,'))
        self.assertEqual(metadata['own_image_refs'], ['one:0'])
        self.assertNotIn('private-password', json.dumps(parts))
        self.assertNotIn('base64', json.dumps(metadata))

    def test_untrusted_origin_and_video_remain_missing_without_fetch(self):
        self.unit['media'] = [{'kind':'image','originalUrl':'https://other.test/p.png'},
                              {'kind':'video','originalUrl':'https://pod.test/p.mp4'}]
        with patch.object(vision,'DiasporaClient') as factory:
            parts, metadata = vision.prepare(self.unit,self.root)
        factory.assert_not_called()
        self.assertFalse(parts)
        self.assertEqual(len(metadata['missing']),2)

    def test_parent_is_context_and_previous_comment_media_does_not_block(self):
        self.unit['parent_post'] = {**self.unit,'id':'parent'}
        self.unit['conversation_context'] = [{'id':'old','media':[{'kind':'video','originalUrl':'https://pod.test/movie.mp4'}]}]
        with patch.object(vision,'DiasporaClient',return_value=self.client):
            _, metadata = vision.prepare(self.unit,self.root)
        self.assertEqual(metadata['reviewed_image_refs'], ['one:0','parent:0'])
        self.assertEqual(metadata['own_image_refs'], ['one:0'])
        self.assertFalse(metadata['missing'])
        self.assertFalse(vision.visual_evidence('VAIZDAS[parent:0] aprašymas',metadata['own_image_refs']))

    def test_limit_and_failure_are_explicit_not_invented_coverage(self):
        self.unit['media'] *= 5
        with patch.object(vision,'DiasporaClient',return_value=self.client):
            _, metadata = vision.prepare(self.unit,self.root)
        self.assertEqual(len(metadata['reviewed_image_refs']),4)
        self.assertEqual(metadata['missing'][0]['reason'],'image_budget')
        self.client.image.side_effect = ValueError('private provider details')
        self.root._vision_cache = OrderedDict()
        with patch.object(vision,'DiasporaClient',return_value=self.client):
            parts, metadata = vision.prepare(self.unit,self.root)
        self.assertFalse(parts)
        self.assertNotIn('private provider',json.dumps(metadata))

    def test_response_contains_visual_evidence_and_only_metadata_is_persisted(self):
        valid = {'narrative_analysis':{'match_status':'no_narrative','matches':[],'proposals':[], 'uncertainty_reason':''},
                 'direction':'stabilizing','reason':'Vaizde pateikti pagalbos kontaktai.',
                 'missing_context':'','evidence':'VAIZDAS[one:0] matomi pagalbos kontaktai','reason_codes':['S2']}
        response={'status':'completed','model':'gpt-6-luna','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(valid)}]}]}
        with patch.object(vision,'DiasporaClient',return_value=self.client), patch.object(ai,'api_key',return_value='test'), patch.object(ai,'build_opener') as opener, patch.object(ai.monitoring,'record'), patch.object(ai,'pending_claims',return_value=[]):
            opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(json.dumps(response).encode())
            result=ai.analyze(self.unit,root=self.root)
        sent=json.loads(opener.return_value.open.call_args.args[0].data)
        self.assertTrue(any(p['type']=='input_image' for p in sent['input'][-1]['content']))
        self.assertEqual(result['result']['thermometer_status'],'classified')
        self.assertEqual(result['result']['thermometer_category'],'stabilizing')
        self.assertEqual(result['vision_revision'],vision.REVISION)
        self.assertNotIn('base64',json.dumps(result))
        self.assertTrue(result['coverage']['images'])

    def test_narrative_visual_evidence_must_reference_own_reviewed_photo(self):
        import narrative_registry as registry
        catalog=registry.load()
        value={'match_status':'matched','matches':[{'type_id':catalog['types'][0]['id'],
            'stance':registry.STANCES[0],'evidence':'VAIZDAS[one:0] aiškus vizualinis teiginys',
            'instance_entities':{k:'' for k in registry.ENTITY_KEYS}}], 'proposals':[],'uncertainty_reason':''}
        self.assertTrue(registry.validate(value,catalog,'',visual_refs=['one:0'])['matches'])
        with self.assertRaises(ValueError): registry.validate(value,catalog,'',visual_refs=['parent:0'])
        with self.assertRaises(ValueError): registry.validate(value,catalog,'')

    def test_visual_revision_has_distinct_idempotent_result_identity(self):
        result={'source_reference':{'source':'pod.test','id':'one'}}
        old=analysis_result_name(result)
        self.assertNotEqual(old,analysis_result_name({**result,'vision_revision':vision.REVISION}))
        self.assertEqual(analysis_result_name({**result,'vision_revision':vision.REVISION}),analysis_result_name({**result,'vision_revision':vision.REVISION}))


if __name__=='__main__': unittest.main()
