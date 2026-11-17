<!-- provenance: author=domattioli model=opus effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=spec041-lead -->
# Clarify questions: spec 041 terminology

Highest impact first. Counts come from `inventory.md`. Questions flagged **OPERATOR** are taste or irreversible calls that evidence cannot settle; the rest the CoS can answer.

## Q1. Relational word for "the party that dispatched this delegate and verifies it" (FR-005)

- **A. Supervisor, in this sense only.** Consequence: matches the `SUPERVISOR` slot in `render_dispatch.py:259-299` (which already means "one step above") and D34's note that lowercase "supervisor" is generic for the verifier. Risk: readers still remember Supervisor as a rung and a Lead alias; the lint must tell the senses apart. Cost: no code rename; about 65 current-doc hits to re-read, most already in this sense.
- **B. Dispatcher.** Consequence: no history of rung or role meaning, so the lint can ban Supervisor outright. Cost: 12 current-doc uses of Dispatcher already fit; about 65 current-doc Supervisor hits to rewrite; the `SUPERVISOR` slot name stays as a code identifier that no longer matches prose (P-e).
- **C. No word; say "the Lead" or "the CoS" each time.** Consequence: most precise, wordier; breaks for nested Leads where the dispatcher is a Lead and the delegate is also a Lead.
- **Recommended: B.** A clean lint ban is worth more than slot-name alignment, and a slot docstring can say "SUPERVISOR = dispatcher".

## Q2. Canonical name for the human (FR-008) **OPERATOR**

- **A. operator in prose; CEO only as the role noun in the chain figure and role table.** Consequence: matches 439 existing operator hits; keeps D46.4 fixed noun. Cost: rewrite most of the 46 current-doc CEO prose hits.
- **B. CEO everywhere.** Consequence: one word, corporate frame throughout. Cost: rewrite about 170 current-doc operator hits plus code strings (82 code hits, for example `agents_inc/install/hook.py`), and the `skills/workerbee/scripts/render_dispatch.py` default `operator`.
- **C. Keep both as defined synonyms.** Consequence: violates P-b; cheapest.
- **Recommended: A.** Taste and a D46.4 fixed noun are involved, so the operator rules.

## Q3. Lint shape for retired aliases (FR-013)

- **A. Word list plus context patterns, `.md` only, file allowlist for historical records.** Consequence: catches "aka Supervisor", "alias Orchestrator", "ultra-tier"; ignores generic English. Cost: one script plus one test module; allowlist of about 10 path patterns.
- **B. Bare-word ban with an inline ignore marker.** Consequence: simplest matcher; floods on Worker (118 current-doc hits), cheap (122), tier (211). Cost: many markers in current docs.
- **C. No lint; review only.** Consequence: D34 aliases already survived review; decay likely.
- **Recommended: A.**

## Q4. How to treat `docs/DECISIONS.md`, which mixes history and live rulings

- **A. Allowlist all entries up to and including the new 041 entry's predecessor; later entries are linted.** Consequence: honors append-only; new entries use canonical words. Cost: lint needs a heading-based cutoff.
- **B. Allowlist the whole file.** Consequence: simplest; new entries can reintroduce aliases.
- **C. Lint the whole file and rewrite old entries.** Consequence: breaks append-only and AGENTS.md "old names in historical documents stay unchanged". Irreversible in spirit.
- **Recommended: A.**

## Q5. `governance.json` agent `agent-supervisor-01`, type `supervisor`, name `Orchestrator Supervisor` (FR-015)

- **A. Prose fix only: change `name` to a canonical label, keep `id` and `type`.** Consequence: no policy or test churn beyond fixtures that assert the name. Cost: 8 Supervisor hits in the file; tests referencing it (`tests/test_policy.py` 34, `tests/test_gateway.py` 25 Supervisor hits) need a check for name asserts.
- **B. Rename `type` and `id` too.** Consequence: full consistency; touches policy ids, ledger records and many tests. Against P-e.
- **C. Leave untouched.** Consequence: one visible two-axis label remains in data.
- **Recommended: A.**

## Q6. Rename rungs to grade words (alternative in spec) **OPERATOR**

- **A. No; keep Executive, Orchestrator, Workhorse, Grunt and fix collisions in prose.** Cost: none beyond this spec.
- **B. Yes, prose only: grade words in docs, old names stay as code enums.** Consequence: two vocabularies for one axis, the problem this spec fixes.
- **C. Yes, full migration.** Cost: about 1731 rung-word matches, about 1015 in code and tests, settings keys and values (D80), SQLite CHECK, golden fixtures, the live pane. Hard to reverse for installed users' settings.
- **Recommended: A.** Flagged OPERATOR because it is a naming-taste call with an irreversible branch.

## Q7. "ultra" scope (FR-010)

- **A. Reserve "ultra" for effort and named modes (caveman ultra, `CODEX_BRIDGE_MODE=ultra`); ban it only as a rung adjective (ultra-tier).** Consequence: accurate; bridge mode untouched. Cost: 5 ultra-tier hits.
- **B. Reserve "ultra" for effort only, as the CoS seed said.** Consequence: forces renaming `CODEX_BRIDGE_MODE=ultra` (code value, `route.sh`, `ultra_smoke.sh`) and the caveman level, which sits outside this repo. Against P-e.
- **Recommended: A.**

## Q8. Driver, Host, Stdin worker (FR-011)

- **A. Lead recommendation: retire Driver (1 current-doc hit, duplicates CoS), scope Host to "the agent CLI" (live in `host_wiring.py`, `host_ledger.py`), scope Stdin worker to the MVP adapter path.** Cost: about 3 doc edits plus 6 docstrings left as is.
- **B. Retire all three.** Consequence: Host is a live code concept; retiring it creates a prose and code mismatch.
- **C. Keep all three as is.** Consequence: Driver keeps overlapping CoS and Lead.
- **Recommended: A.**
