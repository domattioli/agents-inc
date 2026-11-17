---
description: "Implementation plan for repository settings permission hygiene"
---
<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->

# Plan: Settings Permission Hygiene

**Branch**: `004-settings-permission-hygiene` | **Date**: 2026-09-06 | **Spec**: [spec.md](spec.md)

## Summary

Audit repo-local Claude settings. Replace broad or malformed grants with measured, least-privilege routine grants. Reconcile documentation without changing global Claude configuration or credentials.

## Technical Context

**Config**: `.claude/settings.local.json`; other repo `.claude/*.json` if present.  
**Validation**: `jq empty`; fresh-session permission probes; `python3 -m unittest discover -s tests` when code-adjacent docs/scripts are changed.  
**Boundary**: repository working tree only. No `~/.claude/**` reads/writes beyond an operator-provided statement; no provider keys or `.env`.  
**Risk**: Claude `Bash(...)` matching is prefix-like; wildcard grants can include chains/redirection unless negative-tested.  

## Constitution Check

| Check | Status | Evidence |
|---|---|---|
| Repo-only writes | PASS | Feature edits only `agents_for_dummies`. |
| No credentials | PASS | Permission review never opens `.env` or key paths. |
| Least privilege | PASS | Broad SQLite access replaced only after a constrained wrapper/probe exists. |
| Labor rule | PASS | Documentation/planning by main; code/script edits delegated per `CLAUDE.md`, unless operator explicitly overrides. |
| Audience rule | PASS | Human docs nested-notes/caveman lite; specs machine/caveman ultra. |

## Design

1. Inventory config and documented routine commands.
2. Classify each allow rule: valid-needed, malformed, broad/risky, stale, or missing.
3. For each candidate grant, prove positive and adversarial near cases in a disposable repo/session.
4. Use a repo-local read-only helper if direct Bash matching cannot safely express the command.
5. Reconcile dispatch/labor statements into a source table; escalate policy conflicts.
6. Re-parse settings, rerun probes, and review diff scope.

## File Changes

| File | Action | Purpose |
|---|---|---|
| `.claude/settings.local.json` | modify | Least-privilege, validated local approvals. |
| `.claude/permissions.md` | add if needed | Rule-to-tooling matrix and probe results; no secrets. |
| `scripts/claude-permission-*.sh` | add only if needed | Constrained repo-local read/test helper. |
| `CLAUDE.md` | modify only on authorized conflict | Current binding dispatch/labor contract. |
| `docs/DECISIONS.md` / `docs/governance/*` | modify only on authorized conflict | Record resolved policy source or decision request. |

## Verification

1. `jq empty` each repo settings JSON.
2. Assert no allow string ends in UI punctuation, has unmatched quote, or broadly accepts shell control operators.
3. Run positive routine-command probes and negative chain/write/secret-path probes in a disposable repository.
4. Confirm documented command set matches retained grants.
5. Run `python3 -m unittest discover -s tests` if implementation files change.
6. `git diff --check`; `git diff --name-only` confirms repo-only scope.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Repo-local wrapper, conditional | Native Bash pattern cannot safely distinguish read-only SQLite from arbitrary SQL/shell behavior | Broad wildcard access is unverified privilege escalation |
