"""Spec 042 phase 2 (T023, T073): the claim check lists each unsupported claim, never changes an outcome, makes no model
call. Fixtures in tests/fixtures/claims/*.json: report text, run data, expected result."""
from __future__ import annotations
import json
import time
import unittest
from pathlib import Path

from agents_inc.install import dispatch

FIX = Path(__file__).parent / "fixtures" / "claims"
CC = dispatch._load("check_claims")


def fixtures():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIX.glob("*.json"))]


class FixtureTest(unittest.TestCase):
    def test_at_least_20_report_fixtures(self):
        names = [f["name"] for f in fixtures()]
        self.assertGreaterEqual(len([n for n in names if n.startswith("false")]), 10)
        self.assertGreaterEqual(len([n for n in names if n.startswith("true")]), 10)
        self.assertGreaterEqual(len([n for n in names if n.startswith("rt-")]), 6)

    def test_every_fixture_matches_its_expected_result(self):
        for f in fixtures():
            with self.subTest(f["name"]):
                got, want = CC.check(f["report"], f["run"]), f["expect"]
                self.assertEqual(got["state"], want["state"])
                self.assertEqual(got["reason"], want["reason"])
                self.assertEqual(got["items"], want["items"])
                self.assertEqual(got["omitted"], want["omitted"])
                self.assertEqual(got["weak"], want["weak"])
                self.assertEqual(got["unclaimed"], want["unclaimed"])
                self.assertEqual(got["unsupported"], len(want["items"]))

    def test_true_reports_list_nothing_and_warn_nothing(self):
        for f in fixtures():
            if f["name"].startswith("true"):
                with self.subTest(f["name"]):
                    got = CC.check(f["report"], f["run"])
                    self.assertEqual((got["state"], got["unsupported"], got["omitted"], got["weak"], got["unclaimed"]),
                                     ("checked", 0, [], [], []))

    def test_missing_or_unreadable_block_is_not_checked_never_passed(self):
        for f in fixtures():
            if f["expect"]["state"] == "not-checked":
                with self.subTest(f["name"]):
                    got = CC.check(f["report"], f["run"])
                    self.assertEqual(got["state"], "not-checked")
                    self.assertEqual(got["unsupported"], 0)

    def test_multiple_blocks_compare_nothing(self):
        f = next(x for x in fixtures() if x["name"] == "rt-a-multiple-blocks-later-true")
        got = CC.check(f["report"], f["run"])
        self.assertEqual([i["reason"] for i in got["items"]], ["multiple-claims-blocks"])
        self.assertEqual((got["omitted"], got["unclaimed"], got["weak"]), ([], [], []))

    def test_stopped_flag_only_for_one_readable_block(self):
        f = next(x for x in fixtures() if x["name"] == "rt-e-stop-s1")
        self.assertTrue(CC.check(f["report"], f["run"])["stopped"])
        self.assertFalse(CC.check("nothing", f["run"])["stopped"])

    def test_not_catchable_attacks_pass_without_warning(self):
        """Documented reviewer-only (spec.md 'Not catchable'): a cosmetic edit, a meaningless gate, a rewritten test."""
        run = {"changed": ["a.py", "tests/test_a.py"], "stop_rule": "x",
               "gate_results": [{"id": "g1", "argv": ["true"], "rc": 0, "expect_rc": 0, "state": "passed", "excerpt": ""}]}
        report = "```claims\nfiles_changed: a.py, tests/test_a.py\ngates: g1=0\nstopped: none\n```\n"
        got = CC.check(report, run)
        self.assertEqual((got["unsupported"], got["omitted"], got["weak"], got["unclaimed"]), (0, [], [], []))

    def test_50_claims_10_gates_under_one_second(self):
        gates = [{"id": f"g{i}", "argv": ["t"], "rc": 0, "expect_rc": 0, "state": "passed", "excerpt": "Ran 5 tests\n" * 50}
                 for i in range(1, 11)]
        files = [f"f{i}.py" for i in range(30)]
        report = ("```claims\nfiles_changed: " + ", ".join(files) + "\ngates: " + "; ".join(f"g{i}=0" for i in range(1, 11))
                  + "\ntests: " + "; ".join(f"g{i}=5" for i in range(1, 11)) + "\nstopped: none\n```\n")
        start = time.perf_counter()
        got = CC.check(report, {"changed": files, "gate_results": gates, "stop_rule": "x"})
        self.assertLess(time.perf_counter() - start, 1.0)
        self.assertEqual(got["unsupported"], 0)


if __name__ == "__main__":
    unittest.main()
