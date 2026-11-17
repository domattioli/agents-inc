"""Offline installer verification; live probing is deliberately opt-in."""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from . import catalog
from .. import datafiles
import time
from .bundle import stage_bundle, verify_bundle
from . import source_git
from .host_wiring import AT_ROUTE, wiring_problems
from .paths import InstallPaths
from .receipt import InstallReceipt
from .runtime import MODEL_ALIASES, build_codex_argv, is_temp_or_shim_path

PROBE_TIMEOUT = 2.0

@dataclass(frozen=True)
class DoctorItem:
    """Spec 042 FR-017: one doctor item. tested: now | record (read from a stored file, `age` seconds old) | not-tested.
    result: pass | fail | could-not-test | warn."""
    name: str
    required: bool
    tested: str
    result: str
    detail: str = ""
    age: float | None = None
    def as_dict(self): return {"name": self.name, "required": self.required, "tested": self.tested, "result": self.result,
                               "detail": self.detail, "age": self.age}

@dataclass(frozen=True)
class DoctorReport:
    ready: bool
    codes: tuple[str, ...]
    live: dict | None = None
    warnings: tuple[str, ...] = ()  # non-fatal; never affects `ready` or the CLI exit code
    items: tuple[DoctorItem, ...] = ()
    @property
    def untested(self) -> tuple[str, ...]:
        """Names of required items that were not tested now and passed."""
        return tuple(i.name for i in self.items if i.required and not (i.tested == "now" and i.result == "pass"))
    def as_dict(self): return {"ready": self.ready, "codes": list(self.codes), "live": self.live, "warnings": list(self.warnings),
                               "items": [i.as_dict() for i in self.items]}

def format_age(seconds: float) -> str:
    """FR-030: `age <n><unit>`, one unit (s, m, h, d), the largest whole unit."""
    n = max(0, int(seconds))
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if n >= size: return f"age {n // size}{unit}"
    return f"age {n}s"

def item_line(item: DoctorItem) -> str:
    """`<name>: <result> (<tested>)`; a stored value or an untested item says so (FR-017, FR-030)."""
    line = f"{item.name}: {item.result} ({item.tested})"
    if item.tested == "record":
        line += f" - not verified now, {format_age(item.age or 0)}"
    if item.detail: line += f" - {item.detail}"
    return line

def item_lines(report: DoctorReport) -> list[str]:
    return [item_line(i) for i in report.items]

def dispatch_path_probe(env=None, timeout: float = PROBE_TIMEOUT) -> bool:
    """Spec 042 FR-019: can this process reach the model provider? An HTTP CONNECT through HTTPS_PROXY when one is set,
    else a TCP connect to api.anthropic.com:443. No request is sent to the API, so no paid usage or quota."""
    from .dispatch import PROBE_HOST, api_reachable  # lazy: dispatch is heavy
    env = os.environ if env is None else env
    if env.get("HTTPS_PROXY") or env.get("https_proxy"): return api_reachable(env, timeout=timeout)
    try:
        with socket.create_connection((PROBE_HOST, 443), timeout=timeout): return True
    except OSError: return False

def _hook_drift(paths: InstallPaths) -> list[str]:
    """Warn when the installed at_route hook differs from the source checkout it came from."""
    installed = paths.current / AT_ROUTE
    try:
        if not installed.is_file(): return []  # release ships no hook: nothing to drift
        record = paths.state / "source-checkout"
        text = record.read_text().strip() if record.is_file() else None
        if text == "packaged": source = datafiles.repo_file(AT_ROUTE)  # pip install: compare with the packaged hook
        else: source = Path(text) / AT_ROUTE if text else None
        if source is None or not source.is_file(): return ["WB_HOOK_DRIFT_UNCHECKED"]
        return ["WB_HOOK_DRIFT"] if source.read_bytes() != installed.read_bytes() else []
    except OSError: return ["WB_HOOK_DRIFT_UNCHECKED"]

def _model_drift(models: list[dict] | None) -> list[str]:
    """D52: one warning per Codex alias whose pinned slug has a newer catalog slug."""
    out = []
    for alias, slug in MODEL_ALIASES.items():
        newer = catalog.drift(slug, models)
        if newer: out.append(f"MODEL_DRIFT {alias}: pinned {slug}, newest {newer}")
    return out

def _install_stale(paths: InstallPaths, release_hash: str) -> list[str]:
    """D52: warn when the checkout recorded at install time would now stage to a different release hash."""
    return ["INSTALL_STALE"] if _stale_checkout(paths, release_hash) else []

def _stale_checkout(paths: InstallPaths, release_hash: str) -> Path | None:
    return _stale_basis(paths, release_hash)[0]

def _stale_basis(paths: InstallPaths, release_hash: str) -> tuple[Path | None, str]:
    """(source or None, basis): basis is `record` when the answer came from the stored source-git.json (D82), `measured` when
    the checkout was staged and compared now, `unknown` when no comparison could be made. The recorded source checkout when it would now stage to a different release hash, else None. Staging goes to
    a temp dir so nothing is written under ~/.local; any failure (no record, packaged install, unreadable) is None.
    #174: while the active release is a clean git install, stale means HEAD's bundle paths differ from the installed
    commit; work in progress is not stale. A record for another release, or a missing commit, uses the digest compare."""
    record = paths.state / "source-checkout"
    try:
        if not record.is_file(): return None, "unknown"
        source = Path(record.read_text().strip())
        git = source_git.load_record(paths.state)
        if git is not None and git["clean"] and git["release"] == release_hash and source_git.is_git_checkout(source):
            try: changed = source_git.bundle_changed_since(source, git["head"])
            except RuntimeError: return None, "unknown"  # git cannot run or read HEAD
            if changed is not None: return (source if changed else None), "record"
        tmp = Path(tempfile.mkdtemp(prefix="agents-inc-stale-"))
        try:
            digest = stage_bundle(source, replace(paths, releases=tmp / "releases")).digest
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    except (OSError, ValueError, RuntimeError): return None, "unknown"
    return (source if digest != release_hash else None), "measured"

def install_match_item(paths: InstallPaths, release_hash: str) -> DoctorItem:
    """FR-021: does the installed copy match its source, and was that measured now or read from the stored record."""
    source, basis = _stale_basis(paths, release_hash)
    if basis == "unknown": return DoctorItem("install-match", False, "not-tested", "could-not-test", "no comparable source checkout")
    if basis == "record":
        try: age = max(0.0, time.time() - (paths.state / source_git.RECORD).stat().st_mtime)
        except OSError: age = None
        detail = "compared HEAD with the commit stored at install (D82)" if source is None else f"HEAD differs from the commit stored at install ({source})"
        return DoctorItem("install-match", False, "record", "warn" if source else "pass", detail, age)
    return DoctorItem("install-match", False, "now", "warn" if source else "pass", f"installed bundle differs from {source}" if source else "")

def source_uncommitted(paths: InstallPaths) -> Path | None:
    """FR-021a: the source checkout when it has uncommitted edits under the installed paths, else None. Read-only git."""
    try:
        record = paths.state / "source-checkout"
        if not record.is_file(): return None
        source = Path(record.read_text().strip())
        if not source_git.is_git_checkout(source): return None
        state = source_git.source_state(source)
    except (OSError, ValueError, RuntimeError): return None
    return source if state is not None and not state["clean"] else None

def stale_refusal(paths: InstallPaths) -> str:
    """Operator rule 2026-11-11: a stale install stops dispatch. One-line refusal naming the repair command, or ""
    when there is no receipt (source-checkout run) or the install matches its checkout."""
    try: receipt = InstallReceipt.load(paths.receipt)
    except (OSError, ValueError): return ""
    release_hash = getattr(receipt, "release_hash", None)
    if not isinstance(release_hash, str): return ""  # a stub receipt (tests) has no hash to compare
    source, basis = _stale_basis(paths, release_hash)
    if source is None: return ""
    if basis == "record":  # D86: a stored answer says so and how old it is
        try: age = format_age(max(0.0, time.time() - (paths.state / source_git.RECORD).stat().st_mtime))
        except OSError: age = "age unknown"
        how = f"record stored at install, not measured now, {age}"
    else:
        how = "measured now"
    return (f"agents-inc dispatch refused: INSTALL_STALE (installed bundle differs from {source}; {how}). "
            f"Run: agents-inc repair --source {source}")

def _sandbox_exclusion(paths: InstallPaths) -> list[str]:
    """#100: a Claude Code session that sandboxes Bash cannot start a dispatch (#94) until `agents-inc dispatch *` (or the legacy `agents-inc *`) sits in
    `sandbox.excludedCommands` of ~/.claude/settings.json. Warn only when that settings file exists."""
    settings = paths.home / ".claude/settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, ValueError): return []
    sandbox = data.get("sandbox") if isinstance(data, dict) else None
    excluded = sandbox.get("excludedCommands", []) if isinstance(sandbox, dict) else []
    out = []
    if not any(e in ("agents-inc *", "agents-inc dispatch *") for e in excluded if isinstance(e, str)):
        out.append("WB_SANDBOX_EXCLUDE_MISSING")  # the narrow `agents-inc dispatch *` or the legacy `agents-inc *`
    network = sandbox.get("network") if isinstance(sandbox, dict) else None
    domains = network.get("allowedDomains", []) if isinstance(network, dict) else []
    if not isinstance(domains, list) or "api.anthropic.com" not in domains: out.append("WB_SANDBOX_API_DOMAIN_MISSING")
    return out

def _mod_missing(release: Path, home: Path, runner, which) -> list[str]:
    """Spec 027: the release ships the live-view mod but Claude Code does not list it. Warning only; READY stays."""
    if not (release / "mods/agents-inc/.claude-plugin/plugin.json").is_file(): return []
    claude = which("claude")
    if not claude: return []
    try: listed = runner([claude, "plugin", "list"], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL, check=False,
                            env=dict(os.environ, HOME=str(home)))  # the install's home, never the caller's
    except (OSError, subprocess.SubprocessError): return []
    if listed.returncode != 0: return []
    if "agents-inc@agents-inc-local" not in (listed.stdout or ""): return ["MOD_NOT_INSTALLED"]
    return mod_version_warnings(listed.stdout or "")


def installed_mod_version(plugin_list: str, plugin: str = "agents-inc@agents-inc-local") -> str | None:
    """The `Version:` line of plugin's block in `claude plugin list` output, or None when it has none."""
    block = False
    for line in plugin_list.splitlines():
        text = line.strip().lstrip("❯").strip()
        if "@" in text and ":" not in text:  # a plugin header line, `name@marketplace`
            block = text == plugin
        elif block and text.startswith("Version:"):
            return text.split(":", 1)[1].strip() or None
    return None


def mod_version_warnings(plugin_list: str) -> list[str]:
    """Spec 038 FR-018: the mod is versioned with the package. The version Claude Code lists for the installed mod must
    equal this package's __version__ (the shipped plugin.json carries the same number). Warning only."""
    from .. import __version__
    installed = installed_mod_version(plugin_list)
    if installed is None or installed == __version__: return []
    return [f"MOD_VERSION_MISMATCH: installed mod {installed}, package {__version__}; run agents-inc repair"]

def _mcp_user_scope(home: Path, runner, which) -> list[str]:
    """Spec 031 FR-015: the plugin ships delegate-agent now; a user-scope entry from the old install.sh doubles it.
    A plugin server is listed as `plugin:agents-inc:delegate-agent:`, a user one as `delegate-agent:`. Warning only."""
    claude = which("claude")
    if not claude: return []
    try: listed = runner([claude, "mcp", "list"], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL, check=False,
                            env=dict(os.environ, HOME=str(home)))
    except (OSError, subprocess.SubprocessError): return []
    if listed.returncode != 0: return []
    if any(ln.strip().startswith("delegate-agent:") for ln in (listed.stdout or "").splitlines()):
        return ["MCP_USER_SCOPE_DUPLICATE: remove the old user-scope entry with `claude mcp remove --scope user delegate-agent`"]
    return []

def _luna_report(release: Path, paths: InstallPaths) -> dict | None:
    """Spec 028: the native agents-inc:luna type's status, only when the release ships the mod. Any failure is silent."""
    if not (release / "mods/agents-inc/hooks/luna.ts").is_file(): return None
    try:
        from . import luna_native
        return luna_native.status(paths)
    except (OSError, ValueError, KeyError): return None

def _luna_warnings(release: Path, paths: InstallPaths) -> list[str]:
    """LUNA_OFF, LUNA_CODEX_NOT_READY, LUNA_CATALOG_MISSING: warnings only; READY and the failure codes stay as they are."""
    report = _luna_report(release, paths)
    if report is None: return []
    from . import luna_native
    code = luna_native.doctor_code(report)
    return [code] if code else []

def luna_line(paths: InstallPaths) -> str | None:
    """The `luna type:` line `agents-inc doctor` prints, or None when no installed release ships the mod."""
    report = _luna_report(paths.current, paths)
    if report is None: return None
    from . import luna_native
    return luna_native.doctor_line(report)

def check_install(paths: InstallPaths, live_model: str | None = None, runner=subprocess.run,
                  models: list[dict] | None = None, catalog_path: Path | None = None,
                  which=None, sandbox_probe=None, net_probe=None) -> DoctorReport:
    from .dispatch import WORKER_PATH, sandbox_available, worker_env  # lazy: dispatch is heavy and optional here
    sandbox_probe = sandbox_probe or sandbox_available
    net_probe = net_probe or dispatch_path_probe
    which = which or shutil.which  # resolved per call so a patched shutil.which applies
    codes = []; warnings = []
    try: receipt = InstallReceipt.load(paths.receipt)
    except (OSError, ValueError):
        # #35: say why. No receipt at all is "not installed", not an untrusted release.
        if not paths.receipt.exists(): return DoctorReport(False, ("WB_NOT_INSTALLED",), items=(DoctorItem("install", True, "now", "fail", "no install receipt"),))
        return DoctorReport(False, ("WB_RELEASE_UNTRUSTED",), items=(DoctorItem("install", True, "now", "fail", "receipt unreadable"),))
    release = paths.releases / receipt.release_hash
    if not verify_bundle(release): codes.append("WB_RELEASE_UNTRUSTED")
    if not paths.current.is_symlink() or paths.current.resolve() != release.resolve(): codes.append("WB_RELEASE_UNTRUSTED")
    items = [DoctorItem("install", True, "now", "fail" if "WB_RELEASE_UNTRUSTED" in codes else "pass")]
    if receipt.codex_path is None: warnings.append("WB_CLI_NOT_FOUND")  # installed without codex: warning only
    elif not receipt.codex_path.is_file() or not os.access(receipt.codex_path, os.X_OK): codes.append("WB_CLI_NOT_FOUND")
    elif is_temp_or_shim_path(receipt.codex_path): warnings.append("WB_CLI_TEMP_PATH")
    items.append(DoctorItem("codex-cli", receipt.codex_path is not None, "now", "fail" if "WB_CLI_NOT_FOUND" in codes else ("pass" if receipt.codex_path else "warn"),
                            "" if receipt.codex_path else "installed without codex"))
    skills_before = len(codes)
    for root in (paths.claude_skills, paths.codex_skills):
        for name in ("workerbee", "codex-bridge"):
            if not (root / name).is_symlink(): codes.append("WB_SKILL_MISSING")
    items.append(DoctorItem("skills", True, "now", "fail" if len(codes) > skills_before else "pass"))
    # Skills load lazily; without the always-on block and hooks no session learns to delegate.
    if wiring_problems(paths): codes.append("WB_HOST_UNWIRED")
    items.append(DoctorItem("host-wiring", True, "now", "fail" if "WB_HOST_UNWIRED" in codes else "pass"))
    # Claude is the required provider: a Worker launch needs the CLI on the same PATH worker_env gives it.
    claude_found = which("claude", path=WORKER_PATH + os.pathsep + os.environ.get("PATH", "")) is not None
    if not claude_found: codes.append("WB_CLAUDE_NOT_FOUND")
    items.append(DoctorItem("claude-cli", True, "now", "pass" if claude_found else "fail"))
    if sys.platform == "darwin" and not sandbox_probe(): warnings.append("WB_SANDBOX_NESTED")  # inside another sandbox
    warnings.extend(_mod_missing(release, paths.home, runner, which))
    warnings.extend(_mcp_user_scope(paths.home, runner, which))
    warnings.extend(_luna_warnings(release, paths))
    warnings.extend(_hook_drift(paths))
    warnings.extend(_sandbox_exclusion(paths))
    if models is None:  # the catalog of the home being checked; CODEX_HOME still wins. [] stops a re-read of the default.
        default = catalog.cache_path({**os.environ, "HOME": str(paths.home)})
        models = catalog.load(catalog_path or default) or []
    warnings.extend(_model_drift(models))
    warnings.extend(_install_stale(paths, receipt.release_hash))
    match = install_match_item(paths, receipt.release_hash)
    items.append(match)
    if match.result == "warn" and "INSTALL_STALE" not in warnings: warnings.append("INSTALL_STALE")
    if source_uncommitted(paths): warnings.append("WB_SOURCE_UNCOMMITTED")  # FR-021a: never changes READY; D82 stays
    repair_failed = paths.state.joinpath("repair-failed.json").exists()
    if repair_failed: codes.append("WB_REPAIR_FAILED")  # before the live probe: no model ping after a failed repair
    items.append(DoctorItem("repair", True, "now", "fail" if repair_failed else "pass", "an earlier repair did not finish" if repair_failed else ""))
    # FR-019: reachability of the model provider; no model call, no quota. Needs the claude CLI first.
    if not claude_found: items.append(DoctorItem("dispatch-path", True, "not-tested", "could-not-test", "claude CLI not found"))
    elif net_probe(): items.append(DoctorItem("dispatch-path", True, "now", "pass", "api.anthropic.com:443 reachable (no model call)"))
    else: items.append(DoctorItem("dispatch-path", True, "not-tested", "could-not-test",
                                  "api.anthropic.com:443 not reachable from here; check with `agents-inc doctor` from a normal terminal"))
    live = None
    if live_model and not codes and receipt.codex_path is not None:
        models = json.loads((release / "agents_inc/models.json").read_text()).get("models", {})
        efforts = {slug: row["supported_efforts"] for slug, row in models.items() if row.get("provider") == "codex" and "supported_efforts" in row}
        argv = build_codex_argv(receipt.codex_path, live_model, "medium", Path.cwd(), efforts)
        completed = runner(argv, input="Reply PONG", text=True, capture_output=True, env=worker_env(str(receipt.codex_path)), check=False)
        output = (completed.stdout or "") + (completed.stderr or "")
        code = "READY" if completed.returncode == 0 and "PONG" in output else ("WB_AUTH_REQUIRED" if "auth" in output.lower() or "login" in output.lower() else "WB_MODEL_UNAVAILABLE")
        live = {"code": code, "executable": str(receipt.codex_path), "isolated": True}
        if code != "READY": codes.append(code)
    report = DoctorReport(False, tuple(sorted(set(codes))), live, tuple(sorted(set(warnings))), tuple(items))
    return replace(report, ready=not codes and not report.untested)
