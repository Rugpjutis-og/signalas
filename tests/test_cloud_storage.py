import unittest
from unittest.mock import patch
import cloud_storage as cloud

URL = 'postgresql://test:local-secret@ep-test-123.eu-central-1.aws.neon.tech/neondb?sslmode=require'


class CloudTests(unittest.TestCase):
    def test_only_neon_https_no_redirects(self):
        self.assertEqual(cloud.endpoint(URL), 'https://api.eu-central-1.aws.neon.tech/sql')
        for value in ['postgresql://u:p@evil.test/db', 'https://example.org', URL.replace(':local-secret', ''), URL.replace('/neondb?', '/?')]:
            with self.assertRaises(cloud.CloudStorageError):
                cloud.endpoint(value)
        self.assertIsNone(cloud.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test'))

    def test_retry_identity_parameters_and_atomic_writes(self):
        packet = {'collected_at': '2026-10-21T19:23:06Z', 'records': [{'id': 'one', 'text': "quote ' ; DROP TABLE x"}]}
        with patch.object(cloud, 'query', return_value={'results': [{}, {}]}) as q:
            cloud.sync(packet, URL, 'scope')
            first = q.call_args_list[-1].args[1]
            cloud.sync(packet, URL, 'scope')
            self.assertEqual(first, q.call_args_list[-1].args[1])
            self.assertEqual(len(first), 2)
            self.assertNotIn('DROP TABLE', first[1]['query'])
            self.assertIn('ON CONFLICT', first[1]['query'])
            self.assertIn('>= signalas_content.collected_at', first[1]['query'])

    def test_provider_errors_do_not_leak(self):
        with patch.object(cloud, 'build_opener', side_effect=RuntimeError(URL)):
            with self.assertRaises(cloud.CloudStorageError) as error:
                cloud.query(URL, [])
            self.assertNotIn('local-secret', str(error.exception))
            self.assertNotIn('postgresql', str(error.exception))

    def test_collection_survives_cloud_failure(self):
        import integrations
        config = {'SIGNALAS_DATABASE_URL': URL}
        with patch.object(integrations, 'settings', return_value=config), patch.object(integrations, 'DiasporaClient') as client, patch.object(integrations, 'save_packet', return_value={'status': 'ok'}), patch.object(cloud, 'sync', side_effect=cloud.CloudStorageError('cloud unavailable')):
            result = integrations.collect_sample()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['cloud_storage']['status'], 'error')

if __name__ == '__main__':
    unittest.main()
