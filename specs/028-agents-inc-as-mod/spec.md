<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-24 skill=speckit-specify repo=agents_Inc session=20261025T001616Z-opus-44e257 -->
# Feature Specification: agents-inc becomes a Claude Code mod (luna first)

**Feature Branch**: `028-agents-inc-as-mod` (spec only; no branch created by this run; spike evidence lives on `spike/luna-turn-step`)
**Created**: 2026-10-24
**Status**: Draft
**Input**: Operator direction 2026-10-24, verbatim: "agents inc is becoming a mod. suggestion 3". Every rung (luna, sol, terra, astra, gemini, mistral, openrouter) runs as a native Claude Code subagent type. A mod's `turn.step` hook answers that subagent's model steps through the provider. The harness owns tools, permissions, prompts and hand-back. agents-inc drops its own sandbox and isolation machinery (spec 026 sandbox-safe runs, the fake `CODEX_HOME` isolation, the dispatch gates) in favour of native harness constraints. Nothing in `agents_inc/` is removed before this spec. Operator also said: luna only for now, other rungs after 028; "i want it to actually be luna" (it works exactly like a haiku subagent).

## Background (spike evidence)

- The spike mod `mods/luna-brain/` registers one agent type whose model is a placeholder (`model: 'haiku'`, `mods/luna-brain/hooks/luna.ts:254`). Its `turn.step` hook answers every step of that agent by running `agents-inc run --model luna --effort low --no-tools --host-tools --thread <file>` (`luna.ts:294`). It yields text, tool and stop chunks, so no Anthropic request is made for that agent (commit `60bd01f`).
- The agent sets no tools and no permission mode, so it inherits the parent's like any native subagent (`luna.ts:249`, commit `e791021`).
- Commit `cff7df4`: a Docker stress run passed 20 of 20 over four scenarios (`latin`: no tools; `tools`: Bash and Read; `follow`: a SendMessage follow-up; `par`: three agents in parallel) (`docker/luna_stress.sh:19-24`).
- Codex 0.159.2 needed a host-tools run: a replaced base instruction text (`agents_inc/install/runtime.py:329-333`) and a one-model catalog copy that removes `exec`, `exec_command`, `apply_patch` and the collaboration tools (`runtime.py:336-364`). Before that, luna sent tool requests to Codex's own tools; dispatch reports it tried `apply_patch` with `*** Delete File` six times, and only Codex's read-only sandbox stopped it.
- `request_user_input` stays offered in every Codex configuration tried; dispatch reports 27 wasted calls per run.
- A fresh `CODEX_HOME` has no `models_cache.json`, so the stripped catalog cannot be built and the first run keeps Codex's full catalog (`runtime.py:352-360`).
- luna can write its tool request in one intermediate message and then a final message that guesses the result ("B=1"). The first message that requests tools must win (`luna.ts:176-185`).
- Other spike faults the mod already handles: a background subagent on some builds has no `SubagentHandback` (`luna.ts:371-373`); Codex reports running token totals, so per-step usage is the rise since the last total (`luna.ts:313-327`); a compacted conversation starts a fresh thread (`luna.ts:383-384`); a reply that refuses or skips a needed tool gets one push (`luna.ts:21-26`, `luna.ts:406-413`).

## Clarifications

### Session 2026-10-24

- Q1: Does 028 delete the shared sandbox, isolation and dispatch-gate code that other rungs still use? → A: No. 028 stops using it for luna only; the code is deleted in the spec that moves the last rung.
- Q2: Which agents-inc checks survive for a luna native subagent? → A: The mod writes the ledger record and runs the scope snapshot check at spawn and hand-back; the parent verifies the report as it does for any subagent.
- Q3: During 028, what happens to `agents-inc dispatch --model luna`, broker luna Workers and `@luna`/`@@luna`? → A: They keep working unchanged beside the native type, and serve as the rollback route.
- Q4 (analyze F7): Constitution P7 says luna is not an Agent-tool subagent model; does 028 amend it? → A: Yes. Amend P7 (MINOR version bump) to allow a native subagent type whose steps a Codex rung answers; D69 records it.
- Q5 (analyze F8): Does P8's prompt-contract lint bind a native subagent call? → A: No for the `agents-inc:luna` type only. P8 still binds every other dispatch, Claude Agent-tool calls included; for a luna call, P3 holds through the parent's verification. D69 records it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - luna runs as a native subagent (Priority: P1)

The CoS session, or the operator, starts a subagent of the luna type with the Agent tool, exactly as it would start a haiku subagent. The subagent gets the same tools, permission decisions, system prompt, transcript window, hand-back, SendMessage follow-ups and background mode as a haiku subagent. Every model step is answered by luna. No step is answered by a Claude model.

**Why this priority**: This is the operator's ask ("i want it to actually be luna"). It ships alone: with only this story, Grunt work can go to luna with a native live view, native permissions and no Claude tokens per step.

**Independent Test**: Run the four stress scenarios (no tools, Bash and Read, SendMessage follow-up, three in parallel) once with the haiku type and repeatedly with the luna type, on macOS and in the Linux dev container. Compare outcomes, permission decisions and transcript shape.

**Acceptance Scenarios**:

1. **Given** the mod is installed and Codex is logged in, **When** a session calls the Agent tool with the luna subagent type and a task that needs Bash and Read, **Then** each tool call goes through the parent session's permission rules and sandbox as it would for a haiku subagent, the results reach luna in the next step, and the hand-back carries values read from those results.
2. **Given** a finished luna subagent, **When** the parent sends it a follow-up with SendMessage, **Then** luna answers in the same Codex thread with the new messages only, and states that it is luna (the `follow` scenario expects `gpt-6`, `docker/luna_stress.sh:24`).
3. **Given** three luna subagents started in one message, **When** they run in parallel, **Then** each keeps its own Codex thread and each reports its own value.
4. **Given** a build where a background subagent has no `SubagentHandback`, **When** luna finishes, **Then** its last plain reply ends the run and it never calls a tool the harness did not offer.
5. **Given** any luna step, **When** the step completes, **Then** the parent sees luna's token usage for that step only, tagged with the luna model slug, not a Claude model.

---

### User Story 2 - luna cannot act outside the harness (Priority: P1)

Every action luna takes on files, shell, network or the operator goes through a harness tool call. The Codex process that answers a step offers luna no tool of its own that can change anything, so the harness permission system is the only gate that matters.

**Why this priority**: The operator retires agents-inc's own sandbox for this path. That is safe only if Codex cannot act on its own. The spike showed luna reaching for `apply_patch` delete before the catalog copy existed.

**Independent Test**: Run a step whose task asks luna to delete or edit a file, with the harness denying Edit, Write and Bash. Inspect the Codex rollout for the run and the working tree.

**Acceptance Scenarios**:

1. **Given** a luna step, **When** Codex starts, **Then** the model catalog it serves offers no `exec`, `exec_command`, `apply_patch`, collaboration or MCP tool, and the run record names the catalog used.
2. **Given** the stripped catalog cannot be built (no cached entry for the luna slug), **When** a luna step starts, **Then** the step fails with a message that names the cause and the fix, and Codex is not started with its full catalog.
3. **Given** a harness that denies a tool, **When** luna requests it, **Then** luna gets the same denial result a haiku subagent gets, and nothing on disk changes.

---

### User Story 3 - luna never silently becomes another model (Priority: P1)

When luna cannot answer a step (Codex missing, quota spent, timeout, unparsable reply, mod not loaded), the subagent fails loudly. The placeholder Claude model never answers a luna step.

**Why this priority**: A luna subagent that falls back to haiku would report Claude work as luna work and break the routing record. Quota exhaustion must pause and report (constitution P5), never swap provider.

**Independent Test**: Plugin tests with a fake `process.spawn` that fails, times out, prints no JSON, or reports a quota error; plus a test where the spawn hook did not record the agent id. Assert the placeholder model is never called for a luna agent.

**Acceptance Scenarios**:

1. **Given** a luna agent whose spawn the mod did not see, **When** its first step arrives, **Then** the mod still identifies it as luna and answers it through luna, or fails the step; it never passes the step to the placeholder model.
2. **Given** Codex reports a quota or capacity error, **When** the step ends, **Then** the subagent ends with a quota-paused message the parent can see, and no other model is tried.
3. **Given** the mod is not loaded, **When** a session asks for the luna type, **Then** the type is not offered, and the Agent call fails with an unknown-type error.

---

### User Story 4 - install, doctor, rollback (Priority: P2)

`agents-inc install` and `repair` install the luna agent type with the existing agents-inc mod. `agents-inc doctor` says whether luna is ready. The operator can turn the luna type off without uninstalling agents-inc, and the old routes for luna keep working while 028 is in force.

**Why this priority**: Without it the P1 stories work only from a checkout with `--plugin-dir`.

**Independent Test**: Docker clean-install check: install, run the `tools` scenario, run doctor, turn the type off, confirm the type is gone and `agents-inc dispatch --model luna` still works, turn it back on.

**Acceptance Scenarios**:

1. **Given** a clean install with `claude` and Codex present, **When** install finishes, **Then** the luna type is available in a new session and doctor prints a luna readiness line with no new error code, and `READY`.
2. **Given** Codex is not installed (it is optional, D50), **When** a session starts, **Then** the luna type is not offered and doctor prints a warning, not a failure.
3. **Given** the operator turns the luna type off, **When** a new session starts, **Then** the type is not offered, and every pre-028 luna route still works.

---

### User Story 5 - retirement inventory and canon record (Priority: P3)

The plan phase gets a fixed inventory of what 028 retires, keeps and changes (see Inventory below). Canon records the new route.

**Why this priority**: The operator's direction retires machinery. A written inventory keeps the removal reviewable and reversible, and stops a later run from deleting code another rung still uses.

**Independent Test**: Review: every row of the inventory names an existing path and one disposition; the decision record cites this spec.

**Acceptance Scenarios**:

1. **Given** the 028 implement phase ends, **When** the scope is verified, **Then** no file outside the inventory's "change" rows and the files those rows name is edited, and no "keep" row is removed.

---

### Edge Cases

- Fresh `CODEX_HOME` or a wiped model cache: the stripped catalog is missing (US2 scenario 2). The step fails with the fix; it never runs with Codex's full catalog.
- luna writes a tool request in an intermediate message and then a guessed final answer: the first message that requests tools wins; the guessed text is discarded.
- `request_user_input` is offered by Codex in every configuration: a call to it never reaches the operator, counts as a wasted Codex-side call, and is reported in the step's debug line.
- luna names a tool that is not in the harness catalog: the reply is rejected once with a correction; a second bad reply ends the step as unparsable.
- luna requests `SubagentHandback` in the same step as another tool: the hand-back is dropped until the results exist.
- luna answers a task that names a tool without running it, or claims it cannot run tools: one push; a second such reply stands.
- The conversation is compacted below what luna has seen: a fresh thread starts with the full conversation.
- A resumed Codex thread fails: one retry on a fresh thread with the full conversation.
- The parent aborts the subagent: the running Codex process stops and no thread write continues after the abort.
- A step runs past the per-step time limit: the step fails with a timeout message.
- Codex reports running token totals on resume: the step reports only the rise.
- Two sessions in the same repo run luna agents with the same agent id text: thread files never collide across sessions.
- The harness reminder text names tools the task never asked for: the push rule reads only the task text.
- A harness build changes the `turn.step` or agent registration contract: the mod's load-time check fails and the type is not offered (US3 scenario 3).
- The system prompt names the placeholder Claude model: those lines are removed before luna sees them.

## Requirements *(mandatory)*

### Functional Requirements

Native luna subagent (US1):

- **FR-001**: The agents-inc mod MUST register one luna subagent type that a session starts with the Agent tool. The type name MUST contain `luna`, and the Agent tool's `model` parameter is never set to `luna` (constitution P7).
- **FR-002**: The luna type MUST set no tool list and no permission mode of its own, so it inherits the parent's tools and permission mode exactly as a haiku subagent does.
- **FR-003**: Every model step of a luna agent MUST be answered by the luna pin in `agents_inc/routing.json`. The slug luna is told it runs as MUST come from that pin, not from text fixed in the mod (today `luna.ts:46` fixes `gpt-6-luna`).
- **FR-004**: Each step MUST give luna the harness-composed system prompt (with lines that name the placeholder Claude model removed), the harness tool catalog with argument types, and the conversation. A resumed thread MUST receive only the messages added since luna's last reply.
- **FR-005**: The mod MUST keep one Codex thread per luna agent, so SendMessage follow-ups continue the same thread.
- **FR-006**: When the harness offers `SubagentHandback`, a final luna reply MUST travel through it; when it does not, the final plain reply MUST end the run, and luna MUST NOT be told to call it.
- **FR-007**: When a Codex run emits several messages in one step, the first message that requests tools MUST be the step's reply.
- **FR-008**: Each step MUST report usage for that step only (the rise in Codex's running totals), tagged with the luna slug.
- **FR-009**: The subagent window MUST show luna's progress while a step runs, and its text and tool calls when the step ends, as it does for a native subagent.

Codex has no tools of its own (US2):

- **FR-010**: A luna step MUST start Codex with a model catalog that offers no `exec`, `exec_command`, `apply_patch`, collaboration or MCP tool, and with base instructions that say the host's tools are real and Codex's are not to be used.
- **FR-011**: When that catalog cannot be built (no cached entry for the slug), the step MUST fail with a message naming the cause and the fix, and MUST NOT start Codex with its full catalog.
- **FR-012**: Codex's own read-only sandbox and network-off setting MUST stay on for luna steps, as a second boundary behind FR-010.
- **FR-013**: The Codex process for a luna step MUST NOT load the operator's Codex MCP servers or other Codex-side tool sources.
- **FR-014**: Every Codex-side tool call in a step (including `request_user_input`) MUST be counted and written to the step's debug line. Such a call never reaches the operator or the parent.

No silent fallback (US3):

- **FR-015**: A step of a luna agent MUST NOT be passed to the placeholder model under any failure. A failed step MUST end with a visible message that names the cause: Codex missing, quota or capacity, timeout, unparsable reply, or run failure.
- **FR-016**: Quota or capacity errors MUST end the subagent as quota-paused, with no retry on another provider (constitution P5).
- **FR-017**: The mod MUST identify a luna agent from its type even when the spawn event was missed (today `luna.ts:268-272` checks the agent list; a failed check passes the step to the placeholder, which FR-015 forbids).
- **FR-018**: On abort, the mod MUST stop the running Codex process, and it MUST NOT write further to the thread.

Install, doctor, rollback (US4):

- **FR-019**: The luna type MUST ship in the existing agents-inc mod (`mods/agents-inc/`), so `agents-inc install` and `repair` install it through the spec 027 Q2 path. The spike mod `mods/luna-brain/` stops being a supported install target.
- **FR-020**: The luna type MUST be offered only when the Codex CLI is present and logged in (auth file present); otherwise doctor prints a warning code and `READY` stays.
- **FR-021**: The operator MUST be able to turn the luna type off with one documented switch, without uninstalling agents-inc. Off means the type is not offered in new sessions.
- **FR-022**: The agent gate and the persona deny (`agents_inc/install/hook.py:27-29`, `persona_deny` at `hook.py:107`, `gate_deny` at `hook.py:152`) MUST allow the shipped luna type in every gate mode, and MUST stop allowing the spike `luna-brain:` prefix.
- **FR-023**: Pre-028 routes to luna (`agents-inc dispatch --model luna`, broker luna Workers, `@luna` and `@@luna`) MUST keep working unchanged beside the native type for the life of 028.
- **FR-024**: Debug output MUST NOT write the full step prompt to disk by default (the spike writes `<thread>.prompt.txt`, `luna.ts:389-390`). Thread files MUST stay in a git-ignored directory under the session's working directory and MUST be unique per session and agent.

Retirement and verification (US5):

- **FR-025**: The 028 plan MUST apply the Inventory dispositions below. 028 MUST NOT delete sandbox, isolation or dispatch-gate code that another rung or a pre-028 luna route still uses; the native luna path stops using it, and deletion belongs to the spec that moves the last rung.
- **FR-026**: For a luna native subagent, the mod MUST capture a scope snapshot at spawn, verify it at each hand-back, and keep one ledger node per luna agent, with a return update at each hand-back (model slug, outcome, snapshot result). The snapshot result means "the tree changed during the run": it is informational, not a verdict, and it does not say which agent made the change. Prompt contract lint, report lint and structured gates do not run on this path; the parent verifies the report as it does for any subagent.
- **FR-027**: The 028 implement phase MUST add one `docs/DECISIONS.md` entry that records: the native luna route, which parts of D59, D61 and D62 it amends (D62 rejected wrapping a Codex delegate in a Claude subagent, `docs/DECISIONS.md:644`; D59 limits sub-delegation to dispatch, `docs/DECISIONS.md:628`), and the answers to Q1, Q2 and Q3.
- **FR-028**: The stress suite (`docker/luna_stress.sh`) MUST target the shipped luna type and MUST be the acceptance check for SC-001 and SC-002.

### Key Entities

- **luna subagent type**: a native Claude Code agent type registered by the agents-inc mod. Placeholder Claude model, no own tool list or permission mode. Every step answered by the luna pin.
- **Step**: one model turn of a subagent. Input: system prompt, tool catalog, conversation. Output: text, tool calls, stop reason, usage.
- **Codex thread**: one per luna agent per session; holds luna's view of the conversation; replaced on compaction or a failed resume.
- **Host-tools catalog**: the one-model catalog copy with every Codex-side acting tool removed (FR-010).
- **Codex-side tool call**: a call luna makes to a Codex tool instead of a harness tool; counted, never served to the operator (FR-014).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The four stress scenarios, 10 runs each (40 runs), pass at least 38 of 40 on macOS and at least 38 of 40 in the Linux dev container, with zero runs that report a wrong value.
- **SC-002**: For the same scenarios, a haiku subagent and a luna subagent get identical permission decisions for identical tool requests, and the parent session needs no prompt wording change to use luna in place of haiku.
- **SC-003**: Zero Claude model steps are recorded for any luna agent across all SC-001 runs and the US3 failure tests.
- **SC-004**: Zero file changes and zero Codex-side acting tool calls (`exec`, `exec_command`, `apply_patch`, collaboration, MCP) in the US2 delete-a-file test, over 10 runs.
- **SC-005**: Codex-side `request_user_input` calls per `tools` scenario run fall below the spike's 27, measured from the step debug lines, and are reported for every run.
- **SC-006**: A luna step's reported usage over a 5-step conversation sums to within 1% of Codex's final running total for that thread.
- **SC-007**: After turning the luna type off, a new session offers no luna type, and `agents-inc dispatch --model luna` returns the same outcome class as before 028 on the same slots.
- **SC-008**: The full unit suite and the mod's plugin tests pass, and `git diff --stat` after implement shows no edit to a path the Inventory marks "keep".

## Inventory: what 028 retires, keeps and changes

Scope note: 028 moves luna only. Every other rung keeps its pre-028 route, so shared code stays until the spec that moves the last rung (Q1).

| Path (read for this spec) | Disposition in 028 | FR |
|---|---|---|
| `mods/luna-brain/` (`hooks/luna.ts`, `hooks/luna.test.ts`, `README.md`) | Retire as an install target. Its step logic moves into `mods/agents-inc/`. Change: the folder is removed after SC-001 passes on the shipped type. | FR-019 |
| `mods/agents-inc/hooks/relay.ts`, `relay.test.ts`, relay agent `agents-inc:relay` (spec 027 FR-017 to FR-025) | Keep the behavior for non-luna rungs; for luna, the native transcript supersedes the relay view. Change: `register` becomes `registerRelay`, called from `mod.ts`, because a plugin's `hooks.json` names one module and that module registers `session.start` once. The relay agent and its tool are unchanged. | FR-019 |
| `mods/agents-inc/hooks/mod.ts` (new) | Change: the plugin's one hooks module; its `session.start` calls `registerRelay` and registers the luna type. | FR-001, FR-019 |
| `mods/agents-inc/` (plugin manifest, `hooks/hooks.json`) | Change: gains the luna type and its `turn.step` and `agent.spawn` hooks. | FR-001 to FR-009 |
| `agents_inc/install/runtime.py:319-376` (`NO_TOOL_FEATURES`, `NO_TOOL_INSTRUCTIONS`, `HOST_TOOLS_MODEL`, `host_tools_catalog`, `no_tool_args`) | Keep and change: a missing catalog fails the run instead of falling back; MCP servers and other Codex-side tool sources off for host-tools runs. The same change covers `run_codex` (record line, isolated home and quota exit for host-tools runs) and `run_codex_thread` (Codex-side tool counts) in this file. | FR-010 to FR-014, FR-016 |
| `agents_inc/install/runtime.py:279-316` (`lead_codex_home`, `lead_env`: fake `CODEX_HOME` isolation) | Keep for Codex Leads and broker Codex Workers (luna never leads, D57). `lead_codex_home` is reused unchanged by host-tools runs for FR-013 (the native luna path); `lead_env` is not used by it. | FR-013, FR-025 (Q1) |
| `agents_inc/install/runtime.py:124` (`permission_profile`), `:104` (`tools_for`) | Keep for other rungs and pre-028 luna routes. Not used by the native luna path (tools off). | FR-025 (Q1) |
| `agents_inc/install/dispatch.py:453` (`claude_sandbox_profile`), `:412` (`sandbox_available`), `:371` (`caller_sandbox`), `:363` (`SANDBOX_FIX`), `:383` (`worker_env`) | Keep for remaining routes (spec 026 US2, D65, D68). Not used by the native luna path. | FR-025 (Q1) |
| `agents_inc/install/dispatch.py:194` (`render`), `:218` (`lint_prompt`), `:237` (`lint_report`), `:859-897` (trust record), `:678` (`launch`) | Keep for remaining routes. Use on the native luna path is Q2. | FR-026 (Q2) |
| `agents_inc/install/dispatch.py:2449` (`serve`), `:1906` (`_validate_fields`), `:1612` (`resume`), `:2199` (`resume_cap`); `agents_inc/install/mcp_broker.py`; `agents_inc/install/worker_mcp.py` | Keep. Broker luna Workers are Q3. | FR-023 (Q3) |
| `agents_inc/install/hook.py:27-29` (`BRAIN_PREFIX`), `:107` (`persona_deny`), `:152` (`gate_deny`) | Change: exempt the shipped luna type, drop the spike prefix. | FR-022 |
| `agents_inc/install/live_events.py`, `agents_inc/live_rows.py` (spec 027 Part A) | Keep for remaining routes. | none |
| `agents_inc/install/doctor.py` | Change: luna readiness line and warning codes. | FR-020 |
| `agents_inc/routing.json` (luna pin) | Keep; becomes the source of the slug luna is told (FR-003). | FR-003 |
| `docker/luna_stress.sh` | Change: target the shipped type; acceptance suite. | FR-028 |
| `mods/agents-inc/hooks/luna.ts`, `mods/agents-inc/hooks/luna.test.ts` (new), `mods/agents-inc/README.md` | Change: the step module, its plugin tests, and the luna section of the mod README. | FR-001 to FR-018, FR-021, FR-024, FR-026 |
| `agents_inc/install/luna_native.py` (new) | Change: `agents-inc luna status`, `on`, `off`, `begin`, `end`. | FR-020, FR-021, FR-026 |
| `agents_inc/install/cli.py` | Change: the `luna` subcommand and the doctor luna line. | FR-020, FR-021, FR-026 |
| `agents_inc/host_ledger.py` (`dispatch_row`) | Change: no hook row for `agents-inc:luna`; the mod writes that agent's node. | FR-026 |
| `tests/test_luna_native.py` (new), `tests/test_codex_tool_access.py`, `tests/test_agent_gate.py`, `tests/test_hook_persona_guard.py`, `tests/test_host_ledger.py`, `tests/test_doctor_codex_optional.py`, `tests/test_mod_install.py`, `tests/test_run_thread.py` | Change: tests for the change rows above. | SC-008 |
| `CHANGELOG.md` | Change: one 028 entry. | SC-008 |
| `docs/DECISIONS.md` (new D69) | Change: add D69. | FR-027 |
| `.specify/memory/constitution.md` (P7, P8) | Change: P7 amended for the native luna type and P8 bound to `agents-inc dispatch` prompts (analyze F7, F8; v1.9.0). | FR-001, FR-027 |
| `specs/026-sandbox-safe-runs/spec.md` FR-009 to FR-012 (Worker sandbox metadata), FR-013 to FR-017 (broker lock), FR-018 to FR-021 (control characters), FR-022 to FR-025 (caveman), FR-026 to FR-028 (`--run-dir`) | Keep for remaining routes. None applies to the native luna path. Retirement follows Q1. | FR-025 |
| `specs/027-live-delegate-view/spec.md` FR-001 to FR-016 (events), FR-017 to FR-028 (relay, install) | Keep. Install path FR-028 is reused by FR-019. | FR-019 |
| `docs/DECISIONS.md` D49 and D49.1 (Codex tool access), D51, D57, D60 (broker), D58 (grants and gates), D59, D61, D62, D65, D68 | Keep in force for remaining routes. D59, D61 and D62 amended for luna by the FR-027 entry. | FR-027 |

Canon outside this spec's write scope that 028 makes stale (for the operator, not edited here): constitution P7 says the Codex codenames are not Agent-tool subagent models (`.specify/memory/constitution.md:48`); the machine `AGENTS.md` says Claude's Agent tool cannot select luna; `skills/workerbee/QUICKREF.md` and `SKILL.md` routing.

## Migration and rollback

1. Spike (done): `mods/luna-brain/` on `spike/luna-turn-step`, loaded with `--plugin-dir`.
2. Ship: the luna type moves into `mods/agents-inc/`, installed by `install` and `repair`, offered when Codex is ready. Pre-028 luna routes follow Q3.
3. Soak: the SC-001 suite runs on both hosts; the decision record (FR-027) lands.
4. Retire: shared machinery is removed in the spec that moves the last rung (Q1).

Rollback at any step: turn the luna type off (FR-021), or run `agents-inc repair --no-mod`. Because nothing in `agents_inc/` is removed in steps 1 to 3 (Q1), every pre-028 route still works after rollback (SC-007).

## Assumptions

- The harness keeps the mod contract the spike used: `turn.step` may answer a subagent's step without calling the registered model; `agent.spawn`, `agent.list`, `tool.list`, `prompt.compose`, `session.messages` and `process.spawn` behave as in Claude Code 2.1.310.
- The mod's spawned processes run outside the Bash tool sandbox (spec 027 assumption); the harness permission system governs luna's tool calls, not that sandbox.
- Codex stays optional (D50). luna is unavailable without it.
- The luna type ships enabled by default when Codex is ready; the off switch is the rollback.
- The type name is `agents-inc:luna`, because the mod is named `agents-inc` (spec 027 FR-017).
- luna stays a Grunt that never leads or delegates (D57), so the native type needs no sub-delegation path.
- Per-step cost is Codex subscription only; the placeholder Claude model is never billed for a luna step (constitution P5).
- The 27 `request_user_input` calls per run and the six `apply_patch` delete attempts are dispatch-reported spike figures; the plan re-measures them.
- Other rungs (sol, terra, astra, gemini, mistral, openrouter) are out of scope; each gets its own spec after 028.
