<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Governance Slice — Minimal Policy Enforcement

**Feature Branch**: `003-governance-slice`  
**Created**: 2026-09-05  
**Status**: Contract  
**Input**: Operator objective (CEO-BRIEF.md) + ASSESSMENT.md §3 proposed changes

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Registry and Edge Validation (Priority: P1)

The operator loads a versioned governance graph and asks "is this supervisor allowed to delegate to this worker?" The system consults the registry and returns a definitive yes/no without calling any model or invoking any external service.

**Why this priority**: Without deterministic policy evaluation, there is no boundary between user intent (prompt) and enforced rules.

**Independent Test**: Load a governance.json with one supervisor, one worker, one allowed edge; ask for edge decision; expect ALLOWED. Load same graph, ask for non-existent edge; expect DENIED. Invocation takes <100ms, no model calls.

**Acceptance Scenarios**:

1. **Given** a governance.json with agents A, B and an allowed edge A→B, **When** asked "can A delegate to B?", **Then** return {allowed: true, decision_id: UUID, checked_rules: ["edge_exists", "target_registered", "enabled"]}
2. **Given** the same graph, **When** asked "can A delegate to C?", **Then** return {allowed: false, decision_id: UUID, reason: "target not registered", checked_rules: ["target_registered"]}
3. **Given** a disabled edge A→B in governance.json, **When** asked to delegate, **Then** return {allowed: false, reason: "edge disabled until 2026-10-01", checked_rules: ["enabled"]}

---

### User Story 2 — Deny Forbidden Operations (Priority: P1)

The operator requests a worker run with an unsupported capability (e.g., deploy, delete, send_email, grant_permission). The gateway rejects it with a reason before any dispatch, returning a denial decision with the capability name and policy rule.

**Why this priority**: Unsupported capabilities are the highest-risk class; failing closed is non-negotiable.

**Independent Test**: Construct a request with operation='deploy'; run through gateway; expect immediate DENIED with reason mentioning 'deploy capability not supported'.

**Acceptance Scenarios**:

1. **Given** an enabled gateway with WORKERBEES_GOVERNANCE=enforce, **When** a request specifies operation='deploy', **Then** deny with {allowed: false, reason: "deploy operation not in supported set", checked_rules: ["operation_permitted"]}
2. **Given** the same setup, **When** operation='extract' (supported), **Then** proceed to edge check.
3. **Given** a request with operation='grant_permission', **When** evaluated, **Then** deny with same structure.

---

### User Story 3 — Inspect Both Allow and Deny (Priority: P1)

After each decision (allow or deny), the operator can inspect the complete audit record: sender, recipient, operation, checked rules, policy version, decision reason, timestamps, no secrets.

**Why this priority**: Provenance tracing determines whether a deployment succeeded or failed due to policy, not accident.

**Independent Test**: Run one allowed delegation and one denied delegation; query control database for both decision records; each has decision_id, sender, operation, allowed, reason_code, policy_version, checked_rules, no raw prompts or stderr.

**Acceptance Scenarios**:

1. **Given** a completed allowed worker invocation, **When** queried from control.decisions, **Then** record contains {decision_id, sender_id, recipient_id, operation, allowed: true, policy_version, created_at, checked_rules: list}
2. **Given** a denied request, **When** queried, **Then** record contains the deny reason and which rule triggered, verbatim but secret-free.
3. **Given** both records, **When** exported, **Then** the operator can construct a timeline from timestamps without reading logs.

---

## Clarifications

### Session 2026-09-05

- Q: Does the governance graph define ALL agents or just the controlled ones? → A: Registry contains only known, versioned agents; unknown identities denied.
- Q: Can an operator override a policy decision in this slice? → A: No; override is a later approval subsystem. This slice returns the computed decision only.
- Q: What if the governance.json file is malformed? → A: Reject at load time with a precise error; never fall back to off mode silently.
- Q: Does token budget enforcement happen in this slice? → A: No; budget metadata is recorded but not enforced. First supported slice uses explicit "unsupported" or null token budget.
- Q: How many policies can be evaluated? → A: Minimal set: edge, operation, classification, depth, expiry. No approval, no cost-optimized routing, no complex Casbin/Cedar rules in this slice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Registry MUST load versioned JSON config at startup; agents, capabilities, relationships, immutable snapshot with effective dates and version hash.
- **FR-002**: Edge query MUST return {allowed, decision_id, reason_code, reason, policy_version, checked_rules} deterministically in <100ms, no external calls.
- **FR-003**: Policy evaluation MUST check in order: registered sender, registered recipient, edge exists, operation permitted, classification within clearance, lineage depth, expiry.
- **FR-004**: Unsupported capabilities (deploy, delete, send, grant, tools, web, etc.) MUST be explicitly denied via "operation_not_supported" reason code.
- **FR-005**: Decision record MUST be persisted atomically before dispatch; deny persists the same as allow.
- **FR-006**: Gateway MUST authenticate caller context (trusted local only, no remote claims); sender identity derived from host context, not message.
- **FR-007**: All decision records MUST exclude raw prompts, model output, and secret values; only decision metadata and rule IDs.
- **FR-008**: Feature flag WORKERBEES_GOVERNANCE MUST be one of {off, shadow, enforce}; defaults off; explicitly rejects unknown values at startup.

### Key Entities

- **Agent**: registered identity with name, version, owner, provider/runtime, capabilities, trust level, data clearance, enabled/expiry dates.
- **Capability**: explicit operation name (e.g., research.summarize, code.write) with risk level, delegable?, approval?, idempotent?.
- **Relationship**: source agent, target agent, relationship type (delegates_to, submits_to, etc.), allowed capabilities, enabled/expiry, approval required.
- **Registry**: immutable snapshot of agents, capabilities, relationships at one version, with sha256 hash and effective date.
- **Envelope**: typed message with sender, recipient, operation, payload, classification, created/expires, security context.
- **Decision**: allowed/denied boolean, decision_id, reason_code, reason, policy_version, checked_rules, timestamps, no audit data.
- **Control**: SQLite transactions table storing decisions (PK: decision_id), one row per decision, indexed by sender/recipient/operation for audit.

## Success Criteria *(mandatory)*

- **SC-001**: Load and query a 100-agent registry in <50ms; respond to 1000 edge queries per second deterministically.
- **SC-002**: Deny all six unsupported capability operations (deploy, delete, send, grant, tools, web) without model invocation.
- **SC-003**: Operator can reconstruct sender→recipient→operation→allowed for any decision from database query with no log parsing.
- **SC-004**: Feature flag defaults off; setting WORKERBEES_GOVERNANCE=enforce enables strict evaluation; any other value fails startup.
- **SC-005**: All denial records persist and survive process restart; no silent failures or decisions lost to cache.

## Assumptions

- One versioned governance.json per workspace under per-workspace state directory.
- SQLite control.db under same directory; one sessions table (reserved for future lease), one decisions table (populated immediately on policy evaluation).
- Trusted local supervisor context only; no remote agent claims, no delegation tokens, no A2A.
- Capabilities are operation names, not granular permissions; "deploy" is all-or-nothing disabled.
- Policy version is a monotonic integer; config file hash is recorded alongside for auditability.
- No OPA, Cedar, Casbin, or graph database in this slice; pure Python evaluation with stdlib only.

## Unsupported / Explicitly Denied in Spec-003

- **Capabilities disabled**: deploy, delete, send_email, grant_permission, request_tools, web_access (any request→403 DENIED).
- **Remote agents**: A2A, MCP client for remote dispatch, tool invocations, HTTP-based delegation.
- **Token budgets**: Hard token caps and enforcement (budget fields recorded; requests for finite token limit explicitly rejected).
- **Complex policies**: Casbin rules, OPA Rego, cost-optimized routing, fuzzy matching.
- **Approval gates**: Pending approval, no self-approval rules (reserved for later subsystem).
- **Deployment/migration**: No producer/consumer contract, no synchronization of governance files across machines.

## Runtime Architecture

8 Python modules under `workerbees/`, stdlib only, strict line caps:

| Module | Cap | Responsibility |
|---|---:|---|
| `registry.py` new | 180 lines | Load/parse governance.json; validate references; Agent, Capability, Relationship dicts; snapshot version hash. |
| `envelope.py` new | 220 lines | Envelope, Decision, Artifact types; strict field validation; canonical hashes; operation-specific schema stubs. |
| `policy.py` extend | 240 lines | Pure evaluate(context, envelope, registry) → Decision; no I/O; reason codes; checked_rules list; D7/D9 classification mapping. |
| `control.py` new | 290 lines | SQLite transactions: decisions table (PK: decision_id), schema validation, atomic writes, audit queries, no copy of provider state. |
| `gateway.py` new | 290 lines | Authenticate context, validate envelope, resolve parties, check edge, evaluate policy, reserve, invoke adapter, emit audit, release. |
| `pipeline.py` adapt | 280 lines | Extract existing logic; remove inline dispatch/ledger; call gateway with frozen run context; preserve correction/acceptance contracts. |
| `reviewer.py` adapt | 120 lines | Preserve prompt/verdict; explicit capability annotation; call gateway; enforce vendor difference. |
| `doctor.py` adapt | 140 lines | Registered synthetic probe operation; gateway invocation; cache diagnostics unchanged externally. |

Config files (separate from 8-module count):
- `workerbees/governance.json`: agents, capabilities, relationships, versioned, with effective_date and expiry.
- `workerbees/protocols.json`: operation schemas (request/response shapes), bounded by operation name.

Existing `workerbees/routing.json` unchanged (model ID table).

Database (separate):
- `workerbees/control.db`: SQLite with decisions table (decision_id PK, sender_id, recipient_id, operation, allowed, reason_code, reason, policy_version, checked_rules JSON, created_at, expires_at).

## Configuration Format

All JSON, no YAML; startup rejects malformed files.

### governance.json structure

```json
{
  "version": 1,
  "effective_date": "2026-09-05T00:00:00Z",
  "policy_version": 1,
  "policy_hash": "<sha256 of this file>",
  "agents": {
    "supervisor_1": {
      "id": "supervisor_1",
      "name": "CLI Supervisor",
      "version": "1.0",
      "owner": "system",
      "provider": "local",
      "capabilities": ["task.decompose"],
      "trust_level": "high",
      "data_clearance": "confidential",
      "max_delegation_depth": 1,
      "enabled": true,
      "enabled_until": null
    }
  },
  "capabilities": {
    "task.extract": {
      "id": "task.extract",
      "name": "Extract and summarize",
      "risk_level": "low",
      "delegable": true,
      "requires_approval": false,
      "idempotent": true,
      "prohibited_in": ["deploy", "delete", "send", "grant"]
    }
  },
  "relationships": [
    {
      "source_id": "supervisor_1",
      "target_id": "worker_a",
      "type": "delegates_to",
      "allowed_capabilities": ["task.extract"],
      "enabled": true,
      "enabled_until": "2026-10-31T23:59:59Z"
    }
  ]
}
```

### Decision record (in control.decisions)

```json
{
  "decision_id": "uuid",
  "sender_id": "supervisor_1",
  "recipient_id": "worker_a",
  "operation": "task.extract",
  "allowed": true,
  "reason_code": "edge_allows_operation",
  "reason": "edge supervisor_1→worker_a allows task.extract",
  "policy_version": 1,
  "checked_rules": ["sender_registered", "recipient_registered", "edge_exists", "operation_permitted", "enabled"],
  "created_at": "2026-09-05T12:34:56Z",
  "expires_at": "2026-10-31T23:59:59Z"
}
```

## Feature Flag

```python
WORKERBEES_GOVERNANCE = os.getenv("WORKERBEES_GOVERNANCE", "off")
if WORKERBEES_GOVERNANCE not in ("off", "shadow", "enforce"):
    raise ValueError(f"Invalid WORKERBEES_GOVERNANCE: {WORKERBEES_GOVERNANCE}")

# Behavior:
# - "off": preserve existing signatures, no gate enforcement
# - "shadow": evaluate and record decisions; existing execution unchanged; label as shadow
# - "enforce": freeze run context, require gateway pass before dispatch
```

## Phase & Sequencing

1. **Spec review** (this document): operator confirms scope, unsupported capabilities list, 8-module plan.
2. **Registry + envelope**: load, validate, store snapshots.
3. **Policy evaluation**: pure function, minimal rules.
4. **Control + gateway**: atomic decision persist, invoke adapter, audit.
5. **Pipeline/reviewer/doctor integration**: call gateway, preserve acceptance.
6. **Testing**: allow/deny paths, registry loads, config errors, audit trails.
7. **Docs + rollout**: feature flag defaults off; operator owns cutover.

## Testing Strategy

- **Unit**: registry load/validate, policy rules, decision format, control transactions.
- **Integration**: gateway→runner chain with injected transport; allow + deny paths.
- **Negative**: malformed config, missing agents, disabled edges, unsupported operations, auth failures.
- **Audit**: decision records inspectable, no secrets, timestamps accurate.
- **Flag matrix**: off, shadow, enforce modes with same test suite; flag=off preserves existing behavior exactly.

## Open Questions for Operator

1. Should governance.json be auto-reloaded on file change, or requires restart?
2. Can the operator query control.decisions via CLI, or only via embedded Python API?
3. When WORKERBEES_GOVERNANCE=shadow, should denial still block execution (shadow observability only) or allow it?
