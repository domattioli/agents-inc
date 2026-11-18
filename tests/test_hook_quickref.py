"""QUICKREF.md loads into context once per session on the first dispatch-shaped tool call.

Fixture payloads and a fake home only.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import hook
from agents_inc.install.paths import InstallPaths

MARK = "# workerbee quick reference (fixture)"
DISPATCH = "agents-inc dispatch --slots x.json --model opus"


def bash(command, session="s1"):
    return {"session_id": session, "tool_name": "Bash", "tool_input": {"command": command}}


def agent(session="s1", description="Grunt fix typo"):
    return {"session_id": session, "tool_name": "Agent", "tool_input": {"description": description, "prompt": "p"}}


class QuickrefTest(unittest.TestCase):
    def setUp(self):
        gate = mock.patch.dict(os.environ, {"AGENTS_INC_AGENT_GATE": "advisory"}); gate.start(); self.addCleanup(gate.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = InstallPaths.for_home(Path(self.tmp.name))
        quickref = self.paths.current / "skills/workerbee/QUICKREF.md"
        quickref.parent.mkdir(parents=True, exist_ok=True)
        quickref.write_text(MARK + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def context(self, data):
        out = io.StringIO()
        raw = data if isinstance(data, str) else json.dumps(data)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(hook.run(self.paths, "agent-nudge", None, io.StringIO(raw)), 0)
        text = out.getvalue().strip()
        return json.loads(text)["hookSpecificOutput"].get("additionalContext", "") if text else ""

    def test_native_agent_gets_reminder_without_quickref_or_permission_decision(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(hook.run(self.paths, "agent-nudge", None, io.StringIO(json.dumps(agent()))), 0)
        result = json.loads(output.getvalue())["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", result)
        self.assertNotIn(MARK, result["additionalContext"])
        self.assertIn(hook.NUDGE, result["additionalContext"])
        self.assertEqual(self.context(agent()), "")
        self.assertIn(MARK, self.context(bash(DISPATCH)))

    def test_other_session_gets_it_again(self):
        self.context(bash(DISPATCH, session="s1"))
        self.assertIn(MARK, self.context(bash(DISPATCH, session="s2")))

    def test_bash_dispatch_gets_quickref_without_agent_nudge(self):
        text = self.context(bash(DISPATCH))
        self.assertIn(MARK, text)
        self.assertNotIn(hook.NUDGE, text)
        self.assertEqual(self.context(bash(DISPATCH)), "")

    def test_bridge_scripts_and_codex_exec_count_as_dispatch(self):
        for i, cmd in enumerate(("bash ~/x/gask.sh 'q'", "agent.sh run", "codex exec -m x 'p'")):
            with self.subTest(cmd=cmd):
                self.assertIn(MARK, self.context(bash(cmd, session=f"b{i}")))

    def test_plain_bash_gets_nothing(self):
        for cmd in ("ls -la", "ls", "cat agents.sh.txt", "grep dispatch x"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.context(bash(cmd)), "")
        self.assertFalse((self.paths.state / "quickref").exists())

    def test_delegate_agent_mcp_tool_gets_quickref(self):
        payload = {"session_id": "m1", "tool_name": "mcp__delegate-agent__DelegateAgent", "tool_input": {}}
        text = self.context(payload)
        self.assertIn(MARK, text)
        self.assertNotIn(hook.NUDGE, text)

    def test_missing_quickref_yields_note_not_error(self):
        (self.paths.current / "skills/workerbee/QUICKREF.md").unlink()
        self.assertIn("quickref missing", self.context(bash(DISPATCH)))

    def test_malformed_stdin_is_silent(self):
        for raw in ("garbage", "[]", json.dumps({"tool_name": "Bash", "tool_input": "x"})):
            with self.subTest(raw=raw):
                self.assertEqual(self.context(raw), "")


if __name__ == "__main__":
    unittest.main()
