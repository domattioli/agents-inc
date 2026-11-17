<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Dispatch Graph Ledger

**Branch**: `002-dispatch-graph-ledger` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-dispatch-graph-ledger/spec.md`

## Summary

Add a per-workspace, append-only dispatch graph ledger that records every delegated job (worker, reviewer, correction, doctor probe) as a node with model/tier/task/provider/parent/edge-type/status/seconds/subscription-calls, purely as a side effect of `pipeline.brief()` and `doctor.run()`/`probe_cli()` — never LLM-planned. A new `workerbees/ledger.py` (stdlib only, ≤300 lines) owns the JSONL file format, idempotent append, a small deterministic linter (depth, same-vendor-review, frontier-without-gate), JSON/Mermaid export, and cost rollup. `pipeline.py` and `doctor.py` gain thin recording calls at existing decision points; no new authority for job status is created — the runner's own status remains canonical, the ledger keeps its own eventually-consistent copy recorded at dispatch and at return (per spec clarification, D13/FR-009).

## Technical Context

**Language/Version**: Python 3.9+ (stdlib only), matching the rest of `workerbees/`
**Primary Dependencies**: None — `json`, `dataclasses`, `pathlib`, `time`, `uuid` from stdlib only
**Storage**: `<workspace>/.workerbees/ledger.jsonl` — one JSON object per line, append-only, idempotent by node `id`
**Testing**: `pytest` under `tests/`, following `tests/test_pipeline.py` / `tests/test_doctor.py` conventions (fake `runner`, `tempfile.mkdtemp()` workspace)
**Target Platform**: macOS/Linux, single workspace per process, same as existing `workerbees/`
**Project Type**: Single project — library module inside the existing `workerbees/` package
**Performance Goals**: Lint over a hand-built ledger completes in under 1 second (SC-002); ledger append must not add perceptible latency to a brief
**Constraints**: Recording must never make a model call (FR-003) and must never fail or block a brief (FR-008, SC-004); append must be idempotent by node id (FR-004); no second authority for execution status is created (FR-009)
**Scale/Scope**: One ledger file per workspace; nodes per run bounded by fan-out width (worker + reviewer + optional correction + N doctor probes), not a high-volume log
**Verified 2026-09-05**: `workerbees/pipeline.py` exists (9898 bytes); hook sites = the worker `runner(cmd, stdin)` call and the `review(...)` call inside `brief()` — locate by grep at implement time, not by line number.

## Constitution Check

No `.specify/memory/constitution.md` exists in this project (confirmed: `.specify/memory/` has no constitution file), so no project constitution gates apply, matching the precedent in `specs/001-codex-delegation-regime/plan.md`. The governing rules are the operator's global `CLAUDE.md` and the decisions already ratified in `docs/DECISIONS.md` (D13: dispatch graph emitted by the runner as a side effect; D13 aligns with spec FR-005 "reviewer provider != reviewed node provider" same-vendor validation rule):

| Rule | Status | Note |
|---|---|---|
| Ledger emitted as a runner side effect, never LLM-planned | PASS | `ledger.py` exposes pure functions called from `pipeline.py`/`doctor.py` after each job returns; no prompt ever asks a model to describe the graph |
| stdlib only | PASS | No new third-party dependency; JSONL + dataclasses + a hand-rolled Mermaid string builder |
| New module ≤300 lines | PASS (tracked) | `ledger.py` scoped to node/edge model, append, lint, export, rollup only; if it grows past 300 lines, split lint rules into a sibling module rather than relaxing this gate |
| No second authority for job status | PASS | FR-009: ledger status is a copy recorded at dispatch and at return, explicitly eventually consistent with the runner; runner remains canonical |
| Ledger failure never fails a brief | PASS | Recording calls wrapped in `try/except`, logged into the existing receipt dict, never raised |

No deviations requiring operator awareness beyond what D13 already ratified.

## Project Structure

### Documentation (this feature)

```text
specs/002-dispatch-graph-ledger/
├── spec.md
├── plan.md              # This file
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md  # spec quality gate (existing)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
workerbees/
├── ledger.py             # NEW - Node/Edge/Run/Finding model, append, read, lint, export (JSON+Mermaid), rollup
├── pipeline.py            # EXISTING - add ledger.record_dispatch()/record_return() calls around
│                          #   worker call (line ~68 res = runner(...)), reviewer call (~97 rv = review(...))
├── doctor.py               # EXISTING - add ledger.record_dispatch()/record_return() calls around
│                          #   probe_cli()'s runner call, tagged edge type "probes", parent_id None
├── router.py               # EXISTING - unchanged; Route already carries provider/model/tier consumed by ledger
└── routing.json            # EXISTING - unchanged; frontier tier name used by the frontier_without_gate lint rule

tests/
├── test_ledger.py          # NEW - node/edge model, idempotent append, lint (3 rules), JSON round-trip, Mermaid export, cost rollup
├── test_pipeline.py         # EXISTING - extend: a brief with worker+reviewer produces 2 ledger nodes + 1 `reviews` edge
└── test_doctor.py            # EXISTING - extend: a doctor run produces N probe nodes with edge type `probes`, no parent
```

**Structure Decision**: Single new module inside the existing flat `workerbees/` package, mirroring how `verifier.py` and `reviewer.py` are already separate single-purpose stdlib modules called from `pipeline.py`. The ledger is deliberately not a new top-level package: it has one file format, one workspace-scoped state directory (`.workerbees/`, already used by `doctor.json`), and no need for sub-modules at this size. Hooks into `pipeline.py`/`doctor.py` are additive function calls at existing call sites, not a rewrite of either module's control flow.

## Phase 0 — Research Notes

No `NEEDS CLARIFICATION` markers remain; the spec's own Clarifications session (2026-09-05) already resolved the one open design question (status ownership: the ledger keeps its own copy, eventually consistent, recorded at dispatch and at return). Findings established by reading the existing codebase before design:

- **Node emission points already exist and are few.** `pipeline.brief()` has exactly two model-call sites: the worker (`res = runner(cmd, stdin)`) and the reviewer (`rv = review(...)`, gated by `status == "needs-review" and review_enabled`). `doctor.probe_cli()` is the only doctor-side model call, invoked once per provider from `doctor.run()`. A correction/retry node type is anticipated by the spec (edge type `corrects`) but no correction/retry call exists yet in `pipeline.py` today — the ledger model must define the `corrects` edge type now so a future retry path has a place to attach, per FR-002, without requiring a ledger schema change later.
- **Route already carries the needed node attributes.** `router.Route` is a frozen dataclass with `provider`, `model`, `tier`, `cmd_kind`; `pipeline.py` already stores `route.__dict__` in the receipt. The ledger node reuses these fields directly rather than re-deriving them.
- **Workspace state directory convention is established.** `doctor.py` already writes `<workspace>/.workerbees/doctor.json`. The ledger reuses the same directory (`<workspace>/.workerbees/ledger.jsonl`), consistent with the spec's "existing per-workspace state directory" assumption.
- **Runner result carries seconds and status.** `WorkerResult` (from `adapters/base.py`, referenced by both `pipeline.py` and `doctor.py`) is the natural source of a node's `status` and `seconds`; exact field names to be confirmed against `workerbees/adapters/base.py` during implementation (not re-read in this planning pass — call `WorkerResult.__dict__` at the two emission sites rather than assuming field names).
- **Test fixture pattern.** Both existing test files fake `runner` and pass a `tempfile.mkdtemp()` workspace; `test_ledger.py` follows the same shape so hooked tests in `test_pipeline.py`/`test_doctor.py` can assert on `<ws>/.workerbees/ledger.jsonl` without any new fixture infrastructure.
- **Decision**: JSONL over a single JSON array file — satisfies FR-004 (append-only) trivially (each append is one `open(..., "a")` write of one line) and keeps a crash mid-write from corrupting prior nodes, matching the edge case "job that never returns... must record it, never drop it" and "ledger file corrupt or missing → empty ledger plus a warning, never a crash". A single JSON array would require read-modify-write on every append, which risks exactly the corruption the edge cases warn against.
- **Decision**: idempotency by node id is enforced on read (dedupe when loading the ledger into memory for lint/export/rollup), not by scanning the file on every append — appends stay O(1); a node written twice with the same id is possible on disk (e.g., duplicate dispatch call) but collapses to one node whenever the ledger is loaded, matching "a node written twice with the same id must not duplicate."
- **Decision**: correction/retry, frontier-tier gate_reason, and multi-run interleaving are modeled in the schema now (fields exist: `run_id`, `gate_reason`) even though no caller populates `corrects` edges yet — this keeps FR-002's edge-type enum satisfied without a future migration, while the record-writing hooks in `pipeline.py`/`doctor.py` only wire the two call sites that exist today.

**Output**: All NEEDS CLARIFICATION resolved above; no separate research.md required (Phase 0 findings are two-line entries, retained inline per the "Key rules" guidance to use judgment on artifact necessity for a scope this size).

## Phase 1 — Design

### Data Model

See `data-model.md` for the full Node/Edge/Run/Finding field list, validation rules, and lint rule definitions.

### Interface / Contract

`ledger.py` is an internal library module, not an externally exposed API; its "contract" is the function signatures other `workerbees/` modules call:

- `record_dispatch(workspace, *, node_id, run_id, model, tier, task, provider, parent_id, edge_type, gate_reason=None) -> None` — appends a node in a "dispatched" status; never raises (catches and swallows I/O errors, per FR-008).
- `record_return(workspace, *, node_id, status, seconds, subscription_calls) -> None` — appends the same node id again with terminal status/seconds/calls; idempotent-by-id on read means the terminal record is what lint/export/rollup see once both records exist for the same id (last-write-wins semantics on load, keyed by id, so a "dispatched" and a later "returned" line for the same id resolve to one current node — this is the concrete mechanism behind "own copy... eventually consistent").
- `load(workspace) -> Ledger` — reads and dedupes; returns an empty `Ledger` plus a `warnings` list on corrupt/missing file, never raises.
- `lint(ledger) -> list[Finding]` — pure function, no I/O; implements the three FR-005 rules.
- `to_json(ledger) -> str` / `from_json(s) -> Ledger` — round-trip export (SC round-trip test).
- `to_mermaid(ledger) -> str` — diagram export, one line per node/edge (FR-006).
- `rollup(ledger) -> dict[node_id, {"calls": int, "seconds": float}]` — per-root subtree sums (FR-007).

No HTTP/CLI surface is added; this is consistent with the project having no external interface layer for internal state (the project's only external contracts are the model-adapter command builders in `workerbees/adapters/`, which are unaffected).

### Hook Placement (pipeline.py / doctor.py)

- `pipeline.brief()`: wrap the worker call `runner(cmd, stdin)` with `record_dispatch(...)` immediately before and `record_return(...)` immediately after, using a freshly generated `node_id` and `run_id` (one `run_id` per `brief()` invocation, satisfying "two briefs in the same workspace must not interleave nodes"), `parent_id=None`, `edge_type=None` (root node). Wrap the reviewer call `review(...)` the same way, with `parent_id` = the worker node's id and `edge_type="reviews"`.
- `doctor.run()` / `probe_cli()`: wrap each provider probe with `record_dispatch(...)`/`record_return(...)`, `parent_id=None`, `edge_type="probes"`, one `run_id` per `run()` call.
- Both hook sites pass `gate_reason` only when `tier == "frontier"` and a caller-supplied reason is available (plumbed through as an optional parameter on `brief()`/dispatch call sites that route to frontier; defaulting to `None` elsewhere, which the lint rule then flags per FR-005's `frontier_without_gate`).
- All hook calls are wrapped in `try/except Exception` at the call site (or inside `ledger.py`'s public functions themselves) so a ledger I/O failure surfaces only as a receipt field (e.g., `receipt["ledger_error"] = str(e)`), never as a changed brief `status` (FR-008, SC-004).

**Output**: `data-model.md` produced. Agent context file update: this project has no `CLAUDE.md` `<!-- SPECKIT START -->`/`<!-- SPECKIT END -->` marker pair present (N/A for this project); skip marker checking.

**Phase 2 Task F2 (seconds computation)**: The `seconds` field is computed via wall-clock `time.monotonic()` around the job call in the hook at the call site (i.e., at `pipeline.py` and `doctor.py` hook sites), not by the ledger module or WorkerResult. The ledger receives the computed seconds in `record_return()` and writes it as-is to the ledger.

## Complexity Tracking

*No Constitution Check violations require justification; table intentionally omitted.*
