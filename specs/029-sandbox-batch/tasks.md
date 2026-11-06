<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-28 skill=speckit-implement repo=agents_Inc session=b027a483-3613-4691-bfdd-d5c85383077c -->
# Tasks: agents-inc under the Claude Code sandbox (batch)

**Input**: specs/029-sandbox-batch/{spec.md, plan.md, research.md, checklists/requirements.md}
**Branch**: `029-sandbox-batch` (PR to `development`)
**Format**: `- [ ] T### [P?] [US#] description with exact file path`. [P] = can run in parallel (different file, no dependency).
**Tests first**: within each phase, test tasks come before the code tasks they cover.
**Out of scope**: #112 item 1 (NETWORK slot), #114, edits to `skills/codex-bridge/scripts/at_route.sh` and `codexagent.sh`, any change to `WB_SANDBOX_EXCLUDE_MISSING` or `_sandbox_exclusion`.

## Phase 1: Setup and research (plan.md "Phase 0", "Sequencing" A1)

- [x] T001 [US1] Confirm the FR-004 root cause recorded in specs/029-sandbox-batch/research.md section R1 (test env drops TMPDIR; wrappers hardcode `/tmp/<name>`) against a sandboxed run of `python3 -m unittest tests.test_model_map tests.test_install_at_route tests.test_free_wrappers tests.test_route_health_freshness`, and note the baseline in that file (FR-004: cause identified and recorded before any fix; baseline 10 failures + 1 error = 11).
- [x] T002 [US1] Record the full-suite baseline count on the same tree state as T035/T036, and note the pre-existing diff list, (`Ran N`, failures, errors) from `python3 -m unittest discover -s tests -p 'test_*.py'` in specs/029-sandbox-batch/research.md so SC-001 can be compared later (FR-003).

## Phase 2: User Story 1 - Test suite passes inside the sandbox (P1) (plan.md "Phase A")

Tests first.

- [x] T003 [US1] Add `TestWrapperTempFiles` static check to tests/test_free_wrappers.py: oask.sh, mask.sh and gask.sh contain no `/tmp/[a-z_]+(report_err|response)` literal (FR-001).
- [x] T004 [US1] Add a runtime check to `TestWrapperTempFiles` in tests/test_free_wrappers.py: run oask, mask and gask through the existing shim with `TMPDIR` set to its own subdir `tmp_path/"t"`, then assert that subdir is empty after each run (FR-001: unique file, removed on every exit path).
- [x] T005 [US1] Add an unwritable-TMPDIR check to `TestWrapperTempFiles` in tests/test_free_wrappers.py: with TMPDIR chmod 0o500, assert non-zero exit, no traceback, no new files (FR-001, spec edge case).
- [x] T006 [P] [US1] Add `"TMPDIR": str(self.root)` to the env dict at about line 209 of tests/test_install_at_route.py (FR-002).
- [x] T007 [P] [US1] Add `"TMPDIR": self.tmp.name` to the env dict at about line 69 of tests/test_model_map.py (FR-002).
- [x] T008 [P] [US1] Add `"TMPDIR": str(Path(self.tmp.name))` to `self.env` at about line 87 of tests/test_route_health_freshness.py (FR-002).
- [x] T009 [US1] Add `monkeypatch.setenv("TMPDIR", str(tmp_path))` in `wrapper_env` at about line 106 of tests/test_free_wrappers.py so tests using `env=os.environ.copy()` inherit it (FR-002).
- [x] T010 [P] [US1] In skills/codex-bridge/scripts/oask.sh, change `oask_report_trap` (lines about 77 and 85) to send the health-report stderr to `2>/dev/null` (no err file), and clean up with `rm -f "$OASK_REPORT_BODY_FILE"`; leave `exit $ec` unchanged (FR-001).
- [x] T011 [US1] In skills/codex-bridge/scripts/oask.sh lines about 245-258, create `OASK_REPORT_BODY_FILE=$(mktemp "${TMPDIR:-/tmp}/oask_response.XXXXXX")` above `OASK_ATTEMPTED=true` (oask.sh:244), so an unwritable TMPDIR reports nothing for a request never sent, use `curl -o "$OASK_REPORT_BODY_FILE"` and `RESPONSE=$(cat "$OASK_REPORT_BODY_FILE")`, and delete the old `cp` and `rm` lines (FR-001, FR-003; needed because the fixed `/tmp/oask_response.json` also fails in the sandbox).
- [x] T012 [P] [US1] In skills/codex-bridge/scripts/mask.sh lines about 58 and 68, send the health-report stderr to `2>/dev/null` (no err file) (FR-001).
- [x] T013 [P] [US1] In skills/codex-bridge/scripts/gask.sh lines about 45-46, send the health-report stderr to `2>/dev/null` (no err file) (FR-001).
- [x] T014 [US1] Run `python3 -m unittest tests.test_free_wrappers tests.test_route_health_freshness tests.test_install_at_route tests.test_model_map` inside the sandbox and confirm zero failures and zero errors; record the result in specs/029-sandbox-batch/research.md (FR-002, FR-003).

**Checkpoint**: sandboxed run of the four affected modules is green.

## Phase 3: User Story 2 - Doctor tells the truth about dispatch reachability (P2) (plan.md "Phase B", "Contract: CLI", "Contract: child script")

Tests first. All new tests go in tests/test_doctor_probe.py (NEW), using the fixture idiom of tests/test_doctor_claude.py. No live network: runner and opener are injected.

- [x] T015 [US2] Create tests/test_doctor_probe.py with a `classify`/`probe` test class using an injected opener: `HTTPError` gives reachable; `URLError(SSLCertVerificationError())` gives cert; `ConnectionRefusedError`, `TimeoutError`, `socket.gaierror` and `OSError("Tunnel connection failed: 403")` give blocked (FR-006, SC-003).
- [x] T016 [US2] Add to tests/test_doctor_probe.py a fake-runner test that records argv and env: `argv[1]` ends with `netprobe.py`, `env == worker_env(sys.executable)`, no `HTTPS_PROXY`, no `*TOKEN*` key (FR-005).
- [x] T017 [US2] Add to tests/test_doctor_probe.py a test that `check_install(..., probe_dispatch=False)` never calls the runner with a netprobe argv, and that `DoctorReport.probe` is `None` (FR-005, US2 scenario 4).
- [x] T018 [US2] Add to tests/test_doctor_probe.py a test that model-host `blocked` and `cert` give `ready False` with `WB_DISPATCH_API_BLOCKED` and `WB_DISPATCH_API_CERT` in codes, and that `main(["doctor","--probe-dispatch"])` with a patched `check_install` prints no `READY` and one `FIX:` line containing `agents-inc *` for blocked only (the cert fix line is the TLS text, not `agents-inc *`) (FR-007, FR-012, SC-002).
- [x] T019 [US2] Add to tests/test_doctor_probe.py a timeout test: the fake runner raises `TimeoutExpired(argv, 12, output=<one github reachable JSON line>)`, giving anthropic `blocked`, no raise, a timeout kwarg equal to `PROBE_CHILD_TIMEOUT`, and `PROBE_CHILD_TIMEOUT + GH_TIMEOUT < 20`; also a silent-child case (`TimeoutExpired` with `output=None`), a missing-row and `OSError` case that fails closed to `blocked` (FR-008, SC-005).
- [x] T020 [US2] Add to tests/test_doctor_probe.py the github tests: github blocked gives warning `WB_GITHUB_BLOCKED` with `ready True`; github reachable plus `gh` stderr `x509: OSStatus -26276` gives warning `WB_GITHUB_CERT` with `ready True`; `which("gh")` returning `None` gives no gh call and no code; child github `blocked` plus gh stderr `x509: OSStatus -26276` gives `WB_GITHUB_CERT` and no `WB_GITHUB_BLOCKED`; a gh auth error gives no code (FR-006, FR-012, US2 scenario 3).
- [x] T021 [US2] Add to tests/test_doctor_probe.py the FR-011 guard: settings without the exclusion plus model blocked gives `warnings.count("WB_SANDBOX_EXCLUDE_MISSING") == 1` and no other code containing `EXCLUDE` (FR-011).
- [x] T022 [US2] Create agents_inc/install/netprobe.py (NEW, stdlib-only, no package imports): `classify(exc)`, `probe(host, timeout=5.0, opener=None)` with default opener `build_opener(ProxyHandler({})).open`, and a `__main__` that prints one flushed JSON line per argv host (FR-005, FR-006, FR-008).
- [x] T023 [US2] In agents_inc/install/doctor.py, add constants `PROBE_HOSTS`, `PROBE_HOST_TIMEOUT=5`, `PROBE_CHILD_TIMEOUT=12`, `GH_TIMEOUT=6`, the `DoctorReport.probe` field (after `warnings`) plus its `as_dict` key, and `_probe_dispatch(runner, which)`: child run with `worker_env(sys.executable)`, catches `TimeoutExpired` and `OSError`, missing hosts default to `blocked`, and the `gh api /zen` stderr check whenever `which("gh")` returns a path, run in the caller env, regardless of the child's github row (FR-005, FR-006, FR-008).
- [x] T024 [US2] In agents_inc/install/doctor.py, add `_probe_codes(probe, warnings, env=os.environ)` mapping model blocked to `WB_DISPATCH_API_BLOCKED` and model cert to `WB_DISPATCH_API_CERT` (blocking), github blocked to `WB_GITHUB_BLOCKED` and github cert to `WB_GITHUB_CERT` (warnings), and set the per-host `fix` text (`os.environ.get("SANDBOX_RUNTIME") or "WB_SANDBOX_EXCLUDE_MISSING" in warnings` gets `SANDBOX_FIX`, otherwise the firewall/proxy text; model cert gets the TLS text); wire `check_install(..., probe_dispatch=False)` to run the probe after the live block and merge codes and warnings; leave `_sandbox_exclusion` and its call byte-identical (FR-007, FR-011, FR-012). Test both fix branches with an injected env: `{"SANDBOX_RUNTIME":"1"}` gives `SANDBOX_FIX`; `{}` with no exclusion warning gives the firewall/proxy cause text (N4, spec edge case Linux/no sandbox).
- [x] T025 [US2] In agents_inc/install/cli.py, add `--probe-dispatch` (`store_true`) to the doctor parser (about line 218), pass `probe_dispatch=args.probe_dispatch` to `check_install` (about line 263), print `probe: <host> <status> <elapsed>s` and `FIX: <fix>` lines after the codes line (about line 267), and keep the exit code `0 if report.ready else 1` (FR-005, FR-007).
- [x] T026 [US2] Run `python3 -m unittest tests.test_doctor_probe tests.test_doctor_claude` and confirm green, including the FR-011 guard (FR-005 to FR-008, FR-011, FR-012).

**Checkpoint**: probe codes verifiable with no live network.

## Phase 4: User Stories 3 and 4 - Docs (P3) (plan.md "Phase C")

Tests first. The `DocsTest` class goes in tests/test_doctor_probe.py.

- [x] T027 [US3] Add `DocsTest` to tests/test_doctor_probe.py asserting that skills/workerbee/SKILL.md and skills/workerbee/QUICKREF.md both contain the exact sentence `A Codex delegate (astra, sol, terra, luna) cannot read a path outside --cwd; paste the needed excerpts into the prompt.` (FR-009).
- [x] T028 [US4] Add to `DocsTest` in tests/test_doctor_probe.py asserting both docs contain `x509: OSStatus -26276`, `GitHub MCP`, `outside the sandbox` and `not confirmed` (FR-010, SC-004).
- [x] T029 [US3] In skills/workerbee/SKILL.md Step 11 element 7, after the line ending "does not commit." (about line 701), add the FR-009 sentence; do not add a 15th element (FR-009).
- [x] T030 [P] [US3] In skills/workerbee/QUICKREF.md, in the "MUST lines that are easy to drop" list (after about line 43), add the same FR-009 sentence word for word (FR-009).
- [x] T031 [US4] In skills/workerbee/SKILL.md Hard stops table, add the #122 row after about line 992 using the plan's row text: exact error line, GitHub MCP tools or `gh` outside the sandbox, cause outside this repo and not confirmed, and `WB_GITHUB_CERT` from `doctor --probe-dispatch` (FR-010).
- [x] T032 [P] [US4] In skills/workerbee/QUICKREF.md Hard stops list (after about line 64), add the matching #122 bullet (FR-010).
- [x] T033 [US4] Run `python3 -m unittest tests.test_doctor_probe` and confirm `DocsTest` is green (FR-009, FR-010).

## Phase 5: User Story 5 - Installer allow rule (P2) (plan.md "Phase D")

Tests first. All in tests/test_install_host_wiring.py. Out of scope: delegate `--allowedTools`, doctor, hook.py, dispatch.py.

- [x] T039 [US5] Add `test_claude_host_gets_allow_rule_once` to tests/test_install_host_wiring.py: seed `permissions.allow` with a foreign entry and a `deny` list, run `add_hooks` twice, assert exactly one `Bash(agents-inc *)` at the end, foreign entries and `deny` unchanged, codex host gets no `permissions` key (FR-013).
- [x] T040 [US5] Add `test_no_host_wiring_leaves_settings_without_allow_rule` to tests/test_install_host_wiring.py: run the cli install with `--no-host-wiring` over a tmp home with `.claude/settings.json`, assert no `Bash(agents-inc *)` in it and that the file bytes equal the pre-install bytes (FR-013, US5 scenario 4).
- [x] T041 [US5] Add `test_uninstall_removes_only_our_allow_rule` to tests/test_install_host_wiring.py: seed allow with `Bash(git status)` and `Bash(agents-inc doctor)`, install_host_wiring then remove_host_wiring, assert the allow list equals the seed exactly; second case with no seed asserts no `permissions` key remains; third asserts `unwire_hooks` reports `permissions.allow: Bash(agents-inc *)` (FR-014, SC-006).
- [x] T042 [US5] In agents_inc/install/host_wiring.py add `ALLOW_RULE = "Bash(agents-inc *)"` after `SANDBOX_EXCLUDE` (line 110) and `add_allow_rule(config)` after `add_sandbox_exclusion` (membership check, non-dict/non-list guards as at lines 115-117) (FR-013).
- [x] T043 [US5] In agents_inc/install/host_wiring.py add `strip_allow_rule(config)` after `strip_sandbox_exclusion`: equality filter, delete emptied `allow` then emptied `permissions` (FR-014).
- [x] T044 [US5] In agents_inc/install/host_wiring.py wire both: `strip_allow_rule(config)` beside `strip_sandbox_exclusion(config)` at line 95; `add_allow_rule(config)` beside `add_sandbox_exclusion(config)` at line 144 (claude only); add the `permissions.allow` line to `unwire_hooks` next to line 237 (FR-013, FR-014).
- [x] T045 [US5] Run `python3 -m unittest tests.test_install_host_wiring` and confirm green with the existing sandbox-exclusion tests (lines 102-118) unmodified (FR-013, FR-014, SC-006).

## Phase 6: Polish and verification (plan.md "Sequencing", D70 "last")

- [x] T034 Add a new `## D70` entry (amends D66, cross-references D65 and D66 without restating them) to docs/DECISIONS.md: the `--probe-dispatch` flag, the four codes, the FR-004 root cause, and the installer allow rule as an operator-session grant distinct from D51/D59 delegate grants, and the residual corporate-MITM CA false-positive note [inferred from plan Grill] (FR-004, FR-005, FR-012, FR-013).
- [x] T035 Run the full suite inside the sandbox with `python3 -m unittest discover -s tests -p 'test_*.py'` and record the `Ran N`, failures and errors counts in specs/029-sandbox-batch/research.md; expect 0 failures and 0 errors (FR-003, SC-001).
- [ ] T036 Run the same full-suite command unsandboxed (operator `!` run or CI) on the same commit and record its counts in specs/029-sandbox-batch/research.md; confirm `Ran N` equals T035, and name any by-design skips (FR-003, US1 scenario 2).
- [x] T037 Confirm via `git diff --stat` that skills/codex-bridge/scripts/at_route.sh and skills/codex-bridge/scripts/codexagent.sh are untouched, that agents_inc/install/dispatch.py is untouched, and that `_sandbox_exclusion` in agents_inc/install/doctor.py is unchanged (FR-011, FR-014, plan "NOT touched").
- [ ] T038 Move specs to DomI: bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply (first delete the empty specs/029-sandbox-batch/.claude/ folder so it does not travel)

## Dependencies and order

- T001 and T002 first. T001 must land before T006 to T009 (FR-004 before FR-002), per the plan's sequencing.
- Phase 2 (US1) test tasks T003 to T005 before T010 to T013. T014 after all of them.
- Phases 2, 3 and 4 are independent once T001 lands. T006 to T008, T010, T012, T013, T030 and T032 are [P].
- Phase 3: T015 to T021 (tests) before T022 to T025 (code). T022 before T023. T023 before T024. T024 before T025. T026 last.
- Phase 4: T027 and T028 before T029 to T032. T033 last.
- T039 to T041 before T042 to T044; T042, T043, T044 in order; T045 last of Phase 5.
- T034 after Phases 3, 4 and 5. T035 to T037 after T034. T038 is the final task.

## FR trace

| FR | Tasks |
|---|---|
| FR-001 | T003, T004, T005, T010, T011, T012, T013 |
| FR-002 | T006, T007, T008, T009, T014 |
| FR-003 | T002, T011, T014, T035, T036 |
| FR-004 | T001, T034 |
| FR-005 | T016, T017, T022, T023, T025, T026, T034 |
| FR-006 | T015, T020, T022, T023 |
| FR-007 | T018, T024, T025 |
| FR-008 | T019, T022, T023 |
| FR-009 | T027, T029, T030, T033 |
| FR-010 | T028, T031, T032, T033 |
| FR-011 | T021, T024, T037 |
| FR-012 | T018, T020, T024, T034 |
| FR-013 | T039, T040, T042, T044, T045 |
| FR-014 | T037, T041, T043, T044, T045 |
