"""F1: SANDBOX_RUNTIME dispatch probes api.anthropic.com through HTTPS_PROXY instead of refusing outright."""
import base64
import socket
import socketserver
import threading
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch


def _proxy(reply: bytes, seen: list):
    class H(socketserver.BaseRequestHandler):
        def handle(self):
            data = b""
            while b"\r\n\r\n" not in data:
                c = self.request.recv(1024)
                if not c:
                    break
                data += c
            seen.append(data.decode())
            self.request.sendall(reply)
    try:
        srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    except PermissionError:
        raise unittest.SkipTest("local bind not permitted")
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class ProbeTest(unittest.TestCase):
    def _srv(self, reply):
        seen = []
        srv = _proxy(reply, seen)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv, seen

    def test_200_reachable_with_auth(self):
        srv, seen = self._srv(b"HTTP/1.1 200 Connection established\r\n\r\n")
        env = {"HTTPS_PROXY": f"http://u:p@127.0.0.1:{srv.server_address[1]}"}
        self.assertTrue(dispatch.api_reachable(env))
        self.assertIn("CONNECT api.anthropic.com:443", seen[0])
        self.assertIn("Basic " + base64.b64encode(b"u:p").decode(), seen[0])

    def test_403_unreachable(self):
        srv, _ = self._srv(b"HTTP/1.1 403 Forbidden\r\n\r\n")
        self.assertFalse(dispatch.api_reachable({"https_proxy": f"http://127.0.0.1:{srv.server_address[1]}"}))

    def test_no_proxy_and_dead_port_unreachable(self):
        self.assertFalse(dispatch.api_reachable({}))
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", 0))
        except PermissionError:
            self.skipTest("local bind not permitted")
        port = s.getsockname()[1]
        s.close()
        self.assertFalse(dispatch.api_reachable({"HTTPS_PROXY": f"http://127.0.0.1:{port}"}, timeout=0.5))


class LaunchBranchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def _launch(self, kind, model, reachable):
        env = {"SANDBOX_RUNTIME": "1", "PATH": "/usr/bin"}
        proc = mock.MagicMock()
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch.object(dispatch, "api_reachable", return_value=reachable), \
             mock.patch.object(dispatch.subprocess, "Popen", return_value=proc) as popen, \
             mock.patch.object(dispatch, "_stream_run", return_value=(0, "", "")):
            try:
                dispatch.launch(kind, model, None, self.dir, "p", self.dir)
            except dispatch.CallerSandboxed as exc:
                return exc, None
            return None, popen.call_args[0][0] if popen.called else None

    def test_pass_claude_adds_settings_and_notes(self):
        exc, argv = self._launch("claude", "sonnet", True)
        self.assertIsNone(exc)
        self.assertIn("--settings", argv)
        self.assertEqual(argv.count("--settings"), 1)
        self.assertEqual(dispatch._SANDBOX_NOTE, {"caller_sandbox": "claude-code", "api": "reachable"})

    def test_pass_codex_refused(self):
        exc, _ = self._launch("codex", "luna", True)
        self.assertEqual(exc.code, "caller-sandboxed-codex")
        self.assertIn("rc 71", exc.fix)

    def test_fail_refused_with_both_routes(self):
        exc, _ = self._launch("claude", "sonnet", False)
        self.assertEqual(exc.code, "caller-sandboxed")
        self.assertIn("allowedDomains", dispatch.SANDBOX_FIX)
        self.assertIn("one plain command", dispatch.SANDBOX_FIX)

    def test_no_settings_when_not_sandboxed(self):
        proc = mock.MagicMock()
        with mock.patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True), \
             mock.patch.object(dispatch.subprocess, "Popen", return_value=proc) as popen, \
             mock.patch.object(dispatch, "_stream_run", return_value=(0, "", "")):
            dispatch.launch("claude", "sonnet", None, self.dir, "p", self.dir)
        self.assertNotIn("--settings", popen.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
