"""narrate: speak a short digest of each new Claude Code assistant message.

A watcher tails the active Claude Code transcript, a summarizer shortens each message, and a speaker reads it
aloud with macOS `say`. The model path is the installed `agents-inc run --model luna` launcher only.
"""
from __future__ import annotations

import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .install.paths import InstallPaths

LUNA_PROMPT = ("Two spoken sentences, no code, no file paths, say what changed and what the operator must decide; "
               "if nothing is needed from the operator say so")
CLASSIFIED_RE = re.compile(r"U//FOUO|FOUO|CLASSIFIED|SECRET|NOFORN", re.IGNORECASE)
QUOTA_EXIT = 75  # `agents-inc run` exit code for a usage or rate limit (install/runtime.py); the ledger exposes no signal
LOCAL_LIMIT = 280
DEFAULT_VOICE = "Samantha"
FLAG_NAME = "narrate-on"


class SummarizerError(Exception):
    """The summarizer could not produce a digest (non-zero exit, quota pause, empty reply, launch failure)."""

    def __init__(self, message: str, paused: bool = False):
        super().__init__(message)
        self.paused = paused


# ---- paths and flag -------------------------------------------------------------------------------------------

def settings_dir(home: Optional[Path] = None) -> Path:
    return InstallPaths.for_home(home or Path.home()).settings.parent


def flag_path(home: Optional[Path] = None) -> Path:
    return settings_dir(home) / FLAG_NAME


def flag_on(home: Optional[Path] = None) -> bool:
    return flag_path(home).exists()


def set_flag(on: bool, home: Optional[Path] = None) -> None:
    path = flag_path(home)
    if on:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    else:
        path.unlink(missing_ok=True)


def projects_dir(home: Optional[Path] = None) -> Path:
    return (home or Path.home()) / ("." + "claude") / "projects"


def find_transcript(home: Optional[Path] = None) -> Optional[Path]:
    """Newest-modified *.jsonl in any workspace folder under the Claude Code projects directory."""
    candidates = []
    for p in projects_dir(home).glob("*/*.jsonl"):
        try:
            candidates.append((p.stat().st_mtime, p))
        except OSError:
            continue
    return max(candidates)[1] if candidates else None


# ---- transcript parsing and text cleanup ----------------------------------------------------------------------

def assistant_text(line: str) -> Optional[str]:
    """Joined text blocks of one assistant record; None for any other record or when no text block exists."""
    try:
        rec = json.loads(line)
    except ValueError:
        return None
    if not isinstance(rec, dict) or rec.get("type") != "assistant":
        return None
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    text = "\n\n".join(p.strip() for p in parts if p and p.strip())
    return text or None


def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?(```|\Z)", " ", text, flags=re.DOTALL)  # fenced code, including an unclosed fence
    text = re.sub(r"`([^`\n]*)`", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"(\*\*|__|\*|_)(\S(?:.*?\S)?)\1", r"\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_classified(text: str) -> bool:
    return bool(CLASSIFIED_RE.search(text))


def passes_decide_only(text: str) -> bool:
    """Decide-only filter: a question mark in the final paragraph, or the token DECIDE anywhere."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return "DECIDE" in text or bool(paragraphs and "?" in paragraphs[-1])


def read_new_messages(path: Path, offset: int) -> tuple[list[str], int]:
    """Assistant texts appended after byte `offset`, and the new offset. A partial last line waits for more data."""
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read()
    end = data.rfind(b"\n") + 1
    texts = []
    for raw in data[:end].splitlines():
        t = assistant_text(raw.decode("utf-8", "replace"))
        if t:
            texts.append(t)
    return texts, offset + end


def latest_message(path: Path) -> Optional[str]:
    texts, _ = read_new_messages(path, 0)
    return texts[-1] if texts else None


# ---- summarizers ----------------------------------------------------------------------------------------------

class LocalSummarizer:
    """No model call: the first paragraph, cut to 280 characters."""
    name = "local"

    def summarize(self, text: str) -> str:
        first = next((p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()), "")
        first = " ".join(first.split())
        return first if len(first) <= LOCAL_LIMIT else first[:LOCAL_LIMIT - 1].rstrip() + "…"


class LunaSummarizer:
    """Shells out to `agents-inc run --model luna --no-tools --cwd <cwd>`. The launcher reads the prompt from stdin
    (install/cli.py passes sys.stdin to run_codex) and prints the reply on stdout; exit 75 means quota paused."""
    name = "luna"

    def __init__(self, cwd: str, launcher: Optional[str] = None, runner: Callable = subprocess.run, timeout: float = 120):
        self.cwd = cwd
        self.launcher = launcher or str(InstallPaths.for_home(Path.home()).launcher)
        self.runner = runner
        self.timeout = timeout

    def argv(self) -> list[str]:
        return [self.launcher, "run", "--model", "luna", "--no-tools", "--cwd", self.cwd]

    def summarize(self, text: str) -> str:
        prompt = f"{LUNA_PROMPT}\n\nAssistant message:\n{text}\n"
        try:
            proc = self.runner(self.argv(), input=prompt, capture_output=True, text=True, timeout=self.timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise SummarizerError(f"launcher failed: {exc}") from exc
        if proc.returncode != 0:
            raise SummarizerError(f"luna exit {proc.returncode}", paused=proc.returncode == QUOTA_EXIT)
        reply = " ".join((proc.stdout or "").split())
        if not reply:
            raise SummarizerError("luna returned an empty reply")
        return reply


# ---- speaker --------------------------------------------------------------------------------------------------

def say_runner(voice: str, text: str) -> None:
    subprocess.run(["say", "-v", voice, "-f", "-"], input=text, text=True, check=False)


class Speaker:
    """One worker thread drains a queue, so utterances never overlap. `speak_fn(voice, text)` is injectable."""

    def __init__(self, voice: str = DEFAULT_VOICE, speak_fn: Callable[[str, str], None] = say_runner):
        self.voice = voice
        self._speak = speak_fn
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

    def _work(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item is None:
                    return
                try:
                    self._speak(self.voice, item)
                except Exception as exc:  # a speech failure must not kill the watcher
                    log(f"speak failed: {exc}")
            finally:
                self._q.task_done()

    def say(self, text: str) -> None:
        self._q.put(text)

    def close(self) -> None:
        self._q.put(None)
        self._thread.join()


# ---- narrator -------------------------------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"narrate: {msg}", file=sys.stderr, flush=True)


class Narrator:
    def __init__(self, summarizer, speaker=None, decide_only: bool = False, dry_run: bool = False):
        self.summarizer = summarizer
        self.speaker = speaker
        self.decide_only = decide_only
        self.dry_run = dry_run

    def digest(self, raw: str) -> Optional[str]:
        """The sentence to speak for one assistant message, or None when a guard says to stay silent."""
        if is_classified(raw):
            log("skipped: classification marker found")
            return None
        text = strip_markdown(raw)
        if not text:
            return None
        if self.decide_only and not passes_decide_only(text):
            return None
        try:
            return self.summarizer.summarize(text)
        except SummarizerError as exc:
            log(f"{'paused' if exc.paused else 'failed'} ({exc}); using local digest")
            return "local. " + LocalSummarizer().summarize(text)

    def handle(self, raw: str) -> Optional[str]:
        out = self.digest(raw)
        if out is None:
            return None
        if self.dry_run or self.speaker is None:
            print(out, flush=True)
        else:
            self.speaker.say(out)
        return out


def watch(narrator: Narrator, transcript: Optional[Path], once: bool = False, poll: float = 1.0,
          home: Optional[Path] = None, sleep: Callable[[float], None] = time.sleep) -> int:
    """Follow the transcript in the foreground. Off flag: messages are consumed but nothing is spoken."""
    path, offset = None, 0
    while True:
        target = transcript or find_transcript(home)
        if target is not None and target.exists():
            if target != path:  # first sight or a newer session: skip history unless --once wants the latest message
                path = target
                if once:
                    msg = latest_message(path)
                    if msg is not None and (narrator.dry_run or flag_on(home)):
                        narrator.handle(msg)
                    return 0
                offset = path.stat().st_size
            else:
                texts, offset = read_new_messages(path, offset)
                if flag_on(home) or narrator.dry_run:
                    for t in texts:
                        narrator.handle(t)
        elif once:
            log("no transcript found")
            return 1
        try:
            sleep(poll)
        except KeyboardInterrupt:
            return 0


# ---- CLI --------------------------------------------------------------------------------------------------------

def run_cli(args, home: Optional[Path] = None) -> int:
    transcript = Path(args.transcript) if args.transcript else None
    if args.verb in ("on", "off"):
        set_flag(args.verb == "on", home)
        print(f"narrate {args.verb}")
        return 0
    if args.verb == "status":
        print(f"flag: {'on' if flag_on(home) else 'off'} ({flag_path(home)})")
        print(f"summarizer: {args.summarizer}")
        print(f"voice: {args.voice}")
        print(f"transcript: {transcript or find_transcript(home) or 'none found'}")
        return 0
    summarizer = LocalSummarizer() if args.summarizer == "local" else LunaSummarizer(cwd=str(Path.cwd()))
    speaker = None if args.dry_run else Speaker(args.voice)
    narrator = Narrator(summarizer, speaker, args.decide_only, args.dry_run)
    try:
        return watch(narrator, transcript, args.once, home=home)
    finally:
        if speaker:
            speaker.close()
