<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Research: Measured status (spec 042)

Phase 0 output of `speckit-plan`. For each functional requirement this file records whether the behaviour exists in code today, with file:line evidence read on 2026-11-15 from the `development` checkout. States: **present** (no work planned), **partial** (work planned for the gap only), **absent** (work planned). Line numbers are from the files as read; they drift as soon as code changes.

## Decisions that shape every phase

### R1. `unverified` already exists; this spec changes its exit code

- Decision: keep the existing outcome word `unverified` (it is not new) and give it a new exit code `4` (`EXIT_UNVERIFIED`). Exit codes 0 (green), 1 (red), 2 (child usage error), 3 (refused), 69 (blocked), 75 (quota-paused) and 130 (cancelled) stay as they are.
- Evidence: `_outcome` already returns `("unverified", "no-gates")` at `agents_inc/install/dispatch.py:1403`; `_exit_code` maps every non-red outcome to 0 at `dispatch.py:1465-1468`; codes are defined at `dispatch.py:37,56-57`; `tests/test_dispatch_grants.py:516` asserts `(0, "unverified", "no-gates")`; the broker reads `unverified` only when the child exit code is 0 (`dispatch.py:2363-2365`, `REQ_GREEN`), and `mcp_broker.py:190` treats `unverified` as not an error. D58 states "New outcome `unverified` (reason `no-gates`, exit 0)".
- Rationale: the clarified answer asks for a non-zero code distinct from red. Code 4 is not used by `dispatch` today (the only `rc == 4` in the tree is the free wrapper's own code, `agents_inc/install/free_launch.py:247`, which dispatch classifies and never passes through). The change amends D58, so it needs D84.
- Alternatives considered: a new word such as `not-checked` (rejected: the operator fixed the word `unverified`, and it is already in callers); exit 0 kept with a status-line flag (rejected by the clarification).
- Consequence: every caller that reads exit 0 as "returned" must accept 4: the broker `_req_status` and `REQ_STATUS` map (`dispatch.py:2360-2365`), `_run_end_outcome` (`dispatch.py:1842`), `mcp_broker.py:190`, `QUICKREF.md` ("Exit 0 means returned, not verified"), the delegate-pane start and resume readers (`mods/delegate-pane/hooks/controls.tsx:39` and `:177`, which label every nonzero exit `failed`), and non-git read-only runs, which end `unverified reason=snapshot-skipped` (`dispatch.py:1530-1532`) and will now exit 4 too.

### R2. "Not checked" replaces `gate-missing` for a gate that could not start

- Decision: a gate whose binary is missing or not executable (`FileNotFoundError`, `PermissionError`, the pre-launch `shutil.which` miss at `dispatch.py:1331-1332`) becomes state `not-checked`, reason `gate-not-runnable`. A gate killed by its timeout becomes `failed`, reason `gate-timeout` (spec edge case). A gate refused by the post-run re-screen (`dispatch.py:1318-1322`) stays `failed`, reason `gate-refused`, because the refusal is itself a measured security finding.
- Evidence: today any `rc is None` row returns `gate-missing` before any failed row is considered (`dispatch.py:1351-1354`); that is the cause of the evidence row "`reason=gate-missing` although three gates were supplied and two failed".
- Rationale: FR-002, FR-003, FR-011. Amends D58 ("A gate that cannot run (missing binary, timeout, refused) is red `gate-missing`"), so it needs D84.
- Alternatives considered: keep `gate-missing` as the reason word (rejected: FR-011 asks for a word that describes the condition; "missing" reads as "no gate supplied").

### R3. Scope check: outside-scope changes end `unverified`, never green

- Decision: the snapshot verify keeps its single allow list (FILES_IN_SCOPE). A changed path outside FILES_IN_SCOPE no longer ends `red snapshot-not-clean`; it ends `unverified` reason `scope-foreign-change`, lists the paths with `attribution=unknown`, and keeps the gate results. Inside-scope changes stay allowed. There is no second "declared change" list in this release.
- Evidence: the slots have one scope list (`dispatch.py:1879`, `allow_paths(FILES_IN_SCOPE)`); `_snapshot_verify` passes it as `--allow` (`dispatch.py:1248-1250`) and reports `CHANGED:<paths>` (`dispatch.py:1255-1256`); `_outcome` turns any non-zero verify into `red snapshot-not-clean` (`dispatch.py:1397-1398`).
- Rationale: the amended FR-005 specifies a two-way split (inside scope, outside scope) and ends an outside change `unverified`, with attribution unknown. A second list of declared changes would let a delegate's own out-of-scope write pass as "another party". `unverified` satisfies "do not alone make the run fail" and keeps the run from reading as passed. The P1 repo-scoped-write rule is kept.
- Attribution: the harness cannot name a gate as the author of an outside change. `dispatch.py:1496-1499` labels any outside change first seen after the gates `gate-wrote`, by timing only, with no author evidence; a neighbouring session writing during a gate would turn the run red. `gate-wrote` is therefore retired and such a change is `scope-foreign-change`.
- Detection: `_snapshot_verify` today reads only `CHANGED ` lines (`dispatch.py:1255`) and turns a nonzero verify without them into `ERROR` (`1256`), so the verify output change to `OUTSIDE ` lines needs a matching reader change there. The verify also skips allowed paths (`pre_dispatch_snapshot.py:122`); for the claim check and the in-scope list it compares baseline and final hashes for in-scope paths as well, and a final `git status --porcelain` alone is never evidence of a change in this run.
- Alternatives considered: a `DECLARED_CHANGES` slot (rejected for this release: D70 schema change, and spec Assumptions say the slots schema is not redefined); green with a warning (rejected: removes the scope gate).

### R4. A declared stop is a reason, not a new outcome word

- Decision: a delegate that ends at a declared stop writes `stopped: <rule text>` in its report block (contracts/claims-block.md). Dispatch then ends `unverified` reason `delegate-stopped`, keeps collected gate results, and exits 4. No new outcome word.
- Rationale: spec Assumptions (line 240) allow one new exit code and no other new outcome word; `unverified` is the honest state ("the work was not completed, so nothing vouches for it") and is distinct from red (FR-008).
- Alternatives considered: outcome `stopped` (rejected: second new word).

### R5. Claim check is deterministic and advisory

- Decision: new module `skills/workerbee/scripts/check_claims.py` (pinned with the other scripts per run, like `check_dispatch_prompt.py`). Input: the report text, the baseline-to-final hash comparison from the snapshot verify (a final `git status --porcelain` alone is not evidence, because it cannot tell an inherited dirty file from one changed this run), and `gate_results`. Output: a list of claim results. Dispatch writes them to `claims.json` in the run directory, to `run.json` key `claims`, to the status line as `claims=<n> unsupported`, and to the return row. Never changes the outcome (clarified answer).
- Rationale: FR-012, FR-016. Standard library only.

### R6. doctor dispatch-path test uses the existing CONNECT probe

- Decision: `doctor` gains a `dispatch-path` item: `claude` resolvable (exists, `doctor.py:196`) plus `api_reachable()`-style HTTP CONNECT to `api.anthropic.com:443` when a proxy is set, or a TCP connect otherwise (the probe of D71 F1, `dispatch.py` `api_reachable`). Cost: no model call, $0. The existing Codex PONG under `--live-model` (`doctor.py:209-218`) stays opt-in. If no probe can run, the item is `could-not-test` and the overall result is not READY.
- Alternatives considered: a `claude -p` PONG on every doctor run (rejected: uses subscription quota on every start).

## Per-requirement findings

Verdicts

- FR-001 — partial. Run outcomes are `green`, `red`, `unverified` plus refusal/cancel words (`dispatch.py:1377-1403`, `1737-1748`). Gate rows have `rc`, `expect_rc`, `error` but no `state` field (`dispatch.py:1313-1314`). Work: add `state` to each gate row; route all not-checked conditions to `unverified` (Phase 1).
- FR-001a — absent. `unverified` exits 0 (`dispatch.py:1465-1468`). Work: `EXIT_UNVERIFIED = 4` (R1, Phase 1).
- FR-002 — partial. A missing binary is detected (`dispatch.py:1331-1332`, `1345-1346`) but reported as red `gate-missing` (`dispatch.py:1351-1352`). Work: R2 (Phase 1).
- FR-003 — partial. `gate_results` with argv and rc are in run.json (`dispatch.py:1490`), but the status line has no per-gate entry (`dispatch.py:1414-1420`). Work: status line `gates=` token and a `gates.txt` block, failed and not-checked first (Phase 1).
- FR-004 — partial. No gates already ends `unverified no-gates` (`dispatch.py:1401-1403`). All gates not-checked ends red `gate-missing` today. Work: R2 makes the all-not-checked case `unverified` (Phase 1).
- FR-005 — partial and changed by the plan. One allow list exists (`dispatch.py:1248-1250`); outside-scope changes end red (`dispatch.py:1397-1398`). Work: R3 (Phase 1). The split is two kinds: inside scope and outside scope (R3). An outside change ends `unverified scope-foreign-change`.
- FR-006 — absent. `CHANGED:<paths>` carries no attribution (`dispatch.py:1255-1256`). Work: `attribution=unknown` on every changed path in the status and run.json (Phase 1).
- FR-007 — present. Quota is the first check in `_outcome` (`dispatch.py:1377-1378`), and quota text is read from stdout and stderr whenever the report has no `WORKERS SPAWNED` line (`dispatch.py:1505`, `1511-1512`), which is the evidence case (usage limit reported as `workers-spawned-missing`, 2026-10-04). No work beyond one regression test in Phase 1 for SC-001 (the test is required by SC-001, not a behaviour change).
- FR-008 — absent. No stop outcome or reason exists in `_outcome` (`dispatch.py:1371-1403`). Work: R4 (Phase 2, needs the report block).
- FR-009 — partial. D70 amendment: a format miss is advisory when gates ran and passed (`dispatch.py:1389-1392`, `1402`). With failed gates the reason is `report-noncompliant`, which hides `gate-failed` (`dispatch.py:1390-1392` runs before `1399-1400`). Work: carry `report=` as its own status field (already printed, `dispatch.py:1417`) and order the derivation so a failed gate wins, then every `unverified` case, and `report-noncompliant` comes last (data-model.md order); a format fault never turns an unverified case red (Phase 1).
- FR-010 — absent. No pre-launch check of gate strength. Work: slots lint warning for a gate whose argv is `test -s|-e|-f <path>` or `ls <path>` where the path exists before launch (Phase 1, warning only).
- FR-011 — partial. `no-gates` and `gate-failed` are distinct (`dispatch.py:1354`, `1403`); `gate-missing` is reused for tampered scripts (`dispatch.py:1488`) and for not-runnable gates. Work: `gate-not-runnable`, `gate-timeout`, `gate-refused`, `gates-not-run-tampered` (Phase 1).

Delegate claims

- FR-012 — absent. `check_report` checks keywords only (`skills/workerbee/scripts/check_dispatch_prompt.py:218-226`). Work: R5 (Phase 2).
- FR-013 — absent. The REPORT_KEYWORDS set has no machine block (`check_dispatch_prompt.py:71`); the prompt header does not ask for one. Work: `CLAIMS` block in `skills/workerbee/header.md` and `slots.md`, parsed by `check_claims.py` (Phase 2). Also #131 step C.
- FR-014 — absent. Work: `claims=not-checked` when the block is missing or unparsable (Phase 2).
- FR-015 — partial. A return row is written by `_finish` and `_red_before_run` (`dispatch.py:1537`, `1551`) through `host_ledger.record_dispatch_return` (`agents_inc/host_ledger.py:248-254`). Gaps: refusal paths that set `outcome` and return `EXIT_REFUSED` write no return row (`dispatch.py:1897-1993`); the row has `status` and `gate_reason` but no per-gate results and no explicit link field (`host_ledger.py:158-171`; `id` equals `run_id`, which is the implicit link). Work: contracts/return-row.md (Phase 2).
- FR-016 — absent as code, satisfied by design: `check_claims.py` reads only the run directory, the working tree and gate output (Phase 2).

doctor

- FR-017 — absent. `doctor` prints codes or `READY` on one line (`agents_inc/install/cli.py:470`); the report has `codes`, `warnings`, `live` (`doctor.py:20-26`), no per-item tested state. Work: `items` list with `tested` and `result` per item, printed one per line (Phase 3).
- FR-018 — partial. READY is `not codes` (`doctor.py:219`); the live model probe runs only with `--live-model` (`doctor.py:210`), so READY is printed without any dispatch-path test. Work: R6 makes the dispatch-path item required (Phase 3).
- FR-019 — absent for the Claude path. Only an opt-in Codex PONG exists (`doctor.py:210-218`). Work: R6 (Phase 3).
- FR-020 — present. `repair-failed.json` adds `WB_REPAIR_FAILED`, which blocks READY (`doctor.py:208`), and the CLI prints the failure detail (`cli.py:471-474`). Issue #155 item b is done. The work is a regression test (amended spec FR-020) and the per-item line format (Phase 3, FR-017).
- FR-021 — absent. `INSTALL_STALE` is computed now from git or digest (`doctor.py:53-73`) but the output does not say whether the result was measured now or read from `source-git.json`. Work: `install-match` item with `basis=measured|record` (Phase 3).
- FR-021a — partial. The uncommitted-edit warning is printed only at install and repair time (`agents_inc/install/source_git.py:72-78`); `doctor` and dispatch print none (`doctor.py:207` calls only `_install_stale`; the hook text at `hook.py:83-86` says uncommitted edits "do not count"). D82 says "doctor shows a warning for them instead"; that warning is not in `doctor.py`. Work: `WB_SOURCE_UNCOMMITTED` warning in doctor and on the dispatch stderr, never blocking (Phase 3).

Refusals

- FR-022 — partial. Lint names elements (`check_dispatch_prompt.py:229-247`, `label_missing`) and prints a corrected form for element 3 only (`check_dispatch_prompt.py:482-483`) and for fan-out (`check_dispatch_prompt.py:241-242`). Schema errors name allowed values for CLASSIFICATION and EFFORT (`skills/workerbee/scripts/dispatch_schema.py:135`, `142`). The glob refusal names the pattern and the fix (`dispatch.py:1909-1910`). Most other refusals give a reason word only (for example `dispatch.py:1897-1993` set `outcome` with no fix line). Work: one rule table, one message format (contracts/refusal-format.md) (Phase 4).
- FR-023 — absent. QUICKREF lists some rules in prose (`skills/workerbee/QUICKREF.md`, "Hard stops", "Verification") but no per-rule table, and no test ties code rules to it. Work: rule registry module plus a coverage test (Phase 4).
- FR-024 — absent. QUICKREF names install paths: `~/.claude/skills/workerbee/scripts/check_dispatch_prompt.py` and `~/.claude/skills/workerbee/scripts/render_dispatch.py` (QUICKREF "Lint" paragraph); `render_dispatch.py:411-412` reads `slots.md` from the script directory. Work: `agents-inc dispatch --print-template` and `agents-inc dispatch --rules` commands; messages name them (Phase 4).
- FR-025 — partial. The slot text screen already matches locations, not bare words (comment and regex at `dispatch.py:2262-2276`), and deny-list clauses are skipped (`dispatch.py:2287-2296`, `2306-2316`). The gate and BASH_ALLOW screen still matches secret words in basenames (`dispatch.py:2329-2345`, `names_credential`). Work: the replay set decides which recorded refusals still reproduce; only reproduced cases change (Phase 5). See grill G5.
- FR-026 — partial. Secret paths are refused (`dispatch.py:2271-2276`, `2322-2324`). There is no "could not decide" outcome: a path built at run time (for example `$DIR/.env`) is matched only if the regex happens to hit. Work: an undecidable-path rule that refuses with reason `credential-undecidable` (Phase 5).
- FR-027 — partial. Spec 036 fixed `for`, `if`, `while`, `eval` and `sh -c` mentions (D72 amendment 2026-11-09; `hook.py:191` `_parse`). Recorded forms still to check: `--help` after other commands and the F1-F4 list of #152. Work: replay set first (Phase 5).
- FR-028 — partial. `compound_deny` fails open on any exception (`hook.py:369-370`), and D72 lists known allowed bypass forms (ANSI-C words, `${x}` subcommand, redirect before the command). Work: deny with "form could not be parsed" when the text contains `agents-inc` and the tokenizer raises or meets an ANSI-C word or a leading redirect (Phase 5).
- FR-029 — absent as a single set. Hook tests exist per case (not read in full; UNVERIFIED). Work: `fixtures/replay/screens.jsonl` plus `tests/test_screen_replay.py` (Phase 5).

Unverified records

- FR-030 — absent. No surface prints "not verified now" (grep of `agents_inc` and `skills/workerbee/scripts` for the phrase: no match). Surfaces that print stored values: `doctor` install state (`source-git.json`, `doctor.py:53-73`), the hook's session-start text built from a doctor report (`hook.py:78-90`), and the status line cache (`scripts/statusline.sh`: keeps the cache after a failed collection at line 59 and only dims stale window cells at line 138). Work: Phase 3 for doctor, hook and the status line (read `scripts/statusline.d/SPEC.md` first).
- FR-031 — partial. Mirror errors are recorded and never change the exit code (`dispatch.py:1455-1462`), but "run spec not mirrored: no home repo" (`dispatch.py:1430`) says nothing about loss or action. Work: one line: what was skipped, "no record lost: run.json is in <run dir>", "no action needed" (Phase 3).

Governance

- FR-032 — process requirement. D84 (the next free number today; Phase 1 rulings) and the later entries, at the next free numbers and identified by title (claims block, doctor items and READY, screens decide on requested action), are written before the code that depends on them ships.
- FR-033 — absent. Five DomI findings are listed in `evidence.md`; none is filed yet (not checked against DomI issues; UNVERIFIED). Work: Phase 0 files them and writes `upstream-issues.md` in this directory.

FR-0 count note: the requirement list above names 35 requirements (FR-001 to FR-033 plus FR-001a and FR-021a).
