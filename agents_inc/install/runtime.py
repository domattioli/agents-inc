"""Direct Codex execution with an install-recorded executable only."""
from __future__ import annotations
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from .live_events import _stream_run

import json
import sys

def _aliases_from_routing() -> dict[str, str]:
    """D52: alias -> slug from routing.json (the single source); alias is the text after the slug's last hyphen."""
    path = Path(__file__).resolve().parents[1] / "routing.json"
    tiers = json.loads(path.read_text(encoding="utf-8"))["tiers"]
    slugs = [tier["codex"] for tier in tiers.values() if tier.get("codex")]
    return {slug.rsplit("-", 1)[-1]: slug for slug in slugs}


# Built-in DEFAULTS only; resolution goes through load_model_map().
MODEL_ALIASES = _aliases_from_routing()


def _read_map(raw: str) -> dict[str, str]:
    """Parse a JSON object string, or a path to a JSON file. Accepts {"alias": "slug"} or {"models": {...}}."""
    raw = raw.strip()
    text = raw if raw.startswith("{") else Path(raw).expanduser().read_text()
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("models"), dict):
        data = data["models"]
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) and v for k, v in data.items()):
        raise ValueError("model map must be a JSON object of alias -> slug strings")
    return data


def load_model_map(roster: Path | None = None, env: dict | None = None) -> dict[str, str]:
    """Merge model aliases, lowest to highest precedence: built-in defaults < roster file < AGENTS_INC_MODEL_MAP.

    Roster: JSON file (default ~/.config/agents-inc/roster.json), either {"alias": "slug"} or {"models": {...}}.
    AGENTS_INC_MODEL_MAP: a JSON object string (starts with "{"), otherwise a path to a JSON file.
    A malformed or unreadable override is skipped with a message on stderr; it never raises.
    """
    env = os.environ if env is None else env
    merged = dict(MODEL_ALIASES)
    if roster is None:
        from .paths import InstallPaths
        roster = InstallPaths.for_home(Path(env.get("HOME") or Path.home())).roster
    sources = []
    if Path(roster).is_file(): sources.append((f"roster {roster}", lambda: _read_map(str(roster))))
    if env.get("AGENTS_INC_MODEL_MAP"): sources.append(("AGENTS_INC_MODEL_MAP", lambda: _read_map(env["AGENTS_INC_MODEL_MAP"])))
    for label, read in sources:
        try:
            merged.update(read())
        except (OSError, ValueError) as exc:
            print(f"WARN: ignoring malformed model map from {label}: {exc}; using defaults", file=sys.stderr)
    return merged


def is_temp_or_shim_path(entry) -> bool:
    """True when entry sits under the temp root or has a path component ending in -shims (#50)."""
    p = Path(entry)
    roots = {Path(tempfile.gettempdir())}
    try: roots.add(Path(tempfile.gettempdir()).resolve())
    except OSError: pass
    for cand in (p, p.resolve()):
        if any(cand == r or r in cand.parents for r in roots): return True
        if any(part.endswith("-shims") for part in cand.parts): return True
    return False


def resolve_executable(name: str, search_path: str | None = None) -> Path:
    candidate = None
    if search_path:
        kept = [e for e in search_path.split(os.pathsep) if e and not is_temp_or_shim_path(e)]
        if kept: candidate = shutil.which(name, path=os.pathsep.join(kept))
    if not candidate:
        candidate = shutil.which(name, path=search_path)
        if candidate and search_path:
            print(f"WARN: {name} resolved to a temporary or shim path {candidate}; put the stable directory first on PATH", file=sys.stderr)
    if not candidate:
        raise FileNotFoundError(f"WB_CLI_NOT_FOUND: {name}; run agents-inc repair")
    path = Path(candidate).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise FileNotFoundError(f"WB_CLI_NOT_FOUND: {name}; run agents-inc repair")
    return path


# D49: Codex tool access by rung. Grunt (luna) and unknown aliases stay tool-free (fail closed).
TOOL_RUNGS = {"astra": "Executive", "sol": "Orchestrator", "terra": "Workhorse"}
# D49.1: luna gets the shell tool only on an explicit --tools; it stays off by default and never leads.
TOOL_OPT_IN = ("luna",)
HARD_DENY = (".ssh", ".config", ".claude", ".codex-bridge", ".local", ".aws", ".gnupg", ".netrc")
CODEX_READABLE = ("generated_images", "skills")  # under ~/.codex; linked into the isolated home too
PROFILE = "agents_inc_d49"
TOOL_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
# Nested seatbelts fail on macOS (sandbox_apply: Operation not permitted), so an outer sandbox-exec would disable
# Codex's own seatbelt. The read deny therefore rides Codex's permission profile, which its seatbelt enforces.


def tools_for(model: str, no_tools: bool = False, tools: bool = False) -> bool:
    """D49: on by default for astra, sol, terra; D49.1: luna only with --tools; --no-tools wins; a raw slug raises."""
    if no_tools:
        return False
    if model in TOOL_RUNGS:
        return True
    if tools and model in TOOL_OPT_IN:
        return True
    if tools:
        raise ValueError(f"--tools is allowed only for astra, sol, terra, luna; not {model!r}")
    return False


def _toml_key(path) -> str:
    text = os.path.realpath(str(path))
    if any(ch in text for ch in ('"', "\\", "\n")):
        raise ValueError(f"path not expressible in permission profile: {text!r}")
    return f'"{text}"'


def permission_profile(cwd: Path, write: bool, home: Path | None = None,
                       write_dir: Path | None = None, extra_deny: tuple = (), extra_read: tuple = (),
                       extra_write: tuple = ()) -> dict[str, str]:
    """Filesystem grants for tool commands. Anything absent (all of HOME except cwd) is unreadable.
    D51: with write_dir (the Lead's run directory), write goes to write_dir/inbox only; write_dir and cwd stay
    read, so run.json, workers/ and results are broker-owned. Without it, --write grants cwd (legacy)."""
    home = Path(home or Path.home())
    grants ={'":minimal"': "read", _toml_key("/opt/homebrew"): "read", _toml_key("/tmp"): "read",
              _toml_key("/private/tmp"): "read",
              _toml_key("/System/Library/Perl"): "read",  # /usr/bin/shasum and other perl tools need libperl
              _toml_key(cwd): "write" if (write and write_dir is None) else "read"}
    if write_dir is not None:
        if (Path(write_dir) / "inbox").is_symlink():
            raise ValueError(f"run-dir inbox must not be a symlink: {Path(write_dir) / 'inbox'}")
        grants[_toml_key(write_dir)] = "read"
        grants[_toml_key(Path(write_dir) / "inbox")] = "write"
    # Codex loads every AGENTS.md from the git root down to cwd and refuses to start if one is unreadable, so a
    # cwd below the repo root needs read on the instruction files above it (only those files, not the directories).
    real_cwd = Path(os.path.realpath(cwd))
    for parent in () if (real_cwd / ".git").exists() else real_cwd.parents:
        for name in ("AGENTS.md", "AGENTS.override.md"):
            if (parent / name).is_file():
                grants[_toml_key(parent / name)] = "read"
        if (parent / ".git").exists() or parent == Path(os.path.realpath(home)):
            break
    # Built-in image_gen saves under CODEX_HOME/generated_images (the isolated home links here); the delegate
    # copies its PNG into cwd. Codex skills (imagegen and others) are instruction files the model reads with
    # shell commands. Read only; the rest of ~/.codex (auth.json, config, sessions) stays unreadable.
    for name in CODEX_READABLE:
        grants[_toml_key(Path(os.path.realpath(home)) / ".codex" / name)] = "read"
    for name in HARD_DENY:
        grants[f'"{os.path.realpath(home)}/{name}"'] = "none"
    for path in extra_read:  # e.g. the dispatch snapshot outside cwd; files only
        grants[_toml_key(path)] = "read"
    for path in extra_write:  # the per-run tool temp dir (#66)
        grants[_toml_key(path)] = "write"
    for path in extra_deny:  # e.g. the isolated Lead CODEX_HOME
        grants[_toml_key(path)] = "none"
    return grants


def permission_args(cwd: Path, write: bool, home: Path | None = None, write_dir: Path | None = None,
                    extra_deny: tuple = (), extra_read: tuple = (), network: bool = False,
                    extra_write: tuple = ()) -> list[str]:
    """network (#66): opt-in outbound access for tool commands; off unless asked."""
    body = ", ".join(f"{k}={chr(34)}{v}{chr(34)}"
                     for k, v in permission_profile(cwd, write, home, write_dir, extra_deny, extra_read,
                                                    extra_write).items())
    return (["-c", f'default_permissions="{PROFILE}"', "-c", f"permissions.{PROFILE}.filesystem={{{body}}}"]
            + (["-c", f"permissions.{PROFILE}.network={{enabled=true}}"] if network else []))


MCP_BROKER = Path(__file__).resolve().parent / "mcp_broker.py"
MCP_STARTUP_TIMEOUT_SEC = 30  # Codex waits for the tool catalog before the turn starts
MCP_TOOL_TIMEOUT_SEC = 3600  # Codex's 60 s default would cut a Worker run short


def _toml_str(text: str) -> str:
    if any(ch in text for ch in ('"', "\\", "\n")):
        raise ValueError(f"value not expressible in a TOML string: {text!r}")
    return f'"{text}"'


def lead_args(model: str, lead_dir: Path, broker: Path | None = None, codex_home: Path | None = None,
              home_repo: str | None = None) -> list[str]:
    """D51 MCP transport: -c overrides that start mcp_broker.py as the Lead's `agents_inc` MCP server.
    Only astra, sol, terra; a raw slug or luna raises. JSON strings and arrays are valid TOML here."""
    if model not in TOOL_RUNGS:
        raise ValueError(f"--lead is allowed only for astra, sol, terra; not {model!r}")
    if not Path(lead_dir).is_dir():
        raise ValueError(f"--lead run directory missing: {lead_dir}")
    script = str(broker or MCP_BROKER)
    prefix = "mcp_servers.agents_inc"
    server_args = [script, "--run-dir", str(Path(lead_dir).resolve())] + (["--home-repo", str(home_repo)] if home_repo else [])
    # Codex starts stdio MCP servers with a cleared env, so CODEX_HOME (the Worker deny) goes through the env table.
    env_table = ["-c", f"{prefix}.env={{CODEX_HOME={_toml_str(os.path.realpath(codex_home))}}}"] if codex_home else []
    return _mcp_server_args(server_args) + env_table + _denied_skill_args()


def _denied_skill_args(home: Path | None = None) -> list[str]:
    """D57: user skills that resolve into ~/.local (sandbox-denied) make the Lead stop on a blocked read; turn them off."""
    home = Path(home or Path.home())
    denied = Path(os.path.realpath(home / ".local"))
    root, paths, seen = home / ".agents" / "skills", [], set()
    for top, dirs, files in os.walk(root, followlinks=True):  # skill links are symlinked dirs; rglob skips them
        real = os.path.realpath(top)
        if real in seen or len(Path(top).relative_to(root).parts) >= 4:  # visited set: no symlink-loop blowup
            dirs[:] = []
            continue
        seen.add(real)
        if "SKILL.md" in files and Path(os.path.realpath(Path(top) / "SKILL.md")).is_relative_to(denied):
            paths.append(str(Path(top) / "SKILL.md"))
    paths.sort()
    if not paths:
        return []
    items = ", ".join(f"{{path={_toml_str(f)}, enabled=false}}" for f in paths)
    return ["-c", f"skills.config=[{items}]"]


def _mcp_server_args(server_args: list[str]) -> list[str]:
    prefix = "mcp_servers.agents_inc"
    return ["-c", f"{prefix}.command={json.dumps(sys.executable)}",
            "-c", f"{prefix}.args={json.dumps(server_args)}",
            "-c", f"{prefix}.tool_timeout_sec={MCP_TOOL_TIMEOUT_SEC}",
            "-c", f'{prefix}.default_tools_approval_mode="approve"',
            "-c", f"{prefix}.required=true",
            "-c", f'{prefix}.startup_readiness="catalog"',
            "-c", f"{prefix}.startup_timeout_sec={MCP_STARTUP_TIMEOUT_SEC}"]


WORKER_MCP = Path(__file__).resolve().parent / "worker_mcp.py"


def worker_args(channel_dir: Path, request_id: str, server: Path | None = None) -> list[str]:
    """D54: -c overrides that start worker_mcp.py (one tool, ask_lead) as a broker Worker's `agents_inc` server.
    The server knows only its channel directory and request id."""
    return _mcp_server_args([str(server or WORKER_MCP), "--run-dir", str(Path(channel_dir).resolve()),
                             "--request-id", request_id])


THREAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def _events(text: str):
    for line in (text or "").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def parse_thread_id(text: str) -> str | None:
    """D54: the thread id from `codex exec --json` stdout (first thread.started event). Other events and
    non-JSON lines are skipped."""
    for event in _events(text):
        tid = event.get("thread_id")
        if event.get("type") == "thread.started" and isinstance(tid, str) and THREAD_ID_RE.match(tid):
            return tid
    return None


def _json_errors(text: str) -> list[str]:
    """Error messages from `--json` events (error, turn.failed), as `ERROR:` lines for the rate-limit check."""
    out = []
    for event in _events(text):
        if event.get("type") == "error":
            out.append(f"ERROR: {event.get('message')}")
        elif event.get("type") == "turn.failed":
            err = event.get("error")
            out.append(f"ERROR: {err.get('message') if isinstance(err, dict) else err}")
    return out


def lead_codex_home(slug: str) -> Path:
    """Isolated CODEX_HOME for a broker Lead: only auth.json and sessions (symlinks) and a one-line config.toml,
    so the operator's MCP servers and config never load. Never copies or reads auth.json. Caller removes it
    with shutil.rmtree (does not follow symlinks)."""
    real = Path.home() / ".codex"
    auth = real / "auth.json"
    if not auth.is_file():
        raise FileNotFoundError(f"WB_CODEX_AUTH_MISSING: {auth} not found; log in to Codex first")
    if any(ch in slug for ch in ('"', "\\", "\n")):
        raise ValueError(f"model slug not expressible in config.toml: {slug!r}")
    (real / "sessions").mkdir(exist_ok=True)
    for name in CODEX_READABLE:
        (real / name).mkdir(exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="agents-inc-lead-home-"))
    try:
        os.chmod(home, 0o700)
        (home / "auth.json").symlink_to(auth)
        (home / "sessions").symlink_to(real / "sessions")
        # Skills load, and image_gen output outlives the temp home, readable to tool commands (permission_profile).
        for name in CODEX_READABLE:
            (home / name).symlink_to(real / name)
        (home / "config.toml").write_text(f'model = "{slug}"\n', encoding="utf-8")
    except BaseException:
        try:
            shutil.rmtree(home)
        except OSError:
            pass  # the original error below is the one that matters
        raise
    return home


def lead_env(executable: Path, codex_home: Path, base: dict | None = None) -> dict:
    """Explicit minimal env for a broker Lead (and so its MCP server child): the Worker shape (fixed PATH plus
    the codex directory; HOME, USER, TERM, LANG, TMPDIR), no *KEY*/*TOKEN*/*SECRET* variable, plus CODEX_HOME."""
    from .dispatch import worker_env
    env = worker_env(str(executable), os.environ if base is None else base)
    env["CODEX_HOME"] = str(codex_home)
    return env


# A tool-free run turns off every Codex feature that adds a tool, not only the shell: with code_mode_host on, a luna
# brain step searched Codex's own JavaScript tool table for SubagentHandback and looped 18 model calls (2026-10-24).
NO_TOOL_FEATURES = ("shell_tool", "unified_exec", "code_mode_host", "apps", "browser_use", "computer_use", "in_app_browser",
                    "goals", "image_generation", "multi_agent", "plugins", "skill_search", "sleep_tool", "tool_suggest",
                    "view_image")
NO_TOOL_ARGS = [a for f in NO_TOOL_FEATURES for a in ("-c", f"features.{f}=false")]
# Codex keeps its JavaScript exec tool even with those features off, and its base instructions teach the model to use it:
# luna then searched exec for the host's Bash, got "code-mode host is disabled", and answered that it could not run
# anything (Docker stress run, 2026-10-24). A host-tools run (--host-tools: the agents-inc:luna type, whose host runs the
# tools luna names) replaces the base instructions with this text; other tool-free runs keep Codex's own.
NO_TOOL_INSTRUCTIONS = (
    "You answer in text only: your final message is your whole output. Codex's own tools (exec, apply_patch, "
    "request_user_input) are off: never call one and never look for one. "
    "When the user message lists tools that a host runs for you, those are host tools, not Codex tools, Bash and Read "
    "among them. They are real and work: request them in your reply, in the format the user message asks for, and their "
    "results arrive in the next message. Never answer that you cannot run a tool the host lists. Host tools need no "
    "permission from you: the host decides every call. Never ask whether to run a tool, whether to go on, or how to "
    "report: act, then answer.\n")
# luna read "never call any other Codex tool" as a ban on the host's Bash and refused (spec 028 Docker run, 2026-10-25),
# so the text names the Codex tools and says the host's are not among them. luna also asked "May I run wc?" or "Should
# I report?" through request_user_input, dozens of times a step, until Codex exited 1 (macOS host stress run,
# 2026-10-25): the text says host tools need no permission, and HOST_TOOLS_ARGS drops the sandbox note behind it.


# The instructions alone did not hold: gpt-6-luna's catalog entry says tool_mode "code_mode_only", so Codex serves it
# exec whatever the features say, and luna still sent host tool requests to exec (Docker stress run, 2026-10-24).
# A host-tools run gets a one-model catalog, copied from Codex's own model cache, with these fields replaced:
# "direct" drops exec, shell_type "disabled" drops exec_command, multi_agent_version "none" drops collaboration.*, and
# no apply_patch_tool_type drops apply_patch (probed on Codex 0.159.2; luna had called each of them).
HOST_TOOLS_MODEL = {"tool_mode": "direct", "shell_type": "disabled", "experimental_supported_tools": [],
                    "multi_agent_version": "none"}
HOST_TOOLS_DROP = ("apply_patch_tool_type",)
# Codex also adds context a host-tools run must not carry, each dropped by one setting (`codex debug prompt-input`,
# Codex 0.159.2, 2026-10-25): the read-only sandbox note, which luna read as a reason to ask "May I run wc?" through
# request_user_input dozens of times a step until Codex exited 1 (macOS host stress run); the Default-mode text, which
# offers request_user_input; the operator's skills list (13.8k chars), which luna has no tool to read; and the cwd's
# AGENTS.md, which the host already puts in the conversation. The sandbox itself stays: only the notes go.
# luna still calls request_user_input (426 calls in 15 macOS stress runs, 14/15 pass).
HOST_TOOLS_ARGS = ["-c", "include_permissions_instructions=false", "-c", "include_collaboration_mode_instructions=false",
                   "-c", "skills.include_instructions=false", "-c", "project_doc_max_bytes=0"]


def _write_if_changed(path: Path, text: str) -> None:
    if not path.is_file() or path.read_text() != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class HostToolsCatalogMissing(RuntimeError):
    """The stripped model catalog for a host-tools run cannot be built (spec 028 FR-010, FR-011)."""


# `codex debug models` writes models_cache.json in a fresh Codex home with no model call and no session (Codex 0.159.2,
# Docker probe 2026-10-25; research.md R3). It takes no slug: the fetched catalog holds every model the account sees.
CATALOG_WARM_COMMAND = 'codex debug models > /dev/null'


def real_codex_home() -> Path:
    """The operator's Codex home, the directory lead_codex_home links auth.json from. CODEX_HOME is not followed, so the
    catalog source and the credential source are always the same directory."""
    return Path.home() / ".codex"


def host_tools_catalog(slug: str, codex_home: Path | None = None) -> Path | None:
    """A model catalog holding only slug, with HOST_TOOLS_MODEL applied; None when Codex has no cached entry for slug
    under codex_home (default: the real Codex home)."""
    home = codex_home or real_codex_home()
    try:
        cache = json.loads((home / "models_cache.json").read_text())
        entry = next(m for m in cache.get("models", []) if m.get("slug") == slug)
    except (OSError, ValueError, StopIteration, AttributeError):
        return None
    path = Path(tempfile.gettempdir()) / "agents-inc" / f"host-tools-catalog-{slug}.json"
    model = {k: v for k, v in {**entry, **HOST_TOOLS_MODEL}.items() if k not in HOST_TOOLS_DROP}
    _write_if_changed(path, json.dumps({**cache, "models": [model]}))
    return path


def require_host_tools_catalog(slug: str, codex_home: Path | None = None) -> Path:
    """host_tools_catalog, failing closed: a host-tools run never falls back to Codex's own catalog, which would hand
    the model exec and apply_patch."""
    path = host_tools_catalog(slug, codex_home)
    if path is None:
        home = codex_home or real_codex_home()
        raise HostToolsCatalogMissing(
            f"WB_LUNA_CATALOG_MISSING: no models_cache.json entry for {slug} under {home}; `codex debug models` writes it with no model call. "
            f"Run once, then retry: {CATALOG_WARM_COMMAND.format(slug=slug)}")
    return path


def no_tool_args(host_tools: bool = False, slug: str | None = None, catalog: Path | None = None) -> list[str]:
    """NO_TOOL_ARGS; host_tools adds model_instructions_file pointing at NO_TOOL_INSTRUCTIONS and model_catalog_json
    pointing at the stripped catalog: the catalog argument, else one built from the real Codex home for slug. Raises
    HostToolsCatalogMissing when there is none."""
    if not host_tools:
        return list(NO_TOOL_ARGS)
    if catalog is None:
        if not slug: raise ValueError("--host-tools needs a model slug")
        catalog = require_host_tools_catalog(slug)
    path = Path(tempfile.gettempdir()) / "agents-inc" / "no-tools-instructions.md"
    _write_if_changed(path, NO_TOOL_INSTRUCTIONS)
    return NO_TOOL_ARGS + HOST_TOOLS_ARGS + ["-c", f"model_instructions_file={json.dumps(str(path))}",
                           "-c", f"model_catalog_json={json.dumps(str(catalog))}"]


def build_codex_argv(executable: Path, model: str, effort: str, cwd: Path, supported_efforts: dict[str, list[str]],
                     model_map: dict[str, str] | None = None, tools: bool = False, write: bool = False,
                     write_dir: Path | None = None, lead_dir: Path | None = None,
                     extra_deny: tuple = (), lead_home: Path | None = None, home_repo: str | None = None,
                     json_out: Path | None = None, worker: tuple | None = None, extra_read: tuple = (),
                     network: bool = False, tool_tmp: Path | None = None, host_tools: bool = False,
                     host_catalog: Path | None = None) -> list[str]:
    """host_tools (tool-free runs only): replace Codex's base instructions with NO_TOOL_INSTRUCTIONS and serve the
    stripped catalog (host_catalog, else built from the real Codex home; HostToolsCatalogMissing when absent). json_out adds `--json -o <json_out>` (D54 session capture); worker=(channel_dir, request_id) adds the
    ask_lead MCP server. network (#66) turns on outbound access for tool commands. tool_tmp (#66): a writable
    temp dir for tool commands, set as TMPDIR and as the zsh here-document prefix (TMPPREFIX)."""
    slug = (model_map if model_map is not None else load_model_map()).get(model, model if model in supported_efforts else None)
    if not slug:
        raise ValueError(f"unknown Codex model alias: {model}")
    if effort not in supported_efforts.get(slug, []):
        raise ValueError(f"unsupported effort {effort!r} for {slug}")
    if not executable.is_absolute():
        raise ValueError("Codex executable must be absolute")
    if lead_dir is not None and write and Path(os.path.realpath(lead_dir)).is_relative_to(Path(os.path.realpath(cwd))):
        raise ValueError("--lead --write needs the run directory outside cwd (D57)")
    if write and not tools:
        raise ValueError("--write needs --tools (astra, sol, terra, or luna with --tools; without --no-tools)")
    if network and (not tools or lead_dir is not None):
        raise ValueError("--network needs tools on and no --lead")
    if host_tools and tools:
        raise ValueError("--host-tools needs tools off")
    common = ["--skip-git-repo-check", "-C", str(cwd), "-c", f"model_reasoning_effort={effort}",
              "-c", 'shell_environment_policy.inherit="none"', "-c", 'web_search="disabled"']
    if lead_dir is not None and (not tools or write_dir is not None):
        raise ValueError("--lead needs tools on and no --run-dir")
    if lead_dir is not None and worker is not None:
        raise ValueError("a Lead gets the broker server, not the Worker ask_lead server")
    if not tools and extra_deny:
        # Broker Worker without a shell tool (luna): emit the deny profile too, so the D51 promise holds on every rung.
        # `-s` is dropped here only: a sandbox_mode override silently replaces default_permissions (proved 2026-10-04);
        # the profile grants cwd read only and shell_tool stays off.
        argv = ([str(executable), "exec", "-m", slug] + common + permission_args(cwd, False, extra_deny=extra_deny)
                + no_tool_args(host_tools, slug, host_catalog))
    elif not tools:
        argv = [str(executable), "exec", "-m", slug, "-s", "read-only"] + common + no_tool_args(host_tools, slug, host_catalog)
    else:
        # No -s with tools on: a sandbox_mode override silently replaces default_permissions (proved 2026-10-04).
        # The profile alone sets access: cwd "read", or "write" with --write; network stays off unless --network.
        # inherit="none" leaves PATH empty; give tool commands system paths only (no /opt/homebrew, no user paths).
        tmp_env = ([] if tool_tmp is None else
                   ["-c", f"shell_environment_policy.set.TMPDIR={_toml_str(str(tool_tmp))}",
                    "-c", f"shell_environment_policy.set.TMPPREFIX={_toml_str(str(Path(tool_tmp) / 'zsh'))}"])
        # ~/.gitconfig is unreadable in the profile and git aborts on it; tool commands get an empty global config
        argv = ([str(executable), "exec", "-m", slug] + common + ["-c", f'shell_environment_policy.set.PATH="{TOOL_PATH}"',
                                                              "-c", 'shell_environment_policy.set.GIT_CONFIG_GLOBAL="/dev/null"']
                + tmp_env
                + permission_args(cwd, write, write_dir=write_dir, extra_deny=extra_deny, extra_read=extra_read,
                                  network=network, extra_write=() if tool_tmp is None else (tool_tmp,))
                + (lead_args(model, lead_dir, None, lead_home, home_repo) if lead_dir is not None else []))
    if worker is not None:
        argv += worker_args(*worker)
    if json_out is not None:
        argv += ["--json", "-o", str(json_out)]
    return argv + ["-"]


def build_codex_resume_argv(executable: Path, thread_id: str, message: str, model: str, effort: str, cwd: Path,
                            supported_efforts: dict[str, list[str]], model_map: dict[str, str] | None = None,
                            tools: bool = False, write: bool = False, write_dir: Path | None = None,
                            extra_deny: tuple = (), json_out: Path | None = None,
                            worker: tuple | None = None, extra_read: tuple = (), network: bool = False,
                            tool_tmp: Path | None = None, host_tools: bool = False,
                            host_catalog: Path | None = None) -> list[str]:
    """D54: `codex exec resume <thread_id> ... <message>` with the same model, effort, -c and permission flags as
    the original run. `exec resume` takes no -C or -s: the caller runs it with cwd set, and `-s <mode>` becomes
    `-c sandbox_mode=<mode>`. The message is the PROMPT positional; a leading space keeps a message that starts
    with "-" from reading as a flag."""
    if not isinstance(thread_id, str) or not THREAD_ID_RE.match(thread_id):
        raise ValueError(f"bad Codex thread id: {thread_id!r}")
    base = build_codex_argv(executable, model, effort, cwd, supported_efforts, model_map, tools, write, write_dir,
                            None, extra_deny, None, None, json_out, worker, extra_read=extra_read, network=network,
                            tool_tmp=tool_tmp, host_tools=host_tools, host_catalog=host_catalog)
    rest, flags, i = base[2:-1], [], 0  # between [exe, "exec"] and the stdin marker "-"
    while i < len(rest):
        if rest[i] == "-C":
            i += 2
            continue
        if rest[i] == "-s":
            flags += ["-c", f'sandbox_mode="{rest[i + 1]}"']
            i += 2
            continue
        flags.append(rest[i])
        i += 1
    return [base[0], "exec", "resume", thread_id] + flags + [(" " + message) if message.startswith("-") else message]


# One quota/rate-limit pattern for run_codex and for `agents-inc dispatch` (which adds the Claude phrases).
QUOTA_PATTERN = r"usage limit|rate limit|too many requests|\b429\b|model is at capacity"
QUOTA_RE = re.compile(QUOTA_PATTERN, re.IGNORECASE)


def kill_and_reap(proc) -> None:
    """Kill the child's whole process group and wait for the child (cancellation cleanup)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait()
    except Exception:
        pass


def _run_with_deadline(argv, prompt, env, timeout_s, extra, on_line=None) -> subprocess.CompletedProcess:
    """Run argv in its own session; on expiry kill the whole group and return rc 124. Any other exception during
    the run (KeyboardInterrupt included) kills the group and reaps the child before it propagates.
    on_line (spec 027): called with each stdout line as it arrives; the returned stdout is still the full text."""
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env=env, start_new_session=True, **extra)
    rc, out, err = _stream_run(proc, prompt, timeout_s, on_line)  # _stream_run kills and reaps on any exception
    return subprocess.CompletedProcess(argv, rc, out or "", err)


def _run_streaming(argv, prompt, env, extra, on_line) -> subprocess.CompletedProcess:
    """The no-deadline run with a line callback (spec 027)."""
    return _run_with_deadline(argv, prompt, env, None, extra, on_line)


def run_codex(model: str, effort: str, cwd: Path, prompt_stream, receipt, supported_efforts: dict[str, list[str]],
              no_tools: bool = False, write: bool = False, tools: bool = False, write_dir: Path | None = None,
              env: dict | None = None, lead_dir: Path | None = None, home_repo: str | None = None,
              extra_deny: tuple = (), isolate_home: bool = False, thread_out: dict | None = None,
              resume_thread: str | None = None, worker: tuple | None = None, extra_read: tuple = (),
              network: bool = False, timeout_s: float | None = None, on_line=None, host_tools: bool = False) -> int:
    """timeout_s: kill the child's process group after that many seconds and return 124 (None: no deadline).
    on_line (spec 027): called with each JSONL stdout line while the child runs; json mode only.
    thread_out (D54): run with `--json -o`, store the thread id in thread_out["thread_id"], and write the last
    message, not the JSONL, to stdout. resume_thread: continue that thread with the prompt as the next turn."""
    if receipt.codex_path is None:
        raise FileNotFoundError("WB_CLI_NOT_FOUND: Codex not installed (receipt has no codex_path); install codex, then run agents-inc repair")
    executable = Path(receipt.codex_path)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise FileNotFoundError("WB_CLI_NOT_FOUND: recorded Codex executable missing; run agents-inc repair")

    # Resolve model slug using same logic as build_codex_argv
    model_map = load_model_map()
    slug = model_map.get(model, model if model in supported_efforts else None)
    if not slug:
        raise ValueError(f"unknown Codex model alias: {model}")

    if lead_dir is not None:
        if no_tools:
            raise ValueError("--lead excludes --no-tools")
        tools = True  # --lead implies tools on; lead_args refuses luna and raw slugs
        if write_dir is not None:
            raise ValueError("--lead excludes --run-dir (the run directory is broker-owned)")
        if write and Path(os.path.realpath(lead_dir)).is_relative_to(Path(os.path.realpath(cwd))):
            raise ValueError("--lead --write needs the run directory outside cwd (D57)")
        lead_args(model, lead_dir)  # fail before any launch
    tools = tools_for(model, no_tools, tools)
    if write and not tools:
        raise ValueError("--write needs --tools (astra, sol, terra, or luna with --tools; without --no-tools)")
    if write_dir is not None and not tools:
        raise ValueError("--run-dir needs tools")
    if network and (not tools or lead_dir is not None):
        raise ValueError("--network needs tools on and no --lead")
    if host_tools and tools:
        raise ValueError("--host-tools needs tools off")
    if resume_thread is not None and lead_dir is not None:
        raise ValueError("--lead runs cannot be resumed")
    json_mode = thread_out is not None or resume_thread is not None
    host_catalog = None
    if host_tools:
        # Fail closed before anything is created: no cache entry means no stripped catalog (spec 028 FR-011), and
        # Codex's own catalog would give luna exec and apply_patch. The catalog is built from the real Codex home
        # first, because the isolated home below holds no models_cache.json.
        try:
            host_catalog = require_host_tools_catalog(slug)
        except HostToolsCatalogMissing as exc:
            sys.stderr.write(f"agents-inc run: {exc}\n")
            sys.stderr.flush()
            return 3
    # A host-tools run loads no operator MCP server or config either (spec 028 FR-013): the Lead's isolated home.
    lead_home = lead_codex_home(slug) if (lead_dir is not None or isolate_home or host_tools) else None
    cleanup_failed = False
    out_dir = tool_tmp = None
    try:
        if tools:  # #66: tool commands get their own writable temp dir (heredocs, scratch files)
            tmp_root = (env or {}).get("TMPDIR")
            tool_tmp = Path(tempfile.mkdtemp(prefix="agents-inc-tool-tmp-",
                                             dir=tmp_root if tmp_root and os.path.isdir(tmp_root) else None))
        if json_mode:  # the -o file goes to the Worker TMPDIR under the broker, else a private temp dir
            tmp_root = (env or {}).get("TMPDIR")
            out_dir = Path(tempfile.mkdtemp(prefix="agents-inc-codex-out-",
                                            dir=tmp_root if tmp_root and os.path.isdir(tmp_root) else None))
        json_out = out_dir / "last_message.md" if out_dir is not None else None
        sys.stderr.write("agents-inc run: record " + json.dumps({"model": model, "slug": slug, "tools": "on" if tools else "off",
                         "sandbox": "workspace-write" if write else "read-only",
                         **({"network": "on"} if network else {}),
                         **({"transport": "mcp"} if lead_dir is not None else {}),
                         **({"catalog": "host-tools", "catalog_path": str(host_catalog)} if host_catalog is not None else {}),
                         **({"codex_home": "isolated"} if lead_home is not None else {})}) + "\n")
        deny = tuple(extra_deny)
        if lead_home is not None:
            if lead_dir is not None:
                env = lead_env(executable, lead_home, env)
                deny += (Path(lead_dir).resolve(),)  # the run directory is broker-owned: unreadable to the Lead
            else:  # a broker-launched Worker keeps its scrubbed env; only CODEX_HOME is added
                env = {**(os.environ if env is None else env), "CODEX_HOME": str(lead_home)}
            if not host_tools:  # a tool-free run has no tool to deny; the deny profile would replace `-s read-only`
                deny += (lead_home,)
        prompt = prompt_stream.read()  # text, never the stream: StringIO has no fileno
        extra = {}
        if resume_thread is not None:
            argv = build_codex_resume_argv(executable, resume_thread, prompt, model, effort, cwd, supported_efforts,
                                           model_map, tools, write, write_dir, deny, json_out, worker,
                                           extra_read=extra_read, network=network, tool_tmp=tool_tmp,
                                           host_tools=host_tools, host_catalog=host_catalog)
            prompt, extra = "", {"cwd": str(cwd)}  # the message rides the PROMPT positional; resume has no -C
        else:
            argv = build_codex_argv(executable, model, effort, cwd, supported_efforts, model_map, tools, write, write_dir,
                                    lead_dir, deny, lead_home, home_repo, json_out, worker, extra_read=extra_read,
                                    network=network, tool_tmp=tool_tmp, host_tools=host_tools, host_catalog=host_catalog)
        line_cb = on_line if json_mode else None  # Lead runs (no --json) get lifecycle events only
        if timeout_s:
            result = _run_with_deadline(argv, prompt, env, timeout_s, extra, line_cb)
        elif line_cb is not None:
            result = _run_streaming(argv, prompt, env, extra, line_cb)
        else:
            result = subprocess.run(
                argv,
                input=prompt,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                env=env,  # None inherits (CLI default); the D51 broker passes a scrubbed env
                **extra,
            )
        stdout, json_errors = result.stdout, []
        if json_mode:
            tid = parse_thread_id(result.stdout)
            if thread_out is not None and tid:
                thread_out["thread_id"] = tid
            json_errors = _json_errors(result.stdout)
            try:
                stdout = json_out.read_text(encoding="utf-8")
            except OSError:
                stdout = ""
    finally:
        for d in (out_dir, tool_tmp):
            if d is not None:
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except OSError:
                    pass
        if lead_home is not None:
            auth = lead_home / "auth.json"
            if auth.exists() and not auth.is_symlink():  # Codex replaced the link with a real credential file
                sys.stderr.write("agents-inc run: isolated CODEX_HOME kept: auth.json is no longer a symlink\n")
                cleanup_failed = True
            else:
                try:
                    shutil.rmtree(lead_home)  # removes the symlinks, never their targets
                except OSError:
                    pass
                if lead_home.exists():
                    sys.stderr.write(f"agents-inc run: isolated CODEX_HOME not removed: {lead_home}\n")
                    cleanup_failed = True

    # Write captured output unchanged (in --json mode: the last message, and the error events on stderr)
    sys.stdout.write(stdout)
    sys.stdout.flush()
    sys.stderr.write(result.stderr)
    if json_errors:
        sys.stderr.write("\n".join(json_errors) + "\n")
    sys.stderr.flush()

    # Check for usage/rate limit errors only in ERROR lines
    for line in result.stderr.split('\n') + json_errors:
        stripped = line.lstrip()
        if stripped.startswith('ERROR:'):
            # Case-insensitive regex match for rate limit patterns
            if QUOTA_RE.search(stripped):
                # Extract retry time from this ERROR line
                match = re.search(r'try again at ([^\.\n]+)', line)
                retry_time = match.group(1) if match else "unknown"

                # Print error message
                error_msg = f"agents-inc run: codex {slug} hit a usage or rate limit; retry at {retry_time}"
                sys.stderr.write(error_msg + "\n")
                sys.stderr.flush()

                # Report to free_health
                try:
                    from agents_inc import free_health
                    free_health.report("codex", slug, "rate_limited", message=error_msg)
                except Exception:
                    pass

                return 75

    # Check for empty output with success exit code
    if result.returncode == 0 and not stdout.strip():
        sys.stderr.write(f"agents-inc run: codex {slug} returned an empty reply\n")
        sys.stderr.flush()
        return 1

    # Return original exit code; a leaked isolated CODEX_HOME turns success into failure
    return 1 if cleanup_failed and result.returncode == 0 else result.returncode


def thread_progress_line(line: str) -> None:
    """`agents-inc run --thread`: one stderr line per reasoning or agent_message item and per turn usage, flushed
    as the JSONL line arrives. Other lines are ignored."""
    try:
        event = json.loads(line)
    except ValueError:
        return
    if not isinstance(event, dict):
        return
    out = None
    if event.get("type") == "item.completed" and isinstance(event.get("item"), dict):
        item = event["item"]
        if item.get("type") in ("reasoning", "agent_message"):
            out = "agents-inc run: event " + json.dumps({"kind": item["type"], "text": item.get("text")})
    elif event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
        out = "agents-inc run: usage " + json.dumps(event["usage"])
    if out is not None:
        sys.stderr.write(out + "\n")
        sys.stderr.flush()


NOT_TOOL_ITEMS = ("reasoning", "agent_message", "error")


def count_codex_tool_call(line: str, counts: dict[str, int]) -> None:
    """Spec 028 FR-014: add one to counts for each completed Codex-side tool item in a JSONL line, keyed by the tool
    name (MCP calls) or the item type (command_execution, file_change, ...). Codex's own tools are the ones a
    host-tools run must not use; the host's tools travel in the reply text and never appear here."""
    try:
        event = json.loads(line)
    except ValueError:
        return
    item = event.get("item") if isinstance(event, dict) and event.get("type") == "item.completed" else None
    if not isinstance(item, dict) or item.get("type") in NOT_TOOL_ITEMS: return
    name = item.get("tool") or item.get("name") or item.get("type")
    if isinstance(name, str): counts[name] = counts.get(name, 0) + 1


def thread_rollout(tid: str, sessions: Path | None = None) -> Path | None:
    """The rollout file of Codex thread tid under the real Codex sessions dir (host-tools runs link theirs there)."""
    root = sessions or real_codex_home() / "sessions"
    found = sorted(root.glob(f"**/rollout-*{tid}.jsonl")) if tid and root.is_dir() else []
    return found[-1] if found else None


def rui_calls(rollout: Path, offset: int = 0) -> list:
    """The parsed arguments of every request_user_input call in the rollout from byte offset on (None when they do not
    parse). Codex refuses each call in Default mode and its --json stream never shows one, so the rollout is the only
    place they can be counted (spec 028 FR-014)."""
    out: list = []
    try:
        with rollout.open("rb") as f:
            f.seek(offset)
            data = f.read().decode("utf-8", "replace")
    except OSError:
        return out
    for line in data.splitlines():
        try:
            payload = json.loads(line).get("payload") or {}
            if payload.get("type") != "function_call" or payload.get("name") != "request_user_input": continue
        except (ValueError, AttributeError):
            continue
        try:
            out.append(json.loads(payload.get("arguments") or ""))
        except ValueError:
            out.append(None)
    return out


def rui_replies(calls: list) -> list[str]:
    """Host tool requests luna sent as request_user_input calls: each call whose arguments are a JSON object with a
    "tools" list, as that JSON text. Codex refuses the call, so the request never reaches the host unless the run
    replays it."""
    return [json.dumps(a) for a in calls if isinstance(a, dict) and isinstance(a.get("tools"), list) and a["tools"]]


def run_codex_thread(thread_file: Path, *args, **kwargs) -> int:
    """`agents-inc run --thread FILE`: FILE missing or empty starts a new thread, FILE holding a thread id resumes
    it with the prompt as the next message. After the run the thread id (new or resumed) is written to FILE.
    When Codex used any tool of its own, one `agents-inc run: tools {...}` line with the counts closes the run."""
    thread_file = Path(thread_file)
    try:
        known = thread_file.read_text(encoding="utf-8").strip()
    except OSError:
        known = ""
    thread_out: dict = {}
    tool_counts: dict[str, int] = {}
    # luna sent its host tool requests as request_user_input calls and then reported that the results never came
    # (spec 028 Docker runs): a host-tools run replays those requests as agent_message events after the run.
    host_tools = bool(kwargs.get("host_tools"))
    before = thread_rollout(known) if host_tools and known else None
    offset = before.stat().st_size if before else 0

    def on_line(line: str) -> None:
        thread_progress_line(line)
        count_codex_tool_call(line, tool_counts)

    rc = run_codex(*args, thread_out=None if known else thread_out, resume_thread=known or None,
                   on_line=on_line, **kwargs)
    tid = known or thread_out.get("thread_id")
    rollout = thread_rollout(tid) if host_tools and tid else None
    calls = rui_calls(rollout, offset if rollout == before else 0) if rollout else []
    if calls:
        tool_counts["request_user_input"] = tool_counts.get("request_user_input", 0) + len(calls)
    if tool_counts:
        sys.stderr.write("agents-inc run: tools " + json.dumps(tool_counts) + "\n")
    for text in rui_replies(calls):
        sys.stderr.write("agents-inc run: event " + json.dumps({"kind": "agent_message", "text": text}) + "\n")
    sys.stderr.flush()
    if tid:
        thread_file.parent.mkdir(parents=True, exist_ok=True)
        thread_file.write_text(tid + "\n", encoding="utf-8")
    return rc
