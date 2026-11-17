<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# CLI Contracts

## `python3 -m agents_inc.free_health report --provider P --model M --outcome O [--retry-after SECONDS] [--message TEXT]`
Exit 0 always on write success; exit 0 plus one warning when state file unreadable (rewrites fresh). O from Outcome enum.

## `python3 -m agents_inc.free_health classify --status CODE --body-file F`
Prints outcome enum and retry seconds (or `-`). Rules: 404 + "unavailable for free" = withdrawn; 404 + "data policy"/"zero data retention" text = zdr; 429 = rate_limited; 503 = overloaded; 2xx = ok; else error.

## `python3 -m agents_inc.free_health pick-default --provider openrouter --task T`
Prints first model: provider match, id ends `:free`, effective status available, T in tasks_good, T not in tasks_bad. None: stderr `no eligible free model`, exit 3, no network.

## `python3 -m agents_inc.catalog_refresh [--apply] [--from-file PATH]`
Default dry-run: prints `would mark unavailable: ID`, `would add: ID`, changes nothing. `--apply` writes `models.json` and clears overlay entries for listed ids. Fetch error: exit 2, no writes. Only public models endpoint; no key; no generation.

## `python3 -m agents_inc.free_caps probe-openrouter [--from-file PATH]`
Reads key limits, writes `free-caps.json`. No generation call. Key never printed.

## Router API (`agents_inc/router.py`)
`pick_model_chain(task, tier, available, workspace_authorized, exclude_provider=None, prefer_provider=None)` signature unchanged. Reads modality from `AGENTS_INC_MODALITY`, health/caps via `free_health`/`free_caps`.
