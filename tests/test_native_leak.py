"""Spec 038 T023 / SC-005: a fake provider key never appears in spawned argv, the child env, stdout, stderr or any file
the run writes. `agents-inc native step` and `native begin|end` run as real child processes against the fake server.

Planned as tests/test_native_keys.py; .gitignore ignores every path with "key" in it, so it carries this name."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agents_inc.install import native, native_http
from agents_inc.install.paths import InstallPaths

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FAKE = "AIzaFAKE-leak-check-3333333333333333333"


class NoKeyLeak(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"; self.home.mkdir()
        self.ws = Path(self.tmp.name) / "ws"; self.ws.mkdir()
        self.paths = InstallPaths.for_home(self.home)
        self.store = native_http.key_store(self.home); self.store.parent.mkdir(parents=True)
        self.store.write_text(f"GEMINI_API_KEY={FAKE}\n"); self.store.chmod(0o600)
        native.allow(self.paths, "gemini", str(self.ws))

    def child(self, srv, *args, stdin=""):
        argv = [sys.executable, "-m", "agents_inc.install.cli", "native", *args]
        env = {k: v for k, v in os.environ.items() if k != "SANDBOX_RUNTIME"}
        env.update(HOME=str(self.home), PYTHONPATH=str(REPO), AGENTS_INC_NATIVE_GEMINI_URL=srv.url)
        self.assertNotIn(FAKE, " ".join(argv))
        self.assertFalse(any(FAKE in v for v in env.values()))
        return subprocess.run(argv, input=stdin, env=env, cwd=str(self.ws), capture_output=True, text=True, timeout=60)

    def files_hold_key(self):
        hits = []
        for root in (self.home, self.ws):
            for p in root.rglob("*"):
                if p.is_file() and p != self.store and FAKE.encode() in p.read_bytes(): hits.append(str(p))
        return hits

    def test_step_success_and_failures_leak_nothing(self):
        replies = [Reply(200, {"candidates": [{"content": {"parts": [{"text": '{"say": "hi", "tools": []}'}]}}]}),
                   Reply(429, {"error": f"quota for {FAKE}"}),
                   Reply(401, {"error": f"key {FAKE} rejected"})]
        with FakeProvider(replies) as srv:
            runs = [self.child(srv, "step", "--model", "gemini-flash", "--cwd", str(self.ws), "--timeout", "10", stdin="prompt")
                    for _ in replies]
            runs.append(self.child(srv, "--model", "gemini-flash", "begin", "--session", "s", "--agent", "a", "--cwd", str(self.ws)))
            runs.append(self.child(srv, "--model", "gemini-flash", "end", "--session", "s", "--agent", "a", "--cwd", str(self.ws), "--outcome", "done"))
            runs.append(self.child(srv, "status", "--json"))
        self.assertEqual([r.returncode for r in runs[:3]], [0, 75, 1])
        self.assertTrue(all(r.returncode == 0 for r in runs[3:]), [r.stderr for r in runs[3:]])
        for r in runs:
            self.assertNotIn(FAKE, r.stdout)
            self.assertNotIn(FAKE, r.stderr)
        self.assertEqual(self.files_hold_key(), [])
        # The key did reach the provider, in the header and nowhere else.
        for req in srv.requests:
            self.assertEqual({k.lower(): v for k, v in req.headers.items()}["x-goog-api-key"], FAKE)
            self.assertNotIn(FAKE, req.path + req.body.decode())
        self.assertEqual(len(srv.requests), 3)


if __name__ == "__main__":
    unittest.main()
