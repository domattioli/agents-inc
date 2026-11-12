"""Spec 038 T024: `agents-inc native step`: prompt on stdin, reply on stdout, progress lines on stderr in the
`agents-inc run: event|usage|record <json>` format native/loop.ts parses. Fake provider only."""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli, native, native_http
from agents_inc.install.paths import InstallPaths

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402

FAKE = "AIzaFAKE-native-step-2222222222222222222"
LINE = re.compile(r"^agents-inc run: (event|usage|record|tools) (.*)$")


def gemini(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 7}}


class NativeStep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"; self.home.mkdir()
        self.ws = Path(self.tmp.name) / "ws"; self.ws.mkdir()
        self.paths = InstallPaths.for_home(self.home)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home)}); env.start(); self.addCleanup(env.stop)
        store = native_http.key_store(self.home); store.parent.mkdir(parents=True)
        store.write_text(f"GEMINI_API_KEY={FAKE}\n"); store.chmod(0o600)
        native.allow(self.paths, "gemini", str(self.ws))

    def cli_step(self, srv, prompt):
        os.environ["AGENTS_INC_NATIVE_GEMINI_URL"] = srv.url
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(prompt)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["native", "step", "--model", "gemini-flash", "--cwd", str(self.ws), "--timeout", "5"])
        return code, out.getvalue(), err.getvalue()

    def test_reply_and_progress_lines(self):
        reply = '{"say": "", "tools": [{"name": "Read", "input": {"file_path": "a.txt"}}]}'
        with FakeProvider([Reply(200, gemini(reply))]) as srv:
            code, out, err = self.cli_step(srv, "the prompt")
        self.assertEqual(code, 0)
        self.assertEqual(out, reply)
        kinds = {}
        for line in err.splitlines():
            m = LINE.match(line)
            self.assertIsNotNone(m, line)
            kinds[m[1]] = json.loads(m[2])
        self.assertEqual(kinds["record"]["slug"], "gemini-3.8-flash")
        self.assertEqual(kinds["usage"], {"input_tokens": 40, "cached_input_tokens": 0, "output_tokens": 7})
        self.assertIsInstance(kinds["event"]["text"], str)
        self.assertEqual(srv.requests[0].json()["contents"][0]["parts"][0]["text"], "the prompt")

    def test_exit_codes(self):
        with FakeProvider([Reply(429, {"error": "quota"})]) as srv:
            self.assertEqual(self.cli_step(srv, "p")[0], 75)
        with FakeProvider([]) as srv:
            code, _, err = self.cli_step(srv, "x" * 300_001)
            self.assertEqual(code, 2); self.assertIn("WB_NATIVE_CONTEXT_OVER", err)
            self.assertEqual(srv.requests, [])

    def test_unknown_model_is_3(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(native.step(self.paths, "nope", str(self.ws), "p", 5, out=out, err=err), 3)

    def test_missing_key_is_3_and_sends_nothing(self):
        native_http.key_store(self.home).unlink()
        with FakeProvider([]) as srv:
            code, _, err = self.cli_step(srv, "p")
        self.assertEqual(code, 3); self.assertIn("WB_NATIVE_KEY_MISSING", err); self.assertEqual(srv.requests, [])


if __name__ == "__main__":
    unittest.main()
