"""Fake provider HTTP server for spec 038 native adapters (T002).

Stdlib only. Serves scripted replies in order and logs every request (method, path, headers, body) so a test can check
what was sent, including that no key leaked into a path or body. Binding a socket can be refused in a sandbox (D68 R1):
`start()` raises unittest.SkipTest on PermissionError.

    srv = FakeProvider([Reply(200, {"text": "hi"}), Reply(429, {"error": "quota"})])
    srv.start()
    try:
        ... call srv.url ...
    finally:
        srv.stop()
"""
from __future__ import annotations

import json
import threading
import unittest
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Reply:
    status: int = 200
    body: object = field(default_factory=dict)  # dict/list -> JSON; str -> sent as text
    headers: dict = field(default_factory=dict)


@dataclass
class Request:
    method: str
    path: str
    headers: dict
    body: bytes

    def json(self) -> object:
        return json.loads(self.body.decode() or "null")


class FakeProvider:
    """Scripted replies, one per request; after the script runs out every request gets `fallback`."""

    def __init__(self, replies: list[Reply] | None = None, fallback: Reply | None = None):
        self.replies = list(replies or [])
        self.fallback = fallback or Reply(500, {"error": "fake provider: script exhausted"})
        self.requests: list[Request] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("fake provider not started")
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def _next(self, req: Request) -> Reply:
        with self._lock:
            self.requests.append(req)
            return self.replies.pop(0) if self.replies else self.fallback

    def start(self) -> "FakeProvider":
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                reply = fake._next(Request(self.command, self.path, dict(self.headers.items()), body))
                data = reply.body if isinstance(reply.body, str) else json.dumps(reply.body)
                raw = data.encode()
                self.send_response(reply.status)
                ctype = "text/plain" if isinstance(reply.body, str) else "application/json"
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(raw)))
                for k, v in reply.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(raw)

            do_GET = _serve
            do_POST = _serve

            def log_message(self, *args) -> None:  # keep test output clean
                pass

        try:
            self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except PermissionError as exc:  # sandboxed: no socket bind (D68 R1)
            raise unittest.SkipTest(f"fake provider: bind refused ({exc})") from exc
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def __enter__(self) -> "FakeProvider":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
