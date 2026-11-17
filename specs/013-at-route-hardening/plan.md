<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Implementation Plan: at_route Hardening and Installer Ownership

**Branch**: `development` (no feature branch) | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: `specs/013-at-route-hardening/spec.md` (Clarifications answered 2026-10-01). Plan written inline by the Supervisor (Orchestrator rung, ruling R1).

## Summary

Four changes, Bash plus Python standard library:

1. `at_route.sh` runs routed Claude calls with a read-only tool set, names a timeout as a timeout, and gains an `openrouter` alias that calls `oask.sh` with no model override.
2. The installer (`agents_inc/install/`) owns the `UserPromptSubmit` hook entry and eleven `@alias` links. Both point at the installed release copy through the `current` symlink. Install replaces the legacy `~/.claude/scripts/at_route.sh` hook line, relinks legacy links, and deletes the legacy file with a journaled backup.
3. `agents-inc doctor` warns when the installed `at_route.sh` differs from the source checkout's copy.
4. `install_at_route.sh` stops copying; `docs/AT-ROUTE.md` documents the new install path, the read-only and timeout behavior, and `@openrouter`. #32 close-out evidence lands in this directory.

## Technical Context

**Language/Version**: Bash 3.2+, Python 3.9+ standard library
**Primary Dependencies**: none new; `jq` and `perl` already required by `at_route.sh`
**Storage**: Claude settings JSON (host config, receipt-owned), install receipt, `paths.state` (`~/.local/state/agents-inc`)
**Testing**: `python3 -m unittest` (fake HOME, pattern `tests/test_install_host_wiring.py`); `bash skills/codex-bridge/tests/at_route.smoke.sh` (stub `claude` and `oask.sh` on PATH or beside a temp copy of the hook)
**Target Platform**: macOS and Linux developer machines
**Constraints**: no real model calls in tests; no writes to the live `~/.claude`, `~/.local`, `~/.codex-bridge` by tests or by the implementer (FR-016); peer-owned files untouched
**Scale/Scope**: one hook script, one installer module, one doctor check, eleven aliases

## Existing code (evidence)

- Claude branch has no tool restriction: `skills/codex-bridge/scripts/at_route.sh:79-80`.
- Alarm: `at_route.sh:18` (`AT_ROUTE_TIMEOUT`, default 120), `:72-74` (perl `alarm`). Failure block: `:145-151`.
- Alias regex has no `openrouter`: `at_route.sh:43`. Box header: `:138`. Relay line: `:127`.
- `SCRIPT_DIR` resolves the symlink, then falls back to `AT_ROUTE_BRIDGE_DIR` only when `ask.sh` is absent beside the script (`at_route.sh:10-16`). The installed bundle ships `ask.sh` beside it, so the installed copy resolves its own bridge scripts.
- `oask.sh`: model from `free_health pick-default` when `MODEL` unset (`oask.sh:22-30`); spend guard exit 3 for non-`:free` (`:41-50`); stderr model line `[openrouter $MODEL | in N out M]` (`:286`); governance refusal exit 3 (`:7-10`).
- Legacy installer copies and links: `skills/codex-bridge/scripts/install_at_route.sh:5-10`. Live settings line (read-only check, 2026-10-01): `"command": "bash ~/.claude/scripts/at_route.sh", "timeout": 130` inside a `UserPromptSubmit` group that also holds a foreign hook.
- Host wiring: `agents_inc/install/host_wiring.py:71-95` (`hook_command`, `_owned`, `strip_hooks`, `add_hooks`), `:113-136` (backup, journaled `write_file`/`delete_file`), `:138-158` (`install_host_wiring`). Owned hook detection is prefix `<launcher> hook ` only (`:73-74`).
- Symlink ownership and uninstall: `agents_inc/install/discovery.py:33-48` (`restore_skill_links` unlinks every receipt `symlink` item whose target matches, then restores its predecessor). `agents_inc/install/cli.py:76-91` (`uninstall`).
- Journal recovery restores `file` ops from the backup and `symlink` ops to their predecessor: `agents_inc/install/transaction.py:52-77`.
- Doctor warnings are non-fatal: `agents_inc/install/doctor.py:19`, `:31`. The receipt has no source-checkout field (`agents_inc/install/receipt.py:32-60`), and every receipt rebuild passes positional fields (`cli.py:49`, `:54`, `discovery.py:31`, `host_wiring.py:158`), so a new receipt field would be dropped silently.

## Design decisions

- **DD1 read-only flags** (FR-001): the Claude branch runs `claude -p "$question" --model "$model" --tools "Read,Grep,Glob" --disallowedTools "Edit,Write,Bash,NotebookEdit" --strict-mcp-config`. `--tools` restricts the built-in set (`claude --help`); `--disallowedTools` states the deny list from the clarification; `--strict-mcp-config` with no `--mcp-config` loads no MCP servers, so no MCP write tool (for example a GitHub push tool) is reachable. The Codex, Gemini, Mistral, and OpenRouter branches are unchanged (spec Assumptions).
- **DD2 timeout block** (FR-002, FR-003): when `rc == 142`, print `[at_route] <alias> call timed out after <N>s (exit 142). Partial files may exist in the working tree: run \`git status\` before answering.` then the stderr fence and the existing last line. Any other non-zero `rc` keeps the existing first line `call failed (exit N). Stderr:` byte-for-byte.
- **DD2a timeout detection**: `rc == 142` alone marks a timeout; a child that itself exits 142 is mislabeled (accepted, spec Edge Cases, analyze A15).
- **DD3 openrouter branch** (FR-009 to FR-012): alias regex gains `openrouter`; `kind="openrouter"`, display model starts as `unknown model`. Call `env -u MODEL "$SCRIPT_DIR/oask.sh" "$question"` under the alarm. On `rc == 0`, parse the last stderr line matching `^\[openrouter ([^ |]+) \|` and set the display model to the capture. Non-zero exit falls into the failover block (existing path). `oask.sh` is not edited. The same `$model` feeds the relay line and the answers log (FR-011). The stale comment at `at_route.sh:11-13` is rewritten: the installed copy lives in the release bundle beside `ask.sh`; the `AT_ROUTE_BRIDGE_DIR` fallback stays for ad-hoc copies only (analyze A12).
- **DD4 installed hook command** (FR-004, FR-005): settings command `bash <paths.current>/skills/codex-bridge/scripts/at_route.sh` (literal `current` path, not resolved), timeout 130 (> default alarm 120). Claude host only (new `Host` field `prompt_hook=True` for claude). `_owned` also matches this exact command, so `strip_hooks` removes it on uninstall and reinstall never duplicates it. The command is direct, not `<launcher> hook at-route`, so the hook's exit code 2 and stderr box pass through with no Python wrapper (`hook.py:30-40` always returns 0, which would break block mode).
- **DD5 legacy line** (FR-007): `strip_hooks(config, paths, legacy=False)`; with `legacy=True` (passed only by `add_hooks`, so install and repair) it also removes commands equal to `bash ~/.claude/scripts/at_route.sh` or `bash <home>/.claude/scripts/at_route.sh`, keeping the rest of their group. Uninstall calls it without the flag and touches only owned entries (analyze A10). `wiring_problems` keeps its pre-013 test (any `<launcher> hook ` command), so the at_route entry alone never counts as wired (analyze A4). The settings file write is journaled with a byte-exact backup (`write_file`).
- **DD6 alias links** (FR-004, FR-005, FR-007): new `install_alias_links(paths, receipt, journal) -> (receipt, notices)` in `host_wiring.py`, called from `cli.install` after `install_host_wiring` when host wiring is on and the Claude host is detected. Aliases (11): `haiku sonnet opus fable astra sol terra luna gemini mistral openrouter`. Per link `paths.launcher.parent / "@<alias>"`: absent, create; symlink to the desired path, keep; symlink to the legacy file, journaled unlink plus relink (journal predecessor = legacy target, so recovery restores it); any other file or link, leave untouched and add a `NOTE:` notice. Receipt entries are `OwnedPath(link, "symlink", None, desired)`, appended only when the path is not already in `receipt.owned_paths` (analyze A7); `restore_skill_links` already removes them on uninstall. Receipt predecessor is `None` because the legacy file is deleted, so uninstall does not recreate dangling legacy links.
- **DD7 legacy file** (FR-007): if `<home>/.claude/scripts/at_route.sh` is a regular file whose text contains `at_route.sh - UserPromptSubmit hook`, `delete_file` it (backup under `paths.state/backups`, journal `file` op, so recovery restores it). Otherwise leave it and add a notice. "Rollback" in the spec means journal recovery of an interrupted install; the `agents-inc rollback` command only swaps `current` (`cli.py:123-130`), which keeps every alias valid because the links go through `current`.
- **DD8 source checkout record** (FR-006): install writes the resolved `--source` path to `paths.state / "source-checkout"` (plain text, not part of the receipt, to avoid the positional-rebuild drop above). Doctor: if that file is missing or names a missing `skills/codex-bridge/scripts/at_route.sh`, warning `WB_HOOK_DRIFT_UNCHECKED`; if both files exist and bytes differ, warning `WB_HOOK_DRIFT`; else nothing. Warnings never change `ready` or the exit code. Doctor only checks when the receipt loads (existing early return). The record is an unowned cache: not journaled, not in the receipt, left in place by uninstall (analyze A8). Existing installs show `WB_HOOK_DRIFT_UNCHECKED` until the first repair from this release (analyze A9).
- **DD9 legacy installer** (FR-008): `install_at_route.sh` becomes a stub that copies nothing, prints `install_at_route.sh is retired: run agents-inc repair --source <checkout>` with the computed checkout path, and exits 2. `docs/AT-ROUTE.md` install section rewritten to match.
- **DD10 peer file** (FR-014): the `@openrouter` lexicon row in `skills/codex-bridge/SKILL.md:280` is a `BLOCKED-PEER` task; not implemented.

## Constitution Check

Constitution at `~/Projects/DomI/specs/consumers/agents_Inc/memory/constitution.md` is unratified, so violations are WARN.

| Principle | Status | Note |
|---|---|---|
| P0 cross-reference, never duplicate | PASS | Removes the drifting second copy; reuses `host_wiring` journal and `restore_skill_links`. |
| P1 repo-scoped writes | PASS | Implementation edits repo files only; live-machine install runs later by the Executive (FR-016). |
| P2 labor ladder | PASS | tasks.md assigns haiku (narrow Bash, docs) and sonnet (installer design). Supervisor writes tests. |
| P4 deterministic policy over prompt | PASS | Tool restriction is CLI flags, not prompt text. |
| P5 hard $0 per task | PASS | `@openrouter` keeps the `:free` spend guard; tests make no model calls. |
| P9 edit hygiene | PASS | Surgical edits. |

Post-design re-check: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/013-at-route-hardening/
├── spec.md
├── plan.md
├── tasks.md
├── issue32-evidence.md          (#32 close-out)
├── analyze.md                   (analyze phase)
└── checklists/
    ├── requirements.md          (specify)
    └── install-safety.md        (checklist phase)
```

### Source Code

```text
skills/codex-bridge/scripts/
├── at_route.sh                  # edit: DD1, DD2, DD3
└── install_at_route.sh          # edit: DD9 stub
skills/codex-bridge/tests/
└── at_route.smoke.sh            # edit: new cases (Supervisor-owned)
agents_inc/install/
├── host_wiring.py               # edit: DD4-DD7
├── cli.py                       # edit: call install_alias_links, write source-checkout, print notices
└── doctor.py                    # edit: DD8 drift warnings
tests/
└── test_install_at_route.py     # new (Supervisor-owned): installer + doctor drift, fake HOME
docs/AT-ROUTE.md                 # edit: install section, read-only, timeout, @openrouter row
```

**Structure Decision**: extend `host_wiring.py` rather than add a module; the alias links share its journal and backup helpers. One new test file keeps the batch's tests nameable.

## Agent context update

Skipped: no `CLAUDE.md` (retired 2026-10-01); `AGENTS.md` unchanged by this batch.

## Complexity Tracking

None.
