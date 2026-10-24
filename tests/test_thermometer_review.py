import unittest

import thermometer_review as review


class FakeRepository:
    scope = 'exercise-test'

    def __init__(self):
        self.unit = {'source': 'pod.test', 'id': 'p1', 'kind': 'post',
                     'text': 'Taiki žinutė', 'published_at': '2026-10-21T07:00:00Z',
                     'exercise_id': None, 'media': [], 'sourceUrl': 'https://pod.test/p/original'}
        self.values = {}
        self.written = []

    def latest(self):
        return {'records': [self.unit]}

    def read(self, name, default=None):
        return default

    def sql(self, statement, params=None):
        self.written.append((statement, params))
        return {'rows': []}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.payload = {'source': 'pod.test', 'id': 'p1', 'category': 'neutral',
                        'reason_code': 'N1', 'reason': 'Tai taiki nuomonė.'}

    def test_persists_content_bound_decision_in_neon_state(self):
        result = review.save(self.repo, self.payload)
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(len(self.repo.written), 1)
        sql, params = self.repo.written[0]
        self.assertIn('ON CONFLICT', sql)
        self.assertIn('jsonb_build_object($3::text,$4::jsonb)', sql)
        self.assertEqual(params[1:3], [review.NAME, review.key('pod.test', 'p1')])
        import json
        decision = json.loads(params[3])
        self.assertEqual(decision['category'], 'neutral')
        self.assertTrue(review.applicable(decision, self.repo.unit, None))
        self.repo.unit['text'] = 'Pasikeitęs turinys'
        self.assertFalse(review.applicable(decision, self.repo.unit, None))

    def test_all_manual_directions_save_without_separate_excerpt(self):
        import json
        for category, code in [('stabilizing', 'S2'), ('neutral', 'N1'), ('destabilizing', 'D2'), ('destabilizing', 'D5'), ('destabilizing', 'D1'), ('stabilizing', 'S1')]:
            with self.subTest(category=category):
                result = review.save(self.repo, {**self.payload, 'category': category, 'reason_code': code})
                self.assertEqual(result['status'], 'saved')
                decision = json.loads(self.repo.written[-1][1][3])
                self.assertEqual(decision['evidence'], '')
                self.assertEqual(decision['category'], category)
                self.assertEqual(decision['method'], 'manual_review')

    def test_rejects_invalid_or_unverifiable_direction(self):
        for changes in ({'reason_code': 'D2'},
                        {'id': 'missing'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                review.save(self.repo, {**self.payload, **changes})
        self.assertEqual(self.repo.written, [])


if __name__ == '__main__':
    unittest.main()
