<!-- provenance: author=domattioli model=opus effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=spec041-lead -->
# Tasks: Terminology, one name per thing

**Input**: `spec.md` and `plan.md` in this directory; findings in `analyze.md` applied.
**Repository**: all paths are relative to `/Users/domattioli/Projects/agents-inc`.
**Tests**: required; tests come before the edits they guard.
**Authorization**: the D-041 decision entry is proposed. Implement runs only when the operator authorizes it; T025 asks the operator to accept the entry.

## Format: `[ID] [P?] [Story] Description`

- [P]: parallel-safe (different files, no dependency on an open task).
- Each task names its files, the FR or SC it serves, and its check command.
- No task renames a code enum, JSON key, flag, settings key or env var. The only data change is T018; the only code-file changes are prompt-text string literals in T012.
- "D-041 (number N)" means the decision entry; N is reserved in T000.

## Phase 0: Reserve

- [ ] T000 Reserve the decision number N: the next free number after the newest `^## D(\d+)` heading in `docs/DECISIONS.md` (D82 today). Record N in the run spec. Serves FR-014. Check: `grep -oE '^## D[0-9]+' docs/DECISIONS.md | tail -1` prints D(N-1).

## Phase 1: Setup

- [ ] T001 Create `tools/retired_terms.json` with the pattern rows, replacements, `row` names and allowlist from plan.md "Lint design" (allowlist includes `tests/fixtures/**`, `fixtures/**`, `skills/*/tests/**`); set `cutoff_decision` to `null`. Depends on T000. Serves FR-013. Check: `python3 -c "import json;json.load(open('tools/retired_terms.json'))"` exits 0.

## Phase 2: Tests first (US2, blocking)

- [ ] T002 [P] [US2] Create fixtures in `tests/fixtures/041/`: `bad_<row>.md` per pattern row (one seeded alias each, including "one rung up" and a sentence-start "Supervisor"), `good_generic.md` ("primary driver", sentence-start "Driver" in plain English, "code owner", "Free Tier", "a cheap check", "the supervisor verifies", "lead to", "delegate this task", fenced code and an inline code span containing `Supervisor`), `decisions_cutoff.md` (synthetic entries D900 and D901, alias in each; test cutoff 901). Serves FR-013, SC-004. Check: `ls tests/fixtures/041 | wc -l` at least 10.
- [ ] T003 [US2] Write `tests/test_check_terms.py`: each bad fixture, passed by explicit path, exits 1 and prints file, line, word, replacement; good fixture exits 0; cutoff fixture flags only D901; allowlisted path ignored (fixture dirs included); table cross-check (every pattern `row` exists in the CONTEXT.md term table, every alias marked `lint` has a pattern, `review-only` aliases need none, each alias in exactly one row); real-tree run exits 0 (expected to fail until T021). Depends on T001, T002. Serves FR-001, FR-013, SC-003, SC-004. Check: `python3 -m unittest tests.test_check_terms` runs; fixture tests fail before T005.
- [ ] T004 [US1] Add class `CanonShape` to `tests/test_check_terms.py`: CONTEXT.md Orchestrator row has no "dispatches" or "family" (SC-008); DELEGATION-MODEL.md has at least one "Guest agent" (SC-006); CEO in CONTEXT.md and DELEGATION-MODEL.md only in chain figure, role list, CEO entry or "CEO and CoS", path mentions exempt (SC-007); Rung row has no "cost and capability class only" (FR-006); CoS row first sentence names dispatch of the Lead, verify, commit (FR-007); no Driver row and no Tier row (FR-011). Depends on T003 (same file). Serves FR-006, FR-007, FR-008, FR-011, FR-012, FR-017. Check: `python3 -m unittest tests.test_check_terms.CanonShape` runs (fails until Phase 4).

## Phase 3: Lint script (US2)

- [ ] T005 [US2] Write `tools/check_terms.py` per plan.md: scans tracked `.md` files via `git ls-files '*.md'`, skips the allowlist, fenced code and inline code spans; splits `docs/DECISIONS.md` on `^## D(\d+)` and lints entries at or after `cutoff_decision`; exempts the term-table retired column; prints `path:line: word -> replacement`. Tune the Owner, Driver and Tier context patterns until `good_generic.md` passes. Depends on T001, T003. Serves FR-013. Check: `python3 -m unittest tests.test_check_terms` fixture tests pass (real-tree and CanonShape tests may still fail).

## Phase 4: Canon edits (US1, US3, US4)

- [ ] T006 [US1] `CONTEXT.md`: add the canonical term table from spec.md with the `lint` and `review-only` marks and the operator and CEO rule sentence; rewrite rows Worker (line 10), Lead (32), Delegate (new), supervisor (new, "the CoS or a Lead"). Remove Lead aliases Supervisor, Orchestrator and Worker aliases Workhorse, Grunt, Team, Delegate. Depends on T005. Serves FR-001, FR-002, FR-003, FR-005. Check: `grep -nE 'aliases? (Supervisor|Delegate)' CONTEXT.md` prints nothing.
- [ ] T007 [US3] `CONTEXT.md`: rewrite Rung (48) per FR-006 and drop "(aka Supervisor)"; rewrite Orchestrator (31) as rung only and move its dispatch and depth sentence to Lead (32), family rooting to Family (30); rewrite CoS (34) opening per FR-007; Second opinion (49) "A Supervisor" to "The supervisor". Depends on T006. Serves FR-004, FR-006, FR-007, FR-017, SC-008. Check: `python3 -m unittest tests.test_check_terms.CanonShape` CONTEXT tests pass.
- [ ] T008 [US4] `CONTEXT.md`: CEO row (42) as chain position, add operator row; Team (60) D63 only; Chief (61) as label, proposed; remove the Driver row (8) and list Driver as a retired alias in the CoS row; remove the Tier row (23), Tier stays a retired alias in the Rung row; Host (7) and Stdin worker (9) scoped. Depends on T007. Serves FR-008, FR-009, FR-011, SC-002. Check: `grep -nE '^\| \*\*(Driver|Tier)\*\*' CONTEXT.md` prints nothing.
- [ ] T009 [US1] `docs/governance/DELEGATION-MODEL.md`: Roles list per term table (Lead and Worker aliases removed, Owner removed, Delegate and supervisor lines), CEO only in chain positions, line 69 "flash-tier triage helper" to "Grunt-rung triage helper", one Guest agent sentence outside the chain. Depends on T006. Serves FR-003, FR-008, FR-010, FR-012, SC-002, SC-006, SC-007. Check: `grep -c 'Guest agent' docs/governance/DELEGATION-MODEL.md` at least 1 and `grep -c 'Owner' docs/governance/DELEGATION-MODEL.md` prints 0.
- [ ] T010 [P] [US1] `docs/governance/ROUTING-RANKING.md`: rung table "Orchestrator / Supervisor" to "Orchestrator"; keep the D34 history note and add "Supervisor retired as synonym (D-041)"; "A Supervisor compares" to "The supervisor compares". Depends on T006. Serves FR-004, FR-005, SC-001. Check: `grep -n 'Orchestrator / Supervisor' docs/governance/ROUTING-RANKING.md` prints nothing.

## Phase 5: Skills, prompt text, human docs (US1, US5)

- [ ] T011 [P] [US5] `skills/workerbee/SKILL.md`: ultra-tier (lines 73, 237-238) and flash-tier (510, 526) to rung names; Supervisor title and rung uses to Orchestrator or lowercase supervisor; Interlocutor to CoS; line 634 "The dispatcher" to "The supervisor"; line 943 "one rung up" to "one level up the chain". Depends on T005, T006. Serves FR-004, FR-005, FR-010, SC-001, SC-002. Check: `python3 tools/check_terms.py skills/workerbee/SKILL.md` exits 0.
- [ ] T012 [P] [US1] Prompt text, relational "dispatcher" to "supervisor", strings only:
  - `skills/workerbee/header.md` line 17 ("ask your dispatcher"), line 19 ("relay them one rung up to your dispatcher" to "relay them to your supervisor"), line 20 ("your dispatcher may continue you");
  - `skills/workerbee/slots.md` lines 47, 48 ("hand back to the dispatcher");
  - `skills/workerbee/scripts/render_dispatch.py:37` string literal "stop and hand back to the dispatcher";
  - `tests/test_dispatch_schema_131.py:252` the same expected string;
  - `skills/workerbee/tests/fixtures/example_slots.json:4` the `CONSTRAINTS` string.
  Render a sample prompt and lint it. Depends on T005. Serves FR-005, FR-016. Check: `git grep -n -i 'dispatcher' -- skills/workerbee tests` prints no relational use, `python3 -m unittest tests.test_dispatch_schema_131` passes, and `python3 skills/workerbee/scripts/check_dispatch_prompt.py <rendered sample>` exits 0.
- [ ] T013 [P] [US1] `skills/workerbee/QUICKREF.md`: keep relational "supervisor"; line 55 "relays one rung up" to "relays one level up the chain"; fix any rung alias or CEO prose use. Depends on T005. Serves FR-005, FR-008. Check: `python3 tools/check_terms.py skills/workerbee/QUICKREF.md` exits 0.
- [ ] T014 [P] [US5] `skills/codex-bridge/SKILL.md` line 237: "ultra-tier" (2) to "Executive-rung". Depends on T005. Serves FR-010, SC-002. Check: `grep -c 'ultra-tier' skills/codex-bridge/SKILL.md` prints 0.
- [ ] T015 [P] [US1] `skills/speckit-pipeline/SKILL.md`: Orchestrator and Supervisor role uses to Lead or supervisor; frontier as rung to Executive. Depends on T005. Serves FR-003, FR-010, SC-001. Check: `python3 tools/check_terms.py skills/speckit-pipeline/SKILL.md` exits 0.
- [ ] T016 [P] [US4] `README.md`, `docs/HOW-IT-WORKS.md`, `docs/START-HERE.md`, `mods/delegate-pane/README.md`, `AGENTS.md`: role aliases to canonical words; CEO in prose to operator (path mentions such as `docs/governance/CEO-BRIEF.md` stay); leave component "dispatcher" (HOW-IT-WORKS.md:419) and price words. Depends on T005. Serves FR-003, FR-008, FR-011, SC-007. Check: `python3 tools/check_terms.py README.md docs/HOW-IT-WORKS.md docs/START-HERE.md mods/delegate-pane/README.md AGENTS.md` exits 0.
- [ ] T017 [P] [US5] Sweep remaining current `.md` hits reported by `python3 tools/check_terms.py` (for example `docs/EXTENDING.md`, `docs/governance/OPERATING-GOVERNANCE.md`, `docs/governance/ASSESSMENT.md`, `scripts/statusline.d/SPEC.md`) for tier, frontier, cheap, mid used as rung names. Depends on T011 to T016. Serves FR-010, FR-011. Check: `python3 tools/check_terms.py` lists no file outside the DECISIONS cutoff region.

## Phase 6: Data value (US1)

- [ ] T018 [US1] Confirm no test asserts the old name: `git grep -n 'Orchestrator Supervisor'` prints only `agents_inc/governance.json:25`. Then change that `name` value to `"Supervisor"`; leave `id` and `type`. Serves FR-015, SC-005. Check: `python3 -m unittest tests.test_policy tests.test_gateway tests.test_governance_negatives` passes and `git diff --stat -- agents_inc/` shows only `governance.json` with 1 line changed.

## Phase 7: Decision entry and final gates

- [ ] T019 Verify no identifier or logic change. Allowed changed non-`.md` files: `tools/check_terms.py`, `tools/retired_terms.json`, `tests/test_check_terms.py`, `tests/fixtures/041/*`, `agents_inc/governance.json` (T018), `skills/workerbee/scripts/render_dispatch.py`, `tests/test_dispatch_schema_131.py`, `skills/workerbee/tests/fixtures/example_slots.json` (T012). In the last four, the diff touches string literal content only. Serves FR-015, FR-016, SC-005. Check: `git diff --name-only | grep -vE '\.md$'` lists only the allowed files, and `git diff -U0 -- skills/workerbee/scripts/render_dispatch.py tests/test_dispatch_schema_131.py` shows only lines inside string literals.
- [ ] T020 Append the D-041 entry (number N from T000, confirmed still free) to `docs/DECISIONS.md` per plan.md outline with status "proposed"; record Q2 and Q6 as CoS rulings under operator delegation; list the prompt-wording changes from T012 and the follow-ups from spec.md. Set `cutoff_decision` in `tools/retired_terms.json` to N. Depends on T006 to T019. Serves FR-014, FR-016, FR-018. Check: `python3 tools/check_terms.py docs/DECISIONS.md` exits 0 and `grep -n "^## D$N " docs/DECISIONS.md` shows "status: proposed".
- [ ] T021 Run the real-tree lint and full suite. Depends on T020. Serves FR-013, SC-001, SC-002, SC-003, SC-004. Check: `python3 tools/check_terms.py` exits 0 and `python3 -m unittest discover -s tests -p 'test_*.py'` exits 0.
- [ ] T022 Measure SC baselines against results: `git grep -c 'ultra-tier\|flash-tier' -- '*.md'` limited to current docs prints 0; `grep -c 'Guest agent' docs/governance/DELEGATION-MODEL.md` at least 1; CanonShape tests pass. Serves SC-001, SC-002, SC-006, SC-007, SC-008. Check: `python3 -m unittest tests.test_check_terms` exits 0.
- [ ] T023 Cross-vendor review (D46.10, hard separation 2) of all canon edits (T006 to T017, T020) by sol; same-vendor review of T001 to T005, T012 code strings and T018 by opus. Record verdicts in the ledger. Serves FR-014, FR-016. Check: review verdict file in the run directory shows no open CHANGES.
- [ ] T024 Write the follow-up list into the run spec handoff: out of repo (constitution P2, P3, P10; `~/.claude/AGENTS.md`; installed copy via `agents-inc repair`) and in repo (draft an issue for user-visible strings in `.py` and `.ts` files, for example `mods/delegate-pane/hooks/rungs.ts`, `frames.ts`, that carry retired words; draft only, filed by the CoS). No edits outside the repo. Serves FR-018. Check: `git -C /Users/domattioli/Projects/DomI status --porcelain` shows no change outside the run spec file.
- [ ] T025 Ask the operator to accept the proposed D-041 entry: the CoS presents it as a DECIDE item with the Q2 and Q6 rulings marked for veto. On acceptance the CoS changes the status line; on rejection the work stays unmerged. Depends on T021 to T024. Serves FR-014. Check: the operator's reply is recorded in the run spec; `docs/DECISIONS.md` status reads "proposed" until then.

## Dependencies

- T000 before T001. T001 before T002 to T005. T003 before T004 (same file). T004 and T003 before T005 and Phase 4.
- T005 before T006; T006 before T007, T008, T009, T010. T005 before Phase 5.
- Phases 4 to 6 and T019 before T020; T020 before T021, T022; T021 before T023; T021 to T024 before T025.
- Parallel groups: {T002} with T001 done; {T010, T011, T012, T013, T014, T015, T016}.

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 | T003, T006 |
| FR-002 | T006 |
| FR-003 | T006, T009, T015, T016 |
| FR-004 | T007, T010, T011 |
| FR-005 | T006, T010, T011, T012, T013 |
| FR-006 | T004, T007 |
| FR-007 | T004, T007 |
| FR-008 | T004, T008, T009, T013, T016 |
| FR-009 | T008 |
| FR-010 | T009, T011, T014, T015, T017 |
| FR-011 | T004, T008, T016, T017 |
| FR-012 | T004, T009 |
| FR-013 | T001, T002, T003, T005, T021 |
| FR-014 | T000, T020, T023, T025 |
| FR-015 | T018, T019 |
| FR-016 | T012, T019, T020, T023 |
| FR-017 | T004, T007 |
| FR-018 | T020, T024 |
| SC-001 | T010, T011, T015, T021, T022 |
| SC-002 | T008, T009, T011, T014, T021, T022 |
| SC-003 | T003, T021 |
| SC-004 | T002, T003, T021 |
| SC-005 | T018, T019 |
| SC-006 | T009, T022 |
| SC-007 | T009, T016, T022 |
| SC-008 | T007, T022 |
