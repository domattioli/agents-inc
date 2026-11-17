"""Codex callers are diagnosed before private snapshot storage is touched."""
import os
from unittest import mock

from agents_inc.install import dispatch
from tests.test_dispatch_snapshot_trust import DispatchBase, ok_launch


class CodexSandboxPreflightTest(DispatchBase):
    def test_codex_sandbox_refused_before_pinning(self):
        env = {"CODEX_SANDBOX": "seatbelt", "AGENTS_INC_ALLOW_SANDBOXED": "0"}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(dispatch, "_pin_scripts", side_effect=PermissionError("unwritable")) as pin, \
             mock.patch.object(dispatch, "launch", side_effect=ok_launch()) as launch:
            rc, out, _ = self.main("--slots", str(self.slots()), "--model", "astra", "--cwd", str(self.repo),
                                   "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_BLOCKED, out)
        self.assertIn("caller-sandboxed-codex", out)
        self.assertIn("or_terminal", out)
        self.assertFalse(pin.called)
        self.assertFalse(launch.called)
        self.assertEqual(self.spec()["reason"], "blocked")

    def test_unsandboxed_launch_continues(self):
        with mock.patch.object(dispatch, "caller_sandbox", return_value=None), \
             mock.patch.object(dispatch, "launch", side_effect=ok_launch()) as launch:
            rc, out, _ = self.main("--slots", str(self.slots()), "--model", "astra", "--cwd", str(self.repo),
                                   "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        self.assertTrue(launch.called)

    def test_dry_run_does_not_apply_caller_preflight(self):
        env = {"CODEX_SANDBOX": "seatbelt", "AGENTS_INC_ALLOW_SANDBOXED": "0"}
        with mock.patch.dict(os.environ, env), mock.patch.object(dispatch, "launch") as launch:
            rc, out, _ = self.main("--slots", str(self.slots()), "--model", "astra", "--cwd", str(self.repo),
                                   "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("dry-run", out)
        self.assertFalse(launch.called)
