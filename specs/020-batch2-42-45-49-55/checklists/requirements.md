# Requirements checklist: spec 020

- [x] CHK001: Every FR (FR-001 to FR-024) maps to at least one task in tasks.md, or is marked as the supervisor's job.
- [x] CHK002: Every SC names a test file, or a command with an exit-code check.
- [x] CHK003: Every operator decision (#45 slots+lint+doc, #55 full pip-only, #42 files released, #49 run-id key) appears as an FR marked "operator".
- [x] CHK004: No FR breaks an existing CLI invocation: `ledger append --node-id` still works, and `install --source` still works.
- [x] CHK005: The required slots (A1) have a fixture-update task; the malformed-slots fixture is left alone.
- [x] CHK006: The reporting-chain lint reuses the existing alias-to-rung table; there is no second copy.
- [x] CHK007: The dispatch ledger node is created only for launched runs, never for dry runs or lint refusals.
- [x] CHK008: The pip-only path has a fallback named in case setuptools rejects the `package-dir` mapping.
- [x] CHK009: D55 says it supersedes `docs/RELEASING.md:47`.
- [x] CHK010: Tests never touch the real HOME, `~/.claude`, or `~/.local`.
- [x] CHK011: Stdlib only at runtime; the wheel build test is skipped cleanly when `build` or `pip wheel` is not available.
- [x] CHK012: Out of scope stays out: no version bump, no release, no Codex-spawns-Claude automation.
