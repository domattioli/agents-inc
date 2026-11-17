<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# 007 — Tasks

Machine doc. Caveman ultra. **Gates live HERE and only here** (`spec.md` points at task IDs, does not restate — fix for analyze D1, dogfoods P0). `[P]` = parallelizable, disjoint files. Delegate tag = model of record per contract element 11.

Baselines captured 2026-09-06 by run root (fix for U2/U3):
- `CLAUDE.md` "Delegation prompt contract" section = **569 words** pre-edit.
- `pip freeze | wc -l` = **28** pre-edit.
- `python3 -m unittest discover -s tests` → **`Ran 425 tests`** / **`OK`** (summary line, NOT a test's stdout print).

## Phase 0a — cross-repo (independent; run FIRST, dead paths mislead readers now — fix for I1)

- [ ] **T011** DomI PR, branch `fix/workerbee-canonical-source` → `development`, `CLAUDE_BRANCH_OVERRIDE=1`. One PR, all 4 changes, framed single-purpose "reconcile workerbee canonical source". Delegate: **run root** (cross-repo + outward-facing, not delegable).
  - (a) 3 dead `~/Projects/workerbees` refs → `~/Projects/agents_for_dummies` (`MANIFEST.md:212`, `skills/workerbee/SKILL.md:22`, `:122`)
  - (b) delete stale `MANIFEST.md:216` stub-dir cleanup note (dir absent)
  - (c) port poll-every-dispatch discipline (DomI `grep -c poll` = 0, ours = 4)
  - (d) add inbound-source policy (DomI IMPORTING an external skill; current rule covers only skills going OUT)
  - PASS: one PR into `development`; all 4 present; DomI CI compliance lanes green; zero consumer-repo files touched. **Re-verify each cited path:line at execution time before editing** — line numbers drift (fix for V3/CH016).
  - FAIL: any consumer repo written; CI red; `--force`; admin-merge; any cited location edited without re-verifying it first.

## Phase 0b — authority (blocks phase 2)

- [ ] **T001** Amend `.specify/memory/constitution.md` P10: Supervisor may delete prose once a landed test enforces the same rule, citing that test + its green result. Bump `version` 1.5.0 → 1.6.0 (MINOR), set `last_amended`. **Cite the authorizing `docs/DECISIONS.md` D-number** — `constitution.md:67` mandates this on every amendment (fix for C1). D31 authorizes the lesson-routing scope P10 covers. While here: `constitution.md:51/55/59` record P8/P9/P10 authority as "not yet a D-number" — D29/D30/D31 were minted today and now supply them. Delegate: **run root** (constitution amendment, not delegable).
  - PASS: P10 states delete authority AND the cite-the-enforcing-test requirement; `version` = 1.6.0; `last_amended` set; an authorizing D-number cited; P8/P9/P10 stale "not yet a D-number" notes replaced w/ D29/D30/D31; Enforcement still reads P0-P10.
  - FAIL: authority stated without the cite-the-test requirement; version not bumped; no D-number cited (would itself violate `constitution.md:67`).

## Phase 1 — enforcement (blocks phase 2 prune of anything it covers)

- [ ] **T002** [P] Duplicate-block test → `tests/test_canon_dedup.py`. **Block set defined** (fix for A5): normalized-whitespace hash of each `##`-level section body in `CLAUDE.md`, `CONTEXT.md`, `AGENTS.md`, `.specify/memory/constitution.md`, `docs/governance/ROUTING-RANKING.md`, `skills/workerbee/SKILL.md`. Fail if any two files share a normalized block hash. Granularity = whole section body, not line. Delegate: **haiku** (build) → **sonnet** (review; cross-model, not self-grade).
  - PASS: fails on a deliberately re-duplicated section; passes on clean tree; suite ≥ 426, `OK`.
  - FAIL: passes while duplication present.
- [ ] **T003** [P] Dispatch-contract checker → `skills/workerbee/scripts/check_dispatch_prompt.py` + `tests/test_dispatch_contract.py`. Reads a prompt file, reports which of 14 elements missing. NO new skill. **Do NOT edit `skills/workerbee/SKILL.md`** — the Step 11 reference to this script is inserted by T008, which owns that file (fix for I2). Delegate: **haiku** (build) → **sonnet** (review).
  - PASS: flags a prompt missing any of the 14; accepts explicit `not applicable` as satisfying elements 10/11 ONLY; rejects silence for those two; rejects N/A for any unconditional element; suite `OK`; `skills/workerbee/SKILL.md` untouched by this task.
  - FAIL: false GREEN on a non-compliant prompt; N/A accepted for an unconditional element; SKILL.md modified here.
- [ ] **T004** [P] Schema-harden `workerbees/{governance,models,protocols,routing}.json` via stdlib `dataclasses` + `tests/test_config_schema.py`. Delegate: **sonnet**.
  - PASS: all 4 validate; malformed copy raises; `pip freeze | wc -l` still **28** (baseline above).
  - FAIL: any third-party dep added; any file's real shape uncovered.

## Phase 2 — prune (requires T001 AND phase 1 — fix for I3; each prune cites its enforcing test or verified single owner)

- [ ] **T005** [P] `AGENTS.md`: delete copied audience table (~lines 10-19), keep all 4 `CODEX_BRIDGE_MODE` bullets, replace table w/ 1-line pointer to `CLAUDE.md`. Delegate: **haiku**.
  - PASS: `grep -F` of table row text in `AGENTS.md` → 0 hits except pointer; 4 `CODEX_BRIDGE_MODE` bullets byte-intact; T002 test green.
  - FAIL: any row still literal; any bullet lost.
- [ ] **T006** `CLAUDE.md:18-23` rung table: de-duplicate ONLY the rung↔pair mapping vs `docs/governance/ROUTING-RANKING.md`. **KEEP `Does` + `Children?` — they exist in no other file.** Delegate: **sonnet** (judgment).
  - PASS (mechanical — fix for A4): `grep -F` hits post-edit for all 8 protected cells — `final say, risk eval, conflicting results, irreversible acts` / `decompose, dispatch, complex planning` / `build only via promotion` / `routine code writing, classification, summarization`, and the 4 `Children?` values (`yes`, `yes`, `leaf`, `leaf`) still readable per-rung. ROUTING-RANKING unique columns untouched.
  - FAIL: any of the 8 protected cells unreadable post-edit.
- [ ] **T007** `CLAUDE.md` "Delegation prompt contract" → bare 14-item enumeration (names only, no rationale). `skills/workerbee/SKILL.md` Step 11 becomes sole owner of wording + rationale. Delegate: **opus** (binding operator-ruled text, highest meaning-loss risk).
  - PASS: section word count < **285** (i.e. >50% drop from the 569 baseline above); all 14 substantive requirements present in Step 11; `grep -F` hit for EVERY copy-me literal: `Message to model provider: Do not use this to train agentic models.`, `SECOND-OPINION JUSTIFICATION: not applicable`, `PLAN CONTRACT: not applicable — deliverable is not a plan`, `effort control unavailable on this transport`, `low|medium|high|xhigh|max|ultra`, `low|medium|high|xhigh|max`.
  - FAIL: any requirement absent from both copies; any literal broken by line-wrap.
- [ ] **T008** Apply `specs/007-canon-consolidation/step11_compressed.md` (in-repo, 1089 words vs 1527 original — fix for A1) to `skills/workerbee/SKILL.md` Step 11. **Sequence: after T007 AND after T003** (both interact w/ this file — fix for I2). Also insert the Step 11 reference to T003's checker script here. Delegate: **run root** (drafted + literal-verified).
  - PASS: same `grep -F` literal list as T007 all hit; element count reads 14 everywhere (zero "twelve"/"13-element"/"12-element"); Step 11 references the checker script; no normative content lost.
  - FAIL: any normative loss; any literal broken.

## Phase 3 — naming

- [ ] **T009** Rename plural skill dir `skills/workerbees/` → **`skills/doc-analysis/`** (target pinned — fix for A3) + frontmatter `name: workerbees` → `doc-analysis`. **THIRD REQUIRED EDIT (fix for U1): `tests/test_gen_stubs.py:12`** asserts `{".claude/skills/workerbees/SKILL.md", ".agents/skills/workerbees/SKILL.md"}`; `workerbees/hosts/gen_stubs.py:15` derives stub path from `canonical.parent.name`, so the dir rename changes generated paths and turns that test RED unless updated. **Do NOT touch** python package `workerbees/` or the `python3 -m workerbees.pipeline` entrypoint. Update refs: 14 occurrences / 6 lines across `tests/test_gen_stubs.py` (1) and `docs/superpowers/plans/2026-09-05-phase-1-pilot.md` (5) — count is occurrences, not lines (fix for A2). Delegate: **haiku** (mechanical) → **run root** verify.
  - PASS: `skills/doc-analysis/SKILL.md` exists w/ matching frontmatter; `test_gen_stubs.py` updated and green; `python3 -m workerbees.pipeline --help` still resolves; suite ≥ 426, `OK`.
  - FAIL: any python import/entrypoint broken; package dir renamed; `test_gen_stubs.py` left RED.
- [ ] **T010** `skills/doc-analysis` lacks `version:`/`benchmark:` frontmatter; other 3 skills have both. Delegate: **NEEDS-OPERATOR**.
  - Operator question: apply DomI's benchmark mandate in this repo, yes or no? (fix for U4 — two acceptable answers, gate is the answer itself.)
  - PASS: operator answers; if yes, fields added + a `tests/benchmark.md` row created.

## Process gates — owned by run root at close-out (fix for V1/V4; these are not delegable tasks)

- [ ] **T012** Run root verifies at feature close: every edit was surgical not whole-file-rewrite where a targeted edit gave the identical result (P9 / CH011); every dispatch prompt issued for 007 carried all 14 elements (CH017) — verified with T003's checker once it exists; every delegate claim independently re-verified before relay to operator (CH018 / P3).

## Not tasks (operator decisions)

Listed once in `spec.md` "Out of scope" — not restated here (fix for D2).
