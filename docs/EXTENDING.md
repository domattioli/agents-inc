# EXTENDING

- Reader
  - **Audience:** Adapting the system to a new vendor, task, or domain.
  - **Prerequisite:** Read `HOW-IT-WORKS.md` first.

## Rule zero

- Put mechanism changes in `skills/codex-bridge/`.
- Put judgment changes in `skills/workerbee/SKILL.md`.
- A routing table must not contain trust opinions, and a discipline document must not contain a retry loop.

## Add a model to an existing vendor

This is the lowest-code change because it needs no new code.

- Verify the model on the account instead of trusting a table.

```bash
grep -E '^model' ~/.codex/config.toml
python3 -c "
import json;d=json.load(open('$HOME/.codex/models_cache.json'))
for m in d['models']:
    print(m.get('slug') or m.get('id'),'|',m.get('display_name'),
          '| effort:',[e['effort'] for e in m.get('supported_reasoning_levels',[])])
"
```

- Add the nickname, vendor, slug, exact dispatch command, tier, and use case to `skills/workerbee/SKILL.md` Step 1a.
- Add a price to `skills/codex-bridge/reference/prices.json` only when established.
  - Record free as `0.0`.
  - Leave plan-based or unknown prices absent.
- Add the model to `reference/routing-policy.md` when it belongs in a chain.
- `astra`, `sol`, `terra`, and `luna` are account-specific ChatGPT codenames, not public names or Claude tiers.
- Re-run step 1 on another machine before porting a nickname.
- A newer slug of an existing Codex persona needs no hand edit (0.3.0, #57).
  - `python3 -m agents_inc.model_sync` reports the newest slug per persona; `--apply` writes it to `agents_inc/routing.json` and `agents_inc/models.json`.
  - The `model_updates` setting picks `approve` (default) or `auto`; `--scheduled` honours it and `--approve` applies a parked update.
  - `agents-inc models bump <alias> <slug>` pins an alias so sync skips it; `--unpin` releases it.
  - Claude aliases are bare (`opus`, `sonnet`, `haiku`), so a new Claude model needs no entry here.

## Add a whole vendor

1. Write a wrapper in `skills/codex-bridge/scripts/`, using `gask.sh` as the template. Read the key from a file or `.env`, never an argument, and never echo it. Map `--tier` from a friendly name to an actual slug. Exit non-zero on API errors and write the verbatim error text to stderr. Log token counts through `usage_db.py`.
2. Teach `route.sh` the backend name.
3. Teach `agent.sh` to dispatch it.
4. Add a roster row in `workerbee` Step 1a.
5. Add prices to `prices.json` under the honesty rule.
6. Add the limit, reset time, and exact failure string to `reference/budget-mode.md`. The quota record distinguishes a retryable failure from quota burning.

- **Failure example:** `oask.sh` read the wrong key path, passed a file-exists check with placeholder content, and sent an empty bearer token that produced HTTP 401 without a clear key error.
- **Required check:** Test with the key deliberately absent and deliberately wrong.

## Add a task class

1. Add it to `reference/routing-policy.md`.
2. Give it an ORDERED chain because every backend has a ceiling.
3. Explain the order in one clause. “Why this order” is a required column.
4. For money or irreversible work, use numbered gates and `--sandbox read-only`, as required by `HOW-IT-WORKS.md`.

## Adapt to a new domain

- **Invariant:** The discipline stays domain-blind and defines process rather than subject matter.
- **Task classes:** Replace classes such as “repo survey” and “stack trace analysis” with domain-specific classes.
- **Verification:** Define what makes the result checkable before delegating. Code has tests; other domains need an equivalent.
- **Hard stops:** Write down what must never be delegated.
- **Secrets:** Name the actual secret paths in every dispatch.
- **Unchanged rules:** Keep tiering, the self-graded-gate ban, unknown≠zero, sandbox constraints, and fail-closed irreversible actions.

### Worked example: a law practice

Not an endorsement. A shape.

| task class | delegate? | verification |
|---|---|---|
| summarize a long deposition | yes, digest tier, 1M context | spot-check quotes against page numbers in source |
| extract every date + party from discovery | yes, Grunt rung, high volume | re-run on a hand-labeled sample, count misses |
| find contradictions between two statements | yes, but as a CANDIDATE list only | read each candidate yourself |
| draft a client letter | draft only, never send | you are the signatory. Delegate output is a first pass |
| anything filed, served, or sent to a client | **NO. HARD STOP.** | n/a |
| anything privileged leaving the machine | **NO. HARD STOP.** | n/a |

- **Cloud transmission:** A cloud model call sends data away from the machine, and privilege obligations still apply to summaries.
- **Dispatch rule:** Decide what may leave the machine, write it down, and put forbidden paths in every dispatch prompt.
- **Verification:** Use a hand-labeled sample scored the same way every time because law has no test suite.

## Local provider: ollama (pilot)

- Status
  - **Off by default.** It runs only when `WORKERBEES_LOCAL=1` is set and the caller asks for it by name (`worker_provider="ollama"` or `local_only=True`).
  - **Scope:** Grunt rung, `extract` and `summarize` only. Never review, draft, or adjudication work.
- Setup
  - Install and start the server: `brew install ollama`, then `brew services start ollama` (macOS). On Linux, use the distribution package or the official installer.
  - Pull the default model by hand: `ollama pull qwen2.5-coder:3b`. The larger allowlisted models (`qwen2.5-coder:7b`, `qwen3:8b`) are optional and suit hosts with more RAM. The pipeline never pulls, starts, or restarts anything.
  - Set `OLLAMA_MAX_LOADED_MODELS=1` in the *server's* environment. The client cannot set it.
- Confidential work
  - Add `"local_only": true` to `<workspace>/.workerbees/authorization.json`.
  - `optional_providers` does not authorize ollama for confidential input, and `local_only` does not authorize any remote provider.
  - A `local_only=True` brief never falls back to a remote provider and skips the remote reviewer. If ollama is unavailable, the brief is blocked with `WB_LOCAL_UNAVAILABLE`.
  - The catalog field `egress: "none"` is metadata only; no code reads it to grant access. `train_on_input` is `null` (unknown) until someone records the provider's terms.
- Memory guards
  - All limits are percentages of total RAM, so the same settings work on any machine. They live in `agents_inc/routing.json` under `local`.
  - **Admission:** all three must hold before the model loads.
    - Free RAM ≥ `min_free_pct` (35%).
    - Free bytes ≥ model size × `model_headroom` (1.5).
    - Projected free RAM after load ≥ `abort_free_pct` + `projection_margin_pct` (25% + 5%). Projected free = free % − (model size × 1.5 ÷ total RAM). A model too large for the host is rejected upfront instead of loading and then aborting.
  - **Measured on a 16 GiB Apple M4 (2026-09-22):** loading a model cut free RAM by 1.3–1.4 × its file size.
    - `qwen2.5-coder:7b`: free RAM fell from 60% to 22% and swap grew 2.5% of RAM, so every job aborted. The new projected check rejects it on this host.
    - `qwen2.5-coder:3b`: free RAM low point 43%, no swap growth, 4 s per extract job. This is the default.
  - **Watchdog (every 2 s):** abort, unload, and trip the breaker when free RAM falls below `abort_free_pct` (25%), when swap use grows by more than `max_swap_growth_pct` (2%) of total RAM, or when the 90 s deadline passes.
  - **Per request:** `keep_alive: 0`, context 4096 tokens, input ≤ 3072 tokens (estimated as bytes ÷ 3; larger inputs are rejected, not truncated), output ≤ 512 tokens.
  - **One job at a time:** a second request gets `WB_LOCAL_BUSY` instead of waiting.
  - Memory telemetry comes from `sysctl` on macOS and `/proc/meminfo` on Linux. On other systems telemetry is unavailable, so every job is rejected.
- Recovery
  - After an abort, a deadline, an error, or an unload that cannot be confirmed, the adapter writes a breaker file and refuses further local jobs.
  - Check memory with `ollama ps`, then clear the breaker with `python3 -m agents_inc.adapters.ollama --reset`.
  - The breaker lives in `$AGENTS_INC_LOCAL_STATE`, or `~/.cache/agents-inc/local` by default.
- Origin
  - Agreed in a fable–astra consensus debate on 2026-09-22 (see `skills/consensus-debate`). The operator changed the memory limits from absolute GiB to percentages.

## Extensibility smells

| smell | why it costs |
|---|---|
| roster row with no dispatch command | next session reverse-engineers the vendor lookup by hand |
| price written `0.0` because unknown | confident wrong savings figures outlive the session |
| backend added, no failure-signal row | cannot distinguish retry-me from stop-burning-quota |
| task class with one backend, no chain | that backend hits its ceiling and the class dies |
| discipline copied into a second file | two sources of truth drift, and the older one eventually wins an argument |
| verifier the delegate can edit | grades intent, not result |

## Before you claim it works

### Verification checklist

- **Wrapper failure**
  - Run it with the key absent. Expect a clear error and non-zero exit.
  - Run it with the key wrong. Expect a clear error, non-zero exit, and no silent empty result.
- **Real call:** Run a one-shot. Output and token counts must land in `usage.db`.
- **Routing:** `route.sh pick <class>` must return the backend.
- **Cooldown:** Force cooldown and confirm the chain falls through to the next backend.
- **Reporting:** `usage_report.sh` must show calls with a price or an explicit unknown.
- **Count:** Six checks are required.
- **History:** Skipping the two failure checks is how `oask.sh` shipped broken.
