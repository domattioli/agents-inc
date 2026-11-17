"""Spec 042 US4 (FR-023): one registry. `--rules` lists every id and statement, QUICKREF names the command, and the script copies agree."""
from __future__ import annotations
import ast
import re
import unittest
from pathlib import Path

from agents_inc.install import rules

REPO = Path(__file__).resolve().parents[1]
QUICKREF = (REPO / "skills/workerbee/QUICKREF.md").read_text(encoding="utf-8")
SCRIPTS = REPO / "skills/workerbee/scripts"
LINE_RE = re.compile(r"^- `([a-z0-9-]+)`: (.+)$", re.M)


def _function_source(path: Path, name: str) -> str | None:
    text = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    return None


class RulesListingCoversRegistry(unittest.TestCase):
    """D87 item 2 as amended 2026-11-16: `--rules` lists every rule; QUICKREF names the command, not the list."""
    def test_rules_listing_has_every_rule_once_with_statement(self):
        lines = rules.rules_listing().splitlines()
        self.assertEqual(len(lines), len(rules.RULES))
        for rid, rule in rules.RULES.items():
            with self.subTest(rule=rid):
                self.assertEqual([ln for ln in lines if ln.startswith(rid + ": ")], [f"{rid}: {rule['summary']}"])

    def test_cli_rules_flag_prints_listing(self):
        import contextlib, io
        from agents_inc.install import cli
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(["dispatch", "--rules"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), rules.rules_listing())

    def test_quickref_names_command_and_lists_no_rule(self):
        self.assertIn("agents-inc dispatch --rules", QUICKREF)
        self.assertEqual(LINE_RE.findall(QUICKREF), [])


class ScriptCopiesMatch(unittest.TestCase):
    def test_format_function_copies_equal_registry(self):
        want = _function_source(REPO / "agents_inc/install/rules.py", "format_refusal")
        self.assertIsNotNone(want)
        for name in ("render_dispatch.py", "check_dispatch_prompt.py"):
            with self.subTest(script=name):
                self.assertEqual(_function_source(SCRIPTS / name, "format_refusal"), want)

    def test_script_rule_tables_equal_registry(self):
        import importlib.util
        for name in ("render_dispatch", "check_dispatch_prompt"):
            spec = importlib.util.spec_from_file_location(f"_{name}", SCRIPTS / f"{name}.py")
            mod = importlib.util.module_from_spec(spec)
            import sys
            sys.path.insert(0, str(SCRIPTS))
            try:
                spec.loader.exec_module(mod)
            finally:
                sys.path.remove(str(SCRIPTS))
            table = getattr(mod, "REFUSAL_RULES")
            for rid, (summary, fix) in table.items():
                with self.subTest(script=name, rule=rid):
                    self.assertEqual((summary, fix), (rules.RULES[rid]["summary"], rules.RULES[rid]["example_fix"]))


class RefusalSitesUseRegistry(unittest.TestCase):
    def test_every_id_used_at_a_site_is_registered(self):
        pat = re.compile(r"""(?:refuse|one_line|refusal_block|_refusal|with_refusal|refusal_lines)\(\s*["']([a-z0-9-]+)["']""")
        for rel in ("agents_inc/install/dispatch.py", "agents_inc/install/hook.py", "agents_inc/install/mcp_broker.py",
                    "skills/workerbee/scripts/render_dispatch.py", "skills/workerbee/scripts/check_dispatch_prompt.py"):
            text = (REPO / rel).read_text(encoding="utf-8")
            for rid in pat.findall(text):
                with self.subTest(file=rel, rule=rid):
                    self.assertIn(rid, rules.RULES)


if __name__ == "__main__":
    unittest.main()
