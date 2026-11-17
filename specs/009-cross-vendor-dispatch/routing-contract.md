<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# 009 — Cross-Vendor Dispatch Semantics: Routing Contract

Machine doc. Design spec, not code. Implements RFC "Cross-Vendor Dispatch Semantics" Part 2 (Part 1 = glossary + D39, already landed in `CONTEXT.md` and `docs/DECISIONS.md` — not touched here). This doc is self-contained: an implementer should be able to build from it without re-reading the RFC.

Status: specified, not started. No code changed by this doc.

## 0. Current code as-read (cited, not paraphrased)

- `workerbees/routing.json:1-13` — flat JSON. `required` (`claude`, `codex`) + `optional` (`gemini`, `mistral`, `openrouter`) provider lists (`:2-3`); `tiers` maps tier name → one model per provider, single string except `grunt.gemini`/`grunt.mistral`/`grunt.openrouter` which name one free/cheap model each (`:5-8`); `task_tier` maps a task string to exactly one tier (`:10`); `optional_allowed_tasks` gates which tasks may use optional providers at all (`:11`).
- `workerbees/models.json:1-4` — catalog keyed by model name (not provider+model). Each entry: `vendor`, `provider`, `tier`, `tasks_good`, `tasks_bad`, `ctx_hint`, `cost_class`, `status`. `:3` explicitly disclaims that `tasks_good`/`tasks_bad` is a raw quality axis, separate from CLAUDE.md's economic dispatch policy. Vendors present (grepped): `anthropic, codex(openai), google, mistral, cohere, dots-studio, inclusionai, liquid, minimax, nvidia, openai, poolside, thinkingmachines, z-ai`. Providers present: `claude, codex, gemini, mistral, openrouter`.
- `workerbees/router.py:11-16` — `Route` dataclass: `provider: str, model: str, tier: str, cmd_kind: str` (`"cli"` for claude/codex, `"http"` for optional providers). This is the only routing-result shape in the codebase today.
- `workerbees/router.py:18-24` — `_eligible(model, task, require_good=False)`: false if model missing from catalog or `status == "unavailable"`; false if `task in tasks_bad`; if `require_good`, also requires `task in tasks_good`.
- `workerbees/router.py:26-43` — `_provider_routes(provider, task, tier)`: for `openrouter`, scans the WHOLE catalog for matching `provider`+`tier`+eligibility (this is the one place today that already iterates a vendor's full lineup, but only for the openrouter provider, and only within one tier). For every other provider it reads `routing.json["tiers"][tier][provider]` — i.e. **exactly one pinned model per (tier, provider) pair** (or a short fixed list, per `:40`). There is no path today where `claude` or `codex` routes across their own full lineup, and no path where the picking model differs from the fixed tier table's owner.
- `workerbees/router.py:45-63` — `pick_model_chain(task, tier, available, workspace_authorized, exclude_provider=None, prefer_provider=None)`: builds provider order from `required + optional` (`:51`), reorders for `prefer_provider` (`:52-54`), skips unavailable/excluded providers (`:57`), skips optional providers when not `workspace_authorized` or task not in `optional_allowed_tasks` (`:59-61`), concatenates `_provider_routes(...)` per provider (`:62`) into one bounded retry-ordered tuple.
- `workerbees/router.py:65-69` — `pick_model(...)`: thin wrapper, returns `chain[0]` or `None`.

**Gap this spec fills:** nothing above lets one authority-holding model dispatch across *another vendor's whole model list* while itself staying the authority. `_provider_routes` for non-openrouter providers is pinned to `routing.json`'s single-model-per-tier table, and there is no concept of "authority holder" separate from "which provider's tier table is being read" anywhere in `router.py`. This spec adds that as a new, additive mode.

## 1. New data shape — `RoutePlan` (lineup-mode)

Lineup-mode = one authority holder routes across a WHOLE target vendor's model list (not the tier-pinned single model). New dataclass, additive to `router.py`, does not replace `Route`:

```python
@dataclass(frozen=True)
class RoutePlan:
    run_id: str                      # unique id for this Run record, see section 2
    authority: Route                 # who holds final say (a Route into the AUTHORITY's own provider/model)
    target_vendor: str                # e.g. "openai", "anthropic", "google" — matches models.json "vendor"
    candidates: tuple[Route, ...]     # ranked, filtered Routes drawn from target_vendor's WHOLE model list
    picked: Route | None              # candidates[0] after ranking, or None if pool empty post-filter
    mode: str                         # "capability_escalation" | "authority_reassignment" | "normal" | "retry"
```

Key distinction from today's `Route`/`pick_model_chain`:
- `Route` and `pick_model_chain` answer "which model runs the task" for ONE provider at a time, pinned by `routing.json["tiers"]`.
- `RoutePlan` answers a two-part question: (a) who holds authority (a `Route`, unchanged shape, own vendor), and (b) what pool of candidate `Route`s, drawn from a DIFFERENT vendor's entire catalog (all tiers, not one pinned tier), the authority is allowed to pick from. `target_vendor` is the vendor being routed INTO; `authority.provider`/`authority.model` is who is routing.

`candidates` population rule (new function, additive):

```python
def lineup_candidates(target_vendor: str, task: str, policy_allowed_models: set[str]) -> tuple[Route, ...]:
    """Scan models.json for ALL models where vendor == target_vendor, filter by hard limits
    (policy_allowed_models, _eligible(model, task) same as today), rank by policy tie-break order.
    Unlike _provider_routes, this iterates every tier of target_vendor, not one pinned tier."""
```

This mirrors the openrouter special-case already in `_provider_routes` (`router.py:27-38`, whole-catalog scan) but generalizes it to ANY vendor, and separates "who is scanning" (authority) from "whose lineup is scanned" (target_vendor) — a distinction the openrouter case doesn't need because the scanner there is always the fixed dispatch mechanism, never a separate authority-holding model.

**Authority is a role, not a rung** (RFC §1): nothing in `RoutePlan` restricts `authority.tier` — any `Route`, at any tier, in `models.json`, MAY be an authority holder, gated only by policy (`policy_allowed_models` / a to-be-defined authority allowlist, out of scope for this doc's data shape — see Open Questions). `RoutePlan` does not enforce the "untrusted free-tier model can never hold authority" rule (RFC §1) itself; that rule is a POLICY check the caller must run before constructing a `RoutePlan` with a given `authority`. This spec does not invent that allowlist mechanism — flagged as an open question below.

## 2. Run record — exact fields (from RFC §2, verbatim mapping)

RFC §2 states: "A Run record needs: task + accept rule; who holds authority + limits; whether/how authority can move; policy version; which models are allowed; hard limits (skill/tool/data rules); budget/deadline; tie-break order; retry/fallback rule." And: "Must persist: every candidate considered plus why kept/dropped, the picked model, snapshot ref, retries, and any authority-change event."

Concrete shape (JSON-serializable dict or dataclass — implementer's choice, fields are load-bearing, not the container type):

```python
@dataclass(frozen=True)
class RunRecord:
    run_id: str
    task: str                              # task identifier, e.g. "classify", "code-review"
    accept_rule: str                       # human-readable acceptance criterion, e.g. "matches labeled answer key"
    authority_holder: Route                # who holds Task Authority at Run start
    authority_limits: dict                 # e.g. {"max_cost_usd": 2, "max_latency_sec": 120} — the bounds authority cannot exceed
    authority_movable: bool                # can authority move mid-Run? (Capability Escalation never moves it; Authority Reassignment does)
    authority_move_rule: str | None         # if movable: which backup list / condition triggers reassignment; None if not movable
    policy_version: str                     # version tag of the routing policy in effect (e.g. routing.json content hash or explicit version field)
    allowed_models: tuple[str, ...]         # the full allowed pool BEFORE hard-limit filtering (policy scope)
    hard_limits: dict                       # skill/tool/data rules, e.g. {"data": "public_only", "tools": "none", "sandbox": "no_network"}
    budget: dict                            # {"max_cost_usd": ..., "deadline_sec": ...}
    tie_break_order: tuple[str, ...]        # objective order, e.g. ("cost", "latency"); model ID is the FINAL implicit tie-break (RFC §2)
    retry_rule: dict                        # {"max_retries": int, "fallback": "next_candidate" | "stop"}
    model_snapshot_ref: str                 # pointer/hash identifying the exact models.json + routing.json content used (for replay)
    candidates_considered: tuple[dict, ...] # one entry per candidate: {"route": Route, "kept": bool, "reason": str}
    picked: Route | None
    retries: tuple[dict, ...]               # one entry per retry attempt: {"attempt": int, "route": Route, "outcome": str}
    authority_change_events: tuple[dict, ...]  # empty unless authority moved; each: {"from": Route, "to": Route, "reason": str, "timestamp": str}
```

Notes tying back to RFC §2 exactly:
- "same Run + same policy + same model-list snapshot + same event history -> same route picked" ("policy-choice determinism") requires `policy_version` + `model_snapshot_ref` + the full `candidates_considered`/`retries`/`authority_change_events` history to be persisted verbatim — replay recomputes `picked` from these inputs and must match.
- "No stated order = invalid Run — never guess a default order": `tie_break_order` MUST be present and non-empty; a `RunRecord` with `tie_break_order == ()` is invalid and must be rejected at construction, not defaulted (e.g. not silently defaulted to `("cost",)`).
- Persistence must include candidates DROPPED too, with reason (`candidates_considered` entries carry `kept: bool` + `reason`), not just the winner — RFC §2 final paragraph is explicit ("enough detail to replay the decision, not just a summary").

## 3. Routing matrix — decision-table form (from RFC §3, verbatim)

| # | Condition | Eligible pool | Action | Authority holder |
|---|---|---|---|---|
| 1 | Normal dispatch | Full allowed list minus hard-limit failures | Rank, pick best | Unchanged |
| 2 | Failure/timeout/error | Remaining eligible pool (already-failed candidates removed) | Fixed N retries, then re-rank | Unchanged — failure alone grants no new power |
| 3 | Insufficient capability | Pre-approved larger pool | Capability Escalation; if none fit, STOP and ask a human | Unchanged, only if holder can still judge the result |
| 4 | Holder can't continue | Pre-approved backup list | Pick next backup, record Authority Reassignment; if none, STOP | Moves only via an explicit recorded event |

Pseudocode an implementer can code directly from:

```python
def route_step(run: RunRecord, event: str, pool: tuple[Route, ...]) -> RunRecord:
    """event in {"start", "failure", "insufficient_capability", "holder_cannot_continue"}.
    Returns an updated RunRecord (candidates_considered / retries / authority_change_events appended,
    picked updated). Caller persists the returned RunRecord after every call — see section 2."""

    if event == "start":
        # Row 1: Normal dispatch.
        eligible = filter_hard_limits(pool, run.hard_limits)
        ranked = rank(eligible, run.tie_break_order)
        return with_pick(run, ranked, authority=run.authority_holder)  # authority unchanged

    if event == "failure":
        # Row 2: Failure/timeout/error.
        if count_retries(run) < run.retry_rule["max_retries"]:
            return with_retry(run, same_candidate=True)                # fixed N retries, same pick
        remaining = remove_failed(pool, run)
        ranked = rank(remaining, run.tie_break_order)
        return with_pick(run, ranked, authority=run.authority_holder)  # re-rank, authority unchanged
        # if `remaining` is empty after exhausting retries: STOP (no row covers a further action;
        # this is the terminal case of Row 2 falling through to Row 3's "if none fit, STOP" language
        # by analogy — see Open Question below, RFC does not spell out Row 2's own empty-pool terminal case)

    if event == "insufficient_capability":
        # Row 3: Capability Escalation. Authority does NOT change.
        larger_pool = run.pre_approved_larger_pool          # must be pre-approved BEFORE the Run per RFC §3
        eligible = filter_hard_limits(larger_pool, run.hard_limits)
        ranked = rank(eligible, run.tie_break_order)
        if not ranked:
            return stop(run, reason="no capability-escalation candidate fits; ask a human")
        if not authority_can_still_judge(run.authority_holder, ranked[0]):
            return stop(run, reason="authority holder cannot judge escalated candidate's output")
        return with_pick(run, ranked, authority=run.authority_holder)  # SAME authority, stronger worker

    if event == "holder_cannot_continue":
        # Row 4: Authority Reassignment. Authority DOES change, must be explicit + recorded.
        backups = run.pre_approved_backup_list                # must be pre-approved BEFORE the Run
        if not backups:
            return stop(run, reason="holder cannot continue; no pre-approved backup")
        new_holder = backups[0]
        return with_authority_change(run, frm=run.authority_holder, to=new_holder,
                                      reason="holder_cannot_continue", event_recorded=True)
```

`filter_hard_limits`, `rank`, `with_pick`, `with_retry`, `with_authority_change`, `stop` are helper stubs the implementer fills in; `rank` must use `run.tie_break_order` then fall back to model-ID sort as the final tie-break (RFC §2, "Break ties by model ID").

## 4. Example Runs — as concrete test-case inputs

These are RFC §4's three illustrative Runs, translated into dict/JSON shapes suitable for unit tests. Names/prices are RFC-illustrative, NOT pinned real values — see Non-Goals section 6.

```python
RUN_1_INPUT = {
    "run_id": "example-run-1",
    "task": "classify",
    "accept_rule": "matches a labeled answer key",
    "authority_holder": {"provider": "claude", "model": "sonnet", "tier": "workhorse", "cmd_kind": "cli"},
    "target_vendor": "openai",  # RFC: "picks from OpenAI's whole lineup" — nano/mini/full/o-series, i.e. ALL tiers
    "authority_movable": False,
    "hard_limits": {"data": "public_only", "output": "structured"},
    "budget": {"max_cost_usd": 2, "deadline_sec": 120},
    "accept_threshold": {"match_pct": 98},
    "tie_break_order": ("cost", "latency"),
    "retry_rule": {"max_retries": 1, "fallback": "next_candidate"},
    "expected_authority_after_run": "sonnet",  # RFC: "Sonnet keeps authority" even on failure/drop
}

RUN_2_INPUT = {
    "run_id": "example-run-2",
    "task": "review",  # "check an 80k-token doc for contradictions"
    "accept_rule": "findings have evidence links to a checklist",
    "authority_holder": {"provider": "codex", "model": "<an-openai-model>", "tier": "workhorse", "cmd_kind": "cli"},
    "target_vendor": "anthropic",  # RFC: "picks from Claude's whole lineup" — haiku/sonnet/opus, ALL tiers
    "authority_movable": False,
    "hard_limits": {"context_fit": "80k_tokens", "approved_for": "long_review", "tools": "none"},
    "budget": {"max_cost_usd": 5, "deadline_sec": 90},
    "tie_break_order": ("latency", "cost"),
    "retry_rule": {"max_retries": 1, "fallback": "next_candidate"},
    "expected_authority_after_run": "<same-openai-model>",  # RFC: "OpenAI model keeps authority"
}

RUN_3_INPUT = {
    "run_id": "example-run-3",
    "task": "code-write",  # "fix a broken small code tool against a fixed test suite"
    "accept_rule": "passes hidden test suite",
    "authority_holder": {"provider": "codex", "model": "<small-cheap-model>", "tier": "grunt", "cmd_kind": "cli"},
    "target_vendor": None,  # RFC: pool is "Gemini + Mistral models with tool access" — TWO vendors, not one;
                             # RoutePlan.target_vendor is singular (section 1) — this Run needs either two
                             # RoutePlan instances (one per vendor) merged, or a multi-vendor extension.
                             # NOT resolved by this spec — see Open Questions.
    "hard_limits": {"sandbox": True, "network": False, "tests": "hidden"},
    "budget": {"max_cost_usd": 1, "deadline_sec": 60},
    "tie_break_order": ("cost",),
    "retry_rule": {"max_retries": 0, "fallback": "capability_escalation"},
    "events": [
        {"type": "insufficient_capability", "trigger": "failing tests", "expected_action": "escalate to next bigger worker, SAME authority"},
        {"type": "holder_cannot_continue", "trigger": "small model can no longer judge the fix", "expected_action": "Authority Reassignment to pre-approved backup"},
        {"type": "no_backup_left", "expected_action": "stop"},
    ],
}
```

Test assertions each of these implies (for the future implementer's unit tests):
- Run 1 / Run 2: `authority_holder` field on the resulting `RoutePlan`/`RunRecord` is byte-identical before and after any retry or candidate-drop — this is the row-1/row-2 invariant ("Unchanged").
- Run 1: `candidates` pool for `target_vendor="openai"` must include models across MULTIPLE tiers (nano/mini/full/o-series), not just one pinned tier — this is the behavior distinguishing lineup-mode from today's `_provider_routes`.
- Run 3: two `authority_change_events`-shaped transitions must be exercised (escalation with no authority change, then reassignment with a recorded event) plus a terminal `stop` when backups are exhausted.

## 5. Migration path — additive, not a rewrite

Goal: existing `routing.json` consumers and `pick_model()`/`pick_model_chain()` callers keep working unchanged.

- `Route` (router.py:11-16) is NOT modified. `RoutePlan` and `RunRecord` (sections 1-2) are NEW dataclasses in the same module or a new sibling module (e.g. `workerbees/lineup_router.py`), imported by callers who opt into lineup-mode.
- `pick_model()` / `pick_model_chain()` (router.py:45-69) are NOT modified. They remain the tier-pinned, single-vendor-lineup (openrouter-only) path for existing callers (`routing.json`-driven, single provider per call).
- New function `lineup_candidates(target_vendor, task, policy_allowed_models)` (section 1) is additive — it reads `models.json` the same way `_provider_routes`'s openrouter branch already does (router.py:27-38), just generalized to any `vendor` field instead of hardcoding `provider == "openrouter"`. It does NOT touch `routing.json`'s `tiers` table at all; lineup-mode bypasses tier-pinning by design (that's the whole point of "whole lineup" per RFC §1).
- A thin compatibility wrapper, e.g.:
  ```python
  def pick_model_or_lineup(task, tier, available, workspace_authorized, *,
                            lineup_target_vendor: str | None = None, **kwargs) -> Route | RoutePlan:
      if lineup_target_vendor is None:
          return pick_model(task, tier, available, workspace_authorized, **kwargs)  # old path, unchanged
      return build_route_plan(task, lineup_target_vendor, ...)                       # new path
  ```
  lets a caller opt in per-call without any existing call site changing. No existing call site needs to pass `lineup_target_vendor`, so no existing caller's behavior changes.
- `routing.json`'s schema is untouched. If/when lineup-mode needs its own policy config (the "pre-approved larger pool" and "pre-approved backup list" referenced in section 3's Row 3/Row 4), that lands as a NEW top-level key (e.g. `routing.json["lineup_policy"]`) additive to the existing file, never replacing `tiers`/`task_tier`/`optional_allowed_tasks`. This spec does not design that key's shape — flagged as an open question below (the RFC does not specify its exact format either, only that such lists must be "pre-approved").

## 6. Non-goals (explicit)

- **No claim that model output itself is deterministic** (RFC §2, "NOT claimed"). This spec's determinism claim is scoped to policy-choice (which route gets picked) and reproducible replay (recomputing that choice later from saved inputs) — never to what the picked model actually outputs.
- **No untrusted free-tier model may ever hold Task Authority** (RFC §1). This spec does not add an allowlist/trust-check mechanism itself (flagged as open question below) but any implementation MUST reject constructing a `RunRecord`/`RoutePlan` whose `authority_holder` is an unreviewed free-tier model. "Reviewed and qualifies" removes the "untrusted" label per RFC §1 — this spec does not define the review process.
- **No live-availability claim, no full re-execution reproducibility claim** (RFC §2, both explicitly "NOT claimed").
- **Out of scope entirely, not touched by this doc**: Bindle Backend B, `finish_run`, real bindle install, or any other bindle-related mechanism. Nothing in this spec assumes or requires those exist.
- **No real model IDs/prices/test data pinned here** (RFC §5) — section 4's example Runs use RFC-illustrative placeholders (`<an-openai-model>`, `<small-cheap-model>`) intentionally; pinning concrete IDs/prices is a separate follow-up before any real dispatch uses this spec.

## 7. Open questions (genuinely unresolved by the RFC — not guessed here)

1. **Authority allowlist mechanism.** RFC §1 states policy decides who may hold authority and that untrusted free-tier models never can, but never specifies the allowlist's shape, storage location, or the "reviewed and qualifies" review process. This spec's `RunRecord.allowed_models` field names the pool but not how trust-review promotes a model into it. Needs a separate decision before implementation.
2. **Multi-vendor pool in one Run (RFC §4 Run 3).** `RoutePlan.target_vendor` (section 1) is singular, but Run 3's pool is explicitly "Gemini + Mistral" — two vendors at once. The RFC does not say whether this is one `RoutePlan` with a multi-vendor pool, two merged `RoutePlan`s, or a different shape entirely. Section 4 flags this inline; not resolved here.
2a. Related: RFC Run 3 also never states `target_vendor` for the escalation/backup pools explicitly beyond "next bigger worker" / "pre-approved backup" — whether escalation stays within Gemini+Mistral or may cross to a third vendor is unstated.
3. **Row 2's own empty-pool terminal case.** RFC §3 Row 2 ("Fixed N retries, then re-rank") does not state what happens if re-ranking the remaining eligible pool yields nothing (all candidates exhausted, no escalation triggered). Section 3's pseudocode notes this by analogy to Row 3's STOP language but the RFC itself does not specify this transition — flagged, not invented as a certain rule.
4. **`lineup_policy` config shape in `routing.json`.** Section 5 names where a "pre-approved larger pool" / "pre-approved backup list" config would live but the RFC does not specify its schema (per-task? per-authority-holder? global?). Left as a follow-up design decision, not guessed here.
5. **Exact form of `model_snapshot_ref`.** RFC §2 requires a "snapshot ref" sufficient for replay but does not specify whether that's a content hash of `models.json`+`routing.json`, a version string, or a git commit SHA. Section 2 leaves the field typed as `str` without prescribing its construction.
