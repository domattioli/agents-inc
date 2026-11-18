# Tasks: Persistent Cross-Provider Delegate Handles (048)

Format: `[ID] [P] [Story] Description` with files and acceptance command. TS test command: `claude plugin test mods/agents-inc`. Python: `python3 -m unittest discover -s tests -p 'test_*.py'`.

## Phase 1: Setup

- [x] T001 Verify research.md still holds (runner `claude plugin test mods/agents-inc`, `$.fs` read/write only). Files: read-only `mods/agents-inc/hooks/native/loop.ts`, `adapter.ts`; record answers in `research.md`. Accept: `research.md` names the exact test command.
- [x] T002 Extend types: `AgentState` and `LoopState` (`handlesLoaded`, `warned`) in `mods/agents-inc/hooks/native/loop.ts`; schema in `data-model.md`. Accept: `grep -n handlesLoaded mods/agents-inc/hooks/native/loop.ts` hits.

## Phase 2: Foundational (blocks stories)

- [x] T003 Add `handlesPath`, `loadHandles`, `saveHandles` (try/catch, one warning per session, FR-011) in `loop.ts`. Accept: new tests in `loop.test.ts` for corrupt store warn-once pass.

## Phase 3: US1 survive restart (P1)

- [x] T004 [US1] Tests first in `mods/agents-inc/hooks/native/loop.test.ts`: add an in-memory fs to the harness (:55); persist after step; reload resumes with delta only; missing thread file (empty read) starts fresh with reason `thread-missing`; last `threadTotals` per thread persisted (loop.ts:746). Accept: tests fail before T005.
- [x] T005 [US1] Wire load on first step, restore `used` only if thread file exists, save after run record (~:936-953) in `loop.ts`; restart counters and reasons at every `st.n` bump (FR-009; compaction :840, failed step :850, refusal :876, thread-missing); `charsSent` resets on bump, stateless uses last prompt length; `saveHandles` re-reads and merges, file state wins; a step on a retired handle is refused (test here). Accept: T-runner on `loop.test.ts` green.
- [x] T006 [US1] Binding refusal (FR-010; provider plus nickname; slug from first completed step's `acc.slug` informational) in `loop.ts` plus test. Accept: mismatch test green.

## Phase 4: US2 list and retire (P1)

- [x] T007 [P] [US2] Tests `tests/test_handles_cli.py`: list text and `--json`, retire, corrupt file. Accept: fail before T008.
- [x] T008 [US2] Add `handles` subparser and handler in `agents_inc/install/cli.py` (list; retire marks state and prints the paste-into-new-Agent instruction, never contacts the delegate; `--session defaults to newest dir under .scratch/agents-inc-*/`; `--agent --session --cwd --json`). Accept: `python3 -m unittest tests.test_handles_cli`.
- [x] T009 [US2] Ceiling advisory (800k chars, all guests) in `loop.ts` plus test (FR-006). No successor seeding: the supervisor pastes the note into a new Agent prompt. Accept: loop tests green.

## Phase 5: US3 Mistral per-handle ids (P2)

- [x] T010 [P] [US3] Test `tests/test_mask_handle.py`: two `--agent --handle` runs yield two distinct id files, legacy file untouched. Accept: fails before T011.
- [x] T011 [US3] Add `--handle ID` to `skills/codex-bridge/scripts/mask.sh` (id dir `~/.codex-bridge/mistral-conversations/`, used only under `--agent`, mask.sh:236); pass it from `skills/codex-bridge/scripts/agent_runner.py:576-579` (`--handle <job id>`, resumed job passes parent's id, only with `--agent`). Accept: `python3 -m unittest tests.test_mask_handle` and `bash -n skills/codex-bridge/scripts/mask.sh`.

## Phase 6: US4 fingerprint (P2)

- [x] T012 [US4] Test: 3-step run logs 3 fingerprints (header+system+catalog), a changed flag and `sent yes|no`. Implement pure-TS FNV-1a 32-bit (8 hex + length) and log field in `loop.ts` (~:936). Accept: loop tests green.

## Phase 7: Polish

- [x] T013 Full suites: TS runner for `mods/agents-inc`, `python3 -m unittest discover -s tests -p 'test_*.py'`. Accept: both green; `git diff --stat` limited to files in plan.md.
- [x] T014 Doc line for `agents-inc handles` in `docs/START-HERE.md` or the relevant guide (human style). Accept: `grep -rn "agents-inc handles" docs/`.
- [ ] T015 [OPERATOR-GATED, do not run] Move specs to DomI: `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`.

Order: T001, T002, T003, then T004-T006, T007-T009, T010-T011, T012 (US stories independent after T003; T007/T010 parallel), T013, T014, T015.
