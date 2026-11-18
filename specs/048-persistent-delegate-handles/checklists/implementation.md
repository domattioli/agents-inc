<!-- provenance: author=domattioli model=claude-haiku-5-5 effort=default date=2026-11-18 skill=speckit-checklist repo=agents-inc-handles session=speckit-checklist-048 -->
# Implementation Checklist: Persistent Cross-Provider Delegate Handles

**Purpose**: Unit tests for the requirements in spec.md. Each item asks whether a requirement is written clearly, completely and consistently. Focus: persistence, the `handles` CLI, and cache-prefix stability.
**Created**: 2026-11-18
**Feature**: [spec.md](../spec.md) (cross-checked against [plan.md](../plan.md) and [data-model.md](../data-model.md) only where spec.md is silent)

**Status key**: `FAIL` marks an item where spec.md, read as written, is contradicted, missing or ambiguous. The reason follows the mark.

## Persistence and Restart (FR-001, FR-002, FR-003, FR-009, FR-011)

- [ ] CHK001 - Is the on-disk location of the handle store stated in a requirement, rather than only in Clarifications? [Clarity, Spec FR-001]
- [ ] CHK002 - Does FR-001 define when "after every step" is reached, including steps that fail or are cancelled? [Completeness, Spec FR-001]
- [ ] CHK003 - Is "a host restart" defined in a way that can be detected (process exit, new host session id, or resume)? `FAIL` FR-002 and US1 rely on a restart signal that no requirement defines. [Clarity, Spec FR-002, US1]
- [ ] CHK004 - Is the FR-003 field list complete for everything the Edge Cases need? `FAIL` The edge case "keeps the old reference in its history" needs a `history` field, and FR-003 has none. [Completeness, Spec FR-003, Edge Cases]
- [ ] CHK005 - Are the value domains of FR-003 fields (state, restart reason, ceiling unit) specified in the requirement text, not only in Clarifications? `FAIL` FR-003 lists `live`, `retired`, `failed` but no restart reason values are given in the spec. [Clarity, Spec FR-003, FR-009]
- [ ] CHK006 - Is the handle lifecycle closed? spec.md defines only `live` and `retired`, with `live -> retired` by the retire command. [Completeness, Spec FR-003, Key Entities]
- [ ] CHK007 - Is the behavior of a continuation sent to a `retired` handle specified? Plan.md refuses the step; spec.md US2 independent test now states the refusal. [Completeness, Spec US2]
- [ ] CHK008 - Is the behavior specified when the handle store is corrupt and is then rewritten, including whether the corrupt file is kept? `FAIL` The Edge Case says "starts fresh" and "reports one warning", but not whether the file is overwritten. [Gap, Spec Edge Cases]
- [ ] CHK009 - Are concurrent writes to one per-session `handles.json` by parallel delegates addressed? `FAIL` The store is one file per session (Clarifications), and US3 runs parallel delegates, yet no requirement covers lost updates. [Gap, Spec Clarifications, US3]
- [ ] CHK010 - Is "thread reference still exists" (FR-002) defined as a measurable check? [Measurability, Spec FR-002]
- [ ] CHK011 - Is the compaction trigger ("host compaction shrinks the conversation below what the delegate has seen") defined with a detection rule? `FAIL` The Edge Case names the event but gives no test for it. [Clarity, Spec Edge Cases, FR-009]
- [ ] CHK012 - Is the persistence failure behavior (FR-011) defined for every failure class (write error, read error, corrupt JSON, schema mismatch)? [Coverage, Spec FR-011]
- [ ] CHK013 - Is the warning in FR-011 ("one warning per session") tied to a defined session identity? `FAIL` "Session" is not defined in spec.md. [Clarity, Spec FR-011, Edge Cases]
- [ ] CHK014 - Are the routes in scope named? `FAIL` The Input cites five routes with their own continuation ids, but the FRs address only the native loop and Mistral. Codex, Gemini, OpenRouter and the bridge are not covered. [Scope, Spec Input, FR-001 to FR-002]

## Thread Continuation and Model Binding (FR-010, US1, US3)

- [ ] CHK015 - Is "continue the recorded thread and send only messages added since the last step" measurable (what counts as "added", and how it is counted)? [Measurability, Spec US1-AS1]
- [ ] CHK016 - Is the cross-model refusal message (FR-010) specified in content or format, so it can be tested? `FAIL` FR-010 says "a clear message" with no content requirement. [Clarity, Spec FR-010]
- [ ] CHK017 - Does FR-010 say what the handle binds to? Yes: provider plus adapter nickname; the slug from the first completed step is informational. [Clarity, Spec FR-003, FR-010, Clarifications]
- [ ] CHK018 - Is the failed-step retry path (new thread, old reference kept in history) specified as a requirement and not only an Edge Case? [Completeness, Spec Edge Cases, FR-009]
- [ ] CHK019 - Are the restart reasons enumerated, so that "every restart carries a reason" (SC-004) has a closed set to check against? `FAIL` Only compaction, failed step and missing thread appear, and only in plan.md. [Completeness, Spec SC-004, FR-009]
- [ ] CHK020 - Is the stateless (free-rung) handle behavior stated in a requirement, including what the "local conversation record" is? [Clarity, Spec Edge Cases]
- [ ] CHK021 - Does the spec say what happens to a live handle when a legacy global Mistral conversation id already exists? [Gap, Spec FR-007, US3]

## Mistral Isolation (FR-007, US3, SC-002)

- [ ] CHK022 - Is the per-handle conversation id storage specified (where it lives and how the id is derived), or is that left entirely to the plan? [Clarity, Spec FR-007]
- [ ] CHK023 - Is "neither id file is shared" (US3-AS1) defined as a testable condition distinct from SC-002? [Measurability, Spec US3, SC-002]
- [ ] CHK024 - Is the Mistral global id location (noted in Clarifications as living in `mask.sh`) reflected in a requirement? [Traceability, Spec Clarifications, FR-007]

## Listing and Retire (FR-004, FR-005, US2, SC-003)

- [ ] CHK025 - Are the listing fields consistent? `FAIL` US2-AS1 lists seven fields; FR-004 requires every FR-003 field. The two requirements differ. [Consistency, Spec US2-AS1, FR-004]
- [ ] CHK026 - Is the listing surface (`agents-inc handles` launcher subcommand) stated in a requirement or only in Clarifications? `FAIL` FR-004 names no surface, and SC-003 says "one command" without naming it. [Clarity, Spec FR-004, SC-003, Clarifications]
- [ ] CHK027 - Are the CLI output modes (human text, machine-readable) and their required content defined? [Gap, Spec FR-004]
- [ ] CHK028 - Are the CLI's behaviors defined for no handles, an unknown handle id, and a handle that is already retired? [Gap, Spec FR-004, FR-005]
- [ ] CHK029 - Who asks for the handoff note on retire? `FAIL` FR-005 and US2-AS2 say the retire action asks the delegate. Clarifications say the supervisor sends the request as a normal continue step, and the CLI "never talks to a delegate". The two contradict. [Conflict, Spec FR-005, US2-AS2, Clarifications]
- [ ] CHK030 - Is the successor-seed output of retire (the instruction the supervisor receives) specified? `FAIL` FR-005 says "a successor handle is created", but the spec does not state how the note reaches the successor. [Completeness, Spec FR-005, US2-AS2]

## Ceiling and Advisory (FR-006, Clarifications)

- [ ] CHK031 - Is the ceiling unit stated in one place, consistently? `FAIL` FR-006 gives 200k tokens (300k opus), but FR-003 tracks characters and Clarifications set 800k chars (1.2M opus). FR-006 does not convert. [Conflict, Spec FR-003, FR-006, Clarifications]
- [ ] CHK032 - Is the ceiling-reached behavior (advisory only, no automatic retire) written as a requirement? `FAIL` It appears in Clarifications only; no FR covers the advisory. [Completeness, Spec Clarifications, FR-005]
- [ ] CHK033 - Is the 4-chars-per-token conversion documented as an assumption with its error bound? [Assumption, Spec Clarifications]

## Cache-Prefix Stability and Fingerprint (FR-008, US4, SC-005)

- [ ] CHK034 - Is "system text sent ahead of the conversation" defined precisely enough to tell it apart from conversation content? `FAIL` The term is used in FR-008 and US4 but never defined. Without a boundary, the fingerprint cannot be checked. [Clarity, Spec FR-008, US4]
- [ ] CHK035 - Is the fingerprint algorithm and length stated in a requirement? `FAIL` FR-008 says "short fingerprint". The FNV-1a 32-bit choice appears only in Clarifications. [Clarity, Spec FR-008, Clarifications]
- [ ] CHK036 - Is "the run record" defined (location, format, and the field name for the fingerprint)? `FAIL` US4 and SC-005 depend on a run record that no requirement describes. [Gap, Spec US4, SC-005]
- [ ] CHK037 - Is the first-step fingerprint state (no predecessor to compare with) specified? [Edge Case, Spec FR-008]
- [ ] CHK038 - Does the spec say whether a changed fingerprint is only logged, or also surfaces to the supervisor or affects the step? [Clarity, Spec FR-008, US4]
- [ ] CHK039 - Is the goal of the fingerprint (to measure churn before any freeze) matched by an acceptance criterion about cache hits? `FAIL` SC-005 measures logging only. No SC measures provider cache hits, though the Assumptions say cache is the reason for the work. [Measurability, Spec SC-005, Assumptions]
- [ ] CHK040 - Is the scope boundary (freezing the system text is out of scope) stated so that a reviewer can check the implementation does not freeze it? [Scope, Spec Assumptions]

## Non-Functional and Measurability (FR-012, SC-001 to SC-004)

- [ ] CHK041 - Is "$0 incremental spend" (FR-012) backed by a check a reviewer can run? [Measurability, Spec FR-012]
- [ ] CHK042 - Is SC-001 ("100% of continuations ... send only new messages") bounded by a stated set of exceptions, such as compaction and missing thread? [Clarity, Spec SC-001, Edge Cases]
- [ ] CHK043 - Is the handle store's retention specified as a requirement and not only as "same as `.thread` files" in Clarifications? [Clarity, Spec Clarifications, Assumptions]
- [ ] CHK044 - Are the two-session collision cases (same cwd, different sessions) covered by a requirement that names how session identity is derived? `FAIL` Only an Edge Case mentions it; no requirement says how a session is identified. [Coverage, Spec Edge Cases, FR-001]

## Dependencies, Assumptions and Ambiguities

- [ ] CHK045 - Are the "five routes" in the Input mapped to requirements or explicitly excluded? [Traceability, Spec Input]
- [ ] CHK046 - Is the Assumption that provider cache behavior on free tiers is "unverified" linked to a requirement that tests it? [Dependency, Spec Assumptions]
- [ ] CHK047 - Does the spec identify the native loop's registry (`S.agents`) as the persisted object, or leave that to the plan? [Clarity, Spec Input, FR-001]

## Notes

- Check items off as completed: `[x]`
- Items marked `FAIL` are conflicts or gaps in spec.md as written. Resolve them in spec.md or Clarifications before tasks are implemented.
- Items are numbered sequentially for easy reference.
