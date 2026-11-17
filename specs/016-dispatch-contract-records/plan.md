<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Dispatch Contract Header and Dispatch Records

**Branch**: `development` (no feature branch) | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: `specs/016-dispatch-contract-records/spec.md` (Clarifications and addendum answered 2026-10-01). Plan written inline by the Supervisor (Orchestrator rung, ruling R1).

## Summary

1. The ledger gains optional fields (effort, input/output/cache tokens, files created, supervisor verdict, cwd, source). Return rows carry the dispatch's `run_id`. Old rows load with the new fields unknown.
2. A read-only join attaches delegated token usage from `usage.db` to a ledger node when the match is unambiguous, and reports unknown otherwise.
3. An owned `PostToolUse` hook writes a minimal dispatch row for Claude `Agent`/`Task` spawns and for `DelegateAgent` calls into a host ledger under the user-scope state directory. `agents-inc ledger append` writes the return row and fails closed without a supervisor verdict.
4. A fixed header file and a slot template carry the 14-element contract. The lint accepts a `CONTRACT: <path>` reference for file-capable delegates and rejects it for bare-API delegates.
5. A script generates the workerbee tier table from `models.json` and `routing.json` into a marker block, and a drift test fails when the block is stale.
6. The workerbee skill states the delegate persistence rule, and the header carries its inheritance line.
7. `research.md` records the #4 and #27 findings. No DomI file is written.

## Technical Context

**Language/Version**: Python 3.9+ standard library
**Primary Dependencies**: none new
**Storage**: repo ledger `<workspace>/.workerbees/ledger.jsonl` and `workerbees.db` (unchanged locations); host ledger `<state>/host-ledger/.workerbees/ledger.jsonl` (JSONL only), where `<state>` is `InstallPaths.state` (`~/.local/state/agents-inc`); `~/.codex-bridge/usage.db` read only
**Testing**: `python3 -m unittest`; temp workspaces, a fake `InstallPaths` home, generated `usage.db` fixtures; no real model calls
**Constraints**: hook timeout 5 s, fail open; ledger writes never raise (existing FR-008 of spec 002); `agents_inc/install/*` edits are Executive-owned (operator ruling 2026-10-01); `.gitignore:224-232` ignores paths containing `key`, `secret`, `token`, `credential` (new file names avoid them)
**Scale/Scope**: one ledger module extended, two new library modules, two new scripts, one lint extension, two new skill files, one skill section set, five new test modules

## Existing code (evidence, re-grepped 2026-10-01 at `e56cd79` plus the uncommitted batch C)

- `agents_inc/ledger.py:30-45` frozen `Node` dataclass (13 fields); `:70` `record_dispatch`; `:225` `record_return` writes `"run_id": None` at `:248`; `:273` `_dual_write_return` passes `usage={"seconds", "subscription_calls"}`; `:334` `load` merges duplicate ids (later non-null wins); `:497` `lint` has three rules (depth, same_vendor_review, frontier_without_gate) and no orphan rule; `:618` `to_json` and `:641` `from_json` list fields by hand.
- `agents_inc/store.py:179-229` `append_event(usage=...)` already writes `input_tokens`, `output_tokens`, `reasoning_tokens`, `cost_micro_usd` into the SQLite `usage` table (`docs/governance/SCHEMA-3NF.md:273-278`). The schema has no columns for effort, cache tokens, files, or verdict. `agents_inc/schema.py:69-101` `init` compares object names only and raises on a missing or extra table, so a new table would break every existing `workerbees.db`.
- `agents_inc/derivation_store.py:5-8`: the Node shape is the ledger.py schema; derivations are a separate store. Not touched.
- `skills/codex-bridge/scripts/usage_db.py:35-46` `usage(uid, ts, day, backend, model, input_tokens, output_tokens, cache_read, cache_write, reasoning)`. No run or job id column. Claude rows come from session transcripts with `backend='claude'` (`:136`), one row per assistant turn of any session; delegated rows come from `~/.codex-bridge/usage.jsonl`, written by `gask.sh:17`, `oask.sh:17`, `mask.sh:16`.
- `agents_inc/install/hook.py` (batch C, uncommitted): `agent_done(paths, payload)` releases the in-flight entry; `run` routes `agent-done`. `agents_inc/install/host_wiring.py:112-113` adds `PostToolUse` `Agent|Task` `agent-done`, timeout 5, Claude host only. `agents_inc/install/cli.py:105` `hook` choices include `agent-done`; `:110` routes `hook` before the receipt check.
- `agents_inc/install/bundle.py:16` ships the whole `agents_inc` package and `skills/workerbee`, so new modules and skill files reach the installed release.
- `DelegateAgent` is an MCP tool; its hook `tool_name` is `mcp__delegate-agent__DelegateAgent`; input `{prompt, model (astra|luna|sol|terra, default luna), cwd}`, no description (tool schema, 2026-10-01).
- `skills/workerbee/scripts/check_dispatch_prompt.py:60-113` `check(text, tier)`; `:136-170` `main` parses `--with-handoff-lint`, `--profile`, `--tier`.
- `skills/workerbee/SKILL.md` (937 lines after batch C): ladder table `:143-149` uses `ultra/flagship/workhorse/flash/bottom rung`; roster `:206-226` tier cells use the same plus `workhorse-ish` and `—`; Step 3b ends `:404` ("Do not re-litigate it as a doc gap."); Step 4 `:406`; Step 11 tick-list ends `:717` ("non-compliant, do not send it.").
- `agents_inc/models.json` holds 39 ids, all tiered `executive|orchestrator|workhorse|grunt`; `agents_inc/routing.json` `tiers` maps rung -> provider -> default id. `tests/test_vocab_drift_guard.py` already ties both to `docs/governance/ROUTING-RANKING.md`.

## Design decisions

- **DD1 ledger fields** (FR-001, FR-002, SC-001, SC-002): `Node` gains trailing fields, all default `None`: `effort`, `input_tokens`, `output_tokens`, `cache_read`, `cache_write`, `files_created` (tuple of str), `verdict`, `cwd`, `source`. `record_dispatch` gains keyword args `effort`, `cwd`, `source`. `record_return` makes `seconds` and `subscription_calls` optional (default `None`, written as null; the SQLite `usage` row stores null) and gains keyword args `run_id`, `effort`, `input_tokens`, `output_tokens`, `cache_read`, `cache_write`, `files_created`, `verdict`. Both functions gain `store: str | None = None`; when given it overrides `WORKERBEES_STORE` for that call (same three values, same `ValueError` on a bad value). Existing positional and keyword calls keep working. `record_return` writes `run_id` = the argument, else the `run_id` of the node's dispatch row found by `load(workspace)`, else `None`. `verdict` must be `pass`, `fail`, or `None` (unknown); token counts must be non-negative integers or `None`; any other value makes the call return `False` and write nothing. `None` is written as JSON `null` and means unknown; zero is never substituted. `load` reads and merges the new fields (later non-null wins); `to_json` and `from_json` round-trip them. SQLite: `_dual_write_return` adds `input_tokens` and `output_tokens` to the existing `usage` row. Effort, cache tokens, files, verdict, cwd, and source are JSONL-only in this batch, because the SQLite schema has no columns for them and `schema.init` rejects a changed table set (evidence above). Adding them to SQLite needs a schema migration (`SCHEMA-3NF.md`, `SCHEMA_VERSION`), recorded as a follow-up, not done here.
- **DD2 usage join** (FR-003): new `agents_inc/usage_join.py`, `usage_for(workspace, node_id, *, db_path=None) -> dict | None`. It reads the node's rows from `<workspace>/.workerbees/ledger.jsonl` (a merged `Node` keeps only the latest timestamp): the window starts at the `dispatched` row's timestamp and ends at the latest later row's timestamp; provider and model come from the dispatch row. Timestamps from both stores are parsed to timezone-aware datetimes before comparison. Default path `~/.codex-bridge/usage.db`; when the file does not exist return `None` without creating it. Connect normally and run SELECT statements only (a read-only URI fails on a WAL database without `-shm`; machine note). Match rule: `usage.backend == node.provider`, model equal to `node.model` or ending in `-<node.model>` (Codex nicknames), `ts` between the node's dispatch and return timestamps. Return `None` (unknown) when: the node has no dispatch row or no later row, the dispatch row has `source` `host-hook` (the hook runs at `PostToolUse`, so its timestamp is the hook time, which for a foreground call is the completion time; analyze B3), the provider is `claude` (Claude usage rows are per session turn, not per dispatch, so a time window would count the parent's own turns), no row matches, or another ledger node with the same provider and model overlaps the window (ambiguous). Otherwise return the sums `{input_tokens, output_tokens, cache_read, cache_write, rows, match: "time-window"}`. Read errors return `None`. The join is approximate by design; `match` says so.
- **DD3 host hook rows** (FR-004a): new `agents_inc/host_ledger.py`. `host_workspace(state) = state / "host-ledger"`, so rows land at `<state>/host-ledger/.workerbees/ledger.jsonl` and `ledger.load` and `ledger.lint` read them unchanged. `dispatch_row(payload) -> dict | None`: accepts `tool_name` `Agent` or `Task` (provider `claude`, model = `tool_input.model` or `unknown`, task = `tool_input.description`) and any `tool_name` ending in `__DelegateAgent` (provider `codex`, model = `tool_input.model` or `luna`, task = first line of `tool_input.prompt`, at most 80 characters); anything else, a non-dict payload, a non-dict `tool_input`, or a missing `tool_use_id` returns `None` (and `record_hook_dispatch` returns `False`). Row fields: the 13 Node fields (`id` = `tool_use_id`, `run_id` = `session_id` or `unknown`, `tier` from `models.json` by exact id, or for a Codex nickname the codex-provider id ending in `-<nickname>`, else `unknown`; `parent_id` and `edge_type` null; `status` `dispatched`; `seconds`, `subscription_calls`, `gate_reason` null; `timestamp` now) plus `cwd` (payload `cwd`), `source` `host-hook`, and the DD1 token fields as null (unknown, never zero). `record_hook_dispatch(state, payload) -> bool` appends one JSON line (directory created as needed), never raises, never writes under `payload.cwd`, and never creates a SQLite file (host rows are JSONL only; analyze B6). The row status stays `dispatched` because it opens the node; for a foreground call the hook fires at completion, which DD2 handles. An executive-tier hook row has no gate reason, so `ledger.lint` flags it by design (analyze B5). Executive change (T009): `hook.agent_done` calls `record_hook_dispatch(paths.state, payload)` for every payload, first, before the existing `run_in_background` early return (analyze B17), and keeps the in-flight release for `Agent`/`Task` only; `host_wiring.add_hooks` adds a second `PostToolUse` entry, matcher `mcp__.*__DelegateAgent`, command `agent-done`, timeout 5, Claude host only (separate matcher per FR-004).
- **DD4 ledger append** (FR-004b): `host_ledger.cli(argv, state) -> int`, subcommand `append` with `--node-id` (required), `--verdict pass|fail`, `--status` (default `verified` for pass, `red` for fail), `--run-id`, `--seconds`, `--subscription-calls`, `--effort`, `--input-tokens`, `--output-tokens`, `--cache-read`, `--cache-write`, `--file-created` (repeatable), `--workspace` (default `host_workspace(state)`). Missing `--verdict` prints `agents-inc ledger append: --verdict pass|fail is required; a delegate self-report is not a verdict` to stderr and exits 2. When no `--run-id` is given and the workspace has no dispatch row for the node, it prints a message naming the node and exits 2 (SC-001: no return row without a run id). On success it calls `ledger.record_return(..., store="jsonl")` and exits 0, or exits 1 when that returns `False`. Subcommand `pending [--workspace]` prints one tab-separated line per node whose merged status is `dispatched`: `id`, `model`, `task`, `timestamp`, oldest first, and exits 0 (analyze B4: a foreground caller does not see its `tool_use_id`; a background-agent completion notice shows it as `<tool-use-id>`). Executive change (T009): `cli.py` adds a `ledger` subparser taking the remaining argv and returns `host_ledger.cli(rest, paths.state)` before the receipt check, like `hook`.
- **DD5 header and slots** (FR-005, FR-009 #4 part, FR-010): `skills/workerbee/header.md` holds the fixed elements 1, 4, 5, 6, 7 (scope boilerplate without the per-task allowlist), 12, 13, 14, and the persistence inheritance line (DD8), exact text in Appendix B. `skills/workerbee/slots.md` lists the per-task slots as `{{NAME}}` placeholders: ROLE, TASK, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE, FAILURE_GATE, PRE_EXISTING_CHANGES, ALLOWLIST, CLASSIFICATION, EFFORT, SECOND_OPINION, PLAN_CONTRACT, and the optional STYLE slot, whose experimental value is the #4 revised template (Appendix C). New `skills/workerbee/scripts/render_dispatch.py --slots <json> [--contract-ref <path>] [--header <path>] [--template <path>]`: fills the template; a required slot missing or empty exits 2 naming it; STYLE may be empty; output = filled slots, then either the header text or the line `CONTRACT: <path>` followed by the training opt-out line verbatim. No cache-savings claim is made anywhere (FR-010).
- **DD6 CONTRACT lint** (FR-006, SC-004): `check_dispatch_prompt.py` gains `--transport file|bare` (default `file`). A line starting `CONTRACT:` (any case) names a contract file. With `--transport bare`, any such line makes the result `NON-COMPLIANT contract-reference-on-bare-transport` with a one-line reason, exit 1. With `file`, the path is expanded (`~`) and resolved against the current directory, then the prompt file's directory; an unreadable path gives `NON-COMPLIANT contract-unreadable`, exit 1; otherwise the contract text is appended to the prompt text before `check`. Element 5 (training opt-out) must still appear in the prompt file itself; if only the contract has it, element 5 is reported missing. Existing calls without `CONTRACT:` behave exactly as before.
- **DD7 tier tables** (FR-007, SC-003): new `skills/workerbee/scripts/gen_tier_tables.py [--check | --write] [--skill PATH] [--models PATH] [--routing PATH]`. Rung order `executive, orchestrator, workhorse, grunt`. Render one Markdown table: columns `rung | provider | default (routing.json) | all ids (models.json)`, one row per (rung, provider) present in either file, providers sorted, ids sorted, each id in backticks. Fail closed, exit 1 naming the id, when a `models.json` tier or a `routing.json` `tiers` key is outside the rung set, when a routing default id is absent from `models.json`, or when a routing default's `models.json` tier differs from its routing rung. The block sits between `<!-- BEGIN GENERATED tier-table (skills/workerbee/scripts/gen_tier_tables.py --write); do not edit by hand -->` and `<!-- END GENERATED tier-table -->`. `--write` replaces the block body; `--check` exits 1 and names the differing ids when the block is stale or missing, else prints `tier-table: current` and exits 0. Hand tables keep their prose columns; their tier cells are relabelled to rung names (ladder: ultra -> executive, flagship -> orchestrator, flash -> grunt, bottom rung -> grunt; roster: same, `workhorse-ish` -> grunt, `—` kept). Mistral `codestral-latest` and `mistral-large-latest` keep `workhorse` (not in config, so no disagreement is measurable); their conflict with AGENTS.md "Optional providers may handle only allowed Grunt work" is reported as LESSON-CANDIDATE, not changed here.
- **DD8 persistence rule** (FR-008): new `### Step 3c: Keep a delegate until its context ceiling` before `### Step 4`, text in Appendix D (D2). One paragraph after the Step 11 tick-list (D3) names `header.md`, `slots.md`, `render_dispatch.py`, the `CONTRACT:` rule, and the required inheritance line. The header (Appendix B) carries the inheritance line. No tracker, no lint check (clarify answer).
- **DD9 records** (FR-009): `specs/016-dispatch-contract-records/research.md` (Supervisor) records #4 (status opt-in, measurements, what remains unvalidated, where the STYLE slot lives) and #27 (verdict, usage counts, DomI follow-ups as NEEDS-OPERATOR). No DomI write.
- **DD10 ownership**: DD1 -> sonnet (design judgment across the dual-write paths of a 728-line module; escalation trigger (c)). DD3/DD4 library code -> the same sonnet delegate after DD1, kept per Step 3c (analyze B9: payload parsing, tier lookup, and a 14-flag CLI exceed the Grunt narrow-diff rule). DD2, DD5 renderer, DD6, DD7 generator -> haiku (narrow, test-gated). DD3/DD4 install edits -> Executive task spec (operator ruling). DD5 text files, DD7/DD8 SKILL.md text, DD9 -> Supervisor (exact wording is the deliverable; delegating would be a verbatim copy). The Supervisor writes every acceptance test first and shows it failing on unchanged code.

## Constitution Check

Constitution at `~/Projects/DomI/specs/consumers/agents_Inc/memory/constitution.md` is unratified, so violations are WARN.

| Principle | Status | Note |
|---|---|---|
| P0 cross-reference, never duplicate | PASS | Ledger extended, not duplicated; tier table generated from config; header referenced by `CONTRACT:`. |
| P1 repo-scoped writes | PASS | Host ledger lives in the user-scope state dir at run time only; tests use temp dirs and a fake home. |
| P2 labor ladder | PASS | sonnet for the ledger, haiku for narrow modules, Executive for install code. |
| P4 deterministic policy over prompt | PASS | Verdict fail-closed in code; drift and contract checks are scripts. Persistence stays prose by operator decision. |
| P5 hard $0 per task | PASS | No model calls. |
| P7 rung names | PASS | Tables move to the D27/D36 rung names. |

Post-design re-check: PASS.

## Project Structure

```text
specs/016-dispatch-contract-records/
├── spec.md, plan.md, tasks.md, research.md, analyze.md
└── checklists/ (requirements.md, records-and-contract.md)
agents_inc/ledger.py                         # DD1 (sonnet)
agents_inc/usage_join.py                     # new, DD2 (haiku)
agents_inc/host_ledger.py                    # new, DD3/DD4 (sonnet)
agents_inc/install/{hook,host_wiring,cli}.py # DD3/DD4 wiring (Executive)
skills/workerbee/header.md                   # new, DD5 (Supervisor)
skills/workerbee/slots.md                    # new, DD5 (Supervisor)
skills/workerbee/scripts/render_dispatch.py  # new, DD5 (haiku)
skills/workerbee/scripts/check_dispatch_prompt.py  # DD6 (haiku)
skills/workerbee/scripts/gen_tier_tables.py  # new, DD7 (haiku)
skills/workerbee/SKILL.md                    # DD7/DD8 (Supervisor; LESSON-CANDIDATE)
tests/test_ledger_fields.py                  # new, Supervisor
tests/test_usage_join.py                     # new, Supervisor
tests/test_host_ledger.py                    # new, Supervisor
tests/test_dispatch_header.py                # new, Supervisor
tests/test_tier_table_drift.py               # new, Supervisor
```

## Agent context update

Skipped: no `CLAUDE.md` (retired 2026-10-01).

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| Host ledger in the state dir instead of the workspace ledger | Spec FR-004 forbids `<workspace>/.workerbees/` for hook rows | Writing into each project's ledger from a host hook touches repos the operator did not choose |
| Fields JSONL-only for SQLite | Schema change breaks existing databases (`schema.init`) | A migration is a separate, governed change |

## Appendix B: `skills/workerbee/header.md` (exact text)

Written by the Supervisor in T010; the file itself is the source of truth once written. Content summary: title, how to use (slots first, then this header or `CONTRACT: <path>` plus the opt-out line), and the fixed lines CAVEMAN, GRILL, the training opt-out line verbatim, EVIDENCE, SCOPE BOILERPLATE, REPORT SHAPE, EDIT HYGIENE, LESSON-CANDIDATE, PERSISTENCE (inheritance line, DD8). Bare-API delegates (gask/mask/oask) always get the text pasted.

## Appendix C: STYLE slot (experimental, #4)

The optional STYLE slot value, verbatim from #4 "Revised template" (not re-tested; opt-in; extractive and summarization dispatches only):

```text
HARD CONSTRAINT: Default to fragments, labels, arrows, abbreviations — NOT normal prose.
A full grammatical sentence is allowed ONLY where a fragment would lose real precision
(negation scope, conditional/causal clause, operator precedence). Outside those cases,
one complete sentence = you failed the task, rewrite it. When you do use a full sentence,
it should be rare and load-bearing, not a lapse back into prose by default.
```

## Appendix D: SKILL.md text

D1 (DD7): after the ladder table, insert the rung-name note and the generated block markers:

```markdown
Rung names follow D27/D36: executive, orchestrator, workhorse, grunt. Older
prose in this skill says ultra, flagship, and flash for executive,
orchestrator, and grunt. The generated table below is the source of truth for
which model ids sit on each rung; edit `agents_inc/models.json` or
`agents_inc/routing.json`, then run
`python3 skills/workerbee/scripts/gen_tier_tables.py --write`.

<!-- BEGIN GENERATED tier-table (skills/workerbee/scripts/gen_tier_tables.py --write); do not edit by hand -->
<!-- END GENERATED tier-table -->
```

D2 (DD8): before `### Step 4`:

```markdown
### Step 3c: Keep a delegate until its context ceiling

Continue a live or finished delegate that already holds the needed context
instead of spawning a new one: Claude `SendMessage` to the agent id; Codex
`ask.sh` with its thread id. Retire it at its context ceiling: 200k tokens by
default, 300k for opus. Ask it for a handoff note first, then seed the
successor with that note. Measured (#28, 1,399 local subagents): 2.5% ended
at or above 200k and 0.2% at or above 300k; a respawn re-pays about 42k
tokens of context (median). The rule that matters is "continue, do not
respawn"; the ceiling rarely binds.

Exceptions, use a fresh delegate: the premise changed (Step 9 wins); an
adversarial review needs a reviewer without the author's context; the
backend cannot resume. Resume support: Codex yes (`ask.sh` thread id);
Mistral partial (`mask.sh` keeps one global conversation, so parallel
delegates share it; treat as no resume); Gemini and OpenRouter no. When a
transport reports no token count, the supervisor decides and states it.

Every nested dispatch prompt carries the inheritance line from
`skills/workerbee/header.md` (PERSISTENCE), so a delegate that spawns its own
delegates follows the same rule. Enforcement is this text and that line; there
is no token tracker and no lint check.
```

D3 (DD5, DD6): after the paragraph ending "non-compliant, do not send it." in Step 11:

```markdown
**Header and slots (spec 016).** Do not reword the fixed elements per
dispatch. Fill the slots in `skills/workerbee/slots.md`, then append
`skills/workerbee/header.md`, or render both with
`python3 skills/workerbee/scripts/render_dispatch.py --slots <json>`. A
delegate that can read files may get the line `CONTRACT: <path to header.md>`
instead of the pasted header; the training opt-out line stays pasted
verbatim either way. Bare-API delegates (gask/mask/oask) always get the text
pasted; lint them with `--transport bare`, which rejects a `CONTRACT:` line.
Caching the header saves tokens only if measured (`cache_read` over about 10
clustered runs); no saving is claimed until then.
```
