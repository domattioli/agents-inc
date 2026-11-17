<!-- provenance: author=domattioli model=opus effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=spec041-lead -->
# Implementation Plan: Terminology, one name per thing

**Branch**: `041-terminology-one-name` | **Date**: 2026-11-15 | **Spec**: `spec.md` (this directory)
**Input**: Feature specification `specs/consumers/agents-inc/specs/041-terminology-one-name/spec.md`, clarified 2026-11-15.

## Summary

Prose-only terminology cleanup across agents-inc current docs, one canonical term table in CONTEXT.md, one data string change in `agents_inc/governance.json`, one new decision entry, and a new deterministic lint (Python, standard library, run by the unittest suite) that keeps retired aliases out of current `.md` docs. No behavior, routing, gate or identifier change.

## Technical Context

**Language/Version**: Python 3.11+ (standard library only), Markdown
**Primary Dependencies**: none new
**Storage**: N/A (one JSON string value)
**Testing**: `python3 -m unittest discover -s tests -p 'test_*.py'`
**Target Platform**: macOS and the docker dev container (memory: dev in docker)
**Project Type**: CLI and library with documentation canon
**Performance Goals**: lint runs in under 2 seconds on the tracked tree
**Constraints**: zero identifier renames (FR-015); canon edits need a different-vendor reviewer (D46.10, hard separation 2)
**Scale/Scope**: about 15 current-doc files, about 300 candidate hits to read, a minority to change (inventory.md)

## Constitution Check

Against `memory/constitution.md` v1.9.2 (unratified, violations report as WARN).

- P0 cross-reference: the term table lives in CONTEXT.md only; DELEGATION-MODEL.md and QUICKREF.md cite it. PASS.
- P1 repo-scoped writes: all edits inside agents-inc; out-of-repo items are listed follow-ups (spec FR-018). PASS.
- P2 labor ladder: the constitution text "Orchestrator (aka Supervisor)" will conflict with the 041 decision. Canon wins per P0; the constitution is fixed in a DomI follow-up. WARN, tracked.
- P3 no self-graded gates: every task has a check command; reviewer is separate from author. PASS.
- P4 deterministic over prompt: the alias ban is a lint, not a prompt rule. PASS.
- P5 $0: subscription models only. PASS.
- P6 audience docs: CONTEXT.md and DELEGATION-MODEL.md keep their current register; the decision entry is human prose. PASS.
- P7 nickname discipline: no change. PASS.
- P8 prompt contract: `skills/workerbee/header.md` wording change ("your dispatcher" to "your supervisor") must keep `check_dispatch_prompt.py` green. PASS if T012 passes.
- P9 edit hygiene: surgical edits per hit. PASS.
- P10 lesson relay: the constitution conflict is relayed up as LESSON-CANDIDATE. PASS.

## Surfaces to edit (counts from inventory.md, current docs unless stated)

| File | What changes | Driving hits |
|---|---|---|
| `CONTEXT.md` | canonical term table; rows Worker (10), Orchestrator (31), Lead (32), CoS (34), CEO (42), Rung (48), Second opinion (49, "A Supervisor"), Team (60), Chief (61), Driver (8), Host (7), Stdin worker (9), Tier (23), Delegate (new) | 20 Lead, 20 Worker, 9 CoS, 3 CEO, 6 Team |
| `docs/governance/DELEGATION-MODEL.md` | Roles list, CEO only in chain positions, Owner removed, flash-tier (line 69), Guest agent sentence | 35 Lead, 40 CoS, 28 CEO, 2 Owner, 1 flash-tier |
| `docs/governance/ROUTING-RANKING.md` | rung table "Orchestrator / Supervisor", D34 note kept as history pointer, "A Supervisor compares" to lowercase | 2 Second, Supervisor rows |
| `skills/workerbee/SKILL.md` | ultra-tier (3), flash-tier (2), Supervisor as rung or title (23 total hits to read), Interlocutor (1), dispatcher (line 634) | 23 Supervisor, 22 Orchestrator, 58 tier |
| `skills/workerbee/QUICKREF.md` | "The supervisor owns the verifier" stays (relational); check rung and CEO words | 12 operator |
| `skills/workerbee/header.md` (lines 17, 19, 20), `skills/workerbee/slots.md` (lines 47, 48) | relational "dispatcher" to "supervisor"; header line 19 "one rung up" to "one level up the chain" | 3 and 2 Dispatcher, 1 "one rung up" |
| Prompt-text string literals: `skills/workerbee/scripts/render_dispatch.py:37`, `tests/test_dispatch_schema_131.py:252`, `skills/workerbee/tests/fixtures/example_slots.json:4` | "hand back to the dispatcher" to "hand back to your supervisor"; strings only, no identifier or logic | 1 each |
| `skills/codex-bridge/SKILL.md` | ultra-tier (2) | 2 |
| `skills/speckit-pipeline/SKILL.md` | Orchestrator and Supervisor role uses, frontier (3) | 10 Orchestrator |
| `README.md`, `docs/HOW-IT-WORKS.md`, `docs/START-HERE.md`, `mods/delegate-pane/README.md` | role aliases, CEO in prose | 6 Orchestrator or Supervisor lines across the first three; 19 Lead in pane README |
| `AGENTS.md` | rung list wording only if it uses an alias | check |
| `agents_inc/governance.json:25` | `name` "Orchestrator Supervisor" to "Supervisor" | 1 (no test asserts it: `git grep 'Orchestrator Supervisor'` finds only this line) |
| `docs/DECISIONS.md` | append the 041 entry | n/a |

Not edited: `docs/BENCH.md` provider-price "cheap" and "tier" (96 and 51 hits); code identifiers; historical surfaces.

## Lint design

- Script: `tools/check_terms.py` (standard library, no network). Exit 0 clean, 1 on findings, 2 on bad config.
- Pattern list source: `tools/retired_terms.json`, an array of `{pattern, replacement, row}` where `row` names the CONTEXT.md term-table row that retires it. A unit test cross-checks that every `row` exists in the table and every retired alias marked `lint` in the table has at least one pattern; `review-only` aliases need none (SC-003).
- Initial patterns (regex, case-sensitive unless noted; every pattern is a context pattern to tune in T005):
  - Capitalized `\bSupervisor\b` anywhere outside fenced code and inline code spans, sentence start included (spec edge case) -> "supervisor (relation) or Orchestrator (rung)". Covers "aka Supervisor", "Supervisor rung", "Orchestrator / Supervisor".
  - `\balias(es)? [^.|]*\bOrchestrator\b` in a Lead context -> "Lead"
  - `\balias(es)? [^.|]*\b(Workhorse|Grunt)\b` in a Worker context -> "Worker"
  - `\bone rung up\b` -> "to your supervisor" or "one level up the chain"
  - `\bultra-tier\b`, `\bflash-tier\b` -> rung name
  - Owner as the human (for example `\b(the|alias) Owner\b`, `\bOwner\b` in a role list) -> "operator"; "code owner" and file-owner phrases pass
  - `\bInterlocutor\b` -> "CoS"
  - Driver as a role term (for example `\bDriver\b` in a role list or definition, "the Driver") -> "CoS"; lowercase "driver" and sentence-start "Driver" in plain English pass
  - `\b(frontier|cheap|mid)[- ]tier\b`, `\bTier\b` as a rung noun (for example "Tier: Executive") -> rung name; "Free Tier" and provider price tiers pass
- Line exemptions: lines inside fenced code blocks; inline code spans (for every pattern); table cells in the CONTEXT.md term-table "Retired aliases" column; lines carrying `<!-- terms: historical -->`.
- File allowlist: `CHANGELOG.md`, `docs/PLAN-MVP.md`, `docs/adr/**`, `docs/teach-me/**`, `docs/proposals/**`, `docs/governance/ASTRA-REVIEW-2.md`, `docs/governance/FREEZE-002.md`, `docs/governance/PLAN-BUILD-2.md`, `docs/governance/proof/**`, `build/**`, `dist/**`, `tests/fixtures/**`, `fixtures/**`, `skills/*/tests/**`. Fixture tests pass fixture paths explicitly.
- DECISIONS.md cutoff: the script reads `cutoff_decision` (number N of the D-041 entry) from `tools/retired_terms.json`; it splits `docs/DECISIONS.md` on `^## D(\d+)` headings and lints only entries with number >= cutoff.
- Unittest module: `tests/test_check_terms.py` with fixtures under `tests/fixtures/041/` (one seeded bad doc per pattern row, one good doc with generic English such as "primary driver", sentence-start "Driver", "code owner", "Free Tier", "a cheap check", "the supervisor verifies", one DECISIONS sample with synthetic entries D900 and D901 and cutoff 901), plus one test that runs the lint on the real tree and expects exit 0.
- CEO placement (SC-007) is a test assertion on DELEGATION-MODEL.md and CONTEXT.md rather than a lint pattern, since allowed places are structural. Path mentions such as `docs/governance/CEO-BRIEF.md` are exempt; other files are covered by review.

## Decision entry outline (D-041, number N reserved by T000)

Title: "One name per thing: role, rung and relation vocabulary (spec 041)". Status: proposed. The operator accepts or rejects it (T025); until then implement is not authorized beyond the reserved draft. Q2 and Q6 were answered by the CoS under operator delegation; the operator may veto them.

1. Two axes plus one relation: role (CEO, CoS, Lead, Worker), rung (Executive, Orchestrator, Workhorse, Grunt), relation (delegate, supervisor).
2. Supervisor retired as rung synonym and Lead alias; lowercase supervisor is the relation. Amends D34 (second bullet) and D46.4 (Lead aliases).
3. Worker loses Workhorse, Grunt, Team, Delegate aliases. Amends D46.4.
4. Delegate may hold no chain role (D78 native small edit).
5. operator in prose, CEO for chain position; Owner retired. Refines D46.4.
6. Rung definition states what rung decides and never grants. Refines D27 (rung bullet) and CONTEXT.md Rung.
7. Team reserved for D63; Chief noted as D63 label.
8. Legacy rung words and Driver retired; Host and Stdin worker scoped; ultra kept for effort and modes.
9. Chain-level phrases use "supervisor" or "one level up the chain", never "one rung up". Lint `tools/check_terms.py`, cutoff at this entry; historical records unchanged per AGENTS.md.
10. One data change: `agents_inc/governance.json` `name`. Prompt-wording changes listed: `header.md` lines 17, 19, 20; `slots.md` lines 47, 48; string literals in `render_dispatch.py:37`, `tests/test_dispatch_schema_131.py:252`, `example_slots.json:4`. No identifier renamed.
11. Rung rename to grade words weighed and rejected (cost 1731 matches).
12. Follow-ups: constitution P2, P3, P10; `~/.claude/AGENTS.md`; installed copy via repair; in-repo issue for user-visible code and pane strings.

## Rung and reviewer per kind of edit

| Kind | Author rung (model) | Reviewer | Reason |
|---|---|---|---|
| Lint script, fixtures, tests | Workhorse (sonnet) | Orchestrator same vendor (opus) allowed | routine code, D46.10 hard separation 2 |
| `governance.json` name value | Workhorse (sonnet) | same vendor allowed | routine data |
| Canon edits: CONTEXT.md, DELEGATION-MODEL.md, ROUTING-RANKING.md, DECISIONS.md, any SKILL.md, QUICKREF.md, header.md, AGENTS.md | Workhorse (sonnet) | Orchestrator, different vendor (sol) | canon edit, D46.10 hard separation 2 |
| Human docs: README.md, HOW-IT-WORKS.md, START-HERE.md, pane README | Workhorse (sonnet) | different vendor (sol), batched with canon review | prose touches canon terms |
| Gate runs, acceptance | Lead (opus) then CoS | n/a | P3 |

## Order of work

0. Reserve the decision number N (T000).
1. Lint config and tests first (fixtures fail as expected; real-tree test expected to fail until edits land and is marked as the final gate).
2. Lint script until fixture tests pass.
3. CONTEXT.md term table and row rewrites (all later edits cite it).
4. DELEGATION-MODEL.md and ROUTING-RANKING.md.
5. Skill files and prompt header in parallel with human docs.
6. governance.json name value.
7. DECISIONS.md entry as proposed, then set `cutoff_decision` to N.
8. Real-tree lint test plus full suite; cross-vendor review; CoS verification.
9. Ask the operator to accept the proposed D-041 entry (T025).

## Risks

- Over-matching: patterns flag generic English. Mitigation: good-text fixture with known generic phrases; patterns are contextual.
- Under-matching: a retired alias in a new phrasing slips past. Accepted; review remains the second line.
- Header change in `skills/workerbee/header.md` alters every rendered prompt. Mitigation: run `check_dispatch_prompt.py` on a rendered sample (T012) and the render tests.
- DECISIONS number collision if another entry lands first. Mitigation: T000 reserves N; T020 confirms it is still free.
- Installed copies keep old wording until `agents-inc repair`. Documented as follow-up.
- Ruling Q1 keeps a word with a rung history; readers of pre-cutoff entries will still see "Supervisor rung". Accepted per Q4.

## Complexity Tracking

None. No new dependency, no schema change.
