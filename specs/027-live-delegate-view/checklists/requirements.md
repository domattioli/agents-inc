<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-checklist repo=agents_Inc session=unknown -->
# Requirements Quality Checklist: Live delegate view

**Purpose**: Test that spec.md requirements are complete, clear, consistent and measurable before implement.
**Created**: 2026-10-24
**Feature**: [spec.md](../spec.md)

## Content quality

- [x] CHK001 Each user story has a priority, an independent test and Given/When/Then scenarios. [Completeness, Spec §User Scenarios]
- [x] CHK002 Code facts the requirements rest on are tagged [verified] with file:line or [assumed]. [Traceability, Spec §Background, §Assumptions]
- [x] CHK003 Operator-facing decisions the dispatch named (mod location and install, row format, rate limit, cancel, redaction, tests) each have a requirement. [Completeness, FR-014..FR-027]

## Requirement completeness

- [x] CHK004 The event envelope fields and their types are stated. [Clarity, FR-001]
- [x] CHK005 Every dispatch exit path has a `run.end` outcome value. [Completeness, FR-002, FR-011]
- [x] CHK006 Unchanged outputs are named file by file. [Clarity, FR-006]
- [x] CHK007 Limits are numeric: 64 KiB line, 64 MiB file, 240/120-char rows, 1 s / 20-row batches, 600 notices, 60 s held-back notice, 30 s follow wait, 5 s kill. [Measurability, FR-009, FR-014, FR-016, FR-022, FR-013, SC-004]
- [x] CHK008 Cancel covers both the catchable-signal path and the SIGKILL gap. [Coverage, FR-011, FR-012, FR-024]
- [x] CHK009 Redaction sources are listed and the replacement text is fixed. [Clarity, FR-015]
- [x] CHK010 The relay agent's model, tools and turn cap are fixed values. [Clarity, FR-018]
- [x] CHK011 Tool refusals are listed with their trigger. [Completeness, FR-020, Edge Cases]
- [ ] CHK012 Free-provider (gemini, mistral, openrouter) live view has requirements. [Gap, Q1 PENDING OPERATOR: deferred by recommendation]
- [ ] CHK013 Codex Lead runs get provider events. [Gap, Q5 PENDING OPERATOR: lifecycle only by recommendation]

## Requirement consistency

- [x] CHK014 Row kind (`system` notice) is the same in spec, plan and tasks. [Consistency, FR-021, Plan B1, T025]
- [x] CHK015 Tool name `mcp__agents-inc__run` and agent type `agents-inc:relay` match the plugin name `agents-inc`. [Consistency, FR-017..FR-019]
- [x] CHK016 The verdict-line rule (unchanged except `cancelled`) agrees between FR-006 and FR-011. [Consistency]
- [x] CHK017 Install path is an operator step everywhere; nothing in agents-inc writes `~/.claude/**`. [Consistency, Q2, FR-028, Plan Constitution Check P1]

## Acceptance criteria quality

- [x] CHK018 Each success criterion names the test that measures it. [Measurability, SC-001..SC-005]
- [x] CHK019 Golden byte-equality is the measure for "unchanged outputs". [Measurability, SC-002, T009]
- [ ] CHK020 The 2 s latency in SC-001 is measured on a real host, not only on stubs. [Gap: covered only by T043 manual check]

## Dependencies and assumptions

- [x] CHK021 Assumed external shapes (Claude stream-json, Codex event types, engine kill signal, spawn environment) are listed with the task that checks them. [Assumptions, research R1, R2, R4; T010, T043]
- [x] CHK022 Cost stays $0 incremental. [Constitution P5, Assumptions]

## Notes

- Open items CHK012, CHK013 follow the PENDING OPERATOR clarifications; CHK020 is accepted as a manual check.
