#!/usr/bin/env python3
"""Export one agents-inc dispatch run directory for the demo clip.

usage: export_run.py <run-dir> <out-dir>

Copies only what the scene reads and drops everything else. It never rewrites
a value: a field is either copied unchanged or left out.

- run.json   -> keeps run_id, model, kind, outcome, reason, rc, task_access and,
                per gate result, id, argv, state, rc, last_line.
- events.jsonl -> one line per event; keeps seq, ts, source and from the event:
                type, subtype, outcome, rc, model (run.start only: the alias),
                item.type, item.status, item.exit_code, item.command,
                item.text (agent_message only), and for Claude messages the
                list of content parts as type, tool name and text (text parts).
                Thinking text, tool inputs, tool results, session, thread,
                request and uuid ids, account, rate-limit and usage data,
                versions and working directories are not copied.
- stdout.md  -> copied as report.md unchanged.
Privacy rule: any kept string field, and the report, that contains the
current home directory path or the user name is left out whole.
Standard library only.
"""
import getpass
import json
import os
import shutil
import sys

HOME = os.path.expanduser("~")
USER = getpass.getuser()


def private(s):
    return isinstance(s, str) and (HOME in s or USER in s)


def put(dst, key, val):
    if val is None or private(val):
        return
    dst[key] = val


def export_run(src):
    out = {}
    for k in ("run_id", "model", "kind", "outcome", "reason", "rc", "task_access"):
        put(out, k, src.get(k))
    gates = []
    for g in src.get("gate_results") or []:
        d = {}
        for k in ("id", "state", "rc", "last_line"):
            put(d, k, g.get(k))
        if not any(private(a) for a in g.get("argv", [])):
            d["argv"] = g.get("argv")
        gates.append(d)
    out["gate_results"] = gates
    return out


def export_event(rec):
    ev = rec.get("event", {})
    o = {}
    for k in ("seq", "ts", "source"):
        put(o, k, rec.get(k))
    e = {}
    for k in ("type", "subtype", "outcome", "rc"):
        put(e, k, ev.get(k))
    if ev.get("type") == "run.start":
        put(e, "model", ev.get("model"))
    it = ev.get("item")
    if isinstance(it, dict):
        i = {}
        for k in ("type", "status", "exit_code", "command"):
            put(i, k, it.get(k))
        if it.get("type") == "agent_message":
            put(i, "text", it.get("text"))
        e["item"] = i
    msg = ev.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), list):
        parts = []
        for c in msg["content"]:
            p = {}
            put(p, "type", c.get("type"))
            put(p, "name", c.get("name"))
            if c.get("type") == "text":
                put(p, "text", c.get("text"))
            parts.append(p)
        e["parts"] = parts
    o["event"] = e
    return o


def main(argv):
    if len(argv) != 3:
        print(__doc__.splitlines()[2], file=sys.stderr)
        return 2
    src, dst = argv[1], argv[2]
    os.makedirs(dst, exist_ok=True)
    with open(os.path.join(src, "run.json"), encoding="utf-8") as f:
        run = json.load(f)
    with open(os.path.join(dst, "run.json"), "w", encoding="utf-8") as f:
        json.dump(export_run(run), f, indent=1)
        f.write("\n")
    with open(os.path.join(src, "events.jsonl"), encoding="utf-8") as f, \
            open(os.path.join(dst, "events.jsonl"), "w", encoding="utf-8") as g:
        for line in f:
            if line.strip():
                g.write(json.dumps(export_event(json.loads(line))) + "\n")
    rep = os.path.join(src, "stdout.md")
    if os.path.exists(rep):
        with open(rep, encoding="utf-8") as f:
            text = f.read()
        if private(text):
            print("report left out: holds a private path", file=sys.stderr)
        else:
            shutil.copyfile(rep, os.path.join(dst, "report.md"))
    print("exported %s -> %s" % (os.path.basename(src.rstrip("/")), dst))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
