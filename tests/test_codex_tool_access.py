"""D49: Codex tool access by rung. Unit checks always run; live probes need AGENTS_INC_LIVE_PROBES=1."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents_inc.install import runtime
from agents_inc.install.runtime import HARD_DENY, PROFILE, build_codex_argv, permission_profile, run_codex, tools_for

REPO = Path(__file__).resolve().parents[1]
MAP = {"astra": "gpt-6-astra", "sol": "gpt-5.6-sol", "terra": "gpt-5.6-terra", "luna": "gpt-5.6-luna"}
EFF = {slug: ["medium"] for slug in MAP.values()}
EXE = Path("/x/codex")


def _argv(alias, tools=False, write=False, cwd=Path("/w"), no_tools=False):
    return build_codex_argv(EXE, alias, "medium", cwd, EFF, MAP, tools_for(alias, no_tools, tools), write)


class RungArgvTest(unittest.TestCase):
    def test_default_on_for_tool_rungs(self):
        for alias in ("astra", "sol", "terra"):
            self.assertTrue(tools_for(alias))
            self.assertNotIn("-s", _argv(alias))

    def test_off_argv_for_every_alias(self):
        for alias in MAP:
            argv = _argv(alias, no_tools=True)
            self.assertIn("features.shell_tool=false", argv, alias)
            self.assertEqual(argv[argv.index("-s") + 1], "read-only")
            self.assertFalse(any("permissions" in a or "set.PATH" in a for a in argv), alias)

    def test_tools_flag_gets_shell_profile_and_path(self):
        for alias in ("astra", "sol", "terra"):
            argv = _argv(alias, tools=True)
            self.assertNotIn("features.shell_tool=false", argv, alias)
            self.assertIn(f'default_permissions="{PROFILE}"', argv)
            self.assertNotIn("-s", argv)
            self.assertIn('"/w"="read"', argv[-2])
            self.assertIn('web_search="disabled"', argv)
            self.assertIn('shell_environment_policy.set.PATH="/usr/bin:/bin:/usr/sbin:/sbin"', argv)
            self.assertIn('shell_environment_policy.inherit="none"', argv)
            self.assertEqual(argv[-1], "-")

    def test_luna_tools_opt_in_and_unknown_refused(self):
        # D49.1: luna takes tools only with --tools; default stays tool-free; a raw slug fails closed.
        self.assertTrue(tools_for("luna", tools=True))
        argv = _argv("luna", tools=True, write=True)
        self.assertNotIn("features.shell_tool=false", argv)
        self.assertIn('"/w"="write"', argv[-2])
        with self.assertRaisesRegex(ValueError, "allowed only for astra, sol, terra, luna"):
            tools_for("gpt-5.6-sol", tools=True)
        argv = _argv("luna")
        self.assertIn("features.shell_tool=false", argv)
        self.assertFalse(any("permissions" in a or "set.PATH" in a for a in argv))
        with self.assertRaisesRegex(ValueError, "--lead is allowed only for astra, sol, terra"):
            runtime.lead_args("luna", REPO)

    def _fake_home(self, cache=True):
        """A HOME whose .codex holds the models cache (an entry for the luna slug and one for astra) and an auth.json."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        codex = Path(tmp.name, ".codex"); codex.mkdir()
        (codex / "auth.json").write_text("{}")
        if cache:
            (codex / "models_cache.json").write_text(json.dumps({"etag": "x", "models": [
                {"slug": "gpt-5.6-luna", "tool_mode": "code_mode_only", "shell_type": "unified_exec",
                 "experimental_supported_tools": ["clock"], "context_window": 1, "multi_agent_version": "v2",
                 "apply_patch_tool_type": "freeform"},
                {"slug": "gpt-6-astra", "tool_mode": "code_mode_only"}]}))
        env = mock.patch.dict(os.environ, {"HOME": tmp.name}); env.start(); self.addCleanup(env.stop)
        return codex

    def test_host_tools_replaces_base_instructions_only_when_asked(self):
        # The instructions override is for the luna types (--host-tools); a plain --no-tools run keeps Codex's own.
        self._fake_home()
        self.assertFalse(any("model_instructions_file" in a for a in _argv("luna")))
        argv = build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, False, host_tools=True)
        path = Path(json.loads(next(a for a in argv if a.startswith("model_instructions_file=")).split("=", 1)[1]))
        self.assertEqual(path.read_text(), runtime.NO_TOOL_INSTRUCTIONS)
        self.assertIn("features.shell_tool=false", argv)
        resume = runtime.build_codex_resume_argv(EXE, "019a0000-0000-7000-8000-000000000000", "hi", "luna", "medium",
                                                 Path("/w"), EFF, MAP, host_tools=True)
        self.assertTrue(any(a.startswith("model_instructions_file=") for a in resume))

    def test_host_tools_without_a_cache_entry_fails_closed(self):
        # FR-010, FR-011: no stripped catalog means no run; Codex's own catalog would serve exec and apply_patch.
        self._fake_home(cache=False)
        with self.assertRaisesRegex(runtime.HostToolsCatalogMissing, r"^WB_LUNA_CATALOG_MISSING: .*models_cache\.json"):
            build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, False, host_tools=True)
        with self.assertRaisesRegex(runtime.HostToolsCatalogMissing, "WB_LUNA_CATALOG_MISSING"):
            runtime.build_codex_resume_argv(EXE, "019a0000-0000-7000-8000-000000000000", "hi", "luna", "medium",
                                            Path("/w"), EFF, MAP, host_tools=True)
        with self.assertRaisesRegex(runtime.HostToolsCatalogMissing, runtime.CATALOG_WARM_COMMAND.split("{")[0].strip()):
            runtime.no_tool_args(True, "gpt-5.6-luna")

    def test_host_tools_argv_keeps_the_read_only_sandbox_and_no_web_search(self):
        # FR-012
        self._fake_home()
        argv = build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, False, host_tools=True)
        self.assertEqual(argv[argv.index("-s") + 1], "read-only")
        self.assertIn('web_search="disabled"', argv)
        self.assertNotIn("features.shell_tool=true", argv)

    def test_host_tools_argv_drops_codex_context_notes(self):
        # luna read the read-only sandbox note as a reason to ask permission through request_user_input (macOS stress
        # run, 2026-10-25): host-tools runs, fresh and resumed, drop it with the mode text, skills and AGENTS.md.
        self._fake_home()
        argv = build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, False, host_tools=True)
        resume = runtime.build_codex_resume_argv(EXE, "019a0000-0000-7000-8000-000000000000", "hi", "luna", "medium",
                                                 Path("/w"), EFF, MAP, host_tools=True)
        for setting in ("include_permissions_instructions=false", "include_collaboration_mode_instructions=false",
                        "skills.include_instructions=false", "project_doc_max_bytes=0"):
            self.assertIn(setting, argv)
            self.assertIn(setting, resume)
            self.assertNotIn(setting, _argv("luna"))

    def test_host_tools_catalog_ignores_the_env_codex_home(self):
        # plan D3 item 2: the catalog comes from HOME/.codex, the directory auth.json is linked from.
        self._fake_home()
        with tempfile.TemporaryDirectory() as other, mock.patch.dict(os.environ, {"CODEX_HOME": other}):
            argv = build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, False, host_tools=True)
        self.assertTrue(any(a.startswith("model_catalog_json=") for a in argv))

    def test_host_tools_catalog_drops_exec_for_the_cached_model(self):
        codex = self._fake_home()
        argv = build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, False, host_tools=True)
        plain = _argv("luna")
        path = Path(json.loads(next(a for a in argv if a.startswith("model_catalog_json=")).split("=", 1)[1]))
        got = json.loads(path.read_text())
        self.assertEqual(got["etag"], "x")
        self.assertEqual(got["models"], [{"slug": "gpt-5.6-luna", "tool_mode": "direct", "shell_type": "disabled",
                                          "experimental_supported_tools": [], "context_window": 1,
                                          "multi_agent_version": "none"}])
        self.assertFalse(any("model_catalog_json" in a for a in plain))
        self.assertIsNone(runtime.host_tools_catalog("gpt-6-sol", codex))

    def test_host_tools_needs_tools_off(self):
        with self.assertRaisesRegex(ValueError, "--host-tools needs tools off"):
            build_codex_argv(EXE, "astra", "medium", Path("/w"), EFF, MAP, True, host_tools=True)

    def test_no_tools_forces_off(self):
        self.assertFalse(tools_for("astra", no_tools=True, tools=True))
        self.assertFalse(tools_for("luna", no_tools=True, tools=True))  # --no-tools wins before the luna check

    def test_write_needs_tools(self):
        with self.assertRaises(ValueError):
            _argv("luna", write=True)
        with self.assertRaises(ValueError):
            _argv("sol", no_tools=True, write=True)

    def test_write_mode(self):
        argv = _argv("terra", tools=True, write=True)
        self.assertNotIn("-s", argv)
        self.assertIn('"/w"="write"', argv[-2])

    def test_network_opt_in(self):
        # #66: network is off unless asked; it needs tools and refuses a Lead.
        key = f"permissions.{PROFILE}.network={{enabled=true}}"
        self.assertFalse(any("network" in a for a in _argv("sol", tools=True, write=True)))
        argv = build_codex_argv(EXE, "sol", "medium", Path("/w"), EFF, MAP, True, True, network=True)
        self.assertIn(key, argv)
        self.assertEqual(argv[-1], "-")
        with self.assertRaisesRegex(ValueError, "--network needs tools"):
            build_codex_argv(EXE, "sol", "medium", Path("/w"), EFF, MAP, False, network=True)
        resume = runtime.build_codex_resume_argv(EXE, "019a0000-0000-7000-8000-000000000000", "m", "sol", "medium",
                                                 Path("/w"), EFF, MAP, True, True, network=True)
        self.assertIn(key, resume)

    def test_tool_tmp_writable_and_exported(self):
        # #66: tool commands get a writable TMPDIR; zsh heredocs use TMPPREFIX.
        argv = build_codex_argv(EXE, "sol", "medium", Path("/w"), EFF, MAP, True, False, tool_tmp=Path("/t/x"))
        self.assertIn('shell_environment_policy.set.TMPDIR="/t/x"', argv)
        self.assertIn('shell_environment_policy.set.TMPPREFIX="/t/x/zsh"', argv)
        self.assertIn(f'{runtime._toml_key("/t/x")}="write"', argv[-2])
        self.assertIn('"/w"="read"', argv[-2])
        self.assertFalse(any("TMPDIR" in a for a in _argv("sol", tools=True)))


class ProfileTest(unittest.TestCase):
    def test_deny_list_and_grants(self):
        prof = permission_profile(Path("/w"), False, home=Path("/h"))
        for name in HARD_DENY:
            self.assertEqual(prof[f'"/h/{name}"'], "none", name)
        self.assertEqual(prof['"/w"'], "read")
        self.assertEqual(prof['"/private/tmp"'], "read")
        self.assertNotIn('"/h"', prof)  # rest of HOME is absent, so unreadable
        self.assertFalse(any(v == "write" for v in prof.values()))

    def test_generated_images_readable_rest_of_codex_not(self):
        prof = permission_profile(Path("/w"), False, home=Path("/h"))
        self.assertEqual(prof['"/h/.codex/generated_images"'], "read")
        self.assertEqual(prof['"/h/.codex/skills"'], "read")
        self.assertNotIn('"/h/.codex"', prof)  # auth.json, config, sessions stay unreadable

    def test_extra_read_grants_file(self):
        prof = permission_profile(Path("/w"), False, home=Path("/h"), extra_read=(Path("/r/snapshot.json"),))
        self.assertEqual(prof['"/r/snapshot.json"'], "read")
        self.assertNotIn('"/r"', prof)

    def test_subdir_cwd_reads_parent_agents_md_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(os.path.realpath(tmp)) / "repo"
            sub = root / "a" / "b"
            sub.mkdir(parents=True)
            (root / ".git").mkdir()
            (root / "AGENTS.md").write_text("x", encoding="utf-8")
            (root / "a" / "AGENTS.md").write_text("y", encoding="utf-8")
            (Path(tmp) / "AGENTS.md").write_text("above root", encoding="utf-8")
            prof = permission_profile(sub, False, home=Path("/h"))
            self.assertEqual(prof[f'"{root}/AGENTS.md"'], "read")
            self.assertEqual(prof[f'"{root}/a/AGENTS.md"'], "read")
            self.assertNotIn(f'"{os.path.realpath(tmp)}/AGENTS.md"', prof)  # stops at the git root
            self.assertNotIn(f'"{root}"', prof)  # files only, not the directories
            at_root = permission_profile(root, False, home=Path("/h"))
            self.assertFalse(any(k.endswith('AGENTS.md"') for k in at_root))

    def test_lead_home_links_generated_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / ".codex"
            real.mkdir()
            (real / "auth.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(runtime.Path, "home", return_value=Path(tmp)):
                home = runtime.lead_codex_home("gpt-x")
            try:
                self.assertEqual(os.readlink(home / "generated_images"), str(real / "generated_images"))
                self.assertEqual(os.readlink(home / "skills"), str(real / "skills"))
                self.assertTrue((real / "generated_images").is_dir())
            finally:
                shutil.rmtree(home)

    def test_run_dir_only_write(self):
        prof = permission_profile(Path("/w"), True, home=Path("/h"), write_dir=Path("/w/runs/r1"))
        self.assertEqual(prof['"/w"'], "read")
        self.assertEqual(prof['"/w/runs/r1"'], "read")  # run.json, workers/, results: broker-owned
        self.assertEqual([k for k, v in prof.items() if v == "write"], ['"/w/runs/r1/inbox"'])
        for name in HARD_DENY:
            self.assertEqual(prof[f'"/h/{name}"'], "none", name)

    def test_run_dir_argv_and_legacy(self):
        argv = build_codex_argv(EXE, "sol", "medium", Path("/w"), EFF, MAP, True, True, Path("/w/r"))
        self.assertIn('"/w"="read"', argv[-2])
        self.assertIn('"/w/r"="read"', argv[-2])
        self.assertIn('"/w/r/inbox"="write"', argv[-2])
        self.assertIn('"/w"="write"', _argv("sol", tools=True, write=True)[-2])  # legacy: no run dir

    def test_run_dir_inbox_symlink_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            run.mkdir()
            (run / "inbox").symlink_to(Path(tmp))
            with self.assertRaises(ValueError):
                permission_profile(Path("/w"), True, write_dir=run)

    def test_run_dir_needs_tools(self):
        with mock.patch.object(runtime, "load_model_map", return_value=MAP), \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(Path, "is_file", return_value=True), \
                self.assertRaises(ValueError) as cm:
            run_codex("sol", "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF,
                      no_tools=True, write_dir=Path("/w/r"))
        self.assertIn("--run-dir needs tools", str(cm.exception))

    def test_run_dir_read_only_profile_equals_write(self):
        d = Path("/w/r")
        self.assertEqual(permission_profile(Path("/w"), False, home=Path("/h"), write_dir=d),
                         permission_profile(Path("/w"), True, home=Path("/h"), write_dir=d))

    def test_run_dir_profile_grants_no_broker_lock(self):
        prof = permission_profile(Path("/w"), True, home=Path("/h"), write_dir=Path("/w/r"))
        self.assertNotIn("broker.lock", repr(prof))

    def test_run_dir_without_write_builds_argv(self):
        done = SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        with mock.patch.object(runtime, "load_model_map", return_value=MAP), \
                mock.patch.object(runtime.subprocess, "run", return_value=done) as sp, \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(Path, "is_file", return_value=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = run_codex("sol", "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF,
                           write=False, write_dir=Path("/w/r"))
        self.assertEqual(rc, 0)
        self.assertIn('"/w/r/inbox"="write"', sp.call_args[0][0][-2])

    def test_bad_path_rejected(self):
        with self.assertRaises(ValueError):
            permission_profile(Path('/w"x'), False)


class RunRecordTest(unittest.TestCase):
    def _run(self, alias, **kw):
        done = SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        err = io.StringIO()
        with mock.patch.object(runtime, "load_model_map", return_value=MAP), \
                mock.patch.object(runtime.subprocess, "run", return_value=done) as sp, \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(Path, "is_file", return_value=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = run_codex(alias, "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF, **kw)
        return rc, err.getvalue(), sp.call_args[0][0]

    def test_record_fields(self):
        _, err, argv = self._run("sol")
        self.assertIn('"tools": "on", "sandbox": "read-only"', err)
        self.assertNotIn("-s", argv)
        _, err, argv = self._run("sol", tools=True, write=True)
        self.assertIn('"tools": "on", "sandbox": "workspace-write"', err)
        _, err, argv = self._run("luna")
        self.assertIn('"tools": "off", "sandbox": "read-only"', err)
        self.assertIn("features.shell_tool=false", argv)
        _, err, argv = self._run("astra", tools=True, no_tools=True)
        self.assertIn('"tools": "off"', err)


HOST_TOOLS_FAKE = """#!/usr/bin/env python3
import json, os, sys
home = os.environ["CODEX_HOME"]
mode = os.environ.get("FAKE_MODE", "")
sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "codex_home": home, "home": os.environ.get("HOME"),
                        "path": os.environ.get("PATH"), "auth_link": os.path.islink(home + "/auth.json"),
                        "has_cache": os.path.exists(home + "/models_cache.json"),
                        "config": open(home + "/config.toml").read()}) + "\\n")
if mode == "replace_auth":
    os.unlink(home + "/auth.json")
    open(home + "/auth.json", "w").write("{}")
if mode == "quota":
    sys.stderr.write("ERROR: You've hit your usage limit. Please try again at 5:00 PM.\\n")
    sys.exit(1)
if mode == "fail":
    sys.stderr.write("boom\\n")
    sys.exit(7)
print("OK")
"""


class HostToolsRunTest(unittest.TestCase):
    """Spec 028 FR-010 to FR-013, FR-016, FR-023: a host-tools run fails closed without the stripped catalog and runs in
    an isolated CODEX_HOME. A fake Codex records what it sees; no real Codex starts."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.home = self.dir / "home"
        self.real = self.home / ".codex"
        self.real.mkdir(parents=True)
        self.fake = self.dir / "codex"
        self.fake.write_text(HOST_TOOLS_FAKE)
        self.fake.chmod(0o755)
        self.log = self.dir / "log.jsonl"
        self.operator_home = self.dir / "operator-codex"
        self.operator_home.mkdir()
        (self.operator_home / "config.toml").write_text('model = "operator"\n')
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "FAKE_LOG": str(self.log),
                                           "CODEX_HOME": str(self.operator_home)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("FAKE_MODE", None)
        self.receipt = SimpleNamespace(codex_path=self.fake)

    def add_cache(self):
        (self.real / "models_cache.json").write_text(json.dumps({"models": [{"slug": MAP["luna"], "tool_mode": "code_mode_only"}]}))

    def add_auth(self):
        (self.real / "auth.json").write_text("{}")

    def run_luna(self, host_tools=True):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(runtime, "load_model_map", return_value=MAP), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = run_codex("luna", "medium", self.dir, io.StringIO("p"), self.receipt, EFF, no_tools=True,
                           host_tools=host_tools)
        return rc, out.getvalue(), err.getvalue()

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_no_cache_entry_exits_3_before_any_process_or_temp_home(self):
        self.add_auth()
        with mock.patch.object(runtime, "lead_codex_home") as home:
            rc, _, err = self.run_luna()
        self.assertEqual(rc, 3)
        self.assertEqual(err.count("WB_LUNA_CATALOG_MISSING"), 1)
        self.assertIn("models_cache.json", err)
        self.assertEqual(self.calls(), [])
        home.assert_not_called()

    def test_run_uses_an_isolated_home_with_the_real_auth_linked_and_no_cache(self):
        self.add_cache()
        self.add_auth()
        rc, out, _ = self.run_luna()
        self.assertEqual((rc, out), (0, "OK\n"))
        call = self.calls()[0]
        self.assertNotIn(call["codex_home"], (str(self.operator_home), str(self.real)))
        self.assertTrue(call["auth_link"])
        self.assertFalse(call["has_cache"])
        self.assertNotIn("mcp_servers", call["config"])
        self.assertEqual(call["home"], str(self.home))  # the caller's HOME and PATH are kept: no lead_env scrub
        self.assertEqual(call["path"], os.environ["PATH"])
        self.assertFalse(Path(call["codex_home"]).exists())  # removed afterwards
        catalog = next(a for a in call["argv"] if a.startswith("model_catalog_json="))
        self.assertIn(f"host-tools-catalog-{MAP['luna']}.json", catalog)
        self.assertEqual(call["argv"][call["argv"].index("-s") + 1], "read-only")

    def test_record_line_names_the_catalog_and_the_isolated_home(self):
        self.add_cache()
        self.add_auth()
        _, _, err = self.run_luna()
        record = json.loads(next(l for l in err.splitlines() if l.startswith("agents-inc run: record ")).split("record ", 1)[1])
        self.assertEqual(record["catalog"], "host-tools")
        self.assertTrue(record["catalog_path"].endswith(f"host-tools-catalog-{MAP['luna']}.json"))
        self.assertEqual(record["codex_home"], "isolated")
        self.assertEqual(record["tools"], "off")

    def test_missing_auth_json_is_the_auth_error_and_starts_nothing(self):
        self.add_cache()
        with self.assertRaisesRegex(FileNotFoundError, "WB_CODEX_AUTH_MISSING"):
            self.run_luna()
        self.assertEqual(self.calls(), [])

    def test_auth_replaced_by_a_real_file_keeps_the_home_and_turns_success_into_failure(self):
        self.add_cache()
        self.add_auth()
        os.environ["FAKE_MODE"] = "replace_auth"
        rc, _, err = self.run_luna()
        kept = Path(self.calls()[0]["codex_home"])
        self.addCleanup(shutil.rmtree, kept, ignore_errors=True)
        self.assertEqual(rc, 1)
        self.assertIn("isolated CODEX_HOME kept: auth.json is no longer a symlink", err)
        self.assertTrue(kept.exists())
        self.assertEqual((self.real / "auth.json").read_text(), "{}")  # the real credential is untouched

    def test_quota_exits_75_with_the_existing_message_once(self):
        self.add_cache()
        self.add_auth()
        os.environ["FAKE_MODE"] = "quota"
        with mock.patch("agents_inc.free_health.report"):
            rc, _, err = self.run_luna()
        self.assertEqual(rc, 75)
        self.assertEqual(err.count("hit a usage or rate limit"), 1)
        self.assertIn(f"agents-inc run: codex {MAP['luna']} hit a usage or rate limit; retry at 5:00 PM", err)

    def test_plain_exit_code_is_unchanged_with_and_without_host_tools(self):
        self.add_cache()
        self.add_auth()
        os.environ["FAKE_MODE"] = "fail"
        self.assertEqual(self.run_luna()[0], 7)
        self.assertEqual(self.run_luna(host_tools=False)[0], 7)

    def test_a_run_without_host_tools_keeps_the_callers_codex_home(self):
        # FR-023: pre-028 luna routes are untouched: no isolated home, no catalog, no instructions override.
        self.add_auth()
        rc, _, err = self.run_luna(host_tools=False)
        call = self.calls()[0]
        self.assertEqual(rc, 0)
        self.assertEqual(call["codex_home"], str(self.operator_home))
        self.assertFalse(any(a.startswith(("model_catalog_json=", "model_instructions_file=")) for a in call["argv"]))
        self.assertNotIn('"codex_home": "isolated"', err)


class PreMod028RoutesTest(unittest.TestCase):
    """Spec 028 FR-023, SC-007: the luna routes that exist before the native type (dispatch, the @luna at-route, a broker
    Worker) never ask for host tools, the stripped catalog or an isolated CODEX_HOME."""

    HOST_BITS = ("model_instructions_file", "model_catalog_json")

    def test_plain_luna_argv_carries_no_host_tools_bits(self):
        for tools in (False, True):
            argv = build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, tools=tools)
            self.assertFalse([a for a in argv if a.startswith(self.HOST_BITS)])
        worker = build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, tools=True, worker=(Path("/c"), "r1"))
        self.assertFalse([a for a in worker if a.startswith(self.HOST_BITS)])

    def test_the_plain_tool_free_luna_run_keeps_the_callers_codex_home(self):
        done = SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        err = io.StringIO()
        with mock.patch.object(runtime, "load_model_map", return_value=MAP), \
                mock.patch.object(runtime.subprocess, "run", return_value=done) as sp, \
                mock.patch.object(runtime, "lead_codex_home") as home, \
                mock.patch.object(runtime.os, "access", return_value=True), \
                mock.patch.object(Path, "is_file", return_value=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            run_codex("luna", "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF, no_tools=True)
        home.assert_not_called()
        self.assertFalse([a for a in sp.call_args[0][0] if a.startswith(self.HOST_BITS)])
        self.assertIsNone(sp.call_args[1]["env"])
        self.assertNotIn("isolated", err.getvalue())
        self.assertNotIn("catalog", err.getvalue())

    def test_no_pre_028_route_source_passes_host_tools(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ("agents_inc/install/dispatch.py", "agents_inc/install/broker.py",
                    "skills/codex-bridge/scripts/at_route.sh", "skills/codex-bridge/scripts/agent.sh"):
            path = root / rel
            if path.is_file():
                self.assertNotRegex(path.read_text(), r"host[-_]tools", rel)


class LeadMcpTest(unittest.TestCase):
    """D51 MCP transport: --lead appends the mcp_servers.agents_inc overrides."""

    def test_lead_argv_overrides_and_approve(self):
        with tempfile.TemporaryDirectory() as d:
            argv = build_codex_argv(EXE, "terra", "medium", Path("/w"), EFF, MAP, True, lead_dir=Path(d))
            joined = [a for a in argv if a.startswith("mcp_servers.agents_inc.")]
            self.assertEqual([a.split("=", 1)[0] for a in joined], [
                "mcp_servers.agents_inc.command", "mcp_servers.agents_inc.args",
                "mcp_servers.agents_inc.tool_timeout_sec", "mcp_servers.agents_inc.default_tools_approval_mode",
                "mcp_servers.agents_inc.required", "mcp_servers.agents_inc.startup_readiness",
                "mcp_servers.agents_inc.startup_timeout_sec"])
            self.assertIn("mcp_servers.agents_inc.required=true", argv)
            self.assertIn('mcp_servers.agents_inc.startup_readiness="catalog"', argv)
            self.assertIn("mcp_servers.agents_inc.startup_timeout_sec=30", argv)
            self.assertIn('mcp_servers.agents_inc.default_tools_approval_mode="approve"', argv)
            args_value = [a for a in joined if ".args=" in a][0].split("=", 1)[1]
            self.assertEqual(json.loads(args_value), [str(runtime.MCP_BROKER), "--run-dir", str(Path(d).resolve())])
            self.assertTrue(runtime.MCP_BROKER.is_file())
            self.assertIn(f'permissions.{PROFILE}.filesystem', " ".join(argv))

    def test_lead_refuses_luna_and_raw_slug(self):
        with tempfile.TemporaryDirectory() as d:
            for alias in ("luna", "gpt-5.6-terra"):
                with self.assertRaises(ValueError):
                    runtime.lead_args(alias, Path(d))
            with self.assertRaises(ValueError):
                build_codex_argv(EXE, "luna", "medium", Path("/w"), EFF, MAP, False, lead_dir=Path(d))

    def test_lead_run_codex_record_and_exclusions(self):
        done = SimpleNamespace(stdout="OK\n", stderr="", returncode=0)
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with mock.patch.object(runtime, "load_model_map", return_value=MAP), \
                    mock.patch.object(runtime.subprocess, "run", return_value=done) as sp, \
                    mock.patch.object(runtime.os, "access", return_value=True), \
                    mock.patch.object(runtime, "lead_codex_home", return_value=Path(tempfile.mkdtemp())), \
                    mock.patch.object(Path, "is_file", return_value=True), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = run_codex("terra", "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF,
                               lead_dir=Path(d))
                self.assertEqual(rc, 0)
                self.assertIn('"transport": "mcp", "codex_home": "isolated"', err.getvalue())
                self.assertIn('mcp_servers.agents_inc.default_tools_approval_mode="approve"', sp.call_args[0][0])
                for bad in ({"no_tools": True}, {"write_dir": Path(d)}):
                    with self.assertRaises(ValueError):
                        run_codex("terra", "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF,
                                  lead_dir=Path(d), **bad)
                # D57 (#68): a Lead may write to cwd, but never when its run directory sits inside cwd
                self.assertEqual(run_codex("terra", "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE),
                                           EFF, lead_dir=Path(d), write=True), 0)
                argv = sp.call_args[0][0]
                self.assertTrue(any(os.path.realpath(d) in a and "none" in a for a in argv), argv)
                with self.assertRaisesRegex(ValueError, "outside cwd"):
                    run_codex("terra", "medium", Path(d).parent, io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF,
                              lead_dir=Path(d), write=True)
                with self.assertRaises(ValueError):
                    run_codex("luna", "medium", Path("/w"), io.StringIO("p"), SimpleNamespace(codex_path=EXE), EFF,
                              lead_dir=Path(d))


LIVE = os.environ.get("AGENTS_INC_LIVE_PROBES") == "1"
LIVE_TOOLS = os.environ.get("AGENTS_INC_LIVE_TOOLS") == "1"
CODEX = Path("/opt/homebrew/bin/codex") if Path("/opt/homebrew/bin/codex").exists() else (shutil.which("codex") and Path(shutil.which("codex")))
SKIP = "set AGENTS_INC_LIVE_PROBES=1" if not LIVE else ("codex executable absent" if not CODEX else
       ("sandbox-exec absent (not macOS)" if not shutil.which("sandbox-exec") else None))


# Seatbelt text from the tool, or Codex's own policy refusal when it declines to run the command.
# Observed 2026-10-04: seatbelt "Operation not permitted"; Codex refusals "denied by policy", "restricted by policy",
# "denied by the sandbox", "denied by the active filesystem policy". A denial also requires that no tool command succeeded.
DENIAL = r"Operation not permitted|(denied|restricted) by (the )?(active filesystem )?(policy|sandbox)"


@unittest.skipIf(SKIP or not LIVE_TOOLS, f"live sol probes skipped: {SKIP or 'tools are opt-in (D49 provisional); set AGENTS_INC_LIVE_TOOLS=1'}")
class LiveSolProbes(unittest.TestCase):
    """One sol call per probe. Assertions read Codex's transcript for the tool's own result line."""

    def _sol(self, command, write=False):
        prompt = f"Use the shell tool to run exactly: {command}\nThen reply with the verbatim output, nothing else."
        out, err = io.StringIO(), io.StringIO()
        slug = runtime.load_model_map().get("sol", "gpt-5.6-sol")
        with tempfile.TemporaryFile("w+") as stdin:  # subprocess needs a real file descriptor
            stdin.write(prompt); stdin.seek(0)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = run_codex("sol", "medium", REPO, stdin, SimpleNamespace(codex_path=CODEX), {slug: ["medium"]}, tools=True, write=write)
        text = out.getvalue() + err.getvalue()
        print(f"\n--- probe `{command}` rc={rc}\n{text[-1500:]}", file=sys.stderr)
        log = os.environ.get("AGENTS_INC_PROBE_LOG_DIR")
        if log:
            Path(log, f"probe_{self._testMethodName}.log").write_text(f"command: {command}\nrc: {rc}\n{text}")
        if rc == 75:
            self.skipTest("codex usage limit hit (rc 75); probe not run")
        self.assertIn('"tools": "on"', text)
        return rc, text

    def test_a_read_readme(self):
        first = (REPO / "README.md").read_text().splitlines()[0][:40]
        rc, text = self._sol("head -1 README.md")
        self.assertEqual(rc, 0)
        self.assertIn(first, text)

    def test_b_ssh_denied(self):
        _, text = self._sol("ls ~/.ssh")
        self.assertRegex(text, DENIAL)
        self.assertNotRegex(text, r"\bsucceeded in \d+")

    def test_c_config_denied(self):
        _, text = self._sol("ls ~/.config")
        self.assertRegex(text, DENIAL)
        self.assertNotRegex(text, r"\bsucceeded in \d+")

    def test_d_writes_fail(self):
        name = "agents_inc_d49_probe"
        _, text = self._sol(f"touch /tmp/{name}; touch ./{name}; ls /tmp/{name} ./{name}")
        self.assertFalse((Path("/tmp") / name).exists())
        self.assertFalse((REPO / name).exists())
        self.assertIn("Operation not permitted", text)

    def test_e_network_fails(self):
        _, text = self._sol("curl -sS -m 10 https://example.com")
        self.assertNotIn("Example Domain", text)
        self.assertRegex(text, r"Could not resolve host|Operation not permitted|Failed to connect|curl: \(\d+\)")

    def test_g_write_mode(self):
        name = "agents_inc_d49_write_probe"
        _, text = self._sol(f"touch ./{name} && ls ./{name} && rm ./{name} && echo CWD_WRITE_OK; touch /tmp/{name}", write=True)
        self.assertIn("CWD_WRITE_OK", text)
        self.assertFalse((REPO / name).exists())
        self.assertFalse((Path("/tmp") / name).exists())
        self.assertIn(f"touch: /tmp/{name}: Operation not permitted", text)

    def test_f_luna_argv_tool_free(self):
        argv = build_codex_argv(CODEX, "luna", "medium", REPO, EFF, MAP, tools_for("luna"))  # default off
        self.assertIn("features.shell_tool=false", argv)


@unittest.skipIf(SKIP, f"live probes skipped: {SKIP}")
class SeatbeltProbes(unittest.TestCase):
    """No model call: run the same permission profile through `codex sandbox`, the seatbelt Codex uses for tool commands."""

    def _sh(self, script):
        args = runtime.permission_args(REPO, False)
        res = subprocess.run([str(CODEX), "sandbox", *args, "--", "/bin/sh", "-c", script], cwd=REPO,
                             capture_output=True, text=True, timeout=60)
        return res.stdout + res.stderr

    def test_read_cwd(self):
        self.assertIn((REPO / "README.md").read_text().splitlines()[0][:40], self._sh("head -1 README.md"))

    def test_home_denied(self):
        for target in ("~/.ssh", "~/.config", "~/.claude", "~/.local", "~"):
            self.assertIn("Operation not permitted", self._sh(f"ls {target} >/dev/null"), target)

    def test_writes_denied(self):
        name = "agents_inc_d49_seatbelt"
        out = self._sh(f"touch /tmp/{name}; touch ./{name}")
        self.assertEqual(out.count("Operation not permitted"), 2, out)
        self.assertFalse((Path("/tmp") / name).exists() or (REPO / name).exists())

    def test_network_denied(self):
        out = self._sh("curl -sS -m 10 https://example.com")
        self.assertNotIn("Example Domain", out)
        self.assertRegex(out, r"Could not resolve host|Operation not permitted|Failed to connect")


if __name__ == "__main__":
    unittest.main()


class DeniedSkillArgsTest(unittest.TestCase):
    def test_skills_linked_into_local_are_disabled(self):
        import tempfile
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            real = home / ".local/share/x/wb"; real.mkdir(parents=True); (real / "SKILL.md").write_text("x")
            skills = home / ".agents/skills"; skills.mkdir(parents=True)
            (skills / "workerbee").symlink_to(real)
            ok = skills / "other"; ok.mkdir(); (ok / "SKILL.md").write_text("x")
            args = runtime._denied_skill_args(home)
            self.assertEqual(args[0], "-c")
            self.assertIn("workerbee/SKILL.md", args[1]); self.assertIn("enabled=false", args[1])
            self.assertNotIn("other", args[1])
            self.assertEqual(runtime._denied_skill_args(home / "none"), [])


class LeadBuilderContainmentTest(unittest.TestCase):
    def test_builder_refuses_lead_write_inside_cwd(self):
        import tempfile
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            cwd = Path(raw); lead = cwd / "broker"; lead.mkdir()
            with self.assertRaisesRegex(ValueError, "outside cwd"):
                runtime.build_codex_argv(Path("/bin/codex"), "terra", "low", cwd, {runtime.MODEL_ALIASES["terra"]: ["low"]}, tools=True, write=True, lead_dir=lead)

    def test_nested_skill_into_local_is_disabled(self):
        import tempfile
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            real = home / ".local/x"; real.mkdir(parents=True); (real / "SKILL.md").write_text("x")
            nest = home / ".agents/skills/bundle/skills"; nest.mkdir(parents=True)
            (nest / "foo").symlink_to(real)
            self.assertIn("bundle/skills/foo/SKILL.md", runtime._denied_skill_args(home)[1])


class SkillLoopTest(unittest.TestCase):
    def test_symlink_loop_is_walked_once(self):
        import tempfile
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            real = home / ".local/x"; real.mkdir(parents=True); (real / "SKILL.md").write_text("x")
            skills = home / ".agents/skills"; skills.mkdir(parents=True)
            (skills / "wb").symlink_to(real)
            for i in range(20):
                (skills / f"loop{i}").symlink_to(skills)
            self.assertEqual(runtime._denied_skill_args(home)[1].count("enabled=false"), 1)
