<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-06 skill=speckit-implement repo=agents_Inc session=c5e2753c -->
# Implementation Plan: Opus-orchestrated terminal demo of agents-inc

**Branch**: `030-opus-terminal-demo` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/030-opus-terminal-demo/spec.md`

## Revision 2026-11-07 (supersedes the relay and seven-beat design below)

Operator changes after the first implement run:
- No relay haiku courier: it doubles Claude token use. The live view is the `luna-pane` mod, one pane per delegate (luna, haiku), tailing `<run dir>/events.jsonl`. It reads Codex-format and Claude-format rows.
- The prompt is passed to `claude --model opus` as its first input; no paste.
- The demo is about 30 s: three beats (routing; luna builds `csv2json.py` by a background dispatch; opus runs the leak grep and the hidden judge, then appends the ledger verdict). The haiku review, free-model summary and native-luna comparison are dropped from this cut.
- Build slot: write only `csv2json.py`, stop cap 10 tool calls, gate `test -s csv2json.py`. Dispatch run ids are not in `ledger pending` (it lists Agent-tool ids), so the append is a plain record.
- Where the sections below mention the relay, seven beats, or the 10 minute budget, this block wins. `tools/demo/PROMPT.md` and `tests/test_opus_demo.py` are the current source.

## Summary

One checked-in runner script (`tools/demo/opus_demo.py`, Python stdlib) prepares a fresh trial directory under `.scratch/demo-030/<stamp>/trial/`, copies only `fixtures/build-test-verify/S/SPEC.md`, writes two slots files (luna build, haiku review), prints the beat checklist and the paste prompt (`tools/demo/PROMPT.md`), then starts `claude --model opus` under `asciinema rec` when asciinema is installed. The opus session runs seven beats: vendor gate, luna build through the `agents-inc:relay` subagent (live rows), haiku review through the relay, the hidden judge run by opus, a free-model summary through `mask.sh`, the native `agents-inc:luna` versus haiku comparison, and ledger read-back with a supervisor verdict. When the operator exits claude, the runner converts the cast to a GIF with `agg`. A `--dry-run` mode writes files and prints the prompt without launching anything. A stdlib unittest covers that mode.

## Technical Context

**Language/Version**: Python 3.10+ stdlib (matches `tools/governance_demo.py` [verified tools/governance_demo.py:13-23]); prompt as Markdown.
**Primary Dependencies**: `agents-inc` CLI (doctor, dispatch, ledger) [verified agents_inc/install/cli.py:222]; agents-inc mod (relay + luna types) [verified mods/agents-inc/README.md:7-8,44]; optional `asciinema`, `agg` (Homebrew; absent now [verified `which` 2026-11-06]); optional `codex` [verified /opt/homebrew/bin/codex].
**Storage**: files only: trial dir and slots under `.scratch/demo-030/<stamp>/` (git-ignored [verified .gitignore:241]); cast and GIF in the same folder; run dirs written by dispatch.
**Testing**: `python3 -m unittest tests.test_opus_demo` (stdlib unittest, same style as `tests/test_governance_demo.py` [verified tests/test_governance_demo.py:1-11]).
**Target Platform**: macOS operator host, Claude Code terminal; Claude-only machines (Story 3).
**Project Type**: CLI helper plus prompt text inside an existing Python repo.
**Performance Goals**: whole run under 10 min wall clock (FR-001, SC-002); budget in table below.
**Constraints**: $0 (FR-005, P5); no network from the runner; agents-inc must be the whole Bash call [verified skills/workerbee/QUICKREF.md:64-65]; no tmux or second pane (FR-009).
**Scale/Scope**: one fixture (S), one operator, one recording per run.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **P1 Repo-scoped writes: PASS.** Trial dir, slots, cast and GIF all sit under `<repo>/.scratch/demo-030/` (git-ignored). Delegate scope is the trial dir (`FILES_IN_SCOPE`). The free-key check tests whether a key file exists or an env var is set. It never reads a value [verified constitution P1; wrapper key paths mask.sh:14,142, gask.sh:16, oask.sh:16].
- **P2 Labor ladder: PASS.** The build goes to the Grunt rung (luna, Codex side), the review to the Grunt pair (haiku), and the free model also sits at Grunt [verified docs/HOW-IT-WORKS.md:258]. Opus is the Orchestrator and manages [verified QUICKREF.md:19]. When codex is absent, the build goes to haiku. That stays on the same rung, so it is a vendor fallback, not an escalation.
- **P3 No self-graded gates: PASS.** Opus runs `hidden/acceptance.py` itself. `hidden/` is not copied into the trial dir (FR-003); the delegate cwd is the repo root, so the path stays reachable, and the ban plus the post-run grep in point 3 are the control. A green `outcome=` counts only with GATES [verified QUICKREF.md:31]. For native luna, the parent verifies the report [verified docs/DECISIONS.md D69].
- **P7 Nickname discipline: PASS.** luna is reached only as `--model luna` on dispatch or relay (an allowed relay model [verified relay.ts:60; README.md:41]) and as `subagent_type: "agents-inc:luna"`. The Agent `model` parameter is never set to `luna` [verified specs/028-agents-inc-as-mod/spec.md:136].
- **P8 Delegation prompt contract: PASS with justification.** Dispatch renders and lints the 14-element prompt from slots [verified QUICKREF.md:11,52]. The relay Agent call is a courier: its registered prompt says call the tool once and add nothing, with `maxTurns: 3` [verified mods/agents-inc/hooks/relay.ts:12-14,37], and the dispatch it starts carries the linted contract. So the relay call is not a dispatch prompt under P8 and gets no 14-element block. The haiku native-beat Agent call is a Claude Agent-tool call, so P8 binds it [verified constitution.md:52]; PROMPT.md carries one 14-element block for that call only. The `agents-inc:luna` call is exempt (spec 028 Q5, D69) [verified constitution.md:52].

Re-check after Phase 1: unchanged.

## Spec conflicts

1. **Ledger row content (US1 scenario 5, Key Entities).** The spec says the row "names the delegate, rung, outcome and verifier". The dispatch row holds `model`, `tier`, `provider` and `status: dispatched`, with no outcome or verifier field [verified agents_inc/host_ledger.py:113-132]. `ledger pending` prints only id, model, task, timestamp [verified host_ledger.py:252-258]. Resolution: opus prints `ledger pending` (row present), then records the supervisor verdict with `agents-inc ledger append --node-id <run_id> --verdict pass` [verified host_ledger.py:224-226]. It then runs `ledger pending` again to show the row has left the pending list. For the outcome it reads `outcome=` from the status line [verified agents_inc/install/dispatch.py:1088]. The verifier is opus, stated in the beat line. Resolved in spec.md US1 scenario 5 (2026-11-06).
2. **Free-model key location.** The planning brief named `~/.config/workerbees/.env`. The wrappers read env vars, then key files, then `~/Projects/.env` [verified mask.sh:14,142-150; gask.sh:15-16,81-84; oask.sh:15-16,90-99]. Resolution: the runner checks env var set or key file non-empty. A key held only in `~/Projects/.env` reports `maybe`, because the runner may not read it (P1). Opus then tries the wrapper, and a `no API key` error becomes the skip NOTE.
3. **Trial dir location.** The relay always passes `--cwd <session cwd>` [verified relay.ts:63-65] and refuses slots outside it [verified relay.ts:61-63]. So the trial dir cannot be an "empty" directory outside the repo. Resolution: `<repo>/.scratch/demo-030/<stamp>/trial/` is empty apart from SPEC.md. GATES run with `cwd` set to that relative path [verified agents_inc/install/dispatch.py:1238-1239].
4. **Story 3 review independence.** With codex absent, both build and review are haiku. Resolution: keep the review in a separate dispatch (fresh session) and print `NOTE: codex absent -> haiku (build and review share a model)`.
5. **"Runner starts and stops the recording" (FR-008)** sits next to "operator pastes prompt" (US1). Resolution: the runner wraps the claude session: `asciinema rec <cast> --command "claude --model opus"`. Recording stops when the operator exits claude, and then the runner runs `agg`.

## Design decisions (points 1-9)

### 1. Runner location and shape
- Files: `tools/demo/opus_demo.py` (Python stdlib, argparse) and `tools/demo/PROMPT.md`. Python matches the existing `tools/*.py` demos and their tests [verified tools/governance_demo.py; tests/test_governance_demo.py:8-11]. A subfolder keeps the prompt next to its runner.
- Steps:
  1. `agents-inc doctor`: require a `READY` line. Record `luna type: ready|off|unavailable`. Record warnings `MOD_NOT_INSTALLED` [verified README.md:23] and `WB_SANDBOX_EXCLUDE_MISSING` [verified QUICKREF.md:63].
  2. `shutil.which("codex")`.
  3. Free-key presence (see point 4).
  4. Make `.scratch/demo-030/<UTC stamp>/trial/` and copy `fixtures/build-test-verify/S/SPEC.md` only. Assert that no `hidden` path exists under trial.
  5. Write `slots-build.json` (model luna, or haiku when codex is absent) and `slots-review.json` (haiku).
  6. Write `prompt.txt` = PROMPT.md with paths substituted. Print it and the beat checklist.
  7. With `--record` (the default when asciinema is present): `asciinema rec <stamp>/demo.cast --command "claude --model opus"`, then `agg demo.cast demo.gif`.
- When asciinema is absent: print `NOTE: asciinema not installed -> running without recording (brew install asciinema agg)` and exec `claude --model opus` directly.
- When agg is absent: print `NOTE: agg not installed -> cast kept, no GIF`.
- When doctor is not READY: print the doctor line and exit 2 before any write.
- Flags: `--dry-run` (steps 1-6 with doctor and codex results injectable, no claude, no asciinema), `--no-record`, `--root <repo>`. The runner calls `os.chdir(root)` before it launches `claude` so the relay's session cwd is the repo root and the slots files sit inside it.
- Install line: `brew install asciinema agg` [assumed: both Homebrew formulas exist; probe `brew info asciinema agg` in implement].

### 2. Paste prompt and primary live-view path
- Dispatch path (revised): one Bash call with `run_in_background: true`, only the plain dispatch command with `--slots <abs path> --model <m>`. No relay, no Monitor. The pane shows the rows.
- Beats, one printed plain-English line each:
  1. `BEAT 1 routing: vendor gate: operator named luna -> luna (Grunt, Codex) builds, opus verifies`.
  2. `BEAT 2 build: luna builds csv2json, live in the side pane`.
  3. `BEAT 3 verify: opus ran the hidden judge, exit <rc>, passed <n> of <total>, traps <n> of <traps>; ledger verdict <pass|fail>`.
- Order rule: the build and the review run one after the other, never in parallel, because two delegates in one cwd trip `snapshot-not-clean` [verified QUICKREF.md:33]. Beat 6 runs after beat 3 for the same reason (the mod pins the tree [verified README.md:52]).

### 3. Verification
- Opus runs `python3 fixtures/build-test-verify/S/hidden/acceptance.py <abs trial dir>` as one Bash call [verified acceptance.py:5,65: argv[1] is the dir, exit 0 iff all pass].
- Opus reads the JSON summary (`traps_passed`, `traps` [verified acceptance.py:62]) and the case rows with `trap: true`. It names the four trap ids: `no-types-empty-is-string`, `types-True-stays-string`, `select-unknown-is-error`, `ragged-row-no-partial-output` [verified acceptance.py:32,33,35,40].
- The judge also checks the delegate's own tests and its VERIFICATION.md claims [verified acceptance.py:42,47].
- If the judge fails while the delegate claimed PASS, opus prints the judge output verbatim and calls the demo red (edge case).
- Both the build and the review slots set `FILES_IN_SCOPE` to the trial dir, and both `CONSTRAINTS` forbid reading anything under `fixtures/` or `.scratch/bench-*`. The delegate cwd is the repo root [verified mods/agents-inc/hooks/relay.ts:65; agents_inc/install/dispatch.py:931], so the ban is a prompt control, not a deterministic one (P4). After each dispatch opus runs `grep -c -e 'hidden/' -e 'acceptance.py' <run dir>/events.jsonl <run dir>/stdout.md` and calls the run red on a hit.

### 4. Free-model beat
- Order: mistral, then gemini, then openrouter, per `free_order` [verified agents_inc/routing.json:12]. The wrappers map from routing.json [verified routing.json:14].
- Key presence (the runner never reads values):
  - mistral: `MISTRAL_API_KEY` set, or `~/.config/devstral/api_key` non-empty [verified mask.sh:14,142].
  - gemini: `GEMINI_API_KEY`/`GOOGLE_API_KEY` set, or `~/.codex-bridge/gemini-key` [verified gask.sh:16,84].
  - openrouter: `OPENROUTER_API_KEY` set, or `~/.codex-bridge/openrouter-key` [verified oask.sh:16,91].
  - A key file shorter than 20 bytes reports `maybe` (mask.sh rejects keys under 20 characters). The runner prints `free: mistral=yes|maybe|no ...`.
- Call: one Bash call `{ printf 'Summarize this delegate report in 3 lines:\n'; cat <run dir>/stdout.md; } | bash skills/codex-bridge/scripts/mask.sh --tier cheap` (prompt on stdin, never a shell argument; mask.sh reads stdin when no prompt argument is given) [verified mask.sh:131-133]. The wrapper has no filesystem access, so the text is fed to it [verified QUICKREF.md:7].
- On `no API key` [verified mask.sh:162] or a quota error: `NOTE: mistral skipped (<reason>) -> trying gemini`. After all three fail: `NOTE: no free model reachable -> beat 5 skipped`.
- [assumed] The Claude Code Bash sandbox proxy may refuse the provider host. In that case opus reruns with that host in `allowed_domains`, otherwise it prints a NOTE.

### 5. Native luna beat (Story 2)
- Task, the same for both: "Run `wc -l <trial>/SPEC.md` with Bash, Read the first 5 lines of `<trial>/SPEC.md`, report the line count and the title line." This is read-only, so it fits the scout exception [verified QUICKREF.md:8].
- Calls: a general subagent with model haiku, carrying the 14-element block (P8), and `Agent subagent_type: "agents-inc:luna"` with a plain prompt (P8 exempt). Both are started in one message, so they run in parallel.
- Observable from the parent:
  - the result text [verified spec 027:44 shape for Agent results];
  - a `luna failed:`/`luna quota-paused:` prefix on failure [verified README.md:50];
  - a changed-tree line [verified README.md:52];
  - the host-ledger record with `source: native-luna` [verified D69 Q2].
- Opus prints one line per difference (count, title, failure prefix, changed-tree line, ledger source), or `none`.
- UNKNOWN: whether the parent can read the subagent transcript path or its per-step `model` and usage fields (spec 028 FR-008 says usage is tagged with the luna slug [verified spec 028:143]). Cheapest probe in implement: run the two Agent calls once, then `ls -t ~/.claude/projects/*agents_Inc*/` and look for a subagent jsonl, and grep it for `"model"`. If none is readable, beat 6 compares result text plus the ledger source only and says so.

### 6. Degradation (Story 3)
- Detection: `shutil.which("codex") is None`, or doctor prints `luna type: off|unavailable`.
- Runner output: `NOTE: codex absent -> haiku`. It writes `slots-build.json` with `MODEL: haiku` (the runner records the chosen model in `demo.json`), and prompt.txt substitutes the model and marks beat 6 `SKIP: luna type not offered (codex absent)`.
- Beats that still run: 1, 2 (haiku), 3, 4, 5, 7. SC-005 holds.
- `MOD_NOT_INSTALLED` turns beats 2 and 3 into the plain-dispatch fallback and beat 6 into a skip.

### 7. Tests
- `tests/test_opus_demo.py` (stdlib unittest), importing `tools/demo/opus_demo.py` through a `sys.path` insert as in the governance test. Cases:
  - (a) dry-run writes trial/SPEC.md and both slots files;
  - (b) no `hidden` path in trial;
  - (c) slots carry the 8 required slots plus GATES [verified QUICKREF.md:32];
  - (d) printed prompt contains the 7 `BEAT` lines and the `vendor gate:` line;
  - (e) injected `codex=None` gives `NOTE: codex absent -> haiku`, build model haiku and a beat 6 SKIP;
  - (f) injected doctor without READY exits 2 and writes nothing;
  - (g) the free-key check never opens a file (assert with a patched `open`, or only `os.path.getsize`/`exists` used);
  - (h) asciinema absent prints the NOTE.
- Stretch: `agents-inc dispatch --slots <file> --model haiku --dry-run` renders and lints the slots [verified QUICKREF.md:52]. Run it as an optional test, skipped when `agents-inc` is not on PATH.

### 8. Timing budget (revised: target 30 s)
| beat | budget |
|---|---|
| runner: doctor + setup | 5 s (before the session starts) |
| 1 routing line | 2 s |
| 2 luna build, csv2json.py only | 20 s |
| 3 leak grep, judge, ledger append | 8 s |
Slots `STOP_RULE` caps the build at 10 tool calls. Gate `timeout_s` is 30 s. [assumed] Build time under 20 s is not yet measured; the first recorded run fills it in `demo.json`.

### 9. Final task
The last task in tasks.md is "Move specs to DomI": `bash ~/Projects/DomI/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply` (spec Assumptions, final bullet).

## Project Structure

### Documentation (this feature)

```text
specs/030-opus-terminal-demo/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md        # next phase
```
No `contracts/`: this is an internal tool with no external interface. The AGENTS.md agent-context marker step is skipped because this is a consumer repo.

### Source Code (repository root)

```text
tools/demo/
├── opus_demo.py    # runner (new)
└── PROMPT.md       # paste prompt template (new)
tests/
└── test_opus_demo.py   # dry-run unittest (new)
.scratch/demo-030/<stamp>/   # runtime only, git-ignored
```

**Structure Decision**: new `tools/demo/` folder; no agents-inc code changes (surgical, out of scope).

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| P4 residual: `hidden/` reachable by path from the delegate cwd (repo root) | The relay pins cwd to the session cwd (relay.ts:65) and refuses slots outside it | Copying the fixture to a throwaway repo would hide `hidden/` but lose the relay live view, which FR-009 requires |

## Scope left out

tasks.md, manim, tmux, the M fixture, new agents-inc features, free-model live rows (the relay refuses free models [verified relay.ts:59]).

## LESSON-CANDIDATE

- QUICKREF has no pointer to the wrapper key paths (`~/.config/devstral/api_key`, `~/.codex-bridge/{gemini,openrouter}-key`).
- QUICKREF does not say that relay dispatch cwd is pinned to the session cwd (`relay.ts:63-65`).
