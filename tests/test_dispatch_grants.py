"""D58: per-run tool grants for Claude delegates and structured GATES run by dispatch. Writes only to temp dirs."""
from __future__ import annotations
import contextlib
import io
import json
import os
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
GOOD_REPORT = ("caveman ultra confirmed. GRILL: none. [verified] gate rc=0 exit code 0.\n"
               "OUT OF SCOPE / INCOMPLETE: none\nWORKERS SPAWNED: 0\n")
PASS = [sys.executable, "-c", "pass"]
RD = dispatch._load("render_dispatch")
CHECK = dispatch._load("check_dispatch_prompt")

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


def _pair(prefix):
    return [f"Bash({prefix})", f"Bash({prefix} *)"]


class GrantsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = _git_repo(self.root)
        self.runs = self.root / "runs"
        self.env = mock.patch.dict("os.environ", {"HOME": str(self.root)})
        self.env.start()
        os.environ.pop("AGENTS_INC_HOME_REPO", None)
        self.calls = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _slots(self, **extra) -> Path:
        data = json.loads(EXAMPLE.read_text())
        data.update(extra)
        path = self.root / "slots.json"
        path.write_text(json.dumps(data))
        return path

    def _main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(["dispatch", *argv])
        return rc, out.getvalue(), err.getvalue()

    def _fake(self, report=GOOD_REPORT, rc=0):
        def fake(kind, model, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, **kw):
            self.calls.append(dict(kw, kind=kind, model=model, resume=resume, run_dir=run_dir))
            return {"rc": rc, "stdout": report, "stderr": "", "argv": ["x"], "session_id": "sess-1"}
        return fake

    def _dispatch(self, model="sonnet", report=GOOD_REPORT, **slots):
        with mock.patch.object(dispatch, "launch", side_effect=self._fake(report)):
            return self._main("--slots", str(self._slots(**slots)), "--model", model, "--cwd", str(self.repo),
                              "--run-dir", str(self.runs))

    def _run_dir(self) -> Path:
        dirs = list(self.runs.iterdir())
        self.assertEqual(len(dirs), 1)
        return dirs[0]

    def _spec(self) -> dict:
        return json.loads((self._run_dir() / "run.json").read_text())


class ToolGrantTest(GrantsBase):
    def test_default_allow_and_deny_lists_are_exact(self):
        rc, out, _ = self._dispatch()
        self.assertEqual(rc, 0, out)
        spec = self._spec()
        snap, run_dir = spec["snapshot"], self._run_dir()
        want = ["Read", "Glob", "Grep"]
        for p in ("git status", "git diff", "git log", "git show", "git ls-files", "git check-ignore"):
            want += _pair(p)
        want += ["Bash(claude --help)"]
        want += _pair(f"python3 {run_dir}/pre_dispatch_snapshot.py verify {snap}")
        want += _pair(f"python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify {snap}")
        self.assertEqual(spec["allowed_tools"], want)
        self.assertEqual(spec["disallowed_tools"], _pair("git push") + _pair("git commit") + _pair("sudo")
                         + ["WebFetch", "WebSearch", "Agent", "Task"])
        self.assertFalse(any("agents-inc" in r for r in spec["allowed_tools"]))
        self.assertEqual(self.calls[0]["allowed_tools"], want)
        self.assertEqual(self.calls[0]["disallowed_tools"], spec["disallowed_tools"])

    def test_runners_added_only_with_file_paths(self):
        self._dispatch(FILES_IN_SCOPE="agents_inc/x.py\ntests/")
        allowed = self._spec()["allowed_tools"]
        for p in ("python3 -m unittest", "python3 -m pytest", "pytest"):
            for rule in _pair(p):
                self.assertIn(rule, allowed)
        self.tearDown(), self.setUp()
        self._dispatch(FILES_IN_SCOPE="none (read-only)")
        self.assertNotIn("Bash(pytest)", self._spec()["allowed_tools"])
        self.assertNotIn("Bash(python3 -m unittest)", self._spec()["allowed_tools"])

    def test_gates_argv_granted_exactly(self):
        argv = [sys.executable, "-c", "print('a b')"]
        self._dispatch(GATES=[{"argv": argv}])
        self.assertIn(f"Bash({shlex.join(argv)})", self._spec()["allowed_tools"])

    def test_bash_allow_pairs_added(self):
        self._dispatch(BASH_ALLOW=["git blame", "ls docs"])
        allowed = self._spec()["allowed_tools"]
        for rule in _pair("git blame") + _pair("ls docs"):
            self.assertIn(rule, allowed)

    def test_bash_allow_as_lines_string(self):
        self._dispatch(BASH_ALLOW="git blame\n\n  ls docs  \n")
        allowed = self._spec()["allowed_tools"]
        self.assertIn("Bash(git blame *)", allowed)
        self.assertIn("Bash(ls docs)", allowed)

    def test_bash_allow_refusals(self):
        for prefix in ("git push", "git commit -m x", "sudo ls", "rm -rf /tmp/x", "curl http://x", "ssh host",
                       "cat ~/.ssh/id_rsa"):
            with self.subTest(prefix=prefix):
                self.tearDown(), self.setUp()
                rc, out, _ = self._dispatch(BASH_ALLOW=[prefix])
                self.assertEqual(rc, 3, out)
                self.assertIn("refused refused-bash-allow:", out)
                self.assertEqual(self._spec()["outcome"], "refused-bash-allow")
                self.assertEqual(self.calls, [])
                self.assertTrue((self._run_dir() / "lint.txt").read_text().strip())

    def test_claude_argv_flag_shape(self):
        argv = dispatch.claude_argv("opus", "plan", "s1", "low", ["Read", "Bash(x)"], ["WebFetch"])
        self.assertEqual(argv[argv.index("--allowedTools"):],
                         ["--allowedTools", "Read", "Bash(x)", "--disallowedTools", "WebFetch"])
        self.assertEqual(argv[argv.index("--effort"):argv.index("--allowedTools")], ["--effort", "low", "--resume", "s1"])
        bare = dispatch.claude_argv("opus", "plan")
        self.assertNotIn("--allowedTools", bare)
        self.assertNotIn("--disallowedTools", bare)

    def _launch_argv(self, **kw):
        seen = {}
        fake = subprocess.CompletedProcess([], 0, stdout=json.dumps({"result": "ok", "session_id": "s"}), stderr="")
        child = self.root / "child"
        child.mkdir(exist_ok=True)
        run = mock.Mock(return_value=fake)
        with mock.patch.object(dispatch.subprocess, "Popen", side_effect=popen_from_run(run)), \
                mock.patch.object(dispatch, "sandbox_available", return_value=True):
            dispatch.launch("claude", "haiku", "low", self.repo, "p", child, **kw)
        seen["argv"] = run.call_args.args[0]
        return seen["argv"]

    def test_legacy_launch_without_lists_keeps_old_argv(self):
        argv = self._launch_argv()
        self.assertNotIn("--allowedTools", argv)
        self.assertNotIn("--disallowedTools", argv)
        self.assertEqual(argv[1:], ["-p", "--model", dispatch.CLAUDE_MODELS["haiku"], "--permission-mode",
                                    "acceptEdits", "--output-format", "stream-json", "--verbose", "--effort", "low"])

    def test_ask_channel_adds_one_allowed_tools_flag(self):
        dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK = True, "r1"
        try:
            argv = self._launch_argv(allowed_tools=["Read", "Bash(git status)"], disallowed_tools=["WebFetch"])
        finally:
            dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK, dispatch._BROKER_DENY = False, None, ()
        self.assertEqual(argv.count("--allowedTools"), 1)
        i = argv.index("--allowedTools")
        self.assertEqual(argv[i + 1:i + 4], ["Read", "Bash(git status)", dispatch.ASK_TOOL])
        self.assertIn("--strict-mcp-config", argv)

    def test_ask_channel_legacy_keeps_single_ask_tool(self):
        dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK = True, "r1"
        try:
            argv = self._launch_argv()
        finally:
            dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK, dispatch._BROKER_DENY = False, None, ()
        self.assertEqual(argv[argv.index("--allowedTools") + 1], dispatch.ASK_TOOL)
        self.assertEqual(argv.count("--allowedTools"), 1)

    def test_broker_worker_turns_off_nested_sandbox(self):
        dispatch._BROKER_SAFE_WRITES = True
        try:
            argv = self._launch_argv()
        finally:
            dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK, dispatch._BROKER_DENY = False, None, ()
        self.assertEqual(argv[0], dispatch.SANDBOX_EXEC)
        self.assertEqual(argv[argv.index("--settings") + 1], dispatch.WORKER_SETTINGS)
        self.assertNotIn("--settings", self._launch_argv())

    def test_run_json_records_grants_and_gates(self):
        self._dispatch(GATES=[{"argv": PASS}])
        spec = self._spec()
        self.assertEqual(spec["gate_commands"], [{"argv": PASS, "cwd": ".", "timeout_s": 600, "expect_rc": 0}])
        self.assertIsInstance(spec["allowed_tools"], list)
        self.assertIsInstance(spec["disallowed_tools"], list)
        self.assertEqual(spec["gate_results"][0]["rc"], 0)
        self.assertEqual(set(spec["gate_results"][0]), {"argv", "cwd", "expect_rc", "rc", "excerpt"})

    def test_dry_run_records_grants(self):
        rc, out, _ = self._main("--slots", str(self._slots(GATES=[{"argv": PASS}])), "--model", "haiku",
                                "--cwd", str(self.repo), "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        spec = self._spec()
        self.assertEqual(spec["outcome"], "dry-run")
        self.assertTrue(spec["allowed_tools"] and spec["disallowed_tools"] and spec["gate_commands"])

    def test_codex_run_has_no_tool_lists_but_runs_gates(self):
        rc, out, _ = self._dispatch("terra", GATES=[{"argv": PASS}])
        self.assertEqual(rc, 0, out)
        spec = self._spec()
        self.assertIsNone(spec["allowed_tools"])
        self.assertIsNone(spec["disallowed_tools"])
        self.assertNotIn("allowed_tools", self.calls[0])
        self.assertEqual((spec["outcome"], spec["gate_results"][0]["rc"]), ("green", 0))

    def test_codex_run_still_refuses_dangerous_bash_allow(self):
        rc, out, _ = self._dispatch("terra", BASH_ALLOW=["git push"])
        self.assertEqual(rc, 3, out)
        self.assertEqual(self.calls, [])


class GrantsSectionTest(GrantsBase):
    """#54: dispatch renders the fixed grants into every Claude delegate prompt."""
    HEADER = "GRANTS (fixed by dispatch for this run; the harness allows exactly these tools):"
    PREFIX = "gh issue view 54 -R domattioli/agents-inc"

    def _prompt(self) -> str:
        return (self._run_dir() / "prompt.md").read_text()

    def test_prompt_lists_every_allowed_and_denied_rule(self):
        rc, out, _ = self._dispatch()
        self.assertEqual(rc, 0, out)
        spec, prompt = self._spec(), self._prompt()
        self.assertIn(self.HEADER, prompt)
        for rule in spec["allowed_tools"] + spec["disallowed_tools"]:
            self.assertIn(rule, prompt)
        self.assertIn("ALLOWED: " + ", ".join(spec["allowed_tools"]), prompt)
        self.assertIn("DENIED: " + ", ".join(spec["disallowed_tools"]), prompt)
        self.assertIn("requires approval", prompt)

    def test_bash_allow_prefix_rendered_with_its_rules(self):
        self._dispatch(BASH_ALLOW=[self.PREFIX])
        prompt = self._prompt()
        self.assertIn(f"`{self.PREFIX}`", prompt)
        self.assertIn(f"Bash({self.PREFIX} *)", prompt)
        self.tearDown(), self.setUp()
        rc, out, _ = self._main("--slots", str(self._slots(BASH_ALLOW=[self.PREFIX])), "--model", "sonnet",
                                "--cwd", str(self.repo), "--run-dir", str(self.runs), "--dry-run")
        self.assertEqual(rc, 0, out)
        prompt = self._prompt()
        self.assertIn(f"`{self.PREFIX}`", prompt)
        self.assertIn(f"Bash({self.PREFIX} *)", prompt)

    def test_empty_grants_render_none(self):
        text = dispatch.grants_section([], [], [])
        self.assertIn("ALLOWED: none", text)
        self.assertIn("prefixes (each also allowed with arguments): none", text)
        self.assertIn("DENIED: none", text)
        self._dispatch()
        line = next(ln for ln in self._prompt().splitlines() if ln.startswith("BASH_ALLOW prefixes"))
        self.assertTrue(line.endswith(": none"), line)

    def test_codex_prompt_has_no_grants(self):
        rc, out, _ = self._dispatch("terra")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("GRANTS (", self._prompt())

    def test_broker_child_prompt_has_grants(self):
        dispatch._BROKER_SAFE_WRITES = True
        try:
            rc, out, _ = self._dispatch()
        finally:
            dispatch._BROKER_SAFE_WRITES = False
        self.assertEqual(rc, 0, out)
        self.assertIn(self.HEADER, self._prompt())

    def test_grants_section_mentions_acceptEdits(self):
        text = dispatch.grants_section(["Read"], [], [], "acceptEdits")
        self.assertIn("PERMISSION_MODE acceptEdits", text)
        text = dispatch.grants_section(["Read"], [], [], "plan")
        self.assertNotIn("PERMISSION_MODE acceptEdits", text)


class GateParseTest(unittest.TestCase):
    def test_parse_gates_defaults_and_forms(self):
        self.assertEqual(RD.parse_gates(None), (None, None))
        self.assertEqual(RD.parse_gates(""), (None, None))
        self.assertEqual(RD.parse_gates([]), (None, None))
        gates, why = RD.parse_gates(json.dumps([{"argv": ["true"], "timeout_s": 1.5, "expect_rc": 3}]))
        self.assertIsNone(why)
        self.assertEqual(gates, [{"argv": ["true"], "cwd": ".", "timeout_s": 1.5, "expect_rc": 3}])

    def test_parse_gates_rejects(self):
        bad = ["{nope", {"argv": ["true"]}, 5, [1], [{}], [{"argv": []}], [{"argv": ["a", ""]}], [{"argv": ["a\nb"]}],
               [{"argv": ["a"], "extra": 1}], [{"argv": ["a"], "cwd": "/tmp"}], [{"argv": ["a"], "cwd": "x/../y"}],
               [{"argv": ["a"], "timeout_s": 0}], [{"argv": ["a"], "timeout_s": 3601}],
               [{"argv": ["a"], "timeout_s": True}], [{"argv": ["a"], "expect_rc": True}],
               [{"argv": ["a"], "expect_rc": "0"}], [{"argv": ["git", "push"]}], [{"argv": ["sh", "-c", "curl x"]}]]
        for value in bad:
            with self.subTest(value=value):
                gates, why = RD.parse_gates(value)
                self.assertIsNone(gates)
                self.assertTrue(why)

    def test_bash_allow_list(self):
        self.assertEqual(RD.bash_allow_list(None), ([], None))
        self.assertEqual(RD.bash_allow_list("a b\n\n c \n"), (["a b", "c"], None))
        for bad in (["a*"], ["a (b)"], ["a `b`"], [""], [5], 7, ["git commit"], ["sudo x"]):
            with self.subTest(bad=bad):
                prefixes, why = RD.bash_allow_list(bad)
                self.assertEqual(prefixes, [])
                self.assertTrue(why)

    def test_gate_text(self):
        text = RD.gate_text([{"argv": ["python3", "-c", "print('a b')"], "cwd": "sub", "timeout_s": 5, "expect_rc": 3}])
        self.assertIn("`python3 -c 'print('\"'\"'a b'\"'\"')'`", text)
        self.assertIn("`sub`", text)
        self.assertIn("exit code 3", text)
        self.assertIn("no shell", text)


class GateRefusalTest(GrantsBase):
    def _refused(self, gates):
        rc, out, err = self._dispatch(GATES=gates)
        self.assertEqual(rc, 3, out + err)
        self.assertIn("refused refused-gates:", out)
        self.assertEqual(self._spec()["outcome"], "refused-gates")
        self.assertEqual(self.calls, [])
        self.assertTrue((self._run_dir() / "lint.txt").read_text().strip())

    def test_refusals(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.repo / "link").symlink_to(outside)
        cases = {
            "danger": [{"argv": ["git", "push"]}],
            "credential": [{"argv": [sys.executable, "-c", "print(open('.env').read())"]}],  # 022: paths, not words
            "credential-path": [{"argv": ["cat", "~/.ssh/id_rsa"]}],
            "credential-basename-1": [{"argv": ["cat", "credentials.json"]}],
            "credential-basename-2": [{"argv": ["cat", "/tmp/token"]}],
            "credential-basename-3": [{"argv": ["cat", "api_key.txt"]}],
            "credential-basename-4": [{"argv": ["cat", ".secrets"]}],
            "absolute-cwd": [{"argv": PASS, "cwd": "/tmp"}],
            "dotdot-cwd": [{"argv": PASS, "cwd": "../x"}],
            "symlink-cwd": [{"argv": PASS, "cwd": "link"}],
            "bad-json": "{not json",
            "non-list": {"argv": PASS},
            "empty-argv": [{"argv": []}],
        }
        for name, gates in cases.items():
            with self.subTest(name):
                shutil_runs = self.runs
                if shutil_runs.exists():
                    import shutil
                    shutil.rmtree(shutil_runs)
                self.calls.clear()
                self._refused(gates)

    def test_string_gates_message_names_expected_type(self):
        for name, gates in {"plain-command": "python3 -m unittest", "json-scalar": "5", "json-object": '{"argv": ["x"]}'}.items():
            with self.subTest(name):
                self.calls.clear()
                rc, out, err = self._dispatch(GATES=gates)
                self.assertEqual(rc, 3, out + err)
                self.assertIn("GATES must be a JSON list, got string", out)
                import shutil
                shutil.rmtree(self.runs, ignore_errors=True)

    def test_json_string_accepted(self):
        rc, out, _ = self._dispatch(GATES=json.dumps([{"argv": PASS}]))
        self.assertEqual(rc, 0, out)
        self.assertEqual(self._spec()["outcome"], "green")


class GateRunTest(GrantsBase):
    def _gate_run(self, gates, **kw):
        rc, out, _ = self._dispatch(GATES=gates, **kw)
        return rc, out, self._spec()

    def test_passing_gate_is_green(self):
        rc, out, spec = self._gate_run([{"argv": PASS}])
        self.assertEqual((rc, spec["outcome"], spec["reason"]), (0, "green", None))
        self.assertIn("outcome=green out=", out)

    def test_failing_gate_is_red_gate_failed(self):
        rc, out, spec = self._gate_run([{"argv": [sys.executable, "-c", "import sys;sys.exit(1)"]}])
        self.assertEqual((rc, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"))
        self.assertIn("outcome=red reason=gate-failed", out)

    def test_expect_rc_three(self):
        rc, _, spec = self._gate_run([{"argv": [sys.executable, "-c", "import sys;sys.exit(3)"], "expect_rc": 3}])
        self.assertEqual((rc, spec["outcome"]), (0, "green"))

    def test_missing_binary_is_refused_by_preflight(self):
        rc, out, spec = self._gate_run([{"argv": ["/nonexistent/bin/xyz"]}])
        self.assertEqual((rc, spec["outcome"]), (3, "refused-capability"))
        self.assertIn("gate[0] executable not found", spec["reason_detail"])

    def test_missing_binary_is_gate_missing(self):
        # D72: preflight normally refuses first; a binary that vanishes after preflight is still gate-missing.
        with mock.patch.object(dispatch, "capability_preflight", return_value=[]):
            rc, _, spec = self._gate_run([{"argv": ["/nonexistent/bin/xyz"]}])
        self.assertEqual((rc, spec["outcome"], spec["reason"]), (1, "red", "gate-missing"))
        self.assertIsNone(spec["gate_results"][0]["rc"])
        self.assertEqual(spec["gate_results"][0]["error"], "FileNotFoundError")

    def test_timeout_is_gate_missing(self):
        rc, _, spec = self._gate_run([{"argv": [sys.executable, "-c", "import time;time.sleep(5)"], "timeout_s": 0.5}])
        self.assertEqual((rc, spec["reason"]), (1, "gate-missing"))
        self.assertEqual(spec["gate_results"][0]["error"], "timeout")

    def test_no_gates_is_unverified_exit_zero(self):
        rc, out, spec = self._gate_run(None)
        self.assertEqual((rc, spec["outcome"], spec["reason"]), (0, "unverified", "no-gates"))
        self.assertIn("outcome=unverified reason=no-gates", out)
        self.assertEqual(spec["gate_commands"], [])
        self.assertNotIn("gate_results", spec)

    def test_red_check_beats_gates(self):
        report = GOOD_REPORT.replace("WORKERS SPAWNED: 0", "WORKERS SPAWNED: 2")
        rc, out, _ = self._dispatch(report=report, GATES=[{"argv": PASS}])
        self.assertEqual(rc, 1)
        self.assertIn("reason=fan-out-over-total", out)

    def test_failure_gate_text_is_never_run(self):
        marker = self.root / "marker"
        rc, out, spec = self._gate_run(None, FAILURE_GATE=f"any failure; `touch {marker}` must not run",
                                      SUCCESS_GATE=f"`touch {marker}` exits 0")
        self.assertEqual(rc, 0, out)
        self.assertFalse(marker.exists())

    def test_excerpt_is_capped(self):
        gate = [{"argv": [sys.executable, "-c", "print('a'*10000)"]}]
        _, _, spec = self._gate_run(gate)
        excerpt = spec["gate_results"][0]["excerpt"]
        self.assertTrue(0 < len(excerpt.encode()) <= 2048)

    def test_gate_runs_in_cwd_subdirectory_without_shell(self):
        (self.repo / "sub").mkdir()
        gate = [{"argv": [sys.executable, "-c", "import os;print(os.path.basename(os.getcwd()), '$HOME')"],
                 "cwd": "sub"}]
        _, _, spec = self._gate_run(gate)
        self.assertEqual(spec["gate_results"][0]["excerpt"].strip(), "sub $HOME")

    def test_gate_rescreened_at_run_time(self):
        spec = {"cwd": str(self.repo), "gate_commands": [{"argv": ["git", "push"], "cwd": ".", "timeout_s": 5,
                                                          "expect_rc": 0}]}
        results, reason = dispatch._run_gates(spec)
        self.assertEqual((results[0]["rc"], results[0]["error"], reason), (None, "refused", "gate-missing"))

    def test_gate_cwd_link_planted_after_dispatch_is_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.repo / "sub").symlink_to(outside)
        spec = {"cwd": str(self.repo), "gate_commands": [{"argv": [sys.executable, "-c", "pass"], "cwd": "sub",
                                                          "timeout_s": 5, "expect_rc": 0}]}
        results, reason = dispatch._run_gates(spec)
        self.assertEqual((results[0]["rc"], results[0]["error"], reason), (None, "cwd-outside", "gate-missing"))

    def test_broker_child_skips_gates(self):
        marker = self.root / "gate-ran"
        gate = [{"argv": [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"]}]
        dispatch._BROKER_SAFE_WRITES = True
        try:
            rc, out, _ = self._dispatch(GATES=gate)
        finally:
            dispatch._BROKER_SAFE_WRITES = False
        spec = self._spec()
        self.assertEqual((rc, spec["outcome"], spec["reason"]), (0, "unverified", "gates-skipped-broker"))
        self.assertIsNone(spec["gate_results"])
        self.assertFalse(marker.exists())


class ResumeGateTest(GrantsBase):
    def test_resume_reuses_lists_and_reruns_gates(self):
        counter = self.root / "count"
        gate = [{"argv": [sys.executable, "-c", f"open({str(counter)!r}, 'a').write('x')"]}]
        self._dispatch(GATES=gate)
        run = self._run_dir()
        first = self._spec()
        self.assertEqual(counter.read_text(), "x")
        with mock.patch.object(dispatch, "launch", side_effect=self._fake()):
            rc, out, _ = self._main("--resume", run.name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        resumed = self.calls[-1]
        self.assertEqual(resumed["resume"], "sess-1")
        self.assertEqual(resumed["allowed_tools"], first["allowed_tools"])
        self.assertEqual(resumed["disallowed_tools"], first["disallowed_tools"])
        self.assertEqual(counter.read_text(), "xx")
        spec = self._spec()
        self.assertEqual(spec["resumes"][-1]["gate_results"][0]["rc"], 0)
        self.assertEqual(spec["gate_results"][0]["rc"], 0)

    def test_legacy_resume_without_lists_passes_none(self):
        self._dispatch()
        run = self._run_dir()
        spec = json.loads((run / "run.json").read_text())
        for key in ("allowed_tools", "disallowed_tools", "gate_commands"):
            spec.pop(key)
        (run / "run.json").write_text(json.dumps(spec))
        with mock.patch.object(dispatch, "launch", side_effect=self._fake()):
            rc, out, _ = self._main("--resume", run.name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        self.assertIsNone(self.calls[-1]["allowed_tools"])
        self.assertIsNone(self.calls[-1]["disallowed_tools"])
        self.assertIn("unverified", out)


class RendererTest(GrantsBase):
    def _render(self, model, **slots):
        return dispatch.render(self._slots(**slots), model)

    def test_gate_text_appended_to_success_gate(self):
        rc, prompt, err = self._render("sonnet", GATES=[{"argv": ["python3", "-m", "unittest"], "expect_rc": 0}])
        self.assertEqual(rc, 0, err)
        line = next(ln for ln in prompt.splitlines() if ln.startswith("SUCCESS GATE:"))
        self.assertIn("`grep -n", line)  # the original text stays
        self.assertIn("`python3 -m unittest` in `.` expecting exit code 0", line)
        self.assertIn("no shell", line)

    def test_empty_success_gate_accepted_with_gates(self):
        rc, prompt, err = self._render("sonnet", SUCCESS_GATE="", GATES=[{"argv": PASS}])
        self.assertEqual(rc, 0, err)
        self.assertIn("SUCCESS GATE: After you exit, dispatch runs these commands", prompt)
        rc, _, err = self._render("sonnet", SUCCESS_GATE="")
        self.assertEqual(rc, 2)
        self.assertIn("SUCCESS_GATE", err)

    def test_invalid_slots_exit_two(self):
        rc, _, err = self._render("sonnet", GATES=[{"argv": ["git", "commit"]}])
        self.assertEqual(rc, 2)
        self.assertIn("GATES invalid:", err)
        rc, _, err = self._render("sonnet", BASH_ALLOW=["sudo ls"])
        self.assertEqual(rc, 2)
        self.assertIn("BASH_ALLOW invalid:", err)

    def test_executive_chain_defaults_to_operator(self):
        for model in ("fable", "astra"):
            with self.subTest(model=model):
                rc, prompt, err = self._render(model)
                self.assertEqual(rc, 0, err)
                self.assertIn(f"REPORTING CHAIN: {model} reports to the operator\n", prompt)
                self.assertFalse(CHECK.reporting_chain_inverted(prompt.lower()))

    def test_lower_chains_unchanged(self):
        expect = {"opus": "opus reports to fable; fable reports to the operator",
                  "sonnet": "sonnet reports to opus; opus reports to fable; fable reports to the operator",
                  "haiku": "haiku reports to sonnet; sonnet reports to fable; fable reports to the operator",
                  "terra": "terra reports to sol; sol reports to astra; astra reports to the operator"}
        for model, chain in expect.items():
            with self.subTest(model=model):
                _, prompt, _ = self._render(model)
                self.assertIn(f"REPORTING CHAIN: {chain}\n", prompt)

    def test_unknown_rung_keeps_cos(self):
        _, prompt, _ = self._render("mystery")
        self.assertIn("mystery reports to CoS; CoS reports to the operator", prompt)


class BrokerGrantTest(GrantsBase):
    def setUp(self):
        super().setUp()
        self.run_dir = self.root / "lead-run"
        (self.run_dir / "inbox").mkdir(parents=True)
        self.sb = mock.patch.object(dispatch, "sandbox_available", return_value=True)
        self.sb.start()
        self.addCleanup(self.sb.stop)

    def _manifest(self):
        spec = {"schema_version": 1, "run_id": "lead-1", "model": "sol", "effort": "high", "cwd": str(self.repo),
                "chain": ["CoS", "sol"], "worker_models": ["haiku"], "fan_out": {"width": 1, "total": 2, "depth": 1},
                "permission_mode": "default"}
        (self.run_dir / "run.json").write_text(json.dumps(spec))
        return spec

    def _request(self, rid, **slots):
        data = json.loads(EXAMPLE.read_text())
        data.update(slots)
        req = {"schema_version": 1, "request_id": rid, "model": "haiku", "effort": "low", "tier": "grunt",
               "slots": data}
        path = self.run_dir / "inbox" / f"{rid}.request.json"
        path.write_text(json.dumps(req))

    def _serve(self):
        (self.run_dir / "inbox" / "lead.done").write_text("")
        with mock.patch.object(dispatch, "launch", side_effect=self._fake()), contextlib.redirect_stderr(io.StringIO()):
            return dispatch.serve(self.run_dir, poll_interval=0.01, idle_timeout=5)

    def _result(self, rid):
        return json.loads((self.run_dir / f"{rid}.result.json").read_text())

    def test_bash_allow_is_broker_owned(self):
        spec = self._manifest()
        req = {"schema_version": 1, "request_id": "r1", "model": "haiku", "effort": "low", "tier": "grunt",
               "slots": dict(json.loads(EXAMPLE.read_text()), BASH_ALLOW="git blame")}
        self.assertEqual(dispatch._validate_fields(req, spec, "r1"), (None, "broker-owned-slot"))
        self.assertIn("BASH_ALLOW", dispatch.BROKER_OWNED_SLOTS)

    def test_broker_request_with_gates_string_is_unverified_and_counted(self):
        marker = self.root / "gate-ran"
        gate = [{"argv": [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"]}]
        self._manifest()
        self._request("g1", GATES=json.dumps(gate))
        self.assertEqual(self._serve(), 0)
        res = self._result("g1")
        self.assertEqual((res["status"], res["dispatch_exit_code"], res["outcome"], res["reason"]),
                         ("unverified", 0, "unverified", "gates-skipped-broker"))
        self.assertFalse(marker.exists())
        spec = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual(spec["request_counts"]["unverified"], 1)
        self.assertEqual(spec["request_counts"]["green"], 0)

    def test_init_broker_state_counts_unverified(self):
        spec = {}
        dispatch.init_broker_state(spec)
        self.assertEqual(spec["request_counts"]["unverified"], 0)

    def test_plan_resume_accepts_unverified(self):
        spec = self._manifest()
        child = self.run_dir / "workers" / "r1" / "runs" / "c1"
        child.mkdir(parents=True)
        (child / "run.json").write_text(json.dumps({"session_id": "s", "model": "haiku"}))
        for status, ok in (("unverified", True), ("green", True), ("red", True), ("refused", False)):
            (self.run_dir / "r1.result.json").write_text(json.dumps({"status": status}))
            plan, why = dispatch.plan_resume(self.run_dir, spec, "r1", "go", lambda r: True)
            self.assertEqual(plan is not None, ok, (status, why))
            if not ok:
                self.assertEqual(why, "not-resumable")


if __name__ == "__main__":
    unittest.main()
