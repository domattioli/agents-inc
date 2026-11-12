"""Spec 038 T045 (FR-015): every guest agent run writes host-ledger rows with `source: native-<provider>` and the
provider's name, and its run directory gets events.jsonl rows (run.start, step, run.end). Fake HOME, fake keys and
the fake provider server only."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import native, native_http
from agents_inc.install.paths import InstallPaths

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402

FAKE = {"gemini": "AIzaFAKE-ledger-0000000000000000000000", "mistral": "FAKE-mistral-ledger-000000000000",
        "openrouter": "FAKE-openrouter-ledger-0000000000"}
NICKS = {"gemini": "gemini-flash", "mistral": "codestral", "openrouter": "gemma-31b"}
REPLY = {"gemini": {"candidates": [{"content": {"parts": [{"text": '{"say": "ok", "tools": []}'}]}}],
                    "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1}},
         "chat": {"choices": [{"message": {"content": '{"say": "ok", "tools": []}'}}], "usage": {"prompt_tokens": 3, "completion_tokens": 1}}}


class NativeLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"; self.home.mkdir()
        self.ws = Path(self.tmp.name) / "ws"; self.ws.mkdir()
        self.paths = InstallPaths.for_home(self.home)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home)}); env.start(); self.addCleanup(env.stop)
        os.environ.pop("AGENTS_INC_MODEL_MAP", None)
        store = native_http.key_store(self.home); store.parent.mkdir(parents=True)
        store.write_text("".join(f"{native_http.KEY_VARS[p][0]}={k}\n" for p, k in FAKE.items()))

    def rows(self):
        path = self.paths.state / "host-ledger" / ".workerbees" / "ledger.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def events(self, nick, session="s1", agent="a1"):
        path = self.paths.state / "native-runs" / nick / session / agent / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_free_provider_rows_and_events(self):
        for provider, nick in NICKS.items():
            with self.subTest(provider=provider):
                native.allow(self.paths, provider, str(self.ws))
                agent = f"a-{provider}"
                self.assertEqual(native.begin(self.paths, nick, "s1", agent, str(self.ws), "task")[0], 0)
                body = REPLY["gemini" if provider == "gemini" else "chat"]
                with FakeProvider([Reply(200, body)]) as srv:
                    code = native.step(self.paths, nick, str(self.ws), "prompt", 5, out=io.StringIO(), err=io.StringIO(),
                                       env={native_http.URL_ENV[provider]: srv.url}, session="s1", agent=agent)
                self.assertEqual(code, 0)
                native.end(self.paths, nick, "s1", agent, "done", str(self.ws), {"input_tokens": 3, "output_tokens": 1})
                mine = [r for r in self.rows() if r["id"] == agent]
                self.assertEqual([r["source"] for r in mine], [f"native-{provider}"] * 2)
                self.assertEqual(mine[0]["provider"], provider)
                self.assertEqual(mine[0]["model"], native.model(nick)["slug"])
                ev = self.events(nick, agent=agent)
                self.assertEqual([e["event"]["type"] for e in ev], ["run.start", "step", "run.end"])
                self.assertEqual([e["seq"] for e in ev], [1, 2, 3])
                self.assertEqual(ev[1]["event"]["usage"]["input_tokens"], 3)
                self.assertEqual(ev[2]["event"]["outcome"], "done")
                text = json.dumps(ev) + json.dumps(mine)
                self.assertNotIn(FAKE[provider], text)
                self.assertNotIn("prompt", [k for e in ev for k in e["event"]])

    def test_codex_nickname_rows_say_native_codex(self):
        native.begin(self.paths, "terra", "s1", "a1", str(self.ws), "task")
        native.end(self.paths, "terra", "s1", "a1", "failed", str(self.ws), {})
        rows = self.rows()
        self.assertEqual([r["source"] for r in rows], ["native-codex"] * 2)
        self.assertEqual(rows[0]["provider"], "codex")
        self.assertEqual([e["event"]["type"] for e in self.events("terra")], ["run.start", "run.end"])

    def test_failed_step_records_its_exit_and_no_usage(self):
        native.allow(self.paths, "gemini", str(self.ws))
        native.begin(self.paths, "gemini-flash", "s1", "a1", str(self.ws), "task")
        with FakeProvider([Reply(429, {"error": "quota"})]) as srv:
            code = native.step(self.paths, "gemini-flash", str(self.ws), "p", 5, out=io.StringIO(), err=io.StringIO(),
                               env={"AGENTS_INC_NATIVE_GEMINI_URL": srv.url}, session="s1", agent="a1")
        self.assertEqual(code, 75)
        step = self.events("gemini-flash")[-1]["event"]
        self.assertEqual((step["type"], step["exit"], step["usage"]), ("step", 75, None))

    def test_step_without_a_run_directory_writes_nothing(self):
        native.allow(self.paths, "gemini", str(self.ws))
        with FakeProvider([Reply(200, REPLY["gemini"])]) as srv:
            native.step(self.paths, "gemini-flash", str(self.ws), "p", 5, out=io.StringIO(), err=io.StringIO(),
                        env={"AGENTS_INC_NATIVE_GEMINI_URL": srv.url}, session="s9", agent="a9")
        self.assertFalse((self.paths.state / "native-runs" / "gemini-flash" / "s9").exists())


if __name__ == "__main__":
    unittest.main()
