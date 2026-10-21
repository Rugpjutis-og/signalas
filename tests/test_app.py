import json
import tempfile
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

import app


class LocalAppTests(unittest.TestCase):
    def setUp(self):
        mode = patch("live_data.enabled", return_value=False)
        mode.start()
        self.addCleanup(mode.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "test.sqlite3"
        self.rows = json.loads((app.ROOT / "examples/posts.json").read_text())

    def ingest(self, rows):
        path = Path(self.temp.name) / "posts.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return app.import_file(path, self.db_path)

    def test_import_is_idempotent_and_unknown_stays_unassigned(self):
        self.assertEqual(self.ingest(self.rows), {"added": 2, "duplicates": 0})
        self.assertEqual(self.ingest(self.rows), {"added": 0, "duplicates": 2})
        db = app.connect(self.db_path)
        self.addCleanup(db.close)
        self.assertEqual(app.summary(db), {"total": 2, "demo": 2, "non_demo": 0, "unassigned": 1})
        self.assertEqual(db.execute("SELECT published_at FROM posts LIMIT 1").fetchone()[0], "2026-10-19T09:00:00+00:00")

    def test_invalid_batch_is_not_partially_imported(self):
        self.ingest(self.rows[:1])
        self.rows[0]["external_id"] = "new"
        self.rows[1]["narrative_id"] = "invented-narrative"
        with self.assertRaises(ValueError):
            self.ingest(self.rows)
        db = app.connect(self.db_path)
        self.addCleanup(db.close)
        self.assertEqual(app.summary(db)["total"], 1)

    def test_metadata_validation(self):
        for change in ({"published_at": "2026-10-19T12:00:00"}, {"text": " "}, {"stance": "positive"}, {"is_demo": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                app.normalize(dict(self.rows[0], **change), 1)

    def test_csv_import(self):
        path = Path(self.temp.name) / "posts.csv"
        path.write_text('source,external_id,published_at,text,narrative_id,stance,is_demo\nmanual,1,2026-10-19T12:00:00Z,"Tekstas, su kableliu",,unknown,false\n')
        self.assertEqual(app.import_file(path, self.db_path)["added"], 1)

    def test_api_and_private_files(self):
        self.ingest(self.rows)
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(app.Handler, db_path=self.db_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:%s" % server.server_port
        with urlopen(base + "/api/posts?limit=1&offset=1") as response:
            posts = json.load(response)["posts"]
            self.assertEqual(len(posts), 1)
            self.assertIsInstance(posts[0]["media"], list)
        with urlopen(base + "/api/metrics/context") as response:
            context = json.load(response)
            self.assertEqual(context["audience"]["status"], "missing")
            self.assertIsNone(context["audience"]["count"])
            self.assertEqual(context["growth_policy"]["minAudienceFraction"], 0.01)
        with urlopen(base + "/api/catalog") as response:
            data = json.load(response)
            self.assertEqual(len(data["themes"]), 15)
            self.assertEqual(sum(t["priority"] for t in data["themes"]), 8)
            self.assertEqual(len(data["narratives"]), 21)
        with urlopen(base + "/") as response:
            self.assertIn("Naratyvų observatorija", response.read().decode())
        for period in (10, 7, 3, 1):
            with urlopen(base + "/api/platform/overview?period=%s" % period) as response:
                report = json.load(response)
                self.assertEqual(report["mode"], "demo")
                self.assertEqual(report["period"], period)
                self.assertEqual(len(report["categories"]), 3)
                self.assertLessEqual(len(report["authors"]["items"]), 5)
        for period, expected in ((10, 34), (7, 34), (3, 16), (1, 6)):
            with urlopen(base + "/api/thermometer?period=%s" % period) as response:
                report = json.load(response)
                self.assertEqual(report["total"], expected)
                self.assertEqual(report["mode"], "demo")
        for route, status in (("/api/platform/overview?period=2", 400), ("/api/platform/overview?period=no", 400), ("/api/posts?limit=no", 400), ("/api/thermometer?period=2", 400), ("/api/thermometer?period=no", 400), ("/../app.py", 404), ("/var/signalas.sqlite3", 404), ("/api/missing", 404)):
            with self.subTest(route=route), self.assertRaises(HTTPError) as error:
                urlopen(base + route)
            self.assertEqual(error.exception.code, status)


if __name__ == "__main__":
    unittest.main()
