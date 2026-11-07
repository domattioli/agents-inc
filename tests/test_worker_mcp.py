"""D54 Worker-to-Lead channel: worker_mcp.py (ask_lead), broker relay (needs-lead), answer, and broker resume."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from agents_inc.install import cli, dispatch, mcp_broker, runtime, worker_mcp
from tests.test_dispatch_broker import popen_from_run

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "skills/workerbee/tests/fixtures/example_slots.json"
GOOD_REPORT = ("caveman ultra confirmed. GRILL: none. [verified] gate rc=0 exit code 0.\n"
               "OUT OF SCOPE / INCOMPLETE: none\nWORKERS SPAWNED: 0\n")

_ALLOW = mock.patch.dict(os.environ, {dispatch.ALLOW_SANDBOXED_ENV: "1"})


def setUpModule():
    _ALLOW.start()  # #94: real launch() calls stay allowed when the suite runs inside a sandbox


def tearDownModule():
    _ALLOW.stop()


def _until(cond, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


class WorkerServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ask = Path(self.tmp.name).resolve() / "ask"
        self.ask.mkdir()

    def _channel(self, **kw):
        return worker_mcp.Channel(self.ask, "r1", **kw)

    def test_only_ask_lead_is_exposed(self):
        ch = self._channel()
        listed = worker_mcp.handle(ch, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual([t["name"] for t in listed["result"]["tools"]], ["ask_lead"])
        for name in ("dispatch", "status", "wait", "resume", "answer"):
            reply = worker_mcp.handle(ch, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                           "params": {"name": name, "arguments": {}}})
            self.assertEqual(reply["error"]["code"], -32602, name)
        init = worker_mcp.handle(ch, {"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "agents_inc")
        self.assertIsNone(worker_mcp.handle(ch, {"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_timeout_returns_decide_or_stop(self):
        now = [0.0]
        ch = self._channel(sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])
        text, is_error = ch.ask("which file?")
        self.assertEqual((text, is_error), (worker_mcp.NO_ANSWER, False))
        self.assertGreaterEqual(now[0], worker_mcp.WAIT_SEC)
        q = json.loads((self.ask / "r1.question.1.json").read_text())
        self.assertEqual(q["question"], "which file?")
        self.assertIn("asked_at", q)

    def test_answer_round_trip_and_numbering(self):
        def answer_later():
            _until(lambda: (self.ask / "r1.question.2.json").exists())
            (self.ask / "r1.answer.2.json").write_text(json.dumps({"answer": "pelican"}))
        os.symlink("/nonexistent", self.ask / "r1.question.1.json")  # a planted name is skipped, never followed
        t = threading.Thread(target=answer_later)
        t.start()
        text, is_error = self._channel(poll_sec=0.01).ask("what is the password word")
        t.join()
        self.assertEqual((text, is_error), ("pelican", False))
        self.assertTrue(os.path.islink(self.ask / "r1.question.1.json"))

    def test_bad_and_oversize_questions(self):
        ch = self._channel()
        self.assertTrue(ch.ask("")[1])
        self.assertTrue(ch.ask(None)[1])
        self.assertTrue(ch.ask("x" * (worker_mcp.QUESTION_MAX_BYTES + 1))[1])
        self.assertEqual(list(self.ask.iterdir()), [])

    def test_subprocess_stdio(self):
        (self.ask / "r1.answer.1.json").write_text(json.dumps({"answer": "ready"}))
        frames = "\n".join(json.dumps(m) for m in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ask_lead",
                                                                          "arguments": {"question": "go?"}}})) + "\n"
        res = subprocess.run([sys.executable, str(REPO / "agents_inc/install/worker_mcp.py"), "--run-dir",
                              str(self.ask), "--request-id", "r1"], input=frames, capture_output=True, text=True,
                             timeout=30)
        replies = [json.loads(ln) for ln in res.stdout.splitlines()]
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(replies[2]["result"]["content"][0]["text"], "ready")
        bad = subprocess.run([sys.executable, str(REPO / "agents_inc/install/worker_mcp.py"), "--run-dir",
                              str(self.ask), "--request-id", "../x"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


def _git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    for cmd in (["git", "init", "-q"], ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                                        "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


class BrokerTurnBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = _git_repo(self.root)
        self.run_dir = self.root / "lead-run"
        self.run_dir.mkdir()
        (self.run_dir / "inbox").mkdir()
        env = mock.patch.dict(os.environ, {"HOME": str(self.root), "D54_CANARY": "canary-value-1234"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("AGENTS_INC_HOME_REPO", None)
        sb = mock.patch.object(dispatch, "sandbox_available", return_value=True)
        sb.start()
        self.addCleanup(sb.stop)
        self.launches = []

    def _manifest(self, model="haiku", total=2):
        spec = {"schema_version": 1, "run_id": "lead-1", "model": "sol", "effort": "high", "cwd": str(self.repo),
                "chain": ["CoS", "sol"], "worker_models": [model], "permission_mode": "default",
                "fan_out": {"width": 1, "total": total, "depth": 1}}
        (self.run_dir / "run.json").write_text(json.dumps(spec))

    def _slots(self):
        return json.loads(EXAMPLE.read_text())

    def _launch(self, ask=None):
        """Fake Worker. With ask, the first turn asks the Lead through the real ask_lead channel code."""
        def fake(kind, model, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, codex_write=False, **_):
            self.launches.append({"resume": resume, "prompt": prompt, "rid": dispatch._WORKER_ASK})
            body = GOOD_REPORT
            if ask and resume is None and len(self.launches) == 1:  # only the first Worker asks
                channel = dispatch._ask_channel(run_dir, dispatch._WORKER_ASK)
                text, _ = worker_mcp.Channel(channel["ask"], channel["rid"], poll_sec=0.01, wait_sec=20).ask(ask)
                body += f"answer: {text}\n"
            if resume:
                body += f"turn for: {prompt}\n"
            return {"rc": 0, "stdout": body, "stderr": "", "argv": ["claude"], "session_id": "sess-1"}
        return fake


class FileBrokerTurnTest(BrokerTurnBase):
    def _start(self, launch):
        out = {}

        def target():
            with mock.patch.object(dispatch, "launch", side_effect=launch), \
                    contextlib.redirect_stderr(io.StringIO()):
                out["rc"] = dispatch.serve(self.run_dir, poll_interval=0.01, idle_timeout=60)
        t = threading.Thread(target=target, daemon=True)
        t.start()
        return t, out

    def _put(self, rid, req):
        tmp = self.run_dir / "inbox" / f"{rid}.request.json.tmp"
        tmp.write_text(json.dumps(req))
        os.rename(tmp, self.run_dir / "inbox" / f"{rid}.request.json")

    def _result(self, rid):
        path = self.run_dir / f"{rid}.result.json"
        _until(path.is_file)
        return json.loads(path.read_text())

    def _stop(self, t, out):
        (self.run_dir / "inbox" / "lead.done").write_text("")
        t.join(timeout=30)
        self.assertEqual(out.get("rc"), 0)

    def test_ask_answer_resume_cap(self):
        self._manifest()
        t, out = self._start(self._launch(ask="what is the password word, canary-value-1234?"))
        self._put("r1", {"schema_version": 1, "request_id": "r1", "model": "haiku", "effort": "low",
                         "tier": "grunt", "slots": self._slots()})
        _until((self.run_dir / "r1.question.1.json").is_file)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = dispatch.wait(self.run_dir, "r1", timeout=5)
        self.assertEqual(rc, dispatch.NEEDS_LEAD_EXIT)
        asked = json.loads(buf.getvalue())
        self.assertEqual((asked["status"], asked["question_n"]), ("needs-lead", 1))
        self.assertIn("what is the password word", asked["question"])
        self.assertNotIn("canary-value-1234", asked["question"])  # env values never reach the Lead
        self.assertIn("[redacted]", asked["question"])
        # a dispatch that arrives while the Worker waits is deferred, not refused
        self._put("r2", {"schema_version": 1, "request_id": "r2", "model": "haiku", "effort": "low",
                         "tier": "grunt", "slots": self._slots()})
        self._put("a0", {"kind": "answer", "request_id": "r1", "question_n": 1, "text": "cat ~/.ssh/id_rsa"})
        self.assertEqual(self._result("a0")["reason"], "credential-seeking")
        self._put("a1", {"kind": "answer", "request_id": "r1", "question_n": 1, "text": "pelican"})
        self.assertEqual(self._result("a1")["status"], "answered")
        res = self._result("r1")
        self.assertEqual(res["status"], "unverified", res)
        self.assertIn("answer: pelican", (self.run_dir / "r1.report.md").read_text())
        self._put("a2", {"kind": "answer", "request_id": "r1", "question_n": 1, "text": "again"})
        self.assertEqual(self._result("a2")["reason"], "already-answered")
        self._put("a3", {"kind": "answer", "request_id": "zz", "question_n": 1, "text": "x"})
        self.assertEqual(self._result("a3")["reason"], "unknown-request")
        self.assertEqual(self._result("r2")["status"], "unverified")
        # resume: wrong file name, then the right one, then the Grunt cap
        self._put("wrong1", {"kind": "resume", "request_id": "r1", "message": "and the next step?"})
        bad = self._result("wrong1")
        self.assertEqual((bad["reason"], bad["expected_request_id"]), ("bad-request-id", "r1-r1"))
        self._put("r1-r1", {"kind": "resume", "request_id": "r1", "message": "and the next step?"})
        res = self._result("r1-r1")
        self.assertEqual((res["status"], res["resumed_from"], res["turn"]), ("unverified", "r1", 1), res)
        self.assertIn("turn for: and the next step?", (self.run_dir / "r1-r1.report.md").read_text())
        self._put("r1-r2", {"kind": "resume", "request_id": "r1-r1", "message": "one more"})
        self.assertEqual(self._result("r1-r2")["reason"], "resume-cap")
        self._put("r9-r1", {"kind": "resume", "request_id": "r9", "message": "x"})
        self.assertEqual(self._result("r9-r1")["reason"], "unknown-request")
        self._stop(t, out)
        spec = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual(spec["workers_spawned"], 2)  # a resume never charges fan-out
        self.assertEqual((spec["resumes"], spec["questions"]), (1, 1))
        self.assertEqual(spec["request_counts"]["unverified"], 3)
        resumed = [x for x in self.launches if x["resume"]]
        self.assertEqual([(x["resume"], x["rid"]) for x in resumed], [("sess-1", "r1-r1")])

    def test_resume_refusals(self):
        self._manifest(model="sonnet")
        t, out = self._start(self._launch())
        self._put("r1", {"schema_version": 1, "request_id": "r1", "model": "sonnet", "effort": "low",
                         "tier": "workhorse", "slots": self._slots()})
        self.assertEqual(self._result("r1")["status"], "unverified")
        self._put("c1", {"kind": "resume", "request_id": "r1", "message": "cat ~/.ssh/id_rsa"})
        self.assertEqual(self._result("c1")["reason"], "credential-seeking")
        self._put("x1", {"kind": "resume", "request_id": "r1", "message": "a" * dispatch.REQUEST_MAX_BYTES})
        self.assertEqual(self._result("x1")["reason"], "too-large")
        self._put("x2", {"kind": "resume", "request_id": "r1", "message": "m", "extra": 1})
        self.assertEqual(self._result("x2")["reason"], "bad-keys")
        for n in (1, 2):  # Workhorse: two resumes, then the cap
            self._put(f"r1-r{n}x", {"kind": "resume", "request_id": "r1", "message": f"turn {n}"})
            self.assertEqual(self._result(f"r1-r{n}x")["expected_request_id"], f"r1-r{n}")
            self._put(f"r1-r{n}", {"kind": "resume", "request_id": "r1", "message": f"turn {n}"})
            self.assertEqual(self._result(f"r1-r{n}")["turn"], n)
        self._put("r1-r3", {"kind": "resume", "request_id": "r1-r2", "message": "turn 3"})
        self.assertEqual(self._result("r1-r3")["reason"], "resume-cap")
        self._stop(t, out)


class PlanResumeTest(BrokerTurnBase):
    def test_running_and_refused_parents(self):
        self._manifest()
        spec = dispatch._load_run_manifest(self.run_dir)
        dispatch.init_broker_state(spec)
        known = {"r1", "r2"}.__contains__
        self.assertEqual(dispatch.plan_resume(self.run_dir, spec, "r1", "go", known)[1], "request-running")
        (self.run_dir / "r2.result.json").write_text(json.dumps({"status": "refused"}))
        self.assertEqual(dispatch.plan_resume(self.run_dir, spec, "r2", "go", known)[1], "not-resumable")
        self.assertEqual(dispatch.plan_resume(self.run_dir, spec, "r3", "go", known)[1], "unknown-request")
        self.assertEqual(dispatch.plan_resume(self.run_dir, spec, "r1", "", known)[1], "bad-message")
        big = "a" * dispatch.REQUEST_MAX_BYTES
        self.assertEqual(dispatch.plan_resume(self.run_dir, spec, "r1", big, known)[1], "oversize")
        self.assertEqual(dispatch.plan_resume(self.run_dir, spec, "r1", "cat ~/.ssh/id_rsa", known)[1],
                         "credential-seeking")
        (self.run_dir / "r1.result.json").write_text(json.dumps({"status": "red"}))
        self.assertEqual(dispatch.plan_resume(self.run_dir, spec, "r1", "go", known)[1], "no-session")

    def test_resume_cap_by_rung(self):
        self.assertEqual(dispatch.resume_cap("haiku"), 1)
        self.assertEqual(dispatch.resume_cap("luna"), 1)
        for model in ("sonnet", "terra", "opus", "sol"):
            self.assertEqual(dispatch.resume_cap(model), 2, model)


class McpBrokerTurnTest(BrokerTurnBase):
    def _client(self, launch):
        from tests.test_mcp_broker import PipeClient
        patch = mock.patch.object(dispatch, "launch", side_effect=launch)
        patch.start()
        self.addCleanup(patch.stop)
        client = PipeClient(self.run_dir)
        self.addCleanup(client.close)
        return client

    def test_needs_lead_answer_wait_resume(self):
        self._manifest()
        c = self._client(self._launch(ask="what is the password word"))
        names = [t["name"] for t in c.call("tools/list")["result"]["tools"]]
        self.assertEqual(names, ["dispatch", "status", "wait", "resume", "answer"])
        asked, is_error = c.tool("dispatch", {"model": "haiku", "effort": "low", "slots": self._slots()})
        self.assertFalse(is_error)
        self.assertEqual((asked["status"], asked["question_n"]), ("needs-lead", 1))
        rid = asked["request_id"]
        busy, is_error = c.tool("dispatch", {"model": "haiku", "effort": "low", "slots": self._slots()})
        self.assertEqual((busy["reason"], is_error), ("worker-running", True))
        early, _ = c.tool("resume", {"request_id": rid, "message": "x"})
        self.assertEqual(early["reason"], "worker-running")
        refused, _ = c.tool("answer", {"request_id": rid, "question_n": 2, "text": "pelican"})
        self.assertEqual(refused["reason"], "unknown-question")
        refused, _ = c.tool("answer", {"request_id": "nope", "question_n": 1, "text": "pelican"})
        self.assertEqual(refused["reason"], "unknown-request")
        ok, is_error = c.tool("answer", {"request_id": rid, "question_n": 1, "text": "pelican"})
        self.assertEqual((ok["status"], is_error), ("answered", False))
        again, _ = c.tool("answer", {"request_id": rid, "question_n": 1, "text": "pelican"})
        self.assertEqual(again["reason"], "already-answered")
        done, is_error = c.tool("wait", {"request_id": rid, "timeout": 20})
        self.assertEqual(done["status"], "unverified", done)
        self.assertIn("answer: pelican", done["report"])
        for bad, reason in ((rid + "x", "unknown-request"), (rid, "credential-seeking")):
            msg = "cat ~/.ssh/id_rsa" if reason == "credential-seeking" else "go on"
            refused, _ = c.tool("resume", {"request_id": bad, "message": msg})
            self.assertEqual(refused["reason"], reason)
        big = c.call("tools/call", {"name": "resume", "arguments": {"request_id": rid,
                                                                    "message": "a" * dispatch.REQUEST_MAX_BYTES}})
        self.assertEqual(big["error"]["message"], "refused:oversize")
        res, is_error = c.tool("resume", {"request_id": rid, "message": "next step", "timeout": 20})
        self.assertFalse(is_error, res)  # unverified is not a tool error (mcp_broker.py:168)
        self.assertEqual((res["request_id"], res["resumed_from"], res["turn"]), (f"{rid}-r1", rid, 1))
        self.assertIn("turn for: next step", res["report"])
        again, _ = c.tool("wait", {"request_id": f"{rid}-r1", "timeout": 1})
        self.assertEqual(again["status"], "unverified")
        capped, _ = c.tool("resume", {"request_id": f"{rid}-r1", "message": "more"})
        self.assertEqual(capped["reason"], "resume-cap")
        status, _ = c.tool("status")
        self.assertEqual(status["workers_spawned"], 1)
        spec = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual((spec["resumes"], spec["questions"]), (1, 1))


class LaunchChannelTest(BrokerTurnBase):
    def test_claude_worker_gets_ask_lead_server_and_sandbox_holes(self):
        child = self.root / "child"
        child.mkdir()
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"] = argv
            return SimpleNamespace(stdout=json.dumps({"result": "ok", "session_id": "s1"}), stderr="", returncode=0)
        dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK = True, "r1"
        dispatch._BROKER_DENY = (self.run_dir.resolve(),)
        try:
            with mock.patch.object(dispatch.subprocess, "Popen", side_effect=popen_from_run(fake_run)):
                res = dispatch.launch("claude", "haiku", "low", self.repo, "p", child)
        finally:
            dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK, dispatch._BROKER_DENY = False, None, ()
        argv = seen["argv"]
        self.assertEqual(res["session_id"], "s1")
        config = Path(argv[argv.index("--mcp-config") + 1])
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "mcp__agents_inc__ask_lead")
        server = json.loads(config.read_text())["mcpServers"]["agents_inc"]
        self.assertEqual(server["args"][1:], ["--run-dir", str((child / "ask").resolve()), "--request-id", "r1"])
        self.assertEqual(Path(server["args"][0]).read_text(), dispatch.WORKER_MCP.read_text())
        profile = (child / "sandbox.sb").read_text()
        self.assertIn(str((child / "ask").resolve()), profile)
        self.assertIn(str(config.resolve()), profile)

    def test_codex_worker_gets_worker_tuple(self):
        child = self.root / "child"
        child.mkdir()
        captured = {}
        receipt = SimpleNamespace(codex_path="/opt/x/bin/codex")
        paths = SimpleNamespace(receipt=self.root / "r.json", current=self.root)

        def fake_run_codex(*a, **kw):
            captured.update(kw)
            kw["thread_out"]["thread_id"] = "th-1"
            return 0
        dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK = True, "r1"
        try:
            with mock.patch.object(cli, "_paths", return_value=paths), mock.patch.object(cli, "_efforts", return_value={}), \
                    mock.patch("agents_inc.install.receipt.InstallReceipt.load", return_value=receipt), \
                    mock.patch.object(runtime, "run_codex", side_effect=fake_run_codex):
                res = dispatch.launch("codex", "luna", "low", self.repo, "p", child)
        finally:
            dispatch._BROKER_SAFE_WRITES, dispatch._WORKER_ASK = False, None
        ask, rid, script = captured["worker"]
        self.assertEqual((ask, rid, script.name), ((child / "ask").resolve(), "r1", "worker_mcp.py"))
        self.assertEqual(res["session_id"], "th-1")
        self.assertIn('"--request-id", "r1"', " ".join(runtime.worker_args(ask, rid, script)))

    def test_plain_launch_has_no_channel(self):
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"] = argv
            return SimpleNamespace(stdout="{}", stderr="", returncode=0)
        with mock.patch.object(dispatch.subprocess, "Popen", side_effect=popen_from_run(fake_run)):
            dispatch.launch("claude", "haiku", None, self.repo, "p", self.root)
        self.assertNotIn("--mcp-config", seen["argv"])
        self.assertFalse((self.root / "ask").exists())


if __name__ == "__main__":
    unittest.main()


class WorkerProtocolHygieneTest(unittest.TestCase):
    """Spec 018 wave 1 (DomI specs/consumers/agents_Inc/specs/018-mcp-channel-hygiene): FR-001, FR-006, FR-009."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ask = Path(self.tmp.name).resolve() / "ask"
        self.ask.mkdir()
        self.ch = worker_mcp.Channel(self.ask, "r1")

    def _init(self, params):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        if params is not None:
            msg["params"] = params
        return worker_mcp.handle(self.ch, msg)["result"]

    def test_initialize_negotiates_version(self):
        for asked in ("2025-06-18", "2024-11-05"):
            self.assertEqual(self._init({"protocolVersion": asked})["protocolVersion"], asked)
        for asked in ("2099-01-01", "2026-07-28", "", 20250618):
            self.assertEqual(self._init({"protocolVersion": asked})["protocolVersion"], "2025-06-18", asked)
        self.assertEqual(self._init({})["protocolVersion"], "2025-06-18")
        self.assertEqual(self._init(None)["protocolVersion"], "2025-06-18")
        self.assertEqual(worker_mcp.SUPPORTED_VERSIONS, ("2025-06-18", "2024-11-05"))

    def test_no_tasks_capability_declared(self):
        for asked in ("2025-06-18", "2024-11-05"):
            init = self._init({"protocolVersion": asked})
            self.assertNotIn("tasks", init["capabilities"])
            tools = worker_mcp.handle(self.ch, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
            for tool in tools:
                self.assertNotIn("execution", tool)
                self.assertNotIn("outputSchema", tool)  # Worker tools keep plain text (FR-002)

    def test_worker_server_stays_self_contained(self):
        source = (REPO / "agents_inc/install/worker_mcp.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^\s*(from|import)\s+agents_inc")

    def test_client_timeouts_exceed_server_waits(self):
        child = Path(self.tmp.name).resolve() / "child"
        child.mkdir()
        paths = dispatch._ask_channel(child, "r1")
        server = json.loads(paths["config"].read_text())["mcpServers"]["agents_inc"]
        self.assertEqual(server["timeout"], runtime.MCP_TOOL_TIMEOUT_SEC * 1000)
        self.assertGreaterEqual(runtime.MCP_TOOL_TIMEOUT_SEC - worker_mcp.WAIT_SEC, 60)
        self.assertGreaterEqual(runtime.MCP_TOOL_TIMEOUT_SEC - mcp_broker.AWAIT_MAX_SEC, 60)
        self.assertEqual(dispatch.WORKER_ENV_KEYS, ("HOME", "USER", "TERM", "LANG", "TMPDIR"))
        base = {"HOME": "/h", "USER": "u", "CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT": "1", "MCP_TIMEOUT": "1"}
        self.assertEqual(set(dispatch.worker_env("/usr/bin/claude", base)), {"PATH", "HOME", "USER", "AGENTS_INC_WORKER"})
