# Spec 019: easy wins for issues #56, #50, #46

Branch: `fix/easy-wins-56-50-46` (agents_Inc, off `development`). Date: 2026-10-09.
Input: Fable assessment, 2026-10-09 (cites checked by the supervisor).

## Scope

Three independent small fixes. They touch no shared files.

### US1: the report lint accepts a tagged WORKERS SPAWNED line (#56)

`WORKERS_LINE_RE` at `skills/workerbee/scripts/check_dispatch_prompt.py:81` rejects `[verified] WORKERS SPAWNED: 0.`. The workerbee contract asks for evidence tags on every claim, so a delegate that follows it fails the lint.

- FR-001: The lint accepts one optional leading `[verified]`, `[inferred]` or `[assumed]` tag before `WORKERS SPAWNED: <n>`.
- FR-001a: The dispatch wrapper's own parser, `WORKERS_SPAWNED_RE` at `agents_inc/install/dispatch.py:384` (used by `parse_workers_spawned`, `:387`, and the red reason `workers-spawned-missing`, `:401` to `:407`), accepts the same optional tag and still captures the integer. Without this the lint passes but the run stays red.
- FR-002: The lint still rejects a line with no number, for example `[verified] WORKERS SPAWNED: unknown`.
- FR-003: The rule that exactly one WORKERS line must appear stays the same.
- FR-004: Both `skills/workerbee/header.md:14` (the rendered EVIDENCE line every delegate reads) and `skills/workerbee/SKILL.md:673` (the canon tag rule) say the `WORKERS SPAWNED: n` line needs no evidence tag.

### US2: install never records a per-session shim as codex_path (#50)

`agents_inc/install/cli.py:68` resolves `codex` from PATH. Inside cmux, PATH starts with `$TMPDIR/cmux-cli-shims/<uuid>/`, so install can record a path that dies with the session.

- FR-005: `resolve_executable` skips PATH entries that sit under the temp root (`tempfile.gettempdir()`, compared both raw and resolved, because macOS `/var` resolves to `/private/var`) and entries where any path component ends in `-shims` (the cmux layout is `$TMPDIR/cmux-cli-shims/<uuid>/codex`, so the `-shims` directory is a grandparent, not the PATH entry itself). It takes the first match that is left. No environment override; the code never reads `TMPDIR` directly.
- FR-006: If only a skipped match exists, it uses that match and prints a warning to stderr.
- FR-007: `doctor` reports a warning (not an error code) when the recorded `codex_path` sits under `$TMPDIR` or a `*-shims` directory. The warning joins the existing `warnings` tuple, so `READY` still prints and the exit code stays 0.
- FR-007a: `repair` gets the fix for free: it calls the same `install()` function and therefore the same `resolve_executable` call. No separate change; one test asserts that `repair` with a shim-first PATH records the stable path.

### US3: `agents-inc run` gives a clear message for Claude aliases (#46)

`agents-inc dispatch` already sends Claude aliases to Claude (`agents_inc/install/dispatch.py:27`). `agents-inc run` handles Codex only and fails with `unknown Codex model alias: opus`.

- FR-008: When `run` gets an alias from `CLAUDE_MODELS`, it prints `Claude aliases go through: agents-inc dispatch --model <m> --effort <e> --cwd <d>` to stderr and exits 2.
- FR-009: `run` keeps its current Codex-only behavior for every other alias.
- FR-010: After merge to `development`, post one comment on #46 with the `comment-issue` template, pointing to `agents-inc dispatch` and to this fix. Close the issue when the deliverable is on the canonical branch (DomI git policy, "Close the loop").

## Success criteria

- SC-001: New tests cover FR-001, FR-001a, FR-002, FR-005, FR-006, FR-007, FR-007a and FR-008. The FR-001 and FR-002 tests live in `tests/test_dispatch_contract.py`, class `TestFanOutAndReport`. The FR-001a test lives in `tests/test_dispatch_cli.py` next to `test_parse_workers_spawned` (`:242`). The FR-005 and FR-006 tests live in `tests/test_install_runtime.py`. The FR-007 test lives in `tests/test_install_doctor.py`. The FR-007a test lives in `tests/test_install_cli.py`. The FR-008 test lives in `tests/test_install_cli.py`.
- SC-002: `python3 -m unittest discover -s tests -p 'test_*.py'` passes.

## Out of scope

- Making `run` dispatch Claude.
- Changing how a lint rejection affects the dispatch outcome (the second request in #56). That needs a ruling.
- Other open issues.

## Clarifications

Answered 2026-10-09 from the agents_Inc working tree and canon. Every file:line is in agents_Inc unless marked DomI.

- Q1 (#56): loosen the regex, add the tag exemption to the prompt text, or both?
  Answer: both (FR-001 and FR-004 stand).
  Reason: the lint is the only thing that rejects the line (`skills/workerbee/scripts/check_dispatch_prompt.py:81`, `WORKERS_LINE_RE`, and `:138`, which counts matches). The prompt contract is the thing that causes the tag: `skills/workerbee/SKILL.md:673` says "Tag every factual claim and conclusion" with the sole exemption being action-log lines. A regex-only fix leaves the contract contradicting itself; a prompt-only fix leaves old prompts and delegates that tag anyway failing. Both are needed and both are one-line edits.

- Q2 (#56): should a lint rejection of good content still turn the outcome red?
  Answer: out of scope; keep red.
  Reason: red comes from `agents_inc/install/dispatch.py:401` to `:407` (`_fan_out_check` returns `workers-spawned-missing` when `parse_workers_spawned` finds no line) and from the report lint at `:367` and `:522` to `:525`. D47 (`docs/DECISIONS.md:507` to `:517`) rules that "The 14-element check rejects; handoff-lint findings are advisory". Changing the reject to a warning overturns D47 and needs its own ruling. Fixing the regex removes the false red that motivated the question.

- Q3 (#50): skip `$TMPDIR`, `*-shims`, or both? Should an env override exist?
  Answer: both, no override (FR-005 updated).
  Reason: the cmux shim sits at `$TMPDIR/cmux-cli-shims/<uuid>/codex` (issue #50 evidence), so either rule alone catches it; both together catch a shim dir outside `$TMPDIR` and a temp dir not named `-shims`. `resolve_executable` (`agents_inc/install/runtime.py:60` to `:67`) already resolves with `shutil.which` on an explicit `search_path` argument, so the filter is a PATH-string pre-pass and needs no new knob. An operator who wants a specific binary can already order PATH (issue #50 workaround) and FR-006 keeps the shim as a last resort, so an override adds surface without a use case.

- Q4 (#50): should doctor give a warning or a hard error code?
  Answer: warning (FR-007 updated).
  Reason: `agents_inc/install/doctor.py:22` defines `warnings` as "non-fatal; never affects `ready` or the CLI exit code", and `:69` already treats an absent `codex_path` as a warning, while `:70` reserves the error code for a path that is missing or not executable. A shim that still exists works today; the risk is future, so it matches the drift warnings of D52 (`docs/DECISIONS.md:580`: "warnings on a separate line that leave the code list empty so READY still prints"). Code name: `WB_CLI_TEMP_PATH`.

- Q5 (#50): should `repair` re-resolve codex_path too, or only install?
  Answer: repair already re-resolves; no separate code change (new FR-007a).
  Reason: `agents_inc/install/cli.py:167` is `if args.command == "repair": return install(args)`, and `install()` calls `resolve_executable("codex", os.environ.get("PATH"))` at `:68` on every run unless `--without-codex` is passed (`:132` defines the flag for repair too). So a fix inside `resolve_executable` covers both commands. Add one test so a future refactor that splits the two paths cannot silently drop the fix.

- Q6 (#46): error only, or real Claude dispatch in `run`?
  Answer: error only (FR-008 stands, with stderr made explicit).
  Reason: Claude dispatch already exists in `agents_inc/install/dispatch.py:27` (`CLAUDE_MODELS`), `:145` to `:155` (`claude_argv`, with `--effort`), and `:320` to `:325` (`_kind` routes claude or codex); D47 (`docs/DECISIONS.md:515`) fixes that "Claude rungs launch through `claude -p` and Codex rungs through the existing `run_codex`". `run` is the raw Codex primitive (`agents_inc/install/cli.py:162` calls `run_codex` directly; `runtime.py:320`). Duplicating Claude dispatch into `run` would bypass the D47 lint, snapshot and ledger steps. Exit 2 is chosen because `cli.py:160` and `:165` use 1 for not-installed and config conflicts, so 2 distinguishes a usage error. Also update the issue (Q7): the "Impact" bullets about effort and ledger no longer hold for `dispatch`.

- Q7 (#46): post a comment on the issue pointing to `dispatch`?
  Answer: yes, once, after merge, with closure (new FR-010).
  Reason: #46 was written against release `5b67eb76` and says "Claude dispatches bypass agents-inc's ledger", which is stale since commit `51631c0` ("fix: pass --effort to Claude delegates in agents-inc dispatch", `git log -- agents_inc/install/dispatch.py`). DomI git policy (`~/Projects/DomI/.claude/policies/git.md:25`, "Close the loop") says the session closes an issue directly once the deliverable is on the canonical branch, with one verify-and-close comment. The `comment-issue` skill provides the template. One comment, not a running thread.

- Q8 (#56): put the tests in `tests/test_dispatch_contract.py`?
  Answer: yes, class `TestFanOutAndReport` (SC-001 updated).
  Reason: that file already imports the checker as `cdp` and holds the WORKERS line tests at `tests/test_dispatch_contract.py:237` to `:242` (`test_report_requires_one_integer_line`, which asserts `WORKERS SPAWNED: 0` passes and `unknown` fails). The new cases are the tagged twins of those lines. No other test file touches `check_report` (`grep -rln check_report tests` returns only this file).
