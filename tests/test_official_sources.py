import copy
import unittest
from unittest.mock import Mock, patch

import official_sources as policy
from scenario_supplement import context_digest
from thermometer_policy import VERSION
from thermometer_review import key
from live_data import fingerprint
from discussion_context import DiscussionIndex


class OfficialSourceTests(unittest.TestCase):
    def setUp(self):
        self.context = {'initialSituation': 'Fiktyvios pratybos', 'confirmedFacts': 'Pradinis kontekstas', 'nameMappings': []}
        self.config = {'revision': policy.REVISION, 'status': 'waiting_for_current_checks',
            'source': 'pod.test', 'exercise_id': 'exercise-one', 'base_context_digest': context_digest(self.context),
            'after_review_run_id': 'started-review', 'accounts': [
                {'author_id': 'official-guid', 'handle': 'official@pod.test', 'label': 'Oficialus pratybų šaltinis'}]}
        self.db = {policy.STATE: self.config, 'live-context.json': self.context,
                   'analysis-job.json': {'status': 'pending'},
                   'thermometer-recheck-job.json': {'run_id': 'started-review', 'status': 'pending'}}
        self.repo = Mock(scope='test')
        self.repo.values = {}
        self.repo.read.side_effect = lambda name, default=None: copy.deepcopy(self.db.get(name, default))
        self.repo.write.side_effect = lambda name, value: self.db.update({name: copy.deepcopy(value)})
        self.repo.sql.return_value = {'rows': [['owner']]}
        self.unit = {'source': 'pod.test', 'id': 'post', 'exercise_id': 'exercise-one', 'kind': 'post',
            'author_id': 'official-guid', 'author_handle': 'official@pod.test',
            'published_at': '2026-10-23T09:00:00Z', 'text': 'Pranešimas', 'media': []}
        self.independent = {'status': 'assessed', 'category': 'neutral', 'method': 'openai_text_pilot', 'reason': 'AI pagrindas'}

    def activate_fixture(self):
        self.config.update(status='active', activated_at='2026-10-29T12:00:00Z')

    def test_waiting_never_changes_content_or_starts_more_work(self):
        self.assertIs(policy.assessment(self.repo, self.unit, self.independent), self.independent)
        policy.maybe_activate(self.repo)
        self.repo.sql.assert_not_called(); self.repo.write.assert_not_called()
        self.db['analysis-job.json']['status'] = 'complete'
        policy.maybe_activate(self.repo)
        self.repo.sql.assert_not_called(); self.repo.write.assert_not_called()

    def test_activates_only_after_both_checks_complete_and_is_idempotent(self):
        self.db['analysis-job.json']['status'] = 'complete'
        self.db['thermometer-recheck-job.json']['status'] = 'complete'
        result = policy.maybe_activate(self.repo)
        self.assertEqual(result['status'], 'active')
        self.assertEqual(self.repo.write.call_count, 1)
        policy.maybe_activate(self.repo)
        self.assertEqual(self.repo.write.call_count, 1)

    def test_archived_completion_and_busy_lease_are_respected(self):
        self.db['analysis-job.json']['status'] = 'complete'
        self.db['thermometer-recheck-job.json'] = {'run_id': 'another-review', 'status': 'pending'}
        self.db['thermometer-recheck-history/started-review'] = {'run_id': 'started-review', 'status': 'complete'}
        self.repo.sql.return_value = {'rows': []}
        self.assertEqual(policy.maybe_activate(self.repo)['status'], 'waiting_for_current_checks')
        self.repo.write.assert_not_called()
        self.repo.sql.return_value = {'rows': [['owner']]}
        self.assertEqual(policy.maybe_activate(self.repo)['status'], 'active')

    def test_own_exact_post_only_and_independent_assessment_retained(self):
        self.activate_fixture()
        result = policy.assessment(self.repo, self.unit, self.independent)
        self.assertEqual(result['category'], 'stabilizing')
        self.assertEqual(result['method'], 'exercise_organizer_rule')
        self.assertEqual(result['independent_content_assessment'], self.independent)
        self.assertEqual(self.independent['category'], 'neutral')
        for changes in ({'source': 'other.test'}, {'exercise_id': 'another'}, {'author_id': 'other'},
                        {'kind': 'comment', 'parent_id': 'post'}, {'author_handle': 'impostor@pod.test'}):
            self.assertIs(policy.assessment(self.repo, {**self.unit, **changes}, self.independent), self.independent)
        self.assertEqual(policy.assessment(self.repo, {**self.unit, 'author_handle': None}, self.independent)['category'], 'stabilizing')

    def test_changed_context_disables_rule(self):
        self.activate_fixture()
        self.db['live-context.json'] = {**self.context, 'confirmedFacts': 'Kitas kontekstas'}
        self.assertIs(policy.assessment(self.repo, self.unit, self.independent), self.independent)

    def test_report_statistics_and_manual_priority_without_rewriting_ai(self):
        import live_data
        self.activate_fixture()
        packet = {'records': [self.unit], 'coverage': 'account_visible_stream', 'source': 'pod.test'}
        analysis = {'analysis_executed': True, 'thermometer_rules_version': VERSION,
                    'method': 'openai_text_pilot', 'result': {'thermometer_status': 'classified',
                    'thermometer_category': 'neutral', 'reason': 'AI pagrindas', 'reason_codes': ['N1'], 'evidence': 'Pranešimas'}}
        before = copy.deepcopy(analysis)
        def report():
            with patch.object(live_data, 'load', return_value=(packet, self.context, {('pod.test', 'post'): analysis})), \
                    patch.object(live_data, 'coverage', return_value={}):
                return live_data.thermometer(root=self.repo, start_date='2026-10-23', end_date='2026-10-23')
        result = report()
        self.assertEqual(result['units'][0]['assessment']['category'], 'stabilizing')
        self.assertEqual({c['id']: c['count'] for c in result['categories']}['stabilizing'], 1)
        self.assertEqual(analysis, before)
        expanded = DiscussionIndex([self.unit]).expand(self.unit)
        self.db['thermometer-reviews.json'] = {key('pod.test', 'post'): {
            'content_fingerprint': fingerprint(expanded), 'exercise_id': 'exercise-one',
            'exercise_context': self.context, 'rules_version': VERSION, 'category': 'destabilizing',
            'reason': 'Analitiko sprendimas', 'evidence': ''}}
        result = report()
        self.assertEqual(result['units'][0]['assessment']['method'], 'manual_review')
        self.assertEqual({c['id']: c['count'] for c in result['categories']}['destabilizing'], 1)
        self.assertEqual({c['id']: c['count'] for c in result['categories']}['stabilizing'], 0)
        self.repo.write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
