<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Contracts: 010-persistent-exec-session (Phase 1)

Two interfaces change. Both additive; every existing invocation keeps today's behaviour (FR-012).

## C1 — `agent.sh submit` (runner CLI)

New flags on `submit`. **`follow-up` does NOT inherit them** — see "C1a — `follow-up` exclusion" below (analyze fix, blocking #2).

| flag | type | semantics |
|---|---|---|
| `--mandate <run_id>` | string | Engage under mandate. Implicitly opens the mandate on first use. Requires `--role`. |
| `--role <name>` | string | Role session key within the mandate. Requires `--mandate`. |
| `--model <slug>` | string | Passed through to `ask.sh --model`. Under a mandate: recorded on first engagement; mismatch on later engagement → exit 7 unless `--force`. |
| `--fresh` | flag | Mandate-scoped only. Abandon the stored `thread_id` (recorded in `replaced_thread_ids`) and start a new provider session for this role. |
| `--force` | flag | Mandate-scoped only. Override a duplicate-in-flight refusal or a model-mismatch refusal; logged as an Override. |

Exit codes (new). **Renumbered 3/4/6 → 7/8/9 (analyze fix, blocking #3); 10 added 2026-09-12 (round-3 fix, N-C2) for the in-flight close refusal.** Reason: 3 and 4 are already live exit codes of `skills/codex-bridge/scripts/route.sh` (`route.sh:209` `exit 3` = no non-cooling backend available; `route.sh:162` `exit 4` = unknown/invalid chain) and they propagate **verbatim** out of `agent.sh submit` through `agent_runner.py:150` `die(detail, selected.returncode)` whenever `--backend auto` routes. A caller could not tell "route found no backend" (3) from "duplicate in flight" (3), or "bad chain" (4) from "mandate closed" (4). Renumbering was chosen over making `--backend auto` mutually exclusive with `--mandate`: `auto` is the default backend value and rung dispatch legitimately wants routing, so an exclusion would refuse the common case; renumbering costs nothing and keeps both features composable. Codes in use today and therefore reserved: 1 (`route.sh:369`), 2 (`route.sh:10`, `:165`), 5 (`agent_runner.py:133` **and `route.sh:201`** — `route.sh`'s 5 propagates verbatim through `agent_runner.py:150`), 127 (`route.sh:360`), plus 3 (`route.sh:209`) and 4 (`route.sh:162`). Verified 2026-09-12: `grep -nE "exit [0-9]+" route.sh` → `{1, 2, 3, 4, 5, 127}` at `:10, :162, :165, :201, :209, :360, :369`; 7/8/9/10 appear nowhere (analyze pass-2 W-07; 10 re-verified in the round-3 fix pass). New codes are 7/8/9/10.

**Exit 2 is not "reserved, unexplained" (round-3 fix, N-C6).** 2 is the **shared usage-error class** for this CLI: `agent_runner.py:50` `die(message, code=2)` defaults to it, and argparse's own usage errors (`parser.error`, unrecognized/missing arguments) exit 2 as well — verified 2026-09-12: `python3 agent_runner.py follow-up job-aaaa --mandate M --role executive "x"` → `agent.sh: error: unrecognized arguments: --mandate --role executive x`, exit 2. Every new mandate-side refusal that is a *caller-usage* error therefore **deliberately reuses 2** rather than claiming a new code: C1a (`follow-up` given mandate flags), C2a (`--by` not on the allowlist), FR-015 (state dir resolving inside the repo or `~/.claude/`). Codes 7/8/9/10 are reserved for *state*-derived refusals (the mandate record said no), which a caller cannot fix by correcting its argv. Renumbering 2 was rejected: it would fork the existing `die()` default and break every current caller's usage-error contract for no gain.

| code | class | meaning | stderr (exact prefix) |
|---|---|---|---|
| 2 | usage | `follow-up` given mandate flags | `agent: follow-up does not accept mandate flags in v1; use submit --mandate` |
| 2 | usage | `--by` outside the allowlist | `agent: --by must be one of: ceo, lead` |
| 2 | usage | state dir inside repo / `~/.claude` | `agent: mandate state dir must be outside the repo and outside ~/.claude` |
| 7 | state | refused: duplicate in flight | `agent: mandate <M> role <R> in flight: <job_id> (use --force to override)` |
| 7 | state | refused: model mismatch | `agent: mandate <M> role <R> opened with <X>, requested <Y> (use --force to override)` |
| 8 | state | refused: mandate closed | `agent: mandate <M> closed at <ts> by <actor>; open a new mandate` |
| 9 | state | resume failed | `agent: mandate <M> role <R> resume failed for thread <T>; rerun with --fresh to replace` |
| 10 | state | refused: `mandate close` blocked by an in-flight role | `agent: mandate <M> has role <R> in flight: <job_id> (use --force to close anyway)` |

Behaviour matrix (backend `codex`). The **bridge body** column is normative — a mandate engagement is never allowed to fall through to the bridge's global thread (round-3 fix, N-C5; see C3 `fresh`):

| stored thread_id | `--fresh` | result | bridge body sent |
|---|---|---|---|
| null | any | fresh; `mode=fresh` | `{"fresh": true}` — **no** `thread_id`, **no** `reset` |
| T | no | resume T; `mode=resumed` | `{"thread_id": "T"}` |
| T | yes | fresh; `mode=fresh-forced`; T appended to `replaced_thread_ids` | `{"fresh": true}` |

Backend ≠ `codex` under a mandate: allowed, always fresh, `continuity=no-resume`, stderr note `mandate continuity not available for backend <b>` (FR-011).

`result.json` gains, **under a mandate only** (a non-mandate `submit` writes today's artifact unchanged — FR-012): `mandate`, `role`, `mode`, `thread_id`, `prior_engagement`, `prompt`. `prompt` is the exact outbound prompt string handed to `ask.sh` for this engagement; it exists so SC-001 corroboration can be read back from a published artifact through `agent.sh result <id> --json` (round-3 fix, N-C1 — `brief()` at `agent_runner.py:271-275` publishes neither `prompt` nor `mode`, so `agent.sh status --json` is **not** a valid source for either field, and quickstart step 3a-ii reads `result --json` instead).

### C1a — `follow-up` exclusion (v1)

The earlier draft promised `follow-up` would inherit the mandate flags when its parent had a mandate. **That promise is struck** (analyze blocking #2, option (b) chosen: strike, not implement — nothing in tasks.md ever implemented it, and inheritance would require `follow-up` to acquire the whole guard/engagement path, i.e. a second full integration surface for no scenario in spec.md US1–US4).

v1 contract for `follow-up`:

- `follow-up` accepts **no** mandate flags; passing `--mandate`/`--role`/`--fresh`/`--force` to `follow-up` → exit 2 `agent: follow-up does not accept mandate flags in v1; use submit --mandate`.
  - **Implementation note — the string is not free (round-3 fix, N-W10).** Today the `follow-up` subparser (`agent_runner.py:384-388`) declares none of these flags, so argparse refuses first and the contract string never fires. Verified 2026-09-12: `python3 agent_runner.py follow-up job-aaaa --mandate M --role executive "x"` → `agent.sh: error: unrecognized arguments: --mandate --role executive x`, exit 2. **LANDED 2026-09-12** ahead of T013, because it is self-contained and makes contract and code agree today rather than at implement time: the `follow-up` subparser now declares `--mandate`/`--role`/`--fresh`/`--force` with `help=argparse.SUPPRESS`, and `main()`'s `follow-up` branch rejects any of them via `die("follow-up does not accept mandate flags in v1; use submit --mandate")` (exit 2). `follow-up`'s `prompt` positional became `nargs="?"` with an explicit `die("follow-up requires a prompt")` guard — required because argparse abandons a trailing positional when an optional is interspersed between two positionals (`follow-up J --mandate M --role R "x"` otherwise died on `unrecognized arguments: x`); the prompt stays effectively required, and T013 MUST NOT revert it. Verified 2026-09-12: all three flag forms → the contract string, exit 2; `follow-up job-aaaa "x"` → `agent: job not found: job-aaaa`, exit 1 (unchanged); `follow-up job-aaaa` → `agent: follow-up requires a prompt`, exit 2. Chosen over rewriting the contract to argparse's wording because the wording is the caller-facing remedy ("use submit --mandate") and argparse's generic text carries none of it. Owner: **T013** (keeps the wiring; nothing left to add here); asserted by **T041** `test_followup_rejects_mandate_flags_exit2`.
- A `follow-up` on a codex parent keeps exactly today's behaviour: it rides `bridge.py`'s **global** thread — one `self.thread_id` per server object, initialized at `bridge.py:431`, resumed at `bridge.py:194-195`, and **written** at `bridge.py:216` (success path) and `bridge.py:298` (retry path) — i.e. its continuity is incidental, not mandate-scoped. `follow-up` on a mistral `--agent` parent keeps its own real vendor-side continuity (`agent_runner.py:318-319` allows codex-or-mistral follow-up; `:322-323` refuses only the stateless non-`--agent` Mistral case — cites re-verified 2026-09-12).
- Because the codex `follow-up` continuity is the *global* thread, a mandate dispatch MUST NOT disturb it. This is guaranteed by C3's request-local rule (the mandate path never mutates the server's global thread) and is a **mandatory test** — see tasks.md T041.

## C2 — `agent.sh mandate …` (new verb group)

| command | effect | exit |
|---|---|---|
| `mandate close <run_id> --by <actor> [--reason <text>]` | `state=closed`, stamps `closed_at/closed_by/close_reason`. Idempotent **only once argument validation has passed** (second close with a *valid* `--by` → exit 0, prints already-closed; an invalid `--by` → exit 2 even on an already-closed mandate — see C2a precedence rule). Refuses if any role has `in_flight_job_id` unless `--force` (logged) — that refusal exits **10** with stderr `agent: mandate <M> has role <R> in flight: <job_id> (use --force to close anyway)` (exit code added 2026-09-12, round-3 fix N-C2: this row previously listed only exit 0, leaving the refusal without a caller-distinguishable status). | 0, or **10** on in-flight refusal, 2 on invalid `--by`, 1 if missing |
| `mandate list [--json]` | one line per mandate: `<run_id> <state> opened=<ts> age=<N>d roles=<k>`; open mandates with age > 7d prefixed `WARN:` on stderr as well (FR-013) | 0 |
| `mandate show <run_id> [--json]` | dumps the Mandate record | 0 / 1 if missing |

Only `close` is required by clarify Q3=B; `list`/`show` are the minimum read surface needed for FR-013 and for tests/quickstart (`[INFERRED]` — accepted, see spec.md FR-012). `--force` on `close` is likewise `[INFERRED]` (spec.md FR-005 tags it).

### C2a — `--by` actor validation (analyze fix, blocking #5)

`--by` is **not** free text. `mandate close` MUST validate it against a fixed allowlist and fail closed on anything else:

```
allowed: ceo | lead
```

- Value is lowercased and compared exactly. Empty, unknown, or absent `--by` → exit 2, stderr `agent: --by must be one of: ceo, lead`. No env-var or flag widens the list; no `--force` bypass.

**Precedence rule — argument validation precedes state inspection (normative; analyze pass-2 F-01 / OQ-5).** `mandate close` MUST evaluate in exactly this order, and MUST NOT reorder it:

1. **Argument validation** — `--by` against the allowlist above (and `run_id` present). Invalid → **exit 2**, no file read, no write, *regardless of the mandate's state*. In particular an invalid `--by` on an **already-closed** mandate exits 2, not 0: idempotency is a property of the *close operation*, not a bypass of its argument contract.
2. **Record load** — missing mandate file → exit 1.
3. **State inspection / idempotency** — already `closed` → **exit 0**, print already-closed, write nothing.
4. **In-flight guard** — any role with a non-terminal `in_flight_job_id` → refuse with **exit 10** and stderr `agent: mandate <M> has role <R> in flight: <job_id> (use --force to close anyway)`, unless `--force` (logged as an Override). Naming the first such role is sufficient; nothing is written on the refusal.
5. **Transition** — stamp `state/closed_at/closed_by/close_reason`, atomic write.

Rationale: P4 fail-closed (a refused value is never silently accepted) and it makes the two tests non-conflicting — `test_mandate_close_idempotent_and_refuses_with_inflight_unless_force` (T023, step 3) and `test_close_by_rejects_unknown_actor_exit2` (T003/T034, step 1) now exercise different steps of one ordered pipeline instead of contradicting each other. Consequence for callers: a repeat `close` is safe **iff** the repeat carries a valid `--by`.
- Rationale: spec.md FR-005 names exactly two actors — "current Task Authority holder (Lead by default; CEO always permitted)". `CONTEXT.md:31,33` define **Lead** and **Task Authority** but the repo contains **no Task Authority roster file** (searched `CONTEXT.md`, `docs/DECISIONS.md`, `docs/governance/` 2026-09-12 — no roster).
- ⚠ **NEEDS OPERATOR CONFIRMATION** (grill clause): this two-value roster `{ceo, lead}` is the most conservative reading derivable from FR-005, not a doc-sourced roster. If canon later names more holders (e.g. `cto`, `cso` per `docs/DECISIONS.md` owner statements), the list is extended by an operator-signed edit to this row — never by a caller flag. Until confirmed, fail-closed on two values is deliberately narrower than reality rather than wider.
- Supersedes plan.md risk **R-A** (comment-only mitigation), which is now closed by real validation.

## C3 — `bridge.py` `POST /prompt`

Request body, two new optional fields:

| field | type | semantics |
|---|---|---|
| `thread_id` | string | If present and non-empty: run `codex exec … resume <thread_id>`; ignore the server's global thread; do **not** mutate the server's global thread on success. Mutually exclusive with `reset: true` → 400, and with `fresh: true` → 400. |
| `fresh` | bool | If `true`: run `codex exec …` with **no** `resume` argument — the server's global thread is neither read nor written. Mutually exclusive with `thread_id` → 400, and with `reset: true` → 400. |

**Why `fresh` exists (round-3 fix, N-C5 — this is the real fix for a bug the earlier C3 text blessed).** The earlier contract covered only the *resume* half of thread isolation. It said nothing about a request that carries no `thread_id`, so a **fresh mandate engagement** (stored `thread_id` is null, or `--fresh` was passed) fell through to the bridge's global-thread path: `bridge.py:194-195` appends `resume <self.server.thread_id>` whenever the server holds one, and `bridge.py:216` overwrites it on success. Consequence, with no caller doing anything wrong: opening role `supervisor` under a mandate would silently **resume the Executive's / a `follow-up`'s conversation** and then steal the global thread — the exact cross-contamination rule 4 claims to prevent, and the reason quickstart step 2's "separate role, separate thread" was previously false as written. Old rule 3 was narrowly true and globally wrong: it made "the request carried no `thread_id`" mean "the caller wants the global thread", which is right for a bare `ask.sh` call and wrong for every mandate engagement. `fresh: true` gives the caller a third, explicit option — *isolated and new* — instead of inferring intent from an absent field. `reset: true` was not reused: `reset` deliberately **mutates** the global thread (`bridge.py:182`, `:398`), which is the opposite of isolation.

| `thread_id` | `fresh` | `reset` | path |
|---|---|---|---|
| absent | absent/false | absent/false | **global** (today's behaviour, unchanged — FR-012) |
| absent | absent/false | `true` | global, reset first (today's behaviour, unchanged) |
| `T` | absent/false | absent/false | isolated resume of `T` |
| absent | `true` | absent/false | **isolated fresh** — no `resume` arg, global untouched |
| `T` | `true` | any | 400 |
| any | any | `true` with `thread_id` or `fresh` | 400 |

Response, unchanged shape (`response`, `thread_id`, `usage`, `session_restarted`) — for caller-supplied `thread_id` **and** for `fresh: true`, `session_restarted` is always `false`.

**Request-local thread_id rule (analyze fix, blocking #1; cites corrected by analyze pass-2 F-02).** Today `bridge.py` parses the `--json` event stream and assigns the observed session id straight onto the server object. **The two write sites are `bridge.py:216` (`self.server.thread_id = obj.get("thread_id")`, success path) and `bridge.py:298` (same assignment inside the resume-failure retry block)** — both verified by `grep -n thread_id bridge.py` on 2026-09-12. `bridge.py:431` (`self.thread_id = None`) is the server-object **initializer**, not a write site, and an edit locus that names only `:431` or only `:190-200`/`:250-322` **misses `:216` entirely**. The reads that must also change on the caller-supplied path are `bridge.py:238` (success response echo), `:319` (retry response echo), and `:248`/`:331` (`resolve_actual_model(model, self.server.thread_id)`); `:182`, `:268` and `:398` null the global and belong to the global/`reset` path only. That unconditional write contradicts this contract's "do not mutate the global on success" and, on the caller-supplied path, would also let one role's mandate dispatch silently steal the global thread from a pending `follow-up` (C1a). Required behaviour, stated normatively:

Define **isolated request** := the body carries a non-empty `thread_id` **or** `fresh: true`. Everything else is a **global request**.

1. Event parsing MUST write the observed session id into a **request-local** variable (per-request, e.g. a local `observed_thread_id` in the handler), never directly onto the server object.
2. The response body's `thread_id` MUST be that request-local `observed_thread_id` — **not** a read of the server's global attribute.
3. The server's global thread attribute MUST be assigned **only** on the **global** path, i.e. only when the request is not an isolated request. On any isolated request — resume *or* `fresh` — the global attribute is left **byte-identical** across the request (including on resume failure → 409). *(Rule widened 2026-09-12, round-3 fix N-C5: the earlier wording keyed only on `thread_id`, which left a fresh mandate engagement on the global path by construction.)*
4. An isolated request MUST NOT **read** the global attribute either: on the `fresh: true` path the command is built with no `resume` argument at all, regardless of what the server holds (`bridge.py:194-195` is a global-path-only branch).
5. Consequence: two roles engaged through one bridge process never cross-contaminate — whether both are resumes, both are fresh opens, or a mix — and `/reset` semantics for the global path are unchanged.
6. **Edit locus of record** (so an implementer cannot satisfy rules 1-4 at one site and leave the other live): rule 1 MUST be applied at **both** `bridge.py:216` **and** `bridge.py:298`; rule 2 at `bridge.py:238` and `:319`; the model-resolution reads at `:248` and `:331` MUST use the request-local id on any isolated request; rule 4 gates the `resume` branch at `bridge.py:194-195`. `bridge.py:431` needs no change (it is the initializer); `:182`, `:268`, `:398` are global/`reset`-only and stay as they are.

Verification is mandatory, not advisory: the tests MUST assert (a) the returned `thread_id` equals the id observed in this request's event stream, (b) the server object's global thread attribute is unchanged before vs. after an isolated request (identity comparison on the attribute, not just on the response), for **both** the caller-supplied-`thread_id` case (including its 409 path) **and** the `fresh: true` case, and (c) a `fresh: true` request issued while the server holds a global thread builds a command containing **no** `resume` argument. Tasks: T009 (impl), T005/T041 (tests).

New error: resume of a caller-supplied `thread_id` fails → HTTP **409** `{"error":"resume failed","thread_id":"<T>","stderr":"<first 500 chars>"}`. No automatic fresh retry on this path (FR-008). Global-thread path keeps today's auto-restart.

## C4 — `ask.sh`

Two new flags: `--thread <id>` → adds `thread_id` to the JSON body; `--fresh` → adds `fresh: true` to the JSON body (round-3 fix, N-C5 — the runner sends it for every `mode=fresh`/`fresh-forced` mandate engagement so the engagement is isolated from the bridge's global thread). `--thread` and `--fresh` together → `ask.sh` refuses with exit 2 before issuing the request. `--raw` unchanged (runner uses it under a mandate to read `thread_id`).

**Edit locus** (verified 2026-09-12): the POST body is built in a `python3` heredoc at `ask.sh:76-90` (`body = {"prompt":…, "reset":…}`, `model` added conditionally at `:86-87`) — `--thread` and `--fresh` MUST add their keys inside that heredoc (exported env vars, same pattern as `MODEL`), **not** on the `curl` line at `:96+`. Flag parsing goes beside `--model` (`ask.sh:42`) / `--raw` (`ask.sh:50`); the `--raw` output block is `ask.sh:135-148`. When a flag is absent its key MUST be absent from the body entirely — no `thread_id`, no `"fresh": false` (FR-012, CHK002).

## C5 — `preflight.sh` (speckit-pipeline)

After the `.specify/` check: run `agent.sh mandate list` if `agent.sh` is on the expected path; print its `WARN:` lines; never affects exit code.

## C7 — repo-root resolution for FR-015 (round-3 fix, N-W11)

FR-015 requires refusing a `CODEX_BRIDGE_AGENT_STATE_DIR` that resolves "inside the repo root", but named no resolution method, so two implementers could disagree on what the repo root *is*. Pinned here, normatively:

1. **Primary**: `git rev-parse --show-toplevel`, run with `cwd` = `Path(__file__).resolve().parent` (the directory holding `agent_runner.py`), `check=False`, 10 s timeout — same subprocess discipline as `route_backend` (`agent_runner.py:140-151`). Exit 0 → the repo root is its stripped stdout.
2. **Fallback** (git absent, or not a work tree — exit non-zero): walk ancestors of `Path(__file__).resolve()` and take the first directory containing a `.git` entry (file or dir, so worktrees and submodules resolve).
3. **Neither resolves** → there is no repo root to be inside; the containment check against the repo root is skipped, and only the `~/.claude/` check applies. This is fail-*open* on one clause only because a runner installed outside any checkout cannot write into a repo it is not in.
4. Comparison is on **fully resolved** paths (`Path.resolve()`, symlinks followed) using `is_relative_to`, applied to the state dir *and* the repo root / `Path.home()/".claude"`. Equality counts as "inside".
5. Refusal is exit **2** with stderr exactly `agent: mandate state dir must be outside the repo and outside ~/.claude` (C1 usage class).

`CODEX_BRIDGE_SCRIPTS_DIR` is deliberately **not** used as the anchor: it is caller-settable (`agent_runner.py:25`) and would let the same env surface the guard exists to police move the guard's own reference point.

Implementer: **T043**. `git` is not a new dependency (fallback covers its absence).

## C6 — Docs touched (no behaviour)

- `skills/codex-bridge/SKILL.md` `### agent.sh` + `### ask.sh`: document flags (incl. `ask.sh --thread`/`--fresh`), exit codes 7/8/9/10 and the exit-2 usage class, the bridge body's `fresh` field, 409, `--by` allowlist, `follow-up` mandate-flag exclusion (C1a).
- `skills/workerbee/SKILL.md` Step 1a: add a sentence after the roster — "under a mandate, dispatch Codex rows via `agent.sh submit --backend codex --model <slug> --mandate <run_id> --role <rung>`; bare `codex exec` is stateless and must not be used for Executive/Supervisor re-engagement." Rows themselves unchanged.
