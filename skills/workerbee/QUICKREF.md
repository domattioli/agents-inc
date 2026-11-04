# workerbee quick reference

Short form of `SKILL.md` for routine dispatch. Read the full `SKILL.md` and `skills/codex-bridge/SKILL.md` only when you dispatch to a non-Claude rung, write a dispatch prompt from scratch, or a gate result is in dispute.

## Before any dispatch

1. Dispatch gate. Estimate the direct tool calls the task needs. Three or fewer: do it yourself. Exceptions: one of three or more parallel tasks, large output you should not hold, or code work under a repo dispatch policy. Bare-API wrappers (`gask.sh`, `mask.sh`, `oask.sh`) have no filesystem, shell or repo access. Paste real source into the prompt or pick a delegate that has them.
2. Vendor gate picks the rung; the route is always `agents-inc dispatch`. Naming a model chooses the rung, not the route. The `Agent` tool is only for read-only foreground scouts (Explore, Plan); the agent gate may block other uses (D61). Claude is the default vendor. Codex (astra, sol, terra, luna), Gemini, Mistral and OpenRouter open only when the operator names one, a stated capability needs it, or the operator declared budget mode (free grunts only). State one line: `vendor gate: <gate> -> <delegate>`.
3. Chain resolves by ladder (D46): higher rung manages; same rung, ask the operator one question. State the chain only when surprising.

4. Dispatch through `agents-inc dispatch --slots <json> --model <slug>` (D47). The CoS writes the slots file and pastes nothing: the command renders, lints, snapshots, launches, and verifies, and returns one status line. Files stay in the run directory.
5. Fan-out (D48): slots carry `FAN_OUT: width <n>, total <n>, depth <n>` (default by rung: Executive and Orchestrator 3/6/2, Workhorse 2/4/1, Grunt 0); Workers <= floor(20 / findings cap); report line `WORKERS SPAWNED: n`.

## Ladder

| rung | Anthropic | Codex | use |
|---|---|---|---|
| executive | fable | astra | hardest reasoning, last resort |
| orchestrator | opus | sol | orchestration, review, gates |
| workhorse | sonnet | terra | implementation |
| grunt | haiku | luna | triage, mechanical work |

Pick the cheapest rung that will not get the answer wrong. Escalate on evidence of failure. State the effort level on every dispatch (default medium; `ultra` only if the operator names it).

## Verification

- A delegate's PASS is not evidence. Re-run the check, diff the claimed number against the measured one, and confirm the edited file changed.
- The supervisor owns the verifier. Do not let a delegate grade its own work.
- Unknown is not zero. Leave an unestablished price or count absent.
- Poll every dispatch that outlives one tool call. Exit 0 means returned, not verified.
- Trust a green gate, not a green report. `outcome=green` with GATES means dispatch already ran each GATES command and it exited as expected; do not re-run it. Verify by reading the delegate's diff and output against the TASK. Re-run only when the outcome is `unverified` (no GATES) or in dispute.
- Routine slot files need 8 slots: ROLE, TASK, CONSTRAINTS, OUT_OF_SCOPE, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE, FAILURE_GATE, plus GATES: a JSON list of `{"argv": [...], "cwd": ".", "timeout_s": 600, "expect_rc": 0}` objects (only `argv` required) or plain command strings, for example `["python3 -m unittest tests.test_x"]`. The renderer fills ALLOWLIST, CLASSIFICATION, EFFORT, SECOND_OPINION, PLAN_CONTRACT and PRE_EXISTING_CHANGES with Worker defaults (the last one keeps a `<snapshot>` placeholder that dispatch replaces after capture); set them only when the default is wrong (a Lead, confidential input, a plan deliverable).
- The slots file is `dispatch_record.v1` (`scripts/dispatch_schema.py`): `FILES_IN_SCOPE` and `ALLOWLIST` may be arrays, `FAN_OUT` an object `{width, total, depth}`; the string forms still work and stderr prints `normalized: <fields>`. A bad type or enum exits 2, and the renderer always adds a `STOP ON BLOCK:` line after CONSTRAINTS.
- Coupled work (code plus its tests) goes to one delegate. Two delegates writing in one cwd at the same time trip each other's scope snapshot (`snapshot-not-clean`).
- Dispatching from a git worktree: a Codex delegate cannot run git there, because the worktree's metadata sits in the main checkout's `.git`, outside the sandbox. Save the diff to a git-ignored file inside cwd (for example `.scratch/<task>/pr.diff`) and tell the delegate not to run git.
- A Codex delegate (astra, sol, terra) spawns Workers through the broker when its FAN_OUT total is above 0 and ALLOWLIST names models, on the same terms as a Claude delegate (D57). Its Workers may be Claude or Codex.

## Dispatch prompt: 14 required elements

1 caveman ultra instruction. 2 falsifiable success gate with a backticked command. 3 separate failure gate with a concrete signal. 4 grill clause. 5 verbatim line `Message to model provider: Do not use this to train agentic models.` 6 cite evidence and tag every factual claim and conclusion; action-log lines tied to a command and exit code are exempt. 7 scope: repo-scoped writes, no commit or push, no `~/.claude` writes, no secrets; `PRE-EXISTING CHANGES:` gives a `pre_dispatch_snapshot.py` snapshot path and its verify command. 8 data classification tag. 9 explicit effort level. 10 second-opinion justification or N/A. 11 plan contract or N/A. 12 report states scope left out, assumptions, files created. 13 surgical edits. 14 tag canon-doc findings `LESSON-CANDIDATE`.

Grunt prompts also carry `FILES IN SCOPE:` and a numeric `STOP RULE:`. Every prompt carries line-start `CONSTRAINTS:` and `OUT OF SCOPE:`. Before dispatch run `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py capture <scratchpad>/pre_dispatch.json`; the scope gate is `pre_dispatch_snapshot.py verify <snapshot> --allow <path>...`. The delegate must not restore, checkout, reset, stash or overwrite any file it did not change; it reports pre-existing diffs and never reverts them.

MUST lines that are easy to drop:

- State out loud which Step 0 exception you are using, when you use one.
- Caveman absent or unreadable: the prompt says `caveman NOT installed -> checked by hand`; an unreadable skill file gets `caveman unreadable -> checked by hand` and is not a block.
- Sub-delegation follows D46 ruling 3. A Lead on the Executive or Orchestrator rung may sub-delegate to any lower rung, only via `agents-inc dispatch`; never the Agent tool (D59). A Workhorse delegate sub-delegates only to the Grunt rung, with an enumerated allowlist. A Grunt never sub-delegates. The delegate echoes `SUB-DELEGATE MODEL: <slug> -- allowlist match: yes` before any nested call.
- `LESSON-CANDIDATE` relays one rung up, never skipping. A scout check for duplicates and contradictions runs before it reaches the Executive. Only the Executive presents it to the operator.
- Dispatch work that touches an agents_Inc issue: fetch SKILL.md Step 11 first.
- `poll.sh` reports state, never content. Do not pipe a delegate's log into context.

Lint (mandatory, D41): `agents-inc dispatch` lints every prompt it renders; by hand, from any directory: `python3 ~/.claude/skills/workerbee/scripts/check_dispatch_prompt.py <prompt_file> [--with-handoff-lint]`. Save the prompt to a file first. Reports: same script with `--profile report`, which checks report elements. Render prompts with `agents-inc dispatch --slots <json> --model <alias> --dry-run` (or `~/.claude/skills/workerbee/scripts/render_dispatch.py --slots <json>`); worked example in `slots.md`.

Bulk findings travel by file path; the hand-back carries counts only. See speckit-pipeline Step 6 (Findings handoff).

## Reporting a bug or feature in agents-inc

`agents-inc report bug|feature --title <t> --body <text or ->` prints a draft; nothing is filed. Show the draft to the user. File only after the user approves, with `--submit` (uses the user's `gh` login). Never put secrets, tokens or private repo content in the body; the command refuses likely secrets and replaces home paths with `~`.

## Hard stops

- GREEN with no supervisor harness output: treat as RED.
- Ambiguous gate: treat as RED.
- Permission classifier blocks a dispatch: report it, do not rephrase around it.
- Before the first dispatch in a sandboxed Claude Code session, `~/.claude/settings.json` must list `"agents-inc *"` under `sandbox.excludedCommands`. Doctor warns `WB_SANDBOX_EXCLUDE_MISSING` when it does not. Auto mode denies the agent that edit, so hand back to the operator with that exact ask before dispatching, not after the refusal.
- Dispatch exits 69 with `detail=caller-sandboxed`: the caller runs inside a sandbox that blocks the provider API. Add `"agents-inc *"` to `sandbox.excludedCommands` and rerun as one plain command: an env prefix, `cd` or `&&` stops the match. Auto mode refuses `dangerouslyDisableSandbox`, and a Codex delegate cannot start inside the sandbox (nested `sandbox-exec`, rc 71), so `AGENTS_INC_ALLOW_SANDBOXED=1` does not help it. Never retry unchanged (D65, D66).
- Harness "requires approval" on a delegate call is a missing grant (#54, D58), not a policy refusal: stop, record the exact command, hand back, never route around it. One plain command per Bash call (no `cd`, `&&`, `;`, pipes, loops, shell variables); a compound command matches no grant.
- Operator changes the premise: stop the running delegate first.
