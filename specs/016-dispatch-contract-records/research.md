<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Research: #4 and #27 records (spec 016, FR-009, FR-010)

Supervisor record, 2026-10-01. No new model runs. No DomI write.

## #4: dispatch-prompt style compression

**Status.** The revised hard-constraint template is an opt-in draft, not canon.

**What was measured.** The 2026-09 rerun used n=5 per arm with blind grading. It found:

- a 40% cut in answer words;
- higher billed output tokens, a mean of 1,175 rising to 2,500;
- a 1-point fact gap, within noise.

The word cut did not lower cost. Billed output rose; the rerun did not isolate why.

**What remains unvalidated.**

- The full factorial (template by model by task type) was not run.
- No non-extractive task was tested; the n=5 result covers extraction only.
- No measurement shows the template saves money. FR-010 forbids any savings claim until `cache_read` or billed tokens are measured over about 10 clustered runs.
- The template conflicts with caveman element 1 on arrows and abbreviations. Caveman forbids invented abbreviations and arrows; the template asks for both. A dispatch that uses the STYLE slot must choose one.

**Where it lives.** The template is the optional `{{STYLE}}` slot in `skills/workerbee/slots.md`, verbatim from #4 "Revised template". It is empty by default. `render_dispatch.py` drops the line when the slot is empty. Use it only on extractive and summarization dispatches.

## #27: DomI dispatch-skill overlap scan

**Verdict.** No overlap. DomI `skills/subagent-dispatch-policy` picks a model tier and caveman level per dispatch. agents_Inc `skills/workerbee` owns supervision, verification, and the 14-element prompt contract. Neither copies the other.

**Usage counts (from the #27 comment, not re-measured here).**

- 0 of 987 sessions invoked `subagent-dispatch-policy`.
- 4 of 6 DomI dispatch skills had zero invocations.

**Follow-ups.**

- Stale id `opus 4.7` in DomI `subagent-dispatch-policy`: already fixed. DomI `skills/subagent-dispatch-policy/SKILL.md:192` (v1.3.1, 2026-09-26) says "Replaced the stale model name "opus 4.7"" [verified, read-only]. No action needed.
- NEEDS-OPERATOR: decide whether to retire, merge, or keep the zero-use DomI dispatch skills. That is a DomI change; this repo does not write DomI.
- NEEDS-OPERATOR: if `subagent-dispatch-policy` stays, consider pointing it at `skills/workerbee/header.md` and `slots.md` for the fixed contract text, so the two skills cannot drift.
