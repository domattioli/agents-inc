<!-- provenance: author=domattioli model=unknown effort=unknown date=2026-10-01 skill=speckit-pipeline repo=agents_Inc session=unknown -->
# Issue #32 close-out evidence

Issue #32 reported that the `agents-inc` launcher failed when run outside the repository root. Fix #35 made `scripts/agents-inc` set `PYTHONPATH` from its own directory. No code change in this batch.

Run by the Supervisor on 2026-10-01, HEAD `dd48471`:

- Working directory: `/tmp`
- Command: `/Users/domattioli/.local/bin/agents-inc doctor`
- Output: `READY`
- Exit code: `0`

```text
$ cd /tmp && /Users/domattioli/.local/bin/agents-inc doctor; echo "exit=$?"; pwd
READY
exit=0
/tmp
```
