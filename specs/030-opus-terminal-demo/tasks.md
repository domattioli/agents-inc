<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-06 skill=speckit-implement repo=agents_Inc session=c5e2753c -->
# Tasks: Opus-orchestrated terminal demo of agents-inc

**Input**: Design documents from `specs/030-opus-terminal-demo/`
**Prerequisites**: plan.md, spec.md, data-model.md, research.md, quickstart.md (no contracts/: internal tool, plan.md "Project Structure")

**Tests**: Requested. plan.md design point 7 requires a stdlib unittest, cases (a) to (h), in `tests/test_opus_demo.py`.

**Organization**: Tasks are grouped by user story (spec.md "User Scenarios & Testing"). Story priorities: US1 P1, US2 P2, US3 P3.

## Revision 2026-11-07

The design changed after T001 to T037 ran: no relay, a `luna-pane` mod pane per delegate, the prompt passed to `claude` at launch, and a 3-beat demo of about 30 s (spec.md FR-001, FR-002, FR-009; plan.md "Revision 2026-11-07"). Checked boxes below record the original work. The tasks in this block cover the change.

- [x] T039 Cut `tools/demo/PROMPT.md` to 3 beats and shrink the build slot to `csv2json.py` only (stop cap 10, gate `test -s csv2json.py`); update `tests/test_opus_demo.py` (23 tests pass).
- [x] T040 Pass the prompt as the positional argument of `claude --model opus` in the runner.
- [x] T041 Write the `luna-pane` mod (luna and haiku panes, Codex-format and Claude-format rows) in the dev-mods folder; `claude plugin validate` passes.
- [ ] T042 Move the `luna-pane` mod into the repo under `mods/` and add a mod test.
- [ ] T043 Time one real run in a real terminal (`python3 tools/demo/opus_demo.py`) and fill `beat_seconds` in `demo.json`; the target is about 30 s (SC-002).
- [ ] T044 Re-point T024, T033 and T036 at the 3-beat demo: T033 means a haiku-built run, T036 means 3 runs each near 30 s.

## Format: `- [ ] T### [P?] [US?] Description with path`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task).
- **[Story]**: US1, US2, US3, only on user story phase tasks.
- Three files are written by this feature: `tools/demo/opus_demo.py`, `tools/demo/PROMPT.md`, `tests/test_opus_demo.py`. Tasks that touch the same file are not marked [P].

## Path Conventions

- Runner and prompt: `tools/demo/` (plan.md "Source Code").
- Test: `tests/test_opus_demo.py`, imports the runner through a `sys.path` insert, as `tests/test_governance_demo.py` does (research.md R1).
- Runtime output: `.scratch/demo-030/<stamp>/`, git-ignored, never committed (plan.md "Technical Context", Storage).

---

## Phase 1: Setup

**Source**: plan.md "Project Structure", "Technical Context"; research.md R1, R7.

**Purpose**: Create the folder layout and run the two cheap probes that decide wording in later tasks.

- [x] T001 Create the new folder `tools/demo/` with an empty module `tools/demo/opus_demo.py` (module docstring only) and an empty `tools/demo/PROMPT.md`.
- [ ] T002 [P] Probe the Homebrew install line: run `brew info asciinema agg` and record in `specs/030-opus-terminal-demo/research.md` (R7) whether both formulas exist. If either is missing, change the install line in `tools/demo/opus_demo.py` and `specs/030-opus-terminal-demo/quickstart.md` to match. This closes the `[assumed]` tag in plan.md point 1.
- [x] T003 [P] Read `tests/test_governance_demo.py` lines 1-11 and copy its `sys.path` insert and import style into a new stub `tests/test_opus_demo.py` (one empty `unittest.TestCase`, no cases yet).

---

## Phase 2: Foundational

**Source**: plan.md design point 1 (steps 1-6), data-model.md "Runner script", "Run directory", "Slots file".

**Purpose**: Runner functions that every story needs. No story can start until these exist.

**CRITICAL**: Finish this phase before Phase 3.

- [x] T004 In `tools/demo/opus_demo.py`, add the argparse entry point with flags `--dry-run`, `--no-record`, `--root <repo>` (the runner calls `os.chdir(root)` before any launch), and make `doctor_text` and `which` injectable parameters so tests can replace them. Exit codes: 0 ok, 2 doctor not READY, 3 setup error (data-model.md "Runner script").
- [x] T005 In `tools/demo/opus_demo.py`, add the doctor step: run `agents-inc doctor`, require a `READY` line, record `luna type: ready|off|unavailable` and the warnings `MOD_NOT_INSTALLED` and `WB_SANDBOX_EXCLUDE_MISSING`. When doctor is not READY, print the doctor line and exit 2 before writing anything. When `WB_SANDBOX_EXCLUDE_MISSING` shows, print the exact ask `add "agents-inc *" to sandbox.excludedCommands` (research.md R9).
- [x] T006 In `tools/demo/opus_demo.py`, add the free-key presence check from plan.md point 4: for mistral, gemini and openrouter, report `yes` when the env var is set or the key file has size 20 bytes or more, `maybe` when the file is under 20 bytes or the key may live only in `~/Projects/.env`, otherwise `no`. Use only `os.environ`, `os.path.exists` and `os.path.getsize`. Never open a key file. Print `free: mistral=<x> gemini=<x> openrouter=<x>`.
- [x] T007 In `tools/demo/opus_demo.py`, add trial setup: create `.scratch/demo-030/<UTC stamp>/trial/`, copy only `fixtures/build-test-verify/S/SPEC.md` into it, then assert that no path named `hidden` exists under `trial/` (FR-003, plan.md point 1 step 4).
- [x] T008 In `tools/demo/opus_demo.py`, add the slots writer for `slots-build.json` (model luna, or haiku when codex is absent) and `slots-review.json` (haiku). Each file carries ROLE, TASK, CONSTRAINTS, OUT_OF_SCOPE, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE, FAILURE_GATE and GATES. Build GATES run `python3 -m unittest discover -s tests` with cwd `.scratch/demo-030/<stamp>/trial`, `timeout_s` 120 and `expect_rc` 0. Review GATES run `test -s REVIEW.md` with `expect_rc` 0. STOP_RULE caps the build at 40 tool calls and the review at 15. Both slots' CONSTRAINTS forbid reading anything under `fixtures/` or `.scratch/bench-*` (data-model.md "Slots file", plan.md points 3 and 8, spec FR-003).
- [x] T009 In `tools/demo/opus_demo.py`, add the `demo.json` writer with the fields `stamp`, `doctor_ready`, `luna_type`, `codex`, `mod_installed`, `sandbox_exclude_ok`, `free`, `build_model`, `recorded`, `cast`, `gif` (data-model.md "Runner script"). Leave a `beat_seconds` map that the first real run fills in later (T021).
- [x] T010 [P] In `tools/demo/PROMPT.md`, write the template skeleton: placeholders `{TRIAL}`, `{SLOTS_BUILD}`, `{SLOTS_REVIEW}`, `{BUILD_MODEL}`, `{FREE_STATUS}`, `{BEAT6}`, plus one 14-element prompt block used only by the haiku native-beat Agent call in beat 6 (constitution P8, plan.md Constitution Check: the relay call is a courier and gets no block). Beat text comes in the story phases.

- [x] T034 (moved here from Polish, analyze U5) Add the dispatch render test to `tests/test_opus_demo.py`: write the slots in a dry run, then run `agents-inc dispatch --slots <file> --model haiku --dry-run` and expect it to render and lint them (exit 0). Skip the test with `unittest.skipUnless` when `agents-inc` is not on PATH (plan.md "Testing"). This confirms the gate schema (`expect_rc`, `timeout_s`) and the `danger` regex accept both slots files before any live run.

**Checkpoint**: Runner can check doctor, check keys, build the trial dir and write slots, `demo.json` and a bare prompt.

---

## Phase 3: User Story 1 - One scripted session shows the whole loop (Priority: P1) MVP

**Source**: spec.md User Story 1, FR-001 to FR-005, FR-007 to FR-010; plan.md design points 1 to 4 and 8; data-model.md "Demo prompt", "Cast file".

**Goal**: One runner command and one pasted prompt produce the full loop: vendor gate line, luna build through the relay, haiku review, hidden judge run by opus, free-model summary, ledger read-back with a supervisor verdict. The run is recorded as a cast with a GIF.

**Independent Test**: Run `python3 tools/demo/opus_demo.py --dry-run` and see the folder and prompt. Then do one live run on this machine: the judge exits 0 and the ledger row leaves the pending list.

### Tests for User Story 1 (written before the prompt tasks; they run against the Phase 2 runner)

- [x] T011 [US1] In `tests/test_opus_demo.py`, add case (a): `--dry-run` writes `trial/SPEC.md`, `slots-build.json` and `slots-review.json` under a temporary `--root`.
- [x] T012 [US1] In `tests/test_opus_demo.py`, add case (b): no path named `hidden` exists anywhere under the trial dir after a dry run.
- [x] T013 [US1] In `tests/test_opus_demo.py`, add case (c): both slots files carry the 8 required slots plus GATES.
- [x] T014 [US1] In `tests/test_opus_demo.py`, add case (f): an injected `doctor_text` without `READY` exits 2 and writes nothing under `.scratch/`.
- [x] T015 [US1] In `tests/test_opus_demo.py`, add case (g): the free-key check never opens a file. Patch `builtins.open` to raise, run the check, expect no error.
- [x] T016 [US1] In `tests/test_opus_demo.py`, add case (h): an injected `which` that returns `None` for `asciinema` makes the runner print `NOTE: asciinema not installed -> running without recording`.

### Implementation for User Story 1

- [x] T017 [US1] In `tools/demo/PROMPT.md`, write beats 1, 2, 3, 4, 5 and 7 as one printed plain-English line each, using the exact line shapes from plan.md point 2: `BEAT 1 routing: vendor gate: ...`, `BEAT 2 build: relay -> luna on csv2json`, `BEAT 3 review: ...`, `BEAT 4 verify: opus runs the hidden judge` plus `traps avoided: <ids>`, `BEAT 5 free model: ...`, `BEAT 7 ledger: ...`. Leave a `{BEAT6}` slot between beats 5 and 7.
- [x] T018 [US1] In `tools/demo/PROMPT.md`, write the dispatch instructions: primary path `Agent` with `subagent_type: "agents-inc:relay"` naming the model and slots path; fallback path one plain Bash call `agents-inc dispatch --slots <abs path> --model <m>` with no env prefix, `cd`, `&&` or pipe, plus the line `NOTE: relay unavailable -> plain dispatch, rows in <run dir>/events.jsonl`. Order rule: build, then review, never in parallel (plan.md point 2).
- [x] T019 [US1] In `tools/demo/PROMPT.md`, write the verification beat: opus runs `python3 fixtures/build-test-verify/S/hidden/acceptance.py <abs trial dir>` as one Bash call, reads `traps_passed` and `traps`, and names the four trap ids `no-types-empty-is-string`, `types-True-stays-string`, `select-unknown-is-error`, `ragged-row-no-partial-output`. If the judge fails while the delegate claimed PASS, opus prints the judge output verbatim and calls the demo red (plan.md point 3, spec.md Edge Cases). After each relay dispatch opus runs `grep -c -e 'hidden/' -e 'acceptance.py' <run dir>/events.jsonl <run dir>/stdout.md` and calls the run red on a hit (spec FR-003 residual limit). Opus spot-checks two REVIEW.md claims: a claim about a file (for example "tests exist") against the delegate's files in the trial dir, a claim about behaviour (for example "empty cell is a string") against the judge output, checks the beat 6 counts with its own `wc -l`, and labels the free summary "unverified, shown as-is" (spec FR-007).
- [x] T020 [US1] In `tools/demo/PROMPT.md`, write the free-model beat (one Bash call `{ printf 'Summarize this delegate report in 3 lines:\n'; cat <run dir>/stdout.md; } | bash skills/codex-bridge/scripts/mask.sh --tier cheap` (prompt on stdin, never a shell argument; mask.sh reads stdin when no prompt argument is given), fall through mistral, gemini, openrouter on `no API key` or quota, notes `NOTE: mistral skipped (<reason>) -> trying gemini` and `NOTE: no free model reachable -> beat 5 skipped`) and the ledger beat (`agents-inc ledger pending`, then `agents-inc ledger append --node-id <run_id> --verdict pass`, then `ledger pending` again, filtered to this run's ids; do this for the build run and the review run; read `outcome=` from each status line; state "verifier=opus" in the beat line). Also write the three edge-case instructions: a quota pause counts as one failed attempt, then escalate per the ladder or stop with a reason, never retry silently; more than 600 relay notices means point at `<run dir>/events.jsonl`; `snapshot-not-clean` means run `git status --porcelain`, state the cause, and re-run that dispatch once (spec.md Edge Cases). This follows plan.md "Spec conflicts" item 1, not the spec.md wording (plan.md points 2 and 4, research.md R4, R5).
- [x] T021 [US1] In `tools/demo/opus_demo.py`, add prompt rendering: read `tools/demo/PROMPT.md`, substitute the placeholders, check that no `NEEDS` marker remains, write `prompt.txt`, and print the prompt and the beat checklist (plan.md point 1 step 6, data-model.md "Demo prompt").
- [x] T022 [US1] In `tools/demo/opus_demo.py`, add recording: unless `--dry-run` or `--no-record`, run `asciinema rec <stamp>/demo.cast --command "claude --model opus"`, then `agg demo.cast demo.gif`. When asciinema is absent print `NOTE: asciinema not installed -> running without recording (brew install asciinema agg)` and run `claude --model opus` directly. When agg is absent print `NOTE: agg not installed -> cast kept, no GIF`. Record `recorded`, `cast`, `gif` in `demo.json` (FR-008, plan.md point 1).
- [x] T023 [US1] Run `python3 -m unittest tests.test_opus_demo` and fix `tools/demo/opus_demo.py` until cases (a), (b), (c), (f), (g), (h) pass.
- [ ] T024 [US1] First real run on this machine: `python3 tools/demo/opus_demo.py`, paste the prompt, run all beats. Record the real seconds per beat in `beat_seconds` in `.scratch/demo-030/<stamp>/demo.json` and compare them against the plan.md point 8 budget (target 9 min 30 s, cap 10 min). Decoy check for the leak grep: before the run, write a line `see hidden/ and acceptance.py` into `<stamp>/decoy.md` outside the trial dir, then confirm the grep over the run dirs does not count it (the pattern must match only delegate reads), and confirm `events.jsonl` has at least one row before the delegate finished. Also record whether the relay spawns dispatch outside the Bash sandbox (research.md R9 `[assumed]`) and whether the Claude Code sandbox proxy refused the free-model host (plan.md point 4 `[assumed]`). Copy any budget changes into `specs/030-opus-terminal-demo/plan.md` as a note for the next clarify pass; do not edit plan.md in this task.

**Checkpoint**: US1 works on its own. The MVP stops here.

---

## Phase 4: User Story 2 - luna as a native subagent, beside haiku (Priority: P2)

**Source**: spec.md User Story 2; plan.md design point 5; research.md R8.

**Goal**: The opus session starts the same small read-only task with a haiku subagent and with `agents-inc:luna`, in one message, and compares the two.

**Independent Test**: Both subagents finish. Opus prints one line per observable difference, or `none`.

### Tests for User Story 2

- [x] T025 [US2] In `tests/test_opus_demo.py`, add case (d): the rendered `prompt.txt` contains all 7 `BEAT` lines and the `vendor gate:` line, and keeps no unreplaced `{...}` placeholder.

### Implementation for User Story 2

- [ ] T026 [US2] Run the native-luna transcript probe (plan.md point 5 UNKNOWN). Start the two Agent calls once, then run `ls -t ~/.claude/projects/*agents_Inc*/` and look for a subagent jsonl. If one exists, grep it for `"model"` and per-step usage. Record the finding (readable or not) in `specs/030-opus-terminal-demo/research.md` R8. This is a read-only listing of `~/.claude/projects/`, with no writes.
- [x] T027 [US2] In `tools/demo/PROMPT.md`, write `{BEAT6}`: the shared read-only task "Run `wc -l {TRIAL}/SPEC.md` with Bash, Read the first 5 lines of `{TRIAL}/SPEC.md`, report the line count and the title line." Start a haiku general subagent (carrying the 14-element block) and `Agent subagent_type: "agents-inc:luna"` (plain prompt, P8 exempt) in one message. Never set the Agent `model` parameter to `luna` (constitution P7). Print one line per difference: count, title, failure prefix (`luna failed:` or `luna quota-paused:`), changed-tree line, ledger `source: native-luna`; or `none`. Add the transcript comparison only if T026 found it readable; otherwise state that beat 6 compares result text and ledger source only.
- [x] T028 [US2] In `tools/demo/opus_demo.py`, make the prompt renderer fill `{BEAT6}` from `PROMPT.md` when `luna type: ready` and codex is present.
- [x] T029 [US2] Run `python3 -m unittest tests.test_opus_demo` and confirm case (d) passes together with the earlier cases.

**Checkpoint**: US1 and US2 both work.

---

## Phase 5: User Story 3 - The demo survives a missing provider (Priority: P3)

**Source**: spec.md User Story 3, FR-006; plan.md design point 6 and "Spec conflicts" item 4; research.md R9.

**Goal**: With no `codex` on PATH, or `luna type: off|unavailable`, the runner prints `NOTE: codex absent -> haiku` and routes the build to haiku. Beat 6 shows a SKIP. Beats 1 to 5 and 7 still run.

**Independent Test**: Run the runner with `which` reporting no `codex`. Slots and prompt show haiku and a SKIP line, and exit code is 0.

### Tests for User Story 3

- [x] T030 [US3] In `tests/test_opus_demo.py`, add case (e): injected `which` returning `None` for `codex` gives the output `NOTE: codex absent -> haiku (build and review share a model)`, `build_model` haiku in `demo.json` and `slots-build.json`, and a beat 6 line starting `SKIP: luna type not offered (codex absent)` in `prompt.txt`.

### Implementation for User Story 3

- [x] T031 [US3] In `tools/demo/opus_demo.py`, add the degradation branch: `shutil.which("codex") is None`, or doctor prints `luna type: off` or `unavailable`, sets build model haiku, prints the NOTE, and sets `{BEAT6}` to `SKIP: luna type not offered (codex absent)`. When doctor warns `MOD_NOT_INSTALLED`, set `{BEAT6}` to a SKIP too and print a note that beats 2 and 3 use the plain-dispatch fallback.
- [x] T032 [US3] In `tools/demo/PROMPT.md`, add the instruction that the review stays a separate dispatch (fresh session) when build and review share a model. The runner, not the session, prints the `NOTE:` line (plan.md "Spec conflicts" item 4, spec US3 scenario 1).
- [ ] T033 [US3] Run `python3 -m unittest tests.test_opus_demo` and confirm case (e) passes. Then do one live run with `codex` hidden from PATH (use a throwaway shim directory under `.scratch/demo-030/` that keeps `claude` and `agents-inc` visible but not `codex`) and confirm beats 1 to 5 and 7 pass and beat 6 shows `SKIP` (spec.md US3 Independent Test, SC-005).

**Checkpoint**: All three stories work.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Source**: plan.md "Testing" stretch test, point 8; spec.md SC-001 to SC-005; quickstart.md.

- [x] T035 [P] Walk `specs/030-opus-terminal-demo/quickstart.md` against the finished runner: each command, each flag, each path. Fix `tools/demo/opus_demo.py` or note drift for the next clarify pass.
- [ ] T036 Repeat the live run twice more (3 runs in total, spec.md SC-002 and SC-003): each run under 10 minutes, the judge exits 0 in at least 2 of 3. Append each run's `beat_seconds` to its `demo.json` under `.scratch/demo-030/<stamp>/`. Confirm `$0` API spend (SC-004): no paid fallback was used.
- [ ] T037 Run the full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`. All tests pass, including `tests/test_opus_demo.py`.
- [ ] T038 Move specs to DomI: run `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T002 and T003 can run beside T001's follow-up.
- **Foundational (Phase 2)**: needs T001 and T003. Blocks all stories.
- **US1 (Phase 3)**: needs Phase 2. Tests T011 to T016 before implementation T017 to T022.
- **US2 (Phase 4)**: needs Phase 2 and T017 to T022 (the prompt renderer and `PROMPT.md` skeleton from US1). T026 needs a working session from T024.
- **US3 (Phase 5)**: needs Phase 2 and T021. Independent of US2 except that both edit `tools/demo/PROMPT.md` and `tools/demo/opus_demo.py`, so do them one after the other.
- **Polish (Phase 6)**: needs all stories.
- **T038 (Move specs to DomI)**: depends on every other task. Nothing runs after it, because it moves `.specify/` and `specs/` into DomI `specs/consumers/agents_Inc/`.

### Within Each Story

- Write each test task before its implementation task and run it once to see it fail.
- `PROMPT.md` tasks run in order (same file). `opus_demo.py` tasks run in order (same file). `tests/test_opus_demo.py` tasks run in order (same file).

### Parallel Opportunities

- T002 and T003 (different files and tools).
- T010 (`PROMPT.md`) beside T004 to T009 (`opus_demo.py`).
- In US1, the `PROMPT.md` tasks T017 to T020 can run beside the test tasks T011 to T016, because they edit different files.
- T034 in Phase 2 (dispatch render test); T035 in Polish.

### Parallel Example: Phase 2

```text
Stream A (tools/demo/opus_demo.py): T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T034
Stream B (tools/demo/PROMPT.md):    T010
```

### Parallel Example: User Story 1

```text
Stream A (tests/test_opus_demo.py):  T011 -> T012 -> T013 -> T014 -> T015 -> T016
Stream B (tools/demo/PROMPT.md):     T017 -> T018 -> T019 -> T020
Join:                                T021 -> T022 -> T023 -> T024
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup, then Phase 2 Foundational.
2. Phase 3: US1 through T024.
3. Stop and validate: dry run prints the prompt, one live run passes the judge and clears the ledger row.
4. Show the cast if it is good enough.

### Incremental Delivery

1. Add US2 (native luna beat) after the MVP run proves timing.
2. Add US3 (degradation) last, since it needs the runner to be stable.
3. Polish, three-run check, full suite, move specs.

---

## Notes

- **Spec conflicts resolved in favor of plan.md** (plan.md "Spec conflicts"):
  - Ledger content (conflict 1, resolved in spec.md US1 scenario 5 on 2026-11-06): T020 follows plan.md: `ledger pending`, then `ledger append --node-id <run_id> --verdict pass`, then `ledger pending` again, with `outcome=` read from the status line and opus named as verifier in the beat line.
  - Free-model key location (conflict 2): T006 checks env vars and wrapper key files, and reports `maybe` for a key that may live only in `~/Projects/.env`. The runner never reads a value.
  - Trial dir location (conflict 3): T007 uses `.scratch/demo-030/<stamp>/trial/` inside the repo, because the relay pins `--cwd` to the session cwd.
  - Story 3 review independence (conflict 4): T030 and T031 print the NOTE that build and review share a model.
  - Recording (conflict 5): T022 wraps `claude --model opus` in `asciinema rec`, so recording stops when the operator exits claude.
- **Beat count**: revised 2026-11-07 to three beats (spec.md FR-002). The seven-beat text in tasks T017 to T027 is historic.
- **Probes in the implement phase**: T002 (`brew info asciinema agg`), T026 (native-luna transcript), T024 (first real run, beat timings, sandbox and proxy assumptions).
- **Live runs need operator action**: T024, T033 and T036 need a human in a Claude Code terminal with Codex logged in. They cannot run from a headless delegate.
- **Out of scope** (plan.md "Scope left out"): manim video, tmux, the M fixture, new agents-inc features, free-model live rows, relay rows (dropped 2026-11-07), `checklist.md`.
- Commit after each task or logical group is the operator's call; this tasks.md does not commit anything.
