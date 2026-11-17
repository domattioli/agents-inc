<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Data Model: Dispatch Graph Ledger

## Node

One delegated job (worker, reviewer, correction, doctor probe). Identity = `id`.

| Field | Type | Notes |
|---|---|---|
| `id` | str | Unique per node; caller-supplied (e.g. `uuid4().hex`); append key for idempotency (FR-004) |
| `run_id` | str | Groups nodes from one brief or one doctor preflight (FR-001); prevents interleaving across concurrent briefs |
| `model` | str | e.g. `haiku`, `gpt-5.6-luna` |
| `tier` | str | `cheap` \| `mid` \| `frontier` |
| `task` | str | e.g. `extract`, `review`, `probe` |
| `provider` | str | e.g. `claude`, `codex` |
| `parent_id` | str \| null | Null for root nodes (worker, doctor probe) |
| `edge_type` | str \| null | One of `reviews`, `corrects`, `probes` (MVP); `depends-on` reserved for future multi-worker decomposition; null only when `parent_id` is null |
| `status` | str | Ledger's own copy: `dispatched` at record time, then `returned`/`needs-review`/`verified`/`paused`/`blocked`/etc. at return time (eventually consistent with the runner, FR-009) |
| `seconds` | float \| null | Null until return recorded; computed via wall-clock (time.monotonic) around the job call in the hook at the call site |
| `subscription_calls` | int \| null | Null until return recorded; 1 per CLI invocation (per spec Assumptions) |
| `gate_reason` | str \| null | Required by lint when `tier == "frontier"`; free text supplied by the caller |
| `timestamp` | str | ISO-8601 UTC, set at each append (dispatch and return each get their own line/timestamp) |

Two lines may exist on disk for the same `id` (one from `record_dispatch`, one from `record_return`); `load()` collapses them to one current node keyed by `id`, later timestamp wins. This is the "own copy... eventually consistent" mechanism named in the spec's Clarifications. `record_return` with no matching dispatch line still creates a node; dispatch-only fields (model, tier, task, provider, parent_id, edge_type) are null.

## Edge

Not a separate stored record — implied by a node's `parent_id` + `edge_type` (per spec's Key Entities: "implied by parent id + edge type on the child"). Directed child → parent. `edge_type` MUST be one of `depends-on`, `reviews`, `corrects`, `probes` (FR-002).

## Run

Groups nodes from one top-level brief or one doctor preflight. Not a separately stored record; derived as `{n.run_id for n in nodes}`. Root nodes are those with `parent_id is None`.

## Finding

Lint result.

| Field | Type | Notes |
|---|---|---|
| `rule` | str | `depth` \| `same_vendor_review` \| `frontier_without_gate` |
| `node_ids` | list[str] | The node(s) that triggered the finding |
| `message` | str | Human-readable explanation |

### Lint rules (FR-005)

1. **`depth`**: a node whose parent already has a non-null `parent_id` (depth > 1 from any root). Reports the deep node's id.
2. **`same_vendor_review`**: a node with `edge_type == "reviews"` whose `provider` equals its parent node's `provider`. Reports both node ids.
3. **`frontier_without_gate`**: a node with `tier == "frontier"` and `gate_reason` empty (None or gate_reason.strip() == ''). Reports that node's id.

Zero findings on a clean ledger (Acceptance Scenario 2.4); exactly one finding per seeded violation, no false positives (SC-002), computed in-memory over the loaded (deduped) node set — no model calls, deterministic, expected well under 1 second for realistic ledger sizes.

## Export

- **JSON**: `{"nodes": [ {..every field above.. } ]}` — round-trips exactly (`from_json(to_json(l)) == l`), satisfying FR-006 and Acceptance Scenario 3.2.
- **Mermaid**: `graph TD` (or similar) with one line per node (`id[task/model]`) and one line per edge (`child -->|edge_type| parent`), each node and edge appearing exactly once (FR-006, Acceptance Scenario 3.1).

## Cost Rollup (FR-007)

For each root node (`parent_id is None`), sum `subscription_calls` and `seconds` over its full subtree (itself + all descendants reachable by following `parent_id` edges). Returned as `{root_id: {"calls": int, "seconds": float}}`.

## MVP Edge Types

Test task: Assert that only `reviews`, `corrects`, `probes` edge types are emitted by MVP hooks; `depends-on` does not appear in ledger records during MVP deployment.
