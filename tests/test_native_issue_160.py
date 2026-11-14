import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from agents_inc.install import runtime


class Issue160Test(unittest.TestCase):
    def test_json_unavailable_request_user_input_explains_empty_failure(self):
        event = json.dumps({"type": "turn.failed", "error": {
            "message": "request_user_input is unavailable in Default mode"}})
        result = SimpleNamespace(stdout=event, stderr="", returncode=1)
        err = io.StringIO()
        with mock.patch.object(runtime, "load_model_map", return_value={"luna": "gpt-6-luna"}), \
                mock.patch.object(runtime.subprocess, "run", return_value=result), \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(runtime.Path, "is_file", return_value=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = runtime.run_codex("luna", "low", Path.cwd(), io.StringIO("work"),
                                   SimpleNamespace(codex_path="/fake/codex"),
                                   {"gpt-6-luna": ["low"]}, thread_out={},
                                   env={"TMPDIR": str(Path.cwd() / ".scratch/wave6")})
        self.assertEqual(rc, 1)
        self.assertIn("cause: the model asked the user a question", err.getvalue())


if __name__ == "__main__":
    unittest.main()
