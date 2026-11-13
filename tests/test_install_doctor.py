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


class GitSourceStaleTest(unittest.TestCase):
    """#174: after a clean git install only a commit that changes a bundle path is stale; work in progress is not."""
    def git(self, *argv, cwd=None):
        import subprocess
        return subprocess.run(["git", "--no-optional-locks", "-C", str(cwd or self.source), *argv], env=self.git_env,
                              check=True, capture_output=True, text=True).stdout

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(os.path.realpath(self.tmp.name))
        # No real HOME, global or system git config reaches git, in the test helper or in the code under test:
        # source_git._run passes GIT_CONFIG_NOSYSTEM and GIT_CONFIG_GLOBAL through, so both point at nothing real.
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.raw), "XDG_CONFIG_HOME": str(self.raw / "xdg"),
                                                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(self.raw / "no-gitconfig")})
        self.env.start()
        self.git_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.git_env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(self.raw / "no-gitconfig"))
        self.source = self.raw / "source"
        (self.source / "agents_inc").mkdir(parents=True)
        (self.source / "agents_inc" / "models.json").write_text("{}")
        for name in ("workerbee", "codex-bridge"):
            (self.source / "skills" / name).mkdir(parents=True)
            (self.source / "skills" / name / "SKILL.md").write_text("x")
        (self.source / "README.md").write_text("readme\n")
        self.git("init", "-q")
        for key, value in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
            self.git("config", key, value)
        self.git("add", "-A"); self.git("commit", "-qm", "init"); self.git("tag", "v1")
        self.home = self.raw / "home"; (self.home / ".claude").mkdir(parents=True)
        self.paths = InstallPaths.for_home(self.home)

    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()

    def install(self, command="install", source=None):
        out = io.StringIO()
        argv = [command, "--source", str(source or self.source), "--yes", "--without-codex", "--no-host-wiring", "--no-mod"]
        with mock.patch.object(cli, "_paths", return_value=self.paths), contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(argv), 0)
        return out.getvalue()

    def stale(self):
        from agents_inc.install.doctor import _stale_checkout
        return _stale_checkout(self.paths, InstallReceipt.load(self.paths.receipt).release_hash)

    def release(self):
        return InstallReceipt.load(self.paths.receipt).release_hash

    def record(self):
        from agents_inc.install import source_git
        return source_git.load_record(self.paths.state)

    def commit_bundle_change(self, cwd=None):
        cwd = cwd or self.source
        (cwd / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.git("add", "-A", cwd=cwd); self.git("commit", "-qm", "more", cwd=cwd)

    def test_clean_install_then_tracked_edit_is_not_stale(self):
        self.install()
        self.assertEqual(self.record(), {"head": self.git("rev-parse", "HEAD").strip(), "clean": True, "release": self.release()})
        (self.source / "agents_inc" / "models.json").write_text('{"edited": 1}')
        self.assertIsNone(self.stale())

    def test_clean_install_then_untracked_file_is_not_stale(self):
        self.install()
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertIsNone(self.stale())

    def test_clean_install_then_bundle_commit_is_stale_and_refuses(self):
        from agents_inc.install.doctor import stale_refusal
        self.install()
        self.commit_bundle_change()
        self.assertEqual(self.stale(), self.source)
        self.assertIn(f"agents-inc repair --source {self.source}", stale_refusal(self.paths))

    def test_clean_install_then_commit_outside_bundle_is_not_stale(self):
        self.install()
        (self.source / "README.md").write_text("changed\n")
        self.git("commit", "-qam", "docs")
        self.assertIsNone(self.stale())

    def test_dirty_install_installs_work_in_progress_and_later_edit_is_stale(self):
        (self.source / "agents_inc" / "models.json").write_text('{"wip": 1}')
        out = self.install()
        self.assertEqual((self.paths.current / "agents_inc/models.json").read_text(), '{"wip": 1}')
        self.assertFalse(self.record()["clean"])
        self.assertIn("uncommitted or untracked changes in the bundle; they were installed", out)
        self.assertIsNone(self.stale())
        (self.source / "agents_inc" / "models.json").write_text('{"wip": 2}')
        self.assertEqual(self.stale(), self.source)

    def test_no_record_keeps_base_behaviour(self):
        from agents_inc.install import source_git
        self.install()
        (self.paths.state / source_git.RECORD).unlink()
        self.assertIsNone(self.stale())
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertEqual(self.stale(), self.source)

    def test_non_git_source_keeps_base_behaviour(self):
        import shutil
        shutil.rmtree(self.source / ".git")
        out = self.install()
        self.assertIsNone(self.record()); self.assertNotIn("--source", out)
        self.assertIsNone(self.stale())
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertEqual(self.stale(), self.source)

    def test_git_missing_or_failing_at_check_is_not_stale(self):
        from agents_inc.install import source_git
        self.install()
        self.commit_bundle_change()
        with mock.patch.object(source_git, "_run", side_effect=RuntimeError("git: not found")):
            self.assertIsNone(self.stale())
        with mock.patch.object(source_git, "_run", return_value=mock.Mock(returncode=128, stdout="", stderr="fatal")):
            self.assertIsNone(self.stale())

    def test_git_failing_at_install_writes_no_record_and_keeps_base_behaviour(self):
        from agents_inc.install import source_git
        self.install()  # leaves a record that the failed install must remove
        with mock.patch.object(source_git, "_run", side_effect=RuntimeError("git: not found")):
            self.install()
        self.assertIsNone(self.record())
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertEqual(self.stale(), self.source)

    def test_clean_install_not_stale_under_other_umasks(self):
        self.install()
        for mask in (0o077, 0o002, 0o022):
            old = os.umask(mask)
            try: self.assertIsNone(self.stale(), oct(mask))
            finally: os.umask(old)

    def test_linked_worktree_source(self):
        wt = self.raw / "release"
        self.git("worktree", "add", "-q", str(wt), "v1")
        self.assertTrue((wt / ".git").is_file())
        out = self.install(source=wt)
        self.assertTrue(self.record()["clean"]); self.assertNotIn("WARNING", out)
        (wt / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertIsNone(self.stale())
        self.git("add", "-A", cwd=wt); self.git("commit", "-qm", "more", cwd=wt)
        self.assertEqual(self.stale(), wt)

    def test_repair_writes_the_record(self):
        self.install()
        self.commit_bundle_change()
        self.install("repair")
        self.assertEqual(self.record(), {"head": self.git("rev-parse", "HEAD").strip(), "clean": True, "release": self.release()})
        self.assertIsNone(self.stale())

    def test_source_repo_index_and_status_unchanged(self):
        import time
        (self.source / "agents_inc" / "models.json").write_text('{"wip": 1}')
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        future = time.time() + 5
        os.utime(self.source / "skills/workerbee/SKILL.md", (future, future))  # stat change git would refresh
        index = self.source / ".git" / "index"
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        status = self.git("status", "--porcelain", "--untracked-files=all")
        self.install(); self.stale()
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), status)

    def test_record_ties_to_release(self):
        from agents_inc.install import source_git
        self.install()
        self.assertEqual(self.record()["release"], self.release())
        data = json.loads((self.paths.state / source_git.RECORD).read_text()); del data["release"]
        (self.paths.state / source_git.RECORD).write_text(json.dumps(data))  # a record from before `release`
        self.assertIsNone(self.record())

    def test_rollback_to_older_release_with_newer_head_is_stale(self):
        self.install()
        self.commit_bundle_change()
        self.install("repair")
        with mock.patch.object(cli, "_paths", return_value=self.paths): self.assertEqual(cli.main(["rollback"]), 0)
        self.assertEqual(self.stale(), self.source)  # record names the newer release: digest compare

    def test_rollback_with_head_back_at_installed_commit_is_not_stale(self):
        self.install()
        self.commit_bundle_change()
        self.install("repair")
        self.git("checkout", "-q", "v1")
        with mock.patch.object(cli, "_paths", return_value=self.paths): self.assertEqual(cli.main(["rollback"]), 0)
        self.assertIsNone(self.stale())

    def test_install_failing_after_record_is_stale_against_kept_release(self):
        from agents_inc.install import cli as cli_mod
        self.install()
        self.commit_bundle_change()
        argv = ["install", "--source", str(self.source), "--yes", "--without-codex", "--no-host-wiring", "--no-mod"]
        with mock.patch.object(cli, "_paths", return_value=self.paths), \
             mock.patch.object(cli_mod, "verify_installed", side_effect=RuntimeError("boom")), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(argv), 1)
        self.assertEqual(self.stale(), self.source)

    def test_recorded_commit_missing_uses_digest_compare(self):
        self.install()
        self.git("tag", "-d", "v1")
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.git("add", "-A"); self.git("commit", "-q", "--amend", "-m", "init")
        self.git("reflog", "expire", "--expire=now", "--all"); self.git("gc", "-q", "--prune=now")
        self.assertEqual(self.stale(), self.source)

    def test_git_removed_inside_parent_repo_uses_digest_compare(self):
        import shutil
        self.install()
        shutil.rmtree(self.source / ".git")
        self.git("init", "-q", cwd=self.raw)
        for key, value in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
            self.git("config", key, value, cwd=self.raw)
        self.git("add", "source", cwd=self.raw); self.git("commit", "-qm", "parent", cwd=self.raw)
        self.assertIsNone(self.stale())
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertEqual(self.stale(), self.source)

    def test_symlinked_source(self):
        link = self.raw / "link"; link.symlink_to(self.source)
        self.install(source=link)
        self.assertTrue(self.record()["clean"])
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertIsNone(self.stale())
        self.git("add", "-A"); self.git("commit", "-qm", "more")
        self.assertEqual(self.stale(), self.source)

    def test_optional_bundle_paths(self):
        mod = self.source / "mods" / "agents-inc"; mod.mkdir(parents=True); (mod / "a.txt").write_text("a\n")
        (self.source / "workerbees").mkdir(); (self.source / "workerbees" / "__init__.py").write_text("")
        self.git("add", "-A"); self.git("commit", "-qm", "optional"); self.git("tag", "v2")
        self.install()
        self.assertTrue((self.paths.current / "mods/agents-inc/a.txt").is_file())
        (mod / "b.txt").write_text("b\n")
        self.assertIsNone(self.stale())
        self.git("add", "-A"); self.git("commit", "-qm", "mod")
        self.assertEqual(self.stale(), self.source)

    def test_warning_for_dirty_source(self):
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        out = self.install()
        self.assertIn("they were installed", out)
        self.assertIn("git worktree add <path> <tag>", out)

    def test_dirty_warning_ignores_show_untracked_config(self):
        self.git("config", "status.showUntrackedFiles", "no")
        (self.source / "agents_inc" / "extra.py").write_text("x = 1\n")
        self.assertIn("they were installed", self.install())

    def test_note_for_untagged_head(self):
        self.commit_bundle_change()
        out = self.install()
        self.assertIn("HEAD is not on a release tag", out)
        self.assertNotIn("they were installed", out)

    def test_no_message_for_clean_tagged_source(self):
        out = self.install()
        self.assertNotIn("--source", out)


if __name__ == "__main__":
    unittest.main()
