"""Spec 027: live provider events for `agents-inc dispatch`.

EventSink appends one JSON envelope per line to <run dir>/events.jsonl while the delegate runs. The streaming
runner (_stream_run) feeds provider stdout lines to a callback as they arrive."""
from __future__ import annotations
import contextlib
import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

LINE_CAP = 64 * 1024  # bytes of one stored provider line (FR-009)
TOTAL_CAP = 64 * 1024 * 1024  # bytes of events.jsonl before provider events stop (FR-009)
EVENTS_FILE = "events.jsonl"
_POPEN = subprocess.Popen  # bound at import: tests patch subprocess.Popen with a Mock factory
CHILD_START = None  # callable(pid) the dispatch run sets: told the pid of every delegate process once it runs (FR-012)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _cut(text: str, cap: int) -> str:
    return text.encode("utf-8", "replace")[:cap].decode("utf-8", "ignore")


class EventSink:
    """Envelope writer for <run dir>/events.jsonl (FR-001, FR-008, FR-009). Never raises into dispatch: any OSError
    disables the sink and sets `error`, which the run path copies to run.json `events_error`."""

    def __init__(self, run_dir, safe_writes: bool = False, line_cap: int = LINE_CAP, total_cap: int = TOTAL_CAP):
        self.path = Path(run_dir) / EVENTS_FILE
        self.error: str | None = None
        self._line_cap, self._total_cap = line_cap, total_cap
        self._lock = threading.Lock()
        self._seq = self._size = 0
        self._truncated = False
        self._fd: int | None = None
        # D51: under the broker never follow a planted link and never reuse a file.
        flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL | os.O_NOFOLLOW if safe_writes else os.O_APPEND)
        try:
            self._fd = os.open(self.path, flags, 0o600)
        except OSError as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    @property
    def active(self) -> bool:
        return self._fd is not None

    def _write(self, source: str, event: dict, cut: bool = False) -> None:
        self._seq += 1
        envelope = {"v": 1, "seq": self._seq, "ts": _now(), "source": source, "event": event}
        if cut:
            envelope["cut"] = True
        data = (json.dumps(envelope, ensure_ascii=False) + "\n").encode("utf-8")
        view = memoryview(data)
        while view:  # the line lands whole before the next provider line is read
            view = view[os.write(self._fd, view):]
        self._size += len(data)

    def emit(self, source: str, event: dict, cut: bool = False) -> None:
        with self._lock:
            if self._fd is None:
                return
            try:
                text = json.dumps(event, ensure_ascii=False)
                if not cut and len(text.encode("utf-8", "replace")) > self._line_cap:
                    event, cut = {"type": "raw", "text": _cut(text, self._line_cap)}, True
                if source != "agents-inc":  # lifecycle events always land; provider events stop at the total cap
                    if self._truncated:
                        return
                    if self._size + len(text) > self._total_cap:
                        self._truncated = True
                        self._write("agents-inc", {"type": "events.truncated", "cap_bytes": self._total_cap})
                        return
                self._write(source, event, cut)
            except OSError as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                self._close_locked()

    def line(self, source: str, text: str) -> None:
        """Store one provider stdout line: a JSON object as is, anything else as {"type": "raw", "text": ...}."""
        text = text.rstrip("\r\n")
        if len(text.encode("utf-8", "replace")) > self._line_cap:
            self.emit(source, {"type": "raw", "text": _cut(text, self._line_cap)}, cut=True)
            return
        try:
            event = json.loads(text)
        except ValueError:
            event = None
        self.emit(source, event if isinstance(event, dict) else {"type": "raw", "text": text})

    def _close_locked(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def close(self) -> None:
        with self._lock:
            self._close_locked()


def _kill_group(proc) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)


def _give_up_on_pipes(proc) -> None:  # a grandchild holds the pipes open
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        with contextlib.suppress(Exception):
            pipe.close()


def _lines(text: str):
    return (ln.rstrip("\r\n") for ln in text.splitlines())


def _communicate_run(proc, prompt, limit, on_line, mark):
    """Not a piped Popen (a test double): the old blocking path; its lines reach on_line after the fact."""
    from .runtime import kill_and_reap  # runtime imports this module: resolve late
    try:
        stdout, stderr = proc.communicate(input=prompt, timeout=limit)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            _give_up_on_pipes(proc)
            stdout, stderr = "", ""
        rc, stderr = 124, f"{stderr or ''}{mark} {limit:g} s"
    except BaseException:  # cancellation (KeyboardInterrupt included): no detached delegate survives the supervisor
        kill_and_reap(proc)
        raise
    if on_line:
        for ln in _lines(stdout or ""):
            on_line(ln)
    return rc, stdout, stderr


def _stream_run(proc, prompt: str, limit: float | None, on_line=None, mark: str = "turn timeout after",
                on_start=None) -> tuple[int, str, str]:
    """Drive a Popen started with text pipes and start_new_session=True. Write prompt, close stdin, hand each
    stdout line (no line end) to on_line as it arrives, and return (rc, stdout, stderr) with the full texts.

    limit seconds (None: no deadline): at expiry kill the process group, return rc 124 and stderr + "<mark> <limit> s",
    as launch() and run_codex always did. Any other exception (KeyboardInterrupt included) kills the group and reaps
    the child before it propagates. on_start(pid) runs once the readers are up."""
    if not isinstance(proc, _POPEN) or proc.stdout is None:
        return _communicate_run(proc, prompt, limit, on_line, mark)
    from .runtime import kill_and_reap  # runtime imports this module: resolve late
    out_buf: list[str] = []
    err_buf: list[str] = []

    def pump(pipe, buf, callback):
        try:
            for line in iter(pipe.readline, ""):
                buf.append(line)
                if callback is not None:
                    try:
                        callback(line.rstrip("\r\n"))
                    except Exception:
                        pass  # a broken viewer never stops the delegate
        except (OSError, ValueError):
            pass

    def feed():
        try:
            proc.stdin.write(prompt)
        except (OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(Exception):
                proc.stdin.close()

    threads = [threading.Thread(target=pump, args=(proc.stdout, out_buf, on_line), daemon=True),
               threading.Thread(target=pump, args=(proc.stderr, err_buf, None), daemon=True),
               threading.Thread(target=feed, daemon=True)]
    try:
        for t in threads:
            t.start()
        for start in dict.fromkeys(f for f in (on_start, CHILD_START) if f is not None):  # both, each once
            try:
                start(proc.pid)
            except Exception:
                pass  # recording the group is best effort: the delegate still runs
        deadline = None if not limit else time.monotonic() + limit
        for t in threads:
            t.join(None if deadline is None else max(0.0, deadline - time.monotonic()))
        expired = any(t.is_alive() for t in threads)
        if not expired:
            try:
                proc.wait(timeout=None if deadline is None else max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                expired = True
        if not expired:
            _give_up_on_pipes(proc)  # both are at EOF: close the handles
            return proc.returncode, "".join(out_buf), "".join(err_buf)
        _kill_group(proc)
        for t in threads:
            t.join(10)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)
        if any(t.is_alive() for t in threads):  # a grandchild holds the pipes open: give up on the output
            out_buf, err_buf = [], []
        _give_up_on_pipes(proc)
        return 124, "".join(out_buf), f"{''.join(err_buf)}{mark} {limit:g} s"
    except BaseException:
        kill_and_reap(proc)
        _give_up_on_pipes(proc)
        raise
