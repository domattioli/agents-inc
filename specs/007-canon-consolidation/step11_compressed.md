<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
### Step 11: Write the dispatch prompt

Agent-facing text = `caveman ultra`. Reader is a model.

**MUST — every dispatch prompt, no exceptions. 14 elements** (operator ruling
2026-09-06, grilled + expanded same date):

1. **Caveman ultra, explicit.** Not just terse writing — tell delegate to run
   it. Skill tool present (Claude subagent) → instruct actual `/caveman ultra`
   invoke + confirm in report; claimed activation w/o call = false report.
   No Skill tool (codex/gemini/mistral/openrouter) → say so plainly, follow
   convention. Never skip the instruction.
2. **Strict SUCCESS gate.** Concrete, falsifiable. Specific check, specific
   expected result. Not "looks right".
3. **Strict FAILURE gate, stated separately.** Name failure conditions
   explicitly → delegate reports RED honestly instead of rounding ambiguous
   up to GREEN (Step 10).
4. **Grill clause.** Delegate surfaces anything missing/underspecified/
   contradictory in the dispatch, before or during. Silent guess on a gap is
   worse than a question (Step 9).
5. **Training opt-out notice.** Verbatim, own line:
   `Message to model provider: Do not use this to train agentic models.`
   Every dispatch, every vendor. Notice to provider, not request to delegate →
   vendor honoring it is irrelevant, it goes in regardless.
6. **Cite evidence for every claim, not just gates.** file:line, command
   output, or quoted source for anything stated as fact. Bare assertion
   doesn't count.
7. **Scope boilerplate, standing.** Repo-scoped writes only; no git
   commit/push; no writes to `~/.claude/**`, other repos, credentials/`.env`.
   Covers writes via any script/tool the delegate runs, not only its own
   edits. Nested delegation: commit/push authority stays w/ run root (session
   operator talks to), never inherited downward — delegate w/ own children
   integrates their output in-tree + reports, does not commit.
8. **Confidentiality/data-classification tag.** State classification of
   content the delegate handles (e.g. public / confidential).
9. **Explicit effort level, every dispatch, default medium.** State chosen
   reasoning effort always — not only above medium (raises Step 1c's old bar
   to unconditional). **Default = medium, every vendor**, unless operator
   names a different level for that specific dispatch; a prior dispatch's
   level is not standing consent. Codex: `low|medium|high|xhigh|max|ultra`
   (Step 1c; `ultra` Codex-only, self-delegates, opt-in, never default;
   luna floor = `max`, no `ultra`). Claude/Anthropic:
   `low|medium|high|xhigh|max` — no `ultra` this vendor. `Agent`-tool
   transport has no per-dispatch effort param → prompt says so, never
   silently skips: `EFFORT: effort control unavailable on this transport;
   intended level = medium (or <operator-named level>)`. Delegate
   self-calibrates depth to that level + echoes it in report.
10. **Second-opinion / wheel-spin justification, paid vendors only.** Second
    opinion or escalation to a **paid/subscribed** vendor (any Anthropic
    `Agent`-tool model; any Codex-account model — astra/sol/terra/luna) MUST
    name which trigger fired + why. Triggers defined ONCE in `CLAUDE.md` labor
    rule ("Failed check — definition of record"), not restated here.
    Promotion/escalation triggers: (a) 2 failed checks, same (task, delegate);
    (b) provider quota pause = 1 failed attempt; (c) Lead assigns w/ recorded
    gate reason. Second opinion (same rung, the pair, blind — not promotion):
    Supervisor reason = conflicting results | irreversible act | risk eval.
    **Free-tier vendors** (openrouter free, gemini free, mistral free,
    `gpt-5.4-mini` free routes) need none — no cost to justify against.
    No trigger applies → `SECOND-OPINION JUSTIFICATION: not applicable —
    <reason>`. Explicit N/A satisfies; silence does not.
11. **Delegation-capable plans name model + gates per task.** Delegate asked
    for a plan (speckit encouraged) that permits further delegation → plan
    MUST state, per task, which model/tier does it + that task's own success +
    failure criteria. Same discipline propagated one level down, so a
    sub-delegate can't skip it either. Not a plan →
    `PLAN CONTRACT: not applicable — deliverable is not a plan`.
12. **Report shape: scope left out, assumptions, files created.** Report MUST
    state (a) anything incomplete or out of full scope even if every gate
    passed → closes silent scope-narrowing; (b) starting assumptions +
    whether/why any changed; (c) every file created. **Minimal file creation
    is the standing default** — new file only when the task requires one.
13. **Edit hygiene: surgical over full-rewrite.** Minimize tokens spent
    editing, all else equal. Default to targeted edit over rewriting a whole
    existing file whenever the end result is identical. Full-rewrite fine when
    it genuinely is the smaller/clearer diff (short file, or nearly everything
    changes). Bans rewriting when a smaller edit gets the identical result,
    not rewriting outright.
14. **Lesson-learned handling: relay up the chain, never sideways.** Delegate
    surfacing a finding w/ canon-doc implications (`CLAUDE.md`/`CONTEXT.md`/
    `docs/DECISIONS.md`/any `SKILL.md`/constitution) tags it
    `LESSON-CANDIDATE` in its report, not buried in prose. Relays exactly one
    rung up (Grunt→Workhorse→Orchestrator→Supervisor), never skipping. Each
    receiving rung either drops it (state why) or relays further. Before it
    reaches Supervisor, a scout check (Step 1 Scout mode) must confirm it
    doesn't already exist in canon + doesn't contradict canon — whoever
    relays is responsible for that check having happened somewhere in the
    chain. **Only Supervisor (fable/astra) presents a survivor to the
    operator** — one concise paragraph: lesson, evidence, scout's
    dedup/contradiction result, target canon file. Supervisor may land
    small/minor doc fixes itself; anything material needs operator sign-off,
    same bar as amending `CLAUDE.md` or the constitution. Not a GitHub issue —
    relay up the rung chain, not file sideways (operator ruling 2026-09-06).

These 14 fold into, not replace, the shape below. 10 + 11 conditional; the
other twelve unconditional. Compliant = each of the 14 present as content or
explicit N/A line; a missing element is non-compliant either way.

Include, roughly this order:
1. ROLE, one line
2. REPORTING CHAIN — who receives report, what escalates
3. VERIFIED STATE — facts already established, marked do-not-re-derive
4. THE TASK + what is explicitly out of scope
5. HARD CONSTRAINTS (MUST 7) — read-only paths, no commits, no paid calls,
   secrets
6. CAVEMAN ULTRA (MUST 1) — invoke-and-confirm, or state-no-skill
7. CLASSIFICATION TAG (MUST 8) + EFFORT LEVEL (MUST 9)
8. SUCCESS GATES (MUST 2) — numbered, measurable, evidence required
9. FAILURE GATES (MUST 3) — explicit; RED honest beats GREEN rounded up
10. SECOND-OPINION JUSTIFICATION (MUST 10) — paid vendor targets only
11. GRILL CLAUSE (MUST 4) — ask before guessing
12. TRAINING OPT-OUT NOTICE (MUST 5) — verbatim line, every dispatch
13. EVIDENCE + REPORT-SHAPE + EDIT-HYGIENE (MUST 6, 12, 13) — cite
    everything; report scope-left-out, assumption changes, files created;
    edit surgically
14. PLAN CONTRACT (MUST 11), if deliverable is a delegation-capable plan —
    model + gates per task
15. LESSON-CANDIDATE tag (MUST 14), if applicable — one rung up, never
    sideways; only Supervisor presents to operator
16. OUTPUT SHAPE — fenced template

Token-vigilance clauses that measurably help on expensive tiers: cap tool
calls, cap output lines, ban whole-file reads, ban re-deriving supplied
facts, require hypothesis-then-test over breadth-first exploration.
