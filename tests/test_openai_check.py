import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import openai_check


class OpenAICheckTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("monitoring.record")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_key_does_not_call_network(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {}, clear=True), patch.object(openai_check, "build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "Įrašykite raktą"):
                openai_check.check(root)
            opener.assert_not_called()

    def test_file_key_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {}, clear=True):
            Path(root, ".env").write_text('# local\nOPENAI_API_KEY="test-file-key"\n')
            self.assertEqual(openai_check.api_key(root), "test-file-key")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-env-key"}):
                self.assertEqual(openai_check.api_key(root), "test-env-key")

    def test_models_only_and_no_secret_in_status(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), patch.object(openai_check, "build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(b'{"data": []}')
            status = openai_check.check()
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.openai.com/v1/models")
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertNotIn("test-secret", status)

    def test_error_response_does_not_expose_secret(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), patch.object(openai_check, "build_opener") as opener:
            opener.return_value.open.side_effect = HTTPError("https://api.openai.com/v1/models", 401, "test-secret", {}, None)
            with self.assertRaises(ValueError) as caught:
                openai_check.check()
            self.assertNotIn("test-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
