# Feature Specification: Release pullback, stress tests, and repo cleanup

**Feature Branch**: `033-release-pullback-cleanup`
**Created**: 2026-11-07
**Status**: Draft
**Input**: Ship the D73 Codex lift, stress-test the code in the dev container and on the Mac consumer install, pull back release v0.6.1, clean up merged branches and the stale worktree, and comment on or close open GitHub issues.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ship the D73 Codex lift (Priority: P1)

The operator wants Codex rungs to take any task type, read-only by default, recorded as binding canon.

**Independent Test**: The D73 entry and the AGENTS.md project rule agree on wording, a review from a different vendor than the author ends with an approve verdict, and the change reaches `main` through a PR.

**Acceptance Scenarios**:

1. **Given** the uncommitted AGENTS.md and DECISIONS.md edits, **When** the review runs to completion, **Then** it ends with `VERDICT: approve` or the listed changes are applied and re-reviewed.
2. **Given** an approved review, **When** the PR merges, **Then** D73 status reads accepted with the date and the reviewer.

### User Story 2 - Stress tests in two environments (Priority: P1)

The operator wants evidence that the current code works for a developer (container) and for a consumer (Mac install) before deciding the fate of v0.6.1.

**Independent Test**: Two result files exist, one per environment, each listing every check with pass/fail, and a comparison lists every check whose result differs.

**Acceptance Scenarios**:

1. **Given** the dev container, **When** the full test suite, the mod plugin tests and the stress/proof scripts run, **Then** each result is recorded with its exit code.
2. **Given** the Mac install after repair, **When** doctor runs and one pane dispatch plus one fallback dispatch run, **Then** doctor prints READY and both dispatches reach a terminal state recorded with outcome.
3. **Given** both result files, **When** compared, **Then** every difference is listed with a likely cause.

### User Story 3 - Pull back v0.6.1 (Priority: P2)

The operator wants the release from 2026-11-07 withdrawn so consumers do not install it, without breaking history.

**Independent Test**: The release channels where v0.6.1 appeared show it withdrawn as chosen, and a replacement version is available if one was chosen.

**Acceptance Scenarios**:

1. **Given** the list of channels where v0.6.1 was published, **When** the pullback runs, **Then** each channel shows the chosen state. Mode (operator, 2026-11-07): delete the v0.6.1 tag and GitHub release, local and remote, after operator approval at the delete step; delete or hide any PyPI/Zenodo copy where the channel allows.
2. **Given** stress results show a defect in 0.6.1 code on `main`, **When** the defect is confirmed, **Then** a revert or fix lands through a PR, never a force-push.

### User Story 4 - Branch and worktree cleanup (Priority: P2)

The operator wants only live branches and worktrees left.

**Independent Test**: `git worktree list` shows only the main checkout; every remaining branch is `main`, `development`, or holds commits not in `main`.

**Acceptance Scenarios**:

1. **Given** the detached worktree `../agents_Inc-dev`, **When** it has no uncommitted changes, **Then** it is removed and pruned; **When** it has changes, **Then** cleanup halts and reports them.
2. **Given** a proposed delete list with merge evidence per branch, **When** the operator approves it, **Then** exactly those local and remote branches are deleted.

### User Story 5 - Open GitHub issues (Priority: P3)

The operator wants each open issue either closed with evidence or given a status comment.

**Independent Test**: Every open issue at the start has either been closed with a comment that links the resolving PR or commit, or has a new status comment.

**Acceptance Scenarios**:

1. **Given** a proposed close list with the resolving PR or commit for each, **When** the operator approves it, **Then** those issues are closed with the linking comment.
2. **Given** the remaining open issues, **When** status comments are posted, **Then** each names the current state and the next step. Scope (operator, 2026-11-07): only issues this session's work touched (#145, #147, #148, #152 and any issue resolved by PR #150, #151 or D73).

### Edge Cases

- The dev container is missing or will not build: stress tests halt and report; Mac results alone do not count as the comparison.
- A branch looks merged only by squash: merge evidence must come from the merged PR state, not from git ancestry.
- A branch on the delete list belongs to another live session: it stays.
- PR #151 is still open when cleanup runs: its branch stays.
- The sandbox blocks a network command: use the GitHub MCP route, and report a step that cannot run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The D73 canon edit MUST get a completed review from a different vendor than the author before merge.
- **FR-002**: Stress checks MUST run in the dev container and on the Mac consumer install, with results recorded per check.
- **FR-003**: The Mac check MUST include repair, doctor, one pane dispatch and one fallback dispatch.
- **FR-004**: The v0.6.1 pullback MUST NOT rewrite commits on `main` or force-push. Tag deletion is an accepted history break (operator choice); the halt for it MUST show who is affected (other clones, Zenodo DOI version, PyPI).
- **FR-011**: Zenodo and PyPI state MUST be recorded before any deletion, and their own deletion MUST have a separate operator approval.
- **FR-012**: Merge evidence for squash-merged branches MUST come from a merged PR whose head is that branch; ancestry alone is not enough.
- **FR-005**: Tag deletion, release deletion, branch deletion and issue closure MUST halt for operator approval of an explicit list.
- **FR-006**: Every branch on the delete list MUST carry merge evidence (ancestry in `main` or a merged PR).
- **FR-007**: Worktree removal MUST check for uncommitted changes first.
- **FR-008**: Every issue closure MUST carry a comment linking the resolving PR or commit.
- **FR-009**: A delegate's self-report MUST NOT count as evidence; the supervisor verifies each artifact.
- **FR-010**: The stress run MUST happen before the pullback decision is applied. The dev-side run uses the existing dev image from the dev-in-docker setup (operator, 2026-11-07).

## Clarifications

### Session 2026-11-07

- Q: Pullback mode? → A: Delete the v0.6.1 tag and release.
- Q: Issue comment scope? → A: Only issues this session's work touched.
- Q: Container source? → A: Existing dev image.

### Key Entities

- **Stress result**: environment, check name, command, exit code, outcome.
- **Delete list entry**: branch name, location (local/remote), merge evidence.
- **Close list entry**: issue number, resolving PR or commit, comment text.

## Success Criteria *(mandatory)*

- **SC-001**: D73 reaches `main` with an approve verdict on record.
- **SC-002**: The fixed check list (suite, plugin tests, each `scripts/` stress/proof script found in T003, doctor, pane dispatch, Bash dispatch) has a recorded result in both environments where the check applies; 0 unexplained differences.
- **SC-003**: v0.6.1 tag and release are absent from GitHub and the local repo; any other channel copy is deleted or hidden where allowed.
- **SC-004**: After cleanup, 1 worktree remains and 0 remaining branches are fully merged into `main`.
- **SC-005**: 100% of in-scope issues (Clarifications) are closed with a link or have an approved status comment.
- **SC-006**: 0 irreversible actions run without an approved list.

## Assumptions

- PR #151 merges before branch cleanup, or its branch stays.
- v0.6.1 is the only release made on 2026-11-07.
- Roles: opus runs analyze, sonnet runs implement, the main session supervises and verifies.
- Untracked `.specify/` and `specs/` move to DomI as the final task.
