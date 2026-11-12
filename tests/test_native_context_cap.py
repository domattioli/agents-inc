"""The prompt cap of a free guest agent step is per model (models.json ctx_hint), and the first step of a real
77-tool session fits it once the catalog holds only the tools a guest agent can use (spec 038, D75)."""
import re
import sys
import unittest
from pathlib import Path

from agents_inc import native_names
from agents_inc.install import native
from agents_inc.install.free_launch import FREE_MODELS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import native_stress  # noqa: E402


class ContextCap(unittest.TestCase):
    def test_cap_is_derived_from_the_window_with_reply_headroom(self):
        self.assertEqual(native.model("codestral")["max_input_chars"], 72000)  # 32000 tokens * 3 chars * 0.75
        self.assertEqual(native.model("dots-note")["max_input_chars"], 18000)
        for nick, entry in native.NATIVE_MODELS.items():
            if entry["slug"] in FREE_MODELS:
                self.assertGreater(native.model(nick)["max_input_chars"], 0)

    def test_unknown_or_unusable_window_falls_back(self):
        self.assertEqual(native_names.context_chars("no-such-model", 48000), 48000)

    def test_step_zero_of_a_77_tool_session_fits_codestral_only_with_the_core_catalog(self):
        cap = native.model("codestral")["max_input_chars"]
        whole = len(native_stress.session_prefix(core_only=False)) + 200
        core = len(native_stress.session_prefix(core_only=True)) + 200
        self.assertGreater(whole, 48000, "the unfiltered 77-tool catalog must exceed the old fixed cap, or the fixture is too small")
        self.assertLess(core, 48000)
        self.assertLess(core, cap)

    def test_stress_core_list_matches_the_mod(self):
        src = (ROOT / "mods/agents-inc/hooks/native/loop.ts").read_text()
        names = re.search(r"GUEST_TOOLS: readonly string\[\] = \[([^\]]*)\]", src).group(1)
        self.assertEqual(tuple(re.findall(r"'(\w+)'", names)), native_stress.GUEST_CORE)


if __name__ == "__main__":
    unittest.main()
