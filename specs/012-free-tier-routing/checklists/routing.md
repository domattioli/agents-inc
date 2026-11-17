<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Routing Requirements Quality Checklist: Free-Tier-Aware Routing

**Purpose**: Unit tests for the requirements text in spec.md (routing, health, caps, catalog)
**Created**: 2026-09-23
**Feature**: [spec.md](../spec.md)

## Completeness

- [ ] CHK001 Are the five stale OpenRouter entries named in the spec? [Gap, FR-002]
- [ ] CHK002 Is the modality environment variable name specified? [Gap, FR-011, Clarifications]
- [ ] CHK003 Is the outcome for "other error" specified (cooldown or not)? [Gap, FR-003/FR-004]
- [ ] CHK004 Are requirements defined for Gemini and Mistral default-model choice, or only OpenRouter? [Completeness, FR-001]
- [ ] CHK005 Is it stated which component increments the daily call count for standalone wrapper calls? [Gap, FR-008]
- [ ] CHK006 Is a limits-probe equivalent required for Mistral and Gemini, or are configured caps final? [Completeness, FR-009, FR-016]

## Clarity

- [ ] CHK007 Is "approved for the requested task" defined as `tasks_good` membership, and is `unprobed` status eligible? [Ambiguity, FR-001]
- [ ] CHK008 Is "authorized workspace" defined or referenced? [Ambiguity, FR-011]
- [ ] CHK009 Is "coding tasks" enumerated (code-write, code-review, draft?) for FR-013? [Ambiguity, FR-013]
- [ ] CHK010 Is the failure streak reset scope (per provider vs per model) specified? [Clarity, US2]
- [ ] CHK011 Is the ZDR-exclusion response signature defined well enough to detect? [Clarity, FR-005]

## Consistency

- [ ] CHK012 Does FR-011 "free providers first" agree with the existing `route.sh` class routing, which sends `code` to mistral? [Conflict, FR-013; `skills/codex-bridge/scripts/route.sh:32`]
- [ ] CHK013 Is adding `classify` consistent with FR-012 "ordering unchanged for all other tasks"? [Consistency, Clarifications]
- [ ] CHK014 Is FR numbering ordered (FR-016 precedes FR-015)? [Consistency]
- [ ] CHK015 Does the Gemini grunt default in `routing.json` (`gemini-2.5-flash`) conflict with the clarified cheap tier? [Conflict, Clarifications]

## Measurability

- [ ] CHK016 Is SC-005 measurable without a defined baseline number and metric source? [Measurability, SC-005]
- [ ] CHK017 Does SC-001 define how the 20 test runs vary? [Measurability, SC-001]

## Edge cases and recovery

- [ ] CHK018 Is behavior specified when a model becomes available again before the next refresh? [Edge case, FR-005]
- [ ] CHK019 Is behavior specified when catalog refresh sees a model that the overlay marked withdrawn but the live list still shows? [Edge case, FR-005/FR-006]
- [ ] CHK020 Is the one-warning rule scoped (per process, per file, per call)? [Clarity, FR-015]

## Non-functional

- [ ] CHK021 Is the "never spend credits" rule stated for the limits probe as well as refresh? [Completeness, FR-009, P5]
- [ ] CHK022 Is secret handling (API key never printed) stated as a requirement? [Gap, FR-009]
