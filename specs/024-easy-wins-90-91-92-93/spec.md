<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-pipeline repo=agents_Inc session=spec024 -->
# Spec 024: easy wins for issues #90, #91, #92, #93

Branch: `development` (agents_Inc). Date: 2026-10-23.
Input: issue bodies #90, #91, #92, #93 (copies at `.scratch/spec024/issues/`), scope fixed by the Chief of Staff dispatch of 2026-10-23.

## Scope

Four independent small fixes. US2, US3 and US4 share no source file. US3 and US4 both touch `agents_inc/install/dispatch.py`, in different functions (`_verify` for US3, `resume`/`_status` for US4). Every story adds one `## [Unreleased]` line to `CHANGELOG.md`.

### US1: declare Python 3.11 as the floor (#90)

Python 3.10 reaches end of life in October 2026. CI tests only 3.11 (`.github/workflows/tests.yml:16`, `.github/workflows/portability.yml:13`), so the 3.10 claim is untested.

- FR-001: `pyproject.toml:10` reads `requires-python = ">=3.11"`.
- FR-002: The classifier `Programming Language :: Python :: 3.10` (`pyproject.toml:28`) is removed. No other classifier changes.
- FR-003: The README badge (`README.md:11`) reads `python-3.11+` with alt text `Python 3.11+`.
- FR-004: `README.md:48`, `AGENTS.md:23` and `docs/START-HERE.md:32` say "Python 3.11 or later".
- FR-005: `README.md` carries one note next to the requirements line: Python 3.10 support ends in the next release, and the current minor release stays installable on Python 3.10.
- FR-006: `CHANGELOG.md` `## [Unreleased]` gains a `### Removed` section with one line ending `(#90)`.
- FR-007: No file under `.github/workflows/` changes. No package is yanked.

### US2: the report lint accepts the contract's own gate line (#91)

The rendered REPORT SHAPE asks for `none, exit code N/A` when no gate ran, and EVIDENCE asks for a tag on each claim. `skills/workerbee/scripts/check_dispatch_prompt.py:172-173` then marks the line `verified-exit-without-code`. A second false positive: any `[verified]` line that uses the word "exit" in prose ("Exit gate needs 10 scored").

- FR-008: `EXIT_CODE_RE` accepts `exit code N/A` (case-insensitive), so `[verified] Gate commands: none, exit code N/A.` passes.
- FR-009: `VERIFIED_EXIT_RE` matches only command-result forms: `exit <n>` or `exits <n>`, `exited`, `exit code`, `rc=` or `rc:`. A bare word `exit` or `exits` with no number after it does not match.
- FR-010: A `[verified]` line that says `exited` or `exit code` with no code and no `N/A` stays flagged (`the gate exited cleanly [verified]`).
- FR-011: Tests in `skills/workerbee/tests/test_element1_conditional.py` cover the contract-mandated line (passes), the prose line `[verified] Exit gate needs 10 scored` (passes), and `the gate exited cleanly [verified]` (still flagged).
- FR-012: The existing assertion at `tests/test_dispatch_contract.py:262-263`, which expects `[verified] gate exit code N/A` to be flagged, is changed to expect a pass; FR-008 makes the old expectation wrong.

### US3: the snapshot verify gate needs no `cd` (#92)

- FR-013: `pre_dispatch_snapshot.py capture` records the repository top level as key `repo` (absolute path) in the snapshot JSON.
- FR-014: `pre_dispatch_snapshot.py verify <snap> [--repo <dir>] [--allow ...]` resolves the repository in this order: `--repo <dir>` (its git top level), then the snapshot's `repo` key, then the cwd's git top level (snapshots made before this change). A cwd outside any git work tree no longer exits 2 when `--repo` or the `repo` key is present.
- FR-015: `--repo` can appear before, between or after `--allow` groups. `--repo` without a value exits 2 with the usage text.
- FR-016: `render_dispatch.py` exits 2 when a non-blank `PRE_EXISTING_CHANGES` slot carries a backticked `pre_dispatch_snapshot.py` command that contains `&&` or starts with `cd `. The error names the slot and says to write one plain command. The default text (`default_pre_existing`, `render_dispatch.py:148-154`) is already one plain command and stays unchanged.
- FR-017: `agents_inc/install/dispatch.py` keeps the snapshot path absolute in the prompt (it is `run_dir.resolve() / "snapshot.json"`, `dispatch.py:1129,1137`) and passes `--repo <cwd>` to its own verify call in `_verify`, so the wrapper's gate does not depend on the subprocess cwd.
- FR-018: `skills/workerbee/SKILL.md` Step 7 (`### Step 7: Know the sandbox gotchas`, line 559) gains one bullet: do not commit while a delegate snapshot is live; if a commit is unavoidable, re-capture the snapshot and re-issue it to the delegate.
- FR-019: Tests in `skills/workerbee/tests/test_pre_dispatch_snapshot.py` cover verify from a cwd outside the repo with `--repo`, with the recorded `repo` key only, and `--repo` without a value (exit 2). A test in `skills/workerbee/tests/test_template_revision.py` covers the FR-016 refusal. A test in `tests/test_dispatch_cli.py` covers the FR-017 prompt form (absolute snapshot path, no `cd`, no `&&`).

### US4: `dispatch --resume <bare id>` searches every candidate parent (#93)

- FR-020: When `--resume` is a bare run id and `--run-dir` is not given, and `<default_parent(cwd)>/<id>/run.json` is missing, `resume()` tries `<cwd>/.scratch/agents-inc-runs/<id>`, `$CLAUDE_SCRATCHPAD/agents-inc-runs/<id>`, `$TMPDIR/agents-inc-runs/<id>`, `/tmp/agents-inc-runs/<id>`, in that order. It skips unset variables and paths already tried, and uses the first directory that holds `run.json`.
- FR-021: When no candidate holds `run.json`, stderr reads `dispatch: no run.json for <id> (searched: <p1>, <p2>, ...)`, listing every run directory tried, in order, and the exit code stays 2.
- FR-022: With `--run-dir` given, only `<run-dir>/<id>` is searched; the error still names it in the `(searched: ...)` form.
- FR-023: The dispatch status line (`_status`, `dispatch.py:919-923`) ends with ` (resume with --resume <absolute run dir>)`. `STATUS_RE` in `tests/test_dispatch_cli.py:22-24` accepts that suffix.
- FR-024: Tests in `tests/test_dispatch_resume.py` cover: the run found under `$TMPDIR` from a cwd whose `.scratch` is git-ignored; the error text listing every searched path; `--run-dir` limiting the search; the status-line suffix naming an absolute run directory.

## Clarifications

### Session 2026-10-23

No operator was attached. The Orchestrator Lead answered each question from the issue bodies, the code and canon, as the dispatch directs. `.specify/scripts/bash/check-prerequisites.sh` was not run: the Lead's Bash grants do not include `bash`.

- Q1 (#91): accept `N/A` after any exit word, or only in the form `exit code N/A`? → A: only `exit code N/A` (FR-008).
  Reason: the contract text is literally `none, exit code N/A` (the REPORT SHAPE item (d) quoted in issue #91). A looser rule (`exited N/A`, `rc=N/A`) would let a `[verified]` claim about a command that did run skip its code, which is what the rule exists to catch (`check_dispatch_prompt.py:171`, "A `[verified]` claim about an exit or gate result must carry the exit code it saw").

- Q2 (#91): the existing test `test_verified_exit_needs_code` (`tests/test_dispatch_contract.py:261-263`) asserts `[verified] gate exit code N/A` is flagged. Keep it or flip it? → A: flip that one assertion to expect a pass (FR-012).
  Reason: it directly contradicts FR-008, which the dispatch fixes as binding scope. The other three assertions in that test stay as they are and still hold under FR-009 and FR-010 (`exited cleanly` still flags; `rc=0; exited 1` and `[inferred] exit code not printed` still pass).

- Q3 (#92): when a hand-written `PRE_EXISTING_CHANGES` slot wraps the verify command in `cd <repo> && ...`, should the renderer rewrite it or refuse? → A: refuse with exit 2 (FR-016).
  Reason: AGENTS.md project rules say the dispatch gate "lints and rejects; it never rewrites text" (handoff lint gate, D41). With FR-014 the `cd` is no longer needed, so the fix for the slot author is to delete it.

- Q4 (#93): when the caller passes `--run-dir`, should resume still search the other candidate parents? → A: no (FR-022).
  Reason: `--run-dir` names the parent explicitly; the broker resumes children that way (`agents_inc/install/dispatch.py:1968`, `run_dir=str(child.parent)`), and a silent fallback there could resolve a different directory than the one the broker vouched for. The 022 trust checks key on the run directory name (`dispatch.py:1276-1278`), so the bare-id search stays safe, but the explicit form should not widen.

- Q5 (#93): suggest the absolute resume form on the status line itself, or on a second line? → A: a suffix on the same line (FR-023).
  Reason: the wrapper prints one status line per run (`dispatch.py:1015,1028` print `_status(...)` once), and the spec 022 ruling recorded in `docs/DECISIONS.md:678` already grew that line with `detail=`. A second line would break callers that read one line. `out=` already holds the run directory, but only as part of a file path; the suffix gives the copy-paste form.

## Success criteria

- SC-001: `python3 -m unittest skills.workerbee.tests.test_element1_conditional skills.workerbee.tests.test_pre_dispatch_snapshot tests.test_dispatch_resume tests.test_dispatch_contract tests.test_dispatch_cli tests.test_packaging` exits 0 and prints `OK`.
- SC-002: `grep -c '3\.10' pyproject.toml` prints `0`.
- SC-003: `grep -n 'N/A' skills/workerbee/scripts/check_dispatch_prompt.py`, `grep -n 'searched:' agents_inc/install/dispatch.py` and `grep -n -- '--repo' skills/workerbee/scripts/pre_dispatch_snapshot.py` each print at least one line.
- SC-004: `CHANGELOG.md` `## [Unreleased]` carries four new lines ending `(#90)`, `(#91)`, `(#92)`, `(#93)`.
- SC-005: the dispatch scope gate (`pre_dispatch_snapshot.py verify <run snapshot> --allow <FILES IN SCOPE>...`) exits 0.

## Out of scope

- Dropping 3.10 from CI (already untested), yanking or re-releasing a package.
- A run-id index under `~/.local/share/agents-inc` (#93 alternative).
- Rewriting the installed bundle; moving specs to DomI; committing.
- Other open issues and refactors beyond the four fixes.

## Assumptions

- A1: "the current minor stays installable on 3.10" means the already-published 0.4.x wheels keep `>=3.10`; only the next release carries `>=3.11`.
- A2: The `Python 3.10` comment at `tests/test_packaging.py:20` (a `tomllib` import fallback) is code history, not a support claim, and stays.
- A3: Old snapshots without `repo` keep working through the cwd fallback (FR-014).
