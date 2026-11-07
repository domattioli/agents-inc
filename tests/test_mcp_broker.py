"""D51 MCP transport: stdio JSON-RPC server over the shared broker validation and processing path."""
from __future__ import annotations
import io
import json
import os
import subprocess
import sys
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from agents_inc.install import dispatch, mcp_broker, runtime

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "skills/workerbee/tests/fixtures/example_slots.json"


class PipeClient:
    """Fake JSON-RPC client: drives mcp_broker.serve() over OS pipes in a thread."""

    def __init__(self, run_dir: Path, **kw):
        c2s_r, c2s_w = os.pipe()
        s2c_r, s2c_w = os.pipe()
        self.w = os.fdopen(c2s_w, "w", encoding="utf-8")
        self.r = os.fdopen(s2c_r, "r", encoding="utf-8")
        self.rc = None
        sin, sout = os.fdopen(c2s_r, "r", encoding="utf-8"), os.fdopen(s2c_w, "w", encoding="utf-8")

        def target():
            self.rc = mcp_broker.serve(run_dir, sin, sout, **kw)
            sout.close()
            sin.close()
        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()
        self.n = 0

    def raw(self, line: str) -> dict:
        self.w.write(line + "\n")
        self.w.flush()
        return json.loads(self.r.readline())

    def call(self, method: str, params=None) -> dict:
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        return self.raw(json.dumps(msg))

    def tool(self, name: str, args=None) -> tuple[dict, bool]:
        res = self.call("tools/call", {"name": name, "arguments": args or {}})["result"]
        return json.loads(res["content"][0]["text"]), res["isError"]

    def close(self):
        self.w.close()
        self.thread.join(timeout=10)
        self.r.close()


class McpBrokerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run_dir = self.root / "lead-run"
        self.run_dir.mkdir()
        self.sb = mock.patch.object(dispatch, "sandbox_available", return_value=True)
        self.sb.start()
        self.addCleanup(self.sb.stop)
        self.addCleanup(self.tmp.cleanup)

    def _client(self, total=1, spawned=0, **kw) -> PipeClient:
        spec = {"schema_version": 1, "run_id": "lead-1", "model": "terra", "effort": "high", "cwd": str(self.repo),
                "chain": ["CoS", "terra"], "worker_models": ["haiku"], "permission_mode": "default",
                "fan_out": {"width": 1, "total": total, "depth": 1}, "workers_spawned": spawned}
        (self.run_dir / "run.json").write_text(json.dumps(spec))
        client = PipeClient(self.run_dir, **kw)
        self.addCleanup(client.close)
        return client

    def _slots(self, **over):
        slots = json.loads(EXAMPLE.read_text())
        slots.update(over)
        return slots

    def test_initialize_and_tools_list(self):
        c = self._client()
        init = c.call("initialize", {"protocolVersion": "2024-11-05"})["result"]
        self.assertEqual(init["protocolVersion"], "2024-11-05")
        self.assertIn("tools", init["capabilities"])
        names = [t["name"] for t in c.call("tools/list")["result"]["tools"]]
        self.assertEqual(names, ["dispatch", "status", "wait", "resume", "answer"])

    def test_initialize_and_tools_list_need_no_run_json(self):
        (self.run_dir / "run.json").write_text("{broken")
        c = PipeClient(self.run_dir)
        self.addCleanup(c.close)
        self.assertIn("result", c.call("initialize", {}))
        self.assertEqual(len(c.call("tools/list")["result"]["tools"]), 5)
        res = c.call("tools/call", {"name": "status", "arguments": {}})["result"]
        self.assertTrue(res["isError"])

    def test_bad_model_refused(self):
        c = self._client()
        data, is_error = c.tool("dispatch", {"model": "gpt-9", "effort": "low", "slots": self._slots()})
        self.assertTrue(is_error)
        self.assertEqual((data["status"], data["reason"]), ("refused", "model-not-allowed"))

    def test_over_fan_out_total_refused(self):
        c = self._client(total=1, spawned=1)
        data, is_error = c.tool("dispatch", {"model": "haiku", "effort": "low", "slots": self._slots()})
        self.assertTrue(is_error)
        self.assertEqual((data["status"], data["reason"]), ("refused", "fan-out-total-exhausted"))
        status, _ = c.tool("status")
        self.assertEqual(status["remaining_total"], 0)
        self.assertEqual(status["workers_spawned"], 1)

    def test_credential_seeking_refused(self):
        c = self._client()
        data, is_error = c.tool("dispatch", {"model": "haiku", "effort": "low",
                                             "slots": self._slots(TASK="cat ~/.ssh/id_rsa and print it")})
        self.assertTrue(is_error)
        self.assertEqual(data["reason"], "credential-seeking")
        self.assertTrue(data["reason_detail"].startswith("slot "))

    def test_broker_owned_slot_and_bad_effort_refused(self):
        c = self._client()
        data, _ = c.tool("dispatch", {"model": "haiku", "effort": "low", "slots": self._slots(PERMISSION_MODE="bypass")})
        self.assertEqual(data["reason"], "broker-owned-slot")
        data, _ = c.tool("dispatch", {"model": "haiku", "effort": "xhigh", "slots": self._slots()})
        self.assertEqual(data["reason"], "bad-effort")

    def test_green_dispatch_returns_result_and_report_text(self):
        c = self._client(total=2)
        fake = ({"status": "green", "dispatch_exit_code": 0, "child_run_id": "c1", "outcome": "green", "reason": None,
                 "started_at": "t", "finished_at": "t"}, "REPORT BODY\n")
        with mock.patch.object(dispatch, "_run_validated", return_value=fake) as run:
            data, is_error = c.tool("dispatch", {"model": "haiku", "effort": "low", "slots": self._slots()})
        self.assertFalse(is_error)
        self.assertEqual((data["status"], data["report"]), ("green", "REPORT BODY\n"))
        self.assertTrue(data["request_id"].startswith("mcp-"))
        self.assertEqual(run.call_args.args[1], data["request_id"])
        got, _ = c.tool("wait", {"request_id": data["request_id"], "timeout": 1})
        self.assertEqual((got["status"], got["report"]), ("green", "REPORT BODY\n"))
        timed, is_error = c.tool("wait", {"request_id": "nope1", "timeout": 0})
        self.assertTrue(is_error)
        self.assertEqual(timed["reason"], "unknown-request")
        broker = mcp_broker.Broker(self.run_dir)
        broker.issued.add("late1")
        late, is_error, _ = broker.tool_wait({"request_id": "late1", "timeout": 0})
        self.assertTrue(is_error)
        self.assertEqual(late["status"], "timeout")

    def test_oversize_frame_refused_and_server_stays_up(self):
        c = self._client()
        c.w.write("x" * (dispatch.REQUEST_MAX_BYTES + 500) + "\n")
        c.w.flush()
        err = json.loads(c.r.readline())
        self.assertEqual(err["error"]["message"], "refused:oversize")
        self.assertIn("result", c.call("tools/list"))
        status, _ = c.tool("status")
        self.assertEqual(status["request_counts"]["refused"], 1)

    def test_oversize_constructed_request_refused(self):
        self._client().close()  # writes run.json
        broker = mcp_broker.Broker(self.run_dir)
        big = self._slots(TASK="a" * dispatch.REQUEST_MAX_BYTES)
        data, is_error, _ = broker.tool_dispatch({"model": "haiku", "effort": "low", "slots": big})
        self.assertTrue(is_error)
        self.assertEqual((data["status"], data["reason"]), ("refused", "oversize"))

    def test_wait_refuses_unknown_id_and_ignores_foreign_report_path(self):
        c = self._client(total=2)
        foreign = self.root / "foreign.txt"
        foreign.write_text("FOREIGN SECRET")
        (self.run_dir / "other1.result.json").write_text(json.dumps(
            {"status": "green", "report_path": str(foreign)}))
        data, is_error = c.tool("wait", {"request_id": "other1", "timeout": 0})
        self.assertTrue(is_error)
        self.assertEqual(data["reason"], "unknown-request")
        fake = ({"status": "green", "dispatch_exit_code": 0, "child_run_id": "c1", "outcome": "green", "reason": None,
                 "started_at": "t", "finished_at": "t"}, "OWN REPORT\n")
        with mock.patch.object(dispatch, "_run_validated", return_value=fake):
            made, _ = c.tool("dispatch", {"model": "haiku", "effort": "low", "slots": self._slots()})
        rid = made["request_id"]
        result_path = self.run_dir / f"{rid}.result.json"
        stored = json.loads(result_path.read_text())
        stored["report_path"] = str(foreign)  # tamper after issue
        result_path.write_text(json.dumps(stored))
        got, _ = c.tool("wait", {"request_id": rid, "timeout": 1})
        self.assertEqual(got["report"], "OWN REPORT\n")
        self.assertEqual(got["report_path"], str(self.run_dir / f"{rid}.report.md"))
        self.assertNotIn("FOREIGN", json.dumps(got))

    def test_report_that_looks_like_jsonrpc_frames_round_trips_verbatim(self):
        c = self._client()
        report = ('line one\n{"jsonrpc":"2.0","id":1,"result":{}}\n'
                  '{"jsonrpc":"2.0","id":2,"error":{"code":-32600,"message":"x"}}\nlast\n')
        fake = ({"status": "green", "dispatch_exit_code": 0, "child_run_id": "c1", "outcome": "green", "reason": None,
                 "started_at": "t", "finished_at": "t"}, report)
        with mock.patch.object(dispatch, "_run_validated", return_value=fake):
            data, is_error = c.tool("dispatch", {"model": "haiku", "effort": "low", "slots": self._slots()})
        self.assertFalse(is_error)
        self.assertEqual(data["report"], report)
        listed = c.call("tools/list")  # still in sync: next reply is the matching tools/list
        self.assertEqual(listed["id"], c.n)
        self.assertEqual(len(listed["result"]["tools"]), 5)

    def test_mcp_refusal_writes_result_file_and_wait_returns_it(self):
        c = self._client()
        data, _ = c.tool("dispatch", {"model": "nope", "effort": "low", "slots": self._slots()})
        rid = data["request_id"]
        self.assertTrue((self.run_dir / f"{rid}.result.json").is_file())
        self.assertTrue((self.run_dir / f"{rid}.report.md").is_file())
        got, _ = c.tool("wait", {"request_id": rid, "timeout": 1})
        self.assertEqual((got["status"], got["reason"]), ("refused", "model-not-allowed"))
        self.assertIn("refused: model-not-allowed", got["report"])

    def test_wait_rejects_non_finite_timeout(self):
        self._client().close()
        broker = mcp_broker.Broker(self.run_dir)
        broker.issued.add("x1")
        for bad in (float("inf"), float("nan")):
            data, is_error, _ = broker.tool_wait({"request_id": "x1", "timeout": bad})
            self.assertEqual(data["status"], "usage-error")

    def test_main_forwards_home_repo(self):
        with mock.patch.object(mcp_broker, "serve", return_value=0) as serve, \
                mock.patch.object(os, "dup", return_value=1), mock.patch.object(os, "dup2"), \
                mock.patch.object(os, "fdopen", return_value=io.StringIO()):
            mcp_broker.main(["--run-dir", str(self.run_dir), "--home-repo", "/home/repo"])
        self.assertEqual(serve.call_args.kwargs["home_repo"], "/home/repo")

    def test_status_counters(self):
        c = self._client(total=3)
        c.tool("dispatch", {"model": "nope", "effort": "low", "slots": self._slots()})
        status, is_error = c.tool("status")
        self.assertFalse(is_error)
        self.assertEqual(status["request_counts"]["refused"], 1)
        self.assertEqual(status["remaining_total"], 3)
        self.assertEqual(status["fan_out"], {"width": 1, "total": 3, "depth": 1})
        spec = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual(spec["broker"]["transport"], "mcp")
        self.assertEqual(spec["request_counts"]["refused"], 1)

    def test_malformed_line_error_then_server_stays_up(self):
        c = self._client()
        err = c.raw("{not json")
        self.assertEqual(err["error"]["code"], -32700)
        self.assertIsNone(err["id"])
        self.assertEqual(c.raw("[1]")["error"]["code"], -32600)
        self.assertEqual(c.call("nope")["error"]["code"], -32601)
        self.assertIn("result", c.call("tools/list"))

    def test_notification_gets_no_reply_and_log_has_no_values(self):
        c = self._client(log_env_keys=True)
        c.w.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        c.w.flush()
        c.call("tools/list")
        c.tool("status")
        c.tool("dispatch", {"model": "nope", "effort": "low", "slots": self._slots()})
        lines = (self.run_dir / "mcp.log").read_text().splitlines()
        self.assertTrue(any("env-keys:" in ln for ln in lines))
        self.assertEqual(sum(1 for ln in lines if "tool=" in ln), 2)
        self.assertNotIn("=", "".join(ln.split(" ", 1)[1].replace("tool=", "") for ln in lines))

    def test_log_never_follows_a_link(self):
        victim = self.root / "victim.txt"
        victim.write_text("keep")
        os.symlink(victim, self.run_dir / "mcp.log")
        mcp_broker.log_line(self.run_dir, "tool=x ok")
        self.assertEqual(victim.read_text(), "keep")

    def test_shared_validation_path(self):
        spec = dispatch._load_run_manifest(self._write_manifest())
        req, reason = dispatch._validate_fields(
            {"schema_version": 1, "request_id": "a1", "model": "haiku", "effort": "low", "tier": "grunt",
             "slots": self._slots()}, spec, "a1")
        self.assertIsNone(reason)
        _, reason = dispatch._validate_fields(
            {"schema_version": 1, "request_id": "a1", "model": "haiku", "effort": "low", "tier": "grunt",
             "slots": self._slots()}, spec, "other")
        self.assertEqual(reason, "bad-request-id")

    def _write_manifest(self) -> Path:
        self._client()
        return self.run_dir

    def test_subprocess_stdio_roundtrip(self):
        self._write_manifest()
        proc = subprocess.Popen([sys.executable, str(REPO / "agents_inc/install/mcp_broker.py"), "--run-dir", str(self.run_dir)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = proc.communicate(
                '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\nGARBAGE\n'
                '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n', timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
        replies = [json.loads(ln) for ln in out.splitlines()]
        self.assertEqual(len(replies), 3, err)
        self.assertEqual(replies[1]["error"]["code"], -32700)
        self.assertEqual(len(replies[2]["result"]["tools"]), 5)
        self.assertEqual(proc.returncode, 0)

    def test_bad_run_dir_exits_usage(self):
        res = subprocess.run([sys.executable, str(REPO / "agents_inc/install/mcp_broker.py"), "--run-dir",
                              str(self.root / "missing")], capture_output=True, text=True)
        self.assertEqual(res.returncode, dispatch.BROKER_USAGE)


class LeadCodexHomeTest(unittest.TestCase):
    """Isolated CODEX_HOME for the Lead: operator MCP servers and config never load."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.fake_home = self.root / "home"
        (self.fake_home / ".codex").mkdir(parents=True)
        (self.fake_home / ".codex" / "auth.json").write_text("SECRET-NOT-READ")
        patch = mock.patch.object(Path, "home", return_value=self.fake_home)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_helper_creates_symlinks_and_config(self):
        home = runtime.lead_codex_home("gpt-5.6-terra")
        self.addCleanup(shutil.rmtree, home, True)
        self.assertEqual(sorted(p.name for p in home.iterdir()),
                         ["auth.json", "config.toml", "generated_images", "sessions", "skills"])
        self.assertEqual(os.readlink(home / "auth.json"), str(self.fake_home / ".codex" / "auth.json"))
        self.assertEqual(os.readlink(home / "sessions"), str(self.fake_home / ".codex" / "sessions"))
        self.assertTrue((self.fake_home / ".codex" / "sessions").is_dir())
        self.assertEqual((home / "config.toml").read_text(), 'model = "gpt-5.6-terra"\n')
        self.assertEqual(os.stat(home).st_mode & 0o777, 0o700)
        self.assertTrue((home / "auth.json").is_symlink())

    def test_missing_auth_raises(self):
        (self.fake_home / ".codex" / "auth.json").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "WB_CODEX_AUTH_MISSING"):
            runtime.lead_codex_home("gpt-5.6-terra")

    def test_run_codex_env_deny_and_cleanup(self):
        done = SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        eff = {"gpt-5.6-terra": ["medium"]}
        seen = {}
        real_home = runtime.lead_codex_home

        def fake_run(argv, **kw):
            seen["argv"], seen["env"] = argv, kw["env"]
            seen["home"] = Path(kw["env"]["CODEX_HOME"])
            seen["existed"] = seen["home"].is_dir()
            return done
        run_dir = self.root / "lead-run"
        run_dir.mkdir()
        scrubbed = {"PATH": "/usr/bin", "HOME": str(self.fake_home), "FOO_API_KEY": "v"}
        err = io.StringIO()
        with mock.patch.object(runtime, "load_model_map", return_value={"terra": "gpt-5.6-terra"}), \
                mock.patch.object(runtime.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(Path, "is_file", lambda self_: True if self_.name in ("auth.json", "codex") else os.path.isfile(self_)), \
                mock.patch.object(runtime, "lead_codex_home", side_effect=real_home), \
                mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", err):
            rc = runtime.run_codex("terra", "medium", Path("/w"), io.StringIO("p"),
                                   SimpleNamespace(codex_path=Path("/x/codex")), eff, env=scrubbed, lead_dir=run_dir)
        self.assertEqual(rc, 0)
        self.assertTrue(seen["existed"])
        self.assertIn("CODEX_HOME", seen["env"])
        self.assertTrue(seen["env"]["PATH"].startswith("/usr/bin:/bin:"))
        self.assertNotIn("FOO_API_KEY", seen["env"])
        self.assertIn(f'"{os.path.realpath(run_dir)}"="none"', " ".join(seen["argv"]))
        self.assertFalse([k for k in seen["env"] if dispatch.SECRET_ENV_RE.search(k)])
        self.assertIn('"codex_home": "isolated"', err.getvalue())
        self.assertNotIn(str(seen["home"]), err.getvalue())
        deny = f'"{os.path.realpath(seen["home"])}"="none"'
        self.assertIn(deny, " ".join(seen["argv"]))
        self.assertFalse(seen["home"].exists())  # removed on exit
        self.assertEqual((self.fake_home / ".codex" / "auth.json").read_text(), "SECRET-NOT-READ")
        self.assertTrue((self.fake_home / ".codex" / "sessions").is_dir())


    def _run(self, run_dir, cwd, env=None, home_repo=None):
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["env"] = argv, kw["env"]
            return SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        run_patch = runtime.subprocess.run if isinstance(runtime.subprocess.run, mock.Mock) else None
        with mock.patch.object(runtime, "load_model_map", return_value={"terra": "gpt-5.6-terra"}), \
                mock.patch.object(runtime.subprocess, "run", side_effect=run_patch.side_effect if run_patch else fake_run) as sp, \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(Path, "is_file", lambda self_: True if self_.name in ("auth.json", "codex") else os.path.isfile(self_)), \
                mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO()) as err:
            seen["rc"] = runtime.run_codex("terra", "medium", cwd, io.StringIO("p"),
                                           SimpleNamespace(codex_path=Path("/x/codex")),
                                           {"gpt-5.6-terra": ["medium"]}, env=env, lead_dir=run_dir,
                                           home_repo=home_repo)
            seen["err"] = err.getvalue()
        return seen

    def test_lead_dir_denied_even_under_cwd(self):
        cwd = self.root / "repo"
        run_dir = cwd / "lead-run"
        run_dir.mkdir(parents=True)
        seen = self._run(run_dir, cwd)
        self.assertIn(f'"{os.path.realpath(run_dir)}"="none"', " ".join(seen["argv"]))

    def test_lead_env_is_minimal_when_env_is_none(self):
        run_dir = self.root / "lead-run"
        run_dir.mkdir()
        fake = {"PATH": "/x", "HOME": str(self.fake_home), "USER": "u", "FOO_API_KEY": "v", "GH_TOKEN": "t", "MY_SECRET": "s"}
        with mock.patch.dict(os.environ, fake, clear=True):
            seen = self._run(run_dir, self.root)
        self.assertIn("CODEX_HOME", seen["env"])
        self.assertFalse([k for k in seen["env"] if dispatch.SECRET_ENV_RE.search(k)])
        self.assertLessEqual(set(seen["env"]), {"PATH", "HOME", "USER", "TERM", "LANG", "TMPDIR", "CODEX_HOME",
                                                      "AGENTS_INC_WORKER"})

    def test_cleanup_failure_is_reported_and_fails_the_run(self):
        run_dir = self.root / "lead-run"
        run_dir.mkdir()
        with mock.patch.object(runtime.shutil, "rmtree", side_effect=PermissionError("denied")):
            seen = self._run(run_dir, self.root)
        self.assertEqual(seen["rc"], 1)
        self.assertIn("agents-inc run: isolated CODEX_HOME not removed", seen["err"])
        shutil.rmtree(Path(seen["env"]["CODEX_HOME"]), ignore_errors=True)

    def test_cleanup_ok_keeps_exit_zero(self):
        run_dir = self.root / "lead-run"
        run_dir.mkdir()
        seen = self._run(run_dir, self.root)
        self.assertEqual(seen["rc"], 0)
        self.assertNotIn("not removed", seen["err"])

    def test_home_removed_when_env_builder_raises(self):
        run_dir = self.root / "lead-run"
        run_dir.mkdir()
        homes = []
        real = runtime.lead_codex_home

        def spy(slug):
            homes.append(real(slug))
            return homes[-1]
        with mock.patch.object(runtime, "lead_codex_home", side_effect=spy), \
                mock.patch.object(runtime, "lead_env", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self._run(run_dir, self.root)
        self.assertEqual(len(homes), 1)
        self.assertFalse(homes[0].exists())

    def test_lead_home_reaches_mcp_server_through_env_table(self):
        run_dir = self.root / "lead-run"
        run_dir.mkdir()
        seen = self._run(run_dir, self.root, home_repo="/home/repo")
        argv = seen["argv"]
        env_args = [a for a in argv if a.startswith("mcp_servers.agents_inc.env=")]
        self.assertEqual(len(env_args), 1)
        self.assertRegex(env_args[0], r'^mcp_servers\.agents_inc\.env=\{CODEX_HOME="[^"]*agents-inc-lead-home-[^"]*"\}$')
        self.assertIn(os.path.realpath(seen["env"]["CODEX_HOME"]), env_args[0])
        args_value = [a for a in argv if a.startswith("mcp_servers.agents_inc.args=")][0].split("=", 1)[1]
        self.assertEqual(json.loads(args_value)[-2:], ["--home-repo", "/home/repo"])

    def test_lead_args_codex_home_quoting_guard(self):
        with self.assertRaises(ValueError):
            runtime.lead_args("terra", self.root, None, Path('/bad"home'))

    def test_broker_codex_worker_gets_isolated_home_and_deny(self):
        run_dir = self.root / "worker-run"
        run_dir.mkdir()
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["env"] = argv, kw["env"]
            return SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        err = io.StringIO()
        with mock.patch.object(runtime, "load_model_map", return_value={"sol": "gpt-5.6-sol"}), \
                mock.patch.object(runtime.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(Path, "is_file", lambda self_: True if self_.name in ("auth.json", "codex") else os.path.isfile(self_)), \
                mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", err):
            rc = runtime.run_codex("sol", "medium", self.root, io.StringIO("p"), SimpleNamespace(codex_path=Path("/x/codex")),
                                   {"gpt-5.6-sol": ["medium"]}, env={"PATH": "/usr/bin"},
                                   extra_deny=(run_dir.resolve(),), isolate_home=True)
        self.assertEqual(rc, 0)
        self.assertIn("CODEX_HOME", seen["env"])
        self.assertEqual(seen["env"]["PATH"], "/usr/bin")
        joined = " ".join(seen["argv"])
        self.assertIn(f'"{os.path.realpath(run_dir)}"="none"', joined)
        self.assertIn(f'"{os.path.realpath(seen["env"]["CODEX_HOME"])}"="none"', joined)
        self.assertNotIn("mcp_servers.agents_inc", joined)
        self.assertIn('"codex_home": "isolated"', err.getvalue())
        self.assertNotIn('"transport"', err.getvalue())
        self.assertFalse(Path(seen["env"]["CODEX_HOME"]).exists())

    def test_auth_replaced_by_regular_file_keeps_home_and_fails(self):
        run_dir = self.root / "lead-run"
        run_dir.mkdir()
        homes = []

        def fake_run(argv, **kw):
            home = Path(kw["env"]["CODEX_HOME"])
            homes.append(home)
            (home / "auth.json").unlink()
            (home / "auth.json").write_text("rewritten by codex")  # atomic-rename style replacement
            return SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        with mock.patch.object(runtime.subprocess, "run", side_effect=fake_run):
            seen = self._run(run_dir, self.root)
        self.addCleanup(shutil.rmtree, homes[0], True)
        self.assertEqual(seen["rc"], 1)
        self.assertIn("agents-inc run: isolated CODEX_HOME kept: auth.json is no longer a symlink", seen["err"])
        self.assertTrue(homes[0].exists())
        self.assertEqual((self.fake_home / ".codex" / "auth.json").read_text(), "SECRET-NOT-READ")

    def test_permission_profile_extra_deny(self):
        grants = runtime.permission_profile(Path("/w"), False, home=self.fake_home, extra_deny=(self.root / "h",))
        self.assertEqual(grants[f'"{os.path.realpath(self.root / "h")}"'], "none")


if __name__ == "__main__":
    unittest.main()


class BrokerProtocolHygieneTest(unittest.TestCase):
    """Spec 018 wave 1 (DomI specs/consumers/agents_Inc/specs/018-mcp-channel-hygiene): FR-001, FR-002, FR-007, FR-009."""

    setUp, _client, _slots = McpBrokerTest.setUp, McpBrokerTest._client, McpBrokerTest._slots

    STATUS_KEYS = ["workers_spawned", "request_counts", "fan_out", "remaining_total", "worker_models"]

    def _init(self, c, asked):
        params = {} if asked is None else {"protocolVersion": asked}
        return c.call("initialize", params)["result"]

    def test_initialize_negotiates_version(self):
        c = self._client()
        for asked in ("2025-06-18", "2024-11-05"):
            self.assertEqual(self._init(c, asked)["protocolVersion"], asked)
        for asked in ("2099-01-01", "2026-07-28", "", 20250618, None):
            self.assertEqual(self._init(c, asked)["protocolVersion"], "2025-06-18", asked)
        self.assertEqual(mcp_broker.SUPPORTED_VERSIONS, ("2025-06-18", "2024-11-05"))

    def test_tools_list_has_output_schema_only_at_2025_06_18(self):
        c = self._client()
        self._init(c, "2025-06-18")
        tools = {t["name"]: t for t in c.call("tools/list")["result"]["tools"]}
        for name, tool in tools.items():
            schema = tool["outputSchema"]
            self.assertEqual(schema["type"], "object", name)
            want = self.STATUS_KEYS if name == "status" else ["status"]
            self.assertEqual(schema["required"], want, name)
        self._init(c, "2024-11-05")
        for tool in c.call("tools/list")["result"]["tools"]:
            self.assertNotIn("outputSchema", tool)

    def test_structured_result_matches_text(self):
        c = self._client()
        self._init(c, "2025-06-18")
        schemas = {t["name"]: t["outputSchema"] for t in c.call("tools/list")["result"]["tools"]}
        calls = (("status", {}), ("wait", {"request_id": "never1", "timeout": 0}),
                 ("answer", {"request_id": "never1", "question_n": 1, "text": "x"}))
        for name, args in calls:
            res = c.call("tools/call", {"name": name, "arguments": args})["result"]
            self.assertEqual(json.loads(res["content"][0]["text"]), res["structuredContent"], name)
            self._conforms(res["structuredContent"], schemas[name], name)
        self._init(c, "2024-11-05")
        for name, args in calls:
            res = c.call("tools/call", {"name": name, "arguments": args})["result"]
            self.assertNotIn("structuredContent", res, name)
            json.loads(res["content"][0]["text"])

    JSON_TYPES = {"string": str, "integer": int, "object": dict, "array": list}

    def _conforms(self, data, schema, name):
        """MCP 2025-06-18 server/tools: structured results MUST conform to the declared outputSchema."""
        for key in schema["required"]:
            self.assertIn(key, data, (name, key))
        for key, prop in schema["properties"].items():
            if key in data:
                self.assertIsInstance(data[key], self.JSON_TYPES[prop["type"]], (name, key))

    def test_structured_content_only_when_it_conforms(self):
        (self.run_dir / "run.json").write_text("{broken")  # status then fails: its error body lacks the five keys
        c = PipeClient(self.run_dir)
        self.addCleanup(c.close)
        self._init(c, "2025-06-18")
        res = c.call("tools/call", {"name": "status", "arguments": {}})["result"]
        self.assertTrue(res["isError"])
        self.assertNotIn("structuredContent", res)
        json.loads(res["content"][0]["text"])

    def test_no_tasks_capability_declared(self):
        c = self._client()
        for asked in ("2025-06-18", "2024-11-05"):
            self.assertNotIn("tasks", self._init(c, asked)["capabilities"])
            for tool in c.call("tools/list")["result"]["tools"]:
                self.assertNotIn("execution", tool)

    def _refused_ids(self, n):
        c = self._client(total=n)
        rids = []
        for _ in range(n):
            data, _ = c.tool("dispatch", {"model": "nope", "effort": "low", "slots": self._slots()})
            rids.append(data["request_id"])
        c.close()
        return rids

    def test_issued_ids_survive_restart(self):
        rids = self._refused_ids(5)
        self.assertTrue((self.run_dir / "issued").is_dir())
        broker = mcp_broker.Broker(self.run_dir)  # a new process on the same run dir
        for rid in rids:
            data, _, _ = broker.tool_wait({"request_id": rid, "timeout": 0})
            self.assertEqual((data["status"], data["reason"]), ("refused", "model-not-allowed"), rid)
        data, _, _ = broker.tool_answer({"request_id": rids[0], "question_n": 1, "text": "x"})
        self.assertEqual(data["reason"], "unknown-question")  # known id; it simply asked nothing
        data, _, _ = broker.tool_resume({"request_id": rids[0], "message": "go on"})
        self.assertEqual(data["reason"], "not-resumable")  # known id; a refused turn cannot resume
        spec = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual(spec["workers_spawned"], 0)

    def test_unrecorded_id_still_refused(self):
        self._client().close()
        planted = ["plant1", "plant2", "plant3", "plant4", "plant5"]
        for rid in planted:
            (self.run_dir / f"{rid}.result.json").write_text(json.dumps({"status": "green"}))
        broker = mcp_broker.Broker(self.run_dir)
        for rid in planted:
            data, _, _ = broker.tool_wait({"request_id": rid, "timeout": 0})
            self.assertEqual(data["reason"], "unknown-request", rid)
        # a link planted as a record, or a linked issued/ dir, never makes an id known
        issued = self.run_dir / "issued"
        issued.mkdir(exist_ok=True)
        target = self.root / "elsewhere"
        target.write_text("")
        os.symlink(target, issued / "plant1")
        self.assertEqual(mcp_broker.Broker(self.run_dir).tool_wait(
            {"request_id": "plant1", "timeout": 0})[0]["reason"], "unknown-request")
        shutil.rmtree(issued)
        other = self.root / "other-issued"
        other.mkdir()
        (other / "plant2").write_text("")
        os.symlink(other, issued)
        self.assertEqual(mcp_broker.Broker(self.run_dir).tool_wait(
            {"request_id": "plant2", "timeout": 0})[0]["reason"], "unknown-request")
