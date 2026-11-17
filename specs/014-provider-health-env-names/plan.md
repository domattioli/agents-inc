<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Provider Health Freshness and Key Name Consistency

**Branch**: `development` (no feature branch) | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: `specs/014-provider-health-env-names/spec.md` (Clarifications answered 2026-10-01). Plan written inline by the Supervisor (Orchestrator rung, ruling R1).

## Summary

Three changes, Bash plus Python standard library:

1. `route.sh` stops showing old errors as current: an `ok` report clears `last_error`, `status` marks entries older than 24 hours as stale, and a missing backend entry no longer crashes `report`. `mask.sh` and `oask.sh` also report each call to `route.sh`, so the backend entry refreshes after a standalone call.
2. Both key modules list provider `openrouter` for `OPEN_ROUTER_API_KEY` and `OPENROUTER_API_KEY`, and both read `~/.config/workerbees/.env` and `~/.config/agents_inc/.env`, writing only the first.
3. Dated correction notes for the 2026-09 Mistral state, and a ZDR note in `docs/HOW-IT-WORKS.md`.

## Technical Context

**Language/Version**: Bash 3.2+, Python 3.9+ standard library
**Primary Dependencies**: none new
**Storage**: `~/.codex-bridge/backend-health.json` (shared by `route.sh` and `agents_inc/free_health.py`), `.env` files (names only)
**Testing**: `python3 -m unittest`; new `tests/test_route_health_freshness.py` runs `route.sh`, `mask.sh`, `oask.sh` under a fake HOME with stub `curl`; `tests/test_keys.py` extended for both modules
**Constraints**: no real model or network call; no write to the live `~/.codex-bridge`, `.env`, or key files; fake sentinel key values only; peer-owned `agents_inc/free_health.py` untouched
**Scale/Scope**: one Bash router, two wrapper traps, two key modules, three doc notes

## Existing code (evidence, re-grepped 2026-10-01)

- `route.sh:229-260` `cmd_report`: on `ok` sets `status` and `cooldown_until` only; any non-empty message overwrites `last_error`; `last_checked` is already set on every report. `data[backend]` raises `KeyError` when the entry is absent; `_init_state` adds only `mistral`, `opus`, `fable` to an existing file (`route.sh:92-101`).
- `route.sh:262-301` `cmd_status`: text table with no age column; an expired cooldown already renders as `ok`.
- `route.sh:173-226` `cmd_pick`: reads only `cooldown_until`. Staleness never enters pick (FR-003 holds today; a regression test guards it).
- `agents_inc/free_health.py:119-124` `backend_key` returns the provider name for `mistral` and `openrouter`, the same keys `route.sh` uses; on `ok` it sets `status`, `failure_streak`, `cooldown_until` but neither clears `last_error` nor sets `last_checked` (`:156-172`). The spec Background bullet "keys entries by provider and model" holds only for Gemini (correction G13). Not edited (peer-owned).
- `mask.sh:27-61` and `oask.sh:60-81`: exit traps classify the last HTTP status and call `free_health report`, preserving the exit code. `oask.sh` skips the report when no request was attempted (`OASK_ATTEMPTED`); `mask.sh` reports on every exit.
- `workerbees.keys` is an import alias of `agents_inc.keys` (`workerbees/__init__.py` aliases its public modules; `python3 -c 'import workerbees.keys as w, agents_inc.keys as a; print(w is a)'` prints `True`). `workerbees/keys.py` is never imported; DD6 and DD7 edit only `agents_inc/keys.py`, and the file is left as is (found while writing T002).
- `agents_inc/keys.py:6` `ENV_PATH = ~/.config/agents_inc/.env`; `workerbees/keys.py:11` `~/.config/workerbees/.env`. Both derive the provider as `name[:-len("_API_KEY")].lower()`. `agents_inc/doctor.py:8,104,120` passes `ENV_PATH` explicitly; `agents_inc/pipeline.py:13` calls `available_providers()` with defaults.
- `agents_inc/free_caps.py:166` reads only `OPEN_ROUTER_API_KEY` from the process environment. Out of FR-004 scope; recorded as a follow-up.
- Mistral recovery evidence: the local usage log `~/.codex-bridge/usage.jsonl` records `codestral-latest` calls with non-zero output tokens on 2026-09-24 and 2026-09-30 (read by the Supervisor 2026-10-01; rows not copied).

## Design decisions

- **DD1 ok clears error** (FR-001): in `cmd_report`, `ok` sets `last_error = None` and ignores any message. Non-`ok` results keep today's behavior (message overwrites `last_error`). `last_checked` stays set on every report.
- **DD2 missing entry** (FR-001, FR-003a): `cmd_report` calls `data.setdefault(backend, {status ok, cooldown_until None, last_error None, last_checked None})` before writing, so a file first created by `free_health` (no `openrouter` key) no longer crashes the report.
- **DD3 stale marker** (FR-002): `cmd_status` text mode adds an `Age` column. `last_checked` null or unparseable renders `unknown`. Age above 24 h renders `stale <N>h` (whole hours, floor) or `stale <N>d` at 48 h and above; age at or under 24 h renders `<N>h` or `<N>m`; a future timestamp counts as fresh (`0m`); a timestamp without a timezone is read as UTC (analyze B12). The window is a constant `FRESH_WINDOW_H = 24` in the embedded Python. `status --json` is unchanged (raw file).
- **DD4 pick unaffected** (FR-003): no change to `cmd_pick`; a test asserts a stale or unknown entry is still picked.
- **DD5 wrapper reports** (FR-003a): after the existing `free_health report` line, each trap runs `bash "$SCRIPT_DIR/route.sh" report <backend> <result> "<msg>" >/dev/null 2>&1 || true`, with backend `mistral` or `openrouter`. Mapping: `ok` to `ok`; `rate_limited`, `overloaded`, `error` to `transient` (status `degraded`, no cooldown change, so the cooldown `free_health` computed is not overwritten by `route.sh`'s fixed 60-minute quota cooldown); `withdrawn` and `zdr` send no route report, matching `free_health`, which leaves the backend record untouched for model-level outcomes. The message is the wrapper's existing error message when one is set (`mask.sh` only), else `<outcome> http <status>`, or `<outcome>` when no HTTP status was seen (`oask.sh` has no message today), so a failure report always leaves a non-empty `last_error`. The trap's `exit $ec` is unchanged. `mask.sh` reports on every exit today, including usage and missing-key exits (analyze B2), so it gains `MASK_ATTEMPTED=false` near the trap and `MASK_ATTEMPTED=true` on the line before the request `python3 -` block; the new `route.sh` report runs only when `MASK_ATTEMPTED` is true (the `free_health` report is unchanged). `oask.sh` already guards with `OASK_ATTEMPTED`. `CODEX_BRIDGE_MODE` is pinned to `standard` for that call (`CODEX_BRIDGE_MODE=standard bash route.sh ...`), because `route.sh` exits 2 on an invalid mode before doing anything.
- **DD6 key alias** (FR-004): `agents_inc/keys.py` (serving both import paths) gains `_PROVIDER_ALIASES = {"open_router": "openrouter"}` applied after the strip-and-lowercase step. `setup_key("openrouter")` still writes `OPENROUTER_API_KEY`. The modules never read values into output; only `bool(val)` is used, as today.
- **DD7 key store paths** (FR-008): `agents_inc/keys.py` sets `ENV_PATH = ~/.config/workerbees/.env` and add `LEGACY_ENV_PATH = ~/.config/agents_inc/.env`. `available_providers(env_path=None, ...)`: when `env_path` is `None` or equals the module's `ENV_PATH`, scan both, computing `Path.home()` at call time; an explicit other path scans only that path (existing tests pass explicit temp paths). `setup_key` default target is `ENV_PATH` (workerbees). `extra_env_paths` defaults keep each module's current behavior (`agents_inc` adds `~/Projects/.env`; `workerbees` adds none).
- **DD8 docs** (FR-006, FR-007): append one dated line under each cited bullet in `docs/DECISIONS.md` (after `:60` and `:98`) and a dated note after `specs/010-persistent-exec-session/analyze-2026-09-12b.md:191`, each reading: 2026-10-01 correction, the Mistral 401 was the pre-rotation state; later calls returned output on 2026-09-24 and 2026-09-30 per the local usage log; health freshness now shows in `route.sh status` (spec 014). Existing text is not rewritten. `docs/HOW-IT-WORKS.md` `## Legacy wrappers for optional providers` gains a ZDR bullet: an OpenRouter account privacy setting, changed at `openrouter.ai/settings/privacy`; with ZDR on, many `:free` endpoints refuse requests (404 ZDR violation); relaxing it lets those free providers train on inputs (#19); the repo does not change it. The same section's stale sentence "There is no `~/.config/workerbees/.env`" is corrected to name the read paths (`~/.config/workerbees/.env`, the older `~/.config/agents_inc/.env`, and `~/Projects/.env` for `agents_inc`'s default scan, analyze B5) and the one write path, and the table's OpenRouter env var cell lists both names.
- **DD9 peer file**: `free_health.py` clearing `last_error` and setting `last_checked` on its own `ok` path is the root fix for the shared file; it is a `BLOCKED-PEER` task. With DD5, `route.sh`'s report runs after `free_health`'s and corrects both fields.

## Constitution Check

Constitution at `~/Projects/DomI/specs/consumers/agents_Inc/memory/constitution.md` is unratified, so violations are WARN.

| Principle | Status | Note |
|---|---|---|
| P0 cross-reference, never duplicate | WARN | Two key modules stay duplicated; unifying them is out of scope (both edited identically). |
| P1 repo-scoped writes | PASS | Tests use a fake HOME; no live file written. |
| P2 labor ladder | PASS | haiku for narrow Bash, key, and doc edits; Supervisor writes tests. |
| P4 deterministic policy over prompt | PASS | Freshness is computed, not described. |
| P5 hard $0 per task | PASS | No model calls. |
| P6 human-doc rendering | PASS | T007 docs follow the AGENTS.md documentation style table: readable prose for human docs (analyze B7). |
| P8 dispatch contract | PASS | Every delegate prompt carries the 14 elements and passes `check_dispatch_prompt.py` (analyze B7). |
| P9 edit hygiene | PASS | Surgical edits. |

Post-design re-check: PASS (P0 WARN carried).

## Project Structure

### Documentation (this feature)

```text
specs/014-provider-health-env-names/
├── spec.md
├── plan.md
├── tasks.md
├── analyze.md
└── checklists/
    ├── requirements.md          (specify)
    └── health-and-names.md      (checklist phase)
```

### Source Code

```text
skills/codex-bridge/scripts/
├── route.sh                     # edit: DD1-DD3
├── mask.sh                      # edit: DD5 trap line
└── oask.sh                      # edit: DD5 trap line
agents_inc/keys.py               # edit: DD6, DD7
workerbees/keys.py               # edit: DD6, DD7
tests/
├── test_route_health_freshness.py   # new (Supervisor-owned)
└── test_keys.py                 # extend (Supervisor-owned)
docs/DECISIONS.md                # append notes (DD8)
docs/HOW-IT-WORKS.md             # ZDR + key-path notes (DD8)
specs/010-persistent-exec-session/analyze-2026-09-12b.md   # append note (DD8)
```

**Structure Decision**: one new test file named without the `.gitignore` words `key`, `secret`, `token`, `credential` (checked with `git check-ignore`, exit 1 = not ignored).

## Agent context update

Skipped: no `CLAUDE.md` (retired 2026-10-01); `AGENTS.md` unchanged.

## Complexity Tracking

None.
