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
        self.assertEqual((text, slept, stats), ("hi", [5.0], {"retries": 1}))

    def test_429_four_times_exits_75_with_the_retry_count(self):
        slept = []
        with FakeProvider([Reply(429, RATE)] * 4) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv, retries=3, sleep=slept.append)
            self.assertEqual(len(srv.requests), 4)
        self.assertEqual(cm.exception.code, 75)
        self.assertIn("after 3 retries", cm.exception.text)
        self.assertEqual(slept, [5.0, 20.0, 40.0])

    def test_retry_after_is_honoured_and_capped(self):
        slept = []
        with FakeProvider([Reply(429, RATE, {"Retry-After": "3"}), Reply(429, RATE, {"Retry-After": "600"}), Reply(200, OK)]) as srv:
            call(srv, retries=3, sleep=slept.append)
        self.assertEqual(slept, [3.0, nh.RETRY_AFTER_CAP_S])
        self.assertEqual(nh.RETRY_AFTER_CAP_S, 45.0)

    def test_wait_budget_stops_the_retries(self):
        slept = []
        with FakeProvider([Reply(429, RATE, {"Retry-After": "30"})] * 4) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv, retries=3, sleep=slept.append)
        self.assertEqual(slept, [30.0, 30.0])  # a third 30 s wait would pass the 65 s budget
        self.assertIn("after 2 retries", cm.exception.text)

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
        self.assertEqual(slept, [5.0])
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


class Headers(unittest.TestCase):
    HDRS = {"x-ratelimit-remaining-tokens": "0", "x-ratelimit-reset-tokens": "37", "RateLimit-Limit": "50000",
            "Set-Cookie": "secret=1", "X-Request-Id": "abc", "x-ratelimit-note": "z" * 500}

    def test_only_rate_limit_headers_reach_the_error_and_values_are_capped(self):
        with FakeProvider([Reply(429, RATE, self.HDRS)]) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv, sleep=lambda s: None)
        text = cm.exception.text
        self.assertIn("x-ratelimit-reset-tokens=37", text)
        self.assertIn("ratelimit-limit=50000", text)
        self.assertNotIn("secret", text); self.assertNotIn("abc", text); self.assertNotIn("z" * 61, text)
        self.assertIn("z" * 60, text)

    def test_a_success_or_other_error_shows_no_headers(self):
        with FakeProvider([Reply(500, {"error": "boom"}, self.HDRS)]) as srv:
            with self.assertRaises(nh.StepError) as cm: call(srv)
        self.assertNotIn("ratelimit", cm.exception.text.lower())

    def test_reset_header_sets_the_wait_and_the_event_line_carries_the_headers(self):
        slept, events = [], []
        with FakeProvider([Reply(429, RATE, self.HDRS), Reply(200, OK)]) as srv:
            call(srv, retries=3, sleep=slept.append, on_retry=lambda n, of, w, h: events.append((n, of, w, h)))
        self.assertEqual(slept, [37.0])
        self.assertEqual(events[0][:3], (1, 3, 37.0))
        self.assertEqual(events[0][3]["x-ratelimit-reset-tokens"], "37")

    def test_reset_forms_and_cap(self):
        self.assertEqual(nh.header_wait({"x-ratelimit-reset-tokens": "1m30s"}, 0), 90.0)
        self.assertEqual(nh.header_wait({"x-ratelimit-reset-requests": "250ms"}, 0), 0.25)
        self.assertEqual(nh.header_wait({"x-ratelimit-reset": "1800000060"}, 1800000000.0), 60.0)
        self.assertIsNone(nh.header_wait({"x-ratelimit-remaining": "0"}, 0))
        slept = []
        with FakeProvider([Reply(429, RATE, {"x-ratelimit-reset-tokens": "1m30s"}), Reply(200, OK)]) as srv:
            call(srv, retries=3, sleep=slept.append)
        self.assertEqual(slept, [nh.RETRY_AFTER_CAP_S])

    def test_without_headers_the_default_schedule_outlasts_a_minute(self):
        self.assertEqual(sum(nh.RETRY_WAITS), 65.0)
        self.assertLessEqual(sum(nh.RETRY_WAITS), nh.WAIT_BUDGET_S)

    def test_step_emits_a_waiting_status_line_with_the_headers(self):
        import io
        with tempfile.TemporaryDirectory() as tmp:
            paths = InstallPaths.for_home(Path(tmp))
            store = nh.key_store(Path(tmp)); store.parent.mkdir(parents=True)
            store.write_text(f"GEMINI_API_KEY={KEY}\n"); store.chmod(0o600)
            native.allow(paths, "gemini", tmp)
            with FakeProvider([Reply(429, RATE, {"x-ratelimit-remaining-tokens": "0"}), Reply(200, OK)]) as srv:
                env = {"AGENTS_INC_NATIVE_GEMINI_URL": srv.url, nh.RETRY_WAITS_ENV: "0,0,0"}
                err = io.StringIO()
                native.step(paths, "gemini-flash", tmp, "P", 5, io.StringIO(), err, env)
        self.assertIn("rate limited, waiting", err.getvalue())
        self.assertIn("x-ratelimit-remaining-tokens=0", err.getvalue())


class DebugPrompt(unittest.TestCase):
    def run_step(self, env_extra):
        import io
        tmp = tempfile.mkdtemp()
        paths = InstallPaths.for_home(Path(tmp))
        store = nh.key_store(Path(tmp)); store.parent.mkdir(parents=True)
        store.write_text(f"GEMINI_API_KEY={KEY}\n"); store.chmod(0o600)
        native.allow(paths, "gemini", tmp)
        with FakeProvider([Reply(200, OK)] * 2) as srv:
            env = {"AGENTS_INC_NATIVE_GEMINI_URL": srv.url, **env_extra}
            native.step(paths, "gemini-flash", tmp, "FIRST PROMPT", 5, io.StringIO(), io.StringIO(), env, session="s1", agent="a1")
            native.step(paths, "gemini-flash", tmp, "SECOND PROMPT", 5, io.StringIO(), io.StringIO(), env, session="s1", agent="a1")
        return paths

    def test_flag_dumps_only_step_zero_with_mode_0600_and_no_key(self):
        paths = self.run_step({native.DEBUG_PROMPT_ENV: "1"})
        f = paths.state / "native-runs" / "gemini-flash" / "s1" / "a1" / "step0-prompt.txt"
        self.assertEqual(f.read_text(), "FIRST PROMPT")
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(KEY, f.read_text())

    def test_no_flag_no_file(self):
        paths = self.run_step({})
        self.assertFalse((paths.state / "native-runs" / "gemini-flash" / "s1" / "a1" / "step0-prompt.txt").exists())


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
