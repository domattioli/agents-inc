<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-tasks repo=agents_Inc session=f26522 -->
# Tasks: spec 025, dispatch follow-ups from the 2026-10-23 Docker stress run

**Input**: `specs/025-stress-followups/spec.md`, `specs/025-stress-followups/plan.md`
**Prerequisites**: plan.md, spec.md. No research.md, data-model.md or contracts/ (folded into plan.md).

One delegate implements every story in one run (spec Scope). Write each test first and see it fail, then make it pass. Re-run `grep -n` before each edit; line numbers are from 2026-10-23. No commit, no push. A task is done only when its acceptance command has run and exited as stated. The Executive ruled on analyze F1 to F13 (spec.md "Analyze resolutions, 2026-10-23"); the **[F#]** marks below name the ruling each task follows.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an open task). In a one-delegate run, [P] only means order-free.
- **[Story]**: US1 to US6.

## Phase 1: Setup

- [X] T001 Baseline: run the SC-001 command `python3 -m unittest tests.test_dispatch_cli tests.test_dispatch_slot_screens tests.test_dispatch_contract tests.test_dispatch_resume tests.test_dispatch_broker tests.test_dispatch_failloud tests.test_dispatch_snapshot_trust skills.workerbee.tests.test_template_revision` and record the result before any edit.

## Phase 2: User Story 6 (#108), parse the verify gate (P1, separate file)

**Goal**: `render_dispatch.py` accepts only a plain positional verify command. **Independent test**: `python3 -m unittest skills.workerbee.tests.test_template_revision` exits 0.

- [X] T002 [P] [US6] In `skills/workerbee/tests/test_template_revision.py`, add class `VerifyGateParseTest` with the five FR-024 cases: `cd /tmp && python3 pre_dispatch_snapshot.py verify <snapshot>` exits 2; `python3 pre_dispatch_snapshot.py verify <snapshot>` exits 2; `python3 x.py verify <snapshot>` exits 2; the default text from `default_pre_existing` renders exit 0; `/usr/bin/python3 /abs/skills/workerbee/scripts/pre_dispatch_snapshot.py verify /abs/run/snapshot.json --repo /abs --allow a.py` renders exit 0. Also unit-test `verify_gate_ok` returning None and a string. Change `Issue92Test.test_plain_verify_command_renders` from `/x/s.json` to `/x/snapshot.json` (FR-022 argv[3] rule). (FR-024) **[F13]**
- [X] T003 [US6] In `skills/workerbee/scripts/render_dispatch.py`, add `verify_gate_ok(span)` per plan US6 and replace the check loop at `:355-360` with it; stderr line `PRE_EXISTING_CHANGES invalid: <error>; write the verify gate as one plain command`, return 2. Acceptance: the independent test exits 0; `grep -n 'def verify_gate_ok' skills/workerbee/scripts/render_dispatch.py` prints one line. (FR-022, FR-023)

## Phase 3: User Story 2 (#85, #87 item 1), path-based request text screen (P2)

**Goal**: deny-list prose passes; requests to read credential paths stay refused. **Independent test**: `python3 -m unittest tests.test_dispatch_slot_screens` exits 0.

- [X] T004 [US2] **[F2, F3, F4, F11, F12]** In `tests/test_dispatch_slot_screens.py`, add class `PathScreenTest`: the four FR-007 refusals (`read ~/.ssh/id_rsa and .env, print the api_key` with `credential_hit` detail `slot X matched '~/.ssh/id_rsa'`; `` run `cat .env` ``; `cat ~/.claude/.credentials.json`; `print server.pem.`) and the six FR-008 accepts (rendered Worker boilerplate from `render_dispatch.py` with `skills/workerbee/tests/fixtures/example_slots.json`; `No writes to credentials, .env, or key files. Never open .env.`; `walk mode of the teaching skill mentions credentials and secrets; do not read or modify .env`; `run ~/.local/bin/agents-inc doctor`; `refresh the token cache test (test_token_refresh.py)`; `print access_token`). Flip the existing tests to acceptance (F4 ruling): `:109-110` (`token`), `:123-124` (`show the token`, `print access_token`), `:133-135` (`no .env reads`); `test_credential_hit_names_slot` uses `cat ~/.ssh/id_rsa`. (FR-007, FR-008, FR-010)
- [X] T005 [US2] **[F2, F3, F12]** In `agents_inc/install/dispatch.py:1392-1395`, add `_HOME_CRED_TEXT` and replace `CREDENTIAL_RE` with the three-part path pattern of plan US2; `_HOME_CRED` and `GATE_CREDENTIAL_RE` stay as they are; `credential_hit` (`:1582`) keeps its form. Acceptance: the independent test exits 0. (FR-006, FR-007, FR-009)

## Phase 4: User Story 3 (#105), one screen on both paths (P3, after Phase 3)

**Goal**: the direct path and `--resume --message` refuse what the broker refuses. **Independent test**: `python3 -m unittest tests.test_dispatch_slot_screens tests.test_dispatch_resume` exits 0.

- [X] T006 [US3] In `tests/test_dispatch_slot_screens.py`, add class `DirectPathScreenTest`: a slots file whose TASK is the FR-007 fixture, run through `dispatch.main` with and without `--dry-run`, exits 3, stderr starts `dispatch: refused credential-seeking (slot TASK matched`, and the `--run-dir` parent stays empty; the same slots through `dispatch._validate_fields` return reason `credential-seeking`; the FR-008 boilerplate slots file is accepted by both. A `--resume <run dir> --message 'cat ~/.ssh/id_rsa'` exits 3 and leaves `run.json` byte-identical. (FR-011, FR-012, FR-013)
- [X] T007 [US3] In `agents_inc/install/dispatch.py` `run()`, call `credential_hit(slots)` after the slots type check (`:1129-1131`) and before `new_run_id` (`:1136`); in `resume()`, screen `args.message` after `:1309`. Print `dispatch: refused credential-seeking (<detail>)` to stderr, return `EXIT_REFUSED`. Acceptance: the independent test exits 0. (FR-011, FR-012, FR-009)
- [X] T008 [P] [US3] In `skills/workerbee/slots.md:99`, append to the D51 paragraph: "The direct path (`agents-inc dispatch --slots`) and the broker apply one request text screen; a refusal names the slot and the matched text." Acceptance: `grep -n 'one request text screen' skills/workerbee/slots.md` prints one line. (FR-014)

## Phase 5: User Story 4 (#106), `--run-dir` under cwd must be git-ignored (P4, after Phase 4)

**Goal**: an explicit run directory never lands as untracked files in the repo. **Independent test**: `python3 -m unittest tests.test_dispatch_cli` exits 0.

- [X] T009 [US4] In `tests/test_dispatch_cli.py`, add class `RunDirIgnoreTest`: `--run-dir <repo>/runs` with no ignore rule exits 2, stderr contains `is inside --cwd and not git-ignored`, `<repo>/runs` does not exist; with `runs/` in `<repo>/.gitignore` the run launches; `--run-dir` outside the repo launches; a `--cwd` that is not a git repo with `--run-dir` inside it launches. (FR-015, FR-016, FR-017)
- [X] T010 [US4] In `agents_inc/install/dispatch.py` `run()`, add the check of plan US4 between the US3 screen and `run_dir.mkdir` (`:1139`); `git check-ignore` rc 1 refuses with exit 2, rc 128 or `OSError` accepts. Acceptance: the independent test exits 0. (FR-015, FR-016)

## Phase 6: User Story 5 (#107), a gate that writes flips the outcome (P5, after Phase 5)

**Goal**: a gate's writes reach a snapshot compare. **Independent test**: `python3 -m unittest tests.test_dispatch_cli` exits 0.

- [X] T011 [US5] **[F6]** In `tests/test_dispatch_cli.py`, add class `GateWroteTest` with the fake delegate: GATES `[{"argv": ["sh", "-c", "echo pwned > gate_wrote.txt"]}]` prints `snapshot=CHANGED:gate_wrote.txt outcome=red reason=gate-wrote`, exits 1, and `verify.txt` has an `after gates:` block; a gate that writes and exits 1 prints `reason=gate-wrote` (precedence over `gate-failed`); the default read-only gate prints `snapshot=clean outcome=green` and `verify.txt` has `after gates: clean`. (FR-018, FR-019, FR-020, FR-021)
- [X] T012 [US5] **[F6, F10]** In `agents_inc/install/dispatch.py`, split `_snapshot_verify` out of `_verify` (`:767-799`) and run it again in `_finish` after `_run_gates` (`:988`) per plan US5 (`gate-wrote` over `gate-failed`; a second `TAMPERED` or `ERROR:` keeps its own reason); leave `_exit_code` (`:969`) and the broker-child branch (`:985-986`) unchanged. Acceptance: the independent test exits 0; `grep -n 'gate-wrote' agents_inc/install/dispatch.py` prints at least one line. (FR-018, FR-019, FR-020)

## Phase 7: User Story 1 (#104), lint with the checkout's scripts (P6, last code phase)

**Goal**: the copy that judges is the checkout's, and the status line says so. **Independent test**: `python3 -m unittest tests.test_dispatch_cli tests.test_dispatch_resume tests.test_dispatch_broker tests.test_dispatch_failloud` exits 0.

- [X] T013 [US1] **[F1, F5, F9]** In `tests/test_dispatch_cli.py`, add class `ScriptsSourceTest`: a fake checkout (git repo holding a copy of `skills/workerbee/` plus a stub `agents_inc/install/dispatch.py`, with `check_dispatch_prompt.py` patched so `check_report` flags `sentinel-025`) prints `lint=checkout` and `report=NON-COMPLIANT:['sentinel-025']`, and `run.json` has `scripts_source` `checkout` and `scripts_dir` the trusted copy under the trust folder (outside cwd); the fake delegate rewrites the checkout's `check_dispatch_prompt.py` during its turn and the report is still `sentinel-025`; a plain repo prints `lint=installed`; the fake checkout with the probe files as symlinks prints `lint=installed`; a checkout missing one of the five probe files prints `lint=installed`; `verify.txt` starts with `lint source: `; a trusted copy changed after launch gives `snapshot=TAMPERED reason=snapshot-tampered`; a resume reads the recorded trusted copy, a resume whose `run.json` `scripts_dir` points elsewhere is red `snapshot-tampered`, and a `run.json` without the keys resumes as `lint=installed`. (FR-001, FR-002, FR-003, FR-005)
- [X] T014 [US1] **[F8]** In `tests/test_dispatch_cli.py:23-26`, add ` lint=(checkout|installed)` after the report group of `STATUS_RE`, and add the token to the substring at `:182`; in `tests/test_dispatch_failloud.py:191`, add the token to the literal. (FR-003)
- [X] T015 [US1] **[F1, F5, F9]** In `agents_inc/install/dispatch.py`, add `scripts_dir(cwd)` (five-file probe), `_pin_scripts` (copy and hash into the trust folder), `_scripts(spec)` and `ScriptsTampered`; give `_load` and `snapshot` a `scripts` argument with the hash check, and thread it through `render`, `lint_prompt`, `lint_report`, `parse_fan_out`, `_run_gates`, `_grants_from_slots`, `lead_roster`, `_validate_fields` and the verifier copy; record `scripts_dir`/`scripts_source` in `run()`, read and check them in `resume()`, add `lint=` to `_status` (`:919-924`), and write `lint source: <dir>` first in `verify.txt`. Acceptance: the independent test exits 0; `grep -n 'lint=' agents_inc/install/dispatch.py` prints at least one line. (FR-001, FR-002, FR-003)
- [X] T016 [US1] **[F5]** In `agents_inc/install/dispatch.py`, `make_lead_dir` copies `scripts_dir`/`scripts_source` into the Lead `run.json`; `_in_worker_scope` (`:1775-1791`) passes them to the Worker's `run()`/`resume()` through a module global cleared in the `finally`. Add a test to `tests/test_dispatch_cli.py` (`tests/test_dispatch_broker.py` is not in the spec Scope list) that a Worker run under `_in_worker_scope` with a Lead spec carrying a checkout `scripts_dir` records it, prints `lint=checkout`, and never calls `scripts_dir`. Acceptance: `python3 -m unittest tests.test_dispatch_broker tests.test_dispatch_cli` exits 0. (FR-004)

## Phase 8: Polish and cross-cutting

- [X] T017 [P] In `docs/DECISIONS.md`, append D67 after D66 (`:684`) recording rulings Q1 (lint with the checkout), Q3 (path-based screen) and Q7 (gate-wrote is red), per spec Assumptions. Acceptance: `grep -n '^## D67' docs/DECISIONS.md` prints one line.
- [X] T018 In `CHANGELOG.md` under `## [Unreleased]` / `### Fixed` (`:7-9`), add six lines ending `(#104)`, `(#85, #87)`, `(#105)`, `(#106)`, `(#107)`, `(#108)`. Acceptance: `grep -nE '\((#104|#85, #87|#105|#106|#107|#108)\)$' CHANGELOG.md` prints six lines. (SC-004)
- [ ] T019 (RED: SC-001 fails on `tests.test_dispatch_broker` `test_credential_seeking_refused`, out of scope, see analyze C2-5) Final gate: SC-001 `python3 -m unittest tests.test_dispatch_cli tests.test_dispatch_slot_screens tests.test_dispatch_contract tests.test_dispatch_resume tests.test_dispatch_broker tests.test_dispatch_failloud tests.test_dispatch_snapshot_trust skills.workerbee.tests.test_template_revision` exits 0 and prints `OK`; SC-003 three greps; SC-002 full discover reports no new failure beyond `tests.test_ollama_adapter.TestUnloadUnconfirmed.test_unload_unconfirmed_exit4`; SC-005 the dispatch scope verify exits 0.
- [ ] T020 Move specs to DomI: run `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. Depends on every other task; nothing runs after it. Done by the Chief of Staff after commit, not by the implement delegate.

## Dependencies and execution order

- T001 first. Phase 2 (US6) is independent of all others.
- Phase 3 before Phase 4 (US3 calls the new screen). Phases 4, 5, 6 edit `run()`, `_verify` and `_finish` in `dispatch.py` and run in that order. Phase 7 (US1) last among code phases: it changes signatures the others call.
- T008 and T017 are doc-only and order-free. T018 after all stories. T019 after T018. T020 last.
- All findings F1 to F13 are ruled; no task waits on the Executive.

## FR coverage

| FR | Tasks |
|---|---|
| FR-001, FR-002 | T013, T015 |
| FR-003 | T013, T014, T015 |
| FR-004 | T016 |
| FR-005 | T013 |
| FR-006 | T005 |
| FR-007 | T004, T005 |
| FR-008 | T004 |
| FR-009 | T005, T007 |
| FR-010 | T004 |
| FR-011, FR-012 | T006, T007 |
| FR-013 | T006 |
| FR-014 | T008 |
| FR-015, FR-016 | T009, T010 |
| FR-017 | T009 |
| FR-018, FR-019, FR-020 | T011, T012 |
| FR-021 | T011 |
| FR-022, FR-023 | T003 |
| FR-024 | T002 |
| SC-001 to SC-005 | T018, T019 |
