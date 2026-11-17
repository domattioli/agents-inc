"""Spec 042 US4 (FR-022): a refusal names the rule, the value and one fix. One bad input per rule; temp dirs, no launch."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch, hook, rules
from agents_inc.install.paths import InstallPaths
from tests.test_dispatch_snapshot_trust import DispatchBase, ok_launch

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/workerbee/scripts"
EXAMPLE = REPO / "skills/workerbee/tests/fixtures/example_slots.json"

_ALLOW = mock.patch.dict(os.environ, {dispatch.ALLOW_SANDBOXED_ENV: "1"})


def setUpModule():
    _ALLOW.start()


def tearDownModule():
    _ALLOW.stop()


class Shape(unittest.TestCase):
    def assert_refusal(self, text, rule_id, value=None, fix_has=None):
        self.assertIn(f"refused: {rule_id} (", text)
        self.assertIn(rules.RULES[rule_id]["summary"], text)
        self.assertRegex(text, r"(?m)^value: \S")
        self.assertRegex(text, r"(?m)^fix: \S")
        self.assertNotRegex(text, r"(?m)^Rule \d+:")  # never a number alone
        if value is not None:
            self.assertIn(value, text)
        if fix_has:
            self.assertIn(fix_has, text)

    def assert_reason(self, reason, rule_id, value):
        """A hook reason: the same three parts joined by spaces."""
        self.assertIn(f"refused: {rule_id} (", reason)
        self.assertIn(f" value: {value}", reason)
        self.assertRegex(reason, r" fix: \S")


class RegistryHelper(Shape):
    def test_refuse_three_lines_and_screens_value(self):
        text = rules.refuse("scope-glob", "x" * 500 + " api_key=abcdef123456")
        lines = text.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("refused: scope-glob ("))
        self.assertLessEqual(len(lines[1][len("value: "):].encode()), 203)
        self.assertNotIn("abcdef123456", rules.refuse("scope-glob", "api_key=abcdef123456"))

    def test_every_rule_has_screen_summary_fix(self):
        for rid, rule in rules.RULES.items():
            with self.subTest(rule=rid):
                self.assertRegex(rid, r"^[a-z0-9]+(-[a-z0-9]+)*$")
                self.assertTrue(rule["summary"].strip() and rule["example_fix"].strip())
                self.assertIn(rule["screen"], {"render", "lint", "scope", "grants", "credential", "capability", "non-git", "broker", "hook", "install"})
                self.assertNotIn("\n", rule["summary"] + rule["example_fix"])


class LintMessages(Shape):
    def _lint(self, text, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.md"
            path.write_text(text)
            return subprocess.run([sys.executable, str(SCRIPTS / "check_dispatch_prompt.py"), str(path), *extra],
                                  capture_output=True, text=True)

    def _good(self):
        return subprocess.run([sys.executable, str(SCRIPTS / "render_dispatch.py"), "--slots", str(EXAMPLE)],
                              capture_output=True, text=True, cwd=REPO).stdout

    def test_failure_gate_without_backtick(self):
        text = "\n".join(ln.replace("`", "") if ln.startswith("FAILURE GATE") else ln for ln in self._good().splitlines())
        res = self._lint(text)
        self.assertEqual(res.returncode, 1)
        self.assertIn("NON-COMPLIANT missing elements: [3 failure-gate]", res.stdout)  # D41: names stay on stdout
        self.assert_refusal(res.stderr, "lint-element-failure-gate", "FAILURE GATE", "`test -f out.txt`")

    def test_every_missing_element_gets_value_and_fix(self):
        res = self._lint("hello\n")
        for rid in (f"lint-element-{n}" for n in rules.LINT_NAMES.values()):
            with self.subTest(rule=rid):
                self.assertIn(f"refused: {rid} (", res.stderr)
        self.assertEqual(res.stderr.count("value: "), 14)
        self.assertEqual(res.stderr.count("fix: "), 14)

    def test_grunt_tier_files_in_scope_and_stop_rule(self):
        res = self._lint(self._good().replace("FILES IN SCOPE:", "FILES:").replace("STOP RULE:", "STOP:"), "--tier", "grunt")
        self.assert_refusal(res.stderr, "lint-files-in-scope", fix_has="FILES IN SCOPE: path/a.py")
        self.assert_refusal(res.stderr, "lint-stop-rule", fix_has="STOP RULE: stop after 20 tool calls")

    def test_fan_out_and_contract_and_bare(self):
        res = self._lint(self._good().replace("FAN_OUT: width 0, total 0, depth 0", "FAN_OUT: lots"))
        self.assert_refusal(res.stderr, "lint-fan-out", "FAN_OUT: lots", "FAN_OUT: width 0, total 0, depth 0")
        res = self._lint(self._good() + "\nCONTRACT: nope/missing.md\n")
        self.assert_refusal(res.stderr, "lint-contract-unreadable", "nope/missing.md")
        res = self._lint(self._good() + "\nCONTRACT: x.md\n", "--transport", "bare")
        self.assert_refusal(res.stderr, "lint-contract-bare-transport")

    def test_report_profile(self):
        res = self._lint("short report\n", "--profile", "report")
        self.assert_refusal(res.stderr, "lint-report-element", "caveman")

    def test_chain_inverted(self):
        res = self._lint(self._good().replace("REPORTING CHAIN: haiku reports to sonnet", "REPORTING CHAIN: sonnet reports to haiku"))
        if res.returncode:
            self.assert_refusal(res.stderr, "lint-reporting-chain-inverted")


class RenderMessages(Shape):
    def _render(self, **extra):
        data = json.loads(EXAMPLE.read_text())
        data.update(extra)
        data = {k: v for k, v in data.items() if v is not None}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps(data))
            return subprocess.run([sys.executable, str(SCRIPTS / "render_dispatch.py"), "--slots", str(path)],
                                  capture_output=True, text=True, cwd=REPO)

    def test_missing_slot(self):
        res = self._render(TASK=None)
        self.assertEqual(res.returncode, 2)
        self.assertIn("Required slot missing or empty: TASK", res.stderr)
        self.assert_refusal(res.stderr, "slot-missing", "TASK", "agents-inc dispatch --print-template")

    def test_schema_classification_and_list_type(self):
        res = self._render(CLASSIFICATION="secret")
        self.assert_refusal(res.stderr, "schema-invalid", "CLASSIFICATION", "CLASSIFICATION: internal")
        self.assertIn("CLASSIFICATION must start with one of public, internal, confidential", res.stderr)
        res = self._render(FILES_IN_SCOPE=5)
        self.assert_refusal(res.stderr, "schema-invalid", "FILES_IN_SCOPE")

    def test_gates_and_bash_allow(self):
        res = self._render(GATES=[{"argv": ["git", "commit"]}])
        self.assertIn("GATES invalid:", res.stderr)
        self.assert_refusal(res.stderr, "gate-danger", "commit")
        res = self._render(GATES=[{"argv": "pytest"}])
        self.assert_refusal(res.stderr, "gates-invalid", "pytest")
        res = self._render(GATES="oops")
        self.assert_refusal(res.stderr, "gates-not-json-list", "oops")
        res = self._render(BASH_ALLOW=["sudo ls"])
        self.assertIn("BASH_ALLOW invalid:", res.stderr)
        self.assert_refusal(res.stderr, "bash-allow-invalid", "sudo")

    def test_placeholder_and_control_char(self):
        res = self._render(TASK="a {{NOPE}} b")
        self.assert_refusal(res.stderr, "placeholder-unfilled", "{{NOPE}}")
        res = self._render(TASK="bad \x07 char")
        self.assert_refusal(res.stderr, "control-char", "U+0007")

    def test_slots_file_unreadable(self):
        res = subprocess.run([sys.executable, str(SCRIPTS / "render_dispatch.py"), "--slots", "/nonexistent/s.json"],
                             capture_output=True, text=True)
        self.assert_refusal(res.stderr, "slots-unreadable", "/nonexistent/s.json", "agents-inc dispatch --print-template")


class DispatchMessages(DispatchBase, Shape):
    def _refused(self, rule_id, want_rc=3, value=None, fix_has=None, **extra):
        rc, out, err = self.dispatch(ok_launch(), slots=self.slots(**extra))
        self.assertEqual(rc, want_rc, out + err)
        self.assert_refusal(err, rule_id, value, fix_has)
        return out, err

    def test_scope_glob(self):
        out, _ = self._refused("scope-glob", value="src/*.py", fix_has="exact paths", FILES_IN_SCOPE="src/*.py")
        self.assertIn("refused-scope", out)  # status line and reason codes keep their names

    def test_gates_rules(self):
        self._refused("gates-not-json-list", value="GATES", GATES="x")
        self._refused("gate-credential-path", value=".env", GATES=[{"argv": ["cat", ".env"]}])
        self._refused("gate-cwd-outside", value="cwd must be a relative path", GATES=[{"argv": ["python3", "-c", "pass"], "cwd": "../.."}])

    def test_bash_allow_rules(self):
        self._refused("bash-allow-invalid", value="sudo", BASH_ALLOW=["sudo ls"])
        self._refused("bash-allow-credential", value="server.pem", BASH_ALLOW=["python3 tools/x.py server.pem"])

    def test_capability_missing(self):
        self._refused("capability-missing", value="no-such-tool-xyz", GATES=[{"argv": ["no-such-tool-xyz"]}])

    def test_credential_slot_text_and_control_char(self):
        _, err = self._refused("credential-slot-text", value="TASK", TASK="read ~/.ssh/id_rsa and report")
        self.assertIn("refused credential-seeking", err)
        self._refused("control-char", value="U+0007", TASK="ok\x07")

    def test_free_run_precheck_exit_two(self):
        rc, out, err = self.main("--slots", str(self.slots()), "--model", "sonnet", "--effort", "bogus")
        self.assertEqual(rc, 2)

    def test_render_refusal_forwards_rule(self):
        rc, out, err = self.dispatch(ok_launch(), slots=self.slots(TASK=""))
        self.assertIn(rc, (2, 3))
        self.assertTrue("refused: slot-missing (" in err or "refused: render-refused (" in err, err)
        self.assertRegex(err, r"(?m)^fix: \S")


class BrokerMessages(Shape):
    def test_refusal_text_for_each_reason_code(self):
        for reason in ("broker-owned-slot", "bad-slots", "worker-cannot-lead", "no-sandbox-backend", "fan-out-zero",
                       "fan-out-total-exhausted", "oversize", "tier-model-mismatch", "unknown-reason-xyz"):
            with self.subTest(reason=reason):
                rid = rules.broker_rule_id(reason)
                self.assertIn(rid, rules.RULES)
                self.assert_refusal(rules.refuse(rid, reason), rid, reason)
        self.assertEqual(rules.broker_rule_id("unknown-reason-xyz"), "broker-refused")

    def test_broker_reply_keeps_fields_and_adds_refusal_text(self):
        from agents_inc.install import mcp_broker
        data = mcp_broker.with_refusal({"status": "refused", "reason": "bad-slots", "request_id": "r1"}, "bad-slots")
        self.assertEqual((data["status"], data["reason"], data["request_id"]), ("refused", "bad-slots", "r1"))
        self.assert_refusal(data["refusal"], "broker-bad-slots", "bad-slots")


class HookMessages(Shape):
    def test_compound_reason_has_three_parts_and_old_text(self):
        data = json.loads(hook.compound_deny({"tool_name": "Bash", "tool_input": {"command": "agents-inc dispatch s.json && ls"}}))
        reason = data["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertTrue(reason.startswith("agents-inc must be the whole Bash call."))
        self.assert_reason(reason, "hook-compound", "&&")
        self.assertIn("agents-inc dispatch --slots <file> --model <alias>", reason)

    def test_persona_reason(self):
        data = json.loads(hook.persona_deny({"tool_name": "Agent", "tool_input": {"description": "terra: implement X", "subagent_type": "general-purpose"}}))
        reason = data["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertTrue(reason.startswith("FR-002:"))
        self.assert_reason(reason, "hook-persona", "terra: implement X")

    def test_agent_gate_reason(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {hook.AGENT_GATE_ENV: "enforce"}):
            paths = InstallPaths.for_home(Path(tmp))
            data = json.loads(hook.gate_deny(paths, {"tool_name": "Agent", "tool_input": {"description": "x", "subagent_type": "general-purpose"}}))
        reason = data["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("agents-inc agent gate", reason)
        self.assert_reason(reason, "hook-agent-gate", "general-purpose")


if __name__ == "__main__":
    unittest.main()
