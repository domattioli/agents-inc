<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Analyze report: 013 at_route hardening

Run by the Workhorse analyst (sonnet) on 2026-10-01 for the Supervisor. Cycle 1 of 2. Read-only: no artifact or code was edited. Checkbox state in tasks.md was ignored. Tags: [verified] means read in code or run; [inferred] means reasoned from code.

## Open questions in the dispatch

- Dispatch gave no analyze phase pre-hook file; `.specify/extensions.yml` was not looked for (repo has no `.specify/`, per dispatch). Assumed no hooks.
- Constitution path was given as unratified, so every violation is WARN. No constitution finding below is CRITICAL.
- `checklists/requirements.md` was not in the dispatch artifact list; not analyzed.
- The dispatch said `git status --porcelain` may differ only inside the spec dir. The live status also shows ` M skills/codex-bridge/tests/at_route.smoke.sh` (T002, Supervisor-owned, not in the dispatch snapshot). Treated as Supervisor work, not mine. [verified: git status]

## Findings

| ID | Severity | Finding | Recommended resolution |
|---|---|---|---|
| A1 | HIGH | Contradiction on inherited `MODEL`. spec.md:95 (US4 scenario 2) says that with `MODEL=openai/gpt-4o-mini` "no non-free model is called and the failover block tells the session model to answer". But FR-010 (spec.md:134), plan.md:42 (DD3 `env -u MODEL`), and tasks.md:15 case (l) clear `MODEL`, so `oask.sh` picks its own free model (`oask.sh:23-25`) and the call succeeds with a normal box. No failover occurs. SC-005 (spec.md:156) is satisfied either way. | Reword spec.md:95 to: "`MODEL` is ignored, the stub sees it unset, and the answer comes from the free-tier pick." Keep case (l). |
| A2 | HIGH | `rollback` is used with two meanings. spec.md:79 (US3 scenario 3), :80, :128 (FR-004), :131 (FR-007) say `uninstall` or `rollback` removes owned entries and `rollback` restores the legacy file. The `rollback` command only swaps the `current` symlink (`agents_inc/install/cli.py:123-130`, plan.md:46 admits this). Journal recovery is a different mechanism (`transaction.py:52-77`) and runs only on an interrupted install. As written, an operator reading FR-007 expects `agents-inc rollback` to bring back the legacy file; it will not. After a committed install, nothing restores the legacy file or its settings line. | Edit spec.md US3 AS3/AS4, FR-004, FR-007 and Clarification Q4 to name "journal recovery of an interrupted install" and drop `rollback`/`uninstall` restoring the legacy file. State plainly that uninstall removes owned entries and does not recreate the legacy copy (consistent with plan.md:45 and CHK011). Add the backup path to the install notice so the operator can restore by hand. |
| A3 | HIGH | SC-004 (spec.md:155, "settings file byte-identical after install then uninstall") does not hold in general. (1) `strip_hooks` leaves an empty `"hooks": {}` when the last event is removed (`host_wiring.py:85-87`; existing test asserts exactly `{"hooks": {}}`, `tests/test_install_host_wiring.py:80`). A pre-install file with no `hooks` key therefore changes. (2) Install and uninstall rewrite through `json.dumps(indent=2)` (`host_wiring.py:111`), so a hand-formatted settings file changes bytes. (3) In the legacy case the legacy settings line is removed by DD5 and never restored. | Scope SC-004 to "a settings file already in canonical indent-2 form that already has a `hooks` object and no legacy line", or make `strip_hooks` delete an emptied `hooks` key and update the test at `test_install_host_wiring.py:80`. State which in spec and T003. |
| A4 | MEDIUM | `wiring_problems` regression risk. DD4 makes `_owned` match the at_route command (plan.md:43). `wiring_problems` passes if `any(_owned(c))` over all hook commands (`host_wiring.py:184`). After the change, a Claude settings file holding only the at_route entry passes `WB_HOST_UNWIRED` even if the SessionStart hook is gone. Opposite also true: nothing checks that the at_route entry or the 11 links exist, so a deleted entry or link is invisible to doctor. No FR or task covers this. | Add to DD4/T005: keep the SessionStart check keyed on the `<launcher> hook ` prefix, and add an optional warning (for example `WB_HOOK_UNWIRED`) when the at_route entry or any alias link is missing. Or record in spec that doctor does not check them (INFO). Add a T003 case either way. |
| A5 | MEDIUM | FR-005 (spec.md:129) says the settings hook timeout "MUST exceed `AT_ROUTE_TIMEOUT`", but DD4 fixes it at 130 (plan.md:43) while the alarm is an env var (`at_route.sh:18`). A caller who sets `AT_ROUTE_TIMEOUT=200` breaks the invariant, and the host kills the hook before the alarm message prints. Also `oask.sh` has its own `OASK_TIMEOUT` default 180 (`oask.sh:33`) that is above the 120 s alarm, so the alarm always wins for `@openrouter`. | Reword FR-005 to "exceeds the default `AT_ROUTE_TIMEOUT` (120)" and note in AT-ROUTE.md that raising the env value needs a matching settings timeout. |
| A6 | MEDIUM | `--no-host-wiring` and non-Claude installs are unspecified for aliases. DD6 (plan.md:45) says call `install_alias_links` "when host wiring is on and the Claude host is detected". Spec FR-004 says only "install and repair". The Codex-only, Gemini-only, and `--no-host-wiring` cases have no stated outcome, and `cli.py:25` gates wiring on `--no-host-wiring` (verified). | Add one Edge Case line and one T003 case: aliases are created only with host wiring on and `~/.claude` present; otherwise none, and no error. |
| A7 | MEDIUM | Receipt duplicate risk on reinstall. `cli.install` carries prior ownership forward (`cli.py:49`), and `install_host_wiring` strips only `block`/`hooks`/`context` kinds (`host_wiring.py:139`), so prior `symlink` items stay. DD6 says "symlink to the desired path, keep" but does not say the new `OwnedPath` is skipped when already recorded. `install_skill_links` guards this (`discovery.py:30`); `install_convenience_launcher` replaces explicitly (`cli.py:53-54`). Without a guard, repair doubles the 11 entries. | Add to DD6: append only when the path is not already in `receipt.owned_paths`. Add a T003 case: install twice, receipt has exactly one entry per alias. |
| A8 | MEDIUM | `source-checkout` state file (DD8, plan.md:47) is outside both the journal and the receipt. It is written at install, never removed by uninstall (`cli.py:76-91` removes only receipt items), and not restored on journal recovery. FR-004 and SC-004 speak of "exactly the owned entries". It also leaves a stale path after the checkout is deleted (covered by `WB_HOOK_DRIFT_UNCHECKED`). | Write it through `write_file` with the journal, and delete it in uninstall; or state in the plan that it is an unowned cache that uninstall leaves. T003 should assert one of the two. |
| A9 | MEDIUM | Doctor output format change. `agents-inc doctor` prints `READY [WARNING: ...]` when warnings exist (`cli.py:80-83`). Every pre-013 install now gets `WB_HOOK_DRIFT_UNCHECKED` until `repair` runs, so the documented health check (AGENTS.md and the host block text, `host_wiring.py:43`, "expect `READY`") will no longer print a bare `READY` on any existing machine, including the Executive's. Exit code stays 0. [inferred: no script compares the string; grep found none in repo code outside specs] | Note in spec that the first doctor after upgrade shows the unchecked warning and `repair` clears it. Tell the Executive to run `repair` before the next `doctor`. |
| A10 | LOW | Legacy-line strip is permanent. DD5 (plan.md:44) puts the legacy command inside `strip_hooks`, which `remove_host_wiring` also calls (`host_wiring.py:171`). A foreign legacy line the operator re-adds later is silently stripped on uninstall and on every repair. | Limit the legacy strip to the install path (a flag on `strip_hooks`) so uninstall touches only the owned command. |
| A11 | LOW | Line-number citations in spec.md are off by one or two against HEAD: spec.md:11 says alarm at `at_route.sh:73-75` (actual `:72-74`, plan.md:28 is right) and failure block `:145-150` (actual `:145-151`); spec.md:14 says doctor bundle check at `doctor.py:27` (actual `:29`, with `:30` the `current` check). Host wiring `:37`, `host_wiring.py:89-95`, `oask.sh:23-25`, `:43-46`, `:286`, `:7-10`, `bundle.py:16` check out. [verified] | Fix the three citations in spec.md. |
| A12 | LOW | Stale comment becomes a second source of the old design. `at_route.sh:11-13` says the hook "may be installed as a copy under ~/.claude/scripts" and `:14-16` keep an `AT_ROUTE_BRIDGE_DIR` and `$HOME/Projects/agents_Inc` fallback. FR-008 retires that copy, but no task edits these lines, and the fallback silently points a copy at the checkout. | Add to T004: rewrite that comment, or keep the fallback and say it is for ad-hoc copies only. |
| A13 | LOW | Relay line and answers log use the same `$model` as the box header (`at_route.sh:117`, `:127`). FR-011 (spec.md:135) and US4 AS1 cover only the box header. DD3 sets the display model in the shared variable, so all three show the resolved id. Not stated in spec. | Add one clause to FR-011: relay line and `at_route_answers.log` show the same model id. Optional smoke assertion in case (n). |
| A14 | LOW | T004 (tasks.md:20) gives a Grunt (haiku) three changes: new flags, a timeout block, and a new provider branch with stderr parsing and `env -u`. AGENTS.md says free Grunt coding is limited to "small, narrow diffs with fixed scope", and design or scope judgment belongs at Workhorse. Constitution P2 (labor ladder) is a MUST, unratified so WARN. The parse step and the exit-142 rule across all alias kinds (including `rc` reset paths at `at_route.sh:85`, `:100`) need judgment. | Split T004 into DD1+DD2 (haiku) and DD3 (sonnet), or justify haiku in the task. T002 verifiers already cover the risk. |
| A15 | LOW | `rc == 142` is treated as a timeout (DD2, plan.md:41). A child that itself exits 142 is mislabeled. The gemini and mistral branches also convert some failures to `rc=1` (`at_route.sh:85`), so they are never labeled correctly if the alarm fires after output. Rare. | Accept and note under Edge Cases, or time-check `elapsed >= TIMEOUT_S` as a second condition. |
| A16 | LOW | T008 (tasks.md:30) gates on `git diff --stat agents_inc/free_health.py` equal to "41 insertions" and on exactly one known failing test. Both belong to peer-owned, moving files. A peer edit makes the gate red for reasons outside this feature. | Compare against the pre-dispatch hash or `git diff` bytes of the peer files, or say "unchanged by this batch". |
| A17 | LOW | Smoke test hardcodes `total=19` (`at_route.smoke.sh:12`). T002 adds cases (h) to (o). The pass line will misreport unless the Supervisor updates the constant. | Mention in T002 success: `total` updated. |
| A18 | INFO | CHK018 stays open (checklist install-safety.md:35): grandchildren of `claude` survive the alarm. Read-only flags (DD1) reduce the damage. `--tools`, `--disallowedTools`, and `--strict-mcp-config` all exist in the installed CLI (`claude --help`, [verified]). Read-only still lets the routed model read any file the caller can read, including secrets in the working tree; the spec does not address read exposure. | Keep accepted. Optionally add one Edge Case line on read exposure. |
| A19 | INFO | LESSON-CANDIDATE: `skills/codex-bridge/SKILL.md:260` still says "Copy or link the script to `~/.claude/scripts/at_route.sh`" and FR-014 plans only the lexicon row. After this batch the install section there contradicts docs/AT-ROUTE.md (peer-owned file, BLOCKED-PEER). Target canon file: `skills/codex-bridge/SKILL.md` Install paragraph. Relay one rung up; do not file sideways. | Add the Install paragraph to the T007 BLOCKED-PEER scope. |
| A20 | INFO | Spec says the source of #41 evidence (`~/.codex-bridge/at_route.log`) was quoted from the issue, not re-read (spec.md:12). [assumed] I did not re-verify it either. | None. |

## Verified plan claims (no finding)

- Claude branch has no restriction: `at_route.sh:79-80`. Alias regex lacks `openrouter`: `:43`. Failure block: `:145-151`. Header: `:138`. Relay: `:127`. [verified]
- `install_at_route.sh:5-10` copies and links ten aliases. [verified]
- `host_wiring.py:71-95`, `:113-136`, `:138-158`; `discovery.py:33-48`; `transaction.py:52-77`; `cli.py:76-91`, `:123-130`; `doctor.py:19`, `:31`; `receipt.py:32-60`; positional receipt rebuilds at `cli.py:49`, `:54`, `discovery.py:31`, `host_wiring.py:158`; `hook.py:30-40` always returns 0. [verified]
- `oask.sh` resolves `REPO_ROOT` as three levels above its directory (`oask.sh:20`), which is the release root in the installed layout and holds `agents_inc` (allowlist, `bundle.py:16`). [verified]
- `OwnedPath`'s `predecessor` of `None` for relinked legacy links matches `restore_skill_links` (`discovery.py:45`). [verified]

## Coverage

FR-001 to FR-016 each map to at least one task (tasks.md:34-46): 16 of 16 covered, 0 unmapped tasks (T001 to T008 each cite an FR or SC). Weak spots: FR-008 has only a manual stub check (T006); doctor wiring checks (A4) have no FR. FR-014 is half `BLOCKED-PEER`.

Constitution: unratified, WARN only. P0, P1, P4, P5, P9 hold. P2 WARN for T004 (A14). P3 holds (Supervisor writes verifiers, others implement). No CRITICAL.

Metrics: 16 FR, 6 SC, 8 tasks, 20 findings: 0 CRITICAL, 3 HIGH (A1-A3), 6 MEDIUM (A4-A9), 8 LOW (A10-A17), 3 INFO (A18-A20).

Result: resolve A1 to A3 before implement; A4 to A9 should be settled in spec or plan text; the rest are optional.

## Resolution (Supervisor, cycle 1, 2026-10-01)

All findings were resolved by editing artifacts; no finding needed code to resolve. Cycle count: 1 of 2.

| ID | Resolution |
|---|---|
| A1 | spec US4 AS2 now says `oask.sh` receives no `MODEL`; new AS4 covers the failover on non-zero exit (smoke cases l, m). |
| A2 | spec FR-004, FR-007, US3 AS3/AS4 now bind "rollback" to journal recovery of an interrupted install; Edge Cases state what `agents-inc rollback` and uninstall do with the legacy file. |
| A3 | SC-004 reworded: byte-identical for installer-style JSON without a legacy line; the empty `hooks` residue (pre-existing since dd48471) is the one allowed difference; a legacy line is migrated, not restored. Test `test_install_then_uninstall_is_byte_identical` asserts exactly that. |
| A4 | plan DD5: `wiring_problems` keeps the launcher-hook test. |
| A5 | FR-005 now names the default (120 s); docs must say a raised `AT_ROUTE_TIMEOUT` needs a matching settings timeout (T006). |
| A6 | Edge Case added; test `test_no_host_wiring_creates_no_alias_links` added to T003. |
| A7 | plan DD6 dedupe; test asserts unique receipt paths after two installs. |
| A8 | plan DD8: unowned cache, left by uninstall. |
| A9 | Edge Case added; reported to the Executive. |
| A10 | plan DD5: legacy strip on install and repair only. |
| A11 | spec citations fixed. |
| A12 | T004 rewrites the stale comment (plan DD3). |
| A13 | FR-011 clause added. |
| A14 | Kept on haiku with stated reason in T004; D27 promotion path named. |
| A15 | Accepted (plan DD2a, Edge Cases). |
| A16 | Gate is set by the dispatch; kept. |
| A17 | `total=19` already set in T002. |
| A18 | Read-exposure Edge Case added; CHK018 stays accepted. |
| A19 | T007 (BLOCKED-PEER) now includes the install paragraph; relayed to the Executive as LESSON-CANDIDATE. |
| A20 | None. |

Open after resolution: 0 CRITICAL, 0 HIGH.
