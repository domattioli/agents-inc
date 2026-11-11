"""A short rate limit (429, 503) is retried inside the step with bounded backoff; pacing spaces requests per provider.
Fake provider only; the sleep function is injected, so no test sleeps."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

from agents_inc.install import native, native_http as nh, native_probe
from agents_inc.install.paths import InstallPaths

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402

KEY = "AIzaFAKE-native-retry-3333333333333333333"
OK = {"candidates": [{"content": {"parts": [{"text": "hi"}]}}], "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1}}
RATE = {"error": {"message": "Rate limit exceeded"}}


def call(srv, **kw):
    return nh.ask("gemini", "gemini-3.8-flash", "P", KEY, max_chars=1000, timeout=5,
                  env={"AGENTS_INC_NATIVE_GEMINI_URL": srv.url}, **kw)


class Retry(unittest.TestCase):
    def test_429_then_200_succeeds_with_one_retry_and_no_real_sleep(self):
        slept, stats = [], {}
        with FakeProvider([Reply(429, RATE), Reply(200, OK)]) as srv:
            text, _ = call(srv, retries=3, sleep=slept.append, stats=stats)
            self.assertEqual(len(srv.requests), 2)
        self.assertEqual((text, slept, stats), ("hi", [2.0], {"retries": 1}))

    def test_429_four_times_exits_75_with_the_retry_count(self):
        slept = []
        with FakeProvider([Reply(429, RATE)] * 4) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv, retries=3, sleep=slept.append)
            self.assertEqual(len(srv.requests), 4)
        self.assertEqual(cm.exception.code, 75)
        self.assertIn("after 3 retries", cm.exception.text)
        self.assertEqual(slept, [2.0, 5.0, 12.0])

    def test_retry_after_is_honoured_and_capped(self):
        slept = []
        with FakeProvider([Reply(429, RATE, {"Retry-After": "3"}), Reply(429, RATE, {"Retry-After": "600"}), Reply(200, OK)]) as srv:
            call(srv, retries=3, sleep=slept.append)
        self.assertEqual(slept, [3.0, nh.RETRY_AFTER_CAP_S])

    def test_wait_budget_stops_the_retries(self):
        slept = []
        with FakeProvider([Reply(429, RATE, {"Retry-After": "15"})] * 4) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv, retries=3, sleep=slept.append)
        self.assertEqual(slept, [15.0])  # a second 15 s wait would pass the 20 s budget
        self.assertIn("after 1 retries", cm.exception.text)

    def test_daily_quota_body_is_not_retried(self):
        slept = []
        with FakeProvider([Reply(429, {"error": {"message": "daily quota exhausted"}})]) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv, retries=3, sleep=slept.append)
            self.assertEqual(len(srv.requests), 1)
        self.assertEqual((cm.exception.code, slept), (75, []))
        self.assertNotIn("retries", cm.exception.text)

    def test_503_is_retried_and_other_errors_are_not(self):
        slept = []
        with FakeProvider([Reply(503, {"error": "overloaded"}), Reply(200, OK)]) as srv:
            call(srv, retries=3, sleep=slept.append)
        self.assertEqual(slept, [2.0])
        with FakeProvider([Reply(500, {"error": "boom"})]) as srv:
            with self.assertRaises(nh.StepError): call(srv, retries=3, sleep=slept.append)
            self.assertEqual(len(srv.requests), 1)

    def test_default_is_no_retry(self):
        with FakeProvider([Reply(429, RATE), Reply(200, OK)]) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv, sleep=lambda s: None)
        self.assertEqual(cm.exception.code, 75)

    def test_policy_gives_a_loopback_server_nothing_unless_the_env_asks(self):
        env = {"AGENTS_INC_NATIVE_GEMINI_URL": "http://127.0.0.1:9"}
        self.assertEqual(nh.live_policy("gemini", env, 3, Path("/x")), {"retries": 0, "pace_dir": None})
        got = nh.live_policy("gemini", {**env, nh.RETRY_WAITS_ENV: "0,0"}, 3, Path("/x"))
        self.assertEqual((got["retries"], got["waits"]), (3, (0.0, 0.0)))
        live = nh.live_policy("mistral", {}, 3, Path("/x"))
        self.assertEqual((live["retries"], live["pace_dir"]), (3, Path("/x")))

    def test_probe_uses_its_one_small_retry(self):
        self.assertEqual(native_probe.PROBE_RETRIES, 1)
        self.assertEqual(native.STEP_RETRIES, 3)
        with tempfile.TemporaryDirectory() as tmp:
            paths = InstallPaths.for_home(Path(tmp))
            store = nh.key_store(Path(tmp)); store.parent.mkdir(parents=True)
            store.write_text(f"GEMINI_API_KEY={KEY}\n"); store.chmod(0o600)
            with FakeProvider([Reply(429, RATE)] * 5) as srv:
                env = {"AGENTS_INC_NATIVE_GEMINI_URL": srv.url, nh.RETRY_WAITS_ENV: "0,0,0"}
                rec = native_probe.probe_one(paths, "gemini-flash", env=env)
                self.assertEqual(len(srv.requests), 2)  # first try plus one retry
        self.assertEqual(rec["result"], "quota-paused")
        self.assertIn("after 1 retries", rec["reason"])


class Pace(unittest.TestCase):
    def test_second_request_waits_for_the_gap_and_providers_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            slept, now = [], [100.0]
            clock = lambda: now[0]
            nh.pace("mistral", Path(tmp), 1.1, slept.append, clock)
            self.assertEqual(slept, [])  # the first request does not wait
            now[0] += 0.4
            nh.pace("mistral", Path(tmp), 1.1, slept.append, clock)
            self.assertAlmostEqual(slept[0], 0.7)
            nh.pace("gemini", Path(tmp), 1.1, slept.append, clock)
            self.assertEqual(len(slept), 1)

    def test_table_and_env_override(self):
        self.assertEqual(nh.pace_gap("mistral", {}), 1.1)
        self.assertEqual(nh.pace_gap("unknown", {}), nh.PACE_DEFAULT_S)
        self.assertEqual(nh.pace_gap("mistral", {nh.PACE_ENV: "0"}), 0.0)

    def test_ask_paces_before_each_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            slept = []
            with FakeProvider([Reply(200, OK), Reply(200, OK)]) as srv:
                call(srv, pace_dir=Path(tmp), sleep=slept.append)
                call(srv, pace_dir=Path(tmp), sleep=slept.append)
        self.assertEqual(len(slept), 1)
        self.assertLessEqual(slept[0], nh.PACE_S["gemini"])


if __name__ == "__main__":
    unittest.main()
