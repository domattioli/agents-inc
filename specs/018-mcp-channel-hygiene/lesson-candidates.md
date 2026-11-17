# Lesson candidates from spec 018 (approved, pending cross-vendor review)

Status: approved by the operator (domattioli) on 2026-10-06. These edits change `skills/*/SKILL.md`, which is canon, so D46 requires a reviewer from a different vendor (Codex) before they land. No Codex CLI was available in the session that drafted them, so they are not applied. Whoever lands them: run the Codex review against the diff below, apply it to DomI `skills/`, bump each skill's Version History, and record the review in this file.

Source: Fable analyze of 018 (cycle 1 A1 and A6, cycle 2 N4), relayed by the Supervisor (opus).

## LC-1: speckit-tasks gets a canon-landing task

Problem: when a feature amends `docs/DECISIONS.md` (or other canon), the task template has no step for who commits the signed amendment and when. In 018, the plan gated a code merge on the canon commit, and that collided with the "no canon edits by implementation" diff check (Fable N4).

Target: `skills/speckit-tasks/SKILL.md`, a new subsection after "### Phase Structure", before "### Final task: move specs to DomI".

```markdown
### Canon-landing task (features that amend canon)

When spec.md or plan.md says the feature amends a canon file (`docs/DECISIONS.md`, `CONTEXT.md`, `AGENTS.md`, a constitution or any `SKILL.md`), add these tasks in this order before the first code task that depends on the amendment:

1. Draft the amendment text in the run report (no file edit).
2. Cross-vendor review of the draft (D46), naming the reviewer model.
3. Operator sign-off on the reviewed draft.
4. Land the signed text: one commit by the Chief of Staff, touching only canon files. The task records the commit hash.

Code tasks that depend on the amendment depend on task 4. Any "implementation never edits canon" check runs per implementation commit and excludes the task-4 commit by hash, never over a plain `<base>..HEAD` range.
```

## LC-2: speckit-checklist gets an exact-list assertion item

Problem: two features in a row (017 analyze A2, 018 analyze A1) changed a tool list without naming the existing tests that assert that list exactly, so "existing tests pass unchanged" could not hold.

Target: `skills/speckit-checklist/SKILL.md`, "## Example Checklist Types & Sample Items", appended to the **API Requirements Quality** sample items.

```markdown
- "If a requirement adds, removes or renames a tool, endpoint, command or enum value, does the spec name every existing test that asserts that list exactly, and say how each assertion changes? [Consistency, Gap]"
```

## Review record

| Candidate | Reviewer (vendor, model) | Date | Verdict | Landed commit |
|---|---|---|---|---|
| LC-1 | pending (Codex) | | | |
| LC-2 | pending (Codex) | | | |
