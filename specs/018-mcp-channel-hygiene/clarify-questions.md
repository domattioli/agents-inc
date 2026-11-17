<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-specify repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->
# Clarify questions: 018-mcp-channel-hygiene

For the Supervisor (clarify gate, operator-directed). Each question maps to one open item in `spec.md`. The recommended option is marked. Answer by number and letter, for example "1A, 2A, 3A, 4A, 5B". None is answered here.

## Q1: Which MCP protocol versions enter each server's supported set? (FR-001, FR-002; F1)

Both servers pin `2024-11-05`; the Worker server echoes any requested version. Claude Code 2.1.290 carries a `2026-07-28` protocol era (local binary, 2026-10-06); Codex CLI's version preference is unknown [assumed]. A version may enter the set only when the server meets all of that version's requirements.

**Recommended:** Option A - it fixes the negotiation bug and gains structured results at low risk, without claiming 2026-07-28 features (Tasks, new envelope rules) that are unverified.

| Option | Description |
|--------|-------------|
| A | Set `{2025-06-18, 2024-11-05}`. Structured results (`structuredContent`, `outputSchema`) only when `2025-06-18` is negotiated. Plan re-checks every 2025-06-18 server requirement against the primary spec before code. |
| B | Set `{2024-11-05}` only. Fix the echo; no structured results (FR-002 dropped). |
| C | Set `{2026-07-28, 2025-06-18, 2024-11-05}`. Requires meeting every 2026-07-28 server requirement, which is not yet verified (egress blocked). |
| Short | Provide a different short answer (<=5 words) |

You can reply with the option letter, accept the recommendation by saying "yes" or "recommended", or give your own short answer.

## Q2: May the Lead cancel a running Worker? (FR-010; F4; amends D51)

D51 says "Parallel width, cancellation, and free-provider routing are later" (`docs/DECISIONS.md:578`). 017 lists cancellation as out of scope. A cancel tool needs a new decision entry (LESSON-CANDIDATE, sign-off and cross-vendor review per D46).

**Recommended:** Option A - a runaway or wrong Worker can only be waited out today (up to the Worker's own run time); a Lead-only cancel that never refunds fan-out closes that gap without widening what any agent can reach.

| Option | Description |
|--------|-------------|
| A | Yes. Broker tool `cancel {request_id}`, Lead only. Ends the Worker process group; result `status` `red`, `reason` `cancelled`, `task_state` `canceled`; fan-out and resume counts unchanged. Needs a D51 amendment before code. |
| B | No. FR-010 moves to Out of Scope. `notifications/cancelled` (FR-004) still ends a Lead wait but never the Worker. |
| C | Yes, but only through the file inbox (`kind: cancel`), not as an MCP tool. |
| Short | Provide a different short answer (<=5 words) |

## Q3: Which tool calls may run while a blocking call waits? (FR-003; F3; 017 plan DD7)

017 keeps Lead calls sequential so that `push` runs only between bounded Lead calls (017 FR-016, DD7). 018 must not contradict that. `ping` and notifications are not tool calls and are answered in every option.

**Recommended:** Option A - `status` is read-only and never touches a Worker, so serving it during a wait answers F3 without changing 017's ordering of `answer` and `push`.

| Option | Description |
|--------|-------------|
| A | Broker: `status` only. Worker server: none (its only other tool, 017's `check_lead`, is called by the same model that is blocked). All other calls wait. |
| B | No tool calls during a blocking call; only `ping`, cancel and progress. |
| C | Broker: `status`, `answer` and 017's `push`. Not recommended: it changes the sequential handling that 017 DD7 relies on and would need a 017 amendment. |
| Short | Provide a different short answer (<=5 words) |

## Q4: How are task states named? (FR-008; F2; layer decision)

The operator accepted A2A task-state names where states are named. Existing `status` values (`green`, `red`, `refused`, `needs-lead`, `timeout`) are read by Lead prompts and tests. A2A and the MCP Tasks extension spell some states differently (A2A `input-required`, `canceled` [assumed]; MCP `input_required`, `cancelled` [verified in the Claude Code 2.1.290 binary]).

**Recommended:** Option A - additive, so no Lead prompt or test breaks, and it follows the operator's layer decision literally.

| Option | Description |
|--------|-------------|
| A | Add `task_state` beside `status`, A2A v1.0 names in lower-case hyphen form (`working`, `input-required`, `completed`, `failed`, `rejected`, `canceled`). `status` unchanged. Plan re-checks the spellings against the A2A primary spec. |
| B | As A, but MCP Tasks spellings (`input_required`, `cancelled`), so a later Tasks migration needs no mapping. |
| C | Replace `status` values with A2A names. Breaks existing Lead prompts and tests. |
| D | No state field now; wait for the FR-009 probe. |
| Short | Provide a different short answer (<=5 words) |

## Q5: Landing order against 017 (Overlap with 017)

017's implementation is gated on agents_Inc PR 52. 018 FR-003 to FR-005, FR-008 and FR-010 build on 017's threads and `_await` event. FR-001, FR-002, FR-006, FR-007, FR-009 and FR-011 touch code 017 does not redesign, though FR-001 and FR-002 edit the same `handle` functions.

**Recommended:** Option B - the client timeout race (FR-006) and the version echo (FR-001) are live defects today; they are small and need not wait for 017.

| Option | Description |
|--------|-------------|
| A | All of 018 starts after 017 merges. One start gate, no merge conflicts. |
| B | Two waves. Wave 1, after PR 52 and independent of 017: FR-001, FR-002, FR-006, FR-007, FR-009, FR-011. Wave 2, after 017 merges: FR-003, FR-004, FR-005, FR-008, FR-010. 017 rebases over wave 1 where `handle` changed. |
| C | 018 wave 1 lands before 017 starts, and 017 is re-planned on top. Not recommended: re-opens 017's plan. |
| Short | Provide a different short answer (<=5 words) |
