#!/usr/bin/env bash
# Six-column Claude Code statusline. Bash 3.2; output only; exit 0.
export LC_ALL="${LC_ALL:-C.UTF-8}"
input=$(cat 2>/dev/null)
SL_LOG="$HOME/.claude/statusline-domi.log"; [ -f "$SL_LOG" ] && { exec 2>>"$SL_LOG"; printf 'start %s pid=%s\n' "$(date +%H:%M:%S)" "$$" >&2; }
IFS=$'\037' read -r cwd project_dir model tpath sid total_cost ctx_raw ctx_size dur_ms cl5_raw cl5_reset cl7_raw cl7_reset effort_raw cur_id_raw <<EOF
$(printf '%s' "$input" | jq -r '[.cwd//.workspace.current_dir//"",.workspace.project_dir//"",.model.display_name//"",.transcript_path//"",.session_id//"",.cost.total_cost_usd//"",.context_window.used_percentage//"",(.context_window.context_window_size//200000),.cost.total_duration_ms//"",.rate_limits.five_hour.used_percentage//"",.rate_limits.five_hour.resets_at//"",.rate_limits.seven_day.used_percentage//"",.rate_limits.seven_day.resets_at//"",(.effort.level//.effort//""),(.model.id//"")]|join("\u001f")' 2>/dev/null)
EOF
[ -n "$cwd" ] || cwd="$PWD"; [ -n "$project_dir" ] || project_dir="$cwd"
project=$(basename "$project_dir" 2>/dev/null)
SELF_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd 2>/dev/null)
CACHE="${HOME}/.claude/statusline-domi-cache.json"

# Plan-limit readings for agents (they never see the stdin payload). Atomic write; skipped when absent.
if [ -n "$cl5_raw$cl7_raw" ]; then
  RL_FILE="${HOME}/.claude/statusline-rate-limits.json"
  printf '%s' "$input" | jq -c --argjson at "$(date +%s)" --arg sid "$sid" '{written_at:$at,session_id:$sid,five_hour:.rate_limits.five_hour,seven_day:.rate_limits.seven_day}' >"$RL_FILE.$$" 2>/dev/null && mv -f "$RL_FILE.$$" "$RL_FILE" || rm -f "$RL_FILE.$$"
fi

# Epoch mtime, portable + arithmetic-safe.
# GNU coreutils `stat -f %m` does NOT fail: -f selects *filesystem* status, %m
# is not one of its directives, so GNU echoes the literal "%m" and exits 0 —
# the `|| stat -c %Y` fallback never fires and the caller ends up doing
# $((now - %m)), a bash arithmetic syntax error printed on *unredirected*
# stderr. BSD/macOS stat -f %m is the real mtime, so this only breaks on Linux
# (i.e. CI). Try GNU form first, then BSD, then validate digits before use.
mtime(){
  local m
  m=$(stat -c %Y "$1" 2>/dev/null) || m=""
  case "$m" in ''|*[!0-9]*) m=$(stat -f %m "$1" 2>/dev/null) || m="";; esac
  case "$m" in ''|*[!0-9]*) m=0;; esac
  printf '%s' "$m"
}

session_start=""
if [ -n "$tpath" ] && [ -f "$tpath" ]; then
  ts=$(grep -m1 -o '"timestamp":"[^"]*"' "$tpath" 2>/dev/null | cut -d'"' -f4)
  clean="${ts%%.*}"
  [ -n "$clean" ] && session_start=$(date -j -u -f '%Y-%m-%dT%H:%M:%S' "$clean" +%s 2>/dev/null || date -u -d "$ts" +%s 2>/dev/null || true)
fi

# Frozen collector invocation and 60-second same-session cache skip.
run_collector=1
if [ -f "$CACHE" ] && [ -n "$sid" ]; then
  mt=$(mtime "$CACHE")
  age=$(($(date +%s)-mt))
  cache_sid=$(sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$CACHE" 2>/dev/null | head -1)
  [ "$age" -lt 60 ] && [ "$cache_sid" = "$sid" ] && run_collector=0
fi
if [ "$run_collector" -eq 1 ] && [ -n "$sid" ] && [ -f "$SELF_DIR/statusline.d/collect_usage.py" ]; then
  if command -v timeout >/dev/null 2>&1; then runner=timeout
  elif command -v gtimeout >/dev/null 2>&1; then runner=gtimeout
  else runner=""; fi
  cl5_reset_arg=""
  [ -n "$cl5_reset" ] && cl5_reset_arg="--claude-h5-resets-at $cl5_reset"
  if [ -n "$runner" ]; then "$runner" 5s python3 "$SELF_DIR/statusline.d/collect_usage.py" --session-id "$sid" --transcript "$tpath" --session-start "$session_start" --current-claude-model "$cur_id_raw" $cl5_reset_arg >/dev/null 2>&1 || true
  else python3 "$SELF_DIR/statusline.d/collect_usage.py" --session-id "$sid" --transcript "$tpath" --session-start "$session_start" --current-claude-model "$cur_id_raw" $cl5_reset_arg >/dev/null 2>&1 || true; fi
fi

# Deterministic time-throttled background usage-DB ingest (not LLM-triggered; fire-and-forget, never blocks render).
INGEST_MARK="${HOME}/.claude/statusline-ingest-lastrun"
ingest_due=1
if [ -f "$INGEST_MARK" ]; then
  imt=$(mtime "$INGEST_MARK")
  iage=$(($(date +%s)-imt))
  [ "$iage" -lt 300 ] && ingest_due=0
fi
if [ "$ingest_due" -eq 1 ] && [ -f "$SELF_DIR/statusline.d/ingest_usage.py" ]; then
  touch "$INGEST_MARK" 2>/dev/null
  ( python3 "$SELF_DIR/statusline.d/ingest_usage.py" >/dev/null 2>&1 & ) 2>/dev/null
fi

dump=$(jq -r '
 def s:if .==null then "—" else tostring end;
 "META\t"+([(.codex.h5.used_pct|s),(.codex.h5.resets_at|s),(.codex.observed_at|s),(.codex.d7.used_pct|s),(.codex.d7.resets_at|s),(.cum_use.tokens//0),(.cum_use.cost|s),(.claude_d7.cost|s),(.sub_ratio_d7.claude|s),(.openai_total_d7.tokens|s),(.generated_at|s),(.claude_today.tokens//0),(.claude_today.cost|s),(.openai_today.tokens//0),(.openai_today.cost|s),(.claude_h5.tokens//0),(.claude_h5.cost|s),(.openai_h5.tokens//0),(.openai_h5.cost|s),(.claude_all.tokens//0),(.claude_all.cost|s),(.openai_all.tokens//0),(.openai_all.cost|s),(.free_all.tokens//0),(.free_all.equiv_cost|s),(.session_id|s)]|join("\t")),
 "PWT\t"+([("claude","openai","free") as $p|("h5","d1","d7","d28","all") as $w|(.provider_windows[$p][$w].tokens|s)]|join("\t")),
 "PWC\t"+([("claude","openai","free") as $p|("h5","d1","d7","d28","all") as $w|(.provider_windows[$p][$w].cost|s)]|join("\t")),
 "HIST\t"+([(.history_days.claude|s),(.history_days.openai|s),(.history_days.free|s)]|join("\t")),
 (.models|to_entries[]|.key as $id|.value as $v|"MODEL\t"+([$id,($v.session.tokens|s),($v.session.cost|s),($v.d1.tokens|s),($v.d1.cost|s),($v.d7.tokens|s),($v.d7.cost|s),($v.d28.tokens|s),($v.d28.cost|s),($v.all.tokens|s),($v.all.cost|s),($v.h5.tokens|s),($v.session.tokens_noncache|s)]|join("\t"))),
 ((.free_top4_d7//[])[]|"FREE\t"+([(.model//""),(.tokens//0),(.session.tokens//0),((.session.equiv_cost//.session.cost)|s),(.d7.tokens//0),((.d7.equiv_cost//.d7.cost)|s),(.h5.tokens//0),(.d1.tokens//0),(.d1.equiv_cost|s),(.d28.tokens//0),(.d28.equiv_cost|s),(.all.tokens//0),(.all.equiv_cost|s),(.h5.equiv_cost|s)]|join("\t")))
' "$CACHE" 2>/dev/null)
sncache=(— — — — — — — —); mtok=(0 0 0 0 0 0 0 0 0 0 0 0); mcost=(— — — — — — — — — — — —)
h5tok=(0 0 0 0 0 0 0 0 0 0 0 0); h5cost=(— — — — — — — — — — — —)  # 0-3 ANT, 4-7 OAI, 8-11 FREE top4 (ALL)
d1tok=(0 0 0 0 0 0 0 0 0 0 0 0); d1cost=(— — — — — — — — — — — —)
dtok=(0 0 0 0 0 0 0 0 0 0 0 0); dcost=(— — — — — — — — — — — —)
motok=(0 0 0 0 0 0 0 0 0 0 0 0); mocost=(— — — — — — — — — — — —)
altok=(0 0 0 0 0 0 0 0 0 0 0 0); alcost=(— — — — — — — — — — — —)
hist_c=—; hist_o=—; hist_f=—
pwt=(); pwc=()  # provider_windows: 15 each, claude/openai/free x h5 d1 d7 d28 all; empty = absent
fmod=("" "" "" ""); ftok=(0 0 0 0); fstok=(0 0 0 0); fscost=(— — — —); fdtok=(0 0 0 0); fdcost=(— — — —); ci=0; oi=0; fi=0
mids=("" "" "" "" "" "" "" "")  # ANT 0-3, OAI 4-7: exact model ids
while IFS=$'\t' read -r kind a b c d e f g h i j k l m n o p q r s t u v w x y z; do
 case "$kind" in
 META) gen_at=$k; cache_sid_now=$z; ch5_raw=$a; ch5_reset=$b; cd7_raw=$d; cd7_reset=$e; claude_h5_cost=$q; openai_h5_cost=$s; claude_all_tok=$t; claude_all_cost=$u; openai_all_tok=$v; openai_all_cost=$w; free_all_tok=$x; free_all_cost=$y; : "$c" "$f" "$g" "$h" "$i" "$j" "$l" "$m" "$n" "$o" "$p" "$r";;
 PWT) pwt=("$a" "$b" "$c" "$d" "$e" "$f" "$g" "$h" "$i" "$j" "$k" "$l" "$m" "$n" "$o");;
 PWC) pwc=("$a" "$b" "$c" "$d" "$e" "$f" "$g" "$h" "$i" "$j" "$k" "$l" "$m" "$n" "$o");;
 HIST) hist_c=$a; hist_o=$b; hist_f=$c;;
 MODEL) # exact ids from the cache, ranked by the collector: first 4 claude-* rows -> ANT (0-3), first 4 others -> OAI (4-7)
  case "$a" in claude*) if [ "$ci" -lt 4 ]; then x=$ci; ci=$((ci+1)); else x=; fi;; *) if [ "$oi" -lt 4 ]; then x=$((oi+4)); oi=$((oi+1)); else x=; fi;; esac
  [ -n "$x" ] && { mids[x]=$a; mtok[x]=$b; mcost[x]=$c; d1tok[x]=$d; d1cost[x]=$e; dtok[x]=$f; dcost[x]=$g; motok[x]=$h; mocost[x]=$i; altok[x]=$j; alcost[x]=$k; h5tok[x]=${l:-0}; sncache[x]=${m:-—}; };;
 FREE) [ "$fi" -lt 4 ] && { fmod[fi]=$a; ftok[fi]=$b; fstok[fi]=$c; fscost[fi]=$d; fdtok[fi]=$e; fdcost[fi]=$f; x=$((fi+8)); mtok[x]=$c; mcost[x]=$d; dtok[x]=$e; dcost[x]=$f; h5tok[x]=${g:-0}; d1tok[x]=${h:-0}; d1cost[x]=${i:-—}; motok[x]=${j:-0}; mocost[x]=${k:-—}; altok[x]=${l:-0}; alcost[x]=${m:-—}; h5cost[x]=${n:-—}; fi=$((fi+1)); };;
 esac
done <<EOF
$dump
EOF
# No cache at all: placeholder roster (dashes). Cache without enough models: blank rows.
if [ -z "$dump" ]; then mids=(claude-fable-5-1 claude-opus-5-5 claude-sonnet-5-5 claude-haiku-4-5 gpt-6-astra gpt-5.6-sol gpt-5.6-terra gpt-5.6-luna)
else for k in 0 1 2 3 4 5 6 7; do [ -n "${mids[k]}" ] || { mtok[k]=—; mcost[k]=—; h5tok[k]=—; h5cost[k]=—; d1tok[k]=—; d1cost[k]=—; dtok[k]=—; dcost[k]=—; motok[k]=—; mocost[k]=—; altok[k]=—; alcost[k]=—; }; done; fi
: "${ch5_reset:-}" "${cd7_reset:-}" "${dur_ms:-}" "${ftok[0]}" "${total_cost:-}"

# Integer helpers (bash 3.2, no awk): iround <float-string> -> nearest int.
iround(){ local v=$1 ip fp; case "$v" in -*) v=${v#-};; esac; ip=${v%%.*}; fp=${v#*.}; [ "$fp" = "$v" ] && fp=0; ip=${ip:-0}; case "${fp:0:1}" in 5|6|7|8|9) ip=$((ip+1));; esac; printf %s "$ip"; }
pct(){ case "$1" in ""|—|null|*[!0-9.]*) printf —;; *) iround "$1";; esac; }
# tok: 10B / 1.9B / 12M / 1.9M / 45k / 166 (nearest unit). Integer arithmetic on the integer part.
tok(){ local n; case "$1" in ""|—|null) printf '—'; return;; esac; n=${1%%.*}; n=${n:-0}; case "$n" in *[!0-9]*) printf '—'; return;; esac
 if [ "$n" -ge 9950000000 ];then printf '%dB' "$(((n+500000000)/1000000000))"
 elif [ "$n" -ge 1000000000 ];then n=$(((n+50000000)/100000000)); printf '%d.%dB' "$((n/10))" "$((n%10))"
 elif [ "$n" -ge 9950000 ];then printf '%dM' "$(((n+500000)/1000000))"
 elif [ "$n" -ge 999500 ];then n=$(((n+50000)/100000)); printf '%d.%dM' "$((n/10))" "$((n%10))"
 elif [ "$n" -ge 1000 ];then printf '%dk' "$(((n+500)/1000))"
 else printf '%d' "$n"; fi; }
# Whole dollars from $0.50; under that, cents ($.01, $<.01). Exact 0 shows $0; null shows a dash.
# $0 / $5 / $36 / $489 / $1.1k / $12k — max 5 chars.
# ecost is the same formatter as cost; it adds no ~ (the OAI row label carries the ~).
cost(){ local n c; case "$1" in ""|—|null|-*|*[!0-9.]*) printf '—'; return;; esac; n=$(iround "$1")
 if [ "$n" -le 0 ];then c=$(awk -v v="$1" 'BEGIN{v+=0;if(v<=0)print "0";else if(v<0.005)print "<.01";else printf ".%02d",int(v*100+0.5)}'); case "$c" in 0) printf '$0';; *) printf '$%s' "$c";; esac; return; fi
 if [ "$n" -ge 10000 ];then printf '$%dk' "$(((n+500)/1000))"
 elif [ "$n" -ge 1000 ];then n=$(((n+50)/100)); printf '$%d.%dk' "$((n/10))" "$((n%10))"
 elif [ "$n" -le 0 ];then printf '$0'
 else printf '$%d' "$n"; fi; }
ecost(){ cost "$1"; }
NOW=$(date +%s)
# Data trust. cache_ok=0: no readable cache, every figure is unknown and shows a dash.
# sess_ok=0: SESS and TPM show a dash when the cache belongs to another session, the payload has no session id, or the cache is over 5 min old.
# win_stale=1: the cache is over 5 min old, so the window cells keep their numbers but render dim.
cache_ok=1; sess_ok=1; win_stale=0
[ -n "$dump" ] || cache_ok=0
case "${gen_at:-}" in ""|*[!0-9]*) gen_age=999999;; *) gen_age=$((NOW-gen_at));; esac
[ "$gen_age" -gt 300 ] && win_stale=1
{ [ -n "$sid" ] && [ "${cache_sid_now:-}" = "$sid" ] && [ "$win_stale" -eq 0 ]; } || sess_ok=0
[ "$cache_ok" -eq 1 ] || sess_ok=0
if [ "$cache_ok" -eq 0 ]; then
 for k in 0 1 2 3 4 5 6 7 8 9 10 11; do mtok[k]=—; mcost[k]=—; h5tok[k]=—; h5cost[k]=—; d1tok[k]=—; d1cost[k]=—; dtok[k]=—; dcost[k]=—; motok[k]=—; mocost[k]=—; altok[k]=—; alcost[k]=—; done
elif [ "$sess_ok" -eq 0 ]; then
 for k in 0 1 2 3 4 5 6 7 8 9 10 11; do mtok[k]=—; mcost[k]=—; done
fi
reset_in(){ local x diff d h m; case "$1" in ""|—|null) printf 'n/a'; return;; esac; x=${1%.*}; diff=$((x-NOW)); [ "$diff" -le 0 ] && { printf 'now'; return; }; d=$((diff/86400)); h=$(((diff%86400)/3600)); m=$(((diff%3600)/60)); if [ "$d" -gt 0 ];then printf '%dd %dh' "$d" "$h";elif [ "$h" -gt 0 ];then printf '%dh %dm' "$h" "$m";else printf '%dm' "$m";fi; }
bar(){ local p="$1" n; case "$p" in ""|—|null) p=0;; esac; p=${p%.*}; n=$(((p*5+50)/100)); [ "$n" -eq 0 ] && [ "$p" -gt 0 ] && n=1; case "$n" in 0) printf '░░░░░';;1) printf '█░░░░';;2) printf '██░░░';;3) printf '███░░';;4) printf '████░';;*) printf '█████';; esac; }
# Normalize dynamic text to printable ASCII. UI glyphs have wcwidth 1.
ascii(){ printf %s "$1"|LC_ALL=C tr -cd '[:print:]'; }
vlen(){ local s=$1 t; while [ "${s#*$'\033['}" != "$s" ];do t=${s%%$'\033['*}; s=${s#*$'\033['}; s="$t${s#*m}"; done; _len=${#s}; }
pad(){ local w=$1 s="$2" name=${3:-cell} len; vlen "$s"; len=$_len; if [ "$len" -le "$w" ];then printf '%s%*s' "$s" "$((w-len))" '';elif [ "${STATUSLINE_STRICT:-}" = 1 ] && [ "${4:-}" != free ];then printf 'statusline: overflow in %s\n' "$name" >&2; exit 3;else printf '%s' "${s:0:$w}";fi; }
pad_left(){ local w=$1 s="$2" len; vlen "$s"; len=$_len; if [ "$len" -lt "$w" ];then printf '%*s%s' "$((w-len))" '' "$s";else printf '%s' "$s";fi; }
center(){ local w=$1 s="$2" l; vlen "$s"; l=$(( (w-_len)/2 )); [ "$l" -lt 0 ] && l=0; printf '%*s%s%*s' "$l" '' "$s" "$((w-_len-l))" ''; }
# Colour mode. NO_COLOR (non-empty): no colour escapes; bars use reverse video and block glyphs.
# COLORTERM set to anything but truecolor/24bit, or STATUSLINE_COLORS=256: the 256-colour cube. Otherwise truecolor.
CMODE=24; [ -n "${NO_COLOR:-}" ] && CMODE=0
if [ "$CMODE" = 24 ]; then if [ "${STATUSLINE_COLORS:-}" = 256 ]; then CMODE=256; else case "${COLORTERM:-truecolor}" in truecolor|24bit) ;; *) CMODE=256;; esac; fi; fi
# esc <38|48> r g b: foreground or background escape in the active mode.
esc(){ local k=$1 r=$2 g=$3 b=$4; case "$CMODE" in 24) printf '\033[%s;2;%s;%s;%sm' "$k" "$r" "$g" "$b";; 256) printf '\033[%s;5;%dm' "$k" "$((16+36*((r*5+127)/255)+6*((g*5+127)/255)+(b*5+127)/255))";; esac; }
fg(){ esc 38 "$1" "$2" "$3"; }
# Palette = ONE ramp, cyan(0,224,255) -> magenta(255,102,214). Position on the ramp carries every
# meaning (low->high amount, pressure, effort, recency, model tier). Chrome keeps the original violet.
R=$'\033[0m'; CB=$(fg 120 86 168); CN=$(fg 158 166 190); CS=$(fg 84 78 104); CD=$(fg 128 128 136); TRK=$(esc 48 44 42 56)
# Pressure ramp (bars, %, effort, session clock, reset countdown): cyan(0,224,255) -> magenta(255,102,214).
# t = per-mille integer 0..1000 (no awk fork). Floats (0.55) still accepted for constants.
# ramp_c <permille> -> sets _c (no fork). ramp_color prints it (costs a subshell at the call site; use ramp_c in loops).
ramp_c(){ local t=$1; case "$t" in *.*) t=$(awk -v t="$t" 'BEGIN{printf "%d",t*1000}');; esac; t=${t:-0}; [ "$t" -lt 0 ] && t=0; [ "$t" -gt 1000 ] && t=1000
 case "$CMODE" in 24) _c=$'\033[38;2;'"$((255*t/1000));$((224-122*t/1000));$((255-41*t/1000))m";; *) _c=$(fg "$((255*t/1000))" "$((224-122*t/1000))" "$((255-41*t/1000))");; esac; }
# Names (models, dir, branch): lightness only, no hue — tier = brightness. Keeps one hue ramp on screen.
ramp2_color(){ local t=$1 v; case "$t" in *.*) t=$(awk -v t="$t" 'BEGIN{printf "%d",t*1000}');; esac; v=$((130+115*t/1000)); fg "$v" "$v" "$((v+8))"; }
ramp_color(){ ramp_c "$1"; printf %s "$_c"; }
# Percent colour for bars: the cyan -> magenta pressure ramp (operator: bars keep this mapping). Missing or non-numeric: dim.
level(){ case "$1" in ""|—|null|*[!0-9.]*) printf %s "$CD";; *) ramp_color "$((${1%.*}*10))";; esac; }
# Model-name tier scale: teal lightness (blue-green, separate from the cyan->magenta pressure ramp). Top tier brightest.
teal_color(){ local t=$1; fg "$((60+70*t/1000))" "$((120+125*t/1000))" "$((130+75*t/1000))"; }
CT1=$(teal_color 1000); CT2=$(teal_color 750); CT3=$(teal_color 500); CT4=$(teal_color 250); CT5=$(teal_color 0)
# Colour rules (SPEC.md "Token colour model"). Window order SESS 5H 1D 7D 30D ALL; value i of a call belongs to column (i mod 6).
# Both helpers: missing, zero, negative or non-numeric ("—", "null", "") -> NA (renders CD) and is left out of the column's set.
# Tokens, sharecols: LOG share of the column max. Set = the 12 model cells only (Σ cells leave the set; they use pacecols). permille = clamp(int(1000*(1+log10(v/max)/3)),0,1000); v>=max -> exactly 1000 (float guard).
# sharecols <values...> -> one permille / NA per value.
sharecols(){ printf '%s\n' "$@" | awk '{i=NR-1;c=i%6;v=$0;if(v==""||v~/[^0-9.eE+-]/||v+0<=0){ok[i]=0;next}v+=0;ok[i]=1;x[i]=v;if(!(c in mx)||v>mx[c])mx[c]=v}
 END{for(j=0;j<NR;j++){if(!ok[j]){print "NA";continue}m=mx[j%6];if(x[j]>=m)t=1000;else t=1000*(1+log(x[j]/m)/log(10)/3);if(t>1000)t=1000;if(t<0)t=0;print int(t)}}'; }
# Pace, pacecols <sess_s> <min_since_midnight> <history_days a,b,c> <18 values>: pace colour per provider against its own history (SPEC.md "Dollar cells", "Σ token cells").
# Values: 3 providers x 6 windows (SESS 5H 1D 7D 30D ALL), CSUM dollars or TSUM tokens.
# No noise floor: only a zero, missing or non-numeric cell is NA, or every cell of a provider whose d28 is zero.
# history_days = days of history per provider (— or empty = unknown -> 28). days = clamp(history, 1, 28). d28 = the provider's 30D cell.
# 30D cell: if raw history_days > 28 and ALL > 0, expected = ALL*28/history, r = 30D/expected, same log2 map; else N. ALL cell: N.
# expected = d28 * window_hours / (days*24); permille = clamp(500 + 500*log2(value/expected), 0, 1000). Window hours: 5H 5, 1D hours since midnight (floor 6), 7D min(168, days*24), SESS = duration (under 30 min -> NA).
# Prints one token per value: permille, NA (dim: zero, unknown, or d28 zero), or N (neutral: ALL always; 30D when history <= 28 or unknown).
pacecols(){ local ss=$1 mm=$2 hd=$3; shift 3; printf '%s\n' "$@" | awk -v ss="$ss" -v mm="$mm" -v hd="$hd" 'BEGIN{split(hd,H,",")}{v[NR-1]=$0}
 END{for(j=0;j<NR;j++){g=int(j/6);c=j%6;if(c==5){print "N";continue}
   x=v[j];d=v[g*6+4];if(x==""||x~/[^0-9.eE+-]/||d==""||d~/[^0-9.eE+-]/){print "NA";continue}
   x+=0;d+=0;if(x<=0||d<=0){print "NA";continue}
   hr=28;if(H[g+1]!=""&&H[g+1]!~/[^0-9.eE+-]/)hr=H[g+1]+0;dy=hr;if(dy>28)dy=28;if(dy<1)dy=1
   if(c==4){a=v[g*6+5];if(hr<=28||a==""||a~/[^0-9.eE+-]/||a+0<=0){print "N";continue}r=x/(a*28/hr);t=500+500*log(r)/log(2);if(t>1000)t=1000;if(t<0)t=0;print int(t);continue}
   if(c==0){if(ss<1800){print "NA";continue}h=ss/3600}else if(c==1)h=5;else if(c==2)h=(mm/60<6)?6:mm/60;else h=(dy*24<168)?dy*24:168
   r=x/(d*h/(dy*24));t=500+500*log(r)/log(2);if(t>1000)t=1000;if(t<0)t=0;print int(t)}}'; }
ramp_t(){ case "$1" in NA) _c=$CD;; *) ramp_c "$1";; esac; }
# Tier color: classify by model display name (case-insensitive substring match)
tier_color(){ local name="$1" lower; lower=" $(printf '%s' "$name" | LC_ALL=C tr '[:upper:]-_:/' '[:lower:]    ') "  # ids -> words, padded so " pro " matches as a word
 case "$lower" in
  *lite*|*ministral*) printf %s "$CT5";;
  *fast*|*flash*|*haiku*|*luna*) printf %s "$CT4";;
  *fable*|*astra*|*ultra*|*behemoth*|*flagship*|*"mistral large"*|*"deepseek pro"*) printf %s "$CT1";;
  *opus*|*sol*|*" pro "*|*maverick*|*"deepseek v4"*|*"mistral medium"*|grok) printf %s "$CT2";;
  *sonnet*|*terra*|*scout*|*standard*|*"deepseek chat"*|*"mistral small"*) printf %s "$CT3";;
  *) printf %s "$CN";;
 esac
}
# Name colors: neutral lightness axis (hue is reserved for pressure and amounts).
CNM=$(ramp2_color 1); CNC=$(ramp2_color 0.6); CNO=$(ramp2_color 0.25); BOLD=$'\033[1m'
# DIR = repo role: upstream DomI (bold), consumer with .domi-pin, other.
dir_color(){ local name="$1" lower; lower=$(printf '%s' "$name" | LC_ALL=C tr '[:upper:]' '[:lower:]')
 if [ "$lower" = domi ];then printf '%s%s' "$BOLD" "$CNM"; elif [ -f "$project_dir/.domi-pin" ];then printf %s "$CNC"; else printf %s "$CNO"; fi; }
# BRA name = kind: main (bold) > development > other. Dirty/unpushed state lives in the attributes, not the name color.
branch_kind_color(){ local b="$1"
 case "$b" in
  main|master) printf '%s%s' "$BOLD" "$CNM";;
  development|develop|dev) printf %s "$CNC";;
  *) printf %s "$CN";;
 esac
}
# Middle-ellipsis fit: trunc <string> <width>.
trunc(){ local s=$1 w=$2 h t; [ "$w" -lt 4 ] && w=4; if [ "${#s}" -le "$w" ];then printf %s "$s";else h=$((w/2)); t=$((w-1-h)); printf '%s…%s' "${s:0:h}" "${s: -t}"; fi; }
# BRA row: "<name:7> <dirty:3> <ahead:3>" = 15 = col1 value budget.
#   name  : last path segment (claude/foo-bar -> foo-bar), development/develop -> dev, middle-ellipsis to 7
#   +N    : paths in `git status --porcelain` (uncommitted work); 0 = neutral, 1 = amber, 20+ = red
#   ↑N    : commits ahead of @{u} (unpushed work); 0 = neutral, 1 = amber, 10+ = red; — when no upstream
# Both attributes answer "what have I not shipped yet". Behind (↓) is omitted: it is stale without a fetch.
# Unlike a %-of-limit, any nonzero count is already "unshipped", so counts skip the ramp's neutral segment.
count_color(){ local n=$1 cap=$2 u; [ "$n" -gt 0 ] || { level 0; return; }; u=$((n*1000/cap)); [ "$u" -gt 1000 ] && u=1000; ramp_color "$((300+700*u/1000))"; }
branch=""; branch_base_color=$CN; bra_dirty="—"; bra_ahead="—"; bra_dirty_c=$CD; bra_ahead_c=$CD
if b=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null||git -C "$cwd" rev-parse --short HEAD 2>/dev/null);then
 b=$(ascii "$b"); branch_base_color=$(branch_kind_color "$b")
 branch_full=${b##*/}
 n=$(git -C "$cwd" status --porcelain 2>/dev/null | grep -c .); n=${n:-0}; [ "$n" -gt 99 ] && n=99
 bra_dirty="+$n"; bra_dirty_c=$(count_color "$n" 20)
 a=$(git -C "$cwd" rev-list --count '@{u}..HEAD' 2>/dev/null)
 case "$a" in ''|*[!0-9]*) ;; *) [ "$a" -gt 99 ] && a=99; bra_ahead="↑$a"; bra_ahead_c=$(count_color "$a" 10);; esac
fi
git_val="${bra_dirty_c}$(pad_left 3 "$bra_dirty")${R} ${bra_ahead_c}$(pad_left 3 "$bra_ahead")${R}"
ctx=$(pct "$ctx_raw");cl5=$(pct "$cl5_raw");cl7=$(pct "$cl7_raw");ch5=$(pct "${ch5_raw:-}");cd7=$(pct "${cd7_raw:-}")
# Context bar scaled to autoCompactWindow
ac_win=$(jq -r 'if .autoCompactEnabled == false then "" else (.autoCompactWindow // "") end' "$HOME/.claude/settings.json" 2>/dev/null)
cw=${ctx_size%%.*}; case "$cw" in ''|*[!0-9]*) cw=200000;; esac
cap=$cw
if [ -n "$ac_win" ] && [ "$ac_win" -gt 0 ] 2>/dev/null && [ "$ac_win" -lt "$cw" ]; then cap=$ac_win
elif [ -n "$CLAUDE_AUTOCOMPACT_PCT_OVERRIDE" ]; then case "$CLAUDE_AUTOCOMPACT_PCT_OVERRIDE" in [0-9]|[1-9][0-9]|100) cap=$((cw*CLAUDE_AUTOCOMPACT_PCT_OVERRIDE/100));; esac; [ "$cap" -gt 0 ] || cap=$cw; fi
if [ "$ctx" = "—" ]; then ctx_ac="—"; else ctx_raw_int=$(iround "$ctx_raw"); used=$((cw*ctx_raw_int/100)); ctx_ac=$((used*100/cap)); [ "$ctx_ac" -gt 100 ] && ctx_ac=100; fi
: "${cum_tok:-}" "${cum_cost:-}"
effort=$(ascii "${effort_raw:-${CLAUDE_CODE_EFFORT_LEVEL:-$(jq -r '.effortLevel // empty' "$HOME/.claude/settings.json" 2>/dev/null)}}")
[ -n "$effort" ] || effort="—"
# All window sums in ONE awk call (was 13 forks).
IFS=$'\t' read -r claude7_tok_raw claude7_cost_raw codex7_tok_raw codex7_cost_raw claude_session_tokens claude_session_cost openai_session_tokens openai_session_cost claude_mo_tokens claude_mo_cost openai_mo_tokens openai_mo_cost all_tokens all_cost <<EOF
$(awk 'BEGIN{OFS="\t";printf "%s",ARGV[1]+ARGV[2]+ARGV[3]+ARGV[4] OFS ARGV[5]+ARGV[6]+ARGV[7]+ARGV[8] OFS ARGV[9]+ARGV[10]+ARGV[11]+ARGV[12] OFS ARGV[13]+ARGV[14]+ARGV[15]+ARGV[16] OFS ARGV[17]+ARGV[18]+ARGV[19]+ARGV[20] OFS ARGV[21]+ARGV[22]+ARGV[23]+ARGV[24] OFS ARGV[25]+ARGV[26]+ARGV[27]+ARGV[28] OFS ARGV[29]+ARGV[30]+ARGV[31]+ARGV[32] OFS ARGV[33]+ARGV[34]+ARGV[35]+ARGV[36] OFS ARGV[37]+ARGV[38]+ARGV[39]+ARGV[40] OFS ARGV[41]+ARGV[42]+ARGV[43]+ARGV[44] OFS ARGV[45]+ARGV[46]+ARGV[47]+ARGV[48] OFS ARGV[49]+ARGV[50]+ARGV[51] OFS ARGV[52]+ARGV[53]+ARGV[54]}' \
 "${dtok[0]}" "${dtok[1]}" "${dtok[2]}" "${dtok[3]}" "${dcost[0]}" "${dcost[1]}" "${dcost[2]}" "${dcost[3]}" \
 "${dtok[4]}" "${dtok[5]}" "${dtok[6]}" "${dtok[7]}" "${dcost[4]}" "${dcost[5]}" "${dcost[6]}" "${dcost[7]}" \
 "${mtok[0]}" "${mtok[1]}" "${mtok[2]}" "${mtok[3]}" "${mcost[0]}" "${mcost[1]}" "${mcost[2]}" "${mcost[3]}" \
 "${mtok[4]}" "${mtok[5]}" "${mtok[6]}" "${mtok[7]}" "${mcost[4]}" "${mcost[5]}" "${mcost[6]}" "${mcost[7]}" \
 "${motok[0]}" "${motok[1]}" "${motok[2]}" "${motok[3]}" "${mocost[0]}" "${mocost[1]}" "${mocost[2]}" "${mocost[3]}" \
 "${motok[4]}" "${motok[5]}" "${motok[6]}" "${motok[7]}" "${mocost[4]}" "${mocost[5]}" "${mocost[6]}" "${mocost[7]}" \
 "${claude_all_tok:-0}" "${openai_all_tok:-0}" "${free_all_tok:-0}" "${claude_all_cost:-0}" "${openai_all_cost:-0}" "${free_all_cost:-0}")
EOF
# RAM and CPU info for row 5-6. All commands guarded; failure yields "—".
get_ram_info() {
  local vm page_size free inactive speculative total_bytes avail_bytes used_pct used_g total_g
  vm=$(vm_stat 2>/dev/null) || { printf '%s\t%s' '—' '—'; return 0; }
  page_size=$(printf '%s\n' "$vm" | sed -n '1s/.*page size of \([0-9]*\).*/\1/p')
  [ -z "$page_size" ] && { printf '%s\t%s' '—' '—'; return 0; }
  free=$(printf '%s\n' "$vm" | sed -n 's/^Pages free:[[:space:]]*\([0-9]*\).*/\1/p')
  inactive=$(printf '%s\n' "$vm" | sed -n 's/^Pages inactive:[[:space:]]*\([0-9]*\).*/\1/p')
  speculative=$(printf '%s\n' "$vm" | sed -n 's/^Pages speculative:[[:space:]]*\([0-9]*\).*/\1/p')
  [ -z "$free" ] || [ -z "$inactive" ] || [ -z "$speculative" ] && { printf '%s\t%s' '—' '—'; return 0; }
  total_bytes=$(sysctl -n hw.memsize 2>/dev/null) || { printf '%s\t%s' '—' '—'; return 0; }
  [ -z "$total_bytes" ] && { printf '%s\t%s' '—' '—'; return 0; }
  avail_bytes=$((($free + $inactive + $speculative) * $page_size))
  used_pct=$((((total_bytes - avail_bytes) * 100) / total_bytes))
  [ "$used_pct" -lt 0 ] && used_pct=0; [ "$used_pct" -gt 100 ] && used_pct=100
  used_g=$(awk -v b="$((total_bytes - avail_bytes))" 'BEGIN{printf "%.1f", b/1073741824}')
  total_g=$(awk -v b="$total_bytes" 'BEGIN{printf "%.0f", b/1073741824}')
  : "$used_g" "$total_g"; printf '%d%% %s\t%d' "$used_pct" "$(bar "$used_pct")" "$used_pct"
}
get_cpu_info() {
  local ncpu total_pct pct cpu_bar
  ncpu=$(sysctl -n hw.ncpu 2>/dev/null) || { printf '%s\t%s' '—' '—'; return 0; }
  [ -z "$ncpu" ] && { printf '%s\t%s' '—' '—'; return 0; }
  total_pct=$(ps -A -o %cpu= 2>/dev/null | awk '{sum+=$1}END{printf "%d", sum}')
  [ -z "$total_pct" ] && { printf '%s\t%s' '—' '—'; return 0; }
  pct=$(awk -v t="$total_pct" -v n="$ncpu" 'BEGIN{p=int(t/n);if(p<0)p=0;if(p>100)p=100;printf "%d", p}')
  cpu_bar=$(bar "$pct")
  printf '%d%% %s\t%d' "$pct" "$cpu_bar" "$pct"
}
get_disk_info() {
  local p; p=$( (df -P /System/Volumes/Data 2>/dev/null || df -P / 2>/dev/null) | awk 'NR==2{gsub(/%/,"",$5);print $5}'); [ -n "$p" ] || { printf '%s\t%s' '—' '—'; return 0; }
  printf '%d%% %s\t%d' "$p" "$(bar "$p")" "$p"
}
dsk_val_pct=$(get_disk_info); IFS=$'\t' read -r dsk_val dsk_pct <<< "$dsk_val_pct"
# GPU load % (Apple Silicon IOAccelerator, no sudo). Missing -> — (dim, empty bar).
gpu_pct=$(ioreg -r -d 1 -c IOAccelerator 2>/dev/null | sed -n 's/.*"Device Utilization %"=\([0-9][0-9]*\).*/\1/p' | head -1); [ -n "$gpu_pct" ] || gpu_pct=—
ram_val_pct=$(get_ram_info)
IFS=$'\t' read -r ram_val ram_pct <<< "$ram_val_pct"
ram_val=$(pad_left 15 "$ram_val")
cpu_val_pct=$(get_cpu_info)
IFS=$'\t' read -r cpu_val cpu_pct <<< "$cpu_val_pct"
cpu_val=$(pad_left 15 "$cpu_val")
# Model tables (col4 ANT, col5 OAI): 6 rows = 4 models, Σ tokens, Σ $.
# Row layout: name left-justified to 10, then SESS 1D 7D 30D ALL tokens, each right-justified in 5 (35 total).
# Column labels live in the top border (see hdr below).
# Display names come from the exact model id: claude-opus-5-5 -> "Opus 5.5", gpt-5.6-sol -> "GPT-5.6 Sol". Unknown ids pass through.
# OAI's longest (GPT-5.6 Terra, 13) sets that table's name column to 13.
# Terra stays on 5.6: gpt-6-terra is rejected for Codex on a ChatGPT account (checked 2026-10-01).
onw=13
model_label(){ local id=${1%%\[*} f re1='^claude-([a-z]+)-([0-9]+)(-([0-9]+))?$' re2='^gpt-([0-9]+(\.[0-9]+)?)(-([a-z0-9]+))?$'
 case "$id" in *-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) id=${id%-*};; esac
 if [[ $id =~ $re1 ]]; then f=${BASH_REMATCH[1]}; f="$(printf %s "${f:0:1}" | LC_ALL=C tr a-z A-Z)${f:1}"; _lbl="$f ${BASH_REMATCH[2]}${BASH_REMATCH[4]:+.${BASH_REMATCH[4]}}"
 elif [[ $id =~ $re2 ]]; then f=${BASH_REMATCH[4]}; [ -n "$f" ] && f=" $(printf %s "${f:0:1}" | LC_ALL=C tr a-z A-Z)${f:1}"; _lbl="GPT-${BASH_REMATCH[1]}$f"
 elif [ -n "$id" ]; then _lbl=$id; else _lbl=—; fi
 _lbl=${_lbl:0:$onw}; }
fsum(){ awk 'BEGIN{t=0;n=0}{for(i=1;i<=NF;i++)if($i!="—"&&$i!="null"&&$i!=""){t+=$i;n++}}END{if(n)printf "%.4f",t;else printf "—"}' <<<"$*"; }
# Heat: the 12 model cells share one log-share scale per window column; sigma cells use pace (pacecols).
MH=(); TH=(); _hv=()
for k in 0 1 2 3 4 5 6 7 8 9 10 11; do _hv+=("${mtok[k]}" "${h5tok[k]}" "${d1tok[k]}" "${dtok[k]}" "${motok[k]}" "${altok[k]}"); done
# o = offset into the per-model arrays (0 ANT, 4 OAI, 8 FREE). Sigma and $ = provider totals (provider_windows,
# all rows of the provider, not only the 4 model cells). SESS keeps the row sum. A window falls back to the row
# sum when its provider_windows value is missing, null or non-numeric.
pwnum(){ case "$1" in ""|—|null|*[!0-9.eE+-]*) return 1;; esac; }
# Σ/$ window cell = max(provider total, row sum): a provider total covers every model, so it is never below the row sum (OAI d28 cost comes from a different price source).
pwmax(){ local pv="$1" rs="$2"; if ! pwnum "$rs"; then printf '%s' "$pv"; else awk -v a="$pv" -v b="$rs" 'BEGIN{if((a+0) > (b+0)) printf("%s",a); else printf("%s",b)}'; fi; }
TSUM=(); CSUM=(); wi=0
for o in 0 4 8; do
 pb=$((o/4*5))
 for w in mtok h5tok d1tok dtok motok altok; do v=0; kn=0; for j in 0 1 2 3; do eval "x=\${${w}[o+j]}"; case "$x" in ""|*[!0-9]*) x=0;; *) kn=1;; esac; v=$((v+x)); done; [ "$kn" -eq 0 ] && v=—; [ "$w" = mtok ] && [ "$sess_ok" -eq 0 ] && v=—
  if [ "$w" != mtok ]; then wi=$((${#TSUM[@]}%6-1)); pv=${pwt[pb+wi]:-—}; pwnum "$pv" && v=$(pwmax "${pv%%.*}" "$v"); fi
  TSUM+=("$v"); done
 # Fallback 5H $: provider-level cache fields (collector keeps no per-model 5H cost).
 case $o in 0) h5c=${claude_h5_cost:-—};; 4) h5c=${openai_h5_cost:-—};; *) h5c=$(fsum "${h5cost[8]}" "${h5cost[9]}" "${h5cost[10]}" "${h5cost[11]}");; esac
 for w in mcost h5c d1cost dcost mocost alcost; do if [ "$w" = h5c ]; then v=$h5c; else eval "v=\$(fsum \"\${${w}[o]}\" \"\${${w}[o+1]}\" \"\${${w}[o+2]}\" \"\${${w}[o+3]}\")"; fi
  if [ "$w" != mcost ]; then wi=$((${#CSUM[@]}%6-1)); pv=${pwc[pb+wi]:-—}; pwnum "$pv" && v=$(pwmax "$pv" "$v"); fi
  CSUM+=("$v"); done
done
# Model cells: one sharecols (log share) call over the 72 model values.
for x in $(sharecols "${_hv[@]}"); do ramp_t "$x"; MH+=("$_c"); done
# Σ and $ cells (provider totals): pace colour per provider (pacecols) on TSUM tokens and CSUM dollars; 30D neutral. ALL cells get log share across the 3 providers.
_sd=${dur_ms%%.*}; _sd=$((${_sd:-0}/1000)); [ "$sess_ok" -eq 0 ] && _sd=0
read -r _hh _mn <<<"$(date +'%H %M')"; _mm=$((10#$_hh*60+10#$_mn))
_hd="${hist_c},${hist_o},${hist_f}"
CH=(); for x in $(pacecols "$_sd" "$_mm" "$_hd" "${CSUM[@]}"); do if [ "$x" = N ]; then CH+=("$CN"); else ramp_t "$x"; CH+=("$_c"); fi; done
TH=(); for x in $(pacecols "$_sd" "$_mm" "$_hd" "${TSUM[@]}"); do if [ "$x" = N ]; then TH+=("$CN"); else ramp_t "$x"; TH+=("$_c"); fi; done
# ALL cells: log share across the 3 providers (sharecols column 5 = indices 5, 11, 17).
_as=($(sharecols "${TSUM[@]}")); _ac=($(sharecols "${CSUM[@]}")); for i in 5 11 17; do ramp_t "${_as[i]}"; TH[i]=$_c; ramp_t "${_ac[i]}"; CH[i]=$_c; done
# hc <heat-array-name> <index> <text>: color one 5-wide right-justified value.
hc(){ local a="$1[$2]" t=$3; printf '%s%*s%s%s' "${!a}" "$((5-${#t}))" '' "$t" "$R"; }
# tokB: tok (k/M) below 100M, billions from 100M (13B, 1.1B, .52B, .10B), 4 chars max. Used for 7D/30D/ALL.
tokB(){ local n=${1%%.*}; case "$n" in ""|—|null|*[!0-9]*) printf '—'; return;; esac; [ "$n" -lt 100000000 ] && { tok "$n"; return; }
 awk -v n="$n" 'BEGIN{v=n/1e9;if(v>=9.95)printf "%dB",v+0.5;else if(v>=0.995)printf "%.1fB",v;else printf ".%02dB",int(v*100+0.5)}'; }
mrow(){ local c=$1 l=$2 o=$3 b=$(( $3*6 )) F=${4:-tokB}; printf '%s%s%s%s%s%s%s%s%s' "$c" "$l" "$R$(printf '%*s' $((${NW:-12}-${#l})) '')" "$(hc MH $b "$(tok "${mtok[o]}")")" "$(hc MH $((b+1)) "$(tok "${h5tok[o]}")")" "$(hc MH $((b+2)) "$(tok "${d1tok[o]}")")" "$(hc MH $((b+3)) "$($F "${dtok[o]}")")" "$(hc MH $((b+4)) "$($F "${motok[o]}")")" "$(hc MH $((b+5)) "$($F "${altok[o]}")")"; }
# Current model: match the rows by exact model id (version suffixes never merge); display-name label is the fallback.
cur_id=${cur_id_raw%%\[*}; case "$cur_id" in *-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) cur_id=${cur_id%-*};; esac
lbls=(); cur_k=-1
for k in 0 1 2 3 4 5 6 7; do model_label "${mids[k]}"; lbls[k]=$_lbl; [ -n "$cur_id" ] && [ "${mids[k]}" = "$cur_id" ] && cur_k=$k; done
if [ "$cur_k" -lt 0 ]; then cur_disp=$(printf '%s' "$(ascii "$model")" | LC_ALL=C tr '[:upper:]' '[:lower:]' | awk '{n=$1;if($2~/^[0-9.]+$/)n=n " " $2;print n}')
 if [ -n "$cur_disp" ]; then for k in 0 1 2 3 4 5 6 7; do [ "$(printf '%s' "${lbls[k]}" | LC_ALL=C tr '[:upper:]' '[:lower:]')" = "$cur_disp" ] && cur_k=$k; done; fi; fi
# Stale cache (over 5 min): window cells keep their numbers but render dim. Must run before the model rows are built.
if [ "$win_stale" -eq 1 ]; then for i in $(seq 0 $(( ${#MH[@]}-1 ))); do [ $((i%6)) -ne 0 ] && MH[i]=$CD; done; for i in $(seq 0 $(( ${#TH[@]}-1 ))); do [ $((i%6)) -ne 0 ] && { TH[i]=$CD; CH[i]=$CD; }; done; fi
ant_rows=(); oai_rows=()
for k in 0 1 2 3; do
 hl=; [ "$cur_k" -eq "$k" ] && hl=$'\033[7m'  # reverse video = model this session runs on
 ant_rows[k]=$(NW=$onw mrow "$(tier_color "${lbls[k]}")$hl" "${lbls[k]}" "$k")
 hl=; [ "$cur_k" -eq "$((k+4))" ] && hl=$'\033[7m'
 oai_rows[k]=$(NW=$onw mrow "$(tier_color "${lbls[k+4]}")$hl" "${lbls[k+4]}" "$((k+4))")
done
# $ row drops the "$" sign (the row label carries it) so $3.4k fits 4 cols + 1 space.
nod(){ local v; v=$("$@"); printf '%s' "${v#\$}"; }
# Countdown: neutral slate (time to reset is a clock, not an amount); a missing or zero resets_at is a dash. Name cells: Σ row = 5H bar+countdown, $ row = 7D bar+countdown; bar at left, one space, countdown left-aligned 5 chars, then " Σ"/" $" (13 visible).
lrst(){ local t; case "$1" in ""|—|null|0|0.*|*[!0-9.]*) printf '%s—    %s' "$CD" "$R"; return;; esac; t=$(reset_in "$1"); t=${t// /}; local el=$(( (${2:-0} - (${1%.*}-NOW)) * 1000 / ${2:-1} )); [ "$el" -lt 0 ] && el=0; [ "$el" -gt 1000 ] && el=1000; ramp_c "$el"; printf '%s%-5s%s' "$_c" "${t:0:5}" "$R"; }
# lbar <pct> <label>: 5-cell bar with 5% steps and shaded-edge blending; label right-aligned inside.
lbar(){ local p=$1 L=$2 c n=0 q=0 i k ch bg out= s=0 r=0 rs gs bs rb gb bb blend_bg=0 blend_bg_str; c=$(level "$p"); case "$p" in ""|—|null) ;; *) q=${p%.*}; s=$(((q*20+50)/100)); [ "$s" -lt 0 ] && s=0; [ "$s" -gt 20 ] && s=20; [ "$q" -gt 0 ] && [ "$s" -eq 0 ] && s=1; n=$((s/4)); r=$((s%4));; esac
 bg=${c/\[38;/[48;}; k=$((5-${#L})); local dk=$'\033[1;30m' fg; case "$c" in *"38;2;"*) dk=$'\033[1;38;2;44;42;56m';; esac
 case "$c" in *"38;2;"*) local rgb; rgb=${c#*38;2;}; rgb=${rgb%m}; rs=${rgb%%\;*}; rgb=${rgb#*\;}; gs=${rgb%%\;*}; bs=${rgb#*\;}; if [ "$r" -gt 0 ]; then rb=$((44+(rs-44)*r/4)); gb=$((42+(gs-42)*r/4)); bb=$((56+(bs-56)*r/4)); blend_bg_str=$'\033[48;2;'"${rb};${gb};${bb}m"; fi; blend_bg=1;; *) blend_bg=0;; esac
 for i in 0 1 2 3 4; do ch=' '; [ "$i" -ge "$k" ] && ch=${L:$((i-k)):1}
  if [ "$CMODE" = 0 ]; then
   if [ "$i" -lt "$n" ]; then if [ "$ch" = ' ' ]; then out+='█'; else out+=$'\033[7m'"${ch}${R}"; fi
   elif [ "$i" -eq "$n" ] && [ "$r" -gt 0 ]; then if [ "$ch" = ' ' ]; then out+='▒'; else out+=$'\033[7m'"${ch}${R}"; fi
   else if [ "$ch" = ' ' ]; then out+='░'; else out+="$ch"; fi; fi
   continue
  fi
  fg=$c; [ "$ch" != ' ' ] && fg=$dk
  if [ "$i" -lt "$n" ]; then out+="${bg}${fg}${ch}${R}"
  elif [ "$i" -eq "$n" ] && [ "$r" -gt 0 ] && [ "$blend_bg" -eq 1 ]; then out+="${blend_bg_str}${fg}${ch}${R}"
  else out+="${TRK}${c}${ch}${R}"; fi; done; printf '%s' "$out"; }
# hotlbl <pct> <name>: pct empty/—/null or <90 -> name; 90..99 -> "NN%name"; >=100 -> "100%" (row label identifies the window).
hotlbl(){ local p=${1%.*}; case "$p" in ""|—|null|*[!0-9]*) printf '%s' "$2"; return;; esac; if [ "$p" -ge 100 ]; then printf '100%%'; elif [ "$p" -ge 90 ]; then printf '%s%%%s' "$p" "$2"; else printf '%s' "$2"; fi; }
tsum(){ local b=$1 i out; if [ "$2" = - ]; then out="$CN$(pad_left "${NW:-12}" Σ)$R"; else out="$(lbar "$2" "$(hotlbl "$2" 5H)") $(lrst "$3" 18000)$(printf '%*s' $((${NW:-12}-13)) '') ${CN}Σ$R"; fi; for i in 0 1 2 3 4 5; do if [ "$i" -ge 3 ] && [ "$2" != - ]; then f=tokB; else f=tok; fi; out+=$(hc TH $((b+i)) "$($f "${TSUM[b+i]}")"); done; printf '%s' "$out"; }
csum(){ local b=$1 cf=$2 i out lb=${LBL:-\$}; if [ "$3" = - ]; then out="$CN$(pad_left "${NW:-12}" "$lb")$R"; else out="$(lbar "$3" "$(hotlbl "$3" 7D)") $(lrst "$4" 604800)$(printf '%*s' $((${NW:-12}-13)) '') ${CN}${lb}$R"; fi; for i in 0 1 2 3 4 5; do out+=$(hc CH $((b+i)) "$(nod $cf "${CSUM[b+i]}")"); done; printf '%s' "$out"; }
ant_rows[4]=$(NW=$onw tsum 0 "$cl5" "$cl5_reset"); oai_rows[4]=$(NW=$onw tsum 6 "$ch5" "${ch5_reset:-}"); ant_rows[5]=$(NW=$onw csum 0 cost "$cl7" "$cl7_reset"); oai_rows[5]=$(LBL="~" NW=$onw csum 6 ecost "$cd7" "${cd7_reset:-}")
# Free-model label (<=8 chars, same name width as Fable51/Haiku45 in cols 4-5).
# 1. drop vendor/ prefix, :free suffix, size tokens (120b, a12b) and noise words (latest, preview, instruct, free, exp, it)
# 2. numeric tokens are kept verbatim with dots removed (3.8 -> 38)
# 3. word tokens use the alias table when present, else first letter + up to 3 consonants (model -> Mdl)
# 4. join and hard-cut at 8
# gemini-flash-lite-latest -> GemFlLt · gemini-3.8-flash -> Gem38Fl · nvidia/nemotron-3-super-120b-a12b:free -> Nemo3Sup · codestral-latest -> Codstral
fname(){ printf '%s' "$1" | awk -v L=8 'BEGIN{a["gemini"]="Gem";a["gemma"]="Gemma";a["flash"]="Fl";a["lite"]="Lt";a["pro"]="Pro";a["ultra"]="Ult";a["nano"]="Nano";a["mini"]="Mini"
  a["nemotron"]="Nemo";a["super"]="Sup";a["codestral"]="Codstral";a["mistral"]="Mist";a["ministral"]="Mnst";a["devstral"]="Devst";a["magistral"]="Magst"
  a["llama"]="Llama";a["deepseek"]="DS";a["qwen"]="Qwen";a["coder"]="Code";a["code"]="Code";a["chat"]="Chat";a["thinking"]="Thk";a["reasoning"]="Rsn";a["vision"]="Vis"
  a["small"]="Sm";a["medium"]="Md";a["large"]="Lg";a["moe"]="MoE"}
 {s=tolower($0);sub(/^.*\//,"",s);sub(/:.*$/,"",s);n=split(s,p,/[-_.]/);m=0
 for(i=1;i<=n;i++){t=p[i];if(t=="")continue
  if(t~/^a?[0-9]+[bmk]$/||t~/^[0-9][0-9][0-9][0-9]+$/||t~/^(latest|preview|instruct|free|exp|it)$/)continue
  if(t~/^v[0-9]+$/)t=substr(t,2)
  m++
  if(t~/^[0-9]+$/)w[m]=t
  else if(t in a)w[m]=a[t]
  else{c=substr(t,2);gsub(/[aeiou]/,"",c);w[m]=toupper(substr(t,1,1)) substr(c,1,3)}}
 out="";for(i=1;i<=m;i++)out=out w[i];print substr(out,1,L)}'; }

# Column widths: 19 (col1) + 43 (ANTROP) + 43 (OAI) + FREE (42 default; reset below to longest free name + 30) + 3 separators.
ws=(19 43 43 42); SEP="${CS}│${R}"
cell(){ local w=$1 label=$2 value=$3 color=$4 vw name=${5:-cell};if [ -z "$label" ];then printf '%s' "$color";pad "$w" "$value" "$name" "$6";printf %s "$R";return;fi;vw=$((w-${#label}-1));printf '%s%s%s %s' "$CN" "$label" "$R" "$color";pad "$vw" "$value" "$name" "$6";printf %s "$R"; }
row(){ shift;printf '%s║%s' "$CB" "$R";local k=0;while [ "$k" -lt 4 ];do [ "$k" -gt 0 ]&&printf %s "$SEP";if [ "$k" -eq 3 ];then cell "${ws[k]}" "$1" "$2" "$3" "${1:-col4}" free;else cell "${ws[k]}" "$1" "$2" "$3" "${1:-col$((k+1))}";fi;shift 3;k=$((k+1));done;printf '%s║%s\n' "$CB" "$R"; }
rep(){ local s; s=$(printf '%*s' "$2" ''); printf '%s' "${s// /$1}"; }
model=$(ascii "$model"); project=$(ascii "$project"); project=$(trunc "$project" 5)
# DIR row: "<proj:<=5>" left, CTX bar right (lines up with RAM/CPU), value budget 15.
# Branch row (no label): "<branch:<=9>" left, RAM bar right, value budget 19.
branch=${branch_full:-}
[ "${#branch}" -gt 9 ] && branch="${branch:0:8}…"
# sub2 <LBL> <pct> [text]: "<LBL> <bar>", 9 visible; 2-char value (NN, 99 caps 100; or text) sits inside the bar like the 5H/7D labels.
sub2(){ local v=$2 s=$3; [ -n "$s" ] || case "$v" in ""|—|null) s='--';; *) v=${v%.*}; [ "$v" -gt 99 ] && v=99; s=$(printf %02d "$v");; esac; printf '%s%s%s %s' "$CN" "$1" "$R" "$(lbar "$2" "$s")"; }
dir_val="$(dir_color "$project")${project}${R}$(printf '%*s' $((6-${#project})) '')$(sub2 RAM "$ram_pct")"
case "$effort" in low) eff_s=LOW;; medium) eff_s=MED;; high) eff_s=HIGH;; xhigh) eff_s=XHIGH;; max) eff_s=MAX;; ultra|ultracode) eff_s=ULT;; *) eff_s=$(printf %s "${effort:0:3}" | tr a-z A-Z);; esac
case "$effort" in low) eff_t=0;; medium) eff_t=250;; high) eff_t=500;; xhigh) eff_t=750;; max|ultra|ultracode) eff_t=1000;; *) eff_t=NA;; esac
case "$effort" in low) eff_l=LO;; medium) eff_l=ME;; high) eff_l=HI;; xhigh) eff_l=XH;; max|ultra|ultracode) eff_l=MX;; *) eff_l=;; esac
if [ "$eff_t" = NA ]; then eff_pct=—; else eff_pct=$(( (eff_t/250+1)*20 )); fi
# Session time (cost.total_duration_ms): 45s / 23m / 1h23m / 1d2h; neutral (a clock, not a limit or a magnitude).
sess_s=${dur_ms%%.*}; sess_s=$((${sess_s:-0}/1000))
if [ "$sess_s" -ge 864000 ];then sess_time="$((sess_s/86400))d"
elif [ "$sess_s" -ge 86400 ];then sess_time="$((sess_s/86400))d$(((sess_s%86400)/3600))h"
elif [ "$sess_s" -ge 36000 ];then sess_time="$((sess_s/3600)).$(((sess_s%3600)/360))h"  # 13.7h: NNhNNm would overflow the 5-char slot
elif [ "$sess_s" -ge 3600 ];then sess_time="$((sess_s/3600))h$(((sess_s%3600)/60))m"
elif [ "$sess_s" -ge 60 ];then sess_time="$((sess_s/60))m"
else sess_time="${sess_s}s"; fi

# CLK: hue ramp, log scale (SPEC.md CLK). permille = clamp(int(500+500*log(s/3600)/log(6)),0,1000); 600 s -> 0, 3600 s -> 500, 21600 s -> 1000; s<=0 -> 0.
_clkp=$(awk -v s="$sess_s" 'BEGIN{if(s<=0){print 0;exit}t=500+500*log(s/3600)/log(6);if(t<0)t=0;if(t>1000)t=1000;print int(t)}'); ramp_c "$_clkp"; sess_color=$BOLD$_c
# Top border carries the col4/col5 column labels. Col4 starts at inner offset 58, col5 at 94.
thdr(){ local L o="═ $1 $(rep ═ $((${2:-12}-3-${#1})))"; for L in SESS 5H 1D 7D 30D ALL; do o+="$(rep ═ $((5-${#L})))$L"; done; printf '%s' "$o"; }  # 42 visible
# FREE has no countdown/bar cell, so its name column shrinks to the longest name (min 7 for the "═ FREE " header); Σ/$ sit under the last letter.
fnw=7; for k in 0 1 2 3; do [ -n "${fmod[k]}" ] && { x=$(fname "${fmod[k]}"); [ "${#x}" -gt "$fnw" ] && fnw=${#x}; }; done; ws[3]=$((fnw+30))
# sess_name: this session's name for the top-left slot (copy-paste address for other agents). STATUSLINE_SESSION_NAME overrides; else walk $PPID up <=6 hops to ~/.claude/sessions/<pid>.json, else match sessionId (payload session_id or transcript basename). ascii, trunc 14 cols, empty -> STATUS.
sess_name(){ local p=$PPID i=0 f="" n="${STATUSLINE_SESSION_NAME:-}" s=$sid d="$HOME/.claude/sessions"; [ -n "$s" ]||{ s=${tpath##*/}; s=${s%.jsonl}; }; if [ -z "$n" ];then while [ "$i" -lt 6 ]&&[ "${p:-0}" -gt 1 ];do [ -f "$d/$p.json" ]&&{ f="$d/$p.json";break; };p=$(ps -o ppid= -p "$p" 2>/dev/null|tr -d ' ');i=$((i+1));done;[ -z "$f" ]&&[ -n "$s" ]&&f=$(grep -l "\"sessionId\":\"$s\"" "$d"/*.json 2>/dev/null|head -1);[ -n "$f" ]&&n=$(jq -r '.name//""' "$f" 2>/dev/null);fi;n=$(ascii "$n"|tr -s " ");n=${n% };n=${n# };[ -n "$n" ]||n=STATUS;trunc "$n" 14; }
sn=$(sess_name); vlen "$sn"  # slot: "═ <name> " + (16-len) ═ = 20 cols, same as "═ STATUS ═══════════"
hdr="═ $sn $(rep ═ $((16-_len)))═$(thdr ANTROP "$onw")═$(thdr OAI "$onw")═$(thdr FREE "$fnw")"
printf '%s╔%s╗%s\n' "$CB" "$hdr" "$R"
# Grand total across Anthropic + OpenAI + free (equiv) all-time usage.
# Lives in col1 rows 5-6 (tokens over cost).
# ANT+OAI session burn rate: (Claude + OpenAI session tokens) / session minutes.
# Model rows 1-4
# FREE table: top-4 free models by all-time tokens, same layout as ANT/OAI; no plan limits so Σ/$ name cells are plain.
# Free volumes are small, so 7D/30D/ALL stay in k/M (tokB would floor them all to .01B).
free_rows=(); for k in 0 1 2 3; do [ -n "${fmod[k]}" ] && free_rows[k]=$(NW=$fnw mrow "$(tier_color "${fmod[k]}")" "$(fname "${fmod[k]}")" "$((k+8))" tok); done
free_rows[4]=$(NW=$fnw tsum 12 -); free_rows[5]=$(NW=$fnw csum 12 ecost -)
row 1 CLK "$(printf '%-5s ' "$sess_time")${R}$(sub2 DSK "$dsk_pct")" "$sess_color" '' "${ant_rows[0]}" "$R" '' "${oai_rows[0]}" "$R" '' "${free_rows[0]}" "$R"
row 2 DIR "$dir_val" "" '' "${ant_rows[1]}" "$R" '' "${oai_rows[1]}" "$R" '' "${free_rows[1]}" "$R"
row 3 '' "${branch_base_color}$(pad 10 "$branch")${R}$(sub2 CPU "$cpu_pct")" "$R" '' "${ant_rows[2]}" "$R" '' "${oai_rows[2]}" "$R" '' "${free_rows[2]}" "$R"
# Col1 left rows 4-6: tokens/min this session, all-time tokens, all-time $ (ANT+OAI). Log-scale color.
# tok6: like tok with one more digit, max 5 chars (9.87B, 11.0B, 432M) for the wider ALL cell.
tok6(){ awk -v n="${1%%.*}" 'BEGIN{n+=0;if(n>=1e9){v=n/1e9;u="B"}else if(n>=1e6){v=n/1e6;u="M"}else if(n>=1e3){v=n/1e3;u="k"}else{printf "%d",n;exit}
 if(v>=100)printf "%d%s",v,u;else if(v>=10)printf "%.1f%s",v,u;else printf "%.2f%s",v,u}'; }
tpm_min=$(( sess_s / 60 )); [ "$tpm_min" -lt 1 ] && tpm_min=1
# TPM counts non-cache tokens (input + output + cache write) of Claude and OpenAI models; cache reads would pin it to the top.
tpm_sum=0; tpm_known=0; for k in 0 1 2 3 4 5 6 7; do case "${sncache[k]}" in ""|*[!0-9]*) ;; *) tpm_sum=$((tpm_sum+${sncache[k]})); tpm_known=1;; esac; done
if [ "$sess_ok" -eq 1 ] && [ "$tpm_known" -eq 1 ]; then tpm_raw=$((tpm_sum / tpm_min)); else tpm_raw=—; fi
kv(){ printf '%s%s%s %s%s%s' "$CN" "$1" "$R" "$2" "$3" "$R"; }
# TPM bands (non-cache tokens per minute): cyan 2k, mid 20k, magenta 200k. TOK is neutral (CN) when the cache is readable, dim (CD) otherwise; DOL likewise.
if [ "$tpm_raw" = — ]; then tpm_c=$CD; else tpm_c=$(awk -v v="$tpm_raw" 'BEGIN{if(v<=0){print "NA";exit}if(v<=2000)t=0;else if(v<=20000)t=500*log(v/2000)/log(10);else t=500+500*log(v/20000)/log(10);if(t>1000)t=1000;print int(t)}'); ramp_t "$tpm_c"; tpm_c=$_c; fi
if [ "$cache_ok" -eq 1 ]; then tok_all=$(tok6 "$all_tokens"); dol_all=$(cost "$all_cost"); else tok_all=—; dol_all=—; fi
tok_c=$CD; dol_c=$CD
if [ "$cache_ok" -eq 1 ]; then tok_c=$CN; dol_c=$CN; fi
c1_tpm=$(pad 10 "$(kv TPM "$tpm_c" "$(tok "$tpm_raw")")")
c1_atok=$(pad 10 "$(kv TOK "$tok_c" "$tok_all")")
c1_acost=$(pad 10 "$(kv DOL "$dol_c" "$dol_all")")
row 4 '' "${c1_tpm}$(sub2 GPU "$gpu_pct")" "$R" '' "${ant_rows[3]}" "$R" '' "${oai_rows[3]}" "$R" '' "${free_rows[3]}" "$R"
row 5 '' "${c1_atok}$(sub2 EFF "$eff_pct" "${eff_l:---}")" "$R" '' "${ant_rows[4]}" "$R" '' "${oai_rows[4]}" "$R" '' "${free_rows[4]}" "$R"
row 6 '' "${c1_acost}$(sub2 CTX "$ctx_ac")" "$R" '' "${ant_rows[5]}" "$R" '' "${oai_rows[5]}" "$R" '' "${free_rows[5]}" "$R"
# Row 5: Σ (sums)
# Row 6: Dollar costs and cache bars in col2
printf '%s╚%s╝%s' "$CB" "$(rep ═ $((ws[0]+ws[1]+ws[2]+ws[3]+3)))" "$R"
[ -f "$SL_LOG" ] && printf 'end   %s pid=%s sid=%s\n' "$(date +%H:%M:%S)" "$$" "${sid:0:8}" >&2
exit 0
