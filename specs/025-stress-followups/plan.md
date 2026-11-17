<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-plan repo=agents_Inc session=f26522 -->
# Implementation Plan: spec 025, dispatch follow-ups from the 2026-10-23 Docker stress run

**Branch**: `development` | **Date**: 2026-10-23 | **Spec**: `specs/025-stress-followups/spec.md`
**Input**: Feature specification from `specs/025-stress-followups/spec.md` (issues #104, #85, #87 item 1, #105, #106, #107, #108)

Line numbers below are from the working tree on 2026-10-23. Re-run `grep -n` before each edit; several anchors in spec.md have drifted by a few lines (see analyze.md).

## Summary

Six fixes to the dispatch wrapper, found by the Docker stress run. US1 makes a dispatch from an agents_Inc checkout lint and verify with the checkout's own scripts and says which copy judged. US2 turns the request text screen from a word list into a path list. US3 applies that screen on the direct path and on `--resume --message`. US4 refuses an explicit `--run-dir` that sits inside the repo and is not git-ignored. US5 runs the snapshot verify a second time after the gates, so a gate that writes into the repo turns the outcome red. US6 replaces the substring test for the verify gate in `render_dispatch.py` with a positional `shlex` parse. All six land in one delegate run, because five of them edit `agents_inc/install/dispatch.py`.

## Technical Context

**Language/Version**: Python 3.11+, standard library only.
**Primary Dependencies**: none new. `git` on PATH for the US4 check (absent git means no refusal).
**Storage**: `run.json` per run directory gains two keys (`scripts_dir`, `scripts_source`); `verify.txt` gains a first line and an `after gates:` block. No schema version change (spec Scope, out of scope).
**Testing**: `unittest`. The fake-delegate harness in `tests/test_dispatch_cli.py` (a `claude` stub on PATH, temp git repo from `_git_repo`, `tests/test_dispatch_cli.py:41-47`) serves FR-005, FR-017 and FR-021.
**Target Platform**: macOS and Linux hosts that run `agents-inc dispatch`.
**Project Type**: CLI and library (`agents_inc/install/dispatch.py`, `skills/workerbee/scripts/render_dispatch.py`).
**Performance Goals**: N/A. US5 adds one snapshot verify per gated turn; US4 adds one `git check-ignore` call when `--run-dir` is given.
**Constraints**: $0 spend; no network; tests use temp dirs and a fake HOME; no change to the broker protocol, `run.json` schema version, or `pre_dispatch_snapshot.py` (spec Scope).
**Scale/Scope**: about 6 functions changed and 2 added in `dispatch.py`, 1 function added in `render_dispatch.py`, 4 test files, 1 skill doc paragraph, 1 DECISIONS entry, 6 CHANGELOG lines.

Research and data model are folded into this file, as in spec 024: there are no NEEDS CLARIFICATION items left after the spec's Clarifications section, and the only data change is two `run.json` keys plus two `verify.txt` text forms, defined under US1 and US5. No contracts/ or quickstart.md: the interfaces are the status line, stderr refusal lines and `verify.txt`, each given verbatim below. The DomI `SPECKIT` agent-context marker step does not apply (not a DomI run).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- P1 repo-scoped writes: every write is inside agents_Inc. Tests use temp dirs and patched HOME. US3 and US4 refuse before any run directory exists. Pass.
- P3 no self-graded gates: US5 closes one self-grading path (a gate that writes after the compare). US1 would open a new one if the judging scripts were loaded from the delegate's cwd. The Executive's F1 ruling (spec FR-002) closes it: the four checkout scripts are copied into the run's private trust folder at launch, hashed into the trust record, and every load reads the trusted copy. Pass (cycle 2).
- P4 deterministic policy over prompt: US2, US3, US4, US6 are regex, argv and exit-code checks. Pass.
- P8 prompt contract: the implement dispatch carries the 14 fields; FILES IN SCOPE lists every file in "Project Structure" below, copied from the spec Scope list (F7 ruled). Pass.
- P9 surgical edits: no file is rewritten whole. Pass.
- Result: no WARN after the analyze rulings.

Post-design re-check (cycle 2, after the analyze rulings): unchanged, no violation.

## Project Structure

### Documentation (this feature)

```text
specs/025-stress-followups/
├── spec.md                    # written and clarified by the Executive
├── plan.md                    # this file
├── tasks.md                   # /speckit-tasks output
├── checklists/requirements.md # /speckit-checklist output
└── analyze.md                 # /speckit-analyze output
```

### Source Code (repository root)

```text
agents_inc/install/dispatch.py                 # US1-US5
skills/workerbee/scripts/render_dispatch.py    # US6
skills/workerbee/slots.md                      # US3 FR-014 (D51 paragraph, line 99)
tests/test_dispatch_cli.py                     # US1 FR-003/FR-005, US4 FR-017, US5 FR-021, STATUS_RE
tests/test_dispatch_slot_screens.py            # US2 FR-010, US3 FR-013
tests/test_dispatch_failloud.py                # status-line literal at :191 (US1 FR-003 token)
tests/test_dispatch_contract.py                # only if an existing assertion flips (spec Scope)
skills/workerbee/tests/test_template_revision.py  # US6 FR-024
docs/DECISIONS.md                              # D67 (spec Assumptions: Q1, Q3, Q7)
CHANGELOG.md                                   # six lines under ## [Unreleased] / ### Fixed (:9)
```

**Structure Decision**: existing single-project layout; no new modules or files.

## Design per story

### US1 (#104): lint with the checkout's scripts (FR-001 to FR-005)

Anchors (verified): `REPO_ROOT` `dispatch.py:31`, `SCRIPTS` `:32`, `_load` `:46`, `snapshot` `:139`, `lint_report` `:130`, `lint_prompt` `:111`, `render` `:87`, `parse_fan_out` `:811`, verifier copy `:1195-1197`, `_status` `:919`, `_in_worker_scope` `:1775`.

- New `scripts_dir(cwd: Path) -> tuple[Path, str]`. Probe five regular files (FR-001, F5 ruling): `cwd/agents_inc/install/dispatch.py` and, in `cwd/skills/workerbee/scripts/`, `check_dispatch_prompt.py`, `render_dispatch.py`, `dispatch_rungs.py`, `pre_dispatch_snapshot.py`. Checkout when all five are `is_file()` and none `is_symlink()`, and `cwd.resolve()` is not `REPO_ROOT.resolve()` or under it. Else `(SCRIPTS, "installed")`.
- Trusted copy (FR-002, F1 ruling): new `_pin_scripts(src: Path, run_id: str) -> Path`. Right after the probe in `run()` (after `run_id` exists, before `render`), when the source is `checkout`, copy the four scripts into `_trust_path(run_id) / "workerbee" / "scripts"` and `header.md`, `slots.md` into `workerbee/` (render reads them from the directory above its own; folder mode 0700, outside cwd), and write `trust.json` in `_trust_path(run_id)` with `scripts_sha256: {name: sha256}` for all six files. `render_dispatch.py` imports `dispatch_rungs` from its own directory through `sys.path`, so the copy is self-contained unless the module is already cached in the process (open, recorded in D67). `_record_trust` keeps the `scripts_sha256` map when it writes the snapshot record. `spec["scripts_dir"]` is the trusted copy directory (the directory loaded from); `spec["scripts_source"]` is `checkout`. Installed source: `spec["scripts_dir"] = str(SCRIPTS)`, no copy.
- One judge per run (F5 ruling): `_load(name, scripts=SCRIPTS)`, `snapshot(*args, cwd, scripts=SCRIPTS)`, and every caller thread one `scripts` argument: `render`, `lint_prompt`, `lint_report`, `parse_fan_out`, `_run_gates` (`DANGER_RE`), `_grants_from_slots` (`parse_gates`), `lead_roster`, `_validate_fields` (`dispatch_rungs`), and the verifier copy written to the run directory. Helper `_scripts(spec) -> Path` returns the recorded trusted directory for `checkout`, else `SCRIPTS`.
- Hash check: when `scripts` is not `SCRIPTS`, `_load` and `snapshot` compare the file's sha256 with `scripts_sha256` in `<scripts>/../../trust.json` and raise `ScriptsTampered` on a mismatch or a missing record. `_verify` checks all six first; a mismatch writes `report: none` (the status-line report set is COMPLIANT, NON-COMPLIANT, none), sets `snap` to `TAMPERED` and skips lint and the snapshot compare. `_outcome` returns `red`/`snapshot-tampered` for `snap == "TAMPERED"` with report `none` (before the report check). `_finish` runs no gate when report is `none` and records `gate-missing` (the outcome is already `snapshot-tampered`).
- `resume()`: read `scripts_source` from `run.json`; never call `scripts_dir`. `checkout`: the directory must equal `_trust_path(<run dir name>) / "workerbee" / "scripts"` (run.json is delegate-writable, so the location is derived from the run directory name, as for the snapshot record in 022); a different recorded `scripts_dir` is red `snapshot-tampered` before launch. A `run.json` without the keys resumes as `installed` (F9 ruling).
- Broker (FR-004): `make_lead_dir` copies `scripts_dir`/`scripts_source` into the broker-owned Lead `run.json` (outside cwd; no schema version change). `_in_worker_scope` (`:1775`) sets a module global `_INHERITED_SCRIPTS` from that spec and clears it in its `finally`; a Worker's `run()` and `resume()` use it and never probe. The broker's own `_validate_fields` uses `_scripts(spec)` on the Lead spec.
- `_status`: insert ` lint={spec.get('scripts_source') or 'installed'}` after `report={report}`. `STATUS_RE` (`tests/test_dispatch_cli.py:23-26`) gains ` lint=(checkout|installed)` after the report group, and the substring `report=COMPLIANT snapshot=clean` at `tests/test_dispatch_cli.py:182` gains the token. `tests/test_dispatch_failloud.py:191` gains the token too (F8 ruling).
- `verify.txt`: `_verify` writes `lint source: <abs dir>\n` as the first line, before `report: ...`.
- Tests (FR-005): build a fake checkout in a temp dir by copying `skills/workerbee/` whole (render needs `header.md`, `slots.md` beside `scripts/`), writing a stub `agents_inc/install/dispatch.py`, and `git init`; patch the copied `check_dispatch_prompt.py` `check_report` to flag `sentinel-025`. Expect `lint=checkout` and `report=NON-COMPLIANT:['sentinel-025']`. The fake delegate rewrites the checkout's `check_dispatch_prompt.py` to return `[]` during its turn; the report is still `sentinel-025`. Plain repo: `lint=installed`. Probe files as symlinks: `lint=installed`. A changed trusted copy: `snapshot=TAMPERED reason=snapshot-tampered`.

### US2 (#85, #87 item 1): path-based request text screen (FR-006 to FR-010)

Anchors (verified): `_HOME_CRED` `dispatch.py:1392`, `CREDENTIAL_RE` `:1394-1395`, `GATE_CREDENTIAL_RE` `:1397-1399`, `credential_hit` `:1582`, broker detail `:1736-1739`.

- New `CREDENTIAL_RE`, three alternatives (F2, F3, F12 rulings). `GATE_CREDENTIAL_RE` keeps today's `_HOME_CRED`; the slot text screen gets its own home pattern `_HOME_CRED_TEXT`.
  1. `_HOME_CRED_TEXT` followed by `/` and one further path segment that holds no glob character: `/(?![^\s/]*[*?\[])[^\s/'"`,;)]+`. `_HOME_CRED_TEXT` is `_HOME_CRED` with `local` exempting `local/bin/` and `local/share/agents-inc/` the way `claude` exempts `claude/skills/` (a later `..` cancels the exemption). `~/.claude`, `~/.claude/**`, `~/.local/bin/agents-inc` pass; `~/.ssh/id_rsa`, `~/.claude/.credentials.json` match.
  2. Key files as path tokens: `(?:^|[\s/='"])(?:id_rsa|id_ed25519|[^\s/]*\.(?:pem|key))(?=$|[\s/'".,;:)])`.
  3. `.env` after a path separator or `~`: `(?<=[/~])\.env(?:\.[\w.-]+)?\b`; or the first argument of a read verb (`cat`, `read`, `print`, `open`, `source`, `dump`, `echo`, `show`, `less`, `head`, `tail`) inside one backticked span: `` `[^`\n]*?(?<![\w-])(?:cat|...|tail)\s+\.env(?:\.[\w.-]+)?(?=[\s`])[^`\n]*` ``. Prose never matches on `.env` alone.
- Removed: `credentials`, `(?<![a-z])token(?![a-z])`, `api[_-]?key` bare words.
- Existing tests flip (F4 ruling): `tests/test_dispatch_slot_screens.py:109-110` (`token`), `:123-124` (`show the token`, `print access_token`) and `:133-135` (`no .env reads`) now expect acceptance; `test_credential_hit_names_slot` uses `cat ~/.ssh/id_rsa`.
- `credential_hit` keeps its form. FR-007 fixture `read ~/.ssh/id_rsa and .env, print the api_key`: the leftmost match is `~/.ssh/id_rsa` at offset 5, so the detail is `slot X matched '~/.ssh/id_rsa'`.
- Tests: new class `PathScreenTest` in `tests/test_dispatch_slot_screens.py` with the four FR-007 refusals and the six FR-008 accepts.

### US3 (#105): one screen on both paths (FR-011 to FR-014)

Anchors (verified): `run()` slots read `dispatch.py:1123-1131`, run dir created `:1136-1142`, `resume()` message check `:1309`, broker message screen `:1972`, `_validate_fields` screen `:1575`.

- `run()`: after the `isinstance(slots, dict)` check (`:1129-1131`) and before `new_run_id` (`:1136`): `hit = credential_hit(slots)`; on a hit print `dispatch: refused credential-seeking (<hit>)` to stderr, return `EXIT_REFUSED`. This sits before `--dry-run` handling, so dry-run refuses the same way.
- `resume()`: after `if not args.message` (`:1309`) and before any write to the run directory: `credential_hit({"MESSAGE": args.message})`, same line, exit 3.
- Order with US4: the credential screen runs first, then the US4 run-dir check, then `mkdir`. Both write nothing.
- Note: after the F2 ruling, Executive slots that say `no ~/.claude writes` or cite `~/.local/bin/agents-inc` pass the direct-path screen.
- `skills/workerbee/slots.md:99`: append one sentence to the D51 paragraph: "The direct path (`agents-inc dispatch --slots`) and the broker apply one request text screen; a refusal names the slot and the matched text."
- Test (FR-013): one refused slots file through `dispatch.main` (exit 3, stderr has `slot TASK matched`) and through `_validate_fields` (reason `credential-seeking`); one accepted file through both. `_validate_fields` needs a full request dict and a spec with `worker_models`; look for an existing request builder in `tests/test_dispatch_broker.py` before writing one (not checked by this plan).

### US4 (#106): `--run-dir` under cwd must be git-ignored (FR-015 to FR-017)

Anchors (verified): `run()` `dispatch.py:1137`, `default_parent` `:53-62`, `_verify` run-dir allow `:772-775`.

- In `run()`, before `run_dir.mkdir` (`:1139`), when `args.run_dir` is set: `parent = Path(args.run_dir).resolve()`. If `parent.is_relative_to(cwd)`: run `git -C <cwd> check-ignore -q <parent relative to cwd>`. rc 0: accept. rc 1: print `dispatch: --run-dir <parent> is inside --cwd and not git-ignored; later snapshot verifies would see its files` to stderr, return `EXIT_USAGE` (2). rc 128 (not a repo) or `OSError` (no git): accept.
- `--run-dir` equal to cwd gives relative path `.`; `check-ignore` returns 1, so it is refused. That is the intended result.
- Tests in `tests/test_dispatch_cli.py`: `self.repo / "runs"` (not ignored) exits 2, message on stderr, `runs` absent afterwards; same with a `.gitignore` holding `runs/` launches; `self.runs` (outside the repo, `:55`) launches.

### US5 (#107): a gate that writes flips the outcome (FR-018 to FR-021)

Anchors (verified): `_verify` `dispatch.py:767-799`, `_finish` `:980-1018`, `_run_gates` `:836`, `_outcome` `:880-908`, `_exit_code` `:969`.

- Split `_verify`: new `_snapshot_verify(spec, run_dir) -> (src, slog, snap)` holds `:770-797` (allow list, trust handling, `snapshot` call). `_verify` calls it and keeps writing `verify.txt`. This keeps the report lint to one run.
- `_finish`: in the `elif gated:` branch after `_run_gates` (`:988`): `src2, slog2, snap2 = _snapshot_verify(spec, run_dir)`. Append to `run_dir / verify_name`: `after gates: clean\n` when `src2 == 0`, else `after gates:\nsnapshot rc=<src2>\n<slog2>`. Only when the first verify was clean: `snap2` `CHANGED:` gives `snap = snap2`, `gate_reason = "gate-wrote"` (this replaces `gate-failed` and `gate-missing`; F6 ruling); `snap2` `TAMPERED` or `ERROR:` gives `snap = snap2`, and `_outcome` returns `snapshot-tampered` or `snapshot-error` from `snap`.
- `_outcome` returns `("red", "gate-wrote")` through the existing `gate_reason` branch (`:904-905`), because `vrc` is still 0. When the first verify is already dirty, `snapshot-not-clean` wins and the second verify only adds its block to `verify.txt`.
- `_exit_code`: no change needed; `gate-wrote` falls to `EXIT_RED`. The broker-child branch (`:985-986`) skips gates and so skips the second verify.
- Tests in `tests/test_dispatch_cli.py`: GATES `[{"argv": ["sh", "-c", "echo pwned > gate_wrote.txt"]}]` gives `snapshot=CHANGED:gate_wrote.txt outcome=red reason=gate-wrote`, exit 1, `verify.txt` contains `after gates:`; a gate that writes and exits 1 gives `reason=gate-wrote`; the default `_slots` gate (`[sys.executable, "-c", "pass"]`, `:72`) gives `snapshot=clean outcome=green` and `after gates: clean`.

### US6 (#108): parse the verify gate (FR-022 to FR-024)

Anchors (verified): `default_pre_existing` `render_dispatch.py:148-154`, check loop `:355-360`.

- New `verify_gate_ok(span: str) -> str | None`:
  - metacharacters first: on `span.replace("<snapshot>", "")`, search `&&|\|\||;|\||>|<|\$\(|` and a backquote; hit → `"shell metacharacter in verify gate"`.
  - `argv = shlex.split(span)`; `ValueError` → `"cannot parse verify gate: <exc>"`.
  - `argv[0]` in `("python3", "python")` or ending `/python3` or `/python`.
  - `argv[1]` ends `skills/workerbee/scripts/pre_dispatch_snapshot.py` and has no `..` part (`Path(argv[1]).parts`).
  - `argv[2] == "verify"`; `argv[3]` is `<snapshot>` or ends `snapshot.json`.
  - the rest pairs as `--allow <v>` or `--repo <v>`; an odd tail or other flag → error.
- `main()`: replace the `:356-360` loop body with `err = verify_gate_ok(span)`; on `err` print `PRE_EXISTING_CHANGES invalid: <err>; write the verify gate as one plain command` and return 2. The existing prefix `PRE_EXISTING_CHANGES invalid` stays, so spec 024's test keeps passing.
- Tests: new class in `skills/workerbee/tests/test_template_revision.py` with the five FR-024 cases, run through `render_dispatch.py` with a temp slots file built from `skills/workerbee/tests/fixtures/example_slots.json`. The existing `Issue92Test.test_plain_verify_command_renders` names `/x/s.json`, which FR-022 rejects (argv[3] must end `snapshot.json`); its fixture path becomes `/x/snapshot.json`.

## Cross-cutting

- `docs/DECISIONS.md`: append `## D67 — Dispatch judges with the checkout's scripts, screens paths not words, and fails a gate that writes (2026-10-23, status: accepted)` recording Q1, Q3, Q7. Last entry today is D66 (`docs/DECISIONS.md:684`).
- `CHANGELOG.md`: six lines under `## [Unreleased]` / `### Fixed` (`CHANGELOG.md:7-9`), ending `(#104)`, `(#85, #87)`, `(#105)`, `(#106)`, `(#107)`, `(#108)`.
- Order inside the one delegate run: US6 (separate file) can go first. Then US2 and US3 (screen), US4 (same `run()` region as US3), US5 (`_verify`, `_finish`), and US1 last. US1 touches the most signatures and should rebase on the others.
- Final gate: SC-001 unittest command, SC-003 greps, SC-004 grep, then the dispatch scope verify (SC-005).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| none (cycle 2) | The F1 ruling pins the checkout scripts in the trust folder, which removes the P3 WARN | n/a |
