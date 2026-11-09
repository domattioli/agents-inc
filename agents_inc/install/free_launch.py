"""Free-model dispatch kind (spec 037): the allowed-slug map and the launch of the unchanged legacy wrappers.

`gask.sh`, `mask.sh` and `oask.sh` receive the prompt on stdin, never in argv. Free runs use no tools, no fan-out and no resume.
This module holds the map and the launch only; `dispatch.py` owns the run directory, the gates and the outcome.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from agents_inc.datafiles import repo_file

WRAPPER_DIR = repo_file("skills/codex-bridge/scripts")  # tests patch this to point at stub wrappers
DEFAULT_TASK_KIND = "summarize"
TURN_TIMEOUT_S = 600


class FreeModel(NamedTuple):
    slug: str
    provider: str  # gemini, mistral, openrouter
    wrapper: str  # file name under WRAPPER_DIR
    tier: str | None  # --tier value; None for OpenRouter
    model_env: str | None  # MODEL value for oask.sh
    host: str  # provider host, named in a blocked message
    max_input_chars: int


def _entry(slug, provider, wrapper, tier, host, max_input_chars, model_env=None) -> tuple[str, FreeModel]:
    return slug, FreeModel(slug, provider, wrapper, tier, model_env, host, max_input_chars)


_GEMINI, _MISTRAL, _OPENROUTER = "generativelanguage.googleapis.com", "api.mistral.ai", "openrouter.ai"

# Exact slugs only. Deep tiers (gemini-3.1-pro-preview, mistral-large-latest) and paid OpenRouter slugs stay out (SC-005).
FREE_MODELS: dict[str, FreeModel] = dict([
    _entry("gemini-3.8-flash", "gemini", "gask.sh", "digest", _GEMINI, 200000),
    _entry("gemini-flash-lite-latest", "gemini", "gask.sh", "cheap", _GEMINI, 48000),
    _entry("ministral-3b-latest", "mistral", "mask.sh", "cheap", _MISTRAL, 48000),
    _entry("codestral-latest", "mistral", "mask.sh", "code", _MISTRAL, 48000),
    _entry("nvidia/nemotron-3.5-lightning:free", "openrouter", "oask.sh", None, _OPENROUTER, 48000,
           "nvidia/nemotron-3.5-lightning:free"),
    _entry("nvidia/nemotron-3-ultra-550b-a55b:free", "openrouter", "oask.sh", None, _OPENROUTER, 190000,
           "nvidia/nemotron-3-ultra-550b-a55b:free"),
    _entry("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "openrouter", "oask.sh", None, _OPENROUTER, 96000,
           "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"),
    _entry("google/gemma-4-26b-a4b-it:free", "openrouter", "oask.sh", None, _OPENROUTER, 24000,
           "google/gemma-4-26b-a4b-it:free"),
    _entry("google/gemma-4-31b-it:free", "openrouter", "oask.sh", None, _OPENROUTER, 48000,
           "google/gemma-4-31b-it:free"),
    _entry("dots-studio/dots-3-note-preview:free", "openrouter", "oask.sh", None, _OPENROUTER, 12000,
           "dots-studio/dots-3-note-preview:free"),
])


def is_free(slug) -> bool:
    return isinstance(slug, str) and slug in FREE_MODELS


def wrapper_path(slug: str, scripts: Path | None = None) -> Path:
    return Path(scripts if scripts is not None else WRAPPER_DIR) / FREE_MODELS[slug].wrapper


def wrapper_argv(slug: str, scripts: Path | None = None) -> list[str]:
    """`bash <wrapper> [--tier T]`. The prompt is not here: it goes on stdin."""
    entry = FREE_MODELS[slug]
    argv = ["bash", str(wrapper_path(slug, scripts))]
    if entry.tier:
        argv += ["--tier", entry.tier]
    return argv


def wrapper_env(slug: str, task_kind: str | None, base: dict | None = None) -> dict:
    """Child environment. WORKERBEES_GOVERNANCE=off is the wrapper's own gate (it exits 3 otherwise); dispatch is the
    governed caller. MODEL is set for OpenRouter and dropped for the others, whose tier picks the model."""
    env = dict(os.environ if base is None else base)
    env["WORKERBEES_GOVERNANCE"] = "off"
    env["TASK"] = task_kind or DEFAULT_TASK_KIND
    entry = FREE_MODELS[slug]
    if entry.model_env:
        env["MODEL"] = entry.model_env
    else:
        env.pop("MODEL", None)
    return env


_SNAPSHOT_SPAN_RE = re.compile(r"snapshot <snapshot>; verify with `[^`]*`")


def strip_snapshot(prompt: str) -> str:
    """A free run never shows the provider a snapshot path or verifier line (supervisor ruling 1)."""
    prompt = _SNAPSHOT_SPAN_RE.sub("none (this run has no repository access)", prompt)
    return prompt.replace("<snapshot>", "none")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


ROUTING_PATH = repo_file("agents_inc/routing.json")  # read at run time, never cached (FR-003); tests patch this
ALLOWED_PERMISSION_MODES = ("default", "plan")
_CLASSIFICATIONS = ("public", "internal", "confidential")


class Refusal(str):
    """A refusal name (`refused-task`, ...) that also carries the human detail written to lint.txt."""
    detail: str = ""

    def __new__(cls, name: str, detail: str = ""):
        obj = super().__new__(cls, name)
        obj.detail = detail
        return obj


class InputsRefused(ValueError):
    """build_input_section refuses; `str(exc)` is the detail. The refusal name is always `refused-inputs`."""
    name = "refused-inputs"


def load_routing() -> dict:
    return json.loads(Path(ROUTING_PATH).read_text(encoding="utf-8"))


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


MODELS_PATH = repo_file("agents_inc/models.json")  # catalog, read at run time (FR-014); tests patch this


def load_catalog() -> dict:
    """The `models` map of models.json; an unreadable catalog is an empty map (the allowed-slug map still guards)."""
    try:
        return json.loads(Path(MODELS_PATH).read_text(encoding="utf-8")).get("models", {})
    except (OSError, ValueError, AttributeError):
        return {}


def pre_checks(slots: dict, args=None, routing: dict | None = None, cwd: Path | None = None,
               model: str | None = None) -> Refusal | None:
    """Refusals that need no provider call (FR-003..FR-005, FR-014). Return a Refusal (a str name with `.detail`) or None.
    Order: task, classification, fan-out, grants. `routing` defaults to routing.json read now. With `model`, a catalog
    entry that lists the task in `tasks_bad` is `refused-task` too."""
    routing = load_routing() if routing is None else routing
    kind = _text(slots.get("TASK_KIND"))
    allowed = routing.get("optional_allowed_tasks", [])
    if not kind or kind not in allowed:
        return Refusal("refused-task", f"TASK_KIND {kind or 'missing'!r} is not one of: {', '.join(allowed)}")
    if model and kind in (load_catalog().get(model) or {}).get("tasks_bad", []):
        return Refusal("refused-task", f"the catalog lists {kind!r} as a bad task for {model}")
    # Author written: the slot is in the author's slots file. The renderer fills a default for a missing slot; that does not count.
    text = _text(slots.get("CLASSIFICATION"))
    level = text.split(None, 1)[0].lower().rstrip(":;,.") if text else ""
    if level not in _CLASSIFICATIONS:
        return Refusal("refused-classification",
                       f"CLASSIFICATION must be written by the author and start with: {', '.join(_CLASSIFICATIONS)}")
    if level == "confidential":
        from agents_inc.policy import is_authorized  # per-workspace authorization, the router's rule
        base = Path(cwd or getattr(args, "cwd", None) or os.getcwd())
        if not is_authorized(base):
            return Refusal("refused-classification",
                           f"confidential input needs workspace authorization in {base}/.workerbees/authorization.json")
    fan = slots.get("FAN_OUT")
    fan_text = json.dumps(fan) if isinstance(fan, (dict, list)) else _text(fan)
    if fan_text:
        nums = re.findall(r"\d+", fan_text)
        if not nums or any(int(n) > 0 for n in nums):
            return Refusal("refused-fan-out", f"a free run takes no fan-out, got {fan_text!r}")
    mode = _text(slots.get("PERMISSION_MODE"))
    if mode and mode not in ALLOWED_PERMISSION_MODES:
        return Refusal("refused-grants", f"PERMISSION_MODE {mode!r} is beyond default or plan")
    bash = slots.get("BASH_ALLOW")
    if bash not in (None, "", []) and (not isinstance(bash, str) or bash.strip()):
        return Refusal("refused-grants", "BASH_ALLOW grants tools; a free run has none")
    return None


def build_input_section(slots: dict, cwd: Path, max_chars: int) -> tuple[str, list]:
    """Read INPUT_FILES (repo-relative text files). Return (prompt section, [{path, bytes, sha256}]).
    Raise InputsRefused for a path outside cwd, a symlink, a non-regular or non-text file, credential-shaped
    content, or total text over max_chars. No file: ("", [])."""
    raw = slots.get("INPUT_FILES")
    if raw in (None, "", []):
        return "", []
    if isinstance(raw, str):
        raw = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not isinstance(raw, list) or not all(isinstance(p, str) and p.strip() for p in raw):
        raise InputsRefused("INPUT_FILES must be a list of path strings")
    from agents_inc.install.dispatch import credential_hit  # lazy: dispatch imports this module
    base = Path(cwd).resolve()
    parts, files, total = [], [], 0
    for rel in raw:
        rel = rel.strip()
        path = base / rel
        if os.path.isabs(rel) or not path.resolve().is_relative_to(base):
            raise InputsRefused(f"{rel}: outside the working directory")
        probe = base
        for part in Path(rel).parts:
            probe = probe / part
            if probe.is_symlink():
                raise InputsRefused(f"{rel}: symlink")
        if not path.is_file():
            raise InputsRefused(f"{rel}: not a regular file")
        data = path.read_bytes()
        try:
            if b"\x00" in data:
                raise UnicodeDecodeError("utf-8", b"", 0, 1, "NUL")
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            raise InputsRefused(f"{rel}: not a text file") from None
        if credential_hit({"path": rel, "content": content}):
            raise InputsRefused(f"{rel}: credential-shaped content")
        total += len(content)
        if total > max_chars:
            raise InputsRefused(f"input over the model limit of {max_chars} characters (at {rel})")
        parts.append(f"=== {rel} ===\n{content.rstrip(chr(10))}\n=== end {rel} ===")
        files.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return "INPUT FILES (read by dispatch; you have no tools):\n\n" + "\n\n".join(parts) + "\n", files


class Classification(NamedTuple):
    reason: str | None  # None: the wrapper succeeded, or its failure belongs to the shared timeout path
    detail: str = ""


_QUOTA_TEXT = re.compile(r"error 429|\b429\b|too many requests|rate.?limit|quota|resource.?exhausted|at capacity", re.I)
_UNREACHABLE_TEXT = re.compile(r"cannot reach|timeout", re.I)
_NO_KEY_TEXT = re.compile(r"no API key", re.I)
_TIMEOUT_MARK = "turn timeout after"  # run_free writes it with rc 124; dispatch's own timeout path owns that case


def _first_line(text: str) -> str:
    return next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")


def classify_rc(rc: int, stdout: str, stderr: str, slug: str | None = None) -> Classification:
    """Map a wrapper result to a failure reason (research R6). Wrappers print 429, timeout and connect failures with
    rc 1, so rc 1 is read by its stderr text. `stdout` is the reply and is never searched: a reply may quote any text.
    Reasons: redacted-reply, provider-key-missing, wrapper-refused, quota-paused, blocked (detail names the host from
    FREE_MODELS), rc-nonzero. rc 0, and rc 124 with the turn-timeout mark, give reason None."""
    err = stderr or ""
    if rc == 0 or (rc == 124 and _TIMEOUT_MARK in err):
        return Classification(None)
    if rc == 4:
        return Classification("redacted-reply", _first_line(err))
    if rc == 2 and _NO_KEY_TEXT.search(err):
        return Classification("provider-key-missing", _first_line(err))
    if rc == 3:
        return Classification("wrapper-refused", _first_line(err))
    if rc == 1:
        if _QUOTA_TEXT.search(err):
            return Classification("quota-paused", _first_line(err))
        if _UNREACHABLE_TEXT.search(err):
            host = FREE_MODELS[slug].host if slug in FREE_MODELS else "unknown-host"
            return Classification("blocked", f"cannot reach {host}: {_first_line(err)}")
    return Classification("rc-nonzero", _first_line(err))


_USAGE_RE = re.compile(r"\|\s*in (\d+) out (\d+)(?: think (\d+))?\s*\]")


def parse_usage(stdout: str, stderr: str) -> dict | None:
    """Tokens when a wrapper reports them (`[gemini M | in N out N think N]` on stderr), else None. Only stderr is read."""
    match = _USAGE_RE.search(stderr or "")
    if not match:
        return None
    usage = {"input_tokens": int(match.group(1)), "output_tokens": int(match.group(2))}
    if match.group(3) is not None:
        usage["reasoning_tokens"] = int(match.group(3))
    return usage


HOLD_TIER = "grunt"  # the router tier whose cooldown keys cover the free providers


def pre_launch_hold(slug: str, now=None, health: dict | None = None) -> str | None:
    """FR-009: the wrappers hold no cap or cooldown check, so ask the router before any call. Return a detail string
    when the provider is cooling down or at its daily cap (the run ends quota-paused, exit 75), else None.
    An unreadable health or cap store never blocks a run."""
    from datetime import datetime, timezone
    from agents_inc import free_health, router
    entry = FREE_MODELS[slug]
    now = now or datetime.now(timezone.utc)
    try:
        health = free_health.load_health() if health is None else health
        # The router's keys follow the grunt tier model (gemini: flash-lite), so check this slug's own keys one by one:
        # the provider key and the backend key (gemini flash and flash-lite cool down apart).
        for key in dict.fromkeys((entry.provider, free_health.backend_key(entry.provider, slug))):
            if key in health and router._in_cooldown(entry.provider, HOLD_TIER, {entry.provider: health[key]}, now):
                return f"{key} is in cooldown"
        if router._at_cap(entry.provider, now):
            return f"{entry.provider} is at its daily call cap"
    except Exception:  # noqa: BLE001
        return None
    return None


def tcp_probe(host: str, timeout: float = 3.0) -> bool:
    import socket
    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return True
    except OSError:
        return False


def reachability_hold(slug: str, sandboxed, probe=None) -> str | None:
    """FR-011: when the caller is sandboxed (`sandboxed` is the sandbox name or None) probe the provider host before the
    call. Return a detail naming the host when it is unreachable (the run ends blocked, exit 69), else None.
    `probe(host) -> bool` is injectable; no sandbox, no probe."""
    if not sandboxed:
        return None
    host = FREE_MODELS[slug].host
    if (probe or tcp_probe)(host):
        return None
    return f"cannot reach {host} from the caller sandbox ({sandboxed})"


def run_free(spec: dict, prompt: str, run_dir: Path, cwd: Path, scripts: Path | None = None,
             timeout: float = TURN_TIMEOUT_S) -> dict:
    """Run the wrapper for spec["model"] with the prompt on stdin. Save stdout to run_dir/stdout.md and stderr to
    run_dir/stderr.txt. Return {rc, stdout, stderr, argv, wrapper, wrapper_sha256, session_id}. A wrapper that is
    missing or cannot start raises OSError (the caller records launch-failed). A timeout is rc 124 with the
    `turn timeout after` mark, the form the Claude and Codex path uses."""
    model = spec["model"]
    argv = wrapper_argv(model, scripts)
    wrapper = Path(argv[1])
    digest = sha256_file(wrapper)
    env = wrapper_env(model, spec.get("task_kind"))
    try:
        proc = subprocess.run(argv, input=prompt, cwd=str(cwd), env=env, capture_output=True, text=True,
                              errors="replace", timeout=timeout)
        rc, out, err = proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        text = lambda b: b.decode("utf-8", "replace") if isinstance(b, bytes) else (b or "")  # noqa: E731
        rc, out = 124, text(exc.stdout)
        err = text(exc.stderr) + f"\nturn timeout after {int(timeout)}s\n"
    (Path(run_dir) / "stdout.md").write_text(out, encoding="utf-8")
    (Path(run_dir) / "stderr.txt").write_text(err, encoding="utf-8")
    return {"rc": rc, "stdout": out, "stderr": err, "argv": argv, "wrapper": str(wrapper),
            "wrapper_sha256": digest, "session_id": None}
