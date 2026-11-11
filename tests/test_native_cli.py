"""Spec 038 T021: `agents-inc native status|on|off|allow|begin|end` and the luna aliases.

A fake HOME and a fake key; no provider request is made and no network is used.
"""
import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli, native, native_http
from agents_inc.install.paths import InstallPaths

FAKE_KEY = "AIzaFAKE-native-cli-0000000000000000000"


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class NativeCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"; self.home.mkdir()
        self.ws = Path(self.tmp.name) / "ws"; self.ws.mkdir()
        self.paths = InstallPaths.for_home(self.home)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home)}); env.start(); self.addCleanup(env.stop)
        os.environ.pop("AGENTS_INC_MODEL_MAP", None)

    def key(self):
        store = native_http.key_store(self.home); store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n"); store.chmod(0o600)

    def probe(self, result="pass", age=0.0):
        native._write_json(self.paths.state / native.PROBE_FILE,
                           {"gemini-flash": {"result": result, "at_epoch": time.time() - age, "slug": "gemini-3.8-flash"}})

    def status(self, nick="gemini-flash"):
        code, out, _ = run(["native", "--model", nick, "status", "--json", "--cwd", str(self.ws)])
        self.assertEqual(code, 0)
        return json.loads(out)

    def test_status_all_lists_every_model_and_reads_files_only(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("child")):
            code, out, _ = run(["native", "status", "--json"])
        self.assertEqual(code, 0)
        names = [m["nickname"] for m in json.loads(out)["models"]]
        self.assertEqual(names, ["luna", "gemini-flash"])

    def test_luna_status_all_is_the_native_status_the_mod_reads(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            code, out, _ = run(["luna", "status", "--json", "--all", "--cwd", str(self.ws)])
            _, ref, _ = run(["native", "status", "--json", "--cwd", str(self.ws)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), json.loads(ref))

    def test_each_nickname_maps_to_one_free_model_and_one_provider(self):
        roster = {n: m for n, m in native.NATIVE_MODELS.items() if n != "luna"}
        self.assertIn("gemini-flash", roster)
        self.assertEqual(roster["gemini-flash"]["provider"], "gemini")
        for nick, m in roster.items():
            self.assertIn(m["provider"], native.BUILT_PROVIDERS, nick)

    def test_not_offered_without_key_names_why(self):
        s = self.status()
        self.assertFalse(s["offered"])
        self.assertIn("WB_NATIVE_KEY_MISSING", s["reason"])

    def test_not_offered_without_passing_fresh_probe(self):
        self.key()
        self.assertEqual(self.status()["probe"], "none")
        self.probe("fail"); s = self.status()  # a failed probe is offered chat only, not hidden
        self.assertTrue(s["offered"]); self.assertFalse(s["tools"]); self.assertIn("chat only, no tools", s["reason"])
        self.probe("pass", age=native.PROBE_TTL_S + 1); s = self.status()
        self.assertFalse(s["offered"]); self.assertEqual(s["probe"], "stale"); self.assertFalse(s["tools"])
        self.probe("pass"); s = self.status()
        self.assertTrue(s["offered"]); self.assertTrue(s["tools"]); self.assertEqual(s["slug"], "gemini-3.8-flash")
        self.assertNotIn(FAKE_KEY, json.dumps(s))

    def test_on_off_switch(self):
        self.key(); self.probe()
        self.assertEqual(run(["native", "off", "gemini-flash"])[1], "gemini-flash type: off\n")
        self.assertFalse(self.status()["offered"])
        run(["native", "on", "gemini-flash"])
        self.assertTrue(self.status()["offered"])

    def test_first_start_asks_second_does_not(self):
        self.key(); self.probe()
        args = ["native", "--model", "gemini-flash", "begin", "--session", "s1", "--agent", "a1", "--cwd", str(self.ws)]
        code, out, _ = run(args)
        self.assertEqual(code, 3)
        ask = json.loads(out)
        self.assertEqual(ask["status"], "needs-authorization")
        self.assertEqual(ask["provider"], "gemini")
        self.assertIn("whole conversation", ask["sends"])
        self.assertEqual(ask["write_dirs"], [os.path.join(os.path.realpath(self.ws), ".scratch")])
        self.assertFalse((self.paths.state / "native-runs").exists())  # nothing started
        code, out, _ = run(["native", "allow", "gemini", "--workspace", str(self.ws)])
        self.assertEqual(code, 0)
        self.assertEqual(oct((self.paths.state / native.ALLOW_FILE).stat().st_mode & 0o777), "0o600")
        code, out, _ = run(args)
        self.assertEqual(code, 0)
        self.assertIn(json.loads(out)["snapshot"], ("captured", "no-repo"))
        self.assertTrue(self.status()["authorized"])

    def test_status_and_begin_carry_write_dirs(self):
        self.key(); self.probe()
        self.assertEqual(self.status()["write_dirs"], [])
        sub = self.ws / "out"
        native.allow(self.paths, "gemini", str(self.ws), ["out"])
        want = [os.path.realpath(sub)]
        self.assertEqual(self.status()["write_dirs"], want)
        code, out, _ = run(["native", "--model", "gemini-flash", "begin", "--session", "s1", "--agent", "a1", "--cwd", str(self.ws)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["write_dirs"], want)

    def test_begin_by_provider(self):
        native.allow(self.paths, "gemini", str(self.ws))
        code, out, _ = run(["native", "--provider", "gemini", "begin", "--session", "s1", "--agent", "a1", "--cwd", str(self.ws)])
        self.assertEqual(code, 0)
        code, out, _ = run(["native", "--provider", "gemini", "end", "--session", "s1", "--agent", "a1", "--cwd", str(self.ws), "--outcome", "done"])
        self.assertEqual(code, 0)
        self.assertIn("snapshot", json.loads(out))

    def test_authorization_is_per_workspace_and_per_provider(self):
        native.allow(self.paths, "gemini", str(self.ws))
        other = Path(self.tmp.name) / "other"; other.mkdir()
        self.assertIsNone(native.authorization(self.paths, "gemini", str(other)))
        self.assertIsNone(native.authorization(self.paths, "mistral", str(self.ws)))
        (self.ws / "sub").mkdir()
        self.assertIsNotNone(native.authorization(self.paths, "gemini", str(self.ws / "sub")))

    def test_refusal_starts_nothing_and_sends_nothing(self):
        self.key(); self.probe()
        err = io.StringIO()
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            code = native.step(self.paths, "gemini-flash", str(self.ws), "hello", 5, out=io.StringIO(), err=err)
        self.assertEqual(code, 3)
        self.assertIn(native.NEEDS_AUTH, err.getvalue())
        self.assertFalse((self.paths.state / "native-runs").exists())

    def test_allow_refuses_codex_and_unknown(self):
        self.assertEqual(run(["native", "allow", "codex", "--workspace", str(self.ws)])[0], 2)

    def test_luna_alias_output_unchanged(self):
        a = run(["luna", "status", "--json"])
        b = run(["native", "--model", "luna", "status", "--json"])
        luna = json.loads(a[1]); nat = json.loads(b[1])
        self.assertEqual({k: nat[k] for k in luna}, luna)
        self.assertEqual(run(["luna", "status"])[1], run(["native", "--model", "luna", "status"])[1])
        self.assertEqual(run(["luna", "off"])[1], "luna type: off\n")
        self.assertEqual(run(["native", "on", "luna"])[1], "luna type: on\n")


if __name__ == "__main__":
    unittest.main()
