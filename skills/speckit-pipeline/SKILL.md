---
name: speckit-pipeline
version: "1.5-agents_Inc.2"
benchmark: manual_speckit_command_invocations_per_feature
description: Chain the spec-driven-development phases (specify → clarify → plan → tasks → checklist → analyze → implement) into one guided pipeline. Runs specify, pauses at an interactive clarify gate, then advances unattended (under act-autonomously discipline) through plan, tasks, checklist, and analyze, auto-resolving analyze findings (≤3 cycles), and finishes with implement. Deterministic skip/add phase selection, per-phase agent/model/effort dispatch, optional nested-notes summary and accelerate illustration. Use when you want a whole feature taken from a plain-language description to an implemented change with a single invocation instead of hand-running seven commands. Pairs speckit-* (the phases it orchestrates), act-autonomously (unattended discipline), nested-notes + accelerate (optional outputs).
---

> **FORK — NOT CANON, operator exception to the no-vendoring default (D35, 2026-09-07).**
> Forked from the upstream private governance repo (commit `476e141`, branch `feat/pipeline-model-classes`, an unmerged upstream PR) so v1.5's new default-mode class dispatch can be fleshed out and tested against this repo's own `docs/governance/ROUTING-RANKING.md` before it becomes that repo's default for every consumer. This deliberately overrides the upstream repo's own "never vendor its skills into consumer trees" rule — see D35 for the exit criteria. Do not treat this copy as authoritative upstream canon; do not let it silently diverge and get treated as this repo's own original work.

# speckit-pipeline

One orchestration skill that carries a feature from a plain-language description to an implemented change by chaining the existing `speckit-*` phase skills into a single guided run. The main session **is** the orchestrator: it follows this procedure turn by turn, running main-session-tier phases inline via the `Skill` tool and dispatching subagent-tier phases via the `Agent` tool. It replaces the manual chore of invoking `/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-checklist`, `/speckit-analyze`, and `/speckit-implement` in sequence and hand-resolving analyze findings.

## Metadata

- **Category**: Spec-Driven Development / Orchestration
- **Use Case**: Take one feature from description to implementation in a single guided invocation
- **Dependencies**: the `speckit-*` phase skills, `act-autonomously`, `nested-notes`, `accelerate`, the `cavecrew-builder` preset, `python3` (stdlib), `bash`
- **Scope**: One feature per invocation; orchestrates 7 default phases + 4 insertable + 2 optional outputs

## When to Use

- You have a feature idea and want the full spec → implement pipeline run for you, with one human checkpoint.
- You want a tailored pipeline (skip phases you don't need, add optional ones) but keep a deterministic order.
- You want a routine/cron session to run the whole pipeline unattended (`--yes`).

## When NOT to Use

- You only need one phase — invoke that phase skill directly.
- The feature is already specified and you only want to implement — run `/speckit-implement`.
- You are outside a spec-kit-initialized project (no `.specify/`) — initialize first.

## The pipeline

Canonical default order (FR-002):

```
specify → clarify → plan → tasks → checklist → analyze → implement
```

Insertable phases (FR-022), each at a fixed canonical position: `constitution` (before specify), `tasks-to-issues` + `split` (after tasks), `commit` (after implement). `clarify` is the single interactive human gate; everything after it runs unattended.

### Analyze vs. converge — two different checks, two different positions

`analyze` and the (upstream) `converge` command look similar but check different things at different points in the pipeline, and conflating them is a real design trap:

- **`analyze` is a pre-implement, cross-artifact consistency check.** It reads `spec.md`, `plan.md`, and `tasks.md` and reports where those three artifacts disagree with each other. It inspects no code (there is none yet — it runs before `implement`), so its findings are resolved by editing the *artifacts*, never by writing code. This is why the pipeline runs `analyze` at position 6 and its resolve loop (Step 6) makes artifact edits, not implementation edits. Pairing `analyze` findings with an `implement` "fix" is the wrong tool for the wrong layer.
- **`converge` is a post-implement, code-vs-spec check.** It assesses the *code* against `spec.md`/`plan.md`/`tasks.md` and appends any remaining unbuilt work as new tasks, so a follow-up `implement` closes the gap. It must run *after* `implement` by contract.

**Future work — `speckit-converge` phase (not yet available upstream).** Upstream `github/spec-kit` ships a `converge` command (PR #3001); the upstream private governance repo has not yet ported it as a `speckit-converge` phase skill. When it lands, the intended shape is a bounded post-implement convergence loop — `implement → converge → (tasks appended?) → implement → converge …`, capped at ~3 cycles — added as a default phase after `implement` (order between `implement` and `commit`). The loop is bounded rather than exit-code-driven because a `converged` pass leaves `tasks.md` byte-for-byte unchanged, making extra iterations safe no-ops. This is deliberately **not** wired into the registry today: with no `speckit-converge` skill on disk, `preflight.sh` would fail any run that included the phase. Port the skill first, then add the phase.

## Modes

Two modes select the Execution Policy table below. **New mode is DEFAULT** — no flag needed. `--legacy` opts into the old hardcoded-model table (retained for callers not ready to move). See `specs/008-pipeline-model-classes/spec.md` (consumer-side spec) for the rationale and the class→collision resolutions this table reflects.

- **New mode (default)**: phases bind to a provider-agnostic CLASS (`Executive`/`Orchestrator` (aka `Supervisor`)/`Workhorse`/`Grunt`/`free`) instead of a hardcoded model name. **agents_for_dummies-native addition (D35, 2026-09-07):** CLASS → concrete model resolution is a real script, not eyeballed prose — run `python3 skills/speckit-pipeline/scripts/resolve_rung.py <CLASS>` (parses `docs/governance/ROUTING-RANKING.md` live, so it can never drift from canon; fails closed — non-zero exit, no guess — on an unrecognized rung or a missing/reshaped table). If `docs/governance/ROUTING-RANKING.md` is absent entirely (a repo without this repo's rung ladder), fall back to the legacy table's model column for that phase and emit one warning line. Default effort is `medium` everywhere (was `high` on constitution/specify/plan/analyze). `clarify-surrogate` is **disabled**: see Step 5. The analyze retry cap is **2** cycles, not 3: see Step 6. Preflight tolerates a missing `.specify/scripts/bash/check-prerequisites.sh`: see Step 3. **Every phase dispatch is also recorded into this repo's real dispatch ledger** — see Step 4's ledger sub-step — giving pipeline runs the same lineage/cost-rollup/lint visibility as any other governed dispatch in this repo, and threading a sha256 of each phase's deliverable through the same (imperfect, already-existing) artifact-hash path spec 006 documents, so Bindle can pick it up later with zero pipeline-side change once it's built (it is not built yet — this only readies the seam).
- **Legacy mode (`--legacy`)**: unchanged dispatch targets (Plan/general-purpose/adversarial-reviewer/cavecrew-builder, same models), but default effort also drops `high` → `medium` on every row that previously said `high` (operator ruling, aligns with the same medium-by-default direction as new mode). Everything else in legacy mode (clarify-surrogate enabled, 3-cycle analyze retry cap, hard-required `check-prerequisites.sh`) is unchanged from v1.4.

## Execution Policy (dispatch map)

Canonical copy lives in `specs/017-speckit-workflow/spec.md` (`## Execution Policy`) and `data-model.md`. Mirrored here as the forcing function the orchestrator consults per phase — if this diverges from the spec on a future edit, the spec wins.

**New mode (default):**

| Phase | Agent | Class | Effort | Caveman |
|---|---|---|---|---|
| constitution | main session | session | medium | none (artifact) |
| specify | main session | session | medium | none (artifact) |
| clarify | main session | session | session | light (human gate) |
| plan | `Plan` | Orchestrator | medium | dispatch max · `plan.md` none |
| tasks | `general-purpose` | Workhorse | medium | dispatch max · `tasks.md` none |
| tasks-to-issues | `general-purpose` | Grunt | low | dispatch max · issue light |
| split | `general-purpose` | Grunt | low | dispatch max · issue light |
| checklist | `general-purpose` | Grunt | low | dispatch max · none |
| analyze | `adversarial-reviewer` | Workhorse (escalate Orchestrator if findings conflict) | medium | dispatch max · report max |
| implement | `cavecrew-builder` preset (`general-purpose`/Grunt) | Grunt | medium (escalate Workhorse if broad, per D27 promotion) | dispatch max · **code normal** |
| commit | main session | session | low | `caveman-commit` |

Class → concrete model is resolved from `docs/governance/ROUTING-RANKING.md` at dispatch time, not hardcoded here (avoids the drift 007 removes). `implement` still lands on a Grunt-tier builder by default per the coding-dispatch binding; escalation to Workhorse follows the same promotion triggers as any other rung (two failed checks, quota pause, or a Lead-assigned gate reason) — never on confidence alone.

**Legacy mode (`--legacy`):**

| Phase | Agent | Model | Effort | Caveman |
|---|---|---|---|---|
| constitution | main session | session | medium | none (artifact) |
| specify | main session | session | medium | none (artifact) |
| clarify | main session | session | session | light (human gate) |
| plan | `Plan` | opus/sonnet | medium | dispatch max · `plan.md` none |
| tasks | `general-purpose` | sonnet | medium | dispatch max · `tasks.md` none |
| tasks-to-issues | `general-purpose` | haiku | low | dispatch max · issue light |
| split | `general-purpose` | haiku | low | dispatch max · issue light |
| checklist | `general-purpose` | haiku | low | dispatch max · none |
| analyze | `adversarial-reviewer` | sonnet/opus | medium | dispatch max · report max |
| implement | `cavecrew-builder` preset (`general-purpose`/haiku) | haiku | medium (escalate high if broad) | dispatch max · **code normal** |
| commit | main session | session | low | `caveman-commit` |

Not pipeline phases (excluded from skip/add): `resolve-issues` (internal analyze sub-loop, ≤3 cycles legacy / ≤2 cycles new mode), `summary` (`--summary` → `nested-notes`), `illustrate` (`--illustrate` → `accelerate`). Caveman is audience-scoped (#387): maximum intensity on machine-facing subagent dispatch prompts, light on human-facing recaps/clarify, never on generated artifacts or code.

## Protocol

### Step 1: Parse arguments

Read `$ARGUMENTS`: the feature description (required, FR-001; error out if empty). Flags: `--legacy` (opt into the legacy Execution Policy table + legacy clarify/analyze/preflight behavior — see Modes; default is new mode without this flag), `--skip <csv>`, `--add <csv>`, `--plan-only` (planning-only run — skips `implement`, implies `--allow-required-skip`; for checkpoint/diagnosis runs that stop before code, #405), `--allow-required-skip` (permit `--skip` to target a required phase `specify`/`implement`; the dependency check still guards), `--yes` (autonomous — in legacy mode delegates the clarify phase to a `clarify-surrogate` subagent instead of a human; in new mode `clarify-surrogate` is disabled and `--yes` still halts at the clarify gate for the operator, see Step 5; does NOT skip clarification either way, FR-020), `--summary[=granularity,mode]` (FR-007/008), `--illustrate` (FR-009), `--parallel` (opt-in fan-out, FR-024).

### Step 2: Resolve the phase set (deterministic)

Shell out once to the resolver, capture the ordered plan, branch on exit code:

```
python3 skills/speckit-pipeline/scripts/resolve_phases.py --skip "$SKIP" --add "$ADD" --json
```

Exit codes: `0` OK · `10` unknown phase name (stderr lists valid names) · `11` skip/add name conflict · `12` add name not insertable · `13` skip targets a required phase (`specify`/`implement`) **without** `--allow-required-skip`/`--plan-only` (the required guard is opt-out, not absolute — a forced skip that breaks a dependency still fails with `14`) · `14` dependency break (all violations listed). On any non-zero code, report the resolver's message to the operator and stop — do not run a partial or incoherent pipeline (FR-012/FR-013). Ordering is deterministic by construction (SC-002/SC-003): the resolver consumes skip/add only as sets and derives order from a single fixed key.

### Step 3: Preflight (before the first dispatch)

```
bash skills/speckit-pipeline/scripts/preflight.sh <resolved phase ids...>
```

Verifies every resolved phase's skill is present (via the id→skill-dir map — `tasks-to-issues→speckit-taskstoissues`, `commit→speckit-git-commit`, `constitution→speckit-constitution`, `split→speckit-split`, else `speckit-<id>`) and that `.specify/` exists (FR-015). Missing pieces are reported now, never mid-pipeline. Also preflight the optional-output skills if their flags are set; a missing one is a warning, not a blocker (FR-016).

Several phase skills (`checklist`, `tasks`, `tasks-to-issues`, `clarify`, `analyze`, `implement`) call `.specify/scripts/bash/check-prerequisites.sh` themselves at their own Setup step. **New mode** tolerates that script being absent: preflight checks for it and, if missing, emits one warning (`WARN: .specify/scripts/bash/check-prerequisites.sh not found — phases that depend on it may fail at their own Setup step`) instead of failing the whole preflight, since a consumer repo not scaffolded by upstream `spec-kit` may not carry it. **Legacy mode** keeps the old behavior: the script's absence is not itself preflighted (unchanged from v1.4 — the affected phase simply fails at its own Setup step when it hits the missing script).

### Step 4: Execute each resolved phase in order

For each phase, consult the Execution Policy table:

- **Main-session-tier** (`constitution`, `specify`, `commit`, and `clarify` when `--yes` is NOT set): run inline via `Skill(skill="speckit-<id>")`.
- **`clarify` under `--yes`**: dispatched to the `clarify-surrogate` persona via `Agent(agentType="clarify-surrogate")` — see Step 5.
- **Subagent-tier** (`plan`, `tasks`, `checklist`, `analyze`, `implement`, `tasks-to-issues`, `split`): dispatch via `Agent` with the phase's own canonical Outline **transcluded fresh from disk** (`skills/<skill-dir>/SKILL.md`) into the prompt — never a baked-in copy, so the pipeline never drifts from the standalone phase skills (FR-025). `cavecrew-builder` is a preset (`general-purpose`/haiku), not a raw subagent type — resolve it. Code-writing (`implement`) MUST go to a Haiku builder subagent per the repo's coding-dispatch binding; the main session integrates and verifies.
- **After every dispatch**: verify the expected on-disk artifact was produced (`git status`/diff on the expected path) before proceeding. A subagent's self-reported success is not trusted until the artifact is on disk (guards the Haiku false-completion mode).
- Record each phase's outcome (ran/skipped/succeeded/failed) to `.specify/workflow-state.json` (FR-017/FR-026) so the ledger survives context compaction or resume.
- **New mode only — record into this repo's real dispatch ledger (D35), record-only, never blocking:**
  1. Before the phase's `Agent`/`Skill` call: `python3 skills/speckit-pipeline/scripts/resolve_rung.py <CLASS>` to get the concrete model(s) for the phase's table row (escalate to `escalate_to` per the same D27 promotion trigger everything else in this repo uses — two failed checks on this phase, provider quota pause, or an explicit gate reason; never on confidence).
  2. Still before the call: `python3 skills/speckit-pipeline/scripts/ledger_bridge.py dispatch --run-id <pipeline run's uuid, one per pipeline invocation> --node-id <fresh uuid> --model <resolved slug> --rung <CLASS> --task speckit-<phase> --provider claude|codex [--parent-id <this run's root node>] [--gate-reason "<reason, required when the rung mapped to frontier>"]` — capture the printed node id.
  3. Run the phase exactly as already specified (Agent tool / Skill tool, unchanged).
  4. After the phase's artifact is verified on disk: `python3 skills/speckit-pipeline/scripts/ledger_bridge.py return --node-id <from step 2> --status verified|needs-review|red --seconds <elapsed> --artifact-file <the phase's produced file, e.g. plan.md>`.
  5. A ledger write failure here is never a pipeline failure (`ledger.py`'s own FR-008 posture — `record_dispatch`/`record_return` never raise) — this bridge fails open by design; a run that can't reach `.workerbees/` still completes.

### Step 5: The clarify gate

**Default (`--yes` not set)** — run `clarify` inline. Present the clarification questions and **end the turn to wait** for operator answers (FR-003) — an ordinary conversational boundary, which is how the interactive gate is realized.

**`--yes` set, legacy mode** — `--yes` does **not** mean skip clarification; it means no human is present to answer it, so a surrogate answers instead (FR-020):

1. Run `/speckit-clarify`'s own question-generation logic (its ambiguity scan + prioritized queue) as normal, but do not present the questions to a human.
2. Dispatch `Agent(agentType="clarify-surrogate")` — **do not pass an explicit `model` override on this call.** The persona's own frontmatter (`.claude/agents/clarify-surrogate.md`) has no `model:` field for exactly this reason: it must inherit the orchestrating session's current model, so an unattended run's clarification quality tracks the tier the rest of the run is using, not a hardcoded one. Pass it the drafted spec and the generated questions (with their suggested-options tables); its own SKILL.md-equivalent persona instructions govern how it grounds and answers.
3. Integrate each returned answer into the spec exactly as `/speckit-clarify` integrates a human's answer (its own Step 5 integration rules — `## Clarifications` section, per-section updates, save after each).
4. Emit one warning line: `WARN: clarify answered by clarify-surrogate (model inherited from this session), not the operator — see spec Clarifications section for grounding.` This is what the FR-017 audit ledger uses to record that a human never actually weighed in on this run's clarification.
5. **If the surrogate flags any question unresolved** (its own escalation rules: insufficient grounding, security/scope/privacy stakes, or a materially shape-changing decision the spec leaves open), treat this exactly like any other unsafe-to-continue condition (FR-020a/FR-006): halt **before** `plan`, name the unresolved question and why, and do not guess. This is a correct, intended outcome — it means the run correctly recognized it should not proceed unattended past this point.

**`--yes` set, new mode (default)** — `clarify-surrogate` is **disabled**, unconditionally. A surrogate answering the operator's own clarify questions and then feeding that into `plan` is a self-graded input (constitution P3) — new mode does not run this pattern at all, not even opt-in. Instead: run `/speckit-clarify`'s question-generation logic as normal, then **halt and end the turn**, presenting the generated questions to the operator exactly as the non-`--yes` path does. `--yes` in new mode therefore affects only the phases *after* clarify (no acknowledgment theater between them, per `act-autonomously`) — it does not remove the human clarify checkpoint. Emit one line: `NOTE: --yes does not bypass clarify in new mode (clarify-surrogate disabled, P3) — halting for operator answers.` An operator who explicitly wants the old surrogate behavior must pass `--legacy` as well.

**`--skip clarify`** (structurally separate from `--yes`) removes the phase from the effective set entirely — a true no-answers skip, with none of the surrogate's grounding or halting behavior. An operator who explicitly wants the old bare-skip behavior uses `--skip clarify`, not `--yes`. The two controls are independent: `--yes` alone never results in zero answers (it either gets surrogate answers or halts); `--skip clarify` alone never invokes the surrogate (the phase doesn't run at all).

### Step 6: The analyze → resolve-issues loop

Dispatch `analyze` (`adversarial-reviewer`, read-only — it reports, never edits). Because `analyze` is a cross-artifact consistency check (see "Analyze vs. converge" above), every fix in this loop is an **artifact** edit to `spec.md`/`plan.md`/`tasks.md`, never an implementation edit — the code doesn't exist yet at this point. For each surfaced finding, apply the fix (main session, or a `cavecrew-builder` subagent for larger edits), then re-run `analyze`. Repeat **up to 2 cycles in new mode, 3 cycles in legacy mode**; on the final still-unresolved cycle, halt and report the unresolved findings to the operator (FR-005/FR-021). New mode's lower cap matches this repo's own retired 3-count convention. The cycle counter is persisted to `.specify/workflow-state.json` (FR-026). The post-implement code-vs-spec gap is a separate concern handled by the future `converge` phase, not by this loop.

**Findings handoff (agents_Inc binding).** The analyze dispatch names `<feature dir>/analyze.md` as the findings path. The reviewer writes the findings table there (ID, severity, file:line, remedy, OPERATOR flag) and returns only counts by severity plus the OPERATOR IDs. The orchestrator sends the fixer "fix all findings in analyze.md" plus rulings on the OPERATOR items only. The fixer appends a Resolution column. The orchestrator verifies the file on disk before the re-run.

### Step 7: Unattended discipline & halting

From clarify-satisfied through implement, follow `act-autonomously` verbatim: no acknowledgment theater between phases, log every skip/fallback (silent-deviation ban), and apply its Hard-Stop-vs-Handle-and-Continue table — halt on destructive or irreversible actions during `implement` rather than proceeding blindly (FR-018). Any phase failure that is not auto-resolvable or is unsafe to continue past halts **before** implement, naming the phase and reason (FR-006).

### Step 8: Optional outputs (post-pipeline)

- `--summary` → `Skill(skill="nested-notes", ...)` at light caveman, passing granularity/render-mode through (FR-007/008).
- `--illustrate` → `Skill(skill="accelerate")` to present an image of the result (FR-009).

Both are independent of each other and of the pipeline (FR-014); a missing capability yields one warning and the core result still reports success (FR-016).

### Step 9: `--parallel` (opt-in fan-out)

Default off = strictly sequential per-phase dispatch with the single agent named above. When `--parallel` is set, the harness MAY parallelize independent phase work and prefer cheaper models at its discretion — **without** changing the resolved phase set or order (execution strategy only, FR-024).

## CLI

```
scripts/resolve_phases.py [--skip a,b] [--add x,y] [--json] [--explain]
scripts/resolve_phases.py --plan-only [--add x,y]  # planning-only: skip implement (forced)
scripts/resolve_phases.py --skip implement --allow-required-skip  # explicit forced required-skip
scripts/resolve_phases.py --list          # dump the registry, bypass resolution
scripts/preflight.sh <phase-id>...        # verify phase skills + .specify present
```

Resolver exit codes:

| Exit | Meaning |
|---|---|
| 0 | resolved OK, ordered phase list on stdout |
| 2 | usage error |
| 10 | unknown phase name (skip or add) — stderr lists valid names |
| 11 | skip/add same-phase conflict |
| 12 | add-list name not in the insertable set |
| 13 | skip-list targets a required phase (`specify`/`implement`) **without** `--allow-required-skip`/`--plan-only` (opt-out guard; a forced skip breaking a dep still fails `14`) |
| 14 | dependency break — a retained phase's dependency was skipped |

## Hard stops

| Condition | Behavior |
|---|---|
| Empty feature description | Report missing input; do not start (FR-001). |
| Resolver returns non-zero | Report the message; run no phase (FR-012/FR-013). |
| Required phase skill or `.specify/` missing at preflight | Report; do not start (FR-015). |
| Dispatched artifact absent after a phase | Halt, name the phase; do not proceed (FR-025). |
| Analyze unresolved after 2 cycles (new mode) / 3 cycles (legacy) | Halt; report unresolved findings (FR-021). |
| `clarify-surrogate` flags a question unresolved (`--yes` runs, legacy mode only) | Halt before `plan`, name the question and why; never guess (FR-020a). |
| `--yes` reaches the clarify gate in new mode | Halt for operator answers — `clarify-surrogate` is disabled in new mode (P3), `--yes` does not bypass this gate. |
| Destructive/irreversible action during implement | Halt and ask, per `act-autonomously` (FR-018). |

## Cost discipline

- Sequential single-agent dispatch by default; parallel/Workflow fan-out only under `--parallel`.
- Dispatch prompts carry maximum-intensity caveman; artifacts and code never do.
- Optional outputs degrade gracefully — never fail the pipeline over a missing recap/illustration.

## Cross-skill interaction

| Skill | Relationship |
|---|---|
| `speckit-*` | The phases this skill orchestrates (transcluded, never reimplemented). |
| `act-autonomously` | Supplies the unattended-execution discipline for the post-clarify tail. |
| `nested-notes` | `--summary` renderer. |
| `accelerate` | `--illustrate` renderer. |
| `clarify-surrogate` (`.claude/agents/clarify-surrogate.md`) | Legacy mode only: answers `/speckit-clarify`'s questions in place of a human under `--yes`; inherits the orchestrating session's model. Disabled in new mode (default) — new mode halts at clarify for the operator regardless of `--yes` (P3). |
| `cavecrew-builder` | The Haiku builder preset the `implement` phase dispatches to. |

## Files

- `SKILL.md` — this orchestration procedure + the Execution Policy dispatch map.
- `scripts/phase_registry.py` — the phase registry + `resolve()` (deterministic ordering core; pure, no I/O).
- `scripts/resolve_phases.py` — CLI wrapper over `resolve()` with exit-code branching.
- `scripts/preflight.sh` — phase-skill + scaffold availability check (FR-015).
- `tests/test_phase_registry.py` — `python3 -m unittest` (stdlib only); asserts determinism + validation exit codes.
- `tests/benchmark.md` — v1.0 baseline per #21 mandate.

## Version History

- **v1.5-agents_Inc.2** (2026-09-07) — the `agents_inc/` governance slice's SQLite schema now natively speaks the D27 rung vocabulary (D36: `grunt`/`workhorse`/`orchestrator`/`executive` replace `cheap`/`mid`/`frontier` across `SCHEMA-3NF.md`, `routing.json`, `models.json`, and every consumer module). `ledger_bridge.py` simplified accordingly — it now just normalizes a rung name (D34 `Supervisor` synonym included) straight to the schema's `tier` column, no bucket-mapping layer. `tests/smoke_ledger_bridge.sh` (6 assertions) extended to prove the gate-reason lint requirement survived the rename (an executive-tier dispatch missing a gate reason is still flagged).
- **v1.5-agents_Inc.1** (2026-09-07) — agents_for_dummies-native fork addition (D35): real CLASS->model resolution (`scripts/resolve_rung.py`, parses `docs/governance/ROUTING-RANKING.md` live, fails closed) replaces eyeballed-prose resolution; every new-mode phase dispatch is now recorded into this repo's real ledger (`scripts/ledger_bridge.py`) for lineage/cost-rollup/lint parity with the rest of the repo's governed dispatches, and threads an artifact sha256 through the existing (imperfect) capture path spec 006 documents, readying — not building — a future Bindle seam. Found a real bug in the process (superseded by D36 above, see v1.5-agents_Inc.2): `agents_inc/ledger.py`'s SQLite schema hardcoded `tier CHECK (tier IN ('cheap','mid','frontier'))` (pre-D27 vocabulary) — passing a D27 rung name straight into `tier` silently failed to persist to SQLite (swallowed `IntegrityError`, JSONL still wrote, `record_dispatch` still reported success). `tests/smoke_ledger_bridge.sh` (initially 5 assertions, all passing) covers the fix against an isolated temp workspace, never the real `.workerbees/` ledger.

- **v1.5** (2026-09-06) — `specs/008-pipeline-model-classes` (consumer-side spec). New mode becomes **DEFAULT**: phases bind to provider-agnostic classes (`Executive`/`Orchestrator` (aka `Supervisor`)/`Workhorse`/`Grunt`/`free`, existing D27 rung vocabulary — no new class tokens introduced) resolved to a concrete model at dispatch time from `docs/governance/ROUTING-RANKING.md`, not a hardcoded table, and default effort is `medium` everywhere. `--legacy` retains the old hardcoded-model table, also dropped to default effort `medium` (was `high`). New mode disables `clarify-surrogate` outright (P3 — a surrogate answering clarify then feeding plan is a self-graded input); `--yes` in new mode still halts at the clarify gate for the operator. Analyze retry cap drops 3 → 2 cycles in new mode only (legacy keeps 3). Preflight (new mode only) tolerates a missing `.specify/scripts/bash/check-prerequisites.sh` with a warning instead of failing, since a consumer repo not scaffolded by upstream `spec-kit` may lack it. No change to the phase registry, resolver, or `speckit-*` phase skills themselves — only this skill's own policy table, mode selection, and preflight.
- **v1.4** (2026-07-15) — `#405` — allow excluding *any* phase, not just insertable ones. The required-phase guard (`specify`/`implement`) is now **opt-out**, not absolute: `--allow-required-skip` on the CLI (`force=True` on `resolve()`) bypasses the exit-13 `RequiredPhaseSkip` check, and `--plan-only` is convenience sugar for a planning/checkpoint run (skips `implement`, implies the force). The dependency checker (`DepBreak`, exit 14) remains the real backstop — forcing `--skip specify` still fails because `clarify`/`plan`/`checklist`/`analyze` depend on it, so operators get a precise list of what else to skip rather than a silent broken pipeline. Default behavior unchanged (a bare `--skip implement` still exits 13), so every existing caller and test is untouched. Serves the diagnosis-only pipeline the QuADMESH-RL spec-015 run needed (`specify→plan→tasks→checklist→analyze`, no `implement`) that previously forced a manual orchestration halt. New resolver `force` param + two CLI flags + 4 tests (17 total). Additive.
- **v1.3** (2026-07-09) — Docs-only. Added an "Analyze vs. converge" section clarifying that `analyze` is a pre-implement cross-artifact consistency check (findings fixed in artifacts, never code) versus the post-implement code-vs-spec `converge` check, and documented `speckit-converge` as a pending port from upstream `github/spec-kit` (#3001) — the phase is deliberately not wired into the registry until the skill exists, since `preflight.sh` would otherwise fail. Prompted by the `github/spec-kit` pipeline-workflow review (PR #3338), where the same analyze/implement mispairing surfaced. No behavior change; registry, resolver, and dispatch policy unchanged.
- **v1.2** (2026-07-05) — Renamed `speckit-workflow` → `speckit-pipeline` (operator-directed). Skill dir, `name:` frontmatter, self-referencing script/test paths, MANIFEST entry, and live cross-refs (`.claude/agents/*`, `clarify-surrogate`) updated. Historical spec `017-speckit-workflow` keeps its dir/id (spec of record, not renamed). No behavior change — the phase registry, resolver, and dispatch policy are identical. A fully-generic, upstream-decoupled port of this pipeline is staged at `contrib/spec-kit/pipeline/` for upstream contribution to `github/spec-kit`.
- **v1.1** (2026-07-03) — Operator-directed revision: `--yes` no longer skips the clarify gate with a warning. It now dispatches a new `clarify-surrogate` subagent (`.claude/agents/clarify-surrogate.md`) that answers `/speckit-clarify`'s questions grounded in the spec/repo, spawned without a model override so it inherits the orchestrating session's own model tier — an unattended/optimized run gets real clarification answers instead of none. A literal no-answers skip remains available only via the structurally separate `--skip clarify`. If the surrogate can't responsibly answer (insufficient grounding, security/scope stakes, materially shape-changing decision), it flags the question unresolved and the run halts before `plan` rather than guessing (FR-020a). New Hard Stop row + Cross-skill entry.
- **v1.0** (2026-07-03) — Initial. Spec-driven-development pipeline orchestrator (spec `017-speckit-workflow`). SKILL.md-driven hybrid: main-session inline `Skill` for interactive/docs phases, `Agent` dispatch with fresh transclusion for subagent phases, pure-Python deterministic phase resolver, `act-autonomously` unattended tail, optional `nested-notes`/`accelerate` outputs, opt-in `--parallel`.
