# delegate-pane

One pane for the agents-inc delegates of the current session.

## Lists

- Native agent types registered by agents-inc (`agents-inc:<nickname>`).
- Native agents of this session. Only `agents-inc:*` subagents appear here; dispatch run directories do not.

## Mission map

Below the lists the pane draws a mission map (spec 039): a centre line for the session, six stations, and one marker per working agent. A marker reads `nickname · rung · state`.

- Stations: Review, Build, Write, Scout, Plan, Other. The category comes from a fixed rule table (subagent type, dispatch slots `TASK_KIND` or `ROLE`, the leading verb of the task text, then the grunt rung), never from a model.
- Sources: every subagent type of the session (`Explore`, `general-purpose`, `agents-inc:*`) and every `agents-inc dispatch` run of this session found under `.scratch/agents-inc-runs`.
- Rung: from `hooks/rungs.ts`, which `tests/test_delegate_pane_rungs.py` checks against `agents_inc/models.json`. An unknown model shows `?`.
- State: running, review (dispatch outcome `unverified`), done, failed, paused (`quota-paused`).
- A station is lit (`●`) while a delegate on it is running or in review. It shows the count of failures not yet acknowledged (`2✗`). A station shows 4 markers, then `+K more`.
- Lost: a dispatch run with no outcome and no file change for 5 minutes shows `lost`. It is not counted as working and raises the station's count like a failure. A new event or an outcome brings it back.
- Acknowledge: a Button on a station with failures acknowledges the failure events it covers (one delegate, one failure). The count returns for a new failure, including a second failure of the same delegate. Acknowledgements survive a reload and `claude --resume`: the pane keeps the session start and acknowledgements in its store, by session id, for the 20 most recent sessions.
- Layout follows the pane width: a grid from 70 columns, stacked stations from 30 (the Raster map shows from 34), one line per station below that.

### Motion (terminal)

In a terminal pane 34 columns or wider the map gains a Raster above the station boxes: a vertical map, 34 to 56 columns by 16 rows, drawn on a braille dot grid. Narrower panes show the text map alone.

- Three role nodes, placed the same way every time so nothing jumps when one comes or goes:
  - **CoS** (Chief of Staff): a small node at the top of the spine, labelled `CoS` and the session's model. It is the main session, the agent you talk to.
  - **Lead**: the middle of the spine, labelled `Lead · <name>` to its right. The Lead is a delegate that has started delegates of its own. If several have, the one on the higher rung wins, then the one that started first. If none has, the main session is doing the Lead's job itself: the hub shows a hollow `○` labelled `CoS as Lead`, with no link to the CoS node, because both are the same agent.
  - **Worker**: the hub below the Lead on the same spine, labelled `Worker · <name>` to its right. It names the Lead's workhorse-rung delegate with the newest running task (any delegate's, when there is no Lead). When none runs, the hub is not drawn.
- One vertical spine runs CoS, Lead, Worker from top to bottom. Six stations stand in a column on each side: Plan, Scout and Write on the left, Other, Review and Build on the right. A thin, dim spoke joins the Lead to each station, along the spine and across (Scout is straight). It brightens while the Lead's work on that station runs. The Lead and the primary Worker are named on their hubs only, not again under their station, which stays lit. A failed station shows one red mark and its count (`✗ Review 2`).
- Who talks to whom (delegation model, Chains):
  - The CoS dispatches the Lead and gets its one report: a permanent link joins them while a Lead exists.
  - The Lead dispatches and hears from its Workers on the spokes. Each running Worker sends a small pulse out every 2.4 s.
  - A delegate the main session started itself while a Lead runs gets a CoS edge, drawn only while its dispatch or its result travels.
  - A Worker that starts its own helper (workhorse to grunt) draws a curve between the two stations, only while that pulse travels.
  - Results go back to whoever started the delegate. A Lead's Worker never sends anything to the CoS. A failed result travels in red.
- Each station shows the names of its working delegates. When they do not all fit, it shows `x2`, `x3` and so on.
- An unacknowledged failure shows a steady red `✗` and its count. It does not blink.
- One colour for activity, pale grey for passing edges, red for failure.
- Frames run at 12.5 a second, only while something moves. A refused frame falls back to the static map. Desktop and narrow panes get the static map.
- Frames come from `hooks/frames.ts`, a pure function of stations, returns, dispatches and time.
- The static map (desktop, narrow panes, refused frames) names the three in one dim line, two when narrow: `CoS: main session (<model>) · Lead: <name> (<rung>) · Worker: <name>`.

### Status line and feed

Under the map, on every surface:

- One line: `Nothing is running.`, or the newest running delegate and its task, with `and N more`.
- Then one row per delegate, newest first: bullet, name, task, and `running` or how long it took. Running rows are highlighted, failed rows are red with `✗`, finished rows are dim. The feed shows up to a third of the pane's height (3 to 10 rows).
- Times are what the pane saw: a subagent starts when the pane first lists it. With no known times the row shows `—`.

### Limits

- Dispatch runs are visible only when `<cwd>/.scratch/` is git-ignored. Otherwise runs land in `$CLAUDE_SCRATCHPAD` or `$TMPDIR`, which the pane cannot read, and it shows the note `dispatch runs not visible: .scratch not ignored`.
- A run belongs to the session when its run id (UTC start time) is at or after the session start. A second session started later in the same directory shares those runs.
- Each poll lists the run root once and reads files only for runs that are not final; final runs are cached.
- The pane calls no model and no network.

Framing inspired by lot-map (https://github.com/alexeyw/lot-map, MIT); no code or art reused.

## Roles

Feed rows show a dim role word (the delegate's rung: executive, orchestrator, workhorse, grunt) between name and task; blank when the rung is unknown, dropped on a narrow pane. The static centre line reads `main session · chief of staff`. Only the hubs carry role words (CoS, Lead, Worker); stations show none.

## Checks

```
claude plugin validate mods/delegate-pane
claude plugin test mods/delegate-pane
python3 -m unittest tests.test_delegate_pane_rungs
```
