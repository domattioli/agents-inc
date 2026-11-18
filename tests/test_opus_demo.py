"""Tests for tools/demo/opus_demo.py (spec 030, plan.md design point 7)."""
import builtins
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Add the demo tools directory to the path, the same way test_governance_demo.py adds tools/
REPO = Path(__file__).parent.parent
DEMO_DIR = REPO / "tools" / "demo"
sys.path.insert(0, str(DEMO_DIR))

import opus_demo

READY_DOCTOR = "READY\nagent gate: on (test)\nluna type: ready\n"
SLOT_KEYS = ["ROLE", "TASK", "CONSTRAINTS", "OUT_OF_SCOPE", "FILES_IN_SCOPE",
             "STOP_RULE", "SUCCESS_GATE", "FAILURE_GATE", "GATES"]


def fake_which(missing=()):
    """Return a `which` stand-in that finds every program except the ones in `missing`."""
    return lambda name: None if name in missing else "/usr/bin/" + name


class DemoCase(unittest.TestCase):
    """Common setup: a temporary repo root holding the S fixture and a hidden judge."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)
        s = self.root / "fixtures" / "build-test-verify" / "S"
        (s / "hidden").mkdir(parents=True)
        shutil.copy(REPO / "fixtures" / "build-test-verify" / "S" / "SPEC.md", s / "SPEC.md")
        (s / "hidden" / "acceptance.py").write_text("print('judge')\n")

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_demo(self, argv=None, doctor=READY_DOCTOR, which=None, **kw):
        out = io.StringIO()
        args = ["--dry-run", "--root", str(self.root)] + (argv or [])
        with contextlib.redirect_stdout(out):
            rc = opus_demo.main(args, doctor_text=doctor, which=which or fake_which(), **kw)
        return rc, out.getvalue()

    def stamp_dir(self):
        dirs = sorted((self.root / ".scratch" / "demo-030").iterdir())
        self.assertEqual(len(dirs), 1)
        return dirs[0]


class TestDryRun(DemoCase):
    def test_a_dry_run_writes_trial_and_slots(self):
        rc, _ = self.run_demo()
        self.assertEqual(rc, 0)
        d = self.stamp_dir()
        self.assertTrue((d / "trial" / "SPEC.md").is_file())
        self.assertTrue((d / "slots-build.json").is_file())
        self.assertTrue((d / "slots-review.json").is_file())
        self.assertTrue((d / "demo.json").is_file())
        self.assertTrue((d / "prompt.txt").is_file())
        self.assertEqual(os.listdir(d / "trial"), ["SPEC.md"])

    def test_b_no_hidden_path_in_trial(self):
        self.run_demo()
        trial = self.stamp_dir() / "trial"
        names = [p.name for p in trial.rglob("*")]
        self.assertNotIn("hidden", names)
        self.assertNotIn("acceptance.py", names)

    def test_c_slots_carry_required_keys(self):
        self.run_demo()
        d = self.stamp_dir()
        rel = "/".join((".scratch", "demo-030", d.name, "trial"))
        for name, rc_cmd, model_cap in (("slots-build.json", "csv2json", "10"),
                                        ("slots-review.json", "REVIEW.md", "15")):
            slots = json.loads((d / name).read_text())
            for key in SLOT_KEYS:
                self.assertIn(key, slots, f"{name} lacks {key}")
            gate = slots["GATES"][0]
            self.assertEqual(gate["cwd"], rel)
            self.assertEqual(gate["expect_rc"], 0)
            self.assertIn(rc_cmd + ("" if rc_cmd == "REVIEW.md" else ".py"), gate["argv"])
            self.assertIn(model_cap + " tool calls", slots["STOP_RULE"])
            self.assertIn("fixtures/", slots["CONSTRAINTS"])
            self.assertIn(".scratch/bench-", slots["CONSTRAINTS"])
            # The delegate must not be told where the judge lives (leak grep in PROMPT.md).
            text = (d / name).read_text()
            self.assertNotIn("hidden/", text)
            self.assertNotIn("acceptance.py", text)
        build = json.loads((d / "slots-build.json").read_text())
        self.assertEqual(build["GATES"][0]["argv"], ["test", "-s", "csv2json.py"])
        self.assertEqual(build["GATES"][0]["timeout_s"], 30)
        review = json.loads((d / "slots-review.json").read_text())
        self.assertEqual(review["GATES"][0]["argv"], ["test", "-s", "REVIEW.md"])

    def test_d_prompt_has_three_beats_and_no_placeholder(self):
        rc, out = self.run_demo()
        self.assertEqual(rc, 0)
        prompt = (self.stamp_dir() / "prompt.txt").read_text()
        for n in range(1, 4):
            self.assertRegex(prompt, rf"BEAT {n} \w", f"BEAT {n} missing")
        self.assertIn("vendor gate:", prompt)
        self.assertNotIn("Monitor", prompt)
        self.assertIsNone(re.search(r"\{[A-Z_0-9]+\}", prompt))
        self.assertNotIn("NEEDS", prompt)
        self.assertNotIn("<!--", prompt)
        self.assertIn("BEAT 1", out)  # the runner prints the prompt
        self.assertIn(str(self.stamp_dir() / "trial"), prompt)

    def test_e_codex_absent_degrades_to_haiku(self):
        rc, out = self.run_demo(which=fake_which(missing=("codex",)))
        self.assertEqual(rc, 0)
        self.assertIn("NOTE: codex absent -> haiku (build and review share a model)", out)
        d = self.stamp_dir()
        self.assertEqual(json.loads((d / "demo.json").read_text())["build_model"], "haiku")
        self.assertEqual(json.loads((d / "slots-build.json").read_text()).get("MODEL"), "haiku")
        prompt = (d / "prompt.txt").read_text()

    def test_f_doctor_not_ready_exits_2_and_writes_nothing(self):
        rc, out = self.run_demo(doctor="WB_AUTH_REQUIRED\n")
        self.assertEqual(rc, 2)
        self.assertIn("WB_AUTH_REQUIRED", out)
        self.assertFalse((self.root / ".scratch").exists())

    def test_h_asciinema_absent_prints_note(self):
        rc, out = self.run_demo(which=fake_which(missing=("asciinema",)))
        self.assertEqual(rc, 0)
        self.assertIn("NOTE: asciinema not installed -> running without recording"
                      " (brew install asciinema agg)", out)

    def test_ready_default_uses_luna_and_beat6_task(self):
        self.run_demo()
        d = self.stamp_dir()
        self.assertEqual(json.loads((d / "demo.json").read_text())["build_model"], "luna")
        self.assertEqual(json.loads((d / "slots-build.json").read_text())["MODEL"], "luna")

    def test_luna_off_degrades_even_with_codex(self):
        rc, out = self.run_demo(doctor="READY\nluna type: off\n")
        self.assertEqual(rc, 0)
        self.assertIn("-> haiku (build and review share a model)", out)
        self.assertEqual(json.loads((self.stamp_dir() / "demo.json").read_text())["build_model"], "haiku")

    def test_mod_not_installed_skips_beat6_and_notes_fallback(self):
        rc, out = self.run_demo(doctor="READY\nluna type: ready\nWARNING: MOD_NOT_INSTALLED\n")
        self.assertEqual(rc, 0)
        self.assertIn("plain-dispatch fallback", out)
        self.assertFalse(json.loads((self.stamp_dir() / "demo.json").read_text())["mod_installed"])

    def test_sandbox_exclude_warning_prints_exact_ask(self):
        rc, out = self.run_demo(doctor="READY\nluna type: ready\nWARNING: WB_SANDBOX_EXCLUDE_MISSING\n")
        self.assertEqual(rc, 0)
        self.assertIn('add "agents-inc *" to sandbox.excludedCommands', out)

    def test_demo_json_fields(self):
        self.run_demo()
        meta = json.loads((self.stamp_dir() / "demo.json").read_text())
        for key in ("stamp", "doctor_ready", "luna_type", "codex", "mod_installed",
                    "sandbox_exclude_ok", "free", "build_model", "recorded", "cast", "gif",
                    "beat_seconds"):
            self.assertIn(key, meta)
        self.assertTrue(meta["doctor_ready"])
        self.assertFalse(meta["recorded"])
        self.assertEqual(set(meta["free"]), {"mistral", "gemini", "openrouter"})

    def test_free_line_printed(self):
        _, out = self.run_demo()
        self.assertRegex(out, r"free: mistral=(yes|maybe|no) gemini=(yes|maybe|no) openrouter=(yes|maybe|no)")

    def test_missing_spec_is_setup_error(self):
        (self.root / "fixtures" / "build-test-verify" / "S" / "SPEC.md").unlink()
        rc, out = self.run_demo()
        self.assertEqual(rc, 3)

    def test_hidden_in_trial_is_setup_error(self):
        def bad_copy(src, dst):
            shutil.copy(src, dst)
            (Path(dst).parent / "hidden").mkdir()
        rc, _ = self.run_demo(copy=bad_copy)
        self.assertEqual(rc, 3)


class TestLaunch(DemoCase):
    """The live path, with the launcher injected so nothing real starts."""

    def run_live(self, which, launch, argv=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = opus_demo.main(["--root", str(self.root)] + (argv or []),
                                doctor_text=READY_DOCTOR, which=which, launch=launch)
        return rc, out.getvalue()

    def test_launch_wraps_claude_in_asciinema_after_chdir(self):
        calls = []

        def launch(cmd):
            calls.append((list(cmd), os.getcwd()))
            return 0
        rc, out = self.run_live(fake_which(), launch)
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][0][:2], ["asciinema", "rec"])
        self.assertTrue(any(a.startswith("claude --model opus ") and "opus runs the whole loop" in a for a in calls[0][0]))
        self.assertEqual(os.path.realpath(calls[0][1]), os.path.realpath(self.root))
        self.assertEqual(calls[1][0][0], "agg")
        meta = json.loads((self.stamp_dir() / "demo.json").read_text())
        self.assertTrue(meta["recorded"])

    def test_agg_absent_keeps_cast(self):
        rc, out = self.run_live(fake_which(missing=("agg",)), lambda cmd: 0)
        self.assertIn("NOTE: agg not installed -> cast kept, no GIF", out)
        self.assertIsNone(json.loads((self.stamp_dir() / "demo.json").read_text())["gif"])

    def test_no_asciinema_runs_claude_directly(self):
        calls = []
        rc, out = self.run_live(fake_which(missing=("asciinema",)), lambda cmd: calls.append(list(cmd)) or 0)
        self.assertEqual(calls[0][:3], ["claude", "--model", "opus"])
        self.assertIn("opus runs the whole loop", calls[0][3])

    def test_no_record_flag_runs_claude_directly(self):
        calls = []
        self.run_live(fake_which(), lambda cmd: calls.append(list(cmd)) or 0, argv=["--no-record"])
        self.assertEqual(calls[0][:3], ["claude", "--model", "opus"])
        self.assertIn("opus runs the whole loop", calls[0][3])


class TestFreeKeys(unittest.TestCase):
    def test_g_free_key_check_never_opens_a_file(self):
        with tempfile.TemporaryDirectory() as home:
            key = Path(home, ".config", "devstral", "api_key")
            key.parent.mkdir(parents=True)
            key.write_text("x" * 40)
            with mock.patch.object(builtins, "open", side_effect=AssertionError("open called")):
                got = opus_demo.free_key_status(environ={}, home=home)
            self.assertEqual(got["mistral"], "yes")

    def test_statuses(self):
        with tempfile.TemporaryDirectory() as home:
            Path(home, ".codex-bridge").mkdir()
            Path(home, ".codex-bridge", "gemini-key").write_text("short")
            got = opus_demo.free_key_status(environ={"OPENROUTER_API_KEY": "set"}, home=home)
            self.assertEqual(got, {"mistral": "no", "gemini": "maybe", "openrouter": "yes"})

    def test_shared_env_file_gives_maybe(self):
        with tempfile.TemporaryDirectory() as home:
            Path(home, "Projects").mkdir()
            Path(home, "Projects", ".env").write_text("irrelevant")
            got = opus_demo.free_key_status(environ={}, home=home)
            self.assertEqual(set(got.values()), {"maybe"})


@unittest.skipUnless(shutil.which("agents-inc"), "agents-inc launcher not on PATH")
class TestDispatchRender(unittest.TestCase):
    def test_slots_render_and_lint(self):
        # dispatch snapshots a git tree even on a dry run, so use the real repo as root and
        # delete the stamp folder this test created when it ends
        base = REPO / ".scratch" / "demo-030"
        before = set(base.iterdir()) if base.is_dir() else set()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = opus_demo.main(["--dry-run", "--root", str(REPO)], doctor_text=READY_DOCTOR,
                                which=fake_which())
        self.assertEqual(rc, 0)
        made = set(base.iterdir()) - before
        def cleanup():
            for p in made:
                shutil.rmtree(p, ignore_errors=True)
            if not before:
                _rmdir_quiet(base)
        self.addCleanup(cleanup)
        self.assertEqual(len(made), 1)
        d = next(iter(made))
        for name in ("slots-build.json", "slots-review.json"):
            done = subprocess.run([str(REPO / "scripts" / "agents-inc"), "dispatch", "--slots", str(d / name),
                                   "--model", "haiku", "--dry-run", "--cwd", str(REPO)],
                                  capture_output=True, text=True, cwd=str(REPO),
                                  env={**os.environ, "PYTHONPATH": str(REPO)})
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


def _rmdir_quiet(path):
    try:
        os.rmdir(path)
    except OSError:
        pass


if __name__ == "__main__":
    unittest.main()
