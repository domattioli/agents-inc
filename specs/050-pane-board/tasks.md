# Tasks: Pane Board

**Input**: `specs/050-pane-board/` (spec.md, plan.md, research.md, data-model.md, quickstart.md)
**Prerequisites**: plan.md and spec.md. No contracts directory exists.

**Tests**: The spec requires tests (FR-041): one test per golden scene, each compared to an exact expected Board. Scene tasks sit in the phase that owns them.

**Organization**: Tasks follow the four plan phases, which map to the four user stories (US1 Mechanical Board, US2 CoS items by markers, US3 Teams across sessions, US4 Secretary). Each phase opens with its spikes. FR-040 (ship in four phases) is covered by this structure as a whole.

## Format: `[ID] [P?] [Story] [FR ids] Description with path`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task).
- Spike results are recorded in `specs/050-pane-board/research.md` under the spike's heading, with host build, surface, observable result and the implementation path the result supports.

## Path notes

Plan.md names these paths and no others. Board code goes in the directory `mods/agents-inc/hooks/`. Plan.md does not name individual new source or test files there, so each task below says "a new file in `mods/agents-inc/hooks/`" and the implementer picks the file name when the task starts. Existing files to adapt or reference:

- `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts` (host declarations)
- `mods/agents-inc/.claude-plugin/plugin.json`
- `mods/agents-inc/hooks/hooks.json`
- `mods/agents-inc/hooks/native/loop.ts` (reference for hook composition, transcript access, hand-back)
- `mods/delegate-pane/hooks/register.tsx`, `poll.ts`, `controls.tsx`, `pane.test.tsx`
- `docs/DECISIONS.md`, `CONTEXT.md`

---

## Phase 1: Mechanical Board (US1, Priority P1, MVP)

**Goal**: The current session's Board shows the two mechanical NEEDS YOU cases, TROUBLE and WORKING, with no model calls.

**Independent Test**: Golden scenes 2, 3 and 4 pass against exact expected Boards, plus the focused width, dismissal, active/quiet and focus cases.

### Spikes (run first, each blocks the tasks named)

- [ ] T001 [P] [US1] [FR-014] Run spike S3 (operator hold versus idle): probe an operator approval, an operator input hold, an idle delegate and a background-work wait; compare status, any question or approval payload and how the signal clears; read quota pause and its reset time from dispatch state. Use `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts` as the reference and record the result in `specs/050-pane-board/research.md`. Blocks T007, T017, T018.
- [ ] T002 [P] [US1] [FR-020] Run spike S4 (current step and refresh cadence): probe deterministic action summaries from native tool events with a sampled transcript read as fallback, using `mods/delegate-pane/hooks/poll.ts` and `mods/agents-inc/hooks/native/loop.ts` as references. Measure reads and update delay as a delegate goes from active to quiet. Record the result in `specs/050-pane-board/research.md`. Blocks T010.
- [ ] T003 [P] [US1] [FR-022, FR-035] Run spike S6 (key focus and automatic opening): test Board arrow keys, selection actions and Escape against a non-empty chat draft, manual reopening, and automatic opening without focus, at a wide and a narrow terminal. Record the result and any affected surface and width in `specs/050-pane-board/research.md`. Blocks T012 and T014.

### Decision record and terms

- [x] T004 [P] [US1] [FR-044, FR-013] Add the FR-044 entry to `docs/DECISIONS.md`: CoS Items are published through chat markers, not a tool call, because a posting tool would cost an extra model round trip per post. This entry must exist before Phase 1 ships. This edits canon, so a different-vendor reviewer checks it per D46 and the result is recorded.
- [x] T005 [P] [US1] [FR-039] Verify that `CONTEXT.md` already defines Board, Item and Secretary (plan.md cites `CONTEXT.md` lines 90 to 92). If any term is missing or inconsistent with spec.md, add or correct it in `CONTEXT.md`. This edits canon, so a different-vendor reviewer checks any change per D46 and the result is recorded.

### Implementation

- [x] T006 [US1] [FR-001, FR-004, FR-038] Create the collection layer in a new file in `mods/agents-inc/hooks/`: normalize native agent and dispatch run activity for the current session into one list keyed by Team and stable delegate identity, adapting the coordinated poll in `mods/delegate-pane/hooks/poll.ts`. Hide finished delegates with no outstanding trouble.
- [x] T007 [US1] [FR-014] In the collection layer from T006, classify the two mechanical NEEDS YOU cases: a host operator hold (using the positive signal from T001, leaving unsupported waits unclassified) and a quota pause carrying its reset time. A Worker's Question stays with its Lead and does not create an Item.
- [x] T008 [US1] [FR-018] In the collection layer from T006, classify TROUBLE: failed check, died, timed out, `killed` (kept until dismissed), lost run (unfinished dispatch run with nothing new for five minutes, cleared by a new event or outcome), and review owed (`needs-review` or `unverified`).
- [x] T009 [US1] [FR-019] Add session-scoped dismissal: one dismiss action serves rows and Items, a dismissed trouble episode stays hidden on later reads of that episode, a later distinct episode can surface again, and nothing persists beyond the session. New file in `mods/agents-inc/hooks/`.
- [x] T010 [US1] [FR-020, FR-021] Build WORKING rows in a new file in `mods/agents-inc/hooks/`: state glyph, model alias, task text and the latest short step from the T002 method, with the state note `quiet 3m` as fallback, no model call, no tokens, elapsed time, short id, rung word or handle letter.
- [x] T011 [US1] [FR-002, FR-003, FR-005, FR-030, FR-031, FR-032, FR-033, FR-036, FR-037] Build the deterministic Board renderer in a new file in `mods/agents-inc/hooks/`: section order NEEDS YOU, FYI, TROUBLE, WORKING; flat rows most urgent first; empty sections hidden; one blank line between sections and two before folded Teams; two-space indent; dim capital labels with counts on NEEDS YOU, TROUBLE and WORKING and none on FYI; amber for NEEDS YOU and red for TROUBLE only; glyphs `●`, `◌`, `▲`, `!`, `▸`, `·`. Render none of the map, stations, roles line, feed, tree, new-agent form, done list, tokens or animation.
- [x] T012 [US1] [FR-022, FR-023] Add selection by identity, arrow-key movement active only while Board owns focus, and the single footer line listing the keys valid for the selection. Add the open transcript, stop and dismiss actions, adapting `mods/delegate-pane/hooks/controls.tsx`. Reply is wired in Phase 2. Depends on T003.
- [x] T013 [US1] [FR-048] Add width handling in the renderer: at 30 columns or more keep the glyph and alias and truncate task text and step; below 30 columns show section counts only (including the FYI count when present).
- [x] T014 [US1] [FR-035, FR-034, FR-029] Register Board in `mods/agents-inc/hooks/` and `mods/agents-inc/hooks/hooks.json` (and `mods/agents-inc/.claude-plugin/plugin.json` if registration requires it). Open without taking focus on the first delegate or first NEEDS YOU Item, stay closed with nothing to show, add the slash command that reopens it, use no toast or status line cell, and add no launch or settings UI to the pane. Depends on T003 and T011; the old registration is turned off by T050.
- [x] T015 [US1] [FR-045] Confirm Board is named `Board` in all user-visible registration text and lives in the existing `agents-inc` mod, not a new mod. Files: `mods/agents-inc/.claude-plugin/plugin.json`, `mods/agents-inc/hooks/hooks.json`.
- [x] T050 [US1] [FR-045] Turn off the old delegate-pane registration in `mods/delegate-pane/hooks/register.tsx` so only Board registers the pane. Depends on T014.

### Golden scene tests (Phase 1)

- [x] T016 [P] [US1] [FR-041, FR-018, FR-019, FR-023] Golden scene 2 (dead delegate): fixed `luna` fixture with a died event and a two-minute clock advance; assert TROUBLE count 1 and the exact row `  ▲ luna    scan docs     died 2m ago`; assert transcript action, dismiss, and absence after refresh; repeat with `killed`. New test file in `mods/agents-inc/hooks/`.
- [x] T017 [P] [US1] [FR-041, FR-014] Golden scene 3 (operator hold): `sonnet` delegate held with question `run migration?`; assert NEEDS YOU count 1 and the exact line `  1 sonnet waits: run migration?`; assert idle, background-wait and Worker Question cases create no Item. New test file in `mods/agents-inc/hooks/`.
- [x] T018 [P] [US1] [FR-041, FR-014, FR-034, FR-035] Golden scene 4 (quota pause): `haiku` paused with reset `14:20`, Board starting closed; assert it opens without taking focus, NEEDS YOU count 1 and the exact line `  1 haiku paused: quota, resets 14:20`, and no model call or signal outside Board. New test file in `mods/agents-inc/hooks/`.
- [x] T019 [P] [US1] [FR-041, FR-004, FR-005, FR-020, FR-021, FR-022, FR-048] Focused cases: width above and below 30 columns, active versus quiet delegates, two delegates with one alias differing by task text, empty sections hidden, and selection staying on the same target across a refresh. New test file in `mods/agents-inc/hooks/`.
- [x] T020 [US1] [FR-040, FR-022, FR-035] Qualify Phase 1 against host evidence: confirm in `specs/050-pane-board/research.md` that the operator-hold signal, step extraction and focus behavior from T001 to T003 match what shipped, and record any limitation.

**Checkpoint**: Phase 1 works alone and is demoable as the MVP.

---

## Phase 2: CoS Items from markers (US2, Priority P2)

**Goal**: The CoS's marker lines in its final message become Items, with a reply sub-pane for the current session.

**Independent Test**: Golden scene 1 passes, plus repeat delivery and failed-send cases, with zero extra model calls to post an Item.

### Spike

- [x] T021 [P] [US2] [FR-024] Run spike S5 (reply region and local chat path): compare an inline region below Board with a separate reply pane for Enter to open, Escape to close and focus return; confirm how an operator-confirmed chat submission can be tied to its Item and that a draft, cancel or refusal keeps the Item open. Use `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts` as the reference and record the result in `specs/050-pane-board/research.md`. Blocks T026.
- [x] T022 [P] [US2] [FR-007] Probe that `turn.complete` exposes the main loop's final visible answer with a stable identity and does not disturb native hand-back; check main, delegate and interrupted turns. Reference `mods/agents-inc/hooks/native/loop.ts` and `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts`; record in `specs/050-pane-board/research.md`. Blocks T023.

### Implementation

- [x] T023 [US2] [FR-007, FR-013, FR-043] Add the marker parser in a new file in `mods/agents-inc/hooks/`, registered in `mods/agents-inc/hooks/hooks.json`: read the `answer` on `turn.complete` for successful main-loop turns only, match complete lines of the form `[board:<section>] <text> | <option> | <option>` accept only the sections `needs-you`, `fyi` and `done` (ignore `[board:trouble]` and `[board:working]` silently), treat the whole marker text as the title, parse the closing marker `[board:done] <same text as the Item title>`, keep the full marker text as source, and make no model call. Depends on T022.
- [x] T024 [US2] [FR-006, FR-016] Publish Items from markers: `needs-you` and `fyi` become Items, `trouble` and `working` markers are ignored silently so mechanical rows stay in control, no HANDLED section exists, duplicates are suppressed by session, turn id and source line, and FYI shows only the newest three with older ones aged out. New file in `mods/agents-inc/hooks/`.
- [x] T025 [US2] [FR-015, FR-043] Add NEEDS YOU lifetime: an Item stays until answered from Board, dismissed, or closed by the CoS. Implement CoS closure with the parsed `[board:done] <same text as the Item title>` marker from T023, removing the matching Item. Depends on T023. File: a new file in `mods/agents-inc/hooks/`.
- [x] T026 [US2] [FR-017, FR-024, FR-025] Build the reply sub-pane using the region chosen in T021: Enter opens, Escape closes; show title, the full source chat turn as context, source, age, quick keys, a reply box and the last messages sent to that target. Quick keys are the marker options when present, else `1 yes   2 no   3 hold`; free text always available. Show one-line question-only rows on the Board. Extend `mods/delegate-pane/hooks/controls.tsx` adaptation from T012. Depends on T021.
- [x] T027 [US2] [FR-023, FR-026] Wire the reply action for the current session's CoS through the operator's own chat submission flow (not a direct plugin send), keeping the Item open on draft, cancel or refusal and closing it only after the operator submits. New file in `mods/agents-inc/hooks/`.
- [x] T028 [US2] [FR-011, FR-013] Verify that mechanical rows and marker posting issue no model call: add a trace assertion in the Phase 2 test file in `mods/agents-inc/hooks/`.

### Golden scene test (Phase 2)

- [x] T029 [US2] [FR-041, FR-006, FR-007, FR-013, FR-024, FR-025] Golden scene 1 (CoS question from a marker): complete a turn with `[board:needs-you] Merge parser fix to main?`; assert the exact selected line `▸ 1 Merge parser fix to main?`; assert the sub-pane contents and Escape; submit a test reply and assert the Item leaves; repeat with explicit marker options replacing the default keys; assert zero extra model calls. New test file in `mods/agents-inc/hooks/`.
- [x] T030 [P] [US2] [FR-007, FR-015, FR-016] Edge-case tests: repeat delivery of one turn creates no duplicate, a failed send keeps the Item open, FYI age-out after three, and a marker on a non-main or interrupted turn is ignored. New test file in `mods/agents-inc/hooks/`.

**Checkpoint**: Phases 1 and 2 work together. Cross-session replies wait for Phase 3.

---

## Phase 3: Teams across sessions (US3, Priority P3)

**Goal**: Every pane shows every local Team, and the operator can message any Board target in any Team.

**Independent Test**: Golden scene 6 passes, two live sessions show the same Team data, and cross-session delivery and refusal behave as recorded.

### Prerequisite and spikes

- [ ] T031 [US3] [FR-047, FR-028] Write the Memo amendment to D54 and D46 in `docs/DECISIONS.md` before any other Phase 3 work: allow only the one-way checkpoint Memo accepted for Board, keep a Worker's Question going to its Lead, and preserve governed verification and resume limits. D63 (Team definition) is already accepted. D46 requires a different-vendor reviewer for this canon edit; record the review result.
- [ ] T032 [P] [US3] [FR-001, FR-038] Run spike S1 (shared state and session ownership): with two independent Claude processes, probe plugin store visibility, concurrent writes, restart and stale-session behavior; test a session-owned atomically replaced summary file if the store is unsuitable; confirm how each local harness supplies explicit session, delegate and Sync ownership, including two Teams in one checkout. Reference `mods/agents-inc/.claude-plugin/types/claude-code/index.d.ts`; record in `specs/050-pane-board/research.md`. Blocks T034.
- [ ] T033 [P] [US3] [FR-026, FR-027, FR-028, FR-047] Run spike S2 (cross-session message provenance and Worker Memos), after T031: probe a live and an idle recipient by stable id; compare sender acknowledgement, receiving envelope and what the recipient does; record queue acceptance and reading separately; test Memo delivery to native Claude Workers at a checkpoint and to Codex Workers on the next governed resume; verify the recipient Chief's FYI for another Team's delegate. Record in `specs/050-pane-board/research.md`. Blocks T036 and T037.

### Implementation

- [ ] T034 [US3] [FR-001, FR-038] Implement shared Team data per the S1 result (plugin store or session-owned summary file) in a new file in `mods/agents-inc/hooks/`, sharing only what each pane needs and identifying a Team by harness and session, not display name or working directory.
- [ ] T035 [US3] [FR-001, FR-030, FR-033] Render folded Teams: every other Team as one count line with `!` when it holds a needs-you Item, two blank lines before them, no "other sessions" label, and the open Team always the pane's own. Extend the renderer from T011.
- [ ] T036 [US3] [FR-026, FR-027, FR-028, FR-047] Route Board replies by stable target identity (Team line to that Team's CoS, Item to its source, delegate row to its Team's delegate), preserve plugin provenance, keep a Worker Memo pending until an authorized checkpoint or next resume, and send the other Team's Chief an FYI when its delegate is messaged. Extend the controls from T026 and T027. Depends on T031 and T033.
- [ ] T037 [US3] [FR-035] Extend first-event detection so the first delegate or first NEEDS YOU Item in any Team opens Board without focus. File: the registration from T014 in `mods/agents-inc/hooks/`. Depends on T014 and T034.
- [ ] T038 [US3] [FR-042] Prepare the one-week operator observation: record how often the operator still switches sessions, with no target count, starting when cross-session counts are available. Record the start date and method in `specs/050-pane-board/research.md`.

### Golden scene test (Phase 3)

- [ ] T039 [US3] [FR-041, FR-001, FR-030, FR-033, FR-038] Golden scene 6 (folded Teams): `ainc2` with one NEEDS YOU Item and three working delegates, `quadmesh` with two working; assert two blank lines after the open Team and the exact lines `! ainc2       1 needs you · 3 working` and `● quadmesh    2 working`; assert two sessions show the same Team data, each opening its own Team. New test file in `mods/agents-inc/hooks/`.
- [ ] T040 [P] [US3] [FR-026, FR-027, FR-028] Delivery and refusal tests: a message to another Team's delegate produces an FYI for that Team's CoS, a Memo to a running dispatch Worker stays pending until checkpoint or resume, and a refused send keeps its target and Item open. New test file in `mods/agents-inc/hooks/`.

**Checkpoint**: Phases 1 to 3 work together.

---

## Phase 4: Optional Secretary (US4, Priority P4)

**Goal**: An optional extractor turns unmarked CoS turns into validated Items.

**Independent Test**: Golden scene 5 passes, and the extraction bench meets the threshold confirmed for the chosen route.

### Bench and FR-046 gate (run first)

- [ ] T041 [P] [US4] [FR-008, FR-009, FR-010] Run the extraction bench: build a fixed set of unmarked CoS turns with expected Items, no-action turns and bad quotes; record accuracy, false positives, latency and cost in `specs/050-pane-board/research.md`. Confirm the acceptance threshold before any backend is enabled. Keep a model-agnostic local route and an explicit none option.
- [ ] T042 [P] [US4] [FR-046] Run the FR-046 free-tier limits check: from authoritative current sources, confirm the free API's limits, eligible use and data-use terms, including the unverified Mistral free-tier limits and third-party training opt-in claim. Record the evidence in `specs/050-pane-board/research.md`. A missing or inconclusive result keeps that route ungranted, and no paid fallback is allowed.

### Implementation

- [ ] T043 [US4] [FR-008] Add the install choice local, eligible free API, or none, with the local route model-agnostic and the free API selectable only after T042 passes. Files: `mods/agents-inc/.claude-plugin/plugin.json` and a new file in `mods/agents-inc/hooks/`.
- [ ] T044 [US4] [FR-009, FR-011] Implement the extraction call in a new file in `mods/agents-inc/hooks/`: one fixed JSON input envelope (CoS final message plus ids) and fixed JSON output (kind, title, verbatim quote, options); run only on CoS turns with no markers; send nothing mechanical.
- [ ] T045 [US4] [FR-010] Validate output in code: check shape and drop any Item whose quote is not literally contained in the source message; tag accepted Items `auto`. Render the dim `auto` tag in the renderer from T011.
- [ ] T046 [US4] [FR-012] Render `CoS turn unread, open chat` when extraction fails, is disabled or the choice is none; render nothing new when extraction succeeds with no Items.

### Golden scene test (Phase 4)

- [ ] T047 [US4] [FR-041, FR-008, FR-010, FR-011, FR-012] Golden scene 5 (Secretary extraction): unmarked turn containing `Merge parser fix to main?` with a deterministic Secretary response; assert NEEDS YOU count 1 and the exact line `  1 Merge parser fix to main?  auto`; repeat with an absent quote (Item dropped), a failed Secretary and the none setting (both show `CoS turn unread, open chat`); feed a mechanical death event and assert the Secretary gets no input. New test file in `mods/agents-inc/hooks/`.

**Checkpoint**: All four phases complete.

---

## Final phase: Close-out

- [ ] T048 [FR-041, FR-040] Run all six golden scene tests together, plus the focused test files, from the repository's mod test setup, and fix any regression across phases.
- [ ] T049 [FR-042] After the one-week observation from T038 ends, record the session-switch counts in `specs/050-pane-board/research.md`.
- [ ] T051 Move specs to DomI: run `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. Depends on every other task; nothing may run after it.

---

## Dependencies and execution order

- Phase 1 spikes T001 to T003 run in parallel, then T006 to T015 and T050 in order of dependency, then tests T016 to T019 (parallel), then T020.
- Phase 2 needs Phase 1 complete. T021 and T022 run in parallel first; T023 needs T022; T026 needs T021.
- Phase 3 needs Phase 2 complete. T031 first, then T032 and T033 in parallel (T033 after T031), then T034 to T038.
- Phase 4 needs Phase 2 complete only (the renderer comes from T011); T041 and T042 run in parallel first. Phase 4 may be skipped without affecting Phases 1 to 3.
- T049 waits for the observation week and T051 is last.

## Parallel examples

```text
Phase 1 spikes T001 to T003 and record tasks T004, T005: all parallel
Phase 1 scene tests: T016, T017, T018, T019
Phase 3 spikes: T032, T033 (after T031)
Phase 4 gates: T041, T042
```

## Implementation strategy

1. Ship Phase 1 alone as the MVP: mechanical Board for the current session, validated by scenes 2 to 4.
2. Add Phase 2 (markers and replies), then Phase 3 (Teams, after the D54/D46 amendment), then Phase 4 only if the bench and FR-046 check pass.
3. Each phase is accepted by deterministic checks first (the golden scenes), then a reviewer, per the project rules. Live spike results stay marked unverified until recorded.
