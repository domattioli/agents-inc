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


if __name__ == "__main__":
    unittest.main()
