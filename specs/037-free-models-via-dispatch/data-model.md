<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-plan repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Data Model: Free models through dispatch

## FreeModel (entry in `FREE_MODELS`)

| Field | Type | Notes |
|---|---|---|
| slug | string | key; exact match only |
| provider | gemini, mistral, openrouter | selects wrapper |
| wrapper | path under `skills/codex-bridge/scripts/` | `gask.sh`, `mask.sh`, `oask.sh` |
| tier | string or null | `--tier` value; null for OpenRouter |
| model_env | string or null | `MODEL` value for `oask.sh` |
| host | string | provider host, for the blocked message |
| max_input_chars | int | per-slug input limit |

Rule: a slug not in the map is unsupported. A catalog entry that lists the task as bad blocks the run.

## FreeRun (additions to `run.json`)

| Field | Value |
|---|---|
| kind | `free` |
| provider | from the entry |
| wrapper, wrapper_sha256 | path and hash at launch |
| task_kind | one of `optional_allowed_tasks` |
| classification | public, internal, or confidential (author written) |
| input_files | list of `{path, bytes, sha256}` |
| usage | tokens when the wrapper reports them, else null |
| cost_usd | 0 |
| workers_spawned | 0 |
| outcome, reason | per the rc map |

## Slots (new)

- `TASK_KIND`: required for free runs.
- `INPUT_FILES`: optional array of repo-relative text file paths.

## State transitions

`refused-*` (before launch) → none. `launched` → `green` | `unverified` | `red:<reason>` | `quota-paused` | `blocked`.
