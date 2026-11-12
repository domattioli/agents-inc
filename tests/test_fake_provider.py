"""Spec 038 T002: the fake provider fixture serves its script in order and logs requests."""
import json
import os
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from fake_provider import FakeProvider, Reply  # noqa: E402


def _post(url: str, payload: object, headers: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # loopback: never through a proxy
    return opener.open(req, timeout=5)


class FakeProviderTest(unittest.TestCase):
    def test_script_in_order_then_fallback_and_request_log(self):
        with FakeProvider([Reply(200, {"text": "one"}), Reply(429, {"error": "quota"})]) as srv:
            with _post(srv.url + "/v1/generate", {"prompt": "p1"}, {"X-Test": "h"}) as r:
                self.assertEqual(json.loads(r.read()), {"text": "one"})
            with self.assertRaises(urllib.error.HTTPError) as quota:
                _post(srv.url + "/v1/generate", {"prompt": "p2"})
            self.assertEqual(quota.exception.code, 429)
            with self.assertRaises(urllib.error.HTTPError) as done:
                _post(srv.url + "/v1/generate", {})
            self.assertEqual(done.exception.code, 500)
            self.assertEqual([q.json() for q in srv.requests], [{"prompt": "p1"}, {"prompt": "p2"}, {}])
            self.assertEqual(srv.requests[0].path, "/v1/generate")
            self.assertEqual(srv.requests[0].headers.get("X-Test"), "h")

    def test_text_body(self):
        with FakeProvider([Reply(200, "not json")]) as srv:
            with _post(srv.url, {}) as r:
                self.assertEqual(r.read(), b"not json")


if __name__ == "__main__":
    unittest.main()
