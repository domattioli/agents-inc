<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# 007 — Plan

Machine doc. Caveman ultra. Reads from `spec.md` (clarified 2026-09-06). Constitution `.specify/memory/constitution.md` v1.5.0 P0-P10 governs.

## Architecture / approach

No new runtime component. Two kinds of change only:
1. **Doc edits** — collapse duplicated rule text to one owner per fact (P0).
2. **Deterministic enforcement** — python unittests in existing `tests/` harness (`python3 -m unittest discover -s tests`), so a pruned prose rule stays enforced (P4: deterministic policy over prompt).

Ordering constraint: **T001 (P10 exit clause) before any phase-2 prune.** Without it a Supervisor has no authority to delete prose, so pruning is a one-time cleanup that re-silts. **T011 (DomI) is independent and runs FIRST** — its dead paths actively mislead any reader today. Phase numbering in `tasks.md` reflects this: DomI is phase 0a, not last.

## Tech constraints

- Python stdlib only. **No pydantic, no new third-party dep** (spec clarification).
- Tests: `unittest`, NOT pytest. All numeric baselines recorded once in `tasks.md` header — not restated here (P0).
- Shell: `bash -n` clean on any touched `.sh`.
- Edit hygiene (P9 / contract 13): surgical edits, no whole-file rewrites where a targeted edit gets identical result.
- Minimal file creation (contract 12). New files this feature: checker script + its test, dup-block test, schema module + its test. Nothing else.

## Phases

| Phase | Tasks | Gate to advance |
|---|---|---|
| 0a — cross-repo | T011 | one PR into DomI `development`, CI green |
| 0b — authority | T001 | P10 amended, v1.6.0, authorizing D-number cited |
| 1 — enforce | T002, T003, T004 | new tests fail-on-violation proven, suite still `OK` |
| 2 — prune | T005, T006, T007, T008 | every pruned rule cites its enforcing test or its surviving single owner |
| 3 — naming | T009, T010 | plural skill renamed, `python3 -m workerbees.pipeline` still resolves |
| close | T012 | process gates verified by run root |

Phase 1 before phase 2 is load-bearing: prune only what an enforcing test (or a verified single owner) already covers.

## Risks

- **T006 mis-scoped upstream.** Prior proposal would have deleted `Does`/`Children?` facts that exist nowhere else. Rescoped in spec. Any A2 executor must diff facts pre/post, not just text.
- **Copy-me literals broken by line-wrap.** Already observed once (`PLAN CONTRACT: not applicable — deliverable is not a plan` failed `grep -F` after wrapping). Every A-task verifies literals w/ `grep -F`, not eyeball.
- **Self-graded gates.** P3: delegate PASS is not evidence. Run root re-runs every check.
- **DomI branch policy.** Named branch needs `CLAUDE_BRANCH_OVERRIDE=1`; operator instruction is the carve-out. Never `--force`, never admin-merge.

## Out of scope

Per `spec.md` "Out of scope". Unchanged.
