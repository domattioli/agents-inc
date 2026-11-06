#!/bin/bash
set -euo pipefail

# Model map: built-in defaults < ~/.config/agents-inc/roster.json < AGENTS_INC_MODEL_MAP < CODEXAGENT_MODEL_MAP
# (JSON object or path to JSON file), resolved by mcp/codex_agent_mcp.py --resolve-model. --slug passes a raw slug.
MCP_PY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../mcp/codex_agent_mcp.py"

MODEL="luna"
RAW_SLUG=""
EFFORT=""
RESUME_ID=""
PROMPT_ARGS=()

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)
            MODEL="$2"
            shift 2
            ;;
        --slug)
            RAW_SLUG="$2"
            shift 2
            ;;
        --effort)
            EFFORT="$2"
            shift 2
            ;;
        --resume)
            RESUME_ID="$2"
            shift 2
            ;;
        *)
            # Everything else is part of prompt
            PROMPT_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ -n "$RAW_SLUG" ]]; then
    SLUG="$RAW_SLUG"
elif ! SLUG="$(python3 "$MCP_PY" --resolve-model "$MODEL")"; then
    echo "Error: invalid model '$MODEL'. Allowed: $(python3 "$MCP_PY" --list-models)" >&2
    exit 1
fi

if [[ ${#PROMPT_ARGS[@]} -eq 0 ]]; then
    echo "Error: prompt required." >&2
    exit 1
fi

if ! command -v codex &>/dev/null; then
    echo "Error: codex CLI not found on PATH" >&2
    exit 1
fi

# Join prompt args with space
PROMPT="${PROMPT_ARGS[@]}"

TMPFILE=$(mktemp ${TMPDIR:+"$TMPDIR/bridge.XXXXXX"})
STDERR_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/bridge.XXXXXX"})
JSONL_FILE=$(mktemp ${TMPDIR:+"$TMPDIR/bridge.XXXXXX"})
trap "rm -f '$TMPFILE' '$STDERR_FILE' '$JSONL_FILE'" EXIT

TIMEOUT_CMD=""
if command -v timeout &>/dev/null; then
    TIMEOUT_CMD="timeout"
elif command -v gtimeout &>/dev/null; then
    TIMEOUT_CMD="gtimeout"
fi

TIMEOUT_VAL="${CODEXAGENT_TIMEOUT:-300}"

EFFORT_ARGS=()
if [[ -n "$EFFORT" ]]; then
    EFFORT_ARGS=(-c "model_reasoning_effort=$EFFORT")
fi

if [[ -n "$RESUME_ID" ]]; then
    # exec resume has no -s and no -C: sandbox mode goes through -c, cwd is the caller's.
    CODEX_ARGV=(exec resume "$RESUME_ID" -m "$SLUG" ${EFFORT_ARGS[@]+"${EFFORT_ARGS[@]}"} -c sandbox_mode=read-only --skip-git-repo-check --json -o "$TMPFILE" -- "$PROMPT")
else
    CODEX_ARGV=(exec -m "$SLUG" ${EFFORT_ARGS[@]+"${EFFORT_ARGS[@]}"} -s read-only --skip-git-repo-check --json -o "$TMPFILE" -- "$PROMPT")
fi

CODEX_EXIT=0
if [[ -n "$TIMEOUT_CMD" ]]; then
    "$TIMEOUT_CMD" "$TIMEOUT_VAL" codex "${CODEX_ARGV[@]}" 2>"$STDERR_FILE" >"$JSONL_FILE" || CODEX_EXIT=$?
else
    codex "${CODEX_ARGV[@]}" 2>"$STDERR_FILE" >"$JSONL_FILE" || CODEX_EXIT=$?
fi

if [[ $CODEX_EXIT -ne 0 ]]; then
    cat "$STDERR_FILE" >&2
    exit $CODEX_EXIT
fi

THREAD_ID="$(head -n 5 "$JSONL_FILE" | python3 -c '
import json, sys
for line in sys.stdin:
    try:
        tid = json.loads(line).get("thread_id")
    except (ValueError, AttributeError):
        continue
    if tid:
        print(tid)
        break
' || true)"

if [[ -n "$RESUME_ID" && "$THREAD_ID" != "$RESUME_ID" ]]; then
    echo "Error: conversation $RESUME_ID not found; Codex started a new thread" >&2
    exit 1
fi

if [[ ! -s "$TMPFILE" ]]; then
    LAST_ERR="$(grep -v '^[[:space:]]*$' "$STDERR_FILE" | tail -n 1 || true)"
    if [[ -s "$STDERR_FILE" ]]; then
        cat "$STDERR_FILE" >&2
    fi
    echo "Error: empty result from codex exec${LAST_ERR:+: $LAST_ERR}" >&2
    exit 1
fi

if [[ -n "$THREAD_ID" ]]; then
    echo "CONVERSATION_ID=$THREAD_ID" >&2
fi
cat "$TMPFILE"
