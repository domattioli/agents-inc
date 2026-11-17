<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-11 skill=speckit-pipeline repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Research: One native Agent route for every provider

## R1. Tool calling for models without native function calling

Decision: reuse the luna text protocol. Evidence: luna.ts never uses Codex function calling for catalog tools; it runs Codex with `--no-tools --host-tools`, sends the catalog as text, parses the first balanced JSON object (`parseReply`), checks names against `$.tool.list()` (`allowed`), and yields `tool`/`input` chunks from `turn.step`. Claude Code then runs the tools under its own permission rules. Nothing in that path depends on the provider. Alternatives: provider-native function calling (Gemini, Mistral, OpenRouter offer it in their HTTP APIs, but the wrappers do not use it, each schema differs, and weak free models often emit malformed calls either way). Rejected for v1.

## R2. Where the provider call runs

Decision: a new `agents-inc native step --model <nick>` CLI verb (Python stdlib, `urllib`), spawned by the loop via `$.process.spawn` with the prompt on stdin, exactly like `agents-inc run` for luna. Keys are read in-process from `~/.config/workerbees/.env` (mode 0600) and sent as a header. Alternatives: call `gask.sh`/`mask.sh`/`oask.sh` (rejected: keys go into curl argv, D75 follow-up; wrappers carry their own guards and caches, H1 drift); fetch from TypeScript in the mod (rejected: no `fetch` is shown in the mod API used by existing code, and keys would enter the mod process; do not invent API).

## R3. Stateful vs stateless adapters

Codex keeps a thread file and sends only the delta (`DELTA_HEADER`). HTTP free providers are stateless: the loop resends the rendered conversation each step. The adapter declares its kind; the loop picks full vs delta prompt. Cost is $0 but context limits matter: the adapter refuses a prompt over `max_input_chars` (from `FREE_MODELS`).

## R4. Sandbox position of mod spawns (open, FR-019)

Unknown from code. luna works on the operator Mac through `$.process.spawn` while Bash-tool dispatches hit exit 69, which suggests mod spawns are outside the Bash sandbox, but D69 records no measurement. Must be measured before slice 2 (task T030). If spawns are sandboxed, free hosts need `sandbox.network.allowedDomains` entries and doctor checks them (D71 F3 pattern).

## R5. Guards that become unnecessary

Native types bypass dispatch, so persona deny, compound deny and credential prompt screen do not apply to them (D69 already exempts `agents-inc:luna`). FR-017 makes `NATIVE_TYPES` data-driven so a new type needs no hook edit. The compound-deny guard stays for the remaining `agents-inc dispatch` CLI use.

## R6. Registering many types

Existing code calls `$.agent.register` twice per session (relay, luna). No evidence of a cap. Verify with 6 registrations in slice 2 (T031). Risk if the engine caps or slows session start.

## R7. Probe design

Minimal tool round trip: catalog with one `Read` tool, task "Read the file probe.txt", expect a reply naming `Read`. Pass also requires parse success. Cached in install state with TTL 7 days (Q5). Rationale: models that cannot follow the protocol are not offered at all (operator goal "one type per model that passes a live probe").

## R8. Live measurements, 2026-11-11 (T030, T031, T053)

T030 (R4): a guest agent step started by the mod (`$.process.spawn` of `agents-inc native step`) reached `api.mistral.ai` and got answers on the operator Mac. Mod spawns are not inside the Bash sandbox, so no `sandbox.network.allowedDomains` entry and no `WB_NATIVE_DOMAIN_MISSING` doctor check is needed. `SANDBOX_RUNTIME` and proxy variables inside the spawn were not dumped; the reachability result stands in for them. Gemini host not measured (503, then 60 s timeout on the probe).

T031 (R6): one session start registered 8 types (relay, luna, ministral, codestral, nemotron-lightning, nemotron-ultra, nemotron-nano, dots-note) in about 0.3 s (22:14:19, `$.agent.register ... listed` lines). With legacy routes off (slice 4) it is 7. No cap seen.

T053: on 7e21b41, Mac suite 2192 OK (skipped=26), mod 114 pass, delegate-pane 3 pass, docker suite only the known `test_opus_demo` failure, docker stress 36 rows and no FAIL (builder run, before the last rebase). SC-003: `native/http.ts` 93 lines. SC-004 partly met: fresh install registers no relay type, no `mcp__agents-inc__run`, no @alias hook; `ROUTE_RULE` and `NUDGE` in `hook.py` still name `agents-inc dispatch` and a test guards that text, left until D79 is accepted.

Live guest agent run (codestral, toy workspace) found three defects the offline stress missed: workspace authorization compared path spellings (fixed 12118cb); step 0 over the 48000-char cap with a 77-tool catalog (fixed fb1f419: 6 core tools, per-model cap); HTTP 429 on the third request. Retries of 2, 5, 12 s (7e21b41) did not clear the 429; open.
