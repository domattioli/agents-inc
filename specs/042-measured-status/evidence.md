<!-- provenance: author=domattioli model=claude-fable-5-2 effort=medium date=2026-11-15 skill=speckit-specify repo=agents-inc session=b437620e -->
# Evidence for spec 042

Source: review of 2026-11-15. Four read-only scouts extracted 294 pain rows from 113 session retrospective files in `DomI/.introspect/` (11 repositories; `archive/` not read) and the 28 open agents-inc issues. One synthesis pass grouped them into 16 clusters. The counts are from that grouping and were spot-checked, not recounted.

Row ids are `repo/file prefix/date`. All dates are 2026.

## False red: sound work reported as failed

| Condition | Evidence |
|---|---|
| Gate command cannot start, exit 127, no dependencies installed | #186; domattioli.github.io/02817c7c/11-14 |
| `snapshot-not-clean` from files outside the delegate's scope | #145; #155 item h; DomI/bc9f3f00/11-12 |
| `snapshot-not-clean` from the task's own intended changes | DomI/bc9f3f00/11-12; DomI/e185f7e2/11-11 |
| Report-format fault turns a complete run red | agents-inc/90502f63/11-15 (`gate-exit-codes`); ADMESH/3a04a867/11-11 (`verified-exit-without-code`) |
| `reason=gate-missing` although three gates were supplied and two failed | domattioli.github.io/63ca3257/11-15 |
| Usage limit reported as `workers-spawned-missing` | DomI/development_44d810d/10-04 |
| Correct stop reported as red | #87 item 5 |
| No per-gate exit code in the status line | domattioli.github.io/63ca3257/11-15 |
| Rendered prompt carried a literal `<snapshot>` placeholder, six Workers could not run the verify step | agents-inc/90502f63/11-15 |

## False green: unchecked state reported as passed

| Condition | Evidence |
|---|---|
| `doctor` READY while dispatch cannot reach the model API | #112 item 2; #87 item 3 |
| `doctor` READY after a failed repair | #155 item b |
| Install stale against uncommitted source edits, not noticed | agents_Inc/8520fa10/11-14 (see D82) |
| `test -s` gate passes on an empty run | #155 item j |
| Worker without gates returns no explicit verdict | handoff 2026-11-14 open item |
| No `returned` ledger row from dispatch | #131 step B |

## Delegate claims not supported by the run

29 rows in two clusters ("agents report success without evidence", 11; "delegate output wrong or incomplete", 18). Five rows are tagged high or critical. Examples:

| Claim | Fact | Evidence |
|---|---|---|
| "638 green" | SyntaxError, 0 tests collected | Health-Wealth-Assistant/06-27T22Z/06-27 |
| Skill-draft files written | Nothing on disk | DomI/6efe4aac/11-14 |
| "completed" | Zero disk changes | MADMESHing/2026-07-/07-01 |
| Full docker suite OK | One test fails alone 5 of 5 | agents-inc/91aeecb8/11-14; #198 |
| "43 tests OK" | Output showed rule failures | DomI/development_635663f/09-17 |
| Provider credentials on a public page | Invented | Therapy_CoPi/2026-07-26/07-26 |
| "zero em-dashes", "sent" | Nine present; write was blocked | Therapy_CoPi/2026-07-26/07-26 |

Related open issue: #131 steps A, C and D.

## Refusals decided on text, or without a stated fix

| Condition | Evidence |
|---|---|
| Launch refused as credential-seeking for words in the prompt | #87 item 1; agents_Inc/8520fa10/11-14; DomI/6efe4aac/11-14 |
| Slots file refused for quoting an error that contains a settings path | #155 item i |
| Hook denies a mention that does not execute (`for`, `if`, `eval`, `bash -c`, `--help` after other commands) | #152 F1 to F4; domattioli.github.io/63ca3257/11-15; domattioli.github.io/02817c7c/11-14 |
| Hook fails open on unparsed forms | #152 B1 to B8 |
| Lint gives rule numbers only | #135 item 4; #155 items e and f |
| Undocumented rule: failure gate needs a backticked command | #87 item 4; domattioli.github.io/02817c7c/11-14 |
| Undocumented rule: no glob in `FILES_IN_SCOPE` | domattioli.github.io/63ca3257/11-15 |
| Docs point at the install tree, which a guard blocks | #172 |

## Stored records printed as fact

| Condition | Evidence |
|---|---|
| "run spec not mirrored: no home repo" printed with no explanation | #87 item 4; domattioli.github.io/63ca3257/11-15 |
| Stale-install state not marked as measured or stored | agents_Inc/8520fa10/11-14; ADMESH/3a04a867/11-11 |

## Findings that belong upstream (DomI)

To be filed under FR-033.

| Finding | Evidence |
|---|---|
| `session-resume` prints "none open" when the GitHub call failed | domattioli.github.io/63ca3257/11-15; observed again in the 2026-11-15 review session (28 issues open) |
| Scripts continue after a failed `mktemp -d` and act on the repository root | DomI/e185f7e2/11-11 (112 files committed); DomI/bc9f3f00/11-12; DomI/40af3ecb/10-28 |
| `run_introspection.sh` writes under `/` with an empty root variable | ADMESH/3a04a867/11-11; domattioli.github.io/63ca3257/11-15 |
| `protected_paths_guard` matches text (`/System` in `df`, relative delete in a protected cwd) | DomI/7d87e7ab/11-12 |
| `safe_rm.py` exits 1 after a successful delete when its log write fails | DomI/40af3ecb/10-28 |

## Not addressed

- Clusters recorded only from June to July in the cloud-rotation environment: missing container dependencies (45 rows), pin gate before branch switch (22), large tool payloads (19), most of the protected-branch push rows (15).
- Shared-checkout collisions between sessions (7 rows, #145 isolation part).
- OS sandbox access and network (#112 items 1 and 3, #114, #135 items 1 to 3).
