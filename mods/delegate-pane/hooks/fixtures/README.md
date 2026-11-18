Synthetic dispatch run dirs for pane tests. Invented values; no real run copied.
Key sources in agents_inc/install/dispatch.py: run id format :202; run.json `outcome`/`reason` :1311-1321; `run_id, model, kind, cwd, effort` set on the run spec; events.jsonl line 1 `run.start` with run_id, model, kind (sink.emit in launch path); slots.json keys ROLE, TASK, MODEL (slots file the run was rendered from, skills/workerbee/slots.md).
- 20991112T120000Z-sonnet-abc123: finished, outcome green.
- 20991112T120500Z-luna-def456: running, events.jsonl and slots.json, no run.json.
- 20991101T000000Z-sonnet-old000: started before the test session; must be excluded.
