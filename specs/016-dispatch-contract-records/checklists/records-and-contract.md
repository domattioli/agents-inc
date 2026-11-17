<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Requirements Quality Checklist: Dispatch Records, Header, Tier Table

**Purpose**: test whether spec 016 states its ledger, hook, header, tier-table, and persistence requirements completely and unambiguously before implementation.
**Created**: 2026-10-01 (Supervisor, checklist phase)
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md)

## Ledger fields and run id

- [x] CHK001 Are the new fields enumerated? [Completeness, Spec FR-001]
- [x] CHK002 Is "unknown, never zero" stated for missing counts? [Clarity, Spec Edge Cases, US1 scenario 2]
- [x] CHK003 Is the allowed verdict vocabulary defined? [Gap resolved in Plan DD1: `pass`, `fail`, unknown]
- [ ] CHK004 Is "in both the JSONL and SQLite stores" achievable without a schema migration? [Conflict: SQLite has columns only for input/output tokens; Plan DD1 keeps the other fields JSONL-only and records the migration as a follow-up; reported to the Executive]
- [x] CHK005 Is the source of the return row's run id defined when the caller omits it? [Plan DD1: dispatch row lookup]

## Usage join

- [ ] CHK006 Is "join by run" defined when `usage.db` has no run column? [Ambiguity: `usage_db.py:35-46` has no run or job id; Plan DD2 defines an approximate time-window match with an ambiguity rule; reported]
- [x] CHK007 Is the behavior on a missing match specified? [Spec FR-003: unknown]
- [x] CHK008 Is "read-only" defined for a WAL database? [Plan DD2: SELECT only, no file creation]

## Hook rows and ledger append

- [x] CHK009 Are both matchers named? [Spec FR-004, Plan DD3]
- [x] CHK010 Is the row location given and the workspace ledger excluded? [Spec FR-004, Plan DD3]
- [x] CHK011 Is the timeout a number? [Spec FR-004: at most 5 s]
- [x] CHK012 Is fail-closed defined for a missing verdict, with the exit code? [Plan DD4: exit 2 and message]
- [x] CHK013 Is the orphan rule addressed? [Spec FR-004; Plan Existing code: lint has no orphan rule, test pins it]
- [ ] CHK014 Is the tier of an `Agent` call without a `model` argument specified? [Gap resolved in Plan DD3 as `unknown`; the inherited model is not visible to the hook]
- [x] CHK015 Is the `DelegateAgent` description source defined? [Plan DD3: first prompt line, 80 characters]

## Header, slots, lint

- [x] CHK016 Is the split between fixed header and per-task slots listed? [Plan DD5]
- [x] CHK017 Is "file-capable" versus "bare-API" made checkable? [Plan DD6: `--transport`]
- [x] CHK018 Is the opt-out line required in the prompt itself when `CONTRACT:` is used? [Spec US2 scenario 3, Plan DD6]
- [x] CHK019 Is the cache-savings claim gated on a measurement? [Spec FR-010]

## Tier table

- [x] CHK020 Is the rung vocabulary fixed? [Spec FR-007]
- [x] CHK021 Is fail-closed defined for an off-vocabulary tier? [Spec Edge Cases, Plan DD7]
- [x] CHK022 Is the expected id count stated? [Spec SC-003: current count at implement time; 39 at plan time]
- [ ] CHK023 Are roster ids absent from config (`codestral-latest`, `mistral-large-latest`, `gemini-3.8-flash`, `gemini-3.1-pro-preview`, `ministral-3b-latest`) reconciled? [Gap: out of scope; reported]

## Persistence and records

- [x] CHK024 Are both ceilings and the exceptions stated? [Spec FR-008, Plan Appendix D2]
- [x] CHK025 Is per-backend resume support stated? [Spec FR-008, #28 comment]
- [x] CHK026 Is the #27 deliverable location fixed and DomI excluded? [Spec FR-009]

## Notes

- Open items CHK004, CHK006, CHK014, CHK023 are reported in the batch D report. CHK014 is resolved in the plan and kept open only to show the information limit.
