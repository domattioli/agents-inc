<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-06 skill=speckit-analyze repo=domi session=session_01TixUJB6fxnLqLfgUv42xTG -->
# Analyze log: 018-mcp-channel-hygiene

Analyzer: fable (Executive rung, read-only), dispatched by the Supervisor. Fixes by the Orchestrator Lead (opus) in spec.md, plan.md, tasks.md, research.md and checklists only; no code edited. Rulings where fable left a choice came from the Supervisor (opus), 2026-10-06.

## Cycle 1 (2026-10-06): 16 findings, 0 CRITICAL, 2 HIGH

| Id | Finding (as relayed by the Supervisor) | Resolution | Location |
|---|---|---|---|
| A1 (HIGH) | Two existing tests `assertEqual` the exact broker tool list (`tests/test_worker_mcp.py:293`, `tests/test_mcp_broker.py:96`); SC-009 "adds cases only" breaks when `cancel` is added. | Fixed. SC-009 names both assertions (`test_initialize_and_tools_list`, `test_needs_lead_answer_wait_resume`), each updated to add `cancel` only; T034 does that update; plan Project Structure notes both. | spec.md SC-009; tasks.md T034; plan.md Project Structure |
| A2 (HIGH) | DD7's 30 s slice cannot meet FR-004's 1 s cancel bound. | Fixed. The reader wakes the 017 wait object on cancel (queue sentinel; `link.event.set()`); the slice bounds progress only. FR-004 and SC-003: 1 s on the broker and in Worker socket mode, `POLL_SEC` + 1 s in Worker file mode. | plan.md DD7; research.md R10; spec.md FR-004, SC-003 |
| A3 | `task_state` undefined for `answered`, `not-running` and a successful `cancel` reply. | Fixed. `answered` and `not-running` carry none; successful cancel reply → `canceled`; every other `refused` reason → `rejected`. Reading of the ruling: `not-running` is a refusal reason, and the specific ruling (none) wins over the general one (`rejected`). | spec.md FR-008; research.md R4; tasks.md T025, T030 |
| A4 | "`timeout` while the turn runs → `working`" is false for a recovered id whose turn died. | Fixed. Mapping is `timeout` → `working` with no liveness claim; the restart edge case says a dead recovered turn reads `working` and that recovering running turns is out of scope. | spec.md FR-008, Edge Cases; research.md R4 |
| A5 | Nothing proves a client accepts an older negotiated version (CHK024). | Fixed. T011 records the Claude client's negotiated version and now serves FR-001; Codex stays [assumed] until installed. CHK024 closed. | tasks.md T011; checklists/protocol-hygiene.md CHK024 |
| A6 | Canon order: operator sign-off came before the cross-vendor review. | Fixed. T027 draft → T028 Codex review → T029 operator sign-off; plan start gate adds that FR-010 merge waits for the CoS commit of the signed D51 amendment. | tasks.md T028, T029, Dependencies; plan.md Start gates |
| A7 | `status` tool `outputSchema` keys unspecified (CHK012). | Fixed. All five keys required (`mcp_broker.py:122-124`). CHK012 closed. | research.md R11; checklists/protocol-hygiene.md CHK012 |
| A8 | Worker server has no task state to put in its progress message. | Fixed. Worker: `waiting; elapsed=<s>`; broker adds `; task_state=<state>`. | spec.md FR-005; research.md R9 |
| A9 | File-broker restart durability unaddressed (CHK005). | Fixed. One Out of Scope line. CHK005 closed. | spec.md Out of Scope; checklists/protocol-hygiene.md CHK005 |
| A10 (LOW) | R13 has an FR-003 row (`ping`), but T002 Serves and the FR-003 map row omit T002. | Fixed. FR-003 added to T002 Serves; T002 added to the FR-003 map row. | tasks.md T002, FR to task map |
| A11 | `<base>` undefined in the FR-012 acceptance and T037. | Fixed. `<base>` = PR 52 merge commit (wave 1), 017 merge commit (wave 2). | spec.md FR-012; tasks.md T037 |
| A12 (LOW) | FR-002 says "each tool" then exempts `ask_lead`; silent on 017's `check_lead`; DD2 says broker tools only. | Fixed. FR-002 says "each broker tool"; Worker server tools (`ask_lead`, 017's `check_lead`) keep plain text. | spec.md FR-002 |
| A13 | DD3 left the import choice open. | Fixed. Lazy import of `MCP_TOOL_TIMEOUT_SEC` inside `_ask_channel`, as `launch` does (`dispatch.py:297-299`). | plan.md DD3 |
| A14 (LOW, WARN) | Constitution Check lacks P6 and P7 rows. | Fixed. Two PASS rows added. | plan.md Constitution Check |
| A15 (LOW) | T021 "no tool call other than `ping`": `ping` is a JSON-RPC method, not a `tools/call`. | Fixed. T021: no `tools/call` served during `ask_lead` while `ping` is answered. | tasks.md T021 |
| A16 | T028/T035 need a Codex CLI on the implement host. | Fixed. Plan start gate: without a Codex CLI, FR-010 waits; T028 failure names it. | plan.md Start gates; tasks.md T028 |

Cycle 1 tally: 16 fixed, 0 rejected, 0 pending. A10, A12, A14 and A15 were applied after the Supervisor sent their text (same cycle). A3 reading accepted by the Supervisor.

## Cycle 2 (fable, 2026-10-06, final)

Fable re-checked A1 and A2 in full (both resolved) and confirmed A3 to A16 present at their logged locations. The fixes introduced 6 new findings: 0 CRITICAL, 0 HIGH, 2 MEDIUM, 4 LOW. The Supervisor (opus, main session) applied them under speckit-pipeline Step 6; no third analyze cycle.

| ID | Finding | Resolution | Location |
|---|---|---|---|
| N1 (MEDIUM) | DD9 added `task_state` to every dict with `status` and `request_id`, so `answered` and `not-running` contradicted FR-008 and R4. | Fixed. DD9 excludes `usage-error`, `answered` and `not-running`; `task_state()` returns None and `handle` omits the key. | plan.md DD9 |
| N2 (LOW) | FR-001 map row omitted T011. | Fixed. T011 added. | tasks.md FR-to-task map |
| N3 (LOW) | T034 updates the two exact-list tests but its Success gate did not run them. | Fixed. Both tests added to T034 Success. | tasks.md T034 |
| N4 (MEDIUM) | The plan start gate requires the CoS to commit the D51 amendment before FR-010 merges, so the wave-2 canon diff check would fail by construction. | Fixed. FR-012 and T037 check each implementation commit with `git show --name-only`; the CoS canon commit is excluded and named by hash. | spec.md FR-012; tasks.md T037 |
| N5 (LOW) | R9 progress message markup unbalanced. | Fixed. R9 rewritten. | research.md R9 |
| N6 (LOW) | Overlap row 4 silent on the exact-list updates. | Fixed. Row cites SC-009. | spec.md Overlap with 017 |

Also fixed: checklists/requirements.md said "Clarifications (empty)", which was stale (Fable cycle 2 out-of-scope note).

Cycle 2 tally: 6 fixed, 0 rejected. No CRITICAL or HIGH open. Analyze succeeded in 2 cycles.
