<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# 007 — Requirements checklist

Machine doc. Caveman ultra. Check only w/ evidence (file:line, command output). P3: self-grade is not evidence.

## Authority

- [x] CH001 P10 grants delete-prose authority to Supervisor AND requires citing the enforcing test + its green result. Both halves present, not just the first. Evidence: `.specify/memory/constitution.md:59` "Supervisor MAY delete a prose rule once a landed test enforces the same rule, and MUST cite that specific test plus its green result when doing so — authority without the evidence cite does not satisfy this clause."
- [x] CH002 Constitution version 1.5.0 → 1.6.0, `last_amended` updated, **authorizing `docs/DECISIONS.md` D-number cited** (`constitution.md:67` mandates it), Enforcement still reads P0-P10. Evidence: `.specify/memory/constitution.md:3` `version: 1.6.0`, `:6` `last_amended: 2026-09-06`, `:63` "P0–P10 report as WARN". D-number cite: P8→D29, P9→D30, P10 (lesson-routing half)→D31, all at lines 51/55/59; caveat — D31's actual text (`docs/DECISIONS.md:289-294`) does not mention the delete-on-test-coverage clause, flagged in-line rather than fabricated (see report).

## Enforcement precedes pruning

- [ ] CH003 Every rule deleted in phase 2 has EITHER a landed green test enforcing it OR a verified surviving single owner. No rule deleted on the grounds that it "felt redundant".
- [ ] CH004 Each new test proven to actually fail when its violation is introduced (a test that cannot fail is worse than none).

## No semantic loss

- [x] CH005 `grep -F` returns a hit for every copy-me literal after every edit: the verbatim training-notice line, `SECOND-OPINION JUSTIFICATION: not applicable`, `PLAN CONTRACT: not applicable — deliverable is not a plan`, `effort control unavailable on this transport`, both effort-level lists. Evidence: all 6 `grep -Fn` hits shown in T012 report, `skills/workerbee/SKILL.md` lines 394/431/417/438/412/166.
- [x] CH006 No copy-me literal split across a line break. Evidence: PLAN CONTRACT literal now on one line, `skills/workerbee/SKILL.md:438` (was split at old 465/466). SECOND-OPINION literal checked — the em-dash+reason after it varies per dispatch by design, not a broken copy-me string.
- [ ] CH007 not evidenced this pass — `CLAUDE.md` untouched by T001/T008/T012 (out of my 3-file write scope), left unticked pending owning task's own verify.
- [x] CH008 Element count reads 14 in all three canon locations; zero stale counts ("twelve"/"13-element"/etc) anywhere. Evidence: `grep -rn "twelve\|thirteen\|12-element\|13-element\|fourteen elements" CLAUDE.md skills/workerbee/SKILL.md .specify/memory/constitution.md` → one hit, `skills/workerbee/SKILL.md:467` "the other twelve unconditional" — this is a correct count of the 12-of-14 unconditional elements (14 minus 2 conditional = 12), not a stale total-element count. No "14"-contradicting count found.

## Scope + hygiene

- [ ] CH009 Zero new third-party dependencies. `workerbees/*.json` hardening uses stdlib `dataclasses` only.
- [ ] CH010 New files limited to: dedup test, checker script + test, schema module + test, `step11_compressed.md` (landed in-repo). No others. Owner: T012.
- [x] CH011 Edits surgical, not whole-file rewrites, wherever a targeted edit gives the identical result (P9). Owner: T012. Evidence: constitution.md — 4 targeted string replaces (version bump, 3 D-number cites), no rewrite. SKILL.md — Step 11 body block-replaced (lines 373-496, that block's content genuinely changes almost entirely per the compression task) + one 2-line insert for the checker reference; Step 12+ untouched. Checklist — targeted line replaces only.
- [ ] CH012 Python package `workerbees/` and `python3 -m workerbees.pipeline` entrypoint unchanged by the skill rename.

## Suite

- [x] CH013 `python3 -m unittest discover -s tests` reports `OK`, count ≥ 425 baseline, quoted VERBATIM **before and after** (before-capture is in `tasks.md` header). Read the `Ran N tests`/`OK` summary — NOT a test's stdout print. Evidence: before = `tasks.md:8` "Ran 425 tests" / OK. After (this session, post T001+T008 edits): "Ran 440 tests" / "OK" — verbatim command output in T012 report.
- [ ] CH014 N/A this feature — no 007 task touches a `.sh`. Re-activate if that changes.

## Cross-repo

- [ ] CH015 DomI: exactly one PR into `development`; zero consumer-repo files touched; no `--force`, no admin-merge, no bypassed CI.
- [ ] CH016 DomI cited defects re-verified at execution time before editing (paths/line numbers drift). Owner: T011 PASS gate.

## Contract compliance

- [ ] CH017 Every dispatch prompt issued for this feature carries all 14 elements (content or explicit N/A for 10/11 only). Owner: T012, verified w/ T003's checker.
- [ ] CH018 Every delegate claim independently re-verified by run root before relay to operator (P3). Owner: T012.
