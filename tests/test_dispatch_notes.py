"""Spec 042 Phase 3 (US3): dispatch status notes (FR-021a, FR-030, FR-031)."""
from __future__ import annotations
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")

from agents_inc.install import cli, dispatch
from tests.test_doctor_items import ItemsBase


class SourceUncommittedNoteTest(ItemsBase):
    git = True

    def _dispatch(self):
        err = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), mock.patch.object(dispatch, "run", return_value=0) as run, \
             contextlib.redirect_stderr(err):
            code = cli.main(["dispatch", "--slots", "s.json", "--model", "haiku"])
        return code, run, err.getvalue()

    def test_uncommitted_source_prints_once_and_does_not_block(self):
        (self.source / "agents_inc" / "models.json").write_text('{"x": 1}')
        code, run, err = self._dispatch()
        self.assertEqual(code, 0)
        run.assert_called_once()
        self.assertEqual(err.count("WB_SOURCE_UNCOMMITTED"), 1)

    def test_clean_source_prints_nothing(self):
        code, run, err = self._dispatch()
        self.assertEqual(code, 0)
        self.assertNotIn("WB_SOURCE_UNCOMMITTED", err)

    def test_stored_install_match_is_marked_not_verified_now_with_age(self):
        import time
        old = time.time() - 2 * 3600 - 30
        record = self.paths.state / "source-git.json"
        os.utime(record, (old, old))
        (self.source / "agents_inc" / "models.json").write_text('{"x": 1}')
        _, _, err = self._dispatch()
        self.assertIn("not verified now", err)
        self.assertIn("age 2h", err)


class MirrorNoteTest(unittest.TestCase):
    def test_no_home_repo_note_says_what_was_skipped_and_that_nothing_was_lost(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as raw, mock.patch.object(dispatch, "resolve_home_repo", return_value=None), \
                contextlib.redirect_stderr(err):
            run_dir = Path(raw)
            self.assertIsNone(dispatch._mirror({"cwd": raw}, run_dir, None, "p"))
        text = err.getvalue()
        self.assertIn("run spec not mirrored: no home repo", text)
        self.assertIn("run.json stays in", text)
        self.assertIn("no record lost", text)
        self.assertIn("no action needed", text)

    def test_other_mirror_error_note_has_the_same_three_facts(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as raw, mock.patch.object(dispatch, "_mirror", return_value="OSError: disk"), \
                mock.patch.object(dispatch, "_write_json"), contextlib.redirect_stderr(err):
            dispatch._mirror_and_note({"cwd": raw}, Path(raw), None, "p")
        text = err.getvalue()
        self.assertIn("run spec not mirrored: OSError: disk", text)
        self.assertIn("no record lost", text)
        self.assertIn("run.json stays in", text)


if __name__ == "__main__":
    unittest.main()
