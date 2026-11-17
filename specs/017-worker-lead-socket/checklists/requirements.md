<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-10-04 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Requirements Quality Checklist: Worker-Lead Socket Channel (017)

**Purpose**: Check the quality of the requirements in spec.md: completeness, clarity, consistency, measurability, edge-case coverage, traceability and security. It tests the writing of the requirements, not the code.
**Created**: 2026-10-04
**Feature**: [spec.md](../spec.md), with [plan.md](../plan.md) and [tasks.md](../tasks.md) for traceability

**Note**: `[x]` means the item was checked against the text, with one line of evidence. `[ ]` means it fails, with one line of finding. Findings go to the Lead; this run did not edit spec.md, plan.md or research.md.

## Completeness

- [x] CHK001 All mandatory sections exist (User Scenarios, Requirements, Success Criteria). Evidence: spec.md has all three, plus Assumptions and Out of Scope.
- [x] CHK002 Each user story has a priority, a reason for the priority, an independent test and acceptance scenarios. Evidence: US1 to US5.
- [x] CHK003 Each clarify question has a recorded answer. Evidence: Clarifications, Session 2026-10-04, Q1 to Q7.
- [x] CHK004 The dependency on the D54 merge is stated. Evidence: Assumptions, first bullet.
- [x] CHK005 Out of scope is explicit. Evidence: Out of Scope lists the HTTP bridge, free-provider transports, the issue 51 tee, and the native protocol.
- [x] CHK006 The ladder terms used for the push cap (Grunt, Workhorse) are defined in the spec. Evidence: "Terms used here", Grunt, Workhorse (analyze A17).
- [x] CHK007 Every term used in a requirement is defined once. Evidence: "Terms used here" defines `run.json` and Doorbell; FR-012 says the push counts live in `run.json` (analyze A17).

## Clarity

- [x] CHK008 The socket name and place are fixed, with no process id. Evidence: FR-006 ("one short, fixed name", "MUST NOT depend on a process id").
- [x] CHK009 The push cap values and the refusal reasons are named. Evidence: FR-008 (2 and 5, `push-cap`, `turn-ended`).
- [x] CHK010 The line format of `events.jsonl` is exact. Evidence: FR-011 (six fields, the two `dir` values, the four `kind` values).
- [x] CHK011 FR-016 is unambiguous. Evidence: FR-016 now requires an optional time limit on `dispatch`, `resume` and `wait`, and a separate path for `tell` (analyze A3).
- [x] CHK012 Requirements avoid vague words without a number. Evidence: FR-003 is bounded by SC-001 (0.5 s); FR-005 lists the failure kinds.

## Consistency

- [x] CHK013 SC-006 and plan.md agree on the D54 tests. Evidence: SC-006 allows additions only, except three named exact-list assertions; plan.md "Project Structure" and T024, T041 match (analyze A2).
- [x] CHK014 The `tell` source tags agree across spec and plan. Evidence: FR-010 and US4 AC3 now accept only `cos` or `operator` for `tell`, as plan.md DD8 does (analyze A1).
- [x] CHK015 The CONTEXT.md terms to propose match across documents. Evidence: FR-015, plan.md "Agent context update" and T045 all list new Push, Channel, Doorbell and amended Turn, Dispatch broker (analyze A5, A10).
- [x] CHK016 Fallback rules agree across stories and requirements. Evidence: Q6, FR-005 and US3 AC2 all say files for the rest of the turn, with `check_lead` reading files.
- [x] CHK017 The file-first rule agrees with the push rule. Evidence: FR-001 ("every question, answer and push") and Key Entities, Durable log.
- [x] CHK018 No requirement conflicts with the D46 chain or the D51 screen. Evidence: FR-004 (same screen), FR-010 (broker only), Q3 reason.

## Measurability of the success criteria

- [x] CHK019 SC-001 has a number and a trial count. Evidence: SC-001 (under 0.5 s, 20 of 20).
- [x] CHK020 SC-002 has fault kinds, run counts and a rate. Evidence: SC-002 (at least 4 kinds, 5 runs each, 100%, 0 lost).
- [x] CHK021 SC-004 can be measured as written. Evidence: SC-004 counts reads with a patched `Channel._read_answer` (T011): one read per answer, 0 while waiting (analyze A13).
- [x] CHK022 SC-005 has a trial count for the live probe. Evidence: SC-005 sets 4 probes (2 directions, 2 vendors), all refused (T038; analyze A14).
- [x] CHK023 SC-007 can fail. Evidence: SC-007 names the T031 live test and its assertions (nonce in the report, `.seen` marker, Claude transport `socket`) (analyze A6).
- [x] CHK024 SC-008 and SC-009 are countable. Evidence: SC-008 (0 body or token lines, 100% six fields); SC-009 (5 of 5 trials while `wait` blocks).
- [x] CHK025 SC-003 and SC-006 are checkable by a test run. Evidence: SC-003 (a file with the same content exists); SC-006 (named test files pass).

## Edge-case coverage

- [x] CHK026 Stale socket, resume without a process id, and the 104-byte limit each map to a requirement. Evidence: Edge Cases 1 to 3 map to FR-005 and FR-006.
- [x] CHK027 The blocking Lead call maps to a requirement and a criterion. Evidence: Edge Case 4, FR-016, SC-009.
- [x] CHK028 The forge path is covered. Evidence: Edge Case 7 and FR-014 (no widening); FR-004 (screen).
- [x] CHK029 The Lead-dies edge case has a requirement or criterion. Evidence: FR-005 last sentence (30-minute limit, no-answer text); tested by T019 (analyze A15).
- [x] CHK030 The sent-but-not-delivered push has a testable criterion. Evidence: SC-010 (1 sent, 0 delivered, 5 of 5; T049) (analyze A7).
- [x] CHK031 The 104-byte path case is inside the fault criterion. Evidence: SC-002 and US2's Independent Test list it as the fifth fault kind (analyze A16).
- [x] CHK032 Unknown Codex behaviour has a fallback and a proof. Evidence: Edge Case 8, FR-005, SC-007.

## Traceability (FR to SC to task)

- [x] CHK033 Every FR-001 to FR-016 appears in at least one task. Evidence: tasks.md "Coverage map".
- [x] CHK034 Every SC-001 to SC-011 appears in at least one task. Evidence: tasks.md "Coverage map".
- [x] CHK035 Every FR maps to at least one SC or a named test task. Evidence: spec "Requirements checked by a named test task" maps FR-002, FR-004, FR-008, FR-013 and FR-015 to tasks; FR-006 maps to SC-002 and FR-012 to SC-010 (analyze A7).
- [x] CHK036 The FR to design decision link exists in the plan. Evidence: plan.md DD1 to DD12 each name their FR ids.
- [x] CHK037 Each user story has acceptance tests first in tasks.md. Evidence: tasks.md US1 T011 to T013, US2 T019 and T020, US3 T024 to T026, US4 T032 to T034, US5 T039.

## Hygiene

- [x] CHK038 No `NEEDS CLARIFICATION` marker is left in spec.md. Evidence: reading of spec.md found none; open points carry `[inferred]` or `[assumed]` tags in Assumptions and Background.
- [x] CHK039 Assumptions that are guesses are tagged and tied to a proof. Evidence: Assumptions bullets 3 to 6 use `[inferred]` or `[assumed]`; FR-005 and SC-007 give the proofs.

## Security (token, source tag, events.jsonl body ban)

- [x] CHK040 The token is kept out of argv, prompts, logs, `run.json` and `events.jsonl`. Evidence: FR-007 lists all five.
- [x] CHK041 A success criterion checks that the token stays out of argv, the prompt, logs and `run.json`. Evidence: SC-011 (T005, T039) (analyze A7).
- [x] CHK042 The token's mode and the same-user limit are stated. Evidence: FR-007 (mode 0600, same OS user); Q4 (an unsandboxed same-user process can read the file).
- [x] CHK043 The source tag is stated to be unproven. Evidence: FR-010 ("the broker cannot prove it") and Assumptions bullet 2.
- [x] CHK044 The source tag is kept out of `events.jsonl` and the allowed values are closed. Evidence: FR-011 (no source tag in a line); FR-010 (one of three values); US4 AC3 (usage error otherwise).
- [x] CHK045 The body ban in `events.jsonl` is a requirement and a criterion. Evidence: FR-011 ("MUST NOT contain a message body"), SC-008, US5 AC2.
- [x] CHK046 The socket cannot widen file access or open a network path. Evidence: FR-013 (Unix socket only, no TCP) and FR-014 (no new path for Lead or Worker).
- [x] CHK047 A non-broker peer is refused by requirement and by criterion. Evidence: FR-007, US4 AC2, SC-005.

## Notes

- Open items (fail): none. The 14 items that failed on the first run (CHK006, CHK007, CHK011, CHK013, CHK014, CHK015, CHK021, CHK022, CHK023, CHK029, CHK030, CHK031, CHK035, CHK041) were closed by the Lead at analyze, cycles 1 and 2, on 2026-10-04. See analyze.md "Resolved".
- The Workhorse run that wrote this checklist did not edit spec.md, plan.md or research.md. The Lead later edited spec.md, plan.md, tasks.md and this file.
