"""Runner for the opus-orchestrated terminal demo of agents-inc (spec 030).

Prepares a fresh trial directory under .scratch/demo-030/<UTC stamp>/trial/, writes two slots
files and the paste prompt, prints the beat checklist, then starts `claude --model opus` under
`asciinema rec` when asciinema is installed. Standard library only.

Exit codes: 0 ok, 2 doctor not READY, 3 setup error.
"""
import argparse
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_SPEC = Path("fixtures") / "build-test-verify" / "S" / "SPEC.md"
BEAT6_RE = re.compile(r"<!-- BEAT6-TEXT-BEGIN -->(.*?)<!-- BEAT6-TEXT-END -->", re.S)
PLACEHOLDER_RE = re.compile(r"\{[A-Z_0-9]+\}")
KEY_MIN_BYTES = 20  # mask.sh rejects keys shorter than 20 characters

# provider -> (env vars, key files relative to home)
FREE_KEYS = {
    "mistral": (("MISTRAL_API_KEY",), (".config/devstral/api_key",)),
    "gemini": (("GEMINI_API_KEY", "GOOGLE_API_KEY"), (".codex-bridge/gemini-key",)),
    "openrouter": (("OPENROUTER_API_KEY",), (".codex-bridge/openrouter-key",)),
}
SHARED_ENV_FILE = "Projects/.env"  # existence only; never read

ASCIINEMA_NOTE = "NOTE: asciinema not installed -> running without recording (brew install asciinema agg)"
AGG_NOTE = "NOTE: agg not installed -> cast kept, no GIF"
SANDBOX_ASK = 'add "agents-inc *" to sandbox.excludedCommands'


class SetupError(Exception):
    """Raised for a problem that stops the run with exit code 3."""


def default_doctor_text():
    """Run `agents-inc doctor` and return its stdout; empty text when the launcher is missing."""
    try:
        done = subprocess.run(["agents-inc", "doctor"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout


def parse_doctor(text):
    """Pull readiness, the luna type and the warning codes out of `agents-inc doctor` output."""
    lines = [line.strip() for line in (text or "").splitlines()]
    luna = "unavailable"
    warnings = []
    for line in lines:
        if line.startswith("luna type:"):
            words = line.split(":", 1)[1].split()
            luna = words[0] if words else "unavailable"
        elif line.startswith("WARNING:"):
            warnings.append(line.split(":", 1)[1].strip())
    return {
        "ready": "READY" in lines,
        "first_line": lines[0] if lines and lines[0] else "no output from agents-inc doctor",
        "luna_type": luna,
        "warnings": warnings,
    }


def free_key_status(environ=None, home=None):
    """Report yes, maybe or no per free provider without reading any key value.

    Uses only environ lookups, os.path.exists and os.path.getsize.
    """
    environ = os.environ if environ is None else environ
    home = os.path.expanduser("~") if home is None else home
    shared = os.path.exists(os.path.join(home, SHARED_ENV_FILE))
    result = {}
    for provider, (env_names, files) in FREE_KEYS.items():
        status = "no"
        if any(environ.get(name) for name in env_names):
            status = "yes"
        else:
            for rel in files:
                path = os.path.join(home, rel)
                if os.path.exists(path):
                    status = "yes" if os.path.getsize(path) >= KEY_MIN_BYTES else "maybe"
                    break
            else:
                if shared:
                    status = "maybe"  # the key may live only in the shared env file
        result[provider] = status
    return result


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_run_dir(root):
    """Create .scratch/demo-030/<stamp>/ and return it; a same-second repeat gets a suffix."""
    base = Path(root) / ".scratch" / "demo-030"
    base.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    run_dir = base / stamp
    n = 0
    while True:
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            n += 1
            run_dir = base / f"{stamp}-{n}"


def setup_trial(root, run_dir, copy=shutil.copy):
    """Create trial/ holding only SPEC.md and assert that no `hidden` path sits under it."""
    spec = Path(root) / FIXTURE_SPEC
    if not spec.is_file():
        raise SetupError(f"fixture spec not found: {spec}")
    trial = run_dir / "trial"
    trial.mkdir()
    copy(spec, trial / "SPEC.md")
    leaked = [str(p) for p in trial.rglob("*") if p.name == "hidden"]
    if leaked:
        raise SetupError(f"hidden path found under trial dir: {leaked}")
    return trial


def build_slots(model, role,task, constraints, out_of_scope, files, stop_rule,
                success_gate, failure_gate, gates):
    return {
        "MODEL": model,
        "ROLE": role,
        "TASK": task,
        "CONSTRAINTS": constraints,
        "OUT_OF_SCOPE": out_of_scope,
        "FILES_IN_SCOPE": files,
        "STOP_RULE": stop_rule,
        "SUCCESS_GATE": success_gate,
        "FAILURE_GATE": failure_gate,
        "GATES": gates,
    }


def write_slots(run_dir, stamp_name, build_model):
    """Write slots-build.json and slots-review.json; return their paths."""
    rel = f".scratch/demo-030/{stamp_name}/trial"
    no_peek = ("Do not read anything under fixtures/ or .scratch/bench-*, and nothing else in .scratch/ "
               "outside this trial directory.")
    build = build_slots(
        build_model,
        role=f"Grunt builder. Build the csv2json tool described in the spec, inside {rel} only.",
        task=(f"Read {rel}/SPEC.md. Write only {rel}/csv2json.py, the tool it describes. "
              "No tests and no other files; the supervisor verifies it."),
        constraints=(f"Write only inside {rel}. Python 3.10+ standard library only. {no_peek} "
                     "No network. No git commands. Do not edit SPEC.md."),
        out_of_scope=f"Any file outside {rel}. Tests. Installing packages. Editing SPEC.md.",
        files=[f"{rel}/csv2json.py"],
        stop_rule="Stop after 10 tool calls, or once csv2json.py is written, whichever comes first.",
        success_gate=f"`test -s csv2json.py` run in {rel} exits 0.",
        failure_gate=f"`test -s csv2json.py` run in {rel} exits 1, because csv2json.py is missing or empty.",
        gates=[{"argv": ["test", "-s", "csv2json.py"], "cwd": rel, "timeout_s": 30, "expect_rc": 0}],
    )
    review = build_slots(
        "haiku",
        role=f"Grunt reviewer. Review the csv2json build in {rel}. Read-only on code.",
        task=(f"Read {rel}/csv2json.py, the tests under {rel}/tests and {rel}/VERIFICATION.md. Write "
              f"{rel}/REVIEW.md: for each requirement R1 to R6 in {rel}/SPEC.md say covered or not "
              "covered, cite the test name, and list any claim in VERIFICATION.md you could not "
              "confirm from the files."),
        constraints=(f"Write only {rel}/REVIEW.md. Do not change any other file. {no_peek} "
                     "No network. No git commands."),
        out_of_scope=f"Any file other than {rel}/REVIEW.md. Fixing the code.",
        files=[f"{rel}/REVIEW.md"],
        stop_rule="Stop after 15 tool calls, or once REVIEW.md is written, whichever comes first.",
        success_gate=f"`test -s REVIEW.md` run in {rel} exits 0.",
        failure_gate=f"`test -s REVIEW.md` run in {rel} exits 1, because REVIEW.md is missing or empty.",
        gates=[{"argv": ["test", "-s", "REVIEW.md"], "cwd": rel, "timeout_s": 30, "expect_rc": 0}],
    )
    paths = {}
    for name, slots in (("slots-build.json", build), ("slots-review.json", review)):
        path = run_dir / name
        path.write_text(json.dumps(slots, indent=2) + "\n")
        paths[name] = path
    return paths["slots-build.json"], paths["slots-review.json"]


def render_prompt(template, values, beat6):
    """Substitute the placeholders in PROMPT.md and return the prompt text.

    The BEAT6 block is cut out of the template; `beat6` replaces {BEAT6}. Raises SetupError when
    a placeholder or a NEEDS marker is left over.
    """
    match = BEAT6_RE.search(template)
    if not match:
        raise SetupError("PROMPT.md has no BEAT6-TEXT block")
    ready_text = match.group(1).strip()
    body = BEAT6_RE.sub("", template)
    body = re.sub(r"<!--.*?-->\s*", "", body, flags=re.S)  # provenance and marker comments
    body = body.replace("{BEAT6}", ready_text if beat6 is None else beat6)
    for key, value in values.items():
        body = body.replace("{" + key + "}", value)
    left = PLACEHOLDER_RE.findall(body)
    if left:
        raise SetupError(f"unreplaced placeholder in prompt: {sorted(set(left))}")
    if "NEEDS" in body:
        raise SetupError("NEEDS marker left in prompt")
    return body.strip() + "\n"


def default_launch(cmd):
    return subprocess.call(cmd)


def main(argv=None, doctor_text=None, which=None, launch=None, copy=shutil.copy):
    """Run the demo setup. `doctor_text`, `which`, `launch` and `copy` are injectable for tests."""
    parser = argparse.ArgumentParser(description="Opus terminal demo of agents-inc (spec 030).")
    parser.add_argument("--dry-run", action="store_true",
                        help="write the folder and print the prompt; start nothing")
    parser.add_argument("--no-record", action="store_true", help="skip asciinema; run claude directly")
    parser.add_argument("--root", default=".", help="repo root (default: current directory)")
    args = parser.parse_args(argv)
    which = which or shutil.which
    launch = launch or default_launch
    root = Path(args.root).resolve()

    # Step 1: doctor. Not READY stops here, before anything is written.
    doctor = parse_doctor(default_doctor_text() if doctor_text is None else doctor_text)
    if not doctor["ready"]:
        print(f"doctor: {doctor['first_line']}")
        print("agents-inc doctor is not READY; fix it (agents-inc repair --source <agents-inc checkout>) "
              "and run again.")
        return 2
    mod_installed = "MOD_NOT_INSTALLED" not in doctor["warnings"]
    sandbox_ok = "WB_SANDBOX_EXCLUDE_MISSING" not in doctor["warnings"]
    print(f"doctor: READY; luna type: {doctor['luna_type']}")
    if not sandbox_ok:
        print(f"ASK: {SANDBOX_ASK}")

    # Steps 2-3: codex, free keys.
    codex = which("codex") is not None
    free = free_key_status()
    print("free: " + " ".join(f"{p}={free[p]}" for p in ("mistral", "gemini", "openrouter")))

    # Degradation (US3): no codex, or luna type not ready.
    build_model = "luna"
    beat6 = None
    if not codex:
        build_model = "haiku"
        print("NOTE: codex absent -> haiku (build and review share a model)")
        beat6 = "SKIP: luna type not offered (codex absent)"
    elif doctor["luna_type"] != "ready":
        build_model = "haiku"
        print(f"NOTE: luna type {doctor['luna_type']} -> haiku (build and review share a model)")
        beat6 = f"SKIP: luna type not offered (luna type: {doctor['luna_type']})"
    if not mod_installed:
        print("NOTE: agents-inc mod not installed -> beats 2 and 3 use the plain-dispatch fallback")
        beat6 = "SKIP: agents-inc mod not installed (beats 2 and 3 use the plain-dispatch fallback)"

    # Step 4-6: run dir, trial, slots, prompt.
    template_path = HERE / "PROMPT.md"
    try:
        template = template_path.read_text()
    except OSError as exc:
        print(f"setup error: cannot read {template_path}: {exc}")
        return 3
    try:
        if not (root / FIXTURE_SPEC).is_file():
            raise SetupError(f"fixture spec not found: {root / FIXTURE_SPEC}")
        run_dir = make_run_dir(root)
        trial = setup_trial(root, run_dir, copy=copy)
        slots_build, slots_review = write_slots(run_dir, run_dir.name, build_model)
        values = {
            "TRIAL": str(trial),
            "SLOTS_BUILD": str(slots_build),
            "SLOTS_REVIEW": str(slots_review),
            "BUILD_MODEL": build_model,
            "FREE_STATUS": " ".join(f"{p}={free[p]}" for p in ("mistral", "gemini", "openrouter")),
        }
        prompt = render_prompt(template, values, beat6)
    except (SetupError, OSError) as exc:
        print(f"setup error: {exc}")
        return 3
    (run_dir / "prompt.txt").write_text(prompt)

    meta = {
        "stamp": run_dir.name,
        "doctor_ready": True,
        "luna_type": doctor["luna_type"],
        "codex": codex,
        "mod_installed": mod_installed,
        "sandbox_exclude_ok": sandbox_ok,
        "free": free,
        "build_model": build_model,
        "recorded": False,
        "cast": None,
        "gif": None,
        "beat_seconds": {},  # the first real run fills this in
    }
    demo_json = run_dir / "demo.json"

    def save_meta():
        demo_json.write_text(json.dumps(meta, indent=2) + "\n")

    save_meta()

    print(f"run dir: {run_dir}")
    print("beat checklist: 1 routing, 2 build, 3 verify and ledger")
    print("--- prompt (also saved as prompt.txt) ---")
    print(prompt)
    print("--- end prompt ---")

    # Step 7: recording and launch.
    record = not args.no_record
    have_asciinema = which("asciinema") is not None
    if record and not have_asciinema:
        print(ASCIINEMA_NOTE)
    if args.dry_run:
        return 0

    claude_cmd = ["claude", "--model", "opus", prompt]  # positional prompt: the session starts on it, no paste
    os.chdir(root)  # launch from the repo root so the slots files sit inside the session cwd
    if record and have_asciinema:
        cast = run_dir / "demo.cast"
        launch(["asciinema", "rec", str(cast), "--command", shlex.join(claude_cmd)])
        meta.update(recorded=True, cast=str(cast))
        if which("agg") is None:
            print(AGG_NOTE)
        else:
            gif = run_dir / "demo.gif"
            launch(["agg", str(cast), str(gif)])
            meta["gif"] = str(gif)
    else:
        launch(claude_cmd)
    save_meta()
    return 0


if __name__ == "__main__":
    sys.exit(main())
