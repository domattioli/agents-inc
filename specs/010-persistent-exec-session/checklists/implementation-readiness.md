<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Readiness Checklist: Persistent Executive Session Across a Mandate

**Purpose**: Binary yes/no gate to run against `tasks.md` + eventual implementation before `/speckit-analyze` and `/speckit-implement`. Every item is a command or file:line check, not a judgment call.
**Created**: 2026-09-12
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [contracts/cli-and-bridge.md](../contracts/cli-and-bridge.md)

**Note**: `checklists/requirements.md` (spec-quality gate, all items already `[x]`) is unchanged by this file — this is a separate, implementation-facing checklist (Gate C in plan.md).

## Disposition status (added 2026-09-12 — analyze warning (f))

Analyze flagged that every item sat unchecked with no stated disposition, and that Gate C did not require one. Gate C now has row **C-G4**: every item must be checked, or explicitly marked `PRE-REGISTERED` / `N/A`, or the gate FAILs. Dispositions as of today (no implementation code exists yet — the target files are unmodified, so most items are *unrunnable*, not *unexamined*):

| group | items | disposition today |
|---|---|---|
| Static, verifiable **now** against the current tree | CHK008 (+CHK029 registered), CHK018, CHK023, CHK024 | **DISPOSED — findings recorded below.** CHK008: **RED as originally written** → rewritten (see item). CHK018/CHK023/CHK024: `PRE-REGISTERED` — the code sites they grep do not exist yet, but the item text is final and needs no change. |
| Depends on code that does not exist yet | CHK001–CHK007, CHK009–CHK017, CHK019–CHK022, CHK025–CHK027, CHK029–CHK031 | `PRE-REGISTERED (implement phase)` — each names its verifying test or command; none is a judgment call. |
| Already satisfied | CHK028 | **[x]** — `checklists/requirements.md` is fully `[x]` and was not edited by the tasks/checklist/analyze-fix passes. |
| Pointer / deduplicated | CHK024 | **N/A as a separate check** — `--by` value validation folded into CHK030 (analyze pass-2 W-08); the id is retained as a pointer plus the C2a precedence assertion, which is `PRE-REGISTERED (implement phase)` behind T003/T034. |

**Round-3 update (2026-09-12).** Six items added — CHK035-CHK040 — all disposed `PRE-REGISTERED (implement phase)`: each names its verifying test (T005/T009, T015/T045, T023/T024, T043, T044) and none is a judgment call. CHK028's checkbox was ticked so the item agrees with the `Already satisfied` row above it (N-W4). No item was removed and no item is left undisposed.

**Pass-2 update (2026-09-12, `analyze-2026-09-12b.md`).** Gate **C-G4** now covers *every* checklist under `checklists/`, not this file alone (W-03), and a new Gate **C-G5** requires each `PRE-REGISTERED` item above to flip to `[x]` or RED at Gate I (OQ-2) — a `PRE-REGISTERED` marker surviving into Gate I is a FAIL. Items re-pointed or qualified this pass: CHK001/CHK002 (now backed by T046, W-10), CHK021 (idempotency qualified as C2a step 3, F-01), CHK024 (pointer, W-08), CHK034 (re-pointed at T045, F-03). No item was removed and no item is left undisposed.

Findings actually disposed today:

- **CHK008 → RED, fixed.** The original item's grep scope (`agent_runner.py` definitions only) could not detect the 3/4 collision with `route.sh`, which is exactly the collision the analyze pass found. Item rewritten to grep the propagation source as well; new codes 7/8/9.
- **CHK028 → GREEN.** Verified by reading `checklists/requirements.md`: all items `[x]`.
- No item was found ambiguous or non-binary; C-G2 holds.

## Backward compatibility (FR-012)

- [ ] CHK001 `agent.sh submit --backend codex "ping"` (no `--mandate`) produces a `result.json` with **no** `mandate` key — verifiable via `agent.sh status <id> --json | jq 'has("mandate")'` returning `false`, **and by the automated test `test_submit_without_mandate_has_no_mandate_key` (T046)**, which also asserts `role`/`mode`/`prior_engagement` are absent and that no file is created under `STATE_DIR/mandates/` (test added 2026-09-12, analyze pass-2 W-10 — this item previously had no test task behind it).
- [ ] CHK002 `ask.sh` invoked without `--thread` sends a POST body with **no** `thread_id` field (absent, not `null`) — verifiable via the automated test `test_ask_sh_body_omits_thread_id_when_flag_absent` (T046) in `tests/test_bridge_thread_id.py`; the `bash -x ask.sh` trace is corroboration only.
- [ ] CHK003 Bridge `POST /prompt` with no `thread_id` field in the body preserves today's global-thread auto-restart behaviour unchanged — verifiable via `test_global_thread_path_unaffected_when_thread_id_absent` in `tests/test_bridge_thread_id.py` passing (R-C regression).

## Exit-code table (contracts/cli-and-bridge.md C1)

- [ ] CHK004 Exit code `7` fires with stderr exactly `agent: mandate <M> role <R> in flight: <job_id> (use --force to override)` on duplicate in-flight engagement — verifiable via `test_duplicate_inflight_refused_names_job_id`.
- [ ] CHK005 Exit code `7` fires with stderr exactly `agent: mandate <M> role <R> opened with <X>, requested <Y> (use --force to override)` on model mismatch — verifiable via `test_model_mismatch_refused_before_dispatch`.
- [ ] CHK006 Exit code `8` fires with stderr exactly `agent: mandate <M> closed at <ts> by <actor>; open a new mandate` on any `submit --mandate` against a closed mandate — verifiable via `test_closed_mandate_refuses_all_resume`.
- [ ] CHK007 Exit code `9` fires with stderr exactly `agent: mandate <M> role <R> resume failed for thread <T>; rerun with --fresh to replace` when the bridge returns 409 — verifiable by tracing `agent_runner.py`'s handling of the 409 response (T016).
- [ ] CHK008 **[REWRITTEN — the old version structurally missed the collision]** New exit codes 7/8/9 do not collide with any code reachable from `agent.sh submit`, including codes **propagated from another script**. The old item grepped only `agent_runner.py` for exit-code *definitions*, which cannot see a code that enters the runner at runtime — `agent_runner.py:150` does `die(detail, selected.returncode)`, re-raising `route.sh`'s exit status verbatim, and `route.sh` exits **3** (`route.sh:209`, no non-cooling backend) and **4** (`route.sh:162`, bad chain). Verify **both** sources:
  - `grep -nE "sys\.exit|die\(.*, *[0-9]+\)" skills/codex-bridge/scripts/agent_runner.py` → no use of 7/8/9 outside the new mandate paths;
  - `grep -nE "exit [0-9]+" skills/codex-bridge/scripts/route.sh` → the set of codes it can exit with (today 1, 2, 3, 4, 5, 127) contains **none** of 7/8/9;
  - `grep -nE "returncode" skills/codex-bridge/scripts/agent_runner.py` → every propagation site is accounted for in the two greps above.
  Any future propagation source added to `submit` must be added to this item's grep list.
- [ ] CHK029 A mandate refusal never returns exit 3, 4, 5, or 127 — verifiable via `test_mandate_exit_codes_do_not_collide_with_route_sh` (T044).

## Bridge 409 behaviour (contracts/cli-and-bridge.md C3)

- [ ] CHK009 A caller-supplied `thread_id` that fails to resume returns HTTP `409` with JSON body `{"error":"resume failed","thread_id":"<T>","stderr":"<first 500 chars>"}` — verifiable via `test_thread_id_resume_failure_returns_409`.
- [ ] CHK010 No automatic fresh retry occurs on the caller-supplied-`thread_id` failure path — verifiable by inspection: the 409 branch in `bridge.py` does not call the existing retry-as-fresh code path (T009/T016).
- [ ] CHK011 A body with both `thread_id` and `reset: true` returns HTTP `400` — verifiable via `test_reset_and_thread_id_mutually_exclusive_400`.
- [ ] CHK012 For a caller-supplied `thread_id`, a successful response has `session_restarted: false` always — verifiable by reading the response-construction branch in `bridge.py` for the `thread_id`-present path.

## Edge cases (spec.md `### Edge Cases`) — individually

- [ ] CHK013 Resume target no longer exists (provider purged / machine changed): the system surfaces the failure and does not silently cold-start — verifiable via `test_thread_id_resume_failure_returns_409` + `test_submit_mandate_resumes_stored_thread_id_no_rebrief`'s negative case.
- [ ] CHK014 Caller process (run root) dies mid-mandate: a second, independent process reading the same mandate file sees identical `thread_id` values — verifiable via `test_mandate_survives_process_restart_second_reader_sees_same_thread_id` (I5).
- [ ] CHK015 A backend other than `codex` dispatched under a mandate records `continuity: no-resume` and never sets a non-null `thread_id` — verifiable via `test_no_resume_continuity_for_non_codex_backend` (I4).
- [ ] CHK016 Two concurrent mandates re-using the same role name and model keep fully separate `thread_id` values, keyed by `run_id` — verifiable via a two-mandate variant of `test_load_save_roundtrip` or `test_new_mandate_same_roles_gets_fresh_session_no_leak`.
- [ ] CHK017 `--force` on a duplicate in-flight engagement lets the second engagement proceed, both engagements remain recorded in `roles.<r>.engagements`, and one `Override{kind:"duplicate"}` entry is appended naming both job ids — verifiable via `test_force_duplicate_proceeds_both_recorded_override_logged`.

## Never-auto-close / 7-day preflight warning (FR-013)

- [ ] CHK018 An open mandate is never transitioned to `closed` by any code path except the explicit `mandate close` verb — verifiable by `grep -n '"state"\s*[:=]\s*"closed"' skills/codex-bridge/scripts/agent_runner.py` showing exactly one write site (inside the close-verb function).
- [ ] CHK019 `agent.sh mandate list` prints a `WARN:` line on stderr for every open mandate with `opened_at` older than 7 days, and prints no `WARN:` line for mandates ≤7 days old — verifiable via `test_mandate_list_warns_open_mandate_over_7_days`.
- [ ] CHK020 `skills/speckit-pipeline/scripts/preflight.sh` invokes `agent.sh mandate list` after its existing `.specify/` check and its own exit code is unaffected by any `WARN:` output — verifiable via `bash -n skills/speckit-pipeline/scripts/preflight.sh` plus a manual run showing exit 0 with a seeded stale mandate present.

## Mandate close / show semantics (contracts/cli-and-bridge.md C2)

- [ ] CHK021 A second `mandate close` on an already-closed mandate **carrying a valid `--by`** exits `0` and prints an already-closed message rather than erroring — verifiable via `test_mandate_close_idempotent_and_refuses_with_inflight_unless_force`. (Qualified 2026-09-12, analyze pass-2 F-01: idempotency is C2a precedence **step 3** and is reached only after argument validation passes at step 1; a repeat close with an invalid `--by` exits 2 — CHK024/CHK030.)
- [ ] CHK022 `mandate close` on a mandate with a non-terminal `in_flight_job_id` for any role is refused unless `--force` is passed, and `--force` use is logged as an Override — verifiable via the same test (CHK021's file).
- [ ] CHK023 `mandate show <run_id> --json` on a nonexistent `run_id` exits `1` — verifiable by direct invocation against a state dir with no matching file.
- [ ] CHK024 **[POINTER — deduplicated 2026-09-12, analyze pass-2 W-08]** `--by` value validation (including the empty-string case) is **not** re-checked here: it was a strict subset of **CHK030**, which covers empty/unknown/valid values, the exact stderr string, and the no-widening rule. See CHK030. The non-duplicated remainder retained under this id: `mandate close` honours the **C2a precedence rule** — an invalid `--by` exits 2 *before* the mandate record is read or its state inspected, so an invalid actor is refused even on an already-closed mandate and nothing is written — verifiable via `test_close_by_invalid_rejected_even_when_already_closed` (T003) and quickstart step 8a's `state` assertion after a refused close.

## Documentation (C6)

- [ ] CHK025 `skills/codex-bridge/SKILL.md` documents the new `submit` flags (`--mandate --role --model --fresh --force`), exit codes 7/8/9, the `mandate close/list/show` verb group, the `--by` allowlist (C2a), the `follow-up` mandate-flag exclusion (C1a), and the bridge 409 response shape — verifiable by `grep` for each flag/exit-code/verb name in the file.
- [ ] CHK026 `skills/workerbee/SKILL.md` Step 1a contains the mandate-dispatch sentence naming `agent.sh submit --backend codex --model <slug> --mandate <run_id> --role <rung>` and the bare-`codex exec` prohibition, with the astra/sol/terra/luna rows themselves left unchanged — verifiable by diffing Step 1a before/after.
- [ ] CHK027 The implementation PR description contains the verbatim v1-scope note (Codex-only, Claude `Agent`-tool + free-model paths deferred) sourced from `specs/010-persistent-exec-session/pr-description-note.md` — verifiable by reading the PR body once opened.

## `--by` actor validation (FR-005a / contracts C2a)

- [ ] CHK030 `mandate close <M> --by <actor>` accepts **only** `ceo` or `lead` (case-insensitive) and refuses every other value — including `--by ""`, `--by grunt`, `--by supervisor` — with exit 2 and stderr exactly `agent: --by must be one of: ceo, lead`; no env var, flag, or `--force` widens the allowlist — verifiable via `test_close_by_rejects_unknown_actor_exit2` + `test_close_by_accepts_ceo_and_lead_only` (T034) and by `grep -n "ceo" skills/codex-bridge/scripts/agent_runner.py` showing exactly one allowlist literal. ⚠ The roster `{ceo, lead}` itself is operator-unconfirmed (no Task Authority roster file in repo); this item checks enforcement, not roster correctness.

## State-dir containment (FR-015)

- [ ] CHK031 A `CODEX_BRIDGE_AGENT_STATE_DIR` resolving inside the repository root or under `~/.claude/` is refused with exit 2 and nothing is written there — verifiable via `test_state_dir_inside_repo_refused` + `test_state_dir_under_dot_claude_refused` (T043).

## Mandate × follow-up interaction (FR-014 / contracts C1a, C3)

- [ ] CHK032 A caller-supplied-`thread_id` request leaves the bridge's global thread attribute byte-identical (before vs. after, including on the 409 path) and returns the **request-local** observed id, so a pending `follow-up` is undisturbed — verifiable via `test_thread_id_path_returns_request_local_id_and_leaves_global_unchanged` + `test_mandate_dispatch_does_not_disturb_pending_followup_thread` (T005, T041) and quickstart step 3b.
- [ ] CHK033 `follow-up` passed any mandate flag exits 2 with `agent: follow-up does not accept mandate flags in v1; use submit --mandate` — verifiable via `test_followup_rejects_mandate_flags_exit2` (T041).

## SC-001 measurability

- [ ] CHK034 The round-≥2 outbound body's `prompt` field — **as produced by the `submit --mandate` path itself**, not by a hand-built `ask.sh --thread` call — is byte-identical to the caller's new input with no injected background. Authoritative verification: **`test_submit_mandate_prompt_body_byte_identical_no_preamble` (T045)**, which captures the body the stub `ask.sh` receives on round 2 and asserts content + length equality and `mode == "resumed"`; it makes **no provider call**. Corroboration: quickstart step 3a (runs that test) and 3a-ii (read-only check that step 3's recorded round-2 prompt is unmutated). **Re-pointed 2026-09-12 (analyze pass-2 F-03)** — the previous wording named quickstart step 3a alone, which measured a different call path and fired a live, unrecorded provider turn that mutated the system under test.

## Fresh-engagement isolation (FR-014 / contracts C3 `fresh` / I9)

- [ ] CHK035 A `POST /prompt` body carrying `fresh: true` builds a `codex exec` command with **no** `resume` argument even when the server already holds a global thread, returns the request-local observed id, and leaves the server's global thread attribute byte-identical — verifiable via `test_fresh_true_builds_command_without_resume_and_leaves_global_unchanged` (T005/T009). Added 2026-09-12, round-3 fix N-C5.
- [ ] CHK036 Every `submit --mandate` engagement sends **exactly one** of `--thread`/`--fresh` to `ask.sh` — never neither (which would join the bridge's global thread) and never both (`ask.sh` exits 2; the bridge returns 400) — verifiable via the captured stub argv in `test_submit_mandate_prompt_body_byte_identical_no_preamble` (T045) plus `test_fresh_and_thread_id_together_400` (T005), and by `engagements[n].isolation` in the mandate record (I9, T015).

## In-flight close refusal exit code (contracts C1/C2/C2a step 4)

- [ ] CHK037 `mandate close <M>` with a role still in flight and no `--force` exits **10** with stderr exactly `agent: mandate <M> has role <R> in flight: <job_id> (use --force to close anyway)`, writes nothing, and the same close with `--force` exits 0 and appends one Override — verifiable via `test_mandate_close_inflight_refusal_exits_10` (T023/T024) and quickstart step 5a. Added 2026-09-12, round-3 fix N-C2 (C2 previously named no exit code for this refusal).
- [ ] CHK038 The exit-**2** usage class is intentional and pinned: `follow-up` with mandate flags (C1a), an off-allowlist `--by` (C2a), and a repo-inside state dir (FR-015) all exit 2, while no mandate **state** refusal returns 2 — verifiable via `test_mandate_exit_codes_do_not_collide_with_route_sh` (T044). Added 2026-09-12, round-3 fix N-W2.

## Repo-root resolution for FR-015 (contracts C7)

- [ ] CHK039 The repo root used by the FR-015 guard is resolved by `git rev-parse --show-toplevel` from `agent_runner.py`'s own directory, falling back to the nearest ancestor containing `.git`, and is **never** anchored on `CODEX_BRIDGE_SCRIPTS_DIR` — verifiable via `test_repo_root_resolution_prefers_git_toplevel_and_falls_back_to_dot_git` (T043) and `grep -n "CODEX_BRIDGE_SCRIPTS_DIR" skills/codex-bridge/scripts/agent_runner.py` showing no use inside the guard. Added 2026-09-12, round-3 fix N-W11.

## SC-001 corroboration source (contracts C1 `result.json`)

- [ ] CHK040 `result.json` under a mandate carries `prompt` and `mode`, and `agent.sh result <id> --json` exposes them — verifiable via T015/T045; note `agent.sh status --json` does **not** (`brief()`, `agent_runner.py:271-275`), which is why quickstart step 3a-ii reads `result`, not `status`. A non-mandate `submit` artifact gains none of the mandate keys (CHK001, T046). Added 2026-09-12, round-3 fix N-C1.

## Spec-quality carry-forward (checklists/requirements.md)

- [x] CHK028 `checklists/requirements.md` remains fully `[x]` with no item reverted to unchecked by any edit made during tasks/checklist authoring — verifiable by reading that file (unchanged since the specify phase; this dispatch made no edits to it). **Box ticked 2026-09-12 (round-3 fix N-W4)** — the Disposition-status table already recorded this item as `[x] Already satisfied` while the item itself sat unticked; the two now agree.

## Notes

- CHK001–CHK003, CHK013–CHK017, CHK025–CHK026 are pre-registered checks for the implement phase (target files not yet modified), not yet run. See **§ Disposition status** for the per-group disposition Gate C-G4 requires.
- Items added by the 2026-09-12 **round-3** fix pass: CHK035-CHK036 (fresh-engagement isolation, N-C5), CHK037-CHK038 (exit 10 + the exit-2 usage class, N-C2/N-W2), CHK039 (repo-root resolution, N-W11), CHK040 (`result.json` `prompt`/`mode`, N-C1). CHK028's box was ticked to match its recorded disposition (N-W4).
- Items added by the 2026-09-12 analyze-fix pass: CHK029 (exit-code non-collision test), CHK030 (`--by` allowlist), CHK031 (state-dir containment), CHK032–CHK033 (mandate × follow-up / request-local thread), CHK034 (SC-001 measurement). CHK008 was rewritten.
- Every item cites a concrete command or file:line; none says "ensure quality" or similar.
