<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-14 skill=speckit-plan repo=agents-inc session=91aeecb8 -->
# Data model: Unified delegate pane

## Delegate (mission.ts, unchanged shape)
id, nickname, rung, state (running|review|done|failed|lost|paused), category/station, parent, startedAt, endedAt?, alertAt?. Source: native subagent, dispatch run, free run.

## TreeRow (tree.ts, new)
- key: `agent:<agentId>` | `run:<dirName>` | `job:<n>`
- kind: agent | run | free | job
- parentKey (main session root `main`), depth
- label, state, model, effort?
- controls: open (agent view / run sub-pane), cancel (dispatch run running), stop (live agent), message (agent live | run resumable); free: none
- Rule: a job row is removed once a row with its agentId or run dir exists.
- Rule: finished runs older than session start hidden; running runs always shown; finished capped KEEP_RUNS=8.

## PollResult (poll.ts, new)
{ agents: Listed[], treeRows: TreeRow[], delegates: Delegate[], finalRuns, lostRuns, mapNote, note }. One per tick; both sections read it from `$.state` view.

## PaneView ($.state, extended)
Existing fields minus `types`, `agents` list rendering; plus `treeRows`, `controlsOpen: boolean`, `selected?: key`, form fields.

## Session record ($.store `session:<id>`, unchanged)
{ sessionStart, acked, alertAt, savedAt }; STORE_KEEP sessions. FR-010.

## Pane mod (installer)
(name, plugin, marketplace). Active: delegate-pane. Retired: agents-manager@agents-manager-local / agents-manager-local; luna-pane@luna-pane-local / luna-pane-local.
State transitions per machine: {old mods present} -> install -> {delegate-pane 0.6.0 only} -> install -> unchanged.
