<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-pipeline repo=agents_Inc session=spec024 -->
# Requirements quality checklist: spec 024

Purpose: check that the spec 024 requirements are complete, clear and testable before implement. Created 2026-10-23. Depth: standard. Audience: reviewer. Answered by the Orchestrator Lead (no operator attached).

## Requirement completeness

- [x] CHK001 Is every 3.10 claim named in #90 mapped to a requirement with a file and line? [Completeness, Spec FR-001 to FR-004] Yes: `pyproject.toml:10,28`, `README.md:11,48`, `AGENTS.md:23`, `docs/START-HERE.md:32`.
- [x] CHK002 Does the spec say whether the `Python 3.10` comment at `tests/test_packaging.py:20` changes? [Gap, Spec A2] Yes: it stays (A2).
- [x] CHK003 Are both #91 triggers (contract line, prose "Exit gate") covered by named tests? [Completeness, Spec FR-011]
- [x] CHK004 Is the conflict with the existing assertion at `tests/test_dispatch_contract.py:262-263` named and resolved? [Conflict, Spec FR-012, Q2]
- [x] CHK005 Are all three #92 problems (compound command, cwd, HEAD moves) mapped to a requirement? [Completeness, Spec FR-014, FR-016, FR-018]
- [x] CHK006 Are all three #93 suggestions (fallback search, searched paths, absolute resume form) mapped to a requirement, with the index alternative excluded? [Completeness, Spec FR-020 to FR-023, Out of scope]

## Requirement clarity

- [x] CHK007 Is "looks like a command result" defined as a closed list of forms? [Clarity, Spec FR-009]
- [x] CHK008 Is the resolution order for the verify repository stated, including the legacy fallback? [Clarity, Spec FR-014, A3]
- [x] CHK009 Is the candidate-parent order exact, with the rule for unset variables and duplicates? [Clarity, Spec FR-020]
- [x] CHK010 Is the error text given verbatim? [Clarity, Spec FR-021]
- [x] CHK011 Is the README note wording fixed? [Clarity, Plan US1] Fixed in plan US1 and T003.

## Consistency

- [x] CHK012 Does the status-line suffix requirement agree with the pinned `STATUS_RE`? [Consistency, Spec FR-023] FR-023 updates `STATUS_RE`.
- [x] CHK013 Does the render refusal agree with the rule that the gate rejects and never rewrites? [Consistency, Spec FR-016, Q3]
- [x] CHK014 Is the CHANGELOG ownership the same in spec, plan and tasks? [Consistency] Lead writes all four lines (plan Order, T017).

## Edge cases

- [x] CHK015 Is `--repo` without a value specified? [Edge Case, Spec FR-015]
- [x] CHK016 Is behavior with an explicit `--run-dir` specified? [Edge Case, Spec FR-022, Q4]
- [x] CHK017 Is an old snapshot without the `repo` key specified? [Edge Case, Spec A3]
- [x] CHK018 Is a `[verified] exited` line with no code still a failure? [Edge Case, Spec FR-010]

## Acceptance criteria

- [x] CHK019 Does every task name a runnable acceptance command? [Measurability, tasks.md] T019 is deferred to the Chief of Staff by the dispatch.
- [x] CHK020 Does SC-001 to SC-005 match the dispatch SUCCESS GATE? [Traceability]

## Dependencies

- [x] CHK021 Is the shared-file order of US3 and US4 stated? [Dependency, Plan Order]
