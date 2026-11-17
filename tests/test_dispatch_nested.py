"""D60: Claude Leads (fable, opus, sonnet) spawn Workers through the broker under parent authority. Writes only to temp dirs;
launch is always patched, so no model runs."""
from __future__ import annotations
import contextlib
import fnmatch
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch, mcp_broker, runtime
from tests.test_dispatch_grants import EXAMPLE, GOOD_REPORT, GrantsBase
from tests.test_dispatch_broker import popen_from_run
from tests.test_mcp_broker import PipeClient

FAN = "width 1, total 2, depth 1"
ZERO = {"width": 0, "total": 0, "depth": 0}

_ALLOW = mock.patch.dict(os.environ, {dispatch.ALLOW_SANDBOXED_ENV: "1"})


def setUpModule():
    _ALLOW.start()  # #94: real launch() calls stay allowed when the suite runs inside a sandbox


def tearDownModule():
    _ALLOW.stop()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class NestedBase(GrantsBase):
    """Dispatch a Claude Lead with a patched launch; keep what the launch saw (kwargs, prompt, run.json, token)."""

    def setUp(self):
        super().setUp()
        sb = mock.patch.object(dispatch, "sandbox_available", return_value=True)
        sb.start()
        self.addCleanup(sb.stop)
        self.hook = None

    def _fake(self, report=GOOD_REPORT, rc=0):
        def fake(kind, model, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, **kw):
            call = dict(kw, kind=kind, model=model, prompt=prompt, run_dir=Path(run_dir), resume=resume,
                        cwd=Path(cwd), permission_mode=permission_mode)
            lead = kw.get("lead_dir")
            if lead is not None:
                self.addCleanup(shutil.rmtree, str(lead), True)
                cfg = Path(lead) / "lead_mcp.json"
                if cfg.is_file():
                    call["mcp"] = json.loads(cfg.read_text())["mcpServers"]["agents_inc"]
                    call["token"] = call["mcp"]["env"]["AGENTS_INC_PARENT_TOKEN"]
                    call["mcp_mode"] = cfg.stat().st_mode & 0o777
                if (Path(run_dir) / "run.json").is_file():
                    call["parent_at_launch"] = json.loads((Path(run_dir) / "run.json").read_text())
            self.calls.append(call)
            if self.hook:
                self.hook(call)
            return {"rc": rc, "stdout": report, "stderr": "", "argv": ["x"], "session_id": "sess-1"}
        return fake

    def _lead(self, model="opus", allow="haiku", fan=FAN, report=GOOD_REPORT, **slots):
        slots.setdefault("ALLOWLIST", allow)
        slots.setdefault("FAN_OUT", fan)
        return self._dispatch(model, report, **slots)

    def _parts(self, **kw) -> dict:
        """One real Claude Lead dispatch; return what a broker needs to check its parent."""
        rc, out, _ = self._lead(**kw)
        self.assertEqual(rc, 4, out)
        call = self.calls[0]
        lead = Path(call["lead_dir"])
        return {"call": call, "lead": lead, "run_dir": self._run_dir(), "token": call["token"],
                "spec": json.loads((lead / "run.json").read_text()),
                "env": {"AGENTS_INC_PARENT_RUN": call["mcp"]["env"]["AGENTS_INC_PARENT_RUN"],
                        "AGENTS_INC_PARENT_TOKEN": call["token"]}}

    def _check(self, p, env=None):
        spec = json.loads((p["lead"] / "run.json").read_text())
        return dispatch.check_parent(spec, p["env"] if env is None else env, p["lead"])


class LeadSetupTest(NestedBase):
    def test_claude_lead_roster_follows_rungs(self):
        fan = {"width": 1, "total": 2, "depth": 1}
        allow = {"ALLOWLIST": "opus, sonnet, haiku"}
        self.assertEqual(sorted(dispatch.lead_roster("fable", allow, fan)), ["haiku", "opus", "sonnet"])
        self.assertEqual(sorted(dispatch.lead_roster("opus", allow, fan)), ["haiku", "sonnet"])
        self.assertEqual(dispatch.lead_roster("sonnet", allow, fan), ["haiku"])  # Workhorse: Grunt only
        self.assertEqual(dispatch.lead_roster("haiku", allow, fan), [])
        self.assertEqual(dispatch.lead_roster("opus", allow, dict(fan, depth=0)), [])
        self.assertEqual(dispatch.lead_roster("sol", {"ALLOWLIST": "luna, haiku"}, dict(fan, depth=0)),
                         ["luna", "haiku"])  # Codex: depth is not required (D57)

    def test_claude_lead_gets_exact_mcp_grants_and_denies(self):
        p = self._parts()
        spec, lead = self._spec(), p["lead"]
        tools = ["mcp__agents_inc__dispatch", "mcp__agents_inc__status", "mcp__agents_inc__wait",
                 "mcp__agents_inc__resume", "mcp__agents_inc__answer"]
        self.assertEqual(spec["allowed_tools"][-5:], tools)
        self.assertEqual(spec["allowed_tools"][:-5].count("mcp__agents_inc__dispatch"), 0)
        sibling = f"/{Path(lead).parent}/agents-inc-lead-*/**"
        self.assertEqual(spec["disallowed_tools"][-4:], ["Agent", "Task", f"Read({sibling})", f"Edit({sibling})"])
        self.assertTrue(fnmatch.fnmatch(f"/{lead}/lead_mcp.json", sibling))  # the Lead's own directory stays covered
        self.assertFalse(any("agents-inc" in r for r in spec["allowed_tools"]))
        self.assertEqual(p["call"]["allowed_tools"], spec["allowed_tools"])
        self.assertEqual(p["call"]["disallowed_tools"], spec["disallowed_tools"])
        self.assertEqual((spec["lead_workers"], spec["lead_dir"]), (["haiku"], str(lead)))

    def test_no_lead_when_total_zero_or_allowlist_none(self):
        cases = (({"ALLOWLIST": "haiku", "FAN_OUT": "width 0, total 0, depth 0"}, "total-zero"),
                 ({"ALLOWLIST": "none -- do all work yourself", "FAN_OUT": FAN}, "no-roster"),
                 ({"ALLOWLIST": "haiku", "FAN_OUT": "width 1, total 2, depth 0"}, "depth-zero"))
        for slots, why in cases:
            with self.subTest(why=why):
                self.tearDown(), self.setUp()
                rc, out, _ = self._dispatch("opus", **slots)
                self.assertEqual(rc, 4, out)
                spec = self._spec()
                self.assertEqual(spec["lead_skipped"], why)
                self.assertNotIn("lead_dir", spec)
                self.assertFalse(any(r.startswith("mcp__") for r in spec["allowed_tools"]))
                self.assertNotIn("lead_dir", self.calls[0])
        self.tearDown(), self.setUp()
        self._dispatch("haiku", ALLOWLIST="haiku", FAN_OUT=FAN)
        self.assertNotIn("lead_skipped", self._spec())  # a Grunt is never a Lead candidate

    def test_no_lead_under_bypass_permissions(self):
        rc, out, _ = self._lead(PERMISSION_MODE="bypassPermissions")
        self.assertEqual(rc, 4, out)
        spec = self._spec()
        self.assertEqual(spec["lead_skipped"], "bypass-permissions")
        self.assertNotIn("lead_dir", spec)
        self.assertFalse(any(r.startswith("mcp__") for r in spec["allowed_tools"]))
        self.assertNotIn("lead_dir", self.calls[0])

    def test_lead_argv_has_mcp_config_and_strict_flag(self):
        p = self._parts()
        lead, mcp = p["lead"], p["call"]["mcp"]
        done = subprocess.CompletedProcess([], 0, stdout=json.dumps({"result": "r", "session_id": "s"}), stderr="")
        run = mock.Mock(return_value=done)
        with mock.patch.object(dispatch.subprocess, "Popen", side_effect=popen_from_run(run)):
            dispatch.launch("claude", "opus", None, self.repo, "P", self.runs, "acceptEdits", lead_dir=lead,
                            allowed_tools=["Read"], disallowed_tools=["Agent"])
        argv, env = run.call_args.args[0], run.call_args.kwargs["env"]
        at = argv.index("--mcp-config")
        self.assertEqual(argv[at:at + 3], ["--mcp-config", str(lead / "lead_mcp.json"), "--strict-mcp-config"])
        self.assertEqual(env["MCP_TOOL_TIMEOUT"], str(runtime.MCP_TOOL_TIMEOUT_SEC * 1000))
        self.assertEqual((mcp["type"], mcp["command"]), ("stdio", sys.executable))
        self.assertEqual(mcp["args"][:3], [str(runtime.MCP_BROKER), "--run-dir", str(lead)])
        self.assertEqual(sorted(mcp["env"]), ["AGENTS_INC_PARENT_RUN", "AGENTS_INC_PARENT_TOKEN"])
        self.assertEqual(mcp["timeout"], runtime.MCP_TOOL_TIMEOUT_SEC * 1000)
        self.assertEqual(p["call"]["mcp_mode"], 0o600)

    def test_lead_dir_outside_cwd(self):
        spec = {"run_id": "r1", "model": "opus", "effort": None, "cwd": str(self.repo), "chain": ["CoS", "opus"],
                "fan_out": {"width": 1, "total": 2, "depth": 1}, "permission_mode": "acceptEdits"}
        with mock.patch.object(tempfile, "tempdir", str(self.repo)):
            with self.assertRaisesRegex(ValueError, "lead-dir-inside-cwd"):
                dispatch.make_lead_dir(spec, ["haiku"], {"run_dir": self.runs, "allowed_tools": [], "disallowed_tools": []})
        self.assertEqual([p for p in self.repo.iterdir() if p.name != ".git"], [])  # the refused dir is removed

    def test_parent_run_json_written_before_launch(self):
        p = self._parts()
        at, token = p["call"]["parent_at_launch"], p["token"]
        self.assertEqual(at["lead_token_sha256"], _sha(token))
        self.assertEqual(at["lead_dir"], str(p["lead"]))
        for name in ("run.json", "prompt.md", "stdout.md", "stderr.txt"):
            self.assertNotIn(token, (p["run_dir"] / name).read_text(), name)
        self.assertNotIn(token, json.dumps(at))

    def test_lead_spec_binds_parent(self):
        p = self._parts()
        spec, parent = p["spec"], self._spec()
        self.assertEqual(spec["parent_run_id"], parent["run_id"])
        self.assertEqual(spec["parent_run_dir"], os.path.realpath(p["run_dir"]))
        self.assertEqual(spec["parent_token_sha256"], parent["lead_token_sha256"])
        self.assertEqual(spec["parent_token_sha256"], _sha(p["token"]))
        self.assertEqual(spec["cwd"], parent["cwd"])
        self.assertEqual(spec["lead_kind"], "claude")
        base = [r for r in parent["allowed_tools"] if not r.startswith("mcp__agents_inc__")]
        self.assertEqual(spec["parent_allowed_tools"], base)  # the five broker tools are not part of a Worker's ceiling
        self.assertEqual(spec["parent_disallowed_tools"], parent["disallowed_tools"][:-2])
        self.assertEqual(spec["worker_models"], ["haiku"])

    def test_claude_lead_note_in_prompt(self):
        p = self._parts()
        for text in (p["call"]["prompt"], (p["run_dir"] / "prompt.md").read_text()):
            self.assertIn("WORKERS (D60)", text)
            self.assertIn("mcp__agents_inc__dispatch", text)
            self.assertNotIn("WORKERS (D57)", text)
            self.assertNotIn("tool_search", text)


class CheckParentTest(NestedBase):
    @contextlib.contextmanager
    def _mutate(self, path: Path, text: str):
        original = path.read_text()
        path.write_text(text)
        try:
            yield
        finally:
            path.write_text(original)

    def test_check_parent_ok(self):
        self.assertIsNone(self._check(self._parts()))

    def test_check_parent_env_missing(self):
        p = self._parts()
        for drop in ("AGENTS_INC_PARENT_RUN", "AGENTS_INC_PARENT_TOKEN"):
            for how in ("unset", "empty"):
                with self.subTest(drop=drop, how=how):
                    env = dict(p["env"])
                    env.pop(drop) if how == "unset" else env.update({drop: ""})
                    self.assertTrue(self._check(p, env).startswith("parent-env-missing:"))

    def test_check_parent_run_missing(self):
        p = self._parts()
        run = p["run_dir"]
        link = self.root / "link"
        link.symlink_to(run)
        cases = {"relative": "rel/run", "absent": str(self.root / "nope"), "symlinked dir": str(link)}
        for name, path in cases.items():
            with self.subTest(case=name):
                self.assertTrue(self._check(p, dict(p["env"], AGENTS_INC_PARENT_RUN=path)).startswith("parent-run-missing:"))
        for name, text in (("bad json", "{nope"), ("not an object", "[1]")):
            with self.subTest(case=name):
                with self._mutate(run / "run.json", text):
                    self.assertTrue(self._check(p).startswith("parent-run-missing:"))
        with self.subTest(case="symlinked run.json"):
            real = run / "real.json"
            (run / "run.json").rename(real)
            (run / "run.json").symlink_to(real)
            self.assertTrue(self._check(p).startswith("parent-run-missing:"))

    def test_check_parent_run_mismatch(self):
        p = self._parts()
        run, parent = p["run_dir"], self._spec()
        for field in ("run_id", "cwd", "lead_dir"):
            with self.subTest(field=field):
                with self._mutate(run / "run.json", json.dumps(dict(parent, **{field: "elsewhere"}))):
                    self.assertTrue(self._check(p).startswith("parent-run-mismatch:"), field)
                    self.assertIn(field, self._check(p))
        with self.subTest(field="parent_run_dir"):
            other = self.root / "copy"
            shutil.copytree(run, other)
            self.assertTrue(self._check(p, dict(p["env"], AGENTS_INC_PARENT_RUN=str(other))).startswith("parent-run-mismatch:"))

    def test_check_parent_token_mismatch(self):
        p = self._parts()
        self.assertTrue(self._check(p, dict(p["env"], AGENTS_INC_PARENT_TOKEN="0" * 64)).startswith("parent-token-mismatch:"))
        with self._mutate(p["run_dir"] / "run.json", json.dumps(dict(self._spec(), lead_token_sha256=_sha("forged")))):
            self.assertTrue(self._check(p).startswith("parent-token-mismatch:"))  # a Lead that edits the parent run only fails closed

    def test_mcp_broker_refuses_all_tools_on_parent_error(self):
        p = self._parts()
        env = {k: v for k, v in os.environ.items() if not k.startswith("AGENTS_INC_PARENT_")}
        (p["lead"] / "inbox").mkdir()
        with mock.patch.dict(os.environ, env, clear=True):
            c = PipeClient(p["lead"])
            self.addCleanup(c.close)
            self.assertIn("result", c.call("initialize", {}))
            self.assertEqual(len(c.call("tools/list")["result"]["tools"]), 5)
            slots = json.loads(EXAMPLE.read_text())
            for name, args in (("dispatch", {"model": "haiku", "effort": "low", "slots": slots}), ("status", {}),
                               ("wait", {"request_id": "r1", "timeout": 0})):
                with self.subTest(tool=name):
                    data, is_error = c.tool(name, args)
                    self.assertTrue(is_error)
                    self.assertEqual((data["status"], data["reason"]), ("refused", "parent-env-missing"))
        self.assertIn("parent refused:parent-env-missing", (p["lead"] / "mcp.log").read_text())
        good = dict(env, **p["env"])  # control: the right env gets through the same server
        with mock.patch.dict(os.environ, good, clear=True):
            c2 = PipeClient(p["lead"])
            self.addCleanup(c2.close)
            data, is_error = c2.tool("status")
        self.assertFalse(is_error, data)
        self.assertEqual(data["workers_spawned"], 0)

    def test_codex_lead_without_parent_fields_unchanged(self):
        self.tearDown(), self.setUp()
        rc, out, _ = self._dispatch("terra", ALLOWLIST="haiku", FAN_OUT=FAN)
        self.assertEqual(rc, 4, out)
        call, lead = self.calls[0], Path(self.calls[0]["lead_dir"])
        run = json.loads((lead / "run.json").read_text())
        self.assertNotIn("parent_run_id", run)
        self.assertFalse((lead / "lead_mcp.json").exists())
        self.assertIsNone(self._spec()["allowed_tools"])
        self.assertIn("WORKERS (D57)", call["prompt"])
        (lead / "inbox").mkdir()
        with mock.patch.object(dispatch, "check_parent") as check:
            c = PipeClient(lead)
            self.addCleanup(c.close)
            data, is_error = c.tool("status")
        self.assertFalse(is_error, data)
        check.assert_not_called()


class WorkerRulesTest(NestedBase):
    """The broker side: one real Claude Lead dispatch makes the Lead run directory, then dispatch.serve runs Workers."""

    def setUp(self):
        super().setUp()
        self._new_lead()

    def _new_lead(self, **kw):
        self.runs = self.root / f"runs-{len(list(self.root.glob('runs*')))}"  # _run_dir expects one run per directory
        self.calls.clear()
        self.p = self._parts(**kw)
        self.lead, self.inbox = self.p["lead"], self.p["lead"] / "inbox"
        self.inbox.mkdir()
        self.calls.clear()

    def _request(self, rid, model="haiku", tier="grunt", drop=(), **slots):
        data = json.loads(EXAMPLE.read_text())
        data.update(slots)
        for key in drop:
            data.pop(key)
        req = {"schema_version": 1, "request_id": rid, "model": model, "effort": "low", "tier": tier, "slots": data}
        final = self.inbox / f"{rid}.request.json"
        tmp = final.with_name(final.name + ".tmp")
        tmp.write_text(json.dumps(req))
        os.rename(tmp, final)

    def _serve(self, **kw):
        (self.inbox / "lead.done").write_text("")
        with mock.patch.object(dispatch, "launch", side_effect=self._fake(**kw)), contextlib.redirect_stderr(io.StringIO()):
            return dispatch.serve(self.lead, poll_interval=0.01, idle_timeout=5)

    def _result(self, rid):
        return json.loads((self.lead / f"{rid}.result.json").read_text())

    def _lead_spec(self):
        return json.loads((self.lead / "run.json").read_text())

    def _child(self, rid) -> dict:
        res = self._result(rid)
        return json.loads((self.lead / "workers" / rid / "runs" / res["child_run_id"] / "run.json").read_text())

    def test_worker_fan_out_nonzero_refused(self):
        for i, fan in enumerate(("width 1, total 1, depth 1", "width 0, total 0, depth 1", "lots")):
            self._request(f"f{i}", FAN_OUT=fan)
        self.assertEqual(self._serve(), 0)
        for i in range(3):
            res = self._result(f"f{i}")
            self.assertEqual((res["status"], res["dispatch_exit_code"], res["reason"]), ("refused", 3, "worker-cannot-lead"))
        self.assertEqual(self.calls, [])
        self.assertEqual(self._lead_spec()["workers_spawned"], 0)  # no reservation consumed

    def test_worker_fan_out_absent_filled_zero(self):
        self._request("a1", drop=("FAN_OUT",))
        self._serve()
        self.assertEqual(self._result("a1")["status"], "unverified")
        self.assertEqual(self._child("a1")["fan_out"], ZERO)
        self.assertIn("FAN_OUT: width 0, total 0, depth 0", self.calls[0]["prompt"])

    def test_child_grants_subset_of_parent(self):
        gate = [sys.executable, "-c", "print(1)"]
        self._request("g1", FILES_IN_SCOPE="agents_inc/x.py\ntests/", GATES=json.dumps([{"argv": gate}]))
        self._serve()
        self.assertEqual(self._result("g1")["status"], "unverified", self._result("g1"))
        child, lead = self.calls[0], self._lead_spec()
        allowed = child["allowed_tools"]
        self.assertNotIn("Bash(pytest)", allowed)  # the parent holds no runner, so the child gets none
        self.assertNotIn("Bash(python3 -m unittest)", allowed)
        self.assertFalse(any(" -c print(1)" in r or "print(1)" in r for r in allowed))  # no gate argv rule
        self.assertTrue(all(r in lead["parent_allowed_tools"] or r.startswith("Bash(python3 ") and "pre_dispatch_snapshot.py" in r
                            for r in allowed), allowed)
        self.assertTrue(set(lead["parent_disallowed_tools"]) <= set(child["disallowed_tools"]))
        self.assertFalse(any(r in dispatch.LEAD_TOOLS for r in allowed))

    def test_render_refusal_reaches_lead_result(self):
        with mock.patch.object(dispatch, "render", return_value=(2, "", "slot CONSTRAINTS missing\n")):
            self._request("rr1")
            self.assertEqual(self._serve(), 0)
        res = self._result("rr1")
        self.assertEqual(res["outcome"], "refused-render")
        self.assertIn("slot CONSTRAINTS missing", res["status_line"])
        self.assertIn("slot CONSTRAINTS missing", res["reason_detail"])

    def test_worker_pre_existing_changes_is_broker_owned(self):
        lead_cmd = (f"snapshot {self.lead}/snapshot.json; verify with `python3 {self.lead}/pre_dispatch_snapshot.py "
                    f"verify {self.lead}/snapshot.json`")
        self._request("pe1", PRE_EXISTING_CHANGES=lead_cmd)
        self.assertEqual(self._serve(), 0)
        res = self._result("pe1")
        self.assertNotEqual(res.get("outcome"), "refused-render", res)
        self.assertEqual(len(self.calls), 1)
        prompt = self.calls[0]["prompt"]
        lines = [ln for ln in prompt.splitlines() if "verify with `" in ln]
        self.assertEqual(len(lines), 1, prompt)
        self.assertIn("python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify", lines[0])
        self.assertNotIn(f"{self.lead}/snapshot.json", lines[0])
        self.assertNotIn(f"{self.lead}/pre_dispatch_snapshot.py", lines[0])
        self.assertIn("/workers/pe1/runs/", lines[0])

    def test_child_grant_exceeding_parent_refused(self):
        run = self.lead / "run.json"
        spec = json.loads(run.read_text())
        spec["parent_allowed_tools"].remove("Read")
        run.write_text(json.dumps(spec))
        self._request("x1")
        self.assertEqual(self._serve(), 0)
        res = self._result("x1")
        self.assertEqual((res["status"], res["dispatch_exit_code"], res["outcome"]), ("refused", 3, "refused-grants"))
        self.assertEqual(self.calls, [])
        after = self._lead_spec()
        self.assertEqual((after["workers_spawned"], after["request_counts"]["refused"]), (0, 1))  # reservation released
        lint = next((self.lead / "workers" / "x1" / "runs").iterdir()) / "lint.txt"
        self.assertIn("grant-exceeds-parent: Read is not granted to the parent run", lint.read_text())

    def test_child_permission_mode_is_parent_mode(self):
        self._new_lead(PERMISSION_MODE="default")
        self._request("m1")
        self._request("m2", PERMISSION_MODE="bypassPermissions")
        self._serve()
        self.assertEqual(self._lead_spec()["permission_mode"], "default")
        self.assertEqual(self._child("m1")["permission_mode"], "default")
        self.assertEqual(self.calls[0]["permission_mode"], "default")
        self.assertEqual(self._result("m2")["reason"], "broker-owned-slot")

    def test_child_cwd_is_parent_cwd(self):
        self._request("c1")
        self._serve()
        self.assertEqual(self._child("c1")["cwd"], str(self.repo))
        self.assertEqual(self.calls[0]["cwd"], self.repo)

    def test_total_cap_counts_against_parent(self):
        for rid in ("t1", "t2", "t3"):
            self._request(rid)
        self._serve()
        self.assertEqual(self._result("t1")["status"], "unverified")
        self.assertEqual(self._result("t2")["status"], "unverified")
        self.assertEqual((self._result("t3")["status"], self._result("t3")["reason"]), ("refused", "fan-out-total-exhausted"))
        self.assertEqual(self._lead_spec()["workers_spawned"], 2)

    def test_broker_worker_never_gets_dispatch_tools(self):
        self._request("d1")
        self._serve()
        self.assertFalse(set(self.calls[0]["allowed_tools"]) & set(dispatch.LEAD_TOOLS))
        self.assertNotIn("lead_dir", self.calls[0])
        # a grant list that did carry one is a bug, not a request error: the run raises and the reservation is released
        self._new_lead()
        self._request("d2")
        with mock.patch.object(dispatch, "tool_grants", return_value=(["Read", dispatch.LEAD_TOOLS[0]], [])):
            self._serve()
        res = self._result("d2")
        self.assertEqual(res["reason"], "dispatch-exception:RuntimeError")
        self.assertEqual(self.calls, [])
        self.assertEqual(self._lead_spec()["workers_spawned"], 0)


class RecordingTest(NestedBase):
    def _broker_wrote(self, spawned=1):
        """Launch hook: the broker did its work during the Lead turn."""
        def hook(call):
            lead = Path(call["lead_dir"])
            run = json.loads((lead / "run.json").read_text())
            run["workers_spawned"] = spawned
            (lead / "run.json").write_text(json.dumps(run))
            child = lead / "workers" / "r1" / "runs" / "c1"
            child.mkdir(parents=True)
            (child / "run.json").write_text(json.dumps({"run_id": "c1", "model": "haiku"}))
            (lead / "r1.result.json").write_text(json.dumps(
                {"request_id": "r1", "child_run_id": "c1", "status": "unverified", "outcome": "unverified"}))
        self.hook = hook

    def test_parent_links_children(self):
        home = self.root / "home"
        home.mkdir()
        self._broker_wrote()
        report = GOOD_REPORT.replace("WORKERS SPAWNED: 0", "WORKERS SPAWNED: 1")
        with mock.patch.dict(os.environ, {"AGENTS_INC_HOME_REPO": str(home)}):
            rc, out, _ = self._lead(report=report)
        self.assertEqual(rc, 4, out)
        want = [{"request_id": "r1", "child_run_id": "c1", "model": "haiku", "status": "unverified", "outcome": "unverified"}]
        spec = self._spec()
        self.assertEqual((spec["children"], spec["broker_workers_spawned"]), (want, 1))
        mirrored = next(home.glob("specs/consumers/*/runs/*/run.json"))
        self.assertEqual(json.loads(mirrored.read_text())["children"], want)

    def test_underreported_workers_spawned_is_red(self):
        self._broker_wrote()
        rc, out, _ = self._lead()  # the report says WORKERS SPAWNED: 0, the broker ran one
        self.assertEqual(rc, 1, out)
        spec = self._spec()
        self.assertEqual((spec["outcome"], spec["reason"]), ("red", "workers-spawned-underreported"))
        self.assertEqual(spec["broker_workers_spawned"], 1)

    def test_resume_lead_reattaches_mcp_config(self):
        rc, out, _ = self._lead()
        self.assertEqual(rc, 4, out)
        spec, first = self._spec(), self.calls[0]
        with mock.patch.object(dispatch, "launch", side_effect=self._fake()):
            rc, out, _ = self._main("--resume", spec["run_id"], "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, 4, out)
        again = self.calls[1]
        self.assertEqual(again["resume"], "sess-1")
        self.assertEqual(again["lead_dir"], Path(spec["lead_dir"]))
        self.assertEqual((again["allowed_tools"], again["disallowed_tools"]), (spec["allowed_tools"], spec["disallowed_tools"]))
        self.assertEqual(again["mcp"], first["mcp"])  # same broker config, same token

    def test_resume_lead_dir_missing_refused(self):
        rc, out, _ = self._lead()
        self.assertEqual(rc, 4, out)
        spec = self._spec()
        (Path(spec["lead_dir"]) / "lead_mcp.json").unlink()
        with mock.patch.object(dispatch, "launch", side_effect=self._fake()):
            rc, out, err = self._main("--resume", spec["run_id"], "--message", "go on", "--run-dir", str(self.runs))
        self.assertEqual(rc, 2, out)
        self.assertIn("lead-dir-missing:", err)
        self.assertEqual(len(self.calls), 1)  # no second launch


if __name__ == "__main__":
    unittest.main()
