import copy
import io
import json
import unittest
from unittest.mock import Mock, patch

import narrative_mapping as mapping
import narrative_registry as registry
import thermometer_recheck as retry
from cloud_repository import Repository, analysis_result_name
from live_data import fingerprint
from scenario_supplement import context_digest
from thermometer_review import NAME, key


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.context = {'initialSituation': 'Pratybos', 'confirmedFacts': 'Fiktyvi situacija', 'nameMappings': []}
        self.db = {'live-context.json': self.context, 'analysis-context-supplement.json': {
            'id': mapping.SUPPLEMENT, 'base_context_digest': context_digest(self.context),
            'text': 'Fiktyvus separatistinis darinys.'}}
        self.repo = Repository({'OPENAI_API_KEY': 'test', 'OPENAI_MODEL': 'gpt-6-luna'})
        self.repo.read = lambda name, default=None: copy.deepcopy(self.db.get(name, default))
        self.repo.write = lambda name, value: self.db.update({name: copy.deepcopy(value)})
        self.repo.sql = Mock(return_value={'rows': [['owner']]})
        self.repo.refresh_snapshot = Mock()
        self.unit = {'source': mapping.SOURCE, 'id': 'one', 'kind': 'post', 'text': 'Remiu Valarės šaulius.',
            'published_at': '2026-10-24T09:00:00Z', 'exercise_id': None, 'media': []}
        self.repo.latest = lambda: {'records': [self.unit]}
        self.catalog = registry.load(self.repo)
        self.value = {'match_status': 'matched', 'matches': [{'type_id': 'N031', 'stance': 'support',
            'evidence': self.unit['text'], 'instance_entities': {k: '' for k in registry.ENTITY_KEYS}}],
            'proposals': [], 'uncertainty_reason': ''}
        self.original = {'source_reference': {'source': mapping.SOURCE, 'id': 'one'},
            'content_fingerprint': fingerprint(self.unit), 'exercise_id': None, 'exercise_context': self.context,
            'registry_version': self.catalog['version'], 'thermometer_rules_version': retry.VERSION,
            'model': 'gpt-6-luna', 'requested_model': 'gpt-6-luna', 'analysis_executed': True,
            'usage': {'total_tokens': 19}, 'coverage': {'text': True}, 'exercise_rule_application': {'kept': True},
            'result': {'thermometer_status': 'classified', 'thermometer_category': 'neutral',
                'direction': 'neutral', 'reason_codes': ['N1'], 'reason': 'Old reason', 'evidence': 'Old evidence',
                'narrative_analysis': {'match_status': 'no_narrative', 'matches': [], 'proposals': [], 'uncertainty_reason': ''}}}
        self.repo.analysis_for_unit = lambda *args: copy.deepcopy(self.original)
        self.repo.append_analysis = lambda result: self.db.setdefault(analysis_result_name(result), copy.deepcopy(result))

    def job(self):
        state = {'status': 'pending', 'kind': 'thermometer_recheck', 'run_id': 'narrative-test',
            'targets': [{'source': self.unit['source'], 'id': 'one', 'content_fingerprint': fingerprint(self.unit),
                         'exercise_id': None, 'narrative_mapping_revision': mapping.REVISION}],
            'exercise_context': self.context, 'registry_version': self.catalog['version'],
            'rules_version': retry.VERSION, 'cursor': 0, 'total': 1, 'remaining': 1, 'completed': 0}
        self.db[retry.STATE] = state
        return state

    def response(self):
        return {'narrative_analysis': copy.deepcopy(self.value), 'reviewed_image_refs': [],
            'image_review': {'missing': []}, 'model': retry.MODEL, 'usage': {'total_tokens': 10}}

    def test_aliases_nominate_without_classifying(self):
        for alias in mapping.ALIASES + ['VALARE', 'VALARES RESPUBLIKA']:
            self.assertTrue(mapping.mentions({'text': alias}))
        self.assertFalse(mapping.mentions({'text': 'avalare kitavalarė'}))
        self.assertTrue(mapping.mentions({'text': 'Neremiu Valare respublikos'}))
        # Nomination returns a boolean, never a support/category assignment.

    def test_bound_to_source_and_approved_initial_context(self):
        self.assertTrue(mapping.for_unit(self.repo, self.unit, self.context))
        self.assertIsNone(mapping.for_unit(self.repo, {**self.unit, 'source': 'other.test'}, self.context))
        self.assertIsNone(mapping.for_unit(self.repo, self.unit, {**self.context, 'confirmedFacts': 'Kita'}))
        self.db['analysis-context-supplement.json']['id'] = 'other'
        self.assertIsNone(mapping.for_unit(self.repo, self.unit, self.context))

    def test_narrative_only_payload_has_no_direction_or_roles_and_checks_own_evidence(self):
        response = {'status': 'completed', 'model': retry.MODEL, 'output': [{'type': 'message',
            'content': [{'type': 'output_text', 'text': json.dumps(self.value)}]}]}
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(response).encode())
        vision = {'reviewed_image_refs': [], 'own_image_refs': [], 'missing': []}
        with patch('vision_input.prepare', return_value=([], vision)), patch('monitoring.record'), \
                patch.object(mapping, 'build_opener', return_value=opener):
            value = mapping.analyze_narratives(self.repo, self.unit, self.context, timeout=180, model=retry.MODEL)
        self.assertEqual(value['narrative_analysis'], self.value)
        payload = json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(payload['model'], retry.MODEL)
        self.assertEqual(payload['reasoning']['effort'], 'medium')
        self.assertEqual(payload['text']['format']['schema'], mapping.review_schema(self.catalog))
        self.assertNotIn('direction', payload['text']['format']['schema']['properties'])
        self.assertNotIn('exercise_actor_context', json.dumps(payload))
        self.assertIn('Vien pavadinimas', payload['instructions'])
        self.assertIn('N031', payload['instructions'])

    def test_success_preserves_every_thermometer_field_and_manual_record(self):
        self.job()
        manual = {'content_fingerprint': fingerprint(self.unit), 'exercise_id': None,
            'exercise_context': self.context, 'rules_version': retry.VERSION, 'category': 'stabilizing'}
        self.db[NAME] = {key(self.unit['source'], 'one'): manual}
        with patch.object(mapping, 'analyze_narratives', return_value=self.response()) as paid:
            state = retry.step(self.repo)
        paid.assert_called_once()
        self.assertEqual(state['narrative_updated'], 1)
        self.assertEqual(self.db[NAME], {key(self.unit['source'], 'one'): manual})
        saved = next(v for k, v in self.db.items() if k.startswith('analysis-result/'))
        before = {k: v for k, v in self.original['result'].items() if k != 'narrative_analysis'}
        self.assertEqual({k: v for k, v in saved['result'].items() if k != 'narrative_analysis'}, before)
        self.assertEqual(saved['result']['narrative_analysis'], self.value)
        for field in ('model', 'requested_model', 'usage', 'coverage', 'exercise_rule_application'):
            self.assertEqual(saved[field], self.original[field])
        self.assertEqual(saved['narrative_review']['model'], retry.MODEL)
        self.assertNotEqual(analysis_result_name(saved), analysis_result_name(self.original))

    def test_normal_analysis_receives_mapping_without_changing_primary_model(self):
        import openai_analysis as ai
        value = {'narrative_analysis': self.value, 'direction': 'neutral', 'reason': 'Nuomonė.',
                 'reason_codes': ['N1'], 'missing_context': '', 'evidence': self.unit['text']}
        response = {'status': 'completed', 'model': 'gpt-6-luna', 'output': [{'type': 'message',
            'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}
        opener = Mock(); opener.open.return_value = io.BytesIO(json.dumps(response).encode())
        vision = {'reviewed_image_refs': [], 'own_image_refs': [], 'missing': []}
        with patch.object(ai, 'prepare_images', return_value=([], vision)), patch('monitoring.record'), \
                patch.object(ai, 'build_opener', return_value=opener), patch.object(ai, 'pending_claims', return_value=[]), \
                patch('scenario_supplement.for_unit', return_value=[]), \
                patch('exercise_accounts.for_unit', return_value=None), patch('exercise_rule.for_unit', return_value=None):
            result = ai.analyze(self.unit, self.context, root=self.repo)
        payload = json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(payload['model'], 'gpt-6-luna')
        self.assertEqual(result['narrative_mapping_revision'], mapping.REVISION)
        self.assertEqual(result['result']['thermometer_category'], 'neutral')
        dynamic = json.loads(payload['input'][-1]['content'][0]['text'])
        self.assertEqual(dynamic['analysis_input']['narrative_scenario_mapping']['type_id'], 'N031')

    def test_source_evidence_restores_only_whitespace_and_optional_wrapper(self):
        text = 'Remiu\u00a0Valarės\r\nšaulius.'
        self.assertEqual(mapping.source_excerpt('„Remiu Valarės\nšaulius.“', text), text)
        self.assertEqual(mapping.source_excerpt('Remiu kitus šaulius.', text), 'Remiu kitus šaulius.')
        self.assertEqual(mapping.source_excerpt('I support Valare.', text), 'I support Valare.')

    def test_targeted_review_retains_other_independent_narratives(self):
        self.unit['text'] += ' Kitas savarankiškas teiginys.'
        self.original['result']['narrative_analysis'] = {'match_status': 'matched', 'matches': [{
            'type_id': 'N007', 'stance': 'quote', 'evidence': 'Kitas savarankiškas teiginys.',
            'instance_entities': {k: '' for k in registry.ENTITY_KEYS}}], 'proposals': [], 'uncertainty_reason': ''}
        previous = copy.deepcopy(self.original['result']['narrative_analysis']['matches'][0])
        self.job()
        with patch.object(mapping, 'analyze_narratives', return_value=self.response()):
            state = retry.step(self.repo)
        self.assertEqual(state['narrative_updated'], 1)
        saved = next(v for k, v in self.db.items() if k.startswith('analysis-result/'))
        self.assertEqual(saved['result']['narrative_analysis']['matches'][0], previous)
        self.assertEqual(saved['result']['narrative_analysis']['matches'][1]['type_id'], 'N031')

    def test_narrative_response_rejects_invented_evidence_and_defers_unread_media(self):
        for missing in (False, True):
            value = copy.deepcopy(self.value)
            if not missing:
                value['matches'][0]['evidence'] = 'Not in original'
            response = {'status': 'completed', 'output': [{'type': 'message',
                'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}
            opener = Mock(); opener.open.return_value = io.BytesIO(json.dumps(response).encode())
            vision = {'reviewed_image_refs': [], 'own_image_refs': [], 'missing': [{'reason': 'unavailable'}] if missing else []}
            with patch('vision_input.prepare', return_value=([], vision)), patch('monitoring.record'), \
                    patch.object(mapping, 'build_opener', return_value=opener):
                if missing:
                    result = mapping.analyze_narratives(self.repo, self.unit, self.context, timeout=180, model=retry.MODEL)
                    self.assertEqual(result['narrative_analysis']['match_status'], 'uncertain')
                else:
                    with self.assertRaises(ValueError):
                        mapping.analyze_narratives(self.repo, self.unit, self.context, timeout=180, model=retry.MODEL)

    def test_uncertain_or_error_keeps_previous_narrative(self):
        for uncertain in (True, False):
            self.job()
            response = self.response()
            response['narrative_analysis'] = {'match_status': 'uncertain', 'matches': [], 'proposals': [],
                                             'uncertainty_reason': 'Neaiški ironija'}
            with patch.object(mapping, 'analyze_narratives', **({'return_value': response} if uncertain else
                    {'side_effect': ValueError('invalid json')})):
                state = retry.step(self.repo)
            self.assertFalse(any(k.startswith('analysis-result/') for k in self.db))
            self.assertEqual(state['review_required' if uncertain else 'failed'], 1)

    def test_interrupted_receipt_is_recovered_without_another_paid_call(self):
        state = self.job()
        state['inflight'] = 'narrative-recheck-result/test'
        self.db[retry.STATE] = state
        self.db[state['inflight']] = {'narrative_review_outcome': 'narrative_updated'}
        with patch.object(mapping, 'analyze_narratives') as paid:
            outcome = retry.step(self.repo)
        paid.assert_not_called()
        self.assertEqual(outcome['narrative_updated'], 1)

    def test_changed_content_is_skipped_and_never_repaid(self):
        self.job()
        self.unit['text'] += ' changed'
        with patch.object(mapping, 'analyze_narratives') as paid:
            state = retry.step(self.repo)
        paid.assert_not_called()
        self.assertEqual(state['skipped'], 1)

    def test_request_waits_for_existing_work_and_repeated_start_is_idempotent(self):
        self.db[mapping.STATE] = {'status': 'requested', 'revision': mapping.REVISION,
            'request_id': 'approved-valare', 'base_context_digest': context_digest(self.context)}
        old = self.job()
        with patch.object(mapping, 'candidates') as select:
            mapping.maybe_start(self.repo)
        select.assert_not_called()
        self.assertEqual(self.db[retry.STATE], old)
        old['status'] = 'complete'; self.db[retry.STATE] = old
        with patch.object(mapping, 'candidates', return_value=old['targets']) as select:
            request = mapping.maybe_start(self.repo)
            second = mapping.maybe_start(self.repo)
        select.assert_called_once()
        self.assertEqual(request, second)
        self.assertEqual(request['total'], 1)
        self.assertEqual(self.db[retry.STATE]['purpose'], 'narrative_only')

    def test_open_app_services_pending_request_before_starting_another_primary_batch(self):
        import cloud_analysis
        self.db[mapping.STATE] = {'status': 'requested', 'revision': mapping.REVISION}
        with patch('background_tick.tick') as tick, patch('cloud_analysis.step') as paid_step, \
                patch('cloud_collection.status', return_value={'status': 'idle'}):
            cloud_analysis.drain(self.repo)
        tick.assert_called_once()
        paid_step.assert_not_called()


if __name__ == '__main__':
    unittest.main()
