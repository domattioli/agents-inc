"""Spec 016 FR-004 (#36): host hook dispatch rows and `agents-inc ledger append`.

Supervisor-owned acceptance tests. Fake home and temp dirs only; never touches the live state dir.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc import host_ledger, ledger
from agents_inc.install.paths import InstallPaths

VERDICT_MSG = "agents-inc ledger append: --verdict pass|fail is required; a delegate self-report is not a verdict"


def agent_payload(tool_use_id="toolu_A1", model="haiku", cwd=None, session="S1"):
    return {"session_id": session, "tool_name": "Agent", "tool_use_id": tool_use_id, "cwd": cwd,
            "tool_input": {"description": "Grunt haiku: fix parser", "prompt": "do it", "model": model}}


def delegate_payload(tool_use_id="toolu_D1", model="luna", cwd=None):
    return {"session_id": "S1", "tool_name": "mcp__delegate-agent__DelegateAgent", "tool_use_id": tool_use_id,
            "cwd": cwd, "tool_input": {"prompt": "Review the hook diff\nmore lines " + "x" * 200, "model": model}}


class _Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paths = InstallPaths.for_home(self.root / "home")
        self.project = self.root / "project"
        self.project.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def host_ws(self):
        return host_ledger.host_workspace(self.paths.state)

    def rows(self):
        path = self.host_ws() / ".workerbees" / "ledger.jsonl"
        if not path.exists():
            return []
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = host_ledger.cli(list(argv), self.paths.state)
        return rc, out.getvalue(), err.getvalue()


class HookRowTest(_Home):
    def test_native_luna_agent_call_gets_no_hook_row_and_other_types_still_do(self):
        # Spec 028 FR-026: `agents-inc luna begin` writes that agent's row; the hook would add a second, labelled claude.
        native = agent_payload("toolu_N1")
        native["tool_input"]["subagent_type"] = "agents-inc:luna"
        self.assertIsNone(host_ledger.dispatch_row(native))
        self.assertFalse(host_ledger.record_hook_dispatch(self.paths.state, native))
        self.assertEqual(self.rows(), [])
        for subagent in ("general-purpose", "x-agents-inc:luna", None):
            with self.subTest(subagent=subagent):
                other = agent_payload("toolu_O1")
                if subagent: other["tool_input"]["subagent_type"] = subagent
                self.assertEqual(host_ledger.dispatch_row(other)["provider"], "claude")

    def test_host_workspace_is_under_state_dir(self):
        self.assertEqual(self.host_ws(), self.paths.state / "host-ledger")

    def test_agent_payload_writes_one_node_shaped_row(self):
        self.assertTrue(host_ledger.record_hook_dispatch(self.paths.state, agent_payload(cwd=str(self.project))))
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        for field in ("id", "run_id", "model", "tier", "task", "provider", "parent_id", "edge_type", "status",
                      "seconds", "subscription_calls", "gate_reason", "timestamp"):
            self.assertIn(field, r)
        self.assertEqual((r["id"], r["run_id"], r["model"], r["tier"], r["provider"], r["status"]),
                         ("toolu_A1", "S1", "haiku", "grunt", "claude", "dispatched"))
        self.assertEqual(r["task"], "Grunt haiku: fix parser")
        self.assertIsNone(r["parent_id"])
        self.assertEqual(r["source"], "host-hook")
        self.assertEqual(r["cwd"], str(self.project))
        for field in ("input_tokens", "output_tokens", "cache_read", "cache_write"):
            self.assertIn(field, r)
            self.assertIsNone(r[field], field)
        self.assertFalse((self.project / ".workerbees").exists())

    def test_delegate_agent_payload_writes_codex_row(self):
        self.assertTrue(host_ledger.record_hook_dispatch(self.paths.state, delegate_payload(cwd=str(self.project))))
        r = self.rows()[0]
        self.assertEqual((r["id"], r["provider"], r["model"], r["tier"]), ("toolu_D1", "codex", "luna", "grunt"))
        self.assertEqual(r["task"], "Review the hook diff")
        self.assertFalse((self.project / ".workerbees").exists())

    def test_delegate_agent_task_is_capped_at_80_chars(self):
        p = delegate_payload()
        p["tool_input"]["prompt"] = "y" * 300
        host_ledger.record_hook_dispatch(self.paths.state, p)
        self.assertEqual(len(self.rows()[0]["task"]), 80)

    def test_agent_without_model_is_unknown_tier(self):
        p = agent_payload()
        del p["tool_input"]["model"]
        host_ledger.record_hook_dispatch(self.paths.state, p)
        r = self.rows()[0]
        self.assertEqual((r["model"], r["tier"]), ("unknown", "unknown"))

    def test_codex_nickname_tier_from_models_json(self):
        host_ledger.record_hook_dispatch(self.paths.state, delegate_payload(model="terra"))
        self.assertEqual(self.rows()[0]["tier"], "workhorse")

    def test_unrelated_or_malformed_payloads_write_nothing(self):
        for bad in ({"tool_name": "Bash", "tool_use_id": "x", "tool_input": {"command": "ls"}},
                    "not a dict", None, [], {"tool_name": "Agent", "tool_input": {"description": "no id"}},
                    {"tool_name": "Agent", "tool_use_id": "z", "tool_input": "oops"}):
            self.assertFalse(host_ledger.record_hook_dispatch(self.paths.state, bad))
        self.assertEqual(self.rows(), [])

    def test_unwritable_state_fails_open(self):
        self.paths.state.parent.mkdir(parents=True, exist_ok=True)
        self.paths.state.write_text("not a directory")
        self.assertFalse(host_ledger.record_hook_dispatch(self.paths.state, agent_payload()))

    def test_lint_reports_no_finding_for_hook_rows(self):
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload("toolu_1", "haiku"))
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload("toolu_2", "sonnet"))
        host_ledger.record_hook_dispatch(self.paths.state, delegate_payload("toolu_3", "luna"))
        loaded = ledger.load(self.host_ws())
        self.assertEqual(len(loaded.nodes), 3)
        self.assertEqual(ledger.lint(loaded), [])


class AppendCliTest(_Home):
    def test_missing_verdict_fails_closed(self):
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload())
        before = len(self.rows())
        rc, _, err = self.run_cli("append", "--node-id", "toolu_A1")
        self.assertEqual(rc, 2)
        self.assertIn(VERDICT_MSG, err)
        self.assertEqual(len(self.rows()), before)

    def test_unknown_node_without_run_id_fails_closed(self):
        rc, _, err = self.run_cli("append", "--node-id", "ghost", "--verdict", "pass")
        self.assertEqual(rc, 2)
        self.assertIn("ghost", err)
        self.assertEqual(self.rows(), [])

    def test_append_writes_return_row_with_run_id_and_verdict(self):
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload())
        rc, _, err = self.run_cli("append", "--node-id", "toolu_A1", "--verdict", "pass", "--seconds", "12.5",
                                  "--effort", "medium", "--input-tokens", "100", "--output-tokens", "20",
                                  "--file-created", "a.py", "--file-created", "b.py")
        self.assertEqual(rc, 0, err)
        last = self.rows()[-1]
        self.assertEqual((last["id"], last["run_id"], last["verdict"], last["status"]),
                         ("toolu_A1", "S1", "pass", "verified"))
        self.assertEqual(last["input_tokens"], 100)
        self.assertIsNone(last["cache_read"])
        self.assertEqual(last["files_created"], ["a.py", "b.py"])
        node = ledger.load(self.host_ws()).nodes["toolu_A1"]
        self.assertEqual((node.verdict, node.run_id, node.model), ("pass", "S1", "haiku"))

    def test_fail_verdict_defaults_status_red(self):
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload())
        rc, _, _ = self.run_cli("append", "--node-id", "toolu_A1", "--verdict", "fail")
        self.assertEqual(rc, 0)
        self.assertEqual(self.rows()[-1]["status"], "red")

    def test_explicit_run_id_and_workspace(self):
        ws = self.root / "other"
        rc, _, err = self.run_cli("append", "--node-id", "n9", "--verdict", "pass", "--run-id", "R9",
                                  "--workspace", str(ws))
        self.assertEqual(rc, 0, err)
        self.assertEqual(ledger.load(ws).nodes["n9"].run_id, "R9")

    def test_bad_verdict_value_rejected(self):
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload())
        before = len(self.rows())
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                rc = host_ledger.cli(["append", "--node-id", "toolu_A1", "--verdict", "PASS"], self.paths.state)
            except SystemExit as exc:
                rc = exc.code
        self.assertNotEqual(rc, 0)
        self.assertEqual(len(self.rows()), before)

    def test_host_ledger_never_creates_sqlite(self):
        import os
        old = os.environ.get("WORKERBEES_STORE")
        os.environ["WORKERBEES_STORE"] = "both"
        try:
            host_ledger.record_hook_dispatch(self.paths.state, agent_payload())
            rc, _, err = self.run_cli("append", "--node-id", "toolu_A1", "--verdict", "pass")
        finally:
            if old is None:
                os.environ.pop("WORKERBEES_STORE", None)
            else:
                os.environ["WORKERBEES_STORE"] = old
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(self.rows()), 2)
        self.assertFalse((self.host_ws() / ".workerbees" / "workerbees.db").exists())

    def test_pending_lists_open_rows_only(self):
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload("toolu_1", "haiku"))
        host_ledger.record_hook_dispatch(self.paths.state, delegate_payload("toolu_2", "luna"))
        self.run_cli("append", "--node-id", "toolu_1", "--verdict", "pass")
        rc, out, _ = self.run_cli("pending")
        self.assertEqual(rc, 0)
        lines = [ln.split("\t") for ln in out.splitlines() if ln.strip()]
        self.assertEqual([ln[0] for ln in lines], ["toolu_2"])
        self.assertEqual(lines[0][1:3], ["luna", "Review the hook diff"])
        self.assertEqual(len(lines[0]), 4)


class IntegrationTest(_Home):
    """RED until T009 (Executive wiring in agents_inc/install/*)."""

    def run_hook(self, raw):
        from agents_inc.install import hook
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return hook.run(self.paths, "agent-done", None, io.StringIO(raw))

    def test_agent_done_hook_writes_rows_for_agent_and_delegate_agent(self):
        self.assertEqual(self.run_hook(json.dumps(agent_payload(cwd=str(self.project)))), 0)
        self.assertEqual(self.run_hook(json.dumps(delegate_payload(cwd=str(self.project)))), 0)
        self.assertEqual([r["id"] for r in self.rows()], ["toolu_A1", "toolu_D1"])
        self.assertFalse((self.project / ".workerbees").exists())

    def test_agent_done_hook_exits_zero_on_garbage(self):
        for raw in ("", "{", "[1]", json.dumps({"tool_name": "mcp__x__DelegateAgent"})):
            self.assertEqual(self.run_hook(raw), 0)

    def test_claude_host_gets_delegate_agent_post_tool_use_entry(self):
        from agents_inc.install import host_wiring
        claude = next(h for h in host_wiring.HOSTS if h.name == "claude")
        config = host_wiring.add_hooks({}, self.paths, claude)
        groups = [g for g in config["hooks"].get("PostToolUse", []) if g.get("matcher") == "mcp__.*__DelegateAgent"]
        self.assertEqual(len(groups), 1)
        self.assertEqual([h["command"] for h in groups[0]["hooks"]],
                         [host_wiring.hook_command(self.paths, "agent-done")])
        self.assertLessEqual(groups[0]["hooks"][0]["timeout"], 5)
        self.assertEqual(host_wiring.strip_hooks(config, self.paths).get("hooks", {}).get("PostToolUse"), None)

    def test_cli_routes_ledger_append(self):
        from agents_inc.install import cli
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload())
        with mock.patch.object(cli, "_paths", return_value=self.paths), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = cli.main(["ledger", "append", "--node-id", "toolu_A1", "--verdict", "pass"])
            rc_missing = cli.main(["ledger", "append", "--node-id", "toolu_A1"])
        self.assertEqual(rc, 0)
        self.assertEqual(rc_missing, 2)
        self.assertEqual(self.rows()[-1]["verdict"], "pass")

    def test_cli_routes_ledger_pending(self):
        from agents_inc.install import cli
        host_ledger.record_hook_dispatch(self.paths.state, agent_payload())
        out = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = cli.main(["ledger", "pending"])
        self.assertEqual(rc, 0)
        self.assertIn("toolu_A1", out.getvalue())

    def test_background_agent_payload_still_writes_row(self):
        p = agent_payload()
        p["tool_input"]["run_in_background"] = True
        self.assertEqual(self.run_hook(json.dumps(p)), 0)
        self.assertEqual([r["id"] for r in self.rows()], ["toolu_A1"])


class DispatchRunNodeTest(_Home):
    SPEC = {"run_id": "20261009T000000Z-haiku-abc123", "kind": "claude", "model": "haiku",
            "effort": "medium", "cwd": "/x"}

    def test_record_dispatch_run_writes_one_node_row(self):
        self.assertTrue(host_ledger.record_dispatch_run(self.paths.state, self.SPEC, "Read-only scout.\nmore"))
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["id"], row["run_id"], row["status"], row["source"]),
                         (self.SPEC["run_id"], self.SPEC["run_id"], "dispatched", "dispatch"))
        self.assertEqual((row["model"], row["provider"], row["tier"], row["task"], row["effort"], row["cwd"]),
                         ("haiku", "claude", "grunt", "Read-only scout.", "medium", "/x"))
        self.assertEqual(ledger.lint(ledger.load(self.host_ws())), [])

    def test_task_capped_and_failure_does_not_raise(self):
        row = host_ledger.dispatch_run_row(self.SPEC, "y" * 300)
        self.assertEqual(len(row["task"]), 80)
        self.paths.state.parent.mkdir(parents=True, exist_ok=True)
        self.paths.state.write_text("not a directory")
        self.assertFalse(host_ledger.record_dispatch_run(self.paths.state, self.SPEC, "t"))

    def test_append_by_run_id_closes_node(self):
        host_ledger.record_dispatch_run(self.paths.state, self.SPEC, "t")
        rc, out, _ = self.run_cli("pending")
        self.assertIn(self.SPEC["run_id"], out)
        rc, _, err = self.run_cli("append", "--run-id", self.SPEC["run_id"], "--verdict", "pass")
        self.assertEqual(rc, 0, err)
        rc, out, _ = self.run_cli("pending")
        self.assertNotIn(self.SPEC["run_id"], out)
        last = self.rows()[-1]
        self.assertEqual((last["id"], last["run_id"], last["verdict"]), (self.SPEC["run_id"], self.SPEC["run_id"], "pass"))

    def test_append_with_neither_id_returns_2(self):
        rc, _, err = self.run_cli("append", "--verdict", "pass")
        self.assertEqual(rc, 2)
        self.assertIn("--node-id or --run-id", err)
        self.assertEqual(self.rows(), [])

    def test_append_node_and_run_id_still_works(self):
        rc, _, err = self.run_cli("append", "--node-id", "X", "--run-id", "Y", "--verdict", "fail")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.rows()[-1]["run_id"], "Y")


if __name__ == "__main__":
    unittest.main()
