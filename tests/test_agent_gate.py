"""Agent gate: opt-in blocking PreToolUse deny on Agent/Task, its mode resolution, notice, and `unwire`.

Fixture payloads and a fake HOME only; the operator's AGENTS_INC_AGENT_GATE never leaks in.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli, hook, host_wiring
from agents_inc.install.paths import InstallPaths

ENV = hook.AGENT_GATE_ENV
FIRST_ALLOWED = sorted(hook.GATE_ALLOW)
PERSONA_REASON = hook.PERSONA_DENY_REASON


def payload(subagent="general-purpose", tool="Agent", background=False, description="Grunt fix", session="g1", omit=False):
    tool_input = {"description": description, "prompt": "do it", "run_in_background": background}
    if not omit: tool_input["subagent_type"] = subagent
    return {"session_id": session, "tool_name": tool, "tool_use_id": "t1", "tool_input": tool_input}


class _Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"; self.home.mkdir()
        self.paths = InstallPaths.for_home(self.home)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home)}); env.start(); self.addCleanup(env.stop)
        os.environ.pop(ENV, None)
        self.addCleanup(self.tmp.cleanup)

    def set_env(self, value): os.environ[ENV] = value

    def run_hook(self, data):
        out, err = io.StringIO(), io.StringIO()
        raw = data if isinstance(data, str) else json.dumps(data)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(hook.run(self.paths, "agent-nudge", "claude", io.StringIO(raw)), 0)
        text = out.getvalue().strip()
        return json.loads(text) if text else None

    @staticmethod
    def decision(result): return ((result or {}).get("hookSpecificOutput") or {}).get("permissionDecision")

    @staticmethod
    def reason(result): return ((result or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason") or ""

    @staticmethod
    def context(result): return ((result or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""

    def write_settings(self, text):
        self.paths.settings.parent.mkdir(parents=True, exist_ok=True)
        self.paths.settings.write_text(text)

    def wired_claude(self, extra=None):
        """A settings.json with agents-inc hooks plus foreign hooks; returns the target path."""
        (self.home / ".claude").mkdir(exist_ok=True)
        claude = next(h for h in host_wiring.HOSTS if h.name == "claude")
        config = {"model": "x", "hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "foreign-pre.sh"}]}]}}
        config = host_wiring.add_hooks(config, self.paths, claude)
        config["hooks"]["SessionStart"].append({"hooks": [{"type": "command", "command": "foreign-start.sh"}]})
        next(g for g in config["hooks"]["PreToolUse"] if g.get("matcher") == "Bash")["hooks"].append({"type": "command", "command": "foreign-shared.sh"})  # shared group
        target = self.home / ".claude/settings.json"
        target.write_text(json.dumps(config, indent=2))
        return target


class GateDenyTest(_Gate):
    def setUp(self):
        super().setUp(); self.set_env("enforce")

    def test_allow_each_allowlisted_type_foreground_on_agent_and_task(self):
        for tool in ("Agent", "Task"):
            for subagent in FIRST_ALLOWED:
                with self.subTest(tool=tool, subagent=subagent):
                    self.assertNotEqual(self.decision(self.run_hook(payload(subagent, tool=tool, session=f"{tool}{subagent}"))), "deny")

    def test_deny_general_purpose(self):
        self.assertEqual(self.decision(self.run_hook(payload("general-purpose"))), "deny")

    def test_deny_claude(self):
        self.assertEqual(self.decision(self.run_hook(payload("claude"))), "deny")

    def test_deny_omitted_subagent_type(self):
        result = self.run_hook(payload(omit=True))
        self.assertEqual(self.decision(result), "deny")
        self.assertIn("omitted", self.reason(result))

    def test_deny_allowlisted_type_with_run_in_background_true(self):
        result = self.run_hook(payload("Explore", background=True))
        self.assertEqual(self.decision(result), "deny")

    def test_allow_the_native_luna_type_even_in_background(self):
        # Spec 028 FR-022: the mod's own type is agents-inc's route, so the gate lets it through.
        for background in (False, True):
            with self.subTest(background=background):
                result = self.run_hook(payload("agents-inc:luna", background=background, session=f"n{background}"))
                self.assertNotEqual(self.decision(result), "deny")

    def test_allow_the_native_luna_type_whose_description_names_luna(self):
        result = self.run_hook(payload("agents-inc:luna", description="luna: count lines"))
        self.assertNotEqual(self.decision(result), "deny")

    def test_the_spike_luna_brain_types_are_no_longer_exempt(self):
        for subagent in ("luna-brain:luna", "luna"):
            with self.subTest(subagent=subagent):
                self.assertEqual(self.decision(self.run_hook(payload(subagent, session=subagent))), "deny")

    def test_deny_a_lookalike_of_the_native_type(self):
        for subagent in ("x-agents-inc:luna", "agents-inc:luna-2", "agents-inc:", "agents-inc:luna "):
            with self.subTest(subagent=subagent):
                self.assertEqual(self.decision(self.run_hook(payload(subagent, session=subagent))), "deny")

    def test_native_type_passes_in_advisory_and_off_too(self):
        for mode in ("advisory", "off"):
            with self.subTest(mode=mode):
                self.set_env(mode)
                self.assertNotEqual(self.decision(self.run_hook(payload("agents-inc:luna", session=mode))), "deny")

    def test_deny_task_tool_too(self):
        self.assertEqual(self.decision(self.run_hook(payload("general-purpose", tool="Task"))), "deny")

    def test_deny_reason_contains_each_required_verbatim_string(self):
        result = self.run_hook(payload("general-purpose", background=True))
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        reason = self.reason(result)
        for needle in ("agents-inc agent gate", "general-purpose", "background: yes", ", ".join(FIRST_ALLOWED),
                       "agents-inc dispatch --slots <json> --model <opus|sonnet|haiku|fable>",
                       "Naming a model picks the rung, not the route.", "AGENTS_INC_AGENT_GATE=off claude",
                       "agents-inc repair --agent-gate advisory"):
            with self.subTest(needle=needle): self.assertIn(needle, reason)

    def test_deny_returns_before_claiming_an_inflight_entry(self):
        self.run_hook(payload("general-purpose"))
        inflight = self.paths.state / "inflight"
        self.assertEqual(list(inflight.glob("*")) if inflight.exists() else [], [])

    def test_persona_deny_still_wins_with_its_exact_fr002_reason(self):
        result = self.run_hook(payload("general-purpose", description="terra: implement X"))
        self.assertEqual(self.reason(result), PERSONA_REASON)
        self.assertTrue(self.reason(result).startswith("FR-002:"))

    def test_bash_and_delegate_agent_are_never_gate_denied(self):
        bash = {"session_id": "b", "tool_name": "Bash", "tool_input": {"command": "agents-inc dispatch --model opus"}}
        delegate = {"session_id": "d", "tool_name": "mcp__delegate-agent__DelegateAgent", "tool_input": {"subagent_type": "general-purpose"}}
        for data in (bash, delegate):
            with self.subTest(tool=data["tool_name"]): self.assertNotEqual(self.decision(self.run_hook(data)), "deny")

    def test_opus_xhigh_denied_under_enforce(self):
        self.assertEqual(self.decision(self.run_hook(payload("opus-xhigh"))), "deny")

    def test_fail_open_on_malformed_payloads(self):
        for raw in ("not json", "[]", json.dumps({"tool_name": "Agent", "tool_input": "x"}),
                    json.dumps({"tool_name": "Agent", "tool_input": ["general-purpose"]})):
            with self.subTest(raw=raw): self.assertNotEqual(self.decision(self.run_hook(raw)), "deny")


class GateModeTest(_Gate):
    def test_env_off_means_no_deny(self):
        self.set_env("off")
        self.assertNotEqual(self.decision(self.run_hook(payload("general-purpose"))), "deny")

    def test_env_advisory_means_no_deny_and_nudge_context_present(self):
        self.set_env("advisory")
        result = self.run_hook(payload("general-purpose"))
        self.assertNotEqual(self.decision(result), "deny")
        self.assertIn(hook.NUDGE, self.context(result))

    def test_settings_json_advisory_means_no_deny(self):
        self.write_settings(json.dumps({"agent_gate": "advisory"}))
        self.assertNotEqual(self.decision(self.run_hook(payload("general-purpose"))), "deny")

    def test_settings_json_enforce_denies(self):
        self.write_settings(json.dumps({"agent_gate": "enforce"}))
        self.assertEqual(hook.agent_gate_mode(self.paths), ("enforce", f"settings {self.paths.settings}"))
        self.assertEqual(self.decision(self.run_hook(payload("general-purpose"))), "deny")

    def test_env_enforce_overrides_settings_off(self):
        self.write_settings(json.dumps({"agent_gate": "off"}))
        self.set_env("enforce")
        self.assertEqual(hook.agent_gate_mode(self.paths), ("enforce", "env AGENTS_INC_AGENT_GATE"))
        self.assertEqual(self.decision(self.run_hook(payload("general-purpose"))), "deny")

    def test_no_env_and_no_settings_defaults_advisory_and_general_purpose_not_denied(self):
        self.assertEqual(hook.agent_gate_mode(self.paths), ("advisory", "default"))
        self.assertNotEqual(self.decision(self.run_hook(payload("general-purpose"))), "deny")

    def test_malformed_settings_yield_advisory_with_unreadable_source(self):
        for text in ("{not json", "[]"):
            with self.subTest(text=text):
                self.write_settings(text)
                self.assertEqual(hook.agent_gate_mode(self.paths), ("advisory", "default; settings unreadable"))
                self.assertNotEqual(self.decision(self.run_hook(payload("general-purpose"))), "deny")

    def test_invalid_env_value_falls_through_to_settings(self):
        self.set_env("banana")
        self.assertEqual(hook.agent_gate_mode(self.paths), ("advisory", "default"))
        self.write_settings(json.dumps({"agent_gate": "enforce"}))
        self.assertEqual(hook.agent_gate_mode(self.paths)[0], "enforce")

    def test_env_value_is_stripped_and_lowercased(self):
        self.set_env("  ENFORCE ")
        self.assertEqual(hook.agent_gate_mode(self.paths)[0], "enforce")

    def test_write_agent_gate_keeps_other_keys_and_rejects_bad_mode(self):
        self.write_settings(json.dumps({"other": 1}))
        hook.write_agent_gate(self.paths, "enforce")
        self.assertEqual(json.loads(self.paths.settings.read_text()), {"other": 1, "agent_gate": "enforce"})
        self.assertEqual(self.paths.settings.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError): hook.write_agent_gate(self.paths, "maybe")
        self.assertEqual(json.loads(self.paths.settings.read_text())["agent_gate"], "enforce")

    def test_write_agent_gate_creates_missing_file_and_refuses_malformed(self):
        hook.write_agent_gate(self.paths, "off")
        self.assertEqual(json.loads(self.paths.settings.read_text()), {"agent_gate": "off"})
        self.write_settings("{broken")
        with self.assertRaises(RuntimeError) as ctx: hook.write_agent_gate(self.paths, "enforce")
        self.assertIn(str(self.paths.settings), str(ctx.exception))
        self.assertEqual(self.paths.settings.read_text(), "{broken")


class GateCliTest(_Gate):
    def cli_out(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = cli.main(argv)
        return rc, out.getvalue()

    def test_doctor_cli_prints_agent_gate_line(self):
        _, text = self.cli_out(["doctor"])
        self.assertIn("agent gate: advisory (default)", text.splitlines()[1])

    def test_doctor_json_shape_unchanged_by_gate(self):
        _, text = self.cli_out(["doctor", "--json"])
        self.assertEqual(set(json.loads(text)), {"ready", "codes", "live", "warnings"})

    def test_install_notice_text_names_unwire_env_bypass_and_settings_json(self):
        text = hook.gate_notice(self.paths)
        self.assertLessEqual(len(text.splitlines()), 8)
        for needle in ("agents-inc unwire", "AGENTS_INC_AGENT_GATE=off", "settings.json", "agents-inc repair --agent-gate enforce"):
            with self.subTest(needle=needle): self.assertIn(needle, text)

    def test_install_notice_omits_advisory_warning_under_enforce(self):
        self.set_env("enforce")
        self.assertNotIn("skip agents-inc routing", hook.gate_notice(self.paths))

    def test_cli_install_and_repair_accept_agent_gate_flag(self):
        for command in ("install", "repair"):
            with self.subTest(command=command):
                with self.assertRaises(SystemExit) as ctx: self.cli_out([command, "--agent-gate", "bogus"])
                self.assertEqual(ctx.exception.code, 2)


class UnwireTest(_Gate):
    def test_unwire_removes_owned_entries_and_keeps_foreign_content(self):
        target = self.wired_claude()
        removed = host_wiring.unwire_hooks(self.paths, "claude")
        self.assertTrue(removed)
        self.assertTrue(any(line.startswith("PreToolUse Agent|Task: ") for line in removed))
        self.assertTrue(any(line.startswith("SessionStart *: ") for line in removed))
        config = json.loads(target.read_text())
        self.assertEqual(config["model"], "x")
        commands = [h["command"] for groups in config["hooks"].values() for g in groups for h in g["hooks"]]
        self.assertEqual(sorted(commands), ["foreign-pre.sh", "foreign-shared.sh", "foreign-start.sh"])
        shared = next(g for g in config["hooks"]["PreToolUse"] if g.get("matcher") == "Bash")
        self.assertEqual([h["command"] for h in shared["hooks"]], ["foreign-shared.sh"])
        self.assertEqual(host_wiring.wiring_problems(self.paths).count("claude:hooks"), 1)

    def test_unwire_second_run_returns_empty_and_leaves_file_byte_identical(self):
        target = self.wired_claude()
        host_wiring.unwire_hooks(self.paths, "claude")
        before = target.read_bytes()
        self.assertEqual(host_wiring.unwire_hooks(self.paths, "claude"), [])
        self.assertEqual(target.read_bytes(), before)

    def test_unwire_on_missing_settings_file_returns_empty(self):
        self.assertEqual(host_wiring.unwire_hooks(self.paths, "claude"), [])
        self.assertFalse((self.home / ".claude/settings.json").exists())

    def test_unwire_keeps_a_backup_under_the_state_dir(self):
        self.wired_claude()
        host_wiring.unwire_hooks(self.paths, "claude")
        self.assertTrue(list((self.paths.state / "backups").glob("settings.json.*")))

    def test_cli_unwire_end_to_end_prints_removed_then_nothing_to_remove(self):
        target = self.wired_claude()
        rc, first = self.cli_run(["unwire"])
        self.assertEqual(rc, 0)
        self.assertIn("removed: ", first)
        self.assertIn("agents-inc repair", first)
        self.assertIn("WB_HOST_UNWIRED", first)
        rc, second = self.cli_run(["unwire"])
        self.assertEqual(rc, 0)
        self.assertIn(f"nothing to remove: no agents-inc hooks in {target}", second)
        self.assertNotIn("removed: ", second)

    def cli_run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = cli.main(argv)
        return rc, out.getvalue()


if __name__ == "__main__":
    unittest.main()
