"""Spec 038 T022: the Gemini call in native_http.py against tests/fixtures/fake_provider.py. No real provider."""
import os
import socket
import sys
import unittest

from agents_inc.install import native_http as nh

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402

KEY = "AIzaFAKE-native-http-1111111111111111111"


def gemini(text, usage=None):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": usage or {"promptTokenCount": 12, "candidatesTokenCount": 3, "thoughtsTokenCount": 2}}


class GeminiCall(unittest.TestCase):
    def call(self, srv, prompt="hi", max_chars=1000, timeout=5.0):
        return nh.ask("gemini", "gemini-3.8-flash", prompt, KEY, max_chars=max_chars, timeout=timeout,
                      env={"AGENTS_INC_NATIVE_GEMINI_URL": srv.url})

    def test_ok_reply_usage_and_key_only_in_header(self):
        with FakeProvider([Reply(200, gemini('{"say": "ok", "tools": []}'))]) as srv:
            text, usage = self.call(srv, prompt="PROMPT-TEXT")
        self.assertEqual(text, '{"say": "ok", "tools": []}')
        self.assertEqual(usage, {"input_tokens": 12, "cached_input_tokens": 0, "output_tokens": 5})
        [req] = srv.requests
        self.assertEqual(req.path, "/v1beta/models/gemini-3.8-flash:generateContent")
        self.assertEqual({k.lower(): v for k, v in req.headers.items()}["x-goog-api-key"], KEY)
        self.assertNotIn(KEY, req.path)
        self.assertNotIn(KEY, req.body.decode())
        self.assertEqual(req.json()["contents"][0]["parts"][0]["text"], "PROMPT-TEXT")

    def test_429_is_quota_75(self):
        with FakeProvider([Reply(429, {"error": {"message": "quota"}})]) as srv:
            with self.assertRaises(nh.StepError) as cm: self.call(srv)
        self.assertEqual(cm.exception.code, 75)
        self.assertIn("usage or rate limit", cm.exception.text)

    def test_error_body_echoing_key_is_scrubbed(self):
        with FakeProvider([Reply(400, {"error": f"bad key {KEY}"})]) as srv:
            with self.assertRaises(nh.StepError) as cm: self.call(srv)
        self.assertEqual(cm.exception.code, 1)
        self.assertNotIn(KEY, cm.exception.text)

    def test_unreachable_host_is_69(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        with self.assertRaises(nh.StepError) as cm:
            nh.ask("gemini", "gemini-3.8-flash", "hi", KEY, max_chars=100, timeout=3,
                   env={"AGENTS_INC_NATIVE_GEMINI_URL": f"http://127.0.0.1:{port}"})
        self.assertEqual(cm.exception.code, 69)
        self.assertIn("WB_NATIVE_HOST_BLOCKED", cm.exception.text)

    def test_over_limit_prompt_is_2_and_not_sent(self):
        with FakeProvider([Reply(200, gemini("x"))]) as srv:
            with self.assertRaises(nh.StepError) as cm: self.call(srv, prompt="x" * 101, max_chars=100)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("context over 100 chars", cm.exception.text)
        self.assertEqual(srv.requests, [])

    def test_empty_reply_fails(self):
        with FakeProvider([Reply(200, {"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]})]) as srv:
            with self.assertRaises(nh.StepError) as cm: self.call(srv)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("SAFETY", cm.exception.text)

    def test_url_override_only_for_loopback(self):
        self.assertEqual(nh.base_url("gemini", {"AGENTS_INC_NATIVE_GEMINI_URL": "https://evil.example"}), nh.HOSTS["gemini"])
        self.assertEqual(nh.base_url("gemini", {"AGENTS_INC_NATIVE_GEMINI_URL": "http://127.0.0.1:9/"}), "http://127.0.0.1:9")

    def test_read_key_from_store(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(nh.read_key(Path(d), "gemini"))
            store = nh.key_store(Path(d)); store.parent.mkdir(parents=True)
            store.write_text(f'OTHER=1\nGEMINI_API_KEY="{KEY}"\n')
            self.assertEqual(nh.read_key(Path(d), "gemini"), KEY)
            self.assertIsNone(nh.read_key(Path(d), "mistral"))


if __name__ == "__main__":
    unittest.main()
