"""Spec 038 FR-016: the relay type, mcp__agents-inc__run and @alias routes are off by default. `--legacy-routes` on
install or repair stores the choice in ~/.config/agents-inc/settings.json; status --all reports it to the mod."""
import json
import tempfile
import unittest
from pathlib import Path

from agents_inc.install import cli, hook, native
from agents_inc.install.paths import InstallPaths


class LegacyRoutesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.paths = InstallPaths.for_home(Path(self.tmp.name))

    def test_default_is_off_and_unreadable_reads_off(self):
        self.assertFalse(hook.legacy_routes(self.paths))
        self.paths.settings.parent.mkdir(parents=True); self.paths.settings.write_text("{bad")
        self.assertFalse(hook.legacy_routes(self.paths))

    def test_write_keeps_other_keys(self):
        hook.write_agent_gate(self.paths, "enforce")
        hook.write_legacy_routes(self.paths, True)
        data = json.loads(self.paths.settings.read_text())
        self.assertEqual((data["agent_gate"], data["legacy_routes"]), ("enforce", "on"))
        hook.write_legacy_routes(self.paths, False)
        self.assertFalse(hook.legacy_routes(self.paths))

    def test_status_all_reports_the_switch_for_the_mod(self):
        self.assertIs(native.status_all(self.paths)["legacy_routes"], False)
        hook.write_legacy_routes(self.paths, True)
        self.assertIs(native.status_all(self.paths)["legacy_routes"], True)

    def test_flag_on_install_and_repair_defaults_to_none(self):
        seen = {}
        orig = cli.install
        try:
            cli.install = lambda args: seen.setdefault(args.command, args.legacy_routes) and 0 or 0
            for argv, want in ((["install"], None), (["repair", "--legacy-routes"], True), (["install", "--no-legacy-routes"], False)):
                seen.clear(); cli.main(argv); self.assertEqual(seen[argv[0]], want, argv)
        finally:
            cli.install = orig


if __name__ == "__main__":
    unittest.main()
