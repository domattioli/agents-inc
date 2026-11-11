"""Spec 038 T026: the tool-use probe for a free guest agent model.

One synthetic request per model: a catalog with one Read tool and the task "Read the file probe.txt". The probe
passes when the parsed reply names Read in "tools". No workspace content is sent (no authorization record needed).
The result goes to native-probes.json (mode 0600); `native status` reads it, and a type is offered with tools only after a pass
younger than PROBE_TTL_S. Run by `agents-inc models probe [nick]` and `agents-inc doctor --probe`, never at session start.
"""
from __future__ import annotations

import json
import sys
import time

from . import native, native_http
from .paths import InstallPaths

PROBE_PROMPT = (
    "You drive an agent loop with real tools. To run a tool, name it in \"tools\"; the host runs it.\n"
    "Reply with exactly one JSON object and nothing else:\n"
    "{\"say\": \"<short text>\", \"tools\": [{\"name\": \"<tool from the catalog>\", \"input\": {...}}]}\n\n"
    "Tools:\n- Read: Reads a file.\n  Arguments: { file_path: string }\n\n"
    "Conversation:\nuser: Read the file probe.txt.\n"
)
PROBE_TIMEOUT_S = 60.0


def _names_read(text: str) -> bool:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start: return False
    try:
        reply = json.loads(text[start:end + 1])
    except ValueError:
        return False
    tools = reply.get("tools") if isinstance(reply, dict) else None
    return isinstance(tools, list) and any(isinstance(t, dict) and t.get("name") == "Read" for t in tools)


def probe_one(paths: InstallPaths, nick: str, env: dict | None = None, now: float | None = None) -> dict:
    """Probe one model and store the result. Never raises for a provider failure: the record says why."""
    entry = native.model(nick)
    if entry["provider"] == "codex": raise ValueError(f"{nick} is not a free guest agent model")
    rec = {"result": "unavailable", "at_epoch": now if now is not None else time.time(), "slug": entry["slug"], "reason": ""}
    key = native_http.read_key(paths.home, entry["provider"])
    if key is None:
        rec["reason"] = f"no {entry['provider']} key (WB_NATIVE_KEY_MISSING; checked {', '.join(native_http.key_places(entry['provider']))})"
    else:
        try:
            text, _ = native_http.ask(entry["provider"], entry["slug"], PROBE_PROMPT, key,
                                      max_chars=entry["max_input_chars"], timeout=PROBE_TIMEOUT_S, env=env)
            ok = _names_read(text)
            rec.update(result="pass" if ok else "fail", reason="reply named Read" if ok else "reply did not name Read in tools")
        except native_http.StepError as exc:
            # fail means the model answered without following the protocol; any other failed attempt is unavailable.
            rec["result"] = "quota-paused" if exc.code == native_http.EXIT_QUOTA else "unavailable"
            rec["reason"] = native_http.scrub(exc.text, key)[:300]
    data = native._read_json(paths.state / native.PROBE_FILE)
    old = data.get(nick)
    if rec["result"] in ("unavailable", "quota-paused") and isinstance(old, dict) and old.get("result") == "pass" \
            and isinstance(old.get("at_epoch"), (int, float)) and rec["at_epoch"] - old["at_epoch"] < native.PROBE_TTL_S:
        # One busy moment at the provider must not hide a working type: keep the pass (and its time).
        data[nick] = {**old, "last_attempt": rec}
    else:
        data[nick] = rec
    native._write_json(paths.state / native.PROBE_FILE, data)
    return rec


def run(paths: InstallPaths, target: str | None, out=None, env: dict | None = None) -> int:
    out = out or sys.stdout
    nicks = [n for n, m in native.NATIVE_MODELS.items() if m["provider"] != "codex"] if target in (None, "all") else [target]
    code = 0
    for nick in nicks:
        try:
            rec = probe_one(paths, nick, env=env)
        except ValueError as exc:
            out.write(f"{nick} probe: error: {exc}\n"); code = 2; continue
        out.write(f"{nick} probe: {rec['result']} ({rec['reason']})\n")
        if rec["result"] != "pass": code = code or 1
    return code
