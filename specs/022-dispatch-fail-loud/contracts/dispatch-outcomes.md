# Contract: `agents-inc dispatch` outcome, reason, exit code, status line

## Exit codes (`agents-inc dispatch --slots ... --model ...` and `--resume`)

| Exit | Meaning | outcome | reason |
|---|---|---|---|
| 0 | clean | green or unverified | none, `no-gates`, `gates-skipped-broker` |
| 1 | red | red | any reason not listed below, incl. `launch-failed`, `snapshot-tampered`, `snapshot-error`, `timeout` |
| 2 | usage | red or none | child usage error (unchanged, `dispatch.py:742-743`) or bad arguments |
| 3 | refused before launch | refused-* | `refused-gates`, `refused-bash-allow`, `refused-render`, `refused-lint`, `refused-scope` (now also for globs) |
| 69 | connectivity block | red | `blocked` |
| 75 | quota pause | red | `quota-paused` |

Precedence when several apply: quota-paused, blocked, rc-nonzero/timeout, fan-out reasons, report-noncompliant, snapshot-tampered, snapshot-error, snapshot-not-clean, gate reasons.

`--wait` (unchanged behaviour, docstring fixed): 0 found, 10 needs-lead, 124 timeout, 2 bad request id or non-positive timeout.

## Status line grammar

```text
dispatch <run-id> <model> rc=<int> report=<COMPLIANT|NON-COMPLIANT:[...]|none> snapshot=<clean|CHANGED:<paths>|ERROR:rc=<n>|TAMPERED|none> outcome=<green|red|unverified>[ reason=<reason>][ detail=<screened-no-spaces>] out=<path>/stdout.md
```

- `detail` appears only for red with reason rc-nonzero, quota-paused, blocked, timeout or launch-failed, or when stdout is empty; at most 200 bytes after `screen_text`; whitespace replaced by `_`.
- `snapshot=TAMPERED` appears when the run-dir `snapshot.json` differs from the trusted record (reason `snapshot-tampered`).
- Launch-failed line (no child ran, so no report and no verify): `dispatch <run-id> <model> rc=-1 report=none snapshot=none outcome=red reason=launch-failed detail=<d> out=<run-dir>/stdout.md`. `stdout.md` is written empty.
- `tests/test_dispatch_cli.py:21-22` `STATUS_RE` gains `none` for report and snapshot, `TAMPERED` for snapshot, and the optional `detail=` field.

## Broker result (`<id>.result.json`)

Unchanged keys. The broker maps any child exit outside `REQ_STATUS` to 1 (`dispatch.py:1244`), so a quota or blocked child yields status `red` and `dispatch_exit_code` 1, never 69 or 75. The Lead tells the causes apart by `reason` (`quota-paused`, `blocked`, `timeout`, `launch-failed`). `status_line` carries the detail field.
