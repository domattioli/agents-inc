<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-04 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: Worker-Lead Socket Channel

**Branch**: `development` (no feature branch) | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: `.scratch/sock/spec/spec.md`, with the clarify answers of 2026-10-04 (1A 2A 3B 4A 5A 6A 7B). Research: [research.md](research.md). Final home: DomI `specs/consumers/agents_Inc/017-worker-lead-socket/`.

## Start gate

D54 is on `development` at commit `1fcfd76`. PR 52 (`development` to `main`) is open. Implementation starts only after PR 52 merges (CoS ruling, 2026-10-04). The line citations below were re-checked against `1fcfd76` on 2026-10-04; one drift was fixed (the Codex launch is `dispatch.py:299-312`). At T001 the implementer re-checks them against the PR 52 merge commit. Any drift goes back to the Lead before code is written.

## Summary

1. The Worker's channel server (`worker_mcp.py`) listens on `ask/lead.sock`, bound by a relative name. The broker connects with a per-turn token. Socket frames are doorbells (`{op, rid, n}`). Message bodies stay in the D54 files, which remain the record of truth.
2. With a healthy socket, `ask_lead` waits on a doorbell instead of a 2 s poll, and the broker's `_await` waits on an event instead of a 0.2 s poll. On the first socket error, both sides use files for the rest of the turn.
3. A push: the broker screens it, caps it (2 for a Grunt Worker, 5 above), writes it as a file and rings the doorbell. The Worker gets it from the new `check_lead` tool, or attached to an `ask_lead` result. Sources: the `push` MCP tool and `kind: push` in the file inbox (tag `lead`), and `agents-inc tell` through a broker control socket (tag `cos` or `operator`).
4. The broker appends metadata-only lines to `<child>/events.jsonl`, in the format shared with issue 51.

## Technical Context

**Language/Version**: Python 3.10+ standard library (AGENTS.md); `worker_mcp.py` stays self-contained, because the broker copies it into the child run dir
**Primary Dependencies**: none new
**Storage**: D54 files (unchanged names), plus `<rid>.push.<n>.json` and the `.seen` markers, `<child>/worker_mcp.token` (mode 0600, rewritten each turn), `<child>/events.jsonl`, `<run-dir>/broker.sock`, `<run-dir>/tell/`
**Testing**: `python3 -m unittest discover -s tests -p 'test_*.py'`; temp dirs and a fake HOME; stand-in Worker and broker processes; no real model calls, except the opt-in live tests that already exist for D54
**Target Platform**: macOS (`sandbox-exec`); Linux runs the unit tests only
**Constraints**: socket address limit of 104 bytes on macOS; no TCP; never log a token, an environment value or a message body; `worker_mcp.py` must not import `agents_inc`
**Scale/Scope**: five install modules edited, no new module, two new test modules, four test modules extended

## Existing code (evidence; re-checked against `1fcfd76`, 2026-10-04)

- `worker_mcp.py:24-25` `WAIT_SEC 1800`, `POLL_SEC 2.0`; `:28-34` one tool; `:84-98` `Channel.ask` polls; `:139-157` single-threaded stdio `serve`; `:160-169` `main` takes `--run-dir`, `--request-id`.
- `dispatch.py:200-228` `claude_sandbox_profile` (`(allow default)`, write denies, `write_ok` for `ask/`, `read_ok` for the script and config); `:242-248` `ASK_DIR`, `ASK_TOOL`, `ASK_LEAD_NOTE`; `:251-265` `_ask_channel`; `:272-288` the Claude launch adds `--allowedTools ASK_TOOL` and the sandbox; `:299-312` the Codex launch passes `worker=(ask, rid, script)` to `run_codex` (`:310-312`).
- `dispatch.py:840-856` file inbox `kind: answer`, handled before the busy check; `:935-938` `RESUME_KEYS`, `ANSWER_KEYS`, `QUESTION_MAX_BYTES`; `:941-943` `resume_cap`; `:946-977` `Turn`; `:1006-1012` `screen_text`; `:1015-1044` `relay_question`; `:1062-1087` `answer_question`; `:1163-1178` `init_broker_state` (counters `resumes`, `questions`); `:1181` file `serve`.
- `mcp_broker.py:27-48` TOOLS; `:49` `AWAIT_MAX_SEC 3500`; `:73` poll 0.2; `:94-115` `_await`; `:127-150` `tool_dispatch` blocks; `:184-192` `tool_answer`; `:248-249` handler table; `:261-287` `serve` loop, sequential.
- `runtime.py:172-176` `worker_args(channel_dir, request_id, server)`; `:286-287` appended to the Codex argv.
- `cli.py:130` `dispatch` subparser; `:133-136` the other subcommands. There is no `tell`.

## Design decisions

- **DD1 channel socket in `worker_mcp.py`** (FR-002, FR-003, FR-006, FR-007; R5, R10, R13). New `--token-file` argument (optional; when absent, the turn is file-only and records `no-token`). At start, the server reads the token, then checks for a stale `ask/lead.sock`. A connect that fails with ENOENT or ECONNREFUSED means the file is stale, so the server unlinks it. A live listener means the server goes to file mode. The server binds `lead.sock` after `os.chdir(ask)`, changes back, sets mode 0600 and listens with backlog 1. All of this happens before stdin serving begins. An accept thread takes connections. A peer with another uid is closed. The first frame must be `{"op":"hello","token":<t>}` within 5 s, else the connection is closed. The first good peer becomes the link, and later peers are refused. A reader thread puts `answer`, `push` and `bye` frames into a `queue.Queue`. Frames are newline-delimited JSON, at most 4 KiB, with the fields `op`, `rid` and `n` only. A bind error, a missing token, or any later socket error sets `self.mode = "file"` for the rest of the process, and the reason goes to `ask/<rid>.transport.json`.
- **DD2 `ask_lead` on the doorbell** (FR-003, FR-005, SC-001, SC-004). `Channel.ask` writes the question file as today, then sends `{"op":"ask","rid","n"}`. In socket mode it waits on the queue until the deadline. On an `answer` frame for `n` it reads the answer file once. On a socket error it switches to file mode and resumes the 2 s poll with the same deadline. In file mode the behaviour is unchanged. The 30-minute limit and the `NO_ANSWER` text are unchanged.
- **DD3 `check_lead` and push delivery** (FR-002, FR-009; R2, R9). TOOLS gains `check_lead` (no arguments, `readOnlyHint`). It scans `ask/<rid>.push.<n>.json` for `n = 1..` until the first missing number, and returns every push not yet carried, as `[push <n> from <source>] <text>` blocks. If there is none, it returns `no message from your Lead`. For each push it carries, it writes `ask/<rid>.push.<n>.seen` (O_EXCL) and sends `{"op":"seen","rid","n"}` when the link is up. `ask_lead` adds the same block after the answer text. The server stays standard library only and never imports `agents_inc`.
- **DD4 broker link** (FR-003, FR-005, FR-007; R5, R6, R11). New `WorkerLink` class in `dispatch.py`. `_ask_channel` writes the token with `secrets.token_hex(16)` into `<child>/worker_mcp.token` (O_EXCL into a temp file, then rename, mode 0600) and adds `--token-file` to the server args. The Claude sandbox gets the token file in `read_ok`. `runtime.worker_args` gains `token_file`. The link starts when the `Turn` starts. It waits for `ask/lead.sock` to appear, checking every 0.1 s for at most 30 s (startup only). It connects through the full path when that path is 100 bytes or less, else through a symlink in `tempfile.mkdtemp()` with mode 0700, removed after connect. The broker never changes directory. It sends `hello`. A reader thread sets `link.event` on `ask` and counts `seen`. `relay_question` is unchanged. `answer_question` and `push_message` ring `answer` and `push` after their files are written. Any error sets `link.mode = "file"`, records the reason and closes the link. `Turn` records `{"transport": "socket"|"file", "fallback_reason": str|None}` in the request result.
- **DD5 broker waits on the event** (FR-003, SC-001). `mcp_broker.Broker._await` waits on `turn.link.event.wait(self.poll)` instead of `time.sleep(self.poll)`, and clears the event after each relay check. In file mode the event never fires, so the 0.2 s poll stays. The file broker's `--wait` path is unchanged.
- **DD6 push** (FR-008, FR-012, FR-016; R1). New `push_message(run_dir, spec, rid, text, source, known, running_rid)` in `dispatch.py`, which returns `(fields, reason)`. Refusals: `bad-request-id`, `bad-source` (the source must be one of `cos`, `lead`, `operator`), `bad-message` (empty), `oversize` (over 64 KiB), `credential-seeking`, `unknown-request` (`known(rid)` is false), `turn-ended` (`rid != running_rid` or `<rid>.result.json` exists), `push-cap` (`push_cap(model)`: 2 for a Grunt Worker, 5 above, counted per rid from the run-dir records). On success, under `_SPEC_LOCK`, it writes `<run-dir>/<rid>.push.<n>.json` `{request_id, push_n, source, bytes, pushed_at}` (no body), then `<child>/ask/<rid>.push.<n>.json` `{push, source, pushed_at}`. It appends the event line and rings the doorbell. `spec["pushes"]` holds `{"sent": {src: n}, "refused": {src: n}, "delivered": n}`, per request id; `delivered` is one total, not split by source (the simpler reading, FR-012), comes from the `.seen` markers at turn end and is advisory (R16). `init_broker_state` adds `pushes`. Pushes never touch `workers_spawned`, `resumes` or `request_counts`.
- **DD7 Lead push paths** (FR-008, FR-016). `mcp_broker.py` TOOLS gains `push {request_id, text}` (source `lead`). It is handled at once, never while a Worker call blocks, because the stdio loop is sequential. `dispatch` gains an optional `timeout`, as `resume` has. On timeout it returns `{"status":"timeout","request_id"}`, and the Lead then calls `push` or `wait`. The tool descriptions say this. File inbox: `PUSH_KEYS = {kind, request_id, text}`, handled beside `kind: answer`, before the busy check (`dispatch.py:842`).
- **DD8 `agents-inc tell`** (FR-010, SC-009; R3, R12). `cli.py` adds `tell RUN_DIR REQUEST_ID --source {cos,operator}`. The text comes from stdin, at most 64 KiB, and is never taken from argv. New `ControlServer` in `dispatch.py`, started by `Broker.ensure()` and by the file `serve`. It binds `<run-dir>/broker.sock` by the R5 rule, mode 0600, and only peers of the same uid are accepted. It runs in its own thread: one frame in, `{"op":"tell","rid","source","text"}`, then `push_message(...)`, then one reply frame. The CLI connects by the R5 rule. If the CLI cannot connect, it writes `<run-dir>/tell/<rand>.json` atomically, and the server thread scans `tell/` every 1 s only while its socket is down. Exit codes: 0 pushed, 3 refused (the reason goes to stderr), 2 usage error. The CLI never prints the text.
- **DD9 events.jsonl** (FR-011, SC-008; R7). New `append_event(child, rid, dir, kind, n, nbytes)` in `dispatch.py`. `nbytes` is the UTF-8 length of the screened text (FR-011): the relayed copy for `ask`, the Worker-side text for `answer` and `push`. It opens `O_WRONLY|O_APPEND|O_CREAT|O_NOFOLLOW` with mode 0644 and does one `os.write` of `json.dumps({...}, separators=(",", ":")) + "\n"`. `ts` uses `_now()`. Calls: in `relay_question` when it first copies a question (`to-lead`, `ask`), in `answer_question` (`to-worker`, `answer`), and in `push_message` (`to-worker`, `push`). Errors are ignored, because the log never blocks a message.
- **DD10 prompt note** (FR-009, FR-015). `ASK_LEAD_NOTE` names both tools and says: "call `check_lead` between major steps; the Lead, the CoS or the operator may send you notes; each shows its source". `--allowedTools` gains `mcp__agents_inc__check_lead`. The prompt text is a LESSON-CANDIDATE; the Lead writes it, not a delegate.
- **DD11 live proofs** (SC-007; R5, R12, R14, R15). These extend the opt-in live tests. A Claude Worker under `sandbox-exec` binds `ask/lead.sock`, answers a question over the socket, and calls `check_lead`. A Codex Worker does the same. A probe shows whether a file-inbox Codex Lead can connect to `broker.sock` (the R12 gap). A probe confirms `connect()` through a symlink. Any failed proof gives a recorded fallback, not a code change in this feature. SC-007 pass rule: for each vendor, the Worker report holds the push nonce and `ask/<rid>.push.1.seen` exists; Claude must record `socket`; Codex may record `file` only with a non-empty `fallback_reason`.
- **DD12 ownership** (`coding-dispatch` policy; operator ruling 2026-10-04: opus Lead over sonnet Workhorse). The Lead writes the acceptance tests first (each story's test tasks) and shows them failing on unchanged code. A sonnet Workhorse writes all code, DD1 to DD9, in `agents_inc/install/*`, and any further unit tests: these are threads, sockets and a trust boundary, which need design judgment. The Lead reviews every Workhorse diff. DD10 text is written by the Lead. The operator ruling replaces the earlier Executive-owned assumption for this feature. A reviewer from a different vendor also reviews the trust-boundary diff (D46 item 10(b)).

## Constitution Check

Constitution at DomI `specs/consumers/agents_Inc/memory/constitution.md` was unratified at 016 [assumed unchanged; not read, it is outside this repo], so violations are WARN.

| Principle | Status | Note |
|---|---|---|
| P0 cross-reference, never duplicate | PASS | Bodies stay in the D54 files; the socket carries only doorbells; the broker reuses `worker_mcp` helpers by import. |
| P1 repo-scoped writes | PASS | Runtime writes stay in run dirs; tests use temp dirs and a fake HOME. |
| P2 labor ladder | PASS | Workhorse for socket and threading code and unit tests; Lead for acceptance tests, review and prompt text (DD12). |
| P4 deterministic policy over prompt | PASS | Screen, cap, peer check and token are code. Only the "call `check_lead`" habit is prompt-level, by design (Q2 A). |
| P5 hard $0 per task | PASS | No model calls, except the opt-in live proofs on the subscription. |

Post-design re-check: PASS.

## Project Structure

```text
.scratch/sock/spec/ (later DomI specs/consumers/agents_Inc/017-worker-lead-socket/)
├── spec.md, plan.md, research.md, clarify-questions.md
├── tasks.md                     # Workhorse, from worker_slots.json
└── checklists/requirements.md   # Workhorse
agents_inc/install/worker_mcp.py   # DD1-DD3: socket, token, doorbell, check_lead
agents_inc/install/dispatch.py     # DD4, DD6, DD7 (file inbox), DD8 ControlServer, DD9, DD10
agents_inc/install/mcp_broker.py   # DD5 event wait, DD7 push tool and dispatch timeout, DD8 start
agents_inc/install/runtime.py      # DD4 worker_args token_file
agents_inc/install/cli.py          # DD8 tell subcommand
tests/test_worker_sock.py          # new: bind, stale, long path, token, peer, doorbell, faults (SC-001..005)
tests/test_dispatch_push.py        # new: push screen/cap, inbox kind push, tell, events.jsonl (SC-008, SC-009)
tests/test_worker_mcp.py           # extend: two tools, check_lead, push attached to ask_lead; update only the three exact-list assertions SC-006 names (:48, :293, :354 at 1fcfd76)
tests/test_mcp_broker.py           # extend: push tool, dispatch timeout, event wait
tests/test_codex_tool_access.py    # extend: worker_args carries --token-file
tests/test_worker_mcp_live.py, tests/test_mcp_broker_live.py   # extend: DD11 proofs (opt-in)
tests/test_dispatch_resume.py, tests/test_dispatch_broker.py   # unchanged; must pass (SC-006)
```

Canon edits are LESSON-CANDIDATE only (FR-015). They are not part of the implementation: a new `docs/DECISIONS.md` entry that amends D54 (push, cap, `check_lead`, `tell`, source tags, `events.jsonl` format); the `CONTEXT.md` rows in "Agent context update" below; `skills/workerbee/SKILL.md` and `QUICKREF.md` lines on `tell` and `push`.

## Agent context update

No `CLAUDE.md` (retired 2026-10-01). The agent context for this repo is `CONTEXT.md`. This plan does not edit it. The implementation must add these rows, as LESSON-CANDIDATE items signed off before merge (FR-015, T045):

- New **Push**: a note from the Lead, the CoS or the operator, sent through the broker, screened like an answer, capped per turn (2 Grunt, 5 Workhorse and above), carrying a source tag, and delivered by `check_lead` or attached to an `ask_lead` result.
- New **Channel**: a Worker's `ask/` dir plus its channel server (`worker_mcp.py`), which gives the Worker `ask_lead` and `check_lead` and owns the turn's socket `ask/lead.sock`.
- New **Doorbell**: a socket notice `{op, rid, n}` that says a D54 file is ready; it never carries a message body, and the D54 files stay the record of truth.
- Amended **Turn** (`CONTEXT.md:36`): drop "No message reaches a delegate during a turn (D54)"; a Push now may.
- Amended **Dispatch broker** (`CONTEXT.md:66`): its tools list gains `resume`, `answer` (D54) and `push` (017).

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| Threads in `worker_mcp.py` | The stdio loop blocks on stdin and in `ask`, so it cannot accept a connection | Polling for a connection is the polling this feature removes |
| Broker control socket plus the `tell/` drop dir | `tell` must reach the broker while a Lead call blocks (FR-016) | Routing through the Lead's stdio breaks FR-016; a drop dir alone means polling |
| Symlink connect for long paths | The broker is multi-threaded and must not change directory | A short shared dir such as `/private/tmp` is shared with other tools (Q5 B rejected) |
