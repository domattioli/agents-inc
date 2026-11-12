"""D80: the `roles` object in the agents-inc settings file overrides the D78 role and gate defaults."""
from __future__ import annotations
import contextlib
import io
import itertools
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

from agents_inc import role_defaults
from agents_inc.install import cli, hook
from agents_inc.install.doctor import DoctorReport
from agents_inc.install.host_wiring import BEGIN, END, block_text, install_host_wiring
from agents_inc.install.paths import InstallPaths
from agents_inc.install.receipt import InstallReceipt


class _Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"; self.home.mkdir()
        self.paths = InstallPaths.for_home(self.home)

    def tearDown(self): self.tmp.cleanup()

    def settings(self, data):
        self.paths.settings.parent.mkdir(parents=True, exist_ok=True)
        self.paths.settings.write_text(data if isinstance(data, str) else json.dumps(data))

    def roles(self, **items): self.settings({"agent_gate": "advisory", "roles": items})

    def body(self):
        lines = block_text(self.paths).splitlines()
        return lines[lines.index(BEGIN) + 1:lines.index(END)]

    def session(self):
        report = DoctorReport(True, (), None, ())
        with mock.patch.object(hook, "check_install", return_value=report), \
                mock.patch("agents_inc.install.update_check.notice", return_value=None):
            return json.loads(hook.session_start(self.paths, "claude"))["hookSpecificOutput"]["additionalContext"]

    def nudge(self):
        return hook._nudge_text(self.paths, {"session_id": "s1"})


class DefaultsTest(_Home):
    def test_no_file_gives_defaults_and_no_warning(self):
        roles = role_defaults.load(self.paths.settings)
        self.assertEqual(dict(roles), role_defaults.DEFAULTS)
        self.assertEqual(set(roles.sources.values()), {"default"})
        self.assertEqual(roles.warnings, [])
        self.assertEqual(self.body()[2:5], [f"- {role_defaults.EXECUTIVE_LINE}", f"- {role_defaults.ROLES_LINE}",
                                            f"- {role_defaults.GATE_LINE}"])
        self.assertIn(hook.ROUTE_RULE, self.session())
        self.assertEqual(self.nudge(), hook.NUDGE)

    def test_file_without_roles_gives_defaults_and_no_warning(self):
        self.settings({"agent_gate": "enforce"})
        roles = role_defaults.load(self.paths.settings)
        self.assertEqual(dict(roles), role_defaults.DEFAULTS)
        self.assertEqual(roles.warnings, [])
        self.assertEqual(hook.agent_gate_mode(self.paths, env={})[0], "enforce")  # the agent gate still reads its key

    def test_constants_are_the_default_rendering(self):
        self.assertEqual(role_defaults.GATE_LINE, role_defaults.gate_line(role_defaults.DEFAULTS))
        self.assertEqual(hook.NUDGE, hook.nudge_text(None))
        self.assertEqual(hook.ROUTE_RULE, hook.route_rule(None))


class OverrideTest(_Home):
    def test_write_rung_orchestrator(self):
        self.roles(write_rung="orchestrator")
        self.assertIn("- Rungs: orchestrator (opus, sol) writes code, docs, git and PRs", "\n".join(self.body()))
        self.assertIn("writes", role_defaults.rung_roles(role_defaults.load(self.paths.settings))["orchestrator"])

    def test_grunt_writes(self):
        self.roles(grunt_read_only=False)
        text = "\n".join(self.body())
        self.assertIn("grunt (haiku, luna) does scouts, summaries, triage and small mechanical edits", text)
        self.assertNotIn("grunt (haiku, luna) is read-only", text)

    def test_executive_may_write(self):
        self.roles(executive_judgment_only=False)
        text = "\n".join(self.body())
        self.assertIn("judgment first", text)
        self.assertNotIn("judgment only", text)

    def test_no_native_small_edit_sends_every_edit_to_dispatch(self):
        self.roles(native_small_edit=False)
        self.assertIn("any edit, and anything larger: `agents-inc dispatch`", "\n".join(self.body()))
        for text in (self.session(), self.nudge()):
            self.assertNotIn("native workhorse subagent", text)
            self.assertIn("agents-inc dispatch", text)
            self.assertIn("picks the rung, not the route", text)
        self.assertIn("every edit goes through `agents-inc dispatch`", self.session())

    def test_native_edit_model_and_small_task_calls(self):
        self.roles(native_edit_model="opus", small_task_calls=5)
        self.assertIn("5 or fewer with edits: native orchestrator subagent (Claude Code: Agent, model opus",
                      "\n".join(self.body()))
        for text in (self.session(), self.nudge()):
            self.assertIn("5 or fewer tool calls on a native orchestrator subagent (model opus)", text)

    def test_haiku_edit_model_needs_grunt_writes(self):
        self.roles(native_edit_model="haiku", grunt_read_only=False)
        self.assertIn("native grunt subagent (model haiku)", self.nudge())

    def test_hook_text_changes_at_once(self):
        before = self.session()
        self.roles(small_task_calls=7)
        self.assertNotEqual(before, self.session())
        self.assertIn("7 or fewer tool calls", self.session())

    def test_install_renders_the_block_from_settings(self):
        (self.home / ".claude").mkdir()
        self.roles(small_task_calls=2)
        install_host_wiring(self.paths, InstallReceipt("a" * 64, Path("/usr/bin/python3"), None), claude_settings=False)
        self.assertIn("Gate: 2 or fewer tool calls", (self.home / ".claude/AGENTS.md").read_text())


class InvalidTest(_Home):
    CASES = (("unknown_item", 1), ("write_rung", "grunt"), ("grunt_read_only", "no"), ("native_small_edit", 0),
             ("native_edit_model", "gpt"), ("small_task_calls", 0), ("small_task_calls", 11),
             ("small_task_calls", True), ("small_task_calls", "3"), ("executive_judgment_only", None))

    def test_each_bad_item_falls_back_with_one_warning_naming_the_key(self):
        for key, value in self.CASES:
            with self.subTest(key=key, value=value):
                self.roles(**{key: value})
                roles = role_defaults.load(self.paths.settings)
                self.assertEqual(dict(roles), role_defaults.DEFAULTS)
                self.assertEqual(len(roles.warnings), 1, roles.warnings)
                self.assertIn(f"roles.{key}", roles.warnings[0])
                self.assertEqual(hook.route_rule(roles), hook.ROUTE_RULE)

    def test_good_item_kept_beside_a_bad_one(self):
        self.roles(small_task_calls=4, write_rung="intern")
        roles = role_defaults.load(self.paths.settings)
        self.assertEqual((roles["small_task_calls"], roles.sources["small_task_calls"]), (4, "settings"))
        self.assertEqual((roles["write_rung"], roles.sources["write_rung"]), ("workhorse", "default"))

    def test_haiku_with_read_only_grunt_falls_back(self):
        self.roles(native_edit_model="haiku")
        roles = role_defaults.load(self.paths.settings)
        self.assertEqual(roles["native_edit_model"], "sonnet")
        self.assertIn("roles.native_edit_model", roles.warnings[0])

    def test_loader_never_raises(self):
        for text in ("{not json", "[]", '{"roles": []}', '{"roles": "x"}', "\x00"):
            with self.subTest(text=text):
                self.settings(text)
                roles = role_defaults.load(self.paths.settings)
                self.assertEqual(dict(roles), role_defaults.DEFAULTS)
                self.assertIn(hook.ROUTE_RULE, self.session())
                self.assertEqual(self.nudge(), hook.NUDGE); (self.paths.state / "nudged/s1").unlink()

    def test_doctor_prints_values_sources_and_warning(self):
        self.roles(small_task_calls=4, write_rung="intern")
        out = self._doctor()
        self.assertIn("role small_task_calls=4 (settings)", out)
        self.assertIn('role native_edit_model="sonnet" (default)', out)
        warnings = [line for line in out.splitlines() if line.startswith("WARNING:") and "roles." in line]
        self.assertEqual(len(warnings), 1, out)
        self.assertIn("roles.write_rung", warnings[0])

    def test_doctor_with_no_file_has_no_role_warning(self):
        self.assertNotIn("roles.", self._doctor())

    def _doctor(self):
        out = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), \
                mock.patch.object(cli, "check_install", return_value=DoctorReport(True, (), None, ())), \
                contextlib.redirect_stdout(out):
            cli.main(["doctor"])
        return out.getvalue()


class SetSurfaceTest(_Home):
    def setUp(self):
        super().setUp()
        self.paths.receipt.parent.mkdir(parents=True, exist_ok=True)  # repair runs only on an installed home
        InstallReceipt("a" * 64, Path("/usr/bin/python3"), None).save_atomic(self.paths.receipt)

    def test_write_role_keeps_other_keys_and_reset_removes(self):
        self.settings({"agent_gate": "enforce", "legacy_routes": "off"})
        self.assertIn("role small_task_calls=5", hook.write_role(self.paths, "small_task_calls=5"))
        hook.write_role(self.paths, "grunt_read_only=false")
        data = json.loads(self.paths.settings.read_text())
        self.assertEqual(data["roles"], {"small_task_calls": 5, "grunt_read_only": False})
        self.assertEqual((data["agent_gate"], data["legacy_routes"]), ("enforce", "off"))
        self.assertEqual(oct(self.paths.settings.stat().st_mode & 0o777), "0o600")
        hook.write_role(self.paths, "small_task_calls=default")
        self.assertEqual(json.loads(self.paths.settings.read_text())["roles"], {"grunt_read_only": False})

    def test_write_role_rejects_bad_input_and_writes_nothing(self):
        for bad in ("small_task_calls=11", "write_rung=grunt", "nope=1", "small_task_calls"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                hook.write_role(self.paths, bad)
        self.assertFalse(self.paths.settings.exists())

    def test_write_role_refuses_a_malformed_file(self):
        self.settings("{not json")
        with self.assertRaises(RuntimeError): hook.write_role(self.paths, "small_task_calls=2")
        self.assertEqual(self.paths.settings.read_text(), "{not json")

    def test_repair_role_stores_before_rendering(self):
        seen = {}
        def fake_install(args, source):
            seen["roles"] = role_defaults.load(self.paths.settings); return 0
        out = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), \
                mock.patch.object(cli, "_install", side_effect=fake_install), contextlib.redirect_stdout(out):
            code = cli.main(["repair", "--source", self.tmp.name, "--no-host-wiring", "--role", "write_rung=orchestrator",
                             "--role", "small_task_calls=6"])
        self.assertEqual(code, 0)
        self.assertEqual((seen["roles"]["write_rung"], seen["roles"]["small_task_calls"]), ("orchestrator", 6))
        self.assertIn("re-renders the managed block", out.getvalue())

    def test_repair_bad_role_exits_2_without_installing(self):
        err = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), \
                mock.patch.object(cli, "_install") as install, contextlib.redirect_stderr(err):
            code = cli.main(["repair", "--no-host-wiring", "--role", "small_task_calls=99"])
        self.assertEqual(code, 2)
        install.assert_not_called()
        self.assertIn("small_task_calls", err.getvalue())


class BlockSizeTest(unittest.TestCase):
    def test_heading_plus_at_most_five_lines_under_every_valid_setting(self):
        keys = list(role_defaults.DEFAULTS)
        grid = [list(role_defaults.CHOICES[k]) for k in keys]
        for combo in itertools.product(*grid):
            roles = role_defaults.resolve({"roles": dict(zip(keys, combo))})
            with mock.patch.object(role_defaults, "load", return_value=roles):
                lines = block_text(InstallPaths.for_home(Path("/home/u"))).splitlines()
            body = lines[lines.index(BEGIN) + 1:lines.index(END)]
            self.assertTrue(body[0].startswith("## agents-inc delegation"))
            self.assertLessEqual(len(body[1:]), 5, combo)
            self.assertNotIn("", body)
            self.assertTrue(all("\n" not in line for line in body))


if __name__ == "__main__":
    unittest.main()
