# Implementation Plan: Reliability fixes for 0.6.4

**Spec**: `specs/036-reliability-fixes-0-6-4/spec.md` | **Date**: 2026-11-09 | **Branch**: `development`

Stdlib only. Dev and full-suite runs follow AGENTS.md: docker images for the stress run; unit tests may also run locally with a fake HOME. Every file:line below was read on 2026-11-09 unless tagged [inferred].

## Story 1 (P1): update hint by install kind; loud repair failure (#155 a+b)

### 1a Update hint

- Target: `agents_inc/install/update_check.py:59-70` [verified]. `notice()` builds one fixed string at lines 68-70.
- Callers: `cli.py:328-330` (doctor `UPDATE:` line) [verified] and `hook.py:63` (session start) [verified]. Both pass only `paths.state`; keep that signature and derive the rest from it.
- Add `install_kind(state: Path, launcher: Path) -> tuple[str, str | None]`. Return the kind and, for `checkout`, the path.
  - Read `state / "source-checkout"`. A path value means `checkout` (written at `cli.py:168` [verified]). `packaged` means pip or pipx. Missing or unreadable means `unknown`.
  - For `packaged`, read the first line of the launcher (`~/.local/bin/agents-inc`, `paths.py:36` [verified]) only when `_is_own_console_script` holds (`cli.py:20-26` [verified]). Interpreter line containing `/pipx/venvs/` gives `pipx`. Otherwise an interpreter inside a venv (a `pyvenv.cfg` beside its `bin/` parent) gives `pip-venv`, else `pip-user`. [inferred: layout facts, to be pinned by tests with fixture scripts]
  - Add an optional `launcher` keyword to `notice()`. Default: `Path(state).parents[1] / "bin/agents-inc"`, which maps `~/.local/state/agents-inc` to `~/.local/bin/agents-inc` (`paths.py:36,39` [verified]). Callers keep passing `paths.state` only; tests pass `launcher` explicitly.
- Command table:
  - `pipx`: `pipx upgrade agents-inc && agents-inc repair`
  - `pip-user`: `python3 -m pip install --user -U agents-inc && agents-inc repair`; if the interpreter is externally managed, use the `unknown` text instead.
  - `pip-venv`: `<interpreter> -m pip install -U agents-inc && agents-inc repair`
  - `checkout`: `git -C <path> pull && agents-inc repair --source <path>`
  - `unknown`: `pipx upgrade agents-inc && agents-inc repair` (pipx) or `git pull && agents-inc repair --source <checkout>` (checkout); add "plain pip fails on an externally managed Python (PEP 668)".
- Keep the version text and CHANGELOG link (line 70) unchanged.
- Risk: misdetection gives a wrong command. Mitigation: unknown is the fallback for every read error; the CHANGELOG link stays.

### 1b Repair failure

- Today: `_install` rolls back on any exception and re-raises (`cli.py:181-183` [verified]); `main` prints `str(exc)` and returns 1 (`cli.py:377` [verified]); a sandboxed `os.replace` in `write_file` (`host_wiring.py:183` [verified]) raises `PermissionError` errno 1.
- Change in `install()` (`cli.py:130-138` [verified]): wrap the `_install` call. On exception: print `FAIL: agents-inc <install|repair>: <error>` to stderr (for `OSError` include `exc.filename` and `exc.strerror`); write the marker; return 1. Add a second line for errno 1 (EPERM) and 13 (EACCES): "the file is not writable from here; inside the Claude Code sandbox run `agents-inc repair` from a normal terminal".
- `install()` needs the command name: `main` sets `args.command` (`cli.py:279,364` [verified]); read it with `getattr(args, "command", "install")`.
- Marker: `paths.state / "repair-failed.json"`, JSON `{"command", "at", "error"}`, mode 0600. Write in its own try; on `OSError` print `FAIL: could not record the failure for doctor: <error>`.
- On success, remove the marker after `journal.commit()` (`cli.py:175` [verified]) with `unlink(missing_ok=True)` inside a try.
- Doctor: in `check_install` (`doctor.py:126-171` [verified]) add `if (paths.state / "repair-failed.json").exists(): codes.append("WB_REPAIR_FAILED")` before the live probe (`if live_model and not codes`, `doctor.py:161-162`), so a failed repair does not trigger a live model ping. The CLI then prints the code instead of `READY` (`cli.py:320` [verified]) and exits 1 (`cli.py:331` [verified]).
- Session-start text: `hook.session_start` reports doctor state [inferred from the SessionStart text "doctor: READY"]; it inherits the code if it calls `check_install`. T5 checks that.
- Risk: a stale marker from an old failure blocks READY. Mitigation: the doctor line names the fix: repair. A `WB_REPAIR_FAILED` hint line in doctor text mode says "last repair failed at <time>: <error>; run agents-inc repair".

## Story 2 (P2): luna tools-on argv (#160)

- Target: `build_codex_argv` tools-on branch `runtime.py:489-502` [verified]. Append `["-c", "include_collaboration_mode_instructions=false"]` for every Codex rung on the tools-on branch (clarified 2026-11-09); no model test needed.
- Resume inherits it: `build_codex_resume_argv` copies every flag from `build_codex_argv` (`runtime.py:523-537` [verified]).
- Do not touch `HOST_TOOLS_ARGS` (`runtime.py:364-365` [verified]); the host-tools branch never takes the tools-on path (`runtime.py:473-474` [verified]), so no duplicate.
- Red reason: the empty-reply check is in `run_codex` (`runtime.py:747-750` [verified]); the count helpers `thread_rollout` and `rui_calls` are at `runtime.py:794-822` [verified] and today run only for host-tools threads (`runtime.py:845-859` [verified]).
  - In `run_codex`, when the reply is empty: if `json_mode` and a thread id was parsed (`runtime.py:685` [verified]), count `len(rui_calls(thread_rollout(tid)))`; else `unknown`. Write `agents-inc run: codex <slug> returned an empty reply (request_user_input calls: <n|unknown>)`.
  - `tid` is local to the `try` block (`runtime.py:685`); hoist it to `tid = None` before the block.
  - Dispatch uses JSON mode for non-Lead runs: `dispatch.py:804-806` passes `thread_out=None if lead_dir else thread` [verified].
  - A resumed run has no new thread id in the parse; use `resume_thread` as the id.
- Risk (from review): the host-tools path already sets the setting and still logged 426 `request_user_input` calls in 15 runs (`runtime.py:363` [verified]). The setting may not stop luna. Closure rule: spec SC-004. If live runs still end empty, the next step is a separate issue (for example a stripped catalog for tools-on luna), not part of 0.6.4.
- Existing test to keep green: `tests/test_codex_tool_access.py:482-487` asserts no `model_instructions_file`/`model_catalog_json` on plain luna [verified]; the new flag does not match those prefixes.

## Story 3 (P3): compound guard false denies (#152 F1-F4)

- Targets in `agents_inc/install/hook.py` [verified]: `_HIDING_HEADS` line 114; `_judge` lines 239-270; fail-closed head check lines 247-249; `sh -c` rule lines 262-263.
- Change 1 (F1, F2): split `_HIDING_HEADS` into `_KEYWORD_HEADS = {"{", "}", "if", "then", "do", "else", "elif", "while", "until"}` and `_OPAQUE_HEADS = {"alias", "source", "."}`. In `_judge`, after assignments are stripped, pop leading keyword heads (loop, since `then {` can stack), then judge the rest as a normal command. Keep the expansion check (line 248) after the pop, so `do $x dispatch` still denies. Opaque heads keep the fail-closed return.
- Change 2 (F3): `eval` head. `_unquote` each remaining word (the helper `sh -c` uses at `hook.py:263`), join with spaces, `_parse` the string, and `_judge` it recursively with `could_hide=True`. A parse `ValueError` returns `"eval string"` (deny). An executed dispatch inside returns `"eval string"` (deny). Otherwise continue.
- Change 3 (F4): `sh -c`. Take the word after the `-c` option as the script, `_unquote` it, `_parse` and `_judge` it like eval. Any executed dispatch/run/luna inside an eval or `-c` string denies, compound or not (keeps `test_hook_compound_dispatch.py:98-99`). Keep the quoted-launcher deny that D72 lists (`'agents-inc'` inside the string; test line 127 [verified]): if the script word, before unquoting, holds a quote directly around `agents-inc`, deny as today. Words after the script are positional parameters, not code; ignore them.
- `for`: `for w in agents-inc dispatch` is already a non-dispatch command (head `for`); only the following `do` triggered the deny. Change 1 fixes it.
- Not changed: wrapper handling (lines 250-261), substitution recursion (lines 266-269), `_dispatch_shape` (lines 272-292), the raw fallback (lines 280-282).
- Out of scope: B1-B8 bypasses (D72 known limits, `docs/DECISIONS.md:734` [verified]); `case`, functions, arrays.
- Risk: a relaxed head lets a real dispatch through. Mitigation: every existing deny test (`tests/test_hook_compound_dispatch.py:38-142` [verified]) stays, plus a paired executable deny for each F-shape. Recursion depth is bounded by the string length; an exception still fails open (`hook.py:304-305` [verified]) as D72 records.
- Canon: add an amendment line under D72 in `docs/DECISIONS.md` (after line 734) saying the for/if/eval/bash -c false deny is fixed in 0.6.4, other limits unchanged.

## Test plan

- New unit tests (fake HOME, temp dirs, no network, no real model):
  - `tests/test_update_check.py`: one test per install kind; fixture launcher scripts with pipx and user interpreter lines; checkout record; missing record. Assert `pip install -U` absent for `pipx`, `checkout`, `unknown`.
  - `tests/test_install_cli.py`: patch `host_wiring.write_file`'s `os.replace` (or `install_host_wiring`) to raise `PermissionError(1, "Operation not permitted", "<path>")`; call `cli.main(["repair", "--source", <repo>])` with HOME patched; assert rc 1, `FAIL: agents-inc repair` on stderr, marker present; then `check_install` has `WB_REPAIR_FAILED`; then a successful repair removes the marker.
  - `tests/test_install_runtime.py`: argv test for tools-on luna (flag once), tools-on sol, terra, astra (flag once), resume luna (flag once); empty-reply test with a fake rollout holding 3 `request_user_input` function_call lines (format per `runtime.py:812-821` [verified]) and the `unknown` case.
  - `tests/test_hook_compound_dispatch.py`: F1-F4 allow/deny pairs from spec US3.
- Full suite: `python3 -m unittest discover -s tests -p 'test_*.py'`.
- Docker stress run (AGENTS.md), operator or supervisor with the sandbox off: `docker run --rm --network none -v "$PWD:/src:ro" -v "$PWD/docker/stress_check.sh:/stress.sh:ro" agents-inc-ci bash /stress.sh`.
- Live evidence for #160 per SC-004, on the operator's Mac after release.
