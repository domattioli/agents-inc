<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-checklist repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->
# Requirements Quality Checklist: MCP Channel Protocol Hygiene (018)

**Purpose**: Test the writing of the 018 requirements (completeness, clarity, consistency, measurability, scenario coverage, 017 overlap, invariants, traceability). It does not test code.
**Created**: 2026-10-06
**Feature**: [spec.md](../spec.md), with [plan.md](../plan.md), [research.md](../research.md) and [tasks.md](../tasks.md)

`[x]` checked against the text, with one line of evidence. `[ ]` open, with one line of finding for the Lead or analyze.

## Completeness

- [x] CHK001 Is every Supervisor finding F1 to F10 mapped to an FR or an Out of Scope line? [Spec §Background] Evidence: "Taken by" column; Out of Scope lists F6, F7, F9 part, F10, F2 part.
- [x] CHK002 Does each clarify answer appear once in Clarifications and in the section it changes? [Spec §Clarifications] Evidence: Q1 → FR-001; Q2 → FR-010; Q3 → FR-003; Q4 → FR-008; Q5 → Overlap last paragraph.
- [x] CHK003 Is the Q2 answer recorded as the operator's own, not the Supervisor's? [Spec §Clarifications] Evidence: "(Operator, domattioli, directly.)".
- [x] CHK004 Are start gates stated for both waves and for FR-010? [Plan §Start gates] Evidence: wave 1 after PR 52 and T002; wave 2 after 017; FR-010 after T027 to T029.
- [x] CHK005 Are requirements defined for the file broker (`dispatch --serve`) restart case? [Gap] Evidence (analyze A9): Out of Scope now names file-broker restart durability.
- [x] CHK006 Is the `2026-07-28` deferral recorded as a follow-up, not a requirement? [Research §R1] Evidence: "Follow-up, not a requirement".

## Clarity and measurability

- [x] CHK007 Is the version answer for an unsupported or missing request unambiguous? [Spec §FR-001] Evidence: "else with the newest version in the set"; set given newest first.
- [x] CHK008 Is "at once" for `ping` quantified? [Spec §SC-002] Evidence: within 1 s, 20 of 20 trials.
- [x] CHK009 Is the progress cadence quantified and bounded after the result? [Spec §FR-005] Evidence: every 30 s; none after the result.
- [x] CHK010 Is the client-timeout margin quantified? [Spec §FR-006] Evidence: at least 60 s; `timeout` = `MCP_TOOL_TIMEOUT_SEC` × 1000.
- [x] CHK011 Is each `task_state` mapping stated? [Spec §FR-008, Research §R4] Evidence: six rows plus `usage-error` → none.
- [x] CHK012 Is the `outputSchema` content for each broker tool specified? [Ambiguity, Research §R11] Evidence (analyze A7): R11 lists all five `status` keys as required.

## Consistency with 017

- [x] CHK013 Does any 018 requirement change 017's socket, doorbell, push, `check_lead`, `tell` or `events.jsonl`? [Spec §Overlap with 017] Evidence: none; Out of Scope lists them; edge case says cancel writes no `events.jsonl` line.
- [x] CHK014 Does FR-003 keep 017 DD7's sequential handling of `answer` and `push`? [Spec §FR-003, Tasks T022] Evidence: only `status` runs during a blocking call; T022 tests `answer` waits.
- [x] CHK015 Does 018 add a rival Lead time-limit parameter? [Spec §Overlap with 017] Evidence: "018 adds no rival time-limit parameter"; `cancel` is called between 017's bounded calls (FR-010).
- [x] CHK016 Is the landing order stated per FR? [Spec §Overlap with 017, Plan §Start gates] Evidence: wave 1 and wave 2 lists.

## Invariants and canon

- [x] CHK017 Is every D51/D54 invariant restated and unweakened? [Spec §Requirements preamble] Evidence: preamble; FR-011 widens redaction only; HOME over-redaction kept.
- [x] CHK018 Does any requirement add an environment value, key or token to a Worker? [Spec §FR-006] Evidence: "No key, token or environment value is added to the Worker environment".
- [x] CHK019 Is the Worker kept from seeing `cancel`? [Spec §FR-010] Evidence: "The Worker MUST NOT see a `cancel` tool"; T031 guard.
- [x] CHK020 Are canon edits LESSON-CANDIDATE only, with sign-off and a cross-vendor reviewer, and before FR-010 code? [Spec §FR-010, §FR-012; Tasks T027 to T029] Evidence: FR-010 "No FR-010 code may be written until"; T030 to T034 depend on T029.
- [x] CHK021 Does every MCP or A2A fact carry a URL or an [assumed] tag? [Spec §FR-001, FR-002, FR-004, FR-008; Research §R13] Evidence: each cites a primary URL marked unreachable or a Supervisor-cited secondary URL.

## Scenario and edge coverage

- [x] CHK022 Are cancel races covered (late cancel, cancel of a finished call, answer after cancel)? [Spec §Edge Cases] Evidence: three bullets.
- [x] CHK023 Is a restart during a running turn covered? [Spec §Edge Cases] Evidence: recovered id returns `timeout`; `resume` refuses with `request-running`.
- [x] CHK024 Is the client behavior when it receives an older negotiated version than it asked for covered? [Assumption, Research §R1] Evidence (analyze A5): T011 records the Claude client's negotiated version; Codex stays [assumed] until installed.

## Traceability

- [x] CHK025 Does every FR map to at least one task, and every task to at least one FR? [Tasks §FR to task map] Evidence: map covers FR-001 to FR-012; every task line ends with "Serves:".
- [x] CHK026 Does every task name a model or tier, a runnable success check and a failure condition? [Tasks §Format] Evidence: T001 to T038.

## Notes

- 26 items. Leg 2: 23 pass, 3 open. Analyze cycle 1 (2026-10-06) closed CHK005, CHK012, CHK024: 26 pass.
