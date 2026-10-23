import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import patch

import integrations
import monitoring
import openai_analysis
import openai_check


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "var").mkdir()
        self.now = datetime.now(timezone.utc)
        self.collected = self.now.isoformat()
        self.path = self.root / "var/diaspora-latest.json"
        self.path.write_text(json.dumps({"collected_at": self.collected, "records": []}))

    def status(self, **kwargs):
        return monitoring.status(self.root, **kwargs)

    def test_fresh_stale_empty_and_invalid_status(self):
        self.assertEqual(self.status()["state"], "watching")
        self.assertEqual(self.status(now=self.now+timedelta(minutes=90))["state"], "watching")
        self.assertEqual(self.status(now=self.now+timedelta(minutes=91))["reason"], "stale_collection")
        self.path.unlink()
        self.assertEqual(self.status()["reason"], "missing_collection")
        (self.root/"var/collection-status.json").write_text("bad JSON")
        self.assertEqual(self.status()["state"], "stopped")

    def test_collection_failure_preserves_snapshot_and_recovers(self):
        original=self.path.read_bytes()
        with patch.object(integrations,"ROOT",self.root), patch.object(integrations,"settings",return_value={}), patch.object(integrations,"DiasporaClient") as client:
            client.return_value.login.side_effect=ValueError("synthetic source failure")
            with self.assertRaises(ValueError):
                integrations.collect_sample(self.root/"store.sqlite3")
        self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(self.status()["reason"],"collection_failed")
        monitoring.record("collection",root=self.root)
        self.assertEqual(self.status()["state"],"watching")

    def test_quota_failure_cannot_be_cleared_by_collection_or_models_check(self):
        error=HTTPError("https://api.openai.com/v1/responses",429,"private-token",{},io.BytesIO(
            json.dumps({"error":{"code":"credit_balance_exhausted","type":"insufficient_quota","message":"private-token"}}).encode()))
        monitoring.http_failure(error,self.root)
        self.assertEqual(self.status()["reason"],"api_quota")
        monitoring.record("collection",root=self.root)
        monitoring.access_recovered(self.root)
        self.assertEqual(self.status()["state"],"stopped")
        saved=(self.root/"var/openai-status.json").read_text()
        self.assertNotIn("private-token",saved)
        self.assertEqual((self.root/"var/openai-status.json").stat().st_mode & 0o777,0o600)
        monitoring.record("openai",root=self.root)
        self.assertEqual(self.status()["state"],"watching")

    def test_rate_limit_is_not_assumed_to_be_exhausted_credit(self):
        for code,kind,expected in [("rate_limit_exceeded","rate_limit_error","api_rate_limit"),
                                   ("resource_unavailable",None,"api_capacity"),
                                   ("project_spend_limit_exceeded",None,"api_quota"),
                                   (None,"insufficient_quota","api_quota"),
                                   ({"untrusted":"value"},None,"api_rate_limit")]:
            error=HTTPError("https://api.openai.com/v1/responses",429,"ignored",{},io.BytesIO(
                json.dumps({"error":{"code":code,"type":kind}}).encode()))
            self.assertEqual(monitoring.http_failure(error,self.root),expected)

    def test_already_running_is_not_a_failure(self):
        import fcntl
        with (self.root/"var/collection.lock").open("w") as lock, patch.object(integrations,"ROOT",self.root):
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(integrations.collect_sample(),{"status":"already_running"})
        self.assertEqual(self.status()["state"],"watching")

    def test_api_hooks_record_connection_quota_and_recovery_without_live_requests(self):
        (self.root/"data").mkdir()
        shutil.copy(monitoring.ROOT/"data/catalog.json",self.root/"data/catalog.json")
        unit={"id":"test","source":"test","kind":"post","text":"text","published_at":self.collected}
        with patch.object(openai_analysis,"api_key",return_value="synthetic-key"),patch.object(openai_analysis,"build_opener") as opener:
            opener.return_value.open.side_effect=URLError("private detail")
            with self.assertRaises(ValueError):openai_analysis.analyze(unit,root=self.root)
            self.assertEqual(self.status()["reason"],"api_connection")
            opener.return_value.open.side_effect=HTTPError("https://api.openai.com/v1/responses",429,"ignored",{},io.BytesIO(
                b'{"error":{"code":"insufficient_quota"}}'))
            with self.assertRaises(ValueError):openai_analysis.analyze(unit,root=self.root)
            self.assertEqual(self.status()["reason"],"api_quota")
            opener.return_value.open.side_effect=None
            opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(json.dumps({
                "status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({
                    "narrative_analysis":{"match_status":"no_narrative","matches":[],"proposals":[],"uncertainty_reason":""},"direction":"neutral",
                    "reason":"Kasdienis turinys","missing_context":"","evidence":"text",
                    "reason_codes":["N0"],"verified_claim_source":None})}]}]}).encode())
            openai_analysis.analyze(unit,root=self.root)
            self.assertEqual(self.status()["state"],"watching")
        monitoring.record("openai","api_connection",self.root)
        with patch.object(openai_check,"api_key",return_value="synthetic-key"),patch.object(openai_check,"build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(b'{"data":[]}')
            openai_check.check(self.root)
        self.assertEqual(self.status()["state"],"watching")


if __name__=="__main__":
    unittest.main()
