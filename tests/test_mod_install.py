"""Spec 027 FR-028: install, repair and uninstall register the agents-inc mod with the Claude CLI; doctor warns when it
is missing. Every run uses a temp HOME and a fake `claude` first on PATH that records its argv."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = "agents-inc@agents-inc-local"
FAKE_CLAUDE = """#!/bin/sh
echo "$@" >> "$HOME/claude.log"
if [ "$1 $2" = "plugin list" ]; then cat "$HOME/claude.plugins" 2>/dev/null; fi
if [ "$1 $2 $3" = "plugin install %(plugin)s" ] && [ -z "$FAKE_CLAUDE_FAIL" ]; then echo %(plugin)s > "$HOME/claude.plugins"; fi
if [ "$1 $2" = "plugin uninstall" ]; then rm -f "$HOME/claude.plugins"; fi
if [ -n "$FAKE_CLAUDE_FAIL" ]; then exit 1; fi
exit 0
""" % {"plugin": PLUGIN}


def _rmtree(path):
    for dirpath, dirnames, _ in os.walk(path):
        for d in dirnames:
            os.chmod(os.path.join(dirpath, d), 0o700)
    shutil.rmtree(path, onerror=lambda func, p, _: (os.chmod(p, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC), func(p)))


class ModInstallTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(_rmtree, self.home)
        self.src = self.home / "src"
        ignore = shutil.ignore_patterns("__pycache__", "*.bak", "node_modules", "types")
        for item in ("agents_inc", "skills/workerbee", "skills/codex-bridge", "mods/agents-inc"):
            shutil.copytree(ROOT / item, self.src / item, ignore=ignore)
        self.bin = self.home / "fakebin"
        self.bin.mkdir()
        claude = self.bin / "claude"
        claude.write_text(FAKE_CLAUDE)
        claude.chmod(0o700)
        self.log = self.home / "claude.log"

    def _cli(self, *argv, claude=True, **env):
        path = (str(self.bin) + os.pathsep if claude else "") + "/usr/bin:/bin"
        e = dict(os.environ, HOME=str(self.home), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1", PATH=path, **env)
        return subprocess.run([sys.executable, "-m", "agents_inc.install.cli", *argv],
                              cwd=self.home, env=e, capture_output=True, text=True)

    def _install(self, command="install", *extra, **kw):
        return self._cli(command, "--source", str(self.src), "--without-codex", "--no-host-wiring", *extra, **kw)

    def _calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_bundle_carries_the_mod(self):
        self.assertEqual(self._install().returncode, 0)
        current = self.home / ".local/share/agents-inc/current"
        self.assertTrue((current / "mods/agents-inc/.claude-plugin/plugin.json").is_file())

    def test_bundle_carries_the_luna_type(self):
        """Spec 028 FR-019: the bundle holds luna.ts, and the one module hooks.json lists is the entry that loads it."""
        self.assertEqual(self._install().returncode, 0)
        hooks = self.home / ".local/share/agents-inc/current/mods/agents-inc/hooks"
        self.assertGreater((hooks / "luna.ts").stat().st_size, 0)
        self.assertEqual(json.loads((hooks / "hooks.json").read_text())["modules"], ["mod.ts"])
        self.assertIn("./luna", (hooks / "mod.ts").read_text())

    def test_install_adds_the_marketplace_then_installs_the_plugin(self):
        r = self._install()
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = [c for c in self._calls() if not c.startswith("plugin list")]
        self.assertEqual(len(calls), 2, calls)
        self.assertTrue(calls[0].startswith("plugin marketplace add "), calls)
        self.assertIn("/mods/agents-inc", calls[0])
        self.assertEqual(calls[1], f"plugin install {PLUGIN}")

    def test_repair_refreshes_an_installed_plugin(self):
        """Spec 031 FR-014: an installed plugin gets a marketplace update and a plugin update, nothing else."""
        self._install()
        self.log.unlink()
        self.assertEqual(self._install("repair").returncode, 0)
        self.assertEqual([c for c in self._calls() if not c.startswith("plugin list")],
                         ["plugin marketplace update agents-inc-local", f"plugin update {PLUGIN}"])

    def test_failed_refresh_is_a_warning_only(self):
        self._install()
        r = self._install("repair", FAKE_CLAUDE_FAIL="1")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bundled_manifest_declares_the_delegate_agent_server(self):
        """Spec 031 FR-013: the plugin manifest ships the DelegateAgent MCP server through a shim."""
        manifest = json.loads((ROOT / "mods/agents-inc/.claude-plugin/plugin.json").read_text())
        server = manifest["mcpServers"]["delegate-agent"]
        self.assertEqual(server["command"], "sh")
        self.assertEqual(server["args"], ["${CLAUDE_PLUGIN_ROOT}/mcp/delegate_agent.sh"])
        self.assertTrue((ROOT / "mods/agents-inc/mcp/delegate_agent.sh").is_file())
        self.assertGreater(tuple(int(x) for x in manifest["version"].split(".")), (0, 1, 0))

    def test_shim_without_a_release_exits_1_with_a_message(self):
        r = subprocess.run(["sh", str(ROOT / "mods/agents-inc/mcp/delegate_agent.sh")], capture_output=True, text=True,
                           env={"HOME": str(self.home), "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("agents-inc release not installed", r.stderr)

    def _doctor_out(self, mcp_list):
        shutil.copy(ROOT / "tests/fixtures/fake_claude/claude", self.bin / "claude")
        self._install("install", "--no-mod")
        return self._cli("doctor", FAKE_CLAUDE_PLUGIN_LIST=PLUGIN, FAKE_CLAUDE_MCP_LIST=mcp_list).stdout

    def test_doctor_warns_on_a_user_scope_delegate_agent(self):
        out = self._doctor_out("delegate-agent: python3 /x/codex_agent_mcp.py - Connected")
        self.assertIn("claude mcp remove --scope user delegate-agent", out)

    def test_doctor_is_quiet_for_the_plugin_server_only(self):
        out = self._doctor_out("plugin:agents-inc:delegate-agent: sh /x/delegate_agent.sh - Connected")
        self.assertNotIn("claude mcp remove", out)

    def test_no_mod_skips_every_claude_call(self):
        self.assertEqual(self._install("install", "--no-mod").returncode, 0)
        self.assertEqual(self._calls(), [])

    def test_missing_claude_cli_is_not_an_error(self):
        r = self._install(claude=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._calls(), [])

    def test_failing_claude_cli_warns_and_stays_green(self):
        r = self._install(FAKE_CLAUDE_FAIL="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning: mod install failed", r.stdout + r.stderr)

    def test_uninstall_removes_the_plugin_and_the_marketplace(self):
        self._install()
        self.log.unlink()
        r = self._cli("uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"plugin uninstall {PLUGIN}", self._calls())
        self.assertIn("plugin marketplace remove agents-inc-local", self._calls())

    def test_doctor_warns_until_the_mod_is_installed(self):
        self._install("install", "--no-mod")
        self.assertIn("MOD_NOT_INSTALLED", self._cli("doctor").stdout)
        self._install()
        self.assertNotIn("MOD_NOT_INSTALLED", self._cli("doctor").stdout)


class ModHomeTest(unittest.TestCase):
    """The claude CLI runs with the install's HOME, never the caller's: an in-process install into a temp home once
    registered the mod in the operator's real Claude config (spec 027 slice 2 review)."""

    def test_every_claude_call_gets_the_install_home(self):
        from unittest import mock
        from agents_inc.install import cli
        home = Path(tempfile.mkdtemp())
        self.addCleanup(_rmtree, home)
        (home / "current/mods/agents-inc/.claude-plugin").mkdir(parents=True)
        (home / "current/mods/agents-inc/.claude-plugin/plugin.json").write_text("{}")
        paths = mock.Mock(home=home, current=home / "current")
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(cli.shutil, "which", return_value=str(home / "fake-claude")), \
                mock.patch.object(cli.subprocess, "run", return_value=done) as run:
            cli.install_mod(paths, [])
            cli.uninstall_mod(paths)
        self.assertGreaterEqual(run.call_count, 4)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"]["HOME"], str(home))


if __name__ == "__main__":
    unittest.main()
