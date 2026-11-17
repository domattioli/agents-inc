<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Clarify Questions — 010-persistent-exec-session (#15)

**Status**: ANSWERED 2026-09-12 by operator (relayed via orchestrator): Q1=A, Q2=A, Q3=B, Q4=A, Q5=B. Encoded in `spec.md` `## Clarifications`. This file is retained as the option-table record.

**Coverage scan** (taxonomy → status): Functional scope: Partial (Q2). Domain/data model: Partial (Q1). Interaction flow: Clear. Non-functional: Partial (Q5 — idle policy). Integration/external deps: Partial (Q2, Q3). Edge/failure handling: Partial (Q4). Constraints/tradeoffs: Partial (Q3). Terminology: Partial (Q1 — "mandate"/"Owner"/"Interlocutor" not in `CONTEXT.md`). Completion signals: Clear. Placeholders: 3 markers.

Note: `.specify/scripts/bash/check-prerequisites.sh` does not exist in this repo; feature dir resolved from `.specify/feature.json` (`feature_directory`).

---

## Q1: Who may close a mandate, and what is a "mandate" in canon terms?

**Context**: spec FR-005 — #15 body says "Close (stop resuming) a role's session only when Owner/Interlocutor agree the mandate is complete". Neither "mandate", "Owner", nor "Interlocutor" is defined in `CONTEXT.md`; canon has **Run** (`run_id`), **Lead**, **Task Authority**, **CEO**.

**Recommended:** Option A — maps #15's language onto existing canon without inventing new actors; a mandate becomes one Run, and closure is a Task Authority act, which is already recorded per Derivation rules.

| Option | Description |
|--------|-------------|
| A | Mandate = one `CONTEXT.md` **Run** (`run_id`); close authority = current **Task Authority** holder (Lead by default, CEO always). "Owner/Interlocutor" retconned to these terms. |
| B | Mandate = one Run; close requires **both** CEO (Owner) and Lead (Interlocutor) to agree — two-party close as #15 literally states. |
| C | Mandate is a new first-class entity spanning multiple Runs; add "Mandate", "Owner", "Interlocutor" to `CONTEXT.md` (canon change → needs CEO sign-off per D31). |
| Short | Provide a different short answer (<=5 words) |

You can reply with the option letter, accept the recommendation with "yes"/"recommended", or give your own short answer.

---

## Q2: Which dispatch paths must persist sessions in v1?

**Context**: spec FR-011 — #15 body/c1 name the Codex `codex exec` path (`skills/workerbee` role commands, `codex-bridge`). #15 c4 reports the same failure on the Claude-side `Agent` tool. Gemini/Mistral/OpenRouter wrappers are one-shot with no resume primitive.

**Recommended:** Option A — it is the only path with a verified resume primitive and the only one #15's "Next step" names; a vendor-agnostic abstraction can be designed so other paths slot in later without rework.

| Option | Description |
|--------|-------------|
| A | Codex path only (Executive + Supervisor rungs on astra/sol/terra/luna). Claude `Agent` and free-model paths explicitly out of scope; record "no-resume" honestly in the ledger for them. |
| B | Codex path + Claude `Agent` path (both vendors that hold Executive/Supervisor rungs per ROUTING-RANKING). Free models out of scope. |
| C | All paths; for vendors without resume, emulate continuity by replaying stored transcript into a fresh call. |
| Short | Provide a different short answer (<=5 words) |

---

## Q3: Interface shape — new mandate-level commands, or flags on existing dispatch commands?

**Context**: spec FR-012 — #15 c1: "change the dispatch pattern in this repo's Codex-facing dispatch scripts … capture and store the session id per role per mandate, and prefer resume". Existing surface: `agent.sh submit --backend <b> [--reset] "<prompt>"` (agent_runner.py already has a `--reset` for "persistent Codex or Mistral-agent session") and bare `codex exec` rows in `skills/workerbee/SKILL.md` Step 1a.

**Recommended:** Option B — additive flags keep every existing call site and test valid, and the `--reset` precedent shows the runner already carries per-backend session state; a separate `close` verb is still needed because "stop resuming" is not a dispatch.

| Option | Description |
|--------|-------------|
| A | New verbs: `mandate open` / `engage --mandate M --role R` / `mandate close`. Existing `submit` untouched. |
| B | Additive flags on existing `submit` (`--mandate M --role R`, auto fresh-vs-resume) plus one new `mandate close M` verb. |
| C | No CLI change; persistence lives only in `skills/workerbee/SKILL.md` prose instructions (session-id kept by the supervising model in its own context). |
| Short | Provide a different short answer (<=5 words) |

---

## Q4: Duplicate in-flight engagement of the same (mandate, role) — refuse, or queue?

**Context**: spec FR-006 / US4 — #15 body incident: "a duplicate concurrent dispatch was launched". Spec currently says "refuse (or serialize)".

**Recommended:** Option A — fail-closed matches the repo's stated posture (`resolve_rung.py` "fails closed, no guess"; D35), and a refused duplicate is a visible bug signal whereas a queued one hides it.

| Option | Description |
|--------|-------------|
| A | Refuse with error naming the in-flight engagement id; caller must wait or `--force` (logged). |
| B | Queue behind the in-flight engagement; run automatically when it returns. |
| C | Refuse by default; `--queue` flag opts into B. |
| Short | Provide a different short answer (<=5 words) |

---

## Q5: Idle policy — does an open mandate ever auto-close?

**Context**: spec Edge Cases "Mandate never closed (operator forgets)". #15 body: close "only when Owner/Interlocutor agree the mandate is complete" — implies never-automatic, but leaves stale open sessions unbounded.

**Recommended:** Option B — honours #15's "only when … agree" (no silent close) while giving the next session a visible prompt instead of an unbounded pile of resumable stale sessions.

| Option | Description |
|--------|-------------|
| A | Never auto-close. Open until explicit close, no warning. |
| B | Never auto-close, but any session-start / preflight lists open mandates older than N days (suggest N=7) as a warning. |
| C | Auto-close after N days idle (suggest N=7), recorded as `closed-by: timeout`. |
| Short | Provide a different short answer (<=5 words) |
