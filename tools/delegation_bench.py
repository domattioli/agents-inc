"""Token savings bench: the same build-test-verify task with and without agents-inc.

See docs/proposals/delegation-savings-test.md. Each trial: fresh empty git dir holding only SPEC.md, a fresh
`claude -p` session under one arm's isolated HOME, then the hidden acceptance script. One JSON row per trial.

Arms
  A0  no agents-inc, Agent/Task disallowed (session does everything itself)
  A1  no agents-inc, native Agent allowed (host's own delegation)
  B   agents-inc installed, agent gate advisory
  C   agents-inc installed, agent gate enforce
  Acheap  as A0 but the session model is sonnet
  Bcheap  as B but the session model is sonnet (cheap supervisor, cheap delegates)

Usage:
  python3 tools/delegation_bench.py --size S --arms A0,A1,B,C --n 1 --out <dir>
  python3 tools/delegation_bench.py --rollup <dir>
Auth: each arm runs `claude -p` under an isolated HOME, so Keychain auth (macOS interactive login) is not
visible to the trial. Set CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) or ANTHROPIC_API_KEY in the calling
environment; those two survive the CLAUDE* scrub. Each arm HOME also gets a `claude` shim on PATH that re-exports
CLAUDE_CODE_OAUTH_TOKEN from `<home>/.bench-oauth` (mode 0600, written from the calling env, removed when absent):
without it a delegate started from the trial's Bash tool runs with no login. A preflight (`claude auth status` under
the trial env) runs once per arm before its first trial; skip it with --no-auth-check.

Sandbox: the harness launches `claude -p` and `agents-inc` itself, so the repo's sandbox.excludedCommands entry
`agents-inc *` does not cover it. Either add `python3 tools/delegation_bench.py *` to sandbox.excludedCommands or
run it from a plain terminal (agents-inc dispatch exits 69 inside the sandbox).
"""
from __future__ import annotations

import argparse, json, os, shlex, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agents_inc.install.dispatch import claude_usage, CLAUDE_MODELS  # noqa: E402

FIX = ROOT / "fixtures" / "build-test-verify"
ARMS = ("A0", "A1", "B", "C", "Acheap", "Bcheap")
AGENTS_INC_ARMS = ("B", "C", "Bcheap")
SONNET_ARMS = ("Acheap", "Bcheap")
SCRUB = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDECODE",
         "CLAUDE_PID", "CLAUDE_CODE_ENTRYPOINT", "SANDBOX_RUNTIME")
KEEP = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")   # headless auth; survive the CLAUDE* scrub
AUTH_FIX = ("claude not logged in under the trial HOME: run `claude setup-token` and export CLAUDE_CODE_OAUTH_TOKEN "
            "(or ANTHROPIC_API_KEY) before running the bench, or pass --no-auth-check")
BASE_PROMPT = ("Read SPEC.md in the current directory and deliver everything it asks for, in this directory. "
               "Work unattended: there is no one to answer questions, so state any assumption in VERIFICATION.md. "
               "Do not edit SPEC.md.")
LADDER = " opus, sonnet, haiku."


def arm_home(out: Path, arm: str) -> Path:
    """One isolated HOME per arm, built once. B and C get agents-inc installed with their gate."""
    home = out / "homes" / arm
    marker = home / ".bench-ready"
    if marker.exists():
        install_shim(home)      # token may have changed since the arm was built
        return home
    home.mkdir(parents=True, exist_ok=True)
    install_shim(home)
    if arm in AGENTS_INC_ARMS:
        env = dict(os.environ, HOME=str(home))
        launcher = home / ".local/bin/agents-inc"
        try:
            subprocess.run([shutil.which("agents-inc") or "agents-inc", "install", "--without-codex", "--source", str(ROOT)],
                           env=env, check=True, capture_output=True, text=True)
            subprocess.run([str(launcher), "repair", "--agent-gate", "enforce" if arm == "C" else "advisory"],
                           env=env, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            log = home / "install.log"
            log.write_text(f"$ {' '.join(map(str, e.cmd))}\nexit {e.returncode}\n--- stdout ---\n{e.stdout or ''}"
                           f"\n--- stderr ---\n{e.stderr or ''}\n")
            tail = "\n".join((e.stderr or "").strip().splitlines()[-5:])
            raise SystemExit(f"arm {arm}: {e.cmd[1]} exited {e.returncode}; full output in {log}\n{tail}")
        doctor = subprocess.run([str(launcher), "doctor"], env=env, capture_output=True, text=True)
        if not doctor.stdout.startswith("READY"):
            raise SystemExit(f"arm {arm}: doctor not READY:\n{doctor.stdout}{doctor.stderr}")
    marker.write_text("ok")
    return home


def trial_env(home: Path) -> dict:
    # Drop every CLAUDE_* variable: the calling host's flags (auto background tasks, effort, remote-session
    # wiring) otherwise leak into the trial and add ~25k tokens of host context. KEEP carries headless auth:
    # the fake HOME cannot see the macOS Keychain login.
    env = {k: v for k, v in os.environ.items() if k in KEEP or (k not in SCRUB and not k.startswith("CLAUDE"))}
    env["HOME"] = str(home)
    env["PATH"] = f"{home / '.local/bin'}:{env.get('PATH', '')}"
    env.setdefault("AGENTS_INC_TURN_TIMEOUT_S", "1800")
    return env


SHIM = """#!/bin/sh
# delegation bench: every `claude` under this HOME (trial, native subagent, agents-inc delegate) logs in with the
# operator's setup-token. A delegate launched from a trial's Bash tool otherwise prints `Not logged in`: the fake
# HOME has no Keychain login and CLAUDE_CODE_OAUTH_TOKEN does not survive into the command's environment.
if [ -z "$CLAUDE_CODE_OAUTH_TOKEN" ] && [ -r "$HOME/.bench-oauth" ]; then
  CLAUDE_CODE_OAUTH_TOKEN=$(cat "$HOME/.bench-oauth"); export CLAUDE_CODE_OAUTH_TOKEN
fi
exec {real} "$@"
"""


def install_shim(home: Path) -> None:
    """`<home>/.local/bin/claude`: re-exports the token from `<home>/.bench-oauth` (mode 0600), then execs the
    real claude. The token file is written only when the calling env carries CLAUDE_CODE_OAUTH_TOKEN, and removed
    when it does not. Nothing prints or logs the value."""
    real = next((p for p in (shutil.which("claude", path=d) for d in os.environ.get("PATH", "").split(os.pathsep))
                 if p and not p.startswith(str(home))), None)
    if not real:
        raise SystemExit("claude not on PATH")
    shim = home / ".local" / "bin" / "claude"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(SHIM.format(real=shlex.quote(real)))
    shim.chmod(0o755)
    tok = home / ".bench-oauth"
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        fd = os.open(tok, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(token)
        tok.chmod(0o600)
    elif tok.exists():
        tok.unlink()


_AUTH_OK: set = set()


def auth_preflight(home: Path, arm: str) -> None:
    """Once per arm: `claude auth status` under the trial env must report loggedIn true, else SystemExit."""
    if arm in _AUTH_OK:
        return
    p = subprocess.run(["claude", "auth", "status"], env=trial_env(home), capture_output=True, text=True)
    try:
        logged_in = bool(json.loads(p.stdout).get("loggedIn"))
    except (ValueError, AttributeError):
        logged_in = '"loggedIn": true' in p.stdout or "loggedIn: true" in p.stdout
    if not logged_in:
        raise SystemExit(f"arm {arm}: {AUTH_FIX}\nclaude auth status (rc {p.returncode}): {p.stdout.strip()[-300:]}")
    _AUTH_OK.add(arm)


def dispatch_usage(home: Path, since: float) -> list[dict]:
    runs = home / ".local/state/agents-inc/dispatch-runs"
    rows = []
    for f in sorted(runs.glob("*/usage.json")) if runs.is_dir() else []:
        if f.stat().st_mtime >= since:
            with_id = json.loads(f.read_text())
            with_id["run_id"] = f.parent.name
            rows.append(with_id)
    return rows


def run_trial(out: Path, size: str, arm: str, rep: int, timeout: int, auth_check: bool = True) -> dict:
    tid = f"{size}-{arm}-{rep}"
    work = out / "trials" / tid / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(FIX / size / "SPEC.md", work / "SPEC.md")
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    # dispatch's scope snapshot needs a HEAD; an empty repo fails it with "ambiguous argument 'HEAD'"
    subprocess.run(["git", "add", "SPEC.md"], cwd=work, check=True)
    subprocess.run(["git", "-c", "user.name=bench", "-c", "user.email=bench@localhost", "commit", "-q", "-m", "fixture"],
                   cwd=work, check=True)
    home = arm_home(out, arm)
    if auth_check:
        auth_preflight(home, arm)
    model = CLAUDE_MODELS["sonnet" if arm in SONNET_ARMS else "opus"]
    argv = ["claude", "-p", "--model", model, "--output-format", "json", "--permission-mode", "bypassPermissions"]
    if arm in ("A0", "Acheap"):
        argv += ["--disallowedTools", "Agent", "Task"]
    prompt = BASE_PROMPT + (LADDER if arm in AGENTS_INC_ARMS else "")
    argv += ["--", prompt]
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=work, env=trial_env(home), capture_output=True, text=True, timeout=timeout)
        rc, stdout, stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = 124, e.stdout or "", "timeout"
    seconds = round(time.time() - t0, 1)
    (work.parent / "session.json").write_text(stdout if isinstance(stdout, str) else stdout.decode())
    (work.parent / "stderr.txt").write_text(stderr if isinstance(stderr, str) else stderr.decode())
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        data = {}
    session = claude_usage(data)
    delegates = dispatch_usage(home, t0)
    acc = subprocess.run([sys.executable, "-I", str(FIX / size / "hidden" / "acceptance.py"), str(work)],
                         capture_output=True, text=True, timeout=600)
    try:
        acceptance = json.loads(acc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        acceptance = {"error": acc.stderr[-500:]}
    row = {"trial": tid, "size": size, "arm": arm, "rep": rep, "session_model": model, "claude_version": version,
           "rc": rc, "is_error": data.get("is_error"), "seconds": seconds, "accepted": acc.returncode == 0,
           "acceptance": acceptance, "session_usage": session, "delegate_usage": delegates,
           "subagent_stats": data.get("subagent_stats"), "totals": totals(session, delegates)}
    (work.parent / "row.json").write_text(json.dumps(row, indent=1))
    with (out / "rows.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def totals(session: dict | None, delegates: list[dict]) -> dict:
    """Per-model token sums over the session (incl. native subagents) and every agents-inc delegate."""
    per: dict[str, dict] = {}
    for u in ([session] if session else []) + delegates:
        for m, v in (u.get("models") or {}).items():
            acc = per.setdefault(m, {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0, "cost_usd": 0.0})
            for k in acc:
                acc[k] += v.get(k) or 0
    all_ = {k: sum(v[k] for v in per.values()) for k in ("input_tokens", "output_tokens", "cache_read", "cache_write", "cost_usd")}
    all_["cost_usd"] = round(all_["cost_usd"], 4)
    return {"all": all_, "by_model": per}


def rollup(out: Path) -> str:
    rows = [json.loads(l) for l in (out / "rows.jsonl").read_text().splitlines() if l.strip()]
    lines = ["| trial | arm | accepted | cases | traps | false accept | input | output | cache read | cache write | list-price USD (quota proxy) | seconds | turns (session+delegates) | agents-inc dispatches | native subagents |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        a, t = r["acceptance"], r["totals"]["all"]
        sub = (r.get("subagent_stats") or {}).get("spawned")
        turns = sum((u or {}).get("num_turns") or 0 for u in [r.get("session_usage")] + list(r["delegate_usage"]))
        lines.append(f"| {r['trial']} | {r['arm']} | {r['accepted']} | {a.get('passed')}/{a.get('total')} | "
                     f"{a.get('traps_passed')}/{a.get('traps')} | {a.get('false_accept')} | {t['input_tokens']:,} | "
                     f"{t['output_tokens']:,} | {t['cache_read']:,} | {t['cache_write']:,} | {t['cost_usd']} | "
                     f"{r['seconds']} | {turns} | {len(r['delegate_usage'])} | {sub} |")
    lines += ["", "By model:", ""]
    for r in rows:
        bm = ", ".join(f"{m}: in {v['input_tokens']:,} out {v['output_tokens']:,} cr {v['cache_read']:,} cw {v['cache_write']:,}"
                       for m, v in r["totals"]["by_model"].items())
        lines.append(f"- {r['trial']}: {bm}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="S")
    ap.add_argument("--arms", default="A0,A1,B,C")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--rollup", type=Path)
    ap.add_argument("--no-auth-check", action="store_true",
                    help="skip the per-arm `claude auth status` preflight under the trial HOME")
    a = ap.parse_args()
    if a.rollup:
        print(rollup(a.rollup)); return
    if not a.out:
        raise SystemExit("--out is required")
    a.out = a.out.resolve()         # arm HOMEs live under it; agents-inc install refuses a relative HOME
    arms = [x for x in a.arms.split(",") if x]
    bad = [x for x in arms if x not in ARMS]
    if bad:
        raise SystemExit(f"unknown arm(s): {bad}")
    a.out.mkdir(parents=True, exist_ok=True)
    for rep in range(a.n):          # interleave arms within each rep
        for arm in arms:
            r = run_trial(a.out, a.size, arm, rep, a.timeout, auth_check=not a.no_auth_check)
            print(json.dumps({k: r[k] for k in ("trial", "rc", "accepted", "seconds")} | {"tokens": r["totals"]["all"]}), flush=True)
    print(rollup(a.out))


if __name__ == "__main__":
    main()
