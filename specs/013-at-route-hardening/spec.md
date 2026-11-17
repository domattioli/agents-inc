<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: at_route Hardening and Installer Ownership

**Feature Branch**: `development` (spec dir `specs/013-at-route-hardening`; no feature branch, per dispatch)
**Created**: 2026-10-01
**Status**: Draft
**Input**: Batch A of the 2026-10-01 Supervisor dispatch: issues #41 (read-only routed Claude calls, timeout message on exit 142, `agents-inc install` owns `at_route.sh` and the `@alias` links, no drifting copy), #38 (`@openrouter` alias, option a: `oask.sh` default free model, model id in box header, spend guard kept), #32 (close-out evidence only, no code).

## Background (verified 2026-10-01 against HEAD `dd48471` unless noted)

- The `claude` branch of the hook runs `claude -p "$question" --model "$model"` with no tool or permission restriction (`skills/codex-bridge/scripts/at_route.sh:79-80`). A routed call therefore has the full write-capable tool set in the caller's working directory.
- Every routed call runs under a perl `alarm` of `AT_ROUTE_TIMEOUT` seconds, default 120 (`at_route.sh:18`, `:72-74`). SIGALRM gives exit 142. The failure block prints only `call failed (exit N)` plus the child stderr (`at_route.sh:145-151`).
- Issue #41 evidence (from `~/.codex-bridge/at_route.log`, quoted in the issue, not re-read here): a 2026-10-01 `opus` call exited 142 after 120 s and left a half-written `doc/work-log/README.md` in the caller's project.
- `skills/codex-bridge/scripts/install_at_route.sh` copies the hook to `~/.claude/scripts/at_route.sh` and links ten aliases (`haiku sonnet opus fable astra sol terra luna gemini mistral`) in `~/.local/bin` to that copy (`install_at_route.sh:5-10`). The copy is byte-identical to the repo script today (Executive check, 2026-10-01). Nothing detects drift.
- `agents-inc install` already stages a hash-manifested release bundle that includes `skills/codex-bridge` (`agents_inc/install/bundle.py:16`), so `at_route.sh` already ships inside every installed release. `agents-inc doctor` verifies the bundle manifest (`agents_inc/install/doctor.py:29`) and the host wiring (`:37`).
- `agents_inc/install/host_wiring.py` writes receipt-owned, journaled, reversible entries into user-scope host config. It owns `SessionStart` and `PreToolUse` hooks today (`host_wiring.py:89-95`), not `UserPromptSubmit`.
- The alias regex does not include `openrouter` (`at_route.sh:43`).
- Since spec 012, `oask.sh` has no hardcoded default. When `MODEL` is unset it asks `agents_inc.free_health pick-default --provider openrouter` for a health-aware free model (`oask.sh:23-25`). The spend guard refuses any model id without the `:free` suffix with exit 3 (`oask.sh:43-46`). `oask.sh` prints the model it used on stderr as `[openrouter <model> | in N out M]` (`oask.sh:286`).
- Issue #38's 2026-09-23 comment reports the then-hardcoded default as delisted. That finding predates spec 012's health-aware default.
- Lexicon tables: `docs/AT-ROUTE.md:8` and `skills/codex-bridge/SKILL.md:280`. The second file is peer-owned this session.
- The smoke test lives at `skills/codex-bridge/tests/at_route.smoke.sh` (issue #38 names `tests/at_route.smoke.sh`).
- Issue #32 is fixed: `scripts/agents-inc` sets `PYTHONPATH` from its own directory (fix #35), and `agents-inc doctor` run from `/tmp` prints `READY` (Executive check, 2026-10-01).

## Clarifications

### Session 2026-10-01

Answered by the operator through the Executive, 2026-10-01.

- Q: How do routed Claude calls become read-only? → A: Explicit tool allowlist `Read`, `Grep`, `Glob`; write and execute tools (`Edit`, `Write`, `Bash`, `NotebookEdit`) are denied.
- Q: Where does the single installed hook live? → A: Inside the installed release, reached through the `current` symlink (`~/.local/share/agents-inc/current/skills/codex-bridge/scripts/at_route.sh`); the bundle already ships and hash-checks it.
- Q: How severe is the doctor drift code? → A: Warning only; doctor stays READY.
- Q: What happens to the legacy `~/.claude/scripts/at_route.sh` copy, its links, and its settings line? → A: Install replaces the settings line, relinks the aliases to the installed path, and removes the legacy file with a journaled backup that rollback restores.
- Q: What does #38 option a mean now? → A: `oask.sh` with no model override, so its health-aware `free_health pick-default` choice applies; the box header shows the resolved model id.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A routed Claude call cannot change the caller's files (Priority: P1)

The operator types `@opus <question>` or `@@fable <question>`. The routed model answers. Whether the call finishes, fails, or times out, no file in the caller's working tree is created or modified by that call.

**Why this priority**: A routed call that writes files and then dies leaves unexplained partial work, which is the incident in #41.

**Independent Test**: Run the hook with a stub `claude` that records its argv. Assert the argv carries the read-only restriction for every Claude alias.

**Acceptance Scenarios**:

1. **Given** any Claude alias (`haiku`, `sonnet`, `opus`, `fable`), **When** the hook routes a question, **Then** the `claude` invocation allows only the `Read`, `Grep`, and `Glob` tools.
2. **Given** CLI mode (`@opus <q>` through a symlink), **When** the call runs, **Then** the same restriction applies.

---

### User Story 2 - A timeout says it was a timeout (Priority: P1)

A routed call hits the alarm. The session model sees a message that names the timeout, says that partial files may exist, and tells it to run `git status`.

**Why this priority**: Today the session model sees `exit 142` and a perl line, and cannot tell a timeout from a crash.

**Independent Test**: Stub the delegate to sleep past a 1 s `AT_ROUTE_TIMEOUT`; assert the failure block text.

**Acceptance Scenarios**:

1. **Given** `AT_ROUTE_TIMEOUT=1` and a delegate that sleeps 3 s, **When** the hook runs, **Then** the failure block states the call timed out after 1 s, that partial files may exist, and that the session model should run `git status`.
2. **Given** a delegate that fails fast with a non-alarm exit code, **When** the hook runs, **Then** the failure block keeps today's wording and does not claim a timeout.

---

### User Story 3 - One installed hook, owned by the installer, with drift detection (Priority: P2)

`agents-inc install` (and `repair`) owns the `UserPromptSubmit` hook entry and the `@alias` links. They reference one installed path. `agents-inc doctor` reports when that installed hook differs from the source checkout's `at_route.sh`. No other copy of the script text is maintained.

**Why this priority**: Fixes to the hook must reach the operator's machine, and a stale copy must be visible.

**Independent Test**: In a fake HOME, run install, assert the settings hook and links point at the installed path and are receipt-owned; then edit the source script and assert doctor reports drift; then uninstall/rollback and assert the entries are gone.

**Acceptance Scenarios**:

1. **Given** a fake HOME with no hook, **When** `agents-inc install` runs, **Then** the Claude settings file gains one `UserPromptSubmit` hook entry and the alias links exist, all recorded as owned in the receipt.
2. **Given** an installed hook, **When** the source checkout's `at_route.sh` changes, **Then** `agents-inc doctor` reports a drift code.
3. **Given** an installed hook, **When** `agents-inc uninstall` runs, or an interrupted install is rolled back by journal recovery, **Then** the owned hook entry and links are removed and foreign settings entries are untouched.
4. **Given** a pre-existing legacy hook line `bash ~/.claude/scripts/at_route.sh` and legacy links, **When** install runs, **Then** the settings line is replaced by the owned entry, the aliases are relinked to the installed path, and the legacy file is removed with a journaled backup that journal recovery restores if the install is interrupted.

---

### User Story 4 - `@openrouter` alias on the free tier (Priority: P2)

The operator types `@openrouter <question>` and gets a cyan box whose header names the free model that answered. No path through the alias reaches a non-free model.

**Why this priority**: Requested in #38; small once the guard is reused.

**Independent Test**: Stub `oask.sh` to print an answer and the `[openrouter <model> | ...]` stderr line; assert the box header shows the model id. Stub it to exit 3; assert the failover block.

**Acceptance Scenarios**:

1. **Given** a stub `oask.sh` that answers with model `vendor/model:free`, **When** `@openrouter hi` runs, **Then** the box header reads `openrouter (vendor/model:free) · Ns`.
2. **Given** `MODEL=openai/gpt-4o-mini` in the caller's environment, **When** `@openrouter hi` runs, **Then** `oask.sh` receives no `MODEL` value, so its own free-tier selection applies and no non-free model is called.
4. **Given** `oask.sh` exits non-zero (for example spend-guard exit 3), **When** `@openrouter hi` runs, **Then** the failover block tells the session model to answer.
3. **Given** `@@openrouter hi`, **When** the call succeeds, **Then** relay mode injects the answer as for every other alias.

---

### User Story 5 - #32 closed with evidence (Priority: P3)

The spec directory records the command and output proving the launcher works from outside the repo root, so #32 can be closed by the Executive.

**Independent Test**: The evidence file exists and quotes a `doctor` run from `/tmp` with exit code.

**Acceptance Scenarios**:

1. **Given** the evidence file, **When** the Executive reads it, **Then** it contains the command, working directory, output, and exit code.

### Edge Cases

- `AT_ROUTE_TIMEOUT` set to a non-integer: keep today's behavior (perl coerces); out of scope.
- The alarm kills only the direct child; grandchildren of `claude` may survive. Read-only mode limits damage; the message says partial files may exist.
- The settings hook timeout (130 s today, per #41) must exceed the alarm so the alarm fires first.
- `oask.sh` exits 0 but prints no model line: the header shows `openrouter (unknown model)`.
- `WORKERBEES_GOVERNANCE` not `off`: `oask.sh` refuses with exit 3 (`oask.sh:7-10`); the hook emits the failover block.
- Source checkout unknown or missing at doctor time: skip the drift comparison with a warning, never a false drift.
- `~@` escape and non-alias prompts: unchanged.
- Alias links are created only when host wiring is on and `~/.claude` exists. With `--no-host-wiring` or without a Claude host, install creates no links and reports no error.
- After a committed install, the legacy file is not restored by uninstall; its byte-exact backup stays under `~/.local/state/agents-inc/backups/` for manual restore. The `agents-inc rollback` command swaps only the `current` release link, so every hook path and alias stays valid.
- The first `agents-inc doctor` after upgrading to this release, before `repair` runs, prints `READY [WARNING: WB_HOOK_DRIFT_UNCHECKED]`, because the source checkout is recorded only by an install or repair from this release. Exit code stays 0.
- A child process that itself exits 142 is reported as a timeout. Accepted as rare.
- Read-only mode still lets the routed model read any file the caller can read. Accepted; the restriction targets writes and execution.
- The Codex, Gemini, and Mistral branches are not given new write restrictions by this spec (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The hook MUST invoke `claude` for every Claude alias with a restriction that prevents file creation, file modification, and shell command execution. Mechanism: an explicit allowlist of `Read`, `Grep`, and `Glob`; `Edit`, `Write`, `Bash`, and `NotebookEdit` are denied.
- **FR-002**: When a routed call ends by the alarm (exit 142), the failure block MUST state the timeout in seconds, state that partial files may exist in the working tree, and instruct the session model to run `git status` before answering. This applies to every alias kind.
- **FR-003**: Non-timeout failures MUST keep the existing failure block text.
- **FR-004**: `agents-inc install` and `repair` MUST write the Claude `UserPromptSubmit` hook entry and the `@alias` links as receipt-owned, journaled, reversible entries, reusing the `host_wiring.py` pattern. `uninstall` MUST remove exactly the owned entries, and journal recovery of an interrupted install MUST restore every predecessor.
- **FR-005**: The hook entry and every `@alias` link MUST resolve to the installed release copy reached through the `current` symlink (`<install root>/current/skills/codex-bridge/scripts/at_route.sh`), so the path survives repo branch switches and is covered by the bundle hash check. The hook's settings timeout MUST exceed the default `AT_ROUTE_TIMEOUT` (120 s); `docs/AT-ROUTE.md` MUST say that raising `AT_ROUTE_TIMEOUT` needs a matching settings timeout.
- **FR-006**: `agents-inc doctor` MUST report a distinct drift code when the installed `at_route.sh` differs from the source checkout's `skills/codex-bridge/scripts/at_route.sh`. Severity: warning only; doctor stays READY and the CLI exit code is unchanged.
- **FR-007**: Install MUST handle the legacy `~/.claude/scripts/at_route.sh` copy, its links, and its settings line by replacing the settings line with the owned entry, relinking the aliases, and removing the legacy file with a journaled backup that journal recovery restores. The legacy-line removal applies on install and repair only; uninstall touches only the owned entry.
- **FR-008**: `install_at_route.sh` MUST stop creating a second copy; it either delegates to `agents-inc install` or is removed, with `docs/AT-ROUTE.md` updated to match.
- **FR-009**: The alias set MUST include `openrouter` in hook mode, relay mode (`@@`), and CLI mode (`@openrouter` link).
- **FR-010**: `@openrouter` MUST call `oask.sh` without passing a model id and MUST clear any inherited `MODEL` value, so the model always comes from `oask.sh`'s own free-tier selection.
- **FR-011**: The box header for `@openrouter` MUST show the model id `oask.sh` reports on stderr. The relay line and `at_route_answers.log` show the same id.
- **FR-012**: If `oask.sh` exits non-zero (including spend-guard exit 3), the hook MUST emit the failover block so the session model answers.
- **FR-013**: `skills/codex-bridge/tests/at_route.smoke.sh` MUST gain cases for FR-001, FR-002, FR-009 to FR-012, with stubbed `claude` and `oask.sh`. No real model calls.
- **FR-014**: `docs/AT-ROUTE.md` MUST gain the `@openrouter` lexicon row and the read-only and timeout behavior. The same row and the install paragraph (`skills/codex-bridge/SKILL.md:260`, which still tells operators to copy the script to `~/.claude/scripts`) are peer-owned and are planned as `BLOCKED-PEER`.
- **FR-015**: Issue #32 close-out evidence MUST be recorded in this spec directory. No code change for #32.
- **FR-016**: Implement MUST NOT change the live machine. Installer behavior is tested with a fake HOME only; the Executive runs the real `agents-inc repair`.

### Key Entities

- **Installed hook path**: the one file path the settings hook and the alias links resolve to.
- **Owned hook entry**: a `UserPromptSubmit` command in the Claude settings file recorded in the install receipt.
- **Drift code**: a doctor code naming a mismatch between installed and source `at_route.sh`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 4 of 4 Claude aliases invoke `claude` with the read-only restriction in the smoke test.
- **SC-002**: In 100% of timeout cases in the smoke test, the failure block names the timeout seconds and `git status`; in 0% of non-timeout failure cases does it claim a timeout.
- **SC-003**: Doctor reports drift in every fixture where installed and source scripts differ, and reports no drift where they match.
- **SC-004**: Install then uninstall in a fake HOME leaves a settings file that has no legacy at_route line byte-identical to its pre-install state, when that file uses the installer's JSON style (2-space indent, trailing newline). The one allowed residue is the empty `hooks` object that `remove_host_wiring` has left since `dd48471`. A legacy line is migrated, not restored.
- **SC-005**: 0 smoke cases reach a non-`:free` model through `@openrouter`.
- **SC-006**: `bash skills/codex-bridge/tests/at_route.smoke.sh` exits 0, and the unit suite shows only the known pre-existing failure.

## Assumptions

- Routed Codex calls go through `ask.sh --fresh` under the bridge's own sandbox; hardening them is out of scope for #41, which names only the Claude branch.
- `oask.sh` model selection (`free_health pick-default`) is used as-is; `agents_inc/free_health.py` is peer-owned and is not edited.
- Option d (retry the next free model on 429/404) and option c (tiers) from #38 are out of scope.
- The `@alias` count becomes eleven with `openrouter`.
- #38 idea list (inbox digest, per-alias threads, notebooks, triage verbs) is out of scope; idea 3 (read-only allowlist) is covered by FR-001.
