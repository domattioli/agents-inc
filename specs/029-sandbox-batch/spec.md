<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-28 skill=speckit-analyze repo=agents_Inc session=b027a483-3613-4691-bfdd-d5c85383077c -->
# Feature Specification: agents-inc under the Claude Code sandbox (batch)

**Feature Branch**: `029-sandbox-batch`
**Created**: 2026-10-28
**Status**: Draft
**Input**: User description: "Batch of five asks (fifth added by operator ruling 2026-10-28: installer allow rule) for running agents-inc inside the Claude Code Bash sandbox: #113 (tests fail under the sandbox), #112 item 2 (doctor does not probe the dispatch path), #112 item 3 (Codex reads stop at --cwd), #122 (gh TLS failure in the sandbox). Out of scope: #112 item 1 (NETWORK slot), #114."

## Clarifications

### Session 2026-10-28

- Q: Should the dispatch-path probe run on every `doctor` call, or only on request? → A: Only on request, with an opt-in flag `--probe-dispatch`; plain `doctor` makes no new network calls.
- Q: When the requested probe fails, is that a blocking code or a warning? → A: Model API unreachable (blocked or certificate) is a blocking code (`READY` off); a GitHub failure, blocked or certificate, is a warning only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Test suite passes inside the sandbox (Priority: P1)

A developer runs the full unit test suite from a sandboxed Claude Code session. Today 11 tests fail there and pass outside it (#113). After this change, the suite gives the same result in both places.

**Why this priority**: Agents run the suite from sandboxed sessions to verify their own work. A suite that fails for environment reasons hides real regressions and trains agents to ignore red results.

**Independent Test**: Run the suite inside the sandbox and outside it on the same commit. Compare the counts.

**Acceptance Scenarios**:

1. **Given** a sandboxed Claude Code Bash shell, **When** the developer runs the full suite, **Then** it reports no failures and no errors.
2. **Given** an unsandboxed shell on the same commit, **When** the developer runs the full suite, **Then** it reports the same number of tests run as the sandboxed run, with no failures and no errors (skip counts may differ only for tests that skip on a missing sandbox or network by design, and each such skip is named).
3. **Given** the three free-provider wrapper scripts, **When** each runs, **Then** it writes no fixed name under `/tmp`: health-report stderr is discarded, and `oask`'s response body goes to a unique file under the caller's temp directory that is removed before exit.

---

### User Story 2 - Doctor tells the truth about dispatch reachability (Priority: P2)

An operator runs `agents-inc doctor` from a sandboxed session. Today doctor can print `READY` while a dispatch from that same session cannot reach the model API (#112 item 2). After this change, doctor can start a child process the way dispatch does and report whether that child reaches the model API and GitHub.

**Why this priority**: A false `READY` sends the operator into a failed dispatch with no clear cause. It is the root of the dead ends recorded in D65 and D66.

**Independent Test**: Run the doctor probe in a sandboxed shell where the model API is blocked, and in an unsandboxed shell where it is reachable. Doctor runs inside the sandbox, e.g. `bash -c 'agents-inc doctor --probe-dispatch'`, so the exclusion does not match. Doctor reports a different, named result in each.

**Acceptance Scenarios**:

1. **Given** a session where a dispatch child cannot reach the model API, **When** the operator runs the doctor probe, **Then** doctor names the failure with a stable code and a one-line fix, and does not print `READY` for the dispatch path.
2. **Given** a session where the child reaches the model API and GitHub, **When** the operator runs the doctor probe, **Then** doctor reports both reachable.
3. **Given** the child reaches GitHub over the network but `gh` fails certificate verification, **When** the probe runs, **Then** doctor reports that case with its own code, separate from "host blocked" (links to User Story 4).
4. **Given** doctor runs without the opt-in probe flag, **When** it finishes, **Then** it makes no network calls beyond what it makes today.

---

### User Story 3 - Dispatchers know Codex reads stop at --cwd (Priority: P3)

An agent writes a dispatch prompt for a Codex rung (astra, sol, terra, luna). Today a Codex delegate cannot read a file outside `--cwd`, and the brief may name such a file (#112 item 3, run `20261020T015238Z-astra-2eec43`). After this change, the delegation prompt contract says so, and tells the dispatcher to paste excerpts.

**Why this priority**: One line of guidance prevents a wasted dispatch. It is small and has no runtime risk.

**Independent Test**: Read the prompt contract and the quick reference. Both carry the rule in the same words.

**Acceptance Scenarios**:

1. **Given** the 14-field prompt contract, **When** a dispatcher reads it, **Then** it states that a Codex delegate cannot read paths outside `--cwd` and that the dispatcher must paste the needed excerpts into the prompt.

---

### User Story 4 - gh TLS failure in the sandbox is documented and detected (Priority: P3)

An agent calls `gh` from a sandboxed Bash call on macOS. Every call fails with `x509: OSStatus -26276` even when `api.github.com` is allowed (#122). After this change, the operator docs name the cause as outside this repo, give the working routes, and doctor detects the condition (User Story 2, scenario 3).

**Why this priority**: The fix lives in Claude Code, not here. This repo can only stop agents from losing time on it.

**Independent Test**: Search the docs for the error string. Find the workaround. Run the doctor probe in a sandboxed shell as `bash -c 'agents-inc doctor --probe-dispatch'`, so the `agents-inc *` exclusion does not match, and see the named code.

**Acceptance Scenarios**:

1. **Given** an agent sees `x509: OSStatus -26276` from `gh`, **When** it searches the workerbee quick reference or troubleshooting table, **Then** it finds the routes that work: the GitHub MCP tools, or `gh` run outside the sandbox.
2. **Given** the docs, **When** an operator reads the #122 entry, **Then** it says the cause is not confirmed and points to the upstream report if one is filed, or states none is filed.

### User Story 5 - Install grants the plain dispatch command (Priority: P2)

A consumer installs agents-inc. Today the installer adds the `agents-inc *` sandbox exclusion but no permission allow rule, so every `agents-inc` call from the operator's session raises a permission prompt. After this change, install adds one allow rule for the plain command, and uninstall removes it.

**Why this priority**: agents-inc exists to enable delegation, not to add friction. A prompt on every dispatch pushes operators toward hand-written rules, which break (the env-prefix rule removed on 2026-10-28 was one).

**Independent Test**: Install into a scratch settings file. Find the allow rule once. Uninstall. Find it gone, with every other rule unchanged.

**Acceptance Scenarios**:

1. **Given** a settings file without the rule, **When** the operator runs install, **Then** the file carries `Bash(agents-inc *)` in `permissions.allow` exactly once, and every other entry is unchanged.
2. **Given** the rule is already present, **When** install runs again, **Then** no duplicate is added.
3. **Given** an installed host, **When** the operator runs uninstall, **Then** the rule is removed, and rules the operator added by hand stay (an identical hand-added `Bash(agents-inc *)` is treated as ours, as with the sandbox exclusion).
4. **Given** install with `--no-host-wiring`, **When** it finishes, **Then** the settings file is not touched.
5. **Given** the rule, **When** a Lead or Worker is dispatched, **Then** its own tool grants are unchanged: the rule applies to the operator's session only (D51, D59).

### Edge Cases

- `TMPDIR` is unset: wrapper scripts fall back to `/tmp`; macOS `mktemp` falls back to `/var/folders/…/T` (research R1).
- `TMPDIR` is set but not writable: the wrapper fails before the request with a non-zero exit and a stderr line; it does not hang and leaves no file behind.
- The doctor probe runs on Linux or with no sandbox at all: it still reports reachability; the sandbox-specific hints are omitted.
- The model API probe hits a timeout: doctor reports `blocked` after a bounded wait, not a hang.
- No network at all (offline laptop): the probe reports both hosts unreachable and does not crash doctor.
- `gh` is not installed: the GitHub check uses the HTTPS request only and adds no code for the absence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The free-provider wrapper scripts (`oask`, `mask`, `gask`) MUST NOT write fixed `/tmp` names. Health-report stderr MAY be discarded (`2>/dev/null`); `oask`'s response body MUST go to a unique file under the caller's temp directory, removed before exit.
- **FR-002**: Every test in the research R1 failure list (test_free_wrappers, test_route_health_freshness, test_install_at_route, test_model_map) that starts a wrapper or routing script MUST give that script a writable temp directory of its own, so the test does not depend on the host's temp policy.
- **FR-003**: The full unit test suite MUST report zero failures and zero errors inside the Claude Code Bash sandbox, with the same number of tests run as an unsandboxed run of the same commit. Skip counts may differ only as US1 scenario 2 allows.
- **FR-004**: The cause of the `mktemp ... Operation not permitted` failures in the at-route install tests and the model-map test MUST be identified and recorded in the plan's research (research.md R1) before it is fixed.
- **FR-005**: `agents-inc doctor` MUST offer a dispatch-path probe, run only when the operator passes an opt-in flag, that starts a child process with the same environment dispatch gives a Worker, and checks from that child whether the model API and GitHub are reachable; the GitHub certificate check also runs `gh` in the caller's environment (where #122 occurs).
- **FR-006**: The probe MUST report each host separately with a stable code: reachable, blocked by the network, or certificate verification failed.
- **FR-007**: Per FR-012, a model API failure turns `READY` off; doctor MUST print one fix line: under the sandbox, a blocked model host gets the D66 route (the `agents-inc *` sandbox exclusion and a plain command); a certificate failure or an off-sandbox host gets a cause line instead.
- **FR-008**: The probe MUST finish within a bounded total time (SC-005) and never hang doctor; a host with no result inside the child budget reports `blocked`.
- **FR-009**: The 14-field delegation prompt contract and the workerbee quick reference MUST state, in the same sentence in both files, that a Codex delegate cannot read paths outside `--cwd` and that the dispatcher pastes the needed excerpts.
- **FR-010**: The workerbee troubleshooting table and quick reference MUST carry a #122 entry: the exact error line, the routes that work (GitHub MCP tools, or `gh` run outside the sandbox), and that the cause is outside this repo and not confirmed.
- **FR-011**: The existing `WB_SANDBOX_EXCLUDE_MISSING` doctor warning (#100) stays as it is; this batch MUST NOT duplicate it.
- **FR-012**: When the requested probe finds the model API unreachable (blocked or certificate failure), doctor MUST add a blocking code and MUST NOT report `READY`. When it finds GitHub blocked or failing certificate verification, doctor MUST add a warning only and `READY` is unaffected.
- **FR-013**: `agents-inc install` MUST add `Bash(agents-inc *)` to the host settings `permissions.allow` once, idempotently, alongside the existing sandbox exclusion; `--no-host-wiring` MUST skip it.
- **FR-014**: `agents-inc uninstall` MUST remove exactly that rule and leave every other allow entry unchanged. The rule MUST NOT change any delegate's tool grants.

### Key Entities

- **Probe result**: one entry per host (model API, GitHub) with a status code, the elapsed time, and a one-line fix when not reachable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full suite run inside the sandbox goes from 10 failures and 1 error to 0 and 0, with the same test count as the unsandboxed run.
- **SC-002**: In a sandboxed session that cannot reach the model API, the doctor probe never reports the dispatch path as ready (0 false `READY` results across the test cases).
- **SC-003**: Each of the three probe outcomes (reachable, blocked, certificate failure) has a test that produces it without live network access.
- **SC-004**: An agent that hits the #122 error finds the working route in one search of the workerbee docs.
- **SC-005**: The doctor probe finishes in under 20 seconds with both hosts unreachable.
- **SC-006**: After install, settings carry `Bash(agents-inc *)` in `permissions.allow` (T039); after uninstall the allow list equals pre-install (T041).

## Assumptions

- The Claude Code sandbox sets a writable per-command `TMPDIR`; scripts that honor it pass under the sandbox.
- The `#122` TLS failure most likely comes from the Claude Code sandbox's proxy CA and the macOS keychain, not from this repo (not confirmed). The repo documents and detects it; it does not fix it.
- "Same environment dispatch gives a Worker" means the existing `worker_env` used by dispatch and by doctor's `--live-model` path.
- The `agents-inc *` exclusion check already shipped in #100 (`WB_SANDBOX_EXCLUDE_MISSING`); D66's open item about `doctor` is therefore closed except for the reachability probe.
- #112 item 1 (`NETWORK` slot) and #114 (Codex git metadata) stay open and out of scope.
- `skills/workerbee/SKILL.md` carries a pre-existing uncommitted edit; plan line anchors (701, 992) must be re-checked at implement.
- Spec artifacts move to DomI `specs/consumers/agents_Inc/` at the end (T038).
- Changes land on `development` through a PR, per the repo's branch rules.
- The installer-managed allow rule targets the operator's own session. It is a new grant decision (recorded as D70 with the rest of this batch), distinct from the delegate grants that D51 and D59 govern.
