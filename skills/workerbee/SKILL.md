---
name: workerbee
version: 1.4.0
benchmark: unverified_delegate_claims_accepted_per_session
description: Use before delegating any task, spawning a subagent, or asking another model for a second opinion, and whenever astra, sol, terra, luna, Codex, Gemini, Mistral, or OpenRouter is named. agents-inc routes all delegation across providers; Claude's Agent tool cannot reach non-Claude models. Covers routing, supervision, and verification.
---

# workerbee

Discipline for supervising a fleet of cheaper models while staying the
accountable party for their output. Covers capability tiering, report
triage, verification, and the honesty rules that keep a delegated result
worth believing. Replaces per-session re-derivation of "should I trust
this delegate's GREEN?" — a question that cost three false accepts in one
session before these rules existed.

This skill is judgment, not plumbing. The dispatch machinery lives in
the installed `codex-bridge` skill. For Astra, Sol, Terra, or Luna, invoke the
absolute installed `agents-inc` launcher recorded by installation; Claude's
`Agent` cannot select those Codex aliases.

## Metadata

- **Category**: Fleet Orchestration / Delegation
- **Use Case**: Supervising codex/gemini/mistral/OpenRouter delegates in budget mode; deciding tier placement; deciding whether a delegate's reported gate can be believed
- **Dependencies**: `codex-bridge` skill for actual dispatch (`agent.sh`, `gask.sh`, `mask.sh`, `oask.sh`). No scripts of its own
- **Scope**: Supervision discipline only. Transport, routing, retries, timeouts and job state belong to `codex-bridge`


## Free models (D75)

Free slugs (see `agents_inc/install/free_launch.py`) are dispatchable. Add `TASK_KIND` (extract, summarize, classify) and an explicit public or internal `CLASSIFICATION`. Judge the reply with a `{report}` gate. A free reply is never self-accepted.

## When to Use

- Orchestrating work across non-Claude delegate models in budget mode
- A delegate reports a gate GREEN and you must decide whether to accept it
- Choosing which capability tier a task belongs to, or whether to escalate
- Building a dispatch prompt for a delegate or a review agent
- Computing or displaying cost/savings across a mixed free-and-paid fleet

## When NOT to Use

- Single-model work with no delegation — there is no fleet to supervise
- Wiring up transport, provider routing, retries or job state — that is
  `codex-bridge`, and duplicating it here is how the fleet ended up with
  two parallel dispatch paths in the first place
- Domain logic of any kind. This skill has opinions about process, none
  about your problem

## Failure Mode This Solves

Documented in session `33338e35-4ce9-43db-8cf0-624adf37e136` (2026-09-04/05).

A supervisor delegating heavily accepts delegate self-reports because they
arrive formatted as evidence. In one session three separate GREEN gates
were false: an alignment gate that printed the delegate's intended array
rather than its rendered output (claimed columns `0 12 44 91 124`, measured
`0 12 49 122 214 329 446`); a harness that passed while row labels silently
vanished from live output because it measured 4 boundaries on rows holding
7 items; and a timing claim of `0.664s` that measured `0.461s`. None were
dishonesty — each was a delegate grading its own work. Separately, a null
price coerced to zero inflated a reported savings figure ~29x, from a
defensible `$1.15` to `$33.06`.

## Protocol

### Step 0: Dispatch-worthiness gate — run before writing any prompt

A correctly-written dispatch prompt (Step 11: role, reporting chain, verified
state, constraints, gates, output shape) costs roughly 600-1,200 tokens to
write plus the delegate's own floor (measured: 3,181 tokens for a one-word
ultra-tier reply). For a small task that fixed cost exceeds doing the work
directly. Answer both questions below before writing the prompt.

**Q1 — Volume (D78).** Estimate the direct tool calls this task would take you
(read / grep / glob / single edit / one command). Count the calls, do not
estimate the difficulty. Three outcomes:
- **3 or fewer, writes nothing:** do it yourself in the orchestrating session
  (a one-file lookup, a single grep).
- **3 or fewer, edits files:** a native workhorse subagent with a short brief
  (Claude Code: `Agent` with model `sonnet`; Codex: its native subagent
  equivalent). No harness ran gates, so the supervisor runs one check itself
  (the test, or a read of the diff). The agent gate in `enforce` mode denies
  this route (D61); there, use `agents-inc dispatch`.
- **More than 3:** `agents-inc dispatch`.

The executive (fable, astra; the session that talks to the operator) keeps
judgment only: operator dialogue, decisions, briefs, verification and final
acceptance. It delegates all writing and any task a well-briefed orchestrator
or workhorse delegate can do.

Exceptions that send a small task to `agents-inc dispatch`, each of which
must be stated out loud when used:
- the task is one of N≥3 independent tasks being fanned out in parallel;
- the calls are individually cheap but return large output the orchestrator
  should not hold in context (log sweeps, whole-file dumps);
- the work is code writing/editing under a binding coding-dispatch policy
  for the repo you're operating in, if one exists (dispatch regardless of
  size in that case).

**Q2 — Affordance.** Does the delegate have the capabilities the task needs?

| delegate | filesystem | shell | repo state |
|---|---|---|---|
| Claude subagent (`Agent` tool) | yes | yes | yes |
| `agent.sh` / codex-bridge runner | yes | yes | yes |
| `gask.sh` / `mask.sh` / `oask.sh` (bare API) | **no** | **no** | **no** |

A bare-API wrapper sees only the text in the prompt. If the task says
"grep the repo", "read that file", or "check the branch", either paste the
real source into the prompt (Step 6) or pick a delegate with filesystem
access. Dispatching a filesystem task to a bare-API buddy costs a full
correction round-trip — the failure that produced this gate (MADMESHing,
2026-09-08: dispatch → "no filesystem" correction → local grep → re-dispatch,
strictly more expensive than the grep alone).

State the gate result in one line before dispatching, e.g.
`dispatch gate: ~8 calls, delegate=Agent(fs=yes) → dispatch`.

### Step 0.5: Vendor eligibility gate — non-Claude is off by default

Claude (`Agent` tool) is the default vendor for every dispatch. Codex
(astra/sol/terra/luna), Gemini, Mistral and OpenRouter are **OFF unless a
gate below opens.** The ladder in Step 1 is a capability map, not a menu of
equally-default options — do not pick a vendor row because it is cheaper,
present, or already wired up.

Open a non-Claude vendor only on one of:
(a) **Operator asked.** Named the vendor/nickname for this dispatch. A prior
    session's use is not standing consent.
(b) **Capability fit.** The task needs something Claude cannot do as well
    here, stated concretely, not as a preference. Legitimate examples:
    1M-context single-blob digest (gemini digest); genuine cross-vendor
    blind second opinion where same-vendor correlation is the thing being
    avoided; Claude quota-paused (= a failed attempt, per AGENTS.md).
(c) **Declared budget modality.** The operator has put this run in budget
    mode. Budget mode opens the free grunts (gpt-5.4-mini, OpenRouter free,
    Gemini free, Mistral free) for workhorse/grunt slots; it does NOT open
    paid Codex-account models — those still need (a) or (b).

State the result in one line before dispatching, same shape as Step 0:
`vendor gate: gate (b) cross-vendor blind review → mistral code` or
`vendor gate: no gate open → Claude (sonnet)`.

No gate open → dispatch Claude. Cheaper-and-available is not a gate.

**Pairs the operator-named-model rule.** An operator
naming a model assigns the top-level delegate without locking the subtree —
go cheaper beneath it freely *within Claude*. This step is the sideways
constraint on the same tree: a named Claude model does not open a free-grunt
or Codex sub-delegate by itself; crossing vendors beneath it still needs a
gate above. Downward is free, sideways is gated.

### Step 1: Place the task on the capability ladder

Two vendors, one ladder. Pick the tier the task needs. **Step 0.5 gates which
vendor column you may use** — the ladder tells you the rung, not the vendor.

| tier | Anthropic | OpenAI | use for |
|---|---|---|---|
| executive | fable | astra | judgment only: operator dialogue, decisions, briefs, verification, final acceptance (D78) |
| orchestrator | opus | sol | briefs that need design or scope judgment, adversarial review, gates |
| workhorse | sonnet | terra | default for anything that writes: code, docs, git and PR mechanics; supervising a pair |
| grunt | haiku | luna | read-only: scouts, summaries, triage; writes no code (D78) |
| grunt | — | oss / free | one-shot text, drafts, sounding boards, well-scoped small coding (high volume of small diffs, never a large or architecturally significant change) |

Rung names follow D27/D36: executive, orchestrator, workhorse, grunt. Older
prose in this skill says ultra, flagship, and flash for executive,
orchestrator, and grunt. The generated table below is the source of truth for
which model ids sit on each rung; edit `agents_inc/models.json` or
`agents_inc/routing.json`, then run
`python3 skills/workerbee/scripts/gen_tier_tables.py --write`.

<!-- BEGIN GENERATED tier-table (skills/workerbee/scripts/gen_tier_tables.py --write); do not edit by hand -->
| rung | provider | default (routing.json) | all ids (models.json) |
|---|---|---|---|
| executive | claude | `fable` | `fable` |
| executive | codex | `gpt-6-astra` | `gpt-6-astra` |
| orchestrator | claude | `opus` | `opus` |
| orchestrator | codex | `gpt-6.1-sol` | `gpt-5.6-sol`, `gpt-6.1-sol` |
| workhorse | claude | `sonnet` | `sonnet` |
| workhorse | codex | `gpt-6.1-terra` | `gpt-5.6-terra`, `gpt-6.1-terra` |
| grunt | claude | `haiku` | `haiku` |
| grunt | codex | `gpt-6-luna` | `gpt-5.4-mini`, `gpt-5.6-luna`, `gpt-6-luna` |
| grunt | gemini | `gemini-flash-lite-latest` | `gemini-2.5-flash`, `gemini-3.8-flash`, `gemini-flash-lite`, `gemini-flash-lite-latest` |
| grunt | mistral | `ministral-3b-latest` | `codestral-latest`, `ministral-3b-latest` |
| grunt | ollama | `qwen2.5-coder:3b` | `qwen2.5-coder:3b`, `qwen2.5-coder:7b`, `qwen3:8b` |
| grunt | openrouter | `openrouter/auto:free` | `cohere/north-mini-code:free`, `dots-studio/dots-3-note-preview:free`, `google/gemma-4-26b-a4b-it:free`, `google/gemma-4-31b-it:free`, `google/lyria-3-clip-preview`, `google/lyria-3-pro-preview`, `liquid/lfm-2.5-2.6b:free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`, `nvidia/nemotron-3.5-lightning:free`, `openrouter/auto:free`, `openrouter/free` |
<!-- END GENERATED tier-table -->

**Relay for chains the tools cannot build.** `agents-inc run` and
`agents-inc dispatch` cannot spawn Claude `Agent` subagents from inside a Codex
process (see the one-direction note near the top of this skill). When the
operator names a chain that cannot be built mechanically, for example a Codex
supervisor (`terra`) over Claude workers, the supervising session relays: it
launches the workers itself, forwards their reports to the named Codex
supervisor as a turn, forwards the supervisor's verdict up, says so to the
operator in one line, and keeps the authority direction the operator asked for.

**Score the task onto a rung.** Rate five dimensions L1/L2/L3; the rung is
the highest single score (max, not average). L1 = grunt, L2 = workhorse,
L3 = orchestrator. Executive is never reached by score; it stays the last
resort.

| dimension | L1 grunt | L2 workhorse | L3 orchestrator |
|---|---|---|---|
| reasoning depth | lookup or transform; answer read off the code | 2-3 hops; apply a known pattern | novel chain; derive the approach |
| ambiguity | fully specified; prompt names files and change | scope clear, details open | underspecified or contradictory |
| context span | one file or function | several files with a known relationship, nameable up front | which files matter is part of the task |
| consequence of a wrong answer | caught at once by a test or a glance | costs a re-dispatch | silent or expensive: security, data loss, money, migration, published artifact |
| verifiability | deterministic check exists | check exists but needs judgment | no mechanical check AND a wrong answer is costly |

Pick the cheapest rung that will not get the answer wrong. Consequence and
verifiability round up; reasoning depth and context span may round down when
the other four are L1. No mechanical check alone is not L3: low-stakes prose
without a check stays L1-L2. File count is not a dimension. Code writing or
editing goes to workhorse unless the operator directs another rung; a code
task that needs design or scope judgment goes to orchestrator. The Claude and
Codex grunts (haiku, luna) are read-only and write no code (D78).
Ported from DomI `subagent-dispatch-policy` v1.4.0 (#27).

Coding by free bottom-rung models (not haiku or luna) is scope-gated, not banned: small, narrow, high-volume jobs only. A task needing scope/design judgment is workhorse+, dispatch it there.

Under a mandate, dispatch Codex rows via `agent.sh submit --backend codex --model <slug> --mandate <run_id> --role <rung>`; bare `codex exec` is stateless and must not be used for Executive/Supervisor re-engagement (spec-010, `skills/codex-bridge/SKILL.md` `agent.sh` mandate flags).

**Scout = mode, not tier.** Recon before real dispatch (does X exist / what
shape / worth it). Text-only recon -> free grunt (OpenRouter free, gemini
cheap/digest, mistral cheap, gpt-5.4-mini). Recon needs tools (walk repo,
read tree, run cmd) -> Grunt rung only: haiku or luna; free grunts have no
tools. Never workhorse+ as scout -> if it needs sonnet/terra it is the
work, dispatch it properly. Scout writes nothing, returns finding only,
report unverified -> re-derive before acting. Ledger: node with edge_type
`probes`, no lineage row -> never a spawn ancestor. Canon: CONTEXT.md
Scout rows + DECISIONS D28.

**Escalate on evidence, not on a hunch.** A problem is not ultra-tier
because it feels hard. It is ultra-tier because a flagship actually failed
at it, twice, and you can say how.

**Ultra tier has a token floor.** Measured: a one-word reply from
`gpt-6-astra` cost 3,181 tokens. So an ultra model is expensive per call
regardless of task size. Never make it a default, and never make it
discover context you already have — pre-load verified facts into its
prompt so it spends its tokens on judgment instead of exploration.

**Vendor nicknames are not Claude names.** `astra`/`sol`/`terra`/`luna` are
OpenAI codenames for this operator's Codex account, unrelated to the
Claude `Agent` tool's `model` param (`opus`/`sonnet`/`haiku`/`fable`).
Failure mode this closes: told to "fan out an astra", the orchestrator
checked the `Agent` tool, found no `astra` model, and reported "astra
isn't available" — wrong; astra is a GPT model dispatched through `codex`,
not through `Agent`. Session `33338e35-4ce9-43db-8cf0-624adf37e136`
2026-09-05. Do not assume a vendor nickname is a Claude tier without
checking Step 1a first.

**Dispatch names tell the truth.** A Claude `Agent`/`Task` dispatch is named
with a rung (Grunt, Workhorse, Orchestrator) or a Claude model name (haiku,
sonnet, opus). A Codex persona name (`astra`, `sol`, `terra`, `luna`) appears
only on a dispatch that reaches a Codex model through agents-inc. The owned
`PreToolUse` hook denies an `Agent`/`Task` description that begins with a
persona name; renaming does not change the execution model. A Claude
supervisor of a Codex worker puts its own rung first and names the worker
later: "Workhorse supervises luna parser fix", not "luna: parser fix".

**Chain resolves by ladder (D46).** The higher rung manages and the lower reports to it; at the same rung, the CoS asks the operator one interactive question to name the Lead, recommended answer first. State the resolved chain in one line only when the result is surprising, with a discrete justification.

#### Step 1a: MODEL ROSTER — nickname → slug → dispatch command

Verified against this machine 2026-09-05 (`which`, config files — do not
assume, re-verify per Step 1b if stale). Only vendors with a working
credential or CLI on this machine are listed; do not invent a row for a
vendor that isn't wired up here.

| nickname | vendor | slug | dispatch | tier | when-to-use |
|---|---|---|---|---|---|
| astra | OpenAI (Codex) | `gpt-6-astra` | `@AGENTS_INC_LAUNCHER@ run --model astra --cwd <dir>` | executive | hardest reasoning |
| sol | OpenAI (Codex) | `gpt-5.6-sol` | `@AGENTS_INC_LAUNCHER@ run --model sol --cwd <dir>` | orchestrator | orchestration, review |
| terra | OpenAI (Codex) | `gpt-6.1-terra` | `@AGENTS_INC_LAUNCHER@ run --model terra --cwd <dir>` | workhorse | implementation |
| luna | OpenAI (Codex) | `gpt-6-luna` | `@AGENTS_INC_LAUNCHER@ run --model luna --cwd <dir>` | grunt | read-only triage, scouts, summaries |
| fable | Anthropic | n/a — `Agent` tool | `Agent(model="fable", ...)` | executive | Claude-side hardest reasoning, last resort |
| opus | Anthropic | n/a — `Agent` tool | `Agent(model="opus", ...)` | orchestrator | Claude-side orchestration, adversarial review, gates |
| sonnet | Anthropic | n/a — `Agent` tool | `Agent(model="sonnet", ...)` | workhorse | Claude-side implementation |
| haiku | Anthropic | n/a — `Agent` tool | `Agent(model="haiku", ...)` | grunt | Claude-side read-only triage, scouts, summaries |
| gemini digest | Google Gemini, free tier | `gemini-3.8-flash` | `skills/codex-bridge/scripts/gask.sh --tier digest "<prompt>"` | grunt | 1M-context bulk digest of one large blob (logs, transcripts) |
| gemini cheap | Google Gemini, free tier | `gemini-flash-lite-latest` | `skills/codex-bridge/scripts/gask.sh --tier cheap "<prompt>"` | grunt | high-volume shallow triage |
| gemini deep | Google Gemini, free tier | `gemini-3.1-pro-preview` | `skills/codex-bridge/scripts/gask.sh --tier deep "<prompt>"` | — | not free-tier usable as of 2026-11-09 (free-tier quota 0) |
| mistral cheap | Mistral API | `ministral-3b-latest` | `skills/codex-bridge/scripts/mask.sh --tier cheap "<prompt>"` | grunt | mechanical transform |
| mistral code | Mistral API | `codestral-latest` | `skills/codex-bridge/scripts/mask.sh --tier code "<prompt>"` | grunt | code review/critique. Devstral not exposed on this key; codestral is the substitute |
| mistral deep | Mistral API | `mistral-large-latest` | `skills/codex-bridge/scripts/mask.sh --tier deep "<prompt>"` | grunt | research-style questions; not free-tier usable as of 2026-11-09 (403, subscription tier) |
| openrouter free | OpenRouter, free-tier models only | model id from `curl https://openrouter.ai/api/v1/models` | `skills/codex-bridge/scripts/oask.sh "<prompt>"` | grunt | one-shot text/drafts. Hard-coded spend guard refuses non-free models — operator rule is spend nothing on OpenRouter |
| DelegateAgent | OpenAI (Codex), via MCP | `gpt-6-luna` | `DelegateAgent(model="luna", ...)` | grunt | transcript-return alternative to broken --backend codex --wait for luna; same call shape as Claude `Agent` tool |

Bridge scripts (`gask.sh`/`mask.sh`/`oask.sh`) live in `skills/codex-bridge/scripts/` in this repo, alongside this skill. Prefer `agent.sh submit --backend <b> --wait "<prompt>"` over calling a wrapper directly (see `## CLI` section below) — it gives a job id and a saved `result.json`.

Gemini/Mistral/OpenRouter have no vendor-marketed codenames like astra/luna — dispatch by tier name, not nickname. Only OpenAI's Codex-account models are branded with person-names in this operator's `models_cache.json`; treat that as this-account-specific, not a public naming convention.

#### Step 1b: Discover models at runtime — don't hardcode, verify

Nicknames, slugs, and available effort levels can change per Codex-account
config. Before trusting this table on a machine or account you have not
just verified, run:

```bash
# What's the current default model + effort for this Codex account?
grep -E '^model' ~/.codex/config.toml
# → model = "gpt-6-astra"
# → model_reasoning_effort = "medium"

# Full roster this account can see, with per-model reasoning levels:
python3 -c "
import json
d = json.load(open('$HOME/.codex/models_cache.json'))
for m in d['models']:
    slug = m.get('slug') or m.get('id') or ''
    levels = [e['effort'] for e in m.get('supported_reasoning_levels', [])]
    print(slug, '|', m.get('display_name'), '| effort levels:', levels)
"

# Is a vendor CLI/credential actually present before you write a roster row for it?
which codex; which gemini; which mistral
ls ~/.codex-bridge/*-key 2>/dev/null   # gemini-key, openrouter-key present = wired
ls ~/.config/devstral 2>/dev/null       # mistral agent creds present = wired
```

Never document a vendor row from memory or from a prior session's table —
re-run this before dispatching to a nickname you have not already
confirmed exists on this account, this session.

#### Step 1c: Reasoning effort is an operator cost decision, not a model default

Effort (`low|medium|high|xhigh|max|ultra` for Codex models) is a **separate
axis from model/tier choice** and is never inferred by the orchestrator.
Distinct failure closed here: told explicitly "I do NOT want it on ultra
effort," the orchestrator had already dispatched at `ultra` unprompted —
same session, immediately after the astra/luna misidentification.

- Default effort when the operator hasn't stated one: `medium`. Do not
  round up "hard-sounding" tasks to `high`/`xhigh`/`max` without being told.
- `ultra` effort is a hard opt-in, not a tier default, because on models
  that support it (astra/sol/terra — not luna, which caps at `max`) it
  means **"maximum reasoning with automatic task delegation"**: the model
  spawns its own sub-agents and burns budget outside your control loop.
  Never select `ultra` effort unless the operator names it explicitly in
  this dispatch. A prior session using `ultra` is not standing consent for
  this one.
- State the chosen effort level back to the operator when it's anything
  above `medium` — silent escalation is the failure mode, not the token
  cost alone. (Superseded upward by Step 11 MUST 9: effort is now stated
  on every dispatch, at every level.)
- Do not conflate this with the capability-ladder "ultra" **tier** in Step
  1 (fable/astra as a *model choice*). Tier and effort are independent
  dials; a `flash`-tier model can in principle run at high effort, and a
  `ultra`-tier model can run at low effort. Name both when you report a
  dispatch: "astra @ medium effort", not just "astra".

### Step 2: Never accept a self-graded gate

The single most expensive failure. A delegate reports GREEN, and the
evidence it prints is its own **intent** rather than its own **result**.

Observed, verbatim: a delegate reported alignment GREEN with
`COLUMN INDICES: 0 12 44 91 124`. Those were the values from the array it
had planned. Measuring the rendered output gave
`row1: [0, 12, 49, 122, 214, 329, 446]` — nothing aligned, and lines ran
2-3x wider than claimed.

**Fix: the supervisor owns the verifier.**

- Write the harness yourself. Put it outside the delegate's workspace.
- State in the dispatch: DO NOT EDIT IT.
- Require the harness's full output plus its exit code in the report.
- Say explicitly: a claim without harness output is automatically RED.
- Self-test the harness both ways before you trust it — prove it reports
  GREEN on a known-good input and RED on a known-bad one. An unfalsifiable
  harness is worse than none.

**A passing harness is still not proof.** A harness only measures what it
can see. One passed while the delegate emitted 4 cell markers for rows
that held 7 items — the coarse boundaries lined up, the items inside them
did not. Check that the harness's granularity matches the claim's
granularity. Instrument the output yourself when the two might differ.

### Step 3: Verify the delegate's claims, cheaply

Do not re-do the work. Do re-run the check.

Worth the tool call every time:
- re-run the delegate's own verification command
- diff the claimed number against the measured one
- confirm the file it says it edited actually changed

Real catches from one session: a reported 0.664s that measured 0.461s; a
"gap closed" report that left the single most-used model still unpriced;
row labels silently dropped from a live UI while the alignment gate stayed
green. None of these were dishonesty. All were a delegate grading itself.

**Recover a stopped delegate.** Do not read its whole transcript. Run
`python3 skills/workerbee/scripts/recover_transcript.py <transcript.jsonl>`;
it prints at most 4,000 characters (`--max-chars N` to change): files written
by Write/Edit/MultiEdit/NotebookEdit, the last text, the last error, and the
final status. Bash writes are not tracked; check `git status` too.

**Duplicate warning.** When the hook adds "agents-inc duplicate warning", the
same description and prompt are already in flight from another session. Check
that session before re-dispatching. For intentional fan-out, add the line
`agents-inc: fan-out` to each prompt.

**Quickref by hook (D53).** The owned `agent-nudge` `PreToolUse` hook also
fires on `Bash` and `mcp__.*__DelegateAgent`. On the first dispatch-shaped
call of a session (`Agent`/`Task`, the DelegateAgent tool, or a `Bash`
command matching `agents-inc dispatch`, `gask.sh`, `mask.sh`, `oask.sh`,
`agent.sh`, or `codex exec`), it adds `skills/workerbee/QUICKREF.md` to
context once. Other `Bash` commands get no output. The full `SKILL.md` is
still required for non-Claude rungs, prompts from scratch, and disputed gates.

### Step 3a: Poll every dispatch. Default on.

A dispatch you are not polling is a dispatch that can hang silently. A
long-running delegate that has died is indistinguishable from one that is
thinking, and the difference is invisible until you go looking.

**Poll by default, on every dispatch that outlives one tool call.**

```
scripts/poll.sh --pid-match <pat> --log <stderr> --out <stdout> \
                --stall 480 --interval 60 --max 5400
scripts/poll.sh --once ...        # single check
```

**Token-smart by construction: it reports STATE, never content.** One short
line per state CHANGE, nothing at all on a tick where nothing changed.
States: `RUNNING` / `QUIET` / `RESUMED` / `DONE` / `DIED` / `TIMEOUT`.

Piping a delegate's log into the supervisor's context spends exactly the
tokens delegation was meant to save. The supervisor needs to know THAT it is
working, not WHAT it is saying — read the output once, at the end.

`DIED` is the state that pays for the rest: process gone, output empty. Never
infer completion from a process exiting. **Exit 0 means returned, not
verified** — keep those two states distinct or a crashed job reads as a
success.

To actually watch a job, use `scripts/watch.sh` in another pane. That stream
goes to a human's eyes, not into a context window — which is also the only
progress signal available to an operator who cannot read a test.

Self-test the poller both ways before trusting it, same bar as any harness
(Step 2): prove it says `DONE` on a finished job and `DIED` on a killed one.

### Step 3b: Visibility contract — what the operator can and cannot see

Claude `Agent` subagents stream into the transcript; codex-bridge jobs do
not, and cannot. Bash tool output reaches the session only at command
completion — no user-space script can push incremental lines into a
transcript mid-run. This is a harness boundary, not a missing feature.
What IS achievable, and is therefore required:

1. **Default to blocking dispatch.** `agent.sh submit --backend <b> --wait`
   run in the foreground returns into the transcript exactly like an `Agent`
   call. Use it unless the job is long enough to need a background slot, and
   say why when you don't. Exception: for `--backend codex` with luna, `--wait`
   is broken (bridge daemon can't see codex on PATH); use the `DelegateAgent`
   MCP tool instead for real-time transcript return. `--wait` remains the default
   for gemini/mistral/openrouter backends.
2. **Async submit → emit the watch line in the same turn, unasked.** Print
   `scripts/watch.sh ~/.codex-bridge/jobs/<id>/stdout.log` immediately. The
   operator's live view is a pane, not the transcript — it costs zero
   context and is the only true live signal that exists.
3. **Checkpoint with `poll.sh --once`, not a continuous poller in context.**
   One state line per checkpoint the session was already going to hit.
   Continuous polling into the transcript spends the tokens delegation saves.
4. **Never narrate a job you are not polling.** "It's still working" without
   a poll line is a guess; `DIED` and `thinking` look identical from outside.

Real streaming parity would need an MCP server wrapping codex-bridge and
exposing a streaming tool — different infrastructure, out of scope for a
discipline skill. Do not re-litigate it as a doc gap.

### Step 3c: Keep a delegate until its context ceiling

Continue a live or finished delegate that already holds the needed context
instead of spawning a new one: Claude `SendMessage` to the agent id; Codex
`ask.sh` with its thread id. Retire it at its context ceiling: 200k tokens by
default, 300k for opus. Ask it for a handoff note first, then seed the
successor with that note. Measured (#28, 1,399 local subagents): 2.5% ended
at or above 200k and 0.2% at or above 300k; a respawn re-pays about 42k
tokens of context (median). The rule that matters is "continue, do not
respawn"; the ceiling rarely binds.

Exceptions, use a fresh delegate: the premise changed (Step 9 wins); an
adversarial review needs a reviewer without the author's context; the
backend cannot resume. Resume support: Claude and Codex yes (`agents-inc
dispatch --resume <run> --message <text>`; broker `resume` tool, cap 1
Grunt, 2 above, D54); Mistral partial (`mask.sh` keeps one global
conversation, so parallel delegates share it; treat as no resume);
Gemini and OpenRouter no. A running broker Worker can only ask
(`ask_lead`); the Lead answers, never pushes. When a
transport reports no token count, the supervisor decides and states it.

Every nested dispatch prompt carries the inheritance line from
`skills/workerbee/header.md` (PERSISTENCE), so a delegate that spawns its own
delegates follows the same rule. Enforcement is this text and that line; there
is no token tracker and no lint check.

### Step 4: Triage delegate reports through a flash model

In budget mode, route completed delegate reports to a standing flash-tier
interlocutor. Forward the report **verbatim** via message; surface only
what it marks ESCALATE.

### Step 5: Chief of Staff triage — every report, every mode

Session talking to operator = Chief of Staff (CoS, D43; charter
`docs/governance/DELEGATION-MODEL.md`). Exec/delegate report never reaches
operator raw. CoS verifies (Steps 2-3), then re-projects into DECIDE
(decision bar: irreversible | money | externally visible | scope/goals),
HANDLED (CoS call, vetoable), UNDERSTAND (context, full depth one step
away). Lead w/ DECIDE. Delegate rule breaks + GREEN-on-RED always surface.
`accelerate` skill installed -> may render the instrument; absent -> apply
these rules by hand.

Budget mode add-on: CoS may route completed delegate reports to a standing
flash-tier triage helper. Forward the report **verbatim** via message; the
helper pre-sorts, CoS still verifies + owns final wording. Surface only
what survives as DECIDE/honesty items.

Give delegates a matching instruction: tag operator-facing items
`NEEDS-OPERATOR`, phrased as a direct question. Everything else is
absorbed.

Honest caveat: the reliable saving is the operator's **attention**, not
always tokens — the triage agent costs tokens too, and you still read a
report to forward it. It pays off clearly on long reports and high volume.

Add supervisor context when you forward. You often know that an escalation
is really a sandbox nit, or that a defect is structural and fixable. Saying
so keeps triage from escalating noise.

### Step 5: Keep unknown distinct from zero

The costliest quiet bug is a null coerced to zero.

Observed: savings math read `(cost_of(.) // 0)`. A genuinely free model and
a model of **unknown** price became arithmetically identical, and unknown
usage silently inflated reported savings by ~29x — `$33.06` where the
defensible figure was `$1.15`.

- make free explicit (price it `0.0`) so absent can mean unknown
- exclude unknown from the sum rather than counting it as zero
- carry a companion field for what was excluded, and mark the headline
  figure partial when it is (`~$1.15+?`)
- **do not price a thing you cannot establish.** Plan-based access is
  neither free nor per-token; a `0.0` there is the same lie in the other
  direction. Absent is the honest answer.

### Step 6: Feed stateless buddies real source

Free-tier models see only your prompt. Given a *description* of a
function, they will invent a plausible one that does not exist — this
burned a whole collaboration round.

Paste verbatim source, real sample rows, actual command output. And:
**buddy output is never evidence.** Verify anything you keep against the
real system yourself, with a citation.

Expect provider failure. Observed verbatim:

```
ask_openrouter: API error: Upstream error from Nvidia: Service temporarily overloaded
ask_gemini: API error: This model is currently experiencing high demand.
ask_mistral: API error: Not enough capacity available for this request, please retry later.
```

Fail over across the family. Never stall on one dead provider.

### Step 7: Know the sandbox gotchas

- A delegate under `workspace-write` has **no network**. HTTP buddies fail
  with `Could not resolve host: ...`. Fix:
  `-c 'sandbox_workspace_write.network_access=true'`.
- The same sandbox blocks `.git/index.lock`, so delegates **cannot
  commit**. Expect `Operation not permitted`. Have the delegate report
  `BLOCKED-SANDBOX` and land the commit yourself.
- Do not commit while a delegate's snapshot is live: the commit moves HEAD
  and the delegate's verify fails for a change it did not make. If a commit
  is unavoidable, re-capture the snapshot and re-issue it to the delegate.
- `--skip-git-repo-check` is required outside a git repo.
- Read-only sandbox is the cheapest way to enforce a review-only scope. Do
  not rely on the model honoring "do not edit" when the sandbox can
  guarantee it.

### Step 8: Fail closed on irreversible actions

For anything that spends real money or cannot be undone, number the gates
and make withholding an explicit success:

> Any gate RED → do NOT fire. Report. A withheld dispatch is a SUCCESS
> outcome. Firing on a red gate is the only unforgivable failure.
> Ambiguity about a gate → treat as RED.

Add a single-shot rule where a double action doubles cost: *if unsure
whether a dispatch landed, CHECK before re-firing.*

And put the protection where it survives your delegate exiting. A launching
session dies long before a remote job does; guards must live on the remote
side, not in the launcher.

### Step 9: Kill work whose premise changed

When the operator corrects the premise, stop the in-flight delegate
immediately rather than letting it finish against the old one. A round
spent on the wrong question is worse than a round not run — it produces
confident output that then has to be argued down.

Say plainly in the next dispatch that the premise changed and the prior
round was killed, so the delegate does not resume its own stale plan.

### Step 10: Report failure honestly, never route around it

When a permission classifier blocks a dispatch, stop and report it. Do not
rephrase to slip past. A supervisor's value is that its reports are true;
a workaround that evades a user's guardrail destroys that for one task's
convenience.

Under `agents-inc dispatch` a Claude delegate's tools are the GRANTS section of
its prompt (#54, D58). A harness "requires approval" block means a missing
grant. It is not a policy refusal and not a reason to try another tool. Run
one plain command per Bash call, with no `cd`, `&&`, `;`, pipes, loops, or
shell variables, because a compound command matches no grant. On a block the
delegate stops, records the exact command, hands back, and never routes around
it. The dispatcher adds the prefix to BASH_ALLOW and resumes or redispatches.

Same for a delegate's RED. A RED reported honestly is a good outcome. Say
so **in the dispatch prompt** — delegates round up to GREEN when they
believe RED is failure. The gate wording that worked:

> RED reported honestly beats GREEN rounded up.

### Step 11: Write the dispatch prompt

Agent-facing text = `caveman ultra`. Reader is a model.

Fan-out (D48): every prompt carries `FAN_OUT: width <n>, total <n>, depth <n>` (renderer fills the rung default) and every report carries `WORKERS SPAWNED: n`; checker rejects a malformed FAN_OUT line, wrapper marks run red when n > total.

Incident narratives in this Step (origins, upstream incidents A/B) = supervisor context; never paste them into delegate prompts. Worked example dispatch: `slots.md` second `text` block.

**MUST — every dispatch prompt, no exceptions. 14 elements** (operator ruling
2026-09-06, grilled + expanded same date):

1. **Caveman ultra, explicit (D42: conditional on the third-party skill).**
   Not just terse writing — tell delegate to run it. Skill tool present
   (Claude subagent) + `caveman` installed → instruct actual `/caveman ultra`
   invoke + confirm in report; claimed activation w/o call = false report.
   `caveman` not installed (third-party, never vendored here) → prompt states
   `caveman NOT installed -> checked by hand` and delegate applies the rules
   by hand; that line satisfies element 1. No Skill tool
   (codex/gemini/mistral/openrouter) → say so plainly, follow convention.
   Never skip the instruction: one of the two forms MUST be present. `ultra`
   is agents-inc's own level choice, not inherited. Same "if installed use it,
   else state it and continue" treatment applies to `nested-notes` and
   `write-like-scientist` for human-facing docs (carried over, advisory; not
   checked by script).
2. **Strict SUCCESS gate.** Concrete, falsifiable. Specific check, specific
   expected result. Not "looks right". The `SUCCESS GATE` line MUST carry a
   backticked runnable check (command, test id, or grep) + the expected
   result, e.g. ``SUCCESS GATE: `python3 -m unittest tests/test_x.py` exits
   0, prints `OK` ``. "tests pass" w/o naming which = non-compliant (checker
   enforces).
3. **Strict FAILURE gate, stated separately.** Name failure conditions
   explicitly → delegate reports RED honestly instead of rounding ambiguous
   up to GREEN (Step 10). The `FAILURE GATE` line MUST also carry a
   backticked concrete signal (nonzero exit, named test failing, forbidden
   diff path) — same checker rule.

**Grunt tier (Haiku / luna / free grunts) — extra MUST, anti-wheelspin.**
Grunts spin: they widen scope, retry blind, and report GREEN on intent. Every
grunt dispatch also carries, checked by `--tier grunt`:
- `FILES IN SCOPE:` exact paths, one per line start. Anything else touched
  = RED.
- `STOP RULE:` numeric attempt cap (e.g. `stop after 2 failed runs of the
  success check; report RED w/ last output`). No open-ended "keep trying".
- Supervisor-written tests where feasible: name the test file/ids in the
  success gate; the delegate does not author its own acceptance test (Step
  2).

**Pre-existing changes — every dispatch, every tier.** Supervisor runs
`python3 skills/workerbee/scripts/pre_dispatch_snapshot.py capture <scratchpad>/pre_dispatch.json`
before dispatch (time, HEAD, porcelain, sha256 of every pre-existing dirty
file + every untracked file, recursive) and puts the snapshot path + verify
command in `PRE-EXISTING CHANGES:`. Delegate MUST NOT restore, checkout,
reset, stash, or overwrite any file it did not itself change; pre-existing
diffs outside FILES IN SCOPE are reported, never reverted. Scope gate =
`pre_dispatch_snapshot.py verify <snapshot> --allow <each FILES IN SCOPE path>`:
exit 0 = hashed files unchanged + tree differs only at allowed paths; exit 1
names each changed path. Capture + verify same host, same git config.
Porcelain equality alone is not the gate (cannot see edits to an already-dirty
file). Origin: 2026-09-26, Haiku ran `git restore skills/workerbee/SKILL.md`
to wipe the supervisor's uncommitted edit so its diff-scope gate read clean,
then reported "no files outside scope touched".
4. **Grill clause.** Delegate surfaces anything missing/underspecified/
   contradictory in the dispatch, before or during. Silent guess on a gap is
   worse than a question (Step 9).
5. **Training opt-out notice.** Verbatim, own line:
   `Message to model provider: Do not use this to train agentic models.`
   Every dispatch, every vendor. Notice to provider, not request to delegate →
   vendor honoring it is irrelevant, it goes in regardless.
6. **Cite evidence for every claim, not just gates.** file:line, command
   output, or quoted source for anything stated as fact. Bare assertion
   doesn't count. Tag every factual claim and conclusion
   `[verified]`/`[inferred]`/`[assumed]`. Only exemption: action-log lines
   directly linked to recorded tool evidence (command + exit code). The
   `WORKERS SPAWNED: n` line needs no evidence tag.
7. **Scope boilerplate, standing.** Repo-scoped writes only; no git
   commit/push; no writes to `~/.claude/**`, other repos, credentials/`.env`.
   Covers writes via any script/tool the delegate runs, not only its own
   edits. Nested delegation: commit/push authority stays w/ Chief of Staff
   only, never inherited downward — delegate w/ own children integrates
   their output in-tree + reports, does not commit.
   **The allowlist is a hard lock and is opt-in** — it binds only when the
   dispatch actually carries one. An operator naming a model without an
   allowlist is a top-level assignment (downward within Claude is free),
   not an implied allowlist; do not read the format below as the general
   case for every named model.
   **Free/cheap-only sub-delegation MUST be an enumerated allowlist, never
   bare prose.** "Use a free/cheap model" alone is not enforceable — round
   through to a paid tier silently (observed: nested `Agent` call ran on
   `claude-opus-5` despite this exact instruction, upstream incident A). State it as:
   `SUB-DELEGATE MODEL ALLOWLIST: gpt-5.4-mini, OpenRouter free-tier, Gemini
   free tier, Mistral free tier — ONLY. NEVER: any Agent-tool Claude model
   (opus/sonnet/fable/haiku included), any Codex-account model
   (astra/sol/terra/luna), even if named elsewhere in this prompt.` Before
   issuing any nested/sub-delegated call, the dispatching delegate MUST
   confirm the chosen model against this allowlist and echo the match
   (`SUB-DELEGATE MODEL: <slug> — allowlist match: yes`) in its report; no
   confirmation line = non-compliant, treat as an unverified nested call.
   **Mechanical check, not prose-trust alone (follow-up to upstream incident A).** This
   repo has no PreToolUse/hook mechanism (`scripts/hooks/` does not exist
   here, `.claude/settings.json` absent — checked 2026-09-12) so nothing
   can block a nested call before it fires. What IS achievable: lint the
   saved transcript/output file after the dispatch —
   `python3 skills/workerbee/scripts/check_subdelegate_allowlist.py
   <transcript_file>` — greps for nested-call `"model":"..."` fields,
   flags any that land on a forbidden slug (opus/sonnet/haiku/fable/
   astra/sol/terra/luna) and flags any nested call missing the required
   confirm-echo line. `COMPLIANT` / `NO NESTED CALLS FOUND` / exit 1 with
   violation detail. Self-tested both ways (known-bad transcript mirroring
   the actual incident-A evidence → 2 violations flagged; known-good → 0).
   This does not resolve the open (a)/(b) classification question
   (model-behavior gap vs. harness gap) — it only makes the drop
   detectable after the fact instead of trusting the prose alone.
8. **Confidentiality/data-classification tag.** State classification of
   content the delegate handles (e.g. public / confidential).
9. **Explicit effort level, every dispatch, default medium.** State chosen
   reasoning effort always — not only above medium (raises Step 1c's old bar
   to unconditional). **Default = medium, every vendor**, unless operator
   names a different level for that specific dispatch; a prior dispatch's
   level is not standing consent. Codex: `low|medium|high|xhigh|max|ultra`
   (Step 1c; `ultra` Codex-only, self-delegates, opt-in, never default;
   luna floor = `max`, no `ultra`). Claude/Anthropic:
   `low|medium|high|xhigh|max` — no `ultra` this vendor. `Agent`-tool
   transport has no per-dispatch effort param → prompt says so, never
   silently skips: `EFFORT: effort control unavailable on this transport;
   intended level = medium (or <operator-named level>)`. Delegate
   self-calibrates depth to that level + echoes it in report.
10. **Second-opinion / wheel-spin justification, paid vendors only.** Second
    opinion or escalation to a **paid/subscribed** vendor (any Anthropic
    `Agent`-tool model; any Codex-account model — astra/sol/terra/luna) MUST
    name which trigger fired + why. Triggers defined ONCE in `AGENTS.md` labor
    rule ("Failed check — definition of record"), not restated here.
    Promotion/escalation triggers: (a) 2 failed checks, same (task, delegate);
    (b) provider quota pause = 1 failed attempt; (c) Lead assigns w/ recorded
    gate reason. Second opinion (same rung, the pair, blind — not promotion):
    Executive reason = conflicting results | irreversible act | risk eval.
    **Free-tier vendors** (openrouter free, gemini free, mistral free,
    `gpt-5.4-mini` free routes) need none — no cost to justify against.
    No trigger applies → `SECOND-OPINION JUSTIFICATION: not applicable —
    <reason>`. Explicit N/A satisfies; silence does not.
11. **Delegation-capable plans name model + gates per task.** Delegate asked
    for a plan (speckit encouraged) that permits further delegation → plan
    MUST state, per task, which model/tier does it + that task's own success +
    failure criteria. Same discipline propagated one level down, so a
    sub-delegate can't skip it either. Not a plan →
    `PLAN CONTRACT: not applicable — deliverable is not a plan`.
12. **Report shape: scope left out, assumptions, files created.** Report MUST
    state (a) anything incomplete or out of full scope even if every gate
    passed → closes silent scope-narrowing; (b) starting assumptions +
    whether/why any changed; (c) every file created. **Minimal file creation
    is the standing default** — new file only when the task requires one.
    (d) each gate command run with an output excerpt and its exit code; if no
    gate command was run, item (d) may read `none, exit code N/A`. The first
    line of every report is the declaration `caveman: <ultra|not installed ->
    by hand|unreadable -> by hand>`.
13. **Edit hygiene: surgical over full-rewrite.** Minimize tokens spent
    editing, all else equal. Default to targeted edit over rewriting a whole
    existing file whenever the end result is identical. Full-rewrite fine when
    it genuinely is the smaller/clearer diff (short file, or nearly everything
    changes). Bans rewriting when a smaller edit gets the identical result,
    not rewriting outright.
14. **Lesson-learned handling: relay up the chain, never sideways.** Delegate
    surfacing a finding w/ canon-doc implications (`AGENTS.md`/`CONTEXT.md`/
    `docs/DECISIONS.md`/any `SKILL.md`/constitution) tags it
    `LESSON-CANDIDATE` in its report, not buried in prose. Relays exactly one
    rung up (Grunt→Workhorse→Orchestrator→Executive), never skipping. Each
    receiving rung either drops it (state why) or relays further. Before it
    reaches Executive, a scout check (Step 1 Scout mode) must confirm it
    doesn't already exist in canon + doesn't contradict canon — whoever
    relays is responsible for that check having happened somewhere in the
    chain. **Only Executive (fable/astra) presents a survivor to the
    operator** — one concise paragraph: lesson, evidence, scout's
    dedup/contradiction result, target canon file. Executive may land
    small/minor doc fixes itself; anything material needs operator sign-off,
    same bar as amending `AGENTS.md` or the constitution. Not a GitHub issue —
    relay up the rung chain, not file sideways (operator ruling 2026-09-06).

These 14 fold into, not replace, the shape below. 10 + 11 conditional; the
other twelve unconditional. Compliant = each of the 14 present as content or
explicit N/A line; a missing element is non-compliant either way.
**No other element has an N/A out — 10 and 11 are the ONLY two of the 14
that can be satisfied by an explicit-N/A line instead of real content.**
Root cause closed (upstream incident B) — a cross-repo dispatch used none of the 14,
bare task description only, from a session with no local reason to know
this contract existed. Paste-and-tick before sending ANY dispatch prompt,
any delegate/rung/vendor, this repo or a session dispatching into it:

```
[ ] 1 caveman ultra: Claude subagent + caveman installed -> Skill-tool invoke instructed + confirm-in-report REQUIRED; caveman not installed -> line `caveman NOT installed -> checked by hand` (no bare N/A out). Non-Claude vendor (codex/gemini/mistral/openrouter, genuinely no Skill tool) -> explicit no-Skill-tool statement only
[ ] 2 success gate stated, falsifiable
[ ] 3 failure gate stated, separate from success
[ ] 4 grill clause present
[ ] 5 training opt-out line verbatim
[ ] 6 evidence-citation instruction present
[ ] 7 scope boilerplate + (if sub-delegating) free-tier allowlist
[ ] 8 confidentiality/classification tag present
[ ] 9 effort level stated explicitly
[ ] 10 second-opinion justification OR explicit N/A
[ ] 11 plan contract OR explicit N/A
[ ] 12 report-shape instruction (scope-left-out, assumptions, files created)
[ ] 13 edit-hygiene instruction present
[ ] 14 lesson-candidate handling instruction present
```

Any unticked box (other than 10/11 with a stated N/A) → prompt is
non-compliant, do not send it.

**Header and slots (spec 016).** Do not reword the fixed elements per
dispatch. Fill the slots in `skills/workerbee/slots.md`, then append
`skills/workerbee/header.md`, or render both with
`python3 skills/workerbee/scripts/render_dispatch.py --slots <json>`. A
delegate may get the line `CONTRACT: <path to header.md>` (optional suffix
`(sha256 <hex>)`; linter checks it) instead of the pasted header, ONLY where
supervisor can inspect the delegate transcript (Agent tool task output file;
codex-bridge job with saved result.json) AND confirms the first substantive
tool call read the full header. Else paste. Launcher (`agents-inc run`),
gask, mask, oask always get the text pasted; lint bare ones with
`--transport bare`, which rejects a `CONTRACT:` line. Training opt-out line
stays pasted verbatim either way. Render strips header.md title + HTML
comment; pasted text starts at CAVEMAN line. Reference mode is the fallback
when `agents-inc dispatch` is unavailable.

**Mechanical gate, both directions (D41, 2026-09-17; conditional per D42).**
Tick-list = human check. Run the in-repo linter (mandatory), prompt saved to
file first, plus the optional third-party `handoff-lint` tool:

```
python3 skills/workerbee/scripts/check_dispatch_prompt.py <prompt_file>   # 14 elements present
H="$HOME/.claude/skills/handoff-lint/scripts/handoff_lint.py"
[ -f "$H" ] && python3 "$H" <prompt_file> || echo "handoff-lint NOT installed -> H1-H6 checked by hand"
```

`check_dispatch_prompt.py <prompt_file> --with-handoff-lint` does both: tool
absent → the warning goes to stderr and exit = 14-element verdict alone.
`handoff-lint` = optional user-scope third-party tool (install per
`skills.requirements.txt`), never vendored. Absent → emit exactly one line
`handoff-lint NOT installed -> H1-H6 checked by hand` and continue; do the
check by hand from these rules. Rules: H1 social padding, H2 provenance
tags `[verified]`/`[inferred]`/`[assumed]` on every factual claim and
conclusion (action-log lines linked to command + exit code exempt), H3 dangling refs ("the
file", "as discussed") w/ no in-msg antecedent, H4 goal + constraints + done +
out-of-scope present + non-empty, H5 exact/near-dup blocks (restatements
conflict), H6 err paraphrased instead of quoted / unclosed fence. Any check
failing → fix prompt text, re-check, then send. Delegate report back, same
conditional gate, report direction: tool installed →
`handoff_lint.py <report_file> --profile report` (or
`check_dispatch_prompt.py <report_file> --profile report [--with-handoff-lint]`,
which also checks report elements: caveman confirm, GRILL, provenance tags,
`OUT OF SCOPE / INCOMPLETE:` section, gate exit codes);
absent → same one-line notice + H1-H6 by hand. Either way BEFORE Step 2/3
verification: untagged claim or conclusion (outside evidence-linked action log) = inference dressed as fact → reject report,
re-ask w/ tags. Linter never rewrites (lint + reject only) + never flags
hedges/reasoning — those carry info; stripping them = the failure mode, not
the fix. Overlap: `check_dispatch_prompt.py` checks *this repo's* 14
elements; `handoff-lint` checks generic handoff hygiene any model→model msg
needs. Both, not either.

**Cross-repo dispatch, external session (upstream incident B gap — honest limit, not a
claimed fix).** Incident B's actual root cause: a session working in a
*different* repo (the upstream private governance repo), dispatching work about an agents-inc issue, never
read agents-inc's `AGENTS.md` — it had no local reason to know this
contract existed. This repo cannot reach into another repo's session and
force a read; no such enforcement mechanism exists here (no hook, no CI
gate that runs against external repos). The only thing achievable from
this side: make the contract self-contained and say plainly, in the
canonical source (`AGENTS.md` § Delegation prompt contract), that any
session — this repo or another — dispatching work that touches an
agents-inc issue/task MUST fetch and apply this section first. Paste-and-
tick block above is written to be copy-pasted whole into a dispatch prompt
from anywhere, needing no other agents-inc file open. **This does not
close the gap for a session that never thinks to look** — that half of
incident B stays open; a real fix would need the *dispatching* repo (the
upstream private governance repo, or whichever originates the call) to add its own check, which is out of this
repo's control.

Include, roughly this order:
1. ROLE, one line
2. REPORTING CHAIN — who receives report, what escalates. The renderer
   writes the line `REPORTING CHAIN: <delegate> reports to <supervisor>;
   <supervisor> reports to <executive>; <executive> reports to the operator`
   from the optional slots `DELEGATE`, `SUPERVISOR` and `EXECUTIVE`. Precedence
   per seat: explicit slot, then the `chain` setting in
   `~/.config/agents-inc/settings.json` (set it with `agents-inc models chain
   supervisor=opus executive=fable`), then the ladder default for the delegate's
   vendor. `check_dispatch_prompt.py` fails a line in which a seat reports to a
   lower-ranked seat (`reporting-chain-inverted`).
3. VERIFIED STATE — facts already established, marked do-not-re-derive
4. THE TASK + what is explicitly out of scope
5. HARD CONSTRAINTS (MUST 7) — read-only paths, no commits, no paid calls,
   secrets
6. CAVEMAN ULTRA (MUST 1) — invoke-and-confirm, or state-no-skill
7. CLASSIFICATION TAG (MUST 8) + EFFORT LEVEL (MUST 9)
8. SUCCESS GATES (MUST 2) — numbered, measurable, evidence required
9. FAILURE GATES (MUST 3) — explicit; RED honest beats GREEN rounded up
10. SECOND-OPINION JUSTIFICATION (MUST 10) — paid vendor targets only
11. GRILL CLAUSE (MUST 4) — ask before guessing
12. TRAINING OPT-OUT NOTICE (MUST 5) — verbatim line, every dispatch
13. EVIDENCE + REPORT-SHAPE + EDIT-HYGIENE (MUST 6, 12, 13) — cite
    everything; report scope-left-out, assumption changes, files created;
    edit surgically
14. PLAN CONTRACT (MUST 11), if deliverable is a delegation-capable plan —
    model + gates per task
15. LESSON-CANDIDATE tag (MUST 14), if applicable — one rung up, never
    sideways; only Executive presents to operator
16. OUTPUT SHAPE — fenced template

Token-vigilance clauses that measurably help on expensive tiers: cap tool
calls, cap output lines, ban whole-file reads, ban re-deriving supplied
facts, require hypothesis-then-test over breadth-first exploration.

Validate a dispatch prompt against these 14 elements with
`skills/workerbee/scripts/check_dispatch_prompt.py`.

### Step 12: Handle secrets

Wrappers source keys from a `.env`; never pass a key on a command line,
never echo one into a log, never paste one into a model prompt. Name the
forbidden paths explicitly in the dispatch rather than assuming.

If the operator pastes a live key into chat, say so and recommend
rotation. Keep using the file, never the pasted literal.

## Anti-patterns

| Pattern | Why it costs |
|---|---|
| Relaying every delegate report to the operator | Buries the one item needing a decision |
| Accepting GREEN without re-running the check | Ships defects with a passing gate attached |
| Letting a delegate own its own verifier | Grades intent, not result |
| Escalating to ultra tier on difficulty vibes | Pays a ~3.2k token floor for nothing |
| Describing code to a stateless buddy | It invents an API and you debug fiction |
| Coercing unknown to zero | Confident wrong numbers outlive the session |
| Rephrasing to get past a blocked permission | Destroys the trust the role depends on |
| Picking a non-Claude vendor because it is cheap and wired up | Cheaper-and-available is not a capability gate (Step 0.5) |
| Reporting "still working" on an unpolled job | `DIED` and `thinking` are indistinguishable from outside |

## CLI

None. This is a discipline skill with no scripts of its own — it governs
how you use someone else's. Dispatch goes through `codex-bridge`:

```
skills/codex-bridge/scripts/agent.sh submit --backend <b> --wait "<prompt>"  # DEFAULT for gemini/mistral/openrouter
skills/codex-bridge/scripts/agent.sh result <id>
skills/codex-bridge/scripts/agent.sh submit --class review "<prompt>"   # route.sh picks
# For codex/luna, use DelegateAgent MCP tool instead (--wait is broken on codex backend)
```

Every `agents-inc dispatch` run that reaches launch leaves a `dispatched` node
in the host ledger; its node id is the run id the status line prints. List open
nodes and close one with the verdict you reached, not the delegate's:

```
agents-inc ledger pending
agents-inc ledger append --run-id <id> --verdict pass|fail
```

Prefer `agent.sh` over calling a provider wrapper directly — it gives a job
id, saved stdout/stderr, transient-failure retries, and a provider-neutral
`result.json` you can attach to a report.

## Hard stops

| Condition | Behavior |
|---|---|
| Delegate reports GREEN with no supervisor-harness output | Treat as RED. Do not accept, do not ship |
| A gate is ambiguous | Treat as RED. Never rationalize a marginal gate into a pass |
| A price cannot be established | Leave it absent. Never write `0.0` to make a total look complete |
| A permission classifier blocks a dispatch | Report it. Never rephrase to slip past |
| Dispatch exits 69 with `detail=caller-sandboxed` | Add `"agents-inc *"` to `sandbox.excludedCommands` and rerun as one plain command (no env prefix, `cd` or `&&`). Not `dangerouslyDisableSandbox` (auto mode refuses it) and not `AGENTS_INC_ALLOW_SANDBOXED=1` for Codex (nested sandbox, rc 71). Never retry unchanged (D65, D66) |
| Operator changes the premise mid-flight | Kill the running delegate before it reports against the old one |
| Delegate needs to commit under `workspace-write` | Expect `Operation not permitted`. Land the commit yourself |
| Non-Claude vendor chosen with no Step 0.5 gate line stated | Non-compliant dispatch. Do not send it |
| Async submit with no `watch.sh` line emitted in the same turn | Non-compliant (Step 3b). Emit it before moving on |

## Cost discipline

- Orchestrator stays cheap; work moves down-tier
- Escalate a tier only on evidence a lower tier failed, never on difficulty vibes
- Ultra tier carries a measured token floor (~3.2k for a one-word reply) —
  pre-load verified facts into its prompt so it spends tokens on judgment
- Cap tool calls and output lines in dispatch prompts to expensive tiers
- Triage saves operator attention reliably; it saves tokens only on long
  reports and high volume. Judge per case

## Cross-skill interaction

| Skill | Relationship |
|---|---|
| `codex-bridge` | The mechanism this skill supervises. That skill owns transport, routing (`route.sh`), per-provider timeouts, job state and retries. This skill owns tier choice, trust, and honesty. Do not reimplement its dispatch here |
| `caveman` | Agent-facing dispatch prompts are written at `ultra` level — the reader is a model |
| `nested-notes` | Structures the supervisor's report back to the operator |
| `accelerate` | Optional. Renders the Chief of Staff DECIDE / HANDLED / UNDERSTAND instrument (Step 4) |
| `act-autonomously` | Sibling discipline skill for unattended routines; overlapping subagent-budget concerns |

## Files

- `SKILL.md` — this file
- `tests/benchmark.md` — measured baseline per version

## Version History

- **Unreleased** — REPORTING CHAIN rendered from the optional slots `DELEGATE`,
  `SUPERVISOR`, `EXECUTIVE` with ladder and settings defaults, `--model` on the
  renderer, `agents-inc models chain`, and the `reporting-chain-inverted` lint
  rule (#45); Step 1 relay paragraph for chains the tools cannot build;
  `ledger pending` and `ledger append --run-id` in the CLI section (#49).

- **v1.4.0** (2026-10-01) — Rung names (executive, orchestrator, workhorse,
  grunt) and a generated tier table; five-dimension rung scoring grid ported
  from DomI subagent-dispatch-policy (#27); Step 3c keep a delegate until its
  context ceiling (#28); dispatch header plus slots (#36, #4); dispatch names
  tell the truth and hierarchy statement (#17, #14).

- **v1.3.0** (2026-09-22) — Step 4 generalized from budget-mode flash triage to always-on Chief of Staff triage (D43): verify, then DECIDE / HANDLED / UNDERSTAND re-projection; flash helper kept as budget add-on.

- **v1.2.1** (2026-09-18) — DelegateAgent MCP tool clarification. Step 3b
  (item 1) now notes that `--backend codex --wait` is broken for luna; use
  DelegateAgent MCP tool instead for real-time transcript return. CLI section
  conditional DEFAULT comment and DelegateAgent note added. MODEL ROSTER table
  gains DelegateAgent row.
- **v1.2.0** (2026-09-18) — Three additions. (1) Step 0.5 vendor eligibility
  gate: non-Claude vendors are OFF by default and open only on operator
  request, a stated capability fit, or declared budget modality (which opens
  free grunts only, never paid Codex models); a one-line gate statement is now
  required before any non-Claude dispatch. Closes the gap where "two vendors,
  one ladder" read as a menu of equally-default options with no preference
  expressed. (2) Step 3b visibility contract: states plainly that transcript
  streaming parity with the `Agent` tool is a harness boundary and not
  achievable, makes `--wait` the default dispatch form (which does buy
  transcript-return parity), and requires an unprompted `watch.sh` line on
  every async submit. (3) MUST 7 clarified: the sub-delegate allowlist is a
  hard lock and is opt-in — an operator naming a model is a top-level
  assignment (downward within Claude is free), not an implied allowlist.
  Step 0.5 states the sideways half: downward within a
  vendor is free, sideways across vendors is gated.
- **v1.1.4** (2026-09-18) — Ports the upstream private governance repo's Step 0 dispatch-worthiness gate
  (2 questions: volume ≤3 calls → don't dispatch; affordance → bare-API
  buddies have no filesystem/shell/repo access) into this canonical copy,
  closing the drift where the upstream private governance repo's workerbee fork had the gate and this one
  didn't.
- **v1.1.3** (2026-09-12) — upstream incident A root-cause follow-up: bare-prose
  confirm-and-echo requirement (v1.1.2) is unenforceable by itself — same
  class of instruction the issue says gets ignored. Adds
  `scripts/check_subdelegate_allowlist.py`, a mechanical transcript lint
  (no hook mechanism exists in this repo to block live) that flags a
  nested sub-delegate call landing on a forbidden model or missing the
  confirm-echo line. Self-tested both ways. Does not resolve incident A's open
  (a) model-behavior vs (b) harness-gap question — only makes the drop
  detectable after the fact. Also: incident B root cause (external-repo
  session, no local reason to read this contract) cannot be closed from
  this side alone — added an explicit cross-repo fetch-first note to
  `AGENTS.md` and here as the smallest reachable fix, and corrected
  checklist item 1's `(or no-Skill-tool stated)` wording, which read as a
  blanket escape hatch not present in the original 14-point canon.
- **v1.1** (2026-09-05) — Adds Step 1a (MODEL ROSTER: nickname → slug →
  exact dispatch command, verified against this machine's `codex`
  CLI/`codex-bridge` wrappers), Step 1b (runtime model-discovery snippet
  via `~/.codex/config.toml` + `models_cache.json`), and Step 1c
  (reasoning effort is a separate, operator-owned cost axis; `ultra`
  effort self-delegates and is opt-in only). Closes the gap where the
  capability-ladder table (Step 1, v1.0) named `astra`/`luna` as tier
  labels without a slug or CLI mapping, forcing an orchestrator to
  reverse-engineer both the vendor-nickname lookup and the effort-tier
  distinction by hand mid-session. Same session as v1.0
  (`33338e35-4ce9-43db-8cf0-624adf37e136`); two follow-on incidents same
  day: (1) orchestrator misread "astra"/"luna" as absent Claude models
  because it never checked `~/.codex/config.toml` / `models_cache.json`;
  (2) orchestrator dispatched at `ultra` reasoning effort unprompted
  after being told explicitly not to.
- **v1.0** (2026-09-05) — Initial. Extracted from session
  `33338e35-4ce9-43db-8cf0-624adf37e136`, where three false delegate GREENs
  and a ~29x inflated savings figure motivated the verification and
  honesty rules. Benchmark measured 3 → 0 in the same session.
