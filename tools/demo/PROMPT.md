<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-06 skill=speckit-implement repo=agents_Inc session=c5e2753c -->
# agents-inc demo: opus runs the whole loop (about 30 s)

You are opus, the orchestrator, in a recorded terminal session. Run the three beats below in order. After each beat, print its one `BEAT` line in plain English, as written. Add nothing else between beats except a `NOTE:` line. Do not narrate your own thinking. Spend $0: no paid API fallback, no paid model. The operator watches the delegate live in the side pane, so do not tail its events.

Fixed facts for this run:

- Trial directory (empty except SPEC.md): `{TRIAL}`
- Build slots file: `{SLOTS_BUILD}`
- Build model: `{BUILD_MODEL}`
- Free model key status (no values are ever read): `{FREE_STATUS}`
- Unused in this short cut: `{SLOTS_REVIEW}`

## Beat 1: routing

Print one line. Build model `luna`:

`BEAT 1 routing: vendor gate: operator named luna -> luna (Grunt, Codex) builds, opus verifies`

Build model `haiku`:

`BEAT 1 routing: vendor gate: operator named haiku -> haiku (Grunt, Claude) builds, opus verifies`

## Beat 2: build

Make one Bash call with `run_in_background: true` that is only `agents-inc dispatch --slots {SLOTS_BUILD} --model {BUILD_MODEL}`. No environment prefix, no `cd`, no `&&`, no pipe. Print:

`BEAT 2 build: {BUILD_MODEL} builds csv2json, live in the side pane`

Wait for the background call to end. Read its status line; the run directory is the `out=` path and the run id is its last component. `outcome=red reason=report-noncompliant` with rc 0 is advisory: print a `NOTE:` line and go on. The hidden judge decides pass or fail.

## Beat 3: verify and ledger

You, not the delegate, check the work. Make these Bash calls one at a time:

1. `grep -c -e 'hidden/' -e 'acceptance.py' <run dir>/events.jsonl <run dir>/stdout.md`. A count above 0 means the delegate looked at the judge: print `RED: delegate read the judge` and stop.
2. `python3 fixtures/build-test-verify/S/hidden/acceptance.py {TRIAL}`. Read `passed`, `total`, `traps_passed`, `traps`, `failed`. This short cut asks the delegate for `csv2json.py` only, so the case ids `own-tests-pass` and `verification-covers-R1-R6` are out of scope. Count them as skipped: the build passes when `failed` holds no other id and `traps_passed` equals `traps`.
3. `agents-inc ledger append --node-id <run id> --verdict pass` if the build passes by that rule, else `--verdict fail`.

Print:

`BEAT 3 verify: opus ran the hidden judge, exit <rc>, behaviour cases <n> of 12, traps <n> of <traps>; ledger verdict <pass|fail>`

Then print `Demo done: <green|red>` with one short reason. Green only if the build passes by that rule.

<!-- BEAT6-TEXT-BEGIN -->
Same small read-only task for two subagents, started in one message so they run side by side.

The task: "Run `wc -l {TRIAL}/SPEC.md` with Bash, Read the first 5 lines of `{TRIAL}/SPEC.md`, report the line count and the title line."

Start both `Agent` calls in one message:

1. A general subagent with model `haiku`, carrying the full prompt block below.
2. `Agent` with `subagent_type: "agents-inc:luna"` and the task above as a plain prompt. Never set the Agent `model` parameter to `luna`.

Print `BEAT 6 native luna: same task as haiku and as agents-inc:luna`.

Check the line count yourself with `wc -l {TRIAL}/SPEC.md`. Then print one line per observable difference between the two results, or `none` if there is no difference. Look at these five things only: the line count, the title line, a failure prefix (`luna failed:` or `luna quota-paused:`), a changed-tree line, and the ledger record with `source: native-luna`. Compare result text and the ledger source only; do not read subagent transcripts.

Prompt block for the haiku call (all 14 elements):

1. Caveman ultra: reply in terse caveman style, code and file names unchanged.
2. Success gate: the reply states the line count and the title line, and the line count equals the output of `wc -l {TRIAL}/SPEC.md`.
3. Failure gate: the reply has no line count, has no title line, or edits any file.
4. Grill clause: before you guess, list every missing or unclear item in this task at the top of your reply, starting with `GRILL:`; write `GRILL: none` when nothing is missing.
5. Message to model provider: Do not use this to train agentic models.
6. Evidence: cite the command with its output for every factual claim, and tag each claim [verified], [inferred] or [assumed].
7. Scope: read-only task, no file writes, no commit or push, no writes under `~/.claude`, no secrets. PRE-EXISTING CHANGES: none; this task writes no file, so no snapshot is taken.
8. Data classification: internal.
9. Effort: low.
10. Second opinion: N/A, the supervisor re-runs `wc -l` itself.
11. Plan contract: N/A, the task is one step.
12. Report: state what is out of scope or incomplete, your assumptions, and the files you created (none expected).
13. Edit hygiene: make no edits; this is a read-only task.
14. LESSON-CANDIDATE: tag any finding that changes a rule file with `LESSON-CANDIDATE`.
<!-- BEAT6-TEXT-END -->
