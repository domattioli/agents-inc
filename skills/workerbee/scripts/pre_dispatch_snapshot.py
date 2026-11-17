"""Pre-dispatch baseline: capture and verify the working tree a delegate inherits.

Usage: python3 pre_dispatch_snapshot.py capture <out.json> [--allow <path>...]
       python3 pre_dispatch_snapshot.py verify <out.json> [--scope-aware] [--repo <dir>] [--allow <path>...]...

Run capture from inside the repository. capture writes JSON with keys time,
head, repo (the absolute repository top level), porcelain (`git status
--porcelain`), and sha256 (repo-relative path -> hex digest of every
pre-existing dirty file plus every untracked file, enumerated recursively with
`git ls-files --others --exclude-standard`). verify needs no particular cwd:
it uses --repo, else the snapshot's repo, else the cwd's repository.

Unreadable files are recorded as "unreadable"; verify lists them as `UNREADABLE <path>` and treats
unreadable-before and unreadable-after as unchanged. With --scope-aware, an allowed path that is unreadable before or
after is printed as `UNREADABLE <path>` and never counted as changed (no bytes were compared).

capture --allow hashes the git-ignored files under the declared paths (a missing ignored file is recorded as null) and
lists the paths in `declared`. verify --scope-aware prints `UNBASELINED <path>` for a git-ignored allow path with no
baseline (an older snapshot, or capture run without --allow): its change is not measured.

verify exits 0 when every hashed file is unchanged and the tree differs from
the snapshot only at --allow paths (a path or a directory prefix). Else it
exits 1 and prints one `CHANGED <path>` line per offending path. Exit 2 on
usage or git error. Capture and verify on the same host and git config.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time


def _git(*args: str) -> str:
    # core.quotepath=off keeps non-ASCII paths literal instead of octal-escaped.
    return subprocess.run(["git", "-c", "core.quotepath=off", *args],
                          capture_output=True, text=True, check=True).stdout


def _unquote(p: str) -> str:
    """Undo git C-style quoting ("a\\"b", octal escapes) on one porcelain path."""
    p = p.strip()
    if len(p) >= 2 and p.startswith('"') and p.endswith('"'):
        raw = p[1:-1].encode("utf-8").decode("unicode_escape")
        try:
            return raw.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return raw
    return p


UNREADABLE = "unreadable"  # marker digest for a path the process may not read (#173)


def _sha(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except (FileNotFoundError, IsADirectoryError):
        return None
    except OSError:  # PermissionError and kin: record, never crash
        return UNREADABLE


def _porcelain_paths(line: str) -> list[str]:
    body = line[3:]
    return [_unquote(p) for p in body.split(" -> ")] if body else []


def _dirty_files(porcelain: str) -> set[str]:
    files: set[str] = set()
    for line in porcelain.splitlines():
        if line.startswith("??"):
            continue
        for p in _porcelain_paths(line):
            if os.path.isfile(p):
                files.add(p)
    return files


def _untracked() -> set[str]:
    return {p for p in _git("ls-files", "--others", "--exclude-standard").splitlines() if p}


def _is_ignored(path: str) -> bool:
    for cand in (path, path.rstrip("/") + "/"):
        if subprocess.run(["git", "check-ignore", "-q", "--", cand], capture_output=True).returncode == 0:
            return True
    return False


def _ignored_files(path: str, cap: int = 5000) -> list[str]:
    out = _git("ls-files", "--others", "--ignored", "--exclude-standard", "--", path.rstrip("/") or ".").splitlines()
    return [p for p in out if p][:cap]


def _declared(allow: list[str]) -> tuple[dict, list[str]]:
    """Hash the git-ignored files under declared paths; a declared ignored file that does not exist yet is None."""
    hashes: dict = {}
    declared: list[str] = []
    for a in allow:
        a = a.rstrip("/")
        if not a or not _is_ignored(a):
            continue
        declared.append(a)
        if os.path.isdir(a):
            for f in _ignored_files(a):
                hashes[f] = _sha(f)
        elif not os.path.isdir(a):
            hashes[a] = _sha(a)
    return hashes, declared


def capture(out: str, allow: list[str] | None = None) -> int:
    porcelain = _git("status", "--porcelain")
    files = _dirty_files(porcelain) | _untracked()
    extra, declared = _declared(allow or [])
    snap = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "head": _git("rev-parse", "HEAD").strip(),
        "repo": os.getcwd(),  # main() has moved to the top level; verify reads it back (#92)
        "porcelain": porcelain,
        "sha256": {**{p: _sha(p) for p in sorted(files)}, **extra},
        "declared": declared,
        # ignored paths as the capturing user's git sees them; a sandboxed verify may lack ~/.gitignore
        "ignored": sorted(p for p in _git("ls-files", "--others", "--ignored", "--exclude-standard",
                                          "--directory").splitlines() if p),
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=1)
        fh.write("\n")
    print(f"captured {len(files | set(extra))} file(s) -> {out}")
    return 0


def _allowed(path: str, allow: list[str]) -> bool:
    path = path.rstrip("/")
    for a in allow:
        a = a.rstrip("/")
        if path == a or path.startswith(a + "/"):
            return True
    return False


def verify(snap_path: str, allow: list[str], scope_aware: bool = False) -> int:
    try:
        with open(snap_path, encoding="utf-8") as fh:
            snap = json.load(fh)
    except OSError:
        print(f"snapshot unreadable: {snap_path}", file=sys.stderr)
        return 2
    changed: set[str] = set()  # outside the allow list
    in_scope: set[str] = set()  # spec 042 --scope-aware only: allowed paths that differ from the baseline
    hashes = snap.get("sha256", {})
    unreadable: list[str] = []
    unproven: set[str] = set()  # scope-aware: allowed paths whose bytes could not be compared
    for path, digest in hashes.items():
        if _allowed(path, allow):
            now = _sha(path) if scope_aware else None
            if scope_aware and UNREADABLE in (now, digest):
                unproven.add(path)
            elif scope_aware and now != digest:
                in_scope.add(path)
            continue
        now = _sha(path)
        if now == UNREADABLE and digest == UNREADABLE:
            unreadable.append(path)  # unreadable before and after: unchanged
        elif now != digest:
            changed.add(path)
    ignored = list(snap.get("ignored", []))
    old = set(snap.get("porcelain", "").splitlines())
    new = set(_git("status", "--porcelain").splitlines())
    for line in old ^ new:
        for p in _porcelain_paths(line):
            # `?? dir/` collapses a new untracked directory; its files are checked one by one below
            if line.startswith("??") and p.endswith("/"):
                continue
            if _allowed(p, allow):
                if scope_aware and p not in hashes:  # dirty now, never hashed (clean before launch)
                    in_scope.add(p)
            elif not (line.startswith("??") and _allowed(p, ignored)):
                changed.add(p)
    # untracked files hidden inside a pre-existing untracked directory line
    for p in _untracked() - set(hashes):
        if _allowed(p, allow):
            if scope_aware and not _allowed(p, ignored):  # new in-scope file inside a new untracked directory
                in_scope.add(p)
        elif not _allowed(p, ignored):
            changed.add(p)
    if scope_aware:
        for a in snap.get("declared", []):  # new git-ignored files inside a declared directory
            if os.path.isdir(a):
                for f in _ignored_files(a):
                    if f not in hashes and _allowed(f, allow):
                        in_scope.add(f)
    if snap.get("head") and _git("rev-parse", "HEAD").strip() != snap["head"]:
        changed.add("HEAD")
    for p in sorted(set(unreadable) if not scope_aware else unproven):
        print(f"UNREADABLE {p}")
    if scope_aware:
        declared = {d.rstrip("/") for d in snap.get("declared", [])}
        for a in sorted(allow):
            if a.rstrip("/") not in declared and _is_ignored(a):
                print(f"UNBASELINED {a}")
    for p in sorted(in_scope):
        print(f"CHANGED {p}")
    for p in sorted(changed):
        print(f"OUTSIDE {p}" if scope_aware else f"CHANGED {p}")
    if changed:
        return 1
    if not in_scope:
        print("UNCHANGED outside allowed paths")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "capture":
        cmd, path, allow, repo, scope_aware = "capture", argv[1], [], None, False
        if argv[2:]:
            if argv[2] != "--allow" or len(argv) < 4:
                print(__doc__, file=sys.stderr)
                return 2
            allow = [a for a in argv[3:] if a != "--allow"]
    elif len(argv) >= 2 and argv[0] == "verify":
        cmd, path, rest, allow, repo = "verify", argv[1], argv[2:], [], None
        scope_aware = "--scope-aware" in rest  # 042 opt-in: CHANGED = in scope, OUTSIDE = outside; exit 1 only for OUTSIDE
        rest = [a for a in rest if a != "--scope-aware"]
        while rest:
            # `--allow a b c` and `--allow a --allow b` both work; each --allow needs a path.
            if rest[0] not in ("--allow", "--repo") or len(rest) < 2 or rest[1] in ("--allow", "--repo"):
                print(__doc__, file=sys.stderr)
                return 2
            if rest[0] == "--repo":
                repo, rest = rest[1], rest[2:]
                continue
            rest = rest[1:]
            while rest and rest[0] not in ("--allow", "--repo"):
                allow.append(rest[0])
                rest = rest[1:]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        path = os.path.abspath(path)
        if cmd == "verify" and repo is None:
            # #92: the repo recorded at capture, so verify works from any cwd
            with contextlib.suppress(OSError, ValueError, AttributeError):
                with open(path, encoding="utf-8") as fh:
                    recorded = json.load(fh).get("repo")
                if isinstance(recorded, str) and os.path.isdir(recorded):
                    repo = recorded
        # porcelain and ls-files paths are repo-root relative; resolve them there.
        top = _git(*(["-C", repo] if repo else []), "rev-parse", "--show-toplevel").strip()
        os.chdir(top)
        return capture(path, allow) if cmd == "capture" else verify(path, allow, scope_aware)
    except subprocess.CalledProcessError as exc:
        print(f"git error: {exc.stderr.strip()}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
