import copy,json,unittest
from unittest.mock import Mock,patch
from cloud_repository import Repository,analysis_result_name
from scenario_supplement import context_digest
from live_data import fingerprint
from thermometer_review import key
import exercise_accounts as ea
import thermometer_recheck as review


class AccountContextTests(unittest.TestCase):
    def setUp(self):
        self.repo=Repository({'DIASPORA_BASE_URL':'https://example.org','DIASPORA_USERNAME':'test','DIASPORA_PASSWORD':'synthetic'})
        self.state={'revision':'organizer-test','source':'example.org','exercise_id':None,
            'base_context_digest':context_digest(None),'usernames':['pax002','pax006'],
            'account_ids':{'pax002':'actor-guid'},'status':'pending','cursor':0}
        self.db={ea.STATE:copy.deepcopy(self.state)}
        self.repo.read=lambda name,default=None:copy.deepcopy(self.db.get(name,default))
        self.repo.write=lambda name,value:self.db.update({name:copy.deepcopy(value)})
        self.repo.sql=Mock(return_value={'rows':[['owner']]})
        self.unit={'source':'example.org','id':'post','author_id':'actor-guid','kind':'post',
            'published_at':'2026-10-24T12:00:00Z','text':'Gražaus savaitgalio šeimai.','exercise_id':None}

    def test_exact_source_identity_not_display_name_or_parent_identity(self):
        self.assertTrue(ea.matches(self.state,self.unit))
        self.assertFalse(ea.matches(self.state,{**self.unit,'source':'different.org'}))
        self.assertFalse(ea.matches(self.state,{**self.unit,'exercise_id':'another'}))
        self.assertFalse(ea.matches(self.state,{**self.unit,'author_id':'other','author_name':'pax002',
            'parent_post':self.unit}))
        self.assertTrue(ea.matches(self.state,{**self.unit,'author_id':'other','author_handle':'PAX006@EXAMPLE.ORG'}))
        self.assertFalse(ea.matches(self.state,{**self.unit,'author_id':'other','author_handle':'pax006@different.org'}))
        value=ea.for_unit(self.repo,self.unit)
        self.assertEqual(value['revision'],'organizer-test')
        self.assertNotIn('category',value)
        self.assertNotIn('author_id',value)
        self.assertNotIn('usernames',value)
        self.db['live-context.json']={'different':'context'}
        self.assertIsNone(ea.for_unit(self.repo,self.unit))

    def test_resolution_requires_source_handle_and_never_uses_display_name(self):
        from diaspora_client import DiasporaRequestError
        client=Mock()
        client.json.side_effect=[{'guid':'g1','diaspora_id':'pax002@example.org'},
            {'guid':'g2','diaspora_id':'different@example.org','name':'pax006'}]
        self.db[ea.STATE]['account_ids']={}
        with patch.object(ea,'DiasporaClient',return_value=client),patch.object(ea,'append_review') as queue:
            ea.service(self.repo,monotonic=lambda:0)
        value=self.db[ea.STATE]
        self.assertEqual(value['account_ids'],{'pax002':'g1'})
        self.assertEqual(value['unresolved'],{'pax006':'source_identity_unconfirmed'})
        queue.assert_called_once()
        self.assertEqual(self.repo.sql.call_args.args[0],'DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2')

    def test_append_keeps_current_pass_and_manual_overrides_and_does_not_requeue_unassessed(self):
        units=[self.unit,{**self.unit,'id':'manual'},{**self.unit,'id':'new'},
               {**self.unit,'id':'not-listed','author_id':'other'}]
        self.repo.latest=lambda:{'records':units};self.repo.expand_unit=lambda u:u
        manual=units[1]
        self.db['thermometer-reviews.json']={key(manual['source'],manual['id']):{
            'content_fingerprint':fingerprint(manual),'exercise_context':None,'exercise_id':None,'rules_version':review.VERSION}}
        target={'source':self.unit['source'],'id':self.unit['id'],'content_fingerprint':fingerprint(self.unit),'exercise_id':None}
        job={'status':'pending','run_id':'keep-existing-pass','targets':[target],'cursor':0,'total':1,'remaining':1}
        self.db[review.STATE]=copy.deepcopy(job)
        bindings=[{'source':u['source'],'id':u['id'],'fingerprint':fingerprint(u)} for u in units[:2]]
        self.repo.sql=Mock(return_value={'rows':[[json.dumps(bindings)]]})
        ea.append_review(self.repo,self.db[ea.STATE])
        saved=self.db[review.STATE]
        self.assertEqual(saved['run_id'],'keep-existing-pass')
        self.assertEqual(len(saved['targets']),1)
        self.assertEqual(saved['targets'][0]['account_context_revision'],'organizer-test')
        self.assertEqual(self.db[ea.STATE]['manual_skips'],1)
        self.assertEqual(self.db[ea.STATE]['review_targets'],1)
        self.db[ea.STATE]['status']='queue_pending' # Recovery after job saved but setup completion interrupted.
        ea.append_review(self.repo,self.db[ea.STATE])
        self.assertEqual(self.db[ea.STATE]['status'],'complete')
        self.assertEqual(len(self.db[review.STATE]['targets']),1,'repeat setup is idempotent')

    def test_context_revision_distinguishes_new_results_without_invalidating_old_bindings(self):
        original={'review_run_id':'same','source_reference':{'source':'pod','id':'p'}}
        self.assertNotEqual(analysis_result_name(original),analysis_result_name({**original,'exercise_actor_context_revision':'new'}))

    def test_scoring_review_request_is_distinct_from_previous_role_review_and_idempotent(self):
        self.repo.latest=lambda:{'records':[self.unit]};self.repo.expand_unit=lambda u:u
        target={'source':self.unit['source'],'id':self.unit['id'],'content_fingerprint':fingerprint(self.unit),'exercise_id':None,'account_context_revision':self.state['revision']}
        self.db[review.STATE]={'status':'pending','run_id':'existing','targets':[target],'cursor':0,'account_context_requests':[self.state['revision']]}
        state=self.db[ea.STATE];state['scoring_review_request']='explicit-scoring-retro';state['scoring_rule']={'id':'rule-test'}
        self.repo.sql=Mock(return_value={'rows':[[json.dumps([{'source':self.unit['source'],'id':self.unit['id'],'fingerprint':fingerprint(self.unit)}])]]})
        ea.append_review(self.repo,state)
        self.assertEqual(self.db[review.STATE]['targets'][0]['scoring_rule_id'],'rule-test')
        self.assertEqual(self.db[review.STATE]['run_id'],'existing')
        self.assertIn('explicit-scoring-retro',self.db[review.STATE]['account_context_requests'])
        ea.append_review(self.repo,state)
        self.assertEqual(len(self.db[review.STATE]['targets']),1)
