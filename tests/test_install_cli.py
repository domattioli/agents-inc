import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

from agents_inc.install.cli import install_convenience_launcher, uninstall
from agents_inc.install.receipt import InstallReceipt, OwnedPath
from agents_inc.install.paths import InstallPaths


class CliTest(unittest.TestCase):
    def test_help_lists_lifecycle_commands(self):
        result = subprocess.run([sys.executable, "-m", "agents_inc.install.cli", "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        for command in ("install", "run", "doctor", "repair", "rollback", "uninstall"):
            self.assertIn(command, result.stdout)

    def test_install_refuses_to_overwrite_foreign_convenience_launcher(self):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "source"; (source / "agents_inc").mkdir(parents=True)
            (source / "agents_inc" / "models.json").write_text("{}")
            for name in ("workerbee", "codex-bridge"):
                (source / "skills" / name).mkdir(parents=True); (source / "skills" / name / "SKILL.md").write_text("x")
            paths = InstallPaths.for_home(Path(raw) / "home"); paths.launcher.parent.mkdir(parents=True)
            paths.launcher.write_text("foreign")
            with self.assertRaisesRegex(RuntimeError, "WB_CONFIG_CONFLICT"):
                install_convenience_launcher(paths)

    def test_install_keeps_pip_console_script_at_launcher_path(self):
        # `pip install --user agents-inc` writes its console script to ~/.local/bin/agents-inc, the launcher path.
        with tempfile.TemporaryDirectory() as raw:
            paths = InstallPaths.for_home(Path(raw) / "home"); paths.launcher.parent.mkdir(parents=True)
            paths.launcher.write_text("#!/usr/bin/python3\nimport sys\nfrom agents_inc.install.cli import main\n"
                                      "sys.exit(main())\n")
            owned = install_convenience_launcher(paths)
            self.assertEqual(owned.kind, "external")
            self.assertTrue(paths.launcher.is_file() and not paths.launcher.is_symlink())
            receipt = InstallReceipt("a" * 64, Path("/usr/bin/python3"), None, (owned,))
            receipt.save_atomic(paths.receipt)
            uninstall(paths, receipt)
            self.assertIn("agents_inc.install.cli", paths.launcher.read_text())

    def test_uninstall_preserves_replaced_launcher_and_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            paths = InstallPaths.for_home(Path(raw) / "home")
            paths.launcher.parent.mkdir(parents=True); paths.launcher.symlink_to("/replacement")
            receipt = InstallReceipt("a" * 64, Path("/usr/bin/python3"), Path("/usr/bin/codex"), (OwnedPath(paths.launcher, "symlink"),))
            receipt.save_atomic(paths.receipt)
            retained = uninstall(paths, receipt)
            self.assertEqual(paths.launcher.readlink(), Path("/replacement"))
            self.assertTrue(paths.receipt.exists())
            self.assertIn(paths.launcher, retained)


class RunGuardTest(unittest.TestCase):
    def test_run_rejects_claude_alias_and_passes_codex_alias(self):
        import contextlib, io
        from unittest import mock
        from agents_inc.install import cli
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            paths = InstallPaths.for_home(tmp / "home")
            rel = paths.releases / "h"; rel.mkdir(parents=True)
            paths.current.parent.mkdir(parents=True, exist_ok=True); paths.current.symlink_to(rel)
            InstallReceipt("a" * 64, Path("/usr/bin/python3"), None).save_atomic(paths.receipt)
            with mock.patch.object(cli, "_paths", return_value=paths), mock.patch.object(cli, "_efforts", return_value={}), \
                 mock.patch.object(cli, "run_codex", return_value=0) as rc:
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = cli.main(["run", "--model", "opus", "--effort", "low", "--cwd", str(tmp)])
                self.assertEqual(code, 2)
                self.assertIn(f"Claude aliases go through: agents-inc dispatch --model opus --effort low --cwd {tmp}", err.getvalue())
                rc.assert_not_called()
                self.assertEqual(cli.main(["run", "--model", "luna", "--cwd", str(tmp)]), 0)
                rc.assert_called_once()


class RepairTest(unittest.TestCase):
    def test_install_and_repair_record_stable_codex_not_shim(self):
        import argparse
        from agents_inc.install import cli
        from unittest import mock
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "source"; (source / "agents_inc").mkdir(parents=True)
            (source / "agents_inc" / "models.json").write_text("{}")
            for name in ("workerbee", "codex-bridge"):
                (source / "skills" / name).mkdir(parents=True); (source / "skills" / name / "SKILL.md").write_text("x")
            for d in ("x-shims/abc", "real"):
                (tmp / d).mkdir(parents=True); f = tmp / d / "codex"; f.write_text("#!/bin/sh\n"); f.chmod(0o755)
            home = tmp / "home"; (home / ".claude").mkdir(parents=True)
            paths = InstallPaths.for_home(home)
            args = argparse.Namespace(source=str(source), adopt_existing_workerbee=False, without_codex=False, no_host_wiring=False, yes=True)
            env = {"PATH": f"{tmp / 'x-shims' / 'abc'}:{tmp / 'real'}"}
            with mock.patch.object(cli, "_paths", return_value=paths), mock.patch.dict(os.environ, env), \
                 mock.patch("agents_inc.install.runtime.tempfile.gettempdir", return_value=str(tmp / "t")):
                for _ in range(2):
                    self.assertEqual(cli.install(args), 0)
                    self.assertEqual(InstallReceipt.load(paths.receipt).codex_path, (tmp / "real" / "codex").resolve())

    def test_repair_over_existing_install_keeps_ownership(self):
        import argparse
        from agents_inc.install import cli
        from unittest import mock
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "source"; (source / "agents_inc").mkdir(parents=True)
            (source / "agents_inc" / "models.json").write_text("{}")
            for name in ("workerbee", "codex-bridge"):
                (source / "skills" / name).mkdir(parents=True); (source / "skills" / name / "SKILL.md").write_text("x")
            home = Path(raw) / "home"; (home / ".claude").mkdir(parents=True)
            paths = InstallPaths.for_home(home)
            args = argparse.Namespace(source=str(source), adopt_existing_workerbee=False, without_codex=True, no_host_wiring=False, yes=True)
            with mock.patch.object(cli, "_paths", return_value=paths):
                self.assertEqual(cli.install(args), 0)
                (source / "skills" / "workerbee" / "SKILL.md").write_text("y")  # new release
                self.assertEqual(cli.install(args), 0)
            receipt = InstallReceipt.load(paths.receipt)
            owned = [item.path for item in receipt.owned_paths]
            self.assertEqual(len(owned), len(set(owned)))
            self.assertIn(paths.launcher, owned)
            self.assertIn(home / ".claude/AGENTS.md", owned)


class RepairFailureTest(unittest.TestCase):
    def _fixture(self, raw):
        import argparse
        source = Path(raw) / "source"; (source / "agents_inc").mkdir(parents=True)
        (source / "agents_inc" / "models.json").write_text("{}")
        for name in ("workerbee", "codex-bridge"):
            (source / "skills" / name).mkdir(parents=True); (source / "skills" / name / "SKILL.md").write_text("x")
        home = Path(raw) / "home"; (home / ".claude").mkdir(parents=True)
        paths = InstallPaths.for_home(home)
        args = argparse.Namespace(command="repair", source=str(source), adopt_existing_workerbee=False, without_codex=True, no_host_wiring=False, no_mod=True, yes=True)
        return paths, args

    def test_failed_repair_is_loud_and_marks_doctor_then_clears(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        from agents_inc.install import cli
        from agents_inc.install.doctor import check_install
        with tempfile.TemporaryDirectory() as raw:
            paths, args = self._fixture(raw)
            with mock.patch.object(cli, "_paths", return_value=paths):
                self.assertEqual(cli.install(args), 0)
                err = io.StringIO()
                boom = PermissionError(1, "Operation not permitted", str(paths.home / ".claude/settings.json"))
                with mock.patch.object(cli, "install_host_wiring", side_effect=boom), redirect_stderr(err), redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.install(args), 1)
                self.assertIn("FAIL: agents-inc repair", err.getvalue())
                self.assertIn("Operation not permitted", err.getvalue())
                self.assertIn("run `agents-inc repair` from a normal terminal", err.getvalue())  # #155 (b): names the sandbox cause
                marker = paths.state / "repair-failed.json"
                self.assertTrue(marker.is_file())
                report = check_install(paths, which=lambda *a, **k: '/x/claude', sandbox_probe=lambda: True)
                self.assertIn("WB_REPAIR_FAILED", report.codes)
                self.assertFalse(report.ready)
                self.assertEqual(cli.install(args), 0)
                self.assertFalse(marker.exists())
                self.assertNotIn("WB_REPAIR_FAILED", check_install(paths, which=lambda *a, **k: '/x/claude', sandbox_probe=lambda: True).codes)


class PackagedInstallTest(unittest.TestCase):
    def test_install_without_source_uses_package_data(self):
        import argparse
        from agents_inc.install import cli
        from unittest import mock
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            data = tmp / "data"
            for name in ("workerbee", "codex-bridge"):
                (data / "skills" / name).mkdir(parents=True); (data / "skills" / name / "SKILL.md").write_text("x")
            (data / "docs/governance").mkdir(parents=True); (data / "docs/governance/SCHEMA-3NF.md").write_text("s")
            home = tmp / "home"; (home / ".claude").mkdir(parents=True)
            paths = InstallPaths.for_home(home)
            args = argparse.Namespace(source=None, adopt_existing_workerbee=False, without_codex=True, no_host_wiring=False, yes=True)
            with mock.patch.object(cli, "_paths", return_value=paths), \
                 mock.patch.object(cli.datafiles, "repo_file", side_effect=lambda rel: data / rel):
                self.assertEqual(cli.install(args), 0)
            self.assertTrue(paths.receipt.exists())
            self.assertEqual((paths.state / "source-checkout").read_text().strip(), "packaged")
            self.assertTrue(any(paths.releases.glob("*/skills/workerbee/SKILL.md")))

