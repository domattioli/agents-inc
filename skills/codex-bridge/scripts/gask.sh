#!/usr/bin/env bash
set -euo pipefail

# codex-bridge gask: Send a prompt to Gemini API
# Usage: gask.sh [--tier digest|cheap|deep] [--file PATH]... [--glob PATTERN] [--raw] [--plain] ["prompt"]

if [[ "${WORKERBEES_GOVERNANCE:-off}" != "off" ]]; then
  echo "gask: REFUSED — legacy wrappers are disabled in governed lanes" >&2
  exit 3
fi

# Check required tools
command -v jq >/dev/null || { echo "error: jq required" >&2; exit 1; }

KEY_DIR="$HOME/.codex-bridge"
KEY_FILE="$KEY_DIR/gemini-key"
USAGE_LOG="$KEY_DIR/usage.jsonl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Exit-trap outcome reporting state (merged with temp-file cleanup below).
GASK_ATTEMPTED=false
GASK_REPORT_STATUS=""
GASK_REPORT_BODY_FILE=""
GASK_CLEANUP_FILES=()
gask_report_trap() {
  local ec=$?
  if [[ "$GASK_ATTEMPTED" == true ]]; then
    local outcome="error"
    local retry=""
    if [[ -n "$GASK_REPORT_STATUS" ]]; then
      local classify_out
      classify_out=$(PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 -m agents_inc.free_health classify \
        --status "$GASK_REPORT_STATUS" --body-file "${GASK_REPORT_BODY_FILE:-/dev/null}" 2>/dev/null) || classify_out=""
      if [[ -n "$classify_out" ]]; then
        outcome="${classify_out%% *}"
        retry="${classify_out#* }"
        [[ "$retry" == "-" ]] && retry=""
      fi
    fi
    local retry_arg=()
    [[ -n "$retry" ]] && retry_arg=(--retry-after "$retry")
    PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 -m agents_inc.free_health report \
      --provider gemini --model "${MODEL:-gemini-3.8-flash}" --outcome "$outcome" "${retry_arg[@]+${retry_arg[@]}}" \
      >/dev/null 2>/dev/null || echo "gask: health report failed" >&2
  fi
  rm -f ${GASK_CLEANUP_FILES[@]+"${GASK_CLEANUP_FILES[@]}"} 2>/dev/null
  exit $ec
}
trap gask_report_trap EXIT

# Defaults
MODEL=""
TIER="digest"
RAW=false
PLAIN=false
GASK_TIMEOUT="${GASK_TIMEOUT:-900}"
GASK_CONNECT_TIMEOUT="${GASK_CONNECT_TIMEOUT:-10}"
PROMPT=""
DECLARE_FILES=()
DECLARE_GLOBS=()
RESOLVED_FILES=()

# Tier → model mapping function
tier_to_model() {
  case "$1" in
    digest) echo "gemini-3.8-flash" ;;
    cheap) echo "gemini-flash-lite-latest" ;;
    deep) echo "gemini-3.1-pro-preview" ;;
    *) echo "gemini-3.8-flash" ;;
  esac
}

# Load key from file
KEY=""
if [[ -f "$KEY_FILE" ]]; then
  KEY=$(cat "$KEY_FILE")
fi

# Fallback: read from ~/Projects/.env if key is missing/empty/placeholder
if [[ -z "$KEY" ]] || [[ ${#KEY} -lt 20 ]]; then
  if [[ -f "$HOME/Projects/.env" ]]; then
    ENV_KEY=$(grep -m1 -E '^(GEMINI_API_KEY|GOOGLE_API_KEY)=' "$HOME/Projects/.env" 2>/dev/null | cut -d= -f2- || true)
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
  echo "gask error: no API key (checked $KEY_FILE and ~/Projects/.env GEMINI_API_KEY|GOOGLE_API_KEY)" >&2
  exit 2
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier)
      TIER="$2"
      shift 2
      ;;
    --file)
      DECLARE_FILES+=("$2")
      shift 2
      ;;
    --glob)
      DECLARE_GLOBS+=("$2")
      shift 2
      ;;
    --raw)
      RAW=true
      shift
      ;;
    --plain)
      PLAIN=true
      shift
      ;;
    *)
      if [[ "$1" == --* ]]; then
        echo "gask: unknown flag: $1" >&2
        exit 2
      fi
      if [[ -n "$PROMPT" ]]; then
        echo "gask: more than one prompt argument; quote the prompt or use stdin" >&2
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

MODEL=$(tier_to_model "$TIER")

# Wrap prompt with plain-language instruction if --plain is set
if [[ "$PLAIN" == true ]]; then
  PROMPT="Rewrite the following text in plain, clear language. Preserve every fact, number, and code block exactly. Do not add filler, hedging, or exclamation points. Keep it concise.

$PROMPT"
fi

# Expand --glob patterns
RESOLVED_FILES=("${DECLARE_FILES[@]:-}")
for pattern in "${DECLARE_GLOBS[@]:-}"; do
  while IFS= read -r match; do
    RESOLVED_FILES+=("$match")
  done < <(compgen -G "$pattern" || true)
done

# Build request body with python3
export PROMPT
export MODEL
export RESOLVED_FILES_JSON
export SCRIPT_DIR
RESOLVED_FILES_JSON=$(printf '%s\n' "${RESOLVED_FILES[@]}" | python3 -c "import sys, json; print(json.dumps([line.rstrip() for line in sys.stdin]))")

# Python script to build body and check size
BODY_OUTPUT=$(python3 << 'PYTHON'
import json
import os
import sys

prompt = os.environ.get('PROMPT', '')
model = os.environ.get('MODEL', '')
files_json = os.environ.get('RESOLVED_FILES_JSON', '[]')

try:
    file_paths = json.loads(files_json)
except:
    file_paths = []

# Read and add files
file_blocks = []

for fpath in file_paths:
    if not os.path.isfile(fpath):
        # Skip non-files
        continue
    try:
        with open(fpath, 'rb') as f:
            content = f.read()
        file_blocks.append(f"=== {fpath} ===\n".encode('utf-8') + content)
    except Exception as e:
        # Silently skip unreadable files
        pass

# Combine prompt + files into one text part
decoded_file_blocks = [b.decode('utf-8', errors='replace') for b in file_blocks]

def compose_text(prompt_text):
    combined = prompt_text
    if decoded_file_blocks:
        combined += "\n\n" + "\n\n".join(decoded_file_blocks)
    return combined

combined_text = compose_text(prompt)

# Payload injection is best-effort: delegation must survive a missing/broken module.
try:
    sys.path.insert(0, os.environ.get('SCRIPT_DIR', ''))
    from data_policy import OPT_OUT_PAYLOAD, is_enabled, prepare_prompt
    if is_enabled():
        # Move an existing caller-supplied payload behind file blocks, without duplication.
        for suffix in (OPT_OUT_PAYLOAD, OPT_OUT_PAYLOAD.rstrip()):
            if prompt.endswith(suffix):
                prompt = prompt[:-len(suffix)]
                combined_text = compose_text(prompt)
                break
        combined_text = prepare_prompt(combined_text)
except Exception:
    pass

# Check the exact composed UTF-8 request size, including file headers and payload.
total_bytes = len(combined_text.encode('utf-8'))
SIZE_LIMIT = 3500000
if total_bytes > SIZE_LIMIT:
    print(json.dumps({"error": f"input too large: {total_bytes} bytes exceeds limit; narrow --glob"}))
    sys.exit(1)

# Build request
body = {
    "contents": [
        {
            "parts": [
                {"text": combined_text}
            ]
        }
    ]
}

# Output both body and size as one JSON object
output = {
    "body": body,
    "size": total_bytes
}
print(json.dumps(output))
PYTHON
)

# Parse output
if echo "$BODY_OUTPUT" | jq -e '.error' >/dev/null 2>&1; then
  ERROR_MSG=$(echo "$BODY_OUTPUT" | jq -r '.error')
  echo "$ERROR_MSG" >&2
  exit 1
fi

BODY_JSON=$(echo "$BODY_OUTPUT" | jq -c '.body')
TOTAL_SIZE=$(echo "$BODY_OUTPUT" | jq -r '.size')

# POST to Gemini API
# Use temp file for body to avoid ARG_MAX overflow on large blobs
BODY_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/gask.XXXXXX"})
GASK_CLEANUP_FILES+=("$BODY_FILE")
echo -n "$BODY_JSON" > "$BODY_FILE"
chmod 600 "$BODY_FILE"

ENDPOINT="https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent"

# Capture response + HTTP code separately
RESPONSE_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/gask.XXXXXX"})
HTTP_CODE_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/gask.XXXXXX"})
GASK_CLEANUP_FILES+=("$RESPONSE_FILE" "$HTTP_CODE_FILE")

GASK_ATTEMPTED=true
set +e
curl -s -o "$RESPONSE_FILE" -w '%{http_code}' \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: $KEY" \
  --connect-timeout "$GASK_CONNECT_TIMEOUT" \
  --max-time "$GASK_TIMEOUT" \
  -X POST \
  --data-binary @"$BODY_FILE" \
  "$ENDPOINT" > "$HTTP_CODE_FILE" 2>&1
CURL_STATUS=$?
set -e

if [[ "$CURL_STATUS" -eq 28 ]]; then
  echo "gemini timeout after ${GASK_TIMEOUT}s (connect timeout ${GASK_CONNECT_TIMEOUT}s)" >&2
  exit 1
fi
if [[ "$CURL_STATUS" -ne 0 ]]; then
  echo "gemini error: cannot reach generativelanguage.googleapis.com (curl exit $CURL_STATUS)" >&2
  exit 1
fi

HTTP_CODE=$(cat "$HTTP_CODE_FILE")
RESPONSE=$(cat "$RESPONSE_FILE")
GASK_REPORT_STATUS="$HTTP_CODE"
GASK_REPORT_BODY_FILE="$RESPONSE_FILE"

# Check transport failure (empty code or non-numeric)
if [[ -z "$HTTP_CODE" ]] || ! [[ "$HTTP_CODE" =~ ^[0-9]{3}$ ]]; then
  echo "gemini error: cannot reach generativelanguage.googleapis.com" >&2
  GASK_REPORT_STATUS=""
  exit 1
fi

# Check HTTP error
if [[ "$HTTP_CODE" != "200" ]]; then
  ERROR_TEXT=$(echo "$RESPONSE" | head -c 300)
  if echo "$RESPONSE" | jq -e '.error.message' >/dev/null 2>&1; then
    MESSAGE=$(echo "$RESPONSE" | jq -r '.error.message')
    echo "gemini error $HTTP_CODE: $MESSAGE" >&2
  else
    echo "gemini error $HTTP_CODE: $ERROR_TEXT" >&2
  fi
  exit 1
fi

# Check for API error in 200 response
if echo "$RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  CODE=$(echo "$RESPONSE" | jq -r '.error.code // "unknown"')
  MESSAGE=$(echo "$RESPONSE" | jq -r '.error.message // "unknown error"')
  echo "gemini error $CODE: $MESSAGE" >&2
  exit 1
fi

# Check for empty/blocked candidate
if ! echo "$RESPONSE" | jq -e '.candidates[0]' >/dev/null 2>&1; then
  FINISH_REASON=$(echo "$RESPONSE" | jq -r '.candidates[0].finishReason // "UNKNOWN"' 2>/dev/null || echo "UNKNOWN")
  echo "gemini returned no content (finishReason: $FINISH_REASON)" >&2
  exit 1
fi

# Extract response text
RESP_TEXT=$(echo "$RESPONSE" | jq -r '.candidates[0].content.parts[0].text // ""' 2>/dev/null)

if [[ -z "$RESP_TEXT" ]]; then
  echo "gemini returned no content" >&2
  exit 1
fi

# Extract usage
PROMPT_TOKENS=$(echo "$RESPONSE" | jq -r '.usageMetadata.promptTokenCount // 0' 2>/dev/null)
OUTPUT_TOKENS=$(echo "$RESPONSE" | jq -r '.usageMetadata.candidatesTokenCount // 0' 2>/dev/null)
REASONING_TOKENS=$(echo "$RESPONSE" | jq -r '.usageMetadata.thoughtsTokenCount // 0' 2>/dev/null)

# Output response
if [[ "$RAW" == true ]]; then
  echo "$RESPONSE"
else
  echo "$RESP_TEXT"
  echo "[gemini $MODEL | in $PROMPT_TOKENS out $OUTPUT_TOKENS think $REASONING_TOKENS]" >&2
fi

# Append to usage ledger (python3 for safe JSON + atomic append + SQLite)
python3 << PYTHON_LOG
import json
import os
from datetime import datetime, timezone

log_file = "$USAGE_LOG"
db_path = os.path.expanduser("~/.codex-bridge/usage.db")

# Ensure directory exists
os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)

# Create log if missing, set 600 perms
if not os.path.exists(log_file):
    open(log_file, 'a').close()
    os.chmod(log_file, 0o600)

# Append record to JSONL (NO content field)
record = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "backend": "gemini",
    "model": "$MODEL",
    "input_tokens": $PROMPT_TOKENS,
    "output_tokens": $OUTPUT_TOKENS,
    "reasoning_tokens": $REASONING_TOKENS
}

try:
    with open(log_file, 'a') as f:
        f.write(json.dumps(record) + '\n')
except Exception as e:
    # Ledger failure must not fail the call
    pass

# SQLite row comes from usage_db.ingest_delegated_usage (sha1 uid); no direct insert here.
PYTHON_LOG
