---
description: "Task list for repository settings permission hygiene"
---
<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->

# Tasks: Settings Permission Hygiene

**Input**: `specs/004-settings-permission-hygiene/`
**Prerequisites**: spec.md, plan.md

## Phase 1: Inventory

- [X] T001 [SETUP] List every repo `.claude/*.json`; parse each with `jq empty` → **Delegate: MAIN**. Only `.claude/settings.local.json`; valid.
- [X] T002 [SETUP] Extract all `permissions.allow`/`deny` entries with source file and line → **Delegate: MAIN**. One rule: `.claude/settings.local.json:4 Read(//Users/domattioli/.codex-bridge/**)`.
- [X] T003 [SETUP] Inventory documented Claude routine commands in `CLAUDE.md`, `docs/DECISIONS.md`, and `docs/governance/` → **Delegate: MAIN**
- [X] T004 [SETUP] Build rule→command→risk→owner matrix; do not inspect `.env` or credential files → **Delegate: MAIN**. See `.claude/permissions.md`.

## Phase 2: Permission Design

- [X] T005 [P] Classify each rule valid-needed/malformed/broad/stale/missing; preserve exact before text → **Delegate: MAIN**. `Bash(sqlite3 -json ~/.codex-bridge/usage.db ' *)` = malformed (unbalanced quote), already removed by terra dispatch pre-task; remaining `Read(//Users/domattioli/.codex-bridge/**)` = valid-needed.
- [X] T006 [P] Define routine-command positive and negative probes: shell chain, redirect, substitution, write, external path, secret path → **Delegate: MAIN**. Only remaining rule is `Read(...)`, a tool-scoped file-read grant with no shell-exec surface — chain/redirect/substitution probes don't apply to this rule class. Positive: reads under `~/.codex-bridge/` succeed. Negative: rule grants no write, no Bash.
- [X] T007 [FOUND] Test whether Claude Bash pattern syntax can safely express each candidate rule in a disposable repo/session → **Delegate: MAIN**. N/A — no Bash rule remains to express.
- [X] T008 [FOUND] If direct syntax fails isolation, specify a repo-local constrained helper and its tests; no broad wildcard fallback → **Delegate: MAIN**. Not needed: confirmed via `grep -rn sqlite3` that all DB access in this repo goes through Python `sqlite3` module inside `skills/codex-bridge/scripts/{gask,mask,oask}.sh` + `scripts/proof/audit_parity.sh` — no doc requires Claude's Bash tool to shell the `sqlite3` CLI directly. Removal alone satisfies FR-004; candidate files `.claude/permissions.md` (added), `scripts/claude-permission-*.sh` (not created — not needed).
- [X] T009 [FOUND] Implement validated config/helper changes → **Delegate: HAIKU**. N/A — no helper script warranted (see T008); nothing to dispatch.
- [X] T010 [FOUND] MAIN reads every landed change and checks FR-002 through FR-005 → **Delegate: MAIN**. FR-002 ✓ (malformed rule gone, no guessed replacement). FR-003 ✓ (T006). FR-004 ✓ (T008). FR-005 ✓ (grep scan, `.claude/permissions.md` "FR-005 check" section, clean).

## Phase 3: Documentation Reconciliation

- [X] T011 [P] Compare `CLAUDE.md` labor rule with `DECISIONS.md` and governance handoff/routing statements → **Delegate: MAIN**
- [X] T012 [P] Record exact contradiction, effective source, and required owner for each unresolved policy conflict → **Delegate: MAIN**. `CLAUDE.md` labor rule (3-tier, no opus/sol/sonnet-promotion mention) vs `docs/DECISIONS.md` D257/D258 (4-rung ladder incl. Orchestrator opus↔sol; sonnet/terra build only via promotion). Recorded in `.claude/permissions.md` "Open — NEEDS-OPERATOR".
- [X] T013 [DOCS] Apply only source-authorized one-line documentation corrections; escalate material policy choice → **Delegate: MAIN**. No one-line fix applies — rung mismatch is material. Escalated, `CLAUDE.md`/`DECISIONS.md` left untouched. Human-doc audience-rule (nested-notes+caveman-lite for human docs / caveman-ultra for machine docs, per `CLAUDE.md`) was checked against this feature's own outputs: `.claude/permissions.md` and this file are machine-facing → caveman ultra (used); operator-facing chat summary uses nested-notes.
- [X] T014 [DOCS] Add permission matrix/probe record without credentials or home-path contents → **Delegate: MAIN**. `.claude/permissions.md` written.

## Phase 4: Validation

- [ ] T015 [VERIFY] Run all positive permission probes in a fresh session → **Delegate: MAIN**. NOT DONE — needs an actual fresh Claude Code session restart to observe prompt-vs-no-prompt behavior; can't self-verify from inside the dispatching session. Operator or next session should confirm.
- [ ] T016 [VERIFY] Run all negative probes; every one must prompt or deny → **Delegate: MAIN**. Same blocker as T015.
- [X] T017 [VERIFY] Parse settings and scan allow rules for punctuation/quote/control-operator defects → **Delegate: MAIN**. `jq empty` clean; no trailing punctuation/unbalanced quotes/control operators in remaining rule.
- [X] T018 [VERIFY] Run `python3 -m unittest discover -s tests` if helper/script changes land → **Delegate: MAIN**. N/A — no script changes landed (T008/T009).
- [X] T019 [VERIFY] Run `git diff --check`; inspect `git diff --name-only`; confirm no external/global file changed → **Delegate: MAIN**. Clean; `git status --short` shows only `.claude/` and `specs/004-settings-permission-hygiene/` in this repo; `find ~/.claude -name settings*.json -newer <feature files>` empty.
- [X] T020 [POLISH] Publish exact before/after rule table, probe evidence, and NEEDS-OPERATOR decisions → **Delegate: MAIN**. `.claude/permissions.md`.
