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


def notice(state: Path, env: dict | None = None, **kw) -> str:
    """One line when PyPI has a newer release, else ""."""
    env = os.environ if env is None else env
    if env.get(OPT_OUT, "").strip() not in ("", "0"):
        return ""
    from .. import __version__
    latest = latest_version(state, **kw)
    if not latest or not newer(latest, __version__):
        return ""
    return (f"agents-inc {latest} is available (installed {__version__}). Update: "
            f"`pip install -U agents-inc && agents-inc repair` (from a checkout: `git pull && agents-inc repair --source <checkout>`). "
            f"Changes: https://github.com/domattioli/agents-inc/blob/main/CHANGELOG.md")
