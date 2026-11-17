<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-specify repo=agents-inc session=b437620e -->
# Feature Specification: Status line true tallies and pace colours

**Feature Branch**: `043-statusline-tallies-pace`
**Created**: 2026-11-15
**Status**: Clarified
**Input**: Operator rulings 2026-11-15, items 1 to 14, in `scripts/statusline.d/SPEC.md` ("Rulings 2026-11-15"), after a read-only audit of the cache and the colour complaints. The operator answered a grill the same day; no open question remains.

## Problem

The status line is the one surface the operator reads all day. Two things make it unreliable.

**The tallies are not true.** An audit on 2026-11-15 compared the table with the cache and with a recount from source.

- `claude-fable-5-2` (592M tokens, all inside 7 days) and `claude-haiku-5-5` (83M in 7D, 227M all-time) have no price entry. Their cost is dropped. Anthropic 7D dollars show 787 where about 1,258 is priced. The session dollar cell shows a dash.
- OpenAI 5H shows 9.4M tokens from Codex threads beside a cost from the usage db that covers 24 tokens ($0.0007). The cost cell renders `<.01`.
- OpenAI window figures use each thread's lifetime `tokens_used`. gpt-6.1-sol 5H counted 16.3M, of which 8.6M sat in threads created more than 5 hours earlier.
- Rows are chosen by all-time tokens. The table shows retired `claude-sonnet-5` (last used 09-29) and `claude-opus-5` at zero. It hides `claude-sonnet-5-5` (670M in 7D) and `claude-haiku-5-5`.
- The header says `30D` but the data is 28 calendar days. OpenAI 7D thread rows roll 168 hours while Claude 7D is calendar days.

A recount of Opus 5.5 7D matched the cache exactly at 1,036,986,081 tokens, so the collector counts what it reads correctly. The faults are in what it reads, how it prices and which rows it shows.

**The colours do not answer a question.** The operator cannot tell what a colour means, and everything looks hot or the same. Model rows colour by share of the column maximum, so one large model turns every other cell cyan. About 96 percent of shown Opus 5.5 7D tokens are cache reads (1,000.9M of 1,037M), so a token count says little about spend.

## Clarifications

### Session 2026-11-15

Answered by the supervising session (claude-fable-5-2) on the operator's instruction "you answer the clarifications", from the operator's grill answers of the same day. These are the supervisor's readings, not operator rulings; the operator may overrule any of them.

- Q: How is "nearest id of the same family" ordered, and what if the family has no priced member? → A: Family = same provider and same name stem (fable, opus, sonnet, haiku; astra, sol, terra, luna). Nearest = the highest priced version at or below the id's version; if none, the lowest priced version above it. No priced member in the family: cost is null and renders `—` (FR-003).
- Q: What tolerance decides that OpenAI 5H tokens and cost "cannot be reconciled"? → A: No tolerance. The cost of a window cell is computed from the same token figure the cell shows, times that model's rate. The cost renders `—` only when the model has no price under the rule above. A cost taken from a different source than its tokens is never shown.
- Q: The pace baseline needs a first-seen date per model; the cache has only `history_days` per provider. → A: The collector adds a first-seen day per model id, taken from the earliest usage row of that id in the source it already reads. A model with no usage row has no baseline and renders zero grey.
- Q: Ruling 3 (window-only tokens) conflicts with the collector rule "state tokens win for token counts". → A: That rule is narrowed. Thread lifetime totals stay the source for OpenAI ALL and SESS. A window cell (5H, 1D, 7D, 28D) never contains tokens used before the window opened. The plan picks the measurement (per-turn records if the thread store has them, else snapshot differences the collector records). Where the in-window amount of a thread cannot be measured, that thread contributes only if it was created inside the window, and the gap is logged, not guessed.
- Q: Is the ALL column a pace cell (ruling 9 against ruling 12)? → A: No. Pace cells are SESS, 5H, 1D, 7D and 28D. ALL keeps share colouring on token counts, unchanged.
- Q: Does the new baseline replace the special rules for the fifth window? → A: No. The 28D cell keeps its current rule, pace against the lifetime rate (expected = ALL × 28 / history days), with the new range formula, and stays neutral `CN` when history is 28 days or less. The same rule applies to model rows with the model's own or borrowed history. SESS keeps session duration as its window and stays grey under 30 minutes.
- Q (from the plan, C2): read literally, FR-003 blanks every OpenAI cost, because OpenAI models have no entry in the price file. → A: The configured OpenAI estimate map stays as the step after family pricing; that is the existing estimated pricing the `~` row label already marks. FR-003 applies when neither a price, a priced family member nor an estimate exists.
- Q (from the plan, C5): do FREE rows get pace colours? → A: Yes. Ruling 8 covers every table cell in the five pace windows. A free model is paced on its Anthropic-equivalent dollars against its own or its family's history like any other row.
- Q (from the plan, C4): SPEC.md calls the thread store a fallback while the code takes the larger of two sources per model. → A: SPEC.md is corrected to describe the code as part of FR-016; behaviour for ALL and SESS does not change.

## Scope

In scope: the collector (`collect_usage.py`), the renderer (`statusline.sh`), the price file the collector reads, the cache fields they share, and the contract file `scripts/statusline.d/SPEC.md`.

Out of scope:

- Operator item 6 (free models run from the delegate pane stored under backend `claude` and counted as Claude). The operator did not approve it. It stays recorded as an open item in `SPEC.md` and is not built here.
- Layout changes: box width, row count, column widths, cell order.
- New columns, an on-screen legend, or any new glyph.
- Changing model-name colours (tier colours stay).
- The DOL left-column pricing method (it sums three pricing methods and stays neutral). It is touched only through item 1: adding the missing prices changes the number DOL shows, but its method and colour do not change.
- Gauge colouring (RAM, CPU, DSK, GPU, EFF, CTX, quota percent, countdowns, CLK) and the ALL column's share colouring. Both are unchanged by ruling.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dollars are complete (Priority: P1)

The operator reads ANTROP dollars and trusts them. Every model with usage in the last 28 days contributes its cost. No model's spend is silently dropped because a price entry is missing.

**Why this priority**: A dropped cost understates spend by about a third (787 against about 1,258) and also breaks the pace colours, which now weigh by dollars.

**Independent Test**: Feed the collector a usage fixture that holds `claude-fable-5-2` and `claude-haiku-5-5` with no price entry. Every model id with 28-day usage has a non-null cost, and the Anthropic 7D dollar total equals the sum of its models' costs.

**Acceptance Scenarios**:

1. **Given** usage for `claude-fable-5-2` and `claude-haiku-5-5`, **When** the cache is built, **Then** each has a non-null `cost` in every window where it has tokens, and the session dollar cell shows a figure, not a dash.
2. **Given** a model id with no price entry but a priced member of the same family on the same provider, **When** the cache is built, **Then** the id is priced at the nearest id of that family.
3. **Given** the price file now holds entries for the two ids above, **When** the cache is built, **Then** those ids use their own entries, not the family fallback.
4. **Given** a model with no price entry and no priced family member, **When** the cache is built, **Then** its cost is `null` and the cell renders `—`; no price is invented.

---

### User Story 2 - OpenAI window figures are true to the window (Priority: P1)

The operator reads OAI 5H and 1D. The tokens are the tokens used inside that window. The cost beside them comes from the same source, so a large token count never sits beside a near-zero cost.

**Why this priority**: The 5H cell is the one the operator watches against the quota. Today it overstates tokens (16.3M against 7.7M for one model) and pairs them with a cost that covers 24 tokens.

**Independent Test**: A fixture holds one Codex thread created 8 hours ago and updated now. The 5H token count excludes the tokens used before the window start, and never exceeds the tokens recounted inside the window from the fixture.

**Acceptance Scenarios**:

1. **Given** a thread created before the 5H window start and touched inside it, **When** the cache is built, **Then** only tokens used inside the window count toward 5H and 1D.
2. **Given** OpenAI 5H tokens and cost from the same source, **When** the cell renders, **Then** the cost covers those tokens.
3. **Given** tokens and cost whose sources differ and cannot be reconciled, **When** the cell renders, **Then** the cost cell shows `—`, not a misleading small number.
4. **Given** the 7D window, **When** OpenAI thread rows are assigned, **Then** they use local calendar days, the same as Claude 7D, not a rolling 168 hours.

---

### User Story 3 - Rows show the models in use now (Priority: P2)

The operator opens the table and sees the four models per provider that carried the last 28 days of work, not a historical ranking that includes retired ids at zero.

**Why this priority**: The table currently hides the two models doing most of the work (`claude-sonnet-5-5`, `claude-haiku-5-5`) and shows two retired ids. It is wrong but not a wrong number, so it ranks below P1.

**Independent Test**: A fixture with two retired ids (high all-time, zero in 28 days) and two live ids (low all-time, high 28-day). The live ids appear in the four rows.

**Acceptance Scenarios**:

1. **Given** more than four ids per provider, **When** rows are chosen, **Then** the four with the most tokens in the last 28 days are shown.
2. **Given** two ids tied on 28-day tokens, **When** rows are chosen, **Then** all-time tokens break the tie, and a remaining tie breaks on id so the order is stable between runs.
3. **Given** a configured pin on row 4, **When** the pin is not in the top four, **Then** it replaces row 4; a pin inside the top four keeps its rank.
4. **Given** a model not shown, **When** the Σ and dollar rows render, **Then** its usage is still counted there.

---

### User Story 4 - The window header matches the data (Priority: P2)

The fifth window column is labelled `28D` and holds 28 calendar days. OpenAI and Claude 7D use the same kind of day.

**Why this priority**: A label that disagrees with its data erodes trust in every cell. The change is small and independent of the others.

**Independent Test**: Render the box and read the top border. It shows `28D`, and its width is identical to the width before the change.

**Acceptance Scenarios**:

1. **Given** the renderer, **When** the top border is drawn, **Then** the labels read `SESS 5H 1D 7D 28D ALL` for every provider block.
2. **Given** OpenAI 7D, **When** the cache is built, **Then** it counts the same calendar days as Claude 7D.

---

### User Story 5 - Table colour means pace against the row's own normal (Priority: P3)

A model cell is hot when that model is burning faster than it normally does, and cool when it is slower. The operator can read a cell without a legend. The ALL column still shows share, gauges still show how full, and grey still means zero, unknown or stale.

**Why this priority**: It is the largest design change and it depends on User Story 1 (the weights are dollars). It gives no wrong number today, only an unreadable colour.

**Independent Test**: Render a fixture where one model runs at 4 times its 28-day rate and another at its normal rate. The first renders at the magenta end, the second at the mid blend, and neither colour depends on the size of the largest model in the column.

**Acceptance Scenarios**:

1. **Given** a model cell in SESS, 5H, 1D, 7D or 28D, **When** the cell is coloured, **Then** the colour input is the model's pace ratio r against its own 28-day rate, weighted by API-equivalent dollars; the number shown stays tokens.
2. **Given** r at or below 0.25, **When** coloured, **Then** the cell is cyan; at r = 1 it is the mid blend; at r at or above 4 it is magenta. The same range applies to model, Σ and dollar pace cells.
3. **Given** a model with at least 7 days of history, **When** its baseline is set, **Then** `days` is the days since the model was first seen, capped at 28.
4. **Given** a model with under 7 days of its own history, **When** its baseline is set, **Then** it is paced against the summed history of its family on that provider (all Fable ids; all Sol ids) until it has 7 days.
5. **Given** the ALL column, a gauge, a model-name cell, **When** coloured, **Then** the result is the same as before this change.
6. **Given** the rendered screen, **When** inspected, **Then** it has no legend and no new glyph.

---

### Edge Cases

- **Model with zero history and no family**: no baseline exists, so the cell renders grey (`CD`), not cyan and not magenta. Unknown is not zero.
- **Family with no priced member**: cost is `null` and shows `—` (User Story 1, scenario 4). Its pace cells render grey because the weight is unknown.
- **Provider with `d28` zero**: every pace cell of that provider renders grey, as today.
- **Session under 30 minutes**: SESS pace cells render grey, as today.
- **Stale or unreadable cache**: unchanged. Stale window cells render grey with fixed width. Unreadable cache renders `—` in every figure. A missing price file or usage db gives nulls and exit 0, never a traceback.
- **`NO_COLOR`**: no colour sequences; the new pace rules produce no output difference except in the text of cells. **256-colour mode**: pace colours map to the 256-colour escapes through the same path as today. Box width is identical in all three modes.
- **Pin on row 4**: the pin replaces row 4 only when it is outside the top four by 28-day tokens (User Story 3, scenario 3).
- **Ties in the 28-day ranking**: broken by all-time tokens, then by id.
- **A model first seen today**: it has under 7 days of history, so it borrows its family's history. If it has no family on that provider, it renders grey (first edge case).
- **A model with usage only outside 28 days**: not shown in rows; still counted in ALL and in the Σ provider totals where those cover it.

## Requirements *(mandatory)*

### Functional Requirements

Tallies

- **FR-001**: Every model id with usage in the last 28 days MUST have a non-null cost when a price or a priced family member exists (ruling 1).
- **FR-002**: The price file MUST gain entries for `claude-fable-5-2` and `claude-haiku-5-5`. An id with no entry MUST be priced at the nearest id of the same family on the same provider, never dropped (ruling 1). This overrides the "Missing price" line in the Inputs section of `SPEC.md`.
- **FR-003**: A model with no entry, no priced family member and no configured estimate MUST have `cost` null and render `—`. No price is invented. The configured OpenAI estimate map is the step after family pricing (Clarifications).
- **FR-004**: OpenAI 5H cost MUST come from the same source as OpenAI 5H tokens. Where the two differ and cannot be reconciled, the cost cell MUST render `—` (ruling 2).
- **FR-005**: OpenAI 5H and 1D MUST count only tokens used inside the window, not a thread's lifetime `tokens_used` (ruling 3). Measurement (plan R1): a thread's in-window tokens are its running total at the last recorded event before now minus its running total at the last event before the window opened; a thread with no event record counts only if created inside the window, and the gap is logged.
- **FR-006**: The fifth window MUST be 28 calendar days and its header label MUST read `28D` (ruling 4).
- **FR-007**: OpenAI 7D thread rows MUST use calendar days, the same as Claude 7D (ruling 4).
- **FR-008**: The four model rows per provider MUST be the top four by tokens in the last 28 days, with all-time tokens as tie-break then id. A configured pin MUST take row 4 when outside the top four. Models not shown MUST stay counted in Σ (ruling 5). This replaces the operator ruling of 2026-11-09.

Colour

- **FR-009**: The renderer MUST keep one cyan to magenta ramp for every ramp-coloured cell. Model-name colours MUST NOT change (ruling 7).
- **FR-010**: Model cells in SESS, 5H, 1D, 7D and 28D MUST be coloured by pace, the rule the Σ and dollar rows already use, replacing log share of the column maximum (ruling 8).
- **FR-011**: The pace quantity MUST be API-equivalent dollars for every pace cell, token cells included. The number shown MUST stay tokens (ruling 9). This depends on FR-001 and FR-002.
- **FR-012**: A model's pace baseline MUST be its own 28-day rate with `days` = days since first seen, capped at 28. Under 7 days of own history, the baseline MUST be the summed history of its family on that provider until it has 7 days (ruling 10). The 28D cell is the exception: it is paced against the lifetime rate of the same source (own or family) and is neutral when that history is 28 days or less (Clarifications).
- **FR-013**: The pace-to-colour mapping MUST be permille = clamp(500 + 250 × log2 r, 0, 1000): r at or below 0.25 cyan, r = 1 mid blend, r at or above 4 magenta. It MUST apply to model, Σ and dollar pace cells alike (ruling 11).
- **FR-014**: The ALL column MUST keep share colouring. Gauges MUST keep the ramp as "more is hotter" (rulings 12 and 13).
- **FR-015**: The screen MUST NOT show a legend or a new glyph. Grey MUST still mean zero, unknown or stale (ruling 14).

Contract

- **FR-016**: `scripts/statusline.d/SPEC.md` MUST be updated in the same change: the "NOT YET IN CODE" markers and "Replaced by" notes are resolved, the `30D` label becomes `28D`, and the Rulings section is folded into the contract text. SPEC.md stays the collector contract.
- **FR-017**: The existing Gates MUST still pass: shell lint on touched `.sh`, the collector tests, the smoke script, render under 0.40 s warm, and nulls plus exit 0 when a source is missing.

### Key Entities

- **Model row**: one exact model id on one provider, with tokens and cost per window.
- **Pace ratio r**: a window's API-equivalent dollars divided by the dollars expected at that model's own 28-day rate for the window length.
- **Family**: the set of model ids on one provider that share a name stem (all Fable ids; all Sol ids), used for pricing fallback and for the baseline of a new model.
- **Price entry**: dollars per million tokens for input, output, cache read and cache write, keyed by exact id.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a fixture with 28-day usage, every model id has a non-null cost, except an id with no price and no priced family, which shows `—`.
- **SC-002**: The Anthropic 7D dollar total in the audit data moves from 787 to about 1,258, and the session dollar cell no longer shows a dash.
- **SC-003**: OpenAI 5H tokens never exceed the tokens recounted inside the window from a fixture. For the audit case, gpt-6.1-sol 5H falls from 16.3M by the 8.6M that sat in older threads.
- **SC-004**: OpenAI 5H cost and tokens agree on source: no fixture renders a cost under $0.01 beside more than 1M tokens.
- **SC-005**: The four shown rows per provider equal the top four by 28-day tokens in a fixture. In the audit data `claude-sonnet-5-5` appears and retired `claude-sonnet-5` and `claude-opus-5` do not (`claude-haiku-5-5` ranks fifth there and shows only when pinned).
- **SC-006**: The top border reads `28D`, and box width is identical before and after the change in truecolor, 256-colour and `NO_COLOR` modes.
- **SC-007**: A cell at r = 0.25 renders the cyan end, r = 1 the mid blend, r = 4 the magenta end, from a rendered fixture, and the colour of a cell does not change when another model in the column grows tenfold.
- **SC-008**: A reader shown three cells (cool, mid, hot) can say which model is running above its normal, without a legend, in under 10 seconds.
- **SC-009**: Render time stays under 0.40 s warm. All Gates in `SPEC.md` pass.
- **SC-010**: ALL column colours, gauge colours and model-name colours are byte-identical before and after for the same fixture.

## Assumptions

- Python standard library only; no new dependency. $0 spend: no paid API and no network call is added.
- `scripts/statusline.d/SPEC.md` stays the collector contract and is updated in the same change as the code.
- The 2026-11-09 row ruling (rank by all-time tokens) is replaced by operator ruling 2026-11-15, item 5.
- "Nearest id of the same family" means the same provider and the same name stem, ordered by closest version; the plan picks the exact ordering rule.
- Prices for the two missing ids come from the operator-approved price source the price file already uses; if no source exists the fallback applies and the entry is flagged.
- "Cannot be reconciled" (ruling 2) has no tolerance: see Clarifications. Cost is computed from the token figure the cell shows.
- The collector cache keeps its existing key `d28`; only the user-facing label changes.
- Dependencies: ruling 9 depends on ruling 1; the family baseline in ruling 10 depends on the cache holding per-model first-seen dates.
