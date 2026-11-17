<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-11 skill=speckit-pipeline repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Tasks: One native Agent route for every provider

All development and test runs in the docker images (`docker/Dockerfile.dev`, `docker/Dockerfile.ci`). The Mac only installs and runs live probes. [P] = parallel-safe.

## Phase 1: Setup

- [x] T001 Record the D69 luna baseline in docker: run `docker/luna_stress.sh` (tools, par, steps5, follow; R=10) and save scores to `specs/038-native-agent-every-provider/baseline.md`.
- [x] T002 [P] Add a fake provider HTTP server fixture `tests/fixtures/fake_provider.py` (stdlib, scripted replies, request log, skip on bind `PermissionError`).

## Phase 2: Slice 1 - Shared loop + Codex adapter, luna parity (US1, P1) - shippable alone

- [x] T010 Write `mods/agents-inc/hooks/native/adapter.ts` with the Adapter interface from contracts/step-adapter.md.
- [x] T011 Move provider-neutral code from luna.ts into `native/loop.ts` (render, catalog, parseReply, pickReply, handback, skipsTools, stopsEarly, ask loop, usage, begin/end) with no logic change.
- [x] T012 Write `native/codex.ts`: identity line, Codex refusal pushes, `agents-inc run --model <nick> --host-tools --thread` argv, `exitFailure` mapping (75, WB_CLI_NOT_FOUND, WB_CODEX_AUTH_MISSING, WB_LUNA_CATALOG_MISSING).
- [x] T013 Make luna.ts a shim exporting `register`/`registerLunaAgent` from loop + codex adapter; mod.ts unchanged.
- [x] T014 Run `mods/agents-inc/hooks/luna.test.ts` unchanged against the shim; all pass.
- [x] T015 Add `native/loop.test.ts` with a fake adapter: correction once, push once, fail closed on unknown agent, abort, timeout, no placeholder call.
- [x] T016 Rerun T001 stress on the shim; scores at least baseline (SC-001). Record in baseline.md.
- [x] T017 Remove luna.ts logic (keep file as re-export only) and update `mods/agents-inc/README.md` luna section wording only.

## Phase 3: Slice 2 - First free provider as native type (US2, P1) - shippable alone

- [x] T020 Operator gate: draft D-entries for Q1 (free native types do general work, per-workspace authorization) and P8 extension to all native types; implementation of T024+ waits for operator acceptance.
- [x] T021 `agents_inc/install/native.py`: `native status --json`, `on|off`, `allow`, `begin|end` with `--provider`; `luna status|on|off|begin|end` become aliases. Tests in `tests/test_native_cli.py`. Per Q2: `begin` for a free provider with no authorization record for the workspace returns a `needs-authorization` status naming the provider, what is sent and the write directories; the mod asks the operator once and calls `native allow`, which stores the per-workspace, per-provider record; later starts do not ask. Test: first start asks, second does not, a refusal starts nothing and sends nothing.
- [x] T021a Per Q4: adapter interface in `contracts/step-adapter.md` and `native/loop.ts` carries an `auth` field (`cli-login` | `key-store`) so a later optional API-key adapter fits without a loop change. No API-key adapter is built in slices 1 to 4; test only that an unknown `auth` value fails closed.
- [x] T022 `agents_inc/install/native_http.py`: Gemini request via urllib, key from key store in-process as header, map 429 -> 75, unreachable host -> 69, over-limit prompt -> 2. Tests with fake server.
- [x] T023 [P] Key-leak test `tests/test_native_keys.py`: fake key absent from spawned argv, child env, stdout, stderr, run dir files (SC-005).
- [x] T024 `agents-inc native step` verb wiring in `cli.py`; progress lines in the existing `agents-inc run: event|usage|record` format.
- [x] T025 `native/http.ts` stateless adapter: full-conversation prompt each step, context-limit refusal text.
- [x] T026 `agents_inc/install/native_probe.py`: tool-protocol probe, cache with 7-day TTL, `doctor --probe`, `models probe`.
- [x] T027 `native/registry.ts`: read `native status`, register one type per offered model, offer hook per type; add the one Gemini nickname to the roster here (rest in T046).
- [x] T028 Docker stress: tools, par, steps5 against fake Gemini server, R=10, at least 7/10 each (SC-002); session-start request count 0 (SC-006).
- [ ] T029 Mac live probe of one Gemini free slug; record result in baseline.md.
- [x] T030 Mac measurement (FR-019): from a mod spawn, record `SANDBOX_RUNTIME`, proxy env, and reachability of the Gemini host; write result in research.md R4; if sandboxed, add doctor check `WB_NATIVE_DOMAIN_MISSING`.
- [x] T031 Mac measurement: register 6 types in one session start; record success and start time in research.md R6.

## Phase 4: Slice 3 - Every probed model (US3, P2)

- [x] T040 [P] Mistral adapter config in native_http.py + tests.
- [x] T041 [P] OpenRouter adapter config in native_http.py (`:free` slugs only, free-only guard) + tests.
- [x] T042 Codex nicknames sol, terra, astra as native types through codex adapter + tests.
- [x] T043 `hook.py` `NATIVE_TYPES` read from `native status` registry file, not a literal (FR-017); update `tests/test_hook_persona_guard.py`.
- [x] T044 Doctor: per-model offer line, mod/package version mismatch warning (FR-018).
- [x] T045 Loop writes `events.jsonl` rows and the host-ledger record `source: native-<provider>` per agent run dir (FR-015); tests.
- [x] T046 [P] Add free-model nicknames to the roster/`models.json` with a test that each nickname maps to one vendor (FR-006, P7).

## Phase 5: Slice 4 - Route collapse and pane (US3 pane, US4, P3)

- [x] T050 delegate-pane: list native agents and registered types only (FR-020); tests.
- [x] T051 Install: relay agent, `mcp__agents-inc__run` and `@` routes off by default; `--legacy-routes` keeps them (FR-016); tests.
- [x] T052 Docs: README, QUICKREF, skills/workerbee name native types as the route; D-entry for route collapse.
- [x] T053 Full suite plus `docker/stress_check.sh` in docker; check SC-003 (each stateless adapter at most 200 lines) and SC-004 (one user-facing route, no single-route text guard); record.

## Phase 6: Final

- [ ] T060 Move specs to DomI: `bash <DomI>/skills/speckit-pipeline/scripts/move_specs_to_domi.sh --apply` (run last, by implement only).

## Dependencies

Phase 1 -> Slice 1 -> Slice 2 (T020 operator gate before T024) -> Slice 3 -> Slice 4 -> T060. T030 and T031 must finish before slice 2 is called shipped.

## Strategy

Ship slice 1 alone (no user-visible change, removes per-model duplication). Ship slice 2 once D-entries are accepted. Slices 3-4 follow.
