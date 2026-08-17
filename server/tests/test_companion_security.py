from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import unittest
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pachevideo_companion_server", ROOT / "companion" / "server.py")
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helper
SPEC.loader.exec_module(helper)


class CompanionSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_port = helper.PORT
        self.original_token = helper.SESSION_TOKEN
        self.original_state_home = os.environ.get("XDG_STATE_HOME")
        helper.ALLOWED_OUTPUT_FOLDERS.clear()

    def tearDown(self) -> None:
        helper.PORT = self.original_port
        helper.SESSION_TOKEN = self.original_token
        if self.original_state_home is None:
            os.environ.pop("XDG_STATE_HOME", None)
        else:
            os.environ["XDG_STATE_HOME"] = self.original_state_home

    def test_creates_fresh_private_session_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            os.environ["XDG_STATE_HOME"] = temporary
            first = helper.create_session_token()
            second = helper.create_session_token()
            token_path = helper.session_token_path()
            self.assertNotEqual(first, second)
            self.assertEqual(second, token_path.read_text(encoding="utf-8").strip())
            if os.name != "nt":
                self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)

    def test_output_folder_requires_current_session_allowance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "Downloads"
            resolved = helper.validate_output_folder(folder)
            self.assertFalse(helper.output_folder_is_allowed(resolved))
            self.assertEqual(helper.allow_output_folder(folder), resolved)
            self.assertTrue(helper.output_folder_is_allowed(resolved))
            with self.assertRaisesRegex(ValueError, "ocultas"):
                helper.validate_output_folder(Path(temporary) / ".secret")

    def test_output_name_is_portable_and_bounded(self) -> None:
        safe = helper.safe_output_name("..\\CON:<bad>?" + "x" * 200 + ".webm", "video")
        self.assertTrue(safe.endswith(".mp4"))
        self.assertNotIn("..", safe)
        self.assertNotRegex(safe, r'[<>:\\"|?*]')
        self.assertLessEqual(len(safe.removesuffix(".mp4").encode("utf-8")), 120)

    def test_http_requires_exact_local_host_and_bearer_token(self) -> None:
        server = helper.ThreadingHTTPServer(("127.0.0.1", 0), helper.Handler)
        helper.PORT = server.server_address[1]
        helper.SESSION_TOKEN = "test-token"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{helper.PORT}"
        try:
            with self.assertRaises(HTTPError) as missing_token:
                urlopen(f"{base}/health", timeout=2)
            self.assertEqual(missing_token.exception.code, 401)

            request = Request(f"{base}/health", headers={"Authorization": "Bearer test-token"})
            with urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

            request = Request(
                f"{base}/health",
                headers={"Authorization": "Bearer test-token", "Host": "evil.example"},
            )
            with self.assertRaises(HTTPError) as bad_host:
                urlopen(request, timeout=2)
            self.assertEqual(bad_host.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
