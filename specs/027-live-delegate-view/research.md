<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-plan repo=agents_Inc session=unknown -->
# Research: Live delegate view (027)

Phase 0 of `plan.md`. Each item: decision, rationale, alternatives, evidence.

## R1 Claude live events: stream-json

- Decision: `claude_argv` emits `--output-format stream-json --verbose`. `launch()` reads stdout lines as they come (reader threads for stdout and stderr, main thread waits on a deadline), writes each line to `events.jsonl`, and takes the last line that parses to an object with `type == "result"` as today's `data`. If none, it tries `json.loads(whole stdout)` (legacy single payload, keeps test fakes that print one object working), else raw stdout (today's fallback).
- Rationale: only stream-json gives events before exit [verified `claude --help`: "stream-json" (realtime streaming)]. Keeping the `data` shape lets `claude_usage` stay as is [verified dispatch.py:764-788].
- Alternatives: keep `json` and tail the Claude session transcript file under `~/.claude/projects` (rejected: reads the home dir, path is an engine detail); `--include-partial-messages` (rejected for v1: token-level chunks need heavy coalescing; whole messages are enough for rows).
- Open: `--verbose` requirement and `result` message fields are [assumed]. Implement task T010 checks them against a recorded real stream that the operator captures once (no model call from the delegate).
- Tests that pin the argv must change: tests/test_dispatch_cli.py:246, 425 and tests/test_dispatch_grants.py:184 [verified grep].

## R2 Codex live events

- Decision: add a line callback to `_run_with_deadline` and the no-timeout `subprocess.run` branch (runtime.py:420-446, 525-537) so stdout lines reach the event sink as they arrive; `result.stdout` stays the full text so `parse_thread_id`, `_json_errors` and the `-o` read do not change [verified runtime.py:538-547].
- Rationale: smallest change; the JSONL already exists in json_mode, only its timing changes.
- Alternatives: tail Codex's own session files under `CODEX_HOME` (rejected: home dir, isolated homes vary); turn on `--json` for Lead runs (deferred, Q5: Lead stdout parsing differs).
- Codex event type list beyond `thread.started`, `error`, `turn.failed` is [assumed]; the renderer falls back to a type-only row for unknown types.

## R3 Getting events to the mod

- Decision: dispatch announces its run dir on stderr (FR-007); the mod spawns a second child, `agents-inc events follow <run dir>`, that tails `events.jsonl`, renders, redacts and batches rows in Python.
- Rationale: `$.fs.read` returns a whole file and rejects past 4 MiB [verified claude-code.d.ts:3313-3331], so polling it is quadratic and capped; a `$.clock.sleep` poll also burns the hook's 10 s budget [verified reference.md:190; claude-code.d.ts:5261-5277]. Pulls on a `$.process.spawn` stream do not count against the budget, so a follower child is free to wait. Rendering and redaction in Python reuse `report.SECRET_RE` [verified report.py:18-21] and get unittest coverage; the mod stays a thin relay.
- Alternatives: rows on dispatch stderr directly (rejected: operator asked for a tail of `events.jsonl`, and `--run-dir` users without the mod gain nothing); `tail -F` plus TS rendering (rejected: regex drift between TS and Python).

## R4 Cancel

- Decision: dispatch traps SIGTERM, SIGHUP, SIGINT and runs `kill_and_reap` on the delegate (FR-011). `run.json` records `delegate_pgid`; `agents-inc dispatch --cancel <run dir>` kills that group if the run has no final outcome and the leader still runs the recorded executable (FR-012). The mod calls `--cancel` after an abort.
- Rationale: delegates start in their own session [verified dispatch.py:709-710 `start_new_session=True`; runtime.py:423-424], so killing dispatch alone orphans them. Today only `BaseException` inside `communicate` triggers `kill_and_reap` [verified dispatch.py:725-727; runtime.py:443-445]; a default SIGTERM ends Python with no exception. Which signal the engine sends on abort is [assumed catchable]; `--cancel` covers SIGKILL.
- Open: whether `$.process.run` still works after `next.signal` aborted is [assumed]. Plugin test T031 asserts the call is made; a manual check (T043) confirms on a real host.

## R5 Row kind and rate

- Decision: `system` notices, one per batch (Q3, Q4).
- Rationale: a notice is shown in the transcript and never read by the model [verified reference.md:181]; delegate text cannot steer the relay and the relay's context stays flat. Batching keeps notice count near 1/s.
- Alternatives: user-meta rows (rejected: model reads them, cost and injection risk).

## R6 Mod location and install

- Decision: `mods/agents-inc/` (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `hooks/hooks.json`, `hooks/relay.ts`, `hooks/relay.test.ts`, `tsconfig.json`). Bundle allowlist gains `mods/agents-inc` [verified bundle.py:16 `ALLOWLIST`]; packaged source copies it [verified cli.py:73-86]. agents-inc install/repair register the bundle folder as a folder marketplace and install the plugin through the `claude plugin` CLI (operator Q2, 2026-10-24), which is read in place on `/reload-plugins` [verified reference.md:76].
- Rationale: a folder marketplace tracks repairs without reinstall. The installer goes through the official CLI instead of editing `~/.claude/**` files; constitution P1 binds delegates, not the installer.
- Alternatives: `CLAUDE_CODE_PLUGIN_DIRS` in `~/.claude/settings.json` (rejected: needs a settings edit); repo root as marketplace (rejected: whole repo is not a plugin).

## R7 Relay shape

- Decision: `$.agent.register({ name: "relay", model: "haiku", tools: ["mcp__agents-inc__run"], maxTurns: 3, prompt })` and `$.tool.register({ name: "run", isDeferred: false, inputSchema })` in `session.start` [verified reference.md:194-196 awaited before first prompt; 258-268]. The calling subagent's id is `e.agentId` [verified claude-code.d.ts:13520-13529].
- Rationale: native subagent loops cannot run non-Claude models (CoS fact); a haiku loop with one tool is the cheapest real loop.
- Risk: haiku may paraphrase the report. The CoS still verifies from `stdout.md` (constitution P3); the relay prompt asks for verbatim text.

## R8 Tests

- Decision: Python unittest for events sink, renderer, redaction, follower, cancel, golden stdout/usage (fake `claude`/`codex` executables as the existing tests use [verified tests/test_dispatch_cli.py and 12 other files match fake-CLI patterns]); `claude plugin validate` and `claude plugin test` for the mod, where test hooks on `process.spawn` stand in for dispatch and the follower [inferred from reference.md:81: test hooks sit beneath the plugin].
