#!/usr/bin/env python3
"""Deterministic structure gate for the demo clip's formatted output.

Checks structure only, never wording:
  1. exactly one level-1 heading, on the first non-blank line;
  2. level-2 headings exactly Overview, Schedule, Rules, Contacts, in that order;
  3. no other heading levels;
  4. Overview holds a non-empty paragraph and no list;
  5. Schedule, Rules and Contacts each hold only a bullet list ("- " items)
     with 3, 3 and 2 items (no lost or invented items);
  6. the word sequence, without Markdown markup and section labels, equals
     the draft's (case-sensitive, punctuation kept).
It never reads the source notes, so it cannot see a wrong fact.
Exit 0 when every rule holds, 1 otherwise (one line per failure on stderr).
Standard library only.
"""
import re
import sys

SECTIONS = ["Overview", "Schedule", "Rules", "Contacts"]
LIST_COUNTS = {"Schedule": 3, "Rules": 3, "Contacts": 2}


def check(text):
    errors = []
    lines = text.splitlines()
    nonblank = [l for l in lines if l.strip()]
    if not nonblank or not re.match(r"^# \S", nonblank[0]):
        errors.append("first line is not a level-1 heading")
    h1 = [l for l in lines if re.match(r"^# ", l)]
    if len(h1) != 1:
        errors.append("expected 1 level-1 heading, found %d" % len(h1))
    for l in lines:
        if re.match(r"^#{3,} ", l):
            errors.append("unexpected heading level: %s" % l.strip())
    body = {}
    current = None
    for l in lines:
        m = re.match(r"^## (.+?)\s*$", l)
        if m:
            current = m.group(1)
            body.setdefault(current, [])
            continue
        if current is not None and l.strip():
            body[current].append(l)
    found = [m.group(1) for m in (re.match(r"^## (.+?)\s*$", l) for l in lines) if m]
    if found != SECTIONS:
        errors.append("sections %s, expected %s" % (found, SECTIONS))
    ov = body.get("Overview", [])
    if not ov:
        errors.append("Overview is empty")
    if any(re.match(r"^\s*([-*+]|\d+\.) ", l) for l in ov):
        errors.append("Overview holds a list")
    for name, want in LIST_COUNTS.items():
        items = body.get(name, [])
        bad = [l for l in items if not l.startswith("- ")]
        if bad:
            errors.append("%s has non-bullet lines: %d" % (name, len(bad)))
        n = sum(1 for l in items if l.startswith("- "))
        if n != want:
            errors.append("%s has %d items, expected %d" % (name, n, want))
    return errors


def words(text, markdown):
    """Word sequence after dropping Markdown markup and section labels."""
    out = []
    for l in text.splitlines():
        s = l.strip()
        if markdown:
            s = re.sub(r"^(#{1,6} |- )", "", s)
        if s in SECTIONS:
            continue
        out.extend(s.split())
    return out


def check_wording(formatted, draft):
    # Compares against the draft only. This checker never reads the source
    # notes, so a wrong fact copied faithfully from the draft passes; that is
    # why a reviewer is needed.
    a, b = words(formatted, True), words(draft, False)
    if a == b:
        return []
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return ["wording differs from draft at word %d: %r vs draft %r"
            % (i + 1, " ".join(a[i:i + 4]), " ".join(b[i:i + 4]))]


def main(argv):
    if len(argv) != 3:
        print("usage: check_structure.py <formatted.md> <draft.md>", file=sys.stderr)
        return 1
    try:
        with open(argv[1], encoding="utf-8") as f:
            text = f.read()
        with open(argv[2], encoding="utf-8") as f:
            draft = f.read()
    except OSError as e:
        print("cannot read: %s" % e, file=sys.stderr)
        return 1
    errors = check(text) + check_wording(text, draft)
    for e in errors:
        print("FAIL " + e, file=sys.stderr)
    if errors:
        return 1
    print("structure ok: 1 title, 4 sections, lists 3/3/2; wording matches draft")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
