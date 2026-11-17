<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Decouple agents_Inc from DomI and operator machine

**Branch**: `011-decouple-from-domi` | **Date**: 2026-09-18 | **Spec**: specs/011-decouple-from-domi/spec.md

## Summary
Make a fresh clone run green with no DomI checkout, no Codex CLI and no operator-specific paths. Approach: track the gitignored source module, kill absolute paths in the skills manifest and installer, make DomI-provided skills optional with a loud one-line fallback, move account facts out of canon, share one model map across the Codex wrappers, add a CI portability lane, and fix the bash-3.2 preflight bug.

## Technical Context
- Language: Python 3.11 (CI, `.github/workflows/tests.yml:14-16`), bash (macOS bash 3.2 must work).
- Testing: CI runs `PYTHONPATH=. python3 -m unittest discover -s tests` (`tests.yml:18`). Spec cites pytest (`spec.md:32`). See Gaps G3.
- Storage: files only. Install receipt is generated per machine (`agents_inc/install/cli.py:36-40`).
- Target: any clone, HOME empty, PATH without codex/claude/gemini.
- Constraints: see Constraints section.

## Repo facts (evidence)
- `.gitignore:224` `*key*`; `.gitignore:226-227` are the `!workerbees/keys.py` and `!tests/test_keys.py` exceptions. `git check-ignore -v agents_inc/keys.py` prints `.gitignore:224:*key*`. The file exists on disk but `git ls-files agents_inc/keys.py` is empty, so it is untracked. (FR-001 root cause confirmed.)
- `skills.requirements.txt:20-21` are grill-me and grill-with-docs, with absolute `/Users/domattioli/Projects/DomI/...` paths. `:22` is the handoff-lint entry, with a trailing parenthetical after the path. `:23` speckit-pipeline is vendored (D35 fork). `:17,18,19,24` are the vendored entries.
- `scripts/install_skills.sh`: `:42-48` external-repo branch does `[[ ! -d "$src_path" ]]` then MISS with `status=1`. `:43` `sed` extracts the path, so the parenthetical is absorbed into the path. `:52-53` does `rm -rf "$dest"; cp -R`, which silently overwrites `skills/<name>`. `:59` prints SKIP for unrecognized source kinds. `:14` parses only `--dry-run`.
- `agents_inc/install/runtime.py:8` `MODEL_ALIASES` is hardcoded. `:22` resolves through it. `:14,17` raise `WB_CLI_NOT_FOUND`.
- `agents_inc/routing.json:5-8` hardcodes Codex slugs per tier. `:2` lists `"required": ["claude","codex"]`.
- `agents_inc/install/cli.py:65` `install` takes `--source` and `--adopt-existing-workerbee` only. `:36` `resolve_executable("codex", ...)` is called unconditionally inside install, so a missing codex fails install. `:68` `repair` has the same args.
- `skills/codex-bridge/scripts/codexagent.sh`: `:24-25` rejects any model other than `luna`. `:52,54` hardcode `gpt-5.6-luna` in the `codex exec` calls. Line 4 comment: "luna=gpt-5.6-luna … terra/sol/astra not wired yet".
- `skills/codex-bridge/mcp/codex_agent_mcp.py:47` `"enum": ["luna"]`, `:48` default luna, `:75` `args.get("model","luna")`, `:97` shells to the script with `--model`. Tests at `skills/codex-bridge/mcp/tests/smoke_mcp.sh`. No `mcp/install.sh` exists.
- `skills/workerbee/scripts/check_dispatch_prompt.py:20` element 1 keyword is only `"caveman ultra"`. No `--with-handoff-lint` flag exists in the file.
- `CLAUDE.md:9-12` is the wording-mandate table. `CLAUDE.md:62` is the D40 gate, hardwired to `~/.claude/skills/handoff-lint/...`.
- `skills/workerbee/SKILL.md`: `:131,520,806` are the `subagent-dispatch-policy` references. `:187,204,227,245,829` carry account/machine facts (`:204` "limit: 0 on this account"). `:640-661` is the D40 mechanical gate section.
- `skills/speckit-pipeline/scripts/preflight.sh:23` is `declare -A SKILL_DIR_MAP=(` (bash 4+ only).
- `skills/` holds codespace-exec, codex-bridge, doc-analysis, grill-me, grill-with-docs, speckit-pipeline, workerbee. So grill-me and grill-with-docs exist both in `skills/` and as external-repo manifest entries (FR-005 confirmed).
- `.github/workflows/tests.yml` has a single `unittest` job on ubuntu-latest and no portability lane.

## Constitution Check
Evaluated against `.specify/memory/constitution.md` v1.7.0 (status `proposed`, `ratified: false` — violations are WARN by its own enforcement, severities below reflect impact on this feature). Supersedes the earlier "not evaluated" note and closes gap G9.

- **P0** cross-reference-never-duplicate — OK; these artifacts cite canon rather than restating it.
- **P1** repo-scoped writes — three WARNs, all now carried as task constraints: T1's key-material check (`analyze F5`, resolved to a non-printing mechanical check), T8's `mcp/install.sh --apply` writing user config (`analyze F13`), and the temp-HOME rule for verification (`analyze F14`).
- **P2** labor ladder — not touched by this feature.
- **P3** no self-graded gates — OK; gates are command-checkable, except the wording issues at `analyze F8` (T4 exit code undefined) and `F11` ("untrusted release" has no referent). Both are artifact-wording fixes, not gate changes.
- **P4** deterministic policy over prompt — not touched.
- **P5** hard $0 — OK; no paid calls, the `github:` fetch is free, and T8's live call stays "would need account".
- **P8** (contract elements) — **impacted**. T4/T5 make element 1 conditional, which amends P8 and edits `CLAUDE.md`, whose own footer requires operator sign-off. Tracked as open decision **D7**.

## Constraints
- Repo-scoped writes only. No writes to `~/.claude/**`, `~/.codex`, `~/.claude.json`.
- No paid model calls during implementation or verification. The T8 live call stays "would need account".
- No wholesale DomI vendoring (#326). Copying a single script with a provenance header and upstream hash is allowed only where a gate depends on it and the task says so.
- Follow-up PR only. Keep PR #29 and DomI PR #504 mergeable. Do not touch files those PRs own unless the task is marked "in #29".
- **Every verification that touches a user-scope path runs against a throwaway `HOME`** (analyze F14). This binds T2 — and note a throwaway `HOME` alone is **not** sufficient for T2, because `install_skills.sh:30,52-53` writes into the **repo's own** `skills/` via `rm -rf` + `cp -R`; T2 verification needs a fresh clone (or a disposable worktree), not just a fresh `HOME`, T8 (`mcp/install.sh --apply` runs `claude mcp add --scope user`, writing `~/.claude.json`) and T9 (`agents-inc install` lands `~/.claude/skills/*`). Constitution P1 forbids writes outside the dispatching repo, so a verification run against the real `HOME` is itself a violation, not just untidy.
- Never read or print `.env`, `~/.codex/**`, `~/.claude.json` or `*key*` file contents. This constrains T1: track `agents_inc/keys.py` by gitignore exception only. Before staging it, the implementer must confirm it holds no credential values, without printing them.

## Work-item groups and approach

**G-A Clean clone (T1, T2), P1, do first**
- T1 / FR-001: add `!agents_inc/keys.py` next to `!workerbees/keys.py` at `.gitignore:226`. Then track the file. The implementer must first confirm it is source, not credentials (it is the code that `import agents_inc.keys` needs).
- T2 / FR-002, FR-003, FR-004: edit `skills.requirements.txt:20-22`. Replace absolute paths with `source=github:domattioli/DomI@<sha>:skills/<name>` (sha choice is D5, open). Strip the `:22` parenthetical into a comment line. Add source kind `optional-user-scope`. In `scripts/install_skills.sh`, add a branch before `:42` that checks `$HOME/.claude/skills/<name>`, prints `OPTIONAL-MISSING <name>` and never sets `status=1`. Handle the `github:` kind without `cp` from an absolute path (fetch or skip-with-message; no network needed on a clean run).
- Tests: shell test that runs the installer with an empty HOME and asserts exit 0. Also grep `/Users/` on the manifest and installer (SC-002).

**G-B Optional DomI skills (T4, T5, T6), P1**
- T4 / FR-006: add `--with-handoff-lint` to `check_dispatch_prompt.py`. Resolve `$HOME/.claude/skills/handoff-lint/scripts/handoff_lint.py`. If absent, print exactly `handoff-lint NOT installed -> H1-H6 checked by hand` and return the 14-element verdict only. Reword `CLAUDE.md:62` and `SKILL.md:640-661` to conditional.
- T5 / FR-007: extend the element-1 keywords at `check_dispatch_prompt.py:20` to also accept the emulation line (`caveman NOT loaded -> emulating`). Reword `CLAUDE.md:9-12` for `nested-notes` and `write-like-scientist` fallbacks. Add one test fixture per form. Level name is D3 (open).
- T6 / FR-008: qualify `SKILL.md:131,520,806` once each as an optional DomI skill and restate the rule in-repo. Restate the Step 0.5 / MUST 7 rules so no "see X" points outside the repo.

**G-C Account facts and model map (T7, T8, T9), P2**
- T7 / FR-009: strip account rows and quotas from `SKILL.md:187,204,227,245,829` into a generated file (location is D4, open). Make `MODEL_ALIASES` (`runtime.py:8`) and `routing.json:5-8` overridable with today's values as defaults, plus a unit test through the override path for `--model luna`. Override vehicle: `AGENTS_INC_MODEL_MAP` env and/or a JSON file. See Gaps G1 on the `models.json` name collision.
- T8 / FR-010: create one shared map that both `codexagent.sh` (remove hardcodes at `:52,54`, replace the luna-only guard at `:24-25`) and `codex_agent_mcp.py` (`:47,48,75`) read. Add `skills/codex-bridge/mcp/install.sh`. Add `--offline` to `mcp/tests/smoke_mcp.sh`, stopping after `tools/list` with `SMOKE PASS`. Document the README one-liner.
- T9 / FR-011: add `--without-codex` to the `install` parser at `cli.py:65` (and likely `repair` at `:68`). Guard the unconditional `resolve_executable("codex", ...)` at `cli.py:36`. `doctor` must report `WB_CLI_NOT_FOUND` as a warning. README states the Codex-CLI prerequisite. Installer prints what it did not do.

**G-D Ownership conflict (T3) — BLOCKED on D1**
- T3 / FR-005: BLOCKED on operator decision D1 (delete `grill-me`/`grill-with-docs` and mark `optional-user-scope`, or keep as a provenance-headed fork). This plan does not pick an answer. No design, files or tests for T3 are committed to until D1 is answered. Facts only: both dirs exist in `skills/` and in `skills.requirements.txt:20-21`; the installer overwrites them at `install_skills.sh:52-53`.

**G-E Guard (T10), P2, last of the portability set**
- T10 / FR-012: add a job to `.github/workflows/tests.yml` (or a sibling workflow) that simulates a clean clone: `HOME` set to an empty tmpdir, PATH stripped of codex/claude/gemini, then runs the installer, the test suite and `governance_demo --fake`. It must depend on no `/Users/` path and no `~/.claude/skills` content. Lands after T1, T2, T4-T9 so it starts green. If T3 is still blocked, the lane must tolerate the grill entries via the T2 `optional-user-scope` path, and that interplay is D1-dependent.

**G-F Pre-existing breakage (T11), P3, separate issue**
- T11 / FR-013: replace `declare -A SKILL_DIR_MAP` at `preflight.sh:23` with the `case` form DomI's copy already uses. Verify on bash 3.2. The 6 `test_config_schema.py` failures are handled by an issue (fix vs file-only is D6, open). Separate from the portability PR.

## FR to file-touch map
| FR | Task | Files |
|---|---|---|
| FR-001 | T1 | `.gitignore` (:226 area), `agents_inc/keys.py` (track) |
| FR-002 | T2 | `skills.requirements.txt`, `scripts/install_skills.sh` |
| FR-003 | T2 | `skills.requirements.txt:22`, `scripts/install_skills.sh:43` |
| FR-004 | T2 | `scripts/install_skills.sh`, `skills.requirements.txt` |
| FR-005 | T3 BLOCKED D1 | `skills.requirements.txt:20-21`, `skills/grill-me/`, `skills/grill-with-docs/` (change set depends on D1) |
| FR-006 | T4 | `skills/workerbee/scripts/check_dispatch_prompt.py`, `CLAUDE.md:62`, `skills/workerbee/SKILL.md:640-661`, new test |
| FR-007 | T5 | `check_dispatch_prompt.py:20`, `CLAUDE.md:9-12`, 2 test fixtures |
| FR-008 | T6 | `skills/workerbee/SKILL.md:131,520,806` (and Step 0.5 / MUST 7 text) |
| FR-009 | T7 | `agents_inc/install/runtime.py:8,22`, `agents_inc/routing.json:5-8`, `skills/workerbee/SKILL.md:187,204,227,245,829`, **destination file TBD by D4** (do not pre-name; see analyze F1 — `InstallReceipt` at `agents_inc/install/receipt.py:33-39` has no account-facts field, so the receipt branch implies an unplanned schema change), new unit test |
| FR-010 | T8 | `skills/codex-bridge/scripts/codexagent.sh:4,24-25,52,54`, `skills/codex-bridge/mcp/codex_agent_mcp.py:47,48,75`, new `skills/codex-bridge/mcp/install.sh`, `skills/codex-bridge/mcp/tests/smoke_mcp.sh`, README |
| FR-011 | T9 | `agents_inc/install/cli.py:36,65,68`, `agents_inc/doctor.py`, README |
| FR-012 | T10 | `.github/workflows/tests.yml` or new workflow file, possibly a script |
| FR-013 | T11 | `skills/speckit-pipeline/scripts/preflight.sh:23`, `tests/test_config_schema.py` (per D6) |

## Sequencing
1. T1, T2 first (P1, unblock everything; T1 clears the 11 collection errors, T2 unblocks the installer).
2. T4, T5, T6 — **not** dependent on T2 (none of them touch the installer; analyze F15). They must be **serialized with each other and with T7** because all four edit `skills/workerbee/SKILL.md` at different line ranges. T4 and T5 are additionally **blocked on D7**.
3. T7 then T8 (T8 consumes the shared map T7 defines), then T9.
4. T3 whenever D1 is answered. Not on the critical path of T1/T2/T4-T9. It gates a fully clean T10 only if the grill entries need a decision.
5. T10 last of the portability set.
6. T11 anytime, own issue and PR.

## Risks
- R1 T1: `agents_inc/keys.py` may contain real key material. Mitigation: implementer checks shape without printing values. If secrets are present, stop and escalate.
- R2 T2: the `github:` source kind needs network or a cache. The clean-run path must not depend on it. Mitigation: `optional-user-scope` for anything optional.
- R3 T7/T8: changing model slugs risks breaking live routing. Defaults must equal today's values, unit-tested.
- R4 T9: `cli.py:36` receipt requires a codex path. `InstallReceipt` may need an optional field, which may affect receipt-schema readers.
- R5 T4/T5: loosening the checker could weaken a binding gate. Emulation acceptance must be explicit, not fuzzy.
- R6 PR mergeability: files touched here may overlap PR #29 / DomI #504. Not verifiable from the repo alone (see Gaps G8).

## Open operator decisions (carried forward, NOT answered here)
- D1 blocks T3. Delete plus `optional-user-scope`, or provenance-headed fork. OPEN.
- D2 shared skills package. Deferred, out of scope. OPEN.
- D3 caveman level name for T5 wording. OPEN.
- D4 T7 account-facts destination (roster.md vs install receipt). OPEN.
- D5 T2 DomI URL pin form (sha vs branch). OPEN.
- D6 T11 whether schema failures are fixed or only filed. OPEN.
- D7 blocks T4 + T5 (raised by analyze F6). Operator sign-off for the `CLAUDE.md` edits, a `docs/DECISIONS.md` entry, and an explicit constitution P8 amendment, since T4/T5 make contract element 1 conditional and P8 calls it unconditional. Includes resolving the D40 label collision (`docs/DECISIONS.md:414` is an unrelated ruling). OPEN.

(The spec's "Recommended default" column is a recommendation to the operator, not adopted by this plan.)

## Gaps
- **G1**: FR-009 says to make routing overridable via `agents_inc/models.json`. That file already exists and is tracked, with a different purpose: a model catalog (`"models": {...}`, vendor/tier/tasks_good, `_note` at line 3). Reusing that name would collide. Needs a naming decision; not chosen here.
- **G2**: FR-006's `--with-handoff-lint` flag does not exist in `check_dispatch_prompt.py` today. It is new work, not a wording change.
- **G3**: spec acceptance uses `python3 -m pytest tests -q` (`spec.md:32`); CI runs `unittest discover` (`tests.yml:18`). The T10 lane must decide which runner it reproduces. Not decided here.
- **G4**: FR-010's `codexagent.sh --model terra` passing the guard is a behavior change, not only a refactor — today the guard is luna-only (`codexagent.sh:24-25`) and the MCP enum is `["luna"]` (`codex_agent_mcp.py:47`).
- **G5**: `codexagent.sh:4` also documents "luna=gpt-5.6-luna"; T8 must update or remove it, beyond the `:52,54` literals the spec names.
- **G6**: SKILL.md account facts appear at more lines than the spec's grep hint covers (`:187,204,227,245,829`). `:204`'s "limit: 0 on this account" is quota content, not just a wording swap. Hit count not exhaustively verified.
- **G7**: `CLAUDE.md:62` and `SKILL.md:640-661` citations confirmed.
- **G8**: PR #29 and DomI PR #504 state not verifiable from the repo; no `gh` calls made.
- **G9**: ~~constitution file not read~~ — **CLOSED**. Evaluated in the Constitution Check section above (v1.7.0, P1 WARNs carried as task constraints, P8 impacted → decision D7).
- **G10**: `skills/*/MANIFEST.md` does not exist in this repo, so DomI-style manifest assumptions do not transfer.
