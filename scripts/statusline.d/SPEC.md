# statusline.d collector contract (frozen 2026-09-06)

CODEX 5H/7D percentages use the newest rollout `rate_limits.primary/secondary.used_percent`, not state_5.sqlite tokens. Window token cells (5H 1D 7D 28D) count only in-window tokens: usage rows from codex/openai backends and configured OpenAI model buckets, and per model the larger of that and the thread-store measurement (rollout `token_count` deltas per thread). Each cell's cost is priced from the same chosen source as its tokens, never from another. Thread lifetime totals (`threads.tokens_used`) stay the token source for ALL and SESS only; their cost uses the category method (running totals at each thread's last rollout event; no rollout: uncached input), the same as window cells and `pace.all_cost`. Percentages: rollout wins.

`collect_usage.py` (python3 stdlib only, no network, exit 0 always) writes
`~/.claude/statusline-cache/<session_id>.json` (per session, so concurrent sessions never overwrite each other; `statusline.sh` passes `--out`; files older than 7 days are pruned; without a session id the legacy `~/.claude/statusline-domi-cache.json` is used). Invoked by `statusline.sh` as
`timeout 5s python3 scripts/statusline.d/collect_usage.py --session-id ID --transcript PATH --session-start EPOCH`.
Skip the run when the cache file is < 60 s old AND its `session_id` matches.

## Inputs
- `config.json` (same dir): `subscriptions{claude,openai}` USD/month, `codex_config_toml` (default `~/.codex/config.toml`; empty string = no OpenAI pin),
  `openai_price_estimates` (merged over the built-in map, keyed by exact ids such as `gpt-5.6-sol`). `claude_models`, `openai_models` and `labels` in a config file are ignored: model rows are discovered, never configured (`DEFAULT_CONFIG.*_models` only pads a provider that has fewer than 4 ids).
  `prices_json` candidate paths, `usage_db` path, `codex_sessions_glob`.
- Claude transcript(s): `--transcript` file plus any `*.jsonl` under the sibling dir named after the session id
  (subagents). Rows: `.type=="assistant"`, `.message.model`, `.message.usage{input_tokens,output_tokens,
  cache_read_input_tokens,cache_creation_input_tokens}`. Dedupe on `.message.id`.
- `usage.db` table `usage(uid,ts,day,backend,model,input_tokens,output_tokens,cache_read,cache_write,reasoning)`.
  7d = `day >= date('now','localtime','-6 days')`. Session = `ts >= session_start` (ISO compare after converting epoch).
- Codex thread store: `~/.codex/state_5.sqlite`, table `threads`. Per model and window the larger of two sources wins (usage.db rows vs threads); the winner supplies tokens and cost. Session assigns threads created since the Claude session start whose `cwd` is the session's project dir (`--project-dir`); other projects' threads are not this session. Windows: 5H = Codex reset-5h; 1D, 7D (-6 days), 28D (-27 days) start at local midnight, same as usage.db. A thread's in-window tokens = rollout (`threads.rollout_path`) `event_msg/token_count` `info.total_token_usage.total_tokens` at the last event <= now minus at the last event before window start; input (cached split out), cache read, output give the cost split. Rollout missing or without events: thread counts its `tokens_used` only if created inside the window (no split: priced as input), else 0 and one `gap <window> <model> threads=<n> tokens=<n>` line appended to config `gap_log` (default `~/.claude/statusline-domi.log`, only if that file exists). Corrupt rollout line: that thread is dropped. Rollouts with mtime before the 28D start are skipped. Render with `~`. When the newest known Codex 5H `resets_at` is at or before now, the window has ended: OpenAI 5H tokens and cost (models, `openai_h5`, `provider_windows.openai.h5`) are 0 and `codex.h5.resets_at` is null (renderer shows a dash). Gap log: at most one line per run, `gaps openai <n> threads <tokens> tokens`, only when it differs from the last logged value (kept in cache key `gap_logged`); detail in cache key `openai_gaps`.
- Codex limits: newest line across `~/.codex/sessions/**/*.jsonl` (check the 3 newest files by mtime) containing
  `"rate_limits"` with `"limit_id":"codex"` and non-null `primary`. `primary` → 5h, `secondary` → 7d.
  Skip `limit_id=="premium"` (windows null). Record the line's `timestamp` field as `observed_at`.
- Window verification (2026-09-06): Claude Code supplies `rate_limits.five_hour` and `rate_limits.seven_day` in the statusline payload. The renderer copies `used_percentage` and reset epochs; it does not recompute usage. Anthropic describes current 5-hour and weekly usage-limit windows. Codex rollout `token_count.rate_limits` supplies `primary.window_minutes=300` and `secondary.window_minutes=10080`; the collector copies those server percentages and reset epochs. Official OpenAI documentation confirms 5-hour and weekly Codex windows. It documents account detail in Codex Settings/UI, not a public percentage API. Local rollout values are authoritative observations, not transcript-token calculations.
- Prices: `models[<id>]` with `input/output/cache_read/cache_write` $/MTok; strip a trailing `-YYYYMMDD` before lookup. Resolution chain, first hit wins: exact id; family (same provider and name stem across versions, nearest priced version at or below the id's, else lowest priced above; stems fable opus sonnet haiku astra sol terra luna); `openai_price_estimates` map; else `cost: null`. An id is never dropped for lacking an entry. NEVER invent a price. tokens = i+o+cr+cw.
- OpenAI model cells mark estimated cost with `~`. These ChatGPT-plan IDs have no entries in the price file: cost comes from the family or `openai_price_estimates` step, applied to the cell's own category split. `~$0` means estimated incremental subscription spend, not a metered API equivalent.

## Output schema (all keys always present; unknown → null)
{
  "schema": 1, "session_id": str, "generated_at": epoch_int,
  "codex": {"h5": {"used_pct": num|null, "resets_at": epoch|null}, "d7": {...}, "observed_at": epoch|null},
  "model_pins": {"claude": id|null, "openai": id|null},   # current models used for the row-4 pin: Claude = `--current-claude-model` (harness `.model.id`, `[1m]` tag and 8-digit date dropped; must start with `claude-`), OpenAI = top-level `model = "..."` of `codex_config_toml` (before the first [table]); null = no pin
  "models": {  # exactly 4 Claude rows then 4 OpenAI rows. One row per EXACT model id (only a trailing 8-digit date suffix is dropped; claude-opus-5 and claude-opus-5-5 are separate rows, no version-merging aliases). Rows = top 4 ids per provider by `d28.tokens` desc, then `all.tokens` desc, then id; shown in the same order (28-day ranking replaces the 2026-11-09 all-time ruling). Claude candidates start with `claude-`. A pin that is not in the top 4 replaces row 4; a pin inside the top 4 keeps its rank. Candidates: usage.db rows (backend claude | codex,openai), state_5 threads with tokens, transcript models, the pins
    "<model_id>": {"label": str, "provider": "claude"|"openai",
                   "session": {"tokens": int|null, "tokens_noncache": int|null, "cost": num|null},   # null = source absent; tokens_noncache = input+output+cache write (Claude: transcript; OpenAI: usage db; null when the Codex thread store raised the total)
                   "h5": {"tokens": int|null, "cost": num|null},   # cost = price x the same 5H rows as tokens (OpenAI: chosen per-model pair); 0 when the window is known and empty; null when unpriced or the source is absent
                   "first_seen": epoch_int|null,    # earliest record of this exact id (date suffix folded): min of usage.db MIN(ts) over every row of the id whatever backend it was stored under, and threads MIN(created_at); null when no source
                   "pace": {"usd_per_day": num|null, "days": num|null, "hist_days": num|null, "all_cost": num|null, "source": "own"|"family"|null},   # baseline for pace colouring (dollars). history = now - first_seen in days. own when history >= 7: days = min(28, history) floor 1, usd_per_day = d28.cost / days, all_cost = the id's lifetime cost. Else family (provider + stem via parse_family, summed over EVERY family member, shown or not): days from the earliest family first_seen, usd_per_day = family d28 cost / days, all_cost = family lifetime cost. hist_days = uncapped history of the chosen source. No family and no own baseline: every field null. source null implies usd_per_day null. OpenAI all_cost uses the category method of d28.cost (running totals at each thread's last rollout event; no rollout -> uncached input); the ALL cell uses the same method, so `all.cost == pace.all_cost` for an own-source OpenAI model.
                   "d1": {"tokens": int|null, "cost": num|null},
                   "d7": {"tokens": int|null, "cost": num|null},
                   "d28": {"tokens": int|null, "cost": num|null},
                   "all": {"tokens": int|null, "cost": num|null}}    # 28-day "Mo" window, same sources/rules as d7; never < d7
  },
  "openai_total_d7": {"tokens": int, "requests": int},   # includes null-model codex rows
  "claude_d7": {"tokens": int, "cost": num|null},
  "claude_today": {"tokens": int, "cost": num|null},    # local calendar day, same day cutoff as usage.db
  "openai_today": {"tokens": int, "cost": num|null},    # local calendar day, same day cutoff as usage.db
  "free_top4_d7": [{"backend": str, "model": str, "tokens": int,     # gemini|mistral|openrouter; top 4 by all-time tokens (key name kept); tokens = 7D sum
                    "session": {"tokens": int, "cost": float|null, "equiv_cost": float|null},   # ts >= --session-start (fallback uid == session_id)
                    "d7": {"tokens": int, "cost": float|null, "equiv_cost": float|null},
                    "first_seen": epoch_int|null, "pace": {same shape as models[id].pace; dollars are equiv_cost}}],      # cost = metered (free tier -> 0/null); equiv_cost = Anthropic-API-equivalent at config.free_price_estimate tier (haiku), rendered with `~`
  "cum_use": {"tokens": int, "cost": num|null},           # ALL usage.db rows ever (max'd against state_5 all-time for the OpenAI share), priced at Anthropic API equivalents: direct price -> openai_price_estimates -> free_price_estimate -> cum_default_estimate (sonnet)
  "claude_all": {"tokens": int, "cost": num|null},        # all-time Claude rows, no time filter, same classification/cost model as claude_today/claude_h5
  "openai_gaps": {"threads": int, "tokens": int}|null,   # OpenAI threads with no usable rollout and activity in a window, and their lifetime tokens; null when the thread store is absent
  "gap_logged": {"threads": int, "tokens": int}|null,    # last value written to gap_log; collector state
  "openai_all": {"tokens": int, "cost": num|null},        # all-time OpenAI rows (incl. state_5 lifetime totals, larger of two sources like cum_use), same classification/cost model as openai_today/openai_h5
  "free_all": {"tokens": int, "equiv_cost": num|null},    # all-time free-backend rows (gemini|mistral|openrouter), Anthropic-API-equivalent cost like free_top4_d7's equiv_cost
  "free_windows": {"session": W, "today": W, "d28": W},   # W = {"tokens": int, "equiv_cost": num|null}; ALL free-backend rows (gemini|mistral|openrouter) in the window (session: ts >= --session-start, fallback uid == session_id; today: local day; d28: last 28 local days)
  "session_list_cost": num|null,                          # sum of models[*].session.cost (claude only)
  "sub_ratio_d7": {"claude": num|null, "openai": null},   # cost_d7 / (sub_usd * 7/30)
  "blended_usd_per_mtok_d7": {"claude": num|null, "openai": null},
  "history_days": {"claude": num|null, "openai": num|null, "free": num|null}   # days from the provider's earliest usage record to now (float, uncapped); null = no record. Renderer caps at 28 for pace baselines.
  "provider_windows": {"claude": PW, "openai": PW, "free": PW}   # PW = {"h5": T, "d1": T, "d7": T, "d28": T, "all": T}, T = {"tokens": int|null, "cost": num|null}. All of the provider's rows, every model including ones without a model cell (retired ids). Same sources and cost model as claude_h5/claude_today/claude_d7/claude_all, openai_h5/openai_today/openai_total_d7/openai_all, free_windows/free_all (free cost = equiv_cost). d1 = local today; d28 = last 28 local days. null = unknown.
}
Labels (`models[id].label`, derived from the id; the renderer derives the same string itself): `claude-<family>-<major>[-<minor>]` -> "Fable 5.1", "Opus 5.5", "Opus 5", "Sonnet 5", "Haiku 4.5";
`gpt-<version>[-<name>]` -> "GPT-6 Astra", "GPT-6.2 Astra" (each id keeps its own label and row; a superseded id such as `gpt-6-astra` stays labeled and takes the same Executive rung colour), "GPT-5.6 Sol", "GPT-5.6 Terra", "GPT-5.6 Luna". Any other id passes through (renderer cuts it to 13 columns).
Ranking key = (`d28.tokens` desc, `all.tokens` desc, id); a pin outside the top 4 takes row 4 and sorts by the same key (low pin last); ids with 28D 0 (retired) drop out unless pinned. Σ/$ rows stay provider totals.

## Renderer layout

`statusline.sh` draws a 6-row box: border `║`, four cells split by `│`, border `║`. Cells: left column, ANTROP, OAI, FREE. Widths `19 43 43 <fnw+30>`; `fnw` = longest `fname` free-model label (cap 8), minimum 7. The top border carries the labels: `═ <session name> ` padded to 20 columns (`sess_name`, 14 columns max, default `STATUS`), then `═ ANTROP `, `═ OAI `, `═ FREE ` each followed by the right-aligned window labels `SESS`, `5H`, `1D`, `7D`, `28D`, `ALL`. Bottom border `╚═╝` spans the same width.

Left column (19 wide), one item per row; gauges are `sub2` cells (`<LBL> <5-cell bar>` with a 2-digit value inside the bar, `--` when unknown):
- Row 1: `CLK` session time (`45s`, `23m`, `1h23m`, `13.7h`, `2d3h`) then `DSK` gauge (disk percent of `/System/Volumes/Data`).
- Row 2: `DIR` project name (5 columns max, middle-ellipsis) then `RAM` gauge (percent used).
- Row 3: branch name only (no label; last path segment, `development` and `develop` stay as given, 9 columns max with `…`; no dirty or ahead markers are drawn) then `CPU` gauge.
- Row 4: `TPM` (non-cache session tokens per minute) then `GPU` gauge. When the cache is stale and readable (`win_stale=1`, `cache_ok=1`), the TPM cell shows `AGE <n><unit>` instead (cache age since `generated_at`, `<n>s`, `<n>m`, `<n>h` or `<n>d`, largest unit giving a whole number of at least 1), value in `CD`, same 10-column cell.
- Row 5: `TOK` (all-time tokens, `tok6`) then `EFF` gauge (effort level: bar 20/40/60/80/100 percent for low to max; inside text `LO ME HI XH MX`, else `--`).
- Row 6: `DOL` (all-time dollars) then `CTX` gauge (context percent scaled to the auto-compact window: `modelSettings.<model-id>.autoCompactWindow` (what `/autocompact` writes; `auto` = no scaling), else top-level `autoCompactWindow`, else the context window).

Provider blocks, rows 1-6 of each:
- Name field: ANTROP and OAI 13 columns, FREE `fnw` columns. Six window cells follow, 5 columns each, right-aligned: `SESS 5H 1D 7D 28D ALL`.
- Rows 1-4: four model rows. Name from the exact id (`Opus 5.5`, `GPT-5.6 Sol`; other ids pass through, 13 columns max; FREE uses `fname`), coloured by tier (`tier_color`). The model this session runs on is drawn in reverse video (ANTROP and OAI only). Tokens: `tok` for SESS, 5H, 1D; `tokB` for 7D, 28D, ALL on ANTROP and OAI; FREE uses `tok` in every column.
- Row 5, `Σ`: provider token totals. On ANTROP and OAI the name field holds the 5H quota: a 5-cell bar (`lbar`, 5% steps) with `5H` inside, one space, the reset countdown (`lrst`, 5 columns, `—` when unknown), then ` Σ` at the right edge of the 13 columns. The bar label becomes `NN%5H` from 90 percent and `100%` at 100 or more. Percent and reset: ANTROP from the payload `rate_limits.five_hour`, OAI from the Codex rollout (`codex.h5`). FREE has no quota: the name field is a right-aligned `Σ`.
- Row 6, dollar row: provider dollars, `cost` formatter without the leading `$`. Name field holds the 7D quota the same way (`7D` label, `lrst` with a 604800 s window) and ends with ` $` on ANTROP, ` ~` on OAI (estimated pricing). FREE has the same row with a right-aligned `$` and no quota; its figures are Anthropic-API equivalents.
- Σ and dollar window cells: SESS is the sum of the four model rows. 5H, 1D, 7D, 28D, ALL are max(`provider_windows` value, sum of the four rows); a missing `provider_windows` value falls back to the row sum. 5H dollars come from the provider-level cache fields `claude_h5.cost` and `openai_h5.cost`; FREE sums its row 5H costs.
- Row source: ANTROP = first 4 `claude*` ids of the cache `models`, OAI = first 4 other ids, FREE = first 4 of `free_top4_d7` (collector order, see `models` above). Without a cache the placeholder roster shows dashes.
- Free-model labels (`fname`): drop `vendor/` prefix, `:free` suffix, size tokens and noise words (`latest preview instruct free exp it`); numerals keep their digits without dots; words use the alias table or first letter plus up to 3 consonants; hard cut at 8.

**Color model.** Palette assigns colours to roles, not widgets.

| Role | Name | RGB | Use |
|---|---|---|---|
| Chrome | `CB` | 120,86,168 | Box borders (`╔═╗╚╝║`) |
| Chrome | `CS` | 84,78,104 | Interior separators (`│`) |
| Label + names | `CN` | 158,166,190 | Gauge labels, `Σ`, `$`, unclassified model names, neutral cells |
| Model tier (ultra) | `CT1` | 130,245,205 | Model-row names: Fable, Astra, ultra, flagship, Mistral Large, DeepSeek Pro |
| Model tier (flagship) | `CT2` | 112,213,186 | Opus, Sol, Pro, Maverick, DeepSeek V4, Mistral Medium, grok |
| Model tier (workhorse) | `CT3` | 95,182,167 | Sonnet, Terra, Scout, standard, DeepSeek Chat, Mistral Small |
| Model tier (flash) | `CT4` | 77,151,148 | Haiku, Luna, fast, flash |
| Model tier (bottom) | `CT5` | 60,120,130 | lite, ministral |
| Name lightness | `CNM` / `CNC` / `CNO` | 245,245,253 / 199,199,207 / 158,158,166 | `DIR` value: `DomI` (bold, `CNM`), repo with `.domi-pin` (`CNC`), other (`CNO`) |
| Branch main/master | `CNM` bold | 245,245,253 | Branch name on `main`, `master` |
| Branch develop | `CNC` | 199,199,207 | Branch name on `develop`, `development`, `dev` |
| Branch other | `CN` | 158,166,190 | Any other branch or detached HEAD |
| Magnitude ramp | — | cyan 0,224,255 → magenta 255,102,214 (literals inside `ramp_c`) | Token/cost cells (below), percent bars (`level()` = pct×10 permille), gauges, countdowns, CLK, TPM |
| Zero/unknown | `CD` | 128,128,136 | No data, null values, empty cells, stale window cells |

Model tier classification: `tier_color` lowercases the name (ids become words) and matches by substring, first match wins: lite/ministral `CT5`; fast/flash/haiku/luna `CT4`; fable/astra/ultra/behemoth/flagship/mistral large/deepseek pro `CT1`; opus/sol/pro/maverick/deepseek v4/mistral medium/grok `CT2`; sonnet/terra/scout/standard/deepseek chat/mistral small `CT3`; anything else `CN`. Tier colours are one teal lightness scale (`teal_color`), separate from the cyan to magenta ramp.

Branch colour: name only, by kind (table above). The git dirty and ahead counts are computed but not drawn.

**Token colour model.** One continuous ramp (cyan → magenta, `ramp_c`) serves every cell; only the input changes.

- Percent bars (`level()`): permille = percent × 10. Unchanged by the token bands. Missing or non-numeric input renders `CD`.
  - Unchanged by the 2026-11-15 rulings (item 13).
- Model cells in SESS, 5H, 1D, 7D, 28D (operator, 2026-11-15): colour = pace, "is this burning faster than normal". The number shown stays tokens; the colour input is API-equivalent dollars (about 96 percent of shown Opus tokens are cache reads).
  - Ratio `r` = cell cost / expected cost. Expected = `pace.usd_per_day` × window days, from the model's own 28-day rate (collector `pace` block: `usd_per_day`, `days`, `hist_days`, `all_cost`). FREE rows pace like any other row (`equiv_cost`, free `pace`).
  - Window hours: SESS = session duration, `CD` under 5 min (operator, 2026-11-18; was 30 min; constant `PACE_SESS_FLOOR_S` in `statusline.sh`); 5H = 5, cost from `h5.cost` (an ended window gives 0, so `CD`); 1D = hours since local midnight, floor 6; 7D = min(168, `days` × 24).
  - 28D cell: expected = `pace.all_cost` × 28 / `pace.hist_days`; neutral `CN` when `hist_days` ≤ 28.
  - Mapping: permille = clamp(500 + 250 × log2 r, 0, 1000). r ≤ 0.25 cyan (0,224,255), r = 1 mid (127,163,235), r ≥ 4 magenta (255,102,214).
  - Zero, null or missing pace or cost render `CD`. A cache without the pace fields still renders (all such cells `CD`). Stale-cache dimming (trust rules) still applies.
  - ALL column keeps log share of the column max across the 3 providers (`sharecols`); model-name colours and gauges are unchanged. No legend or glyph on screen.
- Σ token cells (operator, 2026-10-02, third pass): colour = pace against the provider's own history, log scale. Same rule as the dollar cells below, with tokens in place of dollars (Σ 28D cell is the baseline).
  - Same pace mapping and cost-weighted quantity as the model cells (range 250×, r ≤ 0.25 cyan, r ≥ 4 magenta); the shown number stays tokens.
- Σ and `$` values (operator, 2026-10-02, fourth pass): the 5H, 1D, 7D, 28D and ALL cells show the provider total from `provider_windows` (all models, retired ids included), not the sum of the model rows above. A Σ cell can therefore exceed its column's row sum, mostly in 28D and ALL. SESS stays the row sum. Each window cell shows max(provider total, row sum): a provider total covers every model, so a lower figure means a pricing-source gap (OAI `d28` cost comes from the usage db, its model rows from Codex threads). A missing `provider_windows` value falls back to the row sum. Why: the model rows cover only the 4 configured models per provider; most older use sat on retired ids, so a row-sum 28D baseline was about half the real one and every window read hot.
  - The fifth window label is `28D`, 28 calendar days. OpenAI 7D uses calendar days like Claude.
- Dollar cells (operator chose the Opus design, 2026-10-02): colour = pace, each provider against its own 28-day rate. `$` values are API-equivalent figures, not money paid (plans: Claude $100, ChatGPT Plus $20 a month), and OAI uses a different pricing method from ANT, so cross-provider `$` comparison is not meaningful. A ratio against the provider's own baseline has no units, so the pricing bias cancels.
  - Baseline: `d28` = that provider's 28D cell (the collector's 28-day window). `days` = min(28, `history_days[provider]`), floor 1. Expected for a window = `d28 × window_hours / (days × 24)`. Without `history_days`, `days` = 28. (Third pass: dividing by 28 when history is shorter made every window read hot.)
  - Window hours: 5H = 5. 7D = min(168, days × 24). 1D = hours since local midnight, floor 6. SESS = session duration (`cost.total_duration_ms`); a session under 5 min renders `CD` (operator, 2026-11-18; was 30 min; same `PACE_SESS_FLOOR_S`).
  - Ratio `r = value / expected`. permille = clamp(500 + 250 × log2 r, 0, 1000): r ≤ 0.25 cyan, r = 1 mid, r ≥ 4 magenta.
  - 28D cell (operator, 2026-10-02, fifth pass): pace against the lifetime rate. Expected = ALL × 28 / `history_days`; r = 28D / expected; same log mapping. When `history_days` ≤ 28 (or unknown), 28D is most of ALL: neutral `CN`.
  - ALL cell (operator, 2026-10-02, sixth pass): log share across the 3 providers' ALL values, the same mapping as model cells (max magenta, max/1000 or less cyan). Applies to Σ and `$` ALL alike; OpenAI `$` is priced by category like Claude (spec 043 T025a); price tables still differ, so the `$` comparison is rough. Zero or missing renders `CD`.
  - Noise floor (operator, 2026-10-02, fifth pass): only a zero, missing or non-numeric cell renders `CD`, or every cell of a provider whose `d28` is zero. No $1 / 1M-token cell floor; it greyed real low use (OAI 5H 498k against about 1.3M expected).
  - The OAI `$` row label is `~` (estimated pricing). Cells stay 5 wide; no per-cell marker.
- TPM: non-cache session tokens (`session.tokens_noncache`, input + output + cache write) per elapsed minute. Fixed bands: lo 2k, mid 20k, hi 200k. `—` when the session is untrusted.
- TOK (all-time tokens): neutral `CN` (operator, 2026-10-02). `CD` when the cache is unreadable.
- DOL (all-time cost): neutral `CN`. It sums three pricing methods and supports no decision.
- CLK (session length, operator 2026-10-02): hue ramp, log scale. permille = clamp(500 + 500 × log(s / 3600) / log 6, 0, 1000), s = session seconds: 10 min or less cyan, 1 h mid, 6 h or more magenta. Bold kept.
- Countdown text (`lrst`): ramp by elapsed fraction of its window (5H 18000 s, 7D 604800 s), clamped 0–1. Missing, zero, negative or non-numeric `resets_at` renders `—` in `CD`.
- Cost: cents below $0.50 (`$.01`, `$<.01`, `.40`); `—` for null, negative or non-numeric. Token text: `k`/`M` below 100M, `B` from 100M (switch points 9.95M and 9.95B round up).


**Trust rules.** Unknown is not zero.

- `cache_ok=0` (cache unreadable): every figure renders `—`.
- `sess_ok=0` (payload `session_id` empty or different from the cache `session_id`, or cache older than 300 s): SESS and TPM render `—`, and session sums are `—`. Exception (spec 042 FR-030, operator ruling 2026-11-16 "Age in the left column"): with a readable cache that is stale, the TPM cell shows `AGE <n><unit>` (cache age) in `CD` instead of the dash, so a stored value is never taken for a live one; a fresh cache keeps TPM, an unreadable cache keeps the dash, and no glyph, legend or width change is added.
- `win_stale=1` (cache older than 300 s): window cells render `CD`. No `~` prefix, so widths stay fixed.
- A model key absent from the cache renders `—`, not `0`. A sum with no known term renders `—`.

**Colour modes.** `NO_COLOR` (non-empty): no colour sequences; bars draw `█` full, `▒` edge, `░` track. `COLORTERM` set to anything except `truecolor`/`24bit`, or `STATUSLINE_COLORS=256`: 256-colour escapes (`38;5;n`). Otherwise truecolor (also when `COLORTERM` is unset). Box width is identical in every mode.

## Open items

1. Free models run from the delegate pane are stored under backend `claude` and counted as Claude (free ALL is short by about 400k). Not approved by the operator; record only, do not implement.
2. Claude 5H ended-window fault: the collector computes the Claude 5H window start as `resets_at` minus 5 h without comparing `resets_at` with now, so a reset time already in the past keeps showing the ended window's figures. The OpenAI path was fixed in spec 043 (5H is 0 and the reset is null); the Claude path was not changed.
3. Stale quota percent: when the 5H reset time is in the past or null, the quota percent still shows the last value read for the ended window (seen 2026-11-16: Codex 69 percent with a null reset).

## Gates
1. `bash -n` + `shellcheck -S warning` clean on any .sh touched. 2. `python3 -m pytest scripts/tests/test_collect_usage.py -q` all pass.
3. `bash scripts/tests/statusline_smoke.sh` → `smoke: N/N checks passed`. 4. `time bash scripts/statusline.sh < fixture` (warm cache): real < 0.40s in an unsandboxed terminal; inside the Claude Code sandbox the same render measures about 0.9s, so there the gate is "no slower than the recorded baseline plus 10 percent, timed the same way" (supervisor ruling 2026-11-15, spec 043). Also there: gate 1 is "no new shellcheck finding against a recorded baseline" (the renderer has existing findings), and gate 2 runs as `/opt/homebrew/bin/pytest` when `python3 -m pytest` has no pytest.
5. Missing usage.db / prices / codex sessions → nulls + exit 0, never a traceback.

## Operator rules (moved from machine AGENTS.md, 2026-11-07)

- `scripts/statusline.sh` is the only live status line (moved from DomI on 2026-10-11, operator instruction). `~/.claude/settings.json` runs `bash ~/Projects/agents-inc/scripts/statusline.sh`.
- Retired copies: `~/Projects/DomI/scripts/statusline.sh` and `~/.claude/statusline/vaporwave.sh` with its `.bak` copies. Do not edit them or point settings back at them. Do not create a second script.
- Verify every change yourself with the Gates above. Delegate reports of a working status line have been wrong before.
- Never drop the box border or the subtable separators.
- Measure width in terminal columns, not bytes or characters. Box-drawing glyphs are multi-byte; an emoji is one character but two columns.
- Errors go to `~/.claude/statusline-domi.log` when that file exists. `ingest_usage.py` feeds `~/.codex-bridge/usage.db` in the background on a time throttle and never blocks the render.
