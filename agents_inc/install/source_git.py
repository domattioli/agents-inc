"""#174: git state of an install source, so the stale check can ignore work in progress after a clean install.

Install records the release it staged, the source HEAD, and whether the bundle paths were clean
(`<state>/source-git.json`). While that release is the active one, the stale check compares commits, not staged trees:
an uncommitted edit never makes the install stale; HEAD moving to a commit whose bundle paths differ does. Git calls
take no optional locks and never write the source repo.
Limit: the state is read just before staging, and files git status does not show (skip-worktree, assume-unchanged,
excluded) count as clean, so an edit in that window or in such a file is not detected."""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

from .bundle import ALLOWLIST, FILE_ALLOWLIST, OPTIONAL_ALLOWLIST

BUNDLE_PATHS = (*ALLOWLIST, *OPTIONAL_ALLOWLIST, *FILE_ALLOWLIST)  # the paths stage_bundle copies from a source
RECORD = "source-git.json"
KEEP_ENV = ("GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")  # pick config files only
RELEASE_WORKTREE = ("To develop on a machine that runs the install, install from a release worktree: "
                    "git worktree add <path> <tag>, then agents-inc repair --source <path>.")

def _run(source: Path, *argv: str) -> subprocess.CompletedProcess:
    """git in source with no inherited GIT_* variable that redirects the repo (GIT_DIR, GIT_INDEX_FILE, ...); only the
    config-file selectors in KEEP_ENV pass through. Launch failure is RuntimeError."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k in KEEP_ENV}
    try: return subprocess.run(["git", "--no-optional-locks", "-C", str(source), *argv], env=env, capture_output=True,
                               text=True, timeout=60, stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError) as exc: raise RuntimeError(f"git {argv[0]}: {exc}") from exc

def _git(source: Path, *argv: str) -> str:
    done = _run(source, *argv)
    if done.returncode != 0: raise RuntimeError(f"git {argv[0]} failed ({done.returncode}): {done.stderr.strip()}")
    return done.stdout

def is_git_checkout(source: Path) -> bool:
    """A `.git` entry at the source root: a directory, or a file for a linked worktree."""
    return (Path(source) / ".git").exists()

def source_state(source: Path) -> dict | None:
    """{"head": sha, "clean": bool} for a git checkout; None for any other source or any git failure."""
    if not is_git_checkout(source): return None
    try:
        head = _git(source, "rev-parse", "--verify", "HEAD^{commit}").strip()
        dirty = _git(source, "status", "--porcelain", "--untracked-files=normal", "--", *BUNDLE_PATHS).strip()
    except RuntimeError: return None
    return {"head": head, "clean": not dirty} if head else None

def save_record(state_dir: Path, state: dict | None, release: str) -> None:
    """Write the record tied to the staged release hash, or remove an earlier one when there is no git state."""
    record = Path(state_dir) / RECORD
    if state is None: record.unlink(missing_ok=True)
    else: record.write_text(json.dumps({**state, "release": release}, sort_keys=True) + "\n")

def load_record(state_dir: Path) -> dict | None:
    try: data = json.loads((Path(state_dir) / RECORD).read_text())
    except (OSError, ValueError): return None
    if (isinstance(data, dict) and isinstance(data.get("head"), str) and isinstance(data.get("clean"), bool)
            and isinstance(data.get("release"), str) and data["release"]): return data
    return None  # also a record without `release` from before it was added: the caller compares digests

def bundle_changed_since(source: Path, sha: str) -> bool | None:
    """True when HEAD's bundle paths differ from sha's, False when they match, None when sha no longer exists (the
    caller compares digests). RuntimeError when git cannot run or cannot read HEAD."""
    if _git(source, "rev-parse", "--verify", "HEAD^{commit}").strip() == sha: return False
    if _run(source, "rev-parse", "--verify", "--quiet", sha + "^{commit}").returncode != 0: return None
    done = _run(source, "diff-tree", "--quiet", sha, "HEAD", "--", *BUNDLE_PATHS)  # plumbing: no user diff settings
    if done.returncode in (0, 1): return done.returncode == 1
    raise RuntimeError(f"git diff-tree failed ({done.returncode}): {done.stderr.strip()}")

def source_warnings(source: Path, state: dict | None) -> list[str]:
    """Install/repair notices for a git source; warnings only, never a refusal."""
    if state is None: return []
    out = []
    if not state["clean"]:
        out.append(f"WARNING: --source {source} has uncommitted or untracked changes in the bundle; they were installed. "
                   "Any further edit there makes the install stale (INSTALL_STALE) and stops dispatch until repair. "
                   + RELEASE_WORKTREE)
    try: tagged = _run(source, "describe", "--tags", "--exact-match", "HEAD").returncode == 0
    except RuntimeError: tagged = True  # say nothing on git failure
    if not tagged: out.append(f"NOTE: --source {source} HEAD is not on a release tag.")
    return out
