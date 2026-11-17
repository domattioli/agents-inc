<!-- provenance: author=domattioli model=claude-opus-5-5 effort=low date=2026-11-15 skill=speckit-plan repo=agents-inc session=b437620e -->
# Research: Status line true tallies and pace colours

Sources read: `scripts/statusline.sh` (493 lines), `scripts/statusline.d/collect_usage.py` (1215), `scripts/statusline.d/SPEC.md` (184), `scripts/statusline.d/config.json`, `skills/codex-bridge/reference/prices.json`, `scripts/tests/test_collect_usage.py`, `scripts/tests/statusline_smoke.sh`. Live data inspected read-only on 2026-11-15 (schemas, token counts, timestamps; no message content, no auth files): `~/.codex/state_5.sqlite`, `~/.codex/sessions/**/rollout-*.jsonl`, `~/.codex-bridge/usage.db` (opened `mode=ro&immutable=1`; plain `-readonly` fails with SQLITE_CANTOPEN under the sandbox).

## R1. In-window OpenAI tokens (FR-005, clarification 4)

Decision: measure per thread from the rollout file's `event_msg/token_count` events. Each carries `timestamp` and `info.total_token_usage` (cumulative for the thread: `input_tokens` with `cached_input_tokens` as a subset, `output_tokens` with `reasoning_output_tokens` as a subset, `total_tokens` = input + output). In-window tokens of a thread = `total_tokens` at the last event at or before now minus `total_tokens` at the last event before window start (0 if none). Same subtraction per category gives uncached input, cache read (= cached), output for pricing.

Evidence:
- `threads` schema has only lifetime `tokens_used`, `created_at`, `updated_at`, `rollout_path`, `model`, `cwd` (no per-turn table: tables are `threads`, `thread_*`, `projects`, migrations). Current code sums lifetime `tokens_used` for any thread with `updated_at >= window start` (`collect_usage.py:872-923`).
- Last event `total_tokens` equals `threads.tokens_used` for 84 of 84 threads updated in 7 days. So the rollout delta and the thread total share one source; ALL and SESS (lifetime, clarification 4) stay consistent with windows.
- Rollouts also carry `token_usage_record` lines (per response `usage`, `turn_token_usage`, `thread_token_usage`). Not used: `token_count` already gives the cumulative series with one parse per line, and a cumulative difference is robust to a dropped line.
- Audit reproduced: 1 thread spans the rolling 5h start with 8,625,481 lifetime tokens (spec SC-003 says 8.6M). Rolling 5h on live data: in-window 14.13M against 18.28M lifetime for the same threads.
- Cost: byte-filter scan (`b'"token_count"' in line`, then `json.loads` only those lines) took 0.02 s for 5h (10 files, 15 MB), 0.06 s for 1d (24 files, 47 MB), 0.12 s for 7d (84 files, 91 MB). 28d is about 144 MB. Collector has a 5 s timeout and runs at most once per 60 s, off the warm render path.
- usage.db `codex` backend: 2,832 rows, 92M tokens, mostly `gpt-6-astra` bridge dispatches; it misses ChatGPT-plan Codex app use. Keep the existing per-model max(usage.db, threads) rule per window; the winning source supplies both tokens and cost (R4b).

Fallback: rollout file missing or unreadable, or no `token_count` event. The thread contributes its `tokens_used` only when `created_at >= window start` (then lifetime = in-window, exact); otherwise it contributes 0 and the collector appends one line per window to `~/.claude/statusline-domi.log` when that file exists (`gap <window> <model> threads=<n> tokens=<lifetime sum>`). Live size of the gap: 86 of 283 threads updated in 28 days have no rollout file (13.0M of 151.8M tokens, 8.6 %); all 86 were created inside the 28-day window, none is updated inside 7 days. Error today: 0 in 5H/1D/7D, 0 in 28D (all created inside). Worst case in general: undercount of the in-window share of a pre-window thread whose rollout is gone; never an overcount.

Alternatives rejected: snapshot differences recorded by the collector (needs a new state file, wrong after a gap in collector runs, first run has no baseline); pro-rata by time (invents attribution); `token_usage_record` sums (equivalent, more lines to parse).

## R2. Per-model first-seen day and 28-day dollars (FR-011, FR-012)

- usage.db: the all-time query already groups by `backend, model` with `MIN(ts)` (`collect_usage.py:639-676`); today it feeds only per-provider `first_ts` (`note_first`, `:410`). Decision: keep a `first_seen[model] = min(epoch)` map from the same rows (after `normalize_model`, so dated ids fold).
- state_5: `SELECT model, MIN(created_at) ... GROUP BY model` (live: 11 models, e.g. `gpt-6.1-sol` 1791600916). Take the min of both sources.
- Transcript-only model (no row anywhere): no first-seen; baseline from family or none (clarification 3).
- 28-day dollars: `models[id].d28.cost` already exists (`:1026`) for shown rows. The collector computes it for all candidates (`models_full`) before ranking, so family sums can use non-shown members.
- New cache keys: `models[id].first_seen` (epoch|null), `models[id].h5.cost`, `models[id].pace` (contract `contracts/cache-schema.md`). Same for `free_top4_d7[*]` entries.

## R3. Family and nearest priced version (clarification 1)

Decision: a new pure function `parse_family(model_id) -> (provider, stem, version_tuple) | None` in `collect_usage.py`, beside `model_label` (`:120-129`) and reusing its two regexes:
- `^claude-([a-z]+)-(\d+)(?:-(\d+))?$` -> ("claude", stem, (major, minor or 0)). `claude-fable-5-2` -> fable (5,2); `claude-opus-5` -> opus (5,0); `claude-haiku-4-5-20251001` -> date dropped first by `strip_model_version` (`:102`).
- `^gpt-(\d+)(?:\.(\d+))?-([a-z0-9]+)$` -> ("openai", stem, (major, minor or 0)). `gpt-6.1-sol` -> sol (6,1). `gpt-5.5`, `gpt-5.4-mini`, `codex-auto-review`: no stem or unknown stem -> None (no family).
- Stems recognised: fable, opus, sonnet, haiku; astra, sol, terra, luna. Others -> None.
- `price_for(model_id)`: exact id -> date-stripped id -> family nearest (highest priced version <= id's version, else lowest priced above) -> `openai_price_estimates` map (existing, `:19`, config-merged at `:225`) -> None. Returns `(price_dict, source)` with source `exact|family:<id>|estimate:<id>|None`.
- Live effect: `claude-fable-5-2` -> family `claude-fable-5-1` until its own entry lands; `claude-haiku-5-5` -> `claude-haiku-4-5`. OpenAI stems have no priced member in `prices.json`, so they reach the estimate map (see Spec conflicts C2).
- Every cost site calls `price_for` through one `calculate_cost`. Today there are three paths: `calculate_cost` (`:158`), `calculate_estimated_cost` (`:177`), and input-rate-only `price["input"]` multiplications on thread totals (`:882-884, :906-909, :920-923, :934-937, :957-960`, plus `tiered_input_price` `:275`). The thread paths go away once R1 gives a category split.

Prices for the two ids: `prices.json` `_comment` names its source as the claude-api skill model table. Phase 1 builder loads that skill for the two rates. If the table lacks either id, no entry is added; the family fallback prices it and the plan records the gap (spec Assumptions).

## R4. Cost-weighted pace for token cells

What the renderer needs per model cell: the cell's dollars in the same window, and the model's baseline rate (dollars per day) plus the days used for the 7D window hours, plus for 28D the lifetime dollars and history days.
- Cache has per model: `session.cost`, `d1.cost`, `d7.cost`, `d28.cost`, `all.cost`. Missing: `h5.cost` (the h5 block carries tokens only, `:1023`; renderer 5H dollars use provider fields `claude_h5.cost`/`openai_h5.cost`, `statusline.sh:339-340`). Missing: baseline.
- Decision: the collector computes the baseline (cheap, Python) and emits `pace.usd_per_day`, `pace.days`, `pace.hist_days`, `pace.all_cost`, `pace.source`. The renderer only divides. This keeps family lookups out of bash.
- Σ token cells: colour input becomes the matching Σ dollar value (CSUM), so token Σ colour = dollar Σ colour. The renderer drops its second `pacecols` call on TSUM (`statusline.sh:352`).

R4b. Same-source cost (FR-004, clarification 2): every window figure is a (tokens, cost) pair computed from one row set. Where the per-model max rule picks the thread measurement, its cost is priced from the thread category split; where it picks usage.db, from usage.db rows. The OpenAI provider 5H pair (`openai_h5`) is rebuilt as the sum over models of the chosen pairs plus null-model usage.db rows (tokens counted, cost from the same rows only when priced). No tolerance check is needed: a cost from a different source than its tokens can no longer be produced.

## R5. Render-time budget (0.40 s warm, Gate 4)

- The renderer already makes one `jq` call, one `sharecols` awk, two `pacecols` awks, several `awk` cost formatters. Plan net change: replace the model-cell `sharecols` input (cols 0-4) by one new `modelpace` awk over 72 values with the per-model rate list; keep `sharecols` for col 5 (ALL) only; drop the TSUM `pacecols`. Net forks: 0.
- jq: the MODEL line gains 6 fields (`h5.cost`, `pace.*`); META/HIST unchanged. `read` already takes 26 fields (`statusline.sh:95`); MODEL uses `a..m` today, new fields `n..s`. FREE line gains the same 6 (`o..t`).
- All family, version, first-seen and rollout work is in the collector (cached 60 s, 5 s timeout, `statusline.sh:44-61`).
- Bash 3.2: no associative arrays, no `${var,,}`, no `mapfile`; the new awk is POSIX awk (`log`, `int`, `split`).

## R6. Row ranking (FR-008)

- Today `pick_rows` (`collect_usage.py:149-156`) ranks by `all.tokens`, then id, and re-sorts shown rows by all-time. Decision: key `(-d28.tokens, -all.tokens, id)`; pin outside top 4 replaces row 4; output order by the same key (pin keeps its key order, so a low pin sorts last).
- Live 2026-11-15, Claude 28-day tokens (usage.db): opus-5-5 2.68B, sonnet-5-5 1.24B, fable-5-2 593M, fable-5-1 397M, haiku-5-5 196M, haiku-4-5 25.6M; retired sonnet-5, opus-5, fable-5, opus-4-x at 0. See C1.
- Candidate hygiene: Claude candidates come from every usage.db `backend = 'claude'` model (`:359`). That set holds free and OpenAI ids run from the delegate pane (`nvidia/...:free`, `ministral-3b-latest`, `gpt-6-luna`, open item 6). The renderer routes a non-`claude*` id to the OAI block (`statusline.sh:102`). Decision: Claude candidates require prefix `claude-`; others are not added to Claude rows. Their tokens stay in the claude provider totals as today (item 6 stays out of scope).
- `provider_windows` (Σ/$ rows) is computed from all rows, independent of `pick_rows` (`:1084-1108`), so ranking does not change Σ (FR-008 last clause). Renderer `pwmax` keeps max(provider, row sum).

## R7. `30D` to `28D` and the d28 naming

Cache key `d28` stays (spec Assumptions). User-facing `30D` occurrences:
- `scripts/statusline.sh:449` `thdr` label list (the only rendered one). Comments: `:181, :188, :190-193, :311, :347, :357, :462`.
- `scripts/tests/statusline_smoke.sh`: 27 lines; the assertion is `:113-114` (`SESS═══5H═══1D═══7D══30D══ALL`, count 3); others are comments and messages (`:197-315`).
- `scripts/statusline.d/SPEC.md`: 10 lines (`:66, :77, :78, :81, :118, :120, :121, :123, :126`, rulings).
- `scripts/statusline.d/collect_usage.py:720` comment.
- No other file in the repo outside `specs/` contains `30D`.
- Width: `30D` and `28D` are both 3 columns; box width unchanged (smoke `width_gate 147/148`).
- Calendar alignment (FR-007): OpenAI thread 7D uses `now - 7*86400` (`:875`) and 28D `now - 28*86400` (`:913`). usage.db uses `day >= date('now','localtime','-6 days')` and `-27 days`. Decision: thread windows start at local midnight 6 and 27 days back (`time.mktime` of today 00:00 minus days), like 1D (`:897`).

## R8. SPEC.md edits (FR-016)

- Line 3: narrow "state tokens win for token counts" to: thread lifetime totals are the source for OpenAI ALL and SESS; window cells count only in-window tokens (rollout deltas, fallback rule R1).
- Line 19 (Codex fallback): replace "7d assigns threads updated in the preceding 168 hours ... estimated" with the rollout-delta rule, calendar days, and the gap log.
- Lines 24-26 (Prices): replace "Missing price -> cost: null" by the `price_for` order; drop "OpenAI ... input-rate" wording.
- Line 33 (models ranking) and line 62: 28-day ranking, ties, pin, `claude-` prefix.
- Lines 36-40: add `h5.cost`, `first_seen`, `pace`; fix the misplaced "28-day Mo window" comment on `all`.
- Lines 66, 77, 78, 81, 118-126: `30D` -> `28D`.
- Lines 112-130 colour model: model cells pace (cost-weighted), Σ token cells use dollars, range 500 + 250 log2 r, model baseline rules, 28D model rule.
- Lines 148-170: delete the Rulings section after folding; keep item 6 as an "Open item" line.

## Spec conflicts

- C1. SC-005 says `claude-haiku-5-5` appears in the rows. Under FR-008 on the live data (R6) Claude's top 4 by 28-day tokens are opus-5-5, sonnet-5-5, fable-5-2, fable-5-1; haiku-5-5 (196M) is fifth and shows only when pinned. Retired sonnet-5 and opus-5 do drop out, and sonnet-5-5 appears. Test for SC-005 uses a fixture, not live data; the operator should know the live table will not show haiku-5-5.
- C2. FR-003 says an id with no entry and no priced family member gets `cost: null`. Every OpenAI id is in that state (no OpenAI price in `prices.json`), but the collector prices them today through the operator-configured `openai_price_estimates` map (`collect_usage.py:19`, `config.json` `openai_price_estimates`), and SPEC.md line 26 documents it. Literal FR-003 would blank every OAI dollar cell and grey all OAI pace cells. Plan keeps the estimate map as the step after family (it is a configured mapping, not an invented price). Operator to confirm.
- C3. Spec Assumptions: "Cannot be reconciled is decided in the plan by a stated tolerance". Clarification 2 supersedes it (no tolerance; same source by construction). Plan follows clarification 2.
- C4. SPEC.md line 19 says the thread store is used "when a configured OpenAI model has no bridge-DB rows"; code takes the per-model max of both (`:878, :894, :904, :916`). Plan documents the max rule in SPEC.md.
- C5. Spec is silent on FREE model rows. FR-010 says "model cells". Plan applies pace to FREE model cells too (equiv cost, first-seen from usage.db), since the share rule would otherwise survive only there and ruling 8 says one question for every table cell. Operator may restrict it to ANT and OAI; that changes Phase 6 only.
