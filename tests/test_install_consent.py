"""H (2026-11-11): install/repair show the ~/.claude/settings.json entries and write them only with consent."""
import argparse, contextlib, io, json, tempfile, unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli
from agents_inc.install.paths import InstallPaths


class _Tty(io.StringIO):
    def isatty(self): return True


class ConsentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name) / "home"; (home / ".claude").mkdir(parents=True)
        self.paths = InstallPaths.for_home(home)
        self.settings = home / ".claude/settings.json"

    def _ask(self, stdin, **flags):
        args = argparse.Namespace(command="repair", source=None, **flags)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok = cli._settings_consent(args, self.paths, "repair", stdin=stdin)
        return ok, out.getvalue()

    def test_plan_lists_entries_and_prompt_note(self):
        from agents_inc.install import hook as host_hook
        host_hook.write_legacy_routes(self.paths, True)  # the @alias hook and its note come only with --legacy-routes
        _, out = self._ask(io.StringIO(), yes=True)
        self.assertIn("hooks.UserPromptSubmit", out)
        self.assertIn("sandbox.excludedCommands: agents-inc dispatch *", out)
        self.assertNotIn("sandbox.excludedCommands: agents-inc *\n", out)
        self.assertIn("does not start with @<alias> is not sent anywhere", out)

    def test_default_plan_has_no_prompt_hook_and_no_prompt_note(self):
        _, out = self._ask(io.StringIO(), yes=True)
        self.assertNotIn("hooks.UserPromptSubmit", out)
        self.assertNotIn("@<alias>", out)

    def test_confirm_yes(self):
        ok, _ = self._ask(_Tty("y\n"))
        self.assertTrue(ok)

    def test_confirm_no(self):
        ok, out = self._ask(_Tty("n\n"))
        self.assertFalse(ok); self.assertIn("left unchanged", out)

    def test_yes_flag_skips_question(self):
        ok, out = self._ask(_Tty(""), yes=True)
        self.assertTrue(ok); self.assertNotIn("[y/N]", out)

    def test_no_tty_writes_nothing_and_prints_command(self):
        ok, out = self._ask(io.StringIO("y\n"))
        self.assertFalse(ok)
        self.assertIn("Apply with: agents-inc repair --yes", out)

    def test_no_sandbox_exclude_plan_has_no_exclusion(self):
        _, out = self._ask(io.StringIO(), yes=True, no_sandbox_exclude=True)
        self.assertNotIn("sandbox.excludedCommands", out)

    def test_nothing_pending_asks_nothing(self):
        from agents_inc.install.host_wiring import settings_plan
        target, text, _ = settings_plan(self.paths)
        target.write_text(text)
        ok, out = self._ask(io.StringIO())
        self.assertTrue(ok); self.assertEqual(out, "")

    def test_install_without_consent_leaves_settings_unwritten(self):
        args = argparse.Namespace(command="install", source="/nonexistent", no_host_wiring=False)
        with mock.patch.object(cli, "_paths", return_value=self.paths), mock.patch.object(cli, "_install", return_value=0) as inst, \
             mock.patch.object(cli.sys, "stdin", io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.install(args), 0)
        self.assertFalse(inst.call_args[0][0].claude_settings)
        self.assertFalse(self.settings.exists())


if __name__ == "__main__":
    unittest.main()
