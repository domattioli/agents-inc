"""Tests for agents_inc.model_sync (codex slug auto-promotion)."""
import json

from agents_inc import model_sync
from tests._free012 import raises, suite

ROUTING = (
    '{\n'
    '  "tiers": {\n'
    '    "grunt":       {"claude": "haiku",  "codex": "gpt-5.6-luna", "gemini": "g"},\n'
    '    "workhorse":   {"claude": "sonnet", "codex": "gpt-5.6-terra"},\n'
    '    "orchestrator":{"claude": "opus",   "codex": "gpt-5.6-sol"},\n'
    '    "executive":   {"claude": "fable",  "codex": "gpt-6-astra"}\n'
    '  }\n'
    '}\n'
)


INSTALLED = "0.1.0"


def _entry(tier):
    return {"vendor": "openai", "provider": "codex", "tier": tier, "status": "available"}


def _setup(tmp_path, slugs):
    cache = tmp_path / "models_cache.json"
    # Spec 047 D52.1: explicit eligibility fields and a client_version matching INSTALLED (the fake installed codex).
    cache.write_text(json.dumps({"client_version": INSTALLED, "models": [
        {"slug": s, "display_name": s, "visibility": "list", "supported_in_api": True} for s in slugs]}))
    routing = tmp_path / "routing.json"
    routing.write_text(ROUTING)
    models = tmp_path / "models.json"
    models.write_text(json.dumps({"version": "x", "models": {
        "gpt-5.6-luna": _entry("grunt"),
        "gpt-5.6-terra": _entry("workhorse"),
        "gpt-5.6-sol": _entry("orchestrator"),
        "gpt-6-astra": _entry("executive"),
    }}, indent=2))
    return cache, routing, models


def test_dry_run_reports_and_writes_nothing(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-5.6-sol", "gpt-6.1-sol", "gpt-6-sol"])
    before = (routing.read_text(), models.read_text())
    lines = model_sync.sync_codex(cache, routing, models, apply=False, installed=INSTALLED)
    assert any("gpt-5.6-sol" in l and "gpt-6.1-sol" in l for l in lines)
    assert (routing.read_text(), models.read_text()) == before


def test_apply_promotes_highest_version_numerically(tmp_path):
    cache, routing, models = _setup(
        tmp_path, ["gpt-5.6-sol", "gpt-6-sol", "gpt-6.1-sol", "gpt-6.10-sol", "gpt-6.9-sol"])
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert '"orchestrator":{"claude": "opus",   "codex": "gpt-6.10-sol"}' in routing.read_text()


def test_apply_changes_only_the_codex_slug_bytes(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert routing.read_text() == ROUTING.replace("gpt-5.6-sol", "gpt-6.1-sol")


def test_apply_clones_models_entry_with_same_tier(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    data = json.loads(models.read_text())["models"]
    assert data["gpt-6.1-sol"]["tier"] == "orchestrator"
    assert data["gpt-6.1-sol"]["provider"] == "codex"
    assert "gpt-5.6-sol" in data  # old id kept


def test_never_downgrades(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-5.6-astra", "gpt-5.5"])
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert routing.read_text() == ROUTING


def test_ignores_non_persona_slugs(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-reserve", "gpt-5.5", "codex-auto-review"])
    assert model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED) == []
    assert routing.read_text() == ROUTING


def test_idempotent(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol", "gpt-6-luna"])
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    snap = (routing.read_text(), models.read_text())
    assert model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED) == []
    assert (routing.read_text(), models.read_text()) == snap


def test_missing_cache_raises_clear_error(tmp_path):
    _, routing, models = _setup(tmp_path, [])
    try:
        model_sync.sync_codex(tmp_path / "nope.json", routing, models, apply=True, installed=INSTALLED)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_heals_routing_slug_missing_from_models(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-5.6-sol"])
    routing.write_text(ROUTING.replace("gpt-5.6-sol", "gpt-6.1-sol"))
    lines = model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert any("gpt-6.1-sol" in l for l in lines)
    data = json.loads(models.read_text())["models"]
    assert data["gpt-6.1-sol"]["tier"] == "orchestrator"
    assert data["gpt-6.1-sol"]["provider"] == "codex"
    assert "gpt-5.6-sol" in data
    assert model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED) == []


# ---- update-approval setting ----

def _paths(tmp_path):
    return tmp_path / "settings.json", tmp_path / "pending.json"


def test_load_mode_defaults_to_approve(tmp_path):
    settings, _ = _paths(tmp_path)
    assert model_sync.load_mode(settings) == "approve"
    settings.write_text("not json")
    assert model_sync.load_mode(settings) == "approve"
    settings.write_text('{"model_updates": "bogus"}')
    assert model_sync.load_mode(settings) == "approve"


def test_set_mode_roundtrip_and_rejects_bad_value(tmp_path):
    settings, _ = _paths(tmp_path)
    model_sync.set_mode(settings, "auto")
    assert model_sync.load_mode(settings) == "auto"
    model_sync.set_mode(settings, "approve")
    assert model_sync.load_mode(settings) == "approve"
    try:
        model_sync.set_mode(settings, "yolo")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_scheduled_auto_applies(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    settings, pending = _paths(tmp_path)
    model_sync.set_mode(settings, "auto")
    status, lines = model_sync.run_scheduled(cache, routing, models, settings, pending, installed=INSTALLED)
    assert status == "applied" and lines
    assert "gpt-6.1-sol" in routing.read_text()
    assert not pending.exists()


def test_scheduled_approve_writes_pending_and_changes_nothing(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    settings, pending = _paths(tmp_path)
    before = (routing.read_text(), models.read_text())
    status, lines = model_sync.run_scheduled(cache, routing, models, settings, pending, installed=INSTALLED)
    assert status == "pending" and lines
    assert (routing.read_text(), models.read_text()) == before
    data = json.loads(pending.read_text())
    assert data["lines"] == lines


def test_approve_applies_and_clears_pending(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    settings, pending = _paths(tmp_path)
    model_sync.run_scheduled(cache, routing, models, settings, pending, installed=INSTALLED)
    lines = model_sync.approve_pending(cache, routing, models, pending, installed=INSTALLED)
    assert lines and "gpt-6.1-sol" in routing.read_text()
    assert not pending.exists()


def test_scheduled_nothing_to_do_clears_stale_pending(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-5.6-sol"])
    settings, pending = _paths(tmp_path)
    pending.write_text('{"lines": ["stale"]}')
    status, lines = model_sync.run_scheduled(cache, routing, models, settings, pending, installed=INSTALLED)
    assert status == "none" and lines == []
    assert not pending.exists()


# ---- terra review findings ----

def test_equal_versions_do_not_promote(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.0-astra"])
    assert model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED) == []
    assert routing.read_text() == ROUTING


def test_only_tiers_block_is_edited(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    decoy = ('{\n  "other": {"orchestrator": {"codex": "gpt-1-sol"}},\n'
             '  "tiers": {\n'
             '    "orchestrator":{"claude": "opus",   "codex": "gpt-5.6-sol"}\n'
             '  }\n}\n')
    routing.write_text(decoy)
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert routing.read_text() == decoy.replace('"codex": "gpt-5.6-sol"', '"codex": "gpt-6.1-sol"')


# ---- audit additions (failure paths and guards) ----

def test_set_mode_refuses_to_overwrite_corrupt_or_non_object_settings(tmp_path):
    # Data-loss guard: a corrupt or non-object settings file must survive untouched.
    settings, _ = _paths(tmp_path)
    for text in ("{not json", "[1, 2]"):
        settings.write_text(text)
        with raises(ValueError, match="not overwritten"):
            model_sync.set_mode(settings, "auto")
        assert settings.read_text() == text


def test_set_mode_keeps_other_keys(tmp_path):
    settings, _ = _paths(tmp_path)
    settings.write_text('{"other": 7, "model_updates": "approve"}')
    model_sync.set_mode(settings, "auto")
    assert json.loads(settings.read_text()) == {"other": 7, "model_updates": "auto"}


def test_load_mode_non_object_json_is_approve(tmp_path):
    settings, _ = _paths(tmp_path)
    settings.write_text('["auto"]')
    assert model_sync.load_mode(settings) == "approve"


def test_existing_models_entry_for_new_slug_is_not_overwritten(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    data = json.loads(models.read_text())
    data["models"]["gpt-6.1-sol"] = dict(_entry("orchestrator"), status="unprobed", marker=1)
    models.write_text(json.dumps(data, indent=2))
    lines = model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert json.loads(models.read_text())["models"]["gpt-6.1-sol"]["marker"] == 1
    assert not any(l.startswith("models: added") for l in lines)


def test_missing_tier_line_is_reported_and_routing_untouched(tmp_path):
    # tiers parse as JSON, but the orchestrator codex value is on a different line than its key,
    # so the single-line text edit cannot match; the sync must skip, not corrupt the file.
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    odd = ('{\n  "tiers": {\n    "orchestrator": {"claude": "opus",\n'
           '                     "codex": "gpt-5.6-sol"}\n  }\n}\n')
    routing.write_text(odd)
    lines = model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert any("routing line for tier orchestrator not found" in l for l in lines)
    assert routing.read_text() == odd
    assert "gpt-6.1-sol" not in json.loads(models.read_text())["models"]


def test_heal_without_donor_warns_and_adds_nothing(tmp_path):
    cache, routing, models = _setup(tmp_path, [])
    routing.write_text(ROUTING.replace("gpt-5.6-sol", "gpt-7-sol"))
    data = json.loads(models.read_text())
    del data["models"]["gpt-5.6-sol"]
    models.write_text(json.dumps(data, indent=2))
    before = models.read_text()
    lines = model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert lines == ["WARN: no codex donor in tier orchestrator for gpt-7-sol, gpt-7-sol not added to models.json"]
    assert models.read_text() == before


def test_heal_clones_highest_version_donor(tmp_path):
    cache, routing, models = _setup(tmp_path, [])
    routing.write_text(ROUTING.replace("gpt-5.6-sol", "gpt-7-sol"))
    data = json.loads(models.read_text())
    data["models"]["gpt-5.6-sol"]["marker"] = "old"
    data["models"]["gpt-6.1-sol"] = dict(_entry("orchestrator"), marker="new")
    models.write_text(json.dumps(data, indent=2))
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert json.loads(models.read_text())["models"]["gpt-7-sol"]["marker"] == "new"


def test_malformed_cache_entries_are_skipped(tmp_path):
    cache, routing, models = _setup(tmp_path, [])
    cache.write_text(json.dumps({"client_version": INSTALLED, "models": ["gpt-9-sol", {"slug": 9}, {"no_slug": 1},
                                 {"slug": "gpt-6.1-sol", "visibility": "list", "supported_in_api": True}]}))
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert '"codex": "gpt-6.1-sol"' in routing.read_text()


def test_apply_preserves_file_mode(tmp_path):
    import os
    import stat
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    os.chmod(routing, 0o640)
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert stat.S_IMODE(os.stat(routing).st_mode) == 0o640
    assert "gpt-6.1-sol" in routing.read_text()


def _main(tmp_path, *extra):
    settings, pending = _paths(tmp_path)
    from unittest import mock
    from agents_inc.install import host_cli
    with mock.patch.object(host_cli, "installed_version", return_value=INSTALLED):
        return model_sync.main(["--settings", str(settings), "--pending", str(pending), *extra])


def test_main_missing_cache_exits_2(tmp_path, capsys):
    _, routing, models = _setup(tmp_path, [])
    rc = _main(tmp_path, "--cache", str(tmp_path / "nope.json"), "--routing", str(routing), "--models", str(models))
    assert rc == 2
    assert "codex cache missing" in capsys.readouterr().err


def test_main_set_mode_on_corrupt_settings_exits_2(tmp_path, capsys):
    settings, _ = _paths(tmp_path)
    settings.write_text("{bad")
    assert _main(tmp_path, "--set-mode", "auto") == 2
    assert settings.read_text() == "{bad"
    assert "not overwritten" in capsys.readouterr().err


def test_main_dry_run_writes_nothing_and_does_not_regen(tmp_path, monkeypatch, capsys):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    monkeypatch.setattr(model_sync, "_regen_tables", lambda: (_ for _ in ()).throw(AssertionError("regen on dry run")))
    before = (routing.read_text(), models.read_text())
    rc = _main(tmp_path, "--cache", str(cache), "--routing", str(routing), "--models", str(models))
    assert rc == 0
    assert (routing.read_text(), models.read_text()) == before
    out = capsys.readouterr().out
    assert "[dry-run]" in out and "changes applied" not in out


def test_main_apply_regen_failure_exits_1(tmp_path, monkeypatch):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    monkeypatch.setattr(model_sync, "_regen_tables", lambda: 1)
    rc = _main(tmp_path, "--apply", "--cache", str(cache), "--routing", str(routing), "--models", str(models))
    assert rc == 1
    assert "gpt-6.1-sol" in routing.read_text()


# ---- round 2: untested CLI paths ----

def test_main_openrouter_failure_is_reported_not_fatal(tmp_path, monkeypatch, capsys):
    from agents_inc import catalog_refresh

    def boom(**_):
        raise RuntimeError("catalog fetch down")
    monkeypatch.setattr(catalog_refresh, "refresh", boom)
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    before = routing.read_text()
    rc = _main(tmp_path, "--openrouter", "--cache", str(cache), "--routing", str(routing), "--models", str(models))
    assert rc == 0
    err = capsys.readouterr().err
    assert "openrouter skipped: catalog fetch down" in err
    assert routing.read_text() == before  # dry run still writes nothing


def test_main_approve_skip_tables_applies_without_regen(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(model_sync, "_regen_tables", lambda: (_ for _ in ()).throw(AssertionError("regen despite --skip-tables")))
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    _, pending = _paths(tmp_path)
    pending.write_text('{"lines": ["x"]}')
    rc = _main(tmp_path, "--approve", "--skip-tables", "--cache", str(cache), "--routing", str(routing), "--models", str(models))
    assert rc == 0
    assert '"codex": "gpt-6.1-sol"' in routing.read_text()
    assert not pending.exists()
    assert "model_sync: changes applied" in capsys.readouterr().out


# ---- round 3 ----

def test_main_get_mode_prints_setting_without_touching_files(tmp_path, capsys):
    settings, pending = _paths(tmp_path)
    assert _main(tmp_path, "--get-mode") == 0
    assert capsys.readouterr().out.strip() == "approve"
    assert not settings.exists() and not pending.exists()
    settings.write_text('{"model_updates": "auto"}')
    assert _main(tmp_path, "--get-mode") == 0
    assert capsys.readouterr().out.strip() == "auto"


def test_apply_keeps_models_json_format_and_only_adds_lines(tmp_path):
    # models.json has one format (models_cmd._dump: arrays inline). An apply must add the
    # cloned entry and leave every existing line as it was (only a trailing comma may be added).
    import difflib
    from agents_inc.install.models_cmd import _dump
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    data = json.loads(models.read_text())
    for entry in data["models"].values():
        entry["tasks_good"] = ["extract", "summarize"]
    models.write_text(_dump(data) + "\n")
    before = models.read_text().splitlines()
    model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    after = models.read_text().splitlines()
    removed = [l[2:] for l in difflib.ndiff(before, after) if l.startswith("- ")]
    added = [l[2:] for l in difflib.ndiff(before, after) if l.startswith("+ ")]
    assert all(r + "," in added for r in removed), removed
    assert '    "gpt-6.1-sol": {' in added
    assert '      "tasks_good": ["extract", "summarize"]' in added  # array stays inline
    assert len(added) - len(removed) == len(_dump(data["models"]["gpt-5.6-sol"], 4).splitlines())


# ---- round 4: manual pins survive auto sync ----

def test_pinned_persona_not_promoted_or_cloned(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol", "gpt-6-luna"])
    lines = model_sync.sync_codex(cache, routing, models, apply=True, pinned=["sol"], installed=INSTALLED)
    text = routing.read_text()
    assert '"codex": "gpt-5.6-sol"' in text and '"codex": "gpt-6-luna"' in text  # sol held, luna promoted
    assert "codex sol: pinned, skipped" in lines
    assert "gpt-6.1-sol" not in json.loads(models.read_text())["models"]


def test_pinned_persona_heal_still_runs(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-9-sol"])
    routing.write_text(ROUTING.replace("gpt-5.6-sol", "gpt-7-sol"))
    model_sync.sync_codex(cache, routing, models, apply=True, pinned=["sol"], installed=INSTALLED)
    assert '"codex": "gpt-7-sol"' in routing.read_text()
    assert json.loads(models.read_text())["models"]["gpt-7-sol"]["tier"] == "orchestrator"


def test_scheduled_with_only_pinned_updates_is_none(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    settings, pending = _paths(tmp_path)
    settings.write_text('{"model_updates": "auto", "pinned": ["sol"]}')
    before = (routing.read_text(), models.read_text())
    status, _ = model_sync.run_scheduled(cache, routing, models, settings, pending, installed=INSTALLED)
    assert status == "none"
    assert (routing.read_text(), models.read_text()) == before and not pending.exists()


def test_main_apply_honours_pinned_from_settings(tmp_path, capsys):
    cache, routing, models = _setup(tmp_path, ["gpt-6.1-sol"])
    settings, _ = _paths(tmp_path)
    settings.write_text('{"pinned": ["sol"]}')
    rc = _main(tmp_path, "--apply", "--skip-tables", "--cache", str(cache), "--routing", str(routing), "--models", str(models))
    assert rc == 0 and routing.read_text() == ROUTING
    assert "codex sol: pinned, skipped" in capsys.readouterr().out


def test_set_pinned_keeps_keys_rejects_bad_persona_and_corrupt_file(tmp_path):
    settings, _ = _paths(tmp_path)
    settings.write_text('{"model_updates": "auto"}')
    model_sync.set_pinned(settings, "sol", True)
    model_sync.set_pinned(settings, "sol", True)  # idempotent
    assert json.loads(settings.read_text()) == {"model_updates": "auto", "pinned": ["sol"]}
    assert model_sync.load_pinned(settings) == ["sol"] and model_sync.load_mode(settings) == "auto"
    with raises(ValueError):
        model_sync.set_pinned(settings, "nova", True)
    settings.write_text("{bad")
    with raises(ValueError, match="not overwritten"):
        model_sync.set_pinned(settings, "sol", True)
    assert settings.read_text() == "{bad"


def load_tests(loader, tests, pattern):
    """Expose the module-level test_ functions to `unittest discover` (see _free012.suite)."""
    return suite(globals())


# ---- spec 047: trust the cache only when written by the installed codex ----

def test_foreign_cache_skips_promotion_with_one_line(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.2-sol"])
    data = json.loads(cache.read_text()); data["client_version"] = "0.170.0"; cache.write_text(json.dumps(data))
    before = routing.read_text(), models.read_text()
    lines = model_sync.sync_codex(cache, routing, models, apply=True, installed="0.159.2")
    assert lines == ["model_sync: skipped, models_cache.json from codex 0.170.0, installed 0.159.2"]
    assert (routing.read_text(), models.read_text()) == before
    assert not model_sync._has_changes(lines)


def test_matching_cache_still_promotes(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.2-sol"])
    data = json.loads(cache.read_text()); data["client_version"] = "0.170.0"; cache.write_text(json.dumps(data))
    model_sync.sync_codex(cache, routing, models, apply=True, installed="0.170.0")
    assert '"codex": "gpt-6.2-sol"' in routing.read_text()


def test_never_promotes_to_hidden_or_unsupported_slug(tmp_path):
    cache, routing, models = _setup(tmp_path, [])
    cache.write_text(json.dumps({"client_version": "0.1.0", "models": [
        {"slug": "gpt-9-sol", "visibility": "hide", "supported_in_api": True},
        {"slug": "gpt-8-sol", "visibility": "list", "supported_in_api": False}]}))
    assert model_sync.sync_codex(cache, routing, models, apply=True, installed="0.1.0") == []
    assert '"codex": "gpt-5.6-sol"' in routing.read_text()


def _foreign(tmp_path):
    cache, routing, models = _setup(tmp_path, ["gpt-6.2-sol"])
    data = json.loads(cache.read_text()); data["client_version"] = "0.170.0"; cache.write_text(json.dumps(data))
    pending = tmp_path / "pending.json"; pending.write_text('{"lines": ["codex sol: x -> y [dry-run]"]}')
    return cache, routing, models, pending


def test_approve_on_foreign_cache_keeps_pending(tmp_path):  # G2
    cache, routing, models, pending = _foreign(tmp_path)
    lines = model_sync.approve_pending(cache, routing, models, pending, installed="0.159.2")
    assert lines[0].startswith("model_sync: skipped,")
    assert pending.exists()


def test_scheduled_on_foreign_cache_keeps_pending(tmp_path):  # G2
    cache, routing, models, pending = _foreign(tmp_path)
    status, lines = model_sync.run_scheduled(cache, routing, models, tmp_path / "settings.json", pending, installed="0.159.2")
    assert status == "skipped" and pending.exists()


def test_cli_approve_on_foreign_cache_exits_nonzero(tmp_path):  # G2
    from unittest import mock
    from agents_inc.install import host_cli
    cache, routing, models, pending = _foreign(tmp_path)
    with mock.patch.object(host_cli, "installed_version", return_value="0.159.2"):
        rc = model_sync.main(["--approve", "--cache", str(cache), "--routing", str(routing), "--models", str(models),
                              "--pending", str(pending), "--settings", str(tmp_path / "settings.json"), "--skip-tables"])
    assert rc != 0 and pending.exists()


def test_unknown_trust_skips_promotion(tmp_path):  # H1: promotion needs a matching catalog
    cache, routing, models = _setup(tmp_path, ["gpt-6.2-sol"])
    before = routing.read_text()
    lines = model_sync.sync_codex(cache, routing, models, apply=True, installed=None)
    assert lines and lines[0].startswith("model_sync: skipped,") and "codex version unknown" in lines[0]
    data = json.loads(cache.read_text()); data.pop("client_version"); cache.write_text(json.dumps(data))
    lines = model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED)
    assert lines and "catalog version unknown" in lines[0]
    assert routing.read_text() == before


def test_entry_without_eligibility_fields_is_not_promoted(tmp_path):  # H3: same explicit rule as catalog.newest
    cache, routing, models = _setup(tmp_path, [])
    cache.write_text(json.dumps({"client_version": INSTALLED, "models": [{"slug": "gpt-9-sol"}]}))
    assert model_sync.sync_codex(cache, routing, models, apply=True, installed=INSTALLED) == []
