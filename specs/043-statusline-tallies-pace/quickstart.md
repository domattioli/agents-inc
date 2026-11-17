<!-- provenance: author=domattioli model=claude-opus-5-5 effort=low date=2026-11-15 skill=speckit-plan repo=agents-inc session=b437620e -->
# Quickstart: verify spec 043

Work copy, never the live files: `scripts/statusline.sh` and `scripts/statusline.d/` run on every render from this checkout (`SPEC.md` Operator rules). Builders edit `.scratch/043/scripts/` (copy of `scripts/`) and `.scratch/043/skills/codex-bridge/reference/prices.json`. Tests resolve paths relative to their own dir, so they run against the copy.

```bash
R=~/Projects/agents-inc; W=$R/.scratch/043
mkdir -p $W/skills/codex-bridge/reference && cp -R $R/scripts $W/ && cp $R/skills/codex-bridge/reference/prices.json $W/skills/codex-bridge/reference/
```

## Gates on the copy (every phase)

```bash
cd $W
bash -n scripts/statusline.sh
shellcheck -S warning -f gcc scripts/statusline.sh scripts/tests/statusline_smoke.sh | sed -E 's/:[0-9]+:[0-9]+:/:/' | sort > sc.now; comm -13 baseline-shellcheck.txt sc.now   # must print nothing (no new finding)
/opt/homebrew/bin/pytest scripts/tests/test_collect_usage.py -q
bash scripts/tests/statusline_smoke.sh            # smoke: N/N checks passed
# warm render no slower than baseline + 10% (.scratch/043/baseline-time.txt; 0.40 s target is red at baseline under the sandbox); run twice, time the second with /usr/bin/time -p
bash scripts/statusline.sh < scripts/tests/fixtures/statusline_session.json >/dev/null
time bash scripts/statusline.sh < scripts/tests/fixtures/statusline_session.json >/dev/null
# missing sources: nulls + exit 0
python3 scripts/statusline.d/collect_usage.py --session-id x --usage-db /nonexistent --prices /nonexistent --codex-glob '/nonexistent/*' --out $W/null.json --force; echo exit=$?
```

## Width in three colour modes

```bash
W8='import sys,unicodedata as u;print(sorted({sum(2 if u.east_asian_width(c) in "WF" else 0 if u.combining(c) else 1 for c in l.rstrip("\n")) for l in sys.stdin}))'
F=scripts/tests/fixtures/statusline_session.json; S=$'s/\033\\[[0-9;]*m//g'
COLORTERM=truecolor bash scripts/statusline.sh < $F | sed "$S" | python3 -c "$W8"
STATUSLINE_COLORS=256 bash scripts/statusline.sh < $F | sed "$S" | python3 -c "$W8"
NO_COLOR=1 bash scripts/statusline.sh < $F | sed "$S" | python3 -c "$W8"
# each prints one width, the same in all three, equal to the pre-change width
```

## Live dry run before swap (read-only on live data)

Warning: a dry run with the default config writes gap lines to the operator's real `~/.claude/statusline-domi.log`. Always pass `--config` with a scratch copy of `config.json` whose `gap_log` points at a scratch file.

```bash
# --prices: the copied config.json lists the LIVE prices.json first; point the dry run at the copy.
python3 $W/scripts/statusline.d/collect_usage.py --session-id dry --prices $W/skills/codex-bridge/reference/prices.json --out $W/dry.json --force >/dev/null; echo exit=$?
jq '.models|to_entries[]|[.key,.value.d28.tokens,.value.d7.cost,.value.h5.tokens,.value.pace.source]' -c $W/dry.json
```
Check per phase: Phase 1 every 28-day model has non-null `d7.cost`; Phase 2 `gpt-6.1-sol` h5 tokens below the old cache value by about the spanning thread; Phase 4 rows = top 4 by `d28.tokens`.

## Swap into live (orchestrator only, after gates green and review)

```bash
cp $W/scripts/statusline.d/collect_usage.py $R/scripts/statusline.d/collect_usage.py.new && mv -f $R/scripts/statusline.d/collect_usage.py.new $R/scripts/statusline.d/collect_usage.py
cp $W/scripts/statusline.sh $R/scripts/statusline.sh.new && mv -f $R/scripts/statusline.sh.new $R/scripts/statusline.sh
```
Atomic `mv` so a render never reads a half-written script. Collector before renderer. Then re-run the Gates from `$R`, watch two live renders and `~/.claude/statusline-domi.log` (if present) for a traceback. Rollback: `git -C $R checkout -- <file>` restores the last committed version (orchestrator decides; no commit authority implied).

## Story checks

- US1: fixture with `claude-fable-5-2`, `claude-haiku-5-5`, no entries -> non-null cost, priced as fable-5-1 / haiku-4-5; with entries -> own price; `claude-zeta-1` -> null, renders `—`.
- US2: fixture thread created 8 h ago, rollout events at -8 h (T=1000) and -1 h (T=1500) -> 5H tokens 500.
- US3: retired ids high ALL, zero 28D -> not shown; tie on 28D broken by ALL then id.
- US4: top border `SESS═══5H═══1D═══7D══28D══ALL` x3.
- US5: rendered fixture with r = 0.25, 1, 4 -> 0,224,255 / 127,163,235 / 255,102,214 (truecolor, permille 0/500/1000 via `ramp_c`).
