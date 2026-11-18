# Research: 048 (resolved)

- Test runner: `claude plugin test mods/agents-inc` (mods/agents-inc/README.md:66).
- Hash: pure-TS FNV-1a 32-bit (8 hex) plus length; no crypto, no `$` helper needed.
- `$.fs` has only read and write: "exists" means a non-empty read. The loop.test.ts harness (:55) needs an in-memory fs added.
- Retire: the supervisor sends the handoff request as a continue step, then runs `agents-inc handles retire <id>`; the CLI never contacts a delegate. The supervisor pastes the note into a new Agent prompt.
- Binding: provider plus nickname; slug (first completed step's `acc.slug`) informational. All guest ceilings 800k chars.
- Mistral id file is used only under `--agent` (mask.sh:236). Caller: `skills/codex-bridge/scripts/agent_runner.py:576-579` passes `--handle <job id>` (a resumed job passes its parent's id), only alongside `--agent`. bridge.py: no change.
- Restart reasons: compaction (loop.ts:840), failed step (:850), refusal (:876), thread-missing.
- Fingerprint covers header + system + catalog; resumed-thread steps send no prefix, so the log records `sent yes|no`.
- `--session` defaults to the newest session dir under `.scratch/agents-inc-*/`.
- Native listing is out of scope.
