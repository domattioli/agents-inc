<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Requirements Quality Checklist: Hook Deny, Duplicate Registry, Recovery

**Purpose**: test whether spec 015 states its hook, registry, recovery, and skill-text requirements completely and unambiguously before implementation.
**Created**: 2026-10-01 (Supervisor, checklist phase)
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md)

## Persona deny

- [x] CHK001 Is the detection rule given as an exact pattern? [Clarity, Spec FR-002 regex]
- [x] CHK002 Are deny and allow fixtures enumerated? [Completeness, Spec Clarifications addendum, SC-001]
- [x] CHK003 Is the deny reason fixed text? [Clarity, Spec FR-002]
- [x] CHK004 Is the payload shape tied to a known-working emitter? [Spec FR-002, Plan Existing code]
- [x] CHK005 Is the scope of the deny limited to `Agent`/`Task`? [Spec Assumptions; `DelegateAgent` excluded]
- [x] CHK006 Are known whole-name collisions declared expected? [Spec addendum]
- [ ] CHK007 Is a `/` after the persona name (`<Persona>/<word>`) covered? [Gap: the local corpus shows 1 such description; the fixed regex does not match it; reported to the Executive, not acted on]
- [x] CHK008 Is the change to the "never block" contract bounded to this check? [Spec Clarifications, FR-007]

## Duplicate registry

- [x] CHK009 Is the registry location named? [Spec FR-006, Plan DD3]
- [x] CHK010 Is the task key defined? [Gap resolved in Plan DD2]
- [x] CHK011 Is the expiry stated as a number? [Gap resolved in Plan DD3: 2 hours]
- [x] CHK012 Is the override mechanism concrete? [Gap resolved in Plan DD3: prompt line `agents-inc: fan-out`]
- [x] CHK013 Is release defined for background spawns? [Plan DD5: expiry only]
- [x] CHK014 Is the failure mode of an unwritable registry specified? [Spec Edge Cases: fail open]
- [ ] CHK015 Is same-session repetition specified? [Ambiguity: spec says "any session"; Plan DD3 warns only across sessions, citing #13 evidence; accepted]

## Recovery

- [x] CHK016 Is the output bound a number? [Spec Clarifications: 4,000 characters]
- [x] CHK017 Are the summary fields enumerated? [Spec FR-005]
- [x] CHK018 Is behavior on a missing file specified? [Spec Edge Cases]
- [x] CHK019 Is the set of "write" tools defined? [Plan DD6: Write, Edit, MultiEdit, NotebookEdit; Bash writes not tracked]

## Skill text

- [x] CHK020 Is the hierarchy-line format specified? [Plan DD7]
- [x] CHK021 Is the canon-change sign-off path stated? [Spec FR-009]
- [x] CHK022 Is the lack of an automated hierarchy check justified? [Plan DD7]

## Notes

Open items CHK007 and CHK015 are accepted with the stated resolution.
