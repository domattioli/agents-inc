"""Spec 042 phases 1 and 2: regression tests for the sol cross-vendor review (2026-11-16), one group per finding F1..F12.
Inputs follow the reviewer's probes (.scratch/review042/phase1-2.md)."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import dispatch, free_launch
from tests.test_dispatch_grants import GOOD_REPORT, PASS, setUpModule, tearDownModule  # noqa: F401
from tests.test_dispatch_verdicts import VerdictBase, _claims

CC = dispatch._load("check_claims")
SCRIPT = Path(__file__).resolve().parents[1] / "skills/workerbee/scripts/pre_dispatch_snapshot.py"
BLOCK = "```claims\nfiles_changed: {f}\ngates: {g}\nstopped: {s}\n```\n"


def _block(f="none", g="none", s="none", extra=""):
    return "```claims\n" + f"files_changed: {f}\ngates: {g}\n" + extra + f"stopped: {s}\n```\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo, check=True, capture_output=True)


class SnapBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        (self.repo / ".gitignore").write_text(".scratch/\n", encoding="utf-8")
        (self.repo / "a.py").write_text("v1\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "init")
        self.snap = self.root / "snap.json"

    def tearDown(self):
        os.chmod(self.repo / "a.py", 0o644) if (self.repo / "a.py").exists() else None
        self.tmp.cleanup()

    def _run(self, *args: str):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo, capture_output=True, text=True)


class F1ClaimsTextIsNotControlTest(VerdictBase):
    def test_unknown_key_in_claims_block_is_not_a_workers_spawned_line(self):
        text = "WORKERS SPAWNED: 0\n" + _block(extra="WORKERS SPAWNED: 1\n")
        self.assertEqual(dispatch.parse_workers_spawned(text), 0)

    def test_claims_block_cannot_turn_a_passing_run_red(self):
        report = GOOD_REPORT + _block(g="g1=0", extra="WORKERS SPAWNED: 1\n")
        code, out, spec = self._go([{"argv": PASS}], report=report)
        self.assertNotEqual(spec["reason"], "fan-out-over-total", out)
        self.assertEqual((code, spec["outcome"]), (0, "green"), out)

    def test_report_lint_never_reads_inside_the_fence(self):
        stripped = dispatch.strip_claims_fences("a\n```claims\nVERDICT: x\n```\nb\n")
        self.assertEqual(stripped.split(), ["a", "b"])


class F2FinalVerifyIsTheEvidenceTest(VerdictBase):
    def test_file_created_by_a_gate_is_in_scope_and_unclaimed(self):
        gate = {"argv": [sys.executable, "-c", "open('out.txt', 'w').write('x')"]}
        code, out, spec = self._go([gate], report=GOOD_REPORT + _block(g="g1=0"), FILES_IN_SCOPE="out.txt")
        self.assertEqual([f["path"] for f in spec["scope"]["in_scope"]], ["out.txt"], out)
        self.assertEqual(spec["claims"]["unclaimed"], ["out.txt"])

    def test_file_restored_by_a_gate_does_not_support_a_change_claim(self):
        gate = {"argv": [sys.executable, "-c", "import os; os.remove('out.txt')"]}
        code, out, spec = self._go([gate], report=GOOD_REPORT + _block(f="out.txt", g="g1=0"), during=self._stray("out.txt"),
                                   FILES_IN_SCOPE="out.txt")
        self.assertEqual(spec["scope"]["in_scope"], [], out)
        self.assertEqual([i["kind"] for i in spec["claims"]["items"]], ["file-changed"])


class F3UnreadableTest(SnapBase):
    def _prepare(self):
        (self.repo / "a.py").write_text("v2\n", encoding="utf-8")  # dirty before launch: hashed
        self.assertEqual(self._run("capture", str(self.snap)).returncode, 0)
        os.chmod(self.repo / "a.py", 0)

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_unreadable_allowed_file_is_not_a_change(self):
        self._prepare()
        res = self._run("verify", str(self.snap), "--scope-aware", "--allow", "a.py")
        self.assertIn("UNREADABLE a.py", res.stdout.splitlines())
        self.assertNotIn("CHANGED a.py", res.stdout.splitlines())
        self.assertEqual(res.returncode, 0)

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_legacy_default_output_is_unchanged(self):
        self._prepare()
        res = self._run("verify", str(self.snap), "--allow", "a.py")
        self.assertEqual((res.stdout, res.returncode), ("UNCHANGED outside allowed paths\n", 0))

    def test_file_claim_on_an_unreadable_path_is_not_checked_never_unsupported(self):
        got = CC.check(_block(f="a.py", g="none"), {"changed": [], "unreadable": ["a.py"], "gate_results": []})
        self.assertEqual((got["state"], got["unsupported"], got["items"]), ("checked", 0, []))
        self.assertEqual([n["claimed"] for n in got["not_checked"]], ["a.py"])

    def test_scope_state_is_not_passed_with_an_unreadable_allowed_path(self):
        ev = {"in_scope": [], "outside": [], "unreadable": ["a.py"], "unbaselined": []}
        self.assertEqual(dispatch._scope_record(ev, "clean")["state"], "not-checked")


class F4EveryAttemptedRunEndsWithAReturnRowTest(VerdictBase):
    def _ledger(self):
        path = self.root / ".local/state/agents-inc/host-ledger/.workerbees/ledger.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.is_file() else []

    def test_cancel_during_render_writes_a_complete_return_row(self):
        with mock.patch.object(dispatch, "render", side_effect=dispatch.Cancelled("SIGTERM")):
            code, out, _ = self._main("--slots", str(self._slots()), "--model", "sonnet", "--cwd", str(self.repo),
                                      "--run-dir", str(self.runs))
        rows = self._ledger()
        self.assertEqual(code, 130, out)
        self.assertEqual([r["status"] for r in rows], ["dispatched", "cancelled"])
        self.assertEqual((rows[1]["exit_code"], rows[1]["state"], rows[1]["dispatch_row_id"]), (130, "not-checked", rows[0]["id"]))

    def test_pin_failure_writes_both_rows(self):
        with mock.patch.object(dispatch, "scripts_dir", return_value=(dispatch.SCRIPTS, "checkout")), \
                mock.patch.object(dispatch, "_pin_scripts", side_effect=OSError("read-only")):
            code, out, _ = self._main("--slots", str(self._slots()), "--model", "sonnet", "--cwd", str(self.repo),
                                      "--run-dir", str(self.runs))
        rows = self._ledger()
        self.assertEqual(code, 1, out)
        self.assertEqual([r["status"] for r in rows], ["dispatched", "red"])
        self.assertEqual(rows[1]["exit_code"], 1)


class F5IgnoredScopeTest(SnapBase):
    def _ignored(self, text):
        (self.repo / ".scratch").mkdir(exist_ok=True)
        (self.repo / ".scratch/out.md").write_text(text, encoding="utf-8")

    def test_changed_ignored_deliverable_is_measured(self):
        self._ignored("v1\n")
        self.assertEqual(self._run("capture", str(self.snap), "--allow", ".scratch/out.md").returncode, 0)
        self._ignored("v2\n")
        res = self._run("verify", str(self.snap), "--scope-aware", "--allow", ".scratch/out.md")
        self.assertIn("CHANGED .scratch/out.md", res.stdout.splitlines())
        self._ignored("v1\n")
        res = self._run("verify", str(self.snap), "--scope-aware", "--allow", ".scratch/out.md")
        self.assertNotIn("CHANGED .scratch/out.md", res.stdout.splitlines())

    def test_new_ignored_deliverable_is_measured(self):
        self.assertEqual(self._run("capture", str(self.snap), "--allow", ".scratch/out.md").returncode, 0)
        self._ignored("v1\n")
        res = self._run("verify", str(self.snap), "--scope-aware", "--allow", ".scratch/out.md")
        self.assertIn("CHANGED .scratch/out.md", res.stdout.splitlines())

    def test_declared_ignored_path_without_a_baseline_is_named(self):
        self._ignored("v1\n")
        self.assertEqual(self._run("capture", str(self.snap)).returncode, 0)
        res = self._run("verify", str(self.snap), "--scope-aware", "--allow", ".scratch/out.md")
        self.assertIn("UNBASELINED .scratch/out.md", res.stdout.splitlines())

    def test_claim_on_an_unbaselined_path_is_not_checked(self):
        got = CC.check(_block(f="x.md"), {"changed": [], "unbaselined": ["x.md"], "gate_results": []})
        self.assertEqual((got["unsupported"], [n["claimed"] for n in got["not_checked"]]), (0, ["x.md"]))


class F5DispatchIgnoredTest(VerdictBase):
    def test_ignored_deliverable_written_by_the_delegate_supports_the_claim(self):
        (self.repo / ".gitignore").write_text(".scratch/\n", encoding="utf-8")

        def during(cwd):
            (cwd / ".scratch").mkdir(exist_ok=True)
            (cwd / ".scratch/out.md").write_text("x\n", encoding="utf-8")
        code, out, spec = self._go([{"argv": PASS}], report=GOOD_REPORT + _block(f=".scratch/out.md", g="g1=0"),
                                   during=during, FILES_IN_SCOPE=".scratch/out.md\n.gitignore")
        self.assertEqual(spec["claims"]["unsupported"], 0, out)
        self.assertEqual(spec["claims"].get("not_checked"), [], out)
        self.assertIn(".scratch/out.md", [f["path"] for f in spec["scope"]["in_scope"]])


class F6F7MalformedBlockTest(unittest.TestCase):
    RUN = {"changed": [], "gate_results": [{"id": "g1", "rc": 0, "state": "passed", "excerpt": "Ran 3 tests"}], "stop_rule": "r"}

    def _check(self, text):
        return CC.check(text, self.RUN)

    def _assert_malformed(self, text):
        got = self._check(text)
        self.assertEqual((got["state"], got["reason"], got["unsupported"], got["stopped"]), ("not-checked", "claims-block-malformed", 0, False), text)

    def test_duplicate_files_changed_is_unreadable(self):
        self._assert_malformed("```claims\nfiles_changed: made-up.txt\nfiles_changed: none\ngates: g1=0\nstopped: none\n```\n")

    def test_duplicate_tests_key_is_unreadable(self):
        self._assert_malformed(_block(g="g1=0", extra="tests: g1=999\ntests: g1=3\n"))

    def test_tests_pair_without_equals_is_unreadable(self):
        self._assert_malformed(_block(g="g1=0", extra="tests: g1:999\n"))

    def test_empty_values_are_unreadable(self):
        for bad in ("files_changed:\ngates: none\nstopped: none", "files_changed: none\ngates:\nstopped: none",
                    "files_changed: none\ngates: none\ntests:\nstopped: none", "files_changed: none\ngates: none\nstopped:"):
            with self.subTest(bad):
                self._assert_malformed("```claims\n" + bad + "\n```\n")

    def test_bad_gate_pair_is_unreadable(self):
        self._assert_malformed(_block(g="g1"))
        self._assert_malformed(_block(g="g1=ok"))

    def test_empty_stopped_is_not_a_stop(self):
        self.assertFalse(self._check("```claims\nfiles_changed: none\ngates: none\nstopped:\n```\n")["stopped"])

    def test_none_is_the_explicit_empty(self):
        got = self._check(_block(g="g1=0", extra="tests: none\n"))
        self.assertEqual((got["state"], got["unsupported"]), ("checked", 0))

    def test_unknown_keys_stay_ignored(self):
        got = self._check(_block(g="g1=0", extra="mood: fine\n"))
        self.assertEqual(got["state"], "checked")


class F8FenceScanTest(unittest.TestCase):
    def test_20000_unclosed_openers_scan_in_linear_time(self):
        text = "```claims\n" * 20000
        start = time.perf_counter()
        got = CC.check(text, {})
        self.assertLess(time.perf_counter() - start, 0.5)
        self.assertEqual(got["state"], "not-checked")

    def test_oversized_report_is_too_large(self):
        got = CC.check("x" * ((1 << 20) + 1), {})
        self.assertEqual((got["state"], got["reason"]), ("not-checked", "claims-too-large"))

    def test_oversized_block_is_too_large(self):
        got = CC.check("```claims\nfiles_changed: none\ngates: none\nstopped: none\n" + "# pad\n" * 12000 + "```\n", {})
        self.assertEqual((got["state"], got["reason"]), ("not-checked", "claims-too-large"))

    def test_stripping_is_linear_too(self):
        start = time.perf_counter()
        dispatch.strip_claims_fences("```claims\n" * 20000)
        self.assertLess(time.perf_counter() - start, 0.5)


class F9ExitCodeIsWhatTheProcessReturnsTest(VerdictBase):
    def _ledger(self):
        path = self.root / ".local/state/agents-inc/host-ledger/.workerbees/ledger.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

    def test_free_precheck_refusal_records_exit_two(self):
        model = next(iter(free_launch.FREE_MODELS))
        refusal = free_launch.Refusal("refused-classification", "no")
        with mock.patch.object(free_launch, "pre_checks", return_value=refusal):
            code, out, _ = self._main("--slots", str(self._slots()), "--model", model, "--cwd", str(self.repo),
                                      "--run-dir", str(self.runs))
        self.assertEqual(code, 2, out)
        self.assertEqual(self._spec()["exit_code"], 2)
        self.assertEqual(self._ledger()[-1]["exit_code"], 2)

    def test_ordinary_refusal_stays_three(self):
        with mock.patch.object(dispatch, "lint_prompt", return_value=([12], "")):
            code, _, _ = self._main("--slots", str(self._slots()), "--model", "sonnet", "--cwd", str(self.repo),
                                    "--run-dir", str(self.runs))
        self.assertEqual((code, self._spec()["exit_code"], self._ledger()[-1]["exit_code"]), (3, 3, 3))


class F10ReasonRankTest(unittest.TestCase):
    def _o(self, **kw):
        base = dict(report="COMPLIANT", vrc=0, rc=0, fan_reason=None, gate_reason=None, gated=True, snap="clean")
        base.update(kw)
        return dispatch._outcome({}, base.pop("report"), base.pop("vrc"), base.pop("rc"), base.pop("fan_reason"),
                                 base.pop("gate_reason"), base.pop("gated"), **base)

    def test_declared_stop_outranks_skipped_snapshot_and_broker_child(self):
        self.assertEqual(self._o(snap=dispatch.SNAPSHOT_SKIPPED, stopped=True), ("unverified", "delegate-stopped"))
        self.assertEqual(self._o(gated=False, broker_skipped=True, stopped=True), ("unverified", "delegate-stopped"))

    def test_foreign_change_outranks_broker_skip(self):
        self.assertEqual(self._o(gated=False, broker_skipped=True, snap="CHANGED:a.txt", vrc=1),
                         ("unverified", "scope-foreign-change"))

    def test_skip_reasons_at_their_own_rank(self):
        self.assertEqual(self._o(snap=dispatch.SNAPSHOT_SKIPPED, gated=False), ("unverified", "snapshot-skipped"))
        self.assertEqual(self._o(gated=False, broker_skipped=True), ("unverified", "gates-skipped-broker"))
        self.assertEqual(self._o(gated=False), ("unverified", "no-gates"))

    def test_failed_gate_still_outranks_everything(self):
        self.assertEqual(self._o(gate_reason="gate-failed", broker_skipped=True, stopped=True)[0], "red")


class F11ResumeRowsTest(VerdictBase):
    def _ledger(self):
        path = self.root / ".local/state/agents-inc/host-ledger/.workerbees/ledger.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

    def _first_turn(self):
        self._go([{"argv": PASS}])
        return self._spec()["run_id"]

    def _resume(self, message, **patch):
        with mock.patch.object(dispatch, "launch", **patch):
            return self._main("--resume", self._run_id, "--message", message, "--run-dir", str(self.runs))

    def test_refused_resume_records_its_own_row_and_keeps_older_rows(self):
        self._run_id = self._first_turn()
        before = self._ledger()
        code, out, err = self._resume("bad\x07message", side_effect=AssertionError("must not launch"))
        after = self._ledger()
        self.assertEqual(code, 3, err)
        self.assertEqual(after[:len(before)], before)
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual((after[-1]["status"], after[-1]["exit_code"], after[-1]["state"]), ("refused-control-char", 3, "not-checked"))
        self.assertEqual(after[-1]["dispatch_row_id"], self._run_id)

    def test_cancelled_resume_records_a_cancelled_row(self):
        self._run_id = self._first_turn()
        before = len(self._ledger())
        code, out, err = self._resume("go on", side_effect=dispatch.Cancelled("SIGTERM"))
        rows = self._ledger()
        self.assertEqual(code, 130, err)
        self.assertEqual(len(rows), before + 1)
        self.assertEqual((rows[-1]["status"], rows[-1]["exit_code"]), ("cancelled", 130))


class F12PathTransportTest(VerdictBase):
    def test_a_comma_in_a_file_name_does_not_invent_paths(self):
        code, out, spec = self._go([{"argv": PASS}], report=GOOD_REPORT + _block(f="a", g="g1=0"),
                                   during=self._stray("a,b.txt"), FILES_IN_SCOPE="agents_inc/x.py")
        self.assertEqual([f["path"] for f in spec["scope"]["foreign"]], ["a,b.txt"], out)
        self.assertEqual([i["kind"] for i in spec["claims"]["items"]], ["file-changed"])
        self.assertEqual(len(spec["scope"]["foreign"]), 1)


if __name__ == "__main__":
    unittest.main()
