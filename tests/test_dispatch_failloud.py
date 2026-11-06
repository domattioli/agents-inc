"""022 US2: a failed run names its real cause and exit code. Mocked launch, temp dirs, no network."""
from __future__ import annotations
import json
import os
import re
import subprocess
import unittest
from unittest import mock

from agents_inc.install import dispatch
from tests.test_dispatch_cli import GOOD_REPORT, STATUS_RE
from tests.test_dispatch_snapshot_trust import DispatchBase
from tests.test_dispatch_broker import popen_from_run

QUOTA = "You've hit your session limit · resets 8:10pm"
PROXY = "API Error: Couldn't connect through your proxy (ERR_PROXY_TUNNEL)"

_ALLOW = mock.patch.dict(os.environ, {dispatch.ALLOW_SANDBOXED_ENV: "1"})


def setUpModule():
    _ALLOW.start()  # #94: real launch() calls stay allowed when the suite runs inside a sandbox


def tearDownModule():
    _ALLOW.stop()


def launch_result(stdout="", rc=0, stderr="", is_error=False, session="sess-1"):
    def fake(*a, **k):
        return {"rc": rc, "stdout": stdout, "stderr": stderr, "argv": [], "session_id": session, "is_error": is_error}
    return fake


class QuotaBlockedTest(DispatchBase):
    def _check(self, fake, code, reason):
        rc, out, _ = self.dispatch(fake)
        self.assertEqual(rc, code, out)
        spec = self.spec()
        self.assertEqual((spec["outcome"], spec["reason"]), ("red", reason))
        self.assertRegex(out.strip(), STATUS_RE)
        return spec

    def test_rc0_is_error_quota_text_is_quota_paused_75(self):
        spec = self._check(launch_result(QUOTA, rc=0, is_error=True), 75, "quota-paused")
        self.assertTrue(spec["is_error"])

    def test_proxy_stderr_is_blocked_69(self):
        self._check(launch_result("", rc=1, stderr=PROXY), 69, "blocked")

    def test_quota_wins_over_blocked(self):
        self._check(launch_result(QUOTA, rc=1, stderr=PROXY, is_error=True), 75, "quota-paused")

    def test_stderr_quota_with_rc0_is_quota_paused(self):
        self._check(launch_result(GOOD_REPORT, rc=0, stderr=QUOTA), 75, "quota-paused")

    def test_green_turn_with_incidental_429_or_rate_limit_stderr_is_not_a_pause(self):
        """fable F3: a bare 429 or "rate limit" on stderr of a clean, reported turn is noise."""
        shapes = {"traceback-line-429": 'Traceback (most recent call last):\n  File "x.py", line 429, in main\n',
                  "retried-429": "API Error (429 rate limit) · Retrying in 2 seconds... (attempt 1/10)\n"}
        for name, stderr in shapes.items():
            with self.subTest(name=name):
                if self.runs.exists():
                    import shutil
                    shutil.rmtree(self.runs)
                rc, out, _ = self.dispatch(launch_result(GOOD_REPORT, rc=0, stderr=stderr))
                self.assertEqual(rc, 0, out)
                self.assertNotEqual(self.spec().get("reason"), "quota-paused")

    def test_green_turn_anchored_quota_lines_are_still_a_pause(self):
        lines = ("ERROR: 429 Too Many Requests\n", "ERROR: Selected model is at capacity. Please try again.\n",
                 "agents-inc run: codex terra hit a usage or rate limit; retry at unknown\n", QUOTA + "\n")
        for stderr in lines:
            with self.subTest(stderr=stderr):
                if self.runs.exists():
                    import shutil
                    shutil.rmtree(self.runs)
                rc, out, _ = self.dispatch(launch_result(GOOD_REPORT, rc=0, stderr="noise\n" + stderr))
                self.assertEqual(rc, 75, out)

    def test_failed_child_keeps_the_full_text_match(self):
        self._check(launch_result("", rc=1, stderr="API Error (429 rate limit) giving up"), 75, "quota-paused")

    def test_codex_429_through_dispatch_is_75(self):
        """run_codex prints the ERROR line and its own "hit a usage or rate limit" line, then returns 75."""
        from types import SimpleNamespace
        import sys as _sys

        def fake_codex(*a, **k):
            _sys.stderr.write("ERROR: 429 Too Many Requests\n")
            _sys.stderr.write("agents-inc run: codex terra hit a usage or rate limit; retry at unknown\n")
            return 75
        with mock.patch("agents_inc.install.runtime.run_codex", side_effect=fake_codex), \
                mock.patch("agents_inc.install.receipt.InstallReceipt.load", return_value=SimpleNamespace(codex_path=None)), \
                mock.patch("agents_inc.install.cli._efforts", return_value={}):
            rc, out, _ = self.main("--slots", str(self.slots()), "--model", "terra", "--cwd", str(self.repo),
                                   "--run-dir", str(self.runs))
        self.assertEqual(rc, 75, out)
        self.assertEqual((self.spec()["outcome"], self.spec()["reason"]), ("red", "quota-paused"))

    def test_codex_model_at_capacity_through_dispatch_is_75(self):
        """A real sol run printed only this line (rc 1, no report); it is a quota pause, not workers-spawned-missing."""
        from types import SimpleNamespace
        import sys as _sys

        def fake_codex(*a, **k):
            _sys.stderr.write("ERROR: Selected model is at capacity. Please try a different model.\n")
            return 1
        with mock.patch("agents_inc.install.runtime.run_codex", side_effect=fake_codex), \
                mock.patch("agents_inc.install.receipt.InstallReceipt.load", return_value=SimpleNamespace(codex_path=None)), \
                mock.patch("agents_inc.install.cli._efforts", return_value={}):
            rc, out, _ = self.main("--slots", str(self.slots()), "--model", "terra", "--cwd", str(self.repo),
                                   "--run-dir", str(self.runs))
        self.assertEqual(rc, 75, out)
        self.assertEqual((self.spec()["outcome"], self.spec()["reason"]), ("red", "quota-paused"))

    def test_compliant_report_quoting_capacity_is_not_a_pause(self):
        report = GOOD_REPORT.replace("OUT OF SCOPE", "The log said Selected model is at capacity. OUT OF SCOPE", 1)
        rc, out, _ = self.dispatch(launch_result(report, rc=0))
        self.assertEqual(rc, 0, out)

    def test_quota_pattern_is_shared_with_runtime(self):
        from agents_inc.install import runtime
        self.assertIn(runtime.QUOTA_PATTERN, dispatch.QUOTA_RE.pattern)
        for text in ("ERROR: 429 Too Many Requests", "too many requests", "usage limit", "rate limit"):
            self.assertTrue(dispatch.QUOTA_RE.search(text), text)

    def test_compliant_report_quoting_429_is_not_a_pause(self):
        report = GOOD_REPORT.replace("OUT OF SCOPE", "The log said 429 Too Many Requests. OUT OF SCOPE", 1)
        rc, out, _ = self.dispatch(launch_result(report, rc=0))
        self.assertEqual(rc, 0, out)

    def test_compliant_report_quoting_quota_is_not_a_pause(self):
        report = GOOD_REPORT.replace("OUT OF SCOPE", f'The spec quotes "{QUOTA}". OUT OF SCOPE', 1)
        rc, out, _ = self.dispatch(launch_result(report, rc=0, is_error=False))
        self.assertEqual(rc, 0, out)
        self.assertNotEqual(self.spec().get("reason"), "quota-paused")


class OutcomeOrderTest(DispatchBase):
    def test_rc_nonzero_beats_missing_workers_spawned(self):
        rc, out, _ = self.dispatch(launch_result("", rc=1, stderr="boom"))
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.spec()["reason"], "rc-nonzero")

    def test_verifier_error_is_snapshot_error(self):
        real = dispatch.snapshot

        def snap(*args, cwd, **kw):
            return (2, "git error: nope") if args[0] == "verify" else real(*args, cwd=cwd, **kw)
        with mock.patch.object(dispatch, "snapshot", side_effect=snap):
            rc, out, _ = self.dispatch(launch_result(GOOD_REPORT))
        self.assertEqual(rc, 1, out)
        self.assertIn("snapshot=ERROR:rc=2", out)
        self.assertEqual(self.spec()["reason"], "snapshot-error")


class StderrDetailTest(DispatchBase):
    def test_first_stderr_line_on_status_and_run_json(self):
        rc, out, _ = self.dispatch(launch_result("", rc=1, stderr="\nError: not logged in\nsecond line\n"))
        self.assertRegex(out.strip(), STATUS_RE)
        self.assertIn(" detail=Error:_not_logged_in out=", out)
        self.assertEqual(self.spec()["reason_detail"], "Error:_not_logged_in")

    def test_environment_value_is_redacted(self):
        with mock.patch.dict(os.environ, {"MY_PRIVATE_THING": "hunter2hunter2"}):
            rc, out, _ = self.dispatch(launch_result("", rc=1, stderr="Error: hunter2hunter2 rejected"))
        self.assertNotIn("hunter2", out)
        self.assertIn("[redacted]", out)
        self.assertNotIn("hunter2", json.dumps(self.spec()))

    def test_long_detail_is_truncated(self):
        rc, out, _ = self.dispatch(launch_result("", rc=1, stderr="x" * 500))
        self.assertLessEqual(len(self.spec()["reason_detail"].encode()), 200)


class LaunchFailTest(DispatchBase):
    def _raiser(self, exc):
        def fake(*a, **k):
            raise exc
        return fake

    def _assert_failed(self, rc, out, name):
        self.assertEqual(rc, 1, out)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertRegex(out.strip(), STATUS_RE)
        spec = self.spec()
        self.assertIn(spec["run_id"], out)
        self.assertEqual((spec["outcome"], spec["reason"]), ("red", "launch-failed"))
        self.assertIn(name, spec["reason_detail"])
        self.assertIn("rc=-1 report=none lint=installed snapshot=none outcome=red reason=launch-failed detail=", out)

    def test_file_not_found(self):
        rc, out, _ = self.dispatch(self._raiser(FileNotFoundError("claude")))
        self._assert_failed(rc, out, "FileNotFoundError")

    def test_no_sandbox_backend(self):
        rc, out, _ = self.dispatch(self._raiser(RuntimeError("no-sandbox-backend")))
        self._assert_failed(rc, out, "no-sandbox-backend")

    def test_resume_launch_failure(self):
        self.dispatch(launch_result(GOOD_REPORT))
        run = self.run_dir()
        with mock.patch.object(dispatch, "launch", side_effect=self._raiser(RuntimeError("no-sandbox-backend"))):
            rc, out, _ = self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs))
        self._assert_failed(rc, out, "no-sandbox-backend")


class CallerSandboxTest(DispatchBase):
    """#94: dispatch started inside another sandbox stops before any child, red/blocked, exit 69."""

    def _sandboxed(self):
        env = {k: v for k, v in os.environ.items() if k != dispatch.ALLOW_SANDBOXED_ENV}
        return mock.patch.dict(os.environ, dict(env, SANDBOX_RUNTIME="1"), clear=True)

    def _raiser(self, *a, **k):
        raise dispatch.CallerSandboxed("SANDBOX_RUNTIME is set (Claude Code Bash sandbox)")

    def test_caller_sandbox_signals(self):
        self.assertIsNone(dispatch.caller_sandbox({}))
        self.assertIn("SANDBOX_RUNTIME", dispatch.caller_sandbox({"SANDBOX_RUNTIME": "1"}))
        self.assertIn("CODEX_SANDBOX", dispatch.caller_sandbox({"CODEX_SANDBOX": "seatbelt"}))
        self.assertIsNone(dispatch.caller_sandbox({"SANDBOX_RUNTIME": "1", dispatch.ALLOW_SANDBOXED_ENV: "1"}))

    def test_launch_refuses_before_any_child(self):
        run_dir = self.root / "rd"
        run_dir.mkdir()
        with self._sandboxed(), mock.patch.object(dispatch, "api_reachable", return_value=False), \
                mock.patch.object(dispatch.subprocess, "Popen") as popen:
            for kind, model in (("claude", "sonnet"), ("codex", "luna")):
                with self.subTest(kind=kind), self.assertRaises(dispatch.CallerSandboxed):
                    dispatch.launch(kind, model, None, self.repo, "p", run_dir)
        popen.assert_not_called()

    def test_broker_worker_skips_check(self):
        run_dir = self.root / "rd"
        run_dir.mkdir()
        fake = subprocess.CompletedProcess([], 0, stdout=json.dumps({"result": "ok", "session_id": "s"}), stderr="")
        run = mock.Mock(return_value=fake)
        with self._sandboxed(), mock.patch.object(dispatch, "_BROKER_SAFE_WRITES", True), \
                mock.patch.object(dispatch, "sandbox_available", return_value=True), \
                mock.patch.object(dispatch.subprocess, "Popen", side_effect=popen_from_run(run)):
            res = dispatch.launch("claude", "haiku", "low", self.repo, "p", run_dir)
        self.assertEqual(res["rc"], 0)
        run.assert_called_once()

    def test_run_exits_69(self):
        rc, out, _ = self.dispatch(self._raiser)
        self.assertEqual(rc, 69, out)
        self.assertRegex(out.strip(), STATUS_RE)
        spec = self.spec()
        self.assertEqual((spec["outcome"], spec["reason"]), ("red", "blocked"))
        self.assertIn("caller-sandboxed", spec["reason_detail"])
        self.assertIn("do_not_retry_unchanged", spec["reason_detail"])

    def test_resume_exits_69(self):
        self.dispatch(launch_result(GOOD_REPORT))
        run = self.run_dir()
        with mock.patch.object(dispatch, "launch", side_effect=self._raiser):
            rc, out, _ = self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs))
        self.assertEqual(rc, 69, out)
        self.assertEqual(self.spec()["reason"], "blocked")


class MirrorTest(DispatchBase):
    def test_missing_home_repo_is_recorded_and_not_created(self):
        home = self.root / "nope"
        rc, out, err = self.dispatch(launch_result(GOOD_REPORT), extra=("--home-repo", str(home)))
        self.assertEqual(rc, 0, out)
        self.assertFalse(home.exists())
        self.assertEqual(self.spec()["mirror_error"], "home-repo-missing")
        self.assertIn("home-repo-missing", err)

    def test_read_only_destination_keeps_exit_code(self):
        home = self.root / "home-repo"
        runs = home / "specs/consumers/repo/runs"
        runs.mkdir(parents=True)
        runs.chmod(0o500)
        self.addCleanup(runs.chmod, 0o700)
        rc, out, err = self.dispatch(launch_result(GOOD_REPORT), extra=("--home-repo", str(home)))
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.spec()["mirror_error"].startswith("OSError"))
        self.assertIn("mirror", err)


class ExitCodeTest(DispatchBase):
    def _code(self, fake, **kw):
        return self.dispatch(fake, **kw)[0]

    def test_exit_code_map(self):
        cases = [(launch_result(GOOD_REPORT), 0), (launch_result("", rc=1), 1), (launch_result("", rc=2), 2),
                 (launch_result(QUOTA, is_error=True), 75), (launch_result("", rc=1, stderr=PROXY), 69)]
        for fake, code in cases:
            with self.subTest(code=code):
                if self.runs.exists():
                    import shutil
                    shutil.rmtree(self.runs)
                self.assertEqual(self._code(fake), code)

    def test_refused_is_3(self):
        data = json.loads(self.slots().read_text())
        data.pop("OUT_OF_SCOPE")
        path = self.root / "bad.json"
        path.write_text(json.dumps(data))
        self.assertEqual(self._code(launch_result(GOOD_REPORT), slots=path), 3)


class CancelCleanupTest(DispatchBase):
    """Any exception during communicate (KeyboardInterrupt included) kills the group, reaps the child, re-raises."""

    def _proc(self, exc):
        proc = mock.Mock(pid=999999, returncode=None)
        proc.communicate.side_effect = exc
        return proc

    def _check(self, call, exc):
        proc = self._proc(exc)
        with mock.patch("subprocess.Popen", return_value=proc), \
                mock.patch.object(dispatch, "claude_argv", return_value=["fake"]), \
                mock.patch("os.killpg") as kill:
            with self.assertRaises(type(exc)):
                call()
        kill.assert_called_once()
        self.assertEqual(kill.call_args[0][0], 999999)
        proc.wait.assert_called()

    def test_claude_keyboard_interrupt(self):
        run_dir = self.root / "rd"
        run_dir.mkdir()
        self._check(lambda: dispatch.launch("claude", "sonnet", None, self.repo, "p", run_dir), KeyboardInterrupt())

    def test_claude_other_exception(self):
        run_dir = self.root / "rd"
        run_dir.mkdir()
        self._check(lambda: dispatch.launch("claude", "sonnet", None, self.repo, "p", run_dir), RuntimeError("boom"))

    def _deadline_proc(self):
        proc = mock.Mock(pid=999999, returncode=-9)
        proc.communicate.side_effect = [subprocess.TimeoutExpired("fake", 1), subprocess.TimeoutExpired("fake", 10)]
        return proc

    def _check_bounded_reap(self, call, rc_of):
        proc = self._deadline_proc()
        with mock.patch("subprocess.Popen", return_value=proc), \
                mock.patch.object(dispatch, "claude_argv", return_value=["fake"]), \
                mock.patch("os.killpg"):
            res = call()
        self.assertEqual(rc_of(res), 124)
        self.assertEqual(proc.communicate.call_args_list[1].kwargs.get("timeout"), 10)
        proc.stdout.close.assert_called()
        proc.stderr.close.assert_called()

    def test_claude_kill_branch_is_bounded(self):
        """fable F8: a grandchild holding the pipe cannot hang the supervisor past the deadline."""
        run_dir = self.root / "rd"
        run_dir.mkdir()
        self._check_bounded_reap(lambda: dispatch.launch("claude", "sonnet", None, self.repo, "p", run_dir),
                                 lambda res: res["rc"])

    def test_codex_kill_branch_is_bounded(self):
        from agents_inc.install import runtime
        self._check_bounded_reap(lambda: runtime._run_with_deadline(["fake"], "p", None, 1, {}),
                                 lambda res: res.returncode)

    def test_codex_keyboard_interrupt(self):
        from agents_inc.install import runtime
        self._check(lambda: runtime._run_with_deadline(["fake"], "p", None, 1, {}), KeyboardInterrupt())

    def test_codex_other_exception(self):
        from agents_inc.install import runtime
        self._check(lambda: runtime._run_with_deadline(["fake"], "p", None, 1, {}), RuntimeError("boom"))


if __name__ == "__main__":
    unittest.main()
