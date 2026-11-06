"""Spec 013 (#41): the installer owns the at_route hook entry and the @alias links.

Supervisor-owned acceptance tests. Fake HOME only; nothing touches the live machine.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli
from agents_inc.install import host_wiring
from agents_inc.install.doctor import check_install
from agents_inc.install.paths import InstallPaths
from agents_inc.install.receipt import InstallReceipt
from agents_inc.install.transaction import TransactionJournal

ALIASES = ("haiku", "sonnet", "opus", "fable", "astra", "sol", "terra", "luna", "gemini", "mistral", "openrouter")
HOOK_TEXT = "#!/usr/bin/env bash\n# at_route.sh - UserPromptSubmit hook. Routes \"@<alias> <question>\" to a cheap model.\nexit 0\n"
LEGACY_COMMAND = "bash ~/.claude/scripts/at_route.sh"
HOST = {"which": lambda *a, **k: "/usr/bin/claude", "sandbox_probe": lambda: True}  # results must not depend on the host


class AtRouteInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raw = Path(self.tmp.name)
        self.source = raw / "source"
        (self.source / "agents_inc").mkdir(parents=True)
        (self.source / "agents_inc" / "models.json").write_text("{}")
        for name in ("workerbee", "codex-bridge"):
            (self.source / "skills" / name).mkdir(parents=True)
            (self.source / "skills" / name / "SKILL.md").write_text("x")
        scripts = self.source / "skills/codex-bridge/scripts"; scripts.mkdir(parents=True)
        (scripts / "at_route.sh").write_text(HOOK_TEXT)
        self.home = raw / "home"; (self.home / ".claude").mkdir(parents=True)
        self.paths = InstallPaths.for_home(self.home)
        self.settings = self.home / ".claude/settings.json"
        self.bin = self.paths.launcher.parent
        self.installed_hook = self.paths.current / "skills/codex-bridge/scripts/at_route.sh"

    def tearDown(self): self.tmp.cleanup()

    def _args(self): return argparse.Namespace(source=str(self.source), adopt_existing_workerbee=False, without_codex=True, no_host_wiring=False)

    def _install(self):
        with mock.patch.object(cli, "_paths", return_value=self.paths):
            self.assertEqual(cli.install(self._args()), 0)

    def _prompt_commands(self):
        config = json.loads(self.settings.read_text())
        return [h for g in config.get("hooks", {}).get("UserPromptSubmit", []) for h in g.get("hooks", [])]

    # FR-004, FR-005
    def test_install_writes_one_owned_prompt_hook_at_installed_path(self):
        self._install(); self._install()  # repair must not duplicate
        hooks = [h for h in self._prompt_commands() if "at_route.sh" in h["command"]]
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0]["command"], f"bash {self.installed_hook}")
        self.assertGreater(hooks[0]["timeout"], 120)
        self.assertTrue(self.installed_hook.is_file())

    def test_foreign_prompt_hooks_survive_install_and_uninstall(self):
        before = {"model": "x", "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "foreign.sh"}]}]}}
        self.settings.write_text(json.dumps(before, indent=2) + "\n")
        original = self.settings.read_bytes()
        self._install()
        self.assertIn("foreign.sh", [h["command"] for h in self._prompt_commands()])
        receipt = InstallReceipt.load(self.paths.receipt)
        retained = cli.uninstall(self.paths, receipt)
        self.assertEqual(retained, set())
        self.assertEqual(json.loads(self.settings.read_text()), before)  # SC-004 (semantic)

    def test_install_then_uninstall_is_byte_identical(self):
        # SC-004: settings written in the installer's own JSON style round-trip byte-for-byte.
        self.settings.write_text(json.dumps({"model": "x"}, indent=2, ensure_ascii=False) + "\n")
        original = self.settings.read_bytes()
        self._install()
        cli.uninstall(self.paths, InstallReceipt.load(self.paths.receipt))
        # The only allowed residue is the empty "hooks" object that remove_host_wiring has left
        # since dd48471 (asserted in test_install_host_wiring.test_uninstall_removes_only_owned_content).
        config = json.loads(self.settings.read_text())
        self.assertEqual(config.pop("hooks", {}), {})
        self.assertEqual((json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode(), original)

    # FR-004, FR-005, FR-009 (CLI links)
    def test_alias_links_point_at_installed_hook_and_are_owned(self):
        self._install()
        receipt = InstallReceipt.load(self.paths.receipt)
        owned = {item.path: item for item in receipt.owned_paths}
        for alias in ALIASES:
            link = self.bin / f"@{alias}"
            self.assertTrue(link.is_symlink(), alias)
            self.assertEqual(os.readlink(link), str(self.installed_hook), alias)
            self.assertIn(link, owned, alias)
            self.assertEqual(owned[link].kind, "symlink")
        self._install()  # repair: no duplicate receipt entries (analyze A7)
        receipt = InstallReceipt.load(self.paths.receipt)
        paths_owned = [item.path for item in receipt.owned_paths]
        self.assertEqual(len(paths_owned), len(set(paths_owned)))
        cli.uninstall(self.paths, receipt)
        for alias in ALIASES:
            self.assertFalse((self.bin / f"@{alias}").is_symlink(), alias)

    def test_no_host_wiring_creates_no_alias_links(self):
        args = self._args(); args.no_host_wiring = True
        with mock.patch.object(cli, "_paths", return_value=self.paths):
            self.assertEqual(cli.install(args), 0)
        self.assertEqual(sorted(p.name for p in self.bin.glob("@*")), [])

    def test_uninstall_keeps_a_legacy_line_added_after_install(self):
        self._install()
        config = json.loads(self.settings.read_text())
        config["hooks"]["UserPromptSubmit"].append({"hooks": [{"type": "command", "command": LEGACY_COMMAND}]})
        self.settings.write_text(json.dumps(config, indent=2) + "\n")
        cli.uninstall(self.paths, InstallReceipt.load(self.paths.receipt))
        self.assertIn(LEGACY_COMMAND, [h["command"] for h in self._prompt_commands()])

    def test_foreign_alias_file_is_left_untouched(self):
        self.bin.mkdir(parents=True); (self.bin / "@haiku").write_text("mine")
        self._install()
        self.assertEqual((self.bin / "@haiku").read_text(), "mine")
        owned = [item.path for item in InstallReceipt.load(self.paths.receipt).owned_paths]
        self.assertNotIn(self.bin / "@haiku", owned)

    # FR-007
    def test_legacy_line_links_and_file_are_replaced(self):
        legacy = self.home / ".claude/scripts/at_route.sh"; legacy.parent.mkdir(parents=True); legacy.write_text(HOOK_TEXT)
        self.bin.mkdir(parents=True)
        for alias in ALIASES[:10]: (self.bin / f"@{alias}").symlink_to(legacy)
        group = {"hooks": [{"type": "command", "command": "sibling.sh"}, {"type": "command", "command": LEGACY_COMMAND, "timeout": 130}]}
        self.settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [group]}}, indent=2) + "\n")
        self._install()
        commands = [h["command"] for h in self._prompt_commands()]
        self.assertNotIn(LEGACY_COMMAND, commands)
        self.assertIn("sibling.sh", commands)
        self.assertIn(f"bash {self.installed_hook}", commands)
        for alias in ALIASES:
            self.assertEqual(os.readlink(self.bin / f"@{alias}"), str(self.installed_hook), alias)
        self.assertFalse(legacy.exists())
        backups = list((self.paths.state / "backups").glob("at_route.sh.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), HOOK_TEXT)

    def test_legacy_file_without_marker_is_kept(self):
        legacy = self.home / ".claude/scripts/at_route.sh"; legacy.parent.mkdir(parents=True); legacy.write_text("something else\n")
        self._install()
        self.assertEqual(legacy.read_text(), "something else\n")

    def test_interrupted_install_restores_legacy_file_links_and_settings(self):
        legacy = self.home / ".claude/scripts/at_route.sh"; legacy.parent.mkdir(parents=True); legacy.write_text(HOOK_TEXT)
        self.bin.mkdir(parents=True); (self.bin / "@haiku").symlink_to(legacy)
        self.settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": LEGACY_COMMAND}]}]}}, indent=2) + "\n")
        before = self.settings.read_bytes()
        receipt = InstallReceipt("a" * 64, Path("/usr/bin/python3"), None)
        journal = TransactionJournal(self.paths.journal).begin("install")
        receipt = host_wiring.install_host_wiring(self.paths, receipt, journal)
        host_wiring.install_alias_links(self.paths, receipt, journal)
        self.assertFalse(legacy.exists())
        TransactionJournal.recover(self.paths.journal)  # uncommitted: roll back
        self.assertEqual(legacy.read_text(), HOOK_TEXT)
        self.assertEqual(os.readlink(self.bin / "@haiku"), str(legacy))
        self.assertEqual(self.settings.read_bytes(), before)

    # FR-006
    def test_doctor_warns_on_drift_only(self):
        self._install()
        clean = check_install(self.paths, **HOST)
        self.assertNotIn("WB_HOOK_DRIFT", clean.warnings)
        self.assertNotIn("WB_HOOK_DRIFT_UNCHECKED", clean.warnings)
        (self.source / "skills/codex-bridge/scripts/at_route.sh").write_text(HOOK_TEXT + "# edited\n")
        drift = check_install(self.paths, **HOST)
        self.assertIn("WB_HOOK_DRIFT", drift.warnings)
        self.assertNotIn("WB_HOOK_DRIFT", drift.codes)
        self.assertEqual(drift.ready, clean.ready)

    def test_doctor_skips_drift_when_source_unknown(self):
        self._install()
        record = self.paths.state / "source-checkout"
        self.assertEqual(record.read_text().strip(), str(self.source.resolve()))
        record.unlink()
        report = check_install(self.paths, **HOST)
        self.assertIn("WB_HOOK_DRIFT_UNCHECKED", report.warnings)
        self.assertNotIn("WB_HOOK_DRIFT", report.warnings)


REAL_HOOK = Path(__file__).resolve().parents[1] / "skills/codex-bridge/scripts/at_route.sh"


@unittest.skipUnless(shutil.which("jq"), "at_route.sh needs jq")
class AtRouteCodexRouteTest(unittest.TestCase):
    """D54: Codex aliases go through `agents-inc run --model <alias> --no-tools`, prompt on stdin; no bridge."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.log = self.root / "calls.txt"
        self.fake = self.root / "agents-inc"
        self.fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "' + str(self.log) + '"\n'
                             'cat >> "' + str(self.log) + '"\necho "fake answer"\n')
        self.fake.chmod(0o755)

    def _route(self, *argv, stdin=""):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.root), "TMPDIR": str(self.root),
               "AT_ROUTE_AGENTS_INC": str(self.fake), "AT_ROUTE_LOG": str(self.root / "at_route.log"),
               "AT_ROUTE_COLOR": "0"}
        return subprocess.run(["bash", str(REAL_HOOK), *argv], input=stdin, capture_output=True, text=True,
                              env=env, cwd=str(self.root), timeout=60)

    def test_cli_mode_runs_agents_inc_with_stdin_prompt(self):
        res = self._route("luna", "say hi")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("fake answer", res.stdout)
        args, prompt = self.log.read_text().split("\n", 1)
        self.assertEqual(args, f"run --model luna --no-tools --cwd {self.root}")
        self.assertEqual(prompt, "say hi")

    def test_hook_mode_uses_payload_cwd(self):
        work = self.root / "work"
        work.mkdir()
        payload = json.dumps({"prompt": "@terra what is two plus two", "cwd": str(work)})
        res = self._route(stdin=payload)
        self.assertEqual(res.returncode, 2, res.stderr)  # block mode: the answer goes to stderr
        self.assertIn("fake answer", res.stderr)
        args, prompt = self.log.read_text().split("\n", 1)
        self.assertEqual(args, f"run --model terra --no-tools --cwd {work}")
        self.assertEqual(prompt, "what is two plus two")

    def test_persistent_side_session_cannot_run_bash(self):
        payload = json.dumps({"prompt": "@@haiku what is two plus two", "cwd": str(self.root)})
        res = self._route(stdin=payload)
        text = res.stdout + res.stderr
        self.assertIn("claude --bg -n at-haiku", text, text)
        self.assertIn('--disallowedTools "Edit,Write,NotebookEdit,Bash"', text)
        self.assertIn('--allowedTools "Read,Grep,Glob"', text)

    def test_resolve_prints_pinned_slug(self):
        res = self._route("--resolve", "luna")
        pin = json.loads((REAL_HOOK.parents[3] / "agents_inc/routing.json").read_text())["tiers"]["grunt"]["codex"]
        self.assertEqual((res.returncode, res.stdout.strip()), (0, pin))


if __name__ == "__main__":
    unittest.main()
