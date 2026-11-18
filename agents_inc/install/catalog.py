"""D52: read the local Codex model catalog (models_cache.json). Offline; never raises on a bad cache."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path


def cache_path(env: dict | None = None) -> Path:
    """$CODEX_HOME/models_cache.json when CODEX_HOME is set, else ~/.codex/models_cache.json."""
    env = os.environ if env is None else env
    if env.get("CODEX_HOME"):
        return Path(env["CODEX_HOME"]) / "models_cache.json"
    return Path(env.get("HOME") or Path.home()) / ".codex" / "models_cache.json"


def load(path: Path | str | None = None) -> list[dict] | None:
    """The list of model dicts, or None when the file is missing or malformed."""
    try:
        data = json.loads(Path(path or cache_path()).read_text(encoding="utf-8"))
        models = data["models"]
        if not isinstance(models, list):
            return None
        return [m for m in models if isinstance(m, dict)]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def version(slug: str) -> tuple[int, ...] | None:
    """gpt-6.1-sol -> (6, 1); gpt-6-sol -> (6,); None when unparseable."""
    match = re.match(r"gpt-(\d+(?:\.\d+)*)(?:-|$)", slug or "")
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def _key(ver: tuple[int, ...]) -> tuple[int, ...]:
    return ver + (0,) * (8 - len(ver))  # pad so (6,) == (6, 0) and 6.1 > 6 > 5.6


def family(slug: str) -> str:
    return slug.rsplit("-", 1)[-1]


def entry(slug: str, models: list[dict] | None = None) -> dict | None:
    models = load() if models is None else models
    for model in models or ():
        if model.get("slug") == slug:
            return model
    return None


def newest(fam: str, models: list[dict] | None = None) -> str | None:
    """Highest-version listed, API-supported slug of a family; None when no cache or no match. Priority is ignored."""
    models = load() if models is None else models
    best, best_key = None, None
    for model in models or ():
        slug = model.get("slug")
        ver = version(slug) if isinstance(slug, str) else None
        if ver is None or family(slug) != fam or model.get("visibility") != "list" or model.get("supported_in_api") is not True:
            continue
        if best_key is None or _key(ver) > best_key:
            best, best_key = slug, _key(ver)
    return best


def drift(pin: str, models: list[dict] | None = None) -> str | None:
    """The newer slug of the pin's family, or None when the pin is current or unknown."""
    models = load() if models is None else models
    pin_ver = version(pin)
    top = newest(family(pin), models)
    if pin_ver is None or top is None:
        return None
    return top if _key(version(top)) > _key(pin_ver) else None


def client_version(path: Path | str | None = None) -> str | None:
    """Spec 047: the Codex version that wrote the cache (`client_version`), or None."""
    try:
        value = json.loads(Path(path or cache_path()).read_text(encoding="utf-8")).get("client_version")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value else None


def trust(path: Path | str | None, installed: str | None) -> str:
    """Spec 047 FR-002: `match` when the cache was written by the installed codex, `foreign` when by another
    version, `unknown` when either side is unknown. Only a matching cache is the installed CLI's catalog."""
    written = client_version(path)
    if written is None or not installed:
        return "unknown"
    return "match" if written == installed else "foreign"


def _usable(row: dict | None) -> bool:
    return bool(row) and row.get("visibility") == "list" and row.get("supported_in_api") is True


def pin_status(pin: str, models: list[dict] | None = None) -> str:
    """Spec 047 FR-003: `missing` when the catalog lacks the pin or lists it hidden or not API-supported,
    `drift` when a newer slug of its family is listed, else `ok`."""
    models = load() if models is None else models
    if not _usable(entry(pin, models)):
        return "missing"
    return "drift" if drift(pin, models) else "ok"
