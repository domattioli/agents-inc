import tempfile
import unittest
from pathlib import Path

from agents_inc.install import catalog

FIXTURE = Path(__file__).parent / "fixtures/catalog/models_cache.json"


class CatalogTest(unittest.TestCase):
    def test_version_parse_and_order(self):
        self.assertEqual(catalog.version("gpt-6.1-sol"), (6, 1))
        self.assertEqual(catalog.version("gpt-6-sol"), (6,))
        self.assertEqual(catalog.version("gpt-5.6-sol"), (5, 6))
        self.assertIsNone(catalog.version("claude-opus"))
        self.assertIsNone(catalog.version("gpt-reserve"))
        self.assertGreater(catalog._key((6, 1)), catalog._key((6,)))
        self.assertGreater(catalog._key((6,)), catalog._key((5, 6)))
        self.assertEqual(catalog._key((6,)), catalog._key((6, 0)))

    def test_family(self):
        self.assertEqual(catalog.family("gpt-5.6-sol"), "sol")

    def test_newest_per_family(self):
        models = catalog.load(FIXTURE)
        self.assertEqual(catalog.newest("sol", models), "gpt-6.1-sol")
        self.assertEqual(catalog.newest("luna", models), "gpt-6-luna")
        self.assertEqual(catalog.newest("astra", models), "gpt-6-astra")  # gpt-7-astra is not API-supported
        self.assertEqual(catalog.newest("terra", models), "gpt-5.6-terra")  # gpt-9-terra is hidden
        self.assertIsNone(catalog.newest("nova", models))

    def test_drift(self):
        models = catalog.load(FIXTURE)
        self.assertEqual(catalog.drift("gpt-5.6-sol", models), "gpt-6.1-sol")
        self.assertIsNone(catalog.drift("gpt-6.1-sol", models))
        self.assertIsNone(catalog.drift("gpt-6-astra", models))
        self.assertIsNone(catalog.drift("gpt-5.6-terra", models))

    def test_entry(self):
        models = catalog.load(FIXTURE)
        self.assertEqual(catalog.entry("gpt-6-sol", models)["priority"], 1)
        self.assertIsNone(catalog.entry("gpt-0-sol", models))

    def test_missing_or_malformed_cache_gives_none(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertIsNone(catalog.load(Path(raw) / "none.json"))
            bad = Path(raw) / "bad.json"
            bad.write_text("{not json")
            self.assertIsNone(catalog.load(bad))
            bad.write_text('{"models": 3}')
            self.assertIsNone(catalog.load(bad))

    def test_cache_path_honors_codex_home_and_home(self):
        self.assertEqual(catalog.cache_path({"CODEX_HOME": "/x/ch", "HOME": "/h"}), Path("/x/ch/models_cache.json"))
        self.assertEqual(catalog.cache_path({"HOME": "/h"}), Path("/h/.codex/models_cache.json"))

    def test_load_reads_codex_home_cache(self):
        with tempfile.TemporaryDirectory() as raw:
            (Path(raw) / "models_cache.json").write_text(FIXTURE.read_text())
            models = catalog.load(catalog.cache_path({"CODEX_HOME": raw}))
            self.assertEqual(catalog.newest("sol", models), "gpt-6.1-sol")


if __name__ == "__main__":
    unittest.main()


class CatalogTrustTest(unittest.TestCase):
    """Spec 047 FR-002, FR-003: client_version trust and pin status."""

    def _cache(self, body):
        import json
        d = tempfile.mkdtemp()
        p = Path(d) / "models_cache.json"
        p.write_text(json.dumps(body))
        return p

    def test_client_version(self):
        self.assertEqual(catalog.client_version(self._cache({"client_version": "0.170.0", "models": []})), "0.170.0")
        self.assertIsNone(catalog.client_version(self._cache({"models": []})))
        self.assertIsNone(catalog.client_version(Path(tempfile.mkdtemp()) / "none.json"))

    def test_trust(self):
        p = self._cache({"client_version": "0.170.0", "models": []})
        self.assertEqual(catalog.trust(p, "0.170.0"), "match")
        self.assertEqual(catalog.trust(p, "0.159.2"), "foreign")
        self.assertEqual(catalog.trust(p, None), "unknown")
        self.assertEqual(catalog.trust(self._cache({"models": []}), "0.170.0"), "unknown")

    def test_pin_status(self):
        models = catalog.load(FIXTURE)
        self.assertEqual(catalog.pin_status("gpt-6.1-sol", models), "ok")
        self.assertEqual(catalog.pin_status("gpt-6-sol", models), "drift")
        self.assertEqual(catalog.pin_status("gpt-6.2-astra", models), "missing")  # absent
        self.assertEqual(catalog.pin_status("gpt-7-astra", models), "missing")  # not API-supported
        self.assertEqual(catalog.pin_status("gpt-9-terra", models), "missing")  # hidden
