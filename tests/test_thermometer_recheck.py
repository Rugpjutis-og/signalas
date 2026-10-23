import copy
import unittest
from unittest.mock import Mock, patch

import cloud_analysis
from cloud_repository import Repository, analysis_result_name
from live_data import fingerprint
from thermometer_review import NAME, key
import thermometer_recheck as retry


class RecheckTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository({'OPENAI_MODEL': 'gpt-6-luna', 'OPENAI_API_KEY': 'test'})
        self.db = {}
        self.unit = {'source': 'test', 'id': '1', 'kind': 'post', 'text': 'Original',
                     'published_at': '2026-10-23T09:00:00Z', 'exercise_id': None}
        self.repo.read = lambda name, default=None: copy.deepcopy(self.db.get(name, default))
        self.repo.write = lambda name, value: self.db.update({name: copy.deepcopy(value)})
        self.repo.latest = lambda: {'records': [self.unit]}
        self.repo.refresh_snapshot = Mock()
        self.repo.sql = Mock(return_value={'rows': [['owner']]})
        self.repo.append_analysis = lambda value: self.db.setdefault(analysis_result_name(value), copy.deepcopy(value))
        self.original = {'source_reference': {'source': 'test', 'id': '1'},
                         'result': {'thermometer_status': 'needs_review', 'narrative_analysis': {'original': True}},
                         'candidate_cluster_ids': ['preserved']}
        self.repo.analysis_for_unit = lambda *args: copy.deepcopy(self.original)
        self.version = retry.registry(self.repo)['version']

    def job(self):
        return {'status': 'pending', 'run_id': 'one-pass', 'processing_model': retry.MODEL,
                'targets': [{'source': 'test', 'id': '1', 'content_fingerprint': fingerprint(self.unit), 'exercise_id': None}],
                'exercise_context': None, 'rules_version': retry.VERSION, 'registry_version': self.version,
                'cursor': 0, 'total': 1, 'remaining': 1, 'completed': 0,
                'classified': 0, 'review_required': 0, 'failed': 0, 'skipped': 0}

    def response(self, *args, **kwargs):
        return {'result': {'thermometer_status': 'classified', 'thermometer_category': 'neutral',
                           'narrative_analysis': {'must_not_replace_original': True}}, 'usage': {'total_tokens': 10}}

    def test_start_freezes_only_eligible_and_is_idempotent(self):
        units = []
        for state in ('needs_review', 'error', 'waiting_data', 'not_analyzed', 'assessed'):
            units.append({**self.unit, 'assessment': {'status': state}})
        report = {'units': units, 'start': 'a', 'end': 'b'}
        with patch.object(retry, 'thermometer', return_value=report), patch.object(retry, 'load',
                           return_value=({'records': [self.unit]}, None, {})):
            first = retry.start(self.repo)
            self.assertEqual(first['total'], 2)
            self.assertNotIn('targets', first)
            self.assertEqual(retry.start(self.repo)['run_id'], first['run_id'])

    def test_sol_only_changes_direction_and_never_mutates_default_or_repeats(self):
        self.db[retry.STATE] = self.job()
        with patch.object(retry, 'analyze', side_effect=self.response) as api:
            result = retry.step(self.repo)
            self.assertEqual((result['status'], result['classified']), ('complete', 1))
            self.assertEqual(api.call_args.kwargs['model_override'], 'gpt-6.1-sol')
            self.assertTrue(api.call_args.kwargs['thermometer_only'])
            self.assertEqual(self.repo.config['OPENAI_MODEL'], 'gpt-6-luna')
            saved = next(v for k, v in self.db.items() if k.startswith('analysis-result/'))
            self.assertEqual(saved['result']['narrative_analysis'], {'original': True})
            self.assertEqual(saved['candidate_cluster_ids'], ['preserved'])
            self.assertEqual(saved['requested_model'], 'gpt-6.1-sol')
            retry.step(self.repo)
            api.assert_called_once()

    def test_manual_decisions_and_edited_units_are_skipped_without_payment(self):
        for manual in (True, False):
            self.db = {retry.STATE: self.job()}
            if manual:
                self.db[NAME] = {key('test', '1'): {'content_fingerprint': fingerprint(self.unit),
                    'exercise_id': None, 'exercise_context': None, 'rules_version': retry.VERSION}}
            else:
                self.unit['text'] = 'Changed'
            with patch.object(retry, 'analyze') as api:
                self.assertEqual(retry.step(self.repo)['skipped'], 1)
                api.assert_not_called()

    def test_item_failure_advances_and_service_failure_stops_without_replay(self):
        for error, expected in [(ValueError(), 'complete'), (retry.AnalysisServiceError('api_quota'), 'error')]:
            self.db = {retry.STATE: self.job()}
            with patch.object(retry, 'analyze', side_effect=error) as api:
                self.assertEqual(retry.step(self.repo)['status'], expected)
                retry.step(self.repo)
                api.assert_called_once()
            self.assertFalse(any(k.startswith('analysis-result/') for k in self.db))

    def test_interrupted_saved_result_is_recovered_without_second_paid_call(self):
        self.db[retry.STATE] = self.job()
        binding = {'source_reference': self.original['source_reference'], 'content_fingerprint': fingerprint(self.unit),
                   'exercise_id': None, 'exercise_context': None, 'registry_version': self.version,
                   'thermometer_rules_version': retry.VERSION, 'requested_model': retry.MODEL, 'review_run_id': 'one-pass'}
        identity = analysis_result_name(binding)
        self.db[retry.STATE].update(status='running', inflight=identity)
        self.db[identity] = self.response()
        with patch.object(retry, 'analyze') as api:
            self.assertEqual(retry.step(self.repo)['classified'], 1)
            api.assert_not_called()

    def test_normal_worker_dispatches_finite_review_without_resetting_primary_queue(self):
        self.db[retry.STATE] = self.job()
        self.db[cloud_analysis.STATE] = {'status': 'pending', 'remaining': 20}
        with patch.object(retry, 'analyze', side_effect=self.response):
            self.assertEqual(cloud_analysis.step(self.repo)['status'], 'complete')
        self.assertEqual(self.db[cloud_analysis.STATE], {'status': 'pending', 'remaining': 20})


if __name__ == '__main__':
    unittest.main()
