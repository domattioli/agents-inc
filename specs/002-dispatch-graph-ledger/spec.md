<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Dispatch Graph Ledger

**Feature Branch**: `002-dispatch-graph-ledger`
**Created**: 2026-09-05
**Status**: Draft
**Input**: User description: "Dispatch graph ledger: every delegated job (worker, reviewer, correction, doctor probe) is recorded as a node in a per-workspace ledger with model, tier, task, provider, parent_id, edge type, status, seconds, subscription calls. Graph derivable from receipts, linted by rules, exportable as JSON and Mermaid. Emitted by the runner as a side effect, never LLM-planned."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audit who did what (Priority: P1)

After a brief is produced, the operator asks "which models touched this, in what order, and who checked whom?" and gets an exact answer from a file, not from memory.

**Why this priority**: Without it every fan-out is unauditable and the cost metric (D5) cannot be attributed to nodes.

**Independent Test**: Run one brief with a worker and a reviewer; the ledger contains exactly two nodes with one `reviews` edge from reviewer to worker, and the export renders both.

**Acceptance Scenarios**:

1. **Given** an empty workspace, **When** one brief runs with worker + reviewer, **Then** the ledger holds 2 nodes, 1 edge, and each node carries model, tier, task, provider, status, seconds.
2. **Given** a brief with one correction retry, **When** it finishes, **Then** the ledger shows the retry node with a `corrects` edge to the original worker node.
3. **Given** a doctor preflight, **When** it runs, **Then** each probed provider is a node with edge type `probes` and no parent.

---

### User Story 2 - Catch a bad hierarchy before it costs (Priority: P2)

The operator runs a lint over the ledger and is told, deterministically, whether any rule was broken: depth over one, reviewer from the same vendor as its worker, a frontier node without a stated gate reason.

**Why this priority**: These are the exact failure modes that wasted spend earlier today (same-vendor review, frontier used routinely).

**Independent Test**: Feed a hand-built ledger with one violation of each kind; lint reports exactly three findings with node ids.

**Acceptance Scenarios**:

1. **Given** a node whose parent already has a parent, **When** lint runs, **Then** a `depth` finding names that node.
2. **Given** a reviewer node with the same provider as the node it reviews, **When** lint runs, **Then** a `same_vendor_review` finding names both.
3. **Given** a frontier-tier node with no `gate_reason`, **When** lint runs, **Then** a `frontier_without_gate` finding names it.
4. **Given** a clean ledger, **When** lint runs, **Then** zero findings.

---

### User Story 3 - See and share the shape (Priority: P3)

The operator exports the ledger as a diagram and a machine-readable file to paste into a decision record or hand to another session.

**Independent Test**: Export a two-node ledger; the diagram text lists both nodes and one arrow; the JSON round-trips back to the same ledger.

**Acceptance Scenarios**:

1. **Given** any ledger, **When** exported as a diagram, **Then** every node appears once and every edge once, labeled by edge type.
2. **Given** any ledger, **When** exported as JSON and re-imported, **Then** the result is identical.
3. **Given** a ledger, **When** cost rollup is requested, **Then** each root node reports the summed subscription calls and seconds of its subtree.

### Edge Cases

- A job that never returns (crash mid-run) leaves a node in a non-terminal status; the ledger must record it, never drop it.
- Two briefs in the same workspace must not interleave nodes; each run has its own run id.
- A node written twice with the same id must not duplicate (idempotent append).
- Ledger file corrupt or missing: reading yields an empty ledger plus a warning, never a crash of the brief itself.
- Recording must never block or fail a brief; ledger write failure is logged in the receipt.

## Clarifications

### Session 2026-09-05
- Q: Where does a node's status come from? → A: Own copy in the graph ledger, eventually consistent. After MVP the graph ledger replaces the runner's job ledger entirely (operator decision).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every delegated job (worker, reviewer, correction, doctor probe) MUST be recorded as one node with: id, run id, model, tier, task, provider, parent id (nullable), edge type, status, seconds, subscription calls, gate reason (nullable), timestamp.
- **FR-002**: Edge type MUST be one of `depends-on`, `reviews`, `corrects`, `probes`.
- **FR-003**: Recording MUST be a side effect of running the job; no model call may be made to construct the graph.
- **FR-004**: The ledger MUST be per workspace and append-only; appends MUST be idempotent by node id.
- **FR-005**: Lint MUST report: depth greater than one; reviewer with same provider as reviewed node; frontier-tier node without gate reason. Each finding names node ids and rule.
- **FR-006**: Export MUST produce a machine-readable form that round-trips and a diagram form listing every node once and every edge once.
- **FR-007**: Cost rollup MUST sum subscription calls and seconds per subtree from each root.
- **FR-008**: Ledger failure MUST NOT fail or block the brief; the brief receipt records the failure.
- **FR-009**: The existing job ledger in the codex-bridge runner MUST NOT be duplicated as a second authority for the same job; the graph ledger records dispatch relationships, the runner records execution state. The graph ledger carries its own status copy (recorded at dispatch and at return), accepted as eventually consistent with the runner.

### Key Entities

- **Node**: one delegated job; identity = node id; attributes above.
- **Edge**: directed relation child → parent typed by edge type; implied by parent id + edge type on the child. `depends-on` edge type reserved for future multi-worker decomposition; not emitted in MVP.
- **Run**: one top-level brief or preflight; groups nodes; roots have no parent.
- **Finding**: lint result: rule name, node ids, message.

## Success Criteria *(mandatory)*

- **SC-001**: For 100% of briefs run through the pipeline, the ledger contains every model invocation made (verified by comparing invocation count to node count in tests).
- **SC-002**: Lint over a hand-built ledger with one violation per rule reports exactly those violations, zero false positives, in under one second.
- **SC-003**: The operator can answer "which models touched this brief and who reviewed whom" from the export alone, without reading logs.
- **SC-004**: Ledger write failure never changes brief status; verified by a fault-injected test.

## Assumptions

- One ledger file per workspace under the existing per-workspace state directory.
- Subscription calls per node = 1 (CLI invocation); optional HTTP providers out of MVP scope.
- Gate reason is a short free-text string supplied by the caller when a frontier tier is chosen.
- Mermaid is the diagram form; JSON the machine form.
