import copy
import json
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
        def sql(statement, params=None):
            if 'WITH previous AS' in statement:
                old = self.db.get(params[1], {})
                if old.get('status') == 'complete' and old.get('run_id') == params[3]:
                    self.db['thermometer-recheck-history/'+params[3]] = copy.deepcopy(old)
                    self.db[params[1]] = json.loads(params[2])
            elif 'INSERT INTO signalas_state' in statement:
                self.db.setdefault(params[1], json.loads(params[2]))
            return {'rows': [['owner']]}
        self.repo.sql = Mock(side_effect=sql)
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

    def test_neutral_selection_excludes_manual_and_other_categories_and_archives_previous_job(self):
        self.db[retry.STATE] = dict(self.job(), status='complete', cursor=1, remaining=0)
        units = [{**self.unit, 'assessment': {'status': state, 'category': category, 'method': method}}
                 for state, category, method in [('assessed','neutral','openai_text_pilot'),
                    ('assessed','neutral','manual_review'), ('assessed','stabilizing','openai_text_pilot'),
                    ('needs_review',None,'openai_text_pilot'), ('not_analyzed',None,'not_analyzed')]]
        with patch.object(retry, 'thermometer', return_value={'units':units,'start':'a','end':'b'}), patch.object(
                retry, 'load', return_value=({'records':[self.unit]},None,{})):
            first = retry.start(self.repo, category='neutral', request_id='neutral-audit')
            self.assertEqual(first['total'], 1)
            self.assertEqual(first['selection_category'], 'neutral')
            self.assertEqual(self.db[retry.STATE]['status'], 'category_pending')
            self.assertTrue(retry.active(self.repo))
            self.assertIn('thermometer-recheck-history/one-pass', self.db)
            self.assertEqual(retry.start(self.repo, category='neutral', request_id='neutral-audit')['run_id'], first['run_id'])

    def test_neutral_audit_reassigns_without_replacing_narratives(self):
        self.db[retry.STATE] = dict(self.job(), selection_category='neutral')
        self.original['result'].update(thermometer_status='classified', thermometer_category='neutral')
        response = self.response()
        response['result']['thermometer_category'] = 'destabilizing'
        with patch.object(retry, 'analyze', return_value=response):
            state = retry.step(self.repo)
        self.assertEqual(state['reassigned'], 1)
        self.assertEqual(state['classified'], 1)
        saved_result = next(v for k,v in self.db.items() if k.startswith('analysis-result/'))
        self.assertEqual(saved_result['result']['narrative_analysis'], {'original':True})
        self.assertEqual(saved_result['vision_revision'],retry.VISION_REVISION)

    def test_neutral_audit_alternates_with_normal_analysis(self):
        self.db[retry.STATE] = dict(self.job(), selection_category='neutral', targets=self.job()['targets']*2,
                                   remaining=2, total=2)
        self.original['result'].update(thermometer_status='classified', thermometer_category='neutral')
        primary = {'status':'pending','remaining':20,'completed':0,'updated_at':'before'}
        self.db[cloud_analysis.STATE] = primary
        with patch.object(retry, 'analyze', side_effect=self.response) as sol, patch.object(
                cloud_analysis, '_primary_step', return_value=primary) as luna:
            cloud_analysis.step(self.repo)
            self.assertEqual(sol.call_count, 1)
            cloud_analysis.step(self.repo)
            luna.assert_called_once()
            self.db[cloud_analysis.STATE] = dict(primary,remaining=19,completed=1,updated_at='after')
            cloud_analysis.step(self.repo)
            self.assertEqual(sol.call_count, 2)

    def test_invalid_neutral_reassessment_becomes_review_error_not_a_guessed_direction(self):
        self.db[retry.STATE] = dict(self.job(), selection_category='neutral')
        self.original['result'].update(thermometer_status='classified', thermometer_category='neutral')
        with patch.object(retry, 'analyze', side_effect=ValueError('invalid')):
            self.assertEqual(retry.step(self.repo)['failed'], 1)
        result = next(v for k,v in self.db.items() if k.startswith('analysis-result/'))
        self.assertEqual(result['result']['thermometer_status'], 'error')
        self.assertIsNone(result['result']['thermometer_category'])

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

    def test_review_and_primary_alternate_for_noncategory_review(self):
        self.db[retry.STATE]=self.job()
        self.db[retry.STATE]['targets']*=2
        self.db[retry.STATE]['total']=self.db[retry.STATE]['remaining']=2
        self.db[cloud_analysis.STATE]={'status':'pending','remaining':20,'updated_at':'one'}
        with patch.object(retry,'analyze',side_effect=self.response), patch.object(cloud_analysis,'_primary_step',return_value={'status':'pending','remaining':19}) as primary:
            cloud_analysis.step(self.repo)
            primary.assert_not_called()
            cloud_analysis.step(self.repo)
            primary.assert_called_once()
            self.db[cloud_analysis.STATE].update(remaining=19,updated_at='two')
            cloud_analysis.step(self.repo)
            self.assertEqual(primary.call_count,1)
            self.assertEqual(self.db[retry.STATE]['completed'],2)

    def test_normal_worker_dispatches_finite_review_without_resetting_primary_queue(self):
        self.db[retry.STATE] = self.job()
        self.db[cloud_analysis.STATE] = {'status': 'pending', 'remaining': 20}
        with patch.object(retry, 'analyze', side_effect=self.response):
            self.assertEqual(cloud_analysis.step(self.repo)['status'], 'complete')
        self.assertEqual(self.db[cloud_analysis.STATE], {'status': 'pending', 'remaining': 20})


if __name__ == '__main__':
    unittest.main()
