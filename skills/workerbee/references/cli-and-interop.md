# workerbee: CLI and cross-skill interaction

Moved verbatim from `skills/workerbee/SKILL.md` (2026-11-16, token-efficiency order). Rules here bind as if in SKILL.md.

## CLI

None. This is a discipline skill with no scripts of its own — it governs
how you use someone else's. Dispatch goes through `codex-bridge`:

```
skills/codex-bridge/scripts/agent.sh submit --backend <b> --wait "<prompt>"  # DEFAULT for gemini/mistral/openrouter
skills/codex-bridge/scripts/agent.sh result <id>
skills/codex-bridge/scripts/agent.sh submit --class review "<prompt>"   # route.sh picks
# For codex/luna, use DelegateAgent MCP tool instead (--wait is broken on codex backend)
```

Every `agents-inc dispatch` run that reaches launch leaves a `dispatched` node
in the host ledger; its node id is the run id the status line prints. List open
nodes and close one with the verdict you reached, not the delegate's:

```
agents-inc ledger pending
agents-inc ledger append --run-id <id> --verdict pass|fail
```

Prefer `agent.sh` over calling a provider wrapper directly — it gives a job
id, saved stdout/stderr, transient-failure retries, and a provider-neutral
`result.json` you can attach to a report.

## Cross-skill interaction

| Skill | Relationship |
|---|---|
| `codex-bridge` | The mechanism this skill supervises. That skill owns transport, routing (`route.sh`), per-provider timeouts, job state and retries. This skill owns tier choice, trust, and honesty. Do not reimplement its dispatch here |
| `caveman` | Agent-facing dispatch prompts are written at `ultra` level — the reader is a model |
| `nested-notes` | Structures the supervisor's report back to the operator |
| `accelerate` | Optional. Renders the Chief of Staff DECIDE / HANDLED / UNDERSTAND instrument (Step 4) |
| `act-autonomously` | Sibling discipline skill for unattended routines; overlapping subagent-budget concerns |
