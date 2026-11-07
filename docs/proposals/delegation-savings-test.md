# Proposal: token savings test, same task with and without agents-inc

Status: draft, 2026-10-22. Answers the roadmap "Now" item in README §1 ("measure the token cost of delegation against doing the work in one session"). Bound by D5 (metric and quality floor), D9 ($0 incremental, so the unit is tokens and quota, not cash) and D10 (no savings percentage until both workflows reach N≥5).

## 1. Question

For one fixed build-test-verify task and one fixed prompt, how many tokens does a Claude Code session spend when it does the work itself, versus when agents-inc is installed and the work is dispatched down the ladder? "Tokens" means every token billed to any model in the trial: the session you talk to, every delegate, and every reviewer.

The honest expectation is a crossover. agents-inc adds a fixed per-session cost (hook text, the mandate, a SKILL.md read of about 16k tokens, the dispatch prompt contract) and a per-dispatch cost (rendered prompt, report, review). It can only win when the work moved to cheaper rungs is large enough to repay that overhead, and only if quality holds. The test must be able to show a loss as plainly as a win.

## 2. Arms

Each trial is one task run once under one arm, from a clean checkout, in a fresh session.

| Arm | Session setup | Who does the work |
|---|---|---|
| A0. Control, no delegation | Claude Code, no agents-inc hooks. `Agent` and `Task` disallowed. Session model = the model agents-inc would make the Lead (opus). | The session alone. Isolates the cost of doing everything at the top rung. |
| A1. Control, native delegation | As A0 but `Agent` allowed. | The session plus whatever Claude Code delegates on its own (Explore and other scouts already default to a cheaper model) or is asked to ("use sonnet for the tests"). This is what an uninstalled user actually gets today. |
| B. agents-inc, advisory gate (default install) | Hooks installed, `agent gate: advisory`. Same session model. | Session is the CoS; dispatches via `agents-inc dispatch` per the ladder (opus Lead, sonnet or haiku Workers). Native `Agent` still possible for scouts. |
| C. agents-inc, enforce gate | As B with `agent gate: enforce`. | As B, but native `Agent` is blocked, so every delegation goes through dispatch and is in the ledger. |

Lower rungs are delegated to in B and C by design; that is the mechanism under test and is never disabled. The important consequence of A1 is that the test does not measure delegation against no delegation. It measures agents-inc's governed, ladder-routed delegation against the host's native, ungoverned delegation. A0 exists so the two effects can be separated: A1 minus A0 is what native delegation already buys, and B or C minus A1 is what agents-inc adds on top of it.

Because arm A1 delegates to cheaper models too, its token accounting must be split by model, not just by source. The session JSONL carries a `model` field on every message, including subagent turns, so the per-model split comes for free in all arms.

Isolation is by `CLAUDE_CONFIG_DIR`, one directory per arm, so the operator's live install is never unwired and rewired between trials. Arm A's directory has no agents-inc hooks; B and C are `agents-inc install` outputs with the gate set by `agents-inc repair --agent-gate`.

A fifth arm, A-cheap (control run on sonnet alone), is worth one pass: if sonnet alone passes the quality floor at lower cost than either B or C, that is the finding, and the ladder has to beat it rather than beat opus.

Codex rungs stay out of the first run. Quota pauses (D9) would interrupt paired trials, and the Claude-only comparison is already the question the roadmap asks. Add a Codex cell once the Claude cells are clean.

## 3. Task: build, test, verify

One generalized task shape, not tied to any repository. Each trial starts from an empty directory containing only a written spec, and the session must:

1. **Build** a small, self-contained program from the spec (a CLI or library in Python, stdlib only).
2. **Test** it: write a test suite that covers every requirement in the spec, and run it to green.
3. **Verify and validate** it: run the suite, run a provided black-box acceptance script the session is told about but cannot edit, and write a short `VERIFICATION.md` that cites each requirement, the test that covers it, and the command and exit code that proves it.

The acceptance script is the independent judge. The session's own PASS never decides acceptance, which matches how the ladder treats a Worker's report.

Three sizes of the same shape, so the crossover point can be seen:

| Size | Spec | Requirements | Hidden acceptance cases | Seeded trap |
|---|---|---|---|---|
| S | A CSV-to-JSON converter with 3 flags | 6 | 12 | One flag whose spec wording is ambiguous; the spec answers it in a footnote |
| M | A dependency-ordered task runner reading a YAML-like file, with cycle detection and dry-run | 12 | 30 | Cycle case the obvious implementation misses; one requirement contradicts another and must be reported, not silently picked |
| L | A log-ingest tool: parse 3 formats, dedupe, roll up by window, emit a report, with a plugin hook | 20 | 60 | A format sample that violates its own stated grammar; a performance bound the naive version fails |

The seeded traps are the D5 quality floor. A false accept is a `VERIFICATION.md` that claims a requirement is met when the hidden acceptance cases say it is not, or that stays silent on the contradiction in M.

Why this shape rather than a repo fixture: it is the work every consumer asks for, it needs no setup beyond Python, the acceptance script makes grading mechanical, and the build/test/verify split maps directly onto what agents-inc claims to improve (Worker builds, Lead checks, independent verification before acceptance).

One prompt per size, written once and fully specified so no grilling is needed in `-p` mode. The same text goes to every arm. Arms B and C append only the ladder phrase from the README quick start ("... opus, haiku.").

Specs, hidden cases and acceptance scripts live under `fixtures/build-test-verify/{S,M,L}/`. Hidden cases are not in the directory the session works in.

## 4. Metrics

Primary, per trial, split by source:

| Source | Where it comes from | Status |
|---|---|---|
| Main session | `~/.claude/projects/<proj>/<session>.jsonl`, per-message `usage` (input, output, cache_read, cache_write), deduped by message id. `skills/codex-bridge/scripts/usage_db.py` already ingests this format. | Works today |
| Claude delegates | The `usage`, `total_cost_usd`, `num_turns`, `duration_ms` fields of the `claude -p --output-format json` payload. | **Discarded today**: `agents_inc/install/dispatch.py` keeps only `result` and `session_id` (around line 612). Ledger columns `input_tokens`, `output_tokens`, `cache_read`, `cache_write` exist in `ledger.py` but dispatch never fills them. |
| Native `Agent` subagents (arm A) | Their turns appear in the parent session's JSONL with their own usage blocks. | Works today; confirm by inspection in the dry run |
| Codex delegates (later) | `~/.codex-bridge/usage.jsonl` via the bridge, joined by `usage_join.py`. | Works today |

Report four token classes separately. Never collapse them into one number, because cache reads and haiku output are not the same resource as opus input. Also report one weighted figure, tokens × the published per-model price from the claude-api reference, as a cost proxy. Under D9 that figure is quota consumed, not dollars spent, and must be labelled so.

Secondary: wall-clock seconds, number of API calls, number of model turns, and the fixed overhead line (tokens spent before the first task-relevant action: SessionStart text, SKILL.md read, dispatch rendering). Publishing the fixed overhead on its own line is what lets a reader predict the crossover point for their own task size.

Quality gate per trial: hidden acceptance cases passed, false-accept count on seeded faults, and a blind human pass/fail on the deliverable with arm labels stripped. A trial that fails the quality gate counts in the table but not in any cost comparison.

## 5. Instrumentation work before the first measured run

1. **Persist delegate usage.** In `dispatch.py`, keep `data["usage"]`, `total_cost_usd`, `num_turns`, `duration_ms` from the result JSON and write them through `ledger.record_return` (and the host ledger row). Half a day including tests. This is useful on its own and should land regardless of the test.
2. **Record the main session id per trial.** The SessionStart payload carries `session_id`; the harness writes it to the trial's record so the JSONL can be found afterwards.
3. **Harness** `tools/delegation_bench.py`, modelled on `bench.py`: for each (task, arm, rep) it creates a fresh git worktree, picks the arm's `CLAUDE_CONFIG_DIR`, launches `claude -p --output-format json --model <session model>` with the task prompt, waits, runs the acceptance check, then collects usage from the three sources above and writes one JSON row. It must run outside the Claude Code sandbox (dispatch exits 69 inside it, D65).
4. **Rollup** that groups rows by task × arm and prints the table in §7 plus the raw JSON, appended to `docs/BENCH.md` under a new "Token bench" heading, the way `bench.py --t15` appends.

## 6. Controls and confounders

- **N and order.** N≥5 per (task, arm) cell, per D10. Interleave arms (A, B, C, A, B, C ...) rather than running all of one arm, so quota state and time of day do not favour one arm.
- **Fresh state.** New worktree, new session, no `--resume`, per trial. Cache reads are reported, not hidden, because a real user benefits from them in both arms.
- **Same session model in every arm.** Otherwise the test measures the model, not the infrastructure.
- **Native delegation is a moving target.** Which model Claude Code picks for a native subagent is set by the host and can change between releases. Record the Claude Code version per trial and report A1's per-model token split, so a later reader can tell whether a difference between A1 and B came from agents-inc or from the host changing its own defaults.
- **Prompt parity.** Identical spec and task text. Arms B and C add only the ladder phrase. Do not tune the prompt for one arm after seeing results.
- **Turn caps.** None. Let each arm finish or hit the existing `AGENTS_INC_TURN_TIMEOUT_S`. A timeout is a failed trial and is reported as such.
- **Quota pause.** A D9 pause (exit 75) marks the trial `paused`; rerun it after reset and keep the paused row in the raw data.
- **Known defect to watch.** Issue #86 (analyze findings relayed through the main session are paid for twice) is exactly the kind of overhead this test will surface; record it rather than fix it mid-run.
- **Operator presence.** `-p` mode removes grilling and mid-task steering from both arms equally. State this as a limitation; it under-counts arm B's real-life cost where the CoS asks questions, and under-counts arm A's where the operator corrects it.

## 7. Reporting

One table, counts not percentages:

| size | arm | n | accepted | false accepts | median input | median output | median cache_read | median cache_write | weighted proxy (median, IQR) | median seconds | fixed overhead |

Add a second table with the same rows split by model (opus, sonnet, haiku), so the reader can see where each arm spent its tokens, not only how many. Then, per size, one sentence: which arm spent fewer weighted tokens among trials that passed the quality gate, and by how many tokens (absolute). A savings percentage is reported only when every cell in at least two of the three sizes has n≥5 and the quality gate shows zero false accepts (D5, D10). If arm A-cheap wins a task outright, say so first.

Expected shape, to be confirmed or refuted: A0 or A1 wins S, roughly even on M, B or C wins L, with C costing more than B because every scout becomes a full dispatch.

## 8. Schedule

| Step | Effort | Output |
|---|---|---|
| Instrument dispatch usage (§5.1, 5.2) | 0.5 day | PR; ledger rows carry tokens |
| Harness and rollup (§5.3, 5.4) | 1 day | `tools/delegation_bench.py` |
| Specs, hidden cases, acceptance scripts for S, M, L | 1 day | `fixtures/build-test-verify/` |
| Dry run, n=1 per cell, 12 trials | 0.5 day | Bugs in the harness, not conclusions |
| Full run, n=5 × 3 sizes × 4 arms = 60 trials, plus 15 for A-cheap | 2 to 3 days of quota, unattended | Raw rows |
| Write-up into `docs/BENCH.md`, README §1 and §6 updated | 0.5 day | Measured claim or measured non-claim |

Total about 5 working days plus quota time. The first PR (instrumentation) is independent and can go now.

## 9. Build status

- Delegate usage capture landed on branch `token-bench`: `dispatch` writes `usage.json` (per-model tokens, list-price cost, turns) and `agents-inc ledger append` fills the token columns from it.
- Size S fixture: `fixtures/build-test-verify/S/`. The hidden judge scores 0/14 on an empty directory and 14/14 on a reference solution.
- Harness: `tools/delegation_bench.py`. Per-arm isolated `HOME`, session env scrubbed, arms interleaved per rep, one JSON row per trial, `--rollup` prints the tables.
- Linux limit: the broker refuses Claude Workers without macOS `sandbox-exec`, so on Linux the CoS dispatches to each rung directly and the nested Lead layer is not measured.
