---
description: "Task list for 022-dispatch-fail-loud"
---

# Tasks: Dispatch fails loud

**Input**: `.scratch/spec022/` (spec.md, plan.md, research.md, data-model.md, contracts/dispatch-outcomes.md)
**Prerequisites**: plan.md, spec.md
**Tests**: required. Every fix task has a failing-test task before it; run the test task's command and confirm it fails before starting the fix.

## Format: `[ID] [P?] [Story] Description`

- [P]: different file from every other open task in the same phase, no dependency on an incomplete task.
- All paths are repo-relative to `/Users/domattioli/Projects/agents_Inc`.
- Tests use temp dirs, a fake HOME and a mocked `launch`; no network and no model call.

## Phase 1: Setup

None. No new dependency, package or directory. New test files are created by their test tasks.

## Phase 2: Foundational

None. Each story builds on existing functions in `agents_inc/install/dispatch.py`. Cross-story file order is in Dependencies below.

---

## Phase 3: User Story 1 - The scope gate cannot be rewritten (P1) 🎯 MVP

**Goal**: verification uses a trusted snapshot copy outside cwd; tampering turns the run red.
**Independent Test**: `python3 -m unittest tests.test_dispatch_snapshot_trust -v`

- [X] T001 [P] [US1] Write failing tests in NEW `tests/test_dispatch_snapshot_trust.py` (class `SnapshotTrustTest`, `MirrorPromptTest`): temp git repo per `tests/test_dispatch_cli.py:27-33`; patch `dispatch._paths` so `state` is under the temp dir; mock `launch` to (a) edit a tracked file and rewrite `<run-dir>/snapshot.json` hash, (b) rewrite its porcelain, (c) delete it; expect outcome red, reason `snapshot-tampered`, exit 1. Also: resume reuses the private copy; a legacy run with no private dir records `snapshot_trust: "run-dir"`; a mock that rewrites `prompt.md` leaves the mirrored `prompt.md` equal to the launched prompt; with `_BROKER_SAFE_WRITES` set, nothing is written under the patched state dir and `snapshot_trust` is `"broker"`; `--dry-run` writes no trust dir. Patch `HOME` to the temp dir as `tests/test_dispatch_cli.py:43` does. Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust -v` fails before T002.
- [X] T002 [US1] In `agents_inc/install/dispatch.py` add `_trust_dir(run_id)` returning `_paths().state / "dispatch-runs" / run_id` (mkdir mode 0o700) and, once, immediately before `launch` (after `_record_ledger_node` at `dispatch.py:929`; not on `--dry-run` at `:912-915` or any refusal), copy the run-dir capture bytes to `<trust>/snapshot.json` and write `<trust>/trust.json` with `schema_version`, `snapshot_sha256` and `prompt_sha256` of the final `prompt`; set `spec["snapshot_trust"] = "private"`. When `_BROKER_SAFE_WRITES` is set, write `trust.json` into the run dir instead and set `"broker"`. Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust.SnapshotTrustTest -v`.
- [X] T003 [US1] In `agents_inc/install/dispatch.py` `_verify` (`:596-612`): hash `<run-dir>/snapshot.json`, compare with `trust.json`; on mismatch or missing file return snap `TAMPERED`; else run the verifier on `<trust>/snapshot.json`. In `_outcome` (`:683-700`) return `snapshot-tampered` before other snapshot reasons. Extend `tests/test_dispatch_cli.py:21-22` `STATUS_RE` snapshot alternatives with `TAMPERED`. Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust.SnapshotTrustTest tests.test_dispatch_cli -v`.
- [X] T004 [US1] In `agents_inc/install/dispatch.py` `resume` (`:949-990`): locate the trust dir by `spec["run_id"]` only; when absent set `spec["snapshot_trust"] = "run-dir"` and verify the run-dir copy (legacy path); else `"private"`. Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust -v` passes.
- [X] T005 [US1] In `agents_inc/install/dispatch.py` `_mirror` (`:709-719`): write `run.json` from `json.dumps(spec)`; write `prompt.md` from the in-memory prompt on the first turn (pass it from `run`); on resume copy the run-dir `prompt.md` only when its sha256 equals `prompt_sha256`, else skip it and set `spec["mirror_error"] = "prompt-tampered"`. Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust.MirrorPromptTest tests.test_dispatch_cli -v`.

**Checkpoint**: tamper test green; `tests/test_dispatch_cli.py` still green.

---

## Phase 4: User Story 2 - A failed run names its real cause and exit code (P1)

**Goal**: quota, block, crash, launch exception, verifier error and mirror error each get their reason, detail and exit code.
**Independent Test**: `python3 -m unittest tests.test_dispatch_failloud -v`

- [X] T006 [P] [US2] Write failing tests in NEW `tests/test_dispatch_failloud.py`: `QuotaBlockedTest` (rc 0 + `is_error` + "You've hit your session limit · resets 8:10pm" → red `quota-paused`, exit 75; stderr `API Error: Couldn't connect through your proxy (ERR_PROXY_TUNNEL)` → `blocked`, exit 69; both → `quota-paused`; a compliant report quoting the quota sentence with rc 0, `is_error` false → not `quota-paused`); `OutcomeOrderTest` (rc 1 + empty stdout → `rc-nonzero`, not `workers-spawned-missing`; `ERROR:rc=2` → `snapshot-error`); `StderrDetailTest` (status line has ` detail=Error:_not_logged_in`; an env value of 8+ chars in stderr is `[redacted]`); `LaunchFailTest` (`launch` raises `FileNotFoundError` and `RuntimeError("no-sandbox-backend")` → `run.json` outcome red, reason `launch-failed`, `reason_detail`, status line with run id, exit 1; same on `--resume`); `MirrorTest` (missing home → exit 0, `mirror_error: home-repo-missing`, no directory created; read-only dest → `mirror_error` starts `OSError`, exit unchanged); `ExitCodeTest` (map 0/1/2/3/69/75 from contract). Acceptance: `python3 -m unittest tests.test_dispatch_failloud -v` fails before T007.
- [X] T007 [US2] In `agents_inc/install/dispatch.py` `launch` (`:517-524`): add `"is_error": bool(data.get("is_error"))` to the Claude result (False when the envelope does not parse) and `"is_error": False` to the Codex result (`:547-549`); `run` and `resume` record it in `spec["is_error"]`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.QuotaBlockedTest -v` (is_error cases).
- [X] T008 [US2] In `agents_inc/install/dispatch.py`: add `BLOCKED_RE` next to `QUOTA_RE` (`:680`); in `_finish` (`:733-734`) compute `failed = rc != 0 or is_error`, `reported = parse_workers_spawned(stdout) is not None`, match stderr always and stdout when `failed or not reported`; reorder `_outcome` per `contracts/dispatch-outcomes.md` precedence, add `blocked` and `snapshot-error` (snap starts `ERROR:`); in `_finish` (`:742-744`) return 75 for `quota-paused` and 69 for `blocked`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.QuotaBlockedTest tests.test_dispatch_failloud.OutcomeOrderTest tests.test_dispatch_failloud.ExitCodeTest -v`.
- [X] T009 [US2] In `agents_inc/install/dispatch.py` add `_stderr_detail(stderr)` (first non-empty line, `screen_text(line, 200)`, whitespace → `_`); set `spec["reason_detail"]` in `_finish`; `_status` (`:703-706`) appends ` detail=<d>` before ` out=`. Update `tests/test_dispatch_cli.py:21-22` `STATUS_RE` to accept `( detail=\S+)?`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.StderrDetailTest tests.test_dispatch_cli -v`.
- [X] T010 [US2] In `agents_inc/install/dispatch.py` wrap `launch(...)` in `run` (`:934-939`) and `resume` (`:973-979`) in `try/except Exception`; set `rc=-1`, outcome red, reason `launch-failed`, screened `reason_detail`; write `run.json`; print the launch-failed status line per `contracts/dispatch-outcomes.md`; mirror; return 1. Extend `tests/test_dispatch_cli.py:21-22` `STATUS_RE` for `report=none snapshot=none`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.LaunchFailTest tests.test_dispatch_cli -v`.
- [X] T011 [US2] In `agents_inc/install/dispatch.py` `_mirror` (`:709-719`) and `_finish` (`:739-744`): refuse when `Path(home)` is not a directory (`home-repo-missing`); catch `OSError`; `_mirror` returns the error; `_finish` stores `spec["mirror_error"]`, rewrites `run.json`, prints one stderr line, keeps the outcome's exit code. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.MirrorTest tests.test_dispatch_cli -v`.

**Checkpoint**: `python3 -m unittest tests.test_dispatch_failloud tests.test_dispatch_snapshot_trust tests.test_dispatch_cli -v` green.

---

## Phase 5: User Story 3 - The broker never hangs and never runs unconfined (P2)

**Goal**: nested-sandbox probe, turn deadline, locked counters, correct `wait` docstring.
**Independent Test**: `python3 -m unittest tests.test_dispatch_broker_robust -v`

- [X] T012 [P] [US3] Write failing tests in NEW `tests/test_dispatch_broker_robust.py`: `SandboxProbeTest` (patch `subprocess.run` to fail → `sandbox_available()` False and `_validate_fields` refuses a Claude request `no-sandbox-backend`; second call does not re-probe; non-darwin → no probe); `TurnTimeoutTest` (`AGENTS_INC_TURN_TIMEOUT_S=1`, child argv `[sys.executable, "-c", "import time; time.sleep(30)"]` patched into `claude_argv` → returns within 6 s, rc 124, child run reason `timeout`, process group gone); `CounterLockTest` (patch `_SPEC_LOCK` with a recording lock; each `request_counts` update at `mcp_broker.py:215`, `:356` and `dispatch.py:1270`, `:1315` holds it); `WaitDocTest` (`dispatch.wait.__doc__` contains "124 on timeout" and "non-positive timeout"). Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust -v` fails before T013.
- [X] T013 [US3] In `agents_inc/install/dispatch.py` `sandbox_available` (`:262-263`): on darwin with an executable `SANDBOX_EXEC`, run `[SANDBOX_EXEC, "-p", "(version 1)(allow default)", "/usr/bin/true"]` with `timeout=10`, cache in a module global `_SANDBOX_OK`; False on nonzero, timeout or `OSError`. Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.SandboxProbeTest -v`.
- [X] T014 [US3] In `agents_inc/install/dispatch.py` `launch` Claude path (`:517`): replace `subprocess.run` with `Popen(..., start_new_session=True)` + `communicate(input=prompt, timeout=timeout_s)`; on `TimeoutExpired` `os.killpg(proc.pid, signal.SIGKILL)`, collect output, return rc 124 and stderr `turn timeout after <n> s`; `timeout_s` from `AGENTS_INC_TURN_TIMEOUT_S` else 3600. In `_outcome` map rc 124 with that marker to reason `timeout`. Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.TurnTimeoutTest tests.test_dispatch_cli -v`.
- [X] T015 [US3] In `agents_inc/install/runtime.py` `run_codex` (`:404`, `:480-489`): add keyword `timeout_s: float | None = None`; when set, run the child in a new session and kill its group on expiry, returning 124; `agents_inc/install/dispatch.py` `launch` passes `timeout_s` (`:538`). `agents-inc run` (`agents_inc/install/cli.py:221`) passes nothing. Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.TurnTimeoutTest tests.test_install_runtime -v`.
- [X] T016 [P] [US3] In `agents_inc/install/mcp_broker.py` wrap the increments at `:215` and `:356` in `with D._SPEC_LOCK:`. Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.CounterLockTest tests.test_mcp_broker -v`.
- [X] T017 [US3] In `agents_inc/install/dispatch.py` wrap `counts[...] += 1` at `:1270` and `:1315` in `with _SPEC_LOCK:`; reword the `wait` docstring (`:1703-1705`) to "0 found, 10 needs-lead, 124 on timeout, 2 on a bad request id or non-positive timeout". Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.CounterLockTest tests.test_dispatch_broker_robust.WaitDocTest tests.test_dispatch_broker -v`.

**Checkpoint**: `python3 -m unittest tests.test_dispatch_broker_robust tests.test_dispatch_broker tests.test_mcp_broker -v` green.

---

## Phase 6: User Story 4 - Doctor and the hook tell the truth (P2)

**Goal**: `WB_CLAUDE_NOT_FOUND`, `WB_SANDBOX_NESTED`, warnings in the hook, real env for the live probe.
**Independent Test**: `python3 -m unittest tests.test_doctor_claude tests.test_hook_session_start -v`

- [X] T018 [P] [US4] Write failing tests in NEW `tests/test_doctor_claude.py`, reusing the fixture shape of `tests/test_install_doctor.py:29` (`DoctorWarningsTest`): `which=lambda *a, **k: None` → code `WB_CLAUDE_NOT_FOUND`, `ready` False; `sandbox_probe=lambda: False` with `sys.platform` darwin → warning `WB_SANDBOX_NESTED`, `ready` unchanged; recording runner for `live_model="luna"` → env has `HOME`, `USER`, `PATH` and no key matching `KEY|TOKEN|SECRET`. Acceptance: `python3 -m unittest tests.test_doctor_claude -v` fails before T020.
- [X] T019 [P] [US4] Write failing tests in NEW `tests/test_hook_session_start.py`: patch `hook.check_install` to return `DoctorReport(True, (), None, ("INSTALL_STALE", "MODEL_DRIFT luna: pinned a, newest b"))` and `update_check.notice` to None; `session_start(paths, "claude")` additionalContext contains `doctor: READY`, `WARNING: INSTALL_STALE`, `WARNING: MODEL_DRIFT luna` and `agents-inc repair`. Acceptance: `python3 -m unittest tests.test_hook_session_start -v` fails before T021.
- [X] T020 [US4] In `agents_inc/install/doctor.py` `check_install` (`:62-96`): add keyword params `which=shutil.which` and `sandbox_probe=None` (None means lazy-import `sandbox_available` from `.dispatch`), same injection pattern as `runner` (`:62`); lazy-import `worker_env`; add `WB_CLAUDE_NOT_FOUND` when `shutil.which("claude", path=<worker PATH>:<os PATH>)` is None; add warning `WB_SANDBOX_NESTED` when `sys.platform == "darwin"` and `sandbox_available()` is False; at `:91` pass `env=worker_env(str(receipt.codex_path))`. Update every existing `check_install(` call in `tests/test_install_doctor.py` (`:24`, `:58`, `:70`, `:75`, `:96`, `:100`, `:106`, `:111`, `:119`), `tests/test_doctor_codex_optional.py:26` and `tests/test_install_at_route.py:171`, `:175`, `:185` to pass `which=lambda *a, **k: "/usr/bin/claude"` and `sandbox_probe=lambda: True`, so results do not depend on the host. Acceptance: `python3 -m unittest tests.test_doctor_claude tests.test_install_doctor tests.test_doctor_codex_optional tests.test_install_at_route -v`.
- [X] T021 [P] [US4] In `agents_inc/install/hook.py` `session_start` (`:33-39`): append `WARNING: <w>.` per `report.warnings`; when `INSTALL_STALE` is present append "Run `agents-inc repair --source <agents_Inc checkout>`." Acceptance: `python3 -m unittest tests.test_hook_session_start tests.test_hook_quickref -v`.

**Checkpoint**: doctor and hook tests green; existing doctor tests green.

---

## Phase 7: User Story 5 - Screens read paths, not prose (P3)

**Goal**: no prose prefixes, globs refused, test-file names pass the gate screen.
**Independent Test**: `python3 -m unittest tests.test_dispatch_slot_screens -v`

- [X] T022 [P] [US5] Write failing tests in NEW `tests/test_dispatch_slot_screens.py`: `AllowPathsTest` ("Read: any repo file. Write: .scratch/fable-audit/ only." → `[".scratch/fable-audit/"]`; existing case of `tests/test_dispatch_cli.py:458-461` unchanged); `ScopeGlobTest` (FILES_IN_SCOPE `src/*.py` → `run` returns 3, outcome `refused-scope`, no launch); `GateScreenTest` (`python3 -m pytest tests/test_token_refresh.py` and BASH_ALLOW `python3 tools/check_credentials_schema.py` accepted; `cat ~/.ssh/id_rsa`, `cat .env`, `cat server.pem` refused; `_reject_credential_seeking({"X": "token"})` still True). Acceptance: `python3 -m unittest tests.test_dispatch_slot_screens -v` fails before T023.
- [X] T023 [US5] In `agents_inc/install/dispatch.py` `allow_paths` (`:141-148`): skip tokens ending in `.`; add `scope_globs(text)` returning tokens with `*`, `?` or `[`; in `run` before `_grants_from_slots` (`:850`) refuse with outcome `refused-scope`, `lint.txt` reason, exit 3. Acceptance: `python3 -m unittest tests.test_dispatch_slot_screens.AllowPathsTest tests.test_dispatch_slot_screens.ScopeGlobTest tests.test_dispatch_cli -v`.
- [X] T024 [US5] In `agents_inc/install/dispatch.py` add `GATE_CREDENTIAL_RE` (home-path alternative of `CREDENTIAL_RE` at `:1015` plus `.env`, `id_rsa`, `id_ed25519`, `.pem`, `.key` as path components); use it at `:657`, `:767` and `:775`; leave `_reject_credential_seeking` (`:1168-1170`) on `CREDENTIAL_RE`. Acceptance: `python3 -m unittest tests.test_dispatch_slot_screens.GateScreenTest tests.test_dispatch_grants -v`.

**Checkpoint**: slot-screen tests and grant tests green.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T025 Run the full suite. Acceptance: `python3 -m unittest discover -s tests -p 'test_*.py'` exits 0.
- [X] T026 [P] Add an Unreleased entry to `CHANGELOG.md` listing new reasons, exit codes 69 and 75, `detail=`, `WB_CLAUDE_NOT_FOUND`, `WB_SANDBOX_NESTED`. Acceptance: `git diff --stat -- CHANGELOG.md` shows one file changed.
- [ ] T027 CoS only (canon, cross-vendor review per D46.10(b)): draft a `docs/DECISIONS.md` entry amending D58's exit list and outcome reasons, and record the Open-for-CoS rulings. Not a Worker task. Acceptance: `git diff -- docs/DECISIONS.md` shows the new entry after review.
- [ ] T028 CoS only: move `.scratch/spec022/` to DomI `specs/consumers/agents_Inc/022-dispatch-fail-loud/` (AGENTS.md Governance). Acceptance: `test -s /Users/domattioli/Projects/DomI/specs/consumers/agents_Inc/022-dispatch-fail-loud/spec.md`.

---

## Dependencies & Execution Order

- Test tasks T001, T006, T012, T018, T019, T022 touch only NEW files and can all run first, in parallel.
- `agents_inc/install/dispatch.py` is edited by T002-T005, T007-T011, T013-T015 (launch), T017, T023, T024. Run these in ID order, one at a time: T003 and T008 both edit `_outcome`; T005 and T011 both edit `_mirror`; T007 and T014 both edit `launch`.
- `tests/test_dispatch_cli.py` `STATUS_RE` is edited by T003, T009 and T010, in that order.
- T015 (`runtime.py`) after T014. T016 (`mcp_broker.py`) anytime after T012. T020 (`doctor.py`) after T013 (it imports the probe). T021 (`hook.py`) anytime after T019.
- T025 after all story tasks; T026 anytime; T027 and T028 after T025, by the CoS.

### Story order

US1 → US2 → US3 → US4 → US5 by priority. US4's hook task (T021) and US3's broker-file task (T016) are independent of the `dispatch.py` chain.

## Parallel Example

```bash
Task: "T001 failing tests in tests/test_dispatch_snapshot_trust.py"
Task: "T006 failing tests in tests/test_dispatch_failloud.py"
Task: "T012 failing tests in tests/test_dispatch_broker_robust.py"
Task: "T018 failing tests in tests/test_doctor_claude.py"
Task: "T019 failing tests in tests/test_hook_session_start.py"
Task: "T022 failing tests in tests/test_dispatch_slot_screens.py"
```

## Implementation Strategy

MVP: US1 (T001-T005), then validate with `python3 -m unittest tests.test_dispatch_snapshot_trust -v`. Then US2, which closes #88 item 5. US3-US5 follow. Rung guidance (AGENTS.md "Free Grunt coding"): US1, US2 and US3 T013-T015 at Workhorse or above; T016, T017, T021, T022-T024 fit Grunt.
