# Specification Analysis Report: 022-dispatch-fail-loud

Artifacts: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/dispatch-outcomes.md`, `tasks.md`, `checklists/requirements.md`. Constitution: `AGENTS.md` project rules and `docs/DECISIONS.md`. Cycle 1 run on the first drafts; cycle 2 re-ran every detection pass on the edited artifacts (see `analyze-resolve.md`).

## Cycle 1 findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md FR-001..003, FR-013..016, FR-020..021; plan.md Source Code; tasks.md T001, T012, T022 | Spec acceptance commands name `tests.test_dispatch_failloud.<Class>` for US1, US3 and US5, but tasks split those into `test_dispatch_snapshot_trust`, `test_dispatch_broker_robust`, `test_dispatch_slot_screens` (split needed for [P]). | Rename the spec commands and plan tree to the task modules. |
| A2 | Inconsistency | HIGH | contracts/dispatch-outcomes.md "Broker result"; spec FR-012 | Contract says `dispatch_exit_code` 69 or 75 "maps to status red"; the code rewrites any code outside `REQ_STATUS` to 1 (`agents_inc/install/dispatch.py:1244`, `:1586`), so the broker result carries 1, not 69 or 75. A Lead reading the contract would branch on a value it never sees. | State that the broker result carries `dispatch_exit_code` 1 and the cause in `reason`; the CLI keeps 69/75. |
| A3 | Inconsistency | MEDIUM | research.md R5; contracts/dispatch-outcomes.md status grammar | R5 says `rc=None` then `rc=-1`; the contract has a garbled "is not claimed" sentence and `report=none snapshot=none`. | One form: `rc=-1 report=none snapshot=none outcome=red reason=launch-failed detail=<d> out=<run-dir>/stdout.md`; R5 and contract match. |
| A4 | Inconsistency | MEDIUM | plan.md Constitution Check (D58 row) | Plan names task "T040" for the DECISIONS entry; tasks.md has it as T027. | Change plan to T027. |
| A5 | Underspecification | MEDIUM | tasks.md T002; research.md R1 | T002 writes the trusted copy "after the capture at :880" and the prompt hash "after the final prompt at :928", but :928 runs only when a roster exists (`dispatch.py:917-928`), and the capture also runs for `--dry-run` (`:880` before `:912`), so dry-run tests without a fake HOME would write into the real `~/.local/state`. | Write the trusted copy and both hashes once, immediately before `launch` (after `_record_ledger_node` at `:929`); dry-run writes nothing outside the run dir. |
| A6 | Coverage gap | MEDIUM | contracts/dispatch-outcomes.md; tasks.md T003, T009 | Contract adds `snapshot=TAMPERED`, but only `detail=` and the launch-failed form are added to `STATUS_RE` (`tests/test_dispatch_cli.py:21-22`); a tamper status line fails that regex. | T003 extends `STATUS_RE` with `TAMPERED`. |
| A7 | Underspecification | HIGH | spec FR-001; research.md R1; data-model.md | The trusted store sits under `<state>` (`~/.local/state/agents-inc`, `agents_inc/install/paths.py:39`). A broker child run is launched from the broker process of a Lead, whose run dir is outside cwd and denied to Workers (`dispatch.py:1356`, D51 `docs/DECISIONS.md:573`, D57 `:618`). Writing `~/.local` there is unnecessary and may be denied where the broker inherits a Lead's sandbox [unconfirmed]. The spec does not say which store a broker child uses. | Broker children (`_BROKER_SAFE_WRITES`) keep the run-dir copy as trusted and record `snapshot_trust: "broker"`; only top-level runs use `<state>/dispatch-runs/<run-id>/`. |
| A8 | Coverage gap | HIGH | spec FR-017; tasks.md T020 | `WB_CLAUDE_NOT_FOUND` makes `ready` False on any host without `claude` on PATH, and the doctor's sandbox probe would run the real `sandbox-exec` in tests. Existing tests call `check_install` without a stub (`tests/test_install_doctor.py:24`, `:58`, `tests/test_doctor_codex_optional.py:26`, `tests/test_install_at_route.py:171`), so the suite would fail on a host without `claude` (FR-022). | Add injectable `which` and `sandbox_probe` parameters to `check_install` (same pattern as `runner`, `doctor.py:62`), defaulting to the real functions; T020 updates the existing doctor tests to pass stubs. |
| A9 | Underspecification | MEDIUM | spec FR-014; Edge Cases | The 3600 s deadline applies to every `launch()`, including direct CoS dispatches, which were unbounded; a legitimate long run would now end red `timeout`. The spec does not flag this behaviour change. | Add an edge case and Open-for-CoS item 6 (recommend: keep 3600 s default, override by env). |
| A10 | Constitution | LOW | checklists/requirements.md CHK003, CHK004 | Spec carries paths and functions, against speckit-specify's "no implementation details". The dispatch PLAN CONTRACT and `AGENTS.md` Documentation style (dispatch specs are agent surfaces) require it. | Keep; deviation recorded. |
| A11 | Duplication | LOW | spec FR-003 and FR-010 | Both change `_mirror`; FR-003 covers content trust, FR-010 error handling. | Keep separate; tasks T005 then T011 in order. |

No CRITICAL findings. No constitution MUST is violated: the D58 exit-list amendment is routed to the CoS as a canon edit with cross-vendor review (D46.10(b), `docs/DECISIONS.md:502`; tasks.md T027).

## Coverage Summary

| Requirement Key | Source | Has Task? | Task IDs | Notes |
|---|---|---|---|---|
| FR-001 trusted copy | audit 1 | yes | T001, T002, T004 | broker case added (A7) |
| FR-002 tamper check | audit 1 | yes | T001, T003 | |
| FR-003 mirror from memory | audit 1 | yes | T001, T005 | |
| FR-004 is_error | audit 3 / #88-5 | yes | T006, T007 | `is_error` key assumed |
| FR-005 quota any rc | audit 3 / #88-5 | yes | T006, T008 | |
| FR-006 blocked | audit 3 / #88-5 | yes | T006, T008 | |
| FR-007 outcome order | audit 4 | yes | T006, T008 | |
| FR-008 stderr detail | audit 4 | yes | T006, T009 | |
| FR-009 launch-failed | audit 5 | yes | T006, T010 | |
| FR-010 mirror errors | audit 6 | yes | T006, T011 | |
| FR-011 snapshot-error | audit 12 | yes | T006, T008 | |
| FR-012 exit-code map | #88-5 | yes | T006, T008, T027 | canon amendment |
| FR-013 nested probe | audit 2 | yes | T012, T013 | |
| FR-014 turn deadline | audit 7 | yes | T012, T014, T015 | |
| FR-015 locked counters | audit 13 | yes | T012, T016, T017 | |
| FR-016 wait docstring | audit 14 | yes | T012, T017 | |
| FR-017 claude check, nested warning | audit 8, 2 | yes | T018, T020 | |
| FR-018 hook warnings | audit 9 | yes | T019, T021 | |
| FR-019 probe env | audit 15 | yes | T018, T020 | |
| FR-020 allow_paths, globs | audit 10 | yes | T022, T023 | |
| FR-021 gate screen | audit 11 | yes | T022, T024 | |
| FR-022 suite green | all | yes | T025 | |
| SC-001 16/16 mapped | | yes | all test tasks | |
| SC-003 0/3 tamper | | yes | T001 | |
| SC-004 ≤5 s overrun | | yes | T012 | |

Audit findings 1-15 and #88 item 5: 16 of 16 covered.

**Constitution Alignment Issues:** none blocking; D58 amendment tracked (T027).

**Unmapped Tasks:** T026 (CHANGELOG), T028 (move to DomI) are housekeeping, mapped to AGENTS.md Governance.

**Metrics (cycle 1):** Requirements 22 FR + 6 SC; Tasks 28; Coverage 100% (22/22 FR with ≥1 task); Ambiguity 0; Duplication 1 (A11, LOW); Critical 0; High 3 (A2, A7, A8); Medium 6; Low 2.

## Cycle 2 (after edits)

Re-ran passes A-F on the edited artifacts. A1-A9 resolved (see `analyze-resolve.md` for each edit). New findings:

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| B1 | Inconsistency | LOW | data-model.md `snapshot_trust` | After A7 the field has three values; checked: data-model lists `"private"`, `"run-dir"`, `"broker"`. | None (verified consistent). |

**Metrics (cycle 2):** Critical 0; High 0; Medium 0; Low 3 (A10, A11, B1 — accepted).

## Next Actions

- No CRITICAL or HIGH open. Ready for CoS review, then `speckit-implement` from T001.
- CoS rulings needed before T008/T020/T014: Open for CoS items 2, 3, 6 in spec.md.
- The `is_error` envelope key is an assumption; a live probe by the CoS before T007 would confirm it.
