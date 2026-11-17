<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Feature Specification: Measured status

**Feature Branch**: `042-measured-status`
**Created**: 2026-11-15
**Status**: Clarified
**Input**: Operator request: "a speckit pipeline addressing as much of this as possible that is within scope for thread 1 and its similarities", after a review of session retrospectives and open issues.

Evidence for the counts below is in `evidence.md` in this directory.

## Problem

agents-inc exists to check delegated work. Today much of the status it prints is asserted, not measured. A check that could not run is reported as a pass or as a failure, and the reader cannot tell which reports rest on a measurement.

A review on 2026-11-15 read 294 pain rows from session retrospectives in 11 repositories and the 28 open agents-inc issues. Four groups of rows share this one cause:

- **Verdicts that are not true.** A dispatch ends red although the work is sound, because the gate command could not start, a neighbour's file changed, or the report had a format fault. A check ends green although nothing was checked: `doctor` prints READY when a dispatch cannot reach the model, and a gate passes on an empty run.
- **Delegate claims taken on trust.** A delegate reports "tests pass" when no test was collected, or "files written" when no file is on disk. The supervisor finds this only by repeating the work by hand.
- **Refusals decided on words.** A launch is refused as credential-seeking because the prompt contains the word "credentials". A harmless command is denied because it mentions a guarded name. The same matching also lets some real cases through. The refusal does not name the rule or the fix.
- **Stored records printed as fact.** A surface prints an old record as the current state when the live check failed or did not run.

The result is the same in each group: the operator and the supervisor cannot rely on a status line, so they re-run checks by hand.

## Scope

In scope: status and refusals that agents-inc itself produces. This covers dispatch outcomes, gate results, the delegate report check, `doctor`, the dispatch hook, the launch broker's screens, the slots lint, the status line, and the ledger rows that record a return.

Out of scope:

- Guards and session tools owned by DomI (`branch_guard`, `protected_paths_guard`, `commit_msg_guard`, `session-resume`). Findings for these go upstream as issues.
- What the OS sandbox permits: network rules, file access, read paths (#112 items 1 and 3, #114, #135 items 1 to 3).
- Isolation between sessions that share one checkout. This spec only stops one session's files from turning another session's run red.
- Free-model and delegate-pane features (#141, #178, #190, #192, #193, #194, #197), the Windows port (#138), and pains recorded only in the June to July cloud-rotation environment.

## Clarifications

- Operator ruling, 2026-11-15: "Missing/empty = red, malformed = unverified." A missing or empty report is failed (red `no-report`, exit 1), with or without gates. A malformed report with content is `unverified no-gates` when there are no gates; with gates the gate result decides and the format fault prints as a `report-fault` line.

- sol cross-vendor review 2026-11-16, 12 findings fixed (claims fences are not control text; final-verify evidence as lists; unreadable and unbaselined paths are not-checked; every attempted run or resume ends with a return row; malformed claims blocks and size caps; actual exit code recorded; skipped-snapshot and broker reasons ranked in the first-match order).

### Session 2026-11-15

Answers given by the operator.

- Q: How does a dispatch that ends "not checked" exit? → A: A new outcome word, `unverified`, with its own non-zero exit code that differs from the code for a failed run.
- Q: What happens in the first release when a delegate claim has no support in the run? → A: Warn first, enforce later. The mismatch is listed and the run outcome does not change. Enforcement is left to a later spec.
- Q: Does dispatch gain a setup step for missing dependencies (#186)? → A: No. Dispatch reports the gate as not runnable. A setup slot can be a later spec.
- Plan-phase finding, recorded here so the answers above read correctly: the word `unverified` already exists and exits 0 today (D58), for a run with no gates and for a read-only run in a non-git directory. The first answer therefore moves those existing runs from exit 0 to the new code, and amends D58.
- Q: Does this spec reopen D82 (stale-install check follows git history)? → A: No. D82 stays. `doctor` and dispatch add a warning when the source checkout has uncommitted changes under installed paths.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A verdict says what was measured (Priority: P1)

A supervisor dispatches a task with gates. When the run returns, the status tells the supervisor one of three things for the run and for each gate: the check ran and passed, the check ran and failed, or the check did not run. For a failure or a check that did not run, the status names the command, its exit code and the reason.

**Why this priority**: This is the largest group of evidence and it is the product's main claim. Every false red costs a manual re-run. Every false green lets unchecked work through.

**Independent Test**: Run a dispatch in a working directory where the gate command is not installed. The run reports "not checked" for that gate with the command and exit code, and does not report the delegate's work as failed.

**Acceptance Scenarios**:

1. **Given** a gate whose command cannot start (exit 127, command not found), **When** the run returns, **Then** the gate is reported as not checked with the command and exit code, and the run outcome is not "failed".
2. **Given** three gates where two ran and failed, **When** the run returns, **Then** the status names the two failing commands with their exit codes and does not report a gate as missing.
3. **Given** a run where files outside the delegate's declared scope changed during the run, **When** the run returns, **Then** those files are listed as changed outside the scope with attribution unknown, and the run ends `unverified`, not failed and not passed.
4. **Given** a run where every changed file is inside the declared file scope, **When** the run returns, **Then** the scope check passes.
5. **Given** a run that ended because the provider's usage limit was reached, **When** the run returns, **Then** the reason names the usage limit, and no other cause is reported in its place.
6. **Given** a delegate that stopped correctly at a declared stop condition, **When** the run returns, **Then** the outcome is `unverified` with a reason that names the stop, not a failure.
7. **Given** a delegate report with a format fault and gates that all passed, **When** the run returns, **Then** the format fault is reported on its own line and the gate results stay visible as passed.
8. **Given** a gate that can pass without exercising the work (for example a file-not-empty test on a file that existed before the run), **When** the slots are checked before launch, **Then** the supervisor is warned that the gate does not measure the work.

---

### User Story 2 - A delegate's claims are checked against the run (Priority: P1)

A delegate ends its work with a report. The harness compares what the report claims with what the run shows: which files changed on disk, which gates ran, and what they returned. A claim with no matching evidence is marked as unsupported. The supervisor reads one list of mismatches and does not have to repeat the work to find them.

**Why this priority**: These rows appear at the same rate in both periods, so the cause is not the environment. Five of the 29 rows are tagged high or critical, including invented provider credentials on a public page. Each was caught only because a supervisor re-ran the check by hand.

**Independent Test**: Give the check a report that claims a file was written and tests passed, with a run in which no file changed and no test ran. The check lists both claims as unsupported.

**Acceptance Scenarios**:

1. **Given** a report that names a file as written, **When** that file did not change during the run, **Then** the claim is listed as unsupported.
2. **Given** a report that states a test count, **When** no gate produced that count, **Then** the claim is listed as unsupported.
3. **Given** a report that states all gates passed, **When** a gate failed or did not run, **Then** the mismatch is listed, and the run outcome follows the gate results, not the report.
4. **Given** a run with no gates, **When** the run returns, **Then** the outcome states that nothing was checked. It is not reported as passed.
5. **Given** a dispatch that returns in any state, **When** the ledger is read afterwards, **Then** it holds a row for the return with the outcome, the gate results and a link to the dispatch row.
6. **Given** a report whose claims all match the run, **When** the check runs, **Then** it lists no mismatch and adds no warning.

---

### User Story 3 - doctor does not print READY for a path it did not test (Priority: P2)

An operator runs `agents-inc doctor` before delegating. Each line of the result says whether that item was tested now, and what the result was. The overall word READY appears only when every item needed for a dispatch was tested and passed. If an item could not be tested, the result says so and names it.

**Why this priority**: A false READY sends the operator into a failing dispatch. It appears in three open issues and several retrospectives. It ranks below stories 1 and 2 because it affects the start of a session, not every run.

**Independent Test**: Run `doctor` in an environment where the model provider cannot be reached. The result does not print READY, and it names the unreachable path.

**Acceptance Scenarios**:

1. **Given** an environment in which a dispatch cannot reach the model provider, **When** `doctor` runs, **Then** the overall result is not READY and the line for that path says it failed or could not be tested.
2. **Given** a repair that failed part-way, **When** `doctor` runs next, **Then** the result reports the failed repair and is not READY.
3. **Given** an installed copy that differs from the source checkout it was installed from, **When** `doctor` runs, **Then** the result states the difference and whether it was measured or read from a stored record.
4. **Given** a source checkout with uncommitted changes under installed paths, **When** `doctor` or a dispatch runs, **Then** a warning says the source has uncommitted edits that the install was not compared against, and the dispatch is not blocked.
5. **Given** every item tested and passed, **When** `doctor` runs, **Then** the result is READY as it is today.

---

### User Story 4 - A refusal names the rule, the value and the fix (Priority: P2)

A supervisor or delegate has a launch, a command or a slots file refused. The message names the rule that fired, the exact value that triggered it, and what to change. A supervisor who has never seen the rule can correct the input on the next attempt without opening the source.

**Why this priority**: Opaque refusals are the most common single complaint about dispatch in the November retrospectives. The fix is small and independent of the rest.

**Independent Test**: Submit one slots file per known rule, each breaking exactly that rule. Every refusal message contains the rule name, the offending value and a corrected example.

**Acceptance Scenarios**:

1. **Given** a slots file whose failure gate has no command in backticks, **When** it is checked, **Then** the message names that rule, shows the offending text and shows a correct form.
2. **Given** a slots file with a glob pattern in its file scope, **When** it is checked, **Then** the message says exact paths are required and shows the pattern that was refused.
3. **Given** a slots file with a classification value outside the allowed set, **When** it is checked, **Then** the message lists the allowed values.
4. **Given** a shell call in which a dispatch command is combined with other commands, **When** the hook denies it, **Then** the message says the dispatch command must be the whole call.
5. **Given** a slots file that is missing a required slot, **When** it is checked, **Then** the message names the slot and says how to print a template for it without reading the install directory.
6. **Given** any refusal by an agents-inc screen, **When** the message is printed, **Then** it never shows only a rule number.

---

### User Story 5 - A refusal follows what the action would do (Priority: P3)

A supervisor dispatches a read-only research task whose prompt mentions the word "credentials". The launch is not refused for that word. A launch is refused as credential-seeking when the paths, tools or commands it requests would reach secret-bearing files. In the other direction, a command that really runs a dispatch is not allowed through because it is wrapped in an unusual shell form.

**Why this priority**: The false refusals block legitimate work, and the cases that pass wrongly are a safety gap. It ranks last because the changes touch security screens and need the most care and review.

**Independent Test**: Replay a fixed set of recorded cases through the screens. The set holds launches and commands that were wrongly refused and ones that wrongly passed. Each case gets the expected decision.

**Acceptance Scenarios**:

1. **Given** a launch whose prompt contains the words "credentials" or "secrets" and whose requested paths and tools reach no secret-bearing file, **When** it is screened, **Then** it is allowed.
2. **Given** a slots file that quotes an error message containing a settings path as text, **When** it is screened, **Then** it is allowed.
3. **Given** a launch that requests read access to a secret-bearing path, **When** it is screened, **Then** it is refused, whatever words the prompt uses.
4. **Given** a shell call that mentions a dispatch command inside a string or loop that does not execute it, **When** the hook checks it, **Then** it is allowed.
5. **Given** a shell call that executes a dispatch command through a form the hook cannot parse, **When** the hook checks it, **Then** it is denied, and the message says the form could not be parsed.

---

### Edge Cases

- A gate command starts and is then killed by a timeout. This is a failure of the gate with the reason "timed out", not "not checked".
- A gate exits 127 because the command it runs calls a missing program, while the gate command itself started. This is a gate that started and exited 127, so it is `failed`, not `not checked` (see FR-002 for what "could not start" means). The status reports the exit code and the last line of output so the supervisor can tell the two apart.
- Every gate is "not checked". The run outcome is "not checked", never "passed".
- The delegate report is missing or empty. The run is red `no-report` (a Claude or Codex run ends `workers-spawned-missing` first) and still shows the gate results. A report with content that breaks the format is never red by itself.
- A file inside the delegate's scope is changed by another session during the run. The harness cannot tell who changed it. The scope check passes, and the claim check lists the file if the delegate's report does not claim it.
- `doctor` runs with no network. Items that need the network are reported as "could not be tested", and the overall result is not READY.
- A stored record is newer than the last live check. The surface prints the record with its age and the mark "not verified now".
- A screen cannot decide whether a launch reaches a secret-bearing path (the conditions are listed in FR-026). It refuses and says it could not decide.

## Requirements *(mandatory)*

### Functional Requirements

**Verdicts**

- **FR-001**: Every run outcome and every gate result MUST carry exactly one of three states: passed, failed, or not checked. No surface may print a not-checked result as passed or as failed. The outcome word for a not-checked run is `unverified`, the word dispatch already uses for a run with no gates.
- **FR-001a**: A dispatch whose outcome is `unverified` MUST exit with a non-zero code that differs from the code for a failed run. The new code is 4 (`EXIT_UNVERIFIED`). The existing codes for passed and failed runs MUST NOT change. Runs that end `unverified` today with exit 0 move to the new code; this amends D58.
- **FR-002**: A gate whose command could not start MUST be reported as not checked, with the command, the exit code (none when no process ran) and a reason that says the command could not run. "Could not start" means that the harness failed to create the gate process: any `OSError` was raised before the gate process started (the program was not found or could not be executed, or the harness could not create the gate temp directory or profile), or a `shutil.which` missed. A gate that did start and then exited 127, for example because the program it calls is missing, is not "could not start": it is `failed`, and the status shows its exit code and last output line. This amends D58, which rules such a gate red. The D72 refusal before launch, for a gate whose program is absent from the machine, stays as it is.
- **FR-003**: The status for a returned run MUST list each gate with its command, its state and its exit code. When any gate failed or was not checked, the status MUST name those gates first.
- **FR-004**: A run outcome MUST be "passed" only when at least one gate ran and every gate passed. A run with no gates, or with every gate not checked, MUST be reported as not checked. When several conditions hold, the run outcome follows this precedence, first match wins: (1) a launch-level failure (quota pause, blocked, timeout, delegate exit, fan-out fault, tampered or unverifiable snapshot) is failed; (2) any failed gate makes the run failed, and a failed gate beats every not-checked reason below, including a declared stop and an outside-scope change; (3) a declared stop (FR-008); (4) an outside-scope change or a skipped snapshot (FR-005); (5) no gates, or a broker child that skips gates; (6) a gate that could not start, with none failed; (7) a report format fault with no gate evidence, which is the only case in which a format fault alone makes the run failed (FR-009); (8) at least one gate ran and every gate passed, which is passed. A format fault never outranks steps (2) to (6). The same order is in `data-model.md`.
- **FR-005**: The scope check MUST separate changed files inside the declared file scope from changed files outside it. A change inside the declared scope MUST NOT fail the scope check. A change outside the declared scope MUST be listed, MUST NOT make the run outcome failed, and MUST NOT allow the run outcome to be passed: such a run ends `unverified` with a reason that names the outside change, because the harness cannot tell whether the delegate or another party made it. A change is detected by comparing the content hash of each file, and the status of each file in `git status`, between a snapshot taken before launch and a check after the run (and after the gates); a path counts as changed only when it differs from that snapshot, so a file that was already modified before launch and did not change during the run is not a change. A changed path is inside the scope only when it equals a path in FILES_IN_SCOPE (or lies under a listed directory); every other changed path is outside. When FILES_IN_SCOPE is empty, every changed path is outside the scope. A change seen after the gates ran is not attributed to a gate: the time of a change alone is not evidence of who made it, so it is an outside change with attribution unknown, and the harness has no record from which it could name a gate as the author.
- **FR-006**: The harness MUST NOT assert who made a change that it cannot attribute. It MUST report the attribution of an outside-scope change as unknown.
- **FR-007**: When a run ends because of a provider usage limit, the reason MUST name the usage limit. The harness MUST detect this before it reports any other reason. The plan phase found this behaviour present; the work is a regression test.
- **FR-008**: A delegate that stops at a declared stop condition MUST produce the outcome `unverified` with a reason that names the stop, and MUST keep any gate results already collected. A failed gate outranks the stop (FR-004 precedence).
- **FR-009**: A format fault in the delegate report MUST be reported as its own finding. It MUST NOT replace or hide the gate results.
- **FR-010**: Before launch, the slots check MUST warn when a gate can pass without the run having done anything, at minimum for a gate that only tests that a file exists or is not empty.
- **FR-011**: A reason code MUST describe the condition that occurred. The reason for "a gate failed" and the reason for "no gate was supplied" MUST be different codes.

**Delegate claims**

- **FR-012**: The harness MUST compare the delegate report with the run and list each claim that the run does not support. In this release an unsupported claim is a warning: it MUST be listed in the status and in the return row (each unsupported claim with the claimed and the observed value, not only a count), and it MUST NOT change the run outcome. A delegate that truthfully reports the recorded result of a failed gate is supported, not unsupported. At minimum it MUST check: files claimed written against files changed on disk; a claimed gate result against the recorded gate result; a claimed test count against gate output.
- **FR-012a**: A report MUST hold exactly one `claims` block. Two or more blocks make the claim check result `unsupported` with reason `multiple-claims-blocks`, and no claim in any block is compared. There is no "last block wins" rule. This amends the "last block wins" clause of `contracts/claims-block.md`.
- **FR-012b**: A `test-count` claim MUST name the gate id it comes from. The claimed count is compared only with the output of that gate. It is never matched against an integer in the output of another gate.
- **FR-012c**: The block MUST carry a `gate-result` claim for every gate id of the run. A gate with no claim is reported `omitted` in the claim check output and in the return row. This is advisory, like the rest of the claim check.
- **FR-012d**: Gate ids are assigned by the dispatcher from the order of the gates in the slots file (`g1`, `g2`, ...) and are immutable for the run. Two gates with the same argv are two distinct ids. A gate claim is matched by id, never by argv.
- **FR-012e**: A `stopped` claim MUST carry an identifier that matches the run's declared STOP RULE text or id. A stop reason that matches none is `unsupported`.
- **FR-012f**: A `test-count` claim of 0, or an `all-gates-passed` claim over a gate whose output shows zero tests collected, MUST be flagged `weak` (advisory). The check reads "zero tests collected" from the named gate's excerpt only.
- **FR-013**: The delegate report MUST end with a short machine-readable block that states the files changed and the gate results the delegate claims. The format of the block is `contracts/claims-block.md`. The prompt contract MUST tell the delegate how to write it.
- **FR-014**: A missing or unreadable machine-readable block MUST be reported as "claims not checked". It MUST NOT be reported as passed.
- **FR-015**: Every dispatch that returns, in any state, MUST write a ledger row for the return. The row MUST hold the outcome state, the reason, the per-gate results and a link to the dispatch row.
- **FR-016**: The claim check MUST run without a model call. It MUST use only the run directory, the working tree and the gate output.

**Not catchable by the claim check** (red-team 2026-11-15). A deterministic comparison of a report with the run cannot catch these four attacks. They stay with the reviewer (a worker never accepts its own output):

- A cosmetic edit (for example a changed comment) counted as a file change. Hash inequality proves different bytes, not a completed feature.
- A gate that tests nothing meaningful. Argv and exit code are matched; whether the gate measures the work is not (FR-010 and FR-012f warn only for the file-exists and zero-collection forms).
- An in-scope test or helper rewritten so the gate passes. The harness records a genuine run of dishonest code.
- False prose outside the claims block. Only the structured claims and the "all gates passed" phrase are checked.

**doctor**

- **FR-017**: Each `doctor` item MUST state whether it was tested in this run and its result. An item that was not tested MUST say so.
- **FR-018**: `doctor` MUST print READY only when every item required for a dispatch was tested in this run and passed.
- **FR-019**: `doctor` MUST include a test of the dispatch path to the model provider. The test MUST cost no paid usage. When it cannot run, the item MUST be reported as could not be tested.
- **FR-020**: `doctor` MUST report a repair that did not finish, and MUST NOT print READY while that state remains. The plan phase found this behaviour present; the work is a regression test and the per-item line format.
- **FR-021**: When `doctor` or dispatch reports whether the installed copy matches its source, it MUST say whether the comparison was made now or read from a stored record.
- **FR-021a**: When the source checkout has uncommitted changes under paths that the install copies, `doctor` and dispatch MUST print a warning that the source has uncommitted edits and the install was not compared against them. The warning MUST NOT block a dispatch. The D82 rule for the stale-install check MUST NOT change.

**Refusals**

- **FR-022**: Every refusal and lint failure produced by an agents-inc screen MUST state the rule name in words, the value that triggered it, and one corrected example or the next command to run.
- **FR-023**: Every rule that can refuse a slots file or a shell call MUST appear in the quick reference with one line each. The universe of rules is the rule registry (`agents_inc/install/rules.py`, listed in `contracts/refusal-format.md`). A test MUST fail when a rule exists in the code and is absent from the quick reference.
- **FR-024**: A message that tells the reader to consult a template or reference MUST name a command that prints it. It MUST NOT name a path inside the install directory.
- **FR-025**: The credential screen MUST decide from what the launch requests (paths, tools, commands), not from words in free-text slots. Text that quotes a path or a keyword MUST NOT cause a refusal by itself. The plan phase found the screen already matches locations and not bare words; the screen changes only for replay cases that still fail, and a recorded refusal that the replay set cannot reproduce is reported as not caused by agents-inc. A recorded refusal is "not caused by agents-inc" when its recorded input, fed to the agents-inc screen alone (no other guard, hook or tool in front of it), is allowed. That replay is the test, and it is allowed as a replay case.
- **FR-025a**: The credential screen MUST read every string value in every slot, including strings nested in lists or objects, and MUST refuse a value that requests a secret-bearing path in any slot. This covers the exemption slots `OUT_OF_SCOPE` and `CONSTRAINTS`: a clause there that asks for access to a secret-bearing path (for example "Do not stop before reading ~/.codex/auth.json") is refused, while a clause that only denies access stays allowed. A bare `.env`, a bare `~/.ssh` (directory level) and a variable-prefixed secret file (`$D/auth.json`) count as secret-bearing requests; a variable path next to a secret name is also `credential-undecidable` (FR-026). A diagnostic text that quotes a settings path as an error message, with no request to read or write it, MUST be allowed (#155 item i). The screen reads prompt text only; the tool deny list and the OS sandbox are the controls that block the actual reads, and this spec does not test them.
- **FR-026**: The credential screen MUST still refuse a launch that requests access to a secret-bearing path. When it cannot decide, it MUST refuse and say that it could not decide. "Cannot decide" means that a requested path or command contains a shell expansion (a variable, a command substitution, a glob or a backtick) next to a secret-bearing name, so that the final path is not known when the screen runs.
- **FR-027**: The dispatch hook MUST allow a shell call that mentions a dispatch command without executing it, for the recorded false-deny forms.
- **FR-027a**: A comment MUST NOT make the hook deny. Suspicion comes from executable tokens, not from comment text: `source ./helpers.sh # agents-inc dispatch is documented here` is allowed.
- **FR-028**: The dispatch hook MUST deny a shell call that executes a dispatch command through a form it cannot parse, for the recorded bypass forms, and the message MUST say the form could not be parsed. "Cannot parse" means that the text contains `agents-inc` and the tokenizer raises an error, or the text holds an ANSI-C word (`$'...'`), a `${...}` subcommand, or a redirect before the command.
- **FR-028a**: A recursion error (or any parser error) in the hook MUST fail closed when the text contains `agents-inc`; today a nesting of about 1,100 `$(` fails open. The hook MUST also deny the literal interpreter form `python3 -c "import os; os.system('agents-inc dispatch ...')"`. A text hook cannot close every interpreter route; only this literal form is covered, and the DECISIONS entry states the limit.
- **FR-029**: The recorded false-deny and bypass cases MUST be kept as a fixed replay set that runs in the test suite. The recorded cases are named by id: #152 F1 to F4 and B1 to B8, #87 item 1, and #155 item i. The replay set holds at least those cases, plus the rows in `evidence.md` and the existing passing cases as regressions.

**Unverified records**

- **FR-029a**: The replay set MUST also hold the cases measured on 2026-11-15, each with its current decision and its required decision: tasks T077 and T078 list them. Cases that already have the correct decision stay as regressions.
- **FR-030**: Any agents-inc surface that prints a stored value as the current state MUST mark it "not verified now" when the live check failed or did not run, and MUST show the age of the record. The surfaces are: `doctor` output, the session-start hook text, the dispatch status notes (for example the install-match line and the run-record mirror note), and the status line (`scripts/statusline.sh`). The mark is the exact text `not verified now`. The age is written `age <n><unit>` with one unit, `s`, `m`, `h` or `d`, the largest whole unit (for example `age 3h`).
- **FR-031**: A message that reports a skipped side effect (for example a run record that was not mirrored) MUST say what was skipped, whether any record was lost, and whether the reader has to act.

**Governance**

- **FR-032**: Each change to a binding ruling MUST be recorded as a new entry in `docs/DECISIONS.md` that names the rulings it amends, before the change ships.
- **FR-033**: The defect findings in this review that belong to DomI-owned tools MUST be filed as upstream issues, and the list of those issues MUST be recorded in this feature directory.

### Key Entities

- **Verdict**: the result of one check. Holds a state (passed, failed, not checked), a reason code, and the evidence for it (command, exit code, last output line).
- **Gate result**: the verdict of one gate command in one run.
- **Run outcome**: the verdict of a whole dispatch, derived from its gate results, the scope check and the claim check.
- **Claim**: one statement in a delegate report that can be compared with the run (a file changed, a gate result, a test count).
- **Claim check result**: for each claim, supported or unsupported, with the evidence compared.
- **Return row**: the ledger record of a returned dispatch, linked to its dispatch row.
- **Refusal**: a decision by a screen not to proceed. Holds the rule name, the triggering value and the fix.
- **Rule**: one condition under which a screen refuses. Has a name, a one-line description and a corrected example.
- **Replay case**: a recorded input to a screen with its expected decision.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the false-red conditions named in `evidence.md` (gate cannot start, neighbour file changed, declared change flagged, format fault, usage limit, correct stop, failed gate reported as missing) is reproduced by a test, and none of them produces a "failed" outcome for sound work.
- **SC-002**: Each of the false-green conditions named in `evidence.md` (no gates, empty-run gate, unreachable provider, failed repair) is reproduced by a test. None of them produces "passed" or READY, except that the empty-run gate is allowed to run and MUST produce the FR-010 warning before launch.
- **SC-003**: In a seeded set of at least 10 delegate reports with false claims, the claim check lists every false claim as a warning, and in a set of at least 10 true reports it lists none.
- **SC-004**: After any returned dispatch, a reader finds the outcome, the reason and every gate result in one place without re-running a gate.
- **SC-005**: For every refusal rule, a reader who has not seen the rule corrects the input on the next attempt using only the refusal message. This is checked by a test that every message contains a rule name, the offending value and a corrected example.
- **SC-006**: Every recorded false-deny case is allowed and every recorded bypass case is denied in the replay set, with no change to the decision for the existing passing cases.
- **SC-007**: No agents-inc surface prints a stored value as current without a "not verified now" mark when the live check did not run. This is checked by a test per surface, for each surface listed in FR-030.
- **SC-008**: The full test suite passes, and the change adds no paid usage to any dispatch or `doctor` run.
- **SC-009**: Each open issue this spec addresses is either closed by the work or has a comment that lists which of its items remain.

## Assumptions

- The reader of a status line is the supervisor that dispatched the run, or the operator. Both read it in a terminal.
- Existing callers and tests read the present outcome words and exit codes. This spec adds one exit code and new reason codes. It keeps the outcome words and the codes for passed and failed runs.
- The claim check warns in this release. Making an unsupported claim fail the run is left to a later spec, once the rate of false warnings is known.
- Missing dependencies in the working directory are reported, not installed. A setup step for dispatch is out of scope.
- D82 ruled that the stale-install check follows the source's git history, not file contents. This spec keeps that ruling. It adds the "measured now or stored" statement and a warning for uncommitted source edits.
- The dispatch slots file already has a schema under D70. This spec builds the return row and the report block on it and does not redefine it.
- The work uses the Python standard library only, costs $0 in incremental spend, and leaves `WORKERBEES_GOVERNANCE` off by default.
- A worker never accepts its own output. The claim check is a deterministic check and does not replace the reviewer.
- Changes to the credential screen and the dispatch hook are reviewed by a reviewer from a different vendor where the project rules require it for irreversible or canon changes.
- The 101 pain rows from the June to July cloud-rotation environment are not addressed, because no record of that environment exists after 2026-07-27.
