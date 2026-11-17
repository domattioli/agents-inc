<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=low date=2026-11-15 skill=speckit-checklist repo=agents-inc session=b437620e -->
# Verdicts and Refusals Checklist: Measured status

**Purpose**: Check that the requirements for the three-state outcome, exit codes, scope check, claim check, credential screen and hook decisions are complete, clear, consistent and measurable. Reviewer reads this before implementation. Depth: standard.
**Created**: 2026-11-15
**Feature**: [spec.md](../spec.md)

**Note**: Items test the quality of the requirements, not the implementation.

## Three-state outcome and exit codes

- [ ] CHK001 Is the outcome word set closed and listed in one place (passed, failed, `unverified`), with the mapping from the three per-gate states to those words? [Completeness, Spec §FR-001]
- [ ] CHK002 Is the new exit code for `unverified` given as a concrete number, or is the choice left open for the plan? [Clarity, Spec §FR-001a]
- [ ] CHK003 Does the spec list every existing path that returns `unverified` with exit 0 today (no gates, read-only in a non-git directory, others), so the exit-code move is fully scoped? [Completeness, Spec §Clarifications]
- [ ] CHK004 Is the rule for combining mixed gate states (some failed, some not checked, some passed) into one run outcome stated for every combination? [Gap, Spec §FR-004]
- [ ] CHK005 Is the precedence between a failed gate and an `unverified` cause (outside-scope change, stop condition) defined, so a failed gate is never hidden by `unverified`? [Ambiguity, Spec §FR-005, §FR-008]
- [ ] CHK006 Does the spec state how callers that treat any non-zero exit as failure are told about the new code? [Gap, Spec §Assumptions]
- [ ] CHK007 Is the amendment of D58 consistent across the Clarifications, FR-001a and FR-002, and is it recorded before shipping as FR-032 requires? [Consistency, Spec §FR-002, §FR-032]

## Gate state and reasons

- [ ] CHK008 Is "command could not start" defined by objective criteria (exit code 127 only, or also 126 and spawn errors)? [Clarity, Spec §FR-002]
- [ ] CHK009 Is the line between "gate could not start" and "gate started and a program it calls is missing" decidable from stated evidence? [Ambiguity, Spec §Edge Cases]
- [ ] CHK010 Is the boundary with the D72 pre-launch refusal clear, so the same absent program cannot give both a refusal and a not-checked result? [Consistency, Spec §FR-002]
- [ ] CHK011 Is the set of reason codes enumerated, with FR-011's "different codes" requirement testable? [Measurability, Spec §FR-011]
- [ ] CHK012 Is the usage-limit detection order defined against every other reason, and is "before any other reason" measurable? [Clarity, Spec §FR-007]

## Scope check

- [ ] CHK013 Is "declared file scope" defined for the case with no declared scope or an empty scope? [Gap, Spec §FR-005]
- [ ] CHK014 Does the spec say how changes are detected (before and after comparison, git status, hashes), including untracked files and deletions? [Gap, Spec §FR-005]
- [ ] CHK015 Do Scenario 3 (outside change gives `unverified`) and the Edge Case (in-scope change by another session passes) agree about attribution unknown? [Consistency, Spec §FR-006, §Edge Cases]
- [ ] CHK016 Is the spec explicit that an outside-scope change on a run whose gates failed still reports failed, not `unverified`? [Ambiguity, Spec §FR-005]

## Claim check

- [ ] CHK017 Is the machine-readable report block specified (field names, format, location in the report) enough to compare claims? [Completeness, Spec §FR-013]
- [ ] CHK018 Is "unsupported claim" defined for each of the three minimum claim kinds, including how a test count is read from gate output? [Clarity, Spec §FR-012]
- [ ] CHK019 Is the false-warning budget measurable, given the target of listing every false claim and none for true reports on 10-report sets? [Measurability, Spec §SC-003]
- [ ] CHK020 Are the four conditions "claims not checked" (missing block), "no report", "format fault" and "no mismatch" distinguished without overlap? [Consistency, Spec §FR-009, §FR-014]
- [ ] CHK021 Is the warn-only status consistent with Scenario 3 of Story 2 ("run outcome follows the gate results")? [Consistency, Spec §FR-012]

## Credential screen and hook decisions

- [ ] CHK022 Is "secret-bearing path" defined by a list or rule that a reviewer can test? [Clarity, Spec §FR-025, §FR-026]
- [ ] CHK023 Are the "cannot decide" conditions enumerated beyond the run-time path example, and is the refuse-by-default result stated for each? [Coverage, Spec §FR-026]
- [ ] CHK024 Is FR-025's escape clause (a recorded refusal the replay set cannot reproduce is "not caused by agents-inc") given a criterion, so it cannot dismiss any failing case? [Ambiguity, Spec §FR-025]
- [ ] CHK025 Are the "recorded false-deny" and "recorded bypass" forms listed or referenced by id, with a minimum count? [Gap, Spec §FR-027, §FR-028, §FR-029]
- [ ] CHK026 Is "a form the hook cannot parse" defined, so Scenario 5 and the false-allow rule in Scenario 4 cannot conflict? [Clarity, Spec §FR-028]
- [ ] CHK027 Does SC-006 define "no change to the decision for the existing passing cases" with a named baseline set? [Measurability, Spec §SC-006]

## Refusal messages

- [ ] CHK028 Is "corrected example or next command" required to be valid input, and can that be checked per rule? [Measurability, Spec §FR-022, §SC-005]
- [ ] CHK029 Is the full list of refusal rules and screens in scope named, so FR-023's no-gap test has a defined universe? [Completeness, Spec §FR-023]
- [ ] CHK030 Does the spec state how a refusal that fires on one input for two rules is reported (one message or both)? [Gap, Spec §FR-022]
- [ ] CHK031 Is the "not verified now" mark and record age format specified, and is "every surface" listed for SC-007? [Gap, Spec §FR-030, §SC-007]

## Notes

- Leave boxes unchecked until the reviewer has answered.
- Record answers inline under the item.
