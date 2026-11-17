<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Bindle Sibling Integration

**Feature Branch**: `006-bindle-sibling-integration`
**Created**: 2026-09-06
**Status**: Backend A implemented (D37, 2026-09-07) — `workerbees/artifacts.py`, capture points C1/C2/C3 wired. Default flipped `off` -> `local` (D38, 2026-09-07, operator ruling — see S5.4/S7). Backend B (real Bindle CLI/server) remains design-only per S6.
**Input**: Operator override of 005 (2026-09-06): "i think bindle does it better almost certainly. i think this repo works in conjunction w bindle functionality like they will be siblings." Design the sibling split, do not re-litigate adoption.
**Supersedes-in-part**: `specs/005-bindle-integration/spec.md` (its no-duplicate-authority reasoning is retained; its "do not integrate" verdict is not).

## 1. Identity resolution (task 1 — replaces 005's UNRESOLVED)

Bindle = **deislabs/Fermyon Bindle**, an aggregate object storage system. Confidence **high (~85%)** on the technology, with one flagged assumption below.

Verified capabilities (from upstream spec docs):

- **bindle** = named, SemVer-versioned container enumerating its contents.
- **invoice** (`invoice.toml`) = manifest: name, version, description, parcel list.
- **parcel** = opaque blob + `label` metadata, addressed by **sha256** of its content.
- Content-addressing gives **dedup** and **delta transfer**: a server holding a parcel sha256 needs no re-upload; only changed parcels move.
- **conditional groups / features** = optional or alternative parcel sets in one invoice.
- **signing spec** = cryptographic signing + verification of invoices (creator/approver/host roles).
- **transport/server protocol** = push/pull registry over HTTP; CLI client.

Sources: `github.com/deislabs/bindle` `docs/bindle-spec.md`, `invoice-spec.md`, `label-spec.md`, `signing-spec.md`; `deislabs.io/posts/introducing-bindle/`; `docs.rs/bindle`.

**Flagged assumption.** 005 correctly noted the repo's own PLAN-MVP attributes a "git/branch/Obsidian bridge" to `bindle` — deislabs Bindle has **no such bridge**. Two readings: (a) PLAN-MVP's inventory conflated Bindle with a local/personal tool of the same name; (b) the bridge was an operator's own wrapper around Bindle. No `domattioli/bindle` or `riponcm/bindle` repo was found (404). This spec **assumes reading (a)**: `bindle` = deislabs/Fermyon Bindle, and the git/Obsidian bridge is out of scope regardless — it is unrelated to the sibling split designed here. If a private `bindle` repo exists, re-check §3 against it before implementation; nothing below depends on the bridge.

**Upstream health risk (not a blocker, but real).** `deislabs/bindle` was **archived 2025-02-11**, and Fermyon moved to OCI distribution. The format spec is frozen and stable — which is fine for a local sibling store — but there is no upstream maintenance. See §7 FR-009.

## 2. What the ledger already owns (verified by reading code)

Read: `workerbees/ledger.py` (697 lines), `workerbees/store.py`, `workerbees/schema.py`, `docs/governance/SCHEMA-3NF.md`, `workerbees/control.py`, `docs/PLAN-MVP.md` §3.

The ledger is an **append-only dispatch graph**, not a store of things:

- **Nodes** = dispatched jobs (`id, run_id, model, tier, task, provider, parent_id, edge_type, status, seconds, subscription_calls, gate_reason, timestamp`).
- **Edges / lineage** = `reviews | corrects | probes | depends-on`, plus authenticated spawn lineage in the 3NF schema.
- **Idempotency + dedup** = dedup on node id at read; sqlite inserts swallow `IntegrityError`.
- **Dual store** = JSONL (`.workerbees/ledger.jsonl`) + normalized 3NF SQLite, selected by `WORKERBEES_STORE`.
- **Lint** = `depth`, `same_vendor_review`, `frontier_without_gate`.
- **Export / rollup** = JSON round-trip, Mermaid graph, cost rollup per root node.
- **Control plane** = leases, replay keys, approvals (`workerbees/control.py`).
- **Failure posture** = FR-008, ledger failure never fails a brief.

## 3. What the ledger does NOT own — the actual gap

The ledger **already references content but never stores it.**

- `record_dispatch(..., artifact_hash, artifact_size)` writes a sha256 into the ledger row.
- `store.ensure_artifact(sha256, size_bytes)`; SCHEMA-3NF: `artifact K: sha256. FDs: sha256->size_bytes.`
- `node_artifact(node_id, sha256, role)`, `edge_artifact(..., sha256, role)`, `envelope_artifact(envelope_hash, ordinal, sha256, kind)`.
- `pipeline.py:232` hashes the draft — `hashlib.sha256(draft.encode())` — and records the hash. **The draft bytes go nowhere.**

So the repo has a **dangling content-address graph**: every artifact edge names a sha256 whose bytes cannot be retrieved. Concrete consequences, all present today:

1. A review edge cites the exact reviewed content by hash, but the content is unrecoverable — SCHEMA-3NF itself says "Unknown old artifact binding stays absent, cannot satisfy strict review gate."
2. Cost rollups and lint findings survive a run; **deliverables do not**.
3. Nothing distributes a run's outputs off this machine.
4. No versioned grouping: "run N's deliverables" is not a nameable, fetchable unit.

That gap is exactly Bindle's product surface. The operator's "does it better almost certainly" reads as correct here: writing a content-addressed blob store, a manifest format, signing, and a transfer protocol from scratch is a real project; Bindle is that project, specified and frozen.

## 4. Sibling architecture — the split

**One rule governs the seam: the ledger is the authority on *what happened*; Bindle is the authority on *what was produced*. The sha256 is the only join key. Neither system re-states the other's facts.**

| Concern | Owner | Note |
|---|---|---|
| Job identity, status, lineage, edges | **ledger** | unchanged |
| Leases, replay keys, approvals | **ledger** (`control.py`) | unchanged |
| Lint, cost rollup, Mermaid export | **ledger** | unchanged |
| Semantic memory | **projectmem** | unchanged, per PLAN-MVP |
| Artifact **bytes**, content-addressed | **bindle** (parcel) | ledger keeps the sha256 ref only |
| Deliverable **grouping + version** per run | **bindle** (invoice) | one bindle per run/family |
| Artifact **metadata** (media type, name, origin) | **bindle** (label) | ledger stores no label fields |
| **Distribution** off-machine | **bindle** (server/transport) | ledger never gains a network path |
| **Signing** of a run's deliverables | **bindle** (signing spec) | ledger has no crypto |

Directionality: **ledger → bindle is write-and-reference; bindle → ledger is nothing.** Bindle never learns about jobs, tiers, vendors, or approvals. This is what makes them siblings rather than one swallowing the other, and it satisfies 005's retained no-duplicate-authority rule — the sha256 is a *reference*, not a duplicated fact.

### Where the sibling framing is honest — and where it isn't

Clean fits:

- **Parcel ↔ artifact.** Both are sha256-addressed opaque blobs. One-to-one, no impedance. Strongest part of the design.
- **Invoice ↔ run/family deliverable set.** `run_id` maps to a bindle name, run completion to a SemVer version. Conditional groups can separate `draft` / `review` / `corrected` roles.
- **Dedup.** Re-dispatch producing byte-identical output writes one parcel. Matches the ledger's existing idempotency posture.

Imperfect fits — stated, not papered over:

- **Immutability vs. append-only.** A published bindle version is immutable; the ledger appends corrections continuously. A long run cannot publish incrementally under one version. Resolution: publish **once at run close** (a terminal event), and treat mid-run artifacts as local parcels not yet in any invoice. This means Bindle is **not** a crash-durability mechanism mid-run — the ledger keeps that job.
- **SemVer.** Bindle mandates SemVer; runs have no semantic version. Forcing `0.0.<n>` is a convention, not a meaning. Acceptable, but it is a shim.
- **Signing.** Bindle's roles (creator/approver/host) do not map onto the ledger's `approval` table. Do **not** try to unify them — `approval` stays a ledger fact; Bindle signing, if used at all, is a separate transport-integrity concern. **Deferred entirely.**
- **The ledger's own JSONL/SQLite.** These are *not* candidates to move into Bindle. They are mutable, queried, and lint-scanned. Any proposal to store the ledger as a parcel re-creates the duplicate authority 005 warned about. Explicitly rejected.
- **Bindle server.** Running a registry daemon is not sibling-shaped for a single-machine MVP; local standalone bindles suffice. Deferred (§6).

## 5. MVP integration point (revised 2026-09-06 after sol review)

**Superseded design.** The original §5 named `pipeline.py:232` as "the single seam". That is false and was verified false: `pipeline.py:232` is inside `if reviewer_route and gov_mode == "off":`, so it never executes under `WORKERBEES_GOVERNANCE=shadow|enforce`. Two other sites hash content independently — `reviewer.py:69-72` (governed review candidate, into a gateway dispatch context) and `gateway.py:306-308` (worker output, into `control.store_artifact`, which writes only a `replay_keys` row — `control.py:238` — and stores no bytes). A single-site edit is a no-op in two of three governance modes.

**Additional defect found during adjudication.** `store.insert_node_artifact` (`store.py:395`) is never called from any runtime path. Only `edge_artifact(..., role="candidate")` is ever written (`ledger.py:206-210`), and only when `artifact_hash and parent_id and edge_type` all hold. Original SC-001 was phrased over `node_artifact` rows that no run has ever produced. Produced-output binding is a missing feature, not merely an unstored blob.

### 5.1 Capture points — semantic, not syntactic

Artifact capture is defined at **three semantic boundaries**, each of which every governance mode passes through:

| # | Boundary | Bytes | Ledger binding | Where it converges |
|---|---|---|---|---|
| C1 | **Worker/correction output produced** | parsed `draft` | `node_artifact(node_id, sha256, "output")` | `brief()` right after `_process_worker_result` returns, for the initial and every correction dispatch — mode-independent, because both `_dispatch_worker` branches return through it |
| C2 | **Review candidate submitted** | the exact `draft` bytes handed to `review()` | `edge_artifact(reviewer_node, parent, "reviews", 0, sha256, "candidate")` | `brief()` **before** the `gov_mode == "off"` branch; the one hash is then passed into both the off-mode `record_dispatch(artifact_hash=…)` and the governed `review(..., artifact_hash=…)` → `reviewer.py` context |
| C3 | **Gateway worker output returned** | `worker_result.output` | unchanged `control.store_artifact` replay row, **plus** `node_artifact(node_id, sha256, "output")` | `gateway.py:304-309`, replacing the bare `hashlib.sha256` with the same capture call |

C2 removes the duplicated hashing at `pipeline.py:232` and `reviewer.py:71` — `reviewer.py` stops computing a hash and accepts one. That is the actual fix to the "single call site" error: the seam moves *up* to the point all modes share, not sideways to a second syntax site.

### 5.2 The store is content-only

`workerbees/artifacts.py`:

```python
@dataclass(frozen=True)
class Capture:
    sha256: str
    size: int
    stored: bool       # bytes are retrievable now
    backend: str       # "local" | "off"

def capture(workspace: Path, data: bytes, *, media_type: str = "text/markdown") -> Capture: ...
def get(workspace: Path, sha256: str, *, verify: bool = True) -> bytes | None: ...
```

**No occurrence metadata is written to disk.** No `run_id`, `node_id`, or `role` in any sidecar. Those are ledger-owned facts and the ledger already models them (`node_artifact`, `edge_artifact`, `envelope_artifact`); writing them beside a content-addressed blob makes two runs producing identical bytes race to overwrite each other's provenance, and duplicates the authority FR-001 reserves for the ledger.

On-disk layout (internal CAS, **not** claimed to be a standalone Bindle):

```
.workerbees/cas/<sha256[:2]>/<sha256>          # bytes, mode 0600, dir 0700
.workerbees/cas/<sha256[:2]>/<sha256>.meta.json # {"sha256","size","mediaType"} — content facts only
```

Backend B's assembler later reads occurrence metadata **from the ledger** (`node_artifact` / `edge_artifact` joined to `node`/`run`) and content facts from the CAS to emit `invoice.toml` + parcel payloads in whatever layout the pinned Bindle release demands. That mapping is unwritten and unvalidated; see FR-011.

### 5.3 Failure posture and the availability contract

`capture()` returns `stored=False` on any write failure or when the backend is `off`. It never raises. The caller passes `sha256` to the ledger regardless (FR-007 preserved) and surfaces `stored` into the brief receipt as `receipt["artifacts"] = {"stored": n, "unstored": m, "backend": …}`. Recording a hash is therefore never a claim of retrievability; retrievability is asserted only by a successful verified `get`.

### 5.4 Default is `local` (D38, 2026-09-07 — supersedes this section's original default-off)

`WORKERBEES_ARTIFACTS` ∈ `off` | `local` (**default**) | `bindle` (not implemented). Operator ruling 2026-09-07 (D38) resolved §7's NEEDS-OPERATOR: manual purge script (no auto-GC), no encryption at rest, no backup exclusion. `workerbees/artifacts.py`'s `purge(workspace, older_than_days, dry_run=False)` / `python3 -m workerbees.artifacts --older-than-days N` is the operator-run cleanup path — nothing calls it automatically. Confidential draft bytes now persist as plaintext at `.workerbees/cas/` (mode 0600/0700) on any brief unless `WORKERBEES_ARTIFACTS=off` is set explicitly.

## 6. Deferred

- Bindle **server / registry daemon** and off-machine distribution.
- **Signing** and the creator/approver/host role model.
- **Conditional groups / features** for role-partitioned deliverables.
- Any **git/branch/Obsidian bridge** (out of scope in 005; still out of scope).
- Migrating any ledger table into Bindle — **rejected**, not merely deferred.
- **`finish_run(run_id, outcome)`** — deferred but now a stated **prerequisite for Backend B**. `run.outcome` is inserted nullable (`store.py:143-148`) and never updated; `record_return` closes a node, not a run; `brief()` has ~8 early returns and no single exit. No immutable invoice can be published correctly until a run has an idempotent terminal event. Backend B is blocked on this, not merely deferred.

## 7. Blockers and constraints

- **`bindle` CLI is not installed** (`which bindle` → not found). This is a **need-to-install item, not a hard blocker**: MVP Backend A is pure stdlib and requires nothing. Only Backend B needs the CLI.
- **Real risk, not a blocker: upstream is archived** (deislabs/bindle, 2025-02-11; Fermyon moved to OCI). Mitigation is the two-backend design — the repo depends on the *format*, which is frozen and specified, not on a maintained binary. If Bindle ever needs replacing, Backend A's CAS is untouched and only the assembly step changes (OCI is the natural successor).
- **Confidential plaintext persistence — RESOLVED (D38, 2026-09-07).** `brief(confidential=True)` is the default and drafts are classified `confidential` at `pipeline.py:174`; capture now persists those bytes as plaintext by default. Operator ruling: (a) retention/GC = manual purge script, no auto-GC (`workerbees/artifacts.py:purge`); (b) unencrypted persistence = accepted for MVP (0600/0700 perms, single-operator machine); (c) backup scope = no special handling, inherits whatever backs up the repo.
- **No hard technical blocker remains.** §5.1's capture points are wired; the operator ruling above closed the last gate. Backend B (`finish_run`, validated invoice mapping) remains a separate, still-deferred prerequisite (§6).

## 8. Requirements

- **FR-001**: The ledger remains the sole authority on job identity, status, lineage, leases, approvals, lint, and cost. The artifact store holds bytes and content facts only — never `run_id`, `node_id`, or `role`.
- **FR-002**: Artifact bytes are addressed by sha256 only; the ledger stores the hash, never the content.
- **FR-003**: `artifact(sha256, size_bytes)` and all `*_artifact` tables are unchanged by this feature. No column, table, or `SCHEMA_VERSION` bump. Storage availability is store state, not a functional dependency of sha256, and gets no DDL.
- **FR-004**: `workerbees/artifacts.py` provides `capture`/`get` with a stdlib-only default backend and returns a typed `Capture(sha256, size, stored, backend)`.
- **FR-005**: The `local` backend requires no `bindle` install and no network.
- **FR-006**: Capture happens at the three semantic boundaries of §5.1 (C1, C2, C3) and is exercised identically under `WORKERBEES_GOVERNANCE=off|shadow|enforce`. No governance mode may bypass capture.
- **FR-007**: Store failure or `off` degrades to hash-only recording and never fails a brief (inherits FR-008 of 002). Configuration validation happens at the CLI/config boundary before work begins; `capture`/`get` never propagate configuration or I/O errors into `brief()`.
- **FR-008**: Recording an artifact hash is not a claim of retrievability. `Capture.stored` is the only in-band availability signal, and it is surfaced in the brief receipt.
- **FR-009**: `get` accepts only lowercase 64-hex keys, resolves and asserts path containment under the CAS root, and verifies the sha256 of the returned bytes before returning them (`verify=True` default). Digest mismatch returns `None` and quarantines the blob. Dedup no-op requires a size match, not mere path existence.
- **FR-010**: Produced worker/correction output is bound with `node_artifact(node_id, sha256, "output")` via a new never-raising `ledger.record_output(...)`. `store.insert_node_artifact` is currently dead code; this feature is what first calls it.
- **FR-011**: The local layout is an **internal CAS**, not a standalone Bindle. No claim of on-disk Bindle compatibility or zero-migration is made until a golden `invoice.toml` produced by the assembler is validated against a pinned Bindle parser. Only the *bytes* are asserted migration-free; metadata requires assembly.
- **FR-012**: Upstream Bindle is archived; the repo depends on the frozen format, never on upstream maintenance.
- **FR-013**: Blobs are written via `tempfile.NamedTemporaryFile(dir=<shard dir>, delete=False)` with a unique name, flushed and `fsync`ed, then published with `os.replace`. Metadata is published after bytes. A crash between the two leaves a valid blob and a recoverable missing-meta state; `get` tolerates missing meta. CAS files are mode `0600`, directories `0700`.

## 9. Success criteria

- **SC-001**: With `WORKERBEES_ARTIFACTS=local`, a completed brief writes at least one `node_artifact` row whose sha256 resolves through `get` to the exact produced bytes — under each of `WORKERBEES_GOVERNANCE=off`, `shadow`, and `enforce`. (Today zero `node_artifact` rows are written by any path.)
- **SC-002**: A review edge citing an artifact hash re-verifies against the original content **when `Capture.stored` was true for that hash**. With `off` or a failed write, the criterion is explicitly not claimed and the receipt says so.
- **SC-003**: Two runs producing identical output store one blob; the second write is a verified no-op (size + digest match), not a bare path-exists check.
- **SC-004**: All existing ledger/store/schema tests pass unchanged; `SCHEMA_VERSION` unchanged.
- **SC-005**: A mode matrix passes: {off, shadow, enforce} x {review enabled, review disabled} x {clean, corrections exhausted, blocked/early return} — each asserting no dangling hash is recorded as stored, and that governed modes capture the same bytes as `off`.
- **SC-006**: Security tests pass: `../` traversal key rejected, uppercase/non-hex key rejected, truncated blob returns `None`, tampered blob returns `None` and quarantines, two concurrent writers of the same hash both succeed with one intact blob.
- **SC-007**: A future maintainer reads §4 and §5.2 and can say, for any fact, which sibling owns it — and can see that no occurrence metadata lives in the CAS.
