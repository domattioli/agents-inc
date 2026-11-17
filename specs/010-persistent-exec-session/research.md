<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Research: 010-persistent-exec-session (Phase 0)

All findings from direct repo reads 2026-09-12 (no sub-delegation; file:line cited). Resolves every Technical Context unknown in `plan.md`.

## R1 — Where the Codex dispatch path actually lives

- **Decision**: The v1 integration point is `skills/codex-bridge/scripts/agent_runner.py` (`submit` → `make_command` → `ask.sh` → HTTP `POST /prompt` on `bridge.py`). Not the bare `codex exec` rows in `skills/workerbee/SKILL.md`.
- **Evidence** (re-verified 2026-09-12, analyze pass-2 re-grep): `agent_runner.py:154-161` `make_command()` builds `[ask.sh, --reset?]` for backend `codex` (the earlier cite `:149-152` was the backend-*selection* `die`/return block, not the command builder); `ask.sh:76-90` builds the JSON body `{prompt, reset, model?}` in a `python3` heredoc and `ask.sh:92-100` `curl`-POSTs it to `127.0.0.1:$PORT/prompt`; `bridge.py:190-196` builds `codex exec -s <sandbox> -m <model> [resume <thread_id>] --json ...`.
- **Rationale**: #15 c1 names "`skills/codex-bridge/scripts/agent_runner.py`, or wherever future Exec/Super dispatch helpers land". Routing through the runner gives job ids + `result.json` (already preferred by `workerbee/SKILL.md` Step 1a footnote).
- **Alternatives rejected**: (a) direct `codex exec resume` from the runner bypassing the bridge — loses the bridge's sandbox/usage-ledger/lock; (b) SKILL.md prose-only (clarify Q3 option C) — rejected by operator.

## R2 — Today's "session" is one global bridge thread, not per-role

- **Finding**: `bridge.py:431` `self.thread_id = None` **initializes** the single server-object thread; `bridge.py:194-195` resumes it; the two places it is **written** are `bridge.py:216` (success path, `self.server.thread_id = obj.get("thread_id")`) and `bridge.py:298` (same assignment in the resume-failure retry block); it is **read** at `:238`, `:248`, `:319`, `:331`, `:383`; `bridge.py:182`, `:268` and `:397-398` (`/reset`) null it; `bridge.py:432` `codex_lock` serializes all prompts. (Write-site cites corrected 2026-09-12 by analyze pass-2 F-02 — the earlier text cited only the initializer `:431`.) `ask.sh --reset` maps to that global reset (`agent_runner.py:159-160` in `make_command`, corrected 2026-09-12 in the pass-2 re-grep — `:151` is the backend-selection `die`; `:377` help text "reset a persistent Codex … session").
- **Consequence**: Per-(mandate, role) persistence CANNOT be built on `--reset` alone; the bridge must accept a caller-supplied `thread_id` to resume, or the whole design collapses back to one shared conversation across every role.
- **Decision**: Extend the `POST /prompt` body with optional `thread_id` (string). If present → `codex exec … resume <thread_id>` regardless of the server's global id; response already echoes `thread_id` (`bridge.py:236-241`). Global-thread behaviour unchanged when field absent (FR-012 backward compat). **Correction 2026-09-12 (analyze blocking #1)**: the echo at `:236-241` currently reads the *server attribute* that the event loop has already overwritten at **`bridge.py:216`** (and, on the retry path, at **`:298`**). On the caller-supplied path the response MUST instead carry a **request-local** observed id and the server attribute MUST NOT be written at all — contracts C3 "request-local thread_id rule". Without that, the feature both violates C3 and lets a mandate dispatch hijack the global thread a pending `follow-up` depends on.
- **Alternative rejected**: one bridge process per role — heavier, no lock sharing, port sprawl.

## R3 — Session identifier capture

- **Finding**: bridge response JSON carries `thread_id` (`bridge.py:238`, `codex-bridge/SKILL.md:85`). `ask.sh --raw` returns full JSON (`ask.sh:135-148` — `if [[ "$RAW" == true ]]` at `:135`, flag parsed at `:50`); without `--raw` only `.response` text. (Cite corrected 2026-09-12, analyze pass-2 W-06; was `:135-137`.)
- **Decision**: the runner invokes `ask.sh --raw` when `--mandate` is given, parses `thread_id`, stores it in the mandate record and in the job's `result.json`. Existing non-mandate jobs keep current behaviour.

## R4 — Persistence store for mandate records

- **Finding**: runner state already file-backed at `STATE_DIR = ~/.codex-bridge/agents` (`agent_runner.py:26-28`, corrected 2026-09-12 per analyze pass-2 W-06; docstring lines 3-6 "survive the calling shell … never require a daemon"). Env override `CODEX_BRIDGE_AGENT_STATE_DIR` exists → tests can redirect.
- **Decision**: `STATE_DIR/mandates/<run_id>.json`, mode 0600, atomic write (tmp + rename), one file per mandate. Satisfies FR-009 (survives caller process) and SC-005.
- **Note on P1 (repo-scoped writes)**: this is the runner's existing runtime state dir, not a repo write and not `~/.claude/**`; same class as today's `job-*/` dirs. Flag for analyze, not a violation.
- **Alternative rejected**: SQLite via `workerbees/store.py` — that schema is shared, has the `tier CHECK` gotcha (D35 addendum), higher blast radius.

## R5 — Mandate identity = ledger `run_id`

- **Finding**: `workerbees/ledger.py:70-71` `record_dispatch(..., run_id, ...)`; `CONTEXT.md:27` Run "identified by run_id". `skills/speckit-pipeline/scripts/ledger_bridge.py:120` `cmd_new_run` (full path added 2026-09-12 in the pass-2 re-grep; line verified) mints run ids for speckit phases.
- **Decision** (clarify Q1=A): mandate id **is** a `run_id`. The ledger is **read-only context** for this feature: a mandate borrows an existing `run_id`, and dispatch under a mandate passes that `run_id` through unchanged wherever the caller already records to the ledger. Ledger schema untouched.
- **Struck 2026-09-12 (analyze warning (e))**: the earlier claim "`mandate close` writes a ledger event" is removed — no task implemented it, and implementing it would cross tasks.md's scope guard (no `workerbees/**` edits) and R4's rejection of the shared SQLite store (`tier CHECK` gotcha, D35 addendum). Close audit is served by the mandate record's `closed_by` / `closed_at` / `close_reason` fields (data-model.md). **Ledger emission on mandate close = post-v1 follow-up**, not a v1 claim.

## R6 — Duplicate in-flight guard

- **Finding**: job status lifecycle exists (`queued` → running → `TERMINAL` set at `agent_runner.py:43`, corrected 2026-09-12 per analyze pass-2 W-06). A mandate record can hold `in_flight_job_id` per role.
- **Decision** (Q4=A): on `submit --mandate M --role R`, if record shows a non-terminal job for R → exit **7** (renumbered from 3 — `route.sh:209` already owns 3, see contracts C1) with `mandate M role R in flight: <job_id>`; `--force` bypasses and appends `{force: true, by: <USER/env>, at, prior_job}` to the mandate record's `overrides` list. Non-terminal detection re-reads the job file (a crashed worker must not wedge the role forever — treat `interrupted`/`failed` as terminal per `TERMINAL`).

## R7 — Model mismatch surfacing (FR-007)

- **Finding**: bridge chooses `model = data.get("model") or self.server.default_model` (`bridge.py:175`, corrected 2026-09-12 in the pass-2 re-grep — `:172` is a bare `return`); `ask.sh --model` exists (`ask.sh:42`, corrected 2026-09-12 per analyze pass-2 W-06; body-build site `ask.sh:86-87`) but the runner never passes it (`make_command` has no model arg).
- **Decision**: mandate record stores `model` per role at first engagement; runner gains `--model` passthrough (needed anyway to pin a rung's slug); re-engagement with a different `--model` → exit **7** `model mismatch: session opened with X, requested Y` unless `--force`.

## R8 — Resume failure semantics (FR-008)

- **Finding**: bridge already retries fresh on resume failure and reports `session_restarted: true, previous_thread_id` (`bridge.py:266-322`). That silently replaces the conversation — exactly what FR-008 forbids for mandate calls.
- **Decision**: when `thread_id` is caller-supplied, bridge MUST NOT auto-restart; return HTTP 409 `{"error":"resume failed","thread_id":...,"stderr":...}`. Runner surfaces it; operator re-runs with `--fresh` (new flag, mandate-scoped) which records `replaced_thread_id` in the record. Global-thread path keeps its existing auto-restart.

## R9 — Preflight warning for stale mandates (FR-013)

- **Finding**: `skills/speckit-pipeline/scripts/preflight.sh` is speckit-phase-only; the repo has no generic session-start hook in-tree (root `CLAUDE.md` "Session start" is prose). `agent.sh list` (subparser `agent_runner.py:402`, dispatch `:444`; corrected 2026-09-12 in the pass-2 re-grep — `:440-455` spanned the `result` verb) is the natural read surface.
- **Decision**: add `agent.sh mandate list` printing open mandates with age; emit `WARN: mandate <id> open <N>d` for age > 7d. Wire one line into `preflight.sh` (non-blocking, after the `.specify` check). Whether a broader session-start hook should call it is deferred (out of scope; note in handoff).

## R10 — Tests

- **Finding**: `tests/` = 43 unittest modules; `tests/test_dispatch_contract.py` tests `check_dispatch_prompt.py` (prompt-contract linter), **not** dispatch behaviour — #15 c3 item 6's pointer is inexact.
- **Decision**: new `tests/test_mandate_session.py` (unittest, `CODEX_BRIDGE_AGENT_STATE_DIR` → tmp, `CODEX_BRIDGE_SCRIPTS_DIR` → a stub `ask.sh` that echoes canned JSON). Covers: fresh-vs-resume branch, dup refusal + force, model mismatch, close → refuse, 7-day warn, resume-failure surfacing. Bridge change covered by `tests/test_bridge_thread_id.py` using `bridge.py`'s handler with a stubbed `subprocess.run`.

## R11 — `codex exec resume` availability

- Verified 2026-09-12: `codex exec --help` lists `resume  Resume a previous session by id or pick the most recent with --last` and `fork`. Matches #15 c1 and A4.
