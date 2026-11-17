<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-14 skill=speckit-pipeline repo=agents-inc session=91aeecb8 -->
# Implementation Plan: Unified delegate pane

**Branch**: `feat/pane-auto-open` (spec 040 work branches from it) | **Date**: 2026-11-14 | **Spec**: specs/040-unified-delegate-pane/spec.md
**Input**: specs/040-unified-delegate-pane/spec.md (Clarifications 2026-11-14: map first; narrow collapse toggle; drop native types list)

## Summary

Merge mods/agents-manager into mods/delegate-pane. One pane `agents-inc-delegates`, command `/delegate-pane`, version 0.6.0. Sections top to bottom: mission map + status line + feed, delegation tree, new-agent form, message box. One 1 s poll feeds tree and map. Both old agent lists and the native-types list go. Installer installs delegate-pane only and uninstalls `agents-manager@agents-manager-local` and `luna-pane-local` idempotently. mods/agents-manager deleted; stray folders and the locked worktree cleaned under a commit check.

## Technical Context

**Language/Version**: TypeScript/TSX mod hooks (Claude Code mod runtime, `claude-code/testing`); Python 3.11 installer
**Primary Dependencies**: mod `$` API only: `$.agent.list/spawn`, `$.process.spawn`, `$.session.send/model`, `$.ui.open/view/blit/resolve`, `$.fs`, `$.store`, `$.clock.every`
**Storage**: `$.store` key `session:<id>` (acks, sessionStart, alertAt), unchanged; dispatch runs under `.scratch/agents-inc-runs`
**Testing**: mod tests via `claude-code/testing` (`*.test.ts[x]` in mods/delegate-pane/hooks); `python3 -m unittest` for tests/test_mod_install.py, tests/test_delegate_pane_rungs.py
**Target Platform**: Claude Code terminal pane; dev and stress in docker, Mac installs only
**Project Type**: Claude Code mod + installer
**Performance Goals**: one poll per second; no extra reads versus delegate-pane 0.5.0 + agents-manager 0.1.0 combined (strictly fewer)
**Constraints**: no model call, no network (FR-014); $0 (P5); pane survives a refused frame/open
**Scale/Scope**: ~1170 lines of hooks to reorganise; mod tests: the T001 baseline sum (measured 2026-11-14: 113) (pane 46, mission 26, frames 19, manager 22)

## Constitution Check

| Principle | Status |
|---|---|
| P0 cross-reference | Pass: plan cites spec 039 and DECISIONS D62, does not copy them |
| P1 repo-scoped writes | Pass: all edits in this repo; spec move to DomI is the last task |
| P2 labor ladder | Pass: workhorse writes, orchestrator reviews (D78) |
| P3 no self-graded gates | Pass: tests + separate reviewer |
| P4 deterministic policy | Pass: worktree removal gated by a git command, not judgment |
| P5 $0 | Pass |
| P6 audience docs | Pass: README human prose; specs compressed |
| P9 surgical edits | Watch: register.tsx gets a large restructure; justified by FR-003/FR-009, done as moves into new modules |

No unjustified violations. Re-check after Phase 1: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/040-unified-delegate-pane/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/pane-contract.md
└── tasks.md   # /speckit-tasks
```

### Source Code

```text
mods/delegate-pane/
├── .claude-plugin/plugin.json      # version 0.6.0, new description
├── README.md                       # merged pane
└── hooks/
    ├── register.tsx   # wiring only: session.start, one poll, ui.render composing sections, commands, ui.close
    ├── poll.ts        # NEW: one poll -> PollResult {agents, treeRows, delegates, finalRuns, lostRuns, mapNote, note}; dedupe
    ├── tree.ts        # NEW, pure: tree rows from agents-manager (rows, nesting, job rows, KEEP_RUNS, STALE/RECENT, model+effort lists, argv builders, slotsFor, free run)
    ├── controls.tsx   # NEW: tree section, new-agent form, message box, narrow toggle (moved JSX from agents-manager)
    ├── mission.ts frames.ts rungs.ts   # kept
    ├── tree.test.ts                     # NEW: pure tree/dedupe tests
    ├── controls.test.tsx                # ported manager.test.tsx (22 tests)
    └── pane.test.tsx mission.test.ts frames.test.ts   # kept; list tests rewritten for tree
agents_inc/install/cli.py      # PANE_MODS = delegate-pane only; RETIRED_MODS migration
agents_inc/install/bundle.py   # drop mods/agents-manager from OPTIONAL_ALLOWLIST
tests/test_mod_install.py      # update 176-241; add migration + idempotence tests
mods/agents-manager/           # DELETED
docs/DECISIONS.md CHANGELOG.md # D62 status note; merge entry
```

## Design

1. **Module split** (R1). Keep mission.ts/frames.ts/rungs.ts untouched. Move agents-manager pure logic (row building, job lifecycle, run parsing, model/effort tables, argv builders) into tree.ts with unit tests. Move its JSX and press handlers into controls.tsx. register.tsx keeps lifecycle wiring and composes sections. Module-level mutable maps (`JOBS`, `STOP_ASKED`, `DONE`, `AT`) move behind one `PaneState` object reset at session.start.
2. **One poll** (R2, FR-009). `$.clock.every(1000)` reads `$.agent.list()` once and each run dir once; produces both tree rows and map delegates. agents-manager's 2 s loop and its own `$.fs.list(RUNS)` go. Run parsing: delegate-pane's `readRuns` is the base; it gains the fields the tree needs (stdout/stderr tail for failed starts, run.json kind free).
3. **Dedupe** (R3). Identity: native agent by `agentId`; dispatch run by run dir name; free run by run dir name; job row (pending start) replaced when its agent or run dir appears. One delegate = one tree row and one map marker.
4. **Sections** (FR-003): map, status line, feed, mapNote, tree, form, message box. Remove "Native agent types" and "Native agents this session" and the `agents-inc luna status` spawn at session start (no longer needed: FR-008).
5. **Narrow** (R4): `columns < 34` -> form and message box render as one Button line `▸ new agent / message` toggling a `controlsOpen` flag in `$.state`; tree and map stay. Threshold constant `NARROW_COLS = 34` next to `layoutFor`.
6. **Run sub-pane**: `run-<id>` renderer moves with controls.tsx; register.tsx routes `ui.render` by requestId prefix.
7. **Store**: key and shape unchanged (FR-010); agents-manager stored nothing.
8. **Installer** (R5): `PANE_MODS = (("delegate-pane", ...),)`. New `RETIRED_PANE_MODS = (("agents-manager@agents-manager-local", "agents-manager-local"), ("luna-pane@luna-pane-local", "luna-pane-local"))`. In install_pane_mods, after `plugin list`: uninstall a retired plugin only if listed; remove a retired marketplace only if in known_marketplaces.json. R-c: a stale luna-pane-local entry with no listed plugin is removed by marketplace remove, else reported as a notice. Second run: nothing listed -> no calls. MOD_UNINSTALL_ARGVS keeps retired entries so full uninstall still clears old machines.
9. **Bundle** (FR-012): drop `mods/agents-manager` from OPTIONAL_ALLOWLIST and from cli.py:87 loop (follows PANE_MODS).
10. **Cleanup** (FR-016): remove untracked `mods/{agents-manager,delegate-pane,agents-inc}/.claude/` and `mods/agents-manager/.scratch/`. Worktree `.claude/worktrees/agent-ae71b5b16daa5b202` (branch fix/dispatch-non-git-cwd): gate `git log fix/dispatch-non-git-cwd --not development main` empty -> `git worktree unlock` + `remove` (outside sandbox). Non-empty -> report, keep (see R6).
11. **Docs**: D62 status note (FR-015), CHANGELOG entry, mods/delegate-pane/README.md rewrite (FR-017). SC-005 grep: `agents-manager` only in CHANGELOG, DECISIONS, specs, installer retired-list and its test.

## Task order hint (for /speckit-tasks)

1. tree.ts + tree.test.ts (pure, port logic) 2. poll.ts + dedupe tests 3. controls.tsx + port manager.test.tsx 4. register.tsx rewire, drop lists, narrow toggle; update pane.test.tsx 5. version 0.6.0, README 6. installer + bundle + tests 7. delete mods/agents-manager, stray dirs, worktree gate 8. DECISIONS/CHANGELOG 9. docker test run, SC-003 count >= the T001 baseline sum (measured 2026-11-14: 113) 10. **Move specs to DomI** (`<DomI>/specs/consumers/agents-inc/`, pipeline rule; final task of speckit-implement).

## Risks

- **R-a Test port fidelity**: manager tests assert agents-manager PANE id `agents-manager` and 2 s timing; port must retarget to `agents-inc-delegates`/1 s without weakening assertions. Reviewer diffs assertion lists.
- **R-b Worktree gate is red today**: `git log fix/dispatch-non-git-cwd --not development main` lists 19 commits (local development lacks #176 and its merge commits; verified 2026-11-14). Tree diff vs feat/pane-auto-open shows no content missing in agents_inc. Per spec, report and keep unless operator approves; do not substitute a weaker check silently.
- **R-c Uninstall of a plugin the CLI no longer lists** (luna-pane cache only): `plugin uninstall` may fail; treat non-zero as notice, never failure; cache dir removal is out of scope unless the marketplace remove clears it.
- **R-d Poll cost**: merged poll reads stdout/stderr tails only for failed/new runs, else per-second reads grow.
- **R-e Module-level state** in agents-manager leaks across sessions in tests; PaneState reset must be covered.
- **R-f Mac still has delegate-pane 0.2.0**: migration only fixes it after a reinstall; quickstart says so.
