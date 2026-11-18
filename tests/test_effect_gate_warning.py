"""Spec 045 FR-004 (#155 j): a BASH_ALLOW prefix that can act outside the repo with no gate on the same command prints one
stderr warning; never a refusal."""
import contextlib
import io
import unittest
from pathlib import Path

from agents_inc.install import dispatch

RD = dispatch._load("render_dispatch")


class EffectGateTest(unittest.TestCase):
    def test_prefix_list_is_pinned(self):
        self.assertEqual(RD.EFFECT_PREFIXES, ("gh", "npm publish", "git tag", "aws", "gcloud", "docker push", "twine",
                                              "kubectl"))

    def test_gh_without_gh_gate_warns(self):
        out = RD.effect_gate_warnings(["gh issue comment"], [{"argv": ["python3", "-c", "pass"]}])
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("warning: effect-gate-missing:"), out)

    def test_gh_with_gh_gate_is_quiet(self):
        self.assertEqual(RD.effect_gate_warnings(["gh issue comment"], [{"argv": ["gh", "issue", "view", "1"]}]), [])

    def test_absolute_gate_path_counts_by_basename(self):  # 045 review F4
        self.assertEqual(RD.effect_gate_warnings(["gh issue comment"], [{"argv": ["/usr/bin/gh", "issue", "view"]}]), [])

    def test_local_prefix_is_quiet(self):
        self.assertEqual(RD.effect_gate_warnings(["python3", "git status", "npm test"], None), [])

    def test_dispatch_prints_and_does_not_refuse(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            gates, allow, refused = dispatch._grants_from_slots(
                {"GATES": [{"argv": ["true"]}], "BASH_ALLOW": ["gh pr comment"]}, Path.cwd().resolve())
        self.assertIsNone(refused)
        self.assertIn("warning: effect-gate-missing", err.getvalue())


if __name__ == "__main__":
    unittest.main()
