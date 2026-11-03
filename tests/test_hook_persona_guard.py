"""Spec 015 (#17, #13): persona-prefix deny and cross-session duplicate warning in the owned hook.

Supervisor-owned acceptance tests. Fixture payloads and a fake home only.
"""
import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import hook, host_wiring
from agents_inc.install.paths import InstallPaths

REASON = ("FR-002: Agent/Task descriptions cannot begin with a Codex persona name. For Codex execution, "
          "dispatch through agents-inc; Agent/Task creates Claude subagents. If this names a product, "
          "repository, person, or supervised worker, put the actual Claude rung first and mention that "
          "name later. Renaming does not change the execution model.")
DENY = ["terra: implement X", "Luna - triage logs", "sol reviews spec", "ASTRA: review hook", "sol/review"]
ALLOW = ["Solve flaky test", "Terraform plan review", "Sol-gel fit", "Lunation calculation",
         "Haiku reviews luna doc", "terra-pair review"]
COLLISIONS = ["Astra DB migration", "Luna repo cleanup"]


def payload(description, tool="Agent", session="s1", prompt="do the thing", background=False, tool_use_id="t1"):
    return {"session_id": session, "tool_name": tool, "tool_use_id": tool_use_id,
            "tool_input": {"description": description, "prompt": prompt, "run_in_background": background}}


class _Home(unittest.TestCase):
    def setUp(self):
        gate = mock.patch.dict(os.environ, {"AGENTS_INC_AGENT_GATE": "advisory"}); gate.start(); self.addCleanup(gate.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = InstallPaths.for_home(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, event, data):
        out, err = io.StringIO(), io.StringIO()
        raw = data if isinstance(data, str) else json.dumps(data)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = hook.run(self.paths, event, None, io.StringIO(raw))
        self.assertEqual(rc, 0)
        text = out.getvalue().strip()
        return (json.loads(text) if text else None), err.getvalue()

    @staticmethod
    def decision(result):
        return ((result or {}).get("hookSpecificOutput") or {}).get("permissionDecision")

    @staticmethod
    def context(result):
        return ((result or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""


class PersonaDenyTest(_Home):
    # FR-002, SC-001
    def test_deny_fixtures_are_denied_with_verbatim_reason_and_reference_shape(self):
        for i, desc in enumerate(DENY + COLLISIONS):
            with self.subTest(desc=desc):
                result, _ = self.run_hook("agent-nudge", payload(desc, session=f"d{i}"))
                self.assertEqual(result, {"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "deny",
                    "permissionDecisionReason": REASON}})

    def test_allow_fixtures_are_not_denied(self):
        for i, desc in enumerate(ALLOW):
            with self.subTest(desc=desc):
                result, _ = self.run_hook("agent-nudge", payload(desc, session=f"a{i}"))
                self.assertNotEqual(self.decision(result), "deny")

    def test_the_native_luna_type_may_name_luna(self):
        data = payload("luna: count lines")
        data["tool_input"]["subagent_type"] = "agents-inc:luna"
        result, _ = self.run_hook("agent-nudge", data)
        self.assertNotEqual(self.decision(result), "deny")

    def test_spike_and_lookalike_types_get_the_persona_check(self):
        for subagent in ("luna-brain:luna", "x-agents-inc:luna"):
            with self.subTest(subagent=subagent):
                data = payload("luna: count lines")
                data["tool_input"]["subagent_type"] = subagent
                result, _ = self.run_hook("agent-nudge", data)
                self.assertEqual(self.decision(result), "deny")

    def test_other_agent_types_still_denied(self):
        data = payload("luna: count lines")
        data["tool_input"]["subagent_type"] = "general-purpose"
        result, _ = self.run_hook("agent-nudge", data)
        self.assertEqual(self.decision(result), "deny")

    def test_task_tool_is_covered(self):
        result, _ = self.run_hook("agent-nudge", payload("Terra review", tool="Task"))
        self.assertEqual(self.decision(result), "deny")

    def test_other_tools_are_not_denied(self):
        result, _ = self.run_hook("agent-nudge", payload("terra review", tool="DelegateAgent"))
        self.assertNotEqual(self.decision(result), "deny")

    # FR-007: malformed input fails open
    def test_malformed_payloads_fail_open(self):
        for raw in ("not json", "[]", json.dumps({"tool_name": "Agent", "tool_input": {"description": 5}}),
                    json.dumps({"tool_name": "Agent", "tool_input": "x"})):
            with self.subTest(raw=raw):
                result, _ = self.run_hook("agent-nudge", raw)
                self.assertNotEqual(self.decision(result), "deny")


class DuplicateWarningTest(_Home):
    # FR-006, SC-003
    def test_cross_session_duplicate_warns_and_names_other_session(self):
        self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S1"))
        result, _ = self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S2"))
        self.assertNotEqual(self.decision(result), "deny")
        self.assertIn("duplicate", self.context(result).lower())
        self.assertIn("S1", self.context(result))

    def test_same_session_repeat_does_not_warn(self):
        self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S1"))
        result, _ = self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S1"))
        self.assertNotIn("duplicate", self.context(result).lower())

    def test_different_prompt_is_a_different_task(self):
        self.run_hook("agent-nudge", payload("Workhorse fan-out", session="S1", prompt="part 1"))
        result, _ = self.run_hook("agent-nudge", payload("Workhorse fan-out", session="S2", prompt="part 2"))
        self.assertNotIn("duplicate", self.context(result).lower())

    def test_fan_out_override_suppresses_warning(self):
        p = "agents-inc: fan-out\nrun shard"
        self.run_hook("agent-nudge", payload("Grunt shard", session="S1", prompt=p))
        result, _ = self.run_hook("agent-nudge", payload("Grunt shard", session="S2", prompt=p))
        self.assertNotIn("duplicate", self.context(result).lower())

    def test_expired_entry_is_ignored_and_replaced(self):
        self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S1"))
        entries = list((self.paths.state / "inflight").glob("*.json"))
        self.assertEqual(len(entries), 1)
        data = json.loads(entries[0].read_text())
        data["expires"] = time.time() - 1
        entries[0].write_text(json.dumps(data))
        result, _ = self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S2"))
        self.assertNotIn("duplicate", self.context(result).lower())
        self.assertEqual(json.loads(entries[0].read_text())["session_id"], "S2")

    def test_foreground_completion_releases_entry(self):
        self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S1"))
        self.run_hook("agent-done", payload("Workhorse fix parser", session="S1"))
        result, _ = self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S2"))
        self.assertNotIn("duplicate", self.context(result).lower())

    def test_background_launch_does_not_release_entry(self):
        self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S1", background=True))
        self.run_hook("agent-done", payload("Workhorse fix parser", session="S1", background=True))
        result, _ = self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S2"))
        self.assertIn("duplicate", self.context(result).lower())

    def test_unwritable_registry_fails_open(self):
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / "inflight").write_text("not a directory")
        result, err = self.run_hook("agent-nudge", payload("Workhorse fix parser", session="S1"))
        self.assertNotEqual(self.decision(result), "deny")


class WiringTest(_Home):
    def test_claude_host_gets_owned_post_tool_use_release_hook(self):
        claude = next(h for h in host_wiring.HOSTS if h.name == "claude")
        config = host_wiring.add_hooks({}, self.paths, claude)
        post = [h for g in config["hooks"].get("PostToolUse", []) if g.get("matcher") == "Agent|Task"
                for h in g["hooks"]]
        self.assertEqual([h["command"] for h in post], [host_wiring.hook_command(self.paths, "agent-done")])
        self.assertLessEqual(post[0]["timeout"], 5)
        self.assertEqual(host_wiring.strip_hooks(config, self.paths).get("hooks", {}).get("PostToolUse"), None)

    def test_cli_accepts_agent_done_event(self):
        from agents_inc.install import cli
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                cli.main(["hook", "agent-done", "--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)


if __name__ == "__main__":
    unittest.main()
