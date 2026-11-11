import unittest
import json
import re
from pathlib import Path

# Models that are non-text (e.g., music generation) and legitimately have ctx_hint == 0
NON_TEXT_MODELS = {"google/lyria-3-pro-preview", "google/lyria-3-clip-preview"}


class TestModelsCatalog(unittest.TestCase):
    """Validate models.json catalog structure and completeness."""

    @classmethod
    def setUpClass(cls):
        """Load models.json and routing.json once for all tests."""
        base_dir = Path(__file__).parent.parent
        models_path = base_dir / "agents_inc" / "models.json"
        routing_path = base_dir / "agents_inc" / "routing.json"
        doc_path = base_dir / "docs" / "free-openrouter-models.md"

        with open(models_path) as f:
            cls.models_data = json.load(f)
        with open(routing_path) as f:
            cls.routing_data = json.load(f)
        with open(doc_path) as f:
            cls.doc_text = f.read()

    def test_models_json_structure(self):
        """models.json parses; version nonempty str."""
        self.assertIsInstance(self.models_data, dict)
        self.assertIn("version", self.models_data)
        self.assertIsInstance(self.models_data["version"], str)
        self.assertGreater(len(self.models_data["version"]), 0)
        self.assertIn("models", self.models_data)
        self.assertIsInstance(self.models_data["models"], dict)

    def test_all_profiles_have_required_fields(self):
        """Every profile has all required fields with correct types."""
        required_fields = {
            "vendor": (str, type(None)),
            "provider": str,
            "tier": str,
            "tasks_good": list,
            "tasks_bad": list,
            "ctx_hint": int,
            "cost_class": str,
            "status": str,
        }
        for model_id, profile in self.models_data["models"].items():
            for field, expected_type in required_fields.items():
                self.assertIn(
                    field, profile, f"Model {model_id} missing field {field}"
                )
                if isinstance(expected_type, tuple):
                    self.assertIsInstance(
                        profile[field],
                        expected_type,
                        f"Model {model_id} field {field} has wrong type",
                    )
                else:
                    self.assertIsInstance(
                        profile[field],
                        expected_type,
                        f"Model {model_id} field {field} has wrong type",
                    )

    def test_cost_class_values(self):
        """cost_class must be one of allowed values."""
        allowed = {"free", "cheap", "mid", "premium", "local"}
        for model_id, profile in self.models_data["models"].items():
            self.assertIn(
                profile["cost_class"],
                allowed,
                f"Model {model_id} has invalid cost_class",
            )

    def test_vendor_provider_invariant(self):
        """Broker pass-through routes must not claim a vendor."""
        for model_id, profile in self.models_data["models"].items():
            # Rule 1: If provider is openrouter AND model_id starts with openrouter/,
            # then vendor must be None
            if profile["provider"] == "openrouter" and model_id.startswith("openrouter/"):
                self.assertIsNone(
                    profile["vendor"],
                    f"Model {model_id} has provider=openrouter and model_id starts with "
                    f"'openrouter/' but vendor is not None (got {profile['vendor']})",
                )
            # Rule 2: No profile may have vendor == "openrouter"
            self.assertNotEqual(
                profile["vendor"],
                "openrouter",
                f"Model {model_id} has vendor='openrouter'; vendors must be model makers, "
                f"not broker aliases",
            )

    def test_status_values(self):
        """status must be one of allowed values."""
        allowed = {"available", "unprobed", "unavailable"}
        for model_id, profile in self.models_data["models"].items():
            self.assertIn(
                profile["status"],
                allowed,
                f"Model {model_id} has invalid status",
            )

    def test_tier_values(self):
        """tier must be one of allowed values."""
        allowed = {"grunt", "workhorse", "orchestrator", "executive"}
        for model_id, profile in self.models_data["models"].items():
            self.assertIn(
                profile["tier"],
                allowed,
                f"Model {model_id} has invalid tier",
            )

    def test_task_vocabulary(self):
        """Every task string in tasks_good/tasks_bad is from allowed vocabulary."""
        allowed_tasks = {
            "extract",
            "summarize",
            "draft",
            "review-draft",
            "review-of-record",
            "code-write",
            "code-review",
            "orchestrate",
            "classify",
        }
        for model_id, profile in self.models_data["models"].items():
            for task in profile["tasks_good"]:
                self.assertIn(
                    task,
                    allowed_tasks,
                    f"Model {model_id} has invalid task_good: {task}",
                )
            for task in profile["tasks_bad"]:
                self.assertIn(
                    task,
                    allowed_tasks,
                    f"Model {model_id} has invalid task_bad: {task}",
                )

    def test_routing_json_models_in_catalog(self):
        """EVERY model string in routing.json is present in models.json."""
        routing_models = set()

        # Extract all model strings from tiers
        for tier_name, providers in self.routing_data["tiers"].items():
            for provider, configured in providers.items():
                model_ids = configured if isinstance(configured, list) else [configured]
                routing_models.update(model_ids)

        for model_id in routing_models:
            self.assertIn(
                model_id,
                self.models_data["models"],
                f"Model {model_id} from routing.json not in models.json",
            )

    def test_openrouter_models_in_catalog(self):
        """EVERY OpenRouter model id from doc is in models.json."""
        # Extract model IDs from doc headers
        # Format: ### N. <model_id>:free or ### N. <model_id>
        pattern = r"^### \d+\. ([a-z0-9/\-\.]+(?::free)?)"
        openrouter_models = []

        for match in re.finditer(pattern, self.doc_text, re.MULTILINE):
            model_id = match.group(1).strip()
            openrouter_models.append(model_id)

        # Expected 11 models in the doc
        self.assertGreaterEqual(
            len(openrouter_models),
            11,
            f"Found {len(openrouter_models)} models in doc, expected at least 11",
        )

        for model_id in openrouter_models:
            self.assertIn(
                model_id,
                self.models_data["models"],
                f"OpenRouter model {model_id} not in models.json",
            )

    def test_probe_2026_11_09(self):
        """T007 / FR-014: the catalog matches the 2026-11-09 probe and records its date."""
        self.assertEqual(self.models_data.get("probed"), "2026-11-09")
        models = self.models_data["models"]
        for slug in ("gemini-3.8-flash", "codestral-latest", "ministral-3b-latest"):
            self.assertIn(slug, models)
            self.assertEqual(models[slug]["status"], "available", slug)
        self.assertEqual(models["gemini-3.8-flash"]["provider"], "gemini")
        self.assertEqual(models["codestral-latest"]["provider"], "mistral")
        self.assertIn("nvidia/nemotron-3.5-lightning:free", models)
        self.assertNotIn("nemotron-3.5-lightning:free", models)  # full nvidia/ slug only

    def test_catalog_matches_free_dispatch_probe_list(self):
        """T024 / FR-014: every dispatchable free slug is an available catalog entry from the same provider and the grunt tier."""
        from agents_inc.install.free_launch import FREE_MODELS
        models = self.models_data["models"]
        for slug, entry in FREE_MODELS.items():
            with self.subTest(slug=slug):
                self.assertIn(slug, models)
                # OpenRouter slugs stay "unprobed" until the T030 live smoke records a probe; direct providers must be available
                ok = ("available", "unprobed") if entry.provider == "openrouter" else ("available",)
                self.assertIn(models[slug]["status"], ok)
                self.assertEqual(models[slug]["provider"], entry.provider)
                self.assertEqual(models[slug]["tier"], "grunt")
        for deep in ("gemini-3.1-pro-preview", "mistral-large-latest"):  # deep tiers never dispatch (SC-005)
            self.assertNotIn(deep, FREE_MODELS)
        for allowed in self.routing_data["optional_allowed_tasks"]:  # no free slug lists an allowed task in both columns
            for slug in FREE_MODELS:
                profile = models[slug]
                self.assertFalse(allowed in profile["tasks_good"] and allowed in profile["tasks_bad"], (slug, allowed))

    def test_no_key_like_strings(self):
        """No value in models.json matches key-like regex."""
        key_pattern = re.compile(r"sk-[A-Za-z0-9]|[A-Za-z0-9+/=]{32,}")

        def check_value(value, path):
            if isinstance(value, str):
                if key_pattern.search(value):
                    self.fail(
                        f"Found key-like string at {path}: {value[:50]}"
                    )
            elif isinstance(value, dict):
                for k, v in value.items():
                    check_value(v, f"{path}.{k}")
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    check_value(v, f"{path}[{i}]")

        check_value(self.models_data, "models.json")

    def test_ctx_hint_bounds(self):
        """ctx_hint must be >= 1000 for text models; 0 only for non-text models in allowlist."""
        for model_id, profile in self.models_data["models"].items():
            ctx = profile["ctx_hint"]
            if model_id in NON_TEXT_MODELS:
                self.assertEqual(
                    ctx, 0,
                    f"Model {model_id} is in NON_TEXT_MODELS and must have ctx_hint == 0, got {ctx}"
                )
            else:
                self.assertGreaterEqual(
                    ctx, 1000,
                    f"Model {model_id} ctx_hint {ctx} must be >= 1000 for text models"
                )


if __name__ == "__main__":
    unittest.main()
