"""The relay tool accepts exactly the free slugs `agents-inc dispatch` runs (spec 037 FREE_MODELS), and keeps its
slots-inside-session-cwd check."""
import re, unittest
from pathlib import Path

from agents_inc.install.free_launch import FREE_MODELS

RELAY = Path(__file__).resolve().parents[1] / "mods/agents-inc/hooks/relay.ts"


class RelayFreeModelsTest(unittest.TestCase):
    def setUp(self):
        self.text = RELAY.read_text(encoding="utf-8")

    def test_free_list_equals_free_models(self):
        block = re.search(r"const FREE_MODELS = \[(.*?)\]", self.text, re.S).group(1)
        self.assertEqual(re.findall(r"'([^']+)'", block), list(FREE_MODELS))

    def test_no_agent_sh_refusal_and_slots_check_kept(self):
        self.assertNotIn("agent.sh", self.text)
        self.assertIn("slots must be a file inside", self.text)


if __name__ == "__main__":
    unittest.main()
