import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock
from agents_inc.install import doctor
from agents_inc.install.paths import InstallPaths
from agents_inc.install.host_wiring import install_host_wiring
from agents_inc.install.receipt import InstallReceipt


class _R:
    release_hash = "h"
    def __init__(self, codex_path): self.codex_path = codex_path


def _run(codex_path, prepare=None, mod=False):
    """prepare(paths) runs before the check; mod puts the luna hooks module into the release (spec 028)."""
    with tempfile.TemporaryDirectory() as raw:
        paths = InstallPaths.for_home(Path(raw) / "home")
        rel = paths.releases / "h"; rel.mkdir(parents=True)
        if mod:
            (rel / "mods/agents-inc/hooks").mkdir(parents=True); (rel / "mods/agents-inc/hooks/luna.ts").write_text("//\n")
        if prepare: prepare(paths)
        paths.current.parent.mkdir(parents=True, exist_ok=True); paths.current.symlink_to(rel)
        for root in (paths.claude_skills, paths.codex_skills):
            root.mkdir(parents=True, exist_ok=True)
            for n in ("workerbee", "codex-bridge"): (root / n).symlink_to(rel)
        install_host_wiring(paths, InstallReceipt("a" * 64, Path("/usr/bin/python3"), None))
        with mock.patch.object(doctor.InstallReceipt, "load", return_value=_R(codex_path)), \
             mock.patch.object(doctor, "verify_bundle", return_value=True):
            report = doctor.check_install(paths, which=lambda *a, **k: "/usr/bin/claude", sandbox_probe=lambda: True)
            return (report, doctor.luna_line(paths)) if mod else report


class DoctorCodexOptionalTest(unittest.TestCase):
    def test_none_codex_is_warning_not_failure(self):
        r = _run(None)
        self.assertTrue(r.ready); self.assertEqual(r.codes, ()); self.assertEqual(r.warnings, ("WB_CLI_NOT_FOUND",))
        self.assertEqual(r.as_dict()["warnings"], ["WB_CLI_NOT_FOUND"])

    def test_recorded_missing_codex_is_failure(self):
        r = _run(Path("/nonexistent/codex"))
        self.assertFalse(r.ready); self.assertIn("WB_CLI_NOT_FOUND", r.codes); self.assertEqual(r.warnings, ())

    def test_present_executable_codex_ready(self):
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "codex"; c.write_text("#!/bin/sh\n"); c.chmod(0o755)
            with mock.patch.object(doctor, "is_temp_or_shim_path", return_value=False):
                r = _run(c)
        self.assertTrue(r.ready); self.assertEqual(r.warnings, ())

    def test_non_executable_codex_is_failure(self):
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "codex"; c.write_text("x"); c.chmod(0o644)
            r = _run(c)
        self.assertFalse(r.ready); self.assertIn("WB_CLI_NOT_FOUND", r.codes)


SLUG = doctor.MODEL_ALIASES["luna"]


def _codex_home(auth=True, cache=True, switch=None):
    def prepare(paths):
        (paths.home / ".codex").mkdir(parents=True)
        if auth: (paths.home / ".codex/auth.json").write_text("{}")
        if cache: (paths.home / ".codex/models_cache.json").write_text(json.dumps({"models": [{"slug": SLUG}]}))
        if switch:
            paths.settings.parent.mkdir(parents=True); paths.settings.write_text(json.dumps({"luna_type": switch}))
    return prepare


class DoctorLunaTypeTest(unittest.TestCase):
    """Spec 028 FR-020: the native luna type adds warnings and a status line; READY and the failure codes do not change."""

    def run_luna(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "codex"; c.write_text("#!/bin/sh\n"); c.chmod(0o755)
            with mock.patch.object(doctor, "is_temp_or_shim_path", return_value=False):
                return _run(c, _codex_home(**kw), mod=True)

    def test_ready_has_no_luna_warning(self):
        r, line = self.run_luna()
        self.assertTrue(r.ready); self.assertEqual(r.warnings, ()); self.assertEqual(line, "luna type: ready")

    def test_off_is_a_warning_and_ready_stays_true(self):
        r, line = self.run_luna(switch="off")
        self.assertTrue(r.ready); self.assertEqual(r.codes, ()); self.assertEqual(r.warnings, ("LUNA_OFF",))
        self.assertEqual(line, "luna type: off")

    def test_logged_out_codex_is_a_warning(self):
        r, line = self.run_luna(auth=False)
        self.assertTrue(r.ready); self.assertEqual(r.warnings, ("LUNA_CODEX_NOT_READY",))
        self.assertEqual(line, "luna type: unavailable (LUNA_CODEX_NOT_READY)")

    def test_missing_catalog_entry_is_a_warning(self):
        r, line = self.run_luna(cache=False)
        self.assertTrue(r.ready); self.assertEqual(r.warnings, ("LUNA_CATALOG_MISSING",))
        self.assertEqual(line, "luna type: unavailable (LUNA_CATALOG_MISSING)")

    def test_missing_codex_adds_the_not_ready_warning_beside_the_existing_one(self):
        r, line = _run(None, _codex_home(), mod=True)
        self.assertTrue(r.ready)
        self.assertEqual(r.warnings, ("LUNA_CODEX_NOT_READY", "WB_CLI_NOT_FOUND"))
        self.assertEqual(line, "luna type: unavailable (LUNA_CODEX_NOT_READY)")

    def test_a_release_without_the_mod_adds_nothing(self):
        r = _run(None, _codex_home(switch="off"))
        self.assertEqual(r.warnings, ("WB_CLI_NOT_FOUND",))

    def test_as_dict_lists_the_luna_warning(self):
        r, _ = self.run_luna(switch="off")
        self.assertEqual(r.as_dict()["warnings"], ["LUNA_OFF"])
