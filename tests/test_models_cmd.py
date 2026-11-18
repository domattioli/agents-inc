import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import catalog, models_cmd

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures/catalog/models_cache.json"
# Test-owned pins, older than the fixture catalog's newest luna/sol, so DRIFT and bump paths stay
# exercised whatever the live routing.json pins. setUp rewrites the tmp routing copy to match.
FIXED = {"luna": "gpt-5.6-luna", "terra": "gpt-5.6-terra", "sol": "gpt-5.6-sol", "astra": "gpt-6-astra"}
MATCH = ("match", "0.1.0", "0.1.0")  # spec 047 D52.1: catalog verdicts and bumps need a catalog matching the installed codex
PERSONA_TIER = {"astra": "executive", "sol": "orchestrator", "terra": "workhorse", "luna": "grunt"}


class ModelsCmdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.routing = self.dir / "routing.json"
        self.models_json = self.dir / "models.json"
        text = (ROOT / "agents_inc/routing.json").read_text()
        self.live = {a: json.loads(text)["tiers"][t]["codex"] for a, t in PERSONA_TIER.items()}
        for alias, live in self.live.items():
            text = text.replace(f'"codex": "{live}"', f'"codex": "{FIXED[alias]}"')
        self.routing.write_text(text)
        self.routing_base = text
        table = json.loads((ROOT / "agents_inc/models.json").read_text())
        table["models"].pop("gpt-6.1-sol", None)  # bump must create it, right after gpt-5.6-sol
        self.models_json.write_text(models_cmd._dump(table) + "\n")
        self.catalog = catalog.load(FIXTURE)
        # Hermetic: an explicit bump records a pin in settings; never let the default reach ~/.config.
        from agents_inc import model_sync
        guard = mock.patch.object(model_sync, "DEFAULT_SETTINGS", str(self.dir / "default-settings.json"))
        guard.start(); self.addCleanup(guard.stop)

    def tearDown(self): self.tmp.cleanup()

    def _bump(self, alias, slug=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = models_cmd.bump(alias, slug, self.routing, self.models_json, self.catalog, FIXED,
                                   settings=self.dir / "settings.json", trust=MATCH)
        return code, out.getvalue(), err.getvalue()

    def test_listing_format_and_order(self):
        lines = models_cmd.listing(self.catalog, FIXED, trust=MATCH)
        self.assertEqual(len(lines), 4)
        self.assertEqual([line.split()[0] for line in lines], ["luna", "terra", "sol", "astra"])
        self.assertEqual(lines[2], "sol pinned gpt-5.6-sol newest gpt-6.1-sol DRIFT")
        self.assertEqual(lines[1], "terra pinned gpt-5.6-terra newest gpt-5.6-terra ok")
        self.assertTrue(lines[0].endswith("DRIFT"))

    def test_listing_without_cache_says_unknown(self):
        # Default aliases come from the live routing.json pins.
        self.assertEqual(models_cmd.listing([])[2], f"sol pinned {self.live['sol']} newest unknown unchecked")

    # ---- spec 047: pins the catalog lacks, foreign caches ----

    def test_listing_missing_pin_is_not_ok(self):
        pins = dict(FIXED, astra="gpt-6.2-astra")
        lines = models_cmd.listing(self.catalog, pins, trust=MATCH)
        self.assertEqual(lines[3], "astra pinned gpt-6.2-astra newest gpt-6-astra NOT-IN-CATALOG")

    def test_run_exit_1_when_a_pin_is_missing(self):
        pins = dict(FIXED, astra="gpt-6.2-astra")
        out = io.StringIO()
        with mock.patch.object(models_cmd, "MODEL_ALIASES", pins), mock.patch.object(catalog, "load", return_value=self.catalog), \
             mock.patch.object(models_cmd, "_trust", return_value=("match", "0.1.0", "0.1.0")), contextlib.redirect_stdout(out):
            self.assertEqual(models_cmd.run(None), 1)
        self.assertIn("NOT-IN-CATALOG", out.getvalue())
        with mock.patch.object(models_cmd, "MODEL_ALIASES", FIXED), mock.patch.object(catalog, "load", return_value=self.catalog), \
             mock.patch.object(models_cmd, "_trust", return_value=("match", "0.1.0", "0.1.0")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(models_cmd.run(None), 0)

    def test_listing_foreign_cache_note(self):
        lines = models_cmd.listing(self.catalog, FIXED, trust=("foreign", "0.170.0", "0.159.2"))
        self.assertIn("catalog written by codex 0.170.0, installed 0.159.2", lines[-1])
        self.assertFalse([l for l in lines if l.endswith("NOT-IN-CATALOG")])

    def test_bump_refused_on_foreign_cache(self):
        routing, models = self.routing.read_text(), self.models_json.read_text()
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = models_cmd.bump("sol", "gpt-6-sol", self.routing, self.models_json, self.catalog, FIXED,
                                   settings=self.dir / "settings.json", trust=("foreign", "0.170.0", "0.159.2"))
        self.assertEqual(code, 2)
        self.assertIn("update the CLI first", err.getvalue())
        self.assertEqual((self.routing.read_text(), self.models_json.read_text()), (routing, models))

    def test_bump_to_slug_absent_from_trusted_catalog_still_refused(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = models_cmd.bump("astra", "gpt-6.2-astra", self.routing, self.models_json, self.catalog, FIXED,
                                   settings=self.dir / "settings.json", trust=("match", "0.1.0", "0.1.0"))
        self.assertEqual(code, 2)
        self.assertIn("not a listed, API-supported catalog entry", err.getvalue())

    def test_unknown_or_foreign_trust_makes_no_verdict(self):  # H1
        for trust in (None, ("unknown", None, "0.1.0"), ("foreign", "0.2.0", "0.1.0")):
            with self.subTest(trust=trust):
                lines = models_cmd.listing(self.catalog, FIXED, trust=trust)
                self.assertFalse([l for l in lines if l.endswith((" DRIFT", " NOT-IN-CATALOG", " ok"))])
                self.assertTrue(all(l.endswith(" unchecked") for l in lines[:4]))
        self.assertIn("catalog version unknown", models_cmd.listing(self.catalog, FIXED, trust=("unknown", None, "0.1.0"))[-1])

    def test_bump_refused_on_unknown_trust_unpin_still_allowed(self):  # H1
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = models_cmd.bump("sol", "gpt-6-sol", self.routing, self.models_json, self.catalog, FIXED,
                                   settings=self.dir / "settings.json", trust=("unknown", None, "0.1.0"))
            self.assertEqual(code, 2)
            self.assertEqual(models_cmd.bump("sol", None, self.routing, self.models_json, self.catalog, FIXED,
                                             settings=self.dir / "settings.json", unpin=True), 0)
        self.assertIn("catalog version unknown", err.getvalue())

    def test_matching_empty_catalog_means_missing_unreadable_means_unchecked(self):  # H2
        self.assertTrue(models_cmd.listing([], FIXED, trust=MATCH)[0].endswith(" NOT-IN-CATALOG"))
        with mock.patch.object(catalog, "load", return_value=None):
            self.assertTrue(models_cmd.listing(None, FIXED, trust=MATCH)[0].endswith(" unchecked"))

    def test_bump_default_target(self):
        code, out, _ = self._bump("sol")
        self.assertEqual(code, 0)
        self.assertEqual(out.split(), [str(self.routing), str(self.models_json)])
        before = self.routing_base
        self.assertEqual(self.routing.read_text(), before.replace('"codex": "gpt-5.6-sol"', '"codex": "gpt-6.1-sol"'))
        table = json.loads(self.models_json.read_text())["models"]
        old = json.loads((ROOT / "agents_inc/models.json").read_text())["models"]["gpt-5.6-sol"]
        self.assertEqual(table["gpt-6.1-sol"]["supported_efforts"], ["low", "medium", "high", "xhigh", "max"])
        self.assertEqual({k: v for k, v in table["gpt-6.1-sol"].items() if k != "supported_efforts"},
                         {k: v for k, v in old.items() if k != "supported_efforts"})
        self.assertEqual(table["gpt-5.6-sol"], old)
        keys = list(table)
        self.assertEqual(keys.index("gpt-6.1-sol"), keys.index("gpt-5.6-sol") + 1)

    def test_bump_explicit_slug(self):
        code, _, _ = self._bump("sol", "gpt-6-sol")
        self.assertEqual(code, 0)
        self.assertIn('"codex": "gpt-6-sol"', self.routing.read_text())
        self.assertEqual(json.loads(self.models_json.read_text())["models"]["gpt-6-sol"]["supported_efforts"], ["low", "medium"])

    def test_models_json_formatting_survives_noop_dump(self):
        text = (ROOT / "agents_inc/models.json").read_text()  # the shipped file, not the tmp copy
        self.assertEqual(models_cmd._dump(json.loads(text)) + "\n", text)

    def test_refusals_exit_2_and_write_nothing(self):
        routing, models = self.routing.read_text(), self.models_json.read_text()
        cases = [("sol", "gpt-0-sol"), ("sol", "gpt-5.6-sol"), ("nova", None), ("terra", None), ("astra", "gpt-7-astra"),
                 ("terra", "gpt-9-terra"), ("sol", "gpt-6-astra")]
        for alias, slug in cases:
            code, _, err = self._bump(alias, slug)
            self.assertEqual(code, 2, (alias, slug))
            self.assertTrue(err.strip())
        self.assertEqual(self.routing.read_text(), routing)
        self.assertEqual(self.models_json.read_text(), models)

    # ---- manual pins (settings.json "pinned") ----

    def _settings(self, text=None):
        s = self.dir / "settings.json"
        if text is not None:
            s.write_text(text)
        return s

    def test_explicit_bump_records_pin_and_keeps_other_keys(self):
        s = self._settings('{"model_updates": "auto", "x": 1}')
        with contextlib.redirect_stdout(io.StringIO()):
            code = models_cmd.bump("sol", "gpt-6-sol", self.routing, self.models_json, self.catalog, FIXED, settings=s, trust=MATCH)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(s.read_text()), {"model_updates": "auto", "x": 1, "pinned": ["sol"]})

    def test_auto_bump_does_not_pin(self):
        s = self._settings('{"model_updates": "auto"}')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(models_cmd.bump("sol", None, self.routing, self.models_json, self.catalog, FIXED, settings=s, trust=MATCH), 0)
        self.assertNotIn("sol", json.loads(s.read_text()).get("pinned", []))

    def test_unpin_removes_pin_and_leaves_routing_and_models(self):
        s = self._settings('{"pinned": ["sol", "luna"], "model_updates": "approve"}')
        routing, models = self.routing.read_text(), self.models_json.read_text()
        with contextlib.redirect_stdout(io.StringIO()):
            code = models_cmd.bump("sol", None, self.routing, self.models_json, self.catalog, FIXED, settings=s, unpin=True)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(s.read_text()), {"pinned": ["luna"], "model_updates": "approve"})
        self.assertEqual((self.routing.read_text(), self.models_json.read_text()), (routing, models))

    def test_explicit_bump_with_corrupt_settings_refused_and_writes_nothing(self):
        s = self._settings("{bad")
        routing, models = self.routing.read_text(), self.models_json.read_text()
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = models_cmd.bump("sol", "gpt-6-sol", self.routing, self.models_json, self.catalog, FIXED, settings=s, trust=MATCH)
        self.assertEqual(code, 2)
        self.assertIn("not overwritten", err.getvalue())
        self.assertEqual((self.routing.read_text(), self.models_json.read_text(), s.read_text()), (routing, models, "{bad"))

    def test_ambiguous_routing_occurrence_refused(self):
        self.routing.write_text(self.routing.read_text() + '\n"codex": "gpt-5.6-sol"\n')
        self.assertEqual(self._bump("sol")[0], 2)


if __name__ == "__main__":
    unittest.main()
