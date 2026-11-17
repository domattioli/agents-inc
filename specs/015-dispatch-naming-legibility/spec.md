<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Dispatch Naming Legibility

**Feature Branch**: `development` (spec dir `specs/015-dispatch-naming-legibility`; no feature branch, per dispatch)
**Created**: 2026-10-01
**Status**: Draft
**Input**: Batch C of the 2026-10-01 Supervisor dispatch: issues #17 (persona name must match the actual vendor and model), #14 (Executive versus Supervisor hierarchy misread), #13 (model mismatch against operator-named models, unsafe partial-transcript recovery, duplicate-dispatch detection).

## Background (verified 2026-10-01 against HEAD `dd48471` unless noted)

- Rung names and vendor nicknames: `docs/governance/ROUTING-RANKING.md:18-25` (D34: Executive is the top rung; Orchestrator has Supervisor as a synonym). Constitution P2 and P7 restate the pairing (`~/Projects/DomI/specs/consumers/agents_Inc/memory/constitution.md`). `skills/workerbee/SKILL.md:175` says `astra/sol/terra/luna` are not Claude names.
- #17 evidence (issue comment, operator machine, 1,389 subagent dispatches): 24 of 24 dispatches whose description begins with a Codex persona ran a Claude model, and 0 of 24 invoked a Codex bridge. In 16 of 24 the name matched neither the vendor nor the rung. A looser match (persona anywhere in the description) found 2 of 48 with a bridge call, where the persona named a Codex worker the Claude subagent supervised.
- The install already owns a Claude `PreToolUse` hook on `Agent|Task` (`agents_inc/install/host_wiring.py:93-94`). It is advisory: it prints a once-per-session reminder and always exits 0 (`agents_inc/install/hook.py:1`, `:23-29`). It does not cover the `DelegateAgent` MCP tool.
- #14 evidence (issue comment, 30 operator role assignments 2026-09-07 to 09-24): 13 put Executive above Supervisor, 2 put Supervisor above Executive (both on 2026-09-09), 1 stated both, 14 gave no ordering cue. The issue body renders the operator's `>` as "less than"; the raw turn said "sol is the exec, which is > the supervisor". The current docs agree with each other: Executive is above Supervisor (D34).
- #13 evidence (issue comment): within-session duplicate detection found 0 accidental duplicates in 1,026 spawns; the two matching pairs were intentional fan-out. The incident duplicate most likely came from a second session or a nested subagent, so a guard needs state shared across sessions. `skills/workerbee/SKILL.md` has no step that confirms operator-named models before dispatch, no bounded transcript-recovery recipe, and no live-agent check before spawning.

## Clarifications

### Session 2026-10-01

Answered by the operator through the Executive, 2026-10-01.

- Q: What naming rule applies to dispatch descriptions? → A: Claude dispatches use rung names (Executive, Orchestrator/Supervisor, Workhorse, Grunt) or Claude model names; Codex persona names (`astra`, `sol`, `terra`, `luna`) appear only on dispatches that actually reach a Codex model.
- Q: What does the hook do when a description begins with a Codex persona? → A: Deny the `Agent`/`Task` call with a reason that names the rule. This changes the `hook.py:1` "Advisory only: never block" contract for this check only; parse errors and exceptions still fail open.
- Q: Which hierarchy is canonical? → A: D34: Executive above Supervisor (= Orchestrator). Before the first dispatch, the orchestrator must echo one line stating the hierarchy and the concrete model per role; operator-named models override the ladder.
- Q: Where does the duplicate-dispatch registry live? → A: A shared user-scope registry in the agents-inc state directory, across sessions and repos; warn only, never block.
- Q: What is the size bound for recovery output? → A: 4,000 characters.
- Q (addendum, refines the deny question above): What exact rule detects a persona prefix, and what does the deny reason say? → A: The literal regex `(?i)\A(?:astra|sol|terra|luna)(?=\s|:|/|\Z)`; a hyphen is not a delimiter. Deny fixtures: `terra: implement X`, `Luna - triage logs`, `sol reviews spec`, `ASTRA: review hook`, `sol/review`. Allow fixtures: `Solve flaky test`, `Terraform plan review`, `Sol-gel fit`, `Lunation calculation`, `Haiku reviews luna doc`, `terra-pair review`. Whole-name collisions such as `Astra DB migration` and `Luna repo cleanup` are expected denials and are documented as such. The deny reason is fixed text (FR-002). Operator decision 2026-10-01 after an astra third opinion and a fable second opinion. Slash added as a delimiter by operator decision 2026-10-01 after the #17 corpus check showed one `<Persona>/<word>` miss (22 of 23 without it).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A dispatch name never claims the wrong vendor (Priority: P1)

The orchestrator spawns a Claude subagent. Its visible name tells the truth about vendor and rung. A Codex persona name appears only on a dispatch that actually reaches a Codex model.

**Why this priority**: 24 of 24 measured persona-named Claude dispatches were mislabeled.

**Independent Test**: Feed the hook a `PreToolUse` payload for `Agent` whose description begins with `Terra`; assert the configured response. Feed one beginning with `Workhorse`; assert no response.

**Acceptance Scenarios**:

1. **Given** an `Agent` call whose description begins with `astra`, `sol`, `terra`, or `luna` (any case), **When** the hook runs, **Then** it denies the call with a reason that names the naming rule.
2. **Given** an `Agent` call whose description names a Codex persona later in the text (for example "Haiku reviews luna doc"), **When** the hook runs, **Then** it does not respond.
3. **Given** the workerbee skill, **When** a reader looks up dispatch naming, **Then** it states that Claude dispatches carry rung or Claude model names and that Codex persona names are reserved for dispatches that reach Codex.

---

### User Story 2 - The role hierarchy is stated before the first dispatch (Priority: P1)

When the operator names two roles or remaps models to rungs without an explicit order, the orchestrator states the resolved hierarchy and models in one line before it dispatches anything.

**Why this priority**: Both #14 and #13 began with a misread hierarchy or model mapping that only the operator caught.

**Independent Test**: The workerbee skill contains the rule; `check_dispatch_prompt.py` (or a new check) accepts a prompt carrying the line and flags a role-pair prompt missing it, as decided in planning.

**Acceptance Scenarios**:

1. **Given** an operator turn "X exec and Y super", **When** the orchestrator prepares the first dispatch, **Then** it first states "Executive = X (top), Supervisor = Y (reports to X)" with the concrete model for each.
2. **Given** an operator turn that names models conflicting with the ladder (for example "terra exec, luna super"), **When** the orchestrator resolves models, **Then** the operator-named models win and the conflict with the ladder is stated.

---

### User Story 3 - Recover a stopped delegate's work safely (Priority: P2)

A delegate is stopped or fails. The orchestrator gets a bounded summary of its work (status, last output, files it wrote or edited, last error) without reading the full transcript into context.

**Independent Test**: Run the recovery command against fixture transcripts (including one larger than the bound); assert output size stays under the bound and lists the written files.

**Acceptance Scenarios**:

1. **Given** a fixture subagent transcript of 5 MB, **When** the recovery command runs, **Then** output is at most the configured bound and includes the files the delegate wrote.
2. **Given** a malformed transcript line, **When** the command runs, **Then** it skips the line and reports the skip count.

---

### User Story 4 - Warn on a duplicate in-flight dispatch (Priority: P3)

Before a spawn, the system checks a shared in-flight registry. If the same task is already running from any session, the orchestrator sees a duplicate warning with the other run's identity and an explicit override path.

**Independent Test**: Two hook invocations with the same task key from different session ids; assert the second gets the duplicate warning; after the first is released or expires, assert no warning.

**Acceptance Scenarios**:

1. **Given** an in-flight entry for task key K from session S1, **When** session S2 spawns K, **Then** S2 sees the duplicate warning naming S1.
2. **Given** an entry older than its expiry, **When** a spawn for K runs, **Then** the stale entry is ignored and replaced.
3. **Given** intentional fan-out marked with the override, **When** spawns share K, **Then** no warning.

### Edge Cases

- Description begins with a persona inside a rung label, for example "Workhorse (terra-pair)": not a prefix match; no response.
- Claude subagent that supervises a real Codex worker and is named after it: name the Claude rung first and mention the Codex worker later in the text; the prefix check then does not deny it.
- Transcript path absent or unreadable: recovery command exits non-zero with a clear message.
- Registry directory unwritable: the duplicate check fails open (no block, one stderr line), because the hook must never break the session.
- `DelegateAgent` (MCP) calls: not covered by the `Agent|Task` matcher; see Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workerbee skill MUST state one naming rule for dispatch descriptions: Claude dispatches use rung names or Claude model names; Codex persona names appear only on dispatches that reach a Codex model.
- **FR-002**: The owned `PreToolUse` hook MUST detect an `Agent`/`Task` description that begins with a Codex persona name and deny the call. Detection MUST use exactly the regex `(?i)\A(?:astra|sol|terra|luna)(?=\s|:|/|\Z)` (prefix-only, case-insensitive, a hyphen is not a delimiter). The deny reason MUST be this text verbatim: "FR-002: Agent/Task descriptions cannot begin with a Codex persona name. For Codex execution, dispatch through agents-inc; Agent/Task creates Claude subagents. If this names a product, repository, person, or supervised worker, put the actual Claude rung first and mention that name later. Renaming does not change the execution model." The deny payload shape MUST match the known-working Claude Code `PreToolUse` deny emitter `~/.claude/scripts/no_claude_md_guard.py` (read-only reference). This deny is the only blocking behavior in the hook; malformed payloads and exceptions still fail open.
- **FR-003**: The workerbee skill MUST require a one-line hierarchy and model statement before the first dispatch whenever an operator turn names two roles without an explicit order, or names models that differ from the ladder. The canonical order is D34: Executive above Supervisor (= Orchestrator). The line names the concrete model for each role.
- **FR-004**: Operator-named models MUST override ladder defaults; the conflict MUST be stated, not silently resolved.
- **FR-005**: A recovery command MUST read a subagent transcript and print a bounded summary: final status, last assistant text (truncated), files written or edited, last tool error, and the count of skipped lines. It MUST NOT print the full transcript.
- **FR-006**: An in-flight registry MUST record spawns keyed by a normalized task key, shared across sessions, with expiry and release, stored in the user-scope agents-inc state directory. The duplicate check MUST warn only (never block), name the other session, and offer an override.
- **FR-007**: Every hook behavior except the FR-002 deny MUST fail open: an exception never blocks the host session (`hook.py` contract).
- **FR-008**: Tests MUST use fixture payloads and transcripts and a fake HOME. No test reads real `~/.claude/projects` data.
- **FR-009**: Changes to `skills/workerbee/SKILL.md` are canon changes and MUST be listed as `LESSON-CANDIDATE` items for Executive sign-off before they are treated as ratified.

### Key Entities

- **Persona name**: one of `astra`, `sol`, `terra`, `luna`.
- **Task key**: normalized identity of a dispatched task, used for duplicate detection.
- **In-flight entry**: task key, session id, start time, expiry.
- **Recovery summary**: bounded extract of one transcript.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The hook denies 4 of 4 addendum deny fixtures (`terra: implement X`, `Luna - triage logs`, `sol reviews spec`, `ASTRA: review hook`) and 0 of 6 addendum allow fixtures (`Solve flaky test`, `Terraform plan review`, `Sol-gel fit`, `Lunation calculation`, `Haiku reviews luna doc`, `terra-pair review`); the two documented collisions (`Astra DB migration`, `Luna repo cleanup`) are denied. A supervisor-owned test holding these fixtures exists before implementation. If the 24 #17-corpus descriptions are reachable read-only, the regex matches 24 of 24; if not reachable, the batch report says so.
- **SC-002**: Recovery output on a 5 MB fixture stays at or below 4,000 characters.
- **SC-003**: A cross-session duplicate fixture produces the warning in 100% of runs; intentional fan-out with the override produces it in 0%.
- **SC-004**: The unit suite shows only the known pre-existing failure.

## Assumptions

- `DelegateAgent` (MCP) dispatches carry an explicit model argument and are out of scope for the hook; the skill rule still applies to them.
- The recovery command reads transcripts only; it never writes to `~/.claude/**`.
- The existing advisory nudge stays; new checks extend the same hook entry rather than adding a second one.
