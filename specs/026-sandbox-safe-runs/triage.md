<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-24 skill=speckit-analyze repo=agents_Inc session=b8dceec1 -->
# Spec 026 US0 triage: #89, #87, #88 against `5f01dfe` (2026-10-24)

Checked by the CoS session (opus) with `grep -n` on `development` at `5f01dfe` plus issue comments. `fixed` cites the commit or decision and one site. Line numbers are from 2026-10-24.

## #89 (dispatch audit, 2026-10-18)

| Item | Verdict | Evidence |
|---|---|---|
| 1 forgeable snapshot | fixed | `4bf45c2` (D64, 022 FR-001): trusted copy outside cwd, `_trust_path` `agents_inc/install/dispatch.py:814`; Linux retest 2026-10-24 gave `snapshot=TAMPERED` (issue comment) |
| 2 nested seatbelt for broker Workers | fixed | `sandbox_available()` probes `sandbox-exec ... /usr/bin/true` and caches it, `dispatch.py:399-409`; doctor warns `WB_SANDBOX_NESTED`, `agents_inc/install/doctor.py:99`; D65 refuses a sandboxed caller with exit 69 |
| 3 (moved to #88 item 5) | moved | see #88 item 5 |
| 4 outcome order hides a crashed child; no stderr | fixed | order quota, blocked, timeout, rc-nonzero before fan-out, `_outcome` docstring `dispatch.py:1000`; stderr excerpt in `detail=` when stdout is empty, `dispatch.py:1139` |
| 5 launch exceptions leave no run.json | fixed | `_launch_failed` writes red/`launch-failed`, `dispatch.py:1163` (022 FR-009) |
| 6 mirror failure flips exit code | fixed | `mirror_error` kept, home repo never created, `dispatch.py:1050-1084` |
| 7 hung Worker hangs broker | fixed | per-turn deadline `_turn_timeout()` default 3600 s, `dispatch.py:414`, process group kill on expiry `dispatch.py:687-696` |
| 8 doctor never checks claude | fixed | `WB_CLAUDE_NOT_FOUND`, `doctor.py:98`. The opt-in `claude auth status` probe was not added; folded into #88 item 8 |
| 9 session hook drops warnings | fixed | hook prints each warning, `agents_inc/install/hook.py:47`; this session's hook showed `WARNING: INSTALL_STALE` |
| 10 allow_paths turns prose into prefixes | fixed | tokens ending `.` or `:` dropped, `dispatch.py:247`; globs refused as `refused-scope`, `scope_globs` `dispatch.py:252`, `dispatch.py:1306` |
| 11 credential screen refuses test-file gates | fixed | path-based `GATE_CREDENTIAL_RE` `dispatch.py:1572` (022), prose screen path-based by D67 (spec 025) |
| comment 2026-10-20: report lint on an empty stdout lists seven misses | fixed | `reason=blocked` precedes report lint in `_outcome`; first stderr line goes to `detail=`, `dispatch.py:1139` |

All items fixed or moved. Close #89 as completed.

## #87 (five dispatch snags, 2026-10-18)

| Item | Verdict | Evidence |
|---|---|---|
| 1 false `credential-seeking` on Worker launch | fixed | D67 (spec 025), `a8d8537` path-based `CREDENTIAL_RE` |
| 2 Lead has no web tools for research | open | Lead tools are the broker MCP tools only, `LEAD_TOOLS` `dispatch.py:536`; delegates are denied `WebFetch`/`WebSearch`, `dispatch.py:308`. Memory note "CoS names delegate tools" (spec 023) is a CoS habit, not code |
| 3 sandbox proxy failure doctor misses | fixed in part | D65 refuses a sandboxed caller (exit 69, `caller-sandboxed`); `f5e2830` adds the `agents-inc *` sandbox exclusion at install. A live network probe in doctor is still absent; same as #88 item 8 |
| 4 failure gate needs a backticked command, undocumented | fixed | `skills/workerbee/slots.md:78` states it |
| 5 correct stop reported RED by handoff-lint | open | report-profile handoff-lint findings still add `handoff-lint` to the missing list, `dispatch.py:229`; a report whose only miss is advisory handoff-lint is red. Operator decision whether that stays |

Leave #87 open with items 2, 3 (doctor probe part) and 5.

## #88 (dispatch defects, 2026-10-18)

| Item | Verdict | Evidence |
|---|---|---|
| 1 Codex sandbox nested under Claude Code | fixed | `WB_SANDBOX_NESTED` doctor warning and D65/D66 exit 69 with fix text; `f5e2830` sandbox exclusion |
| 2 Codex read-only sandbox blocks the caveman skill | in spec 026 | US5 (R2) |
| 3 `--run-dir needs --write` | in spec 026 | US6 |
| 4 credential false positive | fixed | D67, `a8d8537` |
| 5 failed runs reported rc=0 | fixed | `is_error` honoured `dispatch.py:710`; `BLOCKED_RE` `dispatch.py:991`; exits 69 and 75 (D64) |
| 6 child inherits parent sandbox network | fixed in part | install adds the `agents-inc *` sandbox exclusion (`f5e2830`), so dispatch runs outside the Bash sandbox. A declared `NETWORK` host slot does not exist |
| 7 grants hide write access | fixed | grants block names acceptEdits writes, `dispatch.py:325` |
| 8 doctor does not probe the dispatch path | open | doctor checks `sandbox_available()` only, `doctor.py:99`; no model-API or GitHub probe from a child process |
| comment 2026-10-20: Codex reads stop at `--cwd` | open | no `READ_PATHS` slot (`grep -n READ_PATHS` finds nothing) |

Close #88 when spec 026 lands, after splitting items 6 (network slot), 8 (doctor live probe) and the `--cwd` read rule into one new issue.

## Follow-up candidates found during spec 026

- The request text screen refused a read-only fable dispatch whose TASK named the git XDG folder under `~/.config` only to describe a design question, with reading forbidden: `dispatch: refused credential-seeking (slot TASK matched '~/.config/git')`, exit 3, 2026-10-24. D67 clause 1 matches any home credential directory followed by a path segment, so it cannot tell a prohibition from a request.
- Plan R3-1: the MCP broker (`agents_inc/install/mcp_broker.py`) takes no lock; two can serve one run directory.
- Plan R4-1: C1 controls (U+0080 to U+009F) are not screened.
- Plan R4-2: `answer_question` text (`dispatch.py:2112`) is not screened for control characters.
- Codex Worker profile: whether `extra_deny` blocks metadata on the run directory's folders (T020 report).
