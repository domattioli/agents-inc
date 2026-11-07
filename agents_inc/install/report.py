"""`agents-inc report bug|feature`: draft a GitHub issue for agents-inc, file it only with --submit.

Preview first: without --submit the draft is printed and nothing leaves the machine. The draft carries the
version, the doctor codes, the OS and the Codex CLI version; home paths become `~`, and a body that looks
like it holds a secret is refused. Filing uses the caller's own `gh` login."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

REPO = "domattioli/agents-inc"
LABELS = {"bug": "bug", "feature": "enhancement"}
HEADINGS = {"bug": "What happened", "feature": "What you want"}
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}"
    r"|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S{8,})", re.IGNORECASE)


def redact(text: str, home: str | None = None) -> str:
    home = home or str(Path.home())
    return text.replace(home, "~") if home and home != "/" else text


def has_secret(text: str) -> bool:
    return SECRET_RE.search(text) is not None


def environment(doctor_codes: list[str] | None, runner=subprocess.run) -> str:
    from .. import __version__
    codex = "not found"
    exe = shutil.which("codex")
    if exe:
        try:
            out = runner([exe, "--version"], capture_output=True, text=True, timeout=10)
            codex = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else "unknown"
        except (OSError, subprocess.SubprocessError, IndexError):
            codex = "unknown"
    doctor = "not run" if doctor_codes is None else (" ".join(doctor_codes) or "READY")
    return (f"agents-inc {__version__} · doctor {doctor} · {platform.system()} {platform.release()} · "
            f"Python {platform.python_version()} · {codex}")


def draft(kind: str, title: str, body: str, env_line: str, home: str | None = None) -> tuple[str, str, str]:
    """Return (title, label, body). Raises ValueError on empty input or a likely secret."""
    if kind not in LABELS:
        raise ValueError(f"kind must be bug or feature, not {kind!r}")
    title, body = title.strip(), body.strip()
    if not title or not body:
        raise ValueError("--title and --body are required and must not be empty")
    full = (f"## {HEADINGS[kind]}\n\n{body}\n\n## Environment\n\n{env_line}\n\n"
            f"Filed with `agents-inc report {kind}`.\n")
    full, title = redact(full, home), redact(title, home)
    if has_secret(title + "\n" + full):
        raise ValueError("draft looks like it contains a secret or token; remove it and try again")
    return f"[{kind}] {title}", LABELS[kind], full


def run(kind: str, title: str, body: str, submit: bool, doctor_codes: list[str] | None,
        runner=subprocess.run, out=print) -> int:
    if body == "-":
        import sys
        body = sys.stdin.read()
    try:
        t, label, b = draft(kind, title, body, environment(doctor_codes, runner))
    except ValueError as exc:
        out(f"report: {exc}")
        return 2
    out(f"--- draft ({'filing' if submit else 'not filed'}) ---\nRepo: {REPO}\nTitle: {t}\nLabel: {label}\n\n{b}---")
    if not submit:
        out("Show this draft to the user. Run again with --submit to file it.")
        return 0
    gh = shutil.which("gh")
    if not gh:
        out(f"report: gh not found. Install GitHub CLI and run `gh auth login`, or open https://github.com/{REPO}/issues/new and paste the draft.")
        return 1
    res = runner([gh, "issue", "create", "--repo", REPO, "--title", t, "--label", label, "--body-file", "-"],
                 input=b, capture_output=True, text=True, env={**os.environ, "GH_PROMPT_DISABLED": "1"})
    if res.returncode != 0:
        out(f"report: gh issue create failed (rc={res.returncode}): {(res.stderr or '').strip()}")
        return 1
    out(f"filed: {res.stdout.strip()}")
    return 0
