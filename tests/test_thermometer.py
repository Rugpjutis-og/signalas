import copy
import json
import unittest

import thermometer as t


class ThermometerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = t.load_demo()

    def report(self, units=None, start='2026-10-13T00:00:00+03:00', end='2026-10-20T00:00:00+03:00'):
        return t.aggregate(self.fixture['units'] if units is None else units,
                           self.fixture['contexts'], self.fixture['assessments'], start, end)

    def test_denominator_excludes_review_and_unrelated_still_counts(self):
        report = self.report()
        self.assertEqual(report['total'], 34)
        self.assertEqual(report['assessed'] + report['unassessed'], 34)
        self.assertGreater(report['unassessed'], 0)
        self.assertAlmostEqual(sum(c['percent'] for c in report['categories']), 100, delta=.15)
        for c in report['categories']:
            self.assertEqual(c['percent'], round(c['count'] / report['assessed'] * 100, 1))
        self.assertTrue(any(u['narrative_id'] is None and u['assessment']['category'] == 'neutral' for u in report['units']))

    def test_duplicates_and_attachments_count_once_but_reposts_count(self):
        units = self.fixture['units']
        base = self.report()
        self.assertEqual(self.report(units + units)['total'], base['total'])
        repost = copy.deepcopy(units[0]); repost['id'] = 'distinct-repost'
        self.assertEqual(self.report(units + [repost])['total'], base['total'] + 1)
        video = next(u for u in units if any(a['kind'] == 'video' for a in u['attachments']))
        self.assertEqual(self.report([video])['total'], 1)

    def test_missing_context_is_pending_not_neutral(self):
        unit = dict(self.fixture['units'][0], published_at='2026-10-12T12:00:00+03:00')
        a = t.demo_assessment(unit, self.fixture['contexts'], self.fixture['assessments'])
        self.assertEqual(a['status'], 'needs_review')
        self.assertIsNone(a['category'])
        self.assertIsNone(t.model_input(unit, self.fixture['contexts']))

    def test_context_boundary_and_no_hindsight(self):
        unit = self.fixture['units'][0]
        before = dict(unit, published_at='2026-10-17T08:59:59+03:00')
        after = dict(unit, published_at='2026-10-17T09:00:00+03:00')
        self.assertEqual(t.context_at(before, self.fixture['contexts'])['version'], 'vanduo-v1')
        self.assertEqual(t.context_at(after, self.fixture['contexts'])['version'], 'vanduo-v2')
        self.assertEqual(t.demo_assessment(after,self.fixture['contexts'],self.fixture['assessments'])['status'], 'needs_review')
        prompt = t.model_input(before, self.fixture['contexts'])
        self.assertNotIn('vanduo-v2', json.dumps(prompt))

    def test_empty_and_all_unassessed_do_not_fake_zero_percent(self):
        for report in (self.report([]), self.report(start='2026-10-15T00:00:00+03:00',end='2026-10-16T00:00:00+03:00')):
            self.assertEqual(report['assessed'], 0)
            self.assertTrue(all(c['percent'] is None for c in report['categories']))
        self.assertEqual(self.report()['days'][2]['assessed'], 0)

    def test_half_open_interval_and_local_midnight(self):
        original = self.fixture['units'][0]
        units = [dict(original, id='start', published_at='2026-10-18T21:00:00Z'),
                 dict(original, id='before', published_at='2026-10-18T20:59:59Z'),
                 dict(original, id='end', published_at='2026-10-19T21:00:00Z')]
        report = self.report(units, start='2026-10-19T00:00:00+03:00',end='2026-10-20T00:00:00+03:00')
        self.assertEqual([u['id'] for u in report['units']], ['start'])
        self.assertEqual(report['days'][0]['total'], 1)

    def test_role_stance_and_engagement_cannot_change_direction(self):
        original = self.fixture['units'][0]
        changed = dict(original, author_role='opposition', organization='fictional', likes=90000, stance='oppose')
        self.assertEqual(t.demo_assessment(original,self.fixture['contexts'],self.fixture['assessments']),
                         t.demo_assessment(changed,self.fixture['contexts'],self.fixture['assessments']))
        model = t.model_input(changed, self.fixture['contexts'])
        self.assertNotIn('author_role', model['content'])
        self.assertNotIn('stance', model['content'])

    def test_changed_content_requires_new_assessment(self):
        unit = dict(self.fixture['units'][0], text='Pakeistas turinys')
        result = t.demo_assessment(unit, self.fixture['contexts'], self.fixture['assessments'])
        self.assertEqual(result['status'], 'needs_review')
        self.assertIsNone(result['category'])

    def test_future_replies_are_not_in_model_input(self):
        unit = dict(self.fixture['units'][0], conversation_context=[
            {'text': 'Ankstesnis kontekstas', 'published_at': '2026-10-13T08:00:00+03:00'},
            {'text': 'Vėlesnė žinutė', 'published_at': '2026-10-20T08:00:00+03:00'}])
        result = t.model_input(unit, self.fixture['contexts'])
        self.assertEqual(len(result['content']['conversation_context']), 1)
        self.assertEqual(result['content']['conversation_context'][0]['text'], 'Ankstesnis kontekstas')

    def test_interpretation_examples(self):
        assessed = self.report()['units']
        for tag, category in [('criticism','stabilizing'),('refutation','stabilizing'),('warning','stabilizing'),('opposition','neutral'),('positive_harm','destabilizing')]:
            rows = [u for u in assessed if u['assessment'].get('case_tag') == tag]
            self.assertTrue(rows,tag)
            self.assertTrue(all(u['assessment']['category'] == category for u in rows))
        for unit in assessed:
            if unit['assessment']['status'] == 'assessed':
                self.assertTrue(unit['assessment']['reason'])
                self.assertTrue(unit['assessment']['evidence'])
                self.assertTrue(unit['assessment']['context_version'])
            if any(a['kind']=='video' for a in unit['attachments']):
                self.assertFalse(unit['attachments'][0]['coverage']['full_video_reviewed'])

    def test_periods_snapshots_and_totals_match(self):
        for period, count in ((10,34),(7,34),(3,16),(1,6)):
            report=t.demo_report(period)
            self.assertEqual(report['total'],count)
            self.assertEqual(len(report['days']),period)
            self.assertEqual(sum(d['total'] for d in report['days']),count)
            snapshot=json.loads((t.ROOT / ('dist/demo/thermometer-%s.json'%period)).read_text())
            self.assertEqual(snapshot,report)
        with self.assertRaises(ValueError): t.demo_report(2)


if __name__ == '__main__':
    unittest.main()
