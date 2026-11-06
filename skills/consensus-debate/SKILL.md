---
name: consensus-debate
version: 0.2.1
benchmark: rounds_to_consensus_and_fake_consensus_rate
description: Run a moderated two-model debate (e.g. fable vs astra) on a fixed set of questions until both sign the same consensus block or the moderator calls deadlock. Use when the operator asks two models to "discuss until they agree", wants a cross-vendor second opinion that converges, or needs a decision stress-tested by two strong reviewers. Covers brief writing, round protocol, crossed-round repair, wheel-spin and scope-creep stops, resume-not-rebrief transport, and transcript capture for lessons learned.
---

# consensus-debate

Session running this = **moderator**. 2 **debaters** answer same questions, see each other's msgs, revise until agree or stall. Moderator relays verbatim, verifies cites, settles checkable facts, enforces stops. Never argues a side.

Evidence base: 1 run (ollama in agents_Inc, fable vs astra @ medium, 2026-09-22). Unproven until run 2.

## Use / don't

- Use: operator names 2 models + wants consensus; cross-vendor review needing ONE answer; 2–6 discrete questions w/ checkable verdicts.
- Don't: single factual q (measure it); open brainstorm (converges on first idea); code changes (debaters judge, builders build).

## Roles

| role | who | job |
|---|---|---|
| moderator | this session | brief, relay, verify, stop |
| debater A | Claude (transport below: `agents-inc dispatch` when installed) | answer, rebut, revise |
| debater B | other vendor preferred (Codex astra/sol) | same |
| operator | human | settles deadlock |

Debater briefs: the moderator leaves the SUPERVISOR/EXECUTIVE slots blank for any debater and puts the debater's own alias first in ROLE (or adds a `MODEL:` line), with the relay named after it. The moderator relays and does not supervise, and the dispatch lint would refuse the inverted chain.

Vendor gate: non-Claude debater needs `workerbee` Step 0.5 gate line (normally (a) operator asked). Effort default medium for every debater, every vendor (opus included), unless operator names level for this debate.

## Transport — resume, never re-brief

- Claude, agents-inc installed: R1 `agents-inc dispatch --slots <json> --model <opus|sonnet|haiku|fable> --effort <lvl>` → R2+ `agents-inc dispatch --resume <run> --message <text>` (same session, ledgered; D61 enforce blocks `Agent` for debaters, `opus-xhigh` never allowed). Effort = `--effort`, default medium, other level only if operator named it.
- Claude, no agents-inc: `Agent(subagent_type=opus-medium)` (or sonnet/haiku with no effort pin) R1 → `SendMessage` same agent R2+. `Agent` has no effort param → effort comes from the agent def; never use an effort-pinned def (e.g. `opus-xhigh`) unless operator named that level.
- Codex, in this order:
  1. `agents-inc` launcher if installed.
  2. DelegateAgent tool (any `mcp__*__DelegateAgent`): `model=<seat>`, `effort=<lvl>`; R2+ pass `conversation_id` from R1. Claude Code starts the server, not the Bash sandbox (seen 2026-11-02; Mac acceptance T020 confirms it).
  3. Shell line, last resort. R1 `codex exec -m <slug> -c model_reasoning_effort=<lvl> -s read-only -C <repo> --json -o <out.md> - < prompt.md` → grab `thread_id` from first JSON line. R2+ `codex exec resume <thread_id> -m <slug> -c model_reasoning_effort=<lvl> -c sandbox_mode=read-only --json -o <out.md> - < next.md`, run from repo dir (resume has no `-s`, no `-C`).
- After the shell line run `test -s <out.md> || echo "FAIL: empty Codex output; use the DelegateAgent MCP route or run this line with ! (unsandboxed)"`. Exit 0 is not success: an empty `<out.md>` is a failure.
- The shell line needs an unsandboxed shell: sandboxed auto-mode Bash cannot refresh the Codex login (#127).
- Each round sends ONLY moderator notes + peer's latest msg.
- Token accounting: Codex `turn.completed` usage + Claude `subagent_tokens` = CUMULATIVE per thread, not per turn → subtract prior round. Resume replays whole thread each turn (mostly cache hits); input grows ~thread size per round.
- No resume on a transport → resend brief + compact transcript, log as cost.

## Protocol

1. **Preload verified facts.** Measure before R1. Brief VERIFIED STATE, each bullet `[verified]`/`[inferred]`/`[assumed]`. Describe real mechanisms exactly ("router = fixed provider order, no scoring"), never loose ("router picks X over Y") → debaters design around features that don't exist.
2. **Probe load-bearing inferences.** `[inferred]` fact a key choice hinges on (e.g. "CLI reads stdin + takes limits") → probe before R1 or mark BLOCKING. Run 1: one such inference cost a round.
3. **Fix questions.** 2–6 numbered, allowed verdict set each. OUT OF SCOPE list. Out-of-scope → PARKING LOT ≤3 lines, never argued.
4. **One brief, placeholders** `{SELF}` `{PEER}` caveman line, effort line → render per debater. agents_Inc: brief = dispatch prompt → 14-element contract + `check_dispatch_prompt.py --with-handoff-lint` clean before send. Template lines, plain (no fence, no blockquote):
   GOAL: the debate question and the verdict set.
   CONSTRAINTS: allowed sources, effort, caveman level.
   DONE: both final blocks agree on every question, or `DEADLOCK: <item>`.
   OUT OF SCOPE: no file edits, no commands, nothing beyond the debate question.
   STOP ON BLOCK: if a hook or classifier blocks or denies an action, stop and hand back; never switch to another tool to work around it.
5. **R1 blind, parallel.** Neither sees other.
6. **Between rounds, moderator:** grep every cite; settle cheap safe facts (`--help`, one-line probe, file read) → MODERATOR NOTES `[verified]` atop relay + list open disputes. Turns fact-fights into judgment-fights.
7. **R2:** relay peer's latest verbatim. Reply = AGREE/DISPUTE/CONCEDE per item + full PROPOSED CONSENSUS. Concede on evidence only.
8. **Crossed-round repair (after R2).** Parallel rounds cross: each R_n answers peer's R_{n-1} → debaters concede to positions peer already left, can swap sides. After R2: diff latest 2 blocks → numbered residual list D1..Dn, freeze agreed items ("do NOT reopen"), R3 answers D-items only (AGREE peer / KEEP mine + evidence). Run 1: fable R2 conceded fully to astra R1 while astra R2 had added 2 files fable lacked.
9. **Last round = fixed-form reply** for open items only: `D4: ACCEPT` | `D4: DEADLOCK — <evidence>` + `STATUS: ...`. Run 1: 17 output tokens.
10. **Stop on:** consensus (blocks match in substance on every verdict + change item, or `ACCEPT PEER CONSENSUS`) | wheel spin (same DISPUTE set 2 rounds, or repeat w/o new evidence) | debater `DEADLOCK: <item>` | R4 hard cap.
11. **Verify before report.** Grep every file/fn/flag in final block; strike failures.
12. **Report once, at end** — no per-round operator updates unless decision/failure. Short verdict + decisions needed; full block + transcripts behind fold/file.

## Gates

- Success: both final blocks agree every question; every `[verified]` cited; numeric guards have units; done ≤R4.
- Failure: question w/o verdict; invented cite; wording hides real split (fake consensus); out-of-scope argued.
- Honest DEADLOCK = valid outcome. Fake consensus = failure.

## Scope creep

Closed questions. New topics → parking lot. Moderator strikes out-of-scope args before relay. Change lists capped (default 8), each item real path or `NEW <path>`; cap counts FILES touched, not bullet items (helpers can hide extra files).

## Transcripts

Save every rendered prompt + raw reply: `<dir>/<name>_r<N>.md`, `<name>_r<N>_out.md`, Codex `.jsonl` + `.err`, `moderator_r<N>.md`, final `CONSENSUS.md`. Feed skill lessons.

## Run 1 results (2026-09-22)

| measure | value |
|---|---|
| outcome | consensus R4, 4/4 questions, no deadlock |
| rounds | 3 full + 1 single-item confirm |
| astra (Codex, resumed) | 161.5k input cumulative (126.1k cached, 78%), 4.4k output; per round ≈30k, +40k, +44k, +47k |
| fable (Claude, resumed) | ≈77.5k tokens cumulative, 12 tool calls |
| wall time | ≈7 min (file timestamps 15:30:42 → 15:37:46) |

Worked: blind R1 → real splits (CLI vs HTTP, auto vs explicit auth, loose vs tight limits); moderator notes killed fact disputes in 1 step; concessions cited verified lines; fixed-form last round.
Failed: crossed rounds (~1 cycle); loose mechanism wording + untested seam (~1 round); moderator misread cumulative tokens until R4.

## Open for v0.3

- Sequential rounds (A then B answers A's current msg) vs parallel + crossed-round repair — cost/time?
- Blind R1 still worth it when brief already carries key measurements?
