<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Tasks: Dispatch Contract Header and Dispatch Records

**Input**: plan.md and spec.md in `specs/016-dispatch-contract-records/`
**Tests**: required. The Supervisor writes every acceptance test before implementation and shows it failing on unchanged code (workerbee Step 2).
**Rung key**: `[supervisor]` Orchestrator (opus, this session); `[executive]` Executive edits `agents_inc/install/*` (operator ruling 2026-10-01); `[sonnet]` Workhorse, design judgment (escalation trigger (c)); `[haiku]` Grunt, narrow diff with fixed scope.
**Format**: `- [ ] ID [P?] [Story] [rung] description | files | success: ... | failure: ...`
**Global failure criterion**: any edit to a peer-owned file (`agents_inc/free_health.py`, `tests/test_free_health.py`, `skills/codex-bridge/SKILL.md`, `docs/BENCH.md`, `agents_inc/adapters/ollama.py`, `tests/test_ollama_adapter.py`); a delegate edit under `agents_inc/install/`; any write to the live `~/.claude`, `~/.local`, `~/.codex-bridge`, or DomI by code or tests; any real model call; a new path matched by `.gitignore` (`git check-ignore -v <path>` must print nothing). Each is RED for the task that caused it.

## Phase 1: Tests first (Supervisor-owned verifiers)

- [x] T001 [US1] [supervisor] Ledger field tests: dispatch and return with effort, tokens, files, verdict persist through `load`; return `run_id` equals the dispatch's with and without an explicit argument; pre-change fixture loads with new fields `None`; `None` stays `None` (not 0); invalid verdict or negative tokens return `False` and write nothing; SQLite usage row carries input/output tokens; `to_json`/`from_json` round-trip; `store="jsonl"` overrides `WORKERBEES_STORE=both` (no SQLite file); `record_return` without `seconds`/`subscription_calls` writes nulls | `tests/test_ledger_fields.py` | success: behavior cases FAIL on unchanged code (RED shown) | failure: a test errors on a test bug (FR-001, FR-002, SC-001, SC-002)
- [x] T002 [P] [US1] [supervisor] Usage join tests: temp `usage.db`; match sums rows in the window; missing db returns `None` and creates no file; no row, claude provider, no return timestamp, overlapping same-model node, `source` `host-hook` each return `None`; Codex nickname matches `gpt-...-luna` | `tests/test_usage_join.py` | success: FAIL on unchanged code (module absent) | failure: as T001 (FR-003)
- [x] T003 [P] [US1] [supervisor] Host ledger tests: `Agent` and `DelegateAgent` payloads give one row each under `<state>/host-ledger/.workerbees/ledger.jsonl` with Node fields, `source` `host-hook`, token fields `None`; nothing under payload `cwd`; unrelated tool, non-dict, missing `tool_use_id` give no row; unwritable state returns `False` without raising; `lint` gives no finding for grunt/workhorse hook rows; `cli(["append", ...])` without `--verdict` exits 2 with the message; unknown node without `--run-id` exits 2; with a dispatch row writes a return row carrying its `run_id` and verdict; host workspace gains no `workerbees.db` even with `WORKERBEES_STORE=both`; `cli(["pending"])` lists open rows only. Integration (RED until T009): `hook.run(paths, "agent-done", ...)` writes the row and exits 0 on malformed input; `add_hooks` adds `PostToolUse` matcher `mcp__.*__DelegateAgent` command `agent-done` timeout <= 5; `cli.main(["ledger", "append", ...])` routes | `tests/test_host_ledger.py` | success: FAIL on unchanged code | failure: as T001 (FR-004, US1 scenarios 3-6)
- [x] T004 [P] [US2] [US4] [supervisor] Header tests: rendered header plus slots lints COMPLIANT (`--tier grunt`); `CONTRACT: <header.md>` prompt with file transport COMPLIANT; same with `--transport bare` NON-COMPLIANT; unreadable contract path NON-COMPLIANT; opt-out line verbatim in every rendered prompt; missing required slot exits 2 naming it; prompts without `CONTRACT:` unchanged (existing fixtures); header holds the PERSISTENCE line; SKILL.md holds Step 3c with 200k, 300k, the exceptions, and the resume list | `tests/test_dispatch_header.py` | success: FAIL on unchanged code | failure: as T001 (FR-005, FR-006, FR-008, SC-004)
- [x] T005 [P] [US3] [supervisor] Drift tests: the repo SKILL.md block equals the generator output; `--check` on a temp SKILL.md with a changed fixture tier exits 1 and names the id; an off-vocabulary tier fails closed naming the id; every `models.json` id appears in the block (39 of 39 at plan time); every tier cell in the Step 1 ladder and Step 1a roster is a rung name or `—`; roster rows whose nickname or slug is a config id carry the config rung | `tests/test_tier_table_drift.py` | success: FAIL on unchanged code | failure: as T001 (FR-007, SC-003)

## Phase 2: US1 records (P1)

- [x] T006 [US1] [sonnet] Implement plan DD1 in `agents_inc/ledger.py` | `agents_inc/ledger.py` | success: `python3 -m unittest tests.test_ledger_fields tests.test_ledger tests.test_ledger_sqlite tests.test_store_dualwrite tests.test_migrate tests.test_artifacts` OK | failure: red after 2 attempts, an existing test changed, or `docs/governance/SCHEMA-3NF.md`/`agents_inc/schema.py` edited (FR-001, FR-002)
- [x] T007 [P] [US1] [haiku] New `agents_inc/usage_join.py` per DD2 | `agents_inc/usage_join.py` | success: `python3 -m unittest tests.test_usage_join` OK | failure: red after 2 attempts, or any write to a usage db (FR-003)
- [x] T008 [US1] [sonnet] New `agents_inc/host_ledger.py` per DD3 and DD4 (after T006; same sonnet delegate as T006 via SendMessage, Step 3c; analyze B9) | `agents_inc/host_ledger.py` | success: `python3 -m unittest tests.test_host_ledger` passes every non-integration case | failure: red after 2 attempts, or a write under payload `cwd` (FR-004)
- [ ] T009 [US1] [executive] Wire DD3/DD4: `hook.agent_done` calls `host_ledger.record_hook_dispatch(paths.state, payload)` first, for every payload, before the `run_in_background` early return, and keeps the release for `Agent`/`Task` only; `host_wiring.add_hooks` adds `PostToolUse` matcher `mcp__.*__DelegateAgent`, `agent-done`, timeout 5, Claude host; `cli.py` adds `ledger` (`append` and `pending`; remaining argv to `host_ledger.cli(rest, paths.state)`) before the receipt check | `agents_inc/install/hook.py`, `agents_inc/install/host_wiring.py`, `agents_inc/install/cli.py` | success: `python3 -m unittest tests.test_host_ledger tests.test_hook_persona_guard tests.test_install_host_wiring tests.test_install_cli` OK | failure: any red, or the hook exits nonzero on any input (FR-004)

## Phase 3: US2 header and lint (P2)

- [x] T010 [P] [US2] [supervisor] Write `skills/workerbee/header.md` and `skills/workerbee/slots.md` per DD5 and Appendices B and C | those two files | success: `python3 skills/workerbee/scripts/check_dispatch_prompt.py --tier grunt <slots filled + header>` prints COMPLIANT | failure: any element missing (FR-005, FR-009 #4 slot)
- [x] T011 [US2] [haiku] New `render_dispatch.py` per DD5 and `--transport`/`CONTRACT:` in `check_dispatch_prompt.py` per DD6 (after T010) | `skills/workerbee/scripts/render_dispatch.py`, `skills/workerbee/scripts/check_dispatch_prompt.py` | success: `python3 -m unittest tests.test_dispatch_header` passes every case except the SKILL.md text case; existing dispatch prompts in scratchpad still COMPLIANT | failure: red after 2 attempts, or an existing lint behavior changed (FR-005, FR-006)

## Phase 4: US3 + US4 skill (P2, P3)

- [x] T012 [P] [US3] [haiku] New `skills/workerbee/scripts/gen_tier_tables.py` per DD7 | that file | success: drift cases that use temp files pass (`python3 -m unittest tests.test_tier_table_drift.GeneratedBlockTest` minus `test_repo_skill_block_is_current`, `test_block_lists_every_models_json_id`, `test_block_sits_inside_step_1`, which need T013) | failure: red after 2 attempts (FR-007)
- [x] T013 [US3] [US4] [supervisor] SKILL.md: relabel ladder and roster tier cells (DD7), insert Appendix D blocks D1, D2, D3, run `gen_tier_tables.py --write` (after T012) | `skills/workerbee/SKILL.md` | success: `python3 -m unittest tests.test_tier_table_drift tests.test_dispatch_header` OK; `git diff --numstat skills/workerbee/SKILL.md` deleted lines equal the relabelled rows only | failure: any other existing line changed (FR-007, FR-008, FR-011 LESSON-CANDIDATE)

## Phase 5: US5 records (P3)

- [x] T014 [P] [US5] [supervisor] Write `research.md` per DD9 | `specs/016-dispatch-contract-records/research.md` | success: states #4 status, measurements, unvalidated items, STYLE slot location; #27 verdict, counts, NEEDS-OPERATOR follow-ups; `git -C ~/Projects/DomI status --porcelain` unchanged by this batch | failure: a DomI write or a savings claim without measurement (FR-009, FR-010)

## Phase 6: Gates

- [ ] T015 [supervisor] Full unit suite (only `test_openrouter_named_chain_with_auto_last` failing), `bash skills/codex-bridge/tests/at_route.smoke.sh` exit 0, `git status --porcelain` against the batch snapshot, `git diff --stat agents_inc/free_health.py` = 41 insertions, `git check-ignore -v` on every new path prints nothing | none | success: all hold with pasted output | failure: any differs (SC-005)

## Requirement coverage

| FR | Tasks |
|---|---|
| FR-001, FR-002 | T001, T006 |
| FR-003 | T002, T007 |
| FR-004 | T003, T008, T009 |
| FR-005 | T004, T010, T011 |
| FR-006 | T004, T011 |
| FR-007 | T005, T012, T013 |
| FR-008 | T004, T010, T013 |
| FR-009 | T010 (STYLE slot), T014 |
| FR-010 | T010, T013 (no claim), T014 |
| FR-011 | T013 (report LESSON-CANDIDATE) |

## Dependencies

T001-T005 before their implementation tasks. T006 before T008 (return rows use the DD1 signature). T008 before T009. T009 may need `tests/test_install_host_wiring.py` index assertions updated for the second `PostToolUse` group (analyze B16); that test edit is the Executive's. T010 before T011. T010, T011, T012 before T013. T015 last. T007, T010, T012, T014 can run in parallel with T006.
