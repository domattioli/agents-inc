<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Data Model: 010-persistent-exec-session (Phase 1)

Storage: one JSON file per mandate at `$CODEX_BRIDGE_AGENT_STATE_DIR/mandates/<run_id>.json` (default `~/.codex-bridge/agents/mandates/`), mode 0600, atomic replace. Source: research R4/R5.

## Mandate

| field | type | rule |
|---|---|---|
| `run_id` | string | = ledger `run_id` (CONTEXT.md Run). Filename stem. Unique. |
| `state` | `open` \| `closed` | starts `open`; transition `open → closed` only; never reopens (new mandate instead) |
| `opened_at` | ISO-8601 UTC | set on first `submit --mandate` (implicit open) |
| `opened_by` | string | `$USER` or `$CODEX_BRIDGE_ACTOR` if set |
| `closed_at` | ISO-8601 UTC \| null | set by `mandate close` |
| `closed_by` | string \| null | actor passed via `--by <actor>`; MUST be non-empty **and MUST be a member of the fixed allowlist `{ceo, lead}`** (lowercased exact match) — anything else fails closed, exit 2 (contracts C2a, spec FR-005a). **Validation precedes state inspection** — an invalid value is refused even on an already-closed mandate, so no code path can write a non-allowlisted value under any ordering (C2a precedence rule, analyze pass-2 F-01). Value validation is **not caller authentication** (spec FR-005a residual risk). Roster ⚠ operator-unconfirmed; widen only by editing C2a. **EXECUTIVE RULING (Fable, 2026-09-12): does NOT block PR-readiness; ships as explicitly-flagged-open.** Basis, verified: (i) `clarify-questions.md:3` records Q1=A as **answered by the operator** — "close authority = current Task Authority holder (Lead by default, CEO always)" — so `{ceo, lead}` is exactly the two actors the operator's own answer names, not an agent invention; (ii) code enforces exactly that set (`agent_runner.py:34` `ALLOWED_CLOSERS = {"ceo", "lead"}`, `:415` `validate_by`, `:910` `--by` help text) and invariant I7 (line 79) matches; (iii) canon check `CONTEXT.md:31-35`: Task Authority is policy-granted and may move by **Authority Reassignment** to a pre-approved holder — that holder is the one case the roster cannot name. Residual gap therefore = "reassigned holder cannot close under its own label in v1"; since v1 does not authenticate the closer anyway (FR-005a residual risk), this is a labelling gap, not an authority gap, and widening is a one-line operator-signed C2a edit. Open item for operator, non-blocking: confirm `{ceo, lead}` or name the reassignment label. |
| `close_reason` | string \| null | free text from `--reason` |
| `roles` | map role → RoleSession | keyed by role name (see below) |
| `overrides` | list of Override | every `--force` use |

## RoleSession

| field | type | rule |
|---|---|---|
| `role` | string | free-form label chosen by caller (e.g. `executive`, `supervisor`, `reviewer-1`). Case-insensitive, normalized lower. Rung names from ROUTING-RANKING are recommended, not enforced in v1 |
| `model` | string | Codex slug at first engagement (`gpt-6-astra`, `gpt-5.6-sol`, …). Immutable unless `--force` |
| `thread_id` | string \| null | provider session id from bridge response. null until first successful return |
| `continuity` | `resume` \| `no-resume` | `resume` for backend `codex`; `no-resume` recorded for any other backend dispatched under a mandate (FR-011) |
| `in_flight_job_id` | string \| null | job id of non-terminal engagement; cleared when that job reaches `TERMINAL` |
| `engagements` | list of Engagement | append-only |
| `replaced_thread_ids` | list of string | prior thread ids abandoned via `--fresh` (FR-008) |

## Engagement

| field | type | rule |
|---|---|---|
| `job_id` | string | runner job id (`job-<hex>`) |
| `mode` | `fresh` \| `resumed` \| `fresh-forced` | `resumed` iff a `thread_id` was supplied to the bridge; `fresh`/`fresh-forced` iff `fresh: true` was supplied instead (contracts C3). Exactly one of the two bridge fields is sent on every mandate engagement — a mandate engagement never sends neither (that is the global-thread path, N-C5) |
| `isolation` | `thread_id` \| `fresh` | which bridge body field this engagement sent, recorded so I9 is checkable from the record alone. Derived: `thread_id` ⇔ `mode == resumed`; `fresh` ⇔ `mode ∈ {fresh, fresh-forced}` (added 2026-09-12, round-3 fix N-C5) |
| `prior_engagement` | job_id \| null | the engagement whose thread was resumed |
| `requested_model` | string | as passed / defaulted |
| `at` | ISO-8601 UTC | |
| `outcome` | `returned` \| `failed` \| `resume-failed` \| pending | copied from job terminal status |

## Override

| field | type |
|---|---|
| `kind` | `duplicate` \| `model-mismatch` \| `close-in-flight` (added at implement time, T024 — `--force` on `mandate close` with a role still in flight logs this kind; C2/FR-006 required an Override record for this case but the original enum omitted a value for it) |
| `role` | string |
| `by` | actor |
| `at` | ISO-8601 |
| `detail` | string (e.g. `in-flight job-abc; forced job-def`) |

## State transitions

Annotated with the bridge body each transition sends (round-3 fix, N-C5 — the transition table previously showed no bridge body, which is how the "fresh engagement silently rides the global thread" defect stayed invisible here):

```
Mandate:      (none) --submit --mandate M--> open --mandate close M--> closed
                                                  (close refused, exit 10, if any role in flight and no --force)
RoleSession:  absent --first submit--> {thread_id:null, in_flight:jobX, mode:fresh, isolation:fresh}
                                       bridge body: {"fresh": true}      <- NOT the global thread
              --jobX returns ok--> {thread_id:T, in_flight:null}
              --submit again--> {in_flight:jobY, mode:resumed, isolation:thread_id, prior:jobX}
                                       bridge body: {"thread_id": "T"}
              --resume fails--> {in_flight:null, outcome:resume-failed}   (thread_id kept)
              --submit --fresh--> {replaced_thread_ids:[T], thread_id:null, mode:fresh-forced, isolation:fresh}
                                       bridge body: {"fresh": true}
```

## Invariants (test targets)

- I1: `state == closed` ⇒ every `submit --mandate` for this id exits non-zero, no job created (FR-004, SC-004).
- I2: at most one `in_flight_job_id` per role unless an Override of kind `duplicate` exists for that role at that time (FR-006, SC-003).
- I3: `engagements[n].mode == resumed` ⇒ `engagements[n-1].outcome == returned` and `thread_id` non-null at dispatch time (FR-002).
- I4: `continuity == no-resume` ⇒ `thread_id` stays null and `mode` is always `fresh` (FR-011).
- I5: file survives runner process exit; a second runner process reads identical state (FR-009, SC-005).
- I6: an **isolated** request — caller-supplied `thread_id` **or** `fresh: true` — leaves the bridge's global thread attribute unchanged; the response's `thread_id` is the request-local observed id (FR-014, contracts C3). Corollary: a pending `follow-up`'s thread is never disturbed by a mandate dispatch, whether that dispatch resumes or opens fresh.
- I9: every mandate engagement sends exactly one of `thread_id` / `fresh: true` to the bridge — never neither (which would silently join the global thread) and never both (400). Checkable from the record via `engagements[n].isolation` (FR-014, contracts C3 `fresh`; round-3 fix N-C5).
- I7: `closed_by ∈ {ceo, lead}` for every closed mandate; no code path writes any other value (FR-005a, contracts C2a).
- I8: the resolved mandate state dir is never inside the repo root nor under `~/.claude/` (FR-015).
