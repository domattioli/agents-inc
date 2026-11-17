<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-plan repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Implementation Plan: Free models through dispatch

**Branch**: `development` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/037-free-models-via-dispatch/spec.md`

## Summary

Add a third dispatch kind, `free`, beside `codex` and `claude`. A new module `agents_inc/install/free_launch.py` holds the allowed-slug map and runs the unchanged wrappers (`gask.sh`, `mask.sh`, `oask.sh`) with the prompt on stdin. `_kind()` returns `free` for map slugs. Pre-launch refusals (task kind, classification, fan-out, grants, resume, inputs, cap, cooldown) run before any provider call. Gates judge the saved reply through a `{report}` token. The wrapper exit code maps to named outcomes. The catalog refreshes to the 2026-11-09 probe. A D75 entry in `docs/DECISIONS.md` amends D16 and D17.

## Technical Context

**Language/Version**: Python 3.11+ (standard library only), Bash 3.2+ for the wrappers
**Primary Dependencies**: none new. Reuses `dispatch.py`, `router.py`, `routing.json`, `models.json`, and `skills/codex-bridge/scripts/{gask,mask,oask}.sh`
**Storage**: run directory files (`run.json`, `prompt.md`, `stdout.md`, `events.jsonl`)
**Testing**: `python3 -m unittest discover -s tests -p 'test_*.py'`, run in the docker images (`docker/Dockerfile.dev`, `docker/Dockerfile.ci`); wrappers stubbed by fake scripts on PATH
**Target Platform**: macOS consumer, Linux docker for development
**Project Type**: CLI and library
**Performance Goals**: none beyond wrapper latency
**Constraints**: $0 per task (P5); no paid fallback; keys never in prompts (D2); delegates write only in the repo (P1); wrappers unchanged
**Scale/Scope**: about 10 free slugs; one new module of roughly 250 lines; edits to `dispatch.py`, `render_dispatch.py`, `slots.md`, `models.json`, the broker validators, `docs/DECISIONS.md`, and tests

## Constitution Check

| Principle | Result |
|---|---|
| P0 cross-reference | Pass. The D75 entry cites D16 and D17, and copies no rule text. |
| P1 repo-scoped writes | Pass. Free runs have no tools. Input files must sit inside the working directory. |
| P2 ladder | Pass. Free models are Grunt-class optional providers. No Worker or Lead role. |
| P3 no self-graded gates | Pass. No gate gives `unverified`, never green. Gates run in the supervisor, on the saved reply. |
| P4 deterministic policy | Pass. Every refusal is code, and unknown slugs fail closed. |
| P5 hard $0 | Pass. Cost is recorded as 0. Cap and cooldown pause the run. No paid path. |
| P6 audience | Pass. Plan and spec artifacts are agent-facing. |
| P7 nickname discipline | Pass. No codename is passed where a model id is expected. |
| P8 prompt contract | Pass. The free path renders through the same prompt contract and `check_dispatch_prompt.py`. |
| P9 surgical edits | Pass. New logic goes in a new module. `dispatch.py` gets small seams only. |
| P10 lessons | N/A |

Post-design re-check: pass. The one tension is D16 (wrappers are legacy); D75 resolves it by naming dispatch a governed caller.

## Project Structure

### Documentation (this feature)

```text
specs/037-free-models-via-dispatch/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── free-dispatch.md
└── tasks.md            # created by /speckit-tasks
```

### Source Code (repository root)

```text
agents_inc/install/
├── free_launch.py        # NEW: FREE_MODELS map, wrapper_argv, wrapper_env, run_free, classify_rc, parse_usage, build_input_section
├── dispatch.py           # _kind() returns "free"; run() and _run_dir_phase() branch to run_free; _fan_out_check skipped; broker validators reject free slugs
agents_inc/
├── models.json           # refresh to the 2026-11-09 probe
├── routing.json          # optional_allowed_tasks stays; no edit expected
skills/workerbee/
├── slots.md              # TASK_KIND, INPUT_FILES
└── scripts/render_dispatch.py   # accept the two slots; {report} token screen
docs/DECISIONS.md         # D75
tests/
├── test_free_dispatch.py        # NEW: refusals, rc map, gates, inputs, cap/cooldown
├── test_dispatch_cli.py         # kind routing, unchanged codex/claude behavior
├── test_models_catalog.py       # catalog matches probe
└── fixtures/fake_wrappers/      # NEW: stub gask/mask/oask
```

**Structure Decision**: single project. One new module isolates the free path so Codex and Claude dispatch stay byte-for-byte unchanged (FR-016).

## Complexity Tracking

No constitution violations.
