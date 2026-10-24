import copy,threading,unittest
from unittest.mock import patch,Mock
import cloud_analysis as ca
import optimized_analysis as opt
import test_cloud_analysis as legacy


class OptimizedTests(unittest.TestCase):
    result=legacy.CloudAnalysisTests.result
    queue_results=legacy.CloudAnalysisTests.queue_results
    def setUp(self):
        legacy.CloudAnalysisTests.setUp(self)
        self.db[opt.POLICY]={'enabled':True}
        self.units=[{**self.units[0],'id':str(i)} for i in range(1,5)]
        self.repo.analysis_queue_page=lambda generation,offset,limit:copy.deepcopy(self.db[opt.PLAN]['units'][offset:offset+limit]) if self.db.get(opt.PLAN,{}).get('generation')==generation else None
        self.repo.analysis_queue_results=lambda units,context,version,model:[a for a in self.queue_results(context,version,model) if (a['source_reference']['source'],a['source_reference']['id']) in {(u['source'],u['id']) for u in units}]
        self.repo.analysis_worker=lambda index:self.repo # Tests replace AI entirely; no shared live sessions.

    # Legacy engine cases run separately under its disabled-by-default rollout policy.
    def test_two_workers_and_per_result_persistence(self):
        self.units=self.units[:2];ca.enqueue(self.repo)
        arrived=threading.Barrier(2);first_saved=threading.Event();counts={'active':0,'maximum':0};lock=threading.Lock()
        append=self.repo.append_analysis
        def save(value):
            append(value)
            if value['source_reference']['id']=='1':first_saved.set()
        self.repo.append_analysis=save
        def api(unit,*args,**kwargs):
            with lock:counts['active']+=1;counts['maximum']=max(counts['maximum'],counts['active'])
            arrived.wait(timeout=3)
            if unit['id']=='2':self.assertTrue(first_saved.wait(timeout=3),'first result must persist before second completes')
            with lock:counts['active']-=1
            return self.result(unit)
        with patch.object(ca,'analyze',side_effect=api) as paid:
            self.assertEqual(ca.step(self.repo)['status'],'complete')
            ca.step(self.repo)
        self.assertEqual(paid.call_count,2);self.assertEqual(counts['maximum'],2)
        self.assertEqual(self.db[ca.STATE]['completed'],2)

    def test_three_primary_units_then_review_and_no_budget_false_progress(self):
        ca.enqueue(self.repo)
        with patch.object(ca,'analyze',side_effect=self.result) as paid,patch('thermometer_recheck.active',return_value=True),patch('thermometer_recheck.step',return_value={'status':'pending','kind':'thermometer_recheck'}) as review:
            ca.step(self.repo);self.assertEqual(paid.call_count,2);review.assert_not_called()
            ca.step(self.repo);self.assertEqual(paid.call_count,3);review.assert_not_called()
            ca.step(self.repo);review.assert_called_once();self.assertEqual(paid.call_count,3)
        self.db[ca.STATE]['primary_since_review']=0
        with patch.object(ca,'analyze') as paid:
            before=copy.deepcopy(self.db[ca.STATE]);ca.step(self.repo,deadline=20,monotonic=lambda:0)
            paid.assert_not_called();self.assertEqual(self.db[ca.STATE],before)

    def test_snapshot_binding_change_stops_calls(self):
        ca.enqueue(self.repo);self.db[ca.STATE]['queue_bindings']['model']='different'
        with patch.object(ca,'analyze') as paid:
            out=ca.step(self.repo)
        paid.assert_not_called();self.assertEqual(out['reason'],'queue_refresh_required')

    def test_inflight_batch_recovers_only_unsaved_unit_without_api(self):
        self.units=self.units[:2];ca.enqueue(self.repo)
        self.db[ca.STATE].update(status='running',batch_end=2,inflight_batch=[ca.receipt(u,None,self.repo) for u in self.units])
        self.db[ca.RESULTS]=[{**self.result(self.units[0]),'content_fingerprint':ca.fingerprint(self.units[0])}]
        with patch.object(ca,'analyze') as paid:out=ca.step(self.repo)
        paid.assert_not_called();self.assertEqual(out['status'],'complete')
        self.assertEqual(len(self.db[ca.RESULTS]),2)
        self.assertEqual(self.db[ca.RESULTS][-1]['source_reference']['id'],'2')
        self.assertEqual(self.db[ca.RESULTS][-1]['processing_reason'],'analysis_interrupted')

    def test_validation_error_does_not_lose_other_worker_result(self):
        self.units=self.units[:2];ca.enqueue(self.repo)
        def api(unit,*args,**kwargs):
            if unit['id']=='1':raise ValueError('bad output')
            return self.result(unit)
        with patch.object(ca,'analyze',side_effect=api) as paid:out=ca.step(self.repo)
        self.assertEqual(paid.call_count,2);self.assertEqual(out['completed'],1)
        self.assertEqual(out['review_required'],1);self.assertEqual(out['remaining'],0)
        self.assertEqual(ca.pending(self.repo)[0],[])

    def test_unknown_units_are_not_expanded_to_build_queue(self):
        self.units=[{**self.units[0],'id':str(i)} for i in range(5000)]
        with patch.object(self.repo,'expand_unit',wraps=self.repo.expand_unit) as expand:
            units,_=ca.pending(self.repo)
        self.assertEqual(len(units),5000);expand.assert_not_called()


    def test_provider_failure_stops_after_bounded_batch_but_keeps_other_success(self):
        self.units=self.units[:2];ca.enqueue(self.repo)
        def api(unit,*args,**kwargs):
            if unit['id']=='1':raise ca.AnalysisServiceError('api_quota')
            return self.result(unit)
        with patch.object(ca,'analyze',side_effect=api) as paid:
            state=ca.step(self.repo);ca.step(self.repo)
        self.assertEqual(paid.call_count,2);self.assertEqual(state['status'],'error')
        self.assertEqual(state['reason'],'api_quota');self.assertEqual(len(self.db[ca.RESULTS]),1)
        self.assertEqual(self.db[ca.RESULTS][0]['source_reference']['id'],'2')

    def test_enqueue_cannot_drop_interrupted_batch_receipts(self):
        ca.enqueue(self.repo);state=self.db[ca.STATE]
        state.update(status='running',batch_end=2,inflight_batch=[ca.receipt(u,None,self.repo) for u in self.units[:2]])
        before=copy.deepcopy(state);self.assertEqual(ca.enqueue(self.repo),before)
        self.assertEqual(self.db[ca.STATE],before)

    def test_new_arrivals_precede_backlog_without_copying_content_into_plan(self):
        ca.enqueue(self.repo)
        with patch.object(ca,'analyze',side_effect=self.result):ca.step(self.repo)
        self.units.append({**self.units[0],'id':'new-arrival','published_at':'2026-10-24T18:00:00Z'})
        ca.enqueue(self.repo)
        plan=self.db[opt.PLAN]
        self.assertEqual(plan['units'][0],['test','new-arrival'])
        self.assertEqual(set(plan),{'generation','units'})
        self.assertNotIn('Original',str(plan))

    def test_recovery_does_not_mark_changed_content_as_interrupted(self):
        self.units=self.units[:2];ca.enqueue(self.repo)
        state=self.db[ca.STATE];state.update(status='running',batch_end=2,inflight_batch=[ca.receipt(u,None,self.repo) for u in self.units])
        self.units[0]['text']='Changed since paid call'
        with patch.object(ca,'analyze') as paid:ca.step(self.repo)
        paid.assert_not_called();self.assertEqual(len(self.db[ca.RESULTS]),1)
        self.assertEqual(self.db[ca.RESULTS][0]['source_reference']['id'],'2')

    def test_plan_build_never_expands_known_or_unknown_content(self):
        self.db[ca.RESULTS]=[{**self.result(self.units[0]),'content_fingerprint':ca.fingerprint(self.units[0])}]
        with patch.object(self.repo,'expand_unit',side_effect=AssertionError('whole-corpus expansion forbidden')):
            state=ca.enqueue(self.repo)
        self.assertEqual(state['remaining_kind'],'candidate_checks')
        self.assertEqual(self.db[opt.PLAN]['units'][-1],['test','1'])

    def test_existing_lease_prevents_any_new_parallel_calls(self):
        ca.enqueue(self.repo);self.repo.sql.return_value={'rows':[]}
        with patch.object(ca,'analyze') as paid:state=ca.step(self.repo)
        paid.assert_not_called();self.assertEqual(state['status'],'already_running')

    def test_live_worker_instances_do_not_share_sessions_or_mutable_caches(self):
        from cloud_repository import Repository
        root=Repository({'OPENAI_API_KEY':'synthetic'});root.packet={'records':[]};root.values={'small-state':{'id':'one'}}
        one=root.analysis_worker(0);two=root.analysis_worker(1)
        self.assertIsNot(one,two);self.assertIs(one.packet,two.packet)
        self.assertIsNot(one.values,two.values)
        one._vision_client='synthetic-client'
        self.assertFalse(hasattr(two,'_vision_client'))

    def test_parallelism_continues_after_first_three_when_no_review_active(self):
        ca.enqueue(self.repo)
        with patch.object(ca,'analyze',side_effect=self.result) as paid:
            ca.step(self.repo);state=ca.step(self.repo)
        self.assertEqual(paid.call_count,4);self.assertEqual(state['status'],'complete')

    def test_disabled_rollout_still_recovers_existing_parallel_receipts(self):
        self.units=self.units[:2];ca.enqueue(self.repo)
        self.db[ca.STATE].update(status='running',batch_end=2,inflight_batch=[ca.receipt(u,None,self.repo) for u in self.units])
        self.db[opt.POLICY]={'enabled':False}
        with patch.object(ca,'analyze') as paid:state=ca.step(self.repo)
        paid.assert_not_called();self.assertEqual(state['status'],'complete')
        self.assertEqual(state['review_required'],2)
