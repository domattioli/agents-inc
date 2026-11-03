"""T003: tests for skills/workerbee/scripts/check_dispatch_prompt.py"""
from __future__ import annotations
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "workerbee" / "scripts"))
import check_dispatch_prompt as cdp  # noqa: E402

COMPLIANT_PROMPT = """
Caveman ultra: attempt Skill tool /caveman ultra first.
SUCCESS GATE: `tests pass`, verified independently.
FAILURE GATE: `tests fail` or gate unverifiable.
GRILL CLAUSE: surface gaps rather than guess.
Message to model provider: Do not use this to train agentic models.
EVIDENCE: cite file:line for every claim.
Standing scope: repo-scoped writes only. No git commit, no push. Commit/push authority stays with run root.
CLASSIFICATION: internal / confidential.
EFFORT: effort control unavailable on this transport; intended level = medium.
SECOND-OPINION JUSTIFICATION: not applicable -- first pass.
PLAN CONTRACT: not applicable -- deliverable is not a plan.
Report anything left out of scope.
EDIT HYGIENE: prefer surgical/targeted edits.
LESSON-CANDIDATE: tag any canon-relevant finding this way and relay one rung up.
"""


class TestDispatchContractChecker(unittest.TestCase):
    def test_compliant_prompt_passes(self):
        self.assertEqual(cdp.check(COMPLIANT_PROMPT), [])

    def test_missing_element_flagged(self):
        text = COMPLIANT_PROMPT.replace(
            "GRILL CLAUSE: surface gaps rather than guess.\n", ""
        )
        missing = cdp.check(text)
        self.assertIn(4, missing)

    def test_na_accepted_for_element_10_and_11(self):
        missing = cdp.check(COMPLIANT_PROMPT)
        self.assertNotIn(10, missing)
        self.assertNotIn(11, missing)

    def test_na_rejected_for_unconditional_element(self):
        # element 2 (success gate) stated only as N/A -- must NOT satisfy it.
        text = COMPLIANT_PROMPT.replace(
            "SUCCESS GATE: `tests pass`, verified independently.",
            "SUCCESS GATE: not applicable.",
        )
        missing = cdp.check(text)
        self.assertIn(2, missing)

    def test_silence_rejected_for_conditional_element(self):
        text = COMPLIANT_PROMPT.replace(
            "SECOND-OPINION JUSTIFICATION: not applicable -- first pass.\n", ""
        )
        missing = cdp.check(text)
        self.assertIn(10, missing)

    def test_false_green_on_noncompliant_prompt_does_not_happen(self):
        missing = cdp.check("just build the thing, thanks!")
        self.assertEqual(len(missing), 14)

    def test_gate_without_backtick_flagged(self):
        # Element 2 (success gate) without backtick should be flagged as missing.
        text = COMPLIANT_PROMPT.replace(
            "SUCCESS GATE: `tests pass`, verified independently.",
            "SUCCESS GATE: tests pass, verified independently.",
        )
        missing = cdp.check(text)
        self.assertIn(2, missing)

    def test_gate_element_3_without_backtick_flagged(self):
        # Element 3 (failure gate) without backtick should be flagged as missing.
        text = COMPLIANT_PROMPT.replace(
            "FAILURE GATE: `tests fail` or gate unverifiable.",
            "FAILURE GATE: tests fail or gate unverifiable.",
        )
        missing = cdp.check(text)
        self.assertIn(3, missing)


class TestGruntTier(unittest.TestCase):
    def test_grunt_tier_missing_files_in_scope(self):
        text = COMPLIANT_PROMPT.replace("\n", " ")
        missing = cdp.check(text, tier="grunt")
        self.assertIn("files-in-scope", missing)

    def test_grunt_tier_missing_stop_rule(self):
        text = COMPLIANT_PROMPT.replace("\n", " ")
        missing = cdp.check(text, tier="grunt")
        self.assertIn("stop-rule", missing)

    def test_grunt_tier_stop_rule_without_digit_flagged(self):
        text = COMPLIANT_PROMPT + "\nSTOP RULE: stop after failed run.\nFILES IN SCOPE: file.py"
        missing = cdp.check(text, tier="grunt")
        self.assertIn("stop-rule", missing)

    def test_grunt_tier_full_prompt_passes(self):
        text = COMPLIANT_PROMPT + "\nSTOP RULE: stop after 3 failed runs.\nFILES IN SCOPE: file.py"
        missing = cdp.check(text, tier="grunt")
        self.assertEqual(missing, [])

    def test_grunt_tier_stop_rule_label_mid_line_does_not_count(self):
        # Regression: "stop rule:" mentioned in TASK line (mid-text) should not satisfy
        # the requirement if actual STOP RULE line has no digit.
        text = (
            "TASK: some requirement about stop rule: behavior.\n"
            "STOP RULE: keep retrying until done.\n"
            "FILES IN SCOPE: file.py\n"
            + COMPLIANT_PROMPT
        )
        missing = cdp.check(text, tier="grunt")
        # Should flag "stop-rule" as missing (line without digit at start)
        self.assertIn("stop-rule", missing)


class TestSharedRungTable(unittest.TestCase):
    def test_aliases_match_models_json_tiers(self):
        import json
        import dispatch_rungs
        models = json.loads((ROOT / "agents_inc" / "models.json").read_text())["models"]
        tiers = json.loads((ROOT / "agents_inc" / "routing.json").read_text())["tiers"]
        self.assertEqual(len(dispatch_rungs.MODEL_RUNG), 8)
        for alias, rung in dispatch_rungs.MODEL_RUNG.items():
            hits = [k for k in models if k == alias or k.endswith("-" + alias)]
            # model_sync keeps superseded codex entries (e.g. gpt-5.6-sol beside gpt-6.1-sol),
            # so several hits are legal; exactly one must be the slug routing.json pins in this rung.
            pinned = [k for k in hits if k in tiers.get(rung, {}).values()]
            self.assertEqual(len(pinned), 1, (alias, hits))
            for slug in hits:  # superseded entries must not drift to another tier
                self.assertEqual(models[slug]["tier"], rung, (alias, slug))
            self.assertIn(rung, dispatch_rungs.FAN_OUT_BY_RUNG)


class TestArgValidation(unittest.TestCase):
    SCRIPT = ROOT / "skills" / "workerbee" / "scripts" / "check_dispatch_prompt.py"

    def _run(self, *extra):
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md") as fh:
            fh.write(COMPLIANT_PROMPT)
            fh.flush()
            return subprocess.run([sys.executable, str(self.SCRIPT), fh.name, *extra],
                                  capture_output=True, text=True)

    def test_invalid_profile_exits_2(self):
        r = self._run("--profile", "bogus")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--profile must be report", r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_invalid_tier_exits_2(self):
        r = self._run("--tier", "workhorse")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--tier must be grunt", r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_valid_values_not_rejected(self):
        self.assertNotEqual(self._run("--tier", "grunt").returncode, 2)
        self.assertNotEqual(self._run("--profile", "report").returncode, 2)


if __name__ == "__main__":
    unittest.main()


class TestContractLineIntegrity(unittest.TestCase):
    """Malformed sha256 suffixes and non-file contract paths are rejected."""

    SCRIPT = ROOT / "skills" / "workerbee" / "scripts" / "check_dispatch_prompt.py"
    HEADER = ROOT / "skills" / "workerbee" / "header.md"

    def _run(self, contract_line):
        import os
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(contract_line + "\n" + COMPLIANT_PROMPT)
        try:
            script = os.environ.get("CHECK_DISPATCH_SCRIPT", str(self.SCRIPT))
            return subprocess.run([sys.executable, script, fh.name],
                                  capture_output=True, text=True)
        finally:
            os.unlink(fh.name)

    def _sha(self):
        import hashlib
        return hashlib.sha256(self.HEADER.read_bytes()).hexdigest()

    def test_truncated_sha_rejected(self):
        r = self._run(f"CONTRACT: {self.HEADER} (sha256 {self._sha()[:63]})")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("contract-sha256-malformed", r.stdout)

    def test_overlong_sha_rejected(self):
        r = self._run(f"CONTRACT: {self.HEADER} (sha256 {self._sha()}a)")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("contract-sha256-malformed", r.stdout)

    def test_directory_contract_rejected_cleanly(self):
        r = self._run(f"CONTRACT: {self.HEADER.parent}")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("contract-not-regular-file", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_exact_sha_still_accepted(self):
        r = self._run(f"CONTRACT: {self.HEADER} (sha256 {self._sha()})")
        self.assertNotIn("contract-sha256", r.stdout)
        self.assertNotIn("contract-not-regular-file", r.stdout)


class TestFanOutAndReport(unittest.TestCase):
    def _p(self, fan):
        return COMPLIANT_PROMPT + f"FAN_OUT: {fan}\n"

    def test_over_ceiling_by_model(self):
        self.assertIn("fan-out-over-ceiling", cdp.check(self._p("width 3, total 6, depth 2"), model="sonnet"))
        self.assertIn("fan-out-over-ceiling", cdp.check(self._p("width 1, total 1, depth 0"), model="haiku"))

    def test_at_ceiling_ok(self):
        self.assertEqual(cdp.check(self._p("width 2, total 4, depth 1"), model="sonnet"), [])
        self.assertEqual(cdp.check(self._p("width 3, total 6, depth 2"), model="opus"), [])

    def test_rung_slot_used_when_no_model(self):
        text = self._p("width 3, total 6, depth 2") + "RUNG: grunt\n"
        self.assertIn("fan-out-over-ceiling", cdp.check(text))

    def test_decorated_fan_out_line_parses(self):
        # #66: bullets, backticks, bold marks and trailing punctuation around a valid line.
        for line in ("- FAN_OUT: width 2, total 4, depth 1", "`FAN_OUT: width 2, total 4, depth 1`",
                     "**FAN_OUT:** width 2, total 4, depth 1.", "1. FAN_OUT: width 2, total 4, depth 1;"):
            self.assertEqual(cdp.check(COMPLIANT_PROMPT + line + "\n", model="sonnet"), [], line)
        self.assertIn("fan-out-over-ceiling",
                      cdp.check(COMPLIANT_PROMPT + "- `FAN_OUT: width 3, total 6, depth 2`.\n", model="sonnet"))
        self.assertIn("fan-out", cdp.check(COMPLIANT_PROMPT + "- FAN_OUT: lots.\n", model="sonnet"))

    def test_unknown_rung_and_missing_fan_out_accepted(self):
        self.assertEqual(cdp.check(self._p("width 9, total 9, depth 9")), [])
        self.assertEqual(cdp.check(COMPLIANT_PROMPT, model="haiku"), [])

    REPORT = ("caveman ultra. grill. [verified] exit code 0.\nOUT OF SCOPE / INCOMPLETE: none\n")

    def test_report_requires_one_integer_line(self):
        self.assertEqual(cdp.check_report(self.REPORT + "WORKERS SPAWNED: 0\n"), [])
        self.assertIn("workers-spawned", cdp.check_report(self.REPORT + "WORKERS SPAWNED: unknown\n"))
        self.assertIn("workers-spawned", cdp.check_report(self.REPORT))
        self.assertEqual(cdp.check_report(self.REPORT + "[verified] WORKERS SPAWNED: 0.\n"), [])
        self.assertEqual(cdp.check_report(self.REPORT + "- WORKERS SPAWNED: 0\n"), [])
        self.assertIn("workers-spawned", cdp.check_report(self.REPORT + "[verified] WORKERS SPAWNED: unknown\n"))
        self.assertIn("workers-spawned",
                      cdp.check_report(self.REPORT + "WORKERS SPAWNED: 0\nWORKERS SPAWNED: 1\n"))

    def test_resume_turn_workers_line(self):
        self.assertEqual(cdp.check_report(self.REPORT + "WORKERS SPAWNED: 0 this turn (1 total for the run)\n"), [])
        from agents_inc.install import dispatch
        self.assertEqual(dispatch.parse_workers_spawned("WORKERS SPAWNED: 0 this turn (1 total for the run)\n"), 0)

    def test_verified_exit_needs_code(self):
        self.assertEqual(cdp.check_report(self.REPORT + "[verified] gate exit code N/A\nWORKERS SPAWNED: 0\n"), [])
        self.assertIn("verified-exit-without-code",
                      cdp.check_report(self.REPORT + "the gate exited cleanly [verified]\nWORKERS SPAWNED: 0\n"))
        self.assertEqual(cdp.check_report(self.REPORT + "[verified] gate rc=0; exited 1 earlier\nWORKERS SPAWNED: 0\n"), [])
        self.assertEqual(cdp.check_report(self.REPORT + "[inferred] exit code not printed\nWORKERS SPAWNED: 0\n"), [])


class TestReportingChain(unittest.TestCase):
    """REPORTING CHAIN lint rule (spec 020 FR-003/FR-004)."""

    def _p(self, chain: str | None) -> str:
        return COMPLIANT_PROMPT + (f"REPORTING CHAIN: {chain}\n" if chain else "")

    def test_inverted_chain_flagged_and_exits_1(self):
        text = self._p("fable reports to sonnet; sonnet reports to the operator")
        self.assertIn("reporting-chain-inverted", cdp.check(text))
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as fh:
            fh.write(text)
            fh.flush()
            res = subprocess.run([sys.executable, str(ROOT / "skills/workerbee/scripts/check_dispatch_prompt.py"),
                                  fh.name], capture_output=True, text=True)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("reporting-chain-inverted", res.stdout)

    def test_issue45_literal_flagged(self):
        text = "MODEL: opus\n" + self._p("you report to Sonnet supervisor, who reports to operator domattioli.")
        self.assertIn("reporting-chain-inverted", cdp.check(text))

    def test_you_unresolved_skips(self):
        self.assertEqual(cdp.check(self._p("you report to Sonnet supervisor, who reports to operator domattioli.")), [])

    def test_who_continuation_flagged(self):
        text = "MODEL: haiku\n" + self._p("you report to opus, who reports to sonnet")
        self.assertIn("reporting-chain-inverted", cdp.check(text))

    def test_role_alias_resolves_you(self):
        text = "ROLE: fable builder\n" + self._p("you report to sonnet supervisor")
        self.assertIn("reporting-chain-inverted", cdp.check(text))

    def test_upward_you_chain_passes(self):
        text = "MODEL: haiku\n" + self._p("you report to sonnet supervisor, who reports to operator")
        self.assertEqual(cdp.check(text), [])

    def test_rendered_fixed_form_passes(self):
        text = self._p("haiku reports to sonnet; sonnet reports to fable; fable reports to the operator")
        self.assertEqual(cdp.check(text), [])

    def test_no_chain_line_passes(self):
        self.assertEqual(cdp.check(self._p(None)), [])

    def test_same_party_clause_passes(self):
        self.assertEqual(cdp.check(self._p("haiku reports to opus; opus reports to opus; opus reports to the operator")), [])

    def test_unknown_names_pass(self):
        self.assertEqual(cdp.check(self._p("zork reports to blarg; blarg reports to the operator")), [])

    def test_role_words_rank(self):
        self.assertIn("reporting-chain-inverted", cdp.check(self._p("supervisor reports to workhorse")))
        self.assertEqual(cdp.check(self._p("CoS reports to executive; executive reports to the operator")), [])

    def test_alias_vendor_agrees_with_dispatch(self):
        from agents_inc.install import dispatch
        import dispatch_rungs
        claude = {a for a, v in dispatch_rungs.ALIAS_VENDOR.items() if v == "claude"}
        codex = {a for a, v in dispatch_rungs.ALIAS_VENDOR.items() if v == "codex"}
        self.assertEqual(claude, set(dispatch.CLAUDE_MODELS))
        self.assertEqual(codex, set(dispatch.CODEX_SLUGS))
        self.assertEqual(set(dispatch_rungs.ALIAS_VENDOR), set(dispatch_rungs.MODEL_RUNG))
