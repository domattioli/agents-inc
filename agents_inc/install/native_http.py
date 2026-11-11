"""Spec 038 T022: one provider call for a stateless guest agent (Gemini first), standard library only.

The key is read in-process (the 0600 key store `~/.config/workerbees/.env`, then the legacy wrapper's key file, then
`~/Projects/.env`, the operator's canonical store per the D2 amendment) and sent
only as a request header. It never goes in argv, a child env, a prompt, stdout, stderr or a file: nothing here spawns a
child, and every text this module prints passes `scrub` first.

Exit codes (contracts/step-adapter.md): 0 ok; 75 quota; 69 provider host unreachable; 3 not offered (no key, no
workspace authorization, unknown model); 2 usage or context over the model limit; 124 timeout; 1 other failure.
"""
from __future__ import annotations
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_NOT_OFFERED, EXIT_BLOCKED, EXIT_QUOTA, EXIT_TIMEOUT = 0, 1, 2, 3, 69, 75, 124
# Key names as the legacy wrappers read them (gask.sh, mask.sh, oask.sh), first one wins.
KEY_VARS = {"gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"), "mistral": ("MISTRAL_API_KEY",),
            "openrouter": ("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY")}
HOSTS = {"gemini": "https://generativelanguage.googleapis.com", "mistral": "https://api.mistral.ai",
         "openrouter": "https://openrouter.ai"}
# Tests point a provider at the fake server. Only a loopback URL is honoured, so the variable cannot send a key elsewhere.
URL_ENV = {"gemini": "AGENTS_INC_NATIVE_GEMINI_URL", "mistral": "AGENTS_INC_NATIVE_MISTRAL_URL",
           "openrouter": "AGENTS_INC_NATIVE_OPENROUTER_URL"}
LOOPBACK = ("127.0.0.1", "localhost", "::1")
PROGRESS = "agents-inc run:"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would resend the key header to another host: refuse it, so the 3xx surfaces as an HTTPError."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


class StepError(Exception):
    def __init__(self, code: int, text: str):
        super().__init__(text)
        self.code, self.text = code, text


def key_store(home: Path) -> Path:
    return Path(home) / ".config" / "workerbees" / ".env"


# The per-provider key file the legacy wrapper reads first (gask.sh, mask.sh, oask.sh KEY_FILE), relative to HOME.
KEY_FILES = {"gemini": ".codex-bridge/gemini-key", "mistral": ".config/devstral/api_key",
             "openrouter": ".codex-bridge/openrouter-key"}
# The operator's canonical store (D2 amendment); the wrappers read it last.
PROJECTS_ENV = "Projects/.env"
# The wrappers' rule: a key file or ~/Projects/.env value shorter than this is a placeholder.
MIN_KEY_LEN = 20


def key_places(provider: str) -> list[str]:
    """The places read_key checks, in order, as ~ paths (names only, never a value)."""
    places = [str(key_store(Path("~")))]
    if provider in KEY_FILES: places.append(f"~/{KEY_FILES[provider]}")
    places.append(f"~/{PROJECTS_ENV}")
    return places


def _env_key(path: Path, provider: str, min_len: int = 1) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    found = {}
    for line in lines:
        name, sep, value = line.strip().partition("=")
        if sep and name.strip() in KEY_VARS.get(provider, ()):
            value = value.strip().strip('"').strip("'")
            if len(value) >= min_len: found.setdefault(name.strip(), value)
    for var in KEY_VARS.get(provider, ()):
        if var in found: return found[var]
    return None


def read_key(home: Path, provider: str) -> str | None:
    """The provider key, or None. Checked in order: the key store, the wrapper's key file, ~/Projects/.env. The value
    is returned to the caller only, never printed."""
    key = _env_key(key_store(home), provider)
    if key: return key
    if provider in KEY_FILES:
        try:
            value = (Path(home) / KEY_FILES[provider]).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            value = ""
        if len(value) >= MIN_KEY_LEN: return value
    return _env_key(Path(home) / PROJECTS_ENV, provider, MIN_KEY_LEN)


def scrub(text: str, key: str | None) -> str:
    return text.replace(key, "[key]") if key else text


def base_url(provider: str, env: dict) -> str:
    raw = env.get(URL_ENV.get(provider, ""), "")
    if raw:
        host = urllib.parse.urlsplit(raw).hostname or ""
        if host in LOOPBACK: return raw.rstrip("/")
    return HOSTS[provider]


def _gemini_request(base: str, slug: str, prompt: str, key: str) -> urllib.request.Request:
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    url = f"{base}/v1beta/models/{urllib.parse.quote(slug, safe='.-_')}:generateContent"
    return urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                  headers={"Content-Type": "application/json", "x-goog-api-key": key})


def _gemini_reply(data: dict) -> tuple[str, dict]:
    cands = data.get("candidates") or []
    parts = ((cands[0] or {}).get("content") or {}).get("parts") or [] if cands else []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought"))
    meta = data.get("usageMetadata") or {}
    usage = {"input_tokens": int(meta.get("promptTokenCount") or 0),
             "cached_input_tokens": int(meta.get("cachedContentTokenCount") or 0),
             "output_tokens": int(meta.get("candidatesTokenCount") or 0) + int(meta.get("thoughtsTokenCount") or 0)}
    if not text.strip():
        reason = (cands[0] or {}).get("finishReason") if cands else (data.get("promptFeedback") or {}).get("blockReason")
        raise StepError(EXIT_FAIL, f"WB_NATIVE_EMPTY_REPLY: the provider returned no text ({reason or 'no candidate'})")
    return text, usage


# Mistral and OpenRouter: the OpenAI-style chat completions shape, Bearer key (mask.sh, oask.sh).
CHAT_PATHS = {"mistral": "/v1/chat/completions", "openrouter": "/api/v1/chat/completions"}


def _chat_request(provider: str, base: str, slug: str, prompt: str, key: str) -> urllib.request.Request:
    body = {"model": slug, "messages": [{"role": "user", "content": prompt}]}
    # Mistral documents JSON mode for its chat models; OpenRouter free slugs vary, so they get the text protocol alone.
    if provider == "mistral": body["response_format"] = {"type": "json_object"}
    return urllib.request.Request(f"{base}{CHAT_PATHS[provider]}", data=json.dumps(body).encode(), method="POST",
                                  headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})


def _chat_reply(data: dict) -> tuple[str, dict]:
    choices = data.get("choices") or []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    content = (first.get("message") or {}).get("content")
    if isinstance(content, list):  # Mistral can answer with typed chunks
        content = "".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type", "text") == "text")
    text = content if isinstance(content, str) else ""
    meta = data.get("usage") or {}
    details = meta.get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else 0
    usage = {"input_tokens": int(meta.get("prompt_tokens") or 0), "cached_input_tokens": int(cached or 0),
             "output_tokens": int(meta.get("completion_tokens") or 0)}
    if not text.strip():
        reason = first.get("finish_reason") or ((data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else None)
        raise StepError(EXIT_FAIL, f"WB_NATIVE_EMPTY_REPLY: the provider returned no text ({reason or 'no choice'})")
    return text, usage


def _build(provider: str, base: str, slug: str, prompt: str, key: str) -> urllib.request.Request:
    if provider == "gemini": return _gemini_request(base, slug, prompt, key)
    return _chat_request(provider, base, slug, prompt, key)


def _parse(provider: str, data: dict) -> tuple[str, dict]:
    return _gemini_reply(data) if provider == "gemini" else _chat_reply(data)


def free_only(provider: str, slug: str) -> None:
    """The $0 rule (FR-013): an OpenRouter slug that does not end ':free' is refused before any request."""
    if provider == "openrouter" and not (isinstance(slug, str) and slug.endswith(":free")):
        raise StepError(EXIT_NOT_OFFERED, f"WB_NATIVE_NOT_FREE: OpenRouter slug {slug!r} is not a ':free' slug; not sent")


# Rate limits (429) and overload (503) are short: retry inside the step before the agent is called quota-paused.
RETRY_WAITS = (2.0, 5.0, 12.0)  # seconds before retry 1, 2, 3
RETRY_AFTER_CAP_S = 15.0  # a Retry-After header is honoured up to this
WAIT_BUDGET_S = 20.0  # total sleeping per call, well inside the 60 s step timeout
RETRY_WAITS_ENV, PACE_ENV, PACE_DIR_NAME = "AGENTS_INC_NATIVE_RETRY_WAITS", "AGENTS_INC_NATIVE_PACE_S", "native-pace"
# Minimum seconds between two requests to one provider (all agents, through a lock file per provider).
PACE_S = {"gemini": 1.0, "mistral": 1.1, "openrouter": 3.1}
PACE_DEFAULT_S = 1.0
# A body that says the daily or monthly quota is gone is not a passing rate limit: no retry.
_EXHAUSTED = re.compile(r"per[ -]?day|per[ -]?month|daily|monthly|day limit|month limit|RequestsPerDay|exhausted", re.I)


def is_loopback(base: str) -> bool:
    return urllib.parse.urlsplit(base).hostname in LOOPBACK


def live_policy(provider: str, env: dict, retries: int, state: Path | None) -> dict:
    """Keyword arguments for `ask`: retries, waits and pacing for a live provider. A loopback test server gets none of it
    unless AGENTS_INC_NATIVE_RETRY_WAITS (comma list of seconds) or AGENTS_INC_NATIVE_PACE_S is set."""
    if provider not in HOSTS: return {}
    loop = is_loopback(base_url(provider, env))
    out: dict = {"retries": 0 if loop else retries, "pace_dir": None if loop else state}
    raw = env.get(RETRY_WAITS_ENV)
    if raw is not None:
        out["waits"] = tuple(float(x) for x in raw.split(",") if x.strip())
        out["retries"] = retries
    if env.get(PACE_ENV) is not None: out["pace_dir"] = state
    return out


def pace_gap(provider: str, env: dict | None = None) -> float:
    raw = (os.environ if env is None else env).get(PACE_ENV)
    try: return max(0.0, float(raw)) if raw is not None else PACE_S.get(provider, PACE_DEFAULT_S)
    except ValueError: return PACE_S.get(provider, PACE_DEFAULT_S)


def pace(provider: str, state: Path, gap: float, sleep=time.sleep, clock=time.time) -> None:
    """Wait until `gap` seconds after the last request to this provider, then stamp now. The stamp file is locked, so
    parallel agents queue behind each other. Best effort: a lock or file error skips the pacing."""
    if gap <= 0: return
    try:
        import fcntl
        folder = Path(state) / PACE_DIR_NAME
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / provider, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0)
            try: last = float(fh.read().strip() or 0)
            except ValueError: last = 0.0
            wait = last + gap - clock()
            if 0 < wait <= gap: sleep(wait)
            fh.seek(0); fh.truncate(); fh.write(repr(clock()))
    except (OSError, ImportError):
        return


def _retry_after(exc) -> float | None:
    try: return max(0.0, float(exc.headers.get("Retry-After")))
    except (TypeError, ValueError, AttributeError): return None


def ask(provider: str, slug: str, prompt: str, key: str, *, max_chars: int, timeout: float,
        env: dict | None = None, retries: int = 0, waits: tuple = RETRY_WAITS, sleep=time.sleep,
        pace_dir: Path | None = None, stats: dict | None = None, on_retry=None) -> tuple[str, dict]:
    """One request, with up to `retries` retries on 429 or 503 after bounded waits (Retry-After honoured, capped; total
    wait at most WAIT_BUDGET_S) and a per-provider pace when `pace_dir` is set. `stats["retries"]` counts the retries made.
    Returns (reply text, usage). Raises StepError with the exit code and a scrubbed line."""
    used = 0
    slept = 0.0
    while True:
        try:
            if pace_dir is not None: pace(provider, pace_dir, pace_gap(provider, env), sleep)
            return _ask_once(provider, slug, prompt, key, max_chars=max_chars, timeout=timeout, env=env)
        except _Retryable as r:
            wait = min(r.after, RETRY_AFTER_CAP_S) if r.after is not None else (waits[used] if used < len(waits) else waits[-1] if waits else 0.0)
            if r.exhausted or used >= retries or slept + wait > WAIT_BUDGET_S:
                err = r.error
                if used: err.text += f" (after {used} retries)"; err.args = (err.text,)
                raise err from None
            used += 1
            slept += wait
            if stats is not None: stats["retries"] = used
            if on_retry: on_retry(used, retries, wait)
            sleep(wait)


class _Retryable(Exception):
    def __init__(self, error: StepError, after: float | None, exhausted: bool):
        super().__init__(error.text)
        self.error, self.after, self.exhausted = error, after, exhausted


def _ask_once(provider: str, slug: str, prompt: str, key: str, *, max_chars: int, timeout: float,
              env: dict | None = None) -> tuple[str, dict]:
    if provider not in HOSTS: raise StepError(EXIT_NOT_OFFERED, f"WB_NATIVE_UNKNOWN_PROVIDER: {provider}")
    free_only(provider, slug)
    if len(prompt) > max_chars:
        raise StepError(EXIT_USAGE, f"WB_NATIVE_CONTEXT_OVER: context over {max_chars} chars (prompt {len(prompt)} chars); not sent")
    base = base_url(provider, os.environ if env is None else env)
    host = urllib.parse.urlsplit(base).hostname
    req = _build(provider, base, slug, prompt, key)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise StepError(EXIT_FAIL, f"{provider} {slug} answered HTTP {exc.code}: redirect refused") from None
        detail = scrub(exc.read().decode("utf-8", "replace")[:300].replace("\n", " "), key)
        retry_after = _retry_after(exc)
        exc.close()
        if exc.code == 429:
            raise _Retryable(StepError(EXIT_QUOTA, f"{provider} {slug} hit a usage or rate limit (HTTP 429): {detail}"),
                             retry_after, bool(_EXHAUSTED.search(detail))) from None
        if exc.code == 503:
            raise _Retryable(StepError(EXIT_FAIL, f"{provider} {slug} answered HTTP 503: {detail}"), retry_after, False) from None
        raise StepError(EXIT_FAIL, f"{provider} {slug} answered HTTP {exc.code}: {detail}") from None
    except (TimeoutError, socket.timeout):
        raise StepError(EXIT_TIMEOUT, f"WB_NATIVE_TIMEOUT: no reply from {host} within {timeout:g} s") from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise StepError(EXIT_TIMEOUT, f"WB_NATIVE_TIMEOUT: no reply from {host} within {timeout:g} s") from None
        raise StepError(EXIT_BLOCKED, f"WB_NATIVE_HOST_BLOCKED: cannot reach {host}: {scrub(str(exc.reason), key)}") from None
    except OSError as exc:
        raise StepError(EXIT_BLOCKED, f"WB_NATIVE_HOST_BLOCKED: cannot reach {host}: {scrub(str(exc), key)}") from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise StepError(EXIT_FAIL, f"WB_NATIVE_BAD_RESPONSE: {provider} answered with no JSON body") from None
    return _parse(provider, data if isinstance(data, dict) else {})


def progress(err, kind: str, data: dict) -> None:
    """One line in the format native/loop.ts parses (`agents-inc run: event|usage|record <json>`)."""
    err.write(f"{PROGRESS} {kind} {json.dumps(data)}\n")
    err.flush()
