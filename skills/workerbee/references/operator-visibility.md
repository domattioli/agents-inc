# workerbee: operator visibility

Moved verbatim from `skills/workerbee/SKILL.md` (2026-11-16, token-efficiency order). Rules here bind as if in SKILL.md.

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
