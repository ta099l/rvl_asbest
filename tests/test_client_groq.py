import io
import json
import os
import unittest
from unittest import mock

from ai.james_ai import client_groq
from ai.james_ai.client_groq import GroqClient

FAKE_KEY = "test-key-not-real"


def fake_response(content: str):
    body = {"choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    return io.BytesIO(json.dumps(body).encode("utf-8"))


class GroqRequest(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"GROQ_API_KEY": FAKE_KEY})
        env.start()
        self.addCleanup(env.stop)

    def sent_request(self):
        with mock.patch.object(client_groq.urllib.request, "urlopen",
                               return_value=fake_response('{"proposals": []}')) as urlopen, \
                mock.patch.object(client_groq._log, "info"):
            answer = GroqClient().complete("prompt text")
        self.assertEqual(answer, '{"proposals": []}')
        return urlopen.call_args[0][0]

    def test_request_names_itself_so_the_firewall_lets_it_through(self):
        # Without this header Groq's firewall answers HTTP 403, error code 1010.
        req = self.sent_request()
        self.assertEqual(req.get_header("User-agent"), client_groq.USER_AGENT)
        self.assertNotIn("python-urllib", req.get_header("User-agent").lower())

    def test_key_comes_from_the_environment(self):
        req = self.sent_request()
        self.assertEqual(req.get_header("Authorization"), f"Bearer {FAKE_KEY}")

    def test_missing_key_stops_before_any_call(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaises(RuntimeError):
                GroqClient()


if __name__ == "__main__":
    unittest.main()
