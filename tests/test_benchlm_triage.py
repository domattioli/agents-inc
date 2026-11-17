import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from agents_inc import benchlm, lineup_router, router
from agents_inc.router import Route


class BenchlmTriageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'snapshot.json'
        self.routes = (Route('p', 'a', 'grunt', 'http'), Route('p', 'unknown', 'grunt', 'http'),
                       Route('p', 'b', 'grunt', 'http'))
        self.data = {'source': benchlm.SOURCE, 'date': date.today().isoformat(), 'entries': [
            {'job': 'Coding', 'evidence_kind': 'direct', 'rank': 2, 'cohort': 'general', 'model': 'a'},
            {'job': 'Coding', 'evidence_kind': 'direct', 'rank': 1, 'cohort': 'general', 'model': 'b'}]}

    def write(self):
        self.path.write_text(json.dumps(self.data))

    def test_ranked_slots_reordered_unranked_preserved(self):
        self.write()
        result = benchlm.advise(self.routes, self.path, 'Coding')
        self.assertEqual([r.model for r in result], ['b', 'unknown', 'a'])

    def test_default_invalid_stale_and_unsupported_fail_safe(self):
        self.assertEqual(benchlm.advise(self.routes, None, 'Coding'), self.routes)
        self.path.write_text('{')
        self.assertEqual(benchlm.advise(self.routes, self.path, 'Coding'), self.routes)
        self.data['date'] = (date.today() - timedelta(days=91)).isoformat()
        self.write()
        self.assertEqual(benchlm.advise(self.routes, self.path, 'Coding'), self.routes)
        self.data['date'] = (date.today() + timedelta(days=1)).isoformat()
        self.write()
        self.assertEqual(benchlm.advise(self.routes, self.path, 'Coding'), self.routes)
        self.data['date'] = date.today().isoformat()
        self.write()
        self.assertEqual(benchlm.advise(self.routes, self.path, 'unknown'), self.routes)
        self.assertEqual(benchlm.advise(self.routes, self.path, []), self.routes)
        self.data['entries'][0]['rank'] = True
        self.write()
        self.assertEqual(benchlm.advise(self.routes, self.path, 'Coding'), self.routes)

    def test_cohorts_kinds_and_providers_not_compared(self):
        for field, value in [('cohort', 'other'), ('evidence_kind', 'proxy')]:
            original = self.data['entries'][1][field]
            self.data['entries'][1][field] = value
            self.write()
            self.assertEqual(benchlm.advise(self.routes, self.path, 'Coding'), self.routes)
            self.data['entries'][1][field] = original
        self.write()
        routes = (self.routes[0], Route('other', 'b', 'grunt', 'http'))
        self.assertEqual(benchlm.advise(routes, self.path, 'Coding'), routes)

    def test_release_validation_detects_stale_and_malformed_snapshots(self):
        self.write()
        self.assertEqual(benchlm.main([str(self.path)]), 0)
        self.data["date"] = (date.today() - timedelta(days=91)).isoformat()
        self.write()
        self.assertEqual(benchlm.main([str(self.path)]), 1)
        self.path.write_text("{")
        self.assertEqual(benchlm.main([str(self.path)]), 1)

    def test_duplicate_evidence_rejected(self):
        self.data['entries'].append(dict(self.data['entries'][0]))
        self.write()
        self.assertEqual(benchlm.advise(self.routes, self.path, 'Coding'), self.routes)

    def test_lineup_applies_only_to_existing_candidates(self):
        self.write()
        baseline = lineup_router.rank(self.routes, ())
        self.assertEqual(lineup_router.rank(self.routes, (), benchlm_snapshot=self.path, benchlm_job='Coding'),
                         benchlm.advise(baseline, self.path, 'Coding'))
        self.assertEqual(lineup_router.rank(self.routes, ()), baseline)

    def test_lineup_never_overrides_cost_priority(self):
        self.write()
        profiles = {"a": {"cost_class": "free"}, "b": {"cost_class": "premium"}}
        with patch.object(lineup_router, "_CATALOG", profiles):
            result = lineup_router.rank((self.routes[2], self.routes[0]), ("cost",),
                                        benchlm_snapshot=self.path, benchlm_job="Coding")
        self.assertEqual([r.model for r in result], ["a", "b"])

    def test_pipeline_passes_explicit_advice_to_router(self):
        from agents_inc import pipeline
        source = Path(self.tmp.name) / "source.txt"
        source.write_text("Example source.")
        with patch.object(pipeline, "pick_model", return_value=None) as pick, \
             patch.object(pipeline, "is_authorized", return_value=False), \
             patch.object(pipeline, "is_local_authorized", return_value=False):
            result = pipeline.brief(source, "example", "lawyer", Path(self.tmp.name), available={"claude"},
                                    benchlm_snapshot=self.path, benchlm_job="Data extraction")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(pick.call_args.kwargs["benchlm_snapshot"], self.path)
        self.assertEqual(pick.call_args.kwargs["benchlm_job"], "Data extraction")

    def test_router_filters_before_advice(self):
        self.write()
        with patch.object(router, '_provider_routes', return_value=list(self.routes)), \
             patch.object(router.free_health if hasattr(router, 'free_health') else __import__('agents_inc.free_health', fromlist=['x']), 'load_health', return_value={}), \
             patch('agents_inc.free_health.load_overlay', return_value={}):
            # An unavailable provider cannot be introduced by evidence.
            result = router.pick_model_chain('coding', 'grunt', set(), False,
                                             benchlm_snapshot=self.path, benchlm_job='Coding')
            self.assertEqual(result, ())


if __name__ == '__main__':
    unittest.main()
