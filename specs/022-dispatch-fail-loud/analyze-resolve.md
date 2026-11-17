# Analyze resolution log: 022-dispatch-fail-loud

Findings from `analyze.md`. Cycle 1 edits applied 2026-10-18; cycle 2 re-ran the detection passes on the edited files.

| ID | Severity | Edit made | Files | Status |
|---|---|---|---|---|
| A1 | MEDIUM | Spec acceptance commands renamed to the task modules: US1 `tests.test_dispatch_snapshot_trust` (`SnapshotTrustTest`, `MirrorPromptTest`), US3 `tests.test_dispatch_broker_robust`, US5 `tests.test_dispatch_slot_screens` (`AllowPathsTest`, `ScopeGlobTest`, `GateScreenTest`). Plan source tree lists all six NEW test files and the four touched ones; scale line corrected. | spec.md FR-001..003, FR-013..016, FR-020..021; plan.md | resolved |
| A2 | HIGH | FR-012 and the contract's broker section now say a quota or blocked broker child yields `dispatch_exit_code` 1 (`dispatch.py:1244`) and the Lead branches on `reason`; only the CLI carries 69/75. | spec.md FR-012; contracts/dispatch-outcomes.md | resolved |
| A3 | MEDIUM | One launch-failed form everywhere: `rc=-1 report=none snapshot=none outcome=red reason=launch-failed detail=<d> out=<run-dir>/stdout.md`, empty `stdout.md`. Garbled sentence removed; grammar shows `none` alternatives. | research.md R5; contracts/dispatch-outcomes.md | resolved |
| A4 | MEDIUM | Plan D58 row now names T027. | plan.md | resolved |
| A5 | MEDIUM | Trusted copy and both hashes written once, immediately before `launch` (after `:929`), never on `--dry-run` (`:912-915`) or refusal. | tasks.md T002; research.md R1; data-model.md; spec.md FR-001 | resolved |
| A6 | MEDIUM | T003 extends `STATUS_RE` with `TAMPERED`; contract grammar and bullet list it; Dependencies orders T003, T009, T010 edits to `tests/test_dispatch_cli.py`. | tasks.md T003, Dependencies; contracts/dispatch-outcomes.md | resolved |
| A7 | HIGH | Broker children trust the broker-owned run dir, write nothing under `~/.local`, record `snapshot_trust: "broker"`; top-level runs use the state dir (`"private"`). T001 tests the broker and dry-run cases and patches `HOME`. | spec.md FR-001, Open item 5; research.md R1; data-model.md; tasks.md T001, T002 | resolved |
| A8 | HIGH | `check_install` gains injectable `which` and `sandbox_probe`; T020 updates every existing `check_install(` call (13 sites, verified by grep) to pass stubs; T018 uses the params; T020 acceptance adds `tests.test_install_at_route`. | spec.md FR-017; tasks.md T018, T020; plan.md tree | resolved |
| A9 | MEDIUM | Edge case added for long direct dispatches; Open for CoS item 6 (recommend 3600 s default, env override, `0` = none). | spec.md Edge Cases, Open for CoS | resolved (ruling pending CoS, not blocking) |
| A10 | LOW | none; deviation required by the dispatch PLAN CONTRACT. | checklists CHK003, CHK004 | accepted |
| A11 | LOW | none; ordering T005 then T011 already in Dependencies. | spec.md FR-003, FR-010 | accepted |

## Cycle 2

Re-ran duplication, ambiguity, underspecification, constitution, coverage and inconsistency passes on spec.md, plan.md, research.md, data-model.md, contracts/dispatch-outcomes.md, tasks.md.

| ID | Severity | Finding | Status |
|---|---|---|---|
| B1 | LOW | `snapshot_trust` values: data-model.md now lists `"private"`, `"broker"`, `"run-dir"`, matching spec FR-001, research R1, tasks T002/T004. Confirmed consistent. | accepted |

Open CRITICAL: 0. Open HIGH: 0. Open MEDIUM: 0.
