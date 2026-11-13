# HOW IT WORKS

## Installed direct runtime (pre-MVP)

`pip install agents-inc`, then `agents-inc install`. Skills and the schema ship
as package data, so `install` and `repair` need no `--source` (D55); pass
`--source <checkout>` only to install from a git checkout.
Installation stages an allowlisted immutable bundle under
`~/.local/share/agents-inc/releases`, atomically activates `current`, and links
both hosts to it. The launcher records absolute runtime paths. Claude Code is
required and Codex optional (D50). Codex runs with web search off; astra, sol
and terra get the shell tool, luna only with `--tools`, raw slugs never (D49,
D49.1). A Codex permission profile denies home-directory reads and network.
Under `agents-inc run`, writes need `--write`. Under `agents-inc dispatch`, a
Codex delegate matches a Claude subagent: tools on and write access to `--cwd`
whenever `PERMISSION_MODE` allows edits (`acceptEdits`, the default, or
`bypassPermissions`); the slot `CODEX_WRITE: no` opts out and `yes` forces it
on. `--lead <run-dir>` starts the credential-blind MCP
broker, and Workers launch with a scrubbed environment (D51). HTTP
bridge/daemon lifecycle is unsupported by this installer.

- Reader
  - **Audience**
    - Operators and agents.
  - **Prerequisite**
    - Newcomers should read `START-HERE.md` first.

## System

- Delegation system
  - **Work**
    - Lower-cost models do the work.
  - **Supervision**
    - A higher-cost model supervises.
  - **Purpose**
    - The repo combines plumbing with controls for delegation.

## Two halves

| half | file | owns | question it answers |
|---|---|---|---|
| mechanism | `skills/codex-bridge/` | transport, routing, retries, job state, cost logging | HOW do I send work out |
| judgment | `skills/workerbee/` | tier choice, trust, verification, honesty | SHOULD I, and do I believe the answer |

- Boundary
  - **Mechanism**
    - It has no opinions.
  - **Judgment**
    - It has no code.
  - **Reason**
    - Each half stays replaceable.

## Parts

```text
you (orchestrator)
  │
  ├─ route.sh pick <class>      → which backend for this task class
  │
  ├─ agent.sh submit            → queue job, get id
  │     ├─ codex  → codex CLI      (OpenAI, ChatGPT plan)
  │     ├─ gask.sh → Gemini API     (free tier)
  │     ├─ mask.sh → Mistral API    (paid key)
  │     └─ oask.sh → OpenRouter      (free models ONLY, spend guard)
  │
  ├─ agent.sh wait/result       → saved stdout + result.json
  │
  ├─ usage_db.py                → per-call token log → ~/.codex-bridge/usage.db
  └─ dashboard.py / usage_report.sh → what it cost
```

- Remote bridge
  - **File**
    - `bridge.py` is a separate HTTP server with a codex thread for remote clients.
  - **Local use**
    - Local delegation does not need it.
  - **Exception**
    - Use it when serving a phone.

## One-job flow

- Dispatch
  - **Steps**
    - `route.sh pick <class>` classifies the task and skips backends in cooldown.
    - `agent.sh submit --backend <b> --wait "<prompt>"` queues the job and returns its id.
    - The job retries transient failures automatically and places quota failures in cooldown without retrying.
    - `agent.sh result <id>` returns output and `result.json`.
    - `poll.sh` polls the job for the entire run.
    - You verify the result.
    - Usage is logged for later cost reporting.

## Polling

- Job observation
  - **Rule**
    - Poll every dispatch that outlives one tool call.
  - **Poll command**

```bash
scripts/poll.sh --pid-match <pat> --log <stderr> --out <stdout>
```

  - **Watch command**

```bash
scripts/watch.sh <stderr>
```

  - **Boundary**
    - Poll reports state to the supervisor. Watch streams content to a human in another pane.
    - Never pipe a log into supervisor context because it spends the tokens delegation was meant to save.
  - **States**
    - `RUNNING`, `QUIET`, `RESUMED`, `DONE`, `DIED`, and `TIMEOUT` are emitted only on change.
  - **Exit status**
    - Exit 0 means returned, not verified.
  - **DIED**
    - `DIED` means the process is gone and output is empty.

## Money

- Billing pools
  - **Subscriptions**
    - Anthropic covers opus, sonnet, haiku, and fable through session and weekly limits.
    - ChatGPT covers astra, sol, terra, and luna through rolling ~5h and weekly windows.
  - **API**
    - Gemini free tier, Mistral, and OpenRouter use requests per day or dollars per token.
  - **Budget mode**
    - It shifts work from pool 1 to pools 2 and 3.
    - Token cost falls while verification effort rises.
  - **Measurement**
    - The same dashboard recorded 15,221 Gemini tokens versus 79,077 Haiku tokens, while the external output required more checking because its input was not visible.
  - **Price rule**
    - Unknown price is not zero.
  - **Evidence**
    - Coercing null to 0 inflated a savings figure 29x, from $1.15 to $33.06.
    - Free models use `0.0`. Unknown prices stay absent, and plan-based access has no per-token price.

## Trust

- Independent verification
  - **Failure**
    - A delegate can report GREEN while printing intended measurements instead of actual measurements.
  - **Observed data**
    - One session claimed columns `0 12 44 91 124`. The actual values were `0 12 49 122 214 329 446`.
  - **Verifier**
    - You write it outside the delegate’s workspace and tell the delegate not to edit it.
  - **Evidence**
    - A report needs harness output and an exit code. A claim without output is RED.
  - **Harness gate**
    - Self-test the harness with known-good and known-bad inputs before using it.
  - **Granularity**
    - Check that the harness measures the same granularity as the claim.
  - **Recheck**
    - Re-run the delegate’s own check yourself.
  - **Reference**
    - Discipline is in `../skills/workerbee/SKILL.md`.

## Sandbox constraints

- Execution
  - **Network**
    - `workspace-write` blocks network access. HTTP buddies fail with `Could not resolve host`.
  - **Workaround**
    - Use `-c 'sandbox_workspace_write.network_access=true'`.
  - **Git**
    - The same sandbox blocks `.git/index.lock`, so delegates cannot commit. Expect `Operation not permitted` and have them report `BLOCKED-SANDBOX`.
  - **Repository**
    - Outside a git repo, use `--skip-git-repo-check`.
  - **Review**
    - Use `--sandbox read-only` for review-only work.
  - **Caller sandbox**
    - `agents-inc dispatch` refuses to start from inside the Claude Code Bash sandbox or a Codex sandbox, because that sandbox blocks the provider API. It exits 69 with `detail=caller-sandboxed`. Rerun it outside the sandbox, for example by adding `"agents-inc *"` to `sandbox.excludedCommands` (D65).

## Irreversible actions

- Gates
  - **Counting**
    - Number the gates.
  - **Withholding**
    - Withholding an action after a red gate is the successful outcome.
  - **Ambiguity**
    - An ambiguous gate is RED.
  - **Location**
    - Guards belong on the remote side because a launcher guard cannot protect a remote session.
  - **Duplicate dispatch**
    - Check whether an uncertain dispatch landed before firing it again.

## Stateless providers

- One-shot behavior
  - **Context**
    - Gemini, Mistral, and OpenRouter receive only the prompt, with no tools or repository.
  - **Evidence**
    - Paste source, real rows, and actual output instead of describing a function.
  - **Verification**
    - Buddy output is never evidence. Verify it against the real system with a citation.
- Provider failures
  - **Failover**
    - Fail over across provider families.
  - **Signals**

```text
ask_openrouter: API error: Upstream error from Nvidia: Service temporarily overloaded
ask_gemini: API error: This model is currently experiencing high demand.
ask_mistral: API error: Not enough capacity available for this request, please retry later.
```

  - **Gemini**
    - `503` means capacity and merits a retry.
    - `429` means quota and a retry burns remaining allowance faster.

## Secrets

- Key handling
  - **Source**
    - Keys come from a `.env` file.
  - **Prohibition**
    - Never put keys on a command line, echo them to a log, or paste them into a model prompt.
  - **Dispatch**
    - Name forbidden paths explicitly in every dispatch.
  - **Exposure**
    - If an operator pastes a live key into chat, recommend rotation and continue using the file.

## Legacy wrappers for optional providers

`agents_inc/adapters/` ships claude + codex only. Gemini / Mistral / OpenRouter reach the fleet through `codex-bridge` shell wrappers, not through an adapter module:

| provider | wrapper | key file (or env var) |
|---|---|---|
| Gemini | `skills/codex-bridge/scripts/gask.sh` | `~/.codex-bridge/gemini-key` (`GEMINI_API_KEY`) |
| Mistral | `skills/codex-bridge/scripts/mask.sh` | `~/.config/devstral/api_key` |
| OpenRouter | `skills/codex-bridge/scripts/oask.sh` | `~/.codex-bridge/openrouter-key` (`OPENROUTER_API_KEY` or `OPEN_ROUTER_API_KEY`) |

- Optional-provider access
  - **Key location**
    - Key names are read from `~/.config/workerbees/.env`, the older `~/.config/agents_inc/.env`, and `~/Projects/.env`; `agents-inc` writes only `~/.config/workerbees/.env`. A missing file does not mean keys are absent.
  - **Usage**

```bash
bash skills/codex-bridge/scripts/gask.sh --tier digest "prompt"
```

    - `--file PATH` attaches context.
    - `oask.sh` refuses non-`:free` models through its spend guard.
  - **Authorization**
    - D7 denies confidential input to an optional provider until `.workerbees/authorization.json` authorizes that workspace.
    - Non-confidential extract and summarize work is allowed.
    - Zero Data Retention (ZDR) is an OpenRouter account privacy setting at openrouter.ai/settings/privacy, not a repo setting. With it on, many `:free` endpoints refuse requests with a 404 ZDR violation. Turning it off lets those free providers train on your inputs (#19). The repo does not change it.

## Asking for work

Moved from the README for release 0.3.0.

- Rungs
  - **Definition**
    - A rung is a cost and capability class: Executive, Orchestrator, Workhorse, Grunt. It is not a job title. The chain of command decides who is Lead and who is Worker.
  - **Pairs**
    - Each rung names one Claude model and one Codex model ([governance/ROUTING-RANKING.md](governance/ROUTING-RANKING.md)): Executive fable/astra, Orchestrator opus/sol, Workhorse sonnet/terra, Grunt haiku/luna. Gemini, Mistral and OpenRouter free tiers enter only at Grunt. The operator usually names the top two; the rest derive.
- Kickoff
  - **Form**
    - `<task>. <models>.`, for example "Fix the parser. opus, haiku."
  - **Chain**
    - With two or more models named, the higher rung manages and the lower rung reports to it. At the same rung, the CoS asks one question to name the Lead.
  - **Defaults**
    - Effort medium, gates derived from the task, home repo from the consumer's `AGENTS.md`. Each extra word (effort, budget mode, review vendor) overrides exactly one default.
- Delegation limits
  - Executive and Orchestrator delegate to any lower rung.
  - Workhorse delegates only to Grunt, and only with a written allowlist.
  - Grunt never delegates.
  - Depth stops at 3 levels below the CoS.
  - The CoS answers lookups of 3 tool calls or fewer itself. Every repository edit goes through a delegate, including a one-line edit.

### Reporting chain (0.3.0)

Every dispatch prompt carries a line of the form `REPORTING CHAIN: <delegate> reports to <supervisor>; <supervisor> reports to <executive>; <executive> reports to the operator`. Precedence: explicit slot (`DELEGATE`, `SUPERVISOR`, `EXECUTIVE`), then the setting, then the ladder default. Set the default with `agents-inc models chain supervisor=opus executive=fable`; it writes key `chain` in `~/.config/agents-inc/settings.json`. `agents-inc models chain` with no value lists the setting, and `--clear` removes it. `check_dispatch_prompt.py` rejects a chain whose seat ranks above the seat it reports to. Slot details: [../skills/workerbee/slots.md](../skills/workerbee/slots.md).

### Prompt contract

The delegation prompt contract is a binding list of 14 elements in [../skills/workerbee/SKILL.md](../skills/workerbee/SKILL.md) Step 11. Five come up often:

- **Success gate and failure gate**, stated separately. A delegate's own PASS is never the final word.
- **Effort**: `low|medium|high|xhigh|max` (Claude) or the same plus `ultra` (Codex). Medium is the default.
- **Scope boilerplate**: repo-scoped writes only, no credential or cross-repo writes. Only the CoS commits and pushes.
- **CONSTRAINTS and OUT OF SCOPE**: what the delegate must not do and what it must leave alone.
- **Evidence tags** on every factual claim.

- Scope and report
  - **Snapshot**
    - `skills/workerbee/scripts/pre_dispatch_snapshot.py` hashes every dirty and untracked file before dispatch and verifies afterwards that nothing outside the allowed paths changed (D45).
  - **Report shape**
    - Narrative at most 40 lines. A mandatory `OUT OF SCOPE / INCOMPLETE:` section is never capped. Fenced evidence does not count.
- Run spec
  - **When**
    - A big lift: 2 or more delegates, or a run that edits canon.
  - **Where**
    - `specs/consumers/<repo>/runs/` in the home repo. It records the ask, resolved chain, gates, snapshot path and outcome.
  - **Home repo lookup**
    - `agents-inc dispatch` checks `--home-repo`, then `AGENTS_INC_HOME_REPO`, then a line `agents-inc home repo: <path>` in the working directory's `AGENTS.md`. For this operator the home repo is DomI.
- Pattern and anti-pattern
  - **Pattern**
    - Grill first, name models second, dispatch third. The CoS dispatches only the Lead with the full mandate and roster. The Lead runs its Workers and reports up once, when the mandate ends.
  - **Anti-pattern**
    - Dispatching on a vague request ("fix the export bug") with no grilling. The gates then rest on an unsharpened request, and a delegate can pass its own gate while missing the intent.

### `agents-inc dispatch`

```bash
agents-inc dispatch --slots slots.json --model sonnet --dry-run
```

- Jobs
  - Renders the prompt and lints it, snapshots the tree, launches the delegate, verifies the report and the snapshot, and prints one status line (D47).
- Launch paths
  - Claude models launch through `claude -p`. Codex models launch through the Codex runner. Free providers stay on `agent.sh`. No API-key path exists.
- Ledger (0.3.0)
  - Each launched dispatch writes one `dispatched` ledger node whose id is the run id. Record the verified return with `agents-inc ledger append --run-id <run> --verdict pass|fail`; `agents-inc ledger pending` lists nodes still marked dispatched.
- Flags
  - `--effort`, `--cwd`, `--tier grunt`, `--run-dir`, `--resume`, `--message`, `--home-repo`.
  - Without `--run-dir`, runs go to `<cwd>/.scratch/agents-inc-runs` when git ignores `.scratch`, else to the session scratchpad or TMPDIR. All other output, including `run.json`, stays in the run directory.
  - `--resume <run> --message <text>` gives a finished Claude or Codex delegate one more turn in its own session. A broker Lead does the same with the `resume` tool, and a running broker Worker can ask its Lead a question through `ask_lead` (D54).
- Codex sandbox
  - Under `agents-inc run`, astra, sol and terra get a sandboxed Codex shell that cannot read the home directory, write outside the repository (unless `--write`), or reach the network. luna gets it only with `--tools` (D49.1). Free providers never get one. `--no-tools` turns it off for any run.
- Broker
  - A Codex Lead can request Workers without holding provider credentials. The CoS runs `agents-inc dispatch --serve <run-dir>`; the Lead drops JSON requests into `inbox/`, waits with `agents-inc dispatch --wait <run-dir> <request-id>`, and reads back each result and report (D51).
  - `agents-inc run --lead <run-dir>` starts an MCP server for the Lead, with no write access to the run directory and an isolated CODEX_HOME. The file inbox remains the fallback.

## Speckit pipeline and grilling

- Binding
  - [../skills/speckit-pipeline/scripts/resolve_rung.py](../skills/speckit-pipeline/scripts/resolve_rung.py) resolves each phase's rung live against `governance/ROUTING-RANKING.md` and fails closed on an unknown rung.
  - [../skills/speckit-pipeline/scripts/ledger_bridge.py](../skills/speckit-pipeline/scripts/ledger_bridge.py) records every dispatch and return in the append-only ledger. Phases still run through the `Agent` tool.
- Authority
  - The Lead decides gates, accepts or rejects results, resolves conflicts and handles irreversible acts. A Worker executes per gate, reports evidence and never accepts its own work.
  - Phases marked unattended may run without a live operator. Lead gates stay required for authority, ambiguity, risk and acceptance.
- Grilling
  - An attended session: one question at a time, recommended answer first. Output updates `CONTEXT.md`, records a ruling in `DECISIONS.md`, or becomes delegation context. It is not a packaged execution step.

| phase | task | ledger | mode |
|---|---|---|---|
| 1 Specification | requirements, ambiguity, verified gates | task + resolved rung | unattended only after Lead scope gate |
| 2 Plan | subtasks, rungs, risk gates, dispatch matrix | plan, rung, authority per subtask | unattended when scope and risk gates are set |
| 3 Implementation | execute through the Agent tool | dispatch, return, worker metadata | Worker executes; Lead decides exceptions |
| 4 Review | verifier + cross-vendor reviewer | verification + reviewer consensus | unattended checks; Lead owns acceptance |
| 5 Closure | integrate verified outputs | closure + PR/commit link | unattended after acceptance gate |

## Governed pool

- Routing and policy
  - Four rungs; Gemini, Mistral and OpenRouter only at Grunt and only for `extract` and `summarize`. [../workerbees/router.py](../workerbees/router.py) enforces it from [../workerbees/routing.json](../workerbees/routing.json) before dispatch.
- Roles
  - The CEO is the operator; the CoS is the session the operator talks to. The Lead is the top-ranked model the operator names for a run and reports to the CoS once, at the end. A Worker is any agent that reports to a Lead.
- Escalation
  - A costlier rung needs a recorded reason: repeated failed checks or a provider quota pause. Worker confidence is not a reason.
- Separations (by gate, not by title)
  - An author never grades its own work.
  - The reviewer is a different vendor for canon edits and irreversible acts; same vendor is allowed for routine code.
  - Only the CoS commits and pushes.
  - A Worker sees only its own slice.
- Verification order
  1. **Verifier** ([../workerbees/verifier.py](../workerbees/verifier.py)): deterministic, no model call; quote accuracy, file existence, hash match, arithmetic. About 100–500 ms, $0. FAIL stops and returns to a human.
  2. **Reviewer** ([../workerbees/reviewer.py](../workerbees/reviewer.py)): semantic review by a different vendor. About 2–20 s. Returns PASS, FAIL or `same_vendor`; `same_vendor` makes no call and means a person must review.
  3. **Ledger** ([../workerbees/ledger.py](../workerbees/ledger.py)): append-only dual write, `~/.workerbees/ledger.jsonl` and `~/.workerbees/ledger.db`. About 10–50 ms per node.
  - Decision: ACCEPTED when all gates pass, otherwise NEEDS_REVIEW ([../workerbees/pipeline.py](../workerbees/pipeline.py)).
  - Illustrative 500-word summary: Worker haiku 2 s + $0.01, verifier 0.2 s, reviewer terra 8 s + $0.04, ledger 0.05 s; about 10 s + $0.05 in total.
- Schema
  - The config schema still requires a Claude and a Codex model name at every tier. Making either subscription optional at schema level is a goal, not current behavior ([../workerbees/config_schema.py](../workerbees/config_schema.py), [../workerbees/keys.py](../workerbees/keys.py)).

## Models: pins, drift and sync

- Pins (D52)
  - Each Codex alias is pinned to one versioned slug in `agents_inc/routing.json`. The runtime and the `@alias` router both read it. A pin never moves on its own.
  - `agents-inc models` prints one line per alias: pin, newest slug of the same family, `DRIFT` or `ok`. It reads `$CODEX_HOME/models_cache.json` or `~/.codex/models_cache.json`, never the network. Only listed, API-supported slugs count; the highest version wins.
  - `agents-inc models bump <alias> [slug]` moves one pin, rewrites `routing.json`, adds a `models.json` entry, and records a manual pin so sync skips the alias; `--unpin` releases it. It refuses with exit 2 when the slug is not in the catalog or is already pinned, and never runs git. Run it from a checkout.
- Sync (0.3.0, #57)
  - `python3 -m agents_inc.model_sync` promotes the newest Codex slug per persona into `routing.json` and `models.json`, never downgrades, and skips pinned aliases. `--apply` writes; without it the run only reports. `--openrouter` also refreshes the OpenRouter catalog.
  - Mode lives in `~/.config/agents-inc/settings.json` as `model_updates`: `approve` (default) or `auto`. `--scheduled` applies under `auto` and otherwise parks the update in `~/.config/agents-inc/pending-model-update.json`; `--approve` applies it. `--set-mode` and `--get-mode` change and read the mode.
  - Claude aliases are bare (`opus`, `sonnet`, `haiku`), so new Claude releases arrive through Claude Code itself.
- Doctor
  - `agents-inc doctor` prints the status on line 1 and one `WARNING:` line per warning. Warnings never change the status. `MODEL_DRIFT <alias>: pinned <slug>, newest <slug>` means the catalog lists a newer slug. `INSTALL_STALE` means the installed release differs from the checkout it was installed from; run `agents-inc repair --source <checkout>`. After an install from a git checkout whose bundle paths were clean, only HEAD moving to a commit whose bundle paths differ counts (a commit, checkout, reset or branch switch); uncommitted and untracked files do not. After an install with uncommitted bundle changes, any further edit counts. When git cannot run, the check reports not stale. `WB_CLI_TEMP_PATH` means the recorded `codex` path is temporary or a shim.
- Roster
  - The installer creates an empty `~/.config/agents-inc/roster.json`. Model aliases there or in `AGENTS_INC_MODEL_MAP` (JSON object or file path) override the built-in slugs.
- DelegateAgent MCP server
  - `skills/codex-bridge/mcp/codex_agent_mcp.py` exposes a `DelegateAgent` tool that forwards a prompt to Codex. All four seats (`luna`, `terra`, `sol`, `astra`) are exposed by default, with slugs from `routing.json`. The tool takes `effort` (low to xhigh; high and xhigh get longer time limits) and `conversation_id` to resume a thread. An empty or failed Codex run is an error, never a silent success. Roster, `AGENTS_INC_MODEL_MAP` or `CODEXAGENT_MODEL_MAP` still override a slug or add an alias.
  - The server ships with the agents-inc mod, so `agents-inc install` registers it; no separate step. `skills/codex-bridge/mcp/install.sh` is deprecated and only prints how to remove an old user-scope entry. Offline check: `bash skills/codex-bridge/mcp/tests/smoke_mcp.sh --offline`.

## Status detail

- Built and tested
  - The four-rung router and optional-provider limits; deterministic citation checks and cross-vendor review; the JSONL and SQLite ledger; a local SHA-256 content-addressed artifact store; the governed gateway (envelope, policy, registry, budget checks); the live [agent.sh](../skills/codex-bridge/scripts/agent.sh) / [agent_runner.py](../skills/codex-bridge/scripts/agent_runner.py) path.
  - Suite: `python3 -m unittest discover -s tests -p 'test_*.py'`, plus the workerbee skill tests under `skills/workerbee/tests`.
- Free-model counts
  - `PYTHONPATH=. python3 -m agents_inc.free_health rate-limits` lists calls and 429 responses per model, counted from 2026-09-29 ([BENCH.md](BENCH.md)).
- Governance flag
  - `WORKERBEES_GOVERNANCE` defaults to `off` ([../workerbees/gateway.py](../workerbees/gateway.py)).
- Legacy free-tier scripts
  - `gask.sh`, `mask.sh` and `oask.sh` work when governance is off, are refused in governed lanes, and are planned to fold into the governed dispatcher. Each reports to `agents_inc.free_health`. `oask.sh` saves every reply to one file, so never run OpenRouter calls in parallel.
- Artifacts
  - Bindle Backend A (local store) is built; `WORKERBEES_ARTIFACTS` defaults to `local`. Backend B stays deferred until an idempotent `finish_run` event and a validated invoice mapping exist.
- Open limits
  - `free_health` does not track Ollama yet; Ollama usage goes to `~/.codex-bridge/usage.jsonl`.
  - Delegates always receive the full prompt inline. D47 retired the reference-mode pilot of D45.
- Workflow today vs planned
  - Today: submit with `agent.sh submit --backend codex --wait "<prompt>"`, inspect by hand or run the reviewer, optionally record the decision. `agents-inc dispatch` already automates scope and report checks; cross-vendor review and ledger acceptance stay separate steps.
  - Planned (beta, not built): one-line submit, automatic cheapest-eligible selection, automatic verifier and reviewer, acceptance recorded in the ledger. Tracked in [PLAN-MVP.md](PLAN-MVP.md).
- Open issues at 0.3.0
  - [#7](https://github.com/domattioli/agents-inc/issues/7) CLI-agnostic dispatch so Codex can drive the workflow; [#8](https://github.com/domattioli/agents-inc/issues/8) astra `--approve-for-me` classifier blocks; [#6](https://github.com/domattioli/agents-inc/issues/6) stale `BASE` path in `up.sh`; [#4](https://github.com/domattioli/agents-inc/issues/4) prompt style-compression template; [#3](https://github.com/domattioli/agents-inc/issues/3) speckit mandate for Lead-run work.

## Where it fits

`agents-inc` is an integration and governance layer above provider tools. It does not replace their CLIs or instruction formats. It serves developers who use more than one provider, want to control incremental spend, and need delegated work checked before acceptance.

| provider tool | used | changed | notes |
|---|---|---|---|
| Claude Skills | yes | no | `skills/workerbee`, `skills/codex-bridge` |
| Claude subagents / Agent tool | no | — | single-vendor; cannot enforce cross-vendor review alone |
| Claude Code hooks | yes | added | SessionStart, PreToolUse and PostToolUse on Agent spawns, UserPromptSubmit for `@alias` ([../agents_inc/install/host_wiring.py](../agents_inc/install/host_wiring.py)) |
| MCP | D51 Lead transport only | built | [../agents_inc/install/mcp_broker.py](../agents_inc/install/mcp_broker.py) fronts the dispatch broker for a Codex Lead |
| OpenAI Codex CLI | yes | wrapped | `bridge.py` persistent HTTP thread; `agent.sh` / `agent_runner.py` governed job queue |
| OpenAI Assistants / Agent SDK | no | — | uses the Codex CLI and this dispatcher |

✅ built in. ❌ not built in.

| tool | several vendors | no API billing ² | routes by rule | other-vendor review ³ | scripted checks ³ | decision ledger | `@model` question | parallel worktrees | workflow SDK |
|---|---|---|---|---|---|---|---|---|---|
| **agents-inc** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| [CrewAI](https://docs.crewai.com) | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| [AutoGen](https://github.com/microsoft/autogen) / Microsoft Agent Framework ⁴ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| [firstmate](https://github.com/kunchenguid/firstmate) ⁵ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| [aider](https://aider.chat) | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Claude model-router hooks ¹ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Claude Code `/advisor` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| RouteLLM, Martian, Not Diamond | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

- Columns: several vendors = one setup uses models from more than one company; no API billing = runs on CLI subscriptions, so extra work costs $0; routes by rule = written policy picks the model; other-vendor review = a different company's model must approve; scripted checks = tests or commands must pass; decision ledger = append-only record of who did and approved what; `@model` question = ask one named model from inside Claude Code without the session model answering; parallel worktrees = many agents, each in its own worktree; workflow SDK = a Python library for multi-agent programs.
- Notes
  1. [claude-model-router-hook](https://github.com/tzachbon/claude-model-router-hook), [auto-model-router](https://github.com/IuriiTurok/auto-model-router), [model-routing](https://github.com/abroberts14/model-routing), [claude-router](https://github.com/bmersereau/claude-router); details in [at-route/AT-ROUTE-PRIOR-ART.md](at-route/AT-ROUTE-PRIOR-ART.md).
  2. CrewAI, AutoGen, aider and the API routers call provider APIs with your keys; they can also run free local models.
  3. In `agents-inc` these run on the governed path, off by default.
  4. AutoGen is in maintenance mode; Microsoft names Microsoft Agent Framework as its successor.
  5. firstmate works at a different layer (where agents run and how they are watched); evaluation open in [#31](https://github.com/domattioli/agents-inc/issues/31).
  6. [Bindle](https://github.com/deislabs/bindle) is a sibling: the ledger owns job identity and status; Bindle stores artifact bytes.
  7. Continue.dev also uses `@`, but its `@` adds a context source, not a model.
  - LangGraph and other agent frameworks are not compared yet.

## HTTP bridge

`bridge.py` exposes the local `codex` CLI over authenticated HTTP for a second device. It is peripheral to the MVP and keeps one serialized Codex thread across requests.

```bash
export CODEX_BRIDGE_TOKEN=$(openssl rand -hex 32)
python3 bridge.py --port 8787
```

- Defaults
  - `--workdir DIR` sets the Codex working directory (default: current directory; need not be a git repo, the bridge passes `--skip-git-repo-check`). Bind `127.0.0.1`, timeout 60 s, sandbox `workspace-write`.
- Session
  - Each prompt reuses the current `thread_id`. Send `"reset": true` with a prompt or call `POST /reset` to start a new thread.
- Endpoints
  - `GET /health`: no auth, returns `{"status":"ok"}`.
  - `GET /session`: current thread and sandbox; a null `thread_id` means the next prompt starts a new thread.
  - `POST /reset`: clears the thread.
  - `POST /prompt`: body `prompt` (required), `model` (optional), `reset` (optional boolean). Returns `response`, `thread_id`, `usage` and, where applicable, session-restart metadata.
  - Every endpoint except `/health` needs header `X-Auth-Token: $CODEX_BRIDGE_TOKEN`.

```bash
curl -X POST http://127.0.0.1:8787/prompt \
  -H "X-Auth-Token: $CODEX_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"explain currying in Haskell","model":"gpt-5-codex"}'
```

| status | meaning |
|---|---|
| 200 | success |
| 400 | invalid request body or fields |
| 401 | missing or wrong `X-Auth-Token` |
| 404 | unknown endpoint |
| 413 | body over 1 MiB |
| 429 | Codex reported a rate or quota limit |
| 500 | Codex CLI unavailable or unhandled bridge error |
| 502 | Codex exited unsuccessfully; a failed resume is retried once as a fresh thread unless rate-limited |
| 504 | Codex exceeded the timeout |

- Exposure
  - A private network or authenticated tunnel (Tailscale Serve, cloudflared, ngrok) can carry the bridge; their setup and security are outside this repository.
- Security
  - The bearer token is the only gate. A successful request directs a Codex process in the configured workdir and sandbox. Protect the token, rotate it on exposure, and keep the `127.0.0.1` bind unless an authenticated network layer is in place.

## Next docs

- `EXTENDING.md` covers extensions.
- `START-HERE.md` serves new humans.
- `../skills/workerbee/SKILL.md` contains the supervision discipline.
- `../skills/codex-bridge/reference/routing-policy.md` contains routing.
- `../skills/codex-bridge/reference/budget-mode.md` contains budget mode.
