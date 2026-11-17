<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-analyze repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Research: Free models through dispatch

All unknowns resolved. Source: opus-medium design report (2026-11-09) and a read of `dispatch.py`.

## R1: Where the free kind attaches

- **Decision**: `_kind()` (`dispatch.py:877`) returns `"free"` when the slug is in `FREE_MODELS`. `run()` already branches on `kind`; `_run_dir_phase()` calls `run_free()` instead of `launch()` for `free`.
- **Rationale**: Reuses run directory creation, event sink, ledger node, snapshot, prompt lint and `_finish`. Only the launch differs.
- **Alternatives**: a separate `agents-inc free` command (rejected: second run record format, second set of exit codes).

## R2: Use the wrappers, not a new client

- **Decision**: call `gask.sh`, `mask.sh`, `oask.sh` unchanged. Prompt on stdin. Env carries `WORKERBEES_GOVERNANCE=off` and `TASK=<kind>`; `oask.sh` receives `MODEL`.
- **Rationale**: wrappers already hold key handling, caps, cooldowns, redaction and usage logging. Re-implementing doubles the attack surface.
- **Alternatives**: direct HTTP from Python (rejected: duplicates key handling, FR-002).

## R3: Slug map

| Slug | Wrapper | Tier or env |
|---|---|---|
| gemini-3.8-flash | gask.sh | `--tier digest` |
| gemini-flash-lite-latest | gask.sh | `--tier cheap` |
| ministral-3b-latest | mask.sh | `--tier cheap` |
| codestral-latest | mask.sh | `--tier code` |
| OpenRouter `:free` slugs (full `nvidia/...` names) | oask.sh | `MODEL=<slug>` |

Deep tiers (gemini-3.1-pro-preview, mistral-large-latest) stay out.

## R4: Task kind and classification

- **Decision**: `TASK_KIND` must be in `routing.json` `optional_allowed_tasks`, read at run time. `CLASSIFICATION` must be written by the author; the renderer's default does not count. Public and internal pass; confidential needs workspace authorization via the existing router rule (`router.py:141`).
- **Rationale**: matches the existing optional-provider rule (D16 text, P5). Reading the file keeps one source of truth.

## R5: Gates judge text

- **Decision**: a `{report}` token in a gate command expands to the saved reply path after the existing gate screens. No `GATES` gives `unverified/no-gates`.
- **Rationale**: free runs have no tools and no worktree changes, so the snapshot gate has nothing to judge. The reply is the product.

## R6: Wrapper exit code map

| Wrapper result (confirmed in T001 against gask/mask/oask, 2026-11-09) | Outcome |
|---|---|
| rc 4 (`oask.sh` only: redaction placeholders in reply) | red `redacted-reply` |
| rc 2 and stderr has "no API key" | red `provider-key-missing` |
| other rc 2 (bad flag, bad tier, missing file) | red `rc-nonzero` |
| rc 3 (governance not `off`; `oask.sh` spend guard on a non-`:free` MODEL, lines 46-48; `oask.sh` no healthy default model, lines 28-29) | red `wrapper-refused` |
| rc 1 and stderr has `error 429` or quota text | quota-paused, exit 75 |
| rc 1 and stderr has "cannot reach" or "timeout" | blocked, exit 69, host named from `FREE_MODELS` |
| other rc 1 (HTTP error, empty reply) | red `rc-nonzero` |

Findings that differ from the design report:
- `gask.sh` and `mask.sh` never return rc 4; only `oask.sh` does.
- 429, timeout and connect failures are all rc 1. Classify by stderr text, not by rc.
- The wrappers hold no cap or cooldown check. `grep` for cap, cooldown, quota finds nothing in the three scripts. The router owns them: `_in_cooldown` (`agents_inc/router.py:46`) and `_at_cap` (`router.py:65`), fed by `agents_inc/free_health.py`. The pre-launch check in dispatch reuses those functions (analyze cycle 1).
- rc 3 happens with the env `off`: the `oask.sh` spend guard and the no-healthy-default case both exit 3. All rc 3 causes map to `wrapper-refused`.
- HTTP errors print `<provider> error <code>: <message>` with the code taken from a variable, so a literal `429` grep finds nothing. The `error 429` stderr pattern holds for `gask.sh` (line 319) and `oask.sh` (line 266); `mask.sh` classifies through its own status helper (lines 30-64). T022 tests each wrapper's real stderr form.

## R7: Known risks

- D16 conflict: the child env sets `WORKERBEES_GOVERNANCE=off`. D75 states that dispatch is a governed caller, so the off flag refers to the legacy wrapper's own gate.
- D17: `oask.sh` honors the `MODEL` env. The `FREE_MODELS` map plus a free-only guard holds the pinning rule.
- Stale `models.json`: refresh to the 2026-11-09 probe (FR-014).
- API keys appear in curl arguments inside the wrappers. Out of scope; follow-up issue.
- Small-model context limits: an input size limit per slug; over the limit is a refusal, never a cut.
- Broker: `_load_run_manifest` and `_validate_fields` must reject free slugs (FR-013).
