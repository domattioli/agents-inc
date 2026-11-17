"""Pick catalog-eligible stdin worker models. routing.json sets provider order and defaults."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_TABLE = json.loads((Path(__file__).parent / "routing.json").read_text())
_CATALOG = json.loads((Path(__file__).parent / "models.json").read_text())["models"]
_AUTO_FREE = "openrouter/auto:free"

@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    tier: str
    cmd_kind: str  # "cli" for claude/codex, "http" for optional providers

def _overlay_status(model: str, profile: dict, overlay: dict | None) -> str:
    """Overlay status wins over catalog status when present (mirrors free_health.effective_status)."""
    entry = overlay.get(model) if overlay else None
    if entry and "status" in entry:
        return entry["status"]
    return profile.get("status", "unprobed")

def _eligible(model: str, task: str, *, require_good: bool = False, overlay: dict | None = None) -> bool:
    profile = _CATALOG.get(model)
    if not profile:
        return False
    status = _overlay_status(model, profile, overlay) if overlay is not None else profile.get("status")
    if status == "unavailable":
        return False
    if task in profile.get("tasks_bad", []):
        return False
    return not require_good or task in profile.get("tasks_good", [])

def _cooldown_keys(provider: str, tier: str) -> set[str]:
    from . import free_health
    configured_model = _TABLE["tiers"].get(tier, {}).get(provider)
    if isinstance(configured_model, list):
        configured_model = configured_model[0] if configured_model else None
    keys = {provider, free_health.backend_key(provider, configured_model)}
    return keys

def _in_cooldown(provider: str, tier: str, health: dict, now: datetime) -> bool:
    """Check cooldown against an already-loaded health dict (no re-read per provider)."""
    for key in _cooldown_keys(provider, tier):
        record = health.get(key)
        if not record:
            continue
        cooldown_until = record.get("cooldown_until")
        if not cooldown_until:
            continue
        try:
            until = datetime.fromisoformat(cooldown_until)
        except (ValueError, TypeError):
            continue
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if now < until:
            return True
    return False

def _at_cap(provider: str, now: datetime) -> bool:
    try:
        from . import free_caps
    except ImportError:
        return False
    try:
        return free_caps.at_cap(provider, now=now)
    except Exception:
        return False

def _remap_codex(model: str, model_map: dict[str, str] | None = None) -> str:
    """Apply a user nickname override (roster/env) to a routing.json codex slug, on read only."""
    from .install.runtime import MODEL_ALIASES, load_model_map
    model_map = load_model_map() if model_map is None else model_map
    for nick, default in MODEL_ALIASES.items():
        if model == default:
            return model_map.get(nick, default)
    return model

def _provider_routes(provider: str, task: str, tier: str, overlay: dict | None = None) -> list[Route]:
    if provider == "openrouter":
        named = [
            Route(provider, model, tier, "http")
            for model, profile in _CATALOG.items()
            if model != _AUTO_FREE
            and profile.get("provider") == provider
            and profile.get("tier") == tier
            and _eligible(model, task, require_good=True, overlay=overlay)
        ]
        if _eligible(_AUTO_FREE, task, require_good=True, overlay=overlay):
            named.append(Route(provider, _AUTO_FREE, tier, "http"))
        return named
    configured = _TABLE["tiers"].get(tier, {}).get(provider)
    models = configured if isinstance(configured, list) else [configured]
    if provider == "codex":
        models = [_remap_codex(m) if m else m for m in models]
    kind = "cli" if provider in _TABLE["required"] else "http"
    return [Route(provider, model, tier, kind) for model in models
            if model and _eligible(model, task, overlay=overlay)]

def pick_model_chain(task: str, tier: str, available: set[str], workspace_authorized: bool,
                     exclude_provider: str | None = None,
                     prefer_provider: str | None = None, local_authorized: bool = False,
                     local_only: bool = False, *, benchlm_snapshot: str | Path | None = None,
                     benchlm_job: str | None = None) -> tuple[Route, ...]:
    """Return bounded candidates in retry order. OpenRouter auto:free is always last."""
    if tier not in _TABLE["tiers"]:
        return ()
    from . import free_health
    now = datetime.now(timezone.utc)
    # Load health/overlay once per call so missing/corrupt files warn at most once here.
    health = free_health.load_health()
    overlay = free_health.load_overlay()

    order = list(_TABLE["required"] + _TABLE["optional"])
    modality = os.environ.get("AGENTS_INC_MODALITY", "ideal")
    if (modality == "budget" and tier == "grunt" and workspace_authorized
            and task in _TABLE.get("optional_allowed_tasks", [])):
        free_first = [p for p in _TABLE.get("free_order", []) if p in order]
        order = free_first + [p for p in order if p not in free_first]
    if prefer_provider in order:
        order.remove(prefer_provider)
        order.insert(0, prefer_provider)

    # If local_only, restrict to ollama only
    if local_only:
        order = ["ollama"]

    routes: list[Route] = []
    for provider in order:
        if provider not in available or provider == exclude_provider:
            continue
        if provider == "ollama":
            # ollama gated on local_authorized instead of workspace_authorized; explicit selection required
            if not (prefer_provider == "ollama" or local_only) or not local_authorized or task not in _TABLE["optional_allowed_tasks"]:
                continue
        elif provider in _TABLE["optional"]:
            if not workspace_authorized or task not in _TABLE["optional_allowed_tasks"]:
                continue
            if _in_cooldown(provider, tier, health, now) or _at_cap(provider, now):
                continue
        routes.extend(_provider_routes(provider, task, tier, overlay=overlay))
    from .benchlm import advise
    return advise(tuple(routes), benchlm_snapshot, benchlm_job)

def pick_model(task: str, tier: str, available: set[str], workspace_authorized: bool,
               exclude_provider: str | None = None, prefer_provider: str | None = None,
               local_authorized: bool = False, local_only: bool = False, *,
               benchlm_snapshot: str | Path | None = None, benchlm_job: str | None = None) -> Route | None:
    chain = pick_model_chain(task, tier, available, workspace_authorized,
                             exclude_provider, prefer_provider, local_authorized=local_authorized,
                             local_only=local_only, benchlm_snapshot=benchlm_snapshot,
                             benchlm_job=benchlm_job)
    return chain[0] if chain else None
