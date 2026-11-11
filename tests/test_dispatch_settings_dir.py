"""D81: a slot may name ~/.config/agents-inc or its settings.json only from an agents-inc source checkout."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from agents_inc.install import dispatch


def _slot(text):
    return {"TASK": text}


class SettingsDirTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.checkout = root / "src"
        for d in ("agents_inc", "skills/workerbee", "skills/codex-bridge", "docs/governance"):
            (self.checkout / d).mkdir(parents=True)
        (self.checkout / "docs/governance/SCHEMA-3NF.md").write_text("x")
        (self.checkout / "agents_inc/sub").mkdir()
        self.other = root / "other"
        self.other.mkdir()

    def hit(self, text, cwd):
        return dispatch.credential_hit(_slot(text), cwd)

    def test_allowed_from_checkout(self):
        for text in ("add a file under ~/.config/agents-inc and keep it small",
                     "write ~/.config/agents-inc/settings.json with legacy_routes",
                     "see `~/.config/agents-inc/`, then stop",
                     "edit $HOME/.config/agents-inc/settings.json."):
            self.assertIsNone(self.hit(text, self.checkout / "agents_inc/sub"), text)

    def test_refused_outside_checkout(self):
        for cwd in (self.other, None):
            self.assertIsNotNone(self.hit("add ~/.config/agents-inc/settings.json", cwd))
            self.assertIsNotNone(self.hit("under ~/.config/agents-inc here", cwd))

    def test_other_files_in_dir_refused_from_checkout(self):
        for name in ("install.json", "roster.json", "pending-model-update.json", ".env", "settings.json.bak", "x.key"):
            self.assertIsNotNone(self.hit(f"read ~/.config/agents-inc/{name}", self.checkout), name)

    def test_key_stores_refused_from_checkout(self):
        for text in ("read ~/.config/workerbees/.env", "read ~/.config/workerbees/", "cat ~/Projects/.env",
                     "open $HOME/.config/workerbees/.env", "also ~/.config/agents-inc and ~/.config/workerbees/.env"):
            self.assertIsNotNone(self.hit(text, self.checkout), text)

    def test_dotdot_and_spelling_variants_refused(self):
        for text in ("~/.config/agents-inc/../workerbees/.env", "~/.config/agents-inc/../workerbees",
                     "$HOME/.config/agents-inc/settings.json/../../workerbees/.env",
                     "~/.config/agents-inc//../workerbees/x", "~/.config/agents-inc/../",
                     "$HOME/.config/agents-inc/../../.ssh/id_rsa"):
            self.assertIsNotNone(self.hit(text, self.checkout), text)

    def test_marker_needs_all_paths(self):
        (self.checkout / "docs/governance/SCHEMA-3NF.md").unlink()
        self.assertIsNotNone(self.hit("under ~/.config/agents-inc", self.checkout))


if __name__ == "__main__":
    unittest.main()
