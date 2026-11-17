<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Bindle Sibling Integration

**Spec**: `specs/006-bindle-sibling-integration/spec.md`
**Created**: 2026-09-06 · **Revised**: 2026-09-06 after `sol-review.md` (REJECT)
**Scope**: MVP only — internal content-addressed store (`local` backend), default **off**. Backend B (real Bindle invoices) is out of scope and additionally blocked on `finish_run`.

## Design summary

One new module, **three** capture points (not one), one new never-raising ledger writer, zero schema change. The ledger keeps recording sha256; `artifacts.py` makes those hashes resolvable and says honestly when they are not.

## Layout

```
workerbees/artifacts.py                              # new: Capture/capture/get, backend dispatch
tests/test_artifacts.py                              # new: unit, security, concurrency
tests/test_artifact_modes.py                         # new: governance mode matrix
.workerbees/cas/<aa>/<sha256>                        # bytes (runtime, gitignored, 0600)
.workerbees/cas/<aa>/<sha256>.meta.json              # {"sha256","size","mediaType"} content facts only
```

## API

```python
@dataclass(frozen=True)
class Capture:
    sha256: str; size: int; stored: bool; backend: str

def capture(workspace: Path, data: bytes, *, media_type: str = "text/markdown") -> Capture
def get(workspace: Path, sha256: str, *, verify: bool = True) -> bytes | None
def validate_config(env: Mapping[str, str]) -> None   # raises; called at CLI boundary only
```

No `name=` / `role=` / `run_id=` parameters exist. Occurrence metadata cannot enter the store by construction.

## Steps

1. **`artifacts.py`, `local` backend.** sha256 → shard dir → `tempfile.NamedTemporaryFile(dir=shard, delete=False)`, write, `flush`+`fsync`, `os.replace` for the blob, then the same for `.meta.json`. Existing blob: verify size (and digest when cheap) before treating as a dedup no-op; mismatch → rewrite. Dirs `0700`, files `0600`. Every error swallowed → `Capture(sha, size, stored=False, backend=…)`.
2. **`get` trust boundary.** Reject keys not matching `^[0-9a-f]{64}$` **before** any path join; build the path, `Path.resolve()`, assert it is under the resolved CAS root; read; recompute sha256 when `verify=True`; on mismatch move the blob to `.workerbees/cas/.quarantine/` and return `None`. Missing `.meta.json` is tolerated.
3. **Config validation moved out of the hot path.** `validate_config` raises on a bad `WORKERBEES_ARTIFACTS`; it is called once from the CLI entrypoint / `brief()`'s preamble alongside the existing `WORKERBEES_GOVERNANCE` check — **never** from `capture`. An unrecognised value at runtime degrades to `off` with a receipt warning. (This intentionally departs from the `ledger.py:79` `WORKERBEES_STORE` precedent, which predates FR-007's "never fails a brief".)
4. **`ledger.record_output(workspace, *, node_id, sha256, size, role="output") -> bool`.** New, mirrors `record_dispatch`'s never-raises contract: `store.ensure_artifact` then `store.insert_node_artifact`, swallowing `IntegrityError` (re-dispatch idempotency) and returning False on any error. This is the first runtime caller of `insert_node_artifact`.
5. **C1 — capture produced output.** In `brief()`, immediately after each `_process_worker_result(...)` (initial dispatch and every correction), if `draft` is non-empty: `cap = artifacts.capture(workspace, draft.encode(), media_type="text/markdown")` then `ledger.record_output(workspace, node_id=worker_node_id, sha256=cap.sha256, size=cap.size)`. Mode-independent — both `_dispatch_worker` branches return through this point.
6. **C2 — capture the review candidate once, hash flows to both paths.** Hoist the hash out of `pipeline.py:232` and `reviewer.py:71`. In `brief()`, before the `gov_mode == "off"` branch: `cand = artifacts.capture(workspace, draft.encode())`. Pass `cand.sha256`/`cand.size` into the off-mode `record_dispatch(artifact_hash=…, artifact_size=…)` **and** into `review(..., artifact_hash=cand.sha256, artifact_size=cand.size)`. `reviewer.py` gains those two kwargs and stops calling `hashlib` — it forwards them into the gateway dispatch context it already builds at `reviewer.py:69-72`, so `gateway.py:274`'s existing `record_dispatch(artifact_hash=context.get(...))` is untouched.
7. **C3 — capture gateway worker output.** At `gateway.py:304-309`, replace the inline `hashlib.sha256(worker_result.output.encode())` with `capture(...)`; keep the existing `control.store_artifact(message_id, envelope_hash, cap.sha256)` replay row exactly as-is, and add `ledger.record_output(self.workspace, node_id=node_id, sha256=cap.sha256, size=cap.size)`.
8. **Receipt surface.** `brief()` accumulates `receipt["artifacts"] = {"backend": …, "stored": n, "unstored": m}`. Any `stored=False` is visible to the caller; nothing silently claims retrievability.
9. **Gitignore** `.workerbees/cas/`.
10. **Tests.**
    - round-trip; dedup (one blob, verified); absent hash → `None`.
    - `off` returns the correct sha256, `stored=False`, writes nothing.
    - unwritable workspace: no raise, `stored=False`, brief still succeeds.
    - bad `WORKERBEES_ARTIFACTS` raises from `validate_config`, **not** from `capture`, and never from inside `brief()`'s worker path.
    - security: `../../etc/passwd`, uppercase hex, 63/65-char keys, truncated blob, tampered blob (quarantine asserted).
    - concurrency: two processes `capture` the same bytes simultaneously → one intact blob, both `stored=True`; injected crash between blob and meta publish → `get` still returns bytes.
    - **mode matrix** (`test_artifact_modes.py`): {off, shadow, enforce} x {review on, review off} x {clean, corrections exhausted, blocked} — assert `node_artifact` rows exist and resolve, and that governed modes capture byte-identical content to `off`.
11. **Verify no regression.** Full ledger/store/schema/gateway/reviewer suite; assert `SCHEMA_VERSION` unchanged.

## Explicit non-goals in this plan

- No `bindle` CLI dependency, no `invoice.toml` assembly, no server, no signing. No claim of on-disk Bindle compatibility (spec FR-011).
- No new ledger table, column, or schema version bump. No availability/backend column — availability is store state, not an FD of sha256.
- No `finish_run` implementation (spec §6 records it as a Backend-B prerequisite).
- No retention/GC policy — which is precisely why the default is `off`.

## Risks

| Risk | Mitigation |
|---|---|
| Confidential draft bytes persisted in plaintext | default `off`; `0600`/`0700` modes; flipping the default needs the operator ruling in spec §7 |
| Unbounded CAS growth | default `off` bounds exposure; GC deferred, flag on first observation |
| Capture point drift (a future 4th hash site added, unstored) | mode-matrix test asserts every recorded `artifact_hash` in a run resolves through `get` when backend is `local` |
| Backend B mapping unproven | FR-011 forbids the compatibility claim until a golden invoice validates against a pinned parser |

## Done when

Spec SC-001 through SC-007 hold.

---

## Adjudication — opus, 2026-09-06

Reviewed `sol-review.md` (REJECT; 3 blocker / 5 major / 1 minor) as Orchestrator. B1 and B3 were independently re-verified against source before adjudication; the rest were spot-checked, not rubber-stamped.

**Independent finding not in sol's review:** `store.insert_node_artifact` (`store.py:395`) has **no runtime caller** — `grep` over `workerbees/*.py` shows the only artifact binding ever written is `edge_artifact(..., "candidate")` at `ledger.py:206-210`, and only when `artifact_hash and parent_id and edge_type`. Original SC-001 was written over `node_artifact` rows that no run has ever produced. B1 is therefore worse than stated: produced-output binding is a missing feature, not just unstored bytes.

| ID | Verdict | Reasoning |
|---|---|---|
| **B1** — seam misses governed execution + produced outputs | **ACCEPT** | Verified true. `pipeline.py:232` sits inside `if reviewer_route and gov_mode == "off":`; `shadow`/`enforce` route through `reviewer.py:69-72` → `gateway.py:274`, and worker output through `gateway.py:306-308` → `control.store_artifact` → a `replay_keys` row only (`control.py:238`). The original "single call site" claim was my error and is retracted. **Fix taken differs from sol's in one way:** sol says "store each candidate before either path and pass one hash through both". I adopt that but move the seam *up* rather than duplicating it — the candidate is captured once in `brief()` above the `gov_mode` branch (C2), and `reviewer.py` stops hashing entirely and accepts `artifact_hash`/`artifact_size` kwargs. Produced output is captured at the mode-independent convergence after `_process_worker_result` (C1), gateway output at C3. Spec §5.1, plan steps 5-7; mode matrix in SC-005 / plan step 10. |
| **B2** — one label per hash violates occurrence semantics and races | **MODIFY** | Diagnosis accepted in full: `run_id`/`node_id`/`role` in a sha256-keyed sidecar is last-writer-wins, cannot represent two occurrences of identical bytes, and duplicates ledger-owned facts (contra FR-001). **Rejected sub-fix:** sol's "run-scoped staging manifest" is a new occurrence store, and the ledger already *is* that store — `node_artifact(node_id, sha256, role)` and `edge_artifact(...)` model occurrence exactly. Adding a staging manifest re-creates the duplicate authority 005 warned about. Fix instead: the CAS is content-only **by construction** — `capture()` has no `name`/`role`/`run_id` parameter, and the sidecar holds `{sha256, size, mediaType}` only. Backend B's assembler joins the ledger for occurrence data. Concurrency handled under m1. Spec §5.2, FR-001. |
| **B3** — retrieval criteria contradict `off` and fail-open writes | **ACCEPT** | Verified true: `ledger.py:206-210` calls `ensure_artifact` whenever `artifact_hash` is truthy, with no knowledge of whether bytes landed. A recorded hash was being read as a retrievability claim. Adopted sol's typed result verbatim in spirit: `Capture(sha256, size, stored, backend)`; FR-007 hash-only recording preserved; SC-001/SC-002 rewritten as conditional on `stored`; availability surfaced in the receipt, **not** in the schema (agreed — it is storage state, not an FD of sha256, so no DDL). Spec §5.3, FR-008. |
| **M1** — "run close" has no event or trigger | **MODIFY** | Verified: `run.outcome` is inserted nullable (`store.py:143-148`) and never updated; `record_return` closes a node; `brief()` has ~8 early returns. Sol's `finish_run(run_id, outcome)` + retryable outbox keyed by `(run_id, invoice_digest)` is the right design. **Scope disagreement:** it is a prerequisite for Backend B, and Backend B is not in this MVP — building a finalization protocol and an outbox now would be speculative work for an unbuilt consumer. Recorded in spec §6 as a hard blocker on Backend B rather than implemented. MVP publishes no invoice, so nothing in it races run close. |
| **M2** — sidecars are not Bindle-compatible storage | **ACCEPT** | Sol is right and the original spec overclaimed. Bindle's label is invoice manifest data; a sharded raw blob plus a free-standing `.label.toml` is not a standalone bindle any tool would accept, so "Bindle-format-compatible on disk" and "no data migration" were unsupported. Retracted: the local layout is now named an **internal CAS** (renamed `parcels/` → `cas/`, sidecar → `.meta.json` so the name stops implying the claim). FR-011 forbids the compatibility claim until a golden `invoice.toml` validates against a pinned Bindle parser. Only *bytes* are asserted migration-free. |
| **M3** — `get` lacks a trust boundary | **ACCEPT** | Correct and cheap to fix; there is no reason to ship a content-addressed store whose read path neither validates the key nor checks the digest it is named by. Adopted whole: `^[0-9a-f]{64}$` key grammar, resolve-and-contain, verify-on-read by default, verified dedup rather than path-exists, quarantine on mismatch. FR-009, plan step 2, SC-006. |
| **M4** — invalid backend mode can fail a brief | **ACCEPT** | Verified contradiction in my own plan: step 2 required a raise before the try block while step 1 promised `put` never raises, and the call site is inline in `brief()`. `WORKERBEES_ARTIFACTS=locl` would have aborted a brief in violation of FR-007. The `ledger.py:79` precedent I cited does not license a new violation. Fix: `validate_config` at the CLI/config boundary; unknown value at runtime degrades to `off` with a receipt warning; `capture`/`get` propagate nothing. FR-007, plan step 3. |
| **M5** — plaintext drafts are a new exposure class | **ACCEPT, with an operator gate** | My risk row ("no new exposure class") was factually wrong: `ledger.py:93-107` stores a task *label* and a hash, never draft bytes, while `brief(confidential=True)` is the default and `pipeline.py:174` classifies payloads `confidential`. Default-on capture would newly persist confidential content as plaintext with no retention or GC policy. Partial fix applied now (`0600`/`0700`, default `WORKERBEES_ARTIFACTS=off`, GC named as the reason for default-off). The rest — retention, whether confidential-classified content may be persisted unencrypted at all, backup scope — is a policy call I will not guess. **NEEDS-OPERATOR**, spec §7. |
| **m1** — atomicity recipe underspecified | **ACCEPT** | Correct: a predictable temp name lets concurrent writers clobber each other, and blob-atomicity alone permits blob-without-metadata after a crash. Adopted: `tempfile` in the target shard dir, unique names, `flush`+`fsync`, `os.replace` publish, bytes-before-metadata ordering, `get` tolerates missing metadata. Concurrency and injected-crash tests added. FR-013, plan step 1, SC-006. |

**Tally:** 7 ACCEPT · 2 MODIFY (B2, M1) · 0 REJECT.

### Verdict

**Not approved-as-was; approved-to-build as revised, with one operator gate.**

Sol's REJECT was correct on the merits — B1 alone meant the MVP was a no-op in two of three governance modes, and my "single call site" framing was the root error. The revision is a real redesign of the seam (three semantic capture points replacing one syntax site, plus a new `record_output` binding that makes `node_artifact` live for the first time), not a patch around it.

What remains open, and why it is not a guess:

- **NEEDS-OPERATOR (narrow, one decision):** may confidential-classified draft bytes be persisted to disk unencrypted, and under what retention? The MVP is buildable *today* with `WORKERBEES_ARTIFACTS=off` as the default — every capture point, test, and mode-matrix assertion ships and passes — but flipping the default to `local` (which is what actually closes the §3 gap in practice) waits on that ruling. Shipping default-off is not a stall; it is the honest posture given an unresolved data-classification policy.
- **Backend B stays blocked** on `finish_run` + a parser-validated invoice mapping (M1, M2). Neither is MVP work.

Single biggest design change: **the seam moved from `pipeline.py:232` to three mode-independent semantic boundaries, and the ledger gained `record_output` so produced artifacts are bound at all** — previously no code path in the repo wrote a `node_artifact` row.
