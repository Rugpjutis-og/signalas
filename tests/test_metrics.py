import unittest
from copy import deepcopy

from metrics import (aggregate_engagement, audience_ids, author_median, content_activity,
                     interaction_counts, metrics_context, post_engagement, share)


def membership(size, exercise='A'):
    return {'exercise_id': exercise, 'complete': True,
            'assigned_account_ids': ['member-%s' % i for i in range(size)],
            'valid_from': '2026-10-13T00:00:00Z', 'valid_until': '2026-10-20T00:00:00Z'}


def post(id='post-1', accounts=('member-1',), **changes):
    return dict({'id': id, 'source': 'exercise', 'exercise_id': 'A', 'kind': 'post',
                 'published_at': '2026-10-19T12:00:00Z', 'author_id': 'member-0',
                 'visibility': 'all_assigned', 'interactions_complete': True,
                 'interactions': [{'id': '%s-%s' % (id, i), 'account_id': actor, 'kind': 'comment'}
                                  for i, actor in enumerate(accounts)]}, **changes)


class MetricsTests(unittest.TestCase):
    def test_requested_shares(self):
        for size, expected in ((100, 5), (250, 2), (500, 1)):
            with self.subTest(size=size):
                result = share(set(range(5)), set(range(size)))
                self.assertEqual(result['percent'], expected)

    def test_many_comments_are_not_many_people(self):
        # 251 assigned accounts: author excluded => 250 other eligible members.
        p = post(accounts=['member-%s' % (i % 5 + 1) for i in range(100)])
        self.assertEqual(interaction_counts([p], 'A'), {'status': 'ok', 'comments': 100, 'likes': 0, 'shares': 0})
        result = post_engagement(p, membership(251))
        self.assertEqual((result['unique_engaged'], result['audience'], result['percent']), (5, 250, 2))
        # Repeated delivery of the same post/actions does not inflate counts.
        self.assertEqual(interaction_counts([p, p], 'A')['comments'], 100)

    def test_cross_action_and_cross_post_deduplication(self):
        p = post(accounts=['member-1', 'member-1', 'member-0', 'outsider'])
        p['interactions'][1]['kind'] = 'like'
        self.assertEqual(post_engagement(p, membership(101))['unique_engaged'], 1)
        other = post('post-2', ['member-1', 'member-2'])
        self.assertEqual(aggregate_engagement([p, other], membership(101))['percent'], 2)
        actions = interaction_counts([p], 'A')
        self.assertEqual((actions['comments'], actions['likes'], actions['shares']), (3, 1, 0))

    def test_restricted_visibility_and_author_exclusion(self):
        p = post(accounts=['member-0', 'member-1', 'member-1', 'member-50'],
                 visibility='restricted', visible_account_ids=['member-0', 'member-1', 'member-2'])
        result = post_engagement(p, membership(100))
        self.assertEqual((result['audience'], result['unique_engaged'], result['percent']), (2, 1, 50))
        p.pop('visible_account_ids')
        self.assertEqual(post_engagement(p, membership(100))['status'], 'missing_data')

    def test_union_of_restricted_audiences(self):
        a = post(visibility='restricted', visible_account_ids=['member-0', 'member-1', 'member-2'])
        b = post('post-2', ['member-2'], visibility='restricted', visible_account_ids=['member-0', 'member-2', 'member-3'])
        result = aggregate_engagement([a, b], membership(100))
        self.assertEqual((result['unique_engaged'], result['audience']), (2, 3))

    def test_inactive_assigned_members_stay_in_denominator(self):
        snapshot = membership(251)
        snapshot['active_account_ids'] = ['member-0', 'member-1']
        snapshot['global_registered_count'] = 10000
        self.assertEqual(post_engagement(post(), snapshot)['audience'], 250)

    def test_zero_unknown_and_incomplete_audiences(self):
        self.assertIsNone(share([], [])['percent'])
        self.assertEqual(share([], [])['status'], 'zero_audience')
        self.assertIsNone(post_engagement(post(), None)['percent'])
        self.assertIsNone(audience_ids(membership(100), None))
        incomplete = membership(100)
        incomplete['complete'] = False
        self.assertIsNone(post_engagement(post(), incomplete)['percent'])
        self.assertEqual(post_engagement(post(), membership(0))['status'], 'zero_audience')
        self.assertIsNone(post_engagement(post(interactions_complete=False), membership(100))['percent'])
        self.assertIsNone(post_engagement(post(interactions=None), membership(100))['percent'])
        self.assertIsNone(interaction_counts([post(interactions=None)], 'A')['comments'])

    def test_exercise_switch_and_historical_snapshots(self):
        old = post(accounts=['member-%s' % i for i in range(1, 6)])
        a, b = membership(101), membership(501, 'B')
        self.assertEqual(post_engagement(old, a)['percent'], 5)
        self.assertIsNone(post_engagement(old, b)['percent'])
        self.assertEqual(post_engagement(dict(old, exercise_id='B'), b)['percent'], 1)
        self.assertEqual(post_engagement(old, a)['percent'], 5)
        new_snapshot = deepcopy(a)
        new_snapshot['valid_from'] = '2026-10-20T00:00:00Z'
        new_snapshot['valid_until'] = '2026-10-21T00:00:00Z'
        for snapshot in (new_snapshot, dict(a, valid_from=None), dict(a, valid_until='bad')):
            self.assertIsNone(post_engagement(old, snapshot)['percent'])
        self.assertIsNone(post_engagement(dict(old, published_at=None), a)['percent'])

    def test_absolute_activity_and_per_100_can_exceed_100(self):
        units = [post(str(i), kind='comment') for i in range(100)]
        result = content_activity(units + [units[0]], membership(50), 'A')
        self.assertEqual((result['posts'], result['comments'], result['total_content']), (0, 100, 100))
        self.assertEqual(result['content_units_per_100_members'], 200)
        self.assertIsNone(content_activity(units, None, 'A')['content_units_per_100_members'])
        self.assertIsNone(content_activity(units, membership(0), 'A')['content_units_per_100_members'])
        self.assertIsNone(content_activity([post(published_at=None)], membership(50), 'A')['content_units_per_100_members'])
        self.assertIsNone(content_activity(units, membership(50, 'B'), 'A')['content_units_per_100_members'])

    def test_author_median_preserves_selected_active_post_set(self):
        posts = [post('one', ['member-1']), post('two', ['member-%s' % i for i in range(1, 10)])]
        result = author_median(posts + [posts[0], post('comment', kind='comment'), post('foreign', author_id='member-2')], membership(101), 'member-0')
        self.assertEqual(result['active_authored_posts'], 2)
        self.assertEqual(result['median_engagement_percent'], 5)
        self.assertIsNone(author_median([post(interactions=None)] + posts, membership(101), 'member-0')['median_engagement_percent'])

    def test_api_context_does_not_guess_audience(self):
        context = metrics_context()
        self.assertIsNone(context['exercise_id'])
        self.assertEqual(context['audience']['status'], 'missing')
        self.assertIsNone(context['audience']['count'])


if __name__ == '__main__':
    unittest.main()
