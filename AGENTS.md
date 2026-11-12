# agents-inc agent instructions

`agents-inc` pools Claude, Codex, Gemini, Mistral, and OpenRouter capacity behind governed routing. It checks delegated work with deterministic verification and cross-vendor review, then records decisions in an append-only ledger. The repository was named `agents_for_dummies` before 2026-09-07. Old names in historical documents stay unchanged.

## Repository layout

| Path | Purpose |
|---|---|
| `agents_inc/` | Routing, policy, adapters, verification, review, artifacts, ledgers, and the installer |
| `workerbees/` | Import shim: `workerbees.*` aliases the `agents_inc` modules for older callers |
| `skills/workerbee/` | Canonical supervision and delegation prompt contract |
| `skills/codex-bridge/` | Governed job runner and persistent Codex bridge scripts |
| `skills/speckit-pipeline/` | Repository-specific spec pipeline binding |
| `tools/` | Governance demo, migrations, and corpus utilities |
| `tests/` | Python `unittest` suite |
| `fixtures/` | Seeded fault and expected-result fixtures |
| `docs/governance/` | Routing, authority, and operating governance |
| `scripts/` | `agents-inc` launcher, skill installer, isolation and proof scripts, live Claude Code status line (`statusline.sh`, `statusline.d/`) |
| `docs/at-route/` | `@alias` side-question routing guide, bench, and prior art |

## Setup, test, and run

The Python code uses the standard library and has no package-install step. Use Python 3.11 or later and Bash 3.2 or later. Real dispatch also needs authenticated Claude Code and Codex CLIs. Gemini, Mistral, and OpenRouter credentials are optional.

Run the full test suite:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Run the local demo without provider keys:

```bash
PYTHONPATH=. python3 tools/governance_demo.py --fake
```

Submit a Codex job after provider setup:

```bash
skills/codex-bridge/scripts/agent.sh submit --backend codex --wait "your prompt"
```

Run the HTTP bridge:

```bash
export CODEX_BRIDGE_TOKEN=$(openssl rand -hex 32)
python3 bridge.py --port 8787
```

## Develop and stress-test

See `docs/CONTRIBUTING.md` for the docker flow.

## Project rules

- Incremental spend is capped at $0 per task. Pause and report quota exhaustion. Do not add a paid API fallback.
- Claude is the required provider; Codex is optional. Optional providers may handle only allowed Grunt work. Current optional-provider routing is limited to `extract` and `summarize` tasks.
- Confidential inputs may reach optional providers only after explicit per-workspace authorization.
- A worker never accepts its own output. Use deterministic verification, then a reviewer; the reviewer comes from a different vendor for canon edits and irreversible changes, and may share the vendor for routine code (D46). Record the result in the ledger.
- `WORKERBEES_GOVERNANCE` defaults to `off`. Do not describe the governed path as enabled by default.
- Optional provider keys go through the hidden local prompt. Never put a key in a command argument or model prompt. The non-coder key store is `~/.config/workerbees/.env` with mode `0600`; operator storage rules are in `docs/DECISIONS.md`.
- The 14-field delegation prompt contract lives in `skills/workerbee/SKILL.md` Step 11. Apply it to every dispatch that touches this repository, including dispatches from another repository.
- Third-party wording skills (`caveman`, `structured-gist`, `write-like-scientist`, `handoff-lint`) are optional user-scope installs, never vendored (D42). Installed: invoke them with a real Skill call. Absent: state one line such as `caveman NOT installed -> checked by hand`, apply the rules by hand, and continue. Never claim activation without a successful call.
- Handoff lint gate (D41, conditional per D42): before any dispatch, run `python3 skills/workerbee/scripts/check_dispatch_prompt.py <prompt>` (mandatory). Add `--with-handoff-lint` to also run the optional `handoff-lint` tool; when it is absent, check H1 to H6 by hand. Apply the same gate in the report direction (`--profile report`) before verifying a delegate's claims. The gate lints and rejects; it never rewrites text.
- Roles by rung (D78): Workhorse (sonnet, terra) is the default for anything that writes. Work that needs design or scope judgment, review, or gates belongs at Orchestrator (opus, sol). The haiku and luna grunts are read-only. Free-model coding is limited to small, narrow diffs with fixed scope.
- A failed check means a supervisor verified returned output against the dispatch gate and found it red. Two failed checks for the same task and delegate trigger escalation by one rung with the same vendor. A quota pause counts as one failed attempt. A Lead may assign work with a recorded gate reason. A delegate's own result does not count.

When `CODEX_BRIDGE_MODE=ultra`:

- Be terse and report only results, evidence, and blockers.
- Delegate only to Gemini, Mistral, or Codex. Do not fall back to an Anthropic backend.
- Verify delegated work locally before accepting it.
- If no eligible backend is available, stop and report the blocker.

## Documentation style

| Surface | Reader | Wording | Structure |
|---|---|---|---|
| `README.md`, `docs/START-HERE.md`, `docs/HOW-IT-WORKS.md`, `docs/EXTENDING.md`, `docs/DECISIONS.md`, `docs/BENCH.md`, `docs/governance/CEO-BRIEF.md` | Human | Short, readable prose | Scannable nested notes with a precise final pass |
| Agent prompts, `skills/*/SKILL.md`, dispatch specs, `docs/PLAN-MVP.md`, `docs/governance/ASSESSMENT.md`, `agents_inc/*.json` | Agent or builder | Maximum compression | Plain prose without decorative structure |

These audience rules are binding for repository documentation. Preserve template scaffolding, code blocks, and required machine-readable fields.

## Project canon

Use these sources in order:

1. `CONTEXT.md` defines terms.
2. `docs/DECISIONS.md` records binding rulings and overrides `docs/PLAN-MVP.md` on conflict.
3. `docs/governance/` defines the control plane.

The delegation model is in `docs/governance/DELEGATION-MODEL.md`. The routing table is in `docs/governance/ROUTING-RANKING.md`. Do not duplicate either one here.

## Branches

The working branch is `development`; releases use a PR from `development` to `main`. Never push directly to `main` or force-push.
