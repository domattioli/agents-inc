<!-- provenance: author=domattioli model=claude-opus-5-5 effort=low date=2026-11-15 skill=speckit-plan repo=agents-inc session=b437620e -->
# Data model: Status line true tallies and pace colours

Cache shape: `contracts/cache-schema.md`. Here: entities, rules, derivations.

## Model id
- Exact id after `strip_model_version` (drop trailing `-YYYYMMDD`). Versions never merge.
- `provider`: `claude` when id starts `claude-`; `openai` for usage.db backend `codex|openai` and state_5 thread models; free backends separate.

## Family
- `parse_family(id) -> (provider, stem, (major, minor))` or None.
- Claude: `claude-<stem>-<major>[-<minor>]`, stems fable opus sonnet haiku. OpenAI: `gpt-<major>[.<minor>]-<stem>`, stems astra sol terra luna.
- Members: all ids with the same (provider, stem) seen in any source (usage.db, threads, transcript, prices file for pricing).
- Order: tuple compare of (major, minor); missing minor = 0.

## Price entry
- `prices.json models[id]`: input, output, cache_read, cache_write USD/MTok.
- Resolution `price_for(id)`: exact -> date-stripped -> family nearest (highest priced <= version, else lowest priced above) -> `openai_price_estimates[id]` -> None.
- Cost of a usage set = sum over categories; a category missing in the entry counts 0 (as today, `calculate_cost`).
- None -> cost null -> renders `—`; pace cells of that model grey.

## Window
| Key | Label | Start | Claude source | OpenAI source |
|---|---|---|---|---|
| session | SESS | session start | transcript | usage.db ts; threads created since start in project cwd (lifetime) |
| h5 | 5H | reset - 5 h (payload for Claude, rollout `rate_limits` for Codex) | usage.db ts | max(usage.db, rollout delta) per model |
| d1 | 1D | local midnight | usage.db day | same |
| d7 | 7D | local midnight - 6 d | usage.db day | same |
| d28 | 28D | local midnight - 27 d | usage.db day | same |
| all | ALL | none | usage.db | max(usage.db, threads lifetime) |

## Thread in-window measurement
- Input: thread (rollout_path, created_at, tokens_used, model), window start S, now.
- Rollout readable with >= 1 `token_count` event: tokens = T(last event <= now) - T(last event < S), T = `info.total_token_usage`; categories: uncached input = input - cached, cache_read = cached, output = output, cache_write = `cache_write_input_tokens` (0 today).
- Otherwise: created_at >= S -> tokens_used counted; categories unknown, so that share is priced at the input rate and the cell keeps the `~` mark (the only estimate left; logged); created_at < S -> 0 and a gap log line.
- Per model and window: thread sum vs usage.db sum; larger wins and supplies its cost.

## Row
- Candidates per provider (Claude prefix `claude-`), ranked by (d28.tokens desc, all.tokens desc, id asc).
- Pin (Claude: `--current-claude-model`; OpenAI: codex config top-level model) outside top 4 replaces row 4.
- Non-shown models stay in `provider_windows`.

## First seen and pace baseline
- `first_seen[id]` = min(usage.db MIN(ts), threads MIN(created_at)).
- own_hist = (now - first_seen) / 86400.
- own_hist >= 7: source own, hist = own_hist, d28c = own d28.cost, allc = own all.cost.
- else family exists with any member first_seen: source family, hist = (now - min family first_seen)/86400, d28c = sum family d28.cost, allc = sum family all.cost. (Family hist under 7 still used, floor 1 day.)
- else: source null, all fields null -> grey.
- days = clamp(hist, 1, 28); usd_per_day = d28c / days when d28c known and > 0, else null.

## Pace ratio and colour (renderer)
- Window hours h: SESS = session seconds / 3600 (under 1800 s -> grey); 5H = 5; 1D = hours since local midnight, floor 6; 7D = min(168, days × 24).
- SESS, 5H, 1D, 7D: r = cell dollars / (usd_per_day × h / 24).
- 28D: hist > 28 and allc > 0 -> r = d28 dollars / (allc × 28 / hist); else neutral `CN`.
- permille = clamp(500 + 250 × log2 r, 0, 1000). r <= 0.25 cyan, 1 mid, >= 4 magenta.
- Grey `CD`: cell dollars missing/zero/non-numeric, usd_per_day null or 0, stale cache (existing rule).
- Σ token cell colour = the Σ dollar cell's colour (same CSUM pace); Σ and $ provider rules keep their baseline (provider d28, `history_days`) with the new range.
- ALL column: unchanged log share (`sharecols`).
