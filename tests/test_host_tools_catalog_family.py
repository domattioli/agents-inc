"""Host-tools catalog falls back to the newest cached entry of the slug's family (2026-11-07: Codex 0.159.2 caches
gpt-5.6-luna while dispatch runs gpt-6-luna)."""
import json
import tempfile
import unittest
from pathlib import Path

from agents_inc.install.runtime import cache_entry, host_tools_catalog

CACHE = {"models": [{"slug": "gpt-5.4-luna", "tool_mode": "a"}, {"slug": "gpt-5.6-luna", "tool_mode": "b"},
                    {"slug": "gpt-5.6-sol"}, {"slug": "gpt-6-astra"}]}


class CacheEntry(unittest.TestCase):
    def test_exact_slug_wins(self):
        self.assertEqual(cache_entry(CACHE, "gpt-5.4-luna")["tool_mode"], "a")

    def test_missing_slug_takes_newest_same_family(self):
        self.assertEqual(cache_entry(CACHE, "gpt-6-luna")["slug"], "gpt-5.6-luna")

    def test_no_family_member_is_none(self):
        self.assertIsNone(cache_entry(CACHE, "gpt-6.1-terra"))
        self.assertIsNone(cache_entry(CACHE, "luna"))

    def test_catalog_relabels_the_fallback_as_the_requested_slug(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".scratch") as home:
            (Path(home) / "models_cache.json").write_text(json.dumps(CACHE))
            path = host_tools_catalog("gpt-6-luna", Path(home))
            models = json.loads(path.read_text())["models"]
            self.assertEqual([m["slug"] for m in models], ["gpt-6-luna"])
            self.assertEqual(models[0]["tool_mode"], "direct")


if __name__ == "__main__":
    unittest.main()
