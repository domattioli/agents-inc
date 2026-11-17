<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-analyze repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Feature Specification: Free models through dispatch

**Feature Branch**: `037-free-models-via-dispatch`
**Created**: 2026-11-09
**Status**: Draft
**Input**: User description: "Route free models (gemini-3.8-flash, gemini-flash-lite-latest, ministral-3b-latest, codestral-latest, and the working OpenRouter :free slugs) through `agents-inc dispatch` instead of only the legacy agent.sh wrappers."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a cheap text task on a free model with a checked result (Priority: P1)

An operator or supervising session has a small text task (extract, summarize or classify) and wants a free model to do it. Today they must call a separate legacy wrapper by hand, and nothing checks the answer. They want the same `agents-inc dispatch` command they use for every other model, with the same run record, gates and exit codes.

**Why this priority**: This is the whole feature. Free capacity is only useful if it is reachable and checked the same way as paid capacity.

**Independent Test**: Dispatch one extract task to one free model with a deterministic gate on the reply. The run finishes green, writes the reply and a run record, and shows zero cost.

**Acceptance Scenarios**:

1. **Given** a free model, an allowed task kind, an explicit data classification of public or internal, and a gate on the reply text, **When** the operator dispatches it, **Then** the reply is saved, the gate runs on it, and the run ends green with cost 0.
2. **Given** the same dispatch with no gate, **When** it finishes, **Then** the run ends unverified, never green.
3. **Given** a gate that fails on the reply, **When** the run finishes, **Then** it ends red with a gate-failed reason and exit 1.

---

### User Story 2 - Refuse unsafe or out-of-scope free runs before any provider call (Priority: P1)

Free providers may log prompts and have no tools. The operator needs dispatch to refuse, before sending anything, every request that does not fit: a task kind that is not allowed, a missing or confidential data classification without workspace authorization, tool grants, worker fan-out, or resume.

**Why this priority**: Data leaves the machine. A refusal after sending is too late.

**Independent Test**: Dispatch each disallowed request. Each ends with a named refusal reason and no provider call is made.

**Acceptance Scenarios**:

1. **Given** a task kind outside the allowed list, **When** dispatched, **Then** it is refused with a task reason.
2. **Given** no explicit classification written by the author, **When** dispatched, **Then** it is refused; a default classification does not count.
3. **Given** a confidential classification and no workspace authorization, **When** dispatched, **Then** it is refused; with authorization it proceeds.
4. **Given** tool grants, fan-out above zero, or a resume request, **When** dispatched, **Then** it is refused.

---

### User Story 3 - Quota, outage and wrapper failures read clearly (Priority: P2)

When a free provider is at its daily cap, in cooldown, rate limited, unreachable, missing a key, or returns a redacted reply, the operator sees a distinct outcome and exit code, not a generic failure.

**Why this priority**: Free tiers fail often. Distinct outcomes let the supervisor retry, wait or switch.

**Independent Test**: Simulate each failure. Each yields its own reason and exit code, and a quota pause counts as one failed attempt.

**Acceptance Scenarios**:

1. **Given** a provider at cap or in cooldown, **When** dispatched, **Then** nothing is sent and the run ends quota-paused.
2. **Given** a rate-limit reply, **When** the run finishes, **Then** it ends quota-paused.
3. **Given** a missing key, a redacted reply, or a wrapper refusal, **When** the run finishes, **Then** each ends red with its own reason.
4. **Given** an unreachable provider host from a sandboxed caller, **When** dispatched, **Then** the run ends blocked and names the host to allow.

---

### User Story 4 - Catalog matches reality (Priority: P3)

The model catalog lists the free models that were probed working on 2026-11-09 and no dead ones, so routing never picks a model that returns an error.

**Why this priority**: Wrong catalog entries make free routing fail for reasons the operator cannot see.

**Independent Test**: Compare the catalog with the probe record. Every probed-working model is listed and available; no withdrawn model is listed.

**Acceptance Scenarios**:

1. **Given** the probe record, **When** the catalog is read, **Then** gemini-3.8-flash and codestral-latest are present and ministral-3b-latest is available.
2. **Given** a model whose catalog entry lists the task as bad, **When** dispatched, **Then** it is refused.

### Edge Cases

- A free model returns an empty or truncated reply: the gate decides; with no gate the run is unverified.
- A gate writes into the repository: the run ends red with a gate-wrote reason.
- The reply contains a secret-shaped string: the existing screens apply to the saved reply.
- A slug is not in the allowed free map, including deep-tier free models and paid OpenRouter slugs: dispatch treats it as unsupported, not as free.
- A free model is named as a worker, reviewer or lead: rejected in v1.
- Input text larger than the model's limit: refused, never silently cut.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Dispatch MUST accept the allowed free models by slug: gemini-3.8-flash, gemini-flash-lite-latest, ministral-3b-latest, codestral-latest, and each OpenRouter `:free` slug that was probed working on 2026-11-09. Any other slug MUST remain unsupported.
- **FR-002**: Free runs MUST use the existing wrappers unchanged. Dispatch MUST pass the prompt on standard input, never in arguments, and MUST NOT add a new HTTP client.
- **FR-003**: A new optional slot, the task kind, MUST be required for free runs and MUST be limited to the task kinds listed as allowed for optional providers in the routing file, read from that file at run time.
- **FR-004**: A free run MUST be refused unless the author wrote an explicit data classification. A confidential classification MUST also require workspace authorization for optional providers. Public and internal are allowed.
- **FR-005**: A free run MUST be refused when it asks for fan-out above zero, tool grants or permission modes beyond default or plan, or resume.
- **FR-006**: Input files MAY be supplied as a new optional slot. Dispatch MUST read them, and MUST refuse a file outside the working directory, a symlink, a non-text file, a credential-shaped file or content, or input over the model's size limit. The run record MUST list each file with its size and hash.
- **FR-007**: Gates MUST be able to judge the saved reply through a report-path token in the gate command. The token MUST be substituted only after the existing gate safety screens.
- **FR-008**: A free run with no gate MUST end unverified and exit 0. It MUST NOT end green. A report-format miss MUST stay advisory when the gates pass.
- **FR-009**: Before any provider call, dispatch itself MUST check the daily cap and the model cooldown with the router's existing rules; the wrappers do not check them. A hit MUST end quota-paused with exit 75 and send nothing.
- **FR-010**: Wrapper results MUST map as follows: success is normal; a redacted reply is red `redacted-reply`; a missing key is red `provider-key-missing`; a wrapper refusal is red `wrapper-refused`; a rate-limit or quota reply is quota-paused with exit 75; an unreachable host is blocked with exit 69; any other failure is red `rc-nonzero`. Rate-limit, timeout and unreachable arrive as exit 1 from the wrappers, so dispatch MUST tell them apart from the error text; a wrapper refusal covers the governance, spend-guard and no-healthy-model causes.
- **FR-011**: A sandboxed caller MUST be allowed to proceed only when the provider host is reachable; otherwise the run MUST end blocked and name the host.
- **FR-012**: The run record MUST include the provider, the wrapper path and its hash, token usage when reported, cost 0, and zero workers spawned.
- **FR-013**: Free models MUST NOT be accepted as workers, leads or reviewers by the broker or the lead roster in v1.
- **FR-014**: The model catalog MUST be refreshed to the 2026-11-09 probe: add gemini-3.8-flash and codestral-latest, mark ministral-3b-latest available, use the full `nvidia/` slugs for the OpenRouter models, and record the probe date. A catalog entry that lists the task as bad MUST cause a refusal.
- **FR-015**: A decisions entry MUST record the amendment that dispatch is a governed caller of the legacy wrappers (D16) and that the allowed-slug map plus the free-only guard holds the model-pinning rule (D17), and MUST state the data rule for public and internal classifications.
- **FR-016**: Existing dispatch behavior for Codex and Claude models MUST be unchanged.

### Key Entities

- **Free model entry**: slug, provider, wrapper and tier, provider host, input size limit.
- **Task kind**: one of the allowed optional-provider task kinds.
- **Free run record**: provider, wrapper hash, input list, usage, cost 0, outcome and reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the 10 probed-working free models can be dispatched with one command and ends green with a passing gate (verified by one stubbed run per model and one live smoke per provider when keys exist).
- **SC-002**: 100% of the disallowed requests in User Story 2 end in a named refusal with no provider call made (verified by a test per refusal).
- **SC-003**: Each failure mode in FR-010 produces a distinct reason and exit code (verified by one test per mapping).
- **SC-004**: No free run ends green without a passing deterministic gate.
- **SC-005**: Zero paid-model or deep-tier free slugs are accepted as free (verified by a test over the rejected list).
- **SC-006**: The full test suite and the docker stress check pass with no change to existing Codex and Claude dispatch results.

## Assumptions

- Free providers are Gemini, Mistral and OpenRouter. Their keys stay in the wrappers' own key files; dispatch never reads or prints keys.
- Optional-provider task kinds stay extract, summarize and classify. Widening them is a separate ruling.
- The allowed OpenRouter slugs are the six probed working on 2026-11-09 (full `nvidia/` names), plus the other probed ones listed in the catalog.
- Free models run without tools, so every input must arrive as text and every check must run on the reply.
- A free model's output is never self-accepted. The supervisor still reviews it with a different model before acting.
- Deep-tier free models (gemini-3.1-pro-preview, mistral-large-latest) are out: they are not usable on the free tier today.
- Free workers in the broker, and moving API keys out of curl arguments in the wrappers, are follow-up work.
- A next free decision number is assumed to be D75; confirm D73 is not reserved.
