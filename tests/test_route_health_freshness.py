"""Spec 014 (#22): backend health freshness in route.sh and wrapper refresh.

Supervisor-owned acceptance tests. Fake HOME only; no network, no model call,
no write to the live ~/.codex-bridge. Key values are fake sentinels.
"""
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "codex-bridge" / "scripts"
ROUTE = SCRIPTS / "route.sh"
FAKE_KEY = "FAKE-SENTINEL-" + "z" * 24

# Loaded by every python3 started with this dir first on PYTHONPATH: replaces
# urllib.request.urlopen so mask.sh's inner python never reaches the network.
SITECUSTOMIZE = '''
import io, json, os, urllib.error, urllib.request

class _Resp(io.BytesIO):
    def getcode(self):
        return 200
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

def _fake_urlopen(req, *a, **k):
    status = int(os.environ.get("FAKE_HTTP_STATUS", "200"))
    if status == 200:
        body = {"choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        return _Resp(json.dumps(body).encode())
    raise urllib.error.HTTPError(getattr(req, "full_url", "x"), status, "fake", {},
                                 io.BytesIO(json.dumps({"message": "fake failure"}).encode()))

urllib.request.urlopen = _fake_urlopen
'''

# Stub curl for oask.sh: writes the body to -o and prints the -w http_code.
CURL = '''#!/usr/bin/env bash
out=""; wfmt=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -w) wfmt="$2"; shift 2 ;;
    *) shift ;;
  esac
done
status="${FAKE_HTTP_STATUS:-200}"
if [[ "$status" == 200 ]]; then
  body='{"choices":[{"message":{"content":"pong"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":1}}'
else
  body='{"error":{"message":"fake failure"}}'
fi
[[ -n "$out" ]] && printf '%s' "$body" > "$out"
[[ "$wfmt" == *http_code* ]] && printf '%s' "$status"
exit 0
'''


def _iso(delta):
    return (datetime.now(timezone.utc) + delta).isoformat()


def _entry(**kw):
    base = {"status": "ok", "cooldown_until": None, "last_error": None, "last_checked": None}
    base.update(kw)
    return base


class _FakeHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        (self.home / ".codex-bridge").mkdir(parents=True)
        self.state = self.home / ".codex-bridge" / "backend-health.json"
        self.shim = Path(self.tmp.name) / "shim"
        self.shim.mkdir()
        (self.shim / "sitecustomize.py").write_text(SITECUSTOMIZE)
        (self.shim / "curl").write_text(CURL)
        (self.shim / "curl").chmod(0o755)
        self.env = {
            "HOME": str(self.home),
            "TMPDIR": str(self.home),
            "PATH": f"{self.shim}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "PYTHONPATH": f"{self.shim}:{REPO}",
            "CODEX_BRIDGE_MODE": "standard",
            "MISTRAL_API_KEY": FAKE_KEY,
            "OPEN_ROUTER_API_KEY": FAKE_KEY,
            "https_proxy": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self, data):
        self.state.write_text(json.dumps(data, indent=2))

    def read(self):
        return json.loads(self.state.read_text())

    def run_script(self, *argv, extra=None):
        env = dict(self.env)
        env.update(extra or {})
        proc = subprocess.run(["bash", *map(str, argv)], env=env, cwd=str(self.home),
                              capture_output=True, text=True, timeout=60)
        self.assertNotIn(FAKE_KEY, proc.stdout + proc.stderr)  # SC-004
        return proc

    def assertFresh(self, value):
        self.assertIsNotNone(value)
        age = datetime.now(timezone.utc) - datetime.fromisoformat(value)
        self.assertLess(abs(age.total_seconds()), 120)


class RouteReportTest(_FakeHome):
    # FR-001, SC-001
    def test_ok_report_clears_old_error_and_sets_last_checked(self):
        self.seed({"mistral": _entry(last_error="API key expired on 2026-09-08",
                                     last_checked="2026-09-10T00:00:00+00:00")})
        proc = self.run_script(ROUTE, "report", "mistral", "ok")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = self.read()["mistral"]
        self.assertFalse(entry["last_error"])
        self.assertFresh(entry["last_checked"])

    def test_ok_report_with_message_does_not_store_it_as_error(self):
        self.seed({"mistral": _entry(last_error="old")})
        self.run_script(ROUTE, "report", "mistral", "ok", "all good")
        self.assertFalse(self.read()["mistral"]["last_error"])

    def test_failure_report_still_records_error(self):
        self.seed({"mistral": _entry()})
        self.run_script(ROUTE, "report", "mistral", "transient", "http 503")
        self.assertEqual(self.read()["mistral"]["last_error"], "http 503")

    def test_report_for_backend_missing_from_existing_file(self):
        self.seed({"gemini-flash": _entry()})
        proc = self.run_script(ROUTE, "report", "openrouter", "ok")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFresh(self.read()["openrouter"]["last_checked"])


class RouteStatusTest(_FakeHome):
    def _rows(self):
        proc = self.run_script(ROUTE, "status")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return {line.split()[0]: line for line in proc.stdout.splitlines() if line.strip()}

    # FR-002, SC-002
    def test_status_marks_old_entries_stale_and_null_unknown(self):
        self.seed({
            "gemini-flash": _entry(last_checked=_iso(-timedelta(days=3))),
            "codex": _entry(last_checked=_iso(-timedelta(hours=1))),
            "haiku": _entry(last_checked=None),
            "sonnet": _entry(last_checked=_iso(timedelta(hours=2))),
        })
        rows = self._rows()
        self.assertIn("stale", rows["gemini-flash"])
        self.assertIn("3d", rows["gemini-flash"])
        self.assertNotIn("stale", rows["codex"])
        self.assertNotIn("unknown", rows["codex"])
        self.assertIn("unknown", rows["haiku"])
        self.assertNotIn("stale", rows["haiku"])
        self.assertNotIn("stale", rows["sonnet"])  # clock skew counts as fresh
        self.assertNotIn("unknown", rows["sonnet"])

    # FR-003 (regression guard: passes before and after)
    def test_pick_ignores_staleness(self):
        self.seed({"gemini-flash": _entry(last_checked=_iso(-timedelta(days=30)))})
        proc = self.run_script(ROUTE, "pick", "digest")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "gemini-flash")


class WrapperRefreshTest(_FakeHome):
    """FR-003a: a standalone wrapper call refreshes the backend entry."""

    def _stale(self, backend):
        return {backend: _entry(last_error="API key expired on 2026-09-08",
                                last_checked="2026-09-10T00:00:00+00:00")}

    def test_mask_ok_clears_error_and_refreshes(self):
        self.seed(self._stale("mistral"))
        proc = self.run_script(SCRIPTS / "mask.sh", "--raw", "ping", extra={"FAKE_HTTP_STATUS": "200"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = self.read()["mistral"]
        self.assertFalse(entry["last_error"])
        self.assertFresh(entry["last_checked"])

    def test_mask_failure_records_error_and_keeps_exit_code(self):
        self.seed({"mistral": _entry(last_checked="2026-09-10T00:00:00+00:00")})
        proc = self.run_script(SCRIPTS / "mask.sh", "--raw", "ping", extra={"FAKE_HTTP_STATUS": "500"})
        self.assertEqual(proc.returncode, 1, proc.stderr)
        entry = self.read()["mistral"]
        self.assertTrue(entry["last_error"])
        self.assertFresh(entry["last_checked"])

    def test_oask_ok_refreshes_entry_missing_from_file(self):
        self.seed({"gemini-flash": _entry()})
        proc = self.run_script(SCRIPTS / "oask.sh", "--raw", "ping",
                               extra={"FAKE_HTTP_STATUS": "200", "MODEL": "vendor/model:free"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = self.read()["openrouter"]
        self.assertFalse(entry.get("last_error"))
        self.assertFresh(entry.get("last_checked"))

    def test_oask_ok_clears_old_error(self):
        self.seed(self._stale("openrouter"))
        proc = self.run_script(SCRIPTS / "oask.sh", "--raw", "ping",
                               extra={"FAKE_HTTP_STATUS": "200", "MODEL": "vendor/model:free"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = self.read()["openrouter"]
        self.assertFalse(entry["last_error"])
        self.assertFresh(entry["last_checked"])

    def test_oask_failure_records_error_and_keeps_exit_code(self):
        self.seed({"openrouter": _entry(last_checked="2026-09-10T00:00:00+00:00")})
        proc = self.run_script(SCRIPTS / "oask.sh", "--raw", "ping",
                               extra={"FAKE_HTTP_STATUS": "500", "MODEL": "vendor/model:free"})
        self.assertEqual(proc.returncode, 1, proc.stderr)
        entry = self.read()["openrouter"]
        self.assertTrue(entry["last_error"])
        self.assertFresh(entry["last_checked"])


if __name__ == "__main__":
    unittest.main()
