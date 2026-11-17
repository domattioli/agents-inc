<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Requirements Quality Checklist: Health Freshness and Key Names

**Purpose**: test whether spec 014 states its health, key-name, and doc requirements completely and unambiguously before implementation.
**Created**: 2026-10-01 (Supervisor, checklist phase)
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md)

## Health freshness

- [x] CHK001 Is the freshness window stated as a number with a unit? [Clarity, Spec FR-002: 24 hours]
- [x] CHK002 Is the rendering of a null `last_checked` specified? [Completeness, Spec Edge Cases: `unknown`]
- [x] CHK003 Is the treatment of a future timestamp specified? [Edge Case, Spec Edge Cases: fresh]
- [x] CHK004 Is it explicit that stale does not block `pick`? [Consistency, Spec FR-003]
- [x] CHK005 Is the effect of an `ok` report on `last_error` and `last_checked` both stated? [Completeness, Spec FR-001]
- [x] CHK006 Is the mapping from wrapper outcomes to `route.sh` results defined? [Gap resolved in Plan DD5]
- [x] CHK007 Is it stated that wrapper exit codes do not change? [Spec FR-003a]
- [x] CHK008 Is the shared-file overlap with `free_health.py` acknowledged, with the peer edit scoped out? [Spec Assumptions, Plan DD9, Tasks T005]
- [ ] CHK009 Is the stale threshold boundary (exactly 24 h) specified as stale or fresh? [Ambiguity, Plan DD3 chooses "above 24 h is stale"; spec silent; accepted]
- [x] CHK010 Is a backend absent from an existing health file handled? [Gap resolved in Plan DD2]

## Key names and paths

- [x] CHK011 Are both spellings and their target provider name listed? [Spec FR-004]
- [x] CHK012 Is the canonical name written by `setup_key` stated? [Spec FR-004: `OPENROUTER_API_KEY`]
- [x] CHK013 Is precedence for two different values defined? [Spec Edge Cases: prefer `OPENROUTER_API_KEY`; the modules read names only, so precedence applies only where a value is read]
- [x] CHK014 Are both read paths and the single write path named? [Spec FR-008]
- [x] CHK015 Is the "never print a value" rule testable? [Spec FR-005, SC-004: fake sentinels, captured output]
- [ ] CHK016 Is `agents_inc/free_caps.py:166`, which reads only `OPEN_ROUTER_API_KEY`, covered? [Gap: outside FR-004 scope; recorded in plan as a follow-up]

## Docs

- [x] CHK017 Is the correction form (appended dated note, no rewrite) stated? [Spec FR-006]
- [x] CHK018 Is the evidence for "later calls succeeded" identified? [Plan Existing code: local usage log, 2026-09-24 and 2026-09-30]
- [x] CHK019 Is the ZDR note's location and content specified? [Spec FR-007, Plan DD8]
- [x] CHK020 Is the peer-owned `docs/BENCH.md` excluded? [Spec FR-007]

## Safety

- [x] CHK021 Are live-file writes excluded for implement and tests? [Spec FR-009]
- [x] CHK022 Are new file names checked against the `.gitignore` key patterns? [Spec Assumptions, Plan Structure Decision]

## Notes

Open items CHK009 and CHK016 are accepted with the stated resolution.
