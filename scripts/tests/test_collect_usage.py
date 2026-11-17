import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
COLLECTOR = REPO_ROOT / "scripts" / "statusline.d" / "collect_usage.py"
FIXTURES = REPO_ROOT / "scripts" / "tests" / "fixtures"


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def run_collector(args, env=None):
    cmd = [sys.executable, str(COLLECTOR)] + args
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(cmd, capture_output=True, text=True, env=merged_env)
    return result


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def usage_db(temp_dir):
    db_path = temp_dir / "usage.db"
    sql = (FIXTURES / "usage_fixture.sql").read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def prices_file(temp_dir):
    p = temp_dir / "prices.json"
    p.write_text((FIXTURES / "prices_fixture.json").read_text())
    return p


@pytest.fixture
def codex_dir(temp_dir):
    codex_root = temp_dir / "codex" / "sessions" / "a" / "b" / "c"
    codex_root.mkdir(parents=True)
    rollout = codex_root / "rollout.jsonl"
    rollout.write_text((FIXTURES / "codex_rollout.jsonl").read_text())
    # Create 2 older files to test "3 newest by mtime"
    for i in range(2):
        old = codex_root / f"old_{i}.jsonl"
        old.write_text('{"timestamp":"2026-09-05T22:00:00.000Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{}}}\n')
        time.sleep(0.01)
    return temp_dir / "codex"


@pytest.fixture
def transcript_file(temp_dir):
    t = temp_dir / "transcript.jsonl"
    t.write_text((FIXTURES / "transcript_fixture.jsonl").read_text())
    return t


@pytest.fixture
def config_file(temp_dir, usage_db, prices_file, codex_dir):
    cfg = {
        "codex_config_toml": "",
        "openai_price_estimates": {"gpt-5.6-sol": "claude-opus-5"},
        "subscriptions": {"claude": 100, "openai": 100},
        "prices_json": [str(prices_file)],
        "usage_db": str(usage_db),
        "codex_sessions_glob": str(codex_dir / "**" / "*.jsonl"),
        "cache_path": str(temp_dir / "cache.json"),
        "cache_ttl_s": 60,
    }
    cfg_path = temp_dir / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    return cfg_path


def test_collector_happy_path(temp_dir, config_file, transcript_file, usage_db, prices_file, codex_dir):
    cache_path = temp_dir / "cache.json"
    session_id = "test-session-123"
    session_start = 1788600000
    now = 1788651000  # 2026-09-05T23:30:00Z

    args = [
        "--session-id", session_id,
        "--transcript", str(transcript_file),
        "--session-start", str(session_start),
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", str(now),
        "--codex-glob", str(codex_dir / "**" / "*.jsonl"),
        "--usage-db", str(usage_db),
        "--prices", str(prices_file),
        "--force",
    ]

    result = run_collector(args)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out = json.loads(result.stdout)
    assert out["schema"] == 1
    assert out["session_id"] == session_id
    assert out["generated_at"] == now

    # codex assertions
    assert out["codex"]["h5"]["used_pct"] == 87.0
    assert out["codex"]["h5"]["resets_at"] == 1788669699
    assert out["codex"]["d7"]["used_pct"] == 29.0
    assert out["codex"]["d7"]["resets_at"] == 1789238480
    assert out["codex"]["observed_at"] == 1788651000

    # models assertions
    models = out["models"]
    # claude-fable-5-1: 2 unique messages (msg_a deduplicated), each 100+50+1000+200 = 1350 tokens
    fab = models["claude-fable-5-1"]
    assert fab["label"] == "Fable 5.1"
    assert fab["provider"] == "claude"
    assert fab["session"]["tokens"] == 2700  # 2 * 1350
    assert fab["session"]["tokens_noncache"] == 700  # 2 * (100 + 50 + 200): cache reads excluded
    expected_fab_cost = 2 * (100*10 + 50*50 + 1000*0.25 + 200*12.5) / 1_000_000
    assert abs(fab["session"]["cost"] - expected_fab_cost) < 1e-9

    # haiku: strip -20251001 suffix, lookup claude-haiku-4-5
    hai = models["claude-haiku-4-5"]
    assert hai["label"] == "Haiku 4.5"
    assert hai["provider"] == "claude"
    assert hai["session"]["tokens"] == 15  # 10+5+0+0
    assert hai["session"]["tokens_noncache"] == 15
    expected_hai_cost = (10*1 + 5*5) / 1_000_000
    assert abs(hai["session"]["cost"] - expected_hai_cost) < 1e-9

    # OpenAI estimate maps SOL to the Opus ladder at runtime.
    sol = models["gpt-5.6-sol"]
    assert sol["d7"]["tokens"] == 2500
    assert sol["d7"]["cost"] == pytest.approx((2000*5 + 500*25) / 1_000_000)

    # openai_total_d7 includes codex rows (gpt-5.6-sol 2500 + NULL model 3000 = 5500)
    assert out["openai_total_d7"]["tokens"] == 5500
    assert out["openai_total_d7"]["requests"] == 2  # two codex rows in 7d window

    # free_top4_d7 ranks by all-time tokens: old 2020 gemini-old 999999 (7D 0), nemotron 9000, codestral 7000,
    # gemini-3.8-flash 5000; ministral (10) drops out
    free_top4 = out["free_top4_d7"]
    assert [e["model"] for e in free_top4] == ["gemini-old", "nvidia/nemotron-3-ultra-550b-a55b:free", "codestral-latest", "gemini-3.8-flash"]
    assert free_top4[0]["all"]["tokens"] == 999999
    assert free_top4[0]["tokens"] == 0 and free_top4[0]["d7"]["tokens"] == 0 and free_top4[0]["session"]["tokens"] == 0
    assert {k: v for k, v in free_top4[1].items() if k not in ("first_seen", "pace")} == {
        "backend": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free", "tokens": 9000,
        "session": {"tokens": 9000, "cost": None, "equiv_cost": pytest.approx(0.009)}, "d7": {"tokens": 9000, "cost": None, "equiv_cost": pytest.approx(0.009)},
        "h5": {"tokens": 9000, "equiv_cost": pytest.approx(0.009)}, "d1": {"tokens": 9000, "equiv_cost": pytest.approx(0.009)},
        "d28": {"tokens": 9000, "equiv_cost": pytest.approx(0.009)}, "all": {"tokens": 9000, "equiv_cost": pytest.approx(0.009)},
    }
    assert {k: v for k, v in free_top4[2].items() if k not in ("first_seen", "pace")} == {
        "backend": "mistral", "model": "codestral-latest", "tokens": 7000,
        "session": {"tokens": 7000, "cost": None, "equiv_cost": pytest.approx(0.007)}, "d7": {"tokens": 7000, "cost": None, "equiv_cost": pytest.approx(0.007)},
        "h5": {"tokens": 7000, "equiv_cost": pytest.approx(0.007)}, "d1": {"tokens": 7000, "equiv_cost": pytest.approx(0.007)},
        "d28": {"tokens": 7000, "equiv_cost": pytest.approx(0.007)}, "all": {"tokens": 7000, "equiv_cost": pytest.approx(0.007)},
    }
    assert {k: v for k, v in free_top4[3].items() if k not in ("first_seen", "pace")} == {
        "backend": "gemini", "model": "gemini-3.8-flash", "tokens": 5000,
        "session": {"tokens": 5000, "cost": None, "equiv_cost": pytest.approx(0.005)}, "d7": {"tokens": 5000, "cost": None, "equiv_cost": pytest.approx(0.005)},
        "h5": {"tokens": 5000, "equiv_cost": pytest.approx(0.005)}, "d1": {"tokens": 5000, "equiv_cost": pytest.approx(0.005)},
        "d28": {"tokens": 5000, "equiv_cost": pytest.approx(0.005)}, "all": {"tokens": 5000, "equiv_cost": pytest.approx(0.005)},
    }

    # free_windows: all 3 fixture rows are inside the 28d window; old 2020 row excluded
    assert out["free_windows"]["d28"]["tokens"] == 21010
    assert set(out["free_windows"]) == {"session", "today", "d7", "d28"}

    # All schema keys present
    required_keys = {
        "schema", "session_id", "generated_at", "codex", "models",
        "model_pins", "openai_total_d7", "claude_d7", "claude_today", "openai_today", "claude_h5", "openai_h5", "free_top4_d7", "cum_use",
        "claude_all", "openai_all", "free_all", "history_days", "free_windows", "provider_windows", "cache_pct",
        "session_list_cost", "sub_ratio_d7", "blended_usd_per_mtok_d7", "openai_gaps", "gap_logged"
    }
    assert set(out.keys()) == required_keys
    assert set(out["codex"].keys()) == {"h5", "d7", "observed_at"}
    for window in ("h5", "d7"):
        assert set(out["codex"][window].keys()) == {"used_pct", "resets_at"}
    for model_info in out["models"].values():
        assert set(model_info.keys()) == {"label", "provider", "session", "h5", "d1", "d7", "d28", "all", "first_seen", "pace"}
        assert set(model_info["session"].keys()) == {"tokens", "tokens_noncache", "cost"}
        assert set(model_info["d7"].keys()) == {"tokens", "cost"}
        assert set(model_info["d28"].keys()) == {"tokens", "cost"}
        assert model_info["d28"]["tokens"] >= model_info["d7"]["tokens"]
    # d28 ("Mo") window: sonnet has 1M in 7d plus 500k twenty days ago.
    son = out["models"]["claude-sonnet-5"]
    assert son["d7"]["tokens"] == 1000000
    assert son["d28"]["tokens"] == 1500000
    assert son["d28"]["cost"] == pytest.approx(4.5)
    # cum_use: every row ever, Anthropic-API-equivalent pricing (free -> haiku, null codex -> sonnet).
    assert set(out["cum_use"].keys()) == {"tokens", "cost"}
    assert out["cum_use"]["tokens"] == 2526659
    assert out["cum_use"]["cost"] == pytest.approx(5.552859, abs=1e-4)
    assert out["claude_today"] == {"tokens": 1000150, "cost": pytest.approx(3.00035)}
    assert out["openai_today"] == {"tokens": 5500, "cost": pytest.approx(0.0225)}
    # claude_all/openai_all/free_all: same provider classification and cost
    # model as today/h5 blocks, no time filter (all-time totals).
    assert set(out["claude_all"].keys()) == {"tokens", "cost"}
    assert out["claude_all"]["tokens"] == 1500150
    assert out["claude_all"]["cost"] == pytest.approx(4.50035)
    assert set(out["openai_all"].keys()) == {"tokens", "cost"}
    assert out["openai_all"]["tokens"] == 5500
    assert out["openai_all"]["cost"] == pytest.approx(0.0225)
    assert set(out["free_all"].keys()) == {"tokens", "equiv_cost"}
    assert out["free_all"]["tokens"] == 1021009
    assert out["free_all"]["equiv_cost"] == pytest.approx(1.021009, abs=1e-4)
    # claude_all + openai_all + free_all tokens must equal cum_use tokens.
    assert (out["claude_all"]["tokens"] + out["openai_all"]["tokens"]
            + out["free_all"]["tokens"]) == out["cum_use"]["tokens"]
    assert set(out["openai_total_d7"].keys()) == {"tokens", "requests"}
    # provider_windows: provider totals; reuses the claude accumulators, d28 is new.
    pw = out["provider_windows"]
    assert set(pw.keys()) == {"claude", "openai", "free"}
    for prov in pw.values():
        assert set(prov.keys()) == {"h5", "d1", "d7", "d28", "all"}
        for cell in prov.values():
            assert set(cell.keys()) == {"tokens", "cost"}
        assert prov["d28"]["tokens"] >= prov["d7"]["tokens"]
        assert prov["all"]["tokens"] >= prov["d28"]["tokens"]
    assert pw["claude"]["h5"]["tokens"] == out["claude_h5"]["tokens"]
    assert pw["claude"]["d1"]["tokens"] == out["claude_today"]["tokens"]
    assert pw["claude"]["d7"]["tokens"] == out["claude_d7"]["tokens"]
    assert pw["claude"]["d7"]["cost"] == out["claude_d7"]["cost"]
    assert pw["claude"]["all"]["tokens"] == out["claude_all"]["tokens"]
    assert pw["openai"]["d7"]["tokens"] == out["openai_total_d7"]["tokens"]
    assert pw["openai"]["all"]["tokens"] == out["openai_all"]["tokens"]
    assert pw["free"]["d28"]["tokens"] == out["free_windows"]["d28"]["tokens"]
    assert pw["free"]["h5"]["tokens"] is None
    assert set(out["claude_d7"].keys()) == {"tokens", "cost"}
    assert set(out["claude_today"].keys()) == {"tokens", "cost"}
    assert set(out["openai_today"].keys()) == {"tokens", "cost"}
    assert set(out["sub_ratio_d7"].keys()) == {"claude", "openai"}
    assert set(out["blended_usd_per_mtok_d7"].keys()) == {"claude", "openai"}


def test_missing_usage_db_exits_zero(temp_dir, config_file, transcript_file, prices_file, codex_dir):
    cache_path = temp_dir / "cache.json"
    missing_db = temp_dir / "missing.db"

    args = [
        "--session-id", "test",
        "--transcript", str(transcript_file),
        "--session-start", "1788600000",
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", "1788651000",
        "--codex-glob", str(codex_dir / "**" / "*.jsonl"),
        "--usage-db", str(missing_db),
        "--prices", str(prices_file),
        "--force",
    ]

    result = run_collector(args)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["free_top4_d7"] == []


def test_ttl_cache_skips_recollect(temp_dir, config_file, transcript_file, usage_db, prices_file, codex_dir):
    cache_path = temp_dir / "cache.json"
    session_id = "ttl-test"
    session_start = 1788600000
    now = 1788651000

    args = [
        "--session-id", session_id,
        "--transcript", str(transcript_file),
        "--session-start", str(session_start),
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", str(now),
        "--codex-glob", str(codex_dir / "**" / "*.jsonl"),
        "--usage-db", str(usage_db),
        "--prices", str(prices_file),
        "--force",
    ]

    # First run
    result1 = run_collector(args)
    assert result1.returncode == 0
    mtime1 = cache_path.stat().st_mtime

    # Second run immediately (within TTL, no --force)
    args_no_force = [a for a in args if a != "--force"]
    result2 = run_collector(args_no_force)
    assert result2.returncode == 0
    mtime2 = cache_path.stat().st_mtime

    # mtime should not have changed (collector skipped)
    assert mtime2 == mtime1, "Cache file mtime changed; collector did not respect TTL"


def test_premium_only_rollout_codex_none(temp_dir, config_file, transcript_file, usage_db, prices_file):
    # Create codex dir with only premium limit_id
    codex_root = temp_dir / "codex_premium" / "sessions" / "a" / "b" / "c"
    codex_root.mkdir(parents=True)
    rollout = codex_root / "rollout.jsonl"
    rollout.write_text('{"timestamp":"2026-09-05T23:30:00.000Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"limit_id":"premium","primary":null,"secondary":null}}}\n')

    cache_path = temp_dir / "cache.json"
    session_id = "premium-test"
    session_start = 1788600000
    now = 1788651000

    args = [
        "--session-id", session_id,
        "--transcript", str(transcript_file),
        "--session-start", str(session_start),
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", str(now),
        "--codex-glob", str(codex_root / "**" / "*.jsonl"),
        "--usage-db", str(usage_db),
        "--prices", str(prices_file),
        "--force",
    ]

    result = run_collector(args)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["codex"]["h5"]["used_pct"] is None
    assert out["codex"]["d7"]["used_pct"] is None
    assert out["codex"]["observed_at"] is None


def test_model_version_normalization_d7(temp_dir, config_file, transcript_file, usage_db, prices_file, codex_dir):
    # Test that model id with -YYYYMMDD suffix is normalized before d7 aggregation
    cache_path = temp_dir / "cache.json"
    session_id = "version-norm-test"
    session_start = 1788600000
    now = 1788651000

    args = [
        "--session-id", session_id,
        "--transcript", str(transcript_file),
        "--session-start", str(session_start),
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", str(now),
        "--codex-glob", str(codex_dir / "**" / "*.jsonl"),
        "--usage-db", str(usage_db),
        "--prices", str(prices_file),
        "--force",
    ]

    result = run_collector(args)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out = json.loads(result.stdout)
    models = out["models"]

    # claude-haiku-4-5 should include d7 tokens from the versioned row (claude-haiku-4-5-20251001: 100+50+0+0=150)
    hai = models["claude-haiku-4-5"]
    assert hai["d7"]["tokens"] == 150, f"Expected 150 tokens for claude-haiku-4-5 d7, got {hai['d7']['tokens']}"
    # cost should be numeric (not null)
    assert hai["d7"]["cost"] is not None, f"Expected numeric cost for claude-haiku-4-5 d7, got {hai['d7']['cost']}"
    assert isinstance(hai["d7"]["cost"], (int, float)), f"Expected numeric cost, got {type(hai['d7']['cost'])}"


def test_free_top4_session_and_d7_fields(temp_dir, config_file, transcript_file, usage_db, prices_file, codex_dir):
    """free_top4_d7 entries carry session/d7 token+cost blocks (T4)."""
    cache_path = temp_dir / "cache.json"
    args = [
        "--session-id", "free-fields",
        "--transcript", str(transcript_file),
        # Session window starts well after the fixture's older rows but before the -1h rows.
        "--session-start", "1788600000",
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", "1788651000",
        "--codex-glob", str(codex_dir / "**" / "*.jsonl"),
        "--usage-db", str(usage_db),
        "--prices", str(prices_file),
        "--force",
    ]
    result = run_collector(args)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = json.loads(result.stdout)

    for entry in out["free_top4_d7"]:
        assert set(entry.keys()) == {"backend", "model", "tokens", "session", "d7", "h5", "d1", "d28", "all", "first_seen", "pace"}
        assert set(entry["session"].keys()) == {"tokens", "cost", "equiv_cost"}
        assert set(entry["d7"].keys()) == {"tokens", "cost", "equiv_cost"}
        # Free tier is unpriced, but the API-equivalent estimate (haiku tier) is numeric.
        assert entry["d7"]["equiv_cost"] == pytest.approx(entry["d7"]["tokens"] / 1_000_000)
        assert entry["d7"]["tokens"] == entry["tokens"]
        assert isinstance(entry["session"]["tokens"], int)
        # Fixture free rows are all inside the session window.
        assert entry["session"]["tokens"] == entry["d7"]["tokens"]
        # No prices exist for the free backends -> cost is null (renderer shows "$0").
        assert entry["session"]["cost"] is None
        assert entry["d7"]["cost"] is None


def test_free_top4_session_zero_outside_window(temp_dir, config_file, transcript_file, usage_db, prices_file, codex_dir):
    """A session window in the future yields zero session tokens but intact d7 tokens (rows inside 7D)."""
    cache_path = temp_dir / "cache.json"
    future = 4102444800  # 2100-01-01
    args = [
        "--session-id", "free-future",
        "--transcript", str(transcript_file),
        "--session-start", str(future),
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", "1788651000",
        "--codex-glob", str(codex_dir / "**" / "*.jsonl"),
        "--usage-db", str(usage_db),
        "--prices", str(prices_file),
        "--force",
    ]
    result = run_collector(args)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = json.loads(result.stdout)
    assert out["free_top4_d7"], "expected free entries"
    for entry in out["free_top4_d7"]:
        assert entry["session"]["tokens"] == 0
        if entry["model"] != "gemini-old":  # 2020 row: outside 7D, shown by all-time rank
            assert entry["d7"]["tokens"] > 0


def test_absent_sources_give_null_not_zero(temp_dir, config_file, transcript_file, prices_file, codex_dir):
    """Unknown is not zero: a missing usage db leaves OpenAI session and window tokens null."""
    cache_path = temp_dir / "cache.json"
    args = [
        "--session-id", "test",
        "--transcript", str(transcript_file),
        "--session-start", "1788600000",
        "--config", str(config_file),
        "--out", str(cache_path),
        "--now", "1788651000",
        "--usage-db", str(temp_dir / "missing.db"),
        "--prices", str(prices_file),
        "--force",
    ]
    result = run_collector(args)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    oai = [m for m in out["models"].values() if m["provider"] == "openai"]
    assert oai
    for m in oai:
        assert m["session"]["tokens"] is None
        assert m["session"]["tokens_noncache"] is None
        assert m["d7"]["tokens"] is None
    claude = [m for m in out["models"].values() if m["provider"] == "claude"]
    assert any(m["session"]["tokens"] is not None for m in claude)


def test_claude_windows_null_without_usage_db_even_with_state_db(temp_dir, config_file, transcript_file, prices_file):
    """Claude windows come from usage.db only: a Codex state db must not make them look known."""
    import sqlite3 as _s
    state = temp_dir / "state_5.sqlite"
    _s.connect(state).close()
    cfg = json.loads(config_file.read_text()); cfg["codex_state_db"] = str(state)
    config_file.write_text(json.dumps(cfg))
    args = ["--session-id", "test", "--transcript", str(transcript_file), "--session-start", "1788600000",
            "--config", str(config_file), "--out", str(temp_dir / "c.json"), "--now", "1788651000",
            "--usage-db", str(temp_dir / "missing.db"), "--prices", str(prices_file), "--force"]
    out = json.loads(run_collector(args).stdout)
    for m in out["models"].values():
        if m["provider"] == "claude":
            assert m["d7"]["tokens"] is None


def test_history_days_plausible(temp_dir, config_file, transcript_file, usage_db, prices_file, codex_dir):
    """history_days = now - earliest usage row per provider, uncapped (real clock, fixture rows are relative to it)."""
    cache_path = temp_dir / "cache.json"
    args = [
        "--session-id", "hist-1",
        "--transcript", str(transcript_file),
        "--config", str(config_file),
        "--out", str(cache_path),
        "--codex-glob", str(codex_dir / "**" / "*.jsonl"),
        "--usage-db", str(usage_db),
        "--prices", str(prices_file),
        "--force",
    ]
    result = run_collector(args)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    h = json.loads(cache_path.read_text())["history_days"]
    assert set(h) == {"claude", "openai", "free"}
    # claude: oldest fixture row is 20 days old
    assert 19.9 < h["claude"] < 20.1
    # openai: oldest fixture row is 1 hour old
    assert 0.0 < h["openai"] < 0.1
    # free: 2020 gemini row, uncapped (well beyond 28 days)
    assert h["free"] > 2000


OLD_DAY = "2026-01-01"


def _seed_ranking_db(path, rows):
    """rows: (backend, model, tokens[, day]); day defaults to today (inside every window), OLD_DAY is outside 28D."""
    conn = sqlite3.connect(path)
    conn.executescript((FIXTURES / "usage_fixture.sql").read_text().split("INSERT")[0])
    for i, row in enumerate(rows):
        backend, model, tok = row[:3]
        if len(row) > 3:
            conn.execute(
                "INSERT INTO usage(uid,ts,day,backend,model,input_tokens,output_tokens) VALUES (?,?,?,?,?,?,0)",
                ("r%d" % i, row[3] + "T00:00:00.000+00:00", row[3], backend, model, tok))
        else:
            conn.execute(
                "INSERT INTO usage(uid,ts,day,backend,model,input_tokens,output_tokens) VALUES (?,?,date('now','localtime'),?,?,?,0)",
                ("r%d" % i, "2026-10-01T00:00:00.000+00:00", backend, model, tok))
    conn.commit()
    conn.close()


def _run_rank(temp_dir, rows, toml_text=None, claude_model=""):
    db = temp_dir / "rank.db"
    db.unlink(missing_ok=True)
    _seed_ranking_db(db, rows)
    cfg = {"usage_db": str(db), "codex_state_db": "", "prices_json": [], "cache_path": str(temp_dir / "rc.json"),
           "codex_sessions_glob": str(temp_dir / "none" / "*.jsonl"), "codex_config_toml": ""}
    if toml_text is not None:
        toml = temp_dir / "config.toml"
        toml.write_text(toml_text)
        cfg["codex_config_toml"] = str(toml)
    cfg_path = temp_dir / "rank_config.json"
    cfg_path.write_text(json.dumps(cfg))
    args = ["--session-id", "s", "--config", str(cfg_path), "--out", str(temp_dir / "rc.json"), "--force"]
    if claude_model:
        args += ["--current-claude-model", claude_model]
    r = run_collector(args)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


_RANK_CLAUDE = [
    ("claude", "claude-sonnet-5", 900, OLD_DAY), ("claude", "claude-opus-5", 800, OLD_DAY),  # retired: 28D 0
    ("claude", "claude-opus-5-5", 100), ("claude", "claude-haiku-4-5-20251001", 90),
    ("claude", "claude-sonnet-5-5", 70), ("claude", "claude-sonnet-5-5", 500, OLD_DAY),  # 28D tie with fable-5-2, more ALL
    ("claude", "claude-fable-5-2", 70), ("claude", "claude-fable-5-1", 60),               # 5th by 28D
    ("claude", "nvidia/nemotron-x:free", 5000),  # backend claude but not a Claude id
]
_RANK_OPENAI = [("codex", "gpt-5.6-sol", 50), ("codex", "gpt-5.6-luna", 80), ("codex", "gpt-5.6-terra", 70),
                ("codex", "gpt-6-astra", 60), ("codex", "gpt-5.5", 90, OLD_DAY), ("codex", "gpt-5.5", 10)]


def test_rows_rank_by_28d_then_all_then_id(temp_dir):
    out = _run_rank(temp_dir, _RANK_CLAUDE + _RANK_OPENAI)
    ids = list(out["models"])
    # retired ids (28D 0) not shown; sonnet-5-5 beats fable-5-2 on the 28D tie by ALL.
    assert ids[:4] == ["claude-opus-5-5", "claude-haiku-4-5", "claude-sonnet-5-5", "claude-fable-5-2"]
    assert ids[4:] == ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-6-astra", "gpt-5.6-sol"]
    assert "claude-sonnet-5" not in ids and "claude-opus-5" not in ids
    assert out["models"]["claude-sonnet-5-5"]["all"]["tokens"] == 570
    assert out["models"]["claude-opus-5-5"]["label"] == "Opus 5.5"
    assert out["models"]["gpt-5.6-luna"]["label"] == "GPT-5.6 Luna"


def test_non_claude_id_under_claude_backend_is_not_a_claude_row(temp_dir):
    out = _run_rank(temp_dir, _RANK_CLAUDE + _RANK_OPENAI)
    assert "nvidia/nemotron-x:free" not in out["models"]


def test_non_shown_model_stays_in_provider_windows(temp_dir):
    out = _run_rank(temp_dir, _RANK_CLAUDE + _RANK_OPENAI)
    assert "claude-fable-5-1" not in out["models"]
    shown = sum(out["models"][m]["all"]["tokens"] for m in out["models"] if m.startswith("claude-"))
    pw = out["provider_windows"]["claude"]["all"]["tokens"]
    assert pw >= shown + 60 + 900 + 800  # fable-5-1 and both retired ids still counted


def test_pick_rows_tie_breaks_on_all_then_id():
    sys.path.insert(0, str(COLLECTOR.parent))
    import collect_usage as cu
    cands = ["c", "b", "a", "d", "e"]
    d28 = {m: 10 for m in cands}
    all_ = {"a": 5, "b": 5, "c": 9, "d": 1, "e": 7}
    assert cu.pick_rows(cands, all_, None, recent_tokens=d28) == ["c", "e", "a", "b"]


def test_current_model_outside_top4_takes_row4(temp_dir):
    out = _run_rank(temp_dir, _RANK_CLAUDE + _RANK_OPENAI,
                    toml_text='model = "gpt-5.6-sol"\nmodel_reasoning_effort = "low"\n[projects.x]\nmodel = "other"\n',
                    claude_model="claude-fable-5-1[1m]")
    ids = list(out["models"])
    # pin replaces row 4 and sorts last by the same key (28D 60)
    assert ids[:4] == ["claude-opus-5-5", "claude-haiku-4-5", "claude-sonnet-5-5", "claude-fable-5-1"]
    assert out["model_pins"] == {"claude": "claude-fable-5-1", "openai": "gpt-5.6-sol"}
    # Pin already inside the top 4 keeps its rank.
    out = _run_rank(temp_dir, _RANK_CLAUDE + _RANK_OPENAI, toml_text='model = "gpt-5.6-luna"\n', claude_model="claude-haiku-4-5")
    assert list(out["models"])[:4] == ["claude-opus-5-5", "claude-haiku-4-5", "claude-sonnet-5-5", "claude-fable-5-2"]
    assert list(out["models"])[4] == "gpt-5.6-luna"


def test_model_label_and_normalize():
    sys.path.insert(0, str(COLLECTOR.parent))
    import collect_usage as cu
    assert cu.model_label("claude-haiku-4-5-20251001") == "Haiku 4.5"
    assert cu.model_label("claude-sonnet-5") == "Sonnet 5"
    assert cu.model_label("gpt-6-astra") == "GPT-6 Astra"
    assert cu.model_label("gpt-5.6-terra") == "GPT-5.6 Terra"
    assert cu.normalize_model("claude-opus-5-5") == "claude-opus-5-5"
    assert cu.normalize_model("sol") == "sol"


# ---- spec 043 Phase 1: family pricing (FR-001, FR-002, FR-003) ----

def _cu():
    sys.path.insert(0, str(COLLECTOR.parent))
    import collect_usage as cu
    return cu


def test_parse_family_table():
    cu = _cu()
    assert cu.parse_family("claude-fable-5-2") == ("claude", "fable", (5, 2))
    assert cu.parse_family("claude-opus-5") == ("claude", "opus", (5, 0))
    assert cu.parse_family("claude-haiku-4-5-20251001") == ("claude", "haiku", (4, 5))
    assert cu.parse_family("gpt-5.6-sol") == ("openai", "sol", (5, 6))
    assert cu.parse_family("gpt-6.1-sol") == ("openai", "sol", (6, 1))
    assert cu.parse_family("gpt-6-astra") == ("openai", "astra", (6, 0))
    # one family across versions; another stem is another family
    assert cu.parse_family("gpt-5.6-sol")[:2] == cu.parse_family("gpt-6.1-sol")[:2]
    assert cu.parse_family("gpt-6.1-terra")[:2] != cu.parse_family("gpt-6.1-sol")[:2]
    for bad in ("claude-zeta-1", "gpt-5.5", "gpt-5.4-mini", "codex-auto-review", "gemini-3.8-flash", "", None):
        assert cu.parse_family(bad) is None


def test_price_for_chain():
    cu = _cu()
    prices = json.loads((FIXTURES / "prices_fixture.json").read_text())["models"]
    est = {"gpt-6.1-sol": "claude-opus-5", "gpt-6.1-terra": "claude-sonnet-5"}
    p, src = cu.price_for("claude-fable-5-1", prices, est)
    assert (p["input"], src) == (10, "exact")
    p, src = cu.price_for("claude-fable-5-1-20260101", prices, est)  # date stripped
    assert (p["input"], src) == (10, "exact")
    p, src = cu.price_for("claude-fable-5-2", prices, est)  # nearest at or below
    assert (p["input"], src) == (10, "family:claude-fable-5-1")
    p, src = cu.price_for("claude-fable-5-4", prices, est)
    assert (p["input"], src) == (6, "family:claude-fable-5-3")
    p, src = cu.price_for("claude-fable-4-9", prices, est)  # only above: lowest above
    assert (p["input"], src) == (10, "family:claude-fable-5-1")
    p, src = cu.price_for("gpt-6.1-terra", prices, est)  # family beats estimate
    assert (p["input"], src) == (2, "family:gpt-6-terra")
    p, src = cu.price_for("gpt-6.1-sol", prices, est)  # no priced sol -> estimate
    assert (p["input"], src) == (5, "estimate:claude-opus-5")
    assert cu.price_for("claude-zeta-1", prices, est) == (None, None)
    assert cu.price_for("", prices, est) == (None, None)


def _family_db(temp_dir, rows):
    db = temp_dir / "fam.db"
    _seed_ranking_db(db, [])
    conn = sqlite3.connect(db)
    for i, (backend, model, inp, out_) in enumerate(rows):
        conn.execute(
            "INSERT INTO usage(uid,ts,day,backend,model,input_tokens,output_tokens) "
            "VALUES (?,strftime('%Y-%m-%dT%H:%M:%f+00:00','now','-1 hour'),date('now','localtime'),?,?,?,?)",
            ("f%d" % i, backend, model, inp, out_))
    conn.commit()
    conn.close()
    return db


def _family_run(temp_dir, prices_file, rows):
    db = _family_db(temp_dir, rows)
    cfg = {"usage_db": str(db), "codex_state_db": "", "prices_json": [str(prices_file)], "cache_path": str(temp_dir / "fc.json"),
           "codex_sessions_glob": str(temp_dir / "none" / "*.jsonl"), "codex_config_toml": ""}
    cfg_path = temp_dir / "fam_config.json"
    cfg_path.write_text(json.dumps(cfg))
    r = run_collector(["--session-id", "s", "--config", str(cfg_path), "--out", str(temp_dir / "fc.json"),
                       "--prices", str(prices_file), "--force"])
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_collector_unpriced_ids_priced_by_family(temp_dir, prices_file):
    out = _family_run(temp_dir, prices_file, [("claude", "claude-fable-5-2", 1000000, 100000), ("claude", "claude-haiku-5-5", 2000000, 0)])
    fab, hai = out["models"]["claude-fable-5-2"], out["models"]["claude-haiku-5-5"]
    n = 0
    for m in (fab, hai):
        for w, cell in m.items():
            if isinstance(cell, dict) and cell.get("tokens"):
                assert "cost" in cell and cell["cost"] is not None, (w, cell)
                n += 1
    assert n >= 6
    assert fab["d7"]["cost"] == pytest.approx(1 * 10 + 0.1 * 50)  # family claude-fable-5-1
    assert hai["d7"]["cost"] == pytest.approx(2 * 1)  # family claude-haiku-4-5
    assert out["claude_d7"]["cost"] == pytest.approx(fab["d7"]["cost"] + hai["d7"]["cost"])


def test_collector_no_priced_family_cost_null(temp_dir, prices_file):
    out = _family_run(temp_dir, prices_file, [("claude", "claude-zeta-1", 1000, 0)])
    z = out["models"]["claude-zeta-1"]
    assert z["d7"]["tokens"] == 1000 and z["d7"]["cost"] is None
    assert z["all"]["cost"] is None


def test_collector_own_entry_beats_family(temp_dir, prices_file):
    out = _family_run(temp_dir, prices_file, [("claude", "claude-fable-5-3", 1000000, 0)])
    assert out["models"]["claude-fable-5-3"]["d7"]["cost"] == pytest.approx(6.0)  # own 6, not family 5-1's 10


# ---- spec 043 Phase 2: in-window OpenAI tokens from rollout token_count deltas ----
import datetime as _dt

H = 3600
MODEL = "gpt-6.1-sol"


def _iso(epoch):
    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _midnight(now, back_days=0):
    d = _dt.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0) - _dt.timedelta(days=back_days)
    return int(time.mktime(d.timetuple()))


def _write_rollout(path, events, corrupt=False):
    """events: (epoch, total, input, cached, output) cumulative."""
    lines = []
    for ts, total, inp, cached, out in events:
        lines.append(json.dumps({"timestamp": _iso(ts), "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
            "input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out, "reasoning_output_tokens": 0, "total_tokens": total}}}}))
    if corrupt:
        lines.insert(1, '{"type":"event_msg","payload":{"type":"token_count" BROKEN')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def _state_db(path, threads):
    """threads: (id, model, created_at, updated_at, tokens_used, rollout_path)."""
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE threads(id TEXT PRIMARY KEY, model TEXT, created_at INT, updated_at INT, tokens_used INT, rollout_path TEXT, cwd TEXT)")
    c.executemany("INSERT INTO threads VALUES(?,?,?,?,?,?,'/x')", threads)
    c.commit()
    c.close()


def _run043(temp_dir, prices_file, threads=None, now=None, usage_rows=None, use_state=True, rollout_dir_missing=False, reset_off=2 * H, rerun=False, extra_args=()):
    now = now or int(time.time())
    sdb = temp_dir / "state.sqlite"
    if threads is not None and use_state and not rerun:
        _state_db(sdb, threads)
    udb = temp_dir / "u043.db"
    c = sqlite3.connect(udb)
    if not rerun:
        c.executescript((FIXTURES / "usage_fixture.sql").read_text().split("INSERT")[0])
    for r in ([] if rerun else (usage_rows or [])):
        c.execute("INSERT INTO usage(uid,ts,day,backend,model,input_tokens,output_tokens,cache_read) VALUES(?,?,?,?,?,?,?,?)", r)
    c.commit()
    c.close()
    gl = temp_dir / "gap.log"
    if not rerun:
        gl.write_text("")
    glob_dir = temp_dir / "limits"
    glob_dir.mkdir(exist_ok=True)
    (glob_dir / "r.jsonl").write_text(json.dumps({"timestamp": _iso(now - 60), "type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "limit_id": "codex", "primary": {"used_percent": 1.0, "window_minutes": 300, "resets_at": now + reset_off},
        "secondary": {"used_percent": 1.0, "window_minutes": 10080, "resets_at": now + 86400}}}}) + "\n")
    cfg = {"usage_db": str(udb), "codex_state_db": str(sdb) if use_state else str(temp_dir / "nostate.sqlite"), "prices_json": [str(prices_file)],
           "cache_path": str(temp_dir / "c043.json"), "codex_sessions_glob": str(glob_dir / "*.jsonl"), "codex_config_toml": "",
           "openai_price_estimates": {MODEL: "claude-opus-5"}, "gap_log": str(gl)}
    cp = temp_dir / "cfg043.json"
    cp.write_text(json.dumps(cfg))
    r = run_collector(["--session-id", "s", "--config", str(cp), "--out", str(temp_dir / "c043.json"), "--prices", str(prices_file),
                       "--now", str(now), "--force"] + list(extra_args))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout), gl


def test_spanning_thread_gives_in_window_5h_and_1d(temp_dir, prices_file):
    now = int(time.time())
    ro = temp_dir / "ro" / "a.jsonl"
    _write_rollout(ro, [(now - 8 * H, 1000, 800, 0, 200), (now - 1 * H, 1500, 1200, 0, 300)])
    out, _ = _run043(temp_dir, prices_file, [("t1", MODEL, now - 8 * H, now - H, 1500, str(ro))], now)
    m = out["models"][MODEL]
    assert m["h5"]["tokens"] == 500
    # 1D: since local midnight; the -8h event is before midnight only when now-8h < midnight
    mid = _midnight(now)
    base = 1000 if now - 8 * H < mid else 0
    assert m["d1"]["tokens"] == 1500 - base
    assert out["openai_h5"]["tokens"] == 500


def test_missing_rollout_created_in_window_counts_lifetime(temp_dir, prices_file):
    now = int(time.time())
    out, _ = _run043(temp_dir, prices_file, [("t1", MODEL, now - 2 * H, now - H, 700, str(temp_dir / "gone.jsonl"))], now)
    assert out["models"][MODEL]["h5"]["tokens"] == 700


def test_missing_rollout_created_before_window_gives_zero_and_gap_line(temp_dir, prices_file):
    now = int(time.time())
    out, gl = _run043(temp_dir, prices_file, [("t1", MODEL, now - 20 * H, now - H, 900, str(temp_dir / "gone.jsonl"))], now)
    assert out["models"][MODEL]["h5"]["tokens"] == 0
    assert gl.read_text().splitlines() == ["gaps openai 1 threads 900 tokens"]


def test_cost_is_price_times_category_split(temp_dir, prices_file):
    now = int(time.time())
    ro = temp_dir / "ro" / "a.jsonl"
    # in window: input 1,000,000 (of which cached 400,000), output 200,000; total = input + output
    _write_rollout(ro, [(now - 8 * H, 100, 80, 0, 20), (now - H, 1_200_100, 1_000_080, 400_000, 200_020)])
    out, _ = _run043(temp_dir, prices_file, [("t1", MODEL, now - 8 * H, now - H, 1_200_100, str(ro))], now)
    h5 = out["models"][MODEL]["h5"]
    assert h5["tokens"] == 1_200_000
    # estimate map: gpt-6.1-sol -> claude-opus-5 (in 5, out 25, cache_read 0.5 per MTok); uncached input 600k
    expect = 0.6 * 5 + 0.2 * 25 + 0.4 * 0.5
    assert out["openai_h5"]["cost"] == pytest.approx(expect)
    assert out["provider_windows"]["openai"]["h5"]["cost"] == pytest.approx(expect)


def test_no_cost_under_a_cent_beside_over_1m_tokens(temp_dir, prices_file):
    now = int(time.time())
    ro = temp_dir / "ro" / "a.jsonl"
    _write_rollout(ro, [(now - 2 * H, 2_000_000, 1_500_000, 0, 500_000)])
    out, _ = _run043(temp_dir, prices_file, [("t1", MODEL, now - 2 * H, now - H, 2_000_000, str(ro))], now)
    for w in ("h5", "d1", "d7", "d28"):
        cell = out["models"][MODEL][w]
        if cell["tokens"] and cell["tokens"] > 1_000_000 and cell.get("cost") is not None:
            assert cell["cost"] >= 0.01, (w, cell)
    pw = out["provider_windows"]["openai"]["h5"]
    assert pw["tokens"] > 1_000_000 and pw["cost"] is not None and pw["cost"] >= 0.01


def test_d7_and_d28_thread_start_are_local_midnight(temp_dir, prices_file):
    now = int(time.time())
    ro7, ro28 = temp_dir / "ro" / "d7.jsonl", temp_dir / "ro" / "d28.jsonl"
    m7, m28 = _midnight(now, 6), _midnight(now, 27)
    _write_rollout(ro7, [(m7 - 60, 100, 100, 0, 0), (m7 + 60, 400, 400, 0, 0)])
    _write_rollout(ro28, [(m28 - 60, 1000, 1000, 0, 0), (m28 + 60, 1700, 1700, 0, 0)])
    out, _ = _run043(temp_dir, prices_file, [("a", MODEL, m7 - 3600, now, 400, str(ro7)),
                                              ("b", MODEL, m28 - 3600, now, 1700, str(ro28))], now)
    m = out["models"][MODEL]
    # d7 start is -6 days midnight (same as usage.db): thread a delta 300 counts, b's delta after m28 also 700 (before m7)
    # b has only events at m28 -> all 700 delta since m28 sits in d28; in d7 b's last-before-start total is 1700 -> 0
    assert m["d7"]["tokens"] == 300
    assert m["d28"]["tokens"] == 400 + 700  # a: 400 after m28; b: 700 after m28


def test_corrupt_rollout_line_drops_only_that_thread(temp_dir, prices_file):
    now = int(time.time())
    good, bad = temp_dir / "ro" / "g.jsonl", temp_dir / "ro" / "b.jsonl"
    _write_rollout(good, [(now - 2 * H, 300, 300, 0, 0)])
    _write_rollout(bad, [(now - 3 * H, 100, 100, 0, 0), (now - 2 * H, 900, 900, 0, 0)], corrupt=True)
    out, _ = _run043(temp_dir, prices_file, [("g", MODEL, now - 2 * H, now, 300, str(good)), ("b", MODEL, now - 3 * H, now, 900, str(bad))], now)
    assert out["models"][MODEL]["h5"]["tokens"] == 300


def test_missing_state_db_and_rollout_dir_give_nulls_exit_zero(temp_dir, prices_file):
    now = int(time.time())
    out, _ = _run043(temp_dir, prices_file, None, now, use_state=False)
    assert out["openai_h5"]["tokens"] == 0
    sub = temp_dir / "second"
    sub.mkdir()
    out2, _ = _run043(sub, prices_file, [("t", MODEL, now - H, now, 5, str(sub / "nodir" / "x.jsonl"))], now)
    assert "models" in out2 and "provider_windows" in out2


def test_cost_follows_the_larger_token_source(temp_dir, prices_file):
    now = int(time.time())
    ro = temp_dir / "ro" / "a.jsonl"
    # threads: 3M in-window (input 3M uncached) -> wins over usage.db 1000 tokens
    _write_rollout(ro, [(now - 2 * H, 3_000_000, 3_000_000, 0, 0)])
    iso = _dt.datetime.fromtimestamp(now - H, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    day = _dt.datetime.fromtimestamp(now - H).strftime("%Y-%m-%d")
    rows = [("x1", iso, day, "codex", MODEL, 1000, 0, 0)]
    out, _ = _run043(temp_dir, prices_file, [("t1", MODEL, now - 2 * H, now - H, 3_000_000, str(ro))], now, usage_rows=rows)
    m = out["models"][MODEL]
    assert m["h5"]["tokens"] == 3_000_000
    assert out["openai_h5"]["tokens"] == 3_000_000
    assert out["openai_h5"]["cost"] == pytest.approx(3 * 5)  # thread source cost, not usage.db's 1000-token cost
    assert m["d7"]["cost"] == pytest.approx(3 * 5)


def test_missing_rollout_not_updated_in_window_is_no_gap(temp_dir, prices_file):
    now = int(time.time())
    out, gl = _run043(temp_dir, prices_file, [("t1", MODEL, now - 30 * H, now - 20 * H, 900, str(temp_dir / "gone.jsonl"))], now)
    assert out["models"][MODEL]["h5"]["tokens"] == 0
    assert not [l for l in gl.read_text().splitlines() if l.startswith("gap h5 ")]


def _t13a_threads(temp_dir, now):
    ro = temp_dir / "ro" / "a.jsonl"
    _write_rollout(ro, [(now - 8 * H, 1000, 800, 0, 200), (now - 1 * H, 1500, 1200, 0, 300)])
    return [("t1", MODEL, now - 8 * H, now - H, 1500, str(ro)),
            ("g1", MODEL, now - 20 * H, now - H, 900, str(temp_dir / "gone.jsonl"))]


def test_ended_5h_window_zeroes_openai_h5_and_nulls_reset(temp_dir, prices_file):
    now = int(time.time())
    out, _ = _run043(temp_dir, prices_file, _t13a_threads(temp_dir, now), now, reset_off=-60)
    assert out["codex"]["h5"]["resets_at"] is None
    assert out["models"][MODEL]["h5"]["tokens"] == 0
    assert out["openai_h5"]["tokens"] == 0 and out["openai_h5"]["cost"] == 0
    pw = out["provider_windows"]["openai"]["h5"]
    assert pw["tokens"] == 0 and pw["cost"] == 0


def test_future_5h_reset_keeps_delta_figures(temp_dir, prices_file):
    now = int(time.time())
    out, _ = _run043(temp_dir, prices_file, _t13a_threads(temp_dir, now), now, reset_off=2 * H)
    assert out["codex"]["h5"]["resets_at"] == now + 2 * H
    assert out["models"][MODEL]["h5"]["tokens"] == 500


def test_gap_summary_one_line_only_on_change(temp_dir, prices_file):
    now = int(time.time())
    th = _t13a_threads(temp_dir, now)
    out, gl = _run043(temp_dir, prices_file, th, now)
    assert out["openai_gaps"] == {"threads": 1, "tokens": 900}
    lines = [l for l in gl.read_text().splitlines() if l.startswith("gaps ")]
    assert lines == ["gaps openai 1 threads 900 tokens"]
    _run043(temp_dir, prices_file, th, now, rerun=True)
    assert len([l for l in gl.read_text().splitlines() if l.startswith("gaps ")]) == 1
    c = sqlite3.connect(temp_dir / "state.sqlite")
    c.execute("INSERT INTO threads VALUES('g2',?,?,?,?,?,'/x')", (MODEL, now - 30 * H, now - H, 50, str(temp_dir / "gone2.jsonl")))
    c.commit(); c.close()
    _run043(temp_dir, prices_file, th, now, rerun=True)
    lines = [l for l in gl.read_text().splitlines() if l.startswith("gaps ")]
    assert lines[-1] == "gaps openai 2 threads 950 tokens" and len(lines) == 2
    assert not [l for l in gl.read_text().splitlines() if l.startswith("gap ")]


def test_openai_gaps_null_when_sources_missing(temp_dir, prices_file):
    out, _ = _run043(temp_dir, prices_file, None, int(time.time()), use_state=False)
    assert out["openai_gaps"] is None


# ---- spec 043 Phase 5: pace cache keys (FR-011, FR-012) ----
D = 86400
_PACE_KEYS = {"usd_per_day", "days", "hist_days", "all_cost", "source"}


def _urow(uid, backend, model, ts, inp, out=0, cr=0):
    day = _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    return (uid, _iso(ts), day, backend, model, inp, out, cr)


def test_pace_own_history_seven_days_or_more(temp_dir, prices_file):
    now = int(time.time())
    rows = [_urow("a", "claude", "claude-fable-5-1", now - 40 * D, 1_000_000), _urow("b", "claude", "claude-fable-5-1", now - 2 * H, 1_000_000)]
    out, _ = _run043(temp_dir, prices_file, None, now, rows, use_state=False)
    m = out["models"]["claude-fable-5-1"]
    assert abs(m["first_seen"] - (now - 40 * D)) <= 1
    p = m["pace"]
    assert set(p) == _PACE_KEYS and p["source"] == "own"
    assert p["days"] == 28 and p["hist_days"] == pytest.approx(40, abs=0.01)
    assert p["usd_per_day"] == pytest.approx(10.0 / 28) and p["all_cost"] == pytest.approx(20.0)


def test_pace_own_days_floor_is_history_under_cap(temp_dir, prices_file):
    now = int(time.time())
    rows = [_urow("a", "claude", "claude-fable-5-1", now - 10 * D, 1_000_000)]
    out, _ = _run043(temp_dir, prices_file, None, now, rows, use_state=False)
    p = out["models"]["claude-fable-5-1"]["pace"]
    assert p["source"] == "own" and p["days"] == pytest.approx(10, abs=0.01) and p["usd_per_day"] == pytest.approx(1.0, abs=0.01)


def test_pace_new_id_uses_family_sums(temp_dir, prices_file):
    now = int(time.time())
    rows = [_urow("a", "claude", "claude-fable-5-2", now - 2 * D, 1_000_000),
            _urow("b", "claude", "claude-fable-5-1", now - 60 * D, 1_000_000),
            _urow("c", "claude", "claude-fable-5-1", now - 5 * D, 1_000_000)]
    out, _ = _run043(temp_dir, prices_file, None, now, rows, use_state=False)
    m = out["models"]["claude-fable-5-2"]
    assert abs(m["first_seen"] - (now - 2 * D)) <= 1
    p = m["pace"]
    assert p["source"] == "family" and p["days"] == 28 and p["hist_days"] == pytest.approx(60, abs=0.01)
    assert p["usd_per_day"] == pytest.approx(20.0 / 28) and p["all_cost"] == pytest.approx(30.0)


def test_pace_no_family_no_baseline_is_null(temp_dir, prices_file):
    now = int(time.time())
    rows = [_urow("a", "claude", "claude-zeta-1", now - 2 * D, 1000)]
    out, _ = _run043(temp_dir, prices_file, None, now, rows, use_state=False)
    m = out["models"]["claude-zeta-1"]
    assert abs(m["first_seen"] - (now - 2 * D)) <= 1
    assert m["pace"] == {"usd_per_day": None, "days": None, "hist_days": None, "all_cost": None, "source": None}


def test_h5_cost_is_price_times_5h_rows(temp_dir, prices_file):
    now = int(time.time())
    rows = [_urow("a", "claude", "claude-fable-5-1", now - H, 1_000_000, 100_000), _urow("b", "claude", "claude-fable-5-1", now - 9 * H, 1_000_000)]
    out, _ = _run043(temp_dir, prices_file, None, now, rows, use_state=False, extra_args=["--claude-h5-resets-at", str(now + 4 * H)])
    h5 = out["models"]["claude-fable-5-1"]["h5"]
    assert h5["tokens"] == 1_100_000 and h5["cost"] == pytest.approx(10 + 0.1 * 50)


def test_new_keys_present_null_when_sources_missing(temp_dir, prices_file):
    out, _ = _run043(temp_dir, prices_file, None, int(time.time()), None, use_state=False)
    cfg = json.loads((temp_dir / "cfg043.json").read_text())
    cfg["usage_db"] = str(temp_dir / "missing.db")
    (temp_dir / "cfg043.json").write_text(json.dumps(cfg))
    r = run_collector(["--session-id", "s", "--config", str(temp_dir / "cfg043.json"), "--out", str(temp_dir / "m.json"), "--prices", str(prices_file), "--force"])
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["models"]
    for m in out["models"].values():
        assert m["first_seen"] is None and m["h5"]["cost"] is None
        assert m["pace"] == {"usd_per_day": None, "days": None, "hist_days": None, "all_cost": None, "source": None}


def test_free_top4_rows_carry_first_seen_and_pace(temp_dir, prices_file):
    now = int(time.time())
    rows = [_urow("a", "mistral", "mistral-large", now - 30 * D, 1_000_000), _urow("b", "mistral", "mistral-large", now - 2 * H, 1_000_000)]
    out, _ = _run043(temp_dir, prices_file, None, now, rows, use_state=False)
    f = [r for r in out["free_top4_d7"] if r["model"] == "mistral-large"][0]
    assert abs(f["first_seen"] - (now - 30 * D)) <= 1
    assert set(f["pace"]) == _PACE_KEYS and f["pace"]["source"] == "own"
    assert f["pace"]["usd_per_day"] == pytest.approx(f["d28"]["equiv_cost"] / 28)
    assert f["pace"]["all_cost"] == pytest.approx(f["all"]["equiv_cost"])


def test_first_seen_counts_rows_under_any_backend(temp_dir, prices_file):
    now = int(time.time())
    rows = [_urow("a", "claude", MODEL, now - 20 * D, 1000), _urow("b", "codex", MODEL, now - 3 * D, 1000)]
    out, _ = _run043(temp_dir, prices_file, None, now, rows, use_state=False)
    assert abs(out["models"][MODEL]["first_seen"] - (now - 20 * D)) <= 1


def test_first_seen_takes_thread_created_at(temp_dir, prices_file):
    now = int(time.time())
    ro = temp_dir / "ro" / "fs.jsonl"
    _write_rollout(ro, [(now - 15 * D, 1000, 800, 0, 200)])
    out, _ = _run043(temp_dir, prices_file, [("t1", MODEL, now - 15 * D, now - H, 1000, str(ro))], now,
                     [_urow("a", "codex", MODEL, now - 3 * D, 1000)])
    assert out["models"][MODEL]["first_seen"] == now - 15 * D


def test_openai_pace_all_cost_uses_category_method(temp_dir, prices_file):
    now = int(time.time())
    ro = temp_dir / "ro" / "pc.jsonl"
    _write_rollout(ro, [(now - 10 * D, 1_000_000, 800_000, 200_000, 200_000)])
    th = [("t1", MODEL, now - 10 * D, now - H, 1_000_000, str(ro)), ("t2", MODEL, now - 9 * D, now - H, 100_000, str(temp_dir / "gone.jsonl"))]
    out, _ = _run043(temp_dir, prices_file, th, now)
    m = out["models"][MODEL]
    cat = 600_000 * 5 / 1e6 + 200_000 * 0.5 / 1e6 + 200_000 * 25 / 1e6  # t1 by category
    assert m["d28"]["cost"] == pytest.approx(cat + 0.5)
    assert m["pace"]["source"] == "own"
    assert m["pace"]["all_cost"] == pytest.approx(cat + 0.5)  # same method as d28.cost, t2 priced as uncached input


def test_openai_all_and_session_cost_use_category_method(temp_dir, prices_file):
    now = int(time.time())
    ro = temp_dir / "ro" / "ac.jsonl"
    _write_rollout(ro, [(now - 10 * D, 1_000_000, 800_000, 200_000, 200_000)])
    th = [("t1", MODEL, now - 10 * D, now - H, 1_000_000, str(ro)), ("t2", MODEL, now - 9 * D, now - H, 100_000, str(temp_dir / "gone.jsonl"))]
    out, _ = _run043(temp_dir, prices_file, th, now, extra_args=["--session-start", str(now - 20 * D)])
    m = out["models"][MODEL]
    cat = 600_000 * 5 / 1e6 + 200_000 * 0.5 / 1e6 + 200_000 * 25 / 1e6
    assert m["all"]["tokens"] == 1_100_000 and m["session"]["tokens"] == 1_100_000
    assert m["pace"]["source"] == "own"
    assert m["all"]["cost"] == pytest.approx(m["pace"]["all_cost"])
    assert m["all"]["cost"] == pytest.approx(cat + 0.5)
    assert m["session"]["cost"] == pytest.approx(cat + 0.5)
    assert out["provider_windows"]["openai"]["all"]["cost"] == pytest.approx(cat + 0.5)
    assert out["openai_all"]["cost"] == pytest.approx(cat + 0.5)
