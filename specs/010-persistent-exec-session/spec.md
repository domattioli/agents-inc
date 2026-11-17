<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Persistent Executive Session Across a Mandate

**Feature Branch**: `010-persistent-exec-session`
**Created**: 2026-09-12
**Status**: Clarified 2026-09-12 (5/5 answered — see `## Clarifications`; `clarify-questions.md` retained as record)
**Source issue**: domattioli/agents_Inc#15 — "Dispatch is stateless cold-start per call — no persistent Exec/Super session across escalations" (labels: `bug`, `probationary`, `priority: high`)
**Input**: User description: "Issue #15: persistent Executive/Supervisor session across a mandate. Dispatch via `codex exec -m <model>` is stateless cold-start per call; Exec should persist, backstop Supervisor, tear down only when mandate closed. Fix direction: capture `session id` / `thread_id` per role per mandate, prefer `codex exec resume <session-id> -m <model>` on re-engagement, duplicate-dispatch guard, mandate-close teardown."

## Evidence convention

Every requirement below carries a tag:

- `[#15 body]`, `[#15 c1]` … `[#15 c4]` — traces to a quoted fragment of issue #15's body or its comments 1–4 (in thread order).
- `[INFERRED]` — added by the spec author to make a requirement testable; not stated in #15. Flagged for operator review.
- `[CANON: <doc>]` — grounded in a repo governance doc (`CONTEXT.md`, `docs/governance/ROUTING-RANKING.md`, `docs/DECISIONS.md`).

Terminology follows `CONTEXT.md` and `ROUTING-RANKING.md` "Rungs": **Executive** (top rung; "Exec" in #15), **Orchestrator / Supervisor** (second rung; "Super" in #15), **Workhorse**, **Grunt**. "Mandate" (formerly, in #15, closed by "Owner/Interlocutor") = one `CONTEXT.md` **Run** (`run_id`); close authority = the current **Task Authority** holder (Lead by default, CEO always) — per Clarifications Q1.

## Clarifications

### Session 2026-09-12

Operator answers relayed via orchestrator (`clarify-questions.md` holds the full option tables).

- Q: Who may close a mandate, and what is a "mandate" in canon terms? → A: **Option A** — mandate = one `CONTEXT.md` Run (`run_id`); close authority = current Task Authority holder (Lead by default, CEO always). "Owner/Interlocutor" retconned to these canon terms; no `CONTEXT.md` change.
- Q: Which dispatch paths must persist sessions in v1? → A: **Option A** — Codex `codex exec` path only (Executive + Supervisor rungs on astra/sol/terra/luna). Claude `Agent`-tool path (#15 c4) and free-model wrappers (Gemini/Mistral/OpenRouter) explicitly out of scope for v1; ledger records `no-resume` honestly for them. Operator directive: this scoping decision is documented as a comment on #15 and MUST be flagged in the implementation PR description.
- Q: Interface shape — new mandate-level commands, or flags on existing dispatch commands? → A: **Option B** — additive `--mandate <M> --role <R>` flags on existing `agent.sh submit` (auto fresh-vs-resume) plus exactly one new verb `mandate close <M>`.
- Q: Duplicate in-flight engagement of the same (mandate, role) — refuse, or queue? → A: **Option A** — refuse with an error naming the in-flight engagement id; `--force` overrides and is logged.
- Q: Idle policy — does an open mandate ever auto-close? → A: **Option B** — never auto-close; session-start / preflight lists open mandates older than 7 days as a warning.

### Post-analyze amendments 2026-09-12 (adversarial Opus pass, verdict FAIL → fixed)

Five blocking findings were applied to spec/contracts/tasks; the nine WARN findings each carry a written disposition in **`plan.md` § "Analyze disposition (adversarial pass 2026-09-12)"** (single location, so the dispositions do not drift across files). Spec-side changes: FR-005a (`--by` allowlist, fail-closed), FR-011 (corrected the false "non-Codex paths have no continuity" claim), FR-012 (mutating-verb wording vs. read-only `list`/`show`; `--force` tagged `[INFERRED]` in FR-006), FR-014 (global thread untouched → `follow-up` undisturbed), FR-015 (state-dir env-override guard), SC-001 (made measurable). No clarify answer was reversed.

### Post-analyze amendments 2026-09-12, pass 2 (`analyze-2026-09-12b.md`, verdict FAIL: 3 CRITICAL / 13 WARN / 2 INFO → fixed)

A second independent Opus pass found the first fix pass had landed three fixes incompletely. **Every pass-2 disposition lives in `plan.md` § "Analyze disposition — pass 2"** (extending the same single-location convention; not restated per file). Spec-side changes: **FR-005a** reworded to claim only what the allowlist does (value constraint + fail-closed) with an explicit residual-risk line — *v1 does not authenticate the closer* — plus a new grill-clause item raised for the operator; **SC-001** now requires the measurement to be on the `submit --mandate` path and names task **T045** (stubbed, no provider call) as its authoritative evidence instead of a live quickstart re-send; **FR-011**'s `agent_runner.py` cites corrected by re-grep. The `--by` roster `{ceo, lead}` is **unchanged and still flagged** ⚠ NEEDS OPERATOR CONFIRMATION — the operator has not ruled on it. No clarify answer was reversed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-engage a role without re-briefing (Priority: P1)

A supervising session (the run root, or a Supervisor) has already dispatched a role (e.g. an Executive) once during a mandate. Later in the same mandate it needs that role again — e.g. the Supervisor escalates to its Executive for a backstop. The re-engagement continues the role's prior conversation, so the caller sends only the new question, not the full background again.

**Why this priority**: This is the core defect in #15: "every re-dispatch re-pays a full background-explanation tax, and nothing carries forward automatically" `[#15 body]`. Everything else (guards, teardown) exists to make this safe.

**Independent Test**: Dispatch a role with a briefing containing a unique fact; re-engage the same role with a question whose only correct answer requires that fact and no re-briefing; the answer is correct. Compare against a fresh dispatch of the same question, which must fail or ask for context.

**Acceptance Scenarios**:

1. **Given** role R was dispatched once in mandate M and its session identifier was recorded, **When** the caller re-engages R in M, **Then** the dispatch continues R's prior session rather than starting a new one, and the caller's prompt contains no re-pasted background `[#15 body: "use codex exec resume <session-id> -m <model> instead of a fresh codex exec -m <model> call, so the role's context persists across the mandate"]`.
2. **Given** role R has never been dispatched in mandate M, **When** the caller engages R, **Then** a fresh session starts and its identifier is recorded for M `[#15 body: "Track the session id codex exec prints for each dispatched role"]`.
3. **Given** a recorded session for R in M, **When** the resume attempt fails (session gone, provider error), **Then** the system reports the failure and the caller can explicitly choose a fresh start; the fresh session's identifier replaces the stale one and the replacement is recorded `[INFERRED — mirrors existing bridge-internal "Retry as fresh (no resume)" behaviour cited in #15 c3, but c3 states that path is "not exposed to/used by any dispatch call site"]`.

---

### User Story 2 - Executive stands by and backstops the Supervisor (Priority: P2)

The Executive is dispatched at mandate start, hands the work to a Supervisor, and then stays reachable. It does nothing unless the Supervisor trips up; when the Supervisor escalates, the Executive answers with full mandate context.

**Why this priority**: This is the stated design intent: "the Executive is hands-off support to the Supervisor, spawns a Supervisor to actively supervise workers … Executive just listens and steps in only if Supervisor trips up" `[#15 c2]`; "Exec lives, waits, and backstops Super until Owner/Interlocutor close the mandate" `[#15 body]`. Depends on P1 mechanics.

**Independent Test**: Run a two-round mandate: round 1 Executive briefs Supervisor; round 2 Supervisor escalates a stated trip-up; Executive's reply references round-1 facts without them being re-sent.

**Acceptance Scenarios**:

1. **Given** an Executive session opened for mandate M and a Supervisor session opened beneath it, **When** the Supervisor escalates, **Then** the escalation reaches the *same* Executive session `[#15 body: "there was no way to actually reach a live Exec — the dispatching session just cold-started a brand-new Exec instance"]`.
2. **Given** the Supervisor is progressing normally, **When** no escalation occurs, **Then** the Executive session is not re-engaged and incurs no cost `[#15 c2: "Executive just listens and steps in only if Supervisor trips up"; #15 body: "No idle-token cost (models aren't billed while not running)"]`.
3. **Given** the Supervisor pulls in additional Supervisor-level or lower models (including free models) `[#15 c2]`, **When** those are dispatched, **Then** they are recorded under the same mandate so the Executive's view of the mandate is complete `[INFERRED — needed so "backstop" has the information to act on]`.

---

### User Story 3 - Mandate closes and sessions are retired (Priority: P3)

When the mandate is declared complete, every role session opened for it is closed: no further resume is offered for that mandate, and the record shows who closed it and when.

**Why this priority**: "Close (stop resuming) a role's session only when Owner/Interlocutor agree the mandate is complete" `[#15 body]`. Without a close, sessions accumulate and a stale Executive could be resumed into a new mandate.

**Independent Test**: Close a mandate; attempt to re-engage any of its roles; the attempt is refused with a "mandate closed" reason; the record for M shows a close event.

**Acceptance Scenarios**:

1. **Given** open sessions for mandate M, **When** the close signal for M is given by the Task Authority holder (Lead default / CEO), **Then** no role in M can be resumed afterwards `[#15 body]`.
2. **Given** mandate M is closed, **When** a new mandate M′ starts with the same roles, **Then** M′ gets fresh sessions — nothing from M leaks in `[INFERRED]`.
3. **Given** a session in M is closed, **When** the dispatch record is inspected, **Then** the close event is visible with the closer's identity and the reason `[INFERRED — audit; consistent with CONTEXT.md "Ledger" being append-only]`.

---

### User Story 4 - Duplicate dispatch is refused (Priority: P3)

A caller accidentally dispatches the same role for the same mandate while an engagement is already in flight, or dispatches the wrong model for the role. The system refuses or warns instead of silently starting a second, divergent instance.

**Why this priority**: #15 cites a live incident: "this already happened twice in the same session: a wrong model was dispatched, then a duplicate concurrent dispatch was launched" `[#15 body]`; scoping listed "duplicate-dispatch guard" as a required mechanism `[#15 c3]`.

**Independent Test**: Start an engagement of R in M; before it returns, start a second engagement of R in M; the second is refused with a reason naming the in-flight one.

**Acceptance Scenarios**:

1. **Given** an in-flight engagement of role R in mandate M, **When** a second engagement of R in M is requested, **Then** it is refused and the refusal names the existing engagement id; only an explicit, logged `--force` proceeds `[#15 body; #15 c3]`.
2. **Given** role R in M was opened with model X, **When** a re-engagement names a different model Y, **Then** the mismatch is surfaced before dispatch and does not silently proceed `[#15 body: "a wrong model was dispatched"]`.

---

### Edge Cases

- Resume target no longer exists (provider purged the session, machine changed): see US1 scenario 3 — surface, do not silently cold-start `[INFERRED]`.
- Caller process (run root) dies mid-mandate: the recorded session identifiers must survive so a *new* run root can resume the mandate's roles `[INFERRED — #15 c4 notes the gap "is not vendor-specific — it is a missing capability wherever a supervising session dispatches a sub-agent expecting later continuation"]`.
- Vendor without a resume capability (Gemini, Mistral, OpenRouter one-shot; and Claude-side `Agent` dispatch per `[#15 c4]`): out of scope v1; recorded as `no-resume` (FR-011).
- Two concurrent mandates re-using the same role and model: session identifiers are keyed by mandate, never shared `[INFERRED]`.
- Mandate never closed (operator forgets): never auto-closed; preflight warns after 7 days open (FR-013).
- `--force` duplicate override: second engagement proceeds, both engagements recorded, override logged with caller identity (FR-006).
- `follow-up` used under a mandate: refused (contracts C1a) — v1 mandate continuity is `submit --mandate` only; a codex `follow-up`'s continuity rides the bridge's *global* thread and a mandate dispatch must not disturb it (FR-014).
- State-dir env override (`CODEX_BRIDGE_AGENT_STATE_DIR`) pointed back inside the repo: refused (FR-015) — otherwise mandate records become repo writes, contradicting the constitution-P1 reading that placed them outside the tree.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On every role dispatch, the system MUST capture the provider-issued session identifier and store it keyed by (mandate, role) `[#15 body: "Track the session id codex exec prints for each dispatched role"; #15 c1: "Each codex exec invocation already prints its session id in the transcript header"]`.
- **FR-002**: When a role is re-engaged within an open mandate and a stored identifier exists, the system MUST continue the stored session rather than start a fresh one `[#15 body; #15 c1: "prefer resume over a fresh exec when the same role is re-engaged before the mandate closes"]`.
- **FR-003**: When no identifier exists for (mandate, role), the system MUST start a fresh session and record it (FR-001) `[#15 body]`.
- **FR-004**: The system MUST NOT resume any session of a mandate after that mandate has been closed `[#15 body: "Close (stop resuming) a role's session only when Owner/Interlocutor agree the mandate is complete"]`.
- **FR-005**: Mandate close MUST be an explicit, recorded act by the current Task Authority holder (Lead by default; CEO always permitted). No other actor may close; the close record names the closer `[#15 body "Owner/Interlocutor" → Clarifications Q1=A; CANON: CONTEXT.md "Lead", "Task Authority"]`.
- **FR-005a**: The closer identity (`--by`) MUST be validated against a fixed, code-level allowlist and the close MUST fail closed on any other value. What this requirement claims, precisely: it **constrains the set of values that can ever be recorded in `closed_by`** to a fixed roster, and it **fails closed on typos, empty strings, and arbitrary free text** (which would otherwise be written verbatim into the audit record). Validation MUST precede state inspection (contracts C2a precedence rule), so an invalid value is refused even on an already-closed mandate. **Residual risk, stated rather than implied away (analyze pass-2 W-05): this is value validation, not caller authentication.** The guard checks a *string*, not the *identity of the process supplying it*; any delegate able to run `agent.sh` can still assert `--by lead` (or `--by ceo`). FR-005's "no other actor may close" is therefore **not enforced by v1** — v1 enforces only "no unrecognized actor label may be recorded". Authenticating the closer is out of scope for v1 and would need a mechanism `CONTEXT.md:33` implies but the repo does not yet have (Task Authority is **policy-granted and recorded**, so it is not derivable from a role label at all); ⚠ **GRILL-CLAUSE / NEW ITEM FOR OPERATOR** — closing the authentication gap (e.g. a signed/recorded Task Authority grant the close verb checks against) is a design decision beyond a textual fix and is flagged here rather than guessed at. v1 allowlist = `{ceo, lead}`, derived from FR-005's own two named actors; no env var, flag, or `--force` widens it (contracts C2a). ⚠ The roster itself is **unconfirmed canon**: `CONTEXT.md:31,33` define Lead and Task Authority but the repo has no Task Authority roster file, so `{ceo, lead}` is a deliberately narrow placeholder **requiring operator confirmation**; extension happens only by an operator-signed edit to contracts C2a `[INFERRED — analyze blocking #5; CANON: CONTEXT.md "Task Authority" (definition only, no roster)]`.
- **FR-006**: The system MUST refuse a second engagement of the same (mandate, role) while one is in flight; the refusal MUST name the in-flight engagement id. A `--force` override MUST be available and every use of it MUST be logged in the dispatch record `[#15 body; #15 c3 item 5; Clarifications Q4=A]`. `--force` is also accepted on `mandate close` when a role is still in flight; absent `--force`, that close MUST be refused with a **distinct, caller-distinguishable exit code 10** and stderr `agent: mandate <M> has role <R> in flight: <job_id> (use --force to close anyway)` — a refusal the earlier draft required but left with no status of its own, so a caller could not tell it from success `[INFERRED — contracts C1/C2/C2a step 4; consistently tagged as inferred wherever it appears; exit code added 2026-09-12, round-3 fix N-C2]`.
- **FR-007**: The system MUST surface a model mismatch between a stored session and a re-engagement request before dispatching `[#15 body: "a wrong model was dispatched"]`.
- **FR-008**: When a resume fails, the system MUST report the failure to the caller and MUST NOT silently substitute a fresh session; an explicit fresh restart replaces the stored identifier and records the replacement `[INFERRED; #15 c3 notes bridge's existing internal "Retry as fresh" is not a cross-role mechanism]`.
- **FR-009**: Session identifiers and mandate open/close events MUST be persisted outside the caller's process memory so a subsequent run root can continue the mandate `[INFERRED — from #15 body "The dispatching session becomes a single point of failure for continuity"]`.
- **FR-010**: Every dispatch record MUST state whether it was fresh or resumed, and if resumed, from which prior engagement `[INFERRED — audit; consistent with CANON: CONTEXT.md "Ledger" and "Derivation" replay requirements]`.
- **FR-011**: v1 persistence scope = the Codex dispatch path only (any rung dispatched via `codex exec`: astra/sol/terra/luna), validated on the Executive ↔ Supervisor pair `[#15 c1: "validated against a real multi-round Exec↔Super escalation"; Clarifications Q2=A]`. The Claude `Agent`-tool path (#15 c4) and free-model wrappers (Gemini/Mistral/OpenRouter) are OUT OF SCOPE for v1 `[Clarifications Q2=A]`. Recording rule, corrected: `no-resume` means *"this feature provides no mandate-scoped continuity on this path"*, NOT *"this path has no continuity"* — those are different claims and the earlier wording asserted the false one. Ground truth on this machine: a Mistral `--agent` dispatch **does** have real vendor-side conversational continuity, reachable via `agent.sh follow-up` (`skills/codex-bridge/scripts/agent_runner.py:318-319` permits follow-up for `codex` **or** `mistral`, and `:322-323` refuses only the *stateless* non-`--agent` Mistral case — cites re-verified 2026-09-12, analyze pass-2 re-grep; the earlier `:319-323` pointed one line past the backend check); Gemini and OpenRouter are genuinely one-shot (`:331` OpenRouter "stateless single-turn", `:333` Gemini jobs stateless). Therefore a non-Codex dispatch under a mandate MUST record `continuity = no-resume` **and** MUST NOT claim the underlying path is stateless; where that path has its own continuity (Mistral `--agent`), the record notes it as vendor-side and out of mandate scope. Mandate-scoped resume of such a path is deferred past v1.
- **FR-012**: Re-engagement MUST be exposed as additive `--mandate <M> --role <R>` flags on the existing `agent.sh submit` command (system decides fresh-vs-resume per FR-002/FR-003). Mandate closure MUST be exposed as exactly one new **mutating** verb, `mandate close <M>` — no other new verb may change state. Read-only companions `mandate list` and `mandate show <M>` are permitted and required (they are the surface FR-013's warning and the acceptance/close-audit scenarios are observed through); they mutate nothing `[INFERRED — clarify Q3=B constrains the *mutating* surface to one verb; read-only verbs added by the spec author]`. Existing `submit` invocations without the new flags MUST behave exactly as today. `follow-up` accepts no mandate flags in v1 (contracts C1a) `[#15 c1: "change the dispatch pattern in this repo's Codex-facing dispatch scripts"; Clarifications Q3=B]`.
- **FR-013**: Mandates MUST never auto-close. Session-start / preflight MUST list every open mandate whose open-at is older than 7 days as a warning (non-blocking) `[#15 body "only when … agree the mandate is complete"; Clarifications Q5=B]`.
- **FR-014**: A mandate dispatch MUST NOT mutate **or read** the bridge's global conversation thread — on **every** engagement, whether it resumes a stored session or opens a new one. Every mandate engagement MUST therefore declare its isolation explicitly in the request body: a stored session is resumed via `thread_id`, and a first/`--fresh` engagement MUST send `fresh: true`, which starts a new provider session with no `resume` argument and leaves the global thread byte-identical. A mandate engagement MUST NOT send neither field (that is the global-thread path) nor both (rejected 400). Consequence: a pending `follow-up` (whose continuity is that global thread) is never disturbed by any `submit --mandate` on any role, and two roles opened under one mandate never share a session. `follow-up` itself accepts no mandate flags in v1 `[INFERRED — analyze blocking #1/#2; contracts C1a + C3; **widened 2026-09-12, round-3 fix N-C5** — the earlier wording constrained only the resume half, so a *fresh* mandate engagement silently resumed and then overwrote the bridge's global thread (`bridge.py:194-195`, `:216`), which is the cross-contamination this requirement exists to forbid]`.
- **FR-015**: The mandate state directory MUST resolve outside the repository working tree. If `CODEX_BRIDGE_AGENT_STATE_DIR` resolves to a path inside the repo root (or inside `~/.claude/`), the runner MUST refuse with exit 2 rather than write there. **The repo root MUST be resolved by `git rev-parse --show-toplevel`** run from the directory containing `agent_runner.py`, falling back to the nearest ancestor of that file containing a `.git` entry when git is unavailable or the path is not a work tree; comparison is on fully resolved paths (symlinks followed), equality counting as "inside" — full rule and the rejected `CODEX_BRIDGE_SCRIPTS_DIR` anchor in **contracts C7**, implemented by **T043** `[INFERRED — analyze warning (d); resolution method pinned 2026-09-12, round-3 fix N-W11, which found the check specified with no stated method; closes the env-override hole in the constitution-P1 reading recorded in plan.md]`.

### Key Entities

- **Mandate**: One unit of delegated work with a start and an explicit close; groups all role sessions opened for it. Identity = one `CONTEXT.md` **Run** (`run_id`), 1:1. Attributes: opened-at, state ∈ {open, closed}, closed-at, closed-by (Task Authority holder). `[#15 body; CANON: CONTEXT.md "Run"; Clarifications Q1=A]`
- **Role session**: (mandate, role rung, model, provider session identifier, state ∈ {open, in-flight, closed}, opened-at, closed-at, closed-by). `[#15 body; INFERRED attributes]`
- **Engagement**: One dispatch turn against a role session; records fresh-vs-resumed, prior engagement reference, outcome. `[INFERRED]`
- **Close event**: (mandate, closer, reason, timestamp). `[#15 body; INFERRED attributes]`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a multi-round Executive↔Supervisor escalation, the prompt body the bridge sends for round ≥2 is **byte-identical to the caller's new input string**, with **no injected background** (no briefing text, no transcript, no mandate preamble) — measured by capturing the outbound `POST /prompt` body's `prompt` field and asserting `body.prompt == <caller's new input>` byte-for-byte, i.e. `len(body.prompt) == len(caller_input)` and equal content. **The measured path MUST be the `submit --mandate` path the criterion names** — not a hand-built `ask.sh --thread` call, which exercises different code and proves nothing about whether `agent_runner.py` injects a preamble (analyze pass-2 F-03). Reworded from the earlier unmeasurable "bounded by the new question alone" `[#15 body "re-pays a full background-explanation tax"]`.
  - **Primary evidence (automated, no provider call)**: `test_submit_mandate_prompt_body_byte_identical_no_preamble` in `tests/test_mandate_session.py` — drives a real round-2 `submit --mandate --role` against the stub `ask.sh` (T001 fixture) which records the body it was handed, then asserts that body's `prompt` equals the caller's input byte-for-byte. Task **T045**.
  - **Secondary evidence (live run, observational only)**: `quickstart.md` step 3a inspects the round-2 job record produced by step 3 itself; it issues **no additional provider turn** (the earlier version re-sent the prompt live, mutating the system under test between steps 3 and 5/6 and leaving an unrecorded engagement).
- **SC-002**: A round-2 question that depends on a round-1 fact is answered correctly by the resumed role in 100% of validation runs, and fails/asks-for-context in the fresh-dispatch control `[#15 c1 "validated against a real multi-round Exec↔Super escalation"]`.
- **SC-003**: Zero duplicate concurrent engagements of the same (mandate, role) reach the provider in a validation run that deliberately attempts one `[#15 body incident]`.
- **SC-004**: Zero resumes of a closed mandate's sessions succeed `[#15 body]`.
- **SC-005**: After the caller process is killed and restarted, every open role session of the mandate is resumable from the persisted record without operator re-briefing `[INFERRED — FR-009]`.
- **SC-006**: Issue #15 leaves `probationary` status: fix "implemented and validated end-to-end" `[#15 body "Status"]`.

## Out of Scope (for this feature)

- Routing-decision determinism / replay (`specs/009-cross-vendor-dispatch/routing-contract.md` RFC §2) — #15 c3 states this is "adjacent but distinct".
- Ledger visualisation (`specs/002-dispatch-graph-ledger`) — only the *record shape* is touched, not export/diagram.
- Bridge-internal HTTP-proxy reconnect logic (`bridge.py` `session_restarted`) — may be reused, is not the deliverable.
- Idle-time billing or cost accounting — #15 body: "not literally wasted tokens".
- Redefining rungs, escalation, or authority rules (`CONTEXT.md` Capability Escalation / Authority Reassignment; D27/D34) — this feature consumes them, does not change them.
- Claude `Agent`-tool path continuity (#15 c4) and free-model wrapper continuity (Gemini/Mistral/OpenRouter) — deferred past v1 per Clarifications Q2=A; candidate follow-up issue after v1 validates.

## Assumptions

- **A1**: "Persistent" means *conversation-context continuity* across engagements, not a live long-running process. #15 body confirms models "aren't billed while not running" and the fix is resume-by-identifier; no daemon is implied. `[#15 body]`
- **A2**: "Exec" = Executive rung, "Super" = Orchestrator/Supervisor rung per D34 rename; #15 predates/ignores the rename. `[CANON: ROUTING-RANKING.md Rungs; D34]`
- **A3**: Resume trigger is *explicit*: the caller names (mandate, role); the system decides fresh-vs-resume. No automatic re-engagement on a timer or on Supervisor failure detection — that detection stays with the Supervisor/run root. `[INFERRED from #15 c2 "steps in only if Supervisor trips up" — the trip-up signal originates with the Supervisor]`
- **A4**: The provider's resume capability is available (confirmed for Codex CLI: "`codex exec` help lists a `resume` subcommand" `[#15 c1]`; re-verified 2026-09-12 on this machine: `codex exec --help` lists `resume` and `fork`).
- **A5**: (resolved → Clarifications Q1=A) One mandate = one `CONTEXT.md` **Run** (`run_id`).
- **A6**: Existing tests in `tests/test_dispatch_contract.py` are the natural home for new resume-vs-fresh and duplicate-guard cases `[#15 c3 item 6]`.
