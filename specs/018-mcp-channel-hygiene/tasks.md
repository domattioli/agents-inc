---

description: "Task list for feature 018, MCP Channel Protocol Hygiene"
---
<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-tasks repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->

# Tasks: MCP Channel Protocol Hygiene (018)

**Input**: `spec.md`, `plan.md`, `research.md` in this directory.
**Prerequisites**: wave 1 after agents_Inc PR 52 merges (T001) and the R13 checks (T002); wave 2 after 017 merges (T020); FR-010 work after the canon gate (T027 to T029).

**Tests**: Required. The Lead writes each story's acceptance tests first and shows them failing on unchanged code (plan DD11).

**Organization**: by user story, split into wave 1 and wave 2 (Q5 B). US1 (P1), US2 (P1), US3 (P2), US4 (P2), then cross-cutting and polish.

## Format

`- [ ] T### [P?] [US?] Description in <path>. Model/tier. Success: <runnable check>. Failure: <condition>. Serves: FR ids.`

- Rungs come from `python3 skills/speckit-pipeline/scripts/resolve_rung.py <CLASS>` (run 2026-10-06): Orchestrator = opus (the Lead), Workhorse = sonnet or terra, Grunt = haiku or luna.
- "Lead" means the Orchestrator-rung Lead (opus) that owns the implement run. Codex reviewer = terra (Workhorse rung, other vendor, D46).
- Repo paths are relative to `/home/user/agents_Inc` and all exist at `fe37822`, except `<run-dir>/issued/` (new, created at run time, not in the repo).
- Unit test command for a single case: `python3 -m unittest tests.<module> -k <test_name>`. Full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`.
- Every failure gate also includes: any D51/D54 invariant weakened (spec Requirements preamble), any edit outside the task's named file, or any canon file edited (FR-012).

## Phase 1: Setup (gates and baseline)

- [ ] T001 Wave-1 start gate: confirm PR 52 merged; re-check every citation in plan.md "Existing code" against the merge commit; report drift to the Supervisor before T004. Report only, no file edited; reads `agents_inc/install/worker_mcp.py`, `agents_inc/install/mcp_broker.py`, `agents_inc/install/dispatch.py`, `agents_inc/install/runtime.py`. Orchestrator (opus). Success: `gh pr view 52 --json state -q .state` prints `MERGED` and the report lists each citation as matched or moved. Failure: PR not merged, or a moved citation changes a design decision. Serves: FR-001 to FR-012 (gate).
- [x] T002 Primary-source checks: read each URL in research.md R13 and write one finding line with access date under it; any mismatch goes to the Supervisor and may change an FR before code. In DomI `specs/consumers/agents_Inc/specs/018-mcp-channel-hygiene/research.md`. Orchestrator (opus). Success: `grep -c 'accessed 20' research.md` is at least 7 (one per R13 row). Failure: a URL unreachable (record it, stop wave 1 for the FRs it backs), or a fact contradicts an FR. Serves: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008, FR-009.
- [x] T003 Baseline: run `tests/test_worker_mcp.py`, `tests/test_mcp_broker.py`, `tests/test_dispatch_resume.py` and record the pass list as the SC-009 baseline. Run only. Grunt (haiku). Success: `python3 -m unittest tests.test_worker_mcp tests.test_mcp_broker tests.test_dispatch_resume` exits 0, or its failures match the pre-existing list. Failure: a new failure not in the baseline list. Serves: FR-001 to FR-012 (SC-009).

**Checkpoint**: gates passed, baseline recorded.

## Phase 2: User Story 1 - version negotiation and structured results (P1, wave 1)

**Goal**: US1. **Independent test**: `initialize` with supported, unsupported and missing versions; structured result equals text.

- [x] T004 [P] [US1] Test `test_initialize_negotiates_version` (supported `2025-06-18` and `2024-11-05` echoed; `2099-01-01`, `2026-07-28`, missing, non-string → `2025-06-18`) in `tests/test_worker_mcp.py`. Fails today because `:118-120` echoes. Orchestrator (opus). Success: the case fails on unchanged code with an assertion on the version, then passes after T007. Failure: it passes on unchanged code. Serves: FR-001.
- [x] T005 [P] [US1] Same cases as T004, plus `test_tools_list_has_output_schema_only_at_2025_06_18`, in `tests/test_mcp_broker.py`. Fails today because `:238` pins `2024-11-05`. Orchestrator (opus). Success: fails before T008, passes after. Failure: passes on unchanged code. Serves: FR-001, FR-002.
- [x] T006 [US1] Test `test_structured_result_matches_text`: at `2025-06-18`, `json.loads(content[0].text) == structuredContent` and every `outputSchema.required` key is present, for `status`, `wait` (refused path) and `answer` (refused path); at `2024-11-05`, no `structuredContent`. In `tests/test_mcp_broker.py`. Depends on T005 (same file). Orchestrator (opus). Success: fails before T008, passes after. Failure: passes on unchanged code. Serves: FR-002.
- [x] T007 [US1] Implement DD1 in `agents_inc/install/worker_mcp.py`: `SUPPORTED_VERSIONS`, negotiation, stored version; no import of `agents_inc`. Grunt (haiku). Success: `python3 -m unittest tests.test_worker_mcp -k test_initialize_negotiates_version` passes and `grep -cE '^(from|import) agents_inc' agents_inc/install/worker_mcp.py` prints 0. Failure: any existing `tests.test_worker_mcp` case fails, or an import of `agents_inc` appears. Serves: FR-001.
- [x] T008 [US1] Implement DD1 and DD2 in `agents_inc/install/mcp_broker.py`: version set, `outputSchema` on broker tools at `2025-06-18`, `structuredContent` beside the unchanged text block. Workhorse (sonnet). Success: `python3 -m unittest tests.test_mcp_broker` passes, including T005 and T006. Failure: any existing broker case changes behavior beyond tool entries gaining `outputSchema`. Serves: FR-001, FR-002.

**Checkpoint**: US1 green.

## Phase 3: User Story 2 (wave 1 part) - client limits exceed server waits (P1)

**Goal**: US2, FR-006 only. **Independent test**: read `worker_mcp.json` and the constants.

- [x] T009 [US2] Test `test_client_timeouts_exceed_server_waits`: after `_ask_channel`, the `agents_inc` entry of `worker_mcp.json` has `timeout == MCP_TOOL_TIMEOUT_SEC * 1000`; `MCP_TOOL_TIMEOUT_SEC - WAIT_SEC >= 60` and `MCP_TOOL_TIMEOUT_SEC - AWAIT_MAX_SEC >= 60`; `worker_env` output gains no key. In `tests/test_worker_mcp.py`. Fails today: no `timeout` key (`dispatch.py:262-264`). Orchestrator (opus). Success: fails before T010, passes after. Failure: passes on unchanged code. Serves: FR-006.
- [x] T010 [US2] Implement DD3 in `agents_inc/install/dispatch.py` (`_ask_channel` writes `timeout`). Grunt (haiku). Success: `python3 -m unittest tests.test_worker_mcp -k test_client_timeouts_exceed_server_waits` passes and `git diff --stat` shows only `agents_inc/install/dispatch.py`. Failure: `worker_env` or `WORKER_ENV_KEYS` changes, or any existing case fails. Serves: FR-006.
- [ ] T011 [US2] Opt-in live test `test_claude_ask_lead_survives_idle_limit` on macOS: a Claude Worker calls `ask_lead` with a stand-in server whose wait exceeds a lowered client idle limit set only through the per-server `timeout` path, and the Worker report shows the no-answer text, not an abort; records the Claude Code version and the protocol version the Claude client negotiated at `initialize` (FR-001, R1; Codex stays [assumed] until a Codex CLI is installed). In `tests/test_worker_mcp_live.py`. Orchestrator (opus). Success: `AGENTS_INC_LIVE_ASK=1 python3 -m unittest tests.test_worker_mcp_live -k test_claude_ask_lead_survives_idle_limit` passes on the operator's Mac. Failure: abort text in the report; then FR-006's macOS premise is false and goes back to the Supervisor; or no negotiated version recorded. Serves: FR-001, FR-006.

## Phase 4: User Story 3 - restart durability (P2, wave 1)

**Goal**: US3. **Independent test**: new `Broker` on the same run dir.

- [x] T012 [US3] Tests `test_issued_ids_survive_restart` (wait on 5 earlier finished ids returns results; answer and resume work after restart) and `test_unrecorded_id_still_refused` (5 never-issued ids, a symlinked `issued/` and a planted link record are refused) in `tests/test_mcp_broker.py`. Depends on T006 (same file). Orchestrator (opus). Success: fails before T013 with `unknown-request`, passes after. Failure: passes on unchanged code. Serves: FR-007.
- [x] T013 [US3] Implement DD4 in `agents_inc/install/mcp_broker.py`: `issue()`, `known()`, `O_EXCL|O_NOFOLLOW` records under `<run-dir>/issued/` (new run-time dir). Workhorse (sonnet). Success: `python3 -m unittest tests.test_mcp_broker` passes. Failure: a record written through a link, a Lead-writable path, or `run.json` counts changed. Serves: FR-007.

## Phase 5: User Story 4 (wave 1 part) - Tasks stay undeclared until proven (P2)

**Goal**: US4, FR-009. **Independent test**: capabilities and tool entries carry no Tasks keys.

- [x] T014 [P] [US4] Test `test_no_tasks_capability_declared` (no `tasks` in `initialize` capabilities, no `execution` in any tool) in `tests/test_worker_mcp.py`. Orchestrator (opus). Success: passes now and after every later task (a guard). Failure: fails at any later checkpoint. Serves: FR-009.
- [x] T015 [P] [US4] Same guard in `tests/test_mcp_broker.py`. Depends on T012 (same file). Orchestrator (opus). Success: `python3 -m unittest tests.test_mcp_broker -k test_no_tasks_capability_declared` passes now and after every later task. Failure: it fails at any later checkpoint. Serves: FR-009.
- [ ] T016 [US4] Opt-in probe `test_client_tasks_support_probe` (R12): stand-in server declaring `tasks` and `execution.taskSupport: "optional"`; one Claude Code turn and, if installed, one Codex turn; records whether a task-augmented `tools/call` arrived, client versions and date, into research.md R12. In `tests/test_mcp_broker_live.py`. Orchestrator (opus). Success: `AGENTS_INC_LIVE_MCP=1 python3 -m unittest tests.test_mcp_broker_live -k test_client_tasks_support_probe` exits 0 and research.md "R12 result" is filled. Failure: the probe declares Tasks in a production server, or leaves R12 empty. Serves: FR-009.

## Phase 6: Cross-cutting (wave 1) - encoded redaction

- [x] T017 Test `test_screen_text_redacts_encoded_forms`: a fake 20-character environment value planted as plain, base64, URL-safe base64 with and without padding, percent-encoded, lower and upper hex; none survives; plain still redacted; a value under 8 characters untouched. Uses a patched `os.environ`. In `tests/test_dispatch_resume.py`. Orchestrator (opus). Success: fails before T018 on the encoded forms, passes after. Failure: passes on unchanged code. Serves: FR-011.
- [x] T018 Implement DD5 in `agents_inc/install/dispatch.py` (`screen_text`). Grunt (haiku). Success: `python3 -m unittest tests.test_dispatch_resume -k test_screen_text_redacts_encoded_forms` passes and the 16 KiB cut stays first. Failure: any form that was redacted before is no longer redacted. Serves: FR-011.
- [x] T019 Wave-1 checkpoint: full suite and Lead review of T007, T008, T010, T013, T018 diffs. Report only. Orchestrator (opus). Success: `python3 -m unittest discover -s tests -p 'test_*.py'` shows no failure outside the baseline list. Failure: a new failure, or a reviewed diff outside its task's file. Serves: FR-001, FR-002, FR-006, FR-007, FR-009, FR-011.

**Checkpoint**: wave 1 done; may merge before 017.

## Phase 7: Wave-2 gate

- [ ] T020 Wave-2 start gate: confirm 017 merged; re-read its landed `serve`, `Channel.ask` wait, `_await` event wait and `dispatch` time limit in `agents_inc/install/worker_mcp.py` and `agents_inc/install/mcp_broker.py`; confirm they match 017 plan DD1, DD2, DD5, DD7; report drift to the Supervisor before T021. Report only. Orchestrator (opus). Success: the report names the landed functions with line numbers and "matches DD1/DD2/DD5/DD7". Failure: 017 not merged, or its design differs; then DD7 to DD10 are re-planned. Serves: FR-003, FR-004, FR-005, FR-008, FR-010 (gate).

## Phase 8: User Story 2 (wave 2 part) - blocking calls stay alive (P1)

**Goal**: US2, FR-003 to FR-005. **Independent test**: stand-in client over stdio pipes with a fake clock.

- [ ] T021 [P] [US2] Tests in `tests/test_worker_mcp.py`: `test_ping_answered_during_blocking_call` (reply within 1 s, 20 trials), `test_cancelled_notification_ends_wait` (no result line, question file kept, 20 trials), `test_progress_while_blocked` (one notice per 30 s slice, growing, none after result, no question text in any notice), `test_stdout_lines_are_whole_json`, and no `tools/call` served during `ask_lead` while `ping` is answered. Orchestrator (opus). Success: each fails before T023, passes after. Failure: one passes on unchanged code. Serves: FR-003, FR-004, FR-005.
- [ ] T022 [P] [US2] Same tests for the broker (blocked `wait`), plus `test_status_served_during_wait` and `test_answer_waits_behind_blocking_call` (017 DD7 order kept), in `tests/test_mcp_broker.py`. Orchestrator (opus). Success: fail before T024, pass after. Failure: one passes on unchanged code, or the `answer` order test passes by racing. Serves: FR-003, FR-004, FR-005.
- [ ] T023 [US2] Implement DD7 and DD8 in `agents_inc/install/worker_mcp.py` on top of 017's queue wait; no change to 017's socket, token or frames. Workhorse (sonnet). Success: `python3 -m unittest tests.test_worker_mcp` passes, including all 017 cases. Failure: any 017 case fails, an `agents_inc` import appears, or stdout lines interleave. Serves: FR-003, FR-004, FR-005.
- [ ] T024 [US2] Implement DD7 and DD8 in `agents_inc/install/mcp_broker.py` on 017's event wait; `status` inline, all else FIFO. Workhorse (sonnet). Success: `python3 -m unittest tests.test_mcp_broker` passes, including all 017 cases. Failure: `push` or `answer` runs during a blocking call (contradicts 017 DD7), or any 017 case fails. Serves: FR-003, FR-004, FR-005.

## Phase 9: User Story 4 (wave 2 part) - task state and cancel (P2)

**Goal**: US4, FR-008 and FR-010. **Independent test**: stand-in Worker through each state; cancel a sleeping stand-in.

- [ ] T025 [US4] Test `test_task_state_beside_status` (each R4 mapping row; `status` unchanged; `usage-error`, `answered` and `not-running` have none; every other `refused` reason has `rejected`) in `tests/test_mcp_broker.py`. Depends on T022 (same file). Orchestrator (opus). Success: fails before T026, passes after. Failure: passes on unchanged code. Serves: FR-008.
- [ ] T026 [US4] Implement DD9 in `agents_inc/install/mcp_broker.py`. Grunt (haiku). Success: `python3 -m unittest tests.test_mcp_broker -k test_task_state_beside_status` passes and `grep -n '"status"' agents_inc/install/mcp_broker.py` shows no rewritten status value. Failure: any existing `status` value changes. Serves: FR-008.
- [ ] T027 [US4] Canon draft (LESSON-CANDIDATE, not a file edit): D51 amendment text for a Lead-only `cancel` (amends `docs/DECISIONS.md:578`) and the DECISIONS entry for the version set, progress and cancel handling, in the run report to the Supervisor. Orchestrator (opus). Success: the report holds both drafts; `git diff --name-only -- docs/DECISIONS.md` prints nothing. Failure: `docs/DECISIONS.md` edited. Serves: FR-010, FR-012.
- [ ] T028 [US4] Cross-vendor review of the T027 drafts by a Codex reviewer (terra, Workhorse rung; D46), before sign-off. Needs a Codex CLI on the implement host. Report only. Success: a review record with verdict and findings, each finding fixed or rejected with a reason by the Lead. Failure: no Codex CLI or no Codex review, or a reviewer from the Lead's vendor; T029 to T035 do not start. Serves: FR-010, FR-012.
- [ ] T029 [US4] Operator sign-off gate on the T027 drafts as revised after T028 (operator answered Q2 directly, 2026-10-06); the CoS then commits the signed D51 amendment to `docs/DECISIONS.md`, which FR-010's merge waits for. Report only. Orchestrator (opus) relays; operator decides. Success: the run record holds the operator's sign-off line with date. Failure: no sign-off; T030 to T035 do not start. Serves: FR-010, FR-012.
- [ ] T030 [US4] Test `test_cancel_stops_running_worker` (sleeping stand-in Worker in its own process group; result `red`/`cancelled`/`canceled`; process gone within 5 s; `workers_spawned` and `resumes` unchanged; `not-running` for an idle or unknown id; a successful reply has `task_state` `canceled`) in `tests/test_mcp_broker.py`. Depends on T025 (same file) and T029. Orchestrator (opus). Success: fails before T034, passes after. Failure: passes on unchanged code. Serves: FR-010.
- [ ] T031 [P] [US4] Test `test_worker_never_sees_cancel` (Worker `tools/list` has no `cancel`) in `tests/test_worker_mcp.py`. Depends on T029. Orchestrator (opus). Success: passes now and after T034 (a guard). Failure: fails at any checkpoint. Serves: FR-010.
- [ ] T032 [US4] Implement DD10 launch side in `agents_inc/install/dispatch.py`: Claude `Popen(start_new_session=True)` plus `communicate`, the process slot, `Turn.cancel()`, red result with `reason` `cancelled` written by the turn thread. Depends on T029. Workhorse (sonnet). Success: `python3 -m unittest tests.test_dispatch_resume tests.test_dispatch_broker tests.test_worker_mcp` passes. Failure: sandbox argv, env or stdin handling changes, or a second writer of the result appears. Serves: FR-010.
- [ ] T033 [US4] Implement DD10 Codex side in `agents_inc/install/runtime.py` (`run_codex` launch at `:384` uses `Popen(start_new_session=True)` and registers the process). Depends on T032. Workhorse (sonnet). Success: `python3 -m unittest discover -s tests -p 'test_*codex*.py'` and `python3 -m unittest tests.test_dispatch_resume` pass. Failure: Codex argv or permission profile changes. Serves: FR-010.
- [ ] T034 [US4] Implement the `cancel` tool in `agents_inc/install/mcp_broker.py` (Lead only; `known`, `busy`, `turn.rid` checks; `not-running`). Also update the exact broker tool-list assertions `tests/test_mcp_broker.py::test_initialize_and_tools_list` (`:96` at `fe37822`) and `tests/test_worker_mcp.py::test_needs_lead_answer_wait_resume` (`:293`) to add `cancel` only (SC-009). Depends on T033. Workhorse (sonnet). Success: `python3 -m unittest tests.test_mcp_broker -k test_cancel_stops_running_worker` and `python3 -m unittest tests.test_worker_mcp -k test_worker_never_sees_cancel` pass, and the two updated exact-list tests pass: `python3 -m unittest tests.test_mcp_broker -k test_initialize_and_tools_list` and `python3 -m unittest tests.test_worker_mcp -k test_needs_lead_answer_wait_resume` (SC-009). Failure: Worker tool list changes, or fan-out is refunded. Serves: FR-010.
- [ ] T035 [US4] Codex cross-vendor review (terra) of the T032 to T034 diffs (irreversible process kill; D46 item 10(b)). Report only. Success: review record with every finding fixed or rejected with a reason. Failure: no Codex review before merge. Serves: FR-010.

## Phase 10: Polish

- [ ] T036 Full suite and SC check: run the suite; check SC-001 to SC-009 against the named tests. Report only. Orchestrator (opus). Success: `python3 -m unittest discover -s tests -p 'test_*.py'` has no failure outside the baseline list; each SC maps to a passing test. Failure: a new failure, or an SC with no passing test. Serves: FR-001 to FR-011.
- [ ] T037 Canon diff check: no canon file edited by the implementation. Run only. Grunt (haiku). Success: for each implementation commit in `<base>..HEAD`, `git show --name-only --format= <commit> -- docs/DECISIONS.md CONTEXT.md AGENTS.md 'skills/*/SKILL.md'` prints nothing, with `<base>` = the PR 52 merge commit (wave 1) and the 017 merge commit (wave 2); the CoS commit that lands the signed D51 amendment is excluded and named by hash (FR-012). Failure: any path printed for an implementation commit. Serves: FR-012.
- [ ] T038 LESSON-CANDIDATE list in the final report: the T027 drafts as signed off; `CONTEXT.md` new Task state term and amended Dispatch broker tools (`cancel`); a `skills/workerbee/QUICKREF.md` or `SKILL.md` line on `cancel` and `task_state`; each with "needs sign-off and a cross-vendor reviewer (D46)". Report only. Orchestrator (opus). Success: the report lists all four items. Failure: an item missing, or a canon file edited. Serves: FR-012.

## Dependencies and order

- Wave 1: T001, T002, T003 → US1 (T004 to T008), US2 part (T009 to T011), US3 (T012, T013), US4 part (T014 to T016), cross-cutting (T017, T018) → T019. The stories in wave 1 are independent except for shared test files (T005 → T006 → T012 → T015 in `tests/test_mcp_broker.py`).
- Wave 2: T020 → US2 part (T021 to T024) → US4 part (T025, T026; then T027 draft → T028 Codex review → T029 operator sign-off → T030 to T035).
- Canon gate: no FR-010 test or code (T030 to T034) before T028 and T029.
- Polish T036 to T038 after both waves.

## Parallel examples

- Wave 1 tests: T004 (`tests/test_worker_mcp.py`), T005 (`tests/test_mcp_broker.py`) and T017 (`tests/test_dispatch_resume.py`) together.
- Wave 1 code: T007 (`worker_mcp.py`) and T010, T018 (`dispatch.py`, in sequence with each other) beside T008 (`mcp_broker.py`).
- Wave 2 tests: T021 and T022 together.

## Implementation strategy

MVP: wave 1 US1 plus T009 to T010 (FR-001, FR-002, FR-006): it fixes the version echo and the live client-abort race with small diffs. Then US3 and the redaction task. Wave 2 waits for 017.

## FR to task map

| FR | Tasks |
|---|---|
| FR-001 | T001, T002, T004, T005, T007, T008, T011, T019 |
| FR-002 | T002, T005, T006, T008, T019 |
| FR-003 | T002, T020, T021, T022, T023, T024 |
| FR-004 | T002, T021, T022, T023, T024 |
| FR-005 | T002, T021, T022, T023, T024 |
| FR-006 | T009, T010, T011, T019 |
| FR-007 | T012, T013, T019 |
| FR-008 | T002, T025, T026 |
| FR-009 | T002, T014, T015, T016, T019 |
| FR-010 | T027, T028, T029, T030, T031, T032, T033, T034, T035 |
| FR-011 | T017, T018, T019 |
| FR-012 | T027, T028, T029, T037, T038 |

## Wave 1 implementation record (2026-10-06)

Done in agents_Inc `21e4820` on `development` (part of PR 52). Operator ruling 2026-10-06: wave 1 goes in now, inside PR 52, which overrides the T001 start gate ("after PR 52 merges"); T001 is therefore not ticked.

- T002: primary sources read from the spec GitHub repositories (research.md R13 findings); the wave-1 facts hold; two wave-2 mismatches recorded.
- T003: baseline 62 tests OK in the three modules; full suite baseline 1029 tests with 8 environmental failures (root user readonly checks, 5 import errors).
- Tests (Supervisor, opus, as Lead): T004, T005, T006, T009, T012, T014, T015, T017, plus two review tests (`test_structured_content_only_when_it_conforms`, `test_worker_server_stays_self_contained`) and `test_screen_text_cuts_before_redacting`. Every feature test failed first on `fe37822`.
- Code: T007, T010, T018 by haiku (Grunt); T008, T013 by sonnet (Workhorse). Supervisor review sent back two MCP-conformance defects (outputSchema `worker_models` type; structuredContent on non-conforming error bodies, `server/tools.mdx:314`); sonnet fixed both. Supervisor touch-ups: unused `PROTOCOL_VERSION` removed from worker_mcp.py, `screen_text` docstring, one stale comment.
- T019: full suite 1042 tests, failures identical to the baseline list.
- Not done: T011 and T016 (opt-in live checks for the operator's Mac); T001 (overridden, see above).
