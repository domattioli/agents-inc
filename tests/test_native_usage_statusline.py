"""Native step usage reaches free-model status windows once per call."""
import datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeUsageStatuslineTest(unittest.TestCase):
    def test_guest_steps_ingested_once_and_windowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = {**os.environ, "HOME": tmp}
            run = home / ".local/state/agents-inc/native-runs/codestral/s1/a1"
            run.mkdir(parents=True)
            now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
            def event(ts, body):
                return json.dumps({"ts": ts.isoformat(), "event": body}) + "\n"
            path = run / "events.jsonl"
            path.write_text(event(now, {"type": "run.start", "provider": "mistral", "slug": "codestral-latest"}) +
                            event(now, {"type": "step", "usage": {"input_tokens": 100, "cached_input_tokens": 30, "output_tokens": 20}}) +
                            event(now, {"type": "run.end", "usage": {"input_tokens": 100, "cached_input_tokens": 30, "output_tokens": 20}}))
            db = home / "usage.db"
            ingest = [sys.executable, str(ROOT / "scripts/statusline.d/ingest_usage.py"), "--db", str(db)]
            subprocess.run(ingest, env=env, check=True, capture_output=True)
            subprocess.run(ingest, env=env, check=True, capture_output=True)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute("SELECT backend, model, input_tokens, output_tokens, cache_read FROM usage").fetchall(),
                                 [("mistral", "codestral-latest", 70, 20, 30)])
            output = home / "out.json"
            collect = [sys.executable, str(ROOT / "scripts/statusline.d/collect_usage.py"), "--usage-db", str(db),
                       "--out", str(output), "--session-start", str(int(now.timestamp()) - 60), "--force"]
            subprocess.run(collect, env=env, check=True, capture_output=True)
            row = json.loads(output.read_text())["free_top4_d7"][0]
            self.assertEqual([row[k]["tokens"] for k in ("session", "h5", "d1")], [120, 120, 120])
            collect[collect.index("--session-start") + 1] = str(int(now.timestamp()) + 60)
            subprocess.run(collect, env=env, check=True, capture_output=True)
            row = json.loads(output.read_text())["free_top4_d7"][0]
            self.assertEqual([row[k]["tokens"] for k in ("session", "h5", "d1")], [0, 120, 120])

    def test_free_model_equiv_cost_is_priced_not_zero(self):
        """Free-tier usage carries a haiku-tier API-equivalent cost (config free_price_estimate); billed cost stays null."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = {**os.environ, "HOME": tmp}
            run = home / ".local/state/agents-inc/native-runs/codestral/s1/a1"
            run.mkdir(parents=True)
            now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
            body = lambda b: json.dumps({"ts": now.isoformat(), "event": b}) + "\n"
            (run / "events.jsonl").write_text(
                body({"type": "run.start", "provider": "mistral", "slug": "codestral-latest"}) +
                body({"type": "step", "usage": {"input_tokens": 1000000, "cached_input_tokens": 0, "output_tokens": 0}}))
            db = home / "usage.db"
            subprocess.run([sys.executable, str(ROOT / "scripts/statusline.d/ingest_usage.py"), "--db", str(db)], env=env, check=True, capture_output=True)
            out = home / "out.json"
            subprocess.run([sys.executable, str(ROOT / "scripts/statusline.d/collect_usage.py"), "--usage-db", str(db), "--out", str(out),
                            "--session-start", str(int(now.timestamp()) - 60), "--force"], env=env, check=True, capture_output=True)
            row = json.loads(out.read_text())["free_top4_d7"][0]
            self.assertAlmostEqual(row["session"]["equiv_cost"], 1.0)  # 1M input tokens at haiku-4-5 $1/M
            self.assertIsNone(row["session"]["cost"])


class PaceColourTest(unittest.TestCase):
    """modelpace and pacecols, extracted from scripts/statusline.sh and run in bash."""

    @staticmethod
    def _funcs():
        lines = (ROOT / "scripts/statusline.sh").read_text().splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith("PACE_SESS_FLOOR_S="))
        end = next(i for i, l in enumerate(lines) if l.startswith("modelpace(){"))
        stop = next(i for i in range(end, len(lines)) if lines[i].endswith("}}'; }"))
        return "\n".join(lines[start:stop + 1]) + "\n"

    def _run(self, call):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "f.sh"
            f.write_text(self._funcs() + call + "\n")
            return subprocess.run(["bash", str(f)], check=True, capture_output=True, text=True).stdout.split()

    def test_sess_floor_is_five_minutes_model_cells(self):
        row = "0.5 0 0 0 0 1.0 28 80 10"  # c0..c4, usd_per_day, days, hist_days, all_cost
        self.assertEqual(self._run(f'modelpace 240 600 "{row}"')[0], "NA")
        self.assertNotEqual(self._run(f'modelpace 360 600 "{row}"')[0], "NA")

    def test_sess_floor_is_five_minutes_sigma_row(self):
        # 18 values = 3 providers x (SESS 5H 1D 7D 28D ALL); each group valid for SESS
        vals = "0.5 0 0 0 5 20 " * 3
        for secs, gray in ((240, True), (360, False)):
            first = self._run(f'pacecols {secs} 600 "30,30,30" {vals}')[0]
            self.assertEqual(first == "NA", gray, first)

    def test_free_row_colours_with_rate_and_stays_gray_without(self):
        self.assertNotEqual(self._run('modelpace 3600 600 "0.5 0 0 0 0 1.0 28 80 10"')[0], "NA")   # equiv cost + pace
        self.assertEqual(self._run('modelpace 3600 600 "0.5 0 0 0 0 null null null null"')[0], "NA")  # no pace rate
        self.assertEqual(self._run('modelpace 3600 600 "0 0 0 0 0 1.0 28 80 10"')[0], "NA")           # zero equiv cost


if __name__ == "__main__":
    unittest.main()
