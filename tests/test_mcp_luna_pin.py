"""The DelegateAgent MCP server's luna slug follows the routing.json pin."""
import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class McpLunaPinTest(unittest.TestCase):
    def test_luna_matches_routing_pin(self):
        spec = importlib.util.spec_from_file_location("codex_agent_mcp", REPO / "skills/codex-bridge/mcp/codex_agent_mcp.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tiers = json.loads((REPO / "agents_inc/routing.json").read_text())["tiers"]
        self.assertEqual(mod.DEFAULT_MODEL_MAP["luna"], tiers["grunt"]["codex"])
        for alias, tier in (("luna", "grunt"), ("terra", "workhorse"), ("sol", "orchestrator"), ("astra", "executive")):
            self.assertEqual(mod.DEFAULT_MODEL_MAP[alias], tiers[tier]["codex"])
        self.assertEqual(mod._pinned_seats("/nonexistent"), {"luna": "gpt-6-luna"})
        self.assertEqual(mod._pinned_luna("/nonexistent"), "gpt-6-luna")


if __name__ == "__main__":
    unittest.main()
