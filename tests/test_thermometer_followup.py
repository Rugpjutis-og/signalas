import copy,json,unittest
from unittest.mock import Mock,patch
import thermometer_followup as follow
from scenario_supplement import context_digest
from thermometer_review import key
from thermometer_policy import VERSION


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.db={follow.STATE:{'status':'waiting_primary','request_id':'approved-once',
                 'base_context_digest':context_digest(None),'supplement_id':'detail','scoring_rule_id':'rule'},
                 'analysis-job.json':{'status':'complete'},
                 'analysis-context-supplement.json':{'id':'detail','base_context_digest':context_digest(None)},
                 'exercise-account-context.json':{'base_context_digest':context_digest(None),
                    'source':'test','exercise_id':None,'revision':'roles','account_ids':{'synthetic':'guid'},
                    'scoring_rule':{'id':'rule','historical_review_enabled':True}}}
        self.repo=Mock(scope='test')
        self.repo.values={}
        self.repo.read.side_effect=lambda name,default=None:copy.deepcopy(self.db.get(name,default))
        self.repo.write.side_effect=lambda name,value:self.db.update({name:copy.deepcopy(value)})
        self.repo.sql.return_value={'rows':[['owner']]}
        self.units=[{'source':'test','id':'new','content_fingerprint':'hash-new','exercise_id':None,
                     'previous_category':'stabilizing','author_id':'guid','published_at':'2026-10-25T09:00:00Z'},
                    {'source':'test','id':'old','content_fingerprint':'hash-old','exercise_id':None,
                     'previous_category':'neutral','author_id':'other','published_at':'2026-10-24T09:00:00Z'}]

    def start(self):
        with patch.object(follow,'registry',return_value={'version':'registry'}),patch.object(follow,'candidates',return_value=copy.deepcopy(self.units)):
            return follow.maybe_start(self.repo)

    def test_waits_without_reading_source_or_calling_ai(self):
        for status in ('pending','running','error','paused',None):
            self.db['analysis-job.json']={'status':status}
            self.start()
            self.repo.write.assert_not_called()
            self.repo.sql.assert_not_called()
        self.db['analysis-job.json']={'status':'complete'}
        self.db['thermometer-recheck-job.json']={'status':'pending'}
        self.start()
        self.repo.sql.assert_not_called()

    def test_starts_once_in_reverse_order_and_keeps_manual_reviews(self):
        manual={'content_fingerprint':'hash-old','exercise_id':None,'exercise_context':None,'rules_version':VERSION}
        self.db['thermometer-reviews.json']={key('test','old'):manual}
        self.db['thermometer-recheck-job.json']={'status':'complete','run_id':'previous','total':3}
        saved=self.start()
        self.assertEqual(saved['status'],'scheduled')
        self.assertEqual(saved['manual_skips'],1)
        job=self.db['thermometer-recheck-job.json']
        self.assertEqual([t['id'] for t in job['targets']],['new'])
        self.assertEqual(job['targets'][0]['scoring_rule_id'],'rule')
        self.assertEqual(job['scenario_supplement_review'],'detail')
        self.assertEqual(job['selection_categories'],['neutral','stabilizing'])
        self.assertTrue(job['preserve_previous'])
        self.assertEqual(self.db['thermometer-reviews.json'][key('test','old')],manual)
        self.assertIn('thermometer-recheck-history/previous',self.db)
        count=self.repo.write.call_count
        self.start()
        self.assertEqual(self.repo.write.call_count,count)

    def test_new_context_pauses_instead_of_silently_using_different_facts(self):
        self.db['analysis-context-supplement.json']['id']='different'
        result=self.start()
        self.assertEqual(result['status'],'paused')
        self.assertNotIn('thermometer-recheck-job.json',self.db)

    def test_busy_lease_does_not_start(self):
        self.repo.sql.return_value={'rows':[]}
        self.start()
        self.repo.write.assert_not_called()

    def test_candidate_query_filters_latest_before_category_and_returns_no_bodies(self):
        self.repo.sql.return_value={'rows':[[json.dumps(self.units)]]}
        result=follow.candidates(self.repo,None,'registry')
        self.assertEqual(result,self.units)
        statement=self.repo.sql.call_args.args[0]
        self.assertIn('DISTINCT ON',statement)
        self.assertIn("IN('neutral','stabilizing')",statement)
        self.assertIn("published_at')::timestamptz DESC",statement)
        self.assertNotIn("'text',",statement)
        self.assertNotIn('SELECT packet FROM signalas_fetches WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1) SELECT *',statement)
