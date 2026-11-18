"""Spec 016 FR-007, SC-003 (#36): SKILL.md tier tables match models.json and routing.json.

Supervisor-owned acceptance tests. Fixture edits happen on temp copies only.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "workerbee" / "SKILL.md"
GEN = ROOT / "skills" / "workerbee" / "scripts" / "gen_tier_tables.py"
MODELS = ROOT / "agents_inc" / "models.json"
ROUTING = ROOT / "agents_inc" / "routing.json"
BEGIN = "<!-- BEGIN GENERATED tier-table (skills/workerbee/scripts/gen_tier_tables.py --write); do not edit by hand -->"
END = "<!-- END GENERATED tier-table -->"
RUNGS = {"executive", "orchestrator", "workhorse", "grunt"}


def first_table_after(text, heading):
    tail = text.split(heading, 1)[1]
    rows, started = [], False
    for line in tail.splitlines():
        if line.startswith("|"):
            started = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                rows.append(cells)
        elif started:
            break
    return rows[0], rows[1:]


def models():
    return json.loads(MODELS.read_text())["models"]


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.skill = self.dir / "SKILL.md"
        self.models = self.dir / "models.json"
        self.routing = self.dir / "routing.json"
        shutil.copy(SKILL, self.skill)
        shutil.copy(MODELS, self.models)
        shutil.copy(ROUTING, self.routing)

    def tearDown(self):
        self.tmp.cleanup()

    def gen(self, *mode):
        return subprocess.run([sys.executable, str(GEN), *mode, "--skill", str(self.skill),
                               "--models", str(self.models), "--routing", str(self.routing)],
                              capture_output=True, text=True, timeout=60)

    def edit_models(self, model_id, tier):
        data = json.loads(self.models.read_text())
        data["models"][model_id]["tier"] = tier
        self.models.write_text(json.dumps(data, indent=2))


class GeneratedBlockTest(_Tmp):
    def test_repo_skill_block_is_current(self):
        proc = subprocess.run([sys.executable, str(GEN), "--check"], capture_output=True, text=True,
                              timeout=60, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("tier-table: current", proc.stdout)

    def test_block_lists_every_models_json_id(self):
        text = SKILL.read_text()
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        block = text.split(BEGIN, 1)[1].split(END, 1)[0]
        ids = list(models())
        self.assertTrue(ids)
        # Both directions, no hardcoded count: no stale id in the block, no models.json id missing from it.
        self.assertEqual(set(re.findall(r"`([^`]+)`", block)), set(ids))
        for model_id in ids:
            self.assertIn(f"`{model_id}`", block, model_id)

    def test_block_sits_inside_step_1(self):
        text = SKILL.read_text()
        step1 = text.split("### Step 1: Place the task on the capability ladder", 1)[1].split("#### Step 1a", 1)[0]
        self.assertIn(BEGIN, step1)

    def test_changed_fixture_tier_makes_check_fail_naming_id(self):
        self.assertEqual(self.gen("--check").returncode, 0)
        self.edit_models("gpt-5.4-mini", "workhorse")
        proc = self.gen("--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("gpt-5.4-mini", proc.stdout + proc.stderr)

    def test_write_then_check_is_current(self):
        self.edit_models("gpt-5.4-mini", "workhorse")
        self.assertEqual(self.gen("--write").returncode, 0)
        proc = self.gen("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        before, after = SKILL.read_text().split(BEGIN)[0], self.skill.read_text().split(BEGIN)[0]
        self.assertEqual(before, after)  # text outside the block untouched

    def test_missing_markers_fail_check(self):
        self.skill.write_text(SKILL.read_text().replace(BEGIN, "").replace(END, ""))
        self.assertEqual(self.gen("--check").returncode, 1)

    def test_off_vocabulary_tier_fails_closed(self):
        self.edit_models("gemini-2.5-flash", "flash")
        for mode in ("--check", "--write"):
            proc = self.gen(mode)
            self.assertEqual(proc.returncode, 1, mode)
            self.assertIn("gemini-2.5-flash", proc.stdout + proc.stderr)
        self.assertEqual(self.skill.read_text(), SKILL.read_text())

    def test_routing_default_tier_mismatch_fails_closed(self):
        self.edit_models("sonnet", "grunt")  # routing.json says sonnet is the claude workhorse default
        proc = self.gen("--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("sonnet", proc.stdout + proc.stderr)

    def test_routing_default_absent_from_models_fails_closed(self):
        data = json.loads(self.routing.read_text())
        data["tiers"]["grunt"]["claude"] = "haiku-ghost"
        self.routing.write_text(json.dumps(data))
        proc = self.gen("--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("haiku-ghost", proc.stdout + proc.stderr)


class HandTableTest(unittest.TestCase):
    def test_ladder_tier_cells_are_rung_names(self):
        header, rows = first_table_after(SKILL.read_text(), "### Step 1: Place the task on the capability ladder")
        self.assertEqual(header[0], "tier")
        for row in rows:
            self.assertIn(row[0], RUNGS | {"—"}, row)

    # The hand-written MODEL ROSTER was removed on this branch; the generated table is the only per-id rung source.
    def test_no_hand_roster_table_can_drift(self):
        text = SKILL.read_text()
        self.assertNotIn("MODEL ROSTER", text)
        outside = text.split(BEGIN, 1)[0] + text.split(END, 1)[1]
        cfg = models()
        for line in outside.splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
            self.assertFalse(any(c in cfg and "-" in c for c in cells), line)  # no hand row names a config model id

    def test_generated_table_covers_every_config_rung(self):
        text = SKILL.read_text()
        block = text.split(BEGIN, 1)[1].split(END, 1)[0]
        for model_id, spec in models().items():
            self.assertRegex(block, rf"\| {spec['tier']} \|[^\n]*`{re.escape(model_id)}`", model_id)


if __name__ == "__main__":
    unittest.main()
