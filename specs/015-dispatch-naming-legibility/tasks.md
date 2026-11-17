<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Tasks: Dispatch Naming Legibility

**Input**: plan.md and spec.md in `specs/015-dispatch-naming-legibility/`
**Tests**: required. The Supervisor writes every acceptance test before implementation and shows it failing on unchanged code (workerbee Step 2).
**Rung key**: `[supervisor]` Orchestrator (opus, this session); `[executive]` Executive edits `agents_inc/install/*` (operator ruling 2026-10-01: "Executive edits, Supervisor approves"); `[haiku]` Grunt, narrow diff with fixed scope.
**Format**: `- [ ] ID [P?] [Story] [rung] description | files | success: ... | failure: ...`
**Global failure criterion**: any edit to a peer-owned file (`agents_inc/free_health.py`, `tests/test_free_health.py`, `skills/codex-bridge/SKILL.md`, `docs/BENCH.md`, `agents_inc/adapters/ollama.py`, `tests/test_ollama_adapter.py`); a delegate edit under `agents_inc/install/`; any read of real `~/.claude/projects` data by a test; any write to the live `~/.claude`, `~/.local`; any real model call. Each is RED for the task that caused it.

## Phase 1: Tests first (Supervisor-owned verifiers)

- [x] T001 [US1] [US4] [supervisor] Hook tests: 4 deny fixtures and 2 collisions denied with the verbatim FR-002 reason in the reference payload shape; 6 allow fixtures not denied; `Task` covered; `DelegateAgent` not denied; malformed payloads fail open; cross-session duplicate warns naming S1; same session, different prompt, `agents-inc: fan-out` override, expired entry: no warning; foreground `agent-done` releases, background does not; unwritable registry fails open; Claude host gets one owned `PostToolUse` `Agent|Task` `agent-done` entry with timeout <= 5 that `strip_hooks` removes; CLI accepts `agent-done` | `tests/test_hook_persona_guard.py` | success: behavior cases FAIL on `e21db5b` (RED shown: 12 of 15 fail; the 3 that pass are fail-open and allow guards) | failure: a test errors on a test bug (FR-002, FR-006, FR-007, SC-001, SC-003)
- [x] T002 [US3] [supervisor] Recovery tests: files from `Write`/`Edit`/`NotebookEdit`, last text, last error listed; 5 MB fixture output <= 4,000 chars and still lists early and late files; `--max-chars` respected; malformed lines skipped and counted; `SubagentHandback` marks status; missing file exits non-zero with a message | `tests/test_recover_transcript.py` | success: 5 of 6 FAIL on unchanged code (script absent); the missing-file guard passes | failure: as T001 (FR-005, SC-002)

## Phase 2: US1 + US4 hook (P1, P3)

- [x] T003 [US1] [US4] [executive] Implement plan DD1-DD5 in `agents_inc/install/hook.py` (persona deny, task key, registry, combined output, `agent-done` release), `agents_inc/install/cli.py` (`hook` event choice `agent-done`), `agents_inc/install/host_wiring.py` (`PostToolUse` `Agent|Task` `agent-done`, timeout 5, Claude host) | those three files | success: `python3 -m unittest tests.test_hook_persona_guard tests.test_install_host_wiring tests.test_install_at_route tests.test_install_cli` OK | failure: any red, or the deny reason differs from FR-002 by one byte (FR-002, FR-006, FR-007)

## Phase 3: US3 recovery (P2)

- [x] T004 [P] [US3] [haiku] New `skills/workerbee/scripts/recover_transcript.py` per plan DD6 | `skills/workerbee/scripts/recover_transcript.py` | success: `python3 -m unittest tests.test_recover_transcript` OK | failure: red after 2 attempts, the script writes any file, or it reads the transcript whole into memory (FR-005)

## Phase 4: US1 + US2 skill text (P1)

- [x] T005 [P] [US1] [US2] [haiku] Insert plan Appendix A blocks A1 and A2 verbatim into `skills/workerbee/SKILL.md` at the stated anchors (naming rule, hierarchy line, operator-model precedence, recovery command, duplicate warning) | `skills/workerbee/SKILL.md` | success: `grep -c 'Dispatch names tell the truth' skills/workerbee/SKILL.md` = 1; `grep -c 'recover_transcript.py' skills/workerbee/SKILL.md` >= 1; `grep -c 'Hierarchy: Executive' skills/workerbee/SKILL.md` >= 1; `git diff --numstat skills/workerbee/SKILL.md` shows 0 deleted lines and 28 added lines (blocks plus 2 blank separators; recounted 2026-10-01 against a Supervisor-built expected file) | failure: an existing line deleted or a file outside scope changed (FR-001, FR-003, FR-004, FR-009 LESSON-CANDIDATE)

## Phase 5: Gates

- [x] T006 [supervisor] Full unit suite (only `test_openrouter_named_chain_with_auto_last` failing), `bash skills/codex-bridge/tests/at_route.smoke.sh` exit 0, `git status --porcelain` against the batch snapshot, `git diff --stat agents_inc/free_health.py` = 41 insertions | none | success: all hold with pasted output | failure: any differs (SC-004)

## Requirement coverage

| FR | Tasks |
|---|---|
| FR-001 | T005 |
| FR-002 | T001, T003 |
| FR-003, FR-004 | T005 (no automated check, plan DD7) |
| FR-005 | T002, T004 |
| FR-006 | T001, T003 |
| FR-007 | T001, T003 |
| FR-008 | T001, T002 (fixtures, fake home) |
| FR-009 | T005 (report LESSON-CANDIDATE) |

## Dependencies

T001 before T003. T002 before T004. T004 and T005 parallel with T003. T006 last.
