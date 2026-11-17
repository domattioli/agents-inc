<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Pre-Merge Verification Checklist: Decouple agents_Inc from DomI

**Purpose**: Verify feature `011-decouple-from-domi` meets all acceptance gates before merge.
**Created**: 2026-09-18
**Feature**: [spec.md](../spec.md) | [tasks.md](../tasks.md) | [plan.md](../plan.md)

---

## T1 — Track `agents_inc/keys.py`

- [ ] CHK001 Fresh clone, run `python3 -m pytest tests -q 2>&1 | grep -c "ModuleNotFoundError: No module named 'agents_inc.keys'"` returns 0 (T1 Success gate)
- [ ] CHK002 `.gitignore:226` area contains line `!agents_inc/keys.py` exception (T1 Success gate)
- [ ] CHK003 `agents_inc/keys.py` is source-only, no credentials — **non-printing check only** (constitution P1, `constitution.md:23`; analyze N-1 flagged the previous value-printing grep here as a leak): run `python3 -c "import ast,sys;print([n.name for n in ast.parse(open(sys.argv[1]).read()).body if hasattr(n,'name')])" agents_inc/keys.py` (top-level NAMES only) AND `grep -cE '=[[:space:]]*["\x27][A-Za-z0-9_-]{16,}["\x27]' agents_inc/keys.py` (count only, expect `0`). Non-zero → STOP and escalate; never print the matching line. (T1 Change 1)

## T2 — Fix `skills.requirements.txt` + `scripts/install_skills.sh`

- [ ] CHK004 `grep -rn "/Users/" skills.requirements.txt scripts/install_skills.sh` returns 0 hits (T2 Failure gate)
- [ ] CHK005 DomI sources use the URL form `source=github:domattioli/DomI@<ref>:skills/<name>` rather than absolute paths. **`<ref>` form (pinned sha vs branch) is D5, OPEN — do not check this item against `@<sha>` specifically.** (T2 Success gate; analyze N-3)
- [ ] CHK006 `skills.requirements.txt:22` (handoff-lint line) has no trailing parenthetical: `grep "handoff-lint.*(" skills.requirements.txt` finds 0 hits (T2 Success gate)
- [ ] CHK007 `optional-user-scope` kind exists in installer branches, checks `$HOME/.claude/skills/<name>` before dependency error (T2 Success gate)
- [ ] CHK008 On clean HOME (`HOME=$(mktemp -d)`), `bash scripts/install_skills.sh` exits 0 and `2>&1 | grep "OPTIONAL-MISSING"` finds ≥1 line (T2 Success gate)
- [ ] CHK009 On operator machine, `bash scripts/install_skills.sh` exits 0 and `2>&1 | grep "OPTIONAL-MISSING" | wc -l` returns 0 (T2 Success gate regression)
- [ ] CHK010 Installer `github:` kind does not fetch from network on clean run; document fallback message (T2 Success gate / plan R2)

## T4 — Make the D40 handoff-lint gate degrade explicitly

> **BLOCKED on D7** (operator sign-off + `docs/DECISIONS.md` entry + constitution P8 amendment). Every item below that edits `CLAUDE.md` presumes sign-off; none may be checked off until D7 answers. (analyze N-4)

- [ ] CHK011 On clean HOME (`HOME=$(mktemp -d)`), `python3 skills/workerbee/scripts/check_dispatch_prompt.py --with-handoff-lint /tmp/test.txt 2>&1 | head -1 | grep -q "handoff-lint NOT installed"` succeeds (T4 Success gate)
- [ ] CHK012 `CLAUDE.md:62` and `skills/workerbee/SKILL.md:640-661` reworded to "if script exists run it; if absent, emit warning line and continue" (T4 Success gate)
- [ ] CHK013 `check_dispatch_prompt.py --with-handoff-lint` on clean HOME prints warning but does not crash, exits with 14-element verdict only (T4 Failure gate)
- [ ] CHK014 `grep -n "python3.*~/.claude/skills/handoff-lint" CLAUDE.md skills/workerbee/SKILL.md | grep -v "if\|absent\|optional"` finds 0 unconditional paths (T4 Failure gate)
- [ ] CHK015 H1-H6 rules are restated inline in `skills/workerbee/SKILL.md:640-661`, reader can follow without DomI (T4 Success gate)

## T5 — Contract element 1 and caveman/nested-notes/write-like-scientist mandates

> **BLOCKED on D7** — same sign-off gate as T4. CHK016-020 presume it is granted. (analyze N-4)

- [ ] CHK016 Test fixture exists: dispatch prompt with element 1 as Skill-call line `Launching skill: caveman`, passes `check_dispatch_prompt.py` element 1 (T5 Success gate)
- [ ] CHK017 Test fixture exists: dispatch prompt with element 1 as emulation line `caveman NOT loaded -> emulating`, passes `check_dispatch_prompt.py` element 1 (T5 Success gate)
- [ ] CHK018 `check_dispatch_prompt.py:20` code explicitly accepts both forms (check regex/pattern for both patterns) (T5 Success gate)
- [ ] CHK019 `CLAUDE.md:9-12` (wording-mandate table) has same "if installed" language for `caveman`/`nested-notes`/`write-like-scientist` (T5 Failure gate)
- [ ] CHK020 `CLAUDE.md:45` (element 1 definition) states "invoke if skill installed; if call fails, emulate manually" (T5 Failure gate)

## T6 — `subagent-dispatch-policy` cross-reference in workerbee

- [ ] CHK021 Each reference to `subagent-dispatch-policy` at `skills/workerbee/SKILL.md:131,520,806` is qualified: "(a DomI skill; optional here — the rule this step needs is restated in full above)" (T6 Success gate)
- [ ] CHK022 `grep -n "see.*for.*rule\|see DomI\|see subagent-dispatch-policy" skills/workerbee/SKILL.md | grep -v "optional\|DomI skill"` finds 0 external-ref sentences (T6 Failure gate)
- [ ] CHK023 Step 0.5 and MUST 7 rules are complete in `skills/workerbee/SKILL.md` without external references; a reader with no DomI can follow them (T6 Success gate)
- [ ] CHK024 `cavecrew` has 0 references in workerbee: `grep -n "cavecrew" skills/workerbee/SKILL.md` finds 0 hits (T6 Failure gate / plan G8)

## T7 — Roster (Step 1a) and codex nicknames: separate canon from account facts

- [ ] CHK025 `grep -n "this account\|this machine\|limit: 0 on\|Devstral not exposed" skills/workerbee/SKILL.md` finds 0 hits (T7 Failure gate)
- [ ] CHK026 `agents_inc/install/runtime.py:8` `MODEL_ALIASES` is overridable via `AGENTS_INC_MODEL_MAP` env var or JSON file (T7 Success gate)
- [ ] CHK027 `agents_inc/routing.json:5-8` slug entries are not hardcoded strings; use override mechanism from T7 (T7 Success gate)
- [ ] CHK028 Unit test exists: `agents-inc run --model luna` resolves through override path; today's values are defaults (T7 Success gate)
- [ ] CHK029 Override file name does not collide with existing `agents_inc/models.json` catalog (T7 Success gate / plan G1)

## T8 — DelegateAgent MCP: installer + configurable model

- [ ] CHK030 `grep "gpt-5.6-luna" skills/codex-bridge/scripts/codexagent.sh skills/codex-bridge/mcp/codex_agent_mcp.py` finds 0 hardcoded literals (T8 Failure gate)
- [ ] CHK031 `codexagent.sh` reads `CODEXAGENT_MODEL_MAP` or `--slug`; `luna` is default, not only value; enum guard sources the map (T8 Success gate)
- [ ] CHK032 `codex_agent_mcp.py:47` (tools list enum) is built from same shared map as T7 defines (T8 Success gate)
- [ ] CHK033 `skills/codex-bridge/mcp/install.sh` exists, prints or applies `claude mcp add --scope user delegate-agent -- python3 "$(pwd)/codex_agent_mcp.py"` (T8 Success gate)
- [ ] CHK034 On clean HOME (`HOME=$(mktemp -d)`), `bash skills/codex-bridge/mcp/tests/smoke_mcp.sh --offline 2>&1 | grep -q "SMOKE PASS"` (T8 Success gate)
- [ ] CHK035 `codexagent.sh --model terra` with map including `terra` passes guard; live call still reports "would need account" (T8 Success gate)
- [ ] CHK036 `skills/codex-bridge/mcp/README` has one-paragraph Getting Started + the one-liner (T8 Success gate)
- [ ] CHK037 `codexagent.sh:4` comment is updated/removed (no longer documents luna-only mapping) (T8 Success gate / plan G5)

## T9 — Installer honesty

- [ ] CHK038 README step 9 documents "Codex CLI is a hard prerequisite of `agents-inc install`" (T9 Success gate)
- [ ] CHK039 `agents_inc/install/cli.py:36` guard `resolve_executable("codex", ...)` is conditional, not unconditional (T9 Failure gate)
- [ ] CHK040 `--without-codex` flag exists in install parser and repair parser; guards codex launcher install (T9 Success gate)
- [ ] CHK041 On a throwaway HOME (`HOME=$(mktemp -d)`), run the real entrypoint — `agents-inc install --source . --without-codex` (not `cli.py` directly; analyze N-6) — and confirm its output names what it did NOT do (the codex launcher). (T9 Failure gate: "installer exits without saying what it did not do")
- [ ] CHK042 `~/.claude/skills/workerbee` and `~/.claude/skills/codex-bridge` land even with `--without-codex` (T9 Success gate)
- [ ] CHK043 `agents_inc/doctor.py` reports `WB_CLI_NOT_FOUND` as a warning rather than a failure — today `doctor.py:46,78-79` maps it to `failed`. **Check against the concrete status value/exit code chosen under T9 Change 3; do not check against the token `UNTRUSTED_RELEASE`, which has 0 hits in `agents_inc/` (analyze N-6/F11).** (T9 Success gate)
- [ ] CHK044 `InstallReceipt` field handling clarified: optional codex field or other mechanism (T9 Success gate / plan R4)

## T3 — Decide grill-me / grill-with-docs (conditional on D1)

**Note**: These items are conditional on D1 decision. Check only if D1 is answered.

- [ ] CHK045 (IF D1 = delete): `test ! -d skills/grill-me && test ! -d skills/grill-with-docs` succeeds — both dirs gone from `skills/`. (T3 Success gate; analyze N-5: the previous `ls` form also listed this checklist file and matched on its own output)
- [ ] CHK046 (IF D1 = delete): `skills.requirements.txt:20-21` both `grill-me` and `grill-with-docs` are marked `source=optional-user-scope`, not present in `skills/` (T3 Success gate)
- [ ] CHK047 (IF D1 = fork): `grep -n "D35\|provenance\|fork" skills/grill-me/SKILL.md skills/grill-with-docs/SKILL.md | head -1` finds provenance header (T3 Success gate alt)
- [ ] CHK048 T3 Failure gate, stated over the real condition: for each name listed under a **non-`vendored`** kind in `skills.requirements.txt`, assert no directory of that name exists under `skills/` — e.g. `for n in $(awk -F';' '/source=(external-repo|github:|optional-user-scope)/{print $1}' skills.requirements.txt | awk -F'==' '{print $1}' | tr -d ' '); do test ! -d "skills/$n" || echo "VENDORED-CONFLICT $n"; done` returns no output. This covers both the literal gate and the non-vacuous guard at `tasks.md:133`. (analyze N-5: the previous `grep -l ... skills/*/SKILL.md` always self-matched `skills/grill-me/SKILL.md` and never tested the gate)

## T10 — Portability CI lane

- [ ] CHK049 `.github/workflows/tests.yml` (or new workflow) has portability lane that sets `HOME=$(mktemp -d)` (T10 Success gate)
- [ ] CHK050 Lane removes codex/claude/gemini from PATH before running installer and tests (T10 Success gate)
- [ ] CHK051 Lane runs `bash scripts/install_skills.sh`, expects exit 0 (T10 Success gate)
- [ ] CHK052 Lane runs `python3 -m pytest tests -q`, checks for 0 collection errors (T10 Success gate)
- [ ] CHK053 Lane runs `governance_demo --fake`, expects exit 0 (T10 Success gate)
- [ ] CHK054 `grep -rn "/Users/" .github/workflows/tests.yml tests/test_portability.py` (if exists) finds 0 hardcoded paths (T10 Failure gate)
- [ ] CHK055 Lane code does not reference `~/.claude/skills` content as a precondition (T10 Failure gate)

## T11 — Pre-existing breakage found during the sim

- [ ] CHK056 bash 3.2 compat: `/bin/bash skills/speckit-pipeline/scripts/preflight.sh specify 2>&1 | grep -q "unbound variable"` must **exit non-zero** (i.e. the error is absent). Check with `! /bin/bash ... | grep -q "unbound variable"`. (T11; analyze N-5: the previous form used `grep -q` such that finding the error counted as success — inverted)
- [ ] CHK057 `grep "declare -A SKILL_DIR_MAP" skills/speckit-pipeline/scripts/preflight.sh` finds 0 hits; replaced with `case` form (T11 Failure gate)
- [ ] CHK058 (IF D6 = fix): `pytest tests/test_config_schema.py -q 2>&1 | tail -1` shows 0 failures (T11 Success gate)
- [ ] CHK059 (IF D6 = file): separate issue #NNN filed for 6 `test_config_schema.py` failures, NOT folded into portability PR (T11 Success gate)
- [ ] CHK060 Fix is in its own issue/PR, NOT merged with portability PR (T11 Failure gate)

---

## Cross-cutting

*Acceptance from spec.md Success Criteria SC-001 through SC-004, plus constraints.*

- [ ] CHK061 SC-001 — On a machine with no DomI and no Codex CLI, `git clone` + `install_skills.sh` (exit 0) + `pytest tests -q` (green) + `governance_demo --fake` (exit 0) all pass (T1, T2, T4-T9)
- [ ] CHK062 SC-002 — `grep -rn "/Users/" skills.requirements.txt scripts/install_skills.sh` returns 0 hits. **Do not include `specs/011-decouple-from-domi/` in the grep**: these planning artifacts quote the absolute paths as evidence, so including them makes the check unpassable, and SC-002 (`spec.md:199`) names only the manifest and installer. (analyze N-5)
- [ ] CHK063 SC-003 — Every DomI-skill reference (`handoff-lint`, `caveman`, `nested-notes`, `write-like-scientist`, `subagent-dispatch-policy`) in canon is marked optional + fallback stated (T4, T5, T6)
- [ ] CHK064 SC-004 — Portability lane is green on clean runner (no DomI, no codex) (T10)
- [ ] CHK065 Constraint — no writes outside `specs/011-decouple-from-domi/`: `git status --short | grep -vE "^\?\? specs/011-decouple-from-domi/|^\?\? docs/proposals/"` returns no lines. (analyze N-5: the previous `^ specs/` pattern could never match `git status --short` output, which prefixes `?? `; `docs/proposals/` was already untracked before this feature)
- [ ] CHK066 Constraint — No paid model calls in code paths (no gpt-4o, claude-opus calls; grep agent dispatch code)
- [ ] CHK067 Constraint — No wholesale DomI vendoring; single scripts with provenance headers only where gates depend (verify no `skills/` copies of full DomI skills)
- [ ] CHK068 Constraint — PR #29 + DomI PR #504 remain mergeable; changes here are follow-up PR (verify files do not overlap with those PRs)

---

## Added after analyze cycle 2 (coverage gaps)

These cover gates that had no item. Numbering continues from CHK068.

- [ ] CHK069 T1 non-printing check was actually used: the implementation notes/PR show the `ast` name-list + `grep -c` pair (`tasks.md:14`), and no transcript or log contains a value from `agents_inc/keys.py`. (T1 Change 1; constitution P1)
- [ ] CHK070 T3 non-vacuous guard (`tasks.md:133`): re-run CHK048's loop over ALL non-`vendored` kinds, not only `external-repo`, so the gate cannot pass merely because T2 removed the `external-repo` kind.
- [ ] CHK071 T4 exit semantics defined and honoured (`tasks.md:54`): `check_dispatch_prompt.py --with-handoff-lint` exits 0 iff all 14 elements pass, non-zero otherwise, and the `handoff-lint NOT installed -> H1-H6 checked by hand` line goes to the documented stream (stdout stays machine-parseable).
- [ ] CHK072 T4 report direction (`tasks.md:55`): the `--profile report` side of the D40 gate degrades the same way. Note this is new code — `grep -n "profile" skills/workerbee/scripts/check_dispatch_prompt.py` currently returns 0 hits.
- [ ] CHK073 T8 `--apply` rule (`tasks.md:99`): no `--apply` was run against the real `HOME`. Check `~/.claude.json` mtime is unchanged across the implementation window, or that the only run used a throwaway `HOME`.
- [ ] CHK074 T2 verification used a fresh clone, not merely a fresh `HOME` — `install_skills.sh:30,52-53` writes into the repo's own `skills/`. (plan Constraints)

---

## Open decisions

Operator answers needed; items depending on them are flagged conditional.

- **D1** (blocks T3): delete `grill-me`/`grill-with-docs` + mark `optional-user-scope`, or keep as provenance-headed fork. **Answer affects CHK045–CHK047.**
- **D3** (affects T5 wording): caveman level name agents_Inc standardises on. Default: keep `ultra`, state it is agents_Inc's own choice.
- **D4** (affects T7 file path): account-facts destination: `~/.config/workerbees/roster.md` or install receipt. Spec's recommendation was "install receipt", but **analyze F1 (CRITICAL) found `InstallReceipt` (`agents_inc/install/receipt.py:33-39`) has no account-facts field**, so that branch implies an unplanned schema change. Destination is **TBD — do not treat the recommendation as answered**, and no checklist item here presumes it.
- **D7** (blocks T4 + T5): operator sign-off for the `CLAUDE.md` edits, a `docs/DECISIONS.md` entry, and a constitution P8 amendment (P8 calls contract element 1 unconditional). Also resolves the D40 label collision. **No default — T4/T5 items below cannot be checked off until D7 answers.**
- **D5** (affects T2 source form): pin DomI URL to `<sha>` or branch. Default: pin `<sha>`.
- **D6** (affects T11): fix or file the 6 `test_config_schema.py` failures. Default: file + fix `preflight.sh` (bash 3.2) only.

---

## Gaps

Issues found during checklist writing; none weaken acceptance gates.

- **G1**: `agents_inc/models.json` catalog already exists. T7 override file must use non-colliding name; selection not yet made.
- **G2**: `--with-handoff-lint` flag is new code, not a wording change; implementation required.
- **G3**: T1 Success gate uses `pytest collection` but CI uses `unittest discover`; both can be tested, verified against Failure gate (module import error).
- **G4**: T8 guard allows `terra` (behavior change from luna-only); test fixture required.
- **G5**: `codexagent.sh:4` comment documents luna mapping; update/remove during T8.
- **G6**: T7 account-facts appear at more SKILL.md lines than grep hint suggests (`:187,204,227,245,829`); Failure gate "any account-specific quota note" is broader than "this account"/"this machine" grep.
- **TG2**: T1 Success gate uses `pytest tests -q` (spec.md:32), CI uses `unittest discover` (tests.yml:18); both valid, gate kept as specified.

---

**Last updated**: 2026-09-18
