"""Spec 048 US2: `agents-inc handles list|retire` over the per-session handles.json."""
import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from agents_inc.install import cli


def handle(hid, **over):
    h = {"id": hid, "provider": "gemini", "nickname": "gem", "slug": "gemini-x", "thread": f"/w/{hid}.thread", "cwd": "/w",
         "charsSent": 1200, "seen": 4, "ceiling": 800000, "state": "live", "restarts": 1, "lastRestartReason": "compaction",
         "history": [], "fingerprint": "deadbeef", "fingerprintLen": 10, "fingerprintChanged": False, "threadTotal": None, "n": 1, "used": True}
    h.update(over)
    return h


class HandlesCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = self.tmp.name
        self.dir = Path(self.cwd, ".scratch", "agents-inc-gem", "s1")
        self.dir.mkdir(parents=True)
        self.file = self.dir / "handles.json"
        self.file.write_text(json.dumps({"version": 1, "handles": {"a1": handle("a1"), "a2": handle("a2", charsSent=900000)}}))

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        env = {k: v for k, v in os.environ.items() if k != "SANDBOX_RUNTIME"}
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(["handles", *args, "--cwd", self.cwd])
            except SystemExit as e:
                code = e.code
        del env
        return code, out.getvalue(), err.getvalue()

    def test_list_text(self):
        code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        for text in ("a1", "a2", "gemini/gem", "live", "1200", "800000"):
            self.assertIn(text, out)

    def test_list_json(self):
        code, out, _ = self.run_cli("list", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(sorted(h["id"] for h in data["handles"]), ["a1", "a2"])
        self.assertEqual(data["session"], "s1")

    def test_session_defaults_to_the_newest_dir(self):
        newer = Path(self.cwd, ".scratch", "agents-inc-gem", "s2")
        newer.mkdir()
        (newer / "handles.json").write_text(json.dumps({"version": 1, "handles": {"b1": handle("b1")}}))
        later = time.time() + 5
        os.utime(newer, (later, later))
        _, out, _ = self.run_cli("list", "--json")
        self.assertEqual([h["id"] for h in json.loads(out)["handles"]], ["b1"])
        _, out, _ = self.run_cli("list", "--json", "--session", "s1")
        self.assertEqual(len(json.loads(out)["handles"]), 2)

    def test_retire_marks_state_and_prints_the_instruction(self):
        code, out, _ = self.run_cli("retire", "a1")
        self.assertEqual(code, 0)
        self.assertIn("retired", out)
        self.assertIn("new Agent", out)
        stored = json.loads(self.file.read_text())["handles"]
        self.assertEqual(stored["a1"]["state"], "retired")
        self.assertEqual(stored["a2"]["state"], "live")

    def test_retire_unknown_id_fails(self):
        code, _, err = self.run_cli("retire", "nope")
        self.assertEqual(code, 1)
        self.assertIn("nope", err)

    def test_corrupt_file_reports_without_a_traceback(self):
        self.file.write_text("{not json")
        code, out, err = self.run_cli("list")
        self.assertEqual(code, 1)
        self.assertIn("handles.json", err)
        self.assertNotIn("Traceback", out + err)

    def test_no_session_dir(self):
        self.file.unlink()
        self.dir.rmdir()
        code, _, err = self.run_cli("list")
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
