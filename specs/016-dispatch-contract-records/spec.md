<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Dispatch Contract Header and Dispatch Records

**Feature Branch**: `development` (spec dir `specs/016-dispatch-contract-records`; no feature branch, per dispatch)
**Created**: 2026-10-01
**Status**: Draft
**Input**: Batch D of the 2026-10-01 Supervisor dispatch: issues #36 (reusable `header.md` plus slots, generated tier tables, fuller ledger), #28 (delegate persistence until a context ceiling of 200k tokens, 300k for Opus), #4 (dispatch-prompt style-compression findings), #27 (DomI skill overlap scan; DomI read-only). Operator ruling 2026-10-01: full pipeline through implement, no `--plan-only`.

## Background (verified 2026-10-01 against HEAD `dd48471` unless noted)

- The 14-element contract lives in `skills/workerbee/SKILL.md` Step 11 (`:501` onward) and is linted by `skills/workerbee/scripts/check_dispatch_prompt.py` (174 lines). No reusable header file exists (`skills/workerbee/header.md` absent). #36 cites `CLAUDE.md:43`; CLAUDE.md was retired on this machine on 2026-10-01, so that citation is stale.
- Tier vocabularies: `skills/workerbee/SKILL.md:143-149` uses `ultra/flagship/workhorse/flash`; `agents_inc/models.json` and `routing.json` use the D27/D36 rung names `executive/orchestrator/workhorse/grunt`. #36's comment measured 0 tier disagreements after mapping, 30 config ids missing from the SKILL.md tables, 4 SKILL.md ids missing from config (`gemini-flash-lite-latest`, `ministral-3b-latest`, `codestral-latest`, `mistral-large-latest`), and 2 roster rows with labels outside both vocabularies (`workhorse-ish`, a bare dash).
- `agents_inc/install/bundle.py:58` already substitutes `@AGENTS_INC_LAUNCHER@` while staging the installed skills. `tests/test_vocab_drift_guard.py` exists.
- Ledger: `agents_inc/ledger.py` `record_dispatch` (`:70`) and `record_return` (`:225`) record no effort, tokens, files created, or supervisor gate verdict; `record_return` writes `run_id: None` (`:248`). Token usage lives in `skills/codex-bridge/scripts/usage_db.py` (`usage` table, `:35`), not joined to the ledger. Claude `Agent` and `DelegateAgent` dispatches write no ledger row. The owned Claude hooks are `SessionStart` and `PreToolUse` on `Agent|Task` (`agents_inc/install/host_wiring.py:89-95`); there is no `PostToolUse` hook and no `DelegateAgent` matcher.
- #28 measurement (issue comment, 1,399 local subagents): 2.5% ended at or above 200k context and 0.2% at or above 300k; median first-turn context per spawn was 42,110 tokens. Resume support: Codex (`ask.sh` thread id) yes; Mistral (`mask.sh`) one global conversation; OpenRouter and Gemini none.
- #4 status: the revised hard-constraint template is an opt-in draft, not canon. The 2026-09 rerun (n=5 per arm, blind-graded) found a 40% cut in answer words but higher billed output tokens (1,175 to 2,500 mean), and a 1-point fact gap within noise. The full factorial and a non-extractive task were not run.
- #27 status: the scout verdict found no overlap between DomI `subagent-dispatch-policy` and agents_Inc `workerbee`; the comment measured 0 of 987 sessions invoking `subagent-dispatch-policy`, one stale id (`opus 4.7`) in the DomI skill, and 4 of 6 dispatch skills with zero invocations.

## Clarifications

### Session 2026-10-01

Answered by the operator through the Executive, 2026-10-01.

- Q: How are the tier tables produced? → A: A script-generated, marker-delimited block in the repo `skills/workerbee/SKILL.md`, with a drift test; rung names follow D27/D36 (`executive/orchestrator/workhorse/grunt`).
- Q: How do Agent-tool dispatches get ledger rows? → A: ~~An explicit `agents-inc ledger append` command only; no automatic hook logging.~~ Superseded by the addendum answer below.
- Q: What is the #4 deliverable? → A: Record the findings and offer the revised template as an optional, experimental header slot; no new model runs.
- Q: What is the #27 deliverable? → A: `specs/016-dispatch-contract-records/research.md`; DomI follow-ups (stale `opus 4.7` id, zero-use dispatch skills) are reported as NEEDS-OPERATOR items, not edits.
- Q: How is the #28 persistence rule enforced? → A: Skill text plus an inheritance line in nested dispatch prompts only; no token tracker and no lint check.
- Q (addendum, changes D-Q2): How do Agent-tool and `DelegateAgent` dispatches get ledger rows? → A: Both paths. An owned `PostToolUse` hook writes a minimal dispatch row (model, description, cwd, tool_use id, tokens recorded as unknown, never zero) to the user-scope agents-inc state directory, never to `<workspace>/.workerbees/`. `agents-inc ledger append` writes the return row with the supervisor verdict and fails closed when the verdict is missing. `DelegateAgent` is an MCP tool and needs its own matcher; `Agent|Task` does not cover it. The hook fails open, with a timeout of at most 5 s. Rows fit the Node shape (`agents_inc/derivation_store.py:7`); hook rows carry no `parent_id`, so lint must not flag them as orphans. Operator decision 2026-10-01 after a fable second opinion and an Executive recommendation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fuller dispatch records (Priority: P1)

A supervisor records every dispatch, including Claude `Agent` dispatches, with effort, token counts, files created, and its own gate verdict. Return rows carry the run id, and rows join to the usage store by an approximate time window, because the usage store has no run column.

**Why this priority**: Records drive cost and verification review; today most dispatches leave no row.

**Independent Test**: In a temp workspace, call the extended `record_dispatch`/`record_return` and the new append command; assert fields persist in the JSONL store (SQLite keeps input and output tokens only; other fields need a schema migration, out of scope), `run_id` is set on return rows, and old rows still load.

**Acceptance Scenarios**:

1. **Given** a temp workspace, **When** a dispatch and return are recorded with effort, tokens, files, and verdict, **Then** `load()` returns them and the return row's `run_id` equals the dispatch's.
2. **Given** an existing ledger written before this change, **When** loaded, **Then** it loads without error and new fields read as unknown, not zero.
3. **Given** `agents-inc ledger append` with the required fields, **When** run, **Then** one row is written; with the verdict missing, it fails closed with a message.
4. **Given** a delegate self-report of PASS and no supervisor verdict, **When** recorded, **Then** the row's verdict is unknown, never PASS.
5. **Given** a `PostToolUse` payload for `Agent` or for `DelegateAgent`, **When** the owned hook runs under a fake HOME, **Then** one dispatch row with unknown tokens lands in the user-scope state directory, no file is written under `<workspace>/.workerbees/`, and lint reports no orphan for it.
6. **Given** a malformed payload or an unwritable state directory, **When** the hook runs, **Then** it exits 0 and the host session continues.

---

### User Story 2 - One header file, per-task slots (Priority: P2)

A supervisor writes a dispatch by filling slots under a fixed header instead of rewording 14 elements. The lint accepts either pasted elements or a `CONTRACT: <path>` reference for file-capable delegates; bare-API delegates still get the text pasted.

**Independent Test**: Lint a prompt built from header plus slots, a prompt with filled slots plus `CONTRACT: <path>` for a file-capable delegate, and the same for a bare-API delegate; assert COMPLIANT, COMPLIANT, and REJECTED.

**Acceptance Scenarios**:

1. **Given** `header.md` plus filled slots, **When** linted, **Then** COMPLIANT.
2. **Given** a `CONTRACT:` reference with transport set to a bare-API delegate (`--transport bare`), **When** linted, **Then** rejected with the reason.
3. **Given** any rendered prompt, **When** inspected, **Then** the training opt-out line is present verbatim.

---

### User Story 3 - Tier tables that cannot drift (Priority: P2)

The tier tables a reader sees in the workerbee skill come from `models.json` and `routing.json`, in one vocabulary. A test fails when they drift.

**Independent Test**: Change a tier in a fixture config; assert the drift test fails until the table is regenerated.

**Acceptance Scenarios**:

1. **Given** current configs, **When** the generator runs, **Then** the rendered table lists every config id in its rung, using the D27/D36 rung names `executive/orchestrator/workhorse/grunt`, inside a marker-delimited generated block of the repo `skills/workerbee/SKILL.md`.
2. **Given** a config change without regeneration, **When** the drift test runs, **Then** it fails and names the id.

---

### User Story 4 - Delegate persistence rule (Priority: P3)

A supervisor continues a live delegate that holds the needed context instead of spawning a new one, until the delegate reaches its context ceiling, then retires it with a handoff. Listed exceptions apply.

**Independent Test**: The skill text states the rule, ceilings, exceptions, per-backend resume support, and the required inheritance line for nested dispatch prompts.

**Acceptance Scenarios**:

1. **Given** a follow-up task for a delegate under its ceiling, **When** the supervisor dispatches, **Then** the rule says continue (Claude `SendMessage`; Codex thread resume).
2. **Given** an adversarial review, a premise change, or a stateless free-tier backend, **When** dispatching, **Then** the exception applies and a fresh delegate is used.

---

### User Story 5 - Record #4 and #27 findings (Priority: P3)

The style-compression findings and the DomI overlap scan land as repo-side records with clear status, so their issues can be closed or narrowed. No DomI file is written.

**Independent Test**: The records exist, cite the issue evidence, and state status; `git status` in DomI shows no change.

**Acceptance Scenarios**:

1. **Given** #4, **When** the record is read, **Then** it states the template is opt-in, what was measured, and what remains unvalidated, and the template is available as an optional experimental header slot.
2. **Given** #27, **When** the record is read, **Then** it states the verdict and lists DomI-side follow-ups as operator items, not edits.

### Edge Cases

- Ledger rows from before the change have no new fields: read as unknown.
- Token counts unavailable for a transport: record unknown, never zero (repo rule "keep unknown distinct from zero", workerbee Step 5).
- Usage-store row missing for a run: join yields unknown tokens, not an error.
- Config id with a tier label outside the rung set: generator fails closed and names the id.
- A delegate whose cumulative tokens are unknown: persistence rule treats it as under the ceiling only if the transport reports tokens; otherwise the supervisor decides and states it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `record_dispatch` MUST accept effort, cwd, and source; `record_return` MUST accept effort, input/output/cache tokens, files created, and supervisor gate verdict. All are optional. The JSONL store keeps every field; the SQLite store keeps input and output tokens in its existing `usage` columns, and the other fields wait for a schema migration (follow-up). Both functions MUST accept an explicit store mode so a caller can force JSONL only. `seconds` and `subscription_calls` on `record_return` become optional (unknown, never zero). Existing callers MUST keep working unchanged.
- **FR-002**: `record_return` MUST write the dispatch's `run_id`.
- **FR-003**: The ledger MUST join to `usage_db` read-only by provider, model, and the node's dispatch-to-return time window, because `usage_db` has no run column. The result is unknown on a missing db, no match, an overlapping same-model node, a `claude` provider (Claude usage rows are per session turn), or a host-hook row (its timestamp is the hook time, not the dispatch time).
- **FR-004**: Agent-tool and `DelegateAgent` dispatches MUST be recorded on two paths. (a) An owned `PostToolUse` hook, with one matcher for `Agent|Task` and a separate matcher for the `DelegateAgent` MCP tool, MUST write a minimal dispatch row (model, description, cwd, tool_use id, tokens as unknown, never zero) to the user-scope agents-inc state directory, never to `<workspace>/.workerbees/`. The hook MUST fail open and MUST finish within a host timeout of at most 5 s. (b) `agents-inc ledger append` MUST write the return row with the supervisor verdict from the command line; a missing verdict on a return MUST fail closed. Rows from both paths MUST fit the Node shape (`agents_inc/derivation_store.py:7`). Hook rows carry no `parent_id`, and ledger lint MUST NOT flag them as orphans. (c) Because a supervisor session does not see the `tool_use_id` of a foreground call, `agents-inc ledger pending` MUST list open host rows (id, model, task, timestamp) so the supervisor can find the key for `append`; a background-agent completion notice also carries it as `<tool-use-id>`. Hook rows are written JSONL only, so the host state directory never gains a SQLite file. An executive-tier hook row has no gate reason, and lint flags it by design.
- **FR-005**: A header file and slot template MUST exist for the 14-element contract; the training opt-out line MUST be verbatim in every rendered prompt.
- **FR-006**: `check_dispatch_prompt.py` MUST accept a `CONTRACT: <path>` reference for file-capable delegates (`--transport file`, the default) and reject it for bare-API delegates (`--transport bare`). A bare-API wrapper caller MUST pass `--transport bare`.
- **FR-007**: The workerbee tier tables MUST be generated from `models.json` and `routing.json` in the D27/D36 rung vocabulary, written by a script into a marker-delimited block of the repo `skills/workerbee/SKILL.md`, with a drift test beside `tests/test_vocab_drift_guard.py`. No new TOML or other config source.
- **FR-008**: The workerbee skill MUST state the persistence rule with ceilings 200k default and 300k for Opus, the exceptions from #28, and per-backend resume support, and require nested dispatch prompts to carry an inheritance line stating it. Enforcement is the skill text and that line only; no token tracker and no lint check.
- **FR-009**: #4 and #27 findings MUST be recorded: #4 as findings plus an optional experimental header slot carrying the revised template (no new model runs); #27 in `specs/016-dispatch-contract-records/research.md`, with DomI follow-ups listed as NEEDS-OPERATOR items. No DomI write.
- **FR-010**: Any cache-savings claim for the header MUST be backed by a measurement of `cache_read` over about 10 clustered runs; absent that, no savings claim is made.
- **FR-011**: Changes to `skills/workerbee/SKILL.md` are canon changes and MUST be listed as `LESSON-CANDIDATE` items for Executive sign-off.

### Key Entities

- **Ledger row**: dispatch or return record with the new optional fields.
- **Header**: fixed contract text; **Slot**: per-task field.
- **Rung table**: generated view of model ids per rung.
- **Persistence ceiling**: context size at which a delegate is retired.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of return rows written after the change carry a non-null `run_id`.
- **SC-002**: A pre-change ledger fixture loads with 0 errors.
- **SC-003**: The generated table lists 38 of 38 config ids (the #36 count) or the current count at implement time, with 0 disagreements.
- **SC-004**: Lint results on the three US2 fixtures match expectations in 3 of 3 cases.
- **SC-005**: The unit suite shows only the known pre-existing failure.
- **SC-006**: The usage join returns unknown, never a number, in each listed unknown case (missing db, no match, overlap, `claude` provider, host-hook row), and never writes the usage db.

## Assumptions

- Rung vocabulary follows D27/D36 (`executive/orchestrator/workhorse/grunt`).
- No new model experiments run this batch; #4 validation runs stay out of scope.
- `skills/codex-bridge/scripts/usage_db.py` is not peer-owned and may be read; `~/.codex-bridge/usage.db` is never written by tests.
- This batch runs the full pipeline through implement (operator ruling 2026-10-01; no `--plan-only`).
- `.gitignore:224-232` ignores any path containing `key`, `secret`, `token`, or `credential`. New files for the token-count work must avoid those words in their names (for example no `test_ledger_tokens.py`).
