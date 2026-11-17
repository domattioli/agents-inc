<!-- provenance: author=domattioli model=claude-opus-5-5 effort=low date=2026-11-15 skill=speckit-plan repo=agents-inc session=b437620e -->
# Contract: collector cache additions (spec 043)

Producer `scripts/statusline.d/collect_usage.py`; consumer `scripts/statusline.sh` (one `jq` call). Additive only: `schema` stays 1, every existing key keeps name, type and meaning except where marked CHANGED. Unknown -> null, never 0. Old renderer must run against the new cache unchanged (jq ignores new keys); new renderer must run against an old cache (missing keys -> `—` -> grey).

## models.<id> (shown rows, 4 claude then 4 openai)

```
"h5":   {"tokens": int|null, "cost": num|null}          # NEW cost; same row set as tokens
"first_seen": epoch_int|null                            # NEW; min over usage.db MIN(ts) and threads MIN(created_at) for this exact id (date suffix folded)
"pace": {                                               # NEW; baseline for pace colouring
  "usd_per_day": num|null,   # own: d28.cost / days; family: family d28 cost / family days; null when no baseline or cost unknown
  "days":        num|null,   # min(28, history), floor 1; history = own when own >= 7 days, else family
  "hist_days":   num|null,   # uncapped history days of the chosen source (own or family); 28D cell is neutral when <= 28
  "all_cost":    num|null,   # lifetime dollars of the chosen source (own all.cost or family sum)
  "source":      "own"|"family"|null
}
"session"|"d1"|"d7"|"d28"|"all": unchanged shape; CHANGED meaning for openai:
  h5/d1/d7/d28 tokens = in-window tokens (rollout delta, R1), not lifetime thread totals
  cost = priced from the same row set as tokens (category split), never input-rate-only
  d7/d28 start at local midnight (calendar days)
```

## free_top4_d7[*]

Each entry gains `first_seen` and `pace` with the same shape; dollars are `equiv_cost`. `h5.equiv_cost` already exists.

## openai_h5 / provider_windows.openai.h5 — CHANGED

`tokens` and `cost` = sum over OpenAI models of the chosen per-model (tokens, cost) pairs plus null-model usage.db codex rows. Cost null only when no contributing term has a price.

## openai_gaps / gap_logged — NEW (added 2026-11-16, Phase 2 T013a)

```
"openai_gaps": {"threads": int, "tokens": int} | null   # OpenAI threads with activity in a window and no usable rollout, and their lifetime tokens; null when the thread store is absent
"gap_logged":  {"threads": int, "tokens": int} | null   # collector state: the last value written to gap_log; one `gaps openai <n> threads <tokens> tokens` line is appended only when the value changes and n > 0
```

Ended 5H window: when the newest known Codex 5H `resets_at` is at or before now, OpenAI `h5` tokens and cost are 0 for every model, `openai_h5` and `provider_windows.openai.h5`, and `codex.h5.resets_at` is null.

## Ordering — CHANGED

`models` order: Claude top 4 by (`d28.tokens` desc, `all.tokens` desc, id asc), then OpenAI the same. Claude candidates must start with `claude-`. A pin outside the top 4 replaces row 4 and sorts by the same key.

## Price resolution (internal, documented in SPEC.md Inputs)

`price_for(id)`: exact -> date-stripped -> family nearest (same provider and stem; highest priced version <= id's, else lowest above) -> `openai_price_estimates[id]` -> null.

## Invariants (tested)

- `d28.tokens >= d7.tokens` and `all.tokens >= d28.tokens` per model (existing).
- OpenAI `h5.tokens <= d1.tokens`-or-window-overlap is not asserted (5H can start before midnight); asserted instead: per-thread in-window tokens <= the fixture recount.
- `pace.source == null` implies `pace.usd_per_day == null`.
- Exit 0 and every key present when usage.db, state db, rollouts or prices are missing.
