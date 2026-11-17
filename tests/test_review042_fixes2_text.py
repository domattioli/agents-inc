"""Review 042 phase 2 fixes, slice C: refusal text redaction and cap (G5, G14), scope-unreadable verdict (G6),
renderer rule table (G9), stale refusal provenance (G13)."""
from __future__ import annotations
import ast
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli, doctor, dispatch, rules

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/workerbee/scripts"


def _copies():
    out = [rules.format_refusal]
    import importlib.util
    sys.path.insert(0, str(SCRIPTS))
    try:
        for name in ("render_dispatch", "check_dispatch_prompt"):
            spec = importlib.util.spec_from_file_location(f"_t_{name}", SCRIPTS / f"{name}.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            out.append(mod.format_refusal)
    finally:
        sys.path.remove(str(SCRIPTS))
    return out


class RedactionTest(unittest.TestCase):
    def test_structured_secret_values_are_hidden_in_every_copy(self):
        for fn in _copies():
            with self.subTest(fn=fn.__module__):
                for val in ({"password": "FAKE_DEMO_VALUE"}, {"a": [{"token": "FAKE_DEMO_VALUE"}]},
                            {"Authorization": "FAKE_DEMO_VALUE", "ok": 1}, [{"secret": "FAKE_DEMO_VALUE"}]):
                    self.assertNotIn("FAKE_DEMO_VALUE", fn("r", "s", "f", val))
                self.assertIn("ok", fn("r", "s", "f", {"Authorization": "x", "ok": 1}))

    def test_whole_value_under_secret_key_is_replaced(self):
        for fn in _copies():
            with self.subTest(fn=fn.__module__):
                for val in ({"token": {"opaque": "SYNTHETIC_VALUE"}}, {"api_key": ["SYNTHETIC_VALUE", 1]},
                            {"credentials": 5}, {"x": {"passwd": {"a": ["SYNTHETIC_VALUE"]}}}):
                    out = fn("r", "s", "f", val)
                    self.assertNotIn("SYNTHETIC_VALUE", out)
                    self.assertIn("[secret hidden]", out)
                for text in ("credential=SYNTHETIC_VALUE", "credentials: SYNTHETIC_VALUE", "auth=SYNTHETIC_VALUE",
                             "api_key=SYNTHETIC_VALUE", "apikey=SYNTHETIC_VALUE", "passwd=SYNTHETIC_VALUE",
                             "bearer SYNTHETIC_VALUE", "Bearer SYNTHETIC_VALUE", 'credential="SYNTHETIC_VALUE"'):
                    self.assertNotIn("SYNTHETIC_VALUE", fn("r", "s", "f", text), text)

    def test_whole_quoted_value_is_consumed(self):
        for fn in _copies():
            with self.subTest(fn=fn.__module__):
                for text in ('password: "FAKE_DEMO_VALUE has spaces"', "token='FAKE_DEMO_VALUE has spaces' tail"):
                    out = fn("r", "s", "f", text)
                    self.assertNotIn("FAKE_DEMO", out)
                    self.assertNotIn("spaces", out)

    def test_value_is_at_most_200_bytes_with_suffix(self):
        for fn in _copies():
            with self.subTest(fn=fn.__module__):
                for ch in ("x", "é"):
                    line = fn("r", "s", "f", ch * 500).splitlines()[1]
                    self.assertLessEqual(len(line[len("value: "):].encode()), 200)
                    self.assertTrue(line.endswith("..."))
                self.assertEqual(fn("r", "s", "f", "y" * 200).splitlines()[1], "value: " + "y" * 200)


class ScopeUnreadableTest(unittest.TestCase):
    def test_unreadable_scope_is_unverified_ranked_after_stop(self):
        o = lambda **k: dispatch._outcome({}, "COMPLIANT", 0, 0, None, k.pop("gate_reason", None), True, snap="clean", **k)
        self.assertEqual(o(scope_unreadable=True), ("unverified", "scope-unreadable"))
        self.assertEqual(o(scope_unreadable=True, stopped=True), ("unverified", "delegate-stopped"))
        self.assertEqual(o(scope_unreadable=True, gate_reason="gate-failed"), ("red", "gate-failed"))
        self.assertEqual(o(scope_unreadable=False), ("green", None))
        self.assertEqual(dispatch._outcome({}, "COMPLIANT", 0, 0, None, None, False, snap="clean", scope_unreadable=True),
                         ("unverified", "scope-unreadable"))

    def test_exit_code_is_four(self):
        self.assertEqual(dispatch._exit_code("unverified", "scope-unreadable", 0), 4)


class RendererTableTest(unittest.TestCase):
    def test_every_selectable_rule_id_is_in_each_table(self):
        for name in ("render_dispatch.py", "check_dispatch_prompt.py"):
            tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
            ids = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(r"[a-z]+(-[a-z0-9]+)+", node.value):
                    ids.add(node.value)
            import importlib.util
            sys.path.insert(0, str(SCRIPTS))
            try:
                spec = importlib.util.spec_from_file_location(f"_t2_{name[:-3]}", SCRIPTS / name)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            finally:
                sys.path.remove(str(SCRIPTS))
            for rid in ids & set(rules.RULES):
                if name == "render_dispatch.py" and rid.startswith(("lint-", "hook-", "broker-")):
                    continue
                with self.subTest(script=name, rule=rid):
                    self.assertIn(rid, mod.REFUSAL_RULES)

    def test_gate_with_cwd_dotdot_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            slots = Path(d) / "s.json"
            slots.write_text(json.dumps(dict(rules.SLOTS_EXAMPLE, GATES=[{"argv": ["true"], "cwd": ".."}])), encoding="utf-8")
            p = subprocess.run([sys.executable, str(SCRIPTS / "render_dispatch.py"), "--slots", str(slots)],
                               capture_output=True, text=True, cwd=d)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("gate-cwd-outside", p.stderr)


class StaleProvenanceTest(unittest.TestCase):
    def _refusal(self, basis):
        with mock.patch.object(doctor.InstallReceipt, "load", return_value=mock.Mock(release_hash="abc")), \
             mock.patch.object(doctor, "_stale_basis", return_value=(Path("/source"), basis)), \
             mock.patch.object(doctor.source_git, "RECORD", "rec.json"), \
             mock.patch("pathlib.Path.stat", return_value=mock.Mock(st_mtime=__import__("time").time() - 7200)):
            return doctor.stale_refusal(mock.Mock(receipt="r", state=Path("/state")))

    def test_record_basis_and_age(self):
        text = self._refusal("record")
        self.assertIn("record", text)
        self.assertRegex(text, r"\d+\s*(h|m|s|d)")
        self.assertIn("agents-inc repair --source /source", text)

    def test_measured_basis(self):
        text = self._refusal("measured")
        self.assertIn("measured now", text)
        self.assertIn("INSTALL_STALE", text)


if __name__ == "__main__":
    unittest.main()
