import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")  # no PyPI request from tests

from agents_inc.install import catalog, cli
from agents_inc.install.doctor import check_install
from agents_inc.install.paths import InstallPaths
from agents_inc.install.receipt import InstallReceipt
from agents_inc.install.runtime import MODEL_ALIASES

CATALOG_DIR = Path(__file__).parent / "fixtures/catalog"
HOST = {"which": lambda *a, **k: "/usr/bin/claude", "sandbox_probe": lambda: True}  # results must not depend on the host


class DoctorTest(unittest.TestCase):
    def test_missing_receipt_is_not_ready(self):
        with tempfile.TemporaryDirectory() as raw:
            report = check_install(InstallPaths.for_home(Path(raw) / "home"), **HOST)
            self.assertFalse(report.ready)
            self.assertEqual(report.codes, ("WB_NOT_INSTALLED",))  # no receipt is not an untrusted release


class DoctorWarningsTest(unittest.TestCase):
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
        self.home = raw / "home"; (self.home / ".claude").mkdir(parents=True)
        self.paths = InstallPaths.for_home(self.home)
        # Fixture cache plus a sol slug newer than any plausible pin, so drift is provable whatever routing.json pins.
        cache = json.loads((CATALOG_DIR / "models_cache.json").read_text())
        cache["models"].append({"slug": "gpt-99-sol", "visibility": "list", "supported_in_api": True, "priority": 0,
                                "supported_reasoning_levels": [{"effort": "low", "description": "x"}]})
        self.codex_home = raw / "codex_home"; self.codex_home.mkdir()
        (self.codex_home / "models_cache.json").write_text(json.dumps(cache))
        self.models = catalog.load(self.codex_home / "models_cache.json")
        self.drift = f"MODEL_DRIFT sol: pinned {MODEL_ALIASES['sol']}, newest gpt-99-sol"
        args = argparse.Namespace(source=str(self.source), adopt_existing_workerbee=False, without_codex=True, no_host_wiring=False, yes=True)
        with mock.patch.object(cli, "_paths", return_value=self.paths):
            self.assertEqual(cli.install(args), 0)

    def tearDown(self): self.tmp.cleanup()

    def test_model_drift_is_a_warning_not_a_code(self):
        report = check_install(self.paths, models=self.models, **HOST)
        self.assertEqual(report.codes, ())
        self.assertTrue(report.ready)
        self.assertIn(self.drift, report.warnings)

    def test_temp_path_codex_is_warning_not_code(self):
        tmp = Path(self.tmp.name)
        codex = tmp / "bin" / "codex"; codex.parent.mkdir(); codex.write_text("#!/bin/sh\n"); codex.chmod(0o755)
        real = InstallReceipt.load(self.paths.receipt)
        stub = mock.Mock(release_hash=real.release_hash, codex_path=codex)
        with mock.patch("agents_inc.install.doctor.InstallReceipt.load", return_value=stub), \
             mock.patch("agents_inc.install.runtime.tempfile.gettempdir", return_value=str(tmp)):
            report = check_install(self.paths, models=[], **HOST)
        self.assertIn("WB_CLI_TEMP_PATH", report.warnings)
        self.assertTrue(report.ready); self.assertEqual(report.codes, ())

    def test_no_cache_means_no_drift_warning(self):
        report = check_install(self.paths, catalog_path=self.home / "missing.json", **HOST)
        self.assertFalse([w for w in report.warnings if w.startswith("MODEL_DRIFT")])

    def test_cli_text_puts_ready_first_and_warnings_after(self):
        out = io.StringIO()
        stub_bin = Path(self.tmp.name) / "stub-bin"; stub_bin.mkdir()
        (stub_bin / "claude").write_text("#!/bin/sh\nexit 0\n"); (stub_bin / "claude").chmod(0o755)
        env = {"CODEX_HOME": str(self.codex_home), "PATH": str(stub_bin) + os.pathsep + os.environ.get("PATH", "")}  # doctor needs a claude CLI; CI has none
        with mock.patch.object(cli, "_paths", return_value=self.paths), mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
            code = cli.main(["doctor"])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(lines[0], "READY")
        self.assertIn("WARNING: " + self.drift, lines[1:])
        self.assertFalse([ln for ln in lines if ln.startswith("NOTE: Codex")])  # #66: fixture has no codex, so no network note

    def test_cli_json_shape_unchanged(self):
        out = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), mock.patch.dict(os.environ, {"CODEX_HOME": str(CATALOG_DIR)}), contextlib.redirect_stdout(out):
            cli.main(["doctor", "--json"])
        self.assertEqual(set(json.loads(out.getvalue())), {"ready", "codes", "live", "warnings"})

    def test_install_stale_absent_when_checkout_matches(self):
        self.assertNotIn("INSTALL_STALE", check_install(self.paths, models=self.models, **HOST).warnings)

    def test_install_stale_present_when_checkout_changed(self):
        (self.source / "agents_inc" / "extra.txt").write_text("new")
        report = check_install(self.paths, models=self.models, **HOST)
        self.assertIn("INSTALL_STALE", report.warnings)
        self.assertEqual(report.codes, ())

    def _cli_dispatch(self, *extra):
        from agents_inc.install import dispatch
        err = io.StringIO()
        with mock.patch.object(cli, "_paths", return_value=self.paths), mock.patch.object(dispatch, "run", return_value=0) as run, \
             contextlib.redirect_stderr(err):
            code = cli.main(["dispatch", "--slots", "s.json", "--model", "haiku", *extra])
        return code, run, err.getvalue()

    def test_stale_install_refuses_dispatch_before_launch(self):
        (self.source / "agents_inc" / "extra.txt").write_text("new")
        code, run, err = self._cli_dispatch()
        self.assertEqual(code, 1)
        run.assert_not_called()
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn(f"agents-inc repair --source {self.source.resolve()}", err)

    def test_stale_install_still_renders_dry_run(self):
        (self.source / "agents_inc" / "extra.txt").write_text("new")
        code, run, _ = self._cli_dispatch("--dry-run")
        self.assertEqual(code, 0); run.assert_called_once()

    def test_fresh_install_dispatches(self):
        code, run, err = self._cli_dispatch()
        self.assertEqual(code, 0); run.assert_called_once(); self.assertNotIn("INSTALL_STALE", err)

    def test_install_stale_silent_without_record(self):
        (self.paths.state / "source-checkout").unlink()
        self.assertNotIn("INSTALL_STALE", check_install(self.paths, models=self.models, **HOST).warnings)

    def test_stale_check_writes_nothing_under_releases(self):
        before = sorted(p.name for p in self.paths.releases.iterdir())
        (self.source / "agents_inc" / "extra.txt").write_text("new")
        check_install(self.paths, models=self.models, **HOST)
        self.assertEqual(sorted(p.name for p in self.paths.releases.iterdir()), before)

    def _warnings_with_packaged_hook(self, text):
        (self.paths.state / "source-checkout").write_text("packaged\n")
        pkg = Path(self.tmp.name) / "pkg_at_route.sh"; pkg.write_text(text)
        from agents_inc.install import doctor
        with mock.patch.object(doctor.datafiles, "repo_file", return_value=pkg):
            return check_install(self.paths, models=self.models, **HOST).warnings

    def test_packaged_record_matching_hook_has_no_drift_or_stale(self):
        warnings = self._warnings_with_packaged_hook("#!/usr/bin/env bash\nexit 0\n")
        self.assertFalse([w for w in warnings if w.startswith("WB_HOOK_DRIFT")])
        self.assertNotIn("INSTALL_STALE", warnings)

    def test_packaged_record_changed_hook_warns_drift(self):
        warnings = self._warnings_with_packaged_hook("# changed\n")
        self.assertIn("WB_HOOK_DRIFT", warnings)


class SandboxExclusionTest(DoctorWarningsTest):
    """#100: warn when the Claude settings file lacks `agents-inc *` under sandbox.excludedCommands."""

    def _settings(self, data):
        path = self.home / ".claude" / "settings.json"  # keep the hooks the installer wired
        merged = {**json.loads(path.read_text()), **data}
        path.write_text(json.dumps(merged))

    def test_missing_exclusion_is_a_warning(self):
        self._settings({"sandbox": {"excludedCommands": ["gh *"]}})
        report = check_install(self.paths, models=self.models, **HOST)
        self.assertEqual(report.codes, ())
        self.assertIn("WB_SANDBOX_EXCLUDE_MISSING", report.warnings)

    def test_present_exclusion_is_silent(self):
        self._settings({"sandbox": {"excludedCommands": ["agents-inc *"]}})
        self.assertNotIn("WB_SANDBOX_EXCLUDE_MISSING", check_install(self.paths, models=self.models, **HOST).warnings)
        self._settings({"sandbox": {"excludedCommands": ["agents-inc dispatch *"]}})  # H: the narrow form counts
        self.assertNotIn("WB_SANDBOX_EXCLUDE_MISSING", check_install(self.paths, models=self.models, **HOST).warnings)
        self._settings({"sandbox": {"excludedCommands": ["agents-inc doctor *"]}})  # a non-dispatch entry does not
        self.assertIn("WB_SANDBOX_EXCLUDE_MISSING", check_install(self.paths, models=self.models, **HOST).warnings)

    def test_no_settings_file_is_silent(self):
        (self.home / ".claude" / "settings.json").unlink(missing_ok=True)
        self.assertNotIn("WB_SANDBOX_EXCLUDE_MISSING", check_install(self.paths, models=self.models, **HOST).warnings)

    def test_api_domain_missing_is_a_warning(self):
        self._settings({"sandbox": {"excludedCommands": ["agents-inc *"], "network": {"allowedDomains": ["github.com"]}}})
        report = check_install(self.paths, models=self.models, **HOST)
        self.assertEqual(report.codes, ())
        self.assertIn("WB_SANDBOX_API_DOMAIN_MISSING", report.warnings)

    def test_api_domain_present_is_silent(self):
        self._settings({"sandbox": {"network": {"allowedDomains": ["api.anthropic.com"]}}})
        self.assertNotIn("WB_SANDBOX_API_DOMAIN_MISSING", check_install(self.paths, models=self.models, **HOST).warnings)

    def test_no_settings_file_no_api_domain_warning(self):
        (self.home / ".claude" / "settings.json").unlink(missing_ok=True)
        self.assertNotIn("WB_SANDBOX_API_DOMAIN_MISSING", check_install(self.paths, models=self.models, **HOST).warnings)


if __name__ == "__main__":
    unittest.main()
