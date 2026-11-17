<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Persistent Executive Session Across a Mandate

**Branch**: `010-persistent-exec-session` (spec dir name; git branch policy per root `CLAUDE.md` — Supervisor works on `development`, no new branch unless operator carve-out) | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/010-persistent-exec-session/spec.md` (clarified 5/5, issue #15)
**Executive of record**: Fable (this plan's author). Supervisor: follow-on Sonnet. Adversarial analyze: separate Opus.

## Summary

`codex exec` dispatch is stateless; #15 needs a role's provider session to persist across re-engagements within one mandate (= one ledger `run_id`, clarify Q1). v1 = Codex path only (Q2): add `--mandate/--role/--model/--fresh/--force` to `agent.sh submit`, one `mandate close` verb (Q3), a per-mandate JSON record in the runner's state dir holding role → `thread_id`, a bridge `POST /prompt` extension that resumes a caller-supplied `thread_id` **or opens an isolated fresh session on `fresh: true`** (research R2 — today the bridge holds ONE global thread, so this is the load-bearing change; both halves are needed, round-3 fix N-C5), duplicate-in-flight refusal with logged `--force` (Q4), never-auto-close + 7-day preflight warning (Q5). Evidence for every design choice: `research.md` R1–R11.

## Technical Context

**Language/Version**: Python 3 (stdlib only — `agent_runner.py`, `bridge.py` are stdlib; keep it so) + bash (`ask.sh`, `preflight.sh`)
**Primary Dependencies**: Codex CLI with `exec resume` (verified R11); `jq` (already required by `ask.sh:8`)
**Storage**: file-backed JSON, `$CODEX_BRIDGE_AGENT_STATE_DIR/mandates/<run_id>.json` (R4)
**Testing**: `unittest` (repo convention, R10); new `tests/test_mandate_session.py`, `tests/test_bridge_thread_id.py`
**Target Platform**: local macOS/Linux dev machine where the bridge runs
**Project Type**: CLI + local HTTP proxy
**Performance Goals**: none new; the guard adds one file read per submit
**Constraints**: additive only — every existing `submit`/`ask.sh`/bridge call unchanged (FR-012); $0 (P5) — validation uses Codex subscription already in use; no new vendors
**Scale/Scope**: single operator, tens of mandates, ≤10 roles per mandate

## Constitution Check

*GATE: passed pre-research; re-checked post-design 2026-09-12.* Constitution v1.7.0 unratified → violations report WARN.

| principle | status | note |
|---|---|---|
| P0 cross-ref | pass | plan cites canon files, restates none |
| P1 repo-scoped writes | pass w/ note | runtime state at `~/.codex-bridge/agents/mandates/` = existing runner state dir class (R4), not `~/.claude/**`, not a repo write. Analyze confirmed the reading; the env-override hole it flagged is now closed by **FR-015** (refuse a `CODEX_BRIDGE_AGENT_STATE_DIR` resolving inside the repo root or `~/.claude/`) |
| P2 labor ladder | pass | Supervisor (Sonnet) leads tasks/checklist/implement; Grunt-tier free models may draft small diffs; Workhorse build only via promotion — plan §Dispatch. Analyze pass-2 W-12 addressed: **PT-1 re-characterized as scope retention, not promotion**, and the granting-authority confusion (Executive ≠ Lead) removed — see §"Promotion-trigger log". Free-grunt chains FC-1/FC-2 draw only from the free roster (no Haiku/Codex/paid) *as written*; note the post-review operator override recorded in `analyze-2026-09-12b.md` §12 (free tier dead on this machine → Haiku authorized for the free-grunt tasks, this workstream only — **count corrected 2026-09-12, round-3 fix N-W3: 30, not 24**; `grep -c 'Dispatch\*\*: free-grunt' tasks.md` → 30), which supersedes the chain tables at implement time and must be re-probed per dispatch wave |
| P3 no self-graded gates | pass | every phase gate below is Executive- or Opus-verified, never Supervisor self-PASS |
| P4 deterministic policy | pass | fail-closed exits **7/8/9/10** (7/8/9 renumbered from 3/4/6 — see contracts C1, `route.sh` collision; 10 added for the in-flight `close` refusal, round-3 fix N-C2), plus the documented exit-2 usage class; `--by` validated against a fixed allowlist (C2a), not a code comment; no prompt-only enforcement |
| P5 $0 | pass | no paid API path added |
| P6 audience rendering | pass | spec/plan machine-facing → caveman ultra prose/tables |
| P7 nickname discipline | pass w/ note | **Correction 2026-09-12 (round-3 fix, N-C4): `canonical_backend` does not validate `--model` at all.** `canonical_backend` (`agent_runner.py:129-137`) takes a **backend** token, not a model slug: it rejects Anthropic *backend* names (`:131-134`, `die(..., 5)` under ultra mode) and unknown backends (`:135-136`), and never inspects `job["prompt"]`'s sibling `--model` value — `grep -n "model" agent_runner.py` returns nothing before T013 adds the flag. So the earlier claim that "Claude ids [are] rejected by existing `canonical_backend`" was a misattribution. Accurate statement: **a bad `--model` slug is not validated locally at any point; the provider rejects it at call time** (a non-zero `ask.sh` exit the runner reports as a failed engagement — fail-closed, but late). What P7 discipline actually rests on here is the **runtime roster verification** (`workerbee` Step 1a/1b) that `quickstart.md`'s Precondition and **T040** make mandatory before any live run, plus the `--model`-mismatch guard (FR-007, exit 7), which pins a role to the slug it was opened with. No local slug allowlist is added: it would be a second roster to drift (P0), and the roster is the thing P7 says never to hard-code. Analyze pass-2 W-13 addressed: quickstart's hard-coded slugs are now explicitly non-authoritative and T040 carries a runtime roster-verification precondition (`workerbee` Step 1a/1b) before the live run |
| P8 prompt contract | pass | Supervisor dispatch prompts must carry 14 elements; gate T-G0 |
| P9 edit hygiene | pass | all changes are insertions into existing files except two new test files |
| P10 lesson routing | pass | LESSON-CANDIDATEs listed in handoff, relayed up only |

## Project Structure

### Documentation (this feature)

```text
specs/010-persistent-exec-session/
├── spec.md                 # clarified
├── clarify-questions.md    # record of Q1–Q5 + answers
├── plan.md                 # this file
├── research.md             # R1–R11
├── data-model.md           # Mandate / RoleSession / Engagement / Override + invariants I1–I9
├── contracts/cli-and-bridge.md   # C1, C1a, C2, C2a, C3–C7
├── quickstart.md           # SC-002 end-to-end validation script
├── checklists/
│   ├── requirements.md                 # specify-phase spec-quality gate (all [x], untouched)
│   ├── requirements-quality.md         # "unit tests for English" — spec wording quality
│   └── implementation-readiness.md     # Gate C implementation-verification checklist (CHK001–CHK040)
├── pr-description-note.md  # created by T037 (verbatim v1-scope note for the PR body)
├── analyze-2026-09-12b.md  # 2nd independent analyze pass (FAIL) — input to the 2nd fix pass
└── tasks.md                # /speckit-tasks output (exists — T001–T046)
```

(Tree refreshed 2026-09-12, analyze pass-2 W-15: it previously omitted both checklists and still said tasks.md was "NOT created here".)

### Source Code (repository root)

```text
skills/codex-bridge/scripts/
├── agent_runner.py     # MODIFY: submit flags, mandate store, guards, `mandate` verb group, result.json fields
├── ask.sh              # MODIFY: --thread <id>, --fresh (C4)
└── (agent.sh unchanged — thin exec wrapper)
bridge.py               # MODIFY: POST /prompt accepts thread_id + fresh (isolated requests); 409 on resume failure for that path
skills/speckit-pipeline/scripts/preflight.sh   # MODIFY: append mandate-age WARN lines
skills/codex-bridge/SKILL.md                   # MODIFY: docs (C6)
skills/workerbee/SKILL.md                      # MODIFY: one sentence after Step 1a roster (C6)
tests/
├── test_mandate_session.py     # NEW
└── test_bridge_thread_id.py    # NEW
```

**Structure Decision**: no new modules. Mandate store lives as functions inside `agent_runner.py` (file is 463 lines; adding ~150 keeps it one-file, matching its "small, local job runner" docstring). If the Supervisor finds it exceeds ~700 lines, split `mandate_store.py` beside it — record that as a deviation in tasks.md, not a silent choice.

## Design (Phase 1 summary — details in data-model.md / contracts/)

1. **Store** (`agent_runner.py`): `load_mandate(run_id)`, `save_mandate(...)` (atomic), `engage(run_id, role, model, backend, fresh, force)` → returns `(thread_id_to_resume | None, mode)` or raises a typed refusal mapped to exit 7/8. `settle(job)` on worker completion: parse `result.json`, write `thread_id`, clear `in_flight_job_id`, set engagement outcome.
2. **Runner submit path**: when `--mandate`: validate flags → `engage()` → build `ask.sh --raw [--model X] [--thread T] prompt` → job record gains `mandate/role/mode/prior_engagement`. `run_worker` already captures stdout (`agent_runner.py:237`); under a mandate it JSON-parses it, writes `result.txt` = `.response`, `result.json` += thread fields, then `settle()`. Bridge 409 → job status `failed`, engagement outcome `resume-failed`, exit 9 on `--wait`.
3. **Bridge**: in `handle_prompt`, read `thread_id` and `fresh` from the body. Either one present ⇒ **isolated request**: build the cmd with `resume <thread_id>` (or, for `fresh: true`, with **no** `resume` argument, ignoring whatever the server holds), write the observed session id to a **request-local** variable only (never onto `self.thread_id`), return that request-local id in the response, leave the server's global thread byte-identical; on non-zero exit of a resume → 409 (no fresh retry) — contracts C3. Neither present ⇒ today's global path, untouched.
   **`fresh` is the round-3 fix for N-C5**: without it a mandate engagement with no stored thread sends no `thread_id`, falls into the global branch at `bridge.py:194-195`, resumes whatever conversation the server was last holding, and overwrites it at `:216` — so "separate role, separate thread" was false for every first engagement. The isolation decision must be **explicit in the body**, not inferred from an absent field.
   **Edit locus (corrected 2026-09-12, analyze pass-2 F-02; `:194-195` re-scoped to a global-path-only branch by the round-3 fix — the earlier locus `:190-200` + `:250-322` omitted the primary write site and would have left the load-bearing unconditional global write in place):** `bridge.py:194-195` (build `resume`), **`:216` (write site, success path)**, `:238` (response echo), `:248` (`resolve_actual_model`), **`:298` (write site, retry path)**, `:319` (retry response echo), `:331` (`resolve_actual_model`), `:250-322` (retry block → 409 on the caller-supplied path). `bridge.py:431` is the initializer and needs no change. ~30 lines total. Re-verified by `grep -n thread_id bridge.py`.
4. **Guards**, evaluated in `engage()` in this order before any job dir is created: **duplicate in flight (I2, exit 7) → model mismatch (FR-007, exit 7) → mandate closed (I1, exit 8)**. This order is normative and is what `quickstart.md` steps 5 → 6 → 8a demonstrate in sequence; a step that wants to exercise the *later* guard must first clear the earlier one (no in-flight engagement before the mismatch check — hence quickstart's explicit `wait`), otherwise the earlier guard fires and the step proves nothing (round-3 fix, N-C2).
5. **Close/list/show** verbs (C2). `close` follows C2a's 5-step pipeline; its in-flight refusal exits **10** unless `--force` (code added by the round-3 fix, N-C2 — C2 previously named no code for it). `list` computes age from `opened_at`; >7d → `WARN:` on stderr.
6. **Preflight** hook line (C5). **Docs** (C6).

## Dispatch plan for the Supervisor (P2 / P8)

- Supervisor = Sonnet, acts as Orchestrator/Supervisor rung. Owns tasks.md, checklist, implement, PR authoring.
- Coding diffs: Grunt-tier via free models where the job is small + well-scoped (bash flag parsing in `ask.sh`, `preflight.sh` line, SKILL.md sentences, test scaffolds). **Free models only** for any sub-delegation: gpt-5.4-mini, OpenRouter free, Gemini free, Mistral free — never Haiku, never Codex, never paid (operator contract carried from this dispatch).

### Free-tier model assignment + fallback chain (binding for every coding task)

Every coding task in tasks.md names a primary free-tier model **and** its fallback chain, used in order when the primary is quota-paused or returns a failed check. Chains draw only from the repo's free roster (`CLAUDE.md` D27 budget modality): `gpt-5.4-mini`, OpenRouter free-tier, Gemini free tier, Mistral free tier. **Never Haiku, never Codex, never any paid tier.** A quota pause counts as one failed attempt toward the two-failed-checks promotion trigger (`CLAUDE.md` "Failed check — definition of record").

| chain id | primary → fallback 1 → fallback 2 → fallback 3 | used for |
|---|---|---|
| **FC-1** | `gpt-5.4-mini` → OpenRouter free-tier (`nemotron-120b` class) → Gemini free tier → Mistral free tier | default for all free-grunt coding/test-scaffold tasks |
| **FC-2** | `gpt-5.4-mini` → Gemini free tier → OpenRouter free-tier → Mistral free tier | docs/prose transcription tasks (Gemini second: better long-prose fidelity) |
| **FC-S** | Supervisor-self (Sonnet, Orchestrator rung) → on two failed checks, promotion per `CLAUDE.md` (same-vendor one rung up), **not** to a free grunt | `agent_runner.py` / `bridge.py` state-machine + CLI-contract edits |

If all four free models in a chain are exhausted, the task **stops and reports** — it does not silently escalate to a paid tier.

### Promotion-trigger log (P2 / `CLAUDE.md` labor rule) — formally recorded

Analyze flagged that "the Supervisor may write the core interface code itself" was asserted in prose rather than logged. Recorded formally here:

| id | named trigger | rung move | reason of record | authority |
|---|---|---|---|---|
| **PT-1** | **Not a promotion — scope retention** (re-characterized 2026-09-12, analyze pass-2 W-12). The earlier wording borrowed the *Lead assigns with a recorded gate reason* promotion trigger, but that trigger governs moves **one rung up**, whereas this row assigns Workhorse-class leaf work **down** to an Orchestrator — which the labor rule does not license as a promotion at all, and it named the granting authority as "Executive of record (Fable)" while `CONTEXT.md:31` makes Lead ≠ Executive by definition. Restated on its own terms: `CLAUDE.md` D27 scopes Grunt coding to small, narrow diffs and **excludes architecturally significant change**; these edits are architecturally significant (below), so they are **Workhorse+ work by rule**, and an Orchestrator has Workhorse capability by construction (rung ladder is cumulative). The Orchestrator therefore **retains** work it is qualified for rather than being promoted into it. No rung move occurs, so no promotion trigger is required or claimed. | Orchestrator/Supervisor (Sonnet) performs Workhorse-class leaf work on `skills/codex-bridge/scripts/agent_runner.py` + `bridge.py` | These edits are a single coupled state machine plus exact-string CLI/exit-code contracts (C1 exits 7/8/9, C3 request-local thread rule). Splitting them across free grunts risks interface mismatch and exact-string drift, which Gate A-G5/T-G5 check by diff; `CLAUDE.md` D27 scopes Grunt coding to small, narrow diffs and explicitly excludes architecturally significant change. Free-grunt sub-delegation is retained for every mechanical leaf (tests, bash flags, docs). | **Recorded by** the Executive of record (Fable) in this plan; because no rung move is claimed, no Lead/operator grant is required. Should a future row genuinely assign a rung move, the granting authority MUST be the operator or the Lead (not the Executive), per `CONTEXT.md:31`. Executive still grades all gates (P3); the Supervisor never self-PASSes. |

Scope of PT-1 is exactly the tasks tagged `Supervisor-self` in tasks.md — it is not a standing licence, and any additional self-assignment needs its own row here.
- Every dispatch prompt: 14-element contract (`CLAUDE.md` "Delegation prompt contract"), lint with `skills/workerbee/scripts/check_dispatch_prompt.py`.
- Verification harness is Supervisor-owned but **results are Executive/Opus-graded** (P3): the Supervisor runs the commands in the gate tables and pastes exact output; it does not declare PASS.

## Phase gates — checkable, per downstream phase

Convention: **PASS** requires every row's `check` to hold with the cited evidence attached (command + verbatim output, or file:line). **FAIL** on any row. The Supervisor never self-grades: the Executive (or the Opus analyze agent for the analyze phase) reads the evidence and issues the verdict. Two Executive-graded RED on the same phase = promotion trigger per `CLAUDE.md` "failed check — definition of record".

### Gate T — `/speckit-tasks` → tasks.md

| id | check | evidence required |
|---|---|---|
| T-G0 | tasks.md exists at `specs/010-persistent-exec-session/tasks.md`, uses `.specify/templates/tasks-template.md` structure | path + first 20 lines |
| T-G1 | Every **FR-001..FR-015, including FR-005a** (range widened 2026-09-12, analyze pass-2 W-01 — the pre-fix range `FR-001..FR-013` excluded the very requirements the fix pass added) maps to ≥1 task id; every task cites ≥1 FR or SC. Every SC-001..SC-006 also maps to ≥1 task **or** a named gate row | the FR→task matrix **inlined in tasks.md** § "FR / Contract / Edge-Case / Risk → Task Coverage Matrix" (W-02: the matrix must be in the artifact, not only in a handoff report) |
| T-G2 | Every contract row **C1, C1a, C2, C2a, C3–C7** and invariant **I1–I9** has a task (ranges widened per W-01, then again 2026-09-12 for round-3 additions C7 / I9) | matrix rows |
| T-G3 | Test tasks precede impl tasks for the same surface (TDD order) and name the exact test file + test function | task text |
| T-G4 | Each coding task states rung + vendor + model + effort + "why this rung"; sub-delegated tasks name a free model only | per-task header |
| T-G5 | No task touches files outside `plan.md` "Source Code" tree; no task edits `workerbees/**` schema, `CONTEXT.md`, `DECISIONS.md` | grep of file paths in tasks.md |
| T-G6 | A task exists for the PR-description note "v1 scope = Codex path only; Claude Agent-tool + free-model paths deferred (#15 comment 5)" | task text |
| T-G7 | A task exists for quickstart.md execution + transcript capture (SC-002/SC-006) | task text |
| **FAIL** | any row missing, or tasks.md invents a requirement absent from spec/contracts without an `[INFERRED]` tag | |

### Gate C — `/speckit-checklist`

| id | check | evidence |
|---|---|---|
| C-G1 | Checklist file(s) under `checklists/` cover: backward compat of `submit` without flags; exit-code table C1; 409 path; **I1–I9** (range widened 2026-09-12 per analyze pass-2 W-01, extended to I9 by the round-3 fix); the bridge `fresh` field (C3); 7-day warn; `--by` allowlist + its precedence rule (C2a); state-dir containment (FR-015); SC-001 measurement; docs C6 | file listing + item ids |
| C-G2 | Each item is binary-checkable (command or file:line), no "ensure quality" style items | read-through |
| C-G3 | `checklists/requirements.md` remains all-checked | file |
| C-G4 | **Every item in every checklist under `checklists/` carries a disposition** — scope widened 2026-09-12 (analyze pass-2 W-03: the row previously named `implementation-readiness.md` exclusively, which left all 24 items of `requirements-quality.md` wholly undisposed — the same defect in a second file). Applies to `implementation-readiness.md`, `requirements-quality.md`, and `requirements.md`, plus any checklist added later: each item is either `[x]` (verified now, with the command/file:line), or explicitly marked `PRE-REGISTERED (implement phase)` / `RESOLVED — <FR/SC cite>` / `N/A — <reason>` in that file's "Disposition status" grouping. An item that is neither checked nor explicitly disposed = gate FAIL | each checklist file's Disposition status section + per-item markers |
| C-G5 | **Second pass at Gate I** (added 2026-09-12, analyze pass-2 OQ-2): every item disposed `PRE-REGISTERED (implement phase)` at Gate C is re-graded at Gate I and flipped to `[x]` (with pasted command output) or RED. A `PRE-REGISTERED` marker surviving into Gate I = FAIL. Rationale: `PRE-REGISTERED` is honest before code exists but is not a substitute for the check | the checklist files re-read at Gate I, zero `PRE-REGISTERED` markers remaining |
| **FAIL** | any C1/C3 contract row lacks a checklist item, any checklist item is left undisposed (C-G4), or any `PRE-REGISTERED` item is unresolved at Gate I (C-G5) | |

### Gate A — `/speckit-analyze` (run by Opus, adversarial; NOT Supervisor-graded)

| id | check | evidence |
|---|---|---|
| A-G1 | Zero CRITICAL findings; every WARN has a written disposition (fix / accept-with-reason) | analyze report |
| A-G2 | Constitution P1 reading (state dir outside repo) explicitly ruled on | report line |
| A-G3 | Every `[INFERRED]` item in spec.md + contracts C2 `list`/`show` explicitly accepted or cut | report table |
| A-G4 | Cross-cutting check: confirms no task modifies `workerbees/ledger.py` schema (D35 addendum gotcha), no overlap with `specs/002` visualisation or `specs/009` routing determinism | report line |
| A-G5 | tasks.md ↔ contracts consistency: exit codes, flag names, file paths identical strings | diff-style list |
| **Probe list for Opus** (from Executive): (1) R2 assumption that the bridge lock + per-request `thread_id` is safe under two concurrent roles — does `codex_lock` serialize correctly and does Codex CLI allow two threads resumed alternately from one process? (2) A3 — is "explicit re-engagement only" enough for #15 c2's "Executive steps in only if Supervisor trips up", or does the spec silently need a trip-up signal? (3) Q1=A collapses "Owner/Interlocutor agree" (two parties) to one actor — is `--by` without roster validation an acceptable v1 or a P4 fail-closed violation? (4) FR-011 `no-resume` recording for non-Codex backends — is that a scope leak into Gemini/Mistral paths? (5) `follow-up` verb semantics vs `--mandate` — conflict or duplicate? (6) `--force` on `mandate close` with in-flight jobs (C2) is INFERRED. (7) SC-001 "prompt size bounded by new question" — measurable in quickstart or hand-wavy? | |
| **FAIL** | any CRITICAL, or A-G4 finds a schema/scope touch | |

### Gate I — `/speckit-implement`

| id | check | evidence (verbatim command output) |
|---|---|---|
| I-G1 | `python3 -m unittest discover -s tests -p 'test_*.py'` → all pass incl. the two new files; count of tests in new files ≥ 10 | output tail + `grep -c "def test_" tests/test_mandate_session.py tests/test_bridge_thread_id.py` |
| I-G2 | Backward compat: `agent.sh submit --backend codex "ping"` (no mandate) job JSON has no `mandate` key; `ask.sh` without `--thread` sends body without `thread_id` | `agent.sh status <id> --json`; `bash -x ask.sh` excerpt |
| I-G3 | `bash -n` + `shellcheck` clean on `ask.sh`, `preflight.sh` | output |
| I-G4 | quickstart.md executed live; the roster-verification precondition (W-13) run first with pasted output, then steps **2, 3, 3a, 3a-ii, 3b, 4, 5, 5a, 6, 8, 8a, 9** match "expect" (step list corrected 2026-09-12, analyze pass-2 — it previously omitted 3a/3a-ii/3b/8a, i.e. the SC-001, FR-014 and `--by`-precedence checks; extended again by the round-3 fix with **2** (role-isolation proof, N-C5) and **5a** (in-flight close refusal, exit 10, N-C2), and note the guard-order repair at 5b); transcript saved under `specs/010-persistent-exec-session/evidence/quickstart-<date>.txt` | file + step outcomes table |
| I-G5 | I5 survival: run step 3 of quickstart from a **new shell** after killing nothing but proving fresh process (it is by construction) — `mandate show` returns identical `thread_id` before/after | two outputs |
| I-G6 | Diff scope: `git diff --stat development` touches only files in plan "Source Code" tree + spec dir | stat output |
| I-G7 | Commit messages `<type>: <imperative>`; ≤20 commits; no `wip` | `git log --oneline development..HEAD` |
| I-G8 | PR description contains the Codex-only scope note (T-G6), links #15, links quickstart evidence, footer per attribution rule | PR body |
| I-G9 | #15 comment posted: `shipped → development @ <sha>` + evidence link; issue NOT closed by Supervisor (Executive verifies then closes per `CLAUDE.md` #319 rule) | comment URL |
| **FAIL** | any test red, any quickstart "expect" mismatch, any out-of-tree file in diff, or Supervisor asserts PASS without pasted output | |

## Risks / open items (carry into tasks.md, not silently resolved)

- **R-A** ~~`closed_by` actor is recorded, not validated~~ **CLOSED 2026-09-12** by analyze blocking #5: `--by` is now validated against the fixed allowlist `{ceo, lead}`, fail-closed exit 2 (contracts C2a, spec FR-005a). The roster itself remains ⚠ operator-unconfirmed (no Task Authority roster file exists in repo) and is deliberately narrower than canon may be; widening requires an operator-signed edit to C2a. The former mitigation (an inline code comment, old task T034) was unenforceable and is replaced by validation + a test.
- **R-B** Codex CLI behaviour resuming two different threads alternately from one bridge process is asserted (R2) not yet demonstrated → quickstart steps 1–3 are the proof; if it fails, fallback = one bridge port per role (rejected alt in R2) — that is a plan change requiring Executive sign-off.
- **R-C** `bridge.py` resume-failure retry block (`:250-322`) is intertwined; the 409 path must not regress the global-thread auto-restart → `test_bridge_thread_id.py` must include a global-path regression case.
- **R-E** (added 2026-09-12, analyze pass-2 W-14) **Mandate-store concurrency + corrupt-record handling are unspecified in v1.** `save_mandate` is `tmp+rename` atomic per write, but `engage()`'s read-modify-write is **unlocked**, so two simultaneous `submit --mandate` on the same `run_id`, or a `mandate close` racing a `submit`, can lose an engagement; a malformed mandate JSON on disk surfaces as an unhandled decode error. Accepted for v1 (single operator, one machine — plan Technical Context "Scale/Scope") because both failure modes are fail-closed (nothing resumes the wrong thread), and no FR was invented for them. **Post-v1 follow-up: file-lock protocol around `engage()`/`close` + explicit corrupt-record refusal with a stated exit code.** Carried here so it is not silently dropped; also noted as `PRE-REGISTERED`/deferred against `requirements-quality.md` CHK003 + CHK012.
- **R-D** `ask.sh` positional-prompt parsing: a prompt starting with `--` would misparse today already; not in scope, note only.

## Analyze disposition (adversarial pass 2026-09-12)

Independent Opus analyze returned **FAIL**: 5 blocking + 9 WARN. The 5 blocking findings were applied to spec.md / contracts / tasks.md (see spec.md "Post-analyze amendments"). **This section is the single place every WARN disposition lives** — do not restate them in other files. A fix agent applied these; the verdict on whether the feature now passes belongs to the next independent analyze pass, not to this document.

| # | warning | disposition |
|---|---|---|
| a | No protocol for a Supervisor to signal "tripped up" to the Executive, despite the two-failed-checks canon | **Accepted as-is, with the canon now cited.** spec.md A3 deliberately keeps trip-up *detection* with the Supervisor/run root; this feature only guarantees the escalation *reaches the same Executive session*. The canon that governs when a Supervisor must escalate is `CLAUDE.md` "**Failed check — definition of record**" (two supervisor-run RED verifications of a delegate's returned output → promotion trigger; delegate self-PASS is not a check) plus `CONTEXT.md` Capability Escalation / Authority Reassignment. Reason for accept: encoding a trip-up signalling protocol would change escalation rules, which spec.md "Out of Scope" explicitly forbids this feature from touching (it consumes them). Cross-reference added here rather than a new FR. |
| b | "Non-Codex paths are always no-resume" is false — agentic Mistral has real continuity | **Fixed.** spec.md FR-011 rewritten: `no-resume` now means "no *mandate-scoped* continuity on this path", with ground truth cited (`agent_runner.py:318-319` follow-up allowed for codex **or** mistral — cite corrected 2026-09-12 in the pass-2 re-grep, was `:319-323`; `:322-323` refuses only non-`--agent` Mistral; `:331` OpenRouter stateless; `:333` Gemini stateless). |
| c | SC-001 not measurable as written | **Fixed.** SC-001 reworded to "round ≥2 outbound prompt body byte-identical to the caller's new input, no injected background", with the capture method stated; `quickstart.md` step 3a now actually captures and checks it. |
| d | Nothing stops an env-var override redirecting state back inside the repo | **Fixed.** New **FR-015**: runner refuses (exit 2) when `CODEX_BRIDGE_AGENT_STATE_DIR` resolves inside the repo root or `~/.claude/`; edge case added to spec.md; task T043 + checklist CHK031 enforce it. Constitution P1 row updated. |
| e | research.md R5 claims `mandate close` writes a ledger event; no task implements it | **Fixed by striking the claim.** Chose strike over implement: tasks.md's scope guard forbids touching `workerbees/**`, and R4 already rejected the shared SQLite store over the `tier CHECK` blast radius (D35 addendum) — adding a ledger write would cross that guard for audit value already provided by the mandate record's `closed_by/closed_at/close_reason`. research.md R5 now states the ledger is read-only context (mandate id *is* a `run_id`) and records ledger emission as a post-v1 follow-up. |
| f | The implementation-readiness checklist's items are all undisposed and the CHECKLIST gate does not require dispositioning | **Fixed.** New Gate row **C-G4** (below) makes dispositioning a pass condition; `checklists/implementation-readiness.md` gains a "Disposition status" header explaining that items are *pre-registered* (code does not exist yet) and marks the representative items that a fix agent could dispose today vs. those that must wait for implement. |
| g | US2 acceptance scenario 2 ("Executive not re-engaged, no idle cost") rests on a bare inspection task | **Fixed (stronger test added), not accepted.** New task **T042** asserts that engaging role `supervisor` under mandate M appends nothing to `roles.executive.engagements` and leaves `roles.executive.thread_id` and `in_flight_job_id` unchanged — a real assertion instead of "confirmed by inspection". Phase-4 checkpoint prose updated to point at T042. |
| h | Supervisor writing core interface code is asserted in prose, not logged as a promotion-trigger with a reason | **Fixed, then superseded by W-12's re-characterization (wording aligned 2026-09-12, round-3 fix N-C3 — this cell still carried the pre-W-12 text and contradicted the row it describes).** § "Promotion-trigger log" above records row **PT-1** as **scope retention, not a promotion — no rung move, no promotion trigger**: D27 makes architecturally significant change Workhorse+ work by rule, and an Orchestrator has Workhorse capability by construction, so the Orchestrator retains work it is already qualified for. The row states the assignment, the reason of record, and that the Executive merely *records* it (a genuine rung move would require the operator or Lead). Scope limited to tasks tagged `Supervisor-self`. |
| i | `--force` / verb-count tagging | **Covered by blocking #4, not duplicated.** FR-012 now distinguishes the single *mutating* verb from read-only `list`/`show` (both tagged `[INFERRED]`), and `--force` is tagged `[INFERRED]` in FR-006 as well as in contracts C2/C2a. |

Additional non-analyze operator directive applied: every coding task in tasks.md names a free-tier primary model **and** a fallback chain (§ "Free-tier model assignment + fallback chain").

### Analyze disposition — pass 2 (`analyze-2026-09-12b.md`, verdict FAIL: 3 CRITICAL / 13 WARN / 2 INFO)

Second independent Opus pass. **This subsection extends the single-location convention above — every pass-2 disposition lives here, nowhere else.** Fixes applied by the 2nd fix pass 2026-09-12; the verdict on whether the feature now passes belongs to the 3rd independent analyze pass (Fable), not to this document. No pass-2 finding is left without a disposition.

| # | finding | disposition |
|---|---|---|
| **F-01** | `mandate close` idempotency vs. `--by` allowlist precedence undefined; T023 and T034 encoded contradictory expectations | **Fixed (normative precedence rule written).** contracts **C2a** now carries a 5-step ordered pipeline — argument validation → record load → idempotency → in-flight guard → transition — stating that an invalid `--by` exits 2 *regardless of mandate state*; C2's `close` row and spec FR-005a reference it; `quickstart.md` step 8a reordered (invalid values on the open mandate, then a valid close, then a valid idempotent repeat, then an invalid repeat → exit 2) and now asserts `state` is still `open` after a refused close; tasks T023/T034 name which pipeline step each test exercises. Resolves OQ-5 as the reviewer recommended (validation first, matching P4 fail-closed). |
| **F-02** | Blocking-fix #1's edit locus omitted the primary global-thread write site; `bridge.py:431` mis-cited as a write site in C3, C1a, R2 | **Fixed (re-cited everywhere, independently re-grepped).** Write sites verified by `grep -n thread_id bridge.py` on 2026-09-12: **`:216`** (success) and **`:298`** (retry); `:431` is the initializer. Corrected in contracts **C3** (plus a new normative **rule 5 "edit locus of record"** naming both sites so an implementer cannot fix one and leave the other), contracts **C1a**, **research R2** (finding + correction paragraph), and **plan §Design 3** (locus rewritten to `:194-195, :216, :238, :248, :298, :319, :331, :250-322`). Reads that must also change (`:238`, `:319`, `:248`, `:331`) are enumerated; global/`reset`-only sites (`:182`, `:268`, `:397-398`) are marked out of scope for the edit. |
| **F-03** | SC-001's quickstart demo measured a hand-built `ask.sh --thread` call, not `submit --mandate`, and fired a live unrecorded provider turn mid-script; no automated test existed | **Fixed (real test added, live step removed).** spec **SC-001** now states the measured path MUST be `submit --mandate` and names two evidence tiers: primary = new task **T045** / `test_submit_mandate_prompt_body_byte_identical_no_preamble` (drives a real round-2 `submit --mandate` against the T001 stub `ask.sh`, which records the outbound body; asserts byte-identity — **no provider call**); secondary = quickstart **3a** (now runs that unit test) + **3a-ii** (read-only inspection of step 3's own job record, asserting the recorded round-2 prompt is byte-identical and `mode=resumed`). The live `bash -x ask.sh --thread` re-send is deleted with an inline "do not reintroduce" note. `CHK034` re-pointed at T045 as the authoritative check. |
| W-01 | Gate rows carried pre-fix ranges (`FR-001..FR-013`, `I1–I5`), excluding the fixes they exist to check | **Fixed.** T-G1 → `FR-001..FR-015` incl. FR-005a, plus an SC-001..SC-006 clause; T-G2 → `C1, C1a, C2, C2a, C3–C6` and `I1–I8`; C-G1 → `I1–I8` plus C2a/FR-015/SC-001 coverage. All four sites updated. |
| W-02 | tasks.md's coverage matrix was deliberately empty, pointing at a handoff report, while T-G1/T-G2 demand the matrix *in tasks.md* | **Fixed by inlining.** The matrix now lives in tasks.md § "FR / Contract / Edge-Case / Risk → Task Coverage Matrix" (FR/I/C rows, plus SC, edge-case and risk rows), making Gate T re-gradeable from the artifact. Chose inline over amending the gate: the gate's requirement was the reasonable one; the empty section was the defect. |
| W-03 | Warning-(f) dispositioning was applied to one named file, leaving `requirements-quality.md` (23 of 24 items) wholly undisposed | **Fixed per artifact class, not per file.** Gate **C-G4** rescoped to "every checklist under `checklists/`"; `requirements-quality.md` gains a "Disposition status" section and a per-item marker on all 24 items. Also added Gate **C-G5** (OQ-2) forcing every `PRE-REGISTERED` item to flip to `[x]`/RED at Gate I. |
| W-04 | `requirements-quality.md` CHK009 quoted the superseded SC-001 wording; CHK022 asked a question FR-015 answers | **Fixed.** Both marked `RESOLVED` with the FR/SC cite (CHK009 → SC-001 as reworded + T045/CHK034; CHK022 → FR-015 + I8 + T043 + CHK031), matching how CHK004 was handled. |
| W-05 | FR-005a's rationale overclaimed — the allowlist validates a *string*, not the caller, so any delegate may still assert `--by lead`; FR-005 stays unenforced | **Fixed by rewording to what the guard actually does, plus an explicit residual-risk line.** FR-005a now claims only (i) `closed_by` values are constrained to a fixed roster and (ii) typos/empty/free text fail closed, and states plainly that v1 **does not authenticate the closer**, that FR-005's "no other actor may close" is therefore not enforced in v1, and that `CONTEXT.md:33`'s policy-granted-and-recorded Task Authority is not derivable from a role label. **New grill-clause item raised, not guessed:** authenticating the closer (e.g. checking a recorded Task Authority grant) is a design decision beyond a textual fix → flagged in FR-005a for the operator, no mechanism invented here. Roster values untouched (see "not resolved" note below). |
| W-06 | Line drift in research R3/R4/R7 cites | **Fixed (re-grepped, not copied).** `STATE_DIR` → `agent_runner.py:26-28`; `TERMINAL` → `:43`; `ask.sh --raw` output block → `ask.sh:135-148` (flag at `:50`); `ask.sh --model` → `:42` (body-build `:86-87`). Two further cites re-verified and corrected while in the same text: R1's `agent_runner.py:149-152` → `:154-161` (`make_command`), and R1's `ask.sh:80-95` → `:76-90` (body heredoc) + `:92-100` (curl). Conclusions unchanged in every case. |
| W-07 | C1's reserved-code list ascribed exit 5 to `agent_runner.py:133` only; `route.sh:201` also exits 5 | **Fixed.** C1's reserved list now enumerates every code with its site — 1 (`route.sh:369`), 2 (`:10`, `:165`), 5 (`agent_runner.py:133` **and `route.sh:201`**, propagating via `agent_runner.py:150`), 127 (`route.sh:360`), 3 (`:209`), 4 (`:162`) — with the verifying grep and its output recorded. Conclusion (7/8/9 free) re-verified, unchanged. |
| W-08 | CHK024 ("requires non-empty `--by`") is a strict subset of CHK030 | **Fixed as a pointer, not a strike.** CHK024 rewritten to defer to CHK030 for `--by` validation and to retain only the non-duplicated part (the C2a precedence assertion). Kept as a pointer rather than deleted so the checklist's item numbering and the Notes' audit trail stay stable. |
| W-09 | quickstart step 9 forged `open` state on a closed mandate, violating data-model.md:10 inside the acceptance script | **Fixed.** Step 9 now seeds a **separate fresh** mandate file (`$M3`) with an old `opened_at` and removes it afterwards; the closed `$M` is never rewritten. Inline comment records why. |
| W-10 | FR-012's backward-compat half had no test task | **Fixed.** New task **T046** — `test_submit_without_mandate_has_no_mandate_key` (job JSON has no `mandate`/`role`/`mode` keys) and `test_ask_sh_body_omits_thread_id_when_flag_absent` (POST body carries no `thread_id` key), satisfying CHK001/CHK002 with tests rather than manual Gate I-G2 inspection. |
| W-11 | `--fresh` replacement recording (`replaced_thread_ids`) had no named assertion | **Fixed.** T003's `test_engage_fresh_forced_on_flag` renamed to `test_engage_fresh_forced_on_flag_appends_replaced_thread_id` with the body requirement spelled out: assert `mode == "fresh-forced"`, the prior `T` appended to `replaced_thread_ids`, and `thread_id` reset to null (US1 AS3, FR-008, data-model.md RoleSession). |
| W-12 | PT-1 used a *promotion* trigger to license a rung-**down** assignment, and recorded the Executive as granting authority though `CONTEXT.md:31` makes Lead ≠ Executive | **Fixed by re-characterization (reviewer's second option).** PT-1 restated as **scope retention, not promotion**: D27 makes architecturally significant change Workhorse+ work by rule, and an Orchestrator has Workhorse capability by construction, so no rung move occurs and no promotion trigger is claimed. The authority field now says the Executive merely *records* it, and notes that a genuine rung move would require the operator or Lead. Constitution-check row P2 updated. |
| W-13 | Hard-coded Codex slugs, no runtime roster verification before the live run (P7) | **Fixed.** `quickstart.md` gains a **Precondition** block declaring the slugs non-authoritative and requiring `workerbee` Step 1a/1b roster verification + substitution before step 1, and classifying a stale-slug failure as a precondition failure rather than an SC-002 failure; **T040** gains that verification as an explicit first sub-step with pasted-output evidence. Constitution-check row P7 updated. |
| W-14 (INFO) | Genuine uncovered gaps: bridge down at engagement time (CHK001), `close` racing `submit` on one `run_id` (CHK003), corrupted mandate JSON (CHK012); no file lock specified | **Deferred with reason — no FR-016 added (disposition only, per the work order).** (i) **Bridge down**: already surfaced today as a non-zero `ask.sh`/curl failure that the runner reports; a mandate adds no new silent-failure mode, so v1 relies on the existing path — recorded as `PRE-REGISTERED` in `requirements-quality.md` CHK001. (ii) **Concurrency**: real and acknowledged — the store is `tmp+rename` atomic *per write* but `engage()`'s read-modify-write is unlocked, so two simultaneous `submit --mandate` on one `run_id` (or a `close` racing a `submit`) can lose an engagement. Scope of v1 is a single operator on one machine (plan Technical Context "Scale/Scope"), and adding a lock protocol is a design change the reviewer explicitly did not require; deferred as a **named post-v1 follow-up (locking + corrupt-record handling)**, recorded in Risks as **R-E** so it is carried, not forgotten. (iii) **Corrupt JSON**: same follow-up; v1 behaviour is an unhandled `json.JSONDecodeError` surfacing as a non-zero exit, which is fail-closed (no silent wrong resume) and therefore acceptable for v1. Flagged for the operator as a knowingly accepted v1 limitation rather than an invented requirement. |
| W-15 (INFO) | plan §Project Structure omitted both checklists and still said tasks.md was "NOT created here" | **Fixed.** Tree refreshed (both checklists, `pr-description-note.md`, `analyze-2026-09-12b.md`, tasks.md marked as existing, `I1–I8`, `C1a`/`C2a`). |

**Deliberately NOT resolved by this fix pass (OQ-1):** the `--by` roster values `{ceo, lead}` remain exactly as they were and remain flagged ⚠ **NEEDS OPERATOR CONFIRMATION** in spec FR-005a, contracts C2a, data-model `closed_by`, tasks T034 and CHK030. The operator has not ruled on the roster in this round; the narrower W-05 problem (the guard validates a string, not the caller) is fixed textually and its design-level remainder raised as a grill-clause item. No value was added, removed, or reinterpreted.

Also untouched per the work order's "do not touch" list: clarify answers Q1–Q5, `workerbees/**`, `CONTEXT.md`, `docs/DECISIONS.md`.

## Complexity Tracking

No constitution violations requiring justification. Single-file growth of `agent_runner.py` noted under Structure Decision with an explicit split threshold.

## Agent context

Root `CLAUDE.md` has no `<!-- SPECKIT START/END -->` markers (checked 2026-09-12); per template instruction the marker update is skipped. `.specify/feature.json` `feature_directory` already points at this spec dir.
