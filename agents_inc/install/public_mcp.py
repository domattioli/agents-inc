"""Workspace-bound MCP adapter for the existing governed dispatch CLI.

Jobs belong to one server process. It never calls a provider or implements policy itself.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

MAX_FRAME = 65536
TOOLS = [
    {"name": "submit", "description": "Start a governed dispatch in the configured workspace.",
     "inputSchema": {"type": "object", "required": ["model", "slots"], "properties": {
         "model": {"type": "string"}, "slots": {"type": "object"}}}},
    {"name": "status", "description": "Get the state of a job started by this server.",
     "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}}},
    {"name": "result", "description": "Read a completed job's dispatch result.",
     "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}}},
    {"name": "cancel", "description": "Cancel a running dispatch owned by this server.",
     "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}}},
    {"name": "follow_up", "description": "Resume a completed dispatch session.",
     "inputSchema": {"type": "object", "required": ["job_id", "message"], "properties": {
         "job_id": {"type": "string"}, "message": {"type": "string"}}}},
]


class Session:
    def __init__(self, cwd: Path, allow_writes: bool = False):
        self.cwd = cwd.resolve(strict=True)
        if not self.cwd.is_dir():
            raise ValueError("workspace is not a directory")
        self.allow_writes = allow_writes
        self.root = Path(tempfile.mkdtemp(prefix="agents-inc-mcp-"))
        os.chmod(self.root, 0o700)
        self.jobs: dict[str, dict] = {}

    def _job(self, job_id):
        if not isinstance(job_id, str) or job_id not in self.jobs:
            raise ValueError("unknown job")
        return self.jobs[job_id]

    def _start(self, job: dict, args: list[str]):
        turn = job["turn"]
        out = (job["dir"] / f"turn-{turn}.stdout").open("wb")
        err = (job["dir"] / f"turn-{turn}.stderr").open("wb")
        try:
            job["process"] = subprocess.Popen([sys.executable, "-m", "agents_inc.install.cli", "dispatch", *args],
                                              cwd=str(self.cwd), stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                              start_new_session=True)
        finally:
            out.close()
            err.close()

    def _ensure_idle(self):
        if any(job["process"] is not None and job["process"].poll() is None for job in self.jobs.values()):
            raise ValueError("another job is running in this workspace session")

    def submit(self, model, slots):
        self._ensure_idle()
        if not isinstance(model, str) or not model or not isinstance(slots, dict):
            raise ValueError("model and slots are required")
        if slots.get("TASK_ACCESS") not in ("read", "write"):
            raise ValueError("TASK_ACCESS must be explicitly read or write")
        if slots["TASK_ACCESS"] == "write" and not self.allow_writes:
            raise ValueError("server was not started with --allow-writes")
        # Gates run on the host, outside the worker sandbox, and may mutate files.
        if not self.allow_writes and (slots.get("GATES") or slots.get("BASH_ALLOW")):
            raise ValueError("host command grants require --allow-writes")
        if slots["TASK_ACCESS"] == "write":
            scope = slots.get("FILES_IN_SCOPE")
            if not isinstance(scope, list) or not scope:
                raise ValueError("write scope must be a nonempty array of relative paths")
            for item in scope:
                if not isinstance(item, str) or not item or item.lower().startswith("none"):
                    raise ValueError("invalid write scope")
                path = Path(item)
                if path.is_absolute() or ".." in path.parts or any(c in item for c in "*?["):
                    raise ValueError("write scope must contain concrete workspace-relative paths")
                if not (self.cwd / path).resolve().is_relative_to(self.cwd):
                    raise ValueError("write scope resolves outside workspace")
        # Apply dispatch's credential/control screens before saving the submitted slots.
        from . import dispatch
        if dispatch.credential_hit(slots, str(self.cwd)) or dispatch.control_char_hit(slots):
            raise ValueError("slots contain prohibited credentials or control characters")
        job_id = uuid.uuid4().hex
        folder = self.root / job_id
        folder.mkdir(mode=0o700)
        slots_path = folder / "slots.json"
        slots_path.write_text(json.dumps(slots), encoding="utf-8")
        os.chmod(slots_path, 0o600)
        runs = folder / "runs"
        job = {"dir": folder, "runs": runs, "turn": 1, "process": None}
        self.jobs[job_id] = job
        try:
            self._start(job, ["--slots", str(slots_path), "--model", model, "--cwd", str(self.cwd), "--run-dir", str(runs)])
        except Exception:
            self.jobs.pop(job_id, None)
            raise
        return {"job_id": job_id, "status": "running"}

    @staticmethod
    def _run_dir(job):
        root = job["runs"]
        if not root.is_dir():
            return None
        found = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]
        return found[0] if len(found) == 1 else None

    def status(self, job_id):
        job = self._job(job_id)
        rc = job["process"].poll()
        return {"job_id": job_id, "status": "running" if rc is None else "finished", "exit_code": rc, "turn": job["turn"]}

    def result(self, job_id):
        job = self._job(job_id)
        status = self.status(job_id)
        if status["status"] != "finished":
            return status
        for name in ("stdout", "stderr"):
            path = job["dir"] / f"turn-{job['turn']}.{name}"
            status[name] = path.read_text(encoding="utf-8", errors="replace")[-100000:]
        run_dir = self._run_dir(job)
        if run_dir:
            report = run_dir / ("stdout.md" if job["turn"] == 1 else f"stdout.{job['turn'] - 1}.md")
            if report.is_file() and not report.is_symlink():
                status["report"] = report.read_text(encoding="utf-8", errors="replace")[-100000:]
        return status

    def cancel(self, job_id):
        job = self._job(job_id)
        if job["process"].poll() is not None:
            return self.status(job_id)
        run_dir = self._run_dir(job)
        if run_dir is None:
            # The subprocess is ours and has not produced a run directory yet.
            job["process"].terminate()
            return {"job_id": job_id, "status": "cancelling"}
        proc = subprocess.run([sys.executable, "-m", "agents_inc.install.cli", "dispatch", "--cancel", str(run_dir)],
                              cwd=str(self.cwd), capture_output=True, text=True, timeout=10, check=False)
        state = "cancel_requested" if proc.returncode == 0 and "cancelled group" in proc.stdout else "not_cancelled"
        return {"job_id": job_id, "status": state, "exit_code": proc.returncode, "detail": proc.stdout[-2000:]}

    def follow_up(self, job_id, message):
        job = self._job(job_id)
        if job["process"].poll() is None:
            raise ValueError("job is still running")
        self._ensure_idle()
        if not isinstance(message, str) or not message.strip() or len(message) > MAX_FRAME:
            raise ValueError("message must be nonempty and bounded")
        run_dir = self._run_dir(job)
        if run_dir is None:
            raise ValueError("dispatch did not create a resumable run")
        job["turn"] += 1
        try:
            self._start(job, ["--resume", str(run_dir), "--message", message])
        except Exception:
            job["turn"] -= 1
            raise
        return {"job_id": job_id, "status": "running", "turn": job["turn"]}


def handle(session: Session, message):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
    method, ident = message.get("method"), message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        value = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                 "serverInfo": {"name": "agents-inc", "version": "1"}}
    elif method == "ping":
        value = {}
    elif method == "tools/list":
        value = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params", {})
        if not isinstance(params, dict):
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "invalid params"}}
        name, args = params.get("name"), params.get("arguments", {})
        handlers = {"submit": session.submit, "status": session.status, "result": session.result,
                    "cancel": session.cancel, "follow_up": session.follow_up}
        try:
            if name not in handlers or not isinstance(args, dict):
                raise ValueError("unknown tool or invalid arguments")
            data = handlers[name](**args)
            value = {"content": [{"type": "text", "text": json.dumps(data)}], "isError": False}
        except (ValueError, TypeError, OSError, subprocess.SubprocessError) as exc:
            value = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": ident, "result": value} if ident is not None else None


def serve(cwd: Path, allow_writes: bool, stdin, stdout):
    session = Session(cwd, allow_writes)
    while True:
        line = stdin.buffer.readline(MAX_FRAME + 1) if hasattr(stdin, "buffer") else stdin.readline(MAX_FRAME + 1)
        if not line:
            return 0
        if len(line) > MAX_FRAME or not line.endswith(b"\n" if isinstance(line, bytes) else "\n"):
            raise ValueError("MCP frame exceeds limit or is incomplete")
        try:
            reply = handle(session, json.loads(line))
        except (ValueError, UnicodeDecodeError):
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()
