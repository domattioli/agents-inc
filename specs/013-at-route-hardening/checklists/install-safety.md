<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Install Safety and Hook Behavior Checklist: at_route Hardening

**Purpose**: Test the requirements (not the code) for completeness, clarity, and consistency where the installer touches user-scope host config and where the hook restricts routed calls.
**Created**: 2026-10-01
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md)

## Requirement Completeness

- [x] CHK001 Are the exact tools allowed and denied for routed Claude calls listed? [Completeness, Spec FR-001, Clarifications Q1]
- [x] CHK002 Is MCP tool exposure on routed Claude calls addressed, since a tool allowlist on built-ins alone leaves MCP write tools reachable? [Gap, resolved Plan DD1 `--strict-mcp-config`]
- [x] CHK003 Is the timeout message content specified (seconds, partial files, `git status`)? [Completeness, Spec FR-002]
- [x] CHK004 Is the behavior for a foreign file already at an `@alias` path specified? [Gap, resolved Plan DD6: untouched plus notice]
- [x] CHK005 Is the behavior for a legacy file that is not the at_route hook specified? [Gap, resolved Plan DD7: content marker check]
- [x] CHK006 Is the settings hook timeout requirement stated relative to the alarm? [Completeness, Spec FR-005, Edge Cases]
- [x] CHK007 Is the source of the checkout path for drift detection specified? [Gap, resolved Plan DD8 `source-checkout` state record]

## Requirement Clarity

- [x] CHK008 Is "rollback restores" bound to a concrete mechanism? [Ambiguity, Spec FR-007; resolved Plan DD7: journal recovery; `agents-inc rollback` swaps `current` only]
- [x] CHK009 Is "installed release copy" bound to a literal path form (through `current`, not resolved)? [Clarity, Spec FR-005, Plan DD4]
- [x] CHK010 Is the `@openrouter` header format for a missing model line specified? [Clarity, Spec Edge Cases]

## Requirement Consistency

- [x] CHK011 Do FR-004 (owned links) and FR-007 (legacy relink) agree on what uninstall leaves behind? [Consistency, Plan DD6: receipt predecessor `None`, uninstall removes links and does not recreate legacy links]
- [x] CHK012 Is the alias count consistent across spec and plan (11 with `openrouter`)? [Consistency, Spec Assumptions, Plan DD6]
- [x] CHK013 Does the owned-hook test (prefix `<launcher> hook `) still identify the new direct `bash <current>/...` command? [Conflict, resolved Plan DD4: `_owned` matches the exact command]

## Scenario and Edge Case Coverage

- [x] CHK014 Are requirements defined for a fast non-alarm failure so it is not mislabeled a timeout? [Coverage, Spec FR-003]
- [x] CHK015 Is an inherited `MODEL` value covered for `@openrouter`? [Coverage, Spec FR-010]
- [x] CHK016 Is the governance-on refusal of `oask.sh` covered? [Coverage, Spec Edge Cases, FR-012]
- [x] CHK017 Is a missing source checkout at doctor time covered without a false drift? [Coverage, Spec Edge Cases, Plan DD8]
- [ ] CHK018 Are grandchild processes of `claude` that survive the alarm addressed beyond the message? [Gap, accepted: Spec Edge Cases limits to the message; out of scope]

## Safety and Reversibility

- [x] CHK019 Is every host-config mutation required to be journaled with a byte-exact backup? [Spec FR-004, Plan DD5-DD7]
- [x] CHK020 Is the live machine excluded from implementation and tests? [Spec FR-016]
- [x] CHK021 Is a byte-identical settings file after install then uninstall a measurable criterion? [Spec SC-004]
- [x] CHK022 Is the peer-owned lexicon edit planned as blocked rather than performed? [Spec FR-014, Plan DD10]

## Notes

- CHK018 stays open by decision; recorded for the analyze phase.
