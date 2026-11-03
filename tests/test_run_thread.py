"""`agents-inc run --thread FILE`: one Codex thread per file, live event and usage lines on stderr."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import runtime
from agents_inc.install.receipt import InstallReceipt
from agents_inc.install.runtime import count_codex_tool_call, run_codex_thread

FAKE = """#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
stdin = sys.stdin.read()
with open(os.environ["FAKE_ARGV_LOG"], "a") as f:
    f.write(json.dumps({"argv": argv, "stdin": stdin}) + "\\n")
with open(argv[argv.index("-o") + 1], "w") as f:
    f.write("last message\\n")
tid = argv[argv.index("resume") + 1] if "resume" in argv else "thread-new-1"
for event in (
    {"type": "thread.started", "thread_id": tid},
    {"type": "item.completed", "item": {"type": "reasoning", "text": "thinking it over"}},
    {"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}},
    {"type": "item.completed", "item": {"type": "agent_message", "text": "last message"}},
    {"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 3}},
):
    print(json.dumps(event), flush=True)
sys.exit(int(os.environ.get("FAKE_RC", "0")))
"""


class RunThreadTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        fake = self.dir / "codex"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.receipt = InstallReceipt(release_hash="a" * 64, python_path=Path("/usr/bin/python3"), codex_path=fake)
        self.log = self.dir / "argv.jsonl"
        env = mock.patch.dict(os.environ, {"FAKE_ARGV_LOG": str(self.log)})
        env.start()
        self.addCleanup(env.stop)

    def run_thread(self, thread_file, message="hello"):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = run_codex_thread(thread_file, "astra", "medium", self.dir, io.StringIO(message), self.receipt,
                                  {"gpt-6-astra": ["medium"]}, no_tools=True)
        return rc, out.getvalue(), err.getvalue()

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_new_thread_writes_file_and_makes_parents(self):
        thread = self.dir / "sub" / "dir" / "a.thread"
        rc, out, _ = self.run_thread(thread)
        self.assertEqual(rc, 0)
        self.assertEqual(thread.read_text().strip(), "thread-new-1")
        argv = self.calls()[0]["argv"]
        self.assertNotIn("resume", argv)
        self.assertIn("--json", argv)
        self.assertEqual(self.calls()[0]["stdin"], "hello")

    def test_empty_file_starts_a_new_thread(self):
        thread = self.dir / "a.thread"
        thread.write_text("\n")
        self.run_thread(thread)
        self.assertNotIn("resume", self.calls()[0]["argv"])
        self.assertEqual(thread.read_text().strip(), "thread-new-1")

    def test_file_with_id_resumes(self):
        thread = self.dir / "a.thread"
        thread.write_text("thread-old-7\n")
        rc, out, _ = self.run_thread(thread, "next message")
        self.assertEqual(rc, 0)
        argv = self.calls()[0]["argv"]
        self.assertIn("resume", argv)
        self.assertIn("thread-old-7", argv)
        self.assertEqual(argv[-1], "next message")  # the message rides the PROMPT positional
        self.assertEqual(thread.read_text().strip(), "thread-old-7")

    def test_event_and_usage_lines_on_stderr_in_order(self):
        _, _, err = self.run_thread(self.dir / "a.thread")
        lines = [l for l in err.splitlines() if l.startswith("agents-inc run: ")]
        kinds = [l.split(" ")[2] for l in lines]
        self.assertEqual(kinds, ["record", "event", "event", "usage", "tools"])
        self.assertEqual(json.loads(lines[1].split(" event ", 1)[1]), {"kind": "reasoning", "text": "thinking it over"})
        self.assertEqual(json.loads(lines[2].split(" event ", 1)[1]), {"kind": "agent_message", "text": "last message"})
        self.assertEqual(json.loads(lines[3].split(" usage ", 1)[1]),
                         {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 3})

    def test_tools_line_counts_codexs_own_tool_items_only(self):
        # FR-014: reasoning and agent_message are not tools; the fixture's one command_execution is.
        _, _, err = self.run_thread(self.dir / "a.thread")
        line = next(l for l in err.splitlines() if l.startswith("agents-inc run: tools "))
        self.assertEqual(json.loads(line.split(" tools ", 1)[1]), {"command_execution": 1})

    def test_count_codex_tool_call_keys_by_tool_name_then_type(self):
        counts = {}
        for item in ({"type": "mcp_tool_call", "tool": "search"}, {"type": "mcp_tool_call", "tool": "search"},
                     {"type": "file_change"}, {"type": "reasoning"}, {"type": "agent_message"}, {"type": "error"}):
            count_codex_tool_call(json.dumps({"type": "item.completed", "item": item}), counts)
        count_codex_tool_call(json.dumps({"type": "item.started", "item": {"type": "file_change"}}), counts)
        count_codex_tool_call("not json", counts)
        self.assertEqual(counts, {"search": 2, "file_change": 1})

    def test_no_tools_line_when_codex_used_none(self):
        with mock.patch.object(runtime, "count_codex_tool_call"):
            _, _, err = self.run_thread(self.dir / "a.thread")
        self.assertNotIn("agents-inc run: tools ", err)

    def test_stdout_is_the_last_message_only(self):
        _, out, _ = self.run_thread(self.dir / "a.thread")
        self.assertEqual(out, "last message\n")

    def test_failed_new_run_writes_no_file(self):
        thread = self.dir / "a.thread"
        with mock.patch.dict(os.environ, {"FAKE_RC": "3"}):
            rc, _, _ = self.run_thread(thread)
        self.assertEqual(rc, 3)
        self.assertEqual(thread.read_text().strip(), "thread-new-1")  # the id still arrived on thread.started


class RuiReplayTest(unittest.TestCase):
    """luna sent host tool requests as request_user_input calls; a host-tools thread run replays them."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.rollout = self.home / ".codex" / "sessions" / "2026" / "10" / "25" / "rollout-2026-10-25T03-17-33-tid-9.jsonl"
        self.rollout.parent.mkdir(parents=True)

    @staticmethod
    def call(arguments):
        return json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "request_user_input",
                                                                "arguments": arguments}}) + "\n"

    def test_only_calls_carrying_tools_are_replies(self):
        tools = json.dumps({"say": "", "tools": [{"name": "Bash", "input": {"command": "wc -l b.txt"}}]})
        self.rollout.write_text(self.call(json.dumps({"questions": []})) + self.call(tools) + self.call("not json")
                                + self.call(json.dumps({"say": "x", "tools": []})))
        calls = runtime.rui_calls(self.rollout)
        self.assertEqual(len(calls), 4)  # every call counts, the unparsable one too
        self.assertEqual([json.loads(t) for t in runtime.rui_replies(calls)], [json.loads(tools)])

    def test_offset_skips_earlier_runs(self):
        old = self.call(json.dumps({"say": "", "tools": [{"name": "Bash", "input": {"command": "wc -l a.txt"}}]}))
        new = self.call(json.dumps({"say": "", "tools": [{"name": "Bash", "input": {"command": "wc -l c.txt"}}]}))
        self.rollout.write_text(old + new)
        replies = runtime.rui_replies(runtime.rui_calls(self.rollout, len(old.encode())))
        self.assertEqual(len(replies), 1)
        self.assertIn("c.txt", replies[0])

    def test_thread_rollout_finds_the_file_by_thread_id(self):
        self.rollout.write_text("")
        with mock.patch.object(runtime, "real_codex_home", return_value=self.home / ".codex"):
            self.assertEqual(runtime.thread_rollout("tid-9"), self.rollout)
            self.assertIsNone(runtime.thread_rollout("tid-0"))

    def run_thread(self, thread, host_tools):
        tools = json.dumps({"say": "", "tools": [{"name": "Bash", "input": {"command": "wc -l b.txt"}}]})

        def fake_run(*args, thread_out=None, **kwargs):
            with self.rollout.open("a") as f:
                f.write(self.call(tools) + self.call(json.dumps({"questions": []})))
            if thread_out is not None:
                thread_out["thread_id"] = "tid-9"
            return 0

        err = io.StringIO()
        with mock.patch.object(runtime, "real_codex_home", return_value=self.home / ".codex"), \
                mock.patch.object(runtime, "run_codex", side_effect=fake_run), contextlib.redirect_stderr(err):
            run_codex_thread(thread, "luna", "medium", self.home, io.StringIO("go"), None, {}, host_tools=host_tools)
        lines = err.getvalue().splitlines()
        self.tools_lines = [json.loads(l.split(" ", 3)[3]) for l in lines if l.startswith("agents-inc run: tools ")]
        return [json.loads(l.split(" ", 3)[3]) for l in lines if l.startswith("agents-inc run: event ")]

    def test_host_tools_run_replays_only_this_runs_calls(self):
        thread = self.home / "a.thread"
        self.rollout.write_text(self.call(json.dumps({"say": "", "tools": [{"name": "Read", "input": {}}]})))
        thread.write_text("tid-9\n")
        events = self.run_thread(thread, host_tools=True)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "agent_message")
        self.assertIn("wc -l b.txt", events[0]["text"])
        self.assertEqual(self.tools_lines, [{"request_user_input": 2}])  # this run's two calls, not the earlier one

    def test_other_runs_replay_nothing(self):
        self.assertEqual(self.run_thread(self.home / "b.thread", host_tools=False), [])
        self.assertEqual(self.tools_lines, [])


class RunThreadCliTest(unittest.TestCase):
    def test_thread_with_lead_is_rejected(self):
        from agents_inc.install import cli
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as raw, contextlib.redirect_stderr(err), \
                mock.patch.object(cli, "InstallReceipt") as receipt:
            receipt.load.return_value = object()
            with mock.patch("pathlib.Path.exists", return_value=True):
                rc = cli.main(["run", "--model", "astra", "--cwd", raw, "--thread", f"{raw}/t", "--lead", f"{raw}/lead"])
        self.assertEqual(rc, 2)
        self.assertIn("--thread cannot be combined with --lead", err.getvalue())


if __name__ == "__main__":
    unittest.main()
