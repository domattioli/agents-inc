# Clarify questions: 017-worker-lead-socket

For the CoS (clarify gate). Each question maps to one open item in `spec.md`. The recommended option is first and marked (recommended). Answer by number and letter, for example "1A, 2A, 3B".

1. **May the Lead push a message into a running Worker? (FR-008; amends D54)** D54 says the Lead cannot, and the Worker prompt says so too. A socket makes push possible, but only a new ruling makes it allowed.
   - A (recommended): Yes, as a new decision that amends D54. A push passes the answer screen (credential check, 64 KiB), lands as a file, and is capped per turn: 2 for a Grunt Worker, 5 for Workhorse and above. Pushes count in `run.json` but never as Workers or resumes.
   - B: Yes, with the screen but no cap.
   - C: No. Keep the D54 limit. The socket only speeds up ask and answer (Stories 1 and 2). Story 3 is dropped.

2. **How does a push reach the Worker model during its turn? (FR-009)** The socket reaches the channel server, not the model. The model sees new text only in a tool result or in injected context.
   - A (recommended): Add a second Worker tool, `check_lead`, which returns pending pushes at once. The channel server also attaches pending pushes to every `ask_lead` result. The Worker prompt tells the Worker to call `check_lead` between major steps. This works the same for Claude and Codex, but delivery depends on the Worker calling a tool.
   - B: A as the baseline, plus a Claude-only hook that injects pending pushes after each Claude tool call. This gives truer push for Claude, but it adds hook wiring inside the Worker sandbox and splits behaviour by vendor.
   - C: Interrupt and resume. The broker stops the turn and resumes it with the push as the message. This needs no Worker cooperation, but work in progress is lost and each push costs one resume.
   - D: No delivery to the model in this feature. The socket carries ask and answer only (same effect as 1C).

3. **May a native Claude Code session (the CoS or another operator session) message a delegate? (FR-010)** Direct access bypasses the D46 chain (Worker asks Lead, Lead asks CoS) and the D51 screen. The native socket protocol is undocumented.
   - A (recommended): Not in this feature. The channel server refuses every peer except the broker. The CoS reaches a Worker only through its Lead, as D46 item 11 requires. Revisit after 1 and 2 have run in practice.
   - B: Through the broker only. A new `agents-inc tell <run-dir> <request-id>` command hands the text to the broker. The broker screens it, counts it, and sends it as a push tagged with its source. This needs 1A or 1B.
   - C: Speak the native `/tmp/cc-socks` protocol so that a native SendMessage reaches the delegate. This is not recommended: the protocol is undocumented, it can change with any Claude Code release, and it skips the broker screen.

4. **How does the channel server check that its peer is the broker? (FR-007)** Any process of the same user that can reach the socket file can connect. Sandboxed agents cannot reach the file. Unsandboxed operator sessions can.
   - A (recommended): Same-user peer check, plus a per-turn token. The broker writes the token to a mode-0600 file in the child run dir, and the server requires it as the first line of the connection. The token never goes in argv, a prompt, or a log. Limit, stated plainly: an unsandboxed process of the same user can read the token file. The check therefore stops sandboxed agents and accidental connections, not the operator's own tools.
   - B: Same-user peer check only, plus mode 0700 on the socket's directory.
   - C: File mode only, with no peer check.

5. **Where does the socket file live? (FR-006)** macOS limits a socket address to 104 bytes, and a channel dir under a repository path can come close to that limit. The Claude Worker sandbox allows writes only in a short list of places.
   - A (recommended): In the Worker's `ask/` dir, bound by a short relative name from inside that dir, so that the length of the full path does not matter. If the bind still fails, use files (FR-005). The ask dir is already writable by the Worker and readable by the broker.
   - B: Under `/private/tmp/claude-<uid>/agents-inc/<short-hash>.sock`, which the Claude Worker sandbox already allows. This is not proven for Codex Workers, and the directory is shared by every Claude Bash tool.
   - C: In the Worker's per-turn TMPDIR. The path is long too, and it is lost when TMPDIR is reset.

6. **When the socket fails, how far does the fallback reach? (FR-005)**
   - A (recommended): For the rest of the turn. After the first failure, the channel server and the broker both use files until the turn ends, and the result records the reason. This is simple and avoids two transports racing on one message.
   - B: Per message. Try the socket for each message, and use files for any message that fails.
   - C: Try to reconnect up to 3 times with a short delay, then use files for the rest of the turn.

7. **What is the link to issue 51 (the tee of child stdout to `events.jsonl`)? (FR-011)** Issue 51 could not be read: this dispatch allows no network, and the repository has no reference to it.
   - A (recommended): None in this feature. The D54 files remain the only record. A shared `events.jsonl` waits for an issue 51 spec, and that spec decides the format for both.
   - B: Write each socket message also as one line in `<child>/events.jsonl`, in a format that issue 51 then adopts.
   - C: Ship issue 51 first and build this feature on its event stream.
