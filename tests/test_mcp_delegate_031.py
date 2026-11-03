"""Spec 031: the DelegateAgent MCP server offers all 4 seats, takes effort and a conversation id, and never reports an
empty Codex result as success. StdioTests run the server as a subprocess with a fake codex first on PATH; InProcessTests
import the module and patch subprocess.run for the timeout map."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "skills/codex-bridge/mcp/codex_agent_mcp.py"
FAKE_DIR = ROOT / "tests/fixtures/fake_codex"
TIERS = {"luna": "grunt", "terra": "workhorse", "sol": "orchestrator", "astra": "executive"}


def _pins():
    tiers = json.loads((ROOT / "agents_inc/routing.json").read_text())["tiers"]
    return {alias: tiers[tier]["codex"] for alias, tier in TIERS.items()}


class StdioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.log = Path(self.tmp.name) / "codex.log"
        self._id = 0

    def _run(self, requests, mode="ok", path_dirs=None, mcp=MCP, **extra):
        dirs = [str(FAKE_DIR)] if path_dirs is None else path_dirs
        env = {"PATH": os.pathsep.join(dirs + [os.path.dirname(sys.executable), "/usr/bin", "/bin"]),
               "HOME": str(self.home), "FAKE_CODEX_MODE": mode, "FAKE_CODEX_LOG": str(self.log),
               "TMPDIR": self.tmp.name, **extra}
        out = subprocess.run([sys.executable, str(mcp)], input="".join(json.dumps(r) + "\n" for r in requests),
                             env=env, capture_output=True, text=True, timeout=120).stdout
        return [json.loads(line) for line in out.splitlines() if line.strip()]

    def _call(self, mode="ok", path_dirs=None, **arguments):
        self._id += 1
        arguments.setdefault("prompt", "hello")
        req = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
               "params": {"name": "DelegateAgent", "arguments": arguments}}
        return self._run([req], mode=mode, path_dirs=path_dirs)[0]["result"]

    def _schema(self, **extra):
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        tool = self._run([req], **extra)[0]["result"]["tools"][0]
        return tool["inputSchema"]["properties"]

    def _argv_calls(self):
        text = self.log.read_text() if self.log.exists() else ""
        return [block.splitlines() for block in text.split("---\n") if block.strip()]

    def test_enum_has_four_seats_with_routing_pins(self):
        enum = self._schema()["model"]["enum"]
        self.assertEqual(enum, ["astra", "luna", "sol", "terra"])
        script = subprocess.run([sys.executable, str(MCP), "--resolve-model", "sol"], capture_output=True, text=True,
                                env={"HOME": str(self.home), "PATH": "/usr/bin:/bin"})
        for alias, slug in _pins().items():
            out = subprocess.run([sys.executable, str(MCP), "--resolve-model", alias], capture_output=True, text=True,
                                 env={"HOME": str(self.home), "PATH": "/usr/bin:/bin"}).stdout.strip()
            self.assertEqual(out, slug)
        self.assertEqual(script.stdout.strip(), _pins()["sol"])

    def test_schema_has_effort_and_conversation_id(self):
        props = self._schema()
        self.assertEqual(props["effort"]["enum"], ["low", "medium", "high", "xhigh"])
        self.assertIn("conversation_id", props)

    def test_corrupt_routing_file_yields_luna_only(self):
        tree = Path(self.tmp.name) / "tree"
        (tree / "skills/codex-bridge/mcp").mkdir(parents=True)
        (tree / "agents_inc").mkdir()
        (tree / "agents_inc/routing.json").write_text("{not json")
        copy = tree / "skills/codex-bridge/mcp/codex_agent_mcp.py"
        copy.write_text(MCP.read_text())
        enum = self._schema(mcp=copy)["model"]["enum"]
        self.assertEqual(enum, ["luna"])

    def test_env_map_overrides_a_slug_and_adds_an_alias(self):
        override = json.dumps({"sol": "custom-sol", "nova": "custom-nova"})
        for alias, expected in (("sol", "custom-sol"), ("nova", "custom-nova")):
            out = subprocess.run([sys.executable, str(MCP), "--resolve-model", alias], capture_output=True, text=True,
                                 env={"HOME": str(self.home), "PATH": "/usr/bin:/bin", "AGENTS_INC_MODEL_MAP": override}).stdout
            self.assertEqual(out.strip(), expected)
        enum = self._schema(AGENTS_INC_MODEL_MAP=override)["model"]["enum"]
        self.assertEqual(enum, ["astra", "luna", "nova", "sol", "terra"])

    def test_effort_high_passes_reasoning_effort_config(self):
        res = self._call(effort="high")
        self.assertNotIn("isError", res)
        argv = self._argv_calls()[0]
        self.assertIn("-c", argv)
        self.assertIn("model_reasoning_effort=high", argv)

    def test_no_effort_adds_no_config(self):
        self._call()
        self.assertNotIn("model_reasoning_effort=high", self._argv_calls()[0])
        self.assertFalse([a for a in self._argv_calls()[0] if a.startswith("model_reasoning_effort")])

    def test_resume_argv_and_conversation_id(self):
        res = self._call(conversation_id="T-1")
        self.assertNotIn("isError", res)
        argv = self._argv_calls()[0]
        self.assertEqual(argv[:3], ["exec", "resume", "T-1"])
        self.assertIn("sandbox_mode=read-only", argv)
        self.assertNotIn("-s", argv)
        self.assertNotIn("-C", argv)
        texts = [c["text"] for c in res["content"]]
        self.assertIn("conversation_id: T-1", texts)

    def test_new_call_returns_new_conversation_id(self):
        res = self._call()
        texts = [c["text"] for c in res["content"]]
        self.assertEqual(texts[0].strip(), "answer")
        self.assertIn("conversation_id: T-NEW", texts)
        argv = self._argv_calls()[0]
        self.assertEqual(argv[0], "exec")
        self.assertIn("-s", argv)

    def test_resume_mismatch_is_an_error(self):
        res = self._call(mode="resume-mismatch", conversation_id="T-1")
        self.assertTrue(res.get("isError"))
        self.assertIn("not found", res["content"][0]["text"])

    # US2: no silent success (T007)
    def test_empty_output_is_an_error_quoting_stderr_with_login_hint(self):
        res = self._call(mode="empty")
        self.assertTrue(res.get("isError"))
        text = res["content"][0]["text"]
        self.assertIn("Failed to refresh token", text)
        self.assertIn("codex login", text)
        self.assertNotIn("MCP route", text)

    def test_nonzero_exit_quotes_stderr(self):
        res = self._call(mode="fail")
        self.assertTrue(res.get("isError"))
        self.assertIn("boom", res["content"][0]["text"])

    def test_auth_failure_has_login_hint(self):
        res = self._call(mode="auth")
        self.assertTrue(res.get("isError"))
        self.assertIn("codex login", res["content"][0]["text"])

    def test_missing_codex_names_the_cli(self):
        res = self._call(path_dirs=[])
        self.assertTrue(res.get("isError"))
        self.assertIn("codex CLI not found", res["content"][0]["text"])

    def test_mixed_stress_loop_has_no_empty_success(self):
        modes = ["ok", "empty", "auth", "fail"]
        silent = 0
        for i in range(50):
            res = self._call(mode=modes[i % 4])
            blank = not "".join(c["text"] for c in res["content"]).strip()
            if not res.get("isError") and blank:
                silent += 1
            if modes[i % 4] != "ok":
                self.assertTrue(res.get("isError"), modes[i % 4])
        self.assertEqual(silent, 0)


class InProcessTests(unittest.TestCase):
    def _load(self):
        spec = importlib.util.spec_from_file_location("codex_agent_mcp_031", MCP)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _timeout_for(self, effort):
        mod = self._load()
        done = subprocess.CompletedProcess([], 0, "answer\n", "CONVERSATION_ID=T-1\n")
        with mock.patch.object(mod.subprocess, "run", return_value=done) as run:
            args = {"prompt": "x"}
            if effort:
                args["effort"] = effort
            mod.handle_tools_call(1, {"name": "DelegateAgent", "arguments": args})
        kw = run.call_args.kwargs
        return kw["timeout"], kw["env"]["CODEXAGENT_TIMEOUT"]

    def test_timeout_map(self):
        self.assertEqual(self._timeout_for("high"), (930, "900"))
        self.assertEqual(self._timeout_for("xhigh"), (1830, "1800"))
        self.assertEqual(self._timeout_for(None), (330, "300"))

    def test_timeout_error_names_effort_and_limit(self):
        mod = self._load()
        with mock.patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 930)):
            res = mod.handle_tools_call(1, {"name": "DelegateAgent", "arguments": {"prompt": "x", "effort": "high"}})
        self.assertTrue(res["result"]["isError"])
        text = res["result"]["content"][0]["text"]
        self.assertIn("high", text)
        self.assertIn("900", text)


if __name__ == "__main__":
    unittest.main()
