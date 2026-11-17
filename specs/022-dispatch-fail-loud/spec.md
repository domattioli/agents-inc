# Feature Specification: Dispatch fails loud (022-dispatch-fail-loud)

**Feature Branch**: none (hand-run pipeline, no branch; feature id `022-dispatch-fail-loud`)
**Created**: 2026-10-18
**Status**: Draft (clarified 2026-10-18; open items under "Open for CoS")
**Input**: Fix issue #89 (audit `.scratch/fable-audit/findings.md`, findings 1, 2 and 4-15) and issue #88 item 5 as extended by audit finding 3 (`.scratch/spec022/issue88.txt:17`).

## Context

`agents-inc dispatch` runs one delegate, checks its report, verifies the working-tree snapshot, runs structured gates and prints one status line (D47, `docs/DECISIONS.md:511`). The 2026-10-18 audit found fifteen places where a failed, tampered or hung run reads as green, as a delegate fault, or as nothing at all. This feature makes every such failure visible, correctly named and distinguishable by exit code. It changes no routing, no grant set and no prompt contract.

Out of scope: #88 items 1-4 and 6-8 (the credential screen over prose, inherited sandbox network, rendered Write grant, doctor network probe); the live-view mod (spec 021); the DomI repository.

## Clarifications

### Session 2026-10-18

Answers come from code and canon; each carries its source.

- Q: Does dispatch really exit 0 on the quota case of #88 item 5? → A: No for the direct CLI. Any red outcome returns `EXIT_RED` = 1 (`agents_inc/install/dispatch.py:39`, `:744`). The `rc=0` the issue quotes is the child's exit code, which the status line prints as `rc=` (`dispatch.py:705`). The real defect is that the quota text is ignored when the child exits 0 (`dispatch.py:686`), so the reason reads `workers-spawned-missing` or `report-noncompliant`, and the exit code (1) is the same as every other red. The fix keeps red and adds a distinct exit code and reason. See Open for CoS item 1.
- Q: Which exit code for a quota pause? → A: 75, the code `run_codex` already returns on a Codex usage limit (`agents_inc/install/runtime.py:551`), which live tests already treat as quota (`tests/test_mcp_broker_live.py:78`). A connectivity block gets 69. Both stay outcome `red` so the status-line grammar (`tests/test_dispatch_cli.py:21-22`) and broker statuses (`dispatch.py:1020`) are unchanged.
- Q: Should a launch failure get a new outcome value `launch-failed`? → A: No. Outcome stays `red` with reason `launch-failed`; D58 fixes the outcome set at green, red, unverified (`docs/DECISIONS.md:622`), and `_req_status` and the status-line test regex depend on it.
- Q: Where may the trusted snapshot copy live? → A: Outside cwd, keyed by run id and never located through a delegate-writable file. A Claude delegate under acceptEdits and a Codex delegate under `--write` can write only inside cwd (D49, `docs/DECISIONS.md:545-547`; `default_parent` docstring `dispatch.py:50-51`). D57 already refuses a write grant when the broker run directory sits inside cwd (`docs/DECISIONS.md:618`), the same threat shape. The location is a plan decision (research R1).
- Q: Does a failing nested-sandbox probe make doctor not READY? → A: Recommended no: report a warning. Only broker-launched Claude Workers use `sandbox-exec` (`dispatch.py:506-516`); a direct Claude dispatch and every Codex dispatch still work. D52 keeps warnings beside READY (`docs/DECISIONS.md:582`). Open for CoS item 2.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The scope gate cannot be rewritten by the delegate it checks (Priority: P1)

The CoS dispatches a delegate with write access. The snapshot that decides `snapshot=clean` today sits in a run directory under cwd that the delegate can edit (`dispatch.py:49-58`, `:843`, `:605`). After this change, an edit to that file turns the run red instead of green, and the mirrored run spec reflects what dispatch actually sent.

**Why this priority**: Audit finding 1 (HIGH). A tampered snapshot makes the FAILURE GATE silently pass, which defeats the core verification promise in `AGENTS.md` ("A worker never accepts its own output").

**Independent Test**: In a temp git repo, capture, let a fake launch edit a tracked file and rewrite `<run-dir>/snapshot.json` to match, then finish the run. Expect red, reason `snapshot-tampered`.

**Acceptance Scenarios**:

1. **Given** a run whose delegate edits `snapshot.json` in the run directory, **When** dispatch verifies, **Then** outcome is `red`, reason `snapshot-tampered`, exit 1, and verification used the private copy.
2. **Given** a run whose delegate edits `prompt.md` in the run directory, **When** dispatch mirrors, **Then** the mirrored `prompt.md` equals the prompt dispatch launched, byte for byte.
3. **Given** a resumed run, **When** dispatch verifies the new turn, **Then** it uses the same private copy and the same tamper check.

---

### User Story 2 - A failed run names its real cause and exit code (Priority: P1)

The operator, or a driver script, runs dispatch in a loop. A quota pause, a proxy failure, a crashed child, a launch exception, a verifier error or a mirror error each produces a status line that names the cause, a `run.json`, and an exit code a script can branch on. No green run turns into exit 1 because a copy to the home repo failed.

**Why this priority**: #88 item 5 plus findings 3, 4, 5, 6 and 12. A driver dispatched about 30 empty rounds before anyone noticed (`.scratch/spec022/issue88.txt:17`).

**Independent Test**: Unit tests over `_finish` and `run` with a mocked `launch`, each feeding one failure shape; read the status line, `run.json` and exit code.

**Acceptance Scenarios**:

1. **Given** a child that exits 0 with `is_error: true` and result text "You've hit your session limit · resets 8:10pm", **When** dispatch finishes, **Then** outcome `red`, reason `quota-paused`, exit 75.
2. **Given** a child whose stderr holds `API Error: Couldn't connect through your proxy (ERR_PROXY_TUNNEL)`, **When** dispatch finishes, **Then** outcome `red`, reason `blocked`, exit 69.
3. **Given** a child that exits 1 with empty stdout and stderr "Error: not logged in", **When** dispatch finishes, **Then** reason is `rc-nonzero` (not `workers-spawned-missing`) and the status line carries a `detail=` field with the screened first stderr line.
4. **Given** `launch()` raises `FileNotFoundError` or `RuntimeError("no-sandbox-backend")`, **When** dispatch handles it, **Then** `run.json` exists with outcome `red`, reason `launch-failed`, `reason_detail` naming the exception, a status line prints with the run id, and exit is 1.
5. **Given** the verifier exits 2 with no `CHANGED` lines, **When** dispatch finishes, **Then** reason is `snapshot-error`, not `snapshot-not-clean`.
6. **Given** a green run whose home repo is missing or read-only, **When** dispatch mirrors, **Then** exit stays 0, `run.json` gains `mirror_error`, stderr names it, and no directory is created under a missing home repo.

---

### User Story 3 - The broker never hangs and never runs a Worker it cannot confine (Priority: P2)

A Lead's broker launches Claude Workers under `sandbox-exec` and serves one turn at a time. After this change, the broker refuses Claude requests when a nested sandbox cannot start, kills a Worker that outlives its deadline, keeps its request counters exact, and documents `wait` exit codes correctly.

**Why this priority**: Findings 2 (HIGH), 7, 13 and 14. A hung Worker today blocks the broker for good (`dispatch.py:1665-1669`, `:1291-1292`).

**Independent Test**: Unit tests with a stubbed `sandbox-exec` probe, a child that sleeps past a short deadline, and concurrent counter updates.

**Acceptance Scenarios**:

1. **Given** `sandbox-exec -f <minimal profile> /usr/bin/true` fails, **When** the broker validates a Claude request, **Then** it refuses with `no-sandbox-backend`, and the probe ran at most once per process.
2. **Given** a Worker child that runs past its turn deadline, **When** the deadline expires, **Then** the child's process group is killed, the child run records outcome `red`, reason `timeout`, the broker result is written, and the next request is served.
3. **Given** refused MCP requests racing a finishing turn, **When** both update `request_counts`, **Then** every increment is kept.
4. **Given** the `wait` docstring, **When** read, **Then** it states 124 for timeout and 2 for a bad request id or a non-positive timeout.

---

### User Story 4 - Doctor and the session hook tell the truth about the install (Priority: P2)

The operator starts a session and reads the hook's doctor line, or runs `agents-inc doctor`. After this change, a missing `claude` executable is a doctor code, every warning (including `INSTALL_STALE`) appears beside READY in the hook text, and the live Codex probe runs with the environment real Codex runs use.

**Why this priority**: Findings 8, 9 and 15. Claude is the required provider (`AGENTS.md` project rules), yet doctor never checks it (`agents_inc/install/doctor.py:62-96`).

**Independent Test**: Unit tests on `check_install` with a fake PATH and a recording runner, and on `hook.session_start` with a stubbed report.

**Acceptance Scenarios**:

1. **Given** no `claude` on the PATH that `worker_env` builds, **When** doctor runs, **Then** codes include `WB_CLAUDE_NOT_FOUND` and READY does not print.
2. **Given** a report with warning `INSTALL_STALE`, **When** the session-start hook runs, **Then** its text carries `WARNING: INSTALL_STALE` and the repair command.
3. **Given** `--live-model luna`, **When** doctor probes, **Then** the probe env has `HOME`, `USER` and `PATH` from `worker_env`, and no `*KEY*`, `*TOKEN*` or `*SECRET*` variable.

---

### User Story 5 - Scope and credential screens read paths, not prose (Priority: P3)

The CoS writes FILES_IN_SCOPE, GATES and BASH_ALLOW slots. After this change, prose tokens such as `only.` never become allow prefixes, a glob in FILES_IN_SCOPE is refused up front, and a gate or prefix that names a test file containing `token` or `credentials` is accepted.

**Why this priority**: Findings 10 and 11 (LOW). Each causes a false red or a false refusal, not a silent pass.

**Independent Test**: Pure-function tests on `allow_paths` and the gate/prefix screen.

**Acceptance Scenarios**:

1. **Given** FILES_IN_SCOPE "Read: any repo file. Write: .scratch/fable-audit/ only.", **When** parsed, **Then** allow is `[".scratch/fable-audit/"]`.
2. **Given** FILES_IN_SCOPE naming `src/*.py`, **When** dispatch starts, **Then** it refuses with `refused-scope`, exit 3, and no delegate starts.
3. **Given** GATES argv `python3 -m pytest tests/test_token_refresh.py`, **When** screened, **Then** it is accepted; **Given** argv naming `~/.ssh/id_rsa` or `.env`, **Then** it is still refused `refused-gates`.

### Edge Cases

- A delegate report that quotes a quota sentence (for example, a spec about quotas) and ends with a valid `WORKERS SPAWNED` line, child rc 0 and `is_error` false: not `quota-paused`. The quota and block patterns apply to stdout only when the envelope says `is_error`, the child rc is nonzero, or the report lacks a `WORKERS SPAWNED` line; they always apply to stderr.
- Quota and block both match: `quota-paused` wins (a pause is retryable; AGENTS.md counts it as one failed attempt).
- Legacy run (no private snapshot copy) resumed after upgrade: verify falls back to the run-directory copy and records `snapshot_trust: run-dir` in `run.json`.
- Private snapshot copy missing for a new-style run: reason `snapshot-error`, never `clean`.
- Stderr detail holds an environment value: `screen_text` redacts it before it reaches the status line, `run.json` or a broker result.
- Stderr detail longer than 200 bytes or containing spaces: truncated to 200 bytes and spaces replaced so the status line stays one whitespace-separated record.
- Mirror home repo path given but missing: refuse to create it; `mirror_error: home-repo-missing`.
- Turn deadline expires while the Worker waits on `ask_lead`: the Worker is killed the same way; the question stays recorded.
- Nested-sandbox probe on a non-macOS host: `sandbox_available()` stays False without running a probe.
- A direct CoS dispatch that legitimately runs longer than the turn deadline (FR-014): today unbounded, after this change red `timeout`. The env override `AGENTS_INC_TURN_TIMEOUT_S` lifts it; the default is Open for CoS item 6.
- `claude` present but logged out: static doctor check passes; only the opt-in live probe (Open for CoS item 4) would catch it.

## Requirements *(mandatory)*

### Functional Requirements

Scope gate (US1, finding 1)

- **FR-001**: Dispatch MUST keep a trusted copy of the captured snapshot outside cwd at a location derived only from the run id, and MUST verify against that copy. A top-level run writes it to `<InstallPaths.state>/dispatch-runs/<run-id>/` once, immediately before `launch` (never for `--dry-run` or a refusal) and records `snapshot_trust: "private"`. A broker child (`_BROKER_SAFE_WRITES` set) already runs in the broker-owned run dir outside cwd that Workers cannot reach (`dispatch.py:1346-1362`; D57 `docs/DECISIONS.md:618`), so it treats that copy as trusted, writes nothing under `~/.local`, and records `snapshot_trust: "broker"`. Paths: `agents_inc/install/dispatch.py` (`run`, `_verify`, `resume`). Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust.SnapshotTrustTest -v`.
- **FR-002**: Dispatch MUST compare the run-directory `snapshot.json` with the trusted copy before verifying and MUST end red, reason `snapshot-tampered`, when they differ. Path: `agents_inc/install/dispatch.py` (`_verify`, `_outcome`). Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust.SnapshotTrustTest -v`.
- **FR-003**: `_mirror` MUST write `run.json` from the in-memory spec and `prompt.md` from the launched prompt (first turn) or from a run-dir copy whose sha256 matches the trusted record (resume); on mismatch it MUST skip `prompt.md` and record `mirror_error`. Path: `agents_inc/install/dispatch.py` (`_mirror`). Acceptance: `python3 -m unittest tests.test_dispatch_snapshot_trust.MirrorPromptTest -v`.

Outcomes and exit codes (US2, #88 item 5, findings 3, 4, 5, 6, 12)

- **FR-004**: `launch` MUST return the Claude envelope's `is_error` flag; dispatch MUST treat `is_error: true` as a failed child even when rc is 0. Path: `agents_inc/install/dispatch.py` (`launch`, `_finish`). Acceptance: `python3 -m unittest tests.test_dispatch_failloud.QuotaBlockedTest -v`.
- **FR-005**: Dispatch MUST test `QUOTA_RE` on stderr always and on stdout when the child failed (rc nonzero or `is_error`) or the report lacks a `WORKERS SPAWNED` line, independent of rc; a match MUST yield red `quota-paused` and exit 75. Path: `agents_inc/install/dispatch.py` (`QUOTA_RE`, `_outcome`, `_finish`). Acceptance: `python3 -m unittest tests.test_dispatch_failloud.QuotaBlockedTest -v`.
- **FR-006**: Dispatch MUST add `BLOCKED_RE` (at least `Couldn't connect`, `ERR_PROXY_TUNNEL`, `API Error: Connection`) under the same scope rule as FR-005; a match MUST yield red `blocked` and exit 69; quota wins over blocked. Path: `agents_inc/install/dispatch.py`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.QuotaBlockedTest -v`.
- **FR-007**: `_outcome` MUST order its checks quota, blocked, rc-nonzero, then fan-out, report, snapshot, gate. Path: `agents_inc/install/dispatch.py:683-700`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.OutcomeOrderTest -v`.
- **FR-008**: When stdout is empty or the outcome is red with reason rc-nonzero, quota-paused or blocked, dispatch MUST put the first non-empty stderr line, passed through `screen_text`, truncated to 200 bytes and with whitespace replaced by `_`, into `spec["reason_detail"]` and into the status line as ` detail=<text>` before ` out=`. Path: `agents_inc/install/dispatch.py` (`_status`, `_finish`); `tests/test_dispatch_cli.py:21-22` regex extended. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.StderrDetailTest tests.test_dispatch_cli -v`.
- **FR-009**: `run` and `resume` MUST catch any exception from `launch`, write `run.json` with outcome `red`, reason `launch-failed`, `reason_detail` `<ExceptionType>: <message>` (screened), print a status line carrying the run id, and return 1. Path: `agents_inc/install/dispatch.py:934-939`, `:973-979`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.LaunchFailTest -v`.
- **FR-010**: `_mirror` MUST catch `OSError`, store `spec["mirror_error"]`, rewrite `run.json`, print one stderr line, and leave the exit code of the outcome unchanged; it MUST NOT create a missing home repo directory (only the `specs/consumers/<repo>/runs/<id>` tail under an existing home). Path: `agents_inc/install/dispatch.py:709-719`, `:739-744`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.MirrorTest -v`.
- **FR-011**: `_outcome` MUST return reason `snapshot-error` when the verifier result is `ERROR:rc=<n>`, and `snapshot-not-clean` only for `CHANGED:` results. Path: `agents_inc/install/dispatch.py:608-610`, `:694-695`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.OutcomeOrderTest -v`.
- **FR-012**: The exit-code map MUST be: 0 green or unverified; 1 any other red, including launch-failed; 2 child usage error (unchanged, `dispatch.py:742-743`); 3 refused; 69 blocked; 75 quota-paused. The broker MUST keep mapping unknown codes to request status red (`dispatch.py:1244`): a broker result carries `dispatch_exit_code` 1 for a quota or blocked child (not 69 or 75), and the Lead tells the causes apart by `reason` (`quota-paused`, `blocked`). Only the CLI exit carries 69 and 75. Path: `agents_inc/install/dispatch.py:39`, `:742-744`. Acceptance: `python3 -m unittest tests.test_dispatch_failloud.ExitCodeTest -v`.

Broker (US3, findings 2, 7, 13, 14)

- **FR-013**: `sandbox_available()` MUST, on macOS with an executable `sandbox-exec`, run `sandbox-exec -p "(version 1)(allow default)" /usr/bin/true` once per process with a 10 s timeout and cache the boolean; a nonzero exit, timeout or `OSError` MUST yield False. Path: `agents_inc/install/dispatch.py:262-263`. Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.SandboxProbeTest -v`.
- **FR-014**: Every child that `launch()` starts (Claude `subprocess.run` at `dispatch.py:517`; Codex through `run_codex` at `runtime.py:480-489`, via a new optional `timeout_s` argument that `agents-inc run` does not pass) MUST run with a deadline (default 3600 s, overridable by `AGENTS_INC_TURN_TIMEOUT_S`), in its own process group, and on expiry the group MUST be killed and the result recorded as rc 124, outcome red, reason `timeout`. Paths: `agents_inc/install/dispatch.py` (`launch`), `agents_inc/install/runtime.py` (`run_codex`). Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.TurnTimeoutTest -v`.
- **FR-015**: Every update of `spec["request_counts"]` MUST hold `_SPEC_LOCK`. Paths: `agents_inc/install/mcp_broker.py:215`, `:356`; `agents_inc/install/dispatch.py:1270`, `:1315`. Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.CounterLockTest -v`.
- **FR-016**: The `wait` docstring MUST state exit 0 found, 10 needs-lead, 124 timeout, 2 bad request id or non-positive timeout. Path: `agents_inc/install/dispatch.py:1703-1705`. Acceptance: `python3 -m unittest tests.test_dispatch_broker_robust.WaitDocTest -v`.

Doctor and hook (US4, findings 8, 9, 15)

- **FR-017**: `check_install` MUST add code `WB_CLAUDE_NOT_FOUND` when `shutil.which("claude", path=<worker_env PATH>)` returns None, and `sandbox_available()` False on macOS MUST add warning `WB_SANDBOX_NESTED`. `check_install` MUST take injectable `which=shutil.which` and `sandbox_probe=None` parameters (same pattern as `runner`, `doctor.py:62`), and existing callers in `tests/test_install_doctor.py`, `tests/test_doctor_codex_optional.py:26` and `tests/test_install_at_route.py:171-185` MUST pass stubs so the suite stays green on a host without `claude` or without nested sandboxing. Path: `agents_inc/install/doctor.py:62-96`. Acceptance: `python3 -m unittest tests.test_doctor_claude -v`.
- **FR-018**: `hook.session_start` MUST append one `WARNING: <code>` item per `report.warnings` entry to its text, and the repair command when `INSTALL_STALE` is present. Path: `agents_inc/install/hook.py:33-39`. Acceptance: `python3 -m unittest tests.test_hook_session_start -v`.
- **FR-019**: The live Codex probe MUST pass `worker_env(str(receipt.codex_path))` as env instead of `{}`. Path: `agents_inc/install/doctor.py:91`. Acceptance: `python3 -m unittest tests.test_doctor_claude -v`.

Slot parsing (US5, findings 10, 11)

- **FR-020**: `allow_paths` MUST drop tokens that end in `.` and MUST report glob characters (`*`, `?`, `[`); `run` MUST refuse a FILES_IN_SCOPE with a glob as `refused-scope`, exit 3, before render. Path: `agents_inc/install/dispatch.py:141-148`, `:850-855`. Acceptance: `python3 -m unittest tests.test_dispatch_slot_screens.AllowPathsTest tests.test_dispatch_slot_screens.ScopeGlobTest tests.test_dispatch_cli -v`.
- **FR-021**: The gate and BASH_ALLOW screen MUST match only credential home paths (`CREDENTIAL_RE` first alternative) and exact secret file names (`.env`, `id_rsa`, `id_ed25519`, `*.pem`, `*.key` as path components), not the bare words `token`, `credentials` or `api_key`; the request-slot screen `_reject_credential_seeking` stays unchanged (#88 item 4 is out of scope). Paths: `agents_inc/install/dispatch.py:657`, `:766-768`, `:774-776`, `:1014-1017`. Acceptance: `python3 -m unittest tests.test_dispatch_slot_screens.GateScreenTest tests.test_dispatch_grants -v`.

Regression

- **FR-022**: The full suite MUST stay green. Acceptance: `python3 -m unittest discover -s tests -p 'test_*.py'`.

### Key Entities

- **Trusted snapshot record**: the capture bytes and their sha256, plus the launched prompt's sha256, stored outside cwd under the run id. Read only by dispatch.
- **Run spec (`run.json`)**: gains `reason_detail`, `mirror_error`, `snapshot_trust`, `is_error`; outcome stays green, red, unverified or a refused value.
- **Status line**: one line; gains optional ` detail=<text>`.
- **Doctor report**: gains code `WB_CLAUDE_NOT_FOUND` and warning `WB_SANDBOX_NESTED`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the 15 audit findings and #88 item 5 maps to at least one requirement and one test that fails before the fix and passes after (16 of 16).
- **SC-002**: A driver loop can tell quota, connectivity, other failure and success apart from the exit code alone: 4 distinct codes (75, 69, 1, 0) in the exit-code test.
- **SC-003**: Zero tampered-snapshot runs end green in the tamper test (0 of 3 tamper shapes: edit hash, edit porcelain, delete file).
- **SC-004**: No broker turn outlives its deadline by more than 5 s in the timeout test.
- **SC-005**: Every red status line from a child with empty stdout and nonempty stderr shows the first stderr line (100% of the shapes in StderrDetailTest).
- **SC-006**: The full suite passes with 0 failures and 0 errors.

## Assumptions

- `claude -p --output-format json` emits a top-level `is_error` boolean [assumed: not provable without a live run; no fixture in `tests/` carries it]. FR-004 falls back to rc and pattern checks when the key is absent.
- Claude Code acceptEdits and Codex `--write` confine delegate writes to cwd, so a store outside cwd is out of their reach [inferred from D49 `docs/DECISIONS.md:547` and `dispatch.py:50-51`].
- Tests use temp dirs and a fake HOME; no live model call and no network.
- Canon text for new exit codes and reasons (a DECISIONS entry) is drafted by the CoS, not by an implementing Worker (D46.10(b), `docs/DECISIONS.md:502`).

## Open for CoS

1. **#88 item 5 premise.** The issue says dispatch "still exits 0"; the code returns 1 for every red (`dispatch.py:744`). Recommendation: treat the issue's `rc=0` as the child rc on the status line, keep the requirement for distinct codes (FR-012), and say so when closing #88 item 5.
2. **Nested-sandbox doctor severity.** Recommendation: warning `WB_SANDBOX_NESTED` (keeps READY; direct dispatch still works). Alternative: code (blocks READY for every dispatch, as audit finding 2 suggests).
3. **Exit codes 75 and 69.** Recommendation: 75 for quota (matches `runtime.py:551`) and 69 for blocked (sysexits EX_UNAVAILABLE). Needs a DECISIONS entry amending D58's exit list; canon edit, cross-vendor review.
4. **Live `claude auth status` probe** (audit finding 8 second half). Recommendation: defer; it is a live call and overlaps #88 item 8 (out of scope).
5. **Trusted store location.** Recommendation: `<InstallPaths.state>/dispatch-runs/<run-id>/` (mode 0700) for top-level runs, the broker-owned run dir for broker children (FR-001), research R1. Alternative: `tempfile.mkdtemp` (lost across reboots, breaks resume trust).
6. **Turn deadline default for direct dispatch.** FR-014 bounds every child, including direct CoS dispatches that are unbounded today. Recommendation: 3600 s default, `AGENTS_INC_TURN_TIMEOUT_S` override, `0` meaning no deadline. Alternative: bound broker turns only (leaves a hung direct child hung).

## CoS rulings (2026-10-18)

1-6: accept every recommendation as written. Item 3 adds a DECISIONS entry amending D58 (69 blocked, 75 quota); it needs cross-vendor review before commit. Item 6: 3600 s default, `AGENTS_INC_TURN_TIMEOUT_S`, `0` = none.
Added to implement scope: ultrareview item 9 (consensus-debate transport blocked by the D61 gate; opus-xhigh exception) and item 10 (`at_route.sh:137` Claude sync must disallow Bash).
