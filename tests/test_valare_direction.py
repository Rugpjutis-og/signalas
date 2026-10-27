import copy
import io
import json
import unittest
from unittest.mock import Mock, patch

import valare_direction as policy
import exercise_rule
import openai_analysis as ai
import thermometer_recheck as retry
from live_data import fingerprint
from thermometer_review import NAME, key
from scenario_supplement import context_digest


class ValareDirectionTests(unittest.TestCase):
    def setUp(self):
        from tests.test_narrative_mapping import MappingTests
        MappingTests.setUp(self)
        self.unit['text'] = 'Netikėkite Valarės respublika. Lietuva yra vientisa šalis.'
        self.original['content_fingerprint'] = fingerprint(self.unit)
        self.guidance = policy.for_unit(self.repo, self.unit, self.context)

    def job(self):
        from tests.test_narrative_mapping import MappingTests
        return MappingTests.job(self)

    def test_exception_requires_clear_consistent_own_position(self):
        result = {'direction': 'stabilizing', 'reason_codes': ['S1'], 'evidence': self.unit['text']}
        self.assertTrue(policy.exception(result, self.guidance, policy.TRIGGERS[1], self.unit))
        for trigger in ('none', 'unclear'):
            self.assertIsNone(policy.exception(result, self.guidance, trigger, self.unit))
        self.assertIsNone(policy.exception({**result, 'direction': 'destabilizing', 'reason_codes': ['D2']},
                                          self.guidance, policy.TRIGGERS[1], self.unit))
        self.assertIsNone(policy.exception({**result, 'evidence': 'Parent author said this'},
                                          self.guidance, policy.TRIGGERS[1], self.unit))
        self.assertIsNone(policy.for_unit(self.repo, {**self.unit, 'source': 'other.test'}, self.context))

    def test_new_exception_overrides_account_d5_but_not_a_manual_result(self):
        value = {'direction': 'stabilizing', 'reason_codes': ['S4'], 'evidence': self.unit['text'],
            'reason': 'Aiškiai palaiko Lietuvos vientisumą separatizmo kontekste.', 'missing_context': '',
            'exercise_rule_trigger': 'not_unrelated_daily_life',
            'valare_stabilizing_trigger': 'territorial_unity_supported'}
        response = {'status': 'completed', 'model': 'gpt-6.1-sol', 'output': [{'type': 'message',
            'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}
        opener = Mock(); opener.open.return_value = io.BytesIO(json.dumps(response).encode())
        vision = {'reviewed_image_refs': [], 'own_image_refs': [], 'missing': []}
        rule = {'id': exercise_rule.CONTENT_RULE_ID, 'category': 'destabilizing', 'reason_code': 'D5'}
        with patch.object(ai, 'prepare_images', return_value=([], vision)), patch('monitoring.record'), \
                patch.object(ai, 'build_opener', return_value=opener), \
                patch('scenario_supplement.for_unit', return_value=[]), \
                patch('exercise_accounts.for_unit', return_value=None), patch('exercise_rule.for_unit', return_value=rule):
            result = ai.analyze(self.unit, self.context, root=self.repo, thermometer_only=True,
                                model_override='gpt-6.1-sol', scoring_rule_review=exercise_rule.CONTENT_RULE_ID)
        self.assertEqual(result['result']['thermometer_category'], 'stabilizing')
        self.assertIsNone(result['exercise_rule_application'])
        self.assertEqual(result['valare_direction_application']['overridden_scoring_rule_id'], exercise_rule.CONTENT_RULE_ID)
        self.assertEqual(result['valare_direction_revision'], policy.REVISION)
        payload = json.loads(opener.open.call_args.args[0].data)
        self.assertNotIn('narrative_analysis', payload['text']['format']['schema']['required'])
        self.assertIn('valare_stabilizing_trigger', payload['text']['format']['schema']['required'])

    def test_historical_target_skips_manual_and_preserves_narratives(self):
        job = self.job()
        target = job['targets'][0]
        target.pop('narrative_mapping_revision')
        target['valare_direction_revision'] = policy.REVISION
        self.db[retry.STATE] = job
        self.original['result'].update(thermometer_status='classified', thermometer_category='destabilizing')
        original_narratives = copy.deepcopy(self.original['result']['narrative_analysis'])
        response = {'result': {'thermometer_status': 'classified', 'thermometer_category': 'stabilizing',
                              'narrative_analysis': {'not_applied': True}}, 'valare_direction_revision': policy.REVISION}
        with patch.object(retry, 'analyze', return_value=response) as paid:
            state = retry.step(self.repo)
        paid.assert_called_once()
        saved = next(v for k, v in self.db.items() if k.startswith('analysis-result/'))
        self.assertEqual(saved['result']['narrative_analysis'], original_narratives)
        self.assertEqual(saved['result']['thermometer_category'], 'stabilizing')
        self.assertIn(policy.REVISION, saved['review_run_id'])
        self.assertEqual(state['classified'], 1)
        self.job(); job['cursor'] = 0; self.db[retry.STATE] = job
        self.db[NAME] = {key(self.unit['source'], self.unit['id']): {'content_fingerprint': fingerprint(self.unit),
            'exercise_id': None, 'exercise_context': self.context, 'rules_version': retry.VERSION, 'category': 'neutral'}}
        with patch.object(retry, 'analyze') as paid:
            state = retry.step(self.repo)
        paid.assert_not_called()
        self.assertEqual(state['skipped'], 1)

    def test_historical_uncertainty_does_not_replace_prior_direction(self):
        job = self.job(); target = job['targets'][0]; target.pop('narrative_mapping_revision')
        target['valare_direction_revision'] = policy.REVISION; self.db[retry.STATE] = job
        response = {'result': {'thermometer_status': 'needs_review', 'thermometer_category': None,
                              'narrative_analysis': {}}}
        with patch.object(retry, 'analyze', return_value=response):
            state = retry.step(self.repo)
        self.assertEqual(state['review_required'], 1)
        self.assertFalse(any(k.startswith('analysis-result/') for k in self.db))

    def test_interleave_preserves_both_existing_and_new_order(self):
        self.assertEqual(policy.interleave(['n1', 'n2', 'n3'], ['d1', 'd2']), ['n1', 'd1', 'n2', 'd2', 'n3'])

    def test_setup_interleaves_once_and_keeps_inflight_target_and_context(self):
        old = self.job()
        old['inflight'] = 'existing-receipt'
        self.db[retry.STATE] = old
        self.db[policy.STATE] = {'status': 'requested', 'revision': policy.REVISION,
            'request_id': 'approved-direction', 'base_context_digest': context_digest(self.context)}
        candidate = {k: old['targets'][0][k] for k in ('source', 'id', 'content_fingerprint', 'exercise_id')}
        candidate.update(previous_category='destabilizing')
        with patch.object(policy, 'candidates', return_value=[candidate]) as select:
            request = policy.maybe_start(self.repo)
            second = policy.maybe_start(self.repo)
        select.assert_called_once()
        self.assertEqual(request, second)
        job = self.db[retry.STATE]
        self.assertEqual(job['inflight'], 'existing-receipt')
        self.assertEqual(job['targets'][0], old['targets'][0])
        self.assertEqual(job['targets'][1]['valare_direction_revision'], policy.REVISION)
        self.assertEqual(job['exercise_context'], self.context)
        self.assertEqual(request['total'], 1)

    def test_setup_excludes_applicable_manual_decision(self):
        self.db[policy.STATE] = {'status': 'requested', 'revision': policy.REVISION,
            'request_id': 'approved-direction', 'base_context_digest': context_digest(self.context)}
        candidate = {'source': self.unit['source'], 'id': self.unit['id'], 'content_fingerprint': fingerprint(self.unit),
                     'exercise_id': None, 'previous_category': 'destabilizing'}
        self.db[NAME] = {key(self.unit['source'], self.unit['id']): {'content_fingerprint': fingerprint(self.unit),
            'exercise_id': None, 'exercise_context': self.context, 'rules_version': retry.VERSION, 'category': 'neutral'}}
        with patch.object(policy, 'candidates', return_value=[candidate]):
            request = policy.maybe_start(self.repo)
        self.assertEqual(request['total'], 0)
        self.assertEqual(request['manual_skips'], 1)

    def test_open_app_services_direction_request_without_local_paid_call(self):
        import cloud_analysis
        self.db[policy.STATE] = {'status': 'requested', 'revision': policy.REVISION}
        with patch('background_tick.tick') as tick, patch('cloud_analysis.step') as paid, \
                patch('cloud_collection.status', return_value={'status': 'idle'}):
            cloud_analysis.drain(self.repo)
        tick.assert_called_once(); paid.assert_not_called()


if __name__ == '__main__':
    unittest.main()
