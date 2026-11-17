<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-11 skill=speckit-pipeline repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Implementation Plan: One native Agent route for every provider

**Branch**: `038-native-agent-every-provider` | **Date**: 2026-11-11 | **Spec**: spec.md

## Summary

Split `mods/agents-inc/hooks/luna.ts` into a provider-neutral step loop and a Codex adapter with no behaviour change, then add stateless HTTP adapters (Gemini first, then Mistral, OpenRouter) that reuse luna's JSON text tool protocol through a new `agents-inc native step` CLI verb. Register one type per probed, authorised model. Then retire the relay, MCP tool and `@` routes as user-facing and make the agent gate read the same registry.

## Technical Context

- Mod: TypeScript, Claude Code mod API as used by luna.ts/relay.ts only (see spec Assumptions). Tests: `claude plugin test mods/agents-inc` (bun-style `*.test.ts`).
- CLI: Python 3.11 stdlib, `unittest`. HTTP via `urllib.request`.
- Dev and stress: `docker/Dockerfile.dev`, `docker/Dockerfile.ci`, `docker/luna_stress.sh`; fake provider HTTP server in tests (stdlib `http.server`, skip when bind raises `PermissionError`, D68 R1).
- Constraints: $0 (P5), keys never in argv/prompts, no DomI at run time, works after `agents-inc install` alone.

## Constitution Check

- P1 repo-scoped writes: yes; run dirs under install state.
- P2 labor ladder: free native types are Grunt-tier; widening to general work needs Q1 D-entry. FLAG.
- P3 no self-graded gates: parent verifies; snapshot line kept.
- P4 deterministic policy: offer decision is a pure function of files (data-model).
- P5 $0: only FREE_MODELS slugs and Codex login.
- P7 nicknames: one vendor per nickname; free nicknames added to roster.
- P8: does not bind native types (D69 Q5 extended to all native types; needs D-entry with Q1).
Gate: PASS with two D-entries required (Q1/P2, P8 extension).

## Project Structure (touched later by implement)

```
mods/agents-inc/hooks/native/loop.ts        # from luna.ts, provider-neutral
mods/agents-inc/hooks/native/codex.ts       # Codex adapter
mods/agents-inc/hooks/native/http.ts        # stateless adapter (gemini, mistral, openrouter)
mods/agents-inc/hooks/native/registry.ts    # reads native status, registers types
mods/agents-inc/hooks/luna.ts               # removed at end of slice 1 (re-export shim during slice 1)
agents_inc/install/native.py                # status, on/off, allow, begin/end (from luna_native.py)
agents_inc/install/native_http.py           # provider calls, key read, error mapping
agents_inc/install/native_probe.py          # probe + cache
agents_inc/install/hook.py                  # NATIVE_TYPES from registry
mods/delegate-pane/hooks/register.tsx       # list native agents only
```

## Phases

1. Slice 1 (shippable alone): loop + Codex adapter, luna parity. No new types, no user-visible change.
2. Slice 2 (shippable alone): `native step` + Gemini HTTP adapter + probe + workspace authorization + sandbox measurement + D-entries.
3. Slice 3: Mistral, OpenRouter, sol/terra/astra types; data-driven NATIVE_TYPES; doctor checks.
4. Slice 4: pane lists native agents only; relay/MCP/`@` routes off by default (`--legacy-routes`); docs.
5. Final: move specs to DomI.

Later slice, not in this plan's tasks (Q4, operator 2026-11-11): optional per-provider API-key adapter for consumers. Off by default, key entered through the hidden install prompt into the 0600 key store, never in argv, labelled as a paid path. This machine keeps the Codex CLI login and the $0 cap. Slice 2 only reserves the `auth` field (T021a).

Workspace authorization (Q2, operator 2026-11-11): free-provider types are offered in every workspace; the first start in a workspace asks once and stores a per-workspace, per-provider record (T021). No command-only gate.

## Risks

1. Mod API: no evidence of a cap on `$.agent.register` calls, no `fetch` in the mod API surface seen, and `turn.step` cannot read the agent's own prompt (D69). Mitigations: provider calls in Python CLI; measure registration count (T031); keep fail-closed identification via `$.agent.list`.
2. Free models may not follow the JSON protocol reliably; mitigated by the probe gate and SC-002 thresholds; types that fail are not offered.
3. Sandbox: if mod spawns are sandboxed, free hosts are blocked (exit 69 class). Measured in T030; doctor check for `allowedDomains`.
4. Policy: widening optional providers (Q1) and P8 exemption need operator D-entries before slice 2 ships.
