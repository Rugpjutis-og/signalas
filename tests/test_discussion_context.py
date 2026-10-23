import json
import unittest
from discussion_context import compact_records, DiscussionIndex
from live_data import fingerprint


class DiscussionTests(unittest.TestCase):
    def records(self, count):
        parent = {'source': 'test', 'id': 'p', 'kind': 'post', 'text': 'Original',
                  'published_at': '2026-10-23T09:00:00Z', 'media': [], 'sourceUrl': None}
        comments = [{'source': 'test', 'id': str(i), 'kind': 'comment', 'parent_id': 'p',
                     'text': 'Original comment ' + str(i), 'media': [], 'sourceUrl': None,
                     'parentSourceUrl': None, 'published_at': '2026-10-23T10:%02d:%02dZ' % (i//60, i%60)}
                    for i in range(count)]
        return [parent] + comments

    def test_compact_storage_grows_linearly_and_preserves_fingerprints(self):
        records = self.records(200)
        index = DiscussionIndex(records)
        legacy = [index.expand(r) for r in records]
        compact = compact_records(legacy)
        rebuilt = DiscussionIndex(compact)
        self.assertEqual([fingerprint(r) for r in legacy], [fingerprint(rebuilt.expand(r)) for r in compact])
        self.assertTrue(all('conversation_context' not in r for r in compact))
        self.assertLess(len(json.dumps(self.records(200))), 2.1 * len(json.dumps(self.records(100))))
        self.assertLess(len(json.dumps(compact)), len(json.dumps(legacy)) / 10)

    def test_only_earlier_comments_and_own_media(self):
        records = self.records(3)
        records[0]['media'] = [{'kind': 'image', 'originalUrl': 'https://test/provided.jpg'}]
        unit = DiscussionIndex(records).expand(records[2])
        self.assertEqual([r['id'] for r in unit['conversation_context']], ['0'])
        self.assertEqual(unit['media'], [])
        self.assertTrue(unit['parent_post']['media'])

    def test_missing_imported_context_is_not_discarded(self):
        records = self.records(1)
        records[1]['conversation_context'] = [{'id': 'not-in-packet', 'text': 'Original context'}]
        compact = compact_records(records)
        self.assertEqual(DiscussionIndex(compact).expand(compact[1])['conversation_context'], records[1]['conversation_context'])


if __name__ == '__main__': unittest.main()
