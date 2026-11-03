"""Managed host-skill links, never overwriting foreign paths."""
from __future__ import annotations
import os
from pathlib import Path
from .paths import InstallPaths
from .receipt import InstallReceipt, OwnedPath

NAMES = ("workerbee", "codex-bridge")

def install_skill_links(paths: InstallPaths, release: Path, receipt: InstallReceipt, adopt_existing_workerbee: bool = False, journal=None) -> InstallReceipt:
    owned = list(receipt.owned_paths)
    recorded = {item.path: item for item in owned}
    for directory in (paths.claude_skills, paths.codex_skills):
        directory.mkdir(parents=True, exist_ok=True)
        for name in NAMES:
            target = directory / name; desired = paths.current / "skills" / name; desired_raw = str(desired)
            if target.exists() or target.is_symlink():
                existing = os.readlink(target) if target.is_symlink() else None
                prior = recorded.get(target)
                adoptable = directory == paths.claude_skills and name == "workerbee" and target.is_symlink() and not prior
                if target.is_symlink() and prior:
                    if existing == (prior.target or desired_raw): continue
                elif adoptable and adopt_existing_workerbee:
                    owned.append(OwnedPath(target, "symlink", existing, desired_raw))
                else: raise RuntimeError(f"WB_CONFIG_CONFLICT: foreign skill path {target}")
                if journal: journal.apply("symlink", target, existing, desired_raw, target.unlink)
                else: target.unlink()
            if journal: journal.apply("symlink", target, None, desired_raw, lambda: target.symlink_to(desired_raw))
            else: target.symlink_to(desired_raw)
            if target not in {item.path for item in owned}: owned.append(OwnedPath(target, "symlink", None, desired_raw))
    return InstallReceipt(receipt.release_hash, receipt.python_path, receipt.codex_path, tuple(owned), receipt.prior_release)

def restore_skill_links(paths: InstallPaths, receipt: InstallReceipt, journal=None, restored: set[Path] | None = None) -> set[Path]:
    retained: set[Path] = set()
    for item in receipt.owned_paths:
        if item.kind != "symlink": continue
        path = item.path
        if not path.is_symlink():
            if path.exists(): retained.add(path)
            continue
        if item.target is None or os.readlink(path) != item.target:
            retained.add(path); continue
        if journal: journal.apply("unlink", path, item.predecessor, None, path.unlink)
        else: path.unlink()
        if item.predecessor is not None:
            if journal: journal.apply("symlink", path, None, item.predecessor, lambda: path.symlink_to(item.predecessor))
            else: path.parent.mkdir(parents=True, exist_ok=True); path.symlink_to(item.predecessor)
            if restored is not None: restored.add(path)
    return retained
