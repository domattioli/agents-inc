<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-plan repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Contract: `agents-inc dispatch` for free models

## Command

```
agents-inc dispatch --slots <file> --model <free slug>
```

No `--effort`. No `--resume` (exit 2). No fan-out.

## Required slots

`TASK_KIND` (extract, summarize, classify), `CLASSIFICATION` (public or internal; confidential needs workspace authorization). All other slots follow `skills/workerbee/slots.md`. `GATES` is optional; each gate command may use `{report}`.

## Refusals (exit 2, no provider call)

| Outcome | Cause |
|---|---|
| refused-task | `TASK_KIND` missing or not allowed |
| refused-classification | `CLASSIFICATION` missing, not author written, or confidential without authorization |
| refused-fan-out | fan-out above 0 |
| refused-grants | tool grants or a permission mode beyond default or plan |
| refused-inputs | file outside the working directory, symlink, non-text, credential-shaped, or over the size limit |

## Outcomes and exit codes

| Result | Outcome | Exit |
|---|---|---|
| gates pass | green | 0 |
| no gates | unverified | 0 |
| gate fails | red `gate-failed` | 1 |
| gate wrote into the repo | red `gate-wrote` | 1 |
| rc 4 (`oask.sh`) | red `redacted-reply` | 1 |
| rc 2 with "no API key" | red `provider-key-missing` | 1 |
| rc 3 | red `wrapper-refused` | 1 |
| other rc 1 or 2 | red `rc-nonzero` | 1 |
| 429 text, or a router cap or cooldown hit (`router._at_cap`, `router._in_cooldown`, before launch) | quota-paused | 75 |
| stderr "cannot reach" or "timeout" | blocked, host named | 69 |

Classification of 429, timeout and unreachable uses stderr text; all three are rc 1 in the wrappers.

## Run record

`run.json` gains the FreeRun fields in `data-model.md`. Cost is 0 and workers spawned is 0.
