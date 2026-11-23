# Start here

## What this is

agents-inc lets Claude Code hand work to other models. A supervising model (the Lead) splits a request among cheaper models (Workers) and checks what comes back. A stricter governed path adds a scripted check and a separate reviewer before a result counts. That path (`WORKERBEES_GOVERNANCE`) is off by default.

This page is for people who have not run it before. The other docs are written for experienced readers.

## Requirements

- Python 3.11 or later.
- Bash 3.2 or later. macOS system Bash works.
- `jq` and `curl`.
- Claude Code CLI, signed in through an Anthropic subscription.
- Optional: Codex CLI, signed in through a ChatGPT account. Its model slugs depend on your account. `~/.config/agents-inc/roster.json` overrides the defaults in `agents_inc/routing.json`.
- Optional: Gemini, Mistral or OpenRouter API keys. See below.

## Install (0.8.0)

```bash
pip install agents-inc
agents-inc install
agents-inc doctor      # the first line prints READY when the install works
```

- Restart Claude Code (and Codex, if you use it) afterward.
- The skills ship inside the package, so you need no git checkout. To install from a checkout, run `python3 -m agents_inc.install.cli install --source "$PWD"` from it.
- Claude Code is the only required provider. If the `codex` CLI is missing, install prints a `NOTE:` line and carries on. `--without-codex` (on `install` and `repair`) skips Codex on purpose and silences the note.
- Install also adds a small Claude Code add-on (the mod) when `claude` is on your PATH. `--no-mod` skips it. If `agents-inc doctor` prints `MOD_NOT_INSTALLED`, the add-on is missing. The rest still works and `READY` still prints.
- Install edits `~/.claude/settings.json`. It shows the entries and asks first. The full list is in the README under "Hooks this installs".
- Fixing a broken install: `agents-inc repair`.

Tool permissions, the sandbox and the broker are covered in [HOW-IT-WORKS.md](HOW-IT-WORKS.md#sandbox-constraints).

## Optional providers and keys

You can skip this section. Claude alone is enough.

1. Run `python3 -m workerbees.keys gemini`. It opens the provider's key page and asks for a hidden paste. Press Enter to skip.
2. Repeat with `mistral` and `openrouter` if you want them.
3. Keys are saved to `~/.config/workerbees/.env` with mode `0600`. The agent never sees the raw key.

A skipped key only removes that provider from the pool. Optional providers get only small `extract` and `summarize` jobs.

Never type a key into a command or paste it into a chat with a model. If a real key ends up in a chat, replace it.

Text sent to a cloud model goes to that company's servers. Decide what may leave your machine before you send it.

To try the system with no keys, run this from a checkout:

```bash
PYTHONPATH=. python3 tools/governance_demo.py --fake
```

## Your first dispatch

Tell the Claude Code session what to do and which models to use. For example: "Fix the parser. opus, haiku." The higher model manages the lower one.

For Claude models the session uses Claude Code's own Agent tool. For other models it uses the agent types the mod registers, such as `agents-inc:luna`. `agents-inc native status` lists the types available to you. Claude Code's agent gate still applies, and it asks you when approval is needed.

`agents-inc dispatch` is the lower-level command for cross-provider jobs and scripts. Every launched dispatch writes one row to the ledger. See [Asking for work](HOW-IT-WORKS.md#asking-for-work) for the details. To change the default supervisor, run `agents-inc models chain supervisor=opus`.

## Watching a delegate

Delegate models appear as agent types you call with the Agent tool. You get the delegate's report when it finishes.

- To stop a run started with `agents-inc dispatch`, run `agents-inc dispatch --cancel <run dir>`.
- A guest agent keeps its thread across a Claude Code restart. `agents-inc handles list` shows the handles of the newest session. `agents-inc handles retire <id>` ends one. Ask the agent for a handoff note first and paste it into a new Agent.
- An older relay route (`agents-inc:relay`) is off by default. `agents-inc install --legacy-routes` turns it on. With it, allow the tool `mcp__agents-inc__run` in your Claude Code permissions, or Claude asks every time. The relay shows short rows while the delegate reads, edits and runs commands.
- To install the mod by hand, see `mods/agents-inc/README.md`.

## The one rule

The thing that checks the work must not be the thing that did the work.

A model can report what it meant to produce instead of what it produced, and the report can look convincing. So a self-reported result is not evidence. Write the check yourself, or have the supervising model write it where the worker cannot edit it. Then run it.

## What it costs

- An Anthropic subscription covers Claude models. A ChatGPT subscription covers the Codex models.
- Gemini, Mistral and OpenRouter keys are pay-per-use or free-tier.
- The cap on extra spend is $0 per task. When a quota runs out, the system pauses and reports. It does not fall back to a paid API.
- Unknown price is not zero. Treating it as free once inflated a savings figure about 29 times ([HOW-IT-WORKS.md](HOW-IT-WORKS.md#money)).

## Developing on a machine that runs the install

Install from a release worktree, not from the checkout you edit:

```bash
git worktree add ../agents-inc-release v0.7.0   # any release tag
agents-inc repair --source ../agents-inc-release
```

- After an install from a clean checkout, `INSTALL_STALE` appears only when `HEAD` moves to a commit whose installed files differ. Uncommitted edits never stop dispatch.
- Installing from a checkout with uncommitted changes installs them and prints a `WARNING:`. Any further edit there makes the install stale, and dispatch stops until you run `repair`.
- A `NOTE:` says when `HEAD` is not on a release tag. Neither message stops the install.
- To upgrade, run `git -C ../agents-inc-release checkout <tag>`, then the `repair` line again.
- From a checkout, `bash scripts/install_skills.sh` syncs the skills listed in `skills.requirements.txt`. `--dry-run` shows what would change.

## Where to read next

- [HOW-IT-WORKS.md](HOW-IT-WORKS.md): the whole system.
- [EXTENDING.md](EXTENDING.md): new models, vendors and domains.
- [`skills/workerbee/SKILL.md`](../skills/workerbee/SKILL.md): the full supervision rules and their failure history.
