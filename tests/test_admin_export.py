import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from admin_export import read_export
from platform_overview import report
from thermometer import instant


class AdminExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "admin.json"
        self.raw = []
        for index in range(25):
            comments = []
            if index == 0:
                for i in range(101):
                    comments.append({"guid": "comment-%s" % i, "text": "Sintetinis komentaras",
                                     "created_at": (datetime(2026,10,21,7,tzinfo=timezone.utc)+timedelta(seconds=i)).isoformat(),
                                     "author": {"guid": "outside-roster"},
                                     "interactions": {"likes_count": 1, "likes": [{"id": i, "author": {"guid": "liker-outside-roster"}}]}})
            self.raw.append({"sourceUrl": "https://diaspora.sauliai.lt/posts/synthetic-%s" % index,
                "post": {"guid": "post-%s" % index, "post_type": "StatusMessage",
                         "created_at": "2026-10-20T12:00:00Z", "text": "Sintetinis įrašas",
                         "author": {"guid": "outside-roster" if index else "known"},
                         "photos": [{"sizes": {"medium": "/uploads/synthetic.jpg"}}] if index == 0 else [],
                         "interactions": {"likes": [], "likes_count": 0, "reshares": [], "reshares_count": 0,
                                          "comments": comments, "comments_count": len(comments)}}})
        older = deepcopy(self.raw[0])
        older["post"].update(guid="old-parent", created_at="2026-10-10T12:00:00Z")
        older["sourceUrl"] = "https://diaspora.sauliai.lt/posts/older-synthetic"
        older["post"]["interactions"]["comments"] = [
            {"guid": "old-context", "text": "Ankstesnis komentaras", "created_at": "2026-10-11T12:00:00Z"},
            {"guid": "new-reply", "text": "Naujas atsakymas", "created_at": "2026-10-21T12:00:00Z"}]
        older["post"]["interactions"]["comments_count"] = 2
        self.raw.append(older)
        self.payload = {"format": "signalas.diaspora.export.v1", "collected_at": "2026-10-21T14:00:00Z",
                        "raw_posts": self.raw, "membership_snapshots": [{"complete": False, "assigned_account_ids": ["known"]}],
                        "scope": {"kind": "pod_database", "source": "https://diaspora.sauliai.lt",
                                  "from": "2026-10-15T00:00:00Z", "until": "2026-10-22T00:00:00Z",
                                  "complete": True, "includes_private": True, "contact_filter": False,
                                  "membership_filter": False, "database_read_only": True,
                                  "expected_posts": 25, "expected_comments": 102, "exercise_id": "test-exercise"}}

    def load(self):
        self.path.write_text(json.dumps(self.payload), encoding="utf-8")
        return read_export(self.path)

    def test_no_post_comment_or_membership_cap(self):
        packet = self.load()
        self.assertEqual((packet["post_count"],packet["comment_count"]), (25,102))
        self.assertEqual(len(packet["records"]),127)
        self.assertTrue(packet["stream_complete"])
        self.assertIn("outside-roster", {r.get("author_id") for r in packet["records"]})
        comment = next(r for r in packet["records"] if r["id"] == "comment-100")
        self.assertEqual(comment["media"], [])
        self.assertTrue(comment["parent_post"]["media"])
        self.assertEqual(comment["counters"]["likes"],1)
        self.assertEqual(comment["interactions"][0]["account_id"],"liker-outside-roster")
        result = report(packet["records"],packet["membership_snapshots"], exercise_id="test-exercise",
                        start=instant(self.payload["scope"]["from"]),end=instant(self.payload["scope"]["until"]),mode="live")
        self.assertEqual(result["categories"][0]["items"][0]["count"],101)
        self.assertEqual(result["authors"]["status"],"missing_data")

    def test_out_of_period_parent_is_context_not_extra_unit(self):
        packet=self.load()
        self.assertNotIn("old-parent",{r["id"] for r in packet["records"]})
        reply=next(r for r in packet["records"] if r["id"]=="new-reply")
        self.assertEqual(reply["parent_id"],"old-parent")
        self.assertEqual(reply["parent_post"]["sourceUrl"],"https://diaspora.sauliai.lt/posts/older-synthetic")
        self.assertEqual([r["id"] for r in reply["conversation_context"]],["old-context"])

    def test_unproven_completeness_preserves_content(self):
        self.payload["scope"]["expected_posts"]=1000
        packet=self.load()
        self.assertFalse(packet["stream_complete"])
        self.assertEqual(len(packet["records"]),127)


if __name__ == "__main__":
    unittest.main()
