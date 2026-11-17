"""Lineup-mode routing: authority holder dispatches across target vendor's full model list."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from agents_inc.router import Route, _eligible

_CATALOG = json.loads((Path(__file__).parent / "models.json").read_text())["models"]


@dataclass(frozen=True)
class RoutePlan:
    """Authority-driven dispatch across a target vendor's entire model list."""
    run_id: str
    authority: Route  # who holds final say (a Route into the AUTHORITY's own provider/model)
    target_vendor: str  # e.g. "openai", "anthropic", "google" — matches models.json "vendor"
    candidates: tuple[Route, ...]  # ranked, filtered Routes drawn from target_vendor's WHOLE model list
    picked: Route | None  # candidates[0] after ranking, or None if pool empty post-filter
    mode: str  # "capability_escalation" | "authority_reassignment" | "normal" | "retry"


@dataclass(frozen=True)
class RunRecord:
    """Persisted routing decision record with full history."""
    run_id: str
    task: str
    accept_rule: str
    authority_holder: Route
    authority_limits: dict
    authority_movable: bool
    authority_move_rule: str | None
    policy_version: str
    allowed_models: tuple[str, ...]
    hard_limits: dict
    budget: dict
    tie_break_order: tuple[str, ...]
    retry_rule: dict
    model_snapshot_ref: str
    candidates_considered: tuple[dict, ...] = field(default=())
    picked: Route | None = None
    retries: tuple[dict, ...] = field(default=())
    authority_change_events: tuple[dict, ...] = field(default=())
    pre_approved_larger_pool: tuple[Route, ...] = field(default=())
    pre_approved_backup_list: tuple[Route, ...] = field(default=())

    def __post_init__(self):
        """Validate that tie_break_order is non-empty."""
        if self.tie_break_order == ():
            raise ValueError("tie_break_order must be non-empty; never use () as default")


def lineup_candidates(target_vendor: str, task: str, policy_allowed_models: set[str]) -> tuple[Route, ...]:
    """Scan models.json for ALL models where vendor == target_vendor, filter by hard limits.

    Unlike _provider_routes, iterates every tier of target_vendor, not one pinned tier.
    """
    candidates = []
    for model_name, profile in _CATALOG.items():
        if profile.get("vendor") != target_vendor:
            continue
        if model_name not in policy_allowed_models:
            continue
        if not _eligible(model_name, task):
            continue
        provider = profile.get("provider")
        tier = profile.get("tier")
        if provider and tier:
            candidates.append(Route(provider=provider, model=model_name, tier=tier, cmd_kind="http"))
    return tuple(candidates)


def filter_hard_limits(pool: tuple[Route, ...], hard_limits: dict) -> tuple[Route, ...]:
    """Filter pool by hard-limit rules (basic: all in pool are eligible; advanced filtering out of scope)."""
    # For now, return all — actual hard-limit filtering (data/tools/sandbox rules) is caller responsibility
    return pool


def rank(eligible: tuple[Route, ...], tie_break_order: tuple[str, ...], *,
         benchlm_snapshot: str | Path | None = None, benchlm_job: str | None = None) -> tuple[Route, ...]:
    """Rank eligible candidates by tie_break_order, then model ID as final tie-break."""
    if not eligible:
        return ()

    def sort_key(route: Route):
        # Extract profile for this model
        profile = _CATALOG.get(route.model, {})
        # Build tuple of sort keys in tie_break_order (lower is better)
        keys = []
        for criterion in tie_break_order:
            if criterion == "cost":
                cost_class = profile.get("cost_class", "")
                # Define cost order: free < cheap < mid < premium
                cost_order = {"free": 0, "cheap": 1, "mid": 2, "premium": 3}
                keys.append(cost_order.get(cost_class, 999))
            elif criterion == "latency":
                # Use ctx_hint as proxy for latency (lower ctx = faster)
                ctx = profile.get("ctx_hint", 999999)
                keys.append(-ctx)  # invert so lower latency (higher ctx) comes first
            else:
                keys.append(0)  # unknown criterion, tie
        # Final tie-break: model ID (alphabetically)
        keys.append(route.model)
        return tuple(keys)

    from agents_inc.benchlm import advise
    ordered = list(sorted(eligible, key=sort_key))
    # Evidence is a tie-breaker only; it cannot override the caller's cost/latency priorities.
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and sort_key(ordered[end])[:-1] == sort_key(ordered[start])[:-1]:
            end += 1
        ordered[start:end] = advise(tuple(ordered[start:end]), benchlm_snapshot, benchlm_job)
        start = end
    return tuple(ordered)


def with_pick(run: RunRecord, ranked: tuple[Route, ...], authority: Route) -> RunRecord:
    """Return updated RunRecord with new picked model."""
    picked = ranked[0] if ranked else None
    new_candidates_considered = list(run.candidates_considered)
    for route in ranked:
        new_candidates_considered.append({
            "route": {"provider": route.provider, "model": route.model, "tier": route.tier, "cmd_kind": route.cmd_kind},
            "kept": route == picked,
            "reason": "ranked" if route == picked else "not_ranked"
        })
    return RunRecord(
        run_id=run.run_id,
        task=run.task,
        accept_rule=run.accept_rule,
        authority_holder=authority,
        authority_limits=run.authority_limits,
        authority_movable=run.authority_movable,
        authority_move_rule=run.authority_move_rule,
        policy_version=run.policy_version,
        allowed_models=run.allowed_models,
        hard_limits=run.hard_limits,
        budget=run.budget,
        tie_break_order=run.tie_break_order,
        retry_rule=run.retry_rule,
        model_snapshot_ref=run.model_snapshot_ref,
        candidates_considered=tuple(new_candidates_considered),
        picked=picked,
        retries=run.retries,
        authority_change_events=run.authority_change_events,
        pre_approved_larger_pool=run.pre_approved_larger_pool,
        pre_approved_backup_list=run.pre_approved_backup_list,
    )


def with_retry(run: RunRecord, same_candidate: bool = True) -> RunRecord:
    """Record a retry attempt."""
    new_retries = list(run.retries)
    attempt_num = len(new_retries) + 1
    if run.picked:
        new_retries.append({
            "attempt": attempt_num,
            "route": {"provider": run.picked.provider, "model": run.picked.model, "tier": run.picked.tier, "cmd_kind": run.picked.cmd_kind},
            "outcome": "retry"
        })
    return RunRecord(
        run_id=run.run_id,
        task=run.task,
        accept_rule=run.accept_rule,
        authority_holder=run.authority_holder,
        authority_limits=run.authority_limits,
        authority_movable=run.authority_movable,
        authority_move_rule=run.authority_move_rule,
        policy_version=run.policy_version,
        allowed_models=run.allowed_models,
        hard_limits=run.hard_limits,
        budget=run.budget,
        tie_break_order=run.tie_break_order,
        retry_rule=run.retry_rule,
        model_snapshot_ref=run.model_snapshot_ref,
        candidates_considered=run.candidates_considered,
        picked=run.picked,
        retries=tuple(new_retries),
        authority_change_events=run.authority_change_events,
        pre_approved_larger_pool=run.pre_approved_larger_pool,
        pre_approved_backup_list=run.pre_approved_backup_list,
    )


def count_retries(run: RunRecord) -> int:
    """Count retries in the run history."""
    return len(run.retries)


def remove_failed(pool: tuple[Route, ...], run: RunRecord) -> tuple[Route, ...]:
    """Remove models that have already been tried from the pool."""
    failed_models = set()
    for retry in run.retries:
        failed_models.add(retry["route"]["model"])
    if run.picked:
        failed_models.add(run.picked.model)
    return tuple(r for r in pool if r.model not in failed_models)


def with_authority_change(run: RunRecord, frm: Route, to: Route, reason: str, event_recorded: bool = True) -> RunRecord:
    """Record an authority change event and update authority_holder."""
    new_events = list(run.authority_change_events)
    if event_recorded:
        new_events.append({
            "from": {"provider": frm.provider, "model": frm.model, "tier": frm.tier, "cmd_kind": frm.cmd_kind},
            "to": {"provider": to.provider, "model": to.model, "tier": to.tier, "cmd_kind": to.cmd_kind},
            "reason": reason,
            "timestamp": ""  # would be set by caller if needed
        })
    return RunRecord(
        run_id=run.run_id,
        task=run.task,
        accept_rule=run.accept_rule,
        authority_holder=to,
        authority_limits=run.authority_limits,
        authority_movable=run.authority_movable,
        authority_move_rule=run.authority_move_rule,
        policy_version=run.policy_version,
        allowed_models=run.allowed_models,
        hard_limits=run.hard_limits,
        budget=run.budget,
        tie_break_order=run.tie_break_order,
        retry_rule=run.retry_rule,
        model_snapshot_ref=run.model_snapshot_ref,
        candidates_considered=run.candidates_considered,
        picked=run.picked,
        retries=run.retries,
        authority_change_events=tuple(new_events),
        pre_approved_larger_pool=run.pre_approved_larger_pool,
        pre_approved_backup_list=run.pre_approved_backup_list,
    )


def authority_can_still_judge(authority: Route, escalated: Route) -> bool:
    """Check if authority can still judge output from escalated model. Stub for now: always True."""
    return True


def stop(run: RunRecord, reason: str = "") -> RunRecord:
    """Return run unchanged, with terminal state marker. Caller should check and handle stop condition."""
    return run


def route_step(run: RunRecord, event: str, pool: tuple[Route, ...], *,
               benchlm_snapshot: str | Path | None = None, benchlm_job: str | None = None) -> RunRecord:
    """Execute routing decision matrix row.

    event in {"start", "failure", "insufficient_capability", "holder_cannot_continue"}.
    Returns updated RunRecord.
    """
    if event == "start":
        # Row 1: Normal dispatch.
        eligible = filter_hard_limits(pool, run.hard_limits)
        ranked = rank(eligible, run.tie_break_order, benchlm_snapshot=benchlm_snapshot, benchlm_job=benchlm_job)
        return with_pick(run, ranked, authority=run.authority_holder)

    if event == "failure":
        # Row 2: Failure/timeout/error.
        if count_retries(run) < run.retry_rule["max_retries"]:
            return with_retry(run, same_candidate=True)
        remaining = remove_failed(pool, run)
        ranked = rank(remaining, run.tie_break_order, benchlm_snapshot=benchlm_snapshot, benchlm_job=benchlm_job)
        return with_pick(run, ranked, authority=run.authority_holder)

    if event == "insufficient_capability":
        # Row 3: Capability Escalation. Authority does NOT change.
        larger_pool = run.pre_approved_larger_pool
        if not larger_pool:
            return stop(run, reason="no capability-escalation candidate fits; ask a human")
        eligible = filter_hard_limits(larger_pool, run.hard_limits)
        ranked = rank(eligible, run.tie_break_order, benchlm_snapshot=benchlm_snapshot, benchlm_job=benchlm_job)
        if not ranked:
            return stop(run, reason="no capability-escalation candidate fits; ask a human")
        if not authority_can_still_judge(run.authority_holder, ranked[0]):
            return stop(run, reason="authority holder cannot judge escalated candidate's output")
        return with_pick(run, ranked, authority=run.authority_holder)

    if event == "holder_cannot_continue":
        # Row 4: Authority Reassignment. Authority DOES change.
        backups = run.pre_approved_backup_list
        if not backups:
            return stop(run, reason="holder cannot continue; no pre-approved backup")
        new_holder = backups[0]
        return with_authority_change(run, frm=run.authority_holder, to=new_holder,
                                     reason="holder_cannot_continue", event_recorded=True)

    return run


def pick_model_or_lineup(task: str, tier: str, available: set[str], workspace_authorized: bool,
                        lineup_target_vendor: str | None = None,
                        exclude_provider: str | None = None,
                        prefer_provider: str | None = None) -> Route | RoutePlan | None:
    """Compatibility wrapper: use lineup-mode if lineup_target_vendor given, else old pick_model path."""
    if lineup_target_vendor is None:
        # Old path — import and use existing pick_model
        from agents_inc.router import pick_model
        return pick_model(task, tier, available, workspace_authorized,
                         exclude_provider, prefer_provider)

    # Lineup-mode path: build a RoutePlan
    # For now, this is a stub that just builds candidates; full RoutePlan construction
    # requires more policy context (authority, allowed_models, etc.) passed by caller.
    policy_allowed_models = set(_CATALOG.keys())
    candidates = lineup_candidates(lineup_target_vendor, task, policy_allowed_models)
    picked = candidates[0] if candidates else None

    return RoutePlan(
        run_id="",
        authority=Route(provider="", model="", tier="", cmd_kind=""),
        target_vendor=lineup_target_vendor,
        candidates=candidates,
        picked=picked,
        mode="normal"
    )
