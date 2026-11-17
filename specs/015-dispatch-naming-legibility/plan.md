<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Dispatch Naming Legibility

**Branch**: `development` (no feature branch) | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: `specs/015-dispatch-naming-legibility/spec.md` (Clarifications and addendum answered 2026-10-01). Plan written inline by the Supervisor (Orchestrator rung, ruling R1).

## Summary

1. The owned Claude `PreToolUse` hook (`agent-nudge`, matcher `Agent|Task`) denies a description that begins with a Codex persona name, using the fixed regex and reason from FR-002. Every other hook path stays fail-open.
2. The same hook records each spawn in a shared in-flight registry under the agents-inc state directory and adds a duplicate warning when a live entry from another session holds the same task key. A new owned `PostToolUse` hook (`agent-done`, same matcher) releases the entry for foreground spawns.
3. A bounded recovery command summarizes a stopped delegate's transcript in at most 4,000 characters.
4. The workerbee skill states the naming rule, the one-line hierarchy statement, operator-model precedence, the recovery command, and the duplicate warning. These are canon edits, listed as `LESSON-CANDIDATE`.

## Technical Context

**Language/Version**: Python 3.9+ standard library
**Primary Dependencies**: none new
**Storage**: `paths.state / "inflight" / <task key>.json` (user scope, `~/.local/state/agents-inc/inflight/`)
**Testing**: `python3 -m unittest`; hook tests call `agents_inc.install.hook.run` with fixture payloads on a `StringIO` stdin and a fake `InstallPaths` home; recovery tests use generated fixture transcripts
**Constraints**: hook timeout 5 s; never block except the FR-002 deny; no reads of real `~/.claude/projects` in tests (FR-008); `agents_inc/install/*` edits are Executive-owned (operator ruling 2026-10-01: "Executive edits, Supervisor approves")
**Scale/Scope**: one hook module, one wiring entry, one new script, one skill section

## Existing code (evidence, re-grepped 2026-10-01 at `e21db5b`)

- `agents_inc/install/hook.py:1` docstring "Advisory only: never block"; `:22-28` `agent_nudge` once per session via `paths.state/"nudged"/<session>`; `:30-40` `run` catches every exception and returns 0.
- `agents_inc/install/cli.py:105` `hook` subcommand accepts events `session-start`, `agent-nudge` only.
- `agents_inc/install/host_wiring.py:106-113` `add_hooks`: `SessionStart`, `PreToolUse` `Agent|Task` (`agent-nudge`, timeout 5) for hosts with `nudge=True` (Claude only), `UserPromptSubmit` at_route. No `PostToolUse` entry. `_owned` matches any `<launcher> hook ` command, so a new owned entry is stripped and re-added with no extra code.
- Reference deny emitter (read-only): `~/.claude/scripts/no_claude_md_guard.py` prints `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": REASON}}` on stdout and exits 0.
- `skills/workerbee/SKILL.md:174-182` "Vendor nicknames are not Claude names"; `:209` `DelegateAgent` can run Codex `luna`, so persona names are legitimate there (outside the `Agent|Task` matcher).
- #17 corpus check (Supervisor, read-only, 2026-10-01, counts only): the local transcripts now hold 1,841 `Agent`/`Task` dispatches; 23 begin with a persona word under a loose match; the FR-002 regex matches 22 of 23. The one miss uses `/` after the persona (`<Persona>/<word> ...`). The original 24-description set is no longer reproducible exactly (transcript churn). Reported, not acted on: the regex is an operator decision.

## Design decisions

- **DD1 deny** (FR-002, FR-007): new `persona_deny(payload) -> str` in `hook.py`. If `tool_name` is `Agent` or `Task` and `tool_input.description` is a string matching `re.compile(r"(?i)\A(?:astra|sol|terra|luna)(?=\s|:|/|\Z)")`, return the reference deny JSON with `PERSONA_DENY_REASON` (FR-002 text, verbatim, one constant). `run("agent-nudge")` evaluates the deny first; on a deny it prints only the deny JSON and skips the nudge and the registry. A non-dict payload, a missing or non-string description, or any exception yields no deny (fail open). `hook.py:1` docstring becomes "Advisory, except the FR-002 persona deny; never break a session, always exit 0."
- **DD2 task key** (FR-006): `task_key(payload)` = first 16 hex chars of SHA-256 over `normalize(description) + "\n" + normalize(prompt)`, where `normalize` lowercases, strips, and collapses whitespace. Including the prompt keeps intentional fan-out with different prompts distinct.
- **DD3 registry** (FR-006): on `agent-nudge` (no deny), read `paths.state/"inflight"/<key>.json`. If it exists, is unexpired, and its `session_id` differs from the payload's, add a warning to `additionalContext`: `agents-inc duplicate warning: the same task (key <key>) is in flight from session <S1> since <time>. If this is intentional fan-out, add the line "agents-inc: fan-out" to the prompt.` Then write the entry `{session_id, tool_use_id, started, expires}` with expiry 2 hours (constant `INFLIGHT_TTL_S = 7200`), atomically (temp file plus `os.replace`). An expired entry is ignored and replaced. A prompt containing `agents-inc: fan-out` skips both the check and the write. Any `OSError` on the registry prints one stderr line and continues (fail open). Same-session repeats overwrite silently (#13 found 0 accidental within-session duplicates).
- **DD4 nudge plus warning in one object**: when both the once-per-session nudge and a duplicate warning apply, emit one `hookSpecificOutput` with both texts joined by a blank line. When neither applies, print nothing.
- **DD5 release** (FR-006): new hook event `agent-done` (cli `hook` choices gain it), wired as a `PostToolUse` entry, matcher `Agent|Task`, timeout 5, Claude host only. It deletes `inflight/<key>.json` when the entry's `session_id` matches and `tool_input.run_in_background` is not true (a background spawn's `PostToolUse` fires at launch, so its entry lives until expiry). Fail open. Spec 016 extends this same event to write its ledger row (shared design, D runs after C).
- **DD6 recovery command** (FR-005): new `skills/workerbee/scripts/recover_transcript.py <transcript> [--max-chars 4000]`. Streams the JSONL line by line (no full read into memory). Tracks: last assistant text; files from `tool_use` blocks named `Write`, `Edit`, `MultiEdit`, `NotebookEdit` (`file_path` or `notebook_path`); Bash commands are not parsed for writes, and the output says "Bash writes not tracked"; last `tool_result` with `is_error` true; final status (`handback` when a `SubagentHandback` tool_use exists, else the last assistant `stop_reason`, else `unknown`); skipped malformed lines. Output: fixed labels, sections truncated so total length is at most `--max-chars`; file list keeps the most recent 20 unique paths. Missing or unreadable path: stderr message, exit 2. Read-only; no writes anywhere. Not under `agents_inc/install/`, so a delegate may implement it.
- **DD7 skill text** (FR-001, FR-003, FR-004, FR-009): in `skills/workerbee/SKILL.md` after the "Vendor nicknames are not Claude names" paragraph (`:174-182`), add "Dispatch names tell the truth" (rule, hook deny, how to name a Claude supervisor of a Codex worker), "State the hierarchy before the first dispatch" (D34 order, one-line format `Hierarchy: Executive = <name> (<model>, top); Supervisor = <name> (<model>, reports to Executive)` (words, no `>` glyph: #14 began with `>` read as "less than"; analyze A1), operator-named models override the ladder and the conflict is stated), and under Step 3 a "Recover a stopped delegate" line naming `recover_transcript.py` and the 4,000-character bound, plus the duplicate warning meaning. Use offsets; the file is 909 lines with a duplicate Step 5 heading (trap T10). No automated check for the hierarchy line: it is said to the operator before dispatch, not written into a delegate prompt, so `check_dispatch_prompt.py` cannot see it (US2 Independent Test: "as decided in planning").
- **DD8 ownership**: DD1-DD5 touch `agents_inc/install/{hook,cli,host_wiring}.py` and go to the Executive as a task spec (operator ruling). DD6 goes to a haiku delegate. DD7 goes to a haiku delegate with the exact text in Appendix A (analyze A2). The Supervisor writes all tests first.

## Constitution Check

Constitution at `~/Projects/DomI/specs/consumers/agents_Inc/memory/constitution.md` is unratified, so violations are WARN.

| Principle | Status | Note |
|---|---|---|
| P0 cross-reference, never duplicate | PASS | One hook entry extended; one new event; skill text points at the script. |
| P1 repo-scoped writes | PASS | Registry lives in the user-scope state dir at run time only; tests use a fake home. |
| P2 labor ladder | PASS | Executive for install code (ruling), haiku for script and text. |
| P4 deterministic policy over prompt | PASS | The naming rule is enforced by the hook, not only by prose. |
| P5 hard $0 per task | PASS | No model calls. |
| P7 rung names | PASS | Skill text restates D34. |

Post-design re-check: PASS.

## Project Structure

```text
specs/015-dispatch-naming-legibility/
├── spec.md, plan.md, tasks.md, analyze.md
└── checklists/ (requirements.md, hook-and-recovery.md)
agents_inc/install/hook.py          # Executive: DD1-DD5
agents_inc/install/cli.py           # Executive: agent-done event
agents_inc/install/host_wiring.py   # Executive: PostToolUse entry
skills/workerbee/scripts/recover_transcript.py   # new: DD6
skills/workerbee/SKILL.md           # DD7 (LESSON-CANDIDATE)
tests/test_hook_persona_guard.py    # new, Supervisor-owned
tests/test_recover_transcript.py    # new, Supervisor-owned
```

## Agent context update

Skipped: no `CLAUDE.md` (retired 2026-10-01).

## Complexity Tracking

None.

## Appendix A: exact text for T005 (DD7)

Insert block A1 after the paragraph that ends "checking Step 1a first." (`skills/workerbee/SKILL.md`, currently line 183) and before `#### Step 1a`, with one blank line on each side. Insert block A2 after the paragraph that ends "All were a delegate grading itself." under `### Step 3` (currently line 313) and before `### Step 3a`, with one blank line on each side. Add nothing else; delete nothing.

Block A1:

```markdown
**Dispatch names tell the truth.** A Claude `Agent`/`Task` dispatch is named
with a rung (Grunt, Workhorse, Orchestrator) or a Claude model name (haiku,
sonnet, opus). A Codex persona name (`astra`, `sol`, `terra`, `luna`) appears
only on a dispatch that reaches a Codex model through agents-inc. The owned
`PreToolUse` hook denies an `Agent`/`Task` description that begins with a
persona name; renaming does not change the execution model. A Claude
supervisor of a Codex worker puts its own rung first and names the worker
later: "Workhorse supervises luna parser fix", not "luna: parser fix".

**State the hierarchy before the first dispatch.** When an operator turn
names two roles without an explicit order, or names models that differ from
the ladder, say one line to the operator before the first dispatch:
`Hierarchy: Executive = <name> (<model>, top); Supervisor = <name> (<model>, reports to Executive)`.
The order is D34: Executive above Supervisor (= Orchestrator). Use words, not
the `>` glyph; #14 began with `>` read as "less than". Operator-named models
override the ladder default; state the conflict, do not resolve it silently.
```

Block A2:

```markdown
**Recover a stopped delegate.** Do not read its whole transcript. Run
`python3 skills/workerbee/scripts/recover_transcript.py <transcript.jsonl>`;
it prints at most 4,000 characters (`--max-chars N` to change): files written
by Write/Edit/MultiEdit/NotebookEdit, the last text, the last error, and the
final status. Bash writes are not tracked; check `git status` too.

**Duplicate warning.** When the hook adds "agents-inc duplicate warning", the
same description and prompt are already in flight from another session. Check
that session before re-dispatching. For intentional fan-out, add the line
`agents-inc: fan-out` to each prompt.
```
