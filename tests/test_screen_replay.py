"""Spec 042 Phase 5 (FR-025 to FR-029a, SC-006): the fixed replay set runs through the real screens.

Every `false-deny` case is allowed, every `bypass` case is denied, every `regression` case keeps its decision.
The credential screen reads prompt text only; the tool deny list and the OS sandbox are the controls that block
the actual reads, and this file does not test them. Case inputs are text only: no path in them is ever opened.
"""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch, hook, rules
from tests.test_dispatch_snapshot_trust import DispatchBase, ok_launch

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "fixtures/replay/screens.jsonl"
KEYS = {"id", "screen", "input", "expected", "source", "kind"}


def load_cases() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]


def bash(command: str) -> dict:
    return {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": command}}


def decide(case: dict) -> str:
    if case["screen"] == "hook":
        return "deny" if hook.compound_deny(bash(case["input"])) else "allow"
    return "deny" if dispatch.credential_hit(case["input"]) else "allow"


class Fixture(unittest.TestCase):
    def test_every_line_has_the_six_keys(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 25)
        ids = [c["id"] for c in cases]
        self.assertEqual(len(ids), len(set(ids)), "case ids are unique")
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(KEYS <= set(case))
                self.assertIn(case["screen"], ("hook", "credential"))
                self.assertIn(case["expected"], ("allow", "deny"))
                self.assertIn(case["kind"], ("false-deny", "bypass", "regression"))
                if case["kind"] == "regression":
                    self.assertEqual(case.get("current", case["expected"]), case["expected"])
                if case["kind"] == "false-deny":
                    self.assertEqual(case["expected"], "allow")
                if case["kind"] == "bypass":
                    self.assertEqual(case["expected"], "deny")


class Replay(unittest.TestCase):
    def test_each_case_gets_its_expected_decision(self):
        for case in load_cases():
            with self.subTest(case=case["id"], kind=case["kind"]):
                self.assertEqual(decide(case), case["expected"])


class Undecidable(unittest.TestCase):
    """FR-026: a requested path with a shell expansion next to a secret name cannot be decided; refuse and say so."""

    def test_variable_path_refused_as_undecidable(self):
        hit = dispatch.credential_hit({"TASK": "Read $D/auth.json where D is the home .codex directory"})
        self.assertIsNotNone(hit)
        self.assertIn("could not decide", hit)
        self.assertEqual(dispatch.credential_rule_id(hit), "credential-undecidable")

    def test_command_substitution_and_backtick_next_to_secret_name_refused(self):
        for text in ("Read $(echo ~)/.ssh/id_rsa", "Open `pwd`/auth.json", "Show ${BASE}/.env"):
            with self.subTest(text=text):
                self.assertIsNotNone(dispatch.credential_hit({"TASK": text}))

    def test_decided_path_keeps_its_old_rule(self):
        hit = dispatch.credential_hit({"TASK": "Read ~/.codex/auth.json"})
        self.assertEqual(dispatch.credential_rule_id(hit), "credential-slot-text")

    def test_expansion_without_secret_name_is_not_undecidable(self):
        self.assertIsNone(dispatch.credential_hit({"TASK": "Read $D/notes.txt and report"}))

    def test_deny_prose_with_glob_stays_allowed(self):
        self.assertIsNone(dispatch.credential_hit({"TASK": "The deny list covers ~/.claude/** and ~/.ssh/**"}))

    def test_undecidable_in_deny_clause_stays_allowed(self):
        self.assertIsNone(dispatch.credential_hit({"CONSTRAINTS": "Do not read $D/auth.json"}))

    def test_rule_registered_with_three_line_refusal(self):
        self.assertIn("credential-undecidable", rules.RULES)
        text = rules.refuse("credential-undecidable", "slot TASK could not decide '$D/auth.json'")
        self.assertTrue(text.startswith("refused: credential-undecidable ("))
        self.assertEqual(len(text.splitlines()), 3)


class UndecidableCli(DispatchBase):
    def test_dispatch_refuses_with_undecidable_rule(self):
        rc, out, err = self.dispatch(ok_launch(), slots=self.slots(TASK="Read $D/auth.json and report"))
        self.assertEqual(rc, 3, out + err)
        self.assertIn("refused: credential-undecidable", err)
        self.assertIn("could not decide", err)


class Unparsed(unittest.TestCase):
    """FR-028, FR-028a: a form the hook cannot parse, in a call that names the launcher, is denied and says so."""

    def reason(self, command: str) -> str:
        out = hook.compound_deny(bash(command))
        return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out else ""

    def test_each_unparsed_bypass_says_it_could_not_parse(self):
        for case in load_cases():
            if case["screen"] == "hook" and case["kind"] == "bypass":
                with self.subTest(case=case["id"]):
                    reason = self.reason(case["input"])
                    self.assertIn("hook-unparsed", reason)
                    self.assertIn("could not be parsed", reason)

    def test_parser_error_fails_closed_when_launcher_named(self):
        with mock.patch.object(hook, "_dispatch_shape", side_effect=RuntimeError("boom")):
            self.assertIn("hook-unparsed", self.reason("agents-inc dispatch --slots s.json --model terra"))
            self.assertEqual(self.reason("ls -la"), "")

    def test_unterminated_quote_with_launcher_denied(self):
        self.assertIn("hook-unparsed", self.reason('echo "agents-inc dispatch'))

    def test_plain_call_still_allowed(self):
        self.assertEqual(self.reason("agents-inc dispatch --slots s.json --model terra"), "")
        self.assertEqual(self.reason("echo hello"), "")

    def test_ansi_c_word_without_launcher_allowed(self):
        self.assertEqual(self.reason("echo $'a\\tb'"), "")

    def test_comment_mention_allowed(self):
        self.assertEqual(self.reason("source ./helpers.sh # agents-inc dispatch is documented here"), "")

    def test_source_without_comment_still_denied(self):
        self.assertNotEqual(self.reason("source ./helpers.sh; agents-inc dispatch --slots s.json"), "")

    def test_rule_registered(self):
        self.assertIn("hook-unparsed", rules.RULES)


if __name__ == "__main__":
    unittest.main()
