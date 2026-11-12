"""Spec 038 T046 (FR-006, P7): every free guest agent nickname names one FREE_MODELS slug and one vendor, and the mod
registers an adapter for exactly the same nicknames."""
import json
import re
import unittest
from pathlib import Path

from agents_inc.install import native
from agents_inc.install.free_launch import FREE_MODELS

ROOT = Path(__file__).resolve().parents[1]
MODELS = json.loads((ROOT / "agents_inc" / "models.json").read_text())["models"]
FREE = {"ministral": "ministral-3b-latest", "codestral": "codestral-latest", "gemini-flash": "gemini-3.8-flash",
        "nemotron-lightning": "nvidia/nemotron-3.5-lightning:free", "nemotron-ultra": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nemotron-nano": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "gemma-26b": "google/gemma-4-26b-a4b-it:free",
        "gemma-31b": "google/gemma-4-31b-it:free", "dots-note": "dots-studio/dots-3-note-preview:free"}


class Nicknames(unittest.TestCase):
    def test_each_nickname_names_one_slug_and_one_vendor(self):
        seen = {}
        for slug, spec in MODELS.items():
            nick = spec.get("nickname")
            if nick is None: continue
            self.assertNotIn(nick, seen, f"{nick} names {seen.get(nick)} and {slug}")
            self.assertRegex(nick, r"^[a-z][a-z0-9-]*$")
            seen[nick] = slug
        self.assertEqual(seen, FREE)
        for nick, slug in seen.items():
            self.assertIn(slug, FREE_MODELS, nick)
            self.assertEqual(MODELS[slug]["provider"], FREE_MODELS[slug].provider, nick)
            self.assertIsInstance(MODELS[slug]["vendor"], str)

    def test_native_roster_carries_every_free_nickname(self):
        free = {n: m for n, m in native.NATIVE_MODELS.items() if m["provider"] != "codex"}
        self.assertEqual({n: m["slug"] for n, m in free.items()}, FREE)
        for m in free.values():
            if m["provider"] == "openrouter": self.assertTrue(m["slug"].endswith(":free"))

    def test_mod_registers_an_adapter_for_the_same_nicknames(self):
        src = (ROOT / "mods/agents-inc/hooks/native/http.ts").read_text()
        block = src[src.index("HTTP_ADAPTERS"):]
        mod = set(re.findall(r"(?:mistral|openrouter)\('([a-z0-9-]+)'\)", block)) | {"gemini-flash"}
        self.assertEqual(mod, set(FREE))
        for nick, slug in FREE.items():
            if FREE_MODELS[slug].provider != "gemini":
                self.assertIn(f"{FREE_MODELS[slug].provider}('{nick}')", block)


if __name__ == "__main__":
    unittest.main()
