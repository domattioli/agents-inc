# workerbee quick reference

Short form of `SKILL.md` for routine dispatch. Read the full `SKILL.md` and `skills/codex-bridge/SKILL.md` only when you dispatch to a non-Claude rung, write a dispatch prompt from scratch, or a gate result is in dispute.

## Before any dispatch

1. Dispatch gate (D78). Estimate the direct tool calls the task needs. Three or fewer that write nothing: do it yourself. Three or fewer that edit files: a native workhorse subagent with a short brief (Claude Code: `Agent` with model `sonnet`; Codex: its native subagent), then run one check yourself, because no harness ran gates. Anything larger: `agents-inc dispatch`. Exceptions that send a small task to `agents-inc dispatch`: one of three or more parallel tasks, large output you should not hold, or code work under a repo dispatch policy. Bare-API wrappers (`gask.sh`, `mask.sh`, `oask.sh`) have no filesystem, shell or repo access. Paste real source into the prompt or pick a delegate that has them.
2. Vendor gate picks the rung. Route (D79, proposed): in Claude Code with the agents-inc mod, native agent types (item 4a); without the mod, and for scripts, CI and broker Workers, `agents-inc dispatch`. Naming a model chooses the rung, not the route. The `Agent` tool is only for read-only foreground scouts (Explore, Plan) and the item 1 native edit; the agent gate in enforce mode blocks every other use, the native edit included (D61, D78). Claude is the default vendor. Codex (astra, sol, terra, luna), Gemini, Mistral and OpenRouter open only when the operator names one, a stated capability needs it, or the operator declared budget mode (free grunts only). State one line: `vendor gate: <gate> -> <delegate>`.
3. Chain resolves by ladder (D46): higher rung manages; same rung, ask the operator one question. State the chain only when surprising.

4. Dispatch through `agents-inc dispatch --slots <json> --model <slug>` (D47). The CoS writes the slots file and pastes nothing: the command renders, lints, snapshots, launches, and verifies, and returns one status line. Files stay in the run directory.
4a. Route in Claude Code with the agents-inc mod: native agent types (D79, proposed). Claude rung: Agent with `model`. Codex or free model: Agent `subagent_type: agents-inc:<nickname>`; the delegate pane and `agents-inc native status` list the registered types. The brief is the Agent prompt (item 4 fields still apply); the parent verifies the report. The relay type, `mcp__agents-inc__run` and `@alias` routes exist only after `agents-inc install --legacy-routes`. Use Bash `agents-inc dispatch --slots` when the mod is absent.
5. Fan-out (D48): slots carry `FAN_OUT: width <n>, total <n>, depth <n>` (default by rung: Executive and Orchestrator 3/6/2, Workhorse 2/4/1, Grunt 0); Workers <= floor(20 / findings cap); report line `WORKERS SPAWNED: n`.

## Ladder

| rung | Anthropic | Codex | use |
|---|---|---|---|
| executive | fable | astra | judgment only: operator dialogue, decisions, briefs, verification, final acceptance; delegates all writing |
| orchestrator | opus | sol | briefs that need design or scope judgment, review, gates |
| workhorse | sonnet | terra | default for anything that writes: code, docs, git and PR mechanics |
| grunt | haiku | luna | read-only: scouts, summaries, triage; writes no code |

Roles by rung per D78. Table shows shipped defaults; operator's `roles` settings win where they differ (D80); `agents-inc doctor` prints effective values. The executive (the session that talks to the operator) delegates any task a well-briefed orchestrator or workhorse delegate can do. Pick the cheapest rung that will not get the answer wrong. Escalate on evidence of failure. State the effort level on every dispatch (default medium; `ultra` only if the operator names it).

## Verification

- A delegate's PASS is not evidence. Re-run the check, diff the claimed number against the measured one, and confirm the edited file changed.
- The supervisor owns the verifier. Do not let a delegate grade its own work.
- Unknown is not zero. Leave an unestablished price or count absent.
- Poll every dispatch that outlives one tool call. Exit 0 means returned, not verified.
- Trust a green gate, not a green report. `outcome=green` with GATES means dispatch already ran each GATES command and it exited as expected; do not re-run it. Verify by reading the delegate's diff and output against the TASK. Re-run only when the outcome is `unverified` (no GATES) or in dispute.
- Routine slot files need 8 slots: ROLE, TASK, CONSTRAINTS, OUT_OF_SCOPE, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE, FAILURE_GATE, plus GATES: a JSON list of `{"argv": [...], "cwd": ".", "timeout_s": 600, "expect_rc": 0}` objects (only `argv` required) or plain command strings, for example `["python3 -m unittest tests.test_x"]`. The renderer fills ALLOWLIST, CLASSIFICATION, EFFORT, SECOND_OPINION, PLAN_CONTRACT and PRE_EXISTING_CHANGES with Worker defaults (the last one keeps a `<snapshot>` placeholder that dispatch replaces after capture); set them only when the default is wrong (a Lead, confidential input, a plan deliverable).
- The slots file is `dispatch_record.v1` (`scripts/dispatch_schema.py`): `FILES_IN_SCOPE` and `ALLOWLIST` may be arrays, `FAN_OUT` an object `{width, total, depth}`; the string forms still work and stderr prints `normalized: <fields>`. A bad type or enum exits 2, and the renderer always adds a `STOP ON BLOCK:` line after CONSTRAINTS.
- CLASSIFICATION values: public, internal, confidential.
- BASH_ALLOW, not ALLOWLIST, grants Bash commands. A task that acts on an external system needs a gate that checks that effect.
- Coupled work (code plus its tests) goes to one delegate. Two delegates writing in one cwd at the same time trip each other's scope snapshot (`snapshot-not-clean`).
- A Codex delegate (astra, sol, terra, luna) reads only inside the dispatch cwd; dispatch warns on stderr for TASK or FILES_IN_SCOPE paths outside it. Run one dispatch per repo with cwd set to that repo, or inline the text in the brief.
- Non-git cwd: dispatch runs only a read-only delegate (no GATES, never a Lead; Claude PERMISSION_MODE default or plan and no BASH_ALLOW; Codex counts as read-only only when CODEX_WRITE is no, or when CODEX_WRITE is unset and PERMISSION_MODE is something other than acceptEdits or bypassPermissions (default or plan); CODEX_WRITE yes always writes, and an unset PERMISSION_MODE means acceptEdits, so a bare Codex dispatch is refused; free models), skips the snapshot, and reports `outcome=unverified reason=snapshot-skipped` (a skipped run can still end red with its own reason, such as a bad report or a failed launch); anything else, and a resume once cwd is a git tree, is `refused-non-git` (exit 3): dispatch from a git repository with the files in a git-ignored `.scratch/<task>/`.
- Non-git cwd refusals (exit 3): `/`, home and its parents, and anything inside a dot-directory at the top of home or `~/Library` (or a folder holding the real target of a symlinked secret folder); a non-git project there cannot use this path. On it a Claude delegate can read any file the user can read apart from the deny rules; a Codex delegate's profile grants read on cwd, /tmp and /private/tmp, /opt/homebrew, the minimal system set (plus /System/Library/Perl), ~/.codex/skills, ~/.codex/generated_images and AGENTS.md files above cwd, nothing else under home. User-level hooks still run for a read-only Claude delegate in a non-git cwd. Cloud-storage folders that resolve under ~/Library (OneDrive, Dropbox, Google Drive, iCloud Drive) are refused; copy the files to a normal folder first. A cwd that is a mount point (a volume root such as /Volumes/<disk>, or /System/Volumes/Data) is refused; a subfolder of it is allowed. Home is taken from the account database and from $HOME. Known limit: a copy of home on another volume is not detected.
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
- Dispatch work that touches an agents-inc issue: fetch SKILL.md Step 11 first.
- `poll.sh` reports state, never content. Do not pipe a delegate's log into context.

Lint (mandatory, D41): `agents-inc dispatch` lints every prompt it renders; by hand, from any directory: `python3 ~/.claude/skills/workerbee/scripts/check_dispatch_prompt.py <prompt_file> [--with-handoff-lint]`. Save the prompt to a file first. Reports: same script with `--profile report`, which checks report elements. Render prompts with `agents-inc dispatch --slots <json> --model <alias> --dry-run` (or `~/.claude/skills/workerbee/scripts/render_dispatch.py --slots <json>`); worked example in `slots.md`.

Bulk findings travel by file path; the hand-back carries counts only. See speckit-pipeline Step 6 (Findings handoff).

## Reporting a bug or feature in agents-inc

`agents-inc report bug|feature --title <t> --body <text or ->` prints a draft; nothing is filed. Show the draft to the user. File only after the user approves, with `--submit` (uses the user's `gh` login). Never put secrets, tokens or private repo content in the body; the command refuses likely secrets and replaces home paths with `~`.

## Hard stops

- GREEN with no supervisor harness output: treat as RED.
- Ambiguous gate: treat as RED.
- Permission classifier blocks a dispatch: report it, do not rephrase around it.
- Sandboxed Claude Code session: two routes (D71). (a) One plain command as the whole Bash call, with `"agents-inc dispatch *"` in `sandbox.excludedCommands` (`agents-inc repair --yes` adds it) (doctor warns `WB_SANDBOX_EXCLUDE_MISSING`). (b) `sandbox.network.allowedDomains ["api.anthropic.com"]` in `~/.claude/settings.json` lets Claude rungs run inside the sandbox (doctor warns `WB_SANDBOX_API_DOMAIN_MISSING`); Codex rungs need route (a). Auto mode denies the agent those settings edits, so hand back to the operator with the exact ask before dispatching.
- Dispatch exits 69 with `detail=caller-sandboxed` (or `caller-sandboxed-codex`): the sandbox blocks the provider API. Compound markers that void route (a): `cd`, `&&`, `;`, `|`, redirect `>`, heredoc `<<`, `$(...)`, and an env prefix; the hook denies such a compound `agents-inc` call. Write slots in one call, dispatch in the next. Auto mode refuses `dangerouslyDisableSandbox`. Never retry unchanged (D65, D66, D71).
- Harness "requires approval" on a delegate call is a missing grant (#54, D58), not a policy refusal: stop, record the exact command, hand back, never route around it. One plain command per Bash call (no `cd`, `&&`, `;`, pipes, loops, shell variables); a compound command matches no grant.
- Workers inherit operator hooks. A hook that needs host state must check `AGENTS_INC_WORKER` and write only under `$TMPDIR`; agents-inc does not change operator hooks.
- Operator changes the premise: stop the running delegate first.
