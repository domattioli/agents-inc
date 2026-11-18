#!/usr/bin/env python3
import argparse
import collections
import datetime
import glob
import json
import os
import re
import sqlite3
import sys
import time

DEFAULT_CONFIG = {
    # Padding roster only: the displayed rows are the top 4 exact model ids per provider by ALL-time tokens.
    "claude_models": ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
    "openai_models": ["gpt-6.2-astra", "gpt-6.2-sol", "gpt-6.1-terra", "gpt-6-luna"],
    "subscriptions": {"claude": 100, "openai": 100},
    "prices_json": [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills", "codex-bridge", "reference", "prices.json")],
    "openai_price_estimates": {"gpt-6.2-astra": "claude-fable-5-1", "gpt-6-astra": "claude-fable-5-1", "gpt-5.6-sol": "claude-opus-5", "gpt-5.6-terra": "claude-sonnet-5", "gpt-5.6-luna": "claude-haiku-4-5", "gpt-6.2-sol": "claude-opus-5", "gpt-6.1-sol": "claude-opus-5", "gpt-6.1-terra": "claude-sonnet-5", "gpt-6-luna": "claude-haiku-4-5"},
    "free_price_estimate": "claude-haiku-4-5",
    "cum_default_estimate": "claude-sonnet-5",
    "usage_db": "~/.codex-bridge/usage.db",
    "codex_state_db": "",
    "codex_config_toml": "~/.codex/config.toml",
    "codex_sessions_glob": "~/.codex/sessions/**/*.jsonl",
    "cache_path": "~/.claude/statusline-domi-cache.json",
    "cache_ttl_s": 60,
    "gap_log": "~/.claude/statusline-domi.log"
}

def null_pace():
    return {"usd_per_day": None, "days": None, "hist_days": None, "all_cost": None, "source": None}

def compute_pace(mid, table, now):
    """Pace baseline for one id. table: id -> (first_seen, d28_cost, all_cost). Own 28-day rate once the id has 7+ days
    of history; else the summed history of its family (provider + stem, every id in the table); else all null."""
    first = (table.get(mid) or (None, None, None))[0]
    hist = (now - first) / 86400.0 if first else None
    if hist is not None and hist >= 7:
        days = max(1.0, min(28.0, hist))
        d28c, allc = table[mid][1], table[mid][2]
        return {"usd_per_day": (d28c / days) if d28c is not None else None, "days": days, "hist_days": max(0.0, hist),
                "all_cost": allc, "source": "own"}
    fam = parse_family(mid)
    if not fam:
        return null_pace()
    members = [t for k, t in table.items() if (parse_family(k) or (None, None))[:2] == fam[:2]]
    firsts = [t[0] for t in members if t[0]]
    if not firsts:
        return null_pace()
    fhist = (now - min(firsts)) / 86400.0
    days = max(1.0, min(28.0, fhist))
    d28s = [t[1] for t in members if t[1] is not None]
    alls = [t[2] for t in members if t[2] is not None]
    return {"usd_per_day": (sum(d28s) / days) if d28s else None, "days": days, "hist_days": max(0.0, fhist),
            "all_cost": sum(alls) if alls else None, "source": "family"}

def _rollout_last_usage(path):
    """Cumulative total_token_usage of the last token_count event, read from the file tail; None when absent or unreadable."""
    try:
        size = os.path.getsize(path)
        chunk = 65536
        with open(path, "rb") as f:
            while True:
                start = max(0, size - chunk)
                f.seek(start)
                lines = f.read(size - start).split(b"\n")
                if start > 0:
                    lines = lines[1:]
                for line in reversed(lines):
                    if b'"token_count"' not in line:
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    pl = o.get("payload") or {}
                    u = (pl.get("info") or {}).get("total_token_usage") if pl.get("type") == "token_count" else None
                    if isinstance(u, dict):
                        return u
                if start == 0:
                    return None
                chunk *= 4
    except Exception:
        return None

def empty_result(session_id="", now=None):
    if now is None:
        now = int(time.time())

    models = {}
    for m in DEFAULT_CONFIG["claude_models"] + DEFAULT_CONFIG["openai_models"]:
        prov = "claude" if m in DEFAULT_CONFIG["claude_models"] else "openai"
        label = model_label(m)
        models[m] = {
            "label": label,
            "provider": prov,
            "session": {"tokens": None, "cost": None},
            "h5": {"tokens": None, "cost": None},
            "d1": {"tokens": None, "cost": None},
            "d7": {"tokens": None, "cost": None},
            "d28": {"tokens": None, "cost": None},
            "all": {"tokens": None, "cost": None},
            "first_seen": None,
            "pace": null_pace()
        }
        
    return {
        "schema": 1,
        "session_id": session_id,
        "generated_at": now,
        "codex": {
            "h5": {"used_pct": None, "resets_at": None},
            "d7": {"used_pct": None, "resets_at": None},
            "observed_at": None
        },
        "models": models,
        "openai_total_d7": {"tokens": 0, "requests": 0},
        "claude_d7": {"tokens": 0, "cost": None},
        "claude_today": {"tokens": 0, "cost": None},
        "openai_today": {"tokens": 0, "cost": None},
        "claude_h5": {"tokens": 0, "cost": None},
        "openai_h5": {"tokens": 0, "cost": None},
        "openai_gaps": None,
        "gap_logged": None,
        "free_top4_d7": [],
        "cum_use": {"tokens": 0, "cost": None},
        "claude_all": {"tokens": 0, "cost": None},
        "openai_all": {"tokens": 0, "cost": None},
        "free_all": {"tokens": 0, "equiv_cost": None},
        "history_days": {"claude": None, "openai": None, "free": None},
        "free_windows": {k: {"tokens": 0, "equiv_cost": None} for k in ("session", "today", "d7", "d28")},
        "provider_windows": {p: {w: {"tokens": None, "cost": None} for w in ("h5", "d1", "d7", "d28", "all")} for p in ("claude", "openai", "free")},
        "cache_pct": {"claude": None, "openai": None},
        "session_list_cost": None,
        "sub_ratio_d7": {"claude": None, "openai": None},
        "blended_usd_per_mtok_d7": {"claude": None, "openai": None}
    }

def expand_path(p):
    if not p:
        return p
    return os.path.expanduser(os.path.expandvars(p))

def load_prices(price_paths):
    prices = {}
    for p in price_paths:
        ep = expand_path(p)
        if os.path.exists(ep):
            try:
                with open(ep, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        models_block = data.get("models")
                        if isinstance(models_block, dict):
                            prices.update(models_block)
                        else:
                            prices.update(data)
                        break
            except Exception:
                pass
    return prices

def strip_model_version(model_id):
    if not model_id:
        return model_id
    parts = model_id.split("-")
    if len(parts) > 1 and len(parts[-1]) == 8 and parts[-1].isdigit():
        return "-".join(parts[:-1])
    return model_id

_NORM_CACHE = {}

def normalize_model(model_id):
    """Exact version id: only a trailing 8-digit date suffix is dropped. Versions are never merged."""
    r = _NORM_CACHE.get(model_id, _NORM_CACHE)
    if r is _NORM_CACHE:
        r = _NORM_CACHE[model_id] = strip_model_version(model_id)
    return r

def clean_current_id(model_id):
    """Harness model id -> exact id (drop a trailing [1m]-style tag and date suffix)."""
    if not model_id:
        return None
    return strip_model_version(str(model_id).split("[", 1)[0].strip()) or None

def model_label(model_id):
    """claude-opus-5-5 -> 'Opus 5.5', gpt-5.6-sol -> 'GPT-5.6 Sol'; unknown ids pass through."""
    mid = strip_model_version(model_id or "")
    m = re.match(r"^claude-([a-z]+)-(\d+)(?:-(\d+))?$", mid)
    if m:
        return "%s %s%s" % (m.group(1).capitalize(), m.group(2), "." + m.group(3) if m.group(3) else "")
    m = re.match(r"^gpt-(\d+(?:\.\d+)?)(?:-([a-z0-9]+))?$", mid)
    if m:
        return "GPT-%s%s" % (m.group(1), " " + m.group(2).capitalize() if m.group(2) else "")
    return mid

def read_codex_model(path):
    """Top-level `model = "..."` of ~/.codex/config.toml (before the first [table]); None when absent."""
    ep = expand_path(path)
    if not ep or not os.path.exists(ep):
        return None
    try:
        with open(ep, "r", encoding="utf-8") as f:
            for line in f:
                t = line.strip()
                if t.startswith("["):
                    break
                m = re.match(r"""^model\s*=\s*["']([^"']+)["']""", t)
                if m:
                    return normalize_model(m.group(1))
    except Exception:
        pass
    return None

def pick_rows(candidates, all_tokens, pin, n=4, recent_tokens=None):
    """Top n ids by key (28-day tokens desc, ALL tokens desc, id). recent_tokens = 28-day tokens per id.
    A pin outside the top n replaces row n. Output order uses the same key, so a low pin sorts last."""
    d28 = recent_tokens or {}
    def key(m):
        return (-(d28.get(m) or 0), -(all_tokens.get(m) or 0), m)
    top = sorted(candidates, key=key)[:n]
    if pin and pin in candidates and pin not in top:
        top = top[:n - 1] + [pin]
    return sorted(top, key=key)

_FAMILY_STEMS = ("fable", "opus", "sonnet", "haiku", "astra", "sol", "terra", "luna")

def parse_family(model_id):
    """(provider, stem, (major, minor)) for claude-<stem>-N[-M] and gpt-N[.M]-<stem> with a known stem; else None.
    The family is provider + stem across versions: gpt-5.6-sol and gpt-6.1-sol are one family."""
    mid = strip_model_version(model_id or "")
    m = re.match(r"^claude-([a-z]+)-(\d+)(?:-(\d+))?$", mid)
    if m and m.group(1) in _FAMILY_STEMS:
        return ("claude", m.group(1), (int(m.group(2)), int(m.group(3) or 0)))
    m = re.match(r"^gpt-(\d+)(?:\.(\d+))?-([a-z0-9]+)$", mid)
    if m and m.group(3) in _FAMILY_STEMS:
        return ("openai", m.group(3), (int(m.group(1)), int(m.group(2) or 0)))
    return None

def _priced_entry(prices, model_id):
    p = prices.get(model_id) or prices.get(strip_model_version(model_id))
    return p if isinstance(p, dict) and p.get("input") is not None else None

_PRICE_CACHE = {}

def price_for(model_id, prices, estimates=None):
    """Memoized per (prices, estimates, id) object identity: the collector prices ~300k usage rows per run."""
    key = (id(prices), id(estimates), model_id)
    hit = _PRICE_CACHE.get(key)
    if hit is None:
        hit = _PRICE_CACHE[key] = _price_for(model_id, prices, estimates)
    return hit

def _price_for(model_id, prices, estimates=None):
    """(price_dict, source): exact | family:<id> | estimate:<id> | (None, None).
    Family = nearest priced version at or below the id's, else the lowest priced version above (same provider and stem)."""
    if not model_id or not isinstance(prices, dict):
        return (None, None)
    p = prices.get(model_id) or prices.get(strip_model_version(model_id))
    if p:
        return (p, "exact")
    fam = parse_family(model_id)
    if fam:
        below, above = [], []
        for pid, pv in prices.items():
            f = parse_family(pid)
            if f and f[:2] == fam[:2] and isinstance(pv, dict) and pv.get("input") is not None:
                (below if f[2] <= fam[2] else above).append((f[2], pid, pv))
        pick = max(below, key=lambda t: t[0]) if below else (min(above, key=lambda t: t[0]) if above else None)
        if pick:
            return (pick[2], "family:" + pick[1])
    mapped = estimates.get(model_id) if isinstance(estimates, dict) else None
    if mapped:
        p = _priced_entry(prices, mapped)
        if p:
            return (p, "estimate:" + mapped)
    return (None, None)

_RATE_CACHE = {}

def calculate_cost(model_id, usage_dict, prices, estimates=None):
    key = (id(prices), id(estimates), model_id)
    rates = _RATE_CACHE.get(key, _RATE_CACHE)
    if rates is _RATE_CACHE:
        pinfo, _src = price_for(model_id, prices, estimates)
        try:
            rates = _RATE_CACHE[key] = (float(pinfo.get("input", 0)), float(pinfo.get("output", 0)),
                                        float(pinfo.get("cache_read", 0)), float(pinfo.get("cache_write", 0))) if pinfo else None
        except Exception:
            rates = _RATE_CACHE[key] = None
    if rates is None:
        return None
    try:
        g = usage_dict.get
        return ((g("input_tokens", 0) or 0) * rates[0] + (g("output_tokens", 0) or 0) * rates[1]
                + (g("cache_read_input_tokens", g("cache_read", 0)) or 0) * rates[2]
                + (g("cache_creation_input_tokens", g("cache_write", 0)) or 0) * rates[3]) / 1_000_000.0
    except Exception:
        return None

def calculate_estimated_cost(model_id, usage_dict, prices, estimates):
    mapped = estimates.get(model_id) if isinstance(estimates, dict) else None
    return calculate_cost(mapped, usage_dict, prices) if mapped else None

def parse_iso_to_epoch(iso_str):
    if not iso_str:
        return None
    # If already a number, return it as-is
    if isinstance(iso_str, (int, float)):
        return int(iso_str)
    try:
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(iso_str)
        return int(dt.timestamp())
    except Exception:
        return None

def _rollout_events(path):
    """[(epoch, usage)] of cumulative token_count events; raises on a corrupt line."""
    ev = []
    with open(path, "rb") as f:
        for line in f:
            if b'"token_count"' not in line:
                continue
            o = json.loads(line)
            pl = o.get("payload") or {}
            if pl.get("type") != "token_count":
                continue
            u = (pl.get("info") or {}).get("total_token_usage")
            ts = parse_iso_to_epoch(o.get("timestamp"))
            if isinstance(u, dict) and ts:
                ev.append((ts, u))
    return ev

def _cum(ev, limit, strict):
    last = None
    for ts, u in ev:
        if (ts < limit) if strict else (ts <= limit):
            last = u
    return last

def thread_window_tokens(rows, starts, now, mtime_floor=0):
    """In-window tokens per window and model from rollout token_count deltas.
    rows: (model, created_at, tokens_used, rollout_path, updated_at); starts: {window: epoch}.
    Returns (res, gaps): res[w][model] = tokens/input/cache_read/output/threads; gaps[w][model] = [threads, lifetime tokens].
    Missing rollout or no events: counts tokens_used only if created inside the window, else gap. A corrupt file drops its thread."""
    res = {w: {} for w in starts}
    gaps = {w: {} for w in starts}
    uniq = [0, 0]  # threads with a gap in any window, and their lifetime tokens
    def add(w, model, tok, inp, cr, out):
        r = res[w].setdefault(model, {"tokens": 0, "input": 0, "cache_read": 0, "output": 0, "threads": 0})
        r["tokens"] += tok; r["input"] += inp; r["cache_read"] += cr; r["output"] += out; r["threads"] += 1
    for model, created, used, rpath, upd in rows:
        try:
            model = normalize_model(model)
            if not model:
                continue
            used = int(used or 0)
            ev = None
            # A thread last updated before a window opened has nothing in it: not a contributor, not a gap.
            active = {w: st for w, st in starts.items() if (upd or 0) >= st}
            if not active:
                continue
            p = expand_path(rpath) if rpath else ""
            if p and os.path.isfile(p):
                if os.path.getmtime(p) < min(active.values()):
                    continue
                ev = _rollout_events(p)
            _gapped = False
            for w, st in active.items():
                if ev:
                    hi = _cum(ev, now, False)
                    if hi is None:
                        continue
                    lo = _cum(ev, st, True) or {}
                    def g(k):
                        return max(0, int(hi.get(k) or 0) - int(lo.get(k) or 0))
                    tot = g("total_tokens")
                    cached = min(g("cached_input_tokens"), g("input_tokens"))
                    if tot > 0:
                        add(w, model, tot, g("input_tokens") - cached, cached, g("output_tokens"))
                elif (created or 0) >= st:
                    add(w, model, used, used, 0, 0)  # no category split without a rollout
                elif used > 0:
                    gg = gaps[w].setdefault(model, [0, 0])
                    gg[0] += 1; gg[1] += used
                    if not _gapped:
                        _gapped = True
                        uniq[0] += 1; uniq[1] += used
        except Exception:
            continue
    return res, gaps, uniq

def log_gap_summary(path, line):
    """Append one summary line, only when the log file already exists."""
    try:
        p = expand_path(path)
        if p and os.path.isfile(p):
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass

def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--session-id", default="")
        parser.add_argument("--transcript", default="")
        parser.add_argument("--session-start", type=int, default=0)
        parser.add_argument("--project-dir", default="")
        parser.add_argument("--config", default="")
        parser.add_argument("--out", default="")
        parser.add_argument("--now", type=int, default=None)
        parser.add_argument("--codex-glob", default="")
        parser.add_argument("--usage-db", default="")
        parser.add_argument("--prices", default="")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--claude-h5-resets-at", type=float, default=0)
        parser.add_argument("--current-claude-model", default="")
        args = parser.parse_args()

        now = args.now if args.now is not None else int(time.time())

        # Load config
        cfg = DEFAULT_CONFIG.copy()
        config_path = expand_path(args.config) if args.config else os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    # Rows are discovered from usage (exact ids, top 4 by ALL); a config roster or label table must not pin them.
                    for _k in ("claude_models", "openai_models", "labels"):
                        user_cfg.pop(_k, None)
                    _est = dict(DEFAULT_CONFIG["openai_price_estimates"])
                    _est.update(user_cfg.get("openai_price_estimates") or {})
                    user_cfg["openai_price_estimates"] = _est
                    cfg.update(user_cfg)
            except Exception:
                pass

        out_path = expand_path(args.out) if args.out else expand_path(cfg.get("cache_path", "~/.claude/statusline-domi-cache.json"))
        cache_ttl = int(cfg.get("cache_ttl_s", 60))

        # Check TTL cache skip
        if not args.force and os.path.exists(out_path):
            try:
                mtime = int(os.path.getmtime(out_path))
                if (now - mtime) < cache_ttl:
                    with open(out_path, "r", encoding="utf-8") as cf:
                        cdata = json.load(cf)
                        if cdata.get("session_id") == args.session_id:
                            sys.exit(0)
            except Exception:
                pass

        openai_gaps = None
        gap_logged = None  # last gap summary written to the log, kept in the cache file
        try:
            with open(out_path, "r", encoding="utf-8") as _pf:
                _pg = json.load(_pf).get("gap_logged")
                gap_logged = _pg if isinstance(_pg, dict) else None
        except Exception:
            pass

        # Prices
        price_candidates = []
        if args.prices:
            price_candidates.append(args.prices)
        if isinstance(cfg.get("prices_json"), list):
            price_candidates.extend(cfg["prices_json"])
        elif isinstance(cfg.get("prices_json"), str):
            price_candidates.append(cfg["prices_json"])
        price_candidates.extend(DEFAULT_CONFIG["prices_json"])  # script-relative repo price file: a stale config path must not blank every cost
        prices = load_prices(price_candidates)
        estimates = cfg.get("openai_price_estimates", {})
        free_est = cfg.get("free_price_estimate", "claude-haiku-4-5")
        cum_default = cfg.get("cum_default_estimate", "claude-sonnet-5")
        free_backends = ("gemini", "mistral", "openrouter", "ollama")

        def equiv_cost(backend, model_id, usage):
            """Anthropic-API-equivalent USD: direct price -> tier estimate -> free tier -> default tier."""
            if model_id:
                c = calculate_cost(model_id, usage, prices)
                if c is not None and (c > 0 or backend not in free_backends):
                    return c
                c = calculate_estimated_cost(model_id, usage, prices, estimates)
                if c is not None:
                    return c
            if backend in free_backends:
                return calculate_cost(free_est, usage, prices)
            return calculate_cost(cum_default, usage, prices)

        def tiered_input_price(model_id):
            price, _src = price_for(model_id, prices, estimates)
            if not price or price.get("input") is None:
                price, _src = price_for(cum_default, prices, estimates)
            return float(price["input"]) if price and price.get("input") is not None else None

        # Session transcripts parsing (Claude session tokens/cost)
        session_tokens_map = collections.defaultdict(int)
        # Non-cache session tokens (input + output + cache write): the rate meter; cache reads would pin it to the top.
        session_noncache_map = collections.defaultdict(int)
        session_costs_map = collections.defaultdict(float)
        session_costs_has_val = collections.defaultdict(bool)
        # Prompt-cache hit ratio, session scope (Claude transcript): cache_read / (input + cache_read + cache_write).
        sess_cache = {"read": 0, "total": 0}

        transcript_files = []
        if args.transcript:
            t_path = expand_path(args.transcript)
            if os.path.exists(t_path):
                transcript_files.append(t_path)
                s_dir = os.path.dirname(t_path)
                if args.session_id and s_dir:
                    sub_glob = os.path.join(s_dir, args.session_id, "**", "*.jsonl")
                    transcript_files.extend(glob.glob(sub_glob, recursive=True))

        seen_msg_ids = set()
        for tf in transcript_files:
            try:
                with open(tf, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            row = json.loads(line)
                            if row.get("type") == "assistant":
                                msg = row.get("message", {})
                                msg_id = msg.get("id")
                                if msg_id and msg_id in seen_msg_ids:
                                    continue
                                if msg_id:
                                    seen_msg_ids.add(msg_id)

                                model = msg.get("model")
                                usage = msg.get("usage", {})
                                # Exact version id (date suffix dropped); versions are never merged.
                                base_model = normalize_model(model) if model else None
                                if base_model and base_model.startswith("claude-"):
                                    i = usage.get("input_tokens", 0) or 0
                                    o = usage.get("output_tokens", 0) or 0
                                    cr = usage.get("cache_read_input_tokens", 0) or 0
                                    cw = usage.get("cache_creation_input_tokens", 0) or 0
                                    tot = i + o + cr + cw
                                    session_tokens_map[base_model] += tot
                                    session_noncache_map[base_model] += i + o + cw
                                    sess_cache["read"] += cr
                                    sess_cache["total"] += i + cr + cw

                                    c = calculate_cost(base_model, usage, prices)
                                    if c is not None:
                                        session_costs_map[base_model] += c
                                        session_costs_has_val[base_model] = True
                        except Exception:
                            continue
            except Exception:
                continue

        # usage.db parsing
        db_path = expand_path(args.usage_db) if args.usage_db else expand_path(cfg.get("usage_db", ""))

        # Row discovery: every exact model id seen per provider is a candidate; the top 4 by 28-day tokens
        # are shown (see pick_rows below). Candidates also include the pins and transcript models.
        claude_pin = clean_current_id(args.current_claude_model)
        if claude_pin and not claude_pin.startswith("claude-"):
            claude_pin = None
        openai_pin = read_codex_model(cfg.get("codex_config_toml", ""))
        cand_claude = set(session_tokens_map.keys())
        cand_openai = set()
        if claude_pin:
            cand_claude.add(claude_pin)
        if openai_pin:
            cand_openai.add(openai_pin)
        if db_path and os.path.exists(db_path):
            try:
                _c = sqlite3.connect(db_path)
                for (_m,) in _c.execute("SELECT DISTINCT model FROM usage WHERE backend = 'claude' AND model IS NOT NULL AND model != ''"):
                    cand_claude.add(normalize_model(_m))
                for (_m,) in _c.execute("SELECT DISTINCT model FROM usage WHERE backend IN ('codex', 'openai') AND model IS NOT NULL AND model != ''"):
                    cand_openai.add(normalize_model(_m))
                _c.close()
            except Exception:
                pass
        _sdb = expand_path(cfg.get("codex_state_db", "~/.codex/state_5.sqlite"))
        if _sdb and os.path.exists(_sdb):
            try:
                _c = sqlite3.connect("file:{}?mode=ro".format(_sdb), uri=True)
                for (_m,) in _c.execute("SELECT DISTINCT model FROM threads WHERE tokens_used > 0 AND model IS NOT NULL AND model != ''"):
                    cand_openai.add(normalize_model(_m))
                _c.close()
            except Exception:
                pass
        # Pad to 4 from the default roster so a provider with little history still renders 4 rows.
        # Row candidates only: non-claude ids logged under backend claude never become rows, but
        # cfg["claude_models"] (which feeds provider_windows sums) keeps them as before.
        row_claude = {m for m in cand_claude if m.startswith("claude-")}
        for _m in DEFAULT_CONFIG["claude_models"]:
            if len(row_claude) >= 4:
                break
            row_claude.add(_m)
        for _m in DEFAULT_CONFIG["claude_models"]:
            if len(cand_claude) >= 4:
                break
            cand_claude.add(_m)
        cand_claude |= row_claude
        for _m in DEFAULT_CONFIG["openai_models"]:
            if len(cand_openai) >= 4:
                break
            cand_openai.add(_m)
        cfg["claude_models"] = sorted(cand_claude)
        cfg["openai_models"] = sorted(cand_openai)
        d1_models_data = {m: {"tokens": 0, "cost": 0.0, "has_cost": False} for m in cfg["claude_models"] + cfg["openai_models"]}
        d7_models_data = {m: {"tokens": 0, "cost": 0.0, "has_cost": False} for m in cfg["claude_models"] + cfg["openai_models"]}
        d28_models_data = {m: {"tokens": 0, "cost": 0.0, "has_cost": False} for m in cfg["claude_models"] + cfg["openai_models"]}
        all_models_data = {m: {"tokens": 0, "cost": 0.0, "has_cost": False} for m in cfg["claude_models"] + cfg["openai_models"]}
        cum_other = {"tokens": 0, "cost": 0.0}
        cum_openai_db = {"tokens": 0, "cost": 0.0}
        claude_all_tok = 0
        claude_all_cost = 0.0
        claude_all_has_cost = False
        openai_all_tok = 0
        openai_all_cost = 0.0
        openai_all_has_cost = False
        free_all_tok = 0
        free_all_cost = 0.0
        # Provider-wide 28-day totals (all rows of the provider, not only the configured model cells).
        claude_d28_tok = 0
        claude_d28_cost = 0.0
        claude_d28_has_cost = False
        openai_d28_tok = 0
        openai_d28_cost = 0.0
        openai_d28_has_cost = False
        # Earliest usage record per provider (epoch s), same sources as the *_all totals.
        first_ts = {"claude": None, "openai": None, "free": None}

        first_by_id = {}   # exact id -> earliest epoch over usage.db rows (any backend) and Codex threads
        thr_all = {}       # exact id -> {"tokens", "cost", "has"}: lifetime thread totals priced by category (rollout) or uncached input (no rollout)

        def note_id_first(mid, epoch):
            if mid and epoch and (mid not in first_by_id or epoch < first_by_id[mid]):
                first_by_id[mid] = int(epoch)

        def note_first(key, epoch):
            if epoch and (first_ts[key] is None or epoch < first_ts[key]):
                first_ts[key] = epoch
        openai_total_d7_tokens = 0
        openai_total_d7_requests = 0
        claude_d7_tokens = 0
        claude_d7_cost = 0.0
        claude_d7_has_cost = False
        provider_today = {
            "claude": {"tokens": 0, "cost": 0.0, "has_cost": False},
            "openai": {"tokens": 0, "cost": 0.0, "has_cost": False},
        }
        free_top4_d7 = []
        free_windows = {k: {"tokens": 0, "equiv_cost": None} for k in ("session", "today", "d7", "d28")}
        cache_pct = {"claude": None, "openai": None}

        # Codex limits parsing (must happen BEFORE calculating h5 window starts)
        codex_glob_pat = expand_path(args.codex_glob) if args.codex_glob else expand_path(cfg.get("codex_sessions_glob", "~/.codex/sessions/**/*.jsonl"))
        codex_res = {
            "h5": {"used_pct": None, "resets_at": None},
            "d7": {"used_pct": None, "resets_at": None},
            "observed_at": None
        }
        try:
            matched_files = glob.glob(codex_glob_pat, recursive=True)
            if matched_files:
                matched_files.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
                newest_files = matched_files[:500]
                found_limit = False
                for nf in newest_files:
                    if found_limit:
                        break
                    try:
                        with open(nf, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            for line in reversed(lines):
                                if "rate_limits" in line:
                                    try:
                                        jline = json.loads(line)
                                        payload = jline.get("payload", {})
                                        rls = payload.get("rate_limits")
                                        if isinstance(rls, list):
                                            for rl in rls:
                                                if rl.get("limit_id") == "codex" and rl.get("primary") is not None:
                                                    primary = rl.get("primary", {})
                                                    secondary = rl.get("secondary", {})
                                                    codex_res["h5"]["used_pct"] = primary.get("used_percent")
                                                    codex_res["h5"]["resets_at"] = parse_iso_to_epoch(primary.get("resets_at"))
                                                    codex_res["d7"]["used_pct"] = secondary.get("used_percent")
                                                    codex_res["d7"]["resets_at"] = parse_iso_to_epoch(secondary.get("resets_at"))
                                                    codex_res["observed_at"] = parse_iso_to_epoch(jline.get("timestamp"))
                                                    found_limit = True
                                                    break
                                        elif isinstance(rls, dict):
                                            if rls.get("limit_id") == "codex" and rls.get("primary") is not None:
                                                primary = rls.get("primary", {})
                                                secondary = rls.get("secondary", {})
                                                codex_res["h5"]["used_pct"] = primary.get("used_percent")
                                                codex_res["h5"]["resets_at"] = parse_iso_to_epoch(primary.get("resets_at"))
                                                codex_res["d7"]["used_pct"] = secondary.get("used_percent")
                                                codex_res["d7"]["resets_at"] = parse_iso_to_epoch(secondary.get("resets_at"))
                                                codex_res["observed_at"] = parse_iso_to_epoch(jline.get("timestamp"))
                                                found_limit = True
                                                break
                                    except Exception:
                                        continue
                    except Exception:
                        continue
        except Exception:
            pass

        # 5-hour window aggregates initialization (using codex_res now available)
        claude_h5_data = {"tokens": 0, "cost": 0.0, "has_cost": False}
        openai_h5_data = {"tokens": 0, "cost": 0.0, "has_cost": False}
        openai_h5_other = {"tokens": 0, "cost": 0.0, "has_cost": False}  # usage.db 5H rows of no configured model
        h5_models_data = {m: {"tokens": 0, "cost": 0.0, "has_cost": False} for m in cfg["claude_models"] + cfg["openai_models"]}
        claude_h5_resets_at = int(args.claude_h5_resets_at) if args.claude_h5_resets_at else 0
        claude_h5_window_start = claude_h5_resets_at - 5 * 3600 if claude_h5_resets_at > 0 else 0
        codex_h5_resets_at = codex_res["h5"]["resets_at"] if codex_res["h5"]["resets_at"] else 0
        codex_h5_window_start = codex_h5_resets_at - 5 * 3600 if codex_h5_resets_at > 0 else 0
        codex_h5_ended = 0 < codex_h5_resets_at <= now
        if codex_h5_ended:
            # The newest known 5H window has closed: nothing is in it, and its reset time is no longer a fact.
            codex_h5_window_start = 0
            codex_res["h5"]["resets_at"] = None

        if db_path and os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()

                # Convert session_start epoch to ISO string for comparison
                session_start_iso = ""
                if args.session_start:
                    session_start_iso = datetime.datetime.fromtimestamp(args.session_start, datetime.timezone.utc).isoformat()

                # Query 7d data grouped by backend/model
                query_7d = """
                    SELECT backend, model,
                           SUM(input_tokens + output_tokens + coalesce(cache_read,0) + coalesce(cache_write,0)) as toks,
                           COUNT(*) as reqs
                    FROM usage
                    WHERE day >= date('now','localtime','-6 days')
                    GROUP BY backend, model
                """
                cur.execute(query_7d)
                rows = cur.fetchall()
                
                # We also need to map costs for 7d. Let's fetch all rows for 7d with full columns to calculate costs precisely per model
                query_7d_details = """
                    SELECT backend, model, input_tokens, output_tokens, cache_read, cache_write
                    FROM usage
                    WHERE day >= date('now','localtime','-6 days')
                """
                cur.execute(query_7d_details)
                for b, m, i, o, cr, cw in cur.fetchall():
                    tot = (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                    base_m = normalize_model(m) if m else None
                    if base_m and base_m in d7_models_data:
                        d7_models_data[base_m]["tokens"] += tot
                        c = calculate_cost(base_m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices)
                        if c is None and base_m in cfg["openai_models"]:
                            c = calculate_estimated_cost(base_m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices, estimates)
                        if c is not None:
                            d7_models_data[base_m]["cost"] += c
                            d7_models_data[base_m]["has_cost"] = True

                    # Include codex rows in openai_total_d7 (even with model=null)
                    if b == "codex" or b == "openai" or (base_m and base_m in cfg["openai_models"]):
                        openai_total_d7_tokens += tot
                        openai_total_d7_requests += 1

                    if b == "claude" or (base_m and base_m in cfg["claude_models"]):
                        claude_d7_tokens += tot
                        c = calculate_cost(base_m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices)
                        if c is not None:
                            claude_d7_cost += c
                            claude_d7_has_cost = True

                # Today-only provider totals use the same local-day cutoff as
                # the rolling windows above. Unknown OpenAI rows still count
                # tokens, but do not receive an invented cost.
                cur.execute("""
                    SELECT backend, model, input_tokens, output_tokens, cache_read, cache_write
                    FROM usage
                    WHERE day >= date('now','localtime')
                """)
                for b, m, i, o, cr, cw in cur.fetchall():
                    base_m = normalize_model(m) if m else None
                    if b == "claude" or (base_m and base_m in cfg["claude_models"]):
                        provider = "claude"
                    elif b in ("codex", "openai") or (base_m and base_m in cfg["openai_models"]):
                        provider = "openai"
                    else:
                        continue
                    u = {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}
                    provider_today[provider]["tokens"] += sum((i or 0, o or 0, cr or 0, cw or 0))
                    c = calculate_cost(base_m, u, prices)
                    if c is None and provider == "openai":
                        c = calculate_estimated_cost(base_m, u, prices, estimates)
                    if c is not None:
                        provider_today[provider]["cost"] += c
                        provider_today[provider]["has_cost"] = True

                # 1-day (today, local day) per-model window, same shape as 7d.
                cur.execute("""
                    SELECT backend, model, input_tokens, output_tokens, cache_read, cache_write
                    FROM usage
                    WHERE day >= date('now','localtime')
                """)
                for b, m, i, o, cr, cw in cur.fetchall():
                    base_m = normalize_model(m) if m else None
                    if base_m and base_m in d1_models_data:
                        u = {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}
                        d1_models_data[base_m]["tokens"] += (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                        c = calculate_cost(base_m, u, prices)
                        if c is None and base_m in cfg["openai_models"]:
                            c = calculate_estimated_cost(base_m, u, prices, estimates)
                        if c is not None:
                            d1_models_data[base_m]["cost"] += c
                            d1_models_data[base_m]["has_cost"] = True

                # 28-day ("Mo") per-model window, same shape as 7d.
                cur.execute("""
                    SELECT backend, model, input_tokens, output_tokens, cache_read, cache_write
                    FROM usage
                    WHERE day >= date('now','localtime','-27 days')
                """)
                for b, m, i, o, cr, cw in cur.fetchall():
                    base_m = normalize_model(m) if m else None
                    # Provider-wide d28: same classification and cost model as the all-time block.
                    _u28 = {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}
                    _t28 = (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                    if b == "claude" or (base_m and base_m in cfg["claude_models"]):
                        claude_d28_tok += _t28
                        _c28 = calculate_cost(base_m, _u28, prices)
                        if _c28 is not None:
                            claude_d28_cost += _c28
                            claude_d28_has_cost = True
                    elif b in ("codex", "openai") or (base_m and base_m in cfg["openai_models"]):
                        openai_d28_tok += _t28
                        _c28 = calculate_cost(base_m, _u28, prices)
                        if _c28 is None:
                            _c28 = calculate_estimated_cost(base_m, _u28, prices, estimates)
                        if _c28 is not None:
                            openai_d28_cost += _c28
                            openai_d28_has_cost = True
                    if base_m and base_m in d28_models_data:
                        u = {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}
                        d28_models_data[base_m]["tokens"] += (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                        c = calculate_cost(base_m, u, prices)
                        if c is None and base_m in cfg["openai_models"]:
                            c = calculate_estimated_cost(base_m, u, prices, estimates)
                        if c is not None:
                            d28_models_data[base_m]["cost"] += c
                            d28_models_data[base_m]["has_cost"] = True

                # All-time cumulative per-model window, same shape as 7d/28d.
                cur.execute("""
                    SELECT backend, model, input_tokens, output_tokens, cache_read, cache_write
                    FROM usage
                """)
                for b, m, i, o, cr, cw in cur.fetchall():
                    base_m = normalize_model(m) if m else None
                    if base_m and base_m in all_models_data:
                        u = {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}
                        all_models_data[base_m]["tokens"] += (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                        c = calculate_cost(base_m, u, prices)
                        if c is None and base_m in cfg["openai_models"]:
                            c = calculate_estimated_cost(base_m, u, prices, estimates)
                        if c is not None:
                            all_models_data[base_m]["cost"] += c
                            all_models_data[base_m]["has_cost"] = True

                # First usage per exact id, over every row of the id whatever backend it was stored under.
                cur.execute("SELECT model, MIN(ts) FROM usage WHERE model IS NOT NULL AND model != '' GROUP BY model")
                for _m, _ts in cur.fetchall():
                    note_id_first(normalize_model(_m), parse_iso_to_epoch(_ts))

                # All-time cumulative use, priced at Anthropic API equivalents.
                cur.execute("""
                    SELECT backend, model, SUM(input_tokens), SUM(output_tokens),
                           SUM(coalesce(cache_read,0)), SUM(coalesce(cache_write,0)), MIN(ts)
                    FROM usage GROUP BY backend, model
                """)
                for b, m, i, o, cr, cw, min_ts in cur.fetchall():
                    base_m = normalize_model(m) if m else None
                    u = {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}
                    tot = (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                    c = equiv_cost(b, base_m, u) or 0.0
                    is_openai = (b in ("codex", "openai") or (base_m and base_m in cfg["openai_models"]))
                    is_claude = (b == "claude" or (base_m and base_m in cfg["claude_models"]))
                    is_free = b in free_backends
                    bucket = cum_openai_db if is_openai else cum_other
                    bucket["tokens"] += tot
                    bucket["cost"] += c
                    # Same provider classification and cost model as the
                    # today/h5 blocks, no time filter (all-time totals).
                    if is_claude:
                        note_first("claude", parse_iso_to_epoch(min_ts))
                        claude_all_tok += tot
                        cc = calculate_cost(base_m, u, prices)
                        if cc is not None:
                            claude_all_cost += cc
                            claude_all_has_cost = True
                    elif is_openai:
                        note_first("openai", parse_iso_to_epoch(min_ts))
                        openai_all_tok += tot
                        cc = calculate_cost(base_m, u, prices)
                        if cc is None:
                            cc = calculate_estimated_cost(base_m, u, prices, estimates)
                        if cc is not None:
                            openai_all_cost += cc
                            openai_all_has_cost = True
                    elif is_free:
                        note_first("free", parse_iso_to_epoch(min_ts))
                        free_all_tok += tot
                        free_all_cost += equiv_cost(b, base_m, u) or 0.0

                # Free top4 (only gemini, mistral, openrouter, ollama): ranked by all-time tokens so rows
                # stay visible after a week without free use; the sums returned are still the 7D window.
                query_free = """
                    SELECT backend, model,
                           SUM(CASE WHEN d7 THEN input_tokens ELSE 0 END),
                           SUM(CASE WHEN d7 THEN output_tokens ELSE 0 END),
                           SUM(CASE WHEN d7 THEN coalesce(cache_read,0) ELSE 0 END),
                           SUM(CASE WHEN d7 THEN coalesce(cache_write,0) ELSE 0 END),
                           SUM(CASE WHEN d7 THEN tot ELSE 0 END) as toks,
                           SUM(tot) as all_toks
                    FROM (SELECT *, day >= date('now','localtime','-6 days') AS d7,
                                 input_tokens + output_tokens + coalesce(cache_read,0) + coalesce(cache_write,0) AS tot
                          FROM usage
                          WHERE backend IN ('gemini', 'mistral', 'openrouter', 'ollama'))
                    GROUP BY backend, model
                    HAVING all_toks > 0
                    ORDER BY all_toks DESC
                    LIMIT 4
                """
                cur.execute(query_free)
                free_rows = cur.fetchall()
                for b, m, fi, fo, fcr, fcw, toks, _all_toks in free_rows:
                    d7_usage = {"input_tokens": fi, "output_tokens": fo,
                                "cache_read": fcr, "cache_write": fcw}
                    if session_start_iso:
                        sess_sql = ("SELECT SUM(input_tokens), SUM(output_tokens),"
                                    " SUM(coalesce(cache_read,0)), SUM(coalesce(cache_write,0)),"
                                    " SUM(input_tokens + output_tokens + coalesce(cache_read,0)"
                                    " + coalesce(cache_write,0)) FROM usage"
                                    " WHERE backend IS ? AND model IS ? AND ts >= ?")
                        sess_params = (b, m, session_start_iso)
                    else:
                        sess_sql = ("SELECT SUM(input_tokens), SUM(output_tokens),"
                                    " SUM(coalesce(cache_read,0)), SUM(coalesce(cache_write,0)),"
                                    " SUM(input_tokens + output_tokens + coalesce(cache_read,0)"
                                    " + coalesce(cache_write,0)) FROM usage"
                                    " WHERE backend IS ? AND model IS ? AND uid = ?")
                        sess_params = (b, m, args.session_id)
                    cur.execute(sess_sql, sess_params)
                    srow = cur.fetchone() or (0, 0, 0, 0, 0)
                    sess_usage = {"input_tokens": srow[0], "output_tokens": srow[1],
                                  "cache_read": srow[2], "cache_write": srow[3]}
                    # Extra windows so the FREE table matches the ANT/OAI layout (SESS 5H 1D 7D 28D ALL).
                    _h5_iso = datetime.datetime.fromtimestamp(time.time() - 5 * 3600, datetime.timezone.utc).isoformat()
                    _win = {}
                    for _wn, _wsql, _wp in (("h5", "ts >= ?", (_h5_iso,)),
                                            ("d1", "day >= date('now','localtime')", ()),
                                            ("d28", "day >= date('now','localtime','-27 days')", ()),
                                            ("all", "1=1", ())):
                        cur.execute("SELECT SUM(input_tokens), SUM(output_tokens), SUM(coalesce(cache_read,0)),"
                                    " SUM(coalesce(cache_write,0)) FROM usage WHERE backend IS ? AND model IS ? AND " + _wsql,
                                    (b, m) + _wp)
                        _r = cur.fetchone() or (0, 0, 0, 0)
                        _u = {"input_tokens": _r[0], "output_tokens": _r[1], "cache_read": _r[2], "cache_write": _r[3]}
                        _t = sum(int(x or 0) for x in _r)
                        _win[_wn] = {"tokens": _t, "equiv_cost": equiv_cost(b, normalize_model(m), _u) if _t else None}
                    _fid = normalize_model(m) if m else None
                    free_top4_d7.append({
                        "_fid": _fid,
                        "h5": _win["h5"], "d1": _win["d1"], "d28": _win["d28"], "all": _win["all"],
                        "backend": str(b or "unknown"),
                        "model": str(m or "unknown"),
                        "tokens": int(toks or 0),
                        "session": {
                            "tokens": int(srow[4] or 0),
                            "cost": calculate_cost(normalize_model(m), sess_usage, prices),
                            "equiv_cost": equiv_cost(b, normalize_model(m), sess_usage)
                        },
                        "d7": {
                            "tokens": int(toks or 0),
                            "cost": calculate_cost(normalize_model(m), d7_usage, prices),
                            "equiv_cost": equiv_cost(b, normalize_model(m), d7_usage)
                        }
                    })

                # Free-backend window totals (session / today / 28d) for the statusline FREE table.
                for wname, wsql, wparams in (
                    ("session", "ts >= ?" if session_start_iso else "uid = ?",
                     (session_start_iso if session_start_iso else args.session_id,)),
                    ("today", "day >= date('now','localtime')", ()),
                    ("d7", "day >= date('now','localtime','-6 days')", ()),
                    ("d28", "day >= date('now','localtime','-27 days')", ()),
                ):
                    cur.execute(
                        "SELECT backend, model, SUM(input_tokens), SUM(output_tokens),"
                        " SUM(coalesce(cache_read,0)), SUM(coalesce(cache_write,0)) FROM usage"
                        " WHERE backend IN ('gemini', 'mistral', 'openrouter', 'ollama') AND " + wsql +
                        " GROUP BY backend, model", wparams)
                    wtok = 0
                    wcost = 0.0
                    for b, m, i, o, cr, cw in cur.fetchall():
                        u = {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}
                        wtok += (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                        wcost += equiv_cost(b, normalize_model(m) if m else None, u) or 0.0
                    free_windows[wname] = {"tokens": int(wtok), "equiv_cost": wcost if wtok > 0 else None}

                # Prompt-cache hit ratio today per provider (DB). Session-scope Claude value (transcript) overrides when present.
                cache_pct = {"claude": None, "openai": None}
                for prov, bsql in (("claude", "backend = 'claude'"), ("openai", "backend IN ('codex', 'openai')")):
                    cur.execute("SELECT coalesce(SUM(cache_read),0), coalesce(SUM(input_tokens + coalesce(cache_read,0) + coalesce(cache_write,0)),0) FROM usage WHERE " + bsql + " AND day >= date('now','localtime')")
                    crd, ctot = cur.fetchone() or (0, 0)
                    if ctot and ctot > 0:
                        cache_pct[prov] = round(100.0 * crd / ctot, 1)

                # 5-hour window queries for Claude and Codex (after all other queries)
                if claude_h5_window_start > 0:
                    claude_h5_start_iso = datetime.datetime.fromtimestamp(claude_h5_window_start, datetime.timezone.utc).isoformat()
                    try:
                        cur.execute("""
                            SELECT backend, model, input_tokens, output_tokens, cache_read, cache_write
                            FROM usage
                            WHERE ts >= ? AND (backend='claude' OR model IN ({}))
                        """.format(','.join(['?' for _ in cfg["claude_models"]])), [claude_h5_start_iso] + cfg["claude_models"])
                        for b, m, i, o, cr, cw in cur.fetchall():
                            base_m = normalize_model(m) if m else None
                            if base_m and base_m in cfg["claude_models"]:
                                tot = (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                                claude_h5_data["tokens"] += tot
                                h5_models_data[base_m]["tokens"] += tot
                                c = calculate_cost(base_m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices)
                                if c is not None:
                                    claude_h5_data["cost"] += c
                                    claude_h5_data["has_cost"] = True
                                    h5_models_data[base_m]["cost"] += c
                                    h5_models_data[base_m]["has_cost"] = True
                    except Exception:
                        pass

                if codex_h5_window_start > 0:
                    codex_h5_start_iso = datetime.datetime.fromtimestamp(codex_h5_window_start, datetime.timezone.utc).isoformat()
                    try:
                        cur.execute("""
                            SELECT backend, model, input_tokens, output_tokens, cache_read, cache_write
                            FROM usage
                            WHERE ts >= ? AND (backend='codex' OR backend='openai' OR model IN ({}))
                        """.format(','.join(['?' for _ in cfg["openai_models"]])), [codex_h5_start_iso] + cfg["openai_models"])
                        for b, m, i, o, cr, cw in cur.fetchall():
                            base_m = normalize_model(m) if m else None
                            tot = (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                            c = calculate_cost(base_m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices, estimates)
                            # Pair tokens and cost from the same rows: per configured model, else the "other" bucket.
                            tgt = h5_models_data[base_m] if base_m in h5_models_data else openai_h5_other
                            tgt["tokens"] += tot
                            if c is not None:
                                tgt["cost"] += c
                                tgt["has_cost"] = True
                    except Exception:
                        pass

                conn.close()
            except Exception:
                pass

        # Parse session usage for OpenAI models from usage.db (ts >= session_start)
        openai_session_tokens_map = {m: 0 for m in cfg["openai_models"]}
        openai_session_noncache_map = {m: 0 for m in cfg["openai_models"]}
        openai_session_from_threads = set()  # models whose session total was raised by the Codex thread fallback (no cache split)
        openai_session_costs_map = {m: 0.0 for m in cfg["openai_models"]}
        openai_session_costs_has_val = {m: False for m in cfg["openai_models"]}

        if db_path and os.path.exists(db_path) and args.session_start:
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()

                session_start_iso = datetime.datetime.fromtimestamp(args.session_start, datetime.timezone.utc).isoformat()
                query_session = """
                    SELECT model, input_tokens, output_tokens, cache_read, cache_write
                    FROM usage
                    WHERE ts >= ? AND (backend='openai' OR model IN ({}))
                """.format(','.join(['?' for _ in cfg["openai_models"]]))  # nosec B608 — only the count of '?' placeholders is interpolated; all values are bound parameters
                params = [session_start_iso] + cfg["openai_models"]
                cur.execute(query_session, params)

                for m, i, o, cr, cw in cur.fetchall():
                    m = normalize_model(m)
                    if m in openai_session_tokens_map:
                        tot = (i or 0) + (o or 0) + (cr or 0) + (cw or 0)
                        openai_session_tokens_map[m] += tot
                        openai_session_noncache_map[m] += (i or 0) + (o or 0) + (cw or 0)
                        c = calculate_cost(m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices)
                        if c is not None:
                            openai_session_costs_map[m] += c
                            openai_session_costs_has_val[m] = True

                conn.close()
            except Exception:
                pass

        # ChatGPT-plan calls are absent from usage.db here. Fall back to Codex's
        # per-thread state. Boundary assignment is estimated for spanning threads.
        state_db = expand_path(cfg.get("codex_state_db", "~/.codex/state_5.sqlite"))
        if state_db and os.path.exists(state_db):
            try:
                conn = sqlite3.connect("file:{}?mode=ro".format(state_db), uri=True)
                cur = conn.cursor()
                # Window cells count only in-window tokens: rollout token_count deltas per thread (see thread_window_tokens).
                _mid_dt = datetime.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
                def _local_mid(back):
                    return int(time.mktime((_mid_dt - datetime.timedelta(days=back)).timetuple()))
                _starts = {"d1": _local_mid(0), "d7": _local_mid(6), "d28": _local_mid(27)}
                if codex_h5_window_start > 0:
                    _starts["h5"] = int(codex_h5_window_start)
                _floor = min(_starts.values())
                cur.execute("SELECT model, created_at, tokens_used, rollout_path, updated_at FROM threads WHERE updated_at >= ? AND tokens_used > 0", (_floor,))
                _res, _gaps, _uniq = thread_window_tokens(cur.fetchall(), _starts, now, _floor)
                openai_gaps = {"threads": _uniq[0], "tokens": _uniq[1]}
                if _uniq[0] and openai_gaps != gap_logged:
                    log_gap_summary(cfg.get("gap_log", ""), "gaps openai {} threads {} tokens".format(_uniq[0], _uniq[1]))
                    gap_logged = dict(openai_gaps)

                def _take(window, data_map):
                    """Per-model larger of usage.db and threads; the winner supplies both tokens and cost."""
                    gained = 0
                    _take.cost_delta = 0.0
                    for model, r in _res.get(window, {}).items():
                        if model in data_map and r["tokens"] > data_map[model]["tokens"]:
                            gained += r["tokens"] - data_map[model]["tokens"]
                            c = calculate_cost(model, {"input_tokens": r["input"], "output_tokens": r["output"], "cache_read": r["cache_read"]}, prices, estimates)
                            _take.cost_delta += (c or 0.0) - (data_map[model]["cost"] if data_map[model]["has_cost"] else 0.0)
                            data_map[model].update({"tokens": r["tokens"], "cost": c or 0.0, "has_cost": c is not None})
                    return gained
                openai_total_d7_tokens += _take("d7", d7_models_data)
                openai_total_d7_requests += sum(r["threads"] for r in _res.get("d7", {}).values())
                if "h5" in _starts:
                    _take("h5", h5_models_data)
                _take("d1", d1_models_data)
                openai_d28_tok += _take("d28", d28_models_data)
                if _take.cost_delta:
                    openai_d28_cost += _take.cost_delta  # provider 28D cost follows the chosen source
                    openai_d28_has_cost = True
                def _thread_cost(model, used, rpath):
                    """One thread priced by category (running totals at its last rollout event); no rollout -> uncached input."""
                    p = expand_path(rpath) if rpath else ""
                    lu = _rollout_last_usage(p) if p and os.path.isfile(p) else None
                    if lu:
                        cached = min(int(lu.get("cached_input_tokens") or 0), int(lu.get("input_tokens") or 0))
                        u = {"input_tokens": int(lu.get("input_tokens") or 0) - cached, "output_tokens": int(lu.get("output_tokens") or 0), "cache_read": cached}
                    else:
                        u = {"input_tokens": used}
                    return calculate_cost(model, u, prices, estimates)
                # Lifetime thread totals priced like the window cells: running totals at each thread's last rollout event
                # by category; no rollout -> uncached input (such threads are the no-usable-rollout gap class).
                cur.execute("SELECT model, created_at, tokens_used, rollout_path FROM threads WHERE tokens_used > 0")
                for raw_model, created, used, rpath in cur.fetchall():
                    model = normalize_model(raw_model)
                    if not model:
                        continue
                    note_id_first(model, created)
                    used = int(used or 0)
                    c = _thread_cost(model, used, rpath)
                    t = thr_all.setdefault(model, {"tokens": 0, "cost": 0.0, "has": False})
                    t["tokens"] += used
                    if c is not None:
                        t["cost"] += c
                        t["has"] = True
                cur.execute("SELECT model, SUM(tokens_used) FROM threads WHERE tokens_used > 0 GROUP BY model")
                state_all = {"tokens": 0, "cost": 0.0}
                for raw_model, tokens in cur.fetchall():
                    model = normalize_model(raw_model)
                    state_all["tokens"] += int(tokens or 0)
                    _t = thr_all.get(model)
                    if _t and _t["has"]:
                        state_all["cost"] += _t["cost"]
                    else:
                        ip = tiered_input_price(model)
                        state_all["cost"] += (int(tokens or 0) / 1_000_000.0) * ip if ip is not None else 0.0
                    # Per-model ALL = all-time thread total when larger than usage.db (was capped at the 28-day thread total).
                    if model in all_models_data and int(tokens or 0) > all_models_data[model]["tokens"]:
                        all_models_data[model]["tokens"] = int(tokens or 0)
                        if _t and _t["has"]:
                            all_models_data[model]["cost"] = _t["cost"]
                            all_models_data[model]["has_cost"] = True
                        else:
                            price = prices.get(model) or (prices.get(estimates.get(model)) if isinstance(estimates, dict) and estimates.get(model) else None)
                            if price and price.get("input") is not None:
                                all_models_data[model]["cost"] = (int(tokens or 0) / 1_000_000.0) * float(price["input"])
                                all_models_data[model]["has_cost"] = True
                if state_all["tokens"] > cum_openai_db["tokens"]:
                    cum_openai_db = state_all
                if state_all["tokens"] > openai_all_tok:
                    openai_all_tok = state_all["tokens"]
                    openai_all_cost = state_all["cost"]
                    openai_all_has_cost = state_all["cost"] > 0
                    cur.execute("SELECT MIN(created_at) FROM threads WHERE tokens_used > 0")
                    _row = cur.fetchone()
                    first_ts["openai"] = int(_row[0]) if _row and _row[0] else first_ts["openai"]
                if args.session_start:
                    cur.execute("""
                        SELECT model, tokens_used, rollout_path FROM threads
                        WHERE created_at >= ? AND tokens_used > 0 AND (? = '' OR cwd = ? OR cwd LIKE ? || '/%')
                    """, (args.session_start, args.project_dir, args.project_dir, args.project_dir))  # other projects' threads are not this session
                    _sess = {}
                    for raw_model, used, rpath in cur.fetchall():
                        model = normalize_model(raw_model)
                        d = _sess.setdefault(model, {"tokens": 0, "cost": 0.0, "has": False})
                        d["tokens"] += int(used or 0)
                        c = _thread_cost(model, int(used or 0), rpath)
                        if c is not None:
                            d["cost"] += c
                            d["has"] = True
                    for model, d in _sess.items():
                        if model in openai_session_tokens_map and d["tokens"] > openai_session_tokens_map[model]:
                            openai_session_tokens_map[model] = d["tokens"]
                            openai_session_from_threads.add(model)
                            if d["has"]:
                                openai_session_costs_map[model] = d["cost"]
                                openai_session_costs_has_val[model] = True
                conn.close()
            except Exception:
                pass

        # OpenAI 5H pair: sum of the chosen per-model pairs plus usage.db rows of no configured model.
        openai_h5_data = {"tokens": openai_h5_other["tokens"], "cost": openai_h5_other["cost"], "has_cost": openai_h5_other["has_cost"]}
        if codex_h5_ended:
            openai_h5_data = {"tokens": 0, "cost": 0.0, "has_cost": True}
        for _m in cfg["openai_models"]:
            _h = h5_models_data[_m]
            openai_h5_data["tokens"] += _h["tokens"]
            if _h["has_cost"]:
                openai_h5_data["cost"] += _h["cost"]
                openai_h5_data["has_cost"] = True

        # Unknown is not zero: a window whose source is absent is emitted as null, never 0.
        _state_path = expand_path(cfg.get("codex_state_db", "~/.codex/state_5.sqlite"))
        db_present = bool(db_path and os.path.exists(db_path))
        state_present = bool(_state_path and os.path.exists(_state_path))
        claude_win_known = db_present  # Claude windows come from usage.db only
        win_known = db_present or state_present
        claude_sess_known = bool(transcript_files)
        openai_sess_known = bool(args.session_start) and win_known

        def known_int(v, known):
            return int(v) if known else None

        # Build final models dict in strict order (claude first, then openai)
        models_dict = {}
        models_full = {}
        session_list_cost_sum = 0.0
        session_list_has_val = False

        all_conf_models = cfg.get("claude_models", []) + cfg.get("openai_models", [])
        subscriptions = cfg.get("subscriptions", {"claude": 100, "openai": 100})

        pace_all = {}
        for m in all_conf_models:
            prov = "claude" if m in cfg.get("claude_models", []) else "openai"
            label = model_label(m)

            if prov == "claude":
                sess_tok = session_tokens_map.get(m, 0)
                sess_nc = session_noncache_map.get(m, 0)
                sess_c = session_costs_map.get(m, None) if session_costs_has_val.get(m, False) else None
            else:
                sess_tok = openai_session_tokens_map.get(m, 0)
                # The Codex thread-total fallback (above) carries no cache split: leave the non-cache count unknown.
                sess_nc = None if m in openai_session_from_threads else openai_session_noncache_map.get(m, 0)
                sess_c = openai_session_costs_map.get(m, None) if openai_session_costs_has_val.get(m, False) else None

            d1_info = d1_models_data.get(m, {"tokens": 0, "cost": 0.0, "has_cost": False})
            d1_tok = d1_info["tokens"]
            d1_c = d1_info["cost"] if d1_info["has_cost"] else None
            d7_info = d7_models_data.get(m, {"tokens": 0, "cost": 0.0, "has_cost": False})
            d7_tok = d7_info["tokens"]
            d7_c = d7_info["cost"] if d7_info["has_cost"] else None
            d28_info = d28_models_data.get(m, {"tokens": 0, "cost": 0.0, "has_cost": False})
            if d28_info["tokens"] < d7_tok:
                d28_info = {"tokens": d7_tok, "cost": d7_info["cost"], "has_cost": d7_info["has_cost"]}
            all_info = all_models_data.get(m, {"tokens": 0, "cost": 0.0, "has_cost": False})
            # d28 can be raised from Codex thread totals (state db) that the usage db lacks;
            # all-time must never read below the 28-day window.
            if d28_info["tokens"] > all_info["tokens"]:
                all_info = dict(d28_info)
            all_tok = all_info["tokens"]
            all_c = all_info["cost"] if all_info["has_cost"] else None
            # Pace lifetime dollars: for OpenAI the thread totals priced by category replace the usage.db sum only when they are the larger source.
            pace_all_c = all_c
            _ta = thr_all.get(m)
            if _ta and _ta["has"] and _ta["tokens"] >= all_tok:
                pace_all_c = _ta["cost"]
            pace_all[m] = pace_all_c

            models_full[m] = {
                "label": label,
                "provider": prov,
                "session": {"tokens": known_int(sess_tok, claude_sess_known if prov == "claude" else openai_sess_known),
                            "tokens_noncache": sess_nc if (claude_sess_known if prov == "claude" else openai_sess_known) else None,
                            "cost": sess_c},
                "h5": {"tokens": known_int(h5_models_data.get(m, {}).get("tokens", 0), claude_win_known if prov == "claude" else win_known),
                       "cost": None},
                "d1": {"tokens": known_int(d1_tok, claude_win_known if prov == "claude" else win_known), "cost": d1_c},
                "d7": {"tokens": known_int(d7_tok, claude_win_known if prov == "claude" else win_known), "cost": d7_c},
                "d28": {"tokens": known_int(d28_info["tokens"], claude_win_known if prov == "claude" else win_known), "cost": d28_info["cost"] if d28_info["has_cost"] else None},
                "all": {"tokens": known_int(all_tok, claude_win_known if prov == "claude" else win_known), "cost": all_c}
            }

        for m in all_conf_models:
            _h5 = models_full[m]["h5"]
            _hd = h5_models_data.get(m, {"tokens": 0, "cost": 0.0, "has_cost": False})
            if _h5["tokens"] is not None:
                _h5["cost"] = _hd["cost"] if _hd["has_cost"] else (0.0 if _h5["tokens"] == 0 else None)
            models_full[m]["first_seen"] = first_by_id.get(m)
        _pace_table = {m: (first_by_id.get(m), models_full[m]["d28"]["cost"], pace_all.get(m)) for m in all_conf_models}
        for m in all_conf_models:
            models_full[m]["pace"] = compute_pace(m, _pace_table, now)

        # Rows: top 4 exact ids per provider by 28-day tokens, then ALL, then id; the current model outside the top 4 takes row 4.
        claude_rows = pick_rows([m for m in cfg["claude_models"] if m in row_claude], {m: models_full[m]["all"]["tokens"] for m in cfg["claude_models"]}, claude_pin,
                                recent_tokens={m: models_full[m]["d28"]["tokens"] for m in cfg["claude_models"]})
        openai_rows = pick_rows(cfg["openai_models"], {m: models_full[m]["all"]["tokens"] for m in cfg["openai_models"]}, openai_pin,
                                recent_tokens={m: models_full[m]["d28"]["tokens"] for m in cfg["openai_models"]})
        for m in claude_rows + openai_rows:
            models_dict[m] = models_full[m]
        for m in claude_rows:
            sc = models_full[m]["session"]["cost"]
            if sc is not None:
                session_list_cost_sum += sc
                session_list_has_val = True

        session_list_cost = session_list_cost_sum if session_list_has_val else None

        # Sub ratios & blended costs
        claude_sub = subscriptions.get("claude", 100)
        openai_sub = subscriptions.get("openai", 100)
        
        claude_sub_proportional = claude_sub * (7.0 / 30.0)
        openai_sub_proportional = openai_sub * (7.0 / 30.0)

        claude_sub_ratio = (claude_d7_cost / claude_sub_proportional) if (claude_d7_has_cost and claude_sub_proportional > 0) else None
        openai_d7_cost = sum(v["cost"] for m, v in d7_models_data.items() if m in cfg["openai_models"] and v["has_cost"])
        openai_d7_has_cost = any(v["has_cost"] for m, v in d7_models_data.items() if m in cfg["openai_models"])
        openai_sub_ratio = (openai_d7_cost / openai_sub_proportional) if (openai_d7_has_cost and openai_sub_proportional > 0) else None

        blended_claude = (claude_d7_cost / (claude_d7_tokens / 1_000_000.0)) if (claude_d7_has_cost and claude_d7_tokens > 0) else None
        blended_openai = None

        # Some bridge rows use an unrecognized backend while retaining the full
        # model id. Keep the aggregate at least as large as its visible buckets.
        visible_openai_tokens = sum(
            d7_models_data[m]["tokens"] for m in cfg.get("openai_models", [])
        )
        openai_total_d7_tokens = max(openai_total_d7_tokens, visible_openai_tokens)

        # Provider-wide windows (Sigma/$ rows). Never d28 < d7, never all < d28.
        _cl_d7_tok = int(claude_d7_tokens)
        _cl_d28_tok = max(int(claude_d28_tok), _cl_d7_tok)
        _cl_d28_cost = claude_d28_cost if claude_d28_has_cost else None
        if _cl_d28_tok == _cl_d7_tok and int(claude_d28_tok) < _cl_d7_tok:
            _cl_d28_cost = claude_d7_cost if claude_d7_has_cost else None
        _cl_all_tok = max(int(claude_all_tok), _cl_d28_tok)
        _cl_all_cost = claude_all_cost if claude_all_has_cost else None
        if _cl_all_tok > int(claude_all_tok):
            _cl_all_cost = _cl_d28_cost
        _op_d7_tok = int(openai_total_d7_tokens)
        _op_d28_tok = max(int(openai_d28_tok), _op_d7_tok)
        _op_d28_cost = openai_d28_cost if openai_d28_has_cost else None
        _op_all_tok = max(int(openai_all_tok), _op_d28_tok)
        _op_all_cost = openai_all_cost if openai_all_has_cost else None
        if _op_all_tok > int(openai_all_tok):
            _op_all_cost = _op_d28_cost
        provider_windows = {
            "claude": {
                "h5": {"tokens": int(claude_h5_data["tokens"]), "cost": claude_h5_data["cost"] if claude_h5_data["has_cost"] else None},
                "d1": {"tokens": int(provider_today["claude"]["tokens"]), "cost": provider_today["claude"]["cost"] if provider_today["claude"]["has_cost"] else None},
                "d7": {"tokens": _cl_d7_tok, "cost": claude_d7_cost if claude_d7_has_cost else None},
                "d28": {"tokens": _cl_d28_tok, "cost": _cl_d28_cost},
                "all": {"tokens": _cl_all_tok, "cost": _cl_all_cost},
            },
            "openai": {
                "h5": {"tokens": int(openai_h5_data["tokens"]), "cost": openai_h5_data["cost"] if openai_h5_data["has_cost"] else None},
                "d1": {"tokens": int(provider_today["openai"]["tokens"]), "cost": provider_today["openai"]["cost"] if provider_today["openai"]["has_cost"] else None},
                # d7 cost: no provider-wide d7 openai cost accumulator exists; null (not computable here).
                "d7": {"tokens": _op_d7_tok, "cost": None},
                "d28": {"tokens": _op_d28_tok, "cost": _op_d28_cost},
                "all": {"tokens": _op_all_tok, "cost": _op_all_cost},
            },
            "free": {
                # No free-model 5h source exists in usage.db queries; null by design.
                "h5": {"tokens": None, "cost": None},
                "d1": {"tokens": free_windows["today"]["tokens"], "cost": free_windows["today"]["equiv_cost"]},
                "d7": {"tokens": free_windows["d7"]["tokens"], "cost": free_windows["d7"]["equiv_cost"]},
                "d28": {"tokens": free_windows["d28"]["tokens"], "cost": free_windows["d28"]["equiv_cost"]},
                "all": {"tokens": int(free_all_tok), "cost": free_all_cost if free_all_tok > 0 else None},
            },
        }
        _fw = provider_windows["free"]
        if _fw["all"]["tokens"] < (_fw["d28"]["tokens"] or 0):
            _fw["all"] = dict(_fw["d28"])

        _ft = {r["_fid"]: (first_by_id.get(r["_fid"]), r["d28"]["equiv_cost"], r["all"]["equiv_cost"]) for r in free_top4_d7 if r.get("_fid")}
        for r in free_top4_d7:
            _fid = r.pop("_fid", None)
            r["first_seen"] = first_by_id.get(_fid) if _fid else None
            r["pace"] = compute_pace(_fid, _ft, now) if _fid else null_pace()

        output = {
            "schema": 1,
            "session_id": args.session_id,
            "generated_at": now,
            "openai_gaps": openai_gaps,
            "gap_logged": gap_logged,
            "codex": codex_res,
            "models": models_dict,
            "model_pins": {"claude": claude_pin, "openai": openai_pin},
            "openai_total_d7": {
                "tokens": int(openai_total_d7_tokens),
                "requests": int(openai_total_d7_requests)
            },
            "claude_d7": {
                "tokens": int(claude_d7_tokens),
                "cost": claude_d7_cost if claude_d7_has_cost else None
            },
            "claude_today": {
                "tokens": int(provider_today["claude"]["tokens"]),
                "cost": provider_today["claude"]["cost"] if provider_today["claude"]["has_cost"] else None
            },
            "openai_today": {
                "tokens": int(provider_today["openai"]["tokens"]),
                "cost": provider_today["openai"]["cost"] if provider_today["openai"]["has_cost"] else None
            },
            "claude_h5": {
                "tokens": int(claude_h5_data["tokens"]),
                "cost": claude_h5_data["cost"] if claude_h5_data["has_cost"] else None
            },
            "openai_h5": {
                "tokens": int(openai_h5_data["tokens"]),
                "cost": openai_h5_data["cost"] if openai_h5_data["has_cost"] else None
            },
            "free_top4_d7": free_top4_d7,
            "cum_use": {
                "tokens": int(cum_other["tokens"] + cum_openai_db["tokens"]),
                "cost": (cum_other["cost"] + cum_openai_db["cost"]) if (cum_other["tokens"] + cum_openai_db["tokens"]) > 0 else None
            },
            "claude_all": {
                "tokens": int(claude_all_tok),
                "cost": claude_all_cost if claude_all_has_cost else None
            },
            "openai_all": {
                "tokens": int(openai_all_tok),
                "cost": openai_all_cost if openai_all_has_cost else None
            },
            "free_all": {
                "tokens": int(free_all_tok),
                "equiv_cost": free_all_cost if free_all_tok > 0 else None
            },
            "history_days": {k: (max(0.0, (now - v) / 86400.0) if v else None) for k, v in first_ts.items()},
            "free_windows": free_windows,
            "provider_windows": provider_windows,
            "cache_pct": {
                "claude": (round(100.0 * sess_cache["read"] / sess_cache["total"], 1) if sess_cache["total"] > 0 else cache_pct["claude"]),
                "openai": cache_pct["openai"],
            },
            "session_list_cost": session_list_cost,
            "sub_ratio_d7": {
                "claude": claude_sub_ratio,
            "openai": openai_sub_ratio
            },
            "blended_usd_per_mtok_d7": {
                "claude": blended_claude,
                "openai": None
            }
        }

        # Write output safely
        if out_path:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=2, sort_keys=False)
            except Exception:
                pass

        # Print to stdout
        print(json.dumps(output))
        sys.exit(0)

    except Exception:
        # Fallback safe output on ANY error
        try:
            fallback = empty_result()
            args_list = sys.argv
            for i, arg in enumerate(args_list):
                if arg == "--session-id" and i + 1 < len(args_list):
                    fallback["session_id"] = args_list[i+1]
            out_path = expand_path("~/.claude/statusline-domi-cache.json")
            for i, arg in enumerate(args_list):
                if arg == "--out" and i + 1 < len(args_list):
                    out_path = expand_path(args_list[i+1])
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(fallback, f, indent=2, sort_keys=False)
            # Print to stdout
            print(json.dumps(fallback))
        except Exception:
            pass
        sys.exit(0)

if __name__ == "__main__":
    main()
