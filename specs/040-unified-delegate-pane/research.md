<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-14 skill=speckit-plan repo=agents-inc session=91aeecb8 -->
# Research: Unified delegate pane

## R1 Module split
- Decision: keep mission.ts, frames.ts, rungs.ts; add tree.ts (pure), poll.ts (I/O, one poll), controls.tsx (JSX + handlers); register.tsx wiring only.
- Rationale: register.tsx (507) + agents-manager register.tsx (662) in one file exceeds reviewable size; pure tree logic gets unit tests like mission.ts.
- Alternatives: single register.tsx (rejected: size, P9 review cost); keep two mods with one pane (rejected: FR-001, two auto-opens).

## R2 One poll
- Decision: 1 s `$.clock.every` in register.tsx calls poll.ts; result feeds tree rows and map delegates; view saved once per changed signature.
- Rationale: FR-009; delegate-pane already polls 1 s; agents-manager 2 s is subsumed.
- Alternatives: keep 2 s (rejected: map motion needs 1 s state).

## R3 Dedupe
- Decision: key native by agentId, runs by run dir name; job rows dropped once their agent/run dir is seen (existing agents-manager rule). Map `subagentDelegate` and tree row share the key.
- Rationale: edge case "same delegate through two sources".
- Alternatives: dedupe by description text (rejected: not unique).

## R4 Narrow layout
- Decision: below 34 columns the form and message box collapse behind a one-line toggle; state in `$.state` (not `$.store`).
- Rationale: Clarification 2026-11-14; 34 matches the map's stacked/line threshold region.
- Alternatives: hide entirely (rejected: loses controls, SC-002).

## R5 Installer migration
- Decision: RETIRED_PANE_MODS list; uninstall/remove only when present in `plugin list` / known_marketplaces.json; warnings not failures.
- Rationale: FR-011 idempotence; matches install_pane_mods contract (problems are warnings).
- Alternatives: unconditional uninstall (rejected: second run emits failures).

## R6 Worktree gate
- Decision: spec rule as stated: `git log <wt-branch> --not development main` empty before remove; else report.
- Finding 2026-11-14: currently non-empty (19 commits, merge history); worktree clean; `git diff 1cb057a feat/pane-auto-open -- agents_inc` empty. Operator decides.

## R7 Native types list
- Decision: drop list and the `agents-inc luna status --json` spawn at session start.
- Rationale: Clarification; form model picker covers it; removes a process spawn per session.
