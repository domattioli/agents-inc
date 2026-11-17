<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-12 skill=speckit-specify repo=agents-inc session=f8c024a9-ee62-4516-9889-edd03b1d02b1 -->
# Feature Specification: Mission map view in the delegate pane

**Feature Branch**: none (spec directory only; no branch created)
**Created**: 2026-11-12
**Status**: Clarified, with 4 operator confirmations open (FR-003 supersedes 038 FR-020; station set; queued state; session scoping limit)
**Input**: Operator: "create a visualization in the modded pane to implement our agents-inc mission framing https://github.com/alexeyw/lot-map". Interpreted by the Executive as: add a view to the agents-inc delegate pane that shows a mission (every delegate, by task category, with lifecycle state), borrowing only the framing of lot-map.

## Background

- The delegate pane (`mods/delegate-pane`) today lists the offered native agent types and the native agents of the session as two text lists. Spec 038 FR-020 limits it to native agents and excludes dispatch run directories.
- lot-map (MIT license) is a Claude Code mod that draws a live hub map beside the chat: the session sits at the centre, each action pulses to a "station" for its kind of work, running work stays lit, and errors carry a red mark.
- This feature borrows that framing only: a centre, stations for kinds of work, lit state, error marks. It copies no lot-map code, name, station set, art or text.

## Clarifications

### Session 2026-11-12

- Q: Scope? → A: "all working agents and the categories of tasks they are working on": every delegate, subagents and `agents-inc dispatch` runs. **This overturns spec 038 FR-020** (pane lists only native agents, no dispatch runs). Spec 038 is not edited; this spec supersedes FR-020 for the pane. Operator confirmation pending (NEEDS-OPERATOR).
- Q: Stage? → A: delegate lifecycle: queued, running, review, done (plus failed as an error state).
- Q: Placement? → A: "below the existing list": same pane, list on top, map under it, both visible. No toggle, no second pane.
- Q: Stations? → A: operator "not sure". Executive ruling, provisional `[assumed]`, operator may veto: stations are task categories (kinds of work). Each agent is a marker at its category station, labelled with nickname and rung.
- Q: Rung source? → A: agents-inc status JSON, fixed table fallback.
- Q: Error marks? → A: manual dismiss; "ideally i could click to acknowledge". The pane can draw a pressable control (click where the terminal reports clicks, Enter under focus otherwise), so acknowledgement is by press.
- Q: Feed? → A: none in v1. REVERSED 2026-11-12 at operator request (pass 3): status line + feed under map, from mission data only; see FR-014.
- Q: Layout? → A: radial-ish grid under the list, stacked fallback when narrow.

### Operator decisions 2026-11-12 (after review)

- Lost state: a dispatch run with no outcome and no new event for 5 minutes is `lost` (FR-012).
- Station from the task verb first; ROLE only when the task text matches nothing (plan R2).
- Rung table complete; drift test strict (plan R3).
- An acknowledgement covers one failure (or lost) event of one delegate, not the id forever (FR-008).
- The map survives `claude --resume` (FR-013).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the mission at a glance (Priority: P1)

The operator opens the delegate pane. Below the existing lists, a mission map shows the session at the centre and one station per task category. Every delegate (native agent or dispatch run) is a marker at its category station, labelled with nickname and rung, with a lifecycle mark.

**Why this priority**: This is the feature.

**Independent Test**: Start one native luna agent on a scouting task and one dispatch run on a code task; open the pane; each appears at the right station with nickname, rung and state.

**Acceptance Scenarios**:

1. **Given** a running native luna agent asked to "summarize the logs", **When** the pane draws, **Then** a marker "luna · grunt · running" shows at the Scout station.
2. **Given** a dispatch run under review, **When** the pane draws, **Then** its marker shows state "review".
3. **Given** no agents, **When** the pane draws, **Then** the centre and stations show empty with one "no delegates" line; the list above is unchanged.

### User Story 2 - Live lifecycle and error acknowledgement (Priority: P2)

A station reads as lit while any marker on it is running or in review. A failed agent adds an error mark with a count to its station. The mark stays until the operator presses its acknowledge control.

**Independent Test**: Let an agent fail; see the mark and count; press acknowledge; mark clears; a new failure raises it again.

**Acceptance Scenarios**:

1. **Given** a running agent, **When** it finishes, **Then** its marker shows done within 2 seconds and the station dims if nothing else runs there.
2. **Given** two failures on one station, **When** the pane draws, **Then** the station shows an error mark with count 2 and a press control; **When** pressed, **Then** count resets to 0 and the mark hides.

### Edge Cases

- An agent whose task matches no category goes to Other, never dropped.
- An agent whose rung is unknown is labelled "?" for rung, never dropped.
- Status read or ledger read fails: the map draws from what it has and shows a one-line note.
- Pane narrower than the grid minimum: stations stack one per row.
- More markers on a station than fit: first N plus "+K more".
- Pane reload mid-session: older stored state renders without error; acknowledged counts survive reload.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pane MUST show a mission map below the existing type list and agent list; both stay visible.
- **FR-002**: The map MUST show a centre node for the session and one station per task category from a small fixed set with an Other bucket.
- **FR-003**: Every delegate of this session MUST appear as exactly one marker. A delegate is (a) any subagent `$.agent.list` reports for this session, native agents-inc types and other types alike, or (b) an `agents-inc dispatch` run whose run directory sits under `<session cwd>/.scratch/agents-inc-runs/` and whose run id timestamp is at or after this session's start, recorded by the pane at `session.start` and kept across reloads. Known limit: a second session started earlier in the same cwd is excluded, but one started later in the same cwd shares dispatch runs started after both began; dispatch records no parent session id. This supersedes spec 038 FR-020 for the pane.
- **FR-004**: An agent's category MUST be derived deterministically from its recorded data, with no model call.
- **FR-005**: Each marker MUST show nickname, rung and lifecycle state: running, review, done, failed, paused or lost (FR-012). `queued` is never shown in v1. The engine subagent status `pending` is a queued report; v1 draws it as running. Subagent `waiting` and `idle` show as `paused`. A quota pause (dispatch reason `quota-paused`) shows as `paused`, not queued. A dispatch dry run (outcome `dry-run`) launched nothing and is not drawn.
- **FR-006**: Rung MUST come from agents-inc's model data via the status read, with a fixed fallback table in the mod.
- **FR-007**: A station MUST read as lit while any marker on it is running or in review.
- **FR-008**: A station's error count MUST be the number of failed or lost delegates on it whose current failure event is not acknowledged. A failure event is one delegate id plus the time that failure (or loss) began. Pressing the station's acknowledge control acknowledges every current failure event on that station. A delegate that fails again under an acknowledged id (a resumed subagent, a run that came back and went silent again) counts again. A delegate that leaves the window never hides a new failure. Acknowledgements are not trimmed by count; they live as long as the session's record (FR-013).
- **FR-009**: The map MUST fit the minimum size stated in the plan and degrade to a stacked layout below it, losing no marker or state. Known limit: below 30 columns the map shows one line per station with counts only (working and unacknowledged failed); markers, nicknames and per-marker state are not shown there (plan R6).
- **FR-012**: A dispatch run with no outcome whose newest file change is 5 minutes old or more MUST show as `lost`. A lost run is not counted as working and not lit; it raises its station's error count like a failure and is cleared by the same press. When the run writes a new event or an outcome, it MUST return to running (or its real outcome) and its alert is withdrawn. A run.json that stays malformed falls under the same rule. The pane does not re-read a lost run's files until one of them changes.
- **FR-013**: Session start, acknowledgements and subagent failure times MUST be kept in the mod's store under the session id and read back at session start when the session state is empty (a `--resume`). Runs from before the resume stay on the map; acknowledged failures stay acknowledged. The store keeps the 20 most recent sessions.
- **FR-010**: The mod MUST make no network request and call no model to draw the map.
- **FR-011**: The mod MUST contain no code, art, names or text copied from lot-map; its README MUST credit lot-map as the inspiration for the framing.

### Key Entities

- **Delegate**: one unit of delegated work in this session: a subagent or a dispatch run. Fields: id, source (subagent or dispatch), nickname, rung, task text, category, lifecycle state. The spec uses only this term.
- **Marker**: the drawing of one delegate on the map.
- **Station**: one task category with its markers, lit flag and the set of failed delegate ids not yet acknowledged.
- **Acknowledgement**: per station, the set of failed delegate ids the operator has acknowledged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With up to 10 agents, the operator names each agent's category, rung and state from the pane in under 10 seconds.
- **SC-002**: A state change shows in the pane within 2 seconds, and stays within 2 seconds after 200 dispatch runs in the session.
- **SC-003**: 100% of delegates appear on the map; none dropped.
- **SC-004**: The mod's test suite passes, including tests for category derivation, rung mapping, lifecycle mapping, error acknowledgement and narrow layout.

## Assumptions

- Station set and derivation are the Executive's provisional ruling `[assumed]`; the plan proposes them.
- Poll interval stays at 1 second.
- Per-station marker cap is 4 names, then "+K more".
- lot-map is MIT licensed (README "License: MIT", read 2026-11-12).
- Terminal is the main surface; other surfaces get the same tree.

## Pass 3 additions (2026-11-12, operator feedback on motion pass 2)

- FR-014 Narration: one status line under map ("Nothing is running." or newest running delegate `name: task` + "and N more"), then feed, newest start first: bullet, name, task with ellipsis, right-aligned `running`/`review`/`paused`/`lost` or duration (start..end as polled; `—` when unknown). Running rows highlighted, failed/lost red with `✗`, finished dim. Rows capped at a third of pane body, 3..10. Normal Text elements, all surfaces. Reverses the v1 "no feed" answer.
- FR-015 Centre label: `main session` plus model from `$.session.model()`; fixed label alone when engine gives none. Static centre line `◉ main session · N working[ · model]`.
- FR-016 Station names: Raster station shows names of working delegates (else newest one) that fit, `xN` badge when not all fit, steady red `✗N` for unacked failures (no blink).
- FR-017 Spawn arcs: real relation only, engine `AgentInfo.parentId` (subagent spawned inside another subagent). Parent and child on different stations: thin pale arc parent -> child, one travelling dot, held then faded, gone ARC_MS (6 s) after child start. Dispatch runs carry no parent: no arc. 
- FR-019 Start-order arcs (2026-11-12): when a delegate starts on station B and the previous start by real start time was on a different station A, a fainter A -> B arc (lower colour level, no travelling dot) with the same hold and fade. Same station: none. Start time unknown: none. A spawn arc on the same pair wins. Timer runs while any arc lives.
- FR-018 Look: straight thin dim spokes, brighter while working; one activity colour, pale grey arcs, red failure; pulses with short shrinking tail cross a spoke in 0.6 s, outward per running delegate every 2.4 s, inward once on finish; ripple 0.4 s where a pulse lands.
- FR-021 Roles (2026-11-12): feed rows carry one dim column between name and task with the delegate's rung word in lower case (executive, orchestrator, workhorse, grunt), derived only from the rung the pane already holds (rungs.ts); unknown rung is a blank column; width is the longest word shown; dropped on a narrow pane before the task is cut further; dim on every row state. Per-task roles (Lead, Worker) are shown only if the data carries them; today it does not. Centre line reads `main session · chief of staff` (glossary CoS), role dropped first when it does not fit. Stations carry no role words, glyphs or colours.


## Hierarchy pass (2026-11-12, operator decisions)

Operator words: "the visual should include orchestrator/supervisor/workhorse/lead/grunt/worker etc but i dont want it to get too busy"; "what about the concept of the orchestrator and primary worker being as many as two unique nodes"; "i dont think the cos is in the center"; chosen sketch (CoS small at top, Lead centre-left hub, Worker centre-right hub joined by one link, stations on ring: "looks good"); "cos can takl to any og them, lead can talk to any of them, none except lead can interact w cos, etc see the other rules". Supersedes FR-002 and FR-015 single centre node: no centre node; at most two centre hubs.
- FR-022 Nodes. CoS: small top-edge node, label `CoS · <model>` (model dropped when no room). Lead hub centre-left, primary Worker hub centre-right, one trunk link. Geometry fixed regardless of data (no jump when a hub comes or goes).
- FR-023 Lead = delegate with a child on the map (`parentId`). Tie: higher rung (executive>orchestrator>workhorse>grunt>unknown), then earliest start (unknown last), then list order. No Lead: main session does Lead job; hub drawn hollow `○` labelled `CoS as Lead`, no CoS link (same agent; glossary CoS dispatches only the Lead, Worker reports to a Lead, so the slot is filled by the CoS, not invented).
- FR-024 Primary Worker = among Lead's children (all delegates when no Lead) the workhorse-rung delegate running with newest start; none running: hub absent.
- FR-025 Routes (DELEGATION-MODEL Chains, Delegation by rung): Lead spokes permanent (left stations direct, right stations through trunk and Worker position); CoS-Lead link permanent while a Lead exists, carries Lead dispatch and its one report; delegate with no parent while a Lead exists: CoS edge drawn only while its dispatch or result pulse travels; child of a non-Lead delegate: station-to-station curve only while its pulse travels; parent missing from map or same station: nothing drawn. Results return to starter; a Lead child never reaches the CoS. Heartbeat pulses only on Lead spokes. Failed or lost result travels in red. Dispatch drawn only for a delegate seen working (first seen ended: none).
- FR-026 Quiet: FR-019 start-order arcs removed (no real relation); FR-018 spawn arcs replaced by FR-025 routes (Lead spawns ride spokes; other spawns draw a curve only during the pulse; ARC_MS hold and fade removed). Role words only on hubs; feed keeps rung column; no text under stations beyond names.
- FR-027 Static map (every surface): one dim line `CoS: main session (<model>) · Lead: <name> (<rung>) · Worker: <name>`, two lines when narrow; `Lead: none, the CoS leads`, `Worker: none running` when absent.
- Data cannot show: dispatch runs carry no parent (a Lead's own `agents-inc dispatch` draws as CoS-started); escalation path (ask_lead); Lead to CoS exactly once and no progress updates (only ends are seen); depth cap and fan-out budget; hard separations (author never grades own work, reviewer vendor, only CoS commits, delegate slice).

## Vertical map (2026-11-12, operator request)

Operator words: "we should probably orient it vertically as opposed to horizontally so it fits in the pane".
- FR-028 Vertical orientation. One spine, CoS then Lead then Worker top to bottom; Plan, Scout, Write on the left, Other, Review, Build on the right; each station joined to the Lead by a thin spoke along the spine and across (one bend, Scout straight). Hub labels sit right of their node. Horizontal geometry removed, one layout at every width. Everything else (roles, links, routes, pulses, red failures, stable positions, timer rules, blit fallback, colour pairs) unchanged. Supersedes the centre-left/centre-right and ring geometry in FR-022 and FR-025.
- FR-029 Width. Raster minimum 34 columns (`RASTER_MIN_COLUMNS`, was 70), the smallest width where the longest labels stay whole (nine-letter hub names, `Scout 12`); cap 56 columns; 16 rows. Shown in the grid and stacked layouts; below 34 the static text map stands alone.
- FR-030 Label fixes. A hub's delegate is named on the hub only, not again under its station (the station stays lit); a failed station shows one `✗` mark and the count, not two marks.

