<!-- provenance: author=domattioli model=claude-opus-5-5 effort=low date=2026-10-28 skill=speckit-checklist repo=agents_Inc session=b027a483-3613-4691-bfdd-d5c85383077c -->
# Requirements Quality Checklist: sandbox-compat

**Purpose**: Unit tests for the English in spec.md, plan.md and tasks.md. Tests requirement quality, not implementation.
**Created**: 2026-10-28
**Feature**: specs/029-sandbox-batch
**Domain**: sandbox-compat (test hermeticity, doctor probe correctness, docs)
**Depth**: standard. **Audience**: PR reviewer. **Focus**: probe fail-closed behavior, temp-file hygiene, doc accuracy.
**Citation key**: Spec = spec.md, Plan = plan.md, Tasks = tasks.md, Research = research.md, Gap = absent from all four.

## Probe fail-closed behavior

- [ ] CHK001 Are requirements stated for what doctor reports when the probe itself fails (child cannot start, child killed, output unparsable), rather than only for per-host outcomes? [Gap, Spec §FR-005, Spec §FR-008]
- [ ] CHK002 Does the spec require that a probed host with no result row defaults to blocked, so READY is never printed for a host the probe did not report? [Gap, Spec §FR-007, Spec §FR-012, Plan §Grill]
- [ ] CHK003 Is the status classification (reachable, blocked, cert) defined in the spec itself, including whether HTTP 4xx or 5xx responses count as reachable? [Gap, Spec §FR-006]
- [ ] CHK004 Is a timeout explicitly assigned to one status (blocked) so the three-way classification is exhaustive? [Clarity, Spec §FR-006, Spec §Edge Cases]
- [ ] CHK005 Is the "bounded time per host" requirement in FR-008 consistent with a probe that uses one shared child budget for both hosts? [Conflict, Spec §FR-008, Plan §Technical Context]
- [ ] CHK006 Are the plan's two worst-case timing statements (probe at most 18 s; both hosts unreachable at most 12 s) reconciled with each other and with the under-20 s target in SC-005? [Conflict, Plan §Technical Context, Spec §SC-005]
- [ ] CHK007 Is it stated whether a model-host certificate failure is blocking, given FR-012 names only "unreachable" as blocking? [Ambiguity, Spec §FR-012, Spec §Clarifications, Plan §Data model]
- [ ] CHK008 Does the spec say where the GitHub certificate check runs (inside the dispatch-env child per FR-005, or a separate gh call in the caller environment as the plan describes)? [Conflict, Spec §FR-005, Spec §US2 AS3, Plan §Phase B]
- [ ] CHK009 Is the behavior when gh is absent defined as one outcome, or left as "uses a plain HTTPS request instead, or reports gh absent"? [Ambiguity, Spec §Edge Cases]
- [ ] CHK010 Are the child environment requirements stated in the spec (proxy variables excluded, credential variables excluded), or only referenced through "same environment dispatch gives a Worker"? [Clarity, Spec §FR-005, Spec §Assumptions]
- [ ] CHK011 Is the residual false-positive risk for a certificate failure caused by a keychain-trusted but Python-untrusted CA either accepted in the spec or assigned to a requirement? [Gap, Plan §Grill]
- [ ] CHK012 Are stable probe code names required by the spec, or only the phrase "stable code" with names appearing only in the plan? [Gap, Spec §US2 AS1, Spec §Key Entities, Plan §Data model]

## Probe scope and flag

- [ ] CHK013 Is the flag name settled, or does the spec still treat --probe-dispatch as a "working name"? [Ambiguity, Spec §Clarifications]
- [ ] CHK014 Is the baseline for "no network calls beyond what it makes today" (US2 AS4) defined, and does the spec say whether the probe combines with --live-model? [Clarity, Spec §US2 AS4, Plan §Constraints]
- [ ] CHK015 Is the sandbox-detection criterion for omitting sandbox hints defined, or only the outcome (hints omitted on Linux)? [Clarity, Spec §Edge Cases, Plan §Contract: CLI]

## Temp-file hygiene

- [ ] CHK016 Is the cleanup requirement in FR-001 self-contained, or does "every exit path they remove it on today" make the required cleanup depend on current behavior? [Clarity, Spec §FR-001]
- [ ] CHK017 Does the temp-file requirement cover the fixed /tmp/oask_response.json path that the plan moves into the same temp scheme, or is that path absent from the spec? [Gap, Spec §FR-001, Plan §Wrapper changes, Research §R1]
- [ ] CHK018 Do the spec's TMPDIR-unset fallback (/tmp) and the research finding (macOS mktemp falls back to /var/folders) agree on which directory is required? [Conflict, Spec §Edge Cases, Research §R1]
- [ ] CHK019 Is the option to send health-report stderr to /dev/null instead of a temp file accepted or excluded by the spec, given FR-001 requires a unique temp file? [Ambiguity, Spec §FR-001, Research §R1]
- [ ] CHK020 Is the unwritable-TMPDIR outcome specified with a measurable criterion (exit code equal to the writable-TMPDIR run, and the named "health report failed" line)? [Measurability, Spec §Edge Cases]

## Test hermeticity

- [ ] CHK021 Does FR-002 enumerate or bound the set of tests that start a wrapper or routing script, or can "every test" be read more widely? [Completeness, Spec §FR-002, Plan §Test changes]
- [ ] CHK022 Is "host's temp policy" in FR-002 defined well enough to know what the test must be insulated from? [Clarity, Spec §FR-002]
- [ ] CHK023 Does the spec resolve the conflict between FR-003 requiring the same test count and US1 AS2 allowing skip counts to differ? [Conflict, Spec §FR-003, Spec §US1 AS2, Spec §SC-001]
- [ ] CHK024 Is the unsandboxed comparison run required to be recorded with its counts somewhere the spec names, so the "same count" criterion is measurable? [Measurability, Spec §FR-003, Tasks §T036]
- [ ] CHK025 Is the requirement that the FR-004 cause be "recorded in the plan" consistent with the plan's own pointer to research.md and D70 as the record? [Conflict, Spec §FR-004, Plan §Phase 0, Tasks §T001]
- [ ] CHK026 Is the assumption that the sandbox sets a writable per-command TMPDIR stated with a requirement to verify it, or left as an unverified assumption? [Assumption, Gap, Spec §Assumptions]

## Doc accuracy

- [ ] CHK027 Is the #122 cause described with one level of certainty across the spec, given Assumptions states the cause as fact while FR-010 and US4 AS2 require "not confirmed"? [Conflict, Spec §Assumptions, Spec §FR-010, Spec §US4 AS2]
- [ ] CHK028 Does FR-009 require the same wording in both the prompt contract and the quick reference, as US3's Independent Test implies, or only the presence of the rule? [Consistency, Spec §FR-009, Spec §US3 Independent Test]
- [ ] CHK029 Is the 14-field prompt contract's location, and the requirement that its field count stays at 14, stated in the spec rather than only in the plan? [Traceability, Gap, Spec §US3, Plan §Constitution Check]
- [ ] CHK030 Is the upstream-link requirement in US4 AS2 defined for the case where no report is filed, so the doc does not ship an open placeholder? [Ambiguity, Spec §US4 AS2, Plan §Phase C]
- [ ] CHK031 Does the spec require the docs to name the same probe codes the doctor emits (for example WB_GITHUB_CERT), or does that link exist only in the tasks? [Gap, Spec §FR-010, Tasks §T031]
- [ ] CHK032 Is the "consistent with D66" requirement in FR-007 self-contained, or does the spec leave the content of D66 undefined? [Dependency, Spec §FR-007, Plan §Contract: CLI]

## Scope and dependencies

- [ ] CHK033 Does the spec state the end-of-work move of spec artifacts to DomI, or does that step appear only in the tasks? [Gap, Tasks §T038]
- [ ] CHK034 Is the existing uncommitted change to skills/workerbee/SKILL.md (present in the working tree before this run) addressed in the spec's scope or assumptions, given the plan edits that same file? [Gap, Plan §Phase C, Spec §Assumptions]
