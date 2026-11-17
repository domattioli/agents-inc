<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-plan repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->
# Research: MCP Channel Protocol Hygiene (018)

Phase 0 for [plan.md](plan.md). R1 to R5 record the clarify answers of 2026-10-06. R6 to R12 settle the technical unknowns from the code. R13 lists the primary-source checks that must pass before implementation. Line citations are against agents_Inc `fe37822` (2026-10-06); the implementer re-checks them at T001.

Network note: `WebFetch` of `https://modelcontextprotocol.io/specification/2026-07-28/changelog` and `https://modelcontextprotocol.net/specification/2026-07-28/changelog` returned `EGRESS_BLOCKED` on 2026-10-06. The block was not routed around. Every protocol fact below that rests on a primary spec is tagged [assumed] and listed in R13.

## Clarify answers

**R1. Supported version set `{2025-06-18, 2024-11-05}` (Q1 A, Supervisor, operator-directed).**
- Decision: both servers negotiate inside this set, newest first. Structured results only when `2025-06-18` is negotiated.
- Rationale: fixes the echo at `worker_mcp.py:118-120` and the pin at `mcp_broker.py:24`, `:238`, and adds structured results without claiming 2026-07-28 features that are unverified.
- Alternatives: `2024-11-05` only (B) loses structured results; adding `2026-07-28` (C) promises Tasks and envelope rules nobody has checked.
- Follow-up, not a requirement: add `2026-07-28` to the set only after its primary spec is read and every server requirement of that version is met. Claude Code 2.1.290 already carries a `2026-07-28` protocol era (binary strings, 2026-10-06), so a client may ask for it; under R1 it gets `2025-06-18` back [assumed: the client accepts an older version; the FR-001 live check confirms].

**R2. Lead-only `cancel` broker tool (Q2 A, operator domattioli, directly).**
- Decision: `cancel {request_id}` on the broker server only. Canon first: the D51 amendment and the DECISIONS entry need operator sign-off and a Codex (cross-vendor) review before any FR-010 code (tasks T027 to T029 precede every FR-010 test and code task, T030 to T035).
- Mechanism finding: both Worker launches block in `subprocess.run` with no process handle: Claude at `dispatch.py:289`, Codex at `runtime.py:384`. Cancel therefore needs the launch to start the Worker in its own session (`start_new_session=True`) and to register the process with the running `Turn`, so `cancel` can signal the group (SIGTERM, then SIGKILL after 5 s) [inferred from the code].
- Result: `status` `red`, `reason` `cancelled`, `task_state` `canceled`, written by the turn thread when the launch returns, so the existing single writer of `<rid>.result.json` stays the only writer (`dispatch.py:972-975`).
- Counts: `workers_spawned`, `resumes` and `request_counts` follow the normal red path; nothing is refunded.

**R3. During a blocking call, broker `status` only (Q3 A, Supervisor, operator-directed).**
- Decision: each server gets a stdin reader thread. A blocking `tools/call` runs on one worker thread at a time. While it runs, the reader answers `ping`, handles `notifications/cancelled`, and (broker only) runs `status` inline. Any other request queues in arrival order behind the blocking call.
- Rationale: keeps 017 plan DD7 ("handled at once, never while a Worker call blocks, because the stdio loop is sequential") true for `answer`, `push`, `cancel`, `resume`, `wait` and `dispatch`.
- Output: one `threading.Lock` around each stdout line write; a reply is one `json.dumps(...) + "\n"` write and flush.

**R4. Additive `task_state`, A2A names, lower-case hyphen form (Q4 A, Supervisor, operator-directed).**
- Decision and mapping: `timeout` → `working` (no claim that the turn is alive; a recovered id of a dead turn also reads `working`); `needs-lead` → `input-required`; `green` → `completed`; `red` → `failed`, except `reason` `cancelled` → `canceled`; every `refused` reason → `rejected`, except `not-running`; `answered` and `not-running` → no `task_state`; a successful `cancel` reply → `canceled`; `usage-error` → no `task_state` (not a turn).
- Spellings are [assumed] from the Supervisor's secondary source (https://www.glukhov.org/ai-systems/comparisons/a2a-protocol-2026-adoption/). A2A v1.0 may write states as `TASK_STATE_INPUT_REQUIRED` in its protobuf form [assumed]; the JSON lower-case form is checked at R13 before code.

**R5. Two waves (Q5 B, Supervisor, operator-directed).**
- Wave 1, after PR 52, independent of 017: FR-001, FR-002, FR-006, FR-007, FR-009, FR-011.
- Wave 2, after 017 merges: FR-003, FR-004, FR-005, FR-008, FR-010.
- Conflict surface: wave 1 edits `handle()` in both servers (FR-001, FR-002) and `TOOLS` (FR-002); 017 edits the same `TOOLS` lists (adds `check_lead`, `push`). 017 rebases over wave 1 without design change.

## Technical unknowns

**R6. Claude Worker client timeout (F8, FR-006).**
- Finding: Claude Code 2.1.290 (`/opt/claude-code/bin/claude`, Linux build) computes the stdio idle limit as `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT ?? 1800000` ms, raised to a per-server `timeout` (ms) when larger, and aborts with "sent no response or progress for ...s; aborting" [verified by Lead 2026-10-06; Supervisor confirmed the variable and the message, and marked the exact stdio default [inferred]].
- `worker_env` passes neither variable (`dispatch.py:165-173`), and `worker_mcp.json` sets no `timeout` (`dispatch.py:262-264`).
- Decision: write `"timeout": MCP_TOOL_TIMEOUT_SEC * 1000` (3 600 000) in the `agents_inc` server entry of `worker_mcp.json`. No environment change. The opt-in live test on macOS (T011) confirms; until then the macOS default is [assumed].
- Codex: `tool_timeout_sec=3600` for both servers (`runtime.py:133`, `:162`, through `_mcp_server_args`). Margins: `WAIT_SEC` 1800 and `AWAIT_MAX_SEC` 3500 are 1800 s and 100 s below 3600 [verified].

**R7. Durable issued ids (F5, FR-007).**
- Decision: `<run-dir>/issued/<rid>` empty file per issued id, created with `O_CREAT|O_EXCL|O_NOFOLLOW`, mode 0600, before the id is used. `issued/` is created mode 0700 and refused if it is a symlink. `Broker.known(rid)` = in-memory set, else `REQUEST_ID_RE` match plus `os.path.lexists(issued/<rid>)` with a non-link regular file.
- Trust: the run dir is broker-owned; the Lead has no read or write access to it (D51, `docs/DECISIONS.md:573`) [verified by read]. So a record there cannot be forged by the Lead.
- `resume` new ids (`<root>-r<n>`) are recorded the same way (`mcp_broker.py:176-177`).

**R8. Encoded-form redaction (F9, FR-011).**
- Decision: for each value `screen_text` redacts today (environment values of 8 or more characters, `dispatch.py:1010`), also replace `base64.b64encode`, `base64.urlsafe_b64encode` (with and without `=` padding), `urllib.parse.quote(value, safe="")` and `value.encode().hex()` (lower and upper case). Longest first, as today. Plain-value redaction stays unchanged.
- Limit, stated: a value base64-encoded inside a larger blob at a non-3-byte offset, or split across fragments, still passes (spec Out of Scope).

**R9. Progress notices (F3, F8, FR-005).**
- Decision: when `params._meta.progressToken` is present, the blocking call's wait loop sends `notifications/progress` with `{progressToken, progress: <elapsed whole seconds>, message}` every 30 s, where `message` is `waiting; elapsed=<s>` on the Worker server and `waiting; elapsed=<s>; task_state=<state>` on the broker. The sender checks a per-call `done` flag under the stdout lock, so no notice follows the result.
- Shape [assumed; primary https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress, R13].
- In wave 2 the wait is 017's queue wait (Worker, 017 DD2) or event wait (broker, 017 DD5), with a 30 s timeout per wait slice instead of the plain sleep.

**R10. Cancel notification (F3, FR-004).**
- Decision: the reader thread maps `notifications/cancelled {requestId}` to the in-flight call's `cancel` event; the reader also wakes the 017 wait object at once (a sentinel on the Worker's doorbell queue; `turn.link.event.set()` on the broker), and the wait returns a sentinel that suppresses the reply. Bound: 1 s on the broker and in Worker socket mode; `POLL_SEC` + 1 s in Worker file mode.
- Shape and "no response" rule [assumed; primary https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/cancellation, R13].

**R11. Structured results (F1, FR-002).**
- Decision: broker tools declare `outputSchema` (an object schema with `required: ["status"]` for `dispatch`, `wait`, `resume`, `answer`, `cancel`, and, for `status`, all five keys required: `workers_spawned`, `request_counts`, `fan_out`, `remaining_total`, `worker_models`, `mcp_broker.py:122-124`). Results carry `structuredContent` equal to the JSON in the text block. `ask_lead` declares no `outputSchema` and keeps plain text.
- Version rule [assumed; primary https://modelcontextprotocol.io/specification/2025-06-18/server/tools, R13].

**R12. Tasks client-support probe (F2, FR-009).**
- Decision: an opt-in live test starts a stand-in stdio server that declares `tasks` and `execution.taskSupport: "optional"` on one tool, runs one Claude Code turn and (if installed) one Codex turn that calls the tool, and records whether the client sent a task-augmented `tools/call`. It records client version and date into this file (R12 result line). No production server declares `tasks` until a recorded pass and a new clarify round.
- Local evidence so far: Claude Code 2.1.290 holds the Tasks schemas and an adapter that removes `execution` and `capabilities.tasks` in some path [inferred]; Codex CLI absent here [assumed unknown].
- R12 result: (empty until T016 runs).

## R13. Primary-source checks before implementation (T002)

Each must be read, and its finding written here with access date, before wave code. A mismatch goes back to the Lead and may change an FR.

| Fact | Used by | Primary URL |
|---|---|---|
| Version negotiation rule | FR-001 | https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle |
| `structuredContent` and `outputSchema` arrive in 2025-06-18 | FR-002 | https://modelcontextprotocol.io/specification/2025-06-18/changelog and https://modelcontextprotocol.io/specification/2025-06-18/server/tools |
| `notifications/cancelled` semantics | FR-004 | https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/cancellation |
| `notifications/progress` shape | FR-005 | https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress |
| `ping` during requests | FR-003 | https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/ping |
| Tasks extension id and states (2026-07-28) | FR-009, R1 follow-up | https://modelcontextprotocol.io/specification/2026-07-28/changelog |
| A2A v1.0 task-state names and JSON spelling | FR-008 | https://a2a-protocol.org/latest/specification/ |

### R13 findings (T002, Supervisor opus, 2026-10-06)

The spec websites stay blocked (`CONNECT tunnel failed, response 403`), but the spec source repositories on GitHub are reachable. Each page below was read from the source file that the website renders: `raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/<version>/<path>.mdx` and `raw.githubusercontent.com/a2aproject/A2A/main/docs/specification.md`.

- Version negotiation (FR-001), accessed 2026-10-06, `2025-06-18/basic/lifecycle.mdx:130-132`: "If the server supports the requested protocol version, it **MUST** respond with the same version. Otherwise, the server **MUST** respond with another protocol version it supports. This **SHOULD** be the _latest_ version supported by the server." Matches FR-001 [verified].
- Structured output (FR-002), accessed 2026-10-06, `2025-06-18/changelog.mdx:14` ("Add support for structured tool output") and `2025-06-18/server/tools.mdx:188`, `:298-300` (`outputSchema` optional; `structuredContent` object; "a tool that returns structured content SHOULD also return the serialized JSON in a TextContent block"). Matches FR-002 [verified].
- Cancellation (FR-004), accessed 2026-10-06, `2025-06-18/basic/utilities/cancellation.mdx:36-43`: receivers SHOULD stop processing and not send a response; MAY ignore unknown or completed requests. Matches FR-004 [verified].
- Progress (FR-005), accessed 2026-10-06, `2025-06-18/basic/utilities/progress.mdx:16`, `:38`, `:53`, `:56`: token string or integer; optional `message`; `progress` MUST increase. Matches R9 [verified].
- Ping (FR-003), accessed 2026-10-06, `2025-06-18/basic/utilities/ping.mdx:29`: "The receiver **MUST** respond promptly with an empty response". Matches FR-003 [verified].
- Tasks extension (FR-009), accessed 2026-10-06, `2026-07-28/changelog.mdx:22`: extension id `io.modelcontextprotocol/tasks` [verified]. MISMATCH for FR-009 text: 2026-07-28 replaces `tasks/result` with polling via `tasks/get` plus a new `tasks/update`. The FR-009 probe must look for `tasks/get` and `tasks/update`, not `tasks/result`. Also `:14`: 2026-07-28 removes the `initialize` handshake (stateless; the version travels in each request's `_meta`). So the R1 follow-up "add `2026-07-28` to the set" is a protocol redesign, not a version-string addition. Neither changes wave 1.
- A2A task states (FR-008), accessed 2026-10-06, `a2aproject/A2A docs/specification.md:3` (latest released 1.0.0) and `:1213-1219`: enum values MUST serialize as their ProtoJSON names, e.g. `"TASK_STATE_INPUT_REQUIRED"`; terminal states `TASK_STATE_COMPLETED`, `TASK_STATE_FAILED`, `TASK_STATE_CANCELED`, `TASK_STATE_REJECTED` (`:175`). MISMATCH: FR-008 and Q4 A assumed the lower-case hyphen form (`input-required`). A2A's own prose still says "`input-required` state" (`:632`), but the wire value is SCREAMING_SNAKE. FR-008 is wave 2; its spelling goes back to the operator before wave 2 (T020 gate).
