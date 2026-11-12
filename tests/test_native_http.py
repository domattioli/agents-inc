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

    def test_redirect_is_refused_and_target_gets_no_request(self):
        with FakeProvider([Reply(200, gemini("x"))]) as target:
            with FakeProvider([Reply(302, {}, {"Location": target.url + "/v1beta/stolen"})]) as srv:
                with self.assertRaises(nh.StepError) as cm: self.call(srv)
            self.assertEqual(target.requests, [])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("HTTP 302: redirect refused", cm.exception.text)

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


def chat(text, usage=None):
    return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": usage or {"prompt_tokens": 20, "completion_tokens": 4, "prompt_tokens_details": {"cached_tokens": 8}}}


class ChatProviders(unittest.TestCase):
    """T040 Mistral, T041 OpenRouter: OpenAI-style chat completions against the fake server."""
    CASES = (("mistral", "ministral-3b-latest", "AGENTS_INC_NATIVE_MISTRAL_URL", "/v1/chat/completions"),
             ("openrouter", "google/gemma-4-31b-it:free", "AGENTS_INC_NATIVE_OPENROUTER_URL", "/api/v1/chat/completions"))

    def call(self, provider, slug, var, srv, prompt="hi"):
        return nh.ask(provider, slug, prompt, KEY, max_chars=1000, timeout=5.0, env={var: srv.url})

    def test_ok_reply_usage_and_bearer_header_only(self):
        for provider, slug, var, path in self.CASES:
            with self.subTest(provider=provider):
                with FakeProvider([Reply(200, chat('{"say": "ok", "tools": []}'))]) as srv:
                    text, usage = self.call(provider, slug, var, srv, prompt="PROMPT-TEXT")
                self.assertEqual(text, '{"say": "ok", "tools": []}')
                self.assertEqual(usage, {"input_tokens": 20, "cached_input_tokens": 8, "output_tokens": 4})
                [req] = srv.requests
                self.assertEqual(req.path, path)
                self.assertEqual({k.lower(): v for k, v in req.headers.items()}["authorization"], f"Bearer {KEY}")
                self.assertNotIn(KEY, req.body.decode())
                body = req.json()
                self.assertEqual(body["model"], slug)
                self.assertEqual(body["messages"], [{"role": "user", "content": "PROMPT-TEXT"}])
                self.assertEqual("response_format" in body, provider == "mistral")

    def test_429_is_quota_and_redirect_refused(self):
        for provider, slug, var, _ in self.CASES:
            with self.subTest(provider=provider):
                with FakeProvider([Reply(429, {"error": "rate"})]) as srv:
                    with self.assertRaises(nh.StepError) as cm: self.call(provider, slug, var, srv)
                self.assertEqual(cm.exception.code, 75)
                with FakeProvider([Reply(200, chat("x"))]) as target:
                    with FakeProvider([Reply(307, {}, {"Location": target.url + "/x"})]) as srv:
                        with self.assertRaises(nh.StepError) as cm: self.call(provider, slug, var, srv)
                    self.assertEqual(target.requests, [])
                self.assertIn("redirect refused", cm.exception.text)

    def test_empty_reply_and_chunked_content(self):
        with FakeProvider([Reply(200, {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}),
                           Reply(200, {"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}]})]) as srv:
            with self.assertRaises(nh.StepError) as cm: self.call("mistral", "codestral-latest", "AGENTS_INC_NATIVE_MISTRAL_URL", srv)
            self.assertIn("length", cm.exception.text)
            text, usage = self.call("mistral", "codestral-latest", "AGENTS_INC_NATIVE_MISTRAL_URL", srv)
        self.assertEqual((text, usage["input_tokens"]), ("ab", 0))

    def test_openrouter_refuses_a_slug_not_ending_free_before_any_request(self):
        for slug in ("openrouter/auto", "google/lyria-3-pro-preview", "x:free-ish", ""):
            with self.subTest(slug=slug):
                with FakeProvider([Reply(200, chat("x"))]) as srv:
                    with self.assertRaises(nh.StepError) as cm: self.call("openrouter", slug, "AGENTS_INC_NATIVE_OPENROUTER_URL", srv)
                self.assertEqual(srv.requests, [])
                self.assertEqual(cm.exception.code, 3)
                self.assertIn("WB_NATIVE_NOT_FREE", cm.exception.text)

    def test_url_override_only_for_loopback(self):
        for provider in ("mistral", "openrouter"):
            self.assertEqual(nh.base_url(provider, {nh.URL_ENV[provider]: "https://evil.example"}), nh.HOSTS[provider])
            self.assertEqual(nh.base_url(provider, {nh.URL_ENV[provider]: "http://localhost:9"}), "http://localhost:9")

    def test_adapter_config_size(self):
        """SC-003: the per-provider code for the stateless adapters stays small (whole module at most 3 x 200 lines)."""
        with open(nh.__file__) as f: self.assertLessEqual(len(f.read().splitlines()), 600)


class KeyLookupOrder(unittest.TestCase):
    """Key store, then the wrapper's key file, then ~/Projects/.env (the gask.sh/mask.sh/oask.sh order and length rule)."""
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def write(self, rel, text):
        p = self.home / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)

    def test_each_source_alone(self):
        for provider, var in (("gemini", "GEMINI_API_KEY"), ("mistral", "MISTRAL_API_KEY"), ("openrouter", "OPENROUTER_API_KEY")):
            with self.subTest(provider=provider):
                fake = f"FAKE-{provider}-file-0000000000000000"
                self.write(nh.KEY_FILES[provider], fake + "\n")
                self.assertEqual(nh.read_key(self.home, provider), fake)
                (self.home / nh.KEY_FILES[provider]).unlink()
                self.assertIsNone(nh.read_key(self.home, provider))
                self.write(nh.PROJECTS_ENV, f'{var}="FAKE-{provider}-projects-000000000000"\n')
                self.assertEqual(nh.read_key(self.home, provider), f"FAKE-{provider}-projects-000000000000")
                (self.home / nh.PROJECTS_ENV).unlink()

    def test_order_store_then_file_then_projects(self):
        self.write(nh.PROJECTS_ENV, "MISTRAL_API_KEY=FAKE-projects-00000000000000000\n")
        self.assertEqual(nh.read_key(self.home, "mistral"), "FAKE-projects-00000000000000000")
        self.write(nh.KEY_FILES["mistral"], "FAKE-file-0000000000000000000000")
        self.assertEqual(nh.read_key(self.home, "mistral"), "FAKE-file-0000000000000000000000")
        self.write(".config/workerbees/.env", "MISTRAL_API_KEY=FAKE-store-1\n")
        self.assertEqual(nh.read_key(self.home, "mistral"), "FAKE-store-1")

    def test_short_values_are_placeholders(self):
        self.write(nh.KEY_FILES["gemini"], "short")
        self.write(nh.PROJECTS_ENV, "GEMINI_API_KEY=also-short\nOPEN_ROUTER_API_KEY=FAKE-legacy-name-000000000000\n")
        self.assertIsNone(nh.read_key(self.home, "gemini"))
        self.assertEqual(nh.read_key(self.home, "openrouter"), "FAKE-legacy-name-000000000000")

    def test_missing_text_names_every_place_and_no_value(self):
        from agents_inc.install import native
        from agents_inc.install.paths import InstallPaths
        self.write(nh.KEY_FILES["gemini"], "short-placeholder")
        s = native.status_one(InstallPaths.for_home(self.home), "gemini-flash")
        for place in ("~/.config/workerbees/.env", "~/.codex-bridge/gemini-key", "~/Projects/.env"):
            self.assertIn(place, s["reason"])
        self.assertNotIn("short-placeholder", s["reason"])


if __name__ == "__main__":
    unittest.main()
