---
description: "Project constitution — agents_for_dummies"
version: 1.9.2
status: proposed
ratified: false
last_amended: 2026-10-25
---
<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-09-24 skill=speckit-pipeline repo=agents_Inc session=unknown -->

# Constitution: agents_for_dummies

Machine-facing. Caveman ultra. Binding rules only; canon lives elsewhere and is cross-referenced, never restated (see P0).

Sources synthesized: `CONTEXT.md` (glossary), `docs/DECISIONS.md` (rulings, truth-source #2), `docs/governance/ASSESSMENT.md` + `CEO-BRIEF.md` (control plane, objective), `docs/governance/ROUTING-RANKING.md` (ladder), root `AGENTS.md` (session rules).

Truth-source order (from `AGENTS.md` § Project canon): CONTEXT.md > docs/DECISIONS.md > docs/governance/. DECISIONS amends, never retracts; on conflict DECISIONS wins. This constitution ranks BELOW all three — it restates none of them and yields to any of them.

## P0 — Cross-reference, never duplicate (MUST)

Constitution states a principle + names its canonical file. No rule text is copied here. Conflict between this file and canon = canon wins, and this file gets fixed. Resolves skeleton open-question 1.

## P1 — Repo-scoped writes (MUST)

Delegates (any rung, any vendor, incl. free grunts) write only inside dispatching repo working tree. Never `~/.claude/**`, never other repos, never credentials/`.env`. Reading `.env` or printing key material: forbidden at every rung (`AGENTS.md` § Project rules; CEO-BRIEF security reqs — secrets never in model context). Key never enters any model prompt (D2).

## P2 — Labor ladder (MUST)

4 rungs, claude↔codex pairs: Executive fable↔astra; Orchestrator (aka Supervisor) opus↔sol; Workhorse sonnet↔terra; Grunt haiku↔luna. Renamed 2026-09-07 (D34): top rung was Supervisor, now Executive; Orchestrator gained Supervisor as a synonym, same rung. Escalate one rung up same vendor; second opinion across the pair, blind; reviewer at a rung = that rung's pair = that rung's fallback. Sonnet/terra build only via promotion. Promotion triggers: two failed checks ("failed check" defined once in `AGENTS.md` § Project rules), provider quota pause, or Lead assigns w/ gate reason — never worker confidence. Only Executive + Orchestrator rungs have children. Canon: `AGENTS.md` § Project rules + `docs/DECISIONS.md` D27 + `docs/governance/ROUTING-RANKING.md` + `CONTEXT.md` (Rung / Run spec / Derivation / Modality). Operator instruction overrides. Delegation/support flow figure (roles × phases, Mermaid): `docs/governance/DELEGATION-MODEL.md`.

## P3 — No self-graded gates (MUST)

Delegate's own GREEN/PASS/LGTM is not evidence. Executive re-runs the check itself before accepting. Procedure of record: `skills/workerbee/SKILL.md` Step 2. Corollary from CEO-BRIEF: gateway permission is never a claim about output quality; `verified` requires verifier + reviewer gates (`CONTEXT.md`). No self-approval.

## P4 — Deterministic policy over prompt (MUST)

Model may propose a route/delegation; deterministic runtime policy approves or rejects. Never rely on prompt alone for security, permissions, topology, comms. Fail closed on unknown agent/capability/schema/missing decision. Canon: `docs/governance/CEO-BRIEF.md` core principle + security requirements; `docs/governance/ASSESSMENT.md` gateway row.

## P5 — Hard $0 per task (MUST)

Zero incremental dollars. Quota exhaustion pauses job + tells user; no paid API path. Free grunts = $0 only, never a Codex subscription call. No savings % claimed until measured on both acceptance workflows. Canon: D9, D10, `CONTEXT.md` (Free / Spend cap / Free grunt).

## P6 — Audience-scoped doc rendering (MUST)

Human-facing repo docs: caveman lite + nested-notes + write-like-scientist. Agent/machine-facing docs (skill bodies, dispatch specs, this file): caveman ultra, prose, no structure overhead. Table of record: root `AGENTS.md` § Documentation style (= D14).

## P7 — Nickname discipline (MUST)

astra / sol / terra / luna are OpenAI Codex-account model codenames reached via the codex host. They are NOT Claude `Agent`-tool subagent models and must never be passed where a Claude model id is expected. Claude-side ids: fable, opus, sonnet, haiku. Roster is runtime-verified (`skills/workerbee/SKILL.md` Step 1a/1b) — never trust a stale table; ChatGPT-account Codex rejects several plausible-looking ids (DECISIONS "Codex model IDs 2026-09-05"). Never fabricate model capability. Amended 2026-10-24 (MINOR, operator-approved, spec 028 Q4, `docs/DECISIONS.md` D69): luna is also reachable as the native Claude Code subagent type `agents-inc:luna`. The mod answers each step through the codex host, so the nickname rule holds: the type name is `agents-inc:luna`, luna is never passed where a Claude model id is expected, and the type's placeholder model (`haiku`) is never called for a luna step.

## P8 — Delegation prompt contract (MUST)

Every dispatch prompt, any rung, any vendor, carries the 14-element contract. Elements 10 (second-opinion / wheel-spin justification, paid vendors only) and 11 (plan contract) are conditional and satisfied by an explicit N/A line when unmet; the other ten are unconditional [SUPERSEDED in part by D42, 2026-09-18: element 1 (caveman) is now CONDITIONAL, see below; nine remain unconditional]. Element 1 (D42): if the caveman skill is installed, invoke it; if absent, emit `caveman NOT installed -> checked by hand` and continue. The same conditional applies to the handoff-lint gate (D41). The in-repo `check_dispatch_prompt.py` check stays mandatory, unconditional. Element 9 (effort) on the Claude `Agent`-tool transport = state that effort control is unavailable + intended level. Element 10's trigger is the P2 promotion trigger, defined once ("Failed check — definition of record"). Canon, full list + exact wording: `skills/workerbee/SKILL.md` Step 11; template + per-element rationale: `skills/workerbee/SKILL.md` Step 11. Not restated here (P0). Scope (spec 028 Q5, D69): the contract does not bind a call to the `agents-inc:luna` type; it binds every other dispatch, Claude `Agent`-tool calls included. P3 holds for a luna call through the parent's verification. Authority: `docs/DECISIONS.md` D29 (effort default, element 9); broader contract ratified by operator 2026-09-06, grilled + expanded same date; consistency pass same date (fable final say); element-1 conditionality authorized by `docs/DECISIONS.md` D42 (operator sign-off 2026-09-18).

## P9 — Edit hygiene: surgical over full-rewrite (MUST)

Minimize tokens spent editing files, all else equal. Default to a surgical/targeted edit over rewriting a whole existing file, whenever the end result is unaffected either way. Full-rewrite is fine when it genuinely IS the smaller/clearer diff (e.g. the file is short, or nearly everything changes) — the rule is "don't rewrite when a smaller edit gets the identical result," not "never rewrite." Applies to every rung, every vendor. Canon + template wording: `skills/workerbee/SKILL.md` Step 11 MUST 13; `skills/workerbee/SKILL.md` Step 11. Authority: `docs/DECISIONS.md` D30.

## P10 — Lesson-learned handling: relay up, never sideways (MUST)

A delegate finding with canon-doc implications is tagged `LESSON-CANDIDATE`, relayed exactly one rung up at a time (never skipped, never filed sideways as an issue), scout-checked for duplication/contradiction before it reaches Executive, and only Executive presents a survivor to the operator — concise, evidenced, one target canon file named. Executive may land small/minor fixes itself; material changes need operator sign-off (same bar as amending `AGENTS.md`/this file). Executive MAY delete a prose rule once a landed test enforces the same rule, and MUST cite that specific test plus its green result when doing so — authority without the evidence cite does not satisfy this clause. Canon + exact template: `skills/workerbee/SKILL.md` Step 11 MUST 14; `skills/workerbee/SKILL.md` Step 11. Authority: `docs/DECISIONS.md` D31 (lesson-routing half: explicitly rejected a GitHub-issue-intake alternative); delete-on-test-coverage clause authorized by D32 (2026-09-06); D31 covers only the lesson-relay half.

## Enforcement

`speckit-analyze` reads this file for MUST-violations. Until operator ratification (`ratified: true` in frontmatter, set only by operator sign-off), violations of P0–P10 report as **WARN**, not CRITICAL. Rationale: an unratified file must not hard-block a build. Resolves skeleton open-question 2 by default — **NEEDS-OPERATOR** to confirm the default and flip `ratified`.

## Amendment

Semver on `version`. PATCH = wording/cross-ref fix. MINOR = new principle or materially widened scope. MAJOR = a principle removed or its meaning reversed. Every amendment: bump `version`, set `last_amended`, cite the `docs/DECISIONS.md` D-number that authorizes it. Constitution amends, never retracts — a superseded principle is marked superseded in place, not deleted. Operator sign-off or CEO directive required (same bar as `AGENTS.md`). Resolves skeleton open-question 3.

## Still open — NEEDS-OPERATOR

1. Ratification: flip `ratified: true` + confirm WARN-vs-CRITICAL default above.
2. `docs/governance/CEO-BRIEF.md` "Operator constraints for THIS repo" (2026-09-05: free/cheapest models write, luna reviews w/ sonnet fallback, no frontier at build time except astra planning) predates D27's ladder. Read here as the budget-modality instance of P2, not a competing rule. Operator to confirm that reading or restate the brief.
