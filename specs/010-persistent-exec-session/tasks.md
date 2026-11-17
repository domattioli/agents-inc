---
description: "Task list for 010-persistent-exec-session"
---
<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->

# Tasks: Persistent Executive Session Across a Mandate

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/cli-and-bridge.md, quickstart.md (all in this dir)
**Prerequisites**: plan.md, spec.md (required); research.md, data-model.md, contracts/ used below
**Tests**: INCLUDED — plan.md Technical Context names `tests/test_mandate_session.py` + `tests/test_bridge_thread_id.py`; R10 mandates unittest coverage; tasks-first ordering per plan §Dispatch.
**Scope guard**: every task below touches only `skills/codex-bridge/scripts/agent_runner.py`, `skills/codex-bridge/scripts/ask.sh`, `bridge.py`, `skills/speckit-pipeline/scripts/preflight.sh`, `skills/codex-bridge/SKILL.md`, `skills/workerbee/SKILL.md`, `specs/010-persistent-exec-session/**`, `tests/**`. No task touches `workerbees/**` schema, `CONTEXT.md`, `docs/DECISIONS.md`.

**Dispatch key** (per plan.md §Dispatch + §"Free-tier model assignment + fallback chain" + §"Promotion-trigger log", `CLAUDE.md` labor rule, this dispatch's constraint §11): "Supervisor-self" = Sonnet writes it directly, formally logged as **scope-retention** row **PT-1** in plan.md — **not a promotion: no rung move, no promotion trigger** (D27 makes architecturally significant change Workhorse+ work by rule, and an Orchestrator has Workhorse capability by construction, so the rung retains work it is already qualified for). Wording aligned 2026-09-12, round-3 fix N-C3 — the key previously said "Lead-assigned with a recorded gate reason", contradicting plan.md's own W-12 re-characterization of the row it names. "Free-grunt" = sub-delegated to a **free model only** (`gpt-5.4-mini`, OpenRouter free, Gemini free, Mistral free) — **never Codex, never any paid tier**. **Haiku override (standing for this workstream, N-W3):** the operator ruled 2026-09-12 (recorded in `analyze-2026-09-12b.md` §12, after all four free tiers were probed dead on this machine) that **Haiku is authorized for every free-grunt row here** — all **30** of them (`grep -c 'Dispatch\*\*: free-grunt' tasks.md` → 30; the §12 text says "24", which was already wrong when written and is corrected here and in plan.md P2). This supersedes the blanket "never Haiku" in the chain tables below for this workstream only; the supervisor MUST re-probe the free tiers before each dispatch wave and prefer any that have recovered. T045/T046 carry the override inline for historical reasons — it applies to every free-grunt row, not just those two. Effort = `low` for free-grunt mechanical tasks, `medium` for Supervisor-self tasks (no operator-named override this dispatch). Every free-grunt task inherits the 14-element delegation prompt contract at implement time (not re-stated per task row here — see `CLAUDE.md` "Delegation prompt contract").

**Fallback chains** (every coding task below names one; definitions of record in plan.md):

| chain | order of use |
|---|---|
| **FC-1** | `gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier → **Haiku** (workstream override, see Dispatch key) |
| **FC-2** | `gpt-5.4-mini` → Gemini free tier → OpenRouter free-tier → Mistral free tier → **Haiku** (workstream override) (docs/prose) |
| **FC-S** | Supervisor-self (Sonnet) → on two failed checks, promote one rung up, same vendor; never down to a free grunt |

A quota pause on any chain member counts as one failed attempt toward the two-failed-checks promotion trigger (`CLAUDE.md` "Failed check — definition of record"). Chain exhausted on all four free models → fall to **Haiku** under the standing workstream override (Dispatch key, N-W3); Haiku unavailable too → **stop and report**. Never silently escalate to Codex or any other paid tier.

**Exit-code note**: new *state*-refusal codes are **7 / 8 / 9 / 10** — 7/8/9 renumbered from 3/4/6 because `route.sh` already exits 3 and 4 and those propagate verbatim through `agent_runner.py:150` (analyze blocking #3, contracts C1); **10** added 2026-09-12 (round-3 fix N-C2) for `mandate close` refused by an in-flight role, which C2 previously left with no code of its own. Exit **2** is the pre-existing *usage*-error class (`agent_runner.py:50` `die()` default + argparse usage exits) and is deliberately reused by C1a, C2a and FR-015 — see the C1 exit table.

---

## Phase 1: Setup

- [x] T001 [P] Create test fixture stub `tests/fixtures/mandate/stub_ask.sh` that echoes canned JSON (`{"response":...,"thread_id":...}`) for `test_mandate_session.py` to point `CODEX_BRIDGE_SCRIPTS_DIR` at (R10). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: mechanical fixture script, no design judgment.

**Checkpoint**: fixture exists; no other setup needed (stdlib-only, no new deps per plan.md Technical Context).

---

## Phase 2: Foundational (blocking — shared by every user story)

**Purpose**: Mandate store + `engage()` decision/guard logic + bridge `thread_id` plumbing. Every user story phase below calls into this.

### Tests first (write, confirm RED, before implementation)

- [x] T002 [P] Write failing tests `test_load_save_roundtrip`, `test_atomic_write_tmp_then_rename`, `test_file_mode_0600` in `tests/test_mandate_session.py` for `load_mandate`/`save_mandate` (FR-009, data-model.md storage rule). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: mechanical unit-test scaffold per plan §Dispatch example list.
- [x] T003 [P] Write failing tests `test_engage_fresh_when_absent` (FR-003), `test_engage_resume_when_thread_present` (FR-002, I3), `test_engage_fresh_forced_on_flag_appends_replaced_thread_id` (C1 behaviour matrix; **renamed + strengthened 2026-09-12, analyze pass-2 W-11** — MUST assert all three: `mode == "fresh-forced"`, the prior thread id appended to `roles.<r>.replaced_thread_ids`, and `roles.<r>.thread_id` reset to null; spec US1 AS3, FR-008, data-model.md RoleSession `replaced_thread_ids`), `test_engage_refuses_when_closed` (FR-004, I1), `test_engage_refuses_duplicate_in_flight` (FR-006, I2), `test_engage_force_override_logs_override` (FR-006), `test_engage_refuses_model_mismatch` (FR-007), `test_engage_force_model_mismatch_logs_override` (FR-007), `test_close_by_rejects_unknown_actor_exit2` + `test_close_by_accepts_ceo_and_lead_only` + **`test_close_by_invalid_rejected_even_when_already_closed`** (added 2026-09-12, analyze pass-2 F-01 — asserts C2a **precedence step 1**: an invalid `--by` exits 2 on an *already-closed* mandate, i.e. argument validation runs before state inspection, and the record is not rewritten) (FR-005a / C2a / I7 — **replaces** the struck free-text test `test_engage_by_field_is_free_text_no_roster_check`; `--by` is now allowlisted `{ceo, lead}`, fail-closed) in `tests/test_mandate_session.py`. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: test scaffolds against an already-specified contract (data-model.md state table); no design judgment, just assertions.
- [x] T004 [P] Write failing test `test_no_resume_continuity_for_non_codex_backend` in `tests/test_mandate_session.py` (FR-011, I4). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T005 [P] Write failing tests `test_thread_id_resume_path`, `test_thread_id_resume_failure_returns_409`, `test_global_thread_path_unaffected_when_thread_id_absent` (R-C regression — global-thread auto-restart must still fire when no `thread_id` supplied), `test_reset_and_thread_id_mutually_exclusive_400`, **`test_thread_id_path_returns_request_local_id_and_leaves_global_unchanged`** (C3 request-local rule / I6 — MUST assert BOTH: (a) response `thread_id` == the id observed in this request's stubbed event stream, and (b) the server object's global thread attribute is identical before vs. after the request, including on the 409 path), and — **added 2026-09-12, round-3 fix N-C5** — **`test_fresh_true_builds_command_without_resume_and_leaves_global_unchanged`** (body `{"fresh": true}` issued while the server already holds a global thread: assert the built `codex exec` argv contains **no** `resume` token, the response `thread_id` is the request-local observed id, and the server's global attribute is byte-identical before vs. after — C3 rules 3/4, I6, I9) and **`test_fresh_and_thread_id_together_400`** (both fields → HTTP 400, as does `fresh` + `reset: true`) in `tests/test_bridge_thread_id.py`, stubbing `subprocess.run` per research.md R10. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: test scaffold against contracts/cli-and-bridge.md C3 (explicit request/response shapes given).

### Implementation

- [x] T006 Implement `load_mandate(run_id)` / `save_mandate(...)` (atomic tmp+rename, mode 0600) in `skills/codex-bridge/scripts/agent_runner.py` under `STATE_DIR/mandates/<run_id>.json` (FR-009, data-model.md). Depends on T002 (red first). **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: state-machine/persistence code, plan.md explicit carve-out (not delegated).
- [x] T007 Implement `engage(run_id, role, model, backend, fresh, force)` in `skills/codex-bridge/scripts/agent_runner.py`: closed-mandate guard (I1/FR-004), duplicate-in-flight guard + `--force` Override append (I2/FR-006), model-mismatch guard + `--force` Override append (FR-007), fresh-vs-resume decision returning `(thread_id_to_resume | None, mode)`. Depends on T003, T006. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: core state-machine + guard logic, plan.md explicit carve-out.
- [x] T008 Implement `continuity=no-resume` branch for backend ≠ `codex` under a mandate (thread_id stays null, mode always `fresh`) in `agent_runner.py` (FR-011, I4). Depends on T004, T007. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: extends T007's state machine.
- [x] T009 Implement `bridge.py` `POST /prompt` **two** optional body fields, `thread_id` and `fresh` (C3). `thread_id` present → build `codex exec … resume <thread_id>`. **`fresh: true` → build `codex exec …` with NO `resume` argument at all, ignoring whatever the server holds** (the `resume` branch at `bridge.py:194-195` becomes global-path-only). Either field present = an **isolated request**: capture the observed session id into a **request-local** variable only (never assign `self.thread_id` — write sites `bridge.py:216` and `:298`), return that request-local id as the response's `thread_id` (not a read of the server attribute — `:238`, `:319`), use it for `resolve_actual_model` (`:248`, `:331`), and leave the server's global thread attribute **unchanged on every outcome incl. 409** (C3 rules 1-4, FR-014, I6, **I9**). On non-zero exit of a *resume* return HTTP 409 `{"error":"resume failed","thread_id":...,"stderr":...}` with **no** automatic fresh retry. 400 on `reset:true` + `thread_id`, on `reset:true` + `fresh`, and on `thread_id` + `fresh`. Global path (**neither** field present) keeps existing auto-restart behaviour unchanged (C3, FR-008, R-C, FR-012). **`fresh` added 2026-09-12, round-3 fix N-C5**: without it a first/`--fresh` mandate engagement sends no `thread_id`, falls through to the global branch, resumes whatever conversation the bridge was last holding and overwrites it — so "separate role, separate thread" was false for every first engagement. Depends on T005. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: touches bridge.py's intertwined resume/retry block (plan.md Design §3, R-C regression risk) — judgment call, not mechanical.

**Checkpoint**: store + guards + bridge thread_id plumbing all green. User story phases below only wire CLI surface + exercise scenarios.

---

## Phase 3: User Story 1 — Re-engage a role without re-briefing (P1) 🎯 MVP

**Goal**: `--mandate/--role` re-engagement continues the stored session; no re-briefing.
**Independent Test**: dispatch role with a unique fact, re-engage with a question needing that fact, answer correct; fresh-dispatch control fails.

### Tests first

- [x] T010 [P] [US1] Write failing test `test_submit_mandate_captures_thread_id_on_fresh` in `tests/test_mandate_session.py` (FR-001, FR-003, FR-010). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T011 [P] [US1] Write failing test `test_submit_mandate_resumes_stored_thread_id_no_rebrief` in `tests/test_mandate_session.py` (FR-002, I3). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T012 [P] [US1] Write failing test `test_mandate_survives_process_restart_second_reader_sees_same_thread_id` in `tests/test_mandate_session.py` (I5, FR-009, SC-005 — simulate via two separate `load_mandate` calls with no shared process state). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.

### Implementation

- [x] T013 [US1] **Owns all argparse/`main()` wiring for this feature (ownership assigned 2026-09-12, round-3 fix N-W9 — no task previously claimed the parser/dispatch surface, so `agent_runner.py:365-459` had no owner). Citations in (b)/(c) re-grepped 2026-09-12 (4th analyze pass finding — round-3's own diff shifted line numbers by 10 and the two citations below weren't re-checked; corrected here, not a new task.)** Three parts: (a) add `--mandate <run_id> --role <name> --model <slug> --fresh --force` flags to `submit` via `add_submit_flags` (`agent_runner.py:372-381`) per the C1 flag table; (b) register the **`mandate` verb-group subparser** — `mandate close|list|show` with their own arguments (`--by`, `--reason`, `--force`, `--json`, `run_id`) — in `command_parser()` (`agent_runner.py:365-404`) and add the corresponding dispatch branch to `main()` (`:417-473` — re-grep at implement time, further edits will shift these), routing each verb to the implementation that lands in T024/T025/T032 (this task wires the surface; those tasks write the bodies); (c) **C1a enforcement**: declare `--mandate/--role/--fresh/--force` on the `follow-up` subparser (`:391-394` — re-grep at implement time) with `help=argparse.SUPPRESS`, and reject any of them in `main()`'s `follow-up` branch via `die("follow-up does not accept mandate flags in v1; use submit --mandate")` (exit 2) — **without this the contract string can never fire**: verified 2026-09-12, `python3 agent_runner.py follow-up job-aaaa --mandate M --role executive "x"` → `agent.sh: error: unrecognized arguments: --mandate --role executive x`, exit 2, from argparse (round-3 fix N-W10). **Part (c) is already LANDED** in `agent_runner.py` by the round-3 fix pass — including `follow-up`'s `prompt` positional becoming `nargs="?"` plus an explicit `die("follow-up requires a prompt")`, which is required because argparse drops a trailing positional when an optional sits between two positionals. T013 verifies it still holds after (a)/(b) land and MUST NOT revert the `nargs="?"` change. Existing invocations without the new flags unchanged (FR-012). Depends on Phase 2. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: touches the shared `submit` argparse + dispatch branch that Phase-2 guards plug into; kept with the state-machine author to avoid an interface mismatch.
- [x] T014 [US1] Add `--thread <id>` **and `--fresh`** flags to `skills/codex-bridge/scripts/ask.sh` (adds `thread_id` / `fresh: true` to the POST body inside the `ask.sh:76-90` heredoc; the two together → exit 2 before any request; each key absent from the body entirely when its flag is absent — no `"fresh": false`; `--raw` unchanged) (C4; `--fresh` added 2026-09-12, round-3 fix N-C5). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: plan.md §Dispatch names "bash flag parsing in ask.sh" as the canonical free-grunt example.
- [x] T015 [US1] Wire `submit --mandate` to invoke `ask.sh --raw [--model] (--thread <T> | --fresh)` — **exactly one of `--thread`/`--fresh` on every mandate engagement, never neither** (`--thread` iff `engage()` returned `mode=resumed`, `--fresh` iff `mode ∈ {fresh, fresh-forced}`; I9, C3, round-3 fix N-C5) — parse `thread_id` from the JSON response (R3), call `engage()`/record the engagement (incl. `engagements[n].isolation`), and write `result.json` fields `mandate/role/mode/thread_id/prior_engagement/`**`prompt`** in `write_artifact` (`agent_runner.py:106-126`), where `prompt` is the exact outbound prompt string handed to `ask.sh`. **`prompt` added 2026-09-12, round-3 fix N-C1**: `brief()` (`agent_runner.py:271-275`) publishes neither `prompt` nor `mode`, so `agent.sh status --json` cannot serve SC-001 corroboration; `agent.sh result <id> --json` (which prints `result.json`, `:429-437`) can, and quickstart step 3a-ii now reads it. These keys are written **only under a mandate** — a non-mandate `submit` writes today's artifact unchanged (FR-012, CHK001, T046). (FR-001, FR-002, FR-003, FR-010, FR-014, SC-001.) Depends on T007, T009, T013, T014. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: integrates Phase-2 state machine with the bridge call — judgment on wiring order, not mechanical.
- [x] T016 [US1] Surface resume failure as exit 9 with the exact stderr prefix from C1 (`agent: mandate <M> role <R> resume failed for thread <T>; rerun with --fresh to replace`) when the bridge returns 409 (FR-008). Depends on T015. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: extends T015's dispatch path.

**Checkpoint**: US1 independently testable — resume mechanics complete.

---

## Phase 4: User Story 2 — Executive stands by and backstops the Supervisor (P2)

**Goal**: Executive session persists untouched while Supervisor works; escalation reaches the same Executive session; other roles pulled in are recorded under the same mandate.
**Independent Test**: two-round mandate — round 1 Executive briefs Supervisor, round 2 Supervisor escalates a stated trip-up; Executive's reply uses round-1 facts without re-sending them.

- [x] T017 [P] [US2] Write failing test `test_multiple_roles_recorded_under_same_mandate` in `tests/test_mandate_session.py` (US2 acceptance scenario 3 — additional Supervisor-level/lower roles engaged under the same `run_id` all appear in `mandate.roles`). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T018 [US2] Run T017 against Phase-2/Phase-3 code; if it fails, extend `engage()`'s role-keying (already generic per data-model.md `roles: map role → RoleSession`) — expected to pass with no new code since role is a free-form string key; if a fix is needed, make it here. Depends on T007, T017. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: verification + conditional fix on shared state-machine code.
- [x] T019 [P] [US2] Add one sentence to `skills/workerbee/SKILL.md` Step 1a (after the astra/sol/terra/luna roster): "under a mandate, dispatch Codex rows via `agent.sh submit --backend codex --model <slug> --mandate <run_id> --role <rung>`; bare `codex exec` is stateless and must not be used for Executive/Supervisor re-engagement." Rows themselves unchanged (C6). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-2** (`gpt-5.4-mini` → Gemini free tier → OpenRouter free-tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: plan.md §Dispatch names "SKILL.md sentences" as a canonical free-grunt example.

**Checkpoint**: US2 independently testable — backstop behaviour verified, no idle cost incurred (no code path re-engages Executive absent an explicit caller request, per A3 — proved by **T042** rather than inspection — see analyze warning (g) disposition in plan.md).

---

## Phase 5: User Story 3 — Mandate closes and sessions are retired (P3)

**Goal**: `mandate close` retires every role session; no further resume; close event recorded with closer identity.
**Independent Test**: close a mandate, attempt re-engage, refused "mandate closed"; record shows close event.

### Tests first

- [x] T020 [P] [US3] Write failing test `test_mandate_close_records_closer_reason_timestamp` in `tests/test_mandate_session.py` (FR-005). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T021 [P] [US3] Write failing test `test_closed_mandate_refuses_all_resume` in `tests/test_mandate_session.py` (I1, FR-004, SC-004). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T022 [P] [US3] Write failing test `test_new_mandate_same_roles_gets_fresh_session_no_leak` in `tests/test_mandate_session.py` (US3 acceptance scenario 2). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T023 [P] [US3] Write failing tests `test_mandate_close_idempotent_and_refuses_with_inflight_unless_force` **and `test_mandate_close_inflight_refusal_exits_10`** (added 2026-09-12, round-3 fix N-C2 — asserts the in-flight refusal returns exit **10**, not a bare non-zero, with stderr exactly `agent: mandate <M> has role <R> in flight: <job_id> (use --force to close anyway)`, and that the record is unchanged; the `--force` variant then exits 0 and appends one Override) in `tests/test_mandate_session.py` (C2 `mandate close` row, C2a step 4). **Precedence note (analyze pass-2 F-01):** this test exercises C2a precedence **steps 3 and 4** only — the idempotent second close MUST pass a *valid* `--by` (e.g. `--by lead`), because an invalid `--by` is refused at step 1 regardless of state. Do not assert exit 0 for a repeat close carrying an invalid actor; that case belongs to `test_close_by_invalid_rejected_even_when_already_closed` (T003). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.

### Implementation

- [x] T024 [US3] Implement `mandate close <run_id> --by <actor> [--reason <text>]` verb in `agent_runner.py`: sets `state=closed`, stamps `closed_at/closed_by/close_reason`; idempotent (second close with a **valid** `--by` → exit 0, prints already-closed); refuses if any role has `in_flight_job_id` unless `--force` (logged as Override) — that refusal MUST exit **10** with stderr exactly `agent: mandate <M> has role <R> in flight: <job_id> (use --force to close anyway)` (C1 exit table, round-3 fix N-C2) (C2, FR-005, FR-006). **MUST implement the C2a ordered pipeline exactly (analyze pass-2 F-01 / OQ-5):** (1) validate `--by` against the allowlist → exit 2 on failure *before any file read or write, whatever the mandate's state*; (2) load record, exit 1 if missing; (3) already-closed → exit 0, write nothing; (4) in-flight guard unless `--force`, exit **10** on refusal; (5) transition + atomic write. The allowlist check lives in T034 and MUST be invoked at step 1 of this function, not after the state check. Depends on T006, T007, T020, T023. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: state-transition + guard logic on the shared mandate record.
- [x] T025 [US3] Implement `mandate show <run_id> [--json]` verb dumping the Mandate record; exit 1 if missing (C2). Depends on T006. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: read-only dump of an already-defined schema — mechanical.

**Checkpoint**: US3 independently testable — close/retire/no-leak verified.

---

## Phase 6: User Story 4 — Duplicate dispatch is refused (P3)

**Goal**: second in-flight engagement of the same (mandate, role), or a model-mismatched re-engagement, is refused unless `--force`.
**Independent Test**: start an engagement, start a second before it returns; second is refused naming the first.

### Tests first

- [x] T026 [P] [US4] Write failing test `test_duplicate_inflight_refused_names_job_id` in `tests/test_mandate_session.py` (FR-006, SC-003). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T027 [P] [US4] Write failing test `test_force_duplicate_proceeds_both_recorded_override_logged` in `tests/test_mandate_session.py` (edge case "`--force` duplicate override"). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T028 [P] [US4] Write failing test `test_model_mismatch_refused_before_dispatch` in `tests/test_mandate_session.py` (FR-007). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T029 [P] [US4] Write failing test `test_force_model_mismatch_proceeds_override_logged` in `tests/test_mandate_session.py` (FR-007, C1). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.

### Implementation

- [x] T030 [US4] Wire `engage()`'s duplicate/model-mismatch refusals into `submit`'s exit-7 paths with the exact stderr prefixes from C1 (`agent: mandate <M> role <R> in flight: <job_id> (use --force to override)`; `agent: mandate <M> role <R> opened with <X>, requested <Y> (use --force to override)`) (FR-006, FR-007). Depends on T007, T013, T026-T029. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: exact-string CLI contract wiring on top of Phase-2 guards — kept with same author to guarantee string match (Gate T-G5/A-G5 diff-style check downstream).

**Checkpoint**: US4 independently testable — SC-003 (zero duplicate concurrent engagements reach the provider) verified.

---

## Phase 7: Polish & Cross-Cutting (FR-013, FR-005a, FR-014, FR-015, docs, PR/process notes, risk R-D; R-A now CLOSED by T034)

- [x] T031 [P] Write failing test `test_mandate_list_warns_open_mandate_over_7_days` in `tests/test_mandate_session.py` (FR-013). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low.
- [x] T032 Implement `mandate list [--json]` in `agent_runner.py`: one line per mandate (`<run_id> <state> opened=<ts> age=<N>d roles=<k>`), `WARN:` stderr prefix for open mandates aged >7d (C2, FR-013). Depends on T006, T031. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: age computation feeds the preflight gate downstream — kept consistent with T006's store author.
- [x] T033 [P] Wire `skills/speckit-pipeline/scripts/preflight.sh` to run `agent.sh mandate list` after the existing `.specify/` check when `agent.sh` is on the expected path; print its `WARN:` lines; never affects exit code (C5). Depends on T032. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: plan.md §Dispatch names "preflight.sh line" as a canonical free-grunt example.
- [x] T034 Implement **real `--by` validation** in `agent_runner.py`'s `mandate close`: lowercase the value and accept only the fixed allowlist `{ceo, lead}`; anything else (incl. empty/absent) → exit 2, stderr exactly `agent: --by must be one of: ceo, lead`. No env var, flag, or `--force` widens the list. **Call site is C2a precedence step 1** — the validation MUST run before the record is read or the state inspected, so an invalid actor is refused even on an already-closed mandate (analyze pass-2 F-01; test `test_close_by_invalid_rejected_even_when_already_closed`, T003). Add a one-line comment pointing at contracts C2a as the single edit site for the roster, and noting the roster is ⚠ operator-unconfirmed (no Task Authority roster file exists in-repo). **Supersedes the struck comment-only task** (old T034, which was an unenforceable mitigation for plan risk R-A). (FR-005a, C2a, I7). Depends on T024. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: fail-closed authorization guard on the same close-verb path as T024 — no longer comment-only; exact stderr string is a CLI contract.
- [x] T035 [P] Add a docs-only note (no functional change) — one line in `skills/codex-bridge/SKILL.md`'s `ask.sh` section: "a prompt argument starting with `--` may misparse as a flag; pre-existing limitation, out of scope for this feature (R-D)." (R-D). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-2** (`gpt-5.4-mini` → Gemini free tier → OpenRouter free-tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: docs-only note per this dispatch's explicit R-D instruction (not functional).
- [x] T036 [P] Update `skills/codex-bridge/SKILL.md`: document `submit` flags (C1), exit codes 7/8/9, `mandate` verb group (C2), bridge 409 response (C3) (C6). **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-2** (`gpt-5.4-mini` → Gemini free tier → OpenRouter free-tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: plan.md §Dispatch names "SKILL.md sentences" as canonical free-grunt work; this is a docs-transcription task against already-fixed contract tables.
- [x] T037 Create `specs/010-persistent-exec-session/pr-description-note.md` stating verbatim: "v1 scope = Codex `codex exec` path only (astra/sol/terra/luna via `agent.sh`); Claude `Agent`-tool path and free-model wrapper (Gemini/Mistral/OpenRouter) continuity are deferred past v1 per clarify Q2 / #15 scoping comment." The implement-phase PR-authoring task (Gate I-G8) copies this verbatim into the PR description. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-2** (`gpt-5.4-mini` → Gemini free tier → OpenRouter free-tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: verbatim-text file, no judgment.
- [x] T038 Run `python3 -m unittest discover -s tests -p 'test_*.py'`; confirm all pass including the two new files; confirm `grep -c "def test_" tests/test_mandate_session.py tests/test_bridge_thread_id.py` totals ≥10 (Gate I-G1 prep). Depends on every other T0xx task above, incl. T041–T046. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: verification gate — Supervisor pastes verbatim output per plan.md "never self-grades" discipline (Executive still issues the phase verdict).
- [x] T039 Run `bash -n` + `shellcheck` on `ask.sh` and `preflight.sh`; confirm clean (Gate I-G3 prep). Depends on T014, T033. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: mechanical lint run.
- [x] T040 **Step 1a/1b roster verification FIRST (constitution P7, analyze pass-2 W-13):** before any quickstart step, run the `workerbee` Step 1a/1b runtime roster verification and paste its verbatim output; confirm each slug the script uses (`gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`) is present on the verified roster, and substitute the verified equivalents where it is not, recording each substitution in the transcript. A stale-slug failure is a **precondition failure, not an SC-002 failure**, and must be reported as such rather than as a feature RED. Then execute `quickstart.md` end-to-end live against the running bridge, with special attention to steps 1–3 (R-B: Executive role X opened, Supervisor role Y opened as a *separate* thread, Executive resumed — confirm the resumed reply contains OCELOT-41 and the Supervisor's own thread shows no cross-talk); capture the full transcript to `specs/010-persistent-exec-session/evidence/quickstart-<date>.txt` (Gate I-G4/I-G5, SC-002, SC-006, R-B). Depends on T038. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: live end-to-end verification against a real bridge process — judgment call on pass/fail per step, results still Executive-graded per plan.md P3.

**RESOLVED (2026-09-12/13):** operator explicitly authorized Codex-bridge use for this one task ("codex is available if you want to address this"), lifting the standing ban for T040 only. Executed live by Sonnet (Supervisor-self, this task's own dispatch assignment). Roster re-verified live first (all 3 slugs current, no substitution needed). Full 12/12-checkpoint transcript: `specs/010-persistent-exec-session/evidence/quickstart-2026-09-12.txt`.

**Incident during the run, not a spec-010 defect:** the first attempt showed identical thread_id across two independently-fresh role engagements — looked exactly like the isolation bug this spec fixes. Root cause: the long-running bridge process (PID 93590, started 2:31PM) was still running pre-spec-010 code (bridge.py last modified 19:09, committed 21:26) — a stale process, not a code defect. Confirmed via two bare `codex exec` calls bypassing the bridge (distinct thread_ids both times). Fixed by restarting the bridge (`down.sh`/`up.sh --force`); re-ran clean from step 1 on a fresh mandate. See evidence file for full detail. LESSON-CANDIDATE (unchecked vs `docs/DECISIONS.md` canon): a live acceptance run against a long-lived server process should confirm/force the process reflects current source before trusting results.

T001-T046: all complete.

**EXECUTIVE RULING (Fable, 2026-09-12, independently verified):** BLOCKED state confirmed, not rubber-stamped — `evidence/` dir is empty (`ls specs/010-persistent-exec-session/evidence/` → nothing), so Gates I-G4/I-G5 (plan.md:171-172) are unmet and I-G8's "links quickstart evidence" clause (plan.md:175) cannot be satisfied yet. Verified independently: `python3 -m unittest discover -s tests` → `Ran 541 tests`, 1 failure = `test_config_schema.test_no_third_party_dependency_added` (asserts `pip freeze` count == 28, observed 44; environment-dependent, file unchanged on this branch per `git log -- tests/test_config_schema.py`, not caused by spec-010); `py_compile` on `bridge.py` + `agent_runner.py` OK; `bash -n` on `ask.sh` + `preflight.sh` OK. **Ruling:** (1) T040 stays open; the ban is the operator's and this Executive does not lift it. (2) Branch may be opened as a **draft PR now** — the change is additive and FR-012 back-compat is test-pinned (T046), so no regression risk to existing callers. (3) **Merge is blocked** until one of: (a) operator authorizes a single live quickstart run (T040 executes, transcript lands in `evidence/`, I-G4/I-G5/I-G8 graded), or (b) operator explicitly accepts merging with risk R-B (plan.md:182 — alternating two-thread resume from one bridge process is asserted, never demonstrated; stub `ask.sh` is the whole transport in every test, so unit green says nothing about R-B) unproven. Option (b) requires a recorded operator decision, not Executive discretion, because an R-B failure is a plan change per plan.md:182. PR body MUST state T040 open + R-B unproven verbatim, not as a footnote.

### Analyze-fix tasks (added 2026-09-12 after the adversarial Opus pass — blocking #1/#2/#3/#5 + warnings (d)/(g))

- [x] T041 **[MANDATORY — mandate × follow-up interaction test]** Write `test_mandate_dispatch_does_not_disturb_pending_followup_thread` in `tests/test_bridge_thread_id.py` **and** `test_followup_rejects_mandate_flags_exit2` in `tests/test_mandate_session.py`. First test: open a global-thread conversation (no `thread_id` in body), record the server's global thread attribute, issue a caller-supplied-`thread_id` mandate request, then assert the global attribute is byte-identical and a subsequent global-thread request still resumes the *original* global thread. Second test: `follow-up` with any of `--mandate/--role/--fresh/--force` exits 2 with `agent: follow-up does not accept mandate flags in v1; use submit --mandate` (contracts C1a, FR-014, I6). Depends on T009, T013. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: assertion scaffold against an explicitly specified contract (C1a + C3), no design judgment.
- [x] T042 [US2] Write `test_engaging_other_role_leaves_executive_session_untouched` in `tests/test_mandate_session.py`: after opening role `executive` under mandate M, engage role `supervisor`; assert `roles.executive.engagements` length unchanged, `roles.executive.thread_id` unchanged, `roles.executive.in_flight_job_id` is null (US2 acceptance scenario 2, "Executive incurs no cost when not escalated"). **Replaces the bare "confirmed by inspection" evidence** for that scenario (analyze warning (g)). Depends on T007. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid — Haiku permitted under the standing workstream override, Dispatch key), effort low, why: pure assertion task on an existing record shape.
- [x] T043 Implement the state-dir containment guard in `agent_runner.py` (FR-015, I8): resolve `CODEX_BRIDGE_AGENT_STATE_DIR` and refuse with exit 2 + stderr `agent: mandate state dir must be outside the repo and outside ~/.claude` when the resolved path lies inside the repository root or under `~/.claude/`. **Repo-root resolution is pinned by contracts C7** (added 2026-09-12, round-3 fix N-W11 — the check previously named no method): primary `git rev-parse --show-toplevel` with `cwd` = `Path(__file__).resolve().parent`, `check=False`, 10 s timeout; fallback = nearest ancestor of `Path(__file__).resolve()` containing a `.git` entry; neither resolves → skip the repo clause, keep the `~/.claude/` clause; compare fully-resolved paths with `is_relative_to`, equality counts as inside; **never** anchor on the caller-settable `CODEX_BRIDGE_SCRIPTS_DIR` (`agent_runner.py:25`). Add `test_repo_root_resolution_prefers_git_toplevel_and_falls_back_to_dot_git`. Also write `test_state_dir_inside_repo_refused` and `test_state_dir_under_dot_claude_refused` in `tests/test_mandate_session.py` (test first, RED). Depends on T006. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: path-resolution guard on the store's entry point, coupled to T006's state-dir code.
- [x] T044 Enforce the renumbered exit codes end-to-end (analyze blocking #3): replace every 3/4/6 refusal code with **7/8/9** in `agent_runner.py`'s mandate paths (**plus 10** for the in-flight `close` refusal, round-3 fix N-C2), and add `test_mandate_exit_codes_do_not_collide_with_route_sh` asserting that no mandate **state** refusal returns 3, 4, 5, or 127 (the codes `route.sh` and the existing runner already own) and that the mandate state codes are exactly `{7, 8, 9, 10}`. The **usage** class deliberately reuses exit 2 (C1a, C2a, FR-015) — the test MUST assert those three paths return 2, not a new code, so the reuse is intentional and pinned rather than accidental (round-3 fix N-W2). Depends on T013, T016, T024, T030. **Dispatch**: Supervisor-self (Sonnet, Orchestrator rung; scope-retention row **PT-1** in plan.md — not a promotion: no rung move, no promotion trigger), fallback chain **FC-S** (Supervisor-self → on two failed checks promote one rung up, same vendor per `CLAUDE.md`; never down-delegated to a free grunt, never Codex), effort medium, why: exact-string/exit-code CLI contract, same author as T030 to guarantee match.

### Analyze-fix tasks — 2nd pass (added 2026-09-12 after `analyze-2026-09-12b.md`: F-03, W-10)

- [x] T045 **[MANDATORY — SC-001 measurement on the real code path]** Write `test_submit_mandate_prompt_body_byte_identical_no_preamble` in `tests/test_mandate_session.py`. Extend the T001 stub `ask.sh` so it **records the argv/body it was handed** (e.g. writes them to `$CODEX_BRIDGE_STUB_CAPTURE`) in addition to echoing canned JSON. The test then: (1) opens role `executive` under mandate M with a long briefing prompt via `submit --mandate`; (2) issues a **round-2** `submit --mandate --role executive` with a short caller input `Q`; (3) asserts the captured outbound `prompt` for round 2 equals `Q` **byte-for-byte** (`captured == Q` and `len(captured) == len(Q)`) — no briefing text, no transcript, no mandate preamble prepended anywhere in `agent_runner.py`; (4) asserts the round-2 record has `mode == "resumed"` so the assertion is known to be on the resume path. **No provider call**: the stub is the whole transport, so this test is the authoritative SC-001 signal and is safe to run repeatedly. **Why this task exists:** the previous pass put the SC-001 assertion in `quickstart.md` step 3a against a hand-built `ask.sh --thread` invocation — a *different* call path from `submit --mandate`, which could not detect a preamble injected by the runner, and which issued a live unrecorded provider turn that mutated the system under test between quickstart steps 3 and 5/6 (analyze pass-2 F-03). (SC-001, CHK034, spec.md SC-001 "Primary evidence"). Depends on T001, T015. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (`gpt-5.4-mini` → OpenRouter free-tier → Gemini free tier → Mistral free tier; never Codex, never paid; **note**: per the operator override recorded in `analyze-2026-09-12b.md` §12, Haiku is authorized for this workstream's free-grunt tasks while the free tier is dead on this machine — re-probe free tiers before the dispatch wave), effort low, why: assertion scaffold plus a mechanical stub extension, against an explicitly specified capture shape.
- [x] T046 **[FR-012 backward compatibility]** Write `test_submit_without_mandate_has_no_mandate_key` in `tests/test_mandate_session.py` (a `submit --backend codex "ping"` with **no** mandate flags produces a job/`result.json` carrying **none** of the keys `mandate`, `role`, `mode`, `prior_engagement`, and creates no file under `STATE_DIR/mandates/`) **and** `test_ask_sh_body_omits_thread_id_when_flag_absent` in `tests/test_bridge_thread_id.py` (the POST body built by `ask.sh` without `--thread` contains no `thread_id` key at all — not `null`, absent). Closes the gap that FR-012's "existing `submit` invocations MUST behave exactly as today" was the only FR with no test task, resting solely on pre-registered CHK001/CHK002 and manual Gate I-G2 (analyze pass-2 W-10). (FR-012, CHK001, CHK002, Gate I-G2). Depends on T013, T014, T015. **Dispatch**: free-grunt — model `gpt-5.4-mini`, fallback chain **FC-1** (same roster + the §12 operator override note as T045), effort low, why: pure negative-assertion scaffold against an already-specified contract.

**Checkpoint**: all FR/contract/edge-case/risk coverage closed; re-run of the independent `/speckit-analyze` pass is the gate (this task list does not self-grade) (next dispatch, Opus adversarial).

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS every user story phase (store + `engage()` + bridge plumbing are shared).
- **US1 (Phase 3, P1)**: depends on Phase 2 only. This is the MVP slice — ships SC-001/SC-002.
- **US2 (Phase 4, P2)**: depends on Phase 2 + Phase 3 (reuses `submit --mandate` wiring from T013/T015 to demonstrate the backstop scenario; the docs sentence T019 is independent).
- **US3 (Phase 5, P3)**: depends on Phase 2 only (does not need US1's `--thread` wiring — close/list/show operate on the record directly). Can run in parallel with US1/US2 if staffed.
- **US4 (Phase 6, P3)**: depends on Phase 2 + T013 (needs `submit --mandate` flags to exist for the CLI wiring in T030). Guard *logic* (T007) is already done in Foundational; this phase is CLI-surface + tests only.
- **Polish (Phase 7)**: depends on all of Phase 2–6 (T038 test-suite run and T040 quickstart run are true end-of-line gates).

## Parallel Execution Notes

- All `[P]`-tagged test-writing tasks within a phase are independent files/functions and can run in parallel (different test methods in the same file — assign to separate free-grunt calls only if the fixture in T001 is already merged, otherwise serialize to avoid file-write races on `tests/test_mandate_session.py`).
- Free-grunt tasks (all `[P]` docs/test-scaffold/bash-flag rows) may run concurrently with each other; Supervisor-self tasks (`agent_runner.py`/`bridge.py` logic) are serialized against each other because they share the same two files.
- US3 and US4 phases can proceed in parallel with each other once Phase 2 + T013 land (US3 does not need T013; US4 does).

## FR / Contract / Edge-Case / Risk → Task Coverage Matrix

**Inlined 2026-09-12 (analyze pass-2 W-02).** Previously this section pointed at a handoff report, which made Gate T-G1/T-G2 — both of which demand "a FR→task matrix **in tasks.md**" — un-gradeable from the artifact. The matrix now lives here as the single copy; the handoff report cites this section instead of duplicating it.

### Functional requirements

| req | tasks |
|---|---|
| FR-001 | T010, T015, T006 |
| FR-002 | T003, T011, T007, T015 |
| FR-003 | T003, T010, T013, T015 |
| FR-004 | T003, T021, T007, T024 |
| FR-005 | T020, T024 |
| FR-005a | T003, T034 |
| FR-006 | T003, T026, T027, T007, T030, **T023, T024** (exit-10 in-flight `close` refusal, N-C2) |
| FR-007 | T003, T028, T029, T007, T030 |
| FR-008 | T005, T009, T016 |
| FR-009 | T002, T006, T012 |
| FR-010 | T010, T015 |
| FR-011 | T004, T008 |
| FR-012 | T013, T014, T041, **T046** (backward-compat half — was untested, W-10) |
| FR-013 | T031, T032, T033 |
| FR-014 | T005, T009, T041, **T014, T015** (`fresh` isolation on the non-resume half, N-C5) |
| FR-015 | T043 (incl. C7 repo-root resolution, N-W11) |

### Invariants (data-model.md)

| invariant | tasks |
|---|---|
| I1 | T003, T021, T024 |
| I2 | T026, T027, T007, T030 |
| I3 | T003, T011 |
| I4 | T004, T008 |
| I5 | T012 |
| I6 | T005, T041, T009 |
| **I9** (exactly one of `thread_id`/`fresh` per mandate engagement) | T005, T009, T014, T015 |
| I7 | T003, T034 |
| I8 | T043 |

### Contracts (contracts/cli-and-bridge.md)

| contract | tasks |
|---|---|
| C1 | T013, T016, T030, T044, T036 (incl. exit 10 via T023/T024, and the exit-2 usage class via T044) |
| C1a | T041, T036, **T013** (`follow-up` must *declare* the flags before it can refuse them, N-W10) |
| C2 | T023, T024, T025, T032 |
| C2a (incl. precedence rule) | T003, T024, T034 |
| C3 (incl. edit-locus rule 6 + the `fresh` field) | T005, T009, T014, T015, T041 |
| C4 | T014, T046 |
| **C7** (repo-root resolution for FR-015) | T043 |
| C5 | T033 |
| C6 | T019, T035, T036 |

### Success criteria

| SC | tasks / gates |
|---|---|
| SC-001 | **T045** (authoritative, stubbed byte-identity), **T015** (`result.json.prompt`, the field quickstart 3a-ii reads — N-C1), quickstart 3a/3a-ii via T040, CHK034 |
| SC-002 | T040 (live quickstart steps 1–4), T011 |
| SC-003 | T026, T027, T030 |
| SC-004 | T021, T024 |
| SC-005 | T012 |
| SC-006 | T040 (transcript), T037 + Gate I-G8/I-G9 |

### Edge cases (spec.md `### Edge Cases`)

| edge case | tasks |
|---|---|
| resume target purged | T005, T016 |
| run root dies mid-mandate | T012 |
| vendor without resume | T004, T008 |
| two mandates, same role | T022 |
| mandate never closed (7d warn) | T031, T032, T033 |
| `--force` duplicate override | T027, T030 |
| `follow-up` under a mandate | T041, T013 |
| fresh mandate engagement must not join the global thread (N-C5) | T005, T009, T014, T015 |
| state-dir env override | T043 |

### Risks (plan.md)

| risk | carrier |
|---|---|
| R-A | CLOSED by T034 (real validation) |
| R-B | T040 (live steps 1–3 are the proof) |
| R-C | T005 (`test_global_thread_path_unaffected_when_thread_id_absent`) |
| R-D | T035 (docs-only note) |
| R-E (concurrency / corrupt record) | **deferred post-v1 by design** — plan.md § Analyze disposition pass 2, W-14; no v1 task |

**Zero-coverage check**: no FR, invariant, contract row, or SC is without a task or a named gate. Partial coverage remaining: none (FR-012 closed by T046, SC-001 closed by T045, I9/C7 closed by the round-3 fix rows above).

## Implementation Strategy

MVP = Phase 1 + Phase 2 + Phase 3 (US1) only — delivers SC-001/SC-002, the core defect in #15. Phases 4–6 layer on P2/P3 scenarios; Phase 7 closes out FR-013 + docs + evidence capture required before `/speckit-analyze`.
