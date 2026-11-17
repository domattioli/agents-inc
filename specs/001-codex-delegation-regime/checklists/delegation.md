<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Delegation Regime Checklist

**Purpose**: Verify the delegation feature upholds its own premise and its governance constraints
**Created**: 2026-09-02
**Feature**: [spec.md](../spec.md)

## Context-Saving Invariant (the whole premise)

- [ ] CHK001 Does `gask.sh` read file contents itself, so bytes never pass through the Claude conversation? [FR-021, SC-001]
- [ ] CHK002 Does `gask.sh` refrain from echoing file contents to stdout, where a calling session would capture them? [SC-001]
- [ ] CHK003 Does the Codex leg receive paths rather than contents, so the same invariant holds by a different mechanism? [FR-021]
- [ ] CHK004 Is there an acceptance test proving the transcript stays clean for a 20+ file task, rather than only asserting the answer is correct? [SC-001]
- [ ] CHK005 Does any documented recipe accidentally instruct Claude to read files before delegating, defeating the premise?

## Failure Visibility (the spec's recurring anti-pattern)

- [ ] CHK006 Is stale-session substitution reported to the caller rather than silent? [FR-013, SC-005]
- [ ] CHK007 Is rate-limit exhaustion distinguishable from a generic backend failure? [FR-009, Edge Case 1]
- [ ] CHK008 Does a missing credential produce an actionable message naming the path and remedy? [FR-027]
- [ ] CHK009 Does startup fail loudly when the service never becomes reachable, rather than appearing to succeed? [FR-006]
- [ ] CHK010 Does an oversize input get refused before transmission rather than failing opaquely at the provider? [FR-011]
- [ ] CHK011 Are all five error conditions in FR-009 distinguishable by the caller from the response alone?

## Security and Data Governance

- [ ] CHK012 Is the shared secret absent from every log, response body, and terminal output? [FR-007, SC-006]
- [ ] CHK013 Are credentials stored outside the project tree, and does `.gitignore` guard against in-tree copies? [CLAUDE.md hard stop]
- [ ] CHK014 Is the Codex working-directory boundary narrowed from `$HOME` to the project, and reported at startup? [FR-008]
- [ ] CHK015 Does the routing policy exclude training-on-input backends from sensitive material? [FR-023]
- [ ] CHK016 Does the policy state that the shared secret confers shell-equivalent authority on the host?
- [ ] CHK017 Is the externally-reachable path opt-in rather than default, given the consumer is local? [FR-018]

## Governance Compliance

- [ ] CHK018 Is all code authorship delegated to Haiku subagents per the operator's coding-dispatch rule? [CLAUDE.md]
- [ ] CHK019 Does every code task have a following MAIN verification step, given two defects already survived subagent self-reporting?
- [ ] CHK020 Does the routing policy preserve code writing as a Haiku-subagent route rather than redirecting it to Codex? [FR-024]
- [ ] CHK021 Is delegated output treated as unverified, with local verification required before load-bearing use? [FR-026]

## Requirement Traceability

- [ ] CHK022 Does every FR in the spec map to at least one task in tasks.md?
- [ ] CHK023 Does every task in tasks.md trace to an FR or a stated acceptance criterion?
- [ ] CHK024 Are the operator's stated success criteria (tic-tac-toe from both backends) represented as explicit acceptance tasks?

## Notes

- CHK001–CHK005 are the highest-value items. A feature that saves no context while appearing to work is the primary failure risk, and it is invisible to functional testing.
