<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Tasks: at_route Hardening and Installer Ownership

**Input**: plan.md and spec.md in `specs/013-at-route-hardening/`
**Tests**: required. The Supervisor writes every acceptance test before implementation and shows it failing on unchanged code (workerbee Step 2).
**Rung key**: `[supervisor]` Orchestrator (opus, this session); `[sonnet]` Workhorse, design judgment; `[haiku]` Grunt, narrow diff with fixed scope.
**Format**: `- [ ] ID [P?] [Story] [rung] description | files | success: ... | failure: ...`
**Global failure criterion**: any edit to a peer-owned file (`agents_inc/free_health.py`, `tests/test_free_health.py`, `skills/codex-bridge/SKILL.md`, `docs/BENCH.md`, `agents_inc/adapters/ollama.py`), any write to the live `~/.claude`, `~/.local`, or `~/.codex-bridge`, or any real model call is RED for the task that caused it.

## Phase 1: Setup

- [x] T001 [US5] [supervisor] Record #32 close-out evidence: `agents-inc doctor` run from `/tmp` | `specs/013-at-route-hardening/issue32-evidence.md` | success: file quotes command, cwd `/tmp`, output `READY`, exit `0` | failure: file missing any of the four (FR-015)

## Phase 2: Tests first (Supervisor-owned verifiers)

- [x] T002 [US1] [US2] [US4] [supervisor] Extend the smoke test: (h) every Claude alias passes `--tools Read,Grep,Glob`, `--disallowedTools` naming `Edit`, `Write`, `Bash`, `NotebookEdit`, and `--strict-mcp-config` (argv-recording stub), hook and CLI mode; (i) `AT_ROUTE_TIMEOUT=1` with a sleeping stub prints `timed out after 1s`, `Partial files may exist`, and `git status`; (j) fast non-alarm failure keeps `call failed (exit 3)` and has no `timed out`; (k) `@openrouter hi` with a stub `oask.sh` printing `[openrouter vendor/model:free | in 1 out 1]` on stderr shows header `openrouter (vendor/model:free)`; (l) `MODEL=openai/gpt-4o-mini` reaches the stub unset; (m) stub `oask.sh` exit 3 gives the failover block; (n) `@@openrouter hi` relays; (o) no model line gives `openrouter (unknown model)` | `skills/codex-bridge/tests/at_route.smoke.sh` | success: new cases FAIL on unchanged `at_route.sh`, old cases a-g still PASS | failure: a new case passes on unchanged code (test does not discriminate) (FR-013, SC-001, SC-002, SC-005)
- [x] T003 [US3] [supervisor] Installer and doctor tests in a fake HOME: owned `UserPromptSubmit` entry with command `bash <current>/skills/codex-bridge/scripts/at_route.sh` and timeout > 120; reinstall does not duplicate; foreign `UserPromptSubmit` hooks kept; legacy line `bash ~/.claude/scripts/at_route.sh` replaced, foreign sibling in the same group kept; 11 `@alias` links to the installed path, receipt-owned; legacy links relinked; foreign `@alias` file left untouched with a notice; legacy file deleted with a backup and restored by journal recovery; uninstall leaves settings byte-identical to pre-install and removes the links; doctor `WB_HOOK_DRIFT` on mismatch, none on match, `WB_HOOK_DRIFT_UNCHECKED` when the source record is missing; `ready` unchanged by either warning | `tests/test_install_at_route.py` | success: tests fail on unchanged code for missing behavior, not for test bugs | failure: a test errors on a typo or passes on unchanged code (FR-004 to FR-007, SC-003, SC-004)

## Phase 3: US1 + US2 + US4 hook script (P1, P2)

- [x] T004 [US1] [US2] [US4] [haiku] (Grunt kept despite analyze A14: exact code-level instructions and 19 Supervisor smoke cases fix the scope; D27 promotion to sonnet after 2 failed checks) Edit `at_route.sh` per plan DD1, DD2, DD3, and rewrite the stale comment at `:11-13`: read-only flags on the Claude branch; timeout block for `rc == 142` on every alias kind; `openrouter` in the alias regex, `kind=openrouter` branch running `env -u MODEL "$SCRIPT_DIR/oask.sh" "$question"` under the alarm, display model parsed from the stderr line, default `unknown model` | `skills/codex-bridge/scripts/at_route.sh` | success: `bash skills/codex-bridge/tests/at_route.smoke.sh` exits 0 with every case PASS | failure: smoke exit non-zero after 2 attempts, or any file outside scope changed (FR-001 to FR-003, FR-009 to FR-012)

## Phase 4: US3 installer ownership (P2)

- [x] T005 [US3] [sonnet; done by Executive after the sonnet dispatch was blocked by the auto-mode classifier, reason `[Self-Modification]`; operator approved Executive edits] Implement plan DD4 to DD8: `Host.prompt_hook`, at_route command and `_owned` match, legacy line strip, `install_alias_links`, legacy file delete, `source-checkout` state record written by `cli.install`, notices printed, doctor drift warnings | `agents_inc/install/host_wiring.py`, `agents_inc/install/cli.py`, `agents_inc/install/doctor.py` | success: `python3 -m unittest tests.test_install_at_route tests.test_install_host_wiring tests.test_install_cli tests.test_install_doctor` OK | failure: any of those red after 2 attempts, or a write outside FILES IN SCOPE (FR-004 to FR-007, FR-016). Deviation (Executive, 2026-10-01): doctor emits no drift warning when the installed `at_route.sh` is absent, because `tests/test_doctor_codex_optional` asserts `warnings == ()` for a release with no hook; consistent with DD8, which covers only a missing source record or source file.
- [x] T006 [P] [US3] [haiku] Retire the legacy installer per DD9; rewrite the `docs/AT-ROUTE.md` install section (install is `agents-inc install` or `repair`; hook and links point at `~/.local/share/agents-inc/current/skills/codex-bridge/scripts/at_route.sh`; doctor `WB_HOOK_DRIFT`); add read-only and timeout notes; add `@openrouter` lexicon row; say raising `AT_ROUTE_TIMEOUT` needs a matching settings timeout | `skills/codex-bridge/scripts/install_at_route.sh`, `docs/AT-ROUTE.md` | success: `bash skills/codex-bridge/scripts/install_at_route.sh; echo $?` prints the retire line and `2` with HOME set to a temp dir and creates no file; `grep -c openrouter docs/AT-ROUTE.md` >= 1; `grep -c '.claude/scripts/at_route.sh' docs/AT-ROUTE.md` = 0 except in a sentence naming it as legacy | failure: the stub still copies a file, or docs still instruct the copy (FR-008, FR-014)
- [ ] T007 [US4] [BLOCKED-PEER skills/codex-bridge/SKILL.md] Add the `@openrouter` row to the lexicon at `skills/codex-bridge/SKILL.md:280` and rewrite the install paragraph at `:260` (still says copy to `~/.claude/scripts`; analyze A19) | `skills/codex-bridge/SKILL.md` | success: row present after the peer session releases the file | failure: edited while peer-owned (FR-014)

## Phase 5: Polish and gates

- [x] T008 [supervisor] Run gates: full unit suite (only `test_openrouter_named_chain_with_auto_last` failing), smoke test exit 0, `git status --porcelain` against the pre-dispatch snapshot, `git diff --stat agents_inc/free_health.py` = 41 insertions | none | success: all four hold with pasted output | failure: any differs (SC-006)

## Requirement coverage

| FR | Tasks |
|---|---|
| FR-001 | T002, T004 |
| FR-002, FR-003 | T002, T004 |
| FR-004, FR-005 | T003, T005 |
| FR-006 | T003, T005 |
| FR-007 | T003, T005 |
| FR-008 | T006 |
| FR-009 to FR-012 | T002, T004 |
| FR-013 | T002 |
| FR-014 | T006, T007 (BLOCKED-PEER) |
| FR-015 | T001 |
| FR-016 | T003, T005 (fake HOME only) |

## Dependencies

T002 before T004. T003 before T005. T006 parallel with T004 and T005. T008 last.
