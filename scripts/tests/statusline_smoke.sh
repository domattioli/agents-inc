#!/usr/bin/env bash
# Smoke coverage for scripts/statusline.sh: box layout, row labels, values, bars, failure inputs, cache cases.
# Layout under test (operator-confirmed 2026-10-02): 8 lines (top border, 6 rows, bottom border), a magenta
# box with three table separators (│) at display columns 20, 64 and 108. The box is 139 columns plus the
# longest FREE model name (minimum 7): 147 with no FREE rows, 148 when the longest abbreviated name is 8 chars.
# Needs bash, jq, python3. Portable to bash 3.2 and bash 5 (no GNU-only or BSD-only flags).
set -uo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT="$DIR/../statusline.sh"; FIXTURE="$DIR/fixtures/statusline_session.json"
pass=0; fail=0
ok(){ pass=$((pass+1)); }
bad(){ printf 'FAIL: %s\n' "$1"; fail=$((fail+1)); }
has(){ printf '%s' "$1"|grep -qF -- "$2"&&ok||bad "$3"; }
hasre(){ printf '%s' "$1"|grep -qE -- "$2"&&ok||bad "$3"; }
lacks(){ if printf '%s' "$1"|grep -qF -- "$2";then bad "$3";else ok;fi; }
eq(){ [ "$1" = "$2" ]&&ok||bad "$3 (got: $1 | want: $2)"; }

# Invariant: usage ingest is throttled to once per 300 s and fire-and-forget.
if grep -qF '"$iage" -lt 300' "$SCRIPT" && grep -qF 'statusline.d/ingest_usage.py' "$SCRIPT"; then
  ok
else
  bad "statusline invokes 300s-throttled usage ingest"
fi

WORK=$(mktemp -d "${TMPDIR:-/tmp}/smoke.XXXXXX") || { echo 'smoke: mktemp failed' >&2; exit 1; }; trap 'rm -rf "$WORK"' EXIT
export HOME="$WORK/home"; mkdir -p "$HOME/.claude"
# Per-session cache: payloads with session_id sess-test read statusline-cache/sess-test.json; link it to the seeded global file.
mkdir -p "$HOME/.claude/statusline-cache"; ln -sf "$HOME/.claude/statusline-domi-cache.json" "$HOME/.claude/statusline-cache/sess-test.json"
unset NO_COLOR STATUSLINE_COLORS; export COLORTERM=truecolor

# Python helper: widths (terminal columns), separator columns, 5-cell bars (text + filled-cell count) per line.
cat >"$WORK/probe.py" <<'PYEOF'
import re, sys, unicodedata as u
mode = sys.argv[1]
data = sys.stdin.read()
def cw(c):
    return 0 if u.combining(c) else 2 if u.east_asian_width(c) in "WF" else 1
if mode in ("widths", "seps"):
    lines = re.sub(r"\x1b\[[0-9;]*m", "", data).splitlines()
    if mode == "widths":
        print(len(lines), " ".join(str(sum(cw(c) for c in l)) for l in lines))
    else:
        for i, l in enumerate(lines):
            col = 0; cols = []
            for c in l:
                if c == "│":
                    cols.append(str(col))
                col += cw(c)
            print(i, ",".join(cols))
elif mode == "mask":
    # Byte-identity helper (spec 043 SC-010): drop the first table column (machine gauges), turn the colour of the
    # window cells SESS..28D (the first five of six adjacent 5-wide cells) into <W>, and fold reset countdowns into <T>.
    run = re.compile(r"(?:\x1b\[[0-9;]*m[^\x1b]{5}\x1b\[0m){6}")
    one = re.compile(r"\x1b\[[0-9;]*m[^\x1b]{5}\x1b\[0m")
    def fix(m):
        c = one.findall(m.group(0))
        return "".join([re.sub(r"^\x1b\[[0-9;]*m", "<W>", x) for x in c[:5]] + c[5:])
    tcd = re.compile(r"(?:\x1b\[[0-9;]*m|(?<= ))(?:\d+[dh]\s?\d+[hm]|\d+m)(?=\x1b\[0m)")
    for l in data.splitlines():
        print(tcd.sub("<T>", run.sub(fix, "│".join(l.split("│")[1:]))))
elif mode == "bars":
    cell = re.compile(r"\x1b\[48;2;(\d+;\d+;\d+)m\x1b\[(?:1;)?38;2;(\d+;\d+;\d+)m(.)\x1b\[0m")
    for i, l in enumerate(data.splitlines()):
        ms = list(cell.finditer(l)); run = []
        runs = []
        for m in ms:
            if run and run[-1].end() != m.start():
                runs.append(run); run = []
            run.append(m)
        if run:
            runs.append(run)
        for r in runs:
            for k in range(0, len(r) - 4, 5):
                g = r[k:k + 5]
                text = "".join(m.group(3) for m in g).strip()
                # Full cell: bg == fg. A shaded edge cell is not filled, except as the lone min-1 cell when pct > 0.
                # Label glyphs use dark fg (track colour); bar colour = first non-dark fg, else first cell bg.
                bc = next((m.group(2) for m in g if m.group(2) != "44;42;56"), g[0].group(1))
                filled = sum(1 for m in g if m.group(1) == bc)
                if filled == 0 and any(m.group(1) not in ("44;42;56", m.group(2)) for m in g):
                    filled = 1
                print(i, text, filled)
elif mode == "cells":
    # Per line of lbar output: full cells (bg == fg), edge cells (bg != fg and not track), edge bg, bar fg.
    cell = re.compile(r"\x1b\[48;2;(\d+;\d+;\d+)m\x1b\[(?:1;)?38;2;(\d+;\d+;\d+)m(.)\x1b\[0m")
    for l in data.splitlines():
        ms = cell.findall(l)
        bc = next((f for b, f, _ in ms if f != "44;42;56"), ms[0][0] if ms else "-")
        full = sum(1 for b, f, _ in ms if b == bc)
        edge = [b for b, f, _ in ms if b != bc and b != "44;42;56"]
        print(full, len(edge), edge[0] if edge else "-", ms[0][1] if ms else "-")
PYEOF

run_case(){
 local input=$1 raw err status
 raw="$WORK/raw.out"; err="$WORK/err.out"
 bash "$SCRIPT" < "$input" >"$raw" 2>"$err";status=$?
 RAW=$(cat "$raw"); ERR=$(cat "$err")
 DISPLAY=$(printf '%s' "$RAW"|sed $'s/\033\[[0-9;]*m//g')
 [ "$status" -eq 0 ]&&ok||bad "exit 0"
 [ -z "$ERR" ]&&ok||bad "stderr empty ($ERR)"
}
# width_gate <expected columns>: 8 lines, all equal, exactly the expected terminal-column width.
width_gate(){
 local want=$1 result want_s="8 $1 $1 $1 $1 $1 $1 $1 $1"
 result=$(printf '%s' "$DISPLAY"|python3 "$WORK/probe.py" widths)
 eq "$result" "$want_s" "8 lines, each $want columns wide"
}
# sep_gate: all 6 body rows carry the three table separators at display columns 20, 64, 108.
sep_gate(){
 local got
 got=$(printf '%s' "$DISPLAY"|python3 "$WORK/probe.py" seps|sed -n '2,7p'|cut -d' ' -f2|sort -u|tr '\n' ' ')
 eq "$got" "20,64,108 " "table separators at columns 20,64,108 on all 6 rows"
}
# border_gate: box corners, full-width double rules, header labels.
border_gate(){
 local top bot n
 top=$(printf '%s\n' "$DISPLAY"|sed -n '1p'); bot=$(printf '%s\n' "$DISPLAY"|sed -n '8p')
 case "$top" in '╔'*'╗') ok;; *) bad "top border corners";; esac
 case "$bot" in '╚'*'╝') ok;; *) bad "bottom border corners";; esac
 n=$(printf '%s' "$bot"|python3 -c 'import sys;s=sys.stdin.read();print(s.count("═"))')
 [ "$n" -eq $((${#bot}-2)) ]&&ok||bad "bottom border is all ═ ($n of $((${#bot}-2)))"
 for t in ' STATUS ' ' ANTROP ' ' OAI ' ' FREE ';do has "$top" "$t" "header label$t"; done
 n=$(printf '%s' "$top"|grep -o 'SESS═══5H═══1D═══7D══28D══ALL'|wc -l|tr -d ' ')
 eq "$n" 3 "window letters SESS 5H 1D 7D 28D ALL under each of three tables"
 n=$(printf '%s\n' "$DISPLAY"|sed -n '2,7p'|grep -c '^║.*║$')
 eq "$n" 6 "6 body rows framed by ║"
}
# bars_rows56: filled-cell counts for the labelled bars on rows 5 and 6, in order.
bars_rows56(){ printf '%s' "$RAW"|python3 "$WORK/probe.py" bars|awk '$1==5||$1==6'|tr '\n' ';'; }

# ---------------------------------------------------------------- 1. fixture, no cache
run_case "$FIXTURE"; base=$DISPLAY; baseraw=$RAW
width_gate 147; sep_gate; border_gate
strict_raw="$WORK/s.out"; strict_err="$WORK/s.err"
STATUSLINE_STRICT=1 bash "$SCRIPT" < "$FIXTURE" >"$strict_raw" 2>"$strict_err" && ok || bad "strict fixture exit 0"
[ ! -s "$strict_err" ] && ok || bad "strict fixture stderr empty"

# Row labels (col 1 left, col 1 right) with their fixture values.
has "$base" 'CLK 12m' "CLK label + 754 s session = 12m"
has "$base" 'DIR pr…ct' "DIR label + project name middle-ellipsized to 5"
for label in TPM TOK DOL;do has "$base" "$label " "$label label";done
for label in DSK RAM CPU GPU;do hasre "$base" "$label +([0-9][0-9]|--)" "$label label + 2-char value";done
has "$base" 'EFF    HI' "EFF label + effort high = HI"
has "$base" 'CTX    42' "CTX label + context 42"
# Table labels: model names, sum rows, reset countdown (resets_at 0 is no data -> dash).
for label in 'Fable 5.1' 'Opus 5.5' 'Sonnet 5.5' 'Haiku 4.5' 'GPT-6.2 Astra' 'GPT-6.2 Sol' 'GPT-6.1 Terra' 'GPT-6 Luna';do has "$base" "$label" "$label label";done
has "$base" '5H —     Σ' "Claude 5H row: bar label, reset dash (resets_at 0), Σ"
has "$base" '7D —     $' "Claude 7D row: bar label, reset dash (resets_at 0), \$"
# Bar fill: 5 cells, n = (pct*5+50)/100, at least 1 when pct > 0. EFF high 60% = 3, Claude 5H 41% = 2,
# CTX 42% = 2, Claude 7D 2.0000000000000004% = 1, Codex without data = 0.
eq "$(bars_rows56)" '5 HI 3;5 5H 2;5 5H 0;6 42 2;6 7D 1;6 7D 0;' "bar fill: EFF 3, Claude 5H 2, Codex 5H 0, CTX 2, Claude 7D 1, Codex 7D 0"
lacks "$base" '00002%' "percentage regression"
lacks "$base" '0000000' "float noise in rendered numbers"
lacks "$base" ELAPSED "ELAPSED removed"
lacks "$base" '00:12:34' "elapsed value removed"
for label in TOTAL 'ANTH ALL' 'CC ALL' 'OAI ALL' 'CODEX SEEN' 'API $' 'CUM 1D' 'CUM USE';do lacks "$base" "$label" "retired label $label stays removed"; done
if printf '%s\n' "$base" | sed -n '2,7p' | awk -F'│' '{for(i=2;i<=NF;i++) if($i ~ /…/) exit 1}'; then ok; else bad "no ellipsis inside the model tables"; fi
# Colors (raw): chrome violet, label slate, tier teal per model name.
has "$baseraw" $'\033[38;2;120;86;168m' "box border violet escape present (raw)"
has "$baseraw" $'\033[38;2;158;166;190m' "label slate escape present (raw)"
has "$baseraw" $'\033[38;2;130;245;205mFable 5.1' "Fable 5.1 top-tier teal (raw)"
has "$baseraw" $'\033[38;2;112;213;186mOpus 5.5' "Opus 5.5 tier-2 teal (raw)"
has "$baseraw" $'\033[38;2;95;182;167mSonnet 5.5' "Sonnet 5.5 tier-3 teal (raw)"
has "$baseraw" $'\033[38;2;77;151;148mHaiku 4.5' "Haiku 4.5 tier-4 teal (raw)"
has "$baseraw" $'\033[38;2;130;245;205mGPT-6.2 Astra' "GPT-6.2 Astra top-tier teal (raw)"
has "$baseraw" $'\033[38;2;112;213;186mGPT-6.2 Sol' "GPT-6.2 Sol tier-2 teal (raw)"
has "$baseraw" $'\033[38;2;95;182;167mGPT-6.1 Terra' "GPT-6.1 Terra tier-3 teal (raw)"
has "$baseraw" $'\033[38;2;77;151;148mGPT-6 Luna' "GPT-6 Luna tier-4 teal (raw)"

# ---------------------------------------------------------------- 2. current-model highlight (reverse video)
hl_fixture="$WORK/hl.json"
jq '.model.id = "claude-haiku-4-5"' "$FIXTURE" >"$hl_fixture"
run_case "$hl_fixture"
has "$RAW" $'\033[38;2;77;151;148m\033[7mHaiku 4.5' "model.id highlights Haiku 4.5 row (reverse video)"
lacks "$RAW" $'\033[7mSonnet 5.5' "only the running model is highlighted"
jq '.model.display_name = "Sonnet 5.5"' "$FIXTURE" >"$hl_fixture"
run_case "$hl_fixture"
has "$RAW" $'\033[38;2;95;182;167m\033[7mSonnet 5.5' "display-name fallback highlights Sonnet 5.5 row"

# ---------------------------------------------------------------- 3. seeded cache (new collector schema)
now=$(date +%s); h5r=$((now+7200)); d7r=$((now+3*86400))
cat >"$HOME/.claude/statusline-domi-cache.json" <<EOF
{"session_id":"sess-test","codex":{"h5":{"used_pct":87,"resets_at":$h5r},"d7":{"used_pct":29,"resets_at":$d7r},"observed_at":$now},
"cum_use":{"tokens":2800000000,"cost":2517.4},"claude_d7":{"cost":271.4},"openai_total_d7":{"tokens":10100000},"generated_at":$now,
"claude_today":{"tokens":1000150,"cost":3.00035},"openai_today":{"tokens":5500,"cost":0.0225},
"claude_h5":{"tokens":2500000,"cost":12.5},"openai_h5":{"tokens":7000,"cost":0.4},
"claude_all":{"tokens":2600000000,"cost":2200},"openai_all":{"tokens":150000000,"cost":300},"free_all":{"tokens":50000000,"equiv_cost":17.4},
"cache_pct":{"claude":83,"openai":61},
"free_windows":{"session":{"tokens":25000,"equiv_cost":1.2},"today":{"tokens":30000,"equiv_cost":2.5},"d7":{"tokens":410000,"equiv_cost":35.3},"d28":{"tokens":900000,"equiv_cost":60}},
"free_top4_d7":[{"model":"gemini-flash-lite-latest","tokens":348400,"session":{"tokens":20000,"equiv_cost":1.2},"d7":{"tokens":348400,"equiv_cost":34.9},"h5":{"tokens":1000,"equiv_cost":0.2},"d1":{"tokens":2000,"equiv_cost":0.5},"d28":{"tokens":400000,"equiv_cost":40},"all":{"tokens":500000,"equiv_cost":50}},
{"model":"nvidia/nemotron-3-super-120b-a12b:free","tokens":39500,"session":{"tokens":5000,"equiv_cost":0.02},"d7":{"tokens":39500,"equiv_cost":0.4}},
{"model":"codestral-latest","tokens":22800,"session":{"tokens":0},"d7":{"tokens":22800}}],
"models":{"claude-fable-5-1":{"session":{"tokens":7700000,"tokens_noncache":700000,"cost":6.4},"d1":{"tokens":1500000,"cost":3},"d7":{"tokens":7300000,"cost":15},"d28":{"tokens":20000000,"cost":41.9},"all":{"tokens":30000000,"cost":80},"h5":{"tokens":900000}},
"claude-opus-5-5":{"session":{"tokens":0},"d7":{"tokens":259000000,"cost":181}},
"claude-sonnet-5-5":{"session":{"tokens":4000000,"tokens_noncache":300000,"cost":1.3},"d7":{"tokens":76000000,"cost":26}},
"claude-haiku-4-5":{"session":{"tokens":3700,"tokens_noncache":0,"cost":0.5},"d7":{"tokens":85000000,"cost":14}},
"gpt-6-astra":{"session":{"tokens":0},"d7":{"tokens":2800000,"cost":4}},
"gpt-6-sol":{"session":{"tokens":0},"d7":{"tokens":3400000,"cost":9},"d28":{"tokens":9000000,"cost":45}},
"gpt-5.6-terra":{"session":{"tokens":0},"d7":{"tokens":0}},"gpt-6-luna":{"session":{"tokens":0},"d7":{"tokens":0}}}}
EOF
SIDFIX="$WORK/sid.json"; jq '.session_id = "sess-test"' "$FIXTURE" >"$SIDFIX"
run_case "$SIDFIX"; seeded=$DISPLAY; seededraw=$RAW
# Longest abbreviated FREE name is 8 chars (Nemo3Sup, Codstral), so the box grows from 147 to 148.
width_gate 148; sep_gate; border_gate
STATUSLINE_STRICT=1 bash "$SCRIPT" < "$SIDFIX" >"$strict_raw" 2>"$strict_err" && ok || bad "strict seeded exit 0"
[ ! -s "$strict_err" ] && ok || bad "strict seeded stderr empty"
# Ended Codex 5H window: resets_at null, OpenAI 5H tokens 0 -> OAI 5H countdown is a dash, box width unchanged.
jq '.codex.h5.resets_at = null | .openai_h5.tokens = 0 | .openai_h5.cost = 0' "$HOME/.claude/statusline-domi-cache.json" >"$WORK/ended_cache.json"
cp "$HOME/.claude/statusline-domi-cache.json" "$WORK/seeded_cache.bak"; cp "$WORK/ended_cache.json" "$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"; ended=$DISPLAY
width_gate 148; sep_gate; border_gate
has "$ended" '5H —     Σ    0    —    — 6.2M' "ended Codex 5H window: OAI 5H countdown is a dash, Σ 5H tokens 0"
lacks "$ended" '5H 1h' "ended Codex 5H window: no countdown left on any 5H row"
cp "$WORK/seeded_cache.bak" "$HOME/.claude/statusline-domi-cache.json"
# ANT table: SESS 5H 1D 7D 30D ALL (k/M below 100M, billions from 100M).
has "$seeded" 'Fable 5.1     7.7M 900k 1.5M 7.3M  20M  30M' "Fable row tokens"
has "$seeded" 'Sonnet 5.5    4.0M    —    —  76M    —    —' "Sonnet row tokens"
has "$seeded" 'Haiku 4.5       4k    —    —  85M    —    —' "Haiku row tokens"
has "$seeded" 'Σ  12M 900k 1.5M .43B  20M  30M' "ANT token sums (session 11.7M, 7D 427M)"
has "$seeded" '$    8   13    3  236   42   80' "ANT dollar sums: session 8, 5H 13, 1D 3, 7D 236, 30D 42, ALL 80"
lacks "$seeded" '$6.4' "no cents at or above \$0.50"
# OAI table.
has "$seeded" 'GPT-6 Sol        0    —    — 3.4M 9.0M    —' "Sol row tokens"
has "$seeded" 'Σ    0    —    — 6.2M 9.0M    —' "OAI token sums"
has "$seeded" '~    —  .40    —   13   45    —' "OAI dollar sums: null cost is a dash, cents under \$0.50"
# FREE table: abbreviated names, vendor prefix dropped.
has "$seeded" 'GemFlLt   20k   1k   2k 348k 400k 500k' "free #1 fields"
has "$seeded" 'Nemo3Sup   5k    0    0  40k    0    0' "free #2 fields"
has "$seeded" 'Codstral    0    0    0  23k    0    0' "free #3 fields"
has "$seeded" 'Σ  25k   1k   2k 411k 400k 500k' "free token sums"
has "$seeded" '$    1  .20    1   35   40   50' "free dollar sums (equivalent)"
lacks "$seeded" 'nvidia/' "free vendor prefix dropped"
# Col 1: session burn rate, all-time tokens, all-time dollars (Claude + OpenAI + free).
has "$seeded" 'TPM 83k' "TPM = 1.0M non-cache session tokens / 12 min (cache reads excluded)"
has "$seeded" 'TOK 2.80B' "TOK = 2.6B + 150M + 50M"
has "$seeded" 'DOL $2.5k' "DOL = 2200 + 300 + 17.4"
# Token colour (raw escapes). Model cells in SESS 5H 1D 7D 28D: cost-weighted pace (spec 043), permille = clamp(500 + 250*log2(r), 0, 1000); this cache has no pace block, so those cells are grey 128;128;136. The ALL column keeps LOG share of the column max over the 12 model cells.
# Σ token cells follow the Σ dollar cells (same pace colour, columns SESS to 28D), no history_days in this cache -> days 28. No noise floor (only zero/missing is dim).
# RGB = (255t/1000, 224-122t/1000, 255-41t/1000), integer division, t = permille.
# TPM 83k: fixed bands, between mid 20k and hi 200k -> permille 809.
has "$seededraw" $'\033[38;2;206;126;222m83k' "TPM 83k sits on the fixed ramp at permille 809 (raw)"
# (1) Old cache without pace fields: a model window cell is grey 128;128;136 (unknown is not zero), not a share ramp colour.
has "$seededraw" $'\033[38;2;128;128;136m .26B' "Opus 7D 259M, no pace block: grey (raw)"
# (2) Haiku 7D 85M: no pace block -> grey.
has "$seededraw" $'\033[38;2;128;128;136m  85M' "Haiku 7D 85M, no pace block: grey (raw)"
# (2b) ANT Σ 7D .43B follows the Σ dollar cell: d28 = 41.9, expected = 41.9*168/672 = 10.475, r = 236/10.475 = 22.5 -> permille 1000 -> 255;102;214.
has "$seededraw" $'\033[38;2;255;102;214m .43B' "ANT Σ 7D .43B follows dollar pace (r 22.5), saturates at permille 1000 (raw)"
# (3) OAI Σ 7D 6.2M follows the dollar cell: d7 13, d28 45, expected = 45*168/672 = 11.25, r = 1.1556, log2 r = 0.2085 -> permille 552 -> 255*552/1000=140, 224-122*552/1000=157, 255-41*552/1000=233.
has "$seededraw" $'\033[38;2;140;157;233m 6.2M' "OAI Σ 7D 6.2M follows dollar pace r 1.1556 -> permille 552 -> 140;157;233 (raw)"
# (3b) (d) ANT Σ 5H 900k was under the old 1M floor (CD); now paced: d28 = 20M, expected = 20M*5/672 = 148810, r = 6.05 >= 2 -> permille 1000 -> 255;102;214.
has "$seededraw" $'\033[38;2;255;102;214m 900k' "ANT Σ 5H 900k (old floor: CD) now paced: r 6.05 saturates at permille 1000 (raw)"
# (3c) FREE Σ 7D 411k follows the dollar cell: d7 35.3, d28 40, expected 10, r = 3.53, log2 r = 1.8195 -> permille 954 -> 243;108;216.
has "$seededraw" $'\033[38;2;243;108;216m 411k' "FREE Σ 7D 411k follows dollar pace r 3.53 -> permille 954 -> 243;108;216 (raw)"
# (4) FREE Σ 30D (history unknown) renders neutral CN 158;166;190; ALL (logshare) renders 103;175;239 (500k vs 30M max: log10(.01667)=-1.7782 -> 407 -> RGB).
has "$seededraw" $'\033[38;2;158;166;190m 400k\033[0m\033[38;2;103;175;239m 500k' "FREE Σ 30D 400k neutral CN, ALL 500k logshare 407 -> 103;175;239 (raw)"
# (5) sharecols max is exactly 1000 (not 999 from float error). Columns: 1D = 367123456 max, 58000 lo; hand: 1000*58000/367123456 = 0.16 -> 0; max cell -> 1000.
sharecols_src=$(sed -n "/^sharecols/,/^ END/p" "$SCRIPT"); got=$(printf '%s\n%s' "$sharecols_src" 'sharecols — 48000000 367123456 1 1 1 — 214000 4300000 1 1 1 — 0 58000 1 1 1' | bash | sed -n 3p); [ "$got" = 1000 ] && ok || bad "sharecols: 1D max 367123456 is exactly 1000, not 999 from float error"
got=$(printf '%s\n%s' "$sharecols_src" 'sharecols 5 — 0 x -3 7 10 1 2 3 4 5' | bash | tr '\n' ' '); [ "$got" = "899 NA NA NA NA 1000 1000 1000 1000 1000 1000 951 " ] && ok || bad "sharecols: mixed set (col i%6; hand: col0 5 vs max 10 = 1+log10(.5)/3 = .8997 -> 899; col5 5 vs max 7 = 1+log10(5/7)/3 = .9513 -> 951) -> 899 NA NA NA NA 1000 1000 1000 1000 1000 1000 951, got $got"
# (a) logshare: col 0 values max=1000000, max/10, max/1000, max/10000. Hand: 1000*(1+log10(.1)/3)=666.7 -> 666; max/1000: 1000*(1-1)=0; max/10000: 1000*(1-4/3)=-333 -> clamp 0.
got=$(printf '%s\n%s' "$sharecols_src" 'sharecols 1000000 1 1 1 1 1 100000 1 1 1 1 1 1000 1 1 1 1 1 100 1 1 1 1 1' | bash | sed -n '1p;7p;13p;19p' | tr '\n' ' '); [ "$got" = "1000 666 0 0 " ] && ok || bad "logshare: max, max/10, max/1000, max/10000 -> 1000 666 0 0, got $got"
# (e) CLK formula pure check: 600 s -> 500+500*log(1/6)/log 6 = 0; 3600 s -> 500; 21600 s -> 500+500 = 1000.
clk_src=$(grep '^_clkp=' "$SCRIPT"); got=$(for s_ in 600 3600 21600; do bash -c "ramp_c(){ _c=; }; sess_s=$s_; $clk_src; printf '%s ' \"\$_clkp\""; done); [ "$got" = "0 500 1000 " ] && ok || bad "CLK formula: 600/3600/21600 s -> 0 500 1000, got $got"
# (e) CLK colour, fixture session 754 s: log(754/3600)/log 6 = -1.56334/1.79176 = -0.87250 -> 500-436.25 = 63.75 -> 63 -> r 255*63/1000=16, g 224-122*63/1000=224-7=217, b 255-41*63/1000=255-2=253; bold prefix kept.
has "$baseraw" $'\033[1m\033[38;2;16;217;253m12m' "CLK 12m (754 s) hue ramp permille 63 -> 16;217;253 with bold (raw)"
# (d) TOK (all-time tokens) is neutral: cache_ok=1 -> CN 158;166;190, no concentration ramp.
has "$seededraw" $'\033[38;2;158;166;190m2.80B' "TOK renders neutral CN 158;166;190 (raw)"
# Provider totals: variant cache that adds provider_windows for ANT only (OAI and FREE absent -> per-cell row-sum fallback).
# ANT d7 300M, d28 1000M, all 2.6B; row sums are Fable-only 30D 20M and 7D 427M, so the cells differ from the fallback.
now=$(date +%s)
jq '.provider_windows={claude:{h5:{tokens:3000000,cost:14},d1:{tokens:1200000,cost:3.5},d7:{tokens:300000000,cost:150},d28:{tokens:1000000000,cost:500},all:{tokens:2600000000,cost:2200}}}' "$HOME/.claude/statusline-domi-cache.json" >"$WORK/pw.json"
cp "$HOME/.claude/statusline-domi-cache.json" "$WORK/seed_nopw.json"; cp "$WORK/pw.json" "$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"; pwd_=$DISPLAY; pwraw=$RAW
cp "$WORK/seed_nopw.json" "$HOME/.claude/statusline-domi-cache.json"
# (i) ANT Σ shows max(provider_windows, row sum): 5H 3.0M, 1D max(1.2M, 1.5M)=1.5M, 7D max(300M, 427M)=.43B, 30D 1000M (1.0B), ALL 2.6B; SESS stays row sum 12M.
has "$pwd_" 'Σ  12M 3.0M 1.5M .43B 1.0B 2.6B' "ANT Σ = max(provider, row sum): SESS 12M, 5H 3.0M, 1D 1.5M (max of 1.2M, row 1.5M), 7D .43B (max of 300M, row 427M), 30D 1.0B, ALL 2.6B"
lacks "$pwd_" 'Σ  12M 3.0M 1.2M .30B  20M' "ANT Σ 7D is not provider 300M; it's row sum 427M which is larger"
# ANT $ = max(provider_windows, row sum) costs: 5H 14, 1D max(3.5, 3)=3.5->4, 7D max(150, 236)=236, 30D max(500, 42)=500, ALL max(2200, 80)=2.2k; SESS stays row sum 8.
hasre "$pwd_" '\$ +8 +14 +4 +236 +500 +2\.2k' "ANT \$ = max(provider, row sum): SESS 8, 5H 14, 1D 4, 7D 236 (max of 150, 236), 30D 500, ALL 2.2k"
# (ii) ANT Σ 7D follows the dollar cell: $ 7D = max(150, 236) = 236; d28 $ = 500, expected 500*168/672 = 125.
# r = 1.888, log2 r = 0.9189, permille = int(500+229.7) = 729 -> RGB: 255*729/1000 = 185; 224-122*729/1000 = 136; 255-41*729/1000 = 226.
has "$pwraw" $'\033[38;2;185;136;226m .43B' "ANT Σ 7D follows dollar pace 236 vs expected 125: r 1.888, permille 729 -> 185;136;226 (raw)"
# (iii) Fallback: provider_windows absent -> Σ equals the row sum (seeded cache: 7D 427M, 30D 20M).
has "$seeded" 'Σ  12M 900k 1.5M .43B  20M  30M' "no provider_windows: ANT Σ falls back to the row sum"
# OAI has no provider_windows in the variant -> per-cell fallback to its row sums (7D 6.2M, 30D 9.0M).
has "$pwd_" 'Σ    0    —    — 6.2M 9.0M    —' "OAI Σ per-cell fallback to row sums when its provider_windows is absent"
# (iv) pwmax: provider_windows value below row sum -> row sum renders in the cell. ANT d28 cost 41.07 < row sum 42.
pwmax_variant="$WORK/pwmax.json"
jq '.provider_windows.claude.d28.cost=41.07' "$WORK/pw.json" >"$pwmax_variant"
cp "$pwmax_variant" "$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"; pwmax_out=$DISPLAY; hasre "$pwmax_out" '\$ +8 +14 +4 +236 + 42 +2\.2k' "provider_windows ANT d28 \$ 41.07 < row sum 42: d28 and 7D both show row sums via pwmax"
cp "$WORK/seed_nopw.json" "$HOME/.claude/statusline-domi-cache.json"
# DOL: neutral CN (sums three pricing methods), not a concentration ramp.
has "$seededraw" $'\033[38;2;158;166;190m$2.5k' "DOL renders neutral CN 158;166;190 (raw)"
# Dollar cells: pace colour per provider vs its own 28-day rate (SPEC.md "Dollar cells"). permille = clamp(500 + 250*log2(r), 0, 1000), r = value / (d28 * hours / 672).
# (1) ANT 7D: d28 = 41.9 (30D cell), expected = 41.9*168/672 = 10.475, r = 236/10.475 = 22.5 >= 2 -> permille 1000 -> 255;102;214.
has "$seededraw" $'\033[38;2;255;102;214m  236' "ANT 7D \$ 236 vs expected 10.475 (r 22.5) saturates at permille 1000 (raw)"
# (1b) OAI 7D: d28 = 45, expected = 45*168/672 = 11.25, r = 13/11.25 = 1.1556, log2 r = 0.2085 -> permille 552 -> 140;157;233.
has "$seededraw" $'\033[38;2;140;157;233m   13' "OAI 7D \$ 13 vs expected 11.25 (r 1.1556) at permille 552 (raw)"
# (2) No history_days in this cache (unknown): ANT 30D $ 42 stays neutral CN.
has "$seededraw" $'\033[38;2;158;166;190m   42' "ANT 30D \$ 42 renders neutral CN when history_days is unknown (raw)"
# (3) (d) FREE 5H \$ .20 was under the old \$1 floor (CD); now paced: d28 = 40, expected = 40*5/672 = 0.2976, r = 0.672, log2 r = -0.5735 -> permille 356 -> r 255*356/1000=90, g 224-122*356/1000=224-43=181, b 255-41*356/1000=255-14=241.
has "$seededraw" $'\033[38;2;90;181;241m  .20' "FREE 5H \$ .20 (old floor: CD) now paced: r 0.672 at permille 356 (raw)"
# (4) OAI row label is ~ (estimated pricing); ANT keeps \$.
hasre "$seeded" '7D +[0-9a-z—]+ +~ ' "OAI dollar row label is ~"
# (5) SESS pace floor is 5 min (operator, 2026-11-18). 12 min (754 s): SESS \$ 8 is paced: d28 = 41.9, no history_days -> days 28, expected = 41.9*(754/3600)/672 = 0.01306, r = 628 -> permille 1000 -> 255;102;214.
has "$seededraw" $'\033[38;2;255;102;214m    8' "ANT SESS \$ 8 in a 12 min session is paced, r 628 saturates (raw)"
# 4 min (240 s) is under the floor: SESS \$ renders CD.
jq '.cost.total_duration_ms=240000' "$SIDFIX" >"$WORK/sid4m.json"; run_case "$WORK/sid4m.json"
has "$RAW" $'\033[38;2;128;128;136m    8' "ANT SESS \$ 8 in a 4 min session renders CD (raw)"
# (e) Zero token cell stays dim and is left out of the rank set.
has "$seededraw" $'\033[38;2;128;128;136m    0' "zero token cell is dim (raw)"
# Rate-limit bars: Codex 5H 87% = 4 cells, Codex 7D 29% = 1 cell; Claude unchanged.
eq "$(bars_rows56)" '5 HI 3;5 5H 2;5 5H 4;6 42 2;6 7D 1;6 7D 1;' "bar fill with Codex data: 5H 4, 7D 1"
hasre "$seeded" '5H +[12]h[0-9]+m +Σ' "Codex 5H reset countdown in hours"
hasre "$seeded" '7D +(2d23h|3d0h) +~' "Codex 7D reset countdown in days"
eq "$(printf '%s' "$seeded" | grep -o '5H —' | wc -l | tr -d ' ')" 1 "only the Claude 5H countdown is a dash; Codex reset is known"

# history_days baseline (SPEC.md "Dollar cells"): seed Fable 30D $ = 236 and history_days.claude = 10 -> days = min(28,10) = 10.
# ANT 7D $ 236: d28 = 236, 7D window = min(168, 10*24) = 168 h, expected = 236*168/(10*24) = 165.2, r = 1.4286, log2 r = 0.5146 -> permille 628 -> r 255*628/1000=160, g 224-122*628/1000=224-76=148, b 255-41*628/1000=255-25=230.
# Without history_days (28 days) the same cell would have expected 59, r = 4, saturated magenta.
cp "$HOME/.claude/statusline-domi-cache.json" "$WORK/seed_keep.json"
jq '.history_days={claude:10,openai:null,free:null} | .models["claude-fable-5-1"].d28.cost=236' "$WORK/seed_keep.json" >"$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"
has "$RAW" $'\033[38;2;160;148;230m  236' "history_days.claude=10: ANT 7D \$ 236, d28 236, days 10, expected 165.2, r 1.4286, permille 628 (raw)"
# 28D pace: history_days.claude = 60 (> 28). ANT dollars: 28D 42, ALL 80 -> expected = 80*28/60 = 37.33, r = 41.9/37.33 = 1.1223, log2 r = 0.1665 -> permille 541 -> r 255*541/1000=137, g 224-122*541/1000=224-66=158, b 255-41*541/1000=255-22=233.
# The Σ token 28D cell follows the dollar cell, so both share that colour.
jq '.history_days={claude:60,openai:null,free:null}' "$WORK/seed_keep.json" >"$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"
has "$RAW" $'\033[38;2;137;158;233m  20M' "history 60: ANT Σ 28D 20M follows dollar pace (r 1.1223) at permille 541 (raw)"
has "$RAW" $'\033[38;2;137;158;233m   42' "history 60: ANT 28D \$ 42 vs expected 37.33 (r 1.1223) at permille 541 (raw)"
has "$RAW" $'\033[38;2;255;102;214m  30M' "history 60: ANT Σ ALL 30M logshare max -> permille 1000 -> 255;102;214 (raw)"
# (c) history_days = 28 (not > 28): 30D stays neutral CN.
jq '.history_days={claude:28,openai:null,free:null}' "$WORK/seed_keep.json" >"$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"
has "$RAW" $'\033[38;2;158;166;190m  20M' "history 28: ANT Σ 30D 20M stays neutral CN (raw)"
has "$RAW" $'\033[38;2;158;166;190m   42' "history 28: ANT 30D \$ 42 stays neutral CN (raw)"
cp "$WORK/seed_keep.json" "$HOME/.claude/statusline-domi-cache.json"
# ---- Pace colour of model cells (spec 043 Phase 6). Variant cache with a pace block per row.
# Rows (pace usd_per_day 10, days 28 unless noted): expected 5H = 10*5/24 = 2.0833; 7D = 10*7 = 70; 28D = all_cost*28/hist_days = 84*28/60 = 39.2.
# Fable 5H 0.5 (r .24 -> 0;224;255) 7D 70.0001 and 28D 39.2001 (r 1 -> 127;163;235); Opus 5H 2.0834 (r 1 -> 127;163;235), 7D 280 (r 4 -> 255;102;214), 28D 9.7 (r .247 -> 0;224;255);
# Sonnet 5H 8.4 (r 4.03 -> 255;102;214), 7D 26 (r .371, permille 142 -> 36;207;250), 28D hist 20 -> neutral CN; Haiku null pace -> grey. SESS: 754 s (12 min, over the 5 min floor) is paced: Fable cost 6.4 vs 10*(754/3600)/24 = 0.0872 (r 73), Sonnet 1.3 (r 14.9), FREE 1.2 (r 13.8) all saturate -> 255;102;214.
G=$'\033[38;2;128;128;136m'; Z=$'\033[0m'; C0=$'\033[38;2;0;224;255m'; C1=$'\033[38;2;127;163;235m'; C4=$'\033[38;2;255;102;214m'
PACE_P='{usd_per_day:10,days:28,hist_days:60,all_cost:84,source:"own"}'
jq "
 .models[\"claude-fable-5-1\"] |= (.h5={tokens:900000,cost:0.5} | .d7.cost=70.0001 | .d28.cost=39.2001 | .pace=$PACE_P)
 | .models[\"claude-opus-5-5\"] |= (.h5={tokens:1000000,cost:2.0834} | .d7={tokens:259000000,cost:280} | .d28={tokens:50000000,cost:9.7} | .pace=$PACE_P)
 | .models[\"claude-sonnet-5-5\"] |= (.h5={tokens:2500000,cost:8.4} | .d7={tokens:76000000,cost:26} | .d28={tokens:10000000,cost:5} | .pace={usd_per_day:10,days:28,hist_days:20,all_cost:30,source:\"family\"})
 | .models[\"claude-haiku-4-5\"] |= (.h5={tokens:4000,cost:1} | .d28={tokens:20000000,cost:3} | .pace={usd_per_day:null,days:null,hist_days:null,all_cost:null,source:null})
 | .free_top4_d7[0] |= (.h5.equiv_cost=2.0834 | .pace=$PACE_P)" "$WORK/seed_keep.json" >"$WORK/pace.json"
cp "$WORK/pace.json" "$HOME/.claude/statusline-domi-cache.json"; run_case "$SIDFIX"; pace_d=$DISPLAY; pace_raw=$RAW
width_gate 148; sep_gate; border_gate
has "$pace_raw" "${C4} 7.7M${Z}${C0} 900k" "Fable 5H r 0.24 -> 0;224;255 (raw)"
has "$pace_raw" "${G}    0${Z}${C1} 1.0M" "Opus 5H r 1 -> 127;163;235 (raw)"
has "$pace_raw" "${C4} 4.0M${Z}${C4} 2.5M" "Sonnet 5H r 4.03 -> 255;102;214 (raw)"
has "$pace_raw" "${G}   4k${Z}${G}   4k" "Haiku null pace: 5H grey (raw)"
has "$pace_raw" "${C1} 7.3M${Z}${C1}  20M" "Fable 7D r 1 and 28D r 1 (hist 60) -> 127;163;235 (raw)"
has "$pace_raw" "${C4} .26B${Z}${C0}  50M" "Opus 7D r 4 -> 255;102;214, 28D r 0.247 -> 0;224;255 (raw)"
has "$pace_raw" $'\033[38;2;36;207;250m  76M\033[0m\033[38;2;158;166;190m  10M' "Sonnet 7D r 0.371 -> 36;207;250, 28D neutral CN with history 20 (raw)"
has "$pace_raw" "${G}  85M${Z}${G}  20M" "Haiku null pace: 7D and 28D grey (raw)"
has "$pace_raw" "${C4}  20k${Z}${C1}   1k" "FREE row paced like any other: 5H r 1 -> 127;163;235 (raw)"
has "$pace_raw" "${G} 3.4M${Z}${G} 9.0M" "OAI rows without a pace block: grey (raw)"
lacks "$pace_d" legend "no legend on screen"
# 1D uses hours since local midnight, floor 6: Fable 1D cost = 10*h/24*1.0001 -> r 1 -> 127;163;235.
_h=$(date +'%H %M' | awk '{m=$1*60+$2;h=m/60;if(h<6)h=6;printf "%.6f",10*h/24*1.0001}')
jq --argjson c "$_h" '.models["claude-fable-5-1"].d1={tokens:1500000,cost:$c}' "$WORK/pace.json" >"$HOME/.claude/statusline-domi-cache.json"; run_case "$SIDFIX"
has "$RAW" "${C0} 900k${Z}${C1} 1.5M" "Fable 1D r 1 at hours since midnight (floor 6) -> 127;163;235 (raw)"
# SC-007: another model growing tenfold in the same column leaves a cell's escape unchanged.
jq '.models["claude-sonnet-5-5"].h5={tokens:25000000,cost:84}' "$WORK/pace.json" >"$HOME/.claude/statusline-domi-cache.json"; run_case "$SIDFIX"
has "$RAW" "${G}    0${Z}${C1} 1.0M" "Opus 5H cell colour unchanged when Sonnet 5H grows tenfold (raw)"
# SESS: duration 2 h -> expected 10*2/24 = 0.8333; Fable session cost 0.8334 -> r 1 -> 127;163;235.
jq '.cost.total_duration_ms=7200000' "$SIDFIX" >"$WORK/sid2h.json"
jq '.models["claude-fable-5-1"].session.cost=0.8334' "$WORK/pace.json" >"$HOME/.claude/statusline-domi-cache.json"; run_case "$WORK/sid2h.json"
has "$RAW" "${C1} 7.7M${Z}${C0} 900k" "Fable SESS r 1 with a 2 h session -> 127;163;235 (raw)"
cp "$WORK/seed_keep.json" "$HOME/.claude/statusline-domi-cache.json"
# Capture identity (SC-010): ALL column, gauges and names byte-identical to the pre-change capture; only model, Σ and dollar window cells may differ.
CAPD="$DIR/../../capture"
if [ -f "$CAPD/truecolor.raw" ] && [ -f "$CAPD/cache.json" ] && [ -f "$CAPD/session.json" ]; then
 CAPH="$WORK/caphome"; mkdir -p "$CAPH/.claude/statusline-cache"
 jq --argjson n "$(date +%s)" '.generated_at=$n' "$CAPD/cache.json" >"$CAPH/.claude/statusline-cache/cap043.json"
 for m in truecolor 256 nocolor; do
  case $m in truecolor) e=(COLORTERM=truecolor);; 256) e=(STATUSLINE_COLORS=256);; *) e=(NO_COLOR=1);; esac
  env HOME="$CAPH" "${e[@]}" bash "$SCRIPT" <"$CAPD/session.json" >"$WORK/cap.$m" 2>/dev/null
  python3 "$WORK/probe.py" mask <"$WORK/cap.$m" >"$WORK/cap.$m.mask"; python3 "$WORK/probe.py" mask <"$CAPD/$m.raw" >"$WORK/cap.$m.want"
  cmp -s "$WORK/cap.$m.mask" "$WORK/cap.$m.want" && ok || bad "capture $m: ALL column, gauges and names byte-identical to $m.raw (window cells masked)"
 done
fi
# No session id in the payload: the session is unknown, so SESS and TPM show a dash (cache stays trusted for windows).
run_case "$FIXTURE"; has "$DISPLAY" 'TPM —' "payload without session id: TPM is a dash"
hasre "$DISPLAY" 'Fable 5.1 +— +900k' "payload without session id: SESS cell is a dash, windows kept"
# Cache older than 5 min: SESS dash, window cells dim.
sed "s/\"generated_at\":[0-9]*/\"generated_at\":$((now-1000))/" "$HOME/.claude/statusline-domi-cache.json" >"$WORK/stale.json"
cp "$HOME/.claude/statusline-domi-cache.json" "$WORK/fresh.json"; cp "$WORK/stale.json" "$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"; has "$DISPLAY" 'AGE 16m' "stale cache: left-column TPM cell shows the cache age (1000 s = 16m)"
lacks "$DISPLAY" 'TPM' "stale cache: no TPM label"
hasre "$DISPLAY" 'Fable 5.1 +— +900k' "stale cache: SESS cell is a dash"
has "$RAW" $'\033[38;2;128;128;136m 900k' "stale cache: window cell renders dim (raw)"
has "$RAW" $'\033[38;2;128;128;136m 7.3M' "stale cache: ANT model cell (Fable 7D 7.3M) outside SESS renders dim (raw)"
# Spec 042 T070/T071 (operator ruling 2026-11-16, "Age in the left column"): stale cache shows AGE <n><unit> in the TPM cell, grey.
for pair in "420 7m" "10800 3h" "172800 2d"; do
 secs=${pair% *}; want=${pair#* }
 sed "s/\"generated_at\":[0-9]*/\"generated_at\":$((now-secs))/" "$WORK/fresh.json" >"$HOME/.claude/statusline-domi-cache.json"
 run_case "$SIDFIX"; has "$DISPLAY" "AGE $want " "stale cache ${secs}s: TPM cell reads AGE $want"
 lacks "$DISPLAY" 'TPM' "stale cache ${secs}s: no TPM label"
 has "$RAW" $'\033[38;2;128;128;136m'"$want" "stale cache ${secs}s: age value is the grey CD (raw)"
 width_gate 148; sep_gate
done
# Widths equal 148 in truecolor, 256-colour and NO_COLOR with a stale cache (7 minutes).
sed "s/\"generated_at\":[0-9]*/\"generated_at\":$((now-420))/" "$WORK/fresh.json" >"$HOME/.claude/statusline-domi-cache.json"
for mode in truecolor 256 nocolor; do
 case "$mode" in truecolor) raw=$(bash "$SCRIPT" < "$SIDFIX" 2>/dev/null);; 256) raw=$(STATUSLINE_COLORS=256 bash "$SCRIPT" < "$SIDFIX" 2>/dev/null);; *) raw=$(NO_COLOR=1 bash "$SCRIPT" < "$SIDFIX" 2>/dev/null);; esac
 DISPLAY=$(printf '%s' "$raw"|sed $'s/\033\[[0-9;]*m//g'); has "$DISPLAY" 'AGE 7m' "stale cache, $mode: AGE 7m"; width_gate 148
done
# Age text steps: 45 s, 7 m, 3 h, 2 d (a 45 s cache is never stale, so the formatter is tested directly).
age_src=$(grep '^age_txt()' "$SCRIPT"); [ -n "$age_src" ] && ok || bad "age_txt function present"
for pair in "45 45s" "420 7m" "10800 3h" "172800 2d" "59 59s" "3599 59m" "86399 23h"; do
 got=$(printf '%s\nage_txt %s; printf %%s "$_age"' "$age_src" "${pair% *}" | bash); eq "$got" "${pair#* }" "age_txt ${pair% *} -> ${pair#* }"
done
# Fresh cache: TPM as today. Unreadable cache: dash as today.
cp "$WORK/fresh.json" "$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"; has "$DISPLAY" 'TPM 83k' "fresh cache: TPM renders as today"; lacks "$DISPLAY" 'AGE' "fresh cache: no AGE label"
printf 'not json' >"$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"; has "$DISPLAY" 'TPM —' "unreadable cache: TPM dash as today"; lacks "$DISPLAY" 'AGE' "unreadable cache: no AGE label"
cp "$WORK/fresh.json" "$HOME/.claude/statusline-domi-cache.json"

# ---------------------------------------------------------------- 4. cache variants and bad input
sed 's/"used_pct":87/"used_pct":null/;s/"used_pct":29/"used_pct":null/' "$HOME/.claude/statusline-domi-cache.json" >"$WORK/nocodex.json"
cp "$WORK/nocodex.json" "$HOME/.claude/statusline-domi-cache.json"
run_case "$SIDFIX"; width_gate 148; sep_gate
eq "$(bars_rows56)" '5 HI 3;5 5H 2;5 5H 0;6 42 2;6 7D 1;6 7D 0;' "Codex bars empty when used_pct is null"

printf 'not json' >"$HOME/.claude/statusline-domi-cache.json"
run_case "$FIXTURE"; width_gate 147; sep_gate; border_gate
has "$DISPLAY" 'TOK —' "corrupt cache shows a dash, not zero totals"
has "$DISPLAY" 'TPM —' "corrupt cache: TPM is a dash"
has "$DISPLAY" 'DOL —' "corrupt cache: DOL is a dash"
rm -f "$HOME/.claude/statusline-domi-cache.json"

empty="$WORK/empty.json"; : >"$empty"
run_case "$empty"; width_gate 147; sep_gate; has "$DISPLAY" 'CLK ' "empty stdin: box with CLK row"; has "$DISPLAY" 'CTX ' "empty stdin: CTX row"
braces="$WORK/braces.json"; printf '{}' >"$braces"
run_case "$braces"; width_gate 147; sep_gate; has "$DISPLAY" 'CTX ' "{} stdin: CTX row"; hasre "$DISPLAY" 'EFF +(--|[A-Z]+)' "{} stdin: EFF row"
STATUSLINE_STRICT=1 bash "$SCRIPT" < "$empty" >"$strict_raw" 2>"$strict_err" && ok || bad "strict empty stdin exit 0"
[ ! -s "$strict_err" ] && ok || bad "strict empty stdin stderr empty"

# ---------------------------------------------------------------- 4b. ranked rows: exact versions, top 4 by 28D then ALL, pin (end to end: collector -> cache -> render)
# Seeded usage.db: Claude ranks sonnet-5 > opus-5 > opus-5-5 > haiku-4-5 > fable-5-1 (5th); OpenAI ranks sol > luna > terra > gpt-5.5 > astra (5th).
RANKDB="$WORK/rank.db"; RANKCFG="$WORK/rank_config.json"; printf 'model = "gpt-6-astra"\nmodel_reasoning_effort = "low"\n[projects.x]\nmodel = "other"\n' >"$WORK/codex_config.toml"
python3 - "$RANKDB" "$RANKCFG" "$WORK" <<'PYEOF'
import json, sqlite3, sys
db, cfgp, work = sys.argv[1:4]
c = sqlite3.connect(db)
c.execute("CREATE TABLE usage(uid TEXT PRIMARY KEY, ts TEXT, day TEXT, backend TEXT, model TEXT, input_tokens INT DEFAULT 0, output_tokens INT DEFAULT 0, cache_read INT DEFAULT 0, cache_write INT DEFAULT 0, reasoning INT DEFAULT 0)")
rows = [("claude", "claude-sonnet-5", 9000000), ("claude", "claude-opus-5", 8000000), ("claude", "claude-opus-5-5", 7000000),
        ("claude", "claude-haiku-4-5-20251001", 6000000), ("claude", "claude-fable-5-1", 5000000),
        ("codex", "gpt-5.6-sol", 9086965), ("codex", "gpt-5.6-luna", 3447889), ("codex", "gpt-5.6-terra", 3000000),
        ("codex", "gpt-5.5", 2000000), ("codex", "gpt-6-astra", 1000000)]
for i, (b, m, t) in enumerate(rows):
    c.execute("INSERT INTO usage(uid,ts,day,backend,model,input_tokens,output_tokens) VALUES (?,?,?,?,?,?,0)", ("u%d" % i, "2026-10-01T00:00:00.000+00:00", "2026-10-01", b, m, t))
c.commit(); c.close()
json.dump({"usage_db": db, "codex_state_db": "", "prices_json": [], "codex_sessions_glob": work + "/none/*.jsonl",
           "codex_config_toml": work + "/codex_config.toml"}, open(cfgp, "w"))
PYEOF
python3 "$DIR/../statusline.d/collect_usage.py" --session-id sess-rank --config "$RANKCFG" --out "$HOME/.claude/statusline-cache/sess-rank.json" --current-claude-model 'claude-fable-5-1[1m]' --force >/dev/null
RANKFIX="$WORK/rank_in.json"; jq '.session_id = "sess-rank" | .model.id = "claude-fable-5-1"' "$FIXTURE" >"$RANKFIX"
run_case "$RANKFIX"; rank=$DISPLAY; rankraw=$RAW
width_gate 147; sep_gate; border_gate
# Full-name labels from the exact id; older versions appear when they rank top 4 (Opus 5 next to Opus 5.5, never merged).
for label in 'Sonnet 5 ' 'Opus 5 ' 'Opus 5.5' 'Fable 5.1' 'GPT-5.6 Sol' 'GPT-5.6 Luna' 'GPT-5.6 Terra' 'GPT-6 Astra';do has "$rank" "$label" "ranked label $label"; done
lacks "$rank" 'Haiku 4.5' "Haiku ranks 4th but the pinned current model (Fable 5.1, 5th) takes row 4"
lacks "$rank" 'GPT-5.5' "gpt-5.5 ranks 4th but the pinned codex config model (gpt-6-astra, 5th) takes OAI row 4"
# Row order: ANT rows 1-4 = Sonnet 5, Opus 5, Opus 5.5, Fable 5.1 (pin in row 4); OAI rows 1-4 = Sol, Luna, Terra, Astra (pin in row 4).
eq "$(printf '%s\n' "$rank" | sed -n '2,5p' | cut -d'│' -f2 | cut -c1-9 | tr '\n' ',')" 'Sonnet 5 ,Opus 5   ,Opus 5.5 ,Fable 5.1,' "ANT row order: top 3 by 28D then ALL (seeded rows all outside 28D, ALL decides), then the pinned current model"
eq "$(printf '%s\n' "$rank" | sed -n '2,5p' | cut -d'│' -f3 | cut -c1-13 | tr '\n' ',')" 'GPT-5.6 Sol  ,GPT-5.6 Luna ,GPT-5.6 Terra,GPT-6 Astra  ,' "OAI row order: top 3 by 28D then ALL (seeded rows all outside 28D, ALL decides), then the pinned config.toml model"
# ALL for gpt-5.6-sol comes from the seeded rows (9,086,965 -> 9.1M), not a dash and not a merged alias.
hasre "$rank" 'GPT-5.6 Sol +[^ ]+ +[^ ]+ +[^ ]+ +[^ ]+ +[^ ]+ +9\.1M' "nonzero ALL for gpt-5.6-sol (9.1M) from the seeded usage db"
hasre "$rank" 'Opus 5 +[^ ]+ +[^ ]+ +[^ ]+ +[^ ]+ +[^ ]+ +8\.0M' "claude-opus-5 keeps its own ALL (8.0M), not merged into Opus 5.5"
# Current-model highlight follows the exact id (claude-fable-5-1 is row 4), tier colour stays by name.
has "$rankraw" $'\033[38;2;130;245;205m\033[7mFable 5.1' "pinned current model row is reverse video, Fable tier teal (raw)"
lacks "$rankraw" $'\033[7mOpus 5' "only the running model is highlighted (Opus rows plain)"
has "$rankraw" $'\033[38;2;112;213;186mOpus 5.5' "Opus 5.5 tier-2 teal (raw)"
has "$rankraw" $'\033[38;2;95;182;167mSonnet 5' "Sonnet 5 tier-3 teal (raw)"
has "$rankraw" $'\033[38;2;130;245;205mGPT-6 Astra' "GPT-6 Astra top-tier teal (raw)"
# Pin inside the top 4 keeps its rank: current model claude-sonnet-5 stays row 1 (highlighted); Fable 5.1 is not pinned over Haiku.
python3 "$DIR/../statusline.d/collect_usage.py" --session-id sess-rank --config "$RANKCFG" --out "$HOME/.claude/statusline-cache/sess-rank.json" --current-claude-model claude-sonnet-5 --force >/dev/null
jq '.model.id = "claude-sonnet-5"' "$RANKFIX" >"$WORK/rank_in2.json"
run_case "$WORK/rank_in2.json"
has "$RAW" $'\033[7mSonnet 5' "pin inside top 4: Sonnet 5 row highlighted in place"
has "$DISPLAY" 'Haiku 4.5' "no pin outside top 4: Haiku 4.5 keeps row 4"
lacks "$DISPLAY" 'Fable 5.1' "Fable 5.1 (5th) stays out when it is not the current model"
rm -f "$HOME/.claude/statusline-domi-cache.json"

# ---------------------------------------------------------------- 5. lbar: 5% steps, one shaded edge cell
# Extract fg/ramp/level helpers and lbar by name, source them in this shell (set -u stays on, so unbound reads fail loudly).
LBAR_TEST="$WORK/lbar_under_test.sh"
{ sed -n '/^# Colour mode/,/^level(){/p' "$SCRIPT"; sed -n '/^lbar(){/,/^tsum(){/{/^tsum(){/!p;}' "$SCRIPT"; } >"$LBAR_TEST"
if grep -q '^lbar(){' "$LBAR_TEST" && grep -q '^level(){' "$LBAR_TEST"; then ok; else bad "lbar and level extracted from statusline.sh"; fi
source "$LBAR_TEST"
strip_ansi(){ sed $'s/\033\[[0-9;]*m//g'; }
# Visible width is 5 for every percentage and for the missing value.
for p in 0 1 4 5 25 26 50 51 74 99 100 —; do
  vis=$(lbar "$p" x | strip_ansi)
  [ "${#vis}" -eq 5 ] && ok || bad "lbar p=$p width=5 (got ${#vis})"
done
# lbar_cells <pct>: "<full> <edge> <edge bg> <fg>" (full: bg == fg; edge: bg differs from fg and from the track).
lbar_cells(){ lbar "$1" x | python3 "$WORK/probe.py" cells; }
want_cells(){ eq "$(lbar_cells "$1" | cut -d' ' -f"$2")" "$3" "lbar p=$1 $4"; }
want_cells 0 1 0 "has 0 full cells"; want_cells 0 2 0 "has 0 edge cells"
want_cells 1 1 0 "has 0 full cells"; want_cells 1 2 1 "has 1 edge cell"
want_cells 5 1 0 "has 0 full cells"; want_cells 5 2 1 "has 1 edge cell"
want_cells 20 1 1 "has 1 full cell"; want_cells 20 2 0 "has 0 edge cells"
want_cells 25 1 1 "has 1 full cell"; want_cells 25 2 1 "has 1 edge cell"
want_cells 100 1 5 "has 5 full cells"; want_cells 100 2 0 "has 0 edge cells"
# p=25: the edge bg is the track blended 1/4 of the way toward the bar color.
edge_want=$(lbar_cells 25 | awk '{n=split($4,f,";");o="";for(i=1;i<=n;i++){t=(i==1?44:i==2?42:56);o=o (i>1?";":"") (t+int((f[i]-t)/4))}print o}')
eq "$(lbar_cells 25 | cut -d' ' -f3)" "$edge_want" "lbar p=25 edge bg is the 1/4 blend"
vis=$(lbar 50 LABEL | strip_ansi); has "$vis" LABEL "lbar p=50 label chars present"

# Colour modes: NO_COLOR strips all colour (bars stay visible as block glyphs), COLORTERM=256color uses 38;5;.
def_w=$(bash "$SCRIPT" < "$SIDFIX" 2>/dev/null|sed $'s/\033\[[0-9;]*m//g'|python3 "$WORK/probe.py" widths|cut -d' ' -f2)
nc_raw=$(NO_COLOR=1 bash "$SCRIPT" < "$SIDFIX" 2>/dev/null)
printf '%s' "$nc_raw" | grep -qE $'\033\\[(38|48);' && bad "NO_COLOR: no 38/48 sequences" || ok
printf '%s' "$nc_raw" | grep -qF '█' && ok || bad "NO_COLOR: bars drawn with block glyphs"
DISPLAY=$(printf '%s' "$nc_raw"|sed $'s/\033\\[[0-9;]*m//g'); width_gate "$def_w"
c256_raw=$(COLORTERM=256color bash "$SCRIPT" < "$SIDFIX" 2>/dev/null)
printf '%s' "$c256_raw" | grep -qF $'\033[38;5;' && ok || bad "256 mode: uses 38;5;"
printf '%s' "$c256_raw" | grep -qE $'\033\\[(38|48);2;' && bad "256 mode: no truecolor sequences" || ok
DISPLAY=$(printf '%s' "$c256_raw"|sed $'s/\033\\[[0-9;]*m//g'); width_gate "$def_w"

total=$((pass+fail))
if [ "$fail" -eq 0 ];then printf 'smoke: %d/%d checks passed\n' "$pass" "$total";exit 0;fi
printf 'smoke: %d/%d checks passed; %d failed\n' "$pass" "$total" "$fail";exit 1
