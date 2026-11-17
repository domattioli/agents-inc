<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Quickstart: checking spec 042 by hand

Each block reproduces one user story after its phase ships. Run from a scratch git repository with an installed agents-inc. Write the slots file in one Bash call and run `agents-inc dispatch` alone in the next (the hook denies compound calls).

## Story 1: a gate that cannot start

Slots: a trivial TASK, `FILES_IN_SCOPE: ["out.txt"]`, `GATES: ["no-such-tool --version"]`.

Expected: the pre-launch capability check refuses first (`refused-capability`, exit 3, D72 item 3). To reach the post-run path, use a gate whose program is deleted during the run (test fixture), then expect `outcome=unverified reason=gate-not-runnable`, `gates=0/1 not-checked:no-such-tool:rc=none`, a printed block line `gate not-checked rc=none cmd=no-such-tool --version last=...`, exit 4.

## Story 1: a neighbour's file changes

During the run, touch a file outside FILES_IN_SCOPE from another shell. Expected: `outcome=unverified reason=scope-foreign-change`, the path listed with `attribution=unknown`, gate results still shown, exit 4. Not `red snapshot-not-clean`.

## Story 2: a false claim

Use the fixture delegate in `tests/fixtures/claims/` whose claims block lists `files_changed: out.txt` and `tests: 12` while writing nothing. Expected: outcome follows the gates; status line `claims=checked:2 unsupported`; `claims.json` lists both; the `returned` ledger row has `claims.unsupported == 2`.

## Story 3: doctor with no network

Run `agents-inc doctor` with the network off. Expected: no `READY`; a line `dispatch-path: could-not-test (tested: not-tested)` and the reason `api.anthropic.com unreachable` on the lines that follow, in the uniform `<name>: <result> (<tested>)` format of `plan.md`; exit 1.

With uncommitted edits under `agents_inc/` in the source checkout: a line `WARNING: WB_SOURCE_UNCOMMITTED ...`; READY is unaffected by the warning.

With a failed collection, the status line shows `not verified now` and the record age instead of dimming only.

## Story 4: a refusal message

Slots with `FILES_IN_SCOPE: ["src/*.py"]`. Expected stderr:

```text
refused: scope-glob (FILES_IN_SCOPE must list exact paths)
value: src/*.py
fix: FILES_IN_SCOPE: ["src/a.py", "src/b.py"]
```

`agents-inc dispatch --rules` prints every rule; `agents-inc dispatch --print-template` prints the worked slots example.

## Story 5: replay set

`python3 -m unittest tests.test_screen_replay` passes: every `false-deny` case is allowed, every `bypass` case is denied, every `regression` case keeps its decision.

## Full suite

`python3 -m unittest discover -s tests -p 'test_*.py'` passes after each phase.
