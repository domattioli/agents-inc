<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-plan repo=agents_Inc session=unknown -->
# Implementation Plan: Live delegate view

**Branch**: `development` (no feature branch) | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/027-live-delegate-view/spec.md`

## Summary

Part A makes `agents-inc dispatch` stream provider events into `<run dir>/events.jsonl` while the delegate runs (Claude via `stream-json`, Codex via its existing `--json` lines), adds lifecycle events, a run-dir stderr line, signal-safe cancel and an `agents-inc events` command that follows, renders, redacts and batches rows. Part B adds a Claude Code mod at `mods/agents-inc/` that registers the `agents-inc:relay` haiku agent and the `mcp__agents-inc__run` tool; the tool starts dispatch, runs the follower and appends each batch as a `system` notice to the calling subagent's transcript, then returns the report. Design choices: research.md R1-R8.

## Technical Context

**Language/Version**: Python 3.11+ standard library (agents_inc); TypeScript ES module for the mod (Claude Code plugin API, types in `.claude-plugin/types/` laid by the engine)
**Primary Dependencies**: none new; Claude Code CLI with `claude plugin validate|test`
**Storage**: files in the run dir (`events.jsonl`, `run.json`)
**Testing**: `python3 -m unittest discover -s tests -p 'test_*.py'`; `claude plugin validate mods/agents-inc`; `claude plugin test mods/agents-inc`
**Target Platform**: macOS and Linux hosts running agents-inc
**Project Type**: CLI plus editor plugin
**Performance Goals**: first row within 2 s of its event (SC-001); at most about 1 notice/s per relay
**Constraints**: `stdout.md`, `usage.json`, verdict line unchanged (FR-006); no `~/.claude/**` writes by agents-inc; $0 (P5)
**Scale/Scope**: one relay per dispatch; events file capped at 64 MiB

## Constitution Check

Constitution v1.8.0 is unratified: violations report as WARN [verified .specify/memory/constitution.md:62-64].

- P1 repo-scoped writes, secrets: PASS. Events stay in the git-ignored run dir, mode 0600, not mirrored (FR-008); rows redacted (FR-015); mod install is an operator step (R6).
- P3 no self-graded gates: PASS. The mod does not self-approve its tool (FR-025); the CoS verifies from `stdout.md`, not from the relay's echo (R7).
- P4 deterministic policy: PASS. The tool's model, slots-path and `agentId` checks are code, not prompt (FR-020).
- P5 $0: PASS. Haiku relay on the Claude subscription; no paid API.
- P6 doc audience: PASS. Spec artifacts are agent-facing prose; operator install note goes to `docs/START-HERE.md` in lite prose (T041).
- P9 edit hygiene: PASS. Plan edits existing functions in place.
- Re-check after design: PASS, no new violations.

## Design

### A1 Event sink (`agents_inc/install/live_events.py`, new)

`EventSink(run_dir, safe_writes)`: opens `events.jsonl` (0600; `O_CREAT|O_EXCL|O_NOFOLLOW` when `safe_writes`, else `O_CREAT|O_APPEND`), `emit(source, event)` writes the FR-001 envelope and flushes, cuts lines over 64 KiB, stops provider events at 64 MiB after one `events.truncated`. `line(source, text)` parses JSON or wraps as `{"type":"raw","text":...}`. Thread-safe with one lock. Never raises into dispatch: an OSError disables the sink and sets `run.json` `events_error`.

### A2 Claude launch (`dispatch.py` `claude_argv`, `launch`)

`claude_argv` ends with `--output-format stream-json --verbose`. `launch` replaces `communicate` with `_stream_run(proc, prompt, limit, on_line)`: write prompt and close stdin, two reader threads (stdout lines to `on_line` and a buffer; stderr to a buffer), join with the deadline; on expiry the same `os.killpg` SIGKILL path and rc 124 mark as today (dispatch.py:714-724). Result parse per R1. `_stream_run` lives in `live_events.py` and is shared with A3.

### A3 Codex launch (`runtime.py`)

`run_codex` gains `on_line=None`; `_run_with_deadline` and the no-timeout branch use `_stream_run` when `on_line` is set, else today's code. `launch` passes `sink.line` bound to `codex` only when `json_mode` holds (non-Lead).

### A4 Dispatch lifecycle (`dispatch.py` run path, lines ~1298-1438)

After run-dir mkdir: stderr line (FR-007), create sink, `run.start`. Around `launch`: install SIGTERM/SIGHUP/SIGINT handlers that raise a `Cancelled` exception in the main thread; `launch`'s `BaseException` path already kills and reaps (dispatch.py:725-727, runtime.py:443-445). Catch `Cancelled` in the run path: `run.end` cancelled, `run.json` outcome, verdict line `dispatch <run_id> <model> cancelled`, exit 130. `delegate_pgid` written to `run.json` right after `Popen` through a callback (`on_start(pid)`). `run.end` on every other exit path (`_finish`, `_launch_failed`, refusals after mkdir, dry run). Broker Workers use the same path (their run dirs get events too).

### A5 Cancel command (`dispatch.py` CLI, `cli.py:183`)

`--cancel RUN_DIR`: load `run.json`; final outcome present: `nothing to cancel`, exit 0. Else read `delegate_pgid`, check the group leader's command via `ps -o comm= -p <pgid>` matches `argv[0]` basename of recorded `argv`; match: `os.killpg(pgid, SIGTERM)`, then SIGKILL after 5 s if alive; print `cancelled <pgid>`. No match: `nothing to cancel`.

### A6 Rows (`agents_inc/live_rows.py`, new) and `agents-inc events` (`cli.py`)

`render(envelope, model, t0) -> list[str]` maps events to FR-014 rows:

| source/type | kind | summary |
|---|---|---|
| agents-inc `run.start` | start | `run <run_id>` |
| codex `item.*` `agent_message`; claude `assistant` text block | say | the text |
| codex `reasoning`; claude `thinking` block | think | first 120 chars |
| codex `command_execution`; claude `tool_use` Bash | tool | command, `(exit N)` when known |
| codex `mcp_tool_call`; claude other `tool_use` | tool | tool name + compact input keys |
| codex `file_change`; claude Edit/Write `tool_use` | file | paths |
| codex `error`/`turn.failed`; claude `result` with `is_error` | error | message |
| codex `turn.completed`; claude `result` | usage | in/out tokens |
| `raw`, unknown | note | `<source> <type>` (raw: first 120 chars) |
| agents-inc `run.end` | end | `<outcome> rc=<rc>` |

`redact(text, env, home)` per FR-015 using `report.SECRET_RE`. `follow(run_dir, out, clock, interval=1.0, batch=20)` tails by byte offset with 0.2 s polls, handles partial lines, prints batches per FR-016, exits per FR-013. `events redact` filters stdin. Subcommands in `cli.py` beside `dispatch`.

### B1 Mod (`mods/agents-inc/`)

Files: `.claude-plugin/plugin.json` (`name: "agents-inc"`), `.claude-plugin/marketplace.json` (`name: "agents-inc-local"`, one entry `source: "./"`), `hooks/hooks.json` (`modules: ["relay.ts"]`), `hooks/relay.ts`, `hooks/relay.test.ts`, `tsconfig.json`, `README.md` (install lines).

`relay.ts`: `session.start` registers agent and tool (FR-018, FR-019), then `next(e)`. `tool.call` on `{ tool: 'mcp__agents-inc__run' }`:
1. Guards (FR-020): `e.agentId`; model in a fixed list (`fable opus sonnet haiku astra sol terra luna`); free models deny naming `agent.sh`; `$.fs.stat(slots, { resolve: true }).realPath` under the session cwd's realPath.
2. `const d = $.process.spawn({ argv: ['agents-inc','dispatch','--model',m,'--slots',p,'--cwd',cwd, ...effort] })`.
3. Read `d` chunks; stdout to a buffer; stderr scanned for the FR-007 line; when found, start `f = $.process.spawn({ argv: ['agents-inc','events','follow',runDir] })` in a concurrent async loop that splits stdout on blank lines and calls `$.session.append({ message: { type: 'system', content: [{ type: 'text', text }] }, agentId: e.agentId })`, counting against the 600 cap (FR-022).
4. When `d` ends: let `f` drain up to 3 s, then end it; read `stdout.md` with `$.fs.read`; build FR-023 text; return `{ result: { text } }`.
5. `next.signal` abort listener: end both loops, `$.process.run(['agents-inc','dispatch','--cancel',runDir])` once, catch all.
6. `.catch(($, e, next) => next.called ? next(e) : { deny: 'agents-inc relay failed' })`.

No `tool.check` hook (FR-025). `agents-inc` is found on the engine's PATH; the README names `~/.local/bin` [assumed path from the machine's launcher note, not code-verified].

### B2 Bundle and doctor

`bundle.py:16` `ALLOWLIST` adds `mods/agents-inc`; `cli.py` `_packaged_source` copies it; package data includes it. Q2 (operator): after the bundle copy, `install` and `repair` run `claude plugin marketplace add <bundle>/mods/agents-inc` then `claude plugin install agents-inc@agents-inc-local` through `subprocess.run` with a 60 s timeout, only when `shutil.which("claude")` is set and `claude plugin list` does not name the plugin; `--no-mod` skips both; any non-zero exit prints `warning: mod install failed (<rc>)` and install stays green. `uninstall` runs `claude plugin uninstall agents-inc@agents-inc-local` and `claude plugin marketplace remove agents-inc-local`, warnings only. `doctor` adds warning code `MOD_NOT_INSTALLED` (never fails `READY`). Tests use a fake `claude` on PATH that records its argv.

## Project Structure

### Documentation (this feature)

```text
specs/027-live-delegate-view/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
└── checklists/requirements.md
```

Data model and contracts are inline above (A1 envelope, A6 rows, B1 tool input); no separate files, by dispatch scope.

### Source Code (repository root)

```text
agents_inc/
├── install/
│   ├── live_events.py      # new: EventSink, _stream_run
│   ├── dispatch.py         # claude_argv, launch, run path, --cancel
│   ├── runtime.py          # run_codex on_line
│   ├── cli.py              # events subcommands, --cancel flag, packaged source
│   ├── bundle.py           # ALLOWLIST
│   └── report.py           # SECRET_RE reused, unchanged
└── live_rows.py            # new: render, redact, follow
mods/agents-inc/            # new: Claude Code mod
fixtures/live-events/       # new: codex.jsonl, claude.jsonl, *.rows.txt, fake CLIs
tests/
├── test_live_events.py     # new
├── test_live_rows.py       # new
└── test_dispatch_cancel.py # new
```

**Structure Decision**: Python stays in `agents_inc/`; the mod is a self-contained plugin folder at `mods/agents-inc/` so it bundles and installs as one unit.

## Complexity Tracking

None.
