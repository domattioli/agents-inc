# Tasks: spec 020

Implementer: Sonnet (Workhorse). Repo: agents_Inc, branch `feat/batch2-42-45-49-55`. Write each test first, then make it pass. Standard library only at runtime. Line numbers come from `b5cd279`. Re-run `grep -n` before each edit (spec A7).

## Plan

- Order: US4, US1, US3, US2 (spec Scope). Run the full suite after each story; do not start the next story while the suite is red.
- US4 (#42): one branch edit in `free_health.py`, plus two doc edits in `skills/codex-bridge/SKILL.md`.
- US1 (#45): three optional slots with a pure derivation function (`derive_chain`) and a `--model` flag on the renderer, one template line, one lint rule, two small tables added to `dispatch_rungs.py`, and SKILL.md text. Fixtures need no new keys (operator amendment 2026-10-09).
- US3 (#49): a new row builder in `host_ledger.py`, one call in `dispatch.run()`, and `--run-id` on `ledger append`.
- US2 (#55): a new `datafiles.py` module; move 4 call sites; package data in `pyproject.toml` and `MANIFEST.in`; `--source` becomes optional; D55; RELEASING.md and README text. This is the riskiest story, so it goes last. If the wheel test (T19) shows that setuptools rejects the `package-dir` mapping, use the committed-copy fallback (FR-008) and say so in the report.
- Shared file: both US1 and US3 touch `dispatch.py` (US1 only through test fixtures). US2 moves its first lines. Hence the order.

## US4 (#42)

- T1: In `tests/test_free_health.py` (pytest-only module, hermetic style, `:143`), add a test that an `error` report followed by an `ok` report leaves `last_error` None and `last_checked == t.isoformat()` (SC-005). Run it with `python3 -m pytest tests/test_free_health.py -q`; `unittest discover` does not execute this file.
- T2: Make T1 pass: `agents_inc/free_health.py` `ok` branch (`:190-193`) (FR-023).
- T3: In `skills/codex-bridge/SKILL.md`, rewrite the install paragraph (`:260-263`, FR-020). Widen the alias sentence (`:290`) and add the `@openrouter` lexicon row (FR-021). Check: `bash skills/codex-bridge/tests/at_route.smoke.sh` exits 0, and the two SC-005 greps pass (FR-022).

## US1 (#45)

- T4: In `tests/test_dispatch_contract.py`, add class `TestReportingChain` with the five lint cases of SC-001 and the `ALIAS_VENDOR` agreement test. In `skills/workerbee/tests/test_template_revision.py`, add the seven `derive_chain` cases of SC-001 (temp `HOME`; write the settings file under `<tmp>/.config/agents-inc/settings.json`) and the REPORTING CHAIN line check on the example render.
- T5: In `skills/workerbee/scripts/dispatch_rungs.py`, add `LADDER` and `ALIAS_VENDOR` (FR-001a). In `skills/workerbee/slots.md`, add the 3 optional slot rows to the slot table (`:63-80`) and the `REPORTING CHAIN:` template line right after `ROLE:` (`:17`) (FR-001, FR-002). In `render_dispatch.py`: add `derive_chain(slots, model, settings)` beside `default_fan_out` (`:32-47`), a `--model` flag in the arg loop (`:85`), a settings reader for `Path(os.environ.get("HOME", "~")).expanduser() / ".config/agents-inc/settings.json"` that returns `{}` on any error, the call after the `NOTES` default (`:137-139`), and the stderr `chain:` line. Do not add the slots to `required_slots` (`:128-132`). In `agents_inc/install/dispatch.py` `render()` (`:77-89`), accept and pass `model` (`sys.argv` gains `--model`, `model`); update its caller at `:498`.
- T6: In `check_dispatch_prompt.py` `check()`, add the `reporting-chain-inverted` rule (FR-003, FR-004). Aliases rank through `MODEL_RUNG` (imported at `:87` from `dispatch_rungs.py:14-18`); do not copy it. Role words (`operator` 5, `executive` 4, `supervisor`/`orchestrator`/`cos` 3, `workhorse` 2, `grunt` 1) are a small dict beside the rule, since `dispatch_rungs.py` holds aliases only. Strip trailing punctuation from names; skip unknown names; `X reports to X` is a no-op.
- T7: Fixtures stay as they are (FR-006, A1). Run `skills/workerbee/tests/test_template_revision.py` and `tests/test_dispatch_header.py` after T5 and confirm the derived line renders for `example_slots.json` (ROLE names `haiku`, so the default chain is `haiku < sonnet < fable`) and for `FULL_SLOTS` (`tests/test_dispatch_header.py:21`, ROLE names `haiku` and `opus`; the first `MODEL_RUNG` hit in ROLE text wins, so document that order in `derive_chain`).
- T7b: Add the `chain` verb to `agents-inc models` (`cli.py:135`, `models_cmd.run` at `:147`): listing, `key=alias` writes through `model_sync._update_settings` (`:246-249`) after validating against `MODEL_RUNG` plus `CoS`/`operator`, `--clear` (FR-001b). Tests under a temp `HOME` (SC-000). Then add the SC-000 dry-run cases to `tests/test_dispatch_cli.py` (pattern `test_dry_run` at `:102`; `prompt.md` is written in the run dir).
- T8: Edit `skills/workerbee/SKILL.md`: add the Step 1 relay paragraph (FR-005), update prompt-shape item 2 (FR-006), and add a Version History entry (FR-007). In `README.md`, under `## 2. Asking for work in plain language` (`:43-47`), add one sentence after the tenet at `:45` saying the reporting chain is derived from the ladder and `agents-inc models chain` sets a default.

## US3 (#49)

- T9: In `tests/test_host_ledger.py`, add the four SC-004 ledger cases.
- T10: Add `dispatch_run_row` and `record_dispatch_run` to `host_ledger.py` (FR-015). Change `--node-id` from required to "at least one of `--node-id` or `--run-id`" (exit 2 when both are missing), and set node_id = run_id when only `--run-id` is given (FR-017).
- T11: In `tests/test_dispatch_cli.py`, add a non-dry run with the launch patched that leaves one `dispatched` row. Add `--dry-run` and lint-refusal cases that leave no row (SC-004). Use a temp state dir, never the real HOME.
- T12: In `dispatch.run()`, call `record_dispatch_run` once, after the dry-run return (`:527-530`) and before `launch` (`:533`). Import it lazily (`from .. import host_ledger`, pattern `cli.py:150`); state comes from `_paths().state` (`_paths` import pattern `:300`). A write failure goes into `run.json` as `ledger_error` and never changes the outcome (FR-016). Do not change the status line: `tests/test_dispatch_cli.py:19-20` `STATUS_RE` pins it and the run id it prints is the node id (FR-018).
- T13: Add the `ledger pending` and `ledger append --run-id` commands to `skills/workerbee/SKILL.md` (FR-019).

## US2 (#55)

- T14: Create `tests/test_datafiles.py` with the three SC-002 cases.
- T15: Create `agents_inc/datafiles.py` with `repo_file` and `repo_root` (FR-009).
- T16: Move the 4 call sites to `datafiles`: `schema.py:6`, `doctor.py:147`, `dispatch.py:22-23` and `mcp_broker.py:22`. Leave `models_cmd.py` and `bench.py` alone (FR-010). `tests/test_schema_lazy.py` must still pass.
- T17: In `pyproject.toml`, replace `[tool.setuptools.packages.find]` (`:48-49`) with the explicit `packages` list from FR-008 (`find` cannot see a `package-dir` mapped package; proven by a dry build), add `[tool.setuptools.package-dir]` with the two mappings, add `package-data` entries `"agents_inc._skills" = ["workerbee/**/*", "codex-bridge/**/*"]` and `"agents_inc._docs" = ["SCHEMA-3NF.md"]`, add `[tool.setuptools.exclude-package-data] "agents_inc._skills" = ["*/tests/**"]`, and rewrite the comment at `:51-52`. Add `recursive-include skills/workerbee *`, `recursive-include skills/codex-bridge *` and `include docs/governance/SCHEMA-3NF.md` to `MANIFEST.in` after `:43` (`recursive-include agents_inc *.json`), below the generated release-ignore block that ends at `:40` (`# <<< release-ignore:end`, commit `7573b7e`); never edit inside that block (FR-008). `tests/test_packaging.py:94` (`_package_data_matches`, `:39-52`) ignores keys that are not directories under `agents_inc/`, so it still passes.
- T18: In `tests/test_install_cli.py`, add `install` with no `--source` (patch `datafiles.repo_file` to a temp tree) and assert `paths.state / "source-checkout"` reads `packaged`. In `cli.py`, make `--source` optional for `install` (`:128`) and `repair` (`:132`), add the temporary source-tree build before `stage_bundle` (`:65`), and guard the `source-checkout` write at `:86` (sentinel `packaged` when `args.source` is None) (FR-011). In `tests/test_install_doctor.py`, add: with record `packaged` and an installed hook equal to `repo_file("skills/codex-bridge/scripts/at_route.sh")`, `check_install` returns no `WB_HOOK_DRIFT*` warning and no `INSTALL_STALE`; with the hook changed, `WB_HOOK_DRIFT`. In `agents_inc/install/doctor.py` `_hook_drift` (`:25-34`), branch on the `packaged` record (FR-011a).
- T19: In `tests/test_packaging.py`, extend the build tree copy at `:139-141` (it copies only `agents_inc` and `workerbees`) with `skills/workerbee`, `skills/codex-bridge` and `docs/governance/SCHEMA-3NF.md`, keeping the same `ignore` patterns; then assert the 4 files from SC-002 under `agents_inc/_skills/...` and `agents_inc/_docs/SCHEMA-3NF.md` in the wheel namelist. The `tops` assertion at `:156` still holds (both data packages live under `agents_inc/`). The `:94` test must still pass. If the mapping fails, switch to the fallback (FR-008).
- T20: Add D55 to `docs/DECISIONS.md` (FR-012). Rewrite `docs/RELEASING.md:7-47` and update `README.md:427` (FR-013). Do not bump the version (FR-014).

## Final

- T21: `python3 -m unittest discover -s tests -p 'test_*.py'` passes, `python3 -m pytest tests/test_free_health.py -q` passes, and the rendered example prints `COMPLIANT` (SC-006). For SC-003, build the wheel in a temp dir and put the `unzip -l` excerpt in the report. No commit, no push.
- FR-024 (DomI task marks and closing #42) is the supervisor's job after merge. Not the implementer's.
