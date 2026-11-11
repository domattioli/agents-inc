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

    def test_plain_host_gets_the_same_text(self):
        self.assertIn("WARNING: INSTALL_STALE", self._text(("INSTALL_STALE",), host="codex"))


if __name__ == "__main__":
    unittest.main()



class RouteRuleTest(SessionStartWarningsTest):
    """Token bench dry run 2026-10-22: a session told 'opus, sonnet, haiku' used native Agent subagents
    because the nudge approved any Claude rung. The texts now say the route is always dispatch."""

    def test_nudge_does_not_approve_claude_rungs_via_agent(self):
        self.assertNotIn("only if routing selects a Claude rung", hook.NUDGE)
        self.assertIn("agents-inc dispatch", hook.NUDGE)
        self.assertIn("picks the rung, not the route", hook.NUDGE)

    def test_session_start_carries_route_rule(self):
        self.assertIn(hook.ROUTE_RULE, self._text(()))

    def test_codex_missing_is_explained_not_a_bare_warning(self):
        text = self._text(("WB_CLI_NOT_FOUND",))
        self.assertNotIn("WARNING: WB_CLI_NOT_FOUND", text)
        self.assertIn("Claude rungs dispatch normally", text)
