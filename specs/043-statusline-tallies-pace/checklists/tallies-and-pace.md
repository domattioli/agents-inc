<!-- provenance: author=domattioli model=claude-haiku-5-5 effort=default date=2026-11-15 skill=speckit-checklist repo=agents-inc session=b437620e -->
# Tallies and Pace Requirements Checklist: Status line true tallies and pace colours

**Purpose**: Validate the quality of the written requirements for true tallies (FR-001 to FR-008) and pace-based colouring (FR-009 to FR-015) before implementation. Reviewer audience, pre-implementation.
**Created**: 2026-11-15
**Feature**: [spec.md](../spec.md)

**Note**: This checklist tests the requirements text, not the implementation. Each item asks whether a requirement is complete, clear, consistent, measurable, or covers its edge cases. Leave boxes unchecked until the reviewer has resolved the item in the spec.

## Requirement Completeness

- [ ] CHK001 Are the operator rulings that this spec replaces or folds in (ruling items 1 to 14, and the 2026-11-09 row ruling) reproduced in the spec, or does the spec depend on an external `SPEC.md` for them? [Traceability, Spec §Assumptions, FR-008]
- [ ] CHK002 Is the pace window for SESS (session duration, grey under 30 minutes) stated as a Functional Requirement, or only in Edge Cases and Clarifications? [Completeness, Spec §Edge Cases, FR-010]
- [ ] CHK003 Are the rules for how a configured pin is declared (where it is configured, its format, and what happens when the pinned id has no usage) specified? [Gap, Spec §US3 scenario 3, FR-008]
- [ ] CHK004 Is a backward-compatibility requirement for the cache schema stated in the spec (old renderer on new cache, new renderer on old cache), or only in the contract file? [Gap, Spec §FR-016]
- [ ] CHK005 Are stale-cache thresholds (how old a window may be before it renders grey) specified as a number? [Gap, Spec §Edge Cases]
- [ ] CHK006 Is the source and operator approval of the prices for `claude-fable-5-2` and `claude-haiku-5-5` recorded in the spec, or only assumed? [Assumption, Spec §FR-002, Assumptions]
- [ ] CHK007 Is the "flagged" marker for a fallback-priced entry defined: what is flagged, where it appears, and who sees it? [Ambiguity, Spec §Assumptions]
- [ ] CHK008 Are requirements stated for a model whose first-seen date is missing or whose usage predates the source retention? [Gap, Spec §FR-012, Key Entities]

## Requirement Clarity

- [ ] CHK009 Is "family" (same provider and name stem) defined precisely enough to derive from any model id, including dated suffixes and multi-part version numbers? [Clarity, Spec §Key Entities, Clarifications]
- [ ] CHK010 Is "nearest id" in the family price fallback defined with a version-comparison rule, or only as "highest at or below, else lowest above"? [Clarity, Spec §FR-002, Clarifications]
- [ ] CHK011 Are the day boundaries for "local calendar days" (OpenAI 7D and 28D, FR-007) specified, including the timezone and DST behaviour? [Clarity, Spec §FR-007, US4]
- [ ] CHK012 Is "cannot be reconciled" (FR-004, US2 scenario 3) defined by a testable rule, given Clarifications say there is no tolerance? [Ambiguity, Spec §FR-004, Clarifications]
- [ ] CHK013 Is the expected-dollars window length for the pace ratio r defined for each of SESS, 5H, 1D, 7D and 28D? [Clarity, Spec §Key Entities "Pace ratio r"]
- [ ] CHK014 Is the value of r specified when expected dollars are zero and actual dollars are positive? [Gap, Spec §FR-013]
- [ ] CHK015 Does the NO_COLOR edge case identify which cell text changes, given it says "no output difference except in the text of cells"? [Ambiguity, Spec §Edge Cases]
- [ ] CHK016 Does FR-005 require the in-window token measurement itself, or does it defer it ("the plan picks the measurement") so that the requirement is not testable from the spec alone? [Gap, Spec §FR-005, Clarifications Q3]

## Requirement Consistency

- [ ] CHK017 Do the Clarifications (28D keeps its lifetime-rate rule) agree with FR-010 and FR-012 (model 28D cells paced against the model's own 28-day rate)? [Conflict, Spec §FR-010, FR-012, Clarifications]
- [ ] CHK018 Does FR-003 (no entry and no priced family member gives null) include the OpenAI estimate-map step added by Clarifications, or does the requirement text contradict it? [Conflict, Spec §FR-003, Clarifications]
- [ ] CHK019 Is the 28D neutral rule (grey `CN` when history is 28 days or less) stated in a Functional Requirement, or only in Clarifications? [Consistency, Spec §Clarifications, FR-010]
- [ ] CHK020 Does FR-012 state whether the family baseline includes the model's own usage, and does Story 5 scenario 4 agree? [Ambiguity, Spec §FR-012, US5 scenario 4]
- [ ] CHK021 Are the Clarifications, which the supervising session answered and not the operator, marked as needing operator confirmation before implementation? [Assumption, Spec §Clarifications]

## Acceptance Criteria Quality

- [ ] CHK022 Is "about 1,258" (SC-002) given a numeric tolerance, so the check is objective? [Measurability, Spec §SC-002]
- [ ] CHK023 Is SC-008 (a reader names the above-normal model "in under 10 seconds") replaced by a measurable check, given it depends on a human reader? [Measurability, Spec §SC-008]
- [ ] CHK024 Are the reference environment and the warm-state definition for the "under 0.40 s" render limit specified? [Measurability, Spec §SC-009, FR-017]
- [ ] CHK025 Are the colour outputs for cyan, mid and magenta (permille values or escape codes) specified so that SC-007 can be checked in truecolor and 256-colour modes? [Measurability, Spec §SC-007, FR-013]
- [ ] CHK026 Is "the same fixture" in SC-010 defined, so that byte-identical output can be compared before and after the change? [Measurability, Spec §SC-010]

## Scenario and Edge Case Coverage

- [ ] CHK027 Are requirements defined for OpenAI token counts when the thread store is absent but the usage db is present (partial sources)? [Coverage, Spec §Edge Cases, FR-017]
- [ ] CHK028 Are requirements defined for a pin that names a model with no usage in the last 28 days? [Edge Case, Spec §FR-008]
- [ ] CHK029 Are requirements defined for the renderer reading the cache while the collector is writing it? [Gap, Spec §Edge Cases]

## Non-Functional Requirements

- [ ] CHK030 Are accessibility requirements defined for distinguishing cool, mid and hot cells without relying on colour alone, given SC-008 and FR-015 forbid a legend? [Gap, Spec §SC-008, FR-015]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline
- Items are numbered sequentially for easy reference
