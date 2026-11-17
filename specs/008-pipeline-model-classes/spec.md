<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# 008 — Provider-agnostic model classes + speckit-pipeline revision

Machine doc. Caveman ultra. Status: specified, not started (PR #466 open, unmerged). Created 2026-09-06 (operator direction). **Amended 2026-09-07 (D34):** top rung renamed Supervisor -> Executive; Orchestrator gained Supervisor as a synonym for the same rung. "Supervisor" below is the pre-rename name — read as Executive throughout; DomI PR #466 needs the matching fixup before merge.

## Intent

Revise DomI's `speckit-pipeline` (user scope, v1.4) rather than port or fork it. Two modes:
- **New mode = DEFAULT.** Provider-agnostic model classes, effort default medium, this repo's gates.
- **Legacy mode = retained**, but its default effort drops `high` → `medium` (operator ruling; aligns w/ D29).

Porting is rejected: vendoring a DomI skill into a consumer tree is banned (`CLAUDE.md` "Never"), and forking a moving v1.4 skill reproduces the exact drift `docs/adr/0003` documents.

## Model classes (RESOLVED 2026-09-06 — Resolution 3 is OPERATOR RULING, not implementer judgment; Resolutions 1+2 are Sonnet workhorse-pass evidence calls — see Resolutions below)

Provider-agnostic. Pipeline phases bind to a CLASS; class resolves to a concrete model at dispatch time by reading `docs/governance/ROUTING-RANKING.md` (table of record), not a hardcoded table.

**Vocabulary decision: use the EXISTING canon rung names, no new tokens.** `super`/`power` are dropped entirely — see Resolution 2.

| Class (= existing rung) | Claude | Codex | Notes |
|---|---|---|---|
| Executive (was Supervisor, D34 2026-09-07) | fable | astra | final say, risk eval, irreversible acts. No `ultra`/`super` alias — plain rung name only, so the 3-way `ultra` collision (Codex effort level; caveman intensity; class name) never arises. |
| Orchestrator (aka Supervisor, D34) | opus | sol | decompose, dispatch, complex planning |
| Workhorse | sonnet | terra | normal coding/research/synthesis |
| Grunt | haiku | luna | routine writing, classification, summarization |
| Free grunt | — | — | already-canon term (`CONTEXT.md:36`): OpenRouter `:free`, gemini free, mistral free, `gpt-5.4-mini`. $0, never a subscription call. TEXT-ONLY, no tools. Fills Workhorse/Grunt slots only in **budget modality**; not a 5th rung. |

Maps 1:1 onto D27's existing 4 rungs — because it IS D27's rung table, not a parallel one.

## Known collisions — RESOLVED

1. **`ultra` overloaded — RESOLVED.** No class is named `ultra` or `super`. The class is `Supervisor` (existing canon term). `ultra` keeps its two pre-existing meanings only (Codex effort level; caveman intensity).

2. **`free` — RESOLVED: free grunt stays a distinct, non-workhorse/non-grunt concept. No named free model is folded into Workhorse or Grunt.** Evidence:
   - **Reliability**: real OpenRouter probe run (D24/T9, `docs/DECISIONS.md:230`): `doctor.py` hit every free-tier route once — **0 ok, 17 fail, 6 quota**, i.e. 0/23 succeeded. The very next line (G8, fable, `docs/DECISIONS.md:234`) explicitly disclaims this as a capability verdict: "T9 probes 0/23 ok are NOT model verdicts... daily free cap hit... rerun after OR daily reset before trusting." So the one real-world sample of free-tier reliability is 0% success, and even that number is flagged as unusable evidence, not "clearance." There is no clean run to point to.
   - **The one positive-looking data point is explicitly disclaimed too**: `docs/governance/ORCHESTRATION-HANDOFF.md:9` — "gemini-lite NO DEFECTS = weak signal, not clearance." The record itself refuses to certify a free model as reliable from that result.
   - **Structural, not just evidentiary, gap**: `CONTEXT.md:42` (Scout roster) — "free grunts have no tools" by definition; the Grunt rung's actual job (per `CLAUDE.md` labor rule and the Scout roster split) routinely needs tools (repo walk, run cmd, file writes). A model that categorically cannot hold tools cannot substitute for Grunt on tool-bearing tasks regardless of text-quality — this isn't a probe result that could flip with more data, it's a capability class difference.
   - **Cost framing (D9, `docs/DECISIONS.md:15`)**: hard $0 cap with "quota out = pause"; free tiers pausing under quota is the documented normal case, which cuts against "reliable" on its own terms (availability, not just quality).
   - **Verdict**: no specific free model qualifies for promotion into Workhorse or Grunt on this evidence. `free grunt` stands as its own concept — consistent with existing canon (`CONTEXT.md:36`, "Free grunt"), which already treats it as a *budget-modality* fill-in for Workhorse/Grunt slots, not a class members of those rungs are promoted into permanently. Re-open only after a clean, non-quota-tainted probe run names a specific model at a specific pass rate.

3. **Class rename vs existing canon — RESOLVED BY OPERATOR RULING (2026-09-06), during this pass, after the implementer had independently reached the same conclusion.** Keep the existing canon vocabulary: Supervisor/Orchestrator/Workhorse/Grunt. Conform the new class scheme to it, not the reverse — `super` (and the earlier `ultra`) is now moot and MUST NOT be introduced anywhere; `power` likewise dropped. Final class names: **Supervisor** (fable, astra — replaces both `ultra` and `super`), **Orchestrator** (opus, sol — replaces `power`), **Workhorse** (sonnet, terra — unchanged), **Grunt** (haiku, luna — unchanged), **free** (pending, see Resolution 2). Why: `CONTEXT.md`, `docs/DECISIONS.md` D27, and `docs/governance/ROUTING-RANKING.md` already use these four names — one vocabulary, no canon file needs conforming, no P0 duplication introduced (the exact failure mode feature 007 is concurrently removing). The pipeline binds phases to these existing rung names, resolved at dispatch time from `docs/governance/ROUTING-RANKING.md`.

## Pipeline incompatibilities this fixes (verified in `~/.claude/skills/speckit-pipeline/SKILL.md`)

| # | Current | Evidence | New mode |
|---|---|---|---|
| 1 | `implement` hardcoded to haiku "per the repo's coding-dispatch binding" (= DomI's rule) | `SKILL.md:100`, policy table `:65` | binds to CLASS; codex side reachable |
| 2 | effort `high` on specify/plan/analyze | policy table `:56-64` | default medium (D29) |
| 3 | analyze retry loop capped at **3** cycles | `SKILL.md:120`, `:167` | **2** — repo retired the 3-count today (`ORCHESTRATION-HANDOFF.md:42`) |
| 4 | `clarify-surrogate` answers human clarify questions under `--yes` | `SKILL.md:111`, `:202` | disabled in new mode: halt for operator (P3 — surrogate answers then feed plan = self-graded input) |
| 5 | dispatch prompts carry no 14-element contract | policy table has no contract column | every dispatch built through the T003 checker |
| 6 | `preflight.sh` expects `.specify/scripts/bash/check-prerequisites.sh` | absent in this repo | new mode tolerates its absence |

## Dependencies

- **Blocks on 007 T003** (dispatch-contract checker). Without a deterministic checker, a mode is just more prose asking a model to remember 14 things — the failure P4 exists to prevent.
- Class→model resolution should read `docs/governance/ROUTING-RANKING.md` (table of record), not a hardcoded table (avoids the drift being fixed in 007).

## Where the work lands

DomI, as a **separate PR** from `fix/workerbee-canonical-source`. Different purpose; DomI enforces single-purpose PRs (`DomI/CLAUDE.md:146`). The workerbee PR adds an inbound-source policy (how DomI imports an external skill); this is the mirror case (how a consumer parameterizes a DomI-owned skill without copying it) — related, not the same purpose.

## Out of scope

- Touching `speckit-*` phase skills themselves; only the orchestrator's policy table + mode selection changes.
- Re-opening the `free` verdict without a clean, non-quota-tainted probe run (see Resolution 2).

## Resolution log addendum

Both naming collisions and the `free` question were resolved on repo evidence during implementation (2026-09-06, Sonnet workhorse pass) rather than deferred to the operator — see "Known collisions — RESOLVED" above for full reasoning and citations. The 007 T003 dispatch-contract-checker dependency noted above was carried forward as-is; this pass did not re-verify whether T003 has landed, since DomI-side scope in this pass touches only the policy table + mode selection (item 5 in the incompatibility table is unchanged, not re-verified).
