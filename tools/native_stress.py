#!/usr/bin/env python3
"""Spec 038 T028: stress driver for a stateless guest agent type (gemini-flash) against a fake Gemini server.

Offline and $0: the fake server answers from the prompt text and counts every request. The driver stands in for the
mod's loop (native/loop.ts): it runs the real `agents-inc native` CLI for status, begin, step and end, runs the Bash
tools the reply asks for (wc -l only), appends their output and resends the whole conversation, as a stateless model
needs. Covered: session start sends no request (SC-006), the CLI, the provider call, ledger rows, events.jsonl, the
usage sum, parallel agents. Not covered: Claude Code itself, the mod's TS loop, permission prompts, the real model.

    python3 tools/native_stress.py [--src DIR] [--r N] [--scenarios "tools par steps5"]

Prints one row per run and `PASS n/m`; exit 0 only when every run passes. Uses a temp HOME and a fake key.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

NICK = "gemini-flash"
FILES = {"a.txt": 173, "b.txt": 95, "c.txt": 41, "d.txt": 7, "e.txt": 12}
TASKS = {"tools": [["a.txt", "b.txt"]], "par": [["a.txt"], ["b.txt"], ["c.txt"]], "steps5": [list(FILES)],
         "bigcat": [["a.txt", "b.txt"]], "flaky": [list(FILES)]}  # flaky: every 3rd request answers 429 and is retried  # bigcat: the same task behind the prompt of a real 77-tool session
GUEST_CORE = ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "NotebookEdit")  # mirrors GUEST_TOOLS in native/loop.ts


def session_catalog(n: int = 77, core_only: bool = True) -> str:
    """A catalog like a real session's: the core tools with long descriptions plus MCP, deferred and orchestration tools.
    core_only keeps what the loop offers a stateless guest agent; False is the whole list the host reports."""
    names = [*GUEST_CORE, "Agent", "Skill", "WebFetch", "WebSearch", "TodoWrite", "ToolSearch", "Monitor", "TaskStop"]
    names += [f"mcp__server{i % 6}__operation_{i}" for i in range(n - len(names))]
    keep = [x for x in names if x in GUEST_CORE] if core_only else names
    reps = lambda x: 14 if x in GUEST_CORE else 3 if x.startswith("mcp") else 12
    desc = "Does the thing it is named for; reads the arguments carefully. "
    arg = "arg: string, the value to use\n  " * 6
    return "\n".join(f"- {x}: " + desc * reps(x) + "\n  Arguments:\n  " + arg for x in keep)


def session_prefix(core_only: bool = True) -> str:
    return f"System prompt:\n{'s' * 7457}\n\nTools:\n{session_catalog(core_only=core_only)}\n\nConversation:\n{'c' * 14655}\n"
FAKE_KEY = "AIzaFAKE-stress-000000000000000000000000"


class Fake:
    """Answers like a model that runs `wc -l <file>` once per step for each file the task names, then reports."""

    def __init__(self, flaky: int = 0):
        self.count, self.lock, self.flaky = 0, threading.Lock(), flaky  # flaky=N: every Nth request answers 429
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                with fake.lock:
                    fake.count += 1
                    limited = bool(fake.flaky) and fake.count % fake.flaky == 0
                if limited:
                    raw = json.dumps({"error": {"message": "Rate limit exceeded"}}).encode()
                    self.send_response(429); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
                    return
                prompt = "\n".join(p.get("text", "") for c in body.get("contents", []) for p in c.get("parts", []))
                raw = json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(fake.answer(prompt))}]}}],
                                  "usageMetadata": {"promptTokenCount": len(prompt) // 4, "candidatesTokenCount": 9}}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

            def log_message(self, *a): pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    @staticmethod
    def answer(prompt: str) -> dict:
        m = re.search(r"TASK: count lines of (\S+)", prompt)
        if not m: return {"say": "reading", "tools": [{"name": "Read", "input": {"file_path": "probe.txt"}}]}  # the probe
        files, done = m.group(1).split(","), dict(re.findall(r"RESULT wc -l (\S+) -> (\d+)", prompt))
        todo = [f for f in files if f not in done]
        if todo: return {"say": f"counting {todo[0]}", "tools": [{"name": "Bash", "input": {"command": f"wc -l {todo[0]}"}}]}
        return {"say": " ".join(f"{f[0].upper()}={done[f]}" for f in files), "tools": []}


def cli(env, *args, stdin=None):
    return subprocess.run([sys.executable, "-m", "agents_inc.install.cli", *args], input=stdin, env=env,
                          capture_output=True, text=True, timeout=120)


def agent_run(env, work, session, agent, files, prefix="") -> tuple[str, dict, int, list[str]]:
    """One guest agent: begin, steps until a reply with no tools, end. Returns (say, usage, steps, problems)."""
    bad, usage, steps = [], {"input_tokens": 0, "output_tokens": 0}, 0
    ids = ["--model", NICK, "--cwd", str(work), "--session", session, "--agent", agent]
    if cli(env, "native", "begin", *ids, "--task", "count").returncode: bad.append("begin")
    prompt, say = f"{prefix}TASK: count lines of {','.join(files)}\n", ""
    for _ in range(len(files) + 2):
        r = cli(env, "native", "step", *ids, stdin=prompt); steps += 1
        if r.returncode: bad.append(f"step-exit:{r.returncode}"); break
        for line in r.stderr.splitlines():
            if line.startswith("agents-inc run: usage "):
                u = json.loads(line.split(" ", 3)[3]); usage = {k: usage[k] + int(u.get(k, 0)) for k in usage}
        reply = json.loads(r.stdout); say = reply.get("say", "")
        if not reply.get("tools"): break
        for t in reply["tools"]:
            cmd = t["input"]["command"].split()
            if t["name"] != "Bash" or cmd[:2] != ["wc", "-l"]: bad.append(f"tool:{t['name']}"); continue
            out = subprocess.run(cmd, cwd=work, capture_output=True, text=True).stdout.split()[0]
            prompt += f"ASSISTANT {json.dumps(reply)}\nRESULT wc -l {cmd[2]} -> {out}\n"
    outcome = "done" if not bad else "failed"
    if cli(env, "native", "end", *ids, "--outcome", outcome, "--usage", json.dumps(usage)).returncode: bad.append("end")
    return say, usage, steps, bad


def check_events(state: Path, session, agent, steps, usage) -> list[str]:
    path = state / "native-runs" / NICK / session / agent / "events.jsonl"
    try: ev = [json.loads(l)["event"] for l in path.read_text().splitlines()]
    except (OSError, ValueError): return ["events-missing"]
    bad = []
    if [e["type"] for e in ev] != ["run.start"] + ["step"] * steps + ["run.end"]: bad.append("events-order")
    total = {k: sum((e.get("usage") or {}).get(k, 0) for e in ev if e["type"] == "step") for k in usage}
    if total != usage or ev[-1].get("usage") != usage: bad.append("usage-sum")
    return bad


def one(src: Path, scenario: str, i: int) -> tuple[bool, str, float, int, int]:
    t0, fake = time.time(), Fake(3 if scenario == "flaky" else 0)
    with tempfile.TemporaryDirectory() as tmp:
        home, work = Path(tmp) / "home", Path(tmp) / "work"; work.mkdir(parents=True)
        for name, n in FILES.items(): (work / name).write_text("".join(f"{k}\n" for k in range(1, n + 1)))
        store = home / ".config" / "workerbees" / ".env"; store.parent.mkdir(parents=True)
        store.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n"); store.chmod(0o600)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "PYTHONPATH": str(src),
               "AGENTS_INC_NATIVE_GEMINI_URL": fake.url, "AGENTS_INC_NATIVE_RETRY_WAITS": "0.05,0.05,0.05"}
        bad = []
        if cli(env, "models", "probe", NICK).returncode: bad.append("probe")
        if cli(env, "native", "allow", "gemini", "--workspace", str(work)).returncode: bad.append("allow")
        before = fake.count
        st = cli(env, "native", "status", "--json", "--cwd", str(work))  # what the mod reads once at session start
        start_requests = fake.count - before
        if start_requests: bad.append(f"session-start-requests:{start_requests}")
        try: offered = any(m["nickname"] == NICK and m["offered"] for m in json.loads(st.stdout)["models"])
        except (ValueError, KeyError): offered = False
        if not offered: bad.append("not-offered")
        jobs = TASKS[scenario]
        with ThreadPoolExecutor(len(jobs)) as pool:
            runs = list(pool.map(lambda j: (j, agent_run(env, work, f"s{i}", f"a{j}", jobs[j], session_prefix() if scenario == "bigcat" else "")), range(len(jobs))))
        state = home / ".local" / "state" / "agents-inc"
        for j, (say, usage, steps, problems) in runs:
            bad += problems
            for f in jobs[j]:
                if f"{f[0].upper()}={FILES[f]}" not in say: bad.append(f"missing:{f[0].upper()}={FILES[f]}")
            if not state.is_dir(): state = next(home.rglob("native-runs")).parent
            bad += check_events(state, f"s{i}", f"a{j}", steps, usage)
        ledger = next(home.rglob("host-ledger/.workerbees/ledger.jsonl"), None)
        rows = [json.loads(l) for l in ledger.read_text().splitlines()] if ledger else []
        if sum(r.get("source") == "native-gemini" for r in rows) != 2 * len(jobs): bad.append("ledger-rows")
        if FAKE_KEY in "".join(p.read_text(errors="replace") for p in home.rglob("*") if p.is_file() and p != store):
            bad.append("key-leak")
    fake.server.shutdown(); fake.server.server_close()
    return not bad, " ".join(bad), time.time() - t0, start_requests, fake.count


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--r", type=int, default=int(os.environ.get("R", 10)))
    ap.add_argument("--scenarios", default=os.environ.get("SCENARIOS", "tools par steps5 bigcat flaky"))
    a = ap.parse_args(argv)
    passed = total = 0
    print(f"{'scenario':<8} {'run':<3} {'ok':<4} {'secs':>5} {'start':>5} {'reqs':>4} problems")
    for s in a.scenarios.split():
        if s not in TASKS: print(f"unknown scenario {s}", file=sys.stderr); return 2
        for i in range(1, a.r + 1):
            ok, why, secs, start, reqs = one(Path(a.src), s, i)
            passed += ok; total += 1
            print(f"{s:<8} {i:<3} {'yes' if ok else 'no':<4} {secs:5.1f} {start:>5} {reqs:>4} {why}", flush=True)
    print(f"PASS {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__": raise SystemExit(main())
