<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-06 skill=speckit-implement repo=agents_Inc session=c5e2753c -->
# Quickstart: run the opus terminal demo

## Once per machine
1. Install the recorder: `brew install asciinema agg`. This is optional. Without it, the demo runs unrecorded and prints a NOTE.
2. Run `agents-inc doctor` and check that it prints `READY`. If it warns `MOD_NOT_INSTALLED`, run `agents-inc repair`.
3. In `~/.claude/settings.json`, make sure `sandbox.excludedCommands` lists `"agents-inc *"` and the permission allow list contains `mcp__agents-inc__run`. Without the second, the relay asks on every run.
4. Optional free model: set `MISTRAL_API_KEY` or put the key in `~/.config/devstral/api_key`. Gemini and OpenRouter keys are optional.

## Each run
1. From the repo root on `development`: `python3 tools/demo/opus_demo.py`.
2. The runner checks doctor, codex and the free keys, creates `.scratch/demo-030/<stamp>/`, and prints the beat checklist and the paste prompt. If asciinema is installed, it then starts recording and opens `claude --model opus`.
3. Paste the prompt (also saved as `.scratch/demo-030/<stamp>/prompt.txt`).
4. Watch the beats. The luna and haiku panes beside the chat show each delegate live (open them with `/luna-pane` if they are closed).
5. When opus prints `BEAT 3` and its final line, type `/exit`. The runner stops the recording and writes `demo.gif`.

## Rehearse without running anything
`python3 tools/demo/opus_demo.py --dry-run` writes the folder and prints the prompt only.

## Tests
`python3 -m unittest tests.test_opus_demo`

## Expected result
- The judge exits 0, and opus names the four traps the delegate avoided.
- The ledger row moves out of `pending` after opus records its verdict.
- The whole run takes about 30 seconds.

## Claude-only machine
The runner prints `NOTE: codex absent -> haiku`. Haiku builds in its own pane, and all three beats run.
