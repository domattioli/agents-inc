<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# 007 — Canon consolidation + drift repair

Machine doc. Caveman ultra. Status: clarified, not started. Created 2026-09-06.

## Problem

Canon grew ~3x in one day (2026-09-06). Rules enter, never leave. Same rule now written in 2+ places → already drifted once (`max` dropped from one effort list, element counts stale in both). No mechanism prunes canon.

## Clarifications

### Session 2026-09-06

- Q: DomI PR split, given DomI single-purpose rule (`DomI/CLAUDE.md:146`)? → A: One PR, all four changes. Frame under single root cause "reconcile workerbee canonical source" to satisfy single-purpose bar.
- Q: Who may delete prose once a landed test enforces the same rule? → A: Supervisor, unilaterally, with evidence — must cite the specific enforcing test and that test green. Same authority bar as P10's existing "small/minor doc fixes". Rationale: constraint got stronger, not weaker; operator-in-loop per-prune is the friction that let canon grow unchecked.
- Q: `workerbee` vs `workerbees` one-letter collision? → A: Rename the plural. Singular keeps name (matches DomI, renaming re-opens ADR-0003 drift). Python package `workerbees/` + `python3 -m workerbees.pipeline` entrypoint UNCHANGED — skill dir + frontmatter only.
- Q: Build dispatch-prompt contract checker as skill? → A: No new skill. Script + unittest under `skills/workerbee/scripts/`, referenced from Step 11. Constitution P4: deterministic policy beats prompt. Keeps skill count at 3.
- Q: Commit strategy for session's uncommitted work? → A: Hold. Commit nothing until Groups A–D done, then commit finished state.

## Tasks

Gates live in `tasks.md` and ONLY there — restating them here is the duplication this feature exists to remove (P0). Task IDs + owning model:

| ID | What | Model |
|---|---|---|
| T011 | DomI PR (4 changes, one PR) | run root |
| T001 | Constitution P10 exit clause, v1.6.0 | run root |
| T002 | Duplicate-block test | haiku → sonnet review |
| T003 | Dispatch-contract checker (script+test, no skill) | haiku → sonnet review |
| T004 | Schema-harden `workerbees/*.json`, stdlib only | sonnet |
| T005 | `AGENTS.md` de-dup | haiku |
| T006 | `CLAUDE.md` rung table de-dup (keep `Does`/`Children?`) | sonnet |
| T007 | `CLAUDE.md` contract → 14-item enumeration | opus |
| T008 | Apply Step 11 compression + checker ref | run root |
| T009 | Rename plural skill → `doc-analysis` (+ `test_gen_stubs.py`) | haiku → run root verify |
| T010 | version/benchmark frontmatter | NEEDS-OPERATOR |
| T012 | Close-out process gates | run root |

Ordering of record (`plan.md` Phases): 0a T011 → 0b T001 → 1 T002/T003/T004 → 2 T005/T006/T007/T008 → 3 T009/T010 → close T012.

## Out of scope

- Closing GH issue #2 (needs push authority; run root's call post-commit).
- Ratifying constitution (`ratified: false`, 2 NEEDS-OPERATOR items unresolved — recommendation of record: NOT YET, file defines no ratification criteria beyond operator sign-off).
- GH issue #3 (speckit-mandate brainstorm) — open question, not a task here.
- Automating a periodic context-audit job. Rejected on evidence: canon growth is a 1-day spike, not a recurring pattern. Fold into session-end review.
- A plain-English SKILL.md. `gask.sh --plain` already shipped + live-verified; wrapping it in a skill is the ported-plugin mistake in new costume.

## Assumptions

- Baselines (test count, word counts, dep count) recorded once in `tasks.md` header. A prior delegate misreported a test's stdout print `Ledger nodes: 1` as the unittest summary — read the `Ran N tests`/`OK` lines, not the tail.
- `.specify/scripts/bash/check-prerequisites.sh` absent → every speckit phase here is hand-adapted. Unchanged all session.
