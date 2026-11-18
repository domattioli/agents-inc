# Optional BenchLM triage evidence

Callers may pass `benchlm_snapshot` and an explicit `benchlm_job` to
`router.pick_model_chain`, `router.pick_model`, `lineup_router.rank`, `lineup_router.route_step`, or `pipeline.brief`. These
arguments are opt-in; without both, existing ordering applies. The lineup ranker
must receive candidates already filtered by the caller's policy and hard limits.
The advisory never adds candidates or grants provider or model access. In lineup routing, evidence breaks ties only after the caller's cost and latency priorities.

The snapshot is an operator-maintained local JSON file. Example shape (model
names and ranks are illustrative, not BenchLM recommendations):

```json
{
  "source": "https://benchlm.ai/tools/llm-selector",
  "date": "2026-11-17",
  "entries": [
    {"job": "Coding", "evidence_kind": "direct", "rank": 1,
     "cohort": "general", "model": "catalog-model-id"}
  ]
}
```

Use the exact selector job name and catalog model ID. Each entry records a
positive integer rank, evidence kind (`direct` or `proxy`), and a nonempty
cohort. The source and ISO date apply to every entry. Only comparable entries
within the same provider, job, evidence kind, and cohort can reorder ranked
slots; unranked slots stay in place. The OpenRouter auto fallback stays in
place. Duplicate job/model entries invalidate the snapshot. Missing, malformed,
future-dated, or older-than-90-day snapshots and unsupported jobs preserve the
existing order. All entries are validated before any ranking. No site fetch or
rankings are bundled. The date is the operator's snapshot date, not proof that
the source remains current.

Before each release, review and refresh any local snapshot from an authorized source, then validate it with `python3 -m agents_inc.benchlm /path/to/snapshot.json`. Validation checks format and freshness, not whether the supplied ranks are true. Verify the model IDs, job, evidence kind, cohort, rank and source date; discard stale or uncertain evidence. BenchLM describes automated routing and redistribution under its own plans and terms. The snapshot is optional and is not bundled. See [BenchLM data access](https://benchlm.ai/data/access).

These optional Python arguments are not wired into the `agents-inc dispatch` command or its installed host hooks. Callers must supply both arguments explicitly; ordinary dispatch behavior does not change.

The [BenchLM API specification](https://data.benchlm.ai/openapi.json) says its recommendation endpoint ranks a general surface and does not provide per-use-case quality scores. Do not import its surface ranks as selector job ranks. Until an authorized job-ranking feed is available, refresh the local job snapshot by reviewing the selector evidence and its terms; this is a manual release checkpoint.
