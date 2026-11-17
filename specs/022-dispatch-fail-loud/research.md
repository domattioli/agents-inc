# Research: 022-dispatch-fail-loud

Every decision cites the code read on 2026-10-18 at HEAD `62c2a75` (working tree; the audited files are unmodified).

## R1 Trusted snapshot store (FR-001..003)

- Decision: capture still writes `<run-dir>/snapshot.json` (`dispatch.py:880`) for the delegate's own FAILURE GATE check. Once, immediately before `launch` (after `_record_ledger_node` at `dispatch.py:929`, so after any roster prompt rewrite at `:928` and never on `--dry-run` at `:912-915` or a refusal), a top-level run copies those bytes to `<InstallPaths.state>/dispatch-runs/<run-id>/snapshot.json` (dir mode 0700) and records `snapshot_trust: "private"`. A broker child (`_BROKER_SAFE_WRITES` set) skips the state dir: its run dir is broker-owned, outside cwd and denied to Workers (`dispatch.py:1346-1362`, D57 `docs/DECISIONS.md:618`), so it writes `trust.json` beside the run-dir copy and records `snapshot_trust: "broker"`. It keeps `snapshot_sha256` and `prompt_sha256` in the private dir as `trust.json`. `_verify` reads the private copy; it compares the run-dir copy's sha256 first and returns `snapshot-tampered` on mismatch or deletion. The private path is computed from `run_id` only, never read from `run.json`.
- Rationale: the run dir sits under cwd when `.scratch` is git-ignored (`agents_inc/install/dispatch.py:49-58`); `_verify` trusts that file (`dispatch.py:605`, `skills/workerbee/scripts/pre_dispatch_snapshot.py:99-106`). `run.json` is in the same dir, so a pointer stored there is also writable. The state dir is reached via `_paths()` (`dispatch.py:525`, `agents_inc/install/doctor.py:31`); Claude broker Workers are denied `~/.local` (`dispatch.py:233`) and Codex writes only cwd (`docs/DECISIONS.md:545`).
- Alternatives: in-memory bytes only (lost on `--resume`, which is a new process, `dispatch.py:949-990`); `tempfile.mkdtemp` (not found again on resume); signing with a key (needs a secret store; out of proportion).
- Legacy runs (no private dir): verify against the run-dir copy and set `snapshot_trust: "run-dir"`.

## R2 Nested sandbox probe (FR-013, FR-017)

- Decision: `sandbox_available()` runs `[SANDBOX_EXEC, "-p", "(version 1)(allow default)", "/usr/bin/true"]` with `timeout=10`, `capture_output=True`, and caches the result in a module global (reset hook for tests). Non-darwin or missing binary: False with no probe.
- Rationale: today it checks only `os.access` (`dispatch.py:262-263`); macOS refuses a nested seatbelt (`agents_inc/install/runtime.py:97-98`, `docs/DECISIONS.md:549`). The broker already refuses on False (`dispatch.py:1163-1164`, `:507-508`).
- Doctor: warning `WB_SANDBOX_NESTED` (Open for CoS item 2 in spec).

## R3 Failure classification (FR-004..008, FR-011, FR-012)

- Decision: `launch` adds `"is_error": bool(data.get("is_error"))` for Claude (parse at `dispatch.py:519-523`); Codex sets False. `_finish` computes `failed = rc != 0 or is_error`, `reported = parse_workers_spawned(stdout) is not None`. Pattern scope: stderr tail always; stdout tail when `failed or not reported`. Order in `_outcome`: quota, blocked, rc-nonzero (`failed`), fan-out, report, snapshot (tampered, error, not-clean), gate.
- `BLOCKED_RE = r"Couldn't connect|ERR_PROXY_TUNNEL|API Error: Connection|ECONNREFUSED|ENOTFOUND"`, case-insensitive.
- Exit codes: 75 quota-paused (`runtime.py:551` precedent), 69 blocked. `_finish` returns them before the generic red branch (`dispatch.py:742-744`). Broker: codes outside `REQ_STATUS` map to `REQ_RED` (`dispatch.py:1244`, `:1586`) and the child reason passes through (`:1247`), so broker results need no change.
- Rationale: the current gate `rc != 0 and quota` (`dispatch.py:686`) misses the rc-0 case; `fan_reason` precedes rc (`:688-691`). A delegate report may quote quota text; limiting stdout matching to failed or reportless runs avoids a false pause.
- Alternatives: new outcome values `quota-paused`/`blocked` (breaks the D58 outcome set and `tests/test_dispatch_cli.py:21-22`); match always (false positive on reports quoting the text).

## R4 Stderr detail (FR-008)

- Decision: helper `_stderr_detail(stderr)`: first non-empty line, `screen_text(line, 200)` (`dispatch.py:1443`), whitespace runs replaced by `_`. Status line becomes `... outcome=<o>[ reason=<r>][ detail=<d>] out=<path>`. `tests/test_dispatch_cli.py:21-22` STATUS_RE gains `( detail=\S+)?`.
- Rationale: `_status` prints `rc=` and `out=` only (`dispatch.py:703-706`); the broker copies `status_line` (`:1248`), so the detail reaches the Lead without a new field.

## R5 Launch exceptions (FR-009)

- Decision: wrap `launch(...)` at `dispatch.py:934-939` and `:973-979` in `try/except Exception as exc`; set `rc=-1`, outcome `red`, reason `launch-failed`, `reason_detail=screen_text(f"{type(exc).__name__}: {exc}", 200)`; write empty `stdout.md`; `_write_json(run.json)`; print `dispatch <id> <model> rc=-1 report=none snapshot=none outcome=red reason=launch-failed detail=<d> out=<run-dir>/stdout.md` (`contracts/dispatch-outcomes.md`); `_mirror`; return 1. `rc=-1` keeps `STATUS_RE`'s `rc=-?\d+` (`tests/test_dispatch_cli.py:21-22`).
- Rationale: raisers at `dispatch.py:493`, `:307`, `:507-508`, `:517` (missing binary via `:153`); `cli.py:237` prints only `str(exc)`.

## R6 Mirror (FR-003, FR-010)

- Decision: `_mirror` returns an error string or None; requires `Path(home).is_dir()` else `home-repo-missing`; creates only `specs/consumers/<repo>/runs/<id>` with `parents=True` under the existing home; writes `run.json` via `json.dumps(spec)`; writes the in-memory prompt on first turn; on resume copies `prompt.md` only when its sha256 equals `trust.json` `prompt_sha256`. `OSError` caught. `_finish` stores `mirror_error`, rewrites `run.json`, keeps the outcome's exit code.
- Rationale: `dispatch.py:709-719`, `:739-744`; `cli.py:237`; broker `:1358-1359`.

## R7 Turn deadline (FR-014)

- Decision: `launch` gains `timeout_s` (default from `AGENTS_INC_TURN_TIMEOUT_S`, else 3600). Claude path: `subprocess.Popen(..., start_new_session=True)` + `communicate(input, timeout)`; on `TimeoutExpired`, `os.killpg(pgid, SIGKILL)`, collect, return rc 124 and stderr `turn timeout after <n> s`. Codex: `run_codex(..., timeout_s=None)` applies the same in `runtime.py:480-489` when given. `_outcome` maps rc 124 with that stderr marker to reason `timeout`.
- Rationale: no timeout today (`dispatch.py:517`, `runtime.py:480-489`); serve loop resets `last` while a turn lives (`dispatch.py:1665-1669`); busy re-poll (`:1291-1292`) and `worker-running` (`mcp_broker.py:222-223`). Gate runs already use `timeout=` (`dispatch.py:663-665`), the same shape.
- Alternatives: kill from the serve loop (needs the child pid across threads; more state).

## R8 Counters and docs (FR-015, FR-016)

- Decision: wrap `mcp_broker.py:215` and `:356`, `dispatch.py:1270` and `:1315` in `with D._SPEC_LOCK:` / `with _SPEC_LOCK:` (an `RLock`, `dispatch.py:1371`, so nesting is safe). Docstring at `dispatch.py:1703-1705` reworded.
- Note on finding 14: the docstring already says 124 on timeout; "2 on a bad request id or timeout" means a bad timeout argument (`dispatch.py:1706-1708`). The fix is wording only.

## R9 Doctor and hook (FR-017..019)

- Decision: `check_install` computes `env = worker_env(shutil.which("claude") or "/usr/bin/false")` and `shutil.which("claude", path=env["PATH"] + ":" + os.environ.get("PATH", ""))`; None adds code `WB_CLAUDE_NOT_FOUND`. Import from `dispatch` is lazy (dispatch imports cli, `dispatch.py:525`). Live probe env: `worker_env(str(receipt.codex_path))` (`dispatch.py:236-244`). Hook: `text += " " + " ".join(f"WARNING: {w}." for w in report.warnings)`; when `INSTALL_STALE` in warnings add " Run `agents-inc repair --source <agents_Inc checkout>`."
- Rationale: `doctor.py:62-96`, `:91`; `hook.py:33-39`; `cli.py:196-198` already prints warnings by hand.
- Risk: a host where `claude` is reachable only through a PATH entry outside `WORKER_PATH` but not on the operator PATH; using both PATHs avoids a false code on the CoS host.

## R10 Slot parsing (FR-020, FR-021)

- Decision: `allow_paths` skips tokens ending in `.`; new `scope_globs(files_in_scope)` returns tokens with `*?[`; `run` refuses `refused-scope` before render, next to `_grants_from_slots` (`dispatch.py:850-855`). New `GATE_CREDENTIAL_RE`: the home-path alternative of `CREDENTIAL_RE` (`dispatch.py:1015`) plus `(^|/)\.env(\.|$)|(^|/)id_(rsa|ed25519)\b|\.pem$|\.key$` per argv element; used at `:657`, `:767`, `:775`. `CREDENTIAL_RE` stays for request slots (`:1170`).
- Rationale: `allow_paths` at `dispatch.py:141-148`; existing test `tests/test_dispatch_cli.py:458-461` must still pass; `_allowed` prefix match (`pre_dispatch_snapshot.py:90-96`) never matches a glob.
