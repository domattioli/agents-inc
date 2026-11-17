<!-- provenance: author=domattioli model=opus effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=spec041-lead -->
# Inventory: terminology terms in agents-inc (spec 041)

Snapshot of `/Users/domattioli/Projects/agents-inc` on branch `development` at `cb46412`, taken 2026-11-15. Counts are evidence for scope and migration cost, not a quality judgment.

## Method

Command (script kept in the dispatch scratchpad as `inv.py`):

```bash
python3 -I inv.py   # walks `git -C /Users/domattioli/Projects/agents-inc ls-files`, exit code 0
```

- File set: tracked files only (`git ls-files`), so `.git`, `.scratch`, `.workerbees`, `node_modules`, `build/`, `dist/` and `*.egg-info` are excluded.
- Counts are regex matches (not lines), shown in the `regex` column. Case handling per regex.
- Surface split:
  - historical docs: `CHANGELOG.md`, `docs/DECISIONS.md`, `docs/PLAN-MVP.md`, `docs/adr/`, `docs/teach-me/`, `docs/proposals/`, `docs/governance/{ASTRA-REVIEW-2,FREEZE-002,PLAN-BUILD-2}.md`, `docs/governance/proof/`.
  - current docs: every other `.md`.
  - tests: anything under `tests/` or `fixtures/` (includes golden JSON fixtures).
  - code: every other non-`.md` file (Python, shell, TypeScript, JSON, SVG).
- Limits: `docs/DECISIONS.md` is counted whole as historical, although its newest entries (D78, D80) are live rulings. Generic English uses ("the operator", "a user", "delegate the task", "lead to") are not separated from term uses; treat broad words (Worker, Delegate, operator, user, tier, ultra) as upper bounds.

## Counts

| Term | regex | current docs | historical docs | code | tests | total | files |
|---|---|---|---|---|---|---|---|
| Orchestrator | `\b[Oo]rchestrator` | 72 | 45 | 83 | 106 | 306 | 63 |
| Supervisor | `\b[Ss]upervisor` | 65 | 36 | 53 | 123 | 277 | 65 |
| Executive | `\b[Ee]xecutive` | 60 | 21 | 69 | 195 | 345 | 65 |
| Workhorse | `\b[Ww]orkhorse` | 66 | 23 | 113 | 185 | 387 | 77 |
| Grunt | `\b[Gg]runt` | 103 | 47 | 186 | 357 | 693 | 110 |
| Lead | `\bLead\b` | 117 | 68 | 173 | 27 | 385 | 40 |
| Worker | `\b[Ww]orkers?\b` | 118 | 148 | 251 | 170 | 687 | 97 |
| Delegate (noun/verb) | `\b[Dd]elegates?\b` | 269 | 141 | 326 | 75 | 811 | 95 |
| Chief of Staff | `Chief of Staff` | 12 | 2 | 3 | 0 | 17 | 9 |
| CoS | `\bCoS\b` | 84 | 38 | 68 | 16 | 206 | 36 |
| Interlocutor | `\b[Ii]nterlocutor` | 4 | 5 | 0 | 0 | 9 | 4 |
| CEO | `\bCEO\b` | 46 | 43 | 5 | 0 | 94 | 18 |
| operator | `\b[Oo]perator` | 170 | 152 | 82 | 35 | 439 | 81 |
| Owner | `\bOwner\b` | 3 | 0 | 0 | 0 | 3 | 2 |
| user | `\b[Uu]sers?\b` | 30 | 50 | 148 | 88 | 316 | 103 |
| Team | `\b[Tt]eams?\b` | 7 | 10 | 1 | 0 | 18 | 4 |
| Tier/tier | `\b[Tt]iers?\b` | 211 | 72 | 393 | 319 | 995 | 132 |
| ultra-tier | `ultra-tier` | 5 | 0 | 0 | 0 | 5 | 2 |
| flash-tier | `flash-tier` | 3 | 0 | 0 | 0 | 3 | 2 |
| frontier | `\b[Ff]rontier\b` | 50 | 31 | 11 | 6 | 98 | 23 |
| cheap | `\bcheap\b` | 122 | 28 | 36 | 16 | 202 | 41 |
| mid | `\bmid\b` | 15 | 26 | 53 | 15 | 109 | 36 |
| ultra | `\bultra\b` | 74 | 15 | 78 | 29 | 196 | 60 |
| Driver | `\bDriver\b` | 1 | 5 | 0 | 0 | 6 | 2 |
| Host | `\bHost\b` | 3 | 13 | 10 | 1 | 27 | 11 |
| Stdin worker | `[Ss]tdin worker` | 4 | 14 | 6 | 0 | 24 | 8 |
| Guest agent | `[Gg]uest agent` | 1 | 14 | 29 | 5 | 49 | 23 |
| Dispatcher/dispatcher | `\b[Dd]ispatcher\b` | 12 | 0 | 6 | 1 | 19 | 12 |
| Second (role) | `\bSecond\b` | 15 | 7 | 2 | 19 | 43 | 19 |

- **Orchestrator**: `tests/fixtures/012/router_golden.json` 49, `docs/DECISIONS.md` 43, `mods/delegate-pane/hooks/mission.test.ts` 24, `skills/workerbee/SKILL.md` 22, `fixtures/routing-eval/cases.jsonl` 18, `tests/test_model_sync.py` 14, `skills/speckit-pipeline/SKILL.md` 10, `agents_inc/role_defaults.py` 9
- **Supervisor**: `tests/test_policy.py` 34, `docs/DECISIONS.md` 30, `tests/test_gateway.py` 25, `skills/workerbee/SKILL.md` 23, `tests/test_governance_negatives.py` 14, `skills/workerbee/scripts/render_dispatch.py` 11, `tests/test_astra_group2.py` 9, `agents_inc/governance.json` 8
- **Executive**: `tests/test_mandate_session.py` 76, `tests/fixtures/012/router_golden.json` 49, `docs/DECISIONS.md` 21, `skills/workerbee/SKILL.md` 20, `tests/test_store_dualwrite.py` 14, `fixtures/routing-eval/cases.jsonl` 12, `agents_inc/role_defaults.py` 11, `skills/workerbee/scripts/render_dispatch.py` 10
- **Workhorse**: `tests/fixtures/012/router_golden.json` 49, `fixtures/routing-eval/cases.jsonl` 32, `mods/delegate-pane/hooks/mission.test.ts` 30, `mods/delegate-pane/hooks/pane.test.tsx` 27, `tests/test_lineup_router.py` 26, `docs/DECISIONS.md` 23, `skills/workerbee/SKILL.md` 18, `tests/test_hook_persona_guard.py` 15
- **Grunt**: `tests/fixtures/012/router_golden.json` 78, `docs/DECISIONS.md` 46, `skills/workerbee/SKILL.md` 38, `mods/delegate-pane/hooks/rungs.ts` 35, `tests/test_router_free_first.py` 31, `tests/test_ledger.py` 28, `fixtures/routing-eval/cases.jsonl` 27, `tests/test_gateway.py` 26
- **Lead**: `docs/DECISIONS.md` 59, `agents_inc/install/dispatch.py` 43, `docs/governance/DELEGATION-MODEL.md` 35, `mods/delegate-pane/hooks/frames.ts` 32, `mods/delegate-pane/hooks/frames.test.ts` 29, `CONTEXT.md` 20, `docs/HOW-IT-WORKS.md` 19, `mods/delegate-pane/README.md` 19
- **Worker**: `docs/DECISIONS.md` 96, `agents_inc/install/dispatch.py` 88, `tests/test_policy.py` 23, `CONTEXT.md` 20, `agents_inc/install/runtime.py` 20, `tests/test_governance_negatives.py` 20, `docs/PLAN-MVP.md` 19, `agents_inc/install/mcp_broker.py` 17
- **Delegate (noun/verb)**: `docs/DECISIONS.md` 96, `skills/workerbee/SKILL.md` 89, `mods/delegate-pane/hooks/frames.ts` 44, `agents_inc/install/dispatch.py` 39, `CHANGELOG.md` 36, `tests/test_mod_install.py` 35, `mods/delegate-pane/hooks/mission.ts` 34, `mods/delegate-pane/hooks/register.tsx` 34
- **Chief of Staff**: `skills/workerbee/SKILL.md` 5, `docs/governance/DELEGATION-MODEL.md` 4, `docs/DECISIONS.md` 2, `CONTEXT.md` 1, `docs/assets/delegation-model.svg` 1, `mods/delegate-pane/README.md` 1, `mods/delegate-pane/hooks/mission.test.ts` 1, `mods/delegate-pane/hooks/mission.ts` 1
- **CoS**: `docs/governance/DELEGATION-MODEL.md` 40, `docs/DECISIONS.md` 33, `mods/delegate-pane/hooks/frames.test.ts` 20, `mods/delegate-pane/hooks/frames.ts` 18, `mods/delegate-pane/README.md` 10, `CONTEXT.md` 9, `docs/HOW-IT-WORKS.md` 9, `README.md` 6
- **Interlocutor**: `docs/DECISIONS.md` 5, `docs/governance/DELEGATION-MODEL.md` 2, `CONTEXT.md` 1, `skills/workerbee/SKILL.md` 1
- **CEO**: `docs/DECISIONS.md` 33, `docs/governance/DELEGATION-MODEL.md` 28, `docs/governance/PLAN-BUILD-2.md` 5, `docs/governance/ASSESSMENT.md` 4, `CONTEXT.md` 3, `README.md` 3, `docs/assets/delegation-model.svg` 3, `docs/governance/SCHEMA-3NF.md` 3
- **operator**: `docs/DECISIONS.md` 125, `skills/workerbee/SKILL.md` 44, `skills/speckit-pipeline/SKILL.md` 18, `CONTEXT.md` 14, `scripts/statusline.d/SPEC.md` 12, `skills/workerbee/QUICKREF.md` 12, `agents_inc/install/hook.py` 10, `docs/HOW-IT-WORKS.md` 9
- **Owner**: `docs/governance/DELEGATION-MODEL.md` 2, `docs/RELEASING.md` 1
- **user**: `mods/agents-inc/hooks/luna.test.ts` 27, `docs/PLAN-MVP.md` 22, `mods/agents-inc/hooks/native/loop.test.ts` 19, `docs/DECISIONS.md` 15, `CHANGELOG.md` 8, `tests/test_install_paths.py` 8, `agents_inc/install/dispatch.py` 7, `agents_inc/install/runtime.py` 7
- **Team**: `docs/DECISIONS.md` 10, `CONTEXT.md` 6, `docs/assets/logo.svg` 1, `docs/governance/DELEGATION-MODEL.md` 1
- **Tier/tier**: `skills/workerbee/SKILL.md` 58, `docs/BENCH.md` 51, `tests/test_router_free_first.py` 48, `docs/DECISIONS.md` 35, `agents_inc/models.json` 33, `agents_inc/model_sync.py` 31, `skills/workerbee/scripts/gen_tier_tables.py` 24, `agents_inc/ledger.py` 23
- **ultra-tier**: `skills/workerbee/SKILL.md` 3, `skills/codex-bridge/SKILL.md` 2
- **flash-tier**: `skills/workerbee/SKILL.md` 2, `docs/governance/DELEGATION-MODEL.md` 1
- **frontier**: `docs/free-openrouter-models.md` 25, `docs/DECISIONS.md` 19, `docs/BENCH.md` 14, `docs/PLAN-MVP.md` 6, `agents_inc/ledger.py` 4, `docs/governance/ASTRA-REVIEW-2.md` 3, `skills/speckit-pipeline/SKILL.md` 3, `CONTEXT.md` 2
- **cheap**: `docs/BENCH.md` 96, `docs/DECISIONS.md` 15, `tests/test_store.py` 12, `skills/workerbee/SKILL.md` 11, `agents_inc/models.json` 8, `docs/governance/ASTRA-REVIEW-2.md` 4, `docs/proposals/delegation-savings-test.md` 3, `skills/codex-bridge/scripts/mask.sh` 3
- **mid**: `docs/DECISIONS.md` 19, `agents_inc/install/mcp_broker.py` 10, `agents_inc/install/worker_mcp.py` 9, `agents_inc/models.json` 8, `tests/test_delegate_pane_rungs.py` 7, `scripts/statusline.d/SPEC.md` 6, `mods/delegate-pane/hooks/frames.test.ts` 5, `scripts/statusline.d/collect_usage.py` 4
- **ultra**: `skills/workerbee/SKILL.md` 28, `skills/codex-bridge/tests/ultra_smoke.sh` 11, `skills/codex-bridge/reference/budget-mode.md` 10, `docs/DECISIONS.md` 8, `docs/free-openrouter-models.md` 8, `agents_inc/models.json` 7, `skills/codex-bridge/scripts/route.sh` 6, `skills/codex-bridge/scripts/route.sh.bak.20260904_212336` 6
- **Driver**: `docs/PLAN-MVP.md` 5, `CONTEXT.md` 1
- **Host**: `docs/PLAN-MVP.md` 10, `agents_inc/install/host_wiring.py` 6, `CHANGELOG.md` 2, `agents_inc/install/runtime.py` 2, `CONTEXT.md` 1, `agents_inc/host_ledger.py` 1, `agents_inc/install/hook.py` 1, `docs/DECISIONS.md` 1
- **Stdin worker**: `docs/PLAN-MVP.md` 14, `CONTEXT.md` 4, `agents_inc/adapters/base.py` 1, `agents_inc/adapters/claude.py` 1, `agents_inc/adapters/codex.py` 1, `agents_inc/pipeline.py` 1, `agents_inc/reviewer.py` 1, `agents_inc/router.py` 1
- **Guest agent**: `docs/DECISIONS.md` 10, `CHANGELOG.md` 4, `agents_inc/install/native.py` 4, `.zenodo.json` 3, `agents_inc/install/cli.py` 3, `agents_inc/native_names.py` 3, `tools/native_stress.py` 3, `agents_inc/host_ledger.py` 2
- **Dispatcher/dispatcher**: `docs/governance/CEO-BRIEF.md` 4, `skills/workerbee/header.md` 3, `docs/HOW-IT-WORKS.md` 2, `skills/workerbee/slots.md` 2, `agents_inc/install/mcp_broker.py` 1, `mods/agents-inc/hooks/native/loop.test.ts` 1, `mods/agents-inc/hooks/native/loop.ts` 1, `skills/codex-bridge/scripts/agent.sh` 1
- **Second (role)**: `docs/DECISIONS.md` 6, `tests/test_pipeline.py` 5, `tests/test_governance_negatives.py` 4, `tests/test_migrate.py` 4, `CONTEXT.md` 3, `skills/workerbee/SKILL.md` 3, `docs/governance/DELEGATION-MODEL.md` 2, `docs/governance/ROUTING-RANKING.md` 2

## Code identifiers that carry these words (rename cost, sampled by hand)

- `agents_inc/role_defaults.py` and `~/.config/agents-inc/settings.json` key `roles` (D80): keys `write_rung`, `grunt_read_only`, `executive_judgment_only`, values `"workhorse"`, `"orchestrator"`. Rung words are settings keys and values.
- Rung enums since D36: `tier` field values `grunt`, `workhorse`, `orchestrator`, `executive` in `agents_inc/models.json` (33 tier hits), `agents_inc/ledger.py` (23), the SQLite `tier` CHECK in `docs/governance/SCHEMA-3NF.md`, and `tests/fixtures/012/router_golden.json` (49 Orchestrator, 49 Executive, 49 Workhorse, 78 Grunt hits).
- The column and field name is `tier`, while prose says rung. CONTEXT.md:23 retires Tier as a word, yet the code field keeps it.
- `skills/workerbee/scripts/render_dispatch.py:259-299` `derive_chain` builds slots `DELEGATE`, `SUPERVISOR`, `EXECUTIVE`. `SUPERVISOR` there means "the party one step above this delegate" (operator, the next rung alias, or `CoS`). That is the relational sense of R4, already in code.
- `agents_inc/governance.json:24-26`: agent id `agent-supervisor-01`, name `Orchestrator Supervisor`, type `supervisor`. Both role words sit in one registry record.
- `mods/delegate-pane/hooks/rungs.ts` (35 Grunt hits), `frames.ts` (32 Lead, 18 CoS, 44 Delegate): the live view renders these words to the operator.
- `skills/codex-bridge/scripts/route.sh` and `skills/codex-bridge/tests/ultra_smoke.sh`: `ultra` is the `CODEX_BRIDGE_MODE=ultra` value, a mode name, not a rung.

## Findings against the CoS diagnosis

1. Orchestrator and Supervisor double duty: confirmed. CONTEXT.md:31 (Orchestrator is a rung and an alias for Lead), CONTEXT.md:32 (Lead aliases Supervisor, Orchestrator), CONTEXT.md:48 (Rung: Orchestrator aka Supervisor), CONTEXT.md:49 and ROUTING-RANKING.md (generic "A Supervisor compares both outputs"), QUICKREF.md ("The supervisor owns the verifier").
2. Worker aliases rung names: confirmed. CONTEXT.md:10 and DELEGATION-MODEL.md Roles list Workhorse and Grunt as Worker aliases, and the same file says "Rungs ... cost class only, never a role".
3. Rung "cost and capability class only" vs real effects: confirmed. CONTEXT.md:48 says "only" and in the same row lists default work by rung (D78). DELEGATION-MODEL.md: the ladder picks the Lead ("higher rung manages"). D46.3 makes delegation rights depend on rung.
4. Executive name: confirmed. D78.2 "keeps judgment only", CONTEXT.md:34 "No automatic Task Authority".
5. CoS definition: partly confirmed. CONTEXT.md:34 already says "Only the CoS commits and pushes" and "Dispatches only the Lead", but opens with "the operator's right hand"; the gate role is spread through the row, not stated first.
6. Several names for the human: confirmed. CEO 94 hits, operator 439, Owner 3 (DELEGATION-MODEL.md calls it a pre-D46 alias), user 316 (mostly generic or code). CONTEXT.md:42 "CEO: The operator."
7. Team two senses: confirmed. CONTEXT.md:10 (Worker collective alias, D46.4) and CONTEXT.md:60 (D63 proposed session team).
8. Legacy rung words in current docs: confirmed. Current-doc hits: tier 211, cheap 122, frontier 50, mid 15, ultra-tier 5, flash-tier 3. Many `tier` and `cheap` hits are in `docs/BENCH.md` (51 and 96) and refer to provider price tiers, not rungs.
9. Delegate overload: confirmed. CONTEXT.md:10 lists Delegate as a Worker alias, while the dispatch prompt and CONTEXT.md:36-37 use it for any dispatched agent including a Lead (this prompt's "delegate" for the Lead).
10. Driver, Host, Stdin worker: confirmed overlap, low usage. Driver 1 current-doc hit (CONTEXT.md:8), 5 in PLAN-MVP. Stdin worker 4 current-doc hits, 14 in PLAN-MVP, 6 in code docstrings. Host 3 current, 13 historical, 10 code (`host_wiring.py`, `host_ledger.py`: Host means the agent CLI, a live code sense).
11. Guest agent: confirmed. CONTEXT.md:36 says it is not a Worker or delegate. DELEGATION-MODEL.md never mentions it (0 hits).
