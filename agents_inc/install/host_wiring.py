"""Always-on adoption: a managed instruction block and session hooks in each detected host.

Skills load lazily by description, so an installed skill alone never reaches a session that
does not already know to delegate. This module writes the mandate where every session reads it:
the host's user-scope AGENTS.md, plus a SessionStart hook (Claude, Codex), a PreToolUse hook on
Claude's Agent tool (advisory nudge and duplicate warning, plus the spec 015 persona deny), and a
PostToolUse release and host-ledger hook (Agent/Task, and DelegateAgent MCP calls). Every mutation
is receipt-owned and reversible.
"""
from __future__ import annotations
import hashlib, json, os, shutil, tempfile
from dataclasses import dataclass
from pathlib import Path
from .. import role_defaults
from .paths import InstallPaths
from .receipt import InstallReceipt, OwnedPath

BEGIN = "<!-- agents-inc:begin (managed by `agents-inc install`; edits inside this block are overwritten) -->"
END = "<!-- agents-inc:end -->"
HOOK_MARK = " hook "  # owned hook commands are "<launcher> hook <event>"
AT_ROUTE = "skills/codex-bridge/scripts/at_route.sh"          # relative to the installed release
LEGACY_AT_ROUTE = ".claude/scripts/at_route.sh"               # pre-013 hand-installed copy, relative to home
LEGACY_MARKER = "at_route.sh - UserPromptSubmit hook"
ALIASES = ("haiku", "sonnet", "opus", "fable", "astra", "sol", "terra", "luna", "gemini", "mistral", "openrouter")

@dataclass(frozen=True)
class Host:
    name: str
    root: str               # host config dir relative to home; host is wired only if it exists
    instructions: str       # user-scope instruction file relative to home
    hooks_file: str | None  # Claude-style {"hooks": {...}} JSON, or None
    nudge: bool = False     # PreToolUse + PostToolUse hooks on Agent/Task; PostToolUse on DelegateAgent
    prompt_hook: bool = False  # UserPromptSubmit at_route hook (@alias routing)

HOSTS = (
    Host("claude", ".claude", ".claude/AGENTS.md", ".claude/settings.json", nudge=True, prompt_hook=True),
    Host("codex", ".codex", ".codex/AGENTS.md", ".codex/hooks.json"),
    Host("gemini", ".gemini", ".gemini/AGENTS.md", None),
)
GEMINI_SETTINGS = ".gemini/settings.json"

def detected(home: Path) -> tuple[Host, ...]:
    return tuple(host for host in HOSTS if (home / host.root).is_dir())

def block_text(paths: InstallPaths) -> str:
    """Heading plus at most 5 body lines (D78 R4). Launcher, health and repair text come from the SessionStart hook;
    the rules come from role_defaults, the one place a settings loader will replace."""
    return "\n".join((
        BEGIN,
        "## agents-inc delegation (mandatory, every session, every provider)",
        f"- {role_defaults.ROUTE_LINE}",
        f"- {role_defaults.EXECUTIVE_LINE}",
        f"- {role_defaults.ROLES_LINE}",
        f"- {role_defaults.GATE_LINE}",
        "- The session hook supplies health status and the quick reference; with no hook (Gemini), run "
        f"`agents-inc doctor` and read `{paths.current / 'skills/workerbee/QUICKREF.md'}` first.",
        END,
        "",
    ))

def _sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

def upsert_block(text: str, block: str) -> str:
    start, end = text.find(BEGIN), text.find(END)
    if start != -1 and end > start:
        tail = text[end + len(END):].lstrip("\n")
        return text[:start] + block + (("\n" + tail) if tail else "")
    if not text: return block
    return text.rstrip("\n") + "\n\n" + block

def remove_block(text: str) -> str:
    start, end = text.find(BEGIN), text.find(END)
    if start == -1 or end < start: return text
    head, tail = text[:start].rstrip("\n"), text[end + len(END):].lstrip("\n")
    return "\n\n".join(part for part in (head, tail) if part) + ("\n" if head or tail else "")

def hook_command(paths: InstallPaths, event: str) -> str: return f"{paths.launcher}{HOOK_MARK}{event}"

def at_route_command(paths: InstallPaths) -> str:
    # Direct, not "<launcher> hook ...": the hook's exit 2 + stderr box must pass through unwrapped.
    return f"bash {paths.current}/{AT_ROUTE}"

def _launcher_hook(command: object, paths: InstallPaths) -> bool:
    return isinstance(command, str) and command.startswith(f"{paths.launcher}{HOOK_MARK}")

def _owned(command: object, paths: InstallPaths) -> bool:
    return _launcher_hook(command, paths) or command == at_route_command(paths)

def _legacy(command: object, paths: InstallPaths) -> bool:
    return command in {"bash ~/.claude/scripts/at_route.sh", f"bash {paths.home}/{LEGACY_AT_ROUTE}"}

def strip_hooks(config: dict, paths: InstallPaths, legacy: bool = False) -> dict:
    """Drop owned entries; with legacy=True (install/repair only) also drop the pre-013 at_route line."""
    strip_sandbox_exclusion(config)
    hooks = config.get("hooks")
    if not isinstance(hooks, dict): return config
    def drop(h): return isinstance(h, dict) and (_owned(h.get("command"), paths) or (legacy and _legacy(h.get("command"), paths)))
    for event in list(hooks):
        groups = []
        for group in hooks[event] if isinstance(hooks[event], list) else []:
            if not isinstance(group, dict): groups.append(group); continue
            kept = [h for h in group.get("hooks", []) if not drop(h)]
            if kept: groups.append({**group, "hooks": kept})
        if groups: hooks[event] = groups
        else: del hooks[event]
    return config

BASH_NUDGE_PATTERNS = ("agents-inc", "gask.sh", "mask.sh", "oask.sh", "agent.sh", "codex exec")
# #100: a sandboxed Bash cannot start a dispatch (#94); Claude Code skips its sandbox for these matches. 2026-11-11: only
# the subcommands that must leave it: dispatch and run start delegates (provider API, their own sandbox-exec, which cannot
# nest); install and repair write ~/.claude/settings.json and ~/.local, which the sandbox denies (#155). Every other
# subcommand (doctor, events, ledger, models, luna, hook, unwire, report) works inside the sandbox or is run by the host.
SANDBOX_EXCLUDES = ("agents-inc dispatch *", "agents-inc run *", "agents-inc repair *", "agents-inc install *")
LEGACY_SANDBOX_EXCLUDE = "agents-inc *"  # pre-2026-11-11 broad entry; repair migrates it, unwire removes it
SANDBOX_EXCLUDE = SANDBOX_EXCLUDES[0]  # the entry a dispatch needs (doctor, hints)
OWNED_EXCLUDES = SANDBOX_EXCLUDES + (LEGACY_SANDBOX_EXCLUDE,)

def add_sandbox_exclusion(config: dict) -> dict:
    """Claude host only: list SANDBOX_EXCLUDES under sandbox.excludedCommands, replacing the legacy `agents-inc *`.
    Other entries are left as they are."""
    sandbox = config.setdefault("sandbox", {})
    if not isinstance(sandbox, dict): return config
    excluded = sandbox.setdefault("excludedCommands", [])
    if not isinstance(excluded, list): return config
    excluded[:] = [e for e in excluded if e != LEGACY_SANDBOX_EXCLUDE]
    excluded.extend(e for e in SANDBOX_EXCLUDES if e not in excluded)
    return config

def strip_sandbox_exclusion(config: dict) -> dict:
    """Remove only our entries (narrow and legacy); drop the keys we created when nothing else is left in them."""
    sandbox = config.get("sandbox")
    if not isinstance(sandbox, dict) or not isinstance(sandbox.get("excludedCommands"), list): return config
    sandbox["excludedCommands"] = [e for e in sandbox["excludedCommands"] if e not in OWNED_EXCLUDES]
    if not sandbox["excludedCommands"]: del sandbox["excludedCommands"]
    if not sandbox: del config["sandbox"]
    return config

def _legacy_routes(paths: InstallPaths) -> bool:
    from .hook import legacy_routes  # late import: hook.py imports from this package
    return legacy_routes(paths)

def add_hooks(config: dict, paths: InstallPaths, host: Host, sandbox_exclude: bool = True) -> dict:
    config = strip_hooks(config, paths, legacy=True)
    hooks = config.setdefault("hooks", {})
    hooks.setdefault("SessionStart", []).append({"hooks": [{"type": "command", "command": hook_command(paths, f"session-start --host {host.name}"), "timeout": 10}]})
    if host.nudge:
        hooks.setdefault("PreToolUse", []).append({"matcher": "Agent|Task", "hooks": [{"type": "command", "command": hook_command(paths, "agent-nudge"), "timeout": 5}]})
        nudge = hook_command(paths, "agent-nudge")
        # Bash: one handler per dispatch-shaped pattern, so ordinary Bash calls spawn no process (hook.py still filters).
        bash_handlers = [{"type": "command", "if": f"Bash(*{p}*)", "command": nudge, "timeout": 5} for p in BASH_NUDGE_PATTERNS]
        hooks["PreToolUse"].append({"matcher": "Bash", "hooks": bash_handlers})
        hooks["PreToolUse"].append({"matcher": "mcp__.*__DelegateAgent", "hooks": [{"type": "command", "command": nudge, "timeout": 5}]})
        hooks.setdefault("PostToolUse", []).append({"matcher": "Agent|Task", "hooks": [{"type": "command", "command": hook_command(paths, "agent-done"), "timeout": 5}]})
        hooks["PostToolUse"].append({"matcher": "mcp__.*__DelegateAgent", "hooks": [{"type": "command", "command": hook_command(paths, "agent-done"), "timeout": 5}]})
    if host.prompt_hook and _legacy_routes(paths):  # @alias route: --legacy-routes only (FR-016); timeout above the hook's own 120 s alarm
        hooks.setdefault("UserPromptSubmit", []).append({"hooks": [{"type": "command", "command": at_route_command(paths), "timeout": 130}]})
    if host.name == "claude" and sandbox_exclude: add_sandbox_exclusion(config)
    return config

AT_ROUTE_NOTE = ("The UserPromptSubmit hook reads each prompt on this machine. A prompt that does not start with @<alias> "
                 "is not sent anywhere. A prompt that starts with @<alias> (for example @gemini or @luna) is sent to that "
                 "alias's model provider; ~@ opts out.")

def settings_plan(paths: InstallPaths, sandbox_exclude: bool = True) -> tuple[Path, str | None, list[str]]:
    """(Claude settings path, new text or None when nothing changes, one line per entry agents-inc owns there)."""
    host = next(h for h in HOSTS if h.name == "claude")
    target = paths.home / host.hooks_file
    current = target.read_text() if target.exists() else ""
    config = add_hooks(_load_json(target), paths, host, sandbox_exclude)
    lines = []
    for event, groups in config.get("hooks", {}).items():
        for group in groups if isinstance(groups, list) else ():
            for h in group.get("hooks", []) if isinstance(group, dict) else ():
                if isinstance(h, dict) and _owned(h.get("command"), paths):
                    when = h.get("if") or group.get("matcher") or "*"
                    lines.append(f"hooks.{event} [{when}]: {h['command']}")
    if sandbox_exclude: lines += [f"sandbox.excludedCommands: {e}" for e in SANDBOX_EXCLUDES]
    text = _dump_json(config)
    return target, (None if text == current else text), lines

def gemini_reads_agents_md(config: dict) -> dict:
    context = config.setdefault("context", {})
    names = context.get("fileName", ["GEMINI.md"])
    names = [names] if isinstance(names, str) else list(names)
    if "AGENTS.md" not in names: names.insert(0, "AGENTS.md")
    context["fileName"] = names
    return config

def _load_json(path: Path) -> dict:
    if not path.exists(): return {}
    data = json.loads(path.read_text() or "{}")
    if not isinstance(data, dict): raise RuntimeError(f"WB_CONFIG_CONFLICT: {path} is not a JSON object")
    return data

def _dump_json(data: dict) -> str: return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

def _backup(path: Path, paths: InstallPaths) -> str | None:
    if not path.exists(): return None
    backups = paths.state / "backups"; backups.mkdir(parents=True, exist_ok=True)
    backup = str(backups / f"{path.name}.{_sha(str(path).encode())[:12]}.{_sha(path.read_bytes())[:12]}")
    shutil.copy2(path, backup)
    return backup

def delete_file(path: Path, paths: InstallPaths, journal=None) -> None:
    backup = _backup(path, paths)
    if journal: journal.apply("file", path, backup, None, path.unlink)
    else: path.unlink()

def write_file(path: Path, content: str, paths: InstallPaths, journal=None) -> str | None:
    """Atomic write with a byte-exact backup of the predecessor; returns the backup path."""
    backup = _backup(path, paths)
    def mutate():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as out: out.write(content)
        if backup: shutil.copymode(backup, raw)
        os.replace(raw, path)
    if journal: journal.apply("file", path, backup, _sha(content.encode()), mutate)
    else: mutate()
    return backup

def install_host_wiring(paths: InstallPaths, receipt: InstallReceipt, journal=None, sandbox_exclude: bool = True,
                        claude_settings: bool = True) -> InstallReceipt:
    """claude_settings=False (no consent): write nothing to ~/.claude/settings.json; the other hosts and the AGENTS.md
    blocks are still written."""
    owned = [item for item in receipt.owned_paths if item.kind not in {"block", "hooks", "context"}]
    block = block_text(paths)
    for host in detected(paths.home):
        target = paths.home / host.instructions
        current = target.read_text() if target.exists() else ""
        updated = upsert_block(current, block)
        if updated != current: write_file(target, updated, paths, journal)
        owned.append(OwnedPath(target, "block", None, _sha(block.encode())))
        if host.hooks_file and host.name == "claude" and not claude_settings:
            target = paths.home / host.hooks_file
            if target.exists(): owned.append(OwnedPath(target, "hooks"))  # earlier entries stay removable
        elif host.hooks_file:
            target = paths.home / host.hooks_file
            config = add_hooks(_load_json(target), paths, host, sandbox_exclude)
            if _dump_json(config) != (target.read_text() if target.exists() else ""): write_file(target, _dump_json(config), paths, journal)
            owned.append(OwnedPath(target, "hooks"))
        if host.name == "gemini":
            target = paths.home / GEMINI_SETTINGS
            before = _load_json(target)
            config = gemini_reads_agents_md(json.loads(json.dumps(before)))
            if config != before: write_file(target, _dump_json(config), paths, journal)
            owned.append(OwnedPath(target, "context"))
    return InstallReceipt(receipt.release_hash, receipt.python_path, receipt.codex_path, tuple(owned), receipt.prior_release)

def remove_host_wiring(paths: InstallPaths, receipt: InstallReceipt, journal=None) -> None:
    """Remove only our block and our hook entries; leave the rest of each file intact.
    The Gemini context.fileName entry is left in place: other AGENTS.md files may rely on it."""
    for item in receipt.owned_paths:
        if not item.path.exists(): continue
        if item.kind == "block":
            text = item.path.read_text(); stripped = remove_block(text)
            if stripped == text: continue
            if stripped.strip(): write_file(item.path, stripped, paths, journal)
            else: delete_file(item.path, paths, journal)
        elif item.kind == "hooks":
            config = _load_json(item.path); updated = _dump_json(strip_hooks(json.loads(json.dumps(config)), paths))
            if updated != _dump_json(config): write_file(item.path, updated, paths, journal)

def unwire_hooks(paths: InstallPaths, host_name: str) -> list[str]:
    """Remove only owned hook entries from one host's hooks file (backup kept); returns one line per removed handler."""
    host = next(h for h in HOSTS if h.name == host_name)
    target = paths.home / host.hooks_file if host.hooks_file else None
    if target is None or not target.exists(): return []
    config = _load_json(target)
    hooks, removed = config.get("hooks"), []
    for event, groups in (hooks.items() if isinstance(hooks, dict) else ()):
        for group in groups if isinstance(groups, list) else ():
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list): continue
            removed += [f"{event} {group.get('matcher') or '*'}: {h['command']}" for h in group["hooks"]
                        if isinstance(h, dict) and _owned(h.get("command"), paths)]
    excluded = (config.get("sandbox") or {}).get("excludedCommands") or []
    removed += [f"sandbox.excludedCommands: {e}" for e in OWNED_EXCLUDES if e in excluded]
    if not removed: return []
    write_file(target, _dump_json(strip_hooks(config, paths)), paths)
    return removed

def wiring_problems(paths: InstallPaths) -> list[str]:
    problems = []
    for host in detected(paths.home):
        target = paths.home / host.instructions
        if not target.exists() or BEGIN not in target.read_text(): problems.append(f"{host.name}:instructions")
        if host.hooks_file:
            try: config = _load_json(paths.home / host.hooks_file)
            except (OSError, ValueError, RuntimeError): problems.append(f"{host.name}:hooks"); continue
            commands = [h.get("command") for groups in config.get("hooks", {}).values() if isinstance(groups, list)
                        for g in groups if isinstance(g, dict) for h in g.get("hooks", []) if isinstance(h, dict)]
            if not any(_launcher_hook(c, paths) for c in commands): problems.append(f"{host.name}:hooks")
    return problems

def install_alias_links(paths: InstallPaths, receipt: InstallReceipt, journal=None) -> tuple[InstallReceipt, list[str]]:
    """Own `@<alias>` links next to the launcher, pointing through `current` at the installed hook.
    Links to the legacy hand-installed copy are relinked; foreign paths are left with a notice."""
    desired, legacy = str(paths.current / AT_ROUTE), paths.home / LEGACY_AT_ROUTE
    links = {paths.launcher.parent / f"@{alias}" for alias in ALIASES}
    owned, notices = [item for item in receipt.owned_paths if item.path not in links], []
    for alias in ALIASES:
        link = paths.launcher.parent / f"@{alias}"
        def create(link=link): link.parent.mkdir(parents=True, exist_ok=True); link.symlink_to(desired)
        if link.is_symlink() and os.readlink(link) == desired: pass
        elif link.is_symlink() and os.readlink(link) == str(legacy):
            if journal: journal.apply("unlink", link, str(legacy), None, link.unlink)
            else: link.unlink()
            if journal: journal.apply("symlink", link, None, desired, create)
            else: create()
        elif link.exists() or link.is_symlink():
            notices.append(f"NOTE: {link} is not ours; left untouched. Remove it and run `agents-inc repair` to let agents-inc own it."); continue
        elif journal: journal.apply("symlink", link, None, desired, create)
        else: create()
        owned.append(OwnedPath(link, "symlink", None, desired))
    if legacy.is_file() and not legacy.is_symlink():
        if LEGACY_MARKER in legacy.read_text(errors="replace"): delete_file(legacy, paths, journal)
        else: notices.append(f"NOTE: {legacy} is not the agents-inc at_route hook; left in place.")
    return InstallReceipt(receipt.release_hash, receipt.python_path, receipt.codex_path, tuple(owned), receipt.prior_release), notices
