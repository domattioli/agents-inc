import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_terms  # noqa: E402

SCRIPT = ROOT / "tools" / "check_terms.py"
FIX = ROOT / "tests" / "fixtures" / "041"
CONFIG = json.loads((ROOT / "tools" / "retired_terms.json").read_text(encoding="utf-8"))


def run_lint(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def parse_term_table(text):
    """Return a list of (term, retired_cell) from the CONTEXT.md term table."""
    rows, in_table = [], False
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not in_table:
            if len(cells) >= 4 and cells[-1].lower().startswith("retired aliases"):
                in_table = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append((cells[0].strip("* "), cells[-1]))
    return rows


def split_top(cell):
    """Split a retired-aliases cell on ';' outside parentheses."""
    parts, depth, cur = [], 0, ""
    for ch in cell:
        depth += ch == "("
        depth -= ch == ")"
        if ch == ";" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


class FixtureLint(unittest.TestCase):
    # fixture -> words the lint must print
    BAD = {
        "bad_ceo.md": ["The Owner"],
        "bad_chief_of_staff_cos.md": ["Interlocutor", "- Driver"],
        "bad_lead.md": ["aliases Supervisor, Orchestrator"],
        "bad_worker.md": ["alias Workhorse", "aliases Workhorse and Grunt"],
        "bad_supervisor.md": ["Supervisor"],
        "bad_supervisor_sentence_start.md": ["Supervisor"],
        "bad_one_rung_up.md": ["one rung up"],
        "bad_executive.md": ["ultra-tier", "frontier tier"],
        "bad_grunt.md": ["flash-tier", "cheap-tier"],
        "bad_rung.md": ["Tier:", "mid-tier"],
        "bad_plural.md": ["Supervisors", "Interlocutors", "The Owners", "Tiers:"],
        "bad_tier_owner_forms.md": ["| Tier |", "- Owner: t", "Ultra tier", "FLASH TIER", "One Rung Up"],
        "bad_aliases.md": ["Aliases: Workhorse, Grunt", "aka Orchestrator"],
    }

    def test_each_bad_fixture_fails_with_file_line_word_replacement(self):
        for name, words in self.BAD.items():
            with self.subTest(fixture=name):
                r = run_lint(FIX / name)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                for word in words:
                    pattern = re.escape(f"tests/fixtures/041/{name}") + r":\d+: " + re.escape(word) + r" -> .+"
                    self.assertRegex(r.stdout, pattern)

    def test_every_pattern_row_has_a_bad_fixture(self):
        rows = {p["row"] for p in CONFIG["patterns"]}
        covered = set()
        for name in self.BAD:
            out = run_lint(FIX / name).stdout
            for p in CONFIG["patterns"]:
                for line in out.splitlines():
                    if line.endswith("-> " + p["replacement"]):
                        covered.add(p["row"])
        self.assertEqual(rows - covered, set())

    def test_every_pattern_fires_on_some_fixture(self):
        text = "\n".join((FIX / n).read_text(encoding="utf-8") for n in self.BAD)
        for p in CONFIG["patterns"]:
            with self.subTest(pattern=p["pattern"]):
                self.assertTrue(re.search(p["pattern"], text, re.M), "no fixture seeds this pattern")

    def test_good_generic_passes(self):
        r = run_lint(FIX / "good_generic.md")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_cutoff_flags_only_entries_at_or_after_cutoff(self):
        r = run_lint("--cutoff", "901", FIX / "decisions_cutoff.md")
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 1, r.stdout)
        self.assertIn("decisions_cutoff.md:9:", lines[0])
        text = (FIX / "decisions_cutoff.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("D901", text[6])  # heading above the flagged line

    def test_null_cutoff_treats_all_entries_as_history(self):
        text = (FIX / "decisions_cutoff.md").read_text(encoding="utf-8")
        found = check_terms.scan_text(text, check_terms.load_config()[0], None, True)
        self.assertEqual(found, [])

    def test_allowlisted_path_is_ignored(self):
        allow = CONFIG["allowlist"]
        for rel in ("CHANGELOG.md", "tests/fixtures/041/bad_lead.md", "fixtures/x.md",
                    "skills/workerbee/tests/y.md", "docs/adr/0001.md"):
            with self.subTest(path=rel):
                self.assertTrue(check_terms.is_allowlisted(rel, allow))
        self.assertFalse(check_terms.is_allowlisted("CONTEXT.md", allow))
        r = run_lint("--allowlist", FIX / "bad_lead.md")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_fenced_and_inline_code_skipped(self):
        text = "```\nSupervisor\n```\nuse `Supervisor` here\n"
        self.assertEqual(check_terms.scan_text(text, check_terms.load_config()[0]), [])

    def test_retired_column_of_term_table_is_exempt(self):
        text = ("| Term | Axis | Definition | Retired aliases (check) |\n|---|---|---|---|\n"
                "| Lead | role | x | Supervisor (lint) |\n\nSupervisor outside.\n")
        found = check_terms.scan_text(text, check_terms.load_config()[0], is_context=True)
        self.assertEqual([f[0] for f in found], [5])

    def test_retired_column_exemption_applies_only_to_context_md(self):
        text = ("| Term | Axis | Definition | Retired aliases (check) |\n|---|---|---|---|\n"
                "| Lead | role | x | Supervisor (lint) |\n")
        found = check_terms.scan_text(text, check_terms.load_config()[0])
        self.assertEqual([f[0] for f in found], [3])

    def test_non_decision_heading_ends_skipped_entry(self):
        text = ("## D1 old\nSupervisor in history.\n## Appendix\nSupervisor in current text.\n")
        found = check_terms.scan_text(text, check_terms.load_config()[0], 83, True)
        self.assertEqual([f[0] for f in found], [4])

    def test_fence_closes_only_on_same_character(self):
        text = "```\nSupervisor\n~~~\nSupervisor\n```\nSupervisor\n"
        found = check_terms.scan_text(text, check_terms.load_config()[0])
        self.assertEqual([f[0] for f in found], [6])

    def test_missing_git_prints_one_error_line_and_exits_2(self):
        env = dict(os.environ, PATH=str(FIX))  # no git on PATH
        r = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_bad_config_exits_2(self):
        self.assertRaises(check_terms.ConfigError, check_terms.load_config, FIX / "good_generic.md")
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(SCRIPT, tmp)
            Path(tmp, "retired_terms.json").write_text("{not json", encoding="utf-8")
            r = subprocess.run([sys.executable, str(Path(tmp, "check_terms.py")), str(FIX / "good_generic.md")],
                               cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class TermTable(unittest.TestCase):
    def setUp(self):
        self.rows = parse_term_table(read("CONTEXT.md"))

    def test_table_exists(self):
        self.assertTrue(self.rows, "CONTEXT.md has no term table with a Retired aliases column")

    def test_every_pattern_row_exists_in_table(self):
        terms = {t for t, _ in self.rows}
        for p in CONFIG["patterns"]:
            with self.subTest(row=p["row"]):
                self.assertIn(p["row"], terms)

    def test_every_lint_alias_has_a_pattern(self):
        for term, cell in self.rows:
            for seg in split_top(cell):
                if not re.search(r"\((?:lint)\b", seg):
                    continue
                pats = [p for p in CONFIG["patterns"] if p["row"] == term]
                known = [a.lower() for p in pats for a in p["aliases"]]
                bare = re.sub(r"\([^)]*\)", "", seg)  # drop parenthetical notes
                for piece in bare.split(","):
                    head = piece.split(" as ")[0].strip().strip('"').lower()
                    if not head:
                        continue
                    with self.subTest(term=term, alias=head):
                        self.assertTrue(any(k.startswith(head) or head.startswith(k) for k in known))

    def test_each_alias_in_exactly_one_row(self):
        for p in CONFIG["patterns"]:
            for alias in p["aliases"]:
                with self.subTest(alias=alias):
                    hits = {t for t, cell in self.rows
                            for seg in split_top(cell) if alias.lower() in seg.lower()}
                    self.assertEqual(len(hits), 1, hits)

    def test_real_tree_is_clean(self):
        r = run_lint()
        self.assertEqual(r.returncode, 0, r.stdout)


class CanonShape(unittest.TestCase):
    def row(self, text, term):
        m = re.search(rf"^\| \*\*{re.escape(term)}\*\*[^\n]*$", text, re.M)
        return m.group(0) if m else ""

    def test_orchestrator_row_has_no_dispatch_or_family(self):
        row = self.row(read("CONTEXT.md"), "Orchestrator")
        self.assertTrue(row)
        self.assertNotRegex(row.lower(), r"dispatches|family")

    def test_delegation_model_has_guest_agent(self):
        self.assertGreaterEqual(read("docs/governance/DELEGATION-MODEL.md").count("Guest agent"), 1)

    def test_ceo_only_in_allowed_places(self):
        allowed = re.compile(r"CEO and CoS|chain position|CEO-BRIEF|terms: historical")
        first_cell = re.compile(r"^\|\s*\**(?:CEO|operator)\**\s*\|")
        for rel in ("CONTEXT.md", "docs/governance/DELEGATION-MODEL.md"):
            fence = None
            for n, line in enumerate(read(rel).splitlines(), 1):
                fm = re.match(r"^\s*(`{3,}|~{3,})", line)
                if fm:
                    fence = None if fence == fm.group(1)[0] else fm.group(1)[0]
                    continue
                if fence or "CEO" not in line:
                    continue
                if first_cell.match(line) or allowed.search(line):
                    continue
                self.fail(f"{rel}:{n}: CEO outside allowed places: {line[:100]}")

    def test_rung_row_drops_cost_and_capability_only(self):
        row = self.row(read("CONTEXT.md"), "Rung")
        self.assertTrue(row)
        self.assertNotIn("cost and capability class only", row)

    def test_cos_row_names_dispatch_verify_commit(self):
        text = read("CONTEXT.md")
        m = re.search(r"^\| \*\*Chief of Staff[^\n]*$|^\| \*\*CoS\*\*[^\n]*$", text, re.M)
        self.assertTrue(m, "no CoS row")
        first = re.split(r"(?<=\.)\s", m.group(0).split("|")[-2] if m.group(0).count("|") > 2 else m.group(0))[0].lower()
        for word in ("dispatch", "lead", "verif", "commit"):
            self.assertIn(word, first)

    def test_no_driver_or_tier_row(self):
        self.assertNotRegex(read("CONTEXT.md"), r"(?m)^\| (?:\*\*)?(Driver|Tier)(?:\*\*)? \|")


if __name__ == "__main__":
    unittest.main()
