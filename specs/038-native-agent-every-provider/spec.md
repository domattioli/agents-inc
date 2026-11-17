<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-11 skill=speckit-pipeline repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Feature Specification: One native Agent route for every provider

**Feature Branch**: `038-native-agent-every-provider`
**Created**: 2026-11-11
**Status**: Draft (plan-only run; operator answered Q1 to Q5 on 2026-11-11; plan.md and tasks.md updated for Q2 and Q4 the same day)
**Input**: Operator: "extend the claude code native Agent tooling to all possible model providers and models eg openrouter mistral gemini and oai. we've been working toward this but w limited success and a ton of bugs and failures."

## Context (from evidence, not new requirements)

agents-inc reaches models through four user-facing routes today:

1. `agents-inc:luna`, a native subagent type. A `turn.step` hook in `mods/agents-inc/hooks/luna.ts` (644 lines) answers each step with `agents-inc run --model luna --host-tools` (D69). One model only.
2. `agents-inc:relay` plus the tool `mcp__agents-inc__run`, which runs `agents-inc dispatch` for Claude and Codex rungs (spec 027, `relay.ts`).
3. `agent.sh` and the `gask.sh` / `mask.sh` / `oask.sh` wrappers for Gemini, Mistral and OpenRouter free models. Since spec 037 (D75) these also run through `agents-inc dispatch` as kind `free`: text only, no tools, allowed task kinds only.
4. Broker Workers and Leads (`dispatch --serve`).

Each route has its own cwd rules, run directory, ledger rows, guards (persona deny, compound deny, credential screen, gate deny), pane wiring and install artifact. Issue evidence (`.scratch/issues/`): #160 (luna empty reply), #135 and #155 (sandboxed caller, relay cwd), #154 (Codex delegates missing from the pane), #147 (relay snapshot on non-git root), #146, #95, #87, #85 (text guards false positives), #148 (`@@` aliases cannot read files), #141 (free launcher). A transcript study of 2,502 sessions (`.scratch/hypotheses/`) found two separate causes: (H1) many routes cause per-route text guards and per-route install copies, which cause false positives and drift; (H2) the Claude Code sandbox and permission classifier blocking agents-inc subprocesses (exit 69 `caller-sandboxed`), the most frequent single failure. Route collapse addresses H1. It addresses H2 only to the extent that a mod's `$.process.spawn` runs outside the Bash tool sandbox, which this spec requires be measured, not assumed (FR-019).

The luna design already works without native function calling: the model replies with one JSON object `{"say", "tools": [{name, input}]}` as text, and the hook turns it into tool-use blocks that Claude Code runs under its own permission rules. That text protocol is model-agnostic, so it is the tool-call adapter for providers whose wrappers are text-only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - luna keeps working on the shared step loop (Priority: P1, slice 1)

A session starts `subagent_type: "agents-inc:luna"` and gets the same behaviour as today: tool calls run under Claude Code permission rules, the report comes back through `SubagentHandback`, failures read `luna failed: ...` or `luna quota-paused: ...`, the placeholder model is never called.

**Why this priority**: The shared loop is only safe if the one route that works today does not regress. It is the first shippable slice.

**Independent Test**: The existing `mods/agents-inc/hooks/luna.test.ts` cases pass unchanged against the new loop plus Codex adapter, and `docker/luna_stress.sh` scenarios `tools`, `par`, `steps5` score at least the D69 baseline (38 of 40 on the four main scenarios, Linux container).

**Acceptance Scenarios**:

1. **Given** the shared loop and the Codex adapter installed, **When** a luna agent runs `wc -l a.txt` with Bash, **Then** the Bash call appears as a native tool use, runs under the session's permission rules, and the report states the real count.
2. **Given** Codex quota is exhausted (exit 75), **When** a step runs, **Then** the result reads `luna quota-paused: ...`, no retry is made, and no other model is called.
3. **Given** the agent id cannot be identified, **When** a step runs, **Then** the step fails closed with a text answer and the placeholder model is not called.

---

### User Story 2 - A free model runs as a native agent with tools (Priority: P1, slice 2)

A session starts `subagent_type: "agents-inc:<free model>"` (first: one Gemini free model) and the model reads files and runs commands through the same text tool protocol, gated only by Claude Code permission rules.

**Why this priority**: This is the operator's goal: the native Agent tool reaches non-Claude, non-Codex providers. One provider proves the adapter interface.

**Independent Test**: In the docker image with a fake provider server, an agent of the new type runs the `tools` scenario (Read then Bash then hand back) and reports values that match the tool results. With a real key on the operator Mac, one live probe passes.

**Acceptance Scenarios**:

1. **Given** a Gemini free model passed its live probe, **When** the session starts, **Then** `agents-inc:gemini-flash` (name per FR-006) is offered to the Agent tool.
2. **Given** the provider returns text that is not a valid JSON reply, **When** the step runs, **Then** one correction is sent; a second failure ends the step with `<agent> failed: unparsable reply`.
3. **Given** the provider key is missing, **When** the session starts, **Then** the type is not offered and `agents-inc doctor` says why; no step is attempted.
4. **Given** the data rules of FR-012 refuse the workspace, **When** the session starts, **Then** the type is not offered and doctor names the rule.

---

### User Story 3 - Every probed model is a native type; the pane lists only those (Priority: P2)

Mistral, OpenRouter free slugs and further Codex models (sol, terra, astra) each get a type once their adapter exists and the model passes a live probe. The pane lists only agents that can be opened.

**Independent Test**: With probes stubbed pass for three models and fail for one, the session registers exactly three types and the pane shows exactly those three plus any running native agents.

**Acceptance Scenarios**:

1. **Given** a model whose last probe failed or is older than the probe TTL, **When** the session starts, **Then** no type is registered for it.
2. **Given** a running native agent of any provider, **When** the pane renders, **Then** it lists the agent and opening it shows its native transcript.

---

### User Story 4 - Old routes stop being user-facing (Priority: P3)

The relay agent, the `mcp__agents-inc__run` tool, `@`-alias routes and the `agent.sh` wrappers are no longer how a user or session reaches a model. What stays internal is stated in FR-015.

**Independent Test**: A fresh `agents-inc install` in the docker image registers no `agents-inc:relay` type and no `mcp__agents-inc__run` tool unless the compatibility flag of FR-016 is set; QUICKREF and README name only native types.

---

### Edge Cases

- A provider has native function calling. The adapter still uses the text protocol in v1 (one protocol, one parser); native function calling is an adapter-local optimisation for later.
- The conversation outgrows a free model's context window. The adapter refuses the step with `<agent> failed: context over <n> chars`; it never truncates silently (same rule as D75 input limits).
- A model answers with a tool not in the catalog. Rejected with one correction, as luna does today (`parseReply` with `allowed`).
- Compaction shrinks the message list. Stateless adapters resend the whole conversation; the Codex adapter starts a new thread (existing luna rule).
- The step is aborted. Adapter process is stopped, the step is not marked used, the outcome is `aborted`.
- Host sleeps mid-step. The step timer runs on the monotonic `$.clock.sleep`, as today.
- Two native agents of different providers run at once in one tree. Each has its own begin/end snapshot; the changed-tree line names that misattribution can occur (#145) and is not fixed here.
- A free provider redacts identifiers (OpenRouter PII filter). The reply is used as is; redaction is reported in the step log, not treated as failure.

## Requirements *(mandatory)*

### Functional Requirements

**Shared step loop**

- **FR-001**: The mod MUST hold one provider-neutral step loop that does what luna.ts does today: catalog and prompt build, reply parse with allowed-tool check, one correction, one push on refusal or early stop, handback handling, fail-closed agent identification, abort and timeout, usage accounting, begin/end working-tree snapshot.
- **FR-002**: Provider-specific behaviour MUST live in one adapter per provider with a fixed interface (contracts/step-adapter.md): `status()`, `ask(prompt, state) -> stream of progress + Outcome`, failure classification, and whether the adapter keeps a thread (Codex) or resends the conversation (stateless HTTP).
- **FR-003**: The Codex adapter MUST reproduce luna.ts behaviour with no regression (US1 test). luna.ts is removed only after the Codex adapter passes the full luna test file and the stress baseline.
- **FR-004**: Model-specific prompt text (identity line, refusal pushes tuned to Codex's `request_user_input` habit) MUST live in the adapter, not the loop.

**Registration and probes**

- **FR-005**: The mod MUST register one agent type per model that is enabled, has its credential present, passes the data rules (FR-012) and has a passing live probe within the probe TTL.
- **FR-006**: Type names MUST be `agents-inc:<nickname>` where the nickname comes from the roster (`luna`, `sol`, `terra`, `astra` for Codex; one short nickname per free model in `models.json`). Persona-to-vendor binding (P7) holds: a nickname names exactly one vendor.
- **FR-007**: The live probe MUST be a minimal tool-protocol round trip (one Read tool request expected), recorded in the install state with model, time, result. It runs from `agents-inc doctor --probe` and `agents-inc models probe`, never at session start, so session start makes no network call.
- **FR-008**: Session start MUST read probe state through one CLI call (`agents-inc native status --json`, generalising `agents-inc luna status`), returning per model `{offered, slug, reason}`.
- **FR-009**: `agents-inc native on|off <nickname|all>` MUST replace `agents-inc luna on|off`; `luna on|off` stays as an alias.

**Tool protocol for text-only models**

- **FR-010**: Free adapters MUST use the luna JSON reply protocol (`{"say", "tools"}`) carried as plain text, so no provider-native function calling is required.
- **FR-011**: Free adapters MUST call the provider from Python standard library code inside `agents-inc` with the key read from the key store in-process and sent in a request header; the key MUST NOT appear in argv, env passed to children, prompts or logs. The legacy wrappers are not called by native agents.

**Data and spend rules**

- **FR-012**: A free-provider type MUST NOT make a provider call in a workspace that has no recorded authorization for that provider. The first start asks the operator once and stores the record; `agents-inc native allow <provider> --workspace <path>` writes the same record. A declined or absent record ends the start before any provider call. A native agent sends repository contents and free providers may log prompts. See Clarification Q2.
- **FR-013**: Only $0 slugs MAY be registered: the D75 `FREE_MODELS` map and Codex models reached through the operator's Codex CLI login. No paid API key path, no paid fallback. A quota response ends the step `quota-paused`; it never switches model.
- **FR-014**: Free-provider native types widen optional providers beyond D75's extract/summarize/classify Grunt work. This MUST be recorded as a new D-entry before slice 2 ships (Clarification Q1).

**Route collapse**

- **FR-015**: Internally kept, shared by every native type: the run directory under the install state (one per agent), `events.jsonl` rows written by the loop for the pane, the host-ledger record (`source: native-<provider>`), the begin/end working-tree snapshot. Not applied to native types: dispatch slot rendering, the 14-field prompt contract lint, broker sandbox, credential text screen on prompts, compound-command deny. Verification gates stay a parent duty (P3): the parent verifies the report.
- **FR-016**: The relay agent, `mcp__agents-inc__run`, and `@`-alias routes MUST stop being registered by default once US3 ships; `agents-inc install --legacy-routes` keeps them for one release. `agents-inc dispatch` stays as a CLI for scripts, CI and broker Workers, and is not removed by this feature.
- **FR-017**: The agent gate (`NATIVE_TYPES` in `hook.py`) MUST derive the native type list from the same registry the mod reads, not a hand-kept list, so no second copy drifts.
- **FR-018**: There MUST be one install artifact for the native route: the mod bundle, versioned with the Python package; `agents-inc doctor` MUST report a mod/package version mismatch.

**Sandbox**

- **FR-019**: Before slice 2 ships, a docker-free test on the operator Mac MUST record whether `$.process.spawn` from a mod runs inside the Claude Code Bash sandbox (proxy env present, `SANDBOX_RUNTIME` set) and whether the provider host is reachable from it. The result goes into research.md and decides whether native free types need `sandbox.network.allowedDomains` entries, which `doctor` then checks.

**Pane**

- **FR-020**: The pane MUST list only native agents (running or finished in the session) and registered types; it MUST NOT list run directories that cannot be opened as a transcript.

### Key Entities

- **Adapter**: provider id, kind (`thread` or `stateless`), status check, ask, failure classifier, prompt fragments.
- **NativeModel**: nickname, provider, slug, max context chars, enabled switch, probe record.
- **ProbeRecord**: model, time, result (`pass`/`fail`/`skipped`), reason.
- **WorkspaceAuthorization**: workspace path, provider, time, operator note.
- **StepOutcome**: reply or rejection reason, failed flag, failure text, retry allowed, usage.

## Success Criteria *(mandatory)*

- **SC-001**: luna on the shared loop scores at least the D69 baseline in `docker/luna_stress.sh` (38 of 40 main scenarios, 10 runs each, Linux container) and passes every existing luna.test.ts case.
- **SC-002**: One free provider (Gemini) passes the `tools`, `par` and `steps5` scenarios at least 7 of 10 each against a recorded fake server in docker, and one live probe on the operator Mac.
- **SC-003**: Per-provider code beyond the loop is at most 200 lines per stateless adapter.
- **SC-004**: After US4, a fresh install exposes exactly one user-facing route (native types) and zero text guards that apply only to one route.
- **SC-005**: Zero provider keys in argv, prompts or logs, checked by a test that scans spawned argv and written files for the fake key.
- **SC-006**: Session start adds no network call (measured by the fake-server request count staying 0 during start).

## Assumptions

- The mod API surface used is only what luna.ts and relay.ts already use: `on('turn.step')`, `on('agent.spawn')`, `on('agent.offer')`, `on('turn.complete')`, `$.agent.register`, `$.agent.list`, `$.tool.list`, `$.prompt.compose`, `$.session.messages`, `$.process.spawn` (streaming, with stdin), `$.fs`, `$.clock`, `$.ui.log`. No new API is assumed.
- `$.agent.register` can be called once per model in one `session.start`; luna.ts and relay.ts already make two calls, so several are expected to work. Verified in slice 2 (T-task), not assumed beyond that.
- OpenAI models are reached only through Codex CLI login ($0 under the operator plan); an OpenAI API key route is out of scope (P5).

## Clarifications

### Session 2026-11-11 (operator unreachable; answers are recommendations, marked OPEN where the operator must rule)

- Q1 (ANSWERED 2026-11-11, operator): Free providers may do general agent work, per authorized workspace, recorded in a new D-entry. Writes by a free model are limited to designated directories named in the authorization record, and only for a model whose probe passes the tool-protocol check. Operator note: free tiers may be too weak; the probe gate decides, and a provider with no passing model gets no type.
- Q2 (ANSWERED 2026-11-11, operator; resolution by the supervisor from the operator's concern that a command-only gate is too restrictive while failed dispatches waste tokens): a free-provider type is offered in every workspace. Its first start in a workspace asks the operator once (provider named, what is sent, write directories) and stores a per-workspace, per-provider record; later starts do not ask. `agents-inc native allow <provider> --workspace <path>` writes the same record for scripted setups. A declined or absent record ends the start before any provider call, with one clear line, so no tokens are spent. FR-012 is amended to this.
- Q3 (ANSWERED 2026-11-11, operator): off by default after US3, `--legacy-routes` for one release, then remove. `agents-inc dispatch` CLI stays for scripts and broker Workers.
- Q4 (ANSWERED 2026-11-11, operator): this machine uses the Codex CLI login only; no OpenAI API key. Consumers may want an API key, so the adapter interface must admit an optional API-key adapter per provider: off by default, key entered through the hidden prompt at install into the 0600 key store, never in argv, and labelled as a paid path the consumer opts into. It is a later slice, not slice 1 to 3, and this repository's own $0 rule is unchanged.
- Q5 (ANSWERED 2026-11-11, operator): probe only at `doctor --probe` and `models probe`, cached with a 7-day TTL; session start reads the cache.
- Resolved from code: tool calls for text-only models use the existing luna JSON text protocol (luna.ts `parseReply`, `catalog`), so no provider function-calling API is needed (FR-010).
- Resolved from code: P3 holds through the parent, as D69 already rules for luna; verification gates stay a parent duty (FR-015).
- Resolved from evidence: route collapse does not by itself fix exit 69; FR-019 measures the mod-spawn sandbox position.

## Out of Scope

- Paid API keys or paid slugs; Claude models as native agent types (Claude Code already serves them natively).
- Fixing #145 shared-cwd misattribution.
- Removing `agents-inc dispatch` or the broker.
- Provider-native function calling (later adapter optimisation).

## Grill rulings (operator, 2026-11-11)

- Term: a non-Claude model reached through the Agent tool is a **Guest agent** (CONTEXT.md). "Native type" in this spec means the same thing.
- Order: harden luna before any other provider. Bar: every stress case (tools, par, steps5, follow) passes 10 of 10, no step hangs, and one live talk test passes on the Mac. This replaces the 7 of 10 bar in SC-001 and SC-002 for luna. Supervisor note: 10 of 10 may be unreachable with a model that sometimes ignores instructions; report the measured rate if it stalls below 10.
- Delivery: one build with internal checkpoints. Nothing reaches the install until Codex (luna, sol, terra, astra), Gemini, Mistral and OpenRouter guest agents all exist. Luna parity is tested first inside the build.
- Weak models: a model that fails the tool-protocol probe is offered as a chat-only guest agent, labelled "no tools".
- Streaming (text as written, tool rows as they start): required, in the release after the first one. First release shows a "thinking" marker so a step never looks dead.
- Mid-step message: queued and shown as pending, delivered when the step ends.
- Builder: one opus builder per slice; the supervisor verifies; suites run in docker.
- Specs move to DomI only after the release publishes.
- Claude route: any Claude rung (haiku, sonnet, opus) goes through the native Agent tool with its normal tools and permissions. `agents-inc dispatch` is for non-Claude models only, until each becomes a guest agent. The relay is no longer offered for Claude models. Session-start hook text, the AGENTS.md block that install writes, and QUICKREF change to say so. Evidence: CHILmesh session 2026-11-11, a haiku scout through the relay had no web grant and read nothing (#112).

## Live evidence (Mac, 2026-11-11, Claude Code 2.1.322)

- Clicking a running luna row switches the primary view to its transcript. Returning to main works.
- Talk works but late: a message typed mid-step was delivered after the run's last step; luna resumed and answered with its model id.
- Three luna runs: one clean; one refused host tools ("read access only to root", 382k tokens, 1 tool use); one hung on a Codex step for about 300 s, then "unparsable reply".
- A finished guest agent drops out of the manager pane (FR-020 gap).
- The input box text is shared between the primary view and a guest agent view. Owner not yet determined (harness or mod).

