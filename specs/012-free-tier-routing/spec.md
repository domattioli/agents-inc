<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Free-Tier-Aware Routing

**Feature Branch**: `feat/012-free-tier-routing`
**Created**: 2026-09-23
**Status**: Draft
**Input**: Operator report that free-tier grunt models show almost no usage on the statusline token tracker, plus live probes run on 2026-09-23.

## Background (verified 2026-09-23)

- OpenRouter default model in the `oask` wrapper returns 404: "This model is unavailable for free". The default is hardcoded, not read from the model catalog.
- Two other OpenRouter free models return 429 (upstream rate limit). One returns 404 because the account's zero-data-retention (ZDR) setting excludes its only endpoint.
- Gemini default model returns 503 (high demand). The cheap tier works. The deep tier is rate-limited ("Please retry in 53.02554268s").
- Mistral works.
- The model catalog lists five OpenRouter models that are no longer on the live free list.
- The router places paid providers (Claude, Codex) ahead of free providers, so free providers are chosen only when both paid providers are unavailable. Free providers are also limited to two task types: extract and summarize.
- A backend health file with per-backend cooldowns exists. The governed job runner writes to it; the three standalone wrappers do not.
- A local usage database exists but does not enforce per-provider daily caps.
- Main-session dispatches (Agent tool, workerbee) do not consult the router.

## Clarifications

### Session 2026-09-23

Answered by the main session on operator instruction ("you are to answer the clarify questions").

- Q: Does free-first ordering apply always, or only in budget modality? → A: Only when budget modality is active (CLAUDE.md "Modality": budget opens free grunts for grunt slots). Ideal modality keeps today's order. Modality is read from an environment variable; default stays ideal.
- Q: Order among free providers when several are healthy? → A: Mistral, then Gemini (cheap tier), then OpenRouter. Matches the 2026-09-23 probe results and both second opinions (fable, astra).
- Q: Default Gemini tier for routed grunt calls? → A: cheap (gemini-flash-lite-latest). The default flash model returned 503.
- Q: Default daily caps before any probe? → A: Mistral 500, Gemini 200, OpenRouter 50 (replaced by the probed value when available). Operator-editable in the routing config.
- Q: Modality variable name? → A: `AGENTS_INC_MODALITY` (`budget` | `ideal`, default `ideal`).
- Q: Is a catalog entry with status `unprobed` eligible? → A: Yes, only for tasks in its `tasks_good` list (existing OpenRouter rule). `unavailable` is never eligible.
- Q: FR-014 content? → A: Proposed (operator to ratify): main-session Agent-tool dispatches do not consult the router, because the harness cannot intercept them. Main-session free-tier use goes through `agent.sh submit --backend <free>`, which already reports health; the decision entry records this and marks it `proposed`.
- Q: Is "classify" a grunt-tier task? → A: Yes. Add it to the task-to-tier map and to the free-allowed task list.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Free grunt calls stop failing on dead models (Priority: P1)

The operator (or a dispatching session) sends a grunt-tier prompt through a free wrapper without naming a model. The wrapper picks a model the catalog marks as currently available, and never a model known to be withdrawn.

**Why this priority**: Today the default OpenRouter call fails every time. This is the cheapest fix with the largest effect.

**Independent Test**: Mark a model unavailable in the catalog, call the wrapper with no model named, and confirm it picks a different, available model.

**Acceptance Scenarios**:

1. **Given** the catalog marks the old default unavailable, **When** the OpenRouter wrapper runs with no model named, **Then** it selects the first available free model from the catalog.
2. **Given** no free OpenRouter model is available, **When** the wrapper runs, **Then** it exits non-zero with a clear "no eligible free model" message and makes no network call.
3. **Given** the operator names a model explicitly, **When** the wrapper runs, **Then** it uses that model (existing spend guard still refuses non-free models).

---

### User Story 2 - Failures cool a provider down automatically (Priority: P1)

When any free wrapper gets a rate-limit, overload, withdrawn-model, or ZDR-exclusion response, the outcome is recorded so the next routing decision skips that provider or model for an appropriate time.

**Why this priority**: Without this, every caller retries the same failing provider.

**Independent Test**: Simulate each failure response and check the health record.

**Acceptance Scenarios**:

1. **Given** a 429 or 503 response, **When** the wrapper exits, **Then** the provider is put in cooldown, honoring any retry delay the provider stated.
2. **Given** a "unavailable for free" 404 or a ZDR exclusion, **When** the wrapper exits, **Then** that model is marked unavailable until the next catalog refresh.
3. **Given** a success, **When** the wrapper exits, **Then** the provider's failure streak resets.

---

### User Story 3 - The catalog stays current (Priority: P2)

The operator runs a refresh command that compares the catalog against the live OpenRouter free list and shows what would change. A second flag applies the change.

**Why this priority**: The catalog drifted silently for weeks; this prevents recurrence.

**Independent Test**: Run in dry-run mode against a recorded model list and check the diff output.

**Acceptance Scenarios**:

1. **Given** the live list lacks a catalog model, **When** refresh runs in dry-run, **Then** the model is listed as "would mark unavailable" and no file changes.
2. **Given** a new free model appears, **When** refresh applies, **Then** it is added as available but not approved for any task until a human marks which tasks it is good at.
3. **Given** the list endpoint is unreachable, **When** refresh runs, **Then** it exits non-zero and changes nothing.

---

### User Story 4 - Routing respects daily limits (Priority: P2)

Before a free provider is chosen, the router checks how many calls it has made today against a configured daily cap. A provider at its cap is skipped until the next day.

**Independent Test**: Seed the usage record at the cap and confirm the provider is skipped.

**Acceptance Scenarios**:

1. **Given** a provider has reached its daily cap, **When** the router builds a candidate chain, **Then** that provider is excluded.
2. **Given** OpenRouter reports the key's actual limits, **When** the limits probe runs, **Then** the stored cap reflects the reported value.

---

### User Story 5 - Free providers come first for eligible grunt work (Priority: P2)

For grunt-tier tasks of an allowed type (extract, summarize, classify) in an authorized workspace, the router lists healthy, under-cap free providers before paid providers. Paid providers remain the fallback.

**Independent Test**: Router unit test with all providers available and healthy returns a free provider first for an allowed task and a paid provider first for a disallowed task.

**Acceptance Scenarios**:

1. **Given** an allowed grunt task and a healthy free provider, **When** the router picks, **Then** a free provider is first.
2. **Given** all free providers are in cooldown or at cap, **When** the router picks, **Then** a paid grunt provider is first.
3. **Given** a coding, draft, or review task, **When** the router picks, **Then** ordering is unchanged from today.

---

### User Story 6 - Decision on main-session dispatch (Priority: P3)

A recorded decision states whether Agent-tool and workerbee dispatches must consult the router, and if not, how their free-tier use is governed.

**Independent Test**: The decision entry exists in the decisions log with rationale.

### Edge Cases

- Provider returns 429 without a retry delay: default cooldown applies.
- Health or usage file missing or corrupt: routing continues as if the provider is healthy and uncapped, and prints one warning.
- Clock rollover at midnight: daily counts reset by calendar day in UTC.
- Two callers write the health file at the same moment: last write wins, no crash, no corrupt file.
- Catalog entry that is not a text model (for example an audio model): refresh marks it unavailable for all text tasks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The OpenRouter wrapper MUST choose its default model from the catalog, selecting only models marked available, free, and approved for the requested task.
- **FR-002**: The catalog MUST mark the five stale OpenRouter entries unavailable: `minimax/minimax-m3:free`, `minimax/minimax-m2.7:free`, `google/lyria-3-pro-preview`, `google/lyria-3-clip-preview`, `openrouter/free`. `openrouter/auto:free` is a meta-router absent from the list by design and stays as-is.
- **FR-003**: All three standalone free wrappers MUST report each call outcome (success, 404-withdrawn, ZDR-excluded, 429, 503, other error) to the shared health record.
- **FR-004**: Cooldown after 429/503 MUST honor a provider-stated retry delay when present, else use exponential backoff starting at 60 seconds, capped at 1 hour.
- **FR-005**: A withdrawn-model or ZDR response MUST mark that model unavailable until the next catalog refresh.
- **FR-006**: A catalog refresh command MUST support dry-run (default) and apply modes, fetch only the public free-model list, and never spend credits.
- **FR-007**: New models added by refresh MUST have no approved tasks until a human sets them.
- **FR-008**: The system MUST keep a per-provider count of calls per UTC day and a configurable daily cap per provider.
- **FR-009**: A limits probe MUST read OpenRouter's reported key limits without making a generation call, and store them as the OpenRouter cap.
- **FR-010**: The router MUST exclude free providers that are in cooldown or at their daily cap.
- **FR-011**: When budget modality is active, for grunt-tier tasks of type extract, summarize, or classify in an authorized workspace, the router MUST list eligible free providers (order: Mistral, Gemini cheap, OpenRouter) before paid providers. In ideal modality, free providers keep their current fallback position.
- **FR-012**: For all other tasks and tiers, router ordering MUST be unchanged. The Gemini grunt model changing to the cheap tier is the one allowed substitution in existing chains.
- **FR-013**: Nothing in this feature may disable ZDR, select a non-free OpenRouter model, or route coding tasks to free providers.
- **FR-014**: A decision record MUST state whether main-session dispatches consult the router.
- **FR-016**: Default daily caps MUST be Mistral 500, Gemini 200, OpenRouter 50, editable in the routing config.
- **FR-015**: A missing or unreadable health/usage/catalog file MUST degrade to "healthy, uncapped" with one warning line, never a crash.

### Key Entities

- **Catalog entry**: model id, provider, tier, status (available/unavailable), tasks it is good at, tasks it is bad at.
- **Health record**: per backend or model, last outcome, failure streak, cooldown end time.
- **Usage record**: per call, day, provider, model, tokens.
- **Daily cap**: per provider, maximum calls per UTC day, with source (configured or probed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A no-model-named OpenRouter call never selects a model the catalog marks unavailable (0 of 20 test runs).
- **SC-002**: After any failure response, the next routing decision within the cooldown window skips that provider in 100% of tests.
- **SC-003**: Catalog refresh dry-run on a recorded model list lists all five known-stale entries and changes zero files.
- **SC-004**: For an allowed grunt task with healthy free providers, a free provider is first in 100% of router tests; for disallowed tasks the chain is identical to the pre-change chain.
- **SC-005**: Free-provider share of grunt-tier extract/summarize/classify calls observed by the usage tracker rises above zero within the first week of use (baseline: near zero).
- **SC-006**: The full existing test suite still passes.

## Assumptions

- Mistral and Gemini free tiers cost nothing on the operator's accounts. Not verified; the daily cap guards against surprise use.
- OpenRouter free limits are roughly 50 calls a day (1,000 with credit). Unverified; FR-009 replaces this with the probed value.
- Calendar day for caps is UTC.
- Standard library only; no new dependencies.
- The Executive/Supervisor ladder for this run: independent Opus Executive, Opus Supervisor, Sonnet/Haiku workers.

## Known Limitations and Follow-ups (Executive review, 2026-09-23)

- Mistral (`mistral-small-latest`) is `unavailable` in the catalog with extract and summarize in `tasks_bad`. In practice the free-first chain starts with Gemini, not Mistral. Re-probe the entry before relying on the Mistral-first order.
- The shape of the OpenRouter key-limits response is fixture-based and has not been checked against the live API.
- Wrappers use fixed `/tmp` paths (`/tmp/oask_response.json`, pre-existing, and `*_report_err.$$`). Concurrent runs can mix up the response bodies. Switch to `mktemp`.
- The health file has no lock. Concurrent reports can lose cooldown or counter updates, so caps can undercount. Add `fcntl.flock`.
- Catalog-refresh `--apply` entries use placeholder fields. Validate them against the config schema before the first real apply.
- `route.sh:32` sends the `code` class to Mistral. This predates this feature; Mistral is unavailable, so it is skipped at runtime.
