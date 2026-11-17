<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-analyze repo=agents_Inc session=b8dceec1 -->
# Tasks: spec 026, delegated runs work inside the sandbox, plus broker hygiene

**Input**: `specs/026-sandbox-safe-runs/spec.md`, `specs/026-sandbox-safe-runs/plan.md`
**Prerequisites**: plan.md, spec.md. No research.md, data-model.md or contracts/ (folded into plan.md).

One implement delegate runs every code task (US1 to US6) in one run. Tasks marked **[CoS]** are done by the supervising Chief of Staff, never by the delegate: all GitHub work, home-directory checks, and the final move. Write each test first and see it fail, then make it pass. Re-run `grep -n` before each edit; line numbers are from 2026-10-24 (`5f01dfe`). No commit, no push. A task is done only when its acceptance command has run and exited as stated. Plan departures D1 to D5 (plan.md "Departures from the spec") apply; D1 and D2 need a CoS answer before T019 and T011.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: order-free (different files, no dependency on an open task). In a one-delegate run, [P] only means order-free.
- **[Story]**: US0 to US6.
- **[CoS]**: supervisor task; the delegate skips it.

## Phase 1: Setup

- [x] T001 Baseline before any edit: run `python3 -m unittest discover -s tests -p 'test_*.py'` and `python3 -m unittest discover -s skills/workerbee/tests -p 'test_*.py'`, once outside the Claude Code sandbox and once inside it; record pass, fail and skip counts per run, and name the failing tests inside the sandbox (expected: `tests.test_ollama_adapter` and `tests.test_bridge_thread_id`, #110). (SC-001, SC-002 baseline) — CoS 2026-10-24: baseline at 5f01dfe outside sandbox: tests 1549 OK skipped=17; skills 90 OK. Inside-sandbox baseline not re-run; final inside run fails only the wrapper-script tests (test_free_wrappers, test_route_health_freshness, test_install_at_route, test_model_map: fixed /tmp and mktemp paths), out of 026 scope, follow-up.

## Phase 2: User Story 0, triage of partly fixed issues (supervisor only)

**Goal**: every item of #89, #87 (1 to 5) and #88 (1, 4) has a recorded verdict. **Independent test**: `test -s specs/026-sandbox-safe-runs/triage.md` exits 0 and every FR-001 item has a row.

- [x] T002 [CoS] [US0] Check each numbered item of #89, #87 items 1 to 5 and #88 items 1 and 4 against `5f01dfe`; write `specs/026-sandbox-safe-runs/triage.md` with columns issue, item, verdict (`fixed`/`open`/`moved`), evidence (commit or D-number plus one file:line), note. Add the follow-up row FR-004a (text screen refused a read-forbidden design question naming `~/.config/git`), plus plan risks R3-1 (MCP broker has no lock) and R4-2 (ask_lead answer text not screened) as follow-up candidates. Acceptance: `test -s specs/026-sandbox-safe-runs/triage.md` exits 0. (FR-001, FR-002, FR-004, FR-004a)
- [x] T003 [CoS] [US0] Per issue, post one comment through `comment-issue` with that issue's rows; close with reason `completed` only when every row is `fixed` or `moved`; otherwise leave it open and list only the `open` items as remaining scope. Acceptance: each closed issue shows the comment and state `closed` (`gh issue view <n> --json state,comments`). (FR-003, SC-004) — CoS: #89 closed completed; #87 and #88 commented, #88 open until the split issue is filed.
- [x] T004 [CoS] [US2] Run the #103 reproduction outside any sandbox and check `~/.gitconfig` for includes under `~/.config`. Done 2026-10-24: cause is metadata reads on the broker run dir's folders, not `~/.config`; no include; results in plan.md "US2 reproduction". D1 and D2 accepted. (FR-009, FR-012)

## Phase 3: User Story 1 (#110), suite runs inside the Claude Code sandbox

**Goal**: both modules pass or skip cleanly inside the sandbox. **Independent test**: inside the sandbox `python3 -m unittest tests.test_ollama_adapter tests.test_bridge_thread_id` exits 0 with bridge skips carrying the FR-006 reason.

- [x] T005 [P] [US1] In `tests/test_ollama_adapter.py`, replace the fixed paths at `:264` (`/tmp/ws`), `:405` and `:411` (`/tmp/test.lock`), and `:711` (`/tmp/test_ws`, which really writes `.workerbees/doctor.json`) with paths under a `tempfile.TemporaryDirectory()` the test creates and removes. Acceptance: `grep -n '"/tmp' tests/test_ollama_adapter.py` prints nothing, and `python3 -m unittest tests.test_ollama_adapter` exits 0 inside and outside the sandbox. (FR-005)
- [x] T006 [US1] In `tests/test_bridge_thread_id.py`, add class `BindProbeTest` first: with `socket.socket.bind` patched to raise `PermissionError`, `_bind_probe()` returns exactly `local port binding refused (sandbox); run outside the sandbox or set sandbox.network.allowLocalBinding`; with it patched to raise `OSError(98, "in use")`, the error propagates; reset the probe cache in `addCleanup`. See it fail (no `_bind_probe` yet). (FR-006, FR-007)
- [x] T007 [US1] In `tests/test_bridge_thread_id.py`, add the module-level cached `_bind_probe()` helper and `setUpClass` on `BridgeThreadIdTest` (`:52`) and `AskShBodyShapeTest` (`:184`) that raises `unittest.SkipTest(<reason>)` when the probe returns a reason. No production code changes. Acceptance: outside the sandbox `python3 -m unittest -v tests.test_bridge_thread_id` exits 0 with no `skipped` line; inside it exits 0 and every bridge skip line carries the FR-006 reason. (FR-006, FR-007, FR-008)

## Phase 4: User Story 6 (#88 item 3), `--run-dir` for read-only runs

**Goal**: `--run-dir` no longer needs `--write`. **Independent test**: `python3 -m unittest tests.test_codex_tool_access` exits 0.

- [x] T008 [P] [US6] In `tests/test_codex_tool_access.py`, rename `test_run_dir_needs_write` (`:185`) to `test_run_dir_needs_tools` asserting `--run-dir needs tools` for `no_tools=True` with `write_dir`; add `permission_profile(cwd, False, write_dir=d) == permission_profile(cwd, True, write_dir=d)`; add a `run_codex` case with `write_dir` and `write=False`, tools on, that builds argv without raising (patch the launch as `test_run_dir_only_write`, `:161`, does). See them fail. (FR-028)
- [x] T009 [US6] In `agents_inc/install/runtime.py`, delete the raise at `:129-130` in `permission_profile`; in `run_codex` replace `:483-484` with `if write_dir is not None and not tools: raise ValueError("--run-dir needs tools")` (after `tools = tools_for(...)`, `:480`). Acceptance: the independent test exits 0; `grep -c 'run-dir needs --write' agents_inc/install/runtime.py` prints 0 (grep exits 1 on zero matches; that is expected). (FR-026, FR-027)

## Phase 5: User Story 5 (#88 item 2), unreadable caveman file

**Goal**: the contract and the report checker accept the unreadable case. **Independent test**: `python3 -m unittest tests.test_dispatch_header skills.workerbee.tests.test_template_revision` exits 0.

- [x] T010 [P] [US5] In `tests/test_dispatch_header.py`, assert the rendered prompt contains `caveman unreadable -> checked by hand` and `not a block under the stop-on-block clause`; in `skills/workerbee/tests/test_template_revision.py` (near `:140-144`), add a report-profile case whose first line is `caveman: unreadable -> by hand` and assert no `caveman` miss. See them fail. (FR-025)
- [x] T011 [US5] In `skills/workerbee/header.md:11`, add the unreadable sentence from plan US5 after the "If the skill is absent" sentence, keeping existing sentences verbatim; in `:16`, change the declaration to `caveman: <ultra|not installed -> by hand|unreadable -> by hand>`. Make the same declaration change in `skills/workerbee/SKILL.md:774-775` (the line wraps; D2). Acceptance: `grep -c 'caveman unreadable -> checked by hand' skills/workerbee/header.md` prints 1, `grep -c 'unreadable -> by hand>' skills/workerbee/header.md` prints 1, and `grep -A1 -n 'caveman: <ultra' skills/workerbee/SKILL.md` shows `unreadable -> by hand`. (FR-022, FR-023)
- [x] T012 [US5] In `skills/workerbee/scripts/check_dispatch_prompt.py:72-73`, add `"caveman: unreadable"` and `"caveman unreadable"` to `REPORT_KEYWORDS["caveman"]`. Acceptance: the independent test exits 0, and `python3 -m unittest skills.workerbee.tests.test_element1_conditional` exits 0 (it pins the two older declaration values; out of Scope, so report if it would need an edit). (FR-023)
- [x] T013 [P] [US5] In `skills/workerbee/QUICKREF.md:46`, rewrite the "Caveman absent" line to name the unreadable case in the same sentence (plan US5 text). Acceptance: `grep -n 'unreadable' skills/workerbee/QUICKREF.md` prints the line 46 match. (FR-024)

## Phase 6: User Story 4 (#109 item 2), control and bidi characters

**Goal**: render and dispatch refuse C0 (except tab, LF, CR), DEL and bidi controls. **Independent test**: `python3 -m unittest tests.test_dispatch_slot_screens tests.test_dispatch_cli` exits 0.

- [x] T014 [US4] In `tests/test_dispatch_slot_screens.py`, add class `ControlCharTest`: for each of `\x00`, `‮`, `⁦`, `\x7f` in TASK, `dispatch.main` exits 3 with stderr `dispatch: refused-control-char (slot TASK U+0000)` (code point per case) and the `--run-dir` parent stays empty; `dispatch._validate_fields` returns reason `refused-control-char`; `dispatch.plan_resume` with the char in the message returns `refused-control-char`; `--resume <dir> --message` with U+202E exits 3 and leaves `run.json` byte-identical. Accept: TASK with `\t`, `\n`, `\r\n`; TASK with `é`, `日本`, `🙂`. Assert `dispatch.CONTROL_CHAR_RE.pattern` equals `render_dispatch.CONTROL_CHAR_RE.pattern`. In `tests/test_dispatch_cli.py`, add one render case: slots with U+202E at offset 5 of TASK, `render_dispatch.py` exits 2, stderr `render: slot TASK has control character U+202E at offset 5`, stdout empty. See them fail. (FR-018, FR-019, FR-020, FR-021)
- [x] T015 [US4] In `skills/workerbee/scripts/render_dispatch.py`, add `CONTROL_CHAR_RE` and `control_char_hit(slots)` per plan US4 (strings nested in list and dict values scanned, top-level key reported, code-point offset); call it right after the slots load (`:333-337`), print the FR-019 line, return 2 before any output. Acceptance: the render case in `tests/test_dispatch_cli.py` passes (`python3 -m unittest tests.test_dispatch_cli` exits 0). (FR-018, FR-019)
- [x] T016 [US4] In `agents_inc/install/dispatch.py`, add the same `CONTROL_CHAR_RE` and `control_char_hit`; refuse in `run()` after the credential screen (`:1261-1264`) and in `resume()` after the message screen (`:1457-1463`) with `dispatch: refused-control-char (slot <KEY> U+<XXXX>)` and `EXIT_REFUSED`; in `_validate_fields` return `refused-control-char` before the credential screen (`:1750`) and add `reason_detail` `slot <KEY> U+<XXXX>` in `_handle_one` beside `:1911-1914`; in `plan_resume` refuse after the oversize check (`:2147-2148`). Acceptance: the independent test exits 0; `grep -c 'refused-control-char' agents_inc/install/dispatch.py` prints at least 4. (FR-018, FR-020)

## Phase 7: User Story 3 (#109 item 1), one broker per run directory

**Goal**: a second broker on one run dir refuses. **Independent test**: `python3 -m unittest tests.test_dispatch_broker tests.test_codex_tool_access` exits 0.

- [x] T017 [US3] In `tests/test_dispatch_broker.py`, add class `BrokerLockTest`: lock held on a second fd with pid `4242` gives `serve()` exit 2, stderr `dispatch --serve: another broker holds <run>/broker.lock (pid 4242)`, `run.json` bytes unchanged, inbox request not set aside; garbage pid text gives `(pid unknown)`; two real `serve()` calls (first in a thread held polling by a fake clock and an `Event`) give exit 2 for the second, and after the first exits on `lead.done` a third `serve()` exits 0; a symlinked `broker.lock` gives exit 2 with `must be a regular file` and the target untouched. Add the FR-016 assertions: the Claude profile with `deny_paths=(run_dir,)` has no `require-not` hole naming `broker.lock`, and in `tests/test_codex_tool_access.py` `permission_profile(cwd, True, write_dir=d)` maps no `broker.lock` key to `write`. See the lock tests fail. (FR-013, FR-014, FR-015, FR-016, FR-017)
- [x] T018 [US3] In `agents_inc/install/dispatch.py`, add `BROKER_LOCK` and `_take_broker_lock(root)` per plan US3 (`O_NOFOLLOW` open, `flock(LOCK_EX | LOCK_NB)`, pid written after the lock, never unlinked); call it in `serve()` after the inbox check (`:2243-2246`) and before `_load_run_manifest` (`:2248`), return `BROKER_USAGE` on refusal, and close the fd in a `finally` around the loop (`:2260-2303`). Acceptance: the independent test exits 0; `grep -n 'broker.lock' agents_inc/install/dispatch.py` prints at least one line. (FR-013, FR-014, FR-015)

## Phase 8: User Story 2 (#103), broker Worker runs git (last code phase)

**Goal**: `git init` and `git commit` work in a broker Claude Worker's TMPDIR with `~/.config` still denied. **Independent test**: on macOS outside a sandbox, `python3 -m unittest tests.test_dispatch_broker` exits 0 and the FR-012 test runs (not skipped).

- [x] T019 [US2] Test first, in `tests/test_dispatch_broker.py`: class `WorkerGitTest` per plan US2, skipped unless `dispatch.sandbox_available()`, with the `sandbox_apply` skip guard (`:533-534`). Broker run dir `<b>` in `deny_paths`, TMPDIR `<b>/workers/w1/tmp`: `git init`, `git add -A`, `git commit --allow-empty -m t` in `<tmp>/repo` exit 0; `cat <b>/secret.txt`, `ls <b>`, `ls <b>/workers` exit non-zero; `cat <child>/snapshot.json` exits 0; `touch <child>/snapshot.json` exits non-zero, also with the run dir under the profile cwd. Add the profile-text unit test from plan US2. See them fail on the unpatched tree (expected: `git init` rc 128 `Invalid path`). (FR-009, FR-010, FR-011, FR-012)
- [x] T020 [US2] In `agents_inc/install/dispatch.py` `claude_sandbox_profile` (`:433-463`), add `_ancestors_between(root, leaf)` and emit `(allow file-read-metadata (literal "<a>"))` after the `broker_deny` rules for every folder from each `deny_paths` root down to (excluding) each hole under it (`tmpdir`, `write_ok`, `read_ok`). No env change; `WORKER_ENV_KEYS` and `CLAUDE_WORKER_DENY` stay. Read `runtime.permission_profile` and state in the report whether the Codex `extra_deny` blocks the same metadata; do not change the Codex profile. Acceptance: `grep -n 'file-read-metadata' agents_inc/install/dispatch.py` shows the new rule; `grep -c XDG_CONFIG_HOME agents_inc/install/dispatch.py` prints 0 (grep exits 1 on zero matches; expected); the T019 assertions pass. (FR-009, FR-010)
- [x] T021 [US2] In `agents_inc/install/dispatch.py`, pass `Path(run_dir) / "pre_dispatch_snapshot.py"` and `Path(run_dir) / "snapshot.json"` in the `read_ok` tuple at `:682-684` for every broker Claude Worker; in `claude_sandbox_profile` (`:433-463`) add `(deny file-write* (literal "<p>"))` for every `read_ok` path (departure D4). Acceptance: the independent test exits 0, and `python3 -m unittest tests.test_dispatch_broker tests.test_worker_mcp` exits 0 (the ask channel still works). (FR-011, FR-012)

## Phase 9: Polish and cross-cutting

- [x] T022 [P] In `docs/DECISIONS.md`, append D68 after D67 (`:688`) recording R1, R2, the #103 cause and the FR-009 rule (a deny root grants metadata-only reads on the folders above each hole it opens) and the broker lock rule. Acceptance: `grep -n '^## D68' docs/DECISIONS.md` prints one line. (SC-006)
- [x] T023 In `CHANGELOG.md` under `## [Unreleased]` (`:7`) / `### Fixed` (`:9`), add six lines (Scope rule, spec Scope) ending `(#110)`, `(#103)`, `(#109)`, `(#109)`, `(#88)`, `(#88)`. Acceptance: `grep -cE '\((#110|#103|#109|#88)\)$' CHANGELOG.md` prints at least 6.
- [x] T024 Final gate: SC-001 both discover commands outside the sandbox pass with no new skips against T001; SC-002 inside the sandbox `python3 -m unittest tests.test_ollama_adapter` passes and `python3 -m unittest tests.test_bridge_thread_id` shows FR-006 skips and zero errors; SC-003 the T019 test passes on macOS outside a sandbox; SC-005 the dispatch scope verify exits 0 with edits only in the spec Scope files plus `specs/026-sandbox-safe-runs/`. — CoS 2026-10-24: outside sandbox tests 1574 OK skipped=17 (no new skips), skills 91 OK; inside sandbox test_ollama_adapter OK, test_bridge_thread_id 3 run 2 skipped 0 errors; WorkerGitTest 4/4 OK on macOS outside sandbox; scope verify UNCHANGED outside allowed paths.
- [ ] T025 [CoS] Move specs to DomI: run `bash <DomI>/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. Depends on every other task; nothing runs after it. Done by the Chief of Staff after commit, not by the implement delegate.

## Dependencies and execution order

- T001 first. T002 to T004 are CoS work and run beside the code phases; T004 is done (cause confirmed; D1, D2 accepted).
- Phases 3 (US1) and 4 (US6) touch separate files and are order-free. Phase 5 (US5) is docs plus the checker.
- Phases 6, 7, 8 all edit `agents_inc/install/dispatch.py` and run in that order; US2 last because it needs `sandbox-exec` outside a sandbox and touches `launch()`.
- Inside each story: the test task first and red, then the code task.
- T022 is order-free. T023 after all stories. T024 after T023. T025 last.

## Parallel examples

- T005, T008, T010, T013 together: four different files, no shared state.
- T006 and T007 stay in one file and run in sequence.

## FR coverage

| FR | Tasks |
|---|---|
| FR-001, FR-002 | T002 |
| FR-003 | T003 |
| FR-004, FR-004a | T002 |
| FR-005 | T005 |
| FR-006, FR-007 | T006, T007 |
| FR-008 | T007 |
| FR-009 | T004, T019, T020 |
| FR-010 | T019, T020 |
| FR-011 | T019, T021 |
| FR-012 | T004, T019, T021 |
| FR-013, FR-014, FR-015 | T017, T018 |
| FR-016, FR-017 | T017 |
| FR-018 | T014, T015, T016 |
| FR-019 | T014, T015 |
| FR-020 | T014, T016 |
| FR-021 | T014 |
| FR-022 | T011 |
| FR-023 | T011, T012 |
| FR-024 | T013 |
| FR-025 | T010 |
| FR-026, FR-027 | T009 |
| FR-028 | T008 |
| SC-001 to SC-003, SC-005 | T001, T024 |
| SC-004 | T003 |
| SC-006 | T022 |
