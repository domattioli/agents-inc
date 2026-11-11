---
name: codex-bridge
description: Use for astra, sol, terra, luna, or a Codex delegate. Installed direct launcher is required; Claude Agent cannot select these models. Bridge commands remain source-only.
version: 1.0.1
benchmark: claude_tokens_saved_per_offloaded_task
---

# Codex Bridge

The HTTP bridge is a deferred, source-checkout-only feature. The supported
cross-project path is the installed `agents-inc` direct Codex launcher; it
runs a read-only, isolated command and does not start, stop, or inspect a daemon.

## When to Use

**Good use cases:**
- Bulk digestion of large logs, error dumps, or transcripts that don't need to stay in your Claude context window.
- "Second opinion" debugging: ask Codex why a test failed while keeping your Claude session focused on implementation.
- Triage and filtering: ask Codex to scan a dataset and return only the subset you care about, then summarize the results for Claude.
- Exploratory analysis before asking Claude: use Codex to understand the shape of a problem (sample output, error patterns) and feed a summary back to Claude.

**Bad use cases:**
- Anything that needs continuity with this conversation's context—Codex has no access to your Claude session history.
- Work that depends on private code or secrets; the bridge requires a ChatGPT subscription and runs on your machine, but the prompts are sent to OpenAI.
- Tasks better handled by Claude's reasoning: Codex excels at pattern matching and code generation, not at complex reasoning or design decisions.

## Scripts

### up.sh

Start the Codex Bridge server. Idempotent—safe to call repeatedly even if the bridge is already running.

```bash
codex-bridge up [--port N] [--timeout N] [--workdir DIR] [--model M] [--tunnel] [--force]
```

**Options:**
- `--port N`: Listen on port N (default: 8787).
- `--timeout N`: Prompt timeout in seconds (default: 300).
- `--workdir DIR`: Working directory for bridge operations (default: $HOME).
- `--model M`: Force a specific model (optional; defaults to bridge.py config).
- `--tunnel`: Start a Cloudflare tunnel to expose the bridge publicly. Gracefully degrades if `cloudflared` is not installed.
- `--force`: Replace shared bridge state even when it points to a live bridge on another port. Without this explicit override, `up.sh` refuses to strand the recorded bridge.

**Output:** Prints the local URL, tunnel URL (if enabled), PID, workdir, and token file location. Does NOT print the token itself.

**Example:**
```bash
/codex-bridge up --timeout 600 --tunnel
```

### down.sh

Stop the Codex Bridge server and any active tunnel.

```bash
codex-bridge down
```

**Output:** Prints what was stopped (PIDs, URLs). Exit code 0 even if nothing is running.

**Example:**
```bash
/codex-bridge down
```

### ask.sh

Send a prompt to the persistent Codex session and get a response.

```bash
codex-bridge ask [--model M] [--reset] [--raw] "prompt text"
```

Or pass the prompt on stdin:
```bash
cat logfile.txt | codex-bridge ask "summarize this log"
```

**Options:**
- `--model M`: Override the model for this prompt (optional).
- `--reset`: Clear the session history before this prompt (starts fresh).
- `--raw`: Print the full JSON response instead of just the response text.
- `--thread ID`: Resume a specific provider session id instead of the bridge's global thread; the request is isolated (does not read or write the global thread). Mutually exclusive with `--fresh` (exit 2 if both given).
- `--fresh`: Start an isolated new session (no `resume` argument sent), leaving the global thread untouched. Mutually exclusive with `--thread`.

(R-D, pre-existing limitation, out of scope for this feature: a prompt argument starting with `--` may misparse as a flag.)

**Output (default):** The response text, followed by a summary line on stderr: `[thread <id> | in <n> out <n>]` (token counts).

**Output (--raw):** Full JSON response: `{"response": "...", "thread_id": "...", "usage": {...}}`.

**Example:**
```bash
/codex-bridge ask "what error does this code produce?" < error.log

/codex-bridge ask --reset "start fresh: analyze this dataset" < data.csv

/codex-bridge ask --raw "debug this" | jq .usage
```

### status.sh

Check if the Codex Bridge is healthy and print its state.

```bash
codex-bridge status
```

**Output:** Running status (yes/no), local URL, tunnel URL, current thread ID, workdir, uptime.

**Exit code:** 0 if healthy, 1 if not running or unhealthy.

**Example:**
```bash
/codex-bridge status
```

### mask.sh

Send a prompt through a plain Mistral completion or through the configured persistent Mistral agent:

```bash
skills/codex-bridge/scripts/mask.sh --tier code "review this function"
skills/codex-bridge/scripts/mask.sh --agent "research the current alternatives"
skills/codex-bridge/scripts/mask.sh --agent --reset "start a fresh research thread"
```

The agent leg reads its ID from `~/.config/devstral/agent_id` or `MISTRAL_AGENT_ID`, stores the latest conversation ID in `~/.codex-bridge/mistral-conversation-id`, and continues that conversation until `--reset` is used. It is intended for research-style questions where its web-search and code-interpreter tools earn the roughly 26-second latency, not for quick transforms.

### agent.sh

`agent.sh` is the governed local job runner over `ask.sh`, `gask.sh`, and `mask.sh`. It gives each call a task ID, records lifecycle and output locally, supports concurrent submitted jobs, and sends health outcomes to `route.sh`.

```bash
# Auto-select from the current routing mode; return a job ID immediately.
CODEX_BRIDGE_MODE=ultra skills/codex-bridge/scripts/agent.sh submit --class review "review the parser"

# Synchronous job; status is printed when it reaches a terminal state.
skills/codex-bridge/scripts/agent.sh submit --backend gemini --wait "summarize these errors"

# A persistent Mistral agent can be continued later.
id=$(skills/codex-bridge/scripts/agent.sh submit --backend mistral --agent "research X")
skills/codex-bridge/scripts/agent.sh follow-up "$id" --wait "compare the top two"
skills/codex-bridge/scripts/agent.sh result "$id"
```

Commands are `submit`, `status ID`, `wait ID`, `result ID [--stderr|--json]`, `follow-up ID`, and `list`. `--retries 1` through `3` retry only failures that `route.sh` classifies as transient. Job state is private local metadata under `~/.codex-bridge/agents`; set `CODEX_BRIDGE_AGENT_STATE_DIR` for an isolated state directory in automation. Every terminal job also writes `result.json` with a stable provider-neutral schema and paths to its saved stdout/stderr. A future supervisor-side translator can consume that artifact; the runner never invokes one itself.

In `CODEX_BRIDGE_MODE=ultra`, the runner refuses Anthropic names and follows `route.sh` without provider fallback. Gemini is stateless, so only Codex and Mistral jobs created with `--agent` support `follow-up`.

### Persistent mandate sessions (spec-010)

`submit` accepts additive flags so a Codex-backed role (Executive/Supervisor rung) can be re-engaged within one mandate without re-briefing, instead of `codex exec` cold-starting every call. Full spec: `specs/010-persistent-exec-session/`.

```bash
# NOTE: --backend codex --wait is broken (bridge daemon can't see codex on PATH) and superseded by the delegate-agent MCP tool for luna; other codex models still use this async path until wired into delegate-agent.

# First engagement opens the mandate + role; a fresh provider session starts.
agent.sh submit --backend codex --model gpt-6-astra --mandate run-123 --role executive --wait "brief..."

# Re-engagement resumes the same role's session -- no re-briefing needed.
agent.sh submit --backend codex --model gpt-6-astra --mandate run-123 --role executive --wait "follow-up question"

# Abandon the stored session and start over (recorded in replaced_thread_ids):
agent.sh submit --backend codex --model gpt-6-astra --mandate run-123 --role executive --fresh "..."

# Mandate lifecycle (only close mutates state):
agent.sh mandate close run-123 --by lead --reason "done"
agent.sh mandate list [--json]     # WARN: lines for mandates open >7 days
agent.sh mandate show run-123 [--json]
```

New `submit` flags: `--model <slug>` (passthrough to `ask.sh --model`), `--mandate <run_id>` (requires `--role`), `--role <name>` (requires `--mandate`), `--fresh` (mandate-scoped, abandons the stored thread), `--force` (mandate-scoped, overrides a duplicate-in-flight or model-mismatch refusal; every use is logged).

`follow-up` does **not** accept mandate flags in v1 — it continues to ride the bridge's global thread; passing `--mandate`/`--role`/`--fresh`/`--force` to `follow-up` exits 2 with `agent: follow-up does not accept mandate flags in v1; use submit --mandate`.

Exit codes reserved for mandate **state** refusals (a caller cannot fix these by correcting argv): `7` duplicate-in-flight or model-mismatch (unless `--force`), `8` mandate closed, `9` resume failed (bridge returned 409 for a caller-supplied `thread_id`; rerun with `--fresh`), `10` `mandate close` refused because a role is still in flight (unless `--force`). Exit `2` is the existing shared **usage**-error class and is reused (not renumbered) for caller-fixable mistakes: `follow-up` given mandate flags, `--by` outside the `{ceo, lead}` allowlist, and `CODEX_BRIDGE_AGENT_STATE_DIR` resolving inside the repo or `~/.claude/`.

Under a mandate, the bridge's `POST /prompt` gains two optional body fields sent by the runner (never both, never neither, for any mandate engagement): `thread_id` (resume a specific session, isolated from the global thread) or `fresh: true` (start an isolated new session, no `resume` argument, global thread untouched). A resume failure on a caller-supplied `thread_id` returns HTTP `409 {"error":"resume failed","thread_id":...,"stderr":...}` with no automatic fresh retry — that retry-as-fresh behaviour is preserved only for the bridge's own global thread.

## Free models through dispatch (D75)

`agents-inc dispatch --model <free slug> --slots <file>` runs gemini-3.8-flash, gemini-flash-lite-latest, ministral-3b-latest, codestral-latest and the OpenRouter `:free` slugs through these wrappers. Slots need `TASK_KIND` (extract, summarize or classify) and an author-written `CLASSIFICATION` (public or internal). Gates use the `{report}` token for the saved reply. No gate ends `unverified`. No tools, fan-out or resume.

## Free-model health and 429 history

gask/mask/oask report every call outcome to `agents_inc.free_health`. Per-provider cooldown lives in `~/.codex-bridge/backend-health.json`; lifetime per-model calls/429s/last-429 live in `~/.codex-bridge/rate-limit-stats.json` (503 overloaded counts as 429). Show worst offenders first: `PYTHONPATH=. python3 -m agents_inc.free_health rate-limits`. Consult before picking a free model; prefer low 429 rate. Ollama calls (adapter) log tokens to usage.jsonl as backend `ollama` but do not feed free_health. oask writes a fixed `/tmp/oask_response.json`: never run oask calls in parallel, replies clobber. Latest probe results: `docs/BENCH.md` "Free-model probe — 2026-09-29".

## Delegation timeouts

| Operation | Environment variable | Default |
|---|---|---:|
| Gemini connection | `GASK_CONNECT_TIMEOUT` | 10 seconds |
| Gemini complete request | `GASK_TIMEOUT` | 900 seconds |
| Mistral plain completion | `MASK_TIMEOUT` | 180 seconds |
| Mistral agent request | `MASK_AGENT_TIMEOUT` | 900 seconds |
| Local bridge health/session probe | not configurable | 2 seconds |

The 15-minute generation budgets leave room for deep Gemini output and Mistral agent tool use; the separate 10-second Gemini connection budget fails quickly when the host cannot be reached.

## In-band data-protection declaration

The Gemini leg currently appends the shared opt-out and data-protection declaration from `scripts/data_policy.py` to the end of each non-empty composed request, after any supplied file contents. Injection is enabled by default and is idempotent, so retries or already-prepared prompts receive exactly one copy. Other delegation legs do not currently apply it.

Disable injection for a call by setting:

```bash
CODEX_BRIDGE_OPTOUT=0 skills/codex-bridge/scripts/gask.sh "prompt"
```

This is a declaration sent in-band. Provider data handling is ultimately governed by account settings and terms rather than by prompt text.

## How It Works

The bridge maintains a **persistent OpenAI conversation thread**. Each call to `ask.sh` appends a user message and gets a response while keeping the thread alive. This lets you build context without repeating history.

- Thread ID is stored in `~/.codex-bridge/state.json` and returned after each prompt.
- Token file (`~/.codex-bridge/token`) grants authentication; keep it private (mode 600).
- Logs are written to `~/.codex-bridge/bridge.log` and `~/.codex-bridge/tunnel.log`.

### When to Reset

Use `ask.sh --reset` to start a fresh thread if:
- The session gets confused or diverges from your intent.
- You want to switch tasks completely without history bleeding over.
- Usage tracking shows the thread has grown very large (OpenAI may charge for token usage in the thread history).

## Codex Limits

The bridge uses your ChatGPT subscription, so rate limits and API restrictions apply. You are **not paying per request**; you are subject to OpenAI's **rate limit windows** (typically requests-per-minute). Check your OpenAI account dashboard for current limits.

## Security Note

The token file at `~/.codex-bridge/token` grants shell-level access to codex-bridge operations. Protect it as you would an SSH key or API token. Do not commit it to version control.

**Host-classifier gotcha (ultra-tier / high-autonomy delegates):** dispatching an ultra-tier delegate (e.g. `astra`) through codex-bridge/workerbee with `--approve-for-me` has been blocked by Claude Code's host permission classifier even when the same flag on a lower-tier delegate (`terra`/`luna`) was not blocked. Best-guess cause: auto-approve combined with autonomous git-push/PR authority reads as higher risk to the classifier. Fix observed: one live, explicit in-session operator approval ("i approve") unblocked it immediately, no code or flag change needed. **Do not loop retries on this block** — surface it and ask the operator for a live approval instead.

## @-routing hook (at_route.sh)

`scripts/at_route.sh` is a Claude Code `UserPromptSubmit` hook. When a prompt starts with `@<alias> <question>`, the hook sends the question to a cheaper model before the main model sees the prompt. It then prints the answer as extra context and tells the main model to relay it verbatim. Prompts that do not match are ignored, and the hook prints nothing.

The alias match is case-insensitive:

| Alias | Backend | Model ID |
|---|---|---|
| haiku | `claude -p` | latest (alias) |
| sonnet | `claude -p` | latest (alias) |
| opus | `claude -p` | latest (alias) |
| fable | `claude -p` | latest (alias) |
| astra | `agent.sh submit --backend codex --wait` | `gpt-6-astra` |
| sol | same | `gpt-6.1-sol` |
| terra | same | `gpt-6.1-terra` |
| luna | same | `gpt-6-luna` |

Each call has a 120-second limit, enforced with `perl` `alarm` so that GNU `timeout` is not needed. If a call fails, the hook prints the exit code and the stderr output, and asks the main model to answer the question itself. The hook always exits 0, so it never blocks a prompt. Each call adds one line to `~/.codex-bridge/at_route.log` with the UTC timestamp, alias, exit code and elapsed seconds.

**Recursion guard.** The nested `claude -p` call would trigger the same hook again. The hook runs every nested call with `AT_ROUTE_ACTIVE=1` and exits at once when it sees that variable.

**Codex aliases are best effort.** `--backend codex --wait` is currently broken because the daemon cannot find `codex` on its PATH (see Codex Limits). Until that is fixed, expect astra, sol, terra and luna to take the failure path.

Update 2026-09-23: the "codex CLI not found on PATH" error was a misreport. `bridge.py` catches `FileNotFoundError` from `subprocess.run`, and that error also fires when the daemon `--workdir` no longer exists. Restart with `up.sh --workdir <existing dir>` and the Codex aliases work. The hook now reads the job id from `submit --wait` and prints `agent.sh result <id>`, which is the answer text.

**Install.** The installer owns the `UserPromptSubmit` hook entry and the `@alias` links, so `agents-inc install` is the only install step. The hook runs from `~/.local/share/agents-inc/current/skills/codex-bridge/scripts/at_route.sh`. `agents-inc doctor` warns with `WB_HOOK_DRIFT` when the installed hook differs from the release copy. A hand-copied script under `~/.claude/scripts` is no longer needed.

The hook needs `jq`. Without `jq` it does nothing. Test it with `bash skills/codex-bridge/tests/at_route.smoke.sh`; the test stubs `claude` and never calls a real model.

### Block mode is the default (2026-09-23)

A measured relay run showed the main model rewriting the delegate's answer instead of relaying it, and a verbatim relay still costs output tokens equal to the answer length. So the hook now exits 2 on success: the prompt is blocked, the main model never runs, and the answer is shown to the operator on stderr. Nothing enters the conversation context, so treat `@alias` as a side question. Set `AT_ROUTE_MODE=relay` in the hook's environment to restore context injection (exit 0, answer on stdout) when the answer must be visible to the main model.

Measured on "explain database connection pooling in about 150 words", `claude -p --output-format json`:

| path | main-model output tokens | cost USD |
|---|---|---|
| Fable direct | 582 | 0.78 |
| Haiku via hook + Fable relay turn | 351 (Fable rewrote, did not relay) + Haiku 0.009 | 0.60 |
| Haiku via hook, block mode | 0 | 0.009 |

### Lexicon

The hook recognizes three syntaxes:

| Syntax | Mode | Description |
|---|---|---|
| `@<alias> <question>` | Block | Side question. Main model never runs; answer shown to operator only on stderr. Zero main-model cost. |
| `@@<alias> <question>` | Relay | Shared question. Answer injected into main model context. Main model relays the answer to the operator. |
| `@openrouter <question>` | Block | Side question routed through `oask.sh` to `openrouter/auto:free`. The answer header names the model that actually answered. Add `@@` for relay mode. |
| `~@<alias> <question>` | Escape | Bypass the hook. Prompt passed to session model exactly as typed, including the `~@` prefix. |

All aliases (haiku, sonnet, opus, fable, astra, sol, terra, luna, gemini, mistral, openrouter) are case-insensitive. The `@@` prefix forces relay mode regardless of the `AT_ROUTE_MODE` environment variable. If a single `@` is used, the mode defaults to block unless the environment variable `AT_ROUTE_MODE=relay` is set.
