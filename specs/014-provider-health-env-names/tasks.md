<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Tasks: Provider Health Freshness and Key Name Consistency

**Input**: plan.md and spec.md in `specs/014-provider-health-env-names/`
**Tests**: required. The Supervisor writes every acceptance test before implementation and shows it failing on unchanged code (workerbee Step 2).
**Rung key**: `[supervisor]` Orchestrator (opus, this session); `[haiku]` Grunt, narrow diff with fixed scope.
**Format**: `- [ ] ID [P?] [Story] [rung] description | files | success: ... | failure: ...`
**Global failure criterion**: any edit to a peer-owned file (`agents_inc/free_health.py`, `tests/test_free_health.py`, `skills/codex-bridge/SKILL.md`, `docs/BENCH.md`, `agents_inc/adapters/ollama.py`, `tests/test_ollama_adapter.py`) or to `agents_inc/install/*` (Executive-owned); any write to the live `~/.codex-bridge`, `.env`, or key files; any real network or model call; any key value in output. Each is RED for the task that caused it.

## Phase 1: Tests first (Supervisor-owned verifiers)

- [x] T001 [US1] [supervisor] `tests/test_route_health_freshness.py`, fake HOME: `report mistral ok` after an error clears `last_error` and sets `last_checked`; `report` for a backend missing from an existing file does not fail; `status` shows `stale` for a 3-day-old entry, no `stale` for a 1-hour-old entry, `unknown` for null, fresh for a future timestamp; `pick digest` still returns a stale first backend; `mask.sh` and `oask.sh` with a stub `curl` (HTTP 200, then HTTP 500) refresh `last_checked` on the backend entry, clear or set `last_error` accordingly, and keep their own exit codes | `tests/test_route_health_freshness.py` | success: new cases FAIL on unchanged scripts for missing behavior; the pick and exit-code guards pass | failure: a case errors on a test bug, or a behavior case passes on unchanged code (FR-001 to FR-003a, SC-001, SC-002)
- [x] T002 [US2] [supervisor] Extend `tests/test_keys.py` for both `agents_inc.keys` and `workerbees.keys`: each spelling gives `openrouter`, never `open_router` (4 cases); default call with a fake HOME reads both `~/.config/workerbees/.env` and `~/.config/agents_inc/.env`; `setup_key` default writes only the workerbees path; captured stdout and stderr hold no sentinel value | `tests/test_keys.py` | success: new cases FAIL on unchanged modules; existing cases still pass | failure: as T001 (FR-004, FR-005, FR-008, SC-003, SC-004)

## Phase 2: US1 health freshness (P1)

- [x] T003 [US1] [haiku] (dispatched together with T004 as one Grunt task) Edit `route.sh` per plan DD1, DD2, DD3 (ok clears `last_error`, `setdefault` for a missing backend, `Age` column with `stale`/`unknown`, 24 h window) | `skills/codex-bridge/scripts/route.sh` | success: `python3 -m unittest tests.test_route_health_freshness.RouteReportTest tests.test_route_health_freshness.RouteStatusTest` OK (analyze B3) and `tests.test_router_free_first` OK | failure: red after 2 attempts, or a file outside scope changed (FR-001 to FR-003)
- [x] T004 [US1] [haiku] Add the DD5 `route.sh report` line to the `mask.sh` and `oask.sh` exit traps, with the `MASK_ATTEMPTED` guard in `mask.sh` (mapping ok to ok; rate_limited, overloaded, error to transient; withdrawn and zdr skipped; exit code unchanged) | `skills/codex-bridge/scripts/mask.sh`, `skills/codex-bridge/scripts/oask.sh` | success: `python3 -m unittest tests.test_route_health_freshness` OK and `python3 -m pytest -q tests/test_free_wrappers.py` still `9 passed` (baseline 2026-10-01, analyze B4) | failure: red after 2 attempts, exit code of either wrapper changes, or a file outside scope changed (FR-003a)
- [ ] T005 [US1] [BLOCKED-PEER agents_inc/free_health.py] On `ok`, clear `last_error` and set `last_checked` in `free_health.report` (plan DD9) | `agents_inc/free_health.py` | success: done by the peer session after release | failure: edited while peer-owned

## Phase 3: US2 key names and paths (P1)

- [x] T006 [P] [US2] [haiku] Edit `agents_inc/keys.py` per plan DD6, DD7 (`workerbees.keys` is an alias of it; `workerbees/keys.py` is dead and untouched) | `agents_inc/keys.py` | success: `python3 -m unittest tests.test_keys tests.test_doctor` OK (or the doctor test module present) | failure: red after 2 attempts, a key value printed, or a file outside scope changed (FR-004, FR-005, FR-008)

## Phase 4: US3 docs (P2)

- [x] T007 [P] [US3] [haiku] Append the DD8 dated notes and the ZDR and key-path notes | `docs/DECISIONS.md`, `docs/HOW-IT-WORKS.md`, `specs/010-persistent-exec-session/analyze-2026-09-12b.md` | success: `git diff --numstat` for `docs/DECISIONS.md` and the analyze file shows 0 deleted lines; `grep -c '2026-10-01 correction' docs/DECISIONS.md` = 2; `grep -c ZDR docs/HOW-IT-WORKS.md` >= 1; `grep -c 'There is no .~/.config/workerbees/.env' docs/HOW-IT-WORKS.md` = 0 | failure: any existing line in DECISIONS or the analyze file deleted, or `docs/BENCH.md` touched (FR-006, FR-007)

## Phase 5: Gates

- [x] T008 [supervisor] Full unit suite (only `test_openrouter_named_chain_with_auto_last` failing), `git status --porcelain` against the batch snapshot, `git diff --stat agents_inc/free_health.py` = 41 insertions, `bash skills/codex-bridge/tests/at_route.smoke.sh` exit 0 | none | success: all hold with pasted output | failure: any differs (SC-005)

## Requirement coverage

| FR | Tasks |
|---|---|
| FR-001 | T001, T003 |
| FR-002 | T001, T003 |
| FR-003 | T001 (guard) |
| FR-003a | T001, T004, T005 (BLOCKED-PEER) |
| FR-004 | T002, T006 |
| FR-005 | T002 |
| FR-006, FR-007 | T007 |
| FR-008 | T002, T006 |
| FR-009 | T001, T002 (fake HOME) |

## Dependencies

T001 before T003 and T004. T002 before T006. T003 before T004 (the trap calls the fixed `report`). T006 and T007 parallel with T003 and T004. T008 last.

## Implementation record (2026-10-01)

- T001, T002: RED shown before implementation (9 of 11; 6 subtests).
- T003+T004 (haiku, one Grunt task): GREEN; `tests.test_route_health_freshness` 11 OK, `test_free_wrappers` 9 passed. Supervisor fix after review: `route.sh status` now reads a naive `last_checked` as UTC (plan DD3) instead of printing `unknown`.
- T005: BLOCKED-PEER (`agents_inc/free_health.py` is peer-owned).
- T006+T007 (haiku): GREEN; `tests.test_keys tests.test_doctor` OK; doc grep gates hold; 0 deleted lines in DECISIONS and the analyze file. `LEGACY_ENV_PATH` constant in `agents_inc/keys.py` is unused (cosmetic).
- T008: full suite 699 tests, 18 failures = pre-existing router failure plus 17 intended batch C RED tests (`test_hook_persona_guard`, `test_recover_transcript`) awaiting batch C implementation; smoke exit 0; `free_health.py` 41 insertions.
