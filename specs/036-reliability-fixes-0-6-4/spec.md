# Feature Specification: Reliability fixes for 0.6.4

**Feature Branch**: `development` (spec 036, patch bump 0.6.4)
**Created**: 2026-11-09
**Status**: Draft
**Input**: Dispatch brief: "#155 (a)+(b) update hint by install kind and a loud repair failure; #160 Codex tools-on empty reply from request_user_input; #152 false denies F1-F4 in the compound-dispatch guard."

Evidence tags: [verified] means the spec writer read the cited line on 2026-11-09; [inferred] means a conclusion drawn from read code, not run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Update hint that works, and a repair that fails loudly (Priority: P1)

An operator sees an `UPDATE:` line from `agents-inc doctor` or the session-start hook. Today the line always says `pip install -U agents-inc && agents-inc repair` (`agents_inc/install/update_check.py:68-70` [verified]). On a Homebrew or system Python that command fails with PEP 668 `externally-managed-environment`. The operator needs the command that matches how agents-inc was installed: pipx, `pip --user` or a virtual environment, or a source checkout.

The same operator then runs `agents-inc repair`. Inside the Claude Code sandbox the write of `~/.claude/settings.json` fails with `[Errno 1] Operation not permitted` at the atomic rename (`agents_inc/install/host_wiring.py:183` [verified]). Today the journal rolls the install back (`cli.py:181-183` [verified]) and `main` prints only `str(exc)` to stderr with exit 1 (`cli.py:377` [verified]). A later `agents-inc doctor` then prints `READY`, because the rolled-back install is intact (`cli.py:320` [verified], `doctor.py:171` [verified]). The operator believes the repair worked.

**Why this priority**: Every consumer sees the update hint. A wrong hint plus a silent repair failure leaves the operator on a stale bundle while doctor says READY. This is the `INSTALL_STALE` state seen at this session's start [verified: SessionStart hook text].

**Independent Test**: Unit tests with a fake HOME: (1) the notice text for each install kind; (2) a repair whose host-wiring write raises `PermissionError(1, ...)` prints a `FAIL:` line, exits non-zero, and the next `check_install` is not ready.

**Acceptance Scenarios**:

1. **Given** a pipx install, **When** a newer release exists, **Then** the notice says `pipx upgrade agents-inc && agents-inc repair` and does not say `pip install -U`.
2. **Given** a `pip --user` or virtual-environment install, **When** a newer release exists, **Then** the notice says `python3 -m pip install -U agents-inc && agents-inc repair` with the user flag only for a user install.
3. **Given** a source-checkout install (the `source-checkout` record holds a path), **When** a newer release exists, **Then** the notice says `git -C <that path> pull && agents-inc repair --source <that path>`.
4. **Given** an install kind that cannot be detected, **When** a newer release exists, **Then** the notice lists the pipx and checkout forms and names PEP 668, and never offers a bare `pip install -U` as the only option.
5. **Given** a repair that raises `OSError` while writing any file, **When** repair exits, **Then** stdout or stderr carries one line starting `FAIL: agents-inc repair` that names the path and the errno text, and the exit code is non-zero.
6. **Given** that failed repair, **When** `agents-inc doctor` runs, **Then** it prints `WB_REPAIR_FAILED` instead of `READY` and exits 1.
7. **Given** a later repair that succeeds, **When** `agents-inc doctor` runs, **Then** `WB_REPAIR_FAILED` is gone.

---

### User Story 2 - Tools-on Codex delegates stop ending with an empty reply (Priority: P2)

A supervisor dispatches luna with tools on. Codex offers `request_user_input` in its Default collaboration mode. luna calls it, Codex refuses each call, and the run ends with an empty final message. The empty reply already exits red with `agents-inc run: codex <slug> returned an empty reply` (`runtime.py:747-750` [verified]). The tools-on argv (`runtime.py:489-502` [verified]) lacks `-c include_collaboration_mode_instructions=false`. That setting is set only in `HOST_TOOLS_ARGS` (`runtime.py:364-365` [verified]), applied only through `no_tool_args(host_tools=True)` (`runtime.py:438-446` [verified]), which the tools-on branch never calls.

Known limit: the host-tools path already sets this setting and still logged 426 `request_user_input` calls in 15 macOS stress runs, 14 of 15 passing (`runtime.py:363` [verified]). So this change may reduce the calls without ending them. This story ships the setting, a clearer red reason, and a test. It closes #160 only on the evidence in SC-004.

**Why this priority**: An empty reply wastes a full delegate run and reads as a vague failure. The fix is a narrow argv change; its effect is uncertain, so it ranks below P1.

**Independent Test**: A unit test builds the tools-on argv for each Codex rung and asserts the setting is present; a second test fakes an empty reply with a rollout that holds N `request_user_input` calls and asserts the red line names N.

**Acceptance Scenarios**:

1. **Given** `build_codex_argv(..., "luna", tools=True)`, **When** the argv is built, **Then** it contains `-c` followed by `include_collaboration_mode_instructions=false` exactly once.
2. **Given** the resume path (`build_codex_resume_argv`, `runtime.py:510-537` [verified]), **When** a tools-on luna thread resumes, **Then** the same setting is present.
3. **Given** astra, sol or terra with tools on, **When** the argv is built, **Then** it also contains the setting exactly once (FR-007).
4. **Given** a tools-on luna run that exits 0 with an empty reply and a rollout with 3 `request_user_input` calls, **When** the run ends, **Then** stderr carries `returned an empty reply (request_user_input calls: 3)` and the exit code is 1.
5. **Given** the same run with no readable rollout, **When** the run ends, **Then** the red line says `request_user_input calls: unknown` and the exit code is 1.

---

### User Story 3 - The compound-dispatch guard stops denying literal mentions (Priority: P3)

An agent runs a Bash call that only mentions `agents-inc dispatch` as data inside a `for`, `if`, `eval` or `bash -c` shape, for example `for w in agents-inc dispatch; do echo "$w"; done`. The guard in `agents_inc/install/hook.py` denies it. The cause: when the call text contains `agents-inc`, `_judge` fails closed on any command head in `_HIDING_HEADS` (`hook.py:114`, `hook.py:247-249` [verified]), and the `sh -c` rule denies when any later word matches the dispatch regex, executed or not (`hook.py:262-263` [verified]). D72 records this false deny as a known limit (`docs/DECISIONS.md:734` [verified]).

The guard must deny only when the mention sits in an executable position. A plain `agents-inc dispatch` beside a shell operator must still be denied (`tests/test_hook_compound_dispatch.py:38-49` [verified]).

**Why this priority**: The false deny costs a retry, not a broken run. The guard is security-adjacent, so the change must stay small and keep every existing deny test green.

**Independent Test**: Paired tests in `tests/test_hook_compound_dispatch.py`: for each of F1-F4 one literal form that must be allowed and one executable form that must be denied.

**Acceptance Scenarios**:

1. **Given** F1 `for w in agents-inc dispatch; do echo "$w"; done`, **When** the hook judges it, **Then** it is allowed; **and given** `for w in a; do agents-inc dispatch s.json; done`, **Then** it is denied.
2. **Given** F2 `if grep -q 'agents-inc dispatch' notes.md; then echo yes; fi`, **Then** it is allowed; **and given** `if true; then agents-inc dispatch s.json; printf done; fi`, **Then** it is denied (existing test, `test_hook_compound_dispatch.py:123` [verified]).
3. **Given** F3 `eval "echo 'agents-inc dispatch'"`, **Then** it is allowed; **and given** `eval 'agents-inc dispatch s.json; printf done'`, **Then** it is denied (existing test, line 126 [verified]).
4. **Given** F4 `bash -c "grep 'agents-inc dispatch' log.txt"`, **Then** it is allowed; **and given** `bash -c "agents-inc dispatch s.json"`, **Then** it is denied (existing test, line 98 [verified]).
5. **Given** any existing test in `tests/test_hook_compound_dispatch.py`, **When** the suite runs, **Then** it passes unchanged.

---

### Edge Cases

- pipx and `pip --user` both leave a console script at `~/.local/bin/agents-inc`; `cli.py:35-38` [verified] records it as kind `external`. The two differ only in the script's interpreter line. A script that cannot be read falls back to the unknown-kind hint (scenario US1-4).
- The `source-checkout` record says `packaged` for a pip or pipx install and holds a path for a checkout install (`cli.py:168` [verified]). A missing record means unknown kind.
- The failure marker itself may not be writable. Repair must still print the `FAIL:` line; it then adds that doctor cannot record the failure.
- A repair failure that is not `OSError` (for example `RuntimeError("WB_INSTALL_UNVERIFIED: ...")`, `cli.py:193` [verified]) gets the same `FAIL:` line and marker.
- `agents-inc install` shares `_install` with repair (`cli.py:364` [verified]); the `FAIL:` line and marker apply to both.
- A luna run with `--no-tools` or `--host-tools` keeps its current argv; `HOST_TOOLS_ARGS` already carries the setting there, so it must not appear twice.
- Rollout files are read only for counting. A missing sessions directory gives `unknown`, never an exception.
- Guard: a keyword head followed by an expanded word (`do $x dispatch s.json`) must stay denied; the existing expansion rule (`hook.py:248` [verified]) covers it.
- Guard: `source`, `.` and `alias` stay fail-closed; their target text is not visible to the hook.
- Guard: an `eval` or `sh -c` string that fails to parse falls back to deny when it contains `agents-inc`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The update notice MUST pick its update command from the detected install kind: `pipx`, `pip-user`, `pip-venv`, `checkout` or `unknown`.
- **FR-002**: Install-kind detection MUST use only local reads: the `source-checkout` record, the launcher console script's first line, and the interpreter's own prefix data. It MUST NOT run pip, pipx or the network.
- **FR-003**: The notice MUST NOT offer a bare `pip install -U agents-inc` for the `unknown` kind or for an externally managed interpreter.
- **FR-004**: `agents-inc install` and `agents-inc repair` MUST print one line starting `FAIL: agents-inc repair` (or `FAIL: agents-inc install`) on any exception after rollback. The line MUST name the error text and, for `OSError`, the path. The exit code MUST be non-zero.
- **FR-005**: A failed install or repair MUST leave a marker under the state directory (`~/.local/state/agents-inc/`). A successful install or repair MUST remove it.
- **FR-006**: `check_install` MUST add code `WB_REPAIR_FAILED` while the marker exists, so doctor prints that code, not `READY`, and exits 1.
- **FR-007**: The tools-on Codex argv (luna, sol, terra, astra) MUST carry `-c include_collaboration_mode_instructions=false` once, including on resume. (Clarified 2026-11-09: all tools-on rungs.)
- **FR-009**: When a Codex run exits 0 with an empty reply, the red line MUST name the `request_user_input` call count from the thread rollout, or `unknown` when no rollout is readable. The exit code stays 1.
- **FR-010**: The compound guard MUST deny an executed `agents-inc dispatch|run|luna` after a keyword head (`{`, `}`, `if`, `then`, `do`, `else`, `elif`, `while`, `until`) and allow a command after such a head that does not execute it.
- **FR-011**: The guard MUST judge an `eval` argument string and a `sh -c`/`bash -c` string by parsing it and judging the result, so a literal mention inside it is allowed and an executed one is denied.
- **FR-012**: The guard MUST keep every deny in `tests/test_hook_compound_dispatch.py` as of 2026-11-09, and MUST NOT add bypass fixes B1-B8 or a full shell grammar.
- **FR-013**: The F1-F4 forms used in tests are the four shapes D72 names (`for`, `if`, `eval`, `bash -c`) [inferred]. (Clarified 2026-11-09: session history holds no exact F1-F4 texts; the D72 shapes are used.)
- **FR-014**: `docs/DECISIONS.md` MUST gain an amendment line under D72 that removes the `for`/`if`/`eval`/`bash -c` false-deny limit and keeps the other limits.

### Key Entities

- **Install kind**: one of `pipx`, `pip-user`, `pip-venv`, `checkout`, `unknown`; derived per call, never stored.
- **Repair-failure marker**: a small JSON file in the state directory with the command, the UTC time and the error text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the five install kinds, a unit test asserts the notice text; no kind except `pip-venv` and `pip-user` contains `pip install -U`.
- **SC-002**: A unit test with a fake HOME makes the host-wiring write raise `PermissionError(1, "Operation not permitted")`; repair returns non-zero, prints a `FAIL:` line, and the next `check_install(...).ready` is `False` with `WB_REPAIR_FAILED` in its codes.
- **SC-003**: A unit test asserts the tools-on argv holds the setting once for luna, sol, terra and astra.
- **SC-004**: #160 closes only when both hold: (a) the SC-003 test passes; (b) a live run of at least 5 tools-on luna dispatches on the operator's Mac after 0.6.4 shows zero empty-reply exits (clarified 2026-11-09). Failing (b), #160 stays open with the per-run `request_user_input` counts from FR-009 attached.
- **SC-005**: Each of F1-F4 has one allowed literal test and one denied executable test, and the full suite passes: `python3 -m unittest discover -s tests -p 'test_*.py'`.

## Assumptions

- Python 3.11+, stdlib only (AGENTS.md).
- A pipx console script's interpreter line contains `/pipx/venvs/` [inferred: pipx default layout]; a `pip --user` script's interpreter is the system or Homebrew Python.
- An externally managed interpreter has an `EXTERNALLY-MANAGED` file in `sysconfig.get_path("stdlib")` (PEP 668) [inferred].
- The doctor process runs from the installed bundle (`~/.local/share/agents-inc/current`), so the package's own `__file__` does not reveal pip versus pipx [inferred from `cli.py:30` launcher target]; detection reads the launcher instead.
- Tools-on luna runs started by `agents-inc dispatch` reach `run_codex` in JSON mode: `dispatch.py:804-806` passes `thread_out` for every non-Lead run [verified]. A plain `agents-inc run` without `--thread` is not in JSON mode and reports `unknown`.
- Out of scope: #145, #138, #73, #141, #112, #131 C/D, #87, #114, #135, #101, #31, #21, #19; #152 bypass items B1-B8; #155 items other than (a) and (b).
