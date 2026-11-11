"""Locate data files that live beside the code: skills, the 3NF schema doc.

A checkout and an installed release (``~/.local/share/agents-inc/current``) keep the repository
layout, so ``repo_root() / rel`` exists. A pip install ships the same files as package data under
``agents_inc._skills`` (maps ``skills/``) and ``agents_inc._docs`` (maps ``docs/governance/``);
``repo_file`` falls back to those. Standard library only.
"""
from __future__ import annotations

import atexit
import contextlib
import importlib.resources as resources
from pathlib import Path

# repo-relative prefix -> package that carries it as package data
_PACKAGED = (("skills/", "agents_inc._skills"), ("docs/governance/", "agents_inc._docs"))
_STACK = contextlib.ExitStack()
atexit.register(_STACK.close)


def repo_root() -> Path:
    """Directory that holds ``agents_inc/``: the checkout root, or ``site-packages`` on a pip install."""
    return Path(__file__).resolve().parents[1]


def repo_file(rel: str) -> Path:
    """Return the path of repo-relative file ``rel``, from the checkout or from package data."""
    path = repo_root() / rel
    if path.exists():
        return path
    for prefix, package in _PACKAGED:
        if rel.startswith(prefix):
            try:
                node = resources.files(package)
                for part in rel[len(prefix):].split("/"):
                    node = node.joinpath(part)
                if not node.is_file() and not node.is_dir():
                    continue
                if isinstance(node, Path):
                    return node
                return _STACK.enter_context(resources.as_file(node))
            except (ModuleNotFoundError, FileNotFoundError, OSError):
                continue
    raise FileNotFoundError(
        f"agents_inc: data file {rel!r} not found in a checkout or in the installed package data; "
        "reinstall with `pipx install --force agents-inc` (a bare pip install fails on an externally managed Python, PEP 668)")
