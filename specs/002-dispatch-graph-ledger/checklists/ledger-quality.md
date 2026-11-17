<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Ledger Quality Checklist: Lint Rules, Idempotency & Failure Isolation

**Purpose**: Validate requirements quality for lint rule correctness, idempotent append, and failure isolation (ledger never blocks a brief)
**Created**: 2026-09-05
**Feature**: ../spec.md, ../data-model.md

---

## Lint Rule Correctness

- [ ] CHK001 Is the `depth` rule condition specified with measurable clarity: "parent already has a non-null parent_id"? [Clarity, Data-model §Lint-rules-1]
- [ ] CHK002 Does the `depth` rule's acceptance criteria include a concrete example (e.g., a 3-level chain)? [Gap]
- [ ] CHK003 Is the `same_vendor_review` rule's condition fully specified to avoid edge cases: does it compare `node.provider == parent.provider` or some other field? [Ambiguity, Data-model §Lint-rules-2]
- [ ] CHK004 Is the `same_vendor_review` rule's behavior clear when the parent node has no parent (root): should a root-level reviewer with same vendor as any other node be flagged? [Clarification, Gap]
- [ ] CHK005 Does the `frontier_without_gate` rule define what "empty" means for gate_reason (null vs. empty string vs. whitespace-only)? [Clarity, Data-model §Lint-rules-3]
- [ ] CHK006 Are the three lint rules (depth, same_vendor_review, frontier_without_gate) the exhaustive list, or are there additional rules intended to be added later? [Completeness, Spec §FR-005]
- [ ] CHK007 Is lint rule ordering specified (e.g., report all depth violations before all same_vendor_review violations)? [Gap]
- [ ] CHK008 Is the lint output format for multi-violation scenarios defined: one Finding per rule or one Finding per node or grouped? [Clarity, Data-model §Finding]
- [ ] CHK009 Are lint rules required to report node IDs consistently (e.g., always sorted, or as discovered)? [Gap]
- [ ] CHK010 Is the "zero findings on a clean ledger" requirement (SC-002) applied to all three rules equally, or are some rules optional? [Consistency, Data-model §Lint-rules]

## Idempotent Append

- [ ] CHK011 Is idempotency enforced at the disk level (unique constraint on node id in file) or at read time (dedup on load)? [Clarity, Plan §Phase-1, Data-model §Node]
- [ ] CHK012 When two lines with the same node id exist in the file, is the tiebreaker specified: last-write-wins by timestamp, or by file order? [Clarity, Data-model §Node]
- [ ] CHK013 Does the timestamp field cover both dispatch and return records for the same id, and is it guaranteed unique/monotonic per node? [Gap, Spec §FR-001]
- [ ] CHK014 Is the behavior defined when `record_dispatch()` and `record_return()` are called out of order (e.g., return before dispatch)? [Coverage, Gap]
- [ ] CHK015 Is idempotency tested with duplicate dispatch calls (same node id, seconds apart) to verify no duplication on read? [Acceptance, Spec §Edge-Cases]
- [ ] CHK016 Is the collision risk quantified if node id is caller-supplied (e.g., uuid4 collision probability acceptable)? [Measurability, Plan §Phase-0]
- [ ] CHK017 Are concurrent appends from multiple processes defined as in/out of scope? [Scope, Gap]
- [ ] CHK018 Is the read-modify-write risk acknowledged if idempotency is enforced on read, and is the edge case of "file corrupt mid-append" addressed? [Assumption, Spec §Edge-Cases]

## Failure Isolation (Ledger Never Blocks Brief)

- [ ] CHK019 Is the guarantee "ledger failure never changes brief status" (FR-008, SC-004) stated as a binding non-functional requirement? [Completeness, Spec §FR-008]
- [ ] CHK020 Is the error handling scope defined: which I/O errors must be caught (write failure, missing .workerbees directory, permission denied, disk full)? [Completeness, Gap]
- [ ] CHK021 Are ledger write failures logged into the receipt dict (as stated in plan) specified in the functional requirements, or only in implementation plan? [Consistency, Spec §FR-008, Plan §Phase-1]
- [ ] CHK022 Is the expected latency impact of ledger append quantified or specified as "not perceptible"? [Measurability, Plan §Performance-Goals]
- [ ] CHK023 Is ledger read failure (on corrupt or missing file) specified to return an empty ledger plus warnings, never raise? [Clarity, Spec §Edge-Cases]
- [ ] CHK024 Is the behavior defined for a brief that runs in a workspace without write permission to .workerbees/? [Coverage, Gap]
- [ ] CHK025 Are there acceptance criteria for a fault-injected test (SC-004: ledger write failure never changes brief status)? [Measurability, Spec §SC-004]
- [ ] CHK026 Is the scope of "brief" specified for failure isolation: does it include doctor preflight runs, or only top-level briefs? [Scope, Spec §FR-003]
- [ ] CHK027 Are partial ledger write failures (e.g., dispatch recorded but return lost) defined as acceptable if the brief succeeds? [Consistency, Spec §Edge-Cases]
- [ ] CHK028 Is the recovery path specified if a brief crashes mid-run and leaves nodes in `dispatched` status; are they left as-is or updated on a retry? [Coverage, Gap]

---

## Notes

- Items CHK001–CHK010 focus on the three lint rules and their specification clarity (same_vendor_review rule has a potential edge case with roots; frontier_without_gate needs null/empty definition)
- Items CHK011–CHK018 focus on idempotent append and the tiebreaker when duplicates occur
- Items CHK019–CHK028 focus on failure isolation and the guarantee that ledger I/O never blocks the brief
- All items are phrased as requirement quality tests, not implementation verification (e.g., "Is X specified" not "Does X work")
- Traceability: Items reference Spec §FR-NNN and Data-model §sections; Gaps marked where existing docs do not answer the question
