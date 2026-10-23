import unittest
import json
from urllib.error import HTTPError
from cloud_repository import Repository
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

    def test_manifests_and_changed_units_only_no_full_snapshot_copies(self):
        record = {'source': 'test', 'id': 'p', 'text': 'Original', 'kind': 'post'}
        packet = {'collected_at': '2026-10-23T10:00:00Z', 'records': [record]}
        previous = dict(packet, storage_version=2)
        with patch.object(cloud, 'query', return_value={'results': [{}, {}]}) as q:
            result = cloud.sync(packet, URL, 'scope', previous=previous)
            writes = q.call_args.args[1]
            manifest = json.loads(writes[0]['params'][3])
            self.assertNotIn('records', manifest)
            self.assertNotIn('Original', json.dumps(manifest))
            self.assertEqual(manifest['record_keys'], [{'source': 'test', 'id': 'p'}])
            self.assertEqual(json.loads(writes[1]['params'][2]), [])
            self.assertEqual(result['changed_records'], 0)
            changed = dict(packet, records=[dict(record, text='Edited')])
            result = cloud.sync(changed, URL, 'scope', previous=previous)
            self.assertEqual(len(json.loads(q.call_args.args[1][1]['params'][2])), 1)
            self.assertEqual(result['changed_records'], 1)

    def test_provider_errors_do_not_leak(self):
        with patch.object(cloud, 'build_opener', side_effect=RuntimeError(URL)):
            with self.assertRaises(cloud.CloudStorageError) as error:
                cloud.query(URL, [])
            self.assertNotIn('local-secret', str(error.exception))
            self.assertNotIn('postgresql', str(error.exception))

    def test_neon_quota_has_safe_specific_reason(self):
        with patch.object(cloud, 'build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('https://test', 402, 'private provider SQL', {}, None)
            with self.assertRaises(cloud.CloudStorageError) as failure:
                cloud.query(URL, [])
        self.assertEqual(failure.exception.reason, 'database_quota')
        self.assertNotIn('private', str(failure.exception))

    def test_health_does_not_download_source_snapshot(self):
        repo = Repository({})
        repo.sql = unittest.mock.Mock(return_value={'rows': [['2026-10-23T10:00:00Z']]})
        repo.read = lambda k, default=None: default
        repo.latest = unittest.mock.Mock(side_effect=AssertionError('must not load content'))
        repo.monitoring_status()
        repo.latest.assert_not_called()
        self.assertNotIn('SELECT packet FROM', repo.sql.call_args.args[0])

    def test_append_result_transfers_only_new_result(self):
        repo = Repository({})
        repo.sql = unittest.mock.Mock(return_value={'rows': []})
        repo.read = unittest.mock.Mock(side_effect=AssertionError('must not fetch history'))
        repo.append_analysis({'id': 'new', 'analysis_executed': True})
        self.assertIn('signalas_state.value || EXCLUDED.value', repo.sql.call_args.args[0])
        self.assertEqual(len(repo.sql.call_args.args[1]), 2)

    def test_collection_survives_cloud_failure(self):
        import integrations
        config = {'SIGNALAS_DATABASE_URL': URL}
        with patch.object(integrations, 'settings', return_value=config), patch.object(integrations, 'DiasporaClient') as client, patch.object(integrations, 'save_packet', return_value={'status': 'ok'}), patch.object(cloud, 'sync', side_effect=cloud.CloudStorageError('cloud unavailable')):
            result = integrations.collect_sample()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['cloud_storage']['status'], 'error')

if __name__ == '__main__':
    unittest.main()
