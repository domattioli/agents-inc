# Pane Board research

Repository code and type declarations describe the available integration points. Live behavior identified below remains [unverified]. Each spike should record the host build, surface, observable result, and which implementation path the result supports.

## Mechanical Board

### S3 — Operator hold versus idle

**Decision.** Probe an operator approval, an operator input hold, an idle delegate, and a delegate waiting on background work. Compare status, any actionable question or approval payload, and how the signal clears. Classify NEEDS YOU only when a positive host signal identifies an operator hold. Read a quota pause separately from governed dispatch state and carry the reset time when supplied. The operator-hold signal and quota reset visibility are [unverified].

**Rationale.** The host declarations distinguish `waiting` from `idle` and list several kinds of `waiting`. A Worker's Question belongs to its Lead.

**Operator rulings, 2026-11-20 (grill).**
- A positive signal is a host event or payload that carries the question or approval text. A bare status is not enough, because golden scene 3 prints the question.
- If the spike ends with no such signal, FR-014's first case (agent held for operator input or approval) is deferred. Phase 1 ships only the quota-pause case, and a held agent reaches NEEDS YOU through a CoS marker. No status guess and no transcript-tail scan.
- The deferral takes effect only after the two missing cases have run with no signal: a plan-mode approval and a real tool-permission prompt, each left unanswered for 30 seconds. Evidence so far (47 log lines, 2026-11-20): one `waiting` case, a background `sleep`; finished turns read `completed`, never `idle`; `classic.SubagentStop` fires; no `classic.PermissionRequest` line.
- If the host signals one kind of hold and not another, Phase 1 ships the signalled kind and the spec lists which kinds are covered.
- A `waiting` agent with no positive signal stays in WORKING with its step reading `waiting`.
- On deferral, FR-014, the S3 assumption in the spec and golden scene 3 must be amended before T007 starts.

**Alternatives.** Mapping all `waiting` values to NEEDS YOU would include background waits. Guessing from transcript language would confuse operator holds with ordinary questions. If the spike finds no reliable signal, record the limitation for Phase 1 and leave unsupported waits unclassified.

Sources: `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:558`–`:566`, `spec.md:142`, `spec.md:202`, `docs/DECISIONS.md:596`–`:599`.

### S4 — Current step and refresh cadence

**Decision.** Reuse the coordinated collection path. Probe deterministic action summaries from native tool events, with a sampled transcript read as a candidate fallback. For dispatch, use the observed run events where available. Cache the latest short action and fall back to a state note such as `quiet 3m`. Measure reads and update delay as the delegate moves from active to quiet. Live access and cadence are [unverified].

**Rationale.** The existing poll already collects native and dispatch state. The native loop calls `$.session.messages` and has a path that checks for an array. The declarations allow a denial for another process or unavailable transcript. Those cases need a state note rather than an inferred action.

**Alternatives.** Polling full transcripts on every render duplicates reads. Summarizing with a model conflicts with FR-020. A tool-event-only path is suitable if the spike demonstrates coverage across the supported sources.

Sources: `mods/delegate-pane/hooks/poll.ts:248`–`:254`, `mods/agents-inc/hooks/native/loop.ts:929`–`:932`, `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:11838`–`:11873`, `spec.md:148`, `spec.md:203`.

### S6 — Key focus and automatic opening

**Decision.** Use Board selection keys only while Board owns focus. Probe a non-empty chat draft, keyboard movement in each surface, manual reopening, Escape, and the automatic first-event opening without focus. Test both a wide and a narrow terminal. Live focus and automatic placement are [unverified].

**Rationale.** The host declares pane focus events and width-dependent placement for unasked opens. A successful open request alone cannot establish that Board appeared or preserved the draft.

**Alternatives.** Global key interception can hijack the prompt. A slash-command-only flow is available for reopening and would leave the first-event requirement unmet. If placement fails below the host threshold, document the affected surface and width for Phase 1.

Sources: `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:2515`–`:2536`, `:4180`–`:4191`, `:7605`–`:7625`, `spec.md:150`, `spec.md:163`, `spec.md:205`.

## CoS Items

### Main-loop turn completion and marker handling

**Decision.** Read `answer` on `turn.complete` for successful main-loop turns and deduplicate by session, turn ID, and source line. Probe that the answer matches the final visible text, carries a stable identity, and can be processed without changing native delegate hand-back [unverified]. Match complete marker lines. The grammar accepts only `needs-you`, `fyi` and `done` from chat. `needs-you` and `fyi` become Items. `[board:done] <same text as the Item title>` closes the matching NEEDS YOU Item through the same chat-marker path, with zero extra model calls (ruled 2026-11-19). `[board:trouble]` and `[board:working]` are ignored silently, because those states are mechanical. The whole marker text is the title on one line; there is no context field, and the sub-pane shows the full source chat turn as context.

**Rationale.** The declarations expose the final visible answer, turn ID, loop ID and completion reason. The existing native hook calls `next(e)` and handles only its managed agent IDs. The operator ruled on 2026-11-19 that three marker names are accepted from chat, that the title is the whole marker text, and that closure uses the done marker.

**Alternatives.** A posting tool call adds the round trip FR-013 excludes. Reading every assistant message from the transcript can include prior turns and intermediate text. Rendering CoS `trouble` and `working` markers as rows would give chat text control of mechanical state. Inferring a context boundary from punctuation could split the title wrongly. Closing by exact title match is accepted by ruling; an inexact title closes nothing.

Sources: `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:14188`–`:14227`, `:14238`–`:14250`, `mods/agents-inc/hooks/native/loop.ts:741`–`:765`, `spec.md:134`–`:141`, `spec.md:143`, `spec.md:146`–`:153`, `spec.md:171`, `spec.md:181`, `spec.md:206`.

### S5 — Reply region and the local chat path

**Decision.** Try an inline region below Board first and a separate reply pane if the inline layout cannot close on Escape and return focus reliably. Confirm input focus, last sent messages, and keyboard handling on the host [unverified]. For a reply to the current CoS, prefer an operator-confirmed chat submission. `prompt.fill` is a draft mechanism [unverified live]. Confirm a reliable way to associate final submission with the Item, and keep the Item open on draft, cancellation, or refusal.

**Rationale.** The host declarations describe both pane opening and Escape behavior. They describe `prompt.fill` as content the person edits or submits. The specification asks for a reply made by the operator and requires an answer before the Item leaves.

**Alternatives.** A separate pane may provide better focus behavior at the cost of layout control. Sending directly through `session.send` uses a plugin origin. Treating draft insertion as a reply would close Items before the operator submits them. Cross-session CoS replies wait for S2.

Sources: `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:2515`–`:2536`, `:7605`–`:7625`, `:9005`–`:9017`, `:12197`–`:12205`, `spec.md:63`–`:75`, `spec.md:201`, `spec.md:204`.

## Teams across sessions

### S1 — Shared state and session ownership

**Decision.** Probe two independent Claude processes for plugin store visibility, concurrent writes, restart and stale-session behavior. Test a session-owned, atomically replaced summary file if the store is unsuitable. Confirm how each local harness supplies explicit session, delegate, and Sync ownership [unverified], including two Teams in the same checkout. Share only the Board data each pane needs.

**Rationale.** The declared plugin store is JSON kept between sessions, with a size bound. That documents persistence, while concurrent visibility and consistency require measurement. The old pane's timestamp rule can count one run in more than one Team. D63 accepts the Team definition and describes a proposed pointer path.

**Alternatives.** Session-local state alone cannot give every pane the same Teams. Copying all transcripts into a shared file increases storage and data exposure. Reuse an existing pointer registry only if the ownership data and supported discovery path are confirmed.

Sources: `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:3433`–`:3463`, `mods/delegate-pane/README.md:69`–`:74`, `docs/DECISIONS.md:666`, `docs/DECISIONS.md:682`, `spec.md:129`, `spec.md:200`.

### S2 — Cross-session message provenance and Worker Memos

**Decision.** Send from a deliberate operator action and preserve the host's plugin provenance. Probe a live and an idle recipient by stable ID. Compare sender acknowledgement, the receiving envelope, and what the receiving session does with the message [unverified]. Treat queue acceptance and reading as separate observations. After the D54/D46 amendment lands, test delivery to native Claude Workers at a checkpoint [unverified] and Codex Workers on the next governed resume [unverified on the target build]. Keep a pending Memo visible until consumption is observable. Verify the recipient Chief's FYI for another Team's delegate.

**Rationale.** `session.send` declares an engine-stamped plugin origin and a result for queueing. D54 currently permits the Worker to ask its Lead and otherwise bars pushes to a running Worker. The spec accepts a one-way Memo exception that must be recorded before Phase 3. D63 records an earlier Codex probe in which the message appeared on resume.

**Alternatives.** Drafting with `prompt.fill` supports operator confirmation in the current chat and cannot establish remote delivery. Labeling a plugin envelope as a native operator message would misstate its origin. Direct injection into an active Worker bypasses the checkpoint and the D54 path. If the host cannot carry the operator's reply with its provenance intact, report the unmet Phase 3 behavior.

Sources: `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:12170`–`:12249`, `docs/DECISIONS.md:502`–`:503`, `docs/DECISIONS.md:590`–`:599`, `docs/DECISIONS.md:664`, `spec.md:92`–`:93`, `spec.md:175`, `spec.md:201`.

## Secretary and FR-046

**Decision.** Run the Phase 4 extraction bench before enabling the Secretary. Use a fixed set of CoS turns with expected Items and cases with no Items, then record accuracy, false positives, latency, and cost. Confirm the acceptance threshold before enabling a backend. Validate shape and literal quote containment in code. Keep a model-agnostic local route and an explicit none option. For a free API, confirm current limits, eligible use, and data use before any workspace grant. Mistral's free-tier limits and the third-party training opt-in claim are [unverified]. Resolve them using authoritative current evidence before granting that route. A missing or inconclusive check keeps the route ungranted. FR-046 and the extraction bench apply in Phase 4 only.

**Rationale.** The spec limits extraction to unmarked turns, requires verbatim evidence and a failure line, and leaves the Mistral limits question open. The constitution preserves the zero incremental spend cap.

**Alternatives.** Use the local route or none when no free route qualifies. A paid fallback conflicts with P5. Deploying an unchecked extractor would permit unsupported Items. Running extraction on marked turns or mechanical rows would expand its scope beyond that defined in the spec.

Sources: `spec.md:97`–`:110`, `spec.md:135`–`:141`, `spec.md:174`, `.specify/memory/constitution.md:38`–`:40`.

## Spike results, 2026-11-20

Run by the supervisor in a scratch Claude Code session (v2.1.329, tmux-driven, probe mod `mods/board-spike-probe`, default permission mode). Raw logs: `.scratch/board-spike/probe.jsonl` and the scratch run copy. Host behavior observed once per case; treat as single observations, not guarantees.

### S3 results

- A plan approval in the main session fires `classic.PermissionRequest` (`tool_name: ExitPlanMode`, `tool_input.plan` with the plan text, `permission_mode: plan`) and, 12 seconds later, `classic.Notification` (`message: "Claude Code needs your approval for the plan"`, `notification_type: permission_prompt`). No `agent_id` appears because the hold was in the main session.
- A tool-permission hold in a background subagent (WebFetch, default mode) fires `classic.PermissionRequest` with `agent_id`, `agent_type`, `tool_name` and `tool_input` (the URL and prompt), then `classic.Notification` with the generic text "Claude needs your permission" and no agent id. This meets the grill's bar: an event carrying the question text and the agent identity.
- During that hold the agent's status stayed `running`. It never showed `waiting`. A `$.agent.list` status alone therefore cannot identify a tool-permission hold. The background-work wait (`sleep 90`) did show `waiting`.
- The hold clears silently. After a deny, the log shows only `classic.SubagentStop` and status `completed`. No event says "permission resolved". The Board must clear a held row when the agent's status changes or the agent stops.
- A tool call the sandbox blocks never reaches a permission prompt. The `touch /tmp/board-probe-x` subagent failed with "Operation not permitted" and logged no hold.
- Decision effect: the operator-hold case is supported through `classic.PermissionRequest` (permission holds, plan approvals) and not through status. Per the grill rulings, Phase 1 ships these kinds and the spec lists them.

### S4 results

- `$.session.messages({agentId, as:'api'})` works for a running agent, about 5 seconds apart. During the WebFetch hold the last message was the agent's pending `tool_use` (WebFetch), so the current step is readable from the transcript tail. No read was denied.
- Not measured: delay from a tool call to the first changed read, and cadence under steady tool use beyond one 5-second sample.

### S6 results

Corrected the same day after a recheck. The first reading ("the pane loses focus in 3 to 5 seconds and keys never arrive") was wrong.

- A manual open (`/board-spike-probe`) gives the pane focus (`isFocused: true`). With no keys sent it kept focus for 12 seconds. Left and Down moved focus out of the pane (`isFocused: false`).
- Keys do not reach the pane's `Client` until a mouse click lands on the `Client`. Before the click, Up, Down, Enter and letters went to the chat prompt (`prompt.change` with `origin: history`) and no `key` event was logged. After a click (SGR mouse click at the Client area), Up, Down, Enter and `a` each produced a `key` event on the pane's request id. This matches the type docs: keys arrive "while a `Client` had the focus" (index.d.ts:1448).
- `UiPane.isFocused` stays false even while the `Client` holds key focus, so pane focus and `Client` focus are separate. The probe field `chatPromptHadFocus` is wrong in that case and must not be trusted.
- Escape never reaches the `Client`; it returns focus (index.d.ts:1449).
- Shift+Tab did not cycle the chat's permission mode while the pane had focus; after Escape it did.
- Automatic open on the first agent (`open-auto`) places the pane without taking focus.
- In the operator's own window the pane was a narrow strip at the top right, about 25 columns wide, and clipped its header text.
- Consequence for the spec: Board keys (arrows, Enter) work only after the operator clicks the Board. Whether that is acceptable, or Board also needs slash commands, is an open decision before T016 and T017.
- Not tested: widths of 150 and 100 columns, whether a click on one row selects it, and Escape closing the pane.
