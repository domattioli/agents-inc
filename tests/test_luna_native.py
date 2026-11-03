"""Spec 028: `agents-inc luna status|on|off` for the native agents-inc:luna type.

A fake HOME, receipt and Codex home only; no Codex process starts and no network is used.
"""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli, luna_native, runtime
from agents_inc.install.paths import InstallPaths
from agents_inc.install.receipt import InstallReceipt

SLUG = runtime.MODEL_ALIASES["luna"]


class _Luna(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"; self.home.mkdir()
        self.paths = InstallPaths.for_home(self.home)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home)}); env.start(); self.addCleanup(env.stop)
        os.environ.pop("AGENTS_INC_MODEL_MAP", None)
        self.codex_home = self.home / ".codex"

    def write_receipt(self, codex=True):
        codex_path = None
        if codex:
            codex_path = Path(self.tmp.name) / "codex"
            codex_path.write_text("#!/bin/sh\n"); codex_path.chmod(0o755)
        InstallReceipt("a" * 64, Path("/usr/bin/python3"), codex_path).save_atomic(self.paths.receipt)

    def write_auth(self):
        self.codex_home.mkdir(exist_ok=True)
        (self.codex_home / "auth.json").write_text("{}")

    def write_cache(self, slug=SLUG):
        self.codex_home.mkdir(exist_ok=True)
        (self.codex_home / "models_cache.json").write_text(json.dumps({"models": [{"slug": slug}]}))

    def ready(self):
        self.write_receipt(); self.write_auth(); self.write_cache()


class StatusTests(_Luna):
    def test_slug_follows_the_grunt_codex_pin(self):
        routing = json.loads((Path(runtime.__file__).resolve().parents[1] / "routing.json").read_text())
        self.assertEqual(luna_native.status(self.paths)["slug"], routing["tiers"]["grunt"]["codex"])

    def test_codex_missing_without_a_receipt_codex_path(self):
        self.write_receipt(codex=False); self.write_auth()
        report = luna_native.status(self.paths)
        self.assertEqual(report["codex"], "missing")
        self.assertFalse(report["offered"])

    def test_codex_missing_without_a_receipt(self):
        self.assertEqual(luna_native.status(self.paths)["codex"], "missing")

    def test_codex_logged_out_without_auth_json(self):
        self.write_receipt()
        report = luna_native.status(self.paths)
        self.assertEqual(report["codex"], "logged-out")
        self.assertFalse(report["offered"])

    def test_codex_ready_with_receipt_and_auth(self):
        self.write_receipt(); self.write_auth()
        self.assertEqual(luna_native.status(self.paths)["codex"], "ready")

    def test_catalog_missing_without_a_cache_entry_but_still_offered(self):
        self.write_receipt(); self.write_auth()
        report = luna_native.status(self.paths)
        self.assertEqual(report["catalog"], "missing")
        self.assertTrue(report["offered"])  # the step fails with the fix instead (FR-011)
        self.write_cache(slug="some-other-model")
        self.assertEqual(luna_native.status(self.paths)["catalog"], "missing")

    def test_everything_ready(self):
        self.ready()
        report = luna_native.status(self.paths)
        self.assertEqual({k: report[k] for k in ("offered", "codex", "catalog", "switch", "slug")},
                         {"offered": True, "codex": "ready", "catalog": "ok", "switch": "on", "slug": SLUG})
        self.assertIsInstance(report["reason"], str)

    def test_off_then_on(self):
        self.ready()
        luna_native.write_switch(self.paths, "off")
        report = luna_native.status(self.paths)
        self.assertEqual((report["offered"], report["switch"]), (False, "off"))
        self.assertIn("off", report["reason"])
        luna_native.write_switch(self.paths, "on")
        report = luna_native.status(self.paths)
        self.assertEqual((report["offered"], report["switch"]), (True, "on"))

    def test_switch_keeps_other_settings_keys(self):
        self.paths.settings.parent.mkdir(parents=True)
        self.paths.settings.write_text(json.dumps({"agent_gate": "enforce"}))
        luna_native.write_switch(self.paths, "off")
        data = json.loads(self.paths.settings.read_text())
        self.assertEqual(data, {"agent_gate": "enforce", "luna_type": "off"})
        self.assertEqual(self.paths.settings.stat().st_mode & 0o777, 0o600)

    def test_malformed_settings_are_not_clobbered(self):
        self.paths.settings.parent.mkdir(parents=True)
        self.paths.settings.write_text("{not json")
        with self.assertRaises(RuntimeError): luna_native.write_switch(self.paths, "off")
        self.assertEqual(self.paths.settings.read_text(), "{not json")

    def test_unreadable_settings_leave_the_switch_on(self):
        self.ready()
        self.paths.settings.write_text("{not json")
        self.assertEqual(luna_native.status(self.paths)["switch"], "on")

    def test_bad_switch_value_is_refused(self):
        with self.assertRaises(ValueError): luna_native.write_switch(self.paths, "maybe")


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=repo, check=True,
                   capture_output=True, env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})


class RecordTests(_Luna):
    """Spec 028 D6, FR-026: `luna begin|end` write the ledger rows and run the scope snapshot the dispatch path would."""

    def setUp(self):
        super().setUp()
        self.repo = Path(self.tmp.name) / "repo"; self.repo.mkdir()
        _git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("one\n")
        _git(self.repo, "add", "a.txt"); _git(self.repo, "commit", "-q", "-m", "init")

    def rows(self):
        ledger = self.paths.state / "host-ledger/.workerbees/ledger.jsonl"
        return [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []

    def snapshot_file(self, session="s1", agent="a1"):
        return self.paths.state / "luna-runs" / session / agent / "snapshot.json"

    def test_begin_writes_the_snapshot_outside_cwd_and_one_dispatch_row(self):
        result = luna_native.begin(self.paths, "s1", "a1", str(self.repo), "count lines")
        self.assertEqual(result, {"snapshot": "captured"})
        self.assertTrue(self.snapshot_file().is_file())
        self.assertFalse(str(self.snapshot_file()).startswith(str(self.repo)))
        self.assertEqual(self.snapshot_file().parent.stat().st_mode & 0o777, 0o700)
        (row,) = self.rows()
        self.assertEqual({k: row[k] for k in ("id", "run_id", "provider", "model", "source", "status", "task", "snapshot")},
                         {"id": "a1", "run_id": "s1", "provider": "codex", "model": SLUG, "source": "native-luna",
                          "status": "dispatched", "task": "count lines", "snapshot": "captured"})

    def test_end_with_an_untouched_tree_is_unchanged_and_leaves_the_verdict_null(self):
        luna_native.begin(self.paths, "s1", "a1", str(self.repo))
        result = luna_native.end(self.paths, "s1", "a1", "done", str(self.repo), {"input_tokens": 5, "cached_input_tokens": 2, "output_tokens": 1})
        self.assertEqual(result, {"snapshot": "unchanged", "changed": []})
        row = self.rows()[-1]
        self.assertEqual((row["id"], row["status"], row["verdict"], row["snapshot"]), ("a1", "done", None, "unchanged"))
        self.assertEqual((row["input_tokens"], row["cache_read"], row["output_tokens"]), (5, 2, 1))

    def test_end_after_an_edit_records_the_changed_path(self):
        luna_native.begin(self.paths, "s1", "a1", str(self.repo))
        (self.repo / "a.txt").write_text("two\n")
        result = luna_native.end(self.paths, "s1", "a1", "done", str(self.repo))
        self.assertEqual(result, {"snapshot": "changed:1", "changed": ["a.txt"]})
        row = self.rows()[-1]
        self.assertEqual((row["snapshot"], row["files_created"]), ("changed:1", ["a.txt"]))

    def test_outside_git_records_no_repo(self):
        plain = Path(self.tmp.name) / "plain"; plain.mkdir()
        self.assertEqual(luna_native.begin(self.paths, "s1", "a1", str(plain)), {"snapshot": "no-repo"})
        self.assertFalse(self.snapshot_file().exists())
        self.assertEqual(luna_native.end(self.paths, "s1", "a1", "failed", str(plain)), {"snapshot": "no-repo", "changed": []})
        self.assertEqual(self.rows()[-1]["status"], "failed")

    def test_a_second_end_appends_to_the_same_node_and_reverifies_against_the_spawn_snapshot(self):
        luna_native.begin(self.paths, "s1", "a1", str(self.repo))
        luna_native.end(self.paths, "s1", "a1", "done", str(self.repo))
        (self.repo / "a.txt").write_text("three\n")
        luna_native.end(self.paths, "s1", "a1", "done", str(self.repo))
        rows = self.rows()
        self.assertEqual([r["id"] for r in rows], ["a1", "a1", "a1"])
        self.assertEqual([r["snapshot"] for r in rows[1:]], ["unchanged", "changed:1"])

    def test_two_agents_in_one_repo_both_see_the_tree_change(self):
        luna_native.begin(self.paths, "s1", "a1", str(self.repo))
        luna_native.begin(self.paths, "s1", "a2", str(self.repo))
        (self.repo / "a.txt").write_text("edited by the second\n")  # which agent did it is not recorded
        for agent in ("a1", "a2"):
            self.assertEqual(luna_native.end(self.paths, "s1", agent, "done", str(self.repo)),
                             {"snapshot": "changed:1", "changed": ["a.txt"]})

    def test_end_without_a_begin_is_no_repo_not_an_error(self):
        self.assertEqual(luna_native.end(self.paths, "s9", "a9", "aborted", str(self.repo))["snapshot"], "no-repo")

    def test_bad_outcome_and_bad_ids_are_refused(self):
        with self.assertRaises(ValueError): luna_native.end(self.paths, "s1", "a1", "passed", str(self.repo))
        for session, agent in (("..", "a"), ("s", "../x"), ("", "a"), ("s/t", "a")):
            with self.subTest(session=session, agent=agent), self.assertRaises(ValueError):
                luna_native.begin(self.paths, session, agent, str(self.repo))

    def test_the_cli_prints_one_json_object_and_exits_2_on_a_bad_id(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(["luna", "begin", "--session", "s1", "--agent", "a1", "--cwd", str(self.repo)])
            bad = cli.main(["luna", "begin", "--session", "..", "--agent", "a1", "--cwd", str(self.repo)])
            end_rc = cli.main(["luna", "end", "--session", "s1", "--agent", "a1", "--cwd", str(self.repo), "--outcome", "done",
                               "--usage", '{"input_tokens": 3}'])
        self.assertEqual((rc, bad, end_rc), (0, 2, 0))
        self.assertEqual([json.loads(l) for l in out.getvalue().splitlines()],
                         [{"snapshot": "captured"}, {"snapshot": "unchanged", "changed": []}])
        self.assertIn("not a usable id", err.getvalue())
        self.assertEqual(self.rows()[-1]["input_tokens"], 3)

    def test_the_hook_ledger_row_for_the_native_type_is_skipped_and_other_types_still_recorded(self):
        from agents_inc import host_ledger
        def payload(subagent):
            return {"tool_name": "Agent", "tool_use_id": "t1", "session_id": "s1",
                    "tool_input": {"subagent_type": subagent, "description": "d"}}
        self.assertIsNone(host_ledger.dispatch_row(payload("agents-inc:luna")))
        self.assertEqual(host_ledger.dispatch_row(payload("general-purpose"))["provider"], "claude")
        self.assertIsNotNone(host_ledger.dispatch_row(payload("luna-brain:luna")))


class CliTests(_Luna):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(["luna", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_status_json_prints_one_object(self):
        self.ready()
        rc, out, _ = self.run_cli("status", "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(set(json.loads(out)), {"offered", "reason", "slug", "codex", "catalog", "switch"})

    def test_status_without_json_is_readable_and_exits_zero_when_not_offered(self):
        rc, out, _ = self.run_cli("status")
        self.assertEqual(rc, 0)
        self.assertIn("offered: no", out)

    def test_off_and_on_round_trip(self):
        self.ready()
        self.assertEqual(self.run_cli("off")[0], 0)
        self.assertFalse(json.loads(self.run_cli("status", "--json")[1])["offered"])
        self.assertEqual(self.run_cli("on")[0], 0)
        self.assertTrue(json.loads(self.run_cli("status", "--json")[1])["offered"])

    def test_status_works_before_an_install_receipt_exists(self):
        rc, out, _ = self.run_cli("status", "--json")  # the mod asks at every session start, installed or not
        self.assertEqual(rc, 0)
        self.assertFalse(json.loads(out)["offered"])


if __name__ == "__main__":
    unittest.main()
