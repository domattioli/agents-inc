#!/usr/bin/env bash
set -euo pipefail

# codex-bridge mask: Send a prompt to the Mistral API
# Usage: mask.sh [--tier cheap|code|deep] [--agent] [--reset] [--file PATH]... [--raw] ["prompt"]

if [[ "${WORKERBEES_GOVERNANCE:-off}" != "off" ]]; then
  echo "mask: REFUSED — legacy wrappers are disabled in governed lanes" >&2
  exit 3
fi

command -v python3 >/dev/null || { echo "error: python3 required" >&2; exit 1; }

KEY_FILE="$HOME/.config/devstral/api_key"
AGENT_ID_FILE="$HOME/.config/devstral/agent_id"
USAGE_LOG="$HOME/.codex-bridge/usage.jsonl"
CONVERSATION_FILE="$HOME/.codex-bridge/mistral-conversation-id"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Exit-trap outcome reporting: the python block below writes the observed
# HTTP status (if any) and response body to these temp files; the trap
# classifies and reports them via free_health without changing mask's exit code.
MASK_STATUS_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/bridge.XXXXXX"})
MASK_BODY_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/bridge.XXXXXX"})
export MASK_STATUS_FILE MASK_BODY_FILE
MASK_ATTEMPTED=false
mask_report_trap() {
  local ec=$?
  local status=""
  [[ -s "$MASK_STATUS_FILE" ]] && status=$(cat "$MASK_STATUS_FILE")
  local outcome="error"
  local retry=""
  if [[ -n "$status" ]]; then
    local classify_out
    classify_out=$(PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 -m agents_inc.free_health classify \
      --status "$status" --body-file "$MASK_BODY_FILE" 2>/dev/null) || classify_out=""
    if [[ -n "$classify_out" ]]; then
      outcome="${classify_out%% *}"
      retry="${classify_out#* }"
      [[ "$retry" == "-" ]] && retry=""
    fi
  fi
  local retry_arg=()
  [[ -n "$retry" ]] && retry_arg=(--retry-after "$retry")
  local message=""
  if [[ "$outcome" == "error" ]]; then
    if [[ -s "$MASK_BODY_FILE" ]]; then
      message=$(head -c 300 "$MASK_BODY_FILE")
    else
      message="Connection failed"
    fi
  fi
  local message_arg=()
  [[ -n "$message" ]] && message_arg=(--message "$message")
  PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 -m agents_inc.free_health report \
    --provider mistral --model "${MODEL:-unknown}" --outcome "$outcome" "${retry_arg[@]+${retry_arg[@]}}" "${message_arg[@]+${message_arg[@]}}" \
    >/dev/null 2>"${TMPDIR:-/tmp}/mask_report_err.$$" || echo "mask: health report failed" >&2
  if [[ "$MASK_ATTEMPTED" == true ]] && [[ "$outcome" != "withdrawn" ]] && [[ "$outcome" != "zdr" ]]; then
    local result="ok"
    [[ "$outcome" != "ok" ]] && result="transient"
    local msg=""
    [[ -n "$message" ]] && msg="$message"
    [[ -z "$msg" ]] && [[ -n "$status" ]] && msg="$outcome http $status"
    [[ -z "$msg" ]] && msg="$outcome"
    CODEX_BRIDGE_MODE=standard bash "$SCRIPT_DIR/route.sh" report mistral "$result" "$msg" >/dev/null 2>&1 || true
  fi
  rm -f "${TMPDIR:-/tmp}/mask_report_err.$$" "$MASK_STATUS_FILE" "$MASK_BODY_FILE" 2>/dev/null
  exit $ec
}
trap mask_report_trap EXIT

MODEL=""
TIER="code"
RAW=false
AGENT=false
RESET=false
MASK_TIMEOUT="${MASK_TIMEOUT:-180}"
MASK_AGENT_TIMEOUT="${MASK_AGENT_TIMEOUT:-900}"
PROMPT=""
DECLARE_FILES=()

tier_to_model() {
  case "$1" in
    cheap) echo "ministral-3b-latest" ;;
    code) echo "codestral-latest" ;;
    deep) echo "mistral-large-latest" ;;
    *) echo "error: invalid tier '$1' (expected cheap, code, or deep)" >&2; return 2 ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier)
      [[ $# -ge 2 ]] || { echo "error: --tier requires a value" >&2; exit 2; }
      TIER="$2"
      shift 2
      ;;
    --file)
      [[ $# -ge 2 ]] || { echo "error: --file requires a path" >&2; exit 2; }
      DECLARE_FILES+=("$2")
      shift 2
      ;;
    --agent)
      AGENT=true
      shift
      ;;
    --reset)
      RESET=true
      shift
      ;;
    --raw)
      RAW=true
      shift
      ;;
    *)
      if [[ "$1" == --* ]]; then
        echo "mask: unknown flag: $1" >&2
        exit 2
      fi
      if [[ -n "$PROMPT" ]]; then
        echo "mask: more than one prompt argument; quote the prompt or use stdin" >&2
        exit 2
      fi
      PROMPT="$1"
      shift
      ;;
  esac
done

if [[ -z "$PROMPT" ]]; then
  PROMPT=$(cat)
fi

if [[ -z "$PROMPT" ]]; then
  echo "error: no prompt provided" >&2
  exit 1
fi

MODEL=$(tier_to_model "$TIER")

KEY="${MISTRAL_API_KEY:-}"
if [[ -z "$KEY" ]] && [[ -f "$KEY_FILE" ]]; then
  KEY=$(cat "$KEY_FILE")
fi

# Fallback: read from ~/Projects/.env if key is missing/empty/placeholder
if [[ -z "$KEY" ]] || [[ ${#KEY} -lt 20 ]]; then
  if [[ -f "$HOME/Projects/.env" ]]; then
    ENV_KEY=$(grep -m1 -E '^MISTRAL_API_KEY=' "$HOME/Projects/.env" 2>/dev/null | cut -d= -f2- || true)
    if [[ -n "$ENV_KEY" ]]; then
      ENV_KEY="${ENV_KEY%\"}"
      ENV_KEY="${ENV_KEY#\"}"
      if [[ ${#ENV_KEY} -ge 20 ]]; then
        KEY="$ENV_KEY"
      fi
    fi
  fi
fi

if [[ -z "$KEY" ]] || [[ ${#KEY} -lt 20 ]]; then
  echo "mask error: no API key (checked $KEY_FILE and ~/Projects/.env MISTRAL_API_KEY)" >&2
  exit 2
fi

AGENT_ID=""
if [[ "$AGENT" == true ]]; then
  AGENT_ID="${MISTRAL_AGENT_ID:-}"
  if [[ -z "$AGENT_ID" && -f "$AGENT_ID_FILE" ]]; then
    AGENT_ID=$(cat "$AGENT_ID_FILE")
  fi
  if [[ -z "$AGENT_ID" ]]; then
    echo "mistral agent id not found: $AGENT_ID_FILE (set MISTRAL_AGENT_ID or write the id to that file, chmod 600)" >&2
    exit 1
  fi
fi

export MISTRAL_API_KEY="$KEY"
export MISTRAL_AGENT_ID="$AGENT_ID"
export MODEL PROMPT RAW USAGE_LOG CONVERSATION_FILE AGENT RESET MASK_TIMEOUT MASK_AGENT_TIMEOUT

MASK_ATTEMPTED=true
python3 - "${DECLARE_FILES[@]:-}" <<'PYTHON'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
import tempfile

chat_endpoint = "https://api.mistral.ai/v1/chat/completions"
conversations_endpoint = "https://api.mistral.ai/v1/conversations"
model = os.environ["MODEL"]
prompt = os.environ["PROMPT"]
raw = os.environ.get("RAW") == "true"
agent = os.environ.get("AGENT") == "true"
reset = os.environ.get("RESET") == "true"
usage_log = os.environ["USAGE_LOG"]
conversation_file = os.environ["CONVERSATION_FILE"]
api_key = os.environ["MISTRAL_API_KEY"]
agent_id = os.environ.get("MISTRAL_AGENT_ID", "")
request_timeout = float(os.environ["MASK_AGENT_TIMEOUT"] if agent else os.environ["MASK_TIMEOUT"])
request_kind = "agent" if agent else "completion"

mask_status_file = os.environ.get("MASK_STATUS_FILE", "")
mask_body_file = os.environ.get("MASK_BODY_FILE", "")


def _write_report_files(status_code, body_bytes):
    """Best-effort: record HTTP status + body for the outer bash exit trap."""
    try:
        if mask_status_file:
            with open(mask_status_file, "w", encoding="utf-8") as fh:
                fh.write(str(status_code))
        if mask_body_file:
            with open(mask_body_file, "wb") as fh:
                fh.write(body_bytes or b"")
    except OSError:
        pass

file_blocks = []
for path in sys.argv[1:]:
    if not os.path.isfile(path):
        continue
    try:
        with open(path, "rb") as handle:
            content = handle.read().decode("utf-8", errors="replace")
        file_blocks.append(f"=== {path} ===\n{content}")
    except OSError:
        pass

combined_prompt = "\n\n".join(file_blocks + [prompt])
conversation_id = ""
if agent:
    if not reset:
        try:
            with open(conversation_file, "r", encoding="utf-8") as handle:
                conversation_id = handle.read().strip()
        except OSError:
            pass
    if conversation_id:
        endpoint = f"{conversations_endpoint}/{urllib.parse.quote(conversation_id, safe='')}"
        request_body = {"inputs": combined_prompt}
    else:
        endpoint = conversations_endpoint
        request_body = {"agent_id": agent_id, "inputs": combined_prompt}
else:
    endpoint = chat_endpoint
    request_body = {
        "model": model,
        "messages": [{"role": "user", "content": combined_prompt}],
    }

body = json.dumps(request_body).encode("utf-8")
request = urllib.request.Request(
    endpoint,
    data=body,
    method="POST",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
)

try:
    with urllib.request.urlopen(request, timeout=request_timeout) as response:
        response_bytes = response.read()
        _write_report_files(response.getcode() or 200, response_bytes)
except urllib.error.HTTPError as exc:
    error_bytes = exc.read()
    _write_report_files(exc.code, error_bytes)
    try:
        error_data = json.loads(error_bytes.decode("utf-8", errors="replace"))
        message = error_data.get("message") or error_data.get("detail") or str(error_data)
    except (json.JSONDecodeError, AttributeError):
        message = error_bytes.decode("utf-8", errors="replace")[:300] or exc.reason
    for secret in (api_key, agent_id, conversation_id):
        if secret:
            message = str(message).replace(secret, "[redacted]")
    print(f"mistral error {exc.code}: {message}", file=sys.stderr)
    raise SystemExit(1)
except TimeoutError as exc:
    print(f"mistral {request_kind} timeout after {request_timeout:g}s: {exc}", file=sys.stderr)
    raise SystemExit(1)
except urllib.error.URLError as exc:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, TimeoutError):
        print(f"mistral {request_kind} timeout after {request_timeout:g}s: {reason}", file=sys.stderr)
        raise SystemExit(1)
    print(f"mistral error: cannot reach api.mistral.ai: {reason}", file=sys.stderr)
    raise SystemExit(1)
except OSError as exc:
    reason = getattr(exc, "reason", exc)
    print(f"mistral error: cannot reach api.mistral.ai: {reason}", file=sys.stderr)
    raise SystemExit(1)

response_text = response_bytes.decode("utf-8", errors="replace")
try:
    data = json.loads(response_text)
except json.JSONDecodeError:
    print("mistral error: API returned invalid JSON", file=sys.stderr)
    raise SystemExit(1)

response_model = model
if agent:
    assistant_parts = []
    response_model = None
    for entry in data.get("outputs") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "message.output" or entry.get("role") != "assistant":
            continue
        entry_model = entry.get("model")
        if isinstance(entry_model, str) and entry_model:
            response_model = entry_model
        content = entry.get("content")
        if isinstance(content, str):
            assistant_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        assistant_parts.append(text)
    assistant_text = "\n".join(part for part in assistant_parts if part)
else:
    try:
        assistant_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        assistant_text = ""
if not isinstance(assistant_text, str) or not assistant_text:
    kind = " agent" if agent else ""
    print(f"mistral{kind} returned no assistant content", file=sys.stderr)
    raise SystemExit(1)

usage = data.get("usage") or {}
input_tokens = int(usage.get("prompt_tokens") or 0)
output_tokens = int(usage.get("completion_tokens") or 0)

if agent:
    new_conversation_id = data.get("conversation_id")
    if isinstance(new_conversation_id, str) and new_conversation_id:
        try:
            state_dir = os.path.dirname(conversation_file)
            os.makedirs(state_dir, mode=0o700, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=state_dir, delete=False
            ) as handle:
                handle.write(new_conversation_id)
                temporary_path = handle.name
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, conversation_file)
        except OSError:
            pass

if raw:
    print(response_text)
else:
    print(assistant_text)
    print(f"[mistral {response_model or 'unknown'} | in {input_tokens} out {output_tokens}]", file=sys.stderr)

try:
    os.makedirs(os.path.dirname(usage_log), exist_ok=True)
    if not os.path.exists(usage_log):
        open(usage_log, "a", encoding="utf-8").close()
        os.chmod(usage_log, 0o600)
    record = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "backend": "mistral",
        "model": response_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    with open(usage_log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
except OSError:
    pass

# SQLite row comes from usage_db.ingest_delegated_usage (sha1 uid); no direct insert here.
PYTHON
