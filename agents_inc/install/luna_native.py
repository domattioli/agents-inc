"""Native agents-inc:luna type (spec 028): readiness, the on/off switch, and the verbs the mod calls.

`status` answers whether the mod should offer the type. It reads files only: no Codex process, no network.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from .hook import write_setting
from .paths import InstallPaths
from .receipt import InstallReceipt
from .runtime import load_model_map

SWITCH_KEY = "luna_type"
SWITCH_MODES = ("on", "off")


def read_switch(paths: InstallPaths) -> str:
    """'on' unless settings.json says luna_type is 'off'. An unreadable file leaves the type on, like the agent gate default."""
    try:
        data = json.loads(paths.settings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "on"
    return "off" if isinstance(data, dict) and data.get(SWITCH_KEY) == "off" else "on"


def write_switch(paths: InstallPaths, mode: str) -> None:
    if mode not in SWITCH_MODES: raise ValueError(f"luna switch must be one of {', '.join(SWITCH_MODES)}: {mode!r}")
    write_setting(paths, SWITCH_KEY, mode)


def codex_state(paths: InstallPaths) -> str:
    """ready | missing | logged-out. The same checks the install and `lead_codex_home` make: the receipt names an
    executable Codex, and ~/.codex/auth.json exists. The credential is never read."""
    try:
        codex = InstallReceipt.load(paths.receipt).codex_path
    except (OSError, ValueError):
        return "missing"
    if codex is None or not codex.is_file() or not os.access(codex, os.X_OK): return "missing"
    return "ready" if (paths.home / ".codex" / "auth.json").is_file() else "logged-out"


def catalog_state(paths: InstallPaths, slug: str) -> str:
    """ok when Codex's model cache holds an entry for slug (the source of the host-tools catalog), else missing."""
    try:
        cache = json.loads((paths.home / ".codex" / "models_cache.json").read_text())
        return "ok" if any(m.get("slug") == slug for m in cache.get("models", [])) else "missing"
    except (OSError, ValueError, AttributeError):
        return "missing"


def status(paths: InstallPaths) -> dict:
    slug = load_model_map(roster=paths.roster, env={"HOME": str(paths.home)})["luna"]
    switch, codex, catalog = read_switch(paths), codex_state(paths), catalog_state(paths, slug)
    offered = switch == "on" and codex == "ready"
    if switch == "off": reason = "switched off (agents-inc luna on)"
    elif codex != "ready": reason = f"Codex {codex}"
    else: reason = "ready" if catalog == "ok" else "ready; model catalog missing, steps fail until Codex has cached the model"
    return {"offered": offered, "reason": reason, "slug": slug, "codex": codex, "catalog": catalog, "switch": switch}


def doctor_code(report: dict) -> str | None:
    """The doctor warning code for a status report, or None when the type is ready."""
    if report["switch"] == "off": return "LUNA_OFF"
    if report["codex"] != "ready": return "LUNA_CODEX_NOT_READY"
    if report["catalog"] != "ok": return "LUNA_CATALOG_MISSING"
    return None


def doctor_line(report: dict) -> str:
    code = doctor_code(report)
    if code is None: return "luna type: ready"
    return "luna type: off" if code == "LUNA_OFF" else f"luna type: unavailable ({code})"


OUTCOMES = ("done", "failed", "quota-paused", "aborted")
CHANGED_PATH_CAP = 20


def _run_dir(paths: InstallPaths, session: str, agent: str) -> Path:
    """<state>/luna-runs/<session>/<agent>: outside cwd, so a luna step cannot rewrite its own baseline."""
    for part in (session, agent):
        if not part or Path(part).name != part or part in (".", ".."): raise ValueError(f"not a usable id: {part!r}")
    return paths.state / "luna-runs" / session / agent


def begin(paths: InstallPaths, session: str, agent: str, cwd: str, task: str | None = None) -> dict:
    """Spec 028 D6 item 1: pin the working tree and write the agent's dispatch row. A cwd outside git records
    snapshot 'no-repo' and goes on. Returns {"snapshot": "captured"|"no-repo"}."""
    from .. import host_ledger
    from . import dispatch  # lazy: dispatch is heavy, and status/on/off must not load it
    folder = _run_dir(paths, session, agent)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = folder / "snapshot.json"
    target.unlink(missing_ok=True)
    rc, _ = dispatch.snapshot("capture", str(target), cwd=Path(cwd))
    snapshot = "captured" if rc == 0 and target.is_file() else "no-repo"
    slug = load_model_map(roster=paths.roster, env={"HOME": str(paths.home)})["luna"]
    host_ledger.record_native_luna(paths.state, host_ledger.native_luna_dispatch_row(agent, session, slug, task, cwd, snapshot))
    return {"snapshot": snapshot}


def end(paths: InstallPaths, session: str, agent: str, outcome: str, cwd: str = ".", usage: dict | None = None) -> dict:
    """Spec 028 D6 item 2: verify the tree against the begin snapshot with no allow list and append a return row. Each
    hand-back appends one row to the agent's node. 'changed' means the tree changed while the agent ran, not that this
    agent changed it. Returns {"snapshot": str, "changed": [paths]}."""
    from .. import host_ledger
    from . import dispatch
    if outcome not in OUTCOMES: raise ValueError(f"outcome must be one of {', '.join(OUTCOMES)}: {outcome!r}")
    target = _run_dir(paths, session, agent) / "snapshot.json"
    changed: list[str] = []
    if not target.is_file(): snapshot = "no-repo"
    else:
        rc, text = dispatch.snapshot("verify", str(target), cwd=Path(cwd))
        if rc == 0: snapshot = "unchanged"
        elif rc == 1:
            changed = [line[len("CHANGED "):].strip() for line in text.splitlines() if line.startswith("CHANGED ")]
            snapshot = f"changed:{len(changed)}"
        else: snapshot = "unverified"
    host_ledger.record_native_luna(paths.state, host_ledger.native_luna_return_row(
        agent, session, outcome, usage or {}, snapshot, changed))
    return {"snapshot": snapshot, "changed": changed[:CHANGED_PATH_CAP]}


def run_record(paths: InstallPaths, verb: str, session: str, agent: str, cwd: str, outcome: str | None,
               usage: str | None, task: str | None) -> int:
    """`luna begin|end`: print one JSON object. Exit 2 on bad arguments; the mod logs a failure and goes on (Q2)."""
    try:
        if verb == "begin": result = begin(paths, session, agent, cwd, task)
        else:
            parsed = json.loads(usage) if usage else {}
            if not isinstance(parsed, dict): raise ValueError("--usage must be a JSON object")
            result = end(paths, session, agent, outcome or "", cwd, parsed)
    except (ValueError, OSError) as exc:
        print(f"agents-inc luna {verb}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


def run(paths: InstallPaths, verb: str, as_json: bool = False) -> int:
    if verb in SWITCH_MODES:
        write_switch(paths, verb)
        print(f"luna type: {verb}")
        return 0
    report = status(paths)
    if as_json: print(json.dumps(report))
    else:
        print(f"offered: {'yes' if report['offered'] else 'no'} ({report['reason']})")
        print(f"slug: {report['slug']}; codex: {report['codex']}; catalog: {report['catalog']}; switch: {report['switch']}")
    return 0
