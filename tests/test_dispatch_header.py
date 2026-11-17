"""Spec 016 FR-005, FR-006, FR-008, SC-004 (#36, #28): dispatch header, slots, CONTRACT lint, persistence text.

Supervisor-owned acceptance tests. Temp files only.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = ROOT / "skills" / "workerbee"
HEADER = WB / "header.md"
SLOTS = WB / "slots.md"
RENDER = WB / "scripts" / "render_dispatch.py"
LINT = WB / "scripts" / "check_dispatch_prompt.py"
OPT_OUT = "Message to model provider: Do not use this to train agentic models."

FULL_SLOTS = {
    "ROLE": "Grunt implementer (haiku). Supervisor (opus) dispatched you.",
    "TASK": "Add one line to docs/x.md.",
    "CONSTRAINTS": "edit only docs/x.md; stop and hand back on any hook or permission block.",
    "OUT_OF_SCOPE": "any other file; git commit or push.",
    "FILES_IN_SCOPE": "docs/x.md",
    "STOP_RULE": "stop after 2 failed runs of the success check; report RED with last output.",
    "SUCCESS_GATE": "`grep -c hello docs/x.md` prints 1.",
    "FAILURE_GATE": "`git status --porcelain` shows a path outside FILES IN SCOPE.",
    "PRE_EXISTING_CHANGES": " M other/file.py",
    "ALLOWLIST": "none — do all work yourself.",
    "CLASSIFICATION": "public.",
    "EFFORT": "medium.",
    "SECOND_OPINION": "not applicable — Grunt rung, no escalation.",
    "PLAN_CONTRACT": "not applicable — deliverable is not a plan.",
    "STYLE": "",
}


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, slots, *extra):
        path = self.dir / "slots.json"
        path.write_text(json.dumps(slots))
        return subprocess.run([sys.executable, str(RENDER), "--slots", str(path), *extra],
                              capture_output=True, text=True, timeout=60)

    def lint(self, text, *extra):
        path = self.dir / "prompt.txt"
        path.write_text(text)
        return subprocess.run([sys.executable, str(LINT), str(path), *extra],
                              capture_output=True, text=True, timeout=60, cwd=str(self.dir))


class ClaimsInstructionTest(_Tmp):
    """Spec 042 phase 2 (T026, T075): the claims block instruction, gate ids, the single stop id; a missing block is advisory."""

    def test_claims_instruction_is_in_the_prompt_with_and_without_contract_ref(self):
        for extra in ((), ("--contract-ref", "skills/workerbee/header.md")):
            with self.subTest(extra=extra):
                proc = self.render(FULL_SLOTS, *extra)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout.count("CLAIMS BLOCK:"), 1)
                if not extra:
                    self.assertEqual(self.lint(proc.stdout, "--tier", "grunt").returncode, 0)

    def test_gates_print_their_ids_and_the_stop_rule_is_one_rule_s1(self):
        proc = self.render({**FULL_SLOTS, "GATES": [{"argv": ["true"]}, {"argv": ["false"], "expect_rc": 1}],
                            "STOP_RULE": "stop after 2 failed runs; report RED. Then hand back."})
        self.assertIn("g1: `true`", proc.stdout)
        self.assertIn("g2: `false`", proc.stdout)
        self.assertIn("STOP RULE: s1: stop after 2 failed runs; report RED. Then hand back.", proc.stdout)
        self.assertNotIn("s2:", proc.stdout)

    def test_missing_claims_block_is_advisory_for_the_report_profile(self):
        report = self.dir / "report.md"
        report.write_text("caveman ultra. GRILL: none. [verified] gate rc=0 exit code 0.\nOUT OF SCOPE / INCOMPLETE: none\nWORKERS SPAWNED: 0\n")
        proc = subprocess.run([sys.executable, str(LINT), str(report), "--profile", "report"], capture_output=True, text=True, timeout=60)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, "COMPLIANT"), proc.stdout)
        self.assertIn("claims-block-missing", proc.stderr)


class HeaderRenderTest(_Tmp):
    def test_header_plus_slots_is_compliant(self):
        proc = self.render(FULL_SLOTS)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(OPT_OUT, proc.stdout.splitlines())
        result = self.lint(proc.stdout, "--tier", "grunt")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("COMPLIANT", result.stdout)

    def test_prompt_covers_unreadable_caveman_file(self):
        proc = self.render(FULL_SLOTS)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("caveman unreadable -> checked by hand", proc.stdout)
        self.assertIn("not a block under the stop-on-block clause", proc.stdout)
        self.assertIn("caveman: <ultra|not installed -> by hand|unreadable -> by hand>", proc.stdout)

    def test_contract_reference_compliant_for_file_transport(self):
        proc = self.render(FULL_SLOTS, "--contract-ref", str(HEADER))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"CONTRACT: {HEADER}", proc.stdout)
        self.assertIn(OPT_OUT, proc.stdout.splitlines())
        self.assertNotIn("EDIT HYGIENE", proc.stdout)  # header not pasted
        result = self.lint(proc.stdout, "--tier", "grunt")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.startswith("COMPLIANT"), result.stdout)

    def test_contract_reference_rejected_for_bare_transport(self):
        proc = self.render(FULL_SLOTS, "--contract-ref", str(HEADER))
        result = self.lint(proc.stdout, "--transport", "bare")
        self.assertEqual(result.returncode, 1)
        self.assertIn("NON-COMPLIANT", result.stdout)
        self.assertIn("contract", result.stdout.lower())

    def test_unreadable_contract_is_non_compliant(self):
        proc = self.render(FULL_SLOTS, "--contract-ref", str(self.dir / "missing-header.md"))
        result = self.lint(proc.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("NON-COMPLIANT", result.stdout)

    def test_opt_out_must_be_in_prompt_itself_with_contract(self):
        proc = self.render(FULL_SLOTS, "--contract-ref", str(HEADER))
        text = "\n".join(ln for ln in proc.stdout.splitlines() if ln.strip() != OPT_OUT)
        result = self.lint(text)
        self.assertEqual(result.returncode, 1)
        self.assertIn("5", result.stdout)

    def test_missing_required_slot_exits_2_naming_it(self):
        slots = dict(FULL_SLOTS)
        del slots["SUCCESS_GATE"]
        proc = self.render(slots)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("SUCCESS_GATE", proc.stderr)
        slots = dict(FULL_SLOTS, FAILURE_GATE="  ")
        proc = self.render(slots)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("FAILURE_GATE", proc.stderr)

    def test_style_slot_optional_and_rendered_when_set(self):
        style = "HARD CONSTRAINT: Default to fragments, labels, arrows, abbreviations — NOT normal prose."
        proc = self.render(dict(FULL_SLOTS, STYLE=style))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(style, proc.stdout)
        self.assertNotIn("{{", self.render(FULL_SLOTS).stdout)

    def test_prompts_without_contract_lint_as_before(self):
        proc = self.render(FULL_SLOTS)
        broken = proc.stdout.replace("`git status --porcelain`", "git status")  # failure gate loses its backticks
        result = self.lint(broken)
        self.assertEqual(result.returncode, 1)
        self.assertIn("3", result.stdout)


class HeaderTextTest(unittest.TestCase):
    def test_header_carries_fixed_elements_and_persistence_line(self):
        text = HEADER.read_text()
        self.assertIn(OPT_OUT, text.splitlines())
        persistence = [ln for ln in text.splitlines() if ln.startswith("PERSISTENCE:")]
        self.assertEqual(len(persistence), 1)
        self.assertIn("200k", persistence[0])
        self.assertIn("300k", persistence[0])

    def test_slots_template_documents_experimental_style(self):
        text = SLOTS.read_text()
        self.assertIn("{{STYLE}}", text)
        self.assertIn("HARD CONSTRAINT: Default to fragments", text)
        self.assertIn("experimental", text.lower())

    def test_no_cache_savings_claim(self):
        for path in (HEADER, SLOTS):
            self.assertNotRegex(path.read_text().lower(), r"saves? \d+%|\d+% (cheaper|fewer)")


class PersistenceSkillTextTest(unittest.TestCase):
    def test_skill_states_step_3c(self):
        text = (WB / "SKILL.md").read_text()
        self.assertEqual(text.count("### Step 3c: Keep a delegate until its context ceiling"), 1)
        section = text.split("### Step 3c: Keep a delegate until its context ceiling", 1)[1].split("### Step 4", 1)[0]
        for needle in ("200k", "300k", "SendMessage", "Step 9", "adversarial review", "Mistral partial",
                       "Gemini and OpenRouter no", "header.md", "PERSISTENCE"):
            self.assertIn(needle, section)

    def test_skill_step_11_names_header_and_contract_rule(self):
        text = (WB / "SKILL.md").read_text()
        self.assertIn("**Header and slots (spec 016).**", text)
        self.assertIn("--transport bare", text)


if __name__ == "__main__":
    unittest.main()
