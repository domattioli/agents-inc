import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "workerbee" / "SKILL.md"
QUICKREF = ROOT / "skills" / "workerbee" / "QUICKREF.md"

# (step heading prefix, keyword). Fixed once from the source steps (issue #45).
KEYWORDS = [
    ("Step 0:", "out loud"),
    ("Step 0.5:", "vendor gate"),
    ("Step 2:", "supervisor owns the verifier"),
    ("Step 3a:", "poll.sh"),
    ("Step 11:", "caveman NOT installed"),
    ("Step 11:", "SUB-DELEGATE MODEL"),
    ("Step 11:", "LESSON-CANDIDATE"),
]


def step_text(skill_text, prefix):
    pat = re.compile(r"^#{3,4} " + re.escape(prefix), re.M)
    m = pat.search(skill_text)
    if not m:
        return None
    nxt = re.compile(r"^#{3,4} Step ", re.M).search(skill_text, m.end())
    return skill_text[m.start():nxt.start() if nxt else len(skill_text)]


class QuickrefMustParityTest(unittest.TestCase):
    def test_keywords_in_step_and_quickref(self):
        skill = SKILL.read_text(encoding="utf-8")
        quick = QUICKREF.read_text(encoding="utf-8").lower()
        for prefix, kw in KEYWORDS:
            with self.subTest(step=prefix, keyword=kw):
                body = step_text(skill, prefix)
                self.assertIsNotNone(body, f"{prefix} missing from SKILL.md")
                self.assertIn(kw.lower(), body.lower())
                self.assertIn(kw.lower(), quick)


class DispatchGateD78Test(unittest.TestCase):
    """D78: three-way dispatch gate and roles by rung in QUICKREF and SKILL.md."""
    def test_quickref_gate_and_ladder(self):
        quick = QUICKREF.read_text(encoding="utf-8")
        self.assertNotIn("Three or fewer: do it yourself", quick)
        self.assertIn("Three or fewer that write nothing: do it yourself", quick)
        self.assertIn("Three or fewer that edit files: a native workhorse subagent", quick)
        self.assertIn("| grunt | haiku | luna | read-only", quick)
        self.assertIn("| workhorse | sonnet | terra | default for anything that writes", quick)

    def test_skill_step0_and_grunt_rule(self):
        skill = SKILL.read_text(encoding="utf-8")
        step0 = step_text(skill, "Step 0:")
        self.assertNotIn("If the estimate is 3 or", step0)
        self.assertIn("3 or fewer, edits files:", step0)
        self.assertNotIn("editing goes to grunt", skill)
        self.assertIn("editing goes to workhorse", skill)


if __name__ == "__main__":
    unittest.main()
