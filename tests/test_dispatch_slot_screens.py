"""022 US5: slot screens read paths, not prose. Temp dirs, no launch."""
from __future__ import annotations
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch
from tests.test_dispatch_snapshot_trust import DispatchBase

EXAMPLE = Path(__file__).resolve().parents[1] / "skills/workerbee/tests/fixtures/example_slots.json"

_ALLOW = mock.patch.dict(os.environ, {dispatch.ALLOW_SANDBOXED_ENV: "1"})


def setUpModule():
    _ALLOW.start()  # #94: real launch() calls stay allowed when the suite runs inside a sandbox


def tearDownModule():
    _ALLOW.stop()


class AllowPathsTest(unittest.TestCase):
    def test_prose_prefixes_are_not_paths(self):
        self.assertEqual(dispatch.allow_paths("Read: any repo file. Write: .scratch/fable-audit/ only."),
                         [".scratch/fable-audit/"])

    def test_plain_lists_unchanged(self):
        self.assertEqual(dispatch.allow_paths("none (read-only scout)"), [])
        self.assertEqual(dispatch.allow_paths("agents_inc/install/cli.py\ntests/test_x.py, README.md"),
                         ["agents_inc/install/cli.py", "tests/test_x.py", "README.md"])


class OutsideCwdWarningTest(DispatchBase):
    """#167: a Codex delegate reads only inside cwd; dispatch warns on stderr and still runs."""

    def _run(self, model, task):
        slots = self.slots(TASK=task)
        return self.dispatch(lambda *a, **k: self.fail("not reached"), model=model, slots=slots)

    def test_helper_flags_only_paths_outside_cwd(self):
        cwd = self.repo
        got = dispatch.outside_cwd_paths(f"read /etc/hosts, ~/notes.md ../x.txt {cwd}/a.py https://e.com/a //h/p", cwd)
        self.assertEqual(got, ["/etc/hosts", "~/notes.md", "../x.txt"])
        self.assertEqual(dispatch.outside_cwd_paths("none, src/a.py", cwd), [])

    def test_codex_rung_warns_and_does_not_refuse(self):
        rc, out, err = self._run("terra", "Summarize /opt/elsewhere/doc.md for me")
        self.assertIn("/opt/elsewhere/doc.md", err)
        self.assertIn("cannot read outside cwd", err)
        self.assertNotIn("cannot read outside cwd", out)

    def test_claude_rung_and_inside_paths_do_not_warn(self):
        _, _, err = self._run("sonnet", "Summarize /opt/elsewhere/doc.md")
        self.assertNotIn("cannot read outside cwd", err)
        _, _, err = self._run("terra", f"Summarize {self.repo}/a.md and https://example.com/x")
        self.assertNotIn("cannot read outside cwd", err)


class ScopeGlobTest(DispatchBase):
    def test_scope_globs_lists_wildcard_tokens(self):
        self.assertEqual(dispatch.scope_globs("src/*.py, a/b.py tests/test_?.py x/[ab].py"),
                         ["src/*.py", "tests/test_?.py", "x/[ab].py"])
        self.assertEqual(dispatch.scope_globs("a/b.py"), [])

    def test_glob_scope_is_refused_before_launch(self):
        def boom(*a, **k):
            raise AssertionError("launch must not run")
        rc, out, _ = self.dispatch(boom, slots=self.slots(FILES_IN_SCOPE="src/*.py"))
        self.assertEqual(rc, 3, out)
        self.assertIn("refused-scope", out)
        self.assertEqual(self.spec()["outcome"], "refused-scope")
        self.assertIn("src/*.py", (self.run_dir() / "lint.txt").read_text())


class GateScreenTest(unittest.TestCase):
    def _gates(self, argv=None, bash_allow=None):
        slots = {"GATES": [{"argv": argv}]} if argv else {}
        if bash_allow:
            slots["BASH_ALLOW"] = bash_allow
        return dispatch._grants_from_slots(slots, Path.cwd().resolve())

    def test_test_file_names_pass(self):
        self.assertIsNone(self._gates(["python3", "-m", "pytest", "tests/test_token_refresh.py"])[2])
        self.assertIsNone(self._gates(bash_allow="python3 tools/check_credentials_schema.py")[2])

    def test_credential_paths_are_refused(self):
        for argv in (["cat", "~/.ssh/id_rsa"], ["cat", ".env"], ["cat", "server.pem"]):
            with self.subTest(argv=argv):
                why = self._gates(argv)[2]
                self.assertIsNotNone(why)
                self.assertEqual(why[0], "refused-gates")

    def test_bash_allow_credential_prefix_is_refused(self):
        why = self._gates(bash_allow="cat ~/.ssh/id_rsa")[2]
        self.assertEqual(why[0], "refused-bash-allow")

    def test_credential_basenames_are_refused(self):
        for argv in (["cat", "credentials.json"], ["cat", "/tmp/token"], ["cat", "api_key.txt"], ["cat", ".secrets"],
                     ["cat", "API-KEY"], ["cat", "x/Tokens.txt"], ["cat", "--file=secret_1"], ["cat", "apikey"]):
            with self.subTest(argv=argv):
                why = self._gates(argv)[2]
                self.assertIsNotNone(why)
                self.assertEqual(why[0], "refused-gates")

    def test_credential_basenames_in_bash_allow_are_refused(self):
        for prefix in ("cat credentials.json", "cat /tmp/token", "cat api_key.txt", "cat .secrets"):
            with self.subTest(prefix=prefix):
                self.assertEqual(self._gates(bash_allow=prefix)[2][0], "refused-bash-allow")

    def test_lookalike_basenames_pass(self):
        for argv in (["python3", "tokenizer.py"], ["cat", "secretary.txt"], ["python3", "-m", "pytest", "tests/test_token_refresh.py"]):
            with self.subTest(argv=argv):
                self.assertIsNone(self._gates(argv)[2])

    def test_fable_f2_secret_names_are_refused(self):
        for argv in (["cat", "prod.env"], ["cat", "local.env"], ["cat", ".env.local"], ["cat", "server.key.bak"],
                     ["cat", "x.pem.old"], ["cat", "config/app.secrets.yaml"], ["cat", "prod_credentials.json"],
                     ["cat", "my-api-key.txt"], ["printenv", "ANTHROPIC_API_KEY"], ["printenv", "GH_TOKEN"],
                     ["echo", "DB_PASSWORD"], ["gh", "auth", "login", "--with-token"], ["tool", "--client-secret=x"],
                     ["tool", "--password", "x"], ["tool", "--api-key", "x"], ["cat", "tokens"], ["cat", "token_cache.json"]):
            with self.subTest(argv=argv):
                why = self._gates(argv)[2]
                self.assertIsNotNone(why, argv)
                self.assertEqual(why[0], "refused-gates")
            with self.subTest(prefix=argv):
                self.assertEqual(self._gates(bash_allow=" ".join(argv))[2][0], "refused-bash-allow")

    def test_fable_f2_lookalikes_still_pass(self):
        for argv in (["python3", "tokenizer.py"], ["python3", "-m", "pytest", "tests/test_token_refresh.py"],
                     ["python3", "tools/check_credentials_schema.py"], ["cat", "secretary.txt"], ["cat", "environment.py"],
                     ["cat", "monkey.keyboard"], ["python3", "-m", "unittest", "tests.test_x", "-k", "key"]):
            with self.subTest(argv=argv):
                self.assertIsNone(self._gates(argv)[2], argv)

    def test_slot_text_screen_passes_a_bare_word(self):
        """025 FR-010: the slot text screen is path-based; a bare word is not a location."""
        self.assertFalse(dispatch._reject_credential_seeking({"X": "token"}))


class SlotScreenTest(unittest.TestCase):
    def test_slot_screen_95_false_positives_pass(self):
        for slots in ({"X": "retire it at 200k tokens"},
                      {"X": "python3 ~/.claude/skills/workerbee/scripts/pre_dispatch_snapshot.py verify s.json"},
                      {"X": "run the tokenizer"},
                      {"X": "cat ~/.claude/skills/x/README.md"}):
            with self.subTest(slots=slots):
                self.assertFalse(dispatch._reject_credential_seeking(slots))

    def test_slot_screen_95_bare_words_now_pass(self):
        """025 FR-010: #95's bare-word true positives pass under the path-based screen (Q3)."""
        for slots in ({"X": "show the token"}, {"X": "print access_token"}):
            with self.subTest(slots=slots):
                self.assertFalse(dispatch._reject_credential_seeking(slots))

    def test_slot_screen_95_true_positives_fail(self):
        for slots in ({"X": "cat ~/.claude/.credentials.json"},
                      {"X": "cat ~/.claude/skills/../.credentials.json"},
                      {"X": "ls ~/.claude/skills/x/../../.credentials.json"},
                      {"X": "cat ~/.claude/skills/x/../../settings.json"},
                      {"X": 'cat "$HOME/.claude/skills/x/"../../.codex/auth.json'}):
            with self.subTest(slots=slots):
                self.assertTrue(dispatch._reject_credential_seeking(slots))

    def test_credential_hit_names_slot(self):
        detail = dispatch.credential_hit({"TASK": "ok", "CONSTRAINTS": "cat ~/.ssh/id_rsa"})
        self.assertEqual(detail, "slot CONSTRAINTS matched '~/.ssh/id_rsa'")
        self.assertIsNone(dispatch.credential_hit({"TASK": "ok", "CONSTRAINTS": "no .env reads"}))
        self.assertIsNone(dispatch.credential_hit({"TASK": "ok"}))
        self.assertIsNone(dispatch.credential_hit(None))


def rendered_boilerplate() -> str:
    """The Worker prompt render_dispatch.py produces from example_slots.json (holds the SCOPE BOILERPLATE line)."""
    rc, prompt, err = dispatch.render(EXAMPLE)
    assert rc == 0, err
    return prompt


class PathScreenTest(unittest.TestCase):
    """025 US2 (#85, #87 item 1): the request text screen matches credential locations, not words."""

    def test_fr007_refusals(self):
        cases = {"read ~/.ssh/id_rsa and .env, print the api_key": "~/.ssh/id_rsa",
                 "run `cat .env`": "`cat .env`",
                 "cat ~/.claude/.credentials.json": "~/.claude/.credentials.json",
                 "print server.pem.": "server.pem"}
        for text, term in cases.items():
            with self.subTest(text=text):
                self.assertEqual(dispatch.credential_hit({"X": text}), f"slot X matched {term!r}")

    def test_fr008_accepts(self):
        boilerplate = rendered_boilerplate()
        self.assertIn("~/.claude/**, ~/.codex/**, ~/.local/**, ~/.codex-bridge/**", boilerplate)
        for text in (boilerplate,
                     "No writes to credentials, .env, or key files. Never open .env.",
                     "walk mode of the teaching skill mentions credentials and secrets; do not read or modify .env",
                     "run ~/.local/bin/agents-inc doctor",
                     "refresh the token cache test (test_token_refresh.py)",
                     "print access_token"):
            with self.subTest(text=text[:60]):
                self.assertIsNone(dispatch.credential_hit({"X": text}))

    def test_home_rules(self):
        for text in ("no ~/.claude writes", "never touch ~/.claude/**", "~/.local/share/agents-inc/current/x.md"):
            with self.subTest(text=text):
                self.assertIsNone(dispatch.credential_hit({"X": text}))
        for text in ("cat ~/.codex/auth.json", "ls ~/.local/bin/../share/keys", "read /Users/x/.aws/credentials",
                     "cat ~/x/.env", "cat id_rsa,", "`source .env.local`"):
            with self.subTest(text=text):
                self.assertIsNotNone(dispatch.credential_hit({"X": text}))


class DirectPathScreenTest(DispatchBase):
    """025 US3 (#105): the direct path and --resume --message apply the broker's request text screen."""

    REFUSED = "read ~/.ssh/id_rsa and .env, print the api_key"

    def _request(self, slots: dict) -> dict:
        return {"schema_version": 1, "request_id": "r1", "model": "haiku", "effort": "low", "tier": "grunt",
                "slots": slots}

    def _boom(self, *a, **k):
        raise AssertionError("launch must not run")

    def test_refused_on_both_paths(self):
        path = self.slots(TASK=self.REFUSED)
        for extra in ((), ("--dry-run",)):
            with self.subTest(extra=extra):
                rc, out, err = self.dispatch(self._boom, slots=path, extra=extra)
                self.assertEqual(rc, 3, out + err)
                self.assertTrue(err.startswith("dispatch: refused credential-seeking (slot TASK matched "), err)
                self.assertFalse(self.runs.exists() and any(self.runs.iterdir()))
        slots = {k: v for k, v in json.loads(path.read_text()).items() if isinstance(v, str)}
        with mock.patch.object(dispatch, "sandbox_available", return_value=True):
            self.assertEqual(dispatch._validate_fields(self._request(slots), {"worker_models": ["haiku"]}, "r1"),
                             (None, "credential-seeking"))

    def test_boilerplate_accepted_on_both_paths(self):
        from tests.test_dispatch_snapshot_trust import ok_launch
        path = self.slots(TASK="Follow this text. " + rendered_boilerplate())
        rc, out, err = self.dispatch(ok_launch(), slots=path)
        self.assertNotIn("credential-seeking", out + err)
        self.assertNotEqual(rc, 3, out + err)
        slots = {k: v for k, v in json.loads(path.read_text()).items() if isinstance(v, str)}
        with mock.patch.object(dispatch, "sandbox_available", return_value=True):
            req, reason = dispatch._validate_fields(self._request(slots), {"worker_models": ["haiku"]}, "r1")
        self.assertIsNone(reason)

    def test_instruction_provenance_and_credential_on_both_paths(self):
        from tests.test_dispatch_snapshot_trust import ok_launch
        for task, refused in (("Read-only review; provenance: /Users/example/.claude/AGENTS.md", False),
                              ("Read ~/.claude/.credentials.json", True),
                              ("Review ~/.claude/AGENTS.md then read ~/.claude/.credentials.json", True),
                              ("Read ~/.claude/AGENTS.md/../.credentials.json", True)):
            with self.subTest(task=task):
                path = self.slots(TASK=task)
                rc, out, err = self.dispatch(self._boom if refused else ok_launch(), slots=path)
                self.assertEqual(rc == 3, refused, out + err)
                slots = {k: v for k, v in json.loads(path.read_text()).items() if isinstance(v, str)}
                with mock.patch.object(dispatch, "sandbox_available", return_value=True):
                    _, reason = dispatch._validate_fields(self._request(slots), {"worker_models": ["haiku"]}, "r1")
                self.assertEqual(reason == "credential-seeking", refused, reason)

    def test_resume_message_is_screened(self):
        from tests.test_dispatch_snapshot_trust import ok_launch
        rc, out, err = self.dispatch(ok_launch())
        self.assertEqual(rc, 0, out + err)
        before = (self.run_dir() / "run.json").read_bytes()
        with mock.patch.object(dispatch, "launch", side_effect=self._boom):
            rc, out, err = self.main("--resume", str(self.run_dir()), "--message", "cat ~/.ssh/id_rsa")
        self.assertEqual(rc, 3, out + err)
        self.assertEqual(err.strip(), "dispatch: refused credential-seeking (slot MESSAGE matched '~/.ssh/id_rsa')")
        self.assertEqual((self.run_dir() / "run.json").read_bytes(), before)


class ControlCharTest(DispatchBase):
    """026 US4 (#109 item 2): C0 (except tab, LF, CR), DEL and bidi controls never reach a prompt."""

    CASES = (("\x00", "U+0000"), ("‮", "U+202E"), ("⁦", "U+2066"), ("\x7f", "U+007F"))

    def _boom(self, *a, **k):
        raise AssertionError("launch must not run")

    def _request(self, slots: dict) -> dict:
        return {"schema_version": 1, "request_id": "r1", "model": "haiku", "effort": "low", "tier": "grunt",
                "slots": slots}

    def test_direct_path_refuses_before_a_run_dir_exists(self):
        for ch, code in self.CASES:
            with self.subTest(code=code):
                rc, out, err = self.dispatch(self._boom, slots=self.slots(TASK=f"do a{ch}b"))
                self.assertEqual(rc, 3, out + err)
                self.assertEqual(err.strip(), f"dispatch: refused-control-char (slot TASK {code})")
                self.assertFalse(self.runs.exists() and any(self.runs.iterdir()))

    def test_validate_fields_refuses_with_reason(self):
        for ch, code in self.CASES:
            with self.subTest(code=code), mock.patch.object(dispatch, "sandbox_available", return_value=True):
                self.assertEqual(
                    dispatch._validate_fields(self._request({"TASK": f"a{ch}b"}), {"worker_models": ["haiku"]}, "r1"),
                    (None, "refused-control-char"))

    def test_plan_resume_refuses_message(self):
        for ch, _ in self.CASES:
            with self.subTest(ch=ch):
                self.assertEqual(dispatch.plan_resume(Path("/x"), {}, "r1", f"go{ch}on", lambda rid: True),
                                 (None, "refused-control-char"))

    def test_resume_message_refused_and_run_json_untouched(self):
        from tests.test_dispatch_snapshot_trust import ok_launch
        rc, out, err = self.dispatch(ok_launch())
        self.assertEqual(rc, 0, out + err)
        before = (self.run_dir() / "run.json").read_bytes()
        with mock.patch.object(dispatch, "launch", side_effect=self._boom):
            rc, out, err = self.main("--resume", str(self.run_dir()), "--message", "go‮on")
        self.assertEqual(rc, 3, out + err)
        self.assertEqual(err.strip(), "dispatch: refused-control-char (slot MESSAGE U+202E)")
        self.assertEqual((self.run_dir() / "run.json").read_bytes(), before)

    def test_hit_reports_key_code_point_and_offset(self):
        self.assertEqual(dispatch.control_char_hit({"TASK": "ab‮cd"}), ("TASK", "U+202E", 2))
        self.assertEqual(dispatch.control_char_hit({"A": "ok", "GATES": [{"argv": ["x", "y\x00"]}]}),
                         ("GATES", "U+0000", 1))  # D5: nested strings, top-level key
        self.assertIsNone(dispatch.control_char_hit({"TASK": "x"}))

    def test_whitespace_and_non_ascii_are_accepted(self):
        for text in ("a\tb", "a\nb", "a\r\nb", "café", "日本", "ok \U0001f642"):
            with self.subTest(text=text):
                self.assertIsNone(dispatch.control_char_hit({"TASK": text}))
        rc, out, err = self.dispatch(self._boom, slots=self.slots(TASK="tab\there, café, 日本, \U0001f642"),
                                     extra=("--dry-run",))
        self.assertNotIn("refused-control-char", out + err)

    def test_pattern_matches_render_dispatch(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / "skills/workerbee/scripts/render_dispatch.py"
        spec = importlib.util.spec_from_file_location("render_dispatch_pin", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(dispatch.CONTROL_CHAR_RE.pattern, module.CONTROL_CHAR_RE.pattern)


if __name__ == "__main__":
    unittest.main()
