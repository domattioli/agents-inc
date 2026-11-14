"""Spec 037 (chunk A): free models through `agents-inc dispatch`, with stub wrappers and no provider call."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch, free_launch
from tests.test_dispatch_cli import STATUS_RE, CliBase, _fake_launch

FAKES = Path(__file__).resolve().parent / "fixtures" / "fake_wrappers"
RENDER_DIR = Path(__file__).resolve().parents[1] / "skills" / "workerbee" / "scripts"
REPORT_GATE = {"argv": [sys.executable, "-c", "import sys; sys.exit(0 if 'ok reply' in open(sys.argv[1]).read() else 1)",
                        "{report}"]}


class FreeBase(CliBase):
    """CliBase plus copies of the stub wrappers patched in as the wrapper directory, and a call log."""

    def setUp(self):
        super().setUp()
        self.wrappers = self.root / "wrappers"
        shutil.copytree(FAKES, self.wrappers)
        for stub in self.wrappers.glob("*.sh"):
            stub.chmod(0o755)
        patcher = mock.patch.object(free_launch, "WRAPPER_DIR", self.wrappers)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log = self.root / "calls.jsonl"
        from agents_inc import free_health, router  # hermetic: never read the operator's health or usage files
        for target, name, value in ((free_health, "load_health", lambda: {}), (router, "_at_cap", lambda *a, **k: False)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # CliBase.tearDown restores os.environ; a patch.dict cleanup here would run after it and leak HOME (#185).
        os.environ.update({"FAKE_LOG": str(self.log), "FAKE_REPLY": "ok reply", "FAKE_RC": "0"})
        self.n = 0

    def _free_slots(self, **extra) -> Path:
        extra.setdefault("TASK_KIND", "summarize")
        extra.setdefault("CLASSIFICATION", "public (test text)")
        extra.setdefault("PRE_EXISTING_CHANGES", "")  # the renderer writes the default snapshot text
        return self._slots(**extra)

    def _go(self, model, slots=None, env=None):
        """Dispatch one free run into its own run-dir parent. Return (rc, out, err, run dir)."""
        self.n += 1
        runs = self.root / f"runs{self.n}"
        with mock.patch.dict(os.environ, env or {}):
            rc, out, err = self._main("--slots", str(slots or self._free_slots(GATES=[REPORT_GATE])),
                                      "--model", model, "--cwd", str(self.repo), "--run-dir", str(runs))
        dirs = list(runs.iterdir()) if runs.is_dir() else []
        return rc, out, err, (dirs[0] if dirs else None)

    def _calls(self) -> list:
        if not self.log.is_file():
            return []
        return [json.loads(ln) for ln in self.log.read_text().splitlines() if ln.strip()]


class FreeLaunchUnitTest(unittest.TestCase):
    def test_map_has_ten_exact_slugs_and_known_wrappers(self):
        self.assertEqual(len(free_launch.FREE_MODELS), 10)
        for slug, entry in free_launch.FREE_MODELS.items():
            self.assertEqual(entry.slug, slug)
            self.assertIn(entry.wrapper, ("gask.sh", "mask.sh", "oask.sh"))
            self.assertGreater(entry.max_input_chars, 0)
            self.assertTrue(entry.host)
            if entry.provider == "openrouter":
                self.assertTrue(slug.endswith(":free"), slug)  # free-only guard (D17)
                self.assertEqual(entry.model_env, slug)
            else:
                self.assertIsNone(entry.model_env)
                self.assertTrue(entry.tier)

    def test_is_free_is_exact(self):
        self.assertTrue(free_launch.is_free("codestral-latest"))
        for slug in ("gemini-3.1-pro-preview", "mistral-large-latest", "codestral", "CODESTRAL-LATEST", "luna", "", None):
            self.assertFalse(free_launch.is_free(slug), slug)

    def test_wrapper_argv_has_no_prompt(self):
        argv = free_launch.wrapper_argv("gemini-3.8-flash", Path("/w"))
        self.assertEqual(argv, ["bash", "/w/gask.sh", "--tier", "digest"])
        self.assertEqual(free_launch.wrapper_argv("codestral-latest", Path("/w")), ["bash", "/w/mask.sh", "--tier", "code"])
        self.assertEqual(free_launch.wrapper_argv("google/gemma-4-31b-it:free", Path("/w")), ["bash", "/w/oask.sh"])

    def test_wrapper_env(self):
        env = free_launch.wrapper_env("google/gemma-4-31b-it:free", "extract", {"WORKERBEES_GOVERNANCE": "on", "X": "1"})
        self.assertEqual((env["WORKERBEES_GOVERNANCE"], env["TASK"], env["MODEL"], env["X"]),
                         ("off", "extract", "google/gemma-4-31b-it:free", "1"))
        env = free_launch.wrapper_env("gemini-3.8-flash", None, {"MODEL": "leak"})
        self.assertNotIn("MODEL", env)  # the tier picks the model; an inherited MODEL never does
        self.assertEqual(env["TASK"], free_launch.DEFAULT_TASK_KIND)

    def test_strip_snapshot(self):
        text = "x\nPRE-EXISTING CHANGES: snapshot <snapshot>; verify with `python3 a.py verify <snapshot> --allow b`\n"
        out = free_launch.strip_snapshot(text)
        self.assertNotIn("snapshot>", out)
        self.assertNotIn("verify", out)
        self.assertNotIn("<snapshot>", free_launch.strip_snapshot("snapshot <snapshot> (by hand)"))

    def test_free_fan_out_default_is_zero(self):
        sys.path.insert(0, str(RENDER_DIR))
        try:
            import render_dispatch
        finally:
            sys.path.remove(str(RENDER_DIR))
        for slug in free_launch.FREE_MODELS:
            self.assertEqual(render_dispatch.default_fan_out({}, slug), "width 0, total 0, depth 0", slug)
            self.assertEqual(render_dispatch.default_fan_out({"MODEL": slug}), "width 0, total 0, depth 0", slug)
        self.assertEqual(render_dispatch.default_fan_out({}, "sonnet"), "width 2, total 4, depth 1")  # unchanged


class RunTest(FreeBase):
    def test_green_with_report_gate_for_each_slug(self):
        for slug, entry in free_launch.FREE_MODELS.items():
            with self.subTest(slug=slug):
                self.log.unlink(missing_ok=True)
                rc, out, err, run_dir = self._go(slug)
                self.assertEqual(rc, 0, out + err)
                self.assertRegex(out.strip(), STATUS_RE)
                self.assertIn("outcome=green", out)
                calls = self._calls()
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]["governance"], "off")
                self.assertEqual(calls[0]["task"], "summarize")
                self.assertEqual(calls[0]["model"], entry.model_env)
                spec = json.loads((run_dir / "run.json").read_text())
                self.assertEqual((spec["kind"], spec["provider"], spec["cost_usd"], spec["workers_spawned"]),
                                 ("free", entry.provider, 0, 0))
                self.assertEqual((spec["task_kind"], spec["classification"]), ("summarize", "public (test text)"))
                wrapper = self.wrappers / entry.wrapper
                self.assertEqual(spec["wrapper"], str(wrapper))
                self.assertEqual(spec["wrapper_sha256"], hashlib.sha256(wrapper.read_bytes()).hexdigest())
                self.assertEqual((run_dir / "stdout.md").read_text(), "ok reply")

    def test_prompt_on_stdin_never_argv_and_no_snapshot_in_prompt(self):
        rc, out, err, run_dir = self._go("codestral-latest")
        self.assertEqual(rc, 0, out + err)
        call = self._calls()[0]
        self.assertEqual(call["argv"], ["--tier", "code"])
        prompt = (run_dir / "prompt.md").read_text()
        self.assertEqual(call["stdin"].strip(), prompt.strip())
        for leak in ("SNAPSHOT VERIFIER", "<snapshot>", str(run_dir / "snapshot.json")):
            self.assertNotIn(leak, prompt)
        self.assertTrue((run_dir / "snapshot.json").is_file())  # captured after the wrapper call, before the gates

    def test_fan_out_defaults_to_zero_and_skips_fan_out_check(self):
        slots = self._free_slots(GATES=[REPORT_GATE])
        data = json.loads(slots.read_text())
        data.pop("FAN_OUT")
        slots.write_text(json.dumps(data))
        rc, out, err, run_dir = self._go("gemini-flash-lite-latest", slots)
        self.assertEqual(rc, 0, out + err)  # the reply has no WORKERS SPAWNED line, so _fan_out_check would be red
        self.assertIn("width 0, total 0, depth 0", (run_dir / "prompt.md").read_text())
        spec = json.loads((run_dir / "run.json").read_text())
        self.assertEqual(spec["fan_out"], {"width": 0, "total": 0, "depth": 0})
        self.assertNotIn("workers_spawned_attempts", spec)

    def test_no_gates_is_unverified_exit_zero(self):
        rc, out, err, run_dir = self._go("ministral-3b-latest", self._free_slots(GATES=[]))
        self.assertEqual(rc, 0, out + err)
        self.assertIn("outcome=unverified reason=no-gates", out)
        self.assertNotIn("outcome=green", out)

    def test_failing_report_gate_is_red_gate_failed(self):
        rc, out, err, run_dir = self._go("gemini-3.8-flash", env={"FAKE_REPLY": "something else"})
        self.assertEqual(rc, 1, out + err)
        self.assertIn("outcome=red reason=gate-failed", out)

    def test_report_token_expands_to_saved_reply_path(self):
        gate = {"argv": [sys.executable, "-c", "import sys; print(sys.argv[1])", "{report}"]}
        rc, out, err, run_dir = self._go("gemini-3.8-flash", self._free_slots(GATES=[gate]))
        self.assertEqual(rc, 0, out + err)
        spec = json.loads((run_dir / "run.json").read_text())
        excerpt = spec["gate_results"][0]["excerpt"].strip()
        self.assertTrue(excerpt.endswith("/" + run_dir.name + "/stdout.md"), excerpt)  # excerpt path prefix is redacted
        self.assertEqual(spec["gate_results"][0]["argv"][-1], "{report}")

    def test_gate_writing_into_repo_is_red_gate_wrote(self):
        gate = {"argv": ["sh", "-c", "echo pwned > gate_wrote.txt"]}
        rc, out, err, run_dir = self._go("codestral-latest", self._free_slots(GATES=[gate]))
        self.assertEqual(rc, 1, out + err)
        self.assertIn("snapshot=CHANGED:gate_wrote.txt outcome=red reason=gate-wrote", out)
        self.assertIn("after gates:", (run_dir / "verify.txt").read_text())

    def test_wrapper_failure_is_red_rc_nonzero(self):
        rc, out, err, run_dir = self._go("codestral-latest", env={"FAKE_RC": "1", "FAKE_STDERR": "mask error 500: boom"})
        self.assertEqual(rc, 1, out + err)
        self.assertIn("outcome=red reason=rc-nonzero", out)

    def test_clean_reply_quoting_429_is_not_quota(self):
        rc, out, err, run_dir = self._go("gemini-3.8-flash", env={"FAKE_REPLY": "ok reply: error 429 rate limit exceeded"})
        self.assertEqual(rc, 0, out + err)
        self.assertIn("outcome=green", out)

    def test_codex_and_claude_dispatch_unchanged(self):
        for model in ("haiku", "luna"):
            with self.subTest(model=model):
                with mock.patch.object(free_launch, "run_free", side_effect=AssertionError("free path")), \
                        mock.patch.object(dispatch, "launch", side_effect=_fake_launch()) as launch:
                    self.n += 1
                    rc, out, err = self._main("--slots", str(self._slots()), "--model", model, "--cwd", str(self.repo),
                                              "--run-dir", str(self.root / f"runs{self.n}"))
                self.assertEqual(rc, 0, out + err)
                self.assertIn("outcome=green", out)
                launch.assert_called_once()
                self.assertEqual(self._calls(), [])


class RefusalTest(FreeBase):
    """Spec 037 US2: every refusal exits 2, names its reason in run.json and lint.txt, and never calls the wrapper."""

    MODEL = "codestral-latest"

    def _refused(self, name, slots, model=None, env=None):
        rc, out, err, run_dir = self._go(model or self.MODEL, slots, env)
        self.assertEqual(rc, 2, out + err)
        self.assertIn(f"refused {name}", out)
        self.assertEqual(json.loads((run_dir / "run.json").read_text())["outcome"], name)
        self.assertIn(name, (run_dir / "lint.txt").read_text())
        self.assertEqual(self._calls(), [], "wrapper was called")
        self.assertFalse((run_dir / "prompt.md").exists())
        return run_dir

    def _slots_without(self, *drop, **extra) -> Path:
        path = self._free_slots(**extra)
        data = json.loads(path.read_text())
        for key in drop:
            data.pop(key, None)
        path.write_text(json.dumps(data))
        return path

    def test_refused_task_missing(self):
        self._refused("refused-task", self._slots_without("TASK_KIND"))

    def test_refused_task_not_allowed(self):
        self._refused("refused-task", self._free_slots(TASK_KIND="refactor"))

    def test_refused_task_reads_routing_at_run_time(self):
        routing = self.root / "routing.json"
        routing.write_text(json.dumps({"optional_allowed_tasks": ["extract"]}))
        with mock.patch.object(free_launch, "ROUTING_PATH", routing):
            self._refused("refused-task", self._free_slots(TASK_KIND="summarize"))

    def test_refused_classification_missing(self):
        self._refused("refused-classification", self._slots_without("CLASSIFICATION"))

    def test_refused_classification_blank_or_unknown(self):
        self._refused("refused-classification", self._free_slots(CLASSIFICATION="  "))
        self._refused("refused-classification", self._free_slots(CLASSIFICATION="restricted (customer data)"))

    def test_refused_classification_confidential_without_authorization(self):
        self._refused("refused-classification", self._free_slots(CLASSIFICATION="confidential (client notes)"))

    def test_confidential_with_workspace_authorization_runs(self):
        auth = self.repo / ".workerbees" / "authorization.json"
        auth.parent.mkdir()
        auth.write_text(json.dumps({"optional_providers": True}))
        rc, out, err, run_dir = self._go(self.MODEL, self._free_slots(CLASSIFICATION="confidential (client notes)",
                                                                       GATES=[REPORT_GATE]))
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(len(self._calls()), 1)

    def test_refused_fan_out(self):
        self._refused("refused-fan-out", self._free_slots(FAN_OUT="width 1, total 2, depth 1"))

    def test_zero_fan_out_is_accepted(self):
        rc, out, err, _ = self._go(self.MODEL, self._free_slots(FAN_OUT="width 0, total 0, depth 0", GATES=[REPORT_GATE]))
        self.assertEqual(rc, 0, out + err)

    def test_refused_grants_permission_mode(self):
        self._refused("refused-grants", self._free_slots(PERMISSION_MODE="bypassPermissions"))
        self._refused("refused-grants", self._free_slots(PERMISSION_MODE="acceptEdits"))

    def test_refused_grants_bash_allow(self):
        self._refused("refused-grants", self._free_slots(BASH_ALLOW=["git status"]))

    def test_plan_and_default_permission_modes_are_accepted(self):
        for mode in ("plan", "default"):
            with self.subTest(mode=mode):
                rc, out, err, _ = self._go(self.MODEL, self._free_slots(PERMISSION_MODE=mode, GATES=[REPORT_GATE]))
                self.assertEqual(rc, 0, out + err)

    def test_refused_inputs_outside_cwd(self):
        (self.root / "outside.txt").write_text("secret-free text")
        self._refused("refused-inputs", self._free_slots(INPUT_FILES=["../outside.txt"]))
        self._refused("refused-inputs", self._free_slots(INPUT_FILES=[str(self.root / "outside.txt")]))

    def test_refused_inputs_symlink(self):
        (self.root / "target.txt").write_text("plain text")
        (self.repo / "link.txt").symlink_to(self.root / "target.txt")
        self._refused("refused-inputs", self._free_slots(INPUT_FILES=["link.txt"]))

    def test_refused_inputs_non_text(self):
        (self.repo / "blob.bin").write_bytes(b"\x00\x01\x02binary")
        self._refused("refused-inputs", self._free_slots(INPUT_FILES=["blob.bin"]))

    def test_refused_inputs_credential_shaped(self):
        (self.repo / "notes.txt").write_text("run: cat ~/.ssh/id_rsa\n")
        self._refused("refused-inputs", self._free_slots(INPUT_FILES=["notes.txt"]))

    def test_refused_inputs_over_size_limit(self):
        limit = free_launch.FREE_MODELS[self.MODEL].max_input_chars
        (self.repo / "big.txt").write_text("a" * (limit + 1))
        self._refused("refused-inputs", self._free_slots(INPUT_FILES=["big.txt"]))

    def test_refused_inputs_missing_file(self):
        self._refused("refused-inputs", self._free_slots(INPUT_FILES=["nope.txt"]))

    def test_input_files_reach_the_prompt_and_run_json(self):
        body = "alpha line\nbeta line\n"
        (self.repo / "a.txt").write_text(body)
        rc, out, err, run_dir = self._go(self.MODEL, self._free_slots(INPUT_FILES=["a.txt"], GATES=[REPORT_GATE]))
        self.assertEqual(rc, 0, out + err)
        record = json.loads((run_dir / "run.json").read_text())
        self.assertEqual(record["input_files"], [{"path": "a.txt", "bytes": len(body),
                                                  "sha256": hashlib.sha256(body.encode()).hexdigest()}])
        call = self._calls()[0]
        self.assertIn("alpha line", json.dumps(call))
        self.assertIn("alpha line", (run_dir / "prompt.md").read_text())

    def test_max_input_chars_is_the_model_limit(self):
        small = min(free_launch.FREE_MODELS.values(), key=lambda m: m.max_input_chars)
        (self.repo / "edge.txt").write_text("b" * small.max_input_chars)
        section, files = free_launch.build_input_section({"INPUT_FILES": ["edge.txt"]}, self.repo, small.max_input_chars)
        self.assertEqual(files[0]["bytes"], small.max_input_chars)
        with self.assertRaises(free_launch.InputsRefused):
            free_launch.build_input_section({"INPUT_FILES": ["edge.txt"]}, self.repo, small.max_input_chars - 1)

    def test_no_input_files_gives_empty_section(self):
        self.assertEqual(free_launch.build_input_section({}, self.repo, 100), ("", []))

    def test_pre_checks_clean_slots_pass(self):
        slots = {"TASK_KIND": "extract", "CLASSIFICATION": "public (x)"}
        self.assertIsNone(free_launch.pre_checks(slots, None, {"optional_allowed_tasks": ["extract"]}, self.repo))

    def test_resume_of_a_free_run_exits_2(self):
        rc, out, err, run_dir = self._go(self.MODEL)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(len(self._calls()), 1)
        rc, out, err = self._main("--resume", str(run_dir), "--message", "again", "--cwd", str(self.repo))
        self.assertEqual(rc, 2, out + err)
        self.assertIn("cannot be resumed", err)
        self.assertEqual(len(self._calls()), 1)


class ClassifyRcTest(unittest.TestCase):
    """Spec 037 R6: one row per wrapper result, each with the wrapper's real stderr form."""

    def _reason(self, rc, stderr, slug="gemini-3.8-flash", stdout=""):
        return free_launch.classify_rc(rc, stdout, stderr, slug)

    def test_success_and_dispatch_timeout_have_no_reason(self):
        self.assertIsNone(self._reason(0, "").reason)
        self.assertIsNone(self._reason(124, "x\nturn timeout after 600s\n").reason)

    def test_rc4_redacted_reply(self):
        err = "oask: reply holds redaction placeholders not in the request: [PERSON_NAME]; unfit for code review (exit 4)"
        self.assertEqual(self._reason(4, err, "google/gemma-4-31b-it:free").reason, "redacted-reply")

    def test_rc2_no_api_key(self):
        for err in ("gask error: no API key (checked a and b)", "mask error: no API key (checked a)",
                    "oask error: no API key (checked a)"):
            self.assertEqual(self._reason(2, err).reason, "provider-key-missing", err)

    def test_other_rc2_is_rc_nonzero(self):
        self.assertEqual(self._reason(2, "error: invalid tier 'x' (expected cheap, code, or deep)").reason, "rc-nonzero")

    def test_rc3_is_wrapper_refused(self):
        self.assertEqual(self._reason(3, "oask: REFUSED — 'x' is not a ':free' model.").reason, "wrapper-refused")
        self.assertEqual(self._reason(3, "gask: REFUSED — legacy wrappers are disabled in governed lanes").reason,
                         "wrapper-refused")

    def test_rc1_429_is_quota_in_each_wrapper_form(self):
        for err in ("gemini error 429: Resource has been exhausted", "oask error 429: Rate limit exceeded",
                    "mistral error 429: Too many requests"):
            self.assertEqual(self._reason(1, err).reason, "quota-paused", err)

    def test_rc1_unreachable_and_timeout_are_blocked_with_host(self):
        rows = (("gemini-3.8-flash", "gemini error: cannot reach generativelanguage.googleapis.com (curl exit 6)",
                 "generativelanguage.googleapis.com"),
                ("gemini-3.8-flash", "gemini timeout after 60s (connect timeout 10s)", "generativelanguage.googleapis.com"),
                ("codestral-latest", "mistral error: cannot reach api.mistral.ai: [Errno 8]", "api.mistral.ai"),
                ("codestral-latest", "mistral chat timeout after 30s: timed out", "api.mistral.ai"),
                ("google/gemma-4-31b-it:free", "oask error: cannot reach openrouter.ai", "openrouter.ai"))
        for slug, err, host in rows:
            with self.subTest(err=err):
                got = self._reason(1, err, slug)
                self.assertEqual(got.reason, "blocked")
                self.assertIn(host, got.detail)

    def test_other_rc1_is_rc_nonzero(self):
        for err in ("gemini error 500: boom", "gemini returned no content", "mistral error 401: Unauthorized"):
            self.assertEqual(self._reason(1, err).reason, "rc-nonzero", err)

    def test_reply_text_is_never_searched(self):
        self.assertEqual(self._reason(1, "gemini error 500: boom", stdout="error 429 cannot reach").reason, "rc-nonzero")

    def test_parse_usage(self):
        self.assertEqual(free_launch.parse_usage("", "[gemini gemini-3.8-flash | in 120 out 30 think 5]\n"),
                         {"input_tokens": 120, "output_tokens": 30, "reasoning_tokens": 5})
        self.assertEqual(free_launch.parse_usage("", "[openrouter m:free | in 7 out 9]"),
                         {"input_tokens": 7, "output_tokens": 9})
        self.assertIsNone(free_launch.parse_usage("[x | in 1 out 2]", "no usage here"))


class FailureTest(FreeBase):
    """Spec 037 US3: wrapper failures end as distinct outcomes and exit codes."""

    def _fail(self, model, rc, stderr, expect_exit, reason, detail_has=None):
        out_rc, out, err, run_dir = self._go(model, env={"FAKE_RC": str(rc), "FAKE_STDERR": stderr, "FAKE_REPLY": ""})
        self.assertEqual(out_rc, expect_exit, out + err)
        self.assertIn(f"outcome=red reason={reason}", out)
        spec = json.loads((run_dir / "run.json").read_text())
        self.assertEqual((spec["outcome"], spec["reason"]), ("red", reason))
        if detail_has:
            self.assertIn(detail_has, spec["reason_detail"])
        return spec

    def test_redacted_reply_rc4(self):
        self._fail("google/gemma-4-31b-it:free", 4, "oask: reply holds redaction placeholders: [PERSON_NAME] (exit 4)",
                   1, "redacted-reply")

    def test_provider_key_missing_rc2(self):
        self._fail("gemini-3.8-flash", 2, "gask error: no API key (checked a and b)", 2, "provider-key-missing")

    def test_other_rc2_is_rc_nonzero(self):
        self._fail("codestral-latest", 2, "error: invalid tier 'x'", 2, "rc-nonzero")

    def test_spend_guard_rc3_is_wrapper_refused(self):
        self._fail("google/gemma-4-31b-it:free", 3, "oask: REFUSED — 'x' is not a ':free' model.", 1, "wrapper-refused")

    def test_gemini_429_is_quota_exit_75(self):
        self._fail("gemini-3.8-flash", 1, "gemini error 429: Resource has been exhausted", 75, "quota-paused")

    def test_oask_429_is_quota_exit_75(self):
        self._fail("nvidia/nemotron-3.5-lightning:free", 1, "oask error 429: Rate limit exceeded", 75, "quota-paused")

    def test_mask_429_is_quota_exit_75(self):
        self._fail("codestral-latest", 1, "mistral error 429: Too many requests", 75, "quota-paused")

    def test_cannot_reach_is_blocked_exit_69_with_host(self):
        spec = self._fail("codestral-latest", 1, "mistral error: cannot reach api.mistral.ai: [Errno 8]", 69, "blocked",
                          "api.mistral.ai")
        self.assertNotIn(" ", spec["reason_detail"])

    def test_gemini_timeout_is_blocked_exit_69_with_host(self):
        self._fail("gemini-3.8-flash", 1, "gemini timeout after 60s (connect timeout 10s)", 69, "blocked",
                   "generativelanguage.googleapis.com")

    def test_http_500_is_rc_nonzero(self):
        self._fail("gemini-flash-lite-latest", 1, "gemini error 500: boom", 1, "rc-nonzero")

    def test_usage_recorded_in_run_json(self):
        rc, out, err, run_dir = self._go("gemini-3.8-flash", env={"FAKE_STDERR": "[gemini gemini-3.8-flash | in 12 out 3]"})
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(json.loads((run_dir / "run.json").read_text())["usage"], {"input_tokens": 12, "output_tokens": 3})

    def test_no_usage_is_null(self):
        rc, out, err, run_dir = self._go("gemini-3.8-flash")
        self.assertIsNone(json.loads((run_dir / "run.json").read_text())["usage"])

    def test_cooldown_ends_quota_paused_with_no_wrapper_call(self):
        until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        from agents_inc import free_health
        with mock.patch.object(free_health, "load_health", lambda: {"mistral": {"cooldown_until": until}}):
            rc, out, err, run_dir = self._go("codestral-latest")
        self.assertEqual(rc, 75, out + err)
        self.assertIn("outcome=red reason=quota-paused", out)
        self.assertEqual(self._calls(), [])
        spec = json.loads((run_dir / "run.json").read_text())
        self.assertIn("cooldown", spec["reason_detail"])

    def test_expired_cooldown_runs(self):
        until = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        from agents_inc import free_health
        with mock.patch.object(free_health, "load_health", lambda: {"mistral": {"cooldown_until": until}}):
            rc, out, err, _ = self._go("codestral-latest")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(len(self._calls()), 1)

    def test_cap_ends_quota_paused_with_no_wrapper_call(self):
        from agents_inc import router
        with mock.patch.object(router, "_at_cap", lambda provider, now: provider == "gemini"):
            rc, out, err, run_dir = self._go("gemini-3.8-flash")
            self.assertEqual(rc, 75, out + err)
            self.assertIn("outcome=red reason=quota-paused", out)
            self.assertEqual(self._calls(), [])
            self.assertIn("cap", json.loads((run_dir / "run.json").read_text())["reason_detail"])
            rc, out, err, _ = self._go("codestral-latest")  # another provider is not capped
        self.assertEqual(rc, 0, out + err)

    def test_pre_launch_hold_unit(self):
        now = datetime(2026, 11, 9, tzinfo=timezone.utc)
        soon = (now + timedelta(minutes=5)).isoformat()
        self.assertIsNone(free_launch.pre_launch_hold("codestral-latest", now, {}))
        self.assertIn("cooldown", free_launch.pre_launch_hold("codestral-latest", now, {"mistral": {"cooldown_until": soon}}))
        self.assertIn("gemini-flash-lite", free_launch.pre_launch_hold(
            "gemini-flash-lite-latest", now, {"gemini-flash-lite": {"cooldown_until": soon}}))
        self.assertIsNone(free_launch.pre_launch_hold(
            "gemini-3.8-flash", now, {"gemini-flash-lite": {"cooldown_until": soon}}))  # flash-lite cooling does not stop flash


class ReachabilityTest(FreeBase):
    """Spec 037 FR-011: probe the provider host only when the caller is sandboxed; the probe is injectable."""

    def test_no_sandbox_no_probe(self):
        probe = mock.Mock(return_value=False)
        self.assertIsNone(free_launch.reachability_hold("codestral-latest", None, probe))
        probe.assert_not_called()

    def test_reachable_host_passes(self):
        self.assertIsNone(free_launch.reachability_hold("codestral-latest", "SANDBOX_RUNTIME", lambda host: host == "api.mistral.ai"))

    def test_unreachable_host_is_named(self):
        got = free_launch.reachability_hold("codestral-latest", "SANDBOX_RUNTIME", lambda host: False)
        self.assertIn("api.mistral.ai", got)

    def test_sandboxed_unreachable_run_is_blocked_exit_69_with_no_wrapper_call(self):
        with mock.patch.object(dispatch, "caller_sandbox", lambda env=None: "SANDBOX_RUNTIME is set"), \
                mock.patch.object(free_launch, "tcp_probe", lambda host, timeout=3.0: False):
            rc, out, err, run_dir = self._go("gemini-3.8-flash")
        self.assertEqual(rc, 69, out + err)
        self.assertIn("outcome=red reason=blocked", out)
        self.assertIn("generativelanguage.googleapis.com", json.loads((run_dir / "run.json").read_text())["reason_detail"])
        self.assertEqual(self._calls(), [])

    def test_sandboxed_reachable_run_proceeds(self):
        with mock.patch.object(dispatch, "caller_sandbox", lambda env=None: "SANDBOX_RUNTIME is set"), \
                mock.patch.object(free_launch, "tcp_probe", lambda host, timeout=3.0: True):
            rc, out, err, _ = self._go("gemini-3.8-flash")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(len(self._calls()), 1)


class CatalogRefusalTest(FreeBase):
    """Spec 037 FR-014 / T023: a catalog entry that lists the task as bad refuses before any call."""

    def test_bad_task_entry_is_refused_task(self):
        catalog = self.root / "models.json"
        catalog.write_text(json.dumps({"models": {"codestral-latest": {"tasks_bad": ["summarize"]}}}))
        with mock.patch.object(free_launch, "MODELS_PATH", catalog):
            rc, out, err, run_dir = self._go("codestral-latest")
            self.assertEqual(rc, 2, out + err)
            self.assertIn("refused refused-task", out)
            self.assertEqual(json.loads((run_dir / "run.json").read_text())["outcome"], "refused-task")
            self.assertEqual(self._calls(), [])
            rc, out, err, _ = self._go("codestral-latest", self._free_slots(TASK_KIND="extract", GATES=[REPORT_GATE]))
        self.assertEqual(rc, 0, out + err)  # only the listed task is refused

    def test_pre_checks_without_model_ignores_catalog(self):
        slots = {"TASK_KIND": "summarize", "CLASSIFICATION": "public (x)"}
        routing = {"optional_allowed_tasks": ["summarize"]}
        self.assertIsNone(free_launch.pre_checks(slots, None, routing))
        self.assertIsNone(free_launch.pre_checks(slots, None, routing, model="codestral-latest"))  # real catalog: not bad


class BrokerRejectionTest(FreeBase):
    """Spec 037 FR-013, SC-005: the broker never takes a free slug; slugs outside the map stay unsupported."""

    REJECTED = ("gemini-3.1-pro-preview", "mistral-large-latest", "openrouter/auto:free", "nvidia/nemotron-3-ultra-550b-a55b",
                "google/gemma-4-31b-it", "gemini-flash-lite", "codestral", "nvidia/unknown:free", "")

    def _manifest(self, models) -> Path:
        run_dir = self.root / "broker-run"
        run_dir.mkdir(exist_ok=True)
        (run_dir / "run.json").write_text(json.dumps({
            "schema_version": 1, "worker_models": models, "fan_out": {"width": 1, "total": 1, "depth": 1},
            "cwd": str(self.repo)}))
        return run_dir

    def test_manifest_with_free_worker_is_rejected(self):
        for slug in free_launch.FREE_MODELS:
            with self.subTest(slug=slug):
                with self.assertRaises(ValueError):
                    dispatch._load_run_manifest(self._manifest(["haiku", slug]))

    def test_manifest_with_normal_workers_loads(self):
        self.assertEqual(dispatch._load_run_manifest(self._manifest(["haiku", "luna"]))["worker_models"], ["haiku", "luna"])

    def test_validate_fields_rejects_free_slug(self):
        for slug in free_launch.FREE_MODELS:
            with self.subTest(slug=slug):
                req = {"schema_version": 1, "request_id": "r1", "model": slug, "effort": "low", "tier": "grunt",
                       "slots": {"TASK": "x"}}
                self.assertEqual(dispatch._validate_fields(req, {"worker_models": [slug]}, "r1"),
                                 (None, "model-not-allowed"))

    def test_rejected_slugs_are_not_free_and_not_supported(self):
        for slug in self.REJECTED:
            with self.subTest(slug=slug):
                self.assertFalse(free_launch.is_free(slug))
                self.assertIsNone(dispatch._kind(slug))

    def test_rejected_slug_dispatch_makes_no_wrapper_call(self):
        for slug in self.REJECTED[:4]:
            with self.subTest(slug=slug):
                rc, out, err, run_dir = self._go(slug)
                self.assertEqual(rc, 2, out + err)
                self.assertIn("not supported", out)
                self.assertIsNone(run_dir)
                self.assertEqual(self._calls(), [])


if __name__ == "__main__":
    unittest.main()
