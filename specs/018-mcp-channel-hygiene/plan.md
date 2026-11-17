<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-plan repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->
# Implementation Plan: MCP Channel Protocol Hygiene

**Branch**: `development` (no feature branch) | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: spec.md with the clarify answers of 2026-10-06 (1A 2A 3A 4A 5B; Q2 by the operator directly). Research: [research.md](research.md). Home: DomI `specs/consumers/agents_Inc/specs/018-mcp-channel-hygiene/`. This is a `--plan-only` run: no code is written here.

## Start gates

- **Wave 1** (FR-001, FR-002, FR-006, FR-007, FR-009, FR-011): starts after agents_Inc PR 52 merges, and after every R13 primary-source check in research.md is written up (T002). Independent of 017.
- **Wave 2** (FR-003, FR-004, FR-005, FR-008, FR-010): starts after 017 merges (T020). Its design builds on 017 DD1, DD2, DD5 and DD7 as landed; if 017 landed differently, wave 2 is re-planned before code.
- **FR-010 code and tests**: also wait for the canon gate (T027 to T029): a Codex cross-vendor review of the D51 amendment draft, then operator sign-off (D46, P10; operator ruling on Q2, 2026-10-06).
- **FR-010 merge**: waits until the CoS has committed the signed D51 amendment to `docs/DECISIONS.md`; code never lands while `docs/DECISIONS.md:578` still says cancellation is later.
- **FR-010 host**: T028 and T035 need a Codex CLI on the implement host; without one, FR-010 waits.

Line citations below were read at `fe37822` on 2026-10-06. T001 re-checks them at the PR 52 merge commit; T020 re-checks wave-2 citations at the 017 merge commit.

## Summary

1. Both servers negotiate inside `{2025-06-18, 2024-11-05}` and, at `2025-06-18`, return `structuredContent` with declared `outputSchema` (broker tools only).
2. The Claude Worker's `worker_mcp.json` declares `timeout` 3 600 000 ms, so Claude Code's 1 800 000 ms stdio idle limit no longer ties `ask_lead`'s 1800 s wait.
3. The broker records each issued id as `<run-dir>/issued/<rid>`, so `wait`, `answer` and `resume` survive a restart.
4. Worker questions are screened for base64, URL-safe base64, percent and hex forms of every redacted value.
5. Neither server declares MCP Tasks until a live probe shows client support (FR-009).
6. Wave 2: each server reads stdin on its own thread, answers `ping`, honors `notifications/cancelled`, sends progress every 30 s when asked, and (broker) serves `status` during a blocking call; all else stays sequential, as 017 DD7 requires.
7. Wave 2: broker results carry `task_state` (A2A names) beside `status`; a Lead-only `cancel` tool ends a running Worker's process group.

## Technical Context

**Language/Version**: Python 3.10+ standard library (AGENTS.md). `worker_mcp.py` stays self-contained (`worker_mcp.py:1-8`).
**Primary Dependencies**: none new (`threading`, `base64`, `urllib.parse`, `signal` are standard library).
**Storage**: `<run-dir>/issued/<rid>` (new, broker-owned); `worker_mcp.json` gains `timeout`; result files gain `task_state` for cancelled turns. All other D51/D54 and 017 files unchanged.
**Testing**: `python3 -m unittest discover -s tests -p 'test_*.py'`; temp dirs and a fake HOME; stand-in Worker processes; fake clocks for progress. Opt-in live tests under `AGENTS_INC_LIVE_ASK=1` (`tests/test_worker_mcp_live.py:27`) and `AGENTS_INC_LIVE_MCP=1` (`tests/test_mcp_broker_live.py:33`).
**Target Platform**: macOS for live tests (`sandbox-exec`); Linux runs unit tests.
**Constraints**: D51/D54 invariants (spec Requirements preamble); 017 owns socket, push, `check_lead`, `tell`, `events.jsonl`, Lead call time limits; no new environment variable reaches a Worker.
**Scale/Scope**: four install modules edited (`worker_mcp.py`, `mcp_broker.py`, `dispatch.py`, `runtime.py`), no new module, no new test module; five test modules extended.

## Existing code (evidence, `fe37822`)

- `worker_mcp.py:19` `PROTOCOL_VERSION`; `:24-25` `WAIT_SEC 1800`, `POLL_SEC 2.0`; `:28-34` TOOLS; `:84-98` `Channel.ask` polls; `:110-136` `handle` (`:114-115` drops id-less messages; `:117-120` echoes the version; `:135` text-only result); `:139-157` single-threaded `serve`.
- `mcp_broker.py:24` `PROTOCOL_VERSION`; `:27-48` TOOLS; `:49` `AWAIT_MAX_SEC 3500`; `:70` `issued` set; `:73` poll 0.2; `:94-115` `_await`; `:127-150` `tool_dispatch`; `:162-182` `tool_resume`; `:184-192` `tool_answer`; `:194-203` `tool_wait`; `:230-258` `handle`; `:261-287` sequential `serve`.
- `dispatch.py:165-173` `worker_env`; `:251-265` `_ask_channel` writes `worker_mcp.json`; `:289` Claude launch `subprocess.run`; `:912-925` `_in_worker_scope`; `:946-977` `Turn` (daemon thread, single writer of the result); `:1006-1012` `screen_text`; `:1015-1044` `relay_question`; `:1062-1087` `answer_question`; `:1090-1126` `plan_resume`.
- `runtime.py:133` `MCP_TOOL_TIMEOUT_SEC 3600`; `:158-166` `_mcp_server_args` (`tool_timeout_sec` at `:162`); `:172-176` `worker_args`; `:384` Codex launch `subprocess.run`.

## Design decisions

- **DD1 version set** (FR-001; R1; wave 1). Each server gets `SUPPORTED_VERSIONS = ("2025-06-18", "2024-11-05")`. `initialize` returns the requested version if it is in the tuple, else `SUPPORTED_VERSIONS[0]`. The negotiated version is stored on the server object (`Channel` gets a `version` attribute; `Broker` likewise). `worker_mcp.py` keeps its own copy; it never imports `agents_inc`.
- **DD2 structured results** (FR-002; R11; wave 1). Broker TOOLS entries gain `outputSchema`. When `version >= "2025-06-18"`, `handle` adds `structuredContent: data` beside the existing text block (same `json.dumps(data, indent=1)`). Older versions: no `outputSchema` in `tools/list` and no `structuredContent`. `ask_lead` gets no `outputSchema`.
- **DD3 Claude Worker timeout** (FR-006; R6; wave 1). `_ask_channel` writes `"timeout": runtime.MCP_TOOL_TIMEOUT_SEC * 1000` into the `agents_inc` server entry. DD3 imports `MCP_TOOL_TIMEOUT_SEC` lazily inside `_ask_channel`, as `launch` imports from `runtime` (`dispatch.py:297-299`). No change to `worker_env`.
- **DD4 durable issued ids** (FR-007; R7; wave 1). New `Broker.issue(rid)` writes `<run-dir>/issued/<rid>` (`O_CREAT|O_EXCL|O_NOFOLLOW`, 0600; dir 0700, refused if a link) and adds to the set. `Broker.known(rid)` replaces `rid in self.issued` at `:170`, `:187`, `:200`. `tool_dispatch` and `tool_resume` call `issue`.
- **DD5 encoded redaction** (FR-011; R8; wave 1). `screen_text` builds, per value, the forms in R8 and replaces all forms longest first. The plain-value loop stays; the new forms are added to the same sorted set.
- **DD6 no Tasks declaration, plus probe** (FR-009; R12; wave 1). Unit tests pin the absence of `tasks` and `execution`. The probe is opt-in, uses a stand-in server inside the test file, and only records client behavior to research.md R12.
- **DD7 reader thread** (FR-003, FR-004; R3, R10; wave 2). `serve` in each server becomes: a reader loop on the main thread, and at most one call thread for the blocking call in flight. Reader: `ping` → reply at once; `notifications/cancelled` → set the in-flight call's `cancel` event if ids match; broker `tools/call status` → run inline; any other request → FIFO queue drained by the call thread after the current call. One `stdout_lock`; every reply is one line. Built on 017: in `worker_mcp.py` the wait is 017 DD2's queue wait; in `mcp_broker.py` it is 017 DD5's `turn.link.event` wait. On cancel, the reader wakes the 017 wait object directly (a sentinel on the Worker's doorbell queue; `turn.link.event.set()` on the broker), so a cancel lands within 1 s; in Worker file mode the 2 s poll bounds it to `POLL_SEC` + 1 s. The 30 s slice bounds progress cadence only. The 017 socket threads are not touched.
- **DD8 progress** (FR-005; R9; wave 2). Each slice end in DD7's wait sends `notifications/progress` if the request carried a token. A `done` flag under `stdout_lock` stops notices before the result line.
- **DD9 task_state** (FR-008; R4; wave 2). One pure function `task_state(data) -> str | None` in `mcp_broker.py` implements the R4 mapping; `handle` adds it to every tool result dict that has a `status` and a `request_id`, except `usage-error`, `answered` and `not-running` (R4): `task_state()` returns None for those and `handle` omits the key. `status` is never rewritten.
- **DD10 cancel** (FR-010; R2; wave 2; after the canon gate). `launch` (Claude, `dispatch.py:289`) and `run_codex` (`runtime.py:384`) use `subprocess.Popen(..., start_new_session=True)` plus `communicate`, and register the process in a module-level `_RUNNING` slot owned by the current turn (one turn at a time, D54). `Turn.cancel()` sends SIGTERM to the process group, then SIGKILL after 5 s, and marks `cancelled`; when the launch returns, the turn thread writes the red result with `reason` `cancelled` (single writer kept). Broker tool `cancel {request_id}`: `known(rid)` and `busy()` and `turn.rid == rid`, else `not-running`. Lead-only: `worker_mcp.py` TOOLS never changes for it.
- **DD11 ownership** (P2; D46). Lead (Orchestrator rung, opus) writes acceptance tests first and shows them failing, writes canon drafts, reviews every diff. Workhorse (sonnet) writes DD2, DD4, DD7, DD8, DD10 code. Grunt (haiku) writes DD1, DD3, DD5, DD9 code: each is a small fixed-scope diff. A Codex reviewer (Workhorse rung, terra, resolved by `resolve_rung.py Workhorse`) reviews the canon draft and the DD10 diff (D46 item 10(b): irreversible process kill and a D51 amendment); routine diffs may share the vendor (D46).

## Data model (in place of data-model.md)

- **Supported version set**: tuple of strings, newest first; per server; immutable at run time.
- **Negotiated version**: string on the server object; set by `initialize`; read by DD2.
- **Issued-id record**: `<run-dir>/issued/<rid>`, empty regular file, 0600; created once; never deleted by the broker.
- **In-flight call** (wave 2): `{id, cancel: Event, done: bool, progress_token|None, started: monotonic}`; at most one per server.
- **Task state** (wave 2): string from the R4 mapping, in tool results and in a cancelled turn's result file.
- **Running process slot** (wave 2): the current Worker `Popen` and its process group id; cleared when the launch returns.

## Constitution Check

Constitution: DomI `specs/consumers/agents_Inc/memory/constitution.md` (unratified; "Still open — NEEDS-OPERATOR" item 1), so violations are WARN.

| Principle | Status | Note |
|---|---|---|
| P0 cross-reference, never duplicate | PASS | 017 design cited, not restated; `worker_mcp.py` duplicates the version tuple by necessity (self-contained), pinned equal by a test. |
| P1 repo-scoped writes | PASS | Runtime writes stay in run dirs; tests use temp dirs and a fake HOME. |
| P2 labor ladder | PASS | DD11: Grunt for narrow diffs, Workhorse for threads and process control, Lead for tests and canon. |
| P3 no self-graded gates | PASS | Lead tests before code; Codex review for canon and DD10; Supervisor verifies. |
| P4 deterministic policy over prompt | PASS | Version choice, timeouts, redaction, `task_state`, cancel checks are code. |
| P5 hard $0 per task | PASS | No model calls except opt-in live tests on the subscription. |
| P6 audience-scoped doc rendering | PASS | Spec artifacts are agent/builder documents in plain prose; no human-facing doc is edited. |
| P7 nickname discipline | PASS | Models are named by their aliases (opus, sonnet, haiku, terra) as `resolve_rung.py` prints them. |
| P8 delegation prompt contract | PASS | Each task carries its own success and failure gate for a 14-field dispatch. |
| P9 edit hygiene | PASS | Additive edits; only FR-002 touches existing tool entries. |
| P10 lessons relay up | PASS | FR-012 canon items go to the Supervisor as LESSON-CANDIDATE. |

Post-design re-check: PASS.

## Project Structure

```text
DomI specs/consumers/agents_Inc/specs/018-mcp-channel-hygiene/
├── spec.md, plan.md, research.md, clarify-questions.md, tasks.md
└── checklists/requirements.md, checklists/protocol-hygiene.md
agents_inc/install/worker_mcp.py   # DD1 (w1); DD7, DD8 (w2)
agents_inc/install/mcp_broker.py   # DD1, DD2, DD4 (w1); DD7, DD8, DD9, DD10 tool (w2)
agents_inc/install/dispatch.py     # DD3, DD5 (w1); DD10 Popen and Turn.cancel (w2)
agents_inc/install/runtime.py      # DD10 Codex Popen (w2)
tests/test_worker_mcp.py           # extend: negotiation, timeouts, no Tasks (w1); ping, cancel, progress, no cancel tool (w2); exact broker list in test_needs_lead_answer_wait_resume gains `cancel` only (SC-009)
tests/test_mcp_broker.py           # extend: negotiation, structured, restart, no Tasks (w1); ping, cancel notice, progress, status during wait, task_state, cancel tool (w2); exact list in test_initialize_and_tools_list gains `cancel` only (SC-009)
tests/test_dispatch_resume.py      # extend: encoded redaction (w1)
tests/test_worker_mcp_live.py      # extend (opt-in): Claude idle-limit check (w1)
tests/test_mcp_broker_live.py      # extend (opt-in): Tasks client probe (w1)
```

The final pipeline task "Move specs to DomI" does not apply: this spec was written in DomI from the start (dispatch of 2026-10-06).

## Agent context update

DomI `AGENTS.md` has no `<!-- SPECKIT START -->` marker (`grep -c` printed 0), so this step is skipped. agents_Inc's agent context is `CONTEXT.md`; this plan does not edit it. LESSON-CANDIDATE rows for sign-off (FR-012, T038): new **Task state** (an A2A-named state of one Worker turn, beside `status`); amended **Dispatch broker** tools list gains `cancel`.

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| Reader thread in both stdio servers | `ping`, cancel and progress must work while a call blocks (F3) | Bounded calls alone (017 FR-016) still leave `ask_lead` silent for up to 30 min |
| `Popen` plus a process slot | `subprocess.run` gives no handle to signal (`dispatch.py:289`, `runtime.py:384`) | Killing by name or pid scan could hit the wrong process |
| Duplicate version tuple in `worker_mcp.py` | The copy runs without `agents_inc` | Importing would break the self-contained rule |
