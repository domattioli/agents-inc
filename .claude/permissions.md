# Repo permission matrix — `.claude/settings.local.json`

Machine-facing doc. Caveman ultra.

| Rule | Type | Use case | Negative case (must still prompt/deny) | Status |
|---|---|---|---|---|
| `Read(//Users/<you>/.codex-bridge/**)` | Read | inspect codex-bridge config/logs/job state (`agent.sh`, usage db paths, job json) referenced across `skills/codex-bridge/` + `skills/workerbee/SKILL.md` | N/A — `Read(...)` scopes file-read only, no shell exec, no chaining vector. Tool-inherent safety, no adversarial probe needed | keep |

## Removed 2026-09-06 (terra dispatch, feature 004)

- `Bash(sqlite3 -json ~/.codex-bridge/usage.db ' *)` — malformed (unbalanced quote before `*)`, same defect class as the `Bash(supabase:*).` global-settings incident same day). Verified no doc requires Claude itself to shell `sqlite3` CLI directly: all DB access goes through Python `sqlite3` module inside `gask.sh`/`mask.sh`/`oask.sh`/`scripts/proof/audit_parity.sh`. Removed, no wrapper needed (FR-004 satisfied by absence).

## FR-005 check (credential/`.env` reads)

Scanned `.claude/settings.local.json` for `.env|credential|secret|.ssh|.aws|apikey|token` path patterns: none found. Clean.

## RESOLVED 2026-09-06 — dispatch/labor rung mismatch

Was: `CLAUDE.md` 3-tier labor rule (2026-09-05: write=haiku+free, review=luna, orchestrate=fable/astra) vs `docs/DECISIONS.md` D27 4-rung ladder (2026-09-06). `CLAUDE.md` never placed opus/sol and never gated sonnet/terra behind promotion.

Resolution: DECISIONS wins per `CLAUDE.md` own truth-source order (CONTEXT > DECISIONS > governance) + D27 is 1 day newer + more specific. Rewrote `CLAUDE.md` "Coding dispatch — labor rule" to the 4-rung ladder (Supervisor fable↔astra, Orchestrator opus↔sol, Workhorse sonnet↔terra promotion-gated, Grunt haiku↔luna) w/ escalation, second-opinion, promotion-trigger, run-spec and ideal/budget modality rules. Cites D25/D26/D27 + `docs/governance/ROUTING-RANKING.md` inline. `docs/DECISIONS.md` untouched (ruling, not conformed). <!-- terms: historical -->

Old 3-tier text is not retracted, it is subsumed: budget modality = free grunts write, cross-vendor review, ladder kept for supervise/orchestrate/review — same intent, now with the missing rung + gate.

## Open — NEEDS-OPERATOR

- (none open)
