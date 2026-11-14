<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-14 skill=speckit-implement repo=agents-inc session=91aeecb8 -->
# Tasks: Unified delegate pane

**Input**: specs/040-unified-delegate-pane/ (plan.md, spec.md, research.md, data-model.md, contracts/pane-contract.md, quickstart.md)
**Tests**: requested (FR-013, SC-003). Each code task has its test written first or in the same task. Port all manager tests, keep all delegate-pane tests (total >= the T001 baseline sum (measured 2026-11-14: 113)).
**Where**: DOCKER = dev and tests run in the container (docs/CONTRIBUTING.md). MAC = install and live checks only. OPERATOR = operator-gated.
**Format**: `- [ ] T### [P?] [Story?] Description with path`

## Phase 1: Setup

- [x] T001 DOCKER Record baseline: run mod tests in mods/delegate-pane/hooks and `python3 -m unittest tests.test_mod_install tests.test_delegate_pane_rungs`; note counts (expect 91 pane-side plus 22 manager) in a scratch note, not committed; record exact per-file counts as the SC-003 floor
- [x] T002 [P] DOCKER Read mods/agents-manager/hooks/register.tsx and manager.test.tsx; list pure logic, JSX, and module-level maps (JOBS, STOP_ASKED, DONE, AT) to move

## Phase 2: Foundational (blocks all stories)

- [x] T003 DOCKER Create PaneState object (reset at session.start) to replace module-level maps, with a reset test, in mods/delegate-pane/hooks/tree.ts and mods/delegate-pane/hooks/tree.test.ts (risk R-e)
- [x] T004 [P] DOCKER Write tree tests first: rows, nesting, job rows, KEEP_RUNS=8, STALE/RECENT, model and effort lists, argv builders, slotsFor, free run, dedupe by agentId and run dir (R3) in mods/delegate-pane/hooks/tree.test.ts
- [x] T005 DOCKER Implement pure tree logic ported from agents-manager in mods/delegate-pane/hooks/tree.ts until T004 passes
- [x] T006 DOCKER Write dedupe and poll tests (one delegate = one row and one marker; stdout/stderr tails read only for failed or new runs, R-d) in mods/delegate-pane/hooks/poll.test.ts
- [x] T007 DOCKER Implement poll.ts: one 1 s poll producing PollResult {agents, treeRows, delegates, finalRuns, lostRuns, mapNote, note}; extend readRuns with tree fields, in mods/delegate-pane/hooks/poll.ts

## Phase 3: User Story 1 - One pane shows the whole picture (P1)

**Goal**: one pane with map, status line, feed, tree. **Independent test**: fresh session opens one pane with all four; empty-state texts correct.

- [x] T008 [US1] DOCKER Update mods/delegate-pane/hooks/pane.test.tsx first: section order map, status, feed, tree; empty states "Nothing is running." and "no delegates yet"; one auto-open; `/delegate-pane` reopens; replace native-list tests with tree tests; no `agents-inc luna status` spawn
- [x] T009 [US1] DOCKER Rewire mods/delegate-pane/hooks/register.tsx: wiring only, one `$.clock.every(1000)` calling poll.ts, compose sections, ui.render routing by requestId prefix, ui.close; drop "Native agents this session", native types list, luna status spawn (FR-008, FR-009)
- [x] T010 [P] [US1] DOCKER Add tree section component (main root row, nested rows, click to open agent view) in mods/delegate-pane/hooks/controls.tsx
- [x] T011 [US1] DOCKER Test that acknowledgements under `session:<id>` still load (FR-010) in mods/delegate-pane/hooks/pane.test.tsx; assert mission map, stations, lost state, static fallback tests (FR-005) still pass

## Phase 4: User Story 2 - Start and steer from the pane (P2)

**Goal**: form and message box keep all agents-manager behaviour. **Independent test**: start native, Codex, free; click, message, cancel.

- [x] T012 [US2] DOCKER Port mods/agents-manager/hooks/manager.test.tsx to mods/delegate-pane/hooks/controls.test.tsx: all 22 tests, retarget pane id to `agents-inc-delegates` and timing to 1 s, no assertion weakened (R-a)
- [x] T013 [US2] DOCKER Move new-agent form, message box, run sub-pane `run-<runDir>`, cancel, ask-to-stop, resume, free-run refusal into mods/delegate-pane/hooks/controls.tsx until T012 passes (FR-004, FR-006, FR-007); ensure its test asserts the free-run note "this run takes no messages"
- [x] T014 [US2] DOCKER Add narrow toggle: `NARROW_COLS = 34` beside `layoutFor`, one-line `▸ new agent / message` button, `controlsOpen` in `$.state`; tests in mods/delegate-pane/hooks/controls.test.tsx
- [x] T015 [US2] DOCKER Separate reviewer diffs the ported assertion list against the original manager.test.tsx (P3)

## Phase 5: User Story 3 - Install migrates cleanly (P2)

**Goal**: only delegate-pane 0.6.0 installed; a repeat run is a no-op.

- [x] T016 [US3] DOCKER Update tests/test_mod_install.py (lines ~176-241) first: PANE_MODS is delegate-pane only; migration uninstalls listed retired plugins and removes retired marketplaces present in known_marketplaces.json; clean machine installs only delegate-pane; second run makes no CLI write calls; non-zero uninstall is a notice (R-c); test a stale luna-pane-local marketplace entry with no listed plugin is removed
- [x] T017 [US3] DOCKER Edit agents_inc/install/cli.py: `PANE_MODS` delegate-pane only, add `RETIRED_PANE_MODS` (agents-manager@agents-manager-local, luna-pane@luna-pane-local), conditional uninstall in install_pane_mods, keep retired entries in MOD_UNINSTALL_ARGVS, drop the agents-manager loop entry near line 87
- [x] T018 [P] [US3] DOCKER Edit agents_inc/install/bundle.py: remove `mods/agents-manager` from OPTIONAL_ALLOWLIST; extend its test
- [x] T019 [US3] MAC Operator runs the agents-inc installer; confirm `claude plugin list` shows delegate-pane 0.6.0 only; run again: no changes, no warnings (Mac has 0.2.0 today, R-f); confirm known_marketplaces.json has no luna-pane-local or agents-manager-local entry (Done by operator 2026-11-14: install ran twice; only delegate-pane listed; known_marketplaces has 0 retired entries.)

## Phase 6: User Story 4 - Repository leftovers cleaned (P3)

- [x] T020 [US4] DOCKER Delete the mods/agents-manager directory from git after T012, T013, T017, T018 are green
- [x] T021 [P] [US4] DOCKER Remove untracked stray dirs: mods/agents-manager/.scratch/ and mods/{agents-manager,delegate-pane,agents-inc}/.claude/ (skip any that are tracked)
- [x] T022 [US4] Worktree .claude/worktrees/agent-ae71b5b16daa5b202 (branch fix/dispatch-non-git-cwd, locked): VERIFY AND REPORT ONLY, DO NOT REMOVE. Run `git log fix/dispatch-non-git-cwd --not development main`; it has 19 commits not on development/main (gate red, R-b). Report the commits and `git diff 1cb057a feat/pane-auto-open -- agents_inc`. Operator decides. No unlock, no remove.

## Phase 7: Polish and cross-cutting

- [x] T023 [P] DOCKER Set version 0.6.0 and new description in mods/delegate-pane/.claude-plugin/plugin.json
- [x] T024 [P] DOCKER Rewrite mods/delegate-pane/README.md for the merged pane in human prose (FR-017)
- [x] T025 [P] DOCKER Add D62 status note (office floor view and `agents-inc watch` not built; shipped as specs 039 and 040) to docs/DECISIONS.md and merge entry to CHANGELOG.md (FR-015)
- [x] T026 DOCKER SC-005: `git grep -n agents-manager` excluding CHANGELOG.md, docs/DECISIONS.md and specs shows only the installer retired list and its test
- [x] T027 DOCKER Run all mod tests: count >= the T001 baseline sum (measured 2026-11-14: 113), all pass; run `python3 -m unittest discover -s tests -p 'test_*.py'`; confirm no extra reads versus 0.5.0 plus 0.1.0 (SC-003); grep hooks for fetch, network or model calls (FR-014)
- [x] T028 MAC Live check per quickstart.md steps 4-6: five fresh sessions open one pane; native, Codex, free starts; narrow toggle (Done by operator 2026-11-14: install ran twice; only delegate-pane listed; known_marketplaces has 0 retired entries.)
- [x] T029 OPERATOR Commit the work first (needed before the move), then Move specs to DomI: run `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. Operator-gated. Depends on every other task; nothing runs after it.

## Dependencies

- Phase 1 -> Phase 2 -> stories. T005 after T004; T007 after T005 and T006.
- US1 (T008-T011) needs Phase 2. US2 needs T009 and T005. US3 is independent of US1/US2 and can run in parallel. US4: T020 after US2 and US3 code; T022 independent, report-only.
- Polish after stories. T029 last.

## Parallel examples

- Phase 2: T002 with T004; T006 alongside T005.
- After Phase 2: US3 (T016-T018) in parallel with US1/US2.
- T023, T024, T025 together.

## Implementation strategy

- MVP: Phases 1-3 (one pane with map, feed, tree) in docker.
- Then US2 (controls, port 22 tests), US3 installer, US4 cleanup, polish.
- Mac touches only T019 and T028. Worktree untouched pending operator decision.
