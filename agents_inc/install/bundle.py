"""Immutable allowlisted runtime bundles."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import stat
import tempfile
import sys
from dataclasses import dataclass
from pathlib import Path

from .paths import InstallPaths
from .receipt import InstallReceipt

ALLOWLIST = ("agents_inc", "skills/workerbee", "skills/codex-bridge")
OPTIONAL_ALLOWLIST = ("workerbees", "mods/agents-inc", "mods/delegate-pane")  # the mod (spec 027) ships from a checkout, not from package data
# Single files the runtime reads; agents_inc/schema.py parses the 3NF doc.
FILE_ALLOWLIST = ("docs/governance/SCHEMA-3NF.md",)
EXCLUDED = {".git", ".env", ".workerbees", "__pycache__", "bridge.py", "node_modules"}

@dataclass(frozen=True)
class StagedBundle:
    path: Path
    digest: str

def _files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.name == "manifest.json" or any(part in EXCLUDED or part.endswith(".bak") for part in path.relative_to(root).parts): continue
        if path.is_symlink(): raise ValueError(f"symlink payload rejected: {path}")
        if path.is_file(): yield path
        elif not path.is_dir(): raise ValueError(f"non-regular payload rejected: {path}")

def _manifest(root: Path) -> list[dict[str, object]]:
    result = []
    for path in _files(root):
        payload = path.read_bytes()
        result.append({"path": str(path.relative_to(root)), "size": len(payload), "mode": stat.S_IMODE(path.stat().st_mode), "sha256": hashlib.sha256(payload).hexdigest()})
    return result

def stage_bundle(source: Path, paths: InstallPaths) -> StagedBundle:
    source = source.resolve()
    if not source.is_dir(): raise ValueError("source checkout does not exist")
    stage_parent = paths.releases.parent; stage_parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".stage-", dir=stage_parent))
    try:
        for item in (*ALLOWLIST, *OPTIONAL_ALLOWLIST):
            origin = source / item
            if not origin.is_dir():
                if item in OPTIONAL_ALLOWLIST:
                    continue
                raise ValueError(f"missing required bundle payload: {item}")
            destination = temp / item
            for file in _files(origin):
                target = destination / file.relative_to(origin); target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
                if target.name == "SKILL.md":
                    # Installed skills must not depend on PATH or source checkout.
                    text = target.read_text()
                    target.write_text(text.replace("@AGENTS_INC_LAUNCHER@", str(paths.current / "bin/agents-inc")))
        for item in FILE_ALLOWLIST:
            origin = source / item
            if origin.is_file() and not origin.is_symlink():
                target = temp / item; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, target)
        launcher = temp / "bin/agents-inc"
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text(
            f"#!{Path(sys.executable).resolve()}\n"
            "import sys\nfrom pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
            "from agents_inc.install.cli import main\n"
            "raise SystemExit(main())\n"
        )
        launcher.chmod(0o700)
        manifest = _manifest(temp)
        (temp / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        digest = hashlib.sha256((temp / "manifest.json").read_bytes()).hexdigest()
        final = paths.releases / digest
        paths.releases.mkdir(parents=True, exist_ok=True)
        if final.exists(): shutil.rmtree(temp)
        else: os.replace(temp, final)
        return StagedBundle(final, digest)
    except Exception:
        if temp.exists(): shutil.rmtree(temp)
        raise

def verify_bundle(path: Path) -> bool:
    try:
        expected = json.loads((path / "manifest.json").read_text())
        actual = _manifest(path)
        return expected == actual
    except (OSError, ValueError, json.JSONDecodeError): return False

def activate(staged: StagedBundle, paths: InstallPaths, receipt: InstallReceipt, journal=None) -> InstallReceipt:
    if not verify_bundle(staged.path): raise RuntimeError("WB_RELEASE_UNTRUSTED: staged bundle hash mismatch")
    paths.current.parent.mkdir(parents=True, exist_ok=True)
    prior = os.readlink(paths.current) if paths.current.is_symlink() else None
    replacement = paths.current.with_name(".current.new")
    desired = os.path.relpath(staged.path, replacement.parent)
    replacement.unlink(missing_ok=True); replacement.symlink_to(desired)
    if journal: journal.apply("symlink", paths.current, prior, desired, lambda: os.replace(replacement, paths.current))
    else: os.replace(replacement, paths.current)
    return InstallReceipt(staged.digest, receipt.python_path, receipt.codex_path, receipt.owned_paths, prior)
