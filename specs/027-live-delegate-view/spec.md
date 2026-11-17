<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-specify repo=agents_Inc session=unknown -->
# Feature Specification: Live delegate view

**Feature Branch**: `027-live-delegate-view` (work lands on `development`; no branch created by this pipeline run)
**Created**: 2026-10-24
**Status**: Draft (clarifications answered 2026-10-24)
**Input**: Operator ask 2026-10-24: "In Claude Code I can click a subagent's window to watch its session. Give agents-inc delegates on any model (sol, astra, gemini, mistral, openrouter, and Claude rungs) the same clickable live view." Part A: `agents-inc dispatch` writes live provider events to `<run dir>/events.jsonl` while the run goes. Part B: a Claude Code mod registers a relay agent type whose one tool starts the dispatch, tails the events and appends readable rows to that subagent's transcript.

## Background (code facts)

- Claude delegates run `claude -p ... --output-format json` and the whole stdout is read at exit with `communicate` [verified agents_inc/install/dispatch.py:260-264, 709-712]. Nothing is visible until the run ends.
- Codex delegates outside a Lead run with `--json -o <file>` (`json_mode`) and the JSONL stdout is held in memory until exit [verified agents_inc/install/runtime.py:369-370, 487, 538-547; dispatch.py:752 passes `thread_out` for every non-Lead run]. Codex Lead runs have no `--json` [verified dispatch.py:752: `thread_out=None if lead_dir`].
- `agents-inc dispatch` accepts only Claude rungs and Codex aliases; any other model prints `dispatch: <model> not supported, use agent.sh` and exits 2 [verified dispatch.py:791-796, 1263-1266]. `FREE_SLUGS` is defined but unused in dispatch [verified dispatch.py:42].
- The run directory is `<--run-dir or default parent>/<run_id>`, created before launch [verified dispatch.py:1298-1304]. `stdout.md`, `stderr.txt` and `usage.json` are written after the delegate exits [verified dispatch.py:1428-1437].
- The mirror to the home repo copies only `run.json` and `prompt.md` [verified dispatch.py:1068-1097].
- In the mod API: `tool.call` input carries `agentId` inside a subagent [verified .scratch/027/claude-code.d.ts:13520-13529]; `$.process.spawn` streams a child and the child dies when the loop ends, `next.signal` aborts, or the module unloads [verified claude-code.d.ts:3605-3642]; a hook's 10 s budget stops while a `$` call is in flight [verified claude-code.d.ts:5261-5277]; `$.session.append({ message, agentId })` appends a user-meta row or a `system` notice the model never reads to a running subagent's transcript [verified .scratch/027/reference.md:181]; `$.agent.register` defines `<plugin>:<name>` with `tools` and `model` [verified claude-code.d.ts:461-536; reference.md:268]; a registered tool is listed as `mcp__<plugin>__<name>` and served by a `tool.call` hook [verified reference.md:258-268].
- CoS-verified (dispatcher, not re-checked here): a hook that answers `agent.spawn` without `next` starts no subagent; native subagent loops cannot run non-Claude models; no provider-swap hook exists. So a real Claude relay loop is needed [assumed from dispatch].

## Clarifications

### Session 2026-10-24 (non-interactive; operator not reachable)

- Q1: Gemini, Mistral and OpenRouter are not routable through `agents-inc dispatch` today (dispatch.py:1263-1266). Should v1 add them to dispatch? -> A (operator 2026-10-24, accepted recommendation): No. v1 covers Claude rungs and Codex aliases. The relay tool refuses a free model with a message that names `agent.sh`. Live events for free providers become a follow-up spec once dispatch routes them.
- Q2: Where does the mod live and how is it installed? -> A (operator 2026-10-24, overrides the recommendation): agents-inc installs it. Source at `mods/agents-inc/` in this repo; `agents-inc install` and `repair` copy it into the installed bundle, then run `claude plugin marketplace add <bundle>/mods/agents-inc` and `claude plugin install agents-inc@agents-inc-local` when `claude` is on PATH and the plugin is not installed (idempotent; `--no-mod` skips it). `agents-inc uninstall` runs `claude plugin uninstall agents-inc@agents-inc-local` and `claude plugin marketplace remove agents-inc-local`. A failed plugin step prints a warning and leaves the rest of install green. `agents-inc doctor` prints the warning code `MOD_NOT_INSTALLED` (repair fixes it) and still prints `READY`. Constitution P1 binds delegates, not the installer.
- Q3: Which row kind goes into the relay's transcript? -> A (operator 2026-10-24, accepted recommendation): `system` notices. The model never reads them, so delegate output cannot steer the relay, and the relay's context does not grow per event.
- Q4: Row rate limit? -> A (operator 2026-10-24, accepted recommendation): one notice per flush, a flush at most once per 1 s or when 20 rows wait; each row at most 240 characters; at most 600 notices per run, then one notice every 60 s saying how many rows were held back and where `events.jsonl` is.
- Q5: Codex Lead runs have no `--json` stream. Turn it on for them? -> A (operator 2026-10-24, accepted recommendation): No in v1. A Lead run writes only agents-inc lifecycle events (`run.start`, `run.end`). Its Workers' run dirs get full events through the same launch path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Watch a delegate live from Claude Code (Priority: P1)

The CoS session starts a delegate through the Agent tool with `subagent_type: "agents-inc:relay"`. The operator clicks the subagent's row and sees rows such as `[00:12] sol tool: rg -n "launch" agents_inc (exit 0)` appear while the delegate works. When the delegate ends, the Agent result is the delegate's report and the verdict line.

**Why this priority**: This is the operator ask. Without it a delegate is a black box until exit.

**Independent Test**: `claude plugin test mods/agents-inc` with a fake `process.spawn` that streams the Codex fixture; assert the relay's transcript gets notices in order and the tool result holds the fixture report and verdict line.

**Acceptance Scenarios**:

1. **Given** the mod is loaded and a relay subagent calls `mcp__agents-inc__run` with a Codex model, **When** the follower prints rows, **Then** each row reaches that subagent's transcript as a `system` notice, appended with the call's `agentId`, within 2 s of the event line being written.
2. **Given** the dispatch exits, **When** the tool returns, **Then** the tool result text is `stdout.md` followed by the verdict line, unchanged from what dispatch wrote.
3. **Given** a Claude rung (`haiku`, `sonnet`, `opus`, `fable`), **When** dispatched through the relay, **Then** rows show assistant text and tool calls as they happen.
4. **Given** a real relay run on the operator's host (task T043), **When** the Agent call returns, **Then** its result text equals the tool result text. The haiku echo is not machine-guaranteed, so the CoS still verifies from `<run dir>/stdout.md` (constitution P3); a mismatch is a T043 failure.

---

### User Story 2 - Live events on disk for every dispatch (Priority: P1)

Any `agents-inc dispatch` run, with or without the mod, writes `<run dir>/events.jsonl` while the delegate runs. `stdout.md`, `usage.json`, `run.json` fields and the verdict line stay as today.

**Why this priority**: Part B depends on it, and it lets an operator `tail -f` a run without Claude Code.

**Independent Test**: unittest with a fake `claude` and a fake `codex` executable that print fixture lines with pauses; assert `events.jsonl` grows before the fake exits, and that `stdout.md`/`usage.json` bytes equal the pre-change output for the same fixture.

**Acceptance Scenarios**:

1. **Given** a Codex non-Lead dispatch, **When** Codex prints a JSONL event, **Then** one envelope line holding it is in `events.jsonl` before the next event is read.
2. **Given** a Claude dispatch, **When** the delegate emits a stream-json message, **Then** one envelope line holding it is in `events.jsonl`, and the final `result` message still yields today's `stdout.md`, `session_id`, `is_error` and `usage.json`.
3. **Given** a turn timeout, **When** the deadline hits, **Then** rc is 124 with today's timeout mark and `events.jsonl` ends with a `run.end` event whose outcome is `timeout`.

---

### User Story 3 - Cancel stops the delegate (Priority: P2)

The operator stops the relay subagent. The dispatch and its delegate stop; no delegate keeps running in the background.

**Why this priority**: A watched run that cannot be stopped is worse than no view.

**Independent Test**: unittest sends SIGTERM to a dispatch running a fake delegate that sleeps; assert the delegate process group is gone within 5 s and `run.json` outcome is `cancelled`. Plugin test aborts the tool call and asserts both spawn loops ended and the best-effort `--cancel` run was made.

**Acceptance Scenarios**:

1. **Given** a running relay tool call, **When** the call's signal aborts, **Then** the mod ends both spawn loops and runs `agents-inc dispatch --cancel <run dir>` once.
2. **Given** dispatch gets SIGTERM, SIGHUP or SIGINT, **When** the handler runs, **Then** the delegate process group is killed and reaped, `events.jsonl` ends with `run.end` outcome `cancelled`, and dispatch prints `dispatch <run_id> <model> cancelled` and exits 130.

---

### User Story 4 - No secrets in rows (Priority: P2)

A delegate prints a token or key in a tool output. The row shows `[redacted]` in its place.

**Why this priority**: Rows land in a Claude Code transcript file on disk and on screen.

**Independent Test**: fixtures plant fake secrets in each provider fixture; the follower's unit test and the plugin test assert no planted value appears in any row.

**Acceptance Scenarios**:

1. **Given** an event whose text matches `report.SECRET_RE` [verified agents_inc/install/report.py:18-21], **When** rendered, **Then** the match is replaced by `[redacted]`.
2. **Given** the follower's environment holds a variable whose name contains `KEY`, `TOKEN`, `SECRET` or `PASSWORD` with a value of 8 or more characters, **When** that value appears in an event, **Then** it is replaced by `[redacted]`.

### Edge Cases

- Event line not JSON (provider noise): stored as `{"type":"raw","text":...}`, rendered as a `note` row.
- Event line over 64 KiB: stored cut to 64 KiB with `"cut": true`.
- `events.jsonl` reaches 64 MiB: one `events.truncated` event, then provider events are no longer written; stdout parsing goes on.
- The relay tool is called from the main loop (no `agentId`): the tool refuses with `call through Agent subagent_type agents-inc:relay`.
- A free model (`gemini`, `mistral`, `openrouter`) or any model dispatch refuses: the tool refuses before spawning, naming `agent.sh` (Q1).
- `slots` path outside the session working directory, or missing: refused before spawning.
- Dispatch refuses (lint, grants, dry run): no `events.jsonl` beyond `run.start`/`run.end`; the tool result is the refusal line.
- The run-dir line never arrives on stderr (old installed bundle): the mod shows one notice `live view unavailable: dispatch did not announce its run dir` and still returns the final result.
- An unknown event type: a row with the source and type only, no payload.
- Module hot-reload mid-run: the engine kills spawned children [verified claude-code.d.ts:3609-3611]; dispatch's signal handler stops the delegate.

## Requirements *(mandatory)*

### Functional Requirements

Part A, agents-inc dispatch:

- **FR-001**: Dispatch MUST append one JSON envelope per line to `<run dir>/events.jsonl` while the delegate runs: `{"v":1,"seq":<int from 1>,"ts":"<UTC ISO-8601>","source":"agents-inc"|"claude"|"codex","event":<object>}`. Each line is flushed before the next provider line is read.
- **FR-002**: Dispatch MUST write `run.start` (`run_id`, `model`, `kind`) before launch and `run.end` (`outcome` one of `done`, `red`, `timeout`, `cancelled`, `launch-failed`, `refused`, `dry-run`; `rc`) on every exit path after the run dir exists, both with `source: "agents-inc"`. `refused` covers every refusal printed after mkdir (dispatch.py:1335-1382 [verified]).
- **FR-003**: Claude delegates MUST run with `--output-format stream-json --verbose`; dispatch reads stdout line by line, writes each line as an event, and builds `stdout`, `session_id`, `is_error` and `usage` from the final `type: "result"` message exactly as today's code builds them from the `json` payload. With no `result` message, the whole stdout is parsed as one JSON payload (legacy form); failing that, the raw stdout is the `stdout` value (today's fallback, dispatch.py:728-734).
- **FR-004**: Codex delegates in `json_mode` MUST have each JSONL stdout line written as an event as it arrives; `parse_thread_id`, `_json_errors` and the `-o` last-message read keep their current inputs and results.
- **FR-005**: Turn timeout, group kill and rc 124 with the timeout mark MUST behave as today for both kinds.
- **FR-006**: `stdout.md`, `stderr.txt`, `usage.json`, the existing `run.json` fields and the verdict line printed to stdout MUST be unchanged for the same delegate output. The one new verdict line is the `cancelled` case (FR-011).
- **FR-007**: Dispatch MUST print `agents-inc dispatch: run <run_id> dir <absolute run dir>` to stderr once, right after creating the run dir.
- **FR-008**: `events.jsonl` MUST be created with mode 0600; under broker safe writes it MUST be created with `O_EXCL|O_NOFOLLOW` (D51 rule for artifact writes). It MUST NOT be mirrored to the home repo and MUST NOT be copied into `run.json`.
- **FR-009**: Event lines over 64 KiB are cut with `"cut": true`; at 64 MiB total, one `events.truncated` event is written and provider events stop.
- **FR-010**: Codex Lead runs write `run.start`/`run.end` only (Q5).
- **FR-011**: Dispatch MUST handle SIGTERM, SIGHUP and SIGINT: kill and reap the delegate process group, write `run.end` outcome `cancelled`, set `run.json` `outcome: "cancelled"`, print `dispatch <run_id> <model> cancelled`, exit 130.
- **FR-012**: Dispatch MUST record `delegate_pgid` in `run.json` at launch. `agents-inc dispatch --cancel <run dir>` MUST send SIGTERM to that group only when `run.json` has no final outcome and the group leader still runs the recorded `argv[0]`; else it prints `nothing to cancel` and exits 0.
- **FR-013**: `agents-inc events follow <run dir>` MUST print rendered rows (FR-014) for each event as `events.jsonl` grows, and exit 0 after `run.end`, or exit 3 when no `events.jsonl` appears within 30 s. `agents-inc events redact` MUST read stdin and print it with FR-015 redaction applied.

Rows:

- **FR-014**: A row is one line `[MM:SS] <model> <kind>: <summary>`, `MM:SS` the time since `run.start`, `kind` one of `start`, `think`, `say`, `tool`, `file`, `error`, `usage`, `note`, `end`. Whitespace collapses to single spaces; a row over 240 characters is cut to 239 plus `…`; `think` summaries are cut to 120 characters.
- **FR-015**: Every row MUST pass redaction before printing: `report.SECRET_RE` matches, then values of the follower's environment variables named with `KEY`, `TOKEN`, `SECRET` or `PASSWORD` (8+ characters), become `[redacted]`; the home directory becomes `~`.
- **FR-016**: The follower MUST batch rows: print a batch at most once per 1 s or when 20 rows wait, batches separated by an empty line.

Part B, Claude Code mod:

- **FR-017**: The mod source MUST live at `mods/agents-inc/` with plugin name `agents-inc`; `agents-inc install`/`repair` MUST copy it into the bundle (Q2).
- **FR-018**: At `session.start` the mod MUST register agent type `relay` (`agents-inc:relay`, `model: "haiku"`, `tools: ["mcp__agents-inc__run"]`, `maxTurns: 3`) whose prompt says: call the tool once with the task's fields, then answer with the tool's text exactly.
- **FR-019**: At `session.start` the mod MUST register tool `run` (`mcp__agents-inc__run`, `isDeferred: false`) with input `{ model: string, slots: string, effort?: string }`, served by a `tool.call` hook.
- **FR-020**: The hook MUST refuse (deny text, no spawn) when `agentId` is absent, the model is not a dispatch model, or `slots` does not resolve to an existing file inside the session working directory.
- **FR-021**: The hook MUST spawn `agents-inc dispatch --model <m> --slots <path> [--effort <e>] --cwd <session cwd>` by argv (no shell), read the run dir from FR-007's stderr line, spawn `agents-inc events follow <run dir>`, and append each follower batch as one `system` notice to the calling subagent with `$.session.append({ message, agentId })`.
- **FR-022**: The mod MUST cap notices at 600 per call, then append one notice per 60 s stating the held-back row count and the `events.jsonl` path.
- **FR-023**: The tool result MUST be `{ result: { text } }` with `text` = `<run dir>/stdout.md` content + blank line + the dispatch verdict line; when the dispatch printed no verdict line, `text` is dispatch's exit code and its last 20 stderr lines, passed through `agents-inc events redact` (FR-013).
- **FR-024**: When `next.signal` aborts, the hook MUST end both spawn loops and run `agents-inc dispatch --cancel <run dir>` once, best effort.
- **FR-025**: The mod MUST NOT answer `tool.check` for its own tool; the operator grants `mcp__agents-inc__run` with a permission allow rule (no self-approval, constitution P3).
- **FR-028**: `agents-inc install` and `repair` MUST install the mod through the `claude plugin` CLI (marketplace `agents-inc-local`, plugin `agents-inc@agents-inc-local`) when `claude` is on PATH and the plugin is absent, MUST skip it under `--no-mod`, and MUST NOT fail install when a plugin step fails (warning only). `agents-inc uninstall` MUST remove the plugin and the marketplace. `agents-inc doctor` MUST print the warning code `MOD_NOT_INSTALLED` when `claude plugin list` does not name `agents-inc@agents-inc-local`, and MUST still print `READY` when every other check passes.

Tests:

- **FR-026**: `claude plugin validate mods/agents-inc` MUST report no refusal; `claude plugin test mods/agents-inc` MUST pass.
- **FR-027**: `fixtures/live-events/` MUST hold fake-provider fixtures (`codex.jsonl`, `claude.jsonl`, each with planted fake secrets and an unknown event type) and expected rows (`codex.rows.txt`, `claude.rows.txt`).

### Key Entities

- **Event envelope**: one line of `events.jsonl` (FR-001); `seq` strictly increasing per file.
- **Row**: one rendered, redacted line for a person (FR-014, FR-015).
- **Relay**: the `agents-inc:relay` haiku subagent; its transcript is the live view.
- **Run tool**: `mcp__agents-inc__run`; one call = one dispatch.

## Success Criteria *(mandatory)*

- **SC-001**: With the fake Codex fixture paced at 1 event per 0.5 s, the first row is in the relay transcript (plugin test) and in `events follow` output (unittest) within 2 s of the first event.
- **SC-002**: For each fixture, `stdout.md`, `usage.json` and the verdict line are byte-equal before and after the change (golden test).
- **SC-003**: Zero planted fixture secrets appear in any row, in unittest and plugin test.
- **SC-004**: After SIGTERM to dispatch, no process of the fake delegate's group is alive 5 s later (unittest).
- **SC-005**: `python3 -m unittest discover -s tests -p 'test_*.py'` passes; `claude plugin validate` and `claude plugin test` on `mods/agents-inc` pass.

## Assumptions

- Claude `-p` with `stream-json` needs `--verbose`, and its final `result` message carries `result`, `session_id`, `is_error`, `modelUsage`, `total_cost_usd`, `num_turns`, `duration_ms` like the `json` payload [assumed; `claude --help` lists `stream-json` but not the message shapes]. research.md R1.
- Codex `--json` event types beyond `thread.started`, `error`, `turn.failed` [verified runtime.py:255-273] are `turn.started`, `item.started`, `item.completed` (item types `agent_message`, `reasoning`, `command_execution`, `file_change`, `mcp_tool_call`), `turn.completed` with `usage` [assumed]. Unknown types fall back to FR-014's source-and-type row.
- The engine kills a spawned child with a catchable signal on abort [assumed]; FR-012's `--cancel` covers SIGKILL. research.md R4.
- `$.process.spawn` children run with the engine's environment and outside the Bash tool sandbox [assumed]; the permission grant on `mcp__agents-inc__run` is the control.
- A plugin tool's `{ result: { text } }` reaches the calling model as that text [assumed; reference.md:258-268 says the hook returns the result, not how it is mapped]. T027 asserts the tool result; T043 confirms what the relay model reads.
- The relay costs Claude subscription tokens only (haiku, one tool call, the report echoed once); no paid API (constitution P5).
- Viewing Lead Workers' own runs is out of scope; their `events.jsonl` exist on disk.
