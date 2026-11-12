import io
import os
import stat
import tempfile
import unittest
from pathlib import Path
import json
import contextlib
from unittest import mock

from agents_inc.install.receipt import InstallReceipt
from agents_inc.install.runtime import MODEL_ALIASES, build_codex_argv, resolve_executable, run_codex


class RuntimeTest(unittest.TestCase):
    def test_aliases_and_isolated_argv(self):
        tiers = json.loads((Path(__file__).parents[1] / "agents_inc/routing.json").read_text())["tiers"]
        persona_tier = {"astra": "executive", "sol": "orchestrator", "terra": "workhorse", "luna": "grunt"}
        self.assertEqual(MODEL_ALIASES, {alias: tiers[tier]["codex"] for alias, tier in persona_tier.items()})
        argv = build_codex_argv(Path("/opt/Codex CLI/codex"), "astra", "medium", Path("/work here"), {"gpt-6-astra": ["medium"]})
        self.assertEqual(argv[:4], ["/opt/Codex CLI/codex", "exec", "-m", "gpt-6-astra"])
        self.assertIn("read-only", argv)
        self.assertIn('shell_environment_policy.inherit="none"', argv)
        self.assertIn('web_search="disabled"', argv)
        self.assertIn("features.shell_tool=false", argv)
        self.assertEqual(argv[-1], "-")

    def test_resolution_needs_absolute_executable(self):
        with tempfile.TemporaryDirectory() as raw:
            exe = Path(raw) / "bin" / "codex"
            exe.parent.mkdir(); exe.write_text("#!/bin/sh\n")
            exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
            self.assertEqual(resolve_executable("codex", str(exe.parent)), exe.resolve())
        with self.assertRaises(FileNotFoundError):
            resolve_executable("codex", "")

    def _fake(self, path):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text("#!/bin/sh\n"); path.chmod(0o755)
        return path

    def test_resolution_skips_temp_dir_and_shim_entries(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw); real = self._fake(tmp / "real" / "codex")
            patch = mock.patch("agents_inc.install.runtime.tempfile.gettempdir", return_value=str(tmp / "t"))
            self._fake(tmp / "t" / "codex-dir" / "codex"); self._fake(tmp / "x-shims" / "abc" / "codex")
            with patch:
                self.assertEqual(resolve_executable("codex", f"{tmp / 't' / 'codex-dir'}:{tmp / 'real'}"), real.resolve())
                self.assertEqual(resolve_executable("codex", f"{tmp / 'x-shims' / 'abc'}:{tmp / 'real'}"), real.resolve())
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    got = resolve_executable("codex", str(tmp / "x-shims" / "abc"))
                self.assertEqual(got, (tmp / "x-shims" / "abc" / "codex").resolve())
                self.assertIn("WARN", err.getvalue())

    def test_unsupported_effort_fails_before_execution(self):
        with self.assertRaises(ValueError):
            build_codex_argv(Path("/x/codex"), "luna", "ultra", Path("/tmp"), {"gpt-5.6-luna": ["low"]})

    def test_bundled_catalog_declares_supported_efforts_for_every_alias(self):
        models = json.loads((Path(__file__).parents[1] / "agents_inc/models.json").read_text())["models"]
        for slug in MODEL_ALIASES.values():
            self.assertIn("supported_efforts", models[slug])
            self.assertIn("medium", models[slug]["supported_efforts"])

    def test_run_codex_quota_error_returns_75(self):
        """Quota error in stderr returns 75 and reports to free_health."""
        with tempfile.TemporaryDirectory() as raw:
            # Create fake codex executable
            fake_codex = Path(raw) / "codex"
            fake_codex.write_text("#!/bin/sh\necho 'ERROR: You have hit your usage limit. Upgrade or try again at 11:26 PM.' >&2\nexit 0\n")
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

            # Create receipt
            receipt = InstallReceipt(
                release_hash="a" * 64,
                python_path=Path("/usr/bin/python3"),
                codex_path=fake_codex
            )

            # Mock free_health.report and capture output
            with mock.patch("agents_inc.free_health.report") as mock_report:
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                        tf.write("test")
                        tf.flush()
                        stdin_path = tf.name
                    try:
                        with open(stdin_path) as stdin_file:
                            ret = run_codex("astra", "medium", Path("/tmp"), stdin_file, receipt, {"gpt-6-astra": ["medium"]})
                    finally:
                        os.unlink(stdin_path)

                self.assertEqual(ret, 75)
                stderr_output = stderr_capture.getvalue()
                self.assertIn("retry at 11:26 PM", stderr_output)
                self.assertIn("usage or rate limit", stderr_output)
                mock_report.assert_called_once()
                call_args = mock_report.call_args
                self.assertEqual(call_args[0], ("codex", "gpt-6-astra", "rate_limited"))

    def test_run_codex_empty_output_returns_1(self):
        """Empty stdout with exit 0 returns 1."""
        with tempfile.TemporaryDirectory() as raw:
            # Create fake codex executable that prints nothing
            fake_codex = Path(raw) / "codex"
            fake_codex.write_text("#!/bin/sh\nexit 0\n")
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

            # Create receipt
            receipt = InstallReceipt(
                release_hash="a" * 64,
                python_path=Path("/usr/bin/python3"),
                codex_path=fake_codex
            )

            # Mock free_health.report (should not be called)
            with mock.patch("agents_inc.free_health.report") as mock_report:
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                        tf.write("test")
                        tf.flush()
                        stdin_path = tf.name
                    try:
                        with open(stdin_path) as stdin_file:
                            ret = run_codex("astra", "medium", Path("/tmp"), stdin_file, receipt, {"gpt-6-astra": ["medium"]})
                    finally:
                        os.unlink(stdin_path)

                self.assertEqual(ret, 1)
                stderr_output = stderr_capture.getvalue()
                self.assertIn("empty reply", stderr_output)
                mock_report.assert_not_called()

    def test_run_codex_ok_returns_0(self):
        """Normal output with exit 0 returns 0."""
        with tempfile.TemporaryDirectory() as raw:
            # Create fake codex executable that prints to stdout
            fake_codex = Path(raw) / "codex"
            fake_codex.write_text("#!/bin/sh\necho 'REVIEW-OK'\nexit 0\n")
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

            # Create receipt
            receipt = InstallReceipt(
                release_hash="a" * 64,
                python_path=Path("/usr/bin/python3"),
                codex_path=fake_codex
            )

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                    tf.write("test")
                    tf.flush()
                    stdin_path = tf.name
                try:
                    with open(stdin_path) as stdin_file:
                        ret = run_codex("astra", "medium", Path("/tmp"), stdin_file, receipt, {"gpt-6-astra": ["medium"]})
                finally:
                    os.unlink(stdin_path)

            self.assertEqual(ret, 0)
            stdout_output = stdout_capture.getvalue()
            self.assertIn("REVIEW-OK", stdout_output)

    def test_run_codex_passthrough_exit_code(self):
        """Non-zero exit code is returned as-is."""
        with tempfile.TemporaryDirectory() as raw:
            # Create fake codex executable that exits with 3
            fake_codex = Path(raw) / "codex"
            fake_codex.write_text("#!/bin/sh\necho 'x'\nexit 3\n")
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

            # Create receipt
            receipt = InstallReceipt(
                release_hash="a" * 64,
                python_path=Path("/usr/bin/python3"),
                codex_path=fake_codex
            )

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                    tf.write("test")
                    tf.flush()
                    stdin_path = tf.name
                try:
                    with open(stdin_path) as stdin_file:
                        ret = run_codex("astra", "medium", Path("/tmp"), stdin_file, receipt, {"gpt-6-astra": ["medium"]})
                finally:
                    os.unlink(stdin_path)

            self.assertEqual(ret, 3)
            stdout_output = stdout_capture.getvalue()
            self.assertIn("x", stdout_output)

    def test_run_codex_no_false_positive_on_non_error_lines(self):
        """Strings like '429' and 'rate limit' outside ERROR lines do not trigger quota detection."""
        with tempfile.TemporaryDirectory() as raw:
            # Create fake codex executable that mentions "429" and "rate limit" in non-ERROR output
            fake_codex = Path(raw) / "codex"
            fake_codex.write_text("#!/bin/sh\necho 'user: please review this rate limit code; status 429' >&2\necho 'tokens used 14,290' >&2\necho 'REVIEW-OK'\nexit 0\n")
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

            # Create receipt
            receipt = InstallReceipt(
                release_hash="a" * 64,
                python_path=Path("/usr/bin/python3"),
                codex_path=fake_codex
            )

            # Ensure free_health.report is not called
            with mock.patch("agents_inc.free_health.report") as mock_report:
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                        tf.write("test")
                        tf.flush()
                        stdin_path = tf.name
                    try:
                        with open(stdin_path) as stdin_file:
                            ret = run_codex("astra", "medium", Path("/tmp"), stdin_file, receipt, {"gpt-6-astra": ["medium"]})
                    finally:
                        os.unlink(stdin_path)

                self.assertEqual(ret, 0)
                stdout_output = stdout_capture.getvalue()
                self.assertIn("REVIEW-OK", stdout_output)
                mock_report.assert_not_called()


FLAG = "include_collaboration_mode_instructions=false"


class ToolsOnCollaborationFlagTest(unittest.TestCase):
    """#160: every tools-on Codex rung turns off collaboration-mode instructions, once, resume included."""

    def _argv(self, model, **kw):
        efforts = {slug: ["medium"] for slug in MODEL_ALIASES.values()}
        return build_codex_argv(Path("/x/codex"), model, "medium", Path("/work"), efforts, **kw)

    def test_flag_once_on_every_tools_on_rung(self):
        for model in ("luna", "sol", "terra", "astra"):
            argv = self._argv(model, tools=True)
            self.assertEqual(argv.count(FLAG), 1, model)
            self.assertEqual(argv[argv.index(FLAG) - 1], "-c", model)

    def test_flag_absent_when_tools_off(self):
        self.assertEqual(self._argv("luna").count(FLAG), 0)

    def test_resume_inherits_flag_once(self):
        from agents_inc.install.runtime import build_codex_resume_argv
        efforts = {slug: ["medium"] for slug in MODEL_ALIASES.values()}
        argv = build_codex_resume_argv(Path("/x/codex"), "t-1", "hi", "luna", "medium", Path("/work"), efforts, tools=True)
        self.assertEqual(argv.count(FLAG), 1)


class EmptyReplyReasonTest(unittest.TestCase):
    def _run(self, rollout_lines, tid="thr-1"):
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            raw = Path(raw)
            fake = raw / "codex"
            event = json.dumps({"type": "thread.started", "thread_id": tid}) if tid else "{}"
            fake.write_text(f"#!/bin/sh\necho '{event}'\nexit 0\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            rollout = raw / "rollout.jsonl"
            rollout.write_text("".join(json.dumps(l) + "\n" for l in rollout_lines))
            receipt = InstallReceipt(release_hash="a" * 64, python_path=Path("/usr/bin/python3"), codex_path=fake)
            err = io.StringIO()
            prompt = raw / "p"; prompt.write_text("x")
            with mock.patch.object(runtime, "thread_rollout", return_value=rollout), \
                 contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), open(prompt) as stdin:
                rc = run_codex("luna", "medium", raw, stdin, receipt, {"gpt-6-luna": ["medium"]}, tools=True, thread_out={})
            return rc, err.getvalue()

    def test_red_line_counts_request_user_input_calls(self):
        call = {"payload": {"type": "function_call", "name": "request_user_input", "arguments": "{}"}}
        rc, err = self._run([call, call, call])
        self.assertEqual(rc, 1)
        self.assertIn("returned an empty reply (request_user_input calls: 3)", err)

    def _run_failing(self, script):
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            raw = Path(raw)
            fake = raw / "codex"; fake.write_text(script); fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            receipt = InstallReceipt(release_hash="a" * 64, python_path=Path("/usr/bin/python3"), codex_path=fake)
            err, prompt = io.StringIO(), raw / "p"
            prompt.write_text("edit the file")
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), open(prompt) as stdin:
                rc = run_codex("luna", "medium", raw, stdin, receipt, {"gpt-6-luna": ["medium"]}, tools=True)
            return rc, err.getvalue()

    def test_160_unavailable_ask_names_cause(self):
        line = "ERROR codex_core::tools::router: error=request_user_input is unavailable in Default mode"
        rc, err = self._run_failing(f"#!/bin/sh\ncat >/dev/null\necho '{line}' >&2\necho '{line}' >&2\nexit 1\n")
        self.assertEqual(rc, 1)
        self.assertIn("returned an empty reply (request_user_input calls: 2); cause: the model asked the user", err)

    def test_160_other_failure_keeps_plain_exit(self):
        rc, err = self._run_failing("#!/bin/sh\ncat >/dev/null\necho boom >&2\nexit 3\n")
        self.assertEqual(rc, 3)
        self.assertNotIn("empty reply", err)

    def test_160_tools_prompt_says_no_questions(self):
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            raw = Path(raw); seen = raw / "seen"
            fake = raw / "codex"; fake.write_text(f"#!/bin/sh\ncat > {seen}\necho ok\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            receipt = InstallReceipt(release_hash="a" * 64, python_path=Path("/usr/bin/python3"), codex_path=fake)
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                run_codex("luna", "medium", raw, io.StringIO("do it"), receipt, {"gpt-6-luna": ["medium"]}, tools=True)
            text = seen.read_text()
        self.assertTrue(text.startswith(runtime.NO_ASK_PREAMBLE)); self.assertTrue(text.endswith("do it"))

    def _run_host_tools(self, events):
        """A host-tools thread run whose fake Codex prints these --json events and writes no final message."""
        from agents_inc.install import runtime
        with tempfile.TemporaryDirectory() as raw:
            raw = Path(raw)
            fake = raw / "codex"
            lines = "".join(f"echo '{json.dumps(e)}'\n" for e in events)
            fake.write_text(f"#!/bin/sh\ncat >/dev/null\n{lines}exit 0\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            catalog = raw / "catalog.json"; catalog.write_text("{}")
            receipt = InstallReceipt(release_hash="a" * 64, python_path=Path("/usr/bin/python3"), codex_path=fake)
            err = io.StringIO()
            with mock.patch.object(runtime, "require_host_tools_catalog", return_value=catalog), \
                 mock.patch.object(runtime, "lead_codex_home", return_value=None), \
                 mock.patch.object(runtime, "build_codex_argv", return_value=[str(fake)]), \
                 mock.patch.object(runtime, "thread_rollout", return_value=None), \
                 contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = run_codex("luna", "low", raw, io.StringIO("go"), receipt, {"gpt-6-luna": ["low"]}, no_tools=True,
                               host_tools=True, thread_out={})
            return rc, err.getvalue()

    def test_host_tools_empty_final_message_is_not_a_failure_when_luna_spoke(self):
        said = {"type": "item.completed", "item": {"type": "agent_message", "text": "{\"say\":\"\",\"tools\":[]}"}}
        rc, err = self._run_host_tools([{"type": "thread.started", "thread_id": "t1"}, said])
        self.assertEqual(rc, 0, err)
        self.assertIn("left its final message empty", err)
        self.assertNotIn("empty reply", err)

    def test_host_tools_empty_final_message_with_no_message_still_fails(self):
        blank = {"type": "item.completed", "item": {"type": "agent_message", "text": " "}}
        rc, err = self._run_host_tools([{"type": "thread.started", "thread_id": "t1"}, blank])
        self.assertEqual(rc, 1)
        self.assertIn("returned an empty reply", err)

    def test_red_line_says_unknown_without_thread_id(self):
        rc, err = self._run([], tid=None)
        self.assertEqual(rc, 1)
        self.assertIn("returned an empty reply (request_user_input calls: unknown)", err)
