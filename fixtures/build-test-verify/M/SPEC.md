# tasklog

Build a Python package `tasklog/` (Python 3.10+, standard library only) in this directory, runnable as `python3 -m tasklog`. It keeps a task list in a JSON-lines file.

## Storage

S1. Every command takes `--db <path>` before the subcommand. The file holds one JSON object per line. A task object has exactly these keys: `id` (int), `title` (str), `tags` (list of str, sorted, no duplicates), `due` (`YYYY-MM-DD` string or null), `pri` (int 1 to 5), `done` (bool). The file may also hold at most one counter object `{"next_id": N}` (see S2). A missing file means an empty list; the first `add` creates it.

S2. Ids start at 1 and increase by 1. An id is never reused, even after the task with the highest id is removed. Track the next id in the counter object; a deleted task must not free its id.[^1]

S3. A line that is neither a task object nor the counter object, or `--db` pointing at a directory, prints one line starting with `error:` to stderr and exits 2, before any other output.

## Commands

C1. `add "<title>" [--tag T ...] [--due YYYY-MM-DD] [--pri N]`: appends a task and prints its id. Default `pri` 3, no tags, no due. An empty or whitespace-only title, a `pri` outside 1 to 5, or a `due` that is not a real calendar date exits 2 with an `error:` line.

C2. `done <id>`, `undo <id>`, `rm <id>`: mark done, mark not done, remove. Unknown id exits 2 with `error:`. Marking an already done task done is not an error.

C3. `list`: one line per task, tab-separated: `id`, `[x]` or `[ ]`, `pri`, `due` or `-`, `title`, tags joined by `,` (empty string when none). Order: not done before done, then earlier `due` first with null due last, then lower `pri` first, then lower id first. `list --json` prints the same tasks in the same order as a JSON array of the stored objects.

C4. `list --filter "<expr>"`: `<expr>` is one or more terms joined by ` and `. A term is `<key><op><value>` with no spaces. Keys and allowed ops:

| key | ops | meaning |
|---|---|---|
| `tag` | `=`, `!=` | has / does not have the tag |
| `pri` | `=`, `!=`, `<`, `<=`, `>`, `>=` | numeric compare |
| `due` | `=`, `!=`, `<`, `<=`, `>`, `>=` | date compare; a task with null due never matches `<`, `<=`, `>`, `>=` |
| `done` | `=`, `!=` | value `true` or `false` |

An unknown key, an op not allowed for the key, or a malformed value exits 2 with `error:`.

C5. `report --today YYYY-MM-DD`: prints a Markdown table:

```
| tag | open | done | overdue |
|---|---|---|---|
```

then one row per tag in alphabetical order, then a final row whose tag cell is `(all)`. `open` counts tasks not done, `done` counts tasks done, `overdue` counts tasks not done with `due` before `--today`. A task with several tags counts in each tag's row but once in `(all)`. Tasks with no tags appear only in `(all)`. `--today` is required.

C6. Every error path exits 2, prints exactly one `error:` line to stderr and nothing to stdout, and leaves the db file byte-for-byte unchanged.

[^1]: Do not solve S2 by scanning for the max existing id: after `rm` of the highest id, the next `add` must still get a fresh id.

## Deliverables

1. The `tasklog/` package.
2. A test suite under `tests/` covering S1 to S3 and C1 to C6, runnable with `python3 -m unittest discover -s tests`, passing.
3. `VERIFICATION.md`: for each of S1 to S3 and C1 to C6, the test(s) that cover it and the exact command you ran with its exit code. State anything you could not verify.
