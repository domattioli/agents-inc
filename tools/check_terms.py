#!/usr/bin/env python3
"""Retired-terms lint (spec 041).

Fails on retired role, rung and relation aliases in current Markdown docs.
Usage: check_terms.py [--allowlist] [--cutoff N] [path ...]
With no paths it scans `git ls-files '*.md'` and skips the allowlist.
Explicit paths bypass the allowlist unless --allowlist is given.
Exit 0 clean, 1 findings, 2 bad config or usage.
"""
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(__file__).resolve().parent / "retired_terms.json"
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
DECISION_HEAD = re.compile(r"^## D(\d+)\b")
HISTORICAL = "<!-- terms: historical -->"


class ConfigError(Exception):
    pass


def load_config(path=CONFIG):
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        patterns = [(re.compile(p["pattern"]), p["replacement"], p["row"])
                    for p in cfg["patterns"]]
        allow = list(cfg.get("allowlist", []))
        cutoff = cfg.get("cutoff_decision")
        if cutoff is not None and not isinstance(cutoff, int):
            raise ConfigError("cutoff_decision must be an integer or null")
    except (OSError, ValueError, KeyError, TypeError, re.error) as exc:
        raise ConfigError(f"bad config {path}: {exc}")
    return patterns, allow, cutoff


def rel(path):
    p = Path(path).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def is_allowlisted(relpath, allow):
    return any(fnmatch.fnmatch(relpath, g) for g in allow)


def blank_code_spans(line):
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def table_cells(line):
    return line.strip().strip("|").split("|")


def scan_text(text, patterns, cutoff=None, is_decisions=False, is_context=False):
    """Return a list of (lineno, word, replacement) findings."""
    findings = []
    fence = None  # the opening fence character while inside a fenced block
    retired_col = None  # index of the Retired aliases column in the current table
    skip_entry = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        fm = FENCE.match(raw)
        if fm:
            if fence is None:
                fence = fm.group(1)[0]
            elif fm.group(1)[0] == fence:
                fence = None
            continue
        if fence is not None:
            continue
        if is_decisions and raw.startswith("## "):
            head = DECISION_HEAD.match(raw)
            skip_entry = bool(head) and (cutoff is None or int(head.group(1)) < cutoff)
        if skip_entry or HISTORICAL in raw:
            continue
        line = raw
        if is_context and line.lstrip().startswith("|"):
            cells = table_cells(line)
            if retired_col is None:
                for i, c in enumerate(cells):
                    if c.strip().lower() == "retired aliases" or c.strip().lower().startswith("retired aliases"):
                        retired_col = i
            elif retired_col < len(cells) and not set("".join(cells)) <= set("-: "):
                cells[retired_col] = ""
                line = "|" + "|".join(cells) + "|"
        elif not line.lstrip().startswith("|"):
            retired_col = None
        line = blank_code_spans(line)
        for regex, replacement, _row in patterns:
            for m in regex.finditer(line):
                findings.append((lineno, m.group(0), replacement))
    return findings


def scan_file(path, patterns, cutoff):
    text = Path(path).read_text(encoding="utf-8")
    is_decisions = Path(path).name.lower().startswith("decisions")
    return scan_text(text, patterns, cutoff, is_decisions, rel(path) == "CONTEXT.md")


def tracked_markdown():
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    return [ROOT / line for line in out.splitlines() if line]


def main(argv):
    args = list(argv)
    use_allowlist = False
    cutoff_override = None
    paths = []
    while args:
        a = args.pop(0)
        if a == "--allowlist":
            use_allowlist = True
        elif a == "--cutoff" and args:
            try:
                cutoff_override = int(args.pop(0))
            except ValueError:
                print("check_terms: --cutoff needs an integer", file=sys.stderr)
                return 2
        else:
            paths.append(a)
    try:
        patterns, allow, cutoff = load_config()
    except ConfigError as exc:
        print(f"check_terms: {exc}", file=sys.stderr)
        return 2
    if cutoff_override is not None:
        cutoff = cutoff_override
    if paths:
        files, filter_allow = [Path(p) for p in paths], use_allowlist
    else:
        try:
            files, filter_allow = tracked_markdown(), True
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"check_terms: git ls-files failed: {exc}", file=sys.stderr)
            return 2
    count = 0
    for f in files:
        name = rel(f)
        if filter_allow and is_allowlisted(name, allow):
            continue
        try:
            found = scan_file(f, patterns, cutoff)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"check_terms: cannot read {name}: {exc}", file=sys.stderr)
            return 2
        for lineno, word, replacement in found:
            print(f"{name}:{lineno}: {word} -> {replacement}")
            count += 1
    return 1 if count else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
