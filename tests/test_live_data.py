import json
import shutil
import tempfile
import unittest
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import live_data
import app


class LiveDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "var").mkdir()
        (self.root / "data").mkdir()
        shutil.copy(live_data.ROOT / "data/catalog.json", self.root / "data/catalog.json")
        self.records = [
            {"id": "p1", "source": "pod.test", "kind": "post", "text": "Tekstas",
             "published_at": "2026-10-21T07:00:00Z", "exercise_id": None, "is_demo": False,
             "sourceUrl": "https://pod.test/p/from-source", "media": [],
             "author_id": "a", "author_name": "Autorius", "counter_scope": "lifetime",
             "comments_include_replies": True, "counters": {"comments": 100, "likes": 1, "shares": None},
             "interactions_complete": False},
            {"id": "c1", "source": "pod.test", "kind": "comment", "text": "Atsakymas",
             "published_at": "2026-10-20T07:00:00Z", "exercise_id": None, "is_demo": False,
             "parentSourceUrl": "https://pod.test/p/from-source", "media": []}]
        self.write("diaspora-latest.json", {"collected_at": "2026-10-21T10:00:00Z",
                   "source": "pod.test", "coverage": "account_visible_stream_first_page",
                   "records": self.records})
        self.write("dashboard-mode.json", {"mode": "live"})
        self.write("dashboard-period.json", {"end_date": "2026-10-21"})

    def write(self, filename, value):
        (self.root / "var" / filename).write_text(json.dumps(value), encoding="utf-8")

    def analysis(self, unit=None, context=None):
        unit = unit or self.records[0]
        return {"analysis_executed": True, "source_reference": {"source": unit["source"], "id": unit["id"]},
                "exercise_context": context, "content_fingerprint": live_data.fingerprint(unit),
                "result": {"theme_id": "security", "narrative_id": "N-001", "candidate_title": None,
                           "stance": "support", "direction": "needs_review", "reason": "Teksto siūlymas",
                           "missing_context": "Trūksta pradinio konteksto.", "evidence": "Tekstas"}}

    def test_real_dates_all_content_review_and_no_demo(self):
        data = live_data.bootstrap(self.root)
        self.assertEqual(data["mode"], "live")
        self.assertEqual(data["days"][0], "2026-10-12")
        self.assertEqual(data["days"][-1], "2026-10-21")
        self.assertEqual(data["analysis_count"], 0)
        self.assertEqual(data["narratives"], [])
        report = live_data.thermometer(7, self.root)
        self.assertEqual((report["total"], report["assessed"], report["unassessed"]), (2, 0, 2))
        self.assertTrue(all(c["percent"] is None for c in report["categories"]))
        self.assertEqual(live_data.thermometer(1, self.root)["total"], 1)

    def test_bound_analysis_counts_unknown_stances_and_dedup(self):
        self.write("openai-analysis-pilot.json", [self.analysis(), self.analysis()])
        data = live_data.bootstrap(self.root)
        self.assertEqual(data["analysis_count"], 1)
        self.assertEqual(len(data["narratives"]), 1)
        n = data["narratives"][0]
        self.assertEqual(sum(n["days"]), 1)
        self.assertEqual(n["dailyStances"][-1], [1, 0, 0])
        self.assertFalse(n["history_complete"])
        self.assertEqual(data["relations"], [])
        self.assertEqual(n["evidence"][0]["sourceUrl"], "https://pod.test/p/from-source")

    def test_content_and_context_changes_invalidate_result(self):
        self.write("openai-analysis-pilot.json", [self.analysis()])
        self.assertEqual(live_data.bootstrap(self.root)["analysis_count"], 1)
        self.write("live-context.json", {"initialSituation": "Nauja situacija", "confirmedFacts": "Faktai"})
        self.assertEqual(live_data.bootstrap(self.root)["analysis_count"], 0)
        (self.root / "var/live-context.json").unlink()
        self.records[0]["text"] = "Pakeista"
        self.write("diaspora-latest.json", {"collected_at": "2026-10-21T10:00:00Z", "source": "pod.test",
                   "coverage": "account_visible_stream_first_page", "records": self.records})
        self.assertEqual(live_data.bootstrap(self.root)["analysis_count"], 0)

    def test_platform_unknown_audience_not_derived_from_interactions(self):
        report = live_data.platform(7, self.root)
        self.assertEqual(report["categories"][0]["items"][0]["count"], 100)
        self.assertEqual(report["authors"]["status"], "empty")
        self.assertEqual(report["authors"]["below_minimum_authors"], 1)
        self.assertEqual(report["authors"]["items"], [])
        self.assertEqual(report["categories"][2]["status"], "missing_data")
        self.assertEqual(len(report["posts"]), 1)
        self.assertEqual(report["collected_post_count"], 1)
        self.assertIsNone(report["exercise_id"])
        self.assertNotIn("interactions", report["posts"][0])

    def test_selection_does_not_follow_collection_or_available_post_date(self):
        self.write("dashboard-period.json", {"end_date": "2020-02-01"})
        report = live_data.platform(7, self.root)
        self.assertEqual(report["start"][:10], "2020-01-26")
        self.assertEqual(report["posts"], [])
        self.assertEqual(live_data.bootstrap(self.root)["units"], [])
        self.assertEqual(live_data.thermometer(7,self.root)["total"],0)

    def test_ten_day_window_includes_old_discussion_and_narrative_days(self):
        old = {**self.records[0], "id": "old", "published_at": "2026-10-14T10:00:00Z",
               "counters": {"comments": 104, "likes": 1, "shares": 0}}
        before = {**old, "id": "before", "published_at": "2026-10-11T20:59:59Z"}
        self.write("diaspora-latest.json", {"collected_at": "2026-10-21T10:00:00Z", "source": "pod.test",
                   "coverage": "account_stream_and_own_profile", "records": self.records + [old, before]})
        self.write("openai-analysis-pilot.json", [self.analysis(old)])
        ten, seven = live_data.platform(10, self.root), live_data.platform(7, self.root)
        self.assertEqual(ten["start"][:10], "2026-10-12")
        self.assertEqual(ten["categories"][0]["items"][0]["id"], "old")
        self.assertEqual(ten["categories"][0]["items"][0]["count"], 104)
        self.assertNotIn("old", [p["id"] for p in seven["posts"]])
        self.assertNotIn("before", [p["id"] for p in ten["posts"]])
        data = live_data.bootstrap(self.root)
        self.assertEqual(data["period"], 10)
        self.assertEqual(len(data["days"]), 10)
        self.assertEqual(data["narratives"][0]["days"][2], 1)
        self.assertEqual(data["narratives"][0]["dailyStances"][2], [1, 0, 0])
        for period, total in ((10, 3), (7, 2), (3, 2), (1, 1)):
            self.assertEqual(live_data.thermometer(period, self.root)["total"], total)
            self.assertEqual(len(live_data.thermometer(period, self.root)["days"]), period)
        self.assertEqual(json.loads((self.root/"var/dashboard-period.json").read_text())["end_date"], "2026-10-21")

    def test_live_api_period_write_requires_token_and_preserves_content(self):
        original_bootstrap,original_period=live_data.bootstrap,live_data.store_period
        with patch.object(live_data,"enabled",return_value=True),patch.object(live_data,"bootstrap",side_effect=lambda:original_bootstrap(self.root)),patch.object(
                live_data,"store_period",side_effect=lambda value,**kwargs:original_period(value,self.root,**kwargs)):
            server=ThreadingHTTPServer(("127.0.0.1",0),partial(app.Handler,db_path=self.root/"api.sqlite3"))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                base="http://127.0.0.1:%s"%server.server_port
                with urlopen(base+"/api/dashboard/bootstrap") as response: data=json.load(response)
                self.assertEqual(len(data["units"]),2)
                from private_media import delivery
                with patch.object(delivery,'image',return_value=(b'RIFF0000WEBPtest','image/webp')) as photo:
                    media_url=base+'/api/media/image?source=pod.test&id=p1&index=0'
                    with self.assertRaises(HTTPError) as forbidden:urlopen(media_url)
                    self.assertEqual(forbidden.exception.code,403)
                    with self.assertRaises(HTTPError) as forbidden:
                        urlopen(Request(media_url,headers={'Host':'other.test','X-Signalas-CSRF':data['csrf']}))
                    self.assertEqual(forbidden.exception.code,403)
                    photo.assert_not_called()
                    with urlopen(Request(media_url,headers={'X-Signalas-CSRF':data['csrf']})) as response:
                        self.assertEqual(response.headers['Content-Type'],'image/webp')
                        self.assertEqual(response.headers['Cache-Control'],'no-store')
                        self.assertEqual(response.headers['Cross-Origin-Resource-Policy'],'same-origin')
                        self.assertTrue(response.read().startswith(b'RIFF'))
                    photo.assert_called_once_with('pod.test','p1',0)
                body=json.dumps({"start_date":"2020-01-28","end_date":"2020-02-01"}).encode()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(base+"/api/dashboard/period",data=body))
                self.assertEqual(caught.exception.code,403)
                with urlopen(Request(base+"/api/dashboard/period",data=body,headers={"X-Signalas-CSRF":data["csrf"]})) as response:
                    changed=json.load(response)
                self.assertEqual(changed["units"],[])
                self.assertEqual(changed["end"][:10],"2020-02-02")
                self.assertEqual(changed["days"],["2020-01-28","2020-01-29","2020-01-30","2020-01-31","2020-02-01"])
                self.assertEqual(len(live_data.load(self.root)[0]["records"]),2)
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_custom_range_persists_and_filters_cached_data_without_collection(self):
        snapshot = (self.root / "var/diaspora-latest.json").read_bytes()
        self.write("openai-analysis-pilot.json", [self.analysis()])
        with patch("diaspora_client.DiasporaClient.login", side_effect=AssertionError("must not collect")), patch(
                "openai_analysis.analyze", side_effect=AssertionError("must not analyze"), create=True):
            live_data.store_period("2026-10-21", self.root, start_date="2026-10-21")
            self.assertEqual(live_data.bootstrap(self.root)["days"], ["2026-10-21"])
            self.assertEqual(len(live_data.bootstrap(self.root)["narratives"][0]["days"]), 1)
            self.assertEqual(len(live_data.platform(root=self.root)["posts"]), 1)
            self.assertEqual(live_data.thermometer(root=self.root)["total"], 1)
            live_data.store_period("2026-10-21", self.root, start_date="2026-09-29")
            data = live_data.bootstrap(self.root)
            self.assertEqual(data["period"], 23)
            self.assertEqual(data["days"][0], "2026-09-29")
            self.assertEqual(len(data["units"]), 2)
            self.assertTrue(data["range_saved"])
            self.assertEqual(live_data.thermometer(root=self.root)["total"], 2)
            # Equal-length dates are distinct queries, independent of the saved selection.
            empty = live_data.platform(root=self.root, start_date="2020-02-01", end_date="2020-02-23")
            self.assertEqual(empty["period"], 23)
            self.assertEqual(empty["posts"], [])
            self.assertEqual(live_data.bootstrap(self.root)["days"][0], "2026-09-29")
        self.assertEqual((self.root / "var/diaspora-latest.json").read_bytes(), snapshot)

    def test_range_validation_leap_day_and_lithuanian_daylight_saving(self):
        from periods import calendar_range
        for start, end in [("2026-10-22","2026-10-21"),("2026-02-30","2026-03-01"),
                           ("", "2026-10-21"),(None,"2026-10-21"),("2026-1-01","2026-01-01"),
                           ("9999-12-31","9999-12-31")]:
            before = (self.root / "var/dashboard-period.json").read_bytes()
            with self.assertRaises(ValueError):
                calendar_range(start,end)
            with self.assertRaises(ValueError):
                live_data.store_period(end,self.root,start_date=start if start is not None else "")
            self.assertEqual((self.root / "var/dashboard-period.json").read_bytes(), before)
        first, last = calendar_range("2024-02-28","2024-03-01")
        self.assertEqual((last.date()-first.date()).days,3)
        for day, hours in [("2026-03-29",23),("2026-10-25",25)]:
            first,last=calendar_range(day,day)
            self.assertEqual((last.timestamp()-first.timestamp())/3600,hours)
        # End includes the whole selected day; the next midnight is excluded.
        first,last=calendar_range("2026-10-21","2026-10-21")
        rows=[{"id":"last", "published_at":"2026-10-21T20:59:59Z"},
              {"id":"next", "published_at":"2026-10-21T21:00:00Z"}]
        self.assertEqual([r["id"] for r in live_data.scoped(rows,first,last)],["last"])


if __name__ == "__main__":
    unittest.main()
