#!/usr/bin/env bash
set -euo pipefail

# codex-bridge oask: Send a prompt to OpenRouter API (free tier only)
# Usage: oask.sh [--file PATH]... [--glob PATTERN] [--raw] ["prompt"]

if [[ "${WORKERBEES_GOVERNANCE:-off}" != "off" ]]; then
  echo "oask: REFUSED — legacy wrappers are disabled in governed lanes" >&2
  exit 3
fi

# Check required tools
command -v jq >/dev/null || { echo "error: jq required" >&2; exit 1; }

KEY_DIR="$HOME/.codex-bridge"
KEY_FILE="$KEY_DIR/openrouter-key"
USAGE_LOG="$KEY_DIR/usage.jsonl"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Defaults
if [[ -z "${MODEL:-}" ]]; then
  set +e
  MODEL=$(PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 -m agents_inc.free_health pick-default --provider openrouter --task "${TASK:-summarize}")
  PICK_STATUS=$?
  set -e
  if [[ $PICK_STATUS -ne 0 ]]; then
    exit 3
  fi
fi
RAW=false
OASK_TIMEOUT="${OASK_TIMEOUT:-180}"
OASK_CONNECT_TIMEOUT="${OASK_CONNECT_TIMEOUT:-10}"
PROMPT=""
DECLARE_FILES=()
DECLARE_GLOBS=()
RESOLVED_FILES=()

# SPEND GUARD: operator rule is spend nothing on OpenRouter.
# Only ":free" models are permitted. Paid model IDs are refused outright.
check_spend_guard() {
  case "$MODEL" in
    *:free) ;;
    *)
      echo "oask: REFUSED — '$MODEL' is not a ':free' model." >&2
      echo "oask: operator rule is spend nothing on OpenRouter." >&2
      exit 3
      ;;
  esac
}

# Exit-trap outcome reporting: classifies the last HTTP response (if any) and
# reports it via free_health, without altering the wrapper's own exit code.
OASK_ATTEMPTED=false
OASK_REPORT_STATUS=""
OASK_REPORT_BODY_FILE=""
oask_report_trap() {
  local ec=$?
  [[ "$OASK_ATTEMPTED" == true ]] || exit $ec
  local outcome="error"
  local retry=""
  if [[ -n "$OASK_REPORT_STATUS" ]]; then
    local classify_out
    classify_out=$(PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 -m agents_inc.free_health classify \
      --status "$OASK_REPORT_STATUS" --body-file "${OASK_REPORT_BODY_FILE:-/dev/null}" 2>/dev/null) || classify_out=""
    if [[ -n "$classify_out" ]]; then
      outcome="${classify_out%% *}"
      retry="${classify_out#* }"
      [[ "$retry" == "-" ]] && retry=""
    fi
  fi
  local retry_arg=()
  [[ -n "$retry" ]] && retry_arg=(--retry-after "$retry")
  PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 -m agents_inc.free_health report \
    --provider openrouter --model "$MODEL" --outcome "$outcome" "${retry_arg[@]+${retry_arg[@]}}" \
    >/dev/null 2>"${TMPDIR:-/tmp}/oask_report_err.$$" || echo "oask: health report failed" >&2
  if [[ "$outcome" != "withdrawn" ]] && [[ "$outcome" != "zdr" ]]; then
    local result="ok"
    [[ "$outcome" != "ok" ]] && result="transient"
    local msg="$outcome"
    [[ -n "${OASK_REPORT_STATUS:-}" ]] && msg="$outcome http $OASK_REPORT_STATUS"
    CODEX_BRIDGE_MODE=standard bash "$SCRIPT_DIR/route.sh" report openrouter "$result" "$msg" >/dev/null 2>&1 || true
  fi
  rm -f "${TMPDIR:-/tmp}/oask_report_err.$$" "$OASK_REPORT_BODY_FILE" 2>/dev/null
  exit $ec
}
trap oask_report_trap EXIT

# Load key from env or file; OPENROUTER_API_KEY wins over the legacy OPEN_ROUTER_API_KEY name
OPEN_ROUTER_API_KEY="${OPENROUTER_API_KEY:-${OPEN_ROUTER_API_KEY:-}}"
if [[ -z "${OPEN_ROUTER_API_KEY:-}" ]]; then
  if [[ -f "$KEY_FILE" ]]; then
    OPEN_ROUTER_API_KEY=$(cat "$KEY_FILE")
  fi
fi

# Fallback: read from ~/Projects/.env if key is missing/empty/placeholder
if [[ -z "${OPEN_ROUTER_API_KEY:-}" ]] || [[ ${#OPEN_ROUTER_API_KEY} -lt 20 ]]; then
  if [[ -f "$HOME/Projects/.env" ]]; then
    ENV_KEY=$(grep -m1 -E '^OPENROUTER_API_KEY=' "$HOME/Projects/.env" 2>/dev/null | cut -d= -f2- || true)
    [[ -n "$ENV_KEY" ]] || ENV_KEY=$(grep -m1 -E '^OPEN_ROUTER_API_KEY=' "$HOME/Projects/.env" 2>/dev/null | cut -d= -f2- || true)
    if [[ -n "$ENV_KEY" ]]; then
      ENV_KEY="${ENV_KEY%\"}"
      ENV_KEY="${ENV_KEY#\"}"
      if [[ ${#ENV_KEY} -ge 20 ]]; then
        OPEN_ROUTER_API_KEY="$ENV_KEY"
      fi
    fi
  fi
fi

if [[ -z "${OPEN_ROUTER_API_KEY:-}" ]] || [[ ${#OPEN_ROUTER_API_KEY} -lt 20 ]]; then
  echo "oask error: no API key (checked $KEY_FILE and ~/Projects/.env OPEN_ROUTER_API_KEY|OPENROUTER_API_KEY)" >&2
  exit 2
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      DECLARE_FILES+=("$2")
      shift 2
      ;;
    --glob)
      DECLARE_GLOBS+=("$2")
      shift 2
      ;;
    --list)
      # List free models
      curl -sS -m 30 https://openrouter.ai/api/v1/models | python3 -c '
import sys, json
d = json.load(sys.stdin)
free = [m for m in d["data"]
        if float(m.get("pricing", {}).get("prompt", 1) or 0) == 0
        and float(m.get("pricing", {}).get("completion", 1) or 0) == 0]
for m in sorted(free, key=lambda x: -(x.get("context_length") or 0)):
    print("%-55s ctx=%s" % (m["id"], m.get("context_length")))
'
      exit 0
      ;;
    --raw)
      RAW=true
      shift
      ;;
    *)
      if [[ "$1" == --* ]]; then
        echo "oask: unknown flag: $1" >&2
        exit 2
      fi
      if [[ -n "$PROMPT" ]]; then
        echo "oask: more than one prompt argument; quote the prompt or use stdin" >&2
        exit 2
      fi
      # Positional: prompt text
      PROMPT="$1"
      shift
      ;;
  esac
done

# Read from stdin if no prompt provided
if [[ -z "$PROMPT" ]]; then
  PROMPT=$(cat)
fi

if [[ -z "$PROMPT" ]]; then
  echo "error: no prompt provided" >&2
  exit 1
fi

# Check spend guard BEFORE any API call
check_spend_guard

# Expand --glob patterns
RESOLVED_FILES=("${DECLARE_FILES[@]:-}")
if (( ${#DECLARE_GLOBS[@]} )); then
  for pattern in "${DECLARE_GLOBS[@]}"; do
    while IFS= read -r match; do
      RESOLVED_FILES+=("$match")
    done < <(compgen -G "$pattern" || true)
  done
fi

# Build request body with python3
export PROMPT
export MODEL
export RESOLVED_FILES_JSON

RESOLVED_FILES_JSON=$(python3 -c "
import json
import sys

files = []
for fpath in sys.argv[1:]:
    if not fpath:  # Skip empty paths
        continue
    try:
        with open(fpath, 'r') as f:
            content = f.read()
            files.append({'type': 'file', 'path': fpath, 'content': content})
    except Exception as e:
        sys.stderr.write(f'warning: could not read {fpath}: {e}\n')

print(json.dumps(files))
" "${RESOLVED_FILES[@]:-}")

# Build API request body
BODY=$(python3 << 'PYTHON'
import json
import os
import sys

prompt_text = os.environ["PROMPT"]
files_json = os.environ["RESOLVED_FILES_JSON"]

try:
    files = json.loads(files_json)
except:
    files = []

# Combine file contents with prompt text
if files:
    file_lines = []
    for f in files:
        file_lines.append(f"[{f.get('path', 'unknown')}]\n{f.get('content', '')}")
    file_context = "\n\n---\nAttached files:\n" + "\n".join(file_lines)
    content = prompt_text + file_context
else:
    content = prompt_text

body = {
    "model": os.environ["MODEL"],
    "messages": [
        {"role": "user", "content": content}
    ]
}

print(json.dumps(body))
PYTHON
)

# Make request
OASK_ATTEMPTED=true
OASK_RESPONSE_FILE=$(mktemp "${TMPDIR:-/tmp}/oask_response.XXXXXX")
HTTP_CODE=$(curl -sS -w "%{http_code}" -o "$OASK_RESPONSE_FILE" \
  -m "$OASK_TIMEOUT" \
  --connect-timeout "$OASK_CONNECT_TIMEOUT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPEN_ROUTER_API_KEY" \
  -H "X-Title: codex-bridge" \
  -X POST https://openrouter.ai/api/v1/chat/completions \
  -d "$BODY")

RESPONSE=$(cat "$OASK_RESPONSE_FILE")
OASK_REPORT_STATUS="$HTTP_CODE"
OASK_REPORT_BODY_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/bridge.XXXXXX"})
cp "$OASK_RESPONSE_FILE" "$OASK_REPORT_BODY_FILE" 2>/dev/null || echo -n "$RESPONSE" > "$OASK_REPORT_BODY_FILE"
rm -f "$OASK_RESPONSE_FILE"

# Check HTTP status
if [[ "$HTTP_CODE" != "200" ]]; then
  ERROR_TEXT=$(echo "$RESPONSE" | head -c 300)
  if echo "$RESPONSE" | jq -e '.error.message' >/dev/null 2>&1; then
    MESSAGE=$(echo "$RESPONSE" | jq -r '.error.message')
    echo "oask error $HTTP_CODE: $MESSAGE" >&2
  else
    echo "oask error $HTTP_CODE: $ERROR_TEXT" >&2
  fi
  exit 1
fi

# Check for API error in 200 response
if echo "$RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  MESSAGE=$(echo "$RESPONSE" | jq -r '.error.message // .error // "unknown error"')
  echo "oask error: $MESSAGE" >&2
  exit 1
fi

# Check for empty/blocked completion
if ! echo "$RESPONSE" | jq -e '.choices[0]' >/dev/null 2>&1; then
  FINISH_REASON=$(echo "$RESPONSE" | jq -r '.choices[0].finish_reason // "UNKNOWN"' 2>/dev/null || echo "UNKNOWN")
  echo "oask returned no content (finish_reason: $FINISH_REASON)" >&2
  exit 1
fi

# Extract response text
RESP_TEXT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // ""' 2>/dev/null)

if [[ -z "$RESP_TEXT" ]]; then
  echo "oask returned no content" >&2
  exit 1
fi

# Detect redaction placeholders in reply not in request
PLACEHOLDERS=""
PLACEHOLDER_PATTERN='\[(PERSON|PERSON_NAME|EMAIL|EMAIL_ADDRESS|PHONE|PHONE_NUMBER|ADDRESS|LOCATION|ORGANIZATION|CREDIT_CARD|IP_ADDRESS|US_SSN|SSN|IBAN_CODE|DATE_TIME|URL)\]'
FOUND_PLACEHOLDERS=$(echo "$RESP_TEXT" | grep -oE "$PLACEHOLDER_PATTERN" | sort -u || echo "")

if [[ -n "$FOUND_PLACEHOLDERS" ]]; then
  UNIQUE_PLACEHOLDERS=""
  while IFS= read -r placeholder; do
    if ! grep -qF -- "$placeholder" <<< "$BODY"; then
      UNIQUE_PLACEHOLDERS="$UNIQUE_PLACEHOLDERS $placeholder"
    fi
  done <<< "$FOUND_PLACEHOLDERS"
  PLACEHOLDERS="${UNIQUE_PLACEHOLDERS# }"
fi

# Extract usage (OpenAI-compatible format)
PROMPT_TOKENS=$(echo "$RESPONSE" | jq -r '.usage.prompt_tokens // 0' 2>/dev/null)
OUTPUT_TOKENS=$(echo "$RESPONSE" | jq -r '.usage.completion_tokens // 0' 2>/dev/null)

# Output response
if [[ "$RAW" == true ]]; then
  echo "$RESPONSE"
else
  echo "$RESP_TEXT"
  echo "[openrouter $MODEL | in $PROMPT_TOKENS out $OUTPUT_TOKENS]" >&2
fi

if [[ -n "$PLACEHOLDERS" ]]; then
  echo "oask: reply holds redaction placeholders not in the request: $PLACEHOLDERS; unfit for code review (exit 4)" >&2
fi

# Log to both JSONL and SQLite
python3 << PYTHON_LOG
import json
import os
from datetime import datetime, timezone

log_file = "$USAGE_LOG"
db_path = os.path.expanduser("~/.codex-bridge/usage.db")

# JSONL log (append-only)
try:
    os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)
    if not os.path.exists(log_file):
        open(log_file, 'a').close()
        os.chmod(log_file, 0o600)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "backend": "openrouter",
        "model": "$MODEL",
        "input_tokens": $PROMPT_TOKENS,
        "output_tokens": $OUTPUT_TOKENS
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(record) + '\n')
except Exception:
    pass

# SQLite row comes from usage_db.ingest_delegated_usage (sha1 uid); no direct insert here.
PYTHON_LOG

if [[ -n "$PLACEHOLDERS" ]]; then
  exit 4
fi
