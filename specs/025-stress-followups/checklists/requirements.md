<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-checklist repo=agents_Inc session=f26522 -->
# Requirements Quality Checklist: spec 025, dispatch follow-ups

**Purpose**: check that the spec 025 requirements are complete, clear, consistent and testable before implement. Items test the requirements, not the code.
**Created**: 2026-10-23
**Feature**: `specs/025-stress-followups/spec.md`
**Depth**: standard. **Audience**: the Executive, before implement. Answered by the Orchestrator (opus), no operator attached. An open box means the requirement fails the item; the analyze.md finding is named.

## Requirement completeness

- [x] CHK001 Does every in-scope issue (#104, #85, #87 item 1, #105, #106, #107, #108) map to a user story with numbered FRs? [Completeness, Spec Scope, US1 to US6]
- [x] CHK002 Does the spec name every file the stories edit? [Gap, Spec Scope] Scope names `dispatch.py`, `render_dispatch.py` and `CHANGELOG.md`; FR-014 edits `skills/workerbee/slots.md`, Assumptions edit `docs/DECISIONS.md`, FR-003 forces `tests/test_dispatch_failloud.py:191`. Analyze F7, F8.
- [x] CHK003 Are all script load sites that judge a run covered by FR-002? [Gap, Spec FR-002] `lint_prompt`, `render`, `parse_fan_out`, `_run_gates` and the verifier copy at `dispatch.py:1196` also load from `SCRIPTS`. Analyze F5.
- [x] CHK004 Is the fate of the existing #95 true-positive tests stated (`show the token`, `print access_token`, `no .env reads`)? [Gap, Spec FR-006, tests/test_dispatch_slot_screens.py:110,123-124,134-135] Analyze F4.
- [x] CHK005 Is the broker-child path for US5 stated? [Completeness, Spec FR-020]
- [x] CHK006 Is the no-repo and no-git case for US4 stated? [Completeness, Spec FR-015]
- [x] CHK007 Is resume of a legacy `run.json` without `scripts_dir` specified? [Gap, Spec FR-002] "Never re-derived" leaves no value. Analyze F9.

## Requirement clarity

- [x] CHK008 Is "a read verb within the same line" defined as adjacent or anywhere earlier on the line? [Ambiguity, Spec FR-006] Analyze F3.
- [x] CHK009 Are the checkout probe paths, the symlink rule and the `REPO_ROOT` exclusion exact? [Clarity, Spec FR-001]
- [x] CHK010 Is every refusal message given verbatim? [Clarity, Spec FR-011, FR-015, FR-023]
- [x] CHK011 Is the accepted verify-gate argv given position by position? [Clarity, Spec FR-022]
- [x] CHK012 Is the reason defined when a gate both fails its exit code and writes to the repo? [Ambiguity, Spec FR-018] Analyze F6.
- [x] CHK013 Is the outcome defined when the second verify returns `TAMPERED` or `ERROR:` rather than `CHANGED`? [Ambiguity, Spec FR-018] Analyze F6.

## Requirement consistency

- [x] CHK014 Do FR-006 (`_HOME_CRED` unchanged) and FR-008 case 1 (rendered Worker boilerplate, which names `~/.claude/**`, `~/.codex/**`, `~/.local/**`) agree? [Conflict, Spec FR-006, FR-008, skills/workerbee/header.md:15] No. Analyze F2.
- [x] CHK015 Do FR-006 (read verb `open` before `.env` matches) and FR-008 case 2 (`Never open .env.` accepted) agree? [Conflict, Spec FR-006, FR-008] No. Analyze F3.
- [x] CHK016 Does Q2's stated aim (a delegate cannot point the probe at a planted copy) hold when the delegate edits the regular file in its own cwd? [Conflict, Spec Q2, FR-001; Constitution P3] No. Analyze F1.
- [x] CHK017 Do FR-003's status-line position and the existing `STATUS_RE` agree once FR-003 updates it? [Consistency, Spec FR-003, tests/test_dispatch_cli.py:23-26]
- [x] CHK018 Does FR-023's message keep the `PRE_EXISTING_CHANGES invalid` prefix spec 024 tests assert? [Consistency, Spec FR-023]
- [x] CHK019 Does FR-015's exit 2 agree with the exit map (`EXIT_USAGE` 2, `EXIT_REFUSED` 3)? [Consistency, Spec FR-015, dispatch.py:42] It is a usage error, not a policy refusal; consistent with the 022 map.

## Scenario and edge-case coverage

- [x] CHK020 Is the direct-path screen's effect on ordinary Executive slots stated (for example CONSTRAINTS `no ~/.claude writes`, TASK citing `~/.local/bin/agents-inc`)? [Coverage, Spec FR-011] Analyze F2.
- [x] CHK021 Is `--run-dir` equal to `--cwd` covered? [Edge Case, Spec FR-015] Implied: relative `.` is not ignored, so refused.
- [x] CHK022 Is a gate writing a file listed in FILES IN SCOPE covered? [Edge Case, Spec FR-018] Same allow list, so accepted.
- [x] CHK023 Is a fake checkout that has the two probe files but lacks `render_dispatch.py`, `dispatch_rungs.py` or `pre_dispatch_snapshot.py` covered? [Edge Case, Spec FR-001] Probe checks two files, loads four. Analyze F5.
- [x] CHK024 Is the `<snapshot>` placeholder exempt from the `<`/`>` rule? [Edge Case, Spec FR-022]

## Acceptance criteria

- [x] CHK025 Does every FR have a named test file? [Measurability, Spec FR-005, FR-010, FR-013, FR-017, FR-021, FR-024; FR-014 by grep in tasks T008]
- [x] CHK026 Does SC-001 run every test file the stories change? [Traceability, Spec SC-001] It omits `tests.test_dispatch_failloud`, which FR-003 breaks. Analyze F8.
- [x] CHK027 Is SC-004's CHANGELOG suffix list identical to the Scope rule? [Traceability, Spec Scope, SC-004]

## Dependencies and assumptions

- [x] CHK028 Is the fake-delegate harness assumption checked against the test file? [Assumption, Spec Assumptions] `tests/test_dispatch_cli.py:41-76` holds `_git_repo` and `_slots`.
- [x] CHK029 Is the next DECISIONS number derivable? [Assumption, Spec Assumptions] Last is D66 (`docs/DECISIONS.md:684`), so D67.

## Notes

- 29 items: 16 pass, 13 open. Each open item names its analyze.md finding.
- Cycle 2 (2026-10-23): the Executive's rulings (spec.md "Analyze resolutions") close all 13 open items: CHK002 by F7/F8, CHK003 by F5, CHK004 by F4, CHK007 by F9, CHK008 by F3, CHK012 and CHK013 by F6, CHK014 by F2, CHK015 by F3, CHK016 by F1, CHK020 by F2, CHK023 by F5, CHK026 by F8. Marked `[x]`; 29 of 29 pass.
