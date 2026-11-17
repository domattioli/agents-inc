<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-pipeline repo=agents_Inc session=spec024 -->
# Tasks: spec 024

Plan: `specs/024-easy-wins-90-91-92-93/plan.md`. Repo: agents_Inc, branch `development`. Implementers: one Worker per story through the agents-inc broker (haiku for US1, sonnet for US2, US3, US4); the Lead verifies each diff and reruns its acceptance command. Write each test first, then make it pass. Re-run `grep -n` before each edit. No commit, no push. A task is done only when its acceptance command has run and exited as stated.

## Phase 1: Setup

- [ ] T001 Confirm the baseline: `python3 -m unittest skills.workerbee.tests.test_element1_conditional skills.workerbee.tests.test_pre_dispatch_snapshot tests.test_dispatch_resume tests.test_dispatch_contract tests.test_dispatch_cli tests.test_packaging` runs; record its result in the report before any edit.

## Phase 2: User Story 1 (#90), Python 3.11 floor

Independent test: `grep -c '3\.10' pyproject.toml` prints `0`.

- [ ] T002 [P] [US1] In `pyproject.toml`, set `requires-python = ">=3.11"` (`:10`) and delete the `Programming Language :: Python :: 3.10` classifier line (`:28`). Acceptance: `grep -c '3\.10' pyproject.toml` prints `0`.
- [ ] T003 [P] [US1] In `README.md`, change the badge at `:11` to alt `Python 3.11+` and `python-3.11%2B`; change `:48` to "Python 3.11 or later"; add after `:48` the note "Python 3.10 support ends in the next release; the current 0.4 release stays installable on Python 3.10." Acceptance: `grep -n '3\.1[01]' README.md` shows the badge, the requirements line and the note only.
- [ ] T004 [P] [US1] In `AGENTS.md:23` and `docs/START-HERE.md:32`, change "Python 3.10 or later" to "Python 3.11 or later". Acceptance: `grep -n '3\.10' AGENTS.md docs/START-HERE.md` prints nothing (exit 1).
- [ ] T005 [US1] `python3 -m unittest tests.test_packaging` exits 0.

## Phase 3: User Story 2 (#91), gate-line lint

Independent test: `python3 -m unittest skills.workerbee.tests.test_element1_conditional tests.test_dispatch_contract` exits 0.

- [ ] T006 [US2] In `skills/workerbee/tests/test_element1_conditional.py`, add class `TestVerifiedExitLine` with: `[verified] Gate commands: none, exit code N/A. Snapshot integrity unverified; success gate not established.` not flagged; `[verified] Exit gate needs 10 scored, so the debate continues.` not flagged; `the gate exited cleanly [verified]` flagged `verified-exit-without-code`; `[verified] tests exit 0` not flagged; `[verified] gate exit code` (no value) flagged. Use `cdp.check_report` on a base report that otherwise passes (copy the minimal passing report shape from `tests/test_dispatch_contract.py` `TestFanOutAndReport.REPORT`).
- [ ] T007 [US2] In `tests/test_dispatch_contract.py:262-263`, change the `[verified] gate exit code N/A` assertion from `assertIn("verified-exit-without-code", ...)` to `assertEqual(..., [])` (spec Q2).
- [ ] T008 [US2] In `skills/workerbee/scripts/check_dispatch_prompt.py:172-173`, narrow `VERIFIED_EXIT_RE` and extend `EXIT_CODE_RE` per plan US2. Acceptance: the independent test exits 0, and `grep -n 'N/A' skills/workerbee/scripts/check_dispatch_prompt.py` prints at least one line.

## Phase 4: User Story 3 (#92), cwd-free snapshot verify

Independent test: `python3 -m unittest skills.workerbee.tests.test_pre_dispatch_snapshot skills.workerbee.tests.test_template_revision tests.test_dispatch_cli tests.test_dispatch_contract` exits 0.

- [ ] T009 [US3] In `skills/workerbee/tests/test_pre_dispatch_snapshot.py`, add tests: capture writes key `repo` equal to the resolved repo top level; verify run with `cwd` set to a temp dir outside any repo passes with `--repo <repo>`; the same passes with no `--repo` (the recorded key); `--repo` given with no value exits 2; `--repo` placed after an `--allow` group still parses.
- [ ] T010 [US3] In `skills/workerbee/scripts/pre_dispatch_snapshot.py`, record `repo` in `capture`, parse `--repo` in `main`, and resolve the top level in the plan US3 order; update the module docstring usage line. Acceptance: `python3 -m unittest skills.workerbee.tests.test_pre_dispatch_snapshot` exits 0 and `grep -n -- '--repo' skills/workerbee/scripts/pre_dispatch_snapshot.py` prints at least one line.
- [ ] T011 [US3] In `skills/workerbee/tests/test_template_revision.py`, add a test: a slots file whose `PRE_EXISTING_CHANGES` reads ``snapshot /x/s.json; verify with `cd /repo && python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify /x/s.json` `` makes `render_dispatch.py` exit 2 with `PRE_EXISTING_CHANGES invalid` on stderr; the example fixture still renders exit 0.
- [ ] T012 [US3] In `skills/workerbee/scripts/render_dispatch.py`, add the refusal per plan US3, after the PRE_EXISTING_CHANGES default fill. Acceptance: `python3 -m unittest skills.workerbee.tests.test_template_revision` exits 0.
- [ ] T013 [US3] In `agents_inc/install/dispatch.py` `_verify`, pass `--repo str(cwd)` to the verify call. In `tests/test_dispatch_cli.py`, add a dry-run test: the `prompt.md` PRE-EXISTING CHANGES verify command names an absolute snapshot path ending `snapshot.json` and contains no `cd ` and no `&&`. Acceptance: `python3 -m unittest tests.test_dispatch_cli` exits 0.
- [ ] T014 [US3] In `skills/workerbee/SKILL.md` Step 7 (`### Step 7: Know the sandbox gotchas`, `:559`), add after the commit bullet (`:564-566`): "- Do not commit while a delegate's snapshot is live: the commit moves HEAD and the delegate's verify fails for a change it did not make. If a commit is unavoidable, re-capture the snapshot and re-issue it to the delegate." Acceptance: `grep -n 're-capture the snapshot' skills/workerbee/SKILL.md` prints one line.

## Phase 5: User Story 4 (#93), resume search

Runs after Phase 4 (shared `dispatch.py` and `tests/test_dispatch_cli.py`). Independent test: `python3 -m unittest tests.test_dispatch_resume tests.test_dispatch_cli` exits 0.

- [ ] T015 [US4] In `tests/test_dispatch_resume.py`, add class `ResumeSearchTest`: (a) a temp git repo with a git-ignored `.scratch` as cwd, a run dir with a `run.json` lacking `session_id` under patched `$TMPDIR/agents-inc-runs/<id>`, `CLAUDE_SCRATCHPAD` unset: `dispatch.resume` finds it (stderr says `no session id recorded`, not `no run.json`); (b) no run anywhere: stderr is `dispatch: no run.json for <id> (searched: ...)` and lists `<repo>/.scratch/agents-inc-runs/<id>`, `$TMPDIR/agents-inc-runs/<id>` and `/tmp/agents-inc-runs/<id>` in that order, exit 2; (c) `--run-dir <d>` given: only `<d>/<id>` appears after `searched:`; (d) `dispatch._status(...)` ends with ` (resume with --resume <abs run dir>)`.
- [ ] T016 [US4] In `agents_inc/install/dispatch.py`, add `_resume_candidates`, use it in `resume()` for a bare id, and add the `_status` suffix per plan US4. Update `STATUS_RE` in `tests/test_dispatch_cli.py:22-24`. Acceptance: the independent test exits 0, and `grep -n 'searched:' agents_inc/install/dispatch.py` prints at least one line.

## Phase 6: Polish

- [ ] T017 The Lead adds four `## [Unreleased]` lines to `CHANGELOG.md`: `### Removed` for #90; `### Fixed` for #91, #92, #93; each ends with `(#NN)`. Acceptance: `grep -n '(#9[0-3])$' CHANGELOG.md` prints four lines.
- [ ] T018 The full dispatch SUCCESS GATE: the unittest command of T001 exits 0 and prints `OK`; `grep -c '3\.10' pyproject.toml` prints `0`; then `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <run snapshot> --allow <scope paths>` exits 0.
- [ ] T019 Move specs to DomI: run `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. Deferred: the dispatch puts this move out of scope for the Lead (the Chief of Staff does it after commit). It depends on every other task.

## Dependencies

- T001 first. Phases 2 and 3 are independent of each other and of 4 and 5.
- Phase 5 after Phase 4. T017 after all stories. T018 after T017. T019 last, by the Chief of Staff.

## Parallel

- Width 2 Workers at once: US1 with US2, then US3, then US4.
