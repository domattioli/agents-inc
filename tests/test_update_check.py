"""Update notice: version compare, daily cache, opt-out, silent failure. No network."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents_inc import __version__
from agents_inc.install import update_check as uc


class UpdateCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_newer(self):
        self.assertTrue(uc.newer("0.3.10", "0.3.9"))
        self.assertTrue(uc.newer("0.4.0", "0.4.0rc1"))
        self.assertFalse(uc.newer("0.3.1", "0.3.1"))
        self.assertFalse(uc.newer("0.3.0", "0.3.1"))
        self.assertFalse(uc.newer("garbage", "0.3.1"))

    def test_notice_and_daily_cache(self):
        calls = []

        def fetch(timeout):
            calls.append(timeout)
            return "99.0.0"
        text = uc.notice(self.state, env={}, fetch=fetch, now=1000.0)
        self.assertIn("agents-inc 99.0.0 is available", text)
        self.assertIn(__version__, text)
        uc.notice(self.state, env={}, fetch=fetch, now=1000.0 + 3600)
        self.assertEqual(len(calls), 1)  # cached within a day
        uc.notice(self.state, env={}, fetch=fetch, now=1000.0 + uc.TTL_S + 1)
        self.assertEqual(len(calls), 2)

    def test_same_version_failure_and_opt_out_are_silent(self):
        self.assertEqual(uc.notice(self.state, env={}, fetch=lambda t: __version__), "")
        self.tmp.cleanup(); self.tmp = tempfile.TemporaryDirectory(); self.state = Path(self.tmp.name)

        def boom(timeout):
            raise OSError("offline")
        self.assertEqual(uc.notice(self.state, env={}, fetch=boom), "")
        called = []
        self.assertEqual(uc.notice(self.state, env={uc.OPT_OUT: "1"}, fetch=lambda t: called.append(1) or "99.0.0"), "")
        self.assertEqual(called, [])

    def _script(self, shebang):
        p = self.state / "launcher"
        p.write_text(f"#!{shebang}\nfrom agents_inc.install.cli import main\n")
        return p

    def _notice(self, launcher=None, record=None, managed=False):
        if record is not None:
            (self.state / "source-checkout").write_text(record + "\n")
        std = self.state / "stdlib"; std.mkdir(exist_ok=True)
        if managed:
            (std / "EXTERNALLY-MANAGED").write_text("[externally-managed]\n")
        return uc.notice(self.state, env={}, fetch=lambda t: "99.0.0", now=1000.0, launcher=launcher, stdlib=std)

    def test_kind_pipx(self):
        text = self._notice(self._script("/Users/x/.local/pipx/venvs/agents-inc/bin/python"), record="packaged")
        self.assertIn("pipx upgrade agents-inc && agents-inc repair", text)
        self.assertNotIn("pip install -U", text)

    def test_kind_pip_user_and_venv(self):
        text = self._notice(self._script("/usr/bin/python3"), record="packaged")
        self.assertIn("python3 -m pip install --user -U agents-inc && agents-inc repair", text)
        venv = self.state / "venv" / "bin"; venv.mkdir(parents=True)
        (venv.parent / "pyvenv.cfg").write_text("home = /usr/bin\n")
        text = self._notice(self._script(str(venv / "python")), record="packaged")
        self.assertIn("python3 -m pip install -U agents-inc && agents-inc repair", text)
        self.assertNotIn("--user", text)

    def test_kind_pip_user_externally_managed_never_offers_bare_pip(self):
        text = self._notice(self._script("/usr/bin/python3"), record="packaged", managed=True)
        self.assertIn("PEP 668", text)
        self.assertIn("pipx upgrade agents-inc", text)
        self.assertIn("uv tool upgrade agents-inc", text)
        self.assertNotIn("pip install -U", text)

    def test_kind_checkout(self):
        text = self._notice(self._script("/usr/bin/python3"), record="/src/agents-inc")
        self.assertIn("git -C /src/agents-inc pull && agents-inc repair --source /src/agents-inc", text)
        self.assertNotIn("pip install -U", text)

    def test_kind_unknown_lists_forms_and_names_pep668(self):
        text = self._notice(self.state / "missing-launcher")
        self.assertIn("PEP 668", text)
        self.assertIn("pipx upgrade agents-inc", text)
        self.assertIn("uv tool upgrade agents-inc", text)
        self.assertIn("git -C <checkout> pull", text)
        self.assertNotIn("pip install -U", text)


if __name__ == "__main__":
    unittest.main()
