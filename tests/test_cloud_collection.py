import copy
import json
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock,patch
from urllib.parse import urlsplit,parse_qs

import cloud_collection as cc
from cloud_repository import Repository
from diaspora_client import DiasporaRequestError


class Memory:
    def __init__(self):
        self.db={};self.values={};self.staged={};self.live={'old':{'text':'last good'}};self.snapshots=[]
    def read(self,name,default=None):return copy.deepcopy(self.db.get(name,default))
    def checkpoint(self,repo,state,changed=()):
        self.db[cc.STATE]=copy.deepcopy(state)
        for u in changed:self.staged[(u['source'],u['id'])]=copy.deepcopy(u)
    def prior(self,repo,entries,source):
        ids={e['guid'] for e in entries}
        return {'records':[u for u in self.live.values() if u.get('id') in ids or u.get('parent_id') in ids]}
    def finish(self,repo,state):
        if state['entries'] and not state['record_keys']:raise DiasporaRequestError('source_details_unavailable',404)
        self.live.update({u['id']:u for u in self.staged.values()});self.staged={}
        self.snapshots.append(copy.deepcopy(state));self.db[cc.STATE]={'status':'complete'}
        return {'status':'ok','collected_at':cc.now()}


class Client:
    base='https://example.org';username='test'
    def __init__(self):
        date=datetime(2026,10,24,12,tzinfo=timezone.utc)
        self.posts=[{'id':i,'guid':'p'+str(i),'created_at':(date-timedelta(seconds=i*2)).isoformat()} for i in range(34)]
        self.calls=[];self.details=[];self.logins=0;self.fail=False
    def login(self):self.logins+=1
    def json(self,path):
        self.calls.append(path)
        if self.fail:self.fail=False;raise DiasporaRequestError('source_http',503,'feed')
        if path=='/u/test':return {'guid':'person','is_own_profile':True}
        address=urlsplit(path);cursor=parse_qs(address.query).get('max_time')
        rows=self.posts[:33] if address.path=='/stream.json' else self.posts[:5]+self.posts[33:]
        if cursor:rows=[r for r in rows if datetime.fromisoformat(r['created_at']).timestamp()<int(cursor[0])]
        return rows[:15]
    def collect_entries(self,batch,**kwargs):
        rows=[]
        for e in batch:
            self.details.append(e['guid'])
            rows.extend([{'source':'example.org','id':e['guid'],'kind':'post','text':'new',
                          'published_at':e['created_at'],'media':[]},
                         {'source':'example.org','id':'c'+e['guid'],'parent_id':e['guid'],'kind':'comment',
                          'text':'comment','published_at':e['created_at'],'media':[]}])
        return {'records':rows,'collection_stats':{'not_modified':0,'unavailable_details':0}}


class CollectionTests(unittest.TestCase):
    def clock(self):
        value=[0]
        def tick():value[0]+=15;return value[0]
        return tick
    def run_collection(self,db,client):
        for _ in range(30):
            result=cc.run_step(db,client,monotonic=self.clock())
            if result['status']=='ok':return result
            self.assertEqual(db.live,{'old':{'text':'last good'}},'partial runs must not alter published content')
        self.fail('collection did not finish')
    def test_resume_all_pages_all_details_no_limit_or_duplicate_units(self):
        db=Memory();client=Client()
        with patch.object(cc,'checkpoint',side_effect=db.checkpoint),patch.object(cc,'previous',side_effect=db.prior),patch.object(cc,'finish',side_effect=db.finish):
            self.run_collection(db,client)
        snapshot=db.snapshots[0]
        self.assertGreater(client.logins,1,'must resume across independent invocations')
        self.assertEqual(len(snapshot['entries']),34)
        self.assertEqual(len(snapshot['record_keys']),68)
        self.assertEqual(snapshot['counts'],{'feed':33,'profile':6})
        self.assertEqual(snapshot['pages'],{'feed':3,'profile':1})
        self.assertEqual(len(client.details),len(set(client.details)))
        self.assertEqual(len(client.details),34)
        self.assertFalse(db.staged)
    def test_network_error_keeps_checkpoint_and_last_good_snapshot(self):
        db=Memory();client=Client();client.fail=True
        with patch.object(cc,'checkpoint',side_effect=db.checkpoint),patch.object(cc,'previous',side_effect=db.prior),patch.object(cc,'finish',side_effect=db.finish):
            with self.assertRaises(DiasporaRequestError):cc.run_step(db,client,monotonic=self.clock())
            run=db.db[cc.STATE]['run_id'];db.db[cc.STATE]['status']='error'
            self.assertEqual(db.live,{'old':{'text':'last good'}})
            self.run_collection(db,client)
        self.assertEqual(db.snapshots[0]['run_id'],run)
    def test_interrupted_invocation_resumes_saved_detail_cursor(self):
        db=Memory();client=Client();crashed=[False]
        def checkpoint(repo,state,changed=()):
            db.checkpoint(repo,state,changed)
            if state['detail_cursor']==4 and not crashed[0]:
                crashed[0]=True;raise TimeoutError('synthetic hard interruption after commit')
        with patch.object(cc,'checkpoint',side_effect=checkpoint),patch.object(cc,'previous',side_effect=db.prior),patch.object(cc,'finish',side_effect=db.finish):
            for _ in range(10):
                try:cc.run_step(db,client,monotonic=self.clock())
                except TimeoutError:break
            self.assertTrue(crashed[0]);self.assertEqual(db.db[cc.STATE]['detail_cursor'],4)
            self.run_collection(db,client)
        self.assertEqual(len(client.details),34,'completed batches must not be read again')
    def test_changed_bodies_and_checkpoint_share_transaction_and_publish_is_atomic(self):
        repo=Repository({'SIGNALAS_DATABASE_URL':'unused'})
        state={'run_id':'run','entries':[],'record_keys':[],'source':'example.org',
            'pages':{'feed':1,'profile':1},'counts':{'feed':0,'profile':0},'post_count':0,
            'comment_count':0,'not_modified':0,'unavailable_details':0}
        with patch.object(cc,'query',return_value={'results':[]}) as query:
            cc.checkpoint(repo,state,[{'source':'example.org','id':'one','text':'compact'}])
            batch=query.call_args.args[1]
            self.assertEqual(len(batch),2)
            self.assertNotIn('signalas_content',batch[0]['query'])
            self.assertIn('collection-stage/run/',batch[0]['params'][1])
            cc.finish(repo,state)
            publish=query.call_args.args[1]
            self.assertIn('signalas_content',publish[0]['query'])
            self.assertIn('signalas_fetches',publish[1]['query'])
            self.assertTrue(publish[2]['query'].startswith('DELETE FROM signalas_state'))
            self.assertEqual(publish[2]['params'][1],'collection-stage/run/%')
            self.assertEqual(repo.values[cc.STATE]['status'],'complete')
    def test_entire_missing_batch_can_advance_but_full_missing_collection_cannot_publish(self):
        from diaspora_client import DiasporaClient
        client=DiasporaClient('https://example.org','test','synthetic')
        client.json=Mock(side_effect=DiasporaRequestError('source_http',404))
        entries=[{'id':i,'guid':'gone'+str(i)} for i in range(4)]
        packet=client.collect_entries(entries,workers=1,conditional=False,allow_empty=True)
        self.assertEqual(packet['records'],[])
        self.assertEqual(packet['collection_stats']['unavailable_details'],4)
        with self.assertRaises(DiasporaRequestError):
            client.collect_entries(entries,workers=1,conditional=False)

    def test_all_unavailable_details_cannot_publish_empty_replacement(self):
        with self.assertRaises(DiasporaRequestError):
            cc.finish(Mock(),{'entries':[{'guid':'gone'}],'record_keys':[]})

    def test_cutoff_keeps_earlier_units_and_discards_later_comments(self):
        db=Memory();client=Client()
        # Include only the last 14 posts at the first timestamp boundary.
        cutoff=client.posts[20]['created_at']
        db.db['collection-cutoff.json']={'published_until':cutoff}
        original=client.collect_entries
        def details(batch,**kwargs):
            packet=original(batch,**kwargs)
            packet['records'].append({'source':'example.org','id':'late','kind':'comment',
                'parent_id':batch[0]['guid'],'published_at':'2026-10-25T15:00:00Z','text':'later'})
            return packet
        client.collect_entries=details
        with patch.object(cc.cutoff_policy,'retained',return_value=[{'source':'example.org','id':'retained','kind':'post'}]), \
             patch.object(cc,'checkpoint',side_effect=db.checkpoint),patch.object(cc,'previous',side_effect=db.prior),patch.object(cc,'finish',side_effect=db.finish):
            self.run_collection(db,client)
        snapshot=db.snapshots[0]
        self.assertTrue(all(datetime.fromisoformat(e['created_at'])<=datetime.fromisoformat(cutoff) for e in snapshot['entries']))
        self.assertTrue(any(r['id']=='retained' for r in snapshot['record_keys']))
        self.assertFalse(any(r['id']=='late' for r in snapshot['record_keys']))
        self.assertEqual(len(client.details),14)
