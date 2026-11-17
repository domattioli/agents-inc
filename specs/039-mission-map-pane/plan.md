<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-12 skill=speckit-plan repo=agents-inc session=f8c024a9-ee62-4516-9889-edd03b1d02b1 -->
# Implementation Plan: Mission map view in the delegate pane

**Branch**: none (no branch created) | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

## Summary

Extend `mods/delegate-pane` so that, below its two existing lists, it draws a mission map: a vertical spine (CoS, Lead, primary Worker), one station per task category, and one marker per working agent (native agent or dispatch worker) labelled nickname · rung · lifecycle state. Stations light while work runs, carry an error count, and offer a pressable acknowledge control. Pure, tested functions do the mapping; the render hook only lays out.

## Technical Context

- **Language**: TypeScript/TSX hooks module for the Claude Code mod engine (`claude-code` types), as in `mods/delegate-pane/hooks/register.tsx`.
- **Dependencies**: none new. Engine nouns used: `$.agent.list`, `$.process.spawn` (existing), `$.fs.list`, `$.fs.read` (new), `$.clock.every`, `atom`/`read`/`update`, `Button onPress`.
- **Testing**: `claude plugin test mods/delegate-pane` runs `hooks/pane.test.tsx` (convention: `mods/agents-inc/README.md:66`). Repo Python suite `python3 -m unittest discover -s tests -p 'test_*.py'` covers `tests/test_mod_install.py`, which names delegate-pane.
- **Performance**: poll stays 1 s; dispatch read is bounded: one directory list plus only run files of this session that are not yet final (R1 bound).
- **Constraints**: terminal Box/Text layout only; no network, no model call (FR-010).

## Constitution Check

Source: `.specify/memory/constitution.md` (seeded from DomI `specs/consumers/agents-inc/memory/constitution.md`).

- P1 repo-scoped writes (constitution.md:22): changes stay in `mods/delegate-pane/**` and this spec dir. PASS.
- P2 labor ladder (:26): code is written by the workhorse rung; the route is pending an operator decision (tasks T000b). PASS, conditional.
- P3 no self-graded gates (:30): the test command plus fable's acceptance. PASS.
- P4 deterministic policy (:34): category rules are a fixed table, no model. PASS.
- P5 $0 per task (:38): no paid API. PASS.
- P7 nickname discipline (:46): markers show nicknames from agents-inc data. PASS.
- P9 surgical edits (:54): register.tsx extended; existing list code kept. PASS.

## Phase 0: Research (decisions)

### R1. Data source for dispatch runs (redone after analyze C1)

Where `agents-inc dispatch` really writes:
- Run directory: `default_parent(cwd)` returns `<cwd>/.scratch/agents-inc-runs` when git ignores `<cwd>/.scratch/`, else `$CLAUDE_SCRATCHPAD`, `$TMPDIR` or `/tmp` + `/agents-inc-runs` `[verified: agents_inc/install/dispatch.py:155-166]`. A real run left `<cwd>/.scratch/agents-inc-runs/20261112T215234Z-sonnet-6d7fc2/` with `run.json, events.jsonl, slots.json, usage.json, stdout.md, prompt.md, ...` `[verified: ls of that dir]`.
- Ledger node: `_record_ledger_node` calls `host_ledger.record_dispatch_run(_paths().state, spec, TASK)` `[verified: dispatch.py:1348-1357]`; `_paths()` = `InstallPaths.for_home(Path.home())` `[verified: agents_inc/install/cli.py:16]`, state = `~/.local/state/agents-inc` `[verified: agents_inc/install/paths.py:39]`; rows append to `<state>/host-ledger/.workerbees/ledger.jsonl` `[verified: host_ledger.py:26-28, 207-210]`. `ledger.py` and `gateway.py:275` are a different path, not used by dispatch.

Options:

(a) Host ledger file `~/.local/state/agents-inc/host-ledger/.workerbees/ledger.jsonl`.
- Fields of a dispatch row: `id = run_id, model, tier (rung name from models.json, else "unknown"), task (first line of slots TASK, capped), provider, edge_type None, status "dispatched", cwd, source "dispatch", timestamp` `[verified: host_ledger.py:114-147, 41-52]`. Return row: `status = outcome, verdict, gate_reason = reason` `[verified: host_ledger.py:158-171]`.
- Tie to session: only `cwd` and `timestamp`; no session id.
- Reach: `$.fs.read` takes an absolute path; no manifest file-read permission exists; an `fs.*` hook of another plugin may refuse it `[verified: claude-code.d.ts fs doc, about line 3424]`.
- Fatal bound: `$.fs.read` rejects files over 4 MiB `[verified: same doc]`; the file is already 2,153,523 bytes, 3,401 rows, all workspaces mixed `[verified: wc/ls 2026-11-12]`. It will pass the cap; no range read exists. Rejected.

(b) Per-run files under `<cwd>/.scratch/agents-inc-runs/<run_id>/`. **Chosen.**
- `run.json` fields: `run_id, model, kind, cwd, effort, outcome, reason, session_id (the child's own session, not the caller's), slots_path, slots_sha256, delegate_start, ...` `[verified: keys of the real run.json; dispatch.py:1970 sets session_id from the child result]`.
- `slots.json` keys: `MODEL, ROLE, SUPERVISOR, EXECUTIVE, TASK, CONSTRAINTS, ..., CLASSIFICATION, EFFORT` `[verified: real slots.json]`; optional `TASK_KIND` read at `dispatch.py:1820` `[verified]`.
- `events.jsonl` line 1 is `run.start` with `run_id, model, kind` `[verified: real file]`.
- Running state: run dir present with no `outcome` in run.json (or no run.json yet) `[assumed]`: T001 checks at which point run.json is first written (`dispatch.py:1247, 1321, 1335`).
- Tie to session: run dir under session cwd and run id prefix `YYYYMMDDTHHMMSSZ` at or after session start (the pane records start at `session.start` into `$.state`). Run id prefix format `[verified: real id 20261112T215234Z-sonnet-6d7fc2]`; that the prefix is UTC start time is `[assumed]`, T001 checks.
- Reach: relative path under cwd, `$.fs.list` and `$.fs.read`; no permission to declare.
- Gap: when `.scratch/` is not git-ignored, runs land in `$CLAUDE_SCRATCHPAD`/`$TMPDIR`, which the mod cannot see; the pane shows a one-line note "dispatch runs not visible: .scratch not ignored" when `<cwd>/.scratch/agents-inc-runs` is missing.
- Bound (M3): each poll lists the run root once, skips dirs older than session start by name, and re-reads `run.json` only for runs not yet final and not lost-and-unchanged; final runs are cached in `$.state`. Cost per poll = 1 root list + 1 list per non-final run + files of running runs. Test with 500 fixture run dirs.

(c) `agents-inc ledger pending`: prints tab-separated `id, model, task, timestamp` for rows still `dispatched`, all workspaces, no JSON, no outcome `[verified: host_ledger.py:276-296]`. Shows no finished or failed run. Rejected.

### R1 findings (T002, T003, 2026-11-12)

- Run id prefix is `time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())` at id creation `[verified: dispatch.py:202]`, so it is UTC start time.
- `outcome` is set at finalize `[verified: dispatch.py:1311, 1321]`; during a run the dir may hold `events.jsonl` (`run.start` first) and no run.json. Running = `run.start` seen and no run.json `outcome`; model and kind come from `run.start` when run.json is absent.
- Pane props carry `bodyColumns` and `placement` `[verified: plugin-authoring claude-code.d.ts:11316-11324]`; `layoutFor(bodyColumns)` picks grid, stacked or line.

### R2. Task categories (Executive provisional ruling `[assumed]`; redone after M2)

Stations: Review, Build, Write, Scout, Plan, Other.

Signal order; first rule that gives a category wins. Re-ruled 2026-11-12 (operator): the task verb comes before ROLE, because real ROLE values start with the rung word ("Workhorse (sonnet) ...") and ROLE first put every sonnet dispatch in Build.
1. Structured, subagent: `subagentType` `Explore` → Scout; `Plan` → Plan; `claude-code-guide` → Scout. `[assumed]` that `$.agent.list` returns the type; current code reads `type` `[verified: register.tsx:22,27]`.
2. Structured, dispatch: slots `TASK_KIND` if present (map `review|verify`→Review, `code|fix`→Build, `docs|write`→Write, `scout|read`→Scout, `plan|design`→Plan). TASK_KIND values `[assumed]`. Kept before the text: it is a stated kind, not a rung.
3. Leading clause only: text before the first `.`, `:`, `;` or newline, then first verb from a fixed list: `review|verify|audit|grade` → Review; `implement|fix|refactor|patch|code|build` → Build; `write|draft|document|file` (an issue or PR) → Write; `read|find|search|list|summarize|scout|triage|explore|locate|batch` → Scout; `plan|design|scope|spec` → Plan.
   A role prefix ("Orchestrator:", "Dispatch sonnet to") is stripped first.
4. Dispatch only, the text matched nothing: slots `ROLE` leading word (`reviewer`→Review, `workhorse`→Build, `scout|grunt`→Scout, `orchestrator`→Plan). Real ROLE: "Workhorse (sonnet), dispatched by Orchestrator (opus)." `[verified: fixture slots.json shape]`.
5. Read-only grunt rung with no match → Scout.
6. Else Other.

Added rows (ROLE "Workhorse (sonnet), dispatched by ..."): "review PR 212" → Review; "draft README" → Write; "check-in card" → Build (ROLE fallback).

Fixture table (T005 must hold at least these; expected values are the provisional ruling):

| Description | Expected |
|---|---|
| Orchestrator: batch open issues | Scout |
| Orchestrator: mod pane spec pipeline | Plan |
| Dispatch sonnet to file the agents-inc issue | Write |
| read the tests and list failures | Scout |
| fix the failing test in ledger.py | Build |
| review PR 212 for correctness | Review |
| check-in status card | Other |
| summarize the logs | Scout |
| implement mission.ts per plan | Build |
| draft the README section | Write |
| design the station layout | Plan |
| verify gates pass, then report | Review |
| (subagentType Explore) "find the pane source" | Scout |
| (subagentType Plan) "anything" | Plan |

### R3. Rung source (M4)

- Subagent of type `agents-inc:<nick>`: rung from status JSON if it carries a tier; current offeredTypes reads only `nickname, offered` `[verified: register.tsx:40-50]`; a `tier` field there is not verified.
- Dispatch run: host ledger computes rung from `models.json` `tier` `[verified: host_ledger.py:41-52]`; run.json carries `model` and `kind` only, so the pane needs the same lookup.
- Fallback table lives in `mods/delegate-pane/hooks/rungs.ts`: every `agents_inc/models.json` id and nickname, plus the `MODEL_RUNG` aliases (`skills/workerbee/scripts/dispatch_rungs.py`) that are neither. `tests/test_delegate_pane_rungs.py` fails when an id or nickname is missing, an entry differs from models.json or from MODEL_RUNG, an entry sits outside the markers, or a line between the markers is in a form the parser skips. Unknown → `?`.
- Run dir fallback: the model is everything between the `YYYYMMDDTHHMMSSZ-` stamp and the last `-` part (`...-gpt-6-luna-abc123` → `gpt-6-luna`). The dir spells the model with `/` and `:` turned to `_` (`dispatch.py:201`); `rungOf` matches the table in that spelling too.
- Non-agents-inc subagent types (Explore, general-purpose): rung `?` unless the model is known `[assumed]`.

### R4. Lifecycle mapping (M1)

- Subagent: engine `AgentStatus` is `pending|running|waiting|idle|completed|failed|killed` `[verified: claude-code.d.ts AgentStatus]`. `running|pending` → running; `waiting|idle` → paused; `completed|finished|done` → done; `failed|error|killed` → failed; any other status → running (the engine still lists the agent, so it has not ended).
- Dispatch: no `outcome` → running; `unverified` → review (gates not proven); `green` → done; `red` with reason `quota-paused` → paused; `red`, `cancelled`, `blocked`, `launch-failed`, `refused-*` → failed. Outcome values `[verified: dispatch.py:1164, 1252, 1332, 1521, 1576, 1686-1708]`.
- Dispatch `dry-run` outcome: not drawn (nothing launched). Any other unknown outcome → failed (fail-safe).
- Lost (2026-11-12, FR-012): a dispatch run still running whose last event is `LOST_MS` (5 min, `mission.ts`) old or more → lost. Last event = the newest `mtimeMs` among the run dir's files, from one `$.fs.list(<run dir>)` per non-final run per poll (`FsEntry.mtimeMs`: "the listing reads a regular file's size and time in its one call" `[verified: claude-code.d.ts FsEntry]`). A dir with no file: the run id's start time. A failed list: unknown, never lost. A lost run is cached in `lostRuns` and its files are not read again until the newest mtime moves past the cached one; the list each poll still notices that. A failed run's alert time is its newest mtime too, so it is stable across reloads and resumes.
- queued: subagent `pending` reports it; v1 never draws queued and shows `pending` as running (spec FR-005).

### R5. Click support

Pane trees accept `Button` with `onPress`; Enter under focus raises it, and a click raises it where the terminal reports clicks (fullscreen) `[verified: claude-code.d.ts:1091,1197]`. Acknowledge = one Button per station with errors. No slash command needed.

### R6. Layout and minimum size

- Raster map (terminal surface with a Raster element, blit not refused): `rasterColumns(bodyColumns)` is 0 below 34 (`RASTER_MIN_COLUMNS`), else the body width capped at 56 (`RASTER_MAX_COLUMNS`); 16 rows (`RASTER_ROWS`). One spine in the column at 30% of the width (at least 14): CoS row 0, Lead row 5, primary Worker row 11. Six stations, five cells off the spine: left Plan row 2, Scout row 5, Write row 8; right Other row 2, Review row 8, Build row 14. Each station joins the Lead by a thin spoke along the spine and across with one bend; Scout sits on the Lead row and is straight. Geometry is fixed whatever the data, so a hub that comes or goes moves nothing. Hub labels sit right of the node: `CoS · <model>` (model dropped when no room), `Lead · <name>` or hollow `CoS as Lead`, `Worker · <name>`. A hub's delegate is not named again under its station. A station name line lists working delegates (else the newest) that fit, with an `xN` badge; a station with an unacknowledged failure shows one red `✗` mark and the count.
- Text map (every surface), chosen by `layoutFor`: grid at 70 columns or more (3 × 2 station boxes, each 22 wide, under the Raster), stacked from 30 to 69 (one station per row, markers inline), line below 30 (one line per station "Name n● m✗", counts only; spec FR-009 states the lost markers as a known limit). Above the stations: a centre text line `◉ main session · chief of staff · N working[ · model]` (role dropped first when it does not fit) and one or two dim lines `CoS: main session (<model>) · Lead: <name> (<rung>) · Worker: <name>`, with `Lead: none, the CoS leads` and `Worker: none running` when absent. Below 34 columns no Raster draws and the text map stands alone.
- Empty stations collapse to a one-line title in both text layouts.
- Status line and feed (all surfaces, plain Text under the map): one bold status line, then feed rows, newest start first, capped at a third of the pane body rows, between 3 and 10. A row is bullet, name (14), a dim rung column (executive, orchestrator, workhorse or grunt; blank when unknown), task with ellipsis, right-aligned state or duration (8). The rung column drops on a narrow pane, before the task is cut below 16 columns.

## Phase 1: Design

### Data model

- `Delegate { id; source: 'subagent' | 'dispatch'; nickname; rung; task; category; state }`.
- `Station { category; delegates: Delegate[]; lit: boolean; unacked: string[] }`.
- `MissionView extends PaneView { delegates: Delegate[]; acked: Record<category, string[]>; sessionStart: string; finalRuns: Record<runId, Delegate> }`; atom shape tag `view-3` → `view-4`.
- Error count = ack keys `<id>@<alertAt>` of failed or lost delegates on the station not in `acked[category]` (H2, FR-008). `alertAt`: dispatch, the run's newest file mtime at failure or loss; subagent, the poll time the pane first saw it failed (kept in `alertAt` by id while it stays failed, cleared when it leaves failed). Pressing ack adds the station's current keys and drops older keys of the same ids; no count trim. A delegate leaving the window drops nothing a later failure needs.
- Store (FR-013): `$.store` key `session:<$.session.id()>` = `{ sessionStart, acked, alertAt, savedAt }`, written at session start, on each ack press and when `alertAt` changes; read at `session.start` when `$.state` has no `sessionStart`. `$.store` is the plugin's own JSON file under the user's config dir, shared across sessions and projects, 4 MiB cap `[verified: claude-code.d.ts store]`; the 20 newest `session:` records are kept. `$.session.id()` is "the transcript file's name" `[verified]`; that `claude --resume` keeps that id is `[assumed]`.
- Atom shape `view-4` → `view-5`: ack entries changed meaning; a `view-4` value reads as empty and the store record refills it.

### Contracts (pure functions in `hooks/mission.ts`, unit-tested)

- `categoryOf(d: { text; subagentType?; taskKind?; role?; rung? }): Category`
- `rungOf(model: string, nickname?: string): string` (uses `hooks/rungs.ts`)
- `lifecycleOf(source, outcomeOrStatus, reason?): State`
- `runFromFiles(runJson?: string, slotsJson?: string, dirName: string): Delegate`
- `sessionRuns(dirNames: string[], sessionStartIso: string): string[]`
- `stations(delegates, acked): Station[]`
- `layoutFor(columns: number): 'grid' | 'stacked' | 'line'`

### Quickstart

1. `claude plugin validate mods/delegate-pane`
2. `claude plugin test mods/delegate-pane`
3. `python3 -m unittest discover -s tests -p 'test_*.py'`
4. Live: `/delegate-pane`, start one subagent and one dispatch run; check markers, ack.

Agent context update: skipped (consumer repo).

## Risks

- Run root outside cwd when `.scratch/` is not git-ignored: dispatch runs invisible; note shown.
- Same-cwd second session started later shares dispatch runs (spec FR-003 limit).
- Supersedes spec 038 FR-020: operator confirmation open.
- Pane width comes from `props.bodyColumns` (fallback `viewport.columns`, then 80); a surface without a Raster element or a refused blit draws the text map only.

## Pass 3 (2026-11-12)

Operator reversed the v1 no-feed choice. Feed is plain Text under the map (cheaper and sturdier than Raster rows; works on desktop). Relation data: `AgentInfo.parentId` (real data); start-order fallback rejected. Times: poll-observed, never invented; unknown duration shows `—`. See spec FR-014..FR-018, tasks T026-T029.

Hierarchy and vertical passes (spec FR-022..FR-030, tasks T032, T033). No station-to-station arcs are permanent and there is no centre node.
- Lead: a delegate that a child on the map names as `parentId`; several: higher rung, then earliest start (unknown last), then list order. No Lead: the main session leads, hub drawn hollow `CoS as Lead`, no CoS link. Primary Worker: among the Lead's children (all delegates when no Lead), the workhorse-rung delegate in state running with the newest start, never the Lead; none: no Worker hub.
- Permanent lines: Lead spokes and, while a Lead exists, the CoS-Lead link. Every other line exists only while its pulse travels. Route of a delegate (`routeOf`): the Lead, on the CoS-Lead link; a child of the Lead, or any delegate when no Lead exists, on its Lead spoke; no parent while a Lead exists, a CoS-to-station edge; a child of a non-Lead delegate, a station-to-station curve; a parent missing from the map or the same station, nothing.
- Pulses: a dispatch pulse crosses its route in 0.6 s when a delegate with a known start is seen working, then a 0.4 s ripple lands; a result pulse returns along the same route to the starter in 0.6 s with a 0.4 s ripple, red when failed or lost, only for a delegate seen working before it ended. A running or review delegate on a Lead spoke sends a heartbeat pulse every 2.4 s, at most 3 per spoke. Nothing else repeats. Spokes are dim, brighter while a Lead-started delegate runs, red-tinted for an unacknowledged failure.
- Timer: one 80 ms `$.clock.every` runs only while the Raster shows and a heartbeat, a return pulse or a dispatch event lives; stopped on `ui.close`, when nothing moves, and on a refused blit (then the text map only).
