<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Free-Tier-Aware Routing

**Branch**: `feat/012-free-tier-routing` | **Date**: 2026-09-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/012-free-tier-routing/spec.md` (Clarifications answered 2026-09-23)

## Summary

Free grunt wrappers fail on dead models and never cool down, and the router ranks free providers last. The fix has four parts, all Python standard library:

1. A shared free-provider health module (`agents_inc/free_health.py`) that the three wrappers call on exit. It writes cooldowns to the existing `~/.codex-bridge/backend-health.json` and writes model withdrawals to a separate overlay file.
2. Catalog-driven default model choice for `oask.sh`, replacing the hardcoded default at `skills/codex-bridge/scripts/oask.sh:22`.
3. A catalog refresh command (dry-run default) and an OpenRouter limits probe that make no generation call.
4. Router changes in `agents_inc/router.py`: skip free providers in cooldown or at their daily cap, and in budget modality list free providers first for grunt `extract`/`summarize`/`classify`.

## Technical Context

**Language/Version**: Python 3 (repo baseline), Bash wrappers
**Primary Dependencies**: standard library only (`json`, `sqlite3`, `urllib.request`, `os`, `tempfile`, `datetime`)
**Storage**: JSON files under `~/.codex-bridge/` (health, model overlay, probed caps); existing SQLite usage DB (`skills/codex-bridge/scripts/usage_db.py:10`, table `usage(... day, backend, model ...)`)
**Testing**: pytest, hermetic. Network replaced by recorded fixtures under `tests/fixtures/012/`. `HOME` redirected to `tmp_path`.
**Target Platform**: macOS and Linux developer machines
**Project Type**: library + CLI scripts
**Performance Goals**: router decision adds under 50 ms (two small file reads plus one indexed SQLite count)
**Constraints**: ZDR stays on; only `:free` OpenRouter models; no coding tasks to free providers; P5 hard $0 per task
**Scale/Scope**: 3 free providers, about 25 OpenRouter catalog entries

## Existing code (evidence)

- Router order is `required + optional` (`agents_inc/router.py:62`), so claude and codex always precede free providers.
- Free providers are gated by `optional_allowed_tasks` (`agents_inc/router.py:70-72`; `agents_inc/routing.json:11` = `["extract", "summarize"]`).
- `task_tier` has no `classify` (`agents_inc/routing.json:10`).
- Router eligibility rejects only `status == "unavailable"` (`agents_inc/router.py:20`); many OpenRouter entries are `unprobed` (`agents_inc/models.json:137-357`).
- Grunt gemini default is `gemini-2.5-flash` (`agents_inc/routing.json:5`), but `gask.sh` maps tier `cheap` to `gemini-flash-lite-latest` (`skills/codex-bridge/scripts/gask.sh:36`).
- `oask.sh` hardcodes `deepseek/deepseek-v4-flash-0731:free` (`skills/codex-bridge/scripts/oask.sh:22`), which is not a catalog key. The spend guard refuses non-`:free` ids (`oask.sh:32-37`).
- Health file schema and cooldown logic live in `route.sh` (`skills/codex-bridge/scripts/route.sh:4`, `:80`, `:225-250`): `quota` sets 60-minute cooldown, or next UTC midnight for gemini. `agent_runner.py` calls `route.sh` (`skills/codex-bridge/scripts/agent_runner.py:542,591,605`). The wrappers do not.
- `quota_probe.sh` probes only Codex, by sending a generation (`skills/codex-bridge/scripts/quota_probe.sh:27`). It is not reused for OpenRouter.

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| P0 cross-reference, never duplicate | PASS | Health schema reused from `route.sh`; no second copy of cooldown fields. |
| P1 repo-scoped writes | PASS | Runtime writes only `~/.codex-bridge/*` state that already exists as a pattern (`route.sh:4`). |
| P2 labor ladder | PASS | tasks.md assigns haiku (small edits, tests) and sonnet (router, catalog refresh). |
| P4 deterministic policy over prompt | PASS | Ordering, caps, cooldowns are code plus `routing.json`, not prompt text. |
| P5 hard $0 per task | PASS | Refresh and probe make no generation calls; spend guard kept; ZDR not touched (FR-013). |
| P9 edit hygiene | PASS | Surgical edits to `router.py`, `routing.json`, `models.json`, wrappers. |

Post-design re-check: PASS. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/012-free-tier-routing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/cli.md
├── checklists/requirements.md   (from specify)
├── checklists/routing.md        (from checklist phase)
└── tasks.md
```

### Source Code

```text
agents_inc/
├── router.py            # edit: health/cap filter, budget free-first ordering
├── routing.json         # edit: classify, daily_caps, free_order, gemini cheap model
├── models.json          # edit: mark 5 stale OpenRouter entries unavailable
├── free_health.py       # new: health record read/write, outcome classify, model overlay
├── free_caps.py         # new: daily count from usage DB, cap lookup, OpenRouter limits probe
└── catalog_refresh.py   # new: dry-run/apply catalog refresh
skills/codex-bridge/scripts/
├── oask.sh              # edit: catalog default via free_health, report outcome
├── gask.sh              # edit: report outcome
└── mask.sh              # edit: report outcome
docs/DECISIONS.md        # edit: new D-entry for FR-014
tests/
├── fixtures/012/        # new: recorded model list, key-limits JSON, error bodies
├── test_free_health.py
├── test_free_caps.py
├── test_catalog_refresh.py
├── test_router_free_first.py
└── test_free_wrappers.py
```

**Structure Decision**: New logic lives in `agents_inc/` Python modules so the router and the Bash wrappers share one implementation. Wrappers call `python3 -m agents_inc.free_health ...`.

## Agent context update

Skipped. The speckit step edits `CLAUDE.md` markers; this run's scope allows writes only under `specs/012-free-tier-routing/`. Run root decides.

## Complexity Tracking

None.
