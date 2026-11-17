<!-- provenance: author=domattioli model=claude-opus-5-5 effort=low date=2026-11-15 skill=speckit-plan repo=agents-inc session=b437620e -->
# Implementation Plan: Status line true tallies and pace colours

**Branch**: `development` (feature dir `043-statusline-tallies-pace`; no branch change) | **Date**: 2026-11-15 | **Spec**: `specs/043-statusline-tallies-pace/spec.md`
**Input**: spec (status Clarified, six clarifications), operator rulings 2026-11-15 in `scripts/statusline.d/SPEC.md`.

## Summary

Make every figure in the status line table true, then make its colour mean one thing. Tallies first: price every model through an exact, family, estimate chain; measure OpenAI window tokens from rollout `token_count` deltas and price them from the same rows; align 7D and 28D to calendar days and relabel `30D` as `28D`; rank rows by 28-day tokens. Then colour: the collector adds per-model `h5.cost`, `first_seen` and a `pace` baseline; the renderer colours SESS to 28D model and Σ cells by cost-weighted pace with the range 500 + 250 log2 r. ALL, gauges and names stay byte-identical. Evidence and decisions: `research.md` R1 to R8.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib) for the collector; Bash 3.2 + POSIX awk + jq for the renderer
**Primary Dependencies**: none new
**Storage**: per-session JSON cache `~/.claude/statusline-cache/<sid>.json` (contract `contracts/cache-schema.md`); read-only `~/.codex-bridge/usage.db`, `~/.codex/state_5.sqlite`, `~/.codex/sessions/**/rollout-*.jsonl`; `skills/codex-bridge/reference/prices.json`
**Testing**: `python3 -m pytest scripts/tests/test_collect_usage.py -q`; `bash scripts/tests/statusline_smoke.sh`; `shellcheck -S warning`
**Target Platform**: macOS operator terminal (truecolor, 256, NO_COLOR); Linux docker for CI parity
**Project Type**: CLI status line (collector + renderer)
**Performance Goals**: warm render < 0.40 s (Gate 4); collector < 5 s timeout (rollout scan about 0.2 s for 28 days, R1)
**Constraints**: $0; no network; exit 0 always; no traceback on missing sources; box width fixed in three colour modes; live script is the working-tree file
**Scale/Scope**: 4 code files (`collect_usage.py`, `statusline.sh`, `prices.json`, `SPEC.md`), 2 test files plus fixtures, 6 phases

## Constitution Check

Constitution 1.9.2 unratified; violations report as WARN. Pre- and post-design results are the same.

| Principle | Result |
|---|---|
| P0 cross-reference | Pass. SPEC.md stays the single contract; plan cites it. |
| P1 repo-scoped writes | Pass. Builders write `.scratch/043/`; only the orchestrator swaps files into `scripts/` and `skills/codex-bridge/reference/`. No writes under `~/.claude` or `~/.codex` except the collector's own cache and log, as today. |
| P2 ladder | Pass. Opus orchestrator, sonnet builders, one phase at a time. |
| P3 no self-graded gates | Pass. Orchestrator re-runs Gates and the width check itself; delegate reports are not acceptance (SPEC.md Operator rules). |
| P4 deterministic policy | Pass. All checks are scripts. |
| P5 $0 | Pass. No API, no network; prices from the existing file. |
| P6 audience docs | Pass. SPEC.md is agent-facing and compressed. |
| P9 surgical edits | Pass. Each phase names its line ranges; no full rewrite of either script. |

## Project Structure

### Documentation (this feature)

```text
specs/043-statusline-tallies-pace/
├── spec.md                 # input, not edited
├── plan.md                 # this file
├── research.md             # R1-R8, spec conflicts C1-C5
├── data-model.md           # entities, windows, pace rules
├── quickstart.md           # work copy, gates, width check, swap
├── contracts/cache-schema.md
└── tasks.md                # later, speckit-tasks
```

### Source Code

```text
scripts/statusline.d/collect_usage.py   # pricing, OpenAI windows, ranking, pace baseline
scripts/statusline.sh                   # header label, MODEL/FREE dump fields, modelpace, range
scripts/statusline.d/SPEC.md            # contract, folded rulings
skills/codex-bridge/reference/prices.json   # two entries
scripts/tests/test_collect_usage.py     # collector tests
scripts/tests/statusline_smoke.sh       # renderer smoke
scripts/tests/fixtures/                 # new rollout + state-db builders live inside the tests (tmp dirs), prices fixture gains family cases
```

**Structure Decision**: no new file except test fixtures; helpers (`parse_family`, `price_for`, `thread_window_tokens`, `pace_baseline`) are functions in `collect_usage.py`, the new awk (`modelpace`) sits beside `pacecols` in `statusline.sh`.

## Working rule for every phase (live-script risk)

The operator's terminal runs `~/Projects/agents-inc/scripts/statusline.sh` on every render; an edit in the working tree is live at once. Therefore:
1. Builder copies `scripts/` and `prices.json` into `.scratch/043/` (quickstart) and edits only the copy.
2. Tests are written first in the copy and fail before the code change (record the red run).
3. Orchestrator runs on the copy: Gates 1-5, the width check in truecolor, 256 and NO_COLOR (one equal width, same as before the phase), and the live dry run (quickstart) with `--prices` pointed at the copy.
4. Orchestrator swaps by `cp` + atomic `mv`, collector before renderer, then re-runs the Gates in the repo and watches two live renders and the log.
5. SPEC.md edits for the phase land in the same swap.

## Phases

Order: tallies before colours. Each phase leaves the status line working and the Gates green. Old renderer + new cache and new renderer + old cache both work (contract), so a collector phase never needs a renderer change to stay green.

### Phase 1 — Prices and family fallback (US1; FR-001 to FR-003)
- Files: `collect_usage.py` (`calculate_cost` `:158`, `calculate_estimated_cost` `:177`, `equiv_cost` `:262`, `tiered_input_price` `:275`; new `parse_family`, `price_for`), `prices.json` (`claude-fable-5-2`, `claude-haiku-5-5` from the claude-api skill model table, the file's named source; if absent, no entry and note it), `tests/fixtures/prices_fixture.json`, `test_collect_usage.py`, SPEC.md Inputs lines 24-26.
- Tests first: `parse_family` table (claude, gpt, dated, unknown); `price_for` exact / family-below / family-above-only / estimate / none; collector fixture with fable-5-2 and haiku-5-5 unpriced -> non-null cost every window, Anthropic 7D total = sum of model costs; unknown-family id -> `cost` null.
- Thread-path input-rate pricing stays until Phase 2 (it calls `price_for` for the input rate).
- Acceptance: tests green; live dry run shows non-null `d7.cost` for every Claude row with 28-day tokens and session `$` not a dash; Claude 7D dollars near the audit 1,258 (SC-002) — record the figure.

### Phase 2 — OpenAI in-window tokens, same-source cost, calendar days (US2, US4 scenario 2; FR-004, FR-005, FR-007)
- Files: `collect_usage.py` state-db block `:865-963` (replace the four `updated_at >=` lifetime queries with `thread_window_tokens`), Codex 5H usage.db block `:802-823` (pair rule), provider `openai_h5`/`provider_windows.openai` `:1092-1099`, d7 start `:875` and d28 start `:913` to local midnight; gap log; `test_collect_usage.py`; SPEC.md line 3, line 19, line 26.
- Tests first: tmp state_5 db + rollout files built in the test: thread created -8 h with events at -8 h (T=1000) and -1 h (T=1500) -> 5H 500, 1D per midnight; missing rollout created inside window -> lifetime counted; missing rollout created before -> 0 and log line; cost equals price × the category split of the shown tokens; SC-004 (no cost under $0.01 beside > 1M tokens); 7D thread start equals usage.db `-6 days` local midnight; missing state db / rollout dir -> nulls, exit 0.
- Acceptance: tests green; live dry run `gpt-6.1-sol` (or the current spanning model) 5H drops by the spanning thread's pre-window share; OAI 5H cost no longer `<.01` beside millions of tokens; collector run time on live data under 1 s (`time`).

### Phase 3 — `30D` label to `28D` (US4 scenario 1; FR-006)
- Files: `statusline.sh:449` (`thdr`) and comments `:181, :188, :190-193, :311, :347, :357, :462`; `statusline_smoke.sh:113-114` assertion and messages `:197-315`; `collect_usage.py:720` comment; SPEC.md `:66, :77, :78, :81, :118-126`.
- Tests first: smoke `:113` expects `SESS═══5H═══1D═══7D══28D══ALL` x3 (red on old script).
- Acceptance: smoke green; width check equal to pre-phase width in all three modes (SC-006).
- Independent of Phases 1-2 in code (renderer only); may run in parallel with Phase 1 or 2 only if SPEC.md edits are merged by the orchestrator.

### Phase 4 — Row ranking by 28-day tokens (US3; FR-008)
- Files: `collect_usage.py` `pick_rows` `:149-156`, call sites `:1030-1034`, Claude candidate filter `:350-363` (`claude-` prefix); `test_collect_usage.py:537-570` (rewrite both rank tests); smoke rank block `:360-395` if it asserts order; SPEC.md line 33, line 62.
- Tests first: retired ids (high ALL, zero 28D) not shown; 28D tie -> ALL -> id; pin outside top 4 takes row 4, pin inside keeps rank; non-shown model still in `provider_windows`; `nvidia/...:free` under backend claude not a Claude row.
- Acceptance: tests green; live dry run Claude rows = opus-5-5, sonnet-5-5, fable-5-2, fable-5-1 (research C1: haiku-5-5 fifth unless pinned); Σ cells unchanged before/after (diff of `provider_windows`).

### Phase 5 — Cache additions for pace (prep for US5; FR-011, FR-012)
- Files: `collect_usage.py` (per-model `first_seen` from the all-time GROUP BY `:639-676` and threads MIN(created_at); `h5.cost` per model from the Claude 5H block `:781-800` and Phase 2 pairs; `pace_baseline`; same for `free_top4_d7` `:734-749`); `empty_result` `:30-76` gains the keys; `test_collect_usage.py`; SPEC.md output schema lines 33-58; `contracts/cache-schema.md` is the target.
- Tests first: own history >= 7 d -> source own, days = min(28, hist); new id 2 d old with a 60 d family -> source family, family sums; no family, no rows -> null pace; `h5.cost` = price × h5 rows; every new key present (null) with missing sources.
- Acceptance: tests green; renderer unchanged and smoke green against the new cache (forward compatibility); live dry run shows `pace.source` own for opus-5-5, family for fable-5-2 until 2026-11-18, own after.

### Phase 6 — Pace colouring and the new range (US5; FR-009 to FR-015)
- Files: `statusline.sh` jq dump MODEL `:82` and FREE `:83` (add `h5.cost`, `pace.*`), read loop `:101-104`, `pacecols` range `:199-201` (`500*` -> `250*`), new `modelpace` awk next to `pacecols`, model-cell colour loop `:325-346` (sharecols only for column 5), Σ token colours `:351-354` (TH cols 0-4 = CH), comments `:181-202`; `statusline_smoke.sh` colour expectations `:228-315` recomputed for the new range; SPEC.md colour model `:108-130` and delete Rulings `:148-170` (keep item 6 as an open item).
- Tests first (smoke, truecolor raw): r = 0.25 -> `0;224;255`, r = 1 -> `127;163;235`, r = 4 -> `255;102;214` on a model cell; that cell's escape unchanged when another model in the column is ×10 (SC-007); model with null pace -> `128;128;136`; 28D model cell neutral when hist <= 28; ALL column escapes byte-identical to a capture taken before the phase, gauge and name escapes likewise (SC-010); NO_COLOR output text identical to pre-phase except cell text.
- Acceptance: smoke green; Gate 4 under 0.40 s warm (fork count unchanged, R5); width check in three modes; live render inspected by the orchestrator, then operator SC-008 check.

### Shared-file map (no parallel runs on the same file)

| File | Phases |
|---|---|
| `collect_usage.py` | 1, 2, 4, 5 (serial) |
| `test_collect_usage.py` | 1, 2, 4, 5 |
| `statusline.sh` | 3, 6 |
| `statusline_smoke.sh` | 3, (4), 6 |
| `SPEC.md` | all |
| `prices.json` | 1 |

Only Phase 3 can overlap a collector phase, and only with SPEC.md merged by the orchestrator. Recommended order: 1, 2, 3, 4, 5, 6.

## Risks

- Live script: any working-tree edit is live (mitigation: work copy and atomic swap, above).
- Traceback in the collector: `main` catches all and writes `empty_result` (`:1192-1211`), which would blank the table. New helpers must catch per thread/per file so one bad rollout line drops that thread, not the cache. Test: corrupt rollout line fixture.
- Collector time: 28-day rollout scan about 0.2 s now; grows with use. If a dry run exceeds 2 s, limit the scan to threads with `updated_at >= window start` (already the plan) and skip files whose mtime is before the 28D start.
- Copied `config.json` points at the live `prices.json`; dry runs must pass `--prices` (quickstart).
- Rows change on swap of Phase 4 (operator sees different models). Expected; tell the operator at swap.
- Pace colours change everywhere at once in Phase 6; capture a before render (raw) for SC-010 comparison before editing.
- Spec conflicts C1 (haiku-5-5 not in live top 4), C2 (OpenAI estimate map kept), C5 (FREE rows paced) need operator acceptance; C2 or C5 reversal changes only Phase 1 or Phase 6.

## Complexity Tracking

None.
