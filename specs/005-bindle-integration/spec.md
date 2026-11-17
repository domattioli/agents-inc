<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Bindle Integration Decision

> **SUPERSEDED-IN-PART — 2026-09-06 (operator direction).** Amended, not retracted: the reasoning below (ledger owns job ownership/continuity; no duplicate authority) still holds and remains binding. What changed: the operator ruled Bindle is adopted as a **sibling** system, not a replacement, so the blanket "do not integrate" verdict in §Decision and FR-001 no longer governs. Bindle identity is also now resolved (deislabs/Fermyon Bindle, content-addressed aggregate object storage) — see [`specs/006-bindle-sibling-integration/spec.md`](../006-bindle-sibling-integration/spec.md), which governs scope from this date.

**Feature Branch**: `005-bindle-integration`  
**Created**: 2026-09-06  
**Status**: Evaluated — not adopted  
**Input**: Re-evaluate the prior Bindle decision against the current ledger; write a durable decision record.

## Decision

Do not integrate Bindle. Retain the local dispatch-graph ledger and projectmem split.

## Identification

Repository context identifies `bindle` only as a coordination tool whose relevant part was a job ledger and whose excluded parts were a Git/branch/Obsidian bridge. It is **not evidenced as Fermyon Bindle**: Fermyon describes Bindle as an aggregate object-storage/deployment system and has deprecated it in favor of OCI distribution ([Fermyon deployment concepts](https://developer.fermyon.com/cloud/deployment-concepts)). This repository describes no WASM artifacts, packages, registry, or deployment use, and specifically attributes a Git/Obsidian bridge to this tool. No repository source URL, dependency, manifest, prior code, or installed `bindle` CLI identifies the upstream project. Do not infer an upstream package from this name alone.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume a delegated job without Bindle (Priority: P1)

The operator can recover ownership, state, lineage, and usage from local state after interruption.

**Independent Test**: Dispatch then return one node; reload from SQLite and confirm its run, route, state, parent/edge, and usage are available.

**Acceptance Scenarios**:

1. **Given** a dispatch, **When** it is recorded, **Then** the local ledger records its id, run, model, tier, task, provider, parent, edge, state, gate reason, and timestamp.
2. **Given** a returned job, **When** it is recorded, **Then** the SQLite event stream records terminal status and usage.
3. **Given** a restart, **When** JSONL is absent or SQLite mode is selected, **Then** the ledger reconstructs nodes, lineage, status, and usage from SQLite.

## Evidence

- The prior decision says “REIMPLEMENT-MINIMAL” for the coordination ledger, excludes the Git/branch/Obsidian bridge, and names a local recovery journal as fallback: [PLAN-MVP §3](../../docs/PLAN-MVP.md#L72-L85). [HANDOFF](../../docs/HANDOFF.md#L68-L74) repeats it.
- Current code implements the retained role: append-only, per-workspace JSONL/SQLite state; normalized SQLite is available by default dual-write; writes are idempotent and non-blocking: [ledger header](../../workerbees/ledger.py#L1-L19), [dispatch](../../workerbees/ledger.py#L70-L115), [return](../../workerbees/ledger.py#L225-L300).
- It reloads SQLite run/route, lineage, latest status, and usage after restart: [SQLite load](../../workerbees/ledger.py#L377-L463). It also supplies ownership/continuity checks and graph exports: [lint](../../workerbees/ledger.py#L466-L584), [exports and rollup](../../workerbees/ledger.py#L587-L697).
- The plan explicitly assigns execution to the SQLite job ledger and semantic memory to projectmem; a Bindle import would create duplicate authority: [PLAN-MVP §3](../../docs/PLAN-MVP.md#L80-L85).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: No Bindle dependency, CLI, registry, artifact format, Git/branch bridge, or Obsidian bridge is introduced for current MVP execution.
- **FR-002**: `workerbees/ledger.py` remains the authority for dispatch execution ownership/state/lineage; projectmem remains the authority for semantic memory.
- **FR-003**: Reopen this decision only with a concrete missing requirement that cannot be met by the ledger/projectmem ownership split, plus an identified upstream Bindle source and a migration/no-duplicate-authority design.

### Key Entities

- **Coordination ledger**: local JSONL/SQLite dispatch graph and execution state.
- **Semantic memory**: projectmem checkpoint/fact state; not a ledger duplicate.
- **Bindle**: unresolved upstream identity in this repository; only its described coordination concepts are relevant.

## Success Criteria *(mandatory)*

- **SC-001**: A future maintainer can find the prior decision, current-code evidence, and re-evaluation trigger here without re-researching Bindle.
- **SC-002**: No second authoritative record of job execution or semantic facts is introduced.

## Assumptions

- `bindle` is not installed on this machine.
- No source URL or dependency declaration is present in this repository as of this evaluation.
- No concrete artifact-packaging, WASM deployment, Git/branch, or Obsidian requirement is in the current MVP scope; Git/branch workflows are explicitly deferred: [PLAN-MVP deferred scope](../../docs/PLAN-MVP.md#L34-L45).
