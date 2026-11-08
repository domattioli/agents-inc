# Proposal: narrate

Status: prototype. Not wired into Claude Code hooks or launchd.

## What it does

`agents-inc narrate run` follows the active Claude Code transcript and speaks a short digest of each new assistant message through macOS `say`. The operator can step away from the screen and still hear what changed and what needs a decision.

## Design

- Watcher: finds the newest-modified `*.jsonl` under the Claude Code `projects` folder (one subfolder per workspace) or takes `--transcript`. It polls the file and reads only appended complete lines.
- Parsing: only records of type `assistant` count. Only `text` blocks are kept. `tool_use` and `tool_result` content is dropped. Fenced code and markdown are stripped before anything else sees the text.
- Summarizer protocol: `summarize(text) -> str`.
  - `LunaSummarizer` runs `agents-inc run --model luna --no-tools --cwd <cwd>`. The launcher reads the prompt from stdin and prints the reply on stdout. It is the only path to luna: no OpenAI API call, no key.
  - `LocalSummarizer` returns the first paragraph cut to 280 characters. No model call.
- Speaker: one worker thread drains a queue and runs `say -v <voice>`, so utterances never overlap.
- Gate: the file `narrate-on` in the agents-inc settings directory (`~/.config/agents-inc/`). When it is absent, the watcher idles: it consumes new messages and speaks nothing.

## Why a model

The assistant text is long and written for reading. A fixed rule cannot say what changed and what the operator must decide. A small model can. luna is the cheapest rung and this is a summarize task, which optional providers are allowed to do.

## Latency and quota

A luna call takes about 5 to 15 seconds, so the digest trails the message. Each call uses Codex quota. A quota pause (launcher exit code 75) or any non-zero exit makes that message fall back to the local summarizer, and the voice says "local" first so the operator knows it is not a model digest. The ledger exposes no quota-paused signal, so the exit code is the signal.

## Privacy

With the luna summarizer the assistant text leaves the machine. Two controls exist:

- The classification guard skips a message and speaks nothing when it matches `U//FOUO`, `FOUO`, `CLASSIFIED`, `SECRET`, or `NOFORN` (case-insensitive). The skip is logged to stderr. The guard runs before any summarizer, so a marked message never reaches luna.
- `--summarizer local` keeps everything on the machine.

The guard is a keyword match. It cannot catch sensitive text that carries no marker.

## Accuracy

luna's words are a paraphrase of the assistant's text, not the assistant's decision. The operator must read the real message before acting on a digest.

## Modes

- `--decide-only`: speak only messages with a question mark in the final paragraph or the token `DECIDE`.
- `--once`: process the latest assistant message and exit (smoke tests).
- `--dry-run`: print the digest instead of speaking. It also ignores the flag file.

## Open items

- Hook or launchd wiring to start the watcher with a session.
- When a newer transcript appears mid-run, the watcher starts at its end and skips earlier messages.
- Voice selection per workspace.
