<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-analyze repo=agents_Inc session=b8dceec1 -->
# Implementation Plan: spec 026, delegated runs work inside the sandbox, plus broker hygiene

**Branch**: `development` | **Date**: 2026-10-24 | **Spec**: `specs/026-sandbox-safe-runs/spec.md`
**Input**: Feature specification from `specs/026-sandbox-safe-runs/spec.md` (issues #110, #103, #109 items 1 and 2, #88 items 2 and 3; triage of #89, #87, #88 items 1 and 4). Operator rulings R1, R2 and the 2026-10-24 Clarifications (final route: metadata-only reads above sandbox holes, spec FR-009) are binding.

Line numbers below were re-grepped on the working tree on 2026-10-24 (HEAD `5f01dfe`). Re-run `grep -n` before each edit.

## Summary

US0 is GitHub bookkeeping done by the CoS (no code). US1 makes the two test modules that break under the Claude Code sandbox run there: fixed `/tmp` paths move to temp dirs, and a refused loopback bind skips with a stated reason (R1). US2 lets a broker Claude Worker run git: the Worker profile allows metadata-only reads on the folders between the broker run-dir deny and the Worker TMPDIR, so git can resolve its repository path (CoS reproduction), and the Worker may read its own `pre_dispatch_snapshot.py` and `snapshot.json`. US3 adds an exclusive `broker.lock` so one run directory has one broker. US4 refuses C0, DEL and bidi control characters in slots at render and at dispatch. US5 adds an "unreadable caveman" path to the prompt contract (R2). US6 drops the `--write` requirement from `--run-dir`.

## Technical Context

**Language/Version**: Python 3.11+, standard library only (`fcntl` for US3).
**Primary Dependencies**: none new. `git` on PATH for the US2 regression test (host git 2.48.1 per spec FR-009). `/usr/bin/sandbox-exec` for the US2 enforced test (macOS only; skipped elsewhere).
**Storage**: new file `<run-dir>/broker.lock` (pid text). No `run.json` schema change, no broker request protocol change (spec Scope).
**Testing**: `unittest`. Enforced-profile tests follow the existing pattern at `tests/test_dispatch_broker.py:523-554` (`test_sandbox_profile_enforced`) and `:736` (`test_sandbox_deny_paths_enforced`).
**Target Platform**: macOS (sandbox-exec) and Linux hosts.
**Project Type**: CLI and library.
**Performance Goals**: N/A. US3 adds one `open`+`flock` per broker start; US4 adds one regex scan per slot.
**Constraints**: $0 spend; no network; tests use temp dirs and a fake HOME; no change to `pre_dispatch_snapshot.py`; no widening of the Codex read-only sandbox (R2); no new read grant under `~/.config` (Clarification).
**Scale/Scope**: about 8 functions changed or added in `dispatch.py`, 2 in `runtime.py`, 1 in `render_dispatch.py`, 1 keyword list in `check_dispatch_prompt.py`, 3 doc files in `skills/workerbee/`, 7 test files, D68, 6 CHANGELOG lines.

Research and data model are folded into this file, as in spec 025. No NEEDS CLARIFICATION remains. The only data items are `broker.lock` (US3) and the refusal reason `refused-control-char` (US4), each defined below. No contracts/ or quickstart.md: the interfaces are stderr lines and result-file reasons, given verbatim below. The DomI `SPECKIT` agent-context marker step does not apply (not a DomI run).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- P1 repo-scoped writes: all writes inside agents_Inc; tests use temp dirs and a fake HOME. The US2 enforced test runs `git init` only inside a temp TMPDIR. Pass.
- P3 no self-graded gates: US2 FR-011 lets a Worker read `snapshot.json`; the trusted snapshot copy (022 FR-001) still judges the run, so the Worker's readable copy cannot change the verdict. The profile must also deny writes to that file (see US2 risk R2-2). Pass with that deny.
- P4 deterministic policy over prompt: US3 lock, US4 regex and US6 argument checks are code. US5 is a prompt-contract change by design (R2). Pass.
- P8 prompt contract: the implement dispatch carries the 14 fields; FILES IN SCOPE is the spec Scope list (D1 and D2 resolved there). Pass.
- P9 surgical edits: no file rewritten whole. Pass.
- Result: no violation. Post-design re-check: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/026-sandbox-safe-runs/
├── spec.md                    # specify + clarify output
├── plan.md                    # this file
├── tasks.md                   # /speckit-tasks output
├── triage.md                  # US0, written by the CoS (FR-002)
└── checklists/requirements.md # /speckit-checklist output
```

### Source Code (repository root)

```text
agents_inc/install/dispatch.py                     # US2, US3, US4
agents_inc/install/runtime.py                      # US6
skills/workerbee/scripts/render_dispatch.py        # US4 FR-018/FR-019
skills/workerbee/scripts/check_dispatch_prompt.py  # US5 FR-023
skills/workerbee/header.md                         # US5 FR-022/FR-023 (:11, :16)
skills/workerbee/QUICKREF.md                       # US5 FR-024 (:46)
tests/test_ollama_adapter.py                       # US1 FR-005
tests/test_bridge_thread_id.py                     # US1 FR-006..FR-008
tests/test_dispatch_broker.py                      # US2 FR-011/FR-012 (see D1), US3 FR-017
tests/test_dispatch_slot_screens.py                # US4 FR-021
tests/test_dispatch_cli.py                         # US4 FR-021 render case
tests/test_codex_tool_access.py                    # US6 FR-028
tests/test_dispatch_header.py                      # US5 FR-025 header clause
skills/workerbee/tests/test_template_revision.py   # US5 FR-025 report profile
docs/DECISIONS.md                                  # D68 (SC-006), after D67 at :688
CHANGELOG.md                                       # 6 lines under ## [Unreleased] (:7) / ### Fixed (:9)
```

**Structure Decision**: existing single-project layout; no new modules.

## US2 reproduction (#103 cause)

Run by the CoS on 2026-10-24, outside the Claude Code sandbox (a nested `sandbox-exec` fails rc 71 inside it), with the real `claude_sandbox_profile` output: `deny_paths=(<broker run dir>,)`, Worker TMPDIR `<broker>/workers/w1/tmp`. Script: session scratchpad `repro103c.py` (session b8dceec1). Cause **[verified]**: not `~/.config`.

| Case | Result |
|---|---|
| Profile with `~/.config` deny, no `deny_paths`: `git init`, `git commit` in TMPDIR | rc 0, rc 0 |
| Real profile (broker deny): `git init <tmp>/repo` | rc 128, `fatal: Invalid path '<broker run dir>': Operation not permitted` |
| Real profile: `skills.workerbee.tests.test_pre_dispatch_snapshot` + `tests.test_dispatch_resume` | 21 errors |
| Real profile + `(allow file-read-metadata (literal <a>))` per ancestor `a` from the deny root down to TMPDIR (exclusive): same suites | 0 errors, 1 failure (`DefaultParentTest.test_missing_scratch_and_non_repo_fall_back`: the reproduction's temp dir sat inside this checkout; an artifact of location) |
| Same suites, no profile | 35 tests OK |
| Patched profile: `cat` of a file in the broker run dir; `ls` of the broker run dir; write `snapshot.json` | rc 1, rc 1, rc 1 |

Why: SBPL `file-read*` covers `file-read-metadata`. git resolves the real path of every parent of the new repository (`lstat` per component); the components between the broker run dir and TMPDIR sit inside the denied subpath and outside the TMPDIR hole, so `lstat` fails with EPERM. `~/.gitconfig` (`git config --global --list --show-origin`) holds `user.name`, `user.email`, `credential.helper`, `core.excludesfile` (a path outside `~/.config`) and `init.defaultbranch`; it includes nothing under `~/.config`. No `GIT_CONFIG_GLOBAL` or `XDG_CONFIG_HOME` change is needed.

## Design per story

### US0 (#89, #87, #88 items 1 and 4): triage (FR-001 to FR-004a) [CoS]

No code. The CoS writes `specs/026-sandbox-safe-runs/triage.md` with one row per item: `issue | item | verdict (fixed/open/moved) | evidence (commit or D-number + one file:line) | note`. Rows: #89 every numbered item, #87 items 1 to 5, #88 items 1 and 4. One follow-up row from FR-004a (the text screen refusing a design question that names `~/.config/git`). Comments go through `comment-issue`; close with `completed` only when every row of that issue is `fixed` or `moved`. No delegate touches GitHub (spec Assumptions).

Starting evidence for the CoS (verified this session, not a verdict): `credential_hit` path screen `dispatch.py:1757-1763` and D67 `docs/DECISIONS.md:688` (#87 item 1, #88 item 4); `refused-scope` `dispatch.py:1306`, `:1332`; per-turn timeout `_turn_timeout` `dispatch.py:414-421`.

### US1 (#110): suite runs inside the Claude Code sandbox (FR-005 to FR-008)

Anchors (verified): `tests/test_ollama_adapter.py:264` (`Path("/tmp/ws")`, passed to `policy.check_dispatch` with `is_local_authorized` patched), `:405` and `:411` (`Path("/tmp/test.lock")` under patched `open`/`fcntl.flock`), `:711-721` (`Path("/tmp/test_ws")`, then `mkdir` and `write_text` of `.workerbees/doctor.json`: a real write to fixed `/tmp`). `tests/test_bridge_thread_id.py:55-70` (`BridgeThreadIdTest.setUp`, `bridge.CodexBridgeServer(("127.0.0.1", 0), ...)`), `:202-207` (`AskShBodyShapeTest.setUp`, `http.server.HTTPServer(("127.0.0.1", 0), ...)`).

- FR-005: `:711`: wrap in `tempfile.TemporaryDirectory()` and use `Path(raw) / "test_ws"`. `:264`: same pattern as the sibling test at `:273-274`. `:405`, `:411`: use `Path(self.tmp) / "test.lock"` from a `setUp` temp dir (or a `TemporaryDirectory` context). Acceptance grep: `grep -n '"/tmp' tests/test_ollama_adapter.py` prints nothing.
- FR-006, FR-007: module-level helper in `tests/test_bridge_thread_id.py`:
  - `_BIND_REFUSED = "local port binding refused (sandbox); run outside the sandbox or set sandbox.network.allowLocalBinding"`
  - `_bind_probe() -> str | None`: cached in a module global; opens `socket.socket()`, `bind(("127.0.0.1", 0))`, closes; returns `_BIND_REFUSED` on `PermissionError`, else `None`. Any other `OSError` propagates (FR-006 "any other bind error still fails").
  - Both classes get `setUpClass` that calls `_bind_probe()` and `raise unittest.SkipTest(reason)` when it returns a reason. This is the "first local bind of a test class attempted once" in FR-006; the probe result is shared by both classes so the bind is tried once per module.
- FR-008: outside the sandbox the probe binds, so no skip. Check with the SC-001 discover command; skips must not rise.
- Tests: add `BindProbeTest` in the same module: patch `socket.socket.bind` to raise `PermissionError` and assert the reason string; patch it to raise `OSError(98)` and assert it propagates. Reset the cache global in each case.
- Risk R1-1: the cache global leaks between `BindProbeTest` and real classes; reset it in `addCleanup`.

### US2 (#103): broker Worker can run git (FR-009 to FR-012)

Anchors (verified): `WORKER_ENV_KEYS` `dispatch.py:339`; `CLAUDE_WORKER_DENY` `:343`; `worker_env` `:370-378` (copies `WORKER_ENV_KEYS` from the broker's own env); `sandbox_available` `:399-411`; `claude_sandbox_profile` `:433-463` (`read_ok` literal holes `:452`, broker deny `:453-455`, home deny `:460`); `_child_tmp` `:466-472`; Claude Worker env and profile `:675-686`; Codex Worker env `:722-724`; `extra_read` for Codex `:736-737`; `_BROKER_DENY` `:781`, set to the Lead run dir in `_in_worker_scope` `:1962`.

- FR-009, in `claude_sandbox_profile`: after the `broker_deny` rules (SBPL: the last matching rule wins), emit `(allow file-read-metadata (literal "<a>"))` for every folder `a` with `d <= a < h`, for each deny root `d` in `deny_paths` and each hole `h` (`tmpdir`, every `write_ok`, every `read_ok`) that lies under `d`. Use a helper `_ancestors_between(root, leaf)` over resolved paths; skip a hole not under the root. Metadata only: no `file-read-data`, no directory listing (`readdir` needs `file-read-data`), no write. Dedupe the literals.
- No env change: `WORKER_ENV_KEYS` and `CLAUDE_WORKER_DENY` stay as they are. TMPDIR stays `<run-dir>/tmp` (FR-010).
- Codex Worker (`dispatch.py:722-737`, `runtime.permission_profile` with `extra_deny`): Codex enforces its own profile. The implement delegate reads `runtime.permission_profile` and states in its report whether the `extra_deny` entry blocks metadata on the run dir's folders. If the Codex profile language has no metadata-only grant, record that as a follow-up; do not widen the Codex deny.
- FR-011: in the Claude branch, extend the `read_ok` tuple passed to `claude_sandbox_profile` at `:684` with `Path(run_dir) / "pre_dispatch_snapshot.py"` and `Path(run_dir) / "snapshot.json"` (always, not only with an ask channel).
- FR-011 write deny (risk R2-2): `read_ok` holes punch through the broker deny for both read and write (`:451-455`). When the run dir sits under the Worker cwd (the default parent is the repo `.scratch`), the cwd write grant would then allow writing those files. Add one rule to `claude_sandbox_profile`: `(deny file-write* (literal "<p>") ...)` for every `read_ok` path. This also closes the same latent write path for the ask channel's script and config (D54), which is a tightening, not a new grant.
- FR-012 test, in `tests/test_dispatch_broker.py` (D1 accepted): class `WorkerGitTest`.
  - `@unittest.skipUnless(dispatch.sandbox_available(), "sandbox-exec unavailable or nested sandbox")`, plus the existing `sandbox_apply` skip guard (`tests/test_dispatch_broker.py:533-534`).
  - Fake HOME. Fake broker run dir `<b>` holding `secret.txt`, and a child run dir `<b>/workers/w1/` holding `snapshot.json`, `pre_dispatch_snapshot.py` and `tmp/`. Profile: `deny_paths=(<b>,)`, `tmpdir=<b>/workers/w1/tmp`, FR-011 `read_ok`, cwd a separate temp dir (and a second case with the run dir under cwd, for R2-2).
  - Under `sandbox-exec -f`, env `HOME=<fake>`, `TMPDIR=<tmp>`, `PATH=dispatch.WORKER_PATH`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`/`GIT_COMMITTER_NAME`/`GIT_COMMITTER_EMAIL` set (fake HOME has no identity): `git init <tmp>/repo`, `git -C <tmp>/repo add -A`, `git -C <tmp>/repo commit --allow-empty -m t`. Assert rc 0 each.
  - `/bin/cat <b>/secret.txt` rc non-zero; `/bin/ls <b>` rc non-zero; `/bin/ls <b>/workers` rc non-zero; `/bin/cat <child>/snapshot.json` rc 0; `/usr/bin/touch <child>/snapshot.json` rc non-zero.
  - A profile-text unit test (no sandbox): the output holds `(allow file-read-metadata (literal "<b>/workers"))` and `(literal "<b>/workers/w1")`, holds no `file-read-data` allow, and emits nothing for a hole outside every deny root.
- Risk R2-1: metadata reads reveal that the ancestor folders exist and their mode and times. They hold no secret: the names are fixed (`workers/<id>`) and already in the Worker prompt.
- Risk R2-3: `/private/var` vs `/var` symlinks. Resolve both root and hole before comparing, as `_sb` does.
- Risk R2-4: Codex Workers. See the Codex bullet above; FR-011 does not apply to them (Codex already gets `pre_dispatch_snapshot.py` via `extra_read`, `:736-737`; `snapshot.json` is excluded under the broker by design).

### US3 (#109 item 1): one broker per run directory (FR-013 to FR-017)

Anchors (verified): `serve` `dispatch.py:2232-2304`; root check `:2238-2242`; inbox check `:2243-2246`; `_load_run_manifest` `:2248`; first `save()` `:2261`; `BROKER_USAGE` `:1607`.

- New `BROKER_LOCK = "broker.lock"` and `_take_broker_lock(root: Path) -> tuple[int | None, str | None]`:
  - `path = root / BROKER_LOCK`. `path.is_symlink()` or (exists and not regular file): return `(None, f"dispatch --serve: {path} must be a regular file")` (FR-015).
  - `fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)`; `OSError` with `ELOOP` is the same refusal (closes the check-then-open race).
  - `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)`. `BlockingIOError`: read up to 32 bytes, strip, keep only if all digits else `"unknown"`, close `fd`, return `(None, f"dispatch --serve: another broker holds {path} (pid {pid})")`; the `unknown` case prints `pid unknown` (FR-014 text: `(pid unknown)`).
  - On success: `os.ftruncate(fd, 0)`, write `str(os.getpid())`, `os.fsync`, return `(fd, None)`.
- `serve()`: call it after the inbox check (`:2246`) and before `_load_run_manifest` (`:2248`). On a message: print to stderr, return `BROKER_USAGE`. Nothing reads the inbox or writes `run.json` before this point (FR-014). Hold `fd` in a local; close it in a `finally` around the existing `try` (`:2260-2303`). Never unlink the file: unlinking lets a third broker lock a fresh inode while a second still holds the old one.
- FR-013 crash release: `flock` locks drop when the process dies; no pid liveness check needed.
- FR-016: Worker profiles already deny the whole Lead run dir (`_BROKER_DENY`, `:1962`, `:453-455`), so `broker.lock` is neither readable nor writable to a Claude Worker. The Codex Lead grant is `write_dir` read plus `write_dir/inbox` write (`runtime.py:135-139`), so `broker.lock` is read-only to the Lead. No code change; add assertions: `permission_profile(cwd, True, write_dir=d)` has no key for `d/broker.lock` with value `write`, and the Claude profile with `deny_paths=(d,)` has no `require-not` hole for `broker.lock`.
- Tests in `tests/test_dispatch_broker.py` (FR-017):
  - Hold the lock from the test on a second `os.open` fd with `flock` and pid `4242` written; `serve(run_dir, ...)` returns 2; stderr is `dispatch --serve: another broker holds <run>/broker.lock (pid 4242)`; `run.json` bytes unchanged; inbox request file still present (not set aside).
  - Same with garbage in the file: `(pid unknown)`.
  - Two real `serve()` calls: start one in a thread with a fake `sleep`/`clock` that keeps it polling until an `Event`; the second returns 2; set `lead.done`, join; a third `serve()` then starts and exits 0. `flock` is per open file description on macOS and Linux, so two fds in one process conflict [inferred; the existing `test_lock_exclusivity_real_flock`, `tests/test_ollama_adapter.py:414`, tests real `flock` exclusivity and is the model to copy].
  - `broker.lock` as a symlink: exit 2, message `must be a regular file`, link target untouched.
- Risk R3-1: the MCP transport (`agents_inc/install/mcp_broker.py`) runs a broker without `serve()`; two MCP brokers on one run dir stay possible. Not named in the spec; recorded as a follow-up candidate, not fixed.

### US4 (#109 item 2): control and bidi characters never reach a prompt (FR-018 to FR-021)

Anchors (verified): `render_dispatch.py` `main` `:297`, slots load `:333-337`, header path default `:341-342`; `dispatch.py` `run()` credential screen `:1261-1264`; `resume()` message screen `:1457-1463`; `_validate_fields` `:1723-1754` (credential screen `:1750-1751`); broker `reason_detail` `:1911-1914`; `plan_resume` message screen `:2149-2150`; `REQ_REFUSED` `:1608`; `EXIT_REFUSED` `:42`.

- Pattern (FR-018), defined twice with one test pinning equality:
  `CONTROL_CHAR_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f؜‎‏‪-‮⁦-⁩]")`
  in `render_dispatch.py` and in `dispatch.py`. Duplicated rather than loaded through `_load("render_dispatch", ...)` because a pinned checkout copy (025 US1) may predate the function.
- `control_char_hit(slots) -> tuple[str, str, int] | None` (key, `U+XXXX`, offset) in each file. Walk slot values: a `str` is scanned directly; a `list` or `dict` value (direct-path `GATES`, `BASH_ALLOW`) has each nested string scanned and reports the top-level key. Offset is the code-point index inside the string where the match sits. Format code point as `f"U+{ord(ch):04X}"`.
- `render_dispatch.py`: right after slots load (`:337`), on a hit print `render: slot <KEY> has control character U+<XXXX> at offset <n>` to stderr and return 2, before any output (FR-019).
- `dispatch.py` direct path: in `run()` right after the credential screen (`:1264`), print `dispatch: refused-control-char (slot <KEY> U+<XXXX>)` and return `EXIT_REFUSED`; no run dir exists yet (FR-020). `resume()`: after `:1463`, screen `{"MESSAGE": args.message}` the same way.
- Broker: `_validate_fields` returns `(None, "refused-control-char")` before the credential screen (`:1750`); `_handle_one` adds `reason_detail = "slot <KEY> U+<XXXX>"` the way `:1911-1914` does for credentials. `plan_resume`: return `(None, "refused-control-char")` after the oversize check (`:2148`). Result status stays `refused` with `REQ_REFUSED` (`:1921`).
- Tests (FR-021): `tests/test_dispatch_slot_screens.py` class `ControlCharTest`: for `\x00`, `‮`, `⁦`, `\x7f` in TASK: `dispatch.main` exit 3, stderr `refused-control-char (slot TASK U+0000)` etc., `--run-dir` parent empty; `_validate_fields` reason `refused-control-char`; `plan_resume` with the char in the message refused. Accept: TASK with `\t`, `\n`, `\r\n`; TASK with `é`, `日本`, `🙂`. Pattern equality: `dispatch.CONTROL_CHAR_RE.pattern == render_dispatch.CONTROL_CHAR_RE.pattern`. `tests/test_dispatch_cli.py`: one render case runs `render_dispatch.py` on a slots file with U+202E at offset 5, exit 2, exact stderr line, empty stdout.
- Risk R4-1: C1 controls (U+0080 to U+009F) and other format characters (U+2028, U+FEFF) are not in FR-018; they still pass. Recorded as checklist open item, not added.
- Risk R4-2: the ask_lead answer text (`answer_question`, `:2112`) reaches a Worker and is not screened by FR-020. Recorded as a follow-up candidate.

### US5 (#88 item 2): unreadable caveman file does not halt a delegate (FR-022 to FR-025)

Anchors (verified): `skills/workerbee/header.md:11` (CAVEMAN line), `:16` (report shape, `caveman: <ultra|not installed -> by hand>`); `skills/workerbee/QUICKREF.md:46`; `check_dispatch_prompt.py` `REPORT_KEYWORDS` `:71-73`, prompt keyword list element 1 `:52-53`; tests `tests/test_dispatch_header.py` (new assertion), `skills/workerbee/tests/test_template_revision.py:140-144` (report-profile case).

- `header.md:11`: after the "If the skill is absent" sentence add: "If the caveman skill file is installed but cannot be read (permission refused, sandbox), state `caveman unreadable -> checked by hand`, apply its rules by hand, and continue; an unreadable caveman file is not a block under the stop-on-block clause." Keep the existing sentences verbatim so `:52-53` still matches rendered prompts.
- `header.md:16`: declaration becomes `caveman: <ultra|not installed -> by hand|unreadable -> by hand>`.
- `check_dispatch_prompt.py:72-73`: add `"caveman: unreadable"`, `"caveman unreadable"`.
- `QUICKREF.md:46`: "Caveman absent or unreadable: the prompt says `caveman NOT installed -> checked by hand`; an unreadable skill file gets `caveman unreadable -> checked by hand` and is not a block."
- Tests: `tests/test_dispatch_header.py` asserts the rendered prompt contains `caveman unreadable -> checked by hand` and `not a block under the stop-on-block clause`; `test_template_revision.py` report-profile case with first line `caveman: unreadable -> by hand` returns no `caveman` miss.
- `skills/workerbee/SKILL.md:774` repeats the report declaration; D2 accepted, so it changes with header.md.

### US6 (#88 item 3): `--run-dir` works for read-only runs (FR-026 to FR-028)

Anchors (verified): `runtime.py` `permission_profile` `:122-139` (raise `:129-130`), `tools_for` `:102`, `run_codex` `:450`, `tools` resolved `:480`, raise `:483-484`; `tests/test_codex_tool_access.py:161` (`test_run_dir_only_write`), `:185` (`test_run_dir_needs_write`).

- `permission_profile`: delete `:129-130`. With `write=False`, `cwd` is already `read` (`:134`) and the `write_dir` block (`:135-139`) is unchanged, so the mapping equals the `write=True` one (FR-026).
- `run_codex`: replace `:483-484` with `if write_dir is not None and not tools: raise ValueError("--run-dir needs tools")` (FR-027). It sits after `tools = tools_for(...)` (`:480`), so `--no-tools` and a tools-off model both refuse.
- Tests: rename `test_run_dir_needs_write` (`:185`) to `test_run_dir_needs_tools`; add `permission_profile(cwd, False, write_dir=d) == permission_profile(cwd, True, write_dir=d)`; `run_codex` with `write_dir` and `write=False`, tools on, builds argv without raising (patch the launch the way `:161` does); `no_tools=True` with `write_dir` raises `--run-dir needs tools`.
- Risk R6-1: the CLI help or docs may still say `--run-dir` needs `--write`. a grep for `run-dir needs` over `agents_inc/`, `tests/`, `docs/` and `skills/**/*.md` found only the two runtime lines; no doc change.

## Cross-cutting

- `docs/DECISIONS.md`: append `## D68 — Metadata reads above sandbox holes; one broker per run dir; sandbox-refused binds skip (2026-10-24, status: accepted)` after D67 (`:688`), recording R1, R2, the #103 cause and the FR-009 metadata rule, and the broker lock rule (SC-006).
- `CHANGELOG.md`: six lines under `## [Unreleased]` (`:7`) / `### Fixed` (`:9`), ending `(#110)`, `(#103)`, `(#109)` (lock), `(#109)` (control chars), `(#88)` (caveman), `(#88)` (run-dir).
- Order in the implement run: US1 and US6 first (separate files), then US5 (docs and checker), US4, US3, US2 last (it needs the sandbox and touches `launch()`).
- Final gate: SC-001 two discover commands outside the sandbox; SC-002 two module runs inside it; SC-003 FR-012 test on macOS outside a sandbox; SC-005 scope verify.

## Departures from the spec

- D1: FR-012 names `tests/test_dispatch_grants.py`, but that module is not in the spec Scope list (spec line 11) and holds tool-grant tests, not sandbox-profile tests. The existing enforced-profile tests live in `tests/test_dispatch_broker.py:523-554` and `:736`, which is in scope. Plan puts the FR-012 test there. **CoS: accepted**; spec FR-012 now names this file.
- D2: `skills/workerbee/SKILL.md:774` carries the report declaration that FR-023 changes; it is not in Scope. **CoS: accepted**; the spec Scope list now includes that one line.
- D3: FR-012 says "skips when `sandbox_available()` is false"; plan also keeps the `sandbox_apply` stderr skip guard used by the existing tests, because `sandbox_available()` caches a probe and the guard costs nothing. **CoS: accepted.**
- D4: FR-011 adds a write deny on `read_ok` paths. The spec says "read (not write)" but names no deny; without it the run dir under cwd would be writable (risk R2-2). The deny also covers the D54 ask channel script and config. **CoS: accepted.**
- D5: FR-018 defines "slot value" without non-string values. Plan scans strings nested in list and dict slot values (`GATES`, `BASH_ALLOW` on the direct path) and reports the top-level key. **CoS: accepted.**

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `CONTROL_CHAR_RE` defined in two files | A pinned checkout copy of `render_dispatch.py` may lack the function | Loading it through `_load` breaks dispatch from an older checkout; a test pins equality |
