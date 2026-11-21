# Pane Board data model

## Board and Teams

Board is the operator's pane. A Team is one session and the delegates and Syncs it started. Identify a Team by its originating harness and session, independently of its display name or working directory. Identify each delegate by the Team and the native agent ID or dispatch run ID. Keep those IDs internal so that two rows with the same alias remain distinct targets.

The current Team is open. Other local Teams are folded into one line each and show the same counts in every Board. The open Team shows NEEDS YOU, FYI, TROUBLE, and WORKING in that order, omitting empty sections. Order rows by urgency within each section. Insert one blank line between sections and two before the folded Teams. Section labels are dim capitals. In the regular layout NEEDS YOU, TROUBLE, and WORKING show counts, and FYI uses its label alone.

Track the selected entry by identity so refreshes cannot retarget an action. Keep selection, reply drafts, recent sent replies, and dismissal state scoped to the session. The first observed delegate or NEEDS YOU Item opens Board without taking focus. The reopen command remains available after the operator closes it. The mechanism for sharing Team data between processes is [unverified] pending S1.

Sources: `CONTEXT.md:88`–`:92`, `spec.md:129`–`:134`, `spec.md:147`–`:150`, `spec.md:158`–`:163`, `spec.md:200`.

## Items and replies

An Item is either NEEDS YOU or FYI. It carries a title, source, creation time for display age, the source excerpt where available, and optional quick replies. CoS markers and validated Secretary results reference the original CoS turn. The two mechanical NEEDS YOU cases reference their delegate and source event. Use the original source identity to prevent duplicate entries on repeated observations. A Secretary Item carries `auto` and a verbatim quote. The CoS turn remains the record.

A NEEDS YOU Item stays open until the operator answers from Board, dismisses it, or the CoS closes it. The CoS closes an Item with a closing marker `[board:done] <same text as the Item title>`, which removes the matching Item. A draft or refused send leaves the Item open. FYI shows the newest three and older Items age out. Closed or aged-out Items do not have a Board section.

The row shows the title on one line. Enter opens the reply area with title, context, source, age, quick keys, free text, and recent messages sent to the selected target. Escape closes the reply area. Use the writer's quick options when present and `1 yes   2 no   3 hold` otherwise. There is no context field: the whole marker text is the title on one line, and the sub-pane shows the full source chat turn as context. For Secretary Items, use the verified quote as context.

In Phase 3, a Team line addresses that Team's CoS. An Item addresses the source conversation or the host action it represents. A delegate row addresses its owning Team's delegate. A running dispatch Worker receives a one-way Memo at an authorized checkpoint under the Phase 3 amendment. Track a queued Memo as pending until the checkpoint or next resume delivers it. A Worker's Question continues going to its Lead. Cross-session destination visibility and receipt are [unverified].

Sources: `CONTEXT.md:84`, `CONTEXT.md:91`–`:92`, `spec.md:142`–`:145`, `spec.md:152`–`:157`, `spec.md:175`, `spec.md:181`, `spec.md:200`–`:201`.

## Marker grammar

```text
[board:<section>] <text> | <option> | <option>
```

Write one marker per line. From chat the parser accepts only `needs-you`, `fyi` and `done`. `needs-you` and `fyi` create Items. `done` is the closing marker: `[board:done] <same text as the Item title>` removes the matching Item. `[board:trouble]` and `[board:working]` are ignored silently, because those states are mechanical. The text is the whole title on one line and is required; the pipe-delimited reply options are optional. Only process markers in the CoS final visible answer. Preserve the source turn and line for replay and detail. The grammar is recorded in [research](research.md#main-loop-turn-completion-and-marker-handling).

Sources: `spec.md:35`–`:36`, `spec.md:134`–`:135`, `spec.md:146`, `spec.md:148`, `spec.md:152`, `spec.md:171`, `spec.md:181`.

## Mechanical row states

| Observed state | Board placement |
| --- | --- |
| Host holds for operator input or approval | NEEDS YOU, with the actionable question when available. S3 will identify the positive signal [unverified]. |
| Quota paused | NEEDS YOU, with the available reset time. |
| Failed check, died, timed out, or `killed` | TROUBLE with `▲` and the condition. Keep `killed` visible until dismissed. |
| Lost run | TROUBLE with `▲` once an unfinished dispatch run has written nothing new for five minutes. A new event or outcome clears the live lost condition. The recorded alert stays available for dismissal. |
| Review owed (`needs-review` or `unverified`) | TROUBLE with `▲` and the reason. |
| Working or quiet | WORKING with `●` for active and `◌` for quiet, followed by alias, task and the latest short step or a state note such as `quiet 3m`. |
| Finished with no outstanding trouble | Hidden. |

Use the same dismiss action for a row and an Item. Remember a dismissed trouble episode for the session so subsequent reads of that episode do not show it again. A later distinct episode remains eligible to surface. Use glyphs to carry state without color. Use amber for NEEDS YOU, red for TROUBLE, and default or dim styling elsewhere.

Use one line per row. At 30 columns or more, keep the state glyph and model alias visible and truncate task text and current step to the display width. Below 30 columns show section counts only, including the FYI count when that section is present in place of its rows. Keep folded Teams to count lines. The narrow display uses available Board columns.

Sources: `CONTEXT.md:67`, `spec.md:32`–`:33`, `spec.md:116`–`:121`, `spec.md:146`–`:149`, `spec.md:159`–`:161`, `spec.md:183`.

## Secretary

The Secretary is the optional extractor for a CoS turn with no markers. The install choices are a model-agnostic local route, an eligible free API, and none. The Secretary receives only the CoS message and the identifiers needed to associate its result with that turn. It proposes Item kind, title, verbatim quote, and optional quick replies. The mod checks the result and drops any Item whose literal quote is absent from the source message. Accepted Items carry `auto`. An unavailable, disabled, or failed extraction shows `CoS turn unread, open chat`. A successful extraction that finds nothing leaves the Board without new Items. Mechanical facts remain outside extraction.

Sources: `CONTEXT.md:92`, `spec.md:97`–`:110`, `spec.md:135`–`:141`, `spec.md:174`.
