import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from agents_inc.install.paths import InstallPaths
from agents_inc.install.receipt import InstallReceipt
from agents_inc.install.runtime import MODEL_ALIASES, build_codex_argv, load_model_map

# Pinned luna slug comes from routing.json so a pin bump does not need a test edit.
LUNA = json.loads((Path(__file__).resolve().parents[1] / "agents_inc/routing.json").read_text())["tiers"]["grunt"]["codex"]
EFF = {LUNA: ["medium"], "gpt-9-new": ["medium"], "gpt-env": ["medium"]}


class ModelMapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.roster = Path(self.tmp.name) / "roster.json"

    def test_paths_roster(self):
        self.assertEqual(InstallPaths.for_home(Path("/h")).roster, Path("/h/.config/agents-inc/roster.json"))

    def test_defaults(self):
        self.assertEqual(load_model_map(self.roster, {}), MODEL_ALIASES)
        argv = build_codex_argv(Path("/x/codex"), "luna", "medium", Path("/w"), EFF, load_model_map(self.roster, {}))
        self.assertEqual(argv[3], LUNA)

    def test_roster_adds_slug(self):
        self.roster.write_text(json.dumps({"models": {"nova": "gpt-9-new"}}))
        m = load_model_map(self.roster, {})
        self.assertEqual(m["nova"], "gpt-9-new"); self.assertEqual(m["luna"], LUNA)
        self.assertEqual(build_codex_argv(Path("/x/codex"), "nova", "medium", Path("/w"), EFF, m)[3], "gpt-9-new")

    def test_env_beats_roster_json_and_path(self):
        self.roster.write_text(json.dumps({"luna": "from-roster"}))
        self.assertEqual(load_model_map(self.roster, {"AGENTS_INC_MODEL_MAP": '{"luna": "from-env"}'})["luna"], "from-env")
        f = Path(self.tmp.name) / "env.json"; f.write_text('{"luna": "from-file"}')
        self.assertEqual(load_model_map(self.roster, {"AGENTS_INC_MODEL_MAP": str(f)})["luna"], "from-file")
        self.assertEqual(load_model_map(self.roster, {})["luna"], "from-roster")

    def test_malformed_falls_back(self):
        self.roster.write_text("{not json")
        err = StringIO()
        with redirect_stderr(err):
            m = load_model_map(self.roster, {"AGENTS_INC_MODEL_MAP": '{"luna": 5}'})
        self.assertEqual(m, MODEL_ALIASES)
        self.assertIn("malformed model map", err.getvalue())
        with redirect_stderr(StringIO()):
            self.assertEqual(load_model_map(self.roster, {"AGENTS_INC_MODEL_MAP": "/no/such/file.json"}), MODEL_ALIASES)

    def test_receipt_without_codex_roundtrip_and_v1_compat(self):
        r = InstallReceipt("a" * 64, Path("/usr/bin/python3"), None)
        self.assertEqual(r.schema_version, 2)
        p = Path(self.tmp.name) / "r.json"; r.save_atomic(p)
        self.assertIsNone(InstallReceipt.load(p).codex_path)
        d = json.loads(p.read_text()); d["schema_version"] = 1; d["codex_path"] = "/usr/bin/codex"; p.write_text(json.dumps(d))
        self.assertEqual(InstallReceipt.load(p).codex_path, Path("/usr/bin/codex"))

    def test_codexagent_guard_uses_map(self):
        root = Path(__file__).resolve().parent.parent / "skills/codex-bridge/scripts/codexagent.sh"
        stub = Path(self.tmp.name) / "bin"; stub.mkdir()
        (stub / "codex").write_text('#!/bin/bash\nprintf "%s " "$@" > "$STUB_OUT"\nfor a in "$@"; do [ "$prev" = "-o" ] && echo ok > "$a"; prev="$a"; done\n')
        (stub / "codex").chmod(0o755)
        env = {"PATH": f"{stub}:{os.path.dirname(sys.executable)}:/usr/bin:/bin", "HOME": self.tmp.name, "TMPDIR": self.tmp.name, "STUB_OUT": str(Path(self.tmp.name) / "out")}
        bad = subprocess.run(["/bin/bash", str(root), "--model", "nope", "hi"], env=env, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1); self.assertIn("invalid model", bad.stderr)
        dflt = subprocess.run(["/bin/bash", str(root), "--model", "nova", "hi"], env=env, capture_output=True, text=True)
        self.assertEqual(dflt.returncode, 1); self.assertIn("invalid model", dflt.stderr)
        env["CODEXAGENT_MODEL_MAP"] = '{"nova": "gpt-5.6-nova"}'
        ok = subprocess.run(["/bin/bash", str(root), "--model", "nova", "hi"], env=env, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("-m gpt-5.6-nova", (Path(self.tmp.name) / "out").read_text())

    def test_mcp_default_enum_has_all_four_seats_and_config_adds(self):
        mcp = Path(__file__).resolve().parent.parent / "skills/codex-bridge/mcp/codex_agent_mcp.py"
        req = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n'

        def enum(extra_env, home):
            env = {"PATH": f"{os.path.dirname(sys.executable)}:/usr/bin:/bin", "HOME": str(home), **extra_env}
            out = subprocess.run([sys.executable, str(mcp)], input=req, env=env, capture_output=True, text=True).stdout
            tool = [t for t in json.loads(out.splitlines()[0])["result"]["tools"] if t["name"] == "DelegateAgent"][0]
            return tool["inputSchema"]["properties"]["model"]["enum"]

        home = Path(self.tmp.name) / "h"; (home / ".config/agents-inc").mkdir(parents=True)
        self.assertEqual(sorted(enum({}, home)), ["astra", "luna", "sol", "terra"])
        (home / ".config/agents-inc/roster.json").write_text('{"models": {"sol": "gpt-5.6-sol"}}')
        self.assertEqual(sorted(enum({}, home)), ["astra", "luna", "sol", "terra"])
        self.assertEqual(sorted(enum({"AGENTS_INC_MODEL_MAP": '{"nova": "gpt-6-nova"}'}, home)), ["astra", "luna", "nova", "sol", "terra"])

if __name__ == "__main__":
    unittest.main()
