"""Spec 038 T026: the tool-use probe against tests/fixtures/fake_provider.py. No real provider."""
import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli, native, native_http, native_probe
from agents_inc.install.paths import InstallPaths

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402

FAKE = "AIzaFAKE-native-probe-2222222222222222222"


def gemini(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1}}


READ = json.dumps({"say": "", "tools": [{"name": "Read", "input": {"file_path": "probe.txt"}}]})


class Probe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.paths = InstallPaths.for_home(self.home)
        store = native_http.key_store(self.home); store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(f"GEMINI_API_KEY={FAKE}\n"); store.chmod(0o600)

    def probe(self, srv):
        return native_probe.probe_one(self.paths, "gemini-flash", env={"AGENTS_INC_NATIVE_GEMINI_URL": srv.url})

    def test_pass_when_the_reply_names_read_and_the_record_is_0600(self):
        with FakeProvider([Reply(200, gemini(READ))]) as srv:
            rec = self.probe(srv)
        self.assertEqual(rec["result"], "pass")
        self.assertIn("Read the file probe.txt", srv.requests[0].json()["contents"][0]["parts"][0]["text"])
        f = self.paths.state / native.PROBE_FILE
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertEqual(native.probe_state(self.paths, "gemini-flash")[0], "pass")
        self.assertNotIn(FAKE, f.read_text())

    def test_fail_when_the_reply_names_no_tool(self):
        with FakeProvider([Reply(200, gemini('{"say": "I cannot read files", "tools": []}'))]) as srv:
            rec = self.probe(srv)
        self.assertEqual((rec["result"], rec["reason"]), ("fail", "reply did not name Read in tools"))
        self.assertEqual(native.probe_state(self.paths, "gemini-flash")[0], "fail")

    def test_429_records_quota_paused_and_no_key_sends_nothing(self):
        with FakeProvider([Reply(429, {"error": {"message": "quota"}})]) as srv:
            self.assertEqual(self.probe(srv)["result"], "quota-paused")
        native_http.key_store(self.home).unlink()
        with FakeProvider([]) as srv:
            rec = self.probe(srv)
            self.assertEqual(srv.requests, [])
        self.assertIn("WB_NATIVE_KEY_MISSING", rec["reason"])

    def test_old_pass_is_stale(self):
        with FakeProvider([Reply(200, gemini(READ))]) as srv:
            native_probe.probe_one(self.paths, "gemini-flash", env={"AGENTS_INC_NATIVE_GEMINI_URL": srv.url},
                                   now=time.time() - native.PROBE_TTL_S - 1)
        self.assertEqual(native.probe_state(self.paths, "gemini-flash")[0], "stale")

    def test_models_probe_cli_and_luna_refused(self):
        with FakeProvider([Reply(200, gemini(READ))]) as srv, \
             mock.patch.dict(os.environ, {"HOME": str(self.home), "AGENTS_INC_NATIVE_GEMINI_URL": srv.url}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(["models", "probe", "gemini-flash"])
        self.assertEqual(code, 0)
        self.assertIn("gemini-flash probe: pass", out.getvalue())
        with self.assertRaises(ValueError): native_probe.probe_one(self.paths, "luna")


if __name__ == "__main__":
    unittest.main()
