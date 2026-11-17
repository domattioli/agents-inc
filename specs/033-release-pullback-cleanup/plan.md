# Implementation Plan: 033 release pullback and cleanup

**Spec**: spec.md · **Date**: 2026-11-07 · Deviation logged: plan and tasks written by the main session (small scope), not dispatched.

## Order and gates

1. D73 ship (US1). Re-run the cross-vendor review of the D73 edit to completion (sol through agents-inc, report file with VERDICT). Apply changes, then fold into PR #151 or a follow-up PR after #151 merges. Gate: review file ends `VERDICT: approve`.
2. Stress, container (US2). Find the existing dev image (`docker image ls`, repo Dockerfile/compose, memory note dev-in-docker 2026-11-03). Copy the repo into the container at `main` plus PR #151 head. Run the unittest suite, `claude plugin test mods/agents-inc` (if Claude CLI exists in the image, else record `not available`), and each stress/proof script in `scripts/`. Write `.scratch/stress/container.md`.
3. Stress, Mac (US2). `agents-inc repair --source ~/Projects/agents_Inc` (operator `!` command if the sandbox blocks), `agents-inc doctor`, one luna pane dispatch, one luna Bash `--slots` dispatch. Write `.scratch/stress/mac.md`. Then `.scratch/stress/compare.md`.
4. Pullback evidence (US3). List channels: GitHub release v0.6.1 (MCP `get_release_by_tag`), PyPI page, Zenodo record linked to the release. Write `.scratch/pullback/channels.md`. HALT for operator approval.
5. Pullback apply (US3, after approval). Delete the GitHub release, then the remote tag (`git push origin :refs/tags/v0.6.1`), then the local tag. Zenodo: owner delete within 30 days (operator, browser). PyPI: yank if published (operator, browser). Code defect found in step 2 or 3: fix or revert PR to `main`.
6. Cleanup evidence (US4). `git -C ../agents_Inc-dev status --porcelain`; branch list with merge evidence (`git branch -r --merged origin/main` plus merged-PR lookup by head branch through MCP). Write `.scratch/cleanup/delete-list.md`. HALT for operator approval.
7. Cleanup apply (US4, after approval). `git worktree remove ../agents_Inc-dev`, `git worktree prune`, `git branch -D` and `git push origin --delete` for approved names only.
8. Issues (US5). For #145, #147, #148, #152 and issues closed by #150, #151, D73: draft close or status comments in `.scratch/issues/plan.md`. HALT for approval of the close list. Post through GitHub MCP with `state_reason`.
9. Final: move specs to DomI (`move_specs_to_domi.sh --apply`).

## Roles

Analyze: opus via agents-inc (read-only). Implement: sonnet via agents-inc, steps 2, 4 evidence, 6 evidence, 8 drafts. Main session: halts, approvals, all irreversible steps, verification of every artifact.

## Risks

- Sandbox blocks docker socket, gh TLS, `.git/config` writes: use MCP for GitHub, ask the operator for `!` commands where the sandbox refuses.
- Deleting the v0.6.1 tag may orphan a Zenodo DOI version; the channels file must show this before approval.
