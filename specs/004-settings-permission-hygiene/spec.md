---
description: "Claude Code repository permission and settings hygiene"
---
<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->

# Specification: Settings Permission Hygiene

**Feature Branch**: `004-settings-permission-hygiene`
**Created**: 2026-09-06
**Status**: Draft
**Input**: Repo-only Claude Code permission/settings review.

## User Scenarios & Testing

### User Story 1 - Safe routine work does not prompt (Priority: P1)

Maintainer runs documented repo inspection and verification commands without needless confirmation. Grants are exact, read-only where possible, and cannot authorize shell chaining or writes.

**Independent Test**: Fresh Claude Code session runs each approved routine command; each is allowed. Near variants that write, chain, access secrets, or leave the repo require confirmation or deny.

### User Story 2 - Settings reflect repo policy (Priority: P1)

Maintainer can trace every local permission to current tooling and labor/dispatch policy. Stale global-path grants, malformed patterns, and obsolete provider assumptions are gone or explicitly deferred.

**Independent Test**: Review table maps every allow entry to an actual command/path, owner, rationale, and negative case.

### Edge Cases

- Permission UI punctuation must never become part of a rule.
- Wildcards must not convert a read/test approval into arbitrary shell execution.
- `;`, `&&`, pipes, redirects, command substitution, and alternate paths must not inherit a routine grant.
- No repo setting reads a key, `.env`, or external home-directory content without explicit documented need.
- Existing user-global Claude settings are out of scope and never modified.

## Requirements

- **FR-001**: Inspect every repo `.claude/*.json` as JSON and enumerate every allow/deny rule.
- **FR-002**: Remove malformed permission rules; retain no guessed correction for a security-sensitive rule.
- **FR-003**: Grant routine commands only after command, arguments, working-directory boundary, and negative cases are tested.
- **FR-004**: Prefer repo-local wrappers or scripts for constrained database/status reads over broad `Bash(sqlite3 *)` patterns.
- **FR-005**: Do not grant reads of `.env`, credentials, home config, or provider key files.
- **FR-006**: Reconcile `CLAUDE.md`, `docs/DECISIONS.md`, and `docs/governance/` dispatch/labor statements; record conflicts with source and owner.
- **FR-007**: Update human docs under the binding audience rule; update machine docs in caveman ultra.
- **FR-008**: No write touches `~/.claude/**`, user-global settings, or files outside this checkout.

## Success Criteria

- **SC-001**: All repo `.claude/*.json` parse with `jq empty`.
- **SC-002**: Every retained allow rule has one documented routine-use case and one denied/confirmation-required near variant.
- **SC-003**: Required routine inspection/test commands run without repeated prompts; no write or secret-read command is newly auto-approved.
- **SC-004**: Dispatch/labor contradictions are either resolved with an authorized source or listed as operator decisions; none is silently rewritten.
- **SC-005**: Diff review proves all writes stayed in this repository.

## Scope

In: repo `.claude` settings, documented Claude Code workflow, permission tests, dispatch/labor documentation reconciliation.
Out: user-global Claude settings, provider credentials, shell-wrapper implementation, model routing changes, commits/pushes.
