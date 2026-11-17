<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Tasks: Dispatch Graph Ledger

**Input**: Design documents from `/specs/002-dispatch-graph-ledger/`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)

**Approach**: TDD — write tests first, ensure they fail before implementation. Each user story implements independently testable increments.

**Organization**: Tasks grouped by user story (US1: Audit, US2: Lint, US3: Export) with shared foundational tasks in Phase 2.

---

## Phase 1: Setup (Project Structure)

**Status**: Existing project structure sufficient — no setup tasks required.

---

## Phase 2: Foundational (Ledger Module Infrastructure)

**Purpose**: Core ledger data model and I/O — blocking prerequisite for all user stories.

- [x] T001 Create ledger module skeleton in `workerbees/ledger.py` with Node + Finding dataclasses; Edge implied by parent_id + edge_type on child (per data-model)
- [x] T002 [P] Implement idempotent JSONL append in `workerbees/ledger.py`: `record_dispatch()` and `record_return()` functions with error swallowing per FR-008
- [x] T003 Implement ledger load with deduplication in `workerbees/ledger.py`: `load(workspace)` returns Ledger + warnings, handles corrupt/missing files gracefully

**Checkpoint**: Ledger module ready; foundation complete before user story work begins.

---

## Phase 3: User Story 1 — Audit who did what (Priority: P1) 🎯 MVP

**Goal**: Record every delegated job as a node; operator can export and answer "which models touched this, in what order?"

**Independent Test**: Run one brief with worker + reviewer; ledger contains exactly 2 nodes, 1 `reviews` edge, all required fields present.

### Tests for User Story 1 (TDD: Write tests FIRST, ensure they FAIL)

- [x] T004 [P] [US1] Test node creation with all required fields in `tests/test_ledger.py`: model, tier, task, provider, status, timestamp
- [x] T005 [P] [US1] Test idempotent append by node id in `tests/test_ledger.py`: same node written twice collapses to one on load
- [x] T006 [US1] Test brief with worker + reviewer produces 2 nodes + 1 `reviews` edge in `tests/test_pipeline.py` (fixture: fake runner returning WorkerResult)

### Implementation for User Story 1

- [x] T007 [P] [US1] Implement Node + Finding dataclasses in `workerbees/ledger.py` with validation (edge_type enum, tier enum, status eventually consistent); Edge implied by parent_id + edge_type on child (per data-model)
- [x] T008 [US1] Implement basic Ledger class in `workerbees/ledger.py`: nodes dict keyed by id, dedup on load (last-write-wins by timestamp)

**Checkpoint**: User Story 1 complete — ledger records all nodes; tests pass independently.

---

## Phase 4: User Story 2 — Catch a bad hierarchy before it costs (Priority: P2)

**Goal**: Lint the ledger to detect depth > 1, same-vendor review, frontier without gate reason.

**Independent Test**: Feed hand-built ledger with 3 violations; lint reports exactly 3 findings with node ids, zero false positives.

### Tests for User Story 2 (TDD: Write tests FIRST)

- [x] T009 [P] [US2] Test lint rule "depth" in `tests/test_ledger.py`: node whose parent has a parent triggers finding with node id
- [x] T010 [P] [US2] Test lint rule "same_vendor_review" in `tests/test_ledger.py`: reviewer with same provider as reviewed node triggers finding with both ids
- [x] T011 [P] [US2] Test lint rule "frontier_without_gate" in `tests/test_ledger.py`: frontier-tier node with null gate_reason triggers finding with node id

### Implementation for User Story 2

- [x] T012 [US2] Implement Finding dataclass in `workerbees/ledger.py`: rule, node_ids, message
- [x] T013 [US2] Implement `lint(ledger)` function in `workerbees/ledger.py`: checks depth, same_vendor_review, frontier_without_gate; returns list of Findings

**Checkpoint**: User Story 2 complete — linter detects all 3 rule violations; tests pass independently.

---

## Phase 5: User Story 3 — See and share the shape (Priority: P3)

**Goal**: Export ledger as JSON (round-trippable) and Mermaid diagram; compute cost rollup per root.

**Independent Test**: Export 2-node ledger; JSON round-trips identically; Mermaid lists both nodes and one edge.

### Tests for User Story 3 (TDD: Write tests FIRST)

- [x] T014 [P] [US3] Test JSON export and round-trip in `tests/test_ledger.py`: `to_json()` and `from_json()` preserve all fields for 2+ node ledger

### Implementation for User Story 3

- [x] T015 [US3] Implement `to_json(ledger)` and `from_json(s)` in `workerbees/ledger.py`: {"nodes": [...]}, round-trips exactly
- [x] T016 [US3] Implement `to_mermaid(ledger)` in `workerbees/ledger.py`: graph TD with node lines and edge lines, one per node/edge, labeled by edge_type
- [x] T017 [P] [US3] Implement `rollup(ledger)` in `workerbees/ledger.py`: per-root subtree sum of subscription_calls and seconds

**Checkpoint**: User Story 3 complete — operator can export and analyze; all three user stories independently testable and functional.

---

## Phase 6: Integration & Edge Cases

**Purpose**: Wire ledger recording into pipeline and doctor; handle fault injection and edge cases.

- [x] T018 [US1] Add ledger hooks to `workerbees/pipeline.py`: wrap worker call with `record_dispatch()` before and `record_return()` after, one run_id per brief(), parent_id=None, edge_type=None for root
- [x] T018b Add optional `gate_reason: str | None = None` param to `pipeline.brief()`; pass to `record_dispatch()`; required non-empty when `worker_tier == 'frontier'` (lint rule `frontier_without_gate`)
- [x] T019 [US1] Add ledger hooks to `workerbees/pipeline.py`: wrap reviewer call with same, parent_id=worker_node_id, edge_type="reviews"
- [x] T020 [US1] Add ledger hooks to `workerbees/doctor.py`: wrap `probe_cli()` call from `doctor.run()` with `record_dispatch()`/`record_return()`, edge_type="probes", parent_id=None, one run_id per run()
- [x] T021 [P] Extend `tests/test_pipeline.py`: assert ledger file exists post-brief with 2 nodes + 1 edge (fault injection: mock ledger write failure, verify brief status unchanged per SC-004)
- [x] T022 [P] Extend `tests/test_doctor.py`: assert ledger file contains N probe nodes with edge_type="probes" after doctor.run()
- [x] T023 [P] Test sequential brief() calls in same workspace in `tests/test_pipeline.py`: two distinct brief() calls produce two distinct run_ids, nodes not interleaved, each brief's nodes grouped by run_id

**Checkpoint**: Integration wired; edge cases covered; fault injection validates FR-008 (ledger failure never fails brief); sequential briefs produce distinct run_ids.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, final validation, and edge case robustness.

- [x] T024 Update docstrings in `workerbees/ledger.py` for all public functions (record_dispatch, record_return, load, lint, to_json, from_json, to_mermaid, rollup) with FR/SC references
- [x] T025 [P] Add edge case test in `tests/test_ledger.py`: ledger file missing/corrupt → load() returns empty Ledger + warning, never raises
- [x] T026 Add Node/Edge/Run/Finding/Ledger row definitions to project `CONTEXT.md` (if exists) or `.specify/memory/context.md` to make types discoverable for future sessions
- [x] T027 Run all tests in `tests/test_ledger.py`, `tests/test_pipeline.py`, `tests/test_doctor.py` and verify spec acceptance scenarios 1.1–3.2 pass; document MVP validation in `docs/DECISIONS.md`
  - assert len(ledger nodes) == number of runner invocations (worker + reviewer + corrections) in a test with a counting fake runner (SC-001)

**Checkpoint**: All 27 tasks complete; ledger ready for deployment.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (Foundational)**: No dependencies → start immediately
- **Phase 3–5 (User Stories)**: ALL depend on Phase 2 completion → BLOCKS all story work
- **Phase 6 (Integration)**: Depends on Phases 3–5 for test coverage
- **Phase 7 (Polish)**: Depends on Phases 3–5 and 6 for completeness

### Within User Stories (TDD Order)

**CRITICAL**: Tests marked above in Phases 3–5 MUST be written and FAIL before implementation tasks.

Each user story:
1. Write all test tasks [Txxx] first (verify RED)
2. Implement model/function tasks (verify GREEN)
3. Validate independent testability (other stories unaffected)

### Parallel Opportunities

- **Phase 2**: T001, T002, T003 are largely sequential (load/append/dedup depend on each other) — run in order
- **Phase 3 Tests**: T004, T005 can run in parallel; T006 depends on pipeline integration (run after T004–T005 RED)
- **Phase 3 Impl**: T007, T008 sequential (Edge requires Node model)
- **Phase 4 Tests**: T009, T010, T011 fully parallelizable [P] → launch together
- **Phase 4 Impl**: T012, T013 sequential (lint function depends on Finding class)
- **Phase 5 Tests**: T014 parallelizable with prior story tests [P]
- **Phase 5 Impl**: T015, T016, T017 parallelizable [P] (different export formats)
- **Phase 6**: T018, T019, T020 sequential (depend on working ledger module)
- **Phase 6 Tests**: T021, T022 parallelizable [P] (test different modules)
- **Phase 7**: T023, T024 parallelizable [P] (docs + edge case test); T025 depends on all

### Parallel Example: Phase 4 (User Story 2) Tests

```bash
# Launch all three lint-rule tests in parallel:
Task T009: Test "depth" rule
Task T010: Test "same_vendor_review" rule
Task T011: Test "frontier_without_gate" rule
# Then implement T012–T013 sequentially after all three tests are RED
```

### Parallel Example: Phase 5 Impl (User Story 3)

```bash
# Launch all three export functions in parallel:
Task T015: Implement to_json() + from_json()
Task T016: Implement to_mermaid()
Task T017: Implement rollup()
# No dependencies between these; all use the same Ledger + Node structures from earlier phases
```

### Parallel Example: Phase 7 Polish

```bash
# Launch these tasks in parallel:
Task T024: Update docstrings (ledger.py)
Task T025: Add edge case test (test_ledger.py)
# T026 and T027 can run after T025 completes
```

---

## Implementation Strategy

### MVP Scope (User Story 1 Only)

1. Complete Phase 2: Foundational (ledger module skeleton + I/O)
2. Complete Phase 3: User Story 1 (record + load, tests all green)
3. Complete integration for pipeline.py (T018–T019)
4. **STOP and VALIDATE**: One brief with worker + reviewer produces ledger with 2 nodes + 1 edge
5. Deploy/demo MVP (auditable brief history)

**MVP success**: Spec Acceptance Scenarios 1.1–1.3 all pass.

### Incremental Delivery (Full Feature)

1. **MVP (above)**: Ledger records (US1)
2. **Phase 4**: Add lint (US2) → operator can validate graph structure
3. **Phase 5**: Add export (US3) → operator can share and analyze
4. **Phase 6**: Extend pipeline + doctor integration → all job types recorded
5. **Phase 7**: Polish and edge case robustness

Each phase ships independently usable increment without breaking prior ones.

---

## Notes

- All tasks use TDD: write test first, verify RED, then implement and verify GREEN
- [P] tasks = different files, no cross-task dependencies → parallelizable
- Each user story independently testable and deployable (Phase 3 ≠ Phase 4 ≠ Phase 5)
- Fault injection (SC-004): ledger write failure must not change brief status
- Edge cases: job crash mid-run (node left in "dispatched"), two briefs interleaving (separate run_ids), corrupt ledger on disk (empty + warning on load)
- Task count: 3 foundational + 5 US1 + 5 US2 + 4 US3 + 6 integration + 4 polish = 27
- Stop at any checkpoint to validate independently before proceeding to next story
