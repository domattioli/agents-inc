# Plan: split agentic docs (035)

## Approach
1. Add `AGENTS.local.md` to `.gitignore`; create it with operator-only content.
2. Trim `AGENTS.md` to public content; add link to `docs/CONTRIBUTING.md`.
3. Write `docs/CONTRIBUTING.md` (docker dev, tests, stress).
4. Load path: verify Claude Code, Codex, Gemini read `AGENTS.local.md`. If not, the operator's `~/.claude/AGENTS.md` gets one line telling sessions here to read it at start.
5. Sweep readers of moved text; run agentic-docs lint; run full suite in docker.

## Migration table
| Rule in AGENTS.md today | Destination |
|---|---|
| Intro line: downstream of DomI, old repo name | public neutral line; DomI detail to local |
| Develop and stress-test in docker (operator rule 2026-11-09) | public `docs/CONTRIBUTING.md` (commands); mandate wording and sandbox-off note to local |
| Project rules: `$0` spend cap, no paid fallback, optional keys, D41/D42 gates, dispatch contract, handoff lint | binding-for-all stay public, neutral wording; operator-only parts to local |
| CODEX_BRIDGE_MODE=ultra block | public (bridge behavior) |
| Governance: DomI downstream, spec locations, handoffs local | local |
| Documentation style, project canon, layout, setup | public |

## Risks
- A test or doc reads a moved heading: grep `AGENTS.md` references in tests, scripts, docs (task T5).
- Local file unread by some drivers: step 4 fallback.
- `.gitignore` entry must not hide the file from `git status` confusion; document in local file header.
