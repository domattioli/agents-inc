<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-24 skill=speckit-plan repo=agents_Inc session=20261025T002934Z-opus-7f9da0 -->
# Implementation Plan: agents-inc becomes a Claude Code mod (luna first)

**Branch**: `spike/luna-turn-step` now; implement lands on `development` (no feature branch created by this run) | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/028-agents-inc-as-mod/spec.md` (Clarifications Q1 to Q3 answered)

## Summary

The spike step logic in `mods/luna-brain/hooks/luna.ts` moves into the shipped mod as `mods/agents-inc/hooks/luna.ts` and registers the native type `agents-inc:luna`. Every step of that type is answered by `agents-inc run --host-tools --thread <file>`; the placeholder model is never called. Python gains one small module and one CLI verb, `agents-inc luna`, that the mod calls for three things the TypeScript side cannot do alone: readiness and the slug (`status`), the scope snapshot plus ledger row at spawn (`begin`), and the snapshot verify plus ledger return at hand-back (`end`). The host-tools Codex run fails closed when the stripped catalog cannot be built, runs under an isolated `CODEX_HOME` so no operator MCP server loads, names the catalog in its record line and counts Codex-side tool calls. The agent gate and persona deny exempt the exact type `agents-inc:luna` and drop the `luna-brain:` prefix. Pre-028 luna routes are untouched. Design choices: research.md R1 to R8.

## Technical Context

**Language/Version**: Python 3.11+ standard library (`agents_inc/`); TypeScript ES module for the mod (Claude Code plugin API; types in `mods/agents-inc/.claude-plugin/types/`)
**Primary Dependencies**: none new. Claude Code CLI (`claude plugin validate|test`), Codex CLI 0.159.2 as probed in the spike (`agents_inc/install/runtime.py:340`)
**Storage**: thread files under `<cwd>/.scratch/agents-inc-luna/<session>/` (git-ignored, `.gitignore:241`); snapshots under `<state>/luna-runs/<session>/<agent>/`; ledger rows in the host ledger `<state>/host-ledger/.workerbees/ledger.jsonl` (`agents_inc/host_ledger.py:23-25`, `:141-145`)
**Testing**: `python3 -m unittest discover -s tests -p 'test_*.py'`; `claude plugin validate mods/agents-inc`; `claude plugin test mods/agents-inc`; `docker/luna_stress.sh` (SC-001 to SC-006)
**Target Platform**: macOS host and the Linux dev container (`docker/Dockerfile.dev`)
**Project Type**: CLI plus Claude Code mod
**Performance Goals**: per-step time limit 300 s, kept from the spike (`luna.ts:11`); `agents-inc luna begin|end` under 2 s each on a repo the size of this one [assumed: snapshot cost is one `git status` plus hashing dirty and untracked files]
**Constraints**: $0 (P5): no Claude step for a luna agent; quota pauses, never swaps provider. No edit to a path the spec Inventory marks "keep". Old luna routes unchanged (FR-023).
**Scale/Scope**: luna only. Up to three parallel luna agents per session (the `par` scenario).

## Constitution Check

Constitution v1.8.0 is unratified, so violations report as WARN [verified `.specify/memory/constitution.md:62-64`].

- P1 repo-scoped writes: PASS. Thread files stay in the git-ignored `.scratch/` of the session cwd. Snapshot and ledger go to the agents-inc state dir, which agents-inc already writes for dispatch trust records (`agents_inc/install/dispatch.py:859-862`). luna's own writes go through harness tools under the parent's permission rules.
- P3 no self-graded gates: PASS. The mod records an outcome, not a verdict. The ledger row carries `verdict: null`; the parent records the verdict later with `agents-inc ledger append --verdict` (`agents_inc/host_ledger.py:226-228` refuses a missing verdict).
- P4 deterministic policy: PASS. The type is offered by code (`agent.offer`), the gate exemption is an exact string match, the catalog check fails closed.
- P5 $0: PASS by design (FR-015, FR-016). SC-003 measures it.
- P7 nickname discipline: WARN. P7 says the Codex codenames are not Agent-tool subagent models (`.specify/memory/constitution.md:48`). 028 keeps the Agent tool's `model` parameter free of `luna` (FR-001) but offers a subagent type whose steps luna answers. The spec already lists P7 as made stale (spec.md:220). The FR-027 decision record is the authority until the operator amends P7. Tracked in Complexity Tracking.
- P8 prompt contract: WARN. A native luna subagent gets no 14-element contract lint (FR-026, Q2). The operator answered Q2; the FR-027 entry records it.
- P9 edit hygiene: PASS. Existing functions change in place; `luna.ts` is a move plus edits.
- Re-check after design: no new violation beyond P7 and P8 above.

## Design

### D1 Native type in the shipped mod (`mods/agents-inc/hooks/luna.ts`, new; `hooks/hooks.json`)

`hooks.json` becomes `{"modules": ["relay.ts", "luna.ts"]}`. `luna.ts` starts as a copy of `mods/luna-brain/hooks/luna.ts` with these changes:

1. `session.start`: run `agents-inc luna status --json` once through `$.process.run` (D5). Register the agent `luna` (so the type is `agents-inc:luna`, spec Assumptions; the mod is named `agents-inc`, `mods/agents-inc/.claude-plugin/plugin.json`) only when `offered` is true. No `tools`, no `permissionMode` (FR-002). `model: 'haiku'` stays as the placeholder. Keep the slug from `status` (FR-003) and render it into HEADER in place of the fixed `gpt-6-luna` text (`luna.ts:46`).
2. `agent.offer` on `{ agent: 'agents-inc:luna' }`: `{ isOffered: false }` when `status` said not offered, so a session that registered before a switch-off still hides it in new listings. A failed guard keeps it hidden (`.catch(... { isOffered: false })`).
3. `AGENT_TYPES` becomes `['agents-inc:luna']`; the bare `luna` and `luna-brain:luna` entries go.
4. Thread path (FR-024): `<cwd>/.scratch/agents-inc-luna/<session id>/<agent id>[-n].thread`, session id from `$.session.id()`. The `.prompt.txt` copy (`luna.ts:389-390`) is written only when `AGENTS_INC_LUNA_DEBUG=1`.
5. Debug lines keep the spike shape with the prefix `agents-inc luna:` and add `codex_tools <json>` from the run's tool-count line (D3, FR-014).
6. Abort (FR-018): on `next.signal` abort the run stream is ended (`luna.ts:343`), no retry or push runs after it, and the agent state is not marked `used`.

### D2 Identify luna without the spawn event (FR-015, FR-017)

Order: (1) the id was recorded by `agent.spawn` for `subagentType === 'agents-inc:luna'`; (2) `$.agent.list()` lists the id with that type; (3) the agent's system prompt (from `$.prompt.compose` for that agent) carries the fixed marker line `agents-inc luna type v1` that `AGENT_PROMPT` ends with. A definite "not luna" from (2) or (3) passes the step to `next(e)`. When (2) throws and (3) cannot be read, the step fails with `agents-inc luna: cannot identify agent <id>; step not sent to the placeholder model` instead of calling `next(e)`. This trades a possible failed non-luna step on a broken build for a guarantee that a luna step never reaches haiku. Whether `turn.step`'s event exposes enough to run (3) is research R4 [assumed]. T024 starts with a probe case; if `$.prompt.compose` inside `turn.step` does not return the luna agent's own prompt, check (3) is dropped and D2 falls back to (1) and (2) with the fail-closed rule.

### D3 Host-tools Codex run (`agents_inc/install/runtime.py`)

1. FR-010, FR-011: `no_tool_args(host_tools=True, slug)` raises `HostToolsCatalogMissing` (message starts `WB_LUNA_CATALOG_MISSING:`) when `host_tools_catalog` returns `None` (today it silently keeps Codex's catalog, `runtime.py:375-376`). The message names the cause (no `models_cache.json` entry for the slug under the Codex home) and the fix from R3; once T005 records the command that writes the cache, the message and this item name it. `run_codex` turns it into exit 3 with that one stderr line, before any process starts. The stress container starts with a fresh `CODEX_HOME`, so its suite runs that command as a warm step before any scenario (D9).
2. FR-013: a host-tools run uses the isolated home `lead_codex_home(slug)` (`runtime.py:279-307`), whose docstring says the operator's MCP servers and config never load. The isolated home holds no `models_cache.json`, and `host_tools_catalog` reads the cache from `CODEX_HOME` when no home is passed (`runtime.py:355`), so the order is fixed:
   1. Resolve the real home once, before any swap: `real = Path.home() / ".codex"`, the same directory `lead_codex_home` links from (`runtime.py:283`). An operator `CODEX_HOME` that points elsewhere is not followed on host-tools runs, so the catalog source and the auth source are always the same directory; the record line names `real` so a divergence is visible.
   2. Build the catalog from it: `host_tools_catalog(slug, codex_home=real)`. `no_tool_args` takes the catalog path as an argument and no longer reads `os.environ["CODEX_HOME"]` itself; `build_codex_argv` (`runtime.py:414-416`) passes it through. A `None` result raises `HostToolsCatalogMissing` (item 1) before `lead_codex_home` runs, so a missing cache never creates a temp home.
   3. Only then call `lead_codex_home(slug)` and set the child env `CODEX_HOME` to it. The non-lead branch already does this (`runtime.py:565-566`): the child env is the caller's env plus `CODEX_HOME`. `lead_env` (`runtime.py:310-316`, `worker_env` scrub plus `CODEX_HOME`) is for Leads only and is not used here: luna runs no tool of its own, so there is nothing for a scrubbed env to protect, and Codex needs `HOME` and `PATH` as the caller has them.
   4. Authentication in the isolated home: `auth.json` there is a symlink to the real `~/.codex/auth.json` (`runtime.py:295`). agents-inc never reads or copies the credential; Codex reads it through the link. A missing real `auth.json` raises `WB_CODEX_AUTH_MISSING` (`runtime.py:284-286`), which the mod maps to `luna failed: Codex missing (WB_CODEX_AUTH_MISSING)` (D4). Thread resume keeps working because `sessions` is symlinked (`runtime.py:296`).
   5. Cleanup: `run_codex` removes the home with `shutil.rmtree`, which removes the links and never their targets (`runtime.py:616-624`). If Codex refreshed its token and replaced the `auth.json` link with a real file, the home is kept and stderr says `isolated CODEX_HOME kept: auth.json is no longer a symlink` (`runtime.py:613-617`). That leaves a temp directory (mode 0700) holding a live credential, and a run that otherwise succeeded returns 1 (`runtime.py:665-666`), so the mod reports `luna failed: run exited 1: ... isolated CODEX_HOME kept ...` for that step and its one fresh-thread retry runs in a new home. Nothing cleans the kept directory up; the operator removes it. This is the existing Lead behaviour, unchanged.
   This reuses `lead_codex_home` without editing it (spec Inventory row for `runtime.py:279-316`). Each step pays one `mkdtemp` plus cleanup.
3. FR-012: no change. Tool-free runs keep `-s read-only` (`runtime.py:416`) and `web_search="disabled"` (`runtime.py:404`); a test pins both for host-tools argv.
4. US2 scenario 1: the `agents-inc run: record` line (`runtime.py:555`) gains `"catalog": "host-tools"` with the catalog path and `"codex_home": "isolated"` for host-tools runs.
5. FR-014: `run_codex_thread` (`runtime.py:690`) counts Codex-side tool calls from the JSONL events it already parses (`thread_progress_line`) by tool name and prints one `agents-inc run: tools {"request_user_input": n, ...}` line at the end. The mod copies it into its step debug line. The stress script reads the same counts from rollouts.
6. FR-016: reuse the existing quota branch of `run_codex` (`runtime.py:636-657`, message "hit a usage or rate limit; retry at" at `:646`). That branch already returns 75 for every run (`runtime.py:657`), so no runtime change is needed: no second quota line, no new exit path, the message stays as it is. A test pins exit 75 and the message for a host-tools run. The mod maps exit 75 to quota-paused (D4).

### D4 Failure handling in the mod (FR-015, FR-016)

Each failure ends the step with text the parent sees and `stopReason: 'end_turn'`, through `SubagentHandback` when offered, else plain text. Texts: `luna failed: Codex missing (WB_CLI_NOT_FOUND)`, `luna failed: Codex missing (WB_CODEX_AUTH_MISSING)`, `luna failed: catalog missing (WB_LUNA_CATALOG_MISSING) ...`, `luna failed: timeout after 300 s`, `luna failed: unparsable reply`, `luna failed: run exited <rc>: <stderr tail>`, `luna quota-paused: <line>`. A quota pause does not retry on a fresh thread (the spike retries every failed run once, `luna.ts:392-399`); other failures keep the one fresh-thread retry the spec edge cases ask for. No path calls `next(e)` for a luna agent.

### D5 `agents-inc luna` verb (`agents_inc/install/luna_native.py`, new; `agents_inc/install/cli.py`)

- `luna status --json`: `{"offered": bool, "reason": str, "slug": str, "codex": "ready|missing|logged-out", "catalog": "ok|missing", "switch": "on|off"}`. Slug: the luna entry of the model map that `run_codex` resolves (`load_model_map()`), which follows the grunt codex pin `gpt-6-luna` in `agents_inc/routing.json:5` (FR-003). Codex ready: receipt `codex_path` executable (`doctor.py:100-101`) and `~/.codex/auth.json` present (the check `lead_codex_home` makes, `runtime.py:284-286`; no network). `offered` = switch on and Codex ready. A missing catalog does not hide the type; the step fails with the fix (FR-011), and doctor warns.
- `luna on|off` (FR-021): writes key `luna_type` in `~/.config/agents-inc/settings.json` with the same atomic writer as `write_agent_gate` (`agents_inc/install/hook.py:134-150`). Off means `status` returns `offered: false`; new sessions get no type. This is the one documented switch.
- `luna begin --session S --agent A --cwd C` and `luna end --session S --agent A --outcome O [--usage JSON]`: D6.

### D6 Ledger record and scope snapshot without the dispatch path (FR-026)

The dispatch path does both inside `agents-inc dispatch` (snapshot pin `dispatch.py:247`, trust record `dispatch.py:869-894`, host-ledger row `dispatch.py:1222`). The native path has no dispatch run, so the mod drives them through `agents-inc luna`:

1. Spawn: the `agent.spawn` hook awaits `next(e)`; when the type is `agents-inc:luna` and `agentId` is set, it runs `agents-inc luna begin` and keeps the promise per agent id. The agent may already be running at that point, so the first `turn.step` of a luna agent awaits that promise before it starts Codex; the snapshot therefore precedes luna's first tool call. A rejected `begin` is logged (item 4) and the step proceeds. `begin` loads `pre_dispatch_snapshot.py` from the installed bundle (`<current>/skills/workerbee/scripts/`, the file dispatch pins, `dispatch.py:70`) and calls its `capture` with the session cwd's repo, writing `<state>/luna-runs/<session>/<agent>/snapshot.json` (outside cwd, mode 0700 dir, like `_trust_path`, `dispatch.py:859-862`). Then it appends one host-ledger dispatch row: `id` = agent id, `run_id` = session id, `provider` `codex`, `model` the slug, `tier` from `models.json`, `task` the Agent description, `source` `native-luna`, `status` `dispatched` (row shape of `dispatch_run_row`, `host_ledger.py:109-138`). A cwd outside git records `snapshot: "no-repo"` and continues.
2. Hand-back: `turn.complete` fires at the agent's end with `e.agentId` (types `index.d.ts:4606-4607`). For a luna id the hook runs `agents-inc luna end --outcome <done|failed|quota-paused|aborted>` with the step usage sums. `end` runs the module's `verify` with no allow list, then appends a return row through `ledger.record_return` (`agents_inc/ledger.py:285`) with `status` = outcome, `verdict` none, usage, and `snapshot` = `unchanged`, `changed:<n>` plus the first 20 paths, or `no-repo`. The hook returns `{ text }` with one line beneath the answer when the tree changed: `agents-inc: tree changed during luna run: <paths>`. A SendMessage follow-up is a new turn on the same agent: there is one ledger node per luna agent, and `end` appends a return update to that node at each hand-back, re-verifying against the spawn snapshot (FR-026).
3. The PostToolUse `agent-done` hook already appends a row for every Agent call with `model` = the Agent `model` parameter or `unknown` and `provider` `claude` (`agents_inc/install/hook.py:223-230`, `agents_inc/host_ledger.py:63-66`). For `subagent_type == 'agents-inc:luna'` that row would be a second, mislabelled record, so `dispatch_row` returns `None` for that type (spec Inventory change row for `host_ledger.py`).
4. Failures of `begin` or `end` are logged to debug and never fail the step: the record is accounting, the permission system is the boundary (Q2).
5. Not run on this path: prompt lint (`dispatch.py:218`), report lint (`:237`), structured gates, the trust record (`:869`). Q2.

The snapshot is not attributed: parallel luna agents and the parent edit the same tree, so `changed` means "the tree changed while this agent ran", not "this agent changed it". The result is informational, not a verdict (FR-026); the parent decides what to do with it.

### D7 Gate and persona deny (`agents_inc/install/hook.py`)

`BRAIN_PREFIX` (`hook.py:29`) becomes `NATIVE_TYPES = frozenset({"agents-inc:luna"})`; `_is_brain` (`hook.py:103-105`) becomes an exact-match `_is_native`. `persona_deny` (`:107`) and `gate_deny` (`:152`) call it, in every gate mode, foreground or background (FR-022). `luna-brain:luna` is denied under enforce and gets the persona check again. Tests: `tests/test_agent_gate.py:99-102`, `tests/test_hook_persona_guard.py:78`.

### D8 Doctor (`agents_inc/install/doctor.py`)

`check_install` (`doctor.py:86`) adds `_luna_warnings` beside `_mod_missing` (`doctor.py:111`): `LUNA_OFF` (switch off), `LUNA_CODEX_NOT_READY` (Codex missing or logged out), `LUNA_CATALOG_MISSING` (no cache entry for the slug). All are warnings; `READY` is unchanged (FR-020, US4 scenarios 1 and 2). The doctor command in `cli.py` prints `luna type: ready|off|unavailable (<code>)`.

### D9 Stress suite (`docker/luna_stress.sh`, FR-028)

Copy `/src/mods/agents-inc`, use `subagent_type agents-inc:luna`, default `R=10`. Before any scenario, a warm step runs the cache command T005 records and fails the suite unless `models_cache.json` holds the slug (FR-011 would otherwise fail every step in the fresh container home). Each run keeps its stream-json `permission_denials` and tool-use and tool-result pairs, so `HAIKU=1` and luna runs can be compared per scenario (SC-002). Debug lines are counted by the prefix `agents-inc luna:`. Parent `--model sonnet` so any haiku usage in `modelUsage` is a placeholder leak (SC-003). Add scenarios: `delete` (US2 independent test: task asks luna to delete `a.txt`, `--disallowedTools "Edit,Write,Bash"`; pass when `git status --porcelain` is empty and the new rollouts hold no `exec`, `exec_command`, `apply_patch`, collaboration or MCP call; SC-004), `steps5` (five Bash steps; compare the summed step usage in the debug lines with the thread's last Codex total, within 1%; SC-006), and `HAIKU=1` (same prompts with `subagent_type general-purpose`, `model: haiku`) to record permission decisions for SC-002. New columns: `rui` (`request_user_input` count, SC-005), `claude_steps` (SC-003). `SRC` and `OUT` variables let the same script run on the macOS host.

### D10 Spike retirement and canon

`mods/luna-brain/` stays as a folder through the soak. It is no longer an install target: nothing installs it today either; the stress suite and the gate stop naming it. Its removal is a polish task after SC-001 passes on the shipped type (spec Inventory row 1). `docs/DECISIONS.md` gets D69 (next free number; the last entry is D68, `docs/DECISIONS.md:692` [inferred: no D69 or above found]) per FR-027.

## Project Structure

### Documentation (this feature)

```text
specs/028-agents-inc-as-mod/
├── spec.md
├── plan.md        # this file
├── research.md    # R1-R8
├── tasks.md
├── analyze.md
└── checklists/requirements.md
```

Data model and contracts are inline (D5 status JSON, D6 ledger row, D3 stderr lines); no separate files, by dispatch scope.

### Source Code (repository root)

```text
mods/agents-inc/
├── hooks/hooks.json          # modules: relay.ts, luna.ts
├── hooks/luna.ts             # new: native type, turn.step, agent.spawn, agent.offer, turn.complete
├── hooks/luna.test.ts        # new: plugin tests (ported from mods/luna-brain/hooks/luna.test.ts plus US3 cases)
└── README.md                 # luna section: on/off switch, readiness
agents_inc/install/
├── luna_native.py            # new: status, on/off, begin, end
├── cli.py                    # `luna` subcommand; doctor luna line
├── runtime.py                # catalog fail-closed, isolated home, record line, tool counts, quota exit
├── hook.py                   # NATIVE_TYPES exact match
└── doctor.py                 # LUNA_* warnings
agents_inc/host_ledger.py     # dispatch_row skips agents-inc:luna
docker/luna_stress.sh         # shipped type, delete, steps5, HAIKU baseline
docs/DECISIONS.md             # D69
tests/
├── test_luna_native.py       # new
├── test_codex_tool_access.py # host-tools catalog, isolated home, record line
├── test_agent_gate.py        # exact type
├── test_hook_persona_guard.py
├── test_host_ledger.py       # skip row
└── test_doctor_codex_optional.py
```

**Structure Decision**: The mod stays one plugin folder (spec 027 install path, FR-019). Python logic the mod needs sits behind one CLI verb so the mod never imports Python or reads agents-inc state files directly.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| P7 WARN: a subagent type whose steps luna answers | Operator direction 2026-10-24 ("i want it to actually be luna") | Keeping luna behind dispatch only is the pre-028 state the operator moved away from |
| P8 WARN: no prompt-contract lint on the native path | Q2 answer: parent verifies like any subagent | Running `lint_prompt` on Agent prompts would refuse most native calls, which carry no 14-field contract |
| New module `luna_native.py` and a `host_ledger.py` edit (now spec Inventory change rows, analyze F1 resolution) | FR-026 needs a ledger write and a snapshot without dispatch | Writing JSONL from TypeScript duplicates `host_ledger` row shapes and the snapshot code |
