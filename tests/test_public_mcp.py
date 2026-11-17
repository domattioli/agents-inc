import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents_inc.install import public_mcp


class Process:
    def __init__(self, *args, **kwargs):
        self.returncode = None
        self.args = args
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15


class PublicMcpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.session = public_mcp.Session(Path(self.tmp.name))

    def test_protocol_lists_tools_and_rejects_bad_call(self):
        listing = public_mcp.handle(self.session, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual({t['name'] for t in listing['result']['tools']},
                         {'submit', 'status', 'result', 'cancel', 'follow_up'})
        bad = public_mcp.handle(self.session, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": []})
        self.assertIn("error", bad)

    def test_read_only_server_rejects_write_and_host_gates(self):
        with self.assertRaises(ValueError):
            self.session.submit('haiku', {'TASK_ACCESS': 'write', 'FILES_IN_SCOPE': ['a.py']})
        with self.assertRaises(ValueError):
            self.session.submit('haiku', {'TASK_ACCESS': 'read', 'GATES': ['touch x']})
        with self.assertRaises(ValueError):
            self.session.submit('haiku', {})

    def test_scoped_write_cannot_escape_workspace(self):
        self.session.allow_writes = True
        for name in ('../outside', '/tmp/outside', '*.py', 'none'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.session.submit('haiku', {'TASK_ACCESS': 'write', 'FILES_IN_SCOPE': [name]})
        (Path(self.tmp.name) / 'escape').symlink_to('/tmp')
        with self.assertRaises(ValueError):
            self.session.submit('haiku', {'TASK_ACCESS': 'write', 'FILES_IN_SCOPE': ['escape/out']})

    @patch('agents_inc.install.public_mcp.subprocess.Popen', Process)
    def test_submit_status_cancel_and_unknown_job(self):
        result = self.session.submit('haiku', {'TASK_ACCESS': 'read'})
        job = result['job_id']
        self.assertEqual(self.session.status(job)['status'], 'running')
        with self.assertRaises(ValueError):
            self.session.submit('haiku', {'TASK_ACCESS': 'read'})
        self.assertEqual(self.session.result(job)['status'], 'running')
        with self.assertRaises(ValueError):
            self.session.follow_up(job, 'continue')
        self.assertEqual(self.session.cancel(job)['status'], 'cancelling')
        self.assertEqual(self.session.status(job)['status'], 'finished')
        self.assertTrue(self.session._job(job)['process'].terminated)
        with self.assertRaises(ValueError):
            self.session.status('../other')

    @patch('agents_inc.install.public_mcp.subprocess.Popen', Process)
    def test_completed_result_and_follow_up(self):
        job_id = self.session.submit('haiku', {'TASK_ACCESS': 'read'})['job_id']
        job = self.session._job(job_id)
        runs = job['runs'] / 'run-1'
        runs.mkdir(parents=True)
        (runs / 'stdout.md').write_text('worker report')
        (job['dir'] / 'turn-1.stdout').write_text('dispatch complete')
        job['process'].returncode = 4
        result = self.session.result(job_id)
        self.assertEqual(result['exit_code'], 4)
        self.assertEqual(result['report'], 'worker report')
        self.assertEqual(self.session.follow_up(job_id, 'continue')['turn'], 2)
        self.assertEqual(self.session.status(job_id)['status'], 'running')

    def test_real_subprocess_reports_rejected_model(self):
        import time
        # Run from the checkout so the child can import the same package.
        session = public_mcp.Session(Path(__file__).resolve().parents[1])
        job_id = session.submit("not-a-model", {"TASK_ACCESS": "read"})["job_id"]
        deadline = time.monotonic() + 10
        while session.status(job_id)["status"] == "running" and time.monotonic() < deadline:
            time.sleep(.02)
        result = session.result(job_id)
        self.assertEqual(result["status"], "finished")
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("not supported", result["stdout"])

    def test_stdio_handshake(self):
        inp = io.StringIO(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}) + '\n')
        out = io.StringIO()
        self.assertEqual(public_mcp.serve(Path(self.tmp.name), False, inp, out), 0)
        self.assertEqual(json.loads(out.getvalue())['result']['serverInfo']['name'], 'agents-inc')
