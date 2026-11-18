"""Spec 042 FR-010: dispatch warns before launch when a gate can pass without the run having done anything.
The warning never refuses the run. Writes only to temp dirs."""
from __future__ import annotations
import sys
import unittest

from tests.test_dispatch_grants import GrantsBase, setUpModule, tearDownModule  # noqa: F401


class GateWeakTest(GrantsBase):
    def _warned(self, argv):
        rc, out, err = self._dispatch(GATES=[{"argv": argv}])
        self.assertNotIn("refused", out, out)
        self.assertIn(self._spec()["outcome"], ("green", "red", "unverified"), out + err)
        return "warning: gate-weak" in err, err

    def test_existence_gates_on_a_preexisting_path_warn(self):
        for form in (["test", "-s"], ["test", "-e"], ["test", "-f"], ["ls"]):
            with self.subTest(form=form):
                self.tearDown(), self.setUp()
                existing = self.root / "already-there.txt"
                existing.write_text("content\n", encoding="utf-8")
                self.assertTrue(existing.is_file())
                warned, err = self._warned(form + [str(existing)])
                self.assertTrue(warned, err)

    def test_relative_path_is_resolved_against_the_run_cwd(self):
        (self.repo / "present.txt").write_text("x\n", encoding="utf-8")
        warned, err = self._warned(["test", "-s", "present.txt"])
        self.assertTrue(warned, err)

    def test_path_that_does_not_exist_yet_does_not_warn(self):
        warned, err = self._warned(["test", "-s", str(self.root / "to-be-written.txt")])
        self.assertFalse(warned, err)

    def test_a_real_test_command_does_not_warn(self):
        warned, err = self._warned([sys.executable, "-m", "unittest", "--help"])
        self.assertFalse(warned, err)

    def test_the_warning_never_refuses_the_run(self):
        existing = self.root / "already-there.txt"
        existing.write_text("content\n", encoding="utf-8")
        rc, out, err = self._dispatch(GATES=[{"argv": ["test", "-s", str(existing)]}])
        self.assertIn("warning: gate-weak", err)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self._spec()["outcome"], "green")


if __name__ == "__main__":
    unittest.main()
