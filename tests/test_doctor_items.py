"""Spec 042 Phase 3 (US3): doctor items say whether each was tested now; READY rests on measurement."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

from agents_inc.install import cli, doctor
from agents_inc.install.doctor import check_install
from agents_inc.install.paths import InstallPaths

HOST = {"which": lambda *a, **k: "/usr/bin/claude", "sandbox_probe": lambda: True}
UP = {**HOST, "net_probe": lambda: True}
DOWN = {**HOST, "net_probe": lambda: False}


def _item(report, name):
    found = [i for i in report.items if i.name == name]
    assert found, (name, [i.name for i in report.items])
    return found[0]


class ItemsBase(unittest.TestCase):
    git = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raw = Path(self.tmp.name)
        self.source = raw / "source"
        (self.source / "agents_inc").mkdir(parents=True)
        (self.source / "agents_inc" / "models.json").write_text("{}")
        for name in ("workerbee", "codex-bridge"):
            (self.source / "skills" / name).mkdir(parents=True)
            (self.source / "skills" / name / "SKILL.md").write_text("x")
        scripts = self.source / "skills/codex-bridge/scripts"; scripts.mkdir(parents=True)
        (scripts / "at_route.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        if self.git:
            for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
                subprocess.run(["git", "-C", str(self.source), *argv], check=True, capture_output=True)
        self.home = raw / "home"; (self.home / ".claude").mkdir(parents=True)
        self.paths = InstallPaths.for_home(self.home)
        args = argparse.Namespace(source=str(self.source), adopt_existing_workerbee=False, without_codex=True, no_host_wiring=False, yes=True)
        with mock.patch.object(cli, "_paths", return_value=self.paths), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.install(args), 0)

    def tearDown(self): self.tmp.cleanup()


class DoctorItemsTest(ItemsBase):
    def test_all_required_tested_and_passed_is_ready(self):
        report = check_install(self.paths, models=[], **UP)
        self.assertTrue(report.ready, report)
        required = [i for i in report.items if i.required]
        self.assertTrue(required)
        self.assertTrue(all(i.tested == "now" and i.result == "pass" for i in required), required)

    def test_unreachable_provider_is_not_ready_and_names_the_path(self):
        report = check_install(self.paths, models=[], **DOWN)
        self.assertFalse(report.ready)
        item = _item(report, "dispatch-path")
        self.assertIn(item.result, ("could-not-test", "fail"))
        self.assertTrue(item.required)
        self.assertIn("dispatch-path", report.untested)

    def test_probe_is_a_single_call_with_no_model_request(self):
        probe = mock.Mock(return_value=True)
        check_install(self.paths, models=[], net_probe=probe, **HOST)  # no --live-model: no Codex PONG either
        probe.assert_called_once_with()

    def test_default_probe_uses_two_second_timeout_and_no_model_call(self):
        with mock.patch("agents_inc.install.dispatch.api_reachable", return_value=False) as proxied, \
             mock.patch.object(doctor.socket, "create_connection", side_effect=OSError("down")) as direct:
            self.assertFalse(doctor.dispatch_path_probe({}))
            self.assertFalse(doctor.dispatch_path_probe({"HTTPS_PROXY": "http://127.0.0.1:9"}))
        self.assertEqual(direct.call_args.kwargs.get("timeout", direct.call_args.args[1:] and direct.call_args.args[1]), 2.0)
        self.assertEqual(proxied.call_args.kwargs.get("timeout"), 2.0)

    def test_claude_cli_missing_is_a_fail_item(self):
        report = check_install(self.paths, models=[], which=lambda *a, **k: None, sandbox_probe=lambda: True, net_probe=lambda: True)
        self.assertEqual(_item(report, "claude-cli").result, "fail")
        self.assertFalse(report.ready)

    def test_unfinished_repair_is_reported_and_blocks_ready(self):
        (self.paths.state / "repair-failed.json").write_text(json.dumps({"command": "repair", "at": "now", "error": "boom"}))
        report = check_install(self.paths, models=[], **UP)
        self.assertIn("WB_REPAIR_FAILED", report.codes)
        self.assertFalse(report.ready)
        item = _item(report, "repair")
        self.assertEqual((item.result, item.tested), ("fail", "now"))

    def test_digest_compare_is_measured_now(self):
        report = check_install(self.paths, models=[], **UP)
        item = _item(report, "install-match")
        self.assertEqual((item.result, item.tested), ("pass", "now"))
        self.assertFalse(any("not verified now" in line for line in doctor.item_lines(report)))

    def test_stale_by_digest_reports_measured(self):
        (self.source / "agents_inc" / "extra.txt").write_text("new")
        report = check_install(self.paths, models=[], **UP)
        self.assertIn("INSTALL_STALE", report.warnings)
        item = _item(report, "install-match")
        self.assertEqual((item.result, item.tested), ("warn", "now"))
        self.assertTrue(report.ready)

    def test_item_lines_use_the_name_result_tested_format(self):
        lines = doctor.item_lines(check_install(self.paths, models=[], **DOWN))
        self.assertIn("dispatch-path: could-not-test (not-tested)", [ln.split(" - ")[0] for ln in lines])
        self.assertTrue(all(": " in ln and "(" in ln for ln in lines))

    def test_json_adds_items(self):
        out = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), mock.patch.object(doctor, "dispatch_path_probe", return_value=True), \
             mock.patch("shutil.which", return_value="/usr/bin/claude"), contextlib.redirect_stdout(out):
            cli.main(["doctor", "--json"])
        data = json.loads(out.getvalue())
        self.assertEqual(set(data), {"ready", "codes", "live", "warnings", "items"})
        self.assertIn("dispatch-path", {i["name"] for i in data["items"]})
        self.assertEqual(set(data["items"][0]), {"name", "required", "tested", "result", "detail", "age"})

    def test_cli_prints_one_line_per_item_and_no_ready_when_untested(self):
        out = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), mock.patch.object(doctor, "dispatch_path_probe", return_value=False), \
             mock.patch("shutil.which", return_value="/usr/bin/claude"), contextlib.redirect_stdout(out):
            code = cli.main(["doctor"])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 1)
        self.assertNotEqual(lines[0], "READY")
        self.assertIn("dispatch-path", lines[0])
        self.assertTrue([ln for ln in lines if ln.startswith("dispatch-path: could-not-test")])
        self.assertTrue([ln for ln in lines if ln.startswith("claude-cli: pass (now)")])


class DoctorRecordTest(ItemsBase):
    git = True

    def test_record_basis_carries_age_and_not_verified_now(self):
        old = time.time() - 3 * 3600 - 60
        record = self.paths.state / "source-git.json"
        os.utime(record, (old, old))
        report = check_install(self.paths, models=[], **UP)
        item = _item(report, "install-match")
        self.assertEqual(item.tested, "record")
        self.assertGreaterEqual(item.age, 3 * 3600)
        text = "\n".join(doctor.item_lines(report))
        self.assertIn("not verified now", text)
        self.assertIn("age 3h", text)
        self.assertTrue(report.ready)  # install-match is not a required item

    def test_age_format_uses_the_largest_whole_unit(self):
        self.assertEqual([doctor.format_age(s) for s in (5, 59, 60, 3599, 3600, 3 * 3600 + 5, 86400, 2 * 86400 + 3)],
                         ["age 5s", "age 59s", "age 1m", "age 59m", "age 1h", "age 3h", "age 1d", "age 2d"])

    def test_uncommitted_source_edit_warns_and_keeps_d82_and_ready(self):
        (self.source / "agents_inc" / "models.json").write_text('{"x": 1}')
        report = check_install(self.paths, models=[], **UP)
        self.assertIn("WB_SOURCE_UNCOMMITTED", report.warnings)
        self.assertNotIn("INSTALL_STALE", report.warnings)  # D82: uncommitted edits do not make the install stale
        self.assertTrue(report.ready)
        self.assertEqual(report.codes, ())

    def test_clean_source_has_no_uncommitted_warning(self):
        self.assertNotIn("WB_SOURCE_UNCOMMITTED", check_install(self.paths, models=[], **UP).warnings)


if __name__ == "__main__":
    unittest.main()
