"""Spec 029 US2: `doctor --probe-dispatch` reports dispatch reachability; no live network (runner and opener injected)."""
from __future__ import annotations
import contextlib
import io
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import unittest
import urllib.error
from unittest import mock

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

from agents_inc.install import cli, doctor, netprobe
from agents_inc.install.dispatch import SANDBOX_FIX, worker_env
from agents_inc.install.doctor import DoctorReport, check_install
from tests.test_install_doctor import DoctorWarningsTest

ANTH, GH = doctor.PROBE_HOSTS
SANDBOX_OK = lambda: True  # noqa: E731
GH_STDERR_CERT = "x509: OSStatus -26276"


def row(host, status, elapsed=0.1): return json.dumps({"host": host, "status": status, "elapsed": elapsed}) + "\n"


def raiser(exc):
    def opener(url, timeout=None): raise exc
    return opener


class ProbeTest(unittest.TestCase):
    def test_http_error_is_reachable(self):
        err = urllib.error.HTTPError("https://x/", 404, "nf", {}, None)
        self.assertEqual(netprobe.probe("x", opener=raiser(err))["status"], "reachable")

    def test_success_is_reachable(self):
        self.assertEqual(netprobe.probe("x", opener=lambda url, timeout=None: object())["status"], "reachable")

    def test_cert_failure_is_cert(self):
        exc = urllib.error.URLError(ssl.SSLCertVerificationError())
        self.assertEqual(netprobe.probe("x", opener=raiser(exc))["status"], "cert")
        self.assertEqual(netprobe.classify(ssl.SSLCertVerificationError()), "cert")

    def test_other_failures_are_blocked(self):
        for exc in (ConnectionRefusedError(), TimeoutError(), socket.gaierror(8, "nodename"),
                    OSError("Tunnel connection failed: 403"), urllib.error.URLError(ConnectionRefusedError())):
            with self.subTest(exc=exc):
                result = netprobe.probe("x", opener=raiser(exc))
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["host"], "x")
                self.assertIn("elapsed", result)

    def test_netprobe_imports_no_package_module(self):
        self.assertNotRegex(open(netprobe.__file__, encoding="utf-8").read(), r"(?m)^\s*(import|from)\s+(agents_inc|workerbees|\.)")


class DoctorProbeTest(unittest.TestCase):
    setUp = DoctorWarningsTest.setUp  # same installed fixture, without re-running its tests
    tearDown = DoctorWarningsTest.tearDown

    def run_doctor(self, child=None, gh_stderr=None, gh="/usr/bin/gh", probe_dispatch=True, calls=None, env=None):
        """child: stdout string, or an exception to raise. gh_stderr: stderr of `gh api /zen`, or an exception."""
        calls = [] if calls is None else calls

        def runner(argv, **kw):
            calls.append((argv, kw))
            if argv[0] == sys.executable:
                if isinstance(child, BaseException): raise child
                return mock.Mock(returncode=0, stdout=child or "", stderr="")
            if isinstance(gh_stderr, BaseException): raise gh_stderr
            return mock.Mock(returncode=1 if gh_stderr else 0, stdout="", stderr=gh_stderr or "")
        which = lambda name, **k: (gh if name == "gh" else "/usr/bin/claude")  # noqa: E731
        with mock.patch.dict(os.environ, env or {}):
            return check_install(self.paths, models=[], runner=runner, which=which, sandbox_probe=SANDBOX_OK,
                                 probe_dispatch=probe_dispatch)

    def test_child_gets_worker_env_and_netprobe(self):
        calls = []
        base = {"HTTPS_PROXY": "http://p", "GITHUB_TOKEN": "t", "MY_TOKEN": "t", "OPENAI_API_KEY": "k"}
        with mock.patch.dict(os.environ, base):
            self.run_doctor(row(ANTH, "reachable") + row(GH, "reachable"), calls=calls)
            expected = worker_env(sys.executable)
        argv, kw = next(c for c in calls if c[0][0] == sys.executable)
        self.assertTrue(argv[1].endswith("netprobe.py"), argv)
        self.assertEqual(argv[2:], list(doctor.PROBE_HOSTS))
        self.assertEqual(kw["env"], expected)
        self.assertNotIn("HTTPS_PROXY", kw["env"])
        self.assertFalse([k for k in kw["env"] if re.search("KEY|TOKEN|SECRET", k, re.I)])

    def test_both_reachable_adds_nothing(self):
        report = self.run_doctor(row(ANTH, "reachable", 0.4) + row(GH, "reachable"))
        self.assertTrue(report.ready, report)
        self.assertEqual(report.probe[ANTH]["status"], "reachable")
        self.assertEqual(report.probe[ANTH]["elapsed"], 0.4)
        self.assertFalse([w for w in report.warnings if w.startswith("WB_GITHUB") or w.startswith("WB_DISPATCH")])
        self.assertIn("probe", report.as_dict())

    def test_without_flag_no_probe_runs(self):
        calls = []
        report = self.run_doctor(probe_dispatch=False, calls=calls)
        self.assertIsNone(report.probe)
        self.assertNotIn("probe", report.as_dict())
        self.assertFalse([c for c in calls if c[0][0] == sys.executable or "netprobe.py" in " ".join(map(str, c[0]))])
        self.assertFalse([c for c in calls if c[0][-2:] == ["api", "/zen"]])

    def test_model_blocked_and_cert_are_blocking_codes(self):
        report = self.run_doctor(row(ANTH, "blocked") + row(GH, "reachable"))
        self.assertFalse(report.ready)
        self.assertIn("WB_DISPATCH_API_BLOCKED", report.codes)
        report = self.run_doctor(row(ANTH, "cert") + row(GH, "reachable"))
        self.assertFalse(report.ready)
        self.assertIn("WB_DISPATCH_API_CERT", report.codes)
        self.assertNotIn("WB_DISPATCH_API_BLOCKED", report.codes)

    def test_cli_prints_one_agents_inc_fix_for_blocked_only(self):
        paths = self.paths

        def show(model_status):
            probe = {ANTH: {"status": model_status, "elapsed": 0.3, "fix": None}, GH: {"status": "reachable", "elapsed": 0.1, "fix": None}}
            codes, _ = doctor._probe_codes(probe, ["WB_SANDBOX_EXCLUDE_MISSING"], env={})
            report = DoctorReport(not codes, tuple(codes), None, (), probe)
            out = io.StringIO()
            with mock.patch.object(cli, "_paths", return_value=paths), mock.patch.object(cli, "check_install", return_value=report) as ci, \
                    contextlib.redirect_stdout(out):
                code = cli.main(["doctor", "--probe-dispatch"])
            self.assertTrue(ci.call_args.kwargs["probe_dispatch"])
            return code, out.getvalue().splitlines()
        code, lines = show("blocked")
        self.assertEqual(code, 1)
        self.assertNotIn("READY", " ".join(lines))
        self.assertIn(f"probe: {ANTH} blocked 0.3s", lines)
        fix = [ln for ln in lines if ln.startswith("FIX:")]
        self.assertEqual(len(fix), 1, lines)
        self.assertIn("agents-inc *", fix[0])
        code, lines = show("cert")
        self.assertEqual(code, 1)
        fix = [ln for ln in lines if ln.startswith("FIX:")]
        self.assertEqual(len(fix), 1, lines)
        self.assertNotIn("agents-inc *", fix[0])
        self.assertIn("TLS", fix[0])

    def test_fix_text_branches_on_sandbox(self):
        def fix_for(warnings, env):
            probe = {ANTH: {"status": "blocked", "elapsed": 1, "fix": None}, GH: {"status": "reachable", "elapsed": 1, "fix": None}}
            doctor._probe_codes(probe, warnings, env=env)
            return probe[ANTH]["fix"]
        self.assertEqual(fix_for([], {"SANDBOX_RUNTIME": "1"}), "dispatch child cannot reach api.anthropic.com; " + SANDBOX_FIX)
        self.assertEqual(fix_for(["WB_SANDBOX_EXCLUDE_MISSING"], {}), "dispatch child cannot reach api.anthropic.com; " + SANDBOX_FIX)
        plain = fix_for([], {})
        self.assertIn("firewall/proxy", plain)
        self.assertNotIn("agents-inc *", plain)

    def test_child_timeout_keeps_partial_rows(self):
        calls = []
        exc = subprocess.TimeoutExpired(["x"], 12, output=row(GH, "reachable"))
        report = self.run_doctor(exc, calls=calls)
        self.assertEqual(report.probe[ANTH]["status"], "blocked")
        self.assertEqual(report.probe[GH]["status"], "reachable")
        self.assertFalse(report.ready)
        child = next(c for c in calls if c[0][0] == sys.executable)
        self.assertEqual(child[1]["timeout"], doctor.PROBE_CHILD_TIMEOUT)
        self.assertLess(doctor.PROBE_CHILD_TIMEOUT + doctor.GH_TIMEOUT, 20)

    def test_silent_child_missing_rows_and_oserror_fail_closed(self):
        for child in (subprocess.TimeoutExpired(["x"], 12, output=None), subprocess.TimeoutExpired(["x"], 12, output=b""),
                      "garbage\n", "", OSError("exec failed")):
            with self.subTest(child=child):
                report = self.run_doctor(child)
                self.assertEqual({r["status"] for r in report.probe.values()}, {"blocked"})
                self.assertIn("WB_DISPATCH_API_BLOCKED", report.codes)
                self.assertFalse(report.ready)

    def test_github_blocked_is_a_warning_only(self):
        report = self.run_doctor(row(ANTH, "reachable") + row(GH, "blocked"))
        self.assertIn("WB_GITHUB_BLOCKED", report.warnings)
        self.assertTrue(report.ready, report)

    def test_gh_x509_gives_github_cert_warning(self):
        report = self.run_doctor(row(ANTH, "reachable") + row(GH, "reachable"), gh_stderr=GH_STDERR_CERT)
        self.assertIn("WB_GITHUB_CERT", report.warnings)
        self.assertTrue(report.ready, report)

    def test_gh_x509_beats_child_blocked(self):
        report = self.run_doctor(row(ANTH, "reachable") + row(GH, "blocked"), gh_stderr=GH_STDERR_CERT)
        self.assertIn("WB_GITHUB_CERT", report.warnings)
        self.assertNotIn("WB_GITHUB_BLOCKED", report.warnings)

    def test_no_gh_means_no_gh_call_and_no_code(self):
        calls = []
        report = self.run_doctor(row(ANTH, "reachable") + row(GH, "reachable"), gh=None, calls=calls)
        self.assertEqual([c for c in calls if c[0][0] != sys.executable], [])
        self.assertFalse([w for w in report.warnings if w.startswith("WB_GITHUB")])

    def test_gh_auth_error_or_timeout_gives_no_code(self):
        for stderr in ("gh: To get started with GitHub CLI, please run: gh auth login",
                       subprocess.TimeoutExpired(["gh"], 6), OSError("gone")):
            with self.subTest(stderr=stderr):
                report = self.run_doctor(row(ANTH, "reachable") + row(GH, "reachable"), gh_stderr=stderr)
                self.assertFalse([w for w in report.warnings if w.startswith("WB_GITHUB")])
                self.assertTrue(report.ready, report)

    def test_fr011_exclusion_warning_not_duplicated(self):
        (self.home / ".claude/settings.json").write_text("{}")  # exists, no `agents-inc *` exclusion
        report = self.run_doctor(row(ANTH, "blocked") + row(GH, "reachable"))
        self.assertEqual(report.warnings.count("WB_SANDBOX_EXCLUDE_MISSING"), 1)
        self.assertFalse([c for c in (*report.codes, *report.warnings) if "EXCLUDE" in c and c != "WB_SANDBOX_EXCLUDE_MISSING"])
        self.assertIn("agents-inc *", report.probe[ANTH]["fix"])


class DocsTest(unittest.TestCase):
    DOCS = ("SKILL.md", "QUICKREF.md")

    def doc(self, name):
        with open(os.path.join(os.path.dirname(__file__), os.pardir, "skills", "workerbee", name), encoding="utf-8") as f: return f.read()

    def test_codex_read_scope_sentence_in_both_docs(self):  # FR-009
        for name in self.DOCS:
            with self.subTest(doc=name):
                self.assertIn("A Codex delegate (astra, sol, terra, luna) cannot read a path outside --cwd; paste the needed excerpts into the prompt.", self.doc(name))

    def test_gh_tls_entry_in_both_docs(self):  # FR-010, SC-004
        for name in self.DOCS:
            with self.subTest(doc=name):
                text = self.doc(name)
                for phrase in ("x509: OSStatus -26276", "GitHub MCP", "outside the sandbox", "not confirmed"):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
