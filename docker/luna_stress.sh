#!/usr/bin/env bash
# Stress run for the native agents-inc:luna type (spec 028), inside docker/Dockerfile.dev or on the macOS host.
# Each scenario runs R times (default 10). A run passes when every expected string appears in the session's result text,
# no KEY=<n> value in it differs from the expected one, and the scenario's own check holds. Prints one row per run and a
# summary. Never prints a secret.
# The Claude token goes in by variable name only, so its value is never on a command line:
#   docker build -f docker/Dockerfile.dev --build-arg CLAUDE_CODE_VERSION=<host version> --build-arg CODEX_VERSION=<host version> -t agents-inc-dev:luna .
#   export CLAUDE_CODE_OAUTH_TOKEN  # loaded beforehand without echoing it
#   docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN -e R=3 -v "$PWD:/src:ro" -v "$PWD/docker/luna_stress.sh:/stress.sh:ro" \
#     -v "$OUT:/home/dev/out" --mount type=bind,src=$HOME/.codex/auth.json,dst=/run/secrets/codex_auth.json,readonly \
#     agents-inc-dev:luna bash /stress.sh
# On the macOS host: caffeinate -is env SRC=<checkout> OUT=<dir> W=<dir> MOD=<dir> bash docker/luna_stress.sh. Without
# caffeinate an idle Mac sleeps mid-step: the step stalls for the sleep, the mod's timer does not count it, and the run
# fails on time alone (the debug log shows "clock jump"). Docker on the same Mac sleeps with it.
# SCENARIOS picks a subset of: latin tools follow par delete steps5. HAIKU=1 runs the same prompts with a haiku
# general-purpose agent instead, to compare permission decisions with the luna runs (SC-002).
# Columns: steps = "agents-inc luna: step" debug lines; claude = assistant messages from a haiku model (the parent is
# sonnet, so any of them in a luna run is a placeholder leak, SC-003); rui = request_user_input calls in the new Codex
# rollouts (SC-005); codexc = all tool calls in them; act = acting calls (exec, apply_patch, collaboration, MCP; SC-004).
set -uo pipefail
R=${R:-10}
SRC=${SRC:-/src}
OUT=${OUT:-$HOME/out}; mkdir -p "$OUT"
# On the host, point W and MOD at a scratch dir: the script empties MOD and seeds W.
W=${W:-$HOME/work}; MOD=${MOD:-$HOME/mod}; mkdir -p "$W"; cd "$W"
rm -rf "$MOD"; cp -r "$SRC/mods/agents-inc" "$MOD"
seq 1 173 > a.txt; seq 1 95 > b.txt; seq 1 41 > c.txt; seq 1 7 > d.txt; seq 1 12 > e.txt
printf '.scratch/\n' > .gitignore
git init -q . 2>/dev/null
git add -A && git -c user.email=stress@example.invalid -c user.name=stress commit -qm base 2>/dev/null

# Warm step: a fresh CODEX_HOME has no models_cache.json, and a host-tools run fails without the luna entry (FR-011).
# `codex debug models` writes the cache with no model call (T005, research.md R3).
SLUG=$(agents-inc luna status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("slug",""))' 2>/dev/null)
WARM_CMD=${WARM_CMD:-"codex debug models"}
eval "$WARM_CMD" > "$OUT/warm.log" 2>&1
if ! python3 -c 'import json,os,sys
c=json.load(open(os.path.expanduser("~/.codex/models_cache.json")))
sys.exit(0 if any(m.get("slug")==sys.argv[1] for m in c.get("models",[])) else 1)' "${SLUG:-gpt-6-luna}" 2>/dev/null; then
  echo "WARM FAILED: ~/.codex/models_cache.json holds no entry for ${SLUG:-gpt-6-luna}; see $OUT/warm.log" >&2; exit 1
fi

if [ "${HAIKU:-0}" = 1 ]; then AGENT="subagent_type general-purpose and model haiku"; else AGENT="subagent_type agents-inc:luna"; fi
prompt_latin="Call the Agent tool once with $AGENT. Its task: 'Write one Latin sentence with an English translation separated by an em dash. Use no tools.' Quote its report verbatim."
prompt_tools="Call the Agent tool once with $AGENT. Its task: 'Run wc -l a.txt with Bash, then Read b.txt and give its line count and the text of its line 50. Report A=<count> B=<line count> L=<that text>.' Quote its report verbatim."
prompt_follow="Step 1: call the Agent tool once with $AGENT. Its task: 'Run wc -l c.txt with Bash and report the count as C=<n>.' Wait for its report. Step 2: SendMessage the same agent: 'what model are you, exactly'. Wait for its reply. Quote both replies verbatim."
prompt_par="In one message, call the Agent tool three times in parallel, each with $AGENT and run_in_background false. Tasks: 1) 'Run wc -l a.txt with Bash; report A=<n>.' 2) 'Run wc -l b.txt with Bash; report B=<n>.' 3) 'Run wc -l c.txt with Bash; report C=<n>.' Quote all three reports verbatim."
prompt_delete="Call the Agent tool once with $AGENT. Its task: 'Delete the file a.txt. Report what you did.' Quote its report verbatim."
prompt_steps5="Call the Agent tool once with $AGENT. Its task: 'Run these five commands, each with its own Bash call in its own step, and report the counts: wc -l a.txt, wc -l b.txt, wc -l c.txt, wc -l d.txt, wc -l e.txt. Report A=<n> B=<n> C=<n> D=<n> E=<n>.' Quote its report verbatim."

# Lookups by scenario name; macOS /bin/bash is 3.2, which has no associative arrays.
expect() { case $1 in latin) echo "—";; tools) echo "A=173|B=95|L=50";; follow) echo "C=41|gpt-6";; par) echo "A=173|B=95|C=41";;
  delete) echo "";; steps5) echo "A=173|B=95|C=41|D=7|E=12";; esac; }
prompt_for() { eval "echo \"\$prompt_$1\""; }
pass=0; total=0
printf '%-8s %-3s %-5s %6s %5s %6s %4s %6s %4s %5s %s\n' scenario run ok secs steps claude rui codexc act errs missing
for s in ${SCENARIOS:-latin tools follow par delete steps5}; do
  for i in $(seq 1 "$R"); do
    n=$s.$i; before=$(find "$HOME/.codex/sessions" -name 'rollout-*.jsonl' 2>/dev/null | sort)
    allowed="Agent,SendMessage,Bash(wc:*),Read"; denied=()
    # delete: the harness is the only gate, so file-changing tools are denied and the tree must stay clean.
    if [ "$s" = delete ]; then allowed="Agent,SendMessage,Read"; denied=(--disallowedTools "Edit,Write,Bash"); fi
    t0=$(date +%s)
    timeout 600 claude -p "$(prompt_for "$s")" --model sonnet --plugin-dir "$MOD" --output-format stream-json --verbose \
      --debug-file "$OUT/$n.log" --allowedTools "$allowed" ${denied[@]+"${denied[@]}"} > "$OUT/$n.jsonl" 2> "$OUT/$n.err"
    rc=$?; secs=$(( $(date +%s) - t0 ))
    # Result text, the kept permission_denials and tool-use/tool-result pairs, and the haiku message count.
    claude_steps=$(python3 - "$OUT/$n.jsonl" "$OUT/$n.result.txt" "$OUT/$n.permissions.json" <<'PY'
import json, sys
src, res, perm = sys.argv[1:4]
result, denials, uses, results, haiku = [], [], {}, [], 0
for line in open(src):
    try: d = json.loads(line)
    except Exception: continue
    if d.get("type") == "result":
        result.append(str(d.get("result") or "")); denials += d.get("permission_denials") or []
    msg = d.get("message") or {}
    # A step the mod answered carries a msg_hook_ id; the harness labels it with the placeholder model anyway.
    if d.get("type") == "assistant" and "haiku" in str(msg.get("model", "")) and not str(msg.get("id", "")).startswith("msg_hook_"): haiku += 1
    for b in msg.get("content") or []:
        if not isinstance(b, dict): continue
        if b.get("type") == "tool_use": uses[b.get("id")] = {"name": b.get("name"), "input": b.get("input")}
        elif b.get("type") == "tool_result": results.append({"tool_use_id": b.get("tool_use_id"), "is_error": b.get("is_error", False), "content": b.get("content")})
open(res, "w").write("\n".join(result))
json.dump({"permission_denials": denials, "tool_uses": uses, "tool_results": results}, open(perm, "w"), indent=1)
print(haiku)
PY
)
    missing=""; IFS='|' read -ra want <<< "$(expect "$s")"
    for w in ${want[@]+"${want[@]}"}; do [ -z "$w" ] || grep -qiF -- "$w" "$OUT/$n.result.txt" || missing="$missing $w"; done
    # A made-up value fails the run even when another agent's right value also reached the report.
    for w in ${want[@]+"${want[@]}"}; do
      case $w in [A-Z]=*) for got in $(grep -oE "\b${w%%=*}=[0-9]+" "$OUT/$n.result.txt" | sort -u); do
        [ "$got" = "$w" ] || missing="$missing wrong:$got"; done;; esac
    done
    steps=$(grep -c 'agents-inc luna: step' "$OUT/$n.log" 2>/dev/null); errs=$(grep -ciE 'agents-inc luna: .*(fail|empty reply|error)' "$OUT/$n.log" 2>/dev/null)
    new=$(comm -13 <(echo "$before") <(find "$HOME/.codex/sessions" -name 'rollout-*.jsonl' 2>/dev/null | sort))
    cc=0; rui=0; act=0
    for f in $new; do
      cc=$((cc + $(grep -c '"type":"custom_tool_call"\|"type": "custom_tool_call"\|"type":"function_call"' "$f")))
      rui=$((rui + $(grep -cE '"type": ?"function_call".*"name": ?"request_user_input"' "$f")))  # calls, not the tool schema
      act=$((act + $(grep -cE '"name": ?"(exec|exec_command|apply_patch|spawn_agent|send_message|wait_agent|[a-z_]*collab[a-z_]*|mcp__[A-Za-z0-9_-]+)"' "$f")))
    done
    if [ "$s" = delete ]; then
      [ -z "$(git status --porcelain)" ] || missing="$missing tree-changed"
      [ "$act" -eq 0 ] || missing="$missing acting-calls:$act"
      git checkout -q -- . 2>/dev/null; git clean -fdq 2>/dev/null
    fi
    if [ "$s" = steps5 ]; then
      # SC-006: the usage the mod reported per step against the sum of the thread rollouts' last Codex totals.
      delta=$(python3 - "$OUT/$n.log" $new <<'PY'
import json, re, sys
src, rollouts = sys.argv[1], sys.argv[2:]
# The mod's debug line for each step ends with the usage it reported for that step. The parent's stream is not the
# source: it can leave out the final step's message (s028e steps5 run 7). The line spells the numbers without
# token field names, which the debug log redacts.
used = 0
for line in open(src, errors="replace"):
    m = re.search(r"\bstep \d+ of \S+ took .*, usage in (\d+) cached \d+ out (\d+)", line)
    if m: used += int(m.group(1)) + int(m.group(2))
total = 0
for f in rollouts:  # a fresh thread is a second rollout: each one's last running total counts
    last = 0
    for line in open(f):
        try: d = json.loads(line)
        except Exception: continue
        t = ((d.get("payload") or {}).get("info") or {}).get("total_token_usage")
        if t: last = int(t.get("input_tokens", 0)) + int(t.get("output_tokens", 0))
    total += last
print("n/a" if not total or not used else f"{abs(used - total) * 100 / total:.1f}%")
PY
)
      echo "  steps5 usage delta: $delta" >> "$OUT/steps5.delta.txt"
      [ "$delta" = "n/a" ] || python3 -c 'import sys; sys.exit(0 if float(sys.argv[1].rstrip("%")) <= 1.0 else 1)' "$delta" || missing="$missing usage-delta:$delta"
    fi
    # The parent is sonnet, so a haiku message in a luna run means the placeholder answered a step.
    [ "${HAIKU:-0}" = 1 ] || [ "${claude_steps:-0}" -eq 0 ] || missing="$missing placeholder-leak:$claude_steps"
    ok=no; [ -z "$missing" ] && [ $rc -eq 0 ] && ok=yes && pass=$((pass+1)); total=$((total+1))
    printf '%-8s %-3s %-5s %6s %5s %6s %4s %6s %4s %5s %s\n' "$s" "$i" "$ok" "$secs" "$steps" "${claude_steps:-0}" "$rui" "$cc" "$act" "$errs" "${missing:-$( [ $rc -ne 0 ] && echo rc=$rc )}"
  done
done
cp -r "$HOME/.codex/sessions" "$OUT/codex-sessions" 2>/dev/null
echo "PASS $pass/$total"
