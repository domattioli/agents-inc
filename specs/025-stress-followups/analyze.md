<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-10-23 skill=speckit-analyze repo=agents_Inc session=f26522 -->
# Analyze: spec 025

Artifacts: `spec.md` (107 lines), `plan.md`, `tasks.md`, `checklists/requirements.md`. Constitution: `.specify/memory/constitution.md` (P0 to P10, `ratified: false`, so MUST violations report as WARN per `constitution.md:64`). Mode: adversarial, read-only for spec, plan and tasks. Code was not read for correctness; cited anchors were checked to exist with `Grep`/`Read` on 2026-10-23. `check-prerequisites.sh` was not run (no `bash` grant). Note on P3: the author of plan.md and tasks.md also ran this pass (dispatch FAN_OUT 0); the Executive answers the findings.

Line references: `spec.md:N` is the spec line; plan and tasks lines are from the files as written in this run.

## Findings

### F1. HIGH (security; constitution P3 WARN). The checkout scripts that judge a delegate are writable by that delegate.

- Conflict: `spec.md:17` (FR-001) and `spec.md:18` (FR-002) load `check_dispatch_prompt.py` and `pre_dispatch_snapshot.py` from `<cwd>/skills/workerbee/scripts` at verify time. `spec.md:75` (Q2) says symlinks are excluded "so a delegate cannot point the probe at a planted copy". A delegate running under `acceptEdits` in that cwd can edit the regular file instead: make `check_report` return `[]`, or make `verify` print clean. `_verify` runs `lint_report` and then `snapshot` after the delegate exits (`dispatch.py:768`, `:795`), and `_load` runs the file in the dispatcher's own process (`dispatch.py:46-50`), with the operator's credentials. The snapshot compare that would show the edit is itself the edited script. `spec.md:20` (FR-004) carries the same path to broker Workers.
- Against: constitution P3 (`constitution.md:32`, no self-graded gates) and P4 (`constitution.md:36`, fail closed). Plan records it as a WARN (`plan.md:32`, Complexity Tracking). Tasks T013, T015 (`tasks.md:58`, `:60`) implement the spec as written.
- Proposed edit, spec.md FR-002: add "At `run()`, after `scripts_dir` returns `checkout`, dispatch copies the four scripts into the run's trust folder (`_trust_path`), records each file's sha256 in `trust.json`, and every later load, including resume and broker Workers, reads the trusted copy. A copy that fails its hash makes `snap` `TAMPERED`." Add a FR-005 test: the fake delegate edits the checkout's `check_dispatch_prompt.py` during its turn, and the report is still judged by the launch-time copy. tasks.md: new task after T015 for the copy and hash, and a T013 case for the edit.

### F2. HIGH. FR-006 keeps `_HOME_CRED` unchanged, but FR-008 requires the screen to accept text that `_HOME_CRED` matches.

- Conflict: `spec.md:27` (FR-006, item `_HOME_CRED (unchanged)`) against `spec.md:29` (FR-008 case 1, "the full rendered Worker boilerplate"). The rendered SCOPE BOILERPLATE says `No writes to ~/.claude/**, ~/.codex/**, ~/.local/**, ~/.codex-bridge/**` (`skills/workerbee/header.md:15`). `_HOME_CRED` (`dispatch.py:1392`) matches `~/.claude` (not followed by `/skills/`), `~/.codex`, `~/.local` and `~/.codex-bridge`. FR-008 case 1 cannot pass while FR-006 holds.
- Same root, wider effect: `spec.md:37` (FR-011) puts this screen on the direct path. Executive slots often name home paths as deny-list prose or as tools: this dispatch's own CONSTRAINTS say `no ~/.claude writes`, and `AGENTS.md` cites `~/.local/bin/agents-inc` and `~/.local/share/agents-inc/current/skills/workerbee/QUICKREF.md`. All would be refused with exit 3 once FR-011 lands. The broker already has this behavior; the direct path does not.
- Artifacts affected: plan US2 "Known conflicts" (`plan.md:93`), plan US3 note (`plan.md:107`), tasks T004, T005, T006 (`tasks.md:29`, `:30`, `:36`).
- Proposed edit, spec.md FR-006 item 1: "`_HOME_CRED` followed by a further path segment that is not a glob (`~/.ssh/id_rsa`, `~/.codex/auth.json`, `~/.claude/.credentials.json`); a bare home directory (`~/.claude`) or a glob (`~/.claude/**`) in prose does not match. `~/.local/bin/` and `~/.local/share/agents-inc/` are exempt, like `~/.claude/skills/`." Add to FR-008: `No writes to ~/.claude/**, ~/.codex/**, ~/.local/**` and `run ~/.local/bin/agents-inc doctor` as accepted cases, and keep `cat ~/.claude/.credentials.json` (`tests/test_dispatch_slot_screens.py:125`) as refused.

### F3. HIGH. FR-006 refuses `open .env`; FR-008 requires `Never open .env.` to pass. "Within the same line" has two readings.

- Conflict: `spec.md:27` (FR-006) matches `.env` "when it follows ... a read verb (`cat`, `read`, `print`, `open`, ...) within the same line". `spec.md:29` (FR-008 case 2) requires `No writes to credentials, .env, or key files. Never open .env.` to be accepted. `open .env` is a read verb followed by `.env` under either reading.
- Ambiguity: "follows a read verb within the same line" can mean the verb is the word directly before the token, or any earlier word on the line. Under the second reading, any CONSTRAINTS line such as "do not read or modify .env" is refused, which is the #85 complaint. Plan picked the first reading (`plan.md` US2 item 3) and flagged it.
- Q3 (`spec.md:77-78`) rules out negation detection, so "never" cannot be the escape.
- Artifacts affected: tasks T004, T005 (`tasks.md:29-30`); checklist CHK008, CHK015.
- Proposed edit, spec.md FR-006: replace the read-verb clause with "a `.env` or `.env.<suffix>` token that follows a path separator or `~`, or that is the first argument of a read verb inside a backticked command span (`` `cat .env` ``)". Prose sentences then never match on `.env` alone; commands still do. FR-008 case 2 passes; `cat .env` in backticks and `~/x/.env` stay refused (Q4, `spec.md:80-81`). Add one refused case to FR-008's sibling FR-007: `` run `cat .env` ``.

### F4. MEDIUM. Existing #95 tests flip and the spec does not say they should.

- Conflict: `spec.md:27` (FR-006) drops bare `token` and `api_key`; `spec.md:31` (FR-010) adds tests but names no removals. `tests/test_dispatch_slot_screens.py:109-110` asserts bare `token` is refused (`test_slot_text_screen_keeps_the_broad_pattern`); `:123-124` asserts `show the token` and `print access_token` are refused (#95 true positives); `:133-135` asserts `no .env reads` matches `'.env'`. All four turn false under FR-006.
- Proposed edit, spec.md FR-010: "Tests at `tests/test_dispatch_slot_screens.py:109-110`, `:123-124` and `:133-135` change to expect acceptance; `test_credential_hit_names_slot` uses `cat ~/.ssh/id_rsa` instead." If the Executive wants `print access_token` to stay refused, FR-006 needs a read-verb-plus-secret-word rule, which reopens Q3. tasks T004 (`tasks.md:29`) already lists the three sites and waits on this ruling.

### F5. MEDIUM. FR-002 names three load sites; the run loads workerbee scripts from at least seven. The probe checks two files and the run needs four.

- Gap: `spec.md:18` (FR-002) names `_load`, `snapshot`, `lint_report`. Other sites that load from `SCRIPTS` (`dispatch.py:32`): `lint_prompt` (`:111-114`), `render` (`:87-89`), `parse_fan_out` (`:811-814`), `_run_gates` `DANGER_RE` (`:839`), `_validate_fields` `dispatch_rungs` (`:1562`), and the verifier copy shipped into the run dir (`:1195-1197`). If only the named three switch, the prompt is linted and rendered by one copy and the report by another, and the delegate's SNAPSHOT VERIFIER line points at the installed script while the dispatcher verifies with the checkout's.
- Gap: `spec.md:17` (FR-001) probes `check_dispatch_prompt.py` and `dispatch.py`; a checkout that has those two but lacks `render_dispatch.py`, `dispatch_rungs.py` or `pre_dispatch_snapshot.py` would crash in `_load`.
- Artifacts affected: plan US1 (`plan.md:76`), tasks T013, T015 (`tasks.md:58`, `:60`); checklist CHK003, CHK023.
- Proposed edit, spec.md FR-002: "Every workerbee script the run loads or ships, including the verifier copy written to the run directory, comes from `spec["scripts_dir"]`." FR-001: "the probe also requires `render_dispatch.py`, `dispatch_rungs.py` and `pre_dispatch_snapshot.py` as regular files in the same directory."

### F6. MEDIUM. FR-018 does not order `gate-wrote` against `gate-failed`, and does not cover a second verify that is `TAMPERED` or `ERROR:`.

- Gap: `spec.md:52` (FR-018) defines the case "second verify reports changes that the first did not". A gate can exit with the wrong code and also write (reason today: `gate-failed`, `dispatch.py:863-864`). A gate can also rewrite `snapshot.json` when the run dir sits under `<cwd>/.scratch`, which makes the second verify `TAMPERED` (`dispatch.py:785-786`), not `CHANGED`. The spec gives no outcome for either.
- Plan picked `gate-wrote` over `gate-failed` (`plan.md:125`) and is silent on `TAMPERED`.
- Proposed edit, spec.md FR-018: add "`gate-wrote` takes precedence over `gate-failed`. A second verify of `TAMPERED` or `ERROR:` sets `snap` to that value with reason `snapshot-tampered` or `snapshot-error`." tasks T011 (`tasks.md:51`): add a test for a gate that writes and exits 1.

### F7. MEDIUM. The Scope paragraph lists fewer files than the stories edit; an implement dispatch built from Scope fails its scope gate.

- Conflict: `spec.md:9` says the stories touch `agents_inc/install/dispatch.py`, `skills/workerbee/scripts/render_dispatch.py` and `CHANGELOG.md`. `spec.md:40` (FR-014) edits `skills/workerbee/slots.md`; `spec.md:106` (Assumptions) edits `docs/DECISIONS.md`; FR-005, FR-010, FR-013, FR-017, FR-021, FR-024 edit four test files; F8 adds `tests/test_dispatch_failloud.py`.
- Proposed edit, spec.md Scope: list the ten files in `plan.md` Project Structure, so the implement dispatch's FILES IN SCOPE and SC-005 allow list are copied from one place.

### F8. MEDIUM. FR-003's new status-line token breaks a test that SC-001 does not run.

- Gap: `spec.md:19` (FR-003) updates `STATUS_RE` in `tests/test_dispatch_cli.py` only. `tests/test_dispatch_failloud.py:191` asserts the literal `rc=-1 report=none snapshot=none outcome=red reason=launch-failed detail=`; inserting `lint=...` after `report=none` breaks it. `spec.md:97` (SC-001) does not run `tests.test_dispatch_failloud`, so the break shows only in SC-002's full run.
- Proposed edit: FR-003 adds "and the literal at `tests/test_dispatch_failloud.py:191`"; SC-001 adds `tests.test_dispatch_failloud`. tasks T014 and T019 (`tasks.md:59`, `:67`) already include both.

### F9. LOW. Resume of a `run.json` written before this change has no `scripts_dir`, and FR-002 forbids deriving one.

- Gap: `spec.md:18` "On resume the recorded value wins; it is never re-derived." No value exists for older runs.
- Proposed edit, spec.md FR-002: "A `run.json` without the keys resumes as `installed`." Plan already assumes this (`plan.md:78`).

### F10. LOW. Anchor drift in the spec.

- `spec.md:54` (FR-020) cites `_exit_code` at `dispatch.py:965`; it is at `dispatch.py:969`. `spec.md:50` cites `_finish` at `:982-990`; the def is at `:980`, and the cited range is its body. `spec.md:35` and `:39` cite `_validate_fields` at `:1575`; the def is at `:1548`, and `:1575` is the screen line inside it. The others checked match: `:32`, `:46`, `:53`, `:139`, `:919`, `:1106`, `:1394`, `:1397`, `:1582`, `:1737`, `:1972`, `render_dispatch.py:148`, `:357`, `slots.md:99`.
- Proposed edit: FR-020 `:965` to `:969`. The rest are acceptable as written.

### F11. LOW. FR-008 case 3 does not exercise the change.

- `spec.md:29` case 3, `stop idle Supabase containers; test with stub binaries and a fake HOME`, contains none of today's `CREDENTIAL_RE` triggers (`dispatch.py:1395`: no `.env`, `token`, `credentials`, `api_key`, `.pem`, `.key`, `$HOME`) [inferred from the regex, not run]. It passes before and after, so it is a guard only.
- Proposed edit: keep it as a guard and say so, or replace it with the slot text from issue #85 that was refused.

### F12. LOW. The key-file token rule misses trailing punctuation.

- `spec.md:27` reuses the `GATE_CREDENTIAL_RE` token rule, whose lookahead is `(?=$|[\s/'"])` (`dispatch.py:1398`). In prose, `cat id_rsa,` or `print server.pem.` ends in punctuation and does not match.
- Proposed edit, FR-006: "for slot text, the token may also end in `.`, `,`, `;`, `:` or `)`". Plan flags this at `plan.md:90`.

### F13. LOW. FR-023's "wrapper-filled form with `--repo <cwd>`" does not occur at render time.

- `spec.md:62` (FR-023) says the wrapper-filled form with an absolute snapshot path and `--repo <cwd>` passes. `default_pre_existing` emits no `--repo` (`render_dispatch.py:153`); dispatch renders (`dispatch.py:1176`) before it injects the snapshot path (`dispatch.py:1193`), and `inject_snapshot` only replaces the placeholder (`dispatch.py:122-127`). The render check never sees that form.
- Proposed edit, FR-023: "and so does a hand-written form with absolute paths and `--repo <dir>`" (the FR-024 case 5 test already covers it).

## Coverage

FR-001 to FR-024 each map to at least one task (table at the end of tasks.md). SC-001 to SC-005 map to T018 and T019. No task lacks an FR or SC except T001 (baseline), T017 (spec Assumptions) and T020 (move to DomI). Unmapped requirement: none.

## Metrics

24 FR, 5 SC, 20 tasks, coverage 100%. Findings: 13. CRITICAL 0, HIGH 3 (F1, F2, F3), MEDIUM 5 (F4 to F8), LOW 5 (F9 to F13). Constitution: one WARN (P3, F1).

## Next actions

Resolve F1, F2, F3 before implement: each one changes which tests T004, T005, T013 and T015 write. F4 to F8 are spec wording edits that tasks.md already anticipates. F9 to F13 can be accepted as written.

## Cycle 2

Date 2026-10-23. Input: spec.md with the Executive's "Analyze resolutions, 2026-10-23" (F1 to F13 accepted, edits applied to FR-001 to FR-010, FR-018, FR-020, FR-021, FR-023, Scope, SC-001). plan.md, tasks.md and checklists/requirements.md were updated in this cycle to match. Same author and checker as cycle 1 (FAN_OUT 0); the Executive reviews.

Re-check of each ruling against plan and tasks:

- F1, F5, F9 (trusted copy, five-file probe, every load site, legacy resume): plan US1 and tasks T013, T015, T016 carry the copy into `_trust_path(run_id)/workerbee/scripts` (templates in `workerbee/`, trust.json in the folder root), the sha256 map in the trust record, the threaded `scripts` argument (`render`, `lint_prompt`, `lint_report`, `parse_fan_out`, `_run_gates`, `_grants_from_slots`, `lead_roster`, `_validate_fields`, verifier copy), the mid-turn edit test, and `installed` for a `run.json` without the keys. Consistent.
- F2, F3, F4, F11, F12 (screen rules, flipped #95 tests): plan US2 and tasks T004, T005 match FR-006 to FR-010 case for case. Consistent.
- F6, F10 (gate-wrote precedence, anchor): plan US5 and tasks T011, T012. Consistent.
- F7, F8 (ten-file scope, failloud literal, SC-001): plan Project Structure lists the ten files; T014 and T019 match. Consistent.
- F13: T002 and plan US6 use the hand-written absolute form. Consistent.

Remaining findings (none blocks implementation; no ruling is unimplementable as written):

### C2-1. LOW. An existing render test uses a snapshot path that FR-022 rejects.

`skills/workerbee/tests/test_template_revision.py` `Issue92Test.test_plain_verify_command_renders` writes `verify /x/s.json`. FR-022 requires argv[3] to be `<snapshot>` or a path ending `snapshot.json`, so that test turns red. Resolution inside scope: the fixture path becomes `/x/snapshot.json` (T002). The test's intent (#92: a plain command renders) is unchanged.

### C2-2. LOW. The FR-004 test cannot live in `tests/test_dispatch_broker.py`.

Cycle-1 T016 put the Worker-inheritance test in `tests/test_dispatch_broker.py`, which is not in the spec Scope list. Resolution: the test goes in `tests/test_dispatch_cli.py` (T016 updated); it drives `_in_worker_scope` directly.

### C2-3. LOW. "On resume the recorded values win" read together with a delegate-writable `run.json`.

FR-002 says the recorded `scripts_dir` wins on resume. `run.json` sits in the run directory, which a delegate can write when the run directory is under `<cwd>/.scratch`. Reading the recorded path as-is would let a delegate point the resumed run at a copy it controls. Plan reading: for `checkout`, the recorded `scripts_dir` must equal `_trust_path(<run dir name>)/workerbee/scripts` (the 022 rule: trust is located by the run directory name, never by `run.json`), and a different value is red `snapshot-tampered` before launch. The recorded value still wins over a fresh probe. Executive may confirm.

Result: no CRITICAL, HIGH or MEDIUM finding; three LOW notes, each resolved in plan and tasks. Proceeding to implement.

### C2-4. LOW (found during implement, T002). FR-023's trigger misses an FR-024 case.

FR-023 applies `verify_gate_ok` to spans "that contain `pre_dispatch_snapshot.py`". FR-024 case 3, `python3 x.py verify <snapshot>`, contains no such name, so under FR-023 as written it is never checked and renders exit 0, while FR-024 requires exit 2. Implemented reading: the check also runs on any span in PRE_EXISTING_CHANGES that has `verify` as a whitespace-separated word. This is a superset of FR-023 and satisfies all five FR-024 cases. Executive may confirm or narrow.

### C2-5. HIGH (found during implement, T019). An out-of-scope broker test asserts the bare-word refusals FR-006 removes.

`tests/test_dispatch_broker.py:420` `test_credential_seeking_refused` expects `credential-seeking` for eight texts. Under FR-006 four of them now pass, as FR-006 and Q3 require: `print the .env file` (prose `.env`, FR-006 item 3), `find the API_KEY` and `show the token` (bare words), and `ls ~/.config` (a home directory with no further segment, FR-006 item 1). The other four (`~/.claude/.credentials.json`, `$HOME/.ssh/id_rsa`, `/Users/x/.codex/auth.json`, `server.pem`) are still refused. FR-010 lists only `tests/test_dispatch_slot_screens.py` assertions to flip, and `tests/test_dispatch_broker.py` is not in Scope, so the test was not edited and SC-001 fails on it. Needed ruling: add `tests/test_dispatch_broker.py` to scope and move the four texts to an accepted list (or replace them with located forms such as `print ~/x/.env`). Other deviations: a tampered trusted copy reports `none`, not the plan's earlier `UNCHECKED` (the status line allows only COMPLIANT, NON-COMPLIANT and none); `resume_cap` still loads `dispatch_rungs` from the installed bundle (FR-002 does not list it; it reads only the rung table).
