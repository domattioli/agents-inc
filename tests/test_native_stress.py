"""Spec 038 T028: the offline stress driver passes one run of each scenario, and its fake server sees no request at
session start (SC-006)."""
import contextlib
import io
import os
import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import native_stress  # noqa: E402


class NativeStress(unittest.TestCase):
    def setUp(self):
        try: socket.socket().bind(("127.0.0.1", 0))
        except PermissionError as exc: raise unittest.SkipTest(f"bind refused ({exc})")

    def test_one_run_of_each_scenario_passes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = native_stress.main(["--src", str(ROOT), "--r", "1"])
        text = out.getvalue()
        self.assertEqual(code, 0, text)
        self.assertIn("PASS 5/5", text)
        for line in text.splitlines()[1:6]: self.assertEqual(line.split()[4], "0", line)  # start column

    def test_fake_model_reports_only_after_every_file(self):
        a = native_stress.Fake.answer
        self.assertEqual(a("TASK: count lines of a.txt,b.txt\nRESULT wc -l a.txt -> 173\n")["tools"][0]["input"]["command"], "wc -l b.txt")
        self.assertEqual(a("TASK: count lines of a.txt\nRESULT wc -l a.txt -> 173\n"), {"say": "A=173", "tools": []})
        self.assertEqual(a("probe")["tools"][0]["name"], "Read")


if __name__ == "__main__":
    unittest.main()
