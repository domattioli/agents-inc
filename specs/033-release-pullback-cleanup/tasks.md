# Tasks: 033 release pullback and cleanup

Revised after analyze (.scratch/033/analyze.md, 15 findings).

- [ ] T001 [US1] Re-run the D73 cross-vendor review to a VERDICT; apply changes (main session)
- [ ] T002 [US1] Ship D73 by PR (fold into #151 or follow-up); set status accepted after approve
- [ ] T003 [US2] Locate the dev image; record name and digest; list the fixed check set (suite, plugin tests, each scripts/ stress/proof script) in .scratch/stress/container.md. Image missing: HALT and report (sonnet)
- [ ] T004 [US2] depends T003. Run each listed check in the container; record command, exit code, outcome (sonnet)
- [ ] T005 [US2] Mac: repair, doctor, one pane and one Bash luna dispatch; .scratch/stress/mac.md (main session + operator)
- [ ] T006 [US2] depends T004, T005. Write .scratch/stress/compare.md; verify each difference (main session)
- [ ] T006a [US3] depends T006. Defect found in 0.6.1 code: fix or revert PR to main; else record "no defect"
- [ ] T007 [US3] Collect channel evidence to .scratch/pullback/channels.md: GitHub release, tag, PyPI page, Zenodo record and DOI versions, clones affected (sonnet, read-only)
- [ ] T008 [US3] depends T006, T007. HALT: operator approves (a) tag and release deletion, (b) separately Zenodo and PyPI action
- [ ] T009 [US3] depends T008. Delete the GitHub release, remote tag, local tag; operator does approved Zenodo/PyPI steps in the browser
- [ ] T010 [US4] Worktree status; branch merge evidence: ancestry plus merged PR by head branch (squash); mark branches with an open PR (#151) or recent activity from another session as keep; .scratch/cleanup/delete-list.md (sonnet, read-only)
- [ ] T011 [US4] depends T010. HALT: operator approves the delete list; re-check #151 state at this moment
- [ ] T012 [US4] depends T011. Remove the worktree, prune, delete the approved branches only
- [ ] T013 [US5] Draft close and status comments for in-scope issues to .scratch/issues/plan.md (sonnet)
- [ ] T014 [US5] depends T013. HALT: operator approves closes and status comments; post through GitHub MCP with state_reason
- [ ] T015 depends all. Move specs to DomI (move_specs_to_domi.sh --apply)
