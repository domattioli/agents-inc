import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("delegation_bench", ROOT / "tools" / "delegation_bench.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def _completed(stdout="", stderr="", rc=0):
    return subprocess.CompletedProcess(args=["claude"], returncode=rc, stdout=stdout, stderr=stderr)


class TrialEnvTest(unittest.TestCase):
    def test_keeps_headless_auth_and_drops_other_claude_vars(self):
        env = {"PATH": "/usr/bin", "CLAUDE_CODE_OAUTH_TOKEN": "x", "ANTHROPIC_API_KEY": "x",
               "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "s", "CLAUDE_CODE_EFFORT": "high", "SANDBOX_RUNTIME": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            out = bench.trial_env(Path("/tmp/fake-home"))
        self.assertEqual(out["CLAUDE_CODE_OAUTH_TOKEN"], "x")
        self.assertEqual(out["ANTHROPIC_API_KEY"], "x")
        for k in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_EFFORT", "SANDBOX_RUNTIME"):
            self.assertNotIn(k, out)
        self.assertEqual(out["HOME"], "/tmp/fake-home")
        self.assertTrue(out["PATH"].startswith("/tmp/fake-home/.local/bin:"))

    def test_absent_auth_vars_are_not_invented(self):
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            out = bench.trial_env(Path("/tmp/fake-home"))
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", out)
        self.assertNotIn("ANTHROPIC_API_KEY", out)


class AuthPreflightTest(unittest.TestCase):
    def setUp(self):
        bench._AUTH_OK.clear()

    def test_logged_out_raises_with_fix(self):
        with mock.patch.object(bench.subprocess, "run", return_value=_completed('{"loggedIn": false}')) as run:
            with self.assertRaises(SystemExit) as cm:
                bench.auth_preflight(Path("/tmp/fake-home"), "A0")
        msg = str(cm.exception)
        self.assertIn("claude setup-token", msg)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", msg)
        self.assertEqual(run.call_args.args[0], ["claude", "auth", "status"])
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], "/tmp/fake-home")
        self.assertNotIn("A0", bench._AUTH_OK)

    def test_logged_in_passes_and_runs_once_per_arm(self):
        with mock.patch.object(bench.subprocess, "run", return_value=_completed('{"loggedIn": true}')) as run:
            bench.auth_preflight(Path("/tmp/fake-home"), "B")
            bench.auth_preflight(Path("/tmp/fake-home"), "B")
            bench.auth_preflight(Path("/tmp/fake-home"), "C")
        self.assertEqual(run.call_count, 2)

    def test_non_json_output_counts_as_logged_out(self):
        with mock.patch.object(bench.subprocess, "run", return_value=_completed("Not logged in", rc=1)):
            with self.assertRaises(SystemExit):
                bench.auth_preflight(Path("/tmp/fake-home"), "A1")

    def test_run_trial_skips_preflight_with_flag(self):
        with mock.patch.object(bench, "auth_preflight") as pre, \
                mock.patch.object(bench, "arm_home", return_value=Path("/tmp/fake-home")), \
                mock.patch.object(bench.subprocess, "run", side_effect=RuntimeError("stop")), \
                mock.patch.object(bench.shutil, "copy"):
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(RuntimeError):      # stops at git init, before any claude call
                    bench.run_trial(Path(td), "S", "A0", 0, 10, auth_check=False)
        pre.assert_not_called()

    def test_run_trial_calls_preflight_by_default(self):
        with mock.patch.object(bench, "auth_preflight", side_effect=SystemExit("no")) as pre, \
                mock.patch.object(bench, "arm_home", return_value=Path("/tmp/fake-home")), \
                mock.patch.object(bench.subprocess, "run", return_value=_completed()), \
                mock.patch.object(bench.shutil, "copy"):
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(SystemExit):
                    bench.run_trial(Path(td), "S", "A0", 0, 10)
        pre.assert_called_once()

    def test_cli_lists_no_auth_check(self):
        with mock.patch.object(bench.sys, "argv", ["delegation_bench.py", "--help"]), \
                mock.patch.object(bench.sys, "stdout") as out:
            with self.assertRaises(SystemExit) as cm:
                bench.main()
        self.assertEqual(cm.exception.code, 0)
        text = "".join(c.args[0] for c in out.write.call_args_list)
        self.assertIn("--no-auth-check", text)


class ArmHomeInstallFailureTest(unittest.TestCase):
    def test_install_failure_writes_log_and_names_it(self):
        err = subprocess.CalledProcessError(1, ["agents-inc", "install", "--without-codex"],
                                            output="partial out\n", stderr="line one\nWB_HOST_UNWIRED: boom\n")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with mock.patch.object(bench, "install_shim"), \
                    mock.patch.object(bench.subprocess, "run", side_effect=err) as run:
                with self.assertRaises(SystemExit) as cm:
                    bench.arm_home(out, "B")
            log = out / "homes" / "B" / "install.log"
            msg = str(cm.exception)
            self.assertTrue(log.exists())
            self.assertIn(str(log), msg)
            self.assertIn("WB_HOST_UNWIRED: boom", msg)
            self.assertIn("install exited 1", msg)
            text = log.read_text()
            self.assertIn("partial out", text)
            self.assertIn("WB_HOST_UNWIRED: boom", text)
            self.assertEqual(run.call_count, 1)
            self.assertFalse((out / "homes" / "B" / ".bench-ready").exists())

    def test_non_installed_arm_touches_no_subprocess(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(bench, "install_shim"), \
                    mock.patch.object(bench.subprocess, "run", side_effect=AssertionError("no subprocess")):
                home = bench.arm_home(Path(td), "A0")
            self.assertTrue((home / ".bench-ready").exists())


if __name__ == "__main__":
    unittest.main()
