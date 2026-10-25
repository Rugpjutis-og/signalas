import json,unittest
from unittest.mock import Mock
from cloud_repository import Repository
from cloud_storage import CloudStorageError


class DashboardPageTests(unittest.TestCase):
    def test_current_bindings_resolve_pointers_then_fetch_indexed_bodies(self):
        repo=Repository({})
        context={'initialSituation':'test','confirmedFacts':'facts','nameMappings':[]}
        identities=[{'source':'test','id':str(i),'fingerprint':'fp-'+str(i)} for i in range(1205)]
        page_sizes=[];metadata_sizes=[]
        def sql(statement,params):
            if 'WITH assessments AS' in statement:
                self.assertIn('DISTINCT ON',statement)
                self.assertIn('stage DESC,n DESC',statement)
                self.assertIn("a->>'content_fingerprint'=wanted.fingerprint",statement)
                self.assertNotIn('jsonb_agg(a ',statement)
                wanted=json.loads(params[2]);metadata_sizes.append(len(wanted))
                self.assertEqual(json.loads(params[1]),context)
                return {'rows':[[json.dumps([{**p,'row_name':'analysis-result/'+p['id'],'n':0} for p in wanted])]]}
            self.assertIn('s.name=wanted.row_name',statement)
            self.assertIn('s.scope=$1',statement)
            self.assertIn("a-'exercise_context'",statement)
            self.assertIn('s.value->(wanted.n-1)',statement)
            page=json.loads(params[1]);page_sizes.append(len(page))
            self.assertLessEqual(len(page),100)
            self.assertEqual(json.loads(params[2]),context)
            return {'rows':[[json.dumps([{'source_reference':{'source':p['source'],'id':p['id']},
                'content_fingerprint':p['fingerprint']} for p in page])]]}
        repo.sql=Mock(side_effect=sql)
        results=list(repo.dashboard_analyses(identities,context))
        self.assertEqual(metadata_sizes,[1000,205])
        self.assertEqual(page_sizes,[100]*12+[5])
        self.assertEqual(len(results),1205)
        self.assertTrue(all(r['exercise_context'] is context for r in results))
        self.assertEqual({r['source_reference']['id'] for r in results},{str(i) for i in range(1205)})

    def test_empty_content_does_not_load_history(self):
        repo=Repository({});repo.sql=Mock()
        self.assertEqual(list(repo.dashboard_analyses([],None)),[])
        repo.sql.assert_not_called()

    def test_missing_selected_result_is_not_reported_as_empty_success(self):
        repo=Repository({})
        repo.sql=Mock(side_effect=[{'rows':[[json.dumps([{'row_name':'legacy','n':1,'source':'test','id':'p','fingerprint':'fp'}])]]},
                                  {'rows':[['[]']]}])
        with self.assertRaises(CloudStorageError):
            list(repo.dashboard_analyses([{'source':'test','id':'p','fingerprint':'fp'}],None))
