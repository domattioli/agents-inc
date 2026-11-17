<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Cross-Project Installation Implementation Plan

**Goal:** Install `agents_Inc` once at user scope so Claude and Codex sessions in unrelated projects reliably route Astra/Sol/Terra/Luna through the Codex CLI.

**Architecture:** Stage immutable release bundles under user data storage, activate one through an atomic `current` symlink, and expose one stable launcher at an absolute recorded path. A durable transaction journal and exclusive lifecycle lock cover every filesystem mutation and recovery. Host-specific skill links point into the active bundle; every subprocess uses executable paths resolved during install, never ambient daemon `PATH` or the source checkout. Direct, read-only Codex execution is the only v1 transport; HTTP bridge installation and daemon lifecycle are deferred.

**Tech Stack:** Python 3.10+ standard library, Bash 3.2+, `unittest`, filesystem symlinks, JSON receipts/journal, Codex CLI.

**Spec:** Operator-approved local-install carve-out from session 2026-09-13 plus Astra/Luna review. Supporting requirements: `docs/PLAN-MVP.md` sections 5–6 and `docs/adr/0003-workerbee-canonical-source-and-distribution.md`. This plan does not resolve marketplace, private-runtime, release-signing, or upstream distribution ownership.

## Global Constraints

- Terra (`gpt-5.6-terra`) owns implementation and integration.
- Luna (`gpt-5.6-luna`) may implement only bounded tests, fixtures, mechanical docs, and narrow helper changes assigned by Terra.
- TDD: failing test before each production change.
- No runtime dependency on source checkout, shell profile, mutable branch, or ambient `PATH`.
- Never pass Astra/Sol/Terra/Luna to Claude `Agent`; all four aliases resolve to Codex slugs.
- Installation preserves foreign files and records every owned path plus replaced symlink target.
- Credentials, Codex auth, job state, and user data never enter release bundles or receipts.
- Install/repair are idempotent. Failed activation leaves prior release usable.
- Uninstall removes only receipt-owned unchanged artifacts; auth and state survive unless explicit future purge feature.
- Codex execution preserves existing Worker isolation: `-s read-only`, empty inherited environment, disabled web search, disabled shell tool, prompt over stdin.
- First install may adopt only the known `~/.claude/skills/workerbee` symlink after explicit `--adopt-existing-workerbee`; every other foreign collision fails closed.
- Skills invoke the absolute launcher path recorded/generated during install; `.local/bin` PATH discovery is convenience only.
- Model effort support comes from versioned `supported_efforts` entries in bundled `workerbees/models.json`; unknown capability fails closed.
- No `curl | sh`, runtime `pip`, Homebrew mutation, hook installation, downstream-repo edits, or paid provider probes.
- No bridge start/stop/status, PID ownership, or daemon termination in v1 install/uninstall.

---

## File Map

- Create `workerbees/install/__init__.py`: public install package.
- Create `workerbees/install/paths.py`: user-scope path model and platform validation.
- Create `workerbees/install/receipt.py`: receipt schema, atomic JSON I/O, owned-path records.
- Create `workerbees/install/transaction.py`: lifecycle lock, write-ahead mutation journal, crash recovery.
- Create `workerbees/install/bundle.py`: allowlisted staging, hashing, atomic activation, rollback.
- Create `workerbees/install/discovery.py`: Claude/Codex skill-link installation and restoration.
- Create `workerbees/install/runtime.py`: executable resolution and stable Codex argv construction.
- Create `workerbees/install/doctor.py`: offline checks and optional live model probe.
- Create `workerbees/install/cli.py`: `install`, `run`, `doctor`, `repair`, `uninstall`, `rollback` CLI.
- Create `scripts/agents-inc`: thin source-checkout bootstrap into `workerbees.install.cli`.
- Modify `workerbees/adapters/codex.py`: accept resolved executable path.
- Modify `workerbees/gateway.py`: inject resolved executable into Codex adapter.
- Modify `workerbees/models.json`: versioned `supported_efforts` metadata for Codex aliases.
- Modify `skills/workerbee/SKILL.md`: aliases + installed launcher contract + discovery triggers.
- Modify `skills/codex-bridge/SKILL.md`: installed launcher contract; remove stale GPT-4/3.5 and repo-relative claims.
- Modify `README.md`: supported install/update/repair/uninstall path.
- Create `tests/test_install_paths.py`, `tests/test_install_receipt.py`, `tests/test_install_transaction.py`, `tests/test_install_bundle.py`, `tests/test_install_discovery.py`, `tests/test_install_runtime.py`, `tests/test_install_doctor.py`, `tests/test_install_cli.py`.
- Create `tests/fixtures/fake_codex.py`: deterministic argv/stdin recorder.
- Create `tests/integration/install_cross_project.sh`: source-independent two-project acceptance smoke.

### Task 1: Path Model and Receipt Contract

**Owner:** Terra. **Luna assist:** fixture paths and receipt round-trip tests.

**Interfaces:**
- Produces `InstallPaths.for_home(home: Path) -> InstallPaths`.
- Produces `InstallReceipt.load(path: Path)`, `save_atomic(path: Path)`, and `OwnedPath`.
- Later tasks consume exact release/config/state/bin/skill paths and ownership metadata.

- [ ] Write failing tests proving these defaults:

```python
paths = InstallPaths.for_home(Path("/Users/tester"))
assert paths.releases == Path("/Users/tester/.local/share/agents-inc/releases")
assert paths.current == Path("/Users/tester/.local/share/agents-inc/current")
assert paths.launcher == Path("/Users/tester/.local/bin/agents-inc")
assert paths.receipt == Path("/Users/tester/.config/agents-inc/install.json")
assert paths.state == Path("/Users/tester/.local/state/agents-inc")
assert paths.claude_skills == Path("/Users/tester/.claude/skills")
assert paths.codex_skills == Path("/Users/tester/.agents/skills")
```

- [ ] Add receipt tests: schema version `1`; release hash; absolute Python/Codex paths; owned paths; prior symlink targets; no field named `token`, `secret`, `auth`, or `prompt`.
- [ ] Run `python3 -m unittest tests.test_install_paths tests.test_install_receipt -v`; expect failures for missing package.
- [ ] Implement frozen `InstallPaths`, `OwnedPath`, and `InstallReceipt` dataclasses. Reject relative paths, unsupported schema versions, and non-dict JSON.
- [ ] Implement atomic receipt write: sibling temp file, `chmod 0600`, flush + `os.fsync`, then `os.replace`.
- [ ] Re-run tests; expect PASS.
- [ ] Commit: `feat: define installation paths and receipt contract`.

### Task 2: Immutable Bundle Staging and Activation

**Owner:** Terra. **Luna assist:** allowlist and tamper fixtures.

**Interfaces:**
- Consumes `InstallPaths` and `InstallReceipt`.
- Produces `LifecycleLock`, `TransactionJournal.begin(...)`, `record_intent(...)`, `record_applied(...)`, `commit()`, and `recover(...)`.
- Produces `stage_bundle(source: Path, paths: InstallPaths) -> StagedBundle`.
- Produces `activate(staged: StagedBundle, receipt: InstallReceipt) -> InstallReceipt` and `rollback(...)`.

- [ ] Write failing tests for allowlisted copy of `workerbees/`, `skills/workerbee/`, `skills/codex-bridge/`, and launcher payload only. Exclude `bridge.py` from v1 bundle.
- [ ] Test exclusion of `.git`, `.env`, `.workerbees`, `__pycache__`, backups, credentials, logs, and source-repo state.
- [ ] Test deterministic SHA-256 manifest, staged-directory mode, repeated staging, tamper detection, and interruption before activation.
- [ ] Test atomic `current` symlink switch while prior target remains available for rollback.
- [ ] Write failing transaction tests: exclusive install/repair/uninstall lock; durable intent before each mutation; applied marker after mutation; predecessor metadata; recovery from failure immediately before/after every mkdir/write/link/replace/unlink operation; concurrent lifecycle refusal.
- [ ] Run `python3 -m unittest tests.test_install_bundle -v`; expect FAIL.
- [ ] Implement explicit allowlist traversal; reject symlinks escaping source root and non-regular payload entries.
- [ ] Write `manifest.json` containing relative path, size, mode, SHA-256. Verify manifest before activation.
- [ ] Implement write-ahead order: acquire lock → recover incomplete journal → persist intent + fsync → mutate → persist applied + fsync → verify → commit receipt → mark journal committed → release lock.
- [ ] Implement temp-stage → verified release directory → atomic relative symlink swap. Never overwrite an existing different release directory. Recovery restores predecessor or completes a proven idempotent mutation.
- [ ] Re-run tests; expect PASS.
- [ ] Commit: `feat: stage and activate immutable runtime bundles`.

### Task 3: Executable Resolution and Canonical Run Command

**Owner:** Terra. **Luna assist:** fake Codex recorder and alias cases.

**Interfaces:**
- Produces `resolve_executable(name: str, search_path: str | None) -> Path`.
- Produces `MODEL_ALIASES` and `build_codex_argv(...) -> list[str]`.
- Produces `run_codex(model, effort, cwd, prompt_stream, receipt) -> int`.

- [ ] Write failing tests for exact aliases: `astra→gpt-6-astra`, `sol→gpt-5.6-sol`, `terra→gpt-5.6-terra`, `luna→gpt-5.6-luna`.
- [ ] Test absolute executable capture, executable-bit validation, invalid alias/effort refusal, path-with-spaces handling, prompt on stdin, explicit cwd, and no shell invocation.
- [ ] Add versioned `supported_efforts` to Codex model records; test bundled registry lookup and rejection of missing/unsupported effort metadata.
- [ ] Test sparse/hostile runtime `PATH`: recorded `/opt/homebrew/bin/codex` wins over fake `codex`; missing recorded binary emits `WB_CLI_NOT_FOUND` plus `agents-inc repair`.
- [ ] Run `python3 -m unittest tests.test_install_runtime -v`; expect FAIL.
- [ ] Implement argument-array command:

```python
[codex_path, "exec", "-m", slug, "-s", "read-only",
 "--skip-git-repo-check", "-C", str(cwd),
 "-c", f"model_reasoning_effort={effort}",
 "-c", 'shell_environment_policy.inherit="none"',
 "-c", 'web_search="disabled"', "-c", "features.shell_tool=false", "-"]
```

- [ ] Default effort to `medium`; validate model-specific effort caps from installed registry before subprocess launch.
- [ ] Re-run tests; expect PASS.
- [ ] Commit: `feat: add stable cross-project Codex launcher`.

### Task 4: Dual-Host Skill Discovery

**Owner:** Terra. **Luna assist:** collision/restore matrix.

**Interfaces:**
- Produces `install_skill_links(paths, release, receipt) -> InstallReceipt`.
- Produces `restore_skill_links(paths, receipt) -> None`.

- [ ] Write failing tests for `workerbee` and `codex-bridge` links under both `~/.claude/skills` and `~/.agents/skills`.
- [ ] Test absent destination, matching managed link, foreign directory, foreign link, broken managed link, and explicit adoption/restoration of current `~/.claude/skills/workerbee` target.
- [ ] Require conflict refusal `WB_CONFIG_CONFLICT`; never replace a foreign regular directory or unrecorded link.
- [ ] Require `--adopt-existing-workerbee` on first install to record the existing symlink target as immutable predecessor before replacement. Without flag, refuse. Never adopt directories, non-workerbee paths, or later changed links.
- [ ] Run `python3 -m unittest tests.test_install_discovery -v`; expect FAIL.
- [ ] Implement links to `~/.local/share/agents-inc/current/skills/<name>` and receipt updates after each successful mutation.
- [ ] Add skill-frontmatter triggers containing `astra`, `sol`, `terra`, `luna`, `Codex delegate`, and explicit statement that Claude `Agent` cannot select them.
- [ ] Generate installed skill bodies with receipt-derived absolute launcher command, e.g. `/Users/<user>/.local/share/agents-inc/current/bin/agents-inc run ...`; never require `.local/bin` on PATH.
- [ ] Re-run tests; expect PASS.
- [ ] Commit: `feat: register delegation skills for both hosts`.

### Task 5: Doctor and Repair

**Owner:** Terra. **Luna assist:** status fixtures and JSON snapshot tests.

**Interfaces:**
- Produces `check_install(paths, live_model: str | None = None) -> DoctorReport`.
- Produces `repair(source, paths) -> InstallReceipt`.
- Stable statuses: `READY`, `WB_CLI_NOT_FOUND`, `WB_SKILL_MISSING`, `WB_RELEASE_UNTRUSTED`, `WB_CONFIG_CONFLICT`, `WB_AUTH_REQUIRED`, `WB_MODEL_UNAVAILABLE`.

- [ ] Write failing offline-doctor tests covering receipt schema, bundle hashes, `current`, launcher, both hosts’ links, Python/Codex executable viability, permissions, and duplicate/foreign skill paths.
- [ ] Prove offline doctor never claims account/model availability.
- [ ] Write opt-in live-probe test using fake Codex exact-response output; map auth/model errors without printing stderr secrets.
- [ ] Write repair tests for moved Codex binary, missing managed link, corrupted bundle, foreign collision, and repeated repair.
- [ ] Run `python3 -m unittest tests.test_install_doctor -v`; expect FAIL.
- [ ] Implement structured report with human text and `--json`; every failure includes one recovery command.
- [ ] Implement repair under lifecycle lock/journal as re-resolution + re-stage + hash verify + managed-link restore + atomic reactivate. Preserve prior working release on failure.
- [ ] Re-run tests; expect PASS.
- [ ] Commit: `feat: add installation doctor and repair`.

### Task 6: CLI, Uninstall, and Rollback

**Owner:** Terra. **Luna assist:** CLI help and idempotency tests.

**Interfaces:**
- Produces `python3 -m workerbees.install.cli COMMAND`.
- Stable launcher commands: `install --source PATH [--adopt-existing-workerbee]`, `run --model ALIAS --effort LEVEL --cwd PATH`, `doctor [--json] [--live-model ALIAS]`, `repair --source PATH`, `rollback`, `uninstall`.

- [ ] Write failing CLI tests for exit codes, help, receipt creation, stdin forwarding, and exact diagnostics.
- [ ] Test interrupted install, repeated install/repair/uninstall, rollback with/without predecessor, and uninstall after user modifies a managed artifact.
- [ ] Require uninstall under lifecycle lock/journal to unlink only matching managed links/files, restore the once-recorded adopted workerbee predecessor, preserve auth/state, and report retained modified artifacts. Do not inspect or terminate bridge processes.
- [ ] Run `python3 -m unittest tests.test_install_cli -v`; expect FAIL.
- [ ] Implement CLI and thin `scripts/agents-inc` bootstrap. Use no third-party dependency.
- [ ] Install convenience launcher at `~/.local/bin/agents-inc`, plus canonical bundle launcher at `~/.local/share/agents-inc/current/bin/agents-inc`. Generated skills use canonical absolute path. Bootstrap pins absolute Python and bundle import root; test with `PATH` excluding `.local/bin`, `PYTHONPATH` unset, source removed, and spaces in home/workspace paths.
- [ ] Re-run tests; expect PASS.
- [ ] Commit: `feat: add transactional installer lifecycle CLI`.

### Task 7: Inject Resolved Executable Through Direct Runtime

**Owner:** Terra. **Luna assist:** regression tests for adapter/gateway executable injection.

**Interfaces:**
- `workerbees.adapters.codex.build_cmd(model, executable, cwd=None, effort="medium")`.
- Gateway context/config supplies receipt-resolved executable and installed registry path.
- HTTP bridge remains untouched and unsupported by v1 installer.

- [ ] Write failing adapter/gateway tests showing bare `codex` is never emitted and receipt-resolved executable reaches every direct worker call.
- [ ] Run targeted existing suites: `python3 -m unittest tests.test_adapters tests.test_gateway tests.test_doctor -v`; capture baseline.
- [ ] Modify adapter and gateway to require/consume absolute executable, effort, and bundle-relative model registry. No implicit PATH fallback.
- [ ] Search `rg -n '\["codex"|\bcodex exec\b' workerbees` and classify every remaining direct-runtime occurrence. Bridge-only hits are documented deferred debt.
- [ ] Re-run targeted + new tests; expect PASS under sparse/hostile PATH.
- [ ] Commit: `fix: inject resolved Codex executable into direct runtime`.

### Task 8: Cross-Project Acceptance and Documentation

**Owner:** Terra. **Luna assist:** README command tables and shell smoke mechanics; Terra reviews all human docs.

**Interfaces:**
- Produces reproducible `tests/integration/install_cross_project.sh`.
- Produces operator-facing install and recovery instructions.

- [ ] Write acceptance smoke using temp home + source copy + projects `A` and `B`. Install, rename source away, then run fake Codex from both projects.
- [ ] Assert each alias emits exact slug; zero Claude invocation; explicit effort/sandbox/cwd; independent state; paths with spaces; source checkout unavailable.
- [ ] Add collision, explicit adoption, interrupted mutation at every journal boundary, concurrent lifecycle refusal, tampered release, sparse PATH, repair, rollback, and uninstall-preserves-foreign-data cases.
- [ ] Run shell smoke; expect FAIL before final wiring, then PASS.
- [ ] Update README setup tree: supported local user install first, source-root developer mode second, exact doctor/repair/uninstall commands, host restart requirement, explicit bridge deferral, and honest pre-MVP/distribution limits.
- [ ] Update `docs/START-HERE.md` and `docs/HOW-IT-WORKS.md`; remove stale `~/Projects/workerbees`, GPT-4/3.5, and repo-relative production commands.
- [ ] Run `rg -n 'Projects/workerbees|GPT-4 or GPT-3.5|skills/codex-bridge/scripts/agent.sh submit' README.md docs skills/workerbee skills/codex-bridge`; require zero active production-path claims.
- [ ] Commit: `docs: document cross-project installation lifecycle`.

### Task 9: Full Verification and Release Gate

**Owner:** Terra. **Luna assist:** none; independence gate stays with supervisor/root.

**Interfaces:** Final tested install candidate only; no new behavior.

- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Run `bash tests/integration/install_cross_project.sh`.
- [ ] Run `bash -n scripts/agents-inc tests/integration/install_cross_project.sh skills/codex-bridge/scripts/*.sh`.
- [ ] Run repo-required health check if present; current checkout lacks `scripts/instructions_on_start.sh`, so record exact absence rather than invent success.
- [ ] Review git diff for secrets, source-path leakage, unrelated changes, generated state, backup files, and user-owned files.
- [ ] Manually test from unrelated project after host restart: ask Claude for Astra; expected behavior is Codex dispatch via `agents-inc`, never “Astra unavailable” and never Claude-model substitution.
- [ ] Run opt-in absolute-path `~/.local/share/agents-inc/current/bin/agents-inc doctor --live-model astra`; record model slug/status only, no prompts/auth data.
- [ ] Supervisor independently reviews Terra output against this plan; delegate self-PASS is insufficient.
- [ ] Commit final fixes with compliant `<type>: <imperative summary>` messages; do not squash around failing evidence.

## Dispatch Sequence

1. Root dispatches Tasks 1–3 to Terra as one foundation batch. Terra may ask Luna for fixtures/tests only.
2. Root verifies foundation tests and exact argv independently.
3. Root dispatches Tasks 4–7 to Terra. Terra may ask Luna for collision matrices, snapshots, and regression fixtures.
4. Root verifies install ownership, no-ambient-PATH behavior, and rollback independently.
5. Root dispatches Task 8 to Terra with Luna documentation/mechanical assistance.
6. Root alone owns Task 9 acceptance decision.

## Completion Definition

- Fresh unrelated Claude and Codex sessions discover installed skills.
- “Use Astra” routes through recorded `/opt/homebrew/bin/codex` to `exec -m gpt-6-astra -s read-only` with environment/web/shell isolation.
- Source checkout can disappear without breaking installed runtime.
- Sparse/hostile PATH cannot redirect provider execution.
- Doctor diagnoses missing binary/model/auth/link/hash distinctly.
- Repair and rollback retain previous working release on failure.
- Uninstall restores prior workerbee link and preserves unrelated skills, auth, and state.
- HTTP bridge and daemon lifecycle remain explicitly unsupported by this installer version.
- Full unit suite + cross-project smoke pass; supervisor reproduces critical claims.
