<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Research: Free-Tier-Aware Routing

## R1 Where cooldowns live
- Decision: reuse `~/.codex-bridge/backend-health.json` with `route.sh` field names (`status`, `cooldown_until`, `last_error`; `skills/codex-bridge/scripts/route.sh:80,225-250`). Add `failure_streak` per backend. Backend keys reuse `route.sh` names (`route.sh:77`): `mistral`, `openrouter`, and `gemini-flash-lite` / `gemini-flash` chosen by the gemini model (lite model id contains `flash-lite`). Router treats gemini as cooled down when the key for its configured grunt model is in cooldown.
- Rationale: one shared record (FR-003); `agent_runner.py` already feeds it.
- Alternatives: new file (rejected, splits truth).

## R2 Where model withdrawals live
- Decision: overlay file `~/.codex-bridge/model-status.json` `{model_id: {"status": "unavailable", "reason": "withdrawn|zdr", "at": iso}}`. Router and default pick merge overlay over `models.json`. Catalog refresh `--apply` clears overlay entries it re-evaluates.
- Rationale: runtime must not mutate tracked repo files; FR-005 "until next refresh".
- Alternatives: write `models.json` at runtime (rejected, dirty tree); per-model keys in health file (rejected, `route.sh` status listing iterates every key, `route.sh:283`).

## R3 Backoff
- Decision: cooldown = provider retry delay if parsed (`Retry-After` header, or text "retry in Ns"), else `min(60 * 2**(streak-1), 3600)` s. Success resets streak (FR-004).

## R4 Atomic write
- Decision: write temp file in same dir, `os.replace`. Last write wins, no partial file (edge case). Corrupt/missing file: treat healthy, one stderr warning (FR-015).

## R5 Daily count
- Decision: count rows in usage DB `usage` table where `day = today UTC` and `backend = provider`. If DB missing or wrappers' calls not ingested, fall back to a per-day counter in the health file (`calls_today`, `calls_day`) incremented by `free_health report`.
- Rationale: [inferred] usage DB ingests delegated usage (`usage_db.py:154`); unclear whether standalone wrapper calls reach it. Counter in health record guarantees FR-008.

## R6 Limits probe
- Decision: `GET https://openrouter.ai/api/v1/key` (key metadata, no generation). Store `{openrouter: {cap, source: "probed", at}}` in `~/.codex-bridge/free-caps.json`. Key read same way `oask.sh` reads it (`oask.sh:54`), never printed.

## R7 Modality
- Decision: env `AGENTS_INC_MODALITY` in {`ideal`, `budget`}; unset or other = `ideal`. Name [assumed]; spec says only "environment variable".

## R8 Free order and gemini model
- Decision: `routing.json` gains `"free_order": ["mistral", "gemini", "openrouter"]`, `"daily_caps": {"mistral": 500, "gemini": 200, "openrouter": 50}`, grunt gemini = `gemini-flash-lite-latest`, `task_tier.classify = "grunt"`, `optional_allowed_tasks += "classify"`.

## R9 Catalog refresh source
- Decision: public `GET https://openrouter.ai/api/v1/models` (no key). Free = id ends `:free` or all pricing fields `"0"`. Non-text modality (output not text) = unavailable for all tasks. Tests use `--from-file` fixture.
