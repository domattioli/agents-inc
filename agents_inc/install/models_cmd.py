"""D52: `agents-inc models` lists Codex pins against the local catalog; `models bump` moves one pin."""
from __future__ import annotations
import json
import sys
from pathlib import Path

from . import catalog
from .runtime import MODEL_ALIASES

AGENTS_DIR = Path(__file__).resolve().parents[1]
ROUTING = AGENTS_DIR / "routing.json"
MODELS = AGENTS_DIR / "models.json"
ORDER = ("luna", "terra", "sol", "astra")


def _trust() -> tuple[str, str | None, str | None]:
    """Spec 047 FR-002: (trust, cache client_version, installed codex version)."""
    from . import host_cli
    installed = host_cli.installed_version("codex")
    return catalog.trust(catalog.cache_path(), installed), catalog.client_version(), installed


def listing(models: list[dict] | None = None, aliases: dict[str, str] | None = None,
            trust: tuple[str, str | None, str | None] | None = None) -> list[str]:
    """Spec 047 (D52.1): verdicts (ok, DRIFT, NOT-IN-CATALOG) only from a catalog matching the installed codex and
    holding a readable model list; a well-formed empty list means every pin is NOT-IN-CATALOG. Otherwise each pin is
    `unchecked` and a note line says why."""
    aliases = MODEL_ALIASES if aliases is None else aliases
    models = catalog.load() if models is None else models  # None: missing or unreadable
    state = trust[0] if trust else None
    checked = state == "match" and models is not None
    lines = []
    for alias in sorted(aliases, key=lambda a: ORDER.index(a) if a in ORDER else len(ORDER)):
        pin = aliases[alias]
        top = catalog.newest(catalog.family(pin), models or [])
        label = {"drift": "DRIFT", "ok": "ok"}.get(catalog.pin_status(pin, models), "NOT-IN-CATALOG") if checked else "unchecked"
        lines.append(f"{alias} pinned {pin} newest {top or 'unknown'} {label}")
    if state == "foreign":
        lines.append(f"note: catalog written by codex {trust[1]}, installed {trust[2]}; not checked. Update the CLI first, then `codex debug models` refreshes the catalog")
    elif state == "unknown":
        lines.append("note: catalog version unknown; not checked")
    elif state == "match" and models is None:
        lines.append("note: no readable model list in models_cache.json; not checked")
    return lines


def _dump(obj, indent: int = 0) -> str:
    """Match models.json formatting: objects one key per line (2 spaces), every other value inline."""
    if isinstance(obj, dict) and obj:
        pad = " " * (indent + 2)
        body = ",\n".join(f"{pad}{json.dumps(k)}: {_dump(v, indent + 2)}" for k, v in obj.items())
        return "{\n" + body + "\n" + " " * indent + "}"
    return json.dumps(obj)


def _refuse(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def bump(alias: str | None, slug: str | None, routing: Path = ROUTING, models_json: Path = MODELS,
         models: list[dict] | None = None, aliases: dict[str, str] | None = None,
         settings: Path | None = None, unpin: bool = False,
         trust: tuple[str, str | None, str | None] | None = None) -> int:
    """An explicit slug also records a manual pin (settings "pinned") so model_sync never auto-promotes it;
    unpin=True only removes the pin. A bump to the catalog's newest (no slug) does not pin."""
    from agents_inc import model_sync
    settings = model_sync.DEFAULT_SETTINGS if settings is None else settings
    aliases = MODEL_ALIASES if aliases is None else aliases
    if alias not in aliases:
        return _refuse(f"unknown Codex alias: {alias}")
    if unpin:
        try:
            model_sync.set_pinned(settings, alias, False)
        except ValueError as exc:
            return _refuse(str(exc))
        print(settings)
        return 0
    if slug:
        try:
            model_sync.check_settings_writable(settings)  # refuse before touching routing/models
        except ValueError as exc:
            return _refuse(str(exc))
    if not trust or trust[0] != "match":  # spec 047 D52.1: only a catalog matching the installed codex approves a pin
        if trust and trust[0] == "foreign":
            return _refuse(f"catalog written by codex {trust[1]}, installed {trust[2]}; update the CLI first, then `codex debug models`")
        return _refuse("catalog version unknown or installed codex version not known; pin not changed (unpin still works)")
    models = catalog.load() if models is None else models
    pin = aliases[alias]
    target = slug or catalog.drift(pin, models)
    if not target:
        return _refuse(f"no newer slug than {pin} for {alias}")
    row = catalog.entry(target, models)
    if not row or row.get("visibility") != "list" or row.get("supported_in_api") is not True:
        return _refuse(f"{target} is not a listed, API-supported catalog entry")
    if target == pin:
        return _refuse(f"{alias} is already pinned to {pin}")
    if catalog.family(target) != alias:
        return _refuse(f"{target} is not in the {alias} family")
    efforts = [level["effort"] for level in row.get("supported_reasoning_levels", []) if isinstance(level, dict) and "effort" in level]
    if not efforts:
        return _refuse(f"{target} has no supported_reasoning_levels in the catalog")
    routing_text = Path(routing).read_text(encoding="utf-8")
    needle = f'"codex": "{pin}"'
    if routing_text.count(needle) != 1:
        return _refuse(f"expected exactly one {needle} in {routing}, found {routing_text.count(needle)}")
    data = json.loads(Path(models_json).read_text(encoding="utf-8"))
    table = data["models"]
    if target in table:
        table[target]["supported_efforts"] = efforts
    elif pin in table:
        new_row = dict(table[pin])
        new_row["supported_efforts"] = efforts
        rebuilt = {}
        for key, value in table.items():
            rebuilt[key] = value
            if key == pin:
                rebuilt[target] = new_row  # new entry sits right after the one it was copied from
        data["models"] = rebuilt
    else:
        return _refuse(f"models.json has no entry for {pin} to copy")
    Path(routing).write_text(routing_text.replace(needle, f'"codex": "{target}"'), encoding="utf-8")
    Path(models_json).write_text(_dump(data) + "\n", encoding="utf-8")
    print(routing)
    print(models_json)
    if slug:
        model_sync.set_pinned(settings, alias, True)
        print(settings)
    return 0


CHAIN_KEYS = ("supervisor", "executive")
CHAIN_WORDS = ("CoS", "operator")


def chain(pairs: list[str] | None = None, clear: bool = False, settings: Path | str | None = None) -> int:
    """List or set the default REPORTING CHAIN seats (settings key `chain`). Values: model aliases, CoS, operator."""
    from agents_inc import model_sync
    from . import dispatch
    rungs = dispatch._load("dispatch_rungs")
    settings = model_sync.DEFAULT_SETTINGS if settings is None else settings
    if clear and pairs:
        return _refuse("chain --clear takes no key=alias pairs")
    updates = {}
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep or key not in CHAIN_KEYS:
            return _refuse(f"expected supervisor=<alias> or executive=<alias>, got {pair!r}")
        if value not in rungs.MODEL_RUNG and value not in CHAIN_WORDS:
            return _refuse(f"unknown chain value {value!r}; use one of {', '.join(sorted(rungs.MODEL_RUNG))}, CoS, operator")
        updates[key] = value
    try:
        if clear and Path(settings).exists():
            model_sync._update_settings(settings, lambda data: data.pop("chain", None))
        elif updates:
            def change(data):
                cfg = data.get("chain") if isinstance(data.get("chain"), dict) else {}
                cfg.update(updates)
                data["chain"] = cfg
            model_sync._update_settings(settings, change)
        data = model_sync._read_settings(settings)
    except ValueError as exc:
        return _refuse(str(exc))
    cfg = data.get("chain") if isinstance(data.get("chain"), dict) else {}
    for vendor in ("claude", "codex"):
        aliases = [a for rung in rungs.LADDER for a, r in rungs.MODEL_RUNG.items()
                   if r == rung and rungs.ALIAS_VENDOR[a] == vendor]
        print(f"{vendor} ladder " + " < ".join(aliases))
    for key in CHAIN_KEYS:
        value = cfg.get(key)
        print(f"{key} {value} setting" if value else f"{key} ladder ladder")
    return 0


def run(verb: str | None, alias: str | None = None, slug: str | None = None, unpin: bool = False,
        extra: list[str] | None = None, clear: bool = False) -> int:
    if verb == "chain":
        return chain([a for a in (alias, slug, *(extra or [])) if a], clear=clear)
    if verb == "bump":
        return bump(alias, slug, unpin=unpin, trust=None if unpin else _trust())
    lines = listing(trust=_trust())
    for line in lines:
        print(line)
    return 1 if any(line.endswith(" NOT-IN-CATALOG") for line in lines) else 0
