<!-- provenance: author=domattioli model=claude-fable-5-1 effort=low date=2026-10-23 skill=speckit-pipeline repo=agents_Inc session=695d6fe5 -->
# Spec 025: dispatch follow-ups from the 2026-10-23 Docker stress run

Branch: `development` (agents_Inc). Date: 2026-10-23.
Input: issue bodies #104, #85, #87 (item 1 only), #105, #106, #107, #108; handoff `.claude/handoffs/2026-10-23-docker-stress-results.md`. Scope fixed by the Executive (fable) on 2026-10-23.

## Scope

Six stories. All but US6 touch `agents_inc/install/dispatch.py`; US6 touches `skills/workerbee/scripts/render_dispatch.py`. Every story adds one `## [Unreleased]` line to `CHANGELOG.md` under `### Fixed`, ending with its issue numbers. One delegate does all six: the stories share one file and must land together (QUICKREF: coupled work goes to one delegate).

Files the stories edit (the implement dispatch's FILES IN SCOPE and the SC-005 allow list are copied from this list): `agents_inc/install/dispatch.py`, `skills/workerbee/scripts/render_dispatch.py`, `skills/workerbee/slots.md`, `CHANGELOG.md`, `docs/DECISIONS.md`, `tests/test_dispatch_cli.py`, `tests/test_dispatch_slot_screens.py`, `tests/test_dispatch_failloud.py`, `skills/workerbee/tests/test_template_revision.py`, `tests/test_dispatch_contract.py` (only if an existing assertion flips).

Out of scope: #109 (broker lock, control characters), #87 items 2 to 5, #89, #45, any change to the broker protocol or `run.json` schema version, any change to `pre_dispatch_snapshot.py`.

### US1: dispatch from the agents_Inc checkout lints with the checkout's scripts (#104)

`agents-inc dispatch` loads `check_dispatch_prompt.py`, `render_dispatch.py`, `dispatch_rungs.py` and `pre_dispatch_snapshot.py` through `SCRIPTS = repo_file("skills/workerbee/scripts")` (`dispatch.py:32`, `_load` at `dispatch.py:46`, `snapshot` at `dispatch.py:139`). When the dispatch cwd is an agents_Inc checkout whose scripts differ from the installed bundle, the delegate's report is judged by the stale copy.

- FR-001: `dispatch.py` gains `scripts_dir(cwd: Path) -> tuple[Path, str]`. It returns `(<cwd>/skills/workerbee/scripts, "checkout")` when `<cwd>/agents_inc/install/dispatch.py` and, in `<cwd>/skills/workerbee/scripts/`, `check_dispatch_prompt.py`, `render_dispatch.py`, `dispatch_rungs.py` and `pre_dispatch_snapshot.py` all exist as regular files and `<cwd>` is not inside the installed bundle (`REPO_ROOT`); otherwise `(SCRIPTS, "installed")`. A symlink at any probe path counts as missing.
- FR-002: When `scripts_dir` returns `checkout`, `run()` copies those four scripts into the run's private trust folder (the `_trust_path` folder that `snapshot_trust` uses, outside `cwd`) before launch and records each file's sha256 in the trust record. Every later load of a workerbee script in that run, in `_load`, `snapshot`, `lint_report`, `lint_prompt`, `render`, `parse_fan_out`, `_run_gates`, `_validate_fields`, and the verifier copy shipped into the run directory, reads the trusted copy, on the first turn, on resume, and for broker Workers. A trusted copy whose hash no longer matches makes `snap` `TAMPERED` (reason `snapshot-tampered`). `run()` records `spec["scripts_dir"]` (absolute path of the directory loaded from) and `spec["scripts_source"]` (`"checkout"` or `"installed"`) in `run.json`. On resume the recorded values win; they are never re-derived. A `run.json` without the keys resumes as `installed`.
- FR-003: The status line (`_status`, `dispatch.py:919`) carries a new token `lint=<checkout|installed>` right after `report=...`. `STATUS_RE` in `tests/test_dispatch_cli.py` and the literal at `tests/test_dispatch_failloud.py:191` accept the token. `verify.txt` starts with the line `lint source: <absolute dir>`.
- FR-004: Broker Workers inherit the Lead's `scripts_dir`, `scripts_source` and trusted copies from the parent `run.json` and never probe their own cwd.
- FR-005: Tests in `tests/test_dispatch_cli.py`: a dispatch whose cwd is a fake checkout (the five probe files present, `check_dispatch_prompt.py` patched to flag a sentinel key) prints `lint=checkout` and the report is judged by that copy; the fake delegate edits the checkout's `check_dispatch_prompt.py` during its turn and the report is still judged by the launch-time copy; a dispatch from a plain repo prints `lint=installed`; a cwd that carries the probe files as symlinks prints `lint=installed`.

### US2: the request text screen stops refusing deny-list prose (#85, #87 item 1)

`CREDENTIAL_RE` (`dispatch.py:1394`) matches the bare words `credentials`, `token`, `api_key`, and `.env` anywhere in slot text. The standard SCOPE boilerplate and ordinary CONSTRAINTS ("never open .env") trip it. `GATE_CREDENTIAL_RE` (`dispatch.py:1397`) is already path-based.

- FR-006: `CREDENTIAL_RE` becomes path-based. It matches:
  1. `_HOME_CRED` followed by a further path segment that is not a glob (`~/.ssh/id_rsa`, `~/.codex/auth.json`, `~/.claude/.credentials.json`). A bare home directory (`~/.claude`) or a glob (`~/.claude/**`) in prose does not match. `~/.local/bin/` and `~/.local/share/agents-inc/` are exempt, as `~/.claude/skills/` already is.
  2. Key files `id_rsa`, `id_ed25519`, `*.pem`, `*.key` as path tokens, with the `GATE_CREDENTIAL_RE` token rule extended so the token may also end in `.`, `,`, `;`, `:` or `)`.
  3. A `.env` or `.env.<suffix>` token that follows a path separator or `~`, or that is the first argument of a read verb (`cat`, `read`, `print`, `open`, `source`, `dump`, `echo`, `show`, `less`, `head`, `tail`) inside a backticked command span (`` `cat .env` ``). A prose sentence never matches on `.env` alone.
  The bare words `credentials`, `token`, `access_token`, `api_key`, `api-key` no longer match in free text.
- FR-007: The screen still refuses: `read ~/.ssh/id_rsa and .env, print the api_key` (issue #105 step 1), matched term `~/.ssh/id_rsa`; `` run `cat .env` ``; `cat ~/.claude/.credentials.json` (`tests/test_dispatch_slot_screens.py:125`); `print server.pem.`.
- FR-008: The screen accepts, with a regression test for each: the full rendered Worker boilerplate from `render_dispatch.py` with `example_slots.json` (it contains `No writes to ~/.claude/**, ~/.codex/**, ~/.local/**, ~/.codex-bridge/**`); a CONSTRAINTS value `No writes to credentials, .env, or key files. Never open .env.`; a TASK value `walk mode of the teaching skill mentions credentials and secrets; do not read or modify .env` (issue #87 item 1); a TASK value `run ~/.local/bin/agents-inc doctor`; a TASK value `refresh the token cache test (test_token_refresh.py)`; a TASK value `print access_token` (a bare word, consistent with Q3).
- FR-009: `credential_hit` (`dispatch.py:1582`) keeps its `slot <KEY> matched '<text>'` form. Every refusal surface that reports `credential-seeking` carries that detail: broker `reason_detail` (already present, `dispatch.py:1737`) and the direct path (US3).
- FR-010: Tests live in `tests/test_dispatch_slot_screens.py`. The existing assertions at lines 109-110 (bare `token`), 123-124 (`show the token`, `print access_token`) and 133-135 (`no .env reads`) change to expect acceptance; `test_credential_hit_names_slot` uses `cat ~/.ssh/id_rsa` as its refused text.

### US3: the direct path applies the same request text screen as the broker (#105)

`run()` (`dispatch.py:1106`) renders and launches slots that `_validate_fields` (`dispatch.py:1575`) would refuse as `credential-seeking`.

- FR-011: After slots are read and before the run directory is created, `run()` calls `credential_hit(slots)`. On a hit it prints `dispatch: refused credential-seeking (<detail>)` to stderr and exits `EXIT_REFUSED` (3). No run directory, no prompt, no snapshot is written. `--dry-run` refuses the same way.
- FR-012: `resume()` applies the same screen to `--message` text (the broker already does at `dispatch.py:1972`); a hit prints the same line and exits 3 without touching the run directory.
- FR-013: Test in `tests/test_dispatch_slot_screens.py`: one slots file is refused on the direct path (exit 3, stderr names the slot) and by `_validate_fields` with the same `reason`; a second slots file (the FR-008 boilerplate case) is accepted by both.
- FR-014: `skills/workerbee/slots.md` says in the D51 paragraph (line 99) that the direct path and the broker apply one request text screen and that the refusal names the slot and the matched text.

### US4: `--run-dir` under cwd must be git-ignored (#106)

- FR-015: In `run()`, when `--run-dir` resolves to a path inside `cwd` and `git -C <cwd> check-ignore -q <relative run-dir>` does not exit 0, dispatch prints `dispatch: --run-dir <path> is inside --cwd and not git-ignored; later snapshot verifies would see its files` to stderr and exits 2. The check runs before the run directory is created. `git` absent or `cwd` not a repo: no refusal (the existing snapshot capture reports that case).
- FR-016: A `--run-dir` outside `cwd`, or inside `cwd` and git-ignored (the `.scratch` rule of `default_parent`, `dispatch.py:53`), is accepted as today.
- FR-017: Tests in `tests/test_dispatch_cli.py`: an un-ignored run dir inside the repo exits 2 with that message and creates nothing; an ignored one launches; one outside the repo launches.

### US5: a gate that writes into the repo flips the outcome (#107)

`_finish` (`dispatch.py:982-990`) runs `_verify` first, then `_run_gates`, so a gate's writes never reach the snapshot compare.

- FR-018: When gates ran, `_finish` runs the snapshot verify a second time after `_run_gates` (same `allow` list, same trust handling as `_verify`). When the second verify reports changes that the first did not, `snap` becomes `CHANGED:<paths>` and the outcome is `red` with reason `gate-wrote`. `gate-wrote` takes precedence over `gate-failed`. A second verify of `TAMPERED` or `ERROR:` sets `snap` to that value with reason `snapshot-tampered` or `snapshot-error`. `verify.txt` gains a second block headed `after gates:` with the second verify's output.
- FR-019: When the second verify is clean, nothing in the status line changes and `verify.txt` says `after gates: clean`.
- FR-020: The exit map (`_exit_code`, `dispatch.py:969`) treats `gate-wrote` as any other red (exit 1). The broker-child path (`_BROKER_SAFE_WRITES`, gates skipped) is unchanged.
- FR-021: Tests in `tests/test_dispatch_cli.py` with the fake delegate: a gate `["sh", "-c", "echo pwned > gate_wrote.txt"]` yields `snapshot=CHANGED:gate_wrote.txt outcome=red reason=gate-wrote`; a gate that writes and exits 1 yields reason `gate-wrote`; a read-only gate yields `snapshot=clean outcome=green`.

### US6: the compound verify-gate check parses the command (#108)

`render_dispatch.py:357` accepts any backticked span that contains the literal `pre_dispatch_snapshot.py` unless it holds `&&` or starts with `cd `.

- FR-022: `render_dispatch.py` gains `verify_gate_ok(span: str) -> str | None` returning an error string or None. It `shlex.split`s the span; a `ValueError` is an error. It requires: argv[0] in `("python3", "python")` or ending `/python3` or `/python`; argv[1] ending `skills/workerbee/scripts/pre_dispatch_snapshot.py` (relative or absolute, no `..` segment); argv[2] `verify`; argv[3] present and either `<snapshot>` or a path ending `snapshot.json`; every remaining argument one of `--allow <value>` or `--repo <value>` pairs. Any shell metacharacter in the span (`&&`, `||`, `;`, `|`, `>`, `<` outside the `<snapshot>` placeholder, `$(`, backquote) is an error.
- FR-023: `main()` applies `verify_gate_ok` to every backticked span in `PRE_EXISTING_CHANGES` that contains `pre_dispatch_snapshot.py`. On an error it prints `PRE_EXISTING_CHANGES invalid: <error>; write the verify gate as one plain command` to stderr and exits 2. The default text (`default_pre_existing`, `render_dispatch.py:148`) passes unchanged, and so does a hand-written form with absolute paths and `--repo <dir>` (the FR-024 fifth case).
- FR-024: Tests in `skills/workerbee/tests/test_template_revision.py`: issue #108's span (`cd /tmp && python3 pre_dispatch_snapshot.py verify <snapshot>`) exits 2; `python3 pre_dispatch_snapshot.py verify <snapshot>` with no directory exits 2; `python3 x.py verify <snapshot>` exits 2; the default text passes; `/usr/bin/python3 /abs/skills/workerbee/scripts/pre_dispatch_snapshot.py verify /abs/run/snapshot.json --repo /abs --allow a.py` passes.

## Clarifications

### Session 2026-10-23

Answered by the Executive (fable), who wrote this spec.

- Q1 (#104): lint with the checkout's scripts, or only annotate `detail=install-stale`? → A: lint with the checkout (FR-001, FR-002) and say which copy judged (FR-003).
  Reason: the issue's first proposal removes the false red; the second only labels it. A Lead editing the lint in the checkout needs its own report judged by the edited rule, or spec runs like 024 go red for the whole run.

- Q2 (#104): probe the checkout by name or by content? → A: by content, two regular files (FR-001).
  Reason: a directory named `agents_Inc` is not evidence. Two probe files that only this repository carries are. Symlinks are excluded so a delegate cannot point the probe at a planted copy.

- Q3 (#85/#87): exempt negative phrasing, or make the screen path-based? → A: path-based (FR-006).
  Reason: negation detection is fragile ("do not read .env, except to check it exists" is both). The gate screen is already path-based and has not produced a false positive. A bare word is not a location; the D51 screen is about locations.

- Q4 (#85/#87): keep `.env` in the text screen? → A: keep it as a path or read-verb token only (FR-006).
  Reason: `.env` is the most common deny-list word in CONSTRAINTS. `cat .env` and `~/x/.env` remain the cases the screen exists to catch.

- Q5 (#105): screen the direct path, or document the exemption? → A: screen it (FR-011).
  Reason: the issue states the case. The direct path runs with the operator's credentials, so it needs the screen at least as much as the broker.

- Q6 (#106): refuse, exclude the run directory from the compare, or warn? → A: refuse with exit 2 (FR-015).
  Reason: excluding it hides a delegate's writes into that directory; a warning leaves the later resume red. The rule already exists for `.scratch` in `default_parent`; this applies the same rule to the explicit flag.

- Q7 (#107): warning plus `snapshot=CHANGED`, or a red outcome? → A: red with reason `gate-wrote` (FR-018).
  Reason: the outcome is what scripts and supervisors read (QUICKREF: trust a green gate). A green outcome over a dirty repo is the false claim the stress run flagged. A gate that must write belongs in the delegate's TASK, not in GATES.

- Q8 (#108): keep a name check, or parse the command? → A: parse with `shlex` and match argv positions (FR-022).
  Reason: the issue asks for exactly that. A positional match is small to test and leaves no room for a decorated string.

### Analyze resolutions, 2026-10-23

Executive (fable) rulings on `analyze.md` F1 to F13. Each edit is already applied above.

- F1 accepted: checkout scripts are copied into the private trust folder at launch and hashed; every load reads the trusted copy (FR-002, FR-004, FR-005). A delegate that edits the checkout's lint during its turn is still judged by the launch-time copy.
- F2 accepted: `_HOME_CRED` needs a further non-glob segment; bare home dirs and globs in prose pass; `~/.local/bin/` and `~/.local/share/agents-inc/` exempt (FR-006 item 1, FR-007, FR-008).
- F3 accepted: `.env` matches only after a path separator, `~`, or as the first argument of a read verb inside a backticked span (FR-006 item 3).
- F4 accepted: the four #95 assertions flip to acceptance; `print access_token` is accepted, consistent with Q3 (FR-008, FR-010).
- F5 accepted: probe needs five files; every load site and the shipped verifier copy use the trusted directory (FR-001, FR-002).
- F6 accepted: `gate-wrote` outranks `gate-failed`; `TAMPERED` and `ERROR:` on the second verify keep their own reasons (FR-018, FR-021).
- F7 accepted: Scope lists the ten files.
- F8 accepted: `test_dispatch_failloud.py:191` literal updated; SC-001 runs that module (FR-003, SC-001).
- F9 accepted: a `run.json` without the keys resumes as `installed` (FR-002).
- F10 accepted: `_exit_code` anchor `:969` (FR-020). Other anchors stay.
- F11 accepted: case 3 replaced with the issue #87 text (FR-008).
- F12 accepted: slot-text token may end in punctuation (FR-006 item 2, FR-007).
- F13 accepted: FR-023 names the hand-written form, not a wrapper-filled one.

## Success criteria

- SC-001: `python3 -m unittest tests.test_dispatch_cli tests.test_dispatch_slot_screens tests.test_dispatch_contract tests.test_dispatch_resume tests.test_dispatch_broker tests.test_dispatch_failloud tests.test_dispatch_snapshot_trust skills.workerbee.tests.test_template_revision` exits 0 and prints `OK`.
- SC-002: `python3 -m unittest discover -s tests -p 'test_*.py'` reports no new failure beyond the pre-existing order-dependent `tests.test_ollama_adapter.TestUnloadUnconfirmed.test_unload_unconfirmed_exit4`.
- SC-003: `grep -n 'lint=' agents_inc/install/dispatch.py`, `grep -n 'gate-wrote' agents_inc/install/dispatch.py`, `grep -n 'def verify_gate_ok' skills/workerbee/scripts/render_dispatch.py` each print at least one line.
- SC-004: `CHANGELOG.md` `## [Unreleased]` carries lines ending `(#104)`, `(#85, #87)`, `(#105)`, `(#106)`, `(#107)`, `(#108)`.
- SC-005: the dispatch scope gate (`pre_dispatch_snapshot.py verify <run snapshot> --allow <FILES IN SCOPE>...`) exits 0.

## Assumptions

- The fake-delegate test harness in `tests/test_dispatch_cli.py` (a `claude` stub on PATH) is reused for FR-005, FR-017 and FR-021.
- `docs/DECISIONS.md` gets one entry recording Q3, Q7 and Q1 as rulings; its number continues the existing sequence.
