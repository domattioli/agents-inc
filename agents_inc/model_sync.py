"""Promote codex persona slugs in routing.json when a newer version shows up in the codex cache.

Default scope is Claude + OpenAI only: codex promotion, tier-table regen (on --apply).
The OpenRouter catalog refresh runs only when --openrouter is passed. Stdlib only. Never downgrades.
routing.json is edited as text (only the codex slug on the tier's own line changes, so the
hand-aligned layout survives). models.json gets a cloned entry for the new slug; the old entry stays.

Update approval: the user setting model_updates ("auto" or "approve", default "approve") decides
whether a scheduled run applies detected updates unattended (--scheduled) or parks them in a
pending file until the operator runs --approve. Settings live in ~/.config/agents-inc/settings.json.
"""
import argparse
import copy
import datetime
import json
import os
import re
import stat
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

SLUG_RE = re.compile(r"^gpt-(\d+(?:\.\d+)*)-(astra|sol|terra|luna)$")
PERSONA_TIER = {"astra": "executive", "sol": "orchestrator", "terra": "workhorse", "luna": "grunt"}
PERSONA_ORDER = ("astra", "sol", "terra", "luna")

MODES = ("auto", "approve")
PINNED_LINE = "codex {}: pinned, skipped"

DEFAULT_CACHE = os.path.join(os.path.expanduser("~"), ".codex", "models_cache.json")
DEFAULT_ROUTING = os.path.join(_HERE, "routing.json")
DEFAULT_MODELS = os.path.join(_HERE, "models.json")
DEFAULT_SETTINGS = os.path.join(os.path.expanduser("~"), ".config", "agents-inc", "settings.json")
DEFAULT_PENDING = os.path.join(os.path.expanduser("~"), ".config", "agents-inc", "pending-model-update.json")


def _version(text):
    # Trailing zero components do not change a version: 6.0 == 6, 6.1.0 == 6.1.
    parts = [int(part) for part in text.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _codex_line_pattern(tier):
    # Matches the codex value on the same line as the tier key; group 2 is the slug.
    return re.compile(r'("%s"\s*:\s*\{[^\n}]*?"codex"\s*:\s*")([^"\n]*)(")' % re.escape(tier))


def _replace_codex(text, tier, new_slug):
    """Return (new_text, matched). Only the slug between the quotes changes, and only inside the top-level "tiers" object."""
    anchor = re.search(r'"tiers"\s*:\s*\{', text)
    if not anchor:
        return text, False
    head, tail = text[:anchor.end()], text[anchor.end():]
    pattern = _codex_line_pattern(tier)
    new_tail, count = pattern.subn(lambda m: m.group(1) + new_slug + m.group(3), tail, count=1)
    return head + new_tail, count == 1


def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    mode = None
    if os.path.exists(path):
        mode = stat.S_IMODE(os.stat(path).st_mode)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if mode is not None:
            os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _slug_version(slug):
    match = SLUG_RE.match(slug)
    return _version(match.group(1)) if match else ()


SKIP_LINE = "model_sync: skipped, models_cache.json from codex {}, installed {}"


def _best_by_persona(cache):
    best = {}
    for entry in cache.get("models", []):
        slug = entry.get("slug") if isinstance(entry, dict) else None
        if not isinstance(slug, str):
            continue
        # Spec 047 (D52): only entries explicitly listed and API-supported, the rule catalog.newest and pin_status use.
        if entry.get("visibility") != "list" or entry.get("supported_in_api") is not True:
            continue
        match = SLUG_RE.match(slug)
        if not match:
            continue
        persona = match.group(2)
        version = _version(match.group(1))
        if persona not in best or version > best[persona][0]:
            best[persona] = (version, slug)
    return best


def sync_codex(cache_path, routing_path, models_path, apply=False, pinned=(), installed=None):
    """Promote newer codex persona slugs. Returns report lines (empty when nothing to change).
    Personas in `pinned` (operator manual pins) are never promoted or cloned; heal still runs.
    Spec 047: with `installed` (the codex CLI version), a cache written by another codex version is skipped."""
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)
    written = cache.get("client_version") if isinstance(cache, dict) else None
    if not installed:  # spec 047 D52.1: promotion needs a catalog matching the installed codex
        return ["model_sync: skipped, installed codex version unknown; catalog not checked"]
    if not written:
        return ["model_sync: skipped, models_cache.json catalog version unknown (no client_version); catalog not checked"]
    if written != installed:
        return [SKIP_LINE.format(written, installed)]
    best = _best_by_persona(cache)

    with open(routing_path, "r", encoding="utf-8", newline="") as f:
        routing_text = f.read()
    tiers = json.loads(routing_text).get("tiers", {})

    lines = []
    new_routing_text = routing_text
    promotions = []  # (persona, tier, old_slug, new_slug)
    for persona in PERSONA_ORDER:
        if persona not in best:
            continue
        tier = PERSONA_TIER[persona]
        current = tiers.get(tier, {}).get("codex")
        if not current:
            continue
        new_version, new_slug = best[persona]
        match = SLUG_RE.match(current)
        current_version = _version(match.group(1)) if match else ()
        if new_version <= current_version or new_slug == current:
            continue
        if persona in pinned:
            lines.append(PINNED_LINE.format(persona))
            continue
        new_routing_text, matched = _replace_codex(new_routing_text, tier, new_slug)
        if not matched:
            lines.append("codex {}: routing line for tier {} not found, skipped".format(persona, tier))
            continue
        promotions.append((persona, tier, current, new_slug))

    with open(models_path, "r", encoding="utf-8") as f:
        models_text = f.read()
    catalog = json.loads(models_text)
    models = catalog.setdefault("models", {})
    models_changed = False

    suffix = " [applied]" if apply else " [dry-run]"
    for persona, tier, old_slug, new_slug in promotions:
        lines.append("codex {}: {} -> {}{}".format(persona, old_slug, new_slug, suffix))
        if new_slug in models:
            continue
        if old_slug not in models:
            lines.append("models: no entry for {}, {} not added to models.json".format(old_slug, new_slug))
            continue
        models[new_slug] = copy.deepcopy(models[old_slug])
        models_changed = True
        lines.append("models: added {} (clone of {}, tier {}){}".format(new_slug, old_slug, tier, suffix))

    # Heal: every post-promotion routing codex slug must have a models.json entry.
    tiers_after = json.loads(new_routing_text).get("tiers", {})
    for tier, info in tiers_after.items():
        slug = info.get("codex") if isinstance(info, dict) else None
        if not slug or slug in models:
            continue
        donors = [
            (name, entry) for name, entry in models.items()
            if isinstance(entry, dict) and entry.get("provider") == "codex" and entry.get("tier") == tier
        ]
        if not donors:
            lines.append("WARN: no codex donor in tier {} for {}, {} not added to models.json".format(tier, slug, slug))
            continue
        donor = max(donors, key=lambda item: _slug_version(item[0]))[0]
        models[slug] = copy.deepcopy(models[donor])
        models_changed = True
        lines.append("models: added {} (clone of {}, tier {}){}".format(slug, donor, tier, suffix))

    if apply:
        if new_routing_text != routing_text:
            _atomic_write(routing_path, new_routing_text)
        if models_changed:
            # One serializer for models.json (models_cmd._dump), so the two writers never reformat each other.
            from agents_inc.install.models_cmd import _dump
            _atomic_write(models_path, _dump(catalog) + "\n")
    return lines


def load_mode(settings_path):
    """Return "auto" or "approve". Missing file, bad JSON, or any other value gives "approve"."""
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return "approve"
    value = data.get("model_updates") if isinstance(data, dict) else None
    return value if value in MODES else "approve"


def load_pinned(settings_path):
    """Personas the operator pinned by hand. Missing or bad file, or bad value, gives []."""
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    value = data.get("pinned") if isinstance(data, dict) else None
    return [p for p in value if p in PERSONA_TIER] if isinstance(value, list) else []


def set_pinned(settings_path, persona, on):
    """Add (on) or remove a manual pin, keeping every other key. ValueError on a bad persona or corrupt file."""
    if persona not in PERSONA_TIER:
        raise ValueError("pinned persona must be one of {}, got {!r}".format(PERSONA_ORDER, persona))

    def change(data):
        current = data.get("pinned")
        current = [p for p in current if p != persona] if isinstance(current, list) else []
        data["pinned"] = current + [persona] if on else current
    _update_settings(settings_path, change)


def check_settings_writable(settings_path):
    """Raise ValueError if the settings file exists but is not a JSON object (it would not be overwritten)."""
    _read_settings(settings_path)


def _read_settings(settings_path):
    data = {}
    if os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except ValueError as exc:
                raise ValueError("settings file is not valid JSON, not overwritten: {}".format(exc))
        if not isinstance(data, dict):
            raise ValueError("settings file is not a JSON object, not overwritten: {}".format(settings_path))
    return data


def _update_settings(settings_path, change):
    data = _read_settings(settings_path)
    change(data)
    _atomic_write(settings_path, json.dumps(data, indent=2) + "\n")


def set_mode(settings_path, mode):
    """Persist model_updates, keeping every other key. Raises ValueError on a bad mode or a corrupt file."""
    if mode not in MODES:
        raise ValueError("model_updates must be one of {}, got {!r}".format(MODES, mode))
    _update_settings(settings_path, lambda data: data.__setitem__("model_updates", mode))


def run_scheduled(cache, routing, models, settings_path, pending_path, installed=None):
    """Unattended pass. Returns (status, lines): none | applied | pending | skipped (catalog not trusted; any pending
    proposal is kept)."""
    pinned = load_pinned(settings_path)
    proposal = sync_codex(cache, routing, models, apply=False, pinned=pinned, installed=installed)
    if _skipped(proposal):
        return "skipped", proposal
    if not _has_changes(proposal):
        _remove(pending_path)
        return "none", proposal
    if load_mode(settings_path) == "auto":
        applied = sync_codex(cache, routing, models, apply=True, pinned=pinned, installed=installed)
        _remove(pending_path)
        return "applied", applied
    payload = {
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "lines": proposal,
    }
    _atomic_write(pending_path, json.dumps(payload, indent=2) + "\n")
    return "pending", proposal


def _skipped(lines):
    return bool(lines) and lines[0].startswith("model_sync: skipped,")


def _has_changes(lines):
    return any(not line.endswith(": pinned, skipped") and not line.startswith("model_sync: skipped,") for line in lines)


def approve_pending(cache, routing, models, pending_path, settings_path=None, installed=None):
    """Operator approval: apply the current codex sync, then clear the pending file."""
    pinned = load_pinned(settings_path) if settings_path else []
    lines = sync_codex(cache, routing, models, apply=True, pinned=pinned, installed=installed)
    if _skipped(lines):
        return lines  # spec 047 G2: nothing applied, so the proposal stays pending
    _remove(pending_path)
    return lines


def _regen_tables():
    script = os.path.join(_REPO_ROOT, "skills", "workerbee", "scripts", "gen_tier_tables.py")
    proc = subprocess.run(
        [sys.executable, script, "--write"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        detail = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part)
        print("model_sync: tier tables failed (exit {}):\n{}".format(proc.returncode, detail), file=sys.stderr)
        return 1
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -m agents_inc.model_sync",
        description="Promote codex persona slugs. Default scope is Claude + OpenAI only; "
                    "the OpenRouter refresh runs only with --openrouter.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cache", default=DEFAULT_CACHE)
    parser.add_argument("--routing", default=DEFAULT_ROUTING)
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS)
    parser.add_argument("--pending", default=DEFAULT_PENDING)
    parser.add_argument("--openrouter", action="store_true",
                        help="also refresh models.json against the OpenRouter catalog (opt-in)")
    parser.add_argument("--skip-tables", action="store_true")
    parser.add_argument("--scheduled", action="store_true",
                        help="unattended pass: apply if model_updates is auto, else write a pending file")
    parser.add_argument("--approve", action="store_true",
                        help="apply the pending update and clear the pending file")
    parser.add_argument("--set-mode", choices=MODES, help="set model_updates in the settings file")
    parser.add_argument("--get-mode", action="store_true", help="print model_updates")
    args = parser.parse_args(argv)

    settings_path = os.path.expanduser(args.settings)
    pending_path = os.path.expanduser(args.pending)

    if args.get_mode:
        print(load_mode(settings_path))
        return 0
    if args.set_mode:
        try:
            set_mode(settings_path, args.set_mode)
        except ValueError as exc:
            print("model_sync: {}".format(exc), file=sys.stderr)
            return 2
        print("model_sync: model_updates = {}".format(args.set_mode))
        return 0

    cache_path = os.path.expanduser(args.cache)
    if not os.path.exists(cache_path):
        print("model_sync: codex cache missing: {}".format(cache_path), file=sys.stderr)
        return 2

    from agents_inc.install import host_cli  # spec 047: trust the cache only when written by the installed codex
    installed = host_cli.installed_version("codex")
    if args.scheduled:
        status, lines = run_scheduled(cache_path, args.routing, args.models, settings_path, pending_path, installed)
        for line in lines:
            print(line)
        if status == "applied":
            if not args.skip_tables and _regen_tables():
                return 1
            print("model_sync: changes applied")
        elif status == "pending":
            print("model_sync: pending approval (run: python3 -m agents_inc.model_sync --approve)")
        return 0

    if args.approve:
        lines = approve_pending(cache_path, args.routing, args.models, pending_path, settings_path, installed)
        for line in lines:
            print(line)
        if _skipped(lines):
            return 1  # spec 047 G2: approval applied nothing; the pending file is kept
        if _has_changes(lines):
            if not args.skip_tables and _regen_tables():
                return 1
            print("model_sync: changes applied")
        return 0

    codex_lines = sync_codex(cache_path, args.routing, args.models, apply=args.apply, pinned=load_pinned(settings_path),
                             installed=installed)
    for line in codex_lines:
        print(line)

    if args.openrouter:
        try:
            from agents_inc import catalog_refresh
            refresh_lines = catalog_refresh.refresh(apply=args.apply, models_path=args.models)
        except Exception as exc:
            print("model_sync: openrouter skipped: {}".format(exc), file=sys.stderr)
        else:
            for line in refresh_lines:
                print(line)

    if args.apply and not args.skip_tables and _regen_tables():
        return 1
    if args.apply and any(line.endswith("[applied]") for line in codex_lines):
        print("model_sync: changes applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
