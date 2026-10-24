import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta
import background_auth as auth
import background_tick
import cloud_api


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


class BackgroundAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.key=Path(cls.temp.name)/'key.pem'
        subprocess.run(['openssl','genrsa','-out',str(cls.key),'2048'],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        modulus=subprocess.check_output(['openssl','rsa','-in',str(cls.key),'-noout','-modulus'],
                                        stderr=subprocess.DEVNULL).decode().strip().split('=',1)[1]
        cls.jwks={'keys':[{'kid':'test-key','kty':'RSA','use':'sig','alg':'RS256',
                          'n':b64(bytes.fromhex(modulus)),'e':b64((65537).to_bytes(3,'big'))}]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def token(self, overrides=None):
        claims={'iss':auth.ISSUER,'aud':auth.AUDIENCE,'repository':auth.REPOSITORY,
                'repository_id':auth.REPOSITORY_ID,'ref':'refs/heads/main',
                'workflow_ref':auth.WORKFLOW_REF,'event_name':'schedule','iat':1000,'exp':1300}
        claims.update(overrides or {})
        message=b64(json.dumps({'alg':'RS256','kid':'test-key'}).encode())+'.'+b64(json.dumps(claims).encode())
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(message.encode());temp.flush()
            signature=subprocess.check_output(['openssl','dgst','-sha256','-sign',str(self.key),temp.name])
        return 'Bearer '+message+'.'+b64(signature)

    def test_signature_and_immutable_claims(self):
        verify=lambda h:auth.verified_claims(h,now=1100,fetch=lambda:self.jwks)
        good=self.token()
        self.assertEqual(verify(good)['repository_id'],auth.REPOSITORY_ID)
        tampered=good[:-1]+('B' if good[-1] != 'B' else 'A')
        self.assertIsNone(verify(tampered))
        for changes in ({'repository_id':'1'},{'ref':'refs/heads/other'},
                        {'workflow_ref':'another'},{'aud':'another'},{'event_name':'pull_request'},
                        {'exp':1100},{'iat':500}):
            self.assertIsNone(verify(self.token(changes)),changes)
        self.assertIsNone(auth.verified_claims('Bearer invalid',now=1100,fetch=lambda:self.jwks))
        self.assertIsNone(auth.verified_claims(good,now=1100,fetch=lambda:{'keys':[]}))

    def test_background_route_denies_unknown_caller_before_database(self):
        handler=cloud_api.Handler.__new__(cloud_api.Handler)
        handler.path='/api/background/tick';handler.headers={'Authorization':'Bearer invalid'}
        handler.send=Mock()
        with patch('cloud_api.Repository') as repo,patch.dict('os.environ',{'SIGNALAS_ACCESS_PASSWORD':'a-long-private-password'}):
            handler.dispatch('GET')
        self.assertEqual(handler.send.call_args.args[1],401)
        repo.assert_not_called()


class BackgroundTickTests(unittest.TestCase):
    def setUp(self):
        self.db={}
        self.repo=Mock()
        self.repo.read=lambda key,default=None:self.db.get(key,default)
        self.repo.write=lambda key,value:self.db.update({key:value})
        self.current=datetime(2026,10,23,10,tzinfo=timezone.utc)
        self.clock=lambda:self.current
        self.monotonic=lambda:0

    def test_hourly_collection_and_queue_progress_without_browser(self):
        self.repo.collect.return_value={'status':'ok','collected_at':self.current.isoformat()}
        states=[{'status':'pending','remaining':1},{'status':'complete','remaining':0}]
        def work(_, **kwargs):
            state=states.pop(0);self.db['analysis-job.json']=state;return state
        self.db['analysis-job.json']={'status':'pending','remaining':2}
        with patch.object(background_tick,'step',side_effect=work) as run:
            result=background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
        self.assertEqual(result['processed'],2);self.assertEqual(result['collection'],'ok')
        self.assertEqual(result['analysis'],'complete');self.repo.collect.assert_called_once_with(reset_analysis_error=False)
        self.current+=timedelta(minutes=5)
        background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
        self.repo.collect.assert_called_once()
        self.current+=timedelta(minutes=55)
        background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
        self.assertEqual(self.repo.collect.call_count,2)

    def test_existing_short_deadline_adopts_hourly_cadence(self):
        self.db['background-schedule.json'] = {
            'last_success_at': self.current.isoformat(),
            'next_collection_at': (self.current + timedelta(minutes=15)).isoformat()}
        self.db['analysis-job.json'] = {'status': 'complete', 'remaining': 0}
        self.repo.collect.return_value = {'status': 'ok', 'collected_at': self.current.isoformat()}
        self.current += timedelta(minutes=59)
        background_tick.tick(self.repo, clock=self.clock, monotonic=self.monotonic)
        self.repo.collect.assert_not_called()
        self.current += timedelta(minutes=1)
        background_tick.tick(self.repo, clock=self.clock, monotonic=self.monotonic)
        self.repo.collect.assert_called_once_with(reset_analysis_error=False)
        self.assertEqual(self.db['background-schedule.json']['next_collection_at'],
                         (self.current + timedelta(hours=1)).isoformat())

    def test_open_app_services_overdue_collection_before_more_analysis(self):
        from cloud_analysis import drain
        self.db['background-schedule.json']={'next_collection_at':'2026-01-01T00:00:00Z'}
        self.db['analysis-job.json']={'status':'pending','remaining':5}
        with patch.object(background_tick,'tick') as tick, patch('cloud_analysis.step') as paid:
            result=drain(self.repo,monotonic=self.monotonic)
        tick.assert_called_once()
        paid.assert_not_called()
        self.assertEqual(result['remaining'],5)

    def test_errors_stop_paid_calls_and_collection_failure_backoff(self):
        self.repo.collect.side_effect=ValueError('private source error')
        self.db['analysis-job.json']={'status':'error','reason':'api_quota','remaining':10}
        with patch.object(background_tick,'step') as run:
            result=background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
            self.assertEqual(result['status'],'error');run.assert_not_called()
            self.current+=timedelta(minutes=5)
            later=background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
            self.assertEqual(self.repo.collect.call_count,1)
            self.assertEqual(later['status'],'paused')

    def test_busy_analysis_yields_to_collection_at_next_tick(self):
        self.repo.collect.return_value = {'status': 'already_running'}
        self.db['analysis-job.json'] = {'status': 'running', 'remaining': 10}
        with patch.object(background_tick, 'step') as paid:
            result = background_tick.tick(self.repo, clock=self.clock, monotonic=self.monotonic)
        self.assertEqual(result['collection'], 'already_running')
        self.assertEqual(self.db['background-schedule.json']['next_collection_at'], self.current.isoformat())
        self.assertIn('collection_waiting_until', self.db['background-schedule.json'])
        paid.assert_not_called()

    def test_provider_error_retries_after_scheduled_collection_only(self):
        self.db['analysis-job.json']={'status':'error','reason':'api_access','remaining':2}
        self.db['background-schedule.json']={'next_collection_at':(self.current+timedelta(minutes=5)).isoformat()}
        self.repo.collect.return_value={'status':'ok','collected_at':self.current.isoformat()}
        def requeue(_):
            state={'status':'pending','remaining':2}
            self.db['analysis-job.json']=state
            return state
        def work(_, **kwargs):
            state={'status':'complete','remaining':0}
            self.db['analysis-job.json']=state
            return state
        with patch.object(background_tick,'enqueue',side_effect=requeue) as enqueue, patch.object(background_tick,'step',side_effect=work) as step:
            self.assertEqual(background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)['status'],'paused')
            enqueue.assert_not_called();step.assert_not_called()
            self.current+=timedelta(minutes=5)
            outcome=background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
        self.assertEqual(outcome['status'],'ok')
        self.assertEqual(outcome['analysis'],'complete')
        enqueue.assert_called_once_with(self.repo)
        step.assert_called_once_with(self.repo, deadline=235, monotonic=self.monotonic)

    def test_capacity_retries_after_cooldown(self):
        self.db['analysis-job.json']={'status':'error','reason':'api_capacity','remaining':2,
                                      'updated_at':self.current.isoformat(),'processing_tier':'default'}
        self.db['background-schedule.json']={'next_collection_at':(self.current+timedelta(hours=2)).isoformat()}
        with patch.object(background_tick,'enqueue',return_value={'status':'pending','remaining':2}) as enqueue, \
             patch.object(background_tick,'step',return_value={'status':'complete','remaining':0}) as paid:
            self.assertEqual(background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)['status'],'paused')
            self.current+=timedelta(minutes=15)
            self.assertEqual(background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)['status'],'ok')
        enqueue.assert_called_once_with(self.repo)
        paid.assert_called_once_with(self.repo, deadline=235, monotonic=self.monotonic)
        self.repo.collect.assert_not_called()

    def test_api_request_rate_limit_retries_after_cooldown(self):
        self.db['analysis-job.json']={'status':'error','reason':'api_rate_limit','remaining':1044,
                                      'updated_at':self.current.isoformat(),'processing_tier':'default'}
        self.db['background-schedule.json']={'next_collection_at':(self.current+timedelta(hours=2)).isoformat()}
        with patch.object(background_tick,'enqueue',return_value={'status':'pending','remaining':1044}) as enqueue, \
             patch.object(background_tick,'step',return_value={'status':'complete','remaining':0}) as paid:
            self.assertEqual(background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)['status'],'paused')
            self.current+=timedelta(minutes=15)
            self.assertEqual(background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)['status'],'paused')
            self.current+=timedelta(minutes=45)
            self.assertEqual(background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)['status'],'ok')
        enqueue.assert_called_once_with(self.repo)
        paid.assert_called_once_with(self.repo, deadline=235, monotonic=self.monotonic)
        self.repo.collect.assert_not_called()

    def test_switch_from_flex_to_standard_resumes_without_old_cooldown(self):
        self.db['analysis-job.json']={'status':'error','reason':'api_rate_limit','remaining':1044,
                                      'updated_at':self.current.isoformat(),'processing_tier':'flex'}
        self.db['background-schedule.json']={'next_collection_at':(self.current+timedelta(hours=2)).isoformat()}
        with patch.object(background_tick,'enqueue',return_value={'status':'pending','remaining':1044}) as enqueue, \
             patch.object(background_tick,'step',return_value={'status':'complete','remaining':0}) as paid:
            self.assertEqual(background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)['status'],'ok')
        enqueue.assert_called_once_with(self.repo)
        paid.assert_called_once_with(self.repo, deadline=235, monotonic=self.monotonic)
        self.repo.collect.assert_not_called()

    def test_repeated_rate_limit_remains_paused_without_new_failure_alert(self):
        self.db['analysis-job.json']={'status':'error','reason':'api_rate_limit','remaining':1044,
                                      'updated_at':self.current.isoformat(),'processing_tier':'default'}
        self.db['background-schedule.json']={'next_collection_at':(self.current+timedelta(hours=2)).isoformat()}
        self.current+=timedelta(hours=1)
        with patch.object(background_tick,'enqueue',return_value={'status':'pending','remaining':1044}), \
             patch.object(background_tick,'step',return_value={'status':'error','reason':'api_rate_limit','remaining':1044}):
            outcome=background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
        self.assertEqual(outcome['status'],'paused')

    def test_legacy_validation_failure_advances_without_new_collection(self):
        self.db['analysis-job.json']={'status':'error','reason':'analysis_validation','remaining':2}
        self.db['background-schedule.json']={'next_collection_at':(self.current+timedelta(hours=1)).isoformat()}
        def recover(_):
            self.db['analysis-job.json']={'status':'pending','remaining':1}
            return self.db['analysis-job.json']
        with patch.object(background_tick,'recover_validation_failure',side_effect=recover) as fallback, patch.object(background_tick,'step',return_value={'status':'complete','remaining':0}) as paid:
            result=background_tick.tick(self.repo,clock=self.clock,monotonic=self.monotonic)
        self.assertEqual(result['status'],'ok')
        fallback.assert_called_once_with(self.repo)
        paid.assert_called_once_with(self.repo, deadline=235, monotonic=self.monotonic)
        self.repo.collect.assert_not_called()

if __name__=='__main__':unittest.main()
