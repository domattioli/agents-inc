<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Analyze cycle 2: 011-decouple-from-domi (verify cycle-1 fixes, adversarial)

Date 2026-09-18. Read-only. No artifact edited. Inputs read whole: analyze-2026-09-18.md, spec.md, plan.md, tasks.md, checklists/requirements.md, original plan-decouple-agents_inc.md.
Status vocab: RESOLVED / PARTIAL / UNRESOLVED / NOT-ATTEMPTED. Severity = cycle-1 severity unless stated.

## Fix verification (F1..F21)

| ID | Cycle-1 ID | Status | Location | Note |
|---|---|---|---|---|
| C2-01 | F1 (CRITICAL) | RESOLVED | tasks.md:88; plan.md:87 | T7 Files and FR-009 row now say "destination file TBD by D4", receipt schema gap (receipt.py:33-39) recorded as D4-conditional. No file-touch names install-receipt code any more. Residual: spec.md:190 D4 keeps "Install receipt" as recommended default (labelled recommendation, ok). |
| C2-02 | F2 (HIGH) | RESOLVED | spec.md:138-140 | FR-002 now `@<ref>` + "D5 OPEN, must not narrow". Residual, see N-3: plan.md:54 and CHK005 still hardcode `<sha>`. |
| C2-03 | F3 (HIGH) | PARTIAL | tasks.md:28,31-40; spec.md:143 | Table added, but (a) spec.md:143 FR-004 and tasks.md:28 still say "third source kind" while the table now lists `vendored`, `optional-user-scope`, `github:` (and `external-repo` still referenced in T3); (b) skip token for `github:` is only "e.g. `REMOTE-SKIPPED`", not named; (c) tasks.md:40 tells the implementer to "state whether github: counts as optional", i.e. the deciding is deferred, so the T2 Success wording "every optional skill as OPTIONAL-MISSING" is still not verifiable. See N-2. |
| C2-04 | F4 (HIGH) | RESOLVED | tasks.md:30,133 | `github:` fetch target barred from `$REPO_ROOT/skills/<name>` (cites install_skills.sh:30,52-53); T3 non-vacuous guard added. plan.md:54 and plan.md T3 (:68) do not carry the constraint (omission, no contradiction). Guard judged TIGHTENING, see regression. |
| C2-05 | F5 (HIGH) | RESOLVED (task) / regressed (checklist) | tasks.md:14; plan.md:35,48 | T1 now a non-printing `ast` name-list + `grep -c` count, STOP on non-zero, "value printed = RED". Repo check: the grep pattern with `\x27` matched both quote styles on this host's grep (tested on synthetic input). BUT checklist CHK003 (requirements.md:13) reintroduces a value-printing grep on keys.py, see N-1 (HIGH). |
| C2-06 | F6 (HIGH) | RESOLVED (recorded) / PARTIAL (propagation) | spec.md:193; plan.md:116; tasks.md:59,74,168-169 | D7 added in all three, T4/T5 carry "Blocked". Repo confirmed: docs/DECISIONS.md:414 is "D40 — LESSON-CANDIDATE: stale long-lived server proc", CLAUDE.md:62 cites D40 for handoff lint. Propagation gaps: plan.md G-B (:57) and Sequencing (:95) do not mark T4/T5 blocked; T7-T10 chain (tasks.md:95,110,123,144) does not mention D7; checklist "Open decisions" omits D7. See N-4. |
| C2-07 | F7 (MEDIUM) | PARTIAL | plan.md:31-40 vs :129; tasks.md:181 | Constitution Check evaluated at plan.md:32 ("closes gap G9"), but plan.md:129 still says "G9: constitution file not read" and tasks.md:181 "NEEDS CHECK before implement". Direct contradiction remains. |
| C2-08 | F8 (MEDIUM) | PARTIAL | tasks.md:54; spec.md:61 | Exit semantics defined ("exit 0 iff all 14 pass"), but stream is only "stderr recommended", not decided; case handoff-lint present-and-failing unspecified; spec.md:61 unchanged. |
| C2-09 | F9 (MEDIUM) | RESOLVED | tasks.md:55 | Report-direction sub-item added. New fact: `grep profile skills/workerbee/scripts/check_dispatch_prompt.py` = 0 hits, so `--profile report` (CLAUDE.md:62) does not exist in the script either; tasks.md:55 says "flag behaviour" without noting it is new code (plan G2 covers only `--with-handoff-lint`). Minor. |
| C2-10 | F10 (MEDIUM) | NOT-ATTEMPTED | plan.md:123 (G3); tasks.md:175,188; requirements.md:139,143 | pytest vs unittest still "not decided here", no owner or decision id. Checklist calls both "valid". |
| C2-11 | F11 (MEDIUM) | PARTIAL | tasks.md:119; spec.md:94; requirements.md:74 | Task tells implementer to define the observable first; nothing defined. Success text unchanged (verbatim, correct). Checklist CHK043 invents token `UNTRUSTED_RELEASE`; `grep -rn UNTRUSTED_RELEASE agents_inc` = 0 hits. |
| C2-12 | F12 (MEDIUM) | RESOLVED | spec.md:154-157 | Override file "name TBD, NOT models.json", cites plan G1; consistent with plan.md:63,121. |
| C2-13 | F13 (MEDIUM) | PARTIAL | tasks.md:98-99 | Re-tag note + `--apply` verification constraint added, but Size still reads "small", and :99 is self-contradictory: "Any `--apply` run ... = RED" vs "exercise `--apply` only against a throwaway HOME if at all". Is a throwaway-HOME `--apply` RED or allowed? Ambiguous, do not guess. |
| C2-14 | F14 (MEDIUM) | PARTIAL | plan.md:47; spec.md:34,88,92 | Throwaway-HOME rule added to plan Constraints. Spec acceptance wording unchanged (recommended by F14). Also plan.md:47 says a throwaway HOME handles T2, but install_skills.sh:52-53 writes to `$REPO_ROOT/skills`, which HOME does not redirect; T2 verification needs a fresh clone (spec.md:26-28 says so, plan.md:47 does not). |
| C2-15 | F15 (LOW) | PARTIAL | tasks.md:58,73,83; plan.md:95 | Tasks fixed ("serialize, same file SKILL.md"). plan.md:95 still says T4-T6 "independent of each other, after T2 for the installer semantics": plan and tasks disagree. |
| C2-16 | F16 (LOW) | RESOLVED | tasks.md:135; plan.md:97 | "Not on critical path" stated at T3 and in plan Sequencing. Header line tasks.md:5 unchanged (cosmetic). |
| C2-17 | F17 (LOW) | NOT-ATTEMPTED | tasks.md:10 | "one-line" tag kept; informational, no fix required. |
| C2-18 | F18 (LOW) | PARTIAL | tasks.md:141; spec.md:28,193(SC-001); requirements.md:92 | Exact command `python3 tools/governance_demo.py --fake` added in tasks (file exists, verified `ls tools/governance_demo.py`). spec SC-001/US1 and CHK053 still bare `governance_demo --fake`. |
| C2-19 | F19 (LOW) | NOT-ATTEMPTED | tasks.md:155 | Derived T11 Failure clause unchanged. Acceptable (labelled derived). |
| C2-20 | F20 (LOW) | NOT-ATTEMPTED | n/a | Out of feature scope by cycle-1's own note. |
| C2-21 | F21 (LOW) | PARTIAL | tasks.md:16 | "(run root owns commit/push authority)" appended, but the delegate instruction still says `git add`. Staging authority ambiguity stands. |

## New findings

| ID | Sev | Location | Finding | Fix |
|---|---|---|---|---|
| N-1 | HIGH | requirements.md:13 (CHK003) | `grep -E "^[A-Z_]+ = " agents_inc/keys.py` prints every matching line WITH its value. This reintroduces the exact leak F5 closed in tasks.md:14, and violates constitution P1 (constitution.md:23, printing key material forbidden at every rung) and the CLAUDE.md `*key*` rule. The item's own prose says "never print values". | Replace CHK003 with the tasks.md:14 pair (ast name list; `grep -cE ...` expect 0). |
| N-2 | MEDIUM | tasks.md:40 | Deferring "does `github:` count as optional" to the implementer lets the T2 Success line be read two ways; one reading LOOSENS it (github: entries need no OPTIONAL-MISSING). Gate text itself is verbatim, so not CRITICAL, but latitude is a loosening path. | Decide in the artifact: `github:` skip prints a named token, and the T2 gate is stated over every non-vendored entry. |
| N-3 | MEDIUM | requirements.md:18 (CHK005), :127-128; plan.md:54 | CHK005 asserts `@<sha>` as the pass form, presuming D5 = sha. "Open decisions" section restates D4/D5/D6 recommended defaults as "Default:", easy to read as adopted. | CHK005: "`@<ref>` form per D5 outcome". |
| N-4 | MEDIUM | tasks.md:95,110,123,144-145; plan.md:95; requirements.md:121-130 | D7 blocks T4/T5; T7 depends on T4-T6, T8 on T7, T9 on T7, T10 on T4,T5..T9. Only T4/T5 say "Blocked". T10 Blocked line says "only if grill entries unresolved". Checklist Open decisions omits D7 and CHK012,016-020 (the T4/T5 outcome checks) presume D7 = sign-off granted. | State D7 transitive block on T7-T10 (sequencing) and in plan G-B; add D7 to checklist decisions; mark T4/T5 checks conditional. |
| N-5 | HIGH | requirements.md:81,84,98,110,111,114 (CHK045,048,056,062,065; also 009) | Mechanical defects in checkable items: CHK048 is labelled "T3 Failure gate" but tests something else (`grep -l "grill-me" skills/*/SKILL.md` always hits skills/grill-me/SKILL.md itself); original T3 Failure = dir in both skills/ and manifest, guard tasks.md:133 uncovered. CHK062 greps `/Users/` over specs/011-decouple-from-domi/, which contains it in spec.md (4), tasks.md (5), the checklist (3): can never pass, and SC-002 (spec.md:199) only names manifest+installer. CHK065 pattern `^ specs/...` cannot match `git status --short` output (`?? specs/...`), and docs/proposals/ is untracked outside it. CHK045 ls target lists the checklist file itself. CHK056 `grep -q` succeeds on the error text, so "finds no error" is inverted. CHK009 (`OPTIONAL-MISSING` count 0 on operator machine) is stronger than the gate ("no MISS line") and wrong if an optional skill is legitimately absent. These break P3 (command-checkable gates). | Rewrite listed items; cover the T3 non-vacuous guard. |
| N-6 | MEDIUM | requirements.md:72,41,74 (CHK041,043,062) | CHK041 invokes `agents_inc/install/cli.py --source .` (not the `agents-inc install` entry); CHK043 uses invented `UNTRUSTED_RELEASE`; `did not\|skipped` grep is not tied to any defined message. | Align with defined observables (see C2-11). |
| N-7 | LOW | requirements.md:115,116,117,63 (CHK063,066,067,068) | Not mechanically checkable (CHK066 "grep agent dispatch code" no pattern; CHK068 unverifiable per plan G8; CHK015, CHK023 subjective). | Convert to a command or mark manual. |

No new CRITICAL.

## Regression section

- Gate re-diff (whitespace-normalised, script `scratchpad/gd2.py`): T1..T10 Success identical, Failure identical, 20/20. T11 has no original gates; tasks.md:154-155 labelled `(derived ...)`, honest.
- CRITICAL check (any T1-T10 Success/Failure altered or weakened): NONE.
- Added constraints judged: T1 "Verification constraint" (tasks.md:14) TIGHTENS (adds RED on printing). T8 "Verification constraint" (tasks.md:99) TIGHTENS (adds RED on `--apply`), but is internally contradictory, see C2-13. T3 "Gate-vacuity guard" (tasks.md:133) TIGHTENS (extends the check to any non-vendored kind, "both forms must hold"; does not weaken the verbatim lines). Watch item N-2 (T2 latitude) is a potential loosening by interpretation, not by text.
- FR->task coverage intact: plan.md:76-91 maps FR-001..013 to T1..T11 unchanged; no orphan.
- New contradictions introduced or left: plan.md:129/tasks.md:181 G9 vs plan.md:32; "third source kind" (spec.md:143, tasks.md:28) vs 3-kind table; plan.md:95 vs tasks.md:58; tasks.md:99 self-contradiction.
- D7 check (task 4): recorded, unanswered, in spec.md:193 (row says "No default offered", no OPEN token but no answer), plan.md:116 ("OPEN"), tasks.md:168 ("OPEN"). T4 and T5 carry "Blocked ... D7" (tasks.md:59,74). Not marked blocked in plan G-B or checklist (N-4).

## Checklist review (requirements.md)

- Coverage: every task has items: T1 001-003, T2 004-010, T4 011-015, T5 016-020, T6 021-024, T7 025-029, T8 030-037, T9 038-044, T3 045-048, T10 049-055, T11 056-060. Pass.
- IDs: CHK001..CHK068 unique and continuous (68 distinct; only "duplicates" are in-text ranges at :125). Pass.
- Mechanically checkable: many items yes; defects listed at N-1, N-5, N-6, N-7.
- Presumes D1-D7 answers: CHK005 (D5), CHK012/016-020 (D7 granted; not conditional), :127-128 defaults phrased "Default". D1 items are properly conditional (CHK045-047), D6 (CHK058-059) conditional. D7 absent from checklist decisions.
- Gaps: no item for T1 non-printing verification, T3 non-vacuous guard, T8 `--apply` RED, T4 exit semantics, T4 report-direction.

## Out of scope / assumptions

- Did not run pytest; "11 collection errors" (spec.md:26) still unverified.
- Did not read keys.py, .env, ~/.codex, ~/.claude.json. Only ran the grep pattern on synthetic input.
- Assumed cycle-1 line numbers shifted; cited current lines.
- Assumption unchanged: constitution status proposed, so violations are WARN.

STILL-OPEN counts (excluding RESOLVED and NOT-ATTEMPTED-by-design): CRITICAL 0; HIGH 2 (N-1, N-5) plus cycle-1 HIGH F3 still PARTIAL (C2-03) = 3.

VERDICT: 0 CRITICAL, 3 HIGH, 9 MEDIUM, 4 LOW
