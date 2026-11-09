"""`agents-inc dispatch`: render, lint, snapshot, launch, and verify one delegation (D45, D46, D47).

Only the status line goes to stdout. Everything else lands in the run directory.
"""
from __future__ import annotations
import base64
import contextlib
import fcntl
import hashlib
import hmac
import importlib.util
import io
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import stat
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

from agents_inc.datafiles import repo_file, repo_root

from . import free_launch, live_events
from .live_events import EventSink, _stream_run
from .runtime import QUOTA_PATTERN, kill_and_reap

_LIVE_SINK: EventSink | None = None  # spec 027: events.jsonl writer of the dispatch run in progress
EXIT_CANCELLED = 130  # spec 027 FR-011: the shell's code for a run ended by SIGINT
CANCEL_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
CANCEL_GRACE_S = 5.0  # `--cancel`: seconds between SIGTERM and SIGKILL


class Cancelled(BaseException):
    """A termination signal reached the dispatch run. BaseException: the launch-failed handler must not swallow it."""

REPO_ROOT = repo_root()
SCRIPTS = repo_file("skills/workerbee/scripts")

CODEX_SLUGS = ("astra", "sol", "terra", "luna")
# Exact Claude model ids passed to `claude -p --model`. Keep this the only table.
CLAUDE_MODELS = {"fable": "claude-fable-5-1", "opus": "claude-opus-5-5",
                 "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
# Slot placeholder for the snapshot path; the wrapper fills it after capture.
SNAPSHOT_PLACEHOLDER = "<snapshot>"
FREE_SLUGS = ("gemini", "mistral", "openrouter")
DEFAULT_PERMISSION_MODE = "acceptEdits"
EXIT_OK, EXIT_RED, EXIT_USAGE, EXIT_REFUSED = 0, 1, 2, 3
EXIT_BLOCKED, EXIT_QUOTA = 69, 75  # sysexits EX_UNAVAILABLE; the Codex usage-limit code of runtime.run_codex


def _load(name: str, scripts: Path = SCRIPTS):
    path = Path(scripts) / f"{name}.py"
    if Path(scripts) != SCRIPTS:
        _check_pinned(path)
    spec = importlib.util.spec_from_file_location(f"_agents_inc_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 025 (#104): a dispatch from an agents-inc checkout is judged by the checkout's workerbee scripts, pinned at launch.
PINNED_SCRIPTS = ("check_dispatch_prompt.py", "render_dispatch.py", "dispatch_rungs.py", "pre_dispatch_snapshot.py",
                  "dispatch_schema.py")
PINNED_TEMPLATES = ("header.md", "slots.md")  # render_dispatch.py reads these from the directory above its own


class ScriptsTampered(RuntimeError):
    """025 (#104): a trusted copy of a checkout script no longer matches the sha256 recorded at launch."""


def scripts_dir(cwd: Path) -> tuple[Path, str]:
    """(<cwd>/skills/workerbee/scripts, "checkout") when cwd holds agents_inc/install/dispatch.py and the four
    workerbee scripts as regular files (a symlink counts as missing) and is not inside the installed bundle;
    else (SCRIPTS, "installed")."""
    scripts = Path(cwd) / "skills/workerbee/scripts"
    probes = [Path(cwd) / "agents_inc/install/dispatch.py"] + [scripts / n for n in PINNED_SCRIPTS]
    if (not Path(cwd).resolve().is_relative_to(REPO_ROOT.resolve())
            and all(p.is_file() and not p.is_symlink() for p in probes)):
        return scripts, "checkout"
    return SCRIPTS, "installed"


def _slot_str(name: str, value) -> str:
    """#131: the string form of a slot that may be structured (FILES_IN_SCOPE and ALLOWLIST arrays, FAN_OUT object)."""
    if isinstance(value, list):
        return "\n".join(str(v) for v in value) if name == "FILES_IN_SCOPE" else ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return f"width {value.get('width')}, total {value.get('total')}, depth {value.get('depth')}"
    return str(value)


def _pin_scripts(src: Path, run_id: str) -> Path:
    """Copy the checkout scripts (and the render templates) into the run's private trust folder, outside cwd, and
    record each file's sha256 in its trust.json. Return the trusted scripts directory. Raises OSError."""
    folder = _trust_path(run_id)
    dest = folder / "workerbee" / "scripts"
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    hashes = {}
    for name in PINNED_SCRIPTS + PINNED_TEMPLATES:
        origin = (src if name in PINNED_SCRIPTS else src.parent) / name
        if name in PINNED_TEMPLATES and not (origin.is_file() and not origin.is_symlink()):
            origin = SCRIPTS.parent / name
        data = origin.read_bytes()
        (dest if name in PINNED_SCRIPTS else dest.parent).joinpath(name).write_bytes(data)
        hashes[name] = _sha256_bytes(data)
    (folder / "trust.json").write_text(json.dumps({"schema_version": 1, "scripts_sha256": hashes}, indent=1) + "\n",
                                       encoding="utf-8")
    return dest


def _check_pinned(path: Path, folder: Path | None = None) -> None:
    """Raise ScriptsTampered unless path's sha256 matches scripts_sha256 in <folder>/trust.json; folder defaults to
    the trust folder of a script under <folder>/workerbee/scripts/."""
    try:
        record = json.loads(((folder or path.parent.parent.parent) / "trust.json").read_text(encoding="utf-8"))
        ok = _sha256_bytes(path.read_bytes()) == record["scripts_sha256"][path.name]
    except (OSError, ValueError, KeyError, TypeError):
        ok = False
    if not ok:
        raise ScriptsTampered(f"{path.name} differs from its trusted record")


def _scripts(spec: dict | None) -> Path:
    """The directory a run loads workerbee scripts from: its trusted copy for a checkout run, else SCRIPTS."""
    if spec and spec.get("scripts_source") == "checkout" and spec.get("scripts_dir"):
        return Path(spec["scripts_dir"])
    return SCRIPTS


def _scripts_tampered(scripts: Path) -> str | None:
    """Why a trusted copy fails its hash check, else None (always None for the installed bundle)."""
    if Path(scripts) == SCRIPTS:
        return None
    try:
        for name in PINNED_SCRIPTS:
            _check_pinned(Path(scripts) / name)
        for name in PINNED_TEMPLATES:
            _check_pinned(Path(scripts).parent / name, Path(scripts).parent.parent)
    except ScriptsTampered as exc:
        return str(exc)
    return None


# Set by _in_worker_scope: (scripts_dir, scripts_source) of the Lead, which a broker Worker inherits and never probes.
_INHERITED_SCRIPTS: tuple | None = None


def default_parent(cwd: Path | None = None) -> Path:
    """<cwd>/.scratch/agents-inc-runs when git ignores <cwd>/.scratch: a delegate under acceptEdits can write
    there, never outside cwd. Else the session scratchpad, TMPDIR, or /tmp."""
    if cwd is not None and Path(cwd).is_dir():  # #154: .scratch need not exist yet; the pane lists it under cwd
        with contextlib.suppress(OSError):
            res = subprocess.run(["git", "-C", str(cwd), "check-ignore", "-q", ".scratch/"], capture_output=True)
            if res.returncode == 0:
                return Path(cwd) / ".scratch" / "agents-inc-runs"
    base = os.environ.get("CLAUDE_SCRATCHPAD") or os.environ.get("TMPDIR") or "/tmp"
    return Path(base) / "agents-inc-runs"


def _run_dir_ignored(parent: Path, cwd: Path) -> bool:
    """025 (#106): False only when parent sits inside cwd and git says it is not ignored. Outside cwd, no git,
    or cwd not a repo: True (the snapshot capture reports a missing repo)."""
    if not parent.is_relative_to(cwd):
        return True
    try:  # trailing slash: a not-yet-created directory still matches a `runs/` rule
        res = subprocess.run(["git", "-C", str(cwd), "check-ignore", "-q", str(parent.relative_to(cwd)) + "/"],
                             capture_output=True)
    except OSError:
        return True
    return res.returncode != 1


HOME_REPO_RE = re.compile(r"agents-inc home repo:\s*(\S+)", re.IGNORECASE)


def resolve_home_repo(home_repo: str | None, cwd: Path | None) -> str | None:
    """D46 ruling 8: --home-repo, then AGENTS_INC_HOME_REPO, then the first `agents-inc home repo: <path>` line
    in <cwd>/AGENTS.md (the path may start with ~)."""
    if home_repo:
        return home_repo
    if os.environ.get("AGENTS_INC_HOME_REPO"):
        return os.environ["AGENTS_INC_HOME_REPO"]
    try:
        text = (Path(cwd) / "AGENTS.md").read_text(encoding="utf-8") if cwd is not None else ""
    except (OSError, UnicodeDecodeError):
        return None
    m = HOME_REPO_RE.search(text)
    return str(Path(m.group(1).strip("`'\"")).expanduser()) if m else None


def new_run_id(model: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)  # spec 037: an OpenRouter slug holds `/` and `:`; a run id is one path part
    return f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{safe}-{secrets.token_hex(3)}"


def render(slots_path: Path, model: str | None = None, scripts: Path = SCRIPTS) -> tuple[int, str, str]:
    """Render via render_dispatch.main() in-process; return (rc, prompt, stderr)."""
    module = _load("render_dispatch", scripts)
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    sys.argv = ["render_dispatch.py", "--slots", str(slots_path)] + (["--model", model] if model else [])
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = module.main()
    finally:
        sys.argv = saved
    return rc, out.getvalue(), err.getvalue()


def _handoff_lint(module, path: Path, profile: str | None) -> tuple[int, str]:
    script = Path(os.environ.get("HOME", "")) / ".claude/skills/handoff-lint/scripts/handoff_lint.py"
    if not script.is_file():
        return 0, module.HANDOFF_WARNING + "\n"
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = module.run_handoff_lint(str(path), profile)
    return rc, err.getvalue()


def lint_prompt(path: Path, tier: str | None, model: str | None = None, scripts: Path = SCRIPTS) -> tuple[list, str]:
    """Return (missing contract elements, log). handoff-lint findings are advisory:
    they go to the log (lint.txt) and never add to `missing`, so they never refuse."""
    module = _load("check_dispatch_prompt", scripts)
    missing = module.check(path.read_text(encoding="utf-8"), tier, model=model)
    rc, log = _handoff_lint(module, path, None)
    if rc:
        log = f"handoff-lint advisory (rc={rc}, not a refusal)\n" + log
    return missing, log


def inject_snapshot(prompt: str, snapshot_path: str) -> str:
    """Put the real snapshot path into the prompt: replace every placeholder,
    else append a `SNAPSHOT: <path>` line."""
    if SNAPSHOT_PLACEHOLDER in prompt:
        return prompt.replace(SNAPSHOT_PLACEHOLDER, snapshot_path)
    return prompt.rstrip("\n") + f"\nSNAPSHOT: {snapshot_path}\n"


def lint_report(path: Path, scripts: Path = SCRIPTS) -> tuple[list, str]:
    module = _load("check_dispatch_prompt", scripts)
    missing = module.check_report(path.read_text(encoding="utf-8"))
    rc, log = _handoff_lint(module, path, "report")
    if rc:
        log = f"handoff-lint advisory (rc={rc}, not a refusal)\n" + log
    return missing, log


def snapshot(*args: str, cwd: Path, scripts: Path = SCRIPTS) -> tuple[int, str]:
    script = Path(scripts) / "pre_dispatch_snapshot.py"
    if Path(scripts) != SCRIPTS:
        _check_pinned(script)
    res = subprocess.run([sys.executable, str(script), *args],
                         cwd=str(cwd), capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr


def allow_paths(files_in_scope: str) -> list[str]:
    """Paths named in the FILES_IN_SCOPE slot; prose such as "none (read-only)" yields nothing."""
    out = []
    for token in re.split(r"[\s,;]+", files_in_scope or ""):
        token = token.strip("`'\"()")
        if token and ("/" in token or "." in token) and not token.endswith((":", ".")):  # "Read:", "file." are prose
            out.append(token)
    return out


def scope_globs(files_in_scope: str) -> list[str]:
    """Tokens of FILES_IN_SCOPE that hold a glob character. The scope gate compares exact paths, so a glob never matches."""
    tokens = (t.strip("`'\"()") for t in re.split(r"[\s,;]+", files_in_scope or ""))
    return [t for t in tokens if t and any(ch in t for ch in "*?[")]


def claude_argv(model: str, permission_mode: str, resume: str | None = None, effort: str | None = None,
                allowed: list | None = None, disallowed: list | None = None) -> list[str]:
    exe = shutil.which("claude") or "claude"
    argv = [exe, "-p", "--model", CLAUDE_MODELS[model], "--permission-mode", permission_mode,
            "--output-format", "stream-json", "--verbose"]
    if effort:
        argv += ["--effort", effort]
    if resume:
        argv += ["--resume", resume]
    if allowed:
        argv += ["--allowedTools", *allowed]
    if disallowed:
        argv += ["--disallowedTools", *disallowed]
    return argv


def _bash(prefix: str) -> list[str]:
    """The two Bash rules for one command prefix: the bare command and the command with arguments."""
    return [f"Bash({prefix})", f"Bash({prefix} *)"]


# D60: (allowed, disallowed) of the Claude Lead whose broker runs this Worker, else None. Set by _in_worker_scope.
_GRANT_CEILING: tuple | None = None


def _verifier_rules(spec: dict, run_dir) -> list[str]:
    """The two snapshot-verifier Bash pairs of one run; their paths are run-specific."""
    snap = spec["snapshot"]
    return (_bash(f"python3 {run_dir}/pre_dispatch_snapshot.py verify {snap}")
            + _bash(f"python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify {snap}"))


def tool_grants(spec: dict, gates: list | None, bash_allow: list, run_dir) -> tuple[list, list]:
    """Per-run Claude tool grants (D58): (allowed, disallowed), order-preserving and deduplicated. Test runners only
    when FILES_IN_SCOPE names paths. Never grants `agents-inc` Bash. Under a Lead's broker (D60, _GRANT_CEILING) a
    runner is kept only when the Lead has it, GATES argv is not granted (broker children skip gates), and the
    disallowed list gains the Lead's."""
    ceiling = _GRANT_CEILING
    allowed = ["Read", "Glob", "Grep"]
    for prefix in ("git status", "git diff", "git log", "git show", "git ls-files", "git check-ignore"):
        allowed += _bash(prefix)
    allowed += ["Bash(claude --help)"]
    allowed += _verifier_rules(spec, run_dir)
    if spec["gates"]["allow"]:
        for prefix in ("python3 -m unittest", "python3 -m pytest", "pytest"):
            allowed += [r for r in _bash(prefix) if ceiling is None or r in ceiling[0]]
    if ceiling is None:
        allowed += [f"Bash({shlex.join(g['argv'])})" for g in gates or []]
    for prefix in bash_allow:
        allowed += _bash(prefix)
    disallowed = (_bash("git push") + _bash("git commit") + _bash("sudo") + ["WebFetch", "WebSearch", "Agent", "Task"]
                  + (list(ceiling[1]) if ceiling else []))
    return list(dict.fromkeys(allowed)), list(dict.fromkeys(disallowed))


def grants_section(allowed: list, disallowed: list, bash_allow: list, permission_mode: str | None = None) -> str:
    """The GRANTS block rendered into every Claude delegate prompt so a missing grant reads as one (#54)."""
    prefixes = ", ".join(f"`{p}`" for p in bash_allow) or "none"
    text = ("\nGRANTS (fixed by dispatch for this run; the harness allows exactly these tools):\n"
            f"ALLOWED: {', '.join(allowed) or 'none'}\n"
            f"BASH_ALLOW prefixes (each also allowed with arguments): {prefixes}\n"
            f"DENIED: {', '.join(disallowed) or 'none'}\n"
            "A call outside ALLOWED stops with a harness message such as \"This command requires approval\": that is a "
            "missing grant, not a policy refusal. Stop, record the exact command, and hand back; never route around it. "
            "One plain command per Bash call: no cd, &&, ;, pipes, loops, or shell variables; a compound command "
            "matches no grant.\n")
    if permission_mode == "acceptEdits":
        text += "Edit and Write on files under --cwd come from PERMISSION_MODE acceptEdits: they work though ALLOWED does not list them.\n"
    return text


def ceiling_violation(allowed: list, own: list = ()) -> str | None:
    """D60: the first allowed rule the Lead does not hold, else None. own: this run's verifier rules (run-specific)."""
    if _GRANT_CEILING is None:
        return None
    return next((r for r in allowed if r not in _GRANT_CEILING[0] and r not in own), None)


# D51 Claude Worker confinement (mirrors D49), applied only under the broker.
WORKER_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
# USER is required: without it `claude auth status` reports loggedIn false (keychain account lookup).
WORKER_ENV_KEYS = ("HOME", "USER", "TERM", "LANG", "TMPDIR")
SECRET_ENV_RE = re.compile(r"KEY|TOKEN|SECRET", re.IGNORECASE)
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
# Same-vendor exception: ~/.claude stays readable and writable for the Claude Worker; ~/.codex is denied.
CLAUDE_WORKER_DENY = (".ssh", ".config", ".codex-bridge", ".codex", ".local", ".aws", ".gnupg", ".netrc")

# #94: a broker Claude Worker already runs under our seatbelt. Its own Claude Code Bash sandbox would nest sandbox-exec
# (rc 71, sandbox_apply: Operation not permitted), so the Worker turns that sandbox off for itself.
WORKER_SETTINGS = '{"sandbox": {"enabled": false}}'
# #94: AGENTS_INC_ALLOW_SANDBOXED=1 lets dispatch start inside another sandbox (tests, a caller that knows better).
ALLOW_SANDBOXED_ENV = "AGENTS_INC_ALLOW_SANDBOXED"
SANDBOX_FIX = ('do not retry unchanged; two routes: (a) rerun as one plain command with no cd, &&, ;, pipe, redirect, heredoc or $(...) '
               '(add "agents-inc *" to sandbox.excludedCommands); (b) for Claude rungs set '
               'sandbox.network.allowedDomains ["api.anthropic.com"] in ~/.claude/settings.json')
CODEX_NESTED_FIX = "Codex cannot nest a sandbox (rc 71); run as one plain `agents-inc ...` command"
PROBE_HOST, PROBE_TIMEOUT = "api.anthropic.com", 2.0
_SANDBOX_NOTE: dict = {}  # run.json fields launch() sets when it proceeds inside a Claude Code sandbox


class CallerSandboxed(RuntimeError):
    """#94: dispatch itself runs inside another sandbox: the delegate would lose its network, so no child starts."""

    def __init__(self, where="", fix=None, code="caller-sandboxed"):
        super().__init__(where)
        self.fix, self.code = fix, code


def caller_sandbox(env=None) -> str | None:
    """#94: name the sandbox this dispatch process runs in, else None. ALLOW_SANDBOXED_ENV=1 skips the check."""
    env = os.environ if env is None else env
    if env.get(ALLOW_SANDBOXED_ENV) == "1":
        return None
    if env.get("SANDBOX_RUNTIME"):
        return "SANDBOX_RUNTIME is set (Claude Code Bash sandbox)"
    if env.get("CODEX_SANDBOX"):
        return "CODEX_SANDBOX is set (Codex sandbox)"
    return None


def api_reachable(env=None, timeout: float = PROBE_TIMEOUT, target: str = PROBE_HOST, port: int = 443) -> bool:
    """HTTP CONNECT to target:port through HTTPS_PROXY. True only on a 200 status line; anything else is False."""
    import base64 as _b64, socket, urllib.parse
    env = os.environ if env is None else env
    raw = env.get("HTTPS_PROXY") or env.get("https_proxy")
    if not raw:
        return False
    try:
        u = urllib.parse.urlsplit(raw if "//" in raw else "//" + raw)
        host, pport = u.hostname, u.port
        if not host or not pport:
            return False
        head = f"CONNECT {target}:{port} HTTP/1.1\r\nHost: {target}:{port}\r\n"
        if u.username is not None:
            cred = f"{urllib.parse.unquote(u.username)}:{urllib.parse.unquote(u.password or '')}"
            head += "Proxy-Authorization: Basic " + _b64.b64encode(cred.encode()).decode() + "\r\n"
        with socket.create_connection((host, pport), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((head + "\r\n").encode())
            buf = b""
            while b"\n" not in buf and len(buf) < 4096:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buf += chunk
        parts = buf.split(b"\n", 1)[0].decode("latin-1").split()
        return len(parts) >= 2 and parts[1] == "200"
    except Exception:
        return False


def worker_env(exe: str, base: dict | None = None) -> dict:
    """Explicit minimal env for a broker-launched Claude Worker: fixed PATH plus the claude directory,
    HOME, USER, TERM, LANG, TMPDIR. Nothing else passes, so no *KEY*/*TOKEN*/*SECRET* or bridge token."""
    base = os.environ if base is None else base
    env = {"PATH": WORKER_PATH + ":" + os.path.dirname(os.path.abspath(exe))}
    for key in WORKER_ENV_KEYS:
        if key in base:
            env[key] = base[key]
    env["AGENTS_INC_WORKER"] = "1"
    if env.get("TMPDIR"):
        tmp = env["TMPDIR"].rstrip("/")
        env["XDG_CACHE_HOME"] = tmp + "/cache"
        env["npm_config_cache"] = tmp + "/npm"
        env["PIP_CACHE_DIR"] = tmp + "/pip"
    return {k: v for k, v in env.items() if not SECRET_ENV_RE.search(k)}


def _sb(path) -> str:
    text = os.path.realpath(str(path))
    if any(ch in text for ch in ('"', "\\", "\n")):
        raise ValueError(f"path not expressible in sandbox profile: {text!r}")
    return text


# ~/.claude subpaths a Claude Worker may read and write; everything else under ~/.claude and
# ~/.claude.json* is denied (no credentials or api key cache in reports). Login comes from the keychain.
CLAUDE_HOME_ALLOW = ("projects", "todos", "statsig")
# Read-only: settings.json hooks run scripts from here; an unreadable hook fails closed and blocks tools.
# settings.json is read-only so a Worker cannot persist hooks for later unsandboxed sessions.
CLAUDE_HOME_READ = ("scripts", "settings.json")


_SANDBOX_OK: bool | None = None  # probe result, cached for the process


def sandbox_available() -> bool:
    """True when sandbox-exec exists and can start a process. Inside another sandbox it exists but fails."""
    global _SANDBOX_OK
    if sys.platform != "darwin" or not os.access(SANDBOX_EXEC, os.X_OK):
        return False
    if _SANDBOX_OK is None:
        try:
            probe = subprocess.run([SANDBOX_EXEC, "-p", "(version 1)(allow default)", "/usr/bin/true"],
                                   capture_output=True, timeout=10)
            _SANDBOX_OK = probe.returncode == 0
        except (OSError, subprocess.SubprocessError):
            _SANDBOX_OK = False
    return _SANDBOX_OK


def _turn_timeout() -> float | None:
    """Per-turn deadline in seconds: AGENTS_INC_TURN_TIMEOUT_S, default 3600; 0 (or a bad value) means none."""
    raw = os.environ.get("AGENTS_INC_TURN_TIMEOUT_S", "3600")
    try:
        value = float(raw)
    except ValueError:
        value = 3600.0
    return value if value > 0 else None


def claude_scratch_dir() -> str:
    """Claude Code's Bash tool scratch root (/private/tmp/claude-<uid>); the only /private/tmp write grant."""
    return f"/private/tmp/claude-{os.getuid()}"


# #94: with the Worker's Bash sandbox off (WORKER_SETTINGS), Claude Code writes its shell cwd file to /tmp/claude-<hex>-cwd.
CLAUDE_CWD_FILE_RE = r"^/private/tmp/claude-[0-9a-f]+-cwd$"


def _ancestors_between(root: Path, leaf: Path) -> list[Path]:
    """Folders from `root` down to, not including, `leaf`. Empty when `leaf` is not strictly inside `root`."""
    if root == leaf or root not in leaf.parents:
        return []
    return [root] + [p for p in reversed(leaf.parents) if root in p.parents and p != leaf]


def claude_sandbox_profile(cwd: Path, home: Path, tmpdir: str, deny_paths: tuple = (), write_ok: tuple = (),
                           read_ok: tuple = ()) -> str:
    """sandbox-exec profile: writes only to cwd, the child tmpdir, claude_scratch_dir(), /dev, the login keychain,
    Claude Code's /tmp/claude-<hex>-cwd file, and the CLAUDE_HOME_ALLOW subpaths; reads and writes denied under the
    D49 home deny list, ~/.claude.json*,
    and ~/.claude outside CLAUDE_HOME_ALLOW. deny_paths (the broker run directory, the Lead's isolated CODEX_HOME) are
    unreadable and unwritable except the child's own tmpdir, even when they sit under a granted cwd.
    D54: write_ok (the ask_lead channel) is also readable and writable; read_ok files (the ask_lead server and its
    config) are readable only."""
    h = _sb(home)
    claude_ok = [f"{h}/.claude/{name}" for name in CLAUDE_HOME_ALLOW]
    writable = [_sb(cwd), _sb(tmpdir), claude_scratch_dir(), f"{h}/Library/Keychains", "/dev"] + claude_ok
    writable += [_sb(w) for w in write_ok]
    keep = " ".join(f'(require-not (subpath "{w}"))' for w in writable)
    keep += f' (require-not (regex #"{CLAUDE_CWD_FILE_RE}"))'
    deny = " ".join(f'(subpath "{h}/{name}")' for name in CLAUDE_WORKER_DENY)
    claude_read = claude_ok + [f"{h}/.claude/{name}" for name in CLAUDE_HOME_READ]
    claude_keep = " ".join(f'(require-not (subpath "{w}"))' for w in claude_read)
    holes = "".join(f' (require-not (subpath "{_sb(p)}"))' for p in (tmpdir,) + tuple(write_ok))
    holes += "".join(f' (require-not (literal "{_sb(p)}"))' for p in read_ok)
    broker_deny = "".join(
        f'(deny file-read* file-write* (require-all (subpath "{_sb(d)}"){holes}))\n'
        for d in deny_paths)
    claude_write_denies = " ".join(f'(subpath "{h}/.claude/{n}")' for n in CLAUDE_HOME_READ)
    # #103: a path walk (git's realpath) stats every folder above a hole; metadata only, no names or contents.
    holes_at = [Path(_sb(p)) for p in (tmpdir,) + tuple(write_ok) + tuple(read_ok)]
    meta = []
    for d in deny_paths:
        for hole in holes_at:
            for a in _ancestors_between(Path(_sb(d)), hole):
                if str(a) not in meta:
                    meta.append(str(a))
    meta_allow = "".join(f'(allow file-read-metadata (literal "{a}"))\n' for a in meta)
    read_ok_write_deny = "".join(f'(deny file-write* (literal "{_sb(p)}"))\n' for p in read_ok)  # D4: holes lift write denies
    return ("(version 1)\n(allow default)\n"
            f"(deny file-write* (require-all {keep}))\n"
            + broker_deny + meta_allow + read_ok_write_deny +
            f"(deny file-read* file-write* {deny})\n"
            f'(deny file-read* file-write* (regex #"^{re.escape(h)}/\\.claude\\.json"))\n'
            f'(deny file-read* file-write* (require-all (subpath "{h}/.claude") {claude_keep}))\n'
            f'(deny file-write* {claude_write_denies})\n')


def _child_tmp(run_dir: Path, resume_turn: bool = False) -> Path:
    """Broker-owned per-child temp dir; the Worker's only TMPDIR (never inherited /tmp)."""
    tmp = Path(run_dir) / "tmp"
    if resume_turn and tmp.is_dir() and not tmp.is_symlink():
        return tmp.resolve()  # a resumed turn reuses the child's TMPDIR
    tmp.mkdir(mode=0o700)
    return tmp.resolve()


# D54 ask_lead channel: <child>/ask is the only broker-side path a Worker may write; the server script and its
# Claude config sit beside it, read-only to the Worker.
ASK_DIR = "ask"
WORKER_MCP = Path(__file__).resolve().parent / "worker_mcp.py"
ASK_TOOL = "mcp__agents_inc__ask_lead"
ASK_LEAD_NOTE = ("\nLEAD CHANNEL: to ask your Lead a question while you work, call the `ask_lead` tool of the `agents_inc` "
                 "MCP server (Claude: `mcp__agents_inc__ask_lead`; Codex: first call `tool_search` with query "
                 "\"agents_inc\", then `mcp__agents_inc__ask_lead`). It waits up to 30 minutes for the answer. "
                 "The Lead cannot message you otherwise.\n")


def _ask_channel(run_dir: Path, rid: str) -> dict:
    """Create <child>/ask and refresh the server copy and its Claude config (rewritten on every turn, so a
    Worker edit never survives into the next one). Return the paths the launch needs."""
    from .runtime import MCP_TOOL_TIMEOUT_SEC
    child = Path(run_dir)
    ask = child / ASK_DIR
    if ask.is_symlink():
        raise RuntimeError("ask-channel-is-symlink")
    ask.mkdir(mode=0o700, exist_ok=True)
    script = child / "worker_mcp.py"
    _replace_text(script, WORKER_MCP.read_text(encoding="utf-8"))
    args = [str(script.resolve()), "--run-dir", str(ask.resolve()), "--request-id", rid]
    config = child / "worker_mcp.json"
    _replace_text(config, json.dumps({"mcpServers": {"agents_inc": {
        "type": "stdio", "command": sys.executable, "args": args, "timeout": MCP_TOOL_TIMEOUT_SEC * 1000}}}, indent=1) + "\n")
    return {"ask": ask.resolve(), "script": script.resolve(), "config": config.resolve(), "rid": rid}


CODEX_WRITE_MODES = ("acceptEdits", "bypassPermissions")


def codex_write(slots: dict) -> bool:
    """A Codex delegate gets what a Claude subagent gets: tools and write access to cwd whenever PERMISSION_MODE
    (default acceptEdits) lets a Claude delegate edit. Slot CODEX_WRITE: no (or false) opts out; yes forces it on."""
    explicit = str(slots.get("CODEX_WRITE", "")).strip().lower()
    if explicit in ("yes", "true"):
        return True
    if explicit in ("no", "false"):
        return False
    return (slots.get("PERMISSION_MODE") or DEFAULT_PERMISSION_MODE) in CODEX_WRITE_MODES


def codex_network(slots: dict) -> bool:
    """#66: slot CODEX_NETWORK: yes (or true) gives a Codex delegate's tool commands outbound network access.
    Off by default. It needs tools, so it takes effect only with codex_write."""
    return str(slots.get("CODEX_NETWORK", "")).strip().lower() in ("yes", "true")


LEAD_NOTE_CODEX = ("\nWORKERS (D57): you may run Workers ({roster}) with the `agents_inc` MCP server's `dispatch`, `wait`, "
                   "`status`, `resume` and `answer` tools (Codex: call `tool_search` with query \"agents_inc\" first if they "
                   "are not listed). The `dispatch` tool description lists every slot a Worker request needs. Skill files "
                   "under ~/.agents/skills and ~/.local are not readable in this sandbox and are not needed: this prompt and "
                   "the tool descriptions carry the contract.\n")
LEAD_NOTE_CLAUDE = ("\nWORKERS (D60): you may run Workers ({roster}) with the `agents_inc` MCP server's tools "
                    "`mcp__agents_inc__dispatch`, `mcp__agents_inc__wait`, `mcp__agents_inc__status`, "
                    "`mcp__agents_inc__resume` and `mcp__agents_inc__answer`. The `dispatch` tool description lists every "
                    "slot a Worker request needs. A Worker runs one at a time and never leads: send its FAN_OUT as "
                    "'width 0, total 0, depth 0'. The Agent tool is not a route (D59); `agents-inc` is not a Bash command "
                    "for you.\n")
LEAD_RUNGS = ("astra", "sol", "terra", "fable", "opus", "sonnet")  # models that may lead; luna and haiku are Grunts and never delegate
LEAD_TOOLS = tuple(f"mcp__agents_inc__{t}" for t in ("dispatch", "status", "wait", "resume", "answer"))


def lead_roster(model: str, slots: dict, fan_out: dict | None, scripts: Path = SCRIPTS) -> list[str]:
    """#68 (D57, D60): a Codex or Claude delegate gets the broker on the same terms as a Claude delegate gets subagents: a FAN_OUT
    total above 0 (and, for Claude, depth above 0) and models named in SUB-DELEGATE MODEL ALLOWLIST. Keep only models the
    D46.3 rung rule allows: any lower rung, and a Workhorse only the Grunt rung. Empty list: no broker."""
    if model not in LEAD_RUNGS or not fan_out or fan_out.get("total", 0) <= 0:
        return []
    if _kind(model) == "claude" and fan_out.get("depth", 0) <= 0:
        return []
    rungs = _load("dispatch_rungs", scripts)
    text = _slot_str("ALLOWLIST", slots.get("ALLOWLIST", "")).lower()
    mine = rungs.LADDER.index(rungs.MODEL_RUNG[model])
    named = [m for m in (*CODEX_SLUGS, *CLAUDE_MODELS) if re.search(rf"\b{m}\b", text)]
    return [m for m in named if rungs.LADDER.index(rungs.MODEL_RUNG[m]) < mine
            and (rungs.MODEL_RUNG[model] != "workhorse" or rungs.MODEL_RUNG[m] == "grunt")]


def lead_grants(lead_dir) -> tuple[list, list]:
    """D60: the (allow, deny) rules a Claude Lead adds: the five broker tools; no Agent/Task; no Read/Edit of any broker
    run directory (`agents-inc-lead-*` siblings of its own: older runs are never removed and hold lead_mcp.json and Worker
    reports; absolute paths take a leading `/`: Read(//abs/**))."""
    parent = Path(lead_dir).parent
    return list(LEAD_TOOLS), ["Agent", "Task", f"Read(/{parent}/agents-inc-lead-*/**)", f"Edit(/{parent}/agents-inc-lead-*/**)"]


def lead_skip_reason(spec: dict, roster: list) -> str | None:
    """D60: why a Claude Lead gets no broker (recorded as run.json `lead_skipped`), else None."""
    fan = spec.get("fan_out")
    if not fan or fan["total"] <= 0:
        return "total-zero"
    if fan["depth"] <= 0:
        return "depth-zero"
    if not roster:
        return "no-roster"
    if spec["permission_mode"] == "bypassPermissions":
        return "bypass-permissions"  # an allow list does not bind there, so a broker would cap nothing
    return None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_lead_dir(spec: dict, roster: list[str], parent: dict | None = None) -> tuple[Path, str | None]:
    """#68: the broker run directory for a Lead, created outside cwd so the Lead's write grant never covers it.
    D60: with parent (run_dir, allowed_tools, disallowed_tools, home_repo) it is a Claude Lead's: its run.json binds the
    parent run and the sha256 of a fresh token, and lead_mcp.json (0600) starts the broker with the token in its env.
    Return (lead_dir, token); token is None without parent. The token is never written to the parent run."""
    lead_dir = Path(tempfile.mkdtemp(prefix=f"agents-inc-lead-{spec['run_id']}-")).resolve()
    if lead_dir.is_relative_to(Path(spec["cwd"]).resolve()):
        shutil.rmtree(lead_dir, ignore_errors=True)
        raise ValueError("lead-dir-inside-cwd: TMPDIR sits inside the delegate's cwd")
    data = {"schema_version": 1, "run_id": spec["run_id"], "model": spec["model"], "effort": spec["effort"],
            "cwd": spec["cwd"], "chain": spec["chain"], "worker_models": roster, "fan_out": spec["fan_out"],
            "permission_mode": spec["permission_mode"],
            "scripts_dir": spec.get("scripts_dir") or str(SCRIPTS), "scripts_source": spec.get("scripts_source") or "installed"}
    token = None
    if parent is not None:
        from .runtime import MCP_BROKER, MCP_TOOL_TIMEOUT_SEC
        token = secrets.token_hex(32)
        run_dir = os.path.realpath(parent["run_dir"])
        data.update(lead_kind="claude", parent_run_id=spec["run_id"], parent_run_dir=run_dir,
                    parent_token_sha256=_sha256(token), parent_allowed_tools=parent["allowed_tools"],
                    parent_disallowed_tools=parent["disallowed_tools"])
        args = [str(MCP_BROKER), "--run-dir", str(lead_dir)] + (["--home-repo", str(parent["home_repo"])] if parent.get("home_repo") else [])
        _replace_text(lead_dir / "lead_mcp.json", json.dumps({"mcpServers": {"agents_inc": {
            "type": "stdio", "command": sys.executable, "args": args,
            "env": {"AGENTS_INC_PARENT_RUN": run_dir, "AGENTS_INC_PARENT_TOKEN": token},
            "timeout": MCP_TOOL_TIMEOUT_SEC * 1000}}}, indent=1) + "\n", 0o600)
    _write_json(lead_dir / "run.json", data)
    return lead_dir, token


class ParentRefused(Exception):
    """D60: the broker of a Claude Lead cannot prove its parent run. str(exc) is `<code>: <message>`."""

    @property
    def code(self) -> str:
        return str(self).split(":", 1)[0]


def check_parent(spec: dict, env, lead_dir) -> str | None:
    """D60: check a Claude Lead's parent run from the broker side. spec: the Lead run.json; env: the broker's environment;
    lead_dir: the broker run directory. Return `<code>: <message>` for the first failure, else None."""
    run, token = env.get("AGENTS_INC_PARENT_RUN") or "", env.get("AGENTS_INC_PARENT_TOKEN") or ""
    if not run or not token:
        return "parent-env-missing: AGENTS_INC_PARENT_RUN and AGENTS_INC_PARENT_TOKEN must both be set for a Claude Lead broker"
    missing = f"parent-run-missing: {run} is not a run directory with a regular run.json"
    path = Path(run)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir() or (path / "run.json").is_symlink() or not (path / "run.json").is_file():
        return missing
    try:
        parent = json.loads((path / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return missing
    if not isinstance(parent, dict):
        return missing
    for field, left, right in (("parent_run_dir", os.path.realpath(run), spec.get("parent_run_dir")),
                               ("run_id", parent.get("run_id"), spec.get("parent_run_id")),
                               ("cwd", parent.get("cwd"), spec.get("cwd")),
                               ("lead_dir", parent.get("lead_dir"), os.path.realpath(lead_dir))):
        if not isinstance(left, str) or left != right:
            return f"parent-run-mismatch: {field} differs between the Lead run.json and the parent run"
    digest = _sha256(token)
    for want in (spec.get("parent_token_sha256"), parent.get("lead_token_sha256")):
        if not isinstance(want, str) or not hmac.compare_digest(digest.encode(), want.encode("utf-8", "replace")):
            return "parent-token-mismatch: the parent token does not match this run"
    return None


def launch(kind: str, model: str, effort: str | None, cwd: Path, prompt: str, run_dir: Path,
           permission_mode: str = DEFAULT_PERMISSION_MODE, resume: str | None = None,
           codex_write: bool = False, codex_network: bool = False, lead_dir: Path | None = None,
           allowed_tools: list | None = None, disallowed_tools: list | None = None) -> dict:
    """Run the delegate. Return {"rc", "stdout", "stderr", "argv", "session_id"}. resume: the Claude session id
    or the Codex thread id to continue. Under the broker, every Worker also gets the ask_lead server (D54).
    lead_dir (#68, D60): run a Codex or Claude delegate as a Lead with the broker MCP tools over that run directory."""
    if not _BROKER_SAFE_WRITES:
        where = caller_sandbox()
        _SANDBOX_NOTE.clear()
        if where:
            if not where.startswith("SANDBOX_RUNTIME") or not api_reachable():
                raise CallerSandboxed(where)
            if kind != "claude":
                raise CallerSandboxed(where, CODEX_NESTED_FIX, "caller-sandboxed-codex")
            _SANDBOX_NOTE.update({"caller_sandbox": "claude-code", "api": "reachable"})
    channel = _ask_channel(run_dir, _WORKER_ASK) if (_BROKER_SAFE_WRITES and _WORKER_ASK) else None
    if kind == "claude":
        if lead_dir is not None and channel is not None:
            raise RuntimeError("a Worker with an ask channel never leads")
        # allowed_tools None is a legacy run.json: keep the old argv. Else one --allowedTools flag carries ASK_TOOL too.
        granted = None if allowed_tools is None else list(allowed_tools) + ([ASK_TOOL] if channel is not None else [])
        argv = claude_argv(model, permission_mode, resume, effort, granted, disallowed_tools)
        extra = {}
        if channel is not None:
            argv += ["--mcp-config", str(channel["config"]), "--strict-mcp-config"]
            if allowed_tools is None:
                argv += ["--allowedTools", ASK_TOOL]
        if lead_dir is not None:  # D60: the Lead's broker; a long Worker run needs a long MCP tool timeout
            from .runtime import MCP_TOOL_TIMEOUT_SEC
            argv += ["--mcp-config", str(Path(lead_dir) / "lead_mcp.json"), "--strict-mcp-config"]
            extra["env"] = dict(os.environ, MCP_TOOL_TIMEOUT=str(MCP_TOOL_TIMEOUT_SEC * 1000))
        if _BROKER_SAFE_WRITES:
            if not sandbox_available():
                raise RuntimeError("no-sandbox-backend")  # never run a broker Claude Worker unconfined
            env = worker_env(argv[0])
            env["TMPDIR"] = str(_child_tmp(run_dir, resume_turn=bool(resume)))
            extra["env"] = env
            profile = Path(run_dir) / ("sandbox.sb" if not resume else f"sandbox.{secrets.token_hex(3)}.sb")
            _wtext(profile, claude_sandbox_profile(
                Path(cwd), Path(env.get("HOME") or Path.home()), env["TMPDIR"], _BROKER_DENY,
                (channel["ask"],) if channel else (),
                (Path(run_dir) / "pre_dispatch_snapshot.py", Path(run_dir) / "snapshot.json")  # FR-011
                + ((channel["script"], channel["config"]) if channel else ())))
            argv += ["--settings", WORKER_SETTINGS]
            argv = [SANDBOX_EXEC, "-f", str(profile)] + argv
        elif _SANDBOX_NOTE:
            argv += ["--settings", WORKER_SETTINGS]
        limit = _turn_timeout()
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=str(cwd), text=True, start_new_session=True, **extra)
        sink = _LIVE_SINK  # spec 027: the run path installs it; None outside a dispatch run
        # kills the group at the deadline (rc 124, TIMEOUT_MARK) and on cancellation (KeyboardInterrupt included)
        rc, stdout, stderr = _stream_run(proc, prompt, limit, (lambda ln: sink.line("claude", ln)) if sink else None,
                                         mark=TIMEOUT_MARK)
        text, session, is_error, usage = parse_claude_output(stdout)
        return {"rc": rc, "stdout": text, "stderr": stderr, "argv": argv, "session_id": session,
                "is_error": is_error, "usage": usage}
    from .cli import _efforts, _paths
    from .receipt import InstallReceipt
    from .runtime import run_codex
    paths = _paths()
    receipt = InstallReceipt.load(paths.receipt)
    env = None
    if _BROKER_SAFE_WRITES:
        env = worker_env(str(receipt.codex_path or "/usr/bin/false"))
        env["TMPDIR"] = str(_child_tmp(run_dir, resume_turn=bool(resume)))
    out, err = io.StringIO(), io.StringIO()
    thread: dict = {}
    worker = (channel["ask"], channel["rid"], channel["script"]) if channel else None
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = run_codex(model, effort, cwd, io.StringIO(prompt), receipt, _efforts(paths.current.resolve()), env=env,
                       extra_deny=_BROKER_DENY if _BROKER_SAFE_WRITES else (), isolate_home=_BROKER_SAFE_WRITES,
                       thread_out=None if lead_dir else thread, resume_thread=resume, worker=worker,
                       tools=codex_write or lead_dir is not None, write=codex_write, lead_dir=lead_dir,
                       network=codex_write and codex_network and lead_dir is None, timeout_s=_turn_timeout(),
                       # json mode only (run_codex ignores it for Lead runs, which get lifecycle events only)
                       on_line=(lambda ln: _LIVE_SINK.line("codex", ln)) if _LIVE_SINK is not None else None,
                       # the prompt names snapshot.json; a run dir outside cwd (TMPDIR) is otherwise unreadable
                       # the verifier copy too, so the delegate can run its own FAILURE GATE check (#66)
                       extra_read=(Path(run_dir) / "pre_dispatch_snapshot.py",) + (
                           () if _BROKER_SAFE_WRITES else (Path(run_dir) / "snapshot.json",)))
    return {"rc": rc, "stdout": out.getvalue(), "stderr": err.getvalue(),
            "argv": ["run_codex", model, effort, str(cwd)] + (["resume", resume] if resume else []),
            "session_id": thread.get("thread_id") or resume, "is_error": False}


def parse_claude_output(stdout: str) -> tuple:
    """(text, session_id, is_error, usage) from Claude stdout (spec 027 R1).

    The last `type: "result"` line of a stream-json run wins; else the whole stdout as one legacy json payload
    (it must carry `result`); else the raw stdout. Never raises."""
    payload = None
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("type") == "result":
            payload = data
            break
    if payload is None:
        try:
            data = json.loads(stdout)
        except (ValueError, TypeError):
            data = None
        if isinstance(data, dict) and "result" in data:
            payload = data
    if payload is None:
        return stdout, None, False, None
    return (str(payload.get("result", "")), payload.get("session_id"), bool(payload.get("is_error")),
            claude_usage(payload))


def claude_usage(data) -> dict | None:
    """Token usage from a `claude -p --output-format json` payload, else None. Never raises.

    Totals sum modelUsage across models (the session plus any subagents it ran); `models` keeps the
    per-model split. Unknown fields stay None, never zero."""
    try:
        per = data.get("modelUsage") if isinstance(data, dict) else None
        if not isinstance(per, dict) or not per:
            return None
        models = {}
        for name, u in per.items():
            if not isinstance(u, dict):
                continue
            models[name] = {"input_tokens": u.get("inputTokens"), "output_tokens": u.get("outputTokens"),
                            "cache_read": u.get("cacheReadInputTokens"),
                            "cache_write": u.get("cacheCreationInputTokens"), "cost_usd": u.get("costUSD")}
        def total(key):
            vals = [m[key] for m in models.values()]
            return sum(vals) if vals and all(isinstance(v, (int, float)) for v in vals) else None
        return {"input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
                "cache_read": total("cache_read"), "cache_write": total("cache_write"),
                "cost_usd_list": data.get("total_cost_usd"), "num_turns": data.get("num_turns"),
                "duration_ms": data.get("duration_ms"), "models": models}
    except Exception:
        return None


def _kind(model: str) -> str | None:
    if model in CODEX_SLUGS:
        return "codex"
    if model in CLAUDE_MODELS:
        return "claude"
    if free_launch.is_free(model):
        return "free"
    return None


# D51: True while the broker runs a Worker. Artifact writes then never follow a
# planted link and never overwrite (run.json is replaced atomically instead).
_BROKER_SAFE_WRITES = False
_BROKER_DENY: tuple = ()  # D51: broker run directory (+ isolated CODEX_HOME) denied to Claude Workers
_LAUNCHES = 0  # Worker launches started by run(); the broker charges fan-out from this, not from disk
_WORKER_ASK: str | None = None  # D54: request id of the broker turn being launched; the Worker's ask_lead files use it


def _wtext(path: Path, text: str) -> None:
    if _BROKER_SAFE_WRITES:
        _write_new(path, text)
    else:
        path.write_text(text, encoding="utf-8")


def _replace_text(path: Path, text: str, mode: int = 0o644) -> None:
    """Atomic overwrite that never writes through a planted link (the link itself is replaced)."""
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.broker-tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(str(tmp), str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(str(tmp))
        raise


def _write_json(path: Path, data: dict) -> None:
    if _BROKER_SAFE_WRITES:
        _atomic_write_json(path, data, overwrite=True)
    else:
        path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def _trust_path(run_id: str) -> Path:
    """Trusted snapshot directory of one top-level run: derived from the run id only, outside cwd (022 FR-001)."""
    from .cli import _paths
    return _paths().state / "dispatch-runs" / Path(run_id).name


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_trust(spec: dict, run_dir: Path, prompt: str) -> bool:
    """Once, just before launch: keep the captured snapshot bytes and the launched prompt's hash where the delegate
    cannot write. A broker child already runs in a broker-owned run directory outside cwd, so it keeps trust.json there.
    Fails closed: on an OSError spec["trust_error"] says why and False is returned; the caller must not launch."""
    try:
        data = (run_dir / "snapshot.json").read_bytes()
        record = json.dumps({"schema_version": 1, "snapshot_sha256": _sha256_bytes(data),
                             "prompt_sha256": _sha256_bytes(prompt.encode("utf-8"))}, indent=1) + "\n"
        if _BROKER_SAFE_WRITES:
            spec["snapshot_trust"] = "broker"
            _wtext(run_dir / "trust.json", record)
            return True
        spec["snapshot_trust"] = "private"
        trust = _trust_path(run_dir.name)
        trust.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(trust, 0o700)
        (trust / "snapshot.json").write_bytes(data)
        with contextlib.suppress(OSError, ValueError, AttributeError):  # keep the 025 scripts_sha256 written at pin time
            pinned = json.loads((trust / "trust.json").read_text(encoding="utf-8")).get("scripts_sha256")
            if pinned:
                record = json.dumps({**json.loads(record), "scripts_sha256": pinned}, indent=1) + "\n"
        (trust / "trust.json").write_text(record, encoding="utf-8")
        return True
    except OSError as exc:
        spec["trust_error"] = f"{type(exc).__name__}: {exc}"
        return False


def _trust_record(spec: dict, run_dir: Path) -> tuple[dict | None, Path | None]:
    """(trust.json content, directory holding it) for a run, located by the run directory's name (never by run.json's
    own run_id) and the run's trust mode."""
    mode = spec.get("snapshot_trust")
    if mode == "broker":
        folder = run_dir
    elif mode == "private":
        folder = _trust_path(run_dir.name)
    else:
        return None, None
    try:
        record = json.loads((folder / "trust.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, folder
    return (record if isinstance(record, dict) else None), folder


def _verify(spec: dict, run_dir: Path, out_path: Path, name: str = "verify.txt") -> tuple[str, str, int]:
    scripts = _scripts(spec)
    bad = _scripts_tampered(scripts)
    if bad:  # 025 (#104): a changed trusted copy judges nothing; the run is red snapshot-tampered
        _wtext(run_dir / name, f"lint source: {scripts}\nreport: none\nscripts: {bad}\nsnapshot rc=1\n")
        return "none", "TAMPERED", 1
    missing, log = lint_report(out_path, scripts=scripts)
    report = "COMPLIANT" if not missing else f"NON-COMPLIANT:{missing}"
    src, slog, snap = _snapshot_verify(spec, run_dir)
    _wtext(run_dir / name, f"lint source: {scripts}\nreport: {report}\n{log}\nsnapshot rc={src}\n{slog}")
    return report, snap, src


def _snapshot_verify(spec: dict, run_dir: Path) -> tuple[int, str, str]:
    """(rc, log, snap) of one scope-gate verify against the trusted snapshot: snap is clean, CHANGED:<paths>,
    TAMPERED or ERROR:<why>. Shared by the verify after the turn and the one after the gates (025 #107)."""
    allow = list(spec["gates"]["allow"])
    cwd = Path(spec["cwd"])
    try:
        allow.append(str(run_dir.resolve().relative_to(cwd.resolve())))
    except ValueError:
        pass
    snap_file, verdict = spec["snapshot"], None
    if spec.get("snapshot_trust") in ("private", "broker"):
        record, folder = _trust_record(spec, run_dir)
        try:
            actual = _sha256_bytes(Path(spec["snapshot"]).read_bytes())
        except OSError:
            actual = None
        if record is None or not (folder / "snapshot.json").is_file() and spec["snapshot_trust"] == "private":
            verdict = (1, "trusted snapshot record missing\n", "ERROR:trust-missing")
        elif actual != record.get("snapshot_sha256"):
            verdict = (1, "run-dir snapshot.json differs from the trusted record\n", "TAMPERED")
        elif spec["snapshot_trust"] == "private":
            snap_file = str(folder / "snapshot.json")
    if verdict is not None:
        src, slog, snap = verdict
    else:
        args = ["verify", snap_file, "--repo", str(cwd)]  # #92: never depend on the subprocess cwd
        for a in allow:
            args += ["--allow", a]
        try:
            src, slog = snapshot(*args, cwd=cwd, scripts=_scripts(spec))
        except ScriptsTampered as exc:
            return 1, f"{exc}\n", "TAMPERED"
        changed =[ln[8:] for ln in slog.splitlines() if ln.startswith("CHANGED ")]
        snap = "clean" if src == 0 else ("CHANGED:" + ",".join(changed) if changed else f"ERROR:rc={src}")
    return src, slog, snap


WORKERS_SPAWNED_RE = re.compile(r"^\W*(?:\[(?:verified|inferred|assumed)\]\s*)?workers spawned:\s*(\d+)(?:\s+this turn\b.*)?\W*$", re.IGNORECASE | re.MULTILINE)


def parse_workers_spawned(text: str) -> int | None:
    """Return n from the last `WORKERS SPAWNED: <integer>` report line (D48), else None."""
    hits = WORKERS_SPAWNED_RE.findall(text or "")
    return int(hits[-1]) if hits else None


def parse_fan_out(prompt: str, scripts: Path = SCRIPTS) -> dict | None:
    """Return the D48 FAN_OUT budget from a rendered prompt as {width, total, depth}, else None."""
    found = _load("check_dispatch_prompt", scripts).parse_fan_out(prompt)
    return dict(zip(("width", "total", "depth"), found)) if found else None


def _fan_out_check(spec: dict, out_path: Path) -> str | None:
    """Record per-attempt `workers_spawned_attempts` and their sum in `workers_spawned`. Return a red reason
    (`workers-spawned-missing`, `fan-out-over-total`, `workers-spawned-underreported`: the broker's count (D60) is
    above the report's) or None."""
    n = parse_workers_spawned(out_path.read_text(encoding="utf-8"))
    attempts = spec.setdefault("workers_spawned_attempts", [])
    attempts.append(n)
    spec["workers_spawned"] = sum(a for a in attempts if a is not None)
    if n is None:
        return "workers-spawned-missing"
    budget = spec.get("fan_out")
    if budget and spec["workers_spawned"] > budget["total"]:
        return "fan-out-over-total"
    broker = spec.get("broker_workers_spawned")
    if type(broker) is int and broker > spec["workers_spawned"]:
        return "workers-spawned-underreported"
    return None


REPORT_TOKEN = "{report}"  # spec 037: in a free run's gate argv, the saved reply path


def _run_gates(spec: dict, report_path: Path | None = None) -> tuple[list, str | None]:
    """D58: run each structured gate with no shell after the delegate exits. Return (results, red reason):
    gate-missing when a gate could not run, else gate-failed when an exit code differs, else None.
    report_path (free runs only): `{report}` in a gate argv expands to it, after the screens in _grants_from_slots."""
    danger, results = _load("render_dispatch", _scripts(spec)).DANGER_RE, []
    for g in spec["gate_commands"]:
        row = {"argv": g["argv"], "cwd": g["cwd"], "expect_rc": g["expect_rc"], "rc": None, "excerpt": ""}
        argv = [a.replace(REPORT_TOKEN, str(report_path)) for a in g["argv"]] if report_path is not None else g["argv"]
        joined = " ".join(argv)
        wd = (Path(spec["cwd"]) / g["cwd"]).resolve()  # re-checked here: the delegate may have planted a link
        if (danger.search(joined) or GATE_CREDENTIAL_RE.search(joined) or GATE_CREDENTIAL_RE.search(g["cwd"])
                or names_credential(argv)):
            row["error"] = "refused"
        elif not wd.is_relative_to(Path(spec["cwd"]).resolve()):
            row["error"] = "cwd-outside"
        else:
            try:
                res = subprocess.run(argv, cwd=str(wd), shell=False,
                                     stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace",
                                     timeout=g["timeout_s"])
                tail = ((res.stdout or "") + (res.stderr or "")).encode()[-2048:].decode("utf-8", "ignore")
                row.update(rc=res.returncode, excerpt=screen_text(tail, 2048))
            except subprocess.TimeoutExpired:
                row["error"] = "timeout"
            except OSError as exc:
                row["error"] = type(exc).__name__
        results.append(row)
    if any(r["rc"] is None for r in results):
        return results, "gate-missing"
    if any(r["rc"] != r["expect_rc"] for r in results):
        return results, "gate-failed"
    return results, None


# The Claude phrases plus run_codex's own pattern (429, too many requests, usage/rate limit), shared from runtime.py.
_CLAUDE_QUOTA = r"hit your (?:session |usage )?limit|usage limit reached|rate limit exceeded|quota exceeded"
CLAUDE_QUOTA_RE = re.compile(_CLAUDE_QUOTA, re.I)
QUOTA_RE = re.compile(_CLAUDE_QUOTA + "|" + QUOTA_PATTERN, re.I)


BLOCKED_RE = re.compile(r"Couldn't connect|ERR_PROXY_TUNNEL|API Error: Connection|ECONNREFUSED|ENOTFOUND", re.I)
TIMEOUT_MARK = "turn timeout after"  # launch() puts this in stderr with rc 124 when the turn deadline kills the child
# Reasons whose status line carries the first stderr line (022 FR-008).
FREE_WRAPPER_REASONS = frozenset({"redacted-reply", "provider-key-missing", "wrapper-refused"})  # spec 037 R6, free runs only
DETAIL_REASONS = frozenset({"rc-nonzero", "quota-paused", "blocked", "timeout", "launch-failed"}) | FREE_WRAPPER_REASONS


def _outcome(spec: dict, report: str, vrc: int, rc: int, fan_reason: str | None, gate_reason: str | None = None,
             gated: bool = False, quota: bool = False, snap: str = "", blocked: bool = False, is_error: bool = False,
             timed_out: bool = False) -> tuple[str, str | None]:
    """Return (outcome, reason). Order: quota pause, blocked, timeout, rc-nonzero, fan-out, report, snapshot (tampered,
    error, not clean), gate; green only when gates ran and passed. The caller scopes quota and blocked to the text
    it may trust (see _finish)."""
    if quota:
        return "red", "quota-paused"
    if blocked:
        return "red", "blocked"
    if timed_out:
        return "red", "timeout"
    if rc != 0 or is_error:
        return "red", "rc-nonzero"
    if fan_reason:
        return "red", fan_reason
    if report == "none" and snap == "TAMPERED":  # 025 (#104): the trusted script copy changed, nothing was judged
        return "red", "snapshot-tampered"
    advisory = report != "COMPLIANT"  # report wording alone never turns verified work red (see end of function)
    if advisory and not (gated and not gate_reason and vrc == 0 and snap not in ("TAMPERED",) and not snap.startswith("ERROR:")
                         and not snap.startswith("CHANGED")):
        return "red", "report-noncompliant"  # nothing deterministic vouches for the work, so the format failure stands
    if snap == "TAMPERED":
        return "red", "snapshot-tampered"
    if snap.startswith("ERROR:"):
        return "red", "snapshot-error"
    if vrc != 0:
        return "red", "snapshot-not-clean"
    if gate_reason:
        return "red", gate_reason
    if gated:
        return "green", "report-format-advisory" if advisory else None
    return "unverified", "no-gates"


def _stderr_detail(stderr: str | None) -> str:
    """First non-empty stderr line, screened, at most 200 bytes, whitespace replaced by `_` (one status-line token)."""
    for line in (stderr or "").splitlines():
        if line.strip():
            return re.sub(r"\s+", "_", screen_text(line.strip(), 200).strip())
    return ""


def _status(spec: dict, report: str, snap: str, out_path: Path) -> str:
    reason = f" reason={spec['reason']}" if spec.get("reason") else ""
    detail = f" detail={spec['reason_detail']}" if spec.get("reason_detail") else ""
    return (f"dispatch {spec['run_id']} {spec['model']} rc={spec['rc']} report={report} "
            f"lint={spec.get('scripts_source') or 'installed'} snapshot={snap} "
            f"outcome={spec['outcome']}{reason}{detail} out={out_path} "
            f"(resume with --resume {out_path.parent.resolve()})")


def _mirror(spec: dict, run_dir: Path, home_repo: str | None, prompt: str | None = None) -> str | None:
    """D46: write run.json (from the in-memory spec) and prompt.md to <home>/specs/consumers/<repo>/runs/<run-id>/.
    prompt.md is the launched prompt on the first turn; on resume it is the run-dir copy only when its sha256 matches
    the trusted record (022 FR-003), else it is skipped and spec["mirror_error"] says so. Never creates a missing home
    repo. Return an error string (also for an OSError), else None."""
    home = resolve_home_repo(home_repo, Path(spec["cwd"]) if spec.get("cwd") else None)
    if not home:
        print("run spec not mirrored: no home repo", file=sys.stderr)
        return None
    if not Path(home).is_dir():
        return "home-repo-missing"
    try:
        if prompt is None and (run_dir / "prompt.md").is_file():
            record, _ = _trust_record(spec, run_dir)
            text = (run_dir / "prompt.md").read_bytes()
            protected = spec.get("snapshot_trust") in ("private", "broker")
            if record is None and protected:  # a protected run with no readable record has nothing to check the prompt against
                spec["mirror_error"] = "trust-record-missing"
            elif record is None or _sha256_bytes(text) == record.get("prompt_sha256"):
                prompt = text.decode("utf-8", "replace")
            else:
                spec["mirror_error"] = "prompt-tampered"
        dest = Path(home) / "specs" / "consumers" / Path(spec["cwd"]).name / "runs" / run_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "run.json").write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
        if prompt is not None:
            (dest / "prompt.md").write_text(prompt, encoding="utf-8")
    except OSError as exc:
        return f"OSError: {exc}"
    return None


def _mirror_and_note(spec: dict, run_dir: Path, home_repo: str | None, prompt: str | None) -> None:
    """Mirror; a mirror error is recorded in run.json and stderr and never changes the exit code (022 FR-010)."""
    spec.pop("mirror_error", None)
    err = _mirror(spec, run_dir, home_repo, prompt) or spec.get("mirror_error")
    if err:
        spec["mirror_error"] = err
        _write_json(run_dir / "run.json", spec)
        print(f"run spec not mirrored: {err}", file=sys.stderr)


def _exit_code(outcome: str | None, reason: str | None, rc) -> int:
    """022 exit map: 0 green or unverified; 75 quota-paused; 69 blocked; 2 child usage error; 1 any other red."""
    if outcome != "red":
        return EXIT_OK
    if reason == "quota-paused":
        return EXIT_QUOTA
    if reason == "blocked":
        return EXIT_BLOCKED
    return EXIT_USAGE if rc == EXIT_USAGE else EXIT_RED  # keep a child usage error distinct from red


def _finish(spec: dict, run_dir: Path, out_path: Path, result: dict, home_repo: str | None,
            verify_name: str = "verify.txt", prompt: str | None = None) -> int:
    report, snap, vrc = _verify(spec, run_dir, out_path, verify_name)
    free = spec.get("kind") == "free"
    if free:  # spec 037: a free run spawns no Worker and its reply carries no WORKERS SPAWNED line
        fan_reason, spec["workers_spawned"] = None, 0
    else:
        fan_reason = _fan_out_check(spec, out_path)
    gated, skipped, gate_reason = bool(spec.get("gate_commands")), False, None
    if gated and _BROKER_SAFE_WRITES:
        gated, skipped, spec["gate_results"] = False, True, None  # a broker child never runs commands for its Lead
    elif gated and report == "none":  # tampered scripts: run no gate with them
        spec["gate_results"], gate_reason = None, "gate-missing"
    elif gated:  # after _verify; a second verify then catches a gate that writes into the repo (025 #107)
        spec["gate_results"], gate_reason = _run_gates(spec, out_path.resolve() if free else None)
        if spec.get("resumes"):
            spec["resumes"][-1]["gate_results"] = spec["gate_results"]
        src2, slog2, snap2 = _snapshot_verify(spec, run_dir)
        with open(run_dir / verify_name, "a", encoding="utf-8") as fh:
            fh.write("after gates: clean\n" if src2 == 0 else f"after gates:\nsnapshot rc={src2}\n{slog2}")
        if snap == "clean" and snap2 != "clean":
            snap = snap2  # TAMPERED and ERROR: keep their own reasons through _outcome
            if snap2.startswith("CHANGED:"):
                gate_reason = "gate-wrote"  # outranks gate-failed and gate-missing
    stdout, stderr = result.get("stdout") or "", result.get("stderr") or ""
    is_error = bool(result.get("is_error"))
    spec["is_error"] = is_error
    failed = result["rc"] != 0 or is_error
    # stderr always; stdout only when the child failed or sent no WORKERS SPAWNED line (a compliant report may quote the text)
    text = stderr[-4000:] + ("\n" + stdout[-4000:] if failed or parse_workers_spawned(stdout) is None else "")
    cls = free_launch.Classification(None)
    if free:  # a free reply is data: only the wrapper's stderr of a failed call can mean quota or blocked
        text = stderr[-4000:] if failed else ""
        cls = free_launch.classify_rc(result["rc"], stdout, stderr, spec.get("model")) if failed else cls
        quota = cls.reason == "quota-paused" or bool(QUOTA_RE.search(text))
    elif failed or parse_workers_spawned(stdout) is None:
        quota = bool(QUOTA_RE.search(text))
    else:  # clean turn with a report: only an anchored stderr line counts, not an incidental 429 or "rate limit"
        quota = any(("hit a usage or rate limit" in ln or CLAUDE_QUOTA_RE.search(ln)
                     or (ln.startswith("ERROR:") and QUOTA_RE.search(ln))) for ln in stderr[-4000:].splitlines())
    blocked = bool(BLOCKED_RE.search(text)) or cls.reason == "blocked"
    timed_out = result["rc"] == 124 and TIMEOUT_MARK in stderr
    # A free reply is not a delegate report: the format check never decides it. Gates green, no gates unverified (FR-008).
    outcome, reason = _outcome(spec, "COMPLIANT" if free and report != "none" else report, vrc, result["rc"], fan_reason,
                               gate_reason, gated, quota, snap, blocked, is_error, timed_out)
    if free and cls.reason in FREE_WRAPPER_REASONS:  # spec 037 R6: the wrapper's own refusal names the reason
        outcome, reason = "red", cls.reason
    if skipped and outcome == "unverified":
        reason = "gates-skipped-broker"
    spec["outcome"] = outcome
    spec["reason"] = reason
    detail = _stderr_detail(stderr) if outcome == "red" and (reason in DETAIL_REASONS or not stdout.strip()) else ""
    if free and outcome == "red" and reason == "blocked" and cls.reason == "blocked":  # the host is named (R6)
        detail = re.sub(r"\s+", "_", screen_text(cls.detail, 200).strip())
    if detail:
        spec["reason_detail"] = detail
    else:
        spec.pop("reason_detail", None)
    _record_ledger_return(spec)
    _write_json(run_dir / "run.json", spec)
    print(_status(spec, report, snap, out_path))
    _mirror_and_note(spec, run_dir, home_repo, prompt)
    return _exit_code(outcome, reason, result["rc"])


def _red_before_run(spec: dict, run_dir: Path, reason: str, detail: str, home_repo: str | None,
                    out_name: str = "stdout.md", snap: str = "none", code: int = EXIT_RED) -> int:
    """No child ran. Record red/<reason>, print one status line, return code (default 1)."""
    out_path = run_dir / out_name
    _wtext(out_path, "")
    spec.update(rc=-1, outcome="red", reason=reason,
                reason_detail=re.sub(r"\s+", "_", screen_text(detail, 200).strip()))
    _record_ledger_return(spec)
    _write_json(run_dir / "run.json", spec)
    print(_status(spec, "none", snap, out_path))
    _mirror_and_note(spec, run_dir, home_repo, None)
    return code


def _launch_failed(spec: dict, run_dir: Path, exc: Exception, home_repo: str | None, out_name: str = "stdout.md") -> int:
    """022 FR-009: launch() raised, so no child ran. Record red/launch-failed, print one status line, return 1."""
    if isinstance(exc, CallerSandboxed):  # #94: blocked, exit 69, the fix in the detail
        return _red_before_run(spec, run_dir, "blocked", f"{exc.code}: {exc}; {exc.fix or SANDBOX_FIX}", home_repo, out_name,
                               code=EXIT_BLOCKED)
    return _red_before_run(spec, run_dir, "launch-failed", f"{type(exc).__name__}: {exc}", home_repo, out_name)


def _record_ledger_node(spec: dict, slots: dict) -> None:
    """Add a `dispatched` ledger node for this run (id = run id). A failure goes to run.json, never the outcome."""
    try:
        from .. import host_ledger  # lazy, like cli.py
        from .cli import _paths
        task = slots.get("TASK") if isinstance(slots, dict) else None
        if not host_ledger.record_dispatch_run(_paths().state, spec, task if isinstance(task, str) else None):
            spec["ledger_error"] = "ledger write failed"
    except Exception as exc:
        spec["ledger_error"] = f"{type(exc).__name__}: {exc}"


def _record_ledger_return(spec: dict) -> None:
    """Add a `returned` ledger row for this run. A failure goes to run.json, never the outcome."""
    if not spec.get("run_id") or not spec.get("outcome"):
        return
    try:
        from .. import host_ledger  # lazy, like cli.py
        from .cli import _paths
        if not host_ledger.record_dispatch_return(_paths().state, spec):
            spec["ledger_return_error"] = "ledger write failed"
    except Exception as exc:
        spec["ledger_return_error"] = f"{type(exc).__name__}: {exc}"


def _grants_from_slots(slots: dict, cwd: Path, scripts: Path = SCRIPTS) -> tuple[list | None, list, tuple | None]:
    """Parse GATES and BASH_ALLOW. Return (gates, bash_allow, None) or (None, [], (refused outcome, why))."""
    rd = _load("render_dispatch", scripts)
    raw = slots.get("GATES")
    if isinstance(raw, str) and raw.strip():
        try:
            decoded = json.loads(raw)
        except ValueError:
            decoded = None
        if not isinstance(decoded, list):
            return None, [], ("refused-gates", "GATES must be a JSON list, got string")
    gates, why = rd.parse_gates(raw)
    if why:
        return None, [], ("refused-gates", why)
    for g in gates or []:
        joined = " ".join(g["argv"])
        if GATE_CREDENTIAL_RE.search(joined) or GATE_CREDENTIAL_RE.search(g["cwd"]) or names_credential(g["argv"]):
            return None, [], ("refused-gates", f"credential-seeking gate {joined!r}")
        if not (cwd / g["cwd"]).resolve().is_relative_to(cwd):
            return None, [], ("refused-gates", f"gate cwd {g['cwd']!r} resolves outside --cwd")
    bash_allow, why = rd.bash_allow_list(slots.get("BASH_ALLOW"))
    if why:
        return None, [], ("refused-bash-allow", why)
    for prefix in bash_allow:
        if GATE_CREDENTIAL_RE.search(prefix) or names_credential(prefix.split()):
            return None, [], ("refused-bash-allow", f"credential-seeking prefix {prefix!r}")
    return gates, bash_allow, None


def _resolves(name: str, base: Path, path: str | None) -> bool:
    if "/" in name:
        target = Path(name) if os.path.isabs(name) else base / name
        return target.is_file() and os.access(target, os.X_OK)
    return shutil.which(name, path=path) is not None


def capability_preflight(gates, bash_allow, cwd, path: str | None = None) -> list[str]:
    """Return one message per GATES executable or BASH_ALLOW first word that does not resolve (FR3.1).
    A path is checked against its gate cwd under `cwd`; a bare name uses `shutil.which` on `path` (default PATH)."""
    cwd = Path(cwd)
    misses = []
    for i, g in enumerate(gates or []):
        argv = g.get("argv") or []
        if argv and not _resolves(str(argv[0]), cwd / g.get("cwd", "."), path):
            misses.append(f"gate[{i}] executable not found: {argv[0]}")
    for i, prefix in enumerate(bash_allow or []):
        words = prefix.split()
        if words and not _resolves(words[0], cwd, path):
            misses.append(f"bash_allow[{i}] executable not found: {words[0]}")
    return misses


def _record_lead(spec: dict, lead_dir: Path) -> None:
    """After a Lead turn: `broker_workers_spawned` (None when unreadable) and `children` (D60), one entry per broker
    result file in lead_dir (regular files only, at most total + resumes), so the mirrored run.json links the Workers."""
    try:
        lead = json.loads((lead_dir / "run.json").read_text(encoding="utf-8"))
        spec["broker_workers_spawned"] = lead.get("workers_spawned")
    except (OSError, ValueError):
        lead = {}
        spec["broker_workers_spawned"] = None
    fan = spec.get("fan_out") or {}
    resumes = lead.get("resumes") if type(lead.get("resumes")) is int else 0
    children = []
    for path in sorted(lead_dir.glob("*.result.json")):
        if len(children) >= fan.get("total", 0) + resumes:
            break
        if path.is_symlink() or not path.is_file():
            continue
        res, cspec = {}, {}
        try:
            res = json.loads(path.read_text(encoding="utf-8"))
            cid, root = res.get("child_run_id"), res.get("resumed_from") or res.get("request_id")
            if cid and root:
                cspec = json.loads((lead_dir / "workers" / root / "runs" / cid / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        res, cspec = (res if isinstance(res, dict) else {}), (cspec if isinstance(cspec, dict) else {})
        children.append({"request_id": res.get("request_id"), "child_run_id": res.get("child_run_id"),
                         "model": cspec.get("model"), "status": res.get("status"), "outcome": res.get("outcome")})
    spec["children"] = children


def run(args) -> int:
    if getattr(args, "resume", None):
        return resume(args)
    if not args.slots or not args.model:
        print("dispatch: --slots and --model are required", file=sys.stderr)
        return EXIT_USAGE
    model = args.model
    kind = _kind(model)
    if kind is None:
        print(f"dispatch: {model} not supported, use agent.sh")
        return EXIT_USAGE
    # Claude without --effort keeps the claude CLI default (operator settings); record null, not a guess.
    effort = args.effort or (None if kind in ("claude", "free") else "medium")
    if kind == "claude" and effort is not None and effort not in _efforts_for(model):
        print(f"dispatch: effort {effort} not allowed for {model}, use one of: {' '.join(_efforts_for(model))}",
              file=sys.stderr)
        return EXIT_USAGE
    slots_path = Path(args.slots).resolve()
    try:
        slots = json.loads(slots_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"dispatch: cannot read slots: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if not isinstance(slots, dict):
        print(f"dispatch: slots must be a JSON object, got {type(slots).__name__}: {slots_path}", file=sys.stderr)
        return EXIT_USAGE
    hit = credential_hit(slots)  # 025 (#105): the broker's request text screen, before anything is written
    if hit:
        print(f"dispatch: refused credential-seeking ({hit})", file=sys.stderr)
        return EXIT_REFUSED
    control = control_char_hit(slots)  # 026 (#109): C0, DEL and bidi controls, before anything is written
    if control:
        print(f"dispatch: refused-control-char (slot {control[0]} {control[1]})", file=sys.stderr)
        return EXIT_REFUSED
    cwd = Path(args.cwd or os.getcwd()).resolve()
    if not cwd.is_dir():
        print(f"dispatch: cwd is not a directory: {cwd}", file=sys.stderr)
        return EXIT_USAGE
    if args.run_dir and not _run_dir_ignored(Path(args.run_dir).resolve(), cwd):
        print(f"dispatch: --run-dir {Path(args.run_dir).resolve()} is inside --cwd and not git-ignored; "
              "later snapshot verifies would see its files", file=sys.stderr)
        return EXIT_USAGE
    run_id = new_run_id(model)
    run_dir = Path(args.run_dir or default_parent(cwd)).resolve() / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f"dispatch: cannot create run directory {run_dir}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"agents-inc dispatch: run {run_id} dir {run_dir}", file=sys.stderr)  # 027 FR-007
    global _LIVE_SINK
    sink = _LIVE_SINK = EventSink(run_dir, safe_writes=_BROKER_SAFE_WRITES)
    sink.emit("agents-inc", {"type": "run.start", "run_id": run_id, "model": model, "kind": kind})
    code, outcome = EXIT_RED, "red"
    saved_handlers = _install_cancel_handlers()
    try:
        code = _run_dir_phase(args, model, kind, effort, slots, slots_path, cwd, run_id, run_dir)
        outcome = _run_end_outcome(run_dir, code)
        return code
    except Cancelled:  # launch() already killed and reaped the delegate's group
        outcome, code = "cancelled", EXIT_CANCELLED
        _mark_cancelled(run_dir, run_id, model)
        return code
    except BaseException:
        outcome = "cancelled"  # KeyboardInterrupt and anything else that escapes: launch() reaped the child
        raise
    finally:
        _restore_handlers(saved_handlers)
        live_events.CHILD_START = None
        _LIVE_SINK = None
        spec_rc = _read_run_json(run_dir).get("rc")
        sink.emit("agents-inc", {"type": "run.end", "outcome": outcome, "rc": spec_rc if isinstance(spec_rc, int) else code})
        sink.close()
        if sink.error:  # 027 FR-009: a viewer problem never changes the verdict; run.json records it
            spec = _read_run_json(run_dir)
            if spec:
                spec["events_error"] = sink.error
                with contextlib.suppress(OSError):
                    _write_json(run_dir / "run.json", spec)


def _on_cancel_signal(signum, frame) -> None:
    for s in CANCEL_SIGNALS:  # one cancellation: a second signal during cleanup changes nothing
        signal.signal(s, signal.SIG_IGN)
    raise Cancelled(signal.Signals(signum).name)


def _install_cancel_handlers() -> dict:
    """Make SIGTERM, SIGHUP and SIGINT raise Cancelled (FR-011). Only the main thread may install handlers."""
    if threading.current_thread() is not threading.main_thread():
        return {}
    return {s: signal.signal(s, _on_cancel_signal) for s in CANCEL_SIGNALS}


def _restore_handlers(saved: dict) -> None:
    for s, handler in saved.items():
        signal.signal(s, handler if handler is not None else signal.SIG_DFL)


def _process_start(pid: int) -> str | None:
    """`ps` start time of a process: tells a recorded group leader from an unrelated process that took its pid."""
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(int(pid))], capture_output=True, text=True,
                             timeout=5).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return out or None


def _record_child(spec: dict, run_dir: Path, pid: int) -> None:
    """FR-012: the delegate leads its own process group (start_new_session): note the group and the leader's start
    time in run.json while the run is live, so `dispatch --cancel` can find it."""
    spec["delegate_pgid"], spec["delegate_start"] = pid, _process_start(pid)
    with contextlib.suppress(OSError):
        _write_json(run_dir / "run.json", spec)


def _mark_cancelled(run_dir: Path, run_id: str, model: str) -> None:
    spec = _read_run_json(run_dir) or {"run_id": run_id, "model": model}
    spec.update(outcome="cancelled", reason="cancelled", rc=EXIT_CANCELLED)
    with contextlib.suppress(OSError):
        _write_json(run_dir / "run.json", spec)
    print(f"dispatch {run_id} {model} cancelled")


def cancel_run(run_dir) -> int:
    """`dispatch --cancel RUN_DIR` (FR-012): stop the recorded delegate group of a run that has no final outcome and
    whose group leader still has the recorded start time. SIGTERM, then SIGKILL after CANCEL_GRACE_S. Else do nothing."""
    spec = _read_run_json(Path(run_dir))
    pgid, started = spec.get("delegate_pgid"), spec.get("delegate_start")
    if spec.get("outcome") or not isinstance(pgid, int) or pgid <= 1 or not started \
            or _process_start(pgid) != started:
        print("nothing to cancel")
        return EXIT_OK
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signal.SIGTERM)
    deadline = time.monotonic() + CANCEL_GRACE_S
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except (ProcessLookupError, PermissionError):
            print(f"cancelled group {pgid}")
            return EXIT_OK
        time.sleep(0.05)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signal.SIGKILL)
    print(f"cancelled group {pgid} (killed)")
    return EXIT_OK


def _read_run_json(run_dir: Path) -> dict:
    try:
        data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_end_outcome(run_dir: Path, code: int) -> str:
    """The FR-002 `run.end` outcome for a finished run, read back from the run.json the run path wrote."""
    spec = _read_run_json(run_dir)
    outcome, reason = spec.get("outcome"), spec.get("reason")
    if outcome == "dry-run":
        return "dry-run"
    if isinstance(outcome, str) and outcome.startswith("refused"):
        return "refused"
    if outcome == "red" and reason == "launch-failed":
        return "launch-failed"
    if outcome == "red" and reason == "timeout":
        return "timeout"
    if outcome in ("green", "unverified"):
        return "done"
    return "red"


def _run_dir_phase(args, model, kind, effort, slots, slots_path, cwd, run_id, run_dir) -> int:
    """Everything after the run directory exists (split from run() for the spec 027 event bracket)."""
    if _BROKER_SAFE_WRITES:  # 025 (#104): a broker Worker loads its Lead's scripts and never probes its own cwd
        sdir, ssrc = _INHERITED_SCRIPTS or (SCRIPTS, "installed")
    else:
        sdir, ssrc = scripts_dir(cwd)
        if ssrc == "checkout":
            try:
                sdir = _pin_scripts(sdir, run_id)
            except OSError as exc:
                print(f"dispatch: cannot pin checkout scripts: {exc}", file=sys.stderr)
                return EXIT_RED
    if _BROKER_SAFE_WRITES:
        _wtext(run_dir / "slots.json", slots_path.read_text(encoding="utf-8"))
    else:
        shutil.copyfile(slots_path, run_dir / "slots.json")
    spec = {"run_id": run_id, "kind": kind, "slots": str(slots_path), "model": model, "effort": effort,
            "schema_version": 1, "slots_sha256": _sha256_bytes((run_dir / "slots.json").read_bytes()),
            "slots_path": str(run_dir / "slots.json"),
            "cwd": str(cwd), "chain": ["CoS", model], "snapshot": str(run_dir / "snapshot.json"),
            "gates": {"tier": args.tier, "allow": allow_paths(_slot_str("FILES_IN_SCOPE", slots.get("FILES_IN_SCOPE", "")))},
            "permission_mode": slots.get("PERMISSION_MODE") or DEFAULT_PERMISSION_MODE,
            "codex_write": codex_write(slots),
            "codex_network": codex_network(slots),
            "scripts_dir": str(sdir), "scripts_source": ssrc,
            "rc": None, "outcome": None, "session_id": None}
    lint = run_dir / "lint.txt"
    input_section = ""
    if kind == "free":  # spec 037 FR-003..FR-006: refuse before render and before any provider call; exit 2
        refusal = free_launch.pre_checks(slots, args, free_launch.load_routing(), cwd, model=model)
        if not refusal:
            try:
                input_section, spec["input_files"] = free_launch.build_input_section(
                    slots, cwd, free_launch.FREE_MODELS[model].max_input_chars)
            except free_launch.InputsRefused as exc:
                refusal = free_launch.Refusal(exc.name, str(exc))
        if refusal:
            _wtext(lint, f"{refusal}: {refusal.detail}\n")
            spec["outcome"] = str(refusal); spec["reason_detail"] = refusal.detail
            _write_json(run_dir / "run.json", spec)
            print(f"dispatch {run_id} {model} refused {refusal}: {refusal.detail} lint={lint}")
            return EXIT_USAGE
    globs = scope_globs(_slot_str("FILES_IN_SCOPE", slots.get("FILES_IN_SCOPE", "")))
    gates, bash_allow, why = _grants_from_slots(slots, cwd, sdir)
    if globs:
        why = ("refused-scope", f"FILES_IN_SCOPE has glob patterns the scope gate cannot match: {' '.join(globs)}; list exact paths")
    if why:
        _wtext(lint, why[1] + "\n")
        spec["outcome"] = why[0]; _write_json(run_dir / "run.json", spec)
        print(f"dispatch {run_id} {model} refused {why[0]}: {why[1]} lint={lint}")
        return EXIT_REFUSED
    misses = [] if kind == "free" else capability_preflight(
        None if _GRANT_CEILING is not None else gates, bash_allow, cwd,
        (WORKER_PATH + ":" + os.path.dirname(os.path.abspath(shutil.which("claude") or "claude")))
        if _BROKER_SAFE_WRITES else None)
    if misses:
        detail = "; ".join(misses)
        _wtext(lint, detail + "\n")
        spec["outcome"] = "refused-capability"; spec["reason_detail"] = detail; _write_json(run_dir / "run.json", spec)
        print(f"dispatch {run_id} {model} refused refused-capability: {detail} lint={lint}")
        return EXIT_REFUSED
    spec["gate_commands"] = gates or []
    spec["allowed_tools"], spec["disallowed_tools"] = tool_grants(spec, gates, bash_allow, run_dir) if kind == "claude" else (None, None)
    if kind == "claude" and _BROKER_SAFE_WRITES:
        if any(r in LEAD_TOOLS for r in spec["allowed_tools"]):
            raise RuntimeError("a broker Worker is never granted a dispatch tool")  # D60
        bad = ceiling_violation(spec["allowed_tools"], _verifier_rules(spec, run_dir))
        if bad:
            why = f"grant-exceeds-parent: {bad} is not granted to the parent run"
            _wtext(lint, why + "\n")
            spec["outcome"] = "refused-grants"; _write_json(run_dir / "run.json", spec)
            print(f"dispatch {run_id} {model} refused refused-grants: {why} lint={lint}")
            return EXIT_REFUSED
    rc, prompt, err = render(slots_path, model, sdir)
    if rc != 0:
        _wtext(lint, f"render rc={rc}\n{err}")
        spec["outcome"] = "refused-render"; _write_json(run_dir / "run.json", spec)
        print(f"dispatch {run_id} {model} refused render rc={rc} lint={lint}")
        return EXIT_REFUSED
    if _BROKER_SAFE_WRITES and SCOPE_LINE not in prompt:
        _wtext(lint, "rendered prompt lacks the SCOPE BOILERPLATE line\n")
        spec["outcome"] = "refused-scope"; _write_json(run_dir / "run.json", spec)
        print(f"dispatch {run_id} {model} refused scope-boilerplate-missing lint={lint}")
        return EXIT_REFUSED
    if kind == "free":  # spec 037: the snapshot is captured after the wrapper call (_run_free_phase); the provider never sees it
        prompt = free_launch.strip_snapshot(prompt)
        if input_section:
            prompt = prompt.rstrip("\n") + "\n\n" + input_section
    else:
        # Capture first so the real snapshot path reaches the prompt; lint after injection.
        src, slog = snapshot("capture", spec["snapshot"], cwd=cwd, scripts=sdir)
        if src != 0:
            spec["outcome"] = "snapshot-failed"; _write_json(run_dir / "run.json", spec)
            print(f"dispatch {run_id} {model} snapshot failed rc={src}: {slog.strip()}")
            return EXIT_RED
        prompt = inject_snapshot(prompt, spec["snapshot"])
        # #66: the installed scripts sit under ~/.local, which the Codex sandbox denies; ship a copy beside the snapshot
        verifier = run_dir / "pre_dispatch_snapshot.py"
        _wtext(verifier, (sdir / "pre_dispatch_snapshot.py").read_text(encoding="utf-8"))
        prompt = prompt.rstrip("\n") + f"\nSNAPSHOT VERIFIER: `python3 {verifier} verify {spec['snapshot']}` (use this copy)\n"
    if kind == "claude":
        prompt += grants_section(spec["allowed_tools"], spec["disallowed_tools"], bash_allow, spec["permission_mode"])
    if _BROKER_SAFE_WRITES and _WORKER_ASK:
        prompt += ASK_LEAD_NOTE
    spec["fan_out"] = parse_fan_out(prompt, sdir)
    prompt_path = run_dir / "prompt.md"
    _wtext(prompt_path, prompt)
    missing, log = lint_prompt(prompt_path, args.tier, model, scripts=sdir)
    named = _load("check_dispatch_prompt", sdir).label_missing(missing) if missing else missing
    named_text = "[" + ", ".join(str(m) for m in named) + "]"
    _wtext(lint, ("COMPLIANT\n" if not missing else f"NON-COMPLIANT missing: {named_text}\n") + log)
    if missing:
        spec["outcome"] = "refused-lint"; _write_json(run_dir / "run.json", spec)
        print(f"dispatch {run_id} {model} refused NON-COMPLIANT:{named_text} lint={lint}")
        return EXIT_REFUSED
    roster = [] if _BROKER_SAFE_WRITES or kind == "free" else lead_roster(model, slots, spec["fan_out"], sdir)
    if kind == "claude" and model in LEAD_RUNGS and not _BROKER_SAFE_WRITES:
        skipped = lead_skip_reason(spec, roster)
        if skipped:
            spec["lead_skipped"], roster = skipped, []
    if roster:
        spec["lead_workers"] = roster
        if spec["codex_network"]:
            spec["codex_network_ignored"] = "lead"  # D51: a Lead has no network; its Workers may
    if args.dry_run:
        spec["outcome"] = "dry-run"; _write_json(run_dir / "run.json", spec)
        print(f"dispatch {run_id} {model} dry-run prompt={prompt_path}")
        return EXIT_OK
    lead_dir, token = None, None
    if roster:
        parent = {"run_dir": run_dir, "allowed_tools": spec["allowed_tools"], "disallowed_tools": spec["disallowed_tools"],
                  "home_repo": getattr(args, "home_repo", None)} if kind == "claude" else None
        lead_dir, token = make_lead_dir(spec, roster, parent)
        spec["lead_dir"] = str(lead_dir)
        if kind == "claude":  # D60: the parent keeps the token's hash only; its grants gain the broker tools
            spec["lead_token_sha256"] = _sha256(token)
            allow, deny = lead_grants(lead_dir)
            spec["allowed_tools"] = list(dict.fromkeys(spec["allowed_tools"] + allow))
            spec["disallowed_tools"] = list(dict.fromkeys(spec["disallowed_tools"] + deny))
        prompt += (LEAD_NOTE_CLAUDE if kind == "claude" else LEAD_NOTE_CODEX).format(roster=", ".join(roster))
        _wtext(prompt_path, prompt)
    _record_ledger_node(spec, slots)
    if kind == "free":
        return _run_free_phase(args, spec, slots, cwd, run_dir, prompt, sdir)
    if not _record_trust(spec, run_dir, prompt):  # fail closed: no trusted copy, no delegate
        return _red_before_run(spec, run_dir, "snapshot-error", spec["trust_error"], getattr(args, "home_repo", None))
    if token is not None:
        _write_json(run_dir / "run.json", spec)  # before launch: the broker reads the parent run.json
    global _LAUNCHES
    _LAUNCHES += 1
    live_events.CHILD_START = lambda pid: _record_child(spec, run_dir, pid)
    try:
        result = launch(kind, model, effort, cwd, prompt, run_dir, spec["permission_mode"],
                        **({"codex_write": True} if spec["codex_write"] else {}),
                        **({"codex_network": True} if spec["codex_network"] else {}),
                        **({"lead_dir": lead_dir} if lead_dir is not None else {}),
                        **({"allowed_tools": spec["allowed_tools"], "disallowed_tools": spec["disallowed_tools"]}
                           if kind == "claude" else {}))
    except Exception as exc:
        return _launch_failed(spec, run_dir, exc, getattr(args, "home_repo", None))
    spec.update(_SANDBOX_NOTE)
    if lead_dir is not None:
        _record_lead(spec, lead_dir)
    out_path = run_dir / "stdout.md"
    _wtext(out_path, result["stdout"])
    _wtext(run_dir / "stderr.txt", result["stderr"])
    spec.update(rc=result["rc"], session_id=result.get("session_id"), argv=result.get("argv"))
    if result.get("usage") is not None:
        spec["usage"] = result["usage"]
        for where in (run_dir, _trust_path(spec["run_id"])):
            with contextlib.suppress(OSError):
                Path(where).mkdir(parents=True, exist_ok=True)
                _wtext(Path(where) / "usage.json", json.dumps(result["usage"], indent=1))
    return _finish(spec, run_dir, out_path, result, getattr(args, "home_repo", None), prompt=prompt)


def _run_free_phase(args, spec, slots, cwd, run_dir, prompt, sdir) -> int:
    """Spec 037: launch a free model through its wrapper, then snapshot, trust, gate and finish like any other run.
    The snapshot is captured after the wrapper call and before the gates, so a gate that writes into the repo is red
    `gate-wrote` (the verify after the gates sees the change). Cost and Workers spawned are 0."""
    home = getattr(args, "home_repo", None)
    entry = free_launch.FREE_MODELS[spec["model"]]
    task_kind = slots.get("TASK_KIND") if isinstance(slots.get("TASK_KIND"), str) else None
    classification = slots.get("CLASSIFICATION") if isinstance(slots.get("CLASSIFICATION"), str) else None
    spec.update(provider=entry.provider, task_kind=task_kind, classification=classification,
                input_files=spec.get("input_files", []), usage=None, cost_usd=0, workers_spawned=0)
    hold = free_launch.pre_launch_hold(spec["model"])  # FR-009: cap or cooldown ends quota-paused, no wrapper call
    if hold:
        return _red_before_run(spec, run_dir, "quota-paused", hold, home, code=EXIT_QUOTA)
    unreachable = free_launch.reachability_hold(spec["model"], caller_sandbox())  # FR-011: probe only when sandboxed
    if unreachable:
        return _red_before_run(spec, run_dir, "blocked", unreachable, home, code=EXIT_BLOCKED)
    try:
        result = free_launch.run_free(spec, prompt, run_dir, cwd, timeout=_turn_timeout())
    except Exception as exc:
        return _launch_failed(spec, run_dir, exc, home)
    out_path = run_dir / "stdout.md"
    spec.update(rc=result["rc"], session_id=None, argv=result["argv"], wrapper=result["wrapper"],
                wrapper_sha256=result["wrapper_sha256"],
                usage=free_launch.parse_usage(result["stdout"], result["stderr"]))
    src, slog = snapshot("capture", spec["snapshot"], cwd=cwd, scripts=sdir)
    if src != 0:
        spec["outcome"] = "snapshot-failed"; _write_json(run_dir / "run.json", spec)
        print(f"dispatch {spec['run_id']} {spec['model']} snapshot failed rc={src}: {slog.strip()}")
        return EXIT_RED
    if not _record_trust(spec, run_dir, prompt):
        return _red_before_run(spec, run_dir, "snapshot-error", spec["trust_error"], home, out_name="trust-error.txt")
    return _finish(spec, run_dir, out_path, result, home, prompt=prompt)


def _resume_candidates(cwd: Path, run_id: str, run_dir_arg) -> list[Path]:
    """Run directories where a bare run id may live. An explicit --run-dir is the only candidate; else every parent
    a dispatch could have used (default_parent, repo .scratch, session scratchpad, TMPDIR, /tmp), first form kept."""
    if run_dir_arg:
        return [Path(run_dir_arg).resolve() / run_id]
    parents = [default_parent(cwd), Path(cwd) / ".scratch" / "agents-inc-runs"]
    parents += [Path(base) / "agents-inc-runs" for base in (os.environ.get("CLAUDE_SCRATCHPAD"),
                                                            os.environ.get("TMPDIR"), "/tmp") if base]
    found, seen = [], set()
    for parent in parents:
        cand = parent / run_id
        key = cand.resolve()
        if key not in seen:
            seen.add(key)
            found.append(cand)
    return found


def resume(args) -> int:
    """Send one more turn to a finished delegate: Claude via its session id, Codex via its thread id (D54)."""
    cwd = Path(getattr(args, "cwd", None) or os.getcwd()).resolve()
    given = Path(args.resume)  # a run id under --run-dir, or a path to the run directory itself
    if (given.is_absolute() or len(given.parts) > 1) and (given / "run.json").is_file():
        run_dir = given.resolve()
    else:
        candidates = _resume_candidates(cwd, args.resume, args.run_dir)
        run_dir = next((c for c in candidates if (c / "run.json").is_file()), None)
        if run_dir is None:
            print(f"dispatch: no run.json for {args.resume} (searched: {', '.join(str(c) for c in candidates)})",
                  file=sys.stderr)
            return EXIT_USAGE
        run_dir = run_dir.resolve()
    try:
        spec = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"dispatch: no run.json for {args.resume}", file=sys.stderr)
        return EXIT_USAGE
    kind = spec.get("kind")
    if kind == "free":  # spec 037 FR-005: a free run has no session
        print(f"dispatch: refused-resume: a free run cannot be resumed ({args.resume})", file=sys.stderr)
        return EXIT_USAGE
    if kind not in ("claude", "codex") or not spec.get("session_id"):
        print(f"dispatch: no session id recorded for {args.resume}; cannot resume", file=sys.stderr)
        return EXIT_USAGE
    if not args.message:
        print("dispatch: --resume needs --message", file=sys.stderr)
        return EXIT_USAGE
    control = control_char_hit({"MESSAGE": args.message})
    if control:
        print(f"dispatch: refused-control-char (slot {control[0]} {control[1]})", file=sys.stderr)
        return EXIT_REFUSED
    hit = credential_hit({"MESSAGE": args.message})  # 025 (#105): same screen as the broker's resume message
    if hit:
        print(f"dispatch: refused credential-seeking ({hit})", file=sys.stderr)
        return EXIT_REFUSED
    home = getattr(args, "home_repo", None)
    n = len(spec.get("resumes", [])) + 1
    # 022: the trusted snapshot is found from the run directory the caller selected (its name is the run id); run.json
    # is delegate-writable, so its run_id must agree with that name and is never used to locate the record.
    # A mismatch is never healed: run.json keeps the forged run_id and every later resume is red again.
    if spec.get("run_id") != run_dir.name:
        spec.setdefault("resumes", []).append({"rc": -1, "out": str(run_dir / f"stdout.{n}.md")})
        return _red_before_run(spec, run_dir, "snapshot-tampered",
                               f"run.json run_id {spec.get('run_id')!r} differs from run directory {run_dir.name!r}",
                               home, f"stdout.{n}.md", "TAMPERED")
    # 025 (#104): the trusted script copy is located by the run directory's name, never by run.json's scripts_dir.
    if _BROKER_SAFE_WRITES:
        sdir, ssrc = _INHERITED_SCRIPTS or (SCRIPTS, "installed")
    elif spec.get("scripts_source") == "checkout":
        sdir, ssrc = _trust_path(run_dir.name) / "workerbee" / "scripts", "checkout"
        if spec.get("scripts_dir") != str(sdir):
            spec.setdefault("resumes", []).append({"rc": -1, "out": str(run_dir / f"stdout.{n}.md")})
            return _red_before_run(spec, run_dir, "snapshot-tampered",
                                   f"run.json scripts_dir {spec.get('scripts_dir')!r} differs from the trusted copy {str(sdir)!r}",
                                   home, f"stdout.{n}.md", "TAMPERED")
    else:
        sdir, ssrc = SCRIPTS, "installed"
    spec["scripts_dir"], spec["scripts_source"] = str(sdir), ssrc
    # Trust mode comes from the context, not from run.json (delegate-writable): a private record always wins.
    claimed = spec.get("snapshot_trust")
    if not _BROKER_SAFE_WRITES and (_trust_path(run_dir.name) / "trust.json").is_file():
        spec["snapshot_trust"] = "private"
    elif claimed == "private":
        pass  # no private record: _verify reports snapshot-error, never a run-dir fallback
    elif claimed == "broker" and _BROKER_SAFE_WRITES:
        pass
    elif claimed is not None:  # broker claim outside a broker context, or an unknown value
        spec.setdefault("resumes", []).append({"rc": -1, "out": str(run_dir / f"stdout.{n}.md")})
        return _red_before_run(spec, run_dir, "snapshot-tampered",
                               f"run.json snapshot_trust {claimed!r} does not match this context",
                               home, f"stdout.{n}.md", "TAMPERED")
    elif _BROKER_SAFE_WRITES and (run_dir / "trust.json").is_file():
        spec["snapshot_trust"] = "broker"
    else:
        spec["snapshot_trust"] = "run-dir"  # legacy run: run.json has no snapshot_trust key
    lead_dir = Path(spec["lead_dir"]) if kind == "claude" and spec.get("lead_dir") else None
    if lead_dir is not None:  # D60: re-attach the Lead's broker; its counters reload from lead_dir/run.json
        cfg = lead_dir / "lead_mcp.json"
        if cfg.is_symlink() or not cfg.is_file():
            print(f"dispatch: lead-dir-missing: {lead_dir}; cannot resume a Lead without its broker run directory",
                  file=sys.stderr)
            return EXIT_USAGE
    try:
        result = launch(kind, spec["model"], spec["effort"], Path(spec["cwd"]), args.message, run_dir,
                        spec.get("permission_mode", DEFAULT_PERMISSION_MODE), resume=spec["session_id"],
                        **({"lead_dir": lead_dir} if lead_dir is not None else {}),
                        **({"codex_write": True} if spec.get("codex_write") is True else {}),
                        **({"codex_network": True} if spec.get("codex_network") is True else {}),
                        **({"allowed_tools": spec.get("allowed_tools"), "disallowed_tools": spec.get("disallowed_tools")}
                           if kind == "claude" else {}))
    except Exception as exc:
        # the failed attempt is a turn: the broker reads it back as outcome red / reason launch-failed
        spec.setdefault("resumes", []).append({"rc": -1, "out": str(run_dir / f"stdout.{n}.md")})
        return _launch_failed(spec, run_dir, exc, home, f"stdout.{n}.md")
    out_path = run_dir / f"stdout.{n}.md"
    _wtext(out_path, result["stdout"])
    _wtext(run_dir / f"stderr.{n}.txt", result["stderr"])
    spec.setdefault("resumes", []).append({"rc": result["rc"], "out": str(out_path)})
    if lead_dir is not None:
        _record_lead(spec, lead_dir)
    spec["rc"] = result["rc"]
    if result.get("session_id"):
        spec["session_id"] = result["session_id"]
    return _finish(spec, run_dir, out_path, result, getattr(args, "home_repo", None), f"verify.{n}.txt")


# ---------------------------------------------------------------------------
# D51 credential-blind dispatch broker: `agents-inc dispatch --serve <run-dir>`.
# The Lead writes <id>.request.json (via .tmp rename) and lead.done into
# <run-dir>/inbox/, its only write grant. The broker validates each request against
# broker-owned run.json, runs one D47 dispatch under <run-dir>/workers/<id>/, and
# writes <run-dir>/<id>.report.md then <run-dir>/<id>.result.json. Sequential only (MVP).
# ---------------------------------------------------------------------------
REQUEST_SCHEMA_VERSION = 1
REQUEST_MAX_BYTES = 64 * 1024
REQUEST_KEYS = frozenset({"schema_version", "request_id", "model", "effort", "tier", "slots"})
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
REQUEST_FILE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]{0,63})\.request\.json$")
SLOT_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
# Slots a request may never set: the broker owns these through run.json.
BROKER_OWNED_SLOTS = frozenset({"PERMISSION_MODE", "BASH_ALLOW"})
# Efforts for a model without `supported_efforts` in models.json (Claude: passed as `claude -p --effort`).
DEFAULT_EFFORTS = ("low", "medium", "high", "max")
INBOX = "inbox"  # the only Lead-writable path in a run directory (D51)
LEAD_DONE = "lead.done"
SCOPE_LINE = "SCOPE BOILERPLATE: repo-scoped writes only"
# Request text that points the credential-bearing Worker at secrets is refused.
# #95: ~/.claude/skills/ paths (workerbee scripts) pass unless a later .. climbs out.
_HOME_CRED = r"(~|\$HOME|\$\{HOME\}|/Users/[^/\s]+|/home/[^/\s]+|/root)/\.(claude(?!/skills/(?!\S*\.\.))|codex|ssh|config|aws|gnupg|netrc|local|codex-bridge)\b"
# 025 (#85, #87): the slot text screen matches locations, never bare words such as credentials, token or api_key.
# A home directory matches only with a further non-glob segment, so deny-list prose (`~/.claude/**`) passes;
# ~/.local/bin/ and ~/.local/share/agents-inc/ are exempt like ~/.claude/skills/; so is the instruction file ~/.claude/AGENTS.md
# when it ends the path (#146).
_HOME_CRED_TEXT = (r"(~|\$HOME|\$\{HOME\}|/Users/[^/\s]+|/home/[^/\s]+|/root)/\.(claude(?!/skills/(?!\S*\.\.))(?!/AGENTS\.md(?=$|[\s'\"`,;)]))|codex|ssh"
                   r"|config|aws|gnupg|netrc|local(?!/(?:bin|share/agents-inc)/(?!\S*\.\.))|codex-bridge)\b"
                   r"/(?![^\s/]*[*?\[])[^\s/'\"`,;)]+")
_ENV_READ_VERBS = r"cat|read|print|open|source|dump|echo|show|less|head|tail"
CREDENTIAL_RE = re.compile(
    _HOME_CRED_TEXT
    + r"|(?<![^\s/='\"])(?:id_rsa|id_ed25519|[^\s/]*\.(?:pem|key))(?=$|[\s/'\".,;:)])"  # key files as path tokens
    + r"|(?<=[/~])\.env(?:\.[\w.-]+)?\b"  # .env after a path separator or ~
    + r"|`[^`\n]*?(?<![\w-])(?:" + _ENV_READ_VERBS + r")\s+\.env(?:\.[\w.-]+)?(?=[\s`])[^`\n]*`",  # `cat .env`
    re.IGNORECASE)
# Gate and BASH_ALLOW screen: names a credential path, not a word. test_token_refresh.py and check_credentials_schema.py pass.
GATE_CREDENTIAL_RE = re.compile(
    _HOME_CRED + r"|(?:^|[\s/='\"])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|[^\s/]*\.(?:pem|key))(?=$|[\s/'\"])",
    re.IGNORECASE)
# A gate argv element or BASH_ALLOW token whose basename is a secret file name: credentials.json, /tmp/token, api_key.txt,
# .secrets. A leading word such as test_ or check_ keeps test_token_refresh.py and check_credentials_schema.py legal.
CREDENTIAL_BASENAME_RE = re.compile(r"^\.?(?:credentials?|tokens?|api[_-]?key|secrets?)(?:$|[._-])", re.IGNORECASE)


_KEYPEM_RE = re.compile(r"\.(?:pem|key)(?:\.|$)")
_TOKEN_START_RE = re.compile(r"^\.?tokens?(?:$|[._-])")
_SECRET_WORD_RE = re.compile(r"(?:^|[._-])(?:credentials?|api[_-]?key|secrets?)(?:$|[._-])")
_SECRET_ENV_RE = re.compile(r"^[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*$")
_SECRET_FLAG_RE = re.compile(r"token|secret|password|api[_-]?key")


def _part_names_credential(part: str) -> bool:
    if _SECRET_ENV_RE.match(part):
        return True
    if part.startswith("-") and _SECRET_FLAG_RE.search(part.lower()):
        return True
    b = part.rstrip("/").rsplit("/", 1)[-1].lower()
    if b.endswith(".env") or ".env." in b or _KEYPEM_RE.search(b) or _TOKEN_START_RE.match(b):
        return True
    return not b.startswith(("test_", "check_")) and bool(_SECRET_WORD_RE.search(b))


def names_credential(tokens) -> bool:
    """True when any token (or a value after `=`) names a secret file, env var or flag.

    Rules: basename ends in .env or has .env.; has .pem/.key followed by end or a dot; starts with token(s);
    has credential(s), api_key or secret(s) at a word boundary (not after test_/check_); env-var name with
    KEY/TOKEN/SECRET/PASSWORD; flag naming token, secret, password or api-key."""
    return any(_part_names_credential(p) for t in tokens for p in str(t).split("="))


BROKER_OK, BROKER_FATAL, BROKER_USAGE = 0, 1, 2
BROKER_LOCK = "broker.lock"  # flock target in the run directory; never unlinked, never in a sandbox grant
REQ_GREEN, REQ_RED, REQ_USAGE, REQ_REFUSED = 0, 1, 2, 3
REQ_STATUS = {REQ_GREEN: "green", REQ_RED: "red", REQ_USAGE: "usage-error", REQ_REFUSED: "refused"}


def _req_status(code: int, outcome) -> str:
    """Broker request status; a clean child with no gates to check (outcome unverified, exit 0) is "unverified"."""
    return "unverified" if code == REQ_GREEN and outcome == "unverified" else REQ_STATUS[code]


class BrokerFatal(Exception):
    """Broker I/O failure that stops the serve loop (exit 1)."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_new(path: Path, text: str) -> None:
    """Write text to path atomically; never overwrite and never follow a planted link.
    Raises FileExistsError when path already exists."""
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.broker-tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.link(str(tmp), str(path))  # fails if path exists (file or symlink)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(str(tmp))


def _atomic_write_json(path: Path, data: dict, overwrite: bool = False) -> None:
    """Atomic JSON write. overwrite=False never replaces an existing path."""
    text = json.dumps(data, indent=1) + "\n"
    if not overwrite:
        _write_new(path, text)
        return
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.broker-tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(str(tmp), str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(str(tmp))
        raise


def _load_run_manifest(run_dir: Path) -> dict:
    """Read and validate broker-owned run.json; raise ValueError on any defect."""
    path = run_dir / "run.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("run.json missing or not a regular file")
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("run.json schema_version must be 1")
    models = spec.get("worker_models")
    if (not isinstance(models, list) or not models
            or not all(isinstance(m, str) and _kind(m) in ("claude", "codex") for m in models)):
        raise ValueError("run.json worker_models must list supported models")  # spec 037 FR-013: no free model as a Worker
    fan = spec.get("fan_out")
    if (not isinstance(fan, dict) or set(fan) != {"width", "total", "depth"}
            or not all(type(fan[k]) is int and fan[k] >= 0 for k in fan)):
        raise ValueError("run.json fan_out must be {width, total, depth} non-negative integers")
    cwd = spec.get("cwd")
    if not isinstance(cwd, str) or not os.path.isabs(cwd) or not Path(cwd).is_dir():
        raise ValueError("run.json cwd must be an existing absolute directory")
    # A Worker with a writable cwd could rewrite the broker's own scripts (`_load` re-executes them per call).
    # An installed release under ~/.local is never inside a Worker cwd, so it is unaffected.
    if REPO_ROOT.resolve().is_relative_to(Path(cwd).resolve()):
        raise ValueError("broker-code-in-workspace: the broker source checkout is inside the Worker cwd")
    mode = spec.get("permission_mode", DEFAULT_PERMISSION_MODE)
    if not isinstance(mode, str) or not mode:
        raise ValueError("run.json permission_mode must be a string")
    return spec


def _validate_request(inbox: Path, name: str, spec: dict) -> tuple[dict | None, str | None]:
    """Return (request, None) or (None, reason) for <inbox>/<name>. Never trusts paths inside the request."""
    req, reason = _read_request(inbox, name)
    if req is None:
        return None, reason
    return _validate_fields(req, spec, REQUEST_FILE_RE.match(name).group(1))


def _read_request(inbox: Path, name: str) -> tuple[object, str | None]:
    """Return (parsed JSON, None) or (None, reason) for <inbox>/<name>: regular file, size limit, valid JSON."""
    m = REQUEST_FILE_RE.match(name)
    if not m:
        return None, "bad-filename"
    path = inbox / name
    try:
        st = os.lstat(str(path))
    except OSError:
        return None, "unreadable"
    import stat as _stat
    if not _stat.S_ISREG(st.st_mode):
        return None, "not-regular-file"
    if st.st_size > REQUEST_MAX_BYTES:
        return None, "too-large"
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as fh:
            raw = fh.read(REQUEST_MAX_BYTES + 1)
    except OSError:
        return None, "unreadable"
    if len(raw) > REQUEST_MAX_BYTES:
        return None, "too-large"
    try:
        return json.loads(raw.decode("utf-8")), None
    except (UnicodeDecodeError, ValueError):
        return None, "bad-json"


def _validate_fields(req, spec: dict, expected_id: str) -> tuple[dict | None, str | None]:
    """Shared by the file inbox and the MCP transport: check a parsed request against run.json."""
    if not isinstance(req, dict) or set(req) != REQUEST_KEYS:
        return None, "bad-keys"
    if req["schema_version"] != REQUEST_SCHEMA_VERSION or type(req["schema_version"]) is not int:
        return None, "bad-schema-version"
    rid = req["request_id"]
    if not isinstance(rid, str) or not REQUEST_ID_RE.match(rid) or rid != expected_id:
        return None, "bad-request-id"
    model = req["model"]
    if not isinstance(model, str) or model not in spec["worker_models"] or _kind(model) not in ("claude", "codex"):
        return None, "model-not-allowed"  # spec 037 FR-013: a free slug is never a Worker, Lead or reviewer
    if req["effort"] not in _efforts_for(model):
        return None, "bad-effort"
    rung = _load("dispatch_rungs", _scripts(spec)).MODEL_RUNG.get(model)
    if req["tier"] != rung:
        return None, "tier-model-mismatch"
    slots = req["slots"]
    if not isinstance(slots, dict) or not slots:
        return None, "bad-slots"
    for key, value in slots.items():
        if not SLOT_KEY_RE.match(key) or not isinstance(value, str):
            return None, "bad-slots"
        if key in BROKER_OWNED_SLOTS:
            return None, "broker-owned-slot"
    if "FAN_OUT" in slots and parse_fan_out("FAN_OUT: " + slots["FAN_OUT"]) != {"width": 0, "total": 0, "depth": 0}:
        return None, "worker-cannot-lead"  # D60: a broker Worker never leads (#73); send 'width 0, total 0, depth 0' or omit it
    if control_char_hit(slots):
        return None, "refused-control-char"
    if _reject_credential_seeking(slots):
        return None, "credential-seeking"
    if _kind(model) == "claude" and not sandbox_available():
        return None, "no-sandbox-backend"
    return req, None


# 026 US4 (#109): same pattern as skills/workerbee/scripts/render_dispatch.py (a pinned checkout copy of that
# script may predate it, so it is not loaded from there); tests pin the two equal.
CONTROL_CHAR_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f؜‎‏‪-‮⁦-⁩]")


def _nested_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _nested_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _nested_strings(item)


def control_char_hit(slots) -> tuple[str, str, int] | None:
    """(top-level slot key, `U+XXXX`, code-point offset) of the first refused character, else None."""
    for key, value in (slots.items() if isinstance(slots, dict) else ()):
        for text in _nested_strings(value):
            match = CONTROL_CHAR_RE.search(text)
            if match:
                return key, f"U+{ord(match.group(0)):04X}", match.start()
    return None


def credential_hit(slots) -> str | None:
    """#95: `slot <KEY> matched '<text>'` for the first slot value the D51 screen refuses, else None."""
    for key, value in (slots.items() if isinstance(slots, dict) else ()):
        match = CREDENTIAL_RE.search(value) if isinstance(value, str) else None
        if match:
            return f"slot {key} matched {match.group(0)!r}"
    return None


def _reject_credential_seeking(slots: dict) -> bool:
    """True when any slot value names a credential location or secret (D51 screen; not a sandbox)."""
    return credential_hit(slots) is not None


# Broker effort allowlist; ultra auto-delegates outside the control loop (SKILL.md:313) and xhigh stays refused.
BROKER_EFFORTS = ("low", "medium", "high", "max")


def _efforts_for(model: str) -> tuple:
    """Efforts from the model's agents_inc/models.json entry; Codex aliases map through runtime.MODEL_ALIASES."""
    from .runtime import MODEL_ALIASES
    try:
        models = json.loads((REPO_ROOT / "agents_inc" / "models.json").read_text(encoding="utf-8"))["models"]
    except (OSError, ValueError, KeyError):
        return ()
    entry = models.get(MODEL_ALIASES.get(model, model))
    if not isinstance(entry, dict):
        return ()
    efforts = entry.get("supported_efforts")
    allowed = tuple(efforts) if isinstance(efforts, list) else DEFAULT_EFFORTS
    return tuple(e for e in allowed if e in BROKER_EFFORTS)


def _write_request_result(run_dir: Path, rid: str, result: dict, report_text: str) -> None:
    """Write <id>.report.md then <id>.result.json; neither is ever overwritten."""
    report = run_dir / f"{rid}.report.md"
    _write_new(report, report_text)
    result = dict(result, schema_version=1, request_id=rid, report_path=str(report))
    _atomic_write_json(run_dir / f"{rid}.result.json", result)


def _process_request(run_dir: Path, rid: str, req: dict, spec: dict, home_repo: str | None = None) -> dict:
    """Reserve one fan-out slot, run one D47 dispatch, return the result fields."""
    started = _now()
    base = {"child_run_id": None, "outcome": None, "reason": None, "started_at": started}
    fan = spec["fan_out"]
    if fan["total"] == 0 or fan["width"] == 0:
        return dict(base, status="refused", dispatch_exit_code=REQ_REFUSED, reason="fan-out-zero", finished_at=_now())
    if spec["workers_spawned"] >= fan["total"]:
        return dict(base, status="refused", dispatch_exit_code=REQ_REFUSED, reason="fan-out-total-exhausted",
                    finished_at=_now())
    workers = run_dir / "workers"
    if workers.is_symlink() or (workers.exists() and not workers.is_dir()):
        raise BrokerFatal("workers directory is not a real directory")
    workers.mkdir(exist_ok=True)
    wdir = workers / rid
    wdir.mkdir()  # FileExistsError for a planted path: caller refuses
    slots = dict(req["slots"])
    slots.setdefault("FAN_OUT", "width 0, total 0, depth 0")  # D60: render would fill the rung default, which leads
    slots["PERMISSION_MODE"] = spec.get("permission_mode", DEFAULT_PERMISSION_MODE)
    slots_path = wdir / "slots.json"
    _atomic_write_json(slots_path, slots)
    child_parent = wdir / "runs"
    with _SPEC_LOCK:
        spec["workers_spawned"] += 1  # reserved before launch
        _atomic_write_json(run_dir / "run.json", spec, overwrite=True)  # persist the reservation at once
    import argparse
    args = argparse.Namespace(slots=str(slots_path), model=req["model"], effort=req["effort"], cwd=spec["cwd"],
                              tier="grunt" if req["tier"] == "grunt" else None, run_dir=str(child_parent),
                              dry_run=False, resume=None, message=None, home_repo=home_repo)
    out = io.StringIO()
    launches_before = _LAUNCHES
    rc, crash = _in_worker_scope(run_dir, rid, out, lambda: run(args), spec)
    child = None
    children = sorted(p for p in child_parent.iterdir() if p.is_dir() and not p.is_symlink()) if child_parent.is_dir() else []
    if children:
        child = children[-1]
    cspec = {}
    if child is not None:
        with contextlib.suppress(OSError, ValueError):
            cspec = json.loads((child / "run.json").read_text(encoding="utf-8"))
    launched = _LAUNCHES > launches_before
    if not launched:
        with _SPEC_LOCK:
            spec["workers_spawned"] -= 1  # never launched: release the reservation
    code = rc if rc in REQ_STATUS else REQ_RED
    return dict(base, status=_req_status(code, cspec.get("outcome")), dispatch_exit_code=code,
                child_run_id=cspec.get("run_id") or (child.name if child else None),
                outcome=cspec.get("outcome"), reason=crash or cspec.get("reason") or (None if code == REQ_GREEN else "dispatch-rc"),
                finished_at=_now(), status_line=out.getvalue().strip(),
                _report_path=str(child / "stdout.md") if (child and launched) else None)


def _kind_keys(req, keys: frozenset) -> bool:
    """D54 request kinds: exactly keys, plus an optional schema_version 1."""
    if not isinstance(req, dict) or set(req) - {"schema_version"} != keys:
        return False
    return "schema_version" not in req or (type(req["schema_version"]) is int and req["schema_version"] == 1)


def _handle_one(run_dir: Path, name: str, spec: dict, seen: set, home_repo: str | None, issued: set | None = None,
                busy: bool = False):
    """Handle one inbox file. Return None when handled, "busy" when a dispatch or resume must wait for the
    running turn (answers never wait), or a Turn to start."""
    issued = set() if issued is None else issued
    counts = spec["request_counts"]
    m = REQUEST_FILE_RE.match(name)
    rid = m.group(1) if m else None
    inbox = run_dir / INBOX
    req_path = inbox / name
    if rid and (rid in seen or os.path.lexists(str(run_dir / f"{rid}.result.json"))):
        with _SPEC_LOCK:
            counts["duplicate"] += 1
        _set_aside(req_path, f"{name}.duplicate-{secrets.token_hex(3)}")
        return None
    raw, reason = _read_request(inbox, name)
    kind = raw.get("kind") if isinstance(raw, dict) else None
    extra = {}
    if kind == "answer":
        if not _kind_keys(raw, ANSWER_KEYS):
            reason = "bad-keys"
        elif raw["request_id"] not in issued:
            reason = "unknown-request"
        else:
            fields, reason = answer_question(run_dir, spec, raw["request_id"], raw["question_n"], raw["text"])
            if reason is None:
                seen.add(rid)
                now = _now()
                _write_request_result(run_dir, rid, dict(fields, answered_request_id=fields["request_id"],
                                                         started_at=now, finished_at=now), "answered\n")
                _set_aside(req_path, f"{name}.processed")
                return None
        req = None
    elif busy and raw is not None:
        return "busy"
    elif kind == "resume":
        req, plan = None, None
        if not _kind_keys(raw, RESUME_KEYS):
            reason = "bad-keys"
        else:
            plan, reason = plan_resume(run_dir, spec, raw["request_id"], raw["message"], issued.__contains__)
        if plan is not None and plan["new_rid"] != rid:
            plan, reason, extra = None, "bad-request-id", {"expected_request_id": plan["new_rid"]}
        if plan is not None:
            seen.add(rid)
            issued.add(rid)
            with _SPEC_LOCK:
                spec.setdefault("resume_of", {})[rid] = plan["root"]
            _set_aside(req_path, f"{name}.processed")
            message = raw["message"]
            return Turn(run_dir, rid, lambda: run_resume(run_dir, plan, message, spec, home_repo), spec,
                        lambda: _atomic_write_json(run_dir / "run.json", spec, overwrite=True), (OSError, BrokerFatal))
    else:
        req, reason = (None, reason) if raw is None else _validate_fields(raw, spec, rid)
        if reason == "credential-seeking":  # #95: name the slot and the matched text so the Lead fixes it once
            detail = credential_hit(raw.get("slots"))
            if detail:
                extra = dict(extra, reason_detail=detail)
        elif reason == "refused-control-char":  # 026: name the slot and the code point
            hit = control_char_hit(raw.get("slots"))
            if hit:
                extra = dict(extra, reason_detail=f"slot {hit[0]} {hit[1]}")
    if rid:
        seen.add(rid)
    if req is None:
        with _SPEC_LOCK:
            counts["refused"] += 1
        if rid:
            _write_request_result(run_dir, rid, dict({"status": "refused", "dispatch_exit_code": REQ_REFUSED,
                                                      "child_run_id": None, "outcome": None, "reason": reason,
                                                      "started_at": _now(), "finished_at": _now()}, **extra),
                                  f"refused: {reason}\n")
        _set_aside(req_path, f"{name}.rejected")
        return None
    issued.add(rid)
    _set_aside(req_path, f"{name}.processed")
    return Turn(run_dir, rid, lambda: _run_validated(run_dir, rid, req, spec, home_repo), spec,
                lambda: _atomic_write_json(run_dir / "run.json", spec, overwrite=True), (OSError, BrokerFatal))


def _run_validated(run_dir: Path, rid: str, req: dict, spec: dict, home_repo: str | None) -> tuple[dict, str]:
    """Process one validated request and count it; return (result fields, report text). Both transports use this."""
    try:
        result = _process_request(run_dir, rid, req, spec, home_repo)
    except FileExistsError:
        result = {"status": "refused", "dispatch_exit_code": REQ_REFUSED, "child_run_id": None, "outcome": None,
                  "reason": "worker-dir-exists", "started_at": _now(), "finished_at": _now()}
    report_src = result.pop("_report_path", None)
    report_text = f"{result['status']}: {result.get('reason') or 'no worker report'}\n"
    if report_src:
        with contextlib.suppress(OSError):
            report_text = Path(report_src).read_text(encoding="utf-8")
    with _SPEC_LOCK:
        spec["request_counts"][result["status"]] = spec["request_counts"].get(result["status"], 0) + 1
    return result, report_text


def _in_worker_scope(run_dir: Path, rid: str, out, fn, spec: dict | None = None) -> tuple[int, str | None]:
    """Run fn (a D47 run or resume) with the broker's Worker confinement on; return (rc, crash reason). spec: the
    Lead run.json; a Claude Lead's (parent_run_id) grants become the Worker's ceiling (D60)."""
    global _BROKER_SAFE_WRITES, _BROKER_DENY, _WORKER_ASK, _GRANT_CEILING, _INHERITED_SCRIPTS
    with contextlib.redirect_stdout(out):
        try:
            _BROKER_SAFE_WRITES, _WORKER_ASK = True, rid
            if spec and spec.get("scripts_source") == "checkout":  # 025 (#104): the Worker inherits the Lead's scripts
                _INHERITED_SCRIPTS = (_scripts(spec), "checkout")
            if spec and spec.get("parent_run_id"):
                _GRANT_CEILING = (list(spec.get("parent_allowed_tools") or []), list(spec.get("parent_disallowed_tools") or []))
            codex_home = os.environ.get("CODEX_HOME")  # read, never logged
            _BROKER_DENY = (Path(run_dir).resolve(),) + ((Path(codex_home).resolve(),) if codex_home else ())
            return fn(), None
        except Exception as exc:  # one bad request never stops the broker
            return REQ_RED, f"dispatch-exception:{type(exc).__name__}"
        finally:
            _BROKER_SAFE_WRITES, _WORKER_ASK = False, None
            _BROKER_DENY, _GRANT_CEILING, _INHERITED_SCRIPTS = (), None, None


# ---------------------------------------------------------------------------
# D54 delegate turns. A Worker turn (dispatch or resume) runs in a thread so the broker keeps serving while the
# Worker waits on ask_lead: wait returns needs-lead with the screened question, answer writes the reply into the
# Worker's channel. One turn at a time (the confinement state above is process-wide). A resume continues a
# finished Worker in its own child run directory under a new id <root>-r<n>; it never charges fan-out.
# ---------------------------------------------------------------------------
_SPEC_LOCK = threading.RLock()  # run.json state is shared by the serve loop and the turn thread
RESUME_KEYS = frozenset({"kind", "request_id", "message"})
ANSWER_KEYS = frozenset({"kind", "request_id", "question_n", "text"})
QUESTION_MAX_BYTES = 16 * 1024
NEEDS_LEAD_EXIT = 10  # `dispatch --wait`: a Worker asked a question; answer it, then wait again


def resume_cap(model: str) -> int:
    """Operator ruling 2026-10-04: 1 resume for a Grunt Worker, 2 for Workhorse and above."""
    return 1 if _load("dispatch_rungs").MODEL_RUNG.get(model) == "grunt" else 2


class Turn:
    """One Worker turn in a thread. fn returns (result fields, report text); the result is written when it ends.
    fatal: exception types re-raised to the owner (the file broker stops on them); others become a red result."""

    def __init__(self, run_dir: Path, rid: str, fn, spec: dict, save, fatal: tuple = ()):
        self.run_dir, self.rid, self.fn, self.spec, self.save, self.fatal = run_dir, rid, fn, spec, save, fatal
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "Turn":
        self.thread.start()
        return self

    def alive(self) -> bool:
        return self.thread.is_alive()

    def _run(self) -> None:
        try:
            result, report = self.fn()
        except self.fatal as exc:
            self.error = exc
            return
        except Exception as exc:
            reason = f"exception:{type(exc).__name__}"
            result, report = {"status": "red", "dispatch_exit_code": REQ_RED, "child_run_id": None, "outcome": None,
                              "reason": reason, "started_at": _now(), "finished_at": _now()}, f"red: {reason}\n"
        try:
            with _SPEC_LOCK:
                _write_request_result(self.run_dir, self.rid, result, report)
                self.save()
        except Exception as exc:
            self.error = exc


def _root_of(spec: dict, rid: str) -> str:
    return spec.get("resume_of", {}).get(rid, rid)


def _child_dir(run_dir: Path, root: str) -> Path | None:
    """The Worker's child run directory under workers/<root>/runs (broker-owned), or None."""
    runs = Path(run_dir) / "workers" / root / "runs"
    if not runs.is_dir() or runs.is_symlink():
        return None
    children = sorted(p for p in runs.iterdir() if p.is_dir() and not p.is_symlink())
    return children[-1] if children else None


def _read_small(path: Path, limit: int) -> bytes | None:
    """Read at most limit+1 bytes from a regular file without following a link; None when absent or unreadable."""
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    with os.fdopen(fd, "rb") as fh:
        import stat as _stat
        if not _stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return None
        return fh.read(limit + 1)


def screen_text(text: str, limit: int = QUESTION_MAX_BYTES) -> str:
    """What the Lead may see of Worker text: at most limit bytes, and no environment value of 8 or more
    characters, plain or encoded as base64 (standard or URL-safe, with or without padding), percent-encoding or
    hex (each form is replaced by [redacted]; spec 018 FR-011)."""
    text = text.encode("utf-8")[:limit].decode("utf-8", "ignore")
    forms = set()
    for value in {v for v in os.environ.values() if len(v) >= 8}:
        raw = value.encode()
        b64, url = base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode()
        forms.update((value, b64, b64.rstrip("="), url, url.rstrip("="), urllib.parse.quote(value, safe=""),
                      raw.hex(), raw.hex().upper()))
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, "[redacted]")
    return text


def relay_question(run_dir: Path, spec: dict, rid: str) -> dict | None:
    """Find the lowest unanswered question of turn rid in the Worker's channel, copy it screened to
    <run-dir>/<rid>.question.<n>.json (once; counted in run.json `questions`), and return the needs-lead fields."""
    child = _child_dir(run_dir, _root_of(spec, rid))
    if child is None:
        return None
    ask, n = child / ASK_DIR, 1
    while os.path.lexists(str(ask / f"{rid}.question.{n}.json")):
        if not os.path.lexists(str(Path(run_dir) / f"{rid}.answer.{n}.json")):
            break
        n += 1
    else:
        return None
    lead_copy = Path(run_dir) / f"{rid}.question.{n}.json"
    if not lead_copy.is_file():
        raw = _read_small(ask / f"{rid}.question.{n}.json", QUESTION_MAX_BYTES * 2)
        try:
            question = json.loads(raw.decode("utf-8"))["question"] if raw else None
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            question = None
        text = screen_text(question) if isinstance(question, str) else "(question unreadable; answer or tell the Worker to stop)"
        with _SPEC_LOCK:
            try:
                _atomic_write_json(lead_copy, {"request_id": rid, "question_n": n, "question": text, "relayed_at": _now()})
            except FileExistsError:
                pass
            else:
                spec["questions"] = spec.get("questions", 0) + 1
    data = json.loads(lead_copy.read_text(encoding="utf-8"))
    return {"status": "needs-lead", "request_id": rid, "question_n": n, "question": data.get("question", "")}


def pending_question(run_dir: Path, rid: str) -> dict | None:
    """The lowest relayed question of rid with no answer yet, as needs-lead fields; None when there is none."""
    n = 1
    while (Path(run_dir) / f"{rid}.question.{n}.json").is_file():
        if not os.path.lexists(str(Path(run_dir) / f"{rid}.answer.{n}.json")):
            raw = _read_small(Path(run_dir) / f"{rid}.question.{n}.json", QUESTION_MAX_BYTES * 2)
            try:
                question = json.loads(raw.decode("utf-8")).get("question", "") if raw else ""
            except (ValueError, AttributeError, UnicodeDecodeError):
                question = ""
            return {"status": "needs-lead", "request_id": rid, "question_n": n, "question": question}
        n += 1
    return None


def answer_question(run_dir: Path, spec: dict, rid, n, text) -> tuple[dict, str | None]:
    """Write the Lead's answer into the Worker's channel. Return (fields, refusal reason or None)."""
    if not isinstance(rid, str) or not REQUEST_ID_RE.match(rid):
        return {}, "bad-request-id"
    if isinstance(n, bool) or not isinstance(n, int) or n < 1 or not isinstance(text, str):
        return {}, "bad-arguments"
    if len(text.encode("utf-8")) > REQUEST_MAX_BYTES:
        return {}, "oversize"
    if _reject_credential_seeking({"TEXT": text}):
        return {}, "credential-seeking"
    if not (Path(run_dir) / f"{rid}.question.{n}.json").is_file():
        return {}, "unknown-question"
    child = _child_dir(run_dir, _root_of(spec, rid))
    if child is None:
        return {}, "unknown-question"
    now = _now()
    try:
        _write_new(Path(run_dir) / f"{rid}.answer.{n}.json", json.dumps({"request_id": rid, "question_n": n,
                                                                          "answered_at": now}) + "\n")
    except FileExistsError:
        return {}, "already-answered"
    try:
        _write_new(child / ASK_DIR / f"{rid}.answer.{n}.json", json.dumps({"answer": text, "answered_at": now}) + "\n")
    except OSError:
        return {}, "already-answered"  # a planted file or link in the channel: the Worker reads nothing new
    return {"status": "answered", "request_id": rid, "question_n": n}, None


def plan_resume(run_dir: Path, spec: dict, rid, message, known) -> tuple[dict | None, str | None]:
    """Check a resume request. known(rid) says whether this broker issued rid. Return (plan, None) with the
    root id, new id, turn number, and child directory, or (None, reason)."""
    if not isinstance(rid, str) or not REQUEST_ID_RE.match(rid):
        return None, "bad-request-id"
    if not isinstance(message, str) or not message.strip():
        return None, "bad-message"
    if len(json.dumps({"request_id": rid, "message": message}).encode("utf-8")) > REQUEST_MAX_BYTES:
        return None, "oversize"
    if control_char_hit({"MESSAGE": message}):
        return None, "refused-control-char"
    if _reject_credential_seeking({"MESSAGE": message}):
        return None, "credential-seeking"
    if not known(rid):
        return None, "unknown-request"
    result_path = Path(run_dir) / f"{rid}.result.json"
    if not result_path.is_file() or result_path.is_symlink():
        return None, "request-running"
    try:
        status = json.loads(result_path.read_text(encoding="utf-8")).get("status")
    except (OSError, ValueError):
        return None, "unknown-request"
    if status not in ("green", "red", "unverified"):
        return None, "not-resumable"
    root = _root_of(spec, rid)
    child = _child_dir(run_dir, root)
    try:
        cspec = json.loads((child / "run.json").read_text(encoding="utf-8")) if child else None
    except (OSError, ValueError):
        cspec = None
    if not cspec or not cspec.get("session_id"):
        return None, "no-session"
    turn = len(cspec.get("resumes", [])) + 1
    if turn > resume_cap(cspec.get("model", "")):
        return None, "resume-cap"
    new_rid = f"{root}-r{turn}"
    if not REQUEST_ID_RE.match(new_rid):
        return None, "bad-request-id"
    return {"root": root, "new_rid": new_rid, "turn": turn, "child": child, "parent": rid}, None


def run_resume(run_dir: Path, plan: dict, message: str, spec: dict, home_repo: str | None) -> tuple[dict, str]:
    """Run one resume turn on the Worker's child run directory; return (result fields, report text)."""
    import argparse
    child = plan["child"]
    args = argparse.Namespace(resume=child.name, message=message, run_dir=str(child.parent), cwd=spec["cwd"],
                              home_repo=home_repo)
    started, out = _now(), io.StringIO()
    rc, crash = _in_worker_scope(run_dir, plan["new_rid"], out, lambda: resume(args), spec)
    cspec = {}
    with contextlib.suppress(OSError, ValueError):
        cspec = json.loads((child / "run.json").read_text(encoding="utf-8"))
    turns = cspec.get("resumes") or []
    ran = len(turns) >= plan["turn"]
    code = rc if rc in REQ_STATUS else REQ_RED
    result = {"status": _req_status(code, cspec.get("outcome") if ran else None), "dispatch_exit_code": code,
              "child_run_id": child.name,
              "outcome": cspec.get("outcome") if ran else None,
              "reason": crash or (cspec.get("reason") if ran else None) or (None if code == REQ_GREEN else "dispatch-rc"),
              "started_at": started, "finished_at": _now(), "status_line": out.getvalue().strip(),
              "resumed_from": plan["root"], "turn": plan["turn"]}
    report = f"{result['status']}: {result.get('reason') or 'no worker report'}\n"
    if ran:
        with contextlib.suppress(OSError):
            report = (child / f"stdout.{plan['turn']}.md").read_text(encoding="utf-8")
    with _SPEC_LOCK:
        spec["request_counts"][result["status"]] = spec["request_counts"].get(result["status"], 0) + 1
        spec["resumes"] = spec.get("resumes", 0) + 1
    return result, report


def _set_aside(path: Path, new_name: str) -> None:
    with contextlib.suppress(OSError):
        os.rename(str(path), str(path.with_name(new_name)))


def init_broker_state(spec: dict, poll_interval: float | None = None, idle_timeout: float | None = None,
                      transport: str = "file") -> None:
    """Broker owns run.json from here on: in-memory state wins over any later on-disk edit."""
    spec.setdefault("workers_spawned", 0)
    if type(spec["workers_spawned"]) is not int or spec["workers_spawned"] < 0:
        spec["workers_spawned"] = 0
    counts = spec.get("request_counts")
    spec["request_counts"] = {k: (counts or {}).get(k, 0) if isinstance(counts, dict) else 0
                              for k in ("green", "red", "unverified", "usage-error", "refused", "duplicate")}
    for key in ("resumes", "questions"):  # D54 counters
        if type(spec.get(key)) is not int or spec[key] < 0:
            spec[key] = 0
    if not isinstance(spec.get("resume_of"), dict):
        spec["resume_of"] = {}
    spec["broker"] = {"pid": os.getpid(), "started_at": _now(), "status": "serving", "transport": transport,
                      "poll_interval": poll_interval, "idle_timeout": idle_timeout}


def serve(run_dir: str | Path, poll_interval: float = 1.0, idle_timeout: float = 600.0,
          home_repo: str | None = None, sleep=time.sleep, clock=time.monotonic) -> int:
    """Broker loop. Exit 0 on lead.done or idle timeout, 1 on fatal I/O, 2 on bad arguments or run.json."""
    if poll_interval <= 0 or idle_timeout <= 0:
        print("dispatch --serve: --poll-interval and --idle-timeout must be positive", file=sys.stderr)
        return BROKER_USAGE
    root = Path(run_dir)
    if root.is_symlink() or not root.is_dir():
        print(f"dispatch --serve: run directory missing: {run_dir}", file=sys.stderr)
        return BROKER_USAGE
    root = root.resolve()
    inbox = root / INBOX
    if inbox.is_symlink() or not inbox.is_dir():
        print(f"dispatch --serve: {inbox} must be a real directory (the Lead's only write grant)", file=sys.stderr)
        return BROKER_USAGE
    lock_fd, refusal = _take_broker_lock(root)
    if lock_fd is None:
        print(f"dispatch --serve: {refusal}", file=sys.stderr)
        return BROKER_USAGE
    try:
        return _serve_locked(root, inbox, poll_interval, idle_timeout, home_repo, sleep, clock)
    finally:
        os.close(lock_fd)  # the flock goes with the descriptor; the file stays


def _take_broker_lock(root: Path) -> tuple[int | None, str]:
    """Take the exclusive flock on <run-dir>/broker.lock. Return (fd, "") or (None, refusal text)."""
    path = root / BROKER_LOCK
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        return None, f"{path} must be a regular file ({exc.strerror})"
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raw = os.pread(fd, 32, 0).decode("ascii", "replace").strip()
            os.close(fd)
            return None, f"another broker holds {path} (pid {raw if raw.isdigit() else 'unknown'})"
        os.ftruncate(fd, 0)
        os.pwrite(fd, str(os.getpid()).encode(), 0)
    except OSError:
        os.close(fd)
        return None, f"{path} must be a regular file"
    return fd, ""


def _serve_locked(root: Path, inbox: Path, poll_interval: float, idle_timeout: float, home_repo: str | None,
                  sleep, clock) -> int:
    try:
        spec = _load_run_manifest(root)
    except (OSError, ValueError) as exc:
        print(f"dispatch --serve: invalid run.json: {exc}", file=sys.stderr)
        return BROKER_USAGE
    init_broker_state(spec, poll_interval, idle_timeout)
    seen: set = set()
    issued: set = set()
    turn = None

    def save():
        with _SPEC_LOCK:
            _atomic_write_json(root / "run.json", spec, overwrite=True)
    try:
        save()
        last = clock()
        while True:
            if turn is not None and not turn.alive():
                turn.thread.join()
                if turn.error is not None:
                    raise turn.error if isinstance(turn.error, (OSError, BrokerFatal)) else BrokerFatal(str(turn.error))
                turn = None
                save()
                last = clock()
            if turn is not None:  # a Worker is running: relay its question, never stop the broker under it
                with contextlib.suppress(ValueError):
                    if relay_question(root, spec, turn.rid) is not None:
                        save()
                last = clock()
            names = sorted(n for n in os.listdir(str(inbox)) if REQUEST_FILE_RE.match(n))
            progressed = False
            for name in names:
                got = _handle_one(root, name, spec, seen, home_repo, issued, busy=turn is not None)
                if got == "busy":
                    continue
                progressed = True
                if isinstance(got, Turn):
                    turn = got.start()
                save()
                last = clock()
            if progressed:
                continue
            if turn is not None:
                turn.thread.join(poll_interval)  # wakes early when the turn ends
                continue
            if os.path.lexists(str(inbox / LEAD_DONE)):
                stop = "lead-done"
                break
            if clock() - last >= idle_timeout:
                stop = "idle-timeout"
                break
            sleep(poll_interval)
        spec["broker"].update(status="stopped", stop=stop, stopped_at=_now())
        _atomic_write_json(root / "run.json", spec, overwrite=True)
    except (OSError, BrokerFatal) as exc:
        print(f"dispatch --serve: fatal: {exc}", file=sys.stderr)
        return BROKER_FATAL
    return BROKER_OK


def wait(run_dir: str | Path, request_id: str, timeout: float = 600.0, sleep=time.sleep,
         clock=time.monotonic) -> int:
    """Lead waiter: poll once per second for <run-dir>/<id>.result.json.
    Exit 0 and print the path when found, 10 and print the needs-lead JSON when the Worker asked a question the
    Lead has not answered (D54), 124 on timeout, 2 on a bad request id or non-positive timeout."""
    if not isinstance(request_id, str) or not REQUEST_ID_RE.match(request_id) or timeout <= 0:
        print("dispatch --wait: bad request id or timeout", file=sys.stderr)
        return BROKER_USAGE
    path = Path(run_dir) / f"{request_id}.result.json"
    start = clock()
    while True:
        if path.is_file():
            print(path)
            return 0
        asked = pending_question(Path(run_dir), request_id)
        if asked is not None:
            print(json.dumps(asked))
            return NEEDS_LEAD_EXIT
        if clock() - start >= timeout:
            print(f"dispatch --wait: no result for {request_id} after {timeout:g} s", file=sys.stderr)
            return 124
        sleep(1)
