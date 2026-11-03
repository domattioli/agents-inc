# Dispatch slots: per-task contract elements

Spec 016. Fill each `{{NAME}}` slot for one dispatch, then append
`skills/workerbee/header.md` (or a contract-reference line naming it, for a
delegate that can read files). `agents-inc dispatch --slots <json> --model
<alias> --dry-run` does both from a JSON object keyed by slot name (the
renderer by hand, from any directory:
`python3 ~/.claude/skills/workerbee/scripts/render_dispatch.py --slots
<json>`); it exits 2
naming any required slot that is missing or empty. NOTES defaults to `none`;
STYLE may stay empty. The renderer strips the header's markdown title and
authoring comment and emits header text from the CAVEMAN line.

The renderer uses the first `text` code block below as the template.

```text
ROLE: {{ROLE}}
REPORTING CHAIN: {{DELEGATE}} reports to {{SUPERVISOR}}; {{SUPERVISOR}} reports to {{EXECUTIVE}}; {{EXECUTIVE}} reports to the operator
TASK: {{TASK}}
CONSTRAINTS: {{CONSTRAINTS}}
OUT OF SCOPE: {{OUT_OF_SCOPE}}
FILES IN SCOPE:
{{FILES_IN_SCOPE}}
STOP RULE: {{STOP_RULE}}
SUCCESS GATE: {{SUCCESS_GATE}}
FAILURE GATE: {{FAILURE_GATE}}
PRE-EXISTING CHANGES (pre_dispatch_snapshot.py snapshot and its verify command; never restore, checkout, reset, stash, or overwrite these files; the scope gate is the verify command, which hashes them):
{{PRE_EXISTING_CHANGES}}
NOTES (path under the dispatch scratchpad, or none; rewrite whole per milestone, under 60 lines; notes are not evidence, re-verify any fact taken from them in the report): {{NOTES}}
SUB-DELEGATE MODEL ALLOWLIST: {{ALLOWLIST}}
FAN_OUT: {{FAN_OUT}}
CLASSIFICATION: {{CLASSIFICATION}}
EFFORT: {{EFFORT}}
SECOND-OPINION JUSTIFICATION: {{SECOND_OPINION}}
PLAN CONTRACT: {{PLAN_CONTRACT}}
{{STYLE}}
```

Worked example (read-only scout, every slot filled; render appends header.md below it). JSON source: `skills/workerbee/tests/fixtures/example_slots.json`.

The example has no GATES (a scout writes nothing). A code task adds `"GATES": [{"argv": ["python3", "-m", "unittest", "tests.test_x"]}]` to the JSON; `cwd`, `timeout_s` and `expect_rc` take their defaults, and the renderer appends one sentence naming the command to SUCCESS GATE. A plain string entry such as `"python3 -m unittest tests.test_x"` is also accepted: the renderer splits it with shlex and no shell runs it.

```text
ROLE: Grunt scout (haiku, Agent tool), dispatched by Supervisor (opus) in /path/to/repo.
REPORTING CHAIN: haiku reports to sonnet; sonnet reports to fable; fable reports to the operator
TASK: Read-only scout. 1. Read agents_inc/policy.py. 2. List every function name that contains the word route, with file:line. 3. Return the list; write nothing.
CONSTRAINTS: read-only; no file writes; no network; at most 10 tool calls. Stop-on-block: if a hook or permission classifier blocks a tool call, stop and hand back to the dispatcher; never switch tool to route around it.
STOP ON BLOCK: if a hook, permission classifier or sandbox blocks a tool call, stop and hand back to the dispatcher; never switch to another tool to route around the block.
OUT OF SCOPE: editing any file; judging routing design; running unittest suites.
FILES IN SCOPE:
none (read-only scout)
STOP RULE: stop after 2 failed reads of the same file; report RED and paste the last command output in a fenced block.
SUCCESS GATE: `grep -n 'def .*route' agents_inc/policy.py` output matches the returned list line for line.
FAILURE GATE: any name missing from the list versus `grep -n 'def .*route' agents_inc/policy.py`, or any write reported by `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>`.
PRE-EXISTING CHANGES (pre_dispatch_snapshot.py snapshot and its verify command; never restore, checkout, reset, stash, or overwrite these files; the scope gate is the verify command, which hashes them):
snapshot <snapshot>; verify with `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>` (no --allow: scout writes nothing).
NOTES (path under the dispatch scratchpad, or none; rewrite whole per milestone, under 60 lines; notes are not evidence, re-verify any fact taken from them in the report): none
SUB-DELEGATE MODEL ALLOWLIST: none -- do all work yourself
FAN_OUT: width 0, total 0, depth 0
CLASSIFICATION: internal (repo source, non-secret)
EFFORT: effort control unavailable on this transport; intended level = low
SECOND-OPINION JUSTIFICATION: not applicable -- grunt rung, no escalation trigger fired
PLAN CONTRACT: not applicable -- deliverable is not a plan.
```

## Slots

Schema (`dispatch_record.v1`, #131, D70): `scripts/dispatch_schema.py` validates the slots JSON before render. Structured forms: `FILES_IN_SCOPE` and `ALLOWLIST` as arrays of strings, `FAN_OUT` as `{"width": n, "total": n, "depth": n}`; the old string forms are converted by `normalize()` and named on stderr (`normalized: <fields>`). `schema_version` is optional (1); another value, a wrong type or a bad enum exits 2 with the field named. The renderer always adds a `STOP ON BLOCK:` line after CONSTRAINTS.

Defaults: when ALLOWLIST, CLASSIFICATION, EFFORT, SECOND_OPINION or PLAN_CONTRACT is absent or blank, `render_dispatch.py` fills the Worker default (`none -- do all work yourself`, `internal (repo source, non-secret)`, transport effort, `not applicable` with the reason) and prints `defaults filled: ...` to stderr. A Lead, a confidential input or a plan deliverable sets the slot explicitly. A blank PRE_EXISTING_CHANGES is filled with `snapshot <snapshot>; verify with ...` and one `--allow` per bare path line in FILES_IN_SCOPE; dispatch then replaces `<snapshot>` with the captured path. A hand-written slot keeps the `<snapshot>` placeholder for the same reason.

| slot | element | type | content |
|---|---|---|---|
| ROLE | context | text | rung, model, and who dispatched the delegate |
| TASK | context | text | exact work, files to read first, numbered steps |
| CONSTRAINTS | H4 | text | hard limits the work must respect; rendered line-start `CONSTRAINTS:` |
| OUT_OF_SCOPE | 12, H4 | text | work the delegate must not do; rendered line-start `OUT OF SCOPE:` |
| FILES_IN_SCOPE | 7 | array of string, or text | one path per line; the only paths the delegate may write |
| STOP_RULE | Grunt | text | a number of failed attempts, then report RED |
| SUCCESS_GATE | 2 | text | commands in backticks with the expected output; optional when GATES is set, and the renderer appends one sentence naming each GATES command |
| FAILURE_GATE | 3 | text | conditions that make the task RED; at least one must be a command in backticks, or `check_dispatch_prompt.py` rejects the prompt as element 3 missing |
| PRE_EXISTING_CHANGES | 7 | text | optional: blank means the renderer writes the default text above. `<snapshot>` placeholder: the dispatch wrapper (`agents_inc/install/dispatch.py`) fills it with the snapshot path after capture; hand-written prompts put the path from `pre_dispatch_snapshot.py capture <out.json>` plus the verify command `pre_dispatch_snapshot.py verify <out.json> --allow <path>...` |
| ALLOWLIST | 7 | array of string, or text | models the delegate may spawn, or `none — do all work yourself`. With a FAN_OUT total and depth above 0, a Codex delegate (astra, sol, terra) or a Claude delegate (fable, opus, sonnet) runs as a broker Lead with the rung-allowed models from this list (D57, D60). A Worker's FAN_OUT must be zero |
| FAN_OUT | D48 | `{width,total,depth}` ints, or text | `width <n>, total <n>, depth <n>`; optional: the renderer fills the rung default from a `RUNG` or `MODEL` slot, else Orchestrator (`width 3, total 6, depth 2`); Workhorse `2, 4, 1`; Grunt `0, 0, 0` |
| CLASSIFICATION | 8 | text, first word public, internal or confidential | public, internal, or confidential, with the reason |
| EFFORT | 9 | text naming low, medium, high, xhigh or max (ultra: Codex only) | intended effort level, and whether the transport can set it |
| SECOND_OPINION | 10 | text | why this rung, or `not applicable` with the reason |
| PLAN_CONTRACT | 11 | text | plan deliverable rules, or `not applicable — deliverable is not a plan.` |
| PERMISSION_MODE | optional | text | `default`, `acceptEdits` (default), `plan`, `bypassPermissions` or `auto`; passed to `claude -p --permission-mode`, and Codex write access follows it. Headless `claude -p` with `auto` behaved like `acceptEdits` for grants in the 2026-10-15 probe: unlisted Bash is still denied. Broker-owned: a broker request may not set it |
| GATES | optional | array | commands dispatch runs itself after the delegate exits, with no shell: a JSON list (or a JSON string of one) of `{argv, cwd, timeout_s, expect_rc}` objects, or plain command strings that shlex splits into `argv`. Example: `[{"argv": ["python3", "-m", "unittest", "tests.test_x"], "timeout_s": 300}]`. `argv` required; `cwd` relative to `--cwd` (default `.`, no `..`); `timeout_s` above 0 and at most 3600 (default 600); `expect_rc` default 0. Each argv is also granted to a Claude delegate as an exact Bash rule. Refused: push, commit, sudo, recursive rm, curl, ssh, credential paths |
| BASH_ALLOW | optional | array of string, or text | extra Bash command prefixes granted to a Claude delegate: a list of strings, or one string with a prefix per line. No `*`, parentheses or backticks; same refusals as GATES. Broker-owned: a broker request may not set it |
| CODEX_WRITE | optional | text | a Codex delegate matches a Claude subagent by default: tools on and write access to `--cwd` whenever PERMISSION_MODE allows edits (`acceptEdits`, the default, or `bypassPermissions`); read-only under `plan` or `default`. `no` opts out, `yes` forces it on. Built-in `image_gen` saves under `~/.codex/generated_images` (readable); the delegate copies the file into cwd. Writes outside `--cwd` are refused (D49): to edit another repository, dispatch with `--cwd <that repo>`. Claude delegates ignore it |
| CODEX_NETWORK | optional | text | `yes` gives a Codex delegate's tool commands outbound network access (for example DOI lookups). Off by default. Needs CODEX_WRITE on; ignored otherwise. Claude delegates ignore it |
| EXECUTIVE | optional | text | model alias or role word for the top seat of the REPORTING CHAIN line; precedence: explicit slot, then setting `chain.executive`, then the executive-rung alias of the delegate's vendor (equal to SUPERVISOR when that alias is the delegate or the supervisor) |
| SUPERVISOR | optional | text | seat the delegate reports to; precedence: explicit slot, then setting `chain.supervisor`, then the alias one rung above the delegate on the grunt, workhorse, orchestrator, executive ladder for the same vendor, else `operator` for an executive delegate (fable, astra) and `CoS` for an unknown model |
| DELEGATE | optional | text | the delegate's alias; precedence: explicit slot, then the `--model` flag, then the `MODEL` slot, then the first model alias named in `ROLE`, else the word `delegate` |
| NOTES | optional | text | default `none`; a path must sit under the dispatch scratchpad, never the repo or home |
| STYLE | optional | text | empty by default; see below |

The REPORTING CHAIN line is rendered from the three optional slots and always has the fixed form shown in the template. The settings file is `~/.config/agents-inc/settings.json`, key `chain` (`supervisor`, `executive`); set it with `agents-inc models chain supervisor=opus executive=fable`, never by hand. The renderer prints one `chain:` line on stderr that shows what it derived. `check_dispatch_prompt.py` fails a chain whose seat ranks above the seat it reports to.

D51 broker: a Lead sends these slots inline as `slots` in `<run-dir>/inbox/<id>.request.json`
(write `.tmp`, then rename; keys schema_version, request_id, model, effort, tier, slots; never PERMISSION_MODE, BASH_ALLOW or credential paths; GATES, if sent, is a JSON string).
The direct path (`agents-inc dispatch --slots`) and the broker apply one request text screen; a refusal names the slot and the matched text.
It waits with `agents-inc dispatch --wait <run-dir> <id> [--timeout 600]` (1 s polls; exit 124 on timeout), reads `<run-dir>/<id>.report.md`; `inbox/lead.done` stops the broker.
MCP transport (primary): `agents-inc run --model terra --lead <run-dir>` (astra, sol, terra only; CoS writes run.json first) gives the Lead tools `dispatch(model, effort, slots)`, `status()`, `wait(request_id, timeout)`, `resume(request_id, message)`, `answer(request_id, question_n, text)`: same slots rules, no inbox, no `tier`.
The file inbox above is the fallback; it takes `{"kind": "resume", "request_id", "message"}` as `<id>-r<n>.request.json` and `{"kind": "answer", "request_id", "question_n", "text"}` (D54).
A `needs-lead` result (MCP) or exit 10 from `--wait` carries a Worker question: answer it, then wait again.
Tool names are `mcp__agents_inc__dispatch`, `__status`, `__wait`, `__resume`, `__answer` and must be loaded with `tool_search` first (query `agents_inc`).
Without `--run-dir`, runs land in `<cwd>/.scratch/agents-inc-runs` when git ignores `.scratch`, so a delegate under acceptEdits can write its own run files.
A Lead that answers "tool_search is unavailable" or "cannot access" without calling dispatch hit a Codex-side startup flake: rerun it once.
A Worker report must be plain text, never wrapped in a code fence: handoff-lint skips fenced text, so the broker marks the result red (`report-noncompliant`).

Tool grants and outcomes (D58). A Claude delegate gets per-run `--allowedTools` and `--disallowedTools`. Allowed: Read, Glob, Grep, read-only git, the snapshot verifier, each GATES command, each BASH_ALLOW prefix, and the test runners only when FILES_IN_SCOPE names paths. Denied: `git push`, `git commit`, `sudo`, WebFetch, WebSearch, Agent, Task. `agents-inc` is never granted as Bash. A Claude Lead (fable, opus, sonnet; FAN_OUT total and depth above 0, ALLOWLIST names rung-allowed models, PERMISSION_MODE not `bypassPermissions`) also gets exactly five grants, `mcp__agents_inc__dispatch`, `status`, `wait`, `resume` and `answer`, served by the broker over `--mcp-config` (D60); Read and Edit on the broker run directory are denied. A Worker's grants must be a subset of its Lead's, or the run ends `refused-grants`; a Worker's FAN_OUT must be `width 0, total 0, depth 0` (`worker-cannot-lead`). Outcome `green`: the usual checks pass and every GATES command exits as expected. Outcome `red`: a usual check fails, or `gate-failed` (wrong exit code) or `gate-missing` (a gate could not run: missing binary, timeout, refused). Outcome `unverified` (exit 0): the checks pass but there are no GATES, so nothing checked the work. Dispatch never runs FAILURE GATE or SUCCESS GATE text. Gates re-run on every resume turn and also apply to Codex runs. Broker children skip GATES and end `unverified` with reason `gates-skipped-broker`. Red reasons and exits (D64): a red run names its cause in `reason` (`quota-paused`, `blocked`, `timeout`, `rc-nonzero`, `launch-failed`, `snapshot-tampered`, `snapshot-error`, plus the gate reasons) and the status line adds `detail=`. `agents-inc dispatch` exits 0 green or unverified, 1 red, 2 usage, 3 refused, 69 blocked, 75 quota; the broker reports 69 and 75 as red. Every dispatched turn (Claude and Codex) has a deadline, `AGENTS_INC_TURN_TIMEOUT_S` (default 3600, `0` none).

## STYLE slot (experimental, #4)

Opt-in, for extractive and summarization dispatches only. It is not
re-tested in this change. Caveman wins on conflict (operator ruling
2026-10-01): the #4 "Revised template" asked for arrows and abbreviations,
which caveman bans, so the value below drops both:

```text
HARD CONSTRAINT: Default to fragments and labels, NOT normal prose. Follow caveman rules: no arrows, no invented abbreviations; standard acronyms only.
A full grammatical sentence is allowed ONLY where a fragment would lose real precision
(negation scope, conditional/causal clause, operator precedence). Outside those cases,
one complete sentence = you failed the task, rewrite it. When you do use a full sentence,
it should be rare and load-bearing, not a lapse back into prose by default.
```
