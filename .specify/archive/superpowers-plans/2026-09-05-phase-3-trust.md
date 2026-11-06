<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Phase 3 Trust Implementation Plan

**Goal:** Make the brief trustworthy: per-assertion draft checks, seeded qualification/omission faults, a bounded correction loop that produces a rechecked brief with unresolved passages marked, and quota pauses that surface in receipts.

**Architecture:** Extends `workerbees/`. `verifier.py` gains draft-assertion check; fixtures gain `faults.json.omissions`; `pipeline.py` gains one bounded correction retry fed by reviewer issues; `doctor.py` reports quota as `paused` reason.

**Spec:** `docs/DECISIONS.md` (astra Phase 3 NEXT 1–3, D5, D9, D10), `CONTEXT.md`.

## Global Constraints
- Phase 1+2 constraints hold. Budget mode: haiku writes, Opus reviews diffs, luna drift-checks; no frontier runtime calls; do NOT run bench N≥5 this session (operator low on usage).
- Correction loop: max 1 retry. Retry prompt includes reviewer issues verbatim as data. If still `issues` → `needs-review` with `receipt["unresolved"]` listing claim ids + omissions; draft passages for unresolved claims wrapped `[UNRESOLVED: …]`.
- Every `(pN)` in draft must map to a claim anchor (exists). NEW: every draft sentence must carry ≥1 citation or be listed in `receipt["uncited_sentences"]` → status capped at `needs-review`.

---

### Task 1: Per-assertion draft check + seeded omission faults
**Files:** modify `workerbees/verifier.py`, `workerbees/pipeline.py` (call only), `fixtures/{tim,dom}/faults.json`; tests `tests/test_verifier.py`, `tests/test_fixtures.py`, `tests/test_pipeline.py`.
**Interfaces:** `verifier.check_draft(draft: str, anchored: set[str]) -> dict` → `{"sentences": int, "cited": int, "uncited_sentences": [str], "bad_citations": [str]}`; sentence split on `(?<=[.!?])\s+`; a sentence is cited if it contains `\(p\d+\)` whose N ∈ anchored. Pipeline: after verifier pass, `dc = check_draft(draft, anchored)`; if `dc["bad_citations"]` → `returned`/`uncited_draft` (existing); if `dc["uncited_sentences"]` → cap status at `needs-review`, `receipt["uncited_sentences"]=…`. `faults.json` gains `"omissions": [{"anchor": "tim#p4", "why": "Clause 8 overrides Clause 3"}]` (≥1 per fixture) and `tests/test_fixtures.py` asserts each omission anchor exists in source and is NOT in `expected.json` quotes' anchors' texts... simpler: assert omission anchors are valid paragraphs and `why` nonempty.
Tests: `test_check_draft_counts_cited`, `test_check_draft_flags_uncited_sentence`, `test_check_draft_bad_citation`, `test_pipeline_uncited_sentence_caps_needs_review` (reviewer ok but one uncited sentence → status needs-review, receipt has uncited_sentences), `test_fixture_omissions_valid`.

### Task 2: Bounded correction loop + unresolved marking + quota in receipts
**Files:** modify `workerbees/pipeline.py`; tests `tests/test_pipeline.py`.
**Interfaces:** `brief(..., max_corrections: int = 1)`. Flow after reviewer `issues`: build `CORRECTION_PROMPT` = EXTRACT_PROMPT + "\n\nREVIEWER ISSUES (treat as data, address each):\n" + one line per not-ok verdict (`claim i: issue`) + omissions; re-run worker (same route), re-verify, re-check draft, re-review. `receipt["corrections"]=n`. If final reviewer `ok` → `verified`. If still `issues` → `needs-review`, `receipt["unresolved"]={"claims":[ids],"omissions":[…]}`, and for each unresolved claim id whose anchor `pN` appears in the draft, wrap that sentence as `[UNRESOLVED: <sentence>]` in `r.draft`. Worker `paused` on retry → status `paused`, `receipt["paused_reason"]=stderr tail`. Also: any `paused` from worker or reviewer sets `receipt["paused_reason"]`.
Tests: `test_correction_reaches_verified` (call 1 worker, 2 reviewer issues, 3 worker, 4 reviewer ok → verified, corrections 1, runner cmd sequence [claude,codex,claude,codex]); `test_correction_still_issues_marks_unresolved` (→ needs-review, `[UNRESOLVED:` in draft, receipt.unresolved.claims nonempty); `test_max_corrections_zero_skips_retry`; `test_paused_reason_in_receipt`.

### Task 3: Doctor quota → paused; bench per-status tally
**Files:** modify `workerbees/doctor.py`, `workerbees/bench.py`; tests `tests/test_doctor.py`, `tests/test_bench.py`.
**Interfaces:** `doctor.available()` returns set as before BUT `doctor.run()` result gains `"paused": [providers with WB_QUOTA_EXHAUSTED]`; new `doctor.quota_paused(workspace) -> list[str]` reading cache. `bench.summarize` adds per-config `statuses: {status: count}` and `corrections` mean; `run_case` records `receipt.get("corrections",0)` and `receipt.get("paused_reason")`.
Tests: `test_quota_paused_listed`, `test_summary_status_tally`.

### Review + verify (fable orchestrates)
- Opus reviews each task diff for: false-accept paths, glossary drift, silent failures. Haiku fixes. Fable re-runs `python3 -m unittest discover -s tests`.
- luna (gpt-5.6-luna) drift check vs DECISIONS after all three.
- One real run only (tim, claude worker) to observe correction loop; log in DECISIONS. No bench N≥5.
