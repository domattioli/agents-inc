"""Host hook entry points. Advisory, except the FR-002 persona deny and the opt-in agent gate deny; never break a session, always exit 0."""
from __future__ import annotations
import hashlib, json, os, re, sys, tempfile, time
from datetime import datetime
from .. import role_defaults
from .. import native_names
from .doctor import check_install
from .paths import InstallPaths

# The rung is the model; the route is always `agents-inc dispatch` (D59, QUICKREF step 2). The earlier wording
# ("keep this Agent call only if routing selects a Claude rung") approved every Agent call on a Claude-only
# install, since sonnet and haiku are Claude rungs (token bench dry run, 2026-10-22).
# D78 R3 (2026-11-11): a small edit (role_defaults.SMALL_TASK_CALLS tool calls or fewer) may go to a native workhorse
# subagent; the supervisor then runs one check itself. Read-only scouts are unchanged. gate_deny is not changed:
# enforce mode still denies that native edit route (D61).
_NATIVE_EDIT = (f"an edit of {role_defaults.SMALL_TASK_CALLS} or fewer tool calls on a native workhorse subagent "
                f"(model {role_defaults.NATIVE_EDIT_MODEL}) with a short brief")
NUDGE = ("agents-inc reminder: this Agent call bypasses agents-inc routing, the ledger and verification. Use Agent "
         f"only for a read-only foreground scout (Explore, Plan) or for {_NATIVE_EDIT}; after that edit, run one check "
         "yourself, because no harness ran gates. Any other delegation, including to a Claude rung "
         "such as sonnet or haiku, goes through `agents-inc dispatch --slots <json> --model <rung>`: naming a model "
         "picks the rung, not the route.")
ROUTE_RULE = ("Naming a model (opus, sonnet, haiku) picks the rung, not the route: delegate through "
              "`agents-inc dispatch`. Use the Agent tool only for read-only foreground scouts (Explore, Plan) and "
              f"for {_NATIVE_EDIT}, then run one check yourself.")
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
# the true model and the call is agents-inc's own route, so neither the FR-002 deny nor the gate applies. The relay type
# only holds `mcp__agents-inc__run`, so a description such as "Astra analyze" names the model it really runs. Exact names,
# not a prefix: a lookalike such as x-agents-inc:luna is still an outside spawn. The spike's luna-brain:* types are
# no longer exempt; the spike mod stays installable but its types now meet the gate like any other.
# Spec 038 T043 (FR-017): every guest agent type (D76, D77) comes from the one nickname list the native registry
# reads (agents_inc/native_names.py), plus the relay type; no hand-kept literal.
NATIVE_TYPES = native_names.guest_types() | {native_names.RELAY_TYPE}
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
    # D78 R4: on Claude the PreToolUse hook injects QUICKREF on the first Agent, Task, DelegateAgent or Bash dispatch
    # (D53), so the read instruction stays only for the route it does not cover (a direct mcp__agents-inc__run call).
    # Codex has no PreToolUse hook, so its session keeps the read instruction.
    read = (f"the first Agent, Task or Bash dispatch loads the quick reference; read {skill} yourself only before a "
            "direct mcp__agents-inc__run call" if host == "claude" else f"read {skill} before the first dispatch")
    text = (f"agents-inc is installed (doctor: {status}). Every delegation in this session routes through agents-inc; "
            f"{read} (full SKILL.md only for a non-Claude rung, a prompt from scratch, "
            f"or a disputed gate). {ROUTE_RULE} Launcher: {paths.launcher}.")
    if not report.ready: text += " Tell the operator doctor is not READY and suggest `agents-inc repair --source <agents-inc checkout>`."
    for warning in report.warnings:
        # An install made --without-codex reports WB_CLI_NOT_FOUND as a warning; say what it means so a session
        # does not read "CLI not found" as "dispatch is broken" and avoid it.
        text += (" Codex is not installed (WB_CLI_NOT_FOUND): Codex rungs are unavailable; Claude rungs dispatch normally."
                 if warning == "WB_CLI_NOT_FOUND" else f" WARNING: {warning}.")
    if "INSTALL_STALE" in report.warnings:
        text += (" INSTALL_STALE means the installed bundle differs from the source checkout, so launcher and docs may"
                 " disagree. Run `agents-inc repair --source <agents-inc checkout>`.")
    if "WB_SANDBOX_EXCLUDE_MISSING" in report.warnings:
        text += (' WB_SANDBOX_EXCLUDE_MISSING: a sandboxed Bash cannot start a dispatch. Ask the operator once, before the'
                 ' first dispatch, to run `agents-inc repair --yes`, which adds "agents-inc dispatch *" and the other narrow entries to'
                 ' sandbox.excludedCommands in ~/.claude/settings.json.')
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

COMPOUND_DISPATCH_RE = re.compile(r"agents-inc\s+(?:dispatch|run|luna)\b")
COMPOUND_MARKERS = ("&&", ";", "|", "cd ", "<<", ">", "$(")
COMPOUND_DENY_REASON = ("agents-inc must be the whole Bash call. Write the slots file in one call, dispatch in the next. "
                        "Never set dangerouslyDisableSandbox.")

COMPOUND_SAFE_FORM = " Run it as: agents-inc dispatch --slots <file> --model <alias>"
_OPERATOR_CHARS = ";<>|&"
# Wrapper options that take a separate argument word (env -u VAR, nice -n 5, xargs -I {}); the argument is not the wrapped command.
_WRAP_OPT_ARG = frozenset({"-u", "-n", "-C", "-P", "-S", "-I", "-a", "-g", "-s", "-L", "-d", "-E"})
_WRAPPERS = frozenset({"env", "exec", "command", "nohup", "time", "nice", "xargs"})
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
_ASSIGN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# Grammar keywords: the command after one is judged as a normal command (#152 F1, F2).
_KEYWORD_HEADS = frozenset({"{", "}", "if", "then", "do", "else", "elif", "while", "until"})
# Heads that load or rename what follows; shlex cannot see through them, so they fail closed.
_HIDING_HEADS = frozenset({"alias", "source", "."})
# Redirection operators: the next word is a file (or fd) operand, never a command word, and the command goes on
# after it (#152 B7, B8; a `> $D/out.json` target was read as an expanded command head). `<<` takes a delimiter word.
_REDIRECTS = frozenset({">", ">>", "<", ">|", "&>", "&>>", ">&", "<&", "<>", "<<", "<<-", "<<<"})

def _unquote(text: str) -> str:
    """Drop quote chars and backslashes so a quoted launcher word ('agents-inc') still matches the dispatch regex."""
    return re.sub(r"['\"\\]", "", text)

class _Word:
    """One shell word. `text` has quotes and escapes removed; the flags keep what the quoting hid."""
    def __init__(self):
        self.text, self.prefix = "", ""  # prefix: leading chars that were plain (unquoted, unescaped, unexpanded)
        self.broke = self.expands = self.quoted = False
    def plain(self, c: str) -> None:
        self.text += c
        if not self.broke: self.prefix += c
    def lit(self, text: str) -> None:  # quoted or escaped: literal data, never an operator or an assignment
        self.text += text; self.broke = self.quoted = True
    def expand(self, text: str) -> None:  # `$`, a backtick or a substitution: the real value is unknown here
        self.text += text; self.broke = self.expands = True
    @property
    def assign(self) -> bool: return bool(_ASSIGN_RE.match(self.prefix))

def _body_subs(body: str, subs: list) -> None:
    """Substitutions inside an unquoted heredoc body run; the rest of the body is data."""
    k = 0
    while k < len(body):
        c = body[k]
        if c == "\\": k += 2
        elif c == "$" and body[k + 1:k + 2] == "(": res, k = _parse(body, k + 2, "paren"); subs.append(res)
        elif c == "`": res, k = _parse(body, k + 1, "tick"); subs.append(res)
        else: k += 1

def _heredocs(s: str, i: int, pending: list, subs: list) -> int:
    """Skip the bodies of the pending heredocs, from line start `i` to each delimiter line; return the new index."""
    for delim, strip, quoted in pending:
        body = []
        while i < len(s):
            j = s.find("\n", i)
            j = len(s) if j < 0 else j
            line, i = s[i:j], min(j + 1, len(s))
            if (line.lstrip("\t") if strip else line) == delim: break
            body.append(line)
        if not quoted: _body_subs("\n".join(body), subs)
    return i

def _parse(s: str, i: int, mode: str):
    """Split bash text into ((commands, operators, substitutions), next index). `commands` is a list of _Word lists,
    `operators` every operator seen at this level in order, `substitutions` the parsed `$( )` and backtick bodies.
    Tracks single and double quotes, backslash escapes, mid-word quoting, `#` comments at a word start, heredoc bodies
    and nested substitutions with quote-aware closing. mode is "" (top level), "paren" (after `$(`) or "tick" (after a
    backtick). Raises ValueError on an unterminated quote. A heuristic, not a full shell grammar."""
    cmds, ops, subs, cur = [], [], [], []
    word, depth, pending, delim, target, n = None, 0, [], None, False, len(s)
    def end_word():
        nonlocal word, delim, target
        if word is None: return
        if target:  # a redirection operand or heredoc delimiter: data, not a word of the command
            target = False
            if delim is not None: pending.append((word.text, delim, word.quoted)); delim = None
        else: cur.append(word)
        word = None
    def end_cmd():
        nonlocal cur, target
        end_word(); target = False
        if cur: cmds.append(cur)
        cur = []
    while i < n:
        c = s[i]
        if (mode == "tick" and c == "`") or (mode == "paren" and c == ")" and depth == 0):
            end_cmd(); return (cmds, ops, subs), i + 1
        if c in " \t": end_word(); i += 1
        elif c == "\n":
            end_cmd(); ops.append(";"); i += 1
            if pending: i = _heredocs(s, i, pending, subs); pending = []
        elif c == "#" and word is None:
            i = s.find("\n", i)
            i = n if i < 0 else i
        elif c in "()":
            depth += 1 if c == "(" else -(depth > 0)
            end_cmd(); ops.append(c); i += 1
        elif c in _OPERATOR_CHARS:
            j = i
            while j < n and s[j] in _OPERATOR_CHARS: j += 1
            op = s[i:j]
            if op == "<<" and s[j:j + 1] == "-": op, j = "<<-", j + 1
            if op in _REDIRECTS:
                # `2>`: an unquoted all-digit word glued to the operator is its fd number, not a command word.
                if word is not None and word.text.isdigit() and word.prefix == word.text: word = None
                end_word(); ops.append(op); i = j; target = True
                if op in ("<<", "<<-"): delim = op == "<<-"
                continue
            end_cmd(); ops.append(op); i = j
        else:
            if word is None: word = _Word()
            if c == "\\":
                if s[i + 1:i + 2] == "\n": i += 2
                elif i + 1 < n: word.lit(s[i + 1]); i += 2
                else: word.plain(c); i += 1
            elif c == "'":
                j = s.find("'", i + 1)
                if j < 0: raise ValueError("unterminated quote")
                word.lit(s[i + 1:j]); i = j + 1
            elif c == '"':
                word.lit(""); i += 1
                while True:
                    if i >= n: raise ValueError("unterminated quote")
                    d = s[i]
                    if d == '"': i += 1; break
                    if d == "\\" and i + 1 < n:
                        e = s[i + 1]
                        if e in '$`"\\': word.text += e
                        elif e != "\n": word.text += d + e
                        i += 2
                    elif d == "$" and s[i + 1:i + 2] == "(":
                        res, i = _parse(s, i + 2, "paren"); subs.append(res); word.expand("$()")
                    elif d == "`":
                        res, i = _parse(s, i + 1, "tick"); subs.append(res); word.expand("$()")
                    else:
                        if d == "$": word.expands = True
                        word.text += d; i += 1
            elif c == "$" and s[i + 1:i + 2] == "(":
                res, i = _parse(s, i + 2, "paren"); subs.append(res); word.expand("$()")
            elif c == "`":
                res, i = _parse(s, i + 1, "tick"); subs.append(res); word.expand("$()")
            elif c == "$": word.expand(c); i += 1
            else: word.plain(c); i += 1
    end_cmd()
    return (cmds, ops, subs), i

def _words_dispatch(words: list) -> bool:
    return (len(words) >= 2 and os.path.basename(words[0].text) == "agents-inc"
            and words[1].text in ("dispatch", "run", "luna"))

def _script_runs_dispatch(script: str) -> str:
    """Judge a script string run by eval or sh -c: "" when it only mentions agents-inc, else the offending element.
    Any executed dispatch/run/luna inside denies, compound or not (D72). An unparsable string falls back to the
    raw-substring rule."""
    script = _unquote(script)
    try:
        level, _ = _parse(script, 0, "")
    except ValueError:
        return "unparsable script string" if COMPOUND_DISPATCH_RE.search(script) else ""
    found, ran, _ = _judge(level, True)
    if found: return found
    return "executed dispatch in script string" if ran else ""

def _judge(level, could_hide: bool) -> tuple[str, bool, bool]:
    """(offending element or "", an agents-inc dispatch runs at this level or below, env prefix on it)."""
    cmds, _ops, subs = level
    dispatch = env_prefix = False
    for words in cmds:
        rest, skipped = list(words), 0
        while rest and rest[0].assign: rest.pop(0); skipped += 1
        while rest and rest[0].text in _KEYWORD_HEADS: rest.pop(0)
        if not rest: continue
        if could_hide:
            if rest[0].expands or "\n" in rest[0].text: return f"expanded command word {rest[0].text!r}", False, False
            if rest[0].text in _HIDING_HEADS: return f"shell keyword {rest[0].text}", False, False
            if rest[0].text == "eval":
                if any(w.expands for w in rest[1:]): return "eval string", False, False
                inner = _script_runs_dispatch(" ".join(w.text for w in rest[1:]))
                if inner: return "eval string", False, False
        wrapped, name = rest, os.path.basename(rest[0].text)
        while name in _WRAPPERS:  # the wrapped command is the first word after the wrapper's own options
            k = 1
            while k < len(wrapped):
                t = wrapped[k].text
                if t in _WRAP_OPT_ARG: k += 2
                elif t.startswith("-") or wrapped[k].assign or t.isdigit() or t == "{}": k += 1
                else: break
            wrapped = wrapped[k:]
            if not wrapped: break
            if _words_dispatch(wrapped): return f"{os.path.basename(rest[0].text)} wrapper", False, False
            name = os.path.basename(wrapped[0].text)
        if wrapped and name in _SHELLS:
            c_at = next((k for k, w in enumerate(wrapped) if k and re.fullmatch(r"-[a-z]*c[a-z]*", w.text)), None)
            if c_at is not None and c_at + 1 < len(wrapped):  # words after the script are positional parameters, not code
                script = wrapped[c_at + 1]
                if script.expands and "agents-inc" in "".join(w.text for w in wrapped): return f"{name} -c string", False, False
                if _script_runs_dispatch(script.text): return f"{name} -c string", False, False
        if _words_dispatch(rest):
            dispatch = True; env_prefix = env_prefix or bool(skipped)
    for sub in subs:
        found, ran, _ = _judge(sub, could_hide)
        if found: return found, False, False
        if ran: return "command substitution", False, False
    return "", dispatch, env_prefix

def _dispatch_shape(command: str) -> str:
    """Return the offending element when an executed `agents-inc dispatch|run|luna` shares the call with a shell
    operator, cd, command substitution or an env prefix; else "". Quoted text, comments and heredoc bodies that only
    mention the command never count, but a dispatch inside a `$(...)` or backtick substitution, a `sh -c` string, or
    behind a wrapper word (env, exec, command, nohup, time, nice, xargs) does. Unbalanced quotes fall back to the
    raw-substring rule."""
    try:
        level, _ = _parse(command, 0, "")
    except ValueError:
        if not COMPOUND_DISPATCH_RE.search(command): return ""
        return next((m for m in COMPOUND_MARKERS if m in command), "")
    # Fail closed on shapes that can hide a launcher, but only when the call could involve agents-inc at all.
    flat = re.sub(r"\\\n", "", command)
    # A mention followed by `/` is a directory in a path (a cwd, a repo checkout), never the launcher name, so it alone
    # does not make the call suspect; `agents-inc` at a word end (bin/agents-inc, X=agents-inc;) still does.
    def mentions(text: str) -> bool: return bool(re.search(r"agents-inc(?!/)", text))
    could_hide = mentions(flat) or mentions(re.sub(r"\$\{[^}]*\}|[\\'\"`]", "", flat))
    found, dispatch, env_prefix = _judge(level, could_hide)
    if found: return found
    if not dispatch: return ""
    if env_prefix: return "env prefix"
    if level[1]: return level[1][0]
    if level[2]: return "command substitution"
    return ""

def compound_deny(payload: object) -> str:
    """Deny a Bash call that wraps an agents-inc dispatch in a compound command. Fails open on anything unexpected."""
    try:
        if not isinstance(payload, dict) or payload.get("tool_name") != "Bash": return ""
        command = str(_tool_input(payload).get("command") or "")
        found = _dispatch_shape(command)
        if not found: return ""
        reason = f"{COMPOUND_DENY_REASON}{COMPOUND_SAFE_FORM} (found: {found})."
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                  "permissionDecisionReason": reason}})
    except Exception:
        return ""

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

LEGACY_ROUTES_KEY = "legacy_routes"  # spec 038 FR-016: relay type, mcp__agents-inc__run, @alias hook

def legacy_routes(paths: InstallPaths) -> bool:
    """True only when settings.json says legacy_routes is 'on' (set by install/repair --legacy-routes). Default off:
    native agent types are the one user-facing route. Never raises; an unreadable file reads as off."""
    try: data = json.loads(paths.settings.read_text(encoding="utf-8"))
    except (OSError, ValueError): return False
    return isinstance(data, dict) and data.get(LEGACY_ROUTES_KEY) == "on"

def write_legacy_routes(paths: InstallPaths, on: bool) -> None:
    write_setting(paths, LEGACY_ROUTES_KEY, "on" if on else "off")

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
             'sandbox.excludedCommands "agents-inc dispatch|run|repair|install *" (these run outside the Bash sandbox; each delegate still gets '
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
            out = compound_deny(payload)
            if not out and _is_dispatch(payload):  # the Bash matcher sees every command; only dispatch-shaped calls get context
                nudge = _nudge_text(paths, payload) if payload.get("tool_name") in AGENT_TOOLS else ""  # NUDGE wording is Agent-only
                out = persona_deny(payload) or gate_deny(paths, payload) or _context(nudge, _quickref_text(paths, payload), duplicate_check(paths, payload))
        elif event == "agent-done": agent_done(paths, _payload(stdin))
        if out: print(out)
    except Exception as exc:  # a broken hook must never break the host session
        print(f"agents-inc hook {event}: {exc}", file=sys.stderr)
    return 0
