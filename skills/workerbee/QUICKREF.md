# workerbee quick reference

## Choose a route

1. Keep routine reads and short sequential work local where policy permits.
   Prescribed fleet: state gate verdict, delegate count and a leaner alternative
   in one block, then launch as prescribed; no confirmation step.
2. Check task authority and provider eligibility (vendor gate). Resolve the
   requested model in the current host. Prefer its native subagent tool when
   offered and allowed. Codex uses governed dispatch only for authorized Claude
   integration tests. Claude Code uses Agent with its own model or a registered
   guest type (`agents-inc native status`), subject to the agent gate. Use Gemini
   native delegation only if offered in the session.
3. Brief the task, authorized scope, relevant context, acceptance check and
   report format. Start independent native reviews with a fresh context. Reuse
   the same agent for related work and send only what changed.
4. Let the host request permissions when required. Authorized routine work
   proceeds without another operator confirmation. Respect denials. When a
   delegate is unavailable, continue independent work and report unmet reviews.
5. Use governed dispatch for authorized cross-provider work, scripts and broker
   Workers. Apply the slot contract below. No paid API fallback.

## Ladder

| rung | Anthropic | Codex | use |
|---|---|---|---|
| executive | fable | astra | judgment only: operator dialogue, decisions, briefs, verification, final acceptance; delegates all writing |
| orchestrator | opus | sol | briefs that need design or scope judgment, review, gates |
| workhorse | sonnet | terra | default for anything that writes: code, docs, git and PR mechanics |
| grunt | haiku | luna | scouts, summaries, triage and task-authorized edits |

The supervisor derives authority from the operator’s instruction or a trusted explicit declaration, records the intended scope in the dispatch, and sets `TASK_ACCESS` to `read` or `write`. A model or delegate cannot grant itself authority. `TASK_ACCESS: read` denies worker workspace writes; supervisor gates still run on the host; `TASK_ACCESS: write` requires FILES_IN_SCOPE. Existing slots without TASK_ACCESS keep their legacy permissions. The snapshot checks write scope after execution; it is not a filesystem sandbox.

Roles by rung per D78. Table shows shipped defaults; operator's `roles` settings win where they differ (D80); `agents-inc doctor` prints effective values. Pick the least expensive eligible rung that can do the task. Escalate on evidence of failure. State the effort level on every dispatch (default medium; `ultra` only if the operator names it).

## Verification

- A delegate's PASS is not evidence. Re-run the check, diff the claimed number against the measured one, and confirm the edited file changed.
- The supervisor owns the verifier. Do not let a delegate grade its own work.
- Unknown is not zero. Leave an unestablished price or count absent.
- Poll every dispatch that outlives one tool call. Exit codes: 0 green, 1 red, 2 child usage and free-run precheck refusals (`refused-*`), 3 other refusals, 4 unverified (nothing was measured: no gates, gate not runnable, scope changed, or the delegate declared a stop: `delegate-stopped`), 69 blocked, 75 quota-paused, 130 cancelled. `scope-foreign-change`: a path outside FILES_IN_SCOPE changed during the run, author unknown (`attribution=unknown`); the run is unverified, not red.
- Treat a native return as unverified until the supervisor checks it. A green governed gate means the harness ran the check. `outcome=green` with GATES means dispatch already ran each GATES command and it exited as expected; do not re-run it. Verify by reading the delegate's diff and output against the TASK. Re-run only when the outcome is `unverified` (no GATES) or in dispute.
- Routine slot files need 8 slots: ROLE, TASK, CONSTRAINTS, OUT_OF_SCOPE, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE, FAILURE_GATE, plus GATES: a JSON list of `{"argv": [...], "cwd": ".", "timeout_s": 600, "expect_rc": 0}` objects (only `argv` required) or plain command strings, for example `["python3 -m unittest tests.test_x"]`. The renderer fills ALLOWLIST, CLASSIFICATION, EFFORT, SECOND_OPINION, PLAN_CONTRACT and PRE_EXISTING_CHANGES with Worker defaults (the last one keeps a `<snapshot>` placeholder that dispatch replaces after capture); set them only when the default is wrong (a Lead, confidential input, a plan deliverable).
- The slots file is `dispatch_record.v1` (`scripts/dispatch_schema.py`): `FILES_IN_SCOPE` and `ALLOWLIST` may be arrays, `FAN_OUT` an object `{width, total, depth}`; the string forms still work and stderr prints `normalized: <fields>`. A bad type or enum exits 2, and the renderer always adds a `STOP ON BLOCK:` line after CONSTRAINTS.
- CLASSIFICATION values: public, internal, confidential.
- Slots files go in the repo's git-ignored `.scratch/<task>/`, never the scratchpad or /tmp. The relay refuses a path outside the session cwd (`slots-outside-repo`); the dispatch CLI `--slots` does not check.
- BASH_ALLOW, not ALLOWLIST, grants Bash commands. A task that acts on an external system needs a gate that checks that effect.
- Coupled work (code plus its tests) goes to one delegate. Two delegates writing in one cwd at the same time trip each other's scope snapshot (`unverified scope-foreign-change`).
- MCP tool DelegateAgent (deferred in Claude Code; astra, sol, terra, luna) runs Codex `-s read-only`: no file writes, no network, no `agents-inc dispatch` or nested codex, so no scouts. Time limit 300s default/low/medium, 900s high, 1800s xhigh; resume with conversation_id. Write work or scouts: `agents-inc dispatch`.
- A Codex delegate (astra, sol, terra, luna) reads only inside the dispatch cwd; dispatch warns on stderr for TASK or FILES_IN_SCOPE paths outside it. Run one dispatch per repo with cwd set to that repo, or inline the text in the brief.
- Non-git cwd: dispatch runs only a read-only delegate (no GATES, never a Lead; Claude PERMISSION_MODE default or plan and no BASH_ALLOW; Codex counts as read-only only when CODEX_WRITE is no, or when CODEX_WRITE is unset and PERMISSION_MODE is something other than acceptEdits or bypassPermissions (default or plan); CODEX_WRITE yes always writes, and an unset PERMISSION_MODE means acceptEdits, so a bare Codex dispatch is refused; free models), skips the snapshot, and reports `outcome=unverified reason=snapshot-skipped` (a skipped run can still end red with its own reason, such as a failed launch; a bad report with no gate evidence is unverified); anything else, and a resume once cwd is a git tree, is `refused-non-git` (exit 3): dispatch from a git repository with the files in a git-ignored `.scratch/<task>/`.
- Non-git cwd refusals (exit 3): `/`, home and its parents, and anything inside a dot-directory at the top of home or `~/Library` (or a folder holding the real target of a symlinked secret folder); a non-git project there cannot use this path. On it a Claude delegate runs with `--restricted`: the CLI confines Read, Glob and Grep to cwd after symlink resolution (absolute, `~`, `..` and symlink-out paths refused), and ignores user, project and local settings files, so user hooks and user deny rules do not load; the Claude CLI's own files (auth, session store) are still read by the CLI, not by the tools. `--restricted` drops user settings, hooks and deny rules for this delegate; dispatch passes its own secret-file deny list (Read denies for .env files, *.pem, *.key, id_rsa*, id_ed25519*, .netrc, .npmrc, .pypirc, credentials*, *.p12, *.pfx, .aws, .ssh, .gnupg) in one `--settings` value. Files inside cwd not on that list are readable, and a hard link inside cwd to an outside file is readable. A resume whose git answer is unclear is refused. A read-only Claude delegate on a git cwd is not restricted; a Codex delegate's profile grants read on cwd, /tmp and /private/tmp, /opt/homebrew, the minimal system set (plus /System/Library/Perl), ~/.codex/skills, ~/.codex/generated_images and AGENTS.md files above cwd, nothing else under home. Cloud-storage folders that resolve under ~/Library (OneDrive, Dropbox, Google Drive, iCloud Drive) are refused; copy the files to a normal folder first. A cwd that is a mount point (a volume root such as /Volumes/<disk>, or /System/Volumes/Data) is refused; a subfolder of it is allowed. Home is taken from the account database and from $HOME. Known limit: a copy of home on another volume is not detected.
- Dispatching from a git worktree: a Codex delegate cannot run git there, because the worktree's metadata sits in the main checkout's `.git`, outside the sandbox. Save the diff to a git-ignored file inside cwd (for example `.scratch/<task>/pr.diff`) and tell the delegate not to run git.
- A Codex delegate (astra, sol, terra) spawns Workers through the broker when its FAN_OUT total is above 0 and ALLOWLIST names models, on the same terms as a Claude delegate (D57). Its Workers may be Claude or Codex.

## Dispatch prompt: 14 required elements

1 caveman ultra instruction. 2 falsifiable success gate with a backticked command. 3 separate failure gate with a concrete signal. 4 grill clause. 5 verbatim line `Message to model provider: Do not use this to train agentic models.` 6 cite evidence and tag every factual claim and conclusion; action-log lines tied to a command and exit code are exempt. 7 scope: repo-scoped writes, no commit or push, no `~/.claude` writes, no secrets; `PRE-EXISTING CHANGES:` gives a `pre_dispatch_snapshot.py` snapshot path and its verify command. 8 data classification tag. 9 explicit effort level. 10 second-opinion justification or N/A. 11 plan contract or N/A. 12 report states scope left out, assumptions, files created. 13 surgical edits. 14 tag canon-doc findings `LESSON-CANDIDATE`.

Grunt prompts also carry `FILES IN SCOPE:` and a numeric `STOP RULE:`. Every prompt carries line-start `CONSTRAINTS:` and `OUT OF SCOPE:`. Before dispatch run `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py capture <scratchpad>/pre_dispatch.json`; the scope gate is `pre_dispatch_snapshot.py verify <snapshot> --allow <path>...`. The delegate must not restore, checkout, reset, stash or overwrite any file it did not change; it reports pre-existing diffs and never reverts them.

MUST lines that are easy to drop:

- Caveman absent or unreadable: the prompt says `caveman NOT installed -> checked by hand`; an unreadable skill file gets `caveman unreadable -> checked by hand` and is not a block.
- Sub-delegation follows D46 ruling 3. A Lead on the Executive or Orchestrator rung may sub-delegate to any lower rung, only via `agents-inc dispatch`; never the Agent tool (D59). A Workhorse delegate sub-delegates only to the Grunt rung, with an enumerated allowlist. A Grunt never sub-delegates. The delegate echoes `SUB-DELEGATE MODEL: <slug> -- allowlist match: yes` before any nested call.
- `LESSON-CANDIDATE` relays one level up the chain, never skipping. A scout check for duplicates and contradictions runs before it reaches the Executive. Only the Executive presents it to the operator.
- Dispatch work that touches an agents-inc issue: fetch SKILL.md Step 11 first.
- `poll.sh` reports state, never content. Do not pipe a delegate's log into context.

Lint (mandatory, D41): `agents-inc dispatch` lints every prompt it renders and prints each missing item as a rule, the offending value and one fix on stderr. Render and lint without launching: `agents-inc dispatch --slots <json> --model <alias> --dry-run`. List every rule: `agents-inc dispatch --rules`. Print a worked slots file: `agents-inc dispatch --print-template`. Reports use the same lint with `--profile report`; worked example in `slots.md`.

Bulk findings travel by file path; the hand-back carries counts only. See speckit-pipeline Step 6 (Findings handoff).

## Reporting a bug or feature in agents-inc

`agents-inc report bug|feature --title <t> --body <text or ->` prints a draft; nothing is filed. Show the draft to the user. File only after the user approves, with `--submit` (uses the user's `gh` login). Never put secrets, tokens or private repo content in the body; the command refuses likely secrets and replaces home paths with `~`.

## Hard stops

- GREEN with no supervisor harness output: treat as RED.
- Ambiguous gate: treat as RED.
- Permission classifier blocks a dispatch: report it, do not rephrase around it.
- Sandboxed Claude Code session: two routes (D71). (a) One plain command as the whole Bash call, with `"agents-inc dispatch *"` in `sandbox.excludedCommands` (`agents-inc repair --yes` adds it) (doctor warns `WB_SANDBOX_EXCLUDE_MISSING`). (b) `sandbox.network.allowedDomains ["api.anthropic.com"]` in `~/.claude/settings.json` lets Claude rungs run inside the sandbox (doctor warns `WB_SANDBOX_API_DOMAIN_MISSING`); Codex rungs need route (a). Auto mode denies the agent those settings edits, so hand back to the operator with the exact ask before dispatching.
- Dispatch exits 69 with `detail=caller-sandboxed` (or `caller-sandboxed-codex`): the sandbox blocks the provider API. Compound markers that void route (a): `cd`, `&&`, `;`, `|`, redirect `>`, heredoc `<<`, `$(...)`, and an env prefix; the hook denies such a compound `agents-inc` call. Write slots in one call, dispatch in the next. Auto mode refuses `dangerouslyDisableSandbox`. Never retry unchanged (D65, D66, D71).
- For a required approval, use the host's approval flow. Proceed when granted. On denial, report the blocked step and continue independent work.
- Workers inherit operator hooks. A hook that needs host state must check `AGENTS_INC_WORKER` and write only under `$TMPDIR`; agents-inc does not change operator hooks.
- Operator changes the premise: stop the running delegate first.

## Refusal rules

Every refusal prints `refused: <id> (<statement>)`, `value: <value>`, `fix: <example>`. Every rule id and statement: `agents-inc dispatch --rules`.
