<p align="center"><img src="https://raw.githubusercontent.com/domattioli/agents-inc/main/docs/assets/logo-wide.png" width="100%" alt="agents-inc: a crew of original cartoon monsters at work on a night-shift dispatch floor"></p>

# agents-inc

<p align="center"><strong>agents-inc runs AI models the way a company runs staff: a Lead takes your request, delegates it down an org chart of cheaper Worker models, and accepts nothing until a reviewer signs off. The aim is more checked work from the AI subscriptions you already pay for.</strong></p>

<p align="center">
<img alt="Status: experimental" src="https://img.shields.io/badge/status-experimental-orange">
<a href="https://github.com/domattioli/agents-inc/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/domattioli/agents-inc/actions/workflows/tests.yml/badge.svg"></a>
<a href="https://pypi.org/project/agents-inc/"><img alt="PyPI" src="https://img.shields.io/pypi/v/agents-inc?cacheSeconds=3600"></a>
<img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-blue">
<a href="https://github.com/domattioli/agents-inc/blob/main/LICENSE"><img alt="License: PolyForm Small Business 1.0.0 + no-AI terms" src="https://img.shields.io/badge/license-PolyForm%20SB%201.0.0%20%2B%20no--AI%20terms-lightgrey"></a>
<a href="https://github.com/domattioli/agents-inc/issues"><img alt="Open issues" src="https://img.shields.io/github/issues/domattioli/agents-inc"></a>
<a href="https://doi.org/10.5281/zenodo.22670100"><img alt="DOI" src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.22670100-blue"></a>
</p>

## Table of Contents

1. [Status & Roadmap](#1-status--roadmap)
2. [Why it exists](#2-why-it-exists)
3. [Installation](#3-installation)
4. [Quick start](#4-quick-start)
5. [How it works](#5-how-it-works)
6. [Limitations](#6-limitations)
7. [Documentation](#7-documentation)
8. [Citation and license](#8-citation-and-license)

## 1. Status & Roadmap

Version 0.6.4. The project is experimental and pre-MVP. The governed path (`WORKERBEES_GOVERNANCE`) is off by default. Changes per release are in the [CHANGELOG](https://github.com/domattioli/agents-inc/blob/main/CHANGELOG.md). The build plan and cut line are in [docs/PLAN-MVP.md](https://github.com/domattioli/agents-inc/blob/main/docs/PLAN-MVP.md). Open work is tracked in [the issues](https://github.com/domattioli/agents-inc/issues).

- **Now:** measure the token cost of delegation against doing the work in one session, and port the test suite to Windows ([#138](https://github.com/domattioli/agents-inc/issues/138)).
- **Next:** let a Worker launched by a broker lead its own Workers ([#73](https://github.com/domattioli/agents-inc/issues/73)).
- **Later:** route work by data classification, so unpublished work reaches only approved providers ([#19](https://github.com/domattioli/agents-inc/issues/19)).

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>

## 2. Why it exists

Delegated model work can look done while it is wrong. A flat pool of agents has no way to catch that. `agents-inc` borrows a [corporate org chart](https://github.com/domattioli/agents-inc/blob/main/docs/governance/DELEGATION-MODEL.md). The CEO is you. The CoS (chief of staff) is the session you talk to. A Lead manages one run, and a Worker reports to a Lead.

Cheap models take routine work, and costlier models manage. An author never grades its own work: the Lead checks what its Workers report before anything moves up. Savings are not yet measured, so none are claimed ([docs/PLAN-MVP.md](https://github.com/domattioli/agents-inc/blob/main/docs/PLAN-MVP.md)).

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>

## 3. Installation

Requirements: Python 3.11 or later, Bash 3.2 or later, `jq`, `curl`, and the Claude Code CLI signed in to an Anthropic subscription. The Codex CLI is optional; when present, it serves the Codex rungs and cross-vendor review.

```bash
pip install agents-inc
agents-inc install     # skills ship in the package; no checkout needed
agents-inc doctor      # first line prints READY when the install works
```

Restart Claude Code (and Codex, if used) after the install. `agents-inc install --without-codex` skips Codex on purpose. To install from a git checkout instead, pass `--source <checkout>`. Optional Gemini, Mistral and OpenRouter keys, the setup decision tree and key storage rules are in [docs/START-HERE.md](https://github.com/domattioli/agents-inc/blob/main/docs/START-HERE.md).

### Hooks this installs

`agents-inc install` adds these hooks to `~/.claude/settings.json`, plus `"agents-inc dispatch *"`, `"agents-inc run *"`, `"agents-inc repair *"` and `"agents-inc install *"` under `sandbox.excludedCommands` so a sandboxed Bash can start a dispatch (each delegate and each gate still gets its own `sandbox-exec`). It prints the entries first and asks before writing; `--yes` skips the question, and with no terminal and no `--yes` it writes nothing and prints the command to run. `--no-sandbox-exclude` leaves the exclusion out. `repair` replaces an older `"agents-inc *"` entry with the narrow ones. `agents-inc unwire` removes only these entries.

- `SessionStart` gives Claude Code and Codex host-specific routing guidance.
- Claude Code's `PreToolUse` hook checks Agent/Task routing, prevents persona
  impersonation, and warns about duplicate delegations. The `PostToolUse` hook
  records the result and releases the foreground task's duplicate claim.
- Codex's `SubagentStart` and `SubagentStop` hooks record observed lifecycle
  events when the host runs trusted hooks.
- Claude Code's `UserPromptSubmit` hook routes `@alias` questions with
  `--legacy-routes`.

### Choose the route in your host

| Host | Route |
|---|---|
| Codex | Use a native subagent when the session offers the requested model and permits delegation. Reserve agents-inc dispatch in Codex for authorized Claude integration tests. |
| Claude Code | Use Agent for an offered Claude model when the agent gate permits it. With the mod, use Agent with a registered guest type such as `agents-inc:luna` for an authorized cross-provider task. Check `agents-inc native status`. |
| Gemini | Use a native subagent if the current session offers it and permits the task. |
| Scripts and broker Workers | Use governed `agents-inc dispatch` within the existing grants. |

Resolve the requested model against the host's current catalog. Keep the brief
and file scope small. Let the host handle required approvals and continue
independent work if a delegate is unavailable or denied. Verify the result before
accepting it. The [routing and ledger guide](docs/HOW-IT-WORKS.md#native-delegation)
describes what each host records.

**Claude agent gate.** The default `advisory` mode allows host-permitted
Claude Agent calls. `off` also leaves these calls to the host. `enforce`
allows the foreground types `Explore`, `Plan`, `claude-code-guide`, and
`statusline-setup`, plus the registered agents-inc types. All modes retain
the persona guard. Check the effective mode with `agents-inc doctor` and
configure it with `agents-inc repair --agent-gate enforce|advisory|off`.

The relay type, `mcp__agents-inc__run` and `@alias` are optional legacy routes.
Enable them with `agents-inc install --legacy-routes` or
`agents-inc repair --legacy-routes`. Repair preserves that choice unless
you pass `--no-legacy-routes`.

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>

## 4. Quick start

Name your models in plain English. The ladder decides who manages whom, and the rest fills in. You do not hand-pick every model or write JSON.

Write the request to the CoS as `<task>. <models>.`, for example:

> "Fix the parser. opus, haiku."

The higher rung manages and the lower rung reports to it, so opus is the Lead and haiku is its Worker. Defaults fill the rest: effort medium, gates derived from the task, and the home repo from the consumer's `AGENTS.md`. Each extra word, such as an effort level, overrides one default.

| Rung | Claude | Codex | Role |
|---|---|---|---|
| Executive | fable | astra | Final say, irreversible acts, conflicting results |
| Orchestrator | opus | sol | Decompose, dispatch, plan |
| Workhorse | sonnet | terra | Normal coding, research, synthesis |
| Grunt | haiku | luna | Classify, extract, summarize, or make task-authorized edits; free Gemini, Mistral and OpenRouter models enter only here |

For governed dispatch, the CoS uses one command to render and lint the brief, snapshot the tree, launch the delegate and run the checks:

```bash
agents-inc dispatch --slots slots.json --model sonnet --dry-run
agents-inc models chain supervisor=opus                            # change the default REPORTING CHAIN
```

Every dispatch prompt carries a `REPORTING CHAIN` line derived from the ladder, and every launched dispatch writes one `dispatched` row to the ledger. Codex delegates can write to `--cwd` by default, the same as a Claude subagent; the slot `CODEX_WRITE: no` makes one read-only. Use `TASK_ACCESS: read` to deny worker workspace writes, or `TASK_ACCESS: write` with `FILES_IN_SCOPE` for an authorized edit. Existing dispatches without the field retain their previous permissions. Scope is checked after execution; supervisor gates run on the host. A worked slots file is in [skills/workerbee/slots.md](https://github.com/domattioli/agents-inc/blob/main/skills/workerbee/slots.md).

**Narrate (prototype, macOS).** `agents-inc narrate on` enables a watcher; `agents-inc narrate run` follows the active Claude Code transcript and speaks a two-sentence digest of each new assistant message with `say`. luna writes the digest through `agents-inc run`, so message text leaves the machine: messages with a classification marker are skipped, and `--summarizer local` makes no model call. Other options: `--voice`, `--transcript`, `--decide-only`, `--once`, `--dry-run`; `off` and `status` complete the set. Design: [docs/proposals/narrate.md](https://github.com/domattioli/agents-inc/blob/main/docs/proposals/narrate.md).

For a trusted MCP client, `agents-inc mcp --cwd /absolute/workspace` exposes governed dispatch, status, results, cancellation, and follow-up; see [the MCP adapter guide](docs/HOW-IT-WORKS.md#workspace-bound-mcp-adapter). Write tasks and host gates require the server’s `--allow-writes` flag.

Two more entry points need no dispatch. `PYTHONPATH=. python3 tools/governance_demo.py --fake`, run from a checkout, shows routing, policy checks and ledger records with no provider keys. With `--legacy-routes`, `@haiku <question>` inside any Claude Code session sends one side question to a cheaper model before the session model runs ([docs/at-route/AT-ROUTE.md](https://github.com/domattioli/agents-inc/blob/main/docs/at-route/AT-ROUTE.md)).

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>

## 5. How it works

![Delegation and support flow: CEO, CoS, Lead, and Worker roles across the nine speckit phases, with model rungs shown as cost classes](https://raw.githubusercontent.com/domattioli/agents-inc/main/docs/assets/delegation-model.svg)

- **Routing.** A router picks the vendor and rung for each task from a written policy ([agents_inc/routing.json](https://github.com/domattioli/agents-inc/blob/main/agents_inc/routing.json)). Rung names are cost classes, not job titles; the reporting chain sets the role.
- **Grilling and speckit.** The CoS grills you one question at a time until the request is sharp, then a speckit pipeline gates it through spec, plan, tasks and review.
- **Verification.** A deterministic verifier checks cited claims with no model call. A reviewer from a different vendor then checks the meaning. A Worker's own PASS never decides acceptance.
- **Ledger.** An append-only JSONL and SQLite ledger records every dispatch, return, review and acceptance decision.
- **Models.** Each Codex alias is pinned to one slug. `agents-inc models` reports drift. Model sync promotes new Codex slugs in `approve` or `auto` mode and skips pinned aliases.

The full description, including the delegation limits, the 14-element prompt contract, the verification flow and the comparison with other tools, is in [docs/HOW-IT-WORKS.md](https://github.com/domattioli/agents-inc/blob/main/docs/HOW-IT-WORKS.md).

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>

## 6. Limitations

- Cost savings and accuracy against a baseline are not measured. Passing local tests show that the code behaves as written, not that it is reliable in production.
- The governed path is off by default, so a fresh install does not run the enforced cross-vendor review.
- Cross-vendor review catches disagreement between models. It does not catch a blind spot that both vendors share.
- Deterministic checks cover what a script can express, such as a file, a quote or an exit code. They do not replace human judgment on scope or design.
- `agents-inc dispatch` must run outside the Claude Code or Codex sandbox, because the sandbox blocks the provider API. Inside it, dispatch exits 69 before any delegate starts and prints the fix: add `"agents-inc dispatch *"` to `sandbox.excludedCommands`. `agents-inc install` and `repair` add that entry; `agents-inc doctor` warns `WB_SANDBOX_EXCLUDE_MISSING` when it is gone.
- Free-model capacity varies: a probe on 2026-09-29 found 429 or capacity errors on several free models ([docs/BENCH.md](https://github.com/domattioli/agents-inc/blob/main/docs/BENCH.md)). Artifacts stay local; remote publication (Bindle Backend B) is not built.

Updates: new sessions and `agents-inc doctor` tell you when a newer release is on PyPI (one check a day; `AGENTS_INC_NO_UPDATE_CHECK=1` turns it off).

Found a bug or want a feature? `agents-inc report bug --title "..." --body "..."` (or `report feature`) prints a draft issue with your version, doctor result and OS; home paths become `~`. Add `--submit` to file it on GitHub with your own `gh` login.

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>

## 7. Documentation

| File | Reader |
|---|---|
| [docs/START-HERE.md](https://github.com/domattioli/agents-inc/blob/main/docs/START-HERE.md) | New users: setup, providers, keys, first job |
| [docs/HOW-IT-WORKS.md](https://github.com/domattioli/agents-inc/blob/main/docs/HOW-IT-WORKS.md) | Operators and agents: dispatch, verification, comparison, HTTP bridge |
| [docs/EXTENDING.md](https://github.com/domattioli/agents-inc/blob/main/docs/EXTENDING.md) | Adding a vendor, model, task class or domain |
| [docs/DECISIONS.md](https://github.com/domattioli/agents-inc/blob/main/docs/DECISIONS.md) | Binding rulings, with rationale and evidence |
| [CONTEXT.md](https://github.com/domattioli/agents-inc/blob/main/CONTEXT.md) | Glossary: CEO, CoS, Lead, Worker, Mandate, Home repo |
| [skills/workerbee/QUICKREF.md](https://github.com/domattioli/agents-inc/blob/main/skills/workerbee/QUICKREF.md) | Short form of the dispatch rules |
| [docs/RELEASING.md](https://github.com/domattioli/agents-inc/blob/main/docs/RELEASING.md) | Release runbook |

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>

## 8. Citation and license

The DOI for all versions is [10.5281/zenodo.22670100](https://doi.org/10.5281/zenodo.22670100). GitHub's "Cite this repository" button reads [CITATION.cff](https://github.com/domattioli/agents-inc/blob/main/CITATION.cff).

> Cite as: DO Mattioli (2026). agents-inc: Cross-Vendor Governance for an Agentic-AI Workforce. Zenodo. https://doi.org/10.5281/zenodo.22670100

agents-inc is licensed under the PolyForm Small Business License 1.0.0 ([LICENSE](https://github.com/domattioli/agents-inc/blob/main/LICENSE)) **plus** additional terms that forbid AI training ([LICENSE-AI.md](https://github.com/domattioli/agents-inc/blob/main/LICENSE-AI.md)). Both apply. Notices: [NOTICE](https://github.com/domattioli/agents-inc/blob/main/NOTICE).

<div align="right"><a href="#agents_inc"><sub>^ Back to top</sub></a></div>
