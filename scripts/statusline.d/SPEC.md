# statusline.d collector contract (frozen 2026-09-06)

CODEX 5H/7D percentages use the newest rollout `rate_limits.primary/secondary.used_percent`, not state_5.sqlite tokens. `OPENAI 7D <tokens>` sums usage rows from codex/openai backends and configured OpenAI model buckets, with state_5.sqlite `threads.tokens_used` as fallback. If sources disagree, rollout wins for percentages and state tokens win for token counts.

`collect_usage.py` (python3 stdlib only, no network, exit 0 always) writes
`~/.claude/statusline-domi-cache.json`. Invoked by `statusline.sh` as
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
- Codex fallback: `~/.codex/state_5.sqlite`, table `threads`. Use it when a configured OpenAI model has no bridge-DB rows. Session assigns threads created since the Claude session start whose `cwd` is the session's project dir (`--project-dir`); threads from other projects, such as Codex app chats, are not this session. 7d assigns threads updated in the preceding 168 hours. `tokens_used` is exact per thread; time-window attribution is estimated because a thread can cross a boundary. Render these values with `~`.
- Codex limits: newest line across `~/.codex/sessions/**/*.jsonl` (check the 3 newest files by mtime) containing
  `"rate_limits"` with `"limit_id":"codex"` and non-null `primary`. `primary` → 5h, `secondary` → 7d.
  Skip `limit_id=="premium"` (windows null). Record the line's `timestamp` field as `observed_at`.
- Window verification (2026-09-06): Claude Code supplies `rate_limits.five_hour` and `rate_limits.seven_day` in the statusline payload. The renderer copies `used_percentage` and reset epochs; it does not recompute usage. Anthropic describes current 5-hour and weekly usage-limit windows. Codex rollout `token_count.rate_limits` supplies `primary.window_minutes=300` and `secondary.window_minutes=10080`; the collector copies those server percentages and reset epochs. Official OpenAI documentation confirms 5-hour and weekly Codex windows. It documents account detail in Codex Settings/UI, not a public percentage API. Local rollout values are authoritative observations, not transcript-token calculations.
- Prices: `models[<id>]` with `input/output/cache_read/cache_write` $/MTok; strip a trailing `-YYYYMMDD` before lookup.
  Missing price → `cost: null`. NEVER invent a price. tokens = i+o+cr+cw.
- OpenAI model cells mark state-DB time attribution and cost with `~`. These ChatGPT-plan model IDs have no entries in the configured price file. Until prices exist, `~$0` means estimated incremental subscription spend, not a metered API equivalent.

## Output schema (all keys always present; unknown → null)
{
  "schema": 1, "session_id": str, "generated_at": epoch_int,
  "codex": {"h5": {"used_pct": num|null, "resets_at": epoch|null}, "d7": {...}, "observed_at": epoch|null},
  "model_pins": {"claude": id|null, "openai": id|null},   # current models used for the row-4 pin: Claude = `--current-claude-model` (harness `.model.id`, `[1m]` tag and 8-digit date dropped; must start with `claude-`), OpenAI = top-level `model = "..."` of `codex_config_toml` (before the first [table]); null = no pin
  "models": {  # exactly 4 Claude rows then 4 OpenAI rows. One row per EXACT model id (only a trailing 8-digit date suffix is dropped; claude-opus-5 and claude-opus-5-5 are separate rows, no version-merging aliases). Rows = top 4 ids per provider by `all.tokens`, then id, shown in descending `all.tokens` order (operator ruling 2026-11-09: all-time picks and orders). A pin that is not in the top 4 replaces row 4; a pin inside the top 4 keeps its rank. Candidates: usage.db rows (backend claude | codex,openai), state_5 threads with tokens, transcript models, the pins
    "<model_id>": {"label": str, "provider": "claude"|"openai",
                   "session": {"tokens": int|null, "tokens_noncache": int|null, "cost": num|null},   # null = source absent; tokens_noncache = input+output+cache write (Claude: transcript; OpenAI: usage db; null when the Codex thread fallback raised the total)
                   "h5": {"tokens": int|null},
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
                    "d7": {"tokens": int, "cost": float|null, "equiv_cost": float|null}}],      # cost = metered (free tier -> 0/null); equiv_cost = Anthropic-API-equivalent at config.free_price_estimate tier (haiku), rendered with `~`
  "cum_use": {"tokens": int, "cost": num|null},           # ALL usage.db rows ever (max'd against state_5 all-time for the OpenAI share), priced at Anthropic API equivalents: direct price -> openai_price_estimates -> free_price_estimate -> cum_default_estimate (sonnet)
  "claude_all": {"tokens": int, "cost": num|null},        # all-time Claude rows, no time filter, same classification/cost model as claude_today/claude_h5
  "openai_all": {"tokens": int, "cost": num|null},        # all-time OpenAI rows (incl. state_5 fallback, max'd like cum_use), same classification/cost model as openai_today/openai_h5
  "free_all": {"tokens": int, "equiv_cost": num|null},    # all-time free-backend rows (gemini|mistral|openrouter), Anthropic-API-equivalent cost like free_top4_d7's equiv_cost
  "free_windows": {"session": W, "today": W, "d28": W},   # W = {"tokens": int, "equiv_cost": num|null}; ALL free-backend rows (gemini|mistral|openrouter) in the window (session: ts >= --session-start, fallback uid == session_id; today: local day; d28: last 28 local days)
  "session_list_cost": num|null,                          # sum of models[*].session.cost (claude only)
  "sub_ratio_d7": {"claude": num|null, "openai": null},   # cost_d7 / (sub_usd * 7/30)
  "blended_usd_per_mtok_d7": {"claude": num|null, "openai": null},
  "history_days": {"claude": num|null, "openai": num|null, "free": num|null}   # days from the provider's earliest usage record to now (float, uncapped); null = no record. Renderer caps at 28 for pace baselines.
  "provider_windows": {"claude": PW, "openai": PW, "free": PW}   # PW = {"h5": T, "d1": T, "d7": T, "d28": T, "all": T}, T = {"tokens": int|null, "cost": num|null}. All of the provider's rows, every model including ones without a model cell (retired ids). Same sources and cost model as claude_h5/claude_today/claude_d7/claude_all, openai_h5/openai_today/openai_total_d7/openai_all, free_windows/free_all (free cost = equiv_cost). d1 = local today; d28 = last 28 local days. null = unknown.
}
Labels (`models[id].label`, derived from the id; the renderer derives the same string itself): `claude-<family>-<major>[-<minor>]` -> "Fable 5.1", "Opus 5.5", "Opus 5", "Sonnet 5", "Haiku 4.5";
`gpt-<version>[-<name>]` -> "GPT-6 Astra", "GPT-5.6 Sol", "GPT-5.6 Terra", "GPT-5.6 Luna". Any other id passes through (renderer cuts it to 13 columns).
Ranking uses ALL tokens = the `all.tokens` figure above (usage.db i+o+cache read+cache write per exact id, raised to the 28-day Codex thread total when that is larger). Σ/$ rows stay provider totals.

## Renderer layout

The renderer remains 6 columns wide with widths `19 20 19 38 37 30`. Col1 row 5 is `RAM` (used/total memory with bar, e.g. `5.6/16G ▓▓░░░`), colored by percent used. Col1 row 6 is `CPU` (usage percentage and bar, e.g. `42% ▓▓░░░`), colored by percentage. Col2 rows 1–4 are `CLAUDE 5H`, `CLAUDE 7D`, `CODEX 5H`, `CODEX 7D` (each with a progress bar like col1 rows 1–4). Col3 rows 1–4 show reset countdown + usage: `<reset> <tokens> <cost>` formatted with `printf '%-6s %4s %6s'` (18 chars total); the reset/ETA text is ramp-colored by elapsed fraction of its window (`eta_ramp`, 5H=18000s/7D=604800s), and tokens/cost are ramp-colored per-field (relative across the 4 rows) — see the color model paragraph below.

Col1 rows 1-4: `CONTEXT`, `MODEL`, `DIR`, `BRANCH` labels; col1 rows 5-6: `RAM` (bar right-pinned), `CPU` (bar right-pinned). Col2 row 5 is `ALL` (label) with the grand-total usage `<tokens> <cost>` — `claude_all + openai_all + free_all` (free priced at its Anthropic-API equivalent), ramp-colored. Col2 row 6 is blank. Col3 row 5 is `CC ALL` with `claude_all`'s `<tokens> <cost>`; col3 row 6 is `OAI ALL` with `openai_all`'s `<tokens> <cost>` — both real labels (via `cell`'s label slot, so they get the label color) with values right-aligned in the same `%4s %6s` token/cost columns as rows 1–4's usage half, and both ramp-colored on their own 2-row scale. `OAI ALL` is sized to exactly fill col3's 19 chars (`OAI ALL` = 7 + 1 space + 11-char value = 19). Col4 row 5 is `SESSION <session tokens> <session cost>` only (ramp-colored; the `· ALL …` half moved to col2/col3 as described above). Col5 row 5 is `SESSION <session tokens> <session cost>` only (no ALL half). Row 6 (`1D <today tokens> <today cost> · Mo <28d tokens> <28d cost>`) is unchanged and uncolored. The prior `TOTAL … · 7D …` fields on row 5 were dropped: 7D duplicated col3 rows 2/4 (`CLAUDE 7D`/`CODEX 7D`). Free equivalent costs retain cents below $1 (for example `~$.01`) so nonzero free usage is not rendered as `~$0`.

**Color model.** Palette assigns colours to roles, not widgets.

| Role | Name | RGB | Use |
|---|---|---|---|
| Chrome | `CB` | 120,86,168 | Box borders (`╔═╗╚╝║`) |
| Chrome | `CS` | 84,78,104 | Interior separators (`│`), units (`$`/`%`/`~`/`7d`/`Mo`), padding |
| Label + names | `CN` | 158,166,190 | `CONTEXT` label; free-model names |
| Model tier (ultra/platinum) | `CT1` | 229,228,226 | `MODEL` value: Fable, Astra |
| Model tier (flagship/gold) | `CT2` | 255,215,0 | `MODEL` value: Opus, Sol |
| Model tier (workhorse/silver) | `CT3` | 192,192,192 | `MODEL` value: Sonnet, Terra |
| Model tier (flash/bronze) | `CT4` | 205,127,50 | `MODEL` value: Haiku, Luna |
| Model tier (bottom/iron) | `CT5` | 110,112,120 | `MODEL` value: unclassified models |
| Project color (stable) | `PC[0-7]` | 8 fixed mid-lightness hues | `DIR` value: deterministic per project name via `cksum % 8` |
| Branch (main/master) | `CBM` | 255,120,120 | `BRANCH` value: soft red when on main/master |
| Branch (develop/dev) | `CBD` | 120,220,140 | `BRANCH` value: green when on develop/development/dev |
| Branch (other) | `CBO` | 200,200,120 | `BRANCH` value: khaki when on other branches or detached HEAD |
| Magnitude ramp | — | cyan 0,224,255 → magenta 255,102,214 (literals inside `ramp_c`) | Token/cost cells (log bands, below), percent bars (`level()` = pct×10 permille), RAM/CPU, ETA |
| Zero/unknown | `CD` | 128,128,136 | No data, null values, empty cells, stale window cells |
| Warning | `CW` | 245,176,65 | Git dirty count (`✱n`), ahead/behind markers (`↑n`/`↓n`), with glyphs for redundancy; overrides branch color when tree is dirty or ahead/behind |

Model tier classification: `tier_color <display_name>` classifies case-insensitively by substring match: fable/astra → ultra/platinum (CT1), opus/sol → flagship/gold (CT2), sonnet/terra → workhorse/silver (CT3), haiku/luna → flash/bronze (CT4), anything else → bottom/iron (CT5).

Project color: `project_color <name>` hashes project name via `cksum % 8` to select one of 8 fixed hues (all mid-lightness, readable on dark background, distinct from label/ramp/role colors). Same project always gets the same color. `DIR` label uses this color.

Branch color: `branch_kind_color <branch_name>` selects soft red for main/master, green for develop/development/dev, khaki for other branches or detached HEAD. When the git tree is dirty or ahead/behind, `CW` (warning amber) overrides the branch color for the entire BRANCH value, and reverts to branch color when clean and tracking.

**Token colour model.** One continuous ramp (cyan → magenta, `ramp_c`) serves every cell; only the input changes.

- Percent bars (`level()`): permille = percent × 10. Unchanged by the token bands. Missing or non-numeric input renders `CD`.
- Model token cells (operator, 2026-10-02, fifth pass): colour = log share of the column max. (Second pass was linear; it made every OAI and FREE cell flat cyan beside Opus.)
  - Comparison set: one per window column = the 12 model cells (ANT + OAI + FREE together).
  - Mapping: permille = clamp(1000 × (1 + log10(value / set max) / 3), 0, 1000). The max renders magenta, max/31.6 mid, max/1000 or less cyan. A lone nonzero cell is the max.
  - Input = the number shown in the cell (token totals include cache reads).
  - Missing, zero, negative or non-numeric values render `CD` and are left out of the set. Stale-cache dimming (trust rules) still applies.
- Σ token cells (operator, 2026-10-02, third pass): colour = pace against the provider's own history, log scale. Same rule as the dollar cells below, with tokens in place of dollars (Σ 30D cell is the baseline).
- Σ and `$` values (operator, 2026-10-02, fourth pass): the 5H, 1D, 7D, 30D and ALL cells show the provider total from `provider_windows` (all models, retired ids included), not the sum of the model rows above. A Σ cell can therefore exceed its column's row sum, mostly in 30D and ALL. SESS stays the row sum. Each window cell shows max(provider total, row sum): a provider total covers every model, so a lower figure means a pricing-source gap (OAI `d28` cost comes from the usage db, its model rows from Codex threads). A missing `provider_windows` value falls back to the row sum. Why: the model rows cover only the 4 configured models per provider; most older use sat on retired ids, so a row-sum 30D baseline was about half the real one and every window read hot.
- Dollar cells (operator chose the Opus design, 2026-10-02): colour = pace, each provider against its own 28-day rate. `$` values are API-equivalent figures, not money paid (plans: Claude $100, ChatGPT Plus $20 a month), and OAI uses a different pricing method from ANT, so cross-provider `$` comparison is not meaningful. A ratio against the provider's own baseline has no units, so the pricing bias cancels.
  - Baseline: `d28` = that provider's 30D cell (the collector's 28-day window). `days` = min(28, `history_days[provider]`), floor 1. Expected for a window = `d28 × window_hours / (days × 24)`. Without `history_days`, `days` = 28. (Third pass: dividing by 28 when history is shorter made every window read hot.)
  - Window hours: 5H = 5. 7D = min(168, days × 24). 1D = hours since local midnight, floor 6. SESS = session duration (`cost.total_duration_ms`); a session under 30 min renders `CD`.
  - Ratio `r = value / expected`. permille = clamp(500 + 500 × log2 r, 0, 1000): r ≤ 0.5 cyan, r = 1 mid, r ≥ 2 magenta.
  - 30D cell (operator, 2026-10-02, fifth pass): pace against the lifetime rate. Expected = ALL × 28 / `history_days`; r = 30D / expected; same log mapping. When `history_days` ≤ 28 (or unknown), 30D is most of ALL: neutral `CN`.
  - ALL cell (operator, 2026-10-02, sixth pass): log share across the 3 providers' ALL values, the same mapping as model cells (max magenta, max/1000 or less cyan). Applies to Σ and `$` ALL alike; `$` mixes pricing methods (OAI input-only), so the `$` comparison is rough. Zero or missing renders `CD`.
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
- `sess_ok=0` (payload `session_id` empty or different from the cache `session_id`, or cache older than 300 s): SESS and TPM render `—`, and session sums are `—`.
- `win_stale=1` (cache older than 300 s): window cells render `CD`. No `~` prefix, so widths stay fixed.
- A model key absent from the cache renders `—`, not `0`. A sum with no known term renders `—`.

**Colour modes.** `NO_COLOR` (non-empty): no colour sequences; bars draw `█` full, `▒` edge, `░` track. `COLORTERM` set to anything except `truecolor`/`24bit`, or `STATUSLINE_COLORS=256`: 256-colour escapes (`38;5;n`). Otherwise truecolor (also when `COLORTERM` is unset). Box width is identical in every mode.

## Gates
1. `bash -n` + `shellcheck -S warning` clean on any .sh touched. 2. `python3 -m pytest scripts/tests/test_collect_usage.py -q` all pass.
3. `bash scripts/tests/statusline_smoke.sh` → `smoke: N/N checks passed`. 4. `time bash scripts/statusline.sh < fixture` real < 0.40s (warm cache).
5. Missing usage.db / prices / codex sessions → nulls + exit 0, never a traceback.

## Operator rules (moved from machine AGENTS.md, 2026-11-07)

- `scripts/statusline.sh` is the only live status line (moved from DomI on 2026-10-11, operator instruction). `~/.claude/settings.json` runs `bash ~/Projects/agents-inc/scripts/statusline.sh`.
- Retired copies: `~/Projects/DomI/scripts/statusline.sh` and `~/.claude/statusline/vaporwave.sh` with its `.bak` copies. Do not edit them or point settings back at them. Do not create a second script.
- Verify every change yourself with the Gates above. Delegate reports of a working status line have been wrong before.
- Never drop the box border or the subtable separators.
- Measure width in terminal columns, not bytes or characters. Box-drawing glyphs are multi-byte; an emoji is one character but two columns.
- Errors go to `~/.claude/statusline-domi.log` when that file exists. `ingest_usage.py` feeds `~/.codex-bridge/usage.db` in the background on a time throttle and never blocks the render.
