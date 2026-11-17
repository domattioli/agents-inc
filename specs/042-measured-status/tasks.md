<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Tasks: Measured status

**Input**: Design documents from `specs/042-measured-status/` (spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md, evidence.md).
**Prerequisites**: plan.md and spec.md. Where plan.md and spec.md differ, spec.md wins (see "Spec versus plan notes").
**Tests**: Requested. The spec asks for tests per requirement (SC-001 to SC-008), so every phase writes its tests first, and each test must be seen failing before the code it proves is written.

**Organization**: One task phase per plan phase, numbered 0 to 5 as in plan.md. Each phase ships alone: it ends with the full suite, the DECISIONS.md entry for the phase, and a closing comment task for the issues the phase touches.

## Format: `- [ ] TNNN [P?] [Story?] Description with exact paths. FR: ids. Test: the test that proves it.`

- **[P]**: The task touches no file that another task in the same phase touches, so it can run beside them once its own prerequisites are done.
- **[USn]**: The user story in spec.md: US1 verdicts (Phase 1), US2 claims (Phase 2), US3 doctor (Phase 3), US4 refusal wording (Phase 4), US5 refusal on action (Phase 5). Phase 0 has no story tag, because it files upstream issues and serves FR-033 only.
- **OPERATOR**: needs an operator decision or action. **OPERATOR-APPROVAL**: an external write (an issue comment or an issue filed on GitHub) that a supervisor must not run without the operator's approval.
- Paths are relative to `/Users/domattioli/Projects/agents-inc`.
- Task ids T072 to T083 were added 2026-11-15 after the red-team (T072 to T076 in Phase 2, T077 to T083 in Phase 5).
- Task ids T068 to T071 were added after the first analysis. They sit inside their phase, so ids are not in file order. Ids never change.

## Conventions every task follows

- Python standard library only. No model call in any check. $0 incremental spend. `WORKERBEES_GOVERNANCE` stays off by default.
- The full suite command is `python3 -m unittest discover -s tests -p 'test_*.py'`.
- A task that runs `agents-inc` runs it in its own Bash call, alone. Write any slots file in the call before it. The dispatch hook denies a call that combines a dispatch command with other commands.
- A delegate that writes code touches only the files named in its task. Existing exit codes 0, 1, 2, 3, 69, 75 and 130 keep their meaning; only exit code 4 for `unverified` is new.
- Outcome words and reason codes follow `contracts/verdict-reason-codes.md`. Role words follow D83: operator, supervisor (a relation), delegate, Lead, Worker, Executive, Orchestrator, Workhorse, Grunt.
- A delegate never accepts its own output. A supervisor runs the phase's suite task and checks the result.

## Skipped steps (speckit-tasks outline)

- Step 1 (`.specify/scripts/bash/check-prerequisites.sh --json`): skipped, because `.specify/scripts/bash/` does not exist. The feature directory `specs/042-measured-status/` and its files were found by listing the directory.
- `.specify/extensions.yml` before_tasks and after_tasks hooks: not checked and no hooks run; no extension hooks apply to this run.

## Spec versus plan notes

- Plan Phase 2 says the decision entry is an item in D84 or a separate entry at the next free number, and Phase 3 says the next free number. The phase tasks below take the next free number at the time they run: D84 for Phase 1 (the next free number today), and for every later phase either a new entry at the next free number or, for Phase 2, an item in the open proposed entry. Later entries are identified by title ("Claims block", "doctor items and READY", "Screens decide on requested action"), never by a hardcoded number after D84. The supervisor checks `docs/DECISIONS.md` for the real next number before each decision task and verifies an entry by its title.
- Plan Phase 4 names no decision entry. This file still adds a decision task for Phase 4, so the ending of each phase is uniform: it records a note in the open proposed entry rather than a new ruling; when no proposed entry is open, T057 creates one at the next free number ("Refusal wording").
- research.md R4 once named a contract `contracts/report-block.md`; it now names the existing `contracts/claims-block.md`, which tasks cite.
- Plan Phase 1 says "#87 item 5 needs Phase 2" and Phase 2 closes #87 item 5. Phase 1 therefore leaves #87 item 5 uncommented.

---

## Phase 0: Upstream findings (FR-033)

**Purpose**: Turn the five DomI-owned findings in `evidence.md` ("Findings that belong upstream") into drafted issue bodies. Independent of every other phase; can run at any time. It writes only inside the feature directory.

- [x] T001 Draft five issue bodies, one per finding in `specs/042-measured-status/evidence.md` lines 69 to 79 (`session-resume` prints "none open" when the GitHub call failed; scripts continue after a failed `mktemp -d`; `run_introspection.sh` writes under `/` with an empty root variable; `protected_paths_guard` matches text; `safe_rm.py` exits 1 after a successful delete when its log write fails), into the new file `specs/042-measured-status/upstream-issues.md`. Each body states the observed behaviour, the evidence rows quoted from `evidence.md`, the expected behaviour and a suggested title. Write them in the repository's issue voice (use `Skill write-like-scientist`). FR: FR-033. Test: `grep -c '^## ' specs/042-measured-status/upstream-issues.md` prints 5, and each of the five sections contains an `Evidence` line.
- [x] T002 Read `specs/042-measured-status/upstream-issues.md` back in full and confirm that no body contains a secret, a token or a private path, and that each body cites its evidence row. Fix any miss in the same file. FR: FR-033. Test: `grep -n 'Evidence' specs/042-measured-status/upstream-issues.md` shows five lines, and a manual read finds no secret.
- [ ] T003 Run the full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`. Phase 0 changes no code, so a failure is a pre-existing failure; report it, do not fix it here. FR: FR-033 (ship gate). Test: the suite exits 0 or the pre-existing failures are listed.
- [ ] T004 Decision entry for Phase 0: the plan names none. Confirm that `docs/DECISIONS.md` needs no entry for Phase 0, and do not edit it. FR: FR-032 (no ruling changes in this phase). Test: `git diff --stat docs/DECISIONS.md` shows no change from this phase.
- [ ] T005 OPERATOR-APPROVAL File the five drafted issues in the DomI repository (`domattioli/DomI`) after the operator approves, one `gh issue create` call each, using the bodies in `specs/042-measured-status/upstream-issues.md`. Then append the five issue links to the top of that file under a heading `Filed issues`. FR: FR-033. Test: `grep -c 'github.com/domattioli/DomI/issues/' specs/042-measured-status/upstream-issues.md` prints 5 or more.
- [ ] T006 Closing comments for Phase 0: this phase closes or touches no open agents-inc issue, so there is nothing to comment on. Record that in the supervisor's report for the phase. FR: FR-033, SC-009 (nothing owed for this phase). Test: not applicable.

**Checkpoint**: `upstream-issues.md` holds five bodies; after T005 it also holds the five links.

---

## Phase 1: A verdict says what was measured (User Story 1, P1)

**Goal**: Every run outcome and gate result is passed, failed or not checked; `unverified` exits 4; a missing gate command is "not checked"; outside-scope changes end `unverified`, not red.
**Independent test**: `tests/test_dispatch_verdicts.py`. A gate whose command cannot start yields outcome `unverified`, reason `gate-not-runnable`, exit 4, not `red`.
**FRs**: 001, 001a, 002, 003, 004, 005, 006, 007 (regression test only), 009, 010, 011, 032.
**Serial constraint**: this phase edits `agents_inc/install/dispatch.py`, which phases 2, 3, 4 and 5 also edit. Run it first of those five. The pane readers (T068, T069) edit only `mods/delegate-pane/hooks/`.

### Tests first (write them, run them, see them fail)

- [x] T007 [US1] Create `tests/test_dispatch_verdicts.py` with these cases, using the fake provider and temporary working directories used by `tests/test_dispatch_grants.py`: (a) a gate whose program is deleted during the run, outcome `unverified`, reason `gate-not-runnable`, gate row `state=not-checked` with command and `rc=None`, exit 4 (FR-001, FR-001a, FR-002); (b) three gates, two failed: status names the two failing commands with exit codes first, no gate reported as missing (FR-003, FR-011); (c) a file outside FILES_IN_SCOPE changed during the run: `unverified`, reason `scope-foreign-change`, path listed with `attribution=unknown`, gate results kept, not `red snapshot-not-clean` (FR-005, FR-006); (d) only in-scope files changed: scope passes (FR-005); (e) a run that ends on a provider usage limit with no report: reason `quota-paused` (exit 75) and no other reason (FR-007, regression only); (f) a report with a format fault and all gates passed: outcome `green`, reason `report-format-advisory`, the fault on its own line (FR-009); (g) a format fault with a failing gate: outcome `red` with the gate's reason, not `report-noncompliant` (FR-009, FR-011); (h) every gate not checked: `unverified`, never `green` (FR-004); (i) a run with no gates: `unverified`, reason `no-gates`, exit 4, and that reason differs from the reason for a failed gate (FR-004, FR-011); (j) a gate killed by timeout: `failed`, reason `gate-timeout` (spec edge case); (k) a gate exits 127 while the command itself started: `failed` with the last output line shown; (l) a report with a format fault plus a gate that cannot start: `unverified gate-not-runnable`, not `red report-noncompliant` (FR-001, FR-009); (m) a failed gate plus a format fault: red with the gate's reason (FR-009, FR-011); (n) a file outside FILES_IN_SCOPE changed by a neighbour during a gate, with no evidence about the author: `unverified scope-foreign-change` with attribution unknown, not red and not `gate-wrote`, because before/after timing alone cannot attribute a write to a gate (FR-005, FR-006); (o) a real `pre_dispatch_snapshot.py verify` output containing `OUTSIDE ` lines run through `_snapshot_verify` and `_outcome`: `scope-foreign-change`, not `snapshot-error` (FR-005); (p) an empty FILES_IN_SCOPE with a changed file: the file is outside the scope (FR-005); (q) the three-state `state` field is `passed`, `failed` or `not-checked` for every outcome word in `data-model.md` (FR-001). FR: 001, 001a, 002, 003, 004, 005, 006, 007, 009, 011. Test: the file fails before T011 to T014 and passes after.
- [x] T008 [P] [US1] Update the existing tests that read the old behaviour: `tests/test_dispatch_grants.py:516` must expect `(4, "unverified", "no-gates")` instead of `(0, "unverified", "no-gates")`, and every test that asserts the reason `gate-missing` or a non-git read-only run exiting 0 with `snapshot-skipped` must expect the new reason or exit code 4. Find them first with `grep -rn "gate-missing\|snapshot-skipped\|unverified" tests/`. Touch only files under `tests/` other than `tests/test_dispatch_verdicts.py`. FR: 001a, 002, 011. Test: the updated tests fail before T011 to T014 and pass after.
- [x] T009 [P] [US1] Create `tests/test_dispatch_gate_weak.py`: a slots file whose gate is `test -s <path>`, `test -e <path>`, `test -f <path>` or `ls <path>` for a path that exists before launch prints `warning: gate-weak` on stderr and is not refused; a gate that runs a real test command prints no warning. FR: 010. Test: fails before T016 and passes after.
- [x] T010 [P] [US1] Create `tests/test_snapshot_outside.py` for `skills/workerbee/scripts/pre_dispatch_snapshot.py`: the verify step prints `CHANGED ` lines for in-scope paths whose hash differs from the baseline and `OUTSIDE ` lines for changed paths outside the allow list; an in-scope file that was dirty before launch and did not change prints nothing; its exit status stays nonzero only for outside changes. FR: 005, 006. Test: fails before T015 and passes after.
- [x] T068 [P] [US1] Create or extend `mods/delegate-pane/hooks/controls.test.tsx` (the pane start and resume readers at `mods/delegate-pane/hooks/controls.tsx:39` and `:177`, which run `agents-inc dispatch` and today label every nonzero exit `failed`): a dispatch child that exits 4 shows a distinct `unverified` display, never `failed`; exit 0 shows done and any other nonzero exit still shows failed. Find the mod's test runner in `mods/delegate-pane` first. FR: 001, 001a. Test: fails before T069 and passes after.

### Implementation

- [x] T011 [US1] In `agents_inc/install/dispatch.py` add `EXIT_UNVERIFIED = 4` beside the other exit constants; make `_exit_code` return 4 for outcome `unverified`; make `_req_status` and `REQ_STATUS` accept code 4 as `unverified`; map code 4 in `_run_end_outcome`; write the three-state `state` field to `run.json` for every outcome word, per the mapping table in `data-model.md` "Run outcome". Passed and failed codes do not change. FR: 001, 001a. Test: T007 cases (a), (h), (i), (q) and the T008 updates for exit codes.
- [x] T012 [US1] In `agents_inc/install/dispatch.py` change `_run_gates` so each gate row gains `state` (`passed`, `failed`, `not-checked`), `reason` and `last_line`, per `data-model.md` "Gate result": a command that could not start (any `OSError` before the gate process starts, or the `shutil.which` miss) is `not-checked` with reason `gate-not-runnable`; a timeout is `failed` with `gate-timeout`; a post-run re-screen refusal is `failed` with `gate-refused`. A cwd outside the working directory is `gate-refused`. Return the run's gate reason by the precedence `gate-refused`, then `gate-timeout`, then `gate-failed`, then `gate-not-runnable`. `gate-wrote` is retired. Leave the D72 pre-launch refusal for an absent gate program unchanged. FR: 001, 002, 003, 011. Test: T007 cases (a), (b), (j), (k).
- [x] T013 [US1] In `agents_inc/install/dispatch.py` change `_outcome` to the order in `data-model.md` "Run outcome" (launch-level reds, then failed gates, then the `delegate-stopped` placeholder left for Phase 2, then scope `scope-foreign-change` or `snapshot-skipped`, then `no-gates` and `gates-skipped-broker`, then `gate-not-runnable`, then green; `report-noncompliant` retired by the 2026-11-15 ruling, `no-report` joins the launch-level reds). In `_finish` replace the `gate-missing` assignment for tampered scripts with the gate-row reason `gates-not-run-tampered` (the run outcome stays red `snapshot-tampered`). Remove the code at `dispatch.py:1496-1499` that labels an outside change seen after the gates `gate-wrote`: that change is `scope-foreign-change`, because timing alone cannot attribute a write to a gate. Change `_snapshot_verify` (`dispatch.py:1255-1256`) to read both `CHANGED ` and `OUTSIDE ` lines and to build the in-scope and outside partition, so an `OUTSIDE` verify is never `snapshot-error`. An outside-scope change ends `unverified`, never `red snapshot-not-clean` and never green. A format fault never replaces a gate failure and never turns an unverified case red. FR: 001, 002, 004, 005, 006, 007, 009, 011. Test: T007 cases (c) to (i) and (l) to (p), and the T008 updates.
- [x] T014 [US1] In `agents_inc/install/dispatch.py` extend `_status` to append `gates=<passed>/<total>` with each non-passed gate named first (`state:command:rc=`), and `scope=` with the outside paths and `attribution=unknown`; print, after the status line, the per-gate block of `contracts/verdict-reason-codes.md` (`gate <state> rc=<rc|none> cmd=<full command> last=<last output line>`, one line per gate, non-passed gates first); write the same rows to `gates.txt` in the run directory. FR: 003, 005, 006. Test: T007 cases (b) and (c) assert the exact printed block, the status line and `gates.txt`.
- [x] T015 [P] [US1] In `skills/workerbee/scripts/pre_dispatch_snapshot.py` make `verify` compare baseline and final hashes for in-scope paths as well (today it skips allowed paths, `pre_dispatch_snapshot.py:122`), print `CHANGED ` for an in-scope path whose hash differs, and print paths outside the allow list with an `OUTSIDE ` prefix. A final `git status --porcelain` alone is never evidence of a change in this run. The exit status stays nonzero only for outside changes. FR: 005, 006. Test: `tests/test_snapshot_outside.py` (T010). Implemented as an opt-in `--scope-aware` flag; the legacy default of verify is unchanged because existing callers (luna_native.py:147 and older tests) depend on it; dispatch passes the flag.
- [x] T016 [P] [US1] In `skills/workerbee/scripts/render_dispatch.py` (or the dispatch lint step it feeds) print `warning: gate-weak` on stderr for a gate of the form `test -s|-e|-f <path>` or `ls <path>` whose path exists before launch. Never a refusal. FR: 010. Test: `tests/test_dispatch_gate_weak.py` (T009).
- [x] T017 [P] [US1] In `skills/workerbee/QUICKREF.md` replace "Exit 0 means returned, not verified" with a one-line-per-code exit table (0 green, 1 red, 2 child usage and free-run precheck refusals (`refused-*` written at `dispatch.py:1897-1900`), 3 other refusals, 4 unverified, 69 blocked, 75 quota-paused, 130 cancelled) and add one line describing `scope-foreign-change`. Keep the file compressed (agent audience). FR: 001a, 005. Test: `tests/test_hook_quickref.py` still passes, and `grep -n "unverified" skills/workerbee/QUICKREF.md` shows the new table.
- [x] T018 [P] [US1] Verify `agents_inc/install/mcp_broker.py:190`: it must read the child status, not the exit code, so exit 4 is treated as `unverified` and not as an error. Edit it only if it reads the exit code. FR: 001a. Test: `tests/test_dispatch_broker.py` passes with a child that exits 4.
- [x] T069 [P] [US1] In `mods/delegate-pane/hooks/controls.tsx` (`end?.code === 0` near line 39 and `code === 0` near line 177) show exit 4 as a distinct `unverified` state in the resume note and the job state, and leave exit 0 as done and every other nonzero exit as failed. Touch only `mods/delegate-pane/hooks/`. FR: 001, 001a. Test: `mods/delegate-pane/hooks/controls.test.tsx` (T068).

### Phase ship tasks

- [x] T019 [US1] Run the full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`. All tests must pass, including T007 to T010. FR: 001 to 011 (ship gate), SC-001, SC-008. Test: exit code 0.
- [x] T020 [US1] Write the **D84** entry "Measured verdicts" in `docs/DECISIONS.md` with status "proposed; awaits operator acceptance". It amends D67 Q7 (the rule "a change that appears only after the gates is red `gate-wrote`", which outranks `gate-failed` and `gate-missing`, is reversed: an outside change seen after the gates is `unverified scope-foreign-change` and `gate-wrote` is retired), D58 (`unverified` exits 4 instead of 0; a gate that cannot run is not checked, not `gate-missing`) and the D70 2026-11-09 amendment (the reason order, report precedence), and states the outside-scope rule of research R3 (an outside-scope change ends `unverified`, with attribution unknown, and the `gate-wrote` label is retired because timing alone cannot attribute a write to a gate). Use wording per the DECISIONS.md style (agent-facing, compressed). Phase 1 ships only after the operator accepts it. FR: 032. Test: `grep -n "^## D84" docs/DECISIONS.md` finds the entry and its status line reads "proposed; awaits operator acceptance".
- [x] T021 OPERATOR-APPROVAL Comment on the open issues that Phase 1 closes or partly closes, after the operator approves each external write: close #186 (gate not runnable is reported; no setup slot, per the clarification); comment on #145 that neighbour files no longer turn a run red and that isolation stays out of scope; comment on #155 items h and j; no comment on #87 item 5 yet (Phase 2). Each comment lists which of the issue's items remain. FR: 001, 001a, 002, 003, 004, 005, 006, 007, 009, 010, 011 (the FRs Phase 1 delivers), SC-009. Test: `gh issue view <n> --comments` shows the comment for each issue.

**Checkpoint**: Phase 1 works alone: verdict states, exit code 4, scope rule, `gate-weak` warning.

---

## Phase 2: A delegate's claims are checked against the run (User Story 2, P1)

**Goal**: A deterministic claim check lists every unsupported claim as a warning; every return writes a ledger row; a declared stop is `unverified delegate-stopped`.
**Independent test**: `tests/test_check_claims.py`. A report claiming a file written and tests passed, for a run where nothing changed, lists both claims as unsupported.
**FRs**: 008, 012, 012a to 012f, 013, 014, 015, 016, 032.
**Serial constraint**: edits `agents_inc/install/dispatch.py`; start after Phase 1 is shipped.

### Tests first

- [x] T022 [P] [US2] Create the seeded fixtures under `tests/fixtures/claims/`: at least 10 delegate reports with false claims (a file claimed written that did not change, a wrong test count, a claimed gate pass for a failed gate, an "all gates passed" phrase with a failed gate, a file claimed written that was already dirty before launch and did not change, an unreadable block, and similar) and at least 10 true reports (including a truthful report of a failed gate, with the recorded nonzero exit code, which is supported), each with the run data (changed paths, `gate_results`, gate excerpts) it is compared with and its expected claim results, as JSON files. FR: 012, 014. Test: `tests/test_check_claims.py` (T023) loads all of them; `ls tests/fixtures/claims | wc -l` shows at least 20 report files.
- [x] T023 [US2] Create `tests/test_check_claims.py`: for every false fixture the check lists every false claim as `supported: false`; for every true fixture it lists none and adds no warning; a missing or unreadable block gives `claims=not-checked`, never `passed` (FR-014); no model call and no file read outside the run directory, the working tree and the gate output (FR-016); unknown keys are ignored (contracts/claims-block.md); two or more claims blocks give `unsupported` with reason `multiple-claims-blocks` (the earlier "last block wins" clause is replaced, see T073); one timing test with a fixed fixture of 50 claims and 10 gates asserts that the claim check and the gate-state derivation together take under 1 second (the plan's performance goal; no benchmark harness). Depends on T022. FR: 012, 014, 016. Test: fails before T027 and passes after; SC-003.
- [x] T024 [P] [US2] In `tests/test_host_ledger.py` add tests that `dispatch_return_row` carries `dispatch_row_id`, `exit_code`, `gate_results`, `scope` and `claims` per `contracts/return-row.md`, that each return row carries `state` for every outcome word including `refused-*`, `cancelled`, `dry-run` and `snapshot-failed`, that `claims.items` lists each unsupported claim with `claimed` and `observed`, and that a row is written for each outcome including the refused and cancelled paths, each linked to a `dispatched` row that exists. FR: 015. Test: fails before T030 and T031, passes after.
- [x] T025 [P] [US2] In `tests/test_dispatch_verdicts.py` add: a report with `stopped: <rule text>` ends `unverified`, reason `delegate-stopped`, keeps collected gate results and exits 4 (FR-008); the status line carries `claims=checked:<n> unsupported` the printed block lists one `unsupported <kind> claimed=... observed=...` line per unsupported claim (FR-012); the unsupported-claim warning does not change the outcome (FR-012); an unreadable block shows `claims=not-checked` (FR-014); a declared stop plus a format fault ends `unverified delegate-stopped`; a failed gate plus a declared stop ends red with the gate's reason (FR-008). FR: 008, 012, 014. Test: fails before T031 and passes after.
- [x] T026 [P] [US2] Update the existing tests that cover the report shape and prompt header (`tests/test_dispatch_header.py` and the test file that covers `check_dispatch_prompt.py`, found with `grep -ln check_dispatch_prompt tests/*.py`) so they expect the claims block instruction in the header and slots, and expect the report profile to treat a missing block as advisory, never turning a gated green red. FR: 013, 014. Test: fails before T028 and T029 and passes after.
- [x] T072 [P] [US2] (added 2026-11-15, red-team) Add fixtures under `tests/fixtures/claims/`, in the same JSON shape as T022: (a) two `claims` blocks, an earlier one with false file and test claims and a later truthful one (expect `unsupported`, reason `multiple-claims-blocks`, nothing else compared); (b) `tests: g2=42` where only gate `g1` prints "42 passed" and `g2` is a failed gate or prints nothing (unsupported), plus the same count claimed for the right gate (supported); (c) two gates, one omitted from `gates` (expect `omitted: [g2]` and the failed gate still decides the outcome); (d) two gates with the same argv and different cwd or exit code, claimed by id (each matched on its own record); (e) `stopped: <invented text>` that matches no declared STOP RULE (unsupported), and a `stopped` that matches the declared text or `s1` (supported); (f) a gate that collects zero tests, with `tests: g1=0` and with an `all-gates-passed` claim (both flagged `weak`). FR: 012a to 012f. Test: `tests/test_check_claims.py` (T073) loads them; `ls tests/fixtures/claims | wc -l` grows by at least 6 files.
- [x] T073 [US2] (added 2026-11-15, red-team) Extend `tests/test_check_claims.py` to run the T072 fixtures and assert each expected result: `multiple-claims-blocks`, per-gate test-count binding (FR-012b), `omitted` coverage (FR-012c), gate-id matching with duplicate argv (FR-012d), `stopped` identifier match (FR-012e), `weak` flag (FR-012f); and that the four attacks listed under "Not catchable by the claim check" in spec.md pass without a warning (documented as reviewer-only, not asserted as caught). Depends on T072. FR: 012a to 012f. Test: fails before T074 and passes after.

### Implementation

- [x] T027 [P] [US2] Create `skills/workerbee/scripts/check_claims.py`: parse the claims block from the report text per `contracts/claims-block.md`, compare each claim with the baseline-to-final hash comparison from the snapshot verify (a final `git status --porcelain` alone is never evidence), the recorded `gate_results` (a gate claim is unsupported only when no matching recorded gate exists or its exit code differs) and the gate excerpts, and return claim results (`kind`, `claimed`, `observed`, `supported`). Standard library only; no model call. FR: 012, 014, 016. Test: `tests/test_check_claims.py` (T023).
- [x] T028 [P] [US2] In `skills/workerbee/header.md` and `skills/workerbee/slots.md` add the instruction that tells a delegate to end its hand-back with the fenced `claims` block and how to fill each key. Add the block to the report shape through the header, not as a 15th prompt element. FR: 013. Test: the updated header tests (T026).
- [x] T029 [P] [US2] In `skills/workerbee/scripts/check_dispatch_prompt.py` make the report profile treat a missing claims block as advisory. FR: 014. Test: the updated tests (T026).
- [x] T030 [P] [US2] In `agents_inc/host_ledger.py` extend `dispatch_return_row` with `dispatch_row_id`, `exit_code`, `state`, `gate_results`, `scope` and `claims` (with the `items` list of unsupported claims), per `contracts/return-row.md`. Old readers still load rows without the new fields. FR: 015. Test: `tests/test_host_ledger.py` (T024).
- [x] T031 [US2] In `agents_inc/install/dispatch.py`: `_finish` calls the claim check after the gates; write `claims.json` and `run.json["claims"]`; add the status token `claims=` and print one `unsupported <kind> claimed=<claimed> observed=<observed>` line per unsupported claim after the per-gate block, per `contracts/verdict-reason-codes.md`; make a `stopped` value select `unverified delegate-stopped` in `_outcome` (replacing the placeholder from Phase 1); write the `dispatched` ledger row early, once the run has an id and before the first refusal exit (`dispatch.py:1915`, `1925`, `1993`; the existing write at `2022` becomes a no-op when the row exists), and call `_record_ledger_return` on the refusal and cancel paths so every return writes a row linked to an existing row; write `state` and `claims.items` to the row; pin `check_claims.py` and tamper-check it with the other scripts in `_scripts`. The claim check never changes the outcome in this release. FR: 008, 012, 014, 015, 016. Test: `tests/test_dispatch_verdicts.py` (T025) and `tests/test_host_ledger.py` (T024).
- [x] T074 [US2] (added 2026-11-15, red-team) In `agents_inc/install/dispatch.py` assign gate ids `g1`, `g2`, ... from the slots order in `_run_gates` and carry `id` in each `gate_results` row, run.json and the return row; in `skills/workerbee/scripts/check_claims.py` implement FR-012a to FR-012f per `contracts/claims-block.md` (exactly one block, per-gate test count, gate coverage `omitted`, id matching, `stopped` identifier, `weak`); write `omitted` and `weak` to `claims.json` and `run.json["claims"]`. Depends on T027 and T031. FR: 012a to 012f. Test: `tests/test_check_claims.py` (T073).
- [x] T075 [P] [US2] (added 2026-11-15, red-team) In `skills/workerbee/scripts/render_dispatch.py`, `skills/workerbee/header.md` and `skills/workerbee/slots.md` print each gate with its id (`g1: <argv>`) and the STOP RULE with its single id (`s1: ...`; one rule, no per-clause ids, supervisor ruling 2026-11-16) in the delegate prompt, and tell the delegate to write the block in the id form (`gates: g1=0; g2=0`, `tests: g1=42`) with one block only. Edit after T028 (same files). FR: 012a to 012f, 013. Test: the header tests of T026, updated to expect ids.
- [x] T076 [US2] (added 2026-11-15, red-team) In the Phase 2 DECISIONS entry (T033) record the six accepted claim-check rules and the four "not catchable" attacks. Depends on T033. FR: 012a to 012f, 032. Test: `grep -n "multiple-claims-blocks" docs/DECISIONS.md` finds it.

### Phase ship tasks

- [x] T032 (covered by the 2026-11-16 supervisor run recorded in T064) [US2] Run the full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`. FR: 008, 012 to 016 (ship gate), SC-003, SC-004, SC-008. Test: exit code 0.
- [x] T033 [US2] Write the Phase 2 entry in `docs/DECISIONS.md` with status "proposed; awaits operator acceptance": a new entry D85, titled "Claims block", as its own proposed entry. It records that the claims block joins the report shape (#131 step C) and that the claim check is advisory until a later spec. FR: 032. Test: `grep -n "claims block" docs/DECISIONS.md` finds the entry, with the status line.
- [x] T034 OPERATOR-APPROVAL Comment on the open issues Phase 2 closes or partly closes, after the operator approves each external write: partly close #131 (steps B and C done; step D header REPORT SHAPE remains); close or comment on #87 item 5 (a declared stop is `unverified delegate-stopped`) and note the remaining items; comment on the evidence handoff item "Worker without gates returns no explicit verdict". Each comment lists which items remain. FR: 008, 012, 013, 014, 015, 016 (the FRs Phase 2 delivers), SC-009. Test: `gh issue view <n> --comments` shows each comment.

**Checkpoint**: Phase 2 works alone: claim check, return rows, declared stop.

---

## Phase 3: doctor does not print READY for an untested path (User Story 3, P2)

**Goal**: Each `doctor` item states whether it was tested now; READY only when every required item was tested now and passed; stored values are marked "not verified now".
**Independent test**: `tests/test_doctor_items.py`. With the provider unreachable, `doctor` does not print READY and names the dispatch-path item.
**FRs**: 017, 018, 019, 020 (regression and line format only), 021, 021a, 030, 031, 032. FR-030 covers four surfaces: doctor, session-start hook text, dispatch status notes and the status line.
**Serial constraint**: edits `agents_inc/install/dispatch.py` (the mirror note near line 1430 and the uncommitted-source warning) and `agents_inc/install/hook.py`; start after Phase 2 is shipped.

### Tests first

- [x] T035 [P] [US3] Create `tests/test_doctor_items.py`: unreachable provider gives no READY and a `dispatch-path` line `could-not-test` or `fail` (FR-018, FR-019); an unfinished repair is reported and blocks READY (FR-020, regression test); an installed copy that differs from its source reports whether `install-match` was `measured` or read from a `record` with its age (FR-021); uncommitted source edits under installed paths add a `WB_SOURCE_UNCOMMITTED` warning that does not block READY (FR-021a); every required item tested now and passed gives READY as today (FR-018); after a failed or skipped live check the doctor output prints the stored value with the exact text `not verified now` and its age as `age <n><unit>` (FR-030); each CLI line reads `<name>: <result> (<tested>)` and `--json` adds `items` (FR-017). The probe is a TCP or CONNECT check with a 2 second timeout and no model call; tests use a stub for it. FR: 017, 018, 019, 020, 021, 021a, 030. Test: fails before T038 and T039 and passes after; SC-002.
- [x] T036 [P] [US3] In `tests/test_hook_session_start.py` add a test that session-start text marks stored state "not verified now" with its age (`age <n><unit>`) when the live check failed or did not run. FR: 030. Test: fails before T040 and passes after; SC-007 for the hook surface.
- [x] T037 [P] [US3] Create `tests/test_dispatch_notes.py`: a dispatch with uncommitted source edits under installed paths prints `WB_SOURCE_UNCOMMITTED` once on stderr and is not blocked (FR-021a); the run-record mirror note says what was skipped, that no record was lost (`run.json` stays in the run directory) and that the reader needs no action (FR-031); when the live check failed or did not run, a dispatch status note prints the stored value with `not verified now` and `age <n><unit>` (FR-030). FR: 021a, 030, 031. Test: fails before T041 and passes after.
- [x] T070 [P] [US3] **Amended 2026-11-16 (operator ruling "Age in the left column"; supervisor):** the mark is `AGE <n><unit>` (s, m, h, d) in grey in the TPM cell when the cache is readable and over 5 minutes old; the words `not verified now` do not fit the fixed 148-column layout and are not printed. The tests live in `scripts/tests/statusline_smoke.sh`, not in a new `tests/` file. A cache under 300 s is never stale, so second-unit ages are tested on `age_txt` directly. Red run: `.scratch/impl042/p3-red-statusline-age.txt` (338/360). Original text follows. Create `tests/test_statusline_not_verified.py` (read `scripts/statusline.d/SPEC.md` first): when the usage collection fails or is skipped (the collector call at `scripts/statusline.sh:59` fails and the cache is kept), the status line shows `not verified now` and the cache age as `age <n><unit>`, not only dimmed cells (`scripts/statusline.sh:138`); when the collection succeeds it shows neither. The status line stays within the column widths that SPEC.md sets. FR: 030. Test: fails before T071 and passes after; SC-007 for the status-line surface.

### Implementation

- [x] T038 [US3] In `agents_inc/install/doctor.py` add `DoctorReport.items` with fields `name`, `required`, `tested` (`now`, `record`, `not-tested`) and `result` (`pass`, `fail`, `could-not-test`, `warn`) per `data-model.md`; add a `dispatch-path` item (claude CLI found plus a 2 second CONNECT or TCP probe of `api.anthropic.com:443`, reusing the dispatch probe, no paid usage); add `install-match` with `basis=measured|record` and the record age; add the `WB_SOURCE_UNCOMMITTED` warning from the `source_git` status of `BUNDLE_PATHS` (add a helper in `agents_inc/install/source_git.py` only if one is missing); READY only when every required item has `tested == now` and `result == pass`; a stored value shown after a failed or skipped live check carries the exact text `not verified now` and its age (FR-030). D82 (stale-install check follows git history) stays unchanged. FR: 017, 018, 019, 020, 021, 021a. Test: `tests/test_doctor_items.py` (T035).
- [x] T039 [US3] In `agents_inc/install/cli.py` print one line per item (`<name>: <result> (<tested>)`) followed by READY or the codes, and add `items` to `--json`; print `not verified now` and the age beside any stored value shown after a failed or skipped live check (FR-030). Depends on T038. FR: 017, 018, 030. Test: `tests/test_doctor_items.py` (T035).
- [x] T040 [P] [US3] In `agents_inc/install/hook.py` (lines near 78 to 90) mark stored state in the session-start text as "not verified now" with its age when the live check failed or did not run. Audit every other agents-inc surface that prints a stored value as current (`grep -rn "record\|stored\|cached" agents_inc/install/doctor.py agents_inc/install/hook.py`) and list any further surface in the task report. The status line is a surface of FR-030 and is handled by T070 and T071. FR: 030. Test: `tests/test_hook_session_start.py` (T036).
- [x] T041 [P] [US3] In `agents_inc/install/dispatch.py` (the mirror note near line 1430) make the "run spec not mirrored" message say what was skipped, that no record was lost, and whether action is needed; print the `WB_SOURCE_UNCOMMITTED` warning once on stderr, never blocking; mark any stored value in a dispatch status note `not verified now` with its age when the live check failed or did not run (FR-030). FR: 021a, 030, 031. Test: `tests/test_dispatch_notes.py` (T037).
- [x] T071 [P] [US3] **Done as amended in T070; live 2026-11-16 (smoke 357/357 in the live tree, width 148 in three colour modes).** Read `scripts/statusline.d/SPEC.md` first. In `scripts/statusline.sh` (and `scripts/statusline.d/` only if needed) print `not verified now` and the record age (`age <n><unit>`) when the live collection failed or did not run and the cache is shown as current, within the fixed widths of SPEC.md; if SPEC.md must change to carry the mark, update it in the same task. Touch no other file. FR: 030. Test: `tests/test_statusline_not_verified.py` (T070) and `tests/test_native_usage_statusline.py`.

### Phase ship tasks

- [x] T042 (covered by the 2026-11-16 supervisor run recorded in T064) [US3] Run the full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`. FR: 017 to 021a, 030, 031 (ship gate), SC-002, SC-007, SC-008. Test: exit code 0.
- [x] T043 [US3] Write the Phase 3 entry in `docs/DECISIONS.md` (at the next free number after the entries already written) titled "doctor items and READY", with status "proposed; awaits operator acceptance". It narrows D71 F3 (READY stays with warnings) only for the new required item, and records that D82 is unchanged and that its promised doctor warning is now built. FR: 032. Test: `grep -n "doctor items and READY" docs/DECISIONS.md` finds the entry, with the status line.
- [x] T044 OPERATOR-APPROVAL Comment on the open issues Phase 3 closes or partly closes, after the operator approves each external write: close #112 item 2; comment on #87 item 3 and #87 item 4 (mirror note) with the remaining items; comment on #155 item b (already fixed, comment only). Each comment lists which items remain. FR: 017, 018, 019, 020, 021, 021a, 030, 031 (the FRs Phase 3 delivers), SC-009. Test: `gh issue view <n> --comments` shows each comment.

**Checkpoint**: Phase 3 works alone: per-item doctor lines and a READY that rests on measurement.

---

## Phase 4: A refusal names the rule, the value and the fix (User Story 4, P2)

**Goal**: Every refusal prints the rule name, the offending value and one fix, from one rule registry that the quick reference must match.
**Independent test**: `tests/test_refusal_messages.py`. One bad slots file per rule gives a message with the rule id, the value and a corrected example.
**FRs**: 022, 023, 024, 032.
**Serial constraint**: edits `agents_inc/install/dispatch.py` and `agents_inc/install/hook.py`; start after Phase 3 is shipped.

### Tests first

- [x] T045 [P] [US4] Create `tests/test_refusal_messages.py`: one bad slots file or shell call per known rule (failure gate without a backticked command, glob in FILES_IN_SCOPE, classification outside the allowed set, dispatch command combined with other commands, missing required slot, and every other rule in the registry); each message contains the rule name in words, the offending value and a corrected example or next command; no message shows only a rule number (spec US4 scenarios 1 to 6). FR: 022. Test: fails before T048 to T054 and passes after; SC-005.
- [x] T046 [P] [US4] Create `tests/test_rules_quickref.py`: every rule id in `agents_inc/install/rules.py` has one line in `skills/workerbee/QUICKREF.md`, and the test fails when a rule exists in code and is absent from the quick reference. Also compare the copy of the format function in each script under `skills/workerbee/scripts/` with the one in `rules.py`. FR: 023. Test: fails before T048 and T055 and passes after.
- [x] T047 [P] [US4] Create `tests/test_refusal_no_install_path.py`: no refusal or lint message names a path inside the install directory (such as `~/.claude/skills/...`); a message that points to a template names a command that prints it (`agents-inc dispatch --print-template`, `agents-inc dispatch --rules`). FR: 024. Test: fails before T049 to T055 and passes after.

### Implementation

- [x] T048 [US4] Create `agents_inc/install/rules.py`: the rule registry as a dict literal (fields `id`, `screen`, `summary`, `example_fix` per `data-model.md` "Refusal and Rule" and `contracts/refusal-format.md`) and a `refuse(rule_id, value)` helper that formats three lines (`refused: <rule> (<summary>)`, `value: <value>`, `fix: <example_fix>`), with the value screened and cut at 200 bytes. FR: 022, 023. Test: `tests/test_rules_quickref.py` (T046).
- [x] T049 [P] [US4] In `agents_inc/install/dispatch.py` make each refusal site call the helper from `rules.py`, with no bare rule number. FR: 022, 024. Test: `tests/test_refusal_messages.py` (T045).
- [x] T050 [P] [US4] In `agents_inc/install/hook.py` make the denial messages use the helper (including "the dispatch command must be the whole call"). FR: 022. Test: `tests/test_refusal_messages.py` (T045).
- [x] T051 [P] [US4] In `skills/workerbee/scripts/render_dispatch.py` carry a copy of the format function (scripts under `skills/` cannot import `agents_inc`) and use it at each refusal site. FR: 022, 024. Test: T045 and T046.
- [x] T052 [P] [US4] In `skills/workerbee/scripts/dispatch_schema.py` use the same copy of the format function at each refusal site. FR: 022, 024. Test: T045 and T046.
- [x] T053 [P] [US4] In `skills/workerbee/scripts/check_dispatch_prompt.py` use the same copy of the format function at each lint failure; the 14-element lint keeps printing names (D41 unchanged) and now prints value and fix as well. FR: 022, 024. Test: T045 and T046.
- [x] T054 [P] [US4] In `agents_inc/install/cli.py` add `agents-inc dispatch --rules` (prints every rule with its one-line summary) and `agents-inc dispatch --print-template` (prints the worked slots example). FR: 023, 024. Test: `tests/test_install_cli.py` extended in the same task with one case for each flag, and `tests/test_refusal_no_install_path.py` (T047).
- [x] T055 [P] [US4] In `skills/workerbee/QUICKREF.md` add one line per rule from the registry, and replace the `~/.claude/skills/...` paths in the Lint paragraph with the two commands `agents-inc dispatch --rules` and `agents-inc dispatch --print-template`. FR: 023, 024. Test: `tests/test_rules_quickref.py` (T046) and `tests/test_hook_quickref.py`.

### Phase ship tasks

- [x] T056 [US4] Run the full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`. FR: 022 to 024 (ship gate), SC-005, SC-008. Test: exit code 0.
- [x] T057 [US4] Record the Phase 4 note in `docs/DECISIONS.md`: the plan names no new entry for this phase, so add one line to the open proposed entry (whichever proposed entry is not yet accepted); when none is open, create a new entry at the next free number titled "Refusal wording" with the status "proposed; awaits operator acceptance", stating that the 14-element lint now prints names, values and fixes and that D41 is unchanged. The note carries the status "proposed; awaits operator acceptance" through its parent entry. FR: 032. Test: `grep -n "D41 is unchanged\|D41 unchanged" docs/DECISIONS.md` finds the note.
- [x] T058 OPERATOR-APPROVAL Comment on the open issues Phase 4 closes or partly closes, after the operator approves each external write: close #135 item 4, #155 items e and f, and #172; comment on #87 item 4 (undocumented backtick rule) with the remaining items. Each comment lists which items remain. FR: 022, 023, 024 (the FRs Phase 4 delivers), SC-009. Test: `gh issue view <n> --comments` shows each comment.

**Checkpoint**: Phase 4 works alone: every refusal names rule, value and fix, and the quick reference matches the code.

---

## Phase 5: A refusal follows what the action would do (User Story 5, P3)

**Goal**: The credential screen decides from what a launch requests; the dispatch hook allows mentions and denies unparsed executions; a fixed replay set runs in the suite.
**Independent test**: `tests/test_screen_replay.py`. Every `false-deny` case is allowed, every `bypass` case is denied, every `regression` case keeps its decision.
**FRs**: 025, 025a, 026, 027, 027a, 028, 028a, 029, 029a, 032.
**Serial constraint**: edits `agents_inc/install/dispatch.py` and `agents_inc/install/hook.py`; start after Phase 4 is shipped.
**Scope note (added 2026-11-15, red-team)**: the credential screen reads prompt text only. The tool deny list and the OS sandbox are the controls that block the actual reads; they were not tested here. Decisions below were measured by the supervisor on 2026-11-15 against `agents_inc.install.hook.compound_deny` and `agents_inc.install.dispatch.credential_hit`.

### Tests first

- [x] T059 [US5] Create `fixtures/replay/screens.jsonl`, one JSON object per line with `id`, `screen` (`hook` or `credential`), `input`, `expected` (`allow` or `deny`), `source` and `kind` (`false-deny`, `bypass`, `regression`), per `data-model.md` "Replay case". Include every recorded case from #152 (F1 to F4 and B1 to B8; read the issue with `gh issue view 152`, a read only call), #87 item 1, #155 item i, and the retrospective rows in `evidence.md`, plus the existing passing cases as regressions. A recorded refusal that cannot be reproduced is kept as a case with a note `not caused by agents-inc` (FR-025). FR: 025, 026, 027, 028, 029. Test: `python3 -c "import json;[json.loads(l) for l in open('fixtures/replay/screens.jsonl')]"` exits 0, and each line has all six keys.
- [x] T060 [US5] Create `tests/test_screen_replay.py`, which runs every case in `fixtures/replay/screens.jsonl` through the credential screen or `compound_deny` and compares the decision with `expected`; it also asserts that a launch the screen cannot decide (a path built at run time next to a secret name) is refused with `credential-undecidable` and a message saying it could not decide (FR-026), and that an unparsed form is denied with `hook-unparsed` and a message saying the form could not be parsed (FR-028). Depends on T059. FR: 025, 026, 027, 028, 029. Test: fails before T061 and T062 for every case the code gets wrong, passes after; SC-006.
- [x] T077 [US5] (added 2026-11-15, red-team) Add the hook replay cases to `fixtures/replay/screens.jsonl` (one line each, with `current` and `expected`, `source` `redteam-2026-11-15` or the issue item). Shell strings use `s.json` as in `.scratch/oai042/redteam.md`; the exact strings are in that file, items 11 to 16, 22 to 24.
  - Must deny, current allow (`kind` bypass, 7 cases): B1 in sol's form (about 1,100 nested `$(` around `agents-inc dispatch --slots s.json --model terra`; a recursion error fails open); B2 `$'\x61gents-inc' dispatch --slots s.json --model terra`; B3 `agents-inc $'dispatch' --slots s.json --model terra`; B4 `x=run; agents-inc ${x} --slots s.json --model terra`; B5 `echo "$(case x in x) agents-inc dispatch --slots s.json --model terra;; esac)"`; B6 in sol's form (`cat <<$'EOF'`, a body line, `EOF`, then `agents-inc dispatch --slots s.json --model terra` on the next line); `python3 -c "import os; os.system('agents-inc dispatch --slots s.json --model terra')"` (interpreter escape; required decision is deny for this literal form only; the task and the DECISIONS entry state that a text hook cannot close every interpreter route).
  - Must allow, current deny (`kind` false-deny, 1 case): `source ./helpers.sh # agents-inc dispatch is documented here`.
  - Regression, decision already correct (`kind` regression, 8 cases): B7 `>out agents-inc dispatch --slots s.json --model terra` deny; B8 `agents-inc >out dispatch --slots s.json --model terra` deny; F1 `for w in agents-inc dispatch; do echo "$w"; done` allow; F2 `if true; then echo 'agents-inc dispatch'; fi` allow; F3 `eval "echo 'agents-inc dispatch'"` allow; F4 `bash -c "echo 'agents-inc dispatch'"` allow; `ls && agents-inc dispatch --help` deny by design; B1 in luna's form (nested `${`, already denied) deny.
  Depends on T059 (same file; append, do not rewrite its lines). FR: 027, 027a, 028, 028a, 029a. Test: the file parses and each line has all six keys plus `current` on these cases.
- [x] T078 [US5] (added 2026-11-15, red-team) Add the credential replay cases to `fixtures/replay/screens.jsonl` (`screen` credential; "refused" is `expected: deny`).
  - Must refuse, current allow (`kind` bypass, 6 cases): `{"TASK":"Read .env"}`; `{"TASK":"Read ~/.ssh"}`; `{"TASK":"Read $D/auth.json where D is the home .codex directory"}` (the variable-path form in `.scratch/oai042/redteam.md` item 17); `{"OUT_OF_SCOPE":"Read ~/.codex/auth.json"}`; `{"CONSTRAINTS":"Do not stop before reading ~/.codex/auth.json"}`; `{"TASK":["Read ~/.codex/auth.json"]}` (nested value).
  - Must allow, current refuse (`kind` false-deny, 1 case): `{"TASK":"Explain this error text: 'cannot write ~/.claude/settings.json'"}` (#155 item i).
  - Regression, decision already correct (`kind` regression, 2 cases): `{"TASK":"Read ~/.codex/auth.json"}` refused; `{"TASK":"Research how teaching guides discuss credentials and secrets"}` allowed (bare words; #87 item 1 does not reproduce in `credential_hit`).
  These are test inputs recorded as text; no secret file is read. Depends on T059. FR: 025, 025a, 026, 029a. Test: the file parses and each line has all six keys plus `current` on these cases.
- [x] T079 [US5] (added 2026-11-15, red-team) Investigation, no code change: find which check produced the retro `for ... do` and `if` false denies. F1 to F4 do not reproduce in `compound_deny` (the hook decision is allow), so the suspect is the agent-nudge hook. Run the retro strings through each PreToolUse hook that fires on Bash (read-only: `agents_inc/install/hook.py` agent-nudge path and the user-settings guards), and record the check name and file in `.scratch/042-phase5/false-deny-source.md`. Do this before any tokenizer change; T062 waits for the result. FR: 027. Test: the note names one check, with the command that reproduced the deny, or states "not reproduced".
- [x] T080 [US5] (added 2026-11-15, red-team) Investigation, no code change: find which check produced the #87 item 1 refusal. `credential_hit` allows the bare words "credentials and secrets", so the refusal came from another check (candidates: the slots lint, the grants screen's `gate-credential-path` or `bash-allow-credential` name screens, `credential-secret-var-print`). Replay the recorded #87 launch text through each and record the check in `.scratch/042-phase5/refusal-source.md`. Do this before changing `credential_hit`; T061 waits for the result. FR: 025. Test: the note names one check, or states "not caused by agents-inc" with the replay that was allowed.

### Implementation

- [x] T061 [P] [US5] In `agents_inc/install/dispatch.py` change the credential screen only for the replay cases that still fail (research FR-025 shows the slot text screen already matches locations and not bare words); add the refusal `credential-undecidable` for a path with a shell expansion next to a secret name. A launch that requests access to a secret-bearing path is refused whatever words the prompt uses. FR: 025, 026. Test: `tests/test_screen_replay.py` (T060), credential cases.
- [x] T062 [P] [US5] In `agents_inc/install/hook.py` make `compound_deny` fail closed with `hook-unparsed` when the text contains `agents-inc` and the tokenizer raises or meets an ANSI-C word, a `${...}` subcommand or a redirect before the command (the D72 known limits), and allow a shell call that mentions a dispatch command inside a string or loop without executing it. FR: 027, 028. Test: `tests/test_screen_replay.py` (T060), hook cases, and `tests/test_hook_compound_dispatch.py`.
- [x] T063 [US5] **Done 2026-11-16 (supervisor):** sol review `.scratch/review042/phase2fix-5.md` (15 findings), re-check `.scratch/review042/recheck-screens.md` (11 findings); all fixed test-first (`tests/test_review042_fixes2_hook.py`, `_cred.py`, `_text.py`); the hook moved to one carrier rule and the credential screen to allowlisted exemptions; no third review was run. Cross-vendor review of the screen changes before Phase 5 ships. The supervisor, not the delegate that wrote the code, runs one `agents-inc dispatch` for a read-only reviewer from a different vendor than the writer (these are security screens; AGENTS.md project rules and D46), with the diff of `agents_inc/install/dispatch.py` and `agents_inc/install/hook.py` and `fixtures/replay/screens.jsonl`, using the 14-field prompt contract, and lints the prompt first with `python3 skills/workerbee/scripts/check_dispatch_prompt.py <prompt>`. No paid fallback: if the optional provider's quota is exhausted, pause and report. The supervisor verifies each finding and records accepted and rejected findings; fixes go back to T061 or T062. FR: 025, 026, 027, 028. Test: the supervisor's review record lists the reviewer, the vendor and every finding with its disposition, and a recorded line in the run ledger.
- [x] T081 [US5] (added 2026-11-15, red-team) In `agents_inc/install/hook.py`, beyond T062: fail closed when the tokenizer raises `RecursionError` or any parser error and the text contains `agents-inc` (B1); handle the B2 to B6 forms (decode ANSI-C words and heredoc delimiters, or deny as `hook-unparsed`); derive suspicion from executable tokens so that a comment mentioning `agents-inc dispatch` is allowed (FR-027a); deny the literal `python3 -c` form with `os.system` or `subprocess` and `agents-inc` (FR-028a). Do not claim that interpreter routes in general are closed. Depends on T062, T077, T079. FR: 027a, 028, 028a. Test: `tests/test_screen_replay.py` (T060), hook cases.
- [x] T082 [US5] (added 2026-11-15, red-team) In `agents_inc/install/dispatch.py`, beyond T061: recurse into list and object values of every slot (FR-025a); screen affirmative access requests in `OUT_OF_SCOPE` and `CONSTRAINTS` while keeping pure deny wording allowed; treat a bare `.env`, a bare `~/.ssh` and a variable-prefixed secret file as secret-bearing (the variable form is also `credential-undecidable`); allow a quoted diagnostic mention of a settings path that carries no read or write request. Depends on T061, T078, T080. FR: 025a, 026. Test: `tests/test_screen_replay.py` (T060), credential cases.

### Phase ship tasks

- [x] T083 [US5] (added 2026-11-15, red-team) In the Phase 5 DECISIONS entry (T065) state that the credential screen reads prompt text only, that the tool deny list and the OS sandbox are the real read controls and were not tested, and that a text hook cannot close every interpreter route (only the literal `python3 -c ... os.system` form is denied). Depends on T065. FR: 028a, 032. Test: `grep -n "interpreter route" docs/DECISIONS.md` finds the entry.
- [x] T064 [US5] **Done 2026-11-16 (supervisor run):** 2599 tests, 37 failures, all `tests.test_free_dispatch` at the sandbox precheck; that module is 78 OK with `env -u SANDBOX_RUNTIME`. Output: `.scratch/impl042/phase7-suite-supervisor.txt`. Run the full suite after any review fixes: `python3 -m unittest discover -s tests -p 'test_*.py'`. FR: 025 to 029 (ship gate), SC-006, SC-008. Test: exit code 0.
- [x] T065 [US5] Write the entry "Screens decide on requested action" in `docs/DECISIONS.md`, at the next free number (check `docs/DECISIONS.md` for it; do not assume a number), with status "proposed; awaits operator acceptance". It amends D72 (the known limits become denies) and the 025 slot screen, and records that the cross-vendor review in T063 took place. FR: 032. Test: `grep -n "Screens decide on requested action" docs/DECISIONS.md` finds the entry, with the status line.
- [x] T066 OPERATOR-APPROVAL Comment on the open issues Phase 5 closes or partly closes, after the operator approves each external write: close #152; comment on #87 item 1 and #155 item i (partly closed only if the replay reproduces them, otherwise state "not caused by agents-inc"). Each comment lists which items remain. FR: 025, 026, 027, 028, 029 (the FRs Phase 5 delivers), SC-009. Test: `gh issue view <n> --comments` shows each comment.

**Checkpoint**: Phase 5 works alone: replay set in the suite and screens that decide on the action.

---


## Phase ownership

Source files each phase changes (tests and fixtures are new per phase unless noted). `docs/DECISIONS.md` is edited by every phase from 1 to 5 for the decision task, so those edits are serial too. Phase 0 shares no file with any other phase.

| Phase | Source files changed | Shared with another phase |
|---|---|---|
| 0 | `specs/042-measured-status/upstream-issues.md` | none; can run at any time, beside any other phase |
| 1 | `agents_inc/install/dispatch.py`; `mods/delegate-pane/hooks/controls.tsx` (and its test); `skills/workerbee/scripts/pre_dispatch_snapshot.py`; `skills/workerbee/scripts/render_dispatch.py`; `agents_inc/install/mcp_broker.py` (verify, edit only if needed); `skills/workerbee/QUICKREF.md`; `docs/DECISIONS.md` | `dispatch.py` (2, 3, 4, 5); `render_dispatch.py` (4); `QUICKREF.md` (4); `DECISIONS.md` (2, 3, 4, 5) |
| 2 | `skills/workerbee/scripts/check_claims.py` (new); `agents_inc/install/dispatch.py`; `agents_inc/host_ledger.py`; `skills/workerbee/header.md`; `skills/workerbee/slots.md`; `skills/workerbee/scripts/check_dispatch_prompt.py`; `docs/DECISIONS.md` | `dispatch.py` (1, 3, 4, 5); `check_dispatch_prompt.py` (4); `DECISIONS.md` |
| 3 | `agents_inc/install/doctor.py`; `scripts/statusline.sh` (and `scripts/statusline.d/` only if needed); `agents_inc/install/cli.py`; `agents_inc/install/source_git.py` (only if a helper is needed); `agents_inc/install/hook.py`; `agents_inc/install/dispatch.py`; `docs/DECISIONS.md` | `dispatch.py` (1, 2, 4, 5); `cli.py` (4); `hook.py` (4, 5); `DECISIONS.md` |
| 4 | `agents_inc/install/rules.py` (new); `agents_inc/install/dispatch.py`; `agents_inc/install/hook.py`; `agents_inc/install/cli.py`; `skills/workerbee/scripts/render_dispatch.py`; `skills/workerbee/scripts/dispatch_schema.py`; `skills/workerbee/scripts/check_dispatch_prompt.py`; `skills/workerbee/QUICKREF.md`; `docs/DECISIONS.md` | `dispatch.py` (1, 2, 3, 5); `hook.py` (3, 5); `cli.py` (3); `render_dispatch.py` (1); `check_dispatch_prompt.py` (2); `QUICKREF.md` (1); `DECISIONS.md` |
| 5 | `fixtures/replay/screens.jsonl` (new); `agents_inc/install/dispatch.py`; `agents_inc/install/hook.py`; `docs/DECISIONS.md` | `dispatch.py` (1, 2, 3, 4); `hook.py` (3, 4); `DECISIONS.md` |

`agents_inc/install/dispatch.py` is changed by phases 1, 2, 3, 4 and 5. Run those five phases serially, in the order 1, 2, 3, 4, 5, each shipping before the next starts. No two of them can run at the same time. Only Phase 0 can run beside any other phase. Inside a phase, the [P] tasks are the ones that share no file with another task in that phase.

## Dependencies and execution order

- Phase 0: no dependency; its filing task (T005) needs operator approval.
- Phase 1, then 2, then 3, then 4, then 5 (serial, because of `dispatch.py`). Phase 1's decision (D84) must be accepted by the operator before the Phase 1 code ships (FR-032).
- Inside each phase: tests first, then code, then suite, then decision entry, then OPERATOR-APPROVAL comments.
- Phase 5: T063 (cross-vendor review) happens after T061 and T062 and before T064.
- The supervisor handoff (T067) is last. It is owned by the supervisor session, not by a delegate, and depends on every other task.

## Parallel examples

- Phase 1: after T007 to T010 are written and failing, T015, T016, T017 and T018 can run together. T011 to T014 run in order, because they all edit `dispatch.py`.
- Phase 2: T022, T024, T025, T026 together; later T027, T028, T029 and T030 together; T031 alone.
- Phase 3: T035, T036 and T037 together; T038 then T039 in order, with T040 and T041 beside them.
- Phase 4: T045, T046 and T047 together; after T048, T049 to T055 together.
- Phase 5: T061 and T062 together after T060.

## Implementation strategy

- MVP: Phase 1 alone delivers the main claim (a verdict says what was measured). Ship it first, after the operator accepts D84.
- Incremental delivery: ship 1, 2, 3, 4, 5 in order. Each phase passes the full suite on its own and leaves earlier phases working.
- Stop rule for any delegate: after its task budget or at the first blocked read or write, stop and report. Quota exhaustion pauses the run; there is no paid fallback.

## Coverage: functional requirement to task ids

| FR | Task ids |
|---|---|
| FR-001 | T007, T011, T012, T013, T019, T021, T068, T069 |
| FR-001a | T007, T008, T011, T017, T018, T021, T068, T069 |
| FR-002 | T007, T008, T012, T013, T021 |
| FR-003 | T007, T012, T014, T021 |
| FR-004 | T007, T013, T021 |
| FR-005 | T007, T010, T013, T014, T015, T017, T021 |
| FR-006 | T007, T010, T013, T014, T015, T021 |
| FR-007 | T007, T013, T021 (regression test only; behaviour already present) |
| FR-008 | T025, T031, T034 |
| FR-009 | T007, T013, T021 |
| FR-010 | T009, T016, T021 |
| FR-011 | T007, T008, T012, T013, T021 |
| FR-012 | T022, T023, T025, T027, T031, T034, T072, T073, T074, T075 |
| FR-012a to FR-012f | T072, T073, T074, T075, T076 |
| FR-013 | T026, T028, T034, T075 |
| FR-014 | T022, T023, T025, T026, T027, T029, T031, T034 |
| FR-015 | T024, T030, T031, T034 |
| FR-016 | T023, T027, T031, T034 |
| FR-017 | T035, T038, T039, T044 |
| FR-018 | T035, T038, T039, T044 |
| FR-019 | T035, T038, T044 |
| FR-020 | T035, T038, T044 (regression test and line format only) |
| FR-021 | T035, T038, T044 |
| FR-021a | T035, T037, T038, T041, T044 |
| FR-022 | T045, T048, T049, T050, T051, T052, T053, T058 |
| FR-023 | T046, T048, T054, T055, T058 |
| FR-024 | T047, T049, T051, T052, T053, T054, T055, T058 |
| FR-025 | T059, T060, T061, T066, T078, T080, T082 |
| FR-025a | T078, T080, T082 |
| FR-026 | T059, T060, T061, T066, T078, T082 |
| FR-027 | T059, T060, T062, T066, T077, T079, T081 |
| FR-027a | T077, T081 |
| FR-028 | T059, T060, T062, T066, T077, T081 |
| FR-028a | T077, T081, T083 |
| FR-029 | T059, T060, T066, T077, T078 |
| FR-029a | T077, T078 |
| FR-030 | T035, T036, T037, T038, T039, T040, T041, T044, T070, T071 |
| FR-031 | T037, T041, T044 |
| FR-032 | T004, T020, T033, T043, T057, T065, T076, T083 |
| FR-033 | T001, T002, T003, T005 |
| SC-009 (issue comments) | T006, T021, T034, T044, T058, T066 |
| (not an FR task) | T067 is the supervisor handoff and appears in no FR row |

---

## Supervisor handoff (after all tasks)

This step is not an FR task and no delegate runs it. The supervisor session owns it.

- [x] T067 SUPERVISOR-OWNED Move specs to DomI: run `bash /Users/domattioli/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. The supervisor session runs it; a delegate never does, because it writes into another repository. Run it only after every numbered task (T001 to T066 and T068 to T083) is done and the working tree is clean (`git status --porcelain` prints nothing for tracked files). It moves `.specify/` and `specs/` into DomI `specs/consumers/agents-inc/`, so nothing may run after it. Test: after the run `test ! -d specs/042-measured-status` and the feature directory is present under DomI `specs/consumers/agents-inc/`.
