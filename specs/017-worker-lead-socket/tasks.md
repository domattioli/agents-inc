---

description: "Task list for feature 017, Worker-Lead Socket Channel"
---
<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-10-04 skill=speckit-pipeline repo=agents_Inc session=unknown -->

# Tasks: Worker-Lead Socket Channel (017)

**Input**: `.scratch/sock/spec/spec.md`, `plan.md`, `research.md` (final home: DomI `specs/consumers/agents_Inc/017-worker-lead-socket/`)
**Prerequisites**: plan.md and spec.md (both present). D54 is on `development` at `1fcfd76`; PR 52 (`development` to `main`) must merge first (T001).

**Tests**: Required. The plan (DD12) says the Lead writes the acceptance tests first and shows them failing on unchanged code. Each story below starts with its acceptance tests. Each test task says why it fails on unchanged code.

**Organization**: Tasks are grouped by user story in priority order: US1 (P1), US2 (P1), US3 (P2), US4 (P3), US5 (P3).

## Format: `[ID] [P?] [Story] Description in <one file path>. Plan decision. FR and SC ids.`

- **[P]**: May run in parallel with the other [P] tasks of the same phase or story block, because they touch different files and have no dependency on each other.
- **[Story]**: US1 to US5.
- Each task names exactly one file path from plan.md "Project Structure" and the design decision (DD1 to DD12) it implements.
- Owners (DD12; operator ruling 2026-10-04, opus Lead over sonnet Workhorse): the Lead writes the acceptance-test tasks (each story's "Tests" block) first, writes the prompt text, and reviews every Workhorse diff. A sonnet Workhorse writes all DD1 to DD9 code in `agents_inc/install/*` and any further unit tests. A reviewer from a different vendor also reviews the trust-boundary change (T043).
- Test command for every task: `python3 -m unittest discover -s tests -p 'test_*.py'`. Tests use temp dirs and a fake HOME. No real model calls, except the opt-in live tests.

## Phase 1: Setup (start gate and baseline)

**Purpose**: Make sure the plan still matches the merged D54 code before any code is written.

- [ ] T001 Start gate: confirm PR 52 (`development` to `main`) has merged, then re-check every line citation in plan.md "Existing code" (last checked against `1fcfd76`) against the merge commit. Report only, no file edited; plan.md is read, not changed. Report any drift to the Lead before T002. Plan: start gate, DD12. Serves: gate for FR-001 to FR-016 and SC-001 to SC-011.
- [ ] T002 Record the owners in the run report: the operator ruling of 2026-10-04 (opus Lead over sonnet Workhorse; Lead writes acceptance tests first and reviews; Workhorse writes code in `agents_inc/install/*` and unit tests). Report only, no file edited. Plan: DD12. Serves: FR-014, SC-006.
- [ ] T003 Run `tests/test_worker_mcp.py`, `tests/test_mcp_broker.py`, `tests/test_dispatch_resume.py` and `tests/test_dispatch_broker.py` on the merged code and record which pass, as the SC-006 baseline. Run only, no file edited. Plan: DD12. Serves: SC-006.

**Checkpoint**: Gate passed, owners known, baseline recorded.

---

## Phase 2: Foundational (token, argument plumbing, transport record)

**Purpose**: Plumbing that every story needs. No story starts before this phase ends.

**CRITICAL**: The token file and the transport record are used by US1 to US5.

- [ ] T004 [P] Test: `runtime.worker_args` carries `--token-file <path>` for the Codex launch, in `tests/test_codex_tool_access.py`. Fails today because `worker_args` takes no `token_file` argument (`runtime.py:172-176`). Plan: DD4. Serves: FR-007.
- [ ] T005 [P] Test: the broker writes `<child>/worker_mcp.token` with mode 0600; the token value never appears in argv, the Worker prompt, `run.json` or any log; the Claude sandbox profile lists the token file in `read_ok` and gains no other path; each turn gets a new token; the request result carries `transport` and `fallback_reason`; the token value appears in 0 of `events.jsonl`, the broker log, `ask/<rid>.transport.json`, `run.json`, the request result, the Worker argv and the Worker prompt. In `tests/test_dispatch_push.py`. Fails today because no token file exists. Plan: DD4. Serves: FR-007, FR-012, FR-014, SC-005, SC-011.
- [ ] T006 [P] Test: the server started without `--token-file` runs file-only and writes `ask/<rid>.transport.json` with reason `no-token`; a token is read once and never printed. In `tests/test_worker_sock.py` (new file). Fails today because the server has no `--token-file` and no transport file. Plan: DD1. Serves: FR-005, FR-007.
- [ ] T007 [P] Add `token_file` to `worker_args` and pass `--token-file` to the Codex argv, in `agents_inc/install/runtime.py`. Plan: DD4. Serves: FR-007. Depends on T004.
- [ ] T008 [P] Add the optional `--token-file` argument, token read, `self.mode` and the `ask/<rid>.transport.json` record to `main` and `Channel`, in `agents_inc/install/worker_mcp.py`. Plan: DD1. Serves: FR-005, FR-007, FR-013. Depends on T006.
- [ ] T009 Write the token in `_ask_channel` with `secrets.token_hex(16)`: O_EXCL temp file, then rename, mode 0600, at `<child>/worker_mcp.token`. Add `--token-file` to the server args and the token file to the Claude sandbox `read_ok`. In `agents_inc/install/dispatch.py`. Plan: DD4. Serves: FR-007, FR-014, SC-005. Depends on T005.
- [ ] T010 Add `transport` (`socket` or `file`) and `fallback_reason` to `Turn` and to the request result, in `agents_inc/install/dispatch.py`. Plan: DD4. Serves: FR-012, SC-002. Depends on T009 (same file).

**Checkpoint**: Token and transport record exist. Story work can begin.

---

## Phase 3: User Story 1 - A Worker question reaches the Lead, and the answer returns, without polling (Priority: P1) MVP

**Goal**: With a healthy socket, `ask_lead` and the broker wait on doorbells, not on 2 s and 0.2 s polls. The D54 files stay the record.

**Independent Test**: Channel server plus broker stand-in under a fake HOME. Ask one question, answer it, and assert latency under 0.5 s, file parity, and no answer-file reads.

### Tests for User Story 1 (write first; they must fail on unchanged code)

- [ ] T011 [P] [US1] Test: the server binds `ask/lead.sock` by a relative name and accepts `hello` with the token; a question sends an `ask` doorbell; the answer doorbell returns `ask_lead` in under 0.5 s in 20 of 20 trials; each socket doorbell names a question or answer file that exists (SC-003); with a patched `Channel._read_answer`, the server reads each answer file exactly once, after its doorbell, and makes 0 reads while it waits (SC-004); the socket is `AF_UNIX` only and `worker_mcp.py` imports nothing from `agents_inc`. In `tests/test_worker_sock.py`. Fails today because no socket exists and `ask` polls every 2 s. Plan: DD1, DD2. Serves: FR-001, FR-002, FR-003, FR-006, FR-013, SC-001, SC-003, SC-004.
- [ ] T012 [P] [US1] Test: a broker `WorkerLink` writes the answer file before it rings the doorbell; an answer that fails the credential screen or the 64 KiB limit is refused with the D54 reason and nothing reaches the Worker; a question over 16 KiB is cut and redacted as in D54. In `tests/test_dispatch_push.py`. Fails today because no `WorkerLink` exists. Plan: DD4. Serves: FR-001, FR-004, SC-003.
- [ ] T013 [P] [US1] Test: `Broker._await` returns `needs-lead` to a blocked Lead call as soon as the question doorbell arrives, not on the next 0.2 s check; in file mode the 0.2 s poll still works. In `tests/test_mcp_broker.py`. Fails today because `_await` always sleeps `self.poll`. Plan: DD5. Serves: FR-003, SC-001.

### Implementation for User Story 1

- [ ] T014 [P] [US1] Add the channel server: bind `lead.sock` after `os.chdir(ask)` and change back, mode 0600, backlog 1; an accept thread; refuse a peer of another uid; the first frame is `hello` with the token within 5 s; the first good peer is the link; a reader thread feeds a `queue.Queue` with `answer`, `push` and `bye` frames of at most 4 KiB with the fields `op`, `rid`, `n` only. In `agents_inc/install/worker_mcp.py`. Plan: DD1. Serves: FR-002, FR-006, FR-007, FR-013, SC-005.
- [ ] T015 [US1] Change `Channel.ask` to write the question file, send the `ask` doorbell, and wait on the queue until the deadline; on an `answer` frame read the answer file once; keep the 30-minute limit and the `NO_ANSWER` text. In `agents_inc/install/worker_mcp.py`. Plan: DD2. Serves: FR-001, FR-003, SC-001, SC-004. Depends on T014 (same file).
- [ ] T016 [P] [US1] Add the `WorkerLink` class: start with the `Turn`, wait up to 30 s at 0.1 s steps for `ask/lead.sock`, connect, send `hello`, run a reader thread that sets `link.event` on `ask`; make `answer_question` ring `answer` after its file is written. `relay_question` stays unchanged. In `agents_inc/install/dispatch.py`. Plan: DD4. Serves: FR-001, FR-003, FR-004, FR-007, SC-001, SC-003.
- [ ] T017 [US1] Make `Broker._await` wait on `turn.link.event.wait(self.poll)` and clear the event after each relay check. In `agents_inc/install/mcp_broker.py`. Plan: DD5. Serves: FR-003, SC-001. Depends on T016.
- [ ] T018 [US1] Live proof (opt-in): a Claude Worker under `sandbox-exec` and a Codex Worker each bind `ask/lead.sock` and answer one question over the socket, or the result records why that vendor used files. In `tests/test_worker_mcp_live.py`. Plan: DD11. Serves: FR-003, FR-014, SC-005, SC-007. Depends on T015, T016.

**Checkpoint**: US1 works alone. Questions and answers use doorbells, with files unchanged.

---

## Phase 4: User Story 2 - Losing the socket never loses a message (Priority: P1)

**Goal**: Any socket failure falls back to the D54 files for the rest of the turn. Each message arrives exactly once.

**Independent Test**: Five fault kinds, five runs each: socket file removed, stale file with no listener, listener killed after the question, broker restart, full path over 104 bytes.

### Tests for User Story 2 (write first; they must fail on unchanged code)

- [ ] T019 [P] [US2] Test: for the five fault kinds of SC-002, 5 runs each, every question and answer arrives exactly once; a stale `lead.sock` is replaced by a resume turn; the fifth kind, a full path over 104 bytes, still binds by its short relative name or records `file` with a reason; the transport record names the transport per message; when the Lead is gone, `ask_lead` keeps the D54 limit and returns the `NO_ANSWER` text (patch `WAIT_SEC` small). In `tests/test_worker_sock.py`. Fails today because there is no socket, no stale-file handling and no transport record. Plan: DD1, DD2. Serves: FR-005, FR-006, FR-012, SC-002.
- [ ] T020 [P] [US2] Test: the first link error sets `link.mode = "file"` and records the reason; the broker uses files for the rest of the turn; a new turn tries the socket again; a path over 100 bytes connects through a mode-0700 symlink dir that is removed after connect; the startup wait gives up after 30 s and records the reason. In `tests/test_dispatch_push.py`. Fails today because `WorkerLink` does not exist. Plan: DD4. Serves: FR-005, FR-006, FR-012, SC-002.

### Implementation for User Story 2

- [ ] T021 [P] [US2] Add stale-socket handling and fallback: connect to an existing `lead.sock`; unlink it on ENOENT or ECONNREFUSED; go to file mode if a live listener exists; on any later error set `self.mode = "file"`, write the reason to `ask/<rid>.transport.json`, and resume the 2 s poll with the same deadline. In `agents_inc/install/worker_mcp.py`. Plan: DD1, DD2. Serves: FR-005, FR-006, FR-012, SC-002.
- [ ] T022 [P] [US2] Add broker fallback: any link error sets `link.mode = "file"`, closes the link, and records the reason in the `Turn`; add the symlink connect for long paths. In `agents_inc/install/dispatch.py`. Plan: DD4. Serves: FR-005, FR-006, FR-012, SC-002.
- [ ] T023 [US2] Live probe (opt-in): `connect()` through a symlink to a socket works on macOS, and a bind in a long `ask/` path works under `sandbox-exec`, or the fallback is recorded. In `tests/test_worker_mcp_live.py`. Plan: DD11. Serves: FR-006, SC-002. Depends on T018 (same file).

**Checkpoint**: US1 and US2 both work. No message is lost.

---

## Phase 5: User Story 3 - The Lead tells a running Worker something (Priority: P2)

**Goal**: The Lead pushes a short note to a running Worker. The Worker gets it from `check_lead` or attached to an `ask_lead` result.

**Independent Test**: Stand-in Worker. Push a note and assert screen, cap, file, and delivery through the next tool result, in socket mode and in file mode.

### Tests for User Story 3 (write first; they must fail on unchanged code)

- [ ] T024 [P] [US3] Test: the Worker sees exactly two tools, `ask_lead` and `check_lead`; `check_lead` returns every pending push as `[push <n> from <source>] <text>` blocks and never waits; with none pending it returns `no message from your Lead`; each carried push gets a `.seen` marker (O_EXCL); `ask_lead` attaches pending pushes after the answer; in file mode `check_lead` still finds the push file with no polling. In `tests/test_worker_mcp.py` (new cases, plus the three exact-list assertions SC-006 names: the Worker tool list in `test_only_ask_lead_is_exposed`, the `--allowedTools` value in `test_claude_worker_gets_ask_lead_server_and_sandbox_holes`, and the broker tool list in `test_needs_lead_answer_wait_resume`; change nothing else in existing cases). Fails today because the server has one tool. Plan: DD3. Serves: FR-002, FR-009, SC-006, SC-007.
- [ ] T025 [P] [US3] Test: `push_message` refuses `bad-request-id`, `bad-source`, `bad-message`, `oversize`, `credential-seeking`, `unknown-request`, `turn-ended` and `push-cap` (2 for Grunt, 5 above, shared by all sources); a good push writes the run-dir record without a body and the child `ask/<rid>.push.<n>.json`; `spec["pushes"]` counts sent, refused and delivered by source; `workers_spawned`, `resumes` and `request_counts` do not change; a file-inbox `kind: push` is handled before the busy check; `--allowedTools` includes `mcp__agents_inc__check_lead`. In `tests/test_dispatch_push.py`. Fails today because none of this exists. Plan: DD6, DD7, DD10. Serves: FR-002, FR-004, FR-008, FR-009, FR-012.
- [ ] T026 [P] [US3] Test: the broker `push` tool (source `lead`) is handled at once when no Worker call blocks; `dispatch` accepts an optional `timeout` and returns `{"status":"timeout","request_id"}` on expiry; the tool descriptions tell the Lead to call `push` or `wait` next. In `tests/test_mcp_broker.py`. Fails today because there is no `push` tool and `dispatch` has no `timeout`. Plan: DD7. Serves: FR-008, FR-016.
- [ ] T049 [US3] Test: a push sent after the stand-in Worker's last tool call shows in `run.json` as 1 sent and 0 delivered, and its D54 push file exists, in 5 of 5 trials; `delivered` is one total per request id, not split by source. In `tests/test_dispatch_push.py`. Fails today because there is no push and no `pushes` counter. Plan: DD6. Serves: FR-012, SC-010. Depends on T025 (same file). (Added at analyze cycle 2; numbered after T048 to keep earlier ids stable.)

### Implementation for User Story 3

- [ ] T027 [P] [US3] Add the `check_lead` tool (no arguments, `readOnlyHint`): scan `ask/<rid>.push.<n>.json` from `n = 1` to the first gap, return the pushes not yet carried, write `.seen` markers, send `seen` frames when the link is up; attach the same block to `ask_lead` results. In `agents_inc/install/worker_mcp.py`. Plan: DD3. Serves: FR-002, FR-009, SC-007.
- [ ] T028 [P] [US3] Add `push_message`, `push_cap`, the `pushes` counters in `init_broker_state` (delivered read from `.seen` markers at turn end, advisory), `PUSH_KEYS` for the file inbox, and the `push` doorbell after both files are written. In `agents_inc/install/dispatch.py`. Plan: DD6, DD7. Serves: FR-004, FR-008, FR-012, SC-010.
- [ ] T029 [US3] Add the `push {request_id, text}` tool and the optional `dispatch` `timeout`, with the new tool descriptions. In `agents_inc/install/mcp_broker.py`. Plan: DD7. Serves: FR-008, FR-016. Depends on T028.
- [ ] T030 [US3] Add `mcp__agents_inc__check_lead` to `--allowedTools` in the Claude launch. In `agents_inc/install/dispatch.py`. Plan: DD10. Serves: FR-002, FR-009. Depends on T028 (same file). The prompt note text is not written here (see T046).
- [ ] T031 [US3] Live proof (opt-in): push a note holding a random nonce to one Claude Worker and one Codex Worker, each told to repeat any Lead note in its report. Assert, per vendor, that the report contains the nonce and `ask/<rid>.push.1.seen` exists; assert the Claude transport record reads `socket`; let the Codex record read `file` only with a non-empty `fallback_reason`. In `tests/test_worker_mcp_live.py`. Plan: DD11. Serves: FR-009, SC-007. Depends on T023 (same file).

**Checkpoint**: US1 to US3 work. A running Worker can receive a Lead push.

---

## Phase 6: User Story 4 - An operator session reaches a delegate (Priority: P3)

**Goal**: `agents-inc tell` hands a note to the broker, which screens, counts and pushes it with a `cos` or `operator` tag.

**Independent Test**: Run `agents-inc tell` against a temp run dir with a stand-in Worker, and connect straight to the Worker socket without the token.

### Tests for User Story 4 (write first; they must fail on unchanged code)

- [ ] T032 [P] [US4] Test: `agents-inc tell RUN_DIR REQUEST_ID --source cos` and `--source operator` deliver a tagged push under the same screen and cap as a Lead push; text comes from stdin and never from argv; a bad source, including `--source lead` (FR-010), exits 2 and sends nothing; a refusal exits 3 with the reason on stderr and never prints the text; with no broker socket the note goes to `<run-dir>/tell/<rand>.json` and is picked up. In `tests/test_dispatch_push.py`. Fails today because there is no `tell` subcommand and no control server. Plan: DD8. Serves: FR-008, FR-010.
- [ ] T033 [P] [US4] Test: a peer of the same user that connects straight to the Worker socket is refused in 100% of cases: wrong token, no `hello` within 5 s, a second peer, and (where the platform allows) another uid; a failed peer check records `peer_check: token-only`. In `tests/test_worker_sock.py`. Fails today because there is no socket to refuse from. Plan: DD1. Serves: FR-007, SC-005.
- [ ] T034 [P] [US4] Test: while a Lead `wait` call blocks, `tell` still reaches the broker through the control server and the Worker sees the tagged note, in 5 of 5 trials. In `tests/test_mcp_broker.py`. Fails today because the broker has no control socket and `serve` handles one Lead call at a time. Plan: DD8. Serves: FR-010, FR-016, SC-009.

### Implementation for User Story 4

- [ ] T035 [P] [US4] Add `ControlServer`: bind `<run-dir>/broker.sock` by the same relative-name rule, mode 0600, same-uid peers only, its own thread, one `tell` frame in, `push_message`, one reply frame; scan `tell/` every 1 s only while the socket is down; start it from the file `serve` too. In `agents_inc/install/dispatch.py`. Plan: DD8. Serves: FR-007, FR-010, FR-016.
- [ ] T036 [P] [US4] Add the `tell RUN_DIR REQUEST_ID --source {cos,operator}` subcommand: text from stdin up to 64 KiB, connect by the same rule, drop-dir fallback, exit codes 0, 3 and 2. In `agents_inc/install/cli.py`. Plan: DD8. Serves: FR-010.
- [ ] T037 [US4] Start `ControlServer` from `Broker.ensure()`. In `agents_inc/install/mcp_broker.py`. Plan: DD8. Serves: FR-016, SC-009. Depends on T035.
- [ ] T038 [US4] Live probes (opt-in): probe each direction (Lead to the child run dir, Worker to the broker run dir) once per vendor, 4 probes, and assert all 4 are refused; whether a file-inbox Codex Lead can connect to `broker.sock` (the R12 gap; record the answer). In `tests/test_mcp_broker_live.py`. Plan: DD11. Serves: FR-014, SC-005. Depends on T037.

**Checkpoint**: US1 to US4 work. An operator session can reach a running delegate through the broker.

---

## Phase 7: User Story 5 - One event record for a Worker turn (Priority: P3)

**Goal**: Each question, answer and push adds one metadata-only line to `<child>/events.jsonl`.

**Independent Test**: One question, one answer, one push. Read the file. Three lines, six fields each, no message text.

### Tests for User Story 5 (write first; they must fail on unchanged code)

- [ ] T039 [P] [US5] Test: after one question, one answer and one push the file holds three lines in time order (`to-lead`/`ask`, `to-worker`/`answer`, `to-worker`/`push`); each line has exactly `ts`, `rid`, `dir`, `kind`, `n` and `bytes`; each `bytes` equals the UTF-8 length of that message's screened text (the cut and redacted copy for `ask`); a distinctive push string, the source tag and the token never appear in the file; each line is one append of under 512 bytes; a write error does not block a message. In `tests/test_dispatch_push.py`. Fails today because no `events.jsonl` is written. Plan: DD9. Serves: FR-011, SC-008, SC-011.

### Implementation for User Story 5

- [ ] T040 [US5] Add `append_event(child, rid, dir, kind, n, nbytes)` (`O_WRONLY|O_APPEND|O_CREAT|O_NOFOLLOW`, mode 0644, one `os.write`, errors ignored) and call it from `relay_question` on first copy, `answer_question` and `push_message`. In `agents_inc/install/dispatch.py`. Plan: DD9. Serves: FR-011, SC-008. Depends on T039.

**Checkpoint**: All five stories work.

---

## Phase 8: Polish and cross-cutting checks

- [ ] T041 [P] Run `tests/test_dispatch_resume.py` unchanged against the finished code and compare with the T003 baseline. Also check that the existing cases in the extended `tests/test_worker_mcp.py` and `tests/test_mcp_broker.py` are not modified (diff shows additions only, except the three exact-list assertions SC-006 names). Plan: DD12. Serves: SC-006.
- [ ] T042 [P] Run `tests/test_dispatch_broker.py` unchanged against the finished code. Plan: DD12. Serves: SC-006.
- [ ] T043 Cross-vendor review of the trust-boundary diff (token, peer check, control server, sandbox `read_ok`) in `agents_inc/install/dispatch.py`; the reviewer is from a different vendor (D46 item 10(b)). Record the result in the ledger. Plan: DD12. Serves: FR-007, FR-014, SC-005.

---

## Phase 9: Canon (LESSON-CANDIDATE, not implemented)

**Purpose**: Report these to the Lead. Do not edit any of these files (FR-015). Each item is a report item. Tick it when the Lead has the report, not when a file changes.

- [ ] T044 LESSON-CANDIDATE report item: a new decision entry in `docs/DECISIONS.md` that amends D54 (push, the 2 and 5 cap, `check_lead`, `agents-inc tell`, source tags, the `events.jsonl` line format). Plan: Canon paragraph. Serves: FR-008, FR-010, FR-011, FR-015.
- [ ] T045 LESSON-CANDIDATE report item: the `CONTEXT.md` rows in plan.md "Agent context update": new Push, Channel and Doorbell; amended Turn and Dispatch broker (settled at analyze, A5 and A10). Plan: Agent context update, Canon paragraph. Serves: FR-015.
- [ ] T046 LESSON-CANDIDATE report item: the new `ASK_LEAD_NOTE` Worker prompt text in `agents_inc/install/dispatch.py` that names both tools and asks the Worker to call `check_lead` between major steps. The Lead writes it. Plan: DD10, Canon paragraph. Serves: FR-009, FR-015.
- [ ] T047 LESSON-CANDIDATE report item: lines on `tell` and `push` in `skills/workerbee/SKILL.md`. Plan: Canon paragraph. Serves: FR-010, FR-015.
- [ ] T048 LESSON-CANDIDATE report item: lines on `tell` and `push` in `skills/workerbee/QUICKREF.md`. Plan: Canon paragraph. Serves: FR-010, FR-015.

---

## Dependencies and execution order

- Phase 1 first. T001 blocks everything. Phase 2 blocks all stories.
- Stories run in priority order: US1, US2, US3, US4, US5. US2 builds on the US1 channel server and `WorkerLink`. US3 builds on US1 and US2. US4 reuses `push_message` from US3. US5 adds its call sites to `relay_question`, `answer_question` and `push_message`.
- Within a story, test tasks come first and must fail before the implementation tasks run.
- Tasks in the same file never carry [P] together: `dispatch.py` (T009, T010, T016, T022, T028, T030, T035, T040), `worker_mcp.py` (T008, T014, T015, T021, T027), `mcp_broker.py` (T017, T029, T037), `test_dispatch_push.py` (T005, T012, T020, T025, T032, T039, T049), `test_worker_sock.py` (T006, T011, T019, T033), `test_worker_mcp_live.py` (T018, T023, T031).
- Phase 9 items are reports only. They need no code and can be sent to the Lead at any time after T001.

## Coverage map (each id appears in at least one task)

- FR-001: T011, T012, T015, T016. FR-002: T011, T014, T024, T025, T027, T030. FR-003: T011, T013, T015, T016, T017, T018. FR-004: T012, T016, T025, T028. FR-005: T006, T008, T019, T020, T021, T022. FR-006: T011, T014, T019, T020, T021, T022, T023. FR-007: T004 to T009, T014, T016, T033, T035, T043.
- FR-008: T025, T026, T028, T029, T032, T044. FR-009: T024, T025, T027, T030, T031, T046. FR-010: T032, T034, T035, T036, T044, T047, T048. FR-011: T039, T040, T044. FR-012: T005, T010, T019, T020, T021, T022, T025, T028, T049. FR-013: T008, T011, T014. FR-014: T002, T005, T009, T018, T038, T043. FR-015: T044 to T048. FR-016: T026, T029, T034, T035, T037.
- SC-001: T011, T013, T015, T016, T017. SC-002: T010, T019 to T023. SC-003: T011, T012, T016. SC-004: T011, T015. SC-005: T005, T014, T018, T033, T038, T043. SC-006: T002, T003, T024, T041, T042. SC-007: T018, T024, T027, T031. SC-008: T039, T040. SC-009: T034, T037. SC-010: T028, T049. SC-011: T005, T039.

## Notes

- The plan says `tasks.md` comes "from worker_slots.json". That file was not an allowed input for this run, so the slot split is not applied here.
- SC-006 resolved at analyze (A2): existing cases stay untouched and new cases are added, except three exact-list assertions in `tests/test_worker_mcp.py` that FR-002 and FR-016 force. T024 updates them; T041 checks the diff.
- Verify each test fails on unchanged code before starting its implementation tasks.
