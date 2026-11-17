<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Decouple agents_Inc from DomI and the operator's machine

**Feature Branch**: `011-decouple-from-domi`
**Created**: 2026-09-18
**Status**: Draft (planning-only run; `--plan-only --skip clarify --yes`)
**Input**: fable-tier architecture review 2026-09-18, `plan-decouple-agents_inc.md` (tasks T1–T11, each with a success + failure gate; those gates are this spec's acceptance criteria, reproduced verbatim in `tasks.md`).

## Goal

A person who is not the operator can `git clone agents_Inc`, run its tests and fake demo, and follow its
skills, with **no DomI checkout**, **no `~/.claude/skills/*` symlinks into DomI**, and **no knowledge of the
operator's Codex account nicknames**. DomI-provided skills become optional enhancements with explicit
fallback, never silent prerequisites.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Clean clone runs green (Priority: P1)

A contributor with no DomI checkout and no Codex CLI clones the repo, installs skills, and runs the test
suite and the fake governance demo. Nothing exits non-zero because of a missing operator-local path.

**Why this priority**: today this is a hard break — `agents_inc/keys.py` is gitignored by `.gitignore:224`
(`*key*`), so a fresh clone has 11 pytest collection errors, and `scripts/install_skills.sh` exits 1 on any
machine lacking `/Users/domattioli/Projects/DomI`. Nothing else in the feature matters until this passes.

**Independent Test**: fresh clone into a tmpdir with `HOME` pointed at an empty dir and `PATH` stripped of
`codex`/`claude`/`gemini`; run `bash scripts/install_skills.sh`, `python3 -m pytest tests -q`,
`governance_demo --fake`. Delivers a usable repo for a non-operator.

**Acceptance Scenarios**:

1. **Given** a fresh clone, **When** `python3 -m pytest tests -q` runs, **Then** collection reports 0 errors
   and no `ModuleNotFoundError: No module named 'agents_inc.keys'` appears. (T1)
2. **Given** a clean `HOME` with no DomI checkout, **When** `bash scripts/install_skills.sh` runs, **Then**
   it exits 0, lists every vendored skill OK, and lists every optional skill as `OPTIONAL-MISSING`. (T2)
3. **Given** the operator's own machine, **When** the same installer runs, **Then** it exits 0 with no MISS
   line — i.e. the fix does not regress the working case. (T2)
4. **Given** `skills.requirements.txt`, **When** grepped, **Then** no absolute `/Users/` path remains. (T2)

---

### User Story 2 — Optional DomI skills degrade out loud (Priority: P1)

Every place the repo's own contract leans on a DomI-provided skill (`handoff-lint`, `caveman`,
`nested-notes`, `write-like-scientist`, `subagent-dispatch-policy`) either works without it or says exactly
one line explaining what it fell back to. No silent degradation; no doc sentence that presents a DomI path
as unconditional.

**Why this priority**: the D40 handoff-lint gate and delegation-contract element 1 are *binding* rules. A
binding rule that silently no-ops on a non-operator machine is worse than no rule — the reader believes a
check ran that never ran.

**Independent Test**: on a clean `HOME`, run `check_dispatch_prompt.py --with-handoff-lint p.txt` and read
`skills/workerbee/SKILL.md` Step 0.5 / MUST 7 cold. Both must be executable/complete without DomI.

**Acceptance Scenarios**:

1. **Given** a clean `HOME` with no `handoff-lint` installed, **When**
   `check_dispatch_prompt.py --with-handoff-lint p.txt` runs, **Then** it prints the warning line
   `handoff-lint NOT installed -> H1-H6 checked by hand`, emits the 14-element verdict only, and does not
   crash. **And** on the operator machine it runs both. (T4)
2. **Given** a dispatch prompt whose element 1 states the caveman *emulation* line rather than a successful
   Skill call, **When** `check_dispatch_prompt.py` scores it, **Then** element 1 is compliant. (T5)
3. **Given** a reader with no DomI, **When** they execute workerbee Step 0.5 and MUST 7, **Then** every rule
   needed is restated in this repo; no sentence of the form "see X for the rule" where X is not in this
   repo. (T6)

---

### User Story 3 — Canon carries no account facts (Priority: P2)

Skill/canon text describes portable rules. Machine- and account-specific facts (Codex nickname→slug rows,
"limit: 0 on this account", "Devstral not exposed on this key") live in generated or user-scope files, and
model slugs are overridable rather than hardcoded.

**Why this priority**: account facts embedded in canon are wrong for every reader who is not the operator,
and they rot silently. Lower than P1 because the repo still *runs* without this fix.

**Independent Test**: `grep -n "this account\|this machine" skills/workerbee/SKILL.md` returns 0 hits; a unit
test resolves `--model luna` through the override path.

**Acceptance Scenarios**:

1. **Given** `skills/workerbee/SKILL.md`, **When** grepped for "this account"/"this machine", **Then** 0
   hits, and no account-specific quota note remains in canon text. (T7)
2. **Given** an override map, **When** `agents-inc run --model luna` resolves, **Then** it goes through the
   override path (unit-tested), with today's values as defaults. (T7)
3. **Given** a clean `HOME` with no codex on `PATH`, **When** `smoke_mcp.sh --offline` runs, **Then** it
   prints `SMOKE PASS`; **And** `codexagent.sh --model terra` with a map including `terra` passes the guard;
   **And** the live call still reports "would need account". **And** no hardcoded `gpt-5.6-luna` literal
   remains at `skills/codex-bridge/scripts/codexagent.sh:52,54`. (T8)
4. **Given** `agents-inc install` on a clean `HOME` with no Codex CLI, **When** run as
   `install --source . --without-codex`, **Then** `~/.claude/skills/{workerbee,codex-bridge}` land and
   `doctor` reports `WB_CLI_NOT_FOUND` as a **warning**, not an untrusted release; **And** the README states
   the Codex-CLI prerequisite; **And** the installer never exits without saying what it did not do. (T9)

---

### User Story 4 — Regression guard (Priority: P2)

A CI lane reproduces the clean-machine simulation so portability cannot silently rot back.

**Why this priority**: without the lane, every fix above decays on the next PR. It is P2 only because it
must land *after* the things it guards.

**Independent Test**: run the lane on a runner with no DomI and no codex.

**Acceptance Scenarios**:

1. **Given** a runner with no DomI and no codex, **When** the portability lane runs, **Then** it is green.
   (T10)
2. **Given** the lane's source, **When** inspected, **Then** it depends on no `/Users/` path and on no
   `~/.claude/skills` content. (T10)

---

### User Story 5 — Pre-existing breakage cleared (Priority: P3)

Two failures found during the simulation that are **not** portability defects get fixed so they stop
masking portability signal.

**Independent Test**: `pytest tests/test_config_schema.py` green; `preflight.sh` runs under bash 3.2.

**Acceptance Scenarios**:

1. **Given** the operator machine, **When** `tests/test_config_schema.py` runs, **Then** the 6 pre-existing
   failures are resolved or explicitly re-scoped. (T11)
2. **Given** macOS system bash 3.2, **When** `skills/speckit-pipeline/scripts/preflight.sh` runs, **Then** it
   does not die with `constitution: unbound variable` — the `declare -A` at line 23 is replaced by the
   `case` form DomI's copy already uses. (T11)

## Requirements

### Functional

- **FR-001** (T1): `agents_inc/keys.py` is tracked. `.gitignore` gains `!agents_inc/keys.py` beside the
  existing `!workerbees/keys.py` exception (`.gitignore:224-227`).
- **FR-002** (T2): `skills.requirements.txt` carries no absolute path. DomI sources use a URL form —
  e.g. `source=github:domattioli/DomI@<ref>:skills/<name>`; the `<ref>` form (pinned sha vs tracked branch)
  is **D5, OPEN**. The input said "e.g."; this FR must not narrow it into a rule before D5 answers.
- **FR-003** (T2): the `handoff-lint` entry's trailing parenthetical is stripped — it is parsed into the path
  today, so the entry fails **even on the operator's machine** (`skills.requirements.txt:22`).
- **FR-004** (T2): a source kind `optional-user-scope` (added alongside the existing `vendored` and `external-repo`, and any `github:` form FR-002 introduces — the kind set is enumerated in T2's kind table, so do not call it "the third kind") means "look in `$HOME/.claude/skills/<name>`,
  warn if absent, never exit non-zero"; the installer prints `OPTIONAL-MISSING <name>` and exits 0.
- **FR-005** (T3): no directory exists in both `skills/` and an `external-repo` manifest entry.
- **FR-006** (T4): the D40 handoff-lint gate (`CLAUDE.md:62`, `skills/workerbee/SKILL.md:640-661`) is worded
  conditionally and `check_dispatch_prompt.py --with-handoff-lint` resolves-or-warns mechanically.
- **FR-007** (T5): delegation-contract element 1 (and the `nested-notes` / `write-like-scientist` mandates at
  `CLAUDE.md:9-12`) accept an explicit emulation fallback; the checker accepts either form, with a test
  fixture for each.
- **FR-008** (T6): each `subagent-dispatch-policy` reference in workerbee (SKILL.md:131, 520, 806) is
  qualified once as an optional DomI skill whose rule is restated in-repo.
- **FR-009** (T7): Codex nickname→slug rows and account-specific notes move out of canon into a generated or
  user-scope file (destination = **D4, OPEN**); `agents_inc/install/runtime.py:8` `MODEL_ALIASES` and
  `agents_inc/routing.json:5-8` become overridable (`AGENTS_INC_MODEL_MAP` env and/or an override file whose
  **name is TBD — NOT `agents_inc/models.json`**, which already exists as an unrelated tracked model catalog,
  see plan gap G1) with today's values as defaults.
- **FR-010** (T8): `codexagent.sh` and `codex_agent_mcp.py` build their slug set from one shared map; an
  `mcp/install.sh` exists; README documents the one-liner; `smoke_mcp.sh --offline` stops after `tools/list`.
- **FR-011** (T9): `agents-inc install --without-codex` exists and the Codex-CLI prerequisite is documented.
- **FR-012** (T10): a portability lane reproduces the clean-clone simulation end to end.
- **FR-013** (T11): the bash-3.2 `preflight.sh` breakage and the 6 `test_config_schema.py` failures are
  addressed in their own issue, separate from portability.

### Non-functional / constraints (carried verbatim from the input)

- Repo-scoped writes only. No writes to `~/.claude/**`, `~/.codex`, `~/.claude.json`.
- No paid model calls during implementation or verification.
- Do not vendor DomI skills wholesale (DomI no-vendor rule, #326). Copying a *single script* with a
  provenance header + upstream hash is allowed only where a gate depends on it and the task says so.
- Keep PR #29 and DomI PR #504 mergeable; changes here are a follow-up PR unless marked "in #29".

## Out of scope

- Rewriting DomI. The only DomI-side change proposed is wording in `subagent-dispatch-policy` v1.3 to say
  "workerbee (agents_Inc)" so the back-reference is explicit, not a new dependency.
- Publishing a shared skills package (report section C; decision deferred to operator — see below).

## Needs operator decision

`clarify` was skipped by flag (`--skip clarify`) because the input already fixes most decisions. The
questions clarify would have asked are recorded here with a recommended default rather than guessed silently.
Nothing downstream in `plan.md`/`tasks.md` assumes an answer; each item names the task it blocks.

| # | Question | Blocks | Recommended default |
|---|---|---|---|
| D1 | **T3** — delete `grill-me`/`grill-with-docs` from `skills/` and mark them `optional-user-scope`, or keep them as an explicit provenance-headed fork (the speckit-pipeline D35 exception)? They are already drifted from DomI and the installer silently overwrites them each run. | T3 | **(a) delete + `optional-user-scope`.** They are interview aids, not part of the dispatch contract. (Input's own recommendation.) |
| D2 | **Out-of-scope, report section C** — publish a shared skills package so DomI and agents_Inc stop copy-syncing? | nothing in T1–T11 | Defer. Explicitly deferred by the input; no task here depends on it. |
| D3 | **T5** — which caveman level name does agents_Inc standardise on? The upstream governance repo uses a different level; agents_Inc canon says `ultra`. | T5 wording only | Keep `ultra` and state in `CLAUDE.md` that it is agents_Inc's own choice, not an inherited DomI value (the input says "pick one and say it is its own choice"). |
| D4 | **T7** — where do the account facts land: `~/.config/workerbees/roster.md`, or the install receipt? | T7 file path only | Install receipt. It is already generated per-machine, so no new user-scope path or write target is introduced. |
| D5 | **T2** — pin DomI URL sources to a `<sha>` or track a branch? | T2 source form | Pin a `<sha>`. Matches the DomI sync-pin model and keeps the fetch reproducible. |
| D6 | **T11** — are the 6 `test_config_schema.py` failures in scope to fix, or only to file? The input says "own issue". | T11 | File the issue and fix `preflight.sh` (bash 3.2) only. The schema failures are unrelated to decoupling. |
| D7 | **T4/T5** (raised by analyze F6) — T4/T5 edit binding canon (`CLAUDE.md:62`, `:45`, `:9-12`), and making contract element 1 conditional amends constitution P8 ("10 of 14 elements unconditional"). `CLAUDE.md` requires operator sign-off for its own edits. Does the operator sign off, and which `docs/DECISIONS.md` entry records it? Also: `docs/DECISIONS.md:414` D40 is an unrelated ruling while `CLAUDE.md:62` cites "D40" for the handoff-lint gate — duplicate ID. | T4, T5 | **No default offered — this one genuinely needs the operator.** T4/T5 cannot land on sign-off-by-omission. Recommend: operator signs off, a new DECISIONS entry records the P8 amendment, and the D40 label collision is resolved in the same entry. |

## Success criteria

- **SC-001**: On a machine with no DomI checkout and no Codex CLI, a fresh clone reaches green tests, a green
  `governance_demo --fake`, and an exit-0 installer.
- **SC-002**: `grep -rn "/Users/" skills.requirements.txt scripts/install_skills.sh` returns 0 hits.
- **SC-003**: Every DomI-skill reference in repo canon is marked optional and states its fallback.
- **SC-004**: The portability lane is green on a DomI-free, codex-free runner.
