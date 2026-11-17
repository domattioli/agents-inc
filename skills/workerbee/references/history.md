# workerbee: history

Moved verbatim from `skills/workerbee/SKILL.md` (2026-11-16, token-efficiency order). Rules here bind as if in SKILL.md.

## Failure Mode This Solves

Documented in session `33338e35-4ce9-43db-8cf0-624adf37e136` (2026-09-04/05).

A supervisor delegating heavily accepts delegate self-reports because they
arrive formatted as evidence. In one session three separate GREEN gates
were false: an alignment gate that printed the delegate's intended array
rather than its rendered output (claimed columns `0 12 44 91 124`, measured
`0 12 49 122 214 329 446`); a harness that passed while row labels silently
vanished from live output because it measured 4 boundaries on rows holding
7 items; and a timing claim of `0.664s` that measured `0.461s`. None were
dishonesty — each was a delegate grading its own work. Separately, a null
price coerced to zero inflated a reported savings figure ~29x, from a
defensible `$1.15` to `$33.06`.

## Version History

- **Unreleased** — REPORTING CHAIN rendered from the optional slots `DELEGATE`,
  `SUPERVISOR`, `EXECUTIVE` with ladder and settings defaults, `--model` on the
  renderer, `agents-inc models chain`, and the `reporting-chain-inverted` lint
  rule (#45); Step 1 relay paragraph for chains the tools cannot build;
  `ledger pending` and `ledger append --run-id` in the CLI section (#49).

- **v1.4.0** (2026-10-01) — Rung names (executive, orchestrator, workhorse,
  grunt) and a generated tier table; five-dimension rung scoring grid ported
  from DomI subagent-dispatch-policy (#27); Step 3c keep a delegate until its
  context ceiling (#28); dispatch header plus slots (#36, #4); dispatch names
  tell the truth and hierarchy statement (#17, #14).

- **v1.3.0** (2026-09-22) — Step 4 generalized from budget-mode flash triage to always-on Chief of Staff triage (D43): verify, then DECIDE / HANDLED / UNDERSTAND re-projection; flash helper kept as budget add-on.

- **v1.2.1** (2026-09-18) — DelegateAgent MCP tool clarification. Step 3b
  (item 1) now notes that `--backend codex --wait` is broken for luna; use
  DelegateAgent MCP tool instead for real-time transcript return. CLI section
  conditional DEFAULT comment and DelegateAgent note added. MODEL ROSTER table
  gains DelegateAgent row.
- **v1.2.0** (2026-09-18) — Three additions. (1) Step 0.5 vendor eligibility
  gate: non-Claude vendors are OFF by default and open only on operator
  request, a stated capability fit, or declared budget modality (which opens
  free grunts only, never paid Codex models); a one-line gate statement is now
  required before any non-Claude dispatch. Closes the gap where "two vendors,
  one ladder" read as a menu of equally-default options with no preference
  expressed. (2) Step 3b visibility contract: states plainly that transcript
  streaming parity with the `Agent` tool is a harness boundary and not
  achievable, makes `--wait` the default dispatch form (which does buy
  transcript-return parity), and requires an unprompted `watch.sh` line on
  every async submit. (3) MUST 7 clarified: the sub-delegate allowlist is a
  hard lock and is opt-in — an operator naming a model is a top-level
  assignment (downward within Claude is free), not an implied allowlist.
  Step 0.5 states the sideways half: downward within a
  vendor is free, sideways across vendors is gated.
- **v1.1.4** (2026-09-18) — Ports the upstream private governance repo's Step 0 dispatch-worthiness gate
  (2 questions: volume ≤3 calls → don't dispatch; affordance → bare-API
  buddies have no filesystem/shell/repo access) into this canonical copy,
  closing the drift where the upstream private governance repo's workerbee fork had the gate and this one
  didn't.
- **v1.1.3** (2026-09-12) — upstream incident A root-cause follow-up: bare-prose
  confirm-and-echo requirement (v1.1.2) is unenforceable by itself — same
  class of instruction the issue says gets ignored. Adds
  `scripts/check_subdelegate_allowlist.py`, a mechanical transcript lint
  (no hook mechanism exists in this repo to block live) that flags a
  nested sub-delegate call landing on a forbidden model or missing the
  confirm-echo line. Self-tested both ways. Does not resolve incident A's open
  (a) model-behavior vs (b) harness-gap question — only makes the drop
  detectable after the fact. Also: incident B root cause (external-repo
  session, no local reason to read this contract) cannot be closed from
  this side alone — added an explicit cross-repo fetch-first note to
  `AGENTS.md` and here as the smallest reachable fix, and corrected
  checklist item 1's `(or no-Skill-tool stated)` wording, which read as a
  blanket escape hatch not present in the original 14-point canon.
- **v1.1** (2026-09-05) — Adds Step 1a (MODEL ROSTER: nickname → slug →
  exact dispatch command, verified against this machine's `codex`
  CLI/`codex-bridge` wrappers), Step 1b (runtime model-discovery snippet
  via `~/.codex/config.toml` + `models_cache.json`), and Step 1c
  (reasoning effort is a separate, operator-owned cost axis; `ultra`
  effort self-delegates and is opt-in only). Closes the gap where the
  capability-ladder table (Step 1, v1.0) named `astra`/`luna` as tier
  labels without a slug or CLI mapping, forcing an orchestrator to
  reverse-engineer both the vendor-nickname lookup and the effort-tier
  distinction by hand mid-session. Same session as v1.0
  (`33338e35-4ce9-43db-8cf0-624adf37e136`); two follow-on incidents same
  day: (1) orchestrator misread "astra"/"luna" as absent Claude models
  because it never checked `~/.codex/config.toml` / `models_cache.json`;
  (2) orchestrator dispatched at `ultra` reasoning effort unprompted
  after being told explicitly not to.
- **v1.0** (2026-09-05) — Initial. Extracted from session
  `33338e35-4ce9-43db-8cf0-624adf37e136`, where three false delegate GREENs
  and a ~29x inflated savings figure motivated the verification and
  honesty rules. Benchmark measured 3 → 0 in the same session.
