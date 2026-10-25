import unittest
from zoneinfo import ZoneInfo
from datetime import datetime
from collection_cutoff import allows,cursor,records,packet


class CutoffTests(unittest.TestCase):
    cutoff='2026-10-25T12:00:00+02:00'

    def test_noon_vilnius_dst_boundary_is_1000_utc_and_inclusive(self):
        self.assertEqual(datetime(2026,10,25,12,tzinfo=ZoneInfo('Europe/Vilnius')).utcoffset().total_seconds(),7200)
        self.assertTrue(allows({'published_at':'2026-10-25T10:00:00Z'},self.cutoff))
        self.assertFalse(allows({'published_at':'2026-10-25T10:00:00.001Z'},self.cutoff))
        self.assertTrue(allows({'published_at':'2026-10-24T23:59:00Z'},self.cutoff))
        self.assertEqual(cursor(self.cutoff),int(datetime(2026,10,25,10,tzinfo=ZoneInfo('UTC')).timestamp())+1)

    def test_posts_comments_and_actions_are_filtered_without_modifying_originals(self):
        old={'source':'test','id':'p','kind':'post','published_at':'2026-10-25T09:00:00Z',
             'counters':{'comments':2,'likes':2,'shares':0},'interactions_complete':True,
             'interactions':[{'kind':'comment','published_at':'2026-10-25T09:59:00Z'},
                             {'kind':'comment','published_at':'2026-10-25T10:01:00Z'},
                             {'kind':'like','published_at':'2026-10-25T10:00:00Z'},
                             {'kind':'like','published_at':None}]}
        later={**old,'id':'after','published_at':'2026-10-25T10:00:01Z'}
        comment={'source':'test','id':'c','kind':'comment','parent_id':'p','published_at':'2026-10-25T09:59:00Z'}
        result=packet({'records':[old,later,comment]},self.cutoff)
        self.assertEqual([r['id'] for r in result['records']],['p','c'])
        self.assertEqual(result['records'][0]['counters'],{'comments':1,'likes':None,'shares':0})
        self.assertEqual(len(result['records'][0]['interactions']),2)
        self.assertEqual(old['counters']['comments'],2)
        self.assertEqual(len(old['interactions']),4)
        self.assertEqual((result['post_count'],result['comment_count']),(1,1))
        self.assertEqual(records(result['records'],self.cutoff),result['records'])

    def test_no_cutoff_preserves_existing_behavior_and_bad_timestamps_fail_closed(self):
        row={'id':'test'}
        self.assertEqual(records([row],None),[row])
        with self.assertRaises(ValueError):allows({'published_at':'2026-10-25T10:00:00'},self.cutoff)

    def test_bounded_analysis_cannot_return_a_queued_post_after_cutoff(self):
        import json
        from unittest.mock import Mock
        from cloud_repository import Repository
        earlier={'source':'test','id':'before','kind':'post','text':'before','published_at':'2026-10-25T10:00:00Z'}
        later={**earlier,'id':'after','published_at':'2026-10-25T10:00:00.001Z'}
        repo=Repository({});repo.values['collection-cutoff.json']={'published_until':self.cutoff}
        def sql(statement,params=None):
            if "SELECT packet->>'storage_version'" in statement:return {'rows':[['2']]}
            return {'rows':[[json.dumps([earlier,later]),2]]}
        repo.sql=Mock(side_effect=sql)
        result=repo.analysis_units([['test','before'],['test','after']])
        self.assertEqual(set(result),{('test','before')})

    def test_latest_projection_is_cached_without_rebuilding_discussion_each_read(self):
        from cloud_repository import Repository
        repo=Repository({});repo.values['collection-cutoff.json']={'published_until':self.cutoff}
        repo.packet={'records':[{'source':'test','id':'before','kind':'post','published_at':'2026-10-25T10:00:00Z'}]}
        first=repo.latest()
        self.assertIs(repo.latest(),first)
        self.assertIs(repo.latest()['records'],first['records'])
