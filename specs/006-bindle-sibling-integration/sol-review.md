<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# SOL Adversarial Review: Bindle Sibling Integration

Date: 2026-09-06. Scope: review only. Identity accepted; not re-litigated.

## Verdict

**REJECT.** Gap is real. Split is directionally sound. MVP does not close it across runtime modes, cannot meet its retrieval criteria under its own failure contract, and confuses content metadata with occurrence metadata.

Counts: **3 blocker / 5 major / 1 minor**.

## Verified baseline

- Byte gap confirmed. `workerbees/store.py:76-82` inserts only `(sha256,size_bytes)`. `workerbees/ledger.py:206-210` creates only the artifact row and edge binding. No parcel/blob writer exists.
- Review-candidate hash confirmed at `workerbees/pipeline.py:229-233`; governed equivalent is separate at `workerbees/reviewer.py:69-72`. Therefore “single call site” is false.
- Schema meaning confirmed. `docs/governance/SCHEMA-3NF.md:9,27,69,99` makes size content metadata; kind/role occurrence metadata. The current DDL needs no backend column. A blob may exist locally, remotely, both, or neither over time; backend is storage state, not a stable FD of sha256.
- Missing historical bindings remain unable to satisfy strict review (`docs/governance/SCHEMA-3NF.md:5`). CAS fixes future retrievability only; it cannot reconstruct old bytes.

## Findings

### B1 — Planned seam misses governed execution and produced outputs

- Evidence: `spec.md:98-103`; `plan.md:9,35`; `pipeline.py:229-233`; `reviewer.py:69-72`; `gateway.py:304-309`.
- Failure: with `WORKERBEES_GOVERNANCE=shadow|enforce`, the edited `pipeline.py:232` path is not used. `reviewer.py` still hashes only. Gateway also hashes returned worker output into replay metadata without storing bytes. Runs with review disabled, early return, or a final unreviewed correction retain dangling output hashes. No runtime path writes `node_artifact`, yet SC-001 is stated in terms of it (`spec.md:136`).
- Severity: **blocker**.
- Fix: define artifact capture at semantic boundaries, not one syntax site. Store each candidate before either direct or gateway review; pass one returned hash through both paths. Store non-empty worker/reviewer outputs in gateway/direct paths. Bind produced outputs with `node_artifact`; bind reviewed bytes with `edge_artifact`. Add mode-matrix tests: off/shadow/enforce, review disabled, correction exhausted, blocked/early return.

### B2 — One label per hash violates occurrence semantics and races

- Evidence: `plan.md:16-17,29,33`; `spec.md:74,86`; `SCHEMA-3NF.md:9,69,99`.
- Failure: identical bytes in run A/node A and run B/node B dedup to one blob and one `<sha>.label.toml`, but labels carry `run_id`, `node_id`, and `role`. Last writer wins; concurrent writers nondeterministically erase the other occurrence. Even sequential dedup cannot represent both. This duplicates ledger-owned dispatch facts in Bindle, contradicting FR-001 and the stated authority split.
- Severity: **blocker**.
- Fix: keep CAS entries content-only. Put `run_id/node_id/role/name/media-type` in per-run invoice occurrence records assembled from ledger bindings plus a run-scoped staging manifest. Never key occurrence metadata solely by sha256. Make concurrent writes use unique temp files and no-clobber/verified dedup.

### B3 — Retrieval criteria contradict `off` and fail-open writes

- Evidence: `spec.md:104,130,136-138`; `plan.md:24,33-37`; `ledger.py:206-210`.
- Failure: unwritable disk or `WORKERBEES_ARTIFACTS=off` returns a hash and records an artifact edge, while `get(hash)` returns `None`. SC-001 and SC-002 then fail by design. SQLite presence cannot prove resolvability.
- Severity: **blocker**.
- Fix: return a typed result `(sha256, stored)`; preserve hash-only recording for FR-007, but make strict-review success require `stored` plus verified `get`. Rewrite SC-001/002 as conditional guarantees, or disallow `off`/write failure for strict gates. No ledger schema bump is required; availability belongs to the artifact-store health/index layer.

### M1 — “Run close” has no event or trigger

- Evidence: `spec.md:90,102,131`; `plan.md:40-44`; `pipeline.py:191-300`; `ledger.py:225-300`; `store.py:143-148`.
- Failure: `brief()` has many early returns and no close/finalize call. `record_return()` closes a node, not a run. `run.outcome` is inserted nullable and never updated. Backend B cannot know when the immutable invoice is complete; publishing on the last observed node races later corrections.
- Severity: **major**.
- Fix: specify one idempotent `finish_run(run_id, outcome)` invoked from a `finally`/single-exit coordinator after all children settle. Persist close state before publish. Publish from a retryable outbox keyed by `(run_id, invoice_digest)`; never infer close from node returns or lease release.

### M2 — Sidecars are not Bindle-compatible storage

- Evidence: `spec.md:101,106,129`; `plan.md:13-18,29,42`; upstream Bindle README says labels are invoice manifest data and parcel payload is `parcel.dat`.
- Failure: a sharded raw blob plus standalone `.label.toml` is an internal CAS convention, not a standalone Bindle accepted by its CLI/server. Backend B must transform sidecars into invoice parcel labels, choose bindle name/version, and feed parcel bytes through Bindle transport/layout. “Same parcels assembled” is plausible; “Bindle-format-compatible on disk” and “no data migration” are unproven.
- Severity: **major**.
- Fix: call Backend A an internal CAS. Specify an assembler mapping and canonical TOML shape. Add a golden invoice and validate it with the pinned Bindle parser/CLI before claiming compatibility. State that bytes need no rewrite; metadata requires assembly/transformation.

### M3 — `get` lacks required trust boundary

- Evidence: `plan.md:25,33,37`; `spec.md:136-137`.
- Failure: no hash grammar or read-time digest check is required. A malformed `../../...` key can escape the shard path in a naive implementation; a corrupted/replaced blob can be returned as “exact bytes.” Existing-blob no-op also preserves corruption.
- Severity: **major**.
- Fix: accept only lowercase 64-hex keys; resolve and assert containment; verify SHA-256 on every strict-gate read; verify size/hash before dedup no-op; quarantine mismatch. Test traversal, uppercase/nonhex, truncation, and tampering.

### M4 — Invalid backend mode can fail a brief

- Evidence: `spec.md:104,130`; `plan.md:24,34`; `pipeline.py:229-233`.
- Failure: plan says `put` never raises, then requires invalid env values to raise before its try. Once called inline, `WORKERBEES_ARTIFACTS=locl` aborts the brief, violating FR-007’s “never fails a brief.” Existing ledger precedent does not override the new requirement.
- Severity: **major**.
- Fix: validate at an explicit CLI/config boundary before work begins, or degrade to hash-only with a surfaced warning. Runtime `put/get` must not propagate configuration or I/O errors into `brief()`.

### M5 — Plaintext drafts are a new exposure class

- Evidence: `plan.md:51`; `pipeline.py:174` defaults `confidential=True`; `ledger.py:93-107` stores task label and hash, not draft bytes.
- Failure: the risk statement is factually wrong. Today the ledger task is literal `review`; after MVP, confidential draft content is persisted by default in plaintext. Shared workspace permissions, backup, or stale retention can expose it.
- Severity: **major**.
- Fix: define classification/retention policy before default-on persistence; create directories/files with restrictive modes; document backup scope; add deletion/GC policy; require encryption or explicit opt-in for confidential/restricted artifacts.

### m1 — Atomicity recipe is underspecified

- Evidence: `plan.md:33`.
- Failure: if concurrent writers use the same predictable temp name, one can replace/unlink the other’s temp or observe partial metadata state. Blob atomicity alone also leaves blob-without-label after crash.
- Severity: **minor**.
- Fix: use `tempfile` in the target directory, unique names, flush/fsync, atomic publish, cleanup, and deterministic recovery. Test two processes writing the same hash and injected crash between blob/metadata publication.

## Gate for next adjudication

Require revised spec/plan to close B1-B3, define run finalization, demote local layout from “Bindle-compatible” until parser-tested, and add security/integrity tests. Preserve no-ledger-migration decision and never place ledger bytes inside Bindle.
