<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Contract: the `returned` ledger row

Written by `host_ledger.record_dispatch_return` for every dispatch that has a `run_id`, in every end state (FR-015). Today it is written from `_finish` and `_red_before_run` (`agents_inc/install/dispatch.py:1537`, `1551`). This spec adds the refusal paths (`dispatch.py:1897-1993`) and the cancel path.

Lifecycle: the `dispatched` row for the run is written once, early, as soon as the run has an id and its slots are parsed, and before the first refusal exit. Today it is written only at `dispatch.py:2022`, after the refusals at `1915`, `1925` and `1993`, so a refusal return would link to a row that does not exist. The write at `2022` becomes a no-op when the row already exists. Every `returned` row therefore links to an existing `dispatched` row.

Existing fields (`agents_inc/host_ledger.py:158-171`) keep their names and meanings: `id`, `run_id`, `model`, `tier`, `task`, `provider`, `parent_id`, `edge_type`, `status`, `seconds`, `subscription_calls`, `gate_reason`, `artifact_hash`, `effort`, token counts, `files_created`, `verdict`, `cwd`, `source`, `timestamp`.

| Field | Change | Value |
|---|---|---|
| `status` | unchanged | the outcome word |
| `gate_reason` | unchanged name | the run reason (kept for old readers) |
| `verdict` | unchanged mapping | `pass` for green, `fail` for red, null otherwise (null for `unverified`) |
| `state` | new | `passed`, `failed` or `not-checked`, mapped from the outcome word (contracts/verdict-reason-codes.md "Outcome word to three-state field"); set for every outcome including `refused-*`, `cancelled`, `dry-run` and `snapshot-failed` |
| `dispatch_row_id` | new | the `id` of the `dispatched` row of the same run (equal to `run_id` today; stated explicitly so a reader need not know that) |
| `exit_code` | new | the dispatch exit code from contracts/verdict-reason-codes.md |
| `gate_results` | new | list of `{id, argv0, state, rc, reason}`; `id` is the immutable dispatcher-assigned gate id `g<n>` (FR-012d); full argv stays in run.json |
| `scope` | new | `{state, foreign_count, in_scope_count}` plus `unreadable_count` and `unbaselined_count` when non-zero; `state` is `not-checked` when an allowed path was unreadable. `exit_code` is the code the process returned. Every attempted run or resume turn with a run id ends with its own `returned` row (a resume never erases older rows); `run.json` `ledger_returns` counts them |
| `claims` | new | `{state, unsupported, items, omitted, weak}`; `items` lists each unsupported claim as `{kind, claimed, observed}` plus an optional `reason` (for example `multiple-claims-blocks`) (FR-012, FR-012a). `omitted` lists gate ids with no `gate-result` claim (FR-012c); `not_checked` (present when non-empty) lists file claims with no evidence (`unreadable`, `unbaselined`). `weak` lists gate ids whose claim rests on zero collected tests (FR-012f). The count stays as a summary. |

Example:

```json
{"id": "20261115T101500Z-sonnet-ab12cd", "run_id": "20261115T101500Z-sonnet-ab12cd", "status": "unverified",
 "gate_reason": "gate-not-runnable", "verdict": null, "dispatch_row_id": "20261115T101500Z-sonnet-ab12cd",
 "exit_code": 4, "gate_results": [{"id": "g1", "argv0": "pytest", "state": "not-checked", "rc": null, "reason": "gate-not-runnable"}],
 "scope": {"state": "passed", "foreign_count": 0, "in_scope_count": 2}, "claims": {"state": "checked", "unsupported": 1, "omitted": [], "weak": [], "items": [{"kind": "file-changed", "claimed": "out.txt", "observed": "unchanged"}]}, "state": "not-checked",
 "source": "dispatch"}
```

A ledger write failure is recorded in run.json `ledger_return_error` and never changes the outcome (unchanged, `dispatch.py:1588-1599`).
