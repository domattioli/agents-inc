"""Spec 045 FR-005 (#207): a sandboxed caller that launch() would refuse is told `blocked` (exit 69) before checkout-script
pinning, never `snapshot-error`. Callers launch() allows keep the old pin-failure result. Writes only to temp dirs."""
import os
import unittest
from unittest import mock

from agents_inc.install import dispatch
from tests.test_dispatch_grants import GrantsBase, setUpModule, tearDownModule  # noqa: F401


class PinBeforeSandboxTest(GrantsBase):
    def _run(self, env, model="sonnet", reachable=False):
        sdir, _ = dispatch.scripts_dir(self.repo)
        env = dict(env)
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(dispatch, "scripts_dir", return_value=(sdir, "checkout")), \
                mock.patch.object(dispatch, "_pin_scripts", side_effect=PermissionError("state dir not writable")), \
                mock.patch.object(dispatch, "api_reachable", return_value=reachable), \
                mock.patch.object(dispatch, "launch", side_effect=AssertionError("no child may start")):
            if env.get(dispatch.ALLOW_SANDBOXED_ENV) is None:
                os.environ.pop(dispatch.ALLOW_SANDBOXED_ENV, None)
            code, out, err = self._main("--slots", str(self._slots()), "--model", model, "--cwd", str(self.repo),
                                        "--run-dir", str(self.runs))
        return code, out + err, self._spec()

    def test_codex_sandbox_is_blocked_not_snapshot_error(self):
        code, out, spec = self._run({"CODEX_SANDBOX": "seatbelt"}, model="terra")
        self.assertEqual((code, spec["reason"]), (dispatch.EXIT_BLOCKED, "blocked"), out)
        self.assertNotIn("snapshot-error", out)

    def test_allow_sandboxed_keeps_snapshot_error(self):
        code, out, spec = self._run({"CODEX_SANDBOX": "seatbelt", dispatch.ALLOW_SANDBOXED_ENV: "1"}, model="terra")
        self.assertEqual(spec["reason"], "snapshot-error", out)

    def test_claude_in_reachable_claude_sandbox_keeps_snapshot_error(self):
        code, out, spec = self._run({"SANDBOX_RUNTIME": "1"}, reachable=True)
        self.assertEqual(spec["reason"], "snapshot-error", out)


    def test_dry_run_renders_under_each_sandbox_variable(self):
        for env in ({"CODEX_SANDBOX": "seatbelt"}, {"SANDBOX_RUNTIME": "1"}):
            for model in ("terra", "sonnet"):
                with self.subTest(env=env, model=model):
                    self.runs = self.root / f"runs-{model}-{sorted(env)[0]}"
                    sdir, _ = dispatch.scripts_dir(self.repo)
                    with mock.patch.dict(os.environ, env), mock.patch.object(dispatch, "api_reachable", return_value=False), \
                            mock.patch.object(dispatch, "scripts_dir", return_value=(sdir, "checkout")), \
                            mock.patch.object(dispatch, "launch", side_effect=AssertionError("dry run")):
                        os.environ.pop(dispatch.ALLOW_SANDBOXED_ENV, None)
                        code, out, err = self._main("--slots", str(self._slots()), "--model", model, "--cwd",
                                                    str(self.repo), "--run-dir", str(self.runs), "--dry-run")
                    self.assertEqual(code, 0, out + err)
                    self.assertIn("dry-run", out)

    def test_free_model_in_claude_sandbox_reaches_its_own_pre_checks(self):
        sdir, _ = dispatch.scripts_dir(self.repo)
        with mock.patch.dict(os.environ, {"SANDBOX_RUNTIME": "1"}), \
                mock.patch.object(dispatch, "api_reachable", return_value=True), \
                mock.patch.object(dispatch, "scripts_dir", return_value=(sdir, "checkout")), \
                mock.patch.object(dispatch.free_launch, "pre_checks",
                                  return_value=dispatch.free_launch.Refusal("refused-task", "probe")) as pre:
            os.environ.pop(dispatch.ALLOW_SANDBOXED_ENV, None)
            code, out, err = self._main("--slots", str(self._slots()), "--model", "codestral-latest", "--cwd",
                                        str(self.repo), "--run-dir", str(self.runs))
        self.assertTrue(pre.called, out + err)
        self.assertNotIn("caller-sandboxed", out + err)


if __name__ == "__main__":
    unittest.main()
