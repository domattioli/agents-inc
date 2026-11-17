# Analyze: spec 019 against tasks.md

Date: 2026-10-09. Checked against the agents_Inc working tree on branch `fix/easy-wins-56-50-46`. All file:line cites are agents_Inc paths unless the path starts with `specs/`.

## Coverage

- Every FR has a task: FR-001/002 (T1, T2), FR-003 (T2), FR-004 (T3), FR-005/006 (T4, T5), FR-007 (T6), FR-007a (T7), FR-008/009 (T8, T9), FR-010 (Final note, supervisor). No task lacks an FR.
- Spec cites re-checked with `grep -n` / `sed -n`: `check_dispatch_prompt.py:81` and `:138`, `cli.py:68`, `:132`, `:160`, `:162`, `:165`, `:167`, `runtime.py:60-67`, `doctor.py:22`, `:69-70`, `dispatch.py:27`, `:145-155`, `:320-325`, `:367`, `:401-407`, `:522-525`, `test_dispatch_contract.py:237-242`, `SKILL.md:673`. All resolve.

## Findings

### F1 CRITICAL: a second WORKERS regex in dispatch.py still turns the run red

- Cite: `agents_inc/install/dispatch.py:384` `WORKERS_SPAWNED_RE = re.compile(r"^\W*workers spawned:\s*(\d+)\W*$", re.IGNORECASE | re.MULTILINE)`; `:387-390` `parse_workers_spawned` uses it; `:401-407` returns `workers-spawned-missing` when it finds nothing. Issue #56 reports exactly `outcome=red reason=workers-spawned-missing`.
- Problem: spec US1 and T2 change only `check_dispatch_prompt.py:81`. After that fix the report lint passes but `parse_workers_spawned` still returns None for `[verified] WORKERS SPAWNED: 0.`, so the outcome stays red. The bug in the issue title is not fixed.
- Edit: add FR-001a (dispatch.py regex accepts the same optional tag; keep the `(\d+)` capture group) and T2b (regex edit plus a `tests/test_dispatch_cli.py` case next to `:242-244`). Keep SC-001 in step.
- Status: fixed in spec.md (FR-001a, SC-001) and tasks.md (T2b).

### F2 HIGH: FR-007 as written breaks an existing doctor test

- Cite: `tests/test_doctor_codex_optional.py:39-43` `test_present_executable_codex_ready` places codex inside `tempfile.TemporaryDirectory()` and asserts `r.warnings == ()`. A temp-path warning fires there.
- Edit: T6 must either patch `tempfile.gettempdir` in that test or move that fixture's codex outside the temp root; and the production check must use `tempfile.gettempdir()` so a test can patch it.
- Status: fixed in tasks.md (T6).

### F3 HIGH: T4 test design cannot pass as written

- Cite: T4 says PATH = `<tmp>/x-shims:<real>` with `<real>` from a temp dir. Any `tempfile.TemporaryDirectory()` is under the temp root, so `<real>` is itself skipped by the `$TMPDIR` rule and the function falls to the warning branch; the "stable" assertion fails. Also `tempfile.gettempdir()` caches in `tempfile.tempdir` (stdlib behaviour), so setting `TMPDIR` in `os.environ` inside a test does nothing after the first call.
- Edit: tests patch `tempfile.gettempdir` (or set `tempfile.tempdir`) to `<tmp>/t` and put `<real>` at `<tmp>/real`, outside the patched root; production code calls `tempfile.gettempdir()` once per call, never reads `TMPDIR` directly. Compare both the raw and `Path.resolve()`d forms (macOS `/var` is a symlink to `/private/var`).
- Status: fixed in tasks.md (T4, T5) and spec.md (FR-005 wording).

### F4 HIGH: T9 guard position and T8 test fixture are underspecified

- Cite: `agents_inc/install/cli.py:160` returns 1 when the receipt is missing, `:161` loads the receipt, `:162` is one expression that evaluates `_efforts(paths.current.resolve())` before `run_codex` runs. A guard placed after `:162` never runs; a test with no receipt gets exit 1, not 2, and a test with no `current` symlink raises before the guard.
- Cite: `agents_inc/install/dispatch.py:300` imports `_efforts, _paths` from `.cli` lazily; `cli.py:5-13` imports nothing from `dispatch`. A top-level `from .dispatch import CLAUDE_MODELS` in cli.py is safe today but fragile; import inside the `run` branch.
- Edit: T9 says: guard sits after `:161` and before the `run_codex` call; import `CLAUDE_MODELS` inside the branch. T8 says: patch `cli._paths` to a temp home, write a receipt, create `paths.current`, and patch `cli.run_codex` and `cli._efforts` for the FR-009 case. Decide whether the guard should run before the receipt check (#46 users with no install get a usage message): keep it after, so behaviour for a missing install is unchanged.
- Status: fixed in tasks.md (T8, T9).

### F5 HIGH: FR-004 and T3 leave header.md conditional, but it carries the rule

- Cite: `skills/workerbee/header.md:14` is the rendered EVIDENCE line ("Tag each [verified], [inferred], or [assumed]. Action-log lines ... need no tag."); `:17` is the rendered FAN-OUT CAP line that demands `WORKERS SPAWNED: n`. `agents-inc dispatch` renders prompts from header.md, so the delegate sees header.md, not SKILL.md.
- Edit: FR-004 and T3 name both files; the exemption sentence goes in header.md:14 (what delegates read) and SKILL.md:673 (canon).
- Status: fixed in spec.md (FR-004) and tasks.md (T3).

### F6 MEDIUM: T7 repair test needs a codex-enabled install, which no fixture has

- Cite: `tests/test_install_cli.py:54` the only repair test passes `without_codex=True`; `cli.py:68` resolves codex only when that flag is false.
- Edit: T7 states the fixture: copy the RepairTest fixture, set `without_codex=False`, patch `os.environ["PATH"]` to `<tmp>/x-shims:<tmp>/real` with executable fake `codex` files in both, patch `tempfile.gettempdir` to `<tmp>/t`, call `cli.install(args)` twice (install then repair) and assert `InstallReceipt.load(paths.receipt).codex_path == (<tmp>/real/codex).resolve()`.
- Status: fixed in tasks.md (T7).

### F7 MEDIUM: doctor warning placement must not fire on an absent or broken path

- Cite: `doctor.py:69` None -> warning `WB_CLI_NOT_FOUND`; `:70` missing/non-exec -> error code. A temp-path check that runs on every receipt would add `WB_CLI_TEMP_PATH` on top of an error.
- Edit: T6 says the check runs only in the branch where the path exists and is executable (an `else` after `:70`).
- Status: fixed in tasks.md (T6).

### F8 LOW: regex correctness check for T2

- Cite: proposed `^\W*(?:\[(?:verified|inferred|assumed)\]\s*)?workers spawned:\s*\d+\W*$`. Trace on `[verified] WORKERS SPAWNED: 0.`: `^\W*` first eats `[`, the tag group then fails at `v`, the engine backtracks `\W*` to empty, the tag group matches `[verified] `, the rest matches `WORKERS SPAWNED: 0.`. `check_dispatch_prompt.py:138` applies `ln.strip()` first, so leading spaces are fine. Tagged `unknown` still fails (`\d+`). No edit; recorded so the implementer does not "simplify" `\W*` away, which would reject `- WORKERS SPAWNED: 0` (tested at `tests/test_dispatch_cli.py:243`).

### F9 LOW: `-shims` rule matches only the immediate parent directory

- Cite: cmux layout `$TMPDIR/cmux-cli-shims/<uuid>/codex` (issue #50). The directory named `*-shims` is the grandparent of the binary, not the PATH entry itself.
- Edit: FR-005 wording: skip a PATH entry when any path component ends in `-shims`. Fixed in spec.md and T5 (treated as part of F3's rewrite).

### F10 LOW: existing runtime test will hit the fallback branch

- Cite: `tests/test_install_runtime.py:28-33` places codex under `tempfile.TemporaryDirectory()` and asserts the resolved path. Under FR-005 that entry is skipped, the fallback returns the same path, the assertion still holds; only a `WARN` line reaches stderr. No edit required; the implementer may patch `gettempdir` there to keep test output quiet.

## Cycle log

- Cycle 1: F1-F9 found; F1-F7 and F9 edited into spec.md and tasks.md.
- Cycle 2: re-read both artifacts; every FR still has a task (FR-001a -> T2b), every task has an FR, every cite above re-run with `grep -n`. No new CRITICAL or HIGH.

OPEN CRITICAL/HIGH: 0
