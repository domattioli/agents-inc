#!/usr/bin/env bash
# at_route.sh - UserPromptSubmit hook. Routes "@<alias> <question>" to a cheap model.
# Stdout becomes extra context for the main model. Always exits 0.
set -euo pipefail

[[ "${AT_ROUTE_ACTIVE:-}" == "1" ]] && exit 0

# D52: alias -> Codex slug from routing.json, the single source. The same relative path holds in the
# checkout (skills/codex-bridge/scripts) and in the release bundle.
ROUTING_JSON="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)/../../../agents_inc/routing.json"
codex_slug() {
  python3 -c '
import json, sys
for tier in json.load(open(sys.argv[2]))["tiers"].values():
    slug = tier.get("codex")
    if slug and slug.rsplit("-", 1)[-1] == sys.argv[1]:
        print(slug)
        sys.exit(0)
sys.exit(1)
' "$1" "$ROUTING_JSON" 2>/dev/null
}

# CLI mode: "at_route.sh --resolve <alias>" prints the pinned Codex slug (exit 1, no output, if unknown).
if [[ "${1:-}" == "--resolve" ]]; then
  slug="$(codex_slug "${2:-}")" || exit 1
  [[ -n "$slug" ]] || exit 1
  printf '%s\n' "$slug"
  exit 0
fi

command -v jq >/dev/null 2>&1 || exit 0

# Resolve symlinks (~/.local/bin/@luna -> this file) so agent.sh is found.
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# The installed copy lives in the release bundle beside ask.sh. For ad-hoc
# copies (e.g., development), bridge scripts are found via AT_ROUTE_BRIDGE_DIR
# or the default checkout path.
if [[ ! -x "$SCRIPT_DIR/ask.sh" ]]; then
  SCRIPT_DIR="${AT_ROUTE_BRIDGE_DIR:-$HOME/Projects/agents_Inc/skills/codex-bridge/scripts}"
fi
LOG_FILE="${AT_ROUTE_LOG:-$HOME/.codex-bridge/at_route.log}"
TIMEOUT_S="${AT_ROUTE_TIMEOUT:-120}"

# CLI mode: invoked as "@luna <question>" (symlink named after the alias) or
# "at_route.sh luna <question>". Used with Claude Code's "!" prefix:
#   ! @luna say hi
# Output goes to stdout, exit 0, no hook framing, no model turn.
CLI=0
if [[ $# -gt 0 ]]; then
  CLI=1
  self="$(basename "${BASH_SOURCE[0]}")"
  if [[ "$self" == @* ]]; then
    prompt="${self} $*"
  else
    prompt="@$1 ${*:2}"
  fi
else
  input="$(cat)"
  prompt="$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null || true)"
fi
[[ -z "$prompt" ]] && exit 0

# Escape: ~@ prefix → exit 0, pass prompt to session model untouched
[[ "$prompt" =~ ^~@ ]] && exit 0

shopt -s nocasematch
re='^(@@?)(haiku|sonnet|opus|fable|astra|sol|terra|luna|gemini|mistral|openrouter)[[:space:]]+(.+)$'
if [[ ! "$prompt" =~ $re ]]; then
  exit 0
fi
prefix="${BASH_REMATCH[1]}"
alias_name="$(printf '%s' "${BASH_REMATCH[2]}" | tr '[:upper:]' '[:lower:]')"
question="${BASH_REMATCH[3]}"
shopt -u nocasematch
checkin=0

kind="claude"
case "$alias_name" in
  haiku)  model="haiku" ;;
  sonnet) model="sonnet" ;;
  opus)   model="opus" ;;
  fable)  model="fable" ;;
  astra|sol|terra|luna) model="$(codex_slug "$alias_name")" || exit 0; kind="codex" ;;
  gemini) model="gemini-3.8-flash"; kind="gemini" ;;
  mistral) model="codestral-latest"; kind="mistral" ;;
  openrouter) model="unknown model"; kind="openrouter" ;;
  *) exit 0 ;;
esac

# Check-in card route: formats @/@@haiku /check-in to produce a status card
if [[ "$kind" == "claude" && "$CLI" != "1" && "$question" =~ ^/check-in([[:space:]]|$) ]]; then
  transcript="$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)"
  sid="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)"
  cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null || true)"

  checkin_script="${AT_ROUTE_CHECKIN_SCRIPT:-$HOME/.claude/skills/check-in/scripts/checkin_state.sh}"

  if [[ -r "$checkin_script" && -n "$transcript" && -r "$transcript" ]]; then
    facts="$(bash "$checkin_script" --repo "${cwd:-.}" --session "$sid" --transcript "$transcript" 2>&1 || true)"
    recent="$(tail -n 300 "$transcript" | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' 2>/dev/null | tail -c 3000 || true)"

    question="Write a check-in status card for another Claude Code session, using only the facts below. Ten lines or fewer. Use these line labels in this order and omit any line with nothing to say, except NEED YOU, which always prints: NEED YOU, RECOMMEND, GOAL, DONE, NOW, NEXT, RISK, MODES, REPO. One fact per line. Where a fact is missing write unavailable; never guess. NEED YOU counts questions the session asked the operator that are still unanswered. DONE holds only results the session says it verified. MODES: caveman and structured-gist are active when the skills line names them, otherwise lapsed. Print only the card.
FACTS:
$facts
RECENT SESSION REPLIES (latest last):
$recent"
    checkin=1
  fi
fi

# Reject slash commands on @@ with Claude alias
if [[ "$prefix" == "@@" && "$kind" == "claude" && "$CLI" != "1" && "${checkin:-0}" != "1" && "$question" =~ ^/ ]]; then
  # Log the attempt
  {
    mkdir -p "$(dirname "$LOG_FILE")" &&
      printf '%s\t%s\t%s\t%ss\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$alias_name" "2" "0" >>"$LOG_FILE"
  } 2>/dev/null || true

  # Print error to stderr
  printf '[at_route] @@%s does not forward slash commands: the side session would run the command on itself, not on this session. Use @%s /check-in for a status card, or type the command without @@.\n' "$alias_name" "$alias_name" >&2
  exit 2
fi

# Persistent session route for @@ with Claude alias
if [[ "$prefix" == "@@" && "$kind" == "claude" && "$CLI" != "1" && "${AT_ROUTE_PERSIST:-1}" == "1" && "${checkin:-0}" != "1" ]]; then
  # Log the attempt
  {
    mkdir -p "$(dirname "$LOG_FILE")" &&
      printf '%s\t%s\t%s\t%ss\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$alias_name" "0" "0" >>"$LOG_FILE"
  } 2>/dev/null || true

  # Print context for host model
  cat <<EOF
[at_route] Persistent-session route for @@${alias_name}. Do only these steps:
1. If ListAgents or SendMessage are deferred, load both with ToolSearch "select:ListAgents,SendMessage".
2. Call ListAgents. If no peer session is named at-${alias_name}, start one with Bash:
   claude --bg -n at-${alias_name} --model ${model} --allowedTools "Read,Grep,Glob" --disallowedTools "Edit,Write,NotebookEdit,Bash" "You are the at-${alias_name} side session. Wait for questions sent to you by message. Answer each briefly. Do not edit files. Send each answer back with SendMessage to the session named in the message's from attribute. Reply now with exactly: ready"
   Then call ListAgents again to confirm.
3. SendMessage to at-${alias_name}, message = the question between the --- lines, verbatim.
4. End your turn with one line: sent to at-${alias_name}. When the reply arrives as a cross-session message from at-${alias_name}, answer with the literal prefix "${alias_name} ▸ " followed by the reply verbatim. Do not re-answer, reason, or comment.
---
${question}
---
EOF
  exit 0
fi

out_f="$(mktemp "${TMPDIR:-/tmp}/at_route_out.XXXXXX")"
err_f="$(mktemp "${TMPDIR:-/tmp}/at_route_err.XXXXXX")"
trap 'rm -f "$out_f" "$err_f"' EXIT

# Portable timeout: perl alarm survives exec, SIGALRM kills the child.
run_with_timeout() {
  perl -e 'alarm shift @ARGV; exec @ARGV or die "exec failed: $!\n"' "$TIMEOUT_S" "$@"
}

start=$SECONDS
rc=0
if [[ "$kind" == "claude" ]]; then
  AT_ROUTE_ACTIVE=1 run_with_timeout claude -p "$question" --model "$model" --tools "Read,Grep,Glob" --disallowedTools "Edit,Write,Bash,NotebookEdit" --strict-mcp-config \
    >"$out_f" 2>"$err_f" </dev/null || rc=$?
elif [[ "$kind" == "gemini" ]]; then
  AT_ROUTE_ACTIVE=1 run_with_timeout "$SCRIPT_DIR/gask.sh" --tier digest "$question" \
    >"$out_f" 2>"$err_f" </dev/null || rc=$?
  # gask.sh prints upstream errors on stdout with exit 0
  if [[ "$rc" -eq 0 ]] && grep -q '^gemini error' "$out_f"; then rc=1; cat "$out_f" >>"$err_f"; fi
elif [[ "$kind" == "mistral" ]]; then
  AT_ROUTE_ACTIVE=1 run_with_timeout "$SCRIPT_DIR/mask.sh" --tier code "$question" \
    >"$out_f" 2>"$err_f" </dev/null || rc=$?
elif [[ "$kind" == "openrouter" ]]; then
  AT_ROUTE_ACTIVE=1 run_with_timeout env -u MODEL "$SCRIPT_DIR/oask.sh" "$question" \
    >"$out_f" 2>"$err_f" </dev/null || rc=$?
  if [[ "$rc" -eq 0 ]]; then
    # Parse the model from stderr: [openrouter MODEL | ...]
    model="$(grep '^\[openrouter' "$err_f" 2>/dev/null | tail -1 | sed -n 's/^\[openrouter \([^ |]*\) .*/\1/p' || true)"
    [[ -n "$model" ]] || model="unknown model"
  fi
else
  # Codex aliases: one fresh, tool-free `agents-inc run` per question, prompt on stdin. No bridge daemon
  # is needed. (The persistent agent.sh thread grew to 442k input tokens per call by the 6th question,
  # measured 2026-09-23.)
  run_cwd="${cwd:-}"
  [[ -z "$run_cwd" && "$CLI" != "1" ]] && run_cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null || true)"
  [[ -d "$run_cwd" ]] || run_cwd="$PWD"
  printf '%s' "$question" | AT_ROUTE_ACTIVE=1 run_with_timeout "${AT_ROUTE_AGENTS_INC:-agents-inc}" run \
    --model "$alias_name" --no-tools --cwd "$run_cwd" >"$out_f" 2>"$err_f" || rc=$?
  if [[ "$rc" -eq 0 && ! -s "$out_f" ]]; then
    rc=1; echo "empty reply from agents-inc run" >>"$err_f"
  fi
fi
elapsed=$((SECONDS - start))

{
  mkdir -p "$(dirname "$LOG_FILE")" &&
    printf '%s\t%s\t%s\t%ss\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$alias_name" "$rc" "$elapsed" >>"$LOG_FILE"
} 2>/dev/null || true

# Every answer is also appended to a transcript, because Claude Code shows
# hook stderr only between turns: a block-mode prompt sent mid-turn would
# otherwise be lost. Read it with: tail -20 ~/.codex-bridge/at_route_answers.log
ANS_LOG="${AT_ROUTE_ANSWERS:-${LOG_FILE%/*}/at_route_answers.log}"
if [[ "$rc" -eq 0 ]]; then
  {
    printf '\n=== %s %s (%s) %ss\nQ: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$alias_name" "$model" "$elapsed" "$question"
    cat "$out_f"
  } >>"$ANS_LOG" 2>/dev/null || true
  # Exit 2 blocks the prompt: the main model never runs, stderr is shown to the
  # operator, and nothing enters the conversation. Zero main-model cost.
  # @@ prefix or AT_ROUTE_MODE=relay injects the answer as context (relay mode).
  mode="block"
  [[ "$prefix" == "@@" ]] && mode="relay"
  [[ "${AT_ROUTE_MODE:-}" == "relay" && "$mode" != "relay" ]] && mode="relay"
  if [[ "$mode" == "relay" ]]; then
    echo "[at_route] Answer from delegate ${alias_name} (${model}) below. Begin your reply with the literal prefix \"${alias_name} ▸ \" and then relay the answer verbatim. Do not re-answer, do not reason, do not add commentary."
    echo "---"
    cat "$out_f"
    echo "---"
    exit 0
  fi
  _at_route_box() {
    # ANSI cyan box, on by default. Claude Code passes hook stderr escapes through
    # (verified 2026-09-23). AT_ROUTE_COLOR=0 disables.
    c=""; r=""
    if [[ "${AT_ROUTE_COLOR:-1}" == "1" ]]; then c=$'\033[36m'; r=$'\033[0m'; fi
    printf '%s┌─ %s (%s) · %ss ─%s\n' "$c" "$alias_name" "$model" "$elapsed" "$r"
    sed "s/^/${c}│ /; s/\$/${r}/" "$out_f"
    printf '%s└─%s\n' "$c" "$r"
  }
  # Plain redirect, not process substitution: the Claude Code sandbox denies /dev/fd writes (#113).
  if [[ "$CLI" == 1 ]]; then _at_route_box; else _at_route_box >&2; fi
  [[ "$CLI" == 1 ]] && exit 0
  exit 2
else
  if [[ "$rc" -eq 142 ]]; then
    echo "[at_route] ${alias_name} call timed out after ${TIMEOUT_S}s (exit 142). Partial files may exist in the working tree: run \`git status\` before answering."
  else
    echo "[at_route] ${alias_name} call failed (exit ${rc}). Stderr:"
  fi
  echo '```'
  cat "$err_f"
  echo '```'
  echo "Answer the operator's question yourself."
fi
exit 0
