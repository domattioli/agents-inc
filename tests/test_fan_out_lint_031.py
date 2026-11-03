"""Spec 031 FR-009/FR-010: the FAN_OUT lint accepts trailing prose and names the expected form; the consensus-debate
step 4 brief template carries its five plain lines."""
from __future__ import annotations
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/workerbee/scripts/check_dispatch_prompt.py"
sys.path.insert(0, str(ROOT / "skills/workerbee/scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import check_dispatch_prompt as cdp  # noqa: E402
from test_dispatch_contract import COMPLIANT_PROMPT  # noqa: E402

SKILL = ROOT / "skills/consensus-debate/SKILL.md"


def _lint(text):
    with tempfile.TemporaryDirectory() as tmp:
        prompt = Path(tmp) / "prompt.txt"
        prompt.write_text(text)
        return subprocess.run([sys.executable, str(SCRIPT), str(prompt)], capture_output=True, text=True)


class FanOutLintTest(unittest.TestCase):
    def test_trailing_prose_is_compliant(self):
        r = _lint(COMPLIANT_PROMPT + "FAN_OUT: width 0, total 0, depth 0. Spawn no sub-agents.\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("COMPLIANT", r.stdout)

    def test_words_instead_of_numbers_fail_with_the_expected_form(self):
        r = _lint(COMPLIANT_PROMPT + "FAN_OUT: width zero\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAN_OUT: width N, total N, depth N", r.stdout)

    def test_depth_with_glued_suffix_fails(self):
        self.assertIn("fan-out", cdp.check(COMPLIANT_PROMPT + "FAN_OUT: width 0, total 0, depth 0x\n"))

    def test_key_stays_fan_out_for_callers(self):
        self.assertIn("fan-out", cdp.check(COMPLIANT_PROMPT + "FAN_OUT: width zero\n"))


class DebateBriefTemplateTest(unittest.TestCase):
    def _step4(self):
        text = SKILL.read_text()
        start = text.index("4. **One brief")
        end = text.index("5. **R1 blind")
        return re.sub(r"```.*?```", "", text[start:end], flags=re.S)

    def test_template_has_five_plain_labels(self):
        step = self._step4()
        for label in ("GOAL", "CONSTRAINTS", "DONE", "OUT OF SCOPE", "STOP ON BLOCK"):
            self.assertRegex(step, rf"(?m)^[ \t]*{label}:", label)
        self.assertNotRegex(step, r"(?m)^\s*>")

    def test_stop_on_block_line_forbids_workarounds(self):
        line = [ln for ln in self._step4().splitlines() if ln.strip().startswith("STOP ON BLOCK:")][0].lower()
        for word in ("block", "stop", "never"):
            self.assertIn(word, line)


if __name__ == "__main__":
    unittest.main()
