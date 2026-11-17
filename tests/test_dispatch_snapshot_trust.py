"""022 US1: the scope gate verifies against a trusted snapshot copy the delegate cannot reach. Temp dirs only."""
from __future__ import annotations
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import cli, dispatch
from tests.test_dispatch_cli import EXAMPLE, GOOD_REPORT, assert_status_output, _git_repo


class DispatchBase(unittest.TestCase):
    """Temp git repo, fake HOME, helpers shared by the 022 dispatch test modules."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = _git_repo(self.root)
        self.runs = self.root / "runs"
        patcher = mock.patch.dict("os.environ", {"HOME": str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("AGENTS_INC_HOME_REPO", None)
        self.addCleanup(self.tmp.cleanup)
        self.state = self.root / ".local/state/agents-inc"

    def slots(self, **extra) -> Path:
        data = json.loads(EXAMPLE.read_text())
        data.setdefault("GATES", [{"argv": [sys.executable, "-c", "pass"]}])
        data.update(extra)
        path = self.root / "slots.json"
        path.write_text(json.dumps(data))
        return path

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(["dispatch", *argv])
        return rc, out.getvalue(), err.getvalue()

    def dispatch(self, fake, model="sonnet", extra=(), slots=None):
        with mock.patch.object(dispatch, "launch", side_effect=fake):
            return self.main("--slots", str(slots or self.slots()), "--model", model, "--cwd", str(self.repo),
                             "--run-dir", str(self.runs), *extra)

    def run_dir(self) -> Path:
        dirs = list(self.runs.iterdir())
        self.assertEqual(len(dirs), 1)
        return dirs[0]

    def spec(self) -> dict:
        return json.loads((self.run_dir() / "run.json").read_text())


def ok_launch(stdout=GOOD_REPORT, rc=0, stderr="", session="sess-1"):
    def fake(*a, **k):
        return {"rc": rc, "stdout": stdout, "stderr": stderr, "argv": [], "session_id": session}
    return fake


class SnapshotTrustTest(DispatchBase):
    def setUp(self):
        super().setUp()
        (self.repo / "pre.txt").write_text("before\n")  # a dirty file, so the snapshot hashes it

    def _tamper(self, edit):
        def fake(kind, model, effort, cwd, prompt, run_dir, *_, **__):
            edit(Path(run_dir))
            return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": "s1"}
        return fake

    def _assert_tampered(self, edit):
        rc, out, _ = self.dispatch(self._tamper(edit))
        self.assertEqual(rc, 1, out)
        assert_status_output(self, out)
        self.assertIn("snapshot=TAMPERED", out)
        spec = self.spec()
        self.assertEqual((spec["outcome"], spec["reason"]), ("red", "snapshot-tampered"))

    def test_edit_hash_rewrite_is_red(self):
        def edit(run_dir):
            (self.repo / "pre.txt").write_text("evil\n")
            snap = json.loads((run_dir / "snapshot.json").read_text())
            snap["sha256"]["pre.txt"] = hashlib.sha256(b"evil\n").hexdigest()
            (run_dir / "snapshot.json").write_text(json.dumps(snap))
        self._assert_tampered(edit)

    def test_porcelain_rewrite_is_red(self):
        def edit(run_dir):
            (self.repo / "evil.txt").write_text("x\n")
            snap = json.loads((run_dir / "snapshot.json").read_text())
            snap["porcelain"] += "?? evil.txt\n"
            snap["sha256"]["evil.txt"] = hashlib.sha256(b"x\n").hexdigest()
            (run_dir / "snapshot.json").write_text(json.dumps(snap))
        self._assert_tampered(edit)

    def test_deleted_snapshot_is_red(self):
        self._assert_tampered(lambda run_dir: (run_dir / "snapshot.json").unlink())

    def test_untampered_run_uses_private_copy(self):
        rc, out, _ = self.dispatch(ok_launch())
        self.assertEqual(rc, 0, out)
        spec = self.spec()
        self.assertEqual(spec["snapshot_trust"], "private")
        trust = self.state / "dispatch-runs" / spec["run_id"]
        self.assertEqual((trust / "snapshot.json").read_bytes(), (self.run_dir() / "snapshot.json").read_bytes())
        record = json.loads((trust / "trust.json").read_text())
        self.assertEqual(record["snapshot_sha256"], hashlib.sha256((trust / "snapshot.json").read_bytes()).hexdigest())
        self.assertEqual(oct(trust.stat().st_mode & 0o777), "0o700")

    def test_resume_reuses_private_copy(self):
        self.dispatch(ok_launch())
        run = self.run_dir()
        before = sorted(p.name for p in (self.state / "dispatch-runs").iterdir())
        with mock.patch.object(dispatch, "launch", side_effect=ok_launch()):
            rc, out, _ = self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(p.name for p in (self.state / "dispatch-runs").iterdir()), before)
        self.assertEqual(self.spec()["snapshot_trust"], "private")

    def test_resume_detects_tamper(self):
        self.dispatch(ok_launch())
        run = self.run_dir()
        (run / "snapshot.json").write_text("{}")
        with mock.patch.object(dispatch, "launch", side_effect=ok_launch()):
            rc, out, _ = self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs))
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.spec()["reason"], "snapshot-tampered")

    def _resume(self, run, **kw):
        with mock.patch.object(dispatch, "launch", side_effect=ok_launch()) as launch:
            rc, out, err = self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs), *kw.get("extra", ()))
        return rc, out, launch

    def test_trust_store_failure_fails_closed(self):
        calls = []

        def fake(*a, **k):
            calls.append(a)
            return ok_launch()()
        with mock.patch.object(dispatch, "_trust_path", side_effect=OSError("store unavailable")):
            rc, out, _ = self.dispatch(fake)
        self.assertEqual(rc, 1, out)
        self.assertEqual(calls, [], "delegate must not start")
        spec = self.spec()
        self.assertEqual((spec["outcome"], spec["reason"]), ("red", "snapshot-error"))
        self.assertIn("store unavailable", spec["trust_error"])
        self.assertNotEqual(spec.get("snapshot_trust"), "run-dir")

    def test_resume_run_id_mismatch_is_tampered(self):
        self.dispatch(ok_launch())
        run = self.run_dir()
        spec = self.spec()
        spec["run_id"] = "unregistered"
        (run / "run.json").write_text(json.dumps(spec))
        rc, out, launch = self._resume(run)
        self.assertEqual(rc, 1, out)
        self.assertIn("snapshot=TAMPERED", out)
        self.assertEqual(self.spec()["reason"], "snapshot-tampered")
        self.assertFalse(launch.called)

    def test_relabel_private_run_as_broker_cannot_forge_snapshot(self):
        """fable F1: the delegate sets snapshot_trust=broker, plants run_dir/trust.json and a forged snapshot.json."""
        self.dispatch(ok_launch())
        run = self.run_dir()
        (self.repo / "pre.txt").write_text("evil\n")
        snap = json.loads((run / "snapshot.json").read_text())
        snap["sha256"]["pre.txt"] = hashlib.sha256(b"evil\n").hexdigest()
        forged = json.dumps(snap).encode()
        (run / "snapshot.json").write_bytes(forged)
        (run / "trust.json").write_text(json.dumps({"schema_version": 1, "snapshot_sha256": hashlib.sha256(forged).hexdigest(),
                                                    "prompt_sha256": "x"}))
        spec = self.spec()
        spec["snapshot_trust"] = "broker"
        (run / "run.json").write_text(json.dumps(spec))
        rc, out, _ = self._resume(run)
        self.assertEqual(rc, 1, out)
        self.assertIn("snapshot=TAMPERED", out)
        self.assertEqual(self.spec()["reason"], "snapshot-tampered")
        self.assertEqual(self.spec()["snapshot_trust"], "private")

    def test_broker_claim_outside_broker_without_private_record_is_tampered(self):
        self.dispatch(ok_launch())
        run = self.run_dir()
        import shutil
        shutil.rmtree(self.state / "dispatch-runs" / run.name)
        (run / "trust.json").write_text("{}")
        spec = self.spec()
        spec["snapshot_trust"] = "broker"
        (run / "run.json").write_text(json.dumps(spec))
        rc, out, launch = self._resume(run)
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.spec()["reason"], "snapshot-tampered")
        self.assertFalse(launch.called)

    def test_run_id_mismatch_is_not_self_healing(self):
        """fable F4: run.json keeps the forged run_id and every later resume stays red."""
        self.dispatch(ok_launch())
        run = self.run_dir()
        spec = self.spec()
        spec["run_id"] = "unregistered"
        (run / "run.json").write_text(json.dumps(spec))
        for _ in range(2):
            rc, out, launch = self._resume(run)
            self.assertEqual(rc, 1, out)
            self.assertEqual(self.spec()["reason"], "snapshot-tampered")
            self.assertFalse(launch.called)
        self.assertEqual(self.spec()["run_id"], "unregistered")

    def test_forged_run_id_never_steers_the_mirror_path(self):
        home = self.root / "home-repo"
        home.mkdir()
        self.dispatch(ok_launch(), extra=("--home-repo", str(home)))
        run = self.run_dir()
        spec = self.spec()
        spec["run_id"] = "../../escaped"
        (run / "run.json").write_text(json.dumps(spec))
        with mock.patch.object(dispatch, "launch", side_effect=ok_launch()):
            self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs), "--home-repo", str(home))
        self.assertFalse((home / "specs/consumers/escaped").exists())
        self.assertFalse((home / "specs/escaped").exists())
        self.assertTrue((home / "specs/consumers/repo/runs" / run.name / "run.json").is_file())

    def test_resume_private_run_with_lost_record_is_snapshot_error(self):
        self.dispatch(ok_launch())
        run = self.run_dir()
        import shutil
        shutil.rmtree(self.state / "dispatch-runs" / run.name)
        rc, out, _ = self._resume(run)
        self.assertEqual(rc, 1, out)
        spec = self.spec()
        self.assertEqual(spec["reason"], "snapshot-error")
        self.assertEqual(spec["snapshot_trust"], "private")

    def test_legacy_run_without_private_dir_records_run_dir(self):
        self.dispatch(ok_launch())
        run = self.run_dir()
        spec = self.spec()
        import shutil
        shutil.rmtree(self.state / "dispatch-runs" / spec["run_id"])
        spec.pop("snapshot_trust")  # a legacy run.json has no snapshot_trust key
        (run / "run.json").write_text(json.dumps(spec))
        with mock.patch.object(dispatch, "launch", side_effect=ok_launch()):
            rc, out, _ = self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs))
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.spec()["snapshot_trust"], "run-dir")

    def test_dry_run_writes_no_trust_dir(self):
        rc, out, _ = self.dispatch(ok_launch(), extra=("--dry-run",))
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.state / "dispatch-runs").exists())

    def test_broker_child_writes_nothing_under_state(self):
        with mock.patch.object(dispatch, "_BROKER_SAFE_WRITES", True):
            rc, out, err = self.dispatch(ok_launch())
        self.assertFalse((self.state / "dispatch-runs").exists(), (out, err))
        spec = self.spec()
        self.assertEqual(spec["snapshot_trust"], "broker")
        self.assertTrue((self.run_dir() / "trust.json").is_file())


class MirrorPromptTest(DispatchBase):
    def test_mirrored_prompt_is_the_launched_prompt(self):
        home = self.root / "home-repo"
        home.mkdir()
        seen = {}

        def fake(kind, model, effort, cwd, prompt, run_dir, *_, **__):
            seen["prompt"] = prompt
            (Path(run_dir) / "prompt.md").write_text("FORGED\n")
            return {"rc": 0, "stdout": GOOD_REPORT, "stderr": "", "argv": [], "session_id": "s1"}
        rc, out, _ = self.dispatch(fake, extra=("--home-repo", str(home)))
        self.assertEqual(rc, 0, out)
        spec = self.spec()
        mirrored = home / "specs/consumers/repo/runs" / spec["run_id"]
        self.assertEqual((mirrored / "prompt.md").read_text(), seen["prompt"])
        self.assertEqual(json.loads((mirrored / "run.json").read_text())["run_id"], spec["run_id"])

    def test_private_run_with_lost_record_skips_prompt_mirror(self):
        home = self.root / "home-repo"
        home.mkdir()
        self.dispatch(ok_launch(), extra=("--home-repo", str(home)))
        run = self.run_dir()
        mirrored = home / "specs/consumers/repo/runs" / run.name
        launched = (mirrored / "prompt.md").read_text()
        import shutil
        shutil.rmtree(self.state / "dispatch-runs" / run.name)
        (mirrored / "prompt.md").unlink()
        (run / "prompt.md").write_text("FORGED\n")
        with mock.patch.object(dispatch, "launch", side_effect=ok_launch()):
            self.main("--resume", run.name, "--message", "go", "--run-dir", str(self.runs), "--home-repo", str(home))
        self.assertFalse((mirrored / "prompt.md").exists(), "forged prompt must not be mirrored")
        self.assertTrue(self.spec().get("mirror_error"))
        self.assertNotEqual(launched, "FORGED\n")


if __name__ == "__main__":
    unittest.main()
