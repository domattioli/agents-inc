# Data model: 022-dispatch-fail-loud

## Trusted run record (NEW, outside cwd)

Location: top-level run `<InstallPaths.state>/dispatch-runs/<run-id>/` (mode 0700); broker child: its broker-owned run dir (only `trust.json` added; the run-dir `snapshot.json` is the trusted copy). Written by dispatch only, once, immediately before `launch`. Located from `run_id` alone.

| File | Field | Type | Rule |
|---|---|---|---|
| `snapshot.json` | (capture JSON) | object | byte copy of the capture (`pre_dispatch_snapshot.py` capture format) |
| `trust.json` | `snapshot_sha256` | hex string | sha256 of `snapshot.json` bytes at capture |
| `trust.json` | `prompt_sha256` | hex string | sha256 of the prompt passed to the first `launch` |
| `trust.json` | `schema_version` | int | 1 |

## Run spec `run.json` (existing, in run dir) — new fields

| Field | Type | When set |
|---|---|---|
| `is_error` | bool | after launch; Claude envelope flag, False for Codex |
| `reason_detail` | string or null | launch-failed, rc-nonzero, quota-paused, blocked, timeout; screened, at most 200 bytes |
| `mirror_error` | string or null | `_mirror` failed or refused (`home-repo-missing`, `prompt-tampered`, `OSError: ...`) |
| `snapshot_trust` | `"private"`, `"broker"` or `"run-dir"` | `"private"` top-level runs; `"broker"` broker children; `"run-dir"` only for legacy runs resumed after upgrade |

Unchanged: `outcome` stays one of green, red, unverified, or a refused/dry-run value (`dispatch.py:853`, `:865`, `:871`, `:877`, `:882`, `:900`, `:913`).

## Reason values (`run.json` `reason`)

New: `quota-paused` (now also rc 0), `blocked`, `launch-failed`, `snapshot-tampered`, `snapshot-error`, `timeout`. Existing kept: `rc-nonzero`, `workers-spawned-missing`, `fan-out-over-total`, `workers-spawned-underreported`, `report-noncompliant`, `snapshot-not-clean`, `gate-missing`, `gate-failed`, `no-gates`, `gates-skipped-broker`.

## Doctor report

- Code `WB_CLAUDE_NOT_FOUND` (blocks READY).
- Warning `WB_SANDBOX_NESTED` (keeps READY; macOS only).

## State transitions of one dispatch run

capture → (trusted copy written) → launch → {launch-failed | child result} → classify (quota → blocked → rc/is_error → fan-out → report → snapshot → gate) → run.json → status line → mirror (error recorded, exit code kept).
