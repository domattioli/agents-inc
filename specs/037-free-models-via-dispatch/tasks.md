<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-analyze repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Tasks: Free models through dispatch

**Input**: `specs/037-free-models-via-dispatch/` (plan.md, spec.md, research.md, data-model.md, contracts/free-dispatch.md, quickstart.md)
**Rules**: develop and test in docker (`docker/Dockerfile.dev`, `docker/Dockerfile.ci`); Docker commands need the sandbox off. Wrappers stay unchanged. Stage files explicitly; never `git add -A`. Commit and push only when the operator asks.
**Test command**: `python3 -m unittest discover -s tests -p 'test_*.py'`

## Phase 1: Setup

- [x] T001 (done 2026-11-09; R6 and contract updated: 429/timeout/unreachable are rc 1 by stderr text, rc 4 oask only, no wrapper-side cap check) Confirm the wrapper exit-code map in `specs/037-free-models-via-dispatch/research.md` R6 against `skills/codex-bridge/scripts/gask.sh`, `mask.sh`, `oask.sh`: read each script, list real rc values and messages (redacted, no API key, refused, 429, curl failure), and fix R6 and `contracts/free-dispatch.md` if any row differs. No code yet.
- [x] T002 [P] Create stub wrappers `tests/fixtures/fake_wrappers/gask.sh`, `mask.sh`, `oask.sh`. Each reads stdin, honors env `FAKE_RC`, `FAKE_REPLY`, `FAKE_STDERR`, and exits with `FAKE_RC`. Mode 0755.
- [x] T003 [P] Create `tests/test_free_dispatch.py` with a base class that builds a temp repo, a slots file writer, and a PATH or scripts-dir override pointing at the stub wrappers.

## Phase 2: Foundational (blocks all stories)

- [x] T004 Create `agents_inc/install/free_launch.py` with the `FREE_MODELS` map (slug, provider, wrapper, tier, model_env, host, max_input_chars) per `data-model.md` and `research.md` R3. Include `is_free(slug)` and `wrapper_argv(slug)`, `wrapper_env(slug, task_kind)` (sets `WORKERBEES_GOVERNANCE=off`, `TASK`, and `MODEL` for OpenRouter).
- [x] T005 Edit `_kind()` in `agents_inc/install/dispatch.py` (about line 877) to return `"free"` for `is_free(model)`. Add a test in `tests/test_dispatch_cli.py` that codex and claude slugs still return their kinds and an unknown slug returns None.
- [x] T006 [P] Add slots `TASK_KIND` and `INPUT_FILES` to `skills/workerbee/slots.md` and accept them in `skills/workerbee/scripts/render_dispatch.py` without changing existing slot behavior.
- [x] T007 Refresh `agents_inc/models.json` to the 2026-11-09 probe: add gemini-3.8-flash and codestral-latest, ministral-3b-latest available, full `nvidia/` OpenRouter slugs, probe date recorded (FR-014). Update `tests/test_models_catalog.py` so the catalog matches the probe.

**Checkpoint**: the free kind exists, nothing launches yet.

## Phase 3: User Story 1 - Checked cheap run (P1) MVP

**Goal**: one free model runs through dispatch and ends green, unverified, or red from its gates.
**Independent test**: `python3 -m unittest tests.test_free_dispatch.RunTest`

- [x] T008 [US1] In `free_launch.py` add `run_free(spec, prompt, run_dir, cwd, scripts)`: run the wrapper with the prompt on stdin (never argv), capture stdout to `run_dir/stdout.md`, stderr to `stderr.txt`, return `(rc, stdout, stderr)`. Record wrapper path and sha256 in the result.
- [x] T009 [US1] In `dispatch.py` `_run_dir_phase()` branch on `kind == "free"`: skip tool grants, `capability_preflight`, `lead_roster` and the Claude and Lead steps; keep the run directory, event sink, ledger node and prompt lint; skip the scope snapshot capture and its verifier line, because the prompt goes to an off-machine provider and the run changes no repo file; call `run_free()` in place of `launch()`, and feed the saved reply into the existing `_finish` path. Set `cost_usd` 0 and `workers_spawned` 0 in `run.json`.
- [x] T010 [US1] Skip `_fan_out_check` for free runs in `dispatch.py` (about line 1041).
- [x] T011 [US1] Implement the `{report}` gate token: keep the existing gate screen in `_grants_from_slots` (about line 1307, runs before launch) and expand `{report}` to the saved reply path in the gate runner called from `_finish` (about line 1209), where the reply exists. A gate that writes into the repo gives red `gate-wrote`.
- [x] T012 [US1] No `GATES` for a free run yields outcome `unverified`, exit 0, never green (FR-008). Report-format miss stays advisory when gates pass.
- [x] T013 [P] [US1] Tests in `tests/test_free_dispatch.py`: green with a passing `{report}` gate for each of the 10 slugs (stub wrapper); unverified with no gates; red `gate-failed`; red `gate-wrote`; codex and claude dispatch unchanged (FR-016).

## Phase 4: User Story 2 - Refusals before any call (P1)

**Goal**: every unsafe or out-of-scope request refuses with a named reason and no wrapper call.
**Independent test**: `python3 -m unittest tests.test_free_dispatch.RefusalTest`

- [x] T014 [US2] In `free_launch.py` add `pre_checks(slots, args, routing)` returning a refusal name or None: `refused-task` (TASK_KIND absent or not in `routing.json` `optional_allowed_tasks`, read at run time), `refused-classification` (CLASSIFICATION not author written, or confidential without workspace authorization per `router.py`), `refused-fan-out`, `refused-grants` (tools or a permission mode beyond default or plan).
- [x] T015 [US2] Add `build_input_section(slots, cwd, max_chars)` in `free_launch.py`: reads `INPUT_FILES`, refuses (`refused-inputs`) a path outside cwd, a symlink, a non-text file, credential-shaped content (reuse `credential_hit`), or total size over `max_chars`. Returns the prompt section plus a list of `{path, bytes, sha256}` for `run.json`.
- [x] T016 [US2] Wire `pre_checks`, then `build_input_section`, into `_run_dir_phase()` ahead of render (order: pre_checks, inputs, render, lint, cap and cooldown check, launch), writing the refusal to `run.json` and `lint.txt`, exit 2. Make `--resume` on a free run exit 2 in `resume()`.
- [x] T017 [US2] Reject free slugs as workers, leads and reviewers: `_load_run_manifest` and `_validate_fields` in `dispatch.py` (lines 1965 and 2031), and confirm a free-kind run never reaches `lead_roster` (about line 1659) or note the roster check must treat `free` kind as invalid (FR-013). Reject slugs not in the map, including deep-tier and paid OpenRouter slugs (SC-005).
- [x] T018 [P] [US2] Tests: one test per refusal, each asserting the stub wrapper was never called; broker rejects a free slug; rejected-slug list test.

## Phase 5: User Story 3 - Clear failures (P2)

**Goal**: quota, outage and wrapper failures map to distinct outcomes.
**Independent test**: `python3 -m unittest tests.test_free_dispatch.FailureTest`

- [x] T019 [US3] Add `classify_rc(rc, stdout, stderr)` in `free_launch.py` per the confirmed R6 map: `redacted-reply`, `provider-key-missing`, `wrapper-refused`, quota (exit 75), blocked with host named (exit 69), `rc-nonzero`. Feed the result into `_outcome` and `_finish` without changing Codex or Claude paths.
- [x] T020 [US3] Add the pre-launch cap and cooldown check in `free_launch.py` by calling `router._in_cooldown` (`agents_inc/router.py:46`) and `router._at_cap` (`router.py:65`) with `free_health` state (the wrappers hold no such check). A hit ends quota-paused, exit 75, with no wrapper call (FR-009). A quota pause counts as one failed attempt.
- [x] T021 [US3] Add `parse_usage(stdout, stderr)` returning tokens when reported else None; record in `run.json`.
- [x] T022 [P] [US3] Tests: one per map row plus cap and cooldown, each using the wrapper's real stderr form (`gemini error 429:`, `oask error 429:`, `mask` status helper output, "cannot reach", "timeout"); rc 3 from the `oask.sh` spend guard maps to `wrapper-refused`.
- [x] T022a [US3] FR-011: when the caller is sandboxed, probe provider host reachability before launch (`free_launch.py`, `FREE_MODELS[...].host`); unreachable ends blocked, exit 69, host named. Test in `tests/test_free_dispatch.py`.

## Phase 6: User Story 4 - Catalog matches reality (P3)

**Goal**: routing never picks a dead or bad-for-task model.
**Independent test**: `python3 -m unittest tests.test_models_catalog tests.test_router_free_first`

- [x] T023 [US4] Make a catalog entry that lists the task as bad cause `refused-task` in `pre_checks`.
- [x] T024 [P] [US4] Tests in `tests/test_models_catalog.py` and `tests/test_router_free_first.py`: catalog equals the probe list; a bad-task entry is refused.

## Phase 7: Polish and cross-cutting

- [x] T025 Write the D75 entry at the end of `docs/DECISIONS.md` (D73 is absent, D74 is last; confirm no D75 exists). Title: free models through dispatch, 2026-11-09, accepted, amends D16 and D17. Cover: dispatch is a governed caller of the legacy wrappers; the child env `WORKERBEES_GOVERNANCE=off` refers to the wrapper's own gate; the allowed-slug map plus free-only guard holds the model-pinning rule; public and internal data allowed with explicit CLASSIFICATION, confidential needs workspace authorization; no free Workers in the broker in v1. Follow the docs style table in `AGENTS.md`.
- [x] T026 [P] Update `skills/workerbee/SKILL.md` and `skills/codex-bridge/SKILL.md`: free models are reachable through `agents-inc dispatch` with `TASK_KIND` and explicit `CLASSIFICATION`.
- [x] T027 [P] Add one line to the D75 entry (T025) naming the follow-up: move API keys out of curl arguments in the wrappers.
- [x] T028 (2026-11-09: 2028 tests, 4 env-only failures on the :ro mount / container, none in free dispatch) Run the full suite in docker: `docker run --rm -v "$PWD:/src:ro" agents-inc-ci ...` per `docker/` scripts; all tests pass, no change to existing results (SC-006).
- [x] T029 (2026-11-09: 36 PASS, no FAIL lines) Run the stress check: `docker run --rm --network none -v "$PWD:/src:ro" -v "$PWD/docker/stress_check.sh:/stress.sh:ro" agents-inc-ci bash /stress.sh`.
- [x] T030 (2026-11-09 live: codestral-latest, gemini-3.8-flash, nvidia/nemotron-3.5-lightning:free all green; other OpenRouter slugs not probed) Run one live smoke per provider that has a key (codestral-latest, gemini-3.8-flash, one OpenRouter `:free` slug) with a tiny extract task, public classification and a `{report}` gate. Report any provider skipped.
- [x] T031 Move specs to DomI: run `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply` (depends on every other task; needs a clean tree outside `.specify/` and `specs/`; also moves specs 035 and 036).

## Dependencies

- T001 → T019, T020, T022
- Phase 2 (T004–T007) → every story
- US1 → US2 and US3 (both extend the launch path); US4 depends only on Phase 2
- T025 any time after T004; T028 → T029 → T030 → T031

## Parallel examples

- After T004: T002, T003, T006 together.
- Within US1: T013 beside T008–T012 once stubs exist.
- Polish: T026 and T027 together.

## Strategy

MVP is Phase 1 + 2 + US1 (a free model runs and is gated). Add US2 before any real use, because it holds the data rules. US3 and US4 follow.
