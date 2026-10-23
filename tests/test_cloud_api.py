import hashlib
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch, Mock

import cloud_api
from cloud_repository import Repository


class CloudApiTests(unittest.TestCase):
    def test_signed_session_expiration_and_tampering(self):
        token = cloud_api.session_token('a-long-private-password', now=1000)
        self.assertTrue(cloud_api.valid_session(token, 'a-long-private-password', now=1001))
        self.assertFalse(cloud_api.valid_session(token, 'wrong', now=1001))
        self.assertFalse(cloud_api.valid_session(token, 'a-long-private-password', now=50000))
        self.assertFalse(cloud_api.valid_session(token+'bad', 'a-long-private-password', now=1001))

    def test_login_gate_origin_csrf_and_database_only_collection(self):
        password='test-long-access-password'
        repository=Mock()
        repository.sql.return_value={'rows':[['1']]}
        repository.collect.return_value={'status':'ok','posts':15,'comments':115}
        with patch.dict(os.environ, {'SIGNALAS_ACCESS_PASSWORD':password}, clear=True), patch.object(cloud_api, 'Repository', return_value=repository):
            with ThreadingHTTPServer(('127.0.0.1',0),cloud_api.Handler) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                base='http://127.0.0.1:'+str(server.server_port)
                try:
                    for path in ['/api/dashboard/bootstrap','/api/media/image','/api/auth/login','/api/analysis/status','/api/analysis/continue']:
                        with self.assertRaises(HTTPError) as error:urlopen(base+path)
                        self.assertEqual(error.exception.code,401)
                    repository.initialize.assert_not_called()
                    request=Request(base+'/api/auth/login',data=json.dumps({'password':password}).encode(),headers={'Origin':'https://evil.test'})
                    with self.assertRaises(HTTPError) as error:urlopen(request)
                    self.assertEqual(error.exception.code,403)
                    request=Request(base+'/api/auth/login',data=json.dumps({'password':password}).encode(),headers={'Origin':'https://signalas-ecru.vercel.app'})
                    with urlopen(request) as response:
                        cookie=response.headers['Set-Cookie'];csrf=json.load(response)['csrf']
                    self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=Strict',cookie)
                    headers={'Origin':'https://signalas-ecru.vercel.app','Cookie':cookie.split(';')[0]}
                    with self.assertRaises(HTTPError) as error:urlopen(Request(base+'/api/collection/refresh',data=b'',headers=headers))
                    self.assertEqual(error.exception.code,403)
                    repository.collect.assert_not_called()
                    headers['X-Signalas-CSRF']=csrf
                    with urlopen(Request(base+'/api/collection/refresh',data=b'',headers=headers)) as response:
                        self.assertEqual(json.load(response)['posts'],15)
                    repository.collect.assert_called_once()
                    with patch('cloud_analysis.step', return_value={'status':'complete','remaining':0}) as step:
                        with self.assertRaises(HTTPError) as denied:
                            urlopen(Request(base+'/api/analysis/continue',data=b'',headers={'Origin':'https://signalas-ecru.vercel.app','Cookie':cookie.split(';')[0]}))
                        self.assertEqual(denied.exception.code,403);step.assert_not_called()
                        with urlopen(Request(base+'/api/analysis/continue',data=b'',headers=headers)) as response:
                            self.assertEqual(json.load(response)['status'],'complete')
                        step.assert_called_once()
                finally:server.shutdown();thread.join()

    def test_configuration_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            handler=cloud_api.Handler.__new__(cloud_api.Handler);handler.send=Mock()
            handler.dispatch('GET')
            self.assertEqual(handler.send.call_args.args[1],503)

    def test_context_immutable_on_conflicting_save(self):
        repo=Repository({});saved={'initialSituation':'Original','confirmedFacts':'Confirmed','nameMappings':[]}
        repo.sql=Mock(side_effect=[{'rows':[]},{'rows':[[json.dumps(saved)]]}])
        with self.assertRaises(ValueError):repo.save_context({'initialSituation':'Changed','confirmedFacts':'Changed'})
        self.assertNotIn('DO UPDATE',repo.sql.call_args_list[0].args[0])

    def test_cloud_failure_releases_lease_keeps_previous_snapshot(self):
        repo=Repository({'DIASPORA_USERNAME':'test','DIASPORA_PASSWORD':'private'})
        repo.sql=Mock(return_value={'rows':[['owner']]});repo.write=Mock()
        with patch('diaspora_client.DiasporaClient',side_effect=ValueError('private password must not leak')):
            with self.assertRaisesRegex(ValueError,'Paskutinė sėkminga'):repo.collect()
        self.assertIn('DELETE FROM signalas_jobs',repo.sql.call_args.args[0])
        self.assertEqual(repo.write.call_args.args[1]['status'],'error')

if __name__=='__main__':unittest.main()
