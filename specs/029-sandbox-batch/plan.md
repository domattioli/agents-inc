<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-28 skill=speckit-analyze repo=agents_Inc session=b027a483-3613-4691-bfdd-d5c85383077c -->
# Implementation Plan: agents-inc under the Claude Code sandbox (batch)

**Branch**: `029-sandbox-batch` | **Date**: 2026-10-28 | **Spec**: specs/029-sandbox-batch/spec.md
**Input**: specs/029-sandbox-batch/spec.md (#113, #112 item 2, #112 item 3, #122, US5 installer allow rule)

## Summary
5 parts, 1 PR to `development`.
(A) #113: wrappers write fixed `/tmp/*` names, tests build env without TMPDIR → 11 sandbox fails. Fix: wrapper temp files via `mktemp "${TMPDIR:-/tmp}/…"`; tests pass own TMPDIR. FR-001..FR-004.
(B) #112.2: `agents-inc doctor --probe-dispatch` (opt-in). Child python, `worker_env`, stdlib urllib HTTPS to api.anthropic.com + api.github.com, optional `gh api` for TLS. Model API fail = blocking code; GitHub fail = warning. FR-005..FR-008, FR-011, FR-012.
(C) #112.3: one rule line "Codex reads stop at --cwd, paste excerpts" in SKILL.md Step 11 + QUICKREF. FR-009.
(D) #122: Hard-stops row + QUICKREF bullet for `x509: OSStatus -26276`. Doctor detects it via (B). FR-010.
(E) installer allow rule. FR-013, FR-014.

## Technical Context
**Language/Version**: Python 3 stdlib (urllib, ssl, json, subprocess); bash 3.2+ (macOS) for wrappers.
**Primary Dependencies**: none new. `gh` optional at runtime.
**Storage**: N/A. Probe result in memory only, added to `DoctorReport`.
**Testing**: `python3 -m unittest`. Pytest-style modules go through `tests/_free012.py` (`tmp_path` = `tempfile.mkdtemp()`, `tests/_free012.py:118`; `hermetic` patches `urlopen`, `:101-110`). Tests make no live network calls: runner and opener injected.
**Target Platform**: macOS (Seatbelt sandbox) main target; Linux works without sandbox hints.
**Project Type**: CLI + skill docs.
**Performance Goals**: child <=12 s (2x5 s socket timeouts + start), gh <=6 s; worst 18 s < SC-005 20 s.
**Constraints**: plain `doctor` makes no new network calls (US2 sc4). Dense one-line style in doctor.py. P9 surgical edits.
**Scale/Scope**: 3 wrapper scripts, 4 py modules, 5 test files + 1 new, 3 docs.
No NEEDS CLARIFICATION left (research.md resolves the probe design and the FR-004 cause).

## Constitution Check
- P1 repo-scoped writes: pass. Probe writes nothing. `worker_env` strips *KEY*/*TOKEN*/*SECRET* (`agents_inc/install/dispatch.py:383-391`) [read].
- P3 no self-graded gates: pass. Every FR has a supervisor-runnable test, listed below.
- P4 deterministic policy: pass. READY comes from the codes list, not from prose.
- P5 $0: pass. Probe sends unauthenticated GET; no model call, no tokens.
- P6/P8: doc edits in caveman/plain per audience. Step 11 stays 14 elements; rule added inside element 7, not a 15th element.
- P9 surgical: pass. Line-level edits; one new ~35-line module.
- P0: new D70 cross-refs D65/D66, does not restate them.
Gate: PASS (constitution unratified, so violations would be WARN). Re-check post-design: PASS.

## Project Structure
### Documentation (this feature)
specs/029-sandbox-batch/{plan.md, research.md, spec.md, checklists/}. data-model and contract are inline below (small). tasks.md comes from /speckit-tasks.

### Source Code (touched)
skills/codex-bridge/scripts/{oask.sh, mask.sh, gask.sh}       # FR-001
tests/{test_free_wrappers.py, test_route_health_freshness.py, test_install_at_route.py, test_model_map.py}  # FR-002
agents_inc/install/netprobe.py (NEW, stdlib-only child script) # FR-005, FR-006, FR-008
agents_inc/install/doctor.py                                   # FR-005..FR-008, FR-011, FR-012
agents_inc/install/cli.py                                      # FR-005, FR-007
tests/test_doctor_probe.py (NEW)                               # FR-005..FR-012
skills/workerbee/SKILL.md, skills/workerbee/QUICKREF.md        # FR-009, FR-010
agents_inc/install/host_wiring.py, tests/test_install_host_wiring.py  # FR-013, FR-014
docs/DECISIONS.md (new D70)                                    # records FR-004 cause + probe codes
NOT touched: skills/codex-bridge/scripts/at_route.sh, codexagent.sh (their `mktemp -t` / `${TMPDIR:+…}` already honor TMPDIR, at_route.sh:148-149, codexagent.sh:46-47 [read]). `_sandbox_exclusion` (doctor.py:63-73) unchanged (FR-011).

## Phase 0: Research → research.md
Resolved: FR-004 root cause, probe mechanism, code names, timeouts, gh TLS check, test injection. See research.md.

## Phase 1: Design

### Data model: Probe result (spec Key Entity)
`DoctorReport.probe: dict | None = None` (new field after `warnings`, doctor.py:25). `as_dict` adds `"probe"`.
Shape: `{"api.anthropic.com": {"status": "reachable|blocked|cert", "elapsed": 0.42, "fix": "<one line>|None"}, "api.github.com": {...}}`.
Status rules (FR-006):
- reachable = TLS handshake ok + any HTTP response, 4xx/5xx included (`HTTPError`).
- cert = `ssl.SSLCertVerificationError`, or `URLError.reason` is one; for GitHub also `gh` stderr matches `x509|certificate`.
- blocked = any other failure: refused, DNS, proxy 403 tunnel, timeout, child killed, row missing.
Code mapping (FR-007, FR-012):
- model blocked → code `WB_DISPATCH_API_BLOCKED` (blocking, READY off)
- model cert → code `WB_DISPATCH_API_CERT` (blocking)
- github blocked → warning `WB_GITHUB_BLOCKED`
- github cert → warning `WB_GITHUB_CERT`
- reachable → nothing added
Codes go through the existing `sorted(set(...))` at doctor.py:153.

### Contract: CLI
- `cli.py:218` doctor parser: append `p.add_argument("--probe-dispatch", action="store_true")`.
- `cli.py:263`: `check_install(paths, args.live_model, probe_dispatch=args.probe_dispatch)`.
- Text output: after the codes line (cli.py:267), for each host in `report.probe or {}` print `probe: <host> <status> <elapsed>s`. For a non-reachable host with a fix, print `FIX: <fix>`. Exit code unchanged: `0 if report.ready else 1` (cli.py:278).
- `--json`: `probe` key via `as_dict`.
- Model-host fix text (FR-007, D66-consistent): when `os.environ.get("SANDBOX_RUNTIME") or "WB_SANDBOX_EXCLUDE_MISSING" in warnings` → `"dispatch child cannot reach api.anthropic.com; " + SANDBOX_FIX` (SANDBOX_FIX = `dispatch.py:363-364`). Otherwise (Linux, no sandbox) → `"dispatch child cannot reach api.anthropic.com:443; check firewall/proxy"` (spec edge case: sandbox hints omitted).
- Model cert fix: `"dispatch child TLS verify failed for api.anthropic.com (proxy/MITM CA?); see D70"`.
- GitHub fix: blocked → `"allow api.github.com or use the GitHub MCP tools"`; cert → `"gh TLS fails in sandbox (#122); use the GitHub MCP tools or run gh outside the sandbox"`.

### Contract: child script `agents_inc/install/netprobe.py` (NEW)
Stdlib only, no package imports: the child gets no PYTHONPATH (`worker_env` passes only PATH/HOME/USER/TERM/LANG/TMPDIR, dispatch.py:352,383-391). Shipped automatically (bundle `rglob("*")`, bundle.py:28).
- `classify(exc) -> str`: HTTPError→reachable; SSLCertVerificationError (direct or as `URLError.reason`)→cert; else blocked.
- `probe(host, timeout=5.0, opener=None) -> dict`: opener defaults to `urllib.request.build_opener(urllib.request.ProxyHandler({})).open`, so no env or macOS system proxy is used. GET `https://<host>/`, monotonic elapsed.
- `__main__`: one JSON line per argv host, `flush=True`, so a killed child still leaves partial rows.

### doctor.py changes (dense one-line idiom)
- Add `PROBE_HOSTS = ("api.anthropic.com", "api.github.com"); PROBE_HOST_TIMEOUT = 5; PROBE_CHILD_TIMEOUT = 12; GH_TIMEOUT = 6`.
- New `_probe_dispatch(runner, which) -> dict`: `argv = [sys.executable, str(Path(__file__).with_name("netprobe.py")), *PROBE_HOSTS]`; `runner(argv, env=worker_env(sys.executable), capture_output=True, text=True, timeout=PROBE_CHILD_TIMEOUT, stdin=subprocess.DEVNULL, check=False)`. Catch `TimeoutExpired` (`exc.stdout or b""`, decode if bytes) and `OSError` (stdout = ""). Parse JSON lines; any missing host → `{"status": "blocked", "elapsed": PROBE_CHILD_TIMEOUT}`. If `which("gh")` (always, in the caller env): `runner([gh, "api", "/zen"], capture_output=True, text=True, timeout=GH_TIMEOUT, stdin=DEVNULL, check=False)` with the caller env, because #122 hits the caller's gh. `re.search(r"x509|certificate", stderr, re.I)` → github `cert`, whatever urllib returned. Any other gh failure (auth, rate limit) is ignored. Missing gh or a gh timeout never adds a code.
- New `_probe_codes(probe, warnings, env=os.environ) -> (codes, warnings)` (env injected so tests pin both fix branches): applies the mapping above and sets `fix`.
- `check_install(..., probe_dispatch: bool = False)`: after the live block (doctor.py:144-152), `if probe_dispatch: probe = _probe_dispatch(runner, which); c, w = _probe_codes(probe); codes += c; warnings += w`. Runs even when other codes exist. Return `DoctorReport(..., probe=probe)`.
- Lazy import already present (doctor.py:112). Add `SANDBOX_FIX`.
- `check_install` not-installed early returns skip the probe.
- `_sandbox_exclusion` and its call (doctor.py:63-73, 137) left byte-identical (FR-011).

### Wrapper changes (FR-001 + FR-003)
- oask.sh:77,85: in `oask_report_trap`, send the health-report stderr to `2>/dev/null` (decided; no err file). Cleanup: `rm -f "$OASK_REPORT_BODY_FILE"`. Exit code untouched (`exit $ec`, oask.sh:86).
- mask.sh:58,68 and gask.sh:45-46: same (`2>/dev/null`, no err file).
- oask.sh:245-258, the fixed `/tmp/oask_response.json` (also fails in sandbox, see research). Move `OASK_REPORT_BODY_FILE=$(mktemp "${TMPDIR:-/tmp}/oask_response.XXXXXX")` above `OASK_ATTEMPTED=true` (oask.sh:244), before the curl call. Use `curl -o "$OASK_REPORT_BODY_FILE"` and `RESPONSE=$(cat "$OASK_REPORT_BODY_FILE")`. Delete the cp (`:257`) and rm (`:258`) lines. The trap at oask.sh:85 already removes the file. Needed for FR-003.

### Test changes (FR-002)
- tests/test_install_at_route.py:209 env dict: add `"TMPDIR": str(self.root)`.
- tests/test_model_map.py:69 env dict: add `"TMPDIR": self.tmp.name`.
- tests/test_route_health_freshness.py:87 `self.env`: add `"TMPDIR": str(Path(self.tmp.name))`.
- tests/test_free_wrappers.py:106 `wrapper_env`: add `monkeypatch.setenv("TMPDIR", str(tmp_path))`. Tests use `env=os.environ.copy()` (e.g. :164), so monkeypatch carries through.

## Phases, files, tests, trace

### Phase A — sandbox-clean suite (P1, US1)
| FR | Files | Test |
|---|---|---|
| FR-001 | oask.sh:77,85,245-258; mask.sh:58,68; gask.sh:45-46 | test_free_wrappers.py new `TestWrapperTempFiles`: (a) static: each script text has no `/tmp/[a-z_]+(report_err|response)` literal; (b) run oask/mask/gask with TMPDIR=`tmp_path/"t"` through the existing shim; afterwards the TMPDIR subdir `tmp_path/"t"` is empty (T004); (c) TMPDIR pointed at a non-writable dir (chmod 0o500): non-zero exit, no traceback, no new files |
| FR-002 | 4 test files above | existing tests turn green |
| FR-003 | (none beyond A) | `python3 -m unittest discover -s tests -p 'test_*.py'` in sandbox → `OK`; same command unsandboxed (operator `!` run or CI) → same `Ran N`. No new sandbox-conditional skips |
| FR-004 | research.md + D70 | record before fix; research task precedes FR-002 task |

### Phase B — doctor probe (P2, US2 + US4 detection)
| FR | Files | Test (tests/test_doctor_probe.py, unittest, fixture idiom of tests/test_doctor_claude.py:26-65) |
|---|---|---|
| FR-005 | netprobe.py, doctor.py, cli.py:218,263 | fake runner records argv/env: argv[1] endswith `netprobe.py`; `env == worker_env(sys.executable)`; no `HTTPS_PROXY`, no `*TOKEN*`. `probe_dispatch=False` → runner never called with netprobe argv (US2 sc4) |
| FR-006 | netprobe.py `classify`/`probe` | injected opener raising HTTPError→reachable; URLError(SSLCertVerificationError())→cert; URLError(ConnectionRefusedError), TimeoutError, socket.gaierror, OSError("Tunnel connection failed: 403")→blocked (SC-003) |
| FR-007 | doctor.py `_probe_codes`, cli.py print | model blocked → `ready False`; CLI text output via `main(["doctor","--probe-dispatch"])` with patched check_install has no `READY` and one `FIX:` line containing `agents-inc *` (SC-002) |
| FR-008 | doctor.py constants, TimeoutExpired path | fake runner raises `TimeoutExpired(argv, 12, output='{"host":"api.github.com","status":"reachable","elapsed":0.1}\n')` → anthropic `blocked`, no raise. Assert `PROBE_CHILD_TIMEOUT + GH_TIMEOUT < 20` and the timeout kwarg passed equals the constant (SC-005) |
| FR-011 | none (guard) | settings without exclusion + probe model blocked → `warnings.count("WB_SANDBOX_EXCLUDE_MISSING") == 1`, no other code containing `EXCLUDE` |
| FR-012 | doctor.py `_probe_codes` | github blocked → `WB_GITHUB_BLOCKED` in warnings, `ready True`; gh stderr `x509: OSStatus -26276` whatever the child's github row → `WB_GITHUB_CERT` warning, ready True; `which` returns None for gh → no gh call, no code |

### Phase C — docs (P3, US3 + US4)
| FR | Files | Test |
|---|---|---|
| FR-009 | SKILL.md Step 11 element 7, after line 701 ("…does not commit."); QUICKREF.md "MUST lines that are easy to drop" list (after :43) | test_doctor_probe.py `DocsTest`: both files contain the identical sentence `A Codex delegate (astra, sol, terra, luna) cannot read a path outside --cwd; paste the needed excerpts into the prompt.` |
| FR-010 | SKILL.md Hard stops table, new row after :992; QUICKREF.md Hard stops (after :64) | both files contain `x509: OSStatus -26276`, `GitHub MCP`, `outside the sandbox`, `not confirmed` (SC-004) |
| (record) | docs/DECISIONS.md new `## D70` (amends D66): probe flag, 4 codes, FR-004 cause | none (prose) |

Row text (FR-010): `| gh fails with x509: OSStatus -26276 in sandboxed Bash (#122) | Cause outside this repo, not confirmed (suspected: sandbox proxy CA vs macOS keychain trust). Use the GitHub MCP tools, or run gh outside the sandbox. Do not retry gh unchanged. doctor --probe-dispatch reports WB_GITHUB_CERT. Upstream: none filed yet |`

### Sequencing
A1 research (FR-004) → A2 test env TMPDIR (FR-002) → A3 wrappers (FR-001) → A4 full suite (FR-003). B1 netprobe.py + classify tests → B2 doctor.py → B3 cli.py → B4 probe tests. C1/C2 docs + doc test. D70 last. A, B, C independent once A1 lands; B4's doc test needs C.

### FR trace hints for /speckit-tasks
FR-001→A3; FR-002→A2; FR-003→A4; FR-004→A1+D70; FR-005→B1,B2,B3; FR-006→B1; FR-007→B2,B3; FR-008→B2; FR-009→C1; FR-010→C2; FR-011→B4 guard; FR-012→B2,B4; FR-013→D; FR-014→D.

## Grill (self-challenge: one misfire per code, and the guard)
- reachable false positive: child inherits caller proxy env or macOS system proxy and gets through, while a real Worker cannot. Guard: `worker_env` drops proxy vars (dispatch.py:352) and the opener uses `ProxyHandler({})`. FR-005 test asserts the env.
- reachable false negative: api.anthropic.com `/` returns 404/401 and the code reads it as failure. Guard: `HTTPError` = reachable.
- WB_DISPATCH_API_BLOCKED false positive: DNS slow, or child start slow on a cold disk, so the timeout trips. Guard: 12 s child budget > 2×5 s host timeouts; partial JSON lines kept; fix line says rerun. Residual: real flaky network reported as blocked (by design).
- WB_DISPATCH_API_CERT false positive: corporate MITM CA trusted by keychain but not by Python's OpenSSL bundle. Guard: blocking per FR-012 anyway; fix text names the cause. [inferred] residual; note in D70.
- WB_GITHUB_BLOCKED false negative: urllib reaches GitHub, but gh in the caller sandbox cannot. Guard: gh check runs whenever `gh` exists, in the caller env.
- WB_GITHUB_CERT false positive: gh auth error text mentions "certificate". Guard: regex `x509|certificate` only, auth failures ignored. Warning-only.
- READY false positive (SC-002): probe exception escapes and doctor prints READY. Guard: `_probe_dispatch` catches OSError/TimeoutExpired, missing rows default to blocked (fail closed, P4).
- Wrapper misfire: TMPDIR unwritable makes mktemp fail. Guard: wrappers run `set -euo pipefail`, so mask.sh:24-25 and gask.sh:268 abort first with non-zero exit and a stderr line; no hang, no file left.

## Complexity Tracking
None. One new module (netprobe.py) is justified: the child needs stdlib-only code it can run with no PYTHONPATH, and the code must be importable for in-process classify tests.

## Phase D — US5 installer allow rule

Spec 029 US5, FR-013, FR-014, SC-006. Out of scope: delegate `--allowedTools` (D51/D59), phases A-C. Mirrors `add_sandbox_exclusion` / `strip_sandbox_exclusion` (host_wiring.py:112-127 [read]). No new module, no cli change.

- `host_wiring.py` (only product file touched): `ALLOW_RULE = "Bash(agents-inc *)"` after SANDBOX_EXCLUDE (:110). `add_allow_rule(config)`: setdefault `permissions` then `allow`; skip non-dict/non-list; append only if absent. `strip_allow_rule(config)`: equality filter; delete `allow`, then `permissions`, when emptied.
- Wiring: `add_hooks` :144 claude-only adds both; `strip_hooks` :95 strips both, which reaches uninstall (remove_host_wiring) and `unwire_hooks` (:239). `unwire_hooks` reports `permissions.allow: Bash(agents-inc *)` beside :236-237.
- `--no-host-wiring` (FR-013): install_host_wiring is never called (cli.py:150 [read]); a test pins it.
- Idempotency: add checks membership; install runs strip_hooks first, so N installs leave one rule.
- Uninstall preserves others (FR-014, SC-006): exact-string equality on one entry; other allow entries, `deny`/`ask`/`defaultMode` and order unchanged.
- Tests: tests/test_install_host_wiring.py next to :102 (tasks T039-T041).
- Grill: an operator who hand-added the identical `Bash(agents-inc *)` before install loses it on uninstall; equality cannot tell ours from theirs. Same blind spot as the sandbox exclusion today (:124). Mitigation: near-variants are never touched; write_file keeps a byte-exact backup. Residual risk accepted [inferred]; receipt-tracked ownership exceeds smallest change.
