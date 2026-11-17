<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-14 skill=speckit-pipeline repo=agents-inc session=91aeecb8 -->
# Feature Specification: Unified delegate pane

**Feature Branch**: `feat/pane-auto-open` (base; spec 040 work branches from it)
**Created**: 2026-11-14
**Status**: Draft
**Input**: Merge the `agents-manager` mod into the `delegate-pane` mod so the operator sees one pane with the delegation tree, the mission map, the feed, the new-agent form and the message box. Retire the second mod, and clean up leftovers from earlier pane work.

## Background

Two pane mods open at every session start. `agents-manager` (0.1.0) shows a "who delegates to whom" tree, a new-agent form and a message box. `delegate-pane` shows lists of native agents and, from 0.5.0 (spec 039), a mission map. The Mac has `delegate-pane` 0.2.0 installed, so the operator has never seen the map; only the agents-manager pane is visible. Both mods poll the same dispatch run directory, and both register an auto-open and a command.

## Clarifications

### Session 2026-11-14

- Q: Section order, top to bottom? → A: Map first: mission map with status line and feed, then the delegation tree, then the new-agent form and message box.
- Q: Narrow pane (under 34 columns): form and message box? → A: Collapse behind a one-line toggle that expands them; tree and map stay readable.
- Q: Keep the registered native types list? → A: Drop it; the form's model picker covers it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One pane shows the whole delegation picture (Priority: P1)

The operator starts a session. One pane opens. It shows who delegated to whom, the mission map, and the recent activity feed. No second agents pane opens.

**Why this priority**: This is the defect the operator reported: the map never shows, and two panes compete for the same space.

**Independent Test**: Start a session with the merged mod installed and the old mods uninstalled. Exactly one agents pane opens, and it contains the tree, the map and the feed.

**Acceptance Scenarios**:

1. **Given** a fresh session, **When** it starts, **Then** exactly one agents pane opens, titled for agents-inc, and the old manager pane does not open.
2. **Given** no delegates yet, **When** the pane renders, **Then** the tree shows the main session with "no delegates yet", the map shows its empty state, and the status line reads "Nothing is running."
3. **Given** a delegate running, **When** the pane polls, **Then** the delegate appears once in the tree, as a marker on its map station, and as a feed row.
4. **Given** the pane is closed, **When** the operator runs `/delegate-pane`, **Then** the same pane reopens.

### User Story 2 - Start and steer agents from the same pane (Priority: P2)

The operator picks a model, an effort and a task, and starts a delegate. They click a tree row to open that agent, message a live agent, resume a finished run, cancel a run, or ask it to stop.

**Why this priority**: These controls exist today in agents-manager. They must survive the merge without loss.

**Independent Test**: With the merged pane, start one native delegate, one Codex delegate and one free-model delegate from the form. Click each row, message the native one, and cancel the Codex run.

**Acceptance Scenarios**:

1. **Given** a native model is selected, **When** the operator submits a task, **Then** a native subagent starts and appears in the tree, and the effort control is hidden (the session's effort applies).
2. **Given** a Codex model is selected, **When** the operator submits, **Then** an agents-inc dispatch run starts with the chosen effort and appears in the tree and on the map.
3. **Given** a free model is selected, **When** the operator submits, **Then** a free run starts. It has no cancel control; selecting it and sending shows the note "this run takes no messages" (FR-007).
4. **Given** a live agent row is selected, **When** the operator sends a message, **Then** the message reaches that agent. **Given** a finished run is selected, **Then** sending resumes it.
5. **Given** an agent row, **When** clicked, **Then** that agent's view opens. **Given** a run row, **Then** a sub-pane for that run opens.

### User Story 3 - Install migrates cleanly (Priority: P2)

The operator runs the agents-inc installer on a machine with the old mods installed. Afterwards only the merged mod is installed.

**Why this priority**: Without migration, the stale agents-manager pane keeps opening and the operator still sees two panes.

**Independent Test**: On a machine with `agents-manager@agents-manager-local`, `delegate-pane@delegate-pane-local` 0.2.0 and a stale `luna-pane-local` marketplace entry, run the install. Only `delegate-pane` at the new version remains.

**Acceptance Scenarios**:

1. **Given** the old mods are installed, **When** the installer runs, **Then** agents-manager and luna-pane are uninstalled and their marketplaces removed, and delegate-pane updates to the merged version.
2. **Given** a clean machine, **When** the installer runs, **Then** only delegate-pane is installed.
3. **Given** the installer runs twice, **Then** the second run changes nothing and reports no error.

### User Story 4 - Repository leftovers are cleaned up (Priority: P3)

A maintainer reading the repo finds one pane mod, no stray folders, and a decision log that says which pane designs shipped.

**Independent Test**: After the change, `mods/agents-manager` does not exist, the stray folders are gone, and `docs/DECISIONS.md` marks the unbuilt D62 parts as unbuilt.

**Acceptance Scenarios**:

1. **Given** the merge is done, **Then** `mods/agents-manager/` is deleted and nothing in the repo references it except history (CHANGELOG, decisions, archived specs) and the installer retired list and its test.
2. **Given** stray untracked `.claude/` and `.scratch/` folders inside the mod directories, **Then** they are removed.
3. **Given** the locked worktree `.claude/worktrees/agent-ae71b5b16daa5b202`, **Then** it is removed only after confirming that every commit on it is already on `development` or another kept branch; otherwise it is reported and kept.

### Edge Cases

- The pane opens before any dispatch run directory exists: no error, empty tree and map.
- `.scratch/` is not git-ignored: the pane shows the existing "dispatch runs not visible" note, and the form still works for native agents.
- A narrow pane: the map falls back to its static or one-line form, and the form and message box collapse behind a one-line toggle that expands them.
- A frame is refused: the map falls back to static, and the rest of the pane is unaffected.
- The same delegate seen through two sources (native agent list and run directory): shown once in the tree and once on the map.
- Acknowledgements saved by delegate-pane 0.5.0 under `session:<id>` survive the upgrade.
- A free-model run has no agent id: the message box says the run takes no messages.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Exactly one agents pane MUST exist after the merge. It keeps the delegate-pane name, pane id and `/delegate-pane` command.
- **FR-002**: The pane MUST open once at session start. No other agents-inc mod may auto-open a pane.
- **FR-003**: The pane MUST show, in this order: the mission map with its status line and feed, the delegation tree, the new-agent form, and the message box.
- **FR-004**: The delegation tree MUST keep every agents-manager behaviour: the main-session root row, nested delegates, click to open an agent view, click to open a run sub-pane, cancel, and ask-to-stop.
- **FR-005**: The mission map, status line and feed MUST keep every spec 039 behaviour (stations, rungs, lifecycle, lost state, acknowledgements, Raster motion and static fallback).
- **FR-006**: The new-agent form MUST start native, Codex and free-model delegates exactly as agents-manager does today, including model list, effort list, defaults, and hiding effort for native models.
- **FR-007**: The message box MUST send to a live agent, resume a finished run, and refuse with a note for runs that take no messages.
- **FR-008**: The "Native agents this session" list MUST be removed, because the tree replaces it. The registered native types list MUST also be removed.
- **FR-009**: The pane MUST read the dispatch run directory through one shared poll, not two.
- **FR-010**: Acknowledgements saved under the existing store key MUST still load after the upgrade.
- **FR-011**: The installer MUST install only delegate-pane, and MUST uninstall agents-manager and luna-pane mods and remove their marketplaces when present. A repeat run MUST be a no-op.
- **FR-012**: `mods/agents-manager/` MUST be deleted, and the bundle allowlist MUST no longer ship it.
- **FR-013**: All existing tests of both mods MUST pass under the merged mod (ported, not dropped), along with the rung-sync test and the installer tests.
- **FR-014**: The pane MUST call no model and no network, as today.
- **FR-015**: `docs/DECISIONS.md` MUST gain a status note on D62 stating that the office floor view and `agents-inc watch` were not built and that the pane design shipped as specs 039 and 040. CHANGELOG MUST record the merge.
- **FR-016**: Stray untracked folders inside both mod directories MUST be removed, and the locked worktree handled per User Story 4, scenario 3.
- **FR-017**: The mod README MUST describe the merged pane.

### Key Entities

- **Delegate**: one agent working for the session: a native subagent, a dispatch run, or a free run. It has a name, a rung, a state, a parent, and a station category.
- **Session record**: the stored session start and acknowledgements, keyed by session id.
- **Pane mod**: the installed plugin, its marketplace, and its version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 5 of 5 fresh sessions after install, exactly one agents pane opens.
- **SC-002**: Every control the operator had in either old pane (at least 10: open agent, open run, cancel, ask-to-stop, start native, start Codex, start free, message, resume, acknowledge) is reachable in the merged pane.
- **SC-003**: The test count of the merged mod is at least the sum of both old mods' test counts, and all pass.
- **SC-004**: On a machine with the old mods, one installer run leaves zero old pane plugins installed.
- **SC-005**: The repo contains zero references to `agents-manager` outside history files and the installer retired-mod list and its test (agents_inc/install/cli.py, tests/test_mod_install.py).

## Assumptions

- The merged mod keeps the delegate-pane version line and bumps it to 0.6.0.
- Development and stress tests run in docker; the Mac only installs (operator note 2026-11-03).
- Spec 039 work and the auto-open commit on `feat/pane-auto-open` are the base and are kept.
- `gh` currently fails with a TLS error on this machine; PR history came from commit messages only.
- Agents-manager stores no persistent state, so there is nothing of its own to migrate.
