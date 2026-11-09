"""Tell consumers when a newer agents-inc is on PyPI.

One HTTPS GET to pypi.org at most once a day, 2 s timeout, result cached in the state dir. Never raises:
a failed check means no notice. Opt out with AGENTS_INC_NO_UPDATE_CHECK=1."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from pathlib import Path

URL = "https://pypi.org/pypi/agents-inc/json"
TTL_S = 86400
OPT_OUT = "AGENTS_INC_NO_UPDATE_CHECK"


def _key(version: str) -> tuple:
    """Release tuple; a pre-release (any letter part) sorts below the release."""
    m = re.match(r"^(\d+(?:\.\d+)*)(.*)$", version.strip())
    if not m:
        return ()
    return tuple(int(x) for x in m.group(1).split(".")) + ((1,) if not m.group(2) else (0,))


def newer(latest: str, current: str) -> bool:
    a, b = _key(latest), _key(current)
    return bool(a and b) and a > b


def _fetch(timeout: float) -> str | None:
    req = urllib.request.Request(URL, headers={"Accept": "application/json", "User-Agent": "agents-inc-update-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        return str(json.load(resp)["info"]["version"])


def latest_version(state: Path, now: float | None = None, fetch=_fetch, timeout: float = 2.0) -> str | None:
    now = time.time() if now is None else now
    cache = Path(state) / "update-check.json"
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if now - float(data["checked"]) < TTL_S:
            return data.get("latest")
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        latest = fetch(timeout)
    except Exception:  # offline, DNS, HTTP error, bad JSON: no notice
        latest = None
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"checked": now, "latest": latest}) + "\n", encoding="utf-8")
    except OSError:
        pass
    return latest


def install_kind(state: Path, launcher: Path | None = None, stdlib: Path | None = None) -> tuple[str, str]:
    """(kind, detail) from local reads only: the source-checkout record, then the launcher console script's
    interpreter line. kind is checkout, pipx, pip-venv, pip-user or unknown; detail is the checkout path."""
    try:
        rec = (Path(state) / "source-checkout").read_text(encoding="utf-8").strip()
    except OSError:
        rec = ""
    if rec and rec != "packaged":
        return "checkout", rec
    launcher = Path.home() / ".local/bin/agents-inc" if launcher is None else Path(launcher)
    try:
        if launcher.is_symlink() or not launcher.is_file():
            return "unknown", ""
        first = launcher.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return "unknown", ""
    if not first.startswith("#!"):
        return "unknown", ""
    interp = first[2:].strip().split()[0] if first[2:].strip() else ""
    if "/pipx/venvs/" in interp:
        return "pipx", ""
    if interp and (Path(interp).parent.parent / "pyvenv.cfg").is_file():
        return "pip-venv", ""
    if interp:
        return "pip-user", ""
    return "unknown", ""


def _externally_managed(stdlib: Path | None) -> bool:
    try:
        import sysconfig
        base = Path(sysconfig.get_path("stdlib")) if stdlib is None else Path(stdlib)
        return (base / "EXTERNALLY-MANAGED").is_file()
    except Exception:
        return False


def update_command(kind: str, detail: str = "", managed: bool = False) -> str:
    if kind == "checkout":
        return f"`git -C {detail} pull && agents-inc repair --source {detail}`"
    if kind == "pipx":
        return "`pipx upgrade agents-inc && agents-inc repair`"
    if kind == "pip-venv":
        return "`python3 -m pip install -U agents-inc && agents-inc repair`"
    if kind == "pip-user" and not managed:
        return "`python3 -m pip install --user -U agents-inc && agents-inc repair`"
    if kind == "pip-user":
        return ("this Python is externally managed (PEP 668), so pip refuses; reinstall with "
                "`pipx install --force agents-inc && agents-inc repair`")
    return ("pipx: `pipx upgrade agents-inc && agents-inc repair`; checkout: "
            "`git -C <checkout> pull && agents-inc repair --source <checkout>`. "
            "A bare pip install fails on a Python that is externally managed (PEP 668)")


def notice(state: Path, env: dict | None = None, launcher: Path | None = None, stdlib: Path | None = None, **kw) -> str:
    """One line when PyPI has a newer release, else ""."""
    env = os.environ if env is None else env
    if env.get(OPT_OUT, "").strip() not in ("", "0"):
        return ""
    from .. import __version__
    latest = latest_version(state, **kw)
    if not latest or not newer(latest, __version__):
        return ""
    kind, detail = install_kind(state, launcher, stdlib)
    cmd = update_command(kind, detail, _externally_managed(stdlib))
    return (f"agents-inc {latest} is available (installed {__version__}). Update: {cmd}. "
            f"Changes: https://github.com/domattioli/agents-inc/blob/main/CHANGELOG.md")
