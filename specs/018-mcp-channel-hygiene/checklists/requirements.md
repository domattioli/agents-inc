<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-checklist repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->
# Specification Quality Checklist: MCP Channel Protocol Hygiene (018)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-06
**Feature**: [spec.md](../spec.md)

`[x]` passes, with one line of evidence. `[ ]` fails or is pending, with one line of finding.

## Content Quality

- [ ] No implementation details (languages, frameworks, APIs). Accepted deviation: the feature is protocol hygiene on two named servers, so method names, file names and test ids are the subject matter (same deviation as 017).
- [x] Focused on user value and business needs. Evidence: User Stories 1 to 4 state the Lead's and Worker's gain and why each priority holds.
- [ ] Written for non-technical stakeholders. Accepted deviation: readers are the Supervisor, the operator and builders; the Background table states each finding in plain words.
- [x] All mandatory sections completed. Evidence: User Scenarios, Requirements, Success Criteria, plus Overlap with 017, Clarifications (5 answers, Session 2026-10-06), Assumptions, Out of Scope.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain. Evidence: clarify answers of 2026-10-06 integrated (Clarifications, Session 2026-10-06); `grep -c 'NEEDS CLARIFICATION' spec.md` prints 0.
- [x] Requirements are testable and unambiguous. Evidence: each FR-001 to FR-012 ends with an Acceptance line naming a test file and test id, or a command.
- [x] Success criteria are measurable. Evidence: SC-001 to SC-009 give counts, trial numbers or time bounds.
- [ ] Success criteria are technology-agnostic. Accepted deviation: SC-002 to SC-005 name protocol messages, because the outcome is protocol behavior.
- [x] All acceptance scenarios are defined. Evidence: each user story has Given/When/Then scenarios.
- [x] Edge cases are identified. Evidence: Edge Cases lists 7, including late cancel, restart mid-turn and encoded secrets.
- [x] Scope is clearly bounded. Evidence: Out of Scope maps F6, F7, F9 (part), F10, F2 (part), A2A gateway and every 017-owned item.
- [x] Dependencies and assumptions identified. Evidence: Assumptions (017 landing, commit drift, Codex client behavior unknown); Premise section on Tasks client support.

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria. Evidence: FR Acceptance lines.
- [x] User scenarios cover primary flows. Evidence: negotiation (US1), blocking-call liveness (US2), restart (US3), task state and cancel (US4).
- [x] Feature meets measurable outcomes defined in Success Criteria. Evidence: every FR maps to an SC or to a named test (Success Criteria, last subsection).
- [ ] No implementation details leak into specification. Accepted deviation, as the first item.

## Feature-specific checks

- [x] Each of F1 to F10 maps to an FR or an Out of Scope line. Evidence: Background table, "Taken by" column.
- [x] Overlap with 017 states shared code, 017's design, 018's position and which lands first. Evidence: Overlap with 017 table.
- [x] No requirement redoes or contradicts 017. Evidence: FR-003 keeps 017 DD7 sequential Lead calls; FR-004/FR-005 reuse 017's wait; Out of Scope lists 017's items.
- [x] D51/D54 invariants stated and kept. Evidence: Requirements preamble; FR-011 only widens redaction; HOME over-redaction is kept (Out of Scope).
- [x] Every MCP or A2A fact carries a URL or an [assumed] tag. Evidence: FR-001, FR-002, FR-004, FR-008, Premise section.
- [x] Canon edits are LESSON-CANDIDATE only. Evidence: FR-012.
- [x] Tasks client-support premise is gated, not assumed. Evidence: Premise section and FR-009.

## Notes

- Iteration 1 (specify): 3 clarification markers open.
- Iteration 2 (after clarify, 2026-10-06): markers resolved; only the accepted technical-content deviations remain.
