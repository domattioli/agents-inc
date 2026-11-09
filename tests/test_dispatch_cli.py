"""Tests for `agents-inc dispatch` (agents_inc/install/dispatch.py). Writes only to temp dirs."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import shutil
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from agents_inc.install import cli, dispatch
from tests.test_dispatch_broker import popen_from_run

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "skills/workerbee/tests/fixtures/example_slots.json"
STATUS_RE = re.compile(r"^dispatch \S+ \S+ rc=-?\d+ report=(COMPLIANT|NON-COMPLIANT:\[.*\]|none) "
                       r"lint=(checkout|installed) snapshot=(clean|CHANGED:\S+|ERROR:\S+|TAMPERED|none) outcome=(green|red|unverified)"
                       r"( reason=\S+)?( detail=\S+)? out=\S+stdout(\.\d+)?\.md"
                       r"( \(resume with --resume /\S+\))?$")
GOOD_REPORT = ("caveman ultra confirmed. GRILL: none. [verified] gate rc=0 exit code 0.\n"
               "OUT OF SCOPE / INCOMPLETE: none\nWORKERS SPAWNED: 0\n")

_ALLOW = mock.patch.dict(os.environ, {dispatch.ALLOW_SANDBOXED_ENV: "1"})


def setUpModule():
    _ALLOW.start()  # #94: real launch() calls stay allowed when the suite runs inside a sandbox


def tearDownModule():
    _ALLOW.stop()


def _git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    for cmd in (["git", "init", "-q"], ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                                        "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


class CliBase(unittest.TestCase):
    """Temp git repo, fake HOME and the dispatch CLI helpers; holds no tests of its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = _git_repo(self.root)
        self.runs = self.root / "runs"
        # Home without handoff-lint so results do not depend on the host.
        self.env = mock.patch.dict("os.environ", {"HOME": str(self.root)})
        self.env.start()
        self.env_home = mock.patch.dict("os.environ", {}, clear=False)
        self.env_home.start()
        os.environ.pop("AGENTS_INC_HOME_REPO", None)

    def tearDown(self):
        self.env_home.stop()
        self.env.stop()
        self.tmp.cleanup()

    def _slots(self, drop=None, **extra) -> Path:
        data = json.loads(EXAMPLE.read_text())
        if drop:
            data.pop(drop)
        data.setdefault("GATES", [{"argv": [sys.executable, "-c", "pass"]}])  # a passing gate keeps green paths green
        data.update(extra)
        path = self.root / "slots.json"
        path.write_text(json.dumps(data))
        return path

    def _main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(["dispatch", *argv])
        return rc, out.getvalue(), err.getvalue()

    def _run_dir(self) -> Path:
        dirs = list(self.runs.iterdir())
        self.assertEqual(len(dirs), 1)
        return dirs[0]


class DispatchCliTest(CliBase):
    def test_argument_parsing(self):
        captured = {}
        with mock.patch.object(dispatch, "run", side_effect=lambda a: captured.setdefault("a", a) and 0):
            self._main("--slots", "s.json", "--model", "sonnet", "--effort", "high", "--cwd", "/x",
                       "--tier", "grunt", "--run-dir", "/r", "--dry-run")
        a = captured["a"]
        self.assertEqual((a.slots, a.model, a.effort, a.cwd, a.tier, a.run_dir, a.dry_run),
                         ("s.json", "sonnet", "high", "/x", "grunt", "/r", True))

    def test_dispatch_cli_rejects_non_grunt_tier(self):
        with mock.patch.object(dispatch, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["dispatch", "--slots", "s.json", "--model", "haiku", "--cwd", "/x", "--tier", "workhorse"])
        self.assertEqual(ctx.exception.code, 2)
        run.assert_not_called()

    def test_render_refusal_missing_out_of_scope(self):
        rc, out, _ = self._main("--slots", str(self._slots(drop="OUT_OF_SCOPE")), "--model", "haiku",
                                "--cwd", str(self.repo), "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 3)
        self.assertIn("refused", out)
        self.assertIn("OUT_OF_SCOPE", (self._run_dir() / "lint.txt").read_text())

    def test_render_refuses_control_character_with_offset(self):
        """026 US4 FR-019: render_dispatch.py exits 2, names slot and offset, prints nothing on stdout."""
        task = "abcde‮fgh"  # offset 5
        proc = subprocess.run([sys.executable, str(REPO / "skills/workerbee/scripts/render_dispatch.py"),
                               "--slots", str(self._slots(TASK=task))], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stderr.strip(), "render: slot TASK has control character U+202E at offset 5")
        self.assertEqual(proc.stdout, "")

    def test_lint_refusal_prints_missing(self):
        with mock.patch.object(dispatch, "lint_prompt", return_value=([12], "")):
            rc, out, _ = self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                                    "--run-dir", str(self.runs))
        self.assertEqual(rc, 3)
        self.assertIn("NON-COMPLIANT:[12 out-of-scope]", out)

    def test_dry_run(self):
        rc, out, _ = self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                                "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        run = self._run_dir()
        for name in ("prompt.md", "lint.txt", "snapshot.json", "slots.json", "run.json"):
            self.assertTrue((run / name).is_file(), name)
        self.assertEqual(out.strip(), f"dispatch {run.name} haiku dry-run prompt={run / 'prompt.md'}")
        self.assertTrue((run / "lint.txt").read_text().startswith("COMPLIANT"))

    def test_dry_run_verify_gate_is_one_plain_command(self):
        """#92: every verify command in the prompt names the absolute snapshot path, with no cd or &&."""
        rc, out, _ = self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                                "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        run = self._run_dir()
        cmds = [c for c in re.findall(r"`([^`]*)`", (run / "prompt.md").read_text())
                if "pre_dispatch_snapshot.py verify" in c]
        self.assertTrue(cmds)
        for cmd in cmds:
            snap = shlex.split(cmd)[3]
            self.assertEqual(snap, str(run / "snapshot.json"), cmd)
            self.assertTrue(Path(snap).is_absolute(), cmd)
            self.assertNotIn("&&", cmd)
            self.assertFalse(cmd.strip().startswith("cd "), cmd)

    def _chain_line(self, model):
        rc, out, _ = self._main("--slots", str(self._slots()), "--model", model, "--cwd", str(self.repo),
                                "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        run = self._run_dir()
        self.assertTrue((run / "lint.txt").read_text().startswith("COMPLIANT"))
        return [ln for ln in (run / "prompt.md").read_text().splitlines() if ln.startswith("REPORTING CHAIN:")]

    def test_dry_run_derives_claude_chain(self):
        self.assertEqual(self._chain_line("haiku"), [
            "REPORTING CHAIN: haiku reports to sonnet; sonnet reports to fable; fable reports to the operator"])

    def test_dry_run_derives_codex_chain(self):
        self.assertEqual(self._chain_line("luna"), [
            "REPORTING CHAIN: luna reports to terra; terra reports to astra; astra reports to the operator"])

    def _launch(self, model, stdout=GOOD_REPORT, extra=()):
        calls = {}

        def fake(kind, model_, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, codex_write=False,
                 **_):
            calls.update(kind=kind, model=model_, cwd=cwd, prompt=prompt, permission_mode=permission_mode,
                         effort=effort, codex_write=codex_write)
            argv = dispatch.claude_argv(model_, permission_mode, effort=effort) if kind == "claude" else ["run_codex", model_]
            return {"rc": 0, "stdout": stdout, "stderr": "", "argv": argv,
                    "session_id": "sess-1" if kind == "claude" else None}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            rc, out, _ = self._main("--slots", str(self._slots()), "--model", model, "--cwd", str(self.repo),
                                    "--run-dir", str(self.runs), *extra)
        return rc, out, calls

    def _assert_launched(self, rc, out):
        run = self._run_dir()
        for name in ("stdout.md", "run.json", "verify.txt", "stderr.txt"):
            self.assertTrue((run / name).is_file(), name)
        self.assertRegex(out.strip(), STATUS_RE)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("report=COMPLIANT lint=installed snapshot=clean", out)
        self.assertEqual(rc, 0, out)
        return json.loads((run / "run.json").read_text())

    def _ledger_rows(self):
        path = self.root / ".local/state/agents-inc/host-ledger/.workerbees/ledger.jsonl"
        if not path.is_file():
            return []
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

    def test_launched_run_leaves_one_dispatched_ledger_row(self):
        rc, out, _ = self._launch("sonnet")
        spec = self._assert_launched(rc, out)
        rows = self._ledger_rows()
        self.assertEqual(len(rows), 2)  # dispatched, then returned
        self.assertEqual((rows[0]["id"], rows[0]["status"], rows[0]["source"], rows[0]["model"]),
                         (spec["run_id"], "dispatched", "dispatch", "sonnet"))
        self.assertNotIn("ledger_error", spec)

    def test_ledger_write_failure_does_not_change_outcome(self):
        with mock.patch("agents_inc.host_ledger.record_dispatch_run", return_value=False):
            rc, out, _ = self._launch("sonnet")
        spec = self._assert_launched(rc, out)
        self.assertEqual(spec["ledger_error"], "ledger write failed")

    def test_ledger_return_failure_does_not_change_outcome(self):
        with mock.patch("agents_inc.host_ledger.record_dispatch_return", return_value=False):
            rc, out, _ = self._launch("sonnet")
        spec = self._assert_launched(rc, out)
        self.assertEqual(spec["ledger_return_error"], "ledger write failed")
        self.assertNotIn("ledger_error", spec)

    def test_launched_run_also_leaves_a_returned_row(self):
        rc, out, _ = self._launch("sonnet")
        spec = self._assert_launched(rc, out)
        rows = self._ledger_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[1]["id"], rows[1]["status"]), (spec["run_id"], spec["outcome"]))
        self.assertNotIn("ledger_return_error", spec)

    def test_dry_run_and_refusals_leave_no_ledger_row(self):
        self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                   "--run-dir", str(self.runs), "--dry-run")
        with mock.patch.object(dispatch, "lint_prompt", return_value=([12], "")):
            self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                       "--run-dir", str(self.runs))
        self.assertEqual(self._ledger_rows(), [])

    def test_launch_codex_mocked(self):
        rc, out, calls = self._launch("sol")
        spec = self._assert_launched(rc, out)
        self.assertEqual(calls["kind"], "codex")
        self.assertEqual(calls["effort"], "medium")
        self.assertEqual(spec["argv"], ["run_codex", "sol"])
        self.assertTrue(calls["codex_write"])  # default acceptEdits: writes like a Claude subagent
        self.assertTrue(spec["codex_write"])
        self.assertEqual(spec["effort"], "medium")
        self.assertIsNone(spec["session_id"])

    def test_launch_claude_mocked(self):
        rc, out, calls = self._launch("sonnet")
        spec = self._assert_launched(rc, out)
        self.assertEqual(calls["kind"], "claude")
        self.assertIsNone(calls["effort"])
        argv = spec["argv"]
        self.assertEqual(argv[1:], ["-p", "--model", "claude-sonnet-5-5", "--permission-mode", "acceptEdits",
                                    "--output-format", "stream-json", "--verbose"])
        self.assertIsNone(spec["effort"])
        self.assertNotIn("--effort", argv)
        self.assertEqual(spec["session_id"], "sess-1")
        self.assertIn("SUCCESS GATE", calls["prompt"].upper())

    def test_launch_claude_explicit_effort(self):
        rc, out, calls = self._launch("opus", extra=("--effort", "low"))
        spec = self._assert_launched(rc, out)
        self.assertEqual(calls["effort"], "low")
        self.assertEqual(spec["effort"], "low")
        self.assertEqual(spec["argv"][-2:], ["--effort", "low"])

    def test_fan_out_recorded_in_run_json(self):
        rc, out, _ = self._launch("sonnet")
        spec = self._assert_launched(rc, out)
        self.assertEqual(spec["fan_out"], {"width": 0, "total": 0, "depth": 0})
        self.assertEqual(spec["workers_spawned"], 0)
        self.assertEqual(spec["outcome"], "green")

    def test_workers_over_fan_out_total_is_red(self):
        report = GOOD_REPORT.replace("WORKERS SPAWNED: 0", "WORKERS SPAWNED: 2")
        rc, out, _ = self._launch("sonnet", stdout=report)
        spec = json.loads((self._run_dir() / "run.json").read_text())
        self.assertEqual(spec["workers_spawned"], 2)
        self.assertEqual(spec["outcome"], "red")
        self.assertNotEqual(rc, 0)

    def test_workers_spawned_unknown_is_red_missing(self):
        report = GOOD_REPORT.replace("WORKERS SPAWNED: 0", "WORKERS SPAWNED: unknown")
        rc, out, _ = self._launch("sonnet", stdout=report)
        spec = json.loads((self._run_dir() / "run.json").read_text())
        self.assertEqual(spec["outcome"], "red")
        self.assertEqual(spec["reason"], "workers-spawned-missing")
        self.assertIn("outcome=red reason=workers-spawned-missing", out)
        self.assertNotEqual(rc, 0)

    def test_status_line_green_has_outcome(self):
        rc, out, _ = self._launch("sonnet")
        self.assertIn(" outcome=green out=", out)
        self.assertNotIn("reason=", out)

    def test_over_total_status_has_reason(self):
        report = GOOD_REPORT.replace("WORKERS SPAWNED: 0", "WORKERS SPAWNED: 2")
        _, out, _ = self._launch("sonnet", stdout=report)
        self.assertIn("outcome=red reason=fan-out-over-total", out)

    def test_resume_sums_attempts_against_total(self):
        self._launch("haiku")
        run = self._run_dir()
        path = run / "run.json"
        spec = json.loads(path.read_text())
        spec["fan_out"] = {"width": 3, "total": 6, "depth": 2}
        spec["workers_spawned_attempts"] = [4]
        spec["workers_spawned"] = 4
        path.write_text(json.dumps(spec))
        report = GOOD_REPORT.replace("WORKERS SPAWNED: 0", "WORKERS SPAWNED: 3")

        def fake(*a, **k):
            return {"rc": 0, "stdout": report, "stderr": "", "argv": [], "session_id": "sess-1"}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            rc, out, _ = self._main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs))
        spec = json.loads(path.read_text())
        self.assertEqual(spec["workers_spawned_attempts"], [4, 3])
        self.assertEqual(spec["workers_spawned"], 7)
        self.assertEqual(spec["outcome"], "red")
        self.assertEqual(spec["reason"], "fan-out-over-total")
        self.assertNotEqual(rc, 0)

    def test_mirror_unset_prints_stderr_line(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            dispatch._mirror({"cwd": "/x/repo", "run_id": "r1"}, self.root, None)
        self.assertEqual(err.getvalue().strip(), "run spec not mirrored: no home repo")

    def test_mirror_copies_run_spec_to_home_repo(self):
        home = self.root / "home"
        home.mkdir()
        fake = lambda *a, **k: {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": None}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            args = argparse.Namespace(slots=str(self._slots()), model="sonnet", effort=None, cwd=str(self.repo),
                                      tier=None, run_dir=str(self.runs), dry_run=False, resume=None,
                                      message=None, home_repo=str(home))
            with contextlib.redirect_stdout(io.StringIO()):
                rc = dispatch.run(args)
        run = self._run_dir()
        dest = home / "specs" / "consumers" / "repo" / "runs" / run.name
        self.assertTrue((dest / "run.json").is_file())
        self.assertTrue((dest / "prompt.md").is_file())

    def test_codex_write_slot(self):
        self.assertTrue(dispatch.codex_write({}))  # default acceptEdits: same as a Claude subagent
        self.assertTrue(dispatch.codex_write({"PERMISSION_MODE": "bypassPermissions"}))
        self.assertFalse(dispatch.codex_write({"PERMISSION_MODE": "plan"}))
        self.assertFalse(dispatch.codex_write({"PERMISSION_MODE": "default"}))
        self.assertFalse(dispatch.codex_write({"CODEX_WRITE": "no"}))
        self.assertFalse(dispatch.codex_network({}))
        self.assertTrue(dispatch.codex_network({"CODEX_NETWORK": " Yes "}))
        self.assertTrue(dispatch.codex_write({"CODEX_WRITE": " True ", "PERMISSION_MODE": "plan"}))

    def test_launch_codex_passes_write_to_run_codex(self):
        seen = []

        def fake_run_codex(*a, **kw):
            seen.append((kw.get("tools"), kw.get("write"), kw.get("network")) + ((kw["lead_dir"],) if kw.get("lead_dir") else ()))
            self.assertEqual(kw.get("extra_read"),
                             (self.runs / "pre_dispatch_snapshot.py", self.runs / "snapshot.json"))
            return 0
        receipt = mock.Mock(codex_path="/bin/true")
        with mock.patch("agents_inc.install.runtime.run_codex", side_effect=fake_run_codex), \
                mock.patch("agents_inc.install.cli._paths") as paths, \
                mock.patch("agents_inc.install.cli._efforts", return_value={}), \
                mock.patch("agents_inc.install.receipt.InstallReceipt.load", return_value=receipt):
            dispatch.launch("codex", "sol", "medium", self.repo, "p", self.runs)
            dispatch.launch("codex", "sol", "medium", self.repo, "p", self.runs, codex_write=True)
            dispatch.launch("codex", "sol", "medium", self.repo, "p", self.runs, codex_write=True, codex_network=True)
            dispatch.launch("codex", "sol", "medium", self.repo, "p", self.runs, codex_network=True)
            # #68: a Lead always has tools, writes per CODEX_WRITE, and never gets network
            dispatch.launch("codex", "sol", "medium", self.repo, "p", self.runs, codex_write=True, codex_network=True,
                            lead_dir=self.root / "lead")
            dispatch.launch("codex", "sol", "medium", self.repo, "p", self.runs, lead_dir=self.root / "lead")
        self.assertEqual(seen, [(False, False, False), (True, True, False), (True, True, True), (False, False, False),
                                (True, True, False, self.root / "lead"), (True, False, False, self.root / "lead")])

    def test_lead_roster_follows_rungs(self):
        fan = {"width": 1, "total": 2, "depth": 1}
        allow = {"ALLOWLIST": "sol, luna, haiku, sonnet"}
        self.assertEqual(dispatch.lead_roster("astra", allow, fan), ["sol", "luna", "sonnet", "haiku"])
        self.assertEqual(dispatch.lead_roster("terra", allow, fan), ["luna", "haiku"])  # Workhorse: Grunt only
        self.assertEqual(dispatch.lead_roster("luna", allow, fan), [])
        self.assertEqual(dispatch.lead_roster("sol", allow, {"width": 0, "total": 0, "depth": 0}), [])
        self.assertEqual(dispatch.lead_roster("sol", allow, None), [])
        self.assertEqual(dispatch.lead_roster("sol", {"ALLOWLIST": "none -- do all work yourself"}, fan), [])

    def test_codex_dispatch_with_fan_out_runs_as_lead(self):
        seen = {}

        def fake(*a, **k):
            lead = k.get("lead_dir")
            seen["lead"] = lead
            seen["run"] = json.loads((lead / "run.json").read_text())
            return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": None}
        slots = self._slots(ALLOWLIST="luna, haiku", FAN_OUT="width 1, total 2, depth 1",
                            ROLE="Workhorse terra, dispatched by CoS (opus) in repo.")
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            rc, out, _ = self._main("--slots", str(slots), "--model", "terra", "--cwd", str(self.repo),
                                    "--run-dir", str(self.runs))
        self.assertIsNotNone(seen.get("lead"), out)
        self.assertFalse(seen["lead"].is_relative_to(self.repo))
        self.assertEqual(seen["run"]["worker_models"], ["luna", "haiku"])
        self.assertEqual(seen["run"]["fan_out"], {"width": 1, "total": 2, "depth": 1})
        spec = json.loads((self._run_dir() / "run.json").read_text())
        self.assertEqual((spec["lead_workers"], spec["lead_dir"]), (["luna", "haiku"], str(seen["lead"])))
        shutil.rmtree(seen["lead"], ignore_errors=True)

    def test_codex_dispatch_without_fan_out_is_not_a_lead(self):
        seen = {}

        def fake(*a, **k):
            seen["lead"] = k.get("lead_dir")
            return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": None}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            self._main("--slots", str(self._slots(ALLOWLIST="luna")), "--model", "terra", "--cwd", str(self.repo),
                       "--run-dir", str(self.runs))
        self.assertIn("lead", seen)
        self.assertIsNone(seen["lead"])

    def test_parse_workers_spawned(self):
        self.assertEqual(dispatch.parse_workers_spawned("x\n- WORKERS SPAWNED: 3\n"), 3)
        self.assertIsNone(dispatch.parse_workers_spawned("no count here"))
        self.assertEqual(dispatch.parse_workers_spawned("[verified] WORKERS SPAWNED: 2.\n"), 2)

    def test_claude_launch_builds_command_and_parses_json(self):
        fake = subprocess.CompletedProcess([], 0, stdout=json.dumps({"result": "hi", "session_id": "s9"}), stderr="")
        run = mock.Mock(return_value=fake)
        with mock.patch.object(dispatch.subprocess, "Popen", side_effect=popen_from_run(run)):
            res = dispatch.launch("claude", "opus", "high", self.repo, "PROMPT", self.root, "plan")
        argv = run.call_args.args[0]
        self.assertEqual(argv[1:], ["-p", "--model", dispatch.CLAUDE_MODELS["opus"], "--permission-mode", "plan",
                                    "--output-format", "stream-json", "--verbose", "--effort", "high"])
        self.assertEqual(run.call_args.kwargs["input"], "PROMPT")
        self.assertEqual(run.call_args.kwargs["cwd"], str(self.repo))
        self.assertEqual((res["stdout"], res["session_id"]), ("hi", "s9"))

    def test_unsupported_slug_exits_2(self):
        for slug in ("gemini", "mistral", "openrouter"):
            rc, out, _ = self._main("--slots", str(self._slots()), "--model", slug, "--run-dir", str(self.runs))
            self.assertEqual(rc, 2)
            self.assertEqual(out.strip(), f"dispatch: {slug} not supported, use agent.sh")

    def test_slots_that_are_not_an_object_exit_2(self):
        # A JSON list used to reach `slots.get` and die with an AttributeError traceback (Docker stress 2026-10-23).
        for text in ("[]", "\"x\"", "3", "null"):
            path = self.root / "bad_slots.json"
            path.write_text(text)
            rc, out, err = self._main("--slots", str(path), "--model", "haiku", "--run-dir", str(self.runs), "--dry-run")
            self.assertEqual(rc, 2, text)
            self.assertIn("dispatch: slots must be a JSON object", out + err)
        self.assertFalse(self.runs.exists())

    def test_missing_cwd_and_unwritable_run_dir_exit_2(self):
        rc, out, err = self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.root / "nope"),
                                  "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 2)
        self.assertIn("dispatch: cwd is not a directory", out + err)
        blocker = self.root / "blocker"
        blocker.write_text("a file, not a directory")
        rc, out, err = self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                                  "--run-dir", str(blocker), "--dry-run")
        self.assertEqual(rc, 2)
        self.assertIn("dispatch: cannot create run directory", out + err)

    def test_claude_bad_effort_exits_2(self):
        for effort in ("ultra", "xhigh"):
            rc, out, err = self._main("--slots", str(self._slots()), "--model", "haiku", "--effort", effort,
                                      "--cwd", str(self.repo), "--run-dir", str(self.runs))
            self.assertEqual(rc, 2)
            self.assertIn(f"effort {effort} not allowed for haiku", err)
            self.assertFalse(self.runs.exists())

    def test_resume_codex_without_thread_exits_2(self):
        self._launch("terra")
        run = self._run_dir()
        rc, _, err = self._main("--resume", run.name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, 2)
        self.assertIn("no session id recorded", err)

    def test_resume_codex_uses_thread_id(self):
        self._launch("terra")
        run = self._run_dir()
        spec = json.loads((run / "run.json").read_text())
        spec["session_id"] = "thread-abc"
        (run / "run.json").write_text(json.dumps(spec))
        seen = {}

        def fake(kind, model, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, codex_write=False, **_):
            seen.update(kind=kind, resume=resume, prompt=prompt, effort=effort)
            return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": "thread-abc"}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            rc, out, _ = self._main("--resume", run.name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        self.assertEqual(seen, {"kind": "codex", "resume": "thread-abc", "prompt": "go on", "effort": "medium"})
        self.assertTrue((run / "stdout.1.md").is_file())
        self.assertTrue((run / "verify.1.txt").is_file())
        self.assertEqual(len(json.loads((run / "run.json").read_text())["resumes"]), 1)

    def test_resume_claude_uses_session(self):
        self._launch("haiku")
        run = self._run_dir()
        seen = {}

        def fake(kind, model, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, codex_write=False, **_):
            seen.update(resume=resume, prompt=prompt, effort=effort)
            return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": "sess-1"}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            rc, out, _ = self._main("--resume", run.name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        self.assertEqual(seen, {"resume": "sess-1", "prompt": "go on", "effort": None})
        self.assertTrue((run / "stdout.1.md").is_file())

    def test_resume_accepts_run_dir_path(self):
        self._launch("haiku")
        run = self._run_dir()
        seen = {}

        def fake(kind, model, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, codex_write=False, **_):
            seen.update(resume=resume)
            return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": "sess-1"}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            rc, out, _ = self._main("--resume", str(run), "--message", "go on")
        self.assertEqual(rc, 0, out)
        self.assertEqual(seen, {"resume": "sess-1"})

    def test_quota_pause_reason(self):
        self.assertEqual(dispatch._outcome({}, "NON-COMPLIANT", 0, 1, "workers-spawned-missing", quota=True), ("red", "quota-paused"))
        self.assertEqual(dispatch._outcome({}, "NON-COMPLIANT", 0, 1, None), ("red", "rc-nonzero"))
        self.assertTrue(dispatch.QUOTA_RE.search("You've hit your session limit \u00b7 resets 2:50pm"))

    def test_allow_paths(self):
        self.assertEqual(dispatch.allow_paths("none (read-only scout)"), [])
        self.assertEqual(dispatch.allow_paths("agents_inc/install/cli.py\ntests/test_x.py, README.md"),
                         ["agents_inc/install/cli.py", "tests/test_x.py", "README.md"])


    def test_handoff_lint_findings_are_advisory(self):
        with mock.patch.object(dispatch, "_handoff_lint", return_value=(1, "H2:provenance:L3: finding\n")):
            rc, out, _ = self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                                    "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("refused", out)
        lint = (self._run_dir() / "lint.txt").read_text()
        self.assertTrue(lint.startswith("COMPLIANT"))
        self.assertIn("advisory", lint)
        self.assertIn("H2:provenance:L3", lint)

    def _report_log(self, rc, report):
        path = self.root / "report.md"
        path.write_text(report)
        with mock.patch.object(dispatch, "_handoff_lint", return_value=(rc, "H2:x\n" if rc else "")):
            return dispatch.lint_report(path)

    def test_report_handoff_lint_is_advisory(self):
        path = self.root / "r.md"
        path.write_text("anything")
        module = SimpleNamespace(check_report=lambda text: [])
        with mock.patch.object(dispatch, "_load", return_value=module), \
                mock.patch.object(dispatch, "_handoff_lint", return_value=(1, "H2:...\n")):
            missing, log = dispatch.lint_report(path)
        self.assertEqual(missing, [])
        self.assertIn("advisory", log)

    def test_report_contract_missing_still_blocks(self):
        for rc in (0, 1):
            missing, _ = self._report_log(rc, "no mandatory elements here\n")
            self.assertTrue(missing, rc)
            self.assertNotIn("handoff-lint", missing)

    def _preflight_run(self, **extra):
        slots = self._slots(**extra)
        with mock.patch.object(dispatch, "launch", side_effect=_fake_launch()) as launch:
            rc, out, _ = self._main("--slots", str(slots), "--model", "haiku", "--cwd", str(self.repo),
                                    "--run-dir", str(self.runs))
        return rc, out, launch

    def test_preflight_missing_gate_refused(self):
        rc, out, launch = self._preflight_run(GATES=[{"argv": ["no-such-tool-xyz", "--x"]}])
        self.assertEqual(rc, 3, out)
        self.assertIn("refused-capability", out)
        self.assertIn("gate[0] executable not found: no-such-tool-xyz", out)
        launch.assert_not_called()
        spec = json.loads((self._run_dir() / "run.json").read_text())
        self.assertEqual(spec["outcome"], "refused-capability")

    def test_preflight_present_gate_passes(self):
        self.assertEqual(dispatch.capability_preflight([{"argv": ["sh"], "cwd": "."}], [], self.repo), [])

    def test_preflight_missing_bash_allow_refused(self):
        self.assertEqual(dispatch.capability_preflight([], ["no-such-tool-xyz -v"], self.repo),
                         ["bash_allow[0] executable not found: no-such-tool-xyz"])

    def test_preflight_relative_gate_resolves_in_cwd(self):
        sub = self.repo / "sub"
        sub.mkdir(exist_ok=True)
        tool = sub / "run.sh"
        tool.write_text("#!/bin/sh\n")
        gates = [{"argv": ["./run.sh"], "cwd": "sub"}]
        self.assertEqual(dispatch.capability_preflight(gates, [], self.repo)[0],
                         "gate[0] executable not found: ./run.sh")
        tool.chmod(0o755)
        self.assertEqual(dispatch.capability_preflight(gates, [], self.repo), [])

    def test_preflight_skips_gates_under_ceiling(self):
        with mock.patch.object(dispatch, "_GRANT_CEILING", ([], [])):
            rc, out, _ = self._main("--slots", str(self._slots(GATES=[{"argv": ["no-such-tool-xyz"]}])),
                                    "--model", "haiku", "--cwd", str(self.repo), "--run-dir", str(self.runs),
                                    "--dry-run")
        self.assertNotIn("refused-capability", out)

    def test_preflight_runs_on_dry_run(self):
        rc, out, _ = self._main("--slots", str(self._slots(GATES=[{"argv": ["no-such-tool-xyz"]}])),
                                "--model", "haiku", "--cwd", str(self.repo), "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 3, out)
        self.assertIn("gate[0] executable not found", out)

    def test_real_snapshot_path_injected_before_lint(self):
        seen = {}
        real_lint = dispatch.lint_prompt

        def spy(path, tier, model=None, **kw):
            seen["text"] = path.read_text()
            return real_lint(path, tier, model, **kw)

        with mock.patch.object(dispatch, "lint_prompt", side_effect=spy):
            rc, out, _ = self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(self.repo),
                                    "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        run = self._run_dir()
        prompt = (run / "prompt.md").read_text()
        snap = str(run / "snapshot.json")
        self.assertIn(f"verify {snap}", prompt)
        self.assertNotIn(dispatch.SNAPSHOT_PLACEHOLDER, prompt)
        self.assertNotIn("/tmp/dispatch/pre_dispatch.json", prompt)
        self.assertEqual(seen["text"], prompt)

    def test_inject_snapshot_appends_when_no_placeholder(self):
        self.assertEqual(dispatch.inject_snapshot("A\n", "/s.json"), "A\nSNAPSHOT: /s.json\n")
        self.assertEqual(dispatch.inject_snapshot("x <snapshot> y <snapshot>", "/s"), "x /s y /s")

    def test_claude_model_ids_exact(self):
        self.assertEqual(dispatch.CLAUDE_MODELS, {
            "fable": "claude-fable-5-1", "opus": "claude-opus-5-5",
            "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"})
        self.assertEqual(dispatch.claude_argv("haiku", "plan")[3], "claude-haiku-5-5")

    def test_claude_argv_effort(self):
        self.assertEqual(dispatch.claude_argv("opus", "plan", effort="low")[-2:], ["--effort", "low"])
        self.assertNotIn("--effort", dispatch.claude_argv("opus", "plan"))
        self.assertEqual(dispatch.claude_argv("opus", "plan", "s1", "max")[-4:],
                         ["--effort", "max", "--resume", "s1"])


def _fake_launch(stdout=GOOD_REPORT, during=None):
    """A launch() stand-in; during(cwd) runs as the delegate's turn."""
    def fake(kind, model, effort, cwd, prompt, run_dir, *a, **k):
        if during:
            during(Path(cwd))
        return {"rc": 0, "stdout": stdout, "stderr": "", "argv": [], "session_id": "sess-1"}
    return fake


class RunDirIgnoreTest(CliBase):
    """025 US4 (#106): an explicit --run-dir inside --cwd must be git-ignored."""

    def _go(self, run_dir, cwd=None):
        with mock.patch.object(dispatch, "launch", side_effect=_fake_launch()):
            return self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(cwd or self.repo),
                              "--run-dir", str(run_dir))

    def test_unignored_run_dir_in_repo_is_refused(self):
        rc, out, err = self._go(self.repo / "runs")
        self.assertEqual(rc, 2, out + err)
        self.assertIn(f"dispatch: --run-dir {self.repo / 'runs'} is inside --cwd and not git-ignored; "
                      "later snapshot verifies would see its files", err)
        self.assertFalse((self.repo / "runs").exists())

    def test_ignored_run_dir_in_repo_launches(self):
        (self.repo / ".gitignore").write_text("runs/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "ignore"],
                       cwd=self.repo, check=True, capture_output=True)
        rc, out, err = self._go(self.repo / "runs")
        self.assertEqual(rc, 0, out + err)
        self.assertRegex(out.strip(), STATUS_RE)

    def test_run_dir_outside_repo_launches(self):
        rc, out, err = self._go(self.runs)
        self.assertEqual(rc, 0, out + err)

    def test_non_repo_cwd_is_not_refused(self):
        plain = self.root / "plain"
        plain.mkdir()
        rc, out, err = self._go(plain / "runs", cwd=plain)
        self.assertNotIn("not git-ignored", err)
        self.assertTrue((plain / "runs").is_dir(), out + err)


class GateWroteTest(CliBase):
    """025 US5 (#107): a gate that writes into the repo turns the outcome red."""

    def _go(self, gates):
        slots = self._slots(GATES=gates)
        with mock.patch.object(dispatch, "launch", side_effect=_fake_launch()):
            return self._main("--slots", str(slots), "--model", "haiku", "--cwd", str(self.repo),
                              "--run-dir", str(self.runs))

    def test_writing_gate_is_red(self):
        rc, out, err = self._go([{"argv": ["sh", "-c", "echo pwned > gate_wrote.txt"]}])
        self.assertIn("snapshot=CHANGED:gate_wrote.txt outcome=red reason=gate-wrote", out)
        self.assertRegex(out.strip(), STATUS_RE)
        self.assertEqual(rc, 1, out + err)
        verify = (self._run_dir() / "verify.txt").read_text()
        self.assertIn("\nafter gates:\nsnapshot rc=", verify)
        self.assertIn("gate_wrote.txt", verify.split("after gates:")[1])

    def test_writing_failing_gate_reports_gate_wrote(self):
        rc, out, err = self._go([{"argv": ["sh", "-c", "echo pwned > gate_wrote.txt; exit 1"]}])
        self.assertIn("outcome=red reason=gate-wrote", out)
        self.assertEqual(rc, 1, out + err)

    def test_read_only_gate_stays_green(self):
        rc, out, err = self._go([{"argv": [sys.executable, "-c", "pass"]}])
        self.assertIn("snapshot=clean outcome=green", out)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("after gates: clean", (self._run_dir() / "verify.txt").read_text())


SENTINEL_PATCH = ("\n_check_report_025 = check_report\n\n\ndef check_report(text):\n"
                  "    return list(_check_report_025(text)) + ['sentinel-025']\n")
PROBES = ("agents_inc/install/dispatch.py", "skills/workerbee/scripts/check_dispatch_prompt.py",
          "skills/workerbee/scripts/render_dispatch.py", "skills/workerbee/scripts/dispatch_rungs.py",
          "skills/workerbee/scripts/pre_dispatch_snapshot.py", "skills/workerbee/scripts/dispatch_schema.py")


class ScriptsSourceTest(CliBase):
    """025 US1 (#104): a dispatch from an agents-inc checkout is judged by a launch-time copy of its scripts."""

    def setUp(self):
        super().setUp()
        self.co = self.root / "checkout"
        self.co.mkdir()
        shutil.copytree(REPO / "skills/workerbee", self.co / "skills/workerbee",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.co / "agents_inc/install").mkdir(parents=True)
        (self.co / "agents_inc/install/dispatch.py").write_text("# stub\n")
        with (self.co / PROBES[1]).open("a") as fh:
            fh.write(SENTINEL_PATCH)
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"]):
            subprocess.run(cmd, cwd=self.co, check=True, capture_output=True)

    def _go(self, cwd, during=None):
        with mock.patch.object(dispatch, "launch", side_effect=_fake_launch(during=during)):
            return self._main("--slots", str(self._slots()), "--model", "haiku", "--cwd", str(cwd),
                              "--run-dir", str(self.runs))

    def _resume(self):
        with mock.patch.object(dispatch, "launch", side_effect=_fake_launch()):
            return self._main("--resume", str(self._run_dir()), "--message", "go on")

    def test_checkout_lints_with_trusted_copy(self):
        def edit_judge(cwd):  # the delegate rewrites the checkout's lint during its turn
            with (cwd / PROBES[1]).open("a") as fh:
                fh.write("\n\ndef check_report(text):\n    return []\n")
        rc, out, err = self._go(self.co, during=edit_judge)
        self.assertRegex(out.strip(), STATUS_RE)
        self.assertIn("report=NON-COMPLIANT:['sentinel-025'] lint=checkout ", out)
        spec = json.loads((self._run_dir() / "run.json").read_text())
        trusted = Path(spec["scripts_dir"])
        self.assertEqual(spec["scripts_source"], "checkout")
        self.assertTrue(trusted.is_absolute())
        self.assertFalse(trusted.is_relative_to(self.co))
        self.assertEqual(trusted, dispatch._trust_path(self._run_dir().name) / "workerbee" / "scripts")
        verify = (self._run_dir() / "verify.txt").read_text()
        self.assertTrue(verify.startswith(f"lint source: {trusted}\n"), verify)
        shipped = (self._run_dir() / "pre_dispatch_snapshot.py").read_bytes()
        self.assertEqual(shipped, (trusted / "pre_dispatch_snapshot.py").read_bytes())

    def test_plain_repo_is_installed(self):
        rc, out, err = self._go(self.repo)
        self.assertIn("report=COMPLIANT lint=installed ", out)
        self.assertEqual(json.loads((self._run_dir() / "run.json").read_text())["scripts_source"], "installed")
        self.assertTrue((self._run_dir() / "verify.txt").read_text().startswith(f"lint source: {dispatch.SCRIPTS}\n"))

    def test_symlinked_probes_are_installed(self):
        for rel in PROBES:
            target = self.root / "real" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            (self.co / rel).rename(target)
            (self.co / rel).symlink_to(target)
        rc, out, err = self._go(self.co)
        self.assertIn(" lint=installed ", out)

    def test_missing_probe_is_installed(self):
        (self.co / PROBES[3]).unlink()
        rc, out, err = self._go(self.co)
        self.assertIn(" lint=installed ", out)

    def test_changed_trusted_copy_is_tampered(self):
        def tamper(cwd):
            run_id = next(self.runs.iterdir()).name
            path = dispatch._trust_path(run_id) / "workerbee" / "scripts" / "check_dispatch_prompt.py"
            path.write_text(path.read_text() + "\n# changed\n")
        rc, out, err = self._go(self.co, during=tamper)
        self.assertRegex(out.strip(), STATUS_RE)
        self.assertIn("snapshot=TAMPERED outcome=red reason=snapshot-tampered", out)
        self.assertEqual(rc, 1, out + err)

    def test_resume_reads_recorded_copy(self):
        self._go(self.co)
        shutil.rmtree(self.co / "skills/workerbee/scripts")
        rc, out, err = self._resume()
        self.assertIn("report=NON-COMPLIANT:['sentinel-025'] lint=checkout ", out)

    def test_resume_with_redirected_scripts_dir_is_tampered(self):
        self._go(self.co)
        path = self._run_dir() / "run.json"
        spec = json.loads(path.read_text())
        spec["scripts_dir"] = str(self.co / "skills/workerbee/scripts")
        path.write_text(json.dumps(spec))
        rc, out, err = self._resume()
        self.assertIn("snapshot=TAMPERED outcome=red reason=snapshot-tampered", out)
        self.assertEqual(rc, 1, out + err)

    def test_resume_without_keys_is_installed(self):
        self._go(self.co)
        path = self._run_dir() / "run.json"
        spec = json.loads(path.read_text())
        spec.pop("scripts_dir")
        spec.pop("scripts_source")
        path.write_text(json.dumps(spec))
        rc, out, err = self._resume()
        self.assertIn(" lint=installed ", out)

    def test_broker_worker_inherits_lead_scripts(self):
        trusted = dispatch._pin_scripts(self.co / "skills/workerbee/scripts", "lead-run")
        lead = {"scripts_dir": str(trusted), "scripts_source": "checkout"}
        args = argparse.Namespace(slots=str(self._slots()), model="haiku", effort=None, cwd=str(self.repo),
                                  tier=None, run_dir=str(self.runs), dry_run=False, home_repo=None, resume=None)
        out = io.StringIO()
        with mock.patch.object(dispatch, "launch", side_effect=_fake_launch()), \
                mock.patch.object(dispatch, "scripts_dir", side_effect=AssertionError("a Worker never probes")):
            rc, crash = dispatch._in_worker_scope(self.root / "lead", "r1", out, lambda: dispatch.run(args), lead)
        self.assertIsNone(crash, out.getvalue())
        self.assertIn("report=NON-COMPLIANT:['sentinel-025'] lint=checkout ", out.getvalue())
        spec = json.loads((self._run_dir() / "run.json").read_text())
        self.assertEqual((spec["scripts_dir"], spec["scripts_source"]), (str(trusted), "checkout"))
        self.assertIsNone(dispatch._INHERITED_SCRIPTS)

    def test_lead_dir_records_scripts(self):
        spec = {"run_id": "r", "model": "opus", "effort": None, "cwd": str(self.repo), "chain": [], "fan_out": {},
                "permission_mode": "acceptEdits", "scripts_dir": "/t/workerbee/scripts", "scripts_source": "checkout"}
        lead_dir, _ = dispatch.make_lead_dir(spec, ["haiku"])
        self.addCleanup(shutil.rmtree, lead_dir, True)
        data = json.loads((lead_dir / "run.json").read_text())
        self.assertEqual((data["scripts_dir"], data["scripts_source"]), ("/t/workerbee/scripts", "checkout"))


if __name__ == "__main__":
    unittest.main()
