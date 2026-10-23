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
        self.version=ca.registry(self.repo)['version']

    def result(self,unit,*args,**kwargs):
        return {'analysis_executed':True,'source_reference':{'source':unit['source'],'id':unit['id']},
                'registry_version':self.version,'thermometer_rules_version':ca.VERSION,
                'exercise_id':unit.get('exercise_id'),'exercise_context':None,'model':'test-model'}

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
        with patch.object(ca,'analyze',side_effect=ValueError('secret must not leak')) as api:
            state=ca.step(self.repo)
            self.assertEqual(state['status'],'error');self.assertEqual(state['reason'],'api_quota')
            self.assertNotIn('secret',str(state));self.assertEqual(self.db[ca.RESULTS],[{'old':'preserved'}])
            ca.step(self.repo);api.assert_called_once()
            self.assertIn('DELETE',self.repo.sql.call_args.args[0])
        self.repo.latest=lambda:{'collected_at':'2026-10-23T09:00:00Z'}
        self.assertEqual(self.repo.monitoring_status()['reason'],'api_quota')

    def test_collection_enqueues_only_after_successful_save(self):
        packet={'records':self.units,'post_count':1,'comment_count':0,'collected_at':'2026-10-23T09:00:00Z'}
        with patch('diaspora_client.DiasporaClient') as client, patch('cloud_repository.sync') as sync:
            client.return_value.collect.return_value=packet
            self.assertEqual(self.repo.collect()['analysis']['remaining'],1)
            sync.assert_called_once()
        self.assertEqual(self.db['collection-status.json']['status'],'ok')

if __name__=='__main__':unittest.main()
