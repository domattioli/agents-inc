"""Tests for free-first router behavior (spec 012 T018, T021)."""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tests._free012 import fixture, hermetic, parametrize, suite  # noqa: F401


@fixture
def mistral_ok(monkeypatch):
    """Patch mistral-small-latest to be available for extract/summarize/classify."""
    from agents_inc import router
    mistral_entry = {
        "vendor": "mistral",
        "provider": "mistral",
        "tier": "grunt",
        "tasks_good": ["extract", "summarize", "classify"],
        "tasks_bad": [],
        "ctx_hint": 32000,
        "cost_class": "free",
        "status": "available",
    }
    monkeypatch.setitem(router._CATALOG, "mistral-small-latest", mistral_entry)
    return mistral_entry


class TestRouterGoldenIdeal:
    """Test T018: golden-chain equality in ideal modality."""

    @fixture
    def golden_data(self):
        """Load golden chains from fixture."""
        golden_path = Path(__file__).parent / "fixtures" / "012" / "router_golden.json"
        with open(golden_path) as f:
            return json.load(f)

    def _normalize_chain_for_gemini(self, chain):
        """Normalize known substitutions: gemini-2.5-flash -> gemini-flash-lite-latest."""
        normalized = []
        for provider, model, tier, cmd in chain:
            if provider == "gemini" and model in ["gemini-flash", "gemini-2.5-flash"]:
                model = "gemini-flash-lite-latest"
            normalized.append([provider, model, tier, cmd])
        return normalized

    def _remove_stale_ids(self, chain):
        """Remove stale IDs from chain."""
        stale = {
            "minimax/minimax-m3:free",
            "minimax/minimax-m2.7:free",
            "inclusionai/ling-3.0-flash-fin:free",
            "inclusionai/ling-3.0-flash-sante:free",
            "poolside/laguna-s-2.1:free",
            "poolside/laguna-xs-2.1:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "thinkingmachines/inkling-small:free",
            "thinkingmachines/inkling:free",
            "z-ai/glm-5.2:free",
            "nvidia/nemotron-3.5-content-safety:free",
            "google/lyria-3-pro-preview",
            "google/lyria-3-clip-preview",
            "openrouter/free",
        }
        # Golden predates ministral-3b-latest becoming the available mistral grunt route.
        return [[p, m, t, c] for p, m, t, c in chain if m not in stale and p != "mistral"]

    def _pin_codex(self, chain):
        """Golden predates the codex pin bumps; expect today's routing.json codex pin for each row's tier."""
        tiers = json.loads((Path(__file__).resolve().parents[1] / "agents_inc" / "routing.json").read_text())["tiers"]
        return [[p, tiers[t]["codex"] if p == "codex" else m, t, c] for p, m, t, c in chain]

    def _is_new_task(self, task):
        """Check if task is newly added (classify)."""
        return task == "classify"

    def test_ideal_modality_matches_golden(self, golden_data, monkeypatch):
        """AGENTS_INC_MODALITY unset: chains match golden (with allowed diffs)."""
        from agents_inc import router

        # Ensure ideal modality (default); monkeypatch restores any prior value
        monkeypatch.delenv("AGENTS_INC_MODALITY", raising=False)

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        for chain_key, expected_chain in golden_data["chains"].items():
            task, tier, auth_str = chain_key.split("|")
            workspace_authorized = auth_str == "True"

            # Skip new tasks (classify didn't exist pre-change)
            if self._is_new_task(task):
                continue

            # Get current chain
            current_chain = list(router.pick_model_chain(
                task=task,
                tier=tier,
                available=all_providers,
                workspace_authorized=workspace_authorized,
            ))
            # Convert Route objects to lists
            current_chain = [[r.provider, r.model, r.tier, r.cmd_kind] for r in current_chain]

            # Apply normalizations
            expected_normalized = self._normalize_chain_for_gemini(self._pin_codex(expected_chain))
            expected_normalized = self._remove_stale_ids(expected_normalized)
            current_normalized = self._normalize_chain_for_gemini(current_chain)
            current_normalized = self._remove_stale_ids(current_normalized)

            assert current_normalized == expected_normalized, \
                f"Chain mismatch for {chain_key}: expected {expected_normalized}, got {current_normalized}"

    def test_disallowed_tasks_unchanged(self, golden_data, monkeypatch):
        """Disallowed tasks (draft, review, code) chain equals golden in ideal."""
        from agents_inc import router

        monkeypatch.delenv("AGENTS_INC_MODALITY", raising=False)

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}
        disallowed_tasks = {"draft", "review", "code"}

        for task in disallowed_tasks:
            for tier in ["grunt", "workhorse", "orchestrator", "executive"]:
                chain_key = f"{task}|{tier}|True"
                if chain_key not in golden_data["chains"]:
                    continue

                expected_chain = golden_data["chains"][chain_key]
                current_chain = list(router.pick_model_chain(
                    task=task,
                    tier=tier,
                    available=all_providers,
                    workspace_authorized=True,
                ))
                current_chain = [[r.provider, r.model, r.tier, r.cmd_kind] for r in current_chain]

                # For disallowed tasks, should be unchanged
                expected_normalized = self._remove_stale_ids(self._pin_codex(expected_chain))
                current_normalized = self._remove_stale_ids(current_chain)

                assert current_normalized == expected_normalized, \
                    f"Disallowed task {chain_key} should be unchanged"


class TestRouterBudgetModality:
    """Test T018: budget modality with free-first ordering."""

    def test_budget_modality_free_first_for_allowed_tasks(self, monkeypatch, mistral_ok):
        """Budget modality: allowed grunt tasks list free providers first."""
        from agents_inc import router

        monkeypatch.setenv("AGENTS_INC_MODALITY", "budget")
        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        for task in ["extract", "summarize", "classify"]:
            chain = list(router.pick_model_chain(
                task=task,
                tier="grunt",
                available=all_providers,
                workspace_authorized=True,
            ))

            # Sanity: mistral should be available for these tasks
            assert any(r.provider == "mistral" for r in chain), \
                f"Task {task}: sanity check failed, mistral not in chain"

            # First element should be from free providers
            if chain:
                first_provider = chain[0].provider
                free_order = ["mistral", "gemini", "openrouter"]
                assert first_provider in free_order, \
                    f"Task {task}: first provider {first_provider} not in free_order {free_order}"

    def test_budget_modality_free_order_mistral_gemini_openrouter(self, monkeypatch, mistral_ok):
        """Budget modality: free provider order is Mistral, Gemini, OpenRouter (first route is mistral)."""
        from agents_inc import router

        monkeypatch.setenv("AGENTS_INC_MODALITY", "budget")
        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity check: mistral should be in chain before we set up cooldown
        chain = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain]
        assert "mistral" in providers_before, f"Sanity check failed: mistral not in chain before setup: {providers_before}"

        # First provider should be mistral
        assert len(chain) > 0, "Chain should not be empty"
        assert chain[0].provider == "mistral", f"First route should be mistral, got {chain[0].provider}"

        # Get indices of first appearance of each free provider
        free_order = ["mistral", "gemini", "openrouter"]
        provider_indices = {}
        for i, route in enumerate(chain):
            if route.provider in free_order and route.provider not in provider_indices:
                provider_indices[route.provider] = i

        # All free-provider routes should precede first claude route
        claude_idx = next((i for i, r in enumerate(chain) if r.provider == "claude"), len(chain))
        for provider, idx in provider_indices.items():
            assert idx < claude_idx, f"{provider} route at {idx} should precede claude at {claude_idx}"

        # Verify order: first gemini appearance should be after mistral, openrouter after gemini
        if "mistral" in provider_indices and "gemini" in provider_indices:
            assert provider_indices["mistral"] < provider_indices["gemini"], \
                "Mistral should come before Gemini"
        if "gemini" in provider_indices and "openrouter" in provider_indices:
            assert provider_indices["gemini"] < provider_indices["openrouter"], \
                "Gemini should come before OpenRouter"

    def test_budget_modality_disallowed_tasks_unchanged(self, monkeypatch):
        """Budget modality: disallowed tasks (draft, review, code) unchanged."""
        from agents_inc import router

        monkeypatch.setenv("AGENTS_INC_MODALITY", "budget")
        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Delete modality to get ideal chain
        del os.environ["AGENTS_INC_MODALITY"]
        ideal_chain = list(router.pick_model_chain(
            task="draft",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        ideal_providers = [r.provider for r in ideal_chain]

        # Re-set budget modality
        os.environ["AGENTS_INC_MODALITY"] = "budget"
        budget_chain = list(router.pick_model_chain(
            task="draft",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        budget_providers = [r.provider for r in budget_chain]

        assert ideal_providers == budget_providers, \
            f"Disallowed task 'draft' changed in budget modality"


class TestRouterCooldowns:
    """Test T018: cooldown exclusion in routing."""

    def test_cooldown_excludes_provider_ideal_modality(self, monkeypatch):
        """Ideal modality: provider in cooldown is skipped (use gemini since mistral unavailable)."""
        from agents_inc import router, free_health

        # Ensure ideal modality
        if "AGENTS_INC_MODALITY" in os.environ:
            del os.environ["AGENTS_INC_MODALITY"]

        codex_dir = Path.home() / ".codex-bridge"
        codex_dir.mkdir(parents=True, exist_ok=True)

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity check: gemini should be in chain without health file
        chain_before = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain_before]
        assert "gemini" in providers_before, f"Sanity check failed: gemini not in chain before cooldown"

        # Set up health with gemini-flash-lite in cooldown
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        health_data = {
            "gemini-flash-lite": {
                "status": "degraded",
                "cooldown_until": future_time,
            }
        }
        (codex_dir / "backend-health.json").write_text(json.dumps(health_data))

        chain_after = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))

        # gemini should not appear in chain after cooldown
        providers_after = [r.provider for r in chain_after]
        assert "gemini" not in providers_after, f"Cooldown gemini still in chain: {providers_after}"

    def test_cooldown_excludes_provider_budget_modality(self, monkeypatch, mistral_ok):
        """Budget modality: provider in cooldown is skipped."""
        from agents_inc import router

        monkeypatch.setenv("AGENTS_INC_MODALITY", "budget")

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity check: mistral should be in chain before cooldown
        chain_before = list(router.pick_model_chain(
            task="summarize",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain_before]
        assert "mistral" in providers_before, f"Sanity check failed: mistral not in chain before cooldown"

        # Set up cooldown for mistral
        codex_dir = Path.home() / ".codex-bridge"
        codex_dir.mkdir(parents=True, exist_ok=True)

        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        health_data = {
            "mistral": {
                "status": "degraded",
                "cooldown_until": future_time,
            }
        }
        (codex_dir / "backend-health.json").write_text(json.dumps(health_data))

        chain_after = list(router.pick_model_chain(
            task="summarize",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))

        # mistral should not appear after cooldown
        providers_after = [r.provider for r in chain_after]
        assert "mistral" not in providers_after, f"Cooldown mistral still in chain: {providers_after}"

    def test_cooldown_gemini_flash_only_allows_flash_lite_tier_specific(self, monkeypatch):
        """Cooldown on gemini-flash only does not exclude gemini-flash-lite for grunt tier."""
        from agents_inc import router

        # Ideal modality
        if "AGENTS_INC_MODALITY" in os.environ:
            del os.environ["AGENTS_INC_MODALITY"]

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity: gemini should be in chain before cooldown
        chain_before = list(router.pick_model_chain(
            task="summarize",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain_before]
        assert "gemini" in providers_before, f"Sanity check failed: gemini not in chain before cooldown"

        # Set cooldown only on gemini-flash (not gemini-flash-lite)
        codex_dir = Path.home() / ".codex-bridge"
        codex_dir.mkdir(parents=True, exist_ok=True)

        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        health_data = {
            "gemini-flash": {
                "status": "degraded",
                "cooldown_until": future_time,
            }
        }
        (codex_dir / "backend-health.json").write_text(json.dumps(health_data))

        chain_after = list(router.pick_model_chain(
            task="summarize",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))

        # For grunt tier, configured model is gemini-flash-lite-latest, so gemini should still be included
        providers_after = [r.provider for r in chain_after]
        assert "gemini" in providers_after, f"Gemini (flash-lite for grunt) should not be excluded when only gemini-flash cooled: {providers_after}"

    def test_cooldown_gemini_flash_lite_excludes_gemini_tier_specific(self, monkeypatch):
        """Cooldown on gemini-flash-lite excludes gemini for grunt tier."""
        from agents_inc import router

        # Ideal modality
        if "AGENTS_INC_MODALITY" in os.environ:
            del os.environ["AGENTS_INC_MODALITY"]

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity: gemini should be in chain before cooldown
        chain_before = list(router.pick_model_chain(
            task="summarize",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain_before]
        assert "gemini" in providers_before, f"Sanity check failed: gemini not in chain before cooldown"

        # Set cooldown on gemini-flash-lite (the configured model for grunt tier)
        codex_dir = Path.home() / ".codex-bridge"
        codex_dir.mkdir(parents=True, exist_ok=True)

        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        health_data = {
            "gemini-flash-lite": {
                "status": "degraded",
                "cooldown_until": future_time,
            }
        }
        (codex_dir / "backend-health.json").write_text(json.dumps(health_data))

        chain_after = list(router.pick_model_chain(
            task="summarize",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))

        # gemini should be excluded when gemini-flash-lite (configured for grunt) is cooled
        providers_after = [r.provider for r in chain_after]
        assert "gemini" not in providers_after, f"Gemini should be excluded when gemini-flash-lite (configured for grunt) is cooled: {providers_after}"


class TestRouterCaps:
    """Test T018: daily cap exclusion in routing."""

    def test_cap_excludes_provider_ideal_modality(self, monkeypatch):
        """Ideal modality: provider at cap is skipped."""
        from agents_inc import router, free_caps
        import sqlite3

        if "AGENTS_INC_MODALITY" in os.environ:
            del os.environ["AGENTS_INC_MODALITY"]

        # Set up usage at cap
        codex_dir = Path.home() / ".codex-bridge"
        codex_dir.mkdir(parents=True, exist_ok=True)

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity check: openrouter should be in chain before cap
        chain_before = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain_before]
        assert "openrouter" in providers_before, f"Sanity check failed: openrouter not in chain before cap"

        db_path = codex_dir / "usage.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage(
                uid TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                day TEXT NOT NULL,
                backend TEXT NOT NULL,
                model TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read INTEGER DEFAULT 0,
                cache_write INTEGER DEFAULT 0,
                reasoning INTEGER DEFAULT 0
            )
        """)

        today = datetime.now(timezone.utc).date().isoformat()
        # 50 calls for openrouter (at cap)
        for i in range(50):
            conn.execute(
                "INSERT INTO usage (uid, ts, day, backend, model) VALUES (?, ?, ?, ?, ?)",
                (f"uid-{i}", datetime.now(timezone.utc).isoformat(), today, "openrouter", "model-x"),
            )
        conn.commit()
        conn.close()

        # Verify cap is actually at limit
        assert free_caps.at_cap("openrouter", db_path=str(db_path)), "Setup failed: openrouter not at cap"

        chain_after = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))

        # openrouter should not appear after cap
        providers_after = [r.provider for r in chain_after]
        assert "openrouter" not in providers_after, f"At-cap openrouter still in chain: {providers_after}"

    def test_cap_excludes_provider_budget_modality(self, monkeypatch, mistral_ok):
        """Budget modality: provider at cap is skipped."""
        from agents_inc import router, free_caps
        import sqlite3

        monkeypatch.setenv("AGENTS_INC_MODALITY", "budget")

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity check: mistral should be in chain before cap
        chain_before = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain_before]
        assert "mistral" in providers_before, f"Sanity check failed: mistral not in chain before cap"

        # Set up usage at cap for mistral
        codex_dir = Path.home() / ".codex-bridge"
        codex_dir.mkdir(parents=True, exist_ok=True)

        db_path = codex_dir / "usage.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage(
                uid TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                day TEXT NOT NULL,
                backend TEXT NOT NULL,
                model TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read INTEGER DEFAULT 0,
                cache_write INTEGER DEFAULT 0,
                reasoning INTEGER DEFAULT 0
            )
        """)

        today = datetime.now(timezone.utc).date().isoformat()
        # 500 calls for mistral (at cap)
        for i in range(500):
            conn.execute(
                "INSERT INTO usage (uid, ts, day, backend, model) VALUES (?, ?, ?, ?, ?)",
                (f"uid-{i}", datetime.now(timezone.utc).isoformat(), today, "mistral", "model-x"),
            )
        conn.commit()
        conn.close()

        # Verify cap is actually at limit
        assert free_caps.at_cap("mistral", db_path=str(db_path)), "Setup failed: mistral not at cap"

        chain_after = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))

        # mistral should not appear in budget mode when at cap
        providers_after = [r.provider for r in chain_after]
        assert "mistral" not in providers_after, f"At-cap mistral still in chain: {providers_after}"

    def test_all_free_cooled_capped_falls_back_to_paid(self, monkeypatch, mistral_ok):
        """All free cooled/capped -> paid providers come first; NO free providers in chain."""
        from agents_inc import router
        import sqlite3

        monkeypatch.setenv("AGENTS_INC_MODALITY", "budget")

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        # Sanity check: free providers should be in chain before setup
        chain_before = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))
        providers_before = [r.provider for r in chain_before]
        free_providers_set = {"mistral", "gemini", "openrouter"}
        assert any(p in free_providers_set for p in providers_before), \
            f"Sanity check failed: no free providers in chain before exclusion"

        # Set up cooldowns and caps for all free
        codex_dir = Path.home() / ".codex-bridge"
        codex_dir.mkdir(parents=True, exist_ok=True)

        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        health_data = {
            "mistral": {"status": "degraded", "cooldown_until": future_time},
            "gemini": {"status": "degraded", "cooldown_until": future_time},
        }
        (codex_dir / "backend-health.json").write_text(json.dumps(health_data))

        # openrouter at cap
        db_path = codex_dir / "usage.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage(
                uid TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                day TEXT NOT NULL,
                backend TEXT NOT NULL,
                model TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read INTEGER DEFAULT 0,
                cache_write INTEGER DEFAULT 0,
                reasoning INTEGER DEFAULT 0
            )
        """)

        today = datetime.now(timezone.utc).date().isoformat()
        for i in range(50):
            conn.execute(
                "INSERT INTO usage (uid, ts, day, backend, model) VALUES (?, ?, ?, ?, ?)",
                (f"uid-{i}", datetime.now(timezone.utc).isoformat(), today, "openrouter", "model-x"),
            )
        conn.commit()
        conn.close()

        chain = list(router.pick_model_chain(
            task="extract",
            tier="grunt",
            available=all_providers,
            workspace_authorized=True,
        ))

        # Should get paid providers first
        assert len(chain) > 0
        first = chain[0]
        assert first.provider in ["claude", "codex"], \
            f"All free excluded, expected paid first, got {first.provider}"

        # NO free providers should appear when all cooled/capped
        providers = [r.provider for r in chain]
        assert not any(p in free_providers_set for p in providers), \
            f"All free should be excluded but found: {[p for p in providers if p in free_providers_set]}"


class TestBadTaskRefused:
    """Spec 037 T023/T024: a catalog entry that lists the task as bad is never picked and is refused by dispatch."""

    def test_router_skips_bad_task_entry(self, monkeypatch):
        from agents_inc import router

        catalog = {"codestral-latest": {"provider": "mistral", "status": "available", "tasks_good": ["summarize"],
                                        "tasks_bad": []}}
        monkeypatch.setattr(router, "_CATALOG", catalog)
        assert router._eligible("codestral-latest", "summarize")
        catalog["codestral-latest"]["tasks_bad"] = ["summarize"]
        assert not router._eligible("codestral-latest", "summarize")
        assert router._eligible("codestral-latest", "extract")

    def test_dispatch_pre_checks_refuse_bad_task_entry(self, tmp_path, monkeypatch):
        from agents_inc.install import free_launch

        catalog = tmp_path / "models.json"
        catalog.write_text(json.dumps({"models": {"codestral-latest": {"tasks_bad": ["extract"]}}}))
        monkeypatch.setattr(free_launch, "MODELS_PATH", catalog)
        routing = {"optional_allowed_tasks": ["extract", "summarize"]}
        slots = {"TASK_KIND": "extract", "CLASSIFICATION": "public (x)"}
        refusal = free_launch.pre_checks(slots, None, routing, model="codestral-latest")
        assert refusal == "refused-task" and "bad task" in refusal.detail
        assert free_launch.pre_checks(slots, None, routing, model="ministral-3b-latest") is None
        assert free_launch.pre_checks({**slots, "TASK_KIND": "summarize"}, None, routing, model="codestral-latest") is None


class TestRouterGuards:
    """Test T021: guard tests for ZDR, free models, code tasks."""

    def test_no_zdr_disabled_in_code(self):
        """Guard: no code path disables ZDR."""
        import re

        # Pure-Python scan (was host grep: a grep error, exit 2, passed silently).
        pattern = re.compile(r'"zdr"\s*:\s*false|"data_collection".*false|"allow".*false')
        root = Path(__file__).resolve().parent.parent
        files = [f for d in (root / "agents_inc", root / "skills/codex-bridge/scripts")
                 for f in sorted(d.rglob("*")) if f.is_file() and "__pycache__" not in f.parts]
        assert len(files) > 10, "scan found too few files; wrong root?"
        hits = [f"{f}:{n}: {line.strip()}" for f in files
                for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1)
                if pattern.search(line)]
        assert not hits, "Found ZDR-disabling patterns:\n" + "\n".join(hits)

    def test_openrouter_routes_all_free_models(self):
        """Guard: every OpenRouter route has model ending in ':free'."""
        from agents_inc import router

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}

        for task in ["extract", "summarize", "classify", "draft", "review", "adjudicate", "code"]:
            for tier in ["grunt", "workhorse", "orchestrator", "executive"]:
                chain = list(router.pick_model_chain(
                    task=task,
                    tier=tier,
                    available=all_providers,
                    workspace_authorized=True,
                ))

                for route in chain:
                    if route.provider == "openrouter":
                        assert route.model.endswith(":free"), \
                            f"Task {task}, tier {tier}: OpenRouter model {route.model} doesn't end with :free"

    def test_code_tasks_no_free_providers(self):
        """Guard: code-type tasks never route to free providers."""
        from agents_inc import router

        all_providers = {"claude", "codex", "gemini", "mistral", "openrouter"}
        free_providers = {"gemini", "mistral", "openrouter"}

        for task in ["code", "code-write"]:
            for tier in ["grunt", "workhorse"]:
                for auth in [True, False]:
                    chain = list(router.pick_model_chain(
                        task=task,
                        tier=tier,
                        available=all_providers,
                        workspace_authorized=auth,
                    ))

                    for route in chain:
                        assert route.provider not in free_providers, \
                            f"Task {task}, tier {tier}, auth {auth}: free provider {route.provider} in chain"


def load_tests(loader, tests, pattern):
    """Expose this fixture-style file to `unittest discover` (see _free012.suite)."""
    return suite(globals(), autouse=("hermetic",))
