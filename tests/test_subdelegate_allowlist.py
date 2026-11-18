"""The nested sub-delegation lint names every paid Codex pin, including the 2026-11-18 astra pin gpt-6.2-astra."""
import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "skills/workerbee/scripts/check_subdelegate_allowlist.py"
spec = importlib.util.spec_from_file_location("check_subdelegate_allowlist", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AstraPinTest(unittest.TestCase):
    def test_current_pin_is_listed_explicitly(self):
        self.assertIn("gpt-6.2-astra", mod.FORBIDDEN)

    def test_nested_call_to_new_pin_is_flagged(self):
        text = '"model": "gpt-6.2-astra"\nSUB-DELEGATE MODEL: gpt-6.2-astra — allowlist match: yes\n'
        self.assertTrue(any("forbidden" in v for v in mod.check(text)))

    def test_free_model_passes(self):
        text = '"model": "codestral-latest"\nSUB-DELEGATE MODEL: codestral-latest — allowlist match: yes\n'
        self.assertEqual(mod.check(text), [])


if __name__ == "__main__":
    unittest.main()
