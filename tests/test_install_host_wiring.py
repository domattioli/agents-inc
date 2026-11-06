import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from agents_inc.install import hook
from agents_inc.install.host_wiring import BEGIN, END, install_host_wiring, remove_host_wiring, remove_block, upsert_block, wiring_problems
from agents_inc.install.paths import InstallPaths
from agents_inc.install.receipt import InstallReceipt
from agents_inc.install.transaction import TransactionJournal


def _receipt():
    return InstallReceipt("a" * 64, Path("/usr/bin/python3"), None)


class HostWiringTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.home = Path(self.tmp.name) / "home"
        self.paths = InstallPaths.for_home(self.home)

    def tearDown(self): self.tmp.cleanup()

    def _hosts(self, *names):
        for name in names: (self.home / f".{name}").mkdir(parents=True, exist_ok=True)

    def test_block_upsert_is_idempotent_and_preserves_user_text(self):
        block = f"{BEGIN}\nrule\n{END}\n"
        once = upsert_block("# mine\n\nkeep me\n", block)
        self.assertEqual(upsert_block(once, block), once)
        self.assertIn("keep me", once)
        self.assertEqual(remove_block(once), "# mine\n\nkeep me\n")

    def test_block_upsert_replaces_stale_block_in_place(self):
        text = f"head\n\n{BEGIN}\nold\n{END}\n\ntail\n"
        updated = upsert_block(text, f"{BEGIN}\nnew\n{END}\n")
        self.assertEqual(updated, f"head\n\n{BEGIN}\nnew\n{END}\n\ntail\n")

    def test_only_detected_hosts_are_wired(self):
        self._hosts("claude")
        receipt = install_host_wiring(self.paths, _receipt())
        self.assertTrue((self.home / ".claude/AGENTS.md").exists())
        self.assertFalse((self.home / ".codex").exists())
        self.assertFalse((self.home / ".gemini").exists())
        self.assertEqual({item.kind for item in receipt.owned_paths}, {"block", "hooks"})

    def test_hooks_merge_with_foreign_hooks_and_reinstall_does_not_duplicate(self):
        self._hosts("claude", "codex")
        settings = self.home / ".claude/settings.json"
        settings.write_text(json.dumps({"model": "x", "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "foreign.sh"}]}]}}))
        install_host_wiring(self.paths, _receipt()); install_host_wiring(self.paths, _receipt())
        config = json.loads(settings.read_text())
        commands = [h["command"] for g in config["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual(config["model"], "x")
        self.assertEqual(commands.count("foreign.sh"), 1)
        self.assertEqual(sum("hook session-start" in c for c in commands), 1)
        self.assertEqual(config["hooks"]["PreToolUse"][0]["matcher"], "Agent|Task")
        codex = json.loads((self.home / ".codex/hooks.json").read_text())
        self.assertNotIn("PreToolUse", codex["hooks"])  # nudge is Claude-only
        self.assertEqual(wiring_problems(self.paths), [])

    def test_gemini_reads_agents_md_and_keeps_existing_names(self):
        self._hosts("gemini")
        (self.home / ".gemini/settings.json").write_text(json.dumps({"context": {"fileName": "GEMINI.md"}, "security": {}}))
        install_host_wiring(self.paths, _receipt())
        config = json.loads((self.home / ".gemini/settings.json").read_text())
        self.assertEqual(config["context"]["fileName"], ["AGENTS.md", "GEMINI.md"])
        self.assertIn("security", config)
        self.assertIn(BEGIN, (self.home / ".gemini/AGENTS.md").read_text())

    def test_uninstall_removes_only_owned_content(self):
        self._hosts("claude", "codex")
        (self.home / ".claude/AGENTS.md").write_text("# user rules\n")
        receipt = install_host_wiring(self.paths, _receipt())
        remove_host_wiring(self.paths, receipt)
        self.assertEqual((self.home / ".claude/AGENTS.md").read_text(), "# user rules\n")
        self.assertFalse((self.home / ".codex/AGENTS.md").exists())  # block-only file created by us
        self.assertEqual(json.loads((self.home / ".claude/settings.json").read_text()), {"hooks": {}})
        self.assertEqual(sorted(wiring_problems(self.paths)), ["claude:hooks", "claude:instructions", "codex:hooks", "codex:instructions"])

    def test_journal_recovery_restores_predecessor_bytes(self):
        self._hosts("claude")
        target = self.home / ".claude/AGENTS.md"; target.write_text("original\n")
        journal = TransactionJournal(self.paths.journal).begin("install")
        install_host_wiring(self.paths, _receipt(), journal)
        self.assertIn(BEGIN, target.read_text())
        TransactionJournal.recover(self.paths.journal)  # uncommitted: roll back
        self.assertEqual(target.read_text(), "original\n")
        self.assertFalse((self.home / ".claude/settings.json").exists())

    def test_claude_host_wires_quickref_matchers_and_strip_removes_them(self):
        from agents_inc.install.host_wiring import HOSTS, add_hooks, hook_command, strip_hooks
        claude = next(h for h in HOSTS if h.name == "claude")
        config = add_hooks({}, self.paths, claude)
        nudge = hook_command(self.paths, "agent-nudge")
        matchers = {g["matcher"] for g in config["hooks"]["PreToolUse"] if any(h["command"] == nudge for h in g["hooks"])}
        self.assertEqual(matchers, {"Agent|Task", "Bash", "mcp__.*__DelegateAgent"})
        self.assertIsNone(strip_hooks(config, self.paths).get("hooks", {}).get("PreToolUse"))

    def test_claude_host_gets_sandbox_exclusion_and_strip_removes_only_ours(self):
        from agents_inc.install.host_wiring import HOSTS, add_hooks, strip_hooks
        claude = next(h for h in HOSTS if h.name == "claude")
        config = add_hooks({"sandbox": {"excludedCommands": ["docker *"]}}, self.paths, claude)
        self.assertEqual(config["sandbox"]["excludedCommands"], ["docker *", "agents-inc *"])
        self.assertEqual(add_hooks(config, self.paths, claude)["sandbox"]["excludedCommands"], ["docker *", "agents-inc *"])
        self.assertEqual(strip_hooks(config, self.paths)["sandbox"], {"excludedCommands": ["docker *"]})
        codex = next(h for h in HOSTS if h.name == "codex")
        self.assertNotIn("sandbox", add_hooks({}, self.paths, codex))

    def test_unwire_reports_the_sandbox_exclusion(self):
        from agents_inc.install.host_wiring import unwire_hooks
        self._hosts("claude")
        install_host_wiring(self.paths, _receipt())
        removed = unwire_hooks(self.paths, "claude")
        self.assertIn('sandbox.excludedCommands: agents-inc *', removed)
        self.assertNotIn("sandbox", json.loads((self.home / ".claude/settings.json").read_text()))

    def test_claude_host_gets_allow_rule_once(self):
        from agents_inc.install.host_wiring import HOSTS, add_hooks
        claude = next(h for h in HOSTS if h.name == "claude")
        seed = {"permissions": {"allow": ["Bash(git status)"], "deny": ["Bash(rm *)"]}}
        config = add_hooks(json.loads(json.dumps(seed)), self.paths, claude)
        config = add_hooks(config, self.paths, claude)
        self.assertEqual(config["permissions"]["allow"].count("Bash(agents-inc *)"), 1)
        self.assertEqual(config["permissions"]["allow"], ["Bash(git status)", "Bash(agents-inc *)"])
        self.assertEqual(config["permissions"]["deny"], ["Bash(rm *)"])
        codex = next(h for h in HOSTS if h.name == "codex")
        self.assertNotIn("permissions", add_hooks({}, self.paths, codex))

    def test_no_host_wiring_leaves_settings_without_allow_rule(self):
        import argparse
        from unittest import mock
        from agents_inc.install import cli
        source = Path(self.tmp.name) / "source"; (source / "agents_inc").mkdir(parents=True)
        (source / "agents_inc" / "models.json").write_text("{}")
        for name in ("workerbee", "codex-bridge"):
            (source / "skills" / name).mkdir(parents=True); (source / "skills" / name / "SKILL.md").write_text("x")
        self._hosts("claude")
        settings = self.home / ".claude/settings.json"
        settings.write_text(json.dumps({"permissions": {"allow": ["Bash(git status)"]}}))
        before = settings.read_bytes()
        args = argparse.Namespace(source=str(source), adopt_existing_workerbee=False, without_codex=True, no_host_wiring=True, no_mod=True)
        with mock.patch.object(cli, "_paths", return_value=self.paths):
            self.assertEqual(cli.install(args), 0)
        self.assertEqual(settings.read_bytes(), before)
        self.assertNotIn("Bash(agents-inc *)", settings.read_text())

    def test_uninstall_removes_only_our_allow_rule(self):
        from agents_inc.install.host_wiring import unwire_hooks
        self._hosts("claude")
        settings = self.home / ".claude/settings.json"
        seed = ["Bash(git status)", "Bash(agents-inc doctor)"]
        settings.write_text(json.dumps({"permissions": {"allow": list(seed)}}))
        receipt = install_host_wiring(self.paths, _receipt())
        self.assertIn("Bash(agents-inc *)", json.loads(settings.read_text())["permissions"]["allow"])
        remove_host_wiring(self.paths, receipt)
        self.assertEqual(json.loads(settings.read_text())["permissions"]["allow"], seed)
        settings.write_text("{}")
        receipt = install_host_wiring(self.paths, _receipt())
        remove_host_wiring(self.paths, receipt)
        self.assertNotIn("permissions", json.loads(settings.read_text()))
        install_host_wiring(self.paths, _receipt())
        self.assertIn("permissions.allow: Bash(agents-inc *)", unwire_hooks(self.paths, "claude"))

    def test_bash_nudge_handlers_carry_if_filters(self):
        from agents_inc.install.host_wiring import HOSTS, add_hooks, hook_command
        claude = next(h for h in HOSTS if h.name == "claude")
        config = add_hooks({}, self.paths, claude)
        nudge = hook_command(self.paths, "agent-nudge")
        bash = [g for g in config["hooks"]["PreToolUse"] if g["matcher"] == "Bash"]
        self.assertEqual(len(bash), 1)
        handlers = [h for h in bash[0]["hooks"] if h["command"] == nudge]
        self.assertEqual([h["if"] for h in handlers], ["Bash(*agents-inc*)", "Bash(*gask.sh*)", "Bash(*mask.sh*)", "Bash(*oask.sh*)", "Bash(*agent.sh*)", "Bash(*codex exec*)"])
        self.assertTrue(all(h["timeout"] == 5 for h in handlers))

    def test_agent_nudge_fires_once_per_session(self):
        first = hook.agent_nudge(self.paths, {"session_id": "s1"})
        self.assertIn("agents-inc", json.loads(first)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(hook.agent_nudge(self.paths, {"session_id": "s1"}), "")
        self.assertNotEqual(hook.agent_nudge(self.paths, {"session_id": "s2"}), "")

    def test_hook_never_fails_on_bad_input(self):
        self.assertEqual(hook.run(self.paths, "agent-nudge", None, io.StringIO("not json")), 0)
        self.assertEqual(hook.run(self.paths, "session-start", "codex", io.StringIO("")), 0)


if __name__ == "__main__":
    unittest.main()
