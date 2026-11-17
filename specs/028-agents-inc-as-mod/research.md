<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-24 skill=speckit-plan repo=agents_Inc session=20261025T002934Z-opus-7f9da0 -->
# Research: agents-inc becomes a Claude Code mod (luna first)

No NEEDS CLARIFICATION remained after Q1 to Q3. These are the design decisions the plan rests on. Tags: [verified] read in code or types this run; [inferred] follows from read code; [assumed] needs a test or probe in implement.

## R1 Where the step logic lives

- Decision: a second module `mods/agents-inc/hooks/luna.ts` beside `relay.ts`, listed in `hooks/hooks.json`.
- Rationale: FR-019 ships the type in the existing mod; `hooks.json` already lists modules (`mods/agents-inc/hooks/hooks.json:2`) [verified]. The type name follows the mod name: `relay` registers as `agents-inc:relay` (spec 027 FR-017) [inferred].
- Alternatives: fold into `relay.ts` (mixes two features in one file); keep `mods/luna-brain/` and install it (FR-019 retires it).

## R2 How the mod learns readiness, slug and the switch

- Decision: one `agents-inc luna status --json` call at `session.start`.
- Rationale: the slug must come from the routing pin (FR-003; `agents_inc/routing.json:5` maps grunt codex to `gpt-6-luna`) [verified]; Codex readiness reads the install receipt (`agents_inc/install/doctor.py:100-101`) [verified]; the switch sits in the agents-inc settings file that `write_agent_gate` already writes (`agents_inc/install/hook.py:134-150`) [verified]. The mod reaches all three through one process call and parses no Python state.
- Alternatives: read `routing.json` with `$.fs.read` from the bundle (the mod would need the bundle path and the model-map logic); environment variable switch (not persistent across sessions, so not "one documented switch").

## R3 Fix text when the stripped catalog is missing

- Decision: the error names `models_cache.json` under the Codex home and says to run one plain Codex command so Codex writes its model cache, then retry.
- Rationale: `host_tools_catalog` needs the slug's entry in `models_cache.json` (`agents_inc/install/runtime.py:352-360`) [verified]. Which Codex command writes the cache without a model call is not known [assumed]; implement probes it (T005). If only a model call writes it, the fix text names `codex exec` once and says it uses one Codex request.
- Alternatives: ship a frozen catalog entry for the slug in the bundle (goes stale when Codex changes the entry's fields); fall back to the full catalog (forbidden, FR-011).
- T005 probe (2026-10-25, Codex 0.159.2, fresh Docker home with auth.json only): `codex debug models` exits 0, writes `~/.codex/models_cache.json` (399 KB, `gpt-6-luna` present) and creates no session rollout, so it makes no model call [verified]. `CATALOG_WARM_COMMAND` and the stress script's `WARM_CMD` name it.

## R4 Identifying a luna agent without the spawn record

- Decision: spawn set, then `$.agent.list()`, then a marker line in the agent's system prompt; fail the step when identity cannot be read.
- Rationale: the spike passes an unknown agent's step to the placeholder (`mods/luna-brain/hooks/luna.ts:268-272`) [verified], which FR-015 forbids. `$.agent.list` exists (`index.d.ts:7154`) [verified]. Whether `$.prompt.compose` can be asked for a given agent's prompt inside `turn.step` is [assumed]; T024 starts with a probe case in the plugin test harness, and if it cannot, check (3) is dropped and the rule falls back to "fail when `agent.list` throws".
- Alternatives: pass unknown steps through (FR-015 forbids); fail every unknown step (breaks every other subagent in the session).

## R5 Keeping Codex MCP servers out (FR-013)

- Decision: host-tools runs use `lead_codex_home` (isolated `CODEX_HOME`), and the catalog is built from the real home first.
- Rationale: `lead_codex_home` links only `auth.json`, `sessions` and the readable dirs and writes a one-line `config.toml`, "so the operator's MCP servers and config never load" (`agents_inc/install/runtime.py:279-307`) [verified]. A `-c` override cannot empty a TOML table such as `mcp_servers` [inferred from operator memory note "Codex MCP tools lazy-loaded", not re-probed this run]. The isolated home has no `models_cache.json` [verified: not in the link list], and `host_tools_catalog` falls back to `os.environ["CODEX_HOME"]` when no home is passed (`runtime.py:355`) [verified], so the catalog must be built from the real home before isolation and passed into the argv explicitly. `lead_codex_home` always links from `Path.home() / ".codex"` (`runtime.py:283`) [verified]; the catalog uses the same directory so the auth source and the cache source cannot diverge. Codex authenticates through the `auth.json` symlink (`runtime.py:295`) [verified]; agents-inc never reads the credential. The child env is the caller's env plus `CODEX_HOME` (`runtime.py:565-566`) [verified]; `lead_env`'s scrub (`runtime.py:310-316`) is Lead-only. A token refresh that replaces the link keeps the home and fails the run (`runtime.py:613-617`, `:665-666`) [verified].
- Alternatives: `-c mcp_servers={}` (table override trap); a dedicated luna `CODEX_HOME` kept between runs (new state to manage and clean).

## R6 Ledger and snapshot without dispatch (FR-026)

- Decision: `agents-inc luna begin` at `agent.spawn`, `agents-inc luna end` at `turn.complete`; host ledger JSONL rows; snapshot file under the agents-inc state dir.
- Rationale: `turn.complete` fires at each agent turn end with `e.agentId` (`mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts:4598-4609`) [verified]. `agent.spawn`'s `next(e)` result carries `agentId` (`index.d.ts:422-435`) [verified]. Host-ledger rows already exist for hook and dispatch sources (`agents_inc/host_ledger.py:51-138`) [verified]; `ledger append` refuses a missing verdict (`host_ledger.py:226-228`) [verified], so the mod writes an outcome row and the parent adds the verdict.
- Alternatives: a SubagentHandback `tool.call` hook (absent on some background builds, `luna.ts:371-373`); writing JSONL from TypeScript (duplicates row shape).

## R7 Quota detection

- Decision: reuse the existing quota branch of `run_codex`; the mod maps exit 75 to quota-paused and ends the agent without the fresh-thread retry.
- Rationale: one quota pattern already serves `run_codex` and dispatch (`agents_inc/install/runtime.py:467-469`) [verified]. The branch already prints "hit a usage or rate limit; retry at" (`runtime.py:646`) and returns 75 (EX_TEMPFAIL, `runtime.py:657`) [verified this turn; the earlier "unused" note was wrong]. No runtime change; T026 and T027 pin the message and the exit code for host-tools runs.

## R8 Proving zero Claude steps (SC-003)

- Decision: plugin tests assert `next` is never called for a luna agent; the stress suite runs the parent on sonnet so any haiku usage is a placeholder leak.
- Rationale: the spike stress script runs the parent on haiku (`docker/luna_stress.sh:32`) [verified], so haiku usage there cannot be told apart from parent usage.
- T002 baseline (2026-10-25, spike commit cff7df4 in Docker, `tools` R=3): pass 3 of 3; per-run `request_user_input` 0, 2, 1; `apply_patch` attempts 0, 0, 0 (counted from the Codex rollouts). The spike script needed `codex debug models` first and a plugin dir named `luna-brain`, because Claude Code 2.1.310 names an inline plugin after its directory [verified].
