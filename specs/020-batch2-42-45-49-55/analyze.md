# Analyze: spec 020 against tasks.md and checklists/requirements.md

Date: 2026-10-09. Checked against agents_Inc at `7573b7e` (branch `feat/batch2-42-45-49-55`). All file:line cites are agents_Inc paths unless marked. Two operator amendments arrived during the pass (optional chain slots with derived defaults and user settings; the README tenet at `README.md:45`) and are folded into spec.md and tasks.md.

## Coverage

- Every FR has a task or an owner: FR-001/001a (T5), FR-001b (T7b), FR-002 (T5), FR-003/004 (T6), FR-005/006/007 (T8), FR-008 (T17), FR-009 (T15), FR-010 (T16), FR-011/011a (T18), FR-012/013/014 (T20), FR-015/017 (T10), FR-016/018 (T12), FR-019 (T13), FR-020/021/022 (T3), FR-023 (T2), FR-024 (Final, supervisor). No task lacks an FR.
- Spec cites re-run with `grep -n` / `sed -n` at `7573b7e`: `slots.md:17`, `:63-80`; `render_dispatch.py:32-47`, `:85`, `:128-132`, `:134-139`, `:154-156`; `check_dispatch_prompt.py:87-91`, `:134`, `:147`, `:196-203`, `:365`; `dispatch_rungs.py:8-18`; `dispatch.py:22-23`, `:25`, `:27`, `:77-89`, `:300`, `:429-430`, `:461`, `:478-482`, `:498`, `:527-533`, `:661`, `:751`; `host_ledger.py:18`, `:23-27`, `:51-106`, `:109-122`, `:129`, `:156-171`; `cli.py:86`, `:128`, `:132`, `:135`, `:147`, `:150`; `doctor.py:25-34`, `:44-57`; `bundle.py:16-19`, `:30`, `:41-53`; `pyproject.toml:48-56`; `MANIFEST.in:40-44`; `model_sync.py:10`, `:36`, `:246-252`; `codex-bridge/SKILL.md:260-263`, `:266`, `:290`; `at_route.sh:67`, `:86`, `:170-175`; `free_health.py:190-193`, `:208-209`; `README.md:45`, `:427`; tests named below. All resolve.

## Findings

### F1 CRITICAL: FR-018 status-line token breaks every launched-dispatch test

- Cite: `tests/test_dispatch_cli.py:19-20` `STATUS_RE` ends `outcome=(green|red)( reason=\S+)? out=\S+stdout\.md$` and `:130` asserts it on every launched run; D47 (`docs/DECISIONS.md:507-517`) says the wrapper "prints one status line". The run id, which FR-015 makes the node id, is already the second token of that line (`dispatch.py:429`).
- Edit: FR-018 and T12 no longer touch the status line. Done.

### F2 HIGH: `packages.find` cannot ship a `package-dir` mapped package (A3 was unproven)

- Cite: dry build in the scratch dir from `git archive HEAD` with setuptools 84.0.0. With `[tool.setuptools.packages.find]` (`pyproject.toml:48-49`) plus the two mappings: `pip wheel` exit 0, wheel listed 66 entries and zero files under `agents_inc/_skills` or `agents_inc/_docs`. With an explicit `packages = [...]` list: exit 0, 80 entries under the two data packages, and from an unzipped copy `importlib.resources.files("agents_inc._skills")` returned a `MultiplexedPath` whose `workerbee/SKILL.md` answered `is_file() == True`; `resources.files("agents_inc._docs") / "SCHEMA-3NF.md"` likewise. Also observed: `dispatch.REPO_ROOT` from the unzipped wheel is the site directory, which has no `skills/` (the #55 bug, reproduced).
- Side effect: a bare `**/*` glob shipped all nine `skills/*` directories (`codespace-exec`, `consensus-debate`, `doc-analysis`, `ollama-guard`, `speckit-pipeline`, ...), not the two the installer needs (`bundle.py:16`).
- Edit: FR-008 and T17 now require the explicit package list (every `agents_inc` subpackage: `install`, `adapters`, `hosts`, each with an `__init__.py`), globs limited to `workerbee/**/*` and `codex-bridge/**/*`, and `exclude-package-data` for `*/tests/**`; A3 rewritten as verified by the dry build. Done.

### F3 HIGH: the existing wheel test copies only two packages into its build tree

- Cite: `tests/test_packaging.py:28` `BUILD_INPUTS` and `:139-141` copy `agents_inc` and `workerbees` only; a `package-dir` target that is absent fails the build. `:156` asserts the top-level set is `{"agents_inc", "workerbees"}`, which the mapping preserves.
- Edit: T19 and SC-002 extend the copy with `skills/workerbee`, `skills/codex-bridge`, `docs/governance/SCHEMA-3NF.md`. Done.

### F4 HIGH: `--source` optional breaks the `source-checkout` record and doctor's hook-drift check

- Cite: `cli.py:86` `(paths.state / "source-checkout").write_text(str(Path(args.source).resolve()) + "\n")` raises on `None`. `doctor.py:30-32` (`_hook_drift`) reads that record and returns `WB_HOOK_DRIFT_UNCHECKED` when `<record>/skills/codex-bridge/scripts/at_route.sh` is not a file, so every pip install would warn on every `doctor`. `_install_stale` (`:44-57`) is safe: `stage_bundle` raises `ValueError("source checkout does not exist")` (`bundle.py:43`) and `:56` returns `[]`.
- Edit: FR-011 guards the write with the sentinel `packaged`; new FR-011a makes `_hook_drift` compare against `datafiles.repo_file(...)` for that sentinel; T18 gains the doctor tests. Done.

### F5 HIGH: FR-003 said ranks come from "the existing table", but the table has no role words

- Cite: `skills/workerbee/scripts/dispatch_rungs.py:14-18` `MODEL_RUNG` holds eight aliases only; `:8-13` `FAN_OUT_BY_RUNG` holds the four rung names. `operator`, `supervisor`, `CoS` appear nowhere.
- Edit: FR-003 and T6 keep aliases on `MODEL_RUNG` and add a small word-to-rank dict beside the rule. CHK006 holds for aliases. Done.

### F6 HIGH (amendment): derivation needs the delegate alias, the vendor, and the ladder order, none of which the renderer has today

- Cite: `dispatch.render` (`dispatch.py:77-89`) passes only `--slots`; `render_dispatch.py:85` parses `--slots`, `--header`, `--template`, `--contract-ref`. `MODEL_RUNG` has no vendor; vendor lives in `dispatch.py:25` (`CODEX_SLUGS`) and `:27` (`CLAUDE_MODELS`), which the standalone skill script cannot import (`check_dispatch_prompt.py:83-87` imports only `dispatch_rungs`). `default_fan_out` (`render_dispatch.py:32-47`) already shows the pattern: a `MODEL`/`RUNG` slot or a `MODEL_RUNG` hit in text.
- Edit: FR-001a adds `--model` to the renderer and to `dispatch.render`, and `LADDER` plus `ALIAS_VENDOR` to `dispatch_rungs.py` as the single source, with a test asserting agreement with `dispatch.py:25` and `:27`. T5 names the edit points. Done.

### F7 HIGH (tenet): a JSON settings file hand-written by the user violates `README.md:45`

- Cite: `README.md:45` "You do not hand-pick every model or write JSON." The amendment's settings file is `~/.config/agents-inc/settings.json` (`model_sync.py:36`), which today is written by command (`--set-mode`, `model_sync.py` argparse; `_update_settings` at `:246-249`), not by hand.
- Edit: FR-001b adds `agents-inc models chain [key=alias ...] [--clear]` on the existing `models` parser (`cli.py:135`, `:147`) writing through `_update_settings`; SC-000 proves `--model` alone renders a correct chain; a "Tenet check" section records that US2, US3, US4 add no user JSON or model picking. T7b added. Done.

### F8 MEDIUM: `tests/test_free_health.py` never runs under `unittest discover`

- Cite: `tests/test_free_health.py:3` `import pytest`, `:13` `pytestmark`, classes are plain (`:17`). `unittest discover` imports the module (pytest 9.1.1 is installed) and collects nothing. SC-005 would be "green" without running.
- Edit: SC-005, T1 and T21 name `python3 -m pytest tests/test_free_health.py -q`. Done.

### F9 MEDIUM: slots fixtures and the renderer under the amendment

- Cite: producers of slots: `skills/workerbee/tests/fixtures/example_slots.json:2` (ROLE names `haiku`), `tests/test_dispatch_header.py:21-37` `FULL_SLOTS` (ROLE names `haiku` and `opus`), `tests/test_dispatch_cli.py:55-61` `_slots()` reads the example. With optional slots none needs a change, but the ROLE text fallback must define which hit wins when two aliases appear.
- Edit: T7 turned from a fixture edit into a render check and tells the implementer to document the first-hit order. FR-006 updated. Done.

### F10 MEDIUM: `MANIFEST.in` line numbers moved under `7573b7e`

- Cite: `MANIFEST.in:40` `# <<< release-ignore:end`, `:43` `recursive-include agents_inc *.json`; the generated block (`:1-40`) says do not edit inside.
- Edit: T17 inserts after `:43`, never inside the block. Done.

### F11 MEDIUM: `repo_root()` must stay `parents[1]` even on pip, two call sites need it

- Cite: `dispatch.py:751` reads `REPO_ROOT / "agents_inc" / "models.json"`; `mcp_broker.py:22` inserts `parents[2]` on `sys.path`. In the unzipped wheel `parents[1]` is the site directory, which does contain `agents_inc/`.
- Edit: FR-009 defines `repo_root()` as `parents[1]` always and `repo_file` as `repo_root() / rel` when it exists, else packaged. Done.

### F12 LOW: `_package_data_matches` ignores the new keys

- Cite: `tests/test_packaging.py:39-52` builds keys only from directories under `agents_inc/`; `agents_inc._skills` and `agents_inc._docs` map elsewhere, so `:94` compares the same JSON set as before and still passes. Recorded in T17; no edit.

### F13 LOW: `ledger pending` output and dedupe

- Cite: `ledger.load` (`agents_inc/ledger.py:425-460`) dedupes by node id and applies later rows to the first; `record_return` (`:285`) appends a return row with the same `node_id`. A dispatch node keyed by run id therefore closes correctly with `append --run-id`. No edit.

### F14 LOW: `ALIAS_VENDOR` duplicates knowledge held in `dispatch.py:25-27`

- The renderer is a standalone script and cannot import `agents_inc`; the agreement test in SC-001 is the guard. Recorded; LESSON-CANDIDATE for the dispatcher: the alias tables now live in three places (`dispatch_rungs.py`, `dispatch.py`, `routing.json`).

## Checklist

All twelve items ticked in `checklists/requirements.md`. Notes: CHK003 holds with the US4 lead-in sentence marking the file release as the operator's; CHK006 holds for aliases (F5); CHK011 holds through `tests/test_packaging.py:100-115` (skip below setuptools 77, `build_meta` fallback without pypa build).

## Cycle log

- Cycle 1: F1-F14 found; F1-F11 edited into spec.md and tasks.md; checklist ticked. Two operator amendments folded (F6, F7).
- Cycle 2: re-read spec.md and tasks.md; every FR maps to a task (FR-001b -> T7b, FR-011a -> T18), every task to an FR; new cites (`render_dispatch.py:85`, `dispatch.py:498`, `MANIFEST.in:40-43`, `model_sync.py:246-252`, `cli.py:135`, `README.md:43-47`) re-run. No new CRITICAL or HIGH.

OPEN CRITICAL/HIGH: 0
