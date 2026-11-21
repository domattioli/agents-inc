# Implementation Plan for Pane Board

**Branch** `development` · **Date** 2026-11-19 · **Spec** [Pane Board](spec.md)

**Input** `specs/050-pane-board/spec.md`

## Summary

Replace the current delegate pane with Board inside the existing `agents-inc` mod. Show what needs the operator first and what delegates are doing second. Deliver the current session’s mechanical Board, then CoS-written Items, then Teams and replies across sessions, and finally optional Secretary extraction. Use the existing delegate data path and a deterministic renderer. Read CoS markers from completed chat turns. Posting markers and rendering mechanical state require zero model calls. See [the feature summary](spec.md#summary) and [the design decisions](research.md).

## Technical Context

| Area | Plan |
| --- | --- |
| Language and version | TypeScript and TSX using the checked-in Claude Code mod declarations. Keep dispatch integration on the existing `agents-inc` CLI paths. Record the host build in each live spike. |
| Primary dependencies | Claude Code mod hooks, pane controls, native agent state, and governed dispatch records. The existing pane already polls native agents and dispatch runs together. |
| Storage | Keep selection, drafts, and dismissals scoped to the session. Phase 3 will share a minimal Team view through the store or a file, based on S1. Cross-process store visibility and update behavior are [unverified]. |
| Testing | Run focused mod tests with fixed input and clock. Compare all six golden scenes to exact expected Board output and run the live host spikes for their respective phases. Record operator session switches over one week with no target count. |
| Target platform | Local Claude Code mod surface. Phase 3 includes Teams from other local harnesses through supported adapters. Visibility and messaging coverage are [unverified]. |
| Project type | Pane in the existing `agents-inc` mod. |
| Performance goals | Reuse one coordinated state refresh, read step data at a measured cadence, and reuse the last available state where appropriate. Keep rows to one line and use section counts below 30 columns. |
| Constraints | Zero model calls for mechanical state and marker ingestion. Keep Board signals in the pane. Keep launching and settings in chat. Keep animation code unrendered. Secretary API access requires the Phase 4 checks. |
| Scale and scope | One operator, multiple local Teams and delegates. Open the current Team and fold each other Team to a count line. |

Sources: `mods/delegate-pane/hooks/poll.ts:248`, `mods/delegate-pane/hooks/register.tsx:157`, `spec.md:129`, `spec.md:158`, `spec.md:165`, `spec.md:189`.

## Constitution Check

Planning entry and design recheck reach the same result. The design fits the applicable principles and records the pending implementation decisions below. The constitution is proposed and directs the analyzer to report violations as warnings pending ratification. See `.specify/memory/constitution.md:3` and `.specify/memory/constitution.md:62`.

| Principles | Application |
| --- | --- |
| P0, P6, P9, P10 | Cite the canon, write these artifacts in plain prose, keep changes scoped, and relay canon findings to the supervisor. |
| P1, P4 | Keep implementation edits in the repository. Check provenance, routing, message eligibility, and extraction output in code. Keep secrets outside prompts and Board state. |
| P2, P3, P7, P8 | Apply the existing implementation and review rules. Independently verify deterministic checks and use a different-vendor reviewer for canon changes under D46. Use existing model identifiers and dispatch rules for governed work. |
| P5 | Keep the zero incremental spend cap. Free-tier exhaustion follows the configured failure path. |

Sources: `.specify/memory/constitution.md:18`–`:60`, `docs/DECISIONS.md:502` (D46).

## Project Structure

### Documentation for this feature

```text
specs/050-pane-board/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
└── quickstart.md
```

### Source code from the repository root

```text
mods/
├── agents-inc/
│   ├── .claude-plugin/types/claude-code/index.d.ts
│   └── hooks/
│       ├── hooks.json
│       └── native/loop.ts
└── delegate-pane/
    └── hooks/
        ├── register.tsx
        ├── poll.ts
        ├── controls.tsx
        └── pane.test.tsx
docs/
└── DECISIONS.md
```

**Structure decision** Build Board in `mods/agents-inc/hooks/`, using the checked-in host types for the integration. Adapt collection and operator actions from `mods/delegate-pane/hooks/` and test the new renderer beside the mod. Wire Board as the replacement pane without rendering the old map, animation, feed, tree, or status line. Use `native/loop.ts` as a reference for hook composition, transcript access, and existing governed hand-back behavior. See `mods/agents-inc/.claude-plugin/plugin.json:2`, `mods/agents-inc/hooks/hooks.json:2`, `mods/agents-inc/hooks/native/loop.ts:741`, and `mods/delegate-pane/hooks/controls.tsx:127`.

## Phase 1 — Mechanical Board

1. Run the live spikes first. **S3 [unverified]** compare a real operator approval/input hold with idle and background-work waits. Identify a reliable separate signal for the operator hold. **S4 [unverified]** observe a running delegate’s transcript or tool events, and measure a calm read cadence that still surfaces the latest step. **S6 [unverified]** check Board arrow keys, selection actions, and Escape against chat prompt focus, and confirm automatic opening without focus on the target surfaces. Record the checkout and host build, observed signals, and any limitation. See [the spike decisions](research.md#mechanical-board).
2. Normalize native and dispatch activity for the current session. Render the two mechanical NEEDS YOU cases, TROUBLE, and WORKING with session-local dismissals, stable selection, valid footer actions, transcript open, and stop. Include `killed` in TROUBLE. Add first-delegate or first-NEEDS YOU opening, a reopen command, and width handling. Extend first-event detection to other Teams in Phase 3.
3. Before shipping Phase 1, add the FR-044 entry to `docs/DECISIONS.md`. Record the decision to publish CoS Items through chat markers. A posting tool would require an extra model round trip. Verify the existing definitions for Board, Item, and Secretary cover FR-039 (`CONTEXT.md:90`–`:92`).
4. Verify scenes 2–4 and focused cases for width, dismissal, active and quiet delegates, and keyboard focus. Use actual host evidence to qualify the operator hold, step extraction, and focus behavior. See `spec.md:40`–`:57`, `spec.md:172`, and `spec.md:198`–`:205`.

## Phase 2 — CoS Items from markers

1. Run **S5 [unverified]** first. Compare an inline reply region with a separate pane. Confirm Enter opens the reply surface, Escape closes it, and keyboard focus returns correctly. In the same phase, probe that `turn.complete` exposes the main loop’s final visible answer [unverified]. Check main, delegate, and interrupted turns.
2. Parse CoS markers on successful main-loop turns, publish Items once per source line, and keep the CoS turn as the record. Show the newest three FYIs. Keep NEEDS YOU Items until reply, dismissal, or CoS closure. Use the marked options or the default quick keys, with free text, source, age, context, and recent sent replies in the sub-pane. Surface current-session replies through the operator’s own chat flow. Verify scene 1, repeat delivery, failed sends, and zero extra calls to post an Item. Cross-session replies depend on S2 and ship with Phase 3. See `spec.md:61`–`:76`, `spec.md:143`–`:153`, and `spec.md:201`–`:207`.

## Phase 3 — Teams across sessions

1. Land the FR-047 Memo amendment to D54 and D46 before starting Phase 3. Limit it to the one-way checkpoint Memo accepted for Board. Keep Worker Questions with the Lead and preserve governed verification and resume limits. The Team definition is already accepted in D63. See `spec.md:175` and `docs/DECISIONS.md:682`.
2. Run **S1 [unverified]** and **S2 [unverified]** first. Use two local sessions to test whether a store or file supports common Team data with reliable ownership and concurrent updates. Test what the recipient sees from an operator-initiated plugin send, whether the recipient is awake, and whether it treats the message as the operator’s word. Record queued delivery and actual reading separately. Probe Memo receipt at the authorized checkpoint for each supported Worker path. See `spec.md:200`–`:202` and `docs/DECISIONS.md:664`.
3. Fold other Teams into one line each using confirmed session ownership. Route Board replies by stable target identity, preserve plugin provenance, and keep Worker Memos pending until an authorized checkpoint or next resume. Send the other Team’s Chief an FYI when its delegate is messaged. Verify scene 6, inter-session consistency, and delivery and refusal behavior. Start the one-week operator observation when cross-session counts are available. See `spec.md:80`–`:93` and `spec.md:190`.

## Phase 4 — Optional Secretary

1. Start with the extraction bench required by the spec. Use representative unmarked CoS turns, including no-action turns and bad quotes, to record extraction quality, false positives, latency, and zero incremental cost. Treat the bench and FR-046 as Phase 4 gates. FR-046 gates any free-tier workspace grant. Verify the provider’s current limits, eligibility and data-use terms before granting a workspace. Mistral’s limits and the reported training opt-in remain [unverified]. A route with unresolved terms stays ungranted. See `spec.md:97`–`:110` and `spec.md:174`.
2. Offer the install choices local, eligible free API, and none. Run extraction on unmarked CoS turns through the selected route, validate the result and verbatim quotes in code, and render `auto` or `CoS turn unread, open chat` as applicable. Verify scene 5 and confirm mechanical data stays outside extraction. See `spec.md:135`–`:141` and `spec.md:192`–`:194`.

## Open items

- FR-046 only (free-tier Secretary limits check, Phase 4 gate).
