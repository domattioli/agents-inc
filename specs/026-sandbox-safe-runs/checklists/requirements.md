<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-analyze repo=agents_Inc session=b8dceec1 -->
# Requirements Quality Checklist: 026 sandbox-safe runs and broker hygiene

**Purpose**: Unit tests for the requirements in `spec.md`: completeness, clarity, consistency, measurability and coverage, checked before implement. Replaces the specify-phase checklist (its one note, "FR-009 leaves the route to plan", was overtaken by the 2026-10-24 Clarification).
**Created**: 2026-10-24
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [tasks.md](../tasks.md)
**Depth**: standard. **Audience**: reviewer (CoS) before the implement dispatch. **Focus**: sandbox confinement (US2, US3) and refusal text (US4), the two highest-risk clusters.

Each item ends with **pass** or **open** and a one-line reason.

## Requirement Completeness

- [x] CHK001 Does every story name the files it may edit? [Completeness, Spec §Scope] **pass**: spec line 11 lists them; plan departures D1 (`tests/test_dispatch_grants.py`) and D2 (`skills/workerbee/SKILL.md:774`) add two files the list omits.
- [x] CHK002 Is the test file for FR-012 inside the Scope list? [Conflict, Spec §FR-012, §Scope] **pass**: CoS accepted D1; FR-012 now names `tests/test_dispatch_broker.py`, which is in Scope.
- [x] CHK003 Are the seeded git config keys specified? [Completeness, Spec §FR-009] **pass (N/A)**: superseded; FR-009 seeds no git config after the CoS reproduction.
- [x] CHK004 Does the spec define the FR-009 `GIT_CONFIG_GLOBAL` trigger in a way a fake-HOME test can decide? [Gap, Spec §FR-009] **pass**: moot; FR-009 no longer sets `GIT_CONFIG_GLOBAL` (CoS reproduction, plan "US2 reproduction").
- [x] CHK005 Are the triage verdict values and the evidence each needs defined? [Completeness, Spec §FR-001] **pass**: `fixed` (commit or decision plus file:line), `open` (one sentence), `moved` (owner).
- [x] CHK006 Is the broker lock file's content and lifetime defined? [Completeness, Spec §FR-013, §Key entities] **pass**: pid as text, exclusive for the broker's lifetime, OS release on exit.
- [x] CHK007 Does US3 cover the MCP-transport broker as well as `serve()`? [Gap, Spec §FR-013] **pass**: deferred to a follow-up issue by CoS ruling; not blocking.
- [x] CHK008 Is the ask_lead answer text covered by the control-character screen? [Gap, Spec §FR-020] **pass**: deferred to a follow-up issue by CoS ruling; not blocking.

## Requirement Clarity

- [x] CHK009 Is the FR-006 skip reason given verbatim? [Clarity, Spec §FR-006] **pass**: exact string given.
- [x] CHK010 Is "first local bind attempted once" scoped clearly? [Clarity, Spec §FR-006] **pass**: "test class (or module)"; plan picks one cached probe per module.
- [x] CHK011 Are the refused code points listed exactly? [Clarity, Spec §FR-018] **pass**: C0 minus tab, LF, CR; DEL; seven bidi ranges by code point.
- [x] CHK012 Is the unit of "offset" in the FR-019 message defined? [Ambiguity, Spec §FR-019] **pass**: code points are listed in FR-018; CoS ruling.
- [x] CHK013 Does FR-018 say how non-string slot values (`GATES`, `BASH_ALLOW` lists) are screened? [Ambiguity, Spec §FR-018] **pass**: FR-018 now screens nested strings and names the top-level key (D5).
- [x] CHK014 Is the FR-014 stderr text and exit code given verbatim? [Clarity, Spec §FR-014] **pass**: text, `BROKER_USAGE` (2) and the `pid unknown` fallback given.
- [x] CHK015 Is the direct-path stderr line for `refused-control-char` given verbatim? [Ambiguity, Spec §FR-020] **pass**: plan's stderr line accepted as the FR-015 message; CoS ruling.
- [x] CHK016 Is the new caveman declaration value spelled out? [Clarity, Spec §FR-023, §Key entities] **pass**: `caveman: unreadable -> by hand` plus the two checker keywords.

## Requirement Consistency

- [x] CHK017 Do FR-009 and the Clarification agree on the route? [Consistency, Spec §Clarifications, §FR-009] **pass**: both say metadata reads on the broker run dir's folders, no `~/.config` grant, no XDG change.
- [x] CHK018 Is FR-011 consistent with the 022 trusted-snapshot rule? [Consistency, Spec §FR-011] **pass**: the readable copy is informational; the trusted copy judges.
- [x] CHK019 Does "read (not write)" in FR-011 hold given the current profile shape? [Conflict, Spec §FR-011] **pass**: FR-011 now requires an explicit write deny on `read_ok` paths (D4).
- [x] CHK020 Is the report declaration consistent across every surface that carries it? [Consistency, Spec §FR-023] **pass**: CoS accepted D2; Scope now lists `skills/workerbee/SKILL.md` (declaration line only).
- [x] CHK021 Are FR-026 grants consistent with today's `--run-dir --write` grants? [Consistency, Spec §FR-026] **pass**: plan checked `runtime.py:134-139`; the mapping is identical once the raise goes.
- [x] CHK022 Are the CHANGELOG rule and the per-story issue numbers consistent? [Consistency, Spec §Scope] **pass**: one `### Fixed` line per code story, ending with its issue numbers.

## Acceptance Criteria Quality

- [x] CHK023 Can SC-001 and SC-002 be checked by one command each? [Measurability, Spec §SC-001, §SC-002] **pass**: exact unittest commands given.
- [x] CHK024 Is "no new skips" in SC-001 measurable without a recorded baseline? [Measurability, Spec §SC-001] **pass**: SC-001 now compares against the T001 baseline skip count.
- [x] CHK025 Is SC-003 tied to a named test and platform? [Measurability, Spec §SC-003] **pass**: the FR-012 test, macOS, outside a sandbox.
- [x] CHK026 Is SC-004 checkable item by item? [Measurability, Spec §SC-004] **pass**: one row per FR-001 item, comment per closed issue.

## Scenario and Edge Case Coverage

- [x] CHK027 Are stale-lock and symlinked-lock cases specified? [Edge Case, Spec §FR-013, §FR-015] **pass**: OS release on crash; symlink refused with exit 2.
- [x] CHK028 Are accepted inputs specified beside refused ones for US4? [Coverage, Spec §FR-021] **pass**: tab, LF, CRLF and non-ASCII text named as accepted.
- [x] CHK029 Are C1 controls (U+0080 to U+009F) and other invisible format characters (U+2028, U+FEFF) intentionally excluded? [Coverage, Gap, Spec §FR-018] **pass**: deferred to a follow-up issue by CoS ruling; not blocking.
- [x] CHK030 Is the non-macOS and nested-sandbox case for FR-012 specified? [Edge Case, Spec §FR-012] **pass**: skip with a stated reason when `sandbox_available()` is false.
- [x] CHK031 Is a resumed Worker turn covered by the TMPDIR rule? [Coverage, Spec §FR-010] **pass**: TMPDIR stays `<run-dir>/tmp`; `_child_tmp(resume_turn=True)` reuses it, and the FR-009 metadata rules derive from that same path.

## Non-Functional (security)

- [x] CHK032 Does the spec state why a read grant was rejected? [Security, Spec §Clarifications] **pass**: a read grant would expose a git credential-store file under `~/.config/git`.
- [x] CHK033 Is the Codex read-only sandbox explicitly not widened? [Security, Spec §Scope, R2] **pass**: out of scope by ruling R2.
- [x] CHK034 Are Worker and Lead write grants on `broker.lock` explicitly forbidden? [Security, Spec §FR-016] **pass**: FR-016; plan confirms no code change is needed and adds assertions.

## Dependencies and Assumptions

- [x] CHK035 Is the #103 root cause confirmed rather than inferred? [Assumption, Spec §Assumptions] **pass**: CoS reproduction 2026-10-24 confirmed the cause (metadata reads on the broker run dir's folders); spec US2 intro tagged [verified].
- [x] CHK036 Is advisory locking availability stated for every supported host? [Assumption, Spec §Assumptions] **pass**: `flock`/`fcntl` on macOS and Linux.
- [x] CHK037 Is the supervisor-only rule for GitHub writes stated? [Dependency, Spec §Assumptions] **pass**: no delegate writes to GitHub; tasks mark US0 [CoS].

## Summary

37 items: 36 pass, 1 N/A (CHK003), 0 open after CoS rulings 2026-10-24 (CHK007, CHK008, CHK029 pass as deferred follow-ups).
