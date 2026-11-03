"""Host hook entry points. Advisory, except the FR-002 persona deny and the opt-in agent gate deny; never break a session, always exit 0."""
from __future__ import annotations
import hashlib, json, os, re, sys, tempfile, time
from datetime import datetime
from .doctor import check_install
from .paths import InstallPaths

# The rung is the model; the route is always `agents-inc dispatch` (D59, QUICKREF step 2). The earlier wording
# ("keep this Agent call only if routing selects a Claude rung") approved every Agent call on a Claude-only
# install, since sonnet and haiku are Claude rungs (token bench dry run, 2026-10-22).
NUDGE = ("agents-inc reminder: this Agent call bypasses agents-inc routing, the ledger and verification. Use Agent "
         "only for a read-only foreground scout (Explore, Plan). Any other delegation, including to a Claude rung "
         "such as sonnet or haiku, goes through `agents-inc dispatch --slots <json> --model <rung>`: naming a model "
         "picks the rung, not the route.")
ROUTE_RULE = ("Naming a model (opus, sonnet, haiku) picks the rung, not the route: delegate through "
              "`agents-inc dispatch`, and use the Agent tool only for read-only foreground scouts (Explore, Plan).")
# Spec 015 FR-002: a Codex persona name at the start of a Claude subagent description mislabels the model.
PERSONA_RE = re.compile(r"(?i)\A(?:astra|sol|terra|luna)(?=\s|:|/|\Z)")
PERSONA_DENY_REASON = ("FR-002: Agent/Task descriptions cannot begin with a Codex persona name. For Codex execution, "
                       "dispatch through agents-inc; Agent/Task creates Claude subagents. If this names a product, "
                       "repository, person, or supervised worker, put the actual Claude rung first and mention that "
                       "name later. Renaming does not change the execution model.")
AGENT_TOOLS = {"Agent", "Task"}
AGENT_GATE_ENV = "AGENTS_INC_AGENT_GATE"
AGENT_GATE_MODES = ("enforce", "advisory", "off")
GATE_ALLOW = frozenset({"Explore", "Plan", "claude-code-guide", "statusline-setup"})
# The agents-inc mod's native agent types run a Codex model through `agents-inc run` (spec 028): the persona name is
# the true model and the call is agents-inc's own route, so neither the FR-002 deny nor the gate applies. Exact names,
# not a prefix: a lookalike such as x-agents-inc:luna is still an outside spawn. The spike's luna-brain:* types are
# no longer exempt; the spike mod stays installable but its types now meet the gate like any other.
NATIVE_TYPES = frozenset({"agents-inc:luna"})
GATE_DENY_REASON = ("agents-inc agent gate: this Agent/Task call is blocked (subagent_type: {subagent}; background: {background}). "
                    "Agent/Task spawns Claude subagents outside agents-inc routing, ledger, and verification. Allowed here: {allowed} "
                    "(foreground only). For every other delegation run: agents-inc dispatch --slots <json> --model <opus|sonnet|haiku|fable>. "
                    "Naming a model picks the rung, not the route. Per-session bypass: start the session with "
                    "AGENTS_INC_AGENT_GATE=off claude. Switch to advisory: agents-inc repair --agent-gate advisory.")
FAN_OUT = "agents-inc: fan-out"
INFLIGHT_TTL_S = 7200  # a spawn that never reports done stops warning after 2 h
DISPATCH_RE = re.compile(r"agents-inc\s+dispatch|\b(?:gask|mask|oask|agent)\.sh\b|\bcodex\s+exec\b")
DELEGATE_RE = re.compile(r"\Amcp__.*__DelegateAgent\Z")
QUICKREF_HEADER = ("agents-inc quickref (skills/workerbee/QUICKREF.md, loaded once per session on first dispatch; full "
                   "SKILL.md still required for non-Claude rungs, prompts from scratch, or disputed gates):")

def session_start(paths: InstallPaths, host: str) -> str:
    report = check_install(paths)
    status = "READY" if report.ready else " ".join(report.codes)
    skill = paths.current / "skills/workerbee/QUICKREF.md"
    text = (f"agents-inc is installed (doctor: {status}). Every delegation in this session routes through agents-inc; "
            f"read {skill} before the first dispatch (full SKILL.md only for a non-Claude rung, a prompt from scratch, "
            f"or a disputed gate). {ROUTE_RULE} Launcher: {paths.launcher}.")
    if not report.ready: text += " Tell the operator doctor is not READY and suggest `agents-inc repair --source <agents_Inc checkout>`."
    for warning in report.warnings:
        # An install made --without-codex reports WB_CLI_NOT_FOUND as a warning; say what it means so a session
        # does not read "CLI not found" as "dispatch is broken" and avoid it.
        text += (" Codex is not installed (WB_CLI_NOT_FOUND): Codex rungs are unavailable; Claude rungs dispatch normally."
                 if warning == "WB_CLI_NOT_FOUND" else f" WARNING: {warning}.")
    if "INSTALL_STALE" in report.warnings:
        text += (" INSTALL_STALE means the installed bundle differs from the source checkout, so launcher and docs may"
                 " disagree. Run `agents-inc repair --source <agents_Inc checkout>`.")
    if "WB_SANDBOX_EXCLUDE_MISSING" in report.warnings:
        text += (' WB_SANDBOX_EXCLUDE_MISSING: a sandboxed Bash cannot start a dispatch. Ask the operator once, before the'
                 ' first dispatch, to add "agents-inc *" to sandbox.excludedCommands in ~/.claude/settings.json.')
    from .update_check import notice  # at most one PyPI request a day; silent on any failure
    update = notice(paths.state)
    if update: text += " " + update + " Tell the operator once; do not update without their go-ahead."
    if host == "claude":
        return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})
    return text

def _session(payload: dict) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or "unknown"))[:128] or "unknown"

def _tool_input(payload: dict) -> dict:
    value = payload.get("tool_input")
    return value if isinstance(value, dict) else {}

def _context(*texts: str) -> str:
    texts = [t for t in texts if t]
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "\n\n".join(texts)}}) if texts else ""

def _nudge_text(paths: InstallPaths, payload: dict) -> str:
    marker = paths.state / "nudged" / _session(payload)
    if marker.exists(): return ""
    marker.parent.mkdir(parents=True, exist_ok=True); marker.touch()
    return NUDGE

def _is_dispatch(payload: dict) -> bool:
    tool = str(payload.get("tool_name") or "")
    if tool in AGENT_TOOLS or DELEGATE_RE.match(tool): return True
    return tool == "Bash" and bool(DISPATCH_RE.search(str(_tool_input(payload).get("command") or "")))

def _quickref_text(paths: InstallPaths, payload: dict) -> str:
    """Once per session, on the first dispatch-shaped call; a missing file yields a note, never an error."""
    marker = paths.state / "quickref" / _session(payload)
    if marker.exists(): return ""
    marker.parent.mkdir(parents=True, exist_ok=True); marker.touch()
    source = paths.current / "skills/workerbee/QUICKREF.md"
    try: return f"{QUICKREF_HEADER}\n\n{source.read_text(encoding='utf-8')}"
    except OSError: return f"agents-inc quickref missing: {source} not found; read skills/workerbee/SKILL.md before dispatching."

def agent_nudge(paths: InstallPaths, payload: dict) -> str:
    """Once per session, so a run of subagent spawns is not flooded with the same reminder."""
    return _context(_nudge_text(paths, payload))

def _is_native(tool_input: object) -> bool:
    subagent = tool_input.get("subagent_type") if isinstance(tool_input, dict) else None
    return isinstance(subagent, str) and subagent in NATIVE_TYPES

def persona_deny(payload: object) -> str:
    """The only blocking path. Anything unexpected fails open (empty string)."""
    try:
        if not isinstance(payload, dict) or payload.get("tool_name") not in AGENT_TOOLS: return ""
        tool_input = _tool_input(payload)
        if _is_native(tool_input): return ""
        description = tool_input.get("description")
        if not isinstance(description, str) or not PERSONA_RE.match(description): return ""
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                  "permissionDecisionReason": PERSONA_DENY_REASON}})
    except Exception:
        return ""

def agent_gate_mode(paths: InstallPaths, env=None) -> tuple[str, str]:
    """(mode, source): env var, then settings.json 'agent_gate', then advisory. Never raises; read on every call."""
    env = os.environ if env is None else env
    value = str(env.get(AGENT_GATE_ENV) or "").strip().lower()
    if value in AGENT_GATE_MODES: return value, f"env {AGENT_GATE_ENV}"
    try:
        if not paths.settings.exists(): return "advisory", "default"
        data = json.loads(paths.settings.read_text(encoding="utf-8"))
        if not isinstance(data, dict): raise ValueError("not an object")
    except (OSError, ValueError):
        return "advisory", "default; settings unreadable"
    if data.get("agent_gate") in AGENT_GATE_MODES: return data["agent_gate"], f"settings {paths.settings}"
    return "advisory", "default"

def write_agent_gate(paths: InstallPaths, mode: str) -> None:
    """Persist 'agent_gate' in settings.json, keeping other keys; a malformed file raises rather than being clobbered."""
    if mode not in AGENT_GATE_MODES: raise ValueError(f"agent gate mode must be one of {', '.join(AGENT_GATE_MODES)}: {mode!r}")
    write_setting(paths, "agent_gate", mode)

def write_setting(paths: InstallPaths, key: str, value: str) -> None:
    """Persist one key in settings.json atomically with mode 0600, keeping other keys; a malformed file raises."""
    data = {}
    if paths.settings.exists():
        try: data = json.loads(paths.settings.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc: raise RuntimeError(f"{paths.settings} is not readable JSON: {exc}") from exc
        if not isinstance(data, dict): raise RuntimeError(f"{paths.settings} is not a JSON object")
    data[key] = value
    paths.settings.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{paths.settings.name}.", dir=paths.settings.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out: json.dump(data, out, indent=2); out.write("\n")
        os.chmod(raw, 0o600)
        os.replace(raw, paths.settings)
    finally:
        if os.path.exists(raw): os.unlink(raw)

def gate_deny(paths: InstallPaths, payload: object) -> str:
    """Second blocking path: under mode 'enforce', only foreground allowlisted subagent types pass. Fails open."""
    try:
        if not isinstance(payload, dict) or payload.get("tool_name") not in AGENT_TOOLS: return ""
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict) or agent_gate_mode(paths)[0] != "enforce": return ""
        subagent, background = tool_input.get("subagent_type"), tool_input.get("run_in_background") is True
        if isinstance(subagent, str) and subagent in GATE_ALLOW and not background: return ""
        if _is_native(tool_input): return ""
        reason = GATE_DENY_REASON.format(subagent=subagent if isinstance(subagent, str) else "omitted",
                                         background="yes" if background else "no", allowed=", ".join(sorted(GATE_ALLOW)))
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                  "permissionDecisionReason": reason}})
    except Exception:
        return ""

def gate_notice(paths: InstallPaths) -> str:
    mode, source = agent_gate_mode(paths)
    lines = [f"agents-inc added hooks to {paths.home / '.claude/settings.json'}: SessionStart session-start; PreToolUse agent-nudge "
             "(Agent|Task, dispatch-shaped Bash, DelegateAgent); PostToolUse agent-done; UserPromptSubmit at_route; "
             'sandbox.excludedCommands "agents-inc *" (dispatch runs outside the Bash sandbox; each delegate still gets '
             "its own sandbox-exec, #94).",
             f"agent gate: {mode} ({source}). enforce blocks Agent/Task calls except foreground "
             f"{', '.join(sorted(GATE_ALLOW))}."]
    if mode == "advisory":
        lines.append("Advisory: Agent/Task delegations skip agents-inc routing, ledger and verification; "
                     "`agents-inc repair --agent-gate enforce` blocks them.")
    lines += [f"Disable for one session: {AGENT_GATE_ENV}=off claude",
              "Switch mode: agents-inc repair --agent-gate advisory|off|enforce (stored in " + str(paths.settings) + ")",
              "Remove the hooks: agents-inc unwire"]
    return "\n".join(lines)

def task_key(payload: dict) -> str:
    def norm(value): return " ".join(str(value or "").lower().split())
    tool_input = _tool_input(payload)
    return hashlib.sha256((norm(tool_input.get("description")) + "\n" + norm(tool_input.get("prompt"))).encode()).hexdigest()[:16]

def _inflight(paths: InstallPaths, key: str): return paths.state / "inflight" / f"{key}.json"

def _read_entry(path) -> dict | None:
    try: entry = json.loads(path.read_text())
    except (OSError, ValueError): return None
    return entry if isinstance(entry, dict) else None

def _write_entry(path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out: json.dump(entry, out)
        os.replace(raw, path)
    finally:
        if os.path.exists(raw): os.unlink(raw)

def duplicate_check(paths: InstallPaths, payload: dict) -> str:
    """Warn when another live session spawned the same task; then claim the task for this session."""
    if payload.get("tool_name") not in AGENT_TOOLS or FAN_OUT in str(_tool_input(payload).get("prompt") or ""): return ""
    key, session, now = task_key(payload), _session(payload), time.time()
    path, warning = _inflight(paths, key), ""
    try:
        entry = _read_entry(path)
        if entry and entry.get("expires", 0) > now and entry.get("session_id") != session:
            since = datetime.fromtimestamp(entry.get("started", now)).strftime("%Y-%m-%d %H:%M")
            warning = (f"agents-inc duplicate warning: the same task (key {key}) is in flight from session "
                       f"{entry.get('session_id')} since {since}. If this is intentional fan-out, add the line "
                       f"\"{FAN_OUT}\" to the prompt.")
        _write_entry(path, {"session_id": session, "tool_use_id": payload.get("tool_use_id"),
                            "started": now, "expires": now + INFLIGHT_TTL_S})
    except OSError as exc:
        print(f"agents-inc hook agent-nudge: in-flight registry unavailable: {exc}", file=sys.stderr)
    return warning

def agent_done(paths: InstallPaths, payload: dict) -> None:
    """Record a host-ledger dispatch row (spec 016), then release this session's claim when a foreground
    Agent/Task spawn returns; a background launch returns at once, so its claim stays until the TTL."""
    try:
        from .. import host_ledger  # lazy: a broken ledger import must not break the other hook events
        host_ledger.record_hook_dispatch(paths.state, payload)
    except Exception:
        pass
    if payload.get("tool_name") not in AGENT_TOOLS or _tool_input(payload).get("run_in_background") is True: return
    path = _inflight(paths, task_key(payload))
    entry = _read_entry(path)
    if entry and entry.get("session_id") == _session(payload): path.unlink(missing_ok=True)

def _payload(stdin) -> dict:
    raw = stdin.read()
    try: payload = json.loads(raw) if raw.strip() else {}
    except ValueError: return {}
    return payload if isinstance(payload, dict) else {}

def run(paths: InstallPaths, event: str, host: str | None, stdin=sys.stdin) -> int:
    try:
        out = ""
        if event == "session-start": out = session_start(paths, host or "claude")
        elif event == "agent-nudge":
            payload = _payload(stdin)
            if _is_dispatch(payload):  # the Bash matcher sees every command; only dispatch-shaped calls get context
                nudge = _nudge_text(paths, payload) if payload.get("tool_name") in AGENT_TOOLS else ""  # NUDGE wording is Agent-only
                out = persona_deny(payload) or gate_deny(paths, payload) or _context(nudge, _quickref_text(paths, payload), duplicate_check(paths, payload))
        elif event == "agent-done": agent_done(paths, _payload(stdin))
        if out: print(out)
    except Exception as exc:  # a broken hook must never break the host session
        print(f"agents-inc hook {event}: {exc}", file=sys.stderr)
    return 0
