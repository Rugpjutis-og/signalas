import copy
import unittest
from unittest.mock import Mock, patch
from cloud_repository import Repository
import cloud_analysis as ca
import monitoring
from integration_config import settings


class CloudAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.repo=Repository({'OPENAI_MODEL':'test-model', 'OPENAI_API_KEY':'test-key'})
        self.db={}
        self.units=[{'source':'test', 'id':'1','kind':'post','text':'Original',
                     'published_at':'2026-10-23T09:00:00Z','exercise_id':'A'}]
        self.repo.read=lambda k,default=None: copy.deepcopy(self.db.get(k,default))
        self.repo.write=lambda k,v:self.db.update({k:copy.deepcopy(v)})
        self.repo.latest=lambda:{'records':self.units}
        self.repo.sql=Mock(return_value={'rows':[['owner']]})
        self.repo.analysis_for_queue = self.queue_results
        self.repo.append_analysis = lambda result: self.db.setdefault(ca.RESULTS, []).append(copy.deepcopy(result))
        self.repo.refresh_snapshot = Mock()
        self.repo.collection_progress=lambda: copy.deepcopy(self.db.get('collection-job.json',{}))
        self.version=ca.registry(self.repo)['version']

    def queue_results(self, context, version, model):
        return [copy.deepcopy(a) for a in self.db.get(ca.RESULTS, [])
                if (a.get('analysis_executed') or a.get('processing_disposition') == 'needs_review')
                and a.get('registry_version') == version and a.get('thermometer_rules_version') == ca.VERSION
                and a.get('exercise_context') == context and a.get('requested_model', a.get('model')) == model]

    def result(self,unit,*args,**kwargs):
        return {'analysis_executed':True,'source_reference':{'source':unit['source'],'id':unit['id']},
                'registry_version':self.version,'thermometer_rules_version':ca.VERSION,
                'exercise_id':unit.get('exercise_id'),'exercise_context':None,'model':'test-model'}

    def test_prospective_supplement_does_not_requeue_completed_content(self):
        import scenario_supplement
        old = dict(self.result(self.units[0]), content_fingerprint=ca.fingerprint(self.units[0]))
        self.db[ca.RESULTS] = [old]
        self.assertEqual(ca.pending(self.repo)[0], [])
        self.db[scenario_supplement.STATE] = {'id': 'test', 'text': 'Additional scenario fact',
            'base_context_digest': scenario_supplement.context_digest(None),
            'effective_at': '2026-10-24T12:00:00Z'}
        self.assertEqual(ca.pending(self.repo)[0], [])
        self.assertEqual(self.db[ca.RESULTS], [old])
        self.units.append({**self.units[0], 'id': 'new'})
        self.assertEqual([u['id'] for u in ca.pending(self.repo)[0]], ['new'])

    def test_photo_waiting_data_requeues_once_and_manual_decisions_are_excluded(self):
        from vision_input import REVISION
        from thermometer_review import key
        self.units[0]['media']=[{'kind':'image','originalUrl':'https://pod.test/photo.png'}]
        old=dict(self.result(self.units[0]),content_fingerprint=ca.fingerprint(self.units[0]),
                 thermometer_status='waiting_data')
        self.db[ca.RESULTS]=[old]
        self.assertEqual(len(ca.pending(self.repo)[0]),1)
        old['vision_revision']=REVISION
        self.assertEqual(len(ca.pending(self.repo)[0]),0)
        old.pop('vision_revision')
        self.db['thermometer-reviews.json']={key('test','1'):{
            'content_fingerprint':ca.fingerprint(self.units[0]),'exercise_id':'A',
            'exercise_context':None,'rules_version':ca.VERSION}}
        self.assertEqual(len(ca.pending(self.repo)[0]),0)

    def test_resume_skip_versions_context_and_counters(self):
        self.assertEqual(settings(self.repo)['OPENAI_API_KEY'],'test-key')
        ca.enqueue(self.repo)
        with patch.object(ca,'analyze',side_effect=self.result) as api:
            self.assertEqual(ca.step(self.repo)['status'],'complete')
            self.assertEqual(ca.enqueue(self.repo)['remaining'],0)
            ca.step(self.repo);api.assert_called_once()
            self.units[0]['likes']=100
            self.assertEqual(ca.enqueue(self.repo)['remaining'],0)
            self.units[0]['text']='Edited'
            self.assertEqual(ca.enqueue(self.repo)['remaining'],1)
            ca.step(self.repo)
            self.assertEqual(len(self.db[ca.RESULTS]),2)
            self.units[0]['exercise_id']='B'
            self.assertEqual(ca.enqueue(self.repo)['remaining'],1)
            ca.step(self.repo)
            self.db['live-context.json']={'initialSituation':'Situation','confirmedFacts':'Facts'}
            self.assertEqual(ca.enqueue(self.repo)['remaining'],1)

    def test_queue_one_unit_no_duplicate_calls_and_lease(self):
        self.units += [dict(self.units[0],id='2'),dict(self.units[0])]
        self.assertEqual(ca.enqueue(self.repo)['remaining'],2)
        self.repo.sql.return_value={'rows':[]}
        with patch.object(ca,'analyze',side_effect=self.result) as api:
            self.assertEqual(ca.step(self.repo)['status'],'already_running');api.assert_not_called()
            self.repo.sql.return_value={'rows':[['owner']]}
            self.assertEqual(ca.step(self.repo)['remaining'],1);api.assert_called_once()
            self.assertIn('DELETE',self.repo.sql.call_args.args[0])
            self.assertEqual(ca.step(self.repo)['status'],'complete')

    def test_failure_stops_no_retry_retains_results_and_quota(self):
        self.db[ca.RESULTS]=[{'old':'preserved'}]
        ca.enqueue(self.repo)
        monitoring.record('openai','api_quota',self.repo)
        with patch.object(ca,'analyze',side_effect=ca.AnalysisServiceError('api_quota')) as api:
            state=ca.step(self.repo)
            self.assertEqual(state['status'],'error');self.assertEqual(state['reason'],'api_quota')
            self.assertNotIn('secret',str(state));self.assertEqual(self.db[ca.RESULTS],[{'old':'preserved'}])
            ca.step(self.repo);api.assert_called_once()
            self.assertIn('DELETE',self.repo.sql.call_args.args[0])
        self.repo.collected_at=lambda:'2026-10-23T09:00:00Z'
        self.assertEqual(self.repo.monitoring_status()['reason'],'api_quota')

    def test_missing_provider_key_stops_without_paid_call(self):
        self.repo.config.pop('OPENAI_API_KEY')
        ca.enqueue(self.repo)
        with patch.object(ca, 'analyze') as paid:
            result=ca.step(self.repo)
        paid.assert_not_called()
        self.assertEqual(result['status'],'error')
        self.assertEqual(self.db['openai-status.json']['reason'],'api_access')

    def test_invalid_model_result_requires_review_and_does_not_block_queue(self):
        self.units.append(dict(self.units[0], id='2', text='Another original'))
        ca.enqueue(self.repo)
        with patch.object(ca, 'analyze', side_effect=[ValueError('invalid output'), self.result(self.units[1])]) as paid:
            first=ca.step(self.repo)
            self.assertEqual(first['status'],'pending')
            self.assertEqual(first['review_required'],1)
            self.assertEqual(first['remaining'],1)
            fallback=self.db[ca.RESULTS][0]
            self.assertFalse(fallback['analysis_executed'])
            self.assertEqual(fallback['result']['direction'],'needs_review')
            self.assertEqual(fallback['result']['narrative_analysis']['match_status'],'uncertain')
            self.assertNotIn('invalid output',str(fallback))
            self.assertEqual(ca.step(self.repo)['status'],'complete')
            self.assertEqual(ca.pending(self.repo)[0],[])
            self.assertEqual(paid.call_count,2)

    def test_recover_legacy_validation_error_without_paid_retry(self):
        self.db[ca.STATE]={'status':'error','reason':'analysis_validation','remaining':1}
        with patch.object(ca,'analyze') as paid:
            state=ca.recover_validation_failure(self.repo)
        paid.assert_not_called()
        self.assertEqual(state['status'],'complete')
        self.assertEqual(state['review_required'],1)
        self.assertEqual(ca.pending(self.repo)[0],[])

    def test_timeout_and_stale_service_error_do_not_block_next_unit(self):
        self.units.append(dict(self.units[0], id='2'))
        ca.enqueue(self.repo)
        monitoring.record('openai', 'api_rate_limit', self.repo)
        with patch.object(ca, 'analyze', side_effect=[ca.AnalysisItemError('analysis_timeout'), self.result(self.units[1])]) as paid:
            self.assertEqual(ca.step(self.repo)['remaining'], 1)
            self.assertEqual(self.db[ca.RESULTS][0]['processing_reason'], 'analysis_timeout')
            self.assertEqual(ca.step(self.repo)['status'], 'complete')
        self.assertEqual(paid.call_count, 2)

    def test_interrupted_request_is_reviewed_without_repaying(self):
        self.units.append(dict(self.units[0], id='2'))
        ca.enqueue(self.repo)
        self.db[ca.STATE].update(status='running', inflight=ca.receipt(self.units[0], None, self.repo))
        self.repo.sql.return_value = {'rows': []}
        with patch.object(ca, 'analyze') as paid:
            self.assertEqual(ca.step(self.repo)['status'], 'already_running')
            self.repo.sql.return_value = {'rows': [['owner']]}
            self.assertEqual(ca.step(self.repo)['remaining'], 1)
            paid.assert_not_called()
        self.assertEqual(self.db[ca.RESULTS][0]['processing_reason'], 'analysis_interrupted')
        with patch.object(ca, 'analyze', side_effect=self.result) as paid:
            self.assertEqual(ca.step(self.repo)['status'], 'complete')
            self.assertEqual(paid.call_args.args[0]['id'], '2')

    def test_saved_result_with_stale_receipt_does_not_skip_next_unit(self):
        self.units.append(dict(self.units[0], id='2'))
        ca.enqueue(self.repo)
        self.db[ca.STATE].update(status='running', inflight=ca.receipt(self.units[0], None, self.repo))
        self.db[ca.RESULTS] = [dict(self.result(self.units[0]), content_fingerprint=ca.fingerprint(self.units[0]))]
        with patch.object(ca, 'analyze', side_effect=self.result) as paid:
            self.assertEqual(ca.step(self.repo)['status'], 'complete')
            self.assertEqual(paid.call_args.args[0]['id'], '2')
        self.assertNotIn('review_required', self.db[ca.STATE])

    def test_short_invocation_budget_yields_without_paid_call(self):
        ca.enqueue(self.repo)
        with patch.object(ca, 'analyze') as paid:
            self.assertEqual(ca.step(self.repo, deadline=100, monotonic=lambda: 50)['status'], 'pending')
        paid.assert_not_called()
        self.assertNotIn('inflight', self.db[ca.STATE])

    def test_database_failure_does_not_classify_or_remove_unit(self):
        ca.enqueue(self.repo)
        with patch.object(ca, 'analyze', side_effect=ca.CloudStorageError(reason='database_quota')):
            with self.assertRaises(ca.CloudStorageError): ca.step(self.repo)
        self.assertNotIn(ca.RESULTS, self.db)
        self.assertEqual(self.db[ca.STATE]['remaining'], 1)

    def test_drain_continues_after_item_failure(self):
        self.units.append(dict(self.units[0], id='2'))
        ca.enqueue(self.repo)
        with patch.object(ca, 'analyze', side_effect=[ValueError('invalid result'), self.result(self.units[1])]):
            state = ca.drain(self.repo, monotonic=lambda: 0)
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['review_required'], 1)
        self.assertEqual(state['completed'], 1)

    def test_browser_yields_to_waiting_collector(self):
        ca.enqueue(self.repo)
        self.db['background-schedule.json'] = {'collection_waiting_until': '2100-01-01T00:00:00Z'}
        with patch.object(ca, 'analyze') as paid:
            self.assertEqual(ca.step(self.repo)['reason'], 'collection_pending')
        paid.assert_not_called()
        self.assertEqual(self.db[ca.STATE]['status'], 'pending')
        self.assertIn('DELETE', self.repo.sql.call_args.args[0])

    def test_incomplete_collection_does_not_enqueue_or_replace_snapshot(self):
        old=copy.deepcopy(self.units)
        with patch('diaspora_client.DiasporaClient'), patch('cloud_collection.run_step',return_value={
                'status':'pending','phase':'details','processed_posts':4,'discovered_posts':20}), patch.object(ca,'enqueue') as enqueue:
            result=self.repo.collect()
        self.assertEqual(result['status'],'pending');enqueue.assert_not_called()
        self.assertEqual(self.units,old)
        self.assertEqual(self.db['collection-status.json']['status'],'running')

    def test_collection_enqueues_only_after_successful_save(self):
        packet={'records':self.units,'post_count':1,'comment_count':0,'collected_at':'2026-10-23T09:00:00Z'}
        with patch('diaspora_client.DiasporaClient'), patch('cloud_collection.run_step', return_value=dict(packet,status='ok')) as run:
            self.assertEqual(self.repo.collect()['analysis']['remaining'],1)
            run.assert_called_once()
        self.assertEqual(self.db['collection-status.json']['status'],'ok')

if __name__=='__main__':unittest.main()
