<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-06 skill=speckit-implement repo=agents_Inc session=c5e2753c -->
# Data model: Opus terminal demo

## Demo prompt (`tools/demo/PROMPT.md` -> `<stamp>/prompt.txt`)
- Fields:
  - placeholders `{TRIAL}`, `{SLOTS_BUILD}`, `{SLOTS_REVIEW}`, `{BUILD_MODEL}`, `{FREE_STATUS}`, `{BEAT6}`;
  - three `BEAT n` instructions (revised 2026-11-07);
  - the `vendor gate:` line;
  - a 14-element block for Agent-tool calls (P8).
- Rules: plain English output lines; no `NEEDS` markers left after substitution; build model is luna or haiku; `{BEAT6}` is either the task or `SKIP: <reason>`.

## Runner script (`tools/demo/opus_demo.py`)
- Inputs: `--root`, `--dry-run`, `--no-record`; injectable `doctor_text`, `which` (for tests).
- Outputs: the stamp folder (below), a printed checklist and prompt, and exit codes: 0 ok, 2 doctor not READY, 3 setup error.
- State `demo.json`:
  - `stamp`, `doctor_ready`, `luna_type`, `codex`, `mod_installed`, `sandbox_exclude_ok`;
  - `free`: map provider to yes, maybe or no;
  - `build_model`, `recorded`, `cast`, `gif`.

## Run directory (`<stamp>/`, runner-owned)
- `trial/SPEC.md` (only the fixture file), `slots-build.json`, `slots-review.json`, `prompt.txt`, `demo.json`, `demo.cast`, `demo.gif`.
- Invariant: no `hidden` path anywhere under `trial/` (FR-003).
- The dispatch run dir is separate and owned by agents-inc. It holds `prompt.md`, `run.json`, `events.jsonl`, `stdout.md`, `usage.json` [verified spec 030 Key Entities; spec 027 FR-001,FR-006]. Its path is printed in the status line `out=` [verified dispatch.py:1088].

## Slots file (JSON)
- Required keys: ROLE, TASK, CONSTRAINTS, OUT_OF_SCOPE, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE, FAILURE_GATE, GATES [verified QUICKREF.md:32].
- Lint rule found in implement: SUCCESS_GATE and FAILURE_GATE each need at least one backticked command on the line, or the lint reports `NON-COMPLIANT missing: [3]`. The dry run also snapshots the git tree, so `--root` must be a git repo with one commit [verified T034, 2026-11-06].
- Build GATES: `[{"argv":["python3","-m","unittest","discover","-s","tests"],"cwd":".scratch/demo-030/<stamp>/trial","timeout_s":120,"expect_rc":0}]`. Every gate object carries `expect_rc` explicitly: dispatch indexes `g["expect_rc"]` [inferred agents_inc/install/dispatch.py:1003; T034 confirms].
- Review GATES: `[{"argv":["test","-s","REVIEW.md"],"cwd":"<same>","timeout_s":30,"expect_rc":0}]` (a plain argv avoids the `danger` regex on inline Python).
- Rule: gate cwd must resolve inside `--cwd` [verified dispatch.py:1238-1239].

## Ledger row (agents-inc owned)
- Dispatch row fields: `id`=`run_id`, `model`, `tier`, `task`, `provider`, `status` (`dispatched`), `effort` and others [verified host_ledger.py:113-132].
- Transition: `dispatched` -> `verified` by `ledger append --node-id <id> --verdict pass|fail` [verified host_ledger.py:224-226,277]; done for the build run and the review run.
- Native luna rows carry `source: native-luna` [verified D69 Q2].

## Cast file (`demo.cast`, `demo.gif`)
- `demo.cast`: asciinema v2 recording of the whole claude session.
- `demo.gif`: `agg` export. It is absent when agg is missing (NOTE printed).
- Lifecycle: created by the runner, kept until the operator deletes the stamp folder.
