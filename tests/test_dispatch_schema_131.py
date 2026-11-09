"""#131 step A: dispatch_record.v1 validator, normalize, STOP ON BLOCK line, slots link in run.json and the ledger.

Temp dirs only. No real dispatch runs.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc import host_ledger
from agents_inc.install import dispatch
from tests.test_dispatch_snapshot_trust import DispatchBase, ok_launch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "workerbee" / "scripts"
EXAMPLE = ROOT / "skills/workerbee/tests/fixtures/example_slots.json"
RENDER = SCRIPTS / "render_dispatch.py"
LINT = SCRIPTS / "check_dispatch_prompt.py"
sys.path.insert(0, str(SCRIPTS))
import dispatch_schema as ds  # noqa: E402


def example(**extra) -> dict:
    data = json.loads(EXAMPLE.read_text())
    data.update(extra)
    return data


def render(data, home=None, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "slots.json"
        path.write_text(json.dumps(data))
        env = {"HOME": home or tmp, "PATH": "/usr/bin:/bin"}
        return subprocess.run([sys.executable, str(RENDER), "--slots", str(path), "--model", "haiku", *extra],
                              capture_output=True, text=True, env=env)


class ValidateTest(unittest.TestCase):
    def test_sonnet_default_fan_out_passes_lint(self):
        names = ("ROLE", "TASK", "CONSTRAINTS", "OUT_OF_SCOPE", "FILES_IN_SCOPE", "STOP_RULE",
                 "SUCCESS_GATE", "FAILURE_GATE")
        slots = {name: example()[name] for name in names}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "slots.json"
            prompt = Path(tmp) / "prompt.txt"
            path.write_text(json.dumps(slots))
            env = {"HOME": tmp, "PATH": "/usr/bin:/bin"}
            rendered = subprocess.run([sys.executable, str(RENDER), "--slots", str(path), "--model", "sonnet"],
                                      capture_output=True, text=True, env=env)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            prompt.write_text(rendered.stdout)
            lint = subprocess.run([sys.executable, str(LINT), str(prompt), "--model", "sonnet"],
                                  capture_output=True, text=True, env=env)
            self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_ceiling_error_names_limit_and_fix(self):
        from tests.test_dispatch_contract import COMPLIANT_PROMPT
        with tempfile.TemporaryDirectory() as tmp:
            prompt = Path(tmp) / "prompt.txt"
            prompt.write_text(COMPLIANT_PROMPT + "FAN_OUT: width 3, total 6, depth 2\n")
            lint = subprocess.run([sys.executable, str(LINT), str(prompt), "--model", "sonnet"],
                                  capture_output=True, text=True, env={"HOME": tmp, "PATH": "/usr/bin:/bin"})
            self.assertEqual(lint.returncode, 1)
            self.assertIn("width 2, total 4, depth 1", lint.stdout)
            self.assertIn("reduce", lint.stdout.lower())
            self.assertNotIn("missing", lint.stdout.lower())

    def test_example_is_valid(self):
        self.assertEqual(ds.validate_record(example()), [])

    def test_schema_version_absent_is_one(self):
        self.assertEqual(ds.SCHEMA_VERSION, 1)
        self.assertEqual(ds.validate_record(example()), [])
        self.assertEqual(ds.validate_record(example(schema_version=1)), [])

    def test_schema_version_2_refused(self):
        errors = ds.validate_record(example(schema_version=2))
        self.assertEqual(len(errors), 1)
        self.assertIn("schema_version", errors[0])
        self.assertTrue(ds.validate_record(example(schema_version="1")))
        self.assertTrue(ds.validate_record(example(schema_version=True)))

    def test_not_an_object(self):
        self.assertIn("JSON object", ds.validate_record([1])[0])

    def test_files_in_scope_type_errors(self):
        for bad in (5, {"a": 1}, [], [""], [3], ["a\nb"]):
            errors = ds.validate_record(example(FILES_IN_SCOPE=bad))
            self.assertTrue(any(e.startswith("FILES_IN_SCOPE") for e in errors), (bad, errors))
        self.assertEqual(ds.validate_record(example(FILES_IN_SCOPE=["a.py", "b/c.py"])), [])
        self.assertEqual(ds.validate_record(example(FILES_IN_SCOPE="none")), [])

    def test_allowlist_type_errors(self):
        for bad in (7, [], [None], ["x\ny"]):
            errors = ds.validate_record(example(ALLOWLIST=bad))
            self.assertTrue(any(e.startswith("ALLOWLIST") for e in errors), (bad, errors))
        self.assertEqual(ds.validate_record(example(ALLOWLIST=["haiku", "luna"])), [])
        self.assertEqual(ds.validate_record(example(ALLOWLIST="none")), [])

    def test_fan_out_errors_name_the_key(self):
        for bad, needle in (({"width": 1, "total": 2}, "FAN_OUT.depth"),
                            ({"width": "1", "total": 2, "depth": 0}, "FAN_OUT.width"),
                            ({"width": 1, "total": -2, "depth": 0}, "FAN_OUT.total"),
                            ({"width": True, "total": 2, "depth": 0}, "FAN_OUT.width"),
                            ({"width": 1, "total": 2, "depth": 0, "x": 1}, "unknown keys"),
                            ("lots", "FAN_OUT string"), (4, "FAN_OUT must be an object")):
            errors = ds.validate_record(example(FAN_OUT=bad))
            self.assertTrue(any(needle in e for e in errors), (bad, errors))
        self.assertEqual(ds.validate_record(example(FAN_OUT={"width": 3, "total": 6, "depth": 2})), [])

    def test_classification_enum(self):
        for good in ("public", "internal (repo source, non-secret)", "Confidential: client data", "public."):
            self.assertEqual(ds.validate_record(example(CLASSIFICATION=good)), [], good)
        for bad in ("secret", "top internal", 3):
            errors = ds.validate_record(example(CLASSIFICATION=bad))
            self.assertTrue(any("CLASSIFICATION" in e and "public, internal, confidential" in e for e in errors), bad)

    def test_effort_enum(self):
        for good in ("low", "medium.", "xhigh", "max", "as set by the transport; medium when unset",
                     "effort control unavailable on this transport; intended level = low"):
            self.assertEqual(ds.validate_record(example(EFFORT=good)), [], good)
        for bad in ("fast", "extra", 2):
            errors = ds.validate_record(example(EFFORT=bad))
            self.assertTrue(any(e.startswith("EFFORT must name one of low, medium, high, xhigh, max") for e in errors), bad)

    def test_ultra_only_for_codex(self):
        self.assertTrue(any("ultra is for a codex model only" in e
                            for e in ds.validate_record(example(EFFORT="ultra"), model="haiku")))
        self.assertTrue(ds.validate_record(example(EFFORT="ultra")))
        self.assertEqual(ds.validate_record(example(EFFORT="ultra"), model="sol"), [])
        self.assertEqual(ds.validate_record(example(EFFORT="ultra", DELEGATE="luna")), [])

    def test_blank_optional_slots_are_not_errors(self):
        self.assertEqual(ds.validate_record(example(FAN_OUT="", ALLOWLIST="", EFFORT="", CLASSIFICATION="")), [])


class NormalizeTest(unittest.TestCase):
    def test_old_string_forms_convert(self):
        data = example(FILES_IN_SCOPE="a.py\nb/c.py\n", ALLOWLIST="haiku, luna", FAN_OUT="width 2, total 4, depth 1")
        out, converted = ds.normalize(data)
        self.assertEqual(out["FILES_IN_SCOPE"], ["a.py", "b/c.py"])
        self.assertEqual(out["ALLOWLIST"], ["haiku", "luna"])
        self.assertEqual(out["FAN_OUT"], {"width": 2, "total": 4, "depth": 1})
        self.assertEqual(converted, ["FILES_IN_SCOPE", "ALLOWLIST", "FAN_OUT"])
        self.assertEqual(data["FILES_IN_SCOPE"], "a.py\nb/c.py\n")  # input untouched

    def test_none_strings_convert(self):
        out, converted = ds.normalize(example())
        self.assertEqual(out["FILES_IN_SCOPE"], ["none"])
        self.assertEqual(out["ALLOWLIST"], ["none"])
        self.assertEqual(out["FAN_OUT"], {"width": 0, "total": 0, "depth": 0})
        self.assertEqual(ds.validate_record(out), [])

    def test_structured_input_not_reported(self):
        data = example(FILES_IN_SCOPE=["a.py"], FAN_OUT={"width": 0, "total": 0, "depth": 0})
        out, converted = ds.normalize(data)
        self.assertNotIn("FILES_IN_SCOPE", converted)
        self.assertNotIn("FAN_OUT", converted)
        self.assertEqual(out["FILES_IN_SCOPE"], ["a.py"])

    def test_bad_fan_out_string_stays_for_validation(self):
        out, converted = ds.normalize(example(FAN_OUT="lots"))
        self.assertEqual(out["FAN_OUT"], "lots")
        self.assertNotIn("FAN_OUT", converted)
        self.assertTrue(ds.validate_record(out))

    def test_absent_and_blank_untouched(self):
        data = example(FAN_OUT="", ALLOWLIST="")
        out, converted = ds.normalize(data)
        self.assertEqual(converted, ["FILES_IN_SCOPE"])
        self.assertEqual(out["ALLOWLIST"], "")


class RenderTest(unittest.TestCase):
    def test_structured_and_string_forms_render_identically(self):
        text = render(example(FILES_IN_SCOPE="a.py\nb/c.py", ALLOWLIST="haiku, luna", FAN_OUT="width 0, total 0, depth 0"))
        structured = render(example(FILES_IN_SCOPE=["a.py", "b/c.py"], ALLOWLIST=["haiku", "luna"],
                                    FAN_OUT={"width": 0, "total": 0, "depth": 0}))
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(structured.returncode, 0, structured.stderr)
        self.assertEqual(text.stdout, structured.stdout)
        self.assertIn("FILES IN SCOPE:\na.py\nb/c.py\n", structured.stdout)
        self.assertIn("SUB-DELEGATE MODEL ALLOWLIST: haiku, luna\n", structured.stdout)

    def test_none_forms_render_the_default_text(self):
        out = render(example(ALLOWLIST=["none"])).stdout
        self.assertIn("SUB-DELEGATE MODEL ALLOWLIST: none -- do all work yourself\n", out)

    def test_normalized_line_beside_defaults_filled(self):
        data = example(FILES_IN_SCOPE="a.py", FAN_OUT="width 0, total 0, depth 0")
        data.pop("EFFORT")
        proc = render(data)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("defaults filled: EFFORT", proc.stderr)
        self.assertIn("normalized: FILES_IN_SCOPE, ALLOWLIST, FAN_OUT", proc.stderr)

    def test_structured_input_prints_no_normalized_line(self):
        proc = render(example(FILES_IN_SCOPE=["none"], ALLOWLIST=["none"], FAN_OUT={"width": 0, "total": 0, "depth": 0}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("normalized:", proc.stderr)

    def test_old_string_render_is_unchanged_text(self):
        out = render(example()).stdout
        self.assertIn("FILES IN SCOPE:\nnone (read-only scout)\n", out)
        self.assertIn("FAN_OUT: width 0, total 0, depth 0\n", out)

    def test_validation_errors_exit_2(self):
        for bad, needle in ((dict(schema_version=2), "schema_version"), (dict(FAN_OUT={"width": 1}), "FAN_OUT.total"),
                            (dict(EFFORT="fast"), "EFFORT"), (dict(CLASSIFICATION="secret"), "CLASSIFICATION"),
                            (dict(FILES_IN_SCOPE=[3]), "FILES_IN_SCOPE")):
            proc = render(example(**bad))
            self.assertEqual(proc.returncode, 2, bad)
            self.assertIn(needle, proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_ultra_is_allowed_for_a_codex_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps(example(EFFORT="ultra")))
            env = {"HOME": tmp, "PATH": "/usr/bin:/bin"}
            for model, rc in (("sol", 0), ("haiku", 2)):
                proc = subprocess.run([sys.executable, str(RENDER), "--slots", str(path), "--model", model],
                                      capture_output=True, text=True, env=env)
                self.assertEqual(proc.returncode, rc, (model, proc.stderr))

    def test_stop_on_block_line_once_after_constraints(self):
        for extra in (("--contract-ref", "skills/workerbee/header.md"), ()):
            out = render(example(), None, *extra).stdout
            lines = [ln for ln in out.splitlines() if ln.startswith("STOP ON BLOCK:")]
            self.assertEqual(len(lines), 1, out)
            self.assertEqual(out.count("STOP ON BLOCK:"), 1)
            self.assertEqual(lines[0], STOP_LINE)
            names = [ln.split(":")[0] for ln in out.splitlines()]
            self.assertEqual(names.index("STOP ON BLOCK"), names.index("CONSTRAINTS") + 1)
            self.assertEqual(names.index("STOP ON BLOCK") + 1, names.index("OUT OF SCOPE"))

    def test_rendered_example_passes_the_prompt_lint(self):
        out = render(example()).stdout
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt.txt"
            path.write_text(out)
            proc = subprocess.run([sys.executable, str(LINT), str(path)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


STOP_LINE = ("STOP ON BLOCK: if a hook, permission classifier or sandbox blocks a tool call that the task needs, "
             "stop and hand back to the dispatcher with the work done so far; never switch to another tool to "
             "route around the block. A denial of an incidental side effect, such as a cache write, is not a "
             "block: ignore it and continue.")


class PinnedTest(DispatchBase):
    def test_pinned_set_names_the_schema(self):
        self.assertIn("dispatch_schema.py", dispatch.PINNED_SCRIPTS)

    def test_renderer_imports_its_own_directory_copy(self):
        src = RENDER.read_text()
        self.assertIn("import dispatch_schema", src)
        self.assertIn("_SCRIPT_DIR", src)

    def test_tampered_schema_copy_is_refused(self):
        src = self.root / "src"
        src.mkdir()
        for name in dispatch.PINNED_SCRIPTS:
            (src / name).write_bytes((SCRIPTS / name).read_bytes())
        (src.parent / "slots.md").write_text("x")
        (src.parent / "header.md").write_text("x")
        run_id = "20261103T000000Z-haiku-131aaa"
        with mock.patch.object(dispatch, "_trust_path", lambda rid: self.root / "trust" / rid):
            pinned = dispatch._pin_scripts(src, run_id)
            self.assertEqual((pinned / "dispatch_schema.py").read_bytes(), (SCRIPTS / "dispatch_schema.py").read_bytes())
            record = json.loads((pinned.parent.parent / "trust.json").read_text())
            self.assertIn("dispatch_schema.py", record["scripts_sha256"])
            self.assertIsNone(dispatch._scripts_tampered(pinned))
            (pinned / "dispatch_schema.py").write_text("# tampered\n")
            self.assertIn("dispatch_schema.py", dispatch._scripts_tampered(pinned))


class SlotsLinkTest(DispatchBase):
    def test_run_json_carries_slots_sha256_and_schema_version(self):
        slots = self.slots()
        rc, out, _ = self.dispatch(ok_launch(), slots=slots)
        self.assertEqual(rc, 0, out)
        spec = self.spec()
        self.assertEqual(spec["slots_sha256"], hashlib.sha256(slots.read_bytes()).hexdigest())
        self.assertEqual(spec["schema_version"], 1)
        copy = self.run_dir() / "slots.json"
        self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(), spec["slots_sha256"])

    def test_dispatched_ledger_row_carries_slots_sha256(self):
        slots = self.slots()
        rc, out, _ = self.dispatch(ok_launch(), slots=slots)
        self.assertEqual(rc, 0, out)
        spec = self.spec()
        rows = [json.loads(ln) for ln in
                (self.state / "host-ledger" / ".workerbees" / "ledger.jsonl").read_text().splitlines() if ln.strip()]
        dispatched = [r for r in rows if r.get("status") == "dispatched" and r.get("id") == spec["run_id"]]
        self.assertEqual(len(dispatched), 1, rows)
        self.assertEqual(dispatched[0]["slots_sha256"], hashlib.sha256(slots.read_bytes()).hexdigest())
        self.assertEqual(dispatched[0]["slots_path"], str(self.run_dir() / "slots.json"))

    def test_structured_slots_dispatch_end_to_end(self):
        slots = self.slots(FILES_IN_SCOPE=["none (read-only scout)"], ALLOWLIST=["none"],
                           FAN_OUT={"width": 0, "total": 0, "depth": 0})
        rc, out, _ = self.dispatch(ok_launch(), slots=slots)
        self.assertEqual(rc, 0, out)
        self.assertIn("FAN_OUT: width 0, total 0, depth 0", (self.run_dir() / "prompt.md").read_text())

    def test_bad_record_is_refused_before_launch(self):
        rc, out, _ = self.dispatch(ok_launch(), slots=self.slots(schema_version=2))
        self.assertEqual(rc, 3, out)


class LedgerRowTest(unittest.TestCase):
    SPEC = {"run_id": "20261103T000000Z-haiku-abc123", "kind": "claude", "model": "haiku", "effort": "medium", "cwd": "/x"}

    def test_row_gains_slots_fields_only_when_present(self):
        plain = host_ledger.dispatch_run_row(self.SPEC, "t")
        self.assertNotIn("slots_sha256", plain)
        self.assertNotIn("slots_path", plain)
        spec = dict(self.SPEC, slots_sha256="ab" * 32, slots_path="/runs/x/slots.json")
        row = host_ledger.dispatch_run_row(spec, "t")
        self.assertEqual((row["slots_sha256"], row["slots_path"]), ("ab" * 32, "/runs/x/slots.json"))
        skip = ("slots_sha256", "slots_path", "timestamp")
        self.assertEqual({k: v for k, v in row.items() if k not in skip},
                         {k: v for k, v in plain.items() if k not in skip})


if __name__ == "__main__":
    unittest.main()
