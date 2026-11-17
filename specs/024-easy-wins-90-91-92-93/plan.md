<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-pipeline repo=agents_Inc session=spec024 -->
# Plan: spec 024 (issues #90, #91, #92, #93)

Spec: `specs/024-easy-wins-90-91-92-93/spec.md`. Repo: agents_Inc, branch `development`. Line numbers are from the working tree on 2026-10-23; re-run `grep -n` before each edit.

## Technical context

- Python 3.11+ after US1, standard library only, `unittest` tests. No new modules, no new dependencies.
- Setup script `.specify/scripts/bash/setup-plan.sh` was not run: the Lead's grants do not include `bash`. Paths were resolved by hand.
- research.md, data-model.md, contracts/ and quickstart.md are folded into this file. The batch adds one JSON key (`repo` in the snapshot) and three CLI or text forms; each is defined below. The `SPECKIT` marker step does not apply: this is not a DomI run.

## Constitution check

- P1 repo-scoped writes: every write is under agents_Inc, in the dispatch FILES IN SCOPE. Tests use temp dirs and patched environment variables only.
- P3 no self-graded gates: each Worker diff is read and its gate command is rerun by the Lead.
- P4 deterministic policy: US2 and US3 change regexes and argument parsing, not prompt text alone.
- P8 prompt contract: each Worker slot carries its own GATES, FILES IN SCOPE and STOP RULE.
- P9 surgical edits: no file is rewritten whole.
- Result: no violation.

## Design per story

### US1 (#90) — docs and metadata only

Files: `pyproject.toml:10,28`, `README.md:11,48`, `AGENTS.md:23`, `docs/START-HERE.md:32`, `CHANGELOG.md`.
- The README note sits directly after `README.md:48`: "Python 3.10 support ends in the next release; the current 0.4 release stays installable on Python 3.10."
- `CHANGELOG.md`: add `### Removed` under `## [Unreleased]`, after `### Added`.
- Acceptance: `grep -c '3\.10' pyproject.toml` prints `0` (exit 1); `python3 -m unittest tests.test_packaging` exits 0.

### US2 (#91) — two regexes

File: `skills/workerbee/scripts/check_dispatch_prompt.py:171-173`.
- `VERIFIED_EXIT_RE`: keep the two-sided shape (`[verified]` before or after), with the exit part narrowed to `\b(?:exits?\s*[=:]?\s*-?\d+|exited\b|exit\s+code\b|rc\s*[=:])`.
- `EXIT_CODE_RE`: keep the current numeric form and add an alternative `\bexit\s+code\s*[=:]?\s*N/A\b`.
- Decision record: rejected exempting the whole contract line by text match (the #58 approach for `WORKERS SPAWNED`), because the gate line has no fixed prefix in real reports.
- Tests: `skills/workerbee/tests/test_element1_conditional.py`, new class `TestVerifiedExitLine`; flip `tests/test_dispatch_contract.py:262-263`.
- Acceptance: `python3 -m unittest skills.workerbee.tests.test_element1_conditional tests.test_dispatch_contract` exits 0.

### US3 (#92) — verify `--repo`, render refusal, dispatch `--repo`, SKILL.md bullet

Files: `skills/workerbee/scripts/pre_dispatch_snapshot.py`, `skills/workerbee/scripts/render_dispatch.py`, `agents_inc/install/dispatch.py` (`_verify`, about `:792-795`), `skills/workerbee/SKILL.md:559-570`.
- Snapshot JSON gains `"repo": <absolute git top level>` (written by `capture`).
- `main()` parses `--repo <dir>` anywhere after the snapshot path. Resolution in `main()`: `--repo` → `git -C <dir> rev-parse --show-toplevel`; else the snapshot's `repo` key if it is a directory; else the cwd top level (today's behavior). `os.chdir(top)` stays. Usage docstring gains the flag.
- `render_dispatch.py`: after the PRE_EXISTING_CHANGES default fill, find backticked spans in the slot that contain `pre_dispatch_snapshot.py`; any span with `&&` or a leading `cd ` prints `PRE_EXISTING_CHANGES invalid: write the verify gate as one plain command (no cd or &&); verify reads the repo from the snapshot` to stderr and returns 2.
- `dispatch.py` `_verify`: `args = ["verify", snap_file, "--repo", str(cwd)]`.
- SKILL.md Step 7: one new bullet after the commit bullet (`:564-566`).
- Tests: `skills/workerbee/tests/test_pre_dispatch_snapshot.py` (capture records `repo`; verify from a temp cwd outside the repo with `--repo`; with the recorded key only; `--repo` with no value exits 2); `skills/workerbee/tests/test_template_revision.py` (render refusal); `tests/test_dispatch_cli.py` (dry-run prompt: the PRE-EXISTING CHANGES verify command has an absolute snapshot path and no `cd `/`&&`).
- Acceptance: `python3 -m unittest skills.workerbee.tests.test_pre_dispatch_snapshot skills.workerbee.tests.test_template_revision tests.test_dispatch_cli tests.test_dispatch_contract` exits 0.

### US4 (#93) — resume search and status suffix

File: `agents_inc/install/dispatch.py` (`resume`, about `:1263-1270`; `_status`, `:919-923`).
- New helper `_resume_candidates(cwd, run_id, run_dir_arg) -> list[Path]`: with `run_dir_arg`, `[Path(run_dir_arg).resolve() / id]`; else `default_parent(cwd)/id`, then `cwd/.scratch/agents-inc-runs/id`, `$CLAUDE_SCRATCHPAD/agents-inc-runs/id`, `$TMPDIR/agents-inc-runs/id`, `/tmp/agents-inc-runs/id`, deduplicated by resolved path (the first form seen is kept and printed as built, so `/tmp/...` stays `/tmp/...` on macOS), unset or empty variables skipped.
- `resume()`: the absolute-or-path branch is unchanged. For a bare id, take the first candidate with `run.json`; none → `dispatch: no run.json for <id> (searched: <p1>, <p2>, ...)` to stderr, exit 2.
- `_status`: append ` (resume with --resume <run dir>)`, where the run dir is `out_path.parent` resolved (absolute).
- `tests/test_dispatch_cli.py:22-24` `STATUS_RE`: allow `( \(resume with --resume /\S+\))?` before `$`.
- Tests: `tests/test_dispatch_resume.py`, new class `ResumeSearchTest` (temp git repo with ignored `.scratch`, run under patched `$TMPDIR`; error lists every path; `--run-dir` limits the search; `_status` suffix is absolute).
- Acceptance: `python3 -m unittest tests.test_dispatch_resume tests.test_dispatch_cli` exits 0.

## Order and shared files

- US3 and US4 both edit `agents_inc/install/dispatch.py` and `tests/test_dispatch_cli.py`. Run them one after the other (US4 after US3), never in parallel.
- US1 and US2 share only `CHANGELOG.md` with the rest. The Lead writes all four CHANGELOG lines, so Workers do not touch it.
- Final gate: the dispatch SUCCESS GATE unittest command plus the three greps, then the snapshot verify command.
