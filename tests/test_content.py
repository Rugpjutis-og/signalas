import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import app
from content import diaspora_photos, normalize_media, source_reference, source_url


class ContentTests(unittest.TestCase):
    def test_photo_sizes_are_supplied_not_guessed(self):
        photos = [{'guid': 'must-not-be-used-as-path', 'sizes': {'small': '/provided/small.jpg', 'medium': '/provided/medium.jpg', 'raw': '/provided/original.jpg'}, 'alt': 'Pateiktas tekstas'},
                  {'guid': 'without-urls'}]
        media = diaspora_photos(photos, source_base_url='https://pod.test/')
        self.assertEqual(media[0], {'kind': 'image', 'thumbnailUrl': 'https://pod.test/provided/medium.jpg', 'originalUrl': 'https://pod.test/provided/original.jpg', 'alt': 'Pateiktas tekstas'})
        self.assertIsNone(media[1]['thumbnailUrl'])
        self.assertIsNone(media[1]['originalUrl'])
        self.assertNotIn('must-not-be-used-as-path', json.dumps(media))
        original_only = normalize_media([{'kind': 'image', 'originalUrl': 'https://pod.test/photo/original.jpg'}])[0]
        self.assertIsNone(original_only['thumbnailUrl'])
        self.assertEqual(original_only['originalUrl'], 'https://pod.test/photo/original.jpg')
        self.assertIsNone(normalize_media([{'kind': 'image', 'thumbnailUrl': 'javascript:alert(1)'}])[0]['thumbnailUrl'])
        self.assertEqual(normalize_media([]), [])

    def test_only_configured_pod_http_media_upgrades_to_verified_https_origin(self):
        media=normalize_media([{'kind':'image','thumbnailUrl':'http://pod.test/uploads/thumb.webp?size=1',
                                'originalUrl':'http://other.test/uploads/original.webp'}],source_base_url='https://pod.test')
        self.assertEqual(media[0]['thumbnailUrl'],'https://pod.test/uploads/thumb.webp?size=1')
        self.assertEqual(media[0]['originalUrl'],'http://other.test/uploads/original.webp')
        self.assertIsNone(normalize_media([{'kind':'image','thumbnailUrl':'http://user:pass@pod.test/x.webp'}],source_base_url='https://pod.test')[0]['thumbnailUrl'])
    def test_only_supplied_specific_http_links(self):
        for value in (None, ''):
            self.assertIsNone(source_url(value))
        for value in ('javascript:alert(1)', '/posts/123', 'https://pod.test/', 'https://user:secret@pod.test/p/a', 'https://pod.test/p/a\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_url(value)
        ref = source_reference({'id': '123', 'source': 'pod.test', 'kind': 'comment', 'parentSourceUrl': 'https://pod.test/p/supplied'})
        self.assertIsNone(ref['sourceUrl'])
        self.assertEqual(ref['parentSourceUrl'], 'https://pod.test/p/supplied')
        self.assertIsNone(source_reference({'id': '123', 'source': 'https://pod.test'})['sourceUrl'])

    def test_legacy_sqlite_migration_and_import_preserve_links(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / 'old.sqlite3'
            db = sqlite3.connect(db_path)
            db.execute('CREATE TABLE posts(source TEXT, external_id TEXT, published_at TEXT, text TEXT, narrative_id TEXT, stance TEXT, is_demo INTEGER, imported_at TEXT, PRIMARY KEY(source,external_id))')
            db.execute("INSERT INTO posts VALUES('old','1','2026-10-19T12:00:00Z','Senas tekstas',NULL,'unknown',0,'2026-10-19T12:00:00Z')")
            db.commit()
            db.close()
            migrated = app.connect(db_path)
            old = dict(migrated.execute('SELECT * FROM posts').fetchone())
            migrated.close()
            self.assertEqual(old['text'], 'Senas tekstas')
            self.assertEqual(old['kind'], 'post')
            self.assertIsNone(old['sourceUrl'])
            self.assertEqual(json.loads(old['media']), [])
            row = {'source': 'test', 'external_id': 'c1', 'kind': 'comment', 'published_at': '2026-10-19T12:00:00Z',
                   'text': '  Originalus tekstas\n', 'is_demo': False,
                   'sourceUrl': 'https://pod.test/p/exact#provided-comment', 'parentSourceUrl': 'https://pod.test/p/exact',
                   'media': [{'kind': 'image', 'thumbnailUrl': 'https://pod.test/image/small.jpg', 'originalUrl': 'https://pod.test/image/original.jpg', 'alt': 'Nuotrauka'}]}
            path = Path(folder) / 'posts.json'
            path.write_text(json.dumps([row]))
            self.assertEqual(app.import_file(path, db_path)['added'], 1)
            db = app.connect(db_path)
            saved = dict(db.execute("SELECT * FROM posts WHERE external_id='c1'").fetchone())
            db.close()
            self.assertEqual(saved['sourceUrl'], row['sourceUrl'])
            self.assertEqual(saved['parentSourceUrl'], row['parentSourceUrl'])
            self.assertEqual(saved['text'], row['text'])
            self.assertEqual(json.loads(saved['media']), row['media'])


if __name__ == '__main__':
    unittest.main()
