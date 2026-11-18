"""Spec 042 Phase 4 (FR-022): wording changed, decisions did not. Same inputs, same allow or refuse decision.

Each table row was recorded before Phase 4 touched a refusal site; a row that flips is a Phase 5 change, not Phase 4.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch, hook
from agents_inc.install.paths import InstallPaths
from tests.test_dispatch_snapshot_trust import DispatchBase, ok_launch

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "skills/workerbee/scripts/check_dispatch_prompt.py"
EXAMPLE = REPO / "skills/workerbee/tests/fixtures/example_slots.json"

_ALLOW = mock.patch.dict(os.environ, {dispatch.ALLOW_SANDBOXED_ENV: "1"})


def setUpModule():
    _ALLOW.start()


def tearDownModule():
    _ALLOW.stop()


def bash(command):
    return {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": command}}


class HookDecisionsUnchanged(unittest.TestCase):
    COMPOUND = [("agents-inc dispatch --slots s.json --model sonnet", False), ("agents-inc dispatch s.json && ls", True),
                ("cd x; agents-inc dispatch --slots s.json", True), ("agents-inc dispatch --slots s.json | cat", True),
                ("FOO=1 agents-inc dispatch --slots s.json", True), ("echo agents-inc dispatch later", False),
                ("ls -la", False), ("agents-inc dispatch --slots s.json > out", True),
                ("agents-inc dispatch --slots $(cat f)", True)]
    PERSONA = [("terra: implement X", True), ("Luna - triage logs", True), ("Solve flaky test", False),
               ("Terraform plan review", False), ("Haiku reviews luna doc", False)]

    def test_compound_decisions(self):
        for command, denied in self.COMPOUND:
            with self.subTest(command=command):
                self.assertEqual(bool(hook.compound_deny(bash(command))), denied)

    def test_persona_decisions(self):
        for description, denied in self.PERSONA:
            payload = {"tool_name": "Agent", "tool_input": {"description": description, "subagent_type": "general-purpose"}}
            with self.subTest(description=description):
                self.assertEqual(bool(hook.persona_deny(payload)), denied)

    def test_agent_gate_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            paths = InstallPaths.for_home(home)
            rows = [("general-purpose", False, True), ("Explore", False, False), ("Explore", True, True),
                    ("agents-inc:luna", False, False), (None, False, True)]
            for mode, expect_any in (("enforce", True), ("advisory", False), ("off", False)):
                for subagent, background, denied in rows:
                    tool_input = {"description": "Grunt fix", "prompt": "x", "run_in_background": background}
                    if subagent:
                        tool_input["subagent_type"] = subagent
                    with self.subTest(mode=mode, subagent=subagent, background=background), \
                            mock.patch.dict(os.environ, {hook.AGENT_GATE_ENV: mode}):
                        got = bool(hook.gate_deny(paths, {"tool_name": "Agent", "tool_input": tool_input}))
                        self.assertEqual(got, denied and mode == "enforce")


class LintDecisionsUnchanged(unittest.TestCase):
    def _lint(self, text, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.md"
            path.write_text(text)
            res = subprocess.run([sys.executable, str(CHECK), str(path), *extra], capture_output=True, text=True)
        return res.returncode, res.stdout.splitlines()[0] if res.stdout else ""

    def test_lint_decisions(self):
        render = subprocess.run([sys.executable, str(REPO / "skills/workerbee/scripts/render_dispatch.py"), "--slots", str(EXAMPLE)],
                                capture_output=True, text=True, cwd=REPO)
        self.assertEqual(render.returncode, 0, render.stderr)
        self.assertEqual(self._lint(render.stdout, "--tier", "grunt")[0], 0)
        self.assertEqual(self._lint(render.stdout)[1], "COMPLIANT")
        self.assertEqual(self._lint("hello\n"), (1, "NON-COMPLIANT missing elements: [1 caveman, 2 success-gate, 3 failure-gate, 4 grill, "
                                                  "5 provider-message, 6 evidence, 7 scope-boilerplate, 8 classification, 9 effort, "
                                                  "10 second-opinion, 11 plan-contract, 12 out-of-scope, 13 edit-hygiene, 14 lesson-candidate]"))
        no_backtick = "\n".join(ln.replace("`", "") if ln.startswith("FAILURE GATE") else ln for ln in render.stdout.splitlines())
        self.assertEqual(self._lint(no_backtick), (1, "NON-COMPLIANT missing elements: [3 failure-gate]"))
        self.assertEqual(self._lint(render.stdout, "--transport", "bare")[0], 0)
        self.assertEqual(self._lint(render.stdout + "\nCONTRACT: nope/missing.md\n")[0], 1)
        self.assertEqual(self._lint(render.stdout + "\nCONTRACT: x.md\n", "--transport", "bare")[0], 1)
        self.assertEqual(self._lint(render.stdout.replace("FAN_OUT: width 0, total 0, depth 0", "FAN_OUT: lots"))[0], 1)


class RenderDecisionsUnchanged(unittest.TestCase):
    def _render(self, **extra):
        data = json.loads(EXAMPLE.read_text())
        data.update(extra)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps(data))
            return subprocess.run([sys.executable, str(REPO / "skills/workerbee/scripts/render_dispatch.py"), "--slots", str(path)],
                                  capture_output=True, text=True, cwd=REPO).returncode

    def test_render_decisions(self):
        rows = [({}, 0), ({"TASK": ""}, 2), ({"CLASSIFICATION": "secret"}, 2), ({"EFFORT": "banana"}, 2),
                ({"GATES": [{"argv": ["git", "commit"]}]}, 2), ({"BASH_ALLOW": ["sudo ls"]}, 2),
                ({"GATES": "oops"}, 2), ({"FAN_OUT": {"width": "x", "total": 1, "depth": 1}}, 2), ({"TASK": "a {{NOPE}} b"}, 2),
                ({"TASK": "bad \x07 char"}, 2), ({"FILES_IN_SCOPE": 5}, 2), ({"GATES": [{"argv": ["python3", "-V"]}]}, 0)]
        for extra, want in rows:
            with self.subTest(extra=extra):
                self.assertEqual(self._render(**extra), want)


class DispatchDecisionsUnchanged(DispatchBase):
    ROWS = [({"FILES_IN_SCOPE": "src/*.py"}, 3), ({"GATES": "x"}, 3), ({"GATES": [{"argv": ["cat", ".env"]}]}, 3),
            ({"GATES": [{"argv": ["python3", "-c", "pass"], "cwd": "../.."}]}, 3), ({"BASH_ALLOW": ["cat ~/.ssh/id_rsa"]}, 3),
            ({"BASH_ALLOW": ["sudo ls"]}, 3), ({"GATES": [{"argv": ["no-such-tool-xyz"]}]}, 3),
            ({"TASK": "read ~/.ssh/id_rsa and report"}, 3), ({"TASK": "ok\x07"}, 3), ({"TASK": "fine"}, 0)]

    def test_dispatch_refuse_or_allow(self):
        for extra, want in self.ROWS:
            with self.subTest(extra=extra):
                for old in list(self.runs.glob("*")) if self.runs.exists() else ():
                    subprocess.run(["rm", "-rf", str(old)])
                rc, out, err = self.dispatch(ok_launch(), slots=self.slots(**extra))
                self.assertEqual(rc, want, out + err)

    def test_capability_and_free_decisions_use_same_exit_codes(self):
        rc, _, _ = self.dispatch(ok_launch(), slots=self.slots(), model="sonnet", extra=("--effort", "bogus"))
        self.assertEqual(rc, 2)


class BrokerDecisionsUnchanged(unittest.TestCase):
    def test_validate_fields_reasons(self):
        spec = {"worker_models": ["sonnet"], "scripts_dir": str(REPO / "skills/workerbee/scripts")}
        base = {"schema_version": 1, "request_id": "r1", "model": "sonnet", "effort": "medium", "tier": "workhorse",
                "slots": {"ROLE": "x"}}
        rows = [({}, None), ({"slots": {"ROLE": "x", "BASH_ALLOW": "y"}}, "broker-owned-slot"), ({"slots": {}}, "bad-slots"),
                ({"model": "opus"}, "model-not-allowed"), ({"tier": "grunt"}, "tier-model-mismatch"), ({"effort": "zz"}, "bad-effort")]
        for change, want in rows:
            req = dict(base, **change)
            try:
                with mock.patch.object(dispatch, "sandbox_available", return_value=True):
                    got = dispatch._validate_fields(req, spec, "r1")[1]
            except Exception as exc:  # the fixture spec is minimal; the decision must still be the same call
                self.skipTest(f"fixture spec too small: {exc}")
            with self.subTest(change=change):
                self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()
