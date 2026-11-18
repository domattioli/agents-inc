"""Spec 047: doctor trusts the Codex catalog only when its client_version matches the installed CLI; reports pins the
catalog lacks and outdated host CLIs; session start spawns no process and opens no socket. Offline."""
import argparse
import json
import os
import socket
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")

from agents_inc.install import catalog, cli, doctor, host_cli
from agents_inc.install.doctor import check_install
from agents_inc.install.paths import InstallPaths

HOST = {"which": lambda *a, **k: "/usr/bin/claude", "sandbox_probe": lambda: True, "net_probe": lambda: True}
ALIASES = {"astra": "gpt-6-astra", "sol": "gpt-6-sol"}
ROW = {"visibility": "list", "supported_in_api": True, "supported_reasoning_levels": [{"effort": "low"}]}
MODELS = [dict(ROW, slug="gpt-6-astra"), dict(ROW, slug="gpt-6.2-astra"), dict(ROW, slug="gpt-6-sol")]
UPDATE = "npm install -g @openai/codex@latest"


class CatalogWarningsTest(unittest.TestCase):
    def test_foreign_cache_suppresses_drift_and_names_update_then_debug_models(self):  # SC-001
        out = doctor._catalog_warnings(MODELS, "foreign", "0.170.0", "0.159.2", UPDATE, ALIASES)
        self.assertFalse([w for w in out if w.startswith("MODEL_DRIFT")])
        self.assertEqual(len(out), 1)
        self.assertIn("CODEX_CATALOG_FOREIGN", out[0])
        self.assertIn("codex 0.170.0", out[0]); self.assertIn("installed 0.159.2", out[0])
        self.assertLess(out[0].index(UPDATE), out[0].index("codex debug models"))

    def test_matching_cache_drift_and_missing_pin(self):  # SC-002
        out = doctor._catalog_warnings(MODELS, "match", "0.159.2", "0.159.2", UPDATE,
                                       {"astra": "gpt-6.2-astra", "sol": "gpt-5-sol"})
        miss = [w for w in out if w.startswith("PIN_NOT_IN_CATALOG sol")]
        self.assertEqual(len(miss), 1)
        self.assertIn("pin absent or unusable in the matching local catalog; runtime availability not verified", miss[0])  # H5
        self.assertNotIn("will fail", miss[0])
        self.assertIn(UPDATE, miss[0]); self.assertIn("agents-inc models bump sol", miss[0])
        self.assertFalse([w for w in out if "astra" in w])
        out = doctor._catalog_warnings(MODELS, "match", "0.159.2", "0.159.2", UPDATE, ALIASES)
        self.assertEqual(out, ["MODEL_DRIFT astra: pinned gpt-6-astra, newest gpt-6.2-astra"])

    def test_unknown_makes_no_claim_and_says_why(self):  # H1 (overrides clarify Q3)
        out = doctor._catalog_warnings(MODELS, "unknown", None, None, UPDATE, {"astra": "gpt-6-astra", "sol": "gpt-5-sol"})
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("CODEX_CATALOG_UNCHECKED"))
        self.assertIn("catalog version unknown", out[0])
        self.assertFalse([w for w in out if w.startswith(("MODEL_DRIFT", "PIN_NOT"))])

    def test_no_record_makes_no_claim(self):  # H1 + B1: session start without a fresh record prints nothing
        self.assertEqual(doctor._catalog_warnings(MODELS, None, None, None, UPDATE, ALIASES), [])


class ReviewFindingsTest(unittest.TestCase):
    def test_unreadable_matching_catalog_makes_no_pin_claim(self):  # G4 as refined by H2
        out = doctor._catalog_warnings(None, "match", "0.1.0", "0.1.0", UPDATE, ALIASES)
        self.assertFalse([w for w in out if w.startswith(("PIN_NOT", "MODEL_DRIFT"))])
        self.assertTrue(out and "not checked" in out[0])

    def test_empty_matching_catalog_means_pins_missing(self):  # H2
        out = doctor._catalog_warnings([], "match", "0.1.0", "0.1.0", UPDATE, ALIASES)
        self.assertEqual(sorted(w.split()[0] + " " + w.split()[1] for w in out),
                         ["PIN_NOT_IN_CATALOG astra:", "PIN_NOT_IN_CATALOG sol:"])


class CheckInstallHostCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raw = Path(self.tmp.name)
        source = raw / "source"
        (source / "agents_inc").mkdir(parents=True)
        (source / "agents_inc" / "models.json").write_text("{}")
        for name in ("workerbee", "codex-bridge"):
            (source / "skills" / name).mkdir(parents=True)
            (source / "skills" / name / "SKILL.md").write_text("x")
        scripts = source / "skills/codex-bridge/scripts"; scripts.mkdir(parents=True)
        (scripts / "at_route.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        self.home = raw / "home"; (self.home / ".claude").mkdir(parents=True)
        self.paths = InstallPaths.for_home(self.home)
        args = argparse.Namespace(source=str(source), adopt_existing_workerbee=False, without_codex=True, no_host_wiring=False, yes=True)
        with mock.patch.object(cli, "_paths", return_value=self.paths):
            self.assertEqual(cli.install(args), 0)
        self.cache = raw / "models_cache.json"
        self.cache.write_text(json.dumps({"client_version": "0.170.0", "models": MODELS}))
        self.bin = raw / "bin"; self.bin.mkdir()
        exe = self.bin / "codex"
        exe.write_text("#!/bin/sh\necho 'codex-cli 0.159.2'\n"); exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

        env = mock.patch.dict(os.environ); env.start(); self.addCleanup(env.stop)
        os.environ.pop("AGENTS_INC_NO_UPDATE_CHECK", None)  # live path under test; fetch and PATH are injected

    def tearDown(self): self.tmp.cleanup()

    def test_opt_out_makes_live_doctor_read_only(self):
        os.environ["AGENTS_INC_NO_UPDATE_CHECK"] = "1"
        def forbid(*a, **k): raise AssertionError("opt-out must not spawn or fetch")
        with mock.patch.object(host_cli, "installed_version", forbid):
            check_install(self.paths, catalog_path=self.cache, live_versions=True, version_fetch=forbid,
                          version_path=str(self.bin), **HOST)

    def test_no_host_cli_is_not_tested(self):  # G3
        report = check_install(self.paths, catalog_path=self.cache, live_versions=True,
                               version_fetch=lambda p: "0.170.0", version_path=str(self.tmp.name) + "/empty", **HOST)
        item = [i for i in report.items if i.name == "host-cli-version"][0]
        self.assertEqual((item.tested, item.result), ("not-tested", "could-not-test"))
        self.assertIn("no host CLI found", item.detail)

    def test_reused_record_is_labelled_record_with_age(self):  # G3
        check_install(self.paths, catalog_path=self.cache, live_versions=True,
                      version_fetch=lambda p: "0.170.0", version_path=str(self.bin), **HOST)
        def forbid(p): raise AssertionError("fresh record: no second lookup")
        report = check_install(self.paths, catalog_path=self.cache, live_versions=True,
                               version_fetch=forbid, version_path=str(self.bin), **HOST)
        item = [i for i in report.items if i.name == "host-cli-version"][0]
        self.assertEqual((item.tested, item.result), ("record", "pass"))
        self.assertIsNotNone(item.age)

    def test_opt_out_values_follow_one_rule(self):  # G6
        for value in ("1", "true", "yes"):
            with self.subTest(value=value):
                os.environ["AGENTS_INC_NO_UPDATE_CHECK"] = value
                def forbid(*a, **k): raise AssertionError("opted out")
                with mock.patch.object(host_cli, "installed_version", forbid):
                    check_install(self.paths, catalog_path=self.cache, live_versions=True, version_fetch=forbid,
                                  version_path=str(self.bin), **HOST)
        os.environ["AGENTS_INC_NO_UPDATE_CHECK"] = "0"
        report = check_install(self.paths, catalog_path=self.cache, live_versions=True,
                               version_fetch=lambda p: "0.170.0", version_path=str(self.bin), **HOST)
        self.assertTrue([i for i in report.items if i.name == "host-cli-version"])

    def test_live_doctor_foreign_cache_and_outdated(self):
        with mock.patch.object(doctor, "MODEL_ALIASES", ALIASES):
            report = check_install(self.paths, catalog_path=self.cache, live_versions=True,
                                   version_fetch=lambda pkg: "0.170.0", version_path=str(self.bin), **HOST)
        self.assertFalse([w for w in report.warnings if w.startswith("MODEL_DRIFT")])
        self.assertTrue([w for w in report.warnings if w.startswith("CODEX_CATALOG_FOREIGN")])
        self.assertTrue([w for w in report.warnings if w.startswith("HOST_CLI_OUTDATED codex 0.159.2 < 0.170.0")])
        self.assertNotIn("HOST_CLI_OUTDATED", " ".join(report.codes))
        rec = json.loads((self.paths.state / host_cli.RECORD).read_text())
        self.assertEqual(rec["codex"]["installed"], "0.159.2")

    def test_offline_live_returns_could_not_check_line_with_reason(self):  # H4: repair prints warnings only
        def boom(pkg): raise OSError("offline")
        warnings = doctor.cli_warnings(self.paths, catalog_path=self.cache, live=True, fetch=boom, path=str(self.bin))
        line = [w for w in warnings if w.startswith("HOST_CLI_VERSION codex: could-not-check")]
        self.assertEqual(len(line), 1)
        self.assertIn("offline", line[0])

    def test_failed_version_probe_is_reported(self):  # H4
        exe = self.bin / "codex"; exe.write_text("#!/bin/sh\necho garbage\n")
        warnings = doctor.cli_warnings(self.paths, catalog_path=self.cache, live=True, fetch=lambda p: "0.170.0", path=str(self.bin))
        self.assertTrue([w for w in warnings if w.startswith("HOST_CLI_VERSION codex: could-not-check") and "--version" in w])

    def test_live_doctor_offline_could_not_check(self):
        def boom(pkg): raise OSError("offline")
        report = check_install(self.paths, catalog_path=self.cache, live_versions=True,
                               version_fetch=boom, version_path=str(self.bin), **HOST)
        item = [i for i in report.items if i.name == "host-cli-version"]
        self.assertEqual([(i.result, i.required) for i in item], [("could-not-test", False)])
        self.assertNotIn("host-cli-version", report.untested)  # never blocks READY

    def test_session_start_path_spawns_nothing_and_uses_record(self):
        check_install(self.paths, catalog_path=self.cache, live_versions=True,
                      version_fetch=lambda p: "0.170.0", version_path=str(self.bin), **HOST)
        def forbid(*a, **k): raise AssertionError("session start must not spawn or connect")
        with mock.patch.object(doctor, "MODEL_ALIASES", ALIASES), \
             mock.patch.object(host_cli, "installed_version", forbid), mock.patch.object(host_cli, "_fetch", forbid), \
             mock.patch.object(subprocess, "run", forbid), mock.patch.object(subprocess, "Popen", forbid), \
             mock.patch.object(socket, "socket", forbid), mock.patch.object(socket, "create_connection", forbid):
            warnings = doctor.cli_warnings(self.paths, catalog_path=self.cache, live=False, path=str(self.bin))
        self.assertTrue([w for w in warnings if w.startswith("HOST_CLI_OUTDATED codex")])
        self.assertTrue([w for w in warnings if w.startswith("CODEX_CATALOG_FOREIGN")])

    def _record_via_doctor(self):
        check_install(self.paths, catalog_path=self.cache, live_versions=True,
                      version_fetch=lambda p: "0.170.0", version_path=str(self.bin), **HOST)
        rec = json.loads((self.paths.state / host_cli.RECORD).read_text())
        for r in rec.values(): r["checked_at"] = time.time() - 30 * 86400  # 30 days old
        (self.paths.state / host_cli.RECORD).write_text(json.dumps(rec))

    def _session_start(self):
        def forbid(*a, **k): raise AssertionError("session start must not spawn or connect")
        with mock.patch.object(doctor, "MODEL_ALIASES", ALIASES), \
             mock.patch.object(subprocess, "run", forbid), mock.patch.object(subprocess, "Popen", forbid), \
             mock.patch.object(socket, "socket", forbid), mock.patch.object(socket, "create_connection", forbid):
            return doctor.cli_warnings(self.paths, catalog_path=self.cache, live=False, path=str(self.bin))

    def test_retargeted_symlink_gives_stale_line_and_no_verdict(self):  # L1
        self.cache.write_text(json.dumps({"client_version": "0.159.2", "models": MODELS}))
        real = Path(self.tmp.name) / "real"; real.mkdir()
        old = real / "codex-old"; (self.bin / "codex").rename(old)
        new = real / "codex-new"; new.write_text("#!/bin/sh\necho 'codex-cli 0.170.0'\n"); new.chmod(0o755)
        (self.bin / "codex").symlink_to(old)
        self._record_via_doctor()
        (self.bin / "codex").unlink(); (self.bin / "codex").symlink_to(new)
        warnings = self._session_start()
        self.assertFalse([w for w in warnings if w.startswith(("MODEL_DRIFT", "PIN_NOT"))])
        self.assertEqual(len([w for w in warnings if w.startswith("HOST_CLI_RECORD_STALE codex")]), 1)

    def test_no_record_line_absent_when_codex_not_installed(self):  # L3 follow-up: Codex is optional
        empty = Path(self.tmp.name) / "empty"; empty.mkdir()
        with mock.patch.object(doctor, "MODEL_ALIASES", ALIASES):
            for kw in ({"path": str(empty)}, {"path": str(self.bin), "codex_installed": False}):
                with self.subTest(**kw):
                    warnings = doctor.cli_warnings(self.paths, catalog_path=self.cache, live=False, **kw)
                    self.assertFalse([w for w in warnings if "no host CLI record" in w])

    def test_no_record_line_absent_on_live_run(self):  # L3 follow-up: doctor and repair just wrote the record
        with mock.patch.object(doctor, "MODEL_ALIASES", ALIASES):
            warnings = doctor.cli_warnings(self.paths, catalog_path=self.cache, live=True,
                                           fetch=lambda p: "0.170.0", path=str(self.bin))
        self.assertFalse([w for w in warnings if "no host CLI record" in w])

    def test_no_codex_record_says_catalog_not_checked(self):  # L3
        warnings = self._session_start()
        self.assertEqual([w for w in warnings if w.startswith("CODEX_CATALOG_UNCHECKED")],
                         ["CODEX_CATALOG_UNCHECKED: catalog not checked, no host CLI record; run agents-inc doctor"])

    def test_old_record_unchanged_binary_still_gives_verdicts(self):  # K1
        self.cache.write_text(json.dumps({"client_version": "0.159.2", "models": MODELS}))
        self._record_via_doctor()
        self.assertIn("MODEL_DRIFT astra: pinned gpt-6-astra, newest gpt-6.2-astra", self._session_start())

    def test_changed_binary_says_run_doctor_and_no_drift(self):  # K1
        self.cache.write_text(json.dumps({"client_version": "0.159.2", "models": MODELS}))
        self._record_via_doctor()
        os.utime(self.bin / "codex", (5, 5))
        warnings = self._session_start()
        self.assertFalse([w for w in warnings if w.startswith(("MODEL_DRIFT", "PIN_NOT"))])
        self.assertEqual([w for w in warnings if "agents-inc doctor" in w and w.startswith("HOST_CLI_RECORD_STALE codex")].__len__(), 1)

    def test_identity_less_record_gives_stale_line(self):  # L1: no 24 h grace for old-format records
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / host_cli.RECORD).write_text(json.dumps(
            {"codex": {"installed": "0.159.2", "latest": "0.170.0", "checked_at": time.time()}}))
        warnings = self._session_start()
        self.assertFalse([w for w in warnings if w.startswith(("MODEL_DRIFT", "PIN_NOT", "HOST_CLI_OUTDATED"))])
        self.assertEqual(len([w for w in warnings if w.startswith("HOST_CLI_RECORD_STALE codex")]), 1)


if __name__ == "__main__":
    unittest.main()
