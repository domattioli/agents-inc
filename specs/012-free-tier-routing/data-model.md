<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Data Model: Free-Tier-Aware Routing

## Catalog entry (`agents_inc/models.json`, existing)
Fields: `vendor`, `provider`, `tier`, `tasks_good[]`, `tasks_bad[]`, `ctx_hint`, `cost_class`, `status` in {available, unprobed, unavailable}.
Rules: new refresh entries get `tasks_good: []` (FR-007). Effective status = overlay status if present, else catalog status.

## Model status overlay (`~/.codex-bridge/model-status.json`, new)
`{model_id: {status: "unavailable", reason: "withdrawn"|"zdr", at: ISO8601}}`. Cleared per model by `catalog_refresh --apply`.

## Health record (`~/.codex-bridge/backend-health.json`, existing schema + fields)
Per backend: `status`, `cooldown_until` (ISO or null), `last_error`, new `failure_streak` (int), `calls_day` (YYYY-MM-DD UTC), `calls_today` (int).
Transitions: success -> streak 0, cooldown null, status ok. 429/503 -> streak+1, cooldown per R3, status degraded. 404-withdrawn/ZDR -> overlay write, backend unchanged. other -> last_error only.

## Daily cap
Source order: probed (`~/.codex-bridge/free-caps.json`, openrouter only) over configured (`routing.json` `daily_caps`). Day boundary UTC.

## Outcome enum
`ok`, `withdrawn`, `zdr`, `rate_limited` (429), `overloaded` (503), `error`.
