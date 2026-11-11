"""Spec 038 T043 (FR-017): the one list of guest agent nicknames. Import-light (json and pathlib only), so the agent
gate (install/hook.py), the host ledger (host_ledger.py) and the native registry (install/native.py) share it without
pulling in the installer.

Codex nicknames are fixed; free nicknames are the `nickname` fields in models.json (tests/test_native_nicknames.py keeps
each one a FREE_MODELS slug, and native.py drops any whose provider has no adapter).
"""
from __future__ import annotations

import json
from pathlib import Path

CODEX_NICKS = ("luna", "sol", "terra", "astra")
RELAY_TYPE = "agents-inc:relay"
_MODELS_PATH = Path(__file__).resolve().parent / "models.json"


def free_nicknames() -> dict[str, str]:
    """Nickname -> slug for each models.json entry with a `nickname`. Raises ValueError when one nickname names two slugs."""
    try:
        models = json.loads(_MODELS_PATH.read_text(encoding="utf-8"))["models"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out: dict[str, str] = {}
    for slug, spec in models.items():
        nick = spec.get("nickname") if isinstance(spec, dict) else None
        if isinstance(nick, str):
            if nick in out: raise ValueError(f"models.json: nickname {nick!r} names two slugs")
            out[nick] = slug
    return out


def nicknames() -> tuple[str, ...]:
    return (*CODEX_NICKS, *free_nicknames())


def guest_types() -> frozenset[str]:
    """`agents-inc:<nickname>` for every guest agent model."""
    return frozenset(f"agents-inc:{n}" for n in nicknames())


CHARS_PER_TOKEN = 3  # conservative for code and JSON, which tokenize worse than prose
REPLY_HEADROOM = 0.25  # the share of the window left for the reply


def context_chars(slug: str, fallback: int) -> int:
    """The prompt cap for a guest agent step: the models.json `ctx_hint` (tokens) as chars with reply headroom; `fallback`
    when the model has no usable hint. The hint is a floor the roster keeps conservative, so the cap is too."""
    try:
        hint = json.loads(_MODELS_PATH.read_text(encoding="utf-8"))["models"][slug]["ctx_hint"]
    except (OSError, ValueError, KeyError, TypeError):
        return fallback
    if isinstance(hint, bool) or not isinstance(hint, (int, float)) or hint <= 0: return fallback
    return int(hint * CHARS_PER_TOKEN * (1 - REPLY_HEADROOM))
