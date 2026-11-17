# Requirements Quality Checklist: Dispatch fails loud

**Purpose**: Validate spec completeness and quality before implement (spec-quality items from speckit-specify, requirement-quality items from speckit-checklist)
**Created**: 2026-10-18
**Feature**: `.scratch/spec022/spec.md`
**Audience/depth**: reviewer (CoS), standard depth, focus on failure classification and scope-gate integrity.

## Content Quality

- [x] CHK001 Focused on user value: each story names the operator or CoS outcome [Spec §User Stories]
- [x] CHK002 All mandatory sections completed (scenarios, requirements, success criteria, assumptions) [Spec]
- [ ] CHK003 No implementation details in requirements — intentional deviation: the dispatch PLAN CONTRACT requires each requirement to name a real path and a backticked acceptance command, so FRs cite functions and lines [Spec §Functional Requirements]
- [ ] CHK004 Written for non-technical readers — deviation: audience is the CoS and an implementing Worker (`AGENTS.md` Documentation style: dispatch specs are agent surfaces, maximum compression) [Spec]

## Requirement Completeness

- [x] CHK005 No [NEEDS CLARIFICATION] markers remain; unresolved choices are under "Open for CoS" with a recommendation [Spec §Open for CoS]
- [x] CHK006 Every audit finding 1, 2, 4-15 and #88 item 5 / finding 3 maps to at least one FR [Spec §FR-001..021; analyze.md coverage table]
- [x] CHK007 Exit codes for every outcome are specified, including precedence when several apply [Spec §FR-012; contracts/dispatch-outcomes.md]
- [x] CHK008 Legacy-run behaviour after upgrade is specified (`snapshot_trust: run-dir`) [Spec §Edge Cases]
- [x] CHK009 Requirements state what stays unchanged (outcome set, broker statuses, request-slot screen) [Spec §Clarifications, FR-021]
- [x] CHK010 Timeout default and override are specified (3600 s, `AGENTS_INC_TURN_TIMEOUT_S`) [Spec §FR-014]
- [ ] CHK011 Behaviour of the live `claude auth status` probe is specified — deferred to CoS (Open item 4) [Spec §Open for CoS]

## Requirement Clarity

- [x] CHK012 "Fails loud" is quantified as named reason + detail + exit code per failure shape [Spec §US2 scenarios]
- [x] CHK013 Stderr detail bounds are explicit (first non-empty line, 200 bytes, screened, whitespace replaced) [Spec §FR-008]
- [x] CHK014 The pattern-matching scope for quota/block text is explicit, avoiding false pauses on reports that quote the text [Spec §Edge Cases, FR-005]
- [x] CHK015 The trusted store is located from run id only, never from a delegate-writable file [Spec §FR-001; research.md R1]

## Requirement Consistency

- [x] CHK016 Outcome values stay within D58's set; new causes are reasons, not outcomes [Spec §Clarifications; data-model.md]
- [x] CHK017 Doctor severities follow D52 (warnings keep READY) except the required provider (code) [Spec §FR-017; plan.md Constitution Check]
- [x] CHK018 Test file names in spec FRs match tasks.md (resolved in analyze cycle 1, A1) [Spec; tasks.md]

## Acceptance Criteria Quality

- [x] CHK019 Every FR has a backticked unittest command [Spec §FR-001..022]
- [x] CHK020 Success criteria are measurable counts or bounds (16/16, 4 codes, 0/3, ≤5 s, 100%, 0 failures) [Spec §SC-001..006]

## Scenario Coverage

- [x] CHK021 Primary, exception and recovery flows: tamper, quota, block, crash, launch exception, verifier error, mirror error, hang [Spec §US1-US3]
- [x] CHK022 Security scenarios: env values in stderr redacted; trusted copy unreachable by delegates; credential screen still refuses real secrets [Spec §Edge Cases, FR-021]
- [ ] CHK023 Live confirmation that `claude -p` emits `is_error` — assumption only, no fixture [Spec §Assumptions]

## Dependencies & Assumptions

- [x] CHK024 Canon amendment (D58 exit list) identified and assigned to the CoS [plan.md Complexity Tracking; tasks.md T027]
- [x] CHK025 Out-of-scope items listed (#88 items 1-4, 6-8; spec 021; DomI) [Spec §Context]

## Notes

- Re-checked after analyze cycle 1 edits (A1-A9): CHK006, CHK015, CHK018 still hold; Open for CoS now has 6 items (item 6: turn deadline default).
- Open items CHK003, CHK004 are accepted deviations required by the dispatch contract. CHK011 and CHK023 wait on the CoS (Open items 4 and the `is_error` assumption).
