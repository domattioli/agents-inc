"""Spec 042 US4 (FR-024): no refusal or lint message names the install tree; a pointer names a command that prints it."""
from __future__ import annotations
import re
import unittest
from pathlib import Path

from agents_inc.install import rules

REPO = Path(__file__).resolve().parents[1]
INSTALL_PATH = re.compile(r"~/\.claude/skills|\.local/share/agents-inc|\$HOME/\.claude|/\.claude/skills")


class NoInstallPath(unittest.TestCase):
    def test_registry_text_names_no_install_path(self):
        for rid, rule in rules.RULES.items():
            with self.subTest(rule=rid):
                self.assertIsNone(INSTALL_PATH.search(rule["summary"] + " " + rule["example_fix"]))

    def test_template_pointers_name_commands(self):
        for rid, rule in rules.RULES.items():
            if "template" in rule["example_fix"]:
                with self.subTest(rule=rid):
                    self.assertIn("agents-inc dispatch --print-template", rule["example_fix"])

    def test_quickref_lint_paragraph_names_commands_not_paths(self):
        text = (REPO / "skills/workerbee/QUICKREF.md").read_text(encoding="utf-8")
        para = next(p for p in text.split("\n\n") if p.startswith("Lint (mandatory"))
        self.assertIsNone(INSTALL_PATH.search(para))
        self.assertIn("agents-inc dispatch --rules", para)
        self.assertIn("agents-inc dispatch --print-template", para)

    def test_refusal_site_strings_name_no_install_path(self):
        for rel in ("skills/workerbee/scripts/check_dispatch_prompt.py", "skills/workerbee/scripts/render_dispatch.py"):
            text = (REPO / rel).read_text(encoding="utf-8")
            for ln in text.splitlines():
                if "print(" in ln and ("NON-COMPLIANT" in ln or "refused" in ln):
                    with self.subTest(file=rel, line=ln.strip()[:60]):
                        self.assertIsNone(INSTALL_PATH.search(ln))


if __name__ == "__main__":
    unittest.main()
