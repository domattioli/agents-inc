"""D45 template revision: render, wrapper strip, required slots, CONTRACT suffix, report elements, snapshot.

Run: python3 -m unittest discover -s skills/workerbee/tests -p 'test_*.py'
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WB = ROOT / "skills" / "workerbee"
RENDER = WB / "scripts" / "render_dispatch.py"
LINT = WB / "scripts" / "check_dispatch_prompt.py"
SNAP = WB / "scripts" / "pre_dispatch_snapshot.py"
EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "example_slots.json"
HANDOFF = Path.home() / ".claude" / "skills" / "handoff-lint" / "scripts" / "handoff_lint.py"
sys.path.insert(0, str(LINT.parent))
import check_dispatch_prompt as cdp  # noqa: E402
import render_dispatch  # noqa: E402


def run(*cmd, **kw):
    return subprocess.run([sys.executable, *map(str, cmd)], capture_output=True, text=True, **kw)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, slots: dict, *extra):
        p = self.dir / "slots.json"
        p.write_text(json.dumps(slots), encoding="utf-8")
        return run(RENDER, "--slots", p, *extra)

    def example(self) -> dict:
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_fan_out_defaults_by_rung(self):
        cases = [({}, "width 3, total 6, depth 2"), ({"MODEL": "sonnet"}, "width 2, total 4, depth 1"),
                 ({"RUNG": "Grunt"}, "width 0, total 0, depth 0"), ({"MODEL": "fable"}, "width 3, total 6, depth 2")]
        for extra, want in cases:
            slots = self.example()
            slots.pop("FAN_OUT")
            slots.update(extra)
            proc = self.render(slots)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(f"FAN_OUT: {want}\n", proc.stdout, extra)

    def test_example_renders_compliant(self):
        proc = self.render(self.example())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.dir / "prompt.txt"
        out.write_text(proc.stdout, encoding="utf-8")
        res = run(LINT, out, "--with-handoff-lint")
        self.assertEqual(res.stdout.strip(), "COMPLIANT")
        self.assertEqual(res.returncode, 0, res.stderr)
        if HANDOFF.is_file():
            self.assertIn("handoff-lint: 0 finding(s)", res.stderr)

    def test_example_has_reporting_chain_line(self):
        proc = self.render(self.example())
        want = "REPORTING CHAIN: haiku reports to sonnet; sonnet reports to fable; fable reports to the operator"
        self.assertIn(want + "\n", proc.stdout)
        self.assertIn("chain: haiku < sonnet < fable", proc.stderr)
        out = self.dir / "prompt.txt"
        out.write_text(proc.stdout, encoding="utf-8")
        self.assertEqual(run(LINT, out).stdout.strip(), "COMPLIANT")

    def test_model_flag_sets_delegate(self):
        proc = self.render(self.example(), "--model", "luna")
        self.assertIn("REPORTING CHAIN: luna reports to terra; terra reports to astra; astra reports to the operator\n",
                      proc.stdout)

    def test_top_rung_supervisor_has_no_self_link(self):
        proc = self.render(self.example(), "--model", "opus")
        self.assertIn("REPORTING CHAIN: opus reports to fable; fable reports to the operator\n", proc.stdout)
        out = self.dir / "prompt.txt"
        out.write_text(proc.stdout, encoding="utf-8")
        self.assertEqual(run(LINT, out).stdout.strip(), "COMPLIANT")

    def test_wrapper_stripped(self):
        proc = self.render(self.example())
        self.assertNotIn("<!--", proc.stdout)
        self.assertNotIn("# Dispatch header", proc.stdout)
        self.assertIn("\n\nCAVEMAN: ", proc.stdout)
        for label in ("CONSTRAINTS: ", "OUT OF SCOPE: ", "NOTES ("):
            self.assertTrue(any(ln.startswith(label) for ln in proc.stdout.splitlines()), label)

    def test_notes_defaults_to_none(self):
        slots = self.example()
        del slots["NOTES"]
        proc = self.render(slots)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("in the report): none\n", proc.stdout)

    def test_required_slot_missing_exits_2(self):
        for slot in ("CONSTRAINTS", "OUT_OF_SCOPE"):
            slots = self.example()
            slots[slot] = "  "
            proc = self.render(slots)
            self.assertEqual(proc.returncode, 2)
            self.assertIn(f"Required slot missing or empty: {slot}", proc.stderr)

    def test_contract_suffix_end_to_end(self):
        header = WB / "header.md"
        good = hashlib.sha256(header.read_bytes()).hexdigest()
        proc = self.render(self.example(), "--contract-ref", f"{header} (sha256 {good})")
        out = self.dir / "p.txt"
        out.write_text(proc.stdout, encoding="utf-8")
        self.assertEqual(run(LINT, out).stdout.strip(), "COMPLIANT")
        out.write_text(proc.stdout.replace(good, "0" * 64), encoding="utf-8")
        res = run(LINT, out)
        self.assertEqual(res.returncode, 1)
        self.assertIn("contract-sha256-mismatch", res.stdout)


class ContractParseTest(unittest.TestCase):
    def test_suffix_forms(self):
        h = "ab" * 32
        self.assertEqual(cdp.parse_contract_line(f"CONTRACT: skills/workerbee/header.md (sha256 {h})"),
                         ("skills/workerbee/header.md", h))
        self.assertEqual(cdp.parse_contract_line("CONTRACT: /x/header.md read it in full first."),
                         ("/x/header.md", None))
        self.assertEqual(cdp.parse_contract_line("contract:   `~/h.md`"), ("~/h.md", None))
        self.assertEqual(cdp.parse_contract_line("CONTRACT:"), ("", None))


class ReportProfileTest(unittest.TestCase):
    def test_missing_elements_named(self):
        self.assertEqual(cdp.check_report("hello"),
                         ["caveman", "grill", "provenance-tags", "out-of-scope-incomplete", "gate-exit-codes",
                          "workers-spawned"])

    def test_unreadable_caveman_declaration_accepted(self):
        text = ("caveman: unreadable -> by hand\nGRILL: none\n[verified] suite ok, exit code 0\n"
                "OUT OF SCOPE / INCOMPLETE: none\nWORKERS SPAWNED: 0\n")
        self.assertNotIn("caveman", cdp.check_report(text))

    def test_full_report(self):
        text = ("caveman ultra confirmed\nGRILL: none\n[verified] suite ok, exit code 0\n"
                "OUT OF SCOPE / INCOMPLETE: none\nWORKERS SPAWNED: 0\n")
        self.assertEqual(cdp.check_report(text), [])


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.env = {**os.environ, "HOME": self.tmp.name, "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1"}
        g = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, env=self.env)
        (self.repo / "a.txt").write_text("a\n")
        (self.repo / "b.txt").write_text("b\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True, env=self.env)
        subprocess.run(g + ["commit", "-qm", "init"], cwd=self.repo, check=True, env=self.env)
        (self.repo / "a.txt").write_text("a dirty\n")           # pre-existing dirty
        (self.repo / "u").mkdir()
        (self.repo / "u" / "deep.txt").write_text("u\n")        # pre-existing untracked dir
        self.snap = Path(self.tmp.name) / "snap.json"

    def tearDown(self):
        self.tmp.cleanup()

    def snapcmd(self, *args):
        return run(SNAP, *args, cwd=self.repo, env=self.env)

    def test_round_trip(self):
        self.assertEqual(self.snapcmd("capture", self.snap).returncode, 0)
        data = json.loads(self.snap.read_text())
        self.assertEqual(set(data), {"time", "head", "repo", "porcelain", "sha256", "ignored"})
        self.assertEqual(sorted(data["sha256"]), ["a.txt", "u/deep.txt"])
        self.assertEqual(data["sha256"]["a.txt"], hashlib.sha256(b"a dirty\n").hexdigest())
        self.assertEqual(self.snapcmd("verify", self.snap).returncode, 0)
        # allowed edit
        (self.repo / "b.txt").write_text("b2\n")
        self.assertEqual(self.snapcmd("verify", self.snap, "--allow", "b.txt").returncode, 0)
        res = self.snapcmd("verify", self.snap)
        self.assertEqual(res.returncode, 1)
        self.assertIn("CHANGED b.txt", res.stdout)

    def test_edit_to_dirty_file_detected(self):
        self.snapcmd("capture", self.snap)
        (self.repo / "a.txt").write_text("a overwritten\n")   # porcelain line unchanged
        res = self.snapcmd("verify", self.snap)
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stdout.strip(), "CHANGED a.txt")

    def test_new_file_inside_untracked_dir_detected(self):
        self.snapcmd("capture", self.snap)
        (self.repo / "u" / "new.txt").write_text("n\n")       # porcelain still `?? u/`
        res = self.snapcmd("verify", self.snap)
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stdout.strip(), "CHANGED u/new.txt")

    def test_allow_skips_hashed_file(self):
        self.snapcmd("capture", self.snap)
        # a.txt was dirty at capture and is in the hash list
        (self.repo / "a.txt").write_text("a modified again\n")
        # verify without allow detects change
        res = self.snapcmd("verify", self.snap)
        self.assertEqual(res.returncode, 1)
        self.assertIn("CHANGED a.txt", res.stdout)
        # verify with allow skips the hashed file
        res = self.snapcmd("verify", self.snap, "--allow", "a.txt")
        self.assertEqual(res.returncode, 0, res.stdout)




class FanOutTest(unittest.TestCase):
    def test_parse_fan_out(self):
        self.assertEqual(cdp.parse_fan_out("FAN_OUT: width 3, total 6, depth 2"), (3, 6, 2))
        self.assertIsNone(cdp.parse_fan_out("FAN_OUT: wide"))

    def test_malformed_fan_out_line_flagged(self):
        self.assertIn("fan-out", cdp.check("FAN_OUT: lots"))
        self.assertNotIn("fan-out", cdp.check("FAN_OUT: width 1, total 2, depth 1"))

    def test_prompt_without_fan_out_line_passes(self):
        self.assertNotIn("fan-out", cdp.check("ROLE: old prompt before D48"))

    def test_fan_out_trailing_sentence_accepted(self):
        line = "FAN_OUT: width 0, total 0, depth 0. Spawn no sub-agents."
        self.assertEqual(cdp.parse_fan_out(line), (0, 0, 0))
        self.assertNotIn("fan-out", cdp.check(line))

    def test_fan_out_missing_part_still_rejected(self):
        for line in ("FAN_OUT: width 0, total 0. Spawn none.",
                     "FAN_OUT: width 0, depth 0. Spawn none.",
                     "FAN_OUT: total 0, depth 0. Spawn none.",
                     "FAN_OUT: width 0, total 0, depth 0 spawn none"):
            with self.subTest(line=line):
                self.assertIn("fan-out", cdp.check(line))

    def test_fan_out_message_names_expected_form(self):
        labeled = cdp.label_missing(cdp.check("FAN_OUT: lots"))
        self.assertTrue(any("FAN_OUT: width N, total N, depth N" in str(m) for m in labeled), labeled)


class MissingLabelTest(unittest.TestCase):
    def test_label_missing_pairs_number_and_name(self):
        self.assertEqual(cdp.label_missing([2, 3, "stop-rule"]), ["2 success-gate", "3 failure-gate", "stop-rule"])

    def test_every_element_has_a_name(self):
        self.assertEqual(set(cdp.ELEMENT_NAMES), set(cdp.KEYWORDS))

    def test_cli_prints_number_and_name(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "p.md"
            p.write_text("nothing useful\n", encoding="utf-8")
            res = subprocess.run([sys.executable, cdp.__file__, str(p)], capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 1)
        self.assertIn("2 success-gate", res.stdout)
        self.assertIn("3 failure-gate", res.stdout)

class SharedRungSourceTest(unittest.TestCase):
    def test_renderer_and_checker_share_rung_source(self):
        import dispatch_rungs
        import render_dispatch
        self.assertIs(render_dispatch.MODEL_RUNG, dispatch_rungs.MODEL_RUNG)
        self.assertIs(render_dispatch.FAN_OUT_BY_RUNG, dispatch_rungs.FAN_OUT_BY_RUNG)
        self.assertIs(cdp.MODEL_RUNG, dispatch_rungs.MODEL_RUNG)
        self.assertIs(cdp.FAN_OUT_BY_RUNG, dispatch_rungs.FAN_OUT_BY_RUNG)
        self.assertFalse(hasattr(render_dispatch, "FAN_OUT_DEFAULTS"))
        self.assertFalse(hasattr(cdp, "FAN_OUT_CEILINGS"))

    def test_dispatch_load_resolves_shared_rungs_fresh_process(self):
        code = ("import sys\n"
                "from agents_inc.install import dispatch\n"
                "a = dispatch._load('check_dispatch_prompt')\n"
                "b = dispatch._load('render_dispatch')\n"
                "d = sys.modules['dispatch_rungs']\n"
                "assert a.MODEL_RUNG is d.MODEL_RUNG and b.MODEL_RUNG is d.MODEL_RUNG\n"
                "assert a.FAN_OUT_BY_RUNG is d.FAN_OUT_BY_RUNG is b.FAN_OUT_BY_RUNG\n"
                "print('SHARED', d.__file__)\n")
        r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=str(ROOT)))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(str(WB / "scripts" / "dispatch_rungs.py"), r.stdout)




class DeriveChainTest(unittest.TestCase):
    """derive_chain is pure; settings come in as a dict (SC-001)."""

    def chain(self, slots=None, model=None, settings=None):
        got = render_dispatch.derive_chain(slots or {}, model, settings or {})
        return f'{got["DELEGATE"]} < {got["SUPERVISOR"]} < {got["EXECUTIVE"]}'

    def test_defaults_by_vendor(self):
        self.assertEqual(self.chain(model="haiku"), "haiku < sonnet < fable")
        self.assertEqual(self.chain(model="luna"), "luna < terra < astra")
        self.assertEqual(self.chain(model="fable"), "fable < operator < operator")

    def test_setting_overrides_default(self):
        self.assertEqual(self.chain(model="haiku", settings={"chain": {"supervisor": "opus"}}), "haiku < opus < fable")

    def test_slot_beats_setting(self):
        got = self.chain({"SUPERVISOR": "sol"}, "haiku", {"chain": {"supervisor": "opus"}})
        self.assertEqual(got, "haiku < sol < fable")

    def test_role_text_fallback_first_hit_wins(self):
        self.assertEqual(self.chain({"ROLE": "Workhorse (sonnet, Agent tool)"}), "sonnet < opus < fable")
        self.assertEqual(self.chain({"ROLE": "Grunt (haiku) dispatched by Supervisor (opus)"}),
                         "haiku < sonnet < fable")

    def test_unknown_delegate(self):
        self.assertEqual(self.chain({"ROLE": "nobody"}), "delegate < CoS < CoS")

    def test_malformed_settings_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".config" / "agents-inc"
            cfg.mkdir(parents=True)
            (cfg / "settings.json").write_text("{not json")
            old = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                self.assertEqual(render_dispatch.read_settings(), {})
                (cfg / "settings.json").write_text('{"chain": {"supervisor": "opus"}}')
                self.assertEqual(self.chain(model="haiku", settings=render_dispatch.read_settings()),
                                 "haiku < opus < fable")
            finally:
                if old is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old


class Issue100Test(RenderTest):
    """#100: string GATES entries and a defaulted PRE_EXISTING_CHANGES."""

    def test_gates_accept_plain_command_strings(self):
        gates, why = render_dispatch.parse_gates(["python3 -m unittest tests.test_x", {"argv": ["true"]}])
        self.assertIsNone(why)
        self.assertEqual(gates[0]["argv"], ["python3", "-m", "unittest", "tests.test_x"])
        self.assertEqual((gates[0]["cwd"], gates[0]["timeout_s"], gates[0]["expect_rc"]), (".", 600, 0))
        self.assertEqual(gates[1]["argv"], ["true"])

    def test_blank_gate_string_is_refused(self):
        _, why = render_dispatch.parse_gates(["  "])
        self.assertIn("argv", why)

    def test_pre_existing_changes_defaults_with_allow_from_files_in_scope(self):
        slots = self.example()
        slots.pop("PRE_EXISTING_CHANGES")
        slots["FILES_IN_SCOPE"] = "agents_inc/policy.py\ntests/test_policy.py\nnone of the docs"
        proc = self.render(slots)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("defaults filled: PRE_EXISTING_CHANGES", proc.stderr)
        self.assertIn("snapshot <snapshot>; verify with `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify "
                      "<snapshot> --allow agents_inc/policy.py --allow tests/test_policy.py`", proc.stdout)

    def test_pre_existing_changes_default_without_paths_has_no_allow(self):
        slots = self.example()
        slots["PRE_EXISTING_CHANGES"] = ""
        proc = self.render(slots)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        line = proc.stdout.split("PRE-EXISTING CHANGES")[1].split("\n")[1]
        self.assertTrue(line.endswith("verify <snapshot>`"), line)


class Issue92Test(RenderTest):
    """#92: the snapshot verify gate is one plain command, never `cd <repo> && ...`."""

    def test_compound_verify_command_is_refused(self):
        for cmd in ("cd /repo && python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify /x/s.json",
                    "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify /x/s.json && echo ok"):
            slots = self.example()
            slots["PRE_EXISTING_CHANGES"] = f"snapshot /x/s.json; verify with `{cmd}`"
            proc = self.render(slots)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("PRE_EXISTING_CHANGES invalid", proc.stderr)

    def test_plain_verify_command_renders(self):
        slots = self.example()
        slots["PRE_EXISTING_CHANGES"] = ("snapshot /x/snapshot.json; verify with "
                                         "`python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify /x/snapshot.json`")
        proc = self.render(slots)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class VerifyGateParseTest(RenderTest):
    """#108: the verify gate is parsed by argv position, not matched by substring."""

    def _render_gate(self, cmd):
        slots = self.example()
        slots["PRE_EXISTING_CHANGES"] = f"snapshot <snapshot>; verify with `{cmd}`"
        return self.render(slots)

    def test_bad_gates_exit_2(self):
        for cmd in ("cd /tmp && python3 pre_dispatch_snapshot.py verify <snapshot>",
                    "python3 pre_dispatch_snapshot.py verify <snapshot>",
                    "python3 x.py verify <snapshot>"):
            with self.subTest(cmd=cmd):
                proc = self._render_gate(cmd)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertIn("PRE_EXISTING_CHANGES invalid: ", proc.stderr)
                self.assertIn("; write the verify gate as one plain command", proc.stderr)

    def test_default_text_renders(self):
        slots = self.example()
        slots["FILES_IN_SCOPE"] = "agents_inc/policy.py"
        slots["PRE_EXISTING_CHANGES"] = render_dispatch.default_pre_existing(slots["FILES_IN_SCOPE"])
        proc = self.render(slots)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_hand_written_absolute_form_renders(self):
        proc = self._render_gate("/usr/bin/python3 /abs/skills/workerbee/scripts/pre_dispatch_snapshot.py verify "
                                 "/abs/run/snapshot.json --repo /abs --allow a.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_verify_gate_ok_unit(self):
        ok = render_dispatch.verify_gate_ok
        self.assertIsNone(ok("python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot> --allow a.py"))
        for span in ("python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot> | cat",
                     "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>; rm x",
                     "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify $(cat s)",
                     "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot> > out",
                     "python3 skills/workerbee/scripts/../scripts/pre_dispatch_snapshot.py verify <snapshot>",
                     "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py capture <snapshot>",
                     "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify /x/s.json",
                     "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot> --allow",
                     "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot> --force x",
                     "bash skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>",
                     "python3 'skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>"):
            with self.subTest(span=span):
                self.assertIsInstance(ok(span), str)


if __name__ == "__main__":
    unittest.main()
