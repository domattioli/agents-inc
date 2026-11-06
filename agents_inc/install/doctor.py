"""Offline installer verification; live probing is deliberately opt-in."""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from . import catalog
from .. import datafiles
from .bundle import stage_bundle, verify_bundle
from .host_wiring import AT_ROUTE, wiring_problems
from .paths import InstallPaths
from .receipt import InstallReceipt
from .runtime import MODEL_ALIASES, build_codex_argv, is_temp_or_shim_path

PROBE_HOSTS = ("api.anthropic.com", "api.github.com")
PROBE_HOST_TIMEOUT = 5  # per host, sequential in the child
PROBE_CHILD_TIMEOUT = 12  # 2 x PROBE_HOST_TIMEOUT plus start; with GH_TIMEOUT the worst case stays under 20 s (SC-005)
GH_TIMEOUT = 6

@dataclass(frozen=True)
class DoctorReport:
    ready: bool
    codes: tuple[str, ...]
    live: dict | None = None
    warnings: tuple[str, ...] = ()  # non-fatal; never affects `ready` or the CLI exit code
    probe: dict | None = None  # --probe-dispatch: {host: {"status": reachable|blocked|cert, "elapsed", "fix"}}
    def as_dict(self):
        out = {"ready": self.ready, "codes": list(self.codes), "live": self.live, "warnings": list(self.warnings)}
        if self.probe is not None: out["probe"] = self.probe  # keyed only when asked, so the plain --json shape stays pinned
        return out

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
    """D52: warn when the checkout recorded at install time would now stage to a different release hash.
    Staging goes to a temp dir so nothing is written under ~/.local; any failure is silent."""
    record = paths.state / "source-checkout"
    try:
        if not record.is_file(): return []
        source = Path(record.read_text().strip())
        tmp = Path(tempfile.mkdtemp(prefix="agents-inc-stale-"))
        try:
            digest = stage_bundle(source, replace(paths, releases=tmp / "releases")).digest
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    except (OSError, ValueError, RuntimeError): return []
    return ["INSTALL_STALE"] if digest != release_hash else []

def _sandbox_exclusion(paths: InstallPaths) -> list[str]:
    """#100: a Claude Code session that sandboxes Bash cannot start a dispatch (#94) until `agents-inc *` sits in
    `sandbox.excludedCommands` of ~/.claude/settings.json. Warn only when that settings file exists."""
    settings = paths.home / ".claude/settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, ValueError): return []
    sandbox = data.get("sandbox") if isinstance(data, dict) else None
    excluded = sandbox.get("excludedCommands", []) if isinstance(sandbox, dict) else []
    if any(isinstance(e, str) and e.split()[:1] == ["agents-inc"] for e in excluded): return []
    return ["WB_SANDBOX_EXCLUDE_MISSING"]

def _mod_missing(release: Path, home: Path, runner, which) -> list[str]:
    """Spec 027: the release ships the live-view mod but Claude Code does not list it. Warning only; READY stays."""
    if not (release / "mods/agents-inc/.claude-plugin/plugin.json").is_file(): return []
    claude = which("claude")
    if not claude: return []
    try: listed = runner([claude, "plugin", "list"], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL, check=False,
                            env=dict(os.environ, HOME=str(home)))  # the install's home, never the caller's
    except (OSError, subprocess.SubprocessError): return []
    if listed.returncode != 0: return []
    return [] if "agents-inc@agents-inc-local" in (listed.stdout or "") else ["MOD_NOT_INSTALLED"]

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

def _probe_dispatch(runner, which) -> dict:
    """Spec 029: a child with the Worker env tries both hosts; `gh` runs in the caller env (#122). Fails closed to blocked."""
    from .dispatch import worker_env  # lazy, like check_install
    argv = [sys.executable, str(Path(__file__).with_name("netprobe.py")), *PROBE_HOSTS]
    try: out = runner(argv, env=worker_env(sys.executable), capture_output=True, text=True, timeout=PROBE_CHILD_TIMEOUT,
                      stdin=subprocess.DEVNULL, check=False).stdout
    except subprocess.TimeoutExpired as exc: out = exc.stdout  # rows the child flushed before the kill
    except OSError: out = ""
    if isinstance(out, bytes): out = out.decode("utf-8", "replace")
    rows = {}
    for line in (out or "").splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        if isinstance(row, dict) and row.get("host") in PROBE_HOSTS and row.get("status") in ("reachable", "blocked", "cert"): rows[row["host"]] = row
    probe = {h: {"status": rows[h]["status"], "elapsed": rows[h].get("elapsed", PROBE_CHILD_TIMEOUT), "fix": None} if h in rows
             else {"status": "blocked", "elapsed": PROBE_CHILD_TIMEOUT, "fix": None} for h in PROBE_HOSTS}
    gh = which("gh")
    if gh:
        try: done = runner([gh, "api", "/zen"], capture_output=True, text=True, timeout=GH_TIMEOUT, stdin=subprocess.DEVNULL, check=False)
        except (OSError, subprocess.SubprocessError): done = None
        if done is not None and re.search(r"x509|certificate", done.stderr or "", re.I): probe["api.github.com"]["status"] = "cert"
    return probe

def _probe_codes(probe: dict, warnings, env=os.environ) -> tuple[list[str], list[str]]:
    """FR-007, FR-012: model host blocked/cert -> blocking code; GitHub blocked/cert -> warning. Sets each row's `fix`."""
    from .dispatch import SANDBOX_FIX  # lazy, like check_install
    codes, warns = [], []
    model, github = probe["api.anthropic.com"], probe["api.github.com"]
    if model["status"] == "blocked":
        codes.append("WB_DISPATCH_API_BLOCKED")
        sandboxed = env.get("SANDBOX_RUNTIME") or "WB_SANDBOX_EXCLUDE_MISSING" in warnings
        model["fix"] = "dispatch child cannot reach api.anthropic.com; " + SANDBOX_FIX if sandboxed else "dispatch child cannot reach api.anthropic.com:443; check firewall/proxy"
    elif model["status"] == "cert":
        codes.append("WB_DISPATCH_API_CERT")
        model["fix"] = "dispatch child TLS verify failed for api.anthropic.com (proxy/MITM CA?); see D70"
    if github["status"] == "blocked":
        warns.append("WB_GITHUB_BLOCKED"); github["fix"] = "allow api.github.com or use the GitHub MCP tools"
    elif github["status"] == "cert":
        warns.append("WB_GITHUB_CERT"); github["fix"] = "gh TLS fails in sandbox (#122); use the GitHub MCP tools or run gh outside the sandbox"
    return codes, warns

def check_install(paths: InstallPaths, live_model: str | None = None, runner=subprocess.run,
                  models: list[dict] | None = None, catalog_path: Path | None = None,
                  which=shutil.which, sandbox_probe=None, probe_dispatch: bool = False) -> DoctorReport:
    from .dispatch import WORKER_PATH, sandbox_available, worker_env  # lazy: dispatch is heavy and optional here
    sandbox_probe = sandbox_probe or sandbox_available
    codes = []; warnings = []
    try: receipt = InstallReceipt.load(paths.receipt)
    except (OSError, ValueError):
        # #35: say why. No receipt at all is "not installed", not an untrusted release.
        if not paths.receipt.exists(): return DoctorReport(False, ("WB_NOT_INSTALLED",))
        return DoctorReport(False, ("WB_RELEASE_UNTRUSTED",))
    release = paths.releases / receipt.release_hash
    if not verify_bundle(release): codes.append("WB_RELEASE_UNTRUSTED")
    if not paths.current.is_symlink() or paths.current.resolve() != release.resolve(): codes.append("WB_RELEASE_UNTRUSTED")
    if receipt.codex_path is None: warnings.append("WB_CLI_NOT_FOUND")  # installed without codex: warning only
    elif not receipt.codex_path.is_file() or not os.access(receipt.codex_path, os.X_OK): codes.append("WB_CLI_NOT_FOUND")
    elif is_temp_or_shim_path(receipt.codex_path): warnings.append("WB_CLI_TEMP_PATH")
    for root in (paths.claude_skills, paths.codex_skills):
        for name in ("workerbee", "codex-bridge"):
            if not (root / name).is_symlink(): codes.append("WB_SKILL_MISSING")
    # Skills load lazily; without the always-on block and hooks no session learns to delegate.
    if wiring_problems(paths): codes.append("WB_HOST_UNWIRED")
    # Claude is the required provider: a Worker launch needs the CLI on the same PATH worker_env gives it.
    if which("claude", path=WORKER_PATH + os.pathsep + os.environ.get("PATH", "")) is None: codes.append("WB_CLAUDE_NOT_FOUND")
    if sys.platform == "darwin" and not sandbox_probe(): warnings.append("WB_SANDBOX_NESTED")  # inside another sandbox
    warnings.extend(_mod_missing(release, paths.home, runner, which))
    warnings.extend(_luna_warnings(release, paths))
    warnings.extend(_hook_drift(paths))
    warnings.extend(_sandbox_exclusion(paths))
    if models is None:  # the catalog of the home being checked; CODEX_HOME still wins. [] stops a re-read of the default.
        default = catalog.cache_path({**os.environ, "HOME": str(paths.home)})
        models = catalog.load(catalog_path or default) or []
    warnings.extend(_model_drift(models))
    warnings.extend(_install_stale(paths, receipt.release_hash))
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
    probe = None
    if probe_dispatch:  # opt-in: plain doctor makes no new network call
        probe = _probe_dispatch(runner, which)
        c, w = _probe_codes(probe, warnings)
        codes += c; warnings += w
    return DoctorReport(not codes, tuple(sorted(set(codes))), live, tuple(sorted(set(warnings))), probe)
