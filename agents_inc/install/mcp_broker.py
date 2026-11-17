"""D51 MCP transport: a stdio MCP server that fronts the dispatch broker for a Codex Lead.

Started by `agents-inc run --lead <run-dir>` as a child of the Codex process:
    python3 mcp_broker.py --run-dir <dir>
It shares validation and processing with the file broker (dispatch._validate_fields, _run_validated).
The run directory is broker-owned: no inbox, the Lead needs no write access. Standard library only.
D54: a Worker turn runs in a thread, so dispatch, resume and wait return early with status needs-lead when the
Worker calls ask_lead; the Lead replies with answer and then calls wait again. One Worker turn at a time.
"""
from __future__ import annotations
import argparse
import contextlib
import json
import math
import os
import secrets
import stat
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents_inc.install import dispatch as D  # noqa: E402
from agents_inc.install import rules  # noqa: E402


def with_refusal(data: dict, reason, detail=None) -> dict:
    """Spec 042 FR-022: add the refusal text beside the unchanged status, reason and request_id."""
    return dict(data, refusal=rules.refuse(rules.broker_rule_id(str(reason)), detail or reason))

SUPPORTED_VERSIONS = ("2025-06-18", "2024-11-05")  # newest first; the first is the fallback
STRUCTURED_VERSION = "2025-06-18"
SERVER_INFO = {"name": "agents_inc", "version": "1"}
LOG_NAME = "mcp.log"
TOOLS = [
    {"name": "dispatch", "description": "Run one Worker through the credential-blind broker; blocks until done. "
     "Returns the result JSON and the Worker report, or status needs-lead with a Worker question (reply with "
     "answer, then call wait). slots keys (all strings; render refuses a missing one): ROLE, TASK, CONSTRAINTS, "
     "OUT_OF_SCOPE, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE, FAILURE_GATE, PRE_EXISTING_CHANGES, NOTES, ALLOWLIST, "
     "FAN_OUT, CLASSIFICATION, EFFORT, SECOND_OPINION, PLAN_CONTRACT; optional STYLE. Never send PERMISSION_MODE (broker-owned). "
     "CONSTRAINTS must include: 'Stop-on-block: if a hook or permission classifier blocks a tool call, stop and hand "
     "back to the dispatcher; never switch tool to route around it.' SUCCESS_GATE and FAILURE_GATE each name a "
     "command in backticks. PRE_EXISTING_CHANGES may be 'snapshot <snapshot>' (the broker fills the path). "
     "A Worker that writes nothing: ALLOWLIST 'none -- do all work yourself'. "
     "A Worker never leads: FAN_OUT 'width 0, total 0, depth 0' or omitted (else worker-cannot-lead).",
     "inputSchema": {"type": "object", "required": ["model", "effort", "slots"], "properties": {
         "model": {"type": "string"}, "effort": {"type": "string"},
         "slots": {"type": "object", "additionalProperties": {"type": "string"}}}}},
    {"name": "status", "description": "Return run.json counters and the remaining fan-out.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "wait", "description": "Return the stored result for a request_id, polling up to timeout seconds. "
     "Returns status needs-lead early when the Worker asked a question.",
     "inputSchema": {"type": "object", "required": ["request_id"], "properties": {
         "request_id": {"type": "string"}, "timeout": {"type": "number"}}}},
    {"name": "resume", "description": "Follow up a finished Worker (green or red) in "
     "the same session. Returns the new request id <id>-r<n>, the result and the report. Cap: 1 resume for a "
     "Grunt Worker, 2 otherwise.",
     "inputSchema": {"type": "object", "required": ["request_id", "message"], "properties": {
         "request_id": {"type": "string"}, "message": {"type": "string"}, "timeout": {"type": "number"}}}},
    {"name": "answer", "description": "Answer question question_n that a running Worker asked through ask_lead.",
     "inputSchema": {"type": "object", "required": ["request_id", "question_n", "text"], "properties": {
         "request_id": {"type": "string"}, "question_n": {"type": "integer"}, "text": {"type": "string"}}}},
]
_STATUS_KEYS = ["workers_spawned", "request_counts", "fan_out", "remaining_total", "worker_models"]
OUTPUT_SCHEMAS = {  # listed only at 2025-06-18; a result body that has every required key also goes out as structuredContent
    "dispatch": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
    "status": {"type": "object", "properties": {
        "workers_spawned": {"type": "integer"}, "request_counts": {"type": "object"}, "fan_out": {"type": "object"},
        "remaining_total": {"type": "integer"}, "worker_models": {"type": "array"}}, "required": _STATUS_KEYS},
    "wait": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
    "resume": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
    "answer": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
}
AWAIT_MAX_SEC = 3500.0  # under the Lead's MCP tool timeout (runtime.MCP_TOOL_TIMEOUT_SEC)


def log_line(run_dir: Path, text: str) -> None:
    """Append one line to <run-dir>/mcp.log; never follows a planted link."""
    line = f"{D._now()} {text}\n".encode("utf-8", "replace")
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(run_dir / LOG_NAME), flags, 0o644)
    except OSError:
        return
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


class Broker:
    def __init__(self, run_dir: Path, home_repo: str | None = None):
        self.run_dir = run_dir
        self.home_repo = home_repo
        self.issued: set = set()  # cache of request ids known to this broker; the record is <run-dir>/issued/<rid>
        self.version = None  # protocol version negotiated by the latest initialize
        self.spec = None  # loaded on the first tool call, so initialize and tools/list answer at once
        self.turn = None  # D54: the running Worker turn, if any
        self.parent_error = None  # D60: "<code>: <message>" when a Claude Lead's parent check failed; cached per start
        self.poll = 0.2

    def issue(self, rid: str) -> None:
        """Record rid as issued: a durable <run-dir>/issued/<rid> file, never written through a link."""
        if not isinstance(rid, str) or not D.REQUEST_ID_RE.match(rid):
            raise OSError("bad request id")
        d = self.run_dir / "issued"
        try:
            os.mkdir(d, 0o700)
        except FileExistsError:
            pass
        st = os.lstat(d)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise OSError("issued is not a plain directory")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        os.close(os.open(str(d / rid), flags, 0o600))
        self.issued.add(rid)

    def known(self, rid) -> bool:
        """True when this broker issued rid, now or in an earlier process (a plain record file)."""
        if not isinstance(rid, str) or not D.REQUEST_ID_RE.match(rid):
            return False
        if rid in self.issued:
            return True
        try:
            d = os.lstat(self.run_dir / "issued")
            if stat.S_ISLNK(d.st_mode) or not stat.S_ISDIR(d.st_mode):
                return False
            f = os.lstat(self.run_dir / "issued" / rid)
        except OSError:
            return False
        if stat.S_ISLNK(f.st_mode) or not stat.S_ISREG(f.st_mode):
            return False
        self.issued.add(rid)
        return True

    def ensure(self) -> None:
        if self.parent_error:
            raise D.ParentRefused(self.parent_error)
        if self.spec is None:
            spec = D._load_run_manifest(self.run_dir)
            if spec.get("parent_run_id"):  # D60: a Claude Lead proves its parent run; a Codex or legacy run has none
                self.parent_error = D.check_parent(spec, os.environ, self.run_dir)
                if self.parent_error:
                    log_line(self.run_dir, f"parent refused:{self.parent_error.split(':', 1)[0]}")
                    print(f"mcp_broker: {self.parent_error}", file=sys.stderr)
                    raise D.ParentRefused(self.parent_error)
            self.spec = spec
            D.init_broker_state(self.spec, transport="mcp")
            self.save()

    def guard(self) -> None:
        """D60: raise ParentRefused for every tool call (wait and answer included) when the parent check fails. Any other
        load error is left to the tool, which reports it as before."""
        if self.spec is None or self.parent_error:
            try:
                self.ensure()
            except D.ParentRefused:
                raise
            except Exception:
                pass

    def save(self) -> None:
        with D._SPEC_LOCK:
            D._atomic_write_json(self.run_dir / "run.json", self.spec, overwrite=True)

    def busy(self) -> bool:
        if self.turn is not None and not self.turn.alive():
            self.turn.thread.join()
            self.turn = None
        return self.turn is not None

    def start(self, rid: str, fn) -> None:
        self.turn = D.Turn(self.run_dir, rid, fn, self.spec, self.save).start()

    def _await(self, rid: str, timeout: float) -> tuple[dict, bool, str]:
        """Poll for rid's result; return needs-lead early when its Worker asked a question."""
        path = self.run_dir / f"{rid}.result.json"
        end = time.monotonic() + min(float(timeout), AWAIT_MAX_SEC)
        while not path.is_file() or path.is_symlink():
            if self.turn is not None and self.turn.rid == rid:
                asked = None
                with contextlib.suppress(OSError, ValueError):
                    asked = D.relay_question(self.run_dir, self.spec, rid)
                if asked is not None:
                    self.save()
                    return asked, False, f"needs-lead:{asked['question_n']}"
            if time.monotonic() >= end:
                return {"status": "timeout", "request_id": rid}, True, "timeout"
            time.sleep(self.poll)
        self.busy()
        data = json.loads(path.read_text(encoding="utf-8"))
        report = self.run_dir / f"{rid}.report.md"  # derived, never read from the result file
        inside = os.path.realpath(report).startswith(os.path.realpath(self.run_dir) + os.sep)
        data["report_path"] = str(report)
        data["report"] = report.read_text(encoding="utf-8") if inside and report.is_file() else ""
        return data, data.get("status") not in ("green", "unverified"), f"found:{data.get('status')}"

    def remaining(self) -> int:
        return max(0, self.spec["fan_out"]["total"] - self.spec["workers_spawned"])

    def tool_status(self, _args: dict) -> tuple[dict, bool, str]:
        self.ensure()
        data = {"workers_spawned": self.spec["workers_spawned"], "request_counts": self.spec["request_counts"],
                "fan_out": self.spec["fan_out"], "remaining_total": self.remaining(),
                "worker_models": self.spec["worker_models"]}
        return data, False, "ok"

    def tool_dispatch(self, args: dict) -> tuple[dict, bool, str]:
        self.ensure()
        rid = f"mcp-{int(time.time())}-{secrets.token_hex(3)}"
        self.issue(rid)
        model = args.get("model")
        req = {"schema_version": D.REQUEST_SCHEMA_VERSION, "request_id": rid, "model": model,
               "effort": args.get("effort"), "tier": D._load("dispatch_rungs").MODEL_RUNG.get(model)
               if isinstance(model, str) else None, "slots": args.get("slots")}
        detail = None
        if len(json.dumps(req).encode("utf-8")) > D.REQUEST_MAX_BYTES:
            req, reason = None, "oversize"
        else:
            req, reason = D._validate_fields(req, self.spec, rid)
            if reason == "credential-seeking":
                detail = D.credential_hit(args.get("slots"))  # #95
        if req is None:
            with D._SPEC_LOCK:
                self.spec["request_counts"]["refused"] += 1
            now = D._now()
            extra = {"reason_detail": detail} if detail else {}
            D._write_request_result(self.run_dir, rid, dict({
                "status": "refused", "dispatch_exit_code": D.REQ_REFUSED, "child_run_id": None, "outcome": None,
                "reason": reason, "started_at": now, "finished_at": now}, **extra), f"refused: {reason}\n")
            self.save()
            return dict({"status": "refused", "reason": reason, "request_id": rid}, **extra), True, f"refused:{reason}"
        if self.busy():
            return self._refuse(rid, "worker-running")
        self.start(rid, lambda: D._run_validated(self.run_dir, rid, req, self.spec, self.home_repo))
        return self._await(rid, AWAIT_MAX_SEC)

    def _refuse(self, rid: str, reason: str) -> tuple[dict, bool, str]:
        with D._SPEC_LOCK:
            self.spec["request_counts"]["refused"] += 1
        now = D._now()
        D._write_request_result(self.run_dir, rid, {
            "status": "refused", "dispatch_exit_code": D.REQ_REFUSED, "child_run_id": None, "outcome": None,
            "reason": reason, "started_at": now, "finished_at": now}, f"refused: {reason}\n")
        self.save()
        return {"status": "refused", "reason": reason, "request_id": rid}, True, f"refused:{reason}"

    def tool_resume(self, args: dict) -> tuple[dict, bool, str]:
        self.ensure()
        rid, message, timeout = args.get("request_id"), args.get("message"), args.get("timeout", AWAIT_MAX_SEC)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
            return {"status": "usage-error", "reason": "bad-timeout"}, True, "usage-error"
        reason = "worker-running" if self.busy() else None
        plan = None
        if reason is None:
            plan, reason = D.plan_resume(self.run_dir, self.spec, rid, message, self.known)
        if plan is None:
            with D._SPEC_LOCK:
                self.spec["request_counts"]["refused"] += 1
            self.save()
            return {"status": "refused", "reason": reason, "request_id": rid}, True, f"refused:{reason}"
        new_rid = plan["new_rid"]
        self.issue(new_rid)
        with D._SPEC_LOCK:
            self.spec["resume_of"][new_rid] = plan["root"]
        self.save()
        self.start(new_rid, lambda: D.run_resume(self.run_dir, plan, message, self.spec, self.home_repo))
        return self._await(new_rid, timeout)

    def tool_answer(self, args: dict) -> tuple[dict, bool, str]:
        self.ensure()
        rid = args.get("request_id")
        if not isinstance(rid, str) or not self.known(rid):
            return {"status": "refused", "reason": "unknown-request", "request_id": rid}, True, "refused:unknown-request"
        data, reason = D.answer_question(self.run_dir, self.spec, rid, args.get("question_n"), args.get("text"))
        if reason is not None:
            return {"status": "refused", "reason": reason, "request_id": rid}, True, f"refused:{reason}"
        return data, False, f"answered:{data['question_n']}"

    def tool_wait(self, args: dict) -> tuple[dict, bool, str]:
        rid, timeout = args.get("request_id"), args.get("timeout", 60)
        if (not isinstance(rid, str) or not D.REQUEST_ID_RE.match(rid)
                or isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout)
                or timeout < 0):
            return {"status": "usage-error", "reason": "bad-request-id-or-timeout"}, True, "usage-error"
        if not self.known(rid):
            return {"status": "refused", "reason": "unknown-request", "request_id": rid}, True, "refused:unknown-request"
        self.ensure()
        return self._await(rid, timeout)


def _frames(stdin):
    """Yield (line, oversize) per stdin line without buffering more than the size limit plus one."""
    limit = D.REQUEST_MAX_BYTES
    while True:
        line = stdin.readline(limit + 2)
        if not line:
            return
        if len(line.encode("utf-8", "replace")) > limit + 1 and not line.endswith("\n"):
            while line and not line.endswith("\n"):  # discard the rest of the oversize frame
                line = stdin.readline(limit + 2)
            yield "", True
            continue
        yield line, len(line.encode("utf-8", "replace")) > limit + 1


def _reply(mid, result=None, error=None) -> dict:
    msg = {"jsonrpc": "2.0", "id": mid}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    return msg


def handle(broker: Broker, msg) -> dict | None:
    """Return the JSON-RPC reply for one parsed message, or None for a notification."""
    if not isinstance(msg, dict) or not isinstance(msg.get("method"), str):
        return _reply(msg.get("id") if isinstance(msg, dict) else None, error={"code": -32600, "message": "invalid request"})
    mid, method = msg.get("id"), msg["method"]
    if "id" not in msg:
        return None
    if method == "initialize":
        params = msg.get("params")
        asked = params.get("protocolVersion") if isinstance(params, dict) else None
        broker.version = asked if isinstance(asked, str) and asked in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return _reply(mid, {"protocolVersion": broker.version, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO})
    if method == "ping":
        return _reply(mid, {})
    if method == "tools/list":
        if broker.version != STRUCTURED_VERSION:
            return _reply(mid, {"tools": TOOLS})
        return _reply(mid, {"tools": [{**t, "outputSchema": OUTPUT_SCHEMAS[t["name"]]} for t in TOOLS]})
    if method == "tools/call":
        params = msg.get("params")
        name = params.get("name") if isinstance(params, dict) else None
        args = params.get("arguments") if isinstance(params, dict) else None
        args = {} if args is None else args
        handler = {"dispatch": broker.tool_dispatch, "status": broker.tool_status, "wait": broker.tool_wait,
                   "resume": broker.tool_resume, "answer": broker.tool_answer}.get(name)
        if handler is None or not isinstance(args, dict):
            return _reply(mid, error={"code": -32602, "message": "unknown tool or bad arguments"})
        try:
            broker.guard()
            data, is_error, note = handler(args)
        except D.ParentRefused as exc:
            data, is_error, note = {"status": "refused", "reason": exc.code}, True, f"parent refused:{exc.code}"
        except Exception as exc:  # one bad call never stops the server
            data, is_error, note = {"status": "red", "reason": f"exception:{type(exc).__name__}"}, True, f"exception:{type(exc).__name__}"
        if isinstance(data, dict) and data.get("status") == "refused" and "refusal" not in data:
            data = with_refusal(data, data.get("reason"), data.get("reason_detail"))
        log_line(broker.run_dir, f"tool={name} {'error' if is_error else 'ok'} {note}")
        result = {"content": [{"type": "text", "text": json.dumps(data, indent=1)}], "isError": is_error}
        if (broker.version == STRUCTURED_VERSION and isinstance(data, dict)
                and all(k in data for k in OUTPUT_SCHEMAS[name]["required"])):
            result["structuredContent"] = data  # only a body that conforms to the listed outputSchema
        return _reply(mid, result)
    return _reply(mid, error={"code": -32601, "message": "method not found"})


def serve(run_dir: Path, stdin, stdout, log_env_keys: bool = True, home_repo: str | None = None) -> int:
    broker = Broker(run_dir, home_repo)
    logged = not log_env_keys
    for line, oversize in _frames(stdin):
        line = line.strip()
        if oversize:
            with contextlib.suppress(Exception):
                broker.ensure()
                with D._SPEC_LOCK:
                    broker.spec["request_counts"]["refused"] += 1
                broker.save()
            log_line(run_dir, "frame refused:oversize")
            stdout.write(json.dumps(_reply(None, error={"code": -32600, "message": "refused:oversize"})) + "\n")
            stdout.flush()
            continue
        if not line:
            continue
        try:
            reply = handle(broker, json.loads(line))
        except ValueError:
            reply = _reply(None, error={"code": -32700, "message": "parse error"})
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()
        if not logged and reply is not None and "tools" in (reply.get("result") or {}):
            logged = True  # after the first tools/list reply; names only, never values
            log_line(run_dir, "env-keys: " + ",".join(sorted(os.environ)))
    return D.BROKER_OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mcp_broker")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--home-repo")
    args = parser.parse_args(argv)
    root = Path(args.run_dir)
    if root.is_symlink() or not root.is_dir():
        print(f"mcp_broker: run directory missing: {args.run_dir}", file=sys.stderr)
        return D.BROKER_USAGE
    proto_out = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)  # stray prints from dispatch internals go to stderr, never into the protocol stream
    return serve(root.resolve(), sys.stdin, proto_out, home_repo=args.home_repo)


if __name__ == "__main__":
    raise SystemExit(main())
