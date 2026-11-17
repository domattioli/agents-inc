<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Analyze report: 012 free-tier routing

Run by the main session on 2026-09-23, per operator instruction. Cycle 1 of 2. All findings were resolved by editing artifacts only.

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| A1 | High | The spec did not name the five stale OpenRouter ids, which blocked T007 and the T014 fixture. | Named in FR-002. `openrouter/auto:free` is kept as a meta-router. |
| A2 | High | T005 points the Gemini grunt model at `gemini-flash-lite-latest`, but `models.json` has only `gemini-flash-lite`. `_eligible` would reject the new id, which would silently drop Gemini from every chain. | T005 now adds the catalog entry. |
| A3 | Medium | Router provider names (`gemini`) differ from the health-file keys in `route.sh:77` (`gemini-flash`, `gemini-flash-lite`). Without a mapping, the cooldown filter never matches Gemini. | T019 now states the mapping. |
| A4 | Medium | FR-014 had no content. | A proposed answer was added to Clarifications. T020 records it with status `proposed` until the operator ratifies it. |
| A5 | Medium | T005 changes the Gemini model in existing ideal chains. That conflicts with FR-012 ("unchanged"). | FR-012 now names this as the one allowed substitution. |
| A6 | Low | The eligibility of catalog entries with status `unprobed` was unspecified (CHK007). | Clarified: eligible only for tasks in `tasks_good`. |
| A7 | Low | The modality variable name was assumed. | Confirmed in Clarifications: `AGENTS_INC_MODALITY`. |
| A8 | Info (out of scope) | `route.sh:32` sends the `code` class to Mistral. That predates this feature and is outside FR-013, which covers only what this feature widens. | Not fixed. Flagged to the Executive. |
| A9 | Info | The stale `minimax` entries list `code-write` in `tasks_good`. | Harmless: they become unavailable, and `optional_allowed_tasks` excludes code tasks. T021 guards this. |

Coverage: FR-001 to FR-016 each map to at least one task (see the tasks.md table). No constitution conflicts were found. Result: ready for implementation.
