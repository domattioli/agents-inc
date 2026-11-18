"""Spec 047 (D52.1): installed vs latest host CLI versions (codex, claude).

`refresh` (doctor, repair) runs `--version` and, at most once per 24 h per package, asks the public npm registry for the
latest version; it records both in <state>/host-cli-versions.json. `cached` (session start) only reads that file: no
process, no socket. No lookup ever blocks or fails: offline gives latest None (could-not-check)."""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

TIMEOUT = 3
TTL = 24 * 3600
RECORD = "host-cli-versions.json"
USER_AGENT = "agents-inc-doctor"
# name -> (npm package, brew name)
CLIS = {"codex": ("@openai/codex", "codex"), "claude": ("@anthropic-ai/claude-code", "claude-code")}
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def _vkey(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def opted_out(env=None) -> bool:
    """D52.1 opt-out, one rule for doctor, repair and the registry fetch: AGENTS_INC_NO_UPDATE_CHECK set to any
    non-empty value other than "0" means no `--version` process and no registry request; only the record is read."""
    env = os.environ if env is None else env
    return (env.get("AGENTS_INC_NO_UPDATE_CHECK") or "").strip() not in ("", "0")


def probe(name: str, path: str | None = None, run=subprocess.run, exe: str | None = None) -> tuple[bool, str | None, str]:
    """(found on PATH, version or None, reason when the version could not be read). `exe`: the already resolved
    executable, so the version and the recorded identity come from the same file (L1)."""
    exe = exe or shutil.which(name, path=path)
    if exe is None:
        return False, None, "not on PATH"
    try:
        out = run([exe, "--version"], capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return True, None, f"`{name} --version` timed out after {TIMEOUT}s"
    except (OSError, subprocess.SubprocessError) as exc:
        return True, None, f"`{name} --version` failed: {exc}"
    match = VERSION_RE.search((out.stdout or "") + " " + (out.stderr or ""))
    return (True, match.group(0), "") if match else (True, None, f"`{name} --version` printed no version")


def installed_version(name: str, path: str | None = None, run=subprocess.run) -> str | None:
    return probe(name, path=path, run=run)[1]


def install_method(name: str, pkg: str, path: str | None = None) -> str:
    """npm when the resolved binary sits in node_modules/<pkg>; brew when in a Cellar or Caskroom; else unknown.
    A path under the Homebrew prefix alone is not proof of brew (npm-global installs live there too)."""
    exe = shutil.which(name, path=path)
    if exe is None:
        return "unknown"
    target = os.path.realpath(exe)
    if f"node_modules/{pkg}/" in target:
        return "npm"
    if "/Cellar/" in target or "/Caskroom/" in target:
        return "brew"
    return "unknown"


def update_command(method: str, pkg: str, brew_name: str) -> str:
    npm, brew = f"npm install -g {pkg}@latest", f"brew upgrade {brew_name}"
    if method == "npm": return npm
    if method == "brew": return brew
    return f"{npm} or {brew} (install method unknown)"


def registry_request(pkg: str) -> urllib.request.Request:
    """Unauthenticated GET; only a generic client name and Accept. Scoped names encode `/` as %2F."""
    url = "https://registry.npmjs.org/" + pkg.replace("/", "%2F") + "/latest"
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})


def _fetch(pkg: str) -> str | None:
    if opted_out():
        return None
    with urllib.request.urlopen(registry_request(pkg), timeout=TIMEOUT) as resp:
        value = json.loads(resp.read().decode("utf-8")).get("version")
    return value if isinstance(value, str) else None


def lookup(pkg: str, fetch=_fetch) -> tuple[str | None, str]:
    """(latest version or None, reason when None). Never raises."""
    try:
        value = fetch(pkg)
    except Exception as exc:  # offline, timeout, proxy refusal, bad JSON: could-not-check
        return None, f"registry lookup failed: {exc}"
    if isinstance(value, str) and VERSION_RE.fullmatch(value):
        return value, ""
    return None, "registry answer had no version"


def latest_version(pkg: str, fetch=_fetch) -> str | None:
    return lookup(pkg, fetch)[0]


def _read(state: Path) -> dict:
    try:
        data = json.loads((Path(state) / RECORD).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _fresh(rec, now: float) -> bool:
    return isinstance(rec, dict) and isinstance(rec.get("checked_at"), (int, float)) and now - rec["checked_at"] < TTL


def refresh(state: Path, now: float, fetch=_fetch, path: str | None = None, run=subprocess.run) -> dict:
    """Doctor and repair: current installed versions plus latest. A lookup, successful or failed, is reused for 24 h
    (D52.1), so an offline machine makes at most one request per package per day. A CLI on PATH whose version
    cannot be read is kept with `installed` None. Stored: installed, latest, checked_at, lookup_error. Returned also:
    probe_error, error (both reasons) and reused (the latest came from the record). Missing or read-only state dir: nothing written."""
    old = _read(state)
    out, due = {}, []
    for name, (pkg, _brew) in CLIS.items():
        exe = shutil.which(name, path=path)
        if exe is None:
            continue
        real = os.path.realpath(exe)
        found, inst, why = probe(name, run=run, exe=real)
        prev = old.get(name)
        if _fresh(prev, now):
            latest, checked, lookup_err, reused = prev.get("latest"), prev["checked_at"], prev.get("lookup_error") or "", True
        else:
            latest, lookup_err, checked, reused = None, "", now, False
            due.append(name)
        out[name] = {"installed": inst, "latest": latest, "checked_at": checked, "lookup_error": lookup_err,
                     "probe_error": why, "reused": reused, "binary": _stat_identity(real) if inst else None}
    for name, (latest, lookup_err) in _lookup_all({n: CLIS[n][0] for n in due}, fetch).items():
        out[name]["latest"], out[name]["lookup_error"] = latest, lookup_err
    for rec in out.values():
        rec["error"] = "; ".join(e for e in (rec["probe_error"], rec["lookup_error"]) if e)
    _write(state, {k: {f: v for f, v in rec.items() if f in ("installed", "latest", "checked_at", "lookup_error", "binary")}
                   for k, rec in out.items()})
    return out


def _write(state: Path, records: dict) -> None:
    """L2: unique temp file in the same directory, then os.replace. Just before replacing, re-read the current record
    and keep any per-CLI entry newer than the one about to be written, so an older run never overwrites a newer one.
    Missing or read-only state dir: nothing written."""
    import tempfile
    tmp = None
    try:
        Path(state).mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=RECORD + ".", suffix=".tmp", dir=str(state))
        merged = dict(records)
        for name, rec in _read(state).items():
            mine = merged.get(name)
            theirs_at = rec.get("checked_at") if isinstance(rec, dict) else None
            mine_at = mine.get("checked_at") if isinstance(mine, dict) else None
            if mine is None or (isinstance(theirs_at, (int, float)) and (not isinstance(mine_at, (int, float)) or theirs_at > mine_at)):
                merged[name] = rec
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(merged, indent=2) + "\n")
        os.replace(tmp, Path(state) / RECORD)
        tmp = None
    except OSError:
        pass
    finally:
        if tmp:
            try: os.remove(tmp)
            except OSError: pass


def _stat_identity(real: str) -> dict | None:
    try: st = os.stat(real)
    except OSError: return None
    return {"path": real, "mtime_ns": st.st_mtime_ns, "size": st.st_size, "inode": st.st_ino}


def _identity(name: str, path: str | None = None) -> dict | None:
    """The currently selected executable (shutil.which, then realpath; no process): path, mtime in ns, size, inode."""
    exe = shutil.which(name, path=path)
    return _stat_identity(os.path.realpath(exe)) if exe else None


def _lookup_all(pkgs: dict, fetch) -> dict:
    """K2: every due lookup at once, each in a daemon thread; stop waiting TIMEOUT seconds after the start, so the
    lookups add at most about TIMEOUT seconds to a run. A lookup still running then is `timeout`."""
    import threading, time as _time
    results, threads = {}, {}
    deadline = _time.monotonic() + TIMEOUT  # starts before the threads do
    for name, pkg in pkgs.items():
        def work(name=name, pkg=pkg): results[name] = lookup(pkg, fetch)
        threads[name] = threading.Thread(target=work, daemon=True)
        threads[name].start()
    for name, thread in threads.items():
        thread.join(max(0.0, deadline - _time.monotonic()))
    return {name: results.get(name, (None, f"registry lookup timeout after {TIMEOUT}s")) for name in pkgs}


def cached(state: Path, now: float, path: str | None = None) -> dict:
    """Session start: file read, shutil.which, realpath and os.stat only; no process, no socket. A record is trusted
    for `installed` at any age only while the currently selected executable has exactly the recorded identity (path,
    mtime_ns, size, inode); otherwise, or without an identity, it is marked `stale`. `latest` is kept only while the
    lookup is younger than 24 h."""
    out = {}
    for name, rec in _read(state).items():
        if name not in CLIS or not isinstance(rec, dict): continue
        rec = dict(rec)
        ident = rec.get("binary")
        rec["stale"] = not isinstance(ident, dict) or _identity(name, path) != ident
        if not _fresh(rec, now): rec["latest"] = None
        out[name] = rec
    return out


def outdated_lines(records: dict, method=None, path: str | None = None) -> list[str]:
    method = method or (lambda name, pkg: install_method(name, pkg, path=path))
    lines = []
    for name, rec in records.items():
        if name not in CLIS: continue
        inst, latest = rec.get("installed"), rec.get("latest")
        if not (isinstance(inst, str) and isinstance(latest, str)): continue
        try:
            if _vkey(latest) <= _vkey(inst): continue
        except ValueError:
            continue
        pkg, brew = CLIS[name]
        lines.append(f"HOST_CLI_OUTDATED {name} {inst} < {latest}; update: {update_command(method(name, pkg), pkg, brew)}")
    return lines
