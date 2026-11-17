"""Spec 042 FR-005, FR-006: pre_dispatch_snapshot.py verify separates changed in-scope paths (`CHANGED `) from changed
paths outside the allow list (`OUTSIDE `). Only an outside change makes the exit status nonzero. Temp repositories only."""
from __future__ import annotations
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/workerbee/scripts/pre_dispatch_snapshot.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo, check=True,
                   capture_output=True)


class SnapshotOutsideTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.assertTrue(self.repo.is_dir())
        _git(self.repo, "init", "-q")
        (self.repo / "scope").mkdir()
        for name in ("scope/a.py", "scope/b.py", "other.txt"):
            (self.repo / name).write_text("v1\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "init")
        self.snap = self.root / "snap.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo, capture_output=True, text=True)

    def _capture(self):
        res = self._run("capture", str(self.snap))
        self.assertEqual(res.returncode, 0, res.stderr)

    def _verify(self, *allow: str) -> subprocess.CompletedProcess:
        args = ["verify", str(self.snap), "--scope-aware"]
        for a in allow:
            args += ["--allow", a]
        return self._run(*args)

    def _lines(self, res, prefix):
        return sorted(ln[len(prefix):] for ln in res.stdout.splitlines() if ln.startswith(prefix))

    def test_in_scope_change_prints_changed_and_exits_zero(self):
        (self.repo / "scope/a.py").write_text("v2\n", encoding="utf-8")
        self._capture()
        (self.repo / "scope/a.py").write_text("v3\n", encoding="utf-8")
        res = self._verify("scope")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(self._lines(res, "CHANGED "), ["scope/a.py"])
        self.assertEqual(self._lines(res, "OUTSIDE "), [])

    def test_outside_change_prints_outside_and_exits_nonzero(self):
        self._capture()
        (self.repo / "other.txt").write_text("v2\n", encoding="utf-8")
        (self.repo / "scope/a.py").write_text("v2\n", encoding="utf-8")
        res = self._verify("scope")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertEqual(self._lines(res, "OUTSIDE "), ["other.txt"])
        self.assertNotIn("CHANGED other.txt", res.stdout)

    def test_new_in_scope_file_in_new_untracked_directory_prints_changed(self):
        self._capture()
        (self.repo / "scope/newdir").mkdir()
        (self.repo / "scope/newdir/n.py").write_text("x\n", encoding="utf-8")
        res = self._verify("scope")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(self._lines(res, "CHANGED "), ["scope/newdir/n.py"])
        legacy = self._run("verify", str(self.snap), "--allow", "scope")  # legacy default output unchanged
        self.assertEqual(legacy.stdout, "UNCHANGED outside allowed paths\n")

    def test_dirty_in_scope_file_that_did_not_change_prints_nothing(self):
        (self.repo / "scope/b.py").write_text("dirty before launch\n", encoding="utf-8")
        self._capture()
        res = self._verify("scope")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(self._lines(res, "CHANGED "), [])
        self.assertEqual(self._lines(res, "OUTSIDE "), [])

    def test_untouched_tree_reports_nothing_changed(self):
        self._capture()
        res = self._verify("scope")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("UNCHANGED", res.stdout)

    def test_empty_allow_list_makes_every_change_outside(self):
        self._capture()
        (self.repo / "scope/a.py").write_text("v2\n", encoding="utf-8")
        res = self._verify()
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertEqual(self._lines(res, "OUTSIDE "), ["scope/a.py"])


if __name__ == "__main__":
    unittest.main()
