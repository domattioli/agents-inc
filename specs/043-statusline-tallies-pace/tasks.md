<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-tasks repo=agents-inc session=b437620e -->
# Tasks: Status line true tallies and pace colours

**Input**: `specs/043-statusline-tallies-pace/` (spec.md, plan.md, research.md, data-model.md, quickstart.md, contracts/cache-schema.md).
**Prerequisites**: plan.md and spec.md. Where they differ, spec.md Clarifications win (see "Spec versus plan notes").
**Tests**: Requested (the spec gives a testable criterion per SC). Every phase writes its tests first, and the builder records the red run before writing the code that makes it green.
**Organization**: One task phase per plan phase, in plan order: 1 prices, 2 OpenAI windows and cost, 3 `28D` label, 4 row ranking, 5 cache additions for pace, 6 pace colouring. Phase 0 is setup. Each phase ends with its SPEC.md edit and an acceptance task. Verified files reach the live paths only through the supervisor tasks under "Supervisor handoff".

## Format: `- [ ] TNNN [P?] [Story?] Description with exact paths. FR/SC: ids. Done: the checkable condition.`

- **[P]**: touches no file that another task in the same phase touches, and has no order dependency on it. Tasks in different phases are never run together.
- **[USn]**: US1 dollars complete (Phase 1), US2 OpenAI windows (Phase 2), US3 rows (Phase 4), US4 header label (Phase 3; the OpenAI calendar-day scenario is in Phase 2), US5 pace colour (Phases 5 and 6). Phase 0, acceptance and supervisor tasks carry no story tag.
- Paths are relative to `/Users/domattioli/Projects/agents-inc`. `W` means `.scratch/043`. `W/scripts/` is the copy of `scripts/`; `W/skills/codex-bridge/reference/prices.json` is the copy of the live price file.

## Conventions every task follows

- Builders edit only files under `.scratch/043/`. They never edit the live `scripts/statusline.sh`, `scripts/statusline.d/*`, `scripts/tests/*` or `skills/codex-bridge/reference/prices.json`. SPEC.md is edited at `W/scripts/statusline.d/SPEC.md`.
- Python standard library only; `$0` spend; no network. The collector exits 0 and writes no traceback when a source is missing.
- "Gates on the copy" means the Gates block in `specs/043-statusline-tallies-pace/quickstart.md`: `bash -n` and `shellcheck -S warning` on `statusline.sh` and `statusline_smoke.sh`; `python3 -m pytest scripts/tests/test_collect_usage.py -q`; `bash scripts/tests/statusline_smoke.sh`; warm render under 0.40 s (second run timed); missing-sources run with exit 0. Run from `W`.
- "Width check" means the width block in quickstart.md: one equal width in truecolor (`COLORTERM=truecolor`), 256-colour (`STATUSLINE_COLORS=256`) and `NO_COLOR=1`, equal to the baseline width recorded in T002.
- Dry runs pass `--prices W/skills/codex-bridge/reference/prices.json`, because the copied `config.json` lists the live price file first.
- A delegate never accepts its own output. The supervisor re-runs the Gates and the width check itself before any swap.

## Skipped steps (speckit-tasks outline)

- Step 1 (`.specify/scripts/bash/check-prerequisites.sh --json`): skipped, `.specify/scripts/` is absent. The feature directory was read from the file list.
- `.specify/extensions.yml` before_tasks and after_tasks hooks: not checked; none run.
- No branch change and no `.specify/feature.json` edit.

## Spec versus plan notes

- Swap owner: plan.md calls the swapper "orchestrator"; this file names the same role "supervisor". Plan Working rule step 4 (atomic `cp` then `mv`, collector before renderer, SPEC.md in the same swap) is kept as is, one swap task per phase.
- Plan Phase 3 allows overlap with Phase 1 or 2 when the supervisor merges SPEC.md. This file runs the phases serially (1, 2, 3, 4, 5, 6, the plan's recommended order), so no merge is needed.
- C4 (SPEC.md describes the thread store as a fallback while the code takes the larger of two sources) is a spec clarification and FR-016 item, but no plan phase names it. T012 (Phase 2) carries it, because Phase 2 is the phase that changes the thread-store reading.
- Spec "Edge Cases" says a Σ cell rule is unchanged; plan Phase 6 extends the new range to Σ and dollar pace cells (FR-013). No conflict: both say one range for model, Σ and dollar cells.
- Plan Phase 6 lists the pre-change capture only as a risk. This file makes it its own task (T028), ordered after Phase 5 and before any Phase 6 edit.
- Analyze pass (supervisor, 2026-11-15) changed five tasks: every collector swap carries its test file and fixtures (T035, T036, T038, T039); the Phase 4 Σ comparison uses frozen inputs and a fixed clock (T019, T023); a cell's cost follows the token source the cell chose (T011); the OpenAI family is the name stem across versions (T004).
- No other disagreement found between spec.md and plan.md.

---

## Phase 0: Setup

**Purpose**: Work copy and baselines. No live file is touched.

- [x] T001 Create the work copy: `mkdir -p .scratch/043/skills/codex-bridge/reference && cp -R scripts .scratch/043/ && cp skills/codex-bridge/reference/prices.json .scratch/043/skills/codex-bridge/reference/`. FR: FR-017. Done: `diff -r scripts .scratch/043/scripts` prints nothing and the price copy exists.
- [x] T002 Run the Gates on the copy and the width check; write the three widths to `.scratch/043/baseline-width.txt`, and write a dry-run cache from live data to `.scratch/043/baseline-dry.json` (`python3 .scratch/043/scripts/statusline.d/collect_usage.py --session-id dry --prices .scratch/043/skills/codex-bridge/reference/prices.json --out .scratch/043/baseline-dry.json --force`). FR: FR-017. SC: SC-006, SC-009. Done: every Gate passes before any change; `baseline-width.txt` holds one width repeated three times; the dry run exits 0.

- [x] T002a Builder: in `.scratch/043/scripts/tests/statusline_smoke.sh` line 25 use `WORK=$(mktemp -d "${TMPDIR:-/tmp}/smoke.XXXXXX") || { echo 'smoke: mktemp failed' >&2; exit 1; }`. Done: smoke runs in the sandbox and writes nothing to `/`.
- [x] T002b Builder, tests only: find why 6 smoke checks print `bash: ramp_c: command not found`. If the smoke script is stale against the renderer, fix the smoke script in the copy so the checks pass on the unchanged renderer; if the cause is in the renderer or needs a behaviour change, change nothing and record the 6 check names in `.scratch/043/baseline-smoke.txt`. Done: the report says which case.

**Gate baseline (supervisor ruling 2026-11-15)**: the live renderer already has shellcheck findings at `-S warning` (SC1075 at `statusline.sh:388` among them); they are not fixed in this spec. The shellcheck gate is "no new finding": `shellcheck -S warning -f gcc` output for both scripts, line and column numbers stripped and sorted, has no line absent from `.scratch/043/baseline-shellcheck.txt`. The pytest runner is `/opt/homebrew/bin/pytest` (the default `python3` lacks pytest). If T002b records failures, the smoke gate is "no check fails that passed in the baseline". The width check uses inline assignments, one command per mode. The T002a smoke change swaps to live with Phase 1 (T035). The warm-render gate is red at baseline under the sandbox (0.86 to 0.93 s against 0.40 s); for this spec it is "warm render no slower than baseline plus 10 percent" against `.scratch/043/baseline-time.txt`, timed the same way each phase (`/usr/bin/time -p`, second of two runs).

**Checkpoint**: copy identical to live; baseline recorded.

---

## Phase 1: Dollars are complete (User Story 1, P1)

**Goal**: Every model with 28-day usage gets a cost through exact price, family price, estimate, else null.
**Independent test**: a fixture with `claude-fable-5-2` and `claude-haiku-5-5` and no price entries gives non-null costs; Anthropic 7D total equals the sum of model costs.
**FRs**: 001, 002, 003, 016, 017. **SCs**: 001, 002.
**Serial constraint**: edits `collect_usage.py` and `test_collect_usage.py`, which phases 2, 4 and 5 also edit.

### Tests first

- [x] T003 [US1] Extend `.scratch/043/scripts/tests/fixtures/prices_fixture.json` with family cases: a priced claude family (fable at two versions, one gap), a gpt family, and ids with no priced family (`claude-zeta-1`). FR: FR-002, FR-003. Done: the file parses with `python3 -m json.tool` and contains the named ids.
- [x] T004 [US1] In `.scratch/043/scripts/tests/test_collect_usage.py` add: a `parse_family` table (claude, gpt, dated id, unknown; the family is the name stem across versions, so `gpt-5.6-sol` and `gpt-6.1-sol` are one family and `gpt-6.1-terra` is another); `price_for` for exact, family-below, family-above-only, estimate, none; a collector case with `claude-fable-5-2` and `claude-haiku-5-5` unpriced giving non-null `cost` in every window with tokens and Anthropic 7D total equal to the sum of model costs; `claude-zeta-1` giving `cost` null; a case where own entries exist and are used over the family. FR: FR-001, FR-002, FR-003. SC: SC-001. Done: `python3 -m pytest scripts/tests/test_collect_usage.py -q` run from `.scratch/043` fails on the new cases (red run pasted into the phase report) and passes the old ones.

### Implementation

- [x] T005 [US1] In `.scratch/043/scripts/statusline.d/collect_usage.py` add `parse_family` and `price_for` (exact, then nearest priced version at or below, else lowest above, then the OpenAI estimate map, else none) and use them in `calculate_cost` (about `:158`), `calculate_estimated_cost` (`:177`), `equiv_cost` (`:262`) and `tiered_input_price` (`:275`). The thread-path input-rate pricing stays until Phase 2. FR: FR-001, FR-002, FR-003. Done: T004 cases pass; no new network or import.
- [x] T006 [P] [US1] In `.scratch/043/skills/codex-bridge/reference/prices.json` add `claude-fable-5-2` and `claude-haiku-5-5` with the rates from the claude-api skill model table (the file's named source). If the source does not list an id, add no entry and write that in the phase report. FR: FR-002. Done: `python3 -m json.tool` parses the file; each added id has input, output, cache read and cache write rates, or the report names the missing source.
- [x] T007 [P] [US1] In `.scratch/043/scripts/statusline.d/SPEC.md` rewrite the Inputs lines for prices (about lines 24 to 26) to the exact, family, estimate, null chain and remove the "Missing price" line that FR-002 overrides. FR: FR-002, FR-016. Done: `grep -n "Missing price" .scratch/043/scripts/statusline.d/SPEC.md` finds nothing and the new chain is described.

### Acceptance

- [x] T008 [US1] Run the Gates on the copy, then the live dry run (quickstart "Live dry run"). Check every Claude model with 28-day tokens has non-null `d7.cost`, the session dollar cell is not a dash, and record the Anthropic 7D dollar total (target near 1,258). FR: FR-001, FR-017. SC: SC-001, SC-002. Done: Gates pass and the recorded figure sits beside the audit figure 787 in the phase report.

**Checkpoint**: Phase 1 works alone. Supervisor swap task T035 follows.

---

## Phase 2: OpenAI in-window tokens, same-source cost, calendar days (User Stories 2 and 4 scenario 2, P1)

**Goal**: OpenAI 5H and 1D count only in-window tokens; cost uses the shown tokens; 7D and 28D thread rows start at local midnight.
**Independent test**: a thread created 8 h ago with rollout events at -8 h (T=1000) and -1 h (T=1500) gives 5H tokens 500.
**FRs**: 004, 005, 007, 016, 017. **SCs**: 003, 004.
**Serial constraint**: edits `collect_usage.py` after Phase 1 is shipped.

### Tests first

- [x] T009 [US2] In `.scratch/043/scripts/tests/test_collect_usage.py` add tests that build a temporary `state_5` db and rollout files: spanning thread gives 5H 500 and 1D by local midnight; missing rollout for a thread created inside the window counts its lifetime; missing rollout for a thread created before the window gives 0 and one gap-log line; cost equals price times the category split of the shown tokens; no fixture shows a cost under $0.01 beside more than 1M tokens; the 7D thread start equals the usage.db `-6 days` local midnight; the 28D start is local midnight; a corrupt rollout line drops only that thread; a missing state db or rollout dir gives nulls and exit 0. FR: FR-004, FR-005, FR-007. SC: SC-003, SC-004. Done: new cases fail before T010 and T011 (red run recorded).

### Implementation

- [x] T010 [US2] In `.scratch/043/scripts/statusline.d/collect_usage.py` state-db block (about `:865` to `:963`) replace the four `updated_at >=` lifetime queries with `thread_window_tokens` reading rollout `token_count` deltas per thread, catching errors per thread and per file, skipping rollout files whose mtime is before the 28D start. FR: FR-005. SC: SC-003. Done: the T009 window and gap cases pass.
- [x] T011 [US2] In the same file: the Codex 5H usage.db block (about `:802` to `:823`) pairs cost with the in-window tokens from the same rows; `provider_windows.openai` and `openai_h5` (about `:1092` to `:1099`) follow; thread d7 start (`:875`) and d28 start (`:913`) move to local midnight; log gaps. Where a Σ or model cell takes the larger of two token sources, its cost comes from that same chosen source (clarification 2); add a T009 case with two sources that disagree. FR: FR-004, FR-007. SC: SC-004. Done: all T009 cases pass, including the two-source case.
- [x] T012 [P] [US2] In `.scratch/043/scripts/statusline.d/SPEC.md` update line 3, line 19 and line 26 for window-only tokens and same-source cost, narrow the "state tokens win" rule (thread lifetime totals stay the source for ALL and SESS), and correct the thread-store text from "fallback" to "the larger of two sources per model" (clarification C4). FR: FR-016. Done: `grep -n "fallback" .scratch/043/scripts/statusline.d/SPEC.md` shows no line describing the thread store as a fallback.

### Acceptance

- [x] T013 [US2] Run the Gates on the copy and the live dry run. Check the spanning model's 5H tokens fall by the pre-window share, OpenAI 5H cost is not `<.01` beside millions of tokens, and `time python3 .scratch/043/scripts/statusline.d/collect_usage.py ...` on live data is under 1 s. FR: FR-004, FR-005, FR-007, FR-017. SC: SC-003, SC-004. Done: Gates pass; the before and after 5H figure and the elapsed time are in the phase report.

- [x] T013a [US2] (added 2026-11-16, supervisor) Two fixes before the Phase 2 swap, tests first. (1) Ended 5H window: when the newest known Codex 5H `resets_at` is at or before `--now`, OpenAI 5H tokens and cost are 0 for every model, `openai_h5` and `provider_windows.openai.h5`, and the reset time is emitted as null (renderer draws a dash; confirm with the existing smoke fixture, no renderer change); future `resets_at` keeps the built behaviour. Check the Claude 5H path for the same fault and report with evidence, no change. SPEC.md one sentence. (2) Gap log volume: at most one line per run, `gaps openai <n> threads <tokens> tokens`, only when n or tokens differs from the last logged value (kept in the cache file the collector already writes); per-thread detail goes to new cache key `openai_gaps` (`{"threads": n, "tokens": t}`, null when sources are missing), added to `empty_result`, `contracts/cache-schema.md` and the SPEC.md output schema. Tests and dry runs always pass a scratch `gap_log`. FR: FR-004, FR-005. Done: new tests red then green; Gates pass on the copy.

**Checkpoint**: Phase 2 works alone. Supervisor swap task T036 follows.

---

**Open items (recorded 2026-11-16, supervisor; not fixed in this spec)**: (a) The Claude 5H path has the same ended-window fault: `collect_usage.py` ~:633 computes `claude_h5_window_start = resets_at - 5h` from `--claude-h5-resets-at` with no comparison against now. (b) Quota percent may be stale when the reset time is null.

---

## Phase 3: `30D` label becomes `28D` (User Story 4, P2)

**Goal**: The top border reads `SESS═══5H═══1D═══7D══28D══ALL` for every provider block, with the same box width.
**Independent test**: smoke asserts the new border three times.
**FRs**: 006, 016, 017. **SCs**: 006.

### Tests first

- [x] T014 [US4] In `.scratch/043/scripts/tests/statusline_smoke.sh` change the header assertion (about `:113` to `:114`) and the messages (about `:197` to `:315`) to expect `SESS═══5H═══1D═══7D══28D══ALL` x3. FR: FR-006. SC: SC-006. Done: the smoke script fails on the unchanged renderer (red run recorded).

### Implementation

- [x] T015 [US4] In `.scratch/043/scripts/statusline.sh` change `thdr` (about `:449`) to `28D` and update the comments at about `:181`, `:188`, `:190` to `:193`, `:311`, `:347`, `:357`, `:462`. FR: FR-006. Done: T014 passes and `grep -n "30D" .scratch/043/scripts/statusline.sh` finds nothing.
- [x] T016 [P] [US4] In `.scratch/043/scripts/statusline.d/collect_usage.py` update the `30D` comment (about `:720`) to `28D`. The cache key `d28` stays. FR: FR-006. Done: `grep -n "30D" .scratch/043/scripts/statusline.d/collect_usage.py` finds nothing.
- [x] T017 [P] [US4] In `.scratch/043/scripts/statusline.d/SPEC.md` replace `30D` with `28D` at about lines 66, 77, 78, 81, 118 to 126. FR: FR-006, FR-016. Done: `grep -n "30D" .scratch/043/scripts/statusline.d/SPEC.md` finds nothing.

### Acceptance

- [x] T018 [US4] Run the Gates on the copy and the width check. FR: FR-006, FR-017. SC: SC-006. Done: smoke passes; the three widths equal the baseline in `.scratch/043/baseline-width.txt`.

**Checkpoint**: Phase 3 works alone. Supervisor swap task T037 follows.

---

## Phase 4: Row ranking by 28-day tokens (User Story 3, P2)

**Goal**: The four rows per provider are the top four by 28-day tokens; unshown models stay in Σ.
**Independent test**: retired ids with high all-time and zero 28-day tokens are not shown.
**FRs**: 008, 016, 017. **SCs**: 005.

### Tests first

- [x] T019 [US3] Before any edit in this phase, freeze the inputs: copy the usage db and the Codex state db to `.scratch/043/frozen/` (read-only copies; rollouts are read in place) and save `provider_windows` from a dry run against those copies with a fixed `--now` (add the flag to the test harness call if the collector lacks one; say which) to `.scratch/043/pre4-windows.json`. Live data moves between runs, so the before and after comparison must use the same frozen inputs. Then in `.scratch/043/scripts/tests/test_collect_usage.py` rewrite both rank tests (about `:537` to `:570`): retired ids not shown; 28D tie breaks on ALL then id; a pin outside the top four takes row 4; a pin inside keeps its rank; a non-shown model stays in `provider_windows`; `nvidia/...:free` under backend claude is not a Claude row. FR: FR-008. SC: SC-005. Done: the new cases fail on the old ranking (red run recorded) and `pre4-windows.json` exists.
- [x] T020 [P] [US3] In `.scratch/043/scripts/tests/statusline_smoke.sh` check the rank block (about `:360` to `:395`); where it asserts row order, update it to the 28-day order. FR: FR-008. Done: the smoke script asserts nothing contradicting T019, or the report states the block asserts no order.

### Implementation

- [x] T021 [US3] In `.scratch/043/scripts/statusline.d/collect_usage.py` change `pick_rows` (about `:149` to `:156`) and its call sites (about `:1030` to `:1034`) to rank by 28-day tokens, then all-time, then id, with the pin rule; restrict the Claude candidate filter (about `:350` to `:363`) to the `claude-` prefix. FR: FR-008. Done: all T019 cases pass.
- [x] T022 [P] [US3] In `.scratch/043/scripts/statusline.d/SPEC.md` update line 33 and line 62 (ranking rule; the 2026-11-09 ruling is replaced). FR: FR-008, FR-016. Done: the text says 28-day ranking and no longer says all-time.

### Acceptance

- [x] T023 [US3] Run the Gates on the copy and the live dry run. Check Claude rows are opus-5-5, sonnet-5-5, fable-5-2, fable-5-1 (haiku-5-5 is fifth unless pinned), and `jq '.provider_windows'` of a dry run against the same frozen inputs and `--now` as T019 equals `.scratch/043/pre4-windows.json`. FR: FR-008, FR-017. SC: SC-005. Done: Gates pass and the Σ diff is empty.

**Checkpoint**: Phase 4 works alone. Supervisor swap task T038 follows. Tell the operator at swap that rows change.

---

## Phase 5: Cache additions for pace (User Story 5 prep, P3)

**Goal**: The cache carries per-model `h5.cost`, `first_seen` and a `pace` baseline, per `contracts/cache-schema.md`. The renderer is unchanged.
**Independent test**: own history of 7 days or more gives `pace.source` own with `days` = min(28, history); a 2-day-old id with a 60-day family gives source family.
**FRs**: 011, 012, 016, 017. **SCs**: 009.

### Tests first

- [x] T024 [US5] In `.scratch/043/scripts/tests/test_collect_usage.py` add: own history 7 days or more gives source own and days = min(28, history); a new id 2 days old with a 60-day family gives source family and family sums; no family and no rows gives null pace; `h5.cost` equals price times the 5H rows; every new key is present (null) when sources are missing; the same keys on `free_top4_d7` rows. FR: FR-011, FR-012. Done: new cases fail first (red run recorded).

### Implementation

- [x] T025 [US5] In `.scratch/043/scripts/statusline.d/collect_usage.py` add `first_seen` per model (all-time GROUP BY about `:639` to `:676` and thread MIN(created_at)), `h5.cost` per model (Claude 5H block about `:781` to `:800` and the Phase 2 pairs), `pace_baseline`, the same for `free_top4_d7` (about `:734` to `:749`); add the keys to `empty_result` (about `:30` to `:76`) following `specs/043-statusline-tallies-pace/contracts/cache-schema.md`. Note (supervisor 2026-11-16): OpenAI ALL and SESS cost still use the input-rate path while window cells price by category, so `pace.all_cost` for an OpenAI model must be priced by the same category method as `d28.cost` (running totals at each thread's last rollout event; threads without a rollout priced as uncached input and counted in `openai_gaps`), or the 28D pace cell compares two pricing methods. FR: FR-011, FR-012. Done: all T024 cases pass and a dry-run cache validates against the contract field list.
- [x] T026 [P] [US5] In `.scratch/043/scripts/statusline.d/SPEC.md` update the output schema (about lines 33 to 58) with `h5.cost`, `first_seen` and `pace`. FR: FR-016. Done: each key in `contracts/cache-schema.md` appears in the schema text.
- [x] T025a [US5] (added 2026-11-16, supervisor) Tests first. OpenAI `all.cost` and `session.cost`, per model and in `provider_windows.openai` and the session sums, use the category method (running totals at each thread's last rollout event; SESS from the threads the session path already selects; a thread with no rollout priced as uncached input). Tokens unchanged. A test asserts `all.cost == pace.all_cost` for an own-source OpenAI model. Update SPEC.md where it says OpenAI pricing is input-only (the `~` note and the ALL-cell note). Report before and after ALL dollars for the four OpenAI rows, the OpenAI Σ ALL cell and DOL. Verify Claude `all.cost` and `d28.cost` use the same pricing call. Then redo T028 and restage stage5. FR: FR-011. Done: tests pass, one pricing method per row.

### Acceptance

- [x] T027 [US5] Run the Gates on the copy with the renderer unchanged (forward compatibility: old renderer with new cache), then the live dry run: `pace.source` is own for opus-5-5 and family for fable-5-2 until 2026-11-18. FR: FR-012, FR-017. SC: SC-009. Done: Gates pass and the two `pace.source` values are in the phase report.
- [x] T028 [US5] Capture the raw render fixture for the byte-identical check before any Phase 6 edit. Using a frozen cache (copy the T027 dry-run cache to a fixed session id) and `scripts/tests/fixtures/statusline_session.json`, save raw output (escapes kept) to `.scratch/043/capture/truecolor.raw`, `256.raw` and `nocolor.raw` (`COLORTERM=truecolor`, `STATUSLINE_COLORS=256`, `NO_COLOR=1`), and the plain-text widths per mode to `.scratch/043/capture/widths.txt`. The capture covers ALL, gauges and names. FR: FR-014, FR-015. SC: SC-010, SC-006. Done: three non-empty `.raw` files exist; `widths.txt` shows one width, equal to the baseline.

**Checkpoint**: Phase 5 works alone. Supervisor swap task T039 follows. T028 stays valid only while the renderer is unchanged.

---

## Phase 6: Pace colouring and the new range (User Story 5, P3)

**Goal**: SESS, 5H, 1D, 7D and 28D model cells, Σ cells and dollar cells colour by cost-weighted pace with permille = clamp(500 + 250 log2 r, 0, 1000). ALL, gauges and names stay byte-identical.
**Independent test**: r = 0.25, 1, 4 give `0;224;255`, `127;163;235`, `255;102;214` in truecolor.
**FRs**: 009, 010, 011, 012, 013, 014, 015, 016, 017. **SCs**: 006, 007, 009, 010.
**Serial constraint**: all renderer edits are in `statusline.sh`; one builder, in order.

### Tests first

- [x] T029 [US5] In `.scratch/043/scripts/tests/statusline_smoke.sh` add truecolor raw expectations: r = 0.25 gives `0;224;255`, r = 1 gives `127;163;235`, r = 4 gives `255;102;214` on a model cell; that cell's escape is unchanged when another model in the column grows tenfold (SC-007); a model with null pace renders `128;128;136`; the 28D model cell is neutral when history is 28 days or less; a FREE row is paced like any other (clarification C5); ALL column, gauge and name escapes byte-identical to `.scratch/043/capture/truecolor.raw` (SC-010); `NO_COLOR` text identical to `nocolor.raw` except cell text; no legend and no new glyph. Recompute the colour expectations at about `:228` to `:315` for the new range. FR: FR-009, FR-010, FR-013, FR-014, FR-015. SC: SC-007, SC-010. Done: the new checks fail on the old renderer (red run recorded).

### Implementation

- [x] T030 [US5] In `.scratch/043/scripts/statusline.sh` extend the jq dump MODEL (about `:82`) and FREE (`:83`) with `h5.cost` and `pace.*`, and the read loop (about `:101` to `:104`). FR: FR-011, FR-012. Done: the dump carries the new fields; with an old cache (fields absent) the render still passes the existing smoke.
- [x] T031 [US5] In `.scratch/043/scripts/statusline.sh` change the `pacecols` range (about `:199` to `:201`) from `500*` to `250*` and add the `modelpace` awk beside `pacecols`: cost-weighted ratio r against the model's own or family baseline, grey for null pace, neutral for 28D when history is 28 days or less, grey under 30 minutes for SESS. Update comments (about `:181` to `:202`). FR: FR-012, FR-013. Done: the r = 0.25 / 1 / 4 checks of T029 pass.
- [x] T032 [US5] In `.scratch/043/scripts/statusline.sh` change the model-cell colour loop (about `:325` to `:346`) so `sharecols` applies to column 5 (ALL) only and window columns use `modelpace`; make Σ token cell colours (about `:351` to `:354`, TH columns 0 to 4) follow the CH columns. FR: FR-010, FR-014. Done: all T029 checks pass, including ALL, gauge and name byte-identity.
- [x] T033 [P] [US5] In `.scratch/043/scripts/statusline.d/SPEC.md` rewrite the colour model (about lines 108 to 130) with the new range, and delete the Rulings section (about `:148` to `:170`) after folding it into the contract text, keeping item 6 as an open item; resolve every "NOT YET IN CODE" marker and "Replaced by" note. FR: FR-016, FR-015. Done: `grep -n "NOT YET IN CODE\|Replaced by" .scratch/043/scripts/statusline.d/SPEC.md` finds nothing, and item 6 is listed as open.

### Acceptance

- [x] T034 [US5] Run the Gates on the copy. Then: `cmp` the ALL column, gauge and name escapes of a fresh raw render against `.scratch/043/capture/*.raw` (SC-010; differences allowed only in model, Σ and dollar window cells); run the width check (SC-006); time two warm renders (SC-009, under 0.40 s, fork count unchanged). FR: FR-009 to FR-015, FR-017. SC: SC-006, SC-007, SC-009, SC-010. Done: Gates pass; widths equal baseline in all three modes; the byte comparison reports no difference outside the allowed cells; timing is recorded.

**Checkpoint**: Phase 6 works alone. Supervisor swap task T040 follows, then T041.

---

## Phase ownership

| Phase | Builder files (all under `.scratch/043/`) | Shared with |
|---|---|---|
| 1 | `scripts/statusline.d/collect_usage.py`, `scripts/tests/test_collect_usage.py`, `scripts/tests/fixtures/prices_fixture.json`, `skills/codex-bridge/reference/prices.json`, `scripts/statusline.d/SPEC.md` | 2, 4, 5 |
| 2 | `collect_usage.py`, `test_collect_usage.py`, `SPEC.md` | 1, 4, 5 |
| 3 | `scripts/statusline.sh`, `scripts/tests/statusline_smoke.sh`, `collect_usage.py` (comment only), `SPEC.md` | 6 |
| 4 | `collect_usage.py`, `test_collect_usage.py`, `statusline_smoke.sh` (if asserts order), `SPEC.md` | 1, 2, 5 |
| 5 | `collect_usage.py`, `test_collect_usage.py`, `SPEC.md` | 1, 2, 4 |
| 6 | `statusline.sh`, `statusline_smoke.sh`, `SPEC.md` | 3 |

## Dependencies and execution order

- Phase 0, then phases 1 to 6 in order. A phase starts after the supervisor has swapped and verified the previous phase (the copy already holds the verified content, so no re-copy).
- Within a phase: tests, implementation, SPEC.md edit, acceptance. A `[P]` task may run beside the other implementation tasks of its phase only when it names a different file.
- T028 needs T027; T029 needs T028; T034 needs T029 to T033.
- Phase 6 colour depends on Phase 1 (dollar weights) and Phase 5 (cache fields).

## Parallel examples

- Phase 1: after T005 starts, T006 (`prices.json`) and T007 (SPEC.md) run beside it.
- Phase 3: T016 (collector comment) and T017 (SPEC.md) run beside T015.
- Phase 4: T020 (smoke) runs beside T019 (collector tests).
- Phase 6: T033 (SPEC.md) runs beside T030 to T032.

## Implementation strategy

- MVP is Phase 1 (true dollars) swapped alone; each later phase also ships alone and leaves the Gates green.
- Old renderer with new cache and new renderer with old cache both work (cache-schema contract), so a collector phase never needs a renderer change.
- Stop and report on any red Gate; two failed supervisor checks on the same phase escalate by one rung.

---

## Coverage: functional requirement to task ids

| FR | Tasks |
|---|---|
| FR-001 | T004, T005, T008 |
| FR-002 | T003, T004, T005, T006, T007 |
| FR-003 | T003, T004, T005 |
| FR-004 | T009, T011, T013 |
| FR-005 | T009, T010, T013 |
| FR-006 | T014, T015, T016, T017, T018 |
| FR-007 | T009, T011, T013 |
| FR-008 | T019, T020, T021, T022, T023 |
| FR-009 | T029, T031, T034 |
| FR-010 | T029, T032, T034 |
| FR-011 | T024, T025, T030, T031 |
| FR-012 | T024, T025, T027, T030, T031 |
| FR-013 | T029, T031, T034 |
| FR-014 | T028, T029, T032, T034 |
| FR-015 | T028, T029, T033, T034 |
| FR-016 | T007, T012, T017, T022, T026, T033, T042 |
| FR-017 | T002, T008, T013, T018, T023, T027, T034, T035 to T040 |

## Coverage: success criterion to task ids

| SC | Tasks |
|---|---|
| SC-001 | T004, T008 |
| SC-002 | T008 |
| SC-003 | T009, T010, T013 |
| SC-004 | T009, T011, T013 |
| SC-005 | T019, T021, T023 |
| SC-006 | T002, T018, T028, T034, T037 |
| SC-007 | T029, T034 |
| SC-008 | T041 (supervisor and operator check) |
| SC-009 | T002, T027, T034, T040 |
| SC-010 | T028, T029, T034 |

Result: every FR-001 to FR-017 and SC-001 to SC-010 maps to at least one task.

---

## Supervisor handoff (after the phase's builder tasks)

Supervisor-owned. Builders never run these. The swap is atomic: `cp` to a `.new` file, then `mv -f` over the live path, collector before renderer, SPEC.md in the same swap (plan Working rule step 4). Paths use `R=/Users/domattioli/Projects/agents-inc`, `W=$R/.scratch/043`.

- [x] T035 Phase 1 swap. Check before the swap: re-run the Gates on the copy yourself (not the builder's report) and confirm `W/skills/codex-bridge/reference/prices.json` parses. Swap `collect_usage.py`, `prices.json`, `SPEC.md`, `scripts/tests/test_collect_usage.py` and `scripts/tests/fixtures/prices_fixture.json` (collector first; the tests land with the code they test). Then re-run the Gates from `$R`, watch two live renders and `~/.claude/statusline-domi.log` for a traceback. FR: FR-017. Done: Gates pass in `$R`, session dollar cell is not a dash, no traceback in the log.
- [x] T036 Phase 2 swap. Check before: Gates on the copy, T013 live dry run figures, collector time under 1 s. Swap `collect_usage.py`, `scripts/tests/test_collect_usage.py`, `SPEC.md`. Re-run Gates from `$R`, two live renders, log. FR: FR-017. Done: as T035.
- [x] T037 Phase 3 swap. Check before: Gates and the width check on the copy, three equal widths equal to baseline. Swap `collect_usage.py` (comment only), `statusline.sh`, `SPEC.md`, and `scripts/tests/statusline_smoke.sh`. Re-run Gates from `$R`; confirm the live top border reads `28D`. FR: FR-006, FR-017. SC: SC-006. Done: live border reads `28D` and widths are unchanged.
- [x] T038 Phase 4 swap. Check before: Gates on the copy, T023 Σ diff empty, Claude rows match T023. Tell the operator the visible rows change. Swap `collect_usage.py`, `scripts/tests/test_collect_usage.py`, `scripts/tests/statusline_smoke.sh` (if T020 changed it), `SPEC.md`. Re-run Gates from `$R`, two live renders, log. FR: FR-008, FR-017. SC: SC-005. Done: as T035.
- [x] T039 Phase 5 swap. Check before: Gates on the copy, T027 `pace.source` values, `T028` capture files present. Swap `collect_usage.py`, `scripts/tests/test_collect_usage.py`, `SPEC.md`. Re-run Gates from `$R`; confirm the live cache holds the new keys and the live render is unchanged. FR: FR-011, FR-012, FR-017. Done: new keys present in the live cache; live raw render equals `W/capture/truecolor.raw` for the frozen case.
- [x] T040 Phase 6 swap. Check before: Gates on the copy, T034 byte comparison and width check redone by the supervisor, warm render under 0.40 s. Swap `statusline.sh`, `statusline_smoke.sh`, `SPEC.md`. Re-run Gates from `$R`, inspect two live renders, read the log. FR: FR-009 to FR-015, FR-017. SC: SC-006, SC-009, SC-010. Done: Gates pass in `$R`; ALL, gauge and name colours unchanged.
- [x] T041 OPERATOR (2026-11-16: operator answered yes, reads fine; noted 7D reads purple across rows and asked why rows are not sorted by ALL) Show the operator three live cells (cool, mid, hot) and ask which model runs above its normal, without a legend; time the answer. Report C1 (haiku-5-5 not in the live top four), C2 (OpenAI estimate map kept) and C5 (FREE rows paced) for operator acceptance. FR: FR-009, FR-015. SC: SC-008. Done: the operator names the hot model in under 10 seconds, or the failure is recorded with the cell shown.
- [ ] T042 Move the finished specs to DomI: `bash /Users/domattioli/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. Supervisor-owned; needs a clean working tree. Shared with spec 042: run it once for both, after both specs are finished. FR: FR-016. Done: `specs/043-statusline-tallies-pace/` is gone from the repo and present under DomI `specs/consumers/agents-inc/`.
