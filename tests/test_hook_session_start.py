"""022 US4: the SessionStart hook shows doctor warnings and the repair line."""
from __future__ import annotations
import json
import os
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

from agents_inc.install import hook
from agents_inc.install.doctor import DoctorReport
from agents_inc.install.paths import InstallPaths


class SessionStartWarningsTest(unittest.TestCase):
    def _text(self, warnings, host="claude", ready=True, codes=()):
        paths = InstallPaths.for_home(Path("/nonexistent-home"))
        report = DoctorReport(ready, codes, None, warnings)
        with mock.patch.object(hook, "check_install", return_value=report), \
                mock.patch("agents_inc.install.update_check.notice", return_value=None):
            out = hook.session_start(paths, host)
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if host == "claude" else out

    def test_warnings_and_repair_line_are_listed(self):
        text = self._text(("INSTALL_STALE", "MODEL_DRIFT luna: pinned a, newest b"))
        self.assertIn("doctor: READY", text)
        self.assertIn("WARNING: INSTALL_STALE", text)
        self.assertIn("WARNING: MODEL_DRIFT luna", text)
        self.assertIn("agents-inc repair", text)

    def test_no_warnings_adds_nothing(self):
        text = self._text(())
        self.assertNotIn("WARNING", text)
        self.assertNotIn("agents-inc repair", text)

    def test_other_warning_has_no_repair_line(self):
        text = self._text(("WB_SANDBOX_NESTED",))
        self.assertIn("WARNING: WB_SANDBOX_NESTED", text)
        self.assertNotIn("Run `agents-inc repair", text)

    def test_sandbox_exclusion_warning_names_the_operator_ask(self):
        text = self._text(("WB_SANDBOX_EXCLUDE_MISSING",))
        self.assertIn("WARNING: WB_SANDBOX_EXCLUDE_MISSING", text)
        self.assertIn('"agents-inc dispatch *"', text)
        self.assertIn("sandbox.excludedCommands", text)

    def test_stale_warning_explains_itself(self):
        self.assertIn("installed bundle differs from the source checkout", self._text(("INSTALL_STALE",)))

    def test_stored_state_is_marked_not_verified_now_with_age(self):
        from agents_inc.install.doctor import DoctorItem
        item = DoctorItem("install-match", False, "record", "pass", "read from source-git.json", 3 * 3600 + 5)
        paths = InstallPaths.for_home(Path("/nonexistent-home"))
        report = DoctorReport(True, (), None, (), (item,))
        with mock.patch.object(hook, "check_install", return_value=report), \
                mock.patch("agents_inc.install.update_check.notice", return_value=None):
            text = json.loads(hook.session_start(paths, "claude"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("install-match", text)
        self.assertIn("not verified now", text)
        self.assertIn("age 3h", text)

    def test_untested_required_item_is_not_ready_and_names_the_check(self):
        from agents_inc.install.doctor import DoctorItem
        item = DoctorItem("dispatch-path", True, "not-tested", "could-not-test", "no route to api.anthropic.com", None)
        paths = InstallPaths.for_home(Path("/nonexistent-home"))
        report = DoctorReport(False, (), None, (), (item,))
        with mock.patch.object(hook, "check_install", return_value=report), \
                mock.patch("agents_inc.install.update_check.notice", return_value=None):
            text = json.loads(hook.session_start(paths, "claude"))["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("doctor: READY", text)
        self.assertIn("dispatch-path", text)
        self.assertIn("agents-inc doctor", text)

    def test_claude_text_names_delegateagent_for_codex_rungs(self):
        text = self._text(())
        self.assertIn("astra, sol, terra and luna run through the DelegateAgent MCP tool", text)
        self.assertIn("read-only", text)
        self.assertNotIn("DelegateAgent MCP tool", self._text(("WB_CLI_NOT_FOUND",)))
        self.assertNotIn("DelegateAgent MCP tool", self._text((), host="codex"))

    def test_nothing_stored_adds_no_mark(self):
        self.assertNotIn("not verified now", self._text(()))

    def test_plain_host_gets_the_same_text(self):
        self.assertIn("WARNING: INSTALL_STALE", self._text(("INSTALL_STALE",), host="codex"))


if __name__ == "__main__":
    unittest.main()



class RouteRuleTest(SessionStartWarningsTest):
    def test_claude_prefers_host_permitted_native_route(self):
        self.assertIn("Use Claude Code Agent", self._text(()))
        self.assertIn("Use Claude Code for any required approvals", hook.NUDGE)
        self.assertNotIn("picks the rung, not the route", hook.NUDGE)

    def test_session_start_carries_route_rule(self):
        self.assertIn(hook.ROUTE_RULE, self._text(()))

    def test_nudge_and_route_rule_allow_small_native_workhorse_edit(self):
        for text in (hook.NUDGE, hook.ROUTE_RULE):
            self.assertIn("3 or fewer tool calls on a native workhorse subagent (model sonnet)", text)
            self.assertIn("Verify the result yourself", text)

    def test_claude_session_drops_quickref_read_except_direct_mcp_run(self):
        # D78 R4: the PreToolUse hook injects QUICKREF on governed dispatch (D53).
        text = self._text(())
        self.assertNotIn("before the first dispatch", text)
        self.assertIn("only before a direct mcp__agents-inc__run call", text)

    def test_codex_session_keeps_quickref_read(self):
        # Codex does not install a QUICKREF injection hook.
        self.assertIn("QUICKREF.md before the first dispatch", self._text((), host="codex"))

    def test_codex_prefers_native_route_when_session_allows_it(self):
        text = self._text((), host="codex")
        self.assertIn("Use Codex native subagents", text)
        self.assertIn("Use agents-inc dispatch only for authorized Claude integration tests", text)
        self.assertNotIn(hook.ROUTE_RULE, text)

    def test_codex_missing_is_explained_not_a_bare_warning(self):
        text = self._text(("WB_CLI_NOT_FOUND",))
        self.assertNotIn("WARNING: WB_CLI_NOT_FOUND", text)
        self.assertIn("check native availability in the host", text)
