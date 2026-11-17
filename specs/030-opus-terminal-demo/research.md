<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-06 skill=speckit-implement repo=agents_Inc session=c5e2753c -->
# Research: Opus terminal demo

> Revision 2026-11-07: the relay decisions below (R1 primary path, the trial dir reason, the free-model alternative note, the last `[assumed]` line) are superseded. The live view is the `luna-pane` mod tailing `events.jsonl`; dispatch runs as a plain background Bash call; no relay courier (it doubles Claude tokens). The trial dir stays in `.scratch/` because the delegate cwd is the repo root. See plan.md "Revision 2026-11-07".


## R1. Runner language and location
- Decision: Python stdlib, `tools/demo/opus_demo.py`.
- Rationale: The existing demo `tools/governance_demo.py` is Python and is tested by `tests/test_governance_demo.py` through a `sys.path` insert [verified tests/test_governance_demo.py:8-11]. Python makes JSON slots writing and dry-run testing simple.
- Alternatives: bash in `scripts/demo/` was rejected because a bash script is harder to unit test and writing JSON from bash is error-prone. Extending `governance_demo.py` was rejected because it runs a fake worker loop [verified governance_demo.py:13-23], not real dispatch. Only its `--fake` offline idea is reused, as `--dry-run`.

## R2. Live-view path
- Decision: the primary path is `Agent` with `subagent_type: "agents-inc:relay"`. The fallback is one plain Bash `agents-inc dispatch`.
- Rationale: the relay tool runs dispatch itself and appends rows as system notices [verified mods/agents-inc/README.md:7-9; relay.ts:65]. FR-009 requires relay rows. Rows are capped at 600 per call, after which there is one notice per 60 s [verified README.md:46; relay.ts:6].
- Alternatives: `agents-inc events follow` in a second pane was rejected by FR-009 (no second pane or tmux).

## R3. Trial dir placement
- Decision: `<repo>/.scratch/demo-030/<stamp>/trial/`.
- Rationale: the relay pins `--cwd` to the session cwd and refuses slots outside it [verified relay.ts:61-65]. `.scratch/` is git-ignored [verified .gitignore:241].
- Alternatives: `$TMPDIR` was rejected because the relay refuses it. A repo-tracked folder was rejected because it dirties git.

## R4. Ledger read-back
- Decision: `agents-inc ledger pending`, then `agents-inc ledger append --node-id <run_id> --verdict pass`, then `ledger pending` again.
- Rationale: the dispatch row has status `dispatched` and no outcome field [verified host_ledger.py:113-132]. Only `append` and `pending` exist [verified host_ledger.py:224-240].
- Alternatives: reading the ledger JSONL directly was rejected because its path comes from `host_workspace(state)` and is not part of the documented surface [verified host_ledger.py:250].

## R5. Free model choice
- Decision: try mistral first, then gemini, then openrouter.
- Rationale: `free_order` [verified routing.json:12]. Wrappers are bare-API and take pasted text [verified QUICKREF.md:7].
- Alternatives: the relay was rejected because it refuses free models [verified relay.ts:59; spec 027 Q1].

## R6. Key presence without reading values
- Decision: check whether the env var is set and the key file size is above 0. A key only in `~/Projects/.env` reports `maybe`.
- Rationale: P1 forbids reading `.env`. Wrapper key sources: [verified mask.sh:14,142-150; gask.sh:15-16,81-84; oask.sh:15-16,90-99].
- Alternatives: running the wrapper with an empty prompt as a probe was rejected because it spends quota and adds time.

## R7. Recording
- Decision: `asciinema rec <cast> --command "claude --model opus"`, then `agg <cast> <gif>`. Install with `brew install asciinema agg`. When asciinema is absent, print a NOTE and run without recording.
- Rationale: FR-008. Neither tool is installed [verified `which` 2026-11-06]. Formula names `asciinema` and `agg` both exist [verified `brew info --json=v2 asciinema agg` 2026-11-06, T002]; the install line stays `brew install asciinema agg`.
- Alternatives: the macOS screen recorder was rejected (it produces no cast file and is not scriptable).

## R8. Native luna comparison observability
- Decision: compare result text, failure prefix, changed-tree line and ledger source.
- Rationale: [verified README.md:50,52; D69 Q2].
- UNKNOWN: whether the subagent transcript path and the per-step model field are readable from the parent. Probe: one run, then list `~/.claude/projects/` for a subagent jsonl.

## R9. Sandbox
- Decision: the runner checks doctor for `WB_SANDBOX_EXCLUDE_MISSING` and, when present, prints the exact ask (`add "agents-inc *" to sandbox.excludedCommands`) before launching claude.
- Rationale: [verified QUICKREF.md:63-64]. A Codex delegate cannot start inside the sandbox (rc 71).
- [assumed] The relay spawns dispatch through the mod process, not the Bash sandbox. Implement verifies this on the first run.
