<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Feature Specification: Provider Health Freshness and Key Name Consistency

**Feature Branch**: `development` (spec dir `specs/014-provider-health-env-names`; no feature branch, per dispatch)
**Created**: 2026-10-01
**Status**: Draft
**Input**: Batch B of the 2026-10-01 Supervisor dispatch: issue #22. Mistral stale health-cache TTL/refresh plus correcting the two docs that cite the stale state; OpenRouter key env-name mismatch `OPEN_ROUTER_API_KEY` versus `OPENROUTER_API_KEY`; OpenRouter Zero-Data-Retention (ZDR) is an account setting, so no repo change beyond documentation. Never read or print key values; existence and name checks only.

## Background (verified 2026-10-01 against HEAD `dd48471` unless noted)

- `~/.codex-bridge/backend-health.json` has two writers with two key schemas:
  - `skills/codex-bridge/scripts/route.sh` keys entries by backend name (`mistral`, `openrouter`, `gemini-flash`, ...) (`route.sh:76-84`). The governed job runner calls `route.sh report` after each job (`skills/codex-bridge/scripts/agent_runner.py:603-608`, `:681`, `:702`).
  - `agents_inc/free_health.py` keys entries by provider and model (`free_health.py:18`). The standalone wrappers report there (`mask.sh:55`, `oask.sh:75`). This file is peer-owned this session and has uncommitted peer edits.
- On an `ok` result, `route.sh report` sets `status` to `ok` and clears `cooldown_until` but leaves `last_error` in place (`route.sh:231-251`). An entry can therefore read `status: ok` next to a 401 `last_error` indefinitely.
- A standalone `mask.sh` call never refreshes the backend-keyed `mistral` entry, because it reports through `free_health` [inferred from the two call sites above]. **Correction (plan phase, 2026-10-01, analyze B1):** `free_health.backend_key` returns the bare provider name for `mistral` and `openrouter` (`free_health.py:119-124`), so both writers share those entries; the real gap is that `free_health`'s `ok` path neither clears `last_error` nor sets `last_checked` (`free_health.py:156-172`).
- Issue #22's 2026-09-24 comment (live file, read by a prior session) shows `mistral.last_checked` 2026-09-10 and `last_error` "API key expired on 2026-09-08" while `status` is `ok`; 5 of 8 entries were more than 10 days old.
- Docs citing the stale state: `docs/DECISIONS.md:60` and `:98` ("mistral key EXPIRED"), and `specs/010-persistent-exec-session/analyze-2026-09-12b.md:191` (a dated probe record from 2026-09-12).
- Key names: `agents_inc/keys.py:22` and `workerbees/keys.py:27` build the variable name as `f"{provider.upper()}_API_KEY"`, which gives `OPENROUTER_API_KEY`. The operator's `~/Projects/.env` holds `OPEN_ROUTER_API_KEY` (issue #22 comment, name count only). `available_providers` strips `_API_KEY` and lowercases, so that line is listed as provider `open_router`, not `openrouter` (`agents_inc/keys.py:29-44`). `oask.sh:93` already accepts both names.
- Key store paths disagree: `agents_inc/keys.py:6` uses `~/.config/agents_inc/.env`; `workerbees/keys.py:11`, `AGENTS.md:55`, `README.md:356`, and `docs/DECISIONS.md:86` name `~/.config/workerbees/.env`.
- ZDR: the account-level OpenRouter privacy setting excludes `:free` endpoints that are not ZDR-compliant (issue #22 body; #38 comment, 2026-09-23). It is changed at `openrouter.ai/settings/privacy`, outside the repo.

## Clarifications

### Session 2026-10-01

Answered by the operator through the Executive, 2026-10-01.

- Q: What is the scope of the stale-health fix? → A: Clear `last_error` on an `ok` report, add a stale marker to `route.sh status`, and make `mask.sh` and `oask.sh` also report to `route.sh` so the backend entry refreshes. Edits to `agents_inc/free_health.py` stay `BLOCKED-PEER`.
- Q: What is the freshness window? → A: 24 hours.
- Q: How are the stale docs corrected? → A: Append dated correction notes; do not rewrite the existing text.
- Q: How is the key-store path mismatch handled? → A: In scope. Read both `~/.config/agents_inc/.env` and `~/.config/workerbees/.env`; write only the documented `~/.config/workerbees/.env`.
- Q: Where does the ZDR note go? → A: `docs/HOW-IT-WORKS.md`, provider and keys section.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Health status does not lie about old errors (Priority: P1)

The operator or a router reads backend health. A backend that succeeded after an error shows no stale error. An entry not refreshed within the freshness window shows as stale, not as healthy and not as failed.

**Why this priority**: A stale 401 next to `status: ok` sent two documents and one analyze report the wrong way.

**Independent Test**: In a fake HOME, write a health file with an old `last_checked` and a `last_error`, run `route.sh report mistral ok`, then `route.sh status`; assert the error is cleared and old entries render as stale.

**Acceptance Scenarios**:

1. **Given** an entry with `last_error` set, **When** `route.sh report <backend> ok` runs, **Then** `last_error` is cleared and `last_checked` is now.
2. **Given** an entry whose `last_checked` is older than the freshness window, **When** `route.sh status` runs, **Then** the row shows a stale marker and the age.
3. **Given** a stale entry, **When** `route.sh pick` runs, **Then** the stale entry does not block selection (stale is not a failure).

---

### User Story 2 - The OpenRouter key is found under either name (Priority: P1)

A key stored as `OPEN_ROUTER_API_KEY` or `OPENROUTER_API_KEY` makes provider `openrouter` available in both Python key modules, matching the shell wrapper.

**Why this priority**: Today the Python path misses the operator's actual key name.

**Independent Test**: Temporary env files containing fake sentinel values under each name; assert `available_providers` returns `openrouter` and never `open_router`, and that no value is printed.

**Acceptance Scenarios**:

1. **Given** an env file with only `OPEN_ROUTER_API_KEY=<fake>`, **When** `available_providers` runs, **Then** the result contains `openrouter` and not `open_router`.
2. **Given** an env file with only `OPENROUTER_API_KEY=<fake>`, **When** `available_providers` runs, **Then** the result contains `openrouter`.
3. **Given** either case, **When** the test captures stdout and stderr, **Then** the fake value does not appear.

---

### User Story 3 - Docs tell the truth about Mistral and ZDR (Priority: P2)

A reader of the decisions log learns that the 2026-09 Mistral 401 was a pre-rotation state, and that OpenRouter ZDR is an account setting with a known trade-off.

**Independent Test**: grep the corrected docs for the correction note and the ZDR note.

**Acceptance Scenarios**:

1. **Given** `docs/DECISIONS.md`, **When** read, **Then** a dated correction states the Mistral key was rotated and later calls succeeded, as an appended dated note; the original text stays.
2. **Given** the provider documentation, **When** read, **Then** it states that ZDR is an OpenRouter account setting, that it excludes many `:free` endpoints, and that relaxing it lets free providers train on inputs (per #19), with no repo change.

### Edge Cases

- Health file absent: `route.sh` initializes it as today.
- Entry with `last_checked: null`: render as `unknown`, not stale and not ok.
- Clock skew (future `last_checked`): treat as fresh.
- Both key names present with different values: prefer `OPENROUTER_API_KEY`; never print either.
- `free_health.py` entries are out of reach this batch (peer-owned); any change there is planned as `BLOCKED-PEER`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `route.sh report <backend> ok` MUST clear `last_error` and set `last_checked`.
- **FR-002**: `route.sh status` MUST mark entries older than the freshness window as stale and show their age; `null` timestamps show as unknown. Window: 24 hours.
- **FR-003**: `route.sh pick` MUST NOT treat a stale or unknown entry as failed.
- **FR-003a**: `mask.sh` and `oask.sh` MUST also report each call outcome to `route.sh report` for their backend (`mistral`, `openrouter`), in addition to their existing `free_health` report, without changing their own exit codes. Any change needed in `agents_inc/free_health.py` is `BLOCKED-PEER`.
- **FR-004**: Both `agents_inc/keys.py` and `workerbees/keys.py` MUST map `OPEN_ROUTER_API_KEY` and `OPENROUTER_API_KEY` to provider `openrouter`. `setup_key` MUST keep writing the canonical `OPENROUTER_API_KEY`.
- **FR-005**: No code path, test, or log MUST read a key value into output; tests use fake sentinel values in temporary files only. No test touches the real `.env`.
- **FR-006**: `docs/DECISIONS.md` and `specs/010-persistent-exec-session/analyze-2026-09-12b.md` MUST carry the Mistral correction, as appended dated correction notes; existing text is not rewritten.
- **FR-007**: The ZDR finding MUST be documented as an account setting with the #19 training trade-off, in `docs/HOW-IT-WORKS.md` (provider and keys section). `docs/BENCH.md` is peer-owned and is not edited.
- **FR-008**: The key-store path mismatch (`~/.config/agents_inc/.env` versus `~/.config/workerbees/.env`) MUST be resolved in both key modules: `available_providers` reads both paths, and `setup_key` writes only the documented `~/.config/workerbees/.env`.
- **FR-009**: Implement MUST NOT write to `~/.codex-bridge/**`, any `.env`, or any key file. Tests use a fake HOME.

### Key Entities

- **Health entry**: backend name, status, cooldown, last error, last checked.
- **Freshness window**: maximum age of `last_checked` before an entry is stale.
- **Key alias map**: provider name to accepted environment variable names.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After one `ok` report, 0 entries show a non-empty `last_error` in the fake-HOME test.
- **SC-002**: 100% of fixture entries older than the window render as stale; 0 fresh entries do.
- **SC-003**: Both key spellings yield `openrouter` in both modules (4 of 4 cases); `open_router` appears in 0 cases.
- **SC-004**: 0 occurrences of fake key values in captured test output.
- **SC-005**: The unit suite shows only the known pre-existing failure.

## Assumptions

- No live re-probe of providers is run; freshness is shown, not refreshed by new calls.
- The OpenRouter ZDR setting stays as the operator set it; this spec does not recommend changing it.
- The `oask.sh` shell fallback accepts both key names only when reading `~/Projects/.env` (`oask.sh:93`, first match wins); the process environment and `agents_inc/free_caps.py:166` read only `OPEN_ROUTER_API_KEY`. Those paths are out of scope for this batch and recorded as a follow-up (analyze B6, B8).
- Unifying the two health-file schemas is out of scope; it touches the peer-owned `free_health.py`.
- `.gitignore:224-232` ignores any path containing `key`, `secret`, `token`, or `credential` (except three allow-listed key modules). New files for this batch must avoid those words in their names, or they silently never reach git (this spec dir was renamed from `014-provider-health-keys` for that reason).
