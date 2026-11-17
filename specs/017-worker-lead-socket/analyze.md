<!-- provenance: author=domattioli model=claude-opus-5-5 effort=unknown date=2026-10-04 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Analyze report: 017 Worker-Lead socket channel

Run by the Lead (opus) on 2026-10-04 for the CoS. Cycle 1 fixed the HIGH findings; cycle 2 (of 2) fixed the MEDIUM and LOW findings under CoS rulings. Inputs: `spec.md`, `plan.md`, `tasks.md`, with `research.md`, `checklists/requirements.md` and `CONTEXT.md` for cross-checks. Code was read only to test claims; no code was edited. Tags: [verified] means read in code or run; [inferred] means reasoned from text or code; [assumed] means not checked.

## Open questions in the dispatch

- Caveman: real `Skill caveman ultra` call succeeded. This report is plain prose.
- The tree equals HEAD `1fcfd76` for `agents_inc/install` and `tests` (`git status --short agents_inc/install tests` printed nothing) [verified]. `1fcfd76` is on `origin/development` only, not on `main` [verified]. CoS ruling, cycle 2: PR 52 (`development` to `main`) is open; implementation starts after it merges.
- Constitution unratified (plan.md Constitution Check), so every constitution item is WARN. No constitution finding below is CRITICAL [assumed; constitution not re-read, it lives in DomI].
- `worker_slots.json` has 15 keys with `FAN_OUT` set to `width 0, total 0, depth 0` [verified]. The earlier 14-key FAN_OUT grill is closed.
- The 14 checklist fails (CHK006, 007, 011, 013, 014, 015, 021, 022, 023, 029, 030, 031, 035, 041) map to findings below. All 14 are now ticked in `checklists/requirements.md`.

## Findings

| ID | Severity | Location | Summary | Recommended fix |
|---|---|---|---|---|
| A1 | HIGH | spec.md FR-010, US4 AC3, Clarification Q3; plan.md DD8, research R3; tasks.md T032, T036 | Spec let `agents-inc tell` take `cos`, `lead` or `operator`; plan and tasks let the CLI take `cos` or `operator` only. `tell --source lead` was valid in the spec and a usage error in the plan (checklist CHK014). | Amend FR-010 and US4 AC3: `tell` accepts `cos` or `operator`; `lead` comes only from the Lead's own push path. Add `--source lead` exits 2 to T032. **Fixed.** |
| A2 | HIGH | spec.md SC-006; plan.md Project Structure; tasks.md T024, T041, Notes | SC-006 said the D54 tests pass "unchanged", but three existing assertions in `tests/test_worker_mcp.py` pin exact lists that FR-002 and FR-016 change: the Worker tool list `["ask_lead"]` (`:48`), `--allowedTools` equal to `mcp__agents_inc__ask_lead` (`:354`), and the broker tool list without `push` (`:293`) [verified at 1fcfd76]. SC-006 could not pass as written (checklist CHK013). | Amend SC-006: existing cases pass; diff adds cases only, except those three assertions, each updated to the new exact list. Name them in plan Project Structure, T024 and T041. **Fixed.** |
| A3 | HIGH | spec.md FR-016, Edge Case 4; plan.md DD7 | FR-016 said a blocking Lead call "MUST NOT hold off a push for the whole turn" with no bound and no mechanism; the edge case said the Lead "pushes between short waits", but `dispatch` has no time limit today (`mcp_broker.py:36-44` gives `timeout` to `wait` and `resume` only) [verified]. Plan DD7 adds a `dispatch` timeout the spec never asked for (checklist CHK011). | Amend FR-016: `dispatch`, `resume` and `wait` accept an optional time limit so the Lead pushes between bounded calls; `tell` is served apart from the Lead's calls. Rewrite Edge Case 4 to match. **Fixed.** |
| A4 | HIGH | spec.md FR-004; research R8; plan.md DD1, DD4 | FR-004 said "every message on the socket MUST pass the same checks as its D54 file form", but the design (R8 doorbell) puts no body on the socket: frames carry only `op`, `rid` and `n`. Read literally, FR-004 asked for screening of frames that hold no text, and it did not forbid bodies on the socket, so it did not guard the design's key safety property. | Amend FR-004: the socket carries notices only, never a body; every body passes its D54 check before its file is written; no notice is sent for a body that failed. **Fixed.** |
| A5 | MEDIUM | spec.md FR-015; plan.md Project Structure (canon paragraph); tasks.md T045 | FR-015 named CONTEXT.md terms Turn, Question and Push; the plan named Push and an amended Turn only (CHK015). | One list everywhere: new Push, Channel, Doorbell; amended Turn, Dispatch broker. **Fixed.** |
| A6 | MEDIUM | spec.md SC-007; tasks.md T031; plan.md DD11 | SC-007 passed when each vendor delivered a push "or records why that vendor falls back", so a vendor that always falls back still passed (CHK023). | Name the live test and its assertion: nonce in each Worker's report, `.seen` marker exists, Claude transport `socket`, Codex `file` only with a reason. **Fixed.** |
| A7 | MEDIUM | spec.md SC list; Edge Case 6; FR-012 | No SC checked a push sent but never delivered, and no SC checked the token beyond `events.jsonl` (CHK030, CHK041). FR-002, FR-004, FR-006, FR-008, FR-012, FR-013 and FR-015 had no SC (CHK035). | Add SC-010 (undelivered push) and SC-011 (token in no log); map every other FR to an SC or a named test task. **Fixed.** |
| A8 | MEDIUM | plan.md start gate; spec.md Background heading, Assumptions; tasks.md header, T001 | Start gate said "after the D54 PR merges into `development`" and called D54 "uncommitted". D54 is commit `1fcfd76` on `origin/development` [verified]. | Gate on PR 52 merge (CoS ruling); re-cite against `1fcfd76`. **Fixed.** |
| A9 | MEDIUM | plan.md DD12; tasks.md Owners line, T002 | DD12 sent install code to a sonnet Workhorse and also assumed install edits were Executive-owned. Both could not hold. | Apply the operator ruling of 2026-10-04: Workhorse writes code and unit tests; Lead writes acceptance tests first and reviews. **Fixed.** |
| A10 | MEDIUM | CONTEXT.md:36, :66; spec.md Terms; plan.md Agent context update | CONTEXT.md Turn says no message reaches a delegate during a turn; Dispatch broker lists `dispatch`, `status`, `wait` only; no Push term. Spec "Channel" said "its one tool"; spec "Push" said "from the Lead side". | List the CONTEXT.md rows in plan.md "Agent context update" (no CONTEXT.md edit); fix the spec Terms. **Fixed.** |
| A11 | MEDIUM | plan.md DD6; spec.md FR-012 | DD6 counted `delivered` as one number but `sent` and `refused` by source; FR-012 did not say which. | Simpler reading: `delivered` is one total per request id. State it in FR-012 and DD6. **Fixed.** |
| A12 | MEDIUM | spec.md FR-011, US5 AC1; tasks.md T039 | `bytes` for an `ask` line was unclear: the Worker's question file, or the cut and redacted copy. | Simpler reading: `bytes` is the UTF-8 length of the screened text, for every kind. State it in FR-011, DD9, US5 AC1 and T039. **Fixed.** |
| A13 | LOW | spec.md SC-004, US1 Independent Test; tasks.md T011 | "reads 0 answer files" named no method (CHK021), and it contradicted DD2, which reads the answer file once after the doorbell. | SC-004: one read per answer after its doorbell, 0 reads while waiting, counted by a patched `Channel._read_answer`. **Fixed.** |
| A14 | LOW | spec.md SC-005; tasks.md T038 | The live sandbox probe had no trial count (CHK022). | 4 probes (2 directions, 2 vendors), all refused. **Fixed.** |
| A15 | LOW | spec.md Edge Case 5, FR-005 | Lead-dies case had no FR or SC (CHK029). | Add to FR-005: the D54 30-minute limit and no-answer text hold when the broker dies (tested by T019). **Fixed.** |
| A16 | LOW | spec.md SC-002, US2 Independent Test; tasks.md Phase 4, T019 | The long-path case of US2 AC3 was not an SC-002 fault kind (CHK031). | Add "full path over 104 bytes" as the fifth kind. **Fixed.** |
| A17 | LOW | spec.md Terms | Grunt, Workhorse and `run.json` were used without definition (CHK006, CHK007). | Add Terms lines. **Fixed.** |
| A18 | LOW | spec.md Out of Scope | Listed `plan.md` and `tasks.md` as later work; both exist. | Change to "Code and tests for this feature (implement phase, after PR 52 merges)". **Fixed.** |
| A19 | LOW | tasks.md T002, T003 | T002 named `plan.md` as its file and T003 named a test file it only runs. | Mark both "report only" or "run only, no file edited"; T003 runs all four D54 test modules for the baseline. **Fixed.** |
| A20 | LOW | research.md R8; spec.md FR-004 | The 4 KiB frame limit was in research and tasks only. Plan DD1 already stated it ("at most 4 KiB"); the spec did not. | Name the limit in FR-004. **Fixed.** |

## Coverage: FR to tasks

| FR | Tasks |
|---|---|
| FR-001 | T011, T012, T015, T016 |
| FR-002 | T011, T014, T024, T025, T027, T030 |
| FR-003 | T011, T013, T015, T016, T017, T018 |
| FR-004 | T012, T016, T025, T028 |
| FR-005 | T006, T008, T019, T020, T021, T022 |
| FR-006 | T011, T014, T019, T020, T021, T022, T023 |
| FR-007 | T004, T005, T006, T007, T008, T009, T014, T016, T033, T035, T043 |
| FR-008 | T025, T026, T028, T029, T032, T044 |
| FR-009 | T024, T025, T027, T030, T031, T046 |
| FR-010 | T032, T034, T035, T036, T044, T047, T048 |
| FR-011 | T039, T040, T044 |
| FR-012 | T005, T010, T019, T020, T021, T022, T025, T028, T049 |
| FR-013 | T008, T011, T014 |
| FR-014 | T002, T005, T009, T018, T038, T043 |
| FR-015 | T044, T045, T046, T047, T048 |
| FR-016 | T026, T029, T034, T035, T037 |

Every FR has at least one task. Every task T001 to T049 has a "Serves" field naming at least one FR or SC [verified: 0 task lines lack `Serves:`]. No orphan task.

## Coverage: SC to tasks

| SC | Tasks |
|---|---|
| SC-001 | T011, T013, T015, T016, T017 |
| SC-002 | T010, T019, T020, T021, T022, T023 |
| SC-003 | T011, T012, T016 |
| SC-004 | T011, T015 |
| SC-005 | T005, T014, T018, T033, T038, T043 |
| SC-006 | T002, T003, T024, T041, T042 |
| SC-007 | T018, T024, T027, T031 |
| SC-008 | T039, T040 |
| SC-009 | T034, T037 |
| SC-010 | T028, T049 |
| SC-011 | T005, T039 |

## Resolved

Fixes for every HIGH finding, applied by the Lead on 2026-10-04 to text only (no code):

- A1. spec.md FR-010: added "`agents-inc tell` MUST accept only `cos` or `operator`; the tag `lead` comes only from the Lead's own push path". spec.md US4 AC3: the usage error now covers any tag other than `cos` or `operator`, `lead` included. tasks.md T032: `--source lead` exits 2. Plan DD8, R3 and T036 already matched.
- A2. spec.md SC-006: existing cases pass; diff adds cases only, except three named exact-list assertions in `tests/test_worker_mcp.py` (`test_only_ask_lead_is_exposed`, `test_claude_worker_gets_ask_lead_server_and_sandbox_holes`, `test_needs_lead_answer_wait_resume`); `tests/test_dispatch_resume.py` gets no edit. plan.md Project Structure: the `test_worker_mcp.py` line names the three assertions (`:48`, `:293`, `:354` at `1fcfd76`). tasks.md T024: updates those three and nothing else in existing cases, and now serves SC-006. tasks.md T041: diff check allows those three. tasks.md Notes: the open question is marked resolved.
- A3. spec.md FR-016: `dispatch`, `resume` and `wait` accept an optional time limit so the Lead pushes between bounded calls; `tell` reaches the broker apart from the Lead's calls. spec.md Edge Case 4 rewritten to match. Plan DD7 (dispatch timeout) and tasks T026, T029 already matched; `wait` and `resume` already take `timeout` [verified, `mcp_broker.py:36-44`].
- A4. spec.md FR-004: the socket carries notices (kind, request id, number) only, never a body; each body passes its D54 check before its file is written; no notice for a failed body. Plan DD1, DD4 and tasks T014, T016, T028 already matched.

Open after cycle 1: 0 CRITICAL, 0 HIGH.

## Resolved cycle 2

Fixes for every MEDIUM and LOW finding, applied by the Lead on 2026-10-04 under CoS rulings (A6, A7, A8, A9, A10, A11, A12), to text only (no code, no CONTEXT.md edit):

- A5. spec.md FR-015, plan.md canon paragraph and tasks.md T045 now name one list: new rows Push, Channel, Doorbell; amended rows Turn, Dispatch broker.
- A6. spec.md SC-007 names the live test in `tests/test_worker_mcp_live.py` (T031) and its assertion: for each vendor the Worker report holds a random push nonce and `ask/<rid>.push.1.seen` exists; the Claude transport record reads `socket`; the Codex record may read `file` only with a non-empty `fallback_reason`. tasks.md T031 and plan.md DD11 carry the same rule.
- A7. spec.md adds SC-010 (a push after the last tool call: 1 sent, 0 delivered, push file exists, 5 of 5; new task T049 in `tests/test_dispatch_push.py`, and T028 serves it) and SC-011 (the token in 0 of `events.jsonl`, the broker log, `ask/<rid>.transport.json`, `run.json`, the request result, the Worker argv and the Worker prompt; T005 and T039). spec.md adds "Requirements checked by a named test task": FR-002 T024; FR-004 T012, T025; FR-008 T025, T032; FR-013 T011; FR-015 T044 to T048 (report items). Every other FR maps to an SC, listed there.
- A8. plan.md start gate, spec.md Assumptions and Background heading, tasks.md header and T001: D54 is on `development` at `1fcfd76`; implementation starts after PR 52 merges. Plan "Existing code" re-checked against `1fcfd76` with `git show 1fcfd76:<file>` and grep [verified]: all citations hold except the Codex launch, now `dispatch.py:299-312` (was `:308-312`).
- A9. plan.md DD12 and Constitution P2, tasks.md Owners line and T002: the operator ruling of 2026-10-04 (opus Lead over sonnet Workhorse). The Workhorse writes all code in `agents_inc/install/*` and unit tests; the Lead writes acceptance tests first and reviews every diff; a cross-vendor reviewer still checks the trust boundary (T043). The Executive-owned assumption is removed.
- A10. plan.md "Agent context update" lists the CONTEXT.md rows the implementation must add after sign-off: new Push, Channel, Doorbell; amended Turn (`CONTEXT.md:36`) and Dispatch broker (`CONTEXT.md:66`) [line numbers verified]. spec.md Terms: Channel names both tools; Push names all three sources; Doorbell added.
- A11. Simpler reading chosen: `delivered` is one total per request id, not split by source. Stated in spec.md FR-012, plan.md DD6 and T049.
- A12. Simpler reading chosen: `bytes` is the UTF-8 length of the message text after the broker's screen, one rule for every kind (for `ask`, the cut and redacted copy the Lead sees). Stated in spec.md FR-011 and US5 AC1, plan.md DD9 and tasks.md T039.
- A13. spec.md SC-004 and the US1 Independent Test, tasks.md T011: one read per answer after its doorbell, 0 reads while waiting, counted by a patched `Channel._read_answer`. This also removes the conflict with DD2. T011 no longer compares "socket frames byte for byte" with files, since frames hold no body (A4); it checks that each doorbell names an existing file.
- A14. spec.md SC-005 and tasks.md T038: 4 live probes (2 directions, 2 vendors), all refused.
- A15. spec.md FR-005: if the broker dies, `ask_lead` keeps the D54 30-minute limit and returns the D54 no-answer text (T019 tests it).
- A16. spec.md SC-002 and US2 Independent Test, tasks.md Phase 4 Independent Test and T019: "full path over 104 bytes" is the fifth fault kind.
- A17. spec.md Terms: Grunt, Workhorse and `run.json` added.
- A18. spec.md Out of Scope: "Code and tests for this feature (implement phase, after PR 52 merges)".
- A19. tasks.md T001, T002, T003 say "report only" or "run only, no file edited". T003 now runs all four D54 test modules for the SC-006 baseline.
- A20. spec.md FR-004 states the 4 KiB doorbell limit, matching plan.md DD1.
- Checklist: CHK006, 007, 011, 013, 014, 015, 021, 022, 023, 029, 030, 031, 035 and 041 ticked with evidence; CHK034 now reads SC-001 to SC-011; Notes updated.

Open after cycle 2: 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW.
