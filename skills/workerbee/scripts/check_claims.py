"""Spec 042 phase 2: compare a delegate's claims block with the run. Advisory: it never decides the run outcome.

Usage: check_claims.py <report_file> <run_json>   (run_json: {"changed": [...], "gate_results": [...], "stop_rule": "..."})
Standard library only; no model call; reads only the two files it is given (FR-016).
Contract: specs/042-measured-status/contracts/claims-block.md."""
from __future__ import annotations
import json
import re
import sys

OPEN_RE = re.compile(r"^```claims[ \t]*$")
CLOSE_RE = re.compile(r"^```[ \t]*$")
MAX_REPORT = 1 << 20
MAX_BLOCK = 1 << 16
ALL_PASSED_RE = re.compile(r"\ball[ -]gates[ -](?:passed|pass|green)\b", re.I)
COUNT_RES = (re.compile(r"Ran (\d+) tests?"), re.compile(r"(\d+) passed"))
ZERO_RE = re.compile(r"Ran 0 tests|collected 0 items|no tests ran", re.I)
REQUIRED = ("files_changed", "gates", "stopped")


def scan_fences(text: str):
    """One pass over the lines. Return (closed blocks, malformed, body). `malformed` is True for an unclosed or nested
    claims fence; `body` is the text with every claims fence (an unclosed one to the end) removed."""
    blocks, body, cur, malformed = [], [], None, False
    for line in (text or "").split("\n"):
        if cur is None:
            if OPEN_RE.match(line):
                cur = []
            else:
                body.append(line)
        elif CLOSE_RE.match(line):
            blocks.append("\n".join(cur))
            cur = None
        elif OPEN_RE.match(line):
            malformed = True
        else:
            cur.append(line)
    if cur is not None:
        malformed = True
    return blocks, malformed, "\n".join(body)


def _grammar_ok(key: str, val: str) -> bool:
    """`none` is the explicit empty; an empty value is never valid."""
    if not val:
        return False
    if val.lower() == "none" and key != "stopped" or key == "stopped":
        return True
    if key == "files_changed":
        return all(p.strip() for p in val.split(","))
    rx = re.compile(r"^[^=;\s]+=\d+$")
    return all(rx.match(part.strip()) for part in val.split(";"))


def parse_block(block: str):
    """Return (kv dict, state): state is ok, unreadable (a required key missing) or malformed (duplicate recognised key
    or a recognised value that breaks its grammar)."""
    kv, bad = {}, False
    for line in block.splitlines():
        key, sep, val = line.partition(":")
        key = key.strip()
        if not sep or not key:
            continue
        if key in REQUIRED + ("tests",):
            bad = bad or key in kv
        kv[key] = val.strip() if key not in kv else kv[key]
    if bad:
        return kv, "malformed"
    if not all(k in kv for k in REQUIRED):
        return kv, "unreadable"
    keys = REQUIRED + (("tests",) if "tests" in kv else ())
    return kv, "ok" if all(_grammar_ok(k, kv[k]) for k in keys) else "malformed"


def _pairs(value: str) -> list[tuple[str, str]]:
    out = []
    for part in (value or "").split(";"):
        key, sep, val = part.strip().partition("=")
        if sep:
            out.append((key.strip(), val.strip()))
    return out


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _counts(excerpt: str) -> set[int]:
    found = {int(m) for rx in COUNT_RES for m in rx.findall(excerpt or "")}
    if ZERO_RE.search(excerpt or ""):
        found.add(0)
    return found


def _item(kind, claimed, observed, **extra) -> dict:
    return {"kind": kind, "claimed": claimed, "observed": observed, **extra}


def check(report: str, run: dict) -> dict:
    """Return {state, reason, unsupported, items, omitted, weak, unclaimed, stopped}. `stopped` is True when exactly one
    readable block declares a stop (the caller selects unverified delegate-stopped, never this check)."""
    result = {"state": "checked", "reason": None, "unsupported": 0, "items": [], "omitted": [], "weak": [],
              "unclaimed": [], "stopped": False, "not_checked": []}
    if len(report or "") > MAX_REPORT:
        result.update(state="not-checked", reason="claims-too-large")
        return result
    blocks, malformed, body = scan_fences(report)
    if malformed:
        result.update(state="not-checked", reason="claims-block-malformed")
        return result
    if any(len(b) > MAX_BLOCK for b in blocks):
        result.update(state="not-checked", reason="claims-too-large")
        return result
    n = len(blocks)
    if n > 1:
        result["items"].append(_item("claims-block", f"{n} blocks", "1 block allowed", reason="multiple-claims-blocks"))
        result["unsupported"] = 1
        return result
    if n == 0:
        result.update(state="not-checked", reason="claims-block-missing")
        return result
    block, status = parse_block(blocks[0])
    if status != "ok":
        result.update(state="not-checked", reason="claims-block-" + status)
        return result
    gates = {g.get("id"): g for g in run.get("gate_results") or []}
    items, weak = result["items"], result["weak"]
    changed = set(run.get("changed") or [])
    unproven = {p: "unreadable" for p in run.get("unreadable") or []}
    unproven.update({p: "unbaselined" for p in run.get("unbaselined") or [] if p not in unproven})
    files = [] if block["files_changed"].lower() == "none" else [p.strip() for p in block["files_changed"].split(",") if p.strip()]
    for path in files:
        if path in unproven and path not in changed:
            result["not_checked"].append(_item("file-changed", path, unproven[path]))
        elif path not in changed:
            items.append(_item("file-changed", path, "unchanged"))
    result["unclaimed"] = sorted(changed - set(files))
    claimed_gates = set()
    for gid, val in _pairs(block["gates"]):
        claimed_gates.add(gid)
        gate = gates.get(gid)
        if gate is None:
            items.append(_item("gate-result", f"{gid}={val}", "no such gate"))
        elif gate.get("rc") is None:
            items.append(_item("gate-result", f"{gid}={val}", "not-checked"))
        elif str(gate["rc"]) != val:
            items.append(_item("gate-result", f"{gid}={val}", f"rc={gate['rc']}"))
    result["omitted"] = [gid for gid in gates if gid not in claimed_gates]
    for gid, val in _pairs(block.get("tests", "")):
        gate = gates.get(gid)
        found = _counts(gate.get("excerpt", "")) if gate else set()
        if gate is None:
            items.append(_item("test-count", f"{gid}={val}", "no such gate"))
        elif not val.isdigit() or int(val) not in found:
            items.append(_item("test-count", f"{gid}={val}", ",".join(map(str, sorted(found))) or "none"))
        if val == "0" and gid in gates and gid not in weak:
            weak.append(gid)
    if ALL_PASSED_RE.search(body):
        bad = [f"{gid} {g.get('state')}" for gid, g in gates.items() if g.get("state") != "passed"]
        if bad:
            items.append(_item("all-gates-passed", "all gates passed", ", ".join(bad)))
        for gid, g in gates.items():
            if ZERO_RE.search(g.get("excerpt", "")) and gid not in weak:
                weak.append(gid)
    stop = block["stopped"]
    if stop.lower() != "none":
        result["stopped"] = True
        rule = _norm(run.get("stop_rule", ""))
        claimed = _norm(stop)
        if not (claimed == "s1" and rule or claimed == rule and rule):
            items.append(_item("stopped", stop, f"declared: {run.get('stop_rule') or 'none'}"))
    result["unsupported"] = len(items)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_claims.py <report_file> <run_json>", file=sys.stderr)
        return 2
    report = open(argv[0], encoding="utf-8", errors="replace").read()
    print(json.dumps(check(report, json.load(open(argv[1], encoding="utf-8"))), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
