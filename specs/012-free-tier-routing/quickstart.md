<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Quickstart: Free-Tier-Aware Routing

1. Run tests: `python3 -m pytest tests/test_free_health.py tests/test_free_caps.py tests/test_catalog_refresh.py tests/test_router_free_first.py tests/test_free_wrappers.py -q`
2. Dry-run catalog refresh: `python3 -m agents_inc.catalog_refresh`
3. Apply after review: `python3 -m agents_inc.catalog_refresh --apply`, then set `tasks_good` by hand for new models.
4. Probe OpenRouter limits: `python3 -m agents_inc.free_caps probe-openrouter`
5. Enable free-first: `export AGENTS_INC_MODALITY=budget`
6. Check health: `skills/codex-bridge/scripts/route.sh status`
