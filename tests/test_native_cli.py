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
        self.assertEqual(names[0], "luna")
        self.assertIn("gemini-flash", names); self.assertIn("ministral", names); self.assertIn("gemma-31b", names)

    def test_luna_status_all_is_the_native_status_the_mod_reads(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            code, out, _ = run(["luna", "status", "--json", "--all", "--cwd", str(self.ws)])
            _, ref, _ = run(["native", "status", "--json", "--cwd", str(self.ws)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), json.loads(ref))

    def test_each_nickname_maps_to_one_free_model_and_one_provider(self):
        roster = {n: m for n, m in native.NATIVE_MODELS.items() if n not in native.CODEX_NICKS}
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
        for result in ("unavailable", "quota-paused"):
            self.probe(result); s = self.status()  # did not answer: never chat only
            self.assertFalse(s["offered"]); self.assertEqual(s["probe"], result); self.assertFalse(s["tools"])
            self.assertIn("agents-inc models probe gemini-flash", s["reason"])
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
        scratch = Path(self.tmp.name) / "scratchpad"
        patch = mock.patch.dict(os.environ, {"CLAUDE_SCRATCHPAD": str(scratch)}); patch.start(); self.addCleanup(patch.stop)
        args = ["native", "--model", "gemini-flash", "begin", "--session", "s1", "--agent", "a1", "--cwd", str(self.ws)]
        code, out, _ = run(args)
        self.assertEqual(code, 3)
        ask = json.loads(out)
        self.assertEqual(ask["status"], "needs-authorization")
        self.assertEqual(ask["provider"], "gemini")
        self.assertIn("whole conversation", ask["sends"])
        self.assertEqual(ask["write_dirs"], [os.path.join(os.path.realpath(self.ws), ".scratch")])
        self.assertFalse((self.paths.state / "native-runs").exists())  # nothing started
        # #177: the refusal leaves one failed run record for the pane (red, with the reason and the allow command)
        recs = list(scratch.glob("agents-inc-runs/*-gemini-flash-*/run.json"))
        self.assertEqual(len(recs), 1)
        rec = json.loads(recs[0].read_text())
        self.assertEqual((rec["outcome"], rec["model"]), ("red", "gemini-flash"))
        self.assertIn("needs-authorization", rec["reason"]); self.assertIn("native allow gemini", rec["reason"])
        code, out, _ = run(["native", "allow", "gemini", "--workspace", str(self.ws)])
        self.assertEqual(code, 0)
        self.assertEqual(oct((self.paths.state / native.ALLOW_FILE).stat().st_mode & 0o777), "0o600")
        code, out, _ = run(args)
        self.assertEqual(code, 0)
        self.assertIn(json.loads(out)["snapshot"], ("captured", "no-repo"))
        self.assertTrue(self.status()["authorized"])

    def test_status_shows_missing_workspace_allow_with_command(self):
        self.key(); self.probe()
        before = self.status()
        self.assertTrue(before["needs_allow"]); self.assertFalse(before["authorized"])
        cmd = f"agents-inc native allow gemini --workspace {os.path.realpath(self.ws)}"
        self.assertIn("needs workspace allow", before["reason"]); self.assertIn(cmd, before["reason"])
        run(["native", "allow", "gemini", "--workspace", str(self.ws)])
        after = self.status()
        self.assertFalse(after["needs_allow"]); self.assertEqual(after["reason"], "ready")

    def test_status_and_begin_carry_write_dirs(self):
        self.key(); self.probe()
        self.assertEqual(self.status()["write_dirs"], [])
        sub = self.ws / "out"
        native.allow(self.paths, "gemini", str(self.ws), ["out"])
        want = [os.path.realpath(sub)]
        self.assertEqual(self.status()["write_dirs"][:1], want)  # extra entries are the same dirs under cwd's own spelling
        code, out, _ = run(["native", "--model", "gemini-flash", "begin", "--session", "s1", "--agent", "a1", "--cwd", str(self.ws)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["write_dirs"][:1], want)

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

    def test_authorization_matches_a_symlinked_spelling_of_the_workspace(self):
        # Works on every filesystem: a symlink is a second spelling of the same directory.
        link = Path(self.tmp.name) / "link"; link.symlink_to(self.ws)
        native.allow(self.paths, "gemini", str(link), ["out"])
        rec = native.authorization(self.paths, "gemini", str(self.ws))
        self.assertIsNotNone(rec)
        self.assertIsNotNone(native.authorization(self.paths, "gemini", str(link)))
        (self.ws / "sub").mkdir()
        self.assertIsNotNone(native.authorization(self.paths, "gemini", str(link / "sub")))
        # a different directory never matches
        other = Path(self.tmp.name) / "other"; other.mkdir()
        self.assertIsNone(native.authorization(self.paths, "gemini", str(other)))
        self.assertTrue(native._same_dir(str(link), str(self.ws)))
        self.assertFalse(native._same_dir(str(other), str(self.ws)))
        self.assertFalse(native._same_dir(str(self.ws / "missing"), str(self.ws / "missing2")))

    def test_write_dirs_come_back_under_the_spelling_of_cwd(self):
        spelled = Path(self.tmp.name) / "spelled"; spelled.mkdir()
        (spelled / "sub").mkdir()
        # authorize through the real name, then ask from a case-changed or relinked spelling of the same directory
        native.allow(self.paths, "gemini", str(spelled))
        link = Path(self.tmp.name) / "alias"; link.symlink_to(spelled)
        rec = native.authorization(self.paths, "gemini", str(link / "sub"))
        self.assertIn(os.path.join(os.path.realpath(spelled), ".scratch"), rec["write_dirs"])
        self.assertIn(str(link / ".scratch"), rec["write_dirs"])
        # every dir named stays inside the workspace
        for d in rec["write_dirs"]:
            self.assertTrue(native._same_dir(os.path.dirname(d), str(spelled)))

    def test_authorization_matches_a_case_changed_spelling(self):
        d = Path(self.tmp.name) / "CaseDir"; d.mkdir()
        swapped = Path(self.tmp.name) / "casedir"
        if not swapped.exists():
            self.skipTest("case-sensitive filesystem")
        native.allow(self.paths, "gemini", str(swapped))
        self.assertEqual(native.allow(self.paths, "gemini", str(swapped))["workspace"], os.path.realpath(d))  # on-disk case
        self.assertIsNotNone(native.authorization(self.paths, "gemini", str(swapped)))
        self.assertEqual(len(native._read_json(self.paths.state / native.ALLOW_FILE)["records"]), 1)

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

    def test_codex_nicknames_listed_off_by_default_with_roster_slug(self):
        from agents_inc.install.runtime import load_model_map
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("child")):
            code, out, _ = run(["native", "status", "--json", "--cwd", str(self.ws)])
        self.assertEqual(code, 0)
        rows = {m["nickname"]: m for m in json.loads(out)["models"]}
        slugs = load_model_map(roster=self.paths.roster, env={"HOME": str(self.home)})
        for nick in ("sol", "terra", "astra"):
            m = rows[nick]
            self.assertEqual((m["provider"], m["kind"], m["slug"], m["switch"], m["offered"]),
                             ("codex", "thread", slugs[nick], "off", False))
            self.assertIn(f"agents-inc native on {nick}", m["reason"])
            self.assertNotIn("authorized", m)  # D69: no workspace authorization record for Codex
        self.assertEqual(rows["luna"]["switch"], "on")

    def test_codex_nickname_switch_is_its_own(self):
        self.assertEqual(run(["native", "on", "sol"])[1], "sol type: on\n")
        self.assertEqual(native.read_switch(self.paths, "sol"), "on")
        self.assertEqual(native.read_switch(self.paths, "terra"), "off")
        self.assertEqual(native.read_switch(self.paths, "luna"), "on")
        with mock.patch.object(native.luna_native, "codex_state", return_value="ready"):
            self.assertTrue(native.status_one(self.paths, "sol")["offered"])
            self.assertFalse(native.status_one(self.paths, "astra")["offered"])
        run(["native", "off", "sol"])
        self.assertEqual(native.read_switch(self.paths, "sol"), "off")

    def test_codex_nickname_begin_end_need_no_authorization(self):
        for verb, extra in (("begin", []), ("end", ["--outcome", "done"])):
            code, out, _ = run(["native", "--model", "terra", verb, "--session", "s1", "--agent", "a1", "--cwd", str(self.ws), *extra])
            self.assertEqual(code, 0, verb)
            self.assertIn("snapshot", json.loads(out))
        self.assertTrue((self.paths.state / "native-runs" / "terra" / "s1" / "a1").is_dir())

    def test_codex_nickname_step_is_refused(self):
        err = io.StringIO()
        self.assertEqual(native.step(self.paths, "sol", str(self.ws), "x", 5, out=io.StringIO(), err=err), 2)
        self.assertIn("thread model", err.getvalue())

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
