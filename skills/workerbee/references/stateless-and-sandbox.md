# workerbee: stateless buddies and sandbox gotchas

Moved verbatim from `skills/workerbee/SKILL.md` (2026-11-16, token-efficiency order). Rules here bind as if in SKILL.md.

### Step 6: Feed stateless buddies real source

Free-tier models see only your prompt. Given a *description* of a
function, they will invent a plausible one that does not exist — this
burned a whole collaboration round.

Paste verbatim source, real sample rows, actual command output. And:
**buddy output is never evidence.** Verify anything you keep against the
real system yourself, with a citation.

Expect provider failure. Observed verbatim:

```
ask_openrouter: API error: Upstream error from Nvidia: Service temporarily overloaded
ask_gemini: API error: This model is currently experiencing high demand.
ask_mistral: API error: Not enough capacity available for this request, please retry later.
```

Fail over across the family. Never stall on one dead provider.

### Step 7: Know the sandbox gotchas

- A delegate under `workspace-write` has **no network**. HTTP buddies fail
  with `Could not resolve host: ...`. Fix:
  `-c 'sandbox_workspace_write.network_access=true'`.
- The same sandbox blocks `.git/index.lock`, so delegates **cannot
  commit**. Expect `Operation not permitted`. Have the delegate report
  `BLOCKED-SANDBOX` and land the commit yourself.
- Do not commit while a delegate's snapshot is live: the commit moves HEAD
  and the delegate's verify fails for a change it did not make. If a commit
  is unavoidable, re-capture the snapshot and re-issue it to the delegate.
- `--skip-git-repo-check` is required outside a git repo.
- Read-only sandbox is the cheapest way to enforce a review-only scope. Do
  not rely on the model honoring "do not edit" when the sandbox can
  guarantee it.
