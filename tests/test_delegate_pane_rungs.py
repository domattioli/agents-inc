"""mods/delegate-pane/hooks/rungs.ts must agree with agents_inc/models.json and MODEL_RUNG (spec 039 R3).

Strict: every models.json id and nickname is listed; every entry equals the models.json tier and, where MODEL_RUNG names
it, MODEL_RUNG's rung; no entry sits outside the markers; every line between the markers is one the parser reads.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNGS_TS = ROOT / "mods" / "delegate-pane" / "hooks" / "rungs.ts"
MODELS = ROOT / "agents_inc" / "models.json"
DISPATCH_RUNGS = ROOT / "skills" / "workerbee" / "scripts" / "dispatch_rungs.py"
BEGIN, END = "// RUNGS-BEGIN", "// RUNGS-END"
ENTRY = re.compile(r"^\s*'([^']+)':\s*'([^']+)',\s*$")
# The only other lines allowed between the markers.
FRAME = re.compile(r"^\s*(export const RUNGS: Record<string, string> = \{|\}|//.*|)\s*$")
# Anything that looks like a table entry, in any quoting.
LOOKS_LIKE_ENTRY = re.compile(r"""['"`][^'"`]+['"`]\s*:\s*['"`](grunt|workhorse|orchestrator|executive)['"`]""")


def parse_rungs(text: str) -> dict[str, str]:
    """Entries between the markers. Raises ValueError on a line the parser would skip, a duplicate, or a missing marker."""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("rungs.ts must hold exactly one RUNGS-BEGIN and one RUNGS-END marker")
    before, rest = text.split(BEGIN, 1)
    body, after = rest.split(END, 1)
    for part, where in ((before, "before RUNGS-BEGIN"), (after, "after RUNGS-END")):
        if LOOKS_LIKE_ENTRY.search(part):
            raise ValueError(f"rung entry {where}: {LOOKS_LIKE_ENTRY.search(part).group(0)}")
    out: dict[str, str] = {}
    for line in body.splitlines():
        m = ENTRY.match(line)
        if m:
            if m.group(1) in out:
                raise ValueError(f"duplicate rung entry {m.group(1)}")
            out[m.group(1)] = m.group(2)
        elif not FRAME.match(line):
            raise ValueError(f"line between the markers in a form the parser skips: {line!r}")
    return out


def model_rung() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("dispatch_rungs", DISPATCH_RUNGS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return dict(mod.MODEL_RUNG)


def tiers_for(name: str, models: dict[str, dict], aliases: dict[str, str]) -> set[str]:
    """Tiers `name` stands for: its id or nickname; or, for a MODEL_RUNG alias only, every id ending -<name>."""
    found = {spec["tier"] for mid, spec in models.items() if name in (mid, spec.get("nickname"))}
    if not found and name in aliases:
        found = {spec["tier"] for mid, spec in models.items() if mid.endswith("-" + name)}
    return found


class DelegatePaneRungs(unittest.TestCase):
    def setUp(self) -> None:
        self.models = json.loads(MODELS.read_text(encoding="utf-8"))["models"]
        self.aliases = model_rung()
        self.rungs = parse_rungs(RUNGS_TS.read_text(encoding="utf-8"))

    def test_every_models_json_id_and_nickname_is_listed(self) -> None:
        for mid, spec in self.models.items():
            self.assertIn(mid, self.rungs, f"model id {mid} missing from rungs.ts (the pane would draw ?)")
            if spec.get("nickname"):
                self.assertIn(spec["nickname"], self.rungs, f"nickname {spec['nickname']} missing from rungs.ts")

    def test_each_entry_equals_models_json_tier(self) -> None:
        for name, rung in self.rungs.items():
            tiers = tiers_for(name, self.models, self.aliases)
            self.assertTrue(tiers, f"{name} is not a models.json id or nickname, nor a MODEL_RUNG alias")
            self.assertEqual({rung}, tiers, f"{name}: rungs.ts says {rung}, models.json says {sorted(tiers)}")

    def test_each_entry_equals_model_rung(self) -> None:
        for name, rung in self.rungs.items():
            if name in self.aliases:
                self.assertEqual(self.aliases[name], rung, f"{name}: rungs.ts says {rung}, MODEL_RUNG says {self.aliases[name]}")

    def test_every_model_rung_alias_is_listed(self) -> None:
        for name in self.aliases:
            self.assertIn(name, self.rungs, f"MODEL_RUNG alias {name} missing from rungs.ts")

    def test_models_json_agrees_with_model_rung(self) -> None:
        """Not a rungs.ts check: reports a disagreement between the two sources themselves."""
        for name, rung in self.aliases.items():
            tiers = tiers_for(name, self.models, self.aliases)
            self.assertEqual({rung}, tiers, f"MODEL_RUNG {name}={rung} but models.json gives {sorted(tiers)}")


class ParserIsStrict(unittest.TestCase):
    """The parser itself: forms it would skip, and entries outside the markers, fail."""

    GOOD = f"{BEGIN}\nexport const RUNGS: Record<string, string> = {{\n  // c\n  'a': 'grunt',\n}}\n{END}\n"

    def test_good_parses(self) -> None:
        self.assertEqual({"a": "grunt"}, parse_rungs(self.GOOD))

    def test_skipped_forms_fail(self) -> None:
        for bad in ('  "a": "grunt",', "  a: 'grunt',", "  'a': 'grunt'", "  'a': 'grunt', 'b': 'grunt',", "  'a':'grunt' // x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_rungs(self.GOOD.replace("  // c", bad))

    def test_entry_outside_markers_fails(self) -> None:
        with self.assertRaises(ValueError):
            parse_rungs("const X = { 'b': 'workhorse' }\n" + self.GOOD)
        with self.assertRaises(ValueError):
            parse_rungs(self.GOOD + "Object.assign(RUNGS, { 'b': 'grunt' })\n")

    def test_duplicate_and_missing_marker_fail(self) -> None:
        with self.assertRaises(ValueError):
            parse_rungs(self.GOOD.replace("  // c", "  'a': 'grunt',"))
        with self.assertRaises(ValueError):
            parse_rungs(self.GOOD.replace(END, ""))


if __name__ == "__main__":
    unittest.main()
