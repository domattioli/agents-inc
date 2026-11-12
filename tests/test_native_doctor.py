"""Spec 038 T044 (FR-018, US2 scenario 3): `agents-inc doctor` prints one offer line per guest agent model, warns when
the installed mod's version differs from the package's, and `doctor --probe` probes the free models against a fake
server. A temp HOME, a fake `claude` and fake keys only; no provider is reached."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agents_inc import __version__
from agents_inc.install import doctor, native

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402

os.environ.setdefault("AGENTS_INC_NO_UPDATE_CHECK", "1")
ROOT = Path(__file__).resolve().parent.parent
PLUGIN = "agents-inc@agents-inc-local"
FAKE_KEY = "AIzaFAKE-native-doctor-000000000000000000"


def plugin_list(version):
    return (f"Installed plugins:\n\n  ❯ other@market\n    Version: 9.9.9\n    Scope: user\n\n"
            f"  ❯ {PLUGIN}\n    Version: {version}\n    Read from: /x/mods/agents-inc\n    Scope: user\n    Status: ✔ enabled\n")


class VersionParse(unittest.TestCase):
    def test_reads_the_agents_inc_block_only(self):
        self.assertEqual(doctor.installed_mod_version(plugin_list("0.2.0")), "0.2.0")
        self.assertIsNone(doctor.installed_mod_version(PLUGIN))  # no Version line: no claim
        self.assertEqual(doctor.mod_version_warnings(plugin_list(__version__)), [])
        [w] = doctor.mod_version_warnings(plugin_list("0.2.0"))
        self.assertIn(f"installed mod 0.2.0, package {__version__}", w)

    def test_shipped_manifest_carries_the_package_version(self):
        manifest = json.loads((ROOT / "mods/agents-inc/.claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["version"], __version__)


class DoctorCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = Path(tempfile.mkdtemp()).resolve()
        src = cls.home / "src"
        ignore = shutil.ignore_patterns("__pycache__", "*.bak", "node_modules", "types")
        for item in ("agents_inc", "skills/workerbee", "skills/codex-bridge", "mods/agents-inc"):
            shutil.copytree(ROOT / item, src / item, ignore=ignore)
        cls.bin = cls.home / "fakebin"; cls.bin.mkdir()
        shutil.copy(ROOT / "tests/fixtures/fake_claude/claude", cls.bin / "claude")
        r = cls.cli("install", "--source", str(src), "--without-codex", "--no-host-wiring", "--no-mod")
        assert r.returncode == 0, r.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.home, ignore_errors=True)

    @classmethod
    def cli(cls, *argv, **env):
        e = dict(os.environ, HOME=str(cls.home), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
                 PATH=str(cls.bin) + os.pathsep + "/usr/bin:/bin", AGENTS_INC_NO_UPDATE_CHECK="1", **env)
        e.pop("AGENTS_INC_MODEL_MAP", None)
        return subprocess.run([sys.executable, "-m", "agents_inc.install.cli", *argv], cwd=cls.home, env=e,
                              capture_output=True, text=True, timeout=120)

    def test_one_offer_line_per_guest_model_and_version_warning(self):
        out = self.cli("doctor", FAKE_CLAUDE_PLUGIN_LIST=plugin_list("0.2.0")).stdout
        for nick in native.NATIVE_MODELS:
            if nick == "luna": continue  # luna keeps its own `luna type:` line
            self.assertEqual(sum(line.startswith(f"{nick} type: ") for line in out.splitlines()), 1, (nick, out))
        for nick in ("sol", "terra", "astra"):
            self.assertIn(f"{nick} type: not offered (switched off (agents-inc native on {nick}))", out)
        self.assertIn(f"WARNING: MOD_VERSION_MISMATCH: installed mod 0.2.0, package {__version__}", out)
        out = self.cli("doctor", FAKE_CLAUDE_PLUGIN_LIST=plugin_list(__version__)).stdout
        self.assertNotIn("MOD_VERSION_MISMATCH", out)

    def test_doctor_probe_against_a_fake_server(self):
        keyfile = self.home / ".codex-bridge" / "gemini-key"
        keyfile.parent.mkdir(exist_ok=True); keyfile.write_text(FAKE_KEY)
        self.addCleanup(keyfile.unlink)
        reply = {"candidates": [{"content": {"parts": [{"text": '{"say": "reading", "tools": [{"name": "Read", "input": {"file_path": "probe.txt"}}]}'}]}}]}
        with FakeProvider([Reply(200, reply)]) as srv:
            r = self.cli("doctor", "--probe", FAKE_CLAUDE_PLUGIN_LIST=plugin_list(__version__),
                         AGENTS_INC_NATIVE_GEMINI_URL=srv.url, AGENTS_INC_NATIVE_MISTRAL_URL=srv.url,
                         AGENTS_INC_NATIVE_OPENROUTER_URL=srv.url)
        self.assertEqual(len(srv.requests), 1)  # only the model with a key is asked
        self.assertIn("gemini-flash probe: pass", r.stdout)
        self.assertIn("ministral probe: unavailable (no mistral key (WB_NATIVE_KEY_MISSING", r.stdout)
        self.assertIn("gemini-flash type: ready", r.stdout)
        self.assertNotIn(FAKE_KEY, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
