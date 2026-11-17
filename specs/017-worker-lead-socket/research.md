<!-- provenance: author=domattioli model=claude-opus-5-5 effort=high date=2026-10-04 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Research: Worker-Lead Socket Channel (017)

Phase 0 for [plan.md](plan.md). One entry per clarify answer (R1 to R7), then the technical unknowns settled from the code (R8 to R16). Line citations are against the working tree of 2026-10-04, which carries uncommitted D54 work. Re-check them after the D54 PR merges.

## Clarify answers

**R1. The Lead may push (Q1 A).**
- Decision: a new decision amends D54. A push passes the answer screen (`_reject_credential_seeking` and the 64 KiB `REQUEST_MAX_BYTES`, `dispatch.py:575`, `:1068-1071`). The cap is 2 per turn for a Grunt Worker and 5 above, shared by all sources.
- Rationale: the Lead often learns mid-turn that a premise is wrong, and today it can only wait or resume. A cap per rung mirrors `resume_cap` (`dispatch.py:941-943`).
- Alternatives: no cap (B) lets a Lead flood a Worker; keeping the limit (C) leaves the operator request unmet.

**R2. Delivery by the Worker's own tool calls (Q2 A).**
- Decision: a second tool, `check_lead`, returns pending pushes at once. `ask_lead` results also carry them. The prompt note asks the Worker to call `check_lead` between major steps.
- Rationale: an MCP stdio server can only answer tool calls, and both vendors start `worker_mcp.py` the same way (`dispatch.py:263-264`, `runtime.py:172-176`). One rule covers both vendors.
- Alternatives: a Claude-only hook (B) splits behaviour by vendor and adds hook wiring inside the sandbox. Interrupt and resume (C) loses work and spends resumes. No delivery (D) is the same as Q1 C.
- Consequence: delivery depends on the Worker calling a tool. The result records pushes that were sent but never carried (spec edge cases).

**R3. Other sessions go through the broker only (Q3 B).**
- Decision: `agents-inc tell <run-dir> <request-id> --source cos|operator` hands the note to the broker. The broker screens it, counts it under the R1 cap, and sends it as a push. Lead pushes use the broker `push` tool and get the tag `lead`. The CLI does not offer `lead` [assumed: this keeps the `lead` tag tied to the Lead's own transport].
- Rationale: the operator asked twice on 2026-10-04. The broker path keeps the D51 screen and the D46 chain.
- Alternatives: refusing all other sessions (A) ignores the operator request. The native `/tmp/cc-socks` protocol (C) is undocumented and skips the screen.
- Limit: the tag is declared by the caller. Any process of the same user can run the CLI with either tag.

**R4. Peer check: same user plus a turn token (Q4 A).**
- Decision: the server refuses a peer of another uid, and a peer whose first frame lacks the token. The broker writes a fresh token for each turn to `<child>/worker_mcp.token` with mode 0600. It passes only the file path to the server (`--token-file`). The Claude sandbox gets the file as read-only, like the script and config (`dispatch.py:206`, `:287`).
- Rationale: sandboxed agents cannot reach the socket path. The token stops accidental and non-broker connections.
- Limit: an unsandboxed process of the same user can read the token file.

**R5. Socket in `ask/`, bound by a relative name (Q5 A).**
- Decision: the server binds the name `lead.sock` after changing into `ask/`. It does this once, single-threaded, before it starts serving, and changes back afterwards. The broker is multi-threaded (`Turn`, `dispatch.py:946-977`), so it must not change directory. It connects through the full path when that path is 100 bytes or less. Otherwise it connects through a symlink in a private mode-0700 temp dir [assumed: `connect()` follows a symlink to a socket on macOS; confirm in T-proof].
- Rationale: a child path such as `<repo>/.scratch/sock/run/<run-id>/workers/<rid>/runs/<child>/ask/lead.sock` runs past 104 bytes [inferred: about 170 bytes for this run's dir].
- Alternatives: `/private/tmp/claude-<uid>` (B) is shared with every Claude Bash tool and is unproven for Codex. TMPDIR (C) is long too.

**R6. Fallback for the rest of the turn (Q6 A).**
- Decision: on the first socket error, each side sets a per-turn `file` flag and returns to the D54 polling (2 s on the Worker side, 0.2 s on the broker side). The result records `transport` and `fallback_reason`.
- Rationale: one transport per turn means no race between a doorbell and a poll for the same message.
- Alternatives: per-message retry (B) and reconnect with N tries (C) add state for little gain.

**R7. Shared metadata-only `events.jsonl` (Q7 B).**
- Decision: the broker appends to `<child>/events.jsonl`. A line is `{"ts", "rid", "dir", "kind", "n", "bytes"}`, nothing else. `kind` is `ask`, `answer` or `push`; `event` is reserved for the issue 51 tee.
- Rationale: the operator's tmux viewer (`agents-inc cuck`) tails one file per Worker. Byte counts only, so the file is safe to tail and to share.
- Write rule: open with `O_APPEND`, one `os.write` per line. Lines stay under 512 bytes, so lines from the broker and the tee do not mix [inferred: POSIX append on a local file].
- The Worker cannot write the child run dir, only `ask/`, so it cannot forge lines (`dispatch.py:218-220`).

## Technical unknowns settled from the code

**R8. The socket is a doorbell; bodies stay in files.**
- Every body is already written and screened through files: `relay_question` (`dispatch.py:1015-1044`) and `answer_question` (`:1062-1087`). Socket frames carry only `{op, rid, n}`. Byte-for-byte file parity (SC-003) then holds by construction, and the D54 screen stays the one code path (FR-004).

**R9. Push delivery needs no polling, even in file mode.**
- `check_lead` reads the push files when the Worker calls it. The socket only speeds up `ask_lead`, and it gives the broker a "delivered" doorbell.

**R10. The Worker server needs a thread.**
- `worker_mcp.serve` blocks on stdin (`worker_mcp.py:139-157`), and `ask` blocks the same thread (`:84-98`). An accept and reader thread feeds a queue. `ask` waits on that queue instead of `sleep(POLL_SEC)`.

**R11. The broker's stdio loop handles one Lead call at a time.**
- See `mcp_broker.py:264-283`; `dispatch` blocks up to `AWAIT_MAX_SEC` (`:49`, `:150`). The `dispatch` tool therefore gains an optional `timeout`, as `resume` and `wait` have. A `tell` arrives on a broker control socket served by its own thread, so a blocking Lead call never holds it off (FR-016).

**R12. Broker control socket.**
- `<run-dir>/broker.sock` (relative bind, same rule as R5), plus a fallback drop dir `<run-dir>/tell/`. The listener thread scans that dir every 1 s, only while the socket is down.
- MCP Lead: no read or write on the run dir (D51, `DECISIONS.md:573`).
- File-inbox Lead: it can read the run dir but writes only `inbox/` (D51). Whether Codex's seatbelt lets it connect to a Unix socket there is unknown [assumed blocked; live probe in T-proof]. If it can connect, it can send a `tell` tagged `cos`. Recorded as a known gap.

**R13. Peer uid with the standard library.**
- Linux: `SO_PEERCRED`. macOS: `getsockopt(0, LOCAL_PEERCRED=1)` returns `struct xucred`; the uid is the second 32-bit field [assumed; confirm at implement time]. If neither is available, use the 0700 dir mode plus the token, and record `peer_check: token-only`.

**R14. Codex MCP children and the sandbox.**
- Codex Workers get the server through `-c mcp_servers.agents_inc.*` (`runtime.py:172-176`, `:286-287`) and the run-dir deny (`dispatch.py:311`). Whether Codex runs MCP servers inside its seatbelt is unknown. D54's live test shows they can write `ask/` [inferred from `tests/test_worker_mcp_live.py` existing; not run this turn]. A bind in `ask/` is expected to work; T-proof confirms it.

**R15. Claude sandbox and socket calls.**
- The profile is `(allow default)` with file-write denies (`dispatch.py:222-228`). There is no network rule, so bind and connect are allowed, and `ask/` is writable [inferred]. T-proof confirms it.

**R16. Existing forge path, not widened.**
- The Worker can write its own `ask/` dir (`dispatch.py:206`, `:287`). It could therefore write an answer or push file to itself. The socket adds no path to the Lead: questions still pass `relay_question`'s screen. The delivered counts come from Worker-side markers, so they are advisory.
