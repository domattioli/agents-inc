<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=unknown date=2026-11-19 skill=speckit-clarify repo=agents-inc session=a3aab879-2ddd-4dda-8363-5b88faf298e4 -->
# Feature Specification: Pane Board

**Feature Branch**: `development`
**Created**: 2026-11-19
**Status**: Draft
**Input**: Operator grill session 2026-11-19 on issue #192. Operator complaint: the current delegate pane is too busy. Source: the decision record of that session (cited below as `record N`, N = numbered line). Tags: [operator] ruling, [default] Chief of Staff default shown to the operator and not vetoed, [unverified] host fact not yet tested live.

## Summary

One Board beside the chat. First job: tell the operator what needs them now. Second job: show what each delegate is doing. The host already lists agents. The new value is that the Chief of Staff (CoS) decides what the operator must know. (record 5, purpose lines) [operator]

Main user: the fleet operator, with several delegates and several sessions and the pane open all day. Wording stays plain so a new user can read it. [operator]

## Supersedes

- `.scratch/pane-debate/OUTCOME.md` (2026-11-18), wherever it differs from this spec.
- `.scratch/pane-redesign/decisions.md` (2026-11-14), wherever it differs from this spec.
- Cut list (record 31, 32): mission map, stations, roles line, feed, hierarchy tree, new-agent form, done list, tokens. Animation is not in the pane. The animation code stays unrendered on the development branch (ruling 2026-11-18). A more useful animation comes later, outside this design.

The new design replaces the delegate pane in four phases (record 35).

## Clarifications

### Session 2026-11-19 (operator grill, record 1 to 36)

- Items tagged [default] below are defaults, not operator rulings. The operator saw them and did not veto them.
- Items tagged [unverified] depend on a host fact no one has tested live. See Assumptions.

### Session 2026-11-19 (clarify)

- Q: Does a Worker with host status `killed` show in TROUBLE? → A: Yes, until dismissed with the one dismiss key. [operator]
- Q: Narrow-width behavior? → A: Truncate task and step; keep glyph and alias; rows stay one line. Below 30 columns show section counts only. [operator, 30 is a default]
- Q: Names of pane and mod? → A: Pane `Board`, inside the existing `agents-inc` mod. [operator]
- Q: Operator messages from Board to a Worker? → A: Accept D63 Memo (one-way note read at a checkpoint) with a DECISIONS amendment to D54 and D46 before Phase 3. [operator]
- Q: Marker syntax? → A: Bracket tag line, one per line: `[board:<section>] <text> | <option> | <option>`. Accepted from chat: `needs-you`, `fyi`, and `done` (closes the Item with the same text). `trouble` and `working` are ignored silently. Options are optional. [operator]

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mechanical Board (Phase 1, Priority: P1)

The operator opens the pane and sees the session's Team in the new format: TROUBLE rows, WORKING rows, and the two states that need the operator without the CoS. The operator can open a transcript, stop a delegate, and dismiss a row. Phase 1 covers the #192 minimum. (record 35)

**Why this priority**: This is the minimum that fixes "too busy" and delivers value with no model call and no CoS change.

**Independent Test**: Run delegates that work, die, wait on the operator, and hit a quota pause. Compare the Board to the expected text in each scene. No CoS items are needed.

**Acceptance Scenarios**:

1. **Given** one delegate that died 2m ago, **When** the Board renders, **Then** the open Team shows a TROUBLE section with the count 1 and the row `  ▲ luna    scan docs     died 2m ago`. (Golden scene 2; record 13, 15, 28, 36)
2. **Given** a sonnet delegate that the host holds for the operator's input or approval, with the question "run migration?", **When** the Board renders, **Then** NEEDS YOU shows the line `  1 sonnet waits: run migration?`. A Worker's Question still goes to its Lead (D54). (Golden scene 3; record 10, 12, 36)
3. **Given** a delegate paused for quota, **When** the Board renders, **Then** NEEDS YOU shows `  1 haiku paused: quota, resets 14:20` [default]. (Golden scene 4; record 10, 36)
4. **Given** two delegates working, one editing `test_x.py` and one quiet for 3 minutes, **When** the Board renders, **Then** WORKING 2 shows `  ● sonnet  write tests   edit test_x.py` and `  ◌ opus    review PR     quiet 3m`. (record 15, 16, 28)
5. **Given** a TROUBLE row is selected, **When** the operator presses the dismiss key, **Then** the row disappears and stays gone for the rest of the session. (record 14)
6. **Given** a row is selected, **When** the operator presses the open key or the stop key, **Then** the transcript opens or the delegate stops, and the footer line listed those keys for the selection. (record 17, 18)
7. **Given** no delegate and no NEEDS YOU item in any Team, **When** a session starts, **Then** the pane stays closed; **When** either the first delegate or the first NEEDS YOU item appears in any Team, whichever comes first, **Then** the pane opens without taking focus. (record 30)
8. **Given** a section has no rows, **When** the Board renders, **Then** that section is not shown. (record 4) [default]

---

### User Story 2 - CoS items by markers (Phase 2, Priority: P2)

The CoS ends a turn with marked lines. The pane reads the CoS final message, pins each marked line as a NEEDS YOU or FYI item, and lets the operator answer from a sub-pane. No model call runs. The operator can reply to their own Chief. (record 35)

**Why this priority**: This is the new value: the CoS decides what the operator must know. It depends on Story 1.

**Independent Test**: End a CoS turn with a marked line. Check the Board shows the item. Answer it from the sub-pane and check the item leaves.

**Acceptance Scenarios**:

1. **Given** a CoS final message with a marked question "Merge parser fix to main?", **When** the turn ends, **Then** NEEDS YOU shows `▸ 1 Merge parser fix to main?` as one line, the question only. (Golden scene 1; record 5, 6, 12, 36)
2. **Given** FYI items exist, **When** the Board renders, **Then** it shows the newest three, for example `  · 3 of 5 tasks verified`, and older ones age out. (record 11) [default]
3. **Given** a NEEDS YOU item, **When** the operator answers it from the pane, dismisses it, or the CoS closes it, **Then** the item leaves; otherwise it stays. (record 11)
4. **Given** an item is selected, **When** the operator presses Enter, **Then** a sub-pane opens under the Board showing title, the full source chat turn as context, source, age, quick keys, a reply box, and the last messages sent to that target; **When** the operator presses Escape, **Then** it closes. (record 19)
5. **Given** the item carries CoS-written options, **When** the sub-pane opens, **Then** the quick keys are those options; **Given** it carries none, **Then** the quick keys are `1 yes   2 no   3 hold`. Free text is always available. (record 20)
6. **Given** the CoS wrote no tool call, **When** an item is posted, **Then** no extra model round trip happened. (record 9)

---

### User Story 3 - Teams across sessions (Phase 3, Priority: P3)

The Board shows every local session as a Team. The own Team is open. Every other Team is one line with counts. The operator can message a row, an item, or a Team line in any Team. (record 35)

**Why this priority**: It ends the session switching. It depends on shared state across sessions (spike S1) and on message delivery (spike S2).

**Independent Test**: Run two sessions. Make one need the operator. Check the other session's Board shows its line, and send a message from there.

**Acceptance Scenarios**:

1. **Given** another session has one item needing the operator and three delegates working, **When** the Board renders in this session, **Then** after two blank lines it shows `! ainc2       1 needs you · 3 working` and `● quadmesh    2 working`, with no "other sessions" label. (Golden scene 6; record 1, 25, 36)
2. **Given** the same data, **When** any pane renders, **Then** every pane shows the same Teams. (record 1)
3. **Given** the operator picks a delegate in another Team, **When** the operator sends a message, **Then** the message reaches that delegate and that Team's Chief gets an FYI line. (record 21, 22) [default for the FYI line]
4. **Given** the target is a running dispatch Worker, **When** the operator sends a message, **Then** it waits for the Worker's next turn (D54). (record 23) [default]

---

### User Story 4 - Secretary (Phase 4, Priority: P4)

When a CoS turn has no markers, a model called the Secretary extracts the items. The user picks the model at install: local, a free API, or none. Phase 4 starts after an extraction bench. (record 7, 35)

**Why this priority**: It covers CoS turns that forget markers. It is optional and costs a model.

**Independent Test**: Feed a CoS final message with no markers to the Secretary. Check the items, the quotes, and the failure line.

**Acceptance Scenarios**:

1. **Given** a CoS final message with no markers and a working Secretary, **When** the turn ends, **Then** the Board shows the extracted items, each tagged `auto`, for example `  1 Merge parser fix to main?  auto`, with `auto` dim [default]. (Golden scene 5; record 7, 8, 36)
2. **Given** an extracted item whose verbatim quote is not in the message, **When** code checks it, **Then** the item is dropped. (record 8)
3. **Given** the Secretary fails or the user chose none, **When** the turn ends without markers, **Then** the pane shows `CoS turn unread, open chat`. (record 8)
4. **Given** a mechanical fact such as a died delegate, **When** the Board builds a row, **Then** no model sees it. (record 8)

---

### Edge Cases

- A delegate has the same alias as another: the rows differ by task text only. (record 16)
- A delegate has no transcript line yet: the step falls back to a state note such as `quiet 3m`. (record 15)
- A delegate shows no update for 5 minutes: it counts as a lost run in TROUBLE (CONTEXT.md). (record 13)
- A delegate finishes: its row is hidden. (record 3)
- The Board is narrow: task and step truncate, glyph and alias stay, rows stay one line. Below 30 columns the Board shows section counts only.
- A host status of `killed`: the row shows in TROUBLE until the operator dismisses it.

## Requirements *(mandatory)*

### Functional Requirements

Each requirement carries one ruling and cites the record line.

- **FR-001**: The Board MUST show every local session as a Team block, with the same data in every pane. The pane's own Team is open. Every other Team is one line with counts. The Board MUST NOT use an "other sessions" label. (record 1)
- **FR-002**: An open Team MUST show sections in this order: NEEDS YOU, FYI, TROUBLE, WORKING. (record 2)
- **FR-003**: Rows MUST be flat, grouped by state, most urgent first, with no nesting by parent. (record 2)
- **FR-004**: The Board MUST hide finished delegates. (record 3)
- **FR-005**: The Board SHOULD hide an empty section. [default] (record 4)
- **FR-006**: The CoS MUST write NEEDS YOU and FYI items, except the two mechanical states in FR-014, which enter NEEDS YOU without the CoS. HANDLED MUST NOT be a section. (record 5)
- **FR-007**: Route A: the pane MUST read the CoS final message at turn end and pin each line that carries a fixed marker, with no model call. (record 6)
- **FR-008**: Route B: when a CoS turn has no markers, a Secretary model MUST extract the items. The user MUST pick the model at install: local, a free API, or none. The local route MUST be model-agnostic. (record 7)
- **FR-009**: The Secretary input MUST be one fixed JSON envelope (CoS final message plus ids). Its output MUST be fixed JSON items with kind, title, verbatim quote, and options. [default contract detail; the operator accepted the idea] (record 8)
- **FR-010**: Code MUST check that each Secretary quote exists in the message and MUST drop an item whose quote is missing. Extracted items MUST carry an `auto` tag. [default contract detail] (record 8)
- **FR-011**: Mechanical facts MUST NOT go to a model. (record 8)
- **FR-012**: When the Secretary fails, the pane MUST show `CoS turn unread, open chat`. (record 8)
- **FR-013**: The system MUST NOT add a CoS tool call for posting items, because it costs an extra model round trip per post. (record 9)
- **FR-014**: An agent that the host holds for the operator's input or approval, and a quota pause with its reset time, MUST enter NEEDS YOU without the CoS. A Worker's Question still goes to its Lead (D54). (record 10)
- **FR-015**: A NEEDS YOU item MUST stay until the operator answers it from the pane, dismisses it, or the CoS closes it. The CoS closes an Item with a closing marker `[board:done] <same text as the Item title>`, which removes the matching Item (FR-043). (record 11)
- **FR-016**: FYI SHOULD show the newest three items; older ones age out. [default] (record 11)
- **FR-017**: On the Board an item MUST be one line showing the question only. Detail MUST show in the sub-pane. (record 12)
- **FR-018**: TROUBLE MUST be mechanical and MUST cover failed check, died, timeout, `killed` (kept until the operator dismisses it), lost run (no update for 5 minutes), and review owed (needs-review or unverified). The placement of review owed is a [default]. (record 13)
- **FR-019**: A TROUBLE row MUST stay until the operator presses dismiss. One dismiss key MUST serve rows and items. No acknowledgement store beyond the session MUST exist. (record 14)
- **FR-020**: A WORKING row MUST be one line: state glyph, model alias, task text, current step. The current step MUST be the delegate's latest action in a few words, read from its transcript at a calm rate with no model call. The fallback MUST be a state note such as `quiet 3m`. (record 15)
- **FR-021**: Rows MUST NOT show tokens, elapsed time, short id, rung word, or handle letter. Two delegates with the same alias MUST differ by task text. (record 16)
- **FR-022**: Arrow keys MUST move a selection. One footer line MUST list the keys valid for the selection. (record 17)
- **FR-023**: The actions MUST be open transcript, stop, dismiss, and reply. (record 18)
- **FR-024**: Reply MUST open a sub-pane under the Board on Enter and close it on Escape. The sub-pane MUST show the selection like a ticket: title, context, source, age, quick keys, a reply box, and the last messages sent to that target. There is no separate context field: the whole marker text is the title on one line, and the sub-pane shows the full source chat turn as context. For a Secretary Item the context is the verified quote [default]. (record 19)
- **FR-025**: Quick keys MUST be the options the CoS wrote on the item when present, otherwise the fixed set yes, no, hold. Free text MUST always be available. (record 20)
- **FR-026**: The message box MUST be able to address anything on the Board in any Team: a row, an item, or a Team line (its Chief). Messages to a Worker depend on FR-047. (record 21)
- **FR-027**: When the operator messages another Team's delegate, that Team's Chief SHOULD get an FYI line. [default] (record 22)
- **FR-028**: A message to a running dispatch Worker SHOULD wait for its next turn (D54). [default] See FR-047. (record 23)
- **FR-029**: Launching delegates and settings MUST stay in the chat. The pane MUST NOT hold a new-agent form. (record 24)
- **FR-030**: The Board MUST use one blank line between sections, two blank lines before the other Teams, and a two-space indent. (record 25)
- **FR-031**: Labels MUST be dim capitals. The NEEDS YOU, TROUBLE and WORKING labels MUST carry a count; the FYI label carries none, as in the mock. Task text MUST be normal weight. The current step MUST be dim. (record 26)
- **FR-032**: Color MUST appear only where action is needed: NEEDS YOU amber, TROUBLE red. Everything else MUST be default or dim. Glyph shape MUST carry state so the Board reads without color. (record 27)
- **FR-033**: Glyphs SHOULD be `●` working, `◌` quiet, `▲` trouble, `!` needs you, `▸` selection, `·` FYI. `!` also marks a folded Team line that holds a needs-you Item. [default, shown in every mock the operator picked] (record 28)
- **FR-034**: Signals MUST stay inside the pane. The system MUST NOT use a toast or a status line cell. (record 29)
- **FR-035**: The pane MUST open without taking focus when either event happens, whichever comes first: the first delegate or the first NEEDS YOU item in any Team. With nothing to show it MUST stay closed. A slash command MUST reopen it. (record 30)
- **FR-036**: The Board MUST NOT include the mission map, stations, roles line, feed, hierarchy tree, new-agent form, done list, or tokens. (record 31)
- **FR-037**: The pane MUST NOT render animation. The animation code stays unrendered on the development branch (ruling 2026-11-18). (record 32)
- **FR-038**: A Team means one session and the delegates and Syncs it started (D63). (record 33)
- **FR-039**: Board, Item, and Secretary are planned terms and MUST be added to the term list. (record 34)
- **FR-040**: The Board MUST ship in the four phases listed in User Scenarios. Each phase has the scope in its story. (record 35)
- **FR-041**: Tests MUST check the six golden scenes, each against an exact expected Board. (record 36)
- **FR-042**: The pane MUST be tested by one week of operator use that counts how often the operator still switches sessions. (record 36)
- **FR-043**: The marker syntax MUST read naturally in chat and carry optional reply options. Syntax: one line `[board:<section>] <text> | <option> | <option>`. The whole text is the title on one line. From chat the parser MUST accept only `needs-you`, `fyi` and `done`; `[board:trouble]` and `[board:working]` MUST be ignored silently, because those states are mechanical. The closing marker `[board:done] <same text as the Item title>` removes the matching NEEDS YOU Item. Markers cost zero extra model calls. (record 6)
- **FR-044**: The trade-off "CoS-written items by chat markers, not a tool call" MUST be recorded in DECISIONS. The entry is a task for the plan (write before Phase 1 ships). (record 9)
- **FR-045**: The pane is named `Board` and lives in the existing `agents-inc` mod.
- **FR-046**: A free-tier Secretary route MUST pass a limits check before any workspace grant. [NEEDS CLARIFICATION: Mistral free tier limits are not published; a third-party list says the free plan requires data-training opt-in; check before any workspace grant] (record 7, Open)
- **FR-047**: Operator messages from the Board to a Worker need a decision before Phase 3. D54 says no other message reaches a running Worker, and D46 fixes the escalation path Worker, Lead, CoS, CEO. D63 Memo (proposed) would allow a one-way note read at a checkpoint. Ruled 2026-11-19: accept D63 Memo; a DECISIONS amendment to D54 and D46 MUST land before Phase 3. (record 21, 23)

### Key Entities

- **Team**: one session plus the delegates and Syncs it started (D63). Shown open for the own session, one line with counts for the others.
- **Board**: the one pane beside the chat that shows every Team. First job: what needs the operator. Second job: what each delegate does.
- **Item**: a line the CoS wrote, a line the Secretary extracted (tagged `auto`), or one of the two mechanical states (FR-014), in NEEDS YOU or FYI. Has kind, title, quote, options, source, age.
- **Secretary**: the optional model that extracts Items from a CoS turn with no markers. Local, free API, or none. Its output is checked by code.
- **row**: one flat line in TROUBLE or WORKING for one delegate: glyph, alias, task text, and a state note or current step.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six golden scenes pass as tests, each against an exact expected Board. (record 36)
- **SC-002**: After one week of operator use, the count of times the operator switches sessions to learn what needs them is recorded. The record sets no target number; the count is the measure.
- **SC-003**: A WORKING row fits one line and a NEEDS YOU item fits one line. (record 12, 15)
- **SC-004**: Routes A and the mechanical Board make zero model calls. (record 6, 8, 9, 15)
- **SC-005**: An item whose quote is absent from the CoS message appears on the Board zero times. (record 8)
- **SC-006**: A signal appears in zero places outside the pane (no toast, no status line cell). (record 29)

## Assumptions

Each spike is a host fact not yet tested live. Each is a first task and blocks the phase named. (record, Spikes)

- **S1**: Shared state across sessions works (store scope or a file). Blocks Phase 3.
- **S2**: Whether the receiving session treats a mod-sent message as the operator's word. It arrives inside the engine's envelope, marked as sent by a plugin. Blocks Phase 3, and the reply to a Chief in Phase 2 if the Chief is another session's CoS.
- **S3**: Host status `waiting` separates waiting-on-operator from idle. Blocks Phase 1 (the waiting-on-operator state, FR-014).
- **S4**: The current step can be read from a delegate's transcript or tool events at a calm rate. Blocks Phase 1 (FR-020).
- **S5**: The sub-pane can be a second pane or a region of one pane. Blocks Phase 2.
- **S6**: Key focus works in the pane versus the chat prompt. Blocks Phase 1 (arrow keys, FR-022). [default: the record does not name the blocked phase for any spike; the phase is assigned from where each fact is first used]
- Host hook `turn.complete` carries the CoS final message. [unverified live; declared in host types] Blocks Phase 2.
- Host type declarations read 2026-11-19 in the mod's host types file: `turn.complete` input 14241-14244; `$.session.messages({ agentId })` 11838-11860; `prompt.fill` 9009-9013; `session.send` 12186-12230.
- Board keys (arrows, Enter, quick keys) reach the Board's Client only after the operator clicks it; before the click they go to the chat, so the footer carries a dim hint, "click here to use keys" (spike S6, 2026-11-20, host 2.1.329). [operator]
- Scope: launching delegates and settings stay in the chat. Animation returns later, outside this design.
- **FR-048**: The Board MUST handle narrow width: at 30 columns or more, truncate task and step, keep glyph and alias, and keep one line per row; below 30 columns show section counts only. (clarify session 2026-11-19; the 30 is a default)
