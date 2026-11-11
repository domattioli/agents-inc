"""Spec 038 T021/T024: guest agent types (native Claude Code subagent types answered by a non-Claude model).

`agents-inc native status|on|off|allow|begin|end|step`. `agents-inc luna ...` stays as it was (luna_native.py); here
`--model luna` hands status, on/off and begin/end to the same luna code, so both spellings agree.

status reads files only: no provider request and no child process (SC-006). A free-provider type is offered when it is
switched on, its key is in the key store and its tool-protocol probe passed within 7 days. Authorization is per
workspace and per provider (D76): begin and step refuse in a workspace with no record, before any provider call, with a
`needs-authorization` answer naming the provider, what is sent and the write directories.
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

from . import luna_native, native_http
from .free_launch import FREE_MODELS
from .hook import write_setting
from .paths import InstallPaths

FREE_PROVIDERS = ("gemini", "mistral", "openrouter")
# Providers with a built adapter (native_http.HOSTS). Mistral and OpenRouter come in slice 3.
BUILT_PROVIDERS = tuple(native_http.HOSTS)


def _free_nicknames() -> dict[str, dict]:
    """Nickname -> provider and slug for each models.json entry with a `nickname` whose slug is in FREE_MODELS and whose
    provider has an adapter. One nickname names one slug, so one vendor (P7)."""
    try:
        models = json.loads(Path(__file__).resolve().parents[1].joinpath("models.json").read_text(encoding="utf-8"))["models"]
    except (OSError, ValueError, KeyError):
        return {}
    out = {}
    for slug, spec in models.items():
        nick = spec.get("nickname") if isinstance(spec, dict) else None
        if isinstance(nick, str) and slug in FREE_MODELS and FREE_MODELS[slug].provider in BUILT_PROVIDERS:
            if nick in out: raise ValueError(f"models.json: nickname {nick!r} names two slugs")
            out[nick] = {"provider": FREE_MODELS[slug].provider, "slug": slug}
    return out


# Nickname -> provider and slug. luna's slug comes from the roster at run time.
NATIVE_MODELS: dict[str, dict] = {"luna": {"provider": "codex", "slug": None}, **_free_nicknames()}
ALLOW_FILE = "native-allow.json"
PROBE_FILE = "native-probes.json"
PROBE_TTL_S = 7 * 86400
SENDS = ("the whole conversation on every step: the task, the system prompt, the tool catalog and every tool result, "
         "including the contents of files the agent reads")
NEEDS_AUTH = "WB_NATIVE_NEEDS_AUTHORIZATION"
SWITCH_MODES = ("on", "off")


def model(nick: str) -> dict:
    if nick not in NATIVE_MODELS: raise ValueError(f"unknown guest agent model {nick!r}; one of: {', '.join(NATIVE_MODELS)}")
    entry = dict(NATIVE_MODELS[nick], nickname=nick)
    if entry["slug"] in FREE_MODELS: entry["max_input_chars"] = FREE_MODELS[entry["slug"]].max_input_chars
    return entry


def nick_for_provider(provider: str) -> str:
    for nick, entry in NATIVE_MODELS.items():
        if entry["provider"] == provider: return nick
    raise ValueError(f"no guest agent model for provider {provider!r}")


def _switch_key(nick: str) -> str: return f"native_type_{nick}"


def read_switch(paths: InstallPaths, nick: str) -> str:
    if nick == "luna": return luna_native.read_switch(paths)
    try:
        data = json.loads(paths.settings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "on"
    return "off" if isinstance(data, dict) and data.get(_switch_key(nick)) == "off" else "on"


def write_switch(paths: InstallPaths, nick: str, mode: str) -> None:
    if mode not in SWITCH_MODES: raise ValueError(f"switch must be one of {', '.join(SWITCH_MODES)}: {mode!r}")
    if nick == "luna": luna_native.write_switch(paths, mode)
    else: write_setting(paths, _switch_key(nick), mode)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh: fh.write(json.dumps(data, indent=1) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _real(p: str | Path) -> str: return os.path.realpath(os.path.expanduser(str(p)))


# Workspace authorization (D76, data-model WorkspaceAuthorization).
def allow(paths: InstallPaths, provider: str, workspace: str, write_dirs: list[str] | None = None, note: str = "") -> dict:
    if provider not in FREE_PROVIDERS: raise ValueError(f"authorization is for a free provider ({', '.join(FREE_PROVIDERS)}): {provider!r}")
    ws = _real(workspace)
    if not Path(ws).is_dir(): raise ValueError(f"workspace is not a directory: {workspace}")
    dirs = [_real(d if os.path.isabs(d) else os.path.join(ws, d)) for d in (write_dirs or [".scratch"])]
    record = {"workspace": ws, "provider": provider, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "write_dirs": dirs, "note": note}
    data = _read_json(paths.state / ALLOW_FILE)
    rows = [r for r in data.get("records", []) if isinstance(r, dict) and not (r.get("workspace") == ws and r.get("provider") == provider)]
    _write_json(paths.state / ALLOW_FILE, {"records": [*rows, record]})
    return record


def authorization(paths: InstallPaths, provider: str, cwd: str) -> dict | None:
    """The record covering cwd (the workspace itself or a directory inside it), or None."""
    here = _real(cwd)
    for r in _read_json(paths.state / ALLOW_FILE).get("records", []):
        if not isinstance(r, dict) or r.get("provider") != provider: continue
        ws = r.get("workspace")
        if isinstance(ws, str) and (here == ws or here.startswith(ws.rstrip(os.sep) + os.sep)): return r
    return None


def needs_authorization(nick: str, provider: str, cwd: str) -> dict:
    ws = _real(cwd)
    return {"status": "needs-authorization", "model": nick, "provider": provider, "workspace": ws, "sends": SENDS,
            "write_dirs": [os.path.join(ws, ".scratch")],
            "allow": f"agents-inc native allow {provider} --workspace {ws}"}


# Probe cache (T026 writes it; status only reads it).
def probe_record(paths: InstallPaths, nick: str) -> dict | None:
    rec = _read_json(paths.state / PROBE_FILE).get(nick)
    return rec if isinstance(rec, dict) else None


def probe_state(paths: InstallPaths, nick: str, now: float | None = None) -> tuple[str, str]:
    rec = probe_record(paths, nick)
    if rec is None: return "none", "no probe yet (agents-inc models probe)"
    at = rec.get("at_epoch")
    if not isinstance(at, (int, float)) or (now if now is not None else time.time()) - at >= PROBE_TTL_S:
        return "stale", "probe older than 7 days (agents-inc models probe)"
    if rec.get("result") != "pass": return "fail", f"probe {rec.get('result', 'fail')}: {rec.get('reason', '')}".rstrip(": ")
    return "pass", "probe passed"


def status_one(paths: InstallPaths, nick: str, cwd: str = ".") -> dict:
    entry = model(nick)
    if nick == "luna":
        report = luna_native.status(paths)
        return {**report, "nickname": nick, "provider": "codex", "kind": "thread"}
    switch = read_switch(paths, nick)
    has_key = native_http.read_key(paths.home, entry["provider"]) is not None
    probe, probe_reason = probe_state(paths, nick)
    record = authorization(paths, entry["provider"], cwd)
    authorized = record is not None
    if switch == "off": reason = f"switched off (agents-inc native on {nick})"
    elif not has_key: reason = f"no {entry['provider']} key in the key store (WB_NATIVE_KEY_MISSING)"
    elif probe != "pass": reason = probe_reason
    else: reason = "ready" if authorized else "ready; first start in this workspace asks for authorization"
    return {"nickname": nick, "provider": entry["provider"], "slug": entry["slug"], "kind": "stateless",
            "offered": switch == "on" and has_key and probe == "pass", "reason": reason, "switch": switch,
            "key": "present" if has_key else "missing", "probe": probe, "authorized": authorized,
            "write_dirs": list(record.get("write_dirs") or []) if record else [],
            "max_input_chars": entry.get("max_input_chars")}


def status_all(paths: InstallPaths, cwd: str = ".") -> dict:
    return {"models": [status_one(paths, nick, cwd) for nick in NATIVE_MODELS]}


def doctor_lines(paths: InstallPaths) -> list[str]:
    """One line per free guest agent model: offered, or why not (US2 scenario 3)."""
    out = []
    for nick in NATIVE_MODELS:
        if nick == "luna": continue
        s = status_one(paths, nick)
        out.append(f"{nick} type: {'ready' if s['offered'] else 'not offered'} ({s['reason']})")
    return out


def begin(paths, nick, session, agent, cwd, task) -> tuple[int, dict]:
    entry = model(nick)
    if nick == "luna": return 0, luna_native.begin(paths, session, agent, cwd, task)
    record = authorization(paths, entry["provider"], cwd)
    if record is None: return 3, needs_authorization(nick, entry["provider"], cwd)
    result = luna_native.begin(paths, session, agent, cwd, task, slug=entry["slug"], source=f"native-{entry['provider']}",
                               root=f"native-runs/{nick}")
    return 0, {**result, "write_dirs": list(record.get("write_dirs") or [])}


def end(paths, nick, session, agent, outcome, cwd, usage) -> dict:
    entry = model(nick)
    if nick == "luna": return luna_native.end(paths, session, agent, outcome, cwd, usage)
    return luna_native.end(paths, session, agent, outcome, cwd, usage, source=f"native-{entry['provider']}",
                           root=f"native-runs/{nick}")


STEP_TIMEOUT_S = 60.0


def step(paths: InstallPaths, nick: str, cwd: str, prompt: str, timeout: float | None, out=None, err=None,
         env: dict | None = None) -> int:
    """T024: one stateless step. Prompt from the caller (stdin), reply text on stdout, progress lines on stderr."""
    out, err = out or sys.stdout, err or sys.stderr
    try:
        entry = model(nick)
    except ValueError as exc:
        err.write(f"agents-inc native step: WB_NATIVE_UNKNOWN_MODEL: {exc}\n"); return native_http.EXIT_NOT_OFFERED
    provider = entry["provider"]
    if provider == "codex":
        err.write(f"agents-inc native step: {nick} is a thread model; it runs through agents-inc run\n"); return native_http.EXIT_USAGE
    if authorization(paths, provider, cwd) is None:
        err.write(f"agents-inc native step: {NEEDS_AUTH}: {json.dumps(needs_authorization(nick, provider, cwd))}\n")
        return native_http.EXIT_NOT_OFFERED
    key = native_http.read_key(paths.home, provider)
    try:
        if len(prompt) > entry["max_input_chars"]:
            raise native_http.StepError(native_http.EXIT_USAGE, f"WB_NATIVE_CONTEXT_OVER: context over {entry['max_input_chars']} chars (prompt {len(prompt)} chars); not sent")
        if key is None:
            raise native_http.StepError(native_http.EXIT_NOT_OFFERED, f"WB_NATIVE_KEY_MISSING: no {provider} key in {native_http.key_store(Path('~'))}")
        native_http.progress(err, "record", {"model": nick, "slug": entry["slug"], "provider": provider})
        native_http.progress(err, "event", {"kind": "status", "text": f"{nick}: request sent to {entry['slug']}"})
        text, usage = native_http.ask(provider, entry["slug"], prompt, key, max_chars=entry["max_input_chars"],
                                      timeout=timeout or STEP_TIMEOUT_S, env=env)
    except native_http.StepError as exc:
        err.write(f"agents-inc native step: {native_http.scrub(exc.text, key)}\n")
        return exc.code
    native_http.progress(err, "usage", usage)
    out.write(native_http.scrub(text, key))
    out.flush()
    return 0


def run_cli(paths: InstallPaths, args) -> int:
    verb = args.verb
    try:
        if verb in SWITCH_MODES:
            target = args.target or args.model
            if not target: raise ValueError(f"native {verb} needs a nickname or all")
            for nick in (NATIVE_MODELS if target == "all" else [model(target)["nickname"]]):
                write_switch(paths, nick, verb)
                print(f"{nick} type: {verb}")
            return 0
        if verb == "allow":
            provider = args.target or args.provider
            if not provider: raise ValueError("native allow needs a provider")
            print(json.dumps(allow(paths, provider, args.workspace or args.cwd, args.write_dir)))
            return 0
        nick = args.model or (nick_for_provider(args.provider) if args.provider else None)
        if verb == "status":
            if nick is None:
                report = status_all(paths, args.cwd)
                if args.json: print(json.dumps(report))
                else:
                    for m in report["models"]: print(f"{m['nickname']}: {'offered' if m['offered'] else 'not offered'} ({m['reason']})")
                return 0
            if nick == "luna" and not args.json: return luna_native.run(paths, "status", False)
            report = status_one(paths, nick, args.cwd)
            print(json.dumps(report) if args.json else f"offered: {'yes' if report['offered'] else 'no'} ({report['reason']})")
            return 0
        if nick is None: raise ValueError(f"native {verb} needs --model or --provider")
        if verb == "step":
            return step(paths, nick, args.cwd, sys.stdin.read(), args.timeout)
        if not args.session or not args.agent: raise ValueError(f"native {verb} needs --session and --agent")
        if verb == "begin":
            code, result = begin(paths, nick, args.session, args.agent, args.cwd, args.task)
            print(json.dumps(result))
            return code
        if not args.outcome: raise ValueError("native end needs --outcome")
        parsed = json.loads(args.usage) if args.usage else {}
        if not isinstance(parsed, dict): raise ValueError("--usage must be a JSON object")
        print(json.dumps(end(paths, nick, args.session, args.agent, args.outcome, args.cwd, parsed)))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"agents-inc native {verb}: {exc}", file=sys.stderr)
        return 2
