<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Codex Bridge + Multi-Model Delegation Regime

**Branch**: `001-codex-delegation-regime` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-codex-delegation-regime/spec.md`

## Summary

Deliver a local delegation layer that lets a Claude session hand bounded instructions to two external backends — a persistent OpenAI Codex session reached over a localhost HTTP bridge, and Google Gemini reached over its REST API — such that bulk source material is read by the backend rather than passing through the Claude conversation. Around those two legs sits a documented routing policy that assigns classes of work to backends by cost, capability, and data-retention behavior, and a set of lifecycle scripts that make startup a single idempotent command with no manual transcription of addresses or credentials.

The Codex leg already exists and is verified working. This plan covers hardening it against the spec's stated failure modes, adding the Gemini leg with the same command shape, and writing the routing policy that governs both.

## Technical Context

**Language/Version**: Python 3.9+ (stdlib only) for the bridge; Bash 3.2+ (macOS system bash) for lifecycle and client scripts
**Primary Dependencies**: None installed. `codex` CLI (present, authenticated via ChatGPT subscription), `curl`, `openssl`, `python3`. `cloudflared` optional and currently absent.
**Storage**: Flat files under `~/.codex-bridge/` — `token` (600), `gemini-key` (600), `state.json` (600), `bridge.log`, `tunnel.log`. No database.
**Testing**: Shell smoke scripts under `skills/codex-bridge/tests/`; `bash -n` syntax gate; `python3 -m py_compile` for the bridge. No pytest surface — the logic is a request router, exercised end to end over HTTP.
**Target Platform**: macOS (darwin 25.3), single-user localhost
**Project Type**: Single project — local service plus CLI wrappers, packaged as a Claude Code skill
**Performance Goals**: Not throughput-bound. One delegated instruction at a time by design; the meaningful metric is Claude context bytes avoided per delegated task, not requests per second.
**Constraints**: Bind loopback only by default. Secret never emitted to logs or stdout. Codex invocations serialized against a single retained session. Default per-request time limit 300s, payload cap 1 MiB. Backends must degrade independently when a credential or binary is missing.
**Scale/Scope**: One operator, one machine, two backends, four lifecycle scripts, one policy document.

## Constitution Check

No `.specify/memory/constitution.md` exists in this project, so no project constitution gates apply. The governing rules are the operator's global `CLAUDE.md`, checked here:

| Rule | Status | Note |
|---|---|---|
| Code writing dispatched to Haiku subagent | PASS | All bridge and script authorship goes to Haiku; this session plans, reviews, verifies. |
| Never commit `*token*` / `*secret*` / `*credentials*` | PASS | Credentials live in `~/.codex-bridge/`, outside the project tree. A `.gitignore` task guards against accidental in-tree copies. |
| Skills carry `name` / `description` / `version` / `benchmark` frontmatter | PASS | `codex-bridge` skill already conforms; the Gemini leg extends it rather than adding a second skill. |
| No vendored DomI skills downstream | PASS | This skill is original to this project, not a DomI copy. |
| Agent-facing text in caveman ultra | PASS | Subagent dispatch prompts are compressed; repo docs stay in plain prose per the audience-scoping table. |

**Deviation requiring operator awareness**: the routing policy sends reading and triage work to third-party backends that this project does not control. The operator ratified automatic routing on 2026-09-02; the mitigation is that the policy excludes training-on-input backends from sensitive material, and Claude records the route used.

## Project Structure

### Documentation (this feature)

```text
specs/001-codex-delegation-regime/
├── spec.md
├── plan.md              # This file
├── tasks.md             # /speckit-tasks output
└── checklists/
    ├── requirements.md  # spec quality gate
    └── delegation.md    # /speckit-checklist output
```

### Source Code (repository root)

```text
bridge.py                          # Codex HTTP bridge (exists, needs hardening)
README.md                          # operator-facing bridge docs (exists)
.gitignore                         # NEW - guard against in-tree credentials

skills/codex-bridge/
├── SKILL.md                       # exists; extend with Gemini + routing
├── reference/
│   └── routing-policy.md          # NEW - the delegation regime
├── scripts/
│   ├── up.sh                      # exists
│   ├── down.sh                    # exists
│   ├── status.sh                  # exists
│   ├── ask.sh                     # exists - Codex leg
│   ├── gask.sh                    # NEW - Gemini leg, same shape
│   └── usage_report.sh            # NEW - usage ledger reporter
├── reference/
│   └── prices.json                # NEW - operator-editable price table
└── tests/
    └── smoke.sh                   # NEW - consolidated smoke suite
```

**Structure Decision**: Single flat project. The bridge stays one file with no dependencies because its whole value proposition is running anywhere without installation ceremony. Client scripts live inside the skill so the skill is self-contained and portable to other machines by copying one directory. The routing policy sits in `reference/` rather than in `SKILL.md` so it can grow without bloating what loads into context on every skill invocation.

## Key Design Decisions

**Two legs, one command shape.** `ask.sh` (Codex) and `gask.sh` (Gemini) take the same arguments and print the same thing — response on stdout, metadata on stderr. A caller switches backends by changing one letter, which is what makes automatic routing cheap to apply and cheap to reverse.

**The legs differ in how material reaches them, and that difference is the whole design.** Codex reads the filesystem itself; it receives an instruction naming paths. Gemini has no filesystem, so `gask.sh` must read files locally and post their contents — meaning the *script* holds the bytes, never the Claude conversation. Both preserve the invariant in SC-001; they just achieve it differently. Getting this wrong (having Claude read files to feed Gemini) would defeat the feature entirely, so it is called out as an explicit acceptance check.

**Gemini gets model tiers, Codex does not.** Gemini's tier list spans a cheap lite model to a pro reasoning model at identical context limits, so tier selection is a real lever: `gemini-3.8-flash` for digests, `gemini-flash-lite-latest` for high-volume triage, `gemini-3.1-pro-preview` for analysis. Codex model choice is left to the CLI's own default because the subscription tier already constrains it.

**Usage tracking reads, never writes to the request path.** Claude Code already persists per-message usage — input, output, cache read and write counts, and the model id — into `~/.claude/projects/**/*.jsonl` as a side effect of normal operation. So the Claude leg needs no instrumentation whatsoever: a read-only scanner recovers the full history retroactively, including sessions that predate this feature. Codex and Gemini both return usage in their own responses, which the bridge and `gask.sh` append to a ledger. This is what satisfies "non-intrusive" and "deterministic" simultaneously — nothing hooks the request path, and the same records always produce the same report.

**Cache tokens are counted separately, not folded in.** Claude bills cache reads and cache writes at different rates from fresh input. Summing them into one "input" figure would misstate cost by a large factor in a session like this one, where cached input dominates. The ledger keeps the four counts distinct.

**Failure is loud, never silent.** The spec's edge cases all describe the same anti-pattern: a degraded path that looks like success. The stale-session bug found during construction is the canonical example — a failed resume silently started a fresh session, so context loss would have been invisible. Every recovery path must surface that it fired.

## Phase 0 — Research Notes

Findings established empirically before planning, recorded so they are not re-derived:

- `codex exec` refuses to run outside a trusted directory unless `--skip-git-repo-check` is passed. Any working directory that is not a git repo fails without it.
- `codex exec --json` emits JSONL including `{"type":"thread.started","thread_id":...}` and `{"type":"turn.completed","usage":{...}}`. This is the source of both session identity and quota reporting.
- `codex exec resume <ID>` requires `resume` as the subcommand immediately after `exec`; flags may not precede it. Verified by a defect that reached working code.
- `-o FILE` writes the clean final message, avoiding stdout scraping.
- Codex authenticates via ChatGPT subscription (`auth_mode` set, `OPENAI_API_KEY` null), so the binding constraint is rate-limit windows.
- Gemini key is valid and exposes 40+ `generateContent` models, including several at a 1,048,576-token input limit.
- `cloudflared`, `ngrok`, and Tailscale are all absent from the machine.
- Claude Code transcripts at `~/.claude/projects/**/*.jsonl` carry a `message.usage` object per assistant message with keys `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, alongside `message.model`. Verified: 94 such records in the current session. This makes retroactive, zero-instrumentation usage recovery possible.
- Gemini's `generateContent` response carries `usageMetadata` with prompt and candidate token counts.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two client scripts rather than one dispatcher | The two backends differ irreducibly in how material reaches them — Codex reads paths, Gemini receives bytes | A single script with a `--backend` flag would hide that difference behind a uniform interface, and the difference is exactly what a caller must reason about when routing |
| Persistent session state held in the service process | FR-002 requires context to survive across requests, and the Codex CLI is invoked fresh each time | Stateless invocation would force every follow-up to restate prior material, defeating the token-saving premise |
