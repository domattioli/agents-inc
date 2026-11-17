<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-24 skill=speckit-analyze repo=agents_Inc session=20261025T002934Z-opus-7f9da0 -->
# Specification Analysis Report: 028 agents-inc as a mod (luna first)

Adversarial, read-only cross-check of `spec.md`, `plan.md` and `tasks.md` in `specs/028-agents-inc-as-mod/`, against `.specify/memory/constitution.md` and the code the spec cites. Findings are proposals; the CoS rules on each. No artifact was edited by this pass.

Severity note: the skill makes a constitution conflict CRITICAL. The constitution is unratified and says its violations report as WARN until ratified (`.specify/memory/constitution.md:62-64`). Constitution findings below carry `CRITICAL (WARN while unratified)`.

## Findings

| ID | Category | Severity | Location(s) | Summary | Proposed artifact edit |
|----|----------|----------|-------------|---------|------------------------|
| F1 | Inconsistency | HIGH | spec.md:106, spec.md:194, spec.md:200-218; plan.md:78, plan.md:150; tasks.md T004, T032, T039, T041, T045, T046, T047 | US5 scenario 1 and SC-008 allow edits only to Inventory "change" rows and the files they name. The plan edits paths no change row names: `agents_inc/install/luna_native.py` (new), `agents_inc/install/cli.py` (`luna` verb, doctor line), `agents_inc/host_ledger.py` (skip the hook row), `tests/*`, `CHANGELOG.md`, `docs/DECISIONS.md` (row at spec.md:218 says "keep"), and deletes `mods/luna-brain/`. FR-026 and FR-027 cannot be met inside the current rows. | Spec: add change rows for `agents_inc/install/luna_native.py` (new, FR-026, FR-020, FR-021), `agents_inc/install/cli.py` (FR-020, FR-021, FR-026), `agents_inc/host_ledger.py` `dispatch_row` (FR-026), the named test files, `CHANGELOG.md`, and `docs/DECISIONS.md` (add D69, FR-027); and name the `mods/luna-brain/` removal in row 1. Or tasks: drop T046 and move the ledger write into the mod, which plan Complexity Tracking rejects. |
| F2 | Inconsistency | HIGH | spec.md:149 (FR-013), spec.md:206; plan.md:56; tasks.md T016, T017 | FR-013 needs Codex to load no operator MCP server. The plan meets it with `lead_codex_home` (`agents_inc/install/runtime.py:279-307`, docstring: "the operator's MCP servers and config never load"). The Inventory row says that function is "Not used by the native luna path". The plan reuses it unchanged, but the row's text is then false. Each step also pays a `mkdtemp` plus cleanup (`runtime.py:292`, `:616-624`). | Spec: change row spec.md:206 to "Keep; reused unchanged by host-tools runs for FR-013 (the native luna path)". Or plan: pick another FR-013 mechanism and record why `-c` overrides fail (research R5 relies on an operator memory note, not a probe this run); then T016 and T017 change. |
| F3 | Coverage gap | HIGH | spec.md:147 (FR-011), spec.md:187 (SC-001); plan.md:55; research.md R3; tasks.md T005, T012, T014 | FR-011 makes a missing model cache fail every step. The stress container starts with a fresh `CODEX_HOME`: it mounts only `auth.json` (`docker/luna_stress.sh:8`), and the spec says a fresh home has no `models_cache.json` (spec.md:16). Under the new rule every container run would fail until the cache exists, so SC-001 (38 of 40) is unreachable as tasked. The fix text is also unknown (R3 is [assumed]). | Tasks: T012 adds a warm step, before the scenarios, that runs the command T005 finds and checks `models_cache.json` holds the slug; T014 depends on T005. Plan D3 item 1: name the fix command once T005 records it. |
| F4 | Underspecification | MEDIUM | spec.md:171 (FR-026); plan.md:77; tasks.md T038, T042 | FR-026 says "one ledger record per agent run". A SendMessage follow-up (FR-005, US1 scenario 2) runs a new turn on the same agent, and `turn.complete` fires per turn (`mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:4598-4609`). The spec does not say whether a follow-up is a new run. The plan picks one node per agent, updated per hand-back. | Spec FR-026: "one ledger node per luna agent, with a return update at each hand-back". Tasks unchanged if the CoS accepts the plan's choice. |
| F5 | Underspecification | MEDIUM | spec.md:171; plan.md:82; tasks.md T038 | The snapshot is not attributed. The `par` scenario runs three luna agents in one tree, and the parent may edit while they run. `verify` reports every path that changed (`skills/workerbee/scripts/pre_dispatch_snapshot.py:103-132`), so a clean agent can record `changed`. Nothing in the spec says what the result means or who acts on it. | Spec FR-026: state that the snapshot result is "tree changed during the run", informational, and not a verdict. Tasks T038: add a two-agent case where one agent's edit shows in both records. |
| F6 | Inconsistency | MEDIUM | plan.md:77 (D6 item 1); tasks.md T042, T043 | `begin` runs after `agent.spawn`'s `next(e)` resolves, when the agent has already started. The snapshot can race the agent's first tool call. A Codex step takes seconds, so the race is unlikely, but it is not excluded. | Plan D6 item 1 and tasks T043: the first `turn.step` of a luna agent awaits the `begin` promise before it starts Codex; T042 adds a case where `begin` resolves late and the first step waits for it. |
| F7 | Constitution | CRITICAL (WARN while unratified) | constitution.md:48 (P7); spec.md:134, spec.md:220; plan.md:31; tasks.md T045 | P7 says astra, sol, terra and luna are not Claude Agent-tool subagent models. FR-001 keeps `luna` out of the Agent tool's `model` parameter, but a subagent type whose steps luna answers is the case P7 was written to stop. The spec flags P7 as stale, but only the operator can amend it (constitution.md:66-68). | Tasks T045: the D69 draft asks the operator for a P7 amendment (MINOR bump, D69 cited). No spec edit. |
| F8 | Constitution | MEDIUM (WARN while unratified) | constitution.md:52 (P8), constitution.md:32 (P3); spec.md:25, spec.md:171; plan.md:32 | The native path runs no prompt-contract lint and no report lint (Q2). P8 binds "every dispatch prompt". Q2 answers the scope, but no canon entry yet says that an Agent call to `agents-inc:luna` is not a "dispatch" in the P8 sense. | Tasks T045: D69 states that P8 does not apply to native subagent calls and that P3 holds through the parent's verification. LESSON-CANDIDATE for the constitution. |
| F9 | Underspecification | MEDIUM | spec.md:188 (SC-002); tasks.md T015 | SC-002 needs "identical permission decisions". T015 says to compare them but not where to read them. Under `claude -p --allowedTools` there are no prompts, and the stress script keeps only the `result` text (`docker/luna_stress.sh:35-41`). | Tasks T012 and T015: keep each run's `permission_denials` and the tool-use or tool-result pairs from the stream-json output, and compare those per scenario between `HAIKU=1` and luna runs. |
| F10 | Coverage gap | MEDIUM | spec.md:76 (US3 scenario 3); tasks.md T028, T037 | "Mod not loaded: the Agent call fails with an unknown-type error" has no task. T028 covers a broken contract with the mod loaded, not a missing mod. | Tasks T037: add a run without the mod (`agents-inc repair --no-mod` or no `--plugin-dir`) that asks for `agents-inc:luna` and expects the unknown-type error. |
| F11 | Coverage gap | MEDIUM | spec.md:165 (FR-023); tasks.md T035 | FR-023 lists broker luna Workers and `@luna`/`@@luna`. T035 checks only the argv that `agents-inc dispatch --model luna` builds. `@luna` runs a fresh tool-free `agents-inc run` (`skills/codex-bridge/scripts/at_route.sh:179`), and today only `agents-inc run` passes `host_tools` (`agents_inc/install/cli.py:288-289`), so the risk is low but untested. | Tasks T035: also assert that the at-route command line and a broker luna Worker argv carry no `--host-tools`, no `model_catalog_json` and no isolated home. |
| F12 | Duplication | LOW | plan.md:60 (D3 item 6); tasks.md T025, T026 | `run_codex` already prints a quota message, "hit a usage or rate limit; retry at" (`agents_inc/install/runtime.py:646`). Plan D3 item 6 adds a second quota line and exit 75 without saying how it relates to the existing path. | Plan D3 item 6 and T026: reuse the `runtime.py:646` branch and only add exit 75 there for host-tools runs; T025 asserts the existing message stays. |
| F13 | Underspecification | LOW | research.md R4; plan.md:49-51; tasks.md T023 | The third identity check (marker line in the agent's system prompt through `$.prompt.compose`) is [assumed]. If the API cannot be asked for another agent's prompt inside `turn.step`, D2 falls back to "fail when `agent.list` throws". | Tasks T023: first a probe case that shows whether `$.prompt.compose` in `turn.step` returns the luna agent's own prompt; drop check (3) from plan D2 if it does not. |
| F14 | Ambiguity | LOW | spec.md:146 (FR-020), spec.md:213; plan.md:68, plan.md:90 | FR-020 says "logged in", but the plan tests only that `~/.codex/auth.json` exists (no network, as the dispatch requires). An expired login passes. The Inventory row says "warning code" (singular); the plan adds three (`LUNA_OFF`, `LUNA_CODEX_NOT_READY`, `LUNA_CATALOG_MISSING`). | Spec FR-020: "logged in (auth file present)". Inventory row spec.md:213: "luna readiness line and warning codes". |
| F15 | Terminology | LOW | spec.md:41, spec.md:133-142; plan.md:42 | The spike prints `luna-brain:` debug lines (`mods/luna-brain/hooks/luna.ts:351`, `:418`). The stress suite counts them (`docker/luna_stress.sh:49`). The plan renames the prefix to `agents-inc luna:`. Any operator log grep on the old prefix breaks silently. | Tasks T012: the stress grep uses the new prefix (already planned); T036 README names the prefix. |

## Code anchor check

Every anchor below was opened or matched this run [verified]:

- `mods/luna-brain/hooks/luna.ts`: `:11`, `:21-26`, `:46`, `:176-185`, `:249`, `:254`, `:268-272`, `:294`, `:313-327`, `:343`, `:371-373`, `:383-384`, `:389-390`, `:392-399`, `:406-413`.
- `agents_inc/install/runtime.py`: `:104` `tools_for`, `:124` `permission_profile`, `:279-316` `lead_codex_home` and `lead_env`, `:319-376` (`NO_TOOL_FEATURES` through `no_tool_args`), `:329-333`, `:336-364`, `:352-360`, `:468` `QUOTA_PATTERN`, `:555` record line, `:646` quota message, `:690` `run_codex_thread`.
- `agents_inc/install/dispatch.py`: `:194` `render`, `:218` `lint_prompt`, `:237` `lint_report`, `:363` `SANDBOX_FIX`, `:371` `caller_sandbox`, `:383` `worker_env`, `:412` `sandbox_available`, `:453` `claude_sandbox_profile`, `:678` `launch`, `:859-897` trust record (`_trust_path` at 859, `_record_trust` at 869, `_trust_record` at 897), `:1612` `resume`, `:1906` `_validate_fields`, `:2199` `resume_cap`, `:2449` `serve`.
- `agents_inc/install/hook.py`: `:27-29` (comment at 27-28, `BRAIN_PREFIX` at 29), `:107` `persona_deny`, `:152` `gate_deny`.
- `agents_inc/routing.json:5`: grunt codex pin `gpt-6-luna`. `agents_inc/install/doctor.py:75-84` `_mod_missing`, `:86` `check_install`.
- `docker/luna_stress.sh:19-24`, `:24` (`follow` expects `gpt-6`).
- `docs/DECISIONS.md:628` (D59 body), `:644` (D62 PR B, the rejected Claude-subagent wrapper). D68 at `:692` is the last entry found.
- `.specify/memory/constitution.md:48` (P7).

Not opened this run: `agents_inc/install/mcp_broker.py` and `agents_inc/install/worker_mcp.py` bodies (the files exist; spec.md:210 cites them as whole files), and `agents_inc/install/live_events.py`, `agents_inc/live_rows.py` (spec.md:212, "keep", no line cited).

## Coverage summary

| Requirement | Has task? | Task IDs | Notes |
|---|---|---|---|
| FR-001 | yes | T006, T007 | |
| FR-002 | yes | T006, T007 | |
| FR-003 | yes | T003, T004, T006, T007 | |
| FR-004 | yes | T008 | |
| FR-005 | yes | T008, T009 | |
| FR-006 to FR-009 | yes | T010, T011 | FR-009 window look is checked only by the operator runs |
| FR-010 | yes | T016, T017 | |
| FR-011 | yes | T005, T016, T017, T020 | F3 |
| FR-012 | yes | T016 | |
| FR-013 | yes | T016, T017 | F2 |
| FR-014 | yes | T018, T019, T020 | |
| FR-015 | yes | T022, T024 | |
| FR-016 | yes | T022, T025, T026 | F12 |
| FR-017 | yes | T023, T024 | F13 |
| FR-018 | yes | T027 | |
| FR-019 | yes | T001, T034, T046 | |
| FR-020 | yes | T003, T004, T031, T032, T033 | F14 |
| FR-021 | yes | T003, T004, T033, T036 | |
| FR-022 | yes | T029, T030 | |
| FR-023 | yes | T025, T035, T037 | F11 |
| FR-024 | yes | T008, T009 | |
| FR-025 | yes | T044 | F1 |
| FR-026 | yes | T038 to T043 | F4, F5, F6 |
| FR-027 | yes | T045 | F7, F8 |
| FR-028 | yes | T012, T021 | |
| SC-001 | yes | T012, T014 | F3 |
| SC-002 | yes | T012, T015 | F9 |
| SC-003 | yes | T012, T014, T022 | |
| SC-004 | yes | T021 | |
| SC-005 | yes | T002, T012, T014 | |
| SC-006 | yes | T012, T014 | |
| SC-007 | yes | T035, T037 | |
| SC-008 | yes | T013, T044, T047 | F1 |

Unmapped tasks: none. T048 is the required final move task.

## Metrics

- Requirements: 28 FR, 8 SC
- Tasks: 48
- Coverage: 100% of FR and SC have at least one task
- Ambiguity count: 1 (F14). Duplication count: 1 (F12).
- Findings: 15. CRITICAL (WARN while unratified) 1, HIGH 3, MEDIUM 7, LOW 4.

## Next actions

- Resolve F1, F2 and F3 before `/speckit-implement`: F1 and F2 are spec Inventory edits the CoS owns; F3 changes T012 and T014.
- F7 and F8 go to the operator through the D69 draft (T045); they do not block implement while the constitution is unratified.
- F4 to F6 and F9 to F15: accept the plan's choice or apply the proposed task edits.

## Resolution

CoS rulings: `.scratch/spec028/rulings.md` (2026-10-24). Applied by the same opus run. Line numbers are after the edits. The findings table above is kept as written; its task IDs are the old numbering.

Task renumbering: one new task (T017, F2) was added, so old T017 to T048 are now T018 to T049. Final count: 49 tasks; T049 is the move to DomI. Old to new: T017 to T018, T018 to T019, and so on, each +1.

- F1, accepted. spec.md:202 (row 1 now names the `mods/luna-brain/` removal after SC-001), spec.md:205 (the `runtime.py` change row also names `run_codex` and `run_codex_thread`, FR-014 and FR-016), new change rows spec.md:216-222 (`mods/agents-inc/hooks/luna.ts`, `luna.test.ts`, `README.md`; `luna_native.py`; `cli.py`; `host_ledger.py` `dispatch_row`; the seven test files; `CHANGELOG.md`; `docs/DECISIONS.md` new D69, FR-027). plan.md:84 (D6 item 3 cites the new row), plan.md:104 (D10), plan.md:156 (Complexity Tracking row 3). tasks.md:100 (T045 checks every path against a change row).
- F2, accepted with the extra fix. spec.md:206 (`lead_codex_home` reused unchanged for FR-013; `lead_env` not used). plan.md:56-62 (D3 item 2 rewritten: resolve `Path.home() / ".codex"` once, the same directory `lead_codex_home` links from, `runtime.py:283`; build the catalog from it and pass the path into `no_tool_args`, which stops reading `os.environ["CODEX_HOME"]`, `runtime.py:355`; raise the catalog error before any temp home exists; then swap `CODEX_HOME` as the non-lead branch does, `runtime.py:565-566`; `lead_env`, `runtime.py:310-316`, is Lead-only and not used; Codex authenticates through the `auth.json` symlink, `runtime.py:295`, and agents-inc never reads the credential; a token refresh that replaces the link keeps the home and turns exit 0 into 1, `runtime.py:613-617`, `:665-666`). plan.md:70 (D4 adds the `WB_CODEX_AUTH_MISSING` text). research.md:33 (R5). tasks.md:53 (T016 no longer holds the real-home case), tasks.md:54 (new T017 test task), tasks.md:55 (T018 implements T016 and T017; `lead_codex_home` unchanged).
- F3, accepted. tasks.md:41 (T012 warm step before any scenario), tasks.md:43 (T014 "Needs T005"), tasks.md:26 (T005 names its T012 use), tasks.md Dependencies line for T014. plan.md:55 (D3 item 1 names the fix command once T005 records it), plan.md:100 (D9 warm step).
- F4, accepted. spec.md:171 (FR-026: one ledger node per luna agent, a return update at each hand-back). plan.md:83 (D6 item 2). tasks.md:94 (T039 wording).
- F5, accepted. spec.md:171 (FR-026: the snapshot result means "the tree changed during the run", informational, not a verdict, not attributed). plan.md:88. tasks.md:94 (T039 two-agent case).
- F6, accepted. plan.md:82 (D6 item 1: the first `turn.step` awaits the `begin` promise). tasks.md:98 (T043 late-begin case), tasks.md:99 (T044 implements it).
- F7, kept for the operator. tasks.md:101 (T046 asks for the P7 amendment, MINOR bump, D69 cited). No other edit.
- F8, kept for the operator. tasks.md:101 (T046 states that P8 does not apply to native subagent calls and that P3 holds through the parent's verification). No other edit.
- F9, accepted. tasks.md:41 (T012 keeps `permission_denials` and tool-use and tool-result pairs), tasks.md:44 (T015 compares them). plan.md:100 (D9).
- F10, accepted. tasks.md:87 (T038 adds the run without the mod, unknown-type error).
- F11, accepted. tasks.md:85 (T036 adds the `@luna` at-route command line and a broker luna Worker argv).
- F12, accepted with a correction. The quota branch already returns 75 for every run (`runtime.py:657`; this run read it; research R7 had called exit 75 unused, which was wrong). So there is nothing to "add": plan.md:66 (D3 item 6: reuse `runtime.py:636-657`, no runtime change), research.md:44-45 (R7), tasks.md:66 (T023 uses the existing message), tasks.md:69 (T026 asserts the existing message and no second line), tasks.md:70 (T027 confirms instead of implementing; edits `runtime.py` only if a host-tools path bypasses the branch).
- F13, accepted. tasks.md:67 (T024 starts with the probe case). plan.md:51 (D2 drops check 3 if the probe fails). research.md:27 (R4; also corrects its old "T020" reference).
- F14, accepted. spec.md:162 (FR-020: "logged in (auth file present)"), spec.md:213 ("warning codes"). Cite fix: the findings table gives FR-020 as spec.md:146; FR-020 is at spec.md:162 (146 is FR-010).
- F15, accepted. tasks.md:41 (T012 greps the new prefix `agents-inc luna:`), tasks.md:86 (T037 README names it). plan.md:100 (D9).

Not applied: none. F12 was applied in its intent (reuse the existing branch, no second quota line), not as literally worded ("add exit 75"), because exit 75 already exists.
