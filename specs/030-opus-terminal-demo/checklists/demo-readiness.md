<!-- provenance: author=domattioli model=claude-fable-5-1 effort=low date=2026-11-06 skill=speckit-analyze repo=agents_Inc session=c5e2753c -->
# Demo Readiness Checklist: Opus-orchestrated terminal demo of agents-inc

**Purpose**: Check that the requirements for the terminal demo are written clearly, completely and consistently before the first recorded run.
**Created**: 2026-11-06
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [tasks.md](../tasks.md)
**Audience**: the implementer, and the operator before the first recorded run.
**Depth**: standard.

## Requirement Consistency

- [x] CHK001 (resolved in spec US1 scenario 5, 2026-11-06) - Does the ledger requirement in User Story 1 (the row names delegate, rung, outcome and verifier) match the dispatch row fields the plan says exist? [Conflict, Spec §US1 scenario 5, Plan §Spec conflicts 1]
- [ ] CHK002 - Is it stated which record holds the supervisor verdict, given that `ledger pending` shows no outcome or verifier field? [Gap, Plan §Spec conflicts 1]
- [x] CHK003 - Does the beat count agree between FR-002 (five core beats) and the seven beats in plan.md point 2? [Consistency, Spec §FR-002, Plan §2]
- [ ] CHK004 - Are the names and order of the beats defined in one place, so the printed beat lines and the spec beats cannot drift apart? [Consistency, Spec §FR-004, Plan §2]
- [x] CHK005 - Does FR-005 (only Claude and Codex subscriptions, no paid fallback) allow the free-model beat that FR-010 requires from Mistral, Gemini or OpenRouter? [Conflict, Spec §FR-005, Spec §FR-010]
- [ ] CHK006 - Is the free-model state `maybe` (key may exist only in `~/Projects/.env`) defined in the spec, or only in the plan? [Gap, Spec §FR-010, Plan §Spec conflicts 2]
- [ ] CHK007 - Is the expected result when a free-model key is `maybe` defined: try the wrapper, then skip with one NOTE line? [Clarity, Plan §4, Spec §FR-010]
- [ ] CHK008 - Does the review-independence rule in plan.md (separate dispatch, shared model when codex is absent) appear in the spec, or only as a plan decision? [Gap, Plan §Spec conflicts 4]
- [ ] CHK009 - Do the trial directory rules (spec: copy SPEC.md only; plan: trial dir inside the repo under `.scratch/`) agree on location and contents? [Consistency, Spec §Key Entities, Plan §Spec conflicts 3]

## Requirement Completeness

- [ ] CHK010 - Are the required inputs for the runner (doctor state, codex presence, key presence, asciinema and agg presence) listed in one place in the spec? [Completeness, Spec §Key Entities, Plan §1]
- [ ] CHK011 - Is the behavior specified when `agents-inc doctor` does not print `READY`? [Completeness, Plan §1 step 1]
- [ ] CHK012 - Are the requirements for the cast and GIF (who starts recording, who stops it, where files go) defined for every case, including when asciinema or agg is absent? [Completeness, Spec §FR-008, Plan §1 step 7]
- [ ] CHK013 - Is the 600-row cap on relay events (spec edge case) assigned to a named component, and is the message shown when the cap is hit defined? [Gap, Spec §Edge Cases, Plan §2]
- [ ] CHK014 - Is it defined what happens to the trial directory and its retry when the dispatch reports `snapshot-not-clean` (spec says the session cleans and retries once; the plan does not say)? [Gap, Spec §Edge Cases]
- [ ] CHK015 - Is the quota-pause escalation rule (one failed attempt, then ladder or stop) stated with the exact steps the demo session takes? [Clarity, Spec §Edge Cases]

## Requirement Clarity

- [x] CHK016 - Is "runnable in under 10 minutes wall clock" (FR-001) defined to include or exclude the operator's paste and reading time? [Clarity, Spec §FR-001, Spec §SC-002]
- [ ] CHK017 - Is "shown working live" (User Story 1, scenario 3) measurable, or is it only a viewer's impression? [Measurability, Spec §US1 scenario 3]
- [ ] CHK018 - Is "clickable" relay row defined as an observable requirement of the transcript, or as a tool feature the demo depends on? [Clarity, Spec §FR-009, Spec §US1 scenario 3]
- [ ] CHK019 - Is "the judge exits 0" (SC-003, "2 runs out of 3") defined with a clear pass rule for the runs that do not pass? [Clarity, Spec §SC-003]
- [ ] CHK020 - Are the words "free model" and "free_order" defined in the spec with their meaning for the demo? [Ambiguity, Spec §FR-010, Plan §4]

## Acceptance Criteria and Measurability

- [x] CHK021 - Can SC-001 ("a first-time viewer can name all five beats") be checked without a fixed viewer protocol? [Measurability, Spec §SC-001]
- [ ] CHK022 - Are the per-beat time budgets in plan.md point 8 linked to a requirement that says what happens when a beat runs over? [Gap, Plan §8, Spec §FR-001]
- [ ] CHK023 - Does SC-005 (Claude-only machine completes all beats except luna) name which beats count as "all" and which as the skipped luna beat? [Clarity, Spec §SC-005, Spec §US3]
- [x] CHK024 - Does SC-004 ($0 API spend per run) define how spend is measured, given that the free-model beat calls a provider? [Measurability, Spec §SC-004, Spec §FR-005]

## Scenario and Edge Case Coverage

- [ ] CHK025 - Are requirements defined for the case where the delegate claims PASS and the judge fails, beyond "call the demo red"? [Coverage, Spec §Edge Cases]
- [ ] CHK026 - Is the relay refusal path (`MOD_NOT_INSTALLED` or relay refused) covered for each beat that uses the relay, not only in plan.md? [Coverage, Plan §2, Spec §FR-009]
- [ ] CHK027 - Are requirements defined when the Claude Code sandbox blocks the free-model host? [Gap, Plan §4 (assumed)]
- [ ] CHK028 - Is there a requirement for a re-run after a failed live run, including whether the same trial directory may be reused? [Gap, Spec §Edge Cases, Plan §1 step 4]

## Non-Functional and Output Requirements

- [ ] CHK029 - Does the spec say whether the demo lines must be plain English for viewers, given that the Assumptions section says caveman ultra runs in the same terminal? [Conflict, Spec §Assumptions]
- [ ] CHK030 - Is the requirement that the runner never reads a key value stated in the spec, or only in the plan? [Gap, Spec §FR-005, Plan §Constitution Check P1]

## Dependencies and Assumptions

- [ ] CHK031 - Are the assumed dependencies (asciinema, agg, codex, the `agents-inc` mod with the relay and luna types) each stated as required, optional, or assumed, with the fallback for each? [Dependency, Plan §Technical Context, Spec §FR-006]
- [ ] CHK032 - Is the Homebrew install line for asciinema and agg marked as an assumption that must be probed before the demo is shown? [Assumption, Plan §1]
- [ ] CHK033 - Are the dependencies on spec 027 (live view, `events.jsonl`) and spec 028 (native luna, D69) stated as requirements the demo needs, with the state each must be in? [Dependency, Spec §Background]
- [ ] CHK034 - Is the readability of a native subagent transcript (model and per-step usage) stated as a known unknown in the spec, or does User Story 2 assume it? [Assumption, Spec §US2 scenario 2, Plan §5]
