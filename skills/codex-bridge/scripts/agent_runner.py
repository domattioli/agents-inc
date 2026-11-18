#!/usr/bin/env python3
"""Small, local job runner for the Codex Bridge delegation legs.

Jobs are deliberately file-backed rather than service-backed: they survive the calling
shell, are inspectable with ordinary tools, and never require a daemon or credentials in
their metadata.  Provider calls stay in the existing wrapper scripts.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = Path(os.environ.get("CODEX_BRIDGE_SCRIPTS_DIR", SCRIPT_DIR))
STATE_DIR = Path(
    os.environ.get("CODEX_BRIDGE_AGENT_STATE_DIR", Path.home() / ".codex-bridge" / "agents")
)
# spec-010 (persistent Exec/Super session across a mandate): per-mandate JSON records live
# under STATE_DIR/mandates/<run_id>.json. See specs/010-persistent-exec-session/data-model.md.
MANDATE_DIR = STATE_DIR / "mandates"
# FR-005a / contracts C2a: `mandate close --by` allowlist. Roster is deliberately narrow and
# operator-unconfirmed -- widen only by an operator-signed edit here AND in contracts C2a.
ALLOWED_CLOSERS = {"ceo", "lead"}
MODE = os.environ.get("CODEX_BRIDGE_MODE", "standard")
VALID_MODES = {"standard", "budget", "ultra"}
ANTHROPIC = {"haiku", "sonnet", "opus", "fable", "anthropic"}
CANONICAL = {
    "gemini": "gemini-flash",
    "gemini-flash": "gemini-flash",
    "gemini-lite": "gemini-flash-lite",
    "gemini-flash-lite": "gemini-flash-lite",
    "gemini-deep": "gemini-deep",
    "mistral": "mistral",
    "openrouter": "openrouter",
    "codex": "codex",
    "ask": "codex",
}
TERMINAL = {"returned", "verified", "needs-review", "failed", "interrupted", "cancelled"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def die(message: str, code: int = 2) -> None:
    print(f"agent: {message}", file=sys.stderr)
    raise SystemExit(code)


def ensure_mode() -> None:
    if MODE not in VALID_MODES:
        die("invalid CODEX_BRIDGE_MODE: " + MODE + " (accepted values: standard, budget, ultra)")


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(STATE_DIR, 0o700)
    except OSError:
        pass


def job_dir(job_id: str) -> Path:
    if not job_id or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in job_id):
        die("invalid job id")
    return STATE_DIR / job_id


def metadata_path(job_id: str) -> Path:
    return job_dir(job_id) / "job.json"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def read_job(job_id: str) -> dict[str, Any]:
    path = metadata_path(job_id)
    try:
        with path.open(encoding="utf-8") as handle:
            job = json.load(handle)
    except FileNotFoundError:
        die(f"job not found: {job_id}", 1)
    except (OSError, json.JSONDecodeError) as error:
        die(f"cannot read job {job_id}: {error}", 1)
    if not isinstance(job, dict):
        die(f"invalid job metadata: {job_id}", 1)
    return job


def save_job(job: dict[str, Any]) -> None:
    write_json(metadata_path(job["id"]), job)


def write_artifact(job: dict[str, Any]) -> None:
    """Publish a stable, provider-neutral terminal record for external consumers.

    A supervisor may translate or summarize this record later.  The runner never
    invokes a translator itself, which preserves ultra mode's provider boundary.
    """
    directory = job_dir(job["id"])
    payload = {
        "schema": "codex-bridge-agent-result-v1",
        "job_id": job["id"],
        "parent_id": job.get("parent_id"),
        "backend": job.get("backend"),
        "task_class": job.get("task_class"),
        "status": job.get("status"),
        "attempt": job.get("attempt"),
        "exit_code": job.get("exit_code"),
        "completed_at": job.get("finished_at"),
        "error": job.get("error"),
        "output_path": str(directory / "result.txt"),
        "stderr_path": str(directory / "stderr.txt"),
    }
    # contracts C1: these keys are written ONLY under a mandate (FR-012 backward compat --
    # a non-mandate submit's result.json is unchanged from today).
    if job.get("mandate"):
        payload.update({
            "mandate": job["mandate"],
            "role": job.get("role"),
            "mode": job.get("mode"),
            "thread_id": job.get("thread_id"),
            "prior_engagement": job.get("prior_engagement"),
            "prompt": job.get("prompt"),
        })
    write_json(directory / "result.json", payload)


# ---------------------------------------------------------------------------
# spec-010: mandate store (FR-009, data-model.md).
# ---------------------------------------------------------------------------


def actor_id() -> str:
    return os.environ.get("CODEX_BRIDGE_ACTOR") or os.environ.get("USER") or "unknown"


def _repo_root() -> Path | None:
    """Resolve the repo root for FR-015's containment guard (contracts C7).

    Primary: `git rev-parse --show-toplevel` from the directory holding this file.
    Fallback: nearest ancestor of this file containing a `.git` entry.
    Neither resolves -> None (the repo-root clause of the guard is skipped).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(SCRIPT_DIR),
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    current = Path(__file__).resolve()
    for ancestor in (current, *current.parents):
        if (ancestor / ".git").exists():
            return ancestor.resolve()
    return None


def ensure_state_dir_containment() -> None:
    """FR-015 / contracts C7: refuse a mandate state dir inside the repo or ~/.claude."""
    resolved_state_dir = STATE_DIR.resolve()
    home_claude = (Path.home() / ".claude").resolve()
    repo_root = _repo_root()
    inside_repo = repo_root is not None and (
        resolved_state_dir == repo_root or resolved_state_dir.is_relative_to(repo_root)
    )
    inside_claude = resolved_state_dir == home_claude or resolved_state_dir.is_relative_to(home_claude)
    if inside_repo or inside_claude:
        die("mandate state dir must be outside the repo and outside ~/.claude", 2)


def ensure_mandate_dir() -> None:
    ensure_state_dir_containment()
    MANDATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(MANDATE_DIR, 0o700)
    except OSError:
        pass


def mandate_path(run_id: str) -> Path:
    if not run_id or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in run_id.lower()):
        die("invalid mandate id")
    return MANDATE_DIR / f"{run_id}.json"


def load_mandate(run_id: str) -> dict[str, Any] | None:
    ensure_mandate_dir()
    path = mandate_path(run_id)
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        die(f"cannot read mandate {run_id}: {error}", 1)


def save_mandate(mandate: dict[str, Any]) -> None:
    ensure_mandate_dir()
    path = mandate_path(mandate["run_id"])
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(mandate, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _read_job_status(job_id: str) -> str | None:
    try:
        with metadata_path(job_id).open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return data.get("status")


def _job_is_terminal(job_id: str) -> bool:
    """True only when the job store confirms a TERMINAL status.

    A missing/unreadable job record is treated as NOT terminal (conservative:
    still presumed in-flight) rather than as terminal -- the in-flight flag is
    cleared authoritatively by settle_mandate() when a job actually completes;
    an absent job record must never be read as "safe to treat as done" (I2).
    """
    status = _read_job_status(job_id)
    return status is not None and status in TERMINAL


def _new_mandate(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "state": "open",
        "opened_at": now(),
        "opened_by": actor_id(),
        "closed_at": None,
        "closed_by": None,
        "close_reason": None,
        "roles": {},
        "overrides": [],
    }


def engage(
    run_id: str,
    role: str,
    model: str | None,
    backend: str,
    job_id: str,
    fresh: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Decide fresh-vs-resume for (run_id, role) and record the engagement.

    Returns {"mode", "thread_id_to_resume", "isolation", "prior_engagement"}.
    Refuses (die -> SystemExit) on: mandate closed (I1, exit 8), duplicate in-flight
    (I2, exit 7) unless --force, model mismatch (FR-007, exit 7) unless --force.
    """
    role = role.lower()
    mandate = load_mandate(run_id)
    if mandate is None:
        mandate = _new_mandate(run_id)

    if mandate["state"] == "closed":
        die(
            f"mandate {run_id} closed at {mandate['closed_at']} by {mandate['closed_by']}; open a new mandate",
            8,
        )

    role_rec = mandate["roles"].get(role)
    is_new_role = role_rec is None
    if is_new_role:
        role_rec = {
            "role": role,
            "model": model,
            "thread_id": None,
            "continuity": "resume" if backend == "codex" else "no-resume",
            "in_flight_job_id": None,
            "engagements": [],
            "replaced_thread_ids": [],
        }
        mandate["roles"][role] = role_rec

    # Guard 1: duplicate in-flight (I2, FR-006).
    prior_in_flight = role_rec.get("in_flight_job_id")
    if prior_in_flight and not _job_is_terminal(prior_in_flight):
        if not force:
            die(
                f"mandate {run_id} role {role} in flight: {prior_in_flight} (use --force to override)",
                7,
            )
        mandate["overrides"].append({
            "kind": "duplicate",
            "role": role,
            "by": actor_id(),
            "at": now(),
            "detail": f"in-flight {prior_in_flight}; forced {job_id}",
        })
    elif prior_in_flight:
        role_rec["in_flight_job_id"] = None

    # Guard 2: model mismatch (FR-007) -- only meaningful once a role has engaged before.
    if role_rec["engagements"] and model and role_rec.get("model") and model != role_rec["model"]:
        if not force:
            die(
                f"mandate {run_id} role {role} opened with {role_rec['model']}, requested {model} "
                "(use --force to override)",
                7,
            )
        mandate["overrides"].append({
            "kind": "model-mismatch",
            "role": role,
            "by": actor_id(),
            "at": now(),
            "detail": f"opened with {role_rec['model']}; forced {model}",
        })
        role_rec["model"] = model
    elif not role_rec["engagements"] and model:
        role_rec["model"] = model

    # FR-011 / I4: non-codex backends never get mandate-scoped continuity.
    if backend != "codex":
        role_rec["continuity"] = "no-resume"
        mode = "fresh"
        thread_id_to_resume = None
        isolation = "fresh"
    else:
        role_rec["continuity"] = "resume"
        if fresh and role_rec["thread_id"]:
            role_rec["replaced_thread_ids"].append(role_rec["thread_id"])
            role_rec["thread_id"] = None
            mode = "fresh-forced"
            thread_id_to_resume = None
            isolation = "fresh"
        elif role_rec["thread_id"]:
            mode = "resumed"
            thread_id_to_resume = role_rec["thread_id"]
            isolation = "thread_id"
        else:
            mode = "fresh"
            thread_id_to_resume = None
            isolation = "fresh"

    prior_engagement = None
    if mode == "resumed" and role_rec["engagements"]:
        prior_engagement = role_rec["engagements"][-1]["job_id"]

    engagement = {
        "job_id": job_id,
        "mode": mode,
        "isolation": isolation,
        "prior_engagement": prior_engagement,
        "requested_model": model,
        "at": now(),
        "outcome": "pending",
    }
    role_rec["engagements"].append(engagement)
    role_rec["in_flight_job_id"] = job_id

    save_mandate(mandate)
    return {
        "mode": mode,
        "thread_id_to_resume": thread_id_to_resume,
        "isolation": isolation,
        "prior_engagement": prior_engagement,
    }


def settle_mandate(run_id: str, role: str, job_id: str, outcome: str, thread_id: str | None = None) -> None:
    """Update a role's engagement + in-flight/thread state once a job reaches TERMINAL."""
    mandate = load_mandate(run_id)
    if mandate is None:
        return
    role_rec = mandate["roles"].get(role.lower())
    if role_rec is None:
        return
    if role_rec.get("in_flight_job_id") == job_id:
        role_rec["in_flight_job_id"] = None
    for engagement in reversed(role_rec["engagements"]):
        if engagement["job_id"] == job_id:
            engagement["outcome"] = outcome
            break
    # I4: continuity == no-resume must never accumulate a thread_id (backend has no
    # mandate-scoped continuity to resume from, even if the caller supplied one).
    if outcome == "returned" and thread_id and role_rec.get("continuity") == "resume":
        role_rec["thread_id"] = thread_id
    save_mandate(mandate)


def validate_by(by: str | None) -> str:
    """FR-005a / contracts C2a step 1: `--by` must be on the fixed allowlist, checked first."""
    value = (by or "").strip().lower()
    if value not in ALLOWED_CLOSERS:
        die("--by must be one of: " + ", ".join(sorted(ALLOWED_CLOSERS)), 2)
    return value


def mandate_close(run_id: str, by: str | None, reason: str | None, force: bool, as_json: bool) -> int:
    """contracts C2 / C2a: ordered pipeline -- validate --by, load, idempotency, in-flight, transition."""
    actor = validate_by(by)  # step 1: before any read, regardless of mandate state.
    mandate = load_mandate(run_id)  # step 2
    if mandate is None:
        die(f"mandate not found: {run_id}", 1)
    if mandate["state"] == "closed":  # step 3: idempotent, writes nothing.
        if as_json:
            print(json.dumps(mandate, sort_keys=True))
        else:
            print(f"mandate {run_id} already closed at {mandate['closed_at']} by {mandate['closed_by']}")
        return 0

    in_flight: tuple[str, str] | None = None
    for role_name, role_rec in mandate["roles"].items():
        job_id = role_rec.get("in_flight_job_id")
        if not job_id:
            continue
        if _job_is_terminal(job_id):
            role_rec["in_flight_job_id"] = None
            continue
        if in_flight is None:
            in_flight = (role_name, job_id)

    if in_flight is not None:  # step 4
        role_name, job_id = in_flight
        if not force:
            die(
                f"mandate {run_id} has role {role_name} in flight: {job_id} (use --force to close anyway)",
                10,
            )
        mandate["overrides"].append({
            "kind": "close-in-flight",
            "role": role_name,
            "by": actor,
            "at": now(),
            "detail": f"force-closed with in-flight {job_id}",
        })

    mandate.update(state="closed", closed_at=now(), closed_by=actor, close_reason=reason)  # step 5
    save_mandate(mandate)
    if as_json:
        print(json.dumps(mandate, sort_keys=True))
    else:
        print(f"mandate {run_id} closed by {actor}")
    return 0


def _age_days(iso_ts: str | None) -> int | None:
    if not iso_ts:
        return None
    try:
        opened = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - opened).days


def mandate_show(run_id: str, as_json: bool) -> int:
    mandate = load_mandate(run_id)
    if mandate is None:
        die(f"mandate not found: {run_id}", 1)
    if as_json:
        print(json.dumps(mandate, sort_keys=True))
        return 0
    print(f"run_id: {mandate['run_id']}")
    print(f"state: {mandate['state']}")
    print(f"opened_at: {mandate['opened_at']} by {mandate['opened_by']}")
    if mandate["state"] == "closed":
        print(f"closed_at: {mandate['closed_at']} by {mandate['closed_by']} reason={mandate.get('close_reason')}")
    for role, rec in mandate["roles"].items():
        print(
            f"role {role}: model={rec.get('model')} thread_id={rec.get('thread_id')} "
            f"in_flight={rec.get('in_flight_job_id')} continuity={rec.get('continuity')}"
        )
    return 0


def mandate_list(as_json: bool) -> int:
    ensure_mandate_dir()
    mandates = []
    warn_lines = []
    for path in sorted(MANDATE_DIR.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                mandate = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        mandates.append(mandate)
        if mandate.get("state") == "open":
            age = _age_days(mandate.get("opened_at"))
            if age is not None and age > 7:
                warn_lines.append(f"WARN: mandate {mandate['run_id']} open {age}d")
    for line in warn_lines:
        print(line, file=sys.stderr)
    if as_json:
        print(json.dumps(mandates, sort_keys=True))
        return 0
    for mandate in mandates:
        age = _age_days(mandate.get("opened_at")) or 0
        print(
            f"{mandate['run_id']} {mandate['state']} opened={mandate['opened_at']} "
            f"age={age}d roles={len(mandate.get('roles', {}))}"
        )
    return 0


def canonical_backend(backend: str) -> str:
    backend = backend.lower()
    if backend in ANTHROPIC:
        if MODE == "ultra":
            die(f"ultra mode refuses Anthropic backend '{backend}'", 5)
        die(f"backend '{backend}' has no local wrapper", 2)
    if backend not in CANONICAL:
        die("unsupported backend: " + backend + " (use auto, codex, gemini, gemini-lite, gemini-deep, mistral, or openrouter)")
    return CANONICAL[backend]


def mistral_handle(job: dict[str, Any]) -> str:
    """The id that keeps one Mistral agent conversation: a resumed job shares its root job's id."""
    handle = str(job["id"])
    seen = {handle}
    parent = job.get("parent_id")
    while parent and str(parent) not in seen:
        handle = str(parent)
        seen.add(handle)
        try:
            parent = read_job(handle).get("parent_id")
        except (OSError, ValueError, SystemExit):
            break
    return handle


def route_backend(task_class: str) -> str:
    route = SCRIPTS_DIR / "route.sh"
    try:
        selected = subprocess.run(
            [str(route), "pick", task_class], text=True, capture_output=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        die(f"cannot select backend: {error}", 1)
    if selected.returncode:
        detail = selected.stderr.strip() or selected.stdout.strip() or f"route exit {selected.returncode}"
        die(detail, selected.returncode)
    return canonical_backend(selected.stdout.strip())


def make_command(job: dict[str, Any]) -> list[str]:
    backend = job["backend"]
    prompt = job["prompt"]
    if backend == "codex":
        command = [str(SCRIPTS_DIR / "ask.sh")]
        if job.get("reset"):
            command.append("--reset")
        if job.get("model"):
            command.extend(["--model", job["model"]])
        if job.get("mandate"):
            # spec-010: mandate engagements always read the full bridge response (thread_id)
            # and always send exactly one of --thread/--fresh (I9, contracts C3/C4).
            command.append("--raw")
            isolation = job.get("isolation")
            if isolation == "thread_id" and job.get("thread_id_to_resume"):
                command.extend(["--thread", job["thread_id_to_resume"]])
            elif isolation == "fresh":
                command.append("--fresh")
    elif backend.startswith("gemini"):
        tier = {"gemini-flash": "digest", "gemini-flash-lite": "cheap", "gemini-deep": "deep"}[backend]
        command = [str(SCRIPTS_DIR / "gask.sh"), "--tier", tier]
    elif backend == "mistral":
        command = [str(SCRIPTS_DIR / "mask.sh"), "--tier", job.get("tier", "code")]
        if job.get("agent"):
            command.append("--agent")
            command.extend(["--handle", mistral_handle(job)])
        if job.get("reset"):
            command.append("--reset")
    elif backend == "openrouter":
        command = [str(SCRIPTS_DIR / "oask.sh")]
    else:  # Metadata is only written by this runner, but fail closed if it was tampered with.
        die(f"job {job['id']} has unsupported backend '{backend}'", 1)
    command.append(prompt)
    return command


def classify_error(text: str) -> str:
    route = SCRIPTS_DIR / "route.sh"
    try:
        result = subprocess.run(
            [str(route), "classify", text[:1000]], text=True, capture_output=True, check=False, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip() in {"quota", "transient", "unknown"}:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def report_route(backend: str, outcome: str, error: str = "") -> None:
    # Health bookkeeping must never hide a provider result.
    route = SCRIPTS_DIR / "route.sh"
    health_backend = "gemini-flash" if backend == "gemini-deep" else backend
    try:
        subprocess.run([str(route), "report", health_backend, outcome, error[:200]], check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


def start_job(job: dict[str, Any]) -> None:
    command = [sys.executable, str(Path(__file__).resolve()), "_run", job["id"]]
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            env=os.environ.copy(),
        )
    except OSError as error:
        job.update(status="failed", finished_at=now(), error=f"could not start worker: {error}")
        save_job(job)
        die(job["error"], 1)
    # Do not write metadata after spawning: a fast worker may already have
    # recorded its terminal result, and a parent-side write would clobber it.


def run_worker(job_id: str) -> int:
    ensure_mode()
    job = read_job(job_id)
    if job.get("status") in TERMINAL:
        return 0
    job.update(status="running", started_at=now(), error=None)
    save_job(job)
    attempts = int(job.get("retries", 0)) + 1
    result_path = job_dir(job_id) / "result.txt"
    stderr_path = job_dir(job_id) / "stderr.txt"

    for attempt in range(1, attempts + 1):
        job["attempt"] = attempt
        job["status"] = "running" if attempt == 1 else "retrying"
        save_job(job)
        try:
            completed = subprocess.run(make_command(job), text=True, capture_output=True, check=False)
        except OSError as error:
            completed = None
            output, errors, code = "", str(error), 127
        else:
            output, errors, code = completed.stdout, completed.stderr, completed.returncode

        # spec-010: under a mandate, ask.sh --raw returns the full bridge JSON on stdout
        # (contracts C1/C4). Unwrap it before writing result.txt; capture the observed
        # thread_id so settle_mandate() can persist it.
        mandate_thread_id = None
        final_output = output
        if job.get("mandate") and code == 0:
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                final_output = parsed.get("response", "")
                mandate_thread_id = parsed.get("thread_id")

        result_path.write_text(final_output, encoding="utf-8")
        stderr_path.write_text(errors, encoding="utf-8")
        os.chmod(result_path, 0o600)
        os.chmod(stderr_path, 0o600)
        if code == 0:
            job.update(status="returned", finished_at=now(), exit_code=0, error=None, verified_at=None)
            if job.get("mandate"):
                job["thread_id"] = mandate_thread_id
                settle_mandate(job["mandate"], job["role"], job["id"], "returned", thread_id=mandate_thread_id)
            write_artifact(job)  # result.json before the terminal status, so a waiter never sees "returned" without it
            save_job(job)
            report_route(job["backend"], "ok")
            return 0

        detail = (errors or output or f"backend exited {code}").strip()
        # FR-008 / C1 exit 9: a resume failure (bridge 409) surfaces distinctly and is
        # never silently retried as fresh -- caller must rerun with --fresh.
        if job.get("mandate") and job.get("mode") == "resumed" and ("409" in detail or "resume failed" in detail):
            thread = job.get("thread_id_to_resume")
            job["exit_override_code"] = 9
            job["exit_override_message"] = (
                f"mandate {job['mandate']} role {job['role']} resume failed for thread {thread}; "
                "rerun with --fresh to replace"
            )
            settle_mandate(job["mandate"], job["role"], job["id"], "resume-failed")
            code = 9
            detail = job["exit_override_message"]
        elif job.get("mandate"):
            settle_mandate(job["mandate"], job["role"], job["id"], "failed")
        kind = classify_error(detail)
        job.update(exit_code=code, error=detail[-1000:])
        save_job(job)
        report_route(job["backend"], kind, detail)
        if attempt < attempts and kind == "transient":
            time.sleep(min(attempt, 3))
            continue
        break

    job.update(status="failed", finished_at=now())
    write_artifact(job)
    save_job(job)
    return int(job.get("exit_code") or 1)


def brief(job: dict[str, Any]) -> dict[str, Any]:
    return {key: job.get(key) for key in (
        "id", "parent_id", "status", "backend", "task_class", "agent", "attempt", "retries",
        "created_at", "started_at", "finished_at", "verified_at", "exit_code", "error",
    )}


def print_job(job: dict[str, Any], as_json: bool) -> None:
    view = brief(job)
    if as_json:
        print(json.dumps(view, sort_keys=True))
        return
    for key, value in view.items():
        if value is not None:
            print(f"{key}: {value}")


def mark_verified(job_id: str, verdict: str) -> None:
    """Mark a returned job as verified or needs-review.

    Only allowed when status is 'returned'. Updates status and sets verified_at timestamp.
    """
    if verdict not in {"verified", "needs-review"}:
        die(f"invalid verdict: {verdict} (must be 'verified' or 'needs-review')", 2)
    job = read_job(job_id)
    if job.get("status") != "returned":
        die(f"cannot mark job {job_id}: status is '{job.get('status')}' (must be 'returned')", 1)
    job.update(status=verdict, verified_at=now())
    write_artifact(job)
    save_job(job)


def wait_for(job_id: str, as_json: bool = False, interval: float = 0.1) -> int:
    while True:
        job = read_job(job_id)
        if job.get("status") in TERMINAL:
            override_code = job.get("exit_override_code")
            if override_code is not None:
                # FR-008 / C1 exit 9: exact caller-facing stderr, not the generic job dump.
                print(f"agent: {job.get('exit_override_message', job.get('error', ''))}", file=sys.stderr)
                return int(override_code)
            print_job(job, as_json)
            return 0 if job["status"] in {"returned", "verified", "needs-review"} else int(job.get("exit_code") or 1)
        time.sleep(interval)


def submit(args: argparse.Namespace, parent_id: str | None = None, followup: bool = False) -> int:
    ensure_mode()
    ensure_state_dir()
    backend = canonical_backend(args.backend) if args.backend != "auto" else route_backend(args.task_class)
    if followup:
        parent = read_job(parent_id or "")
        if parent.get("backend") not in {"codex", "mistral"}:
            die(f"job {parent['id']} uses {parent.get('backend')}; follow-up is supported only for codex or mistral (openrouter is stateless)", 2)
        backend = parent["backend"]
        agent = bool(parent.get("agent"))
        if backend == "mistral" and not agent:
            die(f"job {parent['id']} used a stateless Mistral completion; use --agent when submitting it", 2)
        tier = parent.get("tier", "code")
    else:
        agent = bool(args.agent)
        tier = args.tier
    if backend == "mistral" and args.agent:
        agent = True
    if backend != "mistral" and agent:
        die("--agent is supported only with mistral (openrouter is stateless single-turn)", 2)
    if backend.startswith("gemini") and args.reset:
        die("--reset is unsupported for stateless Gemini jobs", 2)

    # spec-010: --mandate/--role additive flags on submit (contracts C1). --fresh/--force
    # are mandate-scoped only; a bare submit with neither flag is untouched (FR-012).
    mandate_id = getattr(args, "mandate", None)
    role = getattr(args, "role", None)
    if mandate_id and not role:
        die("--mandate requires --role", 2)
    if role and not mandate_id:
        die("--role requires --mandate", 2)

    job_id = "job-" + secrets.token_hex(8)
    mandate_ctx: dict[str, Any] = {}
    if mandate_id:
        engaged = engage(
            mandate_id,
            role,
            getattr(args, "model", None),
            backend,
            job_id,
            fresh=bool(getattr(args, "fresh", False)),
            force=bool(getattr(args, "force", False)),
        )
        mandate_ctx = {
            "mandate": mandate_id,
            "role": role.lower(),
            "mode": engaged["mode"],
            "isolation": engaged["isolation"],
            "thread_id_to_resume": engaged["thread_id_to_resume"],
            "prior_engagement": engaged["prior_engagement"],
        }
        if backend != "codex":
            print(f"agent: mandate continuity not available for backend {backend}", file=sys.stderr)

    directory = job_dir(job_id)
    directory.mkdir(mode=0o700)
    job = {
        "id": job_id,
        "parent_id": parent_id,
        "status": "queued",
        "backend": backend,
        "task_class": args.task_class,
        "prompt": args.prompt,
        "agent": agent,
        "tier": tier,
        "reset": bool(args.reset),
        "retries": args.retries,
        "attempt": 0,
        "created_at": now(),
        "started_at": None,
        "finished_at": None,
        "verified_at": None,
        "exit_code": None,
        "error": None,
    }
    if getattr(args, "model", None):
        job["model"] = args.model
    if mandate_ctx:
        job.update(mandate_ctx)
    save_job(job)
    start_job(job)
    if args.wait:
        return wait_for(job_id, args.json)
    print(job_id)
    return 0


def command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent.sh",
        description="Dispatch governed local Codex, Gemini, and Mistral jobs.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def add_submit_flags(target: argparse.ArgumentParser) -> None:
        target.add_argument("--backend", default="auto", help="auto, codex, gemini, gemini-lite, gemini-deep, or mistral")
        target.add_argument("--class", dest="task_class", default="review", help="route task class when backend is auto")
        target.add_argument("--agent", action="store_true", help="use the persistent Mistral agent")
        target.add_argument("--tier", choices=("cheap", "code", "deep"), default="code", help="Mistral tier")
        target.add_argument("--reset", action="store_true", help="reset a persistent Codex or Mistral-agent session")
        target.add_argument("--retries", type=int, default=0, choices=range(0, 4), metavar="N", help="retry transient failures (0-3)")
        target.add_argument("--wait", action="store_true", help="wait and print the terminal status")
        target.add_argument("--json", action="store_true", help="with --wait, print terminal status as JSON")
        target.add_argument("--model", help="pin a model slug (passed through to ask.sh --model for codex)")
        # spec-010: mandate re-engagement flags (contracts C1). --fresh/--force are
        # mandate-scoped only and are a no-op without --mandate/--role.
        target.add_argument("--mandate", help="engage under mandate <run_id> (requires --role)")
        target.add_argument("--role", help="role session key within --mandate (requires --mandate)")
        target.add_argument("--fresh", action="store_true", help="mandate-scoped: abandon stored thread_id, start a new session")
        target.add_argument("--force", action="store_true", help="mandate-scoped: override duplicate-in-flight or model-mismatch refusal")
        target.add_argument("prompt")

    add_submit_flags(commands.add_parser("submit", help="queue one job"))
    follow = commands.add_parser("follow-up", help="continue a Codex or Mistral-agent job")
    follow.add_argument("job_id")
    follow.add_argument("--wait", action="store_true")
    follow.add_argument("--json", action="store_true")
    # Mandate flags are declared here only so follow-up can refuse them with a message that
    # names the remedy.  Leaving them undeclared makes argparse answer "unrecognized
    # arguments", which is also exit 2 but tells the caller nothing about `submit --mandate`.
    follow.add_argument("--mandate", help=argparse.SUPPRESS)
    follow.add_argument("--role", help=argparse.SUPPRESS)
    follow.add_argument("--fresh", action="store_true", help=argparse.SUPPRESS)
    follow.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    # Prompt after interspersed flags is dropped by argparse; main() uses parse_known_args()
    # to separate trailing args, then enforces prompt requirement explicitly.
    follow.add_argument("prompt", nargs="?")
    status = commands.add_parser("status", help="show one job")
    status.add_argument("job_id")
    status.add_argument("--json", action="store_true")
    result = commands.add_parser("result", help="print saved job output or its structured artifact")
    result.add_argument("job_id")
    result.add_argument("--stderr", action="store_true", help="print saved stderr instead")
    result.add_argument("--json", action="store_true", help="print the provider-neutral result artifact")
    wait = commands.add_parser("wait", help="wait for a job")
    wait.add_argument("job_id")
    wait.add_argument("--json", action="store_true")
    verify = commands.add_parser("verify", help="mark a returned job as verified or needs-review")
    verify.add_argument("job_id")
    verify.add_argument("--verdict", choices=("verified", "needs-review"), required=True)
    commands.add_parser("list", help="list jobs") .add_argument("--json", action="store_true")
    commands.add_parser("_run", help=argparse.SUPPRESS).add_argument("job_id")

    # spec-010 (contracts C2): `mandate close|list|show` verb group. Only `close` mutates.
    mandate_parser = commands.add_parser("mandate", help="mandate lifecycle (close|list|show)")
    mandate_commands = mandate_parser.add_subparsers(dest="mandate_command", required=True)
    mandate_close_parser = mandate_commands.add_parser("close", help="close a mandate; refuses future resumes")
    mandate_close_parser.add_argument("run_id")
    mandate_close_parser.add_argument("--by", required=True, help="closer identity; must be one of: ceo, lead")
    mandate_close_parser.add_argument("--reason", default=None)
    mandate_close_parser.add_argument("--force", action="store_true", help="close even with a role in flight")
    mandate_close_parser.add_argument("--json", action="store_true")
    mandate_list_parser = mandate_commands.add_parser("list", help="list mandates; WARN on open mandates >7d")
    mandate_list_parser.add_argument("--json", action="store_true")
    mandate_show_parser = mandate_commands.add_parser("show", help="dump one mandate record")
    mandate_show_parser.add_argument("run_id")
    mandate_show_parser.add_argument("--json", action="store_true")

    return parser


def main() -> int:
    parser = command_parser()
    args, extras = parser.parse_known_args()
    if args.command == "follow-up":
        if args.mandate or args.role or args.fresh or args.force:
            die("follow-up does not accept mandate flags in v1; use submit --mandate")
    if extras:
        parser.error("unrecognized arguments: " + " ".join(extras))
    if args.command == "submit":
        return submit(args)
    if args.command == "follow-up":
        if args.prompt is None:
            die("follow-up requires a prompt")
        parent = read_job(args.job_id)
        namespace = argparse.Namespace(
            backend=parent.get("backend", ""), task_class=parent.get("task_class", "review"), agent=parent.get("agent", False),
            tier=parent.get("tier", "code"), reset=False, retries=parent.get("retries", 0), wait=args.wait, json=args.json, prompt=args.prompt,
        )
        return submit(namespace, parent_id=args.job_id, followup=True)
    if args.command == "_run":
        return run_worker(args.job_id)
    if args.command == "status":
        print_job(read_job(args.job_id), args.json)
        return 0
    if args.command == "wait":
        return wait_for(args.job_id, args.json)
    if args.command == "verify":
        mark_verified(args.job_id, args.verdict)
        return 0
    if args.command == "result":
        read_job(args.job_id)
        if args.json:
            path = job_dir(args.job_id) / "result.json"
            try:
                print(path.read_text(encoding="utf-8"), end="")
            except FileNotFoundError:
                die(f"result artifact not available for {args.job_id}", 1)
            return 0
        path = job_dir(args.job_id) / ("stderr.txt" if args.stderr else "result.txt")
        try:
            print(path.read_text(encoding="utf-8"), end="")
        except FileNotFoundError:
            die(f"result not available for {args.job_id}", 1)
        return 0
    if args.command == "list":
        ensure_state_dir()
        jobs = []
        for path in sorted(STATE_DIR.glob("job-*/job.json"), reverse=True):
            try:
                jobs.append(brief(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):
                continue
        if args.json:
            print(json.dumps(jobs, sort_keys=True))
        else:
            for job in jobs:
                print(f"{job['id']} {job['status']} {job['backend']} class={job['task_class']} attempts={job['attempt']}")
        return 0
    if args.command == "mandate":
        if args.mandate_command == "close":
            return mandate_close(args.run_id, args.by, args.reason, args.force, args.json)
        if args.mandate_command == "list":
            return mandate_list(args.json)
        if args.mandate_command == "show":
            return mandate_show(args.run_id, args.json)
        parser.error("unknown mandate command")
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
