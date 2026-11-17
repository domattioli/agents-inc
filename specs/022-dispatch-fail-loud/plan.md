# Implementation Plan: Dispatch fails loud

**Branch**: none (hand-run) | **Date**: 2026-10-18 | **Spec**: `.scratch/spec022/spec.md`
**Input**: Feature specification from `.scratch/spec022/spec.md`

## Summary

Make every failed, tampered or hung `agents-inc dispatch` run visible and correctly named. Verify the snapshot against a trusted copy outside cwd; classify quota, connectivity, crashes, launch exceptions, verifier errors and mirror errors with their own reasons and, for quota and connectivity, their own exit codes; put the first stderr line on the status line; give every child a deadline; probe the nested sandbox; make doctor check `claude` and the hook show warnings; stop prose from turning into scope prefixes and test-file names from tripping the credential screen. Design: `research.md` R1-R10; contract: `contracts/dispatch-outcomes.md`; data: `data-model.md`.

## Technical Context

**Language/Version**: Python 3.10+ standard library only (`AGENTS.md` Setup)
**Primary Dependencies**: none new; `claude` and `codex` CLIs at run time only
**Storage**: files: run dir (`run.json`, `snapshot.json`, `prompt.md`), NEW trusted dir `<state>/dispatch-runs/<run-id>/` for top-level runs; broker children trust the broker-owned run dir (FR-001)
**Testing**: `unittest`; full suite `python3 -m unittest discover -s tests -p 'test_*.py'`; temp dirs and fake HOME, no network, no model calls
**Target Platform**: macOS (sandbox-exec paths) and Linux (probe returns False)
**Project Type**: CLI plus stdio MCP server
**Performance Goals**: sandbox probe ≤ 1 run per process, ≤ 10 s; doctor adds ≤ 1 `which` lookup
**Constraints**: $0 spend; no network in tests; no change to the 14-field prompt contract, grant set, routing, or outcome set
**Scale/Scope**: 5 source files, 6 NEW test files, 4 existing test files touched

## Constitution Check

Constitution = `AGENTS.md` project rules + `docs/DECISIONS.md`.

| Rule | Status |
|---|---|
| $0 per task, no paid fallback (`AGENTS.md`; D9 `docs/DECISIONS.md:15`) | Pass: no API path added; quota stays a pause (exit 75), never a fallback |
| Claude required, Codex optional (`AGENTS.md`; D50 `docs/DECISIONS.md:559`) | Pass: `WB_CLAUDE_NOT_FOUND` is a code; Codex absence stays a warning (`doctor.py:72`) |
| Worker never accepts own output; deterministic verification (`AGENTS.md`) | Pass, strengthened: FR-001..003 remove a self-acceptance path |
| Quota pause counts as one failed attempt (`AGENTS.md`) | Pass: distinct reason `quota-paused` lets the supervisor count it |
| Keys never in prompts or argv; scrubbed env (`AGENTS.md`; D51 `docs/DECISIONS.md:569`) | Pass: doctor probe gains `worker_env` (no `*KEY*/*TOKEN*/*SECRET*`); stderr detail goes through `screen_text` |
| D47 one status line (`docs/DECISIONS.md:511`) | Pass: still one line; optional `detail=` field |
| D51 broker refuses Claude where sandbox unavailable (`docs/DECISIONS.md:570`) | Pass, strengthened: probe makes "unavailable" true when nesting fails |
| D52 warnings keep READY (`docs/DECISIONS.md:582`) | Pass: `WB_SANDBOX_NESTED` is a warning; hook now prints warnings |
| D58 outcome set and exit codes (`docs/DECISIONS.md:622`) | Amend needed: exits 69 and 75 and reasons are new. Outcome set unchanged. Requires a DECISIONS entry (T027, CoS-owned canon edit, cross-vendor review per D46.10(b) `docs/DECISIONS.md:502`) |
| Free Grunt only small fixed diffs (`AGENTS.md`) | Note: US1 and US3 need Workhorse or above; US5 and FR-015/016 fit Grunt |
| `WORKERBEES_GOVERNANCE` default off (`AGENTS.md`) | Untouched |

Gate result: pass with one justified amendment (D58 exit list), tracked below.

## Project Structure

### Documentation (this feature)

```text
.scratch/spec022/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/dispatch-outcomes.md
├── tasks.md
├── checklists/requirements.md
├── analyze.md
└── analyze-resolve.md
```

Final home after implement: DomI `specs/consumers/agents_Inc/022-dispatch-fail-loud/` (AGENTS.md Governance), moved by the CoS.

### Source Code (repository root)

```text
agents_inc/install/
├── dispatch.py      # FR-001..016, FR-020, FR-021
├── runtime.py       # FR-014 (run_codex timeout_s)
├── doctor.py        # FR-017, FR-019
├── hook.py          # FR-018
└── mcp_broker.py    # FR-015
tests/
├── test_dispatch_snapshot_trust.py # NEW: US1 tests (T001)
├── test_dispatch_failloud.py       # NEW: US2 tests (T006)
├── test_dispatch_broker_robust.py  # NEW: US3 tests (T012)
├── test_doctor_claude.py           # NEW: US4 doctor tests (T018)
├── test_hook_session_start.py      # NEW: US4 hook test (T019)
├── test_dispatch_slot_screens.py   # NEW: US5 tests (T022)
├── test_dispatch_cli.py            # STATUS_RE extended (TAMPERED, detail, launch-failed)
├── test_install_doctor.py          # stubs passed to check_install (FR-017)
├── test_doctor_codex_optional.py   # stubs passed to check_install (FR-017)
├── test_install_at_route.py        # stubs passed to check_install (FR-017)
└── test_dispatch_grants.py         # must stay green after FR-021
```

**Structure Decision**: single project; existing `agents_inc/install/` and `tests/` layout.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| New exit codes 69, 75 beyond D58's list | #88 item 5 asks for distinct codes; a driver loop must branch without parsing text | Reason text only: the reported driver already ignored text for 30 rounds |
| Trusted store outside cwd | Run dir is delegate-writable (`dispatch.py:49-58`) | In-memory only breaks `--resume` trust (new process) |
