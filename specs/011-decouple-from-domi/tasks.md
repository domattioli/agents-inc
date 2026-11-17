<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Tasks: Decouple agents_Inc from DomI and operator machine

**Feature**: `011-decouple-from-domi` | **Spec**: specs/011-decouple-from-domi/spec.md | **Plan**: specs/011-decouple-from-domi/plan.md
**Gate source of truth**: `plan-decouple-agents_inc.md` (original T1-T11). `Success`/`Failure` lines below are copied verbatim from it (modulo markdown label + line re-wrap). Not loosened.
**Order**: plan.md Sequencing: T1, T2 -> T4, T5, T6 -> T7 -> T8 -> T9 -> T3 (D1 answered, option a) -> T10 -> T11 (anytime, own issue/PR).

---

### T1. Track `agents_inc/keys.py`
**Size**: one-line
**FR**: FR-001
**Files**: `.gitignore` (`:224` is `*key*`; `:226` is `!workerbees/keys.py`; `:227` is `!tests/test_keys.py`; add new exception at `:226` area), `agents_inc/keys.py` (track)
**Change**:
1. Confirm `agents_inc/keys.py` is source, not credentials, WITHOUT reading or printing any value (constitution P1, `constitution.md:23` — reading key material forbidden at every rung). Mechanical non-printing check ONLY, e.g. `python3 -c "import ast,sys;print([n.name for n in ast.parse(open(sys.argv[1]).read()).body if hasattr(n,'name')])" agents_inc/keys.py` (emits top-level def/class NAMES only) plus `grep -cE '=\s*["\x27][A-Za-z0-9_-]{16,}["\x27]' agents_inc/keys.py` (count only, expect 0). If the count is non-zero: STOP, escalate to operator; do NOT print the line. **Verification constraint (not a gate change): any key value printed to a transcript = RED.** (analyze F5)
2. Add `!agents_inc/keys.py` next to `!workerbees/keys.py` (`.gitignore:224-227`).
3. `git add agents_inc/keys.py` (run root owns commit/push authority).
**Success:** fresh clone, `python3 -m pytest tests -q` collects all modules (0 collection errors).
**Failure:** any `ModuleNotFoundError: No module named 'agents_inc.keys'` in a fresh clone.
**Depends on**: none

### T2. Fix `skills.requirements.txt` + `scripts/install_skills.sh`
**Size**: small
**FR**: FR-002, FR-003, FR-004
**Files**: `skills.requirements.txt` (`:20-21` grill entries abs paths, `:22` handoff-lint parenthetical), `scripts/install_skills.sh` (`:14` parses only `--dry-run`; `:42-48` external-repo branch MISS/`status=1`; `:43` sed path extract; `:52-53` `rm -rf` + `cp -R`; `:59` SKIP for unknown kinds)
**Change**:
1. Remove every absolute `/Users/...` source path from `skills.requirements.txt`. D5 ANSWERED: there is NO upstream-governance-repo source form at all (no path, URL, checkout, or name, per ruling 2); no remote-source kind is added. Entries are only `vendored`, `optional-user-scope`, or (existing, if still needed) `external-repo` with no absolute path.
2. Strip trailing parenthetical from handoff-lint line (`skills.requirements.txt:22`); move to comment line. Parsed into path today (`install_skills.sh:43`) so entry fails even on operator machine. Comment text must not name the upstream governance repo.
3. Add source kind `optional-user-scope` (kind set enumerated in step 6's table, not "third"): check `$HOME/.claude/skills/<name>`, warn if absent, never set `status=1`. Add branch before `install_skills.sh:42`.
4. Installer prints `OPTIONAL-MISSING <name>` for absent optional skills, exit 0.
5. **No remote-source kind (D5 ANSWERED, ruling 2).** The earlier remote-fetch idea is dropped entirely: the installer never fetches into `$REPO_ROOT/skills/<name>` (`install_skills.sh:30` sets `dest` there and `:52-53` does `rm -rf` + `cp -R`; fetching there would re-create vendoring, #326-class drift). Clean run needs no network (plan R2). (analyze F4)
6. **Define the kind table** (analyze F3) — record in the manifest header, one row per non-vendored entry:

   | entry | kind | clean-HOME output line | exit contribution |
   |---|---|---|---|
   | `handoff-lint` | `optional-user-scope` | `OPTIONAL-MISSING handoff-lint` | 0 |
   | `grill-me` | `optional-user-scope` (D1 ANSWERED, ruling 3) | `OPTIONAL-MISSING grill-me` | 0 |
   | `grill-with-docs` | `optional-user-scope` (D1 ANSWERED, ruling 3) | `OPTIONAL-MISSING grill-with-docs` | 0 |
   | `caveman` (if listed) | `optional-user-scope` (ruling 4: never vendored) | `OPTIONAL-MISSING caveman` | 0 |

   Read the T2 gate as: every `optional-user-scope` entry that is absent prints `OPTIONAL-MISSING <name>`; none contributes a non-zero exit. Optional externals are pinned to an upstream sha (ruling 10); see T3.
7. Add shell test: empty HOME, assert exit 0; grep `/Users/` on manifest + installer (SC-002).
**Success:** on a clean HOME with no DomI checkout, `bash scripts/install_skills.sh` exits 0 and lists every vendored skill OK and every optional skill as OPTIONAL-MISSING. On the operator machine, exits 0 with no MISS line.
**Failure:** exit 1 on a clean machine; or any absolute `/Users/` path remaining in the file.
**Depends on**: T1

### T4. Make the D41 handoff-lint gate degrade explicitly
**Size**: small
**FR**: FR-006
**Files**: `skills/workerbee/scripts/check_dispatch_prompt.py` (no `--with-handoff-lint` flag exists today; new work, G2), `CLAUDE.md:62`, `skills/workerbee/SKILL.md:640-661`, new test
**Change**:
1. Reword `CLAUDE.md:62` and `SKILL.md:640-661` (ruling 4, conditional): "if the handoff-lint skill is installed, run it; if absent, emit one line `handoff-lint NOT installed -> H1-H6 checked by hand` and continue". Keep H1-H6 rule list inline so manual check possible. Fix the label: `CLAUDE.md:62` and `SKILL.md:640` cite "D40" for this gate; the gate is D41 (`docs/DECISIONS.md` D41); D40 is an unrelated stale-server lesson. The D42 entry (see T5 step 0) records the resolution. The in-repo `check_dispatch_prompt.py` 14-element check stays mandatory and unconditional; only the external handoff-lint step is conditional.
2. Add `--with-handoff-lint` flag to `check_dispatch_prompt.py`: resolve the installed skill script or print exact warning line; return 14-element verdict only when absent; no crash.
3. Add test: clean HOME -> warning line + verdict, exit as verdict-only.
4. **Define exit semantics before implementing (analyze F8):** "exits with the 14-element verdict only" is not a checkable code. Specify: exit 0 iff all 14 elements pass, non-zero otherwise, and name which stream carries the `handoff-lint NOT installed` warning (stderr recommended, so the verdict on stdout stays machine-parseable).
5. **Cover both gate directions (analyze F9):** `CLAUDE.md:62` fires the gate on a dispatch prompt AND on a returned delegate report (`--profile report`); `SKILL.md:640-661` documents both. This task's flag covers only the prompt direction — add the report-direction conditional wording and flag behaviour, or FR-006 is only half met.
**Success:** `check_dispatch_prompt.py --with-handoff-lint p.txt` on a clean HOME prints the warning line, exits with the 14-element verdict only. On the operator machine it runs both.
**Failure:** any doc text that presents `python3 ~/.claude/skills/handoff-lint/...` as unconditional; or the flag crashing when the script is absent.
**Depends on**: none on the installer. **Serialize with T6 and T7** — all three edit `skills/workerbee/SKILL.md` (T4 `:640-661`, T6 `:131,520,806`, T7 `:187..829`), so they must not run concurrently. (analyze F15: the previous "depends on T2 (installer semantics)" was false — T4 does not touch the installer.)
**Unblocked**: D7 ANSWERED (operator approved the P8 amendment). Land the D42 entry + constitution bump (T5 step 0) in the same change as, or before, the `CLAUDE.md` edit.

### T5. Contract element 1 and the caveman/nested-notes/write-like-scientist mandates
**Size**: small
**FR**: FR-007
**Files**: `skills/workerbee/scripts/check_dispatch_prompt.py:20` (element 1 keyword only `"caveman ultra"`), `CLAUDE.md:9-12` (wording-mandate table; task text also cites `CLAUDE.md:45` and Step 11 element 1), 2 test fixtures
**Change**:
0. **Canon amendment record (D7 ANSWERED, ruling 5).** Add a NEW `docs/DECISIONS.md` entry numbered D42 (D41 already exists for the handoff-lint gate). D42 records: (i) contract element 1 becomes conditional (P8 amendment); (ii) the handoff-lint gate is conditional; (iii) the "D40" label at `CLAUDE.md:62` and `SKILL.md:640` was wrong (D40 is an unrelated stale-server lesson) and D42 resolves the collision. DECISIONS amends, never retracts: do not edit existing entries. Bump `.specify/memory/constitution.md` version per its own Amendment rule: MINOR (materially widened scope), 1.7.0 -> 1.8.0.
1. Reword element 1 (`CLAUDE.md:45`, Step 11 element 1), ruling 4 conditional: "if the caveman skill is installed, invoke it (`/caveman ultra`); if absent, emit one line `caveman NOT installed -> checked by hand` and continue". Never vendor caveman (third-party, github.com/JuliusBrussee/caveman). Wording is repo-consuming: regular prose, no compression.
2. Same "if installed" wording for `nested-notes` / `write-like-scientist` at `CLAUDE.md:9-12`. (Ruling 4 names caveman and handoff-lint explicitly; extending to these two is carried from the existing task text, not a new ruling.)
3. Extend `check_dispatch_prompt.py:20` to accept BOTH the Skill-call line and the `caveman NOT installed -> checked by hand` emulation line, explicitly (not fuzzy, plan R5). The other 13 elements and this script stay mandatory and unconditional.
4. Add one test fixture per form.
5. State level name is agents_Inc's own choice (D3 ANSWERED, ruling 6): this repo stays on `ultra`, not an inherited value.
**Success:** `check_dispatch_prompt.py` accepts either the Skill-call line or the emulation line for element 1 (add a test fixture for each).
**Failure:** a prompt that states the emulation line is scored non-compliant.
**Depends on**: none on the installer. **Serialize with T4, T6, T7** — shared file `skills/workerbee/SKILL.md`. (analyze F15)
**Unblocked**: D7 ANSWERED (operator-approved P8 amendment; recorded as D42 + constitution 1.8.0 via step 0). (analyze F6)

### T6. `subagent-dispatch-policy` cross-reference in workerbee
**Size**: small
**FR**: FR-008
**Files**: `skills/workerbee/SKILL.md:131,520,806` (also Step 0.5 / MUST 7 text; MUST 7 rule restated at `:518-522` per input)
**Change**: keep references; qualify each once: "(`subagent-dispatch-policy`, an optional external skill; the rule this step needs is restated in full above)". Do not name the upstream governance repo (ruling 2). Confirm MUST 7 text self-contained. Restate Step 0.5 / MUST 7 rules so no "see X" points outside repo. `cavecrew` has 0 hits in workerbee (input claim; not re-verified).
**Success:** a reader with no DomI can execute Step 0.5 and MUST 7 from workerbee alone.
**Failure:** any sentence of the form "see X for the rule" where X is not in this repo.
**Depends on**: none on the installer. **Serialize with T4, T5, T7** — shared file `skills/workerbee/SKILL.md` (T6 edits `:131,520,806`). (analyze F15)

### T7. Roster (Step 1a) and codex nicknames: separate canon from account facts
**Size**: small
**FR**: FR-009
**Files**: `skills/workerbee/SKILL.md:187,204,227,245,829` (account/machine facts; `:204` "limit: 0 on this account"), `agents_inc/install/runtime.py:8,22` (`MODEL_ALIASES`, resolve), `agents_inc/routing.json:5-8` (hardcoded slugs), **destination file (D4 ANSWERED, ruling 7): `~/.config/agents-inc/roster.json`**, matching the receipt convention `home / ".config/agents-inc/install.json"` at `agents_inc/install/paths.py:33`; new unit test. No receipt schema change: `InstallReceipt` (`agents_inc/install/receipt.py:33-39`) has no account-facts field and none is added.
**Change**:
1. Move Codex nickname->slug rows and "verified against this machine" / "limit: 0 on this account" / "Devstral not exposed on this key" notes out of canon into `~/.config/agents-inc/roster.json`. Installer creates it empty; workerbee Step 1b discovery fills it; user-editable. Step 1a says "run Step 1b and fill this table for your account". Canon keeps only the tier ladder + generic model families. Keep Claude rows.
2. Make `MODEL_ALIASES` (`agents_inc/install/runtime.py:8`) and `routing.json:5-8` nicknames overridable from `~/.config/agents-inc/roster.json`; today's values = defaults, unit-tested (plan R3). `AGENTS_INC_MODEL_MAP` env override retained from the existing task text (not contradicted by ruling 7). File name `roster.json` does not collide with tracked `agents_inc/models.json` catalog (Gap G1 closed).
3. Unit test: `agents-inc run --model luna` resolves via override path.
**Success:** grep of `skills/workerbee/SKILL.md` for "this account"/"this machine" returns 0; `agents-inc run --model luna` resolves through the override path in a unit test.
**Failure:** any account-specific quota note left in canon text.
**Depends on**: T4, T5, T6 (sequencing only; no code dependency)

### T8. DelegateAgent MCP: installer + configurable model
**Size**: small (input: "small, in #29 or follow-up"; follow-up PR unless operator marks "in #29"). **Re-tag note (analyze F13):** "small" is understated — 5 sub-changes, a new `install.sh`, README copy, and a behaviour change (`--model terra` accepted; MCP enum built from the map). Treat as the largest item in the set; consider splitting if it stalls.
**Verification constraint (not a gate change, analyze F13):** `mcp/install.sh --apply` runs `claude mcp add --scope user`, which writes `~/.claude.json` — outside the repo, forbidden by constitution P1 and this feature's own constraints. **Any `--apply` run against the real `HOME` during implementation or verification = RED.** Verify the print-only path (the default). If `--apply` must be exercised at all, it runs only against a throwaway `HOME`, never the operator's. (Contradiction noted by analyze cycle 2 and resolved here: the blanket "any run = RED" and the "throwaway HOME if at all" allowance are reconciled into one rule.)
**FR**: FR-010
**Files**: `skills/codex-bridge/scripts/codexagent.sh:4,24-25,52,54`, `skills/codex-bridge/mcp/codex_agent_mcp.py:47,48,75` (`:97` shells to script), new `skills/codex-bridge/mcp/install.sh`, `skills/codex-bridge/mcp/tests/smoke_mcp.sh`, README
**Change**:
1. `codexagent.sh` reads `CODEXAGENT_MODEL_MAP` / `--slug` (ruling 1: no hardcoded model names; new providers addable by config); `luna` stays default, not the only value; keep enum guard but source it from the map (replaces luna-only guard `:24-25`); remove `gpt-5.6-luna` literals at `:52,54`; update/remove `:4` comment (G5).
2. `codex_agent_mcp.py` tools/list enum (`:47`, currently `["luna"]`) built from same shared map as T7 defines.
3. Add `skills/codex-bridge/mcp/install.sh`: prints (or with `--apply` runs) `claude mcp add --scope user delegate-agent -- python3 "$(pwd)/codex_agent_mcp.py"`. Default = print only; `--apply` writes user-scope, operator-run only, NOT run during implementation (repo-scoped-writes constraint).
4. README "Getting started": one paragraph + the one-liner.
5. `smoke_mcp.sh --offline`: stop after tools/list, print `SMOKE PASS`; live call opt-in.
**Success:** clean HOME, no codex: `smoke_mcp.sh --offline` prints SMOKE PASS; `codexagent.sh --model terra` with a map that includes terra passes the guard; live call still says "would need account".
**Failure:** hardcoded `gpt-5.6-luna` literal remaining in `codexagent.sh:52,54`.
**Depends on**: T7 (consumes shared map)

### T9. Installer honesty
**Size**: small
**FR**: FR-011
**Files**: `agents_inc/install/cli.py:36` (unconditional `resolve_executable("codex", ...)`), `:65` (install parser), `:68` (repair parser), `agents_inc/install/runtime.py:14,17` (`WB_CLI_NOT_FOUND`), `agents_inc/doctor.py`, README (step 9)
**Change**:
1. Ruling 1: Claude and OpenAI (Codex) are both first-class, neither a hard prerequisite. README step 9 states this (replaces "Codex CLI is a hard prerequisite").
2. Guard `cli.py:36`: install must not abort for a missing `codex` CLI or missing Claude; it skips that provider's parts and prints one explicit notice. Keep `--without-codex` on install parser (and likely repair) as the explicit form used by the Success gate. Install skill dirs, mark codex launcher absent. `InstallReceipt` may need optional codex field (plan R4).
3. `doctor` reports `WB_CLI_NOT_FOUND` as warning, not untrusted release. **Define the observable first (analyze F11):** "untrusted release" has no referent in the codebase (`grep -rn untrusted agents_inc/` = 0 hits) and `agents_inc/doctor.py:46,78-79` currently maps `WB_CLI_NOT_FOUND` to `failed`. Name the concrete doctor status value + exit code that constitutes "warning" before implementing, so the gate is checkable.
4. Installer prints what it did not do (the single provider-skip notice from step 2).
**Success:** README states the prerequisite; `install --source . --without-codex` on a clean HOME lands `~/.claude/skills/{workerbee,codex-bridge}` and `doctor` reports `WB_CLI_NOT_FOUND` as a warning, not an untrusted release.
**Failure:** installer exits without saying what it did not do.
**Depends on**: T7 (sequencing per plan)
**Note**: verification of the landing step must use a temp HOME (`HOME=$(mktemp -d)`), never real `~/.claude`.

### T3. grill-me / grill-with-docs: delete, list as optional externals
**Size**: small
**FR**: FR-005
**Files**: `skills.requirements.txt:20-21`, `skills/grill-me/`, `skills/grill-with-docs/`. Fact: installer overwrites them at `scripts/install_skills.sh:52-53`.
**Change** (D1 ANSWERED option (a), ruling 3):
1. Delete `skills/grill-me/` and `skills/grill-with-docs/` (third-party, github.com/mattpocock/skills, MIT; this repo's copies carry no attribution).
2. List both in `skills.requirements.txt` as `optional-user-scope` externals citing ONLY the upstream URL `github.com/mattpocock/skills`, pinned to an upstream sha (ruling 10). The concrete sha is resolved at implementation time from the upstream repo; do not invent one here.
3. No fork, no provenance-header copy option.
**Success:** `skills/` contains no directory that is also listed as `external-repo` in the manifest.
**Failure:** any skill dir present in both `skills/` and an `external-repo` manifest entry.
**Gate-vacuity guard (TIGHTENING, not a loosening — analyze F4):** T2 may remove the `external-repo` kind entirely (entries become `optional-user-scope`), which would make the gate above pass without D1 ever being decided. Verify the gate in its non-vacuous form as well: *`skills/` contains no directory that is also listed under ANY non-`vendored` kind in the manifest*, and *no skill dir is present in both `skills/` and any non-`vendored` manifest entry*. Both forms must hold.
**Depends on**: T2 (for `optional-user-scope` kind if option (a))
**Unblocked**: D1 ANSWERED (option a). Not on critical path of T1/T2/T4-T9.

### T10. Portability CI lane
**Size**: own-issue (input: "small, needs its own issue")
**FR**: FR-012
**Files**: `.github/workflows/tests.yml` (single `unittest` job, ubuntu-latest, no portability lane; `:14-16` Python 3.11, `:18` unittest discover) or new workflow file; new `tests/test_portability.py` or shell smoke
**Change**: fresh clone into tmp, `HOME=tmp`, PATH without codex/claude/gemini; run `install_skills.sh` (exit 0), pytest collection (0 errors), `governance_demo --fake` (exit 0 — exact invocation is `python3 tools/governance_demo.py --fake`; artifacts previously gave only the bare name, analyze F18), `smoke_mcp.sh --offline` (pass). No `/Users/` path, no `~/.claude/skills` content. Lands after T1, T2, T4-T9 so starts green. Grill entries are `optional-user-scope` after T3 (D1 answered). Runner choice pytest vs unittest = Gap G3.
**Success:** lane green on a runner with no DomI and no codex.
**Failure:** lane depends on any `/Users/` path or `~/.claude/skills` content.
**Depends on**: T1, T2, T3, T4, T5, T6, T7, T8, T9

### T11. Pre-existing breakage found during the sim
**Size**: own-issue (input: "not portability, own issue")
**FR**: FR-013
**Files**: `skills/speckit-pipeline/scripts/preflight.sh:23` (`declare -A SKILL_DIR_MAP=(`, bash 4+ only). In scope: this file only.
**Change**:
1. Replace `declare -A` at `preflight.sh:23` with a bash-3.2-compatible `case` form. Verify on bash 3.2 (`/bin/bash`).
2. D6 ANSWERED (ruling 9): the 6 `tests/test_config_schema.py` failures are NOT fixed here. They are file-only; the filing happens outside this work. Out of scope for T11; do not touch `tests/test_config_schema.py`.
**Success:** (derived — input had no explicit gate) `skills/speckit-pipeline/scripts/preflight.sh` runs under macOS bash 3.2 without `constitution: unbound variable`; the 6 `tests/test_config_schema.py` failures are filed in their own issue with explicit re-scope (filing done outside this work, per D6).
**Failure:** (derived — input had no explicit gate) `preflight.sh` still contains `declare -A` or still dies on bash 3.2; or the schema failures are neither filed nor re-scoped; or the fix is folded into the portability PR.
**Depends on**: none

---

## Open operator decisions
All ANSWERED by operator rulings this session (2026-09-18). No OPEN items remain.
- **D1** (T3) ANSWERED: option (a). `grill-me` and `grill-with-docs` are third-party (github.com/mattpocock/skills, MIT; this repo's copies carry no attribution). DELETE both dirs from `skills/`; list in `skills.requirements.txt` as `optional-user-scope` externals citing ONLY the upstream URL github.com/mattpocock/skills, pinned to an upstream sha.
- **D2** (blocks nothing in T1-T11) ANSWERED: shared-skills package DEFERRED, explicitly out of scope.
- **D3** (T5 wording) ANSWERED: this repo stays on caveman `ultra` as its own choice.
- **D4** (T7 path) ANSWERED: `~/.config/agents-inc/roster.json`, matching the receipt convention `home / ".config/agents-inc/install.json"` in `agents_inc/install/paths.py:33`. Installer creates it empty; workerbee Step 1b discovery fills it; user-editable. `MODEL_ALIASES` (`agents_inc/install/runtime.py:8`) and `agents_inc/routing.json` nicknames become overridable from it. Canon keeps only tier ladder + generic model families.
- **D5** (T2 source form) ANSWERED: the upstream private governance repo must not be referenced by path, URL, checkout, or name anywhere in user-facing or canon files (README, CLAUDE.md, CONTEXT.md, `skills/*/SKILL.md` bodies, scripts, `skills.requirements.txt`). Historical records (`docs/DECISIONS.md` existing entries, `specs/*`, handoffs) are left as written. Therefore there is no upstream-repo source form at all; the remote-source kind idea is dropped entirely.
- **D6** (T11) ANSWERED: do NOT fix the 6 `tests/test_config_schema.py` failures. File-only; filing happens outside this work. T11 keeps only the `preflight.sh` bash-3.2 half in scope.
- **D7** (T4 + T5) ANSWERED: amending constitution P8 is operator-approved. Record as a NEW `docs/DECISIONS.md` entry numbered D42 (D41 already exists for the handoff-lint gate; `CLAUDE.md:62` wrongly cites "D40", which is an unrelated stale-server lesson at `docs/DECISIONS.md:414`; the D42 entry resolves the label collision). Bump `.specify/memory/constitution.md` per its own Amendment rule: MINOR (materially widened scope), 1.8.0.
- **Provider rulings (T8, T9; ruling 1)**: Claude and OpenAI are both first-class, neither a hard prerequisite. Install must not abort for a missing `codex` CLI or missing Claude; it skips that provider's parts and prints one explicit notice. Model names not hardcoded: DelegateAgent reads a model map; `luna` stays default but not the only value; new providers addable by config.
- **Third-party skills (T4, T5; ruling 4)**: `caveman` (github.com/JuliusBrussee/caveman, MIT except engine dirs BSL-1.1) is never vendored. Contract element 1 is conditional: if installed, invoke; if absent, emit `caveman NOT installed -> checked by hand` and continue. Handoff-lint gate: same conditional. In-repo `check_dispatch_prompt.py` stays mandatory and unconditional.
- **Optional externals (ruling 10)**: pinned to an upstream sha.

## Notes
Plan.md gaps G1-G10 carried forward as they affect execution.
- **G1** (T7): CLOSED. `agents_inc/models.json` exists (model catalog); override file is `~/.config/agents-inc/roster.json` (D4), no collision.
- **G2** (T4): `--with-handoff-lint` does not exist; new code, not a wording change.
- **G3** (T10): spec uses `python3 -m pytest tests -q` (`spec.md:32`); CI uses `unittest discover` (`tests.yml:18`). T10 must pick runner. Also affects T1 Success check (pytest collection).
- **G4** (T8): `--model terra` passing guard is behavior change (guard luna-only `codexagent.sh:24-25`; MCP enum `["luna"]` `codex_agent_mcp.py:47`).
- **G5** (T8): `codexagent.sh:4` comment also documents luna mapping; update/remove.
- **G6** (T7): account facts at `SKILL.md:187,204,227,245,829`, more than spec grep hint; `:204` is quota content. Hit count not exhaustively verified; run the grep before/after.
- **G7**: `CLAUDE.md:62` and `SKILL.md:640-661` citations confirmed by plan.
- **G8**: PR #29 / DomI PR #504 state not verifiable from repo; mergeability unchecked. Follow-up PR only; avoid files those PRs own.
- **G9**: ~~constitution not read~~ — **CLOSED**. `.specify/memory/constitution.md` v1.7.0 evaluated; see plan.md "Constitution Check". P1 WARNs became task constraints (T1 non-printing check, T8 `--apply` rule, temp-HOME rule); P8 impact became decision D7.
- **G10**: `skills/*/MANIFEST.md` absent; DomI manifest assumptions do not transfer.
- **Constraints for all tasks**: repo-scoped writes only; no `~/.claude/**`, `~/.codex`, `~/.claude.json` writes; no paid model calls; no wholesale DomI vendoring (#326); never print `*key*`/`.env` contents (T1).

## Gaps
Found while writing tasks.md (grill clause). None weaken a gate.
- **TG1** T3 ordering: task/plan sequencing places T3 "whenever D1 answered"; listed after T9 here per plan Sequencing step 4. T3 option (a) depends on T2's `optional-user-scope` kind.
- **TG2** T1 Success uses pytest, CI uses unittest (G3). Gate kept verbatim; not reconciled.
- **TG3** T5 input cites `CLAUDE.md:45` (element 1) and `CLAUDE.md:9-12`; plan FR map lists only `:9-12` for FR-007. Both carried; `:45` not re-verified.
- **TG4** T8 input says "in #29 or follow-up"; plan says follow-up only unless marked "in #29". Left as follow-up; operator has not marked it.
- **TG5** T7 Success grep covers only "this account"/"this machine"; plan G6 notes facts at more lines (e.g. Devstral note, `:204` quota) that grep may miss. Failure gate ("any account-specific quota note left") is broader; execute against Failure.
- **TG6** T11 has no explicit gates in input; derived gates marked. Derived gates rest on spec.md US5 scenarios (`spec.md:126-130`).
- Line re-check: `.gitignore:224,226,227`, `skills.requirements.txt:20-22`, `codexagent.sh:24-25,52,54`, `preflight.sh:23`, `check_dispatch_prompt.py:20`, `cli.py:36,65,68` match plan. No wrong line numbers found.
