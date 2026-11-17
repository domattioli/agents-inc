<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-04 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Worker-Lead Socket Channel

**Feature Branch**: `development` (feature 017-worker-lead-socket; drafted under `.scratch/sock/spec/`; final spec home is DomI `specs/consumers/agents_Inc/`, per AGENTS.md)
**Created**: 2026-10-04
**Status**: Draft
**Input**: CoS dispatch of 2026-10-04: a Unix domain socket channel between a running Worker and its Lead, modeled on Claude Code's native per-session sockets (`/tmp/cc-socks/<pid>.sock`, push delivery, no polling). Operator direction 2026-10-04: if native Claude Code uses sockets to message agents, agents-inc should too.

## Terms used here

- **Worker**: a delegate model run that reports to a Lead (CONTEXT.md, D46).
- **Lead**: the model that owns the mandate and dispatches Workers through the broker (CONTEXT.md, D46).
- **Broker**: the agents-inc process that launches Workers for the Lead and screens all traffic between them (D51).
- **Run dir**: the broker-owned directory for one run; each Worker gets a child run dir under it (D51).
- **Request id**: the id the broker issues for one Worker turn, for example `mcp-<time>-<hex>`; a resume adds `-r<n>` (D54).
- **Turn**: one run of a Worker from prompt to report; no message reaches a Worker during a turn today (D54).
- **Channel**: the Worker's `ask/` directory, plus the small server (`worker_mcp.py`) that gives the Worker its tools. D54 has one tool, `ask_lead`; this feature adds `check_lead`.
- **Push**: a message from the Lead, the CoS or the operator, sent through the broker, that reaches a Worker while its turn runs, without the Worker asking first.
- **Doorbell**: a short socket notice (kind, request id, number) that tells the other side a D54 file is ready. It never carries a message body (FR-004).
- **Grunt, Workhorse**: rungs of the delegation ladder, Grunt the lowest (CONTEXT.md; `docs/governance/DELEGATION-MODEL.md`). The push cap depends on the Worker's rung (FR-008).
- **`run.json`**: the broker's record for one run dir, which holds its counters, such as `workers_spawned` and `resumes` (D51).

## Background (verified 2026-10-04 against commit `1fcfd76` on `development`, which carries D54)

- Today the channel uses files only. `ask_lead` writes `<rid>.question.<n>.json` and checks for `<rid>.answer.<n>.json` every 2 seconds, for up to 30 minutes (`agents_inc/install/worker_mcp.py:24-25`, `:92-98`).
- The broker checks for Worker questions and results every 0.2 seconds while a Lead call waits (`agents_inc/install/mcp_broker.py:73`, `:98-108`). The Lead sees a question as status `needs-lead` from `dispatch`, `resume` or `wait`, and replies with `answer`.
- The broker reads one Lead call at a time. A blocking `wait` holds the loop until it returns (`mcp_broker.py:264-283`) [inferred].
- D54 states the limit: "the Lead cannot push a message into a running Worker" (`docs/DECISIONS.md:597`). The Worker prompt says "The Lead cannot message you otherwise" (`agents_inc/install/dispatch.py:245-248`).
- D46 item 11 fixes the escalation path: Worker asks Lead, Lead asks CoS, CoS asks CEO (`docs/DECISIONS.md:503`). Item 10(d): a delegate sees only its slice.
- A broker Claude Worker runs under a sandbox profile that allows everything by default and then denies file writes outside a short list. The `ask/` channel is on that list (`dispatch.py:206`, `:222-223`, `:287`). The Worker cannot read or write the broker run dir (`dispatch.py:218-220`).
- Answers pass the D51 credential screen and the 64 KiB limit. Questions are cut to 16 KiB, and every environment value of 8 or more characters is redacted (`dispatch.py:1006-1012`, `:1068-1071`).
- The repository holds no reference to `cc-socks`, `events.jsonl` or issue 51 (grep of `*.md`, `*.py`, `*.sh`, `*.json`, 2026-10-04). Issue 51 was not read: this dispatch allows no network.

### The CoS position, tested

| Claim | Verdict |
|---|---|
| Ship D54 on files first; the socket layer comes after | Holds. D54 is accepted and its code is in the working tree. This spec builds on the D54 file layout and changes none of it. |
| Keep the file inbox as fallback and durable log | Holds. Files survive a restart; a socket does not (the known ENOENT hazard). Every socket message also lands as a D54 file. |
| The socket lets the Lead push into a running Worker | Holds only in part. A socket reaches the Worker's channel server, not the model. The model sees text only as a tool result or injected context. Resolved: a ruling that amends D54 allows push (Q1), and a `check_lead` tool delivers it (Q2). |
| Native Claude Code sessions can message a delegate | Resolved: only through the broker, which screens the note and tags its source (Q3). The native wire protocol is not used. |
| Shares an event stream with issue 51 | Resolved: one metadata-only `events.jsonl` per Worker child run, in a fixed line format (Q7). |

## Clarifications

### Session 2026-10-04

The CoS answered, holding the clarify gate by operator ruling of 2026-10-04 while the operator was away.

- Q1: May the Lead push into a running Worker? → A: Yes, by a new decision that amends D54. A push passes the answer screen and lands as a file. The cap is 2 pushes per turn for a Grunt Worker and 5 for Workhorse and above. Pushes are counted, never as Workers or resumes.
- Q2: How does a push reach the Worker model? → A: A second Worker tool, `check_lead`, returns pending pushes. Every `ask_lead` result also carries pending pushes. The Worker prompt tells the Worker to call `check_lead` between major steps. The rule is the same for both vendors.
- Q3: May a native Claude Code session message a delegate? → B: Only through the broker. A new `agents-inc tell` command hands the note to the broker, which screens it, counts it, and sends it as a push. Each push carries a source tag that names the caller: `cos`, `lead` or `operator`. Reason: the operator asked twice on 2026-10-04 that sibling sessions reach delegates. The broker-only path keeps the D51 screen and the D46 chain.
- Q4: How does the channel server check its peer? → A: A same-user peer check, plus a per-turn token that the broker writes to a mode-0600 file. The token never goes in argv, a prompt or a log. An unsandboxed process of the same user can still read the token file.
- Q5: Where does the socket file live? → A: In the Worker's `ask/` dir, under a short relative name, so the length of the full path does not matter. If the bind fails, files are used.
- Q6: How far does the fallback reach? → A: For the rest of the turn. The result records the reason.
- Q7: What is the link to issue 51? → B: Each message also becomes one line in the Worker's `events.jsonl`. Issue 51 is the operator's tmux viewer, `agents-inc cuck`, which tees child stdout into the same file. A line is one JSON object with the fields `ts`, `rid`, `dir` (`to-worker` or `to-lead`), `kind` (`ask`, `answer`, `push` or `event`), `n` and `bytes`. A line never holds the body of a message, only its byte count, so the file is safe to tail.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Worker question reaches the Lead, and the answer comes back, without polling (Priority: P1)

A Worker calls `ask_lead`. The question reaches the broker at once, the Lead's blocked call returns `needs-lead`, and the Lead answers. The answer reaches the waiting `ask_lead` at once, not on the next 2-second check. The D54 files are still written, so the record is unchanged.

**Why this priority**: This is the smallest slice that proves the socket path on both vendors. It changes no policy, because D54 already allows questions.

**Independent Test**: Start the channel server and a broker stand-in in a temp dir under a fake HOME. Ask one question and answer it. Assert the answer returns faster than one poll interval. Assert the question and answer files match the socket messages byte for byte. Assert the server read each answer file once, after its doorbell, and never while it waited.

**Acceptance Scenarios**:

1. **Given** a running Worker turn with a healthy socket, **When** the Worker asks and the Lead answers, **Then** `ask_lead` returns the answer within the latency target, and the D54 question and answer files exist.
2. **Given** the same setup, **When** the answer fails the credential screen or the size limit, **Then** the broker refuses it with the same reason as D54, and nothing reaches the Worker.
3. **Given** a Codex Worker and a Claude Worker, **When** each asks one question in a live proof, **Then** both use the socket path, or the result records why one used files.

---

### User Story 2 - Losing the socket never loses a message (Priority: P1)

The socket file vanishes, refuses connections, or dies mid-message. This can happen after a restart, a resume, or a crash. The channel falls back to the D54 file path, and every question and answer still arrives exactly once.

**Why this priority**: The known hazard is real: a native peer address returned ENOENT today. A faster channel that drops answers is worse than the current one.

**Independent Test**: Run fault cases: socket file removed, stale socket file with no listener, listener killed after the question is sent, a broker restart, and a full path over 104 bytes. Assert each question and answer arrives once, through files where needed. Assert the turn's result records the transport it used.

**Acceptance Scenarios**:

1. **Given** a stale socket file from an earlier turn, **When** a resume turn starts, **Then** the new channel server replaces it and the broker connects to the new one.
2. **Given** the socket fails after the question file is written, **When** the Lead answers, **Then** the Worker receives the answer through the file path within the D54 wait limit.
3. **Given** the full socket path would exceed the platform limit for socket addresses, **When** the channel starts, **Then** it still binds by its short relative name in `ask/`, or it uses files and records why.

---

### User Story 3 - The Lead tells a running Worker something (Priority: P2)

The Lead learns, for example from a second Worker's report, that the running Worker's premise is wrong. The Lead sends a short note. The Worker receives it while its turn still runs, and the Worker does not need to ask first.

**Why this priority**: This is the new capability the operator asked for. It depends on a ruling that amends D54, so it ships after Stories 1 and 2.

**Independent Test**: With a stand-in Worker, the Lead sends a push. Assert it passes the same screen as an answer, counts toward the per-turn cap, and lands as a file. Assert the next `check_lead` or `ask_lead` result carries it.

**Acceptance Scenarios**:

1. **Given** a running Worker, **When** the Lead pushes a note, **Then** the next `check_lead` or `ask_lead` result carries the note with its source tag `lead`, and `run.json` counts it as sent and then delivered.
2. **Given** the socket has failed for this turn, **When** the Lead pushes, **Then** `check_lead` still finds the note in the push file, because `check_lead` reads files when it is called and needs no polling.
3. **Given** a Worker whose turn has ended, **When** the Lead pushes, **Then** the broker refuses with a reason and points to `resume`.
4. **Given** a push over the cap of 2 (Grunt) or 5 (Workhorse and above), over 64 KiB, or with credential-seeking text, **When** sent, **Then** the broker refuses it, and nothing reaches the Worker.

---

### User Story 4 - An operator session reaches a delegate (Priority: P3)

The CoS, or another native Claude Code session of the operator, sends a note to a running delegate. It does not wait for the Lead to relay it.

**Why this priority**: The operator asked for it twice on 2026-10-04. It reuses the push path of Story 3, so it comes after it. Routing through the broker keeps the D51 screen and the D46 chain.

**Independent Test**: Run `agents-inc tell` against a temp run dir with a stand-in Worker. Assert that the note arrives as a push tagged `cos` or `operator`, under the same screen and cap as a Lead push. Assert that a direct connection to the Worker socket without the token is refused.

**Acceptance Scenarios**:

1. **Given** a running Worker, **When** the CoS runs `agents-inc tell` with source `cos`, **Then** the broker screens and counts the note, and the Worker's next `check_lead` result shows it tagged `cos`.
2. **Given** a process of the same user that is not the broker, **When** it connects straight to a Worker socket, **Then** the channel server refuses it, because it lacks the per-turn token.
3. **Given** a source tag other than `cos` or `operator` (including `lead`, which only the Lead's own push path sets), **When** `agents-inc tell` runs, **Then** it exits with a usage error, and nothing is sent.

---

### User Story 5 - One event record for a Worker turn (Priority: P3)

Each message adds one metadata line to the Worker's `events.jsonl`. The operator's tmux viewer (issue 51, `agents-inc cuck`) tees the Worker's stdout into the same file. A reader can see what the Worker was told and when, without seeing any message body.

**Why this priority**: It helps audits and live watching. The record of truth stays the D54 files, so this story is additive.

**Independent Test**: Run one question, one answer and one push. Read `events.jsonl`. Assert three lines in time order, each with exactly the fields `ts`, `rid`, `dir`, `kind`, `n` and `bytes`. Assert that no line contains any message text.

**Acceptance Scenarios**:

1. **Given** a turn with one question, one answer and one push, **When** the file is read, **Then** the lines show `to-lead`/`ask`, `to-worker`/`answer` and `to-worker`/`push`, in order, and each `bytes` value equals the UTF-8 length of that message's screened text (FR-011).
2. **Given** a push whose body contains a distinctive string, **When** the file is searched for that string, **Then** there is no match.

### Edge Cases

- The socket file exists, but no process listens (a stale file after a crash or a session restart): the server treats ENOENT and connection refused as "no socket" and uses files. It never blocks on them.
- A resume turn starts a new channel server process: the socket address must not depend on a process id, or the broker cannot find it after a resume.
- The channel dir path can exceed the macOS socket address limit of 104 bytes. Run dirs under a repository path come close to it [inferred].
- The broker reads one Lead call at a time [inferred from `mcp_broker.py:264-283`]. A Lead push cannot be accepted while the Lead's own `dispatch`, `resume` or `wait` blocks, so the Lead gives those calls a time limit and pushes between them (FR-016). A `tell` from another session does not wait for the Lead's call to end (FR-016, SC-009).
- The Lead's process dies, and the broker with it: the Worker's `ask_lead` keeps the D54 30-minute limit, then returns the D54 no-answer text.
- A push arrives after the Worker's last tool call: it may never reach the model. The result must record pushes that were sent but not delivered.
- The Worker can already write files in its own `ask/` dir, so it could forge an answer to itself. The socket must not widen this: no socket message may reach the Lead without the broker's screen.
- A Codex Worker: whether Codex starts its MCP servers inside a sandbox that blocks socket calls is unknown. A live proof decides. If they are blocked, Codex Workers use files.
- Two Workers at once: D54 runs one Worker turn at a time, so one socket is live per broker. This feature must not assume more.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The D54 files MUST stay the record of truth. Every question, answer and push MUST be written as a file in the D54 layout before it is sent over the socket. A reader that ignores sockets MUST see the same conversation.
- **FR-002**: The Worker's channel server MUST own one listening socket per turn. The broker MUST be the only connecting peer that it serves. The Worker MUST see exactly two tools, `ask_lead` and `check_lead`, and never dispatch, status, wait, resume, answer or push.
- **FR-003**: When the socket is healthy, a question MUST reach the broker, and an answer MUST reach the waiting `ask_lead`, without any wait for a poll interval. The broker MUST return `needs-lead` to a blocked Lead call as soon as the question arrives.
- **FR-004**: The socket MUST carry only doorbells: short notices of at most 4 KiB that name a message (its kind, request id and number), never a message body. Every body MUST pass the same checks as its D54 file form before its file is written: the 16 KiB question limit with redaction, and the credential screen and 64 KiB limit for answers and pushes. Refusal reasons MUST match D54. A notice for a body that failed its check MUST NOT be sent.
- **FR-005**: Any socket failure (ENOENT, connection refused, a broken pipe, a peer that closes mid-message, a bind refused by the sandbox) MUST fall back to the D54 file path. No message may be lost or delivered twice. After the first failure, the channel server and the broker MUST both use files for the rest of the turn. A new turn, such as a resume, tries the socket again. If the broker dies, `ask_lead` MUST keep the D54 30-minute limit and then return the D54 no-answer text.
- **FR-006**: The socket MUST live in the Worker's `ask/` dir under one short, fixed name, bound and reached by a relative name, so that the length of the full path does not matter. The name MUST NOT depend on a process id, so that a resume turn or a restarted server is found at the same place. At start, the server MUST replace a stale socket file that has no listener. If the bind fails, the turn uses files.
- **FR-007**: The server MUST refuse every peer that is not the same OS user. It MUST also refuse a peer whose first message does not carry the per-turn token. The broker writes the token, new for each turn, to a mode-0600 file that the server may read. The token MUST NOT appear in argv, a prompt, a log, `run.json` or `events.jsonl`.
- **FR-008**: The Lead MAY push a note into a running Worker. A push MUST pass the same screen as an answer: the credential check and the 64 KiB limit. The cap is 2 pushes per turn for a Grunt Worker and 5 for Workhorse and above, shared by all sources. Past the cap, the broker refuses with `push-cap`. A push to a turn that has ended is refused with `turn-ended`. This amends the D54 limit and needs a new decision entry (FR-015).
- **FR-009**: The Worker model MUST receive pushes through its own tool calls, by the same rule for both vendors. `check_lead` returns every pending push at once and never waits. Every `ask_lead` result also carries the pushes that are pending when it returns. The Worker prompt MUST tell the Worker to call `check_lead` between major steps. A push counts as delivered when a tool result has carried it.
- **FR-010**: A session that is not the broker MUST reach a Worker only through the broker. A new command, `agents-inc tell`, MUST hand a note to the broker of a named run dir for a named request id. The broker screens it, counts it under the FR-008 cap, and sends it as a push. Every push MUST carry a source tag, one of `cos`, `lead` or `operator`. `agents-inc tell` MUST accept only `cos` or `operator`; the tag `lead` comes only from the Lead's own push path (the broker `push` tool or a file-inbox push). The Worker sees the tag. The tag names the caller as the caller declares it; the broker cannot prove it. The native Claude Code socket protocol MUST NOT be used.
- **FR-011**: The broker MUST append one line to the Worker child run's `events.jsonl` for each question, answer and push. A line is one JSON object with exactly these fields: `ts`, `rid`, `dir` (`to-worker` or `to-lead`), `kind` (`ask`, `answer`, `push` or `event`), `n` and `bytes`. `bytes` is the UTF-8 length of the message text after the broker's screen: for an `ask`, the cut and redacted copy the Lead sees; for an `answer` or a `push`, the text the Worker reads. A line MUST NOT contain a message body, a source tag or a token. The kind `event` is reserved for issue 51's tee of Worker stdout. Each line MUST be written in one append, so that lines from the two writers never mix.
- **FR-012**: Each Worker result MUST record the transport used for each message (`socket` or `file`), and the reason for each fallback. `run.json` MUST count pushes sent and refused, by source, and pushes delivered, as one total per request id (advisory, read from the Worker's delivery markers at turn end). Pushes MUST NOT count toward `workers_spawned` or `resumes`.
- **FR-013**: The socket MUST be a local Unix domain socket only. No TCP listener and no network path. The channel server MUST stay standard library only and self-contained, because the broker copies it into the child run dir (`worker_mcp.py:3-7`).
- **FR-014**: The feature MUST NOT widen what a sandboxed Lead or Worker can read or write. The Lead MUST NOT gain any path into the child run dir. The Worker MUST NOT gain any path into the broker run dir.
- **FR-015**: Edits to `docs/DECISIONS.md` (a new decision that amends D54), `CONTEXT.md` (new rows Push, Channel and Doorbell; amended rows Turn and Dispatch broker; plan.md "Agent context update") and the Worker prompt note MUST be listed as LESSON-CANDIDATE items for sign-off. They MUST NOT be edited as a side effect of implementation.
- **FR-016**: The Lead's broker MUST let the Lead push while a Worker turn runs. Every Lead call that waits on a Worker (`dispatch`, `resume` and `wait`) MUST accept an optional time limit and return when it runs out, so the Lead can push between bounded calls. `agents-inc tell` MUST reach the broker even while a Lead call blocks, because the broker serves it apart from the Lead's calls.

### Key Entities

- **Channel socket**: one listening endpoint per Worker turn, owned by the channel server, with the broker as its only served peer.
- **Message**: a question (Worker to Lead), an answer (Lead to Worker, tied to one question number) or a push (to the Worker, not tied to a question, with a source tag `cos`, `lead` or `operator`). Each message has a request id, a number, a time and a transport.
- **Durable log**: the D54 files in the child `ask/` dir and the broker run dir. They are written first and read by any fallback.
- **Event line**: one metadata-only line in the Worker's `events.jsonl` (`ts`, `rid`, `dir`, `kind`, `n`, `bytes`). It is shared with issue 51 and is safe to tail.
- **Turn token**: a per-turn secret in a mode-0600 file. The channel server uses it to tell the broker from other processes of the same user.
- **Transport record**: the per-message transport and the fallback reason, stored in the turn result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a healthy socket, the time from the Lead's `answer` call to the return of `ask_lead` is under 0.5 s in 20 of 20 local trials. Today this time can reach 2 s or more, because of the 2 s check interval.
- **SC-002**: In the 5 fault kinds of Story 2 (socket file removed, stale file with no listener, listener killed after the question, broker restart, full path over 104 bytes), 5 runs each, 100% of questions and answers arrive exactly once, and 0 are lost.
- **SC-003**: For 100% of socket messages in the test suite, a D54 file with the same content exists.
- **SC-004**: While the socket is healthy, the channel server reads each answer file exactly once, after its `answer` doorbell, and makes 0 reads while it waits. The test counts reads with a patched `Channel._read_answer` (T011).
- **SC-005**: A connection from a peer that is not the broker is refused in 100% of test cases. In the live probe (T038), each direction (Lead to the child run dir, Worker to the broker run dir) is probed once per vendor, 4 probes in all, and all 4 are refused.
- **SC-006**: The existing D54 tests (`tests/test_worker_mcp.py`, `tests/test_mcp_broker.py`, `tests/test_dispatch_resume.py`) pass. Their diff adds new cases only, with three exceptions in `tests/test_worker_mcp.py` that FR-002 and FR-016 force, each updated to the new exact list and nothing else: the Worker tool list (`test_only_ask_lead_is_exposed`), the Claude `--allowedTools` value (`test_claude_worker_gets_ask_lead_server_and_sandbox_holes`) and the broker tool list (`test_needs_lead_answer_wait_resume`). `tests/test_dispatch_resume.py` passes with no edit.
- **SC-007**: The opt-in live test in `tests/test_worker_mcp_live.py` (T031) pushes a note holding a random nonce to one Claude Worker and one Codex Worker, each told to repeat any Lead note in its report. It passes only if, for each vendor, the Worker's report contains the nonce and `ask/<rid>.push.1.seen` exists. For the Claude Worker, the transport record MUST read `socket`. For the Codex Worker it may read `file`, but only with a non-empty `fallback_reason`.
- **SC-008**: Across the test suite, 0 lines of `events.jsonl` contain a message body or a token, and 100% of lines have exactly the six FR-011 fields.
- **SC-009**: `agents-inc tell` delivers a tagged note to a stand-in Worker while a Lead `wait` call blocks, in 5 of 5 trials.
- **SC-010**: A push sent after the stand-in Worker's last tool call shows in `run.json` as 1 sent and 0 delivered, and its D54 push file exists, in 5 of 5 trials (T049).
- **SC-011**: Across the test suite, the per-turn token value appears in 0 of: `events.jsonl`, the broker log, `ask/<rid>.transport.json`, `run.json`, the request result, the Worker argv and the Worker prompt (T005, T039).

### Requirements checked by a named test task, not a success criterion

- FR-002 (exactly two Worker tools): T024, with the exact-list assertions of SC-006.
- FR-004 (doorbells only; same screen as D54): T012 and T025.
- FR-008 (cap and refusal reasons): T025 and T032.
- FR-013 (Unix socket only; standard library only): T011.
- FR-015 (canon as report items): T044 to T048, report items with no test.

Every other FR maps to an SC: FR-001 SC-003; FR-003 SC-001, SC-004; FR-005 SC-002; FR-006 SC-002; FR-007 SC-005, SC-011; FR-009 SC-007; FR-010 SC-009; FR-011 SC-008; FR-012 SC-010; FR-014 SC-005; FR-016 SC-009.

## Assumptions

- D54 is on `development` at commit `1fcfd76`. PR 52 (`development` to `main`) is open. Work on 017 starts only after PR 52 merges (CoS ruling, 2026-10-04). The plan's line citations are re-checked against `1fcfd76`.
- The source tag is declared by the caller. Any process of the same user can run `agents-inc tell` with any tag. The tag records intent; it does not prove who sent the note [inferred].
- The channel server owns the listening socket, and the broker connects to it. The Worker sandbox denies the broker run dir (`dispatch.py:218-220`), so a broker-owned socket there would be out of the Worker's reach [inferred].
- The Claude Worker sandbox allows socket calls by default, and binding inside the writable `ask/` dir is expected to work. A live proof confirms this [inferred from `dispatch.py:222-223`].
- Whether Codex sandboxes its MCP server processes is unknown [assumed]. A live proof decides, and FR-005 covers the failure.
- macOS is the target platform, because the Claude Worker sandbox is `sandbox-exec`. Linux behaviour is not in scope.
- This feature copies the shape of Claude Code's native sockets (one per session, push delivery). It does not copy their wire protocol, which is undocumented [assumed].
- D54 keeps one Worker turn at a time, so one Worker socket is live per broker.

## Out of Scope

- Code and tests for this feature (implement phase, after PR 52 merges).
- Replacing the file inbox or the D54 file layout.
- Gemini, Mistral and OpenRouter transports. These providers have no tools and no channel server.
- The HTTP bridge (`bridge.py`).
- Parallel Worker turns, cancellation and free-provider routing (deferred by D51).
- The tee of child stdout to `events.jsonl` (issue 51) itself, and the tmux viewer. This feature defines the shared line format and writes only the message lines.
- A Claude-only hook that injects pushes, and interrupt-and-resume delivery (rejected in Q2).
- The native Claude Code socket protocol (rejected in Q3).
