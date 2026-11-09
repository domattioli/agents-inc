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
    "openai_models": ["gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-luna"],
    "subscriptions": {"claude": 100, "openai": 100},
    "prices_json": ["~/Projects/agents_for_dummies/skills/codex-bridge/reference/prices.json"],
    "openai_price_estimates": {"gpt-6-astra": "claude-fable-5-1", "gpt-5.6-sol": "claude-opus-5", "gpt-5.6-terra": "claude-sonnet-5", "gpt-5.6-luna": "claude-haiku-4-5", "gpt-6.1-sol": "claude-opus-5", "gpt-6.1-terra": "claude-sonnet-5", "gpt-6-luna": "claude-haiku-4-5"},
    "free_price_estimate": "claude-haiku-4-5",
    "cum_default_estimate": "claude-sonnet-5",
    "usage_db": "~/.codex-bridge/usage.db",
    "codex_state_db": "",
    "codex_config_toml": "~/.codex/config.toml",
    "codex_sessions_glob": "~/.codex/sessions/**/*.jsonl",
    "cache_path": "~/.claude/statusline-domi-cache.json",
    "cache_ttl_s": 60
}

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
            "d1": {"tokens": None, "cost": None},
            "d7": {"tokens": None, "cost": None},
            "d28": {"tokens": None, "cost": None},
            "all": {"tokens": None, "cost": None}
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

def normalize_model(model_id):
    """Exact version id: only a trailing 8-digit date suffix is dropped. Versions are never merged."""
    return strip_model_version(model_id)

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

def pick_rows(candidates, all_tokens, pin, n=4):
    """Top n ids by ALL tokens (ties: id order). A pin outside the top n replaces row n."""
    ranked = sorted(candidates, key=lambda m: (-(all_tokens.get(m) or 0), m))
    top = ranked[:n]
    if pin and pin in candidates and pin not in top:
        top = top[:n - 1] + [pin]
    return top

def calculate_cost(model_id, usage_dict, prices):
    base_id = strip_model_version(model_id)
    pinfo = prices.get(model_id) or prices.get(base_id)
    if not pinfo:
        return None
    try:
        i = usage_dict.get("input_tokens", 0) or 0
        o = usage_dict.get("output_tokens", 0) or 0
        cr = usage_dict.get("cache_read_input_tokens", usage_dict.get("cache_read", 0)) or 0
        cw = usage_dict.get("cache_creation_input_tokens", usage_dict.get("cache_write", 0)) or 0
        
        cost_i = (i / 1_000_000.0) * float(pinfo.get("input", 0))
        cost_o = (o / 1_000_000.0) * float(pinfo.get("output", 0))
        cost_cr = (cr / 1_000_000.0) * float(pinfo.get("cache_read", 0))
        cost_cw = (cw / 1_000_000.0) * float(pinfo.get("cache_write", 0))
        return cost_i + cost_o + cost_cr + cost_cw
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

def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--session-id", default="")
        parser.add_argument("--transcript", default="")
        parser.add_argument("--session-start", type=int, default=0)
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

        # Prices
        price_candidates = []
        if args.prices:
            price_candidates.append(args.prices)
        if isinstance(cfg.get("prices_json"), list):
            price_candidates.extend(cfg["prices_json"])
        elif isinstance(cfg.get("prices_json"), str):
            price_candidates.append(cfg["prices_json"])
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
            price = prices.get(model_id) or (prices.get(estimates.get(model_id)) if isinstance(estimates, dict) and estimates.get(model_id) else None)
            if not price or price.get("input") is None:
                price = prices.get(cum_default)
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

        # Row discovery: every exact model id seen per provider is a candidate; the top 4 by ALL-time tokens
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
        for _m in DEFAULT_CONFIG["claude_models"]:
            if len(cand_claude) >= 4:
                break
            cand_claude.add(_m)
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
        h5_models_data = {m: {"tokens": 0, "cost": 0.0, "has_cost": False} for m in cfg["claude_models"] + cfg["openai_models"]}
        claude_h5_resets_at = int(args.claude_h5_resets_at) if args.claude_h5_resets_at else 0
        claude_h5_window_start = claude_h5_resets_at - 5 * 3600 if claude_h5_resets_at > 0 else 0
        codex_h5_resets_at = codex_res["h5"]["resets_at"] if codex_res["h5"]["resets_at"] else 0
        codex_h5_window_start = codex_h5_resets_at - 5 * 3600 if codex_h5_resets_at > 0 else 0

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
                    # Extra windows so the FREE table matches the ANT/OAI layout (SESS 5H 1D 7D 30D ALL).
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
                    free_top4_d7.append({
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
                            openai_h5_data["tokens"] += tot
                            if base_m in h5_models_data:
                                h5_models_data[base_m]["tokens"] += tot
                            c = calculate_cost(base_m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices)
                            if c is None and base_m in cfg["openai_models"]:
                                c = calculate_estimated_cost(base_m, {"input_tokens": i, "output_tokens": o, "cache_read": cr, "cache_write": cw}, prices, estimates)
                            if c is not None:
                                openai_h5_data["cost"] += c
                                openai_h5_data["has_cost"] = True
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
                cur.execute("""
                    SELECT model, SUM(tokens_used), COUNT(*) FROM threads
                    WHERE updated_at >= ? AND tokens_used > 0 GROUP BY model
                """, (now - 7 * 24 * 60 * 60,))
                for raw_model, tokens, thread_count in cur.fetchall():
                    model = normalize_model(raw_model)
                    if model in d7_models_data and int(tokens or 0) > d7_models_data[model]["tokens"]:
                        openai_total_d7_tokens += int(tokens or 0) - d7_models_data[model]["tokens"]
                        d7_models_data[model]["tokens"] = int(tokens or 0)
                        openai_total_d7_requests += int(thread_count or 0)
                        price = prices.get(model) or (prices.get(estimates.get(model)) if isinstance(estimates, dict) and estimates.get(model) else None)
                        if price and price.get("input") is not None:
                            d7_models_data[model]["cost"] = (int(tokens or 0) / 1_000_000.0) * float(price["input"])
                            d7_models_data[model]["has_cost"] = True
                # 5H: threads touched inside the Codex 5h window (whole-thread total, estimated).
                if codex_h5_window_start > 0:
                    cur.execute("""
                        SELECT model, SUM(tokens_used) FROM threads
                        WHERE updated_at >= ? AND tokens_used > 0 GROUP BY model
                    """, (int(codex_h5_window_start),))
                    for raw_model, tokens in cur.fetchall():
                        model = normalize_model(raw_model)
                        if model in h5_models_data and int(tokens or 0) > h5_models_data[model]["tokens"]:
                            h5_models_data[model]["tokens"] = int(tokens or 0)
                # 1D: threads touched since local midnight (whole-thread total, estimated).
                _mid = int(time.mktime(datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timetuple()))
                cur.execute("""
                    SELECT model, SUM(tokens_used) FROM threads
                    WHERE updated_at >= ? AND tokens_used > 0 GROUP BY model
                """, (_mid,))
                for raw_model, tokens in cur.fetchall():
                    model = normalize_model(raw_model)
                    if model in d1_models_data and int(tokens or 0) > d1_models_data[model]["tokens"]:
                        d1_models_data[model]["tokens"] = int(tokens or 0)
                        price = prices.get(model) or (prices.get(estimates.get(model)) if isinstance(estimates, dict) and estimates.get(model) else None)
                        if price and price.get("input") is not None:
                            d1_models_data[model]["cost"] = (int(tokens or 0) / 1_000_000.0) * float(price["input"])
                            d1_models_data[model]["has_cost"] = True
                cur.execute("""
                    SELECT model, SUM(tokens_used) FROM threads
                    WHERE updated_at >= ? AND tokens_used > 0 GROUP BY model
                """, (now - 28 * 24 * 60 * 60,))
                for raw_model, tokens in cur.fetchall():
                    model = normalize_model(raw_model)
                    if model in d28_models_data and int(tokens or 0) > d28_models_data[model]["tokens"]:
                        # Mirror the d7 thread-db adjustment for the provider-wide d28.
                        openai_d28_tok += int(tokens or 0) - d28_models_data[model]["tokens"]
                        d28_models_data[model]["tokens"] = int(tokens or 0)
                        price = prices.get(model) or (prices.get(estimates.get(model)) if isinstance(estimates, dict) and estimates.get(model) else None)
                        if price and price.get("input") is not None:
                            d28_models_data[model]["cost"] = (int(tokens or 0) / 1_000_000.0) * float(price["input"])
                            d28_models_data[model]["has_cost"] = True
                cur.execute("SELECT model, SUM(tokens_used) FROM threads WHERE tokens_used > 0 GROUP BY model")
                state_all = {"tokens": 0, "cost": 0.0}
                for raw_model, tokens in cur.fetchall():
                    model = normalize_model(raw_model)
                    ip = tiered_input_price(model)
                    state_all["tokens"] += int(tokens or 0)
                    state_all["cost"] += (int(tokens or 0) / 1_000_000.0) * ip if ip is not None else 0.0
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
                        SELECT model, SUM(tokens_used) FROM threads
                        WHERE created_at >= ? AND tokens_used > 0 GROUP BY model
                    """, (args.session_start,))
                    for raw_model, tokens in cur.fetchall():
                        model = normalize_model(raw_model)
                        if model in openai_session_tokens_map and int(tokens or 0) > openai_session_tokens_map[model]:
                            openai_session_tokens_map[model] = int(tokens or 0)
                            openai_session_from_threads.add(model)
                            price = prices.get(model) or (prices.get(estimates.get(model)) if isinstance(estimates, dict) and estimates.get(model) else None)
                            if price and price.get("input") is not None:
                                openai_session_costs_map[model] = (int(tokens or 0) / 1_000_000.0) * float(price["input"])
                                openai_session_costs_has_val[model] = True
                conn.close()
            except Exception:
                pass

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

            models_full[m] = {
                "label": label,
                "provider": prov,
                "session": {"tokens": known_int(sess_tok, claude_sess_known if prov == "claude" else openai_sess_known),
                            "tokens_noncache": sess_nc if (claude_sess_known if prov == "claude" else openai_sess_known) else None,
                            "cost": sess_c},
                "h5": {"tokens": known_int(h5_models_data.get(m, {}).get("tokens", 0), claude_win_known if prov == "claude" else win_known)},
                "d1": {"tokens": known_int(d1_tok, claude_win_known if prov == "claude" else win_known), "cost": d1_c},
                "d7": {"tokens": known_int(d7_tok, claude_win_known if prov == "claude" else win_known), "cost": d7_c},
                "d28": {"tokens": known_int(d28_info["tokens"], claude_win_known if prov == "claude" else win_known), "cost": d28_info["cost"] if d28_info["has_cost"] else None},
                "all": {"tokens": known_int(all_tok, claude_win_known if prov == "claude" else win_known), "cost": all_c}
            }

        # Rows: top 4 exact ids per provider by ALL-time tokens; the current model outside the top 4 takes row 4.
        claude_rows = pick_rows(cfg["claude_models"], {m: models_full[m]["all"]["tokens"] for m in cfg["claude_models"]}, claude_pin)
        openai_rows = pick_rows(cfg["openai_models"], {m: models_full[m]["all"]["tokens"] for m in cfg["openai_models"]}, openai_pin)
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

        output = {
            "schema": 1,
            "session_id": args.session_id,
            "generated_at": now,
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
