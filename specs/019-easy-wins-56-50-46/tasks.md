# Tasks: spec 019

Implementer: Sonnet (Workhorse). Repo: agents_Inc, branch `fix/easy-wins-56-50-46`. Write each test first, then make it pass. Standard library only. Line numbers are from the tree at dispatch time; re-run `grep -n` before editing.

## Plan

- #56: two regex changes (the report lint and the dispatch wrapper's parser) and one sentence in two contract files.
- #50: a PATH pre-filter inside `resolve_executable`, plus one doctor warning, plus one existing doctor test made temp-root independent.
- #46: one guard in the `run` branch in `cli.py`.
- No shared files across the three stories. Order: T1–T3, T4–T7, T8–T9, T10.

## US1 (#56)

- T1: In `tests/test_dispatch_contract.py`, class `TestFanOutAndReport` (existing WORKERS tests at `:237`–`:242`), add tests. A report whose line is `[verified] WORKERS SPAWNED: 0.` passes the report lint. A report whose line is `[verified] WORKERS SPAWNED: unknown` fails (FR-001, FR-002).
- T2: In `skills/workerbee/scripts/check_dispatch_prompt.py:81`, change `WORKERS_LINE_RE` to `^\W*(?:\[(?:verified|inferred|assumed)\]\s*)?workers spawned:\s*\d+\W*$` (case-insensitive). Keep the leading `\W*`: `- WORKERS SPAWNED: 0` must still pass. Leave the count logic near `:138` alone (FR-003).
- T2b: In `tests/test_dispatch_cli.py`, next to `test_parse_workers_spawned` (`:242`–`:244`), add: `dispatch.parse_workers_spawned("[verified] WORKERS SPAWNED: 2.\n")` returns 2. Then in `agents_inc/install/dispatch.py:384`, change `WORKERS_SPAWNED_RE` to `^\W*(?:\[(?:verified|inferred|assumed)\]\s*)?workers spawned:\s*(\d+)\W*$` with the same flags. The capture group `(\d+)` stays; `findall` at `:389` relies on it (FR-001a).
- T3: In `skills/workerbee/header.md:14` (the rendered EVIDENCE line) and `skills/workerbee/SKILL.md:673` (the canon tag rule), add one sentence: the `WORKERS SPAWNED: n` line needs no evidence tag. Both files carry the rule; edit both (FR-004).

## US2 (#50)

- T4: In `tests/test_install_runtime.py`, class `RuntimeTest` (existing resolution test at `:28`–`:35`), add tests with fake executable files (`write_text("#!/bin/sh\n")`, `chmod(0o755)`). Patch `tempfile.gettempdir` (for example `mock.patch("agents_inc.install.runtime.tempfile.gettempdir", return_value=str(tmp / "t"))`; do not set `TMPDIR` in the environment, `gettempdir` caches). Put the stable binary at `<tmp>/real/codex`, outside the patched root. Case 1: PATH = `<tmp>/t/codex-dir:<tmp>/real`, result is `(<tmp>/real/codex).resolve()`. Case 2: PATH = `<tmp>/x-shims/abc:<tmp>/real`, result is the real path (component rule, not only the immediate parent). Case 3: PATH = `<tmp>/x-shims/abc` only, result is the shim path and stderr (capture with `contextlib.redirect_stderr`) contains `WARN`. (FR-005, FR-006)
- T5: In `agents_inc/install/runtime.py` `resolve_executable` (`:60`–`:67`; `tempfile` is already imported at `:7`), split `search_path` on `os.pathsep`, drop entries where the entry (raw or `Path(entry).resolve()`) is under `Path(tempfile.gettempdir())` (raw or resolved) or where any `Path(entry).parts` element ends with `-shims`. Run `shutil.which` on the kept entries first; on no hit, run it on the full `search_path` and print `WARN: <name> resolved to a temporary or shim path <path>; put the stable directory first on PATH` to stderr. Keep the existing `FileNotFoundError` text when nothing matches.
- T6: In `tests/test_install_doctor.py`, add a test: a receipt whose `codex_path` is an executable file under the patched temp root gives warning `WB_CLI_TEMP_PATH`, `ready` stays true, and `codes` stays empty. In `agents_inc/install/doctor.py`, add the check as an `else` branch after the existing `codex_path` checks (`:69`–`:70`), so it runs only when the path exists and is executable; use the same under-temp-root or `-shims`-component rule as T5 (import or share one helper from `runtime.py`). Then update `tests/test_doctor_codex_optional.py:39`–`:43` (`test_present_executable_codex_ready`): it puts codex under `tempfile.TemporaryDirectory()` and asserts `warnings == ()`, so patch `tempfile.gettempdir` there to a directory that does not contain the fixture, or assert `WB_CLI_TEMP_PATH` is the only warning. (FR-007)
- T7: In `tests/test_install_cli.py`, class `RepairTest` (fixture at `:43`–`:56`), add a test with `without_codex=False`: patch `os.environ["PATH"]` to `<tmp>/x-shims/abc:<tmp>/real` with executable fake `codex` files in both, patch `tempfile.gettempdir` to `<tmp>/t`, patch `cli._paths`, call `cli.install(args)` twice (install, then the repair path, which is `cli.py:167` `return install(args)`), and assert `InstallReceipt.load(paths.receipt).codex_path == (<tmp>/real/codex).resolve()` after each call (FR-007a).

## US3 (#46)

- T8: In `tests/test_install_cli.py`, add a test that calls `cli.main([...])` with `cli._paths` patched to a temp home that has a saved `InstallReceipt` (see `:34` for a constructor example) and a `paths.current` symlink (any directory; `_efforts` is patched). Case 1: `run --model opus --effort low --cwd <tmp>` returns 2 and stderr contains `Claude aliases go through: agents-inc dispatch --model opus --effort low --cwd`. Case 2: with `cli.run_codex` patched to return 0 and `cli._efforts` patched to `{}`, `run --model luna --cwd <tmp>` calls the patched `run_codex` once and returns 0 (FR-008, FR-009). Note `cli.py:160` returns 1 with no receipt; the test needs the receipt or it proves nothing.
- T9: In `agents_inc/install/cli.py`, inside `main`, after the receipt load at `:161` and before the one-line `run` call at `:162`: `if args.command == "run": from .dispatch import CLAUDE_MODELS` (import inside the branch; `dispatch.py:300` imports from `cli` lazily, so keep this one lazy too); if `args.model in CLAUDE_MODELS`, print `Claude aliases go through: agents-inc dispatch --model {args.model} --effort {args.effort} --cwd {args.cwd}` to stderr and return 2. The guard must sit before `:162` because that one expression evaluates `_efforts(paths.current.resolve())` before `run_codex` runs.

## Final

- T10: `python3 -m unittest discover -s tests -p 'test_*.py'` passes. No commit, no push.
- FR-010 (the issue comment) is the supervisor's job after merge. Not the implementer's.
