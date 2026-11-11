"""agents_inc.datafiles: checkout path, packaged fallback, error case. Temp trees only."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc import datafiles


class RepoFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_repo_root_holds_agents_inc(self):
        self.assertTrue((datafiles.repo_root() / "agents_inc" / "datafiles.py").is_file())

    def test_checkout_path_wins(self):
        want = datafiles.repo_root() / "skills" / "workerbee" / "SKILL.md"
        self.assertEqual(datafiles.repo_file("skills/workerbee/SKILL.md"), want)
        self.assertTrue(datafiles.repo_file("docs/governance/SCHEMA-3NF.md").is_file())

    def test_packaged_fallback(self):
        skills, docs = self.root / "pkg_skills", self.root / "pkg_docs"
        (skills / "codex-bridge" / "scripts").mkdir(parents=True)
        (skills / "codex-bridge" / "scripts" / "at_route.sh").write_text("hook")
        docs.mkdir()
        (docs / "SCHEMA-3NF.md").write_text("doc")
        trees = {"agents_inc._skills": skills, "agents_inc._docs": docs}
        empty_root = self.root / "site"
        empty_root.mkdir()
        with mock.patch.object(datafiles, "repo_root", return_value=empty_root), \
                mock.patch.object(datafiles.resources, "files", side_effect=lambda pkg: trees[pkg]):
            hook = datafiles.repo_file("skills/codex-bridge/scripts/at_route.sh")
            schema = datafiles.repo_file("docs/governance/SCHEMA-3NF.md")
        self.assertEqual(hook.read_text(), "hook")
        self.assertEqual(schema.read_text(), "doc")

    def test_missing_file_raises_with_context(self):
        empty_root = self.root / "site"
        empty_root.mkdir()
        with mock.patch.object(datafiles, "repo_root", return_value=empty_root), \
                mock.patch.object(datafiles.resources, "files", side_effect=ModuleNotFoundError("x")):
            with self.assertRaises(FileNotFoundError) as ctx:
                datafiles.repo_file("skills/workerbee/SKILL.md")
            self.assertIn("skills/workerbee/SKILL.md", str(ctx.exception))
            self.assertIn("pipx install --force agents-inc", str(ctx.exception))  # #155: pip fails under PEP 668
            with self.assertRaises(FileNotFoundError):
                datafiles.repo_file("README.md")


if __name__ == "__main__":
    unittest.main()
