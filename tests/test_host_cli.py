"""Spec 047 FR-001, FR-004, FR-005: host CLI versions, install method, registry lookup, 24 h record. Offline."""
import json
import os
import stat
import tempfile
import unittest
import urllib.error
import unittest.mock
from pathlib import Path

from agents_inc.install import host_cli

DAY = 24 * 3600


def _script(directory: Path, name: str, out: str) -> Path:
    path = directory / name
    path.write_text(f"#!/bin/sh\necho '{out}'\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


class HostCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.path = str(self.bin)

    def test_installed_version_parses_and_skips_missing(self):
        _script(self.bin, "codex", "codex-cli 0.159.2")
        _script(self.bin, "claude", "2.1.327 (Claude Code)")
        self.assertEqual(host_cli.installed_version("codex", path=self.path), "0.159.2")
        self.assertEqual(host_cli.installed_version("claude", path=self.path), "2.1.327")
        self.assertIsNone(host_cli.installed_version("nope", path=self.path))

    def test_install_method_by_resolved_target(self):
        npm = self.tmp / "lib/node_modules/@openai/codex/bin"
        npm.mkdir(parents=True)
        _script(npm, "codex.js", "x")
        (self.bin / "codex").symlink_to(npm / "codex.js")
        self.assertEqual(host_cli.install_method("codex", "@openai/codex", path=self.path), "npm")
        brew = self.tmp / "Cellar/codex/1/bin"
        brew.mkdir(parents=True)
        _script(brew, "codex", "x")
        other = self.tmp / "b2"
        other.mkdir()
        (other / "codex").symlink_to(brew / "codex")
        self.assertEqual(host_cli.install_method("codex", "@openai/codex", path=str(other)), "brew")
        plain = self.tmp / "b3"
        plain.mkdir()
        _script(plain, "codex", "x")
        self.assertEqual(host_cli.install_method("codex", "@openai/codex", path=str(plain)), "unknown")

    def test_update_command(self):
        self.assertEqual(host_cli.update_command("npm", "@openai/codex", "codex"), "npm install -g @openai/codex@latest")
        self.assertEqual(host_cli.update_command("brew", "@openai/codex", "codex"), "brew upgrade codex")
        both = host_cli.update_command("unknown", "@openai/codex", "codex")
        self.assertIn("npm install -g @openai/codex@latest", both)
        self.assertIn("brew upgrade codex", both)
        self.assertIn("install method unknown", both)

    def test_request_url_and_headers(self):
        req = host_cli.registry_request("@openai/codex")
        self.assertEqual(req.full_url, "https://registry.npmjs.org/@openai%2Fcodex/latest")
        self.assertEqual({k.lower() for k in req.headers}, {"user-agent", "accept"})
        self.assertEqual(req.get_header("User-agent"), "agents-inc-doctor")
        self.assertEqual(host_cli.registry_request("@anthropic-ai/claude-code").full_url,
                         "https://registry.npmjs.org/@anthropic-ai%2Fclaude-code/latest")

    def test_latest_version_never_raises(self):
        self.assertEqual(host_cli.latest_version("@openai/codex", fetch=lambda pkg: "0.170.0"), "0.170.0")
        def boom(pkg): raise urllib.error.URLError("offline")
        self.assertIsNone(host_cli.latest_version("@openai/codex", fetch=boom))
        def slow(pkg): raise TimeoutError()
        self.assertIsNone(host_cli.latest_version("@openai/codex", fetch=slow))

    def test_refresh_records_and_reuses_within_24h(self):
        _script(self.bin, "codex", "codex-cli 0.159.2")
        state = self.tmp / "state"
        calls = []
        def fetch(pkg):
            calls.append(pkg)
            return "0.170.0"
        recs = host_cli.refresh(state, now=1000.0, fetch=fetch, path=self.path)
        self.assertEqual(recs["codex"]["installed"], "0.159.2")
        self.assertEqual(recs["codex"]["latest"], "0.170.0")
        self.assertNotIn("claude", recs)  # not on this PATH
        data = json.loads((state / "host-cli-versions.json").read_text())
        self.assertEqual(data["codex"]["checked_at"], 1000.0)
        host_cli.refresh(state, now=1000.0 + DAY - 1, fetch=fetch, path=self.path)
        self.assertEqual(calls, ["@openai/codex"])  # fresh record: no second lookup
        host_cli.refresh(state, now=1000.0 + DAY + 1, fetch=fetch, path=self.path)
        self.assertEqual(len(calls), 2)

    def test_refresh_offline_and_readonly_state(self):
        _script(self.bin, "codex", "codex-cli 0.159.2")
        def boom(pkg): raise urllib.error.URLError("offline")
        recs = host_cli.refresh(self.tmp / "s", now=1.0, fetch=boom, path=self.path)
        self.assertIsNone(recs["codex"]["latest"])
        ro = self.tmp / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            recs = host_cli.refresh(ro / "state", now=1.0, fetch=lambda p: "0.170.0", path=self.path)
            self.assertEqual(recs["codex"]["latest"], "0.170.0")
        finally:
            ro.chmod(0o700)

    def test_cached_is_read_only_and_expires(self):
        state = self.tmp / "state"
        state.mkdir()
        (state / "host-cli-versions.json").write_text(json.dumps(
            {"codex": {"installed": "0.159.2", "latest": "0.170.0", "checked_at": 1000.0}}))
        self.assertTrue(host_cli.cached(state, now=1000.0 + 10)["codex"]["stale"])  # L1: no identity, no trust at any age
        self.assertEqual(host_cli.cached(self.tmp / "absent", now=1.0), {})

    def test_outdated_lines(self):
        recs = {"codex": {"installed": "0.159.2", "latest": "0.170.0", "checked_at": 1.0},
                "claude": {"installed": "2.1.327", "latest": "2.1.327", "checked_at": 1.0}}
        lines = host_cli.outdated_lines(recs, method=lambda name, pkg: "npm")
        self.assertEqual(lines, ["HOST_CLI_OUTDATED codex 0.159.2 < 0.170.0; update: npm install -g @openai/codex@latest"])


class HostCliReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"; self.bin.mkdir()
        _script(self.bin, "codex", "codex-cli 0.159.2")

    def test_offline_lookup_reused_for_24h_not_every_run(self):  # G1 (24 h for failures too, per D52.1)
        calls = []
        def boom(pkg):
            calls.append(pkg); raise urllib.error.URLError("offline")
        state = self.tmp / "s"
        host_cli.refresh(state, now=1000.0, fetch=boom, path=str(self.bin))
        rec = host_cli.refresh(state, now=1060.0, fetch=boom, path=str(self.bin))
        self.assertEqual(len(calls), 1)
        self.assertIn("offline", rec["codex"]["error"])  # H4: the reason is kept
        self.assertTrue(rec["codex"]["reused"])
        host_cli.refresh(state, now=1000.0 + host_cli.TTL + 1, fetch=boom, path=str(self.bin))
        self.assertEqual(len(calls), 2)

    def test_opted_out_one_rule(self):  # G6
        for value, want in (("1", True), ("true", True), ("yes", True), ("0", False), ("", False), (None, False)):
            with self.subTest(value=value):
                env = {} if value is None else {"AGENTS_INC_NO_UPDATE_CHECK": value}
                self.assertEqual(host_cli.opted_out(env), want)
        with unittest.mock.patch.dict(os.environ, {"AGENTS_INC_NO_UPDATE_CHECK": "yes"}):
            self.assertIsNone(host_cli._fetch("@openai/codex"))  # no request


class HostCliK1K2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"; self.bin.mkdir()
        self.exe = _script(self.bin, "codex", "codex-cli 0.159.2")

    def test_record_holds_binary_identity(self):  # K1
        recs = host_cli.refresh(self.tmp / "s", now=1.0, fetch=lambda p: "0.170.0", path=str(self.bin))
        st = os.stat(os.path.realpath(self.exe))
        stored = json.loads((self.tmp / "s" / host_cli.RECORD).read_text())["codex"]["binary"]
        self.assertEqual(stored, {"path": os.path.realpath(self.exe), "mtime_ns": st.st_mtime_ns, "size": st.st_size,
                                  "inode": st.st_ino})

    def test_cached_trusts_installed_at_any_age_while_binary_unchanged(self):  # K1
        host_cli.refresh(self.tmp / "s", now=1.0, fetch=lambda p: "0.170.0", path=str(self.bin))
        later = 1.0 + 30 * DAY
        rec = host_cli.cached(self.tmp / "s", now=later, path=str(self.bin))["codex"]
        self.assertEqual(rec["installed"], "0.159.2")
        self.assertFalse(rec["stale"])
        self.assertIsNone(rec["latest"])  # the registry answer is older than 24 h
        os.utime(self.exe, (5, 5))
        self.assertTrue(host_cli.cached(self.tmp / "s", now=later, path=str(self.bin))["codex"]["stale"])

    def test_retargeted_symlink_with_old_target_intact_is_stale(self):  # L1
        a = self.tmp / "a"; a.mkdir(); old = _script(a, "codex", "codex-cli 0.159.2")
        b = self.tmp / "b"; b.mkdir(); new = _script(b, "codex", "codex-cli 0.170.0")
        link = self.tmp / "lb"; link.mkdir(); (link / "codex").symlink_to(old)
        host_cli.refresh(self.tmp / "s", now=1.0, fetch=lambda p: "0.170.0", path=str(link))
        self.assertFalse(host_cli.cached(self.tmp / "s", now=2.0, path=str(link))["codex"]["stale"])
        (link / "codex").unlink(); (link / "codex").symlink_to(new)
        self.assertTrue(old.exists())
        self.assertTrue(host_cli.cached(self.tmp / "s", now=2.0, path=str(link))["codex"]["stale"])

    def test_older_write_keeps_newer_entry(self):  # L2
        state = self.tmp / "s"; state.mkdir()
        (state / host_cli.RECORD).write_text(json.dumps(
            {"codex": {"installed": "0.170.0", "latest": "0.170.0", "checked_at": 500.0}}))
        host_cli._write(state, {"codex": {"installed": "0.159.2", "latest": None, "checked_at": 100.0},
                                "claude": {"installed": "2.1.327", "latest": "2.1.327", "checked_at": 100.0}})
        data = json.loads((state / host_cli.RECORD).read_text())
        self.assertEqual(data["codex"]["checked_at"], 500.0)
        self.assertEqual(data["claude"]["checked_at"], 100.0)
        self.assertEqual([p.name for p in state.iterdir()], [host_cli.RECORD])  # no temp file left behind

    def test_lookups_bounded_to_3s_total_and_concurrent(self):  # K2
        import time as _t
        _script(self.bin, "claude", "2.1.327 (Claude Code)")
        def slow(pkg):
            _t.sleep(10); return "9.9.9"
        start = _t.monotonic()
        recs = host_cli.refresh(self.tmp / "s", now=1.0, fetch=slow, path=str(self.bin))
        took = _t.monotonic() - start
        self.assertLess(took, host_cli.TIMEOUT + 2)  # both lookups together, not 2 x 3 s
        for name in ("codex", "claude"):
            self.assertIsNone(recs[name]["latest"])
            self.assertIn("timeout", recs[name]["lookup_error"])


if __name__ == "__main__":
    unittest.main()
