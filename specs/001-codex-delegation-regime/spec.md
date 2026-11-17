<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Codex Bridge + Multi-Model Delegation Regime

**Feature Branch**: `001-codex-delegation-regime`
**Created**: 2026-09-02
**Status**: Draft
**Input**: User description: "Codex bridge + multi-model delegation regime: local HTTP bridge exposing a persistent OpenAI Codex session, plus a Gemini leg, plus a routing policy that decides which backend (Claude main session, Haiku subagent, Codex, Gemini) handles which class of work, with the goal of keeping large data out of the Claude context window."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Offload bulk reading without spending Claude context (Priority: P1)

The operator asks Claude a question that would require reading a large volume of local material — a directory of source files, a long log, a sprawling transcript. Instead of pulling that material into the Claude conversation, Claude hands a self-contained instruction to a secondary provider that reads the material itself and returns only a compact digest. The operator gets the answer; the bulk never occupies the conversation.

**Why this priority**: This is the entire economic premise. Every other story is scaffolding that makes this one repeatable. If only this ships, the operator already saves context on the highest-volume class of work.

**Independent Test**: Ask a question spanning a directory too large to read inline. Confirm the answer is correct, and confirm the conversation transcript never contains the file contents — only the instruction and the digest.

**Acceptance Scenarios**:

1. **Given** a running delegation service and a directory of source files, **When** the operator asks what a subsystem does, **Then** a digest answer is returned and the raw file contents never enter the Claude conversation.
2. **Given** a multi-megabyte log file, **When** the operator asks which errors matter, **Then** the relevant lines and a diagnosis are returned without the log entering the Claude conversation.
3. **Given** a follow-up question about the same material, **When** the operator asks it, **Then** the secondary provider answers from its retained understanding without the material being re-supplied.

---

### User Story 2 - Start the whole setup with one command (Priority: P1)

The operator starts the delegation service with a single command and does no manual copying of URLs, tokens, or identifiers between terminals. Claude discovers the service's address and credential on its own. Stopping is equally one command, and starting twice does not produce two services.

**Why this priority**: The operator named the two-terminal copy-paste loop as the specific pain. A capability that requires manual ceremony each session will not be used, so ease of startup determines whether Story 1 delivers value in practice.

**Independent Test**: From a cold machine state, run the start command once and confirm Claude can immediately send a prompt without the operator supplying any address or credential.

**Acceptance Scenarios**:

1. **Given** no service running, **When** the operator runs the start command, **Then** the service becomes reachable and its address and credential are recorded where Claude can read them.
2. **Given** a service already running, **When** the operator runs the start command again, **Then** the existing service is reused and no duplicate is created.
3. **Given** a running service, **When** the operator runs the stop command, **Then** the service and any companion processes stop and the recorded state is cleared.
4. **Given** a service that fails to become reachable, **When** startup is attempted, **Then** the failure is reported with diagnostic output rather than silently appearing to succeed.

---

### User Story 3 - Route each task to the appropriate backend deliberately (Priority: P2)

The operator has four backends available with different costs, capabilities, and privacy properties. A documented routing policy states which class of work goes where, so Claude applies it consistently across sessions instead of re-deriving it, and the operator can predict and audit where their data goes.

**Why this priority**: Depends on Stories 1 and 2 existing. Without a policy, routing is ad hoc and the operator loses track of which vendor received what — a governance problem, not merely an efficiency one.

**Independent Test**: Present several tasks of different classes and confirm each is routed per the documented table, with the chosen route named before work begins.

**Acceptance Scenarios**:

1. **Given** a task matching a documented class, **When** Claude begins work, **Then** the documented backend is selected automatically and recorded, without the operator being asked to approve the route.
2. **Given** a task involving sensitive material, **When** routing is chosen, **Then** backends that train on submitted data are excluded.
3. **Given** a task requiring conversation context, **When** routing is chosen, **Then** it stays in the Claude session rather than being delegated.
4. **Given** a task classed as code writing, **When** routing is chosen, **Then** it goes to the governed subagent path unless the operator explicitly directs otherwise.

---

### User Story 4 - Second opinion when debugging stalls (Priority: P3)

When Claude has formed a hypothesis about a bug and cannot confirm it, the operator can obtain an independent diagnosis from a backend that can inspect and run the code locally, without that backend inheriting Claude's assumptions.

**Why this priority**: Valuable but occasional. Depends on the same delivery mechanism as Story 1.

**Independent Test**: Present a known bug, request an independent diagnosis, and confirm the returned reasoning is derived from the code rather than restating the supplied hypothesis.

**Acceptance Scenarios**:

1. **Given** a reproducible failure, **When** an independent diagnosis is requested, **Then** a hypothesis grounded in the actual code is returned.
2. **Given** a returned diagnosis, **When** Claude acts on it, **Then** the claims are checked against the repository before any change is made.

---


### User Story 5 - Know what each subscription is actually worth (Priority: P2)

The operator pays for several AI subscriptions and cannot tell which are earning their cost. A usage ledger records input and output volume per model across every backend, updated without the operator doing anything, so that at any point they can see consumption per provider and decide whether a plan can be downgraded.

**Why this priority**: Independent of the delegation machinery — it measures rather than enables — but it is the feedback loop that tells the operator whether delegation is working. Without it, the token-saving premise is unfalsifiable.

**Independent Test**: After a period of normal work, request a usage report and confirm it shows per-model input and output totals that are consistent with the work actually performed.

**Acceptance Scenarios**:

1. **Given** prior sessions have occurred, **When** the operator requests a usage report, **Then** per-model input and output totals are shown without the operator having enabled tracking in advance.
2. **Given** work was delegated to a secondary backend, **When** the report is produced, **Then** that backend's consumption appears alongside the primary model's.
3. **Given** a subscription with a known monthly price, **When** the report is produced, **Then** it shows the equivalent metered cost of the same usage so the two can be compared.
4. **Given** the report is generated twice over the same bounded record set, **When** the outputs are compared, **Then** they are byte-identical.

---

### Edge Cases

- What happens when the secondary provider's rate-limit window is exhausted mid-task? The operator must be told the work was throttled, not handed a partial or fabricated answer.
- What happens when a retained session identifier becomes stale because the provider restarted? Recovery must not silently discard accumulated context without saying so.
- What happens when a credential file is missing or unreadable? Startup must fail loudly rather than starting an unauthenticated service.
- What happens when two requests arrive at once against a single retained session? Interleaving must not corrupt the session.
- What happens when a requested backend is not installed on the machine? The gap must be reported with the remedy, and unrelated capability must keep working.
- What happens when returned output is wrong or fabricated? Load-bearing claims must be verified locally before being acted upon.
- What happens when the operator asks about material outside the permitted working directory? Access scope must be bounded and stated.
- What happens when usage history is incomplete because records were rotated or deleted? The report must state the period it actually covers rather than implying completeness.
- What happens when a provider reports usage in units that do not map to the others? The report must keep them separable rather than summing incomparable figures.
- What happens when the same logical response is recorded more than once in the underlying records? Usage must be counted once, not multiplied by the number of records mentioning it.
- What happens when a delegated backend is throttled partway through a session? The ledger must show the work that succeeded without implying the throttled work also completed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a text instruction and return a text response from a secondary provider without the operator interacting with that provider directly.
- **FR-002**: The system MUST retain conversational context across successive instructions so follow-up questions do not require restating prior material.
- **FR-003**: Users MUST be able to clear retained context explicitly, both as part of a request and as a standalone action.
- **FR-004**: Users MUST be able to query the current retained-session identity and the service's running state.
- **FR-005**: The system MUST require a shared secret on every request that causes work to be performed, and MUST reject requests lacking a valid secret.
- **FR-006**: The system MUST refuse to start without a configured secret.
- **FR-007**: The system MUST never emit the shared secret into logs, responses, or terminal output.
- **FR-008**: The system MUST bound the working directory the secondary provider may read, and MUST report that boundary to the operator at startup.
- **FR-009**: The system MUST distinguish, in its responses, between provider-unavailable, provider-failed, request-invalid, unauthorized, and timed-out conditions.
- **FR-010**: The system MUST apply a configurable time limit to each delegated instruction and report when the limit is reached.
- **FR-011**: The system MUST reject requests whose payload exceeds a stated size limit.
- **FR-012**: The system MUST serialize concurrent delegated instructions against a single retained session so they cannot interleave.
- **FR-013**: The system MUST recover from a stale retained session by starting a fresh one, and MUST make that substitution visible rather than silent.
- **FR-014**: Users MUST be able to start the service with a single command that requires no manual transcription of addresses or credentials.
- **FR-015**: The start command MUST be idempotent, reusing an already-running service rather than creating a duplicate.
- **FR-016**: The start command MUST record the service's address, credential location, and operating parameters where an automated consumer can read them.
- **FR-017**: Users MUST be able to stop the service and its companion processes with a single command, without destroying the stored credential.
- **FR-018**: The system MUST support an optional externally reachable address for consumers not on the local machine, and MUST degrade gracefully when the tooling for that is absent.
- **FR-019**: The system MUST report the volume of work consumed by each delegated instruction so the operator can track quota use.
- **FR-020**: The system MUST provide a second delegation backend suited to very large single blobs of text, usable through the same command shape as the first, with a selectable model tier for digest, cheap-triage, and deeper-analysis work.
- **FR-021**: The second backend MUST read source material itself rather than requiring that material to pass through the Claude conversation.
- **FR-022**: The system MUST document a routing policy mapping classes of work to backends, including the reason for each mapping.
- **FR-023**: The routing policy MUST identify which backends retain or train on submitted data, and MUST exclude those from work involving sensitive material.
- **FR-024**: The routing policy MUST preserve the existing governance rule that code writing is delegated to the governed subagent path unless the operator directs otherwise.
- **FR-025**: The system MUST route work to a backend automatically when the task matches a documented class, and MUST record the backend used so the operator can audit data egress after the fact.
- **FR-026**: The system MUST state that delegated output is unverified, and MUST require local verification of load-bearing claims before they are acted upon.
- **FR-027**: The system MUST degrade gracefully when a backend's credential is absent, reporting the gap and the remedy while leaving other backends functional.

- **FR-028**: The system MUST record input and output volume per model for every request it makes to any backend.
- **FR-029**: The system MUST recover historical usage for the primary assistant from records already written during normal operation, without requiring tracking to have been enabled beforehand.
- **FR-030**: Usage collection MUST NOT alter, slow, or interpose on the request path; it MUST be observational only.
- **FR-031**: Usage reporting MUST be deterministic over a fixed record set — the same records MUST produce byte-identical output on repeated runs. Because the act of requesting a report can itself append new records, determinism is defined against a bounded record set, and the report MUST accept an explicit upper time bound for that purpose.
- **FR-032**: The system MUST attribute usage to a named model, not merely to a provider, so that tier-level decisions are possible.
- **FR-033**: The system MUST express usage as an equivalent metered cost using an operator-editable price table, so subscription value can be judged.
- **FR-034**: The report MUST state the time period it covers and MUST disclose when that period is bounded by missing or rotated records.
- **FR-035**: The system MUST keep usage that is denominated in incomparable units separable rather than aggregating it into a single figure.
- **FR-036**: Usage records MUST NOT contain prompt or response content — volume and model identity only.
- **FR-037**: Usage aggregation MUST deduplicate records that describe the same logical response, so repeated records do not inflate totals.
- **FR-038**: The system MUST constrain what a delegated backend may read to a stated directory boundary and a stated permission level, and MUST record both.
- **FR-039**: Delegated-backend invocation MUST default to the least permission level that allows the task, rather than to unrestricted host access.

### Key Entities

- **Delegation service**: The long-running local component that accepts instructions, dispatches them to a secondary provider, and returns results. Holds the retained session identity and the concurrency guard.
- **Retained session**: The accumulated conversational context held by a secondary provider, identified by an opaque identifier, resettable on demand and replaceable when stale.
- **Shared secret**: The single credential gating access to the delegation service. Confers the same practical authority as shell access on the host machine.
- **Service state record**: The recorded address, credential location, working directory, limits, and process identities that let an automated consumer use the service without operator transcription.
- **Routing policy**: The documented mapping from classes of work to backends, together with the cost, capability, and privacy rationale for each mapping.
- **Usage ledger**: The append-only record of per-request volume, carrying timestamp, backend, model, input count, output count, and cache counts. Holds no prompt or response content.
- **Price table**: An operator-editable mapping from model identity to metered unit price, used to express consumption as an equivalent cost.
- **Backend**: A provider of delegated work, characterized by whether it can read local material itself, whether it can see the Claude conversation, its marginal cost, and its data-retention behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a bulk-reading task spanning at least twenty files, the material never appears in the Claude conversation, and the conversation grows by no more than the instruction plus the returned digest.
- **SC-002**: An operator can go from a machine with nothing running to a successfully answered delegated question with one command and one question, transcribing nothing by hand.
- **SC-003**: Running the start command twice in succession leaves exactly one service running.
- **SC-004**: A follow-up question referencing material from an earlier instruction is answered correctly without that material being re-supplied, demonstrating retained context.
- **SC-005**: Every failure mode listed in the edge cases produces a distinct, actionable message rather than a generic error or an apparent success.
- **SC-006**: The shared secret appears in no log file, response body, or terminal output produced by the system.
- **SC-007**: For any task Claude delegates, the operator can determine after the fact which backend received which material, from Claude's own reporting alone.
- **SC-008**: A second operator, reading only the routing policy, routes a set of sample tasks the same way the policy author would.
- **SC-009**: Delegated work reports its consumption, so the operator can see quota use per instruction without consulting the provider's own interface.

- **SC-010**: A usage report covering prior work can be produced without tracking having been switched on in advance.
- **SC-011**: Running the report twice against the same bounded record set produces byte-identical output. Unbounded runs are not expected to match, because the reporting session appends records of its own.
- **SC-012**: The report attributes consumption to specific named models, so the operator can tell which tier drove the cost.
- **SC-013**: The operator can determine from the report alone whether a given subscription's monthly price exceeds the metered cost of the usage it covered.
- **SC-014**: Producing the report adds no measurable latency to any request, because it reads records written as a side effect of normal operation.

## Assumptions

- The operator's secondary-provider access is via a subscription rather than metered per-token billing, so the binding constraint is rate-limit windows rather than accumulating cost. Throttling, not expense, is the failure mode to design against.
- The primary consumer of the delegation service runs on the same machine as the service, so externally reachable addressing is an opt-in extra rather than the default path.
- The second backend's credential is stored in a file alongside the first backend's credential, not an environment variable, because the operator's environment did not reliably export it. The system degrades gracefully when the file is absent.
- Routing is automatic: Claude selects the backend from the documented policy without per-task confirmation, and states the route in its report so egress remains auditable after the fact. The operator ratified automatic routing on 2026-09-02.
- The default working-directory boundary is the specific project under discussion rather than the whole home directory, narrowing what a delegated backend can read to what the task requires.
- The existing governance rule binding code writing to a governed subagent path remains in force; this feature adds routes for reading, triage, and diagnosis, and does not redirect implementation work.
- A free-tier backend that trains on submitted inputs is acceptable for public or non-sensitive material and excluded for anything proprietary.
- The operator is the sole user; multi-user access control, audit retention, and quota accounting across people are out of scope.
- The primary assistant already writes per-message usage records during normal operation, so historical usage is recoverable by reading them rather than by instrumenting the request path. This is what makes the tracking non-intrusive and retroactive.
- Subscription-versus-metered comparison is advisory. Rate limits, latency, and feature access also determine a plan's worth, and the report informs the decision rather than making it.
- Delegated output is treated as unverified evidence. Verification against the local repository is part of the workflow, not an optional extra.
