"""Regression tests for pre_dispatch_snapshot.py path resolution."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = os.environ.get(
    "SNAPSHOT_SCRIPT",
    str(Path(__file__).resolve().parents[1] / "scripts" / "pre_dispatch_snapshot.py"),
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _run(cwd, *args):
    return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd,
                          capture_output=True, text=True)


class SnapshotPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "t")
        _git(self.repo, "config", "core.quotepath", "true")
        self.snap = str(self.repo.parent / (self.repo.name + "-snap.json"))

    def tearDown(self):
        self.tmp.cleanup()
        if os.path.exists(self.snap):
            os.remove(self.snap)

    def _commit(self, rel):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("v1\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "init")
        return p

    def test_subdir_capture_detects_second_edit(self):
        f = self._commit("sub/f")
        f.write_text("v2\n", encoding="utf-8")
        cwd = self.repo / "sub"
        self.assertEqual(_run(cwd, "capture", self.snap).returncode, 0)
        f.write_text("v3\n", encoding="utf-8")
        r = _run(cwd, "verify", self.snap)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CHANGED sub/f", r.stdout)

    def test_non_ascii_dirty_file_detected(self):
        f = self._commit("café.txt")
        f.write_text("v2\n", encoding="utf-8")
        self.assertEqual(_run(self.repo, "capture", self.snap).returncode, 0)
        f.write_text("v3\n", encoding="utf-8")
        r = _run(self.repo, "verify", self.snap)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CHANGED café.txt", r.stdout)

    def test_unchanged_tree_verifies_clean(self):
        f = self._commit("café.txt")
        f.write_text("v2\n", encoding="utf-8")
        self.assertEqual(_run(self.repo, "capture", self.snap).returncode, 0)
        r = _run(self.repo, "verify", self.snap)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_allowed_file_in_new_directory_verifies_clean(self):
        self._commit("f")
        self.assertEqual(_run(self.repo, "capture", self.snap).returncode, 0)
        (self.repo / "new").mkdir()
        (self.repo / "new" / "out.md").write_text("x\n", encoding="utf-8")
        r = _run(self.repo, "verify", self.snap, "--allow", "new/out.md")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _two_new_files(self):
        self._commit("f")
        self.assertEqual(_run(self.repo, "capture", self.snap).returncode, 0)
        (self.repo / "a.md").write_text("x\n", encoding="utf-8")
        (self.repo / "b.md").write_text("x\n", encoding="utf-8")

    def test_allow_accepts_multiple_paths_after_one_flag(self):
        self._two_new_files()
        r = _run(self.repo, "verify", self.snap, "--allow", "a.md", "b.md")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("UNCHANGED", r.stdout)

    def test_allow_repeated_flag_still_works(self):
        self._two_new_files()
        r = _run(self.repo, "verify", self.snap, "--allow", "a.md", "--allow", "b.md")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_allow_without_path_is_usage_error(self):
        self._two_new_files()
        self.assertEqual(_run(self.repo, "verify", self.snap, "--allow").returncode, 2)
        r = _run(self.repo, "verify", self.snap, "--allow", "--allow", "a.md")
        self.assertEqual(r.returncode, 2)

    def test_unallowed_file_in_new_directory_detected(self):
        self._commit("f")
        self.assertEqual(_run(self.repo, "capture", self.snap).returncode, 0)
        (self.repo / "new").mkdir()
        (self.repo / "new" / "out.md").write_text("x\n", encoding="utf-8")
        (self.repo / "new" / "stray.md").write_text("x\n", encoding="utf-8")
        r = _run(self.repo, "verify", self.snap, "--allow", "new/out.md")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CHANGED new/stray.md", r.stdout)
        self.assertNotIn("CHANGED new/\n", r.stdout)

    def test_ignored_at_capture_stays_ignored_without_global_excludes(self):
        self._commit("f")
        excludes = self.repo.parent / (self.repo.name + "-excludes")
        excludes.write_text("local.json\n", encoding="utf-8")
        _git(self.repo, "config", "core.excludesFile", str(excludes))
        (self.repo / "local.json").write_text("x\n", encoding="utf-8")
        self.assertEqual(_run(self.repo, "capture", self.snap).returncode, 0)
        _git(self.repo, "config", "--unset", "core.excludesFile")  # the sandbox view: no global excludes
        r = _run(self.repo, "verify", self.snap)
        excludes.unlink()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class RepoFlagTests(unittest.TestCase):
    """#92: verify finds the repo from --repo or the snapshot, not from cwd."""

    _base_setup = SnapshotPathTests.setUp
    tearDown = SnapshotPathTests.tearDown
    _commit = SnapshotPathTests._commit

    def setUp(self):
        self._base_setup()
        self._commit("f")
        self.assertEqual(_run(self.repo, "capture", self.snap).returncode, 0)
        self.outside = tempfile.TemporaryDirectory()
        self.addCleanup(self.outside.cleanup)

    def test_capture_records_repo(self):
        import json
        with open(self.snap, encoding="utf-8") as fh:
            recorded = json.load(fh)["repo"]
        self.assertEqual(Path(recorded).resolve(), self.repo.resolve())

    def test_verify_outside_repo_with_repo_flag(self):
        r = _run(self.outside.name, "verify", self.snap, "--repo", str(self.repo))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_verify_outside_repo_uses_recorded_repo(self):
        r = _run(self.outside.name, "verify", self.snap)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (self.repo / "f").write_text("v2\n", encoding="utf-8")
        r = _run(self.outside.name, "verify", self.snap)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CHANGED f", r.stdout)

    def test_repo_flag_after_allow_group(self):
        (self.repo / "a.md").write_text("x\n", encoding="utf-8")
        r = _run(self.outside.name, "verify", self.snap, "--allow", "a.md", "--repo", str(self.repo))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_repo_flag_without_value_is_usage_error(self):
        self.assertEqual(_run(self.repo, "verify", self.snap, "--repo").returncode, 2)
        self.assertEqual(_run(self.repo, "verify", self.snap, "--repo", "--allow", "a.md").returncode, 2)


class UnreadableTests(unittest.TestCase):
    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads chmod 000 files")
    def test_unreadable_file_recorded_and_verified(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _git(repo, "init", "-q")
            _git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t",
                 "commit", "-q", "--allow-empty", "-m", "init")
            secret = repo / "secret.txt"
            secret.write_text("s\n", encoding="utf-8")
            secret.chmod(0)
            snap = str(repo.parent / (repo.name + "-snap.json"))
            try:
                r = _run(repo, "capture", snap)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                r = _run(repo, "verify", snap)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("UNREADABLE secret.txt", r.stdout)
                (repo / "ok.txt").write_text("a\n", encoding="utf-8")
                _run(repo, "capture", snap)
                (repo / "ok.txt").write_text("b\n", encoding="utf-8")
                r = _run(repo, "verify", snap)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("CHANGED ok.txt", r.stdout)
                self.assertIn("UNREADABLE secret.txt", r.stdout)
            finally:
                secret.chmod(0o644)
                if os.path.exists(snap):
                    os.remove(snap)


if __name__ == "__main__":
    unittest.main()
