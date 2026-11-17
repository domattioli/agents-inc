<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Contract: run outcomes, reason codes and exit codes

Outcome words and exit codes printed by `agents-inc dispatch`. Rows marked "unchanged" keep today's behaviour (constraint: passed and failed codes do not change). Rows marked "new" or "changed" need D84.

## Exit codes

| Code | Name | Outcomes | Status |
|---|---|---|---|
| 0 | `EXIT_OK` | `green`, `dry-run`, `--cancel` acknowledged | unchanged |
| 1 | `EXIT_RED` | `red` (any reason not below), `snapshot-failed` | unchanged |
| 2 | `EXIT_USAGE` | bad arguments, unreadable slots, child exit 2, and the free-run precheck refusals (`refused-*` outcomes written at `dispatch.py:1897-1900`, which return `EXIT_USAGE`) | unchanged |
| 3 | `EXIT_REFUSED` | every other `refused-*` outcome and `credential-seeking` | unchanged |
| 4 | `EXIT_UNVERIFIED` | `unverified` | new (was 0) |
| 69 | `EXIT_BLOCKED` | `red blocked`, caller sandboxed | unchanged |
| 75 | `EXIT_QUOTA` | `red quota-paused` | unchanged |
| 130 | `EXIT_CANCELLED` | `cancelled` | unchanged |

## Reason codes after a run

| Outcome | Reason | Condition | Status |
|---|---|---|---|
| red | `quota-paused` | provider usage limit text; checked first | unchanged |
| red | `blocked` | connection failure text | unchanged |
| red | `timeout` | turn deadline hit | unchanged |
| red | `rc-nonzero` | delegate exit non-zero or `is_error` | unchanged |
| red | `workers-spawned-missing`, `fan-out-over-total`, `workers-spawned-underreported` | fan-out checks | unchanged |
| red | `snapshot-tampered` | trusted script copy or snapshot changed | unchanged |
| red | `snapshot-error` | verify could not run | unchanged |
| red | `launch-failed` | the delegate process could not be launched (`dispatch.py:1573`) | unchanged |
| red | `snapshot-not-clean` | retired for outside-scope changes; kept only for a CHANGED list the verifier cannot split | changed |
| (retired) | `gate-wrote` | retired. Timing alone cannot attribute an outside change to a gate; the harness has no record of which process wrote a file. An outside change seen after the gates is `unverified scope-foreign-change` | changed |
| red | `gate-failed` | a gate ran and returned a different exit code | unchanged |
| red | `gate-timeout` | a gate started and was killed by its timeout | new (was `gate-missing`) |
| red | `gate-refused` | post-run re-screen refused a gate (danger list, credential, cwd outside; the pre-launch rule is `gate-cwd-outside` in `refusal-format.md`) | new (was `gate-missing`) |
| red | `no-report` | the report is missing, empty or only whitespace (operator ruling 2026-11-15); launch-level, so it holds with or without gates. A Claude or Codex run with an empty reply already ends `workers-spawned-missing`, which is reused; `no-report` covers the runs the fan-out check does not (free runs) | new |
| red | free wrapper reasons (`redacted-reply`, `provider-key-missing`, `wrapper-refused`) | spec 037 | unchanged |
| green | none | at least one gate ran, all passed | unchanged |
| green | `report-format-advisory` | as above, report had a format miss | unchanged |
| unverified | `no-gates` | no GATES supplied | exit changed to 4 |
| unverified | `gates-skipped-broker` | broker child | exit changed to 4 |
| unverified | `snapshot-skipped` | non-git read-only run; ranked in the first-match order after `scope-foreign-change` and before `gates-skipped-broker` and `no-gates`; a declared stop outranks it | exit changed to 4 |
| (claims reason) | `claims-block-malformed`, `claims-too-large` | claims check result `not-checked`, not a run outcome; see `claims-block.md` | new |

Scope-aware verify also prints `UNREADABLE <path>` (an allowed path whose bytes could not be compared; not a proven change) and `UNBASELINED <path>` (a git-ignored allowed path with no baseline). Legacy verify output is unchanged. The row and `run.json` carry the exit code actually returned: free precheck refusals 2, other refusals 3.
| unverified | `gate-not-runnable` | no gate failed and at least one could not start | new (was red `gate-missing`) |
| unverified | `scope-foreign-change` | paths outside FILES_IN_SCOPE changed during the run | new (was red `snapshot-not-clean`) |
| unverified | `delegate-stopped` | report block declares a stop | new |
| unverified | `scope-unreadable` | final scope evidence has an allowed path whose bytes could not be read (scope state `not-checked`); ranked after launch reds, failed gates and `delegate-stopped`, and before `gates-skipped-broker`, `no-gates` and `gate-not-runnable`; exit 4 | new (review 042 G6; was green) |

`gates-not-run-tampered` is a reason on each gate row only (the pinned scripts were tampered, so no gate was run). It is never a run reason: the run outcome is red `snapshot-tampered`, which wins at step 1 of the derivation in `data-model.md`.

`gate-missing` is retired as a reason word. Readers that match it (tests, `mcp_broker.py`, QUICKREF) are updated in the same phase.

## Outcome word to three-state field

Every run carries `state` (`passed`, `failed`, `not-checked`), mapped from the outcome word: `green` to `passed`; `red` and `snapshot-failed` to `failed`; `unverified`, every `refused-*`, `credential-seeking`, `cancelled` and `dry-run` to `not-checked`. The full table is in `data-model.md` "Run outcome".

## Status line

Existing tokens stay in order (`dispatch.py:1414-1420`). New tokens are appended before `out=`:

```text
gates=<n_passed>/<n> [failed:<argv0>:rc=<rc>,...] [not-checked:<argv0>:rc=<rc|none>,...] scope=not-checked:<paths> attribution=unknown
```

Failed and not-checked gates come first in the bracketed lists (FR-003). After the status line, dispatch prints one block with one line per gate, non-passed gates first, then passed gates in run order:

```text
gate <state> rc=<rc|none> cmd=<full command> last=<last output line>
```

When `claims=checked:<u> unsupported` has `u` above zero, dispatch then prints one line per unsupported claim (FR-012):

```text
unsupported <kind> claimed=<claimed value> observed=<observed value>
```

`<kind>` is `file-changed`, `gate-result`, `all-gates-passed`, `test-count` or `stopped`, the same labels as `data-model.md`. The same items go to `claims.json` and the return row (`return-row.md`). A terminal reader therefore sees each mismatch, not only the count.

A `gates.txt` file in the run directory holds the same lines (state, exit code, full command, last output line), so a reader sees each gate's command, state and exit code (FR-003) without opening the file.
