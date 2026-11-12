import unittest
from unittest import mock
from agents_inc.router import pick_model, pick_model_chain, Route, _TABLE

class RouterTest(unittest.TestCase):
    def test_cheap_extract_prefers_required_provider(self):
        r = pick_model("extract", "grunt", {"claude", "codex"}, workspace_authorized=False)
        self.assertEqual((r.provider, r.model, r.tier), ("claude", "haiku", "grunt"))

    def test_optional_provider_denied_without_authorization(self):
        r = pick_model("extract", "grunt", {"gemini"}, workspace_authorized=False)
        self.assertIsNone(r)

    def test_optional_provider_allowed_with_authorization(self):
        r = pick_model("extract", "grunt", {"gemini"}, workspace_authorized=True)
        self.assertEqual(r.provider, "gemini")

    def test_review_uses_other_vendor(self):
        r = pick_model("review", "workhorse", {"claude", "codex"}, workspace_authorized=False, exclude_provider="claude")
        self.assertEqual(r.provider, "codex")

    def test_unknown_tier_none(self):
        self.assertIsNone(pick_model("extract", "platinum", {"claude"}, workspace_authorized=False))

    def test_prefer_provider(self):
        # No user roster: the operator's ~/.config/agents-inc/roster.json must not decide the result (CI has none).
        with mock.patch("agents_inc.install.runtime.load_model_map", return_value={}):
            r = pick_model("extract", "grunt", {"claude", "codex"}, workspace_authorized=False, prefer_provider="codex")
        self.assertEqual(r.provider, "codex")
        # gpt-5.4-mini deliberately removed from the required-provider "codex"
        # grunt slot: per D27/CONTEXT.md "Free grunt", it must never be a Codex
        # subscription call. grunt/codex now resolves to the real ladder pair
        # (haiku<->luna), matching docs/governance/ROUTING-RANKING.md.
        self.assertEqual(r.model, _TABLE["tiers"]["grunt"]["codex"])
        self.assertIn("luna", r.model)

    def test_catalog_routes_available_mistral(self):
        r = pick_model("extract", "grunt", {"mistral"}, True)
        self.assertEqual(r.model, "ministral-3b-latest")

    def test_openrouter_named_chain_with_auto_last(self):
        chain = pick_model_chain("extract", "grunt", {"openrouter"}, True)
        self.assertGreater(len(chain), 2)
        self.assertNotEqual(chain[0].model, "openrouter/auto:free")
        self.assertEqual(chain[-1].model, "openrouter/auto:free")
        self.assertEqual(len({r.model for r in chain}), len(chain))
        self.assertTrue(all(r.provider == "openrouter" for r in chain))

    def test_workhorse_codex_default_single_model(self):
        # Was test_mid_codex_default_then_quota_fallback: the old "mid" tier
        # wrongly bucketed luna (Grunt) and sol (Orchestrator) together as a
        # 2-model fallback chain -- the exact vocabulary bug this rename
        # fixes. workhorse/codex now correctly resolves to just terra
        # (sonnet<->terra, D27), with no cross-rung fallback mixing.
        chain = pick_model_chain("review", "workhorse", {"codex"}, False)
        self.assertEqual([r.model for r in chain], ["gpt-6.1-terra"])

    def test_routing_top_level_keys_unchanged(self):
        self.assertEqual(sorted(_TABLE), ["daily_caps", "free_order", "local", "optional", "optional_allowed_tasks",
            "optional_provider_wrappers", "required", "task_tier", "tiers"])

if __name__ == "__main__":
    unittest.main()
