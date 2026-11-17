"""Spec 042 phase 1: a verdict says what was measured. Every outcome and gate is passed, failed or not checked;
`unverified` exits 4; outside-scope changes end `unverified`, never red. Writes only to temp dirs."""
from __future__ import annotations
import contextlib
import io
import json
import shlex
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch
from tests.test_dispatch_grants import GOOD_REPORT, GrantsBase, PASS, setUpModule, tearDownModule  # noqa: F401

NO_GRILL = GOOD_REPORT.replace("GRILL: none. ", "")  # one format fault: the grill element is missing


class VerdictBase(GrantsBase):
    def _go(self, gates=None, report=GOOD_REPORT, rc=0, stderr="", during=None, **slots):
        """Dispatch with a fake delegate; `during(cwd)` runs while the delegate 'works'. Return (rc, stdout, spec)."""
        self.assertTrue(self.repo.is_dir())

        def fake(kind, model, effort, cwd, prompt, run_dir, permission_mode="acceptEdits", resume=None, **kw):
            if during:
                during(Path(cwd))
            return {"rc": rc, "stdout": report, "stderr": stderr, "argv": ["x"], "session_id": "sess-1"}
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            code, out, _ = self._main("--slots", str(self._slots(GATES=gates, **slots)), "--model", "sonnet",
                                      "--cwd", str(self.repo), "--run-dir", str(self.runs))
        return code, out, self._spec()

    def _vanishing_gate(self):
        """A gate program that exists at preflight and is deleted while the delegate runs."""
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        script = bin_dir / "gate.sh"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.chmod(0o755)
        self.assertTrue(script.is_file())
        return script, (lambda _cwd: script.unlink())

    @staticmethod
    def _stray(name="stray.txt"):
        return lambda cwd: (cwd / name).write_text("x\n", encoding="utf-8")


class ExitCodeTest(unittest.TestCase):
    def test_unverified_has_its_own_exit_code(self):
        self.assertEqual(dispatch.EXIT_UNVERIFIED, 4)
        codes = {dispatch.EXIT_OK, dispatch.EXIT_RED, dispatch.EXIT_USAGE, dispatch.EXIT_REFUSED, dispatch.EXIT_BLOCKED,
                 dispatch.EXIT_QUOTA, dispatch.EXIT_CANCELLED}
        self.assertNotIn(dispatch.EXIT_UNVERIFIED, codes)
        self.assertEqual(dispatch._exit_code("unverified", "no-gates", 0), 4)
        self.assertEqual(dispatch._exit_code("green", None, 0), 0)
        self.assertEqual(dispatch._exit_code("red", "gate-failed", 0), 1)

    def test_q_state_is_three_valued_for_every_outcome_word(self):
        table = {"green": "passed", "red": "failed", "snapshot-failed": "failed", "unverified": "not-checked",
                 "refused-capability": "not-checked", "refused-bash-allow": "not-checked",
                 "credential-seeking": "not-checked", "cancelled": "not-checked", "dry-run": "not-checked"}
        for word, state in table.items():
            with self.subTest(outcome=word):
                self.assertEqual(dispatch._outcome_state(word), state)

    def test_broker_status_maps_exit_four_to_unverified(self):
        self.assertEqual(dispatch._req_status(4, "unverified"), "unverified")
        self.assertEqual(dispatch.REQ_STATUS[4], "unverified")
        self.assertEqual(dispatch._req_status(0, "green"), "green")


class GateVerdictTest(VerdictBase):
    def test_a_gate_deleted_during_the_run_is_not_checked(self):
        script, during = self._vanishing_gate()
        code, out, spec = self._go([{"argv": [str(script)]}], during=during)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "gate-not-runnable"), out)
        row = spec["gate_results"][0]
        self.assertEqual((row["state"], row["rc"], row["argv"], row["reason"]),
                         ("not-checked", None, [str(script)], "gate-not-runnable"))
        self.assertEqual(spec["state"], "not-checked")
        self.assertIn(f"gate not-checked rc=none cmd={script}", out)

    def test_b_two_failing_gates_are_named_first_with_exit_codes(self):
        gates = [{"argv": ["true"]}, {"argv": ["false"]}, {"argv": ["sh", "-c", "exit 2"]}]
        code, out, spec = self._go(gates)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"), out)
        status = [ln for ln in out.splitlines() if ln.startswith("dispatch ")][0]
        self.assertIn(" gates=1/3 failed:false:rc=1,sh:rc=2 claims=not-checked out=", status)
        block = [ln for ln in out.splitlines() if ln.startswith("gate ")]
        self.assertEqual(block, ["gate failed rc=1 cmd=false last=",
                                 f"gate failed rc=2 cmd={shlex.join(['sh', '-c', 'exit 2'])} last=",
                                 "gate passed rc=0 cmd=true last="])
        self.assertEqual((self._run_dir() / "gates.txt").read_text(encoding="utf-8"), "\n".join(block) + "\n")
        self.assertNotIn("gate not-checked", out)  # the status line now also carries claims=not-checked
        self.assertNotIn("gate-missing", out)
        self.assertEqual([r["state"] for r in spec["gate_results"]], ["passed", "failed", "failed"])

    def test_g_format_fault_with_failing_gate_is_red_with_the_gate_reason(self):
        code, out, spec = self._go([{"argv": [sys.executable, "-c", "import sys;sys.exit(1)"]}], report=NO_GRILL)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"), out)

    def test_m_failed_gate_with_unusable_report_keeps_the_gate_reason(self):
        code, out, spec = self._go([{"argv": ["false"]}], report="done\nWORKERS SPAWNED: 0\n")
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"), out)
        self.assertEqual(spec["gate_results"][0]["state"], "failed")

    def test_h_every_gate_not_checked_is_never_green(self):
        script, during = self._vanishing_gate()
        code, out, spec = self._go([{"argv": [str(script)]}], during=during)
        self.assertEqual(spec["outcome"], "unverified", out)
        self.assertNotEqual(code, 0)

    def test_i_no_gates_is_unverified_with_its_own_reason(self):
        code, out, spec = self._go(None)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "no-gates"), out)
        self.tearDown(), self.setUp()
        failed, _, failed_spec = self._go([{"argv": ["false"]}])
        self.assertEqual((failed, failed_spec["reason"]), (1, "gate-failed"))
        self.assertNotEqual(failed_spec["reason"], spec["reason"])

    def test_j_gate_killed_by_timeout_is_failed_gate_timeout(self):
        gate = {"argv": [sys.executable, "-c", "import time;time.sleep(5)"], "timeout_s": 0.5}
        code, out, spec = self._go([gate])
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-timeout"), out)
        row = spec["gate_results"][0]
        self.assertEqual((row["state"], row["reason"]), ("failed", "gate-timeout"))

    def test_k_gate_exit_127_after_start_is_failed_with_last_line(self):
        gate = {"argv": [sys.executable, "-c", "import sys;print('tool: command not found');sys.exit(127)"]}
        code, out, spec = self._go([gate])
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"), out)
        row = spec["gate_results"][0]
        self.assertEqual((row["state"], row["rc"], row["last_line"]), ("failed", 127, "tool: command not found"))
        self.assertIn("last=tool: command not found", out)

    def test_refused_gate_precedes_other_gate_reasons(self):
        spec = {"cwd": str(self.repo), "gate_commands": [
            {"argv": ["false"], "cwd": ".", "timeout_s": 5, "expect_rc": 0},
            {"argv": ["git", "push"], "cwd": ".", "timeout_s": 5, "expect_rc": 0}]}
        results, reason = dispatch._run_gates(spec)
        self.assertEqual(reason, "gate-refused")
        self.assertEqual([r["state"] for r in results], ["failed", "failed"])
        self.assertEqual(results[1]["reason"], "gate-refused")


class ReportFaultTest(VerdictBase):
    def test_f_format_fault_with_passing_gates_is_green_advisory_on_its_own_line(self):
        code, out, spec = self._go([{"argv": PASS}], report=NO_GRILL)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (0, "green", "report-format-advisory"), out)
        lines = [ln for ln in out.splitlines() if ln.startswith("report-fault ")]
        self.assertEqual(len(lines), 1, out)
        self.assertIn("grill", lines[0])
        self.assertEqual(spec["gate_results"][0]["state"], "passed")

    def test_l_format_fault_with_unstartable_gate_is_unverified_not_red(self):
        script, during = self._vanishing_gate()
        code, out, spec = self._go([{"argv": [str(script)]}], report=NO_GRILL, during=during)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "gate-not-runnable"), out)


class EmptyReportTest(VerdictBase):
    """Operator ruling 2026-11-15: a missing or empty report is red; a malformed report is never red by itself."""

    def test_empty_report_without_gates_is_red(self):
        code, out, spec = self._go(None, report="")
        self.assertEqual((code, spec["outcome"]), (1, "red"), out)
        self.assertEqual(spec["reason"], "workers-spawned-missing")  # the existing launch-level reason covers a Claude or Codex run

    def test_empty_report_with_passing_gates_is_red(self):
        code, out, spec = self._go([{"argv": PASS}], report="  \n")
        self.assertEqual((code, spec["outcome"]), (1, "red"), out)

    def test_malformed_report_with_content_and_no_gates_is_unverified(self):
        code, out, spec = self._go(None, report=NO_GRILL)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "no-gates"), out)

    def test_malformed_report_with_passing_gates_is_green_with_report_fault_line(self):
        code, out, spec = self._go([{"argv": PASS}], report=NO_GRILL)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (0, "green", "report-format-advisory"), out)
        self.assertTrue(any(ln.startswith("report-fault ") for ln in out.splitlines()), out)


class ScopeVerdictTest(VerdictBase):
    SCOPE = "agents_inc/x.py"

    def test_c_outside_change_is_unverified_scope_foreign_change(self):
        code, out, spec = self._go([{"argv": PASS}], during=self._stray(), FILES_IN_SCOPE=self.SCOPE)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "scope-foreign-change"), out)
        self.assertEqual(spec["scope"]["foreign"], [{"path": "stray.txt", "attribution": "unknown"}])
        self.assertEqual(spec["scope"]["state"], "not-checked")
        self.assertEqual([r["state"] for r in spec["gate_results"]], ["passed"])  # gate results kept
        status = [ln for ln in out.splitlines() if ln.startswith("dispatch ")][0]
        self.assertIn(" gates=1/1 ", status)
        self.assertIn(" scope=not-checked:stray.txt attribution=unknown", status)
        self.assertNotIn("snapshot-not-clean", out)
        self.assertIn("gate passed rc=0 cmd=", out)

    def test_d_in_scope_change_passes_the_scope_check(self):
        def during(cwd):
            (cwd / "agents_inc").mkdir()
            (cwd / "agents_inc" / "x.py").write_text("x = 1\n", encoding="utf-8")
        code, out, spec = self._go([{"argv": PASS}], during=during, FILES_IN_SCOPE=self.SCOPE)
        self.assertEqual((code, spec["outcome"]), (0, "green"), out)
        self.assertEqual(spec["scope"]["foreign"], [])
        self.assertEqual(spec["scope"]["in_scope"], [{"path": "agents_inc/x.py", "attribution": "unknown"}])

    def test_n_write_during_a_gate_is_not_attributed_to_the_gate(self):
        gate = {"argv": [sys.executable, "-c", "open('neighbour.txt', 'w').write('x')"]}
        code, out, spec = self._go([gate], FILES_IN_SCOPE=self.SCOPE)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "scope-foreign-change"), out)
        self.assertEqual(spec["scope"]["foreign"], [{"path": "neighbour.txt", "attribution": "unknown"}])
        self.assertNotIn("gate-wrote", out)

    def test_failed_gate_beats_outside_change(self):
        code, out, spec = self._go([{"argv": ["false"]}], during=self._stray(), FILES_IN_SCOPE=self.SCOPE)
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"), out)
        self.assertEqual(spec["scope"]["foreign"], [{"path": "stray.txt", "attribution": "unknown"}])

    def test_o_real_verify_output_with_outside_lines_is_scope_foreign_change(self):
        spec, run_dir = self._direct_spec(allow=[])
        (self.repo / "stray.txt").write_text("x\n", encoding="utf-8")
        src, log, snap = dispatch._snapshot_verify(spec, run_dir)
        self.assertNotEqual(src, 0)
        self.assertIn("OUTSIDE stray.txt", log)
        self.assertEqual(snap, "CHANGED:stray.txt")
        got = dispatch._outcome(spec, "COMPLIANT", src, 0, None, None, True, snap=snap)
        self.assertEqual(got, ("unverified", "scope-foreign-change"))

    def test_p_empty_scope_makes_every_changed_file_outside(self):
        spec, run_dir = self._direct_spec(allow=[])
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        src, log, snap = dispatch._snapshot_verify(spec, run_dir)
        self.assertEqual((src != 0, snap), (True, "CHANGED:a.txt"), log)

    def test_old_verifier_without_the_flag_is_called_with_legacy_arguments(self):
        spec, run_dir = self._direct_spec(allow=[])
        old = self.root / "old-scripts"
        old.mkdir()
        (old / "pre_dispatch_snapshot.py").write_text(
            "import sys\na = sys.argv[1:]\n"
            "if a[0] != 'verify' or len(a) < 4 or a[2] != '--repo':\n    print('usage'); sys.exit(2)\n"
            "print('CHANGED stray.txt'); sys.exit(1)\n", encoding="utf-8")
        spec = {**spec, "scripts_source": "checkout", "scripts_dir": str(old)}
        with mock.patch.object(dispatch, "_check_pinned"):
            src, log, snap = dispatch._snapshot_verify(spec, run_dir)
        self.assertEqual((src, snap), (1, "CHANGED:stray.txt"), log)

    def test_snapshot_state_in_the_scope_record(self):
        rec = lambda snap: dispatch._scope_record(self.root / "none.txt", snap)["state"]  # noqa: E731
        self.assertEqual(rec("clean"), "passed")
        self.assertEqual(rec(dispatch.SNAPSHOT_SKIPPED), "not-checked")
        self.assertEqual(rec("TAMPERED"), "failed")
        self.assertEqual(rec("ERROR:rc=2"), "failed")
        self.assertEqual(rec("CHANGED:a.txt"), "not-checked")

    def test_mkdtemp_failure_is_gate_not_runnable(self):
        with mock.patch.object(dispatch, "sandbox_available", return_value=True), \
                mock.patch.object(dispatch.tempfile, "mkdtemp", side_effect=OSError("disk full")):
            code, out, spec = self._go([{"argv": PASS}])
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "gate-not-runnable"), out)
        self.assertEqual(spec["gate_results"][0]["state"], "not-checked")

    def test_gates_token_orders_failed_before_not_checked(self):
        rows = [{"argv": ["a"], "state": "not-checked", "rc": None}, {"argv": ["b"], "state": "failed", "rc": 1},
                {"argv": ["c"], "state": "passed", "rc": 0}]
        self.assertEqual(dispatch._gates_token({"gate_results": rows}), " gates=1/3 failed:b:rc=1 not-checked:a:rc=none")

    def test_refused_non_git_run_json_carries_state(self):
        spec = {"run_id": "r1", "model": "haiku"}
        run_dir = self.root / "refused"
        run_dir.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            dispatch._refuse_non_git(spec, run_dir, self.root / "lint.txt", self.repo, "x", "msg")
        self.assertEqual(json.loads((run_dir / "run.json").read_text())["state"], "not-checked")

    def _direct_spec(self, allow):
        snap_path = self.root / "snap.json"
        run_dir = self.root / "direct-run"
        run_dir.mkdir()
        res = subprocess.run([sys.executable, str(dispatch.SCRIPTS / "pre_dispatch_snapshot.py"), "capture",
                              str(snap_path)], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return {"cwd": str(self.repo), "snapshot": str(snap_path), "gates": {"allow": allow}}, run_dir


class QuotaRegressionTest(VerdictBase):
    def test_e_usage_limit_with_no_report_is_quota_paused_only(self):
        code, out, spec = self._go([{"argv": PASS}], report="", rc=1, stderr="Claude usage limit reached")
        self.assertEqual((code, spec["outcome"], spec["reason"]), (75, "red", "quota-paused"), out)


class RunStateFieldTest(VerdictBase):
    def test_q_run_json_carries_state_for_each_outcome(self):
        code, _, spec = self._go([{"argv": PASS}])
        self.assertEqual((code, spec["outcome"], spec["state"]), (0, "green", "passed"))
        self.tearDown(), self.setUp()
        _, _, spec = self._go([{"argv": ["false"]}])
        self.assertEqual((spec["outcome"], spec["state"]), ("red", "failed"))
        self.tearDown(), self.setUp()
        _, _, spec = self._go(None)
        self.assertEqual((spec["outcome"], spec["state"]), ("unverified", "not-checked"))
        self.tearDown(), self.setUp()
        _, _, spec = self._go([{"argv": PASS}], BASH_ALLOW=["git push"])
        self.assertEqual((spec["outcome"], spec["state"]), ("refused-bash-allow", "not-checked"))


def _claims(files="none", gates="none", tests=None, stopped="none"):
    return (GOOD_REPORT + "```claims\nfiles_changed: " + files + "\ngates: " + gates + "\n"
            + (f"tests: {tests}\n" if tests else "") + "stopped: " + stopped + "\n```\n")


GATE3 = [{"argv": [sys.executable, "-c", "print('Ran 3 tests')"]}]


class ClaimCheckTest(VerdictBase):
    """Spec 042 phase 2 (T024, T025): the claim check warns and never changes the outcome; every return writes a row."""

    def _ledger(self):
        path = self.root / ".local/state/agents-inc/host-ledger/.workerbees/ledger.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.is_file() else []

    def test_gate_ids_are_dispatcher_assigned_in_slots_order(self):
        code, out, spec = self._go([{"argv": ["true"]}, {"argv": ["true"]}])
        self.assertEqual([r["id"] for r in spec["gate_results"]], ["g1", "g2"])

    def test_supported_claims_list_nothing(self):
        code, out, spec = self._go(GATE3, report=_claims("out.txt", "g1=0", "g1=3"), during=self._stray("out.txt"))
        self.assertEqual(spec["claims"]["unsupported"], 0, out)
        self.assertIn(" claims=checked:0 unsupported", out)
        self.assertNotIn("\nunsupported ", out)

    def test_unsupported_claims_are_printed_one_line_each_and_never_change_the_outcome(self):
        base_code, _, base = self._go(GATE3, report=_claims("none", "g1=0"))
        self.tearDown(), self.setUp()
        code, out, spec = self._go(GATE3, report=_claims("out.txt", "g1=0", "g1=99"))
        self.assertEqual((code, spec["outcome"], spec["reason"]), (base_code, base["outcome"], base["reason"]))
        self.assertIn(" claims=checked:2 unsupported", out)
        self.assertIn("unsupported file-changed claimed=out.txt observed=unchanged", out)
        self.assertIn("unsupported test-count claimed=g1=99 observed=3", out)
        claims = json.loads((self._run_dir() / "claims.json").read_text(encoding="utf-8"))
        self.assertEqual(claims["unsupported"], 2)
        self.assertEqual(spec["claims"]["items"], claims["items"])

    def test_omitted_gate_is_reported_and_the_failed_gate_still_decides(self):
        code, out, spec = self._go([{"argv": ["true"]}, {"argv": ["false"]}], report=_claims("none", "g1=0"))
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"), out)
        self.assertEqual(spec["claims"]["omitted"], ["g2"])
        self.assertIn(" omitted=g2", out)

    def test_zero_test_gate_claim_is_weak(self):
        gate = [{"argv": [sys.executable, "-c", "print('Ran 0 tests')"]}]
        code, out, spec = self._go(gate, report=_claims("none", "g1=0", "g1=0"))
        self.assertEqual(spec["claims"]["weak"], ["g1"])
        self.assertIn(" weak=g1", out)

    def test_missing_block_is_not_checked_never_passed(self):
        code, out, spec = self._go(GATE3)
        self.assertEqual(spec["claims"]["state"], "not-checked")
        self.assertIn(" claims=not-checked", out)
        self.assertNotIn("claims=checked", out)
        self.assertEqual((code, spec["outcome"]), (0, "green"))  # a missing block never turns a gated green red

    def test_two_blocks_are_unsupported_with_the_reason(self):
        code, out, spec = self._go(GATE3, report=_claims("none", "g1=0") + "```claims\nfiles_changed: none\ngates: g1=0\nstopped: none\n```\n")
        self.assertEqual(spec["claims"]["items"][0]["reason"], "multiple-claims-blocks")
        self.assertIn("unsupported claims-block claimed=2 blocks observed=1 block allowed", out)

    def test_declared_stop_is_unverified_delegate_stopped_with_gate_results_kept(self):
        code, out, spec = self._go(GATE3, report=_claims("none", "g1=0", stopped="s1"))
        self.assertEqual((code, spec["outcome"], spec["reason"]), (4, "unverified", "delegate-stopped"), out)
        self.assertEqual(spec["gate_results"][0]["state"], "passed")
        self.assertEqual(spec["claims"]["unsupported"], 0)

    def test_declared_stop_with_format_fault_is_still_delegate_stopped(self):
        report = NO_GRILL + "```claims\nfiles_changed: none\ngates: g1=0\nstopped: s1\n```\n"
        code, out, spec = self._go(GATE3, report=report)
        self.assertEqual((code, spec["reason"]), (4, "delegate-stopped"), out)

    def test_failed_gate_outranks_a_declared_stop(self):
        code, out, spec = self._go([{"argv": ["false"]}], report=_claims("none", "g1=1", stopped="s1"))
        self.assertEqual((code, spec["outcome"], spec["reason"]), (1, "red", "gate-failed"), out)

    def test_invented_stop_is_unsupported_but_still_a_stop(self):
        code, out, spec = self._go(GATE3, report=_claims("none", "g1=0", stopped="because I felt like it"))
        self.assertEqual(spec["reason"], "delegate-stopped")
        self.assertIn("unsupported stopped claimed=because I felt like it", out)

    def test_return_row_carries_the_new_fields_and_links_to_its_dispatched_row(self):
        self._go(GATE3, report=_claims("out.txt", "g1=0"))
        rows = self._ledger()
        dispatched, returned = rows[0], rows[-1]
        self.assertEqual(dispatched["status"], "dispatched")
        self.assertEqual(returned["dispatch_row_id"], dispatched["id"])
        self.assertEqual((returned["exit_code"], returned["state"]), (0, "passed"))
        self.assertEqual(returned["gate_results"][0]["id"], "g1")
        self.assertEqual(returned["scope"]["state"], "passed")
        self.assertEqual(returned["claims"]["items"], [{"kind": "file-changed", "claimed": "out.txt", "observed": "unchanged"}])

    def test_every_outcome_writes_a_linked_return_row_with_state(self):
        with mock.patch.object(dispatch, "lint_prompt", return_value=([12], "")):
            self._main("--slots", str(self._slots()), "--model", "sonnet", "--cwd", str(self.repo), "--run-dir", str(self.runs))
        self._main("--slots", str(self._slots()), "--model", "sonnet", "--cwd", str(self.repo), "--run-dir", str(self.runs), "--dry-run")
        rows = self._ledger()
        ids = {r["id"] for r in rows if r["status"] == "dispatched"}
        returned = [r for r in rows if r["status"] != "dispatched"]
        self.assertEqual([r["status"] for r in returned], ["refused-lint", "dry-run"])
        for r in returned:
            self.assertIn(r["dispatch_row_id"], ids)
            self.assertEqual(r["state"], "not-checked")
        self.assertEqual(returned[0]["exit_code"], 3)

    def test_claim_check_is_pinned_with_the_other_scripts(self):
        self.assertIn("check_claims.py", dispatch.PINNED_SCRIPTS)


if __name__ == "__main__":
    unittest.main()
