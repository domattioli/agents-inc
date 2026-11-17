<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Tasks: Free-Tier-Aware Routing

**Input**: plan.md, research.md, data-model.md, contracts/cli.md, spec.md in `specs/012-free-tier-routing/`
**Tests**: required. In each story, test tasks come before implementation tasks and must fail first.
**Rung key**: `[haiku]` small edits, fixtures, tests; `[sonnet]` router and catalog refresh logic. Every test gate is hermetic: `HOME=tmp_path`, no live network, fixtures only.
**Format**: `- [ ] ID [P?] [Story] [rung] description | files | gate`

## Phase 1: Setup

- [x] T001 [haiku] Create recorded fixtures: OpenRouter models list with the 5 stale ids absent plus 1 new free text model and 1 audio model; key-limits JSON; error bodies for 404 "unavailable for free", 404 ZDR, 429 with "retry in 53.02s", 503; router golden chains for every (task, tier) from unmodified `router.py` | `tests/fixtures/012/*.json`, `tests/fixtures/012/router_golden.json` | files parse with `python3 -m json.tool`
- [x] T002 [haiku] Add shared pytest fixture that sets `HOME` to `tmp_path` and blocks `urllib.request.urlopen` (raise) | `tests/conftest_012.py` or `tests/test_free_*.py` local fixture | any network call in 012 tests raises

## Phase 2: Foundational (blocks all stories)

- [x] T003 [haiku] Tests for `free_health`: atomic write, corrupt/missing file gives healthy + exactly one warning, concurrent last-write-wins leaves valid JSON, outcome classify table from contracts/cli.md | `tests/test_free_health.py` | tests exist and fail (module absent)
- [x] T004 [sonnet] Implement `agents_inc/free_health.py`: read/write health file with `route.sh` schema + `failure_streak`, `calls_day`, `calls_today`; overlay read/write; `classify`; CLI `report|classify|pick-default` stubs | `agents_inc/free_health.py` | `pytest tests/test_free_health.py` green (FR-015)
- [x] T005 [haiku] Edit `routing.json`: `task_tier.classify="grunt"`, `optional_allowed_tasks += "classify"`, `free_order`, `daily_caps {mistral:500, gemini:200, openrouter:50}`, grunt gemini `gemini-flash-lite-latest`; add a `gemini-flash-lite-latest` entry to `agents_inc/models.json` (catalog today only has `gemini-flash-lite`, so `_eligible` would reject the new id) | `agents_inc/routing.json`, `agents_inc/models.json` | `pytest tests/test_router.py tests/test_lineup_router*.py tests/test_router_roster_override.py` green or updated with a stated reason (FR-016)

## Phase 3: US1 dead-model defaults (P1)

- [x] T006 [US1] [haiku] Tests: `pick-default` skips unavailable and overlay-unavailable models, skips non-`:free`, respects tasks_good/tasks_bad, exit 3 + `no eligible free model` with no network; `oask.sh` with no `MODEL` uses pick-default; explicit non-free `MODEL` still refused. 20-run loop over shuffled catalogs never returns an unavailable model (SC-001) | `tests/test_free_health.py`, `tests/test_free_wrappers.py` | tests fail first
- [x] T007 [US1] [haiku] Mark the 5 stale OpenRouter entries `unavailable` | `agents_inc/models.json` | `pytest tests/test_models_catalog.py` green (FR-002). Ids: `minimax/minimax-m3:free`, `minimax/minimax-m2.7:free`, `google/lyria-3-pro-preview`, `google/lyria-3-clip-preview`, `openrouter/free` (spec FR-002)
- [x] T008 [US1] [haiku] Implement `pick-default` and wire `oask.sh:22` to call it when `MODEL` unset; keep spend guard `oask.sh:32-37` unchanged | `agents_inc/free_health.py`, `skills/codex-bridge/scripts/oask.sh` | T006 green (FR-001, FR-013)

## Phase 4: US2 cooldowns (P1)

- [x] T009 [US2] [haiku] Tests: 429 with stated delay sets cooldown to that delay; 429 without delay uses 60 s then 120 s, cap 3600 s; 503 same; withdrawn/ZDR writes overlay, not backend cooldown; success resets streak; each wrapper invokes `free_health report` on exit (stub `curl` via PATH shim) | `tests/test_free_health.py`, `tests/test_free_wrappers.py` | tests fail first
- [x] T010 [US2] [haiku] Implement backoff + overlay transitions in `report` | `agents_inc/free_health.py` | T009 unit part green (FR-004, FR-005)
- [x] T011 [US2] [haiku] [P] Add exit-trap outcome report to `oask.sh` | `skills/codex-bridge/scripts/oask.sh` | T009 wrapper case for oask green (FR-003)
- [x] T012 [US2] [haiku] [P] Add exit-trap outcome report to `gask.sh` | `skills/codex-bridge/scripts/gask.sh` | T009 gask case green (FR-003)
- [x] T013 [US2] [haiku] [P] Add exit-trap outcome report to `mask.sh` | `skills/codex-bridge/scripts/mask.sh` | T009 mask case green (FR-003)

## Phase 5: US3 catalog refresh (P2)

- [x] T014 [US3] [haiku] Tests: dry-run on fixture lists all 5 stale ids as `would mark unavailable` and leaves `models.json` byte-identical (SC-003); apply adds new model with `tasks_good: []`; audio model marked unavailable; fetch failure exit 2, no writes; apply clears overlay for refreshed ids | `tests/test_catalog_refresh.py` | tests fail first
- [x] T015 [US3] [sonnet] Implement `agents_inc/catalog_refresh.py` per contracts/cli.md; only public models endpoint, no key | `agents_inc/catalog_refresh.py` | T014 green (FR-006, FR-007)

## Phase 6: US4 daily caps (P2)

- [x] T016 [US4] [haiku] Tests: count from usage DB for UTC day; fallback to health `calls_today`; rollover resets at UTC midnight (freeze clock); probed cap overrides configured; probe uses key-metadata fixture and never calls a generation URL; key never in stdout/stderr | `tests/test_free_caps.py` | tests fail first
- [x] T017 [US4] [haiku] Implement `agents_inc/free_caps.py` (`calls_today`, `cap_for`, `at_cap`, `probe-openrouter`) and `calls_today` increment in `free_health report` | `agents_inc/free_caps.py`, `agents_inc/free_health.py` | T016 green (FR-008, FR-009)

## Phase 7: US5 router (P2)

- [x] T018 [US5] [haiku] Tests: capture pre-change chains for every (task, tier) pair as golden data before edits; budget + allowed grunt task + healthy free gives mistral first, then gemini, then openrouter, then paid; all free cooled/capped gives paid first; ideal modality chain equals golden; disallowed tasks (draft, review, code) chain equals golden in both modalities; cooldown and cap exclusion apply in both modalities | `tests/test_router_free_first.py`, `tests/fixtures/012/router_golden.json` | tests fail first; uses golden from T001
- [x] T019 [US5] [sonnet] Edit `pick_model_chain` (`agents_inc/router.py:56-74`): filter free providers by `free_health` cooldown and `free_caps.at_cap`; when `AGENTS_INC_MODALITY=budget`, tier grunt, task in allowed list, place `free_order` providers first; merge overlay in `_eligible` (`router.py:18-24`); map router provider to health keys: `gemini` -> `gemini-flash-lite` (and `gemini-flash`), `mistral` -> `mistral`, `openrouter` -> `openrouter` (`route.sh:77`) | `agents_inc/router.py` | T018 green; full `pytest` green (FR-010, FR-011, FR-012, SC-004, SC-006)

## Phase 8: US6 decision (P3)

- [x] T020 [US6] [haiku] Add D-entry: main-session dispatches (Agent tool, workerbee) do or do not consult the router, with rationale and governance if not. Content per spec Clarifications (FR-014 answer), status `proposed` pending operator ratification | `docs/DECISIONS.md` | entry present, `grep -n "FR-014\|main-session dispatch" docs/DECISIONS.md` hits (FR-014)

## Phase 9: Polish

- [x] T021 [haiku] Guard test: no code path sets ZDR off, OpenRouter pick never returns non-`:free`, code-type tasks never route to free providers | `tests/test_router_free_first.py` | green (FR-013)
- [x] T022 [haiku] Run full suite and quickstart steps 1-2 against fixtures | none | `python3 -m pytest -q` green (SC-006)

## FR coverage

| FR | Tasks |
|---|---|
| FR-001 | T006, T008 |
| FR-002 | T007, T014 |
| FR-003 | T009, T011, T012, T013 |
| FR-004 | T009, T010 |
| FR-005 | T009, T010, T015 |
| FR-006 | T014, T015 |
| FR-007 | T014, T015 |
| FR-008 | T016, T017 |
| FR-009 | T016, T017 |
| FR-010 | T018, T019 |
| FR-011 | T005, T018, T019 |
| FR-012 | T018, T019 |
| FR-013 | T008, T021 |
| FR-014 | T020 |
| FR-015 | T003, T004 |
| FR-016 | T005 |

SC-005 (share rises within a week) is observational; no task can verify it before use.

## Dependencies

T001-T002, then T003-T005, then stories. US1 and US2 share `free_health.py` and `oask.sh`: run T008 before T011. US4 before US5 (router imports `free_caps`). Golden capture sits in T001 so it predates T005. US3, US6 independent.

## Open questions (block or shape tasks)

1. Resolved in analyze cycle 1: stale ids named in FR-002.
2. Resolved: `AGENTS_INC_MODALITY` confirmed in spec Clarifications.
3. T005 changes `task_tier`/`optional_allowed_tasks`, which may alter ideal-modality chains for `classify` (today unmapped). FR-012 says "all other tasks unchanged"; classify is new, so treated as allowed change.
