<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Implementation Plan: Measured status

**Branch**: `development` (feature dir `042-measured-status`; no branch change) | **Date**: 2026-11-15 | **Spec**: `specs/042-measured-status/spec.md`
**Input**: Feature specification from `specs/042-measured-status/spec.md`, evidence from `evidence.md`.

## Summary

Make every status that agents-inc prints rest on a measurement, or say that it does not. The run outcome gains a measured three-state model (passed, failed, not checked) carried by the existing word `unverified` with a new exit code 4. Gates, the scope check and a new deterministic claim check feed it. `doctor` reports per item whether it was tested now. Refusals name the rule, the value and the fix, from one rule registry that the quick reference must match. The credential screen and the dispatch hook are tuned against a fixed replay set. Research findings and the per-FR state of the code are in `research.md`.

## Technical Context

**Language/Version**: Python 3.11 or later, Bash 3.2 or later
**Primary Dependencies**: Python standard library only
**Storage**: JSON files in the run directory (`run.json`, `gates.txt`, `claims.json`); JSONL ledger through `agents_inc/host_ledger.py`
**Testing**: `python3 -m unittest discover -s tests -p 'test_*.py'`
**Target Platform**: macOS (gate sandbox uses `sandbox-exec`), Linux in the docker development container
**Project Type**: CLI and library (`agents-inc` launcher, `agents_inc/install/`, `skills/workerbee/scripts/`)
**Performance Goals**: claim check and gate-state derivation add under 1 s to a dispatch; `doctor` dispatch-path probe has a 2 s timeout
**Constraints**: $0 incremental spend; no model call in any check; `WORKERBEES_GOVERNANCE` stays off by default; exit codes 0, 1, 2, 3, 69, 75 and 130 keep their meaning
**Scale/Scope**: about 10 source files and 8 test files across 5 phases

## Constitution Check

Constitution 1.9.2 is unratified, so violations report as WARN. Pre-design and post-design results are the same.

| Principle | Result |
|---|---|
| P0 cross-reference | Pass. Plan cites DECISIONS entries; it restates no ruling. |
| P1 repo-scoped writes | Pass. No phase widens what a delegate may write. Phase 1 keeps outside-scope writes non-green (research R3). Moving the specs to DomI (T067) is not a delegate task; the supervisor session owns it. |
| P2 ladder | Pass. No routing change. |
| P3 no self-graded gates | Pass. The claim check compares a report with measurements and never upgrades an outcome; the reviewer step stays. |
| P4 deterministic policy | Pass. All checks are deterministic. Phase 5 makes the hook fail closed on unparsed forms. |
| P5 $0 | Pass. `doctor` probe is a CONNECT or TCP check, no model call (research R6). |
| P6 audience docs | Pass. QUICKREF lines are agent-facing and compressed. |
| P8 prompt contract | Pass with a change: the claims block is added to the report shape through the header, not as a 15th element. |

## Project Structure

### Documentation (this feature)

```text
specs/042-measured-status/
├── spec.md, evidence.md, checklists/   # input, not edited here
├── plan.md                             # this file
├── research.md                         # Phase 0
├── data-model.md                       # Phase 1 design
├── quickstart.md                       # manual checks per story
├── contracts/
│   ├── verdict-reason-codes.md
│   ├── return-row.md
│   ├── claims-block.md
│   └── refusal-format.md
└── tasks.md                            # written later by speckit-tasks
```

### Source Code (repository root)

```text
agents_inc/install/dispatch.py      # _run_gates, _outcome, _exit_code, _status, _finish, refusal sites, credential screen
agents_inc/install/hook.py          # compound_deny, _parse, session-start text
agents_inc/install/doctor.py        # check_install, DoctorReport
agents_inc/install/cli.py           # doctor printing, dispatch --rules / --print-template
agents_inc/install/source_git.py    # uncommitted-edit detection reused by doctor
agents_inc/install/rules.py         # new: rule registry
agents_inc/install/mcp_broker.py    # reads child status
agents_inc/host_ledger.py           # dispatch_return_row
skills/workerbee/scripts/check_claims.py         # new
skills/workerbee/scripts/check_dispatch_prompt.py
skills/workerbee/scripts/render_dispatch.py
skills/workerbee/scripts/dispatch_schema.py
skills/workerbee/header.md, slots.md, QUICKREF.md
fixtures/replay/screens.jsonl       # new
tests/                              # see each phase
```

**Structure Decision**: existing single-project layout; no new package.

## Phases

Each phase ships alone, passes the full suite, and maps to one user story in priority order. Phase 0 is independent and can run at any time.

### Phase 0 — Upstream findings (FR-033)

- Files: `specs/042-measured-status/upstream-issues.md` (new, lists the filed issue links).
- Work: file the five DomI findings from `evidence.md` as DomI issues, operator approval first (filing is an external write).
- Tests: none.
- Decision entry: none.
- Issues: none in agents-inc.

### Phase 1 — A verdict says what was measured (Story 1, P1)

FRs: 001, 001a, 002, 003, 004, 005, 006, 007 (regression test only), 009, 010, 011.

- Files:
  - `agents_inc/install/dispatch.py`: `EXIT_UNVERIFIED = 4`; `_run_gates` adds `state`, `reason`, `last_line` per row and returns the reason by precedence `gate-refused` > `gate-timeout` > `gate-failed` > `gate-not-runnable` (`gate-wrote` is retired: before/after timing cannot attribute an outside change to a gate, so the code at `1496-1499` that labels a newly seen outside change `gate-wrote` goes, and the change is `scope-foreign-change`); `_outcome` follows the order in `data-model.md` (failed gates, then every `unverified` case, then `report-noncompliant` last, so a format fault never turns an unverified case red); `_snapshot_verify` reads the `OUTSIDE ` lines and builds the in-scope and outside partition (today it reads only `CHANGED ` lines and would turn an `OUTSIDE` verify into `snapshot-error`); `_finish` replaces the `gate-missing` assignment for tampered scripts with the gate-row reason `gates-not-run-tampered`; `_exit_code` returns 4 for `unverified`; `_status` appends `gates=`, `scope=` and prints the per-gate block (contracts/verdict-reason-codes.md); writes `gates.txt`; the run carries the three-state `state` field mapped from every outcome word; `_req_status` and `REQ_STATUS` accept code 4 as `unverified`; `_run_end_outcome` maps 4.
  - `skills/workerbee/scripts/pre_dispatch_snapshot.py`: verify prints changed paths split into in-scope and outside. It compares baseline and final hashes for in-scope paths too (today it skips allowed paths, `pre_dispatch_snapshot.py:122`), prints `CHANGED ` for an in-scope path whose hash differs and `OUTSIDE ` for an outside path; its exit status stays nonzero only for outside changes. A final `git status --porcelain` alone is never used as evidence of a change in this run.
  - `mods/delegate-pane/hooks/controls.tsx` (lines 39 and 177): the pane start and resume readers run `agents-inc dispatch` and label every nonzero exit `failed`. They show exit 4 as a distinct `unverified` state. Tests in `mods/delegate-pane/hooks/controls.test.tsx`.
  - `skills/workerbee/scripts/render_dispatch.py` or the dispatch lint step: FR-010 warning for `test -s|-e|-f <path>` and `ls <path>` gates whose path exists before launch (stderr `warning: gate-weak`, never a refusal).
  - `agents_inc/install/mcp_broker.py:190`: unchanged meaning, verify it reads status, not exit code.
  - `skills/workerbee/QUICKREF.md`: replace "Exit 0 means returned, not verified" with the exit table; describe `scope-foreign-change`.
- Tests to add: `tests/test_dispatch_verdicts.py` (exit 127 gate, two-of-three failed gates, outside-scope change, in-scope only change, quota text with no report, format fault with passing gates, format fault with failing gates, all gates not-checked, timeout gate, `test -s` warning). Add combined-case tests: a format fault with an unstartable gate gives `unverified gate-not-runnable`; a declared stop with a format fault gives `unverified delegate-stopped` (Phase 2 adds the stop); a failed gate with a format fault gives red with the gate reason; a file changed by a neighbour during a gate gives `unverified scope-foreign-change`, not red; a real `pre_dispatch_snapshot.py verify` output with an outside change run through `_snapshot_verify` gives `scope-foreign-change`, not `snapshot-error`. Update `tests/test_dispatch_grants.py:516` to expect exit 4, and every test that asserts `gate-missing`.
- Decision entry: **D84** (the next free number today) "Measured verdicts" amending D67 Q7 (`docs/DECISIONS.md:694`: a change seen only after the gates is red `gate-wrote`; reversed to `unverified scope-foreign-change`), D58 (exit 0 for `unverified`, `gate-missing` for a gate that cannot run) and D70 2026-11-09 amendment (reason order and report precedence), and stating the outside-scope rule of research R3. Must be accepted before the phase ships (FR-032).
- Issues: closes #186 (gate not runnable reported, no setup slot per the clarification); partly closes #145 (neighbour files no longer turn a run red; isolation stays out of scope), #155 items h and j, #87 item 5 needs Phase 2.

### Phase 2 — A delegate's claims are checked against the run (Story 2, P1)

FRs: 008, 012, 013, 014, 015, 016.

- Files:
  - `skills/workerbee/scripts/check_claims.py` (new): parse the claims block (contracts/claims-block.md), compare with the run using baseline-to-final hashes, return claim results. Pinned and tamper-checked with the other scripts (same path as `check_dispatch_prompt.py` in `_scripts`).
  - `agents_inc/install/dispatch.py`: `_finish` calls the claim check after gates; writes `claims.json` and `run.json["claims"]`; status token `claims=`; `stopped` value selects `unverified delegate-stopped`; the `dispatched` ledger row is written early, before the first refusal exit, so every refusal return links to an existing row; refusal and cancel paths call `_record_ledger_return`; each run carries the three-state `state`.
  - `agents_inc/host_ledger.py`: `dispatch_return_row` adds `dispatch_row_id`, `exit_code`, `state`, `gate_results`, `scope`, `claims` with the list of unsupported claims (contracts/return-row.md).
  - `skills/workerbee/header.md`, `skills/workerbee/slots.md`: the claims block instruction. `check_dispatch_prompt.py` report profile: block missing is advisory (it must not turn a gated green red, D70).
- Tests to add: `tests/test_check_claims.py` with 10 false and 10 true seeded reports (SC-003); `tests/test_host_ledger.py` return-row fields and a row for each refusal outcome; `tests/test_dispatch_verdicts.py` stop case.
- Decision entry: an item in D84, or a separate entry at the next free number if D84 is already accepted when this phase starts (identified by its title "Claims block"): the claims block joins the report shape (#131 step C); claim check is advisory until a later spec.
- Issues: partly closes #131 (steps B and C; step D header REPORT SHAPE stays), closes #87 item 5 (stop), and the evidence handoff item "Worker without gates returns no explicit verdict".

### Phase 3 — doctor does not print READY for an untested path (Story 3, P2)

FRs: 017, 018, 019, 020, 021, 021a, 030, 031. FR-020 is already present (`doctor.py:208`); the work is a regression test and the per-item line format.

- Files:
  - `agents_inc/install/doctor.py`: `DoctorReport.items`; a `dispatch-path` item (claude CLI found plus a CONNECT or TCP probe of `api.anthropic.com:443`, 2 s, reusing the dispatch probe); `install-match` with `basis=measured|record` and the record age; `WB_SOURCE_UNCOMMITTED` warning from `source_git` status of `BUNDLE_PATHS`; READY only when every required item was tested now and passed.
  - `agents_inc/install/cli.py`: print one line per item (`<name>: <result> (<tested>)`), then READY or the codes; `--json` adds `items`.
  - `agents_inc/install/hook.py:78-90`: session-start text marks stored state "not verified now" with its age.
  - `scripts/statusline.sh` (and `scripts/statusline.d/`): read `scripts/statusline.d/SPEC.md` first. The script keeps the cache after a failed collection (`statusline.sh:59`) and only dims stale window cells (`statusline.sh:138`); dimming is not the required mark. It prints `not verified now` and the record age when the live collection failed or did not run, within the fixed column widths that SPEC.md sets.
  - `agents_inc/install/dispatch.py:1430`: the mirror note says what was skipped, that no record was lost (run.json stays in the run directory), and that no action is needed; dispatch prints the `WB_SOURCE_UNCOMMITTED` warning once on stderr, never blocking.
- Tests to add: `tests/test_doctor_items.py` (unreachable provider, failed repair, stale by record vs measured, uncommitted source, all pass gives READY); hook text test for "not verified now"; a status-line test for a failed or skipped refresh (`tests/test_native_usage_statusline.py` or a new file beside it).
- Decision entry: the next free number, titled "doctor items and READY", narrowing D71 F3 (READY stays with warnings) only for the new required item, and recording that D82 is unchanged and its promised doctor warning is now built.
- Issues: closes #112 item 2; partly closes #87 item 3, #87 item 4 (mirror note), #155 item b (already fixed, comment only).

### Phase 4 — A refusal names the rule, the value and the fix (Story 4, P2)

FRs: 022, 023, 024.

- Files:
  - `agents_inc/install/rules.py` (new): rule registry (contracts/refusal-format.md) and a `refuse(rule_id, value)` helper that formats the three lines.
  - `agents_inc/install/dispatch.py`, `skills/workerbee/scripts/render_dispatch.py`, `dispatch_schema.py`, `check_dispatch_prompt.py`, `agents_inc/install/hook.py`: each refusal site calls the helper. The scripts under `skills/` cannot import `agents_inc`; they carry a copy of the format function and the coverage test checks both.
  - `agents_inc/install/cli.py`: `agents-inc dispatch --rules` and `--print-template`.
  - `skills/workerbee/QUICKREF.md`: one line per rule; remove the `~/.claude/skills/...` paths in the Lint paragraph in favour of the two commands.
- Tests to add: `tests/test_refusal_messages.py` (one bad slots file per rule; each message has rule id, value, fix; none is a bare number), `tests/test_rules_quickref.py` (FR-023 coverage), a test that no message names an install path (FR-024).
- Decision entry: none needed if wording only. Record the note per T057: in the open proposed entry, or, when none is open, in a new entry at the next free number titled "Refusal wording" (D41 unchanged; the lint already prints names).
- Issues: closes #135 item 4, #155 items e and f, #172; partly closes #87 item 4 (undocumented backtick rule).

### Phase 5 — A refusal follows what the action would do (Story 5, P3)

FRs: 025, 026, 027, 028, 029.

- Files:
  - `fixtures/replay/screens.jsonl` (new): every recorded case from #152 (F1 to F4, B1 to B8), #87 item 1, #155 item i, and the retrospective rows in `evidence.md`, each with its expected decision; plus the existing passing cases as regressions.
  - `agents_inc/install/dispatch.py`: change the credential screen only for replay cases that still fail (research FR-025 shows the slot text screen already matches locations); add `credential-undecidable` for a path with a shell expansion next to a secret name.
  - `agents_inc/install/hook.py`: `compound_deny` fails closed with `hook-unparsed` when the text contains `agents-inc` and the tokenizer raises, or meets an ANSI-C word, a `${...}` subcommand, or a redirect before the command (D72 known limits).
- Tests to add: `tests/test_screen_replay.py` runs the set (SC-006).
- Decision entry: the next free number, titled "Screens decide on requested action", amending D72 (known limits become denies) and the 025 slot screen. Cross-vendor review required (security screen; AGENTS.md project rules, D46).
- Issues: closes #152; partly closes #87 item 1 and #155 item i (only if the replay reproduces them).

## Out of scope

Implementation code, tests and `tasks.md` (later phases of the pipeline); DomI guards and `session-resume` (Phase 0 files issues only); OS sandbox rules; shared-checkout isolation; free-model and pane features; the Windows port.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| Exit code 4 for `unverified` changes broker and test readers | Clarified operator answer | Exit 0 with a flag: rejected by the operator |
| Rule format copied in `skills/workerbee/scripts/` | Scripts are pinned per run and cannot import `agents_inc` | Shared import: breaks the run pin |
