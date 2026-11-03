import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")

from agents_inc.install import cli
from agents_inc.install.discovery import install_skill_links
from agents_inc.install.paths import InstallPaths
from agents_inc.install.receipt import InstallReceipt

HASH = "a" * 64
OTHER = "b" * 64


def snapshot(root: Path):
    return sorted((str(p.relative_to(root)), os.readlink(p) if p.is_symlink() else p.is_dir()) for p in root.rglob("*"))


class UninstallSpec030Test(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.paths = InstallPaths.for_home(self.home)
        claude = mock.patch.object(cli, "_claude", return_value=None)
        self.claude_mock = claude.start(); self.addCleanup(claude.stop)
        patch = mock.patch.object(cli, "_paths", return_value=self.paths)
        patch.start(); self.addCleanup(patch.stop)

    def release(self, name=HASH, current=True):
        rel = self.paths.releases / name
        (rel / "skills").mkdir(parents=True)
        if current:
            self.paths.current.symlink_to(rel)
        return rel

    def receipt(self, owned=()):
        return InstallReceipt(HASH, Path(sys.executable), None, tuple(owned))

    def install(self, adopt_old=None):
        """Install skill links (optionally adopting a predecessor workerbee link) and save the receipt."""
        self.paths.claude_skills.mkdir(parents=True, exist_ok=True)
        if adopt_old is not None:
            adopt_old.mkdir(parents=True, exist_ok=True)
            (self.paths.claude_skills / "workerbee").symlink_to(adopt_old)
        receipt = install_skill_links(self.paths, self.paths.current, self.receipt(), adopt_existing_workerbee=adopt_old is not None)
        receipt.save_atomic(self.paths.receipt)
        return receipt

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["uninstall", *argv])
        return code, out.getvalue(), err.getvalue()

    def hash_dirs(self):
        if not self.paths.releases.is_dir():
            return []
        return [p.name for p in self.paths.releases.iterdir() if len(p.name) == 64]

    def test_adopt_predecessor_uninstall_clean(self):
        self.release()
        old = self.home / "old-workerbee"
        self.install(adopt_old=old)
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertEqual((self.paths.claude_skills / "workerbee").resolve(), old.resolve())
        self.assertEqual(self.hash_dirs(), [])

    def test_modified_link_conflict_lists_path(self):
        self.release()
        self.install()
        link = self.paths.claude_skills / "codex-bridge"
        link.unlink(); link.symlink_to("/elsewhere")
        code, _, err = self.run_cli()
        self.assertEqual(code, 1)
        lines = err.splitlines()
        self.assertIn("WB_CONFIG_CONFLICT", lines[0])
        self.assertIn(str(link), lines[1:])

    def test_dry_run_changes_nothing(self):
        self.release()
        self.install(adopt_old=self.home / "old-workerbee")
        before = snapshot(self.home)
        code, out, err = self.run_cli("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertEqual(snapshot(self.home), before)
        self.assertFalse(self.paths.journal.exists())
        self.assertFalse(self.paths.lock.exists())
        self.assertIn("would run: claude ", out)
        self.assertIn("would remove: ", out)
        self.claude_mock.assert_not_called()

    def test_non_hash_release_entry_survives(self):
        self.release()
        (self.paths.releases / "keepme").mkdir()
        self.install()
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertTrue((self.paths.releases / "keepme").is_dir())
        self.assertEqual(self.hash_dirs(), [])

    def test_current_release_kept_when_foreign_current(self):
        self.release(HASH, current=False)
        foreign = self.release(OTHER, current=True)
        self.install()
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertTrue(foreign.is_dir())
        self.assertFalse((self.paths.releases / HASH).exists())

    def test_missing_releases_dir_ok(self):
        self.receipt().save_atomic(self.paths.receipt)
        self.assertFalse(self.paths.releases.exists())
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
