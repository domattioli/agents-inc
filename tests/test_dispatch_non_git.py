"""Dispatch from a non-git cwd: a read-only delegate runs with the snapshot skipped; a writing one is refused before
launch. A git cwd (a subdirectory included) keeps capture and verify. Temp dirs and fake launches only."""
from __future__ import annotations
import io
import json
import os
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch, free_launch
from tests.test_dispatch_cli import EXAMPLE, GOOD_REPORT
from tests.test_dispatch_snapshot_trust import DispatchBase


class Recorder:
    """A launch() stand-in that records each call's kind, prompt and keyword arguments."""

    def __init__(self):
        self.calls = []

    def __call__(self, kind, model, effort, cwd, prompt, run_dir, *a, **k):
        self.calls.append({"kind": kind, "prompt": prompt, "cwd": cwd, "kw": k})
        return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": "sess-1"}


class NonGitBase(DispatchBase):
    def setUp(self):
        super().setUp()
        self.plain = self.root / "plain"
        self.plain.mkdir()
        (self.plain / "notes.txt").write_text("hello\n")
        if dispatch.in_git_work_tree(self.plain) is not False:  # a skip here would hide every test below
            self.fail(f"{self.plain} is not a clear non-git dir; the non-git tests cannot run")

    def ro_slots(self, **extra) -> Path:
        data = json.loads(EXAMPLE.read_text())
        data.update(extra)
        path = self.root / "slots.json"
        path.write_text(json.dumps(data))
        return path

    def go(self, model, slots, cwd=None):
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, out, err = self.main("--slots", str(slots), "--model", model, "--cwd", str(cwd or self.plain),
                                     "--run-dir", str(self.runs))
        return rc, out, err, rec


class ReadOnlyRunsTest(NonGitBase):
    def _assert_skipped(self, rc, out, rec, kind):
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        self.assertEqual(len(rec.calls), 1, out)
        self.assertEqual(rec.calls[0]["kind"], kind)
        self.assertTrue(rec.calls[0]["kw"].get("read_only"))
        spec = self.spec()
        self.assertEqual(spec["snapshot"], "skipped")
        self.assertEqual(spec["snapshot_skip_reason"], "non-git cwd, read-only delegate")
        self.assertEqual((spec["outcome"], spec["reason"]), ("unverified", "snapshot-skipped"))
        self.assertFalse((self.run_dir() / "snapshot.json").exists())
        self.assertIn("snapshot=skipped outcome=unverified reason=snapshot-skipped detail=non-git_cwd,_read-only_delegate", out)
        self.assertNotIn("fatal", out)
        prompt = rec.calls[0]["prompt"]
        self.assertNotIn("<snapshot>", prompt)
        self.assertNotIn("snapshot.json", prompt)
        self.assertNotIn("SNAPSHOT VERIFIER", prompt)
        self.assertIn("SNAPSHOT: skipped (non-git cwd, read-only delegate)", prompt)
        trust = json.loads((self.state / "dispatch-runs" / spec["run_id"] / "trust.json").read_text())
        self.assertEqual(trust["snapshot"], "skipped")
        return spec

    def test_claude_plan_mode_runs_read_only(self):
        rc, out, _, rec = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"))
        spec = self._assert_skipped(rc, out, rec, "claude")
        self.assertEqual(spec["allowed_tools"], ["Read", "Glob", "Grep"])
        for denied in ("Bash", "Edit", "Write", "NotebookEdit"):
            self.assertIn(denied, spec["disallowed_tools"])

    def test_codex_without_write_runs(self):
        rc, out, _, rec = self.go("luna", self.ro_slots(CODEX_WRITE="no"))
        self._assert_skipped(rc, out, rec, "codex")
        self.assertNotIn("codex_write", rec.calls[0]["kw"])

    def test_resume_of_skipped_run_stays_skipped(self):
        self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"))
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, out, _ = self.main("--resume", self.run_dir().name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        self.assertTrue(rec.calls[0]["kw"].get("read_only"))
        self.assertIn("snapshot=skipped outcome=unverified reason=snapshot-skipped", out)

    def test_resume_refuses_forged_write_grant(self):
        self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"))
        path = self.run_dir() / "run.json"
        spec = json.loads(path.read_text())
        spec["permission_mode"] = "acceptEdits"
        path.write_text(json.dumps(spec))
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, _, err = self.main("--resume", self.run_dir().name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_REFUSED)
        self.assertEqual(rec.calls, [])
        self.assertIn(".scratch/<task>/", err)


class WritingRunsRefusedTest(NonGitBase):
    def _assert_refused(self, rc, out, err, rec):
        self.assertEqual(rc, dispatch.EXIT_REFUSED, out + err)
        self.assertEqual(rec.calls, [])
        self.assertIn("refused refused-non-git", out)
        self.assertIn("dispatch from a git repository", out)
        self.assertIn("git-ignored .scratch/<task>/", out)
        self.assertNotIn("fatal", out + err)
        self.assertEqual(self.spec()["outcome"], "refused-non-git")

    def test_claude_accept_edits_refused(self):
        self._assert_refused(*self.go("haiku", self.ro_slots()))

    def test_codex_write_refused(self):
        self._assert_refused(*self.go("luna", self.ro_slots(CODEX_WRITE="yes")))

    def test_gates_refused(self):
        self._assert_refused(*self.go("haiku", self.ro_slots(PERMISSION_MODE="plan",
                                                            GATES=[{"argv": ["true"]}])))

    def test_bash_allow_refused(self):
        self._assert_refused(*self.go("haiku", self.ro_slots(PERMISSION_MODE="plan", BASH_ALLOW=["ls"])))


class GitCwdUnchangedTest(NonGitBase):
    def test_subdirectory_of_repo_captures_and_verifies(self):
        sub = self.repo / "sub" / "deeper"
        sub.mkdir(parents=True)
        self.assertTrue(dispatch.in_git_work_tree(sub))
        rc, out, _, rec = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=sub)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        spec = self.spec()
        self.assertNotEqual(spec["snapshot"], "skipped")
        self.assertTrue((self.run_dir() / "snapshot.json").is_file())
        self.assertIn("snapshot=clean", out)
        self.assertFalse(rec.calls[0]["kw"].get("read_only"))
        self.assertIn("SNAPSHOT VERIFIER", rec.calls[0]["prompt"])

    def test_forged_skip_in_git_cwd_resume_refused(self):  # F3
        rc, out, _, _ = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=self.repo)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        path = self.run_dir() / "run.json"
        spec = json.loads(path.read_text())
        spec["snapshot"] = "skipped"
        path.write_text(json.dumps(spec))
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, out, err = self.main("--resume", self.run_dir().name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_REFUSED, out + err)
        self.assertEqual(rec.calls, [])

    def test_resume_after_repo_removed_is_refused(self):
        work = self.repo
        rc, out, _, _ = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=work)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        shutil.rmtree(work / ".git")
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, _, err = self.main("--resume", self.run_dir().name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_REFUSED)
        self.assertEqual(rec.calls, [])
        self.assertIn("refused-non-git", err)

    def test_resume_of_captured_read_only_run_after_repo_removed_is_refused(self):
        rc, out, _, _ = self.go("luna", self.ro_slots(CODEX_WRITE="no"), cwd=self.repo)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        shutil.rmtree(self.repo / ".git")
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, _, err = self.main("--resume", self.run_dir().name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_REFUSED)
        self.assertEqual(rec.calls, [])
        self.assertIn("can no longer verify", err)


class FreePathTest(NonGitBase):
    """The free path through _run_dir_phase and _run_free_phase, with the wrapper and its pre-checks stubbed."""

    def _go_free(self, cwd, **extra):
        slug = next(iter(free_launch.FREE_MODELS))
        calls = []

        def run_free(spec, prompt, run_dir, cwd, timeout=None):
            calls.append(prompt)
            (Path(run_dir) / "stdout.md").write_text("ok reply")
            return {"rc": 0, "stdout": "ok reply", "stderr": "", "argv": ["wrapper"], "wrapper": "w",
                    "wrapper_sha256": "0" * 64, "session_id": None}
        with mock.patch.object(free_launch, "pre_checks", return_value=None), \
                mock.patch.object(free_launch, "build_input_section", return_value=("", [])), \
                mock.patch.object(free_launch, "pre_launch_hold", return_value=None), \
                mock.patch.object(free_launch, "reachability_hold", return_value=None), \
                mock.patch.object(free_launch, "run_free", side_effect=run_free):
            rc, out, err = self.main("--slots", str(self.ro_slots(PERMISSION_MODE="plan", **extra)), "--model", slug,
                                     "--cwd", str(cwd), "--run-dir", str(self.runs))
        return rc, out, err, calls

    def test_free_non_git_skips_capture(self):
        rc, out, err, calls = self._go_free(self.plain)
        self.assertEqual(len(calls), 1, out + err)
        self.assertEqual(rc, dispatch.EXIT_OK, out + err)
        spec = self.spec()
        self.assertEqual((spec["snapshot"], spec["reason"]), ("skipped", "snapshot-skipped"))
        self.assertFalse((self.run_dir() / "snapshot.json").exists())
        self.assertIn("snapshot=skipped", out)

    def test_free_non_git_with_gates_refused(self):
        rc, out, err, calls = self._go_free(self.plain, GATES=[{"argv": ["true"]}])
        self.assertEqual(rc, dispatch.EXIT_REFUSED, out + err)
        self.assertEqual(calls, [])
        self.assertIn(".scratch/<task>/", out)

    def test_free_git_cwd_captures(self):
        rc, out, err, calls = self._go_free(self.repo)
        self.assertEqual(len(calls), 1, out + err)
        self.assertTrue((self.run_dir() / "snapshot.json").is_file())
        self.assertIn("snapshot=clean", out)


class MoreNonGitTest(NonGitBase):
    def test_resume_after_cwd_became_git_refused(self):  # F3
        rc, out, _, _ = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=self.plain)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        subprocess.run(["git", "init", "-q", str(self.plain)], check=True)
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, out, err = self.main("--resume", self.run_dir().name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_REFUSED, out + err)
        self.assertEqual(rec.calls, [])
        self.assertIn("now (or may be) a git work tree", err)

    def test_verify_red_when_cwd_now_git_with_skipped_trust(self):
        rc, out, _, _ = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=self.plain)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        subprocess.run(["git", "init", "-q", str(self.plain)], check=True)
        rc, log, snap = dispatch._snapshot_verify(self.spec(), self.run_dir())
        self.assertEqual(rc, 1, log)
        self.assertTrue(snap.startswith("ERROR"), snap)

    def test_ledger_row_of_skipped_run(self):
        from agents_inc import host_ledger
        rc, out, _, _ = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=self.plain)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        row = host_ledger.dispatch_return_row(self.spec())
        self.assertEqual(row["status"], "unverified")
        self.assertIsNone(row["verdict"])
        self.assertEqual(row["gate_reason"], "snapshot-skipped")

    def test_lead_refused_on_non_git(self):
        slots = self.ro_slots(PERMISSION_MODE="plan", ALLOWLIST="luna, haiku", FAN_OUT="width 1, total 2, depth 1")
        rc, out, _, rec = self.go("sonnet", slots, cwd=self.plain)
        self.assertEqual(rc, dispatch.EXIT_REFUSED, out)
        self.assertIn("a Lead runs Workers", out)
        self.assertEqual(rec.calls, [])

    def test_home_and_root_refused(self):  # F7
        for cwd, word in ((Path.home(), "home directory"), (Path("/"), "filesystem root")):
            with self.subTest(cwd=cwd), mock.patch.object(dispatch, "in_git_work_tree", return_value=False):
                rc, out, _, rec = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=cwd)
                self.assertEqual(rc, dispatch.EXIT_REFUSED, out)
                self.assertEqual(rec.calls, [])
                self.assertIn(word, out)
                self.assertNotIn("not read-only", out)  # L4: its own message


class CwdScopeTest(NonGitBase):
    """M1, F7: cwds a read-only delegate must not read, on a fresh run and on resume. HOME is the temp root here."""

    def _refused(self, cwd, word):
        rc, out, _, rec = self.go("terra", self.ro_slots(CODEX_WRITE="no"), cwd=cwd)
        self.assertEqual(rc, dispatch.EXIT_REFUSED, out)
        self.assertEqual(rec.calls, [])
        self.assertIn(word, out)
        self.assertNotIn("not read-only", out)

    def test_credential_dirs_refused(self):
        for name in (".codex", ".claude", ".ssh", ".config", ".local"):
            with self.subTest(name=name):
                d = self.root / name / "sub"
                d.mkdir(parents=True)
                self._refused(d, "holds credentials or agent config")

    def test_symlink_into_credential_dir_refused(self):
        (self.root / ".codex").mkdir()
        link = self.plain / "codexlink"
        link.symlink_to(self.root / ".codex")
        self._refused(link, "holds credentials or agent config")

    def test_symlink_to_home_refused(self):
        link = self.plain / "homelink"
        link.symlink_to(self.root)
        self._refused(link, "home directory")

    def test_parent_of_home_refused(self):
        with mock.patch.object(dispatch, "in_git_work_tree", return_value=False):
            self._refused(self.root.parent, "home directory or a parent")

    def test_broad_cwd_on_resume_refused(self):
        rc, out, _, _ = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=self.plain)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        secret = self.root / ".codex" / "sub"
        secret.mkdir(parents=True)
        path = self.run_dir() / "run.json"
        spec = json.loads(path.read_text())
        spec["cwd"] = str(secret)
        path.write_text(json.dumps(spec))
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, out, err = self.main("--resume", self.run_dir().name, "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_REFUSED, out + err)
        self.assertEqual(rec.calls, [])
        self.assertIn("holds credentials", err)

    def _resume_read_only(self, model, slots):
        rc, out, _, _ = self.go(model, self.ro_slots(**slots), cwd=self.plain)
        self.assertEqual(rc, dispatch.EXIT_OK, out)
        rec = Recorder()
        with mock.patch.object(dispatch, "launch", side_effect=rec):
            rc, out, err = self.main("--resume", self.run_dir().name, "--message", "go", "--run-dir", str(self.runs))
        self.assertEqual(rc, dispatch.EXIT_OK, out + err)
        self.assertIs(rec.calls[0]["kw"].get("read_only"), True)

    def test_resume_passes_read_only_claude(self):
        self._resume_read_only("haiku", {"PERMISSION_MODE": "plan"})

    def test_resume_passes_read_only_codex(self):
        self._resume_read_only("luna", {"CODEX_WRITE": "no"})

    def test_broker_child_skip_path(self):
        with mock.patch.object(dispatch, "_BROKER_SAFE_WRITES", True), mock.patch.object(dispatch, "_WORKER_ASK", "r1"):
            rc, out, err, rec = self.go("haiku", self.ro_slots(PERMISSION_MODE="plan"), cwd=self.plain)
        self.assertEqual(rc, dispatch.EXIT_OK, out + err)
        self.assertEqual(self.spec()["snapshot"], "skipped")
        self.assertIs(rec.calls[0]["kw"].get("read_only"), True)
        self.assertEqual(json.loads((self.run_dir() / "trust.json").read_text())["snapshot"], "skipped")
        self.assertIn("Read, Glob and Grep and the ask_lead tool", rec.calls[0]["prompt"])  # L6


class ArgvTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)

    def test_claude_read_only_argv(self):
        argv = dispatch.claude_argv("haiku", "plan", allowed=["Read"], disallowed=["Bash"], read_only=True)
        self.assertEqual(argv[argv.index("--tools") + 1], "Read,Glob,Grep")
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "user")
        self.assertNotIn("--tools", dispatch.claude_argv("haiku", "plan"))

    def _launch(self, kind, model, read_only):
        """The real launch(); only the process start (Claude) or run_codex (Codex) and install lookups are faked."""
        with mock.patch.object(dispatch, "caller_sandbox", return_value=None):
            if kind == "claude":
                seen = {}
                with mock.patch.object(dispatch.subprocess, "Popen", side_effect=lambda argv, **k: seen.setdefault("argv", argv)), \
                        mock.patch.object(dispatch, "_stream_run", return_value=(0, "", "")):
                    dispatch.launch("claude", model, None, self.tmp, "hi", self.tmp, "plan", read_only=read_only,
                                    allowed_tools=["Read"], disallowed_tools=["Bash"])
                return seen["argv"]
            from agents_inc.install import cli, receipt, runtime
            fake = mock.Mock(return_value=0)
            with mock.patch.object(cli, "_paths"), mock.patch.object(cli, "_efforts", return_value={}), \
                    mock.patch.object(receipt.InstallReceipt, "load"), mock.patch.object(runtime, "run_codex", fake):
                dispatch.launch("codex", model, None, self.tmp, "hi", self.tmp, read_only=read_only)
            return fake.call_args.kwargs

    def test_claude_launch_read_only_flags(self):  # F2
        argv = self._launch("claude", "haiku", True)
        for flag in ("--tools", "--setting-sources", "--strict-mcp-config"):
            self.assertIn(flag, argv)
        self.assertNotIn("--strict-mcp-config", self._launch("claude", "haiku", False))

    def test_codex_skipped_run_isolated_home(self):  # F1, F4
        for model in ("luna", "terra", "sol", "astra"):
            with self.subTest(model=model):
                kw = self._launch("codex", model, True)
                self.assertTrue(kw["isolate_home"])
                self.assertTrue(kw["no_extensions"])
                self.assertEqual(kw["extra_read"], ())
                kw = self._launch("codex", model, False)
                self.assertFalse(kw["isolate_home"])
                self.assertNotEqual(kw["extra_read"], ())

    def test_claude_resume_launch_read_only_flags(self):  # F2 on resume
        seen = {}
        with mock.patch.object(dispatch, "caller_sandbox", return_value=None), \
                mock.patch.object(dispatch.subprocess, "Popen", side_effect=lambda argv, **k: seen.setdefault("argv", argv)), \
                mock.patch.object(dispatch, "_stream_run", return_value=(0, "", "")):
            dispatch.launch("claude", "haiku", None, self.tmp, "hi", self.tmp, "plan", resume="s1", read_only=True,
                            allowed_tools=["Read"], disallowed_tools=["Bash"])
        argv = seen["argv"]
        self.assertIn("--resume", argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "Read,Glob,Grep")
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "user")
        self.assertIn("--strict-mcp-config", argv)

    def test_codex_resume_read_only_kwargs(self):
        from agents_inc.install import cli, receipt, runtime
        fake = mock.Mock(return_value=0)
        with mock.patch.object(dispatch, "caller_sandbox", return_value=None), mock.patch.object(cli, "_paths"), \
                mock.patch.object(cli, "_efforts", return_value={}), mock.patch.object(receipt.InstallReceipt, "load"), \
                mock.patch.object(runtime, "run_codex", fake):
            dispatch.launch("codex", "luna", None, self.tmp, "hi", self.tmp, resume="t1", read_only=True)
        kw = fake.call_args.kwargs
        self.assertEqual((kw["resume_thread"], kw["isolate_home"], kw["no_extensions"], kw["extra_read"]),
                         ("t1", True, True, ()))

    def _run_codex_argv(self, model, resume=None, no_extensions=True):
        """The real run_codex; only the isolated home and the process start below it are faked (no real ~/.codex)."""
        from agents_inc.install import runtime
        exe = self.tmp / "codex"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        home = self.tmp / "iso"
        home.mkdir(exist_ok=True)
        proc = mock.Mock(stdout="", stderr="", returncode=0)
        with mock.patch.object(runtime, "lead_codex_home", return_value=home), \
                mock.patch.object(runtime, "load_model_map", return_value={model: "gpt-x"}), \
                mock.patch.object(runtime.subprocess, "run", return_value=proc) as run, \
                mock.patch("sys.stderr", new_callable=io.StringIO):
            runtime.run_codex(model, "low", self.tmp, io.StringIO("hi"), mock.Mock(codex_path=str(exe)),
                              {"gpt-x": ["low"]}, env={}, isolate_home=True, no_extensions=no_extensions,
                              resume_thread=resume)
        return [c.args[0] for c in run.call_args_list if c.args and c.args[0] and c.args[0][0] == str(exe)][0]

    def test_run_codex_no_extensions_plumbing(self):  # F1: through run_codex into both argv builders
        for resume in (None, "t1"):
            with self.subTest(resume=resume):
                argv = self._run_codex_argv("terra", resume)
                for f in ("plugins", "apps", "multi_agent", "image_generation"):
                    self.assertIn(f"features.{f}=false", argv)
                self.assertNotIn("features.plugins=false", self._run_codex_argv("terra", resume, no_extensions=False))

    def test_codex_argv_extensions_off_with_tools(self):  # F1
        from agents_inc.install import runtime
        argv = runtime.build_codex_argv(self.tmp / "codex", "gpt-x", "low", self.tmp, {"gpt-x": ["low"]}, {}, tools=True,
                                        no_extensions=True)
        for f in ("plugins", "apps", "multi_agent"):
            self.assertIn(f"features.{f}=false", argv)


class UnitTest(unittest.TestCase):
    def test_in_git_work_tree(self):  # F5
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            self.assertIsNone(dispatch.in_git_work_tree(tmp / "missing"))  # git -C on a missing dir: not a clear answer
            plain = tmp / "plain"
            plain.mkdir()
            self.assertIs(dispatch.in_git_work_tree(plain), False)
            repo = tmp / "repo"
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            with mock.patch.dict(os.environ, {"GIT_DIR": str(tmp / "nowhere"), "GIT_CEILING_DIRECTORIES": str(tmp)}):
                self.assertIs(dispatch.in_git_work_tree(repo), True)
                self.assertIs(dispatch.in_git_work_tree(plain), False)
            git_env = {"GIT_DIR": str(repo / ".git"), "GIT_WORK_TREE": str(plain)}  # plain is that repo's work tree
            with mock.patch.dict(os.environ, git_env):  # L3: an exported bare-dotfiles style pair keeps the base path
                self.assertIs(dispatch.in_git_work_tree(plain), True)
            with mock.patch.dict(os.environ, {"LC_ALL": "de_DE.UTF-8", "LANG": "de_DE.UTF-8", "LANGUAGE": "de"}):  # L1
                self.assertIs(dispatch.in_git_work_tree(plain), False)
                with mock.patch.object(dispatch.subprocess, "run", wraps=subprocess.run) as run:
                    dispatch.in_git_work_tree(plain)
                env = run.call_args.kwargs["env"]
                self.assertEqual(env["LC_ALL"], "C")
                self.assertNotIn("LANGUAGE", env)
            with mock.patch.object(dispatch.subprocess, "run", side_effect=FileNotFoundError("git")):
                self.assertIsNone(dispatch.in_git_work_tree(plain))
            dubious = mock.Mock(returncode=128, stdout="", stderr="fatal: detected dubious ownership in repository")
            with mock.patch.object(dispatch.subprocess, "run", return_value=dubious):
                self.assertIsNone(dispatch.in_git_work_tree(plain))

    def test_codex_auth_hint_only_on_skip_path(self):  # L7
        err = FileNotFoundError("WB_CODEX_AUTH_MISSING: x not found; log in to Codex first")
        for read_only in (True, False):
            with self.subTest(read_only=read_only), self.assertRaises(FileNotFoundError) as ctx:
                with dispatch._auth_hint(read_only):
                    raise err
            self.assertEqual("file-based Codex login" in str(ctx.exception), read_only)
            self.assertIn("log in to Codex first", str(ctx.exception))

    def test_grants_section_read_only_drops_bash_line(self):  # F6
        text = dispatch.grants_section(["Read"], ["Bash"], [], "plan", read_only=True)
        self.assertNotIn("One plain command per Bash call", text)

    def test_write_capability_table(self):
        wc = dispatch.write_capability
        self.assertIsNone(wc("codex", {"codex_write": False}))
        self.assertIsNotNone(wc("codex", {"codex_write": True}))
        self.assertIsNotNone(wc("codex", {}))
        self.assertIsNone(wc("claude", {"permission_mode": "plan"}))
        self.assertIsNotNone(wc("claude", {"permission_mode": "bypassPermissions"}))
        self.assertIsNotNone(wc("claude", {"permission_mode": "plan"}, check_grants=True))  # no recorded grants
        self.assertIsNone(wc("free", {}))
        self.assertIsNotNone(wc("free", {"gate_commands": [{"argv": ["true"]}]}))
        self.assertIsNotNone(wc("codex", {"codex_write": False, "lead_dir": "/x"}))
        self.assertIsNotNone(wc(None, {}))

    def test_strip_leaves_no_placeholder(self):
        text = dispatch.strip_snapshot_skipped(
            "PRE: snapshot <snapshot>; verify with `python3 x/pre_dispatch_snapshot.py verify <snapshot>`\n"
            "FAIL: `grep a b` or `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>`\n")
        self.assertNotIn("<snapshot>", text)
        self.assertNotIn("pre_dispatch_snapshot", text)
        self.assertIn("`grep a b`", text)


if __name__ == "__main__":
    unittest.main()
