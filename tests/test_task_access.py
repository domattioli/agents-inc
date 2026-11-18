"""Explicit task access is independent of the chosen model."""
import unittest
from agents_inc.install import dispatch

schema = dispatch._load("dispatch_schema")


class TaskAccessTest(unittest.TestCase):
    def test_read_rejects_widening(self):
        for extra in ({"CODEX_WRITE": "yes"}, {"PERMISSION_MODE": "acceptEdits"},
                      {"BASH_ALLOW": "python3"}):
            with self.subTest(extra=extra):
                self.assertTrue(schema.validate_record({"TASK_ACCESS": "read", **extra}))

    def test_write_requires_scope(self):
        self.assertTrue(schema.validate_record({"TASK_ACCESS": "write"}))
        self.assertTrue(schema.validate_record({"TASK_ACCESS": "write", "FILES_IN_SCOPE": ["none -- no files"]}))
        self.assertEqual(schema.validate_record({"TASK_ACCESS": "write", "FILES_IN_SCOPE": ["src/a.py"]}), [])

    def test_unknown_access_rejected_and_legacy_accepted(self):
        self.assertTrue(schema.validate_record({"TASK_ACCESS": "maybe"}))
        self.assertEqual(schema.validate_record({}), [])

    def test_read_grants_deny_mutation_and_shell(self):
        allowed, denied = dispatch.tool_grants({}, [], [], "/tmp/run", read_only=True)
        self.assertEqual(allowed, list(dispatch.READ_ONLY_TOOLS))
        self.assertIn("Bash", denied)

from unittest import mock
from tests.test_dispatch_snapshot_trust import DispatchBase, ok_launch


class AccessDispatchTest(DispatchBase):
    def test_luna_read_gets_read_only_tools(self):
        calls = []
        def launch(*args, **kwargs):
            calls.append(kwargs)
            return ok_launch()(*args, **kwargs)
        rc, out, _ = self.dispatch(launch, model="luna", slots=self.slots(TASK_ACCESS="read"))
        self.assertEqual(rc, 0, out)
        self.assertTrue(calls[0]["read_only"])
        self.assertTrue(calls[0]["read_tools"])
        self.assertNotIn("codex_write", calls[0])

    def test_read_grant_is_pinned_and_resume_cannot_widen(self):
        calls = []
        def launch(*args, **kwargs):
            calls.append((args, kwargs))
            return ok_launch()(*args, **kwargs)
        rc, out, _ = self.dispatch(launch, slots=self.slots(TASK_ACCESS="read"))
        self.assertEqual(rc, 0, out)
        self.assertTrue(calls[0][1]["read_only"])
        self.assertEqual(calls[0][0][6], "default")
        spec_path = self.run_dir() / "run.json"
        import json
        spec = json.loads(spec_path.read_text())
        spec["permission_mode"] = "acceptEdits"
        spec["codex_write"] = True
        spec_path.write_text(json.dumps(spec))
        with mock.patch.object(dispatch, "launch", side_effect=launch):
            rc, out, _ = self.main("--resume", self.run_dir().name, "--message", "continue", "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        self.assertTrue(calls[-1][1]["read_only"])
        self.assertNotIn("codex_write", calls[-1][1])
        self.assertEqual(calls[-1][0][6], "default")
