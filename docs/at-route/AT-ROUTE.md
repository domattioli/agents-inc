# At-route: ask a cheaper model without leaving your session

At-route is a Claude Code `UserPromptSubmit` hook. When a prompt starts with `@<alias>`, the hook sends the question to that model and shows you the answer. The expensive session model never runs. You stay in the same session, keep its context, and pay the cheap model's price for the side question.

Script: [`skills/codex-bridge/scripts/at_route.sh`](../../skills/codex-bridge/scripts/at_route.sh).
Smoke test: [`skills/codex-bridge/tests/at_route.smoke.sh`](../../skills/codex-bridge/tests/at_route.smoke.sh).

## Lexicon

Default is the hook form. It is the only form that costs the session model nothing.

| You type | Who answers | Session model cost | Notes |
|---|---|---|---|
| `@haiku what does this flag do` | Haiku | zero | Default. Prompt is blocked, answer shown in a cyan box under Claude Code's yellow "blocked by hook" line. Not in context. |
| `@@haiku what does this flag do` | Haiku, in a persistent session | two short turns | Claude aliases: the session model sends the question to a long-lived background session named `at-haiku` and relays its reply with a `haiku ▸` prefix. The side session keeps its context between questions. Other aliases: answer injected as context, as before. |
| `! @haiku what does this flag do` | Haiku | one turn | Shell form. Clean output in the conversation, in context, works mid-turn. Needs the symlinks under Install. |
| `~@haiku literal text` | Session model | one turn | Escape. Prompt reaches the session model as typed. |

Shell note for the `!` form: zsh expands `?` and `*` before the command runs, so `! @luna ready?` fails with `no matches found`. Quote the question, or add `setopt no_nomatch` to `~/.zshrc`.

## Names

The names below follow D63. The family name is consult; "side question" is the old name.

| Form | Name | Status |
|---|---|---|
| `@a q` | Sidebar | Works today |
| `@@a q` | Sync | Claude aliases: works today, one persistent side session. Codex aliases: one fresh tool-free run per question today; the persistent thread is planned, D62 PR A |
| `@@a /new` | Ends a Codex Sync | Planned, D62 PR A; Claude aliases reject slash commands |
| `@a! q` | Follow-up | Planned, D62 PR A |
| `@inbox` | In-tray | Planned, D62 PR A |
| `@<handle> q` | Sidebar with a live Worker | Proposed, D63 |
| `@@<handle> q` | Sync with a live Worker | Proposed, D63 |
| `@<handle>! note` | Memo | Proposed, D63 |
| `@standup` | Stand-up | Proposed, D63 |

## Which form saves the most session-model tokens

Measured 2026-09-23 from this session's transcript, about 195k tokens of context at the time. The delegate does not matter here; only whether the session model takes a turn.

| form | session-model input | session-model output | turns |
|---|---|---|---|
| `@luna q` hook, exit 2 | 0 | 0 | 0 |
| `! @luna q` shell | ~195k cache-read | ~20, a short ack | 1 |
| `@@luna q` relay | ~195k cache-read | ~350 | 1 |
| ask the session model directly | ~195k cache-read | ~580 | 1 |

Every form except the hook triggers a session-model turn, and a turn re-reads the whole context. In a long session that read is the dominant cost, so the hook form is the only real saving. The other forms trade tokens for having the answer in context.

Future work: a display path that shows the delegate's answer inline without a session-model turn and without the hook-block framing. Candidates are a status-line reader for the answers log, or a Claude Code change that lets a hook return operator-visible text on exit 0 without a model turn.

Aliases, case-insensitive:

| Alias | Model | Path |
|---|---|---|
| `haiku` | `claude-haiku-5-5` | `claude -p` |
| `sonnet` | `claude-sonnet-5-5` | `claude -p` |
| `opus` | `claude-opus-5-5` | `claude -p` |
| `fable` | `claude-fable-5-1` | `claude -p` |
| `astra` | `gpt-6-astra` | codex-bridge daemon |
| `sol` | `gpt-5.6-sol` | codex-bridge daemon |
| `terra` | `gpt-5.6-terra` | codex-bridge daemon |
| `luna` | `gpt-6-luna` | codex-bridge daemon |
| `gemini` | `gemini-3.8-flash` | `gask.sh --tier digest` |
| `mistral` | `codestral-latest` | `mask.sh --tier code` |
| `openrouter` | free tier via `oask.sh` | OpenRouter |

Default is the single `@` form. Use `@@` only when the next thing you ask the session model depends on the answer, or when you want follow-up questions to the same side session.

## Persistent side sessions (`@@` with a Claude alias)

Added 2026-10-01. `@@haiku`, `@@sonnet`, `@@opus`, and `@@fable` no longer start a fresh `claude -p` per question. The hook prints instructions, and the session model:

1. Looks for a peer session named `at-<alias>` with Claude Code's native `ListAgents` tool.
2. Starts one if it is missing: `claude --bg -n at-<alias> --model <id> --allowedTools "Read,Grep,Glob" --disallowedTools "Edit,Write,NotebookEdit,Bash" "<bootstrap prompt>"`. Bash is denied so a side session cannot write files through the shell (fixed 2026-10-18).
3. Sends the question with `SendMessage` and ends its turn.
4. Relays the reply, which arrives as a cross-session message, with the `<alias> ▸` prefix.

What this buys: the side session remembers earlier questions, so follow-ups work, and there is one warm process instead of a cold start per question. What it costs: two short session-model turns (send, then relay) instead of one. The side session's context also grows; stop it with `claude stop <id>` (`claude agents` lists ids) to start fresh.

Setup notes:

- Auto mode blocks the first spawn as "Create Unsafe Agents". Approve the prompt, or add a narrow allow rule such as `Bash(claude --bg -n at-*)` to `~/.claude/settings.json`.
- Nobody watches the side session, so a permission prompt there stalls it without a reply. It may use `Read`, `Grep`, and `Glob` without a prompt. A question that needs any other tool will stall; ask it with single `@` or in the main session.
- `@@` refuses slash commands such as `@@haiku /check-in`. The side session would run the command on itself, not on your session. Use `@haiku /check-in` instead.
- `AT_ROUTE_PERSIST=0` restores the old one-shot `@@` relay.
- Codex, Gemini, Mistral, and OpenRouter aliases are not Claude Code sessions, so their `@@` keeps the one-shot relay.


## Check in on a session (`@haiku /check-in`)

Added 2026-10-01. `@haiku /check-in` gives a status card for the session you type it in, and the session model never runs. Any Claude alias works.

1. The hook reads the session's transcript path, session id, and working directory from the prompt event.
2. It runs the check-in skill's fact script (`checkin_state.sh --transcript`) in plain shell. This takes under a second and calls no model.
3. It adds the session's last few replies and asks the alias model for a card of ten lines or fewer: NEED YOU, RECOMMEND, GOAL, DONE, NOW, NEXT, RISK, MODES, REPO.
4. The card prints in the usual box. The session model does not run, so the check-in costs only the alias model's tokens.

Limits:

- The card is read-only. It names what waits on you but does not ask you questions one at a time the way `/check-in` does inside the session.
- It needs the check-in skill at `~/.claude/skills/check-in`. Set `AT_ROUTE_CHECKIN_SCRIPT` to use another path. Without the script, `/check-in` goes to the alias model as a plain question.
- `@@haiku /check-in` uses the one-shot relay, not the side session. A side session would load the skill for itself and report on its own state.

## Measured savings

Question: "explain database connection pooling in about 150 words". Measured 2026-09-23 with `claude -p --output-format json`, which reports token usage and cost per call.

| Path | Session-model output tokens | Cost (USD) | Saving |
|---|---|---|---|
| Ask Fable directly | 582 | 0.78 | baseline |
| `@@haiku` (shared, session model relays) | 351 | 0.60 | 23% |
| `@haiku` (side question, session model skipped) | 0 | 0.009 | 99% |

Why `@@` saves so little: the session model still has to write the answer back out, and in the measured run it rewrote the answer instead of relaying it. Output tokens are the expensive part, so the shared form is only worth it when the session model needs the answer in context.

Latency for a short question: about 5 to 6 seconds for both Claude and Codex aliases.

## How it works

1. Claude Code runs every `UserPromptSubmit` hook before the session model sees your prompt, passing the prompt as JSON on stdin.
2. The hook matches `^(@@?)(alias)\s+(question)$`. No match: exit 0, print nothing.
3. Claude aliases run `claude -p "<question>" --model <id>`. Codex aliases run `agent.sh submit --backend codex --model <id> --wait`, then `agent.sh result <job id>` for the answer text.
4. Single `@`: answer goes to stderr and the hook exits 2. Exit 2 blocks the prompt, so the session model never runs, and stderr is shown to you. The answer is framed in a box whose top line names the delegate, its model id and the elapsed seconds, so it is never mistaken for a session-model reply.
5. Double `@@` with a Claude alias: the hook prints the persistent-session instructions above and exits 0 without calling a model. Double `@@` with any other alias: answer goes to stdout and the hook exits 0. Stdout becomes extra context for the session model, with a one-line instruction to relay it. The instruction tells the session model to begin its reply with `<alias> ▸` and then the answer verbatim.
6. On any failure the hook prints the error as context and exits 0, so the session model answers the question itself.

Recursion guard: the hook exports `AT_ROUTE_ACTIVE=1` around the nested `claude -p` call and exits immediately if that variable is already set. Without it the nested call would fire the same hook again.

Every call appends one line to `~/.codex-bridge/at_route.log`: UTC timestamp, alias, exit code, seconds.

## Install

Run `agents-inc install --source <agents-inc checkout>` or `agents-inc repair --source <agents-inc checkout>` to install the hook and the alias links. The installer writes the hook entry to `~/.claude/settings.json`, creates the symlinks under `~/.local/bin`, and manages a journal so an interrupted install can be rolled back.

The hook runs from the installed release, reached through `~/.local/share/agents-inc/current/skills/codex-bridge/scripts/at_route.sh`. This path survives branch checkouts and is covered by the bundle hash check.

The settings hook entry is receipt-owned and points to the installed path with a timeout of 130 seconds (must exceed the default `AT_ROUTE_TIMEOUT` of 120 seconds; raise the timeout if you raise `AT_ROUTE_TIMEOUT`):

```json
{
  "type": "command",
  "command": "bash ~/.local/share/agents-inc/current/skills/codex-bridge/scripts/at_route.sh",
  "timeout": 130
}
```

The `@alias` links (11 total: `haiku sonnet opus fable astra sol terra luna gemini mistral openrouter`) are created in `~/.local/bin` and point to the same installed path. They are receipt-owned and removed by uninstall.

If you have a legacy `~/.claude/scripts/at_route.sh` copy, the installer replaces its settings line with the new entry, relinks the aliases, and removes the legacy file with a journaled backup. The legacy-file backup is kept under `~/.local/state/agents-inc/backups/` for manual restore if needed; journal recovery of an interrupted install restores it automatically.

`agents-inc doctor` checks for drift between the installed hook and the source checkout's `skills/codex-bridge/scripts/at_route.sh`. It warns with `WB_HOOK_DRIFT` when the installed copy differs, or `WB_HOOK_DRIFT_UNCHECKED` when the source checkout is unknown or missing. Doctor stays READY; these are warnings only.

Requirements: `jq`, `perl` (for the portable 120-second timeout), the `claude` CLI on PATH. Codex aliases also need the bridge daemon running: `skills/codex-bridge/scripts/up.sh --workdir <an existing directory>`.

### Read-only tool set for routed Claude calls

Every Claude alias (`haiku`, `sonnet`, `opus`, `fable`) routes the question through `claude -p` with a read-only tool restriction. The routed model can read any file the caller can read but cannot create files, modify files, or run shell commands. Allowed tools: `Read`, `Grep`, `Glob`. Denied tools: `Edit`, `Write`, `Bash`, `NotebookEdit`. No MCP servers are reachable. This restriction prevents routed calls from leaving partial or corrupted files in your working tree.

### Timeout behavior

Every routed call runs under a 120-second timeout by default (set by `AT_ROUTE_TIMEOUT`). When the timeout fires (exit code 142), the failure block names the timeout in seconds, warns that partial files may exist in your working tree, and tells you to run `git status` to inspect the state:

```
[at_route] <alias> call timed out after 120s (exit 142). Partial files may exist in the working tree: run `git status` before answering.
```

This replaces the earlier cryptic `exit 142` message and helps distinguish a timeout from other failures.

Environment overrides:

| Variable | Default | Effect |
|---|---|---|
| `AT_ROUTE_MODE` | `block` | `relay` makes single `@` behave like `@@` |
| `AT_ROUTE_TIMEOUT` | `120` | Seconds before the delegate call is killed |
| `AT_ROUTE_LOG` | `~/.codex-bridge/at_route.log` | Log path |
| `AT_ROUTE_ANSWERS` | `~/.codex-bridge/at_route_answers.log` | Transcript of every question and answer |
| `AT_ROUTE_COLOR` | `1` | Cyan box in block mode. `0` for plain text. Claude Code passes the escape codes through; the yellow text above the box is Claude Code's own hook framing. |

## Known limits

- A prompt sent while the session model is still working is queued, and Claude Code does not show hook stderr for queued prompts. The delegate still answers. Read missed answers with `tail -20 ~/.codex-bridge/at_route_answers.log`. Send side questions between turns to see them inline.
- A side question leaves no trace in the session. If you want the session model to build on the answer, ask with `@@` or paste the answer in.
- The daemon's `--workdir` must exist. If it is deleted, every Codex alias fails with a misleading `codex CLI not found on PATH` error from `bridge.py`. Restart the daemon from a stable directory.
- A delegate can refuse. Haiku declined a joke prompt during testing. The refusal is shown to you like any other answer.
- OpenRouter aliases are not wired yet. The bridge has `oask.sh`, so adding one is a small change in the alias table.
- Gemini returns upstream 503 errors during demand spikes. The hook reports the failure and the session model answers instead.

## OpenAI bench

48-call bench across luna, terra, sol and astra with latency and token tables: [AT-ROUTE-BENCH.md](AT-ROUTE-BENCH.md). Short version: about 26k input tokens per fresh call, 5 to 25 seconds, zero metered cost under the ChatGPT subscription.

## Prior art

Survey of similar tools and what is new here: [AT-ROUTE-PRIOR-ART.md](AT-ROUTE-PRIOR-ART.md). Short version: Claude Code hooks that pick a model per session or per subagent exist, and `auto-model-router` uses a `#model=` prompt tag, but none blocks the prompt and answers from the hook. The `@` versus `@@` split and the shared Claude plus Codex alias table appear to be new.
