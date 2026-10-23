import io
import json
import os
import re
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from queue import Queue
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.parse import urlsplit, parse_qs
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

import app
import configure_secrets
import diaspora_client
import integration_config
import openai_analysis


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("monitoring.record")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_use_secret_form_accepts_embedded_origin_and_requires_token(self):
        servers = Queue()
        def factory(address, handler):
            server = HTTPServer(address, handler)
            servers.put(server)
            return server
        with tempfile.TemporaryDirectory() as root, patch.object(configure_secrets, "HTTPServer", side_effect=factory), patch.object(
                configure_secrets, "set_secret", side_effect=lambda name, value: integration_config.set_secret(name, value, root)):
            thread = threading.Thread(target=configure_secrets.web_entry, kwargs={"path": "/test-setup"}, daemon=True)
            thread.start()
            server = servers.get(timeout=3)
            url = "http://127.0.0.1:%s/test-setup" % server.server_port
            with urlopen(url, timeout=3) as response:
                html = response.read().decode()
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            csrf = re.search('name="csrf" type="hidden" value="([^"]+)"', html).group(1)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, data=b"csrf=wrong&password=test"), timeout=3)
            self.assertEqual(error.exception.code, 403)
            body = urlencode({"csrf": csrf, "password": 'local-test#=$"secret'}).encode()
            with urlopen(Request(url, data=body, headers={"Origin": "null"}), timeout=3) as response:
                self.assertNotIn("local-test", response.read().decode())
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(integration_config.settings(root)["DIASPORA_PASSWORD"], 'local-test#=$"secret')

    def test_secret_roundtrip_preserves_other_values_and_special_characters(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, ".env")
            path.write_text("OPENAI_API_KEY=test-other-key\nDIASPORA_PASSWORD=old\n")
            secret = 'test"\\#= dollar$'
            integration_config.set_secret("DIASPORA_PASSWORD", secret, root)
            with patch.dict(os.environ, {}, clear=True):
                values = integration_config.settings(root)
            self.assertEqual(values["OPENAI_API_KEY"], "test-other-key")
            self.assertEqual(values["DIASPORA_PASSWORD"], secret)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_image_only_import_without_fake_text(self):
        post = {"source": "test", "external_id": "image", "published_at": "2026-10-21T09:00:00Z",
                "text": "", "is_demo": False, "media": [{"kind": "image", "originalUrl": "https://example.org/photo.jpg"}]}
        self.assertEqual(app.normalize(post, 1)["text"], "")
        with self.assertRaises(ValueError):
            app.normalize({**post, "media": []}, 1)

    def test_diaspora_requires_https_and_blocks_cross_origin(self):
        with self.assertRaises(ValueError):
            diaspora_client.DiasporaClient("http://example.org", "user", "secret")
        client = diaspora_client.DiasporaClient("https://example.org", "user", "secret")
        with self.assertRaises(ValueError):
            client.request("https://other.org/stream.json")

    def test_diaspora_no_invented_original_and_no_parent_media_for_comment(self):
        client = diaspora_client.DiasporaClient("https://example.org", "user", "secret")
        raw = {"id": 8, "guid": "post-guid", "post_type": "StatusMessage", "author": {"guid": "person"},
               "created_at": "2026-10-21T09:00:00Z", "text": "original",
               "photos": [{"sizes": {"medium": "/photo.jpg"}}],
               "interactions": {"likes": [], "reshares": [], "likes_count": 0, "reshares_count": 0,
                                "comments_count": 1, "comments": [{"guid": "comment-guid", "text": "reply",
                                    "created_at": "2026-10-21T09:01:00Z"}]}}
        client.json = lambda path: ({"guid": "person", "is_own_profile": True} if path == "/u/user" else
                                    [raw] if path in ("/stream.json", "/people/person/stream.json") else raw)
        client.canonical = lambda identity: None
        packet = client.collect()
        self.assertFalse(packet["stream_complete"])
        self.assertIsNone(packet["exercise_id"])
        self.assertEqual(packet["comment_count"], 1)
        self.assertIsNone(packet["records"][0]["sourceUrl"])
        self.assertEqual(packet["records"][1]["media"], [])
        self.assertTrue(packet["records"][1]["parent_post"]["media"])

    def test_all_pages_and_own_profile_are_collected_without_total_limit(self):
        client = diaspora_client.DiasporaClient("https://example.org", "user", "secret")
        # 41 feed posts cross three server pages; own profile adds a new post
        # and repeats a feed post. Identical boundary seconds must not lose rows.
        now = datetime(2026, 10, 21, 10, tzinfo=timezone.utc)
        posts = [{"id": i, "guid": "p%s" % i, "text": "post", "post_type": "StatusMessage",
                  "created_at": (now - timedelta(seconds=i // 2, milliseconds=i % 2 * 100)).isoformat(),
                  "author": {"guid": "person"}, "interactions": {"comments": []}} for i in range(42)]
        calls = []
        def endpoint(path):
            calls.append(path)
            if path == "/u/user":
                return {"guid": "person", "is_own_profile": True}
            address = urlsplit(path)
            if address.path in ("/stream.json", "/people/person/stream.json"):
                rows = posts[:41] if address.path == "/stream.json" else [posts[0], posts[41]]
                cursor = parse_qs(address.query).get("max_time")
                if cursor:
                    rows = [p for p in rows if datetime.fromisoformat(p["created_at"]).timestamp() < int(cursor[0])]
                return rows[:15]
            return posts[int(address.path.split("/")[-1].split(".")[0])]
        client.json = endpoint
        client.canonical = lambda identity: None
        packet = client.collect()
        self.assertEqual(packet["post_count"], 42)
        self.assertEqual(len(packet["records"]), 42)
        self.assertIsNone(packet["limits"]["post_limit"])
        self.assertEqual(packet["account_scope"]["own_profile_posts"], 2)
        self.assertGreaterEqual(packet["account_scope"]["feed_pages"], 3)
        self.assertFalse(packet["stream_complete"])  # Account access is not whole-pod access.
        self.assertEqual(sum(p.startswith("/posts/") for p in calls), 42)

    def test_saturated_timestamp_does_not_silently_skip_content(self):
        client = diaspora_client.DiasporaClient("https://example.org", "user", "secret")
        client.json = lambda path: [{"id": i, "guid": str(i), "created_at": "2026-10-21T09:00:00.200Z"} for i in range(15)]
        with self.assertRaisesRegex(ValueError, "puslapiavimo"):
            client.stream("/stream.json")

    def test_refresh_reuses_original_url_but_detects_edited_old_comment(self):
        client = diaspora_client.DiasporaClient('https://example.org', 'user', 'test')
        post = {'id': 1, 'guid': 'p', 'text': 'Original', 'post_type': 'StatusMessage',
                'created_at': '2026-10-23T09:00:00Z', 'author': {'guid': 'person'},
                'interactions': {'comments_count': 1, 'comments': [{'guid': 'c', 'text': 'Edited old comment',
                    'created_at': '2026-10-23T10:00:00Z'}]}}
        calls = []
        def json_api(path):
            calls.append(path)
            if path == '/u/user': return {'guid': 'person', 'is_own_profile': True}
            return post if path.startswith('/posts/') else [post]
        client.json = json_api
        client.canonical = unittest.mock.Mock(side_effect=AssertionError('must reuse verified URL'))
        packet = client.collect(compact=True, previous={'records': [
            {'source': 'example.org', 'id': 'p', 'sourceUrl': 'https://example.org/verified-original'}]})
        self.assertEqual(sum(p.startswith('/posts/') for p in calls), 1, 'feed/profile duplicate expanded only once')
        self.assertEqual(packet['records'][1]['text'], 'Edited old comment')
        self.assertNotIn('conversation_context', packet['records'][1])
        self.assertEqual(packet['records'][1]['parent_id'], 'p')

    def test_authenticated_conditional_request_requires_real_304(self):
        client = diaspora_client.DiasporaClient('https://example.org', 'user', 'test')
        client.opener = unittest.mock.Mock()
        client.opener.open.side_effect = HTTPError('https://example.org/posts/1.json', 304, 'Not Modified', {}, None)
        body, _, _, _ = client.request('/posts/1.json', validators={'etag': '"etag-test"'}, include_headers=True)
        self.assertIsNone(body)
        self.assertEqual(client.opener.open.call_args.args[0].get_header('If-none-match'), '"etag-test"')
        with self.assertRaises(ValueError):
            client.request('/posts/1.json', validators={'etag': 'bad\r\nheader'}, include_headers=True)
        self.assertIsNone(client.opener.open.call_args.args[0].get_header('If-none-match'))

    def test_304_reuses_complete_cached_thread_and_checks_source(self):
        client = diaspora_client.DiasporaClient('https://example.org', 'user', 'test')
        entry = {'id': 1, 'guid': 'p'}
        client.json = lambda path: {'guid': 'person', 'is_own_profile': True} if path == '/u/user' else [entry]
        client.post_json = unittest.mock.Mock(return_value=(None, {'etag': '"test"'}))
        client.canonical = unittest.mock.Mock(side_effect=AssertionError('must reuse canonical URL'))
        cached = {'source': 'example.org', 'id': 'p', 'kind': 'post', 'text': 'Original',
                  'sourceUrl': 'https://example.org/verified', 'sourceValidators': {'etag': '"test"'}}
        comment = {'source': 'example.org', 'id': 'c', 'kind': 'comment', 'parent_id': 'p', 'text': 'Original comment'}
        result = client.collect(compact=True, conditional=True, previous={'records': [cached, comment]})
        client.post_json.assert_called_once_with(1, {'etag': '"test"'})
        self.assertEqual(result['records'], [cached, comment])
        self.assertEqual(result['collection_stats']['not_modified'], 1)
        self.assertEqual(result['collection_stats']['detail_bodies'], 0)

    def test_bounded_parallel_collection_preserves_unique_post_order(self):
        from types import SimpleNamespace
        barrier = threading.Barrier(4)
        entries = [{'id': i, 'guid': str(i)} for i in range(4)]
        client = diaspora_client.DiasporaClient('https://example.org', 'user', 'test')
        client.json = lambda path: {'guid': 'person', 'is_own_profile': True} if path == '/u/user' else entries
        def detail(path):
            barrier.wait(timeout=5)
            i = path.split('/')[2].split('.')[0]
            return {'id': int(i), 'guid': i, 'text': 'Original', 'post_type': 'StatusMessage',
                    'created_at': '2026-10-23T10:00:00Z', 'author': {'guid': 'person'}, 'interactions': {'comments': []}}
        client.fork = lambda: SimpleNamespace(json=detail, canonical=lambda i: None)
        packet = client.collect(compact=True, workers=4)
        self.assertEqual([r['id'] for r in packet['records']], ['0', '1', '2', '3'])
        self.assertEqual(packet['post_count'], 4)

    def test_previous_discussion_only_and_legacy_context(self):
        unit = {"id": "test", "text": "text", "published_at": "2026-10-21T10:00:00Z",
                "conversation_context": [{"id": "past", "published_at": "2026-10-21T09:00:00Z"},
                                         {"id": "future", "published_at": "2026-10-21T11:00:00Z"}]}
        context = {"initialSituation": "Situation", "confirmedFacts": "Facts"}
        prepared = openai_analysis.prepare_input(unit, context)
        self.assertEqual([x["id"] for x in prepared["content"]["conversation_context"]], ["past"])
        self.assertEqual(prepared["exercise_context"]["nameMappings"], [])
        self.assertFalse(prepared["coverage"]["images"])
        auxiliary = openai_analysis.prepare_input(unit, context, [{"title": "Papildomas pasakojimas"}])
        self.assertEqual(auxiliary["auxiliary_narratives"], [{"title": "Papildomas pasakojimas"}])
        self.assertEqual(auxiliary["content"]["conversation_context"][0]["id"], "past")
        with self.assertRaises(ValueError):
            openai_analysis.context_data({**context, "nameMappings": [
                {"id": "a", "realName": "same", "exerciseName": "a"},
                {"id": "b", "realName": "SAME", "exerciseName": "b"}]})

    def test_model_result_validation_and_review_for_unread_media(self):
        catalog = app.catalog()
        valid = {"narrative_analysis": {"match_status":"no_narrative","matches":[],"proposals":[],"uncertainty_reason":""},
                 "direction": "neutral", "reason": "Kasdienis turinys.", "missing_context": "", "evidence": '"text"', "reason_codes": ["N0"]}
        unit = {"id": "test", "source": "test", "kind": "post", "text": "text",
                "published_at": "2026-10-21T10:00:00Z", "media": [{"kind": "image"}]}
        response = {"status": "completed", "model": "test", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(valid)}]}]}
        with patch.object(openai_analysis, "api_key", return_value="test-secret"), patch.object(openai_analysis, "build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
            result = openai_analysis.analyze(unit, {"initialSituation": "Situation", "confirmedFacts": "Facts"})
            self.assertEqual(result["result"]["direction"], "needs_review")
            self.assertEqual(result["result"]["evidence"], "text")
            request = opener.return_value.open.call_args.args[0]
            sent = json.loads(request.data)
            self.assertFalse(sent["store"])
            self.assertNotIn("test-secret", json.dumps(sent["input"]))
        with self.assertRaises(ValueError):
            openai_analysis.validate_result({**valid, "theme_id": "invented-theme"}, catalog)


    def test_sol_thermometer_only_request_has_no_narrative_workload(self):
        unit = {"id": "recheck", "source": "test", "kind": "post", "text": "Rami diena.",
                "published_at": "2026-10-21T10:00:00Z", "media": []}
        valid = {"direction": "neutral", "reason": "Kasdienis turinys.", "missing_context": "",
                 "evidence": unit["text"], "reason_codes": ["N0"]}
        response = {"status": "completed", "model": "gpt-6.1-sol", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(valid)}]}]}
        with patch.object(openai_analysis, "api_key", return_value="test"), patch.object(openai_analysis, "build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
            result = openai_analysis.analyze(unit, model_override="gpt-6.1-sol", thermometer_only=True)
            sent = json.loads(opener.return_value.open.call_args.args[0].data)
            self.assertEqual(sent["model"], "gpt-6.1-sol")
            self.assertNotIn("narrative_analysis", sent["text"]["format"]["schema"]["properties"])
            self.assertNotIn("narrative_registry", json.loads(sent["input"][0]["content"][0]["text"]))
            self.assertNotIn("pending_claims", json.loads(sent["input"][1]["content"][0]["text"]))
            self.assertEqual(result["result"]["thermometer_category"], "neutral")
            self.assertEqual(result["model"], "gpt-6.1-sol")

    def test_context_supported_s1_and_d1_are_not_forced_to_review(self):
        unit = {"id": "context-test", "source": "test", "kind": "post", "text": "Pagalbos punktas uždarytas.",
                "published_at": "2026-10-21T10:00:00Z", "media": []}
        context = {"initialSituation": "Veikia pagalbos punktas.", "confirmedFacts": "Pagalbos punktas atidarytas."}
        for category, code in [("stabilizing", "S1"), ("destabilizing", "D1")]:
            with self.subTest(code=code):
                valid = {"narrative_analysis": {"match_status": "no_narrative", "matches": [],
                         "proposals": [], "uncertainty_reason": ""}, "direction": category,
                         "reason": "Pateiktu kontekstu pagrįstas vertinimas.", "missing_context": "",
                         "evidence": unit["text"], "reason_codes": [code]}
                response = {"status": "completed", "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": json.dumps(valid)}]}]}
                with patch.object(openai_analysis, "api_key", return_value="test-secret"), patch.object(openai_analysis, "build_opener") as opener:
                    opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
                    result = openai_analysis.analyze(unit, context)
                    self.assertEqual(result["result"]["thermometer_status"], "classified")
                    self.assertEqual(result["result"]["thermometer_category"], category)
                    request = json.loads(opener.return_value.open.call_args.args[0].data)
                    self.assertNotIn("verified_claim_source", request["text"]["format"]["schema"]["properties"])
                    self.assertIn("pateiktą pratybų bei diskusijos kontekstą", request["instructions"])
                    valid.update(direction="needs_review", reason_codes=[], missing_context="Trūksta būtino fakto.")
                    opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps({
                        "status": "completed", "output": [{"type": "message", "content": [
                            {"type": "output_text", "text": json.dumps(valid)}]}]}).encode())
                    pending = openai_analysis.analyze(unit, context)
                    self.assertEqual(pending["result"]["thermometer_status"], "needs_review")
                    self.assertIsNone(pending["result"]["thermometer_category"])

    def test_multilingual_analysis_preserves_original_evidence_and_names(self):
        text = 'Nie panikujcie. Не паникуйте. Stay calm. Šilo miestas.'
        valid = {"narrative_analysis": {"match_status":"no_narrative","matches":[],"proposals":[],"uncertainty_reason":""},
                 "direction": "neutral", "reason": "Kasdienis turinys.", "missing_context": "", "evidence": text, "reason_codes": ["N0"]}
        unit = {"id":"language-test", "source":"test", "kind":"comment", "text":text,
                "published_at":"2026-10-21T10:00:00Z", "media":[]}
        response={"status":"completed","output":[{"type":"message","content":[
            {"type":"output_text","text":json.dumps(valid,ensure_ascii=False)}]}]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'data').mkdir()
            (root/'data/catalog.json').write_text(json.dumps(app.catalog()))
            with patch.object(openai_analysis,'api_key',return_value='test-secret'), patch.object(openai_analysis,'build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(json.dumps(response).encode())
                result=openai_analysis.analyze(unit,{"initialSituation":"Šilo miestas","confirmedFacts":"Faktai"},root=root)
                sent=json.loads(opener.return_value.open.call_args.args[0].data)
                self.assertEqual(sent['model'], 'gpt-6-luna')
                self.assertEqual(sent['reasoning']['effort'], 'medium')
                self.assertEqual(sent['max_output_tokens'], 6000)
                self.assertEqual(sent['service_tier'], 'default')
                self.assertEqual(json.loads(sent['input'][1]['content'][0]['text'])['analysis_input']['content']['text'],text)
                stable=sent['input'][0]['content'][0]
                self.assertNotIn(text,stable['text'])
                self.assertEqual(stable['prompt_cache_breakpoint'],{'mode':'explicit'})
                self.assertEqual(sent['prompt_cache_options'],{'mode':'explicit','ttl':'30m'})
                self.assertEqual(result['requested_service_tier'],'default')
                self.assertEqual(result['original_text'],text)
                self.assertEqual(result['result']['evidence'],text)
                self.assertIn('originalo kalba',sent['instructions'])
                self.assertIn('pagal prasmę tarp kalbų',sent['instructions'])
                self.assertIn('kalbinio paaiškinimo',sent['instructions'])


if __name__ == "__main__":
    unittest.main()
