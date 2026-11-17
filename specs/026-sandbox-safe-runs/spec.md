<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-analyze repo=agents_Inc session=b8dceec1 -->
# Spec 026: delegated runs work inside the sandbox, plus broker hygiene

Branch: `development` (agents_Inc). Date: 2026-10-24.
Input: issue bodies #110, #103, #109, #88 (items 2 and 3); triage of #89, #87 and #88 (items 1 and 4) against commit `5f01dfe`. Operator rulings 2026-10-24: (R1) the #110 port-binding tests skip with a stated reason when binding is refused; they do not require `allowLocalBinding`. (R2) for #88 item 2, the prompt contract tells a delegate to apply caveman by hand when the skill file is unreadable; the Codex read-only sandbox is not widened.

## Scope

Seven stories. US0 is supervisor bookkeeping on GitHub and touches no code. US1 to US6 are small, fixed-scope code changes that share `agents_inc/install/dispatch.py`, `agents_inc/install/runtime.py`, `skills/workerbee/` and `tests/`. Every code story adds one `## [Unreleased]` line to `CHANGELOG.md` under `### Fixed`, ending with its issue numbers.

Files the code stories may edit (the implement dispatch's FILES IN SCOPE and the scope allow list are copied from this list): `agents_inc/install/dispatch.py`, `agents_inc/install/runtime.py`, `skills/workerbee/scripts/render_dispatch.py`, `skills/workerbee/header.md`, `skills/workerbee/slots.md`, `skills/workerbee/QUICKREF.md`, `skills/workerbee/SKILL.md` (the caveman declaration line only, US5), `CHANGELOG.md`, `docs/DECISIONS.md`, `tests/test_ollama_adapter.py`, `tests/test_bridge_thread_id.py`, `tests/test_dispatch_cli.py`, `tests/test_dispatch_broker.py`, `tests/test_dispatch_slot_screens.py`, `tests/test_codex_tool_access.py` (tests `permission_profile`), `tests/test_dispatch_header.py`, `skills/workerbee/scripts/check_dispatch_prompt.py`, `skills/workerbee/tests/test_template_revision.py`. A new test module is allowed only where the FR names it.

Out of scope: #51, #53, #73, #31 (features); #101 (Zenodo release flow); #86 (speckit-pipeline); #45 (prompt-chain lint); #19, #21 (research); any change to the broker request protocol or the `run.json` schema version; widening the Codex read-only sandbox (R2); any change to `pre_dispatch_snapshot.py`.

## Clarifications

### Session 2026-10-24

- Q: #103 fix route? → A (superseded by the next bullet): relocate `XDG_CONFIG_HOME`, per fable run `20261024T043655Z-fable-7293c5`, on the inferred `~/.config` cause.
- Q: (follow-up, same session) does the reproduction confirm the `~/.config` cause? → A: No. The CoS reproduction showed git passes with the `~/.config` deny and fails on metadata reads of the broker run directory's folders. FR-009 now allows metadata reads on those folders; the XDG relocation is dropped. `~/.gitconfig` includes no path under `~/.config` (`git config --global --list --show-origin`), so `GIT_CONFIG_GLOBAL` is moot.

### US0: triage the partly fixed dispatch issues (#89, #87, #88 items 1 and 4)

A grep on 2026-10-24 found code for most #89 findings (trusted snapshot copy 022 FR-001, `launch-failed`, `mirror_error`, `reason_detail`, `WB_CLAUDE_NOT_FOUND`, `refused-scope`, per-turn timeout, hook warnings) and for #87 item 1 / #88 item 4 (path-based credential screen, D67). The issues are still open.

- FR-001: The supervisor checks each numbered item of #89, #87 (items 1 to 5) and #88 (items 1 and 4) against the code at the spec's start commit and records, per item, `fixed` (with the commit or decision that fixed it and one file:line citation), `open` (one sentence on what is left), or `moved` (the issue or spec that now owns it).
- FR-002: The verdict table goes in `specs/026-sandbox-safe-runs/triage.md`.
- FR-003: For each issue whose items are all `fixed` or `moved`, the supervisor posts one comment (through the `comment-issue` skill) carrying the table rows for that issue and closes it with reason `completed`. For an issue with an `open` item, the supervisor posts the table and leaves the issue open; the comment lists only the open items as remaining scope.
- FR-004a: Known follow-up candidate (2026-10-24): the request text screen refused a read-only dispatch whose TASK named `~/.config/git` only to describe a design question, with reading forbidden (run refused before render, `slot TASK matched '~/.config/git'`). Recorded in `triage.md`; not fixed in this spec.
- FR-004: An item found `open` that fits this spec's scope (sandbox-safe runs, broker hygiene) is not added to this spec silently. The supervisor lists it in `triage.md` as a follow-up candidate.

### US1: the test suite runs inside the Claude Code sandbox (#110)

`tests/test_ollama_adapter.py` writes to fixed paths under `/tmp` (lines 264, 405, 411, 711). `tests/test_bridge_thread_id.py` binds a loopback port (`http.server.HTTPServer(("127.0.0.1", 0), ...)`, line 204 and the CodexBridgeServer setup), which the sandbox refuses with `PermissionError: [Errno 1] Operation not permitted`.

- FR-005: Every fixed `/tmp/...` path in `tests/test_ollama_adapter.py` is replaced with a path under a per-test temporary directory that the test creates and removes. No test in the module names `/tmp` literally afterwards, except in assertions about path text that never touch the filesystem.
- FR-006: In `tests/test_bridge_thread_id.py`, the first local bind of a test class (or module) is attempted once. When it raises `PermissionError`, every test that needs the socket is skipped with the reason `local port binding refused (sandbox); run outside the sandbox or set sandbox.network.allowLocalBinding` (R1). Any other bind error still fails the test.
- FR-007: A probe-bind helper used by FR-006 lives in the test module itself, not in production code.
- FR-008: Outside the sandbox the bridge tests still run and pass (no skip).

### US2: a broker Worker can run git-based test gates (#103)

A broker Worker runs under `claude_sandbox_profile` (`dispatch.py`). Its TMPDIR is `<child-run-dir>/tmp`, a hole inside the broker run directory, which the profile denies with `file-read* file-write*` (`deny_paths`). `file-read*` includes `file-read-metadata`, so a process cannot `lstat` the folders between the deny root and TMPDIR. `git init` resolves every parent of the new repository and dies: `fatal: Invalid path '<broker-run-dir>': Operation not permitted` (exit 128) [verified, CoS reproduction 2026-10-24, Apple git and Homebrew git 2.48.1]. The `~/.config` deny is not the cause: `git init` and `git commit` exit 0 under a profile with no `deny_paths` [verified, same reproduction]. Under the real profile, `skills.workerbee.tests.test_pre_dispatch_snapshot` plus `tests.test_dispatch_resume` give 21 errors; with metadata reads allowed on the ancestor folders, 0 errors (1 failure from the reproduction's location inside a git checkout, not from the profile). Separately, the Worker's prompt names `<run-dir>/pre_dispatch_snapshot.py` and `snapshot.json`, but the broker deny covers the run directory, so a Claude Worker cannot run its own FAILURE GATE check.

- FR-009: `claude_sandbox_profile` allows `file-read-metadata` (only) on each folder from a `deny_paths` root down to, not including, every hole it opens (the child TMPDIR, `write_ok`, `read_ok`), as `literal` paths. Folder contents stay unreadable (`ls` and `cat` under the broker run directory still exit nonzero) and unwritable. A broker Claude Worker can then run `git init`, `git add` and `git commit` in a fresh directory under its TMPDIR, and they exit 0. No grant is added under `~/.config`; `XDG_CONFIG_HOME` is not set (Clarifications). The implement run reports whether the Codex Worker profile (`runtime.permission_profile` with `extra_deny`) blocks the same metadata; any Codex fix is a follow-up, not part of this spec.
- FR-010: The Worker's TMPDIR stays the broker-owned `<run-dir>/tmp`. No grant is added for `/tmp`, `/private/tmp`, or `/var/folders` beyond what exists.
- FR-011: A broker Claude Worker can read (not write) its own run directory's `pre_dispatch_snapshot.py` and `snapshot.json`. The trusted snapshot copy (022 FR-001, 025) stays the copy that judges the run; the readable `snapshot.json` is informational for the Worker. The profile denies writes to every `read_ok` path explicitly, because a `read_ok` hole lifts the broker deny for writes too (plan D4); this also tightens the D54 ask channel files.
- FR-012: Regression test in `tests/test_dispatch_broker.py` (beside the existing sandbox-exec tests): build the Worker sandbox profile with a broker run directory in `deny_paths` and the child TMPDIR inside it, run `git init` + one commit under TMPDIR through `sandbox-exec`, assert exit 0; assert `cat` of a file in the broker run directory and `ls` of that directory still exit nonzero; assert a write to `snapshot.json` is still refused. The test skips with a stated reason when `sandbox_available()` is false (non-macOS, or already inside a sandbox).

### US3: one broker per run directory (#109 item 1)

Two `agents-inc dispatch --serve <run-dir>` processes on one run directory both start and both poll the inbox.

- FR-013: `serve()` takes an exclusive lock on a file `<run-dir>/broker.lock` before it polls the inbox and holds it for its lifetime. The lock is released by the operating system when the process exits, including on a crash, so a dead broker never leaves a stale lock.
- FR-014: A second `serve()` on the same run directory, while the first holds the lock, prints `dispatch --serve: another broker holds <run-dir>/broker.lock (pid <pid>)` to stderr and exits `BROKER_USAGE` (2) without reading the inbox or writing `run.json`. The pid is the one the holder wrote into the lock file; an unreadable pid prints `pid unknown`.
- FR-015: `broker.lock` is a regular file. A symlink at that path makes `serve()` refuse with exit 2, as the inbox check does.
- FR-016: The Lead sandbox profile and the Worker profiles never grant write on `broker.lock`.
- FR-017: Tests in `tests/test_dispatch_broker.py`: the second of two concurrent `serve()` calls exits 2 with that message and the first keeps running; after the first exits, a new `serve()` starts; a symlinked `broker.lock` is refused.

### US4: control and bidi characters never reach a prompt (#109 item 2)

Slot text with a NUL byte or U+202E reaches `prompt.md` unchanged.

- FR-018: Rendering refuses a slot value that contains a C0 control character other than tab (U+0009), line feed (U+000A) and carriage return (U+000D), or DEL (U+007F), or a Unicode bidirectional control: U+061C, U+200E, U+200F, U+202A to U+202E, U+2066 to U+2069. A list or dict slot value is screened string by string, and the refusal names the top-level slot key (plan D5).
- FR-019: `render_dispatch.py` exits 2 and prints `render: slot <KEY> has control character U+<XXXX> at offset <n>` for the first offending character. It writes no output.
- FR-020: `agents-inc dispatch` (direct path and broker `_validate_fields`) refuses the same slots before a run directory is created, with reason `refused-control-char`, exit `EXIT_REFUSED` (3) on the direct path and `REQ_REFUSED`-class status at the broker, and the detail `slot <KEY> U+<XXXX>`. `resume --message` text is screened the same way.
- FR-021: Tests (`tests/test_dispatch_slot_screens.py`, plus a render case in `tests/test_dispatch_cli.py`): a NUL, a U+202E, a U+2066, and a U+007F in a slot are each refused at render and at dispatch with the stated detail; a slot with tab, LF and CRLF line endings is accepted; a slot with ordinary non-ASCII text (`é`, `日本`, emoji) is accepted.

### US5: an unreadable caveman skill file does not halt a delegate (#88 item 2)

`skills/workerbee/header.md` line 11 covers a missing caveman skill. It does not cover a skill that is installed but unreadable in the delegate's sandbox (Codex read-only sandbox, `~/.codex/skills`). The stop-on-block clause then halts the delegate after reading no repo file.

- FR-022: The CAVEMAN line in `header.md` adds: when the caveman skill file cannot be read (permission refused, sandbox), the delegate states `caveman unreadable -> checked by hand`, applies the rules by hand, and continues. An unreadable caveman file is not a block under the stop-on-block clause (R2).
- FR-023: The report-shape declaration accepts `caveman: unreadable -> by hand` as a third value beside `ultra` and `not installed -> by hand`. The report checker accepts it: `REPORT_KEYWORDS["caveman"]` in `skills/workerbee/scripts/check_dispatch_prompt.py` gains `caveman: unreadable` and `caveman unreadable`.
- FR-024: `QUICKREF.md` "Caveman absent" line names the unreadable case in the same sentence.
- FR-025: `tests/test_dispatch_header.py` (or `skills/workerbee/tests/test_template_revision.py`, whichever pins `header.md` text) asserts the new clause; a report-profile test accepts a report whose first line is `caveman: unreadable -> by hand`.

### US6: `agents-inc run --run-dir` works for read-only runs (#88 item 3)

`runtime.permission_profile` and `run_codex` raise `--run-dir needs --write` (`runtime.py:130`, `runtime.py:484`). With `write_dir` set, cwd is already read-only and only `<run-dir>/inbox` is writable, so the `--write` requirement adds nothing.

- FR-026: `--run-dir` without `--write` is accepted. The grants are: cwd read, run directory read, `<run-dir>/inbox` write. They are byte-identical to the grants of `--run-dir --write` today.
- FR-027: `--run-dir` with `--no-tools` is still refused (no tools means no inbox writes); the message is `--run-dir needs tools`.
- FR-028: Tests in `tests/test_codex_tool_access.py`: `permission_profile(cwd, write=False, write_dir=d)` returns the same mapping as `write=True, write_dir=d`; `run_codex` with `--run-dir` and no `--write` builds argv without raising; `--run-dir --no-tools` raises with the new message.

## Success criteria

- SC-001: `python3 -m unittest discover -s tests -p 'test_*.py'` and `python3 -m unittest discover -s skills/workerbee/tests -p 'test_*.py'` pass outside the sandbox with no new skips against the T001 baseline skip count, not counting FR-012 tests that skip because `sandbox_available()` is false.
- SC-002: Inside the Claude Code sandbox, `python3 -m unittest tests.test_ollama_adapter` passes, and `python3 -m unittest tests.test_bridge_thread_id` reports skips with the FR-006 reason and zero errors.
- SC-003: The FR-012 test passes on macOS outside a sandbox.
- SC-004: `triage.md` exists with one row per item named in FR-001, and every closed issue has a comment carrying its rows.
- SC-005: A scope verify after implement shows edits only in the files listed under Scope, plus `specs/026-sandbox-safe-runs/`.
- SC-006: `docs/DECISIONS.md` gains D68 recording R1, R2, the FR-009 rule (a deny root grants metadata reads on the folders above each hole it opens, so path resolution works while contents stay hidden), and the broker lock rule.

## Key entities

- Broker lock: `<run-dir>/broker.lock`, regular file, holds the broker pid as text, locked exclusively for the broker's lifetime.
- Control-character refusal: reason `refused-control-char`, detail `slot <KEY> U+<XXXX>`.
- Caveman declaration values: `ultra`, `not installed -> by hand`, `unreadable -> by hand`.

## Assumptions

- The #103 root cause is confirmed (US2 intro). The CoS reproduction script is `<scratchpad>/repro103c.py` (session b8dceec1); the FR-012 test replaces it.
- Advisory file locking (POSIX `flock`/`fcntl`) is available on every supported host (macOS, Linux).
- Carriage return stays allowed in slots, so files with CRLF line endings keep working.
- The supervisor (CoS session) does US0 and posts GitHub comments; no delegate writes to GitHub.

## Final task

Move specs to DomI: `bash <DomI>/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`, run last.
