import math
import unittest

from metrics import timestamp
from platform_overview import AUTHOR_POLICY, adapt_diaspora_comment, adapt_diaspora_post, demo_report, report
from test_metrics import membership, post


class PlatformOverviewTests(unittest.TestCase):
    def make_post(self, id, author='member-0', actors=(), **changes):
        return post(id, actors, author_id=author, author_name=author, text='Originalus tekstas ' + id, is_demo=False, sourceUrl=None,
                    counter_scope='lifetime', comments_include_replies=True,
                    author_classification={'type':'person','verified':True,'provenance':'exercise_administrator'},
                    counters={'comments': len(actors), 'likes': 0, 'shares': 0}, media=[], **changes)

    def report(self, posts, snapshots=None):
        return report(posts, [membership(101)] if snapshots is None else snapshots, exercise_id='A',
                      start=timestamp('2026-10-13T00:00:00Z'), end=timestamp('2026-10-20T00:00:00Z'), mode='live')

    def active_posts(self, number=3, actors=10, **changes):
        return [self.make_post(str(i), actors=['member-%s' % k for k in range(1, actors+1)], **changes) for i in range(number)]

    def test_period_totals_count_unique_content_by_own_date(self):
        old=self.make_post('old',published_at='2026-10-12T23:59:59Z')
        current=self.make_post('current',published_at='2026-10-13T00:00:00Z')
        current['counters']['comments']=999
        comment=self.make_post('reply',kind='comment',published_at='2026-10-19T23:59:59Z')
        comment['parent_id']='old'
        share=self.make_post('share',kind='reshare')
        after=self.make_post('after',kind='comment',published_at='2026-10-20T00:00:00Z')
        foreign=self.make_post('foreign',exercise_id='B')
        result=self.report([old,current,current,comment,comment,share,after,foreign])
        self.assertEqual(result['totals']['posts'],2)
        self.assertEqual(result['totals']['comments'],1)
        self.assertEqual(self.report([])['totals']['posts'],0)
        self.assertEqual(self.report([])['totals']['comments'],0)

    def test_one_viral_post_is_not_enough(self):
        self.assertEqual(self.report(self.active_posts(1, 100))['authors']['items'], [])
        self.assertEqual(self.report(self.active_posts(2, 100))['authors']['items'], [])



    def test_comments_and_reshares_are_not_originals(self):
        posts = self.active_posts(1) + [self.make_post('c', kind='comment'), self.make_post('s', kind='reshare')]
        self.assertEqual(self.report(posts)['authors']['items'], [])


    def test_three_categories_all_content_and_replies(self):
        posts = [self.make_post(str(i), actors=['member-1'] * i) for i in range(1, 7)]
        # Comments_count includes direct comments and replies; all from one person.
        posts[0]['counters'] = {'comments': 20, 'likes': 30, 'shares': 10}
        posts[0]['narrative_id'] = None
        result = self.report(posts + [posts[0]])
        for category in result['categories']:
            self.assertLessEqual(len(category['items']), 3)
            self.assertEqual(category['items'][0]['id'], '1')
            self.assertEqual(category['items'][0]['text'], posts[0]['text'])
        self.assertEqual(result['categories'][0]['items'][0]['count'], 20)

    def test_missing_is_not_zero_and_partial_ranking_is_disclosed(self):
        p = self.make_post('zero')
        self.assertEqual(self.report([p])['categories'][1]['status'], 'empty')
        p['counters']['likes'] = None
        self.assertEqual(self.report([p])['categories'][1]['status'], 'missing_data')
        p['comments_include_replies'] = False
        self.assertEqual(self.report([p])['categories'][0]['status'], 'missing_data')
        q = self.make_post('known')
        q['counters']['likes'] = 2
        self.assertEqual(self.report([p, q])['categories'][1]['status'], 'partial')
        self.assertEqual(self.report([])['authors']['status'], 'empty')

    def test_period_boundaries_consistent_for_authors_and_categories(self):
        result = report([self.make_post('start', published_at='2026-10-19T00:00:00+03:00'),
                         self.make_post('before', published_at='2026-10-18T23:59:59+03:00'),
                         self.make_post('end', published_at='2026-10-20T00:00:00+03:00')],
                        [membership(101)], exercise_id='A', start=timestamp('2026-10-19T00:00:00+03:00'),
                        end=timestamp('2026-10-20T00:00:00+03:00'), mode='live')
        self.assertEqual(result['categories'][0]['status'], 'empty')
        self.assertEqual(result['authors']['items'], [])
        seven, one = demo_report(7), demo_report(1)
        self.assertGreater(len(seven['authors']['items']), len(one['authors']['items']))
        self.assertEqual(one['start'][:10], '2026-10-19')
        self.assertEqual(seven['counter_scope'], 'lifetime_for_posts_published_in_period')
        for period in (10, 7, 3, 1):
            r = demo_report(period)
            for c in r['categories']:
                self.assertTrue(all(timestamp(r['start']) <= timestamp(p['published_at']) < timestamp(r['end']) for p in c['items']))

    def test_original_url_and_adapter_do_not_guess_missing_fields(self):
        raw = {'guid': 'p-guid', 'post_type': 'Reshare', 'created_at': '2026-10-19T10:00:00Z', 'text': 'Originalus tekstas',
               'author': {'guid': 'author-guid', 'name': 'Autorius'},
               'interactions': {'comments_count': 2, 'comments': [{'guid': 'c1', 'author': {'guid': 'a'}},
                                                                {'guid': 'c2', 'author': {'guid': 'a'}, 'parent_id': 'c1'}]}}
        p = adapt_diaspora_post(raw, source='pod.test', exercise_id='A', interactions_complete=True)
        self.assertEqual((p['source'], p['id'], p['kind']), ('pod.test', 'p-guid', 'reshare'))
        self.assertIsNone(p['sourceUrl'])
        self.assertIsNone(p['visibility'])
        self.assertIsNone(p['counters']['likes'])
        self.assertFalse(p['interactions_complete'])
        self.assertEqual(p['counters']['comments'], 2)
        self.assertEqual(p['text'], raw['text'])
        p = adapt_diaspora_post(raw, source='pod.test', exercise_id='A', sourceUrl='https://pod.test/p/exact-from-api')
        self.assertEqual(p['sourceUrl'], 'https://pod.test/p/exact-from-api')
        c = adapt_diaspora_comment({'guid': 'c-guid', 'text': 'Komentaras'}, source='pod.test', exercise_id='A', parentSourceUrl=p['sourceUrl'])
        self.assertIsNone(c['sourceUrl'])
        self.assertEqual(c['parentSourceUrl'], p['sourceUrl'])
        self.assertEqual(c['kind'], 'comment')

    def test_policy_and_top_five_limit(self):
        self.assertEqual(AUTHOR_POLICY['min_original_posts'], 3)
        posts = []
        for i in range(6):
            posts += self.active_posts(3, 3, author='author-%s' % i)
            for p in posts[-3:]:
                p['id'] += '-%s' % i
        self.assertEqual(len(self.report(posts)['authors']['items']), 5)

    def test_adapter_uses_only_own_photos_and_preserves_ranking(self):
        photo = {'sizes': {'medium': 'https://pod.test/photo/small.jpg', 'raw': 'https://pod.test/photo/full.jpg'}}
        parent = {'guid': 'parent', 'post_type': 'StatusMessage', 'photos': [photo]}
        original = adapt_diaspora_post(parent, source='pod.test', exercise_id='A')
        self.assertEqual(len(original['media']), 1)
        comment = adapt_diaspora_comment({'guid': 'c', 'parent_post': parent}, source='pod.test', exercise_id='A')
        self.assertEqual(comment['media'], [])
        own_comment = adapt_diaspora_comment({'guid': 'c', 'photos': [photo]}, source='pod.test', exercise_id='A')
        self.assertEqual(own_comment['media'], original['media'])
        reshared = adapt_diaspora_post({'guid': 'r', 'post_type': 'Reshare', 'root': parent}, source='pod.test', exercise_id='A')
        self.assertEqual(reshared['media'], [])
        posts = self.active_posts()
        before = self.report(posts)
        for p in posts:
            p['media'] = original['media']
        after = self.report(posts)
        for key in ('score', 'unique_original_posts', 'received_comments', 'received_shares', 'authored_posts'):
            self.assertEqual(before['authors']['items'][0][key], after['authors']['items'][0][key])


if __name__ == '__main__':
    unittest.main()
