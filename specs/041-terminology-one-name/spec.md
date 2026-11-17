<!-- provenance: author=domattioli model=opus effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=spec041-lead -->
# Feature Specification: Terminology, one name per thing

**Feature Branch**: `041-terminology-one-name`
**Created**: 2026-11-15
**Status**: Clarified
**Input**: CoS dispatch: "the hierarchy vocabulary mixes two axes and keeps many aliases"; make each thing in the agents-inc hierarchy carry one canonical name, retire the aliases, and stop them coming back.

Evidence for every count below is in `inventory.md` in this directory.

## Problem

The agents-inc vocabulary describes two separate things with overlapping words:

- the **role axis**: where an agent sits in the reporting chain (who dispatches it, who it reports to);
- the **rung axis**: which model class it runs on (cost and capability).

Today one word can name a rung, a role and a generic verifier at once. "Orchestrator" is a rung and an alias for Lead (CONTEXT.md:31-32). "Supervisor" is an alias for Lead, a synonym for the Orchestrator rung (CONTEXT.md:48, D34) and the generic verifier ("A Supervisor compares both outputs", CONTEXT.md:49). "Worker" lists the rung names Workhorse and Grunt as aliases (CONTEXT.md:10) while DELEGATION-MODEL.md says a rung is never a role. Readers, delegates and the live view cannot tell which axis a sentence means.

## Clarifications

### Session 2026-11-15

Answers given by the CoS. Q2 and Q6 were answered by the CoS under operator delegation; the operator may veto them later.

- Q1: Relational word for the party that dispatched a delegate and verifies its return? A: "supervisor", in this sense only, written lowercase in prose to mark a relation, not a title. It matches the rendered `SUPERVISOR` prompt slot, carries the verify duty, and avoids a collision with the dispatch broker and `agents-inc dispatch`. Dispatcher is not canon; existing uses that mean this relation become supervisor. (CoS)
- Q2: Canonical name for the human? A: "operator" in prose; "CEO" only where the text names the chain position (chain figure, role table, the CONTEXT.md CEO entry, and the fixed pair "CEO and CoS"). Owner is retired. (CoS under operator delegation; operator may veto)
- Q3: Lint shape? A: word list plus context patterns, `.md` files only, file allowlist for historical records. (CoS)
- Q4: `docs/DECISIONS.md` treatment? A: entries before the new 041 decision entry are allowlisted; that entry and later ones are linted, using a heading-number cutoff. (CoS)
- Q5: `agents_inc/governance.json` agent `agent-supervisor-01`? A: change only `name` (drop "Orchestrator"); keep `id` and `type`. Type `supervisor` now matches the relational sense. Check tests for name asserts first. (CoS)
- Q6: Rename rungs to grade words? A: no. Keep Executive, Orchestrator, Workhorse, Grunt; the costed alternative below stays as the record. (CoS under operator delegation; operator may veto)
- Q7: Scope of "ultra"? A: reserved for effort and named modes (caveman ultra, `CODEX_BRIDGE_MODE=ultra`); banned only as a rung adjective ("ultra-tier"). (CoS)
- Q8: Driver, Host, Stdin worker? A: retire Driver, scope Host to "the agent CLI", scope Stdin worker to the MVP adapter path. Plain-English "driver" (for example "primary driver") is not the retired term and the lint must not flag it. (CoS)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reader can tell role from rung in any sentence (Priority: P1)

An operator or a delegate reads CONTEXT.md, DELEGATION-MODEL.md, QUICKREF.md or a dispatch prompt and can tell, from the word alone, whether it names a place in the reporting chain, a model class, or a relation.

**Why this priority**: Every other story depends on the canonical table. The current overlap produces prompts that say "Orchestrator" without saying whether they mean opus or the Lead.

**Independent Test**: For each role, rung and relation word in the canonical table, confirm it appears on exactly one axis in CONTEXT.md and DELEGATION-MODEL.md.

**Acceptance Scenarios**:

1. **Given** the updated CONTEXT.md, **When** a reader looks up "Orchestrator", **Then** the entry defines a rung only, names no role alias, and describes no role behavior.
2. **Given** the updated CONTEXT.md, **When** a reader looks up "Lead" or "Worker", **Then** the entry lists no rung word as an alias.
3. **Given** a rendered dispatch prompt, **When** its `REPORTING CHAIN` line names the supervisor, **Then** prose elsewhere uses lowercase "supervisor" for the same relation.

---

### User Story 2 - Retired words stay retired (Priority: P1)

A maintainer edits a current doc and uses a retired alias. A deterministic check fails and names the word, the file, the line and the canonical replacement.

**Why this priority**: D34 and D46 renamed terms once; the aliases survived because nothing checks for them.

**Independent Test**: Insert a retired alias in a fixture copy of a current doc; the lint exits non-zero. The same word in a pre-cutoff `docs/DECISIONS.md` entry passes.

**Acceptance Scenarios**:

1. **Given** a current doc containing "aka Supervisor" or "Supervisor rung", **When** the lint runs, **Then** it exits non-zero and prints file, line, word and replacement.
2. **Given** lowercase "the supervisor verifies", **When** the lint runs, **Then** it passes.
3. **Given** a historical record on the allowlist, **When** it contains a retired alias, **Then** the lint ignores it.
4. **Given** "primary driver" or "a cheap check" in prose, **When** the lint runs, **Then** it passes.

---

### User Story 3 - Definitions say what a word does and does not grant (Priority: P2)

The Rung, Executive, Chief of Staff and Delegate entries say plainly what they decide and what they never grant.

**Why this priority**: CONTEXT.md:48 calls a rung "a cost and capability class only" while the same entry assigns default duties by rung (D78), and the ladder picks the Lead by rung (D46.2).

**Independent Test**: Each rewritten entry has a "decides" clause and a "never grants" clause, each with a decision citation.

**Acceptance Scenarios**:

1. **Given** the Rung entry, **When** read, **Then** it states that rung sets ladder order for Lead choice (D46.2), delegation rights (D46.3) and default duties (D78, D80), and grants no Task Authority.
2. **Given** the Chief of Staff entry, **When** read, **Then** its first sentence states it is the only agent that dispatches the Lead, verifies before relay, and commits or pushes.

---

### User Story 4 - One name for the human (Priority: P2)

Current docs call the human "operator" in prose and "CEO" only for the chain position.

**Independent Test**: Grep current docs for "Owner" and for CEO outside the allowed places; zero hits remain.

**Acceptance Scenarios**:

1. **Given** the current docs, **When** grepped for "Owner" in the human sense, **Then** zero hits remain.
2. **Given** DELEGATION-MODEL.md, **When** read, **Then** CEO appears in the chain figure, role table and "CEO and CoS" pair only.

---

### User Story 5 - Legacy and orphan words cleaned up (Priority: P3)

Legacy rung words leave current prose where they mean a rung; Driver is retired; Host and Stdin worker are scoped; Guest agent is placed relative to the chain in one sentence in DELEGATION-MODEL.md.

**Independent Test**: Grep current docs for `ultra-tier` and `flash-tier`: zero hits. DELEGATION-MODEL.md contains a Guest agent sentence.

**Acceptance Scenarios**:

1. **Given** `skills/workerbee/SKILL.md`, **When** grepped for "ultra-tier", **Then** zero hits remain (3 today).
2. **Given** `docs/BENCH.md`, **When** it says "cheap" about provider pricing, **Then** the word stays.

### Edge Cases

- Generic English: "lead to", "the user", "delegate this task", "a cheap check", "primary driver" are not term uses. The lint matches context patterns, never a bare-word ban on Worker, Delegate, user, cheap, tier or driver.
- A delegate with no chain role: under D78 the CoS sends an edit of 3 tool calls or fewer to a native workhorse subagent that reports to the CoS, with no Lead. It is a delegate but neither Lead nor Worker; its supervisor is the CoS. The Worker definition must not claim every non-Lead delegate.
- Nested Leads: a Lead dispatched through the broker by another Lead (D51). Its supervisor is the dispatching Lead.
- Supervisor capitalized at sentence start in the relational sense ("Supervisor runs the check.") reads like a title. The lint flags every capitalized "Supervisor" outside fenced code and inline code spans; writers rephrase so the sentence does not start with it.
- Code identifiers that carry these words: `SUPERVISOR` and `EXECUTIVE` slots in `render_dispatch.py:259-299`, `agent-supervisor-01` and type `supervisor` in `agents_inc/governance.json:24-26`, the `tier` field and SQLite CHECK (D36), D80 settings keys (`executive_judgment_only`, `write_rung`). These stay. Only the governance.json `name` value changes.
- `docs/DECISIONS.md` is append-only and mixes history with live rulings. Entries before the 041 entry keep old words; the 041 entry and later ones use canonical words.
- "ultra" names an effort level, a caveman level and `CODEX_BRIDGE_MODE=ultra`. Only "ultra-tier" is banned.
- Static `docs/assets/delegation-model.png` and `.svg` carry old labels. The lint scans `.md` only, and skips fenced code and inline code spans for every pattern.
- Test fixtures (`tests/fixtures/**`, `fixtures/**`, `skills/*/tests/**`) are tracked `.md` files with seeded aliases; they are on the allowlist and tests pass their paths explicitly.
- "Dispatcher" in a component sense ("gateway/dispatcher", `docs/governance/CEO-BRIEF.md:15`) is not the relation and stays.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: CONTEXT.md MUST contain one canonical term table with columns term, axis (role, rung, relation, human, other), definition, retired aliases. Each retired alias appears in exactly one row and is marked `lint` or `review-only`.
- **FR-002**: The role axis MUST be CEO, CoS (Chief of Staff), Lead, Worker. Delegate MUST be defined as "any agent reached by dispatch"; a delegate is usually a Lead or a Worker but may hold neither role (D78 native small-edit subagent). Delegate MUST be removed from the Worker alias list.
- **FR-003**: Lead MUST lose the aliases Supervisor and Orchestrator. Worker MUST lose the aliases Workhorse, Grunt and Team, and MUST be defined as an agent dispatched by a Lead that reports to that Lead, not as every non-Lead agent.
- **FR-004**: The rung axis MUST keep Executive, Orchestrator, Workhorse, Grunt (code enums since D36). Supervisor MUST be retired as a rung synonym, amending D34.
- **FR-005**: The relational word MUST be lowercase "supervisor": the party that dispatched a given delegate and verifies its return. It is never a title, rung or role. Existing current-doc uses of "dispatcher" in this relational sense (for example `skills/workerbee/header.md:20`, `skills/workerbee/SKILL.md:634`) MUST become "supervisor". Component uses of "dispatcher" stay. Chain-level phrases MUST say "to your supervisor" or "one level up the chain", never "one rung up" (for example `skills/workerbee/QUICKREF.md:55`, `skills/workerbee/SKILL.md:943`, `skills/workerbee/header.md:19`).
- **FR-006**: The Rung definition MUST state what a rung decides (ladder order for Lead choice D46.2, delegation rights D46.3, default duties D78 as overridden by D80) and what it never grants (Task Authority, special access). The phrase "cost and capability class only" MUST go.
- **FR-007**: The Chief of Staff definition MUST open with its gate function: the only dispatcher of the Lead, the verifier before relay, the only committer and pusher.
- **FR-008**: The human MUST be "operator" in current-doc prose. "CEO" MUST appear only for the chain position: the chain figure, the role table, the CONTEXT.md CEO entry, and the fixed pair "CEO and CoS". The term table MUST state this rule in one sentence. Owner MUST be retired.
- **FR-009**: Team MUST be reserved for the D63 session sense. Chief MUST get its own row as the D63 (proposed) live-view label for a team's CoS, not a new role.
- **FR-010**: "ultra-tier" and "flash-tier" MUST be removed from current docs. tier, frontier, cheap and mid MUST be removed from current docs only where they name a rung. "ultra" keeps its effort, caveman and `CODEX_BRIDGE_MODE` senses and MUST NOT be used for a rung.
- **FR-011**: Driver MUST be retired: the CONTEXT.md:8 row is removed and Driver is listed as a retired alias in the CoS row. Host MUST be scoped to "the agent CLI the user runs". Stdin worker MUST be scoped to the MVP stdin adapter path. Plain-English "driver" is not the term.
- **FR-012**: DELEGATION-MODEL.md MUST state in one place that a Guest agent sits outside the reporting chain: started by the operator, not dispatched, reports to no Lead.
- **FR-013**: A deterministic lint MUST fail on a retired alias in a current `.md` doc, print file, line, word and replacement, and pass on allowlisted historical records (pre-cutoff `docs/DECISIONS.md` entries, `CHANGELOG.md`, `docs/PLAN-MVP.md`, `docs/adr/`, `docs/teach-me/`, `docs/proposals/`, dated governance reviews). It MUST run in the existing unittest suite.
- **FR-014**: The rulings MUST be recorded as one new entry in `docs/DECISIONS.md`, referred to as D-041 (number N, the next free number reserved at the start of implement), with status "proposed" until the operator accepts it. It names the decisions it amends (D34, D46.4, D27 (rung bullet)), records Q2 and Q6 as CoS rulings under operator delegation, and lists every prompt-wording change.
- **FR-015**: No code enum, JSON key, SQLite value, CLI flag, settings key or env var MAY be renamed. Allowed data and string changes: the `name` value of `agent-supervisor-01` in `agents_inc/governance.json` (drop "Orchestrator"), made only after confirming no test asserts the old name; and prompt-text string literals that render into dispatch prompts (FR-016).
- **FR-016**: The change MUST NOT alter delegation behavior, gates, fan-out numbers or routing, and MUST NOT change any identifier or logic. Prompt-text string literals are prose and may change (`skills/workerbee/scripts/render_dispatch.py`, `tests/test_dispatch_schema_131.py`, `skills/workerbee/tests/fixtures/example_slots.json`); each such change is listed in the D-041 entry.
- **FR-017**: Rung entries MUST NOT describe role behavior. The CONTEXT.md:31 sentence "An agent using this rung dispatches children and roots a family tree. Depth rules count from the dispatching agent." MUST move: dispatching and depth to the Lead entry (and D46.3 delegation-by-rung text), family rooting to the Family entry.
- **FR-018**: One section of this spec MUST list follow-ups: out-of-repo items, and the in-repo issue for user-visible code and pane strings. This feature edits none of them.

### Key Entities

- **Canonical term**: a word with one axis, one definition, a list of retired aliases and the decision that set it.
- **Retired alias**: a word or pattern banned from new text in current docs, mapped to one canonical replacement.
- **Historical surface**: a file or file region on the lint allowlist where old words stay (AGENTS.md: "Old names in historical documents stay unchanged").

### Canonical term table

Rule for the human: write "operator" in prose; write "CEO" only when naming the chain position (chain figure, role table, the CEO entry, the pair "CEO and CoS").

| Term | Axis | Definition | Retired aliases (check) |
|---|---|---|---|
| CEO | role (human) | The chain position held by the operator; fixed noun with CoS (D46.4). | Owner (lint) |
| operator | human | The human who owns the work and rules on decisions. The prose name for the CEO. | user in the role sense (review-only) |
| Chief of Staff (CoS) | role | The agent the operator talks to. Only dispatcher of the Lead, verifies every report before relay, only committer and pusher (D43, D46). | Interlocutor (lint); Driver (lint; plain-English "driver" unaffected) |
| Lead | role | The one agent the CoS dispatches for a mandate; runs the mandate, may dispatch Workers within FAN_OUT and depth rules, reports once at mandate end (D46, D48). | Orchestrator as a Lead alias (lint) |
| Worker | role | An agent dispatched by a Lead that reports to that Lead (D46). | Workhorse, Grunt as Worker aliases (lint); Team as Worker collective (review-only); Delegate as Worker alias (review-only) |
| Delegate | relation | Any agent reached by dispatch. Usually a Lead or Worker; a D78 native small-edit subagent is a delegate with neither role. Not a Guest agent or consult. | none |
| supervisor | relation | Lowercase. The party that dispatched a given delegate and verifies its return: the CoS or a Lead. Never a title, rung or role. | Supervisor (capitalized: former Lead alias and Orchestrator-rung synonym) (lint); Dispatcher in the relational sense (review-only); "one rung up" as a chain step (lint) |
| Executive | rung | Top model class (fable, astra). Default duty judgment only (D78.2, D80). | frontier as a rung name, ultra-tier (lint) |
| Orchestrator | rung | Second class (opus, sol). Default duty design and scope judgment, review, gates (D78.1). | none |
| Workhorse | rung | Third class (sonnet, terra). Default writer (D78.1). | none |
| Grunt | rung | Fourth class (haiku, luna). Read-only by default (D78.1). | cheap as a rung name, flash-tier (lint) |
| Rung | rung | A model class. Sets ladder order for Lead choice, delegation rights and default duties; never grants Task Authority or special access. | Tier as a rung noun, mid as a rung name (lint) |
| Family | other | One dispatching node and every node below it (D27). Short form "fam" is kept. | none |
| Team | other | Proposed (D63): one session and the delegates and Syncs it started. | none (the Worker-collective sense is retired in the Worker row) |
| Chief | other | Proposed (D63): live-view label for a team's CoS. Not a new role. | none |
| Guest agent | other | An operator-started agent outside the reporting chain. | none |
| Host | other | The agent CLI the user runs (Claude Code, Codex). | none |
| Stdin worker | other | MVP adapter path: a model call that reads stdin and returns a candidate, no tools. | none |

Check values: "lint" means `tools/retired_terms.json` carries at least one context pattern for the alias; "review-only" means no reliable pattern exists and review catches it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In current docs, hits for Supervisor and Orchestrator as Lead aliases or Supervisor as a rung synonym drop to 0 (baseline: CONTEXT.md:31, 32, 48; DELEGATION-MODEL.md Roles; ROUTING-RANKING.md rung table "Orchestrator / Supervisor").
- **SC-002**: "ultra-tier" and "flash-tier" current-doc hits drop from 8 to 0; "Owner" human-sense hits drop from 2 to 0; Interlocutor and Driver appear in current docs only in the CoS row retired-alias column; no Driver or Tier row exists.
- **SC-003**: Each retired alias appears in exactly one row of the canonical table, checked by a unit test that parses the table.
- **SC-004**: The lint fails on at least one seeded retired alias per row in a fixture, passes on the real tree after the edits, and the full test suite stays green.
- **SC-005**: Zero renamed code identifiers; `git diff` on code files outside `agents_inc/governance.json` shows no identifier change, and in that file only the `name` value of `agent-supervisor-01` changes.
- **SC-006**: DELEGATION-MODEL.md Guest agent hits go from 0 to at least 1.
- **SC-007**: In CONTEXT.md and DELEGATION-MODEL.md, CEO hits outside the allowed places drop to 0 (baseline 46 current-doc CEO hits, most in DELEGATION-MODEL.md). Path mentions such as `docs/governance/CEO-BRIEF.md` are exempt; that file is not renamed. Other files are covered by review, not by this test.
- **SC-008**: The CONTEXT.md Orchestrator entry contains no "dispatches" or "family" wording.

## Assumptions

- Historical surfaces: entries before the 041 entry in `docs/DECISIONS.md`, `CHANGELOG.md`, `docs/PLAN-MVP.md`, `docs/adr/`, `docs/teach-me/`, `docs/proposals/`, `docs/governance/{ASTRA-REVIEW-2,FREEZE-002,PLAN-BUILD-2}.md`, `docs/governance/proof/`.
- The lint scans `.md` files only. Code comments, docstrings and user-visible code strings are not swept in this feature (see follow-ups).
- The D-041 decision takes number N, reserved as the first implement task; the newest entry today is D82.
- Canon edits ship through the Lead and Worker pipeline with a different-vendor reviewer (D46.10, hard separation 2).

## Follow-ups

Follow-ups only; this feature edits none of them.

- In repo: user-visible strings in code and the live pane (`.py`, `.ts`, for example `mods/delegate-pane/hooks/rungs.ts`, `frames.ts`) that carry retired words get their own issue.

- DomI `specs/consumers/agents-inc/memory/constitution.md` P2 ("Orchestrator (aka Supervisor)"), P3 and P10 wording: amend after the 041 decision lands, with a constitution version bump.
- Machine-level `~/.claude/AGENTS.md` (uses "Executive", "orchestrator" in rung lists): check wording after the 041 decision.
- Installed copy under `~/.local/share/agents-inc/current`: refreshed by `agents-inc repair`, never edited by hand.

## Alternative weighed: grade words for rungs (rejected, Q6)

Rename rungs to words with no role meaning (for example grade 1 to 4), as corporations separate level from role.

- Benefit: removes the Orchestrator collision at the root.
- Cost from the inventory: 306 (Orchestrator) + 345 (Executive) + 387 (Workhorse) + 693 (Grunt) = 1731 matches; about 1015 in code and tests, including `tests/fixtures/012/router_golden.json`, `agents_inc/models.json`, the SQLite `tier` CHECK, D80 settings keys and values, and `mods/delegate-pane/hooks/rungs.ts`. Needs a data migration for ledger and settings, against P-e.
- Ruling: not adopted (Q6, CoS under operator delegation). Collisions are fixed in prose.

## Out of Scope

- checklist, analyze, implement in this spec turn.
- Renaming the product, the workerbee skill, the `workerbees` shim or `WORKERBEES_*` env vars.
- Changing delegation behavior, gates, fan-out numbers or routing.
- Regenerating `docs/assets/delegation-model.png` or `.svg`.
