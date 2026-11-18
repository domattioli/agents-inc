# Feature Specification: Persistent Cross-Provider Delegate Handles

**Feature Branch**: `feat/delegate-handles`
**Created**: 2026-11-18
**Status**: Draft
**Input**: Operator: "persistent cross provider agent calls and the cache implications thereof". Supervisor findings (fable review, 2026-11-18): five routes each keep their own continuation id; the native loop's per-agent registry lives only in memory; three events restart a delegate thread with the full prompt; the Mistral route shares one conversation id across all delegates.

## Clarifications

### Session 2026-11-18 (answered by supervisor per operator direction: "you answer the clarify")

- Q: Retire trigger: automatic at ceiling or supervisor action? → A: Supervisor action. At ceiling the step result carries a one-line advisory; no automatic retire.
- Q: Listing surface? → A: An `agents-inc handles` launcher subcommand reading the handle store; no new MCP tool.
- Q: Ceiling unit? → A: Characters sent, converted at 4 chars per token (200k tokens = 800k chars; opus 1.2M chars).
- Q: Store scope and retention? → A: One JSON file per host session under `.scratch/agents-inc-<agent>/<session>/handles.json`; same retention as `.thread` files (git-ignored, no auto-delete).
- Q: Fingerprint form? → A: The mod has no crypto source. Use a pure-TS FNV-1a 32-bit hash (8 hex chars) plus the text length, logged with the step in the run record. Supersedes the earlier SHA-256 answer.
- Q: Who requests the handoff note on retire? → A: The supervisor. It sends the handoff request to the delegate as a normal continue step, then runs `agents-inc handles retire <id>`, which marks the handle `retired` and prints the successor seed instruction. The CLI never talks to a delegate.
- Q: Model slug for FR-010 and the ceiling? → A: The handle binds to provider plus adapter nickname. The slug reported by the first completed step (`acc.slug`) is recorded for information only. Guest rungs are never opus, so every guest handle uses the 800k-char default.
- Q: List native Claude agents? → A: Out of scope. The host does not expose them to the mod.
- Q: bridge.py change for FR-007? → A: None. The Mistral global id lives only in `mask.sh`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Delegate survives a host restart (Priority: P1)

A supervisor delegates to a guest rung (luna, sol, terra, astra or a free rung), the host session restarts or resumes, and the supervisor sends a follow-up to the same delegate. The follow-up continues the delegate's existing thread instead of starting a new one with the whole conversation.

**Why this priority**: A restart today drops the in-memory registry, so the next step re-sends the full prompt and the provider cache starts cold. This is the largest avoidable re-send.

**Independent Test**: Start a delegate, record its handle, restart the host, continue the delegate, and confirm the continuation sends only the new messages and reuses the same thread reference.

**Acceptance Scenarios**:

1. **Given** a delegate with a live thread, **When** the host restarts and the supervisor continues it, **Then** the step resumes the recorded thread and sends only messages added since the last step.
2. **Given** a recorded handle whose thread file no longer exists, **When** the supervisor continues it, **Then** the system starts a fresh thread with the full prompt and records why.

---

### User Story 2 - Supervisor lists and retires handles (Priority: P1)

The supervisor lists every open delegate handle in the session with its provider, model, state and context used, and retires a handle when it reaches its context ceiling, after the supervisor has asked the delegate for a handoff note; the supervisor then starts a successor delegate with that note in its prompt.

**Why this priority**: The continue-do-not-respawn rule exists in prose only. A uniform handle with a listing and a retire action makes the rule usable across providers.

**Independent Test**: Create two handles on different providers, list them, retire one, and confirm the listing shows the retired state and that a continuation sent to the retired handle is refused.

**Acceptance Scenarios**:

1. **Given** handles on two providers, **When** the supervisor lists handles, **Then** each row shows handle id, provider, nickname and slug, thread reference, state, characters sent and ceiling.
2. **Given** a handle at or over its ceiling, **When** the supervisor retires it, **Then** the handle state becomes `retired` and the command prints the instruction to paste the handoff note into a new delegate's prompt; the supervisor, not the system, creates the successor.

---

### User Story 3 - Parallel Mistral delegates keep separate threads (Priority: P2)

Two Mistral delegates run at the same time. Each continues its own conversation; neither overwrites the other's conversation id.

**Why this priority**: The Mistral route stores one global conversation id, so parallel delegates corrupt each other's thread and both lose cache.

**Independent Test**: Run two Mistral delegates in parallel through the bridge, continue each, and confirm each continuation lands in its own conversation.

**Acceptance Scenarios**:

1. **Given** two Mistral handles, **When** both are continued, **Then** each uses its own conversation id and neither id file is shared.

---

### User Story 4 - Prefix churn is visible (Priority: P2)

For each delegate step the system records a short fingerprint of the system text sent ahead of the conversation, so the operator can see whether that text changes between steps of the same delegate.

**Why this priority**: The system text is rebuilt each step. If it changes, every byte after it misses the provider cache. This must be measured before deciding whether to freeze it.

**Independent Test**: Run a delegate for three steps and read the per-step fingerprints from the run record.

**Acceptance Scenarios**:

1. **Given** a delegate run of several steps, **When** the run record is read, **Then** each step lists a system-text fingerprint, and a change between consecutive steps is flagged.

---

### Edge Cases

- Host compaction shrinks the conversation below what the delegate has seen: the thread restarts today. The handle records the restart reason and the restart count.
- A step fails and the retry opens a new thread: the handle points at the new thread and keeps the old reference in its history.
- Two host sessions in the same working directory: handles are scoped per session and never collide.
- Handle store unreadable or corrupt: the system starts fresh threads and reports one warning; it never blocks the step.
- A stateless (free-rung) provider has no provider-side thread: its handle still persists so the listing and retire work, and its thread reference is the local conversation record.
- Cross-model continuation is requested: refused; a handle binds to exactly one model.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist each delegate's handle record to disk in the session's delegate scratch directory after every step.
- **FR-002**: On the first step after a host restart, the system MUST load persisted handles and continue a recorded thread when the thread reference still exists.
- **FR-003**: A handle record MUST hold: handle id, provider, nickname and slug, thread reference, working directory, characters sent, message count seen, ceiling, state (`live`, `retired`), restart count and last restart reason.
- **FR-004**: The system MUST offer a listing of handles for the current session showing the FR-003 fields.
- **FR-005**: The system MUST offer a retire action that marks the handle `retired` and prints the instruction for seeding a successor from the handoff note. The supervisor, not the retire action, requests the handoff note from the delegate beforehand as a normal continue step.
- **FR-006**: The default ceiling MUST be 800,000 characters sent (the workerbee 200k-token rule at 4 characters per token). Every guest-rung handle uses this default.
- **FR-007**: The Mistral route MUST keep one conversation id per handle; no conversation id is shared between handles.
- **FR-008**: Each delegate step MUST record a fingerprint of the system text sent, and flag a change from the previous step of the same handle.
- **FR-009**: Any restart of a delegate thread (compaction, failed step, refusal, missing thread) MUST be recorded on the handle with its reason.
- **FR-010**: A handle MUST bind to one provider and one adapter nickname; continuing it on another provider or nickname MUST be refused with a message naming the handle. The slug reported by the first completed step is recorded for information only and is not part of the binding.
- **FR-011**: Handle persistence failures MUST NOT block a delegate step; they produce one warning per session.
- **FR-012**: The feature MUST add no paid API call and no new provider dependency ($0 incremental spend).

### Key Entities

- **Delegate handle**: one persistent reference to one delegate's thread on one model. Attributes per FR-003. Lifecycle `live` → `retired`.
- **Handle store**: per-session file of handle records beside the existing thread files.
- **Step fingerprint**: per-step short hash of the system text, with a changed flag.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a host restart, 100% of continuations of a live handle whose thread still exists send only new messages, not the full conversation.
- **SC-002**: Parallel Mistral delegates never share a conversation id (0 shared ids across a 2-delegate parallel test).
- **SC-003**: The operator can list all open handles of a session in one command.
- **SC-004**: Every thread restart carries a recorded reason (0 unexplained restarts in the run record).
- **SC-005**: For a 3-step delegate run, the run record shows 3 system-text fingerprints and whether each changed.

## Assumptions

- Provider-side caching (Anthropic, OpenAI, Mistral, OpenRouter) is outside agents-inc control; this feature maximizes the chance of a cache hit by avoiding full re-sends and keeping the prefix stable. Provider cache behavior for free tiers is unverified.
- Native Claude subagents already persist through the host (`SendMessage`); this feature covers guest rungs and bridge routes, and lists native agents only if the host exposes them.
- Freezing the system text (making it byte-stable) is out of scope; FR-008 measures churn first. A follow-up spec decides whether to freeze.
- Tail-only compaction of a delegate's own history is out of scope for this spec; the handle model leaves room for it.
- Delivered inside the mod (`mods/agents-inc`) plus the bridge scripts, consistent with the agents-inc-as-mod direction. No change to governed dispatch.
