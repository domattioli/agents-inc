---
description: "Task list for 027 live delegate view"
---
<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-tasks repo=agents_Inc session=unknown -->

# Tasks: Live delegate view

**Input**: `specs/027-live-delegate-view/` (spec.md, plan.md, research.md)
**Tests**: required (spec FR-026, FR-027, SC-001..SC-005). Write each test task before its implementation task and see it fail first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallel-safe (different files, no open dependency)
- **[Story]**: US1 live view, US2 events on disk, US3 cancel, US4 redaction
- US2 runs before US1: the mod needs `events.jsonl` and the follower.

## Phase 1: Setup

- [x] T001 Create `fixtures/live-events/codex.jsonl` and `fixtures/live-events/claude.jsonl`: realistic event sequences per research R1/R2, each with planted fake secrets (`sk-test` + 20 chars, `ghp_` + 24 chars, `api_key=` + 12 chars), one unknown event type, one non-JSON line (FR-027)
- [x] T002 [P] Create fake executables `fixtures/live-events/fake_codex` and `fixtures/live-events/fake_claude` that print a fixture file line by line with a `FAKE_PACE` delay (default 0.5 s), honour `FAKE_SLEEP` (sleep forever, for cancel tests) and the exit code in `FAKE_RC`
- [x] T003 [P] Create expected rows `fixtures/live-events/codex.rows.txt` and `fixtures/live-events/claude.rows.txt` per plan A6 table, secrets shown as `[redacted]` (FR-014, FR-015, FR-027)
- [x] T004 [P] Create mod skeleton `mods/agents-inc/`: `.claude-plugin/plugin.json` (`name: "agents-inc"`), `.claude-plugin/marketplace.json` (`name: "agents-inc-local"`, entry `source: "./"`), `hooks/hooks.json` (`modules: ["relay.ts"]`), `tsconfig.json`, empty `hooks/relay.ts` exporting `register` (FR-017)

## Phase 2: Foundational

- [x] T005 Write `tests/test_live_events.py` for `EventSink`: envelope fields and `seq` from 1 (FR-001), file mode 0600, safe-writes mode refuses a pre-planted link (FR-008), 64 KiB cut with `"cut": true` and truncation at a small injected cap (FR-009), OSError disables the sink and reports `events_error`
- [x] T006 Implement `EventSink` in `agents_inc/install/live_events.py` (plan A1)
- [x] T007 Add `_stream_run` tests to `tests/test_live_events.py`: a fake child's lines reach `on_line` before it exits, deadline kills the group and returns rc 124 with today's timeout mark, a `BaseException` kills and reaps (FR-005)
- [x] T008 Implement `_stream_run` in `agents_inc/install/live_events.py` (plan A2)

**Checkpoint**: sink and stream runner ready.

## Phase 3: User Story 2 - Live events on disk (P1)

**Goal**: every dispatch writes `events.jsonl` live; outputs unchanged.
**Independent Test**: fake CLIs paced at 0.5 s; `events.jsonl` grows before exit; golden outputs equal.

- [x] T009 [US2] Before any dispatch change, record golden `stdout.md`, `usage.json` and verdict line for both fake CLIs with today's code into `fixtures/live-events/golden/`; add `tests/test_live_events_golden.py` comparing a fresh run to them (FR-006, SC-002)
- [x] T010 [US2] Add a parser test in `tests/test_live_events.py` that feeds `fixtures/live-events/claude.jsonl` to the R1 result parse (last `type: "result"`, then whole-stdout JSON, then raw) and asserts today's `stdout`, `session_id`, `is_error`, `usage`; mark the `--verbose` need and `result` fields as [assumed] in the test docstring until T043 confirms them (FR-003)
- [x] T011 [US2] Change `claude_argv` in `agents_inc/install/dispatch.py` to `--output-format stream-json --verbose`; update the pinned argv in `tests/test_dispatch_cli.py:246`, `tests/test_dispatch_cli.py:425`, `tests/test_dispatch_grants.py:184` (FR-003)
- [x] T012 [US2] Switch the Claude branch of `launch` in `agents_inc/install/dispatch.py` from `communicate` to `_stream_run` with the sink and the R1 parse (FR-003, FR-005)
- [x] T013 [US2] Add `on_line` to `run_codex`, `_run_with_deadline` and the no-timeout branch in `agents_inc/install/runtime.py`; `result.stdout` stays the full text (FR-004)
- [x] T014 [US2] Pass the sink's `codex` line callback from `launch` in `agents_inc/install/dispatch.py` only when the run is in json mode (non-Lead) (FR-004, FR-010)
- [x] T015 [US2] In the dispatch run path of `agents_inc/install/dispatch.py`: stderr run-dir line after mkdir (FR-007), sink creation, `run.start`, and `run.end` with the right outcome on `_finish`, `_launch_failed`, refusals after mkdir and dry run (FR-002); events never copied to `run.json` or the mirror (FR-008)
- [x] T016 [US2] Add tests in `tests/test_live_events.py`: file grows before the fake exits for both kinds, `run.end` outcomes `done`, `red`, `timeout`, `launch-failed`, `refused` (a lint refusal after mkdir), `dry-run`, Lead run lifecycle-only, mirror dest holds no `events.jsonl`, stderr run-dir line format (FR-001, FR-002, FR-007, FR-008, FR-010)
- [x] T017 [US2] Run `tests/test_live_events_golden.py` and the full suite; both green (SC-002, SC-005)

**Checkpoint**: US2 usable alone (`tail -f <run dir>/events.jsonl`).

## Phase 4: User Story 1 - Watch a delegate live (P1)

**Goal**: relay subagent transcript shows rows; Agent result is the report.
**Independent Test**: `claude plugin test mods/agents-inc` with stubbed spawns.

- [x] T018 [P] [US1] Write `tests/test_live_rows.py`: `render` of each fixture equals its `*.rows.txt`; 240/120-char cuts; unknown type and raw rows (FR-014)
- [x] T019 [US1] Implement `render` in `agents_inc/live_rows.py` (plan A6)
- [x] T020 [US1] Add `follow` tests to `tests/test_live_rows.py` with an injected clock: partial last line held, batch at 1 s or 20 rows with blank-line separators (FR-016), exit 0 after `run.end`, exit 3 with no file in 30 s (FR-013); first row printed within 2 s of the first event at 0.5 s pace (SC-001)
- [x] T021 [US1] Implement `follow` in `agents_inc/live_rows.py`
- [x] T022 [US1] Add `events follow` and `events redact` subcommands in `agents_inc/install/cli.py` with a CLI test in `tests/test_live_rows.py` (FR-013)
- [x] T023 [US1] In `mods/agents-inc/hooks/relay.ts`, `session.start` registers agent `relay` and tool `run` per FR-018/FR-019, then `next(e)`
- [x] T024 [US1] In `mods/agents-inc/hooks/relay.ts`, `tool.call` guards: no `agentId`, model outside the fixed list, free model (deny names `agent.sh`), slots missing or outside cwd realPath (FR-020)
- [x] T025 [US1] In `mods/agents-inc/hooks/relay.ts`, spawn dispatch by argv, parse the FR-007 line, spawn the follower, append each batch as a `system` notice with `agentId`, enforce the 600 cap and the 60 s held-back notice, emit `live view unavailable` when no run-dir line arrives (FR-021, FR-022)
- [x] T026 [US1] In `mods/agents-inc/hooks/relay.ts`, build the result from `stdout.md` plus the verdict line, the no-verdict fallback through `agents-inc events redact`, and the `.catch` deny (FR-023)
- [x] T027 [US1] Write `mods/agents-inc/hooks/relay.test.ts` happy path, first asserting the `session.start` registrations carry FR-018/FR-019 values: test hooks on `process.spawn` stream fake dispatch stderr/stdout and `codex.rows.txt`; assert notices arrive in order with the call's `agentId` via `mock.session(on)`, and the result text equals fixture report + verdict (spec US1 scenarios 1-2, SC-001)
- [x] T028 [US1] Add guard cases to `mods/agents-inc/hooks/relay.test.ts` (FR-020) and a no-run-dir-line case and a 600-cap case (FR-022)
- [x] T029 [US1] Add a Claude-rung case to `mods/agents-inc/hooks/relay.test.ts` using `claude.rows.txt` (spec US1 scenario 3)
- [x] T030 [US1] Run `claude plugin validate mods/agents-inc`: no refusal, `tool.call` listed, no `tool.check` hook (FR-025, FR-026)

**Checkpoint**: US1 works with stubbed spawns.

## Phase 5: User Story 3 - Cancel (P2)

- [ ] T031 [US3] Add an abort case to `mods/agents-inc/hooks/relay.test.ts`: abort `next.signal` mid-stream; both spawn loops end and `$.process.run` gets `agents-inc dispatch --cancel <run dir>` exactly once (FR-024)
- [x] T032 [US3] Implement the abort listener in `mods/agents-inc/hooks/relay.ts` (FR-024)
- [x] T033 [P] [US3] Write `tests/test_dispatch_cancel.py`: SIGTERM, SIGHUP, SIGINT each to a dispatch running `fake_codex`/`fake_claude` with `FAKE_SLEEP`; group gone within 5 s, `run.json` outcome `cancelled`, verdict `dispatch <run_id> <model> cancelled`, exit 130, last event `run.end` cancelled (FR-011, SC-004)
- [x] T034 [US3] Implement signal handlers, the `Cancelled` path and `delegate_pgid` recording via `on_start` in `agents_inc/install/dispatch.py` and `agents_inc/install/live_events.py` (FR-011, FR-012)
- [x] T035 [US3] Add `--cancel` cases to `tests/test_dispatch_cancel.py`: final outcome present, leader command mismatch, live group killed (FR-012)
- [x] T036 [US3] Implement `--cancel` in `agents_inc/install/dispatch.py` and its flag in `agents_inc/install/cli.py` (plan A5)

## Phase 6: User Story 4 - No secrets in rows (P2)

- [x] T037 [P] [US4] Add redaction tests to `tests/test_live_rows.py`: `report.SECRET_RE` matches, env-named values of 8+ chars, home to `~`, every planted fixture secret absent from rendered rows of both fixtures, `events redact` on stdin (FR-015, SC-003)
- [x] T038 [US4] Implement `redact` in `agents_inc/live_rows.py`, applied in `render` and `events redact`; import `SECRET_RE` from `agents_inc/install/report.py`, no copy (FR-015)
- [x] T039 [US4] Add a case to `mods/agents-inc/hooks/relay.test.ts`: stub dispatch stdout/stderr hold a planted secret; assert no appended notice and no result text holds it unless it came through the stubbed `events redact` (FR-023, SC-003)

## Phase 7: Polish

- [x] T040 Add `mods/agents-inc` to `ALLOWLIST` in `agents_inc/install/bundle.py:16`, copy it in `_packaged_source` in `agents_inc/install/cli.py`, include it in package data; test that a built bundle holds `mods/agents-inc/.claude-plugin/plugin.json` (FR-017)
- [x] T041 [P] Write install and permission steps (what install/repair do with the `claude plugin` CLI, `--no-mod`, manual fallback commands, allow rule for `mcp__agents-inc__run`, how to start a relay with `subagent_type: "agents-inc:relay"`) in `mods/agents-inc/README.md` and a short lite-prose section in `docs/START-HERE.md` (Q2, FR-025)
- [x] T042 Test first with a fake `claude` on PATH that records argv: `install`/`repair` run `plugin marketplace add` and `plugin install` only when the plugin is absent, skip under `--no-mod`, stay green on a failing fake; `uninstall` runs `plugin uninstall` and `marketplace remove`; `doctor` prints warning `MOD_NOT_INSTALLED` and still `READY`. Then implement in `agents_inc/install/cli.py` and the doctor module (Q2, FR-028)
- [ ] T043 Operator manual check on a real host (no delegate model calls): `claude --plugin-dir mods/agents-inc`, one `luna` and one `haiku` dispatch through the relay, click the subagent, see rows, compare the Agent result text with the tool result text and `stdout.md` (spec US1 scenario 4), stop one run, confirm with `ps` that no delegate survives; save one real Claude stream to `fixtures/live-events/claude.real.jsonl` after `agents-inc events redact`; update R1/R4 [assumed] tags in research.md
- [x] T044 Run `python3 -m unittest discover -s tests -p 'test_*.py'`, `claude plugin validate mods/agents-inc`, `claude plugin test mods/agents-inc`; all green (SC-005); add a `CHANGELOG.md` entry
- [x] T045 Draft a `docs/DECISIONS.md` entry (events.jsonl envelope, relay mod, row notices) for the CoS to land; tag LESSON-CANDIDATE in the report (canon edit, constitution P10)
- [ ] T046 Move `specs/027-live-delegate-view/` to DomI `specs/consumers/agents_Inc/` as the speckit-implement final task (repo AGENTS.md Governance)

## Dependencies

- Phase 1 -> Phase 2 -> US2 (Phase 3) -> US1 (Phase 4). US3 needs T015 and T025. US4 needs T019. Polish last.
- T009 runs before T011-T015 (golden is today's output).
- Within a story: test task before its implementation task.

## Parallel examples

- T002, T003, T004 together after T001.
- T018 alongside T009-T017 (new file, no dispatch dependency).
- T033 and T037 together once their implementations' inputs exist.

## Implementation strategy

MVP = Phases 1-3 (US2: live file) then Phase 4 (US1: live view). US3 and US4 ship in the same release; the mod is not offered to the operator before US3 and US4 pass, since a view without cancel and redaction breaks FR-011 and FR-015.
