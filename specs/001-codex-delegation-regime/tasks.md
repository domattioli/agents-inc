---
description: "Task list for Codex Bridge + Multi-Model Delegation Regime"
---
<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->

# Tasks: Codex Bridge + Multi-Model Delegation Regime

**Input**: Design documents from `/specs/001-codex-delegation-regime/`
**Prerequisites**: plan.md, spec.md

**Tests**: Shell smoke tests included. The spec's edge cases are all "degraded path looks like success" failures, which only end-to-end probes catch.

## Format: `[ID] [P?] [Story] Description` → **Delegate: <who>**

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4 per spec.md, or SETUP/POLISH
- **Delegate**: which executor performs the task, per the operator's `CLAUDE.md` coding-dispatch rule and the routing policy this feature defines

### Delegation legend

| Marker | Executor | Applies to |
|---|---|---|
| **HAIKU** | Haiku subagent via Agent tool | All code and script authorship. Binding per `CLAUDE.md` coding-dispatch policy — main session plans and verifies but does not write code. |
| **MAIN** | This Claude session | Planning, prose docs, policy authorship, review, integration, verification of delegated output. Never code. |
| **FABLE** | Fable subagent, low effort, read-only | Adversarial plan review. Cannot write; reports findings only. |
| **CODEX** | Codex backend via `ask.sh` | Demonstration and dogfooding calls. Not used to author repo code — that stays HAIKU per policy. |
| **GEMINI** | Gemini backend via `gask.sh` | Demonstration and bulk-digest calls. Same restriction. |

**Verification rule**: every HAIKU task is followed by MAIN reading the produced artifact. A subagent's self-report is not evidence — two defects in this feature (wrong `resume` argument order, `--skip-git-repo-check` omission) passed subagent smoke tests and were caught only by MAIN reading the code.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [SETUP] Create `.specify/` scaffolding, `specs/001-codex-delegation-regime/`, and `feature.json` → **Delegate: MAIN** *(complete)*
- [ ] T002 [SETUP] Create `.gitignore` at repo root excluding `__pycache__/`, `*.log`, `state.json`, and any `*token*` / `*key*` / `*secret*` path, so credentials can never be committed even if copied in-tree → **Delegate: HAIKU**
- [ ] T003 [SETUP] Verify `~/.codex-bridge/` holds `token` and `gemini-key` at mode 600 and that the directory is 700 → **Delegate: MAIN**

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ No user story work proceeds until these land.**

- [X] T004 [FOUND] `bridge.py` — HTTP service, token auth, `/prompt` `/health` `/session` `/reset`, error taxonomy → **Delegate: HAIKU** *(complete, verified)*
- [X] T005 [FOUND] `bridge.py` — persistent Codex thread with lock-serialized invocation and stale-resume recovery → **Delegate: HAIKU** *(complete, verified live: thread survives across calls)*
- [ ] T006 [FOUND] `bridge.py` — make stale-resume recovery **visible**: add `"session_restarted": true` to the response when a resume failed and a fresh session was substituted (FR-013, SC-005). Currently the substitution is silent, which is the exact anti-pattern the spec forbids → **Delegate: HAIKU**
- [ ] T007 [FOUND] `bridge.py` — distinguish rate-limit exhaustion from generic non-zero exit: detect quota/rate-limit markers in stderr and return HTTP 429 with `{"error":"rate limited"}` rather than a bare 502 (FR-009, edge case 1) → **Delegate: HAIKU**
- [ ] T008 [FOUND] MAIN reads T006–T007 diffs and confirms behavior against FR-009/FR-013 before dependent work starts → **Delegate: MAIN**

---

## Phase 3: User Story 1 — Offload bulk reading (Priority: P1) 🎯 MVP

**Goal**: Bulk material is read by a backend, never by the Claude conversation.
**Independent test**: Ask a question spanning 20+ files; verify the answer is right and the transcript contains no file contents.

- [ ] T009 [P] [US1] Write `skills/codex-bridge/scripts/gask.sh` — Gemini leg. Args `[--model M] [--tier digest|cheap|deep] [--file PATH]... [--glob PATTERN] [--raw] "prompt"`, prompt also accepted on stdin. Reads key from `~/.codex-bridge/gemini-key`, POSTs to `generativelanguage.googleapis.com/v1beta/models/<model>:generateContent`. **Critical**: the script reads file contents itself and embeds them in the request body — file bytes must never be printed to stdout or returned to the caller (FR-021, SC-001). Build the JSON body with `python3 json.dumps`, never string interpolation. Print response text on stdout; token counts on stderr → **Delegate: HAIKU**
- [ ] T010 [US1] Tier→model mapping in `gask.sh`: `digest`→`gemini-3.8-flash`, `cheap`→`gemini-flash-lite-latest`, `deep`→`gemini-3.1-pro-preview`; `--model` overrides tier (FR-020) → **Delegate: HAIKU**
- [ ] T011 [US1] `gask.sh` failure handling: missing key file → actionable message naming the path and exit 1; HTTP error → surface Google's `error.status` and `error.message`; input exceeding the model's token limit → refuse before sending with a byte count (FR-027, SC-005) → **Delegate: HAIKU**
- [ ] T012 [US1] MAIN reads `gask.sh` and verifies the never-echo-file-bytes invariant by inspection, not by trusting the smoke test → **Delegate: MAIN**
- [ ] T013 [US1] Live acceptance: run `gask.sh --glob 'skills/codex-bridge/scripts/*.sh' "summarize what these scripts do in 5 bullets"` and confirm a correct digest returns while no script body enters the conversation (SC-001) → **Delegate: MAIN** *(invokes GEMINI)*
- [ ] T014 [US1] Live acceptance: same question via `ask.sh` to Codex, confirming the path-based leg reaches the same conclusion without file bytes crossing the conversation → **Delegate: MAIN** *(invokes CODEX)*

**Checkpoint**: Both legs deliver digests with bulk material excluded from Claude context. MVP achieved.

---

## Phase 4: User Story 2 — One-command startup (Priority: P1)

**Goal**: No manual transcription; idempotent start; loud failure.
**Independent test**: cold start → answered question, transcribing nothing.

- [X] T015 [US2] `up.sh` / `down.sh` / `status.sh` / `ask.sh` with state file and idempotent start → **Delegate: HAIKU** *(complete, verified: double-start leaves one process)*
- [ ] T016 [US2] Extend `up.sh` to record Gemini availability in `state.json` (`"gemini": true|false` based on key-file presence) so a consumer can see which legs are live without probing (FR-016, FR-027) → **Delegate: HAIKU**
- [ ] T017 [US2] Extend `status.sh` to report both legs' availability and the active working-directory boundary (FR-008) → **Delegate: HAIKU**
- [ ] T018 [US2] Change default `--workdir` in `up.sh` from `$HOME` to the current project directory, narrowing what Codex may read (FR-008, spec Assumptions) → **Delegate: HAIKU**
- [ ] T019 [US2] MAIN restarts the service and confirms the narrowed boundary is in effect and reported → **Delegate: MAIN**

**Checkpoint**: Startup is one command and reports the full picture of both legs.

---

## Phase 5: User Story 3 — Routing policy (Priority: P2)

**Goal**: A documented, auditable mapping from work classes to backends.
**Independent test**: a second reader routes sample tasks the same way.

- [ ] T020 [US3] Write `skills/codex-bridge/reference/routing-policy.md`. Contents: the never-through-Claude-context principle; the backend comparison table (fetches own data / sees conversation / marginal cost / trains on input); the work-class routing table; explicit non-delegation list (anything needing conversation context, anything sensitive, code writing); the Gemini free-tier training caveat with its sensitivity exclusion; the unverified-output rule requiring local verification of load-bearing claims (FR-022, FR-023, FR-024, FR-026) → **Delegate: MAIN** *(prose policy, not code)*
- [ ] T021 [US3] Record that routing is automatic per operator ratification 2026-09-02, and that Claude states the route used in its report so egress stays auditable (FR-025) → **Delegate: MAIN**
- [ ] T022 [US3] Update `SKILL.md` to reference the routing policy and document `gask.sh` alongside `ask.sh` → **Delegate: HAIKU**
- [ ] T023 [US3] MAIN reviews `SKILL.md` for accuracy against the shipped scripts → **Delegate: MAIN**

**Checkpoint**: Routing is documented and consistently applicable across sessions.

---

## Phase 6: User Story 4 — Second-opinion debugging (Priority: P3)

- [ ] T024 [US4] Add a "second opinion" recipe to `SKILL.md`: how to phrase a diagnosis request so the backend reasons from code rather than restating a supplied hypothesis (i.e. withhold Claude's hypothesis, supply only the symptom) → **Delegate: HAIKU**
- [ ] T025 [US4] Live acceptance: give Codex a real symptom from this project and confirm the returned hypothesis is code-derived → **Delegate: MAIN** *(invokes CODEX)*

---

## Phase 6b: User Story 5 — Usage ledger and subscription value (Priority: P2)

**Goal**: Know input/output volume per model across all backends, retroactively and deterministically.
**Independent test**: request a report; totals match work actually performed; two runs are byte-identical.

- [ ] T034 [P] [US5] Write `skills/codex-bridge/scripts/usage_report.sh` — read-only scanner. Walks `~/.claude/projects/**/*.jsonl`, extracts `message.model` + `message.usage` per assistant message, aggregates by model. Keeps `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` as four separate columns — never summed together, since they price differently (FR-028, FR-029, FR-032, FR-035) → **Delegate: HAIKU**
- [ ] T035 [US5] Extend the scanner to merge the delegated-backend ledger at `~/.codex-bridge/usage.jsonl` so Codex and Gemini consumption appears alongside Claude's (FR-028) → **Delegate: HAIKU**
- [ ] T036 [US5] `bridge.py` appends one JSON line per request to `~/.codex-bridge/usage.jsonl`: timestamp, backend `codex`, model, input/output counts from the `turn.completed` usage object. Content is never written — counts only (FR-028, FR-036) → **Delegate: HAIKU**
- [ ] T037 [US5] `gask.sh` appends the same record shape from Gemini's `usageMetadata` (FR-028, FR-036) → **Delegate: HAIKU**
- [ ] T038 [US5] Write `skills/codex-bridge/reference/prices.json` — operator-editable per-model metered unit prices, with a comment field noting rates must be updated by hand and are advisory (FR-033) → **Delegate: MAIN**
- [ ] T039 [US5] Report renders equivalent metered cost per model and a subscription-comparison line, and states the covered period plus any gap caused by rotated or absent records (FR-033, FR-034) → **Delegate: HAIKU**
- [ ] T040 [US5] Determinism check: run the report twice with no intervening work, diff the outputs, require byte-identical (FR-031, SC-011) → **Delegate: MAIN**
- [ ] T041 [US5] MAIN verifies the scanner is strictly read-only — opens no file for writing under `~/.claude/`, and adds no hook to the request path (FR-030, SC-014) → **Delegate: MAIN**
- [ ] T042 [US5] MAIN confirms no prompt or response text reaches `usage.jsonl` by inspecting a real record (FR-036) → **Delegate: MAIN**

---
## Phase 7: Operator Acceptance — Tic-tac-toe demo

**Goal**: The operator's stated success criterion — a playable HTML file from each backend, openable in a browser.

- [ ] T026 [P] [ACCEPT] *(gated on T012 — do not run against an unverified client)* Via `ask.sh`, have Codex write `demo/tictactoe-codex.html` — single self-contained file, no external assets, playable two-player or vs-computer, works offline → **Delegate: MAIN** *(invokes CODEX)*
- [ ] T027 [P] [ACCEPT] Via `gask.sh`, have Gemini produce `demo/tictactoe-gemini.html` to the same brief → **Delegate: MAIN** *(invokes GEMINI)*
- [ ] T028 [ACCEPT] MAIN verifies both files: valid HTML, no external network references, win/draw logic correct by inspection, opens standalone → **Delegate: MAIN**
- [ ] T029 [ACCEPT] Report both file paths to the operator with a one-line note on how each backend was invoked, demonstrating the routing record required by FR-025 → **Delegate: MAIN**

---

## Phase 8b: Orphan-FR verification (closes the traceability gaps)

Fable's analyze pass found seven FRs asserted as satisfied by ticked tasks but never independently verified. Each gets an explicit check.

- [ ] T043 [P] [VERIFY] FR-006 — start bridge with `CODEX_BRIDGE_TOKEN` unset; confirm refusal to start and exit non-zero → **Delegate: MAIN**
- [ ] T044 [P] [VERIFY] FR-007 — grep `~/.codex-bridge/bridge.log`, `tunnel.log`, and all script stdout for the token value; must be absent (spec SC-006 has no task today) → **Delegate: MAIN**
- [ ] T045 [P] [VERIFY] FR-010/FR-011 — send an oversize body (>1 MiB) expecting 413; set `--timeout 5` against a slow prompt expecting 504 → **Delegate: MAIN**
- [ ] T046 [VERIFY] FR-012 — fire two concurrent `/prompt` requests; confirm serialization and that the thread is not corrupted → **Delegate: MAIN**
- [ ] T047 [VERIFY] FR-018 — confirm tunnel path degrades with a clear message when `cloudflared` is absent (it is) → **Delegate: MAIN**
- [ ] T048 [VERIFY] FR-019 — confirm each `/prompt` response carries usage counts → **Delegate: MAIN**
- [ ] T049 [VERIFY] FR-038/FR-039 — confirm the sandbox mode and workdir boundary are recorded in state, reported by status, and enforced by the bridge invocation → **Delegate: MAIN**
- [ ] T050 [VERIFY] FR-037 — confirm the usage scanner deduplicates repeated records for one logical response → **Delegate: MAIN**

---
## Phase 8: Polish

- [ ] T030 [P] [POLISH] Write `skills/codex-bridge/tests/smoke.sh` consolidating all endpoint probes: health, auth reject, malformed body, oversize payload, session query, reset, both legs' missing-credential paths. No real API calls → **Delegate: HAIKU**
- [ ] T031 [P] [POLISH] Update root `README.md` to cover both legs, the state file, and a pointer to the routing policy → **Delegate: HAIKU**
- [ ] T032 [POLISH] Add `benchmark.md` under the skill recording the `claude_tokens_saved_per_offloaded_task` baseline from the T013 acceptance run → **Delegate: MAIN**
- [ ] T033 [POLISH] MAIN final review: read every changed file, confirm no credential appears in the project tree → **Delegate: MAIN**

---

## Dependencies

```
Phase 1 (T001-T003)
   └─> Phase 2 (T004-T008)  [BLOCKING]
          ├─> Phase 3 US1 (T009-T014)  ── MVP
          ├─> Phase 4 US2 (T015-T019)
          │      └─> Phase 5 US3 (T020-T023)
          │             └─> Phase 6 US4 (T024-T025)
          ├─> Phase 6b US5 (T034-T042)  [independent of US1-US4; reads existing records]
          └─> Phase 7 ACCEPT (T026-T029)  [needs T009-T011 for the Gemini leg]
                 └─> Phase 8 POLISH (T030-T033)
```

## Parallel Opportunities

- T009 and T016–T018 touch different files and may run concurrently.
- T026 and T027 hit different backends and are independent — run together.
- T030 and T031 are independent polish items.
- T034 (usage scanner) touches no file any other task touches, and depends only on records that already exist — it can run at any point, fully parallel to everything else.

## Implementation Strategy

MVP is Phase 1 → 2 → 3. That alone delivers the token-saving premise. Phase 7 is gated only on the Gemini leg existing, so it can run as soon as T009–T011 land, ahead of Phases 4–6 — which matters because it is the operator's stated acceptance criterion.
