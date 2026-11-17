<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-12 skill=speckit-tasks repo=agents-inc session=f8c024a9-ee62-4516-9889-edd03b1d02b1 -->
# Tasks: Mission map view in the delegate pane

**Input**: [spec.md](./spec.md), [plan.md](./plan.md)
**Tests**: required (spec SC-004). Commands: `claude plugin test mods/delegate-pane`; repo gate `python3 -m unittest discover -s tests -p 'test_*.py'`.
**Writer route**: operator decision 2026-11-12: try `agents-inc dispatch --model sonnet`; on refusal, native sonnet subagents.

## Phase 1: Setup

- [x] T001 Work in place on the current branch `fix/0.6.4-low-hanging` (operator decision 2026-11-12: no worktree, no new branch); record `git status --porcelain` before the first edit and report the delta (orchestrator)
- [x] T002 Verify the dispatch data source with a synthetic fixture under `mods/delegate-pane/hooks/fixtures/` (invented values; keys and shapes from `agents_inc/install/dispatch.py`; no real run files copied, fable ruling); read `agents_inc/install/dispatch.py:1247,1321,1335` to confirm when run.json is first written and that the run id prefix is UTC start time; record findings in plan R1 (orchestrator)
- [x] T003 Check whether the Pane `ui.render` event or `$.ui` gives the pane width; record in plan R6; if none, layout is always stacked (orchestrator, read-only)

## Phase 2: Foundational

- [x] T004 Create `mods/delegate-pane/hooks/rungs.ts` (model id and nickname to rung) and `tests/test_delegate_pane_rungs.py` asserting each entry equals `agents_inc/models.json` tier (writer)
- [x] T005 Create `mods/delegate-pane/hooks/mission.ts`: types `Category`, `State`, `Delegate`, `Station`; functions `categoryOf`, `rungOf`, `lifecycleOf`, `runFromFiles`, `sessionRuns`, `stations`, `layoutFor` per plan R1-R6 (writer)
- [x] T006 Extend `mods/delegate-pane/types/index.d.ts`: `PaneView` gains `delegates`, `acked: Record<string, string[]>`, `sessionStart`, `finalRuns`; shape tag `view-3` → `view-4` in `mods/delegate-pane/hooks/register.tsx` (writer)
- [x] T007 [P] Unit tests in `mods/delegate-pane/hooks/mission.test.ts`: `categoryOf` over the 14-row fixture table in plan R2; `lifecycleOf` over every mapping in plan R4 incl. `quota-paused` → paused and `unverified` → review; `rungOf` unknown → `?`; `sessionRuns` drops runs before session start; `runFromFiles` on the T002 fixture and on a dir with no run.json (writer)

## Phase 3: User Story 1 - See the mission at a glance (P1)

**Independent test**: one subagent and one fixture dispatch run show at the right stations with nickname · rung · state.

- [x] T008 [US1] In `mods/delegate-pane/hooks/register.tsx`: record `sessionStart` at `session.start` into state only when unset (survives reload); poll `$.agent.list` for all subagent types (widen `isNative` use for the map only; the top list keeps spec 038 behaviour); `$.fs.list('.scratch/agents-inc-runs')`, `sessionRuns`, read run.json and slots.json only for runs not in `finalRuns`; note when the run root is missing or a read fails (writer)
- [x] T009 [US1] In the Pane `ui.render` hook of `mods/delegate-pane/hooks/register.tsx`, draw the map below the lists: centre line, six station boxes, markers `nickname · rung · state`, cap 4 then `+K more`, empty line (writer)
- [x] T010 [P] [US1] Pane tests in `mods/delegate-pane/hooks/pane.test.tsx`, looped over terminal and desktop: lists stay on top; map below; subagent and fixture run placed right; `+K more` at 5 delegates on one station; unknown rung renders `?`; read-failure note renders; old `view-3` value renders; a run started before `sessionStart` is absent (H1) (writer)
- [x] T011 [P] [US1] FR-010 test in `mods/delegate-pane/hooks/pane.test.tsx`: mock `$.model` and any network noun; run 3 polls and one render; assert neither was called (writer)
- [x] T012 [P] [US1] Bound test (M3) in `mods/delegate-pane/hooks/pane.test.tsx`: 500 fixture run dirs, 495 final and cached; assert a poll reads at most 5 run.json files and finishes within the poll interval (writer)

## Phase 4: User Story 2 - Live lifecycle and error acknowledgement (P2)

**Independent test**: failure raises count; ack clears it; a new failure raises it again.

- [x] T013 [US2] In `mods/delegate-pane/hooks/register.tsx`: station lit when any delegate on it is running or review; error count = failed ids not in `acked[category]`; `Button` ack per station with errors adds current failed ids (writer)
- [x] T014 [US2] Narrow layout per plan R6 using `layoutFor` in `mods/delegate-pane/hooks/register.tsx` (writer)
- [x] T015 [P] [US2] Tests in `mods/delegate-pane/hooks/pane.test.tsx`: press ack clears count on both surfaces; H2 case: 2 failed, ack, one leaves the window, a new failure shows count 1; ack survives reload; lit/dim transitions; stacked layout keeps every marker (writer)

## Phase 5: Polish

- [x] T016 [P] README section in `mods/delegate-pane/README.md` (create if missing): what the map shows, stations, ack, run-root visibility limit, and credit "Framing inspired by lot-map (https://github.com/alexeyw/lot-map, MIT); no code or art reused" (writer)
- [x] T017 Run `claude plugin validate mods/delegate-pane`, `claude plugin test mods/delegate-pane`, `python3 -m unittest discover -s tests -p 'test_*.py'`; all exit 0; excerpts in report (orchestrator)
- [x] T018 `git status --porcelain`: only `mods/delegate-pane/**`, `tests/test_delegate_pane_rungs.py`, `specs/039-mission-map-pane/**`, `.specify/` changed (orchestrator)
- [ ] T019 Move specs to DomI: `bash <DomI>/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply`. NOT RUN in leg 3 (fable ruling 2026-11-12); fable and the operator run it after acceptance.

## Phase 6: Operator decisions 2026-11-12

- [x] T020 Lost state (FR-012): `LOST_MS`, `withLost` in `mission.ts`; per-run dir list for newest mtime, `lostRuns` cache in `register.tsx`; tests in `mission.test.ts` and `pane.test.tsx` (lost, return, outcome later, malformed run.json, no re-read); `CONTEXT.md` "Lost run" (orchestrator)
- [x] T021 Station from the task verb first (plan R2); tests with real ROLE values (orchestrator)
- [x] T022 Rung table complete; strict drift test against models.json and MODEL_RUNG; dir-name fallback fix (orchestrator)
- [x] T023 Acks by id plus failure time; 200-id trim removed (FR-008) (orchestrator)
- [x] T024 Survive `--resume` via `$.store` keyed by session id; 20 sessions kept (FR-013) (orchestrator)
- [x] T025 Terminal motion: `hooks/frames.ts` pure frames (map model, time) -> Raster cells; braille canvas up to 96x15: curved centre-to-station edges, outward pulses with fading trails (one per running delegate, cap 3), one return pulse per finished delegate (`landings`), node glyphs by state; one 80 ms `$.clock.every` timer only while the pane is shown in the terminal grid layout and a station is lit, holds an unacked alert, or a return pulse has not landed; stopped on `ui.close`, when nothing moves, and on a refused blit (then the static map only); tests in `frames.test.ts` and `pane.test.tsx` (motion)

## Phase 7: Pass 3, operator feedback 2026-11-12 (feed decision reversed)

- [x] T026 `mission.ts`: `startedAt`/`endedAt`/`parentId` on Delegate; `statusLine`, `feed`, `duration`, `ellipsis`, `newestFirst`; tests in `mission.test.ts` (FR-014)
- [x] T027 `register.tsx`: poll records subagent first-seen/end times (`view.seen`), dispatch start from run id and end from newest file, `parentId` from `agent.list`, model from `$.session.model()`; status line and feed as Text under map (FR-014, FR-015)
- [x] T028 `frames.ts`: labelled centre, station names with `xN`, steady failure mark, straight spokes, short pulses with ripple, `arcsOf` + fading spawn arcs; timer also runs while an arc lives, no longer for a failure mark alone; tests in `frames.test.ts`, `pane.test.tsx` (FR-015..FR-018)
- [x] T029 README motion section; preview mp4 for operator (scratchpad pipeline)

## Dependencies

- T001 before any write. T002, T003 before T005, T008, T014.
- T004-T006 before T007-T015. US1 before US2. T016 independent. T017, T018 after all. T019 last, outside leg 3.
- [x] T030 2026-11-12 `arcsOf` start-order arcs (`kind: 'order'`, fainter, no dot, spawn arc wins on same pair); tests in `frames.test.ts`, `pane.test.tsx` (FR-019)
- [x] T031 Roles (2026-11-12): role column in feed rows (mission.ts feed/roleOf, register.tsx dim Text), centre role line (centreLabel, MAIN_ROLE), tests in mission, frames, pane suites; stations unchanged (FR-021).

## Implementation strategy

MVP = Phases 1-3. US2 adds ack and narrow layout.
- [x] T032 Hierarchy pass (2026-11-12): `mission.ts` `hierarchy`, `hierarchyLines`; `frames.ts` fixed CoS/Lead/Worker geometry, `spokePath`, `routeOf`, `dispatchesOf` (replaces `arcsOf`), routed dispatch and result pulses, start-order and spawn arcs removed; `register.tsx` `cosLabel` (replaces `centreLabel`) and static role line; tests in mission, frames, pane suites; README; preview `mission-map-v6.mp4` (FR-022..FR-027).
- [x] T033 Vertical map (2026-11-12): `frames.ts` spine geometry (CoS, Lead, Worker in one column, three stations a side), one-bend `spokePath`, `RASTER_MIN_COLUMNS` 34, `RASTER_MAX_COLUMNS` 56, `RASTER_ROWS` 16, `cosRoom`; `register.tsx` shows the Raster in grid and stacked layouts from 34 columns; hub delegates dropped from station names, one failure mark with count; tests for minimum width, label collision at min and cap, stable positions at three widths.
