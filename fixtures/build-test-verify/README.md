# build-test-verify fixtures

Generic tasks for the token savings test (`docs/proposals/delegation-savings-test.md`). Each size has:

- `SPEC.md`: the only file copied into the trial's empty working directory.
- `hidden/acceptance.py`: the independent judge. It is never copied into the trial directory. The harness runs it after the session ends: `python3 hidden/acceptance.py <trial dir>`. Exit 0 means every case passed; it prints one JSON line with counts.
- Seeded traps, named in the acceptance script, form the quality floor (D5).

S is `csv2json`: one script, 6 requirements, 14 hidden cases, 4 traps. M is `tasklog`: a package with storage, commands, filters and a report; 9 requirements, 25 hidden cases, 7 traps. L follows once M has run.
