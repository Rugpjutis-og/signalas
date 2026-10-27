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
        raise AssertionError('A single manual decision must not read the full source snapshot')

    def analysis_units(self, identities):
        identity = (self.unit['source'], self.unit['id'])
        return {identity: self.unit} if list(identity) in identities else {}

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
        self.assertEqual((result['source'], result['id']), ('pod.test', 'p1'))
        self.assertEqual(result['assessment']['category'], 'neutral')
        self.assertEqual(result['assessment']['status'], 'assessed')
        self.assertEqual(result['assessment']['reason_codes'], ['N1'])
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

    def test_reason_is_optional_and_previous_reasons_are_preserved_atomically(self):
        import json
        payload={k:v for k,v in self.payload.items() if k!='reason'}
        review.save(self.repo,payload)
        statement,params=self.repo.written[-1]
        self.assertIn('previous_reasons',statement)
        self.assertNotIn('DELETE',statement)
        self.assertIn('Rankiniu būdu patvirtinta',json.loads(params[3])['reason'])

    def test_direction_only_decisions_are_saved_without_inventing_a_code(self):
        import json
        for category in ('stabilizing', 'neutral', 'destabilizing'):
            with self.subTest(category=category):
                result = review.save(self.repo, {'source': 'pod.test', 'id': 'p1', 'category': category})
                decision = json.loads(self.repo.written[-1][1][3])
                self.assertEqual(result['status'], 'saved')
                self.assertEqual(decision['category'], category)
                self.assertIsNone(decision['reason_code'])
                self.assertEqual(result['assessment']['reason_codes'], [])
                self.assertTrue(review.applicable(decision, self.repo.unit, None))
                self.assertTrue(decision['reason'])

    def test_direction_only_still_rejects_invalid_category_and_legacy_code(self):
        for changes in ({'category': 'unknown'}, {'category': None}, {'category': []},
                        {'reason_code': []}, {'reason_code': 'D5'}):
            payload = {'source': 'pod.test', 'id': 'p1', 'category': 'neutral', **changes}
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                review.save(self.repo, payload)
        self.assertEqual(self.repo.written, [])

    def test_failed_commit_does_not_return_a_success_or_discard_prior_decision(self):
        from unittest.mock import Mock
        from cloud_storage import CloudStorageError
        previous = {'existing': 'decision'}
        self.repo.values[review.NAME] = previous
        self.repo.sql = Mock(side_effect=CloudStorageError())
        with self.assertRaises(CloudStorageError):
            review.save(self.repo, self.payload)
        self.assertIs(self.repo.values[review.NAME], previous)
