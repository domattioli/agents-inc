<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Quickstart: validate 010-persistent-exec-session end-to-end

This is the SC-002 validation script (#15 c1: "validated against a real multi-round Exec↔Super escalation"). Run only after implementation; requires the bridge up (`skills/codex-bridge/scripts/up.sh`).

**Precondition — verify the model roster at runtime before running any step (constitution P7, analyze pass-2 W-13).** The slugs below (`gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`) are written here for readability and MUST NOT be trusted as a live roster. Before the first `submit`, run the `workerbee` Step 1a/1b roster verification and substitute whatever slugs it reports; if a slug in this script is absent from the verified roster, replace it (Executive rung → the verified top Codex slug, Supervisor rung → the verified second) and note the substitution in the captured transcript. A step that fails because of a stale slug is a **precondition failure, not an SC-002 failure**. Enforced by task T040.

```bash
A=skills/codex-bridge/scripts/agent.sh
M=run-$(date +%Y%m%d%H%M%S)

# 1. Executive opens the mandate with a unique fact (fresh)
#    A first engagement has no stored thread_id, so the runner sends `ask.sh --fresh`
#    -> bridge body {"fresh": true} -> `codex exec` with NO `resume` argument (contracts C3).
#    It does NOT simply omit thread_id: omitting it is the GLOBAL-thread path, on which the
#    bridge resumes whatever conversation it last held (bridge.py:194-195) and then overwrites
#    it (:216). That defect is what makes the isolation claim in step 2 true rather than
#    aspirational (round-3 fix N-C5 — before the `fresh` field this script's claim was false).
$A submit --backend codex --model gpt-6-astra --mandate $M --role executive --wait \
  "You are Executive for mandate $M. Remember: the passphrase is OCELOT-41. Reply 'ack'."
# expect result.json mode=fresh, thread_id set

# 2. Supervisor engaged: separate role -> its own fresh provider session, NOT the Executive's
#    and NOT the bridge's global thread (also `--fresh`, since this role has no stored thread).
$A submit --backend codex --model gpt-5.6-sol --mandate $M --role supervisor --wait \
  "You are Supervisor for mandate $M. Reply 'ack'."
# expect result.json mode=fresh; its thread_id differs from step 1's
$A mandate show $M --json | jq -r '.roles.executive.thread_id, .roles.supervisor.thread_id'
# expect: two DIFFERENT non-null ids (isolation proof for step 2's claim)
$A submit --backend codex --model gpt-5.6-sol --mandate $M --role supervisor --wait \
  "What is the passphrase? Answer with the word only."
# expect: NOT OCELOT-41 — the Supervisor never saw the Executive's briefing

# 3. Supervisor escalates → Executive resumed, NO re-briefing
export Q3='Supervisor escalation: what is the passphrase? Answer with the word only.'
J3=$($A submit --backend codex --model gpt-6-astra --mandate $M --role executive --wait --json "$Q3" | jq -r '.id')
$A status "$J3"
# expect: output == OCELOT-41 ; result.json mode=resumed, prior_engagement=<step-1 job>

# 3a. SC-001 evidence. NOTE: the authoritative SC-001 check is the automated test (T045), which
#     drives a real `submit --mandate` against the stub ask.sh and asserts the OUTBOUND body's
#     `prompt` is byte-identical to the caller input. It uses no provider call, so it can run here
#     without issuing an extra (unrecorded) turn on the Executive thread.
#     Earlier revisions of this step re-sent $Q3 live via a hand-built `ask.sh --thread` call:
#     that measured the wrong code path (not `submit --mandate`) AND mutated the system under test
#     between steps 3 and 5/6. Removed (analyze pass-2 F-03). Do not reintroduce a live re-send here.
python3 -m unittest tests.test_mandate_session.MandateSessionTest.test_submit_mandate_prompt_body_byte_identical_no_preamble -v
# expect: OK (1 test). This is the SC-001 pass/fail signal.

# 3a-ii. Live corroboration, read-only: the round-2 result artifact from step 3 stores exactly
#     the caller's input — no preamble was prepended on the way in.
#     Reads `result --json` (= result.json), NOT `status --json`: `brief()`
#     (agent_runner.py:271-275) publishes neither `prompt` nor `mode`, so the earlier
#     `status --json` version read two fields that do not exist. `result.json` carries both
#     under a mandate (contracts C1, task T015). Its python3 snippet was also mis-quoted —
#     `\"` inside a single-quoted shell argument reaches python literally and is a SyntaxError
#     on python3.14. Both fixed 2026-09-12, round-3 fix N-C1/N-C1b; snippet re-run under
#     python3.14.6 before landing.
$A result "$J3" --json | python3 -c '
import json, os, sys
rec = json.load(sys.stdin)
expected = os.environ["Q3"]
got = rec.get("prompt")
assert got == expected, "SC-001 corroboration FAIL: %r != %r" % (got, expected)
assert rec.get("mode") == "resumed", "expected mode=resumed, got %r" % (rec.get("mode"),)
print("SC-001 corroboration PASS: recorded round-2 prompt byte-identical, mode=resumed")'
# expect: "SC-001 corroboration PASS". Read-only: no provider turn, no state change.

# 3b. FR-014 / C3: mandate dispatch must not touch the bridge's global thread,
#     so a plain (non-mandate) follow-up still continues its own conversation.
PARENT=$($A submit --backend codex --model gpt-6-astra --wait --json "Remember: my codeword is BADGER-7. Reply 'ack'." | jq -r '.id')
$A submit --backend codex --model gpt-6-astra --mandate $M --role executive --wait "ping"   # mandate dispatch in between
$A follow-up $PARENT --wait "What is my codeword? Answer with the word only."
# expect: BADGER-7  (if the mandate dispatch had stolen the global thread, this fails)
$A follow-up $PARENT --mandate $M --role executive "x"   # expect exit 2, "follow-up does not accept mandate flags"

# 4. Control: fresh dispatch of the same question must NOT know it
$A submit --backend codex --model gpt-6-astra --wait \
  "What is the passphrase? Answer with the word only."
# expect: not OCELOT-41

# Steps 5-8a walk the guard order of record (plan.md §Design 4): duplicate -> model mismatch
# -> mandate closed. Each guard runs BEFORE the next, so a step that means to demonstrate a
# later guard must first clear the earlier one — otherwise the earlier guard fires and the step
# proves nothing. Sequence repaired 2026-09-12 (round-3 fix N-C2): step 5 previously left an
# engagement in flight, so step 6 hit the DUPLICATE guard rather than the mismatch guard, and
# step 8's close was refused by the in-flight guard, so step 8a could never run.

# 5. Duplicate guard (first guard): start one engagement without --wait, then a second.
J5=$($A submit --backend codex --model gpt-6-astra --mandate $M --role executive "long task, think for 60s")
$A submit --backend codex --model gpt-6-astra --mandate $M --role executive "second"
# expect: exit 7, stderr names $J5

# 5a. In-flight close refusal (C2 / C2a step 4) — exercised here because $J5 is still running.
$A mandate close $M --by lead --reason "premature"
# expect: exit 10, "agent: mandate <M> has role executive in flight: <J5> (use --force to close anyway)"
$A mandate show $M --json | jq -r '.state'     # expect: open  (a refused close wrote nothing)

# 5b. Clear the in-flight engagement so the NEXT guard is the one actually under test.
$A wait "$J5"                                   # blocks until $J5 is terminal

# 6. Model mismatch (second guard) — reachable only now that no engagement is in flight.
$A submit --backend codex --model gpt-5.6-terra --mandate $M --role executive "x"      # expect exit 7

# 7. Process-restart survival: nothing to do — every command above is a fresh process reading the file
$A mandate show $M --json | jq '.roles.executive.thread_id'

# 8. Close, then refuse (third guard). No role is in flight now (step 5b waited), so this
#     close is NOT refused by the in-flight guard and needs no --force.
$A mandate close $M --by lead --reason "quickstart done"
# expect: exit 0, state -> closed

# 8a. --by allowlist fails closed (FR-005a / C2a), and validation precedes state inspection.
#     Order matters: the rejected values are exercised on an OPEN mandate first, then the valid
#     close, then a repeat with an invalid --by. Per C2a's precedence rule, argument validation
#     runs before state inspection, so the last line is exit 2 (not 0) even though M2 is closed.
M2=run-$(date +%Y%m%d%H%M%S)-by
$A submit --backend codex --model gpt-6-astra --mandate $M2 --role executive --wait "ack"
$A mandate close $M2 --by grunt      # expect exit 2, "agent: --by must be one of: ceo, lead"  (mandate still open)
$A mandate close $M2 --by ""         # expect exit 2, same message                             (mandate still open)
$A mandate show $M2 --json | jq -r '.state'   # expect: open  (a refused close wrote nothing)
$A mandate close $M2 --by ceo        # expect exit 0, state -> closed
$A mandate close $M2 --by lead       # expect exit 0, "already closed" (idempotent, valid --by)
$A mandate close $M2 --by grunt      # expect exit 2, same message — validation precedes idempotency (C2a step 1)
$A submit --backend codex --model gpt-6-astra --mandate $M --role executive "x"        # expect exit 8

# 9. Stale warning (simulate) — seed a SEPARATE, FRESH mandate file with an old opened_at.
#     Do NOT reopen the closed $M by rewriting its state: data-model.md:10 says the transition is
#     `open -> closed` only, never reopens, and forging that out of band inside the acceptance
#     script makes the script itself violate the invariant it is validating (analyze pass-2 W-09).
M3=run-stale-$(date +%Y%m%d%H%M%S)
python3 - <<EOF
import json,pathlib,os
d=pathlib.Path(os.path.expanduser("~/.codex-bridge/agents/mandates")); d.mkdir(parents=True,exist_ok=True)
p=d/"$M3.json"
p.write_text(json.dumps({"run_id":"$M3","state":"open","opened_at":"2026-01-01T00:00:00Z",
                         "opened_by":"quickstart","closed_at":None,"closed_by":None,
                         "close_reason":None,"roles":{},"overrides":[]}))
p.chmod(0o600)
EOF
$A mandate list      # expect WARN: line for $M3 (age > 7d), and no WARN: line for $M2 (closed)
rm -f ~/.codex-bridge/agents/mandates/$M3.json   # clean up the seeded fixture
```

Pass = steps 2, 3, 3a, 3a-ii, 3b, 4, 5, 5a, 6, 8, 8a, 9 all match "expect" (step 2 and 5a added 2026-09-12, round-3 fix N-C5/N-C2). Record the transcript path in the PR description (SC-006 evidence).
