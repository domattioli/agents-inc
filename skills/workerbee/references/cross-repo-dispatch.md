# workerbee: cross-repo dispatch

Moved verbatim from `skills/workerbee/SKILL.md` (2026-11-16, token-efficiency order). Rules here bind as if in SKILL.md.

**Cross-repo dispatch, external session (upstream incident B gap — honest limit, not a
claimed fix).** Incident B's actual root cause: a session working in a
*different* repo (the upstream private governance repo), dispatching work about an agents-inc issue, never
read agents-inc's `AGENTS.md` — it had no local reason to know this
contract existed. This repo cannot reach into another repo's session and
force a read; no such enforcement mechanism exists here (no hook, no CI
gate that runs against external repos). The only thing achievable from
this side: make the contract self-contained and say plainly, in the
canonical source (`AGENTS.md` § Delegation prompt contract), that any
session — this repo or another — dispatching work that touches an
agents-inc issue/task MUST fetch and apply this section first. Paste-and-
tick block above is written to be copy-pasted whole into a dispatch prompt
from anywhere, needing no other agents-inc file open. **This does not
close the gap for a session that never thinks to look** — that half of
incident B stays open; a real fix would need the *dispatching* repo (the
upstream private governance repo, or whichever originates the call) to add its own check, which is out of this
repo's control.
