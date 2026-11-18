"""022 US4: doctor reports a missing Claude CLI, a nested sandbox, and probes Codex with a real env."""
from __future__ import annotations
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

from agents_inc.install import doctor
from agents_inc.install.doctor import check_install
from agents_inc.install.receipt import InstallReceipt
from tests.test_install_doctor import DoctorWarningsTest

HAS_CLAUDE = lambda *a, **k: "/usr/bin/claude"  # noqa: E731
SANDBOX_OK = lambda: True  # noqa: E731
NET_OK = lambda: True  # noqa: E731  # the dispatch-path probe must not depend on the host network


class ClaudeDoctorTest(unittest.TestCase):
    setUp = DoctorWarningsTest.setUp  # same installed fixture, without re-running its tests
    tearDown = DoctorWarningsTest.tearDown

    def test_missing_claude_is_a_code(self):
        report = check_install(self.paths, models=[], which=lambda *a, **k: None, sandbox_probe=SANDBOX_OK)
        self.assertIn("WB_CLAUDE_NOT_FOUND", report.codes)
        self.assertFalse(report.ready)

    def test_present_claude_is_ready(self):
        report = check_install(self.paths, models=[], which=HAS_CLAUDE, sandbox_probe=SANDBOX_OK, net_probe=NET_OK)
        self.assertNotIn("WB_CLAUDE_NOT_FOUND", report.codes)
        self.assertTrue(report.ready, report)

    def test_nested_sandbox_is_a_warning_only(self):
        with mock.patch.object(doctor.sys, "platform", "darwin"):
            report = check_install(self.paths, models=[], which=HAS_CLAUDE, sandbox_probe=lambda: False, net_probe=NET_OK)
        self.assertIn("WB_SANDBOX_NESTED", report.warnings)
        self.assertNotIn("WB_SANDBOX_NESTED", report.codes)
        self.assertTrue(report.ready)

    def test_no_sandbox_warning_off_darwin(self):
        probe = mock.Mock(return_value=False)
        with mock.patch.object(doctor.sys, "platform", "linux"):
            report = check_install(self.paths, models=[], which=HAS_CLAUDE, sandbox_probe=probe)
        self.assertNotIn("WB_SANDBOX_NESTED", report.warnings)

    def test_live_probe_gets_a_real_env_without_secrets(self):
        codex = Path(self.tmp.name) / "bin" / "codex"
        codex.parent.mkdir()
        codex.write_text("#!/bin/sh\n")
        codex.chmod(0o755)
        real = InstallReceipt.load(self.paths.receipt)
        stub = mock.Mock(release_hash=real.release_hash, codex_path=codex)
        seen = {}

        def runner(argv, **kw):
            seen.update(kw)
            return mock.Mock(returncode=0, stdout="PONG", stderr="")
        base = {"HOME": str(self.paths.home), "USER": "tester", "OPENAI_API_KEY": "k", "MY_TOKEN": "t"}
        with mock.patch("agents_inc.install.doctor.InstallReceipt.load", return_value=stub), \
                mock.patch.object(doctor, "build_codex_argv", return_value=["codex"]), \
                mock.patch.dict(os.environ, base):
            report = check_install(self.paths, live_model="luna", runner=runner, models=[],
                                   which=HAS_CLAUDE, sandbox_probe=SANDBOX_OK, net_probe=NET_OK)
        env = seen["env"]
        self.assertTrue({"HOME", "USER", "PATH"} <= set(env), env)
        self.assertFalse([k for k in env if re.search("KEY|TOKEN|SECRET", k, re.IGNORECASE)])
        self.assertEqual(report.live["code"], "READY")


if __name__ == "__main__":
    unittest.main()
