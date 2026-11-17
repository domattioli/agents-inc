<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-06 skill=speckit-implement repo=agents_Inc session=c5e2753c -->
# Feature Specification: Opus-orchestrated terminal demo of agents-inc

**Feature Branch**: `030-opus-terminal-demo` (spec only; no branch created by this run)
**Created**: 2026-11-06
**Status**: Draft
**Input**: Operator ask 2026-11-06: "lets plan a demo that opus will orchestrate of agents inc's functionality within the claude code terminal."

## Background (code facts)

- `agents-inc doctor` prints `READY`, `agent gate: advisory (default)`, `luna type: ready` on this machine (run 2026-11-06).
- Dispatch surface: `agents-inc dispatch --slots <json> --model <alias> [--dry-run]`; the command renders the 14-element prompt, lints it, snapshots scope, launches, runs `GATES`, and returns one status line (`skills/workerbee/QUICKREF.md`).
- Live view (spec 027): a dispatch writes `<run dir>/events.jsonl`. A mod pane (`luna-pane`) tails the newest luna and haiku run dirs and draws one pane per delegate beside the chat. The `agents-inc:relay` haiku subagent is not used: it costs Claude tokens on every relayed row (operator, 2026-11-07).
- Native luna (spec 028, D69): `agents-inc:luna` is an Agent-tool subagent type whose model steps are answered by Codex luna through a `turn.step` hook; it inherits the parent's tools and permissions like a haiku subagent.
- Ledger: every launched dispatch appends one row; `agents-inc ledger append|pending`.
- Offline demo exists: `PYTHONPATH=. python3 tools/governance_demo.py --fake` (no provider keys).
- Demo task fixtures: `fixtures/build-test-verify/S` (`csv2json`, 14 hidden cases, 4 traps) and `M` (`tasklog`); each has a `hidden/acceptance.py` judge never shown to the delegate.
- Prior demo (2026-10-18 memory): a 48 s manim video on mock data, judged "a start"; operator wants the watching-the-agents-work framing front and center.

## Clarifications

### Session 2026-11-06

- Q1: Delivery? -> A (operator): recorded cast. FR-008.
- Q2: Live-view surface? -> A (operator, revised 2026-11-07): a Claude Code mod pane per delegate (luna, haiku) tailing `events.jsonl`, no relay and no haiku courier. FR-009.
- Q3: Which Grunt? -> A (operator, verbatim): "luna, haiku, and a free model all shown to be working." FR-010. Note: `agents-inc dispatch` does not route free models (spec 027 Q1); the free beat goes through the provider wrapper (`gask.sh`, `mask.sh`, `oask.sh`), which has no filesystem, so its task is `summarize` over pasted text.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One scripted session shows the whole loop (Priority: P1)

The operator opens Claude Code with the opus model and pastes one demo prompt. The opus session acts as Chief of Staff: it states the vendor gate, writes a slots file, dispatches a Grunt delegate on the `csv2json` fixture, shows the delegate working live, verifies the result with the hidden acceptance judge, and reads back the ledger row. Each beat is visible in the terminal without the operator typing again.

**Why this priority**: This is the operator ask. One run, one terminal, every claimed capability exercised for real.

**Independent Test**: Run the demo prompt in a fresh session on this machine. Every beat below appears, and the acceptance judge exits 0.

**Acceptance Scenarios**:

1. **Given** a fresh opus session in the repo, **When** the operator pastes the demo prompt, **Then** the session prints `vendor gate: <gate> -> <delegate>` before any dispatch.
2. **Given** the slots file is written, **When** the session runs the dispatch, **Then** the dispatch returns one status line with `outcome=green` and a run directory path.
3. **Given** the dispatch is running, **When** the operator looks at the delegate's pane, **Then** at least one event row appears before the delegate finishes.
4. **Given** the delegate reports done, **When** the session runs the hidden judge, **Then** the judge exits 0 and the session states which of the 4 seeded traps the delegate avoided.
5. **Given** verification passed, **When** the session reads the ledger, **Then** the pending row for this run shows the delegate model (the rung is the one the session chose in the slots file), the session records its verdict against that run id, and the row leaves the pending list. The session states the outcome and names itself as verifier in the beat line (plan.md, Spec conflicts 1).

---

### User Story 2 - luna as a native subagent, beside haiku (Priority: P2)

The opus session starts the same small task twice through the Agent tool: once with the haiku type, once with the `agents-inc:luna` type. The operator clicks both subagent rows and sees the same transcript shape, the same permission prompts, and the luna row answered by Codex with no Claude tokens per step.

**Why this priority**: D69 is the newest capability and the one that distinguishes agents-inc from plain subagents. It ships alone.

**Independent Test**: Both subagents finish and hand back a report, and the host ledger holds a `source: native-luna` record. Optional, only when the transcript is readable from the parent (plan.md design point 5, probe T026): the luna transcript records `model` as a luna slug and per-step usage from Codex.

**Acceptance Scenarios**:

1. **Given** the luna type is `ready`, **When** the session spawns `agents-inc:luna` with a Bash and Read task, **Then** the subagent completes and hands back a report.
2. **Given** both subagents are done, **When** the session compares the two transcripts, **Then** it states one line per difference, or `none`.

---

### User Story 3 - The demo survives a missing provider (Priority: P3)

The same demo prompt runs on a machine with Claude only. The session detects the missing Codex, prints one `NOTE:` line, routes the Grunt work to haiku, skips the luna beat with a stated reason, and finishes every other beat.

**Why this priority**: The demo will be shown on machines other than the operator's.

**Independent Test**: Run with the Codex CLI off PATH; the build falls back to haiku in a fresh dispatch and the three beats still pass.

**Acceptance Scenarios**:

1. **Given** no `codex` on PATH, **When** the demo runs, **Then** the runner prints a line starting `NOTE: codex absent -> haiku` before any dispatch and the session continues.

---

### Edge Cases

- Codex quota is exhausted mid-run: the dispatch reports a quota pause, the session counts it as one failed attempt, and escalates per the ladder or stops with a reason. It never retries silently.
- The delegate claims PASS but the judge fails: the session reports the judge output verbatim and does not call the demo green.
- A delegate writes more rows than a pane can show: the pane keeps the newest 60 lines and the full log stays in `events.jsonl`.
- The scope snapshot is not clean: the dispatch reports `snapshot-not-clean`; the session runs `git status --porcelain`, states the cause, and re-runs that dispatch once.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The demo MUST be one prompt passed to the Claude Code session at launch plus one runner script, checked into the repo, runnable in about 30 seconds of wall clock (timer per SC-002).
- **FR-002**: The demo MUST run three beats in this order: 1 routing (vendor gate line), 2 build (luna builds `csv2json.py` through a background `agents-inc dispatch`, visible live in its pane), 3 verify (hidden judge run by the supervisor, not the delegate, then the ledger verdict). The free-model summary, the haiku review and the native-luna comparison are out of the short cut. The beat list in `tools/demo/PROMPT.md` is the single source for the prompt and the tests.
- **FR-003**: The demo MUST use the `csv2json` fixture as the delegate's task and MUST NOT copy `hidden/` into the trial directory. The delegate's working directory is the repo root, so `fixtures/build-test-verify/S/hidden/` stays reachable by path. The build slots MUST forbid reading `fixtures/` and `.scratch/bench-*`, and the supervisor MUST grep the run's `events.jsonl` and `stdout.md` for `hidden/` and `acceptance.py` and call the run red on a hit.
- **FR-004**: The demo MUST print one line per beat (three lines) so an observer who reads only the terminal can follow it.
- **FR-005**: The demo MUST spend $0 in API fees: Claude and Codex subscriptions plus free-tier provider keys only, no paid API fallback.
- **FR-006**: The demo MUST degrade: a missing optional provider produces one `NOTE:` line and a routed substitute, never a crash.
- **FR-007**: Every delegate claim MUST be verified by the opus session before it is reported as green: the build by the hidden judge. Opus records the ledger verdict only after the judge exits 0.
- **FR-008**: The demo MUST be delivered as a recorded terminal cast (asciinema, with a GIF export) made from one live run; the runner script starts and stops the recording.
- **FR-009**: The live view MUST be a mod pane per delegate inside Claude Code that tails `events.jsonl`; the demo MUST NOT relay rows through a Claude subagent. The mod handles Codex-format and Claude-format rows.
- **FR-010**: The demo MUST show luna working through dispatch on the `csv2json` build, with its live session in its own pane. Haiku is the fallback builder when Codex is absent and has its own pane. The free model and the haiku review are out of the short cut.

### Key Entities

- **Demo prompt**: the text the operator pastes; names the fixture, the beats, and the models.
- **Runner script**: prepares the trial directory, copies `SPEC.md` only, and prints the beat checklist.
- **Run directory**: `<run_id>/` holding `prompt.md`, `run.json`, `events.jsonl`, `stdout.md`, `usage.json`.
- **Ledger row**: one append per launched dispatch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time viewer can name all three beats after watching once (post-launch outcome; checked by asking one viewer after the recording).
- **SC-002**: The full demo completes in about 30 seconds on the operator's machine, 3 runs out of 3. The timer starts when the runner starts and stops at the `BEAT 3` line. The build alone must stay under 20 s, which is why the delegate writes only `csv2json.py`.
- **SC-003**: The acceptance judge exits 0 in at least 2 runs out of 3.
- **SC-004**: Zero dollars of API spend per run, checked by: the runner prints `paid env vars: none` (none of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` is set; presence only, values never read), and the operator confirms once per machine that each free-provider key is on a free tier.
- **SC-005**: On a Claude-only machine the demo completes all three beats with haiku as the builder.

## Assumptions

- The demo runs from a checkout of `agents_Inc` on the `development` branch, with `agents-inc doctor` printing `READY`.
- The opus session runs with caveman ultra in the terminal; demo output lines are plain English since they are shown to viewers.
- The `M` fixture is out of scope; `S` is large enough to show traps and small enough for a Grunt.
- The manim video is out of scope; this demo is terminal-only.
- Spec files move to DomI `specs/consumers/agents_Inc/` as the final implement task.
