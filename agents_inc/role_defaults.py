"""Shipped role and dispatch-gate defaults (D78, operator rulings of 2026-11-11) and their settings overlay (D80).

This module is the one named place for these defaults. The installer-managed block (`install/host_wiring.py`) and
the hook texts (`install/hook.py`) render from `resolve()`: the shipped defaults below, overlaid with the valid items of
the `roles` object in the agents-inc user settings file (`~/.config/agents-inc/settings.json`, the file that already
holds `agent_gate`). Routing data (`routing.json`) names models per rung; this module names what each rung is for.
The module constants keep the default rendering for callers that do not pass settings.
"""
from __future__ import annotations
import json
from pathlib import Path

# R1: role meaning per rung. The same meaning holds on the Claude and the Codex column.
RUNG_ROLES = {
    "executive": "judgment only",
    "orchestrator": "design or scope judgment, review, gates",
    "workhorse": "anything that writes: code, docs, git and PR mechanics",
    "grunt": "read-only: scouts, summaries, triage; writes no code",
}
# R1: the default rung for any task that writes. A code edit never defaults to the grunt rung.
WRITE_RUNG = "workhorse"
# R3: the model a Claude Code session gives a small edit through the native Agent tool.
NATIVE_EDIT_MODEL = "sonnet"
# R3: the tool-call count at or below which a task is small.
SMALL_TASK_CALLS = 3

# D80: the `roles` object in settings.json. Each item: default, then the allowed values (a tuple) or an int range.
SETTINGS_KEY = "roles"
CLAUDE_RUNG = {"fable": "executive", "opus": "orchestrator", "sonnet": "workhorse", "haiku": "grunt"}
DEFAULTS = {
    "write_rung": WRITE_RUNG,
    "grunt_read_only": True,
    "executive_judgment_only": True,
    "native_small_edit": True,
    "native_edit_model": NATIVE_EDIT_MODEL,
    "small_task_calls": SMALL_TASK_CALLS,
}
CHOICES = {
    "write_rung": ("workhorse", "orchestrator"),
    "grunt_read_only": (True, False),
    "executive_judgment_only": (True, False),
    "native_small_edit": (True, False),
    "native_edit_model": tuple(CLAUDE_RUNG),
    "small_task_calls": range(1, 11),
}

class Roles(dict):
    """Effective values. `sources[key]` is "default" or "settings"; `warnings` names each ignored item."""
    def __init__(self, values, sources, warnings):
        super().__init__(values); self.sources, self.warnings = sources, warnings

def _valid(key: str, value: object) -> bool:
    if key == "small_task_calls": return type(value) is int and value in CHOICES[key]
    return any(value is c if isinstance(c, bool) else (type(value) is str and value == c) for c in CHOICES[key])

def _allowed(key: str) -> str:
    choices = CHOICES[key]
    if isinstance(choices, range): return f"an integer {choices.start} to {choices.stop - 1}"
    return " | ".join(json.dumps(c) for c in choices)

def resolve(data: object = None, where: str = "settings") -> Roles:
    """Defaults overlaid with the valid items of data['roles']. Never raises. A missing or non-object `roles` gives
    all defaults; an unknown key, wrong type or out-of-range value is ignored with one warning naming the key."""
    values, sources, warnings = dict(DEFAULTS), {k: "default" for k in DEFAULTS}, []
    roles = data.get(SETTINGS_KEY) if isinstance(data, dict) else None
    if roles is None: return Roles(values, sources, warnings)
    if not isinstance(roles, dict):
        return Roles(values, sources, [f"{where} {SETTINGS_KEY}: not a JSON object; all role defaults used"])
    for key, value in roles.items():
        if key not in DEFAULTS:
            warnings.append(f"{where} {SETTINGS_KEY}.{key}: unknown key; ignored"); continue
        if not _valid(key, value):
            warnings.append(f"{where} {SETTINGS_KEY}.{key}: {json.dumps(value)} is not {_allowed(key)}; "
                            f"default {json.dumps(DEFAULTS[key])} used"); continue
        values[key], sources[key] = value, "settings"
    # A grunt edit model contradicts a read-only grunt rung: keep the default model.
    if values["native_edit_model"] == "haiku" and values["grunt_read_only"]:
        warnings.append(f"{where} {SETTINGS_KEY}.native_edit_model: \"haiku\" needs grunt_read_only false; "
                        f"default {json.dumps(NATIVE_EDIT_MODEL)} used")
        values["native_edit_model"], sources["native_edit_model"] = NATIVE_EDIT_MODEL, "default"
    return Roles(values, sources, warnings)

def load(settings: Path | None) -> Roles:
    """resolve() on a settings file. A missing file means all defaults and no warning; never raises."""
    try:
        if settings is None or not Path(settings).exists(): return resolve(None)
        data = json.loads(Path(settings).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Roles(dict(DEFAULTS), {k: "default" for k in DEFAULTS},
                     [f"settings {settings}: not readable JSON ({type(exc).__name__}); all role defaults used"])
    except Exception:
        return resolve(None)
    try: return resolve(data, f"settings {settings}")
    except Exception: return resolve(None)

def parse_value(key: str, raw: str) -> object:
    """Command-line text to a settings value; raises ValueError naming the allowed values."""
    if key not in DEFAULTS: raise ValueError(f"unknown role setting {key!r}; known: {', '.join(DEFAULTS)}")
    text = raw.strip()
    value: object = text
    if isinstance(DEFAULTS[key], bool):
        value = {"true": True, "false": False}.get(text.lower(), text)
    elif isinstance(DEFAULTS[key], int):
        try: value = int(text)
        except ValueError: pass
    if not _valid(key, value): raise ValueError(f"role setting {key} must be {_allowed(key)}: {raw!r}")
    return value

def _roles(r: dict | None) -> dict:
    return DEFAULTS if r is None else r

def rung_roles(r: dict | None = None) -> dict:
    r, out = _roles(r), dict(RUNG_ROLES)
    if not r["grunt_read_only"]: out["grunt"] = "scouts, summaries, triage, small mechanical edits"
    if not r["executive_judgment_only"]: out["executive"] = "judgment first; may write when a brief costs more than the edit"
    if r["write_rung"] == "orchestrator":
        out["orchestrator"] = "anything that writes, plus design or scope judgment, review, gates"
        out["workhorse"] = "writes only when a brief names it"
    return out

def executive_line(r: dict | None = None) -> str:
    if _roles(r)["executive_judgment_only"]:
        return ("Executive (fable, astra; talks to the operator): judgment only (dialogue, decisions, briefs, "
                "verification, acceptance); delegate all writing and anything a briefed orchestrator or workhorse can do.")
    return ("Executive (fable, astra; talks to the operator): judgment first (dialogue, decisions, briefs, verification, "
            "acceptance); it may write itself when a brief costs more than the edit, and delegates the rest.")

def roles_line(r: dict | None = None) -> str:
    r = _roles(r)
    grunt = ("grunt (haiku, luna) is read-only: scouts, summaries, triage." if r["grunt_read_only"] else
             "grunt (haiku, luna) does scouts, summaries, triage and small mechanical edits.")
    if r["write_rung"] == "orchestrator":
        return ("Rungs: orchestrator (opus, sol) writes code, docs, git and PRs and does design or scope judgment, "
                f"review, gates; workhorse (sonnet, terra) writes only when a brief names it; {grunt}")
    return ("Rungs: workhorse (sonnet, terra) writes code, docs, git and PRs; orchestrator (opus, sol) does design or "
            f"scope judgment, review, gates; {grunt}")

def native_edit(r: dict | None = None) -> str:
    """The native small-edit route as one noun phrase, or "" when every edit goes through dispatch."""
    r = _roles(r)
    if not r["native_small_edit"]: return ""
    model = r["native_edit_model"]
    return (f"an edit of {r['small_task_calls']} or fewer tool calls on a native {CLAUDE_RUNG[model]} subagent "
            f"(model {model}) with a short brief")

def gate_line(r: dict | None = None) -> str:
    r = _roles(r); n = r["small_task_calls"]
    if not r["native_small_edit"]:
        return (f"Gate: {n} or fewer tool calls, no writes: do it yourself; any edit, and anything larger: "
                "`agents-inc dispatch`.")
    model = r["native_edit_model"]
    return (f"Gate: {n} or fewer tool calls, no writes: do it yourself; {n} or fewer with edits: native "
            f"{CLAUDE_RUNG[model]} subagent (Claude Code: Agent, model {model}; Codex: native subagent), short brief, "
            "then one check yourself; larger: `agents-inc dispatch`.")

def show_lines(r: Roles) -> list[str]:
    """One line per item: key=value (default|settings)."""
    return [f"role {k}={json.dumps(r[k])} ({r.sources[k]})" for k in DEFAULTS]

ROUTE_LINE = "Route all delegation through agents-inc; never call another vendor's CLI or API directly; no paid API fallback."
EXECUTIVE_LINE = executive_line()
ROLES_LINE = roles_line()
GATE_LINE = gate_line()
