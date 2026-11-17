<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Data model: Measured status (spec 042)

All records are JSON written with the standard library. Existing fields keep their names and meanings; new fields are added beside them. Every new field is optional for a reader, so a run.json from before this spec still loads.

## Verdict

One check result. Used by gate rows, the scope check, the claim check and doctor items.

| Field | Type | Rule |
|---|---|---|
| `state` | `passed` \| `failed` \| `not-checked` | Exactly one. Never derived from a delegate report. |
| `reason` | string from contracts/verdict-reason-codes.md | Required when `state` is not `passed`. |
| `evidence` | object | `command` (string), `rc` (int or null), `last_line` (string, screened, at most 200 bytes). |

## Gate result

Extends the existing row built in `_run_gates` (`agents_inc/install/dispatch.py:1313-1314`): `argv`, `cwd`, `expect_rc`, `rc`, `excerpt`, `network`, `error`.

| New field | Rule |
|---|---|
| `id` | `g<n>`, assigned by the dispatcher from the order of the gates in the slots file; immutable; unique per run even when two gates share an argv (FR-012d). |
| `state` | `passed` when `rc == expect_rc`; `failed` when `rc != expect_rc`, on timeout or on refusal (a command that started and exited 127 is `failed`); `not-checked` when the command could not start. "Could not start" is: any `OSError` raised before the gate process starts (including creating the gate temp directory or profile), or a `shutil.which` miss. |
| `reason` | `gate-failed`, `gate-timeout`, `gate-refused` (the post-run re-screen refused the gate: danger list, credential path, or a cwd outside the working directory), `gate-not-runnable`, `gates-not-run-tampered` (gate row reason only: the pinned scripts were tampered, so no gate was run; the run outcome is then red `snapshot-tampered`, step 1 below). `gate-wrote` and `gate-cwd-outside` are not gate reasons: `gate-wrote` is retired (an outside change is `scope-foreign-change`, see FR-005 and step 4 below), and a cwd refusal is `gate-refused`. |
| `last_line` | Last non-empty line of `excerpt` (edge case: tells "command not found" from a child's exit 127). |

## Scope check result

| Field | Rule |
|---|---|
| `state` | `passed` (no change outside FILES_IN_SCOPE), `not-checked` (changes outside scope, or snapshot skipped), `failed` (snapshot tampered or error). |
| `in_scope` | Paths inside FILES_IN_SCOPE whose content hash after the run differs from the hash in the pre-launch snapshot. Each has `attribution: unknown` (FR-006). A final `git status --porcelain` alone is not evidence of a change in this run, because it cannot tell a file that was already dirty before launch from a file that changed during the run. |
| `foreign` | Changed paths outside FILES_IN_SCOPE (every changed path is outside when FILES_IN_SCOPE is empty), `attribution: unknown`, listed as "changed by another party or by the delegate; not attributed". A change first seen after the gates is also `foreign`; timing alone never attributes a write to a gate. |

Scope fields `unreadable` and `unbaselined` list allowed paths without evidence; scope `state` is `not-checked` when any allowed path is unreadable, and a `file-changed` claim on such a path is `not-checked` (claim check result field `not_checked`). Scope and claim evidence come from the structured result of the final verify; lists are never round-tripped through the comma-joined display token. Declared git-ignored scope paths are captured at baseline. Detection: the snapshot verify prints `CHANGED <path>` for each in-scope path whose hash differs from the snapshot and `OUTSIDE <path>` for each changed path outside the scope. `_snapshot_verify` in `agents_inc/install/dispatch.py` reads both prefixes and builds `in_scope` and `foreign` from them; an `OUTSIDE` line is never read as a verify error.

## Run outcome

Derived, never written by the delegate. Order of derivation (first match wins):

1. Launch-level reds, unchanged: `quota-paused`, `blocked`, `timeout`, `rc-nonzero`, fan-out reasons (an empty reply of a Claude or Codex run ends `workers-spawned-missing`), `no-report` (the report is missing, empty or only whitespace; operator ruling 2026-11-15), `snapshot-tampered`, `snapshot-error`. This holds with or without gates.
2. Any gate `failed` → `red` with that gate's reason (`gate-refused` first, then `gate-timeout`, `gate-failed`). A failed gate beats every `unverified` reason below.
3. Delegate declared a stop → `unverified delegate-stopped`.
4. Scope check `not-checked` → `unverified scope-foreign-change` or `snapshot-skipped`.
5. Skipped snapshot → `unverified snapshot-skipped`; an unreadable allowed path in the final scope evidence → `unverified scope-unreadable`; broker child → `unverified gates-skipped-broker`; no gates → `unverified no-gates` (ranks assigned inside this derivation, below a declared stop and a foreign change).
6. Every gate `not-checked`, or some `not-checked` and none failed → `unverified gate-not-runnable`.
7. Retired. A report with content that breaks the format never turns a run red: with no gates it is `unverified no-gates` (step 5), with gates the gate result decides and the fault prints as a `report-fault` line.
8. At least one gate ran and all passed → `green` (reason `report-format-advisory` when the report had a format miss).

Every run also carries a three-state `state` field (FR-001), derived from the outcome word and written to `run.json` and the return row:

| Outcome word | `state` |
|---|---|
| `green` | `passed` |
| `red`, `snapshot-failed` | `failed` |
| `unverified` | `not-checked` |
| `refused-*`, `credential-seeking` | `not-checked` (nothing was run) |
| `cancelled`, `dry-run` | `not-checked` |

State transitions: a resume turn recomputes the outcome from scratch; nothing is sticky except the ledger rows already written.

## Claim and claim check result

| Field | Rule |
|---|---|
| `kind` | `file-changed`, `gate-result`, `all-gates-passed`, `test-count`, `stopped`, `claims-block` (reason `multiple-claims-blocks`). A `gate-result` and a `test-count` name a gate id. |
| `claimed` | Value from the report block. |
| `observed` | Value from the run (changed paths from the baseline-to-final hash comparison, `gate_results`, count parsed from gate `excerpt`). |
| `supported` | `true`, `false`, or `null` when the run holds no evidence either way. |
| `weak` | Optional flag (advisory) set for a `test-count` of 0 or an `all-gates-passed` claim over a gate with zero collected tests (FR-012f). |
| `omitted` | Run-level list of gate ids with no `gate-result` claim (FR-012c). |

Run-level field `claims`: `{"state": "checked"|"not-checked", "unsupported": <int>, "items": [...], "omitted": [...], "weak": [...]}`. `not-checked` when the report block is missing or unparsable (FR-014). `items` holds one entry per unsupported claim: `{kind, claimed, observed}`. Advisory in this release: it never changes the run outcome.

## Return row

See contracts/return-row.md. Extends `host_ledger.dispatch_return_row` (`agents_inc/host_ledger.py:158-171`).

## Refusal and Rule

| Entity | Fields |
|---|---|
| Rule | `id` (kebab-case, stable), `screen` (`render`, `lint`, `scope`, `grants`, `credential`, `capability`, `non-git`, `broker`, `hook`, `install`), `summary` (one line), `example_fix` (one line). |
| Refusal | `rule` (Rule id), `value` (the offending text, screened, at most 200 bytes), `fix` (the rule's `example_fix` or a next command). |

The rule registry is `agents_inc/install/rules.py`, a dict literal. QUICKREF holds one line per rule; a test compares them.

## doctor item

| Field | Rule |
|---|---|
| `name` | `install`, `release`, `claude-cli`, `codex-cli`, `host-wiring`, `skills`, `dispatch-path`, `repair`, `install-match`, `source-uncommitted`, and the existing warning sources. |
| `required` | True for items a dispatch needs. |
| `tested` | `now`, `record` (read from a stored file, with its age), or `not-tested`. |
| `result` | `pass`, `fail`, `could-not-test`, `warn`. |

READY when every `required` item has `tested == now` and `result == pass`.

## Replay case

`fixtures/replay/screens.jsonl`, one JSON object per line: `id`, `screen` (`hook` or `credential`), `input` (command string or slots object), `expected` (`allow` or `deny`; the credential screen's "refused" is `deny`), `source` (issue item or retrospective row id), `kind` (`false-deny`, `bypass`, `regression`). Optional `current` (`allow` or `deny`): the decision of the code on 2026-11-15, set for the measured cases of T077 and T078; for a `regression` case `current` equals `expected`.
