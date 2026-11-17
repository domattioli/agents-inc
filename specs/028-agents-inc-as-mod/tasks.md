---
description: "Task list for 028 agents-inc as a mod (luna first)"
---
<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-24 skill=speckit-tasks repo=agents_Inc session=20261025T002934Z-opus-7f9da0 -->

# Tasks: agents-inc becomes a Claude Code mod (luna first)

**Input**: `specs/028-agents-inc-as-mod/` (spec.md, plan.md, research.md)
**Tests**: required. The spec gives an independent test per story, plugin tests for US3 and SC-008. Write each test task before its implementation task and see it fail first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallel-safe (different files, no open dependency)
- **[Story]**: US1 native subagent, US2 no Codex tools, US3 no silent fallback, US4 install/doctor/rollback, US5 inventory, ledger and canon
- Tasks marked **(operator)** make real model calls or need a real host; a delegate does not run them.

## Phase 1: Setup

- [X] T001 Copy `mods/luna-brain/hooks/luna.ts` to `mods/agents-inc/hooks/luna.ts` and `mods/luna-brain/hooks/luna.test.ts` to `mods/agents-inc/hooks/luna.test.ts` unchanged, add `"luna.ts"` to `modules` in `mods/agents-inc/hooks/hooks.json`, and run `claude plugin test mods/agents-inc` green before any edit (FR-019; plan D1) — done with a deviation: the harness allows one hooks module per plugin and one `session.start` registration per module, so `hooks.json` lists `mod.ts`, which owns `session.start` and calls `registerRelay`/`registerLunaAgent`; `luna.test.ts` gained a `tool.register` stub and `relay.test.ts` expects `agent:luna` after the relay pair
- [x] T002 [P] **(operator)** Skipped: operator task, real model calls. Re-measure the spike baselines the spec Assumptions name: run `docker/luna_stress.sh` with `SCENARIOS=tools R=3` against the spike mod and record per-run `request_user_input` counts and `apply_patch` attempts from the rollouts in `specs/028-agents-inc-as-mod/research.md` R3 notes (SC-005 baseline) Done 2026-10-25: spike commit cff7df4 in Docker (`SCENARIOS=tools R=3`, `codex debug models` first, plugin dir named `luna-brain`): 3 of 3 pass; `request_user_input` 0, 2, 1 per run; `apply_patch` 0. See research.md R3.

## Phase 2: Foundational

- [X] T003 Write `tests/test_luna_native.py` status cases with a fake HOME and receipt: slug equals the model-map luna entry that follows `agents_inc/routing.json` grunt codex pin; `codex` is `missing` without a receipt `codex_path`, `logged-out` without `~/.codex/auth.json`, `ready` with both; `catalog` is `missing` without a `models_cache.json` entry; `luna off` then `status` gives `offered: false`, `switch: off`; `luna on` restores it; other settings keys survive (FR-003, FR-020, FR-021; plan D5)
- [X] T004 Implement `status`, `on`, `off` in `agents_inc/install/luna_native.py` (new) and the `luna` subcommand in `agents_inc/install/cli.py`; reuse the atomic writer pattern of `write_agent_gate` in `agents_inc/install/hook.py:134-150` (FR-003, FR-020, FR-021)
- [X] T005 **(operator)** Skipped: operator task, needs a real Codex run; `CATALOG_WARM_COMMAND` in `runtime.py` and `WARM_CMD` in `docker/luna_stress.sh` hold a placeholder marked `TODO T005`. Probe which Codex 0.159.2 command writes `~/.codex/models_cache.json` in a fresh `CODEX_HOME` with the fewest model calls; record the command and its cost in `specs/028-agents-inc-as-mod/research.md` R3 (FR-011 fix text; the T012 warm step uses it) — Done 2026-10-25 (supervisor, Docker probe): `codex debug models` writes models_cache.json with no model call and no session; `CATALOG_WARM_COMMAND` and `WARM_CMD` name it; research.md R3 records it.

**Checkpoint**: `agents-inc luna status --json` answers; the mod can be told what to register.

## Phase 3: User Story 1 - luna runs as a native subagent (P1) 🎯 MVP

**Goal**: `agents-inc:luna` starts with the Agent tool like haiku, every step answered by luna.
**Independent Test**: the four stress scenarios with the luna type and once with haiku, on macOS and in the Linux container (T014, T015).

- [X] T006 [US1] Add cases to `mods/agents-inc/hooks/luna.test.ts`: `session.start` registers `luna` with no `tools`, no `permissionMode`, `model: 'haiku'` only when a stubbed `agents-inc luna status --json` says `offered: true`; HEADER names the slug from `status`, not `gpt-6-luna`; `AGENT_TYPES` accepts `agents-inc:luna` and rejects `luna-brain:luna` and bare `luna` (FR-001, FR-002, FR-003)
- [X] T007 [US1] Implement T006 in `mods/agents-inc/hooks/luna.ts`: status call, conditional register, slug in HEADER, `AGENT_TYPES = ['agents-inc:luna']`, debug prefix `agents-inc luna:` (FR-001, FR-002, FR-003; plan D1 items 1, 3, 5)
- [X] T008 [US1] Add cases to `mods/agents-inc/hooks/luna.test.ts`: system prompt lines naming the placeholder model removed; catalog carries argument types; a resumed thread gets only messages after `sent`; a compacted conversation starts a fresh thread; two sessions with the same agent id text get different thread paths under `.scratch/agents-inc-luna/<session>/`; no `.prompt.txt` written unless `AGENTS_INC_LUNA_DEBUG=1`; SendMessage follow-up reuses the same thread file (FR-004, FR-005, FR-024; spec edge cases compaction, collision, model lines) — the debug-on copy is untested: the plugin test harness has no `process.env`, so only the off case is covered
- [X] T009 [US1] Implement T008 in `mods/agents-inc/hooks/luna.ts`: `threadPath` with `$.session.id()`, debug-gated prompt copy (FR-005, FR-024; plan D1 item 4)
- [X] T010 [US1] Port and extend the spike step tests in `mods/agents-inc/hooks/luna.test.ts`: hand-back on and off (no `SubagentHandback` named when absent); first tool-requesting message wins over a guessed final; hand-back next to another tool dropped; unknown tool rejected once with a correction, second bad reply unparsable; one push for a refusal or a named-but-unrun tool, push reads task text without reminders; usage is the rise in running totals, tagged with the slug; thinking chunk while running, then text and tool chunks (FR-006, FR-007, FR-008, FR-009; spec edge cases)
- [X] T011 [US1] Make T010 pass in `mods/agents-inc/hooks/luna.ts` (FR-006 to FR-009)
- [X] T012 [US1] Update `docker/luna_stress.sh` per plan D9: copy `mods/agents-inc`, `subagent_type agents-inc:luna`, default `R=10`, parent `--model sonnet`, `SRC`/`OUT` variables for the macOS host; a warm step before any scenario that runs the command T005 records and fails the suite unless `models_cache.json` holds the slug; step count from the new prefix `agents-inc luna: step` (the old `luna-brain:` grep goes); keep each run's stream-json `permission_denials` and tool-use and tool-result pairs; columns `rui` and `claude_steps`, `HAIKU=1` baseline with `general-purpose`/`haiku`, `steps5` scenario for SC-006 (FR-011, FR-028; SC-001, SC-002, SC-003, SC-005, SC-006)
- [X] T013 [US1] Run `claude plugin validate mods/agents-inc` and `claude plugin test mods/agents-inc`; both green (SC-008)
- [X] T014 [US1] **(operator)** Skipped: operator task, real model calls, docker. Needs T005. Run `docker/luna_stress.sh` (four scenarios, 10 runs each) in the Linux dev container and on macOS; record pass counts, wrong values, `claude_steps`, `rui` and the `steps5` usage delta in `specs/028-agents-inc-as-mod/research.md` (SC-001, SC-003, SC-005, SC-006) — Done 2026-10-25 in the Linux dev container only (macOS not run): s028g and s028i scored 38/40 on the four scenarios (SC-001); s028i 58/60 overall, steps5 10/10, SC-006 delta 0.0% on 10 of 10, delete tree clean, 0 placeholder leaks, 0 Codex-side acting calls. Earlier runs s028b to s028f (33, 37, 37, 40, 35) drove the push, fresh-thread, early-stop, partial-Read and request_user_input replay fixes. — macOS host 2026-10-25: first pass lost 17 runs to idle sleep (debug log "clock jump"); rerun of par, delete, steps5 under `caffeinate -is`: combined 57/60, main four 38/40, steps5 9/10, delete 10/10, usage delta 0.0% on 10/10. All 3 failures are request_user_input loops (Codex exit 1, or a refusal). — macOS host follow-up 2026-10-25: `docker/luna_stress.sh`, tools/par/steps5, R=5. Four context notes dropped plus new `NO_TOOL_INSTRUCTIONS`: 14/15 pass, 426 `request_user_input` calls. The read-only sandbox note caused the "May I run wc?" asks. Adding `default_mode_request_user_input=true` (exec answers `{"answers":{}}`): 11/15 pass, 303 calls; failures tools.1, tools.4, par.2, steps5.1. Rejected because the pass rate fell; keep the four note settings and new instructions.
- [X] T015 [US1] **(operator)** Skipped: operator task, real model calls. Run the same scenarios with `HAIKU=1`; compare the kept `permission_denials` and tool-use and tool-result pairs per scenario with the luna runs (SC-002) — Done 2026-10-25, outcome scores only (s028haiku): haiku 40/60; follow 0/10 by design (the follow scenario expects the gpt-6 name); tools 0/10 with B=96 (Read numbers the empty line after the final newline, which the luna mod strips); latin, par, delete, steps5 10/10. Mean seconds haiku vs luna (s028g): latin 5.4 vs 9.7, tools 8.7 vs 15.5, follow 9.7 vs 18.0, par 8.6 vs 14.9, delete 10.6 vs 11.7, steps5 11.6 vs 32.3. The per-scenario permission_denials and tool-pair comparison was not run. — macOS 2026-10-25 (haiku 41/60): permission_denials empty for both types in every scenario; tool calls per scenario luna/haiku: tools Bash 12/14 Read 11/10, par Bash 27/30, steps5 Bash 34/50 (sleep-hit pass), delete luna none, haiku Bash 7 (all errors, Bash denied) Glob 10 Read 1; no tool errors on luna.

**Checkpoint**: luna works as a native type from a checkout with `--plugin-dir`.

## Phase 4: User Story 2 - luna cannot act outside the harness (P1)

**Goal**: the Codex process offers luna nothing that acts; the harness is the only gate.
**Independent Test**: the `delete` scenario with Edit, Write and Bash denied (T022).

- [X] T016 [P] [US2] Add cases to `tests/test_codex_tool_access.py`: `no_tool_args(host_tools=True, slug)` with no cache entry raises an error starting `WB_LUNA_CATALOG_MISSING:` naming `models_cache.json` and the fix; `run_codex(..., host_tools=True)` then starts no process and exits 3; the built catalog has `tool_mode` `direct`, `shell_type` `disabled`, `multi_agent_version` `none`, no `apply_patch_tool_type`; host-tools argv keeps `-s read-only` and `web_search="disabled"`; a host-tools run sets `CODEX_HOME` to an isolated home with no `mcp_servers` in its `config.toml`; the `agents-inc run: record` line names the catalog and `codex_home: isolated` (FR-010, FR-011, FR-012, FR-013; US2 scenarios 1, 2)
- [X] T017 [US2] Add isolated-home cases to `tests/test_codex_tool_access.py` with a fake HOME holding `.codex/models_cache.json` (an entry for the slug) and `.codex/auth.json`, and an operator `CODEX_HOME` env that points elsewhere: the host-tools argv names a `model_catalog_json` built from `HOME/.codex/models_cache.json`, not from the env `CODEX_HOME`; the child env `CODEX_HOME` is the isolated dir; that dir holds an `auth.json` symlink to the real file and no `models_cache.json`; the child env keeps the caller's `HOME` and `PATH` (no `lead_env` scrub); no real cache gives `WB_LUNA_CATALOG_MISSING`, exit 3 and no temp home created; no real `auth.json` gives `WB_CODEX_AUTH_MISSING`; an `auth.json` replaced by a real file keeps the home, prints `isolated CODEX_HOME kept: auth.json is no longer a symlink` and turns exit 0 into 1 (FR-011, FR-013; plan D3 item 2)
- [X] T018 [US2] Implement T016 and T017 in `agents_inc/install/runtime.py`: `no_tool_args` takes the catalog path, `build_codex_argv` passes it, the catalog is built from `Path.home() / ".codex"` before `lead_codex_home` runs, `run_codex` isolated home for `host_tools`, record line at `runtime.py:555`; `lead_codex_home` itself unchanged (FR-010 to FR-013; plan D3 items 1 to 4)
- [X] T019 [P] [US2] Add a case to `tests/test_codex_tool_access.py` with a fake Codex JSONL stream holding `request_user_input`, `exec` and `apply_patch` calls: `run_codex_thread` prints one `agents-inc run: tools {...}` line with each count (FR-014)
- [X] T020 [US2] Implement the count in `agents_inc/install/runtime.py` `run_codex_thread` / `thread_progress_line` (FR-014; plan D3 item 5)
- [X] T021 [US2] Add cases to `mods/agents-inc/hooks/luna.test.ts`: the `tools` line lands in the step debug line; a run that exits 3 with `WB_LUNA_CATALOG_MISSING` ends the step with the catalog failure text and no fresh-thread retry; a denied tool result reaches luna as the same `tool_result` error block a haiku agent gets (FR-011, FR-014; US2 scenario 3)
- [X] T022 [US2] Script part done (the `delete` scenario is in `docker/luna_stress.sh`); the operator run is skipped: real model calls, docker. Add the `delete` scenario to `docker/luna_stress.sh` per plan D9; **(operator)** run it 10 times; record file changes and Codex-side acting calls (SC-004)

## Phase 5: User Story 3 - luna never silently becomes another model (P1)

**Goal**: every luna failure is loud; the placeholder is never called.
**Independent Test**: plugin tests with a fake `process.spawn` (T023, T024, T028).

- [X] T023 [US3] Add failure cases to `mods/agents-inc/hooks/luna.test.ts` with a fake `process.spawn`: spawn throws (Codex missing), the run outlives a short injected limit (timeout), no JSON twice (unparsable), exit 1 (run failure), exit 75 with the existing `hit a usage or rate limit; retry at` line; each ends with the plan D4 text, quota skips the retry, and `next` is never called (FR-015, FR-016; SC-003) — the timeout text is untested: the harness has no clock advance
- [X] T024 [US3] Add identity cases to `mods/agents-inc/hooks/luna.test.ts`. First a probe case: inside `turn.step`, does `$.prompt.compose` return the luna agent's own prompt? If not, drop check (3) from plan D2 and drop the marker case below. Then: spawn record missing but `agent.list` lists the type (answered by luna); `agent.list` says another type (passed to `next`); `agent.list` throws and the prompt marker is present (answered by luna); both unavailable (step fails, `next` not called) (FR-017; research R4) — the probe was impossible without the engine, so check (3) and its marker cases are dropped; an unidentifiable agent fails closed
- [X] T025 [US3] Implement plan D2 and D4 in `mods/agents-inc/hooks/luna.ts` (FR-015, FR-016, FR-017)
- [X] T026 [P] [US3] Add cases to `tests/test_codex_tool_access.py`: a fake Codex whose stderr matches `QUOTA_RE` makes `agents-inc run --host-tools` exit 75 with the existing `agents-inc run: codex <slug> hit a usage or rate limit; retry at` message (`runtime.py:646`) and no second quota line; a plain exit code is unchanged for runs without `--host-tools` (FR-016, FR-023)
- [X] T027 [US3] Confirm T026 passes on the existing quota branch (`runtime.py:636-657` already returns 75); change `agents_inc/install/runtime.py` only if a host-tools path bypasses that branch (FR-016; plan D3 item 6)
- [X] T028 [US3] Add abort cases to `mods/agents-inc/hooks/luna.test.ts`: abort mid-run ends the stream, no retry or push runs, the thread file is not rewritten after the abort, state is not marked used; then implement in `mods/agents-inc/hooks/luna.ts` (FR-018) — implemented; abort is untested in the harness
- [X] T029 [US3] Add a load-time contract check in `mods/agents-inc/hooks/luna.ts` with a test in `mods/agents-inc/hooks/luna.test.ts`: when `$.agent.register`, `$.process.spawn` or `turn.step` streaming is missing, the type is not registered and the debug log says why (US3 scenario 3; spec edge case contract change)

## Phase 6: User Story 4 - install, doctor, rollback (P2)

**Goal**: install ships the type; doctor reports it; one switch turns it off; old routes keep working.
**Independent Test**: Docker clean-install check (T038).

- [X] T030 [P] [US4] Update `tests/test_agent_gate.py` (lines 99-102) and `tests/test_hook_persona_guard.py` (line 78): `agents-inc:luna` passes `persona_deny` and `gate_deny` in `enforce`, `advisory` and `off`, foreground and background; `luna-brain:luna` is denied under `enforce` and gets the persona check; `x-agents-inc:luna` is denied (FR-022)
- [X] T031 [US4] Implement `NATIVE_TYPES` and `_is_native` in `agents_inc/install/hook.py` replacing `BRAIN_PREFIX` and `_is_brain` (FR-022; plan D7)
- [X] T032 [P] [US4] Add cases to `tests/test_doctor_codex_optional.py`: `LUNA_OFF`, `LUNA_CODEX_NOT_READY`, `LUNA_CATALOG_MISSING` are warnings, `ready` stays true, codes unchanged; `agents-inc doctor` prints `luna type: ready|off|unavailable (<code>)` (FR-020; US4 scenarios 1, 2)
- [X] T033 [US4] Implement `_luna_warnings` in `agents_inc/install/doctor.py` and the doctor line in `agents_inc/install/cli.py` (FR-020; plan D8)
- [X] T034 [US4] Add an `agent.offer` case to `mods/agents-inc/hooks/luna.test.ts` (status `offered: false` hides the type; a throwing guard hides it) and implement it in `mods/agents-inc/hooks/luna.ts` (FR-020, FR-021; plan D1 item 2) — the throwing-guard case is untested
- [X] T035 [P] [US4] Add a case to `tests/test_mod_install.py`: a built bundle holds `mods/agents-inc/hooks/luna.ts` and `hooks.json` lists it; install and repair run the same `claude plugin` commands as before (FR-019)
- [X] T036 [P] [US4] Add regression cases to `tests/test_codex_tool_access.py`: the argv `agents-inc dispatch --model luna` builds, the `agents-inc run` command line the `@luna` at-route builds (`skills/codex-bridge/scripts/at_route.sh:179`) and a broker luna Worker argv each carry no `--host-tools`, no `model_instructions_file`, no `model_catalog_json` and no isolated `CODEX_HOME` (FR-023; SC-007)
- [X] T037 [US4] Write a luna section in `mods/agents-inc/README.md`: what `agents-inc:luna` is, `agents-inc luna off|on`, the doctor line, the debug-line prefix `agents-inc luna:` (it replaces the spike's `luna-brain:`), rollback with `agents-inc repair --no-mod`, pre-028 routes still available (FR-021, FR-023)
- [x] T038 [US4] **(operator)** Skipped: operator task, docker and real model calls. Docker clean-install check: install, `tools` scenario, doctor, `agents-inc luna off`, new session offers no type, `agents-inc dispatch --model luna` returns the same outcome class as before 028 on the same slots, `agents-inc luna on`; then a run without the mod (`agents-inc repair --no-mod`, or no `--plugin-dir`) that asks for `agents-inc:luna` and gets the unknown-type error (US4 independent test; US3 scenario 3; SC-007) Done 2026-10-25 in Docker: install + doctor ok; `tools` 1 of 1 pass; `luna off` offers no type and a new session lists none; `luna on` restores it; a fresh `--no-mod` install gives the unknown-type error. Open: `dispatch --model luna` on the same slots was green 3 of 8 and red 5 of 8 (report-noncompliant, caveman element), with the switch on and off alike; no pre-028 baseline measured. `repair --no-mod` over an existing mod install keeps the mod.

## Phase 7: User Story 5 - retirement inventory, ledger and canon (P3)

**Goal**: the native path writes its ledger record and scope snapshot; scope stays inside the Inventory; canon records the route.
**Independent Test**: review of the Inventory against `git diff --stat` (T045) and the D69 entry (T046).

- [X] T039 [US5] Add `begin`/`end` cases to `tests/test_luna_native.py` with a temp git repo and fake state dir: `begin` writes `<state>/luna-runs/<session>/<agent>/snapshot.json` and one host-ledger row (`provider` `codex`, `model` slug, `source` `native-luna`, `status` `dispatched`); `end` with an untouched tree records `snapshot: unchanged`, with an edited file records `changed:1` and the path, outside git records `no-repo`; `end` sets `status` to the outcome and leaves `verdict` null; a second `end` for the same agent appends a return update to the same node; two agents begun in the same repo, where only the second edits a file, both record `changed:1` with that path (the result says "tree changed during the run", not who changed it) (FR-026; plan D6)
- [X] T040 [US5] Implement `begin` and `end` in `agents_inc/install/luna_native.py` and their CLI wiring in `agents_inc/install/cli.py`, loading `pre_dispatch_snapshot.py` from the installed bundle as `agents_inc/install/dispatch.py:247` does (FR-026)
- [X] T041 [P] [US5] Add a case to `tests/test_host_ledger.py`: `dispatch_row` returns `None` for an Agent payload with `subagent_type` `agents-inc:luna`, and still builds a row for other types (FR-026)
- [X] T042 [US5] Implement the skip in `agents_inc/host_ledger.py` `dispatch_row` (FR-026; plan D6 item 3)
- [X] T043 [US5] Add cases to `mods/agents-inc/hooks/luna.test.ts`: `agent.spawn` for the luna type runs `agents-inc luna begin` once with session, agent and cwd; a `begin` that resolves late holds the agent's first `turn.step` until it resolves, and Codex is not started before then; `turn.complete` for a luna id runs `agents-inc luna end` with the outcome and usage; a changed-tree answer from `end` adds one line beneath the answer; a failing `begin` or `end` does not fail the step (FR-026)
- [X] T044 [US5] Implement T043 in `mods/agents-inc/hooks/luna.ts`: keep the `begin` promise per agent id and await it in the first `turn.step` (FR-026; plan D6 items 1, 2, 4)
- [X] T045 [US5] Scope check (result in the implement report; `analyze.md` is not edited here): compare `git diff --stat` of the implement branch with the spec Inventory; list every edited path, confirm each is in a change row and no "keep" row path is edited (`lead_codex_home` is reused, not edited), and record the result in `specs/028-agents-inc-as-mod/analyze.md` follow-up (FR-025; SC-008; US5 scenario 1)
- [X] T046 [US5] Draft D69 in `docs/DECISIONS.md`: native luna route, the parts of D59, D61 and D62 it amends (`docs/DECISIONS.md:628`, `:636`, `:644`), the Q1 to Q5 answers; land the operator-approved (2026-10-24, spec Q4) P7 amendment in `.specify/memory/constitution.md` (MINOR bump, D69 cited); state that P8 does not apply to native subagent calls and that P3 holds through the parent's verification; tag LESSON-CANDIDATE in the report for the CoS to land (FR-027; constitution P10)

## Phase 8: Polish

- [X] T047 Skipped: needs T014, an operator run; `mods/luna-brain/` stays. Delete `mods/luna-brain/` once T014 passes on the shipped type, and remove its remaining mentions in `tests/test_codex_tool_access.py:72` and `agents_inc/install/runtime.py:327-328` comments (FR-019; plan D10). Skip and record why if the operator keeps the spike folder — Done 2026-10-25: `mods/luna-brain/` removed after T014; the runtime.py and cli.py mentions now name the agents-inc:luna type. tests keep `luna-brain:luna` as a lookalike that must stay denied.
- [X] T048 CHANGELOG entry added; plugin validate and test green here; the full suite was run by the CoS outside the sandbox (1724 OK, 17 skipped), not by this delegate. Run `python3 -m unittest discover -s tests -p 'test_*.py'`, `claude plugin validate mods/agents-inc` and `claude plugin test mods/agents-inc`; all green; add a `CHANGELOG.md` entry (SC-008)
- [ ] T049 Skipped: moves to DomI, CoS or operator step, runs last. Move specs to DomI: run `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`

## Dependencies

- Phase 1 -> Phase 2 -> US1. US2 Python tasks (T016-T020, T026-T027) need only Phase 2 and may run beside US1. US2 T021 and US3 T023-T025, T028-T029 edit `luna.ts` after T011.
- US4 T030-T033, T035-T036 are independent of the mod work; T034 needs T007.
- US5 T039-T042 need T004; T043-T044 need T011.
- Operator runs: T014 needs T005, T012, T025, T044; T015 needs T012, T025, T044; T022 needs T018, T020; T038 needs T033, T034.
- T047 needs T014. T048 needs every other task except T049. T049 depends on every other task and runs last.

## Parallel examples

- After T004: T016, T017, T019, T026, T030, T032, T035, T036, T041 (different files or independent test cases).
- `luna.ts` tasks are serial: T007 -> T009 -> T011 -> T021 -> T025 -> T028 -> T029 -> T034 -> T044.

## Implementation strategy

MVP = Phases 1-3 (US1) plus US2 and US3: the operator retires agents-inc's own boundary for this path only when Codex cannot act (US2) and luna cannot become haiku (US3), so the type is not offered by default before T018, T025 and T027 pass. US4 makes it installable; US5 adds the record and the canon entry. Soak (T014, T022, T038) runs before D69 lands.
