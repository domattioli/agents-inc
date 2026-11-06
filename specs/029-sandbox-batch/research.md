<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-28 skill=speckit-implement repo=agents_Inc session=b027a483-3613-4691-bfdd-d5c85383077c -->
# Research: 029-sandbox-batch

## R1 — FR-004: root cause of `mktemp ... Operation not permitted`

Evidence [read, run 2026-10-28 in sandboxed Bash, TMPDIR=/tmp/claude-501]:
`python3 -m unittest tests.test_model_map tests.test_install_at_route` → `Ran 24`, `FAILED (failures=3)` (supervisor re-ran: same):
- test_codexagent_guard_uses_map: `mktemp: mkstemp failed on /var/folders/44/…/T/tmp.lAIZLwg5QB: Operation not permitted`
- test_cli_mode_runs_agents_inc_with_stdin_prompt, test_hook_mode_uses_payload_cwd: `mkstemp failed on /var/folders/44/…/T/at_route_out.XXXXXX.…`
`python3 -m unittest tests.test_free_wrappers tests.test_route_health_freshness` → `Ran 20`, `FAILED (failures=7, errors=1)`:
- `/tmp/oask_response.json: Operation not permitted` (curl shim writing oask's fixed `-o` path)
- `oask.sh: line 75: /tmp/oask_report_err.<pid>: Operation not permitted` + `oask: health report failed`
- mask: `mkstemp failed on /var/folders/…/T/tmp.…`
- error `KeyError: 'failure_streak'` = downstream of the failed health report (no record written)
Total 10 F + 1 E = 11 = spec SC-001 baseline.

Decision (root cause, two mechanisms):
1. Test env drops TMPDIR. tests/test_install_at_route.py:209-211, tests/test_model_map.py:69 and tests/test_route_health_freshness.py:87-96 build `env` from scratch, with no TMPDIR. With TMPDIR unset, macOS `mktemp` (plain and `-t`) falls back to `/var/folders/…/T`, not `/tmp`. The sandbox write allowlist covers `$TMPDIR` but not /var/folders → EPERM. Scripts hit: at_route.sh:148-149, codexagent.sh:46-47, mask.sh:24-25. The scripts are correct; the tests are wrong (FR-002).
2. Wrappers hardcode `/tmp/<name>`. oask.sh:77,85, oask.sh:245,254,257-258 (`/tmp/oask_response.json`), mask.sh:58,68, gask.sh:45-46. Sandbox denies `/tmp/<name>` writes even though `/tmp/claude*` is allowed. The redirect fails before python runs → "health report failed" → no health record → assertions fail. The scripts are wrong (FR-001).
Rationale: both mechanisms are needed to explain all 11.
Alternatives considered:
- Change at_route.sh/codexagent.sh to `${TMPDIR:-/tmp}`: rejected; /tmp itself is denied under the sandbox, and the scripts already honor TMPDIR.
- Wrapper err to `2>/dev/null` (the err file is never read): decided (FR-001 now allows it).
- `oask_response.json` must move for FR-003. Reuse `OASK_REPORT_BODY_FILE` as the curl `-o` target.

Correction [run 2026-10-28, macOS 26 / Darwin 25.6, sandboxed]: mechanism 1 is wrong for this macOS. `TMPDIR=<writable> mktemp` and `TMPDIR=<writable> mktemp -t x.XXXXXX` both still write to `/var/folders/…/T` (EPERM); only an explicit template `mktemp "$TMPDIR/x.XXXXXX"` honors TMPDIR. So the test-side TMPDIR alone did not fix at_route. Fixes applied:
- at_route.sh:148-149 → `mktemp "${TMPDIR:-/tmp}/at_route_{out,err}.XXXXXX"`.
- at_route.sh box output: `} > >(…)` process substitution replaced with `>&"$box_fd"`; the sandbox denies the `/dev/fd/62` write (`at_route.sh: line 242: /dev/fd/62: Operation not permitted`).
T014 result: `python3 -m unittest tests.test_free_wrappers tests.test_install_at_route tests.test_model_map tests.test_route_health_freshness` sandboxed → `Ran 47`, `OK`.
Remaining unfixed same-class call: usage_report.sh:5 `mktemp -d` (not exercised by the suite; out of FR-002 scope).

## R2 — Probe mechanism (FR-005)
Decision: child `sys.executable agents_inc/install/netprobe.py api.anthropic.com api.github.com`, launched by the existing `runner` with `env=worker_env(sys.executable)` (dispatch.py:383-391). Child runs stdlib urllib `GET https://<host>/`, opener `build_opener(ProxyHandler({}))`, prints one JSON line per host.
Rationale: same env construction as dispatch Workers and the `--live-model` path (doctor.py:148).
Alternatives: in-process urllib (rejected: inherits caller env/proxy); `curl` child (rejected: platform variance); reuse `--live-model` (rejected: needs codex + auth + quota, no GitHub).
Limit [inferred]: the probe does not reproduce the broker's own `sandbox-exec` profile for Claude Workers.

## R3 — Codes (FR-006, FR-007, FR-012)
Per-host status: `reachable | blocked | cert`. Codes: `WB_DISPATCH_API_BLOCKED`, `WB_DISPATCH_API_CERT` (blocking); `WB_GITHUB_BLOCKED`, `WB_GITHUB_CERT` (warnings).

## R4 — Timeouts (FR-008, SC-005)
urllib `timeout=5` per host, sequential in one child; child `timeout=12`; gh `timeout=6`, run whenever `gh` exists. Worst case 18 s < 20 (both hosts down: child 12 s + gh 6 s).

## R5 — gh TLS distinction (#122, US2 sc3, FR-010)
`gh api /zen` with the caller env, whenever `which("gh")`. Stderr `x509|certificate` (case-insensitive) → github `cert`, whatever urllib returned (the worker child drops proxy env, dispatch.py:352, so in the sandbox github always reads blocked). Other gh failures ignored. gh absent → skipped.

## R6 — Test strategy (SC-003, no live network)
`netprobe.classify`/`probe(opener=fake)` in-process with constructed exceptions. `check_install(probe_dispatch=True, runner=fake, which=fake)` with canned child stdout / TimeoutExpired / gh stderr. Injection idiom of tests/test_doctor_claude.py:57-65.

## R7 — Verification results (T002, T035, T036, T037), 2026-10-28

- T002 baseline: the clone baseline run overlapped the US1 Worker's edits, so it is not a clean baseline. The pre-fix baseline stands as the R1 count (10 failures + 1 error in the four affected modules) plus the spike-tree full run (`Ran 1720`, failures=10, errors=1, skipped=26), whose failures were exactly the #113 set.
- T035 sandboxed full suite (macOS host, Claude Code sandbox): `Ran 1759`, `OK (skipped=26)`.
- T036 unsandboxed: Docker `agents-inc-dev` (Linux) gave `Ran 1770`, `FAILED (failures=1, skipped=27)`. The failure, `test_live_events.StreamRunTest.test_deadline_kills_the_group_and_marks_timeout`, passes alone in the container with and without `--init` and passes 3 of 3 on the host; it is a timing flake under full-suite load, in a file this spec does not touch. Static discovery is 1689 tests on both platforms; the `Ran` difference comes from platform-dependent runtime tests, not from the sandbox. The FR-003 same-count check needs an unsandboxed macOS run (operator `!` run), still open.
- T037: `git diff --stat` shows codexagent.sh and dispatch.py untouched and `_sandbox_exclusion` unchanged. Deviation: at_route.sh changed (mktemp templates, fd redirect), required by the R1 correction.
