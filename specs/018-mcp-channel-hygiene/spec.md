<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-clarify repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->
# Feature Specification: MCP Channel Protocol Hygiene

**Feature Branch**: `development` (feature 018-mcp-channel-hygiene; spec home DomI `specs/consumers/agents_Inc/specs/018-mcp-channel-hygiene/`, per AGENTS.md "Governance")
**Created**: 2026-10-06
**Status**: Draft (specify and clarify done 2026-10-06; plan, tasks, checklist done; analyze pending)
**Input**: Supervisor dispatch of 2026-10-06, run as speckit-pipeline new mode, `--plan-only`. Supervisor review findings F1 to F10 on the D51 broker (`agents_inc/install/mcp_broker.py`) and the D54 Worker server (`agents_inc/install/worker_mcp.py`, with the ask, answer and resume helpers in `agents_inc/install/dispatch.py`). Operator ruling 2026-10-06: 018 complements DomI spec 017-worker-lead-socket and must not redo, contradict or re-open it.

## Terms used here

- **Worker, Lead, Broker, Run dir, Request id, Turn, Channel, Push, Doorbell**: as defined in spec 017 "Terms used here" (`../017-worker-lead-socket/spec.md`). This spec does not redefine them.
- **Broker server**: the Lead-facing stdio MCP server, `mcp_broker.py` (D51). Its client is the Codex CLI of a Codex Lead (`mcp_broker.py:1`, `runtime.py:142-148`).
- **Worker server**: the Worker-facing stdio MCP server, `worker_mcp.py` (D54). Its client is the Worker's Claude Code or Codex CLI.
- **Blocking call**: a `tools/call` that waits on something outside the server: `ask_lead` (Worker server, up to 1800 s, `worker_mcp.py:24`), and `dispatch`, `resume` and `wait` (broker server, up to 3500 s, `mcp_broker.py:49`).
- **Task state**: a named lifecycle state of one Worker turn, reported beside the existing `status` field (FR-008).
- **Supported version set**: the MCP protocol versions a server implements in full. A version enters the set only when the server meets that version's requirements.

## Background (verified state; Supervisor findings are cited as input, not re-derived)

Code was read at agents_Inc `fe37822` on 2026-10-06. The Supervisor's findings were made at `1fcfd76`. Every line cited below matches at `fe37822` [verified by Lead read 2026-10-06].

| Id | Finding (Supervisor, 2026-10-06) | Provenance | Taken by |
|---|---|---|---|
| F1 | Both servers pin protocolVersion `2024-11-05` (`mcp_broker.py:24`, `worker_mcp.py:19`). `worker_mcp.py:118-120` echoes any version the client asks for, which breaks negotiation. Results are JSON text in one text block, with no `structuredContent` or `outputSchema` (`mcp_broker.py:257`, `worker_mcp.py:135`). | [verified] Supervisor | FR-001, FR-002 |
| F2 | needs-lead, `wait`, `answer` and `<rid>-r<n>` resume hand-roll a task lifecycle that the MCP 2026-07-28 Tasks extension (`io.modelcontextprotocol/tasks`; states working, input_required, completed, failed, cancelled) and A2A v1.0 tasks standardize. | [verified] Supervisor web search 2026-10-06, secondary sources: https://blog.mcpservers.org/posts/mcp-spec-2026-07-28, https://modelcontextprotocol.net/specification/2026-07-28/changelog, https://www.glukhov.org/ai-systems/comparisons/a2a-protocol-2026-adoption/ | FR-008, FR-009 |
| F3 | A blocking call holds the single-threaded stdio loop: no `ping` reply, no progress notification, `notifications/cancelled` dropped (every message without an id is ignored, `worker_mcp.py:114-115`, `mcp_broker.py:235-236`), and the Lead cannot call `status` during `dispatch`. | [verified] Supervisor | FR-003, FR-004, FR-005 |
| F4 | No way to cancel a running Worker. | [verified] Supervisor | FR-010 (Q2 A, operator) |
| F5 | `Broker.issued` is an in-memory set (`mcp_broker.py:70`). A broker restart loses `wait`, `answer` and `resume` on earlier ids, though the result and question files persist. | [verified] Supervisor | FR-007 |
| F6 | Polling everywhere: Worker 2 s (`worker_mcp.py:25`), broker 0.2 s (`mcp_broker.py:73`), file broker `dispatch --wait` 1 s. 017 covers the Worker answer path and the broker wait (017 plan DD2, DD5). | [verified] Supervisor | Out of Scope |
| F7 | One Worker turn at a time (`worker-running` refusal, `mcp_broker.py:147-148`). | [verified] Supervisor | Out of Scope |
| F8 | Codex Workers and the Codex Lead get `tool_timeout_sec=3600` (`runtime.py:133`, `:162`). Claude Workers get no explicit MCP tool timeout: `worker_env` passes only fixed keys (`dispatch.py:165-173`) and `worker_mcp.json` sets none (`dispatch.py:262-264`). | Codex half [verified] Supervisor; Claude half was [assumed], see next row | FR-006 |
| F8 (Lead check) | The Claude Code 2.1.290 binary in this container sets the stdio MCP tool idle limit to 1 800 000 ms unless `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT` or a per-server `timeout` (ms) raises it, and resets it on any response or progress notification (strings in `/opt/claude-code/bin/claude`: `function Or(e){...a.CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT??(r==="stdio"?Ar:kr)...}` with `Ar=1800000`; message "sent no response or progress for ...s; aborting. If this server is configured in your MCP settings, set a per-server "timeout" (ms)"). `ask_lead` waits 1800 s with no progress, so its no-answer text can arrive after the client has already aborted. | [verified] for the 2.1.290 Linux build read here; [assumed] for the operator's macOS build until the live check (FR-006) | FR-006 |
| F9 | `screen_text` redacts exact substrings of environment values of 8 or more characters (`dispatch.py:1006-1012`): it misses encoded or split secrets and over-redacts paths under HOME. | [inferred] Supervisor | FR-011 (encoded forms); split secrets and HOME over-redaction to Out of Scope |
| F10 | Messages carry only a request id, no sender identity; acceptable under local filesystem isolation. 017 adds a source tag to pushes (017 FR-010). | [inferred] Supervisor | Out of Scope |

### Layer decision (operator-accepted 2026-10-06)

MCP stays the transport for both servers. A2A is not adopted now; it stays a possible future outward gateway (one Out-of-Scope line). Where this spec names Worker-turn states, it uses A2A task-state names (FR-008).

### Premise: do Claude Code and Codex CLI support the MCP Tasks extension as clients?

Status: **not verified; gated** (FR-009).

- Primary-source check failed: `WebFetch https://modelcontextprotocol.io/specification/2026-07-28/changelog` and `https://modelcontextprotocol.net/specification/2026-07-28/changelog` both returned `EGRESS_BLOCKED` on 2026-10-06. The Lead did not route around the block.
- Claude Code 2.1.290 (local binary, read 2026-10-06): the bundled MCP code holds a `2026-07-28` protocol era, the string `io.modelcontextprotocol/tasks`, the state set `working, input_required, completed, failed, cancelled`, the tool field `execution.taskSupport` (`required|optional|forbidden`) and the methods `tasks/get`, `tasks/result`, `tasks/cancel`. One adapter also deletes `execution` from listed tools and `tasks` from server capabilities in some path. So the client knows the shapes, but whether it sends task-augmented `tools/call` to a stdio server is unproven [inferred].
- Codex CLI: not installed in this container (`codex: command not found`). Support is unknown [assumed].

## Clarifications

### Session 2026-10-06

Questions: `clarify-questions.md`. Q2 was answered by the operator (domattioli) directly. Q1, Q3, Q4 and Q5 were answered by the Supervisor (opus), operator-directed, 2026-10-06.

- Q1: Which MCP protocol versions enter each server's supported set? → A: `{2025-06-18, 2024-11-05}`; structured results only when `2025-06-18` is negotiated. `2026-07-28` is deferred until the primary spec is read; research.md records it as a follow-up, not a requirement. (Supervisor, operator-directed.)
- Q2: May the Lead cancel a running Worker? → A: Yes. A Lead-only `cancel` broker tool. The D51 amendment and the DECISIONS entry are LESSON-CANDIDATE items that need operator sign-off and a cross-vendor (Codex) review before any FR-010 code. (Operator, domattioli, directly.)
- Q3: Which tool calls may run while a blocking call waits? → A: Broker `status` only; on the Worker server, none. All other calls wait. (Supervisor, operator-directed.)
- Q4: How are task states named? → A: An additive `task_state` field beside `status`, A2A v1.0 names in lower-case hyphen form; `status` unchanged; spellings re-checked against the A2A primary spec before code. (Supervisor, operator-directed, following the operator's layer decision of 2026-10-06.)
- Q5: Landing order against 017? → B: Two waves. Wave 1, after PR 52 and independent of 017: FR-001, FR-002, FR-006, FR-007, FR-009, FR-011. Wave 2, after 017 merges: FR-003, FR-004, FR-005, FR-008, FR-010. (Supervisor, operator-directed.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A client and a server agree on one protocol version (Priority: P1)

A Codex Lead or a Worker client starts a server and sends `initialize` with the version it prefers. The server answers with that version only when it implements it, and otherwise with its own newest supported version. Results carry structured data where the negotiated version allows it.

**Why this priority**: an echoed version promises features the server does not have (F1). It is the cheapest fix and it unblocks every later protocol feature.

**Independent Test**: start each server over stdio, send `initialize` with a supported, an unsupported and a missing version, and check the reply.

**Acceptance Scenarios**:

1. **Given** the Worker server, **When** the client asks for an unsupported version such as `2099-01-01`, **Then** the reply names the server's newest supported version, never `2099-01-01`.
2. **Given** either server, **When** the client asks for a supported version, **Then** the reply names that same version.
3. **Given** a negotiated version that supports structured results, **When** a tool returns, **Then** the result holds the same JSON in `structuredContent` and in the text block, and the tool's `outputSchema` describes it.

### User Story 2 - A blocking call stays alive and can be stopped (Priority: P1)

While `ask_lead` or a broker `dispatch`, `resume` or `wait` blocks, the client can still `ping` the server, the server reports progress, and a `notifications/cancelled` for the blocked request ends the wait.

**Why this priority**: a silent 30-minute call can be killed by the client's idle limit (F8), and a client that cancels a call today gets no effect (F3).

**Independent Test**: a stand-in client starts a blocking call against a stand-in Worker, sends `ping` and then `notifications/cancelled`, and checks the replies and the timing.

**Acceptance Scenarios**:

1. **Given** a blocked `ask_lead`, **When** the client sends `ping`, **Then** the server replies within 1 s.
2. **Given** a blocked call whose request carried a progress token, **When** 30 s pass, **Then** the client has received at least one progress notification for that token.
3. **Given** a blocked broker `wait`, **When** the client cancels it, **Then** the server stops waiting, sends no result for that request, and the Worker turn keeps running.

### User Story 3 - The broker survives its own restart (Priority: P2)

The broker process restarts while results, questions and answers stay on disk. The Lead can still `wait`, `answer` and `resume` on the ids the earlier process issued.

**Why this priority**: today a restart orphans every earlier request (F5). Restarts are rare but the loss is total.

**Independent Test**: issue a request with one `Broker` object, drop it, build a new one on the same run dir, and call `wait`, `answer` and `resume`.

**Acceptance Scenarios**:

1. **Given** a finished request issued before a restart, **When** the Lead calls `wait` on it, **Then** the result returns, not `unknown-request`.
2. **Given** an id this run dir never issued, **When** the Lead calls `wait`, `answer` or `resume`, **Then** the broker refuses with `unknown-request`, as today.

### User Story 4 - The Lead reads a turn's state by a standard name and can stop a turn (Priority: P2)

Each broker result carries a task state with an A2A name beside the existing `status`. The Lead can also stop a running Worker and see the state `canceled`.

**Why this priority**: named states let a later A2A gateway or MCP Tasks migration map one to one (F2); cancel closes a D51 gap (F4).

**Independent Test**: drive a stand-in Worker through running, needs-lead, green, red and cancelled, and check each `task_state`.

**Acceptance Scenarios**:

1. **Given** a needs-lead reply, **Then** `task_state` is `input-required` and `status` is still `needs-lead`.
2. **Given** a cancelled turn, **Then** its result file holds `task_state` `canceled`, and the Worker process group no longer runs.

### Edge Cases

- A client sends `notifications/cancelled` for a request that has already returned: the server ignores it.
- A client sends `notifications/cancelled` for `ask_lead`: the wait ends, the question file stays, and the broker may still relay the question to the Lead. A late answer is written but never read by that call.
- Two `tools/call` requests arrive while one blocks: only the calls allowed by FR-003 run; every other call waits its turn, as today. Replies may arrive in a different order than the requests; JSON-RPC ids pair them.
- A progress notification is sent after its call has returned: never; the progress sender stops before the result is written to stdout.
- The client asks for a version newer than every supported one, or an empty version: the server answers with its newest supported version.
- A broker restarts while a Worker turn is running: the turn thread died with the old process (`Turn` uses a daemon thread, `dispatch.py:953`), so no result is written. The recovered id is known, `wait` on it returns `timeout` with `task_state` `working` although the turn is dead (recovering running turns is out of scope), and `resume` refuses it with `request-running` (`dispatch.py:1104-1105`). Recovering a running turn is not in scope; FR-007 covers finished turns and pending questions only.
- The Lead answers a question of a cancelled turn: `answer_question` writes the answer files as today (`dispatch.py:1062-1087`) and nothing reads them; no new refusal reason is added.
- A cancel writes no `events.jsonl` line: 017 fixes that file's kinds (017 FR-011), and 018 adds none.
- An environment value is present in a Worker question in base64 or percent-encoded form: it is redacted like the plain form (FR-011).

## Requirements *(mandatory)*

Invariants kept by every requirement below (D51, D54): the Lead stays credential-blind; the Worker sees only its channel tools; the 16 KiB question limit and the 64 KiB request and answer limit stay; redaction and the credential screen only grow, never shrink; files are opened with `O_NOFOLLOW` and new records with `O_EXCL`; the resume cap stays (1 Grunt, 2 above); incremental spend stays $0; `WORKERBEES_GOVERNANCE` stays default `off`; code stays standard library only; `worker_mcp.py` stays self-contained and never imports `agents_inc`.

### Functional Requirements

- **FR-001** (F1): Each server MUST hold a supported version set, and MUST answer `initialize` with the client's requested version only when that version is in the set, else with the newest version in the set. A missing or non-string version gets the newest version in the set. The set is `{2025-06-18, 2024-11-05}` (Q1 A), newest first; `2026-07-28` does not enter it in this feature (deferred, research.md R1). MCP rule relied on: "if the server supports the requested version it responds with the same version, otherwise with another version it supports" [assumed; primary source https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle not reachable, egress blocked 2026-10-06]. Acceptance: new tests `test_initialize_negotiates_version` in `tests/test_worker_mcp.py` and `tests/test_mcp_broker.py` send a supported, an unsupported (`2099-01-01`) and a missing version and assert the reply; `python3 -m unittest tests.test_worker_mcp tests.test_mcp_broker` passes.
- **FR-002** (F1): When the negotiated version supports structured tool results, each broker tool MUST declare an `outputSchema`, and each broker result MUST carry the same JSON object in `structuredContent` and as text in the first content block. With an older negotiated version, results stay as today. Worker server tools (`ask_lead`, and 017's `check_lead`) declare no `outputSchema` and keep plain text for the model. That structured results arrive with version `2025-06-18` [assumed; primary source https://modelcontextprotocol.io/specification/2025-06-18/changelog not reachable, egress blocked 2026-10-06]. Acceptance: new test `test_structured_result_matches_text` in `tests/test_mcp_broker.py` parses the text block and compares it to `structuredContent`, and validates the result keys against the declared `outputSchema` `required` list.
- **FR-003** (F3): While a blocking call runs, each server MUST keep reading stdin and MUST answer `ping` and handle notifications at once. During a blocking call the broker server MUST also serve `tools/call` for `status` (read-only), and the Worker server MUST serve no other tool call (Q3 A); every other call MUST wait until the blocking call returns, so 017's sequential handling of Lead calls (017 plan DD7) is kept. Every write to stdout MUST be one whole JSON line, never interleaved. Acceptance: new test `test_ping_answered_during_blocking_call` in `tests/test_worker_mcp.py` (blocked `ask_lead`) and in `tests/test_mcp_broker.py` (blocked `wait`) asserts a `ping` reply within 1 s; new test `test_stdout_lines_are_whole_json` asserts every stdout line parses.
- **FR-004** (F3): On `notifications/cancelled` naming an in-flight blocking call, the server MUST stop that wait within 1 s on the broker and in 017 socket mode on the Worker, and within `POLL_SEC` + 1 s (3 s) in Worker file mode, because the cancel wakes the 017 wait object directly (plan DD7); it MUST NOT send a result for that request id. Cancelling a broker wait MUST NOT stop the Worker turn (that is FR-010). Cancelling `ask_lead` MUST leave the question file in place. A cancel for an unknown or finished id MUST be ignored. MCP rule relied on: the receiver stops work and does not respond to the cancelled request [assumed; primary source https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/cancellation not reachable, egress blocked 2026-10-06]. Acceptance: new test `test_cancelled_notification_ends_wait` in `tests/test_worker_mcp.py` and `tests/test_mcp_broker.py`.
- **FR-005** (F3, F8): When a blocking call's request carries a progress token (`params._meta.progressToken`), the server MUST send a progress notification for that token at least every 30 s while it waits, with a progress value that grows each time, and MUST send none after the call's result. A progress message MUST hold no question, answer or push text and no environment value; its message is `waiting; elapsed=<s>` on the Worker server and `waiting; elapsed=<s>; task_state=<state>` on the broker. Without a token, the server sends none. Acceptance: new test `test_progress_while_blocked` in `tests/test_worker_mcp.py` and `tests/test_mcp_broker.py` with a fake clock asserts the count, the growth, the token and that no progress follows the result.
- **FR-006** (F8): Every client limit on a blocking call MUST exceed the server's own wait by a stated margin of at least 60 s. The Claude Worker's `worker_mcp.json` MUST set the per-server `timeout` field (milliseconds) to the same value as `runtime.MCP_TOOL_TIMEOUT_SEC` times 1000, so that Claude Code's stdio idle limit (1 800 000 ms in 2.1.290) no longer equals `WAIT_SEC`. The check MUST hold for Codex too: `WAIT_SEC` and `AWAIT_MAX_SEC` stay at least 60 s below `MCP_TOOL_TIMEOUT_SEC`. No key, token or environment value is added to the Worker environment. Acceptance: new test `test_client_timeouts_exceed_server_waits` in `tests/test_worker_mcp.py` reads the written `worker_mcp.json` and the constants and asserts both margins; the opt-in live test `tests/test_worker_mcp_live.py::test_claude_ask_lead_survives_idle_limit` (new, run by the operator on macOS with `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT` unset and a shortened `WAIT_SEC` stand-in) records that the Worker receives the no-answer text, not an abort.
- **FR-007** (F5): The set of request ids the broker issued MUST survive a broker restart. The broker MUST record each issued id in its own run dir (written with `O_EXCL` and `O_NOFOLLOW`, never through a Lead-writable path), and a new broker on the same run dir MUST treat recorded ids as issued. An id that is not recorded MUST still be refused with `unknown-request`. Resume caps, fan-out counts and `resume_of` MUST be read back from `run.json`, unchanged. Acceptance: new test `test_issued_ids_survive_restart` in `tests/test_mcp_broker.py` (wait, answer and resume after a new `Broker` on the same dir) and `test_unrecorded_id_still_refused`.
- **FR-008** (F2): Every broker result and needs-lead reply MUST carry a `task_state` field beside the unchanged `status` field, using A2A v1.0 task-state names: `working` (a call returned `timeout`), `input-required` (`needs-lead`), `completed` (`green`), `failed` (`red`), `rejected` (`refused`), `canceled` (FR-010 result, and a successful `cancel` reply). Every `refused` reason maps to `rejected`, except `not-running`, which, like an `answered` reply, carries no `task_state`. The field is additive and the names use lower-case hyphen form (Q4 A); the spellings are re-checked against the A2A primary spec before code (research.md R4); A2A names as listed are [assumed; secondary source https://www.glukhov.org/ai-systems/comparisons/a2a-protocol-2026-adoption/, cited by the Supervisor, not re-read; primary A2A spec not reachable from this container]. Existing `status` values MUST NOT change. Acceptance: new test `test_task_state_beside_status` in `tests/test_mcp_broker.py` drives a stand-in Worker through each state and asserts both fields.
- **FR-009** (F2, gated): Moving the broker or Worker server to the MCP Tasks extension (task-augmented `tools/call`, `tasks/get`, `tasks/result`, `tasks/cancel`) MUST NOT start until a live probe shows that the client in question (Codex CLI for the broker server; Claude Code and Codex CLI for the Worker server) sends task-augmented calls to a stdio server and accepts the server's task replies. The probe result, with client version and date, MUST be recorded in `research.md`. Until then the servers MUST NOT declare the `tasks` capability or set `execution.taskSupport`. Acceptance: new test `test_no_tasks_capability_declared` in `tests/test_worker_mcp.py` and `tests/test_mcp_broker.py` asserts the `initialize` capabilities and `tools/list` entries hold no `tasks` or `execution` keys; the probe is the opt-in live test `tests/test_mcp_broker_live.py::test_client_tasks_support_probe` (new), which only reads client behavior and records it.
- **FR-010** (F4; Q2 A, operator): The broker server MUST add a Lead tool `cancel {request_id}` that stops the running Worker turn named by an issued id: it ends the Worker's process group, writes the result with `status` `red`, `reason` `cancelled` and `task_state` `canceled`, and keeps the turn's `workers_spawned` and resume counts (a cancel never refunds fan-out). A cancel for an id that is not running MUST be refused with `not-running`. The Worker MUST NOT see a `cancel` tool. This amends D51 ("Parallel width, cancellation, and free-provider routing are later", `docs/DECISIONS.md:578`) and needs a new decision entry (FR-012). No FR-010 code may be written until that entry has operator sign-off and a cross-vendor (Codex) review. With Q3 A, `cancel` is not served during a blocking call: the Lead calls it between bounded calls (017 FR-016) or after cancelling its own wait (FR-004). Acceptance: new test `test_cancel_stops_running_worker` in `tests/test_mcp_broker.py` with a stand-in Worker that sleeps, asserting the result fields, that the process is gone within 5 s, and that counts are unchanged; `test_worker_never_sees_cancel` in `tests/test_worker_mcp.py`.
- **FR-011** (F9): Before a Worker question reaches the Lead, `screen_text` MUST also redact the base64 (standard and URL-safe), percent-encoded and hex forms of every environment value it already redacts. It MUST still redact every plain value it redacts today; redaction never narrows. Acceptance: new test `test_screen_text_redacts_encoded_forms` in `tests/test_dispatch_resume.py` plants each encoded form of a fake 20-character value in a question and asserts none survives, and that a plain value is still redacted.
- **FR-012** (canon): Edits to `docs/DECISIONS.md` (a decision recording the version set, the progress and cancel handling, and a D51 amendment for cancel, Q2 A), `CONTEXT.md` (a Task state term) and any `SKILL.md` or Worker prompt note MUST be reported as LESSON-CANDIDATE items for operator sign-off with a cross-vendor reviewer (D46). They MUST NOT be edited as a side effect of implementation. Acceptance: for each implementation commit in `<base>..HEAD` (`<base>` = the PR 52 merge commit for wave 1, the 017 merge commit for wave 2), `git show --name-only --format= <commit> -- docs/DECISIONS.md CONTEXT.md AGENTS.md 'skills/*/SKILL.md'` in `/home/user/agents_Inc` prints nothing. The CoS commit that lands the signed D51 amendment (plan Start gates) is not an implementation commit and is excluded; the implement report names its hash. The implement report lists each candidate.

### Key Entities

- **Supported version set**: the protocol versions one server implements in full; newest first.
- **Issued-id record**: one broker-owned file per issued request id in the run dir; its presence makes the id known after a restart.
- **Task state**: an A2A-named state beside `status` in each broker result.
- **Progress notice**: a message with a progress token, a growing progress value, elapsed seconds and the task state; never a message body.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of `initialize` tests, a server never answers with a version outside its supported set (FR-001).
- **SC-002**: During a blocked call, `ping` is answered within 1 s in 20 of 20 trials on each server (FR-003).
- **SC-003**: A cancelled blocked call stops within 1 s (broker; Worker in 017 socket mode) or within `POLL_SEC` + 1 s (Worker file mode) and gets no result line in 20 of 20 trials on each server (FR-004).
- **SC-004**: A blocked call with a progress token gets at least one progress notice per 30 s of waiting, and 0 after its result (FR-005).
- **SC-005**: For every client and server pair in the suite, the client limit on a blocking call exceeds the server wait by at least 60 s (FR-006).
- **SC-006**: After a broker restart, `wait` on each of 5 earlier ids returns its stored result, and 5 of 5 never-issued ids are refused (FR-007).
- **SC-007**: 100% of broker results in the suite carry a `task_state` that matches their `status` by the FR-008 table, and 0 existing `status` values change (FR-008).
- **SC-008**: 0 encoded forms of a planted value survive the question screen across the FR-011 test cases.
- **SC-009**: The existing D54 tests (`tests/test_worker_mcp.py`, `tests/test_mcp_broker.py`, `tests/test_dispatch_resume.py`) and, once landed, the 017 tests pass; their diff adds cases only, with one exception forced by FR-010: the exact broker tool-list assertions `tests/test_mcp_broker.py::test_initialize_and_tools_list` (`:96` at `fe37822`) and `tests/test_worker_mcp.py::test_needs_lead_answer_wait_resume` (`:293`), each updated to add `cancel` only (on top of 017's `push`). Tool entries gaining `outputSchema` (FR-002) change no asserted name list.

### Requirements checked by a named test or record, not a success criterion

- FR-002: `test_structured_result_matches_text`. FR-009: `test_no_tasks_capability_declared` and the probe record. FR-010: `test_cancel_stops_running_worker`. FR-012: the report list and the canon diff check.

## Overlap with 017

Spec 017 (`../017-worker-lead-socket/`, CoS-signed, implementation gated on agents_Inc PR 52) owns the socket doorbell, push, `check_lead`, `agents-inc tell`, `events.jsonl`, the 017 Lead call time limits and the Worker answer-path polling. 018 changes none of these and re-decides none of 017's clarifications.

| Shared code | 017 design | 018 position | Lands first |
|---|---|---|---|
| `worker_mcp.py` serve loop and threads (017 plan DD1, DD2) | Socket accept and reader threads; a `queue.Queue` of doorbell frames; stdin serving stays single-threaded; `ask_lead` waits on the queue in socket mode. | FR-003 adds a stdin reader so `ping`, cancel and progress work during `ask_lead`. It reuses 017's queue wait: a cancel or progress tick wakes the same wait, never a second wait loop. The socket, token and frames are untouched. | 017 |
| Broker `_await` (017 plan DD5) | Waits on `turn.link.event` instead of a 0.2 s sleep; file mode keeps the poll. | FR-004 and FR-005 wake the same event for cancel and progress ticks. | 017 |
| Lead call time limits (017 FR-016, plan DD7) | `dispatch`, `resume`, `wait` take an optional time limit and return `{"status":"timeout"}`; `push` is handled only between Lead calls, because the stdio loop is sequential. | 018 adds no rival time-limit parameter. FR-008 maps 017's `timeout` return to `task_state` `working`. FR-003 keeps every Lead call other than the Q3 set sequential, so 017's push ordering holds. | 017 |
| Tool lists asserted exactly (017 SC-006) | Worker: `ask_lead`, `check_lead`; broker adds `push`. | FR-002 adds `outputSchema` to entries; FR-010 adds `cancel` to the broker list only (the two exact-list assertions are updated per SC-009). Names in 017's lists are unchanged. | 017 |
| `turn-ended` push refusal (017 plan DD6) | Refused when the turn has a result. | A cancelled turn (FR-010) writes a result, so 017's existing rule refuses pushes to it; no new rule. | 017 |
| Cancellation, parallel turns (017 Out of Scope) | Deferred by D51. | 018 takes cancel (Q2 A, operator) as a D51 amendment; this does not re-open 017, which left it out. Parallel turns stay out (F7). | n/a |

Requirements with no 017 overlap (FR-001, FR-002, FR-006, FR-007, FR-009, FR-011) land in wave 1, after PR 52 and before or beside 017; FR-003, FR-004, FR-005, FR-008 and FR-010 land in wave 2, after 017 merges (Q5 B). Where wave 1 edits a `handle` function that 017 also edits, 017 rebases over wave 1 without changing its design.

## Assumptions

- 017 lands as planned (DD1 to DD12). If 017 changes its threading or `_await` design, 018's FR-003 to FR-005 are re-planned against the new design before code.
- agents_Inc moved from `1fcfd76` to `fe37822` (release prep). Cited lines still match [verified 2026-10-06]. The implementer re-checks them at the start gate.
- The Codex CLI client may send `ping`, progress tokens or `notifications/cancelled`, or may not [assumed]. The requirements are written so that a client that sends none sees today's behavior.
- Whether a progress notification extends Codex's `tool_timeout_sec` is unknown [assumed]; FR-006 does not rely on it.
- The Lead is a Codex model for the broker server (D51); Claude Leads use the file inbox or native tools and are not changed here.
- MCP and A2A facts tagged [assumed] above are re-checked against the primary specs in `research.md` before plan sign-off; network egress to the spec sites was blocked for this run.

## Out of Scope

- F6: remaining polling. The Worker answer path and broker wait are 017's (DD2, DD5). The file broker `dispatch --wait` 1 s poll and the file-mode fallback polls stay; they are the D51 fallback transport.
- File-broker (`dispatch --serve`) restart durability: FR-007 covers the MCP broker only, since F5 names `Broker.issued` (`mcp_broker.py:70`).
- F7: parallel Worker turns. D51 and D54 keep one turn at a time.
- F9 (part): split secrets (a value cut across two fragments) and over-redaction of paths under HOME. Narrowing redaction to spare HOME would weaken the D54 screen, so it is not taken.
- F10: sender identity on messages. Local filesystem isolation stands; 017's source tag covers pushes.
- F2 (part): any migration to MCP Tasks before the FR-009 probe passes.
- An A2A gateway (A2A as an outward interface); A2A as a transport.
- Everything 017 owns: socket, doorbell, push, `check_lead`, `agents-inc tell`, `events.jsonl`, Lead call time limits.
- Gemini, Mistral and OpenRouter transports, and the HTTP bridge (`bridge.py`).
- Code and tests (implement phase; this run is `--plan-only`).
