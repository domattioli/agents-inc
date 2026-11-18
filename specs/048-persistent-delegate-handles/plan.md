# Implementation Plan: Persistent Cross-Provider Delegate Handles

**Branch**: `feat/delegate-handles` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

## Summary

Persist the native loop's per-agent registry (`S.agents`) to a per-session `handles.json`, reload it on the first step after a restart, add an `agents-inc handles` launcher subcommand (list, retire), give each Mistral handle its own conversation id in `mask.sh`, and log a system-text fingerprint per step. No new MCP tool, no provider dependency, $0 spend.

## Technical Context

**Language**: TypeScript (mod hooks, `claude-code/testing`), Python 3.11 stdlib (`agents_inc/install/cli.py`, `bridge.py`, `skills/codex-bridge/scripts/agent_runner.py`), Bash 3.2 (`mask.sh`).
**Storage**: `.scratch/agents-inc-<agent>/<session>/handles.json`, beside `<agentId>[-n].thread` files (same retention, git-ignored).
**Testing**: `claude-code/testing` for `loop.test.ts`; `python3 -m unittest discover -s tests -p 'test_*.py'`.
**Constraints**: a persistence failure never blocks a step (FR-011); a handle binds to provider plus nickname (FR-010).

## Design per requirement

Handle record (data-model.md): `{id, provider, nickname, slug, thread, cwd, charsSent, seen, ceiling, state, restarts, lastRestartReason, history[], fingerprint, threadTotal}`.

- **FR-001/FR-003** `mods/agents-inc/hooks/native/loop.ts`: extend `AgentState` (`{n, used, sent}` at the `S.agents.get(id)` site, ~:837) with the FR-003 fields. New helpers `handlesPath(S)` (sibling of `threadPath` ~:447), `loadHandles(S, $)` and `saveHandles(S, $)` using `$.fs`. Save after the run-record update (~:936-953), once per step. Writes go to a temp name then rename if `$.fs` offers it, else a plain write.
- **FR-002** First step per `LoopState`: if `S.handlesLoaded` is false, load the file and seed `S.agents`. `used` is restored true only when the thread file for `n` exists (`$.fs` has only read/write, so exists = non-empty read) and the adapter is `thread` kind; otherwise the step starts fresh and records reason `thread-missing`. Stateless adapters keep `resumed=false` as today but still persist the handle (spec edge case); thread reference is the local conversation record (the `.thread` path).
- **FR-009** Every place that bumps `st.n` (compaction :840, failed step :850, refusal :876, missing thread) sets `restarts++` and `lastRestartReason` (`compaction`, `failed-step`, `refusal`, `thread-missing`) and pushes the old thread path to `history`.
- **FR-010** Handle stores `provider` and `nickname`; a mismatch refuses the step with a message naming the handle. `slug` from the first completed step's `acc.slug` is informational. A step on a `retired` handle is refused.
- **FR-006 / ceiling** Unit is characters sent (clarified): `ceiling` is 800000 for every guest handle. `charsSent` accumulates `chars` (:841-:936), resets to 0 on every `st.n` bump, and for a stateless adapter is the last prompt length. Persist the last `threadTotals` value per thread in the handle (loop.ts:746). At or over ceiling the step result carries a one-line advisory (no automatic retire).
- **FR-008** Compute a pure-TS FNV-1a 32-bit hash of the system text (8 hex) plus its length; no crypto. The hash covers header + system + catalog. Stored as `fingerprint`; `changed` flag compared to the previous step; both added to the `$.ui.log` run-record line (:936) as `sys-fp <hex> changed <yes|no|first> sent <yes|no>` (resumed-thread steps send no prefix).
- **FR-011** `saveHandles` re-reads and merges the file before writing; the file's `state` wins. All store I/O wrapped in try/catch; first failure logs one warning (`S.warned` flag), later failures silent.
- **FR-004/FR-005** `agents_inc/install/cli.py`: new `handles` subparser (`verb` in `list|retire`, `--agent`, `--session` (defaults to the newest session dir under `.scratch/agents-inc-*/`), `--cwd`, `--json`, handle id positional for retire). `scripts/agents-inc` already forwards all args to `agents_inc.install.cli`, so no launcher change. List reads `handles.json` for every `agents-inc-*` dir of the session. The supervisor first sends the handoff request as a normal continue step; `agents-inc handles retire <id>` then marks `state: retired` and prints the instruction to paste the note into a new Agent prompt. The CLI never talks to the delegate, and the system creates no successor (no `seed` field).
- **FR-007** `skills/codex-bridge/scripts/mask.sh`: replace the global `CONVERSATION_FILE` (:17) with `$HOME/.codex-bridge/mistral-conversation-id` as legacy default plus new `--handle ID` flag, which selects `$HOME/.codex-bridge/mistral-conversations/<safe-id>`. Python block (:239-247, :343-354) is unchanged, it already takes the path from env. The id file is read only under `--agent` (mask.sh:236). Callers pass `--handle`: `skills/codex-bridge/scripts/agent_runner.py:576-579`, which passes `--handle <job id>` (a resumed job passes its parent's id) only alongside `--agent`. `bridge.py`: no change.
- **FR-012** No new network calls or dependencies.

## Project Structure

```
specs/048-persistent-delegate-handles/{spec,plan,research,data-model,tasks}.md
mods/agents-inc/hooks/native/loop.ts         (handle persistence, fingerprint, restart reasons)
mods/agents-inc/hooks/native/loop.test.ts    (new tests)
agents_inc/install/cli.py                    (handles subcommand)
tests/test_handles_cli.py                    (new)
tests/test_mask_handle.py                    (new)
skills/codex-bridge/scripts/mask.sh, skills/codex-bridge/scripts/agent_runner.py:576-579  (--handle)
```

## Test plan

- TS (`loop.test.ts`, in-memory fs added to the harness at :55; runner `claude plugin test mods/agents-inc`): persistence write after a step; reload after simulated restart resumes with delta only; missing thread file starts fresh with reason; corrupt store warns once and proceeds; model mismatch refused; compaction, failed-step and refusal record reasons; retired handle refused; concurrent save merges (file state wins); threadTotals persisted; fingerprint present on 3 steps and flags change.
- Python unittest (`tests/test_handles_cli.py`): list over a fixture `handles.json` (text and `--json`), retire sets state, corrupt file reports without traceback.
- Shell/py (`tests/test_mask_handle.py`): run `mask.sh --agent --handle a` and `--agent --handle b` against a stubbed endpoint/`python3` shim; assert two distinct id files, neither is the legacy file.

## Rulings

See spec.md Clarifications. Native agent listing is out of scope.
