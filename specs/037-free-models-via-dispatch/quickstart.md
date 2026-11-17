<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-plan repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Quickstart: Free models through dispatch

1. Write a slots file with `TASK_KIND` set to `extract`, `CLASSIFICATION` set to `public`, and a `GATES` line such as `` `test -s {report}` ``.
2. Run `agents-inc dispatch --slots slots.json --model codestral-latest`.
3. Expect `green`, exit 0, `cost_usd` 0 in `run.json`, and the reply in `stdout.md`.
4. Drop `GATES`: expect `unverified`, exit 0.
5. Set `TASK_KIND` to `refactor`: expect `refused-task`, exit 2, no provider call.
6. Test in docker: `docker run --rm --network none -w /src -v "$PWD:/src:ro" agents-inc-ci python3 -m unittest tests.test_free_dispatch` (wrappers are stubbed).
