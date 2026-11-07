"""Every release cites the same Zenodo concept DOI ("Cite all versions").

Operator ruling 2026-10-07: 10.5281/zenodo.22670100 is the concept DOI for agents-inc (record 23092581 is
v0.1.0). Zenodo's GitHub integration adds each new release as a version under that concept, so the
citation never changes between releases. The release workflow runs this suite before it builds.
"""
import json
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
CONCEPT_DOI = "10.5281/zenodo.22670100"


class ReleaseMetadataTests(unittest.TestCase):
    def test_citation_cites_the_concept_doi(self):
        text = (REPO / "CITATION.cff").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"(?m)^doi:\s*(\S+)\s*$", text), [CONCEPT_DOI])

    def test_readme_badge_uses_only_the_concept_doi(self):
        text = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"https://doi.org/{CONCEPT_DOI}", text)
        self.assertEqual(set(re.findall(r"10\.5281/zenodo\.\d+", text)), {CONCEPT_DOI})

    def test_zenodo_json_never_pins_a_doi(self):
        # A doi or concept field here would make Zenodo file the release outside the concept record.
        data = json.loads((REPO / ".zenodo.json").read_text(encoding="utf-8"))
        for key in ("doi", "conceptdoi", "conceptrecid", "prereserve_doi"):
            self.assertNotIn(key, data)

    def test_no_operator_placeholders(self):
        for name in ("CITATION.cff", ".zenodo.json"):
            self.assertNotIn("TODO-operator", (REPO / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
